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
    from tracker.filer import INDEX_COLUMNS, INDEX_LAYOUT

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
    wb = load_workbook(engagement / INDEX_FILENAME)
    ws = wb[INDEX_SHEET]
    headers = [c.value for c in ws[1]]
    assert headers == list(INDEX_COLUMNS)
    # Read the row by header name, the way the filer itself reads it back.
    row = dict(zip(headers, [c.value for c in ws[2]]))
    assert row[INDEX_LAYOUT["decision"][0]] == FILED
    assert row[INDEX_LAYOUT["identifier"][0]] == "A01"
    assert row[INDEX_LAYOUT["prepared_location"][0]].endswith(".pdf")
    assert ws.freeze_panes == "A2"
    wb.close()


def test_an_index_written_with_older_columns_still_reads(tmp_path):
    # Filed As and Document were stored copies and are gone; Candidates is
    # new. An index from before either change reads by header name.
    from openpyxl import Workbook
    from tracker.filer import read_index

    wb = Workbook()
    ws = wb.active
    ws.title = INDEX_SHEET
    ws.append(["Received", "Original Name", "Size KB", "SHA-256", "Identifier", "Document",
               "Filed As", "Prepared Location", "PBC Location", "Decision", "Reason"])
    ws.append(["2026-01-01", "w2.pdf", 9.4, "abc", "A01", "W-2 Wage Statements",
               "A01 - W-2 Wage Statements - TY2025.pdf",
               "Prepared/A01 - W-2 Wage Statements/A01 - W-2 Wage Statements - TY2025.pdf",
               "Shared/PBC/w2.pdf", FILED, "content matched"])
    path = tmp_path / INDEX_FILENAME
    wb.save(path)
    [entry] = read_index(path)
    assert entry.identifier == "A01" and entry.decision == FILED
    assert entry.filed_as == "A01 - W-2 Wage Statements - TY2025.pdf"   # derived, not stored
    assert entry.candidates == ""


def test_the_routers_candidates_travel_as_data_in_the_index(engagement):
    from tracker.filer import read_index

    drop(engagement, "old.pdf", "Form W-2 Wage and Tax Statement 2024")   # contested: wrong year
    report = file_drops(engagement, today=DAY1)
    [parked] = report.review
    assert parked.candidates == "A01"
    assert read_index(engagement / INDEX_FILENAME)[0].candidates == "A01"


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


# ------------------------------------------- one bad file never costs the trail ----


def test_a_locked_index_never_orphans_files_already_moved(engagement, monkeypatch):
    # Originals are moved into PBC before the index is written. If Excel
    # holds _index.xlsx, the rows must still be recorded somewhere the next
    # run reads — a moved file that is nowhere in the index is lost to the
    # workflow, because PBC is never re-sorted.
    import tracker.filer as filer_module

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "mortgage.pdf", "Form 1098 Mortgage Interest Statement 2025")

    def locked(wb, path):
        raise PermissionError(f"[Errno 13] locked: {path}")

    monkeypatch.setattr(filer_module, "save_workbook_atomically", locked)
    monkeypatch.setattr(filer_module, "LOCK_RETRY_DELAY", 0.001)
    report = file_drops(engagement, today=DAY1)
    assert report.handled == 2
    assert report.index_deferred is True
    assert (engagement / filer_module.INDEX_PENDING_FILENAME).exists()
    assert not (engagement / INDEX_FILENAME).exists()
    # The deferred rows are already visible to whoever reads the index.
    assert {e.original_name for e in read_index(engagement / INDEX_FILENAME)} == {
        "w2.pdf", "mortgage.pdf",
    }

    # Excel closed; the next run has nothing to sort but folds the rows in.
    monkeypatch.undo()
    report = file_drops(engagement, today=DAY2)
    assert report.index_deferred is False
    assert (engagement / INDEX_FILENAME).exists()
    assert not (engagement / filer_module.INDEX_PENDING_FILENAME).exists()
    rows = read_index(engagement / INDEX_FILENAME)
    assert {e.original_name for e in rows} == {"w2.pdf", "mortgage.pdf"}
    assert all(e.decision == FILED for e in rows)


def test_a_failure_after_the_move_is_recorded_and_the_rest_still_filed(engagement, monkeypatch):
    import shutil

    drop(engagement, "a-w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "b-mortgage.pdf", "Form 1098 Mortgage Interest Statement 2025")
    drop(engagement, "c-w2.pdf", "Form W-2 Wage and Tax Statement 2025 Jane")
    real_copy = shutil.copy2

    def disk_full(src, dst, *args, **kwargs):
        if "b-mortgage" in str(src):
            raise OSError(28, "No space left on device")
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copy2", disk_full)
    report = file_drops(engagement, today=DAY1)

    assert [e.original_name for e in report.filed] == ["a-w2.pdf", "c-w2.pdf"]
    assert [e.name for e in report.errors] == ["b-mortgage.pdf"]
    assert report.errors[0].left_in_place is False
    # Every original is in PBC, and every one of them is in the index.
    assert {p.name for p in pbc(engagement).iterdir()} == {
        "a-w2.pdf", "b-mortgage.pdf", "c-w2.pdf",
    }
    rows = {e.original_name: e for e in read_index(engagement / INDEX_FILENAME)}
    assert set(rows) == {"a-w2.pdf", "b-mortgage.pdf", "c-w2.pdf"}
    assert rows["b-mortgage.pdf"].decision == NEEDS_REVIEW
    assert "No space left" in rows["b-mortgage.pdf"].reason
    assert "PBC/b-mortgage.pdf" in rows["b-mortgage.pdf"].reason


def test_a_drop_still_held_open_is_left_for_the_next_run(engagement, monkeypatch):
    import shutil

    drop(engagement, "a-w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "b-mortgage.pdf", "Form 1098 Mortgage Interest Statement 2025")
    real_move = shutil.move

    def held_open(src, dst, *args, **kwargs):
        if "a-w2" in str(src):
            raise PermissionError("[WinError 32] used by another process")
        return real_move(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "move", held_open)
    report = file_drops(engagement, today=DAY1)

    assert [e.original_name for e in report.filed] == ["b-mortgage.pdf"]
    assert [e.name for e in report.errors] == ["a-w2.pdf"]
    assert report.errors[0].left_in_place is True
    assert (engagement / SHARED_DIR_NAME / "a-w2.pdf").exists()  # untouched
    assert {e.original_name for e in read_index(engagement / INDEX_FILENAME)} == {
        "b-mortgage.pdf",
    }

    # Released: the next run sorts it as if nothing had happened.
    monkeypatch.undo()
    report = file_drops(engagement, today=DAY2)
    assert [e.original_name for e in report.filed] == ["a-w2.pdf"]
    assert report.errors == []


# ------------------------------------------------------------ one run at a time ----


def test_the_filer_holds_the_engagement_lock(engagement):
    # A second run mid-way used to move the remaining files and overwrite
    # the first run's index rows. Same lock as the scanner, same answer.
    from tracker.locking import LOCK_FILENAME, EngagementLockedError

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    (engagement / LOCK_FILENAME).write_text("pid=999", encoding="utf-8")
    with pytest.raises(EngagementLockedError):
        file_drops(engagement, today=DAY1)
    assert (engagement / SHARED_DIR_NAME / "w2.pdf").exists()   # nothing moved
    # A dry run writes nothing, so it needs no lock.
    assert file_drops(engagement, today=DAY1, dry_run=True).handled == 1
    (engagement / LOCK_FILENAME).unlink()
    assert file_drops(engagement, today=DAY1).handled == 1
    assert not (engagement / LOCK_FILENAME).exists()


def test_a_document_renamed_in_excel_keeps_filing_into_its_existing_folder(engagement):
    drop(engagement, "john.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
    wb = load_workbook(engagement / MANIFEST_FILENAME)
    wb["Requests"].cell(row=2, column=2, value="W-2s (all employers)")
    wb.save(engagement / MANIFEST_FILENAME)
    wb.close()
    drop(engagement, "jane.pdf", "Form W-2 Wage and Tax Statement 2025 Jane")
    report = file_drops(engagement, today=DAY2)
    folders = [p.name for p in (engagement / PREPARED_DIR_NAME).iterdir() if p.name.startswith("A01")]
    assert folders == ["A01 - W-2 Wage Statements"]
    assert report.filed[0].prepared_location.startswith("Prepared/A01 - W-2 Wage Statements/")


def test_a_file_dropped_straight_into_pbc_is_filed_and_indexed(engagement):
    # The client can see PBC/ and was told to drop things anywhere.
    original = text_pdf(pbc(engagement) / "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    before = original.read_bytes()
    report = file_drops(engagement, today=DAY1)
    assert [e.original_name for e in report.filed] == ["w2.pdf"]
    assert original.read_bytes() == before                    # not moved, not touched
    rows = read_index(engagement / INDEX_FILENAME)
    assert rows[0].pbc_location == "Shared/PBC/w2.pdf"
    assert (engagement / rows[0].prepared_location).exists()
    # Recorded now, so the next run leaves it alone.
    assert file_drops(engagement, today=DAY2).handled == 0


def test_a_resend_is_refiled_when_the_working_copy_was_deleted(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    first = file_drops(engagement, today=DAY1).filed[0]
    working = engagement / first.prepared_location
    working.unlink()                                          # a preparer's slip
    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025")
    report = file_drops(engagement, today=DAY2)
    assert report.duplicates == []
    assert [e.original_name for e in report.filed] == ["w2 again.pdf"]
    assert "re-filed" in report.filed[0].reason
    assert working.exists()                                   # same canonical name again
    # A re-send whose working copy is still there is still just a duplicate.
    drop(engagement, "w2 third time.pdf", "Form W-2 Wage and Tax Statement 2025")
    assert [e.decision for e in file_drops(engagement, today=DAY2).duplicates] == [DUPLICATE]


def test_empty_client_folders_are_cleared_after_sorting(engagement):
    nested = engagement / SHARED_DIR_NAME / "from my phone" / "scans"
    nested.mkdir(parents=True)
    text_pdf(nested / "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    (engagement / SHARED_DIR_NAME / "keep" ).mkdir()
    (engagement / SHARED_DIR_NAME / "keep" / "later.txt.tmp").write_text("x")  # still uploading
    file_drops(engagement, today=DAY1)
    left = sorted(p.name for p in (engagement / SHARED_DIR_NAME).iterdir() if p.is_dir())
    assert left == [PBC_DIR_NAME, "keep"]


def test_a_hand_edited_index_cell_does_not_stop_the_next_run(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
    wb = load_workbook(engagement / INDEX_FILENAME)
    wb.active.cell(row=2, column=3, value="about 9 KB")
    wb.save(engagement / INDEX_FILENAME)
    wb.close()
    drop(engagement, "jane.pdf", "Form W-2 Wage and Tax Statement 2025 Jane")
    assert [e.original_name for e in file_drops(engagement, today=DAY2).filed] == ["jane.pdf"]
    assert read_index(engagement / INDEX_FILENAME)[0].size_kb == 0.0


# ------------------------------------------------- a person files a parked file ----


def test_assigning_a_parked_file_moves_it_under_the_canonical_name(engagement):
    from tracker.filer import ASSIGNED_BY_PERSON, assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = file_drops(engagement, today=DAY1).review[0]
    review_copy = engagement / parked.prepared_location
    assert review_copy.exists()

    result = assign_review_file(engagement, parked.pbc_location, "C01", keyword="Home Lending", today=DAY2)

    assert result.moved_review_copy is True
    assert not review_copy.exists()
    working = engagement / result.entry.prepared_location
    assert working.name == "C01 - Mortgage Interest Statement - TY2025.pdf"
    assert working.read_bytes() == (engagement / parked.pbc_location).read_bytes()
    assert (engagement / parked.pbc_location).exists()               # original untouched
    [row] = read_index(engagement / INDEX_FILENAME)
    assert row.decision == FILED and row.identifier == "C01"
    assert row.reason.startswith(f"{ASSIGNED_BY_PERSON} on {DAY2.isoformat()}; was: ")
    assert result.keyword == "Home Lending" and result.keyword_note == ""
    from tracker.manifest import load_manifest
    assert next(i for i in load_manifest(engagement / MANIFEST_FILENAME) if i.identifier == "C01").any_keywords == ("Home Lending",)


def test_assigning_copies_from_pbc_when_the_review_copy_is_gone(engagement):
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = file_drops(engagement, today=DAY1).review[0]
    (engagement / parked.prepared_location).unlink()
    result = assign_review_file(engagement, "scan0012.pdf", "A01")   # by original name
    assert result.moved_review_copy is False
    assert (engagement / result.entry.prepared_location).exists()


def test_assigning_refuses_what_a_person_should_not_do(engagement):
    from tracker.filer import FilingError, assign_review_file
    from tracker.manifest import RequestItem, Override, create_template

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
    with pytest.raises(FilingError, match="no request 'Z99'"):
        assign_review_file(engagement, "scan0012.pdf", "Z99")
    with pytest.raises(FilingError, match="is not waiting for review"):
        assign_review_file(engagement, "w2.pdf", "C01")               # already filed
    with pytest.raises(FilingError, match="nothing in the index is called"):
        assign_review_file(engagement, "ghost.pdf", "C01")

    waived = engagement.parent / "Waived"
    waived.mkdir()
    create_template(waived / MANIFEST_FILENAME, [
        RequestItem(identifier="A01", document="W-2", manual_override=Override.WAIVED)])
    scaffold_engagement(waived)
    drop(waived, "x.pdf", "nothing")
    file_drops(waived, today=DAY1)
    with pytest.raises(FilingError, match="waived"):
        assign_review_file(waived, "x.pdf", "A01")


def test_assigning_still_files_when_excel_holds_the_manifest(engagement, monkeypatch):
    import tracker.manifest as manifest_module
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    file_drops(engagement, today=DAY1)

    def locked(*args, **kwargs):
        raise PermissionError("[Errno 13] locked by Excel")

    monkeypatch.setattr(manifest_module, "add_any_keyword", locked)
    monkeypatch.setattr("tracker.filer.add_any_keyword", locked)
    result = assign_review_file(engagement, "scan0012.pdf", "C01", keyword="lender")
    assert result.entry.decision == FILED
    assert result.keyword == "" and "open in Excel" in result.keyword_note
