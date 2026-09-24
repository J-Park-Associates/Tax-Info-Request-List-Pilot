"""Tests for tracker/content_check.py — tier-3 rules, all local files."""

import datetime as dt

import pytest
from openpyxl import Workbook
from pypdf import PdfWriter

from tests.conftest import make_engagement
from tracker import reasons, store
from tracker.content_check import (
    CACHE_VERSION,
    ContentCache,
    check_content,
    evaluate_rules,
    extract_text,
    has_content_rules,
    rules_fingerprint,
)
from tracker.locking import engagement_lock
from tracker.manifest import RequestItem


def text_pdf(path, text: str):
    """Hand-build a minimal one-page PDF with a real text layer."""
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    bodies = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        4: b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for n in sorted(bodies):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + bodies[n] + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(bodies) + 1)
    for n in sorted(bodies):
        out += b"%010d 00000 n \n" % offsets[n]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(bodies) + 1,
        xref_at,
    )
    path.write_bytes(bytes(out))
    return path


def item(**kwargs) -> RequestItem:
    return RequestItem(identifier="A01", document="Doc", **kwargs)


# ------------------------------------------------------------------ rules ----


def test_no_rules_short_circuits(tmp_path, monkeypatch):
    # With no content rules the file must never even be opened.
    monkeypatch.setattr(
        "tracker.content_check.extract_text",
        lambda p: (_ for _ in ()).throw(AssertionError("file was read")),
    )
    result = check_content(tmp_path / "does-not-even-exist.pdf", item())
    assert result.ok
    assert not has_content_rules(item())
    assert has_content_rules(item(required_keywords=("x",)))


def test_required_keywords(tmp_path):
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement December 2025")
    assert check_content(pdf, item(required_keywords=("Chase",))).ok
    result = check_content(pdf, item(required_keywords=("Chase", "Wells Fargo")))
    assert not result.ok
    assert "'Wells Fargo'" in result.reason and reasons.WRONG_DOCUMENT.matches(result.reason)


def test_keywords_case_insensitive(tmp_path):
    pdf = text_pdf(tmp_path / "s.pdf", "CHASE BANK statement for the account")
    assert check_content(pdf, item(required_keywords=("chase", "Statement"))).ok


def test_any_keywords(tmp_path):
    pdf = text_pdf(tmp_path / "s.pdf", "Monthly account summary for December")
    assert check_content(pdf, item(any_keywords=("statement", "account summary"))).ok
    result = check_content(pdf, item(any_keywords=("invoice", "receipt")))
    assert not result.ok and "invoice, receipt" in result.reason


def test_date_pattern(tmp_path):
    pdf = text_pdf(tmp_path / "s.pdf", "Statement period: December 2025")
    assert check_content(pdf, item(date_pattern=r"(?i)december\s+2025")).ok
    result = check_content(pdf, item(date_pattern=r"(?i)january\s+2026"))
    assert not result.ok and reasons.WRONG_PERIOD.matches(result.reason)


def test_evaluate_rules_lists_all_missing():
    result = evaluate_rules("nothing here", item(required_keywords=("Alpha", "Beta")))
    assert "'Alpha'" in result.reason and "'Beta'" in result.reason


# -------------------------------------------------------------- extractors ----


def test_xlsx_extraction_with_dates(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "Payroll Register Q4 2025"
    ws["B1"] = dt.date(2025, 12, 31)
    xlsx = tmp_path / "payroll.xlsx"
    wb.save(xlsx)

    assert check_content(xlsx, item(required_keywords=("payroll",))).ok
    # Date cells match both ISO and US-style patterns.
    assert check_content(xlsx, item(date_pattern=r"2025-12-31")).ok
    assert check_content(xlsx, item(date_pattern=r"12/31/2025")).ok


def test_csv_extraction(tmp_path):
    f = tmp_path / "gl.csv"
    f.write_text("date,memo\n2025-12-01,Chase transfer\n", encoding="utf-8")
    assert check_content(f, item(required_keywords=("Chase",))).ok


def test_unsupported_extension(tmp_path):
    f = tmp_path / "notes.docx"
    f.write_bytes(b"binary")
    result = check_content(f, item(required_keywords=("x",)))
    assert not result.ok and not result.extractable
    assert ".docx" in result.reason and reasons.UNCHECKABLE_TYPE.matches(result.reason)


def test_image_only_pdf_without_ocr(tmp_path, monkeypatch):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)  # valid PDF, zero text
    scan = tmp_path / "scan.pdf"
    with scan.open("wb") as fh:
        writer.write(fh)
    monkeypatch.setattr("tracker.content_check._ocr_pdf", lambda p: None)

    result = check_content(scan, item(required_keywords=("Chase",)))
    assert not result.ok and not result.extractable
    assert reasons.NO_TEXT_LAYER.matches(result.reason)


def test_ocr_text_used_when_available(tmp_path, monkeypatch):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    scan = tmp_path / "scan.pdf"
    with scan.open("wb") as fh:
        writer.write(fh)
    monkeypatch.setattr(
        "tracker.content_check._ocr_pdf", lambda p: "Chase Bank December 2025"
    )
    assert check_content(scan, item(required_keywords=("Chase",))).ok


# --------------------------------------- photos, and the page upright ----
#
# Decision 127. Every image below is drawn here with Pillow and thrown
# away with tmp_path: no binary is committed and no client's photo is
# anywhere near the suite. The engine itself is not needed - what is
# claimed is which pixels the reading is handed, so the reader and the
# orientation detector are fakes.


def photo(path, words: str = "Form W-2 Wage and Tax Statement", size=(900, 200)):
    """A photo of a document, in a form's own words."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", size, "white")
    ImageDraw.Draw(image).text(
        (20, 60), words, font=ImageFont.load_default(size=40), fill="black",
    )
    image.save(path)
    return path


def catching_the_reading(monkeypatch, reading: str = ""):
    """Hold on to the image ``image_to_string`` is actually handed."""
    import pytesseract

    seen = {}

    def reader(image, *args, **kwargs):
        seen["image"] = image
        return reading

    monkeypatch.setattr(pytesseract, "image_to_string", reader)
    return seen


def test_a_photo_is_read_by_ocr_like_a_scanned_pdf_and_never_has_a_text_layer(tmp_path, monkeypatch):
    """An image has no text layer to be disappointed by, so it takes the
    path a scanned PDF takes: unrouted when OCR is withheld, read by OCR
    when it is not, and the reading is OCR's - which is what keeps
    decision 50's stricter rule over it."""
    from tracker.content_check import extract, extract_text

    picture = photo(tmp_path / "w-2.png")
    assert extract_text(picture) is None                   # never a text layer

    withheld = extract(picture, ocr=False)
    assert withheld.needs_ocr and withheld.text is None    # a scan, with no words yet

    monkeypatch.setattr("tracker.content_check._ocr_image", lambda p: "Chase Bank December 2025")
    reading = extract(picture)
    assert reading.from_ocr and not reading.needs_ocr
    assert "Chase" in reading.text
    assert check_content(picture, item(required_keywords=("Chase",))).ok

    # And the machine's two answers are the machine's, for a photo as for a scan.
    monkeypatch.setattr("tracker.content_check._ocr_image", lambda p: None)
    no_engine = check_content(picture, item(required_keywords=("Chase",)))
    assert no_engine.transient and reasons.NO_TEXT_LAYER.matches(no_engine.reason)
    monkeypatch.setattr("tracker.content_check._ocr_image", lambda p: "   ")
    assert reasons.NO_TEXT_AFTER_OCR.matches(
        check_content(picture, item(required_keywords=("Chase",))).reason)


def test_exif_rotation_is_undone_before_reading(tmp_path, monkeypatch):
    """A phone records which way it was held rather than turning the pixels,
    so the commonest sideways photo there is comes upright for free. It is
    undone first, before anything else looks at the image."""
    from PIL import Image, ImageDraw

    from tracker.content_check import _ocr_image

    marked = Image.new("L", (200, 100), 255)
    ImageDraw.Draw(marked).rectangle([0, 0, 19, 19], fill=0)   # a dark corner, top-left
    tag = Image.Exif()
    tag[0x0112] = 6                                            # "turn me a quarter clockwise"
    picture = tmp_path / "held sideways.png"
    marked.save(picture, exif=tag)

    seen = catching_the_reading(monkeypatch)
    monkeypatch.setattr("tracker.content_check._upright", lambda image: image)
    _ocr_image(picture)

    handed = seen["image"]
    assert handed.size == (100, 200)                           # turned, not merely flagged
    assert handed.getpixel((handed.width - 1, 0)) == 0         # the corner came round
    assert handed.getpixel((0, 0)) == 255
    assert handed.mode == "L"                                  # greyscaled once, for both readings
    assert Image.open(picture).size == (200, 100)              # the file on disk is untouched


def test_a_sideways_page_is_turned_upright_by_osd_before_reading(tmp_path, monkeypatch):
    """Tesseract reads a sideways page as nonsense, and its own orientation
    detector can say which way round it is. When it is sure, that is the
    turn - applied in memory, never to the file."""
    import pytesseract

    from tracker.content_check import _ocr_image

    picture = photo(tmp_path / "landscape.png", size=(400, 200))
    monkeypatch.setattr(pytesseract, "image_to_osd",
                        lambda image, **kw: {"rotate": 90, "orientation_conf": 5.0})
    seen = catching_the_reading(monkeypatch, "Form W-2")

    assert _ocr_image(picture) == "Form W-2"
    assert seen["image"].size == (200, 400)                    # a quarter turn, expanded
    from PIL import Image
    assert Image.open(picture).size == (400, 200)              # and nothing written

    # Under the floor the detector is a guess, and a guess decides nothing.
    monkeypatch.setattr(pytesseract, "image_to_osd",
                        lambda image, **kw: {"rotate": 90, "orientation_conf": 0.4})
    monkeypatch.setattr("tracker.content_check._four_way", lambda image: image)
    _ocr_image(picture)
    assert seen["image"].size == (400, 200)                    # left as it came


def test_when_osd_cannot_say_the_four_way_score_decides_and_a_tie_keeps_the_page_as_it_is(
    tmp_path, monkeypatch,
):
    """With the ``osd`` data missing, or too little text for the detector to
    speak, the reading itself decides: the page is read four ways and the
    reading that scored best wins. A tie, and a page nothing can be scored
    on at all, leave it exactly as it came - a turn the reading did not
    earn would be a guess."""
    import pytesseract
    from PIL import Image

    from tracker.content_check import FOUR_WAY_MIN_WORDS, _upright

    def osd_cannot_say(image, **kw):
        raise pytesseract.TesseractError(1, "Too few characters. Skipping this page")

    monkeypatch.setattr(pytesseract, "image_to_osd", osd_cannot_say)
    page = Image.new("L", (400, 200), 255)

    scores = iter([10.0, 90.0, 20.0, 30.0])                    # the second turn reads best
    def by_turn(image, **kw):
        confidence = next(scores)
        return {"text": ["Wage", "and", "Statement"], "conf": [confidence] * 3}

    monkeypatch.setattr(pytesseract, "image_to_data", by_turn)
    assert _upright(page).size == (200, 400)                   # turned by what it read

    tied = {"text": ["Wage", "and", "Statement"], "conf": [50.0] * 3}
    monkeypatch.setattr(pytesseract, "image_to_data", lambda image, **kw: tied)
    assert _upright(page) is page                              # a tie keeps 0

    too_few = {"text": ["W"] * 9, "conf": [99.0] * 9}          # one letter each: not words
    monkeypatch.setattr(pytesseract, "image_to_data", lambda image, **kw: too_few)
    assert _upright(page) is page
    assert FOUR_WAY_MIN_WORDS == 3

    nothing = {"text": ["Wage", "and"], "conf": [99.0, -1.0]}  # -1: no word was made of it
    monkeypatch.setattr(pytesseract, "image_to_data", lambda image, **kw: nothing)
    assert _upright(page) is page


def test_a_rotated_scanned_pdf_page_goes_through_the_same_upright_step(tmp_path, monkeypatch):
    """One orientation step, used by both readings: a scanned PDF's page is
    turned the same way a photo is, which is the half of decision 127 the
    harness of 2026-09-19 asked for."""
    import pytesseract
    from pypdf import PdfWriter

    from tracker.content_check import _ocr_pdf

    writer = PdfWriter()
    writer.add_blank_page(width=792, height=612)               # landscape, as a sideways scan is
    scan = tmp_path / "scan.pdf"
    with scan.open("wb") as fh:
        writer.write(fh)

    monkeypatch.setattr(pytesseract, "image_to_osd",
                        lambda image, **kw: {"rotate": 90, "orientation_conf": 5.0})
    seen = catching_the_reading(monkeypatch, "Form 1099-R")

    assert _ocr_pdf(scan).strip() == "Form 1099-R"
    handed = seen["image"]
    assert handed.height > handed.width                        # a portrait page, turned in memory
    assert handed.mode == "L"
    assert scan.read_bytes()[:5] == b"%PDF-"                   # the file itself, untouched


def test_the_cache_version_moved_so_a_verdict_read_sideways_is_read_again(tmp_path):
    """A verdict reached at version 9 may have been reached on nonsense: the
    page it was read from was never turned upright. The cache is
    disposable, so the version moves and the first pass after this
    decision re-reads those scans once. (Decision 141 moved it again, for
    the notice's first-page phrases.)"""
    assert CACHE_VERSION == 11

    rule = item(required_keywords=("Chase",))
    engagement = an_engagement(tmp_path, rule)
    fingerprint = rules_fingerprint(rule)
    conn = store.connect()
    engagement_id = store._engagement_row(conn, engagement)["id"]
    conn.execute(
        f"INSERT INTO {store.VERDICTS_TABLE} (engagement_id, digest, fingerprint, version, verdict) "
        "VALUES (?, ?, ?, ?, ?)", (engagement_id, "sideways", fingerprint, 9, '{"ok": true}'))

    assert ContentCache(engagement).get_by_digest("sideways", fingerprint) is None


def test_a_slow_reading_is_said_and_never_cut_short(tmp_path, monkeypatch):
    """The number the reader benchmark and the owner's speed ceiling are
    measured in. Nothing acts on it: a reading that takes its time is
    finished, its words are the words the row is decided on, and the run's
    own line says which document took them."""
    import time as clock

    from tracker.content_check import extract
    from tracker.runner import SLOW_READING_NOTE, SLOW_READING_SECONDS

    def a_slow_reader(path):
        clock.sleep(0.05)
        return "Chase Bank December 2025, every word of it"

    monkeypatch.setattr("tracker.content_check._ocr_image", a_slow_reader)
    monkeypatch.setattr("tracker.runner.SLOW_READING_SECONDS", 0.01)

    reading = extract(photo(tmp_path / "slow.png"))
    assert reading.seconds >= 0.05                             # timed
    assert reading.text.endswith("every word of it")           # and read to the end

    run = an_engagement_run(slowest=[("slow.png", reading.seconds)])
    assert SLOW_READING_NOTE.format(name="slow.png", seconds=reading.seconds) in run.summary()
    assert SLOW_READING_SECONDS == 20.0                        # the shipped threshold

    quiet = an_engagement_run(slowest=[("quick.pdf", 0.001)])
    assert "slow reading" not in quiet.summary()


def an_engagement_run(**kwargs):
    """One run row, enough of one to read its summary line."""
    from pathlib import Path

    from tracker.registry import Engagement
    from tracker.runner import EngagementRun

    return EngagementRun(engagement=Engagement(path=Path("Smith 2025")), **kwargs)


# ------------------------------------------------------------------- cache ----


def counting_extractor(monkeypatch):
    calls = {"n": 0}
    real = extract_text

    def wrapped(path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setattr("tracker.content_check.extract_text", wrapped)
    return calls


def an_engagement(tmp_path, *rules):
    """An engagement the store holds, whose request list is ``rules``."""
    return make_engagement(tmp_path / "Clients", list(rules), household="Smith Family",
                           scaffold=False)


def cache_rows(engagement):
    """The engagement's cache as the store holds it at CACHE_VERSION: (memos, verdicts)."""
    return store.cached_verdicts(store.connect(), engagement, version=CACHE_VERSION)


def saved(cache, engagement):
    with engagement_lock(engagement):
        cache.save()


def test_a_verdict_is_served_from_the_store_and_the_document_read_once(tmp_path, monkeypatch):
    calls = counting_extractor(monkeypatch)
    rule = item(required_keywords=("Chase",))
    engagement = an_engagement(tmp_path, rule)
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement December 2025")
    cache = ContentCache(engagement)

    assert check_content(pdf, rule, cache).ok
    assert check_content(pdf, rule, cache).ok
    assert calls["n"] == 1                       # second call served from the cache

    saved(cache, engagement)
    reopened = ContentCache(engagement)          # loaded from the store, not from memory
    assert check_content(pdf, rule, reopened).ok
    assert calls["n"] == 1                       # survives a save and a fresh load

    text_pdf(pdf, "Chase Bank Statement December 2025 v2")      # file changed -> re-extract
    assert check_content(pdf, rule, reopened).ok
    assert calls["n"] == 2

    stricter = item(required_keywords=("Chase", "Wells Fargo"))
    assert not check_content(pdf, stricter, reopened).ok  # rules changed
    assert calls["n"] == 3
    assert rules_fingerprint(rule) != rules_fingerprint(stricter)


def test_the_cache_is_keyed_on_content_not_path(tmp_path, monkeypatch):
    # A routed drop and its working copy are the same bytes under two
    # names; the second name must be a hit, not a second read.
    calls = counting_extractor(monkeypatch)
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement December 2025")
    rule = item(required_keywords=("Chase",))
    cache = ContentCache()
    assert check_content(pdf, rule, cache).ok
    copy = tmp_path / "A01 - Bank Statement.pdf"
    copy.write_bytes(pdf.read_bytes())
    assert check_content(copy, rule, cache).ok
    assert calls["n"] == 1
    assert cache.digest_of(copy) == cache.digest_of(pdf)


def test_a_verdict_row_at_another_cache_version_is_ignored_and_dropped_on_save(tmp_path):
    # Version 6 stored verdicts with no evidence at all; reading one back
    # would say a verdict had no reason behind it, which is worse than
    # re-extracting once. Version 7 was read before decision 85 taught
    # says() that a form heading its line with its printed title and its
    # year names itself, so a version-7 verdict would say a one-copy W-2
    # is nobody's form. Version 8 was read before decision 90 let a
    # keyword name alternatives, so a version-8 verdict read the "|" and
    # the "+" in one as words to look for and found neither. Version 9 was
    # read before decision 127 turned a page upright, so a verdict on a
    # scan that came through it may have been reached on nonsense. The
    # version is carried per row now (decision 107), and it still means
    # all that. Version 10 was read before decision 141 kept a notice's
    # header phrases to its first page.
    assert CACHE_VERSION == 11
    rule = item(required_keywords=("Chase",))
    engagement = an_engagement(tmp_path, rule)
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement December 2025")
    fingerprint = rules_fingerprint(rule)
    conn = store.connect()
    engagement_id = store._engagement_row(conn, engagement)["id"]
    conn.execute(
        f"INSERT INTO {store.VERDICTS_TABLE} (engagement_id, digest, fingerprint, version, verdict) "
        "VALUES (?, ?, ?, ?, ?)", (engagement_id, "deadbeef", fingerprint, 6, '{"ok": true}'))

    cache = ContentCache(engagement)
    assert cache.get_by_digest("deadbeef", fingerprint) is None      # not this version's
    assert check_content(pdf, rule, cache).evidence                  # read, with its evidence
    saved(cache, engagement)

    versions = [row[0] for row in conn.execute(
        f"SELECT version FROM {store.VERDICTS_TABLE} WHERE engagement_id = ?", (engagement_id,))]
    assert versions == [CACHE_VERSION]                               # the old row is gone
    _memos, verdicts = cache_rows(engagement)
    assert "deadbeef" not in verdicts and len(verdicts) == 1


def test_a_save_that_fails_leaves_the_previous_verdicts(tmp_path, monkeypatch):
    import sqlite3

    rule = item(required_keywords=("Chase",))
    engagement = an_engagement(tmp_path, rule)
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement December 2025")
    cache = ContentCache(engagement)
    check_content(pdf, rule, cache)
    saved(cache, engagement)
    before = cache_rows(engagement)
    assert before[0] and before[1]

    real = store.connect()

    class FailsOnTheVerdict:
        """The process's connection, whose verdict write raises mid-transaction."""

        def execute(self, sql, *args):
            if f"INTO {store.VERDICTS_TABLE}" in sql:
                raise sqlite3.OperationalError("disk I/O error")
            return real.execute(sql, *args)

        def __getattr__(self, name):
            return getattr(real, name)

    monkeypatch.setattr(store, "connect", lambda path=None: FailsOnTheVerdict())
    text_pdf(pdf, "Chase Bank Statement December 2025 v2")        # a memo and a verdict to write
    check_content(pdf, rule, cache)
    with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
        saved(cache, engagement)
    monkeypatch.undo()

    assert cache_rows(engagement) == before                          # the memo write rolled back too
    assert real.in_transaction is False


def test_a_cache_with_no_engagement_never_touches_the_store(tmp_path, monkeypatch):
    def never(path=None):
        raise AssertionError("the store was asked for")

    monkeypatch.setattr(store, "connect", never)
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement December 2025")
    rule = item(required_keywords=("Chase",))
    cache = ContentCache()
    assert check_content(pdf, rule, cache).ok
    assert cache.get(pdf, rules_fingerprint(rule)) is not None
    cache.save()                                                     # nothing to touch, no lock needed


def test_a_cache_for_an_engagement_the_store_does_not_hold_is_refused_by_name(tmp_path):
    folder = tmp_path / "Clients" / "Nobody 2025"
    folder.mkdir(parents=True)
    with pytest.raises(store.StoreError, match="does not hold this engagement") as raised:
        ContentCache(folder)
    assert folder.name in str(raised.value)


def test_a_transient_verdict_is_still_never_cached(tmp_path, monkeypatch):
    from tracker.content_check import Extraction

    monkeypatch.setattr("tracker.content_check.extract", lambda path, ocr=True: Extraction(
        None, reason=reasons.NO_TEXT_LAYER.format(), extractable=False, transient=True))
    rule = item(required_keywords=("Chase",))
    engagement = an_engagement(tmp_path, rule)
    pdf = text_pdf(tmp_path / "s.pdf", "a scan")
    cache = ContentCache(engagement)

    verdict = check_content(pdf, rule, cache)
    assert verdict.transient and not verdict.ok
    assert cache.get(pdf, rules_fingerprint(rule)) is None
    saved(cache, engagement)
    memos, verdicts = cache_rows(engagement)
    assert memos and verdicts == {}                                  # the digest, never the verdict


def test_the_cache_save_refuses_outside_the_engagement_lock(tmp_path):
    rule = item(required_keywords=("Chase",))
    engagement = an_engagement(tmp_path, rule)
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement December 2025")
    cache = ContentCache(engagement)
    check_content(pdf, rule, cache)

    with pytest.raises(store.StoreError, match="engagement lock"):
        cache.save()
    assert cache_rows(engagement) == ({}, {})
    saved(cache, engagement)                                         # the same save, under the lock
    assert cache_rows(engagement) != ({}, {})


def test_own_forms_is_none_for_one_family_and_the_named_set_for_two():
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.content_check import MULTI_FORM_FAMILIES, own_forms, self_named_forms

    one = "\n".join(scanned_w2_lines(2025))
    two = "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025))
    assert MULTI_FORM_FAMILIES == 2
    assert own_forms(one) is None                                  # the ordinary reading
    assert own_forms("a letter about nothing in particular") is None
    assert own_forms(two) == set(self_named_forms(two)) == {"w2", "1098"}


def test_on_every_corpus_form_the_scans_miss_verdict_equals_the_routers_kept_verdict():
    """For every placement in tests/irs/: route with a memory cache, then
    read the same file through check_content() with an empty cache on the
    row(s) it filed under. The kept verdict and the miss verdict are one
    verdict - ok, reason and evidence - so a rebuilt store reaches what
    the router filed on."""
    from tests.test_irs_forms import EXPECT, IRS
    from tracker.manifest import validated
    from tracker.router import route_file
    from tracker.templates import template_items

    catalogs: dict = {}

    def rows(form, year):
        if (form, year) not in catalogs:
            from dataclasses import replace
            catalogs[(form, year)] = [replace(i, min_size_kb=0, date_pattern="")
                                      for i in validated(template_items(form, year=year))]
        return catalogs[(form, year)]

    compared = 0
    for pdf, form, year, expected in EXPECT:
        if expected is None:
            continue
        items = rows(form, year)
        kept = ContentCache()
        routing = route_file(IRS / pdf, items, cache=kept)
        assert routing.identifier == expected, (pdf, form, routing.reason)
        for identifier in (routing.identifier, *routing.also):
            row = next(i for i in items if i.identifier == identifier)
            remembered = kept.get(IRS / pdf, rules_fingerprint(row))
            assert remembered is not None, (pdf, form, identifier)
            miss = check_content(IRS / pdf, row, ContentCache())
            assert (miss.ok, miss.reason, miss.evidence) == (
                remembered.ok, remembered.reason, remembered.evidence), (pdf, form, identifier)
            compared += 1
    assert compared >= len([e for e in EXPECT if e[3] is not None])


def test_cache_prune(tmp_path):
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement page")
    rule = item(required_keywords=("Chase",))
    cache = ContentCache()
    check_content(pdf, rule, cache)
    assert cache.get(pdf, rules_fingerprint(rule)) is not None

    cache.prune(existing=set())                   # file no longer in any folder
    assert cache.get(pdf, rules_fingerprint(rule)) is None


def _many_page_pdf(path, texts):
    """One page per entry in ``texts``, each with a real text layer."""
    pages = []
    for text in texts:
        content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
        pages.append(content)
    n = len(pages)
    objects = {1: b"<< /Type /Catalog /Pages 2 0 R >>"}
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n)).encode()
    objects[2] = b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % n
    font_id = 3 + 2 * n
    for i, content in enumerate(pages):
        page_id, stream_id = 3 + 2 * i, 4 + 2 * i
        objects[page_id] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R "
            b"/Resources << /Font << /F1 %d 0 R >> >> >>" % (stream_id, font_id)
        )
        objects[stream_id] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)
    objects[font_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += b"%d 0 obj\n" % num + objects[num] + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for num in sorted(objects):
        out += b"%010d 00000 n \n" % offsets[num]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objects) + 1, xref)
    path.write_bytes(bytes(out))
    return path


def test_only_the_first_pages_of_a_pdf_are_read(tmp_path):
    from tracker.content_check import extract_text

    texts = [f"page {i + 1} filler" for i in range(15)]
    texts[2] = "Form W-2 early"
    texts[12] = "Form 1098 late"
    text = extract_text(_many_page_pdf(tmp_path / "long.pdf", texts))
    assert "W-2 early" in text
    assert "1098 late" not in text
    assert "page 10 filler" in text and "page 11 filler" not in text


# ------------------------------------------------ a form's own number ----


@pytest.mark.parametrize("text, own", [
    ("Form 1040 (2025)", "1040"), ("Form 1099-DIV (Rev. January 2024)", "1099div"), ("941 for 2026:", "941"),
    ("Form W-2 Wage and Tax Statement 2025", "w2"),        # plain: nothing quotes it, it is named in its own right
])
def test_a_form_names_itself_with_its_year_or_revision(text, own):
    from tracker.content_check import _PLAIN_WEIGHT, _mentions

    (key, _, weight), = list(_mentions(text.lower()))
    assert key == own and weight >= _PLAIN_WEIGHT


@pytest.mark.parametrize("text", [
    "(Form 1040)", "Form 1040 or 1040-SR", "Form 1040 instructions", "Form 1040, line 8", "Form 1040 for individuals",
    "attach Form 1098", "Forms W-2", "reported on Form 1099-INT", "a 1098 - for my return", "see Form 1099-NEC, to use",
    "such as Form 1040)", "Interest and dividends: attach Forms 1099-INT and 1099-DIV",
])
def test_a_form_quoted_in_a_sentence_is_a_reference(text):
    from tracker.content_check import _REFERENCE_WEIGHT, _mentions

    assert all(weight == _REFERENCE_WEIGHT for _, _, weight in _mentions(text.lower()))


def test_the_dominant_form_is_the_heaviest_then_the_first_mentioned():
    from tracker.content_check import dominant_forms

    # A W-2's instructions name Form 1040 many times; the W-2 names itself with its year.
    assert dominant_forms("Form W-2 (2025) " + "see Form 1040 line 1. " * 30) == {"w2"}
    # Two forms named in their own right, equally: the first mentioned.
    assert dominant_forms("Form 1099-INT (2025) Interest Income\nForm 1099-DIV (2025) Dividends") == {"1099int"}
    # Once in passing, beside another form: nobody's.
    assert dominant_forms("You must file Form 941, Form 940 and Form W-2.") == set()
    # A number that is not a known family counts only after "Form", and takes a variant only by a dash.
    assert dominant_forms("Form 4562 (2025) Depreciation and Amortization") == {"4562"}
    assert dominant_forms("4562 4562 4562 (2025)") == set()
    assert dominant_forms("Form 1125-E (Rev. October 2016) Compensation of Officers") == {"1125e"}
    assert dominant_forms("Form 4562 depreciation\nForm 4562 depreciation") == {"4562"}   # "4562 depreciation" is not 4562-DEPR


def test_a_form_told_to_the_reader_is_a_reference_whatever_follows_it():
    # The tenth reading: "attach Form 1098 (2025)" read as a form naming
    # itself, because the year was looked at before the word in front.
    from tracker.content_check import _REFERENCE_WEIGHT, _mentions, says

    for text in ("attach Form 1098 (2025)", "see Form 1098 for 2025 mailed separately", "Forms W-2 2025"):
        assert all(weight == _REFERENCE_WEIGHT for _, _, weight in _mentions(text.lower())), text
    assert not says("2025 Individual Income Tax Organizer\nMortgage interest paid: attach Form 1098 (2025)", "1098")
    assert not says("Annual Escrow Account Disclosure Statement\nFor your deduction, see Form 1098 for 2025.", "1098")


def test_a_title_that_lists_three_forms_names_none_of_them():
    from tracker.content_check import _title_forms, says

    checklist = ("2025 Individual Income Tax Organizer\nIncome Documents Checklist\n"
                 "Form W-2 - Wage and Tax Statement\nForm 1098 - Mortgage Interest Statement\n"
                 "Form 1099-INT - Interest Income\nForm 1099-DIV - Dividends and Distributions")
    assert _title_forms(checklist.lower()) == set()
    assert not says(checklist, "1098") and not says(checklist, "1099-int")
    # A transmittal lists its forms with commas, and every form after one
    # continues the list (the thirteenth reading), which leaves the first
    # naming itself - and the firm's letter is still none of the rows'
    # documents, because none of them asks for a W-2 by its number alone.
    transmittal = "Enclosed please find: Form W-2 2025, Form 1098 2025, Form 1099-INT 2025"
    assert _title_forms(transmittal.lower()) == {"w2"}
    assert not says(transmittal, "1098") and not says(transmittal, "1099-int")
    # Families, not numbers: a broker's consolidated 1099 names the family and
    # its parts and is one family's document, which the rows then contest.
    composite = ("vanguard brokerage services\n2025 consolidated form 1099 - account 8812-4455\n"
                 "form 1099-int   interest income\nform 1099-div   dividends and distributions\n"
                 "form 1099-b   proceeds from broker and barter exchange transactions")
    assert _title_forms(composite) == {"1099int", "1099div", "1099b"}   # "Form 1099 - Account" is set off by its dash
    assert says(composite, "1099-int") and says(composite, "1099-b")
    # A checklist sets a form off from its title with a dash; no form names itself that way.
    assert _title_forms("form 1099-int - interest income\nform 1099-div - dividends and distributions") == set()
    assert _title_forms("form 1099-int   interest income   2025\nform 1099-div   dividends   2025") == {"1099int", "1099div"}
    assert _title_forms("form w-2 - 2025 wage and tax statement") == {"w2"}     # a dash before the year is still dated
    # A sentence wraps where it will: the word before a form may end the line above.
    assert not says("2025 organizer\nmortgage interest paid: please attach\nform 1098 (2025) from each lender", "1098")
    assert not says("annual escrow account disclosure\nfor your deduction, see\nform 1098 for 2025 mailed separately", "1098")


def test_a_form_number_in_the_title_counts_only_when_named_in_its_own_right():
    from tracker.content_check import says

    attention = ("Attention: Which Revision To Use for Which Year. For all forms that we do not issue annually "
                 "(such as Form 1099-NEC), we issue the revision to use for the next calendar year. ")
    assert not says(attention + "Form 1098-T Tuition Statement 2025", "1099-nec")
    assert says(attention + "Form 1098-T Tuition Statement 2025", "1098-t")
    assert not says("2025 Tax Organizer\nMortgage interest: attach Form 1098\nRetirement: attach Forms 1099-R", "1098")
    assert says("Form 1098 Mortgage Interest Statement 2025", "1098")
    assert says("Attached: Form 1099-INT, Form 1098 and W-2 for 2025 tax prep\nForm W-2 Wage and Tax Statement", "w-2")
    assert not says("Subject: Your 2025 Form 1099-R is ready\nForm 5498 IRA Contribution Information 2025", "1099-r")


def test_a_single_dash_set_off_form_beside_its_year_names_itself():
    # Decision 69 made a dash after a form number a checklist's line, which
    # parked a payer's own substitute form: "2025 Form 1099-INT - Interest
    # Income" is how a bank prints its title. A menu *lists* - two such
    # lines or more in the title window - and a single one, dated on its
    # own line, is a form naming itself.
    from tracker.content_check import _title_forms, says

    assert says("2025 Form 1099-INT - Interest Income\nAlly Bank  1 Interest income 1,842.55", "1099-int")
    assert says("Form 1098 - Mortgage Interest Statement  2025\n1 Mortgage interest received 14,220.19", "1098")
    menu = ("2025 Individual Income Tax Organizer - Interest and Dividend Income\n"
            "Form 1099-INT - Interest Income\nForm 1099-DIV - Dividends and Distributions")
    assert _title_forms(menu.lower()) == set()
    # No year beside it: a checklist's line, as before.
    assert not says("Income Documents\nForm 1099-INT - Interest Income\nPayer  Amount", "1099-int")
    # An ask before it is an ask, year or no year.
    assert not says("2025 Organizer\nPlease attach Form 1098 - Mortgage Interest Statement 2025", "1098")


def test_a_form_after_a_comma_continues_a_list():
    # A cover's last form carries no punctuation after it, so it was read as
    # named in its own right and blinded the form printed behind it.
    from tracker.content_check import says

    cover = ("Charles Schwab  2025 Tax Reporting Package\n"
             "Enclosed: Form 1099-INT, Form 1098, Form 5498\n"
             "Form 1099-INT Interest Income 2025\n1 Interest income 1,842.55")
    assert not says(cover, "5498") and not says(cover, "1098")
    assert says(cover, "1099-int")


def test_a_menu_line_names_neither_the_form_nor_its_title():
    # The form and its title on a checklist line are one reference: the
    # firm's organizer sets "Form 1099-B" off from "Proceeds From Broker
    # and Barter Exchange Transactions" with a dash, and the row that keys
    # on the broker's words filed the organizer page as the client's 1099-B.
    from tracker.content_check import says

    page = ("2025 Individual Income Tax Organizer - Investment Income\n"
            "Form 1099-B - Proceeds From Broker and Barter Exchange Transactions\n"
            "Form 1099-DIV - Dividends and Distributions\n"
            "Please list every brokerage account below.  Broker  Account number")
    assert not says(page, "1099-b")
    assert not says(page, "proceeds from broker")
    # A comma sets a form off from its title the same way.
    assert not says("Form 1099-INT, Interest Income\nPayer  Amount", "interest income")
    # The form's own page is not a menu, so its title is its own.
    assert says("Form 1099-B Proceeds From Broker and Barter Exchange Transactions 2025\n"
                "1d Proceeds 24,318.55", "proceeds from broker")


def test_a_document_does_not_ask_for_itself():
    # An ask governs the rest of its sentence, because one ask names several
    # documents; across a line break it governs only the wrap.
    from tracker.content_check import says

    organizer = ("2025 Individual Income Tax Organizer - Investment Income\n"
                 "Did you sell any stocks, bonds or mutual funds in 2025?\n"
                 "If yes, attach your brokerage statement and any realized gain and loss report.")
    assert not says(organizer, "brokerage statement")
    assert not says(organizer, "realized gain and loss")
    fiduciary = ("2025 Fiduciary Organizer - Investment Income\n"
                 "Attach the year-end account statement for each brokerage account.\n"
                 "Attach the realized gain and loss report for the year.")
    assert not says(fiduciary, "year-end account statement")
    assert not says(fiduciary, "realized gain and loss")
    assert not says("Mortgage interest: please attach\nyour brokerage statement", "brokerage statement")
    # The broker's own statement says it plainly, and a line further up than
    # the wrap is another label, not the rest of a request: a return's
    # "Attach Forms W-2G and 1099-R if tax was withheld" two lines above its
    # jurat asks for nothing on the jurat's line.
    assert says("Charles Schwab & Co., Inc.\nYear-End Brokerage Statement January 1, 2025 - December 31, 2025\n"
                "Realized Gain and Loss Summary", "brokerage statement")
    assert says("Attach Forms W-2G and 1099-R if tax was withheld\n1e Taxable dependent care benefits\n"
                "Sign Here Under penalties of perjury, I declare", "under penalties of perjury")


def test_a_keyword_may_name_alternatives_and_the_words_one_of_them_wants_together():
    # Decision 90. Required Keywords is an AND over its cells and Any
    # Keywords an OR over theirs, and neither can say "these three words,
    # or this one" - which is what the prior-year return row has to say,
    # because a standalone state return shares none of the federal
    # return's lines, jurat included.
    from tracker.content_check import contains_keyword, says

    prior_return = ("individual income tax return + filing status + under penalties of perjury"
                    " | resident income tax return")
    federal = ("Form 1040 2024 U.S. Individual Income Tax Return\n"
               "Filing Status Single Married filing jointly\n"
               "Sign Here Under penalties of perjury, I declare")
    state = "TAXABLE YEAR FORM\n2024 California Resident Income Tax Return 540"
    assert says(federal, prior_return)
    assert says(state, prior_return)
    # Two of the three is not the federal alternative: the firm's own
    # organizer says both and signs nothing (decision 65).
    assert not says("2024 Individual Income Tax Organizer\nFiling Status Single", prior_return)
    # A keyword holding neither character is one phrase, exactly as before.
    assert says("Trial Balance - Year-End 2025", "trial balance")
    # A file name is read the same way, phrase by phrase.
    assert contains_keyword("2024 california resident income tax return", prior_return)
    assert not contains_keyword("2024 individual income tax return", prior_return)


def test_the_alternatives_of_a_keyword_are_read_where_a_keyword_cell_is_read():
    # In the module that owns how a keyword cell is read, so the catalog
    # and the matcher cannot disagree about what one keyword means.
    from tracker.manifest import keyword_alternatives

    assert keyword_alternatives("trial balance") == (("trial balance",),)
    assert keyword_alternatives("a + b | c") == (("a", "b"), ("c",))
    assert keyword_alternatives("  spaced  +  out  ") == (("spaced", "out"),)
    assert keyword_alternatives("|") == ()


def test_the_any_keywords_are_read_apart_from_every_other_rule():
    # The year a Period implies is a check on a document a keyword already
    # matched, so the router can ask which rows a document's words fit
    # without reading a verdict's sentence back.
    from tracker.content_check import any_keyword_matched

    childcare = item(any_keywords=("child care statement",), date_pattern=r"(?i)\b2025\b")
    assert any_keyword_matched("2024 Child Care Statement", childcare)
    assert not any_keyword_matched("2024 Tuition Statement", childcare)
    assert not any_keyword_matched("anything at all", item(required_keywords=("w-2",)))


# ------------------------------------------------ a keyword's words on one line ----


def test_a_keywords_words_are_on_one_line_or_wrap_as_a_heading():
    from tracker.content_check import contains_keyword

    # Two labels on two lines are not one phrase.
    assert not contains_keyword("19 Distributions\nSchedule K-1 (Form 1065) 2025", "distribution schedule")
    assert not contains_keyword("16 Items affecting shareholder basis\nSchedule K-1 (Form 1120-S)", "shareholder basis schedule")
    # A heading wraps from the start of its line, two words or more on the first.
    assert contains_keyword("Balance Sheet\nAs of December 31, 2025", "balance sheet as of")
    assert contains_keyword("  Fixed Asset\n  Schedule", "fixed asset schedule")
    assert contains_keyword("Statement of\nFinancial Position", "statement of financial position")
    # One word over another is two labels; the 1098's one-word-per-line title is known by its number.
    assert not contains_keyword("Mortgage\nInterest\nStatement", "mortgage interest statement")
    assert not contains_keyword("Distributions\nSchedule", "distribution schedule")
    # A phrase that begins mid-line and runs on is a sentence, not a heading.
    assert not contains_keyword("the items affecting shareholder basis\nschedule", "shareholder basis schedule")
    # One line, as before: spaces, tabs, a no-break space, a dash.
    assert contains_keyword("Fixed\xa0Asset\tSchedule", "fixed asset schedule")
    assert contains_keyword("fixed-asset-schedule.pdf", "fixed asset schedule")
    assert not contains_keyword("W\n2", "w-2")


def test_a_sheets_row_is_a_line_and_its_cells_are_set_apart(tmp_path):
    from tracker.content_check import contains_keyword

    wb = Workbook()
    ws = wb.active
    ws.append(["Fixed Asset", "Schedule"])
    ws.append(["Distributions"])
    ws.append(["Schedule"])
    path = tmp_path / "book.xlsx"
    wb.save(path)
    text = extract_text(path)
    assert "Fixed Asset\tSchedule" in text
    assert contains_keyword(text, "fixed asset schedule")
    assert not contains_keyword(text, "distribution schedule")


# --------------------------------------------------------------- evidence ----


#: A W-2 as a reader meets it: its number and title at the top, its own
#: number again at the foot of page 1 the way the IRS sets it, and a box
#: label deep on page 2 that no footer and no title carries.
_FILLER = "Wage and Tax Statement for the employee named below. " * 12
TWO_PAGE_W2 = (
    "Form W-2 (2025) Wage and Tax Statement\n" + _FILLER
    + "\nemployer identification number 00-0000000\nForm W-2 (2025)\n"
    + "\f" + "dependent care benefits paid in the year\n" + _FILLER
    + "\nsafe harbor election\nCopy B to be filed with the return\n"
)


def test_a_title_self_mention_is_evidence_from_the_title():
    from tracker.content_check import RULE_REQUIRED, WHERE_TITLE

    result = evaluate_rules(TWO_PAGE_W2, item(required_keywords=("W-2", "wage and tax statement")))
    assert result.ok
    assert [(e.rule, e.term, e.where, e.page) for e in result.evidence] == [
        (RULE_REQUIRED, "W-2", WHERE_TITLE, 1),
        (RULE_REQUIRED, "wage and tax statement", WHERE_TITLE, 1),
    ]


def test_a_footer_hit_names_the_footer_and_the_page_it_was_on():
    from tracker.content_check import WHERE_FOOTER

    result = evaluate_rules(TWO_PAGE_W2, item(required_keywords=("safe harbor election",)))
    assert result.ok
    assert [(e.where, e.page) for e in result.evidence] == [(WHERE_FOOTER, 2)]
    # Page 1's own footer is a footer too, not "the first page".
    first = evaluate_rules(TWO_PAGE_W2, item(required_keywords=("employer identification number",)))
    assert [(e.where, e.page) for e in first.evidence] == [(WHERE_FOOTER, 1)]


def test_a_deep_any_keyword_says_it_was_deep_and_which_page():
    from tracker.content_check import RULE_ANY, WHERE_DEEP

    result = evaluate_rules(TWO_PAGE_W2, item(any_keywords=("dependent care benefits", "tips")))
    assert result.ok
    # Only the keyword that matched leaves evidence; "tips" said nothing.
    assert [(e.rule, e.term, e.where, e.page) for e in result.evidence] == [
        (RULE_ANY, "dependent care benefits", WHERE_DEEP, 2),
    ]


def test_the_date_rule_records_the_period_it_checked_never_the_document():
    from tracker.content_check import RULE_DATE

    rule = item(period="TY2025", date_pattern=r"(?i)\b2025\b",
                required_keywords=("wage and tax statement",))
    result = evaluate_rules(TWO_PAGE_W2, rule)
    assert result.ok
    dates = [e for e in result.evidence if e.rule == RULE_DATE]
    # The row's own Period, which a person can read; the regex it derives is
    # in the reason when the check fails, and no word of the document is here.
    assert [e.term for e in dates] == ["TY2025"]


def test_a_failing_verdict_keeps_what_did_match():
    # The verdict and its sentence are untouched; what matched is the lead a
    # person works the parked file from.
    result = evaluate_rules(
        TWO_PAGE_W2, item(required_keywords=("wage and tax statement", "1099-INT")),
    )
    assert not result.ok and "'1099-INT'" in result.reason
    assert [e.term for e in result.evidence] == ["wage and tax statement"]


def test_the_compact_evidence_parses_back_to_what_was_formatted():
    from tracker.content_check import (
        RULE_FILENAME,
        WHERE_TITLE,
        Evidence,
        format_evidence,
        parse_evidence,
    )

    record = {
        "C01": evaluate_rules(TWO_PAGE_W2, item(
            period="TY2025", date_pattern=r"(?i)\b2025\b",
            required_keywords=("W-2", "safe harbor election"),
            any_keywords=("dependent care benefits",),
        )).evidence,
        "L01": (Evidence(RULE_FILENAME, "1098-t", WHERE_TITLE),),
    }
    written = format_evidence(record)
    assert "C01: W-2@title:1 required" in written
    assert "L01: 1098-t@title filename" in written   # a name has no page
    assert parse_evidence(written) == record
    assert parse_evidence("") == {}


def test_a_verdict_read_back_from_the_store_brings_its_evidence(tmp_path):
    from tracker.content_check import RULE_REQUIRED, WHERE_TITLE

    rule = item(required_keywords=("Chase",))
    engagement = an_engagement(tmp_path, rule)
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement December 2025")
    cache = ContentCache(engagement)
    assert check_content(pdf, rule, cache).ok
    saved(cache, engagement)

    reopened = ContentCache(engagement)
    hit = reopened.get(pdf, rules_fingerprint(rule))
    assert hit is not None and hit.ok
    assert [(e.rule, e.term, e.where) for e in hit.evidence] == [
        (RULE_REQUIRED, "Chase", WHERE_TITLE),
    ]


# ---------------------------------------------- decision 137: the security review ----


def test_a_long_text_file_is_read_to_the_cap_and_says_so(tmp_path, monkeypatch):
    """Decision 137 (M5): a ``.csv``/``.tsv``/``.txt`` is read up to its first
    ``TEXT_READ_CAP_MB`` and no further, and a verdict reached on the cut
    text says the rest was never read."""
    import tracker.content_check as content_check

    monkeypatch.setattr(content_check, "TEXT_READ_CAP_MB", 1)
    cap = 1024 * 1024
    early = tmp_path / "early.csv"
    early.write_bytes(b"Form 1099-B proceeds\n" + b"x," * cap)
    late = tmp_path / "late.csv"
    late.write_bytes(b"x," * cap + b"\nForm 1099-B proceeds\n")

    reading = content_check.extract(early)
    assert reading.cut and len(reading.text) == cap
    rules = item(required_keywords=("1099-B",))
    assert check_content(early, rules).ok                    # found in the part that was read

    verdict = check_content(late, rules)
    assert not verdict.ok
    assert reasons.WRONG_DOCUMENT.matches(verdict.reason)
    assert verdict.reason.endswith(reasons.TEXT_CUT.format(limit=1))

    whole = tmp_path / "short.txt"
    whole.write_text("Form 1099-B proceeds", encoding="utf-8")
    assert not content_check.extract(whole).cut


def test_a_giant_pdf_page_is_rendered_within_the_pixel_budget(tmp_path, monkeypatch):
    """Decision 137 (B1, the ruling's first half): each page is rendered at
    ``min(2, sqrt(budget / page area))``. A maximum-size PDF page (14,400
    points square) at the old fixed scale of 2 is some 830 million pixels,
    handed to Pillow past its own guard. An ordinary page keeps scale 2."""
    import tracker.content_check as content_check

    pypdfium2 = pytest.importorskip("pypdfium2")
    pytest.importorskip("pytesseract")      # _ocr_pdf reaches the render only with both

    def pdf(path, width, height):
        writer = PdfWriter()
        writer.add_blank_page(width=width, height=height)
        with path.open("wb") as handle:
            writer.write(handle)
        return path

    asked: list[tuple[float, float]] = []

    class Stop(Exception):
        pass

    def render(page, *, scale=1.0, **_kwargs):
        width, height = page.get_size()
        asked.append((width * scale, height * scale))
        raise Stop("rendering stops here: the scale is what is under test")

    monkeypatch.setattr(pypdfium2.PdfPage, "render", render)

    for path in (pdf(tmp_path / "giant.pdf", 14400, 14400), pdf(tmp_path / "letter.pdf", 612, 792)):
        with pytest.raises(content_check.OcrError):
            content_check._ocr_pdf(path)
    (giant_w, giant_h), (letter_w, letter_h) = asked
    assert giant_w * giant_h <= content_check.PIXEL_BUDGET * 1.0001
    assert giant_w * giant_h > content_check.PIXEL_BUDGET * 0.99       # read smaller, not refused
    assert (letter_w, letter_h) == (612 * 2.0, 792 * 2.0)              # an ordinary page as before


def test_a_photo_past_the_pixel_budget_is_read_smaller(tmp_path, monkeypatch):
    """Decision 137 (B1): a photo is checked against the same budget before
    it is decoded, and read reduced to it rather than refused."""
    from PIL import Image

    import tracker.content_check as content_check

    pytesseract = pytest.importorskip("pytesseract")
    monkeypatch.setattr(content_check, "PIXEL_BUDGET", 10_000)
    seen = []
    monkeypatch.setattr(content_check, "_upright", lambda image: image)
    monkeypatch.setattr(pytesseract, "image_to_string",
                        lambda image, *a, **k: seen.append(image.size) or "words")
    for name in ("photo.png", "photo.jpg"):
        Image.new("RGB", (400, 300), "white").save(tmp_path / name)
        assert content_check._ocr_image(tmp_path / name) == "words"
    for width, height in seen:
        assert width * height <= 10_000


def test_a_date_pattern_runs_line_by_line_and_skips_lines_over_the_limit():
    """Decision 137 (L3): a staff Date Pattern is compiled and run one line
    at a time, and a line longer than ``DATE_LINE_MAX`` is skipped, so a
    typo that backtracks is bounded by one short line rather than the whole
    OCR text. Where it matched is still found in the whole text."""
    import tracker.content_check as content_check

    rules = item(period="TY2025", date_pattern=r"2025")
    text = "Statement\n" + "2025 " * 200 + "\nPeriod ending 12/31/2025\n"
    verdict = evaluate_rules(text, rules)
    assert verdict.ok
    assert content_check.date_pattern_at(r"2025", text) == text.index("12/31/2025") + 6

    only_long = "x" + "2025 " * 200
    assert content_check.date_pattern_at(r"2025", only_long) is None
    assert not evaluate_rules(only_long, rules).ok
    assert content_check.date_pattern_at(r"(unclosed", "anything") is None
    # A catastrophic pattern over a long run of what it backtracks on
    # finishes at once: the line holding the run is past the limit.
    evil = "a" * 5000 + "!"
    assert content_check.date_pattern_at(r"(a+)+b", evil) is None


def test_ocr_temporary_images_go_to_a_private_folder_each_pass_empties(tmp_path):
    """Decision 137 (L7): during a pass the process's temporary files go to
    a folder beside the settings file, emptied at the start of each pass,
    so a pass killed mid-page leaves a client's page there and not in
    ``%TEMP%``; outside the pass nothing is moved."""
    import os
    import tempfile

    import tracker.content_check as content_check

    before = tempfile.gettempdir()
    before_env = os.environ.get("TMPDIR")
    scratch = tmp_path / "app" / content_check.OCR_SCRATCH_DIR_NAME
    scratch.mkdir(parents=True)
    (scratch / "tess_left_by_a_killed_pass.png").write_bytes(b"a client's page")
    (scratch / "tess_folder").mkdir()

    with content_check.ocr_scratch(scratch) as folder:
        assert folder == scratch and list(scratch.iterdir()) == []       # emptied first
        assert tempfile.gettempdir() == str(scratch)
        with tempfile.NamedTemporaryFile(prefix="tess_", delete=False) as handle:
            written = handle.name
        assert os.path.dirname(written) == str(scratch)

    assert tempfile.gettempdir() == before and os.environ.get("TMPDIR") == before_env
    with content_check.ocr_scratch(scratch):
        assert list(scratch.iterdir()) == []                              # the next pass empties it


def test_a_picture_past_pillows_guard_is_a_kept_too_large_verdict_not_a_retry(tmp_path, monkeypatch):
    """Decision 137 (B1, the owner's ruling on phase 1): a picture Pillow
    refuses as a decompression bomb is a size rule, like the file-size
    ceiling - "Too large to read ... A person looks at it." - kept as the
    verdict, parked for a person, and not read again until the file changes.
    Pillow's guard itself stays on."""
    from PIL import Image

    import tracker.content_check as content_check
    from tracker.content_check import ContentCache
    from tracker.router import route_file
    from tracker.validators import check_file

    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1_000)          # 2,000 px is a bomb now
    photo = tmp_path / "photo.png"
    Image.new("L", (100, 100), "white").save(photo)
    rules = item(allowed_extensions=("pdf",), any_keywords=("w-2",), min_size_kb=0)

    assert reasons.TOO_LARGE.matches(check_file(photo, rules).reason)   # tier 2: ours, not the client's
    reading = content_check.extract(photo)
    assert reading.text is None and not reading.transient
    assert reading.reason == "Too large to read (0 megapixels). A person looks at it."
    routed = route_file(photo, [rules])
    assert routed.identifier is None and reasons.TOO_LARGE.matches(routed.reason)

    cache = ContentCache()
    first = check_content(photo, rules, cache)
    assert not first.ok and reasons.TOO_LARGE.matches(first.reason)

    def never(_path):
        raise AssertionError("a kept verdict was read again")

    monkeypatch.setattr(content_check, "_ocr_image", never)
    assert check_content(photo, rules, cache) == first                 # not retried
    Image.new("L", (100, 101), "white").save(photo)                     # the file changed
    with pytest.raises(AssertionError, match="read again"):
        check_content(photo, rules, cache)


def test_a_reading_past_the_safety_stop_is_abandoned_cached_and_not_retried(tmp_path, monkeypatch):
    """Decision 137 (B1.2; the owner's Q-1 of 2026-09-24): a reading gets a
    minute a page (a photo is one page) and ten minutes a document,
    rendering included. Every Tesseract call is given what is left of that
    as its timeout; a reading that reaches the stop is abandoned - "The
    reader stopped after N minutes on this file. A person reads it." - kept
    as the verdict, parked for a person, and not read again until the file
    changes. A slow reading under the stop is finished as before. The
    clock is moved, not waited for."""
    from PIL import Image
    from pypdf import PdfWriter

    import tracker.content_check as content_check
    from tracker.content_check import ContentCache
    from tracker.router import route_file

    pytesseract = pytest.importorskip("pytesseract")
    pytest.importorskip("pypdfium2")
    now = [1000.0]
    monkeypatch.setattr(content_check, "_clock", lambda: now[0])
    monkeypatch.setattr(content_check, "_upright", lambda image: image)
    assert (content_check.READING_STOP_PAGE_SECONDS,
            content_check.READING_STOP_DOCUMENT_SECONDS) == (60.0, 600.0)
    photo = tmp_path / "photo.png"
    Image.new("L", (40, 40), "white").save(photo)
    rules = item(allowed_extensions=("pdf",), any_keywords=("w-2",), min_size_kb=0)

    # Slow but under the stop: finished and read, as decision 127 says.
    given = []

    def slow(image, *, timeout=0, **kwargs):
        given.append(timeout)
        now[0] += 59.0
        return "Form W-2"

    monkeypatch.setattr(pytesseract, "image_to_string", slow)
    assert content_check.extract(photo).text == "Form W-2"
    assert given == [60.0]                                   # a photo: one page's minute

    # Past it: Tesseract is killed at its timeout, and the reading is abandoned.
    def killed(image, *, timeout=0, **kwargs):
        given.append(timeout)
        now[0] += timeout
        raise RuntimeError("Tesseract process timeout")

    monkeypatch.setattr(pytesseract, "image_to_string", killed)
    stopped = content_check.extract(photo)
    said = "The reader stopped after 1 minute on this file. A person reads it."
    assert stopped.text is None and stopped.reason == said and not stopped.transient
    routed = route_file(photo, [rules])
    assert routed.identifier is None and routed.reason == said

    cache = ContentCache()
    verdict = check_content(photo, rules, cache)
    assert not verdict.ok and reasons.READING_STOPPED.matches(verdict.reason)
    monkeypatch.setattr(pytesseract, "image_to_string",
                        lambda *a, **k: pytest.fail("a kept verdict was read again"))
    assert check_content(photo, rules, cache) == verdict      # not retried
    Image.new("L", (40, 41), "white").save(photo)             # the file changed
    monkeypatch.setattr(pytesseract, "image_to_string", killed)
    before = len(given)
    assert reasons.READING_STOPPED.matches(check_content(photo, rules, cache).reason)
    assert len(given) == before + 1                           # read again, stopped again

    # A document: the render counts against the budget. Two pages render
    # in half a minute each; the third's render alone runs past its minute,
    # and the stop comes before Tesseract is asked about it.
    writer = PdfWriter()
    for _ in range(10):
        writer.add_blank_page(width=612, height=792)
    scan = tmp_path / "scan.pdf"
    with scan.open("wb") as handle:
        writer.write(handle)
    import pypdfium2

    real_render = pypdfium2.PdfPage.render
    renders = iter([30.0, 30.0, 61.0])

    def slow_render(page, **kwargs):
        now[0] += next(renders)
        return real_render(page, scale=0.1)

    asked = []
    monkeypatch.setattr(pypdfium2.PdfPage, "render", slow_render)
    monkeypatch.setattr(pytesseract, "image_to_string",
                        lambda image, *, timeout=0, **k: asked.append(timeout) or "page")
    stopped = content_check.extract_by_ocr(scan)
    assert stopped.reason == "The reader stopped after 2 minutes on this file. A person reads it."
    assert asked == [30.0, 30.0]                              # page 3 never reached Tesseract
    # Each page's timeout is what is left of its own minute, never more
    # than what is left of the document's ten.
    stop = content_check._SafetyStop()
    now[0] = stop.started + 590.0
    stop.page()
    assert stop.remaining() == 10.0
    assert content_check._STOP is None                       # nothing outlives the reading


def test_only_a_staff_date_pattern_runs_line_by_line():
    """Decision 137's review (F7): the line-by-line bound is for a pattern a
    person typed. The one the tracker derives from the Period is its own and
    runs over the whole text as it always did, so a month and its year split
    by a line break still say the year."""
    import re

    from tracker.manifest import derived_date_pattern

    derived = derived_date_pattern("TY2025")
    split = "Statement period\nDecember\n2025 and more\n"
    assert derived and re.search(derived, split) is not None       # the premise
    firm = item(period="TY2025", date_pattern=derived, date_pattern_derived=True)
    assert evaluate_rules(split, firm).ok

    typed = item(period="TY2025", date_pattern=r"December\s2025", date_pattern_derived=False)
    assert not evaluate_rules(split, typed).ok                      # a person's: line by line
    assert evaluate_rules("December 2025\n", typed).ok


def test_orientation_is_scored_on_a_small_copy_and_only_the_chosen_turn_is_full_size(monkeypatch):
    """Decision 137's review of Part B (#2): which way up a page is does not
    need its full resolution. The four turns are scored on a copy whose
    long side is at most ``SCORING_LONG_SIDE``; only the chosen turn of the
    full page is handed back, to be read once."""
    from PIL import Image

    import tracker.content_check as content_check

    pytesseract = pytest.importorskip("pytesseract")

    def osd_cannot_say(image, **kw):
        raise pytesseract.TesseractError(1, "Too few characters. Skipping this page")

    scored = []
    scores = iter([10.0, 90.0, 20.0, 30.0])                    # the quarter turn reads best

    def by_turn(image, **kw):
        scored.append(image.size)
        confidence = next(scores)
        return {"text": ["Wage", "and", "Statement"], "conf": [confidence] * 3}

    monkeypatch.setattr(pytesseract, "image_to_osd", osd_cannot_say)
    monkeypatch.setattr(pytesseract, "image_to_data", by_turn)
    page = Image.new("L", (4032, 3024), 255)                     # a 12-megapixel photo
    turned = content_check._upright(page)

    assert len(scored) == 4
    assert all(max(size) <= content_check.SCORING_LONG_SIDE for size in scored)
    assert turned.size == (3024, 4032)                           # the full page, turned


# ------------------------------------ a reading the pass can stop (150) ----
#
# Decision 150. The pass reads each document in a child process and waits
# for it at most the document's stop; the claims below run a real child.
# The suite reads in its own process everywhere else (tests/conftest.py),
# so each of these turns the child back on. The stops are patched down to
# seconds - never minutes - and the child is handed a stand-in reader from
# tests/child_readers.py, because a patch made here never reaches it.

#: The stop these claims patch in, in seconds. A child starts in about half
#: a second on the office machine; this leaves a slow build runner room to
#: reach the stage it is claimed to be stopped in.
STOP_IN_TESTS = 5.0
#: What a reading stopped at a stop under a minute says.
STOPPED = "The reader stopped after 1 minute on this file. A person reads it."
CRASHED = "The reader could not read this file (it stopped unexpectedly). A person reads it."


@pytest.fixture
def in_a_child(monkeypatch):
    """The reading in a child process, as the pass makes it, at the real stops."""
    import tracker.content_check as content_check

    monkeypatch.setattr(content_check, "READ_IN_A_CHILD", True)
    return monkeypatch


@pytest.fixture
def a_short_stop(in_a_child):
    """The child, stopped at :data:`STOP_IN_TESTS` for a file and a photo alike.
    Only the pass's own wait is shortened: the child's own stop (decision 137,
    B1.2) is still ten minutes, so what ends the reading is the child being
    ended."""
    import tracker.content_check as content_check

    in_a_child.setattr(content_check, "READING_STOP_DOCUMENT_SECONDS", STOP_IN_TESTS)
    in_a_child.setattr(content_check, "READING_STOP_PAGE_SECONDS", STOP_IN_TESTS)
    return in_a_child


def no_child_left():
    """No reading's child of this process is still running."""
    import multiprocessing

    return multiprocessing.active_children() == []


def running(pid: int) -> bool:
    """Whether the process ``pid`` is still running, asked of the system."""
    import os
    import sys
    from pathlib import Path

    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        handle = kernel32.OpenProcess(0x1000, False, pid)     # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == 259                          # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    stat = Path(f"/proc/{pid}/stat")
    try:
        return stat.read_text().rsplit(")", 1)[1].split()[0] != "Z"   # a zombie has ended
    except (OSError, IndexError):
        return True


def eventually(check, within: float = 15.0) -> bool:
    import time

    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.1)
    return check()


def test_a_text_layer_that_never_finishes_is_stopped_and_abandoned(tmp_path, a_short_stop):
    """The PDF text layer runs before any OCR, where decision 137's stop
    never reached: a few megabytes of drawing commands kept pdfplumber busy
    for hours. The reading is now ended at the document's stop, and it is
    the abandoned reading - the same sentence, kept by the cache and not
    read again until the file changes."""
    import time

    import tracker.content_check as content_check
    from tests import child_readers

    a_short_stop.setattr(content_check, "_CHILD_READER", child_readers.a_text_layer_that_never_finishes)
    pdf = text_pdf(tmp_path / "drawing.pdf", "Form W-2 Wage and Tax Statement 2025")
    rules = item(required_keywords=("W-2",))
    cache = ContentCache()

    started = time.monotonic()
    verdict = check_content(pdf, rules, cache)
    took = time.monotonic() - started

    assert child_readers.reached(pdf, "text-layer").is_file()      # stopped inside the text layer
    assert STOP_IN_TESTS <= took < STOP_IN_TESTS + 45
    assert verdict == content_check.ContentResult(ok=False, reason=STOPPED, extractable=False)
    assert no_child_left()
    a_short_stop.setattr(content_check, "_read_in_a_child",
                         lambda *a, **k: pytest.fail("a kept verdict was read again"))
    assert check_content(pdf, rules, cache) == verdict              # kept, not retried


def test_a_render_that_never_finishes_is_stopped_and_abandoned(tmp_path, a_short_stop):
    """One page's render ran inside the reading, and decision 137's stop
    only noticed an overrun once it returned. Ended at the stop now: the
    router parks the file on the abandoned reading's sentence, and the
    scanner keeps that verdict."""
    import tracker.content_check as content_check
    from tests import child_readers
    from tracker.router import route_file

    pytest.importorskip("pytesseract")
    pytest.importorskip("pypdfium2")
    a_short_stop.setattr(content_check, "_CHILD_READER", child_readers.a_render_that_never_finishes)
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)                    # a scan: no text layer
    scan = tmp_path / "scan.pdf"
    with scan.open("wb") as handle:
        writer.write(handle)
    rules = item(allowed_extensions=("pdf",), required_keywords=("W-2",), min_size_kb=0)

    routed = route_file(scan, [rules])
    assert child_readers.reached(scan, "render").is_file()          # stopped inside the render
    assert routed.identifier is None and routed.reason == STOPPED
    assert no_child_left()

    cache = ContentCache()
    verdict = check_content(scan, rules, cache)
    assert verdict == content_check.ContentResult(ok=False, reason=STOPPED, extractable=False)
    a_short_stop.setattr(content_check, "_read_in_a_child",
                         lambda *a, **k: pytest.fail("a kept verdict was read again"))
    assert check_content(scan, rules, cache) == verdict
    assert no_child_left()


def test_a_reader_that_crashes_is_a_failed_reading_not_a_dead_pass(tmp_path, in_a_child):
    """A crash in pdfium or Tesseract used to end the pass's own process,
    and every return after the file went unsorted. The child ends instead:
    the file is a reading that failed - parked with its own sentence, not
    the abandoned one - and the pass goes on to the next document."""
    import tracker.content_check as content_check
    from tests import child_readers
    from tests.conftest import named_page, sort
    from tests.test_scanner import text_pdf as page_pdf
    from tracker.layout import inbox_of

    in_a_child.setattr(content_check, "_CHILD_READER", child_readers.a_reader_that_dies_on_a_crash)
    w2 = RequestItem(identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
                     min_size_kb=0, required_keywords=("W-2",))
    engagement = make_engagement(tmp_path, [w2])
    page_pdf(inbox_of(engagement) / "a crash.pdf", named_page("Form W-2 Wage and Tax Statement 2025"))
    page_pdf(inbox_of(engagement) / "the next one.pdf",
             named_page("Form W-2 Wage and Tax Statement 2025 Employer copy"))

    report = sort(engagement, today=dt.date(2026, 7, 1))

    [parked] = report.review
    assert parked.original_name == "a crash.pdf" and parked.reason == CRASHED
    assert reasons.find(parked.reason) is reasons.READING_CRASHED and reasons.READING_CRASHED.firm_side
    [filed] = report.filed
    assert filed.original_name == "the next one.pdf" and filed.identifier == "A01"
    assert no_child_left()


def test_a_reading_on_time_returns_what_it_returned_in_process(tmp_path, in_a_child):
    """On time, the child hands back exactly the reading the pass's own
    process makes - text, OCR or not, every reason, and tier 2's open test
    beside it (the review's ruling) - for the synthetic
    pile: the samples every client sends (text PDFs, a workbook, a CSV, a
    Word file, a Google shortcut, a bitmap), IRS forms, and a photo and a
    scan read by OCR where this machine has it. Only the seconds differ."""
    from dataclasses import replace
    from pathlib import Path

    from PIL import Image

    import tracker.content_check as content_check
    from tests.samples import build_samples

    pile = tmp_path / "pile"
    pile.mkdir()
    build_samples(pile)
    (pile / "statement.csv").write_text("Date,Amount\n2025-12-31,100\n", encoding="utf-8")
    picture = photo(pile / "w-2.png")
    Image.open(picture).convert("RGB").save(pile / "scanned w-2.pdf")
    irs = Path(__file__).resolve().parent / "irs"
    documents = sorted(pile.iterdir()) + [irs / name for name in ("fw2.pdf", "f1099div.pdf", "f1098.pdf")]

    assert len(documents) >= 12
    for document in documents:
        in_process = content_check.open_and_read(document)
        in_child = content_check.extract_bounded(document)
        assert in_child.opened is not None, document.name
        assert replace(in_child, seconds=0.0) == replace(in_process, seconds=0.0), document.name
    assert no_child_left()


def test_a_cached_verdict_starts_no_child(tmp_path, in_a_child):
    """A child is started on a cache miss only. A pass reads a drop once to
    route it, and the scan that follows finds the router's kept verdict for
    the working copy; a second pass starts nothing at all."""
    from pathlib import Path

    import tracker.content_check as content_check
    from tests.conftest import named_page
    from tests.test_scanner import text_pdf as page_pdf
    from tracker.layout import inbox_of
    from tracker.registry import discover_engagements
    from tracker.runner import REMINDERS_NEVER, run_registry

    started = []
    real = content_check._read_in_a_child

    def counted(path, *, ocr):
        started.append(Path(path).name)
        return real(path, ocr=ocr)

    in_a_child.setattr(content_check, "_read_in_a_child", counted)
    w2 = RequestItem(identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
                     min_size_kb=0, required_keywords=("W-2",))
    engagement = make_engagement(tmp_path, [w2])
    page_pdf(inbox_of(engagement) / "w2.pdf", named_page("Form W-2 Wage and Tax Statement 2025"))

    first = run_registry(discover_engagements(tmp_path), today=dt.date(2026, 7, 1),
                         reminders=REMINDERS_NEVER)
    assert [run.filed for run in first.runs] == [1]
    assert started == ["w2.pdf"]                       # routed once; the scan found the verdict
    run_registry(discover_engagements(tmp_path), today=dt.date(2026, 7, 2), reminders=REMINDERS_NEVER)
    assert started == ["w2.pdf"]                       # a second pass starts nothing

    loose = page_pdf(tmp_path / "loose.pdf", "Form W-2 2025")
    rules = item(required_keywords=("W-2",))
    cache = ContentCache()
    assert check_content(loose, rules, cache).ok
    assert check_content(loose, rules, cache).ok
    assert started == ["w2.pdf", "loose.pdf"]          # one child for the miss, none for the hit
    assert no_child_left()


def test_no_child_is_left_running_after_a_stop(tmp_path, a_short_stop):
    """Ending the reading ends everything it started. OCR runs Tesseract as
    the child's own child, and ending only the child would leave Tesseract
    reading a client's page with nobody waiting for it - so the whole tree
    goes, on Windows as elsewhere."""
    import tracker.content_check as content_check
    from tests import child_readers

    a_short_stop.setattr(content_check, "_CHILD_READER",
                         child_readers.a_reader_that_starts_a_reader_of_its_own)
    pdf = text_pdf(tmp_path / "page.pdf", "Form W-2 2025")

    reading = content_check.extract_bounded(pdf)

    assert reading.text is None and reading.reason == STOPPED and not reading.transient
    helper = child_readers.reached(pdf, "helper")
    assert helper.is_file()                                          # it had started its own
    pid = int(helper.read_text(encoding="utf-8"))
    assert eventually(lambda: not running(pid)), f"process {pid} outlived the stop"
    assert no_child_left()


def test_the_readers_child_puts_its_temporary_files_where_the_pass_said(tmp_path, in_a_child):
    """OCR's temporary page images go to the pass's own scratch folder
    (decision 137, L7). The child is started inside the pass, so it takes
    that folder with the rest of the environment."""
    from pathlib import Path

    import tracker.content_check as content_check
    from tests import child_readers

    in_a_child.setattr(content_check, "_CHILD_READER", child_readers.where_temporary_files_go)
    page = text_pdf(tmp_path / "page.pdf", "Form W-2 2025")
    with content_check.ocr_scratch(tmp_path / "scratch") as scratch:
        reading = content_check.extract_bounded(page)
    assert reading.text is not None
    assert Path(reading.text).resolve() == scratch.resolve()


#: A pass, as a process of its own, that reads one document in a child
#: with a stand-in reader that starts a helper (Tesseract's stand-in) and
#: never finishes. ``lifeline`` as the second argument takes the job object
#: away, so the lifeline alone is what is proved.
A_PASS_READING = """
import sys
from pathlib import Path
sys.path[:0] = [sys.argv[3]]
from tests import child_readers
from tracker import content_check
content_check._CHILD_READER = child_readers.a_reader_that_starts_a_reader_of_its_own
if sys.argv[2] == "lifeline":
    content_check._kill_on_close_job = lambda pid: None
content_check.extract_bounded(Path(sys.argv[1]))
"""


@pytest.mark.parametrize("protection", ["job and lifeline", "lifeline"])
def test_a_reading_child_dies_with_its_pass(tmp_path, protection):
    """The designer's ruling on the build: the reading's child never
    outlives its pass. Task Scheduler's stop kills the pass outright - no
    code of the pass's runs - and the child must go with it, within a few
    seconds, not whenever its own reading ends. Here the pass is a real
    process, killed the way the scheduler kills it, mid-read.

    Two things do it. The lifeline: the child ends itself when the pass's
    end of a pipe closes, which the pass's death closes. And on Windows a
    job object that kills everything in it - the child and what it started
    - when the pass's handle on it closes. Each is proved: all of it, and
    the lifeline alone."""
    import subprocess
    import sys
    import time
    from pathlib import Path

    from tests import child_readers

    if protection == "job and lifeline" and sys.platform != "win32":
        pytest.skip("the job object is Windows'")
    repo = str(Path(__file__).resolve().parents[1])
    pdf = text_pdf(tmp_path / "page.pdf", "Form W-2 2025")
    the_pass = subprocess.Popen([sys.executable, "-c", A_PASS_READING, str(pdf),
                                 "lifeline" if protection == "lifeline" else "all", repo])
    waiting, helper = child_readers.reached(pdf, "waiting"), child_readers.reached(pdf, "helper")
    try:
        assert eventually(waiting.is_file, within=60), "the child never started reading"
        child = int(waiting.read_text(encoding="utf-8"))
        started = int(helper.read_text(encoding="utf-8"))
        assert running(child) and running(started)                 # mid-read

        the_pass.kill()                                            # the scheduler's stop: no code runs
        the_pass.wait(30)
        killed = time.monotonic()

        assert eventually(lambda: not running(child), within=10), "the child outlived its pass"
        assert time.monotonic() - killed < 10
        if protection == "job and lifeline":
            assert eventually(lambda: not running(started), within=10), "what it started outlived it"
    finally:
        if the_pass.poll() is None:
            the_pass.kill()
        for mark in (waiting, helper):
            if mark.is_file():
                _stop_if_running(int(mark.read_text(encoding="utf-8")))


def _stop_if_running(pid: int) -> None:
    """Leave nothing behind, whatever the test found (the lifeline alone
    ends the child, and on Windows not what it started)."""
    import os
    import signal
    import subprocess
    import sys

    if not running(pid):
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, check=False)
    else:
        os.kill(pid, signal.SIGKILL)


def page_tree_bomb(path, depth: int = 40):
    """A PDF whose page tree is ``depth`` levels deep, each level naming its
    one child twice: a few kilobytes that claim 2**depth pages, and a page
    count that walks every one of them (the review of decision 150, its
    generator's logic; every byte is made here). Padded with a comment line
    so no row's minimum size refuses it before it is opened."""
    objects = {1: b"<< /Type /Catalog /Pages 2 0 R >>"}
    for level in range(depth):
        number = 2 + level
        objects[number] = b"<< /Type /Pages /Kids [%d 0 R %d 0 R] /Count %d >>" % (
            number + 1, number + 1, 2 ** (depth - level))
    leaf = depth + 2
    objects[leaf] = b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] >>" % (depth + 1)
    out = bytearray(b"%PDF-1.4\n%" + b"x" * 200_000 + b"\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += b"%d 0 obj\n" % number + objects[number] + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (leaf + 1)
    out += b"".join(b"%010d 00000 n \n" % offsets[number] for number in range(1, leaf + 1))
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (leaf + 1, xref)
    path.write_bytes(bytes(out))
    return path


def test_a_page_tree_bomb_cannot_stall_the_pass(tmp_path, a_short_stop):
    """The review of decision 150's blocker: tier 2's open test - pypdf
    counting a PDF's pages - ran in the pass's own process, and a page
    tree of a few kilobytes counts to a trillion. The open test now runs in
    the reading's child, beside the reading: the pass finishes, the bomb
    parks with the stop's sentence, the next document files, and the
    scanner's open test is the same kept verdict, starting no child."""
    import time
    from pathlib import Path

    import tracker.content_check as content_check
    from tests.conftest import named_page
    from tests.test_scanner import text_pdf as page_pdf
    from tracker.filer import read_index
    from tracker.layout import inbox_of
    from tracker.registry import discover_engagements
    from tracker.runner import REMINDERS_NEVER, run_registry

    w2 = RequestItem(identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
                     min_size_kb=0, required_keywords=("W-2",))
    engagement = make_engagement(tmp_path, [w2])
    page_tree_bomb(inbox_of(engagement) / "bomb.pdf")
    page_pdf(inbox_of(engagement) / "w2.pdf", named_page("Form W-2 Wage and Tax Statement 2025"))

    started = time.monotonic()
    report = run_registry(discover_engagements(tmp_path), today=dt.date(2026, 7, 1),
                          reminders=REMINDERS_NEVER)
    took = time.monotonic() - started

    assert took < STOP_IN_TESTS + 90                     # the pass finished
    rows = {row.original_name: row for row in read_index(engagement)}
    assert rows["bomb.pdf"].reason == STOPPED            # parked, on the stop's sentence
    assert rows["w2.pdf"].identifier == "A01"            # and the next document filed
    assert [run.filed for run in report.runs] == [1]
    assert no_child_left()

    # The scanner's open test: the child's verdict, kept by the fingerprint.
    bomb = page_tree_bomb(tmp_path / "loose bomb.pdf")
    cache = ContentCache()
    assert content_check.open_verdict(bomb, cache) == STOPPED
    a_short_stop.setattr(content_check, "_read_in_a_child",
                         lambda *a, **k: pytest.fail("a kept open test was made again"))
    assert content_check.open_verdict(bomb, cache) == STOPPED
    from tracker.validators import check_file
    refused = check_file(bomb, w2, open_test=lambda path: content_check.open_verdict(Path(path), cache))
    assert not refused.ok and refused.reason == STOPPED
    assert no_child_left()


def _a_reader_only_the_pass_has(monkeypatch):
    """A reader the child can never import: its module is in the pass's
    process only, so the child ends while it is still being set up - the
    shape of a frozen build missing a module, or a machine that cannot
    start the reader - before it has said "started"."""
    import sys
    import types

    module = types.ModuleType("only_in_the_pass_150")

    def reader(path, *, ocr=True):          # never runs: the child cannot find it
        raise AssertionError("unreachable")

    reader.__module__ = module.__name__
    reader.__qualname__ = "reader"
    module.reader = reader
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return reader


def test_a_reader_that_cannot_start_keeps_no_verdict(tmp_path, in_a_child):
    """The review's second fix. A reader that cannot start is the machine's
    fault, not the file's: a death before the child says "started" - or a
    child that could not be created at all - keeps nothing against the
    file. Nothing is kept, a drop is neither decided nor recorded - it
    rests in the year's folder with no row, for the next pass - and the
    pass warns once, however many files it met. Only a death after
    "started" is kept (the crash claim above)."""
    import multiprocessing.context

    import tracker.content_check as content_check
    from tests.conftest import named_page
    from tests.test_scanner import text_pdf as page_pdf
    from tracker.filer import read_index
    from tracker.layout import inbox_of, originals_of
    from tracker.registry import discover_engagements
    from tracker.runner import REMINDERS_NEVER, append_log, format_report, run_registry
    from tracker.validators import sha256_of

    unavailable = ("The reader could not start on this machine, so this file was not read. "
                   "It is read again on the next pass.")
    in_a_child.setattr(content_check, "_CHILD_READER", _a_reader_only_the_pass_has(in_a_child))
    rules = item(required_keywords=("W-2",))
    page = text_pdf(tmp_path / "page.pdf", "Form W-2 2025")

    # Dies before "started": transient, and nothing is kept.
    reading = content_check.extract_bounded(page)
    assert reading.text is None and reading.transient and reading.reason == unavailable
    cache = ContentCache()
    verdict = check_content(page, rules, cache)
    assert verdict.transient and verdict.reason == unavailable
    assert cache.get(page, rules_fingerprint(rules)) is None
    assert content_check.open_verdict(page, cache) == unavailable
    assert cache.get(page, content_check.OPEN_TEST_FINGERPRINT) is None

    # Could not even be created: the same.
    def no_process(_process):
        raise OSError("no more processes")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(multiprocessing.context.SpawnProcess, "_Popen", staticmethod(no_process))
        assert content_check.extract_bounded(page).reason == unavailable
    content_check.readers_that_could_not_start()          # the claims above were not a pass

    # A pass: two documents wait for the next pass - no row, nothing kept
    # about either - and the pass says it once.
    w2 = RequestItem(identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
                     min_size_kb=0, required_keywords=("W-2",))
    engagement = make_engagement(tmp_path / "root", [w2])
    for name in ("one.pdf", "two.pdf"):              # two documents, not one sent twice
        page_pdf(inbox_of(engagement) / name, named_page(f"Form W-2 Wage and Tax Statement 2025 {name}"))
    report = run_registry(discover_engagements(tmp_path / "root"), today=dt.date(2026, 7, 1),
                          reminders=REMINDERS_NEVER)

    assert read_index(engagement) == []                  # not decided, not recorded
    assert sorted(path.name for path in originals_of(engagement).iterdir()) == ["one.pdf", "two.pdf"]
    assert [run.review for run in report.runs] == [0]
    assert reasons.READER_UNAVAILABLE.firm_side
    [warning] = report.warnings
    assert "could not start on this machine for 2 file(s)" in warning
    assert format_report(report).count(warning) == 1
    log = append_log(tmp_path / "runs.log", report)
    assert log.read_text(encoding="utf-8").count(warning) == 1
    _memos, verdicts = store.cached_verdicts(store.connect(), engagement, version=CACHE_VERSION)
    for original in originals_of(engagement).iterdir():
        assert sha256_of(original) not in verdicts, original.name      # nothing kept
    assert no_child_left()


def test_a_drop_the_reader_could_not_start_on_is_routed_next_pass(tmp_path, in_a_child):
    """The re-review's blocker. A machine fault must leave nothing
    permanent, and a routing decision is as permanent as a kept verdict: a
    Needs Review row made the original a non-stray for ever, so a good W-2
    waited for a person after the machine was fixed. Pass 1's reader cannot
    start: the W-2 is moved out of the inbox but decided and recorded
    nowhere. Pass 2's reader works: the W-2 is a stray in the year's folder,
    routed where it lies, and filed."""
    import tracker.content_check as content_check
    from tests.conftest import named_page
    from tests.test_scanner import text_pdf as page_pdf
    from tracker.filer import read_index
    from tracker.layout import inbox_of, originals_of
    from tracker.registry import discover_engagements
    from tracker.runner import REMINDERS_NEVER, run_registry

    root = tmp_path / "root"
    w2 = RequestItem(identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
                     min_size_kb=0, required_keywords=("W-2",))
    engagement = make_engagement(root, [w2])
    page_pdf(inbox_of(engagement) / "w2.pdf", named_page("Form W-2 Wage and Tax Statement 2025"))

    with pytest.MonkeyPatch.context() as broken:           # the machine is broken
        broken.setattr(content_check, "_CHILD_READER", _a_reader_only_the_pass_has(broken))
        first = run_registry(discover_engagements(root), today=dt.date(2026, 7, 1),
                             reminders=REMINDERS_NEVER)
    [warning] = first.warnings
    assert "could not start on this machine for 1 file(s)" in warning and "w2.pdf" in warning
    assert read_index(engagement) == []                    # no row: not decided, not recorded
    assert [path.name for path in originals_of(engagement).iterdir()] == ["w2.pdf"]

    second = run_registry(discover_engagements(root), today=dt.date(2026, 7, 2),
                          reminders=REMINDERS_NEVER)       # the machine is fixed
    assert second.warnings == []
    [row] = read_index(engagement)
    assert row.original_name == "w2.pdf" and row.identifier == "A01"
    assert [run.filed for run in second.runs] == [1]
    assert no_child_left()


def test_a_resent_file_the_reader_could_not_start_on_waits_for_the_next_pass(tmp_path, in_a_child):
    """The final review's note. The re-send road reads again too: a W-2
    already on record whose working copy was deleted by hand, sent again,
    goes through ``_sort_one`` - the digest is known - and must be read
    before it is filed again. Pass 1's reader cannot start: no new row,
    nothing re-filed, no working copy made, one warning; the re-send rests
    in the year's folder. Pass 2's reader works: it is filed again."""
    import tracker.content_check as content_check
    from tests.conftest import named_page
    from tests.test_scanner import text_pdf as page_pdf
    from tracker.filer import read_index
    from tracker.layout import inbox_of, originals_of
    from tracker.registry import discover_engagements
    from tracker.runner import REMINDERS_NEVER, run_registry

    root = tmp_path / "root"
    w2 = RequestItem(identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
                     min_size_kb=0, required_keywords=("W-2",))
    engagement = make_engagement(root, [w2])
    page = named_page("Form W-2 Wage and Tax Statement 2025")
    page_pdf(inbox_of(engagement) / "w2.pdf", page)
    run_registry(discover_engagements(root), today=dt.date(2026, 7, 1), reminders=REMINDERS_NEVER)
    [filed] = read_index(engagement)
    prepared = engagement / filed.prepared_location
    prepared.unlink()                                      # the working copy, deleted by hand

    page_pdf(inbox_of(engagement) / "w2 again.pdf", page)  # the same document, sent again
    with pytest.MonkeyPatch.context() as broken:           # the machine is broken
        broken.setattr(content_check, "_CHILD_READER", _a_reader_only_the_pass_has(broken))
        first = run_registry(discover_engagements(root), today=dt.date(2026, 7, 2),
                             reminders=REMINDERS_NEVER)
    [warning] = first.warnings
    assert "could not start on this machine for 1 file(s)" in warning and "w2 again.pdf" in warning
    assert read_index(engagement) == [filed]               # no new row: not decided, not recorded
    assert not prepared.exists()                           # nothing re-filed
    assert sorted(path.name for path in originals_of(engagement).iterdir()) == ["w2 again.pdf", "w2.pdf"]

    second = run_registry(discover_engagements(root), today=dt.date(2026, 7, 3),
                          reminders=REMINDERS_NEVER)       # the machine is fixed
    assert second.warnings == []
    first_row, again = read_index(engagement)
    assert first_row == filed
    assert again.original_name == "w2 again.pdf" and again.identifier == "A01"
    assert "re-filed: the earlier copy" in again.reason     # the re-send road, not a new arrival
    assert [run.filed for run in second.runs] == [1]
    assert no_child_left()


def test_a_photo_the_open_test_cannot_finish_is_stopped(tmp_path, in_a_child):
    """The re-review's note 6: the open test's photo branch - Pillow and
    pillow-heif opening the picture, native code - runs in the reading's
    child like the PDF branch. A photo whose open never finishes is ended
    at a photo's stop (patched to seconds; a file's stays ten minutes, so
    the photo's is the one that ended it): the router parks it on the
    stop's sentence, and the scanner's open test is the same kept verdict."""
    import time
    from pathlib import Path

    from PIL import Image

    import tracker.content_check as content_check
    from tests import child_readers
    from tracker.router import route_file
    from tracker.validators import check_file

    in_a_child.setattr(content_check, "READING_STOP_PAGE_SECONDS", STOP_IN_TESTS)
    in_a_child.setattr(content_check, "_CHILD_READER", child_readers.a_photo_open_that_never_finishes)
    photo = tmp_path / "w2 photo.jpg"
    Image.new("RGB", (200, 100), "white").save(photo)
    rules = item(allowed_extensions=("pdf",), required_keywords=("W-2",), min_size_kb=0)

    started = time.monotonic()
    routed = route_file(photo, [rules])
    took = time.monotonic() - started

    assert child_readers.reached(photo, "photo-open").is_file()   # stopped inside the photo open
    assert STOP_IN_TESTS <= took < STOP_IN_TESTS + 45
    assert routed.identifier is None and routed.reason == STOPPED
    assert no_child_left()

    cache = ContentCache()
    assert content_check.open_verdict(photo, cache) == STOPPED
    in_a_child.setattr(content_check, "_read_in_a_child",
                       lambda *a, **k: pytest.fail("a kept open test was made again"))
    refused = check_file(photo, rules, open_test=lambda path: content_check.open_verdict(Path(path), cache))
    assert not refused.ok and refused.reason == STOPPED
    assert no_child_left()
