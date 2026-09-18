"""Tests for tracker/content_check.py — tier-3 rules, all local files."""

import datetime as dt

import pytest
from openpyxl import Workbook
from pypdf import PdfWriter

from tracker import reasons
from tracker.content_check import (
    ContentCache,
    check_content,
    evaluate_rules,
    extract_text,
    has_content_rules,
    rules_fingerprint,
)
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


def test_cache_hit_and_invalidation(tmp_path, monkeypatch):
    calls = counting_extractor(monkeypatch)
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement December 2025")
    rule = item(required_keywords=("Chase",))
    cache = ContentCache(tmp_path / "cache.json")

    assert check_content(pdf, rule, cache).ok
    assert check_content(pdf, rule, cache).ok
    assert calls["n"] == 1                       # second call served from cache

    cache.save()
    reopened = ContentCache(tmp_path / "cache.json")
    assert check_content(pdf, rule, reopened).ok
    assert calls["n"] == 1                       # survives a save/reload

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
    cache = ContentCache(tmp_path / "cache.json")
    assert check_content(pdf, rule, cache).ok
    copy = tmp_path / "A01 - Bank Statement.pdf"
    copy.write_bytes(pdf.read_bytes())
    assert check_content(copy, rule, cache).ok
    assert calls["n"] == 1
    assert cache.digest_of(copy) == cache.digest_of(pdf)


def test_a_cache_in_an_older_layout_is_reset(tmp_path):
    import json

    from tracker.content_check import CACHE_VERSION

    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps({"version": 1, "files": {"old": {"ok": True}}}), encoding="utf-8")
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement page")
    cache = ContentCache(cache_file)
    assert cache.get(pdf, rules_fingerprint(item(required_keywords=("Chase",)))) is None
    check_content(pdf, item(required_keywords=("Chase",)), cache)
    cache.save()
    assert json.loads(cache_file.read_text(encoding="utf-8"))["version"] == CACHE_VERSION


def test_cache_corrupt_resets_silently(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache_file.write_text("{broken", encoding="utf-8")
    cache = ContentCache(cache_file)              # no exception
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement page")
    assert check_content(pdf, item(required_keywords=("Chase",)), cache).ok
    cache.save()
    assert ContentCache(cache_file).get(pdf, rules_fingerprint(item(required_keywords=("Chase",))))


def test_a_cache_save_leaves_no_temp_file_and_survives_a_crash(tmp_path, monkeypatch):
    from tracker.manifest import TEMP_SUFFIX

    cache_file = tmp_path / "cache.json"
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement page")
    rule = item(required_keywords=("Chase",))
    cache = ContentCache(cache_file)
    check_content(pdf, rule, cache)
    cache.save()
    before = cache_file.read_text(encoding="utf-8")

    def refuse_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr("tracker.manifest.os.replace", refuse_replace)
    text_pdf(pdf, "Chase Bank Statement page v2")
    check_content(pdf, rule, cache)
    with pytest.raises(OSError, match="disk full"):
        cache.save()

    assert cache_file.read_text(encoding="utf-8") == before   # the old cache survived
    assert list(tmp_path.glob(f"*{TEMP_SUFFIX}")) == []


def test_cache_prune(tmp_path):
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement page")
    rule = item(required_keywords=("Chase",))
    cache = ContentCache(tmp_path / "cache.json")
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
    transmittal = "Enclosed please find: Form W-2 2025, Form 1098 2025, Form 1099-INT 2025"
    assert _title_forms(transmittal.lower()) == set()
    # Families, not numbers: a broker's consolidated 1099 names the family and
    # its parts and is one family's document, which the rows then contest.
    composite = ("vanguard brokerage services\n2025 consolidated form 1099 - account 8812-4455\n"
                 "form 1099-int   interest income\nform 1099-div   dividends and distributions\n"
                 "form 1099-b   proceeds from broker and barter exchange transactions")
    assert _title_forms(composite) == {"1099", "1099int", "1099div", "1099b"}
    assert says(composite, "1099-int") and says(composite, "1099-b")
    # A page footer names the form itself, whatever word the prose above ended on.
    assert _title_forms("be sure to\nform 1040-es (2026) estimated tax for individuals") == {"1040es"}


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
