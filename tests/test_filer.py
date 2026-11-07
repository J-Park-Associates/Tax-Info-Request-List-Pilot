"""Tests for tracker/filer.py — sorting the client's drop folder.

The promises being tested: the client's original is preserved byte-for-byte
under its own name in PBC, a renamed working copy appears in Prepared, every
decision is recorded, and running twice changes nothing.

Since decision 102 "recorded" means the engagement's own record and the
store, in one transaction: there is no index workbook, no snapshot sidecar
and nothing deferred, so the tests that proved that machinery are gone with
it, and since decision 104 so is the migration that read a legacy folder's
workbook once. What is here is the claim that every decision is one call
and one transaction, and that a rules edit saved in the app is what the
next pass files on.
"""

import datetime as dt
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tests import filer_helpers
from tests.builders import (
    BUSINESS,
    DAY1,
    DAY2,
    FATHER,
    FOLDER_BELOW,
    ITEMS,
    LLC_PEOPLE,
    LONG_PERIOD,
    OVER,
    ROOM_ITEMS,
    SCHWAB_146,
    TEST_CLIENT,
    TIGHT_PERIOD,
    _consolidated_return,
    cache_rows,
    drop,
    engagement_fixture,
    feeding,
    killed_at_the_record,
    link_to,
    make_engagement,
    named_page,
    no_room_prepared,
    no_room_return,
    original_at,
    sort,
    sort_all,
    tight_return,
    with_the_long_period,
)
from tests.filer_helpers import (
    DAY3,
    JOHN,
    MORTGAGE,
    _a_pass,
    _asked,
    _catalog_w2,
    _filed_1098,
    _forge_line,
    _only_the_review_folder,
    _review_folder_files,
    _status,
    click,
    conserved,
    counted_records,
    counting_hashes,
    digests_under,
    drag,
    events_named,
    files_under,
    kept_files,
    killed_after_ops,
    killed_after_the_move,
    killed_at_the_intent,
    moves_made,
    open_intents,
    originals,
    parked_notice,
    prepared,
    review_dir,
    rows_rest_at_home,
    seq_of,
)
from tests.samples import text_pdf
from tracker import checkpoint, ledger, reasons, store, store_check
from tracker.filer import (
    FilingError,
)
from tracker.fsio import TEMP_SUFFIX
from tracker.index import DUPLICATE, FILED, NEEDS_REVIEW, ensure, read_index
from tracker.layout import household_of, inbox_of, locate, location_of, originals_of, root_of
from tracker.manifest import (
    RequestItem,
    load_engagement_info,
    load_manifest,
    save_rules,
)
from tracker.names import propose_spellings
from tracker.records import (
    RULE_NAME,
    WHERE_FIRST_PAGE,
    Evidence,
    Person,
    ledger_key,
    parse_evidence,
    rule_from_json,
    rule_to_json,
)
from tracker.router import UNMATCHED
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    README_NAME,
    REVIEW_DIR_NAME,
)

engagement = engagement_fixture(ITEMS)


# ------------------------------------------------------------- the happy path ----


def test_file_is_sorted_renamed_and_indexed(engagement):
    original = drop(engagement, "scan0012.pdf", "Form W-2 Wage and Tax Statement 2025")
    before = original.read_bytes()

    report = sort(engagement, today=DAY1)

    # Original: moved out of the drop zone, name and bytes untouched.
    assert not original.exists()
    kept = originals(engagement) / "scan0012.pdf"
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
    assert entry.pbc_location == original_at(engagement, "scan0012.pdf")
    assert entry.pbc_location.startswith("../")           # it crosses the two trees
    assert (originals(engagement) / "scan0012.pdf").is_file()
    assert entry.prepared_location.endswith("A01 - W-2 Wage Statements - TY2025.pdf")

    rows = read_index(engagement)
    assert [r.original_name for r in rows] == ["scan0012.pdf"]
    assert rows[0].digest == entry.digest


def test_second_file_for_the_same_request_is_numbered(engagement):
    drop(engagement, "john w2.pdf", "Form W-2 Wage and Tax Statement 2025 John")
    drop(engagement, "jane w2.pdf", "Form W-2 Wage and Tax Statement 2025 Jane")
    sort(engagement, today=DAY1)

    names = sorted(p.name for p in prepared(engagement, "A01").iterdir())
    assert names == [
        "A01 - W-2 Wage Statements - TY2025 (2).pdf",
        "A01 - W-2 Wage Statements - TY2025.pdf",
    ]


def test_client_subfolders_are_flattened(engagement):
    nested = inbox_of(engagement) / "tax stuff"
    nested.mkdir()
    text_pdf(nested / "w2.pdf", named_page("Form W-2 Wage and Tax Statement 2025"))

    report = sort(engagement, today=DAY1)
    assert len(report.filed) == 1
    assert (originals(engagement) / "w2.pdf").exists()


# ----------------------------------- a subfolder of the drop (decision 147) ----
# The year folder stays flat (decision 125): a file from a subfolder of the
# drop moves in under its own name. It is numbered only where another file
# has that name, the file at the top of the inbox is the one that keeps it,
# and the row says which of the client's subfolders the file came from - in
# its own Client's Subfolder column since decision 190, never in the Reason.

def came_from(folder):
    """The sentence a row's Reason ended with, before decision 190, when its
    file came out of a subfolder of the drop (decision 147, ruling 4). It
    is the card's label now (``api.CAME_FROM_SUBFOLDER``), and no Reason
    carries it."""
    return f"came from the client's subfolder '{folder}'"


def test_a_subfolder_file_keeps_its_name_when_nothing_else_has_it(engagement):
    nested = inbox_of(engagement) / "Bank statements" / "2025"
    nested.mkdir(parents=True)
    text_pdf(nested / "w2.pdf", named_page("Form W-2 Wage and Tax Statement 2025"))

    [row] = sort(engagement, today=DAY1).filed

    assert [p.name for p in originals(engagement).iterdir()] == ["w2.pdf"]
    assert row.pbc_location == original_at(engagement, "w2.pdf")
    assert row.original_name == "w2.pdf"
    # The path below the inbox, the way the client sees it in Explorer - in
    # its own column, and not a word of it in the Reason (decision 190).
    assert row.subfolder == "Bank statements\\2025"
    assert "Bank statements" not in row.reason
    assert read_index(engagement)[0].subfolder == row.subfolder     # the record's, not the report's


@pytest.mark.skipif(sys.platform == "win32", reason="Windows cannot name a folder with ':' in it")
def test_a_subfolder_named_with_a_windows_illegal_character_is_recorded_with_an_underscore_and_the_pass_completes(
        engagement):
    """Decision 190's review of the port, S2. On Linux or macOS a client can
    name an inbox folder ``Q1: bank``. The filer recorded it raw and the
    store's admission refused it, after the original had already moved, so
    the pass raised. Both now use layout.recorded_subfolder_part: the row
    says ``Q1_ bank``, the store admits it, and the pass files the file."""
    nested = inbox_of(engagement) / "Q1: bank"
    nested.mkdir(parents=True)
    text_pdf(nested / "w2.pdf", named_page("Form W-2 Wage and Tax Statement 2025"))

    [row] = sort(engagement, today=DAY1).filed

    assert row.subfolder == "Q1_ bank", row
    assert [p.name for p in originals(engagement).iterdir()] == ["w2.pdf"]
    assert [(e.original_name, e.subfolder) for e in read_index(engagement)] == [("w2.pdf", "Q1_ bank")]


def test_a_different_file_of_the_same_name_is_the_one_numbered_and_the_row_names_its_subfolder(engagement):
    """``Scans`` sorts before ``W2.pdf`` on Windows and POSIX alike - a
    case-folded path order and a plain one agree - so the old walk moved
    the subfolder's copy first and the top-level file was the one
    numbered. The order is now the inbox's own: top level first."""
    import hashlib

    top = drop(engagement, "W2.pdf", "Form W-2 Wage and Tax Statement 2025 Employer A")
    nested = inbox_of(engagement) / "Scans"
    nested.mkdir()
    inner = text_pdf(nested / "W2.pdf", named_page("Form W-2 Wage and Tax Statement 2025 Employer B"))
    top_digest = hashlib.sha256(top.read_bytes()).hexdigest()
    inner_digest = hashlib.sha256(inner.read_bytes()).hexdigest()
    assert top_digest != inner_digest

    report = sort(engagement, today=DAY1)

    rows = {row.digest: row for row in report.filed}
    assert set(rows) == {top_digest, inner_digest}
    assert rows[top_digest].pbc_location == original_at(engagement, "W2.pdf")
    assert rows[inner_digest].pbc_location == original_at(engagement, "W2 (2).pdf")
    assert rows[top_digest].subfolder == ""
    assert rows[inner_digest].subfolder == "Scans"
    assert came_from("Scans") not in rows[inner_digest].reason
    assert rows[inner_digest].original_name == "W2.pdf"           # what the client called it


def test_an_identical_copy_from_a_subfolder_is_a_duplicate_as_before(engagement):
    top = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    nested = inbox_of(engagement) / "tax stuff"
    nested.mkdir()
    (nested / "w2.pdf").write_bytes(top.read_bytes())

    report = sort(engagement, today=DAY1)

    [filed] = report.filed
    [dup] = report.duplicates
    assert filed.pbc_location == original_at(engagement, "w2.pdf")
    assert filed.subfolder == ""
    # Both preserved; the copy from the subfolder is the one numbered, and
    # it is the duplicate it always was (decision 111).
    assert dup.decision == DUPLICATE
    assert dup.pbc_location == original_at(engagement, "w2 (2).pdf")
    assert "identical to w2.pdf" in dup.reason
    assert dup.subfolder == "tax stuff" and "tax stuff" not in dup.reason
    assert len(list(prepared(engagement, "A01").iterdir())) == 1


def test_a_client_subfolder_named_like_a_marker_changes_nothing(tmp_path):
    """Decision 190, B-4. A client's folder is the client's words: one called
    "not allowed" once turned a password-protected W-2 into a file-type ask,
    and one called "Google Docs shortcut" into an export ask, because the
    folder's name was a clause of the Reason and the reminder searched it.
    The same locked file, dropped at the top and inside each of these
    folders, now gets the same code, the same card and the same letter; the
    folder is in its own column and nowhere in the Reason."""
    from tests.builders import DROPPED, locked
    from tracker.reminder import draft_reminder
    from tracker.review import shortlist_for
    from tracker.scanner import scan_engagement

    seen = []
    for n, folder in enumerate(("", "not allowed", "Google Docs shortcut", "Scans")):
        engagement = make_engagement(tmp_path / f"root{n}", DROPPED)
        shared = inbox_of(engagement) / folder if folder else inbox_of(engagement)
        shared.mkdir(parents=True, exist_ok=True)
        locked("W-2 Jane Smith 2025.pdf")(shared)
        sort(engagement, today=DAY1)
        scan_engagement(engagement, today=DAY1)

        [row] = [e for e in read_index(engagement) if e.decision == NEEDS_REVIEW]
        assert row.subfolder == folder
        assert not folder or folder not in row.reason
        draft = draft_reminder(engagement)
        seen.append((
            row.code, row.reason,
            [(s.identifier, s.reason) for s in shortlist_for(row, DROPPED)],
            [(f.item.identifier, f.reason) for f in draft.held],
            [line.item.identifier for line in draft.lines], draft.body,
        ))
    assert seen[0][0] == reasons.PASSWORD_PROTECTED.code
    assert all(one == seen[0] for one in seen), seen


def test_every_row_a_pass_parks_has_a_code(engagement):
    """Decision 190: every sentence that parks a row has a code, and the
    row carries it - a locked PDF, a page that matches nothing, a type no
    request takes, a zip that will not open and an upload that arrived
    empty each park with a code the reader can read, and none with ``""``,
    which means a row written before 190."""
    from tests.builders import locked

    inbox = inbox_of(engagement)
    locked("W-2 2025.pdf")(inbox)
    drop(engagement, "notes.pdf", "A shopping list with nothing on it", who="")
    (inbox / "setup.exe").write_bytes(b"MZ" * 4000)
    (inbox / "docs.zip").write_bytes(b"PK\x03\x04 not a zip at all" * 200)
    (inbox / "empty.pdf").write_bytes(b"%PDF")

    sort(engagement, today=DAY1)

    parked = {row.original_name: row.code for row in read_index(engagement)
              if row.decision == NEEDS_REVIEW}
    assert set(parked) == {"W-2 2025.pdf", "notes.pdf", "setup.exe", "docs.zip", "empty.pdf"}
    assert all(parked.values()), parked
    assert parked["W-2 2025.pdf"] == reasons.PASSWORD_PROTECTED.code
    assert parked["docs.zip"] == reasons.CONTAINER_DAMAGED.code


def test_the_subfolder_is_removed_once_empty(engagement):
    nested = inbox_of(engagement) / "a" / "b"
    nested.mkdir(parents=True)
    text_pdf(nested / "w2.pdf", named_page("Form W-2 Wage and Tax Statement 2025"))

    sort(engagement, today=DAY1)

    assert not (inbox_of(engagement) / "a").exists()
    assert [p.name for p in inbox_of(engagement).iterdir()] == [README_NAME]


def test_a_name_a_deleted_original_left_is_not_reused_for_a_new_drop(engagement):
    """Audit F-1 (decision 147, ruling 9). The client deletes the wrong W-2
    from the year's folder and drops the corrected one under the same
    name. The freed name was reused, the new row took the old row's
    identity and the old row vanished from every reader; its working copy
    was then an unrecorded copy for ever. A name a row still names is
    taken, so the new one rests beside it and the old row goes on saying
    it is missing - the truthful state."""
    from tracker.filer import MISSING_IN_PBC, UNRECORDED_COPY

    drop(engagement, "W2.pdf", "Form W-2 Wage and Tax Statement 2025 the wrong one")
    [first] = sort(engagement, today=DAY1).filed
    (originals(engagement) / "W2.pdf").unlink()
    drop(engagement, "W2.pdf", "Form W-2 Wage and Tax Statement 2025 the corrected one")

    [second] = sort(engagement, today=DAY2).filed
    third = sort(engagement, today=DAY3)

    assert second.pbc_location == original_at(engagement, "W2 (2).pdf")
    assert second.digest != first.digest
    rows = read_index(engagement)
    assert [(r.pbc_location, r.digest) for r in rows] == [
        (first.pbc_location, first.digest), (second.pbc_location, second.digest)]
    assert [e.error for e in third.attention] == [
        MISSING_IN_PBC.format(location=first.pbc_location, received=DAY1.isoformat())]
    unrecorded = UNRECORDED_COPY.format(location="")      # " is not on the record: ..."
    assert not any(unrecorded in e.error for e in third.attention + third.errors)


def test_an_unrecorded_copys_advice_never_sends_it_to_a_clients_folder():
    """Decision 184: a file nobody can account for is very often another
    client's, and a document put in a client's folder is published to that
    household. So the warning a person reads every pass says to confirm
    whose it is first, and names a client's folder only to forbid it. A
    detector of the one known wording, not a boundary."""
    from tracker.filer import UNRECORDED_COPY

    assert "confirm whose it is" in UNRECORDED_COPY
    assert UNRECORDED_COPY.count("client's folder") == UNRECORDED_COPY.count("never a client's folder")


def test_the_same_bytes_dropped_back_under_a_deleted_originals_name_rest_under_it(engagement):
    """Ruling 9's one exception, as decision 157 carries it: the bytes are
    that row's own, so it is the original coming back and it rests under
    its own name - put back there by the pass, with no new row
    (``filer._put_back_home``), where 147 left it to the numbering."""
    page = drop(engagement, "W2.pdf", "Form W-2 Wage and Tax Statement 2025")
    body = page.read_bytes()
    sort(engagement, today=DAY1)
    (originals(engagement) / "W2.pdf").unlink()
    (inbox_of(engagement) / "W2.pdf").write_bytes(body)

    sort(engagement, today=DAY2)

    assert [p.name for p in originals(engagement).iterdir()] == ["W2.pdf"]
    assert (originals(engagement) / "W2.pdf").read_bytes() == body


# --------------------------------------------------------------- needs review ----


def test_unroutable_file_is_preserved_and_parked(engagement):
    # A readable page nothing asks for: the rules read it and no request
    # wanted it, which is a different answer from "nothing could be read".
    original = drop(engagement, "vacation.pdf", "Photos from Maui, the hotel pool and the beach at sunset")
    before = original.read_bytes()

    report = sort(engagement, today=DAY1)

    assert (originals(engagement) / "vacation.pdf").read_bytes() == before
    review = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    assert (review / "vacation.pdf").exists()
    (entry,) = report.review
    assert entry.decision == NEEDS_REVIEW
    assert UNMATCHED in entry.reason
    assert not report.filed


def test_review_copies_keep_the_clients_own_name(engagement):
    drop(engagement, "IMG_4021.pdf", "unreadable receipt")
    sort(engagement, today=DAY1)
    review = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    assert [p.name for p in review.iterdir()] == ["IMG_4021.pdf"]


# ------------------------------------------------------------------ re-running ----


def test_rerunning_changes_nothing(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    snapshot = {
        p: p.read_bytes()
        for p in (engagement / PREPARED_DIR_NAME).rglob("*") if p.is_file()
    }

    second = sort(engagement, today=DAY2)

    assert second.handled == 0
    assert {
        p: p.read_bytes()
        for p in (engagement / PREPARED_DIR_NAME).rglob("*") if p.is_file()
    } == snapshot


def test_same_document_dropped_twice_is_kept_but_filed_once(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    # Client re-sends the identical document under a different name.
    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025")

    report = sort(engagement, today=DAY2)

    (dup,) = report.duplicates
    assert dup.decision == DUPLICATE
    assert "identical to w2.pdf" in dup.reason
    # Preserved, never deleted...
    assert (originals(engagement) / "w2 again.pdf").exists()
    # ...but not filed a second time.
    assert len(list(prepared(engagement, "A01").iterdir())) == 1


def test_name_collision_in_pbc_never_overwrites(engagement):
    drop(engagement, "statement.pdf", "Form W-2 Wage and Tax Statement 2025 John")
    sort(engagement, today=DAY1)
    drop(engagement, "statement.pdf", "Form W-2 Wage and Tax Statement 2025 Jane")

    sort(engagement, today=DAY2)

    kept = sorted(p.name for p in originals(engagement).iterdir())
    assert kept == ["statement (2).pdf", "statement.pdf"]


# ------------------------------------------------------------------- guarded ----


def test_placeholders_are_left_where_they_are(engagement, monkeypatch):
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module

    waiting = drop(engagement, "big.pdf", "Form W-2 Wage and Tax Statement 2025")
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "is_cloud_placeholder", lambda p: True)

    report = sort(engagement, today=DAY1)

    assert report.waiting == [waiting]
    assert waiting.exists()                       # untouched, still syncing
    assert not any(originals(engagement).iterdir())


def test_sync_junk_is_ignored(engagement):
    junk = inbox_of(engagement) / "w2.pdf.tmp.driveupload"
    junk.write_bytes(b"partial upload")

    report = sort(engagement, today=DAY1)

    assert report.handled == 0
    assert junk.exists()                          # not ours to move or delete


def test_pbc_contents_are_never_re_sorted(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    # The originals now sitting in PBC must not look like new drops.
    assert sort(engagement, today=DAY2).handled == 0


def test_dry_run_moves_nothing(engagement):
    original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    report = sort(engagement, today=DAY1, dry_run=True)

    assert len(report.filed) == 1                 # it still tells you the plan
    assert original.exists()
    assert not any(originals(engagement).iterdir())
    assert ledger.read_events(engagement)[1:] == []      # nothing after the create
    assert cache_rows(engagement) == ({}, {})            # and no verdict, no memo


def test_filing_leaves_verdicts_the_scan_reuses(engagement, monkeypatch):
    # Route once, scan once, read the document once: the router's verdicts
    # are the scanner's, keyed by content so the working copy is a hit.
    from tests.builders import counting_extractor
    from tracker.scanner import scan_engagement

    calls = counting_extractor(monkeypatch)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1, dry_run=True)
    assert cache_rows(engagement) == ({}, {})               # a dry run writes nothing
    assert sort(engagement, today=DAY1).handled == 1
    _memos, verdicts = cache_rows(engagement)
    assert verdicts                                         # the run left its verdicts (by digest)
    assert calls["n"] == 2                                  # the preview and the run

    report = scan_engagement(engagement, today=DAY1)
    assert report.updates["A01"].file_count == 1
    assert calls["n"] == 2                                  # the scan read nothing again


def test_a_sort_that_raises_still_keeps_its_verdicts(engagement, monkeypatch):
    """SPEC-161 ruling 1 (E-4): the sort raises after it read the drop. The
    rows are recorded as always, and now the verdicts are kept too, so the
    next pass does not read the document again."""
    import tracker.filer as filer
    from tests.builders import counting_extractor

    calls = counting_extractor(monkeypatch)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    def surprise(*args, **kwargs):
        raise RuntimeError("after the reading")

    monkeypatch.setattr(filer, "_unaccounted_in_opened", surprise)
    with pytest.raises(RuntimeError, match="after the reading"):
        sort(engagement, today=DAY1)
    _memos, verdicts = cache_rows(engagement)
    assert verdicts, "the verdict reached before the exception is kept"
    assert calls["n"] == 1


def test_each_drops_verdicts_are_kept_before_the_next_drop_is_read(engagement, monkeypatch):
    """Saved per drop (decision 189): when the second drop is read, the
    first drop's verdicts are already in the store."""
    import tracker.content_check as content_check

    drop(engagement, "a.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "b.pdf", "Form 1099-INT Interest Income 2025")
    real, seen = content_check.extract, []

    def looking_at_the_store(path, **kwargs):
        seen.append(len(cache_rows(engagement)[1]))
        return real(path, **kwargs)

    monkeypatch.setattr(content_check, "extract", looking_at_the_store)
    sort(engagement, today=DAY1)
    assert seen[0] == 0 and seen[1] >= 1


def test_a_sort_past_its_deadline_takes_no_file_and_leaves_each_where_it_was(engagement):
    """Decision 189: the household's time is checked before each file that
    would need a new judgment. Past it the sort takes no such file: every
    new drop stays in the inbox, unrecorded, and the first own return's
    report says how many."""
    from tracker import ocr
    from tracker.filer import file_household_drops
    from tracker.locking import engagement_lock

    drop(engagement, "a.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "b.pdf", "Form 1099-INT Interest Income 2025")
    with engagement_lock(engagement):
        reports = file_household_drops(inbox_of(engagement), originals_of(engagement),
                                       own=[engagement], today=DAY1,
                                       deadline=ocr.awake_clock() - 1)
    report = reports[engagement]
    assert report.unreached == 2 and report.handled == 0
    assert (inbox_of(engagement) / "a.pdf").is_file() and (inbox_of(engagement) / "b.pdf").is_file()
    assert read_index(engagement) == []

    assert sort(engagement, today=DAY1).handled == 2, "the next pass takes them"


def test_a_retired_cache_file_is_never_read_and_is_not_the_passs_to_remove(engagement, monkeypatch):
    """Decision 107: nothing is read from the old file. A well-formed cache
    of the last layout, whose memo and verdict would have spared the scan
    its one reading, spares it nothing: the scan reads the document all the
    same. Removing the file is the after-install step's (P234), so a pass
    leaves it where it is."""
    import json

    from tests.builders import counting_extractor
    from tracker.content_check import rules_fingerprint
    from tracker.scanner import scan_engagement
    from tracker.validators import sha256_of
    from tracker.verdicts import CACHE_VERSION, RETIRED_CACHE_FILENAME

    calls = counting_extractor(monkeypatch)
    prepared = engagement / PREPARED_DIR_NAME
    working_copy = text_pdf(prepared / "A01 - W-2 Wage Statements - TY2025.pdf",
                            "Form W-2 Wage and Tax Statement 2025")
    stat = working_copy.stat()
    digest = sha256_of(working_copy)
    old_file = engagement / RETIRED_CACHE_FILENAME
    old_file.write_text(json.dumps({
        "version": CACHE_VERSION,
        "files": {str(working_copy.resolve()).lower(): {
            "size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "digest": digest}},
        "verdicts": {digest: {rules_fingerprint(ITEMS[0]): {
            "ok": True, "reason": "", "extractable": True, "transient": False, "evidence": []}}},
    }), encoding="utf-8")
    old_temp = engagement / f"{RETIRED_CACHE_FILENAME}.4242.abcd{TEMP_SUFFIX}"
    old_temp.write_text("{", encoding="utf-8")

    report = sort(engagement, today=DAY1)
    assert report.handled == 0                              # nothing to sort
    assert old_file.exists() and old_temp.exists()          # and the pass does not tidy up after install
    # Nothing of it reached the store: no verdict of its, and the one memo
    # there is the sweep's own reading of a file no row names (decision
    # 109), not the old file's - the scan below reads the document all the
    # same, which is the claim.
    assert cache_rows(engagement)[1] == {}

    report = scan_engagement(engagement, today=DAY1)
    assert calls["n"] == 1                                  # read once: the file was never a hit
    assert report.updates["A01"].file_count == 1


def test_a_pass_writes_nothing_under_the_clients_root_but_the_record_and_the_page(tmp_path, monkeypatch):
    """Decision 101's walk, extended by 107: after a real sort and scan, the
    only files a pass has put under the clients root are the journal and
    the Status Report - no verdict cache, no temp file, no database."""
    from tracker.ledger import LEDGER_FILENAME
    from tracker.scanner import scan_engagement
    from tracker.verdicts import RETIRED_CACHE_FILENAME
    from tracker.view import VIEW_FILENAME

    root = tmp_path / "Clients"
    engagement = make_engagement(root / "Smith Family 2025", ITEMS)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    before = {p.name for p in root.rglob("*") if p.is_file()}

    sort(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY1)

    names = {p.name for p in root.rglob("*") if p.is_file()}
    assert RETIRED_CACHE_FILENAME not in names
    assert not any(name.endswith(TEMP_SUFFIX) for name in names)
    assert not any(name.endswith((store.STORE_FILENAME, store.STORE_WAL_FILENAME,
                                  store.STORE_SHM_FILENAME, ".db")) for name in names)
    # What the pass did put there: the client's own files, moved and copied,
    # and the record. The page is the runner's, so a bare sort and scan
    # leave none - and nothing else either.
    # The working copy's name is fitted to the room the path leaves
    # (decision 131), so under a long temporary folder it is cut: it is
    # known by its request, not spelled out whole.
    new = names - before
    copies = {name for name in new if name.startswith("A01 - W-2 Wage Statement")
              and name.endswith(".pdf")}
    assert len(copies) == 1, new
    assert new - copies <= {"w2.pdf", "scan0012.pdf", LEDGER_FILENAME, VIEW_FILENAME}, new


# --------------------------------------------------------------------- index ----


def test_no_pass_leaves_a_workbook_behind(engagement):
    """Decisions 102 and 104: the index and the request list are the record,
    and there is no file beside the engagement for Excel to hold, sort,
    re-type or save stale."""
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)

    assert list(engagement.rglob("*.xlsx")) == []
    assert list(engagement.glob("*.pending*.json")) == []      # no sidecar of any kind
    assert [e.identifier for e in read_index(engagement)] == ["A01"]


def test_the_routers_candidates_travel_as_data_in_the_index(engagement):
    from tracker.index import read_index

    drop(engagement, "old.pdf", "Form W-2 Wage and Tax Statement 2024")   # contested: wrong year
    report = sort(engagement, today=DAY1)
    [parked] = report.review
    assert parked.candidates == "A01"
    assert read_index(engagement)[0].candidates == "A01"


def test_a_filed_row_and_a_parked_row_both_say_what_the_rules_saw(engagement):
    from tracker.index import read_index
    from tracker.records import RULE_REQUIRED, WHERE_TITLE

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "old.pdf", "Form W-2 Wage and Tax Statement 2024")   # contested: wrong year
    sort(engagement, today=DAY1)

    by_name = {e.original_name: e for e in read_index(engagement)}
    for name, decision in (("w2.pdf", FILED), ("old.pdf", NEEDS_REVIEW)):
        entry = by_name[name]
        assert entry.decision == decision
        # Read back through the workbook, parsed by the one parser.
        assert [(e.rule, e.term, e.where) for e in entry.evidence_record["A01"]][:1] == [
            (RULE_REQUIRED, "W-2", WHERE_TITLE),
        ], name
    # The cell carries the firm's own keyword and nothing the document said.
    assert "W-2@" in by_name["w2.pdf"].evidence


def test_dry_run_previews_real_numbering(engagement):
    drop(engagement, "john w2.pdf", "Form W-2 Wage and Tax Statement 2025 John")
    drop(engagement, "jane w2.pdf", "Form W-2 Wage and Tax Statement 2025 Jane")

    planned = [e.filed_as for e in sort(engagement, today=DAY1, dry_run=True).filed]

    assert sorted(planned) == [
        "A01 - W-2 Wage Statements - TY2025 (2).pdf",
        "A01 - W-2 Wage Statements - TY2025.pdf",
    ]


# ------------------------ the rules are edited in the app (d103, d104) ----


def edits(engagement) -> list[dict]:
    return [e for e in ledger.read_events(engagement)
            if e[ledger.EVENT_KEY] == ledger.RULES_CHANGED]


def edit_the_list(engagement, **any_keywords_by_identifier):
    """A person editing Any Keywords in the app, saved as one event.

    From the rows as the store holds them - the person's own, without the
    keywords filings taught - which is what the editor opens on.
    """
    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement)]
    edited = [
        RequestItem(**{**rule_from_json(rule_to_json(row)),
                       "any_keywords": tuple(any_keywords_by_identifier[row.identifier].split(", "))})
        if row.identifier in any_keywords_by_identifier else row
        for row in rows
    ]
    return save_rules(engagement, edited, load_engagement_info(engagement))


def test_a_rules_edit_between_two_passes_is_one_event_of_exactly_what_changed(engagement):
    """The edit is a difference, and it is journalled.

    The create carries the whole list - that is what makes the fold of
    every edit the list. The save carries only the row a person touched,
    a pass appends nothing about the rules, and the next pass files on
    the edited row.
    """
    ensure(engagement)
    first = edits(engagement)
    assert len(first) == 1
    assert [row["identifier"] for row in first[0][ledger.RULES_KEY]] == ["A01", "C01"]

    ensure(engagement)                                   # nothing has moved
    assert edits(engagement) == first

    saved = edit_the_list(engagement, C01="lender, mortgage")
    assert saved.recorded and saved.changed == ("C01",)

    second = edits(engagement)
    assert len(second) == 2
    assert [row["identifier"] for row in second[1][ledger.RULES_KEY]] == ["C01"]
    assert second[1][ledger.RULES_KEY][0]["any_keywords"] == ["lender", "mortgage"]
    assert second[1][ledger.REMOVED_KEY] == []
    assert {i.identifier: i.any_keywords
            for i in load_manifest(engagement)}["C01"] == ("lender", "mortgage")

    drop(engagement, "note.pdf", "Form 1098 from your mortgage lender, 2025")
    report = sort(engagement, today=DAY1)
    assert [e.identifier for e in report.filed] == ["C01"]
    assert len(edits(engagement)) == 2                   # the pass wrote no rules event


def test_a_row_a_person_deleted_is_recorded_as_removed_and_leaves_the_store(engagement):
    ensure(engagement)
    kept = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement)
            if row["identifier"] != "C01"]

    saved = save_rules(engagement, kept, load_engagement_info(engagement))

    assert saved.removed == ("C01",) and saved.changed == ()
    last = edits(engagement)[-1]
    assert last[ledger.REMOVED_KEY] == ["C01"]
    assert [row["identifier"] for row in store.rules(store.connect(), engagement)] == ["A01"]
    assert [i.identifier for i in load_manifest(engagement)] == ["A01"]


# --------------------- the statuses live in the record (d103) ----


def test_read_index_keeps_the_place_of_a_row_that_changed_identity(engagement):
    """Decision 88's claim, answered from the store: the client renamed an
    original, the row followed the bytes, and it keeps the place it held -
    the audit trail is not reordered by a rename."""
    drop(engagement, "a first.pdf", "Form W-2 Wage and Tax Statement 2025 A")
    drop(engagement, "b second.pdf", "Form 1098 Mortgage Interest Statement 2025")
    drop(engagement, "c third.pdf", "Form W-2 Wage and Tax Statement 2025 C")
    sort(engagement, today=DAY1)
    before = [e.original_name for e in read_index(engagement)]
    assert before == ["a first.pdf", "b second.pdf", "c third.pdf"]

    (originals(engagement) / "a first.pdf").rename(originals(engagement) / "z renamed.pdf")
    sort(engagement, today=DAY2)

    rows = read_index(engagement)
    assert [e.original_name for e in rows] == before          # the place, not the new name
    assert rows[0].pbc_location.endswith("z renamed.pdf")
    assert list(ledger.replay(ledger.read_events(engagement)).rows) == [
        e.pbc_location for e in rows]


def test_filing_a_drop_is_one_call_and_one_transaction(engagement, monkeypatch):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    calls = counted_records(monkeypatch)

    sort(engagement, today=DAY1)

    # The rows are still one call and so one transaction, in the order the
    # drops were sorted, which is the order they are named. What each drop
    # adds before it is touched is its intent (decision 119): one, before
    # the copies it is about to make, written before the work it stands
    # for - which is the one place "one decision, one call" is deliberately
    # two calls. The move out of the inbox writes none since decision 125:
    # it is a rename, and decision 23 sorts an original with no row where
    # it lies.
    assert [c for c in calls if c != (ledger.MOVING,)] == [(ledger.PARKED, ledger.FILED)]
    assert calls.count((ledger.MOVING,)) == 2
    assert calls[-1] == (ledger.PARKED, ledger.FILED)


def test_a_pass_that_changed_nothing_records_nothing(engagement, monkeypatch):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    calls = counted_records(monkeypatch)

    sort(engagement, today=DAY2)

    assert calls == []


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
    report = sort(engagement, today=DAY1)

    assert [e.original_name for e in report.filed] == ["a-w2.pdf", "c-w2.pdf"]
    assert [e.name for e in report.errors] == ["b-mortgage.pdf"]
    assert report.errors[0].left_in_place is False
    # Every original is in PBC, and every one of them is in the index.
    assert {p.name for p in originals(engagement).iterdir()} == {
        "a-w2.pdf", "b-mortgage.pdf", "c-w2.pdf",
    }
    rows = {e.original_name: e for e in read_index(engagement)}
    assert set(rows) == {"a-w2.pdf", "b-mortgage.pdf", "c-w2.pdf"}
    assert rows["b-mortgage.pdf"].decision == NEEDS_REVIEW
    assert "(OSError (ENOSPC))" in rows["b-mortgage.pdf"].reason   # its class, never its words (decision 190)
    assert original_at(engagement, "b-mortgage.pdf") in rows["b-mortgage.pdf"].reason


def test_a_drop_still_held_open_is_left_for_the_next_run(engagement, monkeypatch):
    import os

    drop(engagement, "a-w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "b-mortgage.pdf", "Form 1098 Mortgage Interest Statement 2025")
    real_rename = os.rename

    def held_open(src, dst, *args, **kwargs):
        # What Windows does to a rename while another program has the file
        # open: refuses it. A copy of the same file would be allowed, and
        # is exactly what must not happen (the ninth reading found
        # shutil.move copying a half-written drop into PBC on this refusal).
        if "a-w2" in str(src):
            raise PermissionError("[WinError 32] used by another process")
        return real_rename(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "rename", held_open)
    report = sort(engagement, today=DAY1)

    assert [e.original_name for e in report.filed] == ["b-mortgage.pdf"]
    assert [e.name for e in report.errors] == ["a-w2.pdf"]
    assert report.errors[0].left_in_place is True
    assert (inbox_of(engagement) / "a-w2.pdf").exists()  # untouched
    assert not any("a-w2" in p.name for p in originals(engagement).iterdir())
    assert {e.original_name for e in read_index(engagement)} == {
        "b-mortgage.pdf",
    }

    # Released: the next run sorts it as if nothing had happened.
    monkeypatch.undo()
    report = sort(engagement, today=DAY2)
    assert [e.original_name for e in report.filed] == ["a-w2.pdf"]
    assert report.errors == []


# ------------------------------------------------------------ one run at a time ----


def test_the_filer_reads_nothing_before_it_holds_the_lock(engagement, monkeypatch):
    # What a run decides from - the manifest, the index, the drop folder -
    # must be read after the lock, or a run that finished in between is
    # invisible and its rows get rewritten from a stale picture.
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.intents as intents_module
    import tracker.readme_ack as readme_ack_module
    from tracker.locking import LOCK_FILENAME

    lock = engagement / LOCK_FILENAME
    seen = []
    for module, name in ((filer_module, "load_manifest"), (filer_module, "read_index"),
                         (copies_module, "read_index"), (intents_module, "read_index"),
                         (readme_ack_module, "load_manifest"), (readme_ack_module, "read_index"),
                         (actions_module, "load_manifest"), (actions_module, "read_index"),
                         (filer_module, "iter_drops")):
        real = getattr(module, name)

        def under_the_lock(*args, _real=real, _name=name, **kwargs):
            seen.append((_name, lock.exists()))
            return _real(*args, **kwargs)

        monkeypatch.setattr(module, name, under_the_lock)

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    assert sort(engagement, today=DAY1).handled == 1
    assert seen and all(held for _, held in seen), seen
    assert not lock.exists()

    seen.clear()                                  # a dry run reads without a lock
    sort(engagement, today=DAY1, dry_run=True)
    assert seen and not any(held for _, held in seen)


def test_the_filer_holds_the_engagement_lock(engagement):
    # A second run mid-way used to move the remaining files and overwrite
    # the first run's index rows. Same lock as the scanner, same answer.
    from tracker.locking import LOCK_FILENAME, EngagementLockedError

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    (engagement / LOCK_FILENAME).write_text(f"pid={os.getpid()}", encoding="utf-8")
    with pytest.raises(EngagementLockedError):
        sort(engagement, today=DAY1)
    assert (inbox_of(engagement) / "w2.pdf").exists()   # nothing moved
    # A dry run writes nothing, so it needs no lock.
    assert sort(engagement, today=DAY1, dry_run=True).handled == 1
    (engagement / LOCK_FILENAME).unlink()
    assert sort(engagement, today=DAY1).handled == 1
    assert not (engagement / LOCK_FILENAME).exists()


def test_a_document_renamed_in_the_editor_keeps_its_copies_and_names_the_next_by_it(engagement):
    """Decision 25 flat (decision 168): the request is found by its
    identifier, so the copy filed before the Document was renamed keeps its
    name and still counts, and the next copy takes the new short name
    beside it - no folder to keep, none made."""
    from tracker.scaffold import assign_files

    drop(engagement, "john.pdf", "Form W-2 Wage and Tax Statement 2025")
    first = sort(engagement, today=DAY1).filed[0]
    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement)]
    rows[0] = RequestItem(**{**rule_from_json(rule_to_json(rows[0])), "document": "W-2s (all employers)"})
    save_rules(engagement, rows, load_engagement_info(engagement))
    drop(engagement, "jane.pdf", "Form W-2 Wage and Tax Statement 2025 Jane")
    report = sort(engagement, today=DAY2)
    assert first.prepared_location == f"{PREPARED_DIR_NAME}/A01 - W-2 Wage Statements - TY2025.pdf"
    assert report.filed[0].prepared_location == f"{PREPARED_DIR_NAME}/A01 - W-2s (all employers) - TY2025.pdf"
    owned = assign_files(engagement / PREPARED_DIR_NAME, ["A01", "C01"])["A01"]
    assert sorted(p.name for p in owned) == ["A01 - W-2 Wage Statements - TY2025.pdf",
                                             "A01 - W-2s (all employers) - TY2025.pdf"]
    assert [p.name for p in (engagement / PREPARED_DIR_NAME).iterdir() if p.is_dir()] == [REVIEW_DIR_NAME]


def test_a_file_dropped_straight_into_the_years_folder_is_filed_and_indexed(engagement):
    # The client can see the year's folder and was told to drop things
    # anywhere, so some land there rather than in the inbox.
    original = text_pdf(originals(engagement) / "w2.pdf",
                        named_page("Form W-2 Wage and Tax Statement 2025"))
    before = original.read_bytes()
    report = sort(engagement, today=DAY1)
    assert [e.original_name for e in report.filed] == ["w2.pdf"]
    assert original.read_bytes() == before                    # not moved, not touched
    rows = read_index(engagement)
    assert rows[0].pbc_location == original_at(engagement, "w2.pdf")
    assert (engagement / rows[0].prepared_location).exists()
    # Recorded now, so the next run leaves it alone.
    assert sort(engagement, today=DAY2).handled == 0


def test_a_resend_is_refiled_when_the_working_copy_was_deleted(engagement, monkeypatch):
    """Decision 24's re-file. Since decision 157 the pass makes a deleted
    copy again from its original before it sorts, and a re-send then finds
    the copy home and is a duplicate; so the road this pins is the one a
    copy takes when its original cannot be read to make it again - the sync
    client still holding the year's folder as placeholders."""
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    first = sort(engagement, today=DAY1).filed[0]
    real = filer_module.is_cloud_placeholder
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "is_cloud_placeholder",
                            lambda p: p.parent == originals(engagement) or real(p))
    working = engagement / first.prepared_location
    working.unlink()                                          # a preparer's slip
    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025")
    report = sort(engagement, today=DAY2)
    assert report.duplicates == []
    assert [e.original_name for e in report.filed] == ["w2 again.pdf"]
    assert "re-filed" in report.filed[0].reason
    assert working.exists()                                   # same canonical name again
    # A re-send whose working copy is still there is still just a duplicate.
    drop(engagement, "w2 third time.pdf", "Form W-2 Wage and Tax Statement 2025")
    assert [e.decision for e in sort(engagement, today=DAY2).duplicates] == [DUPLICATE]
    # ...and one more drop after the working copy goes again: the Duplicate
    # row must not shadow the Filed row, or this re-send is never re-filed.
    working.unlink()
    drop(engagement, "w2 fourth time.pdf", "Form W-2 Wage and Tax Statement 2025")
    fourth = sort(engagement, today=DAY2)
    assert fourth.duplicates == [] and [e.original_name for e in fourth.filed] == ["w2 fourth time.pdf"]
    assert working.exists()


def test_empty_client_folders_are_cleared_after_sorting(engagement):
    inbox = inbox_of(engagement)
    nested = inbox / "from my phone" / "scans"
    nested.mkdir(parents=True)
    text_pdf(nested / "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    (inbox / "keep").mkdir()
    (inbox / "keep" / "later.txt.tmp").write_text("x")  # still uploading
    sort(engagement, today=DAY1)
    # The inbox holds nothing of the firm's to step around since decision
    # 125 - the originals rest in the other tree - so what is left is the
    # one folder that still holds a file.
    left = sorted(p.name for p in inbox.iterdir() if p.is_dir())
    assert left == ["keep"]


# ------------------------------------------------- a person files a parked file ----


def test_a_drop_for_a_not_applicable_row_parks_and_nothing_under_the_engagement_is_deleted_or_moved_by_the_override(
    engagement,
):
    """Rule 3 and decision 116: the router does not consider a set-aside
    row, so its document parks and its parked copy is its working copy;
    setting the override on a row with a filed copy moves and alters
    nothing - the copy and the original are the bytes they were - and the
    row leaves the counts."""
    from dataclasses import replace

    from tracker.manifest import Override, load_engagement_info, load_manifest, save_rules, summarize

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    [filed] = [e for e in read_index(engagement) if e.original_name == "w2.pdf"]
    assert filed.decision == FILED and filed.identifier == "A01"
    original = engagement / filed.pbc_location
    copy = engagement / filed.prepared_location
    before = {p.relative_to(engagement): p.read_bytes() for p in engagement.rglob("*") if p.is_file()
              and p.name != ledger.LEDGER_FILENAME}

    rows = [replace(row, manual_override=Override.NOT_APPLICABLE) if row.identifier == "A01" else row
            for row in load_manifest(engagement)]
    save_rules(engagement, rows, load_engagement_info(engagement))

    after = {p.relative_to(engagement): p.read_bytes() for p in engagement.rglob("*") if p.is_file()
             and p.name != ledger.LEDGER_FILENAME}
    assert after == before, "the override moves and alters nothing under the engagement"
    assert original.read_bytes() == copy.read_bytes()
    summary = summarize(load_manifest(engagement))
    assert summary.not_applicable == 1 and summary.total == len(rows) - 1

    # A second W-2 for the set-aside row parks - it is not filed under a row
    # a person said does not apply - and its parked copy is kept, whole.
    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025 second employer")
    sort(engagement, today=DAY1)
    [parked] = [e for e in read_index(engagement) if e.original_name == "w2 again.pdf"]
    assert parked.decision == NEEDS_REVIEW
    assert (engagement / parked.pbc_location).is_file()
    assert (engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME / "w2 again.pdf").is_file()


# ---------------------------------------------- what a review found (decision 54) ----


def test_an_original_replaced_under_its_own_name_is_said_out_loud_every_run(engagement):
    from tracker.filer import REPLACED_IN_PBC

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    first = sort(engagement, today=DAY1).filed[0]
    text_pdf(originals(engagement) / "w2.pdf", "Form W-2 Wage and Tax Statement 2025 CORRECTED")
    for _ in range(2):
        report = sort(engagement, today=DAY2)
        assert report.handled == 0 and report.errors == []          # nothing was left unsorted
        [error] = report.attention
        assert error.name == "w2.pdf" and error.left_in_place
        assert error.error == REPLACED_IN_PBC.format(
            location=first.pbc_location, received=DAY1.isoformat(), prepared=first.prepared_location)
    assert len(read_index(engagement)) == 1


def test_a_run_killed_after_copying_does_not_leave_a_second_copy_behind(engagement, monkeypatch):
    # The working copy was made, the process died before the index recorded
    # it. The next run finds the original unrecorded and reuses the copy.

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")

    def killed(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(store, "record", killed)
    with pytest.raises(KeyboardInterrupt):
        sort(engagement, today=DAY1)
    monkeypatch.undo()
    assert read_index(engagement) == []

    report = sort(engagement, today=DAY2)
    assert len(report.filed) == 1 and len(report.review) == 1
    assert [p.name for p in prepared(engagement, "A01").iterdir()] == [report.filed[0].filed_as]
    assert [p.name for p in prepared(engagement, REVIEW_DIR_NAME).iterdir()] == ["scan0012.pdf"]


def test_a_file_still_being_written_is_reported_as_waiting_not_passed_over(engagement):

    half = inbox_of(engagement) / f"upload{TEMP_SUFFIX}"
    half.write_bytes(b"%PDF-1.4 partial")
    report = sort(engagement, today=DAY1)
    assert report.waiting == [half] and report.handled == 0
    assert half.exists()


# ------------------------------------------- the second reading (decision 56) ----


def test_a_same_size_replacement_with_an_old_date_is_still_noticed(engagement):
    # One number changed in a CSV, copied in with its original timestamp:
    # same size, older mtime. Only the bytes can tell.
    from tracker.filer import REPLACED_IN_PBC

    (inbox_of(engagement) / "ledger.csv").write_text("a,1\nb,2\n", encoding="utf-8")
    first = sort(engagement, today=DAY1).review[0]
    original = originals(engagement) / "ledger.csv"
    stamp = original.stat().st_mtime - 30 * 86400
    original.write_text("a,1\nb,3\n", encoding="utf-8")          # same length
    os.utime(original, (stamp, stamp))                            # older than its row
    [error] = sort(engagement, today=DAY2).attention
    assert error.error == REPLACED_IN_PBC.format(
        location=first.pbc_location, received=DAY1.isoformat(), prepared=first.prepared_location)


def test_an_original_the_sync_client_dehydrated_is_not_downloaded_to_be_checked(engagement, monkeypatch):
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "is_cloud_placeholder", lambda p: p.name == "w2.pdf")

    def never(path):
        raise AssertionError(f"hashed {path.name}")
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "sha256_of", never)
    assert sort(engagement, today=DAY2).errors == []


def test_a_copy_that_fails_half_way_leaves_no_truncated_working_copy(engagement, monkeypatch):
    import tracker.filer as filer_module

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    def half(src, dst):
        filer_module.Path(dst).write_bytes(b"%PDF-1.4 half")
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(shutil, "copy2", half)
    report = sort(engagement, today=DAY1)
    monkeypatch.undo()
    assert len(report.review) == 1 and "(OSError (ENOSPC))" in report.review[0].reason
    assert not any(prepared(engagement, "A01").iterdir())          # nothing half-written
    assert (originals(engagement) / "w2.pdf").exists()                    # the record is safe


def test_every_unfinished_transfer_name_is_reported_as_waiting(engagement):
    from tracker.validators import UNFINISHED_SUFFIXES

    for suffix in UNFINISHED_SUFFIXES:
        (inbox_of(engagement) / f"upload{suffix}").write_bytes(b"partial")
    report = sort(engagement, today=DAY1)
    assert sorted(p.name for p in report.waiting) == sorted(f"upload{s}" for s in UNFINISHED_SUFFIXES)


def test_a_cloud_placeholder_is_not_a_link(tmp_path):
    # A sync client's placeholder is a reparse point with the client's own
    # tag; only a mount point (junction) or a symlink is a link.
    import stat

    from tracker.fsio import _LINK_TAGS
    from tracker.fsio import is_link as _is_link

    plain = tmp_path / "w2.pdf"
    plain.write_bytes(b"%PDF-1.4")
    assert not _is_link(plain)
    assert getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003) in _LINK_TAGS or sys.platform != "win32"
    assert 0x9000001A not in _LINK_TAGS            # OneDrive's tag
    try:
        (tmp_path / "link.pdf").symlink_to(plain)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks need a privilege here")
    assert _is_link(tmp_path / "link.pdf")


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS takes a lone surrogate in a name")
def test_a_name_the_index_cannot_hold_is_reported_not_allowed_to_take_the_index_down(engagement):
    # The tenth reading: one such name made every index write fail, after
    # the pass's originals had been moved, and nothing was recorded again.
    bad = inbox_of(engagement) / "bank statement \ud83d.pdf"
    bad.write_bytes(b"%PDF-1.4 a name with half an emoji")
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    report = sort(engagement, today=DAY1)
    assert [e.original_name for e in report.filed] == ["w2.pdf"]
    assert [e.left_in_place for e in report.errors] == [True] and "rename it" in report.errors[0].error
    assert bad.exists() and [r.original_name for r in read_index(engagement)] == ["w2.pdf"]
    # Dropped straight into the year's folder, it is not sorted as a stray
    # either: an original the index cannot name is never given a row.
    bad.rename(originals(engagement) / bad.name)
    report = sort(engagement, today=DAY2)
    assert report.filed == []
    assert [r.original_name for r in read_index(engagement)] == ["w2.pdf"]


@pytest.mark.skipif(sys.platform != "win32", reason="names Windows cannot open")
def test_a_name_windows_cannot_open_is_reported_not_passed_over(engagement):
    inbox = inbox_of(engagement)
    # A Mac or a sync client can deliver these; only the \\?\ form creates them here.
    for name in ("dotted.pdf.", "spaced.pdf "):
        with open("\\\\?\\" + str(inbox / name), "wb") as handle:
            handle.write(b"%PDF-1.4 not openable by its plain name")
    report = sort(engagement, today=DAY1)
    assert sorted(e.name for e in report.errors) == ["dotted.pdf.", "spaced.pdf "]
    assert all(e.left_in_place and "rename it" in e.error for e in report.errors)
    assert report.filed == [] and report.review == []


@pytest.mark.skipif(sys.platform != "win32", reason="junctions")
def test_what_lies_behind_a_junction_is_not_a_drop(engagement, tmp_path):
    import _winapi

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "theirs.pdf").write_bytes(b"%PDF-1.4 somebody else's file")
    _winapi.CreateJunction(str(outside), str(inbox_of(engagement) / "link"))
    drop(engagement, "scan0012.pdf", "Form W-2 Wage and Tax Statement 2025")

    report = sort(engagement, today=DAY1)

    assert [e.original_name for e in report.filed] == ["scan0012.pdf"]
    assert (outside / "theirs.pdf").exists()                     # never moved
    assert (inbox_of(engagement) / "link").exists()              # never removed as an "empty folder"
    assert [p.name for p in originals(engagement).iterdir()] == ["scan0012.pdf"]


def test_a_file_named_like_a_formula_is_recorded_as_its_name(engagement):
    drop(engagement, "=SUM scan.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    [row] = read_index(engagement)
    assert row.original_name == "=SUM scan.pdf"


# ------------------------------------------- the thirteenth reading (d72) ----


def test_an_original_deleted_from_pbc_is_said_every_pass(engagement):
    # PBC is the provided-by-client record and the client can see it, so
    # Explorer will delete what is already there. Every other disagreement
    # between the index and the disk was said every pass; this one was said
    # by nothing at all, and the scan went on calling the request Received.
    from tracker.filer import MISSING_IN_PBC

    drop(engagement, "w2 employer a.pdf", "Form W-2 Wage and Tax Statement 2025 A")
    drop(engagement, "w2 employer b.pdf", "Form W-2 Wage and Tax Statement 2025 B")
    filed = {e.original_name: e for e in sort(engagement, today=DAY1).filed}
    (originals(engagement) / "w2 employer a.pdf").unlink()

    for day in (DAY1, DAY2):
        report = sort(engagement, today=day)
        assert report.errors == []                               # a finding, not a failed pass
        assert [(e.name, e.left_in_place) for e in report.attention] == [("w2 employer a.pdf", True)]
        assert report.attention[0].error == MISSING_IN_PBC.format(
            location=filed["w2 employer a.pdf"].pbc_location, received=DAY1.isoformat())
    rows = read_index(engagement)
    assert [r.decision for r in rows] == [FILED, FILED]
    # The working copy is the scan's business and is left exactly as it was.
    assert (engagement / filed["w2 employer a.pdf"].prepared_location).exists()


def test_an_original_the_client_renamed_in_pbc_is_followed_not_filed_again(engagement):
    from tracker.filer import MOVED_IN_PBC

    drop(engagement, "w2 employer a.pdf", "Form W-2 Wage and Tax Statement 2025 A")
    filed = sort(engagement, today=DAY1).filed[0]
    (originals(engagement) / "w2 employer a.pdf").rename(originals(engagement) / "employer A W2 2025.pdf")

    report = sort(engagement, today=DAY2)
    now = original_at(engagement, "employer A W2 2025.pdf")
    assert report.duplicates == [] and report.handled == 0 and report.errors == []
    assert [e.error for e in report.attention] == [
        MOVED_IN_PBC.format(location=filed.pbc_location, now=now)
    ]
    [row] = read_index(engagement)
    assert row.pbc_location == now                                # the row followed the bytes
    assert row.original_name == filed.original_name               # what it arrived as is the record
    assert filed.pbc_location in row.reason
    assert row.prepared_location == filed.prepared_location and row.digest == filed.digest
    assert sort(engagement, today=DAY2).attention == []     # said once; then it is the record


def test_an_original_the_client_moved_into_a_subfolder_of_pbc_is_followed(engagement):
    drop(engagement, "w2 employer a.pdf", "Form W-2 Wage and Tax Statement 2025 A")
    filed = sort(engagement, today=DAY1).filed[0]
    (originals(engagement) / "2025").mkdir()
    (originals(engagement) / "w2 employer a.pdf").rename(originals(engagement) / "2025" / "w2 employer a.pdf")

    report = sort(engagement, today=DAY2)
    assert report.duplicates == [] and report.handled == 0 and len(report.attention) == 1
    [row] = read_index(engagement)
    assert row.pbc_location == original_at(engagement, "2025/w2 employer a.pdf")
    assert row.decision == FILED and row.prepared_location == filed.prepared_location


def test_a_duplicate_rows_own_original_is_watched_like_every_other(engagement):
    from tracker.filer import MISSING_IN_PBC

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025")
    [twice] = sort(engagement, today=DAY1).duplicates
    (originals(engagement) / "w2 again.pdf").unlink()

    report = sort(engagement, today=DAY2)
    assert [e.error for e in report.attention] == [
        MISSING_IN_PBC.format(location=twice.pbc_location, received=DAY1.isoformat())
    ]
    assert [r.decision for r in read_index(engagement)] == [FILED, DUPLICATE]


def test_a_row_recorded_without_its_bytes_is_never_moved_onto_another_file(engagement, monkeypatch):
    # Decision 65: an empty digest is nobody's. Nothing proves a stray is
    # this row's original, so the row is said and left where it is.
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module
    from tracker.filer import MISSING_IN_PBC

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    real = filer_module.sha256_of

    held = set()

    def unreadable(path):
        if path.parent == originals(engagement) and path not in held:
            # Held for the one read that records the row: since decision
            # 187 the intent fingerprints a copy's source itself, a moment
            # later, so the copy is proved and the row keeps no bytes.
            held.add(path)
            raise PermissionError("held by the sync client")
        return real(path)
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "sha256_of", unreadable)
    row = sort(engagement, today=DAY1).filed[0]
    monkeypatch.undo()
    assert row.digest == ""
    (originals(engagement) / "w2.pdf").rename(originals(engagement) / "renamed w2.pdf")

    report = sort(engagement, today=DAY2)
    gone = [e for e in report.attention
            if e.error == MISSING_IN_PBC.format(location=row.pbc_location, received=DAY1.isoformat())]
    assert len(gone) == 1
    rows = read_index(engagement)
    assert rows[0].pbc_location == row.pbc_location               # never relocated
    assert [r.original_name for r in rows] == ["w2.pdf", "renamed w2.pdf"]


def test_an_original_the_sync_client_dehydrated_is_not_called_gone(engagement, monkeypatch):
    # A placeholder is a file the sync client has not brought down, which
    # is not the same as the client having deleted it.
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "is_cloud_placeholder", lambda p: p.parent == originals(engagement))
    report = sort(engagement, today=DAY2)
    assert report.attention == [] and report.errors == []


def test_an_empty_folder_is_cleared_by_a_pass_with_nothing_to_sort(engagement):
    # The tidy-up used to sit past an early return, so a pass that found
    # nothing to sort left the folder the client dragged in behind for ever.
    left_behind = inbox_of(engagement) / "from my phone"
    left_behind.mkdir()
    report = sort(engagement, today=DAY1)
    assert report.handled == 0 and not left_behind.exists()


# ------------------------------- a person says no request asks for it (d76) ----


def test_a_duplicates_reason_says_filed_only_of_a_filed_row(engagement):
    """Step 0's fourth defect: a parked copy has a name, and saying "already
    filed as" of it told the Index a document waiting for a person was done."""
    from tracker.filer import DUPLICATE_OF_FILED, DUPLICATE_OF_PARKED

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "notice.pdf", "nothing the rules recognise")
    first = sort(engagement, today=DAY1)
    filed = first.filed[0]
    parked = first.review[0]

    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "notice again.pdf", "nothing the rules recognise")
    report = sort(engagement, today=DAY2)

    said = {e.original_name: e.reason for e in report.duplicates}
    assert said["w2 again.pdf"] == DUPLICATE_OF_FILED.format(
        name=filed.original_name, copy=filed.filed_as
    )
    assert said["notice again.pdf"] == DUPLICATE_OF_PARKED.format(
        name=parked.original_name, copy=parked.filed_as
    )
    assert "already filed" not in said["notice again.pdf"]


def test_a_resend_of_a_moved_rows_bytes_is_a_duplicate_naming_the_moved_copy(engagement):
    """A row whose copy is not where the record put it is a person's to
    resolve; a second copy of the same document would not help them do it."""
    from tracker.filer import DUPLICATE_OF_MOVED
    from tracker.index import FILE_MOVED

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    drag(engagement / filed.prepared_location, prepared(engagement, "C01"))
    sort(engagement, today=DAY2)
    [moved] = read_index(engagement)
    assert moved.decision == FILE_MOVED
    untouched = files_under(engagement)

    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025")
    report = sort(engagement, today=DAY2)

    (dup,) = report.duplicates
    assert report.filed == [] and report.review == []
    assert dup.decision == DUPLICATE and dup.prepared_location == ""
    assert dup.reason == DUPLICATE_OF_MOVED.format(
        name=moved.original_name, copy=moved.filed_as
    )
    assert read_index(engagement)[0] == moved          # the moved row is untouched
    # The one new file under the engagement is the preserved original, and
    # nothing that was already there changed.
    after = files_under(engagement)
    assert set(after) - set(untouched) == {original_at(engagement, "w2 again.pdf")}
    assert {name: held for name, held in after.items() if name in untouched} == untouched


def test_a_duplicates_reason_of_a_row_with_no_working_copy_says_so(engagement, monkeypatch):
    """Decision 17's row has no copy to name.

    The three sentences above all end in the name of a file; this row has
    none, and "parked as" with nothing after it would be the Index's word
    for a file nobody can find.
    """
    import tracker.filer as filer_module
    from tracker.filer import DUPLICATE_OF_UNCOPIED

    def truncated(src, dst):
        filer_module.Path(dst).write_bytes(filer_module.Path(src).read_bytes()[:40])

    monkeypatch.setattr(shutil, "copy2", truncated)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    (failed,) = sort(engagement, today=DAY1).review
    monkeypatch.undo()
    assert failed.filed_as == "" and "could not be filed" in failed.reason

    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025")
    (dup,) = sort(engagement, today=DAY2).duplicates

    assert dup.reason == DUPLICATE_OF_UNCOPIED.format(name=failed.original_name)
    assert not dup.reason.endswith(" ")
    assert kept_files(engagement) == [
        original_at(engagement, "w2 again.pdf"),
        original_at(engagement, "w2.pdf"),
    ]


def test_a_resend_of_a_parked_rows_bytes_is_a_duplicate_and_makes_no_copy(engagement):
    """One copy in the review folder: a second would be a second thing to work."""
    drop(engagement, "notice.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    drop(engagement, "notice again.pdf", "nothing the rules recognise")
    report = sort(engagement, today=DAY2)

    (dup,) = report.duplicates
    assert report.review == [] and dup.prepared_location == ""
    assert dup.identifier == parked.identifier
    assert [p.name for p in review_dir(engagement).iterdir()] == ["notice.pdf"]
    assert kept_files(engagement) == [
        original_at(engagement, "notice again.pdf"),
        original_at(engagement, "notice.pdf"),
        f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/notice.pdf",
    ]


# ----------------------- a filed document goes back for review (d77) ----


def test_the_scan_after_a_two_form_split_accepts_the_copy_under_each_request(engagement, monkeypatch):
    """Decision 94's second copy is validated on the verdict the router filed
    it on, not on the ordinary reading that called the page one form's. The
    ordinary reading refuses C01 (the W-2 is the page's own form, the 1098
    is not); the split's reading accepts it; the scan must find the second
    in the cache - and read nothing again - or the copy fails validation
    and the client is asked for a 1098 they already sent."""
    from tests.builders import counting_extractor
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.manifest import Status
    from tracker.scanner import scan_engagement

    calls = counting_extractor(monkeypatch)
    drop(engagement, "scan0003.pdf",
         "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    (entry,) = sort(engagement, today=DAY1).filed
    assert entry.also_filed
    read_once = calls["n"]

    report = scan_engagement(engagement, today=DAY1)

    assert calls["n"] == read_once                              # both copies were cache hits
    assert report.updates["C01"].status == Status.RECEIVED, report.updates["C01"]
    assert report.updates["C01"].file_count == 1
    assert report.updates["A01"].status == Status.PARTIAL        # the row expects two
    assert report.updates["A01"].file_count == 1


def test_a_scan_with_an_empty_cache_reaches_the_verdict_the_router_filed_on_for_a_split_copy(
        engagement):
    """Decision 107's amendment: the split is derivable from the bytes, so a
    miss reads the page as the router read it - both forms its own - and
    the second copy passes without the cache."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.content_check import check_content
    from tracker.verdicts import ContentCache

    drop(engagement, "scan0003.pdf",
         "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    (entry,) = sort(engagement, today=DAY1).filed
    assert entry.identifier == "A01" and entry.also_filed
    second_copy = engagement / entry.also_filed.split(";")[0].strip()
    assert second_copy.exists(), entry.also_filed
    c01 = next(i for i in ITEMS if i.identifier == "C01")

    verdict = check_content(second_copy, c01, ContentCache())   # memory only, empty
    assert verdict.ok, verdict.reason
    a01 = next(i for i in ITEMS if i.identifier == "A01")
    assert check_content(engagement / entry.prepared_location, a01, ContentCache()).ok


def test_deleting_the_store_and_rebuilding_leaves_every_status_and_note_byte_identical(
        tmp_path, monkeypatch):
    """The runbook's own upgrade path, on a split: delete the store, rebuild
    from the journals, run a full pass - nothing is recorded and the
    statuses table is byte for byte what it held."""
    import os

    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.ledger import EVENT_KEY, SCANNED, read_events
    from tracker.scanner import scan_engagement
    from tracker.verdicts import CACHE_VERSION

    root = tmp_path / "Clients"
    engagement = make_engagement(root / "Smith Family 2025", ITEMS)
    drop(engagement, "scan0003.pdf",
         "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY1)
    live = store.connect()
    engagement_id = store._engagement_row(live, engagement)["id"]
    held = [tuple(row) for row in live.execute(
        "SELECT * FROM statuses WHERE engagement_id = ? ORDER BY identifier", (engagement_id,))]
    assert {row[1] for row in held} == {"a01", "c01"}
    events = len(read_events(engagement))

    db = os.environ[store.ENV_STORE]
    store.close()
    os.unlink(db)
    fresh = store.connect()
    store.rebuild_engagement(fresh, root, engagement)
    assert store.cached_verdicts(fresh, engagement, version=CACHE_VERSION) == ({}, {})

    sort(engagement, today=DAY2)
    report = scan_engagement(engagement, today=DAY2)

    assert report.recorded == 0                                    # nothing changed, nothing appended
    assert len(read_events(engagement)) == events
    assert read_events(engagement)[-1][EVENT_KEY] == SCANNED     # the first pass's scan is the last line
    rebuilt_id = store._engagement_row(fresh, engagement)["id"]
    again = [tuple(row) for row in fresh.execute(
        "SELECT * FROM statuses WHERE engagement_id = ? ORDER BY identifier", (rebuilt_id,))]
    assert [row[1:] for row in again] == [row[1:] for row in held]  # every column but the row id


def teach(engagement, identifier: str, keyword: str) -> None:
    """A keyword recorded against a request, as a person's filing records it."""
    from tracker.locking import engagement_lock

    with engagement_lock(engagement):
        ensure(engagement)
        store.record(store.connect(), engagement, ledger.new(ledger.KEYWORD_LEARNED, **{
            ledger.IDENTIFIER_KEY: identifier, ledger.KEYWORD_KEY: keyword,
        }))


def test_a_copy_that_passed_only_on_a_taught_keyword_regresses_after_it_is_unlearned(tmp_path):
    """Decision 113: the rules just moved, so the next reading of the copy
    is a different reading.

    A taught keyword is part of the row's rules fingerprint, so a copy that
    passed only on that word is read again on the next scan and fails - and
    the person who took the word back sees that in the same breath, because
    the app re-scans at once.
    """
    from tracker.manifest import Status, unlearn_keyword
    from tracker.reasons import NO_EXPECTED_KEYWORD
    from tracker.scanner import scan_engagement

    items = [RequestItem(
        identifier="B01", document="Escrow Analysis", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("escrow analysis",),
        date_pattern="*",
    )]
    engagement = make_engagement(tmp_path / "Smith Family 2025", items)
    teach(engagement, "B01", "lender statement")
    drop(engagement, "from the bank.pdf", "Lender Statement 2025\nAmount paid this year 1,234.00")

    assert [e.identifier for e in sort(engagement, today=DAY1).filed] == ["B01"]
    scan_engagement(engagement, today=DAY1)
    assert {i.identifier: i.status for i in load_manifest(engagement)} == {"B01": Status.RECEIVED}

    unlearn_keyword(engagement, "B01", "lender statement")
    scan_engagement(engagement, today=DAY2)

    b01 = next(i for i in load_manifest(engagement) if i.identifier == "B01")
    assert b01.status == Status.FAILED
    assert NO_EXPECTED_KEYWORD.format(listed="escrow analysis") in b01.validation_notes

# --------------------------- every working copy is proved (decision 109) ----


def test_a_filed_copy_dragged_into_another_requests_folder_is_file_moved_and_nothing_moves(engagement):
    from tracker.index import FILE_MOVED, MOVED_SENTENCE, moved_to

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    wanderer = drag(engagement / filed.prepared_location, prepared(engagement, "C01"))
    now = location_of(engagement, wanderer)
    untouched = files_under(engagement)

    report = sort(engagement, today=DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED
    assert moved_to(row) == now
    assert row.prepared_location == filed.prepared_location   # home stays the column
    assert row.reason.startswith(filed.reason)                # and what it said before is kept
    sentence = MOVED_SENTENCE.format(
        home=filed.prepared_location, now=now, date=DAY2.isoformat())
    assert row.reason.endswith(sentence)
    assert [(e.name, e.error, e.left_in_place) for e in report.attention] == [
        (wanderer.name, sentence, True)
    ]
    assert len(events_named(engagement, ledger.COPY_MOVED)) == 1
    assert files_under(engagement) == untouched


def test_a_filed_copy_renamed_inside_its_folder_is_file_moved(engagement):
    from tracker.index import FILE_MOVED, moved_to

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    copy = engagement / filed.prepared_location
    renamed = copy.rename(copy.with_name("john's w2 (final).pdf"))
    untouched = files_under(engagement)

    sort(engagement, today=DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED
    assert moved_to(row) == location_of(engagement, renamed)
    assert files_under(engagement) == untouched


def test_a_filed_copy_renamed_to_a_name_no_request_begins_is_file_moved(engagement):
    """The wanderer in the firm's folder under a name no request's
    identifier begins (decision 168; loose at the root of Prepared until
    then): the sweep finds it by its bytes, and the scan goes on warning
    about a file no request's name claims, because one warning per thing is
    the rule and those are two different things."""
    from tracker.index import FILE_MOVED, moved_to
    from tracker.scanner import UNCLAIMED_FILE, scan_engagement

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    home = engagement / filed.prepared_location
    loose = home.with_name("w2 for later.pdf")
    home.rename(loose)
    untouched = files_under(engagement)

    report = sort(engagement, today=DAY2)
    scanned = scan_engagement(engagement, today=DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED and moved_to(row) == location_of(engagement, loose)
    assert len(report.attention) == 1                      # said once by the sweep...
    assert scanned.warnings == [
        UNCLAIMED_FILE.format(name=loose.name, prepared=PREPARED_DIR_NAME)
    ]                                                      # ...and once as the unclaimed file it is
    assert files_under(engagement) == untouched


def test_a_second_copy_of_a_moved_rows_bytes_does_not_re_point_the_row(engagement):
    """A document can be in the firm's folder twice over - somebody copied it
    before dragging the first one, or a (2) name, or a subfolder. The row
    keeps the wanderer it already names: the one that sorts first is not
    the one a person moved, and re-pointing the row at it would append an
    event nothing happened for and send the put-it-back after the wrong
    file. The second copy is what it is - a file nothing on the record put
    there - and is said as one."""
    from tracker.filer import UNRECORDED_COPY
    from tracker.index import FILE_MOVED, moved_to

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    home = engagement / filed.prepared_location
    wanderer = drag(home, prepared(engagement, "C01"))
    sort(engagement, today=DAY2)
    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED and moved_to(row) == location_of(engagement, wanderer)

    # The same bytes again, at a path the walk reaches first.
    planted = home.parent / "A01 - a copy of the same thing.pdf"
    planted.write_bytes(wanderer.read_bytes())
    assert location_of(engagement, planted) < location_of(engagement, wanderer)
    lines = len(ledger.read_events(engagement))
    untouched = files_under(engagement)

    report = sort(engagement, today=DAY2 + dt.timedelta(days=1))

    assert len(ledger.read_events(engagement)) == lines      # nothing happened, nothing said
    [row] = read_index(engagement)
    assert moved_to(row) == location_of(engagement, wanderer)
    assert [e.error for e in report.attention] == [
        UNRECORDED_COPY.format(location=location_of(engagement, planted))
    ]
    assert files_under(engagement) == untouched


def test_a_moved_copy_dragged_back_by_hand_is_filed_again_on_the_next_pass(engagement):
    from tracker.filer import MOVED_BACK_SENTENCE
    from tracker.index import FILE_MOVED, moved_to

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    home = engagement / filed.prepared_location
    wanderer = drag(home, prepared(engagement, "C01"))
    sort(engagement, today=DAY2)
    assert read_index(engagement)[0].decision == FILE_MOVED

    wanderer.rename(home)                                  # a person puts it back
    untouched = files_under(engagement)
    report = sort(engagement, today=DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILED and moved_to(row) is None
    sentence = MOVED_BACK_SENTENCE.format(home=filed.prepared_location, date=DAY2.isoformat())
    assert row.reason.endswith(sentence)
    assert [e.error for e in report.attention] == [sentence]
    assert len(events_named(engagement, ledger.COPY_MOVED)) == 2   # one away, one home
    assert files_under(engagement) == untouched


def test_a_moved_row_is_written_once_per_move_and_a_quiet_pass_appends_nothing(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    wanderer = drag(engagement / filed.prepared_location, prepared(engagement, "C01"))
    lines = len(ledger.read_events(engagement))

    sort(engagement, today=DAY2)
    assert len(ledger.read_events(engagement)) == lines + 1        # said once
    for day in (DAY2, DAY2 + dt.timedelta(days=1)):
        sort(engagement, today=day)
        assert len(ledger.read_events(engagement)) == lines + 1    # and not again

    wanderer.rename(wanderer.with_name("moved again.pdf"))        # moved again
    sort(engagement, today=DAY2 + dt.timedelta(days=2))
    assert len(ledger.read_events(engagement)) == lines + 2
    assert len(events_named(engagement, ledger.COPY_MOVED)) == 2


def test_a_moved_copy_that_is_then_deleted_says_nowhere_once_and_is_made_again_the_pass_after(
        engagement):
    """Decision 109's nowhere sentence, then decision 157: the row is a
    person's question (decision 110's card), so what happened to the
    wanderer is said first, once; the pass after, the copy is made again
    at home from the original and the row is Filed once more - nowhere is
    not left standing while the original can make it."""
    from tracker.filer import REMADE_SENTENCE
    from tracker.index import FILE_MOVED, MOVED_GONE_SENTENCE, moved_to

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    wanderer = drag(engagement / filed.prepared_location, prepared(engagement, "C01"))
    sort(engagement, today=DAY2)

    wanderer.unlink()
    original = (originals(engagement) / "w2.pdf").read_bytes()
    report = sort(engagement, today=DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED and moved_to(row) is None
    sentence = MOVED_GONE_SENTENCE.format(
        home=filed.prepared_location, prepared=PREPARED_DIR_NAME,
        pbc=filed.pbc_location, date=DAY2.isoformat())
    assert row.reason.endswith(sentence)
    assert [e.error for e in report.attention] == [sentence]
    assert (originals(engagement) / "w2.pdf").read_bytes() == original   # the original is the record

    later = sort(engagement, today=DAY2 + dt.timedelta(days=1))

    remade = REMADE_SENTENCE.format(home=filed.prepared_location, pbc=filed.pbc_location,
                                    date=(DAY2 + dt.timedelta(days=1)).isoformat(),
                                    prepared=PREPARED_DIR_NAME)
    [row] = read_index(engagement)
    assert row.decision == FILED and row.reason == f"{filed.reason}; {remade}"
    assert [e.error for e in later.attention] == [remade]
    assert (engagement / filed.prepared_location).read_bytes() == original
    assert len(events_named(engagement, ledger.COPY_REMADE)) == 1


def test_a_copy_deleted_outright_is_made_again_and_nothing_else_moves(engagement):
    """Nothing under the firm's folder holds its bytes, and the original in
    the client's folder does: since decision 157 the copy is made again
    from it - one ``copy_remade`` line, no ``copy_moved`` - and the one new
    file is the copy, byte for byte the original, where the record put it.
    Until 157 the row stayed as it was and the request regressed (decision
    3's regression), and the letter asked the client."""
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    (engagement / filed.prepared_location).unlink()
    untouched = files_under(engagement)

    report = sort(engagement, today=DAY2)

    assert events_named(engagement, ledger.COPY_MOVED) == []
    assert len(events_named(engagement, ledger.COPY_REMADE)) == 1
    assert len(report.attention) == 1
    after = files_under(engagement)
    assert set(after) - set(untouched) == {filed.prepared_location}
    assert {name: held for name, held in after.items() if name in untouched} == untouched
    assert after[filed.prepared_location][0] == (originals(engagement) / "w2.pdf").read_bytes()
    [row] = read_index(engagement)
    assert row.decision == FILED and row.prepared_location == filed.prepared_location


def test_a_parked_copy_dragged_into_a_request_folder_is_file_moved_and_comes_back_as_needs_review(
        engagement):
    from tracker.index import FILE_MOVED, moved_to

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    home = engagement / parked.prepared_location
    wanderer = drag(home, prepared(engagement, "C01"))
    untouched = files_under(engagement)

    sort(engagement, today=DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED and moved_to(row) == location_of(engagement, wanderer)
    assert row.identifier == ""
    assert files_under(engagement) == untouched

    wanderer.rename(home)
    sort(engagement, today=DAY2)
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW               # a person re-decides in one click
    assert row.prepared_location == parked.prepared_location


def test_a_file_under_a_request_folder_matching_no_row_is_said_every_pass_and_never_moved(engagement):
    from tracker.filer import UNRECORDED_COPY

    stray = text_pdf(prepared(engagement, "A01") / "someone dragged this.pdf",
                     "Form W-2 Wage and Tax Statement 2025 Jane")
    said = UNRECORDED_COPY.format(location=location_of(engagement, stray))
    untouched = files_under(engagement)

    for day in (DAY1, DAY2):
        report = sort(engagement, today=day)
        assert [(e.name, e.error, e.left_in_place) for e in report.attention] == [
            (stray.name, said, True)
        ]
    assert ledger.read_events(engagement)[1:] == []         # nothing after the create
    assert files_under(engagement) == untouched


def test_a_copy_whose_bytes_are_not_the_originals_is_unlinked_and_the_drop_is_could_not_be_filed(
        engagement, monkeypatch):
    """Decision 17's row, reached by a copy that came out as something else -
    a virus scanner's stub, a sync client finishing a write for us. The
    working copy is removed rather than counted, and the original is the
    record, as it always is."""
    import tracker.filer as filer_module

    original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    before = original.read_bytes()

    def truncated(src, dst):
        filer_module.Path(dst).write_bytes(filer_module.Path(src).read_bytes()[:40])

    monkeypatch.setattr(shutil, "copy2", truncated)
    report = sort(engagement, today=DAY1)
    monkeypatch.undo()

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and report.filed == []
    # The firm's own sentence, whole: the filer's error is not a parser's
    # words, so the row keeps what it says (decision 190, the review's S3).
    assert "could not be filed (w2.pdf was copied to " in row.reason
    assert "the copy does not hold the original's bytes" in row.reason
    assert original_at(engagement, "w2.pdf") in row.reason
    assert not any(prepared(engagement, "A01").iterdir())    # nothing of it was left behind
    assert not list(review_dir(engagement).iterdir())
    assert (originals(engagement) / "w2.pdf").read_bytes() == before


def test_a_dehydrated_home_is_not_read_and_not_called_absent(engagement, monkeypatch):
    """Hashing a placeholder downloads it. A home the sync client has let go
    of is not looked at this pass, which is not the same as being gone."""
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    home = engagement / filed.prepared_location
    lines = len(ledger.read_events(engagement))

    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "is_cloud_placeholder", lambda p: p == home)
    read = counting_hashes(monkeypatch)
    report = sort(engagement, today=DAY2)

    assert report.attention == [] and report.errors == []
    assert str(home) not in read
    assert len(ledger.read_events(engagement)) == lines
    assert read_index(engagement)[0].decision == FILED


def test_the_sweep_on_a_read_only_prepared_folder_detects_and_touches_nothing(engagement):
    """The standing rule, on the new path: a pass that cannot write in the
    firm's folder still says what it found. Windows marks a file read-only
    and POSIX takes the write bits off the mode; both refuse a write, which
    is the claim, and neither refuses the read the sweep makes."""
    from tracker.index import FILE_MOVED, moved_to

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    wanderer = drag(engagement / filed.prepared_location, prepared(engagement, "C01"))
    copies = [p for p in (engagement / PREPARED_DIR_NAME).rglob("*") if p.is_file()]
    for path in copies:
        os.chmod(path, 0o444)
    try:
        untouched = files_under(engagement)
        report = sort(engagement, today=DAY2)

        assert report.errors == [] and len(report.attention) == 1
        [row] = read_index(engagement)
        assert row.decision == FILE_MOVED and moved_to(row) == location_of(engagement, wanderer)
        assert files_under(engagement) == untouched
    finally:
        for path in copies:
            os.chmod(path, 0o666)


def test_a_row_without_a_digest_is_never_swept(engagement, monkeypatch):
    """Decision 65: a row recorded without its bytes is nobody's. Nothing can
    prove a file is that row's copy, so the row is left exactly as it is -
    and the file nothing accounts for is said as what it is."""
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module
    from tracker.filer import UNRECORDED_COPY

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    real = filer_module.sha256_of

    held = set()

    def unreadable(path):
        if path.parent == originals(engagement) and path not in held:
            # Held for the one read that records the row: since decision
            # 187 the intent fingerprints a copy's source itself, a moment
            # later, so the copy is proved and the row keeps no bytes.
            held.add(path)
            raise PermissionError("held by the sync client")
        return real(path)

    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "sha256_of", unreadable)
    filed = sort(engagement, today=DAY1).filed[0]
    monkeypatch.undo()
    assert filed.digest == ""
    wanderer = drag(engagement / filed.prepared_location, prepared(engagement, "C01"))

    report = sort(engagement, today=DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILED and row.digest == ""        # never swept, never adopted
    assert row.prepared_location == filed.prepared_location
    assert events_named(engagement, ledger.COPY_MOVED) == []
    assert UNRECORDED_COPY.format(location=location_of(engagement, wanderer)) in [
        e.error for e in report.attention
    ]


def test_a_split_rows_second_copy_dragged_away_is_said_on_the_request_that_lost_it(engagement):
    """Decision 94 gives one row a working copy in each request that asked for
    a form the page names, so a row can lose one copy and keep another. The
    row is File Moved once, the note goes to the request whose folder is
    empty now, and the request that still holds its own copy says nothing
    about it and goes on counting it."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker import reasons
    from tracker.index import FILE_MOVED, moved_to
    from tracker.manifest import Status
    from tracker.scanner import scan_engagement

    drop(engagement, "scan0003.pdf",
         "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    [split] = sort(engagement, today=DAY1).filed
    assert len(split.filed_locations) == 2
    scan_engagement(engagement, today=DAY1)
    second = engagement / split.filed_locations[1]
    wanderer = drag(second, review_dir(engagement))
    untouched = files_under(engagement)

    sort(engagement, today=DAY2)
    report = scan_engagement(engagement, today=DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED
    assert moved_to(row) == location_of(engagement, wanderer)
    assert f"{split.filed_locations[1]} -> " in report.updates["C01"].validation_notes
    assert reasons.FILE_MOVED.code in report.updates["C01"].note_code_list
    assert report.updates["C01"].status == Status.MISSING
    # A01 still has the copy the split filed there, and is told nothing.
    assert report.updates["A01"].file_count == 1
    assert reasons.FILE_MOVED.code not in report.updates["A01"].note_code_list
    assert files_under(engagement) == untouched

# ---------------- an interrupted move is finished from the record (119) ----


def test_an_intent_is_written_before_the_first_file_operation_and_completed_by_the_row(engagement):
    """The shape of the whole decision: what a pass is about to do is on the
    record before it does it, and the row it then records completes it, so
    an uninterrupted pass leaves nothing open behind it."""
    from tracker.records import entry_to_json

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    sort(engagement, today=DAY1)

    events = ledger.read_events(engagement)
    assert [e[ledger.EVENT_KEY] for e in events] == [
        ledger.RULES_CHANGED, ledger.MOVING, ledger.FILED]
    [filing] = [e for e in events if e[ledger.EVENT_KEY] == ledger.MOVING]
    # One intent, and it carries the row it will record with the event that
    # will complete it. The move out of the inbox writes none (decision
    # 125): it is one rename, and an original in the year's folder with no
    # row is sorted where it lies.
    [row] = read_index(engagement)
    assert [op[ledger.OP_KEY] for op in filing[ledger.OPS_KEY]] == [ledger.OP_COPY]
    assert filing[ledger.DECIDED_BY_KEY] == ledger.BY_PASS
    assert filing[ledger.EVENT_KEY_AFTER] == ledger.FILED
    assert filing[ledger.ROW_KEY] == entry_to_json(row)
    assert filing[ledger.KEY_KEY] == row.pbc_location
    assert ledger.MOVING not in ledger.ROW_EVENTS
    assert open_intents(engagement) == []


def test_a_quiet_pass_appends_no_intent(engagement):
    """Nothing is about to happen, so nothing is written down: the record
    does not grow because a pass looked."""
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    lines = len(ledger.read_events(engagement))

    sort(engagement, today=DAY2)

    assert len(ledger.read_events(engagement)) == lines
    assert open_intents(engagement) == []


def test_a_drop_moved_by_a_killed_run_is_sorted_as_a_stray_dated_today(
        engagement, monkeypatch):
    """The original was moved out of the inbox and the run died before the
    working copy was made.

    Decision 125 retired the intent that move used to write - its home was
    the one engagement whose folder the inbox was in, and the inbox is the
    household's now - so the next pass finds an original with no row and
    sorts it where it lies (decision 23). The document is safe and it is
    filed; the one cost is the date, which is the day the pass found it and
    not the day it arrived. Decision 119 priced that, and this says it."""
    original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    arrived = digests_under(engagement)[location_of(engagement, original)]
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_the_move(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        sort(engagement, today=DAY1)

    assert read_index(engagement) == []              # nothing was recorded
    assert (originals(engagement) / "w2.pdf").exists()     # and the original is safe
    assert open_intents(engagement) == []            # and nothing is left half decided

    report = sort(engagement, today=DAY2)

    [filed] = report.filed
    assert filed.received == DAY2.isoformat()        # the drift decision 119 priced
    [row] = read_index(engagement)
    assert row.decision == FILED and row.received == DAY2.isoformat()
    assert (engagement / row.prepared_location).is_file()
    conserved(engagement, before, moves, added=[arrived])


def test_a_pass_killed_between_the_copy_and_the_record_finishes_without_a_second_copy(
        engagement, monkeypatch):
    """The copy was made and the batch never landed. The next pass proves
    the copy by its bytes, records the row the intent carried, and makes
    nothing a second time."""
    original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    arrived = digests_under(engagement)[location_of(engagement, original)]
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_at_the_record(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        sort(engagement, today=DAY1)

    assert read_index(engagement) == []
    assert len(list(prepared(engagement, "A01").iterdir())) == 1
    assert open_intents(engagement)

    sort(engagement, today=DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILED and row.received == DAY1.isoformat()
    assert [p.name for p in prepared(engagement, "A01").iterdir()] == [row.filed_as]
    conserved(engagement, before, moves, added=[arrived])


# --------------------------------- every write whole or not there (d155) ----

#: A pass run in its own process and killed inside the working copy's copy,
#: half the bytes down - no clean-up of the pass's runs, as a power cut or
#: Task Scheduler's stop runs none (decision 155).
A_PASS_KILLED_MID_COPY = """
import datetime as dt
import os
import shutil
import sys
from pathlib import Path
sys.path[:0] = [sys.argv[2]]
from tracker import content_check
content_check.READ_IN_A_CHILD = False

def killed(source, target, *args, **kwargs):
    data = Path(source).read_bytes()
    with open(target, "wb") as handle:
        handle.write(data[: len(data) // 2])
        handle.flush()
        os.fsync(handle.fileno())
    os._exit(9)

shutil.copy2 = killed
from tests.builders import sort
sort(Path(sys.argv[1]), today=dt.date(2026, 7, 1))
"""


def a_household_pass(engagement, today):
    """One real pass over the household, as the schedule makes it: the sweep
    first, then the sort, the scan and the page."""
    from tracker.registry import discover_engagements, engagement_from
    from tracker.runner import REMINDERS_NEVER, run_household

    [run] = run_household(household_of(engagement), [engagement_from(engagement)],
                          today=today, reminders=REMINDERS_NEVER,
                          registry=discover_engagements(root_of(engagement)))
    return run


def test_a_copy_killed_half_way_leaves_no_file_under_the_proper_name(engagement):
    """Decision 155, A-F1. The pass is killed inside the working copy's copy
    with half the bytes written. Nothing holds the working copy's name - the
    half is in a temp no walk reads - and the next pass sweeps the temp,
    finishes the filing from the intent (decision 119) and copies it whole.
    Before 155 the half kept the proper name, the row parked, and a person
    filing it left the half counted."""
    import subprocess

    original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    whole = original.read_bytes()
    store.close()
    done = subprocess.run([sys.executable, "-c", A_PASS_KILLED_MID_COPY, str(engagement),
                           str(Path(__file__).resolve().parents[1])],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 9, done.stderr
    a01 = engagement / PREPARED_DIR_NAME             # the copy and its temp sit here (decision 168)
    left = sorted(p.name for p in a01.iterdir() if p.is_file())
    assert [name for name in left if not name.endswith(TEMP_SUFFIX)] == []  # nothing under a name
    assert len(left) == 1 and (a01 / left[0]).stat().st_size == len(whole) // 2
    assert (originals(engagement) / "w2.pdf").read_bytes() == whole
    assert open_intents(engagement)

    run = a_household_pass(engagement, DAY2)

    assert not run.error, run.error
    [row] = read_index(engagement)
    assert row.decision == FILED and row.received == DAY1.isoformat()
    assert [p.name for p in a01.iterdir() if p.is_file()] == [row.filed_as]  # the temp is gone
    assert (engagement / row.prepared_location).read_bytes() == whole       # copied whole
    assert not open_intents(engagement)


def test_a_pass_sweeps_the_readme_temp_so_the_inbox_is_not_syncing(engagement):
    """The client-facing half of A-F6: the README's temp in ``Drop files
    here`` read as one more file syncing every pass. The household pass
    sweeps it before the inbox is read."""
    from tracker.scaffold import README_FIRST_LINE

    stranded = inbox_of(engagement) / f"{README_NAME}.{os.getpid()}.0f1e2d3c.tmp"
    stranded.write_text(f"{README_FIRST_LINE}\r\nhalf a li", encoding="utf-8")

    run = a_household_pass(engagement, DAY1)

    assert not stranded.exists()
    assert run.waiting == 0 and not run.error, run


def test_a_client_file_shaped_like_the_readme_temp_is_never_deleted(engagement, monkeypatch):
    """The inbox is the client's, and a client's file may carry any name -
    the README temp's exact shape, with a process number that is not
    running, included. The sweep takes such a file only when it reads as
    the firm's README (decision 190, revising 179's residual); a client's
    file of that name is left byte for byte and counted with the files
    still arriving - a short one too, when it is not a start of the
    README's first line."""
    import tracker.copies as copies_module

    monkeypatch.setattr(copies_module, "pid_alive", lambda pid: False)
    theirs = inbox_of(engagement) / f"{README_NAME}.4242.0f1e2d3c.tmp"
    theirs.write_bytes(b"%PDF-1.4 a client's own document")
    short = inbox_of(engagement) / f"{README_NAME}.4243.1a2b3c4d.tmp"
    short.write_bytes(b"HOW TO SEND US X")

    run = a_household_pass(engagement, DAY1)

    assert theirs.read_bytes() == b"%PDF-1.4 a client's own document"
    assert short.read_bytes() == b"HOW TO SEND US X", "not the firm's text, so not the machine's"
    assert run.waiting == 2 and not run.error, run


def test_a_readme_temp_the_firm_left_empty_or_cut_in_its_first_line_is_swept(
        engagement, monkeypatch):
    """A kill between making the README's temp and writing its first line
    whole left a file that holds only the start of the firm's own text - or
    nothing - which the README's own test reads as the client's. It sat in
    the client's shared inbox for good, counted as still arriving every
    pass (the review's S5). Empty, or a start of the README's first line,
    it holds nothing of the client's, and the sweep takes it."""
    import tracker.copies as copies_module
    from tracker.scaffold import README_FIRST_LINE

    monkeypatch.setattr(copies_module, "pid_alive", lambda pid: False)
    empty = inbox_of(engagement) / f"{README_NAME}.4243.1a2b3c4d.tmp"
    empty.write_bytes(b"")
    cut = inbox_of(engagement) / f"{README_NAME}.4244.2b3c4d5e.tmp"
    cut.write_bytes(README_FIRST_LINE.encode("ascii")[:9])
    whole_line = inbox_of(engagement) / f"{README_NAME}.4245.3c4d5e6f.tmp"
    whole_line.write_bytes(README_FIRST_LINE.encode("ascii"))

    run = a_household_pass(engagement, DAY1)

    left = [path.name for path in (empty, cut, whole_line) if path.exists()]
    assert left == [], left
    assert run.waiting == 0 and not run.error, run


def test_a_power_loss_mid_copy_leaves_a_truncated_file_that_is_named_and_the_row_parks(
        engagement, monkeypatch):
    """The wreck of a copy the power cut in half - which, since decision 155,
    only an older build could have left under the proper name (a killed copy
    leaves its temp now), or a person's own file sitting there. Nothing at
    that path is touched - the machine never deletes what it finds - the row parks with
    a working copy of its own, the file is named every pass, and the
    request reads Missing with the firm's own note instead of Failed
    Validation for a document the client sent correctly."""
    import tracker.actions as actions_module
    import tracker.intents as intents_module
    from tracker import reasons
    from tracker.manifest import Status
    from tracker.scanner import scan_engagement

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    def power_loss(source, target, *, root, expect="", cache=None):
        Path(target).write_bytes(b"%PDF-1.4 half")   # nothing tidies up after a power cut
        raise KeyboardInterrupt

    for module in (intents_module, actions_module):
        monkeypatch.setattr(module, "_copy_whole", power_loss)
    with pytest.raises(KeyboardInterrupt):
        sort(engagement, today=DAY1)
    monkeypatch.undo()

    truncated = prepared(engagement, "A01") / "A01 - W-2 Wage Statements - TY2025.pdf"
    assert truncated.read_bytes() == b"%PDF-1.4 half"
    original = originals(engagement) / "w2.pdf"
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)

    report = sort(engagement, today=DAY2)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == ""
    assert row.code == reasons.INTERRUPTED_MOVE.code
    assert location_of(engagement, truncated) in row.reason
    assert truncated.read_bytes() == b"%PDF-1.4 half"          # never touched
    parked = engagement / row.prepared_location
    assert parked.parent.name == REVIEW_DIR_NAME
    assert parked.read_bytes() == original.read_bytes()        # made from the original
    assert any(reasons.INTERRUPTED_MOVE.marker in e.error for e in report.attention)

    a01 = scan_engagement(engagement, today=DAY2).updates["A01"]
    assert a01.status == Status.MISSING and a01.file_count == 0
    assert reasons.INTERRUPTED_MOVE.code in a01.note_code_list
    conserved(engagement, before, moves, added=[digests_under(engagement)[row.prepared_location]])


# ============ one inbox, several returns (decision 125) ====================
#
# A household with a business and its owner's 1040 has one folder to drop
# into, so the sort judges each drop against every return of the open year
# and files it where exactly one accepts it. These are the claims about
# that, and about what a person's actions and a killed run do once an
# original lives in the other tree.


#: One household with two returns of the open year, from
#: ``tests/filer_helpers.py``: named once so that a test here can ask for it.
two_returns = filer_helpers.two_returns


def test_one_inbox_feeds_every_return_of_the_open_year_and_a_drop_files_where_exactly_one_accepts(
        two_returns):
    personal, business = two_returns
    drop(personal, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(personal, "tb.pdf", "Trial balance as of December 31 2025")

    done = sort_all(two_returns, today=DAY1)
    first, second = done[personal], done[business]

    # One inbox, one folder of originals, and each document filed under the
    # one return whose requests accept it.
    assert inbox_of(personal) == inbox_of(business)
    assert originals(personal) == originals(business)
    assert [e.original_name for e in first.filed] == ["w2.pdf"]
    assert [e.original_name for e in second.filed] == ["tb.pdf"]
    assert sorted(p.name for p in originals(personal).iterdir()) == ["tb.pdf", "w2.pdf"]
    assert [p.name for p in inbox_of(personal).iterdir()] == [README_NAME]

    for engagement, name in ((personal, "w2.pdf"), (business, "tb.pdf")):
        [row] = read_index(engagement)
        assert row.decision == FILED
        assert row.pbc_location == original_at(engagement, name)
        assert row.pbc_location.startswith("../")        # it crosses the two trees
        assert locate(engagement, row.pbc_location).is_file()
        assert (engagement / row.prepared_location).is_file()


def test_a_drop_accepted_by_two_returns_parks_in_the_first_accepting_return_naming_both(tmp_path):
    """Two 1040s share every row of their lists, so which person's W-2 this
    is cannot be read off the requests: a person chooses, and the sentence
    names every return that accepted it."""
    from tracker.filer import CONTESTED_BETWEEN_RETURNS

    john = make_engagement(tmp_path, ITEMS, household="Park Family",
                           return_name="1040 - John Park")
    sofia = make_engagement(tmp_path, ITEMS, household="Park Family",
                            return_name="1040 - Sofia Park")
    drop(john, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    done = sort_all([john, sofia], today=DAY1)
    assert done[sofia].handled == 0

    [parked] = done[john].review
    assert parked.decision == NEEDS_REVIEW
    assert parked.reason == CONTESTED_BETWEEN_RETURNS.format(
        listed="Park Family 2025 1040 - John Park: A01; "
               "Park Family 2025 1040 - Sofia Park: A01")
    assert read_index(sofia) == []                       # one row, in the first accepting return
    assert (john / parked.prepared_location).is_file()


def test_a_drop_no_return_accepts_parks_in_the_first_return_by_name(two_returns):
    personal, business = two_returns
    drop(personal, "notice.pdf", "an agency notice nothing asks for")

    first = sort(personal, returns=two_returns, today=DAY1)

    [parked] = first.review
    assert parked.original_name == "notice.pdf"
    assert read_index(business) == []
    assert (personal / parked.prepared_location).is_file()


def test_a_re_send_is_judged_by_whichever_returns_record_holds_the_bytes(two_returns):
    """The content hash says which return already holds the bytes, and that
    return's earlier decision says what the arrival is (decision 111)."""
    personal, business = two_returns
    drop(personal, "tb.pdf", "Trial balance as of December 31 2025")
    sort_all(two_returns, today=DAY1)

    drop(personal, "tb again.pdf", "Trial balance as of December 31 2025")
    done = sort_all(two_returns, today=DAY2)
    again, quiet = done[business], done[personal]

    [duplicate] = again.duplicates
    assert duplicate.reason.startswith("identical to tb.pdf")
    assert quiet.handled == 0 and read_index(personal) == []
    assert [r.decision for r in read_index(business)] == [FILED, DUPLICATE]


def test_a_stray_no_record_names_is_sorted_like_a_drop_across_the_household(two_returns):
    """Decision 23, across the returns: an original in the year's folder
    that no row of any return accounts for is sorted where it lies."""
    personal, business = two_returns
    text_pdf(originals(personal) / "tb.pdf",
             named_page("Trial balance as of December 31 2025"))

    second = sort_all(two_returns, today=DAY1)[business]

    assert read_index(personal) == []
    [row] = read_index(business)
    assert row.decision == FILED and row.original_name == "tb.pdf"
    assert second.filed and row.pbc_location == original_at(business, "tb.pdf")


def test_a_dry_run_of_the_household_pass_moves_nothing_and_takes_no_lock(two_returns):
    from tracker.locking import LOCK_FILENAME

    personal, business = two_returns
    drop(personal, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    before = files_under(personal)

    preview = sort(personal, returns=two_returns, today=DAY1, dry_run=True)

    assert [e.original_name for e in preview.filed] == ["w2.pdf"]
    assert preview.dry_run is True
    assert (inbox_of(personal) / "w2.pdf").is_file()          # nothing moved
    assert not any(originals(personal).iterdir())
    assert files_under(personal) == before
    assert read_index(personal) == [] and read_index(business) == []
    assert not any((one / LOCK_FILENAME).exists() for one in two_returns)


def test_the_household_pass_refuses_to_sort_a_return_whose_lock_it_does_not_hold(two_returns):
    """The locks are the caller's and the sort says so rather than writing
    outside them: a run that had no lock must not discover it half way."""
    from tracker.filer import FilingError, file_household_drops

    personal, business = two_returns
    drop(personal, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    with pytest.raises(FilingError, match="only while this run holds"):
        file_household_drops(inbox_of(personal), originals(personal), own=list(two_returns),
                             today=DAY1)
    assert (inbox_of(personal) / "w2.pdf").is_file()


def test_recovery_of_a_file_intent_locates_an_original_across_the_trees(engagement):
    """Decision 119's kill between the copy and the record, with the
    original in the year's folder: the intent's paths cross the two trees
    and the recovery reads them back through the one helper."""
    original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    arrived = digests_under(engagement)[location_of(engagement, original)]
    before = digests_under(engagement)
    moves = moves_made(pytest.MonkeyPatch())
    with pytest.MonkeyPatch.context() as patch:
        killed_after_ops(patch, after=1)
        with pytest.raises(KeyboardInterrupt):
            sort(engagement, today=DAY1)

    [intent] = open_intents(engagement)
    [operation] = intent[ledger.OPS_KEY]
    assert operation[ledger.FROM_KEY].startswith("../")     # the original, across the trees
    assert locate(engagement, operation[ledger.FROM_KEY]).is_file()

    sort(engagement, today=DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILED and row.received == DAY1.isoformat()
    assert (engagement / row.prepared_location).is_file()
    conserved(engagement, before, moves, added=[arrived])


# ============ the name on the page (decision 128) ==========================
#
# Two 1040s share every row of their request lists, so the keywords cannot
# say whose W-2 this is. The name on the page can: every return carries the
# people it is for, and a request that asks for a named document files only
# where one of that return's spellings is on the page.

MARIA = Person("spouse", "Maria Park", propose_spellings("Maria Park", "spouse"))
LANDSCAPING = Person("entity", "Park Landscaping LLC",
                     propose_spellings("Park Landscaping LLC", "entity"))

#: A trial balance is a bookkeeping export with no name on it, which is
#: what every catalog's trial-balance row says.
UNNAMED_BUSINESS = [
    RequestItem(
        identifier="B01", document="Trial Balance", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("trial balance",),
        named=False,
    ),
]


@pytest.fixture
def two_1040s(tmp_path):
    """One household, two 1040s, one person each: the plan's headline case."""
    john = make_engagement(tmp_path, ITEMS, household="Park Family",
                           return_name="1040 - John Park", people=(JOHN,))
    maria = make_engagement(tmp_path, ITEMS, household="Park Family",
                            return_name="1040 - Maria Park", people=(MARIA,))
    return john, maria


def test_a_w2_naming_one_spouse_files_to_that_1040_in_a_two_1040_household(two_1040s):
    """The headline case. Both lists accept the W-2 on its keywords; only
    one return's people are on the page, so only one is left when the
    exactly-one rule is asked, and the row says the name confirmed it."""
    john, maria = two_1040s
    drop(john, "w2.pdf", "Form W-2 Wage and Tax Statement 2025", who="Maria Park")

    done = sort_all(two_1040s, today=DAY1)

    assert done[john].handled == 0 and read_index(john) == []
    [filed] = done[maria].filed
    assert filed.decision == FILED and filed.identifier == "A01"
    assert filed.reason.endswith("; name confirmed (Maria Park)")


def test_a_w2_naming_nobody_on_the_list_parks_even_in_a_one_return_household(tmp_path):
    """Strict, with no soft fail-open: the request plainly wanted this
    document and the page names nobody on the return, so a person looks."""
    engagement = make_engagement(tmp_path, ITEMS, people=(JOHN,))
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025", who="Sofia Ruiz")

    [parked] = sort(engagement, today=DAY1).review

    assert parked.decision == NEEDS_REVIEW
    assert parked.code == reasons.NAME_NOT_ON_PAGE.code
    assert "1040 - Test Client" in parked.reason           # the return it parked in
    assert parked.candidates == "A01"                      # what the keywords said
    assert (engagement / parked.prepared_location).is_file()


def test_a_document_naming_another_returns_person_parks_and_names_them(tmp_path):
    """The page names somebody on another return of the household and
    nobody here: filing it here is exactly the failure the name tier
    exists to stop, so it parks and says whose it looks like."""
    john = make_engagement(tmp_path, ITEMS, household="Park Family",
                           return_name="1040 - John Park", people=(JOHN,))
    business = make_engagement(tmp_path, UNNAMED_BUSINESS, household="Park Family",
                               return_name="1120S - Park Landscaping",
                               people=(LANDSCAPING,))
    drop(john, "w2.pdf", "Form W-2 Wage and Tax Statement 2025",
         who="Park Landscaping LLC")

    done = sort_all([john, business], today=DAY1)

    assert read_index(business) == []
    [parked] = done[john].review
    assert parked.code == reasons.NAMES_ANOTHER_RETURN.code
    assert "Park Landscaping LLC (Park Family 2025 1120S - Park Landscaping)" in parked.reason
    # The evidence carries the other return's spelling, as a rule of its own.
    assert Evidence(RULE_NAME, "Park Landscaping LLC", WHERE_FIRST_PAGE, 1) \
        in parked.evidence_record["A01"]


def test_an_unnamed_request_files_on_keywords_alone_when_no_name_is_on_the_page(tmp_path):
    """A trial balance has no name on it, which is what the row says, so
    the keywords file it exactly as they did before the name tier."""
    business = make_engagement(tmp_path, UNNAMED_BUSINESS, people=(LANDSCAPING,))
    drop(business, "tb.pdf", "Trial balance as of December 31 2025", who="")

    [filed] = sort(business, today=DAY1).filed

    assert filed.decision == FILED and filed.identifier == "B01"
    assert "name confirmed" not in filed.reason          # there was no name to confirm
    assert RULE_NAME not in {e.rule for e in filed.evidence_record["B01"]}


def test_an_unnamed_request_is_vetoed_by_another_returns_name(tmp_path):
    """Unnamed means a *missing* name decides nothing - it does not mean
    the name is ignored. A schedule that plainly names the other return's
    person is not filed here."""
    business = make_engagement(tmp_path, UNNAMED_BUSINESS, household="Park Family",
                               return_name="1120S - Park Landscaping",
                               people=(LANDSCAPING,))
    john = make_engagement(tmp_path, ITEMS, household="Park Family",
                           return_name="1040 - John Park", people=(JOHN,))
    drop(business, "tb.pdf", "Trial balance as of December 31 2025", who="John Park")

    done = sort_all([business, john], today=DAY1)

    assert read_index(john) == []
    [parked] = done[business].review
    assert parked.code == reasons.NAMES_ANOTHER_RETURN.code
    assert "John Park (Park Family 2025 1040 - John Park)" in parked.reason


def test_a_return_with_no_people_parks_its_named_requests_with_the_add_them_sentence(tmp_path):
    """A return nobody has listed anybody on cannot confirm anything, and
    the fix is one edit rather than one spelling - so it is said
    differently."""
    engagement = make_engagement(tmp_path, ITEMS, people=())
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    [parked] = sort(engagement, today=DAY1).review

    assert parked.code == reasons.NO_PEOPLE_ON_FILE.code
    assert "add them in the editor" in parked.reason


def test_the_pass_reads_a_document_once_for_every_return_it_feeds(two_1040s, monkeypatch):
    """One inbox feeds every return of the open year, and a photo OCR'd
    once per return would cost a household twice what it should. The pass
    reads each drop once and hands that reading to every return."""
    import tracker.filer as filer_module

    john, _maria = two_1040s
    drop(john, "w2.pdf", "Form W-2 Wage and Tax Statement 2025", who="John Park")
    readings: list[str] = []
    real = filer_module.read_once

    def counted(path, questions):
        readings.append(path.name)
        return real(path, questions)

    monkeypatch.setattr(filer_module, "read_once", counted)

    sort_all(two_1040s, today=DAY1)

    assert readings == ["w2.pdf"]          # two returns, one reading


def test_a_confirmed_name_is_evidence_of_its_own_rule_and_says_where(tmp_path):
    """What the record keeps is the firm's own spelling that matched and
    where on the page it was said - a rule of evidence of its own, beside
    the keywords, and never a word of the document."""
    engagement = make_engagement(tmp_path, ITEMS, people=(JOHN,))
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025", who="John Park")

    [filed] = sort(engagement, today=DAY1).filed

    found = [e for e in filed.evidence_record["A01"] if e.rule == RULE_NAME]
    assert found == [Evidence(RULE_NAME, "John Park", WHERE_FIRST_PAGE, 1)]
    # The cell round-trips through the index, as every other evidence does,
    # and it carries the firm's own spelling - never the page's words.
    assert "John Park@first_page:1 name" in filed.evidence
    assert "Employee" not in filed.evidence


def test_ocr_text_still_files_on_required_keywords_only_with_the_name_confirmed(
        tmp_path, monkeypatch):
    """Decision 50 (as P282 revised it) through decision 128: OCR's reading
    routes on required keywords alone, and the name check reads the same
    words - so a scan OCR rescued files where its name confirms and nowhere
    else."""
    import tracker.content_check as content_check

    engagement = make_engagement(tmp_path, ITEMS, people=(JOHN,))
    text_pdf(inbox_of(engagement) / "scan0012.pdf", "")            # no text layer
    read_by_ocr = "Form W-2 Wage and Tax Statement 2025 Employee: John Park"
    monkeypatch.setattr(content_check, "_ocr_pdf", lambda path: read_by_ocr)

    [filed] = sort(engagement, today=DAY1).filed

    assert filed.identifier == "A01"
    assert filed.reason.endswith("; name confirmed (John Park)")


#: A made-up 1099-INT request that accepts on its looser keywords only, as
#: the 1040 catalog's does: a scan files under it on its form number (P282).
INT_ROW = RequestItem(
    identifier="A02", document="1099-INT Interest Income", period="TY2025",
    allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("1099-int",),
)


def test_a_scan_filed_on_its_form_number_still_needs_the_name_confirmed(tmp_path, monkeypatch):
    """P282 files a scan on its looser keywords when the title shows the
    request's own form number; guard 4 is decision 128's, untouched. A named
    request files only where the page names one of the return's people: John
    Park's 1099-INT files and says so, a made-up name that is not on the
    return parks with the name tier's own reason."""
    import tracker.content_check as content_check
    from tracker.router import MATCHED_FROM_SCAN

    reading = {"text": ""}
    monkeypatch.setattr(content_check, "_ocr_pdf", lambda path: reading["text"])

    def passed(recipient, root):
        engagement = make_engagement(root, [*ITEMS, INT_ROW], people=(JOHN,))
        reading["text"] = "\n".join([
            "Form 1099-INT Interest Income - 2025", "Payer: Harbor Test Bank",
            f"Recipient: {recipient}", "Box 1  Interest income  $1,842.17"])
        text_pdf(inbox_of(engagement) / "scan0001.pdf", "")         # no text layer
        return sort(engagement, today=DAY1)

    [filed] = passed("John Park", tmp_path / "confirmed").filed
    assert filed.identifier == "A02" and filed.decision == FILED
    assert filed.reason == f"{MATCHED_FROM_SCAN}; name confirmed (John Park)"

    [parked] = passed("Sofia Ruiz", tmp_path / "someone-else").review
    assert parked.decision == NEEDS_REVIEW
    assert parked.code == reasons.NAME_NOT_ON_PAGE.code


def test_a_scan_filed_on_its_form_number_into_an_unnamed_request_needs_no_name(tmp_path, monkeypatch):
    """Jason's ruling on Q1 (2026-10-11): decision 128 is unchanged for a
    scan filed on its form number. A request that is not named (a depreciation
    schedule, whose form prints no person) files by its keywords alone when
    the page names nobody, and no "name confirmed" note is made up; the same
    reading naming a person on another return of the household parks as
    that return's."""
    import tracker.content_check as content_check
    from tracker.router import MATCHED_FROM_SCAN

    depreciation = RequestItem(
        identifier="D04", document="Depreciation Schedule", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0,
        any_keywords=("form 4562", "depreciation schedule"), named=False,
    )
    reading = {"text": ""}
    monkeypatch.setattr(content_check, "_ocr_pdf", lambda path: reading["text"])
    lines = ["Form 4562 Depreciation and Amortization 2025",
             "Part I Election to expense certain property under section 179",
             "Part III MACRS depreciation, placed in service 2025"]

    def passed(extra, root):
        business = make_engagement(root, [depreciation], household="Park Family",
                                   return_name="1120S - Park Landscaping", people=(LANDSCAPING,))
        john = make_engagement(root, ITEMS, household="Park Family",
                               return_name="1040 - John Park", people=(JOHN,))
        reading["text"] = "\n".join([*lines, *extra])
        text_pdf(inbox_of(business) / "scan0001.pdf", "")           # no text layer
        return sort_all([business, john], today=DAY1)[business]

    [filed] = passed([], tmp_path / "nobody").filed
    assert filed.identifier == "D04" and filed.decision == FILED
    assert filed.reason == MATCHED_FROM_SCAN and "name confirmed" not in filed.reason

    [parked] = passed(["Taxpayer: John Park"], tmp_path / "other-return").review
    assert parked.code == reasons.NAMES_ANOTHER_RETURN.code


def test_a_decision_94_split_is_named_if_any_of_its_forms_request_is_named(tmp_path):
    """A sheet holding a W-2 and a 1098 is two documents and the W-2's row
    is named, so the strict rule applies to the whole page rather than to
    whichever request happened to be named first: the page names nobody
    here, and the split parks whole rather than filing the half that would
    otherwise pass."""
    both = [
        ITEMS[0],
        RequestItem(identifier="D01", document="Mortgage Interest", period="TY2025",
                    allowed_extensions=("pdf",), min_size_kb=0,
                    any_keywords=("1098",), named=False),
    ]
    engagement = make_engagement(tmp_path, both, people=(JOHN,))
    text_pdf(inbox_of(engagement) / "stack.pdf", "\n".join([
        "Form W-2 Wage and Tax Statement 2025",
        "a Employee's social security number 123-45-6789",
        "1 Wages, tips, other compensation 64,200.00",
        "Copy B To Be Filed With Employee's FEDERAL Tax Return",
        "Form 1098 Mortgage Interest Statement 2025",
        "1 Mortgage interest received from payer or borrower 12,411.08",
        "Recipient: Sofia Ruiz",
    ]))

    [parked] = sort(engagement, today=DAY1).review

    assert parked.code == reasons.NAME_NOT_ON_PAGE.code


#: A named row of a business's list: a bank statement without the entity's
#: name on it is not one, which is what every catalog's statement row says.
NAMED_BUSINESS = [
    RequestItem(
        identifier="D01", document="Bank Statements", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("bank statement",),
    ),
]


def test_a_name_parked_document_parks_in_the_first_return_that_accepted_it(tmp_path):
    """A parked row's home is the return of the first request that accepted
    the document (decision 125), and the name tier does not change that:
    the 1040's list never asked for a bank statement, so parking it in the
    1040's queue would put it where no row can take it and name a return
    nobody was asking about. It parks in the 1120S, whose row wanted it,
    with that return's own candidates."""
    john = make_engagement(tmp_path, ITEMS, household="Park Family",
                           return_name="1040 - John Park", people=(JOHN,))
    business = make_engagement(tmp_path, NAMED_BUSINESS, household="Park Family",
                               return_name="1120S - Park Landscaping",
                               people=(LANDSCAPING,))
    # First by folder order, and it accepts nothing here; the page names
    # nobody at all, so the name tier empties what the 1120S accepted.
    drop(john, "statement.pdf", "Bank statement for the period ending December 31 2025",
         who="")

    done = sort_all([john, business], today=DAY1)

    assert done[john].handled == 0 and read_index(john) == []
    [parked] = done[business].review
    assert parked.decision == NEEDS_REVIEW
    assert parked.code == reasons.NAME_NOT_ON_PAGE.code
    assert "Park Family 2025 1120S - Park Landscaping" in parked.reason
    assert parked.candidates == "D01"          # the accepting return's, not the 1040's
    assert (business / parked.prepared_location).is_file()


# ====== the household routes: the feed list (decisions 129 and 132) =======
#
# A client with a co-owned business keeps one drop folder, and the business
# lives in a household shared to its co-owners. So a household's drop folder
# feeds its own returns unless a person extends it to named return lines in
# other households - and a document filed to one of those rests under the
# folder that return lives in, seen by exactly that folder's sharing.


#: The father's household feeding the co-owned LLC's return line, from
#: ``tests/filer_helpers.py``: named once so that a test here can ask for it.
fed = filer_helpers.fed


LLC_LABEL = "Park & Lee LLC 2025 1120S - Park & Lee LLC"


def filed_across(father, llc, name, text, *, today=DAY1, clicked=DAY2):
    """A document the father drops for the LLC: parked at home by the pass,
    then handed over with the one click. The LLC's row."""
    drop(father, name, text, who="Park & Lee LLC")
    [waiting] = sort_all([father, llc], home=[father], today=today)[father].review
    return click(father, waiting, llc, today=clicked).target_entry


def test_a_drop_naming_a_fed_households_person_parks_at_home_for_one_click_and_nothing_moves_into_that_household(
        fed):
    """Decision 204, revising 132. The trial balance only the LLC's list
    wants, naming the LLC, is not filed there by the pass: it parks in the
    father's own queue, its original stays in his year folder, and the row
    keeps what the LLC's list accepted - so a person's one click can file
    it. Nothing is written into the LLC's record or its folders."""
    from tracker.records import WaitsFor

    father, llc = fed
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")

    done = sort_all([father, llc], home=[father], today=DAY1)

    assert done[llc].filed == [] and read_index(llc) == []
    [row] = read_index(father)
    assert row.decision == NEEDS_REVIEW and row.identifier == ""
    assert row.code == reasons.NAMED_ACROSS_HOUSEHOLDS.code
    assert row.reason.startswith("Names Park & Lee LLC, who is on " + LLC_LABEL)
    assert row.waiting_for == WaitsFor("Park & Lee LLC", "1120S - Park & Lee LLC", ("B01",), "")
    assert f"{LLC_LABEL} / B01" in parse_evidence(row.evidence)
    assert row.pbc_location == original_at(father, "tb.pdf")
    assert [p.name for p in originals(father).iterdir()] == ["tb.pdf"]
    assert not originals(llc).exists() or not any(originals(llc).iterdir())
    assert (father / row.prepared_location).is_file()
    assert [p.name for p in inbox_of(father).iterdir()] == [README_NAME]
    rows_rest_at_home(father, llc)


def test_the_one_click_files_the_waiting_document_where_it_waits_and_releases_the_row_here(fed):
    """The click is decision 132's hand-over with nothing picked: the
    original moves under the LLC's folder, the working copy is made there,
    the parked copy here goes and the row here is released. The LLC's row
    is the person's own filing, dated their day, and quotes the parked
    sentence, so the confirmed spelling travels with it."""
    from tracker.filer import ASSIGNED_BY_PERSON, DROPPED_ELSEWHERE, RELEASED_TO

    father, llc = fed
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    [waiting] = sort_all([father, llc], home=[father], today=DAY1)[father].review

    done = click(father, waiting, llc, seq=seq_of(father, waiting))

    assert done.moved_original is True and done.label == LLC_LABEL
    assert read_index(father) == []
    [taken] = read_index(llc)
    assert taken == done.target_entry
    assert taken.decision == FILED and taken.identifier == "B01" and taken.waits_for == ""
    assert taken.pbc_location == original_at(llc, "tb.pdf")
    assert taken.reason == (f"{ASSIGNED_BY_PERSON} on {DAY2.isoformat()}; "
                            f"{DROPPED_ELSEWHERE.format(household='Park Family')}; was: {waiting.reason}")
    assert [p.name for p in originals(llc).iterdir()] == ["tb.pdf"]
    assert not any(originals(father).iterdir())
    assert (llc / taken.prepared_location).is_file()
    assert not (father / waiting.prepared_location).exists()
    last = ledger.read_events(father)[-1]
    assert last[ledger.EVENT_KEY] == ledger.RELEASED
    assert last[ledger.REASON_KEY] == RELEASED_TO.format(label=LLC_LABEL, identifier="B01")
    rows_rest_at_home(father, llc)


def test_the_one_click_is_refused_when_its_return_is_no_longer_fed_or_its_request_is_gone(fed, tmp_path):
    """R-8: the claim is resolved at the click, never trusted. A return the
    feed list no longer names resolves to nothing; a request removed or
    marked N/A since refuses in the hand-over's own words; a click naming
    any other return than the claim's is refused. The row stays parked."""
    from tracker.filer import waiting_target
    from tracker.manifest import Override

    father, llc = fed
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    [waiting] = sort_all([father, llc], home=[father], today=DAY1)[father].review
    assert waiting_target(waiting.waiting_for, [father, llc]) == llc
    assert waiting_target(waiting.waiting_for, [father]) is None       # the feed trimmed

    other = make_engagement(tmp_path, BUSINESS, household="Lee Family",
                            return_name="1120S - Park & Lee LLC")
    with pytest.raises(FilingError, match="waits for Park & Lee LLC / 1120S - Park & Lee LLC"):
        click(father, waiting, other)

    info = load_engagement_info(llc)
    save_rules(llc, [replace(BUSINESS[0], manual_override=Override.NOT_APPLICABLE)], info)
    with pytest.raises(FilingError, match="clear the override first"):
        click(father, waiting, llc)
    save_rules(llc, [replace(BUSINESS[0], identifier="B02")], info)
    with pytest.raises(FilingError, match="no request 'B01'"):
        click(father, waiting, llc)

    assert read_index(father) == [waiting] and read_index(llc) == []
    rows_rest_at_home(father, llc)


DANA = (Person("taxpayer", "Dana Reyes", propose_spellings("Dana Reyes", "taxpayer")),)


def daughter(tmp_path, items):
    """The runbook's second shape: an adult daughter's return in her own
    household, fed by her father's drop folder."""
    from tracker.records import Feed

    father = make_engagement(tmp_path, ITEMS, household="Park Family",
                             return_name="1040 - John Park", people=FATHER)
    dana = make_engagement(tmp_path, items, household="Dana Reyes",
                           return_name="1040 - Dana Reyes", people=DANA)
    feeding(tmp_path, [Feed("Dana Reyes", "1040 - Dana Reyes")])
    return father, dana


def test_a_consolidated_statement_waiting_for_another_household_files_whole_with_its_also_answers_on_the_click(
        tmp_path):
    """Decision 146 across the click: the claim records the Also Answers the
    daughter's list gave the broker's statement, and the click files it
    whole under her 1099-B row with that cell - so her 1099-INT/DIV row
    counts it and her letter does not ask for what was sent."""
    from tracker.manifest import validated
    from tracker.scanner import scan_engagement
    from tracker.templates import template_items

    items = [replace(i, min_size_kb=0) for i in validated(template_items("1040", year=2025))]
    father, dana = daughter(tmp_path, items)
    drop(father, "Schwab 2025 1099.pdf", SCHWAB_146, who="Dana Reyes")
    [waiting] = sort_all([father, dana], home=[father], today=DAY1)[father].review
    claim = waiting.waiting_for
    assert claim.identifiers == ("E01",) and claim.answers

    click(father, waiting, dana)

    [taken] = read_index(dana)
    assert taken.identifier == "E01" and taken.also_filed == ""
    assert taken.answers == claim.answers
    assert {identifier for identifier, _ in taken.answered} >= {"A02"}
    scan_engagement(dana, today=DAY2)
    assert _status(dana, "A02").file_count >= 1
    rows_rest_at_home(father, dana)


def test_a_page_naming_two_forms_waiting_for_another_household_gets_a_copy_for_each_on_the_click(tmp_path):
    """Decision 94 across the click: the claim lists both forms' requests,
    and the click makes one working copy under each - as the pass would have
    - on one row for the one original."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines

    father, dana = daughter(tmp_path, ITEMS)
    drop(father, "scan0003.pdf", "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)),
         who="Dana Reyes")
    [waiting] = sort_all([father, dana], home=[father], today=DAY1)[father].review
    assert waiting.waiting_for.identifiers == ("A01", "C01")

    click(father, waiting, dana)

    [taken] = read_index(dana)
    assert taken.identifier == "A01" and taken.also_filed
    assert [name.split(" - ")[0] for name in taken.filed_names] == ["A01", "C01"]
    assert all((dana / location).is_file() for location in taken.filed_locations)
    rows_rest_at_home(father, dana)


def test_a_re_send_through_a_feed_of_a_document_the_other_household_lost_parks_and_the_click_counts_it_once(
        fed, monkeypatch):
    """The LLC's filed copy is gone and its original cannot be read to make
    it again (still syncing). The father sends the same bytes: routed afresh
    in the LLC's record, it parks at home for the click rather than filing
    there, and after the click the LLC's request counts the document once."""
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module
    from tracker.scanner import scan_engagement

    father, llc = fed
    first = filed_across(father, llc, "tb.pdf", "Trial balance as of December 31 2025")
    (llc / first.prepared_location).unlink()
    syncing = locate(llc, first.pbc_location)
    real = filer_module.is_cloud_placeholder
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "is_cloud_placeholder", lambda p: p == syncing or real(p))

    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    done = sort_all([father, llc], home=[father], today=DAY3)

    assert done[llc].filed == [] and read_index(llc) == [first]
    [waiting] = read_index(father)
    assert waiting.code == reasons.NAMED_ACROSS_HOUSEHOLDS.code
    assert waiting.waiting_for.identifiers == ("B01",)

    click(father, waiting, llc, today=DAY3)
    monkeypatch.undo()

    assert read_index(father) == []
    scan_engagement(llc, today=DAY3)
    assert _status(llc, "B01").file_count == 1
    rows_rest_at_home(father, llc)


def test_a_drop_parked_for_another_household_has_its_verdicts_kept_before_the_next_drop_is_read(
        fed, monkeypatch):
    """Decision 204 inside decision 189's sort: the park that waits for one
    click is a verdict like any other, kept as it is reached - when the
    next drop is read, the waiting page's verdicts are already in the
    store, and a pass stopped there would not read it again."""
    import tracker.content_check as content_check

    father, llc = fed
    drop(father, "a tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    drop(father, "b w2.pdf", "Form W-2 Wage and Tax Statement 2025", who="John Park")
    real, seen = content_check.extract, []

    def looking_at_the_store(path, **kwargs):
        seen.append(len(cache_rows(father)[1]) + len(cache_rows(llc)[1]))
        return real(path, **kwargs)

    monkeypatch.setattr(content_check, "extract", looking_at_the_store)
    done = sort_all([father, llc], home=[father], today=DAY1)

    assert [row.original_name for row in done[father].review] == ["a tb.pdf"]
    assert done[father].review[0].code == reasons.NAMED_ACROSS_HOUSEHOLDS.code
    assert seen[0] == 0 and seen[-1] >= 1


def test_a_drop_in_the_other_households_own_inbox_still_files_on_the_pass(fed):
    """R-9 (a): in the LLC's own inbox its return is its own, and the pass
    files there as it always has."""
    father, llc = fed
    drop(llc, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")

    [row] = sort_all([llc], today=DAY1)[llc].filed

    assert row.identifier == "B01" and row.waits_for == ""
    assert row.pbc_location == original_at(llc, "tb.pdf")
    assert read_index(father) == []


def test_an_unnamed_drop_across_households_parks_as_before_and_carries_no_waits_for(tmp_path):
    """R-5: a page naming nobody keeps decision 137 B2's park and the full
    picker - a one-click offer on it would make the unsafe action easy."""
    from tracker.records import Feed

    father = make_engagement(tmp_path, ITEMS, household="Park Family",
                             return_name="1040 - John Park", people=FATHER)
    llc = make_engagement(tmp_path, [replace(BUSINESS[0], named=False)], household="Park & Lee LLC",
                          return_name="1120S - Park & Lee LLC", people=LLC_PEOPLE)
    feeding(tmp_path, [Feed("Park & Lee LLC", "1120S - Park & Lee LLC")])
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="")

    [row] = sort_all([father, llc], home=[father], today=DAY1)[father].review

    assert row.code == reasons.UNNAMED_ACROSS_HOUSEHOLDS.code
    assert row.waits_for == "" and row.waiting_for is None
    assert read_index(llc) == []


def test_the_pass_never_moves_an_original_into_another_household(fed, tmp_path):
    """The guard behind R-1: over every road the feed has - a named page, an
    unnamed one, a vetoed W-2, a set-aside re-send - no move the pass decides
    (``BY_PASS``) in either record lands under the LLC's household, and the
    LLC's record and folders hold nothing the pass put there."""
    from tracker.layout import client_household_dir, private_household_dir

    father, llc = fed
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    drop(father, "tb unnamed.pdf", "Trial balance as of December 31 2025 unnamed", who="")
    drop(father, "w2.pdf", "Form W-2 Wage and Tax Statement 2025", who="Park & Lee LLC")
    sort_all([father, llc], home=[father], today=DAY1)
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    sort_all([father, llc], home=[father], today=DAY2)

    theirs = (client_household_dir(tmp_path, "Park & Lee LLC"),
              private_household_dir(tmp_path, "Park & Lee LLC"))
    for record in (father, llc):
        for event in ledger.read_events(record):
            if event[ledger.EVENT_KEY] != ledger.MOVING:
                continue
            assert event[ledger.DECIDED_BY_KEY] == ledger.BY_PASS
            for op in event[ledger.OPS_KEY]:
                target = locate(record, op[ledger.TO_KEY])
                assert not any(target.is_relative_to(folder) for folder in theirs), op
    assert read_index(llc) == []
    assert not originals(llc).exists() or not any(originals(llc).iterdir())
    rows_rest_at_home(father, llc)


def test_a_returning_original_still_goes_home_across_households(fed):
    """R-9 (d): the put-back-home road is not a filing. The LLC's original of
    a document handed over to it vanished, and the same bytes come back
    through the father's drop folder: they go home to the LLC's row, as
    decision 157 says, and no new row is written anywhere."""
    father, llc = fed
    first = filed_across(father, llc, "tb.pdf", "Trial balance as of December 31 2025")
    locate(llc, first.pbc_location).unlink()

    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    sort_all([father, llc], home=[father], today=DAY3)

    [row] = read_index(llc)
    assert (row.pbc_location, row.digest) == (first.pbc_location, first.digest)
    assert locate(llc, first.pbc_location).is_file()
    assert read_index(father) == []
    rows_rest_at_home(father, llc)


def test_a_drop_that_fails_the_name_check_parks_in_the_dropping_household_naming_the_fed_return(fed):
    """A W-2 the father's list plainly wants, with the LLC's name on the
    page: the name tier vetoes it, and it parks where it was dropped - in
    the dropping household, with the fed return named by its label."""
    father, llc = fed
    drop(father, "w2.pdf", "Form W-2 Wage and Tax Statement 2025", who="Park & Lee LLC")

    done = sort_all([father, llc], home=[father], today=DAY1)

    assert read_index(llc) == []
    [parked] = done[father].review
    assert parked.decision == NEEDS_REVIEW
    assert parked.code == reasons.NAMES_ANOTHER_RETURN.code
    assert "Park & Lee LLC 2025 1120S - Park & Lee LLC" in parked.reason
    assert parked.pbc_location == original_at(father, "w2.pdf")     # it rests where it was dropped
    assert (father / parked.prepared_location).is_file()


def test_nothing_ever_routes_to_a_return_outside_the_feed_list(fed):
    """A document only an unfed return would accept parks. The feed list is
    a person's assembly and the only thing the sort reads: a return nobody
    extended the drop folder to is not judged, not filed into and not
    named."""
    father, llc = fed
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")

    first = sort(father, returns=[father], today=DAY1)

    [parked] = first.review
    assert parked.original_name == "tb.pdf"
    assert read_index(llc) == []
    assert [p.name for p in originals(father).iterdir()] == ["tb.pdf"]
    assert not originals(llc).exists() or not any(originals(llc).iterdir())


def test_a_re_drop_of_a_document_filed_to_a_fed_return_is_that_returns_duplicate(fed):
    """The bytes say which record already holds the document, and that
    record decides - wherever it lives. A second copy of the LLC's trial
    balance is the LLC's duplicate row, not a second arrival for the
    household that dropped it. Since decision 204 the document reaches the
    LLC by the one click, and the re-drop is the LLC's all the same."""
    father, llc = fed
    filed_across(father, llc, "tb.pdf", "Trial balance as of December 31 2025")

    drop(father, "tb again.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    done = sort_all([father, llc], home=[father], today=DAY3)

    assert done[father].handled == 0 and read_index(father) == []
    [duplicate] = done[llc].duplicates
    assert duplicate.reason.startswith("identical to tb.pdf")
    assert [r.decision for r in read_index(llc)] == [FILED, DUPLICATE]


def test_a_cross_household_original_mid_recovery_is_never_a_stray_of_the_dropping_household(
        fed, monkeypatch):
    """Between the intents and the move, the original is in the folder it was
    dropped in while the LLC's open filing intent names it. It is not a
    stray: it is spoken for, by a decision the records already hold, and a
    pass that cannot finish the move leaves it alone rather than sorting it
    a second time. Since decision 204 the only filing across households is
    a person's hand-over - here the one click, killed with both intents
    written; the kill matrix below walks every other point."""
    father, llc = fed
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    [waiting] = sort_all([father, llc], home=[father], today=DAY1)[father].review
    killed_between_the_two_intents(monkeypatch)
    with pytest.raises(KeyboardInterrupt):
        click(father, waiting, llc)
    monkeypatch.undo()
    assert open_intents(llc) and open_intents(father)
    assert [p.name for p in originals(father).iterdir()] == ["tb.pdf"]

    # A dry run finishes nothing, so the intents are still open and the file
    # is still in the dropping household's folder: it must not be sorted.
    preview = sort_all([father, llc], home=[father], today=DAY2, dry_run=True)
    assert all(report.handled == 0 for report in preview.values())

    sort_all([father, llc], home=[father], today=DAY3)

    [row] = read_index(llc)
    assert row.decision == FILED and row.pbc_location == original_at(llc, "tb.pdf")
    assert read_index(father) == [] and not any(originals(father).iterdir())
    rows_rest_at_home(father, llc)


# ---------- one after-routing road: the household road and the re-send road ----------
#
# A drop is settled after the router answers by one sequence - the name tier,
# the park across households, the filing, the park for no room - and two roads
# reach it: a first arrival, routed against every return the drop may feed
# (the household road), and a re-send whose earlier row a person set aside,
# routed afresh in the one return whose record holds the bytes (the re-send
# road, decision 111). The table is what each road writes today, written out
# rather than computed. The roads agree but for the park across households,
# where the re-send road carries no shortlist, none of the home's evidence and
# none of the name's on the wanting return, and lands in the household's first
# own return: that is Q-B, Jason's and open (P313), and the table holds it.

FATHER_LABEL = "Park Family 2025 1040 - John Park"

#: Two of the father's own rows that both take a trial balance, so his list
#: cannot choose between them and its routing names both: the home's
#: shortlist and evidence the household road's park across households
#: carries, and the re-send road's does not.
TWO_TRIAL_BALANCES = [
    RequestItem(identifier="D01", document="Schedule C Trial Balance", period="TY2025",
                allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("trial balance",)),
    RequestItem(identifier="D02", document="Rental Trial Balance", period="TY2025",
                allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("trial balance",)),
]

TRIAL_BALANCE = "Trial balance as of December 31 2025"
NEWSLETTER = "Garden club newsletter for the spring"


def _households(tmp_path, case, *, first):
    """The case's returns, by folder, with the label each is named by: the
    father's, and the LLC's in a household of its own, fed from his drop
    folder, where the case has one. ``first`` gives the return holding the
    re-send's earlier row the list it had at the first arrival."""
    from tests.builders import root_for_a_return_of
    from tracker.records import Feed

    root = tmp_path
    if case["deep"]:
        root = root_for_a_return_of(tmp_path, no_room_return(), household="Park Family",
                                    return_name="1040 - John Park")

    def rows(whose, final):
        return case["first"] if first and case["holder"] == whose and case["first"] is not None else final

    father = make_engagement(root, rows("father", case["home"]), household="Park Family",
                             return_name="1040 - John Park", people=FATHER)
    returns = {father: FATHER_LABEL}
    if case["llc"] is not None:
        llc = make_engagement(root, rows("llc", case["llc"]), household="Park & Lee LLC",
                              return_name="1120S - Park & Lee LLC", people=LLC_PEOPLE)
        feeding(root, [Feed("Park & Lee LLC", "1120S - Park & Lee LLC")])
        returns[llc] = LLC_LABEL
    return returns


def _settled(returns, case):
    """The father drops the case's page and the household's pass sorts it:
    the one row the pass wrote, and the label of the return whose record
    holds it."""
    father = next(iter(returns))
    before = {folder: read_index(folder) for folder in returns}
    drop(father, "page.pdf", case["text"], who=case["who"])
    sort_all(list(returns), home=[father], today=DAY2)
    [(label, row)] = [(label, row) for folder, label in returns.items()
                      for row in read_index(folder) if row not in before[folder]]
    return _row(label, row.decision, row.reason, row.code, candidates=row.candidates,
                evidence=row.evidence, waits_for=row.waits_for, filed_to=row.identifier)


def _by_the_household_road(tmp_path, case):
    """A first arrival: routed against every return the father's drop folder
    feeds."""
    return _settled(_households(tmp_path / "household", case, first=False), case)


def _by_the_resend_road(tmp_path, case):
    """The same page sent again: its first arrival parked in the holding
    return's own inbox and a person set it aside, the list gained what takes
    it where the case says so, and the father's drop is routed afresh in the
    return whose record holds the bytes (decision 111)."""
    from tracker.actions import dismiss_review_file

    returns = _households(tmp_path / "resend", case, first=True)
    holder = list(returns)[0 if case["holder"] == "father" else 1]
    drop(holder, "page.pdf", case["text"], who=case["who"])
    [parked] = sort_all([holder], today=DAY1)[holder].review
    dismiss_review_file(holder, parked.pbc_location, "nothing asks for it yet", today=DAY1)
    if case["first"] is not None:
        final = case["home"] if case["holder"] == "father" else case["llc"]
        save_rules(holder, final, load_engagement_info(holder))
    return _settled(returns, case)


#: The sentence every row the re-send road writes carries, written out: the
#: earlier row quoted whole (decision 111) - first in a park's reason, after
#: the routing's own in a filing's.
SET_ASIDE = ("set aside as not requested (not requested, by a person on 2026-07-01 "
             "(nothing asks for it yet); was: matched no request); the client sent it again")


def _row(record, decision, reason, code, *, candidates="", evidence="", waits_for="", filed_to=""):
    """One row as the table writes it, with the label of the return whose
    record holds it: the cells R4.3.1 names, and the decision. ``filed_to``
    is the request the row is filed under, empty for a park."""
    return {"record": record, "decision": decision, "reason": reason, "code": code,
            "candidates": candidates, "waits_for": waits_for, "evidence": evidence,
            "filed_to": filed_to}


def _settle_table():
    """Each case: what it is made of, the household road's row (None where
    that road has no counterpart) and the re-send road's, written out.

    The no-room sentence's two numbers are the machine's limit
    (``layout.path_limit``: 260, or 259 with long paths off), read the way
    every claim about room reads them; nothing else here is computed."""
    from tracker.layout import path_limit

    limit = path_limit()
    w2 = "A01: W-2@title:1 required, TY2025@title:1 date, John Park@first_page:1 name"
    homes = ("D01: trial balance@title:1 required, TY2025@title:1 date; "
             "D02: trial balance@title:1 required, TY2025@title:1 date")
    wanted = f"{LLC_LABEL} / B01: trial balance@title:1 required, TY2025@title:1 date"
    named = f"Names Park & Lee LLC, who is on {LLC_LABEL}, a return in another household; " \
            "it waits here for a person to file it there."
    unnamed = "Unnamed, so it was not filed into another household's return."
    no_room = (f"the working copy's path would be {limit + 1} characters at its shortest, past the "
               f"{limit} characters a .pdf copy may have; shorten the clients root, or this request's "
               "Short name in the editor")
    long_w2 = "A01: W-2@title:1 required, January 01 2025 - December 31 2025@title:1 date, " \
              "John Park@first_page:1 name"
    waits = "Park & Lee LLC / 1120S - Park & Lee LLC / B01"
    return {
        # 1. Filed: the father's own W-2, naming him.
        "1 filed": (
            dict(home=ITEMS, llc=None, holder="father", first=[ITEMS[1]], deep=False,
                 text="Form W-2 Wage and Tax Statement 2025", who="John Park"),
            _row(FATHER_LABEL, FILED,
                 "content matched this request's required keywords; name confirmed (John Park)",
                 "matched", candidates="A01", evidence=w2, filed_to="A01"),
            _row(FATHER_LABEL, FILED,
                 f"content matched this request's required keywords; {SET_ASIDE}; "
                 "name confirmed (John Park)",
                 "matched", candidates="A01", evidence=w2, filed_to="A01"),
        ),
        # 2. Parked as unrecognised: nothing on the list takes the page.
        "2 unrecognised": (
            dict(home=ITEMS, llc=None, holder="father", first=None, deep=False,
                 text=NEWSLETTER, who="John Park"),
            _row(FATHER_LABEL, NEEDS_REVIEW, "matched no request", "unmatched"),
            _row(FATHER_LABEL, NEEDS_REVIEW, f"{SET_ASIDE}; matched no request", "unmatched"),
        ),
        # 3. Parked across households, named: only the LLC's list takes it and
        # the page names the LLC. Q-B: the household road's row carries the
        # home's shortlist and evidence before the wanting return's, whose part
        # holds the name's RULE_NAME entry; the re-send road's carries neither.
        "3 across, named": (
            dict(home=[*ITEMS, *TWO_TRIAL_BALANCES], llc=BUSINESS, holder="llc", first=[], deep=False,
                 text=TRIAL_BALANCE, who="Park & Lee LLC"),
            _row(FATHER_LABEL, NEEDS_REVIEW, named, "named-across", candidates="D01, D02",
                 evidence=f"{homes}; {wanted}, Park & Lee LLC@first_page:1 name", waits_for=waits),
            _row(FATHER_LABEL, NEEDS_REVIEW, f"{SET_ASIDE}; {named}", "named-across",
                 evidence=wanted, waits_for=waits),
        ),
        # 4. Parked across households, unnamed: the LLC's row is unnamed and the
        # page names nobody. Q-B's shortlist and home evidence, as in case 3;
        # the wanting return's part is the same on both roads.
        "4 across, unnamed": (
            dict(home=[*ITEMS, *TWO_TRIAL_BALANCES], llc=[replace(BUSINESS[0], named=False)],
                 holder="llc", first=[], deep=False, text=TRIAL_BALANCE, who=""),
            _row(FATHER_LABEL, NEEDS_REVIEW, unnamed, "unnamed-across", candidates="D01, D02",
                 evidence=f"{homes}; {wanted}"),
            _row(FATHER_LABEL, NEEDS_REVIEW, f"{SET_ASIDE}; {unnamed}", "unnamed-across",
                 evidence=wanted),
        ),
        # 5. Parked for no room: Prepared leaves no room for the request's
        # shortest name (decision 131). The re-send road reaches it only with
        # the holding return at home.
        "5 no room": (
            dict(home=[replace(ROOM_ITEMS[0], period=LONG_PERIOD)], llc=None, holder="father",
                 first=[], deep=True, text="Form W-2 Wage and Tax Statement 2025", who="John Park"),
            _row(FATHER_LABEL, NEEDS_REVIEW, no_room, "no-room", candidates="A01", evidence=long_w2),
            _row(FATHER_LABEL, NEEDS_REVIEW, f"{SET_ASIDE}; {no_room}", "no-room", candidates="A01",
                 evidence=long_w2),
        ),
        # 6. Re-send only: the LLC's record holds the bytes, its named row takes
        # the page and the page names nobody, so the name keeps nothing. The row
        # lands in the LLC's own record, with what the name tier made of it.
        "6 the name keeps nothing": (
            dict(home=ITEMS, llc=BUSINESS, holder="llc", first=[], deep=False,
                 text=TRIAL_BALANCE, who=""),
            None,
            _row(LLC_LABEL, NEEDS_REVIEW,
                 f"{SET_ASIDE}; the page names none of this return's people ({LLC_LABEL}); "
                 "a person should confirm",
                 "name-absent", candidates="B01",
                 evidence="B01: trial balance@title:1 required, TY2025@title:1 date"),
        ),
        # 7. Re-send only: the LLC's record holds the bytes and nothing on its
        # list takes the page. The row lands in the LLC's own record, with the
        # routing's own reason.
        "7 nothing accepts": (
            dict(home=ITEMS, llc=BUSINESS, holder="llc", first=None, deep=False,
                 text=NEWSLETTER, who="Park & Lee LLC"),
            None,
            _row(LLC_LABEL, NEEDS_REVIEW, f"{SET_ASIDE}; matched no request", "unmatched"),
        ),
    }


SETTLE_CASES = ("1 filed", "2 unrecognised", "3 across, named", "4 across, unnamed", "5 no room",
                "6 the name keeps nothing", "7 nothing accepts")


@pytest.mark.parametrize("name", SETTLE_CASES)
def test_the_household_road_and_the_resend_road_settle_a_drop_the_same_way_but_for_the_across_park(
        tmp_path, name):
    """SPEC-architecture P4.3 (R4.3.1): one made-up page settled by both
    roads, and the literal row each writes, with the return whose record
    holds it. Written before the two roads became one function and kept
    unchanged across it, so the fold is shown to change neither road.

    The roads agree but in three things, each today's and each kept: the
    re-send road's rows say the client sent it again (decision 111); in a
    park across households (cases 3 and 4) the re-send road carries no
    shortlist, none of the home's evidence and, where the page named the
    other return's person, none of the name's evidence on the wanting
    return - Q-B, Jason's and open (P313); and a re-send whose bytes a
    return in another household holds parks there when the name keeps
    nothing or nothing accepts it (cases 6 and 7), which the household road
    has no counterpart for."""
    case, household_row, resend_row = _settle_table()[name]

    if household_row is not None:
        assert _by_the_household_road(tmp_path, case) == household_row
    assert _by_the_resend_road(tmp_path, case) == resend_row

    wanting = f"{LLC_LABEL} / B01"
    if name == "3 across, named":      # difference 10, by each road's own cell
        assert any(found.rule == RULE_NAME and found.term == "Park & Lee LLC"
                   for found in parse_evidence(household_row["evidence"])[wanting])
        assert not any(found.rule == RULE_NAME for found in parse_evidence(resend_row["evidence"])[wanting])
    if name == "4 across, unnamed":
        assert parse_evidence(household_row["evidence"])[wanting] == parse_evidence(resend_row["evidence"])[wanting]


# ------------- File under another return (decisions 129 and 132) -----------


def test_a_hand_over_moves_the_original_copies_the_working_copy_removes_the_parked_copy_and_records_both_records(
        fed):
    """The taking return's row is the person's own filing, the original
    rests under the household that return lives in, the working copy is
    made there and the parked copy here goes. And the dropping household
    keeps **no row** (decision 132): the row is released - gone from the
    index - and the journal's last line says which return took it."""
    from tracker.filer import RELEASED_TO, hand_over

    father, llc = fed
    parked = parked_notice(father)

    done = hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)

    assert done.moved_original is True
    assert done.label == "Park & Lee LLC 2025 1120S - Park & Lee LLC"
    assert done.entry == parked                        # the row as it was, for the app
    assert read_index(father) == []
    last = ledger.read_events(father)[-1]
    assert last[ledger.EVENT_KEY] == ledger.RELEASED
    assert last[ledger.KEY_KEY] == ledger_key(parked)
    assert last[ledger.REASON_KEY] == RELEASED_TO.format(label=done.label, identifier="B01")
    assert ledger.ROW_KEY not in last
    [taken] = read_index(llc)
    assert taken == done.target_entry
    assert taken.decision == FILED and taken.identifier == "B01"
    assert taken.pbc_location == original_at(llc, "notice.pdf")
    assert taken.reason.startswith("assigned by a person on 2026-07-09")
    # The bytes: one original, under the household the taking return lives
    # in, one working copy in its request folder, and nothing left here.
    assert [p.name for p in originals(llc).iterdir()] == ["notice.pdf"]
    assert not any(originals(father).iterdir())
    assert (llc / taken.prepared_location).is_file()
    assert not (father / parked.prepared_location).exists()
    rows_rest_at_home(father, llc)


def test_a_hand_over_within_one_household_moves_no_original_and_writes_the_same_two_intents(
        two_returns):
    """An original moves once, out of the inbox into the year's folder the
    client can see, and never again (decision 125) - which holds for every
    filing inside one household, hand-over included. And there is no
    special case for one household any more (decision 132): the same two
    intents are written, the release here and the filing there, and the
    filing has no move in it."""
    from tracker.filer import hand_over

    personal, business = two_returns
    drop(personal, "notice.pdf", "an agency notice nothing asks for")
    parked = sort(personal, returns=two_returns, today=DAY1).review[0]
    where = parked.pbc_location

    done = hand_over(personal, where, business, "B01", today=DAY2)

    assert done.moved_original is False
    assert read_index(personal) == []
    [taken] = read_index(business)
    assert taken.pbc_location == original_at(business, "notice.pdf")
    assert locate(business, taken.pbc_location) == locate(personal, where)
    assert "dropped in" not in taken.reason
    assert [p.name for p in originals(personal).iterdir()] == ["notice.pdf"]
    # The two intents, one in each record, each closed by its own record.
    [release] = [e for e in ledger.read_events(personal) if e[ledger.EVENT_KEY] == ledger.MOVING
                 and e[ledger.DECIDED_BY_KEY] == ledger.BY_PERSON]
    assert release[ledger.EVENT_KEY_AFTER] == ledger.RELEASED
    assert [op[ledger.OP_KEY] for op in release[ledger.OPS_KEY]] == [ledger.OP_REMOVE]
    [filing] = [e for e in ledger.read_events(business) if e[ledger.EVENT_KEY] == ledger.MOVING]
    assert filing[ledger.EVENT_KEY_AFTER] == ledger.ASSIGNED_BY_PERSON
    assert [op[ledger.OP_KEY] for op in filing[ledger.OPS_KEY]] == [ledger.OP_COPY]
    rows_rest_at_home(personal, business)


def test_a_re_drop_of_a_handed_over_document_is_the_taking_returns_duplicate(fed):
    """While the feed stands the client sending it again is the **taking**
    return's arrival - the record that has it decides, in its own record,
    as decision 111 says - and the dropping household still holds nothing."""
    from tracker.filer import DUPLICATE_OF_FILED, hand_over

    father, llc = fed
    parked = parked_notice(father)
    hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)
    [taken] = read_index(llc)

    drop(father, "notice again.pdf", "an agency notice nothing asks for")
    done = sort_all([father, llc], home=[father], today=DAY3)

    assert done[father].handled == 0 and read_index(father) == []
    [duplicate] = done[llc].duplicates
    assert duplicate.reason == DUPLICATE_OF_FILED.format(name="notice.pdf",
                                                         copy=taken.filed_as)
    assert [r.decision for r in read_index(llc)] == [FILED, DUPLICATE]


def test_a_re_drop_after_the_feed_is_trimmed_is_judged_as_the_households_own_document(
        fed, tmp_path):
    """Once the feed is trimmed the household that no longer feeds that
    return has no business recognising its documents, and holds no row to
    recognise them by (decision 132). A re-send is this household's own
    arrival: filed where exactly one of its own returns accepts it, parked
    otherwise - and the taking return is not touched."""
    from tracker.filer import hand_over

    father, llc = fed
    parked = parked_notice(father)
    hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)
    taken_before = read_index(llc)
    feeding(tmp_path, [])                       # a person trims the feed

    drop(father, "notice again.pdf", "an agency notice nothing asks for")
    drop(father, "w2.pdf", "Form W-2 Wage and Tax Statement 2025", who="John Park")
    first = sort(father, returns=[father], today=DAY3)

    assert first.duplicates == []
    [again] = first.review
    assert again.original_name == "notice again.pdf" and again.decision == NEEDS_REVIEW
    assert not again.reason.startswith("identical to")
    assert [row.original_name for row in first.filed] == ["w2.pdf"]
    assert read_index(llc) == taken_before
    rows_rest_at_home(father, llc)


@pytest.mark.parametrize("by", ("the one click", "a hand-over"))
def test_a_filing_never_takes_a_name_a_vanished_original_left_behind(fed, by):
    """A key is a location, and a location came free again: an original
    filed into the LLC and then removed by hand leaves its row behind,
    pointed at nothing (decision 109), and the next document of that name
    was handed the same place, so the same key - its row became the old
    row's next version and the old row vanished from every reader.

    Since decision 147 (ruling 9, audit F-1) a name a row still names is
    taken. Whichever hand-over files it - the one click on a page naming
    the LLC (decision 204) or the picker (decision 132) - the name is chosen by the one
    numbering function against the taking household-year's rows, so the
    new document rests beside the old name with a row of its own, and the
    old row goes on saying its original is missing."""
    from tracker.filer import ASSIGNED_BY_PERSON, hand_over

    father, llc = fed
    stale = filed_across(father, llc, "notice.pdf", "Trial balance as of December 31 2025",
                         clicked=DAY1)
    (originals(llc) / "notice.pdf").unlink()    # the client removed it by hand

    if by == "the one click":
        drop(father, "notice.pdf", "Trial balance as of December 31 2025 restated",
             who="Park & Lee LLC")
        [waiting] = sort_all([father, llc], home=[father], today=DAY2)[father].review
        done = click(father, waiting, llc)
        assert done.moved_original is True
    else:
        parked = parked_notice(father)
        done = hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)
        assert done.moved_original is True

    kept, taken = read_index(llc)
    assert kept == stale                                # the old row, untouched
    assert ledger_key(taken) != ledger_key(stale)       # a place, and a row, of its own
    assert taken.digest != stale.digest
    assert taken.decision == FILED and taken.identifier == "B01"
    assert taken.reason.startswith(ASSIGNED_BY_PERSON)
    assert taken.pbc_location == original_at(llc, "notice (2).pdf")
    assert read_index(father) == []
    # One original under the household the taking return lives in, and one
    # working copy made by this filing, in the request's folder and named
    # by its row; the earlier filing's copy is beside it, still its row's.
    assert [p.name for p in originals(llc).iterdir()] == ["notice (2).pdf"]
    copies = sorted(p.name for p in prepared(llc, "B01").iterdir())
    assert sorted(Path(row.filed_as).name for row in (kept, taken)) == copies


# The kill matrix of SPEC-129R §3.4 (decision 132): where the machine dies
# in a hand-over, by the step it had finished. Four writes (the release
# intent, the filing intent, the taking return's row, the release) and
# three file operations (the move, the copy, the removal of the parked
# copy), in that order.
HAND_OVER_KILL_POINTS = (
    "after the release intent",
    "after the filing intent",
    "after the move",
    "after the copy",
    "after the taking return's row",
    "after the parked copy went",
)
#: Which pass runs next: the dropping household's with the feed in place
#: (it holds both locks), the same household's after a person trimmed the
#: feed, or the taking return's own household's.
NEXT_PASSES = ("home with the feed", "home without the feed", "the taking return's")


def killed_after_the_nth_write(monkeypatch, n):
    """The machine dies just after the n-th record a decision writes -
    intents included - has reached the journal and the store."""
    real = store.record
    state = {"seen": 0, "died": False}

    def killing(conn, engagement_dir, *events):
        result = real(conn, engagement_dir, *events)
        state["seen"] += 1
        if state["seen"] == n and not state["died"]:
            state["died"] = True
            raise KeyboardInterrupt
        return result

    monkeypatch.setattr(store, "record", killing)
    return state


@pytest.mark.parametrize("next_pass", NEXT_PASSES)
@pytest.mark.parametrize("point", HAND_OVER_KILL_POINTS)
def test_a_hand_over_killed_at_every_point_is_finished_from_the_record_as_the_persons(
        fed, monkeypatch, tmp_path, point, next_pass):
    """Each record's half is its own intent, finished by its own
    household's pass with no lock it does not hold (decision 132). Walk
    every point of the matrix with every pass going next, then let the
    other household's pass run too, and ask of both records what decision
    119 asks: nothing overwritten, nothing moved twice, the store agreeing
    with the journal and no intent left open.

    - After the release intent alone the person's click is the whole cost:
      the row is released and the original, named by no row, is sorted
      again where it lies.
    - From the filing intent on, the decision lands whichever pass runs
      first, feed or no feed: a pass holding the taking return finishes the
      filing, the release waits for the dropping household's own pass, and
      a dropping pass that runs first leaves the original alone - another
      record's open intent names it (the lead's ruling R-1). There is no
      window that needs a person.
    """
    from tracker.filer import hand_over

    father, llc = fed
    parked = parked_notice(father)
    document = parked.digest
    before_father, before_llc = digests_under(father), digests_under(llc)
    moves = moves_made(monkeypatch)
    if point == "after the release intent":
        killed_after_the_nth_write(monkeypatch, 1)
    elif point == "after the filing intent":
        killed_after_the_nth_write(monkeypatch, 2)
    elif point == "after the move":
        killed_after_ops(monkeypatch, after=1)
    elif point == "after the copy":
        killed_after_ops(monkeypatch, after=2)
    elif point == "after the taking return's row":
        killed_after_the_nth_write(monkeypatch, 3)
    else:
        killed_after_ops(monkeypatch, after=3)
    with pytest.raises(KeyboardInterrupt):
        hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)
    real_moves = list(moves)
    monkeypatch.undo()
    moves = moves_made(monkeypatch)
    moves.extend(real_moves)

    if next_pass == "home with the feed":
        sort_all([father, llc], home=[father], today=DAY3)
    elif next_pass == "home without the feed":
        feeding(tmp_path, [])
        sort(father, returns=[father], today=DAY3)
        sort_all([llc], today=DAY3)
    else:
        sort_all([llc], today=DAY3)
        sort_all([father, llc], home=[father], today=DAY3)

    if point == "after the release intent":
        # The click is to make again: the document is the father's
        # arrival once more, parked where it lies, dated the day it was
        # sorted again.
        [again] = read_index(father)
        assert again.decision == NEEDS_REVIEW and again.digest == document
        assert again.pbc_location == parked.pbc_location and again.received == DAY3.isoformat()
        conserved(father, before_father, moves)          # one parked copy out, one in
        assert read_index(llc) == []
        conserved(llc, before_llc, moves)
    else:
        assert read_index(father) == []
        [taken] = read_index(llc)
        assert taken.decision == FILED and taken.identifier == "B01"
        assert taken.received == parked.received          # the day the client sent it
        assert "on 2026-07-09" in taken.reason            # dated the day the person decided
        assert taken.pbc_location == original_at(llc, "notice.pdf")
        assert (llc / taken.prepared_location).is_file()
        # The parked copy and the original leave this household; the
        # original and one working copy arrive in the other. Nothing twice.
        conserved(father, before_father, moves, gone=[document, document])
        conserved(llc, before_llc, moves, added=[document, document])
    rows_rest_at_home(father, llc)


def test_no_record_ever_holds_a_row_for_an_original_resting_under_another_household_once_no_intent_is_open(
        fed, monkeypatch, tmp_path):
    """The invariant behind the owner's sentence (decision 132), asked after
    a season's worth of the feed's roads in one pair of households: a page
    naming the fed return parks at home and is clicked over (decision 204),
    a W-2 naming the fed return parks at home, a click is killed between
    its move and its copy and recovered, a parked document is handed over,
    and a re-send arrives after the feed is trimmed. After each, every row
    of both records names an original under its own household's folder for
    the year."""
    from tracker.filer import hand_over

    father, llc = fed
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    drop(father, "w2.pdf", "Form W-2 Wage and Tax Statement 2025", who="Park & Lee LLC")
    sort_all([father, llc], home=[father], today=DAY1)
    rows_rest_at_home(father, llc)
    [tb] = [row for row in read_index(father) if row.original_name == "tb.pdf"]
    click(father, tb, llc, today=DAY1)
    rows_rest_at_home(father, llc)

    drop(father, "tb2.pdf", "Trial balance as of December 31 2025 second copy",
         who="Park & Lee LLC")
    sort_all([father, llc], home=[father], today=DAY2)
    [tb2] = [row for row in read_index(father) if row.original_name == "tb2.pdf"]
    killed_after_ops(monkeypatch, after=1)
    with pytest.raises(KeyboardInterrupt):
        click(father, tb2, llc)
    monkeypatch.undo()
    sort_all([father, llc], home=[father], today=DAY2)
    rows_rest_at_home(father, llc)

    [w2] = [row for row in read_index(father) if row.original_name == "w2.pdf"]
    hand_over(father, w2.pbc_location, llc, "B01", today=DAY2)
    rows_rest_at_home(father, llc)

    feeding(tmp_path, [])
    drop(father, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025", who="Park & Lee LLC")
    sort(father, returns=[father], today=DAY3)
    rows_rest_at_home(father, llc)
    assert [row.original_name for row in read_index(llc)] == ["tb.pdf", "tb2.pdf", "w2.pdf"]


def killed_between_the_two_intents(monkeypatch):
    """A hand-over dies with both intents written and nothing else done:
    the release open in the dropping record, the filing open in the taking
    one, every file where it was."""
    killed_after_the_nth_write(monkeypatch, 2)


@pytest.mark.parametrize("order", ("the taking pass during the dropping pass",
                                   "the taking pass after the dropping pass"))
def test_a_stray_named_by_another_records_open_intent_is_left_alone_by_the_pass(
        fed, monkeypatch, tmp_path, order):
    """The lead's ruling R-1 (decision 132). With the feed trimmed, the
    dropping household's own pass releases its row, and the original -
    still in its year folder, named by no row of its own - would be a
    stray. It is not: the taking return's open filing intent names that
    path with those bytes as the source of its move. So the pass never
    re-sorts, parks or records it, whether the taking return's pass runs
    in the middle of it (another process, its own lock) or after it; the
    document ends claimed by exactly one row, in the return that took it."""
    import tracker.actions as actions_module
    import tracker.filer as filer_module
    from tracker.filer import LEFT_FOR_ANOTHER_RETURN, hand_over

    father, llc = fed
    parked = parked_notice(father)
    killed_between_the_two_intents(monkeypatch)
    with pytest.raises(KeyboardInterrupt):
        hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)
    monkeypatch.undo()
    feeding(tmp_path, [])                       # a person trims the feed

    if order == "the taking pass during the dropping pass":
        real_record = filer_module._record
        ran = {"llc": False}

        def interleaved(engagement_dir, *args, **kwargs):
            if not ran["llc"] and engagement_dir == father:
                ran["llc"] = True
                sort_all([llc], today=DAY3)      # the other process's pass
            return real_record(engagement_dir, *args, **kwargs)

        for module in (filer_module, actions_module):
            monkeypatch.setattr(module, "_record", interleaved)
        first = sort(father, returns=[father], today=DAY3)
        monkeypatch.undo()
        assert ran["llc"]
    else:
        first = sort(father, returns=[father], today=DAY3)
        assert (originals(father) / "notice.pdf").is_file()     # left where it lies
        sort_all([llc], today=DAY3)

    assert first.handled == 0 and first.review == []
    said = [e.error for e in first.attention if e.name == "notice.pdf"]
    assert said == [LEFT_FOR_ANOTHER_RETURN.format(name="notice.pdf")]
    assert read_index(father) == []
    claimed = [row for row in read_index(father) + read_index(llc) if row.digest == parked.digest]
    assert len(claimed) == 1 and claimed[0].decision == FILED
    rows_rest_at_home(father, llc)


def test_the_taking_returns_recovery_finishes_the_move_after_the_dropping_pass_has_run(
        fed, monkeypatch, tmp_path):
    """Killed after the filing intent, the feed trimmed, the dropping
    household's pass first and then the taking return's (decision 132,
    ruling R-1): what §3.4 once called the one window that needs a person
    needs nobody. The taking return's recovery finishes the move and the
    copy, and the document is one row, Filed, in the return that took it,
    its original under that return's household."""
    from tracker.filer import hand_over

    father, llc = fed
    parked = parked_notice(father)
    before_father, before_llc = digests_under(father), digests_under(llc)
    killed_between_the_two_intents(monkeypatch)
    with pytest.raises(KeyboardInterrupt):
        hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)
    monkeypatch.undo()
    moves = moves_made(monkeypatch)
    feeding(tmp_path, [])

    sort(father, returns=[father], today=DAY3)
    sort_all([llc], today=DAY3)

    assert read_index(father) == []
    [taken] = read_index(llc)
    assert taken.decision == FILED and taken.identifier == "B01"
    assert "on 2026-07-09" in taken.reason
    assert taken.pbc_location == original_at(llc, "notice.pdf")
    assert [p.name for p in originals(llc).iterdir()] == ["notice.pdf"]
    assert not any(originals(father).iterdir())
    conserved(father, before_father, moves, gone=[parked.digest, parked.digest])
    conserved(llc, before_llc, moves, added=[parked.digest, parked.digest])
    rows_rest_at_home(father, llc)


def test_a_rebuilt_store_still_lets_the_taking_returns_recovery_finish_the_filing(
        fed, monkeypatch, tmp_path):
    """The reviewer's finding 3, as a regression claim (decision 132). Killed
    after the filing intent with the feed in place, and then the store is
    rebuilt - a new machine, a version bump - and the taking return's pass
    runs first, before anything has read the dropping household's record
    into the new store. Its recovery finishes the filing from its own
    record, and the dropping household's pass then finishes the release."""
    from tracker.filer import hand_over

    father, llc = fed
    parked = parked_notice(father)
    killed_between_the_two_intents(monkeypatch)
    with pytest.raises(KeyboardInterrupt):
        hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)
    monkeypatch.undo()
    store.close()
    monkeypatch.setenv(store.ENV_STORE, str(tmp_path / "app2" / store.STORE_FILENAME))
    # A new machine has no checkpoint: the old one is kept under another
    # name, as one left beside the program refuses a fresh one (186's
    # rebase review, MF1).
    old = tmp_path / "app" / checkpoint.CHECKPOINT_FILENAME
    old.rename(old.with_name(old.name + ".other-machine"))

    sort_all([llc], today=DAY3)
    [taken] = read_index(llc)
    assert taken.decision == FILED and taken.identifier == "B01", taken.reason
    assert taken.pbc_location == original_at(llc, "notice.pdf")

    sort_all([father, llc], home=[father], today=DAY3)
    assert read_index(father) == []
    assert [row.decision for row in read_index(llc)] == [FILED]
    rows_rest_at_home(father, llc)


def test_an_original_left_for_another_returns_filing_is_said_on_every_pass(
        fed, monkeypatch, tmp_path):
    """The lead's ruling R-3 (decision 132): an original a pass leaves alone
    because another return's unfinished filing names it is said, on the
    dropping household's first own return, on every pass it happens - by
    its name in the year folder, never a full path. An intent that never
    finishes (its return retired, unreadable, its pass never run) must not
    leave an original unrecorded in silence. Once the filing finishes, the
    sentence stops."""
    from tracker.filer import LEFT_FOR_ANOTHER_RETURN, hand_over

    father, llc = fed
    parked = parked_notice(father)
    killed_between_the_two_intents(monkeypatch)
    with pytest.raises(KeyboardInterrupt):
        hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)
    monkeypatch.undo()
    feeding(tmp_path, [])
    sentence = LEFT_FOR_ANOTHER_RETURN.format(name="notice.pdf")

    for day in (DAY2, DAY3):                     # the other return's pass never runs
        report = sort(father, returns=[father], today=day)
        assert [e.error for e in report.attention if e.name == "notice.pdf"] == [sentence]
        assert report.handled == 0 and read_index(father) == []
        assert (originals(father) / "notice.pdf").is_file()
    assert str(originals(father)) not in sentence

    sort_all([llc], today=DAY3)                  # the filing finishes
    report = sort(father, returns=[father], today=DAY3)
    assert all(e.error != sentence for e in report.attention)
    rows_rest_at_home(father, llc)


# ------------------------------------ decision 131: the room a return has ----


def test_the_numbered_suffix_is_counted_when_a_name_is_cut(tmp_path, path_setting):
    """Two files for one request under the same tight root: the second's
    ``(2)`` is counted in the same loop that cuts, so its document part
    gives up the suffix's four characters (less what the cut had to spare)
    and the pair is still one series - the same stem cut further, and the
    number after it."""
    from tracker.layout import path_limit

    items = [replace(ROOM_ITEMS[0], expected_count=2)]
    engagement = tight_return(tmp_path, OVER, items=items)
    drop(engagement, "w2-a.pdf", "Form W-2 Wage and Tax Statement 2025 employer one")
    drop(engagement, "w2-b.pdf", "Form W-2 Wage and Tax Statement 2025 employer two")

    report = sort(engagement, today=DAY1)

    assert len(report.filed) == 2
    folder = prepared(engagement, "A01")
    room = path_limit() - len(str(engagement / PREPARED_DIR_NAME)) - 1
    names = sorted(p.name for p in folder.iterdir())
    assert names == [f"A01 - W-2 Wa - {TIGHT_PERIOD} (2).pdf", f"A01 - W-2 Wage S - {TIGHT_PERIOD}.pdf"]
    assert all(len(name) <= room for name in names)
    second, first = names
    # One series: the second is the first's stem, cut further, numbered.
    first = first.removesuffix(f" - {TIGHT_PERIOD}.pdf")
    second = second.removesuffix(f" - {TIGHT_PERIOD} (2).pdf")
    assert second in first and len(first) - len(second) == 4
    assert sorted(e.prepared_location.rsplit("/", 1)[1] for e in report.filed) == names


def test_a_request_with_no_room_for_its_shortest_name_parks_with_the_sentence(tmp_path, path_setting):
    """Every rule accepted the W-2 and Prepared leaves no room for even
    ``A01 - January 01 2025 - December 31 2025.pdf``: it parks, with PATH_NO_ROOM naming
    both numbers, the request as its candidate, a review copy a person can
    open and the original where every original rests."""
    from tests.builders import root_for_a_return_of
    from tracker.copies import PATH_NO_ROOM
    from tracker.layout import path_limit

    # Prepared is 216 characters: 43 left for a name that needs 44 (215,
    # 43 and 44 with long paths off).
    items = [replace(ROOM_ITEMS[0], period=LONG_PERIOD)]
    engagement = make_engagement(root_for_a_return_of(tmp_path, no_room_return()), items)
    assert len(str(engagement)) + FOLDER_BELOW == no_room_prepared()
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    report = sort(engagement, today=DAY1)

    assert report.filed == []
    [parked] = report.review
    assert parked.reason == PATH_NO_ROOM.format(
        length=path_limit() + 1, limit=path_limit(), ext=".pdf")
    assert parked.candidates == "A01"
    copy = locate(engagement, parked.prepared_location)
    assert copy.is_file() and copy.parent.name == REVIEW_DIR_NAME
    assert (originals(engagement) / "w2.pdf").is_file()
    assert list(prepared(engagement, "A01").iterdir()) == []


def test_a_review_copy_is_named_to_fit_and_the_row_keeps_the_clients_name(short_root, path_setting):
    """A client's file name of 150 characters under a root that leaves the
    review folder less room than that: the document parks, its review copy
    is cut to fit - the extension kept - and the row's ``original_name`` is
    the client's whole name, which is what the queue's *what the name says*
    line reads."""
    from tests.builders import root_for_a_return_of
    from tracker import review
    from tracker.layout import path_limit

    root = root_for_a_return_of(short_root, 109)                  # the review folder: 135
    engagement = make_engagement(root, ROOM_ITEMS)
    review_dir = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    name = "letter " + "n" * 139 + ".pdf"
    assert len(name) == 150 and len(str(review_dir)) + 1 + len(name) > path_limit()
    drop(engagement, name, "A letter about nothing on the list")

    report = sort(engagement, today=DAY1)

    [parked] = report.review
    assert parked.original_name == name
    copy = locate(engagement, parked.prepared_location)
    assert copy.is_file() and copy.suffix == ".pdf"
    assert copy.name.startswith("letter nnn") and len(str(copy)) == path_limit()
    assert (originals(engagement) / name).is_file()                # the original, uncut
    [triaged] = review.triage(engagement, read_index(engagement), items=load_manifest(engagement))
    assert triaged.entry.original_name == name


# --------------------------- decision 131's review: the lead's rulings ----


def test_an_existing_copy_is_found_before_a_name_is_measured(tmp_path, path_setting):
    """F5: a killed run left the copy, under the request's name, in a
    Prepared that has no room for a new name. The pass finds it by its
    bytes first - as the hand-over already did - and files under the name
    it has, rather than parking a document whose copy is already there."""
    from tests.builders import root_for_a_return_of

    items = [replace(ROOM_ITEMS[0], period=LONG_PERIOD)]
    engagement = make_engagement(root_for_a_return_of(tmp_path, no_room_return()), items)
    folder = prepared(engagement, "A01")
    assert len(str(engagement / PREPARED_DIR_NAME)) == no_room_prepared()   # no room for "A01 - <period>.pdf"
    dropped = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    (folder / "c.pdf").write_bytes(dropped.read_bytes())

    report = sort(engagement, today=DAY1)

    assert report.review == []
    [entry] = report.filed
    assert entry.prepared_location == f"{PREPARED_DIR_NAME}/A01 - c.pdf"
    assert [p.name for p in folder.iterdir()] == ["A01 - c.pdf"]


def test_a_filing_that_parks_for_room_leaves_nothing_it_made(short_root, path_setting):
    """F6: decision 94 files one page under two requests. The first has room
    and the second has none, so the filing parks - and nothing the attempt
    would have made for the first is left behind: nothing is made until
    every copy of the filing is named. Since decision 168 there is no
    request folder to make either, only the copy."""
    from tests.builders import root_for_a_return_of
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.copies import PATH_NO_ROOM
    from tracker.layout import path_limit

    # C01's period leaves it no room in a Prepared of 216 characters (215
    # with long paths off), where A01's name fits.
    long_c01 = with_the_long_period(ITEMS[1])
    items = [ITEMS[0], long_c01]
    engagement = make_engagement(root_for_a_return_of(short_root, no_room_return()), items,
                                 scaffold=False)
    assert len(str(engagement / PREPARED_DIR_NAME)) == no_room_prepared()
    inbox_of(engagement).mkdir(parents=True, exist_ok=True)
    drop(engagement, "scan0003.pdf", "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))

    report = sort(engagement, today=DAY1)

    assert report.filed == []
    [parked] = report.review
    assert parked.reason == PATH_NO_ROOM.format(length=path_limit() + 1, limit=path_limit(), ext=".pdf")
    made = sorted(p.name for p in (engagement / PREPARED_DIR_NAME).iterdir())
    assert made == [REVIEW_DIR_NAME]                          # no A01 copy left behind


def test_a_workbook_review_copy_fitted_past_a_readers_limit_says_so(tmp_path):
    """Deviation 4: a reader's shorter limit never stops a park - the copy
    is fitted to Windows's own - but the row says the copy is longer than
    a spreadsheet program may open, and what to do about it."""
    from tests.builders import root_for_a_return_of
    from tracker.copies import REVIEW_COPY_PAST_READER

    engagement = make_engagement(root_for_a_return_of(tmp_path, 200), ROOM_ITEMS)   # review: 227
    assert len(str(review_dir(engagement))) == 227
    inbox_of(engagement).mkdir(parents=True, exist_ok=True)
    (inbox_of(engagement) / "note.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    report = sort(engagement, today=DAY1)

    [parked] = report.review
    copy = locate(engagement, parked.prepared_location)
    assert copy.is_file() and copy.name == "note.csv" and len(str(copy)) > 218
    assert parked.reason.endswith("; " + REVIEW_COPY_PAST_READER)


def test_a_fed_return_with_no_room_parks_at_home_naming_the_fed_return(tmp_path, path_setting):
    """Deviation 5, since decision 204: the fed return's request accepts the
    trial balance and its folder has no room even for the shortest name.
    The pass never files across households, so the document parks where it
    was dropped for one click, the row naming the fed return by its label;
    and the click itself refuses on the room, with nothing moved."""
    from tests.builders import root_for_a_return_of
    from tracker.filer import PATH_NO_ROOM_IN, NoRoom
    from tracker.layout import path_limit
    from tracker.records import Feed
    from tracker.registry import discover_engagements

    llc_name = "1120S - Park & Lee LLC " + "l" * 20
    root = root_for_a_return_of(tmp_path, no_room_return(), household="Park & Lee LLC",
                                return_name=llc_name)
    father = make_engagement(root, ITEMS, household="Park Family",
                             return_name="1040 - John Park", people=FATHER)
    business = [with_the_long_period(BUSINESS[0])]
    llc = make_engagement(root, business, household="Park & Lee LLC",
                          return_name=llc_name, people=LLC_PEOPLE)
    feeding(root, [Feed("Park & Lee LLC", llc_name)])
    b01 = prepared(llc, "B01")
    assert len(str(llc / PREPARED_DIR_NAME)) + 1 + len(f"B01 - {LONG_PERIOD}.pdf") == path_limit() + 1
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")

    done = sort_all([father, llc], home=[father], today=DAY1)

    assert read_index(llc) == [] and list(b01.iterdir()) == []
    [parked] = done[father].review
    label = next(one.label for one in discover_engagements(root).engagements if one.path == llc)
    assert parked.code == reasons.NAMED_ACROSS_HOUSEHOLDS.code and label in parked.reason
    assert "this request" not in parked.reason
    assert parked.pbc_location == original_at(father, "tb.pdf")
    with pytest.raises(NoRoom) as refused:
        click(father, parked, llc)
    # Said in the fed return's own words, on the father's page (the
    # review's S-1): never "this request's Short name".
    assert str(refused.value) == PATH_NO_ROOM_IN.format(label=label, length=path_limit() + 1,
                                                        limit=path_limit(), ext=".pdf")
    assert read_index(father) == [parked] and read_index(llc) == []
    assert [p.name for p in originals(father).iterdir()] == ["tb.pdf"]


def test_a_sibling_return_with_no_room_parks_in_the_home_return_naming_it(tmp_path, path_setting):
    """Deviation 5 inside one household (the review of decision 204, S-2):
    a W-2 naming Maria, whose return has no room even for the shortest
    name, while John's list also accepts it. The name vetoes John's return,
    Maria's has no room, and the row parks in John's - the home return -
    naming Maria's return by its label, never "this request"."""
    from tests.builders import root_for_a_return_of
    from tracker.filer import PATH_NO_ROOM_IN
    from tracker.layout import path_limit
    from tracker.registry import discover_engagements

    long_name = "1040 - Maria Park " + "m" * 24
    root = root_for_a_return_of(tmp_path, no_room_return(), household="Park Family",
                                return_name=long_name)
    john = make_engagement(root, ITEMS, household="Park Family",
                           return_name="1040 - John Park", people=FATHER)
    maria = make_engagement(root, [with_the_long_period(ITEMS[0])], household="Park Family",
                            return_name=long_name, people=(MARIA,))
    drop(john, "w2.pdf", "Form W-2 Wage and Tax Statement 2025", who="Maria Park")

    done = sort_all([john, maria], today=DAY1)

    assert read_index(maria) == []
    [parked] = done[john].review
    label = next(one.label for one in discover_engagements(root).engagements if one.path == maria)
    assert parked.reason.startswith(PATH_NO_ROOM_IN.format(
        label=label, length=path_limit() + 1, limit=path_limit(), ext=".pdf"))
    assert "this request" not in parked.reason
    assert parked.pbc_location == original_at(john, "w2.pdf")


# ---------------------------------------------- decision 137: the security review ----


def test_a_drop_over_the_size_ceiling_goes_to_review_unread(engagement, monkeypatch):
    """Decision 137 (M5): past ``validators.MAX_READ_MB`` a drop is never
    opened by the reader - no text layer, no OCR - and parks for a person
    with the one sentence that says why. It is still counted: moved out of
    the inbox into the year's originals and recorded like any other drop."""
    import tracker.content_check as content_check
    import tracker.validators as validators

    drop(engagement, "huge.pdf", "Form W-2 Wage and Tax Statement 2025")
    size = (inbox_of(engagement) / "huge.pdf").stat().st_size
    monkeypatch.setattr(validators, "MAX_READ_MB", size / (1024 * 1024) / 2)

    def never(*_args, **_kwargs):
        raise AssertionError("the reader opened a file past the ceiling")

    monkeypatch.setattr(content_check, "_extract", never)
    monkeypatch.setattr(content_check, "extract_by_ocr", never)

    report = sort(engagement, today=DAY1)

    assert report.filed == []
    [parked] = report.review
    assert parked.decision == NEEDS_REVIEW
    assert parked.code == reasons.TOO_LARGE.code
    assert parked.reason.startswith("Too large to read (") and "A person looks at it." in parked.reason
    assert [p.name for p in originals(engagement).iterdir()] == ["huge.pdf"]   # counted and kept
    assert [row.original_name for row in read_index(engagement)] == ["huge.pdf"]


def test_an_unnamed_document_is_not_filed_across_households(tmp_path):
    """Decision 137 (B2; the owner's Q-2 of 2026-09-24, "never; a person
    decides"). A page that names nobody, accepted by an unnamed request of a
    return in another household the drop folder feeds, used to be filed there
    on its keywords - moving the original into a folder that household's
    people can open. It now parks in the dropping household's own Needs
    Review with the one sentence that says why. The same page within one
    household files as it always did, and a page that names the fed
    return's people still crosses (decision 129's headline case)."""
    from tracker.records import Feed

    unnamed = [replace(BUSINESS[0], named=False)]
    father = make_engagement(tmp_path / "a", ITEMS, household="Park Family",
                             return_name="1040 - John Park", people=FATHER)
    llc = make_engagement(tmp_path / "a", unnamed, household="Park & Lee LLC",
                          return_name="1120S - Park & Lee LLC", people=LLC_PEOPLE)
    feeding(tmp_path / "a", [Feed("Park & Lee LLC", "1120S - Park & Lee LLC")])
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="")

    done = sort_all([father, llc], home=[father], today=DAY1)

    assert read_index(llc) == [] and done[llc].filed == []
    [parked] = read_index(father)
    assert parked.decision == NEEDS_REVIEW
    assert parked.reason == "Unnamed, so it was not filed into another household's return."
    assert parked.code == reasons.UNNAMED_ACROSS_HOUSEHOLDS.code
    # Where it was wanted, in the firm's words only (review of Part B, #3):
    # the other return's label and the request that accepted it.
    wanted = parse_evidence(parked.evidence)
    llc_label = "Park & Lee LLC 2025 1120S - Park & Lee LLC"
    assert f"{llc_label} / B01" in wanted
    assert all(e.term == "trial balance" or e.rule == "date" for e in wanted[f"{llc_label} / B01"])
    assert [p.name for p in originals(father).iterdir()] == ["tb.pdf"]    # it stays at home
    assert not originals(llc).exists() or not any(originals(llc).iterdir())

    # Within one household the same unnamed page files, as decision 128 says.
    personal = make_engagement(tmp_path / "b", ITEMS, household="Park Family",
                               return_name="1040 - John Park", people=FATHER)
    business = make_engagement(tmp_path / "b", unnamed, household="Park Family",
                               return_name="1120S - Park Landscaping")
    drop(personal, "tb.pdf", "Trial balance as of December 31 2025", who="")
    sort_all([personal, business], today=DAY1)
    [filed] = read_index(business)
    assert filed.decision == FILED and filed.identifier == "B01"


def test_the_link_check_stops_at_the_clients_root(tmp_path):
    """Decision 137's review (F5): only what lies between the clients root
    and the file is judged. A root reached through a link above it - the
    office's sits under Drive for desktop's own folder - files exactly as
    any other; and a path that is not under the root it is checked against
    is refused rather than judged all the way up to the drive."""
    import tracker.filer as filer
    from tracker import door

    real = tmp_path / "real"
    real.mkdir()
    link_to(real, tmp_path / "linked")                  # a link ABOVE the clients root
    root = tmp_path / "linked" / "Clients root"
    engagement = make_engagement(root, ITEMS)
    drop(engagement, "scan0012.pdf", "Form W-2 Wage and Tax Statement 2025")

    report = sort(engagement, today=DAY1)

    assert [e.original_name for e in report.filed] == ["scan0012.pdf"]
    assert report.errors == []
    inbox = inbox_of(engagement)
    # The one link check is the door's since decision 188; the filer asks it.
    assert filer.through_a_link is door.through_a_link
    assert not door.through_a_link(inbox / "a.pdf", inbox)
    assert door.through_a_link(tmp_path / "elsewhere" / "a.pdf", inbox)


def test_an_unnamed_re_send_already_held_in_another_household_parks_too(tmp_path, monkeypatch):
    """Decision 137's review of Part B (#5; the owner's "never"): the bytes
    a return in another household already holds are decided by that record
    (decision 111), and a re-send it would file again - here a person
    handed the unnamed page over, and the working copy has since gone - is
    held to the same rule as a first arrival. Unnamed, it is not filed
    into the other household; it parks in the drop's own household with the
    same sentence. (Since decision 157 a gone copy is made again from its
    original first; the re-file road is the one it takes while the original
    cannot be read, as here.)"""
    import shutil

    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module
    from tracker.filer import hand_over
    from tracker.records import Feed

    unnamed = [replace(BUSINESS[0], named=False)]
    father = make_engagement(tmp_path, ITEMS, household="Park Family",
                             return_name="1040 - John Park", people=FATHER)
    llc = make_engagement(tmp_path, unnamed, household="Park & Lee LLC",
                          return_name="1120S - Park & Lee LLC", people=LLC_PEOPLE)
    feeding(tmp_path, [Feed("Park & Lee LLC", "1120S - Park & Lee LLC")])
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="")
    sort_all([father, llc], home=[father], today=DAY1)
    [parked] = read_index(father)
    hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)        # a person decided
    [taken] = read_index(llc)
    held = locate(llc, taken.pbc_location)
    (llc / taken.prepared_location).unlink()                             # the copy went
    shutil.copyfile(held, inbox_of(father) / "tb again.pdf")              # the same bytes again
    real = filer_module.is_cloud_placeholder
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "is_cloud_placeholder", lambda p: p == held or real(p))

    sort_all([father, llc], home=[father], today=DAY3)

    assert [r.decision for r in read_index(llc)] == [FILED]              # nothing filed again there
    again = [r for r in read_index(father) if r.original_name == "tb again.pdf"]
    assert [r.decision for r in again] == [NEEDS_REVIEW]
    assert again[0].reason.startswith("Unnamed, so it was not filed into another household's return.")


# --------------------------------------------- decision 142: accepted, not asked ----
#
# Every catalog row is on every return; only the ticked ones are asked for.
# A row nobody asked for is a request the router considers like any other:
# a document for it files there, under a folder its first document makes.

NOT_ASKED_ITEMS = [ITEMS[0], replace(ITEMS[1], asked=False)]      # A01 asked, C01 (1098) not


def test_a_document_for_a_not_asked_row_files_there_and_reads_received(tmp_path):
    from tracker.manifest import Status, summarize
    from tracker.scanner import scan_engagement

    engagement = make_engagement(tmp_path, NOT_ASKED_ITEMS)
    drop(engagement, "1098.pdf", "Form 1098 Mortgage Interest Statement 2025")

    report = sort(engagement, today=DAY1)

    [entry] = report.filed
    assert entry.identifier == "C01" and entry.decision == FILED
    assert (engagement / entry.prepared_location).is_file()
    scan_engagement(engagement, today=DAY1)
    c01 = {i.identifier: i for i in load_manifest(engagement)}["C01"]
    assert c01.status == Status.RECEIVED and c01.asked is False
    summary = summarize(load_manifest(engagement))
    assert summary.also_received == 1 and summary.total == 1 and summary.received == 0


def test_a_not_asked_rows_first_document_sits_in_prepared_itself(tmp_path):
    """Decision 142's "no folder up front", widened by decision 168 to every
    row: the scaffold makes none, the scan writes no note for a folder
    nobody has, and the first document is a copy in Prepared itself."""
    from tracker.manifest import Status
    from tracker.scaffold import assign_files, scaffold_engagement
    from tracker.scanner import scan_engagement

    engagement = make_engagement(tmp_path, NOT_ASKED_ITEMS)
    prepared_dir = engagement / PREPARED_DIR_NAME
    assert [p.name for p in prepared_dir.iterdir()] == [REVIEW_DIR_NAME]

    scan_engagement(engagement, today=DAY1)
    rows = {i.identifier: i for i in load_manifest(engagement)}
    assert rows["C01"].status == Status.MISSING
    assert (rows["C01"].validation_notes or "") == ""

    drop(engagement, "1098.pdf", "Form 1098 Mortgage Interest Statement 2025")
    sort(engagement, today=DAY1)
    [copy] = assign_files(prepared_dir, ["A01", "C01"])["C01"]
    assert copy.parent == prepared_dir and copy.name.startswith("C01 - ")
    scaffold_engagement(engagement)
    assert [p.name for p in prepared_dir.iterdir() if p.is_dir()] == [REVIEW_DIR_NAME]


def test_two_returns_in_one_household_that_both_accept_a_notice_park_it_unless_the_name_decides(tmp_path):
    """A 1040 and a 1065 each carry decision 141's notices row, not asked.
    The name decides whose a notice is: the person's files to the 1040, the
    entity's to the 1065. One naming both is contested between the returns
    and parks; one naming neither parks too, with the name's own reason -
    nothing is guessed either way."""
    from tests.routing_cases import cp_notice_lines
    from tracker.filer import CONTESTED_BETWEEN_RETURNS
    from tracker.templates import template_items

    def rows(form):        # the suite's pages are small; the catalog's floor is for real mail
        return [replace(item, min_size_kb=0, asked=item.identifier != "Z01")
                for item in template_items(form) if item.identifier in ("A01", "Z01")]

    entity = "Park Landscaping LLC"
    personal = make_engagement(tmp_path, rows("1040"), household="Park Family",
                               return_name="1040 - Test Client")
    business = make_engagement(tmp_path, rows("1065"), household="Park Family",
                               return_name="1065 - Park Landscaping",
                               people=(Person("entity", entity, propose_spellings(entity, "entity")),))
    notice = "\n".join(cp_notice_lines(2026))
    drop(personal, "person.pdf", notice, who=TEST_CLIENT)
    drop(personal, "entity.pdf", notice + "\nNotice for account holder", who=entity)
    drop(personal, "both.pdf", notice + "\nSecond notice", who=f"{TEST_CLIENT}\n{entity}")
    drop(personal, "nobody.pdf", notice + "\nThird notice", who="")

    done = sort_all([personal, business], today=DAY1)

    assert [(e.original_name, e.identifier) for e in done[personal].filed] == [("person.pdf", "Z01")]
    assert [(e.original_name, e.identifier) for e in done[business].filed] == [("entity.pdf", "Z01")]
    parked = {e.original_name: e for e in done[personal].review}
    assert set(parked) == {"both.pdf", "nobody.pdf"}
    assert parked["both.pdf"].reason == CONTESTED_BETWEEN_RETURNS.format(
        listed="Park Family 2025 1040 - Test Client: Z01; Park Family 2025 1065 - Park Landscaping: Z01")
    assert parked["nobody.pdf"].code == reasons.NAME_NOT_ON_PAGE.code


# ------------------------------------------------ decision 144: short names ----


def test_an_existing_long_folder_is_left_as_it_is_and_the_copy_sits_beside_it(short_root):
    """Decision 144, claim 4 (nothing is renamed), over decision 168: a
    request folder made under the full title before either keeps its name
    and whatever is in it - it is a person's folder now (168, ruling 10) -
    and a copy filed now takes the short name in Prepared itself, beside
    it, never inside it."""
    w2 = _catalog_w2(expected_count=1, min_size_kb=0)
    engagement = make_engagement(short_root, [w2], scaffold=False)
    old = engagement / PREPARED_DIR_NAME / "A01 - W-2 Wage Statements - All Employers"
    old.mkdir(parents=True)
    from tracker.scaffold import scaffold_engagement

    scaffold_engagement(engagement)
    assert [p.name for p in (engagement / PREPARED_DIR_NAME).iterdir()
            if p.name.startswith("A01")] == [old.name]

    drop(engagement, "scan.pdf", "Form W-2 Wage and Tax Statement 2025 wages, tips, other "
                                 "compensation employee's social security number")
    [entry] = sort(engagement, today=DAY1).filed
    assert entry.prepared_location == f"{PREPARED_DIR_NAME}/A01 - W-2 - TY2025.pdf"
    assert list(old.iterdir()) == []
    assert sorted(p.name for p in (engagement / PREPARED_DIR_NAME).iterdir()
                  if p.name.startswith("A01")) == ["A01 - W-2 - TY2025.pdf", old.name]


#: The intake's 39 returns (go-live item 11), as (catalog, tax year, length
#: of the household's folder name). The names themselves are the firm's
#: clients' and never enter the repository; the room a return has depends
#: only on how long they are, so each is rebuilt as a synthetic name of the
#: same length.
INTAKE_RETURNS = (
    ("1040", 2014, 23), ("1040", 2016, 15), ("1040", 2017, 14), ("1040", 2017, 34),
    ("1040", 2019, 11), ("1040", 2020, 11), ("1040", 2020, 14), ("1040", 2020, 32),
    ("1040", 2021, 11), ("1040", 2021, 12), ("1040", 2021, 32), ("1040", 2022, 32),
    ("1040", 2023, 11), ("1040", 2023, 12), ("1040", 2023, 26), ("1040", 2023, 27),
    ("1040", 2024, 11), ("1040", 2024, 11), ("1040", 2024, 12), ("1040", 2024, 15),
    ("1040", 2024, 21), ("1040", 2024, 26), ("1040", 2024, 32), ("1040", 2025, 12),
    ("1040", 2025, 21), ("1040", 2025, 26), ("1040", 2025, 27), ("1040", 2025, 32),
    ("1065", 2011, 28), ("1065", 2017, 14), ("1065", 2022, 27), ("1120", 2025, 12),
    ("1120S", 2015, 19), ("1120S", 2020, 12), ("1120S", 2020, 15), ("1120S", 2020, 26),
    ("1120S", 2025, 19), ("1120S", 2026, 20), ("990", 2025, 20),
)
#: The firm's clients root: the Shared Drive keeps its name (decision 144,
#: the owner's first ruling). Thirty-five characters.
REAL_ROOT = r"G:\Shared drives\Income Tax Clients"


def _intake_refusals(asked_every_row: bool) -> tuple[int, int]:
    """(refused, deepest) over the intake's 39 under the real root, with the
    wizard's default rows asked or every row asked."""
    from tracker.api import default_return_name
    from tracker.copies import room_for
    from tracker.layout import MAX_PATH_LENGTH, return_dir_for
    from tracker.templates import FORM_TEMPLATES, template_items

    refused = deepest = 0
    for form, year, length in INTAKE_RETURNS:
        household = ("Household " + "x" * length)[:length]
        core = [spec["core"] for spec in FORM_TEMPLATES[form]]
        items = [replace(item, asked=asked_every_row or ticked)
                 for item, ticked in zip(template_items(form, year=year), core, strict=True)]
        folder = return_dir_for(Path(REAL_ROOT), household, year, default_return_name(form, household))
        need = room_for(folder, items).need
        deepest = max(deepest, need)
        refused += need > MAX_PATH_LENGTH
    return refused, deepest


def test_the_intake_returns_fit_under_the_real_root():
    """Decision 144, claim 6. Under the firm's own clients root, the
    intake's 39 returns - their household names rebuilt at the same lengths
    - are created with the wizard's default rows asked and **none is
    refused** (9 of 39 were, with the full titles). With every row asked
    the figure is reported, not asserted: it is in the decision's row."""
    assert len(REAL_ROOT) == 35 and len(INTAKE_RETURNS) == 39
    refused, _deepest = _intake_refusals(asked_every_row=False)
    assert refused == 0
    every, deepest_every = _intake_refusals(asked_every_row=True)
    print(f"every row asked: {every} of 39 refused, deepest {deepest_every}")


# ------------------------------------------------ decision 146's claims ----
# A broker's consolidated 1099 files whole under the row its 1099-B asks
# for, and counts as received for every other asked row one of its sections
# would satisfy on its own (the owner's answer to 146-Q). One file, one
# folder, nothing copied; the status, the letter, the client's received
# list, a rebuilt store and ``store check`` all read the filed row's Also
# Answers cell. Every case here is d146.


def test_a_statement_counts_as_the_statements_inside_it_and_no_more(tmp_path):
    """d146. The owner's words: a consolidated statement satisfies what each
    statement inside it would. A02 asking for three is answered by two - the
    1099-INT and the 1099-DIV - so it reads Partial and the letter asks for
    the one still to come, exactly as it would after a loose 1099-INT and a
    loose 1099-DIV."""
    from tracker.manifest import Status
    from tracker.reminder import draft_reminder

    engagement = _consolidated_return(tmp_path, int_div_expected=3)
    item = _status(engagement, "A02")
    assert item.status == Status.PARTIAL and item.file_count == 2
    assert "A02" in draft_reminder(engagement, today=DAY1).asked
    assert _status(engagement, "A04").status == Status.RECEIVED


# ------------- a name a row still names is taken (decision 147, ruling 9) ----
# The one numbering function counts a name as taken when the disk holds it
# or a row of the household-year names it as its original's resting place,
# wherever it is used: the inbox move (above), a filing's second move into
# another household (decision 129) and a person's hand-over (decision 132)
# - both in test_a_filing_never_takes_a_name_a_vanished_original_left_behind
# - and what is taken out of an email or a zip (decision 143).

def test_an_attachment_is_not_written_under_a_name_a_row_still_names(tmp_path):
    """Decision 143's attachments are named by the same function: a file a
    row names and a person removed leaves its name taken - since decision
    157 even for that row's own bytes, so a row whose place is taken by a
    file of its own bytes is never replaced by the row that file gets."""
    import hashlib

    from tracker.containers import Attachment
    from tracker.filer import _take_out

    folder = tmp_path / "_Opened" / "docs"
    gone = folder / "W2.pdf"
    new = Attachment("W2.pdf", b"%PDF-1.4 the corrected one")
    target, _digest = _take_out(folder, new, set(), root=tmp_path, recorded={gone: "a" * 64})
    assert target.name == "W2 (2).pdf" and target.read_bytes() == new.data
    same = Attachment("W2.pdf", b"%PDF-1.4 the row's own")
    own = hashlib.sha256(same.data).hexdigest()
    target, _digest = _take_out(folder, same, set(), root=tmp_path, recorded={gone: own})
    assert target.name == "W2 (3).pdf" and not gone.exists()


def test_a_name_an_open_intent_will_write_to_is_not_given_to_a_new_drop(fed, monkeypatch):
    """Decision 147, the designer's ruling on deviation 3. A filing into the
    LLC - since decision 204 the one click - is interrupted before its
    move, and its source is still syncing,
    so the move stays open and will write the LLC's ``tb.pdf`` once the
    file is down. A different ``tb.pdf`` the LLC drops meanwhile must not
    take that name: its row would carry the waiting filing's key and close
    it, and the move would later meet other bytes there. It rests beside
    it, and the waiting filing stays open for the next pass."""
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module

    father, llc = fed
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    [waiting] = sort_all([father, llc], home=[father], today=DAY1)[father].review
    killed_at_the_intent(monkeypatch, ledger.OP_MOVE)
    with pytest.raises(KeyboardInterrupt):
        click(father, waiting, llc, today=DAY1)
    monkeypatch.undo()
    [intent] = open_intents(llc)
    [move] = [op for op in intent[ledger.OPS_KEY] if op[ledger.OP_KEY] == ledger.OP_MOVE]
    assert locate(llc, move[ledger.TO_KEY]) == originals(llc) / "tb.pdf"
    waiting = originals(father) / "tb.pdf"
    real = filer_module.is_cloud_placeholder
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "is_cloud_placeholder", lambda p: p == waiting or real(p))
    drop(llc, "tb.pdf", "Trial balance as of December 31 2025 restated", who="Park & Lee LLC")

    sort_all([llc], today=DAY2)

    assert [p.name for p in originals(llc).iterdir()] == ["tb (2).pdf"]
    [row] = read_index(llc)
    assert row.pbc_location == original_at(llc, "tb (2).pdf")
    assert open_intents(llc) == [intent]                      # still waiting on the sync client


def test_a_name_held_only_by_a_return_outside_the_pass_is_not_reused(two_returns):
    """The review's N-1: ruling 9 says any return of the household-year. A
    return a pass leaves out - one marked inactive while the 1040 of the
    same year is still worked - still has its rows, and a name one of them
    holds after the client deleted the file is not handed to a different
    drop."""
    personal, business = two_returns
    drop(personal, "tb.pdf", "Trial balance as of December 31 2025")
    sort_all(two_returns, today=DAY1)
    [held] = read_index(business)
    (originals(personal) / "tb.pdf").unlink()
    drop(personal, "tb.pdf", "Form W-2 Wage and Tax Statement 2025")

    sort(personal, returns=[personal], today=DAY2)      # the business return is not in this pass

    assert [p.name for p in originals(personal).iterdir()] == ["tb (2).pdf"]
    [filed] = read_index(personal)
    assert filed.pbc_location == original_at(personal, "tb (2).pdf")
    assert read_index(business) == [held]
# ------------------------- decision 168: working copies sit in Prepared itself ----


def test_a_filed_copy_sits_in_prepared_itself(engagement):
    """Claim 1: a W-2 files as ``Prepared/A01 - <short> - TY2025.pdf``, and
    the record's location is that path - and the store rebuilt from the
    journal agrees, with no version change (claim 11)."""
    drop(engagement, "scan0012.pdf", "Form W-2 Wage and Tax Statement 2025")
    [filed] = sort(engagement, today=DAY1).filed

    assert filed.prepared_location == f"{PREPARED_DIR_NAME}/A01 - W-2 Wage Statements - TY2025.pdf"
    assert (engagement / filed.prepared_location).is_file()
    [row] = read_index(engagement)
    assert row.prepared_location == filed.prepared_location
    _only_the_review_folder(engagement)

    root = root_of(engagement)
    db = os.environ[store.ENV_STORE]
    store.close()
    os.unlink(db)
    fresh = store.connect()
    store.rebuild_engagement(fresh, root, engagement)
    assert [r.prepared_location for r in read_index(engagement)] == [filed.prepared_location]
    assert store_check.check(fresh, root, engagement) == []


def test_two_w2s_for_one_request_number_side_by_side(engagement):
    """Claim 2: the second is `` (2)`` beside the first, and both count
    toward A01."""
    from tracker.manifest import Status
    from tracker.scanner import scan_engagement

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025 Acme Corp")
    drop(engagement, "w2 second job.pdf", "Form W-2 Wage and Tax Statement 2025 Birch LLC")
    report = sort(engagement, today=DAY1)

    assert sorted(e.prepared_location for e in report.filed) == [
        f"{PREPARED_DIR_NAME}/A01 - W-2 Wage Statements - TY2025 (2).pdf",
        f"{PREPARED_DIR_NAME}/A01 - W-2 Wage Statements - TY2025.pdf",
    ]
    _only_the_review_folder(engagement)
    a01 = scan_engagement(engagement, today=DAY1).updates["A01"]
    assert a01.status == Status.RECEIVED and a01.file_count == 2


def test_a_folder_a_person_made_is_never_filed_into(engagement):
    """Ruling 7 from the filer's side: a folder named like a request's, made
    by a person inside Prepared, is not where the next copy goes - it goes
    in Prepared itself, and the folder and its file are left as they are."""
    person = engagement / PREPARED_DIR_NAME / "A01 - W-2 Wage Statements"
    person.mkdir()
    (person / "my notes.txt").write_text("mine", encoding="utf-8")

    drop(engagement, "scan0012.pdf", "Form W-2 Wage and Tax Statement 2025")
    [filed] = sort(engagement, today=DAY1).filed

    assert filed.prepared_location == f"{PREPARED_DIR_NAME}/A01 - W-2 Wage Statements - TY2025.pdf"
    assert [p.name for p in person.iterdir()] == ["my notes.txt"]


def test_a_rename_intent_written_before_168_is_finished_as_written(engagement):
    """SPEC-168 §8, the designer's default ruling: a rename a run was killed
    in before this decision wrote an intent naming folders
    (``Prepared/A01 - .../`` to ``Prepared/A1 - .../``). The next pass
    finishes it as written - the record decided it - with nothing lost and
    nothing doubled: the copy lands where the intent says, the row is
    recorded as the rename's, and no intent is left open. The folders are
    then a person's folders of a return made before 168 (ruling 10)."""
    from tracker.locking import engagement_lock
    from tracker.manifest import renamed_rules
    from tracker.records import IndexEntry, entry_to_json
    from tracker.validators import sha256_of

    original = originals(engagement) / "w2.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    text_pdf(original, named_page("Form W-2 Wage and Tax Statement 2025"))
    digest = sha256_of(original)
    old_home = engagement / PREPARED_DIR_NAME / "A01 - W-2 Wage Statements" / "A01 - W-2 Wage Statements - TY2025.pdf"
    new_home = engagement / PREPARED_DIR_NAME / "A1 - W-2 Wage Statements" / "A1 - W-2 Wage Statements - TY2025.pdf"
    old_home.parent.mkdir()
    old_home.write_bytes(original.read_bytes())

    from tests.builders import seed_index

    [row] = seed_index(engagement, [IndexEntry(
        received="2026-07-01 09:00:00", original_name="w2.pdf",
        size_kb=round(original.stat().st_size / 1024, 1), digest=digest,
        identifier="A01", prepared_location=location_of(engagement, old_home),
        pbc_location=original_at(engagement, "w2.pdf"), decision=FILED, reason="a reason")])
    renamed = replace(row, identifier="A1", prepared_location=location_of(engagement, new_home))
    with engagement_lock(engagement):
        store.record(store.connect(), engagement, *renamed_rules(engagement, "A01", "A1"),
                     ledger.new(ledger.MOVING, **{
                         ledger.KEY_KEY: ledger_key(renamed),
                         ledger.OPS_KEY: [{ledger.OP_KEY: ledger.OP_MOVE,
                                           ledger.FROM_KEY: location_of(engagement, old_home),
                                           ledger.TO_KEY: location_of(engagement, new_home),
                                           ledger.DIGEST_KEY: digest}],
                         ledger.DECIDED_BY_KEY: ledger.BY_PERSON,
                         ledger.ROW_KEY: entry_to_json(renamed),
                         ledger.EVENT_KEY_AFTER: ledger.RENAMED_BY_PERSON,
                     }))
    assert store.open_intents(store.connect(), engagement)

    sort(engagement, today=DAY2)

    assert not store.open_intents(store.connect(), engagement)
    assert not old_home.exists() and new_home.read_bytes() == original.read_bytes()
    [now] = read_index(engagement)
    assert now.identifier == "A1" and now.prepared_location == location_of(engagement, new_home)
    assert now.decision == FILED
    same = [p for p in (engagement / PREPARED_DIR_NAME).rglob("*.pdf") if sha256_of(p) == digest]
    assert same == [new_home]                                           # nothing doubled
    assert old_home.parent.is_dir() and not any(old_home.parent.iterdir())  # left, empty, for a person
    assert events_named(engagement, ledger.RENAMED_BY_PERSON)


def test_an_old_return_with_request_folders_is_named_and_left_alone(engagement):
    """Claim 10, ruling 10: a return made before decision 168 has a folder
    per request. Nothing is moved or migrated, nothing in the folders is
    counted - the recorded copy there included - and the pass names each
    folder, once."""
    from tests.builders import seed_index
    from tracker.manifest import Status
    from tracker.records import IndexEntry
    from tracker.scanner import scan_engagement
    from tracker.validators import sha256_of

    original = originals(engagement) / "w2.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    text_pdf(original, named_page("Form W-2 Wage and Tax Statement 2025"))
    old = engagement / PREPARED_DIR_NAME / "A01 - W-2 Wage Statements"
    old.mkdir()
    copy = old / "A01 - W-2 Wage Statements - TY2025.pdf"
    copy.write_bytes(original.read_bytes())
    stray = old / "a note.pdf"
    stray.write_bytes(b"somebody's")
    empty = engagement / PREPARED_DIR_NAME / "C01 - Mortgage Interest"
    empty.mkdir()
    seed_index(engagement, [IndexEntry(
        received="2026-07-01 09:00:00", original_name="w2.pdf",
        size_kb=round(original.stat().st_size / 1024, 1),
        digest=sha256_of(original), identifier="A01", prepared_location=location_of(engagement, copy),
        pbc_location=original_at(engagement, "w2.pdf"), decision=FILED, reason="a reason")])
    before = kept_files(engagement)

    report = sort(engagement, today=DAY2)
    scanned = scan_engagement(engagement, today=DAY2)

    assert kept_files(engagement) == before                         # nothing moved
    assert copy.is_file() and stray.is_file() and empty.is_dir()
    assert [r.decision for r in read_index(engagement)] == [FILED]  # the record's copy is where it says
    assert report.attention == []                                   # no file in them is named one by one
    assert scanned.updates["A01"].status == Status.MISSING and scanned.updates["A01"].file_count == 0
    assert [w for w in scanned.warnings if old.name in w] == [
        reasons.PERSONS_FOLDER.format(folder=old.name, prepared=PREPARED_DIR_NAME)]
    assert [w for w in scanned.warnings if empty.name in w] == [
        reasons.PERSONS_FOLDER.format(folder=empty.name, prepared=PREPARED_DIR_NAME)]


def test_a_working_copys_number_takes_a_name_an_open_intent_will_write_as_taken(engagement, monkeypatch):
    """Ruling 3 over decision 147: the names a working copy is numbered
    against are Prepared's own - every request's copies share it - and a
    name an open intent will still write there is one of them, so the pass
    never hands a waiting filing's name to another document."""
    import tracker.filer as filer_module

    waiting = engagement / PREPARED_DIR_NAME / "A01 - W-2 Wage Statements - TY2025.pdf"
    real = filer_module._spoken_for_by_an_open_intent

    def with_one_waiting(runs, ends=(ledger.FROM_KEY, ledger.TO_KEY)):
        found = real(runs, ends)
        return found | {waiting} if ends == (ledger.TO_KEY,) else found

    monkeypatch.setattr(filer_module, "_spoken_for_by_an_open_intent", with_one_waiting)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    [filed] = sort(engagement, today=DAY1).filed

    assert filed.prepared_location == f"{PREPARED_DIR_NAME}/A01 - W-2 Wage Statements - TY2025 (2).pdf"
    assert not waiting.exists()


# ------------- decision 157: a missing working copy is made again ----
# A working copy is the firm's and disposable; the client's original in
# their folder for the year is the record. So a copy that is simply gone -
# trashed on Drive's web, lost from Drive's cache, deleted by hand, the
# whole Prepared folder deleted - is made again from the original, proved
# against the row's fingerprint, and the client is never asked for a
# document the firm holds. Where the original is gone too, a person decides;
# and an original that comes back into the inbox goes home. Every case is d157.


def test_a_deleted_working_copy_is_remade_and_the_client_is_not_asked(engagement):
    """d157, claim 1 (the audit's C4 and D-3). A colleague trashes the 1098's
    working copy. The next pass makes it again from the client's original -
    through the whole copy, proved against the row's fingerprint, under an
    intent - says so once, and appends one ``copy_remade`` line. The request
    stays Received with its date and no regression note, and the letter does
    not ask the client for what the firm holds. Until 157 the scan read
    Missing and the letter asked, with no line anywhere."""
    from tracker.manifest import Status

    filed = _filed_1098(engagement)
    copy = engagement / filed.prepared_location
    original = originals(engagement) / "1098.pdf"
    copy.unlink()

    report, _scanned = _a_pass(engagement, DAY2)

    assert "C01" not in _asked(engagement, DAY2)
    assert copy.is_file() and copy.read_bytes() == original.read_bytes()
    from tracker.filer import REMADE_SENTENCE

    sentence = REMADE_SENTENCE.format(home=filed.prepared_location, pbc=filed.pbc_location,
                                      date=DAY2.isoformat(), prepared=PREPARED_DIR_NAME)
    [row] = read_index(engagement)
    assert row.decision == FILED and row.reason == f"{filed.reason}; {sentence}"
    assert [(e.name, e.error, e.left_in_place) for e in report.attention] == [
        (copy.name, sentence, True)]
    assert len(events_named(engagement, ledger.COPY_REMADE)) == 1
    item = _status(engagement, "C01")
    assert item.status == Status.RECEIVED and item.received_date == DAY1
    assert "was Received" not in item.validation_notes
    assert open_intents(engagement) == []
    assert store_check.check(store.connect(), root_of(engagement), engagement) == []

    lines = len(ledger.read_events(engagement))
    quiet, _ = _a_pass(engagement, DAY3)
    assert quiet.attention == [] and len(ledger.read_events(engagement)) == lines


def test_a_deleted_prepared_folder_is_remade_whole(engagement):
    """d157, claim 2. Somebody deletes the whole Prepared folder: every copy
    the record claims - the filed ones and the parked one waiting in the
    review folder - is made again from its own original, byte for byte, at
    the path it had. Every status stays where it was and nothing is asked.
    Until 157 every request read Missing and the letter asked for all of
    them."""
    from tracker.manifest import Status
    from tracker.scanner import scan_engagement

    drop(engagement, "w2 acme.pdf", "Form W-2 Wage and Tax Statement 2025 Acme Corp")
    drop(engagement, "w2 beta.pdf", "Form W-2 Wage and Tax Statement 2025 Beta LLC")
    drop(engagement, "1098.pdf", MORTGAGE)
    drop(engagement, "notice.pdf", "an agency notice nothing asks for")
    first = sort(engagement, today=DAY1)
    assert len(first.filed) == 3 and len(first.review) == 1
    scan_engagement(engagement, today=DAY1)
    before = {where: held for where, (held, _mtime) in files_under(engagement).items()}
    was = {i.identifier: (i.status, i.received_date, i.file_count) for i in load_manifest(engagement)}
    assert was["A01"][0] == was["C01"][0] == Status.RECEIVED
    rows = read_index(engagement)
    shutil.rmtree(engagement / PREPARED_DIR_NAME)

    report, _scanned = _a_pass(engagement, DAY2)

    assert {where: held for where, (held, _mtime) in files_under(engagement).items()} == before
    assert len(events_named(engagement, ledger.COPY_REMADE)) == 4
    assert len(report.attention) == 4
    assert [(r.decision, r.prepared_location) for r in read_index(engagement)] == [
        (r.decision, r.prepared_location) for r in rows]
    assert {i.identifier: (i.status, i.received_date, i.file_count)
            for i in load_manifest(engagement)} == was
    assert not {"A01", "C01"} & _asked(engagement, DAY2)


def test_a_true_duplicate_is_still_a_duplicate(engagement):
    """d157, claim 5. The same bytes sent again while the row's own original
    is still where it was are the Duplicate they always were - under the
    same name too - each with a place and a key of its own. And where two
    rows' originals are gone and the same bytes arrive, which of them came
    back is not guessed: it is a Duplicate with a key of its own, never at
    either row's place, so no row is replaced (C5's second fix - until 157
    it took the Filed row's place, and its row replaced the Filed one)."""
    from tracker.filer import DUPLICATE_OF_FILED

    filed = _filed_1098(engagement)
    body = (originals(engagement) / "1098.pdf").read_bytes()
    (inbox_of(engagement) / "1098.pdf").write_bytes(body)
    (inbox_of(engagement) / "mortgage again.pdf").write_bytes(body)

    report = sort(engagement, today=DAY2)

    assert report.filed == [] and len(report.duplicates) == 2
    rows = read_index(engagement)
    assert rows[0] == filed
    assert [r.decision for r in rows] == [FILED, DUPLICATE, DUPLICATE]
    assert [r.pbc_location for r in rows[1:]] == [
        original_at(engagement, "1098 (2).pdf"), original_at(engagement, "mortgage again.pdf")]
    for dup in rows[1:]:
        assert dup.reason == DUPLICATE_OF_FILED.format(name=filed.original_name, copy=filed.filed_as)

    # Two rows whose originals are gone hold these bytes: nothing is guessed.
    (originals(engagement) / "1098.pdf").unlink()
    (originals(engagement) / "mortgage again.pdf").unlink()
    (inbox_of(engagement) / "1098.pdf").write_bytes(body)

    report = sort(engagement, today=DAY3)

    [dup] = report.duplicates
    assert dup.pbc_location == original_at(engagement, "1098 (3).pdf")
    rows = read_index(engagement)
    assert rows[0].decision == FILED and rows[0].pbc_location == filed.pbc_location
    assert len({ledger_key(r) for r in rows}) == len(rows) == 4
    assert events_named(engagement, ledger.ORIGINAL_RETURNED) == []


@pytest.mark.parametrize("at_the_top", ("the different file", "the original"))
def test_an_original_back_beside_a_different_file_of_its_name_goes_home_in_either_order(
        engagement, at_the_top):
    """d157, ruling B7 over 147's review, N-4 (probe p7). R1 holds W2.pdf with
    bytes X and the client deletes it; in one pass W2.pdf holding Y and
    Scans\\W2.pdf holding X arrive - or the other way round. Either way X
    goes back to W2.pdf and R1 keeps its Filed row, Y is filed at
    W2 (2).pdf under a key of its own, no row is replaced, and no pass says
    a copy is unrecorded. Until 157 X became a Duplicate under R1's key and
    R1's Filed row was gone."""
    from tracker.filer import RETURNED_SENTENCE, UNRECORDED_COPY

    first = drop(engagement, "W2.pdf", "Form W-2 Wage and Tax Statement 2025 Acme Corp")
    x_bytes = first.read_bytes()
    [r1] = sort(engagement, today=DAY1).filed
    (originals(engagement) / "W2.pdf").unlink()
    y_page = named_page("Form W-2 Wage and Tax Statement 2025 Beta LLC")
    scans = inbox_of(engagement) / "Scans"
    scans.mkdir()
    if at_the_top == "the different file":
        text_pdf(inbox_of(engagement) / "W2.pdf", y_page)
        (scans / "W2.pdf").write_bytes(x_bytes)
        arrived = "Scans/W2.pdf"
    else:
        (inbox_of(engagement) / "W2.pdf").write_bytes(x_bytes)
        text_pdf(scans / "W2.pdf", y_page)
        arrived = "W2.pdf"

    report = sort(engagement, today=DAY2)

    assert (originals(engagement) / "W2.pdf").read_bytes() == x_bytes
    rows = read_index(engagement)
    assert [r.decision for r in rows] == [FILED, FILED] and report.duplicates == []
    assert (rows[0].pbc_location, rows[0].digest) == (r1.pbc_location, r1.digest)
    assert rows[0].reason == f"{r1.reason}; " + RETURNED_SENTENCE.format(
        drop=arrived, date=DAY2.isoformat(), pbc=r1.pbc_location)
    assert rows[1].pbc_location == original_at(engagement, "W2 (2).pdf")
    assert rows[1].digest != r1.digest and rows[1].identifier == "A01"
    later = sort(engagement, today=DAY3)
    unrecorded = UNRECORDED_COPY.format(location="")
    assert not any(unrecorded in e.error for e in report.attention + later.attention)
    assert later.attention == []


def test_an_original_that_cannot_be_read_holds_the_request_and_is_never_read(
        engagement, monkeypatch):
    """d157, rulings B3 and B9. The copy is gone and the original is a
    placeholder the sync client has not brought down: it is never read
    (that would download it), nothing is made and nothing is written. The
    request is held firm-side - a missing copy is never by itself a letter
    to the client - and the pass after the original is back makes the copy."""
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module
    from tracker.manifest import Status

    filed = _filed_1098(engagement)
    copy = engagement / filed.prepared_location
    copy.unlink()
    original = originals(engagement) / "1098.pdf"
    real = filer_module.is_cloud_placeholder
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "is_cloud_placeholder", lambda p: p == original or real(p))
    read = counting_hashes(monkeypatch)
    lines = len(ledger.read_events(engagement))

    report, _scanned = _a_pass(engagement, DAY2)

    assert str(original) not in read
    assert not copy.exists() and report.attention == [] and report.errors == []
    assert [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)[lines:]] == [ledger.SCANNED]
    item = _status(engagement, "C01")
    assert item.status == Status.MISSING
    assert reasons.COPY_MISSING.code in item.note_code_list
    assert "C01" not in _asked(engagement, DAY2)

    monkeypatch.undo()
    _a_pass(engagement, DAY3)
    assert copy.read_bytes() == original.read_bytes()
    assert _status(engagement, "C01").status == Status.RECEIVED


def test_a_statement_whose_copy_is_not_counted_answers_nothing_until_it_is_made_again(
        tmp_path, monkeypatch):
    """d157, ruling B9, from 146's restack review (finding 2). E01's
    consolidated statement answers A02 and A04; its working copy is gone and
    its original cannot be read this pass. The answered requests do not
    claim a document the firm cannot open: each is held firm-side, naming
    the statement and why, and the letter asks for none of the three. The
    pass that can read the original makes the copy again and every answer
    heals with it."""
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module
    from tracker.manifest import Status
    from tracker.reasons import IN_CONSOLIDATED
    from tracker.scanner import ANSWER_WHY_MISSING, ANSWERED_BY, scan_engagement

    engagement = _consolidated_return(tmp_path)
    [row] = [r for r in read_index(engagement) if r.decision == FILED]
    (engagement / row.prepared_location).unlink()
    original = locate(engagement, row.pbc_location)
    real = filer_module.is_cloud_placeholder
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "is_cloud_placeholder", lambda p: p == original or real(p))

    sort(engagement, today=DAY2)
    scan_engagement(engagement, today=DAY2)

    held = reasons.ANSWER_NOT_COUNTED.format(
        listed=ANSWERED_BY.format(row="E01", why=ANSWER_WHY_MISSING))
    for identifier in ("A02", "A04"):
        item = _status(engagement, identifier)
        assert item.status == Status.MISSING and item.file_count == 0
        assert held in item.validation_notes
        assert IN_CONSOLIDATED.format(row="E01") not in item.validation_notes
    assert reasons.COPY_MISSING.code in _status(engagement, "E01").note_code_list
    assert not {"E01", "A02", "A04"} & _asked(engagement, DAY2)

    monkeypatch.undo()
    sort(engagement, today=DAY3)
    scan_engagement(engagement, today=DAY3)
    for identifier, count in (("E01", 1), ("A02", 2), ("A04", 1)):
        item = _status(engagement, identifier)
        assert item.status == Status.RECEIVED and item.file_count == count, identifier


def test_a_store_rebuilt_from_the_journal_agrees_after_a_remake_and_a_return(engagement):
    """d157, B11. Both new row events fold like every other row event, so the
    store version stays where it is and a store rebuilt from the journal is
    the live one, row for row, with ``store check`` clean on both."""
    filed = _filed_1098(engagement)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    [w2] = sort(engagement, today=DAY1).filed
    (engagement / filed.prepared_location).unlink()                  # to be made again
    (originals(engagement) / "w2.pdf").rename(inbox_of(engagement) / "w2.pdf")   # to come back

    _a_pass(engagement, DAY2)

    assert len(events_named(engagement, ledger.COPY_REMADE)) == 1
    assert len(events_named(engagement, ledger.ORIGINAL_RETURNED)) == 1
    # Pinned so a new schema re-proves this claim: 20 adds the household's
    # related list (pilot P170), and a rebuild still agrees with the live index.
    assert store.SCHEMA_VERSION == 20
    live = read_index(engagement)
    root = root_of(engagement)
    assert store_check.check(store.connect(), root, engagement) == []
    db = os.environ[store.ENV_STORE]
    store.close()
    os.unlink(db)
    fresh = store.connect()
    store.rebuild_engagement(fresh, root, engagement)
    assert read_index(engagement) == live
    assert [ledger_key(r) for r in live] == [ledger_key(filed), ledger_key(w2)]
    assert store_check.check(fresh, root, engagement) == []


def test_a_remake_killed_after_the_copy_is_finished_from_the_record(engagement, monkeypatch):
    """d157 over decision 119: the re-make is written down before the copy is
    made, so a run killed between the copy and the record is finished by the
    next pass - the copy proved, not made twice, and the row recorded as the
    intent said, dated the day it was decided."""
    from tracker.filer import REMADE_SENTENCE

    filed = _filed_1098(engagement)
    copy = engagement / filed.prepared_location
    copy.unlink()
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_ops(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        sort(engagement, today=DAY2)

    assert copy.is_file() and open_intents(engagement)
    sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.reason.endswith(REMADE_SENTENCE.format(
        home=filed.prepared_location, pbc=filed.pbc_location, date=DAY2.isoformat(),
        prepared=PREPARED_DIR_NAME))
    assert len(events_named(engagement, ledger.COPY_REMADE)) == 1
    conserved(engagement, before, moves, added=[filed.digest])


# Decision 180: every step an intent names stays in its return's places.


def test_a_parked_attachment_is_handed_to_a_return_of_another_year_of_its_household(tmp_path):
    """The cloud branch's own review of decision 180: a person may hand an attachment parked
    in one open year to a return of another, and the first containment
    allowed only the return's own year's _Opened - after both records'
    intents were written, so the release finished, the filing never did,
    and the document was on no queue at all. Any year's _Opened of the
    household is a place a step may read from, and every step is held to
    its places before an intent names it."""
    import io
    import zipfile

    from tracker import store
    from tracker.filer import hand_over

    a = make_engagement(tmp_path, ITEMS, year=2025, return_name="1040 - A")
    b = make_engagement(tmp_path, ITEMS, year=2024, return_name="1040 - B")
    page = text_pdf(tmp_path / "page.pdf", ["Form W-2 Wage and Tax Statement 2025", "nobody"], style="padded")
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("W-2.pdf", page.read_bytes())
    (inbox_of(a) / "docs.zip").write_bytes(packed.getvalue())
    sort(a, today=DAY1)
    parked = next(row for row in read_index(a) if row.container)

    hand_over(a, parked.original_name, b, "A01")

    [filed] = [row for row in read_index(b) if row.original_name == parked.original_name]
    assert filed.decision == FILED and (b / filed.prepared_location).is_file()
    assert store.open_intents(store.connect(), a) == [] == store.open_intents(store.connect(), b)


# Decision 187: the record is untrusted input - every place and link is
# checked before a step is obeyed, and every copy is proved.


def test_a_legitimate_filing_into_a_fed_return_still_completes(fed):
    """The ruling's third proof: the one step that legitimately reads
    another household's folder - a drop in the father's inbox filed into
    the co-owned LLC's return, since decision 204 by the one click - is
    admitted, carried out and proved, and leaves no intent open and nothing
    for the check to name."""
    from tracker.validators import sha256_of

    father, llc = fed
    filed_across(father, llc, "tb.pdf", "Trial balance as of December 31 2025")

    [row] = read_index(llc)
    assert row.decision == FILED
    assert sha256_of(llc / row.prepared_location) == row.digest == sha256_of(llc / row.pbc_location)
    assert ledger.replay(ledger.read_events(llc)).intents == {}
    assert ledger.replay(ledger.read_events(father)).intents == {}
    for folder in (father, llc):
        assert store_check.check(store.connect(), root_of(folder), folder) == []


def test_details_that_cannot_be_read_are_none_and_the_failure_is_kept_on_the_log(
        engagement, monkeypatch, caplog):
    """The audit's E4 (P297): the sort still runs with no people when the
    return's details cannot be loaded at that moment (nothing is guessed),
    but a race with the runner's own read now shows in the error log."""
    import logging

    import tracker.filer as filer
    from tracker import errors

    def torn(_folder):
        raise filer.FilingError("the record changed under this read")

    monkeypatch.setattr(filer, "load_engagement_info", torn)
    with caplog.at_level(logging.WARNING, logger=errors.DEBUG_LOGGER):
        assert filer._details_of(engagement) is None
    assert f"filer: the return's details ({engagement.name})" in caplog.text
    assert "the record changed under this read" in caplog.text


@pytest.mark.skipif(sys.platform == "win32", reason="Windows refuses a control character in a file name, so such a drop cannot exist there")
def test_a_name_with_a_control_character_is_still_filed_and_recorded(engagement, tmp_path):
    """The review's M5: decision 104 files a POSIX name holding a control
    character, and the record's value rule holds a file's own name only to
    what no path can hold - so the drop is filed and recorded, and the
    household beside it is sorted as it always was."""
    drop(engagement, "w2\x01.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "other.pdf", "nothing the rules recognise")

    report = sort(engagement, today=DAY1)

    assert report.errors == []
    # Recorded as the record keeps a name (decision 190's recorded_name drops
    # the control character); the original keeps its own on disk.
    assert sorted((row.original_name, row.decision) for row in read_index(engagement)) == [
        ("other.pdf", NEEDS_REVIEW), ("w2.pdf", FILED)]
    assert (originals(engagement) / "w2\x01.pdf").is_file()


def test_an_interrupted_decision_65_intent_finishes_with_a_proved_copy(engagement):
    """The review's S3: an intent an earlier version wrote for a row with no
    digest, killed after the move and before the copy, carries a copy with
    no fingerprint. The recovery proves it against the original's bytes -
    the original is the record - so the intent finishes and the row is
    recorded, rather than the return stopping every pass."""
    from tracker.records import IndexEntry, entry_to_json
    from tracker.validators import sha256_of

    original = originals(engagement) / "w2.pdf"
    original.write_bytes(b"%PDF-1.4 the client's W-2")     # the move already happened
    working = engagement / PREPARED_DIR_NAME / "A01 - W-2.pdf"
    row = entry_to_json(IndexEntry(
        received="2026-07-01", original_name="w2.pdf", size_kb=0.0, digest="", identifier="A01",
        prepared_location=location_of(engagement, working), pbc_location=location_of(engagement, original),
        decision=FILED, reason="a reason"))
    ops = [
        {ledger.OP_KEY: ledger.OP_MOVE, ledger.FROM_KEY: location_of(engagement, inbox_of(engagement) / "w2.pdf"),
         ledger.TO_KEY: location_of(engagement, original), ledger.DIGEST_KEY: ""},
        {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: location_of(engagement, original),
         ledger.TO_KEY: location_of(engagement, working), ledger.DIGEST_KEY: ""},
    ]
    _forge_line(engagement, ledger.new(ledger.MOVING, **{
        ledger.KEY_KEY: location_of(engagement, original), ledger.OPS_KEY: ops, ledger.ROW_KEY: row,
        ledger.DECIDED_BY_KEY: ledger.BY_PASS, ledger.EVENT_KEY_AFTER: ledger.FILED}))

    sort(engagement, today=DAY1)

    assert ledger.replay(ledger.read_events(engagement)).intents == {}
    assert sha256_of(working) == sha256_of(original)
    assert [row.decision for row in read_index(engagement)] == [FILED]


def test_an_original_held_for_the_whole_pass_is_parked_and_said_so(engagement, monkeypatch):
    """The review's S6: an original the pass cannot read at all this pass is
    never copied unproved. It is kept, recorded for a person, and the
    sentence says it could not be read - not that the record needs checking."""
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module
    from tracker.copies import COPY_UNREAD

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    real = filer_module.sha256_of

    def unreadable(path):
        if path.parent == originals(engagement):
            raise PermissionError("held by the sync client")
        return real(path)

    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "sha256_of", unreadable)
    report = sort(engagement, today=DAY1)
    monkeypatch.undo()

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.prepared_location == "" and row.digest == ""
    assert COPY_UNREAD.format(source="w2.pdf") in row.reason
    assert "checks the record" not in row.reason
    assert (originals(engagement) / "w2.pdf").is_file()
    assert [error.name for error in report.errors] == ["w2.pdf"]


# ------------------------------- decision 190: programs, names, Protected View ----


def test_an_executable_gets_no_review_copy_shows_its_true_type_and_does_not_hold_the_letter(engagement):
    """A program dressed as a W-2 (G-4): decided before any reading, so its
    name reaches no request; parked as not a document with no review copy;
    its original moved byte for byte; the card knows it as an .exe and the
    letter holds nothing for it."""
    from tracker import api, reminder

    program = inbox_of(engagement) / "W-2 2025.pdf.exe"
    program.write_bytes(b"MZ Form W-2 Wage and Tax Statement 2025")
    before = program.read_bytes()

    report = sort(engagement, today=DAY1)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.code == reasons.NOT_A_DOCUMENT.code
    assert row.reason == reasons.NOT_A_DOCUMENT.template
    assert row.prepared_location == "" and row.candidates == "" and row.evidence == ""
    assert (originals(engagement) / "W-2 2025.pdf.exe").read_bytes() == before
    assert _review_folder_files(engagement) == []
    assert report.filed == []
    assert api.review_bucket(row) == api.BUCKET_NOT_A_DOCUMENT
    assert api.true_extension(row) == "exe"
    assert reminder._parked_holds(load_manifest(engagement), [row]) == {}


def test_a_script_inside_a_zip_lands_blocked(engagement):
    """A program inside an email or a zip is never written out of it: no
    file of it in _Opened, and its row parks as not a document, naming no
    file and no copy. The document beside it is taken out as before."""
    import io
    import zipfile

    from tracker.layout import opened_dir_of

    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("W-2.pdf", text_pdf(engagement.parent / "page.pdf", named_page(
            "Form W-2 Wage and Tax Statement 2025", TEST_CLIENT)).read_bytes())
        archive.writestr("invoice.js", b"WScript.Echo('not a document')")
    (inbox_of(engagement) / "docs.zip").write_bytes(packed.getvalue())

    sort(engagement, today=DAY1)

    taken_out = sorted(p.name for p in opened_dir_of(engagement).rglob("*") if p.is_file())
    assert taken_out == ["W-2.pdf"]
    [script] = [row for row in read_index(engagement) if row.original_name == "invoice.js"]
    assert script.decision == NEEDS_REVIEW and script.code == reasons.NOT_A_DOCUMENT.code
    assert script.pbc_location == "" and script.prepared_location == "" and script.container
    assert "invoice.js" not in _review_folder_files(engagement)

    sort(engagement, today=DAY2)           # and a pass later, nothing says it went missing
    assert [row.original_name for row in read_index(engagement)
            if row.original_name == "invoice.js"] == ["invoice.js"]


def test_a_direction_override_is_not_kept_in_any_recorded_name(engagement):
    """E-12/B-10: a right-to-left override and a zero-width space, in a
    drop's name and in the subfolder it came from, reach no name the
    record keeps and no review copy's name; the original on disk keeps its
    raw name, byte for byte (standing rule 2)."""
    import unicodedata

    raw_program = "W2\u202efdp.exe"
    raw_page = "receipt\u200b.pdf"
    raw_suffix = "receipt.pd\u200bf"      # the review's S4: an invisible character inside the suffix
    folder = inbox_of(engagement) / "Scans\u200b"
    folder.mkdir()
    (folder / raw_program).write_bytes(b"MZ")
    text_pdf(folder / raw_page, "Photos from Maui, the hotel pool and the beach at sunset")
    (folder / raw_suffix).write_bytes(b"%PDF-1.4 not really a statement")

    sort(engagement, today=DAY1)

    def invisible(text):
        return [ch for ch in text if unicodedata.category(ch) in ("Cf", "Cc")]

    rows = read_index(engagement)
    assert sorted(row.original_name for row in rows) == ["W2fdp.exe", "receipt.pdf", "receipt.pdf"]
    assert all(row.subfolder == "Scans" for row in rows)
    assert not any(invisible(row.original_name + row.subfolder + row.prepared_location)
                   for row in rows)
    # Nor in any row's reason: the extension a sentence quotes is the
    # recorded name's (decision 190's review, S4).
    assert [row.reason for row in rows if invisible(row.reason)] == []
    assert _review_folder_files(engagement) == ["receipt (2).pdf", "receipt.pdf"]
    on_disk = sorted(p.name for p in originals(engagement).rglob("*") if p.is_file())
    assert on_disk == sorted([raw_program, raw_page, raw_suffix])
    # A person's command may name the row either way: as recorded, or as sent.
    from tracker.filer import find_parked

    assert find_parked(rows, raw_page) is not None


def test_a_macro_workbook_copy_is_marked_for_protected_view(engagement, monkeypatch):
    """A review copy that can carry macros is marked as from the internet
    on its temp, before it takes its name; a copy of a plain PDF is not."""
    import tracker.copies as copies_module

    marked = []
    monkeypatch.setattr(copies_module, "mark_from_internet", lambda path: marked.append(path) or True)
    (inbox_of(engagement) / "budget.docm").write_bytes(b"PK not really a document")
    drop(engagement, "vacation.pdf", "Photos from Maui, the hotel pool and the beach at sunset")

    sort(engagement, today=DAY1)

    assert _review_folder_files(engagement) == ["budget.docm", "vacation.pdf"]
    assert len(marked) == 1 and marked[0].name.startswith("budget.docm")


def test_a_macro_copy_that_cannot_be_marked_is_not_made(engagement, monkeypatch):
    """Fail closed (decision 190): on a volume that will not hold the mark,
    no review copy is made - the drop is a "could not be filed" row the
    pass report names - and the original rests safe."""
    import tracker.copies as copies_module
    from tracker.filer import MARK_REFUSED_STEP

    def refused(path):
        raise OSError(95, "Operation not supported", str(path))

    monkeypatch.setattr(copies_module, "mark_from_internet", refused)
    original = inbox_of(engagement) / "budget.docm"
    original.write_bytes(b"PK not really a document")

    report = sort(engagement, today=DAY1)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.prepared_location == ""
    assert row.code == reasons.COULD_NOT_FILE_CODE
    assert "could not be marked as from the internet" in row.reason
    # The re-check's N-N1: the row's step never points at the unmarked original.
    assert row.reason.endswith(MARK_REFUSED_STEP) and "file it by hand" not in row.reason
    assert _review_folder_files(engagement) == []
    assert (originals(engagement) / "budget.docm").read_bytes() == b"PK not really a document"
    assert [error.name for error in report.errors] == ["budget.docm"]


@pytest.mark.parametrize("raw", ["W2.exe\u200b", "Pay.scr\ufeff.", "W2.ex\u200be", "x.lnk\u202c"])
def test_a_program_hidden_by_an_invisible_character_is_still_not_a_document(engagement, raw):
    """The review's M1: an invisible character after or inside the suffix
    hides the type from the raw name, and the recorded name - which names
    every copy and every card - shows it. Either name saying program is
    enough: no review copy, no Open, and the card's type is printed clean."""
    import unicodedata

    from tracker import api

    (inbox_of(engagement) / raw).write_bytes(b"MZ\x90\x00 a program")

    sort(engagement, today=DAY1)

    [row] = read_index(engagement)
    assert row.code == reasons.NOT_A_DOCUMENT.code, row.reason
    assert row.prepared_location == ""
    assert _review_folder_files(engagement) == []
    assert api.review_bucket(row) == api.BUCKET_NOT_A_DOCUMENT
    assert api._review_copy_key(row) == ""
    assert not [ch for ch in api.true_extension(row) if unicodedata.category(ch) == "Cf"]


# ------------------------------- decision 201: an unnamed issuer's card ----


def test_an_opened_folder_is_cut_to_fit_where_long_paths_are_off(monkeypatch):
    """The folder a container's documents are written into is cut until a
    Windows with long paths off will make it and write into it, so a long
    clients root ends in the room sentence, never "could not be filed"
    (pilot decision P29, the review's finding 3). Elsewhere it is not cut."""
    from types import SimpleNamespace

    from tracker import filer, layout

    engagement = Path("/r/" + "x" * 150 + "/J Park & Associates/Smith Family/2025/1040 - John A. Smith")
    home = SimpleNamespace(engagement_dir=engagement, entries=[])
    original = Path("Very long container name for an email attachment bundle 2025.msg")
    monkeypatch.setattr(layout, "short_paths", lambda: False)
    whole = filer._opened_folder(home, original, [home])
    monkeypatch.setattr(layout, "short_paths", lambda: True)
    cut = filer._opened_folder(home, original, [home])
    assert layout.folder_need(cut, layout.root_of(engagement)) <= layout.path_limit()
    assert cut.parent == whole.parent and len(cut.name) < len(whole.name)
    assert whole.name.startswith(cut.name)


def test_a_held_index_is_read_again_after_a_file_is_recorded(engagement, monkeypatch):
    """P215 (E2): inside a household's hold the index is built once per
    state of the record - kept while nothing is recorded, built again the
    moment a filing moves the record's head."""
    from tracker import hold

    built = []
    real = store.documents

    def counted(conn, folder):
        built.append(folder)
        return real(conn, folder)

    monkeypatch.setattr(store, "documents", counted)
    with hold.one_household():
        assert read_index(engagement) == []
        assert read_index(engagement) == []
        assert len(built) == 1
        drop(engagement, "scan0012.pdf", "Form W-2 Wage and Tax Statement 2025")
        sort(engagement, today=DAY1)
        before = len(built)
        rows = read_index(engagement)
        assert [row.original_name for row in rows] == ["scan0012.pdf"]
        assert read_index(engagement) == rows
        assert len(built) == before + 1
