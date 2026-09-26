"""Tests for tracker/validators.py — tier 1-2 checks, all local files."""

from pathlib import Path

import pytest
from pypdf import PdfWriter

from tracker import reasons
from tracker.manifest import RequestItem
from tracker.validators import (
    IMAGE_EXTENSIONS,
    check_file,
    check_files,
    extension_allowed,
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
    assert result.code == reasons.GOOGLE_STUB.code
    assert reasons.GOOGLE_EXPORT_HINT in result.reason


def test_a_request_with_no_files_checks_nothing(tmp_path):
    """Decision 168: a request's files are handed in (by their names,
    ``tracker.scaffold.assign_files``); a request with none has nothing to
    check - no folder of its own to be missing or empty."""
    assert check_files([], ANY_ITEM) == []


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
    assert not result.ok and result.code == reasons.UNREADABLE_PDF.code


def test_password_protected_pdf_fails(tmp_path):
    locked = write_pdf(tmp_path / "locked.pdf", password="secret123")
    result = check_file(locked, PDF_ITEM)
    assert not result.ok and result.code == reasons.PASSWORD_PROTECTED.code


# ------------------------------------------------- photos are documents ----
#
# Decision 127. Every image here is made by the test, out of a form's own
# words: no binary is committed, and no client's photo is anywhere near
# the suite.


def write_photo(path: Path, words: str = "Form W-2 Wage and Tax Statement") -> Path:
    """A small, readable photo of a document, made here and thrown away."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 200), "white")
    ImageDraw.Draw(image).text(
        (20, 60), words, font=ImageFont.load_default(size=40), fill="black",
    )
    image.save(path)
    return path


def test_an_image_is_accepted_by_every_request_that_accepts_a_pdf_and_by_none_that_does_not(tmp_path):
    """A photo is a scan of a document, so the row that takes the scan takes
    the photo - and no row has to be edited for it, which is the point: a
    request list recorded before this decision admits photos the day it
    lands. A row that wants a spreadsheet still refuses one, with the
    sentence it always refused it with."""
    photo = write_photo(tmp_path / "w-2.jpg")

    assert check_file(photo, PDF_ITEM).ok            # the row that names pdf
    assert check_file(photo, ANY_ITEM).ok            # the row that names nothing

    refused = check_file(photo, SIZED_ITEM)          # the row that names xlsx
    assert not refused.ok
    assert reasons.EXTENSION_NOT_ALLOWED.format(extension="jpg", allowed="xlsx") in refused.reason

    # A row that names an image type itself is taken at its word, PDF or no PDF.
    named = RequestItem(identifier="D01", document="Receipts",
                        allowed_extensions=("jpg",), min_size_kb=0)
    assert check_file(photo, named).ok
    assert not check_file(write_pdf(tmp_path / "ok.pdf"), named).ok

    for extension in IMAGE_EXTENSIONS:               # the whole list, one rule
        assert extension_allowed(extension, ("pdf",)), extension
        assert not extension_allowed(extension, ("xlsx", "csv")), extension
    assert not extension_allowed("bmp", ("pdf",))   # not every image is on the list


def test_a_file_pillow_cannot_open_is_refused_as_an_unreadable_image(tmp_path):
    """The photo tier does what the PDF tier does: open it, and say so when
    it will not open. A half-transferred photo is the client's to send
    again, so the sentence is theirs to act on."""
    not_a_photo = tmp_path / "holiday.jpg"
    not_a_photo.write_bytes(b"this is not a photo at all" * 10)

    result = check_file(not_a_photo, PDF_ITEM)
    assert not result.ok and result.code == reasons.UNREADABLE_IMAGE.code
    assert result.code == reasons.UNREADABLE_IMAGE.code
    assert reasons.UNREADABLE_IMAGE.code not in reasons.FIRM_SIDE      # the client can fix it


def test_a_heic_photo_is_refused_by_name_when_the_reader_is_absent_and_read_when_it_is_present(
    tmp_path, monkeypatch,
):
    """An iPhone sends HEIC. Pillow cannot open one on its own, so a machine
    without the decoder says which reader is missing - ours to install,
    never the client's to work around: they sent an ordinary photo."""
    monkeypatch.setattr("tracker.validators.HEIC_READABLE", False)
    absent = tmp_path / "receipt.heic"
    absent.write_bytes(b"\x00" * 4096)
    result = check_file(absent, PDF_ITEM)
    assert not result.ok and result.code == reasons.HEIC_NOT_SUPPORTED.code
    assert reasons.HEIC_NOT_SUPPORTED.code in reasons.FIRM_SIDE
    assert reasons.HEIC_NOT_SUPPORTED.client_ask == reasons.GENERIC_ASK   # never asked

    monkeypatch.undo()
    pillow_heif = pytest.importorskip("pillow_heif", reason="the HEIC reader is not on this machine")
    pillow_heif.register_heif_opener()
    from PIL import Image

    photo = tmp_path / "w-2.heic"
    Image.new("RGB", (400, 200), "white").save(photo)
    assert check_file(photo, PDF_ITEM).ok


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


def test_check_files_classification(tmp_path, monkeypatch):
    good, bad, cloud, junk = (tmp_path / "A01 - good.pdf", tmp_path / "A01 - bad.docx",
                              tmp_path / "A01 - cloud.pdf", tmp_path / "desktop.ini")
    write_pdf(good)
    bad.write_bytes(b"x" * 100)
    cloud.write_bytes(b"unsynced")
    junk.write_bytes(b"junk")
    monkeypatch.setattr(
        "tracker.validators.is_cloud_placeholder", lambda p: p.name == cloud.name
    )

    results = check_files([good, bad, cloud, junk], PDF_ITEM)
    assert [f.path for f in results if f.ok] == [good]
    assert [f.path for f in results if not f.ok and not f.pending_sync] == [bad]
    assert [f.path for f in results if f.pending_sync] == [cloud]
    assert junk not in [f.path for f in results]          # junk is passed over


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
    assert result.code == reasons.VANISHED.code


def test_pdf_readability_is_parsed_once_per_run_not_per_process(tmp_path, monkeypatch):
    # The router asks check_file() once per manifest row for one file; the
    # run's PdfVerdictCache keys the verdict by (path, size, mtime) so the
    # PDF is parsed once, a rewritten file gets a fresh parse - and a run
    # that brings no cache shares nothing with any other.
    import tracker.validators as v
    from tracker.validators import PdfVerdictCache

    calls = []
    real = v._pdf_error_uncached
    monkeypatch.setattr(v, "_pdf_error_uncached", lambda p: (calls.append(p), real(p))[1])
    pdf = write_pdf(tmp_path / "statement.pdf")
    run = PdfVerdictCache()
    for _ in range(5):
        assert check_file(pdf, PDF_ITEM, pdf_cache=run).ok
    assert len(calls) == 1

    write_pdf(pdf, pages=2)
    import os
    os.utime(pdf, ns=(1, 1))  # a different mtime, whatever the clock did
    assert check_file(pdf, PDF_ITEM, pdf_cache=run).ok
    assert len(calls) == 2

    assert check_file(pdf, PDF_ITEM, pdf_cache=PdfVerdictCache()).ok   # another run
    assert check_file(pdf, PDF_ITEM).ok                                 # no cache at all
    assert len(calls) == 4


def test_the_pdf_verdict_cache_is_bounded(tmp_path):
    from tracker.validators import PdfVerdictCache

    cache = PdfVerdictCache(limit=2)
    cache.put(("a", 1, 1), "")
    cache.put(("b", 1, 1), "")
    cache.put(("c", 1, 1), "")
    assert cache.get(("a", 1, 1)) is None and cache.get(("c", 1, 1)) == ""


def test_the_dry_run_names_a_persons_folder_once(tmp_path):
    """The review of 168, N-7: the dry-run preview names each folder inside
    Prepared once, in ruling 7's sentence, and a file no request's name
    claims once."""
    import subprocess
    import sys

    from tests.conftest import make_engagement
    from tracker.scaffold import PREPARED_DIR_NAME

    engagement = make_engagement(tmp_path, [PDF_ITEM])
    (engagement / PREPARED_DIR_NAME / "my notes").mkdir()
    (engagement / PREPARED_DIR_NAME / "stray.pdf").write_bytes(b"x")
    repo = Path(__file__).resolve().parents[1]
    done = subprocess.run([sys.executable, "-m", "tracker.validators", str(engagement)],
                          capture_output=True, text=True, cwd=repo, timeout=120)
    assert done.returncode == 0, done.stderr
    said = reasons.PERSONS_FOLDER.format(folder="my notes", prepared=PREPARED_DIR_NAME)
    assert done.stdout.count("my notes") == 1 and f"    ? {said}" in done.stdout
    assert done.stdout.count("stray.pdf") == 1


# ------------------------------------------- decision 190: programs and macros ----


def test_a_program_is_known_by_its_real_last_extension():
    from tracker.validators import is_program

    assert is_program("W-2 2025.pdf.exe")
    assert is_program("W2‮fdp.exe")
    assert is_program("statement.pdf.LNK")
    assert is_program("payroll.exe. ")                  # Windows drops the trailing dot and space
    assert is_program("folder.library-ms")
    assert not is_program("W-2 2025.exe.pdf")
    assert not is_program("W-2.pdf")


def test_an_office_file_bears_macros_by_its_type_or_its_vba_project(tmp_path):
    import zipfile

    from tracker.validators import bears_macros

    plain = tmp_path / "budget.xlsx"
    with zipfile.ZipFile(plain, "w") as package:
        package.writestr("xl/workbook.xml", "<workbook/>")
    renamed = tmp_path / "renamed.xlsx"
    with zipfile.ZipFile(renamed, "w") as package:
        package.writestr("xl/workbook.xml", "<workbook/>")
        package.writestr("xl/vbaProject.bin", b"\x00")
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"not a zip")
    (tmp_path / "macros.docm").write_bytes(b"")
    (tmp_path / "old.xls").write_bytes(b"")

    assert bears_macros(tmp_path / "macros.docm") and bears_macros(tmp_path / "old.xls")
    assert bears_macros(renamed)
    assert bears_macros(broken)                          # cannot look: marked, the safe way
    assert not bears_macros(plain)
    assert not bears_macros(tmp_path / "W-2.pdf")


@pytest.mark.parametrize("raw", ["W2.exe​", "Pay.scr﻿.", "W2.ex​e", "x.lnk‬"])
def test_a_program_is_known_by_either_name(raw):
    """The review's M1: an invisible character after or inside the suffix
    hides a program from its raw name; the recorded name - which names its
    review copy and its card - shows it, and either name is enough."""
    from tracker.validators import is_program

    assert is_program(raw)


def test_the_review_widened_the_program_and_macro_lists_and_left_web_pages_alone(tmp_path):
    """Decision 190's review (S5, N1): the installer packages, the shell
    types and the Access databases are programs; the legacy templates,
    add-ins and the binary workbook bear macros; a saved web page is not
    a program, because a client can legitimately send a statement as one."""
    from tracker.validators import bears_macros, is_program

    for name in ("app.msix", "setup.appinstaller", "run.pyw", "fix.diagcab", "books.accdb",
                 "old.mdb", "go.website", "x.shs"):
        assert is_program(name), name
    for name in ("statement.html", "statement.htm", "chart.svg", "notes.one"):
        assert not is_program(name), name
    for name in ("book.xlsb", "addin.xla", "form.xlt", "letter.dot", "deck.pot", "show.pps",
                 "tool.ppa", "book.xlsm​"):
        path = tmp_path / name
        path.write_bytes(b"not an office file")
        assert bears_macros(path), name
