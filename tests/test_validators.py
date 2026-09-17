"""Tests for tracker/validators.py — tier 1-2 checks, all local files."""

from pathlib import Path

import pytest
from pypdf import PdfWriter

from tracker import reasons
from tracker.manifest import RequestItem
from tracker.validators import (
    FileResult,
    check_file,
    check_folder,
    is_cloud_placeholder,
    is_ignored,
    iter_candidate_files,
    sha256_of,
)

PDF_ITEM = RequestItem(
    identifier="A01", document="Bank Statement",
    allowed_extensions=("pdf",), min_size_kb=0,
)
ANY_ITEM = RequestItem(identifier="A02", document="Anything", min_size_kb=0)
SIZED_ITEM = RequestItem(
    identifier="B01", document="Payroll", allowed_extensions=("xlsx",), min_size_kb=10,
)


def write_pdf(path: Path, pages: int = 1, password: str | None = None) -> Path:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if password:
        writer.encrypt(password, algorithm="RC4-128")
    with path.open("wb") as fh:
        writer.write(fh)
    return path


# ----------------------------------------------------------------- tier 1 ----


def test_junk_files_ignored(tmp_path):
    for junk in ("desktop.ini", "Thumbs.db", "~$statement.xlsx", "upload.tmp"):
        (tmp_path / junk).write_bytes(b"junk")
    (tmp_path / "real.pdf").write_bytes(b"data")
    (tmp_path / "extracted").mkdir()
    (tmp_path / "extracted" / "nested.csv").write_bytes(b"a,b")  # recursion

    names = [p.name for p in iter_candidate_files(tmp_path)]
    assert names == ["nested.csv", "real.pdf"]
    assert is_ignored(Path("~$december.xlsx"))
    assert not is_ignored(Path("statement.pdf"))


def test_google_drive_transfer_temps_ignored(tmp_path):
    # Google Drive for desktop stages in-flight transfers as hidden
    # ".tmp.drive*" entries — both loose files and staging directories.
    (tmp_path / "w2.pdf.tmp.driveupload").write_bytes(b"partial")
    staging = tmp_path / ".tmp.drivedownload"
    staging.mkdir()
    (staging / "chunk.bin").write_bytes(b"partial")
    (tmp_path / "real.pdf").write_bytes(b"data")

    names = [p.name for p in iter_candidate_files(tmp_path)]
    assert names == ["real.pdf"]


def test_google_native_stub_fails_with_guidance(tmp_path):
    # A .gsheet is a shortcut to a cloud document, not the document itself:
    # it must fail tier 2 with an actionable note, even with no whitelist.
    stub = tmp_path / "P&L 2025.gsheet"
    stub.write_text('{"url": "https://docs.google.com/..."}')
    result = check_file(stub, ANY_ITEM)
    assert result.ok is False
    assert result.pending_sync is False
    assert reasons.GOOGLE_STUB.matches(result.reason)
    assert reasons.GOOGLE_EXPORT_HINT in result.reason


def test_missing_and_empty_folders(tmp_path):
    missing = check_folder(tmp_path / "nope", ANY_ITEM)
    assert missing.exists is False and missing.files == []

    empty = tmp_path / "empty"
    empty.mkdir()
    result = check_folder(empty, ANY_ITEM)
    assert result.exists is True and result.files == []


def test_local_files_are_not_placeholders(tmp_path):
    f = tmp_path / "normal.pdf"
    f.write_bytes(b"data")
    assert is_cloud_placeholder(f) is False       # plain desktop file
    assert is_cloud_placeholder(tmp_path / "gone.pdf") is False  # no crash


# ----------------------------------------------------------------- tier 2 ----


def test_extension_whitelist(tmp_path):
    docx = tmp_path / "statement.docx"
    docx.write_bytes(b"x" * 100)
    result = check_file(docx, PDF_ITEM)
    assert not result.ok
    assert reasons.EXTENSION_NOT_ALLOWED.format(extension="docx", allowed="pdf") in result.reason

    upper = tmp_path / "STATEMENT.PDF"           # case-insensitive
    write_pdf(upper)
    assert check_file(upper, PDF_ITEM).ok


def test_no_whitelist_allows_anything(tmp_path):
    f = tmp_path / "whatever.xyz"
    f.write_bytes(b"x" * 100)
    assert check_file(f, ANY_ITEM).ok


def test_min_size(tmp_path):
    small = tmp_path / "tiny.xlsx"
    small.write_bytes(b"x" * 2048)               # 2 KB < 10 KB
    result = check_file(small, SIZED_ITEM)
    assert not result.ok and reasons.TOO_SMALL.format(size_kb=2048 / 1024, minimum=10) in result.reason

    exact = tmp_path / "exact.xlsx"
    exact.write_bytes(b"x" * 10 * 1024)          # boundary: exactly 10 KB passes
    assert check_file(exact, SIZED_ITEM).ok


def test_valid_pdf_passes(tmp_path):
    assert check_file(write_pdf(tmp_path / "ok.pdf"), PDF_ITEM).ok


def test_corrupt_pdf_fails(tmp_path):
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"this is not a pdf at all" * 10)
    result = check_file(fake, PDF_ITEM)
    assert not result.ok and reasons.UNREADABLE_PDF.matches(result.reason)


def test_password_protected_pdf_fails(tmp_path):
    locked = write_pdf(tmp_path / "locked.pdf", password="secret123")
    result = check_file(locked, PDF_ITEM)
    assert not result.ok and reasons.PASSWORD_PROTECTED.matches(result.reason)


def test_placeholder_skipped_not_read(tmp_path, monkeypatch):
    # A corrupt "pdf" that would fail tier 2 -- but as a cloud placeholder
    # it must be reported pending_sync WITHOUT being opened at all.
    ghost = tmp_path / "cloud.pdf"
    ghost.write_bytes(b"garbage that must never be parsed")
    monkeypatch.setattr(
        "tracker.validators.is_cloud_placeholder", lambda p: p.name == "cloud.pdf"
    )
    result = check_file(ghost, PDF_ITEM)
    assert result.pending_sync is True
    assert result.ok is False
    assert reasons.PENDING_SYNC.format() in result.reason


def test_check_folder_classification(tmp_path, monkeypatch):
    folder = tmp_path / "A01 - Bank"
    folder.mkdir()
    write_pdf(folder / "good.pdf")
    (folder / "bad.docx").write_bytes(b"x" * 100)
    (folder / "cloud.pdf").write_bytes(b"unsynced")
    (folder / "desktop.ini").write_bytes(b"junk")
    monkeypatch.setattr(
        "tracker.validators.is_cloud_placeholder", lambda p: p.name == "cloud.pdf"
    )

    result = check_folder(folder, PDF_ITEM)
    assert result.exists
    assert [f.path.name for f in result.valid] == ["good.pdf"]
    assert [f.path.name for f in result.failed] == ["bad.docx"]
    assert [f.path.name for f in result.pending] == ["cloud.pdf"]


def test_sha256_of(tmp_path):
    a = tmp_path / "statement.pdf"
    b = tmp_path / "statement (1).pdf"           # duplicate upload
    c = tmp_path / "different.pdf"
    a.write_bytes(b"identical bytes")
    b.write_bytes(b"identical bytes")
    c.write_bytes(b"other bytes")
    assert sha256_of(a) == sha256_of(b)
    assert sha256_of(a) != sha256_of(c)


def test_a_file_that_vanishes_mid_scan_is_pending_not_a_crash(tmp_path):
    # Listed a moment ago, replaced by the sync client now. The scheduled
    # scan must carry on, and the row should wait rather than fail.
    ghost = tmp_path / "ghost.pdf"
    result = check_file(ghost, PDF_ITEM)
    assert result.ok is False
    assert result.pending_sync is True
    assert reasons.VANISHED.matches(result.reason)


def test_pdf_readability_is_parsed_once_per_file(tmp_path, monkeypatch):
    # The router asks check_file() once per manifest row for one file; the
    # verdict is cached per (path, size, mtime) so the PDF is parsed once,
    # and a rewritten file gets a fresh parse.
    import tracker.validators as v

    calls = []
    real = v._pdf_error_uncached
    monkeypatch.setattr(v, "_pdf_error_uncached", lambda p: (calls.append(p), real(p))[1])
    pdf = write_pdf(tmp_path / "statement.pdf")
    for _ in range(5):
        assert check_file(pdf, PDF_ITEM).ok
    assert len(calls) == 1

    write_pdf(pdf, pages=2)
    import os
    os.utime(pdf, ns=(1, 1))  # a different mtime, whatever the clock did
    assert check_file(pdf, PDF_ITEM).ok
    assert len(calls) == 2
