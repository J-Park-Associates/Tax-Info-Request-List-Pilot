"""Tests for tracker/filer.py — sorting the client's drop folder.

The promises being tested: the client's original is preserved byte-for-byte
under its own name in PBC, a renamed working copy appears in Prepared, every
decision is written to the index, and running twice changes nothing.
"""

import datetime as dt

import pytest
from openpyxl import load_workbook

from tracker.filer import (
    DUPLICATE,
    FILED,
    INDEX_FILENAME,
    INDEX_SHEET,
    NEEDS_REVIEW,
    file_drops,
    prepared_name_for,
    read_index,
)
from tracker.manifest import RequestItem, create_template
from tracker.scaffold import (
    MANIFEST_FILENAME,
    PBC_DIR_NAME,
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
    SHARED_DIR_NAME,
    scaffold_engagement,
)

from tests.test_scanner import text_pdf

DAY1 = dt.date(2026, 7, 1)
DAY2 = dt.date(2026, 7, 9)

ITEMS = [
    RequestItem(
        identifier="A01", document="W-2 Wage Statements", period="TY2025",
        expected_count=2, allowed_extensions=("pdf",), min_size_kb=0,
        required_keywords=("W-2",), date_pattern=r"(?i)\b2025\b",
    ),
    RequestItem(
        identifier="C01", document="Mortgage Interest Statement", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("1098",),
    ),
]


@pytest.fixture
def engagement(tmp_path):
    eng = tmp_path / "Smith Family 2025"
    eng.mkdir()
    create_template(eng / MANIFEST_FILENAME, ITEMS)
    scaffold_engagement(eng)
    return eng


def drop(engagement, name, text):
    """Client drops one document into the single shared folder."""
    return text_pdf(engagement / SHARED_DIR_NAME / name, text)


def pbc(engagement):
    return engagement / SHARED_DIR_NAME / PBC_DIR_NAME


def prepared(engagement, folder_prefix):
    root = engagement / PREPARED_DIR_NAME
    return next(p for p in root.iterdir() if p.name.startswith(folder_prefix))


# ------------------------------------------------------------- the happy path ----


def test_file_is_sorted_renamed_and_indexed(engagement):
    original = drop(engagement, "scan0012.pdf", "Form W-2 Wage and Tax Statement 2025")
    before = original.read_bytes()

    report = file_drops(engagement, today=DAY1)

    # Original: moved out of the drop zone, name and bytes untouched.
    assert not original.exists()
    kept = pbc(engagement) / "scan0012.pdf"
    assert kept.read_bytes() == before

    # Working copy: renamed to the firm's convention.
    copies = list(prepared(engagement, "A01").iterdir())
    assert [p.name for p in copies] == ["A01 - W-2 Wage Statements - TY2025.pdf"]
    assert copies[0].read_bytes() == before

    # Index: one row that maps original -> filed.
    (entry,) = report.filed
    assert entry.original_name == "scan0012.pdf"
    assert entry.decision == FILED
    assert entry.identifier == "A01"
    assert entry.pbc_location == f"{SHARED_DIR_NAME}/{PBC_DIR_NAME}/scan0012.pdf"
    assert entry.prepared_location.endswith("A01 - W-2 Wage Statements - TY2025.pdf")

    rows = read_index(engagement / INDEX_FILENAME)
    assert [r.original_name for r in rows] == ["scan0012.pdf"]
    assert rows[0].digest == entry.digest


def test_second_file_for_the_same_request_is_numbered(engagement):
    drop(engagement, "john w2.pdf", "Form W-2 Wage and Tax Statement 2025 John")
    drop(engagement, "jane w2.pdf", "Form W-2 Wage and Tax Statement 2025 Jane")
    file_drops(engagement, today=DAY1)

    names = sorted(p.name for p in prepared(engagement, "A01").iterdir())
    assert names == [
        "A01 - W-2 Wage Statements - TY2025 (2).pdf",
        "A01 - W-2 Wage Statements - TY2025.pdf",
    ]


def test_client_subfolders_are_flattened(engagement):
    nested = engagement / SHARED_DIR_NAME / "tax stuff"
    nested.mkdir()
    text_pdf(nested / "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    report = file_drops(engagement, today=DAY1)
    assert len(report.filed) == 1
    assert (pbc(engagement) / "w2.pdf").exists()


# --------------------------------------------------------------- needs review ----


def test_unroutable_file_is_preserved_and_parked(engagement):
    original = drop(engagement, "vacation.pdf", "Photos from Maui")
    before = original.read_bytes()

    report = file_drops(engagement, today=DAY1)

    assert (pbc(engagement) / "vacation.pdf").read_bytes() == before
    review = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    assert (review / "vacation.pdf").exists()
    (entry,) = report.review
    assert entry.decision == NEEDS_REVIEW
    assert "matched no request" in entry.reason
    assert not report.filed


def test_review_copies_keep_the_clients_own_name(engagement):
    drop(engagement, "IMG_4021.pdf", "unreadable receipt")
    file_drops(engagement, today=DAY1)
    review = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    assert [p.name for p in review.iterdir()] == ["IMG_4021.pdf"]


# ------------------------------------------------------------------ re-running ----


def test_rerunning_changes_nothing(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
    snapshot = {
        p: p.read_bytes()
        for p in (engagement / PREPARED_DIR_NAME).rglob("*") if p.is_file()
    }

    second = file_drops(engagement, today=DAY2)

    assert second.handled == 0
    assert {
        p: p.read_bytes()
        for p in (engagement / PREPARED_DIR_NAME).rglob("*") if p.is_file()
    } == snapshot


def test_same_document_dropped_twice_is_kept_but_filed_once(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
    # Client re-sends the identical document under a different name.
    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025")

    report = file_drops(engagement, today=DAY2)

    (dup,) = report.duplicates
    assert dup.decision == DUPLICATE
    assert "identical to w2.pdf" in dup.reason
    # Preserved, never deleted...
    assert (pbc(engagement) / "w2 again.pdf").exists()
    # ...but not filed a second time.
    assert len(list(prepared(engagement, "A01").iterdir())) == 1


def test_name_collision_in_pbc_never_overwrites(engagement):
    drop(engagement, "statement.pdf", "Form W-2 Wage and Tax Statement 2025 John")
    file_drops(engagement, today=DAY1)
    drop(engagement, "statement.pdf", "Form W-2 Wage and Tax Statement 2025 Jane")

    file_drops(engagement, today=DAY2)

    kept = sorted(p.name for p in pbc(engagement).iterdir())
    assert kept == ["statement (2).pdf", "statement.pdf"]


# ------------------------------------------------------------------- guarded ----


def test_placeholders_are_left_where_they_are(engagement, monkeypatch):
    waiting = drop(engagement, "big.pdf", "Form W-2 Wage and Tax Statement 2025")
    monkeypatch.setattr("tracker.filer.is_cloud_placeholder", lambda p: True)

    report = file_drops(engagement, today=DAY1)

    assert report.waiting == [waiting]
    assert waiting.exists()                       # untouched, still syncing
    assert not any(pbc(engagement).iterdir())


def test_sync_junk_is_ignored(engagement):
    junk = engagement / SHARED_DIR_NAME / "w2.pdf.tmp.driveupload"
    junk.write_bytes(b"partial upload")

    report = file_drops(engagement, today=DAY1)

    assert report.handled == 0
    assert junk.exists()                          # not ours to move or delete


def test_pbc_contents_are_never_re_sorted(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
    # The originals now sitting in PBC must not look like new drops.
    assert file_drops(engagement, today=DAY2).handled == 0


def test_dry_run_moves_nothing(engagement):
    original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    report = file_drops(engagement, today=DAY1, dry_run=True)

    assert len(report.filed) == 1                 # it still tells you the plan
    assert original.exists()
    assert not any(pbc(engagement).iterdir())
    assert not (engagement / INDEX_FILENAME).exists()


# --------------------------------------------------------------------- index ----


def test_index_workbook_is_readable_in_excel(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "mystery.pdf", "nothing recognizable here")
    file_drops(engagement, today=DAY1)

    wb = load_workbook(engagement / INDEX_FILENAME)
    ws = wb[INDEX_SHEET]
    header = [c.value for c in ws[1]]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()

    assert header[:4] == ["Received", "Original Name", "Size KB", "SHA-256"]
    assert {r[1] for r in rows} == {"w2.pdf", "mystery.pdf"}
    decisions = {r[1]: r[9] for r in rows}
    assert decisions["w2.pdf"] == FILED
    assert decisions["mystery.pdf"] == NEEDS_REVIEW


def test_prepared_name_for_collides_safely():
    item = ITEMS[0]
    taken: set[str] = set()
    first = prepared_name_for(item, "pdf", taken)
    second = prepared_name_for(item, "pdf", taken)
    assert first == "A01 - W-2 Wage Statements - TY2025.pdf"
    assert second == "A01 - W-2 Wage Statements - TY2025 (2).pdf"


def test_dry_run_previews_real_numbering(engagement):
    drop(engagement, "john w2.pdf", "Form W-2 Wage and Tax Statement 2025 John")
    drop(engagement, "jane w2.pdf", "Form W-2 Wage and Tax Statement 2025 Jane")

    planned = [e.filed_as for e in file_drops(engagement, today=DAY1, dry_run=True).filed]

    assert sorted(planned) == [
        "A01 - W-2 Wage Statements - TY2025 (2).pdf",
        "A01 - W-2 Wage Statements - TY2025.pdf",
    ]
