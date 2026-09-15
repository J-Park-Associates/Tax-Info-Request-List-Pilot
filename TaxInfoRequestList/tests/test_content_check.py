"""Tests for tracker/content_check.py — tier-3 rules, all local files."""

import datetime as dt

import pytest
from openpyxl import Workbook
from pypdf import PdfWriter

from tracker.manifest import RequestItem
from tracker.content_check import (
    ContentCache,
    ContentResult,
    check_content,
    evaluate_rules,
    extract_text,
    has_content_rules,
    rules_fingerprint,
)


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
    assert "'Wells Fargo'" in result.reason and "wrong document" in result.reason


def test_keywords_case_insensitive(tmp_path):
    pdf = text_pdf(tmp_path / "s.pdf", "CHASE BANK statement")
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
    assert not result.ok and "wrong period" in result.reason


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
    assert ".docx" in result.reason and "review manually" in result.reason


def test_image_only_pdf_without_ocr(tmp_path, monkeypatch):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)  # valid PDF, zero text
    scan = tmp_path / "scan.pdf"
    with scan.open("wb") as fh:
        writer.write(fh)
    monkeypatch.setattr("tracker.content_check._ocr_pdf", lambda p: None)

    result = check_content(scan, item(required_keywords=("Chase",)))
    assert not result.ok and not result.extractable
    assert "OCR is not installed" in result.reason


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


def test_cache_corrupt_resets_silently(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache_file.write_text("{broken", encoding="utf-8")
    cache = ContentCache(cache_file)              # no exception
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement page")
    assert check_content(pdf, item(required_keywords=("Chase",)), cache).ok
    cache.save()
    assert ContentCache(cache_file).get(pdf, rules_fingerprint(item(required_keywords=("Chase",))))


def test_cache_prune(tmp_path):
    pdf = text_pdf(tmp_path / "s.pdf", "Chase Bank Statement page")
    rule = item(required_keywords=("Chase",))
    cache = ContentCache(tmp_path / "cache.json")
    check_content(pdf, rule, cache)
    assert cache.get(pdf, rules_fingerprint(rule)) is not None

    cache.prune(existing=set())                   # file no longer in any folder
    assert cache.get(pdf, rules_fingerprint(rule)) is None
