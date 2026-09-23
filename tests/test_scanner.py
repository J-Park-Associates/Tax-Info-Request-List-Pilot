"""Tests for tracker/scanner.py — full-loop orchestration on local folders."""

import datetime as dt
import os
from dataclasses import replace

import pytest

from tests.conftest import make_engagement, named_page, sort
from tracker import ledger, reasons, store
from tracker.content_check import CACHE_VERSION, RETIRED_CACHE_FILENAME
from tracker.layout import inbox_of
from tracker.locking import LOCK_FILENAME, STALE_LOCK_SECONDS
from tracker.manifest import (
    SUMMARY_SEPARATOR,
    Override,
    RequestItem,
    Status,
    load_engagement_info,
    load_manifest,
    save_rules,
)
from tracker.records import rule_from_json
from tracker.scaffold import PREPARED_DIR_NAME, REVIEW_DIR_NAME, scaffold_engagement
from tracker.scanner import (
    DUPLICATES_NOTE,
    OVERRIDE_NOTE,
    PARTIAL_NOTE,
    REGRESSION_COUNT_RAISED,
    REGRESSION_FILES_CHANGED,
    REGRESSION_NOTE,
    SYNCING_NOTE,
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


def text_pdf(path, text: str, pages: int = 1):
    """A valid PDF whose every page says ``text`` (nothing, for a scan)."""
    def _pdf_string(line: str) -> str:
        return "(" + line.replace(chr(92), chr(92) * 2).replace("(", chr(92) + "(").replace(")", chr(92) + ")") + ")"
    lines = text.split(chr(10)) if text else [""]
    body = " ".join(f"{_pdf_string(line)} Tj T*" for line in lines)
    content = f"BT /F1 12 Tf 14 TL 72 720 Td {body} ET".encode("latin-1", "replace")
    stream, font = 3 + pages, 4 + pages          # objects 3..2+pages are the pages
    kids = b" ".join(b"%d 0 R" % (3 + i) for i in range(pages))
    bodies = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, pages),
        stream: b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        font: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for i in range(pages):
        bodies[3 + i] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents %d 0 R /Resources << /Font << /F1 %d 0 R >> >> >>" % (stream, font)
        )
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
    return make_engagement(tmp_path, ITEMS)


def edit_row(engagement, identifier, **fields):
    """A person changing one row in the app, saved as one event."""
    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement)]
    edited = [replace(row, **fields) if row.identifier == identifier else row for row in rows]
    return save_rules(engagement, edited, load_engagement_info(engagement))


def folder(engagement, prefix):
    """The Prepared/ working folder for one request row."""
    prepared = engagement / PREPARED_DIR_NAME
    return next(p for p in prepared.iterdir() if p.is_dir() and p.name.startswith(prefix))


def statuses(engagement):
    return {i.identifier: i for i in load_manifest(engagement)}


def cache_rows(engagement):
    """The engagement's verdict cache as the store holds it: (memos, verdicts)."""
    return store.cached_verdicts(store.connect(), engagement, version=CACHE_VERSION)


# ------------------------------------------------------------ resolution ----


def test_full_scan_statuses_and_writeback(engagement):
    text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec 2025")
    a02 = folder(engagement, "A02")
    (a02 / "jan.csv").write_text("jan data", encoding="utf-8")
    (a02 / "feb.csv").write_text("feb data", encoding="utf-8")
    # B01 left empty

    report = scan_engagement(engagement, today=DAY1)
    assert report.recorded == 3

    rows = statuses(engagement)
    assert rows["A01"].status == Status.RECEIVED
    assert rows["A01"].received_date == DAY1
    assert rows["A01"].file_count == 1
    assert rows["A02"].status == Status.PARTIAL
    assert PARTIAL_NOTE.format(count=2, expected=3) in rows["A02"].validation_notes
    assert rows["B01"].status == Status.MISSING
    assert rows["B01"].file_count == 0


def test_failed_validation_with_reasons(engagement):
    # Wrong content: tier 2 passes, tier 3 keyword check fails.
    text_pdf(folder(engagement, "A01") / "wrong.pdf", "Wells Fargo Statement Dec 2025")
    scan_engagement(engagement, today=DAY1)
    row = statuses(engagement)["A01"]
    assert row.status == Status.FAILED
    assert reasons.WRONG_DOCUMENT.matches(row.validation_notes) and "'Chase'" in row.validation_notes


def test_received_date_sticky_across_scans(engagement):
    text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec 2025")
    scan_engagement(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY2)
    assert statuses(engagement)["A01"].received_date == DAY1  # first pass wins


def test_auto_revert_preserves_date_and_notes(engagement):
    pdf = text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec 2025")
    scan_engagement(engagement, today=DAY1)

    pdf.unlink()                                   # client deleted their file
    scan_engagement(engagement, today=DAY2)
    row = statuses(engagement)["A01"]
    assert row.status == Status.MISSING            # auto-revert
    assert row.received_date == DAY1               # original date preserved
    assert REGRESSION_NOTE.format(status=Status.RECEIVED, date="2026-07-01", why="").rstrip("; ") in row.validation_notes


def test_manual_override_status_untouched(tmp_path):
    items = [
        RequestItem(
            identifier="A01", document="Bank Statement",
            allowed_extensions=("pdf",), min_size_kb=0,
            required_keywords=("Chase",), manual_override=Override.ACCEPTED,
            override_reason="Client confirmed this is the final version",
            status=Status.RECEIVED, received_date=DAY1,
        ),
    ]
    eng = make_engagement(tmp_path, items, return_name="1040 - Another Client")
    # the status the last scan recorded, which the override keeps
    from tests.conftest import seed_statuses
    from tracker.manifest import StatusUpdate

    seed_statuses(
        eng, {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1, received_date=DAY1)},
    )
    text_pdf(folder(eng, "A01") / "wrong.pdf", "Wells Fargo Statement December")

    scan_engagement(eng, today=DAY2)
    row = statuses(eng)["A01"]
    assert row.status == Status.RECEIVED           # override kept it
    assert row.received_date == DAY1
    assert row.validation_notes.startswith(OVERRIDE_NOTE.format(override=Override.ACCEPTED))
    assert reasons.WRONG_DOCUMENT.matches(row.validation_notes) and "'Chase'" in row.validation_notes  # facts still recorded


def test_duplicates_do_not_inflate_count(engagement):
    a02 = folder(engagement, "A02")
    (a02 / "jan.csv").write_text("identical bytes", encoding="utf-8")
    (a02 / "jan (1).csv").write_text("identical bytes", encoding="utf-8")
    (a02 / "feb.csv").write_text("different bytes", encoding="utf-8")

    scan_engagement(engagement, today=DAY1)
    row = statuses(engagement)["A02"]
    assert row.file_count == 2                     # 3 files, 2 distinct
    assert row.status == Status.PARTIAL
    assert DUPLICATES_NOTE.format(n=1) in row.validation_notes


def test_pending_sync_status(engagement, monkeypatch):
    ghost = folder(engagement, "A01") / "cloud.pdf"
    ghost.write_bytes(b"unsynced placeholder bytes")
    monkeypatch.setattr(
        "tracker.validators.is_cloud_placeholder", lambda p: p.name == "cloud.pdf"
    )
    scan_engagement(engagement, today=DAY1)
    row = statuses(engagement)["A01"]
    assert row.status == Status.PENDING_SYNC
    assert SYNCING_NOTE.format(n=1) in row.validation_notes


def test_deleted_folder_reported_missing(engagement):
    folder(engagement, "A01").rmdir()
    scan_engagement(engagement, today=DAY1)
    row = statuses(engagement)["A01"]
    assert row.status == Status.MISSING
    assert reasons.NO_REQUEST_FOLDER.matches(row.validation_notes)


# --------------------------------------------------------------- unfiled ----


def test_strays_in_prepared_are_warnings_and_parked_files_are_not(engagement):
    # Parked documents are the index's record (with why they were parked);
    # the scan only warns about what nothing else knows: loose files in
    # Prepared/ and folders matching no request.
    prepared = engagement / PREPARED_DIR_NAME
    review = prepared / REVIEW_DIR_NAME
    (review / "scan0012.pdf").write_bytes(b"x" * 100)
    (prepared / "loose_notes.txt").write_text("oops", encoding="utf-8")
    rogue = prepared / "misc uploads"
    rogue.mkdir()
    (rogue / "something.pdf").write_bytes(b"x")

    report = scan_engagement(engagement, today=DAY1)
    assert report.warnings == [
        f"loose_notes.txt is loose in {PREPARED_DIR_NAME}/; it belongs in a request folder",
        f"folder 'misc uploads' in {PREPARED_DIR_NAME}/ matches no request (1 file(s) inside)",
    ]
    assert list(engagement.glob("*.xlsx")) == []                     # no second record

    (prepared / "loose_notes.txt").unlink()
    (rogue / "something.pdf").unlink()
    rogue.rmdir()
    assert scan_engagement(engagement, today=DAY2).warnings == []


def test_a_document_a_person_said_nothing_asks_for_is_not_a_warning_either(engagement):
    """A dismissal rewrites a row; the folder it leaves is the one it was.

    The index is the record of a parked document, with why it was parked and
    now who set it aside. A warning of its own would be the scan disagreeing
    with the index about a file the scan cannot see the decision on.
    """
    from tracker.filer import (
        NOT_REQUESTED,
        dismiss_review_file,
            read_index,
    )

    text_pdf(inbox_of(engagement) / "irs-notice.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    dismiss_review_file(engagement, parked.pbc_location, today=DAY1)

    report = scan_engagement(engagement, today=DAY2)
    assert report.warnings == []
    [row] = read_index(engagement)
    assert row.decision == NOT_REQUESTED
    assert (engagement / row.prepared_location).is_file()


def test_the_scan_report_carries_the_one_summary(engagement):
    text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec 2025")
    report = scan_engagement(engagement, today=DAY1)
    assert report.summary.received == 1
    assert report.summary.outstanding == 2
    assert report.summary.line == SUMMARY_SEPARATOR.join([f"{Status.MISSING}: 2", f"{Status.RECEIVED}: 1"])


# ------------------------------------------------------- lock and dry-run ----


def test_dry_run_writes_nothing(engagement):
    text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec 2025")
    report = scan_engagement(engagement, today=DAY1, dry_run=True)
    assert report.dry_run and report.recorded == 0
    assert report.updates["A01"].status == Status.RECEIVED  # facts computed
    assert statuses(engagement)["A01"].status == ""          # nothing written
    assert cache_rows(engagement) == ({}, {})                # no verdict, no memo
    assert not (engagement / LOCK_FILENAME).exists()


def test_fresh_lock_blocks_scan(engagement):
    (engagement / LOCK_FILENAME).write_text(f"pid={os.getpid()}", encoding="utf-8")
    with pytest.raises(ScanLockedError, match="another scan"):
        scan_engagement(engagement, today=DAY1)


def test_stale_lock_replaced_and_released(engagement):
    import os

    lock = engagement / LOCK_FILENAME
    lock.write_text(f"pid={os.getpid()}", encoding="utf-8")
    old = (dt.datetime.now() - dt.timedelta(seconds=STALE_LOCK_SECONDS + 1)).timestamp()
    os.utime(lock, (old, old))

    report = scan_engagement(engagement, today=DAY1)   # takes over stale lock
    assert report.recorded
    assert not lock.exists()                           # released afterwards


def test_the_scanner_reads_the_request_list_only_under_the_lock(engagement, monkeypatch):
    # A sort that finished between an early read and the lock would be
    # invisible to the scan, so the list is read after the lock is held.
    import tracker.scanner as scanner_module

    real = scanner_module.load_manifest

    def under_the_lock(path):
        assert (engagement / LOCK_FILENAME).exists(), "request list read before the lock was taken"
        return real(path)

    monkeypatch.setattr(scanner_module, "load_manifest", under_the_lock)
    assert scan_engagement(engagement, today=DAY1).recorded
    assert not (engagement / LOCK_FILENAME).exists()


def test_the_scan_leaves_its_verdicts_in_the_store_and_prunes_what_is_gone(engagement):
    from tracker.content_check import rules_fingerprint

    pdf = text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec 2025")
    scan_engagement(engagement, today=DAY1)
    memos, verdicts = cache_rows(engagement)
    [memo] = [memo for key, memo in memos.items() if "chase.pdf" in key]
    assert memo["digest"] in verdicts
    assert rules_fingerprint(ITEMS[0]) in verdicts[memo["digest"]]
    assert not (engagement / RETIRED_CACHE_FILENAME).exists()   # nothing of it in the folder

    pdf.unlink()
    scan_engagement(engagement, today=DAY2)            # prune removes the memo and its verdict
    memos, verdicts = cache_rows(engagement)
    assert not any("chase.pdf" in key for key in memos)
    assert memo["digest"] not in verdicts


def test_a_second_scan_over_an_unchanged_tree_hashes_nothing(engagement, monkeypatch):
    """Step 0's number: the memo makes an unchanged tree cost stats, not reads."""
    import tracker.content_check as content_check_module

    text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec 2025")
    (folder(engagement, "A02") / "jan.csv").write_text("jan data", encoding="utf-8")
    calls = {"n": 0}
    real = content_check_module.sha256_of

    def counted(path):
        calls["n"] += 1
        return real(path)

    # One patch is all there is to make: since decision 109 the scanner
    # hashes nothing of its own - a person's filing and the de-duplication
    # both go through the memo, which is this module's sha256_of.
    monkeypatch.setattr(content_check_module, "sha256_of", counted)
    scan_engagement(engagement, today=DAY1)
    assert calls["n"] >= 1                                   # the first pass hashes

    calls["n"] = 0
    report = scan_engagement(engagement, today=DAY2)
    assert calls["n"] == 0                                   # the second stats and hashes nothing
    assert report.updates["A01"].status == Status.RECEIVED


def test_a_file_that_vanishes_mid_scan_does_not_crash_the_scan(engagement, monkeypatch):
    # The sync client replaces a file between the directory listing and the
    # stat. The scan must finish and write; the row waits for the next run.
    import tracker.scanner as scanner_module

    ghost = folder(engagement, "A01") / "ghost.pdf"
    ghost.write_bytes(b"%PDF-1.4 " + b"x" * 9000)
    real_listing = scanner_module.iter_candidate_files

    def listing_then_vanish(path):
        found = real_listing(path)
        if ghost in found:
            ghost.unlink()
        return found

    monkeypatch.setattr(scanner_module, "iter_candidate_files", listing_then_vanish)
    monkeypatch.setattr("tracker.validators.iter_candidate_files", listing_then_vanish)

    report = scan_engagement(engagement, today=DAY1)
    assert report.recorded
    assert report.updates["A01"].status == Status.PENDING_SYNC


def test_raising_expected_count_after_received_names_the_real_change(engagement):
    text_pdf(folder(engagement, "A01") / "chase.pdf", "Chase Bank Statement Dec 2025")
    scan_engagement(engagement, today=DAY1)
    edit_row(engagement, "A01", expected_count=2)          # A01 Expected Count 1 -> 2
    report = scan_engagement(engagement, today=DAY2)
    update = report.updates["A01"]
    assert update.status == Status.PARTIAL
    assert update.received_date == DAY1
    assert REGRESSION_COUNT_RAISED.format(expected=2) in update.validation_notes
    assert REGRESSION_FILES_CHANGED not in update.validation_notes


def _regressed_from(day):
    """The regression sentence's head, as the note starts: the reason follows."""
    return REGRESSION_NOTE.format(status=Status.RECEIVED, date=day.isoformat(), why="")


def test_a_regressed_rows_reason_is_decided_once_and_carried(engagement):
    # Decision 108. A02 asked for 2 and got 2; one is taken away. The
    # pass it leaves Received says "files changed". Every pass after has
    # only the regressed count to compare with, and used to conclude that
    # the Expected Count had been raised - on every regressed row, from the
    # second pass on. The reason is decided once and carried.
    edit_row(engagement, "A02", expected_count=2)
    a02 = folder(engagement, "A02")
    (a02 / "jan.csv").write_text("jan data", encoding="utf-8")
    (a02 / "feb.csv").write_text("feb data", encoding="utf-8")
    scan_engagement(engagement, today=DAY1)
    assert statuses(engagement)["A02"].status == Status.RECEIVED

    (a02 / "feb.csv").unlink()
    left = scan_engagement(engagement, today=DAY2)
    note = left.updates["A02"].validation_notes
    assert note.startswith(_regressed_from(DAY1) + REGRESSION_FILES_CHANGED)
    assert REGRESSION_COUNT_RAISED.format(expected=2) not in note

    for day in (DAY2 + dt.timedelta(days=1), DAY2 + dt.timedelta(days=7)):
        again = scan_engagement(engagement, today=day)
        assert again.updates["A02"].validation_notes == note
        assert again.recorded == 0                   # nothing moved, nothing written
    assert statuses(engagement)["A02"].validation_notes == note


def test_a_raised_expected_count_says_so_on_the_pass_it_regresses_and_keeps_saying_so(engagement):
    edit_row(engagement, "A02", expected_count=2)
    a02 = folder(engagement, "A02")
    (a02 / "jan.csv").write_text("jan data", encoding="utf-8")
    (a02 / "feb.csv").write_text("feb data", encoding="utf-8")
    scan_engagement(engagement, today=DAY1)

    edit_row(engagement, "A02", expected_count=3)    # a person asks for one more
    raised = scan_engagement(engagement, today=DAY2)
    note = raised.updates["A02"].validation_notes
    assert note.startswith(_regressed_from(DAY1) + REGRESSION_COUNT_RAISED.format(expected=3))
    assert REGRESSION_FILES_CHANGED not in note

    again = scan_engagement(engagement, today=DAY2 + dt.timedelta(days=1))
    assert again.updates["A02"].validation_notes == note
    assert again.recorded == 0


def test_a_count_raised_after_a_regression_does_not_rewrite_why_the_row_left_received(engagement):
    # The sentence says why the row LEFT Received, and it left because a
    # file went. The raise is visible where the current count is said.
    edit_row(engagement, "A02", expected_count=2)
    a02 = folder(engagement, "A02")
    (a02 / "jan.csv").write_text("jan data", encoding="utf-8")
    (a02 / "feb.csv").write_text("feb data", encoding="utf-8")
    scan_engagement(engagement, today=DAY1)
    (a02 / "feb.csv").unlink()
    scan_engagement(engagement, today=DAY2)

    edit_row(engagement, "A02", expected_count=3)
    later = scan_engagement(engagement, today=DAY2 + dt.timedelta(days=1))
    note = later.updates["A02"].validation_notes
    assert note.startswith(_regressed_from(DAY1) + REGRESSION_FILES_CHANGED)
    assert REGRESSION_COUNT_RAISED.format(expected=3) not in note
    assert PARTIAL_NOTE.format(count=1, expected=3) in note


def test_a_regression_note_written_before_this_decision_is_read_as_files_changed(engagement):
    # A regressed row whose last note carries no regression sentence: the
    # count comparison would say "raised" (2 files now, 1 recorded, 3
    # expected, nothing failed), and nobody raised anything.
    from tests.conftest import seed_statuses
    from tracker.manifest import StatusUpdate

    seed_statuses(engagement, {"A02": StatusUpdate(
        status=Status.PARTIAL, file_count=1, received_date=DAY1,
        validation_notes=PARTIAL_NOTE.format(count=1, expected=3),
    )})
    a02 = folder(engagement, "A02")
    (a02 / "jan.csv").write_text("jan data", encoding="utf-8")
    (a02 / "feb.csv").write_text("feb data", encoding="utf-8")

    note = scan_engagement(engagement, today=DAY2).updates["A02"].validation_notes
    assert note.startswith(_regressed_from(DAY1) + REGRESSION_FILES_CHANGED)
    assert REGRESSION_COUNT_RAISED.format(expected=3) not in note


def test_accepted_means_received_with_a_date(engagement):
    # Decision 2: Accepted = treat as Received despite the rules. The status
    # column, the date and every count that reads the column agree.
    scan_engagement(engagement, today=DAY1)          # A01 Missing: no file at all
    edit_row(engagement, "A01", manual_override=Override.ACCEPTED,
             override_reason="Client confirmed this is the final version")
    report = scan_engagement(engagement, today=DAY2)
    update = report.updates["A01"]
    assert update.status == Status.RECEIVED
    assert update.received_date == DAY2
    assert update.validation_notes.startswith(OVERRIDE_NOTE.format(override=Override.ACCEPTED))
    assert statuses(engagement)["A01"].status == Status.RECEIVED
    # Stamped once: a later scan keeps the first date.
    assert scan_engagement(engagement, today=DAY2 + dt.timedelta(days=3)).updates["A01"].received_date == DAY2


def test_not_applicable_rows_are_named_so_counts_can_leave_them_out(engagement):
    edit_row(engagement, "B01", manual_override=Override.NOT_APPLICABLE)
    report = scan_engagement(engagement, today=DAY1)
    assert report.summary.not_applicable == 1
    assert report.summary.total == 2


def test_the_first_date_everything_passed_is_what_the_next_scan_measures_from(engagement):
    # The Received Date the first scan stamped is "the first date all
    # validations passed"; the second carries it rather than re-stamping
    # today. And when the file is then gone, the row regresses from
    # Received - with its date and a note - instead of landing as plain
    # Missing. Nothing here waits for anything (decision 103): a scan
    # records, and nothing a person has open can hold that up.
    a01 = folder(engagement, "A01")
    text_pdf(a01 / "chase.pdf", "Chase Bank Statement Dec 2025")

    first = scan_engagement(engagement, today=DAY1)
    assert first.recorded and first.updates["A01"].received_date == DAY1
    second = scan_engagement(engagement, today=DAY2)
    assert second.recorded == 0                   # nothing changed, nothing recorded
    assert second.updates["A01"].received_date == DAY1

    (a01 / "chase.pdf").unlink()
    third = scan_engagement(engagement, today=DAY2)
    assert third.recorded
    row = statuses(engagement)["A01"]
    assert row.status == Status.MISSING and row.received_date == DAY1
    assert REGRESSION_NOTE.format(status=Status.RECEIVED, date=DAY1.isoformat(), why="").rstrip("; ") \
        in row.validation_notes


def test_a_received_file_the_sync_client_dehydrated_is_not_a_regression(engagement, monkeypatch):
    # OneDrive "free up space" turns a Received file into a placeholder.
    # The row waits for the bytes; it did not lose the document.
    received = folder(engagement, "A01") / "chase.pdf"
    text_pdf(received, "Chase Bank Statement Dec 2025")
    scan_engagement(engagement, today=DAY1)
    assert statuses(engagement)["A01"].status == Status.RECEIVED

    monkeypatch.setattr("tracker.validators.is_cloud_placeholder", lambda p: p.name == "chase.pdf")
    scan_engagement(engagement, today=DAY2)
    row = statuses(engagement)["A01"]
    assert row.status == Status.PENDING_SYNC and row.received_date == DAY1
    assert REGRESSION_FILES_CHANGED not in row.validation_notes
    assert SYNCING_NOTE.format(n=1) in row.validation_notes


def test_an_empty_note_replaces_the_old_one(engagement):
    # A blank note must reach the record as a blank. "request folder not found"
    # must not outlive the folder, or the reminder holds the row back for ever.
    folder(engagement, "A01").rmdir()
    scan_engagement(engagement, today=DAY1)
    assert reasons.NO_REQUEST_FOLDER.matches(statuses(engagement)["A01"].validation_notes)
    scaffold_engagement(engagement)                      # the next pass creates it
    scan_engagement(engagement, today=DAY2)
    assert statuses(engagement)["A01"].validation_notes == ""


def test_a_document_a_person_filed_is_not_second_guessed_by_the_rules(engagement):
    # A person filed it from Needs Review; the row's required keyword is not
    # in it. Their decision stands: Received, not "wrong document" and a
    # client asked for the right file.
    from tests.conftest import sort
    from tracker.filer import assign_review_file
    from tracker.scanner import ACCEPTED_NOTE

    text_pdf(inbox_of(engagement) / "statement.pdf", "Annual account statement 2025 interest paid")
    parked = sort(engagement, today=DAY1).review[0]
    assign_review_file(engagement, parked.pbc_location, "A01", today=DAY1)
    scan_engagement(engagement, today=DAY1)
    row = statuses(engagement)["A01"]
    assert row.status == Status.RECEIVED and row.file_count == 1
    assert ACCEPTED_NOTE.format(n=1) in row.validation_notes


def test_a_persons_acceptance_covers_only_the_bytes_they_filed(engagement):
    # A person filed one document, and then a different one came to sit
    # under the canonical name theirs had. The acceptance was for their
    # bytes, not for that name: the newcomer faces the rules.
    #
    # Until decision 92 the newcomer arrived the way a client sends one -
    # a blank scan called "Chase scan.pdf", which the router filed on its
    # name. Nothing is filed on a name any more, and anything the rules
    # do route into that folder passes the same rules the scan applies, so
    # the only way a stranger reaches that name is a person putting it
    # there. That is what this writes, and the claim is unchanged.
    from tests.conftest import sort
    from tracker.filer import assign_review_file

    text_pdf(inbox_of(engagement) / "statement.pdf", "Annual account statement 2025 interest paid")
    parked = sort(engagement, today=DAY1).review[0]
    filed = assign_review_file(engagement, parked.pbc_location, "A01", today=DAY1).entry
    (engagement / filed.prepared_location).unlink()
    text_pdf(engagement / filed.prepared_location, "Some other bank's statement for 2025")
    scan_engagement(engagement, today=DAY2)
    row = statuses(engagement)["A01"]
    assert row.status != Status.RECEIVED and "filed here by a person" not in row.validation_notes


# ------------------ what the record says about a working copy (d109) ----


def copy_moved_events(engagement):
    return [e for e in ledger.read_events(engagement)
            if e[ledger.EVENT_KEY] == ledger.COPY_MOVED]


def a_filed_pdf(engagement, text="Chase Bank Statement Dec 2025"):
    """One document sorted and scanned the ordinary way: A01, Received."""
    from tests.conftest import sort

    text_pdf(inbox_of(engagement) / "chase.pdf", named_page(text))
    filed = sort(engagement, today=DAY1).filed[0]
    scan_engagement(engagement, today=DAY1)
    assert statuses(engagement)["A01"].status == Status.RECEIVED
    return filed


def test_a_moved_copys_request_reads_missing_with_the_firm_side_note_and_the_wanderer_is_not_counted_elsewhere(
        engagement):
    """The whole of decision 109 from the scan's side: the request whose copy
    was dragged away is Missing, truthfully, and says whose fault that is;
    the request the copy was dragged into counts nothing it did not earn."""
    from tests.conftest import sort
    from tracker.filer import FILE_MOVED, moved_to, read_index

    filed = a_filed_pdf(engagement)
    home = engagement / filed.prepared_location
    home.rename(folder(engagement, "A02") / home.name)      # dragged by hand

    sort(engagement, today=DAY2)
    report = scan_engagement(engagement, today=DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED
    moved = report.updates["A01"]
    assert moved.status == Status.MISSING and moved.file_count == 0
    assert moved.received_date == DAY1
    assert moved.validation_notes.startswith(_regressed_from(DAY1) + REGRESSION_FILES_CHANGED)
    assert reasons.FILE_MOVED.matches(moved.validation_notes)
    assert f"{filed.prepared_location} -> {moved_to(row)}" in moved.validation_notes

    elsewhere = report.updates["A02"]
    assert elsewhere.file_count == 0 and elsewhere.status == Status.MISSING
    assert reasons.find(elsewhere.validation_notes) is None   # not counted, and not refused either


def test_a_filed_copy_replaced_by_a_different_passing_file_stays_received_with_copy_changed_and_a_warning(
        engagement):
    """Decision 3 extended: the status is what the files earn, and the row
    says the file is not the one the record filed there - which no count
    can say, because the newcomer passes every rule."""
    from tests.conftest import sort

    filed = a_filed_pdf(engagement)
    home = engagement / filed.prepared_location
    home.unlink()
    text_pdf(home, "Chase Bank Statement Nov 2025, the other account")

    sort(engagement, today=DAY2)
    report = scan_engagement(engagement, today=DAY2)

    row = report.updates["A01"]
    assert row.status == Status.RECEIVED and row.file_count == 1
    assert row.received_date == DAY1
    assert reasons.COPY_CHANGED.matches(row.validation_notes)
    assert home.name in row.validation_notes
    assert report.warnings == [
        f"{home.name}: {reasons.COPY_CHANGED.format(listed=home.name)}"
    ]
    assert copy_moved_events(engagement) == []      # nothing moved: the bytes are simply not the row's


def test_a_filed_copy_replaced_by_a_failing_file_is_decision_threes_regression_and_says_copy_changed(
        engagement):
    from tests.conftest import sort

    filed = a_filed_pdf(engagement)
    home = engagement / filed.prepared_location
    home.unlink()
    text_pdf(home, "Wells Fargo Statement Dec 2025")         # A01 asks for Chase

    sort(engagement, today=DAY2)
    report = scan_engagement(engagement, today=DAY2)

    row = report.updates["A01"]
    assert row.status == Status.FAILED and row.file_count == 0
    assert row.validation_notes.startswith(_regressed_from(DAY1) + REGRESSION_FILES_CHANGED)
    assert reasons.COPY_CHANGED.matches(row.validation_notes)
    assert reasons.WRONG_DOCUMENT.matches(row.validation_notes)   # both facts, on one row


def test_an_unrecorded_file_in_a_request_folder_is_counted_and_said(engagement):
    """The scanner's contract since its first row: a request's status is what
    its folder holds. A file a person can see going uncounted would be a lie
    in the other direction, so it counts - and the pass says every pass that
    nothing on the record put it there."""
    from tests.conftest import sort
    from tracker.filer import UNRECORDED_COPY

    stray = text_pdf(folder(engagement, "A01") / "someone dragged this.pdf",
                     "Chase Bank Statement Dec 2025")
    location = stray.relative_to(engagement).as_posix()

    report = sort(engagement, today=DAY1)
    scanned = scan_engagement(engagement, today=DAY1)

    assert [e.error for e in report.attention] == [UNRECORDED_COPY.format(location=location)]
    assert scanned.updates["A01"].status == Status.RECEIVED
    assert scanned.updates["A01"].file_count == 1
    assert scanned.warnings == []                 # it is in a request folder, not loose
    assert stray.is_file()


def test_the_scans_memo_survives_for_parked_copies_and_strays(engagement, monkeypatch):
    """The prune used to keep only what a request's folder held, so a parked
    copy and a file nothing claims were forgotten every scan and read again
    every pass. Every file in the firm's folder keeps its memo."""
    import tracker.content_check as content_check_module
    from tests.conftest import sort

    text_pdf(inbox_of(engagement) / "irs-notice.pdf", "nothing the rules recognise")
    stray = text_pdf(folder(engagement, "A01") / "someone dragged this.pdf",
                     "Chase Bank Statement Dec 2025")
    parked = sort(engagement, today=DAY1).review[0]
    scan_engagement(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY2)

    memos, _verdicts = cache_rows(engagement)
    parked_name = parked.prepared_location.rsplit("/", 1)[-1].lower()
    assert any(parked_name in key for key in memos), sorted(memos)
    assert any(stray.name.lower() in key for key in memos), sorted(memos)

    calls = {"n": 0}
    real = content_check_module.sha256_of

    def counted(path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setattr(content_check_module, "sha256_of", counted)
    scan_engagement(engagement, today=DAY2)
    assert calls["n"] == 0


def test_a_person_filed_copy_is_proved_through_the_memo(engagement, monkeypatch):
    """Decision 58's reading of a person's filing - the acceptance holds only
    while the bytes do - now goes through the memo like every other hash
    under the firm's folder, so a second scan over an unchanged tree reads
    nothing at all."""
    import tracker.content_check as content_check_module
    from tests.conftest import sort
    from tracker.filer import assign_review_file
    from tracker.scanner import ACCEPTED_NOTE

    text_pdf(inbox_of(engagement) / "statement.pdf",
             "Annual account statement 2025 interest paid")
    parked = sort(engagement, today=DAY1).review[0]
    assign_review_file(engagement, parked.pbc_location, "A01", today=DAY1)
    first = scan_engagement(engagement, today=DAY1)
    assert ACCEPTED_NOTE.format(n=1) in first.updates["A01"].validation_notes

    calls = {"n": 0}
    real = content_check_module.sha256_of

    def counted(path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setattr(content_check_module, "sha256_of", counted)
    again = scan_engagement(engagement, today=DAY2)
    assert calls["n"] == 0
    assert ACCEPTED_NOTE.format(n=1) in again.updates["A01"].validation_notes
