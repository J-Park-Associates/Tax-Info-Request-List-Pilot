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
    # the "+" in one as words to look for and found neither. The version
    # is carried per row now (decision 107), and it still means all that.
    assert CACHE_VERSION == 9
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
