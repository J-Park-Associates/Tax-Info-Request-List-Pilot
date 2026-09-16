"""Tests for tracker/scanner.py — full-loop orchestration on local folders."""

import datetime as dt
import json

import pytest
from openpyxl import load_workbook
from pypdf import PdfWriter

from tracker.manifest import (
    Override,
    RequestItem,
    Status,
    UNFILED_SHEET_NAME,
    create_template,
    load_manifest,
)
from tracker.scaffold import (
    MANIFEST_FILENAME,
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
    scaffold_engagement,
)
from tracker.scanner import (
    LOCK_FILENAME,
    ScanLockedError,
    scan_engagement,
)

DAY1 = dt.date(2026, 7, 1)
DAY2 = dt.date(2026, 7, 9)

ITEMS = [
    RequestItem(
        identifier="A01", document="Bank Statement", allowed_extensions=("pdf",),
        min_size_kb=0, required_keywords=("Chase",),
    ),
    RequestItem(
        identifier="A02", document="Monthly Statements", expected_count=3,
        allowed_extensions=("csv",), min_size_kb=0,
    ),
    RequestItem(
        identifier="B01", document="Payroll Register", allowed_extensions=("xlsx",),
        min_size_kb=10,
    ),
]


def text_pdf(path, text: str):
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
        len(bodies) + 1, xref_at,
    )
    path.write_bytes(bytes(out))
    return path


@pytest.fixture
def engagement(tmp_path):
    eng = tmp_path / "TY2025 1040"
    eng.mkdir()
    create_template(eng / MANIFEST_FILENAME, ITEMS)
    scaffold_engagement(eng)
    return eng


def folder(engagement, prefix):
    """The Prepared/ working folder for one request row."""
    prepared = engagement / PREPARED_DIR_NAME
    return next(p for p in prepared.iterdir() if p.is_dir() and p.name.startswith(prefix))


def statuses(engagement):
    return {i.identifier: i for i in load_manifest(engagement / MANIFEST_FILENAME)}


# ------------------------------------------------------------ resolution ----


def test_full_scan_statuses_and_writeback(engagement):
    text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec 2025")
    a02 = folder(engagement, "A02")
    (a02 / "jan.csv").write_text("jan data", encoding="utf-8")
    (a02 / "feb.csv").write_text("feb data", encoding="utf-8")
    # B01 left empty

    report = scan_engagement(engagement, today=DAY1)
    assert report.written and not report.deferred

    rows = statuses(engagement)
    assert rows["A01"].status == Status.RECEIVED
    assert rows["A01"].received_date == DAY1
    assert rows["A01"].file_count == 1
    assert rows["A02"].status == Status.PARTIAL
    assert "2 of 3 expected files" in rows["A02"].validation_notes
    assert rows["B01"].status == Status.MISSING
    assert rows["B01"].file_count == 0


def test_failed_validation_with_reasons(engagement):
    # Wrong content: tier 2 passes, tier 3 keyword check fails.
    text_pdf(folder(engagement, "A01") / "wrong.pdf", "Wells Fargo Statement Dec 2025")
    scan_engagement(engagement, today=DAY1)
    row = statuses(engagement)["A01"]
    assert row.status == Status.FAILED
    assert "'Chase' not found" in row.validation_notes


def test_received_date_sticky_across_scans(engagement):
    text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec 2025")
    scan_engagement(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY2)
    assert statuses(engagement)["A01"].received_date == DAY1  # first pass wins


def test_auto_revert_preserves_date_and_notes(engagement):
    pdf = text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec")
    scan_engagement(engagement, today=DAY1)

    pdf.unlink()                                   # client deleted their file
    scan_engagement(engagement, today=DAY2)
    row = statuses(engagement)["A01"]
    assert row.status == Status.MISSING            # auto-revert
    assert row.received_date == DAY1               # original date preserved
    assert "was Received 2026-07-01" in row.validation_notes


def test_manual_override_status_untouched(tmp_path):
    items = [
        RequestItem(
            identifier="A01", document="Bank Statement",
            allowed_extensions=("pdf",), min_size_kb=0,
            required_keywords=("Chase",), manual_override=Override.ACCEPTED,
            status=Status.RECEIVED, received_date=DAY1,
        ),
    ]
    eng = tmp_path / "Eng"
    eng.mkdir()
    create_template(eng / MANIFEST_FILENAME, items)
    # seed scanner columns the accountant "kept" via override
    from tracker.manifest import StatusUpdate, write_statuses
    write_statuses(
        eng / MANIFEST_FILENAME,
        {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1, received_date=DAY1)},
    )
    scaffold_engagement(eng)
    text_pdf(folder(eng, "A01") / "wrong.pdf", "Wells Fargo Statement December")

    scan_engagement(eng, today=DAY2)
    row = statuses(eng)["A01"]
    assert row.status == Status.RECEIVED           # override kept it
    assert row.received_date == DAY1
    assert row.validation_notes.startswith("[override: Accepted]")
    assert "'Chase' not found" in row.validation_notes  # facts still recorded


def test_duplicates_do_not_inflate_count(engagement):
    a02 = folder(engagement, "A02")
    (a02 / "jan.csv").write_text("identical bytes", encoding="utf-8")
    (a02 / "jan (1).csv").write_text("identical bytes", encoding="utf-8")
    (a02 / "feb.csv").write_text("different bytes", encoding="utf-8")

    scan_engagement(engagement, today=DAY1)
    row = statuses(engagement)["A02"]
    assert row.file_count == 2                     # 3 files, 2 distinct
    assert row.status == Status.PARTIAL
    assert "1 duplicate file(s) ignored" in row.validation_notes


def test_pending_sync_status(engagement, monkeypatch):
    ghost = folder(engagement, "A01") / "cloud.pdf"
    ghost.write_bytes(b"unsynced placeholder bytes")
    monkeypatch.setattr(
        "tracker.validators.is_cloud_placeholder", lambda p: p.name == "cloud.pdf"
    )
    scan_engagement(engagement, today=DAY1)
    row = statuses(engagement)["A01"]
    assert row.status == Status.PENDING_SYNC
    assert "still syncing" in row.validation_notes


def test_deleted_folder_reported_missing(engagement):
    folder(engagement, "A01").rmdir()
    scan_engagement(engagement, today=DAY1)
    row = statuses(engagement)["A01"]
    assert row.status == Status.MISSING
    assert "re-run scaffold" in row.validation_notes


# --------------------------------------------------------------- unfiled ----


def test_unfiled_sheet_written(engagement):
    prepared = engagement / PREPARED_DIR_NAME
    review = prepared / REVIEW_DIR_NAME
    (review / "scan0012.pdf").write_bytes(b"x" * 100)
    (prepared / "loose_notes.txt").write_text("oops", encoding="utf-8")
    rogue = prepared / "misc uploads"
    rogue.mkdir()
    (rogue / "something.pdf").write_bytes(b"x")

    scan_engagement(engagement, today=DAY1)
    wb = load_workbook(engagement / MANIFEST_FILENAME)
    assert UNFILED_SHEET_NAME in wb.sheetnames
    rows = list(wb[UNFILED_SHEET_NAME].iter_rows(min_row=2, values_only=True))
    wb.close()
    names = {r[0]: r[1] for r in rows}
    assert names["scan0012.pdf"] == "needs review - could not be matched to a request"
    assert names["loose_notes.txt"] == "loose file in Prepared root"
    assert names["misc uploads"] == "unrecognized folder (1 file(s))"

    # resolved next scan -> sheet snapshot empties
    (review / "scan0012.pdf").unlink()
    (prepared / "loose_notes.txt").unlink()
    (rogue / "something.pdf").unlink()
    rogue.rmdir()
    scan_engagement(engagement, today=DAY2)
    wb = load_workbook(engagement / MANIFEST_FILENAME)
    assert list(wb[UNFILED_SHEET_NAME].iter_rows(min_row=2, values_only=True)) == []
    wb.close()


# ------------------------------------------------------- lock and dry-run ----


def test_dry_run_writes_nothing(engagement):
    text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec 2025")
    report = scan_engagement(engagement, today=DAY1, dry_run=True)
    assert report.dry_run and not report.written
    assert report.updates["A01"].status == Status.RECEIVED  # facts computed
    assert statuses(engagement)["A01"].status == ""          # nothing written
    assert not (engagement / "_content_cache.json").exists()
    assert not (engagement / LOCK_FILENAME).exists()


def test_fresh_lock_blocks_scan(engagement):
    (engagement / LOCK_FILENAME).write_text("pid=999", encoding="utf-8")
    with pytest.raises(ScanLockedError, match="another scan"):
        scan_engagement(engagement, today=DAY1)


def test_stale_lock_replaced_and_released(engagement):
    import os

    lock = engagement / LOCK_FILENAME
    lock.write_text("pid=999", encoding="utf-8")
    old = (dt.datetime.now() - dt.timedelta(hours=2)).timestamp()
    os.utime(lock, (old, old))

    report = scan_engagement(engagement, today=DAY1)   # takes over stale lock
    assert report.written
    assert not lock.exists()                           # released afterwards


def test_content_cache_created_and_pruned(engagement):
    pdf = text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec")
    scan_engagement(engagement, today=DAY1)
    cache_file = engagement / "_content_cache.json"
    assert cache_file.exists()
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert any("chase.pdf" in k for k in data["files"])

    pdf.unlink()
    scan_engagement(engagement, today=DAY2)            # prune removes entry
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert not any("chase.pdf" in k for k in data["files"])
