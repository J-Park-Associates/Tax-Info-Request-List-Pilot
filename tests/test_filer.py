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

from tests.conftest import TEST_CLIENT, make_engagement, named_page, sort, sort_all
from tests.test_scanner import text_pdf
from tracker import ledger, reasons, store
from tracker.filer import (
    DUPLICATE,
    FILED,
    NEEDS_REVIEW,
    FilingError,
    ensure,
    prepared_name_for,
    read_index,
)
from tracker.fsio import TEMP_SUFFIX
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

DAY1 = dt.date(2026, 7, 1)
DAY2 = dt.date(2026, 7, 9)
#: The day a pass recovers what a run left half done (decision 119): the
#: row it records is still dated the day the decision was made.
DAY3 = dt.date(2026, 7, 15)

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
    return make_engagement(tmp_path, ITEMS)


def drop(engagement, name, text, who=TEST_CLIENT):
    """Client drops one document into the household's one inbox.

    The page carries the return's person on it (decision 128), the way a
    real W-2 carries its employee's name: a named request files only where
    one of the return's spellings is on the page. A test that means "a
    page naming nobody here" passes ``who=""`` or writes the PDF itself.
    """
    return text_pdf(inbox_of(engagement) / name, named_page(text, who) if who else text)


def originals(engagement):
    """The folder the client sees for this return's year: where an original
    rests once the pass has moved it out of the inbox (decision 125)."""
    return originals_of(engagement)


def original_at(engagement, name):
    """How a row names an original it holds: relative to the return folder,
    POSIX, and across the two trees - so it begins with ``..``."""
    return location_of(engagement, originals_of(engagement) / name)


def cache_rows(engagement):
    """The engagement's verdict cache as the store holds it: (memos, verdicts)."""
    from tracker.content_check import CACHE_VERSION

    return store.cached_verdicts(store.connect(), engagement, version=CACHE_VERSION)


class RequestFiles:
    """What one request's folder was, flat (decision 168): its working copies
    sit in Prepared itself, and a file is the request's when its name begins
    with the identifier (``tracker.scaffold.assign_files``). So ``/ name``
    is where a file named for the request goes - ``Prepared/A01 - name``,
    or ``Prepared/<name>`` for a name that already begins with it - and
    ``iterdir()`` is the request's files. Dragging a copy "into C01" is
    renaming it under C01's name beside the others, which is the only way a
    person can move a copy between requests now."""

    def __init__(self, root: Path, identifier: str):
        self.root, self.identifier = root, identifier

    def __truediv__(self, name: str) -> Path:
        from tracker.scaffold import matches_identifier

        if matches_identifier(name, self.identifier):
            return self.root / name
        return self.root / f"{self.identifier} - {name}"

    def iterdir(self):
        from tracker.scaffold import assign_files

        return iter(assign_files(self.root, [self.identifier])[self.identifier])

    def mkdir(self, **_kwargs) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def prepared(engagement, folder_prefix):
    """The review folder itself, or one request's files as a
    :class:`RequestFiles` - there is no folder per request (decision 168)."""
    root = engagement / PREPARED_DIR_NAME
    if folder_prefix == REVIEW_DIR_NAME:
        return root / REVIEW_DIR_NAME
    return RequestFiles(root, folder_prefix.split(" ")[0])


def kept_files(engagement):
    """Every preserved original and every working copy, by relative path.

    The conservation check: what is under the engagement is the arrivals
    plus the copies a rule made, and nothing else. ``files_under()`` below
    is the whole folder with each file's bytes and time, for the claims
    about a pass that must change nothing; this one names the two folders a
    rule writes in, which is what a claim about copies wants to say.
    """
    roots = (originals(engagement), engagement / PREPARED_DIR_NAME)
    return sorted(location_of(engagement, path)
                  for root in roots for path in root.rglob("*") if path.is_file())


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
    from tests.test_reminder import DROPPED, locked
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
    from tests.test_reminder import locked

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
    waiting = drop(engagement, "big.pdf", "Form W-2 Wage and Tax Statement 2025")
    monkeypatch.setattr("tracker.filer.is_cloud_placeholder", lambda p: True)

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
    from tests.test_content_check import counting_extractor
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
    from tests.test_content_check import counting_extractor

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


def test_a_retired_cache_file_is_removed_by_the_next_real_pass_and_never_read(engagement, monkeypatch):
    """Decision 107: nothing is read from the old file. A well-formed cache
    of the last layout, whose memo and verdict would have spared the scan
    its one reading, is removed by the first real pass and the scan reads
    the document all the same."""
    import json

    from tests.test_content_check import counting_extractor
    from tracker.content_check import CACHE_VERSION, RETIRED_CACHE_FILENAME, rules_fingerprint
    from tracker.scanner import scan_engagement
    from tracker.validators import sha256_of

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

    sort(engagement, today=DAY1, dry_run=True)
    assert old_file.exists() and old_temp.exists()          # a dry run leaves it where it is

    from tracker.filer import RETIRED_CACHE_REMOVED

    report = sort(engagement, today=DAY1)
    assert report.handled == 0                              # nothing to sort; the tidy-up still runs
    assert not old_file.exists() and not old_temp.exists()
    # Nothing of it reached the store: no verdict of its, and the one memo
    # there is the sweep's own reading of a file no row names (decision
    # 109), not the old file's - the scan below reads the document all the
    # same, which is the claim.
    assert cache_rows(engagement)[1] == {}
    said = [a for a in report.attention if a.error == RETIRED_CACHE_REMOVED]
    assert sorted(a.name for a in said) == sorted([old_file.name, old_temp.name])  # said once each
    assert not any(a.error == RETIRED_CACHE_REMOVED
                   for a in sort(engagement, today=DAY2).attention)          # and not again

    report = scan_engagement(engagement, today=DAY1)
    assert calls["n"] == 1                                  # read once: the file was never a hit
    assert report.updates["A01"].file_count == 1


def test_a_pass_writes_nothing_under_the_clients_root_but_the_record_and_the_page(tmp_path, monkeypatch):
    """Decision 101's walk, extended by 107: after a real sort and scan, the
    only files a pass has put under the clients root are the journal and
    the Status Report - no verdict cache, no temp file, no database."""
    from tracker.content_check import RETIRED_CACHE_FILENAME
    from tracker.ledger import LEDGER_FILENAME
    from tracker.scanner import scan_engagement
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
    from tracker.filer import read_index

    drop(engagement, "old.pdf", "Form W-2 Wage and Tax Statement 2024")   # contested: wrong year
    report = sort(engagement, today=DAY1)
    [parked] = report.review
    assert parked.candidates == "A01"
    assert read_index(engagement)[0].candidates == "A01"


def test_a_filed_row_and_a_parked_row_both_say_what_the_rules_saw(engagement):
    from tracker.content_check import RULE_REQUIRED, WHERE_TITLE
    from tracker.filer import read_index

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


# ------------------------------- the index moves into the record (d102) ----


def test_a_new_engagement_is_simply_current(engagement):
    """A brand new folder is nothing but its create: no index rows, no
    files moved, and the store describes it from its first day."""
    assert ensure(engagement) == store.CURRENT
    assert read_index(engagement) == []
    assert [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)] == [
        ledger.RULES_CHANGED]


def test_only_a_name_the_journal_cannot_hold_is_refused(engagement):
    """The journal is UTF-8 JSON: an unpaired surrogate cannot be written
    into it, and such a name once took the whole index down. A control
    character files again (decision 104): the refusal of one existed
    because a workbook is XML, and there is no workbook."""
    from tracker.filer import _storable

    inbox = inbox_of(engagement)
    assert _storable(inbox / "scan\x072025.pdf")
    assert _storable(inbox / "scan 2025.pdf")
    assert not _storable(inbox / "scan\udcff2025.pdf")


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
    assert list(ledger.fold(ledger.read_events(engagement))) == [
        e.pbc_location for e in rows]


def counted_records(monkeypatch) -> list[tuple]:
    """Every call to ``store.record``, with the events it was given.

    The pass's own import of the request list is left out: it is one call
    of its own at the start (decision 103), and what these tests are
    about is the decisions about documents.
    """
    calls: list[tuple] = []
    real = store.record

    def counting(conn, engagement_dir, *events):
        named = tuple(e[ledger.EVENT_KEY] for e in events)
        if named != (ledger.RULES_IMPORTED,):
            calls.append(named)
        return real(conn, engagement_dir, *events)

    monkeypatch.setattr(store, "record", counting)
    return calls


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


def test_a_person_filing_dismissing_or_unfiling_is_one_call_each(engagement, monkeypatch):
    from tracker.filer import assign_review_file, dismiss_review_file, unfile_document

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "notice.pdf", "an agency notice nothing asks for")
    parked = {e.original_name: e for e in sort(engagement, today=DAY1).review}
    calls = counted_records(monkeypatch)

    assign_review_file(engagement, parked["scan0012.pdf"].pbc_location, "C01", today=DAY2)
    dismiss_review_file(engagement, parked["notice.pdf"].pbc_location, today=DAY2)
    unfile_document(engagement, parked["scan0012.pdf"].pbc_location, today=DAY2)

    # The unfiling's re-scan is a call of its own, and rightly: it is the
    # pass's decision about the request, not the person's about the row.
    # Each action that moves a file writes its intent first (decision 119)
    # and dismissing moves nothing, so it writes none.
    assert calls == [(ledger.MOVING,), (ledger.ASSIGNED_BY_PERSON,),
                     (ledger.DISMISSED_BY_PERSON,),
                     (ledger.MOVING,), (ledger.UNFILED_BY_PERSON,), (ledger.SCANNED,)]


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
    import tracker.filer as filer_module
    from tracker.locking import LOCK_FILENAME

    lock = engagement / LOCK_FILENAME
    seen = []
    for name in ("load_manifest", "read_index", "iter_drops"):
        real = getattr(filer_module, name)

        def under_the_lock(*args, _real=real, _name=name, **kwargs):
            seen.append((_name, lock.exists()))
            return _real(*args, **kwargs)

        monkeypatch.setattr(filer_module, name, under_the_lock)

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    assert sort(engagement, today=DAY1).handled == 1
    assert seen and all(held for _, held in seen), seen
    assert not lock.exists()

    seen.clear()                                  # a dry run reads without a lock
    sort(engagement, today=DAY1, dry_run=True)
    assert seen and not any(held for _, held in seen)


def test_a_persons_keyword_is_recorded_in_the_same_call_as_the_filing(engagement, monkeypatch):
    """One decision, one call, one transaction (decision 103).

    The filing and the word it taught are the same decision, so they are
    the same ``store.record()`` - which means the rollback that puts a
    moved file back asks one question and not two. The word is recorded,
    never typed into the row: the rules the record holds are as they were.
    """
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    before = store.rules(store.connect(), engagement)
    calls = counted_records(monkeypatch)

    result = assign_review_file(engagement, parked.pbc_location, "C01", keyword="lender")

    assert result.keyword == "lender" and result.keyword_note == ""
    # The intent goes down before the copy moves and carries the keyword
    # with it (decision 119), so a filing finished from the record teaches
    # the request the word as well; the decision itself is still one call.
    assert calls == [(ledger.MOVING,), (ledger.ASSIGNED_BY_PERSON, ledger.KEYWORD_LEARNED)]
    assert store.rules(store.connect(), engagement) == before
    assert {i.identifier: i.any_keywords for i in load_manifest(engagement)}["C01"] == ("lender",)


def test_a_keyword_the_request_already_has_is_said_and_not_recorded_twice(engagement, monkeypatch):
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "notice.pdf", "an agency notice nothing asks for")
    parked = {e.original_name: e for e in sort(engagement, today=DAY1).review}
    assign_review_file(engagement, parked["scan0012.pdf"].pbc_location, "C01", keyword="lender")
    calls = counted_records(monkeypatch)

    again = assign_review_file(engagement, parked["notice.pdf"].pbc_location, "C01",
                               keyword="LENDER", today=DAY2)

    assert again.keyword == "" and "already had the keyword" in again.keyword_note
    assert calls == [(ledger.MOVING,), (ledger.ASSIGNED_BY_PERSON,)]


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
    import tracker.filer as filer_module

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    first = sort(engagement, today=DAY1).filed[0]
    real = filer_module.is_cloud_placeholder
    monkeypatch.setattr(filer_module, "is_cloud_placeholder",
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


def test_assigning_a_parked_file_moves_it_under_the_canonical_name(engagement):
    from tracker.filer import ASSIGNED_BY_PERSON, assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    review_copy = engagement / parked.prepared_location
    assert review_copy.exists()

    result = assign_review_file(engagement, parked.pbc_location, "C01", keyword="Home Lending", today=DAY2)

    assert result.moved_review_copy is True
    assert not review_copy.exists()
    working = engagement / result.entry.prepared_location
    assert working.name == "C01 - Mortgage Interest - TY2025.pdf"
    assert working.read_bytes() == (engagement / parked.pbc_location).read_bytes()
    assert (engagement / parked.pbc_location).exists()               # original untouched
    [row] = read_index(engagement)
    assert row.decision == FILED and row.identifier == "C01"
    assert row.reason.startswith(f"{ASSIGNED_BY_PERSON} on {DAY2.isoformat()}; was: ")
    assert result.keyword == "Home Lending" and result.keyword_note == ""
    from tracker.manifest import load_manifest
    assert next(i for i in load_manifest(engagement) if i.identifier == "C01").any_keywords == ("Home Lending",)


def test_assigning_copies_from_pbc_when_the_review_copy_is_gone(engagement):
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    (engagement / parked.prepared_location).unlink()
    result = assign_review_file(engagement, "scan0012.pdf", "A01")   # by original name
    assert result.moved_review_copy is False
    assert (engagement / result.entry.prepared_location).exists()


def test_assigning_refuses_what_a_person_should_not_do(engagement):
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    with pytest.raises(FilingError, match="no request 'Z99'"):
        assign_review_file(engagement, "scan0012.pdf", "Z99")
    with pytest.raises(FilingError, match="is not waiting for review"):
        assign_review_file(engagement, "w2.pdf", "C01")               # already filed
    with pytest.raises(FilingError, match="nothing in the index is called"):
        assign_review_file(engagement, "ghost.pdf", "C01")


def test_filing_to_a_not_applicable_row_is_refused_with_its_label(tmp_path):
    from tracker.filer import assign_review_file
    from tracker.manifest import Override

    set_aside = make_engagement(tmp_path / "Set aside 2025", [
        RequestItem(identifier="A01", document="W-2", period="TY2025",
                    manual_override=Override.NOT_APPLICABLE)])
    drop(set_aside, "x.pdf", "nothing")
    sort(set_aside, today=DAY1)
    with pytest.raises(FilingError, match="A01 is Not Applicable in TY2025; clear the override first"):
        assign_review_file(set_aside, "x.pdf", "A01")


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


def test_a_failed_record_puts_the_filed_copy_back_where_the_record_says(engagement, monkeypatch):
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    def disk_full(*args, **kwargs):
        raise OSError(28, "No space left on device")
    # One transaction: it either committed or it did not, and it did not,
    # so the copy goes back to review and a retry files it once.
    monkeypatch.setattr(store, "record", disk_full)
    with pytest.raises(OSError):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    monkeypatch.undo()
    assert (engagement / parked.prepared_location).exists()
    c01 = engagement / PREPARED_DIR_NAME / "C01 - Mortgage Interest"
    assert not c01.exists() or not any(c01.iterdir())

    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    assert result.moved_review_copy is True
    assert [p.name for p in prepared(engagement, "C01").iterdir()] == [result.entry.filed_as]


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
    import tracker.filer as filer_module

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    monkeypatch.setattr(filer_module, "is_cloud_placeholder", lambda p: p.name == "w2.pdf")

    def never(path):
        raise AssertionError(f"hashed {path.name}")
    monkeypatch.setattr(filer_module, "sha256_of", never)
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


def test_an_interrupt_after_the_record_landed_does_not_undo_the_filing(engagement, monkeypatch):
    # The transaction committed and then the interrupt hit. The record says
    # Filed at the request folder, so the copy stays there - moving it back
    # would leave the record lying about where the document is.
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    real = store.record

    def interrupted(conn, engagement_dir, *events):
        # After the decision's own record, not after the intent it wrote
        # before it moved anything (decision 119): the claim is about a
        # transaction that committed.
        real(conn, engagement_dir, *events)
        if events[0][ledger.EVENT_KEY] != ledger.MOVING:
            raise KeyboardInterrupt
    monkeypatch.setattr(store, "record", interrupted)
    with pytest.raises(KeyboardInterrupt):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    monkeypatch.undo()
    [row] = read_index(engagement)
    assert row.decision == FILED and (engagement / row.prepared_location).exists()
    assert not (engagement / parked.prepared_location).exists()


def test_every_unfinished_transfer_name_is_reported_as_waiting(engagement):
    from tracker.validators import UNFINISHED_SUFFIXES

    for suffix in UNFINISHED_SUFFIXES:
        (inbox_of(engagement) / f"upload{suffix}").write_bytes(b"partial")
    report = sort(engagement, today=DAY1)
    assert sorted(p.name for p in report.waiting) == sorted(f"upload{s}" for s in UNFINISHED_SUFFIXES)



def test_assigning_reuses_a_copy_an_earlier_attempt_left_and_leaves_no_half_copy(engagement, monkeypatch):
    # The same two guarantees the sort path has (decisions 54, 56), on the
    # path a person drives: a kill after the move made a copy the index
    # never learned of, and a copy that fails half-way leaves nothing.
    import tracker.filer as filer_module
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    c01 = prepared(engagement, "C01")
    earlier = engagement / PREPARED_DIR_NAME / "C01 - Mortgage Interest - TY2025.pdf"
    (engagement / parked.prepared_location).rename(earlier)      # the killed attempt's move
    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    assert [p.name for p in c01.iterdir()] == [earlier.name] and result.entry.filed_as == earlier.name

    drop(engagement, "scan0013.pdf", "nothing the rules recognise either")
    parked = sort(engagement, today=DAY2).review[0]
    (engagement / parked.prepared_location).unlink()             # a person removed the parked copy

    def half(src, dst):
        filer_module.Path(dst).write_bytes(b"%PDF-1.4 half")
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(shutil, "copy2", half)
    with pytest.raises(OSError):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    monkeypatch.undo()
    assert [p.name for p in c01.iterdir()] == [earlier.name]     # no half copy beside it


def test_a_persons_filing_of_an_original_recorded_without_its_bytes_records_them(engagement, monkeypatch):
    # Decision 65 records an original the pass could not read back with no
    # digest. The ninth reading found that row carried through a person's
    # filing with no digest still, so the scanner never honoured the person
    # and the client was asked again. Assign records the bytes; and a later
    # pass that can read the original records them too.
    import tracker.filer as filer_module
    from tracker.filer import assign_review_file
    from tracker.validators import sha256_of

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    real = filer_module.sha256_of

    held = set()

    def unreadable_once(path):
        if path.parent == originals(engagement) and path not in held:
            # Held for the one read that records the row: since decision
            # 187 the intent fingerprints a copy's source itself, a moment
            # later, so the copy is proved and the row keeps no bytes.
            held.add(path)
            raise PermissionError("held by the sync client")
        return real(path)
    monkeypatch.setattr(filer_module, "sha256_of", unreadable_once)
    parked = sort(engagement, today=DAY1).review[0]
    monkeypatch.undo()
    assert parked.digest == "" and parked.size_kb == 0.0

    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    original = engagement / parked.pbc_location
    assert result.entry.digest == sha256_of(original) and result.entry.size_kb > 0
    (row,) = read_index(engagement)
    assert row.digest == result.entry.digest

    # And a pass, with nothing to sort, fills in the row the earlier pass could not.
    drop(engagement, "scan0013.pdf", "nothing the rules recognise either")
    monkeypatch.setattr(filer_module, "sha256_of", unreadable_once)
    sort(engagement, today=DAY2)
    monkeypatch.undo()
    assert [r.digest for r in read_index(engagement) if r.original_name == "scan0013.pdf"] == [""]
    sort(engagement, today=DAY2)
    later = next(r for r in read_index(engagement) if r.original_name == "scan0013.pdf")
    assert later.digest == sha256_of(engagement / later.pbc_location) and later.size_kb > 0


def test_bytes_recorded_after_the_fact_are_tied_to_the_row_or_not_recorded(engagement, monkeypatch):
    # The tenth reading: the digest filled in on a later pass came from the
    # original as it was THEN, so a client's replacement was adopted into
    # the old row. The eleventh: the working copy alone is no better - its
    # name is the client's and a freed name is taken by the next drop
    # called the same. A row is tied to its bytes only while its copy and
    # its original still agree; where they do not, nothing is adopted and
    # the row is said out loud, every pass.
    import tracker.filer as filer_module
    from tracker.filer import UNTIED_IN_PBC, assign_review_file
    from tracker.validators import sha256_of

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "scan0013.pdf", "nothing the rules recognise either")
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
    monkeypatch.setattr(filer_module, "sha256_of", unreadable)
    report = sort(engagement, today=DAY1)
    monkeypatch.undo()
    filed = report.filed[0]
    parked = {r.original_name: r for r in report.review}
    assert filed.digest == "" and all(r.digest == "" for r in parked.values())
    first_bytes = (engagement / filed.prepared_location).read_bytes()

    # The client replaces the W-2 under its own name; a reviewer's app re-saves scan0012's parked copy.
    text_pdf(originals(engagement) / "w2.pdf", "Form W-2 Wage and Tax Statement 2025 corrected")
    text_pdf(engagement / parked["scan0012.pdf"].prepared_location, "nothing the rules recognise, annotated")

    report = sort(engagement, today=DAY2)
    rows = {r.original_name: r for r in read_index(engagement)}
    assert rows["w2.pdf"].digest == "" and rows["scan0012.pdf"].digest == ""              # nothing adopted
    assert rows["scan0013.pdf"].digest == sha256_of(originals(engagement) / "scan0013.pdf")   # tied: copy and original agree
    assert (engagement / filed.prepared_location).read_bytes() == first_bytes            # untouched
    said = sorted(e.name for e in report.attention if e.error.startswith(UNTIED_IN_PBC.split("{")[0]))
    assert said == ["scan0012.pdf", "w2.pdf"] and report.errors == []   # for a person, not a failed pass

    # A person cannot file either untied row under it; the tied one files and carries its bytes.
    with pytest.raises(FilingError, match="look at both files first"):
        assign_review_file(engagement, parked["scan0012.pdf"].pbc_location, "C01", today=DAY2)
    result = assign_review_file(engagement, parked["scan0013.pdf"].pbc_location, "C01", today=DAY2)
    assert result.entry.digest == rows["scan0013.pdf"].digest


def test_a_persons_filing_moves_the_parked_copy_only_while_it_holds_the_rows_bytes(engagement):
    # The eleventh reading: a parked name is the client's, so once row A's
    # copy is gone the next drop called the same parks under that very
    # path, and filing row A carried document B into the request folder
    # under A's canonical name.
    #
    # Since decision 157 the pass makes a parked copy that went again from
    # its original before it parks anything, so the freed name is taken
    # only while A's original cannot be read - still syncing, here.
    import tracker.filer as filer_module
    from tracker.filer import assign_review_file
    from tracker.validators import sha256_of

    drop(engagement, "Scan.pdf", "document A, nothing the rules recognise")
    row_a = sort(engagement, today=DAY1).review[0]
    (engagement / row_a.prepared_location).unlink()                  # a person took it away to read
    drop(engagement, "Scan.pdf", "document B, unrelated")
    syncing = locate(engagement, row_a.pbc_location)
    real = filer_module.is_cloud_placeholder
    with pytest.MonkeyPatch.context() as sync:
        sync.setattr(filer_module, "is_cloud_placeholder", lambda p: p == syncing or real(p))
        row_b = sort(engagement, today=DAY2).review[0]
    assert row_b.prepared_location == row_a.prepared_location         # the freed name, taken

    result = assign_review_file(engagement, row_a.pbc_location, "C01", today=DAY2)
    filed = engagement / result.entry.prepared_location
    assert result.moved_review_copy is False
    assert sha256_of(filed) == row_a.digest                            # document A, copied from its original
    assert (engagement / row_b.prepared_location).exists()            # document B still waits for a person
    assert sha256_of(engagement / row_b.prepared_location) == row_b.digest


def test_a_parked_path_a_later_row_claims_means_the_earlier_copy_is_gone(engagement, monkeypatch):
    # The twelfth reading: a digest-less row A whose parked copy a person
    # removed, then a same-named drop B parked under the freed name, was
    # "untied" every pass and refused for ever - though the index itself
    # says whose the file at that path is.
    import tracker.filer as filer_module
    from tracker.filer import assign_review_file
    from tracker.validators import sha256_of

    drop(engagement, "Scan.pdf", "document A, nothing the rules recognise")
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
    monkeypatch.setattr(filer_module, "sha256_of", unreadable)
    row_a = sort(engagement, today=DAY1).review[0]
    monkeypatch.undo()
    assert row_a.digest == ""
    (engagement / row_a.prepared_location).unlink()
    drop(engagement, "Scan.pdf", "document B, unrelated")
    report = sort(engagement, today=DAY2)
    row_b = report.review[0]
    assert row_b.prepared_location == row_a.prepared_location
    assert report.attention == [] and report.errors == []          # not untied: its copy is gone

    result = assign_review_file(engagement, row_a.pbc_location, "C01", today=DAY2)
    assert result.entry.digest == sha256_of(originals(engagement) / "Scan.pdf")   # document A, from its original
    assert sha256_of(engagement / result.entry.prepared_location) == result.entry.digest
    assert (engagement / row_b.prepared_location).exists()          # document B still waits


def test_an_annotated_parked_copy_is_left_behind_and_said_so(engagement):
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    text_pdf(engagement / parked.prepared_location, "nothing the rules recognise, with a reviewer's note")
    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    assert result.moved_review_copy is False and "left there" in result.left_in_review
    assert (engagement / parked.prepared_location).exists()
    assert (engagement / result.entry.prepared_location).read_bytes() == (originals(engagement) / "scan0012.pdf").read_bytes()


def test_the_unlistable_walk_covers_the_same_ground_as_the_others(engagement, tmp_path):
    from tests.samples import listing_denied
    from tracker.filer import unlistable_folders

    inbox = inbox_of(engagement)
    inside = inbox / "from my phone" / "scans"
    inside.mkdir(parents=True)
    staging = inbox / ".tmp.driveupload"
    staging.mkdir()
    assert unlistable_folders(inbox) == []
    with listing_denied(inside):                     # a folder the client dragged in, denied
        assert unlistable_folders(inbox) == [inside]
    if sys.platform == "win32":
        import _winapi

        outside = tmp_path / "outside" / "deep"
        outside.mkdir(parents=True)
        _winapi.CreateJunction(str(tmp_path / "outside"), str(inbox / "link"))
        assert unlistable_folders(inbox) == []                        # never walks behind the junction


def test_a_folder_the_run_cannot_list_is_reported_every_pass(engagement):
    from tests.samples import listing_denied
    from tracker.filer import unlistable_folders

    denied = inbox_of(engagement) / "from my accountant"
    denied.mkdir()
    text_pdf(denied / "inside-w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "readable-w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    with listing_denied(denied):
        assert unlistable_folders(inbox_of(engagement)) == [denied]
        report = sort(engagement, today=DAY1)
    assert [e.original_name for e in report.filed] == ["readable-w2.pdf"]
    assert [(e.name, e.left_in_place) for e in report.errors] == [(denied.name, True)]
    assert "cannot list" in report.errors[0].error


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


def test_assigning_a_replaced_original_is_refused_not_recorded_under_the_old_bytes(engagement):
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    (engagement / parked.prepared_location).unlink()             # the parked copy is gone
    text_pdf(originals(engagement) / "scan0012.pdf", "the client replaced it with something else")
    with pytest.raises(FilingError, match="replaced after it arrived"):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.digest == parked.digest


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
    import tracker.filer as filer_module
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
    monkeypatch.setattr(filer_module, "sha256_of", unreadable)
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
    import tracker.filer as filer_module

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    monkeypatch.setattr(filer_module, "is_cloud_placeholder", lambda p: p.parent == originals(engagement))
    report = sort(engagement, today=DAY2)
    assert report.attention == [] and report.errors == []


def test_a_failed_record_puts_back_a_parked_copy_a_reused_one_stood_in_for(engagement, monkeypatch):
    # Assign reuses a killed attempt's copy and removes the parked one it
    # stands in for (decision 69). The rollback covered the moved copy and
    # the fresh copy but not that removal, so a refused write left the row
    # still naming a parked copy that was no longer there.
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    c01 = engagement / PREPARED_DIR_NAME / "C01 - Mortgage Interest"
    c01.mkdir(parents=True, exist_ok=True)
    attempt = c01 / "C01 - Mortgage Interest - TY2025.pdf"
    attempt.write_bytes((engagement / parked.prepared_location).read_bytes())

    def disk_full(*args, **kwargs):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(store, "record", disk_full)
    with pytest.raises(OSError):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    monkeypatch.undo()

    back = engagement / parked.prepared_location
    assert back.is_file() and back.read_bytes() == attempt.read_bytes()
    assert [p.name for p in c01.iterdir()] == [attempt.name]      # the reused copy stays where it is
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and (engagement / row.prepared_location).is_file()

    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    assert result.entry.filed_as == attempt.name and not back.exists()


def test_an_empty_folder_is_cleared_by_a_pass_with_nothing_to_sort(engagement):
    # The tidy-up used to sit past an early return, so a pass that found
    # nothing to sort left the folder the client dragged in behind for ever.
    left_behind = inbox_of(engagement) / "from my phone"
    left_behind.mkdir()
    report = sort(engagement, today=DAY1)
    assert report.handled == 0 and not left_behind.exists()


# ------------------------------- a person says no request asks for it (d76) ----


def test_dismissing_a_parked_file_rewrites_its_row_and_moves_nothing(engagement):
    """Not Requested is a decision about the request list, not about the file.

    An agency notice the client sent is still the client's: the working copy
    stays parked and the original stays in PBC. What the row says changes,
    and what it said before is kept after it.
    """
    from tracker.filer import DISMISSED_BY_PERSON, NOT_REQUESTED, dismiss_review_file

    drop(engagement, "irs-notice.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    copy = engagement / parked.prepared_location
    original = engagement / parked.pbc_location
    assert copy.is_file()

    result = dismiss_review_file(engagement, parked.pbc_location, "an IRS notice", today=DAY2)

    assert result.entry.decision == NOT_REQUESTED
    assert result.entry.reason == (
        f"{DISMISSED_BY_PERSON} on {DAY2.isoformat()} (an IRS notice); was: {parked.reason}"
    )
    assert copy.is_file() and copy.read_bytes() == original.read_bytes()
    assert original.is_file()
    [row] = read_index(engagement)
    assert row.decision == NOT_REQUESTED
    assert row.prepared_location == parked.prepared_location


def test_the_same_document_sent_again_after_a_dismissal_parks_again_and_names_the_earlier_decision(
    engagement,
):
    """Not requested is a decision about one document on one day (decision 111).

    The client was never told the document was unnecessary, so they send it
    again; a silent Duplicate would tell nobody. It is routed like any drop,
    and where no request takes it the row says what was decided before -
    the date and the person's note, as they wrote them - so the person who
    set it aside decides again with both facts in front of them.
    """
    from tracker.filer import NOT_REQUESTED, RESENT_AFTER_SET_ASIDE, dismiss_review_file

    drop(engagement, "notice.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    dismissed = dismiss_review_file(
        engagement, parked.pbc_location, "an IRS notice", today=DAY2
    ).entry
    set_aside_copy = engagement / dismissed.prepared_location
    before = set_aside_copy.read_bytes()

    drop(engagement, "notice.pdf", "nothing the rules recognise")   # same bytes, same name
    report = sort(engagement, today=DAY2)

    (again,) = report.review
    assert report.duplicates == []
    assert again.decision == NEEDS_REVIEW
    assert again.reason.startswith(RESENT_AFTER_SET_ASIDE.format(earlier=dismissed.reason))
    assert DAY2.isoformat() in again.reason and "an IRS notice" in again.reason
    assert UNMATCHED in again.reason                    # and why it parked, as always

    # The set-aside row and its copy are exactly as they were.
    assert set_aside_copy.read_bytes() == before
    rows = read_index(engagement)
    assert [r.decision for r in rows] == [NOT_REQUESTED, NEEDS_REVIEW]
    assert rows[0].reason == dismissed.reason
    assert rows[0].prepared_location == dismissed.prepared_location

    # Two arrivals, two preserved originals, two parked copies - and
    # _unique_path never overwrote the copy that was already there.
    assert kept_files(engagement) == [
        original_at(engagement, "notice (2).pdf"),
        original_at(engagement, "notice.pdf"),
        f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/notice (2).pdf",
        f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/notice.pdf",
    ]


def test_a_resend_after_a_dismissal_owns_its_own_working_copy(engagement):
    """One row, one working copy.

    If the re-parked row named the set-aside row's file, filing either one
    would carry the other's copy out from under it.
    """
    from tracker.filer import assign_review_file, dismiss_review_file

    drop(engagement, "notice.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    dismissed = dismiss_review_file(engagement, parked.pbc_location, today=DAY2).entry
    drop(engagement, "notice.pdf", "nothing the rules recognise")
    again = sort(engagement, today=DAY2).review[0]
    assert again.prepared_location != dismissed.prepared_location
    resent_copy = engagement / again.prepared_location
    before = resent_copy.read_bytes()

    # A person files the *dismissed* row: only its own copy moves.
    result = assign_review_file(engagement, dismissed.pbc_location, "C01", today=DAY2)

    assert result.moved_review_copy is True
    assert not (engagement / dismissed.prepared_location).exists()
    assert resent_copy.is_file() and resent_copy.read_bytes() == before
    still = {r.pbc_location: r for r in read_index(engagement)}[again.pbc_location]
    assert still.decision == NEEDS_REVIEW and still.reason == again.reason
    assert still.prepared_location == again.prepared_location
    assert kept_files(engagement) == [
        original_at(engagement, "notice (2).pdf"),
        original_at(engagement, "notice.pdf"),
        f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/notice (2).pdf",
        f"{PREPARED_DIR_NAME}/{result.entry.filed_as}",
    ]


def test_a_resend_after_a_dismissal_files_when_the_list_now_asks_for_it(engagement):
    """The person may have taught the list since they set it aside.

    Parking what exactly one request now accepts would be guessing that the
    earlier decision still stands over the later rule, so the re-send is
    routed first - and the row still says it was set aside before.
    """
    from tracker.filer import RESENT_AFTER_SET_ASIDE, dismiss_review_file

    drop(engagement, "notice.pdf", "an agency notice about your account, 2025")
    parked = sort(engagement, today=DAY1).review[0]
    dismissed = dismiss_review_file(engagement, parked.pbc_location, today=DAY2).entry

    # A person edits the request list in the app: C01 now asks for it.
    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement)]
    save_rules(engagement, [
        RequestItem(**{**rule_from_json(rule_to_json(row)),
                       "required_keywords": ("agency notice",)})
        if row.identifier == "C01" else row
        for row in rows
    ], load_engagement_info(engagement))

    drop(engagement, "notice.pdf", "an agency notice about your account, 2025")
    report = sort(engagement, today=DAY2)

    (filed,) = report.filed
    assert report.review == [] and report.duplicates == []
    assert filed.identifier == "C01"
    # The re-send is name-checked before it files (decision 128), so the
    # confirmation follows the sentence that says it was set aside.
    assert f"; {RESENT_AFTER_SET_ASIDE.format(earlier=dismissed.reason)}" in filed.reason
    assert filed.reason.endswith(f"; name confirmed ({TEST_CLIENT})")
    copy = engagement / filed.prepared_location
    assert copy.is_file() and copy.read_bytes() == (originals(engagement) / "notice (2).pdf").read_bytes()
    # The set-aside row keeps its own parked copy; only the re-send was filed.
    assert (engagement / dismissed.prepared_location).is_file()
    assert kept_files(engagement) == [
        original_at(engagement, "notice (2).pdf"),
        original_at(engagement, "notice.pdf"),
        f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/notice.pdf",
        f"{PREPARED_DIR_NAME}/{filed.filed_as}",
    ]


def test_set_aside_bytes_sent_again_after_their_original_went_are_routed_afresh(engagement):
    """d157's review, S-2 (its probe P5). The client deletes the original
    of a document a person set aside, the list then gains its request, and
    the client sends the same bytes again. Decision 157's put-back is for a
    row's own original coming home; a set-aside row is a person's answer
    about one day's document, and decision 111 routes the same bytes sent
    again afresh. So the re-send files to the request the list now asks
    for, under a name of its own, the set-aside row stays as it was, and
    the letter no longer asks for a document the client sent twice."""
    from tracker.filer import NOT_REQUESTED, RESENT_AFTER_SET_ASIDE, dismiss_review_file
    from tracker.manifest import Status

    drop(engagement, "notice.pdf", "an agency notice about your account, 2025")
    parked = sort(engagement, today=DAY1).review[0]
    dismissed = dismiss_review_file(engagement, parked.pbc_location, today=DAY2).entry

    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement)]
    save_rules(engagement, [
        RequestItem(**{**rule_from_json(rule_to_json(row)),
                       "required_keywords": ("agency notice",)})
        if row.identifier == "C01" else row
        for row in rows
    ], load_engagement_info(engagement))

    (originals(engagement) / "notice.pdf").unlink()
    drop(engagement, "notice.pdf", "an agency notice about your account, 2025")
    report, _scanned = _a_pass(engagement, DAY2)

    (filed,) = report.filed
    assert filed.identifier == "C01" and report.review == [] and report.duplicates == []
    assert f"; {RESENT_AFTER_SET_ASIDE.format(earlier=dismissed.reason)}" in filed.reason
    assert filed.pbc_location == original_at(engagement, "notice (2).pdf")
    assert events_named(engagement, ledger.ORIGINAL_RETURNED) == []
    assert not (originals(engagement) / "notice.pdf").exists()
    [kept] = [row for row in read_index(engagement) if ledger_key(row) == ledger_key(dismissed)]
    assert kept.decision == NOT_REQUESTED
    assert _status(engagement, "C01").status == Status.RECEIVED
    assert "C01" not in _asked(engagement, DAY2)


def test_a_third_send_of_set_aside_bytes_is_a_duplicate_of_the_parked_row(engagement):
    """The queue holds a document once: the second arrival is where the work is."""
    from tracker.filer import DUPLICATE_OF_PARKED, dismiss_review_file

    drop(engagement, "notice.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    dismiss_review_file(engagement, parked.pbc_location, today=DAY2)
    drop(engagement, "notice.pdf", "nothing the rules recognise")
    again = sort(engagement, today=DAY2).review[0]

    drop(engagement, "notice.pdf", "nothing the rules recognise")
    report = sort(engagement, today=DAY2)

    (dup,) = report.duplicates
    assert report.review == []
    assert dup.decision == DUPLICATE and dup.prepared_location == ""
    assert dup.reason == DUPLICATE_OF_PARKED.format(
        name=again.original_name, copy=again.filed_as
    )
    assert sorted(p.name for p in review_dir(engagement).iterdir()) == ["notice (2).pdf", "notice.pdf"]


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
    from tracker.filer import DUPLICATE_OF_MOVED, FILE_MOVED

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


def test_filing_a_dismissed_document_is_how_the_decision_is_undone(engagement):
    """A person who was wrong files it; there is no second undo path to build."""
    from tracker.filer import ASSIGNED_BY_PERSON, assign_review_file, dismiss_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    dismiss_review_file(engagement, parked.pbc_location, today=DAY2)

    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)

    assert result.moved_review_copy is True
    assert result.entry.filed_as == "C01 - Mortgage Interest - TY2025.pdf"
    [row] = read_index(engagement)
    assert row.decision == FILED and row.identifier == "C01"
    assert row.reason.startswith(f"{ASSIGNED_BY_PERSON} on {DAY2.isoformat()}; was: ")
    assert (engagement / row.prepared_location).is_file()


def test_dismissing_something_that_is_not_parked_says_what_it_is(engagement):
    """A filed document is not a person's to dismiss without unfiling it first."""
    from tracker.filer import dismiss_review_file

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    with pytest.raises(FilingError, match=f"is not waiting for review \\(it is {FILED}"):
        dismiss_review_file(engagement, "w2.pdf", today=DAY2)
    with pytest.raises(FilingError, match="nothing in the index is called"):
        dismiss_review_file(engagement, "ghost.pdf", today=DAY2)


def test_dismissing_takes_the_engagement_lock(engagement):
    """A decision is written to the index, so it queues behind a run like every other."""
    from tracker.filer import NOT_REQUESTED, dismiss_review_file
    from tracker.locking import LOCK_FILENAME, EngagementLockedError

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    (engagement / LOCK_FILENAME).write_text(f"pid={os.getpid()}", encoding="utf-8")
    with pytest.raises(EngagementLockedError):
        dismiss_review_file(engagement, parked.pbc_location, today=DAY2)
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW               # nothing was written

    (engagement / LOCK_FILENAME).unlink()
    result = dismiss_review_file(engagement, parked.pbc_location, today=DAY2)
    assert result.entry.decision == NOT_REQUESTED
    assert not (engagement / LOCK_FILENAME).exists()


# ----------------------- a filed document goes back for review (d77) ----


def review_dir(engagement):
    return engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME


def test_unfiling_puts_the_working_copy_back_under_the_clients_own_name(engagement):
    """The parked name is the client's, whichever direction the document travels."""
    from tracker.filer import UNFILED_BY_PERSON, unfile_document

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    working = engagement / filed.prepared_location
    assert working.is_file()

    result = unfile_document(engagement, filed.pbc_location, "wrong client", today=DAY2)

    assert result.moved_working_copy is True and result.left_filed == ""
    assert not working.exists()
    parked = engagement / result.entry.prepared_location
    assert parked.name == "w2 john.pdf" and parked.parent == review_dir(engagement)
    assert parked.read_bytes() == (engagement / filed.pbc_location).read_bytes()
    assert (engagement / filed.pbc_location).is_file()          # the original is untouched
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == ""
    assert row.reason == (
        f"{UNFILED_BY_PERSON} on {DAY2.isoformat()} (wrong client); was: {filed.reason}"
    )


def test_filing_an_unfiled_document_puts_it_under_the_canonical_name_again(engagement):
    """Refiling is unfiling and then filing; there is no third path to keep honest."""
    from tracker.filer import (
        ASSIGNED_BY_PERSON,
        UNFILED_BY_PERSON,
        assign_review_file,
        unfile_document,
    )

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    unfile_document(engagement, filed.pbc_location, today=DAY2)

    result = assign_review_file(engagement, filed.pbc_location, "C01", today=DAY2)

    assert result.moved_review_copy is True
    assert result.entry.filed_as == "C01 - Mortgage Interest - TY2025.pdf"
    assert not list(review_dir(engagement).iterdir())
    [row] = read_index(engagement)
    assert row.decision == FILED and row.identifier == "C01"
    assert row.reason.startswith(
        f"{ASSIGNED_BY_PERSON} on {DAY2.isoformat()}; was: {UNFILED_BY_PERSON}"
    )


def test_a_page_that_prints_two_forms_files_a_copy_under_each_and_unfiles_as_one(engagement):
    """Decision 94: one original, one index row, one working copy per request
    that asked for a form the page names - and unfiling takes every copy
    back with the row, because the row is one row."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.filer import unfile_document
    from tracker.validators import sha256_of

    original = drop(engagement, "scan0003.pdf",
                    "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    before = original.read_bytes()

    (entry,) = sort(engagement, today=DAY1).filed

    assert entry.identifier == "A01"
    assert entry.filed_names == [
        "A01 - W-2 Wage Statements - TY2025.pdf",
        "C01 - Mortgage Interest - TY2025.pdf",
    ]
    assert entry.filed_as == entry.filed_names[0]
    copies = [engagement / location for location in entry.filed_locations]
    assert all(copy.read_bytes() == before for copy in copies)
    assert "A01, C01" in entry.reason
    [row] = read_index(engagement)
    assert row.also_filed == entry.also_filed and row.also_filed
    assert row.filed_locations == entry.filed_locations

    unfile_document(engagement, entry.pbc_location, today=DAY2)

    assert not any(copy.exists() for copy in copies)
    [parked] = list(review_dir(engagement).iterdir())
    assert parked.name == "scan0003.pdf" and sha256_of(parked) == entry.digest
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.also_filed == "" and row.identifier == ""


def test_the_scan_after_a_two_form_split_accepts_the_copy_under_each_request(engagement, monkeypatch):
    """Decision 94's second copy is validated on the verdict the router filed
    it on, not on the ordinary reading that called the page one form's. The
    ordinary reading refuses C01 (the W-2 is the page's own form, the 1098
    is not); the split's reading accepts it; the scan must find the second
    in the cache - and read nothing again - or the copy fails validation
    and the client is asked for a 1098 they already sent."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tests.test_content_check import counting_extractor
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
    from tracker.content_check import ContentCache, check_content

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
    from tracker.content_check import CACHE_VERSION
    from tracker.ledger import EVENT_KEY, SCANNED, read_events
    from tracker.scanner import scan_engagement

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


def test_unfiling_something_that_is_not_filed_says_what_it_is(engagement):
    """Each of the other decisions needs a different answer, so none of them is guessed."""
    from tracker.filer import (
        NOT_REQUESTED,
        dismiss_review_file,
        unfile_document,
    )

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    with pytest.raises(FilingError, match=rf"is not filed \(it is {NEEDS_REVIEW}\)"):
        unfile_document(engagement, parked.pbc_location, today=DAY2)

    dismiss_review_file(engagement, parked.pbc_location, today=DAY2)
    with pytest.raises(FilingError, match=rf"is not filed \(it is {NOT_REQUESTED}\)"):
        unfile_document(engagement, parked.pbc_location, today=DAY2)

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025")
    duplicate = sort(engagement, today=DAY2).duplicates[0]
    with pytest.raises(FilingError, match=rf"is not filed \(it is {DUPLICATE}\)"):
        unfile_document(engagement, duplicate.pbc_location, today=DAY2)

    with pytest.raises(FilingError, match="nothing in the index is called"):
        unfile_document(engagement, "ghost.pdf", today=DAY2)


def test_a_working_copy_somebody_re_saved_is_left_where_it_is_and_said_so(engagement):
    """A reviewer's notes are work. Which of the two files the firm wants is not ours."""
    from tracker.filer import LEFT_FILED, unfile_document

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    working = engagement / filed.prepared_location
    working.write_bytes(working.read_bytes() + b"% a reviewer's note\n")

    result = unfile_document(engagement, filed.pbc_location, today=DAY2)

    assert result.moved_working_copy is False
    assert working.is_file()                                   # the notes are not thrown away
    parked = engagement / result.entry.prepared_location
    assert parked.is_file()
    assert parked.read_bytes() == (engagement / filed.pbc_location).read_bytes()
    assert result.left_filed == LEFT_FILED.format(
        location=filed.prepared_location, parked=parked.name)


def test_after_unfiling_the_request_is_not_received_and_the_note_says_why(engagement):
    """The status is put back in the same breath; nothing waits for the next pass."""
    from tracker.filer import unfile_document
    from tracker.manifest import Status, load_manifest
    from tracker.scanner import REGRESSION_FILES_CHANGED, REGRESSION_NOTE, scan_engagement

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025 John")
    drop(engagement, "w2 jane.pdf", "Form W-2 Wage and Tax Statement 2025 Jane")
    filed = sort(engagement, today=DAY1).filed
    assert {e.identifier for e in filed} == {"A01"}            # the row expects two
    scan_engagement(engagement, today=DAY1)
    a01 = next(i for i in load_manifest(engagement) if i.identifier == "A01")
    assert a01.status == Status.RECEIVED

    result = unfile_document(engagement, filed[0].pbc_location, today=DAY2)

    assert result.scan_note == ""
    a01 = next(i for i in load_manifest(engagement) if i.identifier == "A01")
    assert a01.status == Status.PARTIAL
    assert REGRESSION_NOTE.format(
        status=Status.RECEIVED, date=DAY1.isoformat(), why=REGRESSION_FILES_CHANGED,
    ) in a01.validation_notes


def taught_keywords(engagement) -> dict[str, tuple[str, ...]]:
    return {i.identifier: i.any_keywords for i in load_manifest(engagement)}


def teach(engagement, identifier: str, keyword: str) -> None:
    """A keyword recorded against a request, as a person's filing records it."""
    from tracker.locking import engagement_lock

    with engagement_lock(engagement):
        ensure(engagement)
        store.record(store.connect(), engagement, ledger.new(ledger.KEYWORD_LEARNED, **{
            ledger.IDENTIFIER_KEY: identifier, ledger.KEYWORD_KEY: keyword,
        }))


def test_unfiling_still_unlearns_nothing(engagement):
    """Decision 77's second half, prose until decision 113 gave it a way back.

    A keyword is a rule about documents: the request wanted the word when
    the document was filed and wants it still, and guessing which word to
    take back would be guessing. A person who wants one back says which,
    in the editor.
    """
    from tracker.filer import assign_review_file, unfile_document

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    assign_review_file(engagement, parked.pbc_location, "C01", keyword="lender", today=DAY2)
    assert taught_keywords(engagement)["C01"] == ("lender",)

    unfile_document(engagement, parked.pbc_location, today=DAY2)

    assert taught_keywords(engagement)["C01"] == ("lender",)
    assert store.learned_keywords(store.connect(), engagement) == {"c01": ("lender",)}
    names = [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)]
    assert ledger.KEYWORD_UNLEARNED not in names


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


def test_the_next_pass_leaves_an_unfiled_original_where_the_row_says(engagement):
    """It is still in PBC with a row, so it is nobody's stray and no second copy is made."""
    from tracker.filer import unfile_document

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    unfile_document(engagement, filed.pbc_location, today=DAY2)
    parked = sorted(p.name for p in review_dir(engagement).iterdir())

    report = sort(engagement, today=DAY2)

    assert report.handled == 0 and report.errors == [] and report.attention == []
    assert sorted(p.name for p in review_dir(engagement).iterdir()) == parked
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW

    # And the same document sent again is what a re-send of a parked one is.
    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025")
    again = sort(engagement, today=DAY2)
    assert [e.original_name for e in again.duplicates] == ["w2 again.pdf"]
    assert sorted(p.name for p in review_dir(engagement).iterdir()) == parked


def test_a_failed_record_puts_the_unfiled_copy_back_where_the_record_says(engagement, monkeypatch):
    """A retry does this once, not twice: the file goes where the record says."""
    from tracker.filer import unfile_document

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    working = engagement / filed.prepared_location

    def disk_full(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(store, "record", disk_full)
    with pytest.raises(OSError):
        unfile_document(engagement, filed.pbc_location, today=DAY2)
    monkeypatch.undo()

    assert working.is_file()
    assert not list(review_dir(engagement).iterdir())
    [row] = read_index(engagement)
    assert row.decision == FILED and row.prepared_location == filed.prepared_location


# ------------- a person's action is judged against the record (d112) ----


def seq_of(engagement, entry):
    """One index row's sequence number - the journal line that last wrote it.

    What the API ships beside the row and what a person's action carries
    back, read here the way the API reads it.
    """
    from tracker.records import ledger_key

    return store.document_seqs(store.connect(), engagement)[ledger_key(entry)]


def every_byte(folder):
    """Every file under the engagement, by path, with its bytes."""
    return {path.relative_to(folder).as_posix(): path.read_bytes()
            for path in sorted(folder.rglob("*")) if path.is_file()}


def test_an_assign_with_a_stale_seq_refuses_naming_what_the_record_now_says_and_touches_nothing(
        engagement):
    """The harm decision 112 is about: a person opened the card, was called
    away, and came back to File it on a row somebody had meanwhile set
    aside. The row is still parked, so the by-name refusal says nothing
    about it; its sequence number has moved, and that is what catches it."""
    from tracker.filer import (
        NOT_REQUESTED,
        StaleRowError,
        assign_review_file,
        dismiss_review_file,
    )

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    as_the_person_saw_it = seq_of(engagement, parked)

    dismiss_review_file(engagement, parked.pbc_location, "an IRS notice", today=DAY2)
    lines = len(ledger.read_events(engagement))
    files = every_byte(engagement)

    with pytest.raises(StaleRowError) as raised:
        assign_review_file(engagement, parked.pbc_location, "C01",
                           today=DAY2, seq=as_the_person_saw_it)

    # The sentence says what the record now holds, not only that it said no.
    said = str(raised.value)
    assert parked.original_name in said and NOT_REQUESTED in said and "an IRS notice" in said
    # And nothing happened: no file moved, no copy made, no line appended.
    assert every_byte(engagement) == files
    assert len(ledger.read_events(engagement)) == lines
    [row] = read_index(engagement)
    assert row.decision == NOT_REQUESTED


def test_an_assign_with_the_current_seq_proceeds(engagement):
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    result = assign_review_file(engagement, parked.pbc_location, "C01",
                                today=DAY2, seq=seq_of(engagement, parked))

    assert result.entry.decision == FILED and result.entry.identifier == "C01"
    assert (engagement / result.entry.prepared_location).is_file()


@pytest.mark.parametrize("action", ("dismiss", "unfile"))
def test_a_dismiss_and_an_unfile_with_a_stale_seq_refuse_likewise(engagement, action):
    """The same check on the other two decisions: a row dismissed twice from
    one stale card, and a row somebody re-filed between the list being drawn
    and Unfile being pressed."""
    from tracker.filer import (
        StaleRowError,
        assign_review_file,
        dismiss_review_file,
        unfile_document,
    )

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    if action == "dismiss":
        as_the_person_saw_it = seq_of(engagement, parked)
        dismiss_review_file(engagement, parked.pbc_location, "somebody else", today=DAY2)
    else:
        filed = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2).entry
        as_the_person_saw_it = seq_of(engagement, filed)
        unfile_document(engagement, parked.pbc_location, today=DAY2)
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)

    lines = len(ledger.read_events(engagement))
    with pytest.raises(StaleRowError) as raised:
        if action == "dismiss":
            dismiss_review_file(engagement, parked.pbc_location,
                                today=DAY2, seq=as_the_person_saw_it)
        else:
            unfile_document(engagement, parked.pbc_location,
                            today=DAY2, seq=as_the_person_saw_it)

    assert parked.original_name in str(raised.value)
    assert len(ledger.read_events(engagement)) == lines


def test_an_action_with_no_seq_skips_the_check(engagement):
    """A caller with no view - a script, every other call in this file - has
    nothing to be stale against and is not checked."""
    from tracker.filer import assign_review_file, dismiss_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    dismiss_review_file(engagement, parked.pbc_location, today=DAY2)   # the row moves on

    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)

    assert result.entry.decision == FILED


def honoured_by_the_scan(engagement, identifier):
    """One scan, and what it said about the request a person filed into.

    Asked through the pass itself rather than the helper behind it: what the
    scan writes about the row is where a person's filing is honoured or not,
    and the copy here answers none of the row's content rules, so Received
    with the accepted note is the person's decision and nothing else.
    """
    from tracker.manifest import Status
    from tracker.scanner import ACCEPTED_NOTE, scan_engagement

    said = scan_engagement(engagement, today=DAY2).updates[identifier]
    assert said.status == Status.RECEIVED, said
    assert ACCEPTED_NOTE.format(n=1) in said.validation_notes, said


def test_a_pick_off_a_non_empty_shortlist_is_recorded_as_an_override_and_a_pick_on_it_is_not(
        engagement):
    """Decision 84 lets a person file to any row; the record now says when
    they did so against the evidence, and the scanner still honours it."""
    from tracker.filer import (
        ASSIGNED_BY_PERSON,
        OVERRODE_SHORTLIST,
        assign_review_file,
        unfile_document,
    )

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    off = assign_review_file(engagement, parked.pbc_location, "C01",
                             today=DAY2, shortlist=["A01"])

    assert off.overrode_shortlist == OVERRODE_SHORTLIST.format(listed="A01")
    assert off.overrode_shortlist in off.entry.reason
    # The acceptance keys on the reason's prefix and the override clause
    # sits after it, so the pass still takes the copy as a person's filing.
    assert off.entry.reason.startswith(ASSIGNED_BY_PERSON)
    honoured_by_the_scan(engagement, "C01")

    unfile_document(engagement, parked.pbc_location, today=DAY2)
    on = assign_review_file(engagement, parked.pbc_location, "C01",
                            today=DAY2, shortlist=["C01", "A01"])

    # Only this decision's own clause: what the row said before is kept
    # after "was: ", and the override it carried is part of that history.
    assert on.overrode_shortlist == ""
    assert OVERRODE_SHORTLIST.split("(")[0] not in on.entry.reason.split("; was: ")[0]
    honoured_by_the_scan(engagement, "C01")


def test_an_empty_shortlist_is_never_an_override(engagement):
    """Decision 83's "no need prior": with nothing suggested there is nothing
    to overrule, so a filing off nothing says nothing."""
    from tracker.filer import OVERRODE_SHORTLIST, assign_review_file, unfile_document

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    the_clause = OVERRODE_SHORTLIST.split("(")[0]

    for shortlist in ([], None):
        result = assign_review_file(engagement, parked.pbc_location, "C01",
                                    today=DAY2, shortlist=shortlist)
        assert result.overrode_shortlist == ""
        assert the_clause not in result.entry.reason.split("; was: ")[0]
        unfile_document(engagement, parked.pbc_location, today=DAY2)


def test_a_refused_action_leaves_the_file_count_and_every_byte_unchanged(engagement):
    """The first standing rule of a refusal, over all three: nothing moved,
    nothing overwritten, nothing recorded."""
    from tracker.filer import (
        StaleRowError,
        assign_review_file,
        dismiss_review_file,
        unfile_document,
    )

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "notice.pdf", "nothing the rules recognise either")
    review = {e.original_name: e for e in sort(engagement, today=DAY1).review}
    parked, other = review["scan0012.pdf"], review["notice.pdf"]

    stale_parked = seq_of(engagement, parked)
    dismiss_review_file(engagement, parked.pbc_location, today=DAY2)   # parked still, seq moved
    filed = assign_review_file(engagement, other.pbc_location, "C01", today=DAY2).entry
    stale_filed = seq_of(engagement, filed)
    unfile_document(engagement, other.pbc_location, today=DAY2)
    assign_review_file(engagement, other.pbc_location, "C01", today=DAY2)

    files = every_byte(engagement)
    lines = len(ledger.read_events(engagement))

    for refuse in ("assign", "dismiss", "unfile"):
        with pytest.raises(StaleRowError):
            if refuse == "assign":
                assign_review_file(engagement, parked.pbc_location, "A01",
                                   today=DAY2, seq=stale_parked)
            elif refuse == "dismiss":
                dismiss_review_file(engagement, parked.pbc_location,
                                    today=DAY2, seq=stale_parked)
            else:
                unfile_document(engagement, other.pbc_location, today=DAY2, seq=stale_filed)
        assert every_byte(engagement) == files, refuse
        assert len(ledger.read_events(engagement)) == lines, refuse

# --------------------------- every working copy is proved (decision 109) ----


def _everything(engagement):
    """Every file this return and its household's client side hold, in one
    list: the return folder, the household's inbox and the year's folder of
    originals. Since decision 125 an original lives in the other tree, so a
    conservation check over the return folder alone would not see one."""
    roots = (engagement, inbox_of(engagement), originals_of(engagement))
    return sorted(path for root in roots for path in root.rglob("*")
                  if path.is_file() and path.name != ledger.LEDGER_FILENAME)


def files_under(engagement):
    """Every file the return and its client side hold, with its bytes and
    its mtime.

    The record aside, which a pass is meant to write. Every claim below that
    moves a file by hand takes this before the pass and after it: the sweep
    identifies by fingerprint and a person decides, so nothing under the
    client's root may move, change or appear because of what it found.
    """
    return {
        location_of(engagement, path): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in _everything(engagement)
    }


def events_named(engagement, name):
    """Every journal line of one event name."""
    return [e for e in ledger.read_events(engagement) if e[ledger.EVENT_KEY] == name]


def drag(path, folder):
    """A person dragging one file in Explorer, and where it lands."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / path.name
    path.rename(target)
    return target


def counting_hashes(monkeypatch) -> list[str]:
    """Every path anything in the package hashes, as it is hashed.

    Three modules hold the name now, and each holds its own: the memo's is
    the content check's, and a pass that reached around it would show up
    here and nowhere else. The scanner held a fourth until decision 109
    and holds none.
    """
    import tracker.content_check as content_check_module
    import tracker.filer as filer_module
    import tracker.validators as validators_module

    read: list[str] = []
    for module in (filer_module, content_check_module, validators_module):
        real = module.sha256_of

        def counted(path, _real=real):
            read.append(str(path))
            return _real(path)

        monkeypatch.setattr(module, "sha256_of", counted)
    return read


def test_a_filed_copy_dragged_into_another_requests_folder_is_file_moved_and_nothing_moves(engagement):
    from tracker.filer import FILE_MOVED, MOVED_SENTENCE, moved_to

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
    from tracker.filer import FILE_MOVED, moved_to

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
    from tracker.filer import FILE_MOVED, moved_to
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
    from tracker.filer import FILE_MOVED, UNRECORDED_COPY, moved_to

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
    from tracker.filer import FILE_MOVED, MOVED_BACK_SENTENCE, moved_to

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
    from tracker.filer import FILE_MOVED, MOVED_GONE_SENTENCE, REMADE_SENTENCE, moved_to

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
    from tracker.filer import FILE_MOVED, moved_to

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


def test_a_second_and_a_third_pass_over_an_unchanged_tree_hash_only_the_pbc_originals(
        engagement, monkeypatch):
    """Step 0's measure. Every hash of a file in the firm's folder goes
    through the store's memo, so a warm pass reads one file per preserved
    original - decision 68's per-pass reading of the client's own folder,
    accepted unchanged - and no working copy at all."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.filer import assign_review_file
    from tracker.scanner import scan_engagement

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "notice.pdf", "an agency notice nothing asks for")
    drop(engagement, "scan0003.pdf", "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    first = sort(engagement, today=DAY1)
    assert len(first.filed) == 2 and len(first.review) == 2
    assert any(e.also_filed for e in first.filed)            # the decision-94 split
    parked = next(e for e in first.review if e.original_name == "scan0012.pdf")
    assign_review_file(engagement, parked.pbc_location, "C01", today=DAY1)
    scan_engagement(engagement, today=DAY1)                  # the warm pass
    arrivals = sorted(p.name for p in originals(engagement).iterdir())
    assert len(arrivals) == 4

    read = counting_hashes(monkeypatch)
    for day in (DAY2, DAY2 + dt.timedelta(days=1)):          # the second pass, and the third
        read.clear()
        sort(engagement, today=day)
        scan_engagement(engagement, today=day)
        assert sorted(Path(path).name for path in read) == arrivals, read
        assert not any(PREPARED_DIR_NAME in path for path in read), read


def test_a_dehydrated_home_is_not_read_and_not_called_absent(engagement, monkeypatch):
    """Hashing a placeholder downloads it. A home the sync client has let go
    of is not looked at this pass, which is not the same as being gone."""
    import tracker.filer as filer_module

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    home = engagement / filed.prepared_location
    lines = len(ledger.read_events(engagement))

    monkeypatch.setattr(filer_module, "is_cloud_placeholder", lambda p: p == home)
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
    from tracker.filer import FILE_MOVED, moved_to

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
    import tracker.filer as filer_module
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

    monkeypatch.setattr(filer_module, "sha256_of", unreadable)
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


def test_the_moved_sentence_is_read_back_from_any_path():
    """The pattern is derived from the template that wrote the sentence, so a
    client's own file name - spaces, brackets, the (2) a collision makes, a
    semicolon, a name that is not ASCII at all - comes back exactly as it
    went in, and the base the next sentence is appended to is the reason as
    it stood."""
    from tracker.filer import (
        FILE_MOVED,
        MOVED_GONE_SENTENCE,
        MOVED_SENTENCE,
        _without_moved_sentence,
        moved_to,
    )
    from tracker.records import IndexEntry

    base = "the file's own words matched A01; assigned by a person on 2026-07-01"
    home = f"{PREPARED_DIR_NAME}/A01 - W-2 Wage Statements/A01 - W-2 Wage Statements - TY2025.pdf"
    row = IndexEntry(
        received=DAY1.isoformat(), original_name="w2.pdf", size_kb=1.0, digest="a" * 64,
        identifier="A01", prepared_location=home,
        # A location across the two trees, as every row holds one since
        # decision 125: nothing here reads it, and it is written the way
        # the record writes it.
        pbc_location="../../../../Clients/Smith Family/2025/w2.pdf",
        decision=FILE_MOVED, reason=base,
    )
    for now in (
        f"{PREPARED_DIR_NAME}/C01 - Mortgage Interest/w2 (2).pdf",
        f"{PREPARED_DIR_NAME}/C01 - Mortgage Interest/impots; recus (2026) été.pdf",
        f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/scan 0012 - copy.pdf",
    ):
        sentence = MOVED_SENTENCE.format(home=home, now=now, date=DAY2.isoformat())
        moved = replace(row, reason=f"{base}; {sentence}")
        assert moved_to(moved) == now
        assert _without_moved_sentence(moved.reason) == base
        # The same row once the bytes are nowhere: no path to read back.
        gone = replace(row, reason="{}; {}".format(base, MOVED_GONE_SENTENCE.format(
            home=home, prepared=PREPARED_DIR_NAME, pbc=row.pbc_location,
            date=DAY2.isoformat())))
        assert moved_to(gone) is None
        assert _without_moved_sentence(gone.reason) == base
        # And a row that is not File Moved says nothing about where it is.
        assert moved_to(replace(moved, decision=FILED)) is None
    assert _without_moved_sentence(base) == base             # any other reason is left alone


def test_a_split_rows_second_copy_dragged_away_is_said_on_the_request_that_lost_it(engagement):
    """Decision 94 gives one row a working copy in each request that asked for
    a form the page names, so a row can lose one copy and keep another. The
    row is File Moved once, the note goes to the request whose folder is
    empty now, and the request that still holds its own copy says nothing
    about it and goes on counting it."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker import reasons
    from tracker.filer import FILE_MOVED, moved_to
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


# ------------------------------ recovery is the person's (decision 110) ----


def a_moved_filed_row(engagement, folder="C01"):
    """A Filed document whose working copy somebody dragged, as the sweep
    leaves it: the row it made, and the file where the hand put it."""
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    wanderer = drag(engagement / filed.prepared_location, prepared(engagement, folder))
    sort(engagement, today=DAY2)
    return filed, wanderer


def test_put_it_back_moves_the_wanderer_home_and_the_row_is_filed_again(engagement):
    """The first answer, and the one that needs nowhere else for the file to
    go: the bytes return to where the record put them, the row is Filed
    again, and the next pass has nothing left to say about it."""
    from tracker.filer import FILED, PUT_BACK, restore_working_copy

    filed, wanderer = a_moved_filed_row(engagement)
    home = engagement / filed.prepared_location
    bytes_before = wanderer.read_bytes()
    lines = len(ledger.read_events(engagement))

    result = restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert result.moved_home and not result.copied_from_original
    assert not result.already_home and result.parked_as == ""
    assert home.read_bytes() == bytes_before and not wanderer.exists()
    [row] = read_index(engagement)
    assert row.decision == FILED and row.prepared_location == filed.prepared_location
    assert row.reason.endswith(PUT_BACK.format(
        home=filed.prepared_location, date=DAY2.isoformat(),
        now=location_of(engagement, wanderer)))
    assert row.reason.startswith(filed.reason)          # and its history is kept
    assert len(events_named(engagement, ledger.RESTORED_BY_PERSON)) == 1
    # One decision of the person's, and the re-scan that puts the request's
    # status back in the same breath. Nothing else was written.
    assert [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)[lines:]] == [
        ledger.MOVING, ledger.RESTORED_BY_PERSON, ledger.SCANNED
    ]
    assert result.entry == row
    # The request has its file again, and the pass that follows says nothing
    # about it: the copy is where the record put it, so it simply proves.
    lines = len(ledger.read_events(engagement))
    quiet = sort(engagement, today=DAY2 + dt.timedelta(days=1))
    assert quiet.attention == []
    assert len(ledger.read_events(engagement)) == lines


def test_put_it_back_on_a_parked_copy_dragged_into_a_request_folder_returns_it_to_review_as_needs_review(
        engagement):
    """A parked copy that wandered comes back parked. Which of the two parked
    decisions it was is not guessable (109's rule), so it waits for review
    and a person re-decides in one click."""
    from tracker.filer import restore_working_copy

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    wanderer = drag(engagement / parked.prepared_location, prepared(engagement, "C01"))
    sort(engagement, today=DAY2)

    result = restore_working_copy(engagement, parked.pbc_location, today=DAY2)

    assert result.moved_home
    assert (engagement / parked.prepared_location).is_file() and not wanderer.exists()
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == ""
    assert row.prepared_location == parked.prepared_location


def test_put_it_back_copies_from_the_original_when_nothing_under_prepared_holds_the_bytes(
        engagement):
    """A working copy is a copy of the original and the original is safe in
    the client's own folder (rule 2), so a row whose bytes are nowhere under
    the firm's folder is still restorable."""
    from tracker.filer import FILED, PUT_BACK_FROM_ORIGINAL, restore_working_copy

    filed, wanderer = a_moved_filed_row(engagement)
    wanderer.unlink()                                   # and now it is nowhere
    sort(engagement, today=DAY2)
    original = (originals(engagement) / "w2.pdf").read_bytes()

    result = restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert result.copied_from_original and not result.moved_home
    home = engagement / filed.prepared_location
    assert home.read_bytes() == original
    assert (originals(engagement) / "w2.pdf").read_bytes() == original    # untouched, as ever
    [row] = read_index(engagement)
    assert row.decision == FILED
    assert row.reason.endswith(PUT_BACK_FROM_ORIGINAL.format(
        home=filed.prepared_location, date=DAY2.isoformat(),
        pbc=filed.pbc_location, prepared=PREPARED_DIR_NAME))


def test_put_it_back_with_the_same_bytes_already_home_restores_the_row_and_leaves_the_wanderer_for_a_person(
        engagement):
    """The machine deletes nothing. Home holds these bytes, so there is
    nothing to move; the copy somebody left behind stays where it is and the
    sweep goes on naming it until a person removes it."""
    from tracker.filer import FILED, PUT_BACK_ALREADY, UNRECORDED_COPY, restore_working_copy

    filed, wanderer = a_moved_filed_row(engagement)
    home = engagement / filed.prepared_location
    home.write_bytes(wanderer.read_bytes())             # put back by hand, the copy left over
    untouched = files_under(engagement)

    result = restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert result.already_home and not result.moved_home and not result.copied_from_original
    assert files_under(engagement) == untouched         # nothing moved, nothing deleted
    [row] = read_index(engagement)
    assert row.decision == FILED
    assert row.reason.endswith(PUT_BACK_ALREADY.format(
        home=filed.prepared_location, date=DAY2.isoformat(),
        now=location_of(engagement, wanderer)))
    assert len(events_named(engagement, ledger.RESTORED_BY_PERSON)) == 1

    report = sort(engagement, today=DAY2 + dt.timedelta(days=1))
    assert [e.error for e in report.attention] == [
        UNRECORDED_COPY.format(location=location_of(engagement, wanderer))
    ]


@pytest.mark.parametrize("held_by", ("the wanderer", "nowhere"))
def test_put_it_back_never_overwrites_a_different_file_at_home_and_parks_this_documents_copy(
        engagement, held_by):
    """The owner's rule, 2026-09-19: nothing is overwritten. The file at home
    is somebody's, whatever the record says about it, so it stays exactly
    as it is; this document's copy goes to review under the client's own
    name and the row parks naming both, and both files are on disk.

    Runs on Windows and on Linux alike, because the refusal is the byte
    check this makes before ``os.rename`` and never the rename's own: on
    Linux a rename overwrites silently and there would be nothing to see.
    """
    from tracker.filer import PUT_BACK_REFUSED, restore_working_copy

    filed, wanderer = a_moved_filed_row(engagement)
    if held_by == "nowhere":
        wanderer.unlink()
        sort(engagement, today=DAY2)
    home = engagement / filed.prepared_location
    somebody_elses = b"%PDF-1.4 a different document entirely\n"
    home.write_bytes(somebody_elses)
    before = home.stat().st_mtime_ns

    result = restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    # The file at home is byte for byte, mtime and all, what it was.
    assert home.read_bytes() == somebody_elses and home.stat().st_mtime_ns == before
    parked = engagement / result.parked_as
    assert parked.parent == review_dir(engagement)
    assert parked.read_bytes() == (originals(engagement) / "w2.pdf").read_bytes()
    assert parked.name == "w2.pdf"                      # the client's own name
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == "" and row.also_filed == ""
    assert row.prepared_location == result.parked_as
    assert row.reason.endswith(PUT_BACK_REFUSED.format(
        date=DAY2.isoformat(), home=filed.prepared_location, parked=result.parked_as))
    assert len(events_named(engagement, ledger.RESTORED_BY_PERSON)) == 1


def test_put_it_back_refuses_a_row_that_is_not_moved_by_name(engagement):
    from tracker.filer import FilingError, restore_working_copy

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    files = every_byte(engagement)

    with pytest.raises(FilingError) as raised:
        restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert "is not a moved copy" in str(raised.value) and FILED in str(raised.value)
    assert every_byte(engagement) == files


def moved_again(engagement, wanderer, day):
    """The copy dragged a second time, and the pass that rewrites the row:
    still File Moved, still this person's row to act on - and no longer the
    row they were looking at."""
    moved = drag(wanderer, review_dir(engagement))
    sort(engagement, today=day)
    return moved


def test_put_it_back_refuses_a_stale_seq_and_touches_nothing(engagement):
    """Still moved, so the by-name refusal says nothing about it; the row's
    own sequence number has moved, and that is what catches it."""
    from tracker.filer import FILE_MOVED, StaleRowError, restore_working_copy

    filed, wanderer = a_moved_filed_row(engagement)
    [row] = read_index(engagement)
    as_the_person_saw_it = seq_of(engagement, row)
    moved_again(engagement, wanderer, DAY2 + dt.timedelta(days=1))
    [now_row] = read_index(engagement)
    assert now_row.decision == FILE_MOVED
    assert seq_of(engagement, now_row) != as_the_person_saw_it
    files = every_byte(engagement)
    lines = len(ledger.read_events(engagement))

    with pytest.raises(StaleRowError) as raised:
        restore_working_copy(engagement, filed.pbc_location, today=DAY2,
                             seq=as_the_person_saw_it)

    assert filed.original_name in str(raised.value)
    assert every_byte(engagement) == files
    assert len(ledger.read_events(engagement)) == lines


def test_put_it_back_refuses_a_row_without_a_digest(engagement, monkeypatch):
    """Decision 65: a row recorded without its bytes is tied to nothing, so
    nothing can be proved to be its working copy and nothing here may move."""
    import tracker.filer as filer_module
    from tracker.filer import FILE_MOVED, FilingError, restore_working_copy

    filed, wanderer = a_moved_filed_row(engagement)
    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED
    monkeypatch.setattr(filer_module, "read_index",
                        lambda *a, **k: [replace(row, digest="")])
    files = every_byte(engagement)

    with pytest.raises(FilingError) as raised:
        restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert "without its bytes" in str(raised.value)
    assert every_byte(engagement) == files


def test_put_it_back_refuses_when_neither_the_wanderer_nor_the_original_holds_the_bytes_and_names_which(
        engagement):
    from tracker.filer import FilingError, restore_working_copy

    filed, wanderer = a_moved_filed_row(engagement)
    wanderer.write_bytes(b"%PDF-1.4 somebody re-saved it\n")
    (originals(engagement) / "w2.pdf").write_bytes(b"%PDF-1.4 and the client replaced this\n")
    files = every_byte(engagement)

    with pytest.raises(FilingError) as raised:
        restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    said = str(raised.value)
    assert location_of(engagement, wanderer) in said and filed.pbc_location in said
    assert every_byte(engagement) == files


def test_a_refused_record_rolls_the_put_back_move_back(engagement, monkeypatch):
    """The record took the decision or it did not - one transaction, no third
    state - so the file goes back where the record says it is."""
    import tracker.store as store_module
    from tracker.filer import FILE_MOVED, restore_working_copy

    filed, wanderer = a_moved_filed_row(engagement)
    files = every_byte(engagement)
    lines = len(ledger.read_events(engagement))

    def refuse(*a, **k):
        raise RuntimeError("the record said no")

    monkeypatch.setattr(store_module, "record", refuse)
    with pytest.raises(RuntimeError):
        restore_working_copy(engagement, filed.pbc_location, today=DAY2)
    monkeypatch.undo()

    assert every_byte(engagement) == files              # the wanderer is where it was
    assert len(ledger.read_events(engagement)) == lines
    assert events_named(engagement, ledger.RESTORED_BY_PERSON) == []
    assert read_index(engagement)[0].decision == FILE_MOVED


def test_keep_it_here_files_the_wanderer_under_the_request_whose_folder_holds_it_as_the_persons(
        engagement):
    """The second answer: the copy is where somebody meant it to be, so it
    takes the canonical name there and the row is Filed by a person."""
    from tracker.filer import ASSIGNED_BY_PERSON, FILED, assign_review_file
    from tracker.manifest import load_manifest

    filed, wanderer = a_moved_filed_row(engagement)

    result = assign_review_file(engagement, filed.pbc_location, "C01",
                                keyword="escrow", today=DAY2)

    assert result.moved_review_copy and not wanderer.exists()
    kept = engagement / result.entry.prepared_location
    assert kept.parent == engagement / PREPARED_DIR_NAME          # beside the others (decision 168)
    assert kept.name.startswith("C01 - ")
    [row] = read_index(engagement)
    assert row.decision == FILED and row.identifier == "C01"
    assert row.reason.startswith(ASSIGNED_BY_PERSON)
    assert len(events_named(engagement, ledger.ASSIGNED_BY_PERSON)) == 1
    c01 = {i.identifier: i for i in load_manifest(engagement)}["C01"]
    assert "escrow" in c01.any_keywords


def test_keep_it_here_may_pick_another_request_and_the_wanderer_moves_there(engagement):
    """The picker is the same picker: keeping the file and correcting the
    request it answers is one click."""
    from tracker.filer import FILED, assign_review_file

    filed, wanderer = a_moved_filed_row(engagement)

    result = assign_review_file(engagement, filed.pbc_location, "A01", today=DAY2)

    assert not wanderer.exists()
    kept = engagement / result.entry.prepared_location
    assert kept.parent == engagement / PREPARED_DIR_NAME and kept.name.startswith("A01 - ")
    [row] = read_index(engagement)
    assert row.decision == FILED and row.identifier == "A01"


@pytest.mark.parametrize("where", ("the wanderer", "nowhere"))
def test_send_to_review_parks_the_wanderer_under_the_clients_name_as_the_persons(
        engagement, where):
    """The third answer: the copy goes back to the review folder under the
    client's own name, and a row whose bytes are nowhere is copied from the
    original, exactly as an unfiling already does."""
    from tracker.filer import UNFILED_BY_PERSON, unfile_document

    filed, wanderer = a_moved_filed_row(engagement)
    if where == "nowhere":
        wanderer.unlink()
        sort(engagement, today=DAY2)

    result = unfile_document(engagement, filed.pbc_location, today=DAY2)

    assert result.moved_working_copy is (where == "the wanderer")
    parked = engagement / result.entry.prepared_location
    assert parked.parent == review_dir(engagement) and parked.name == "w2.pdf"
    assert parked.read_bytes() == (originals(engagement) / "w2.pdf").read_bytes()
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == ""
    assert row.reason.startswith(UNFILED_BY_PERSON)
    assert len(events_named(engagement, ledger.UNFILED_BY_PERSON)) == 1


def a_moved_split_row(engagement):
    """A page decision 94 filed under two requests, one copy dragged away and
    the other deleted: the row the sweep leaves, and the wanderer."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines

    drop(engagement, "scan0003.pdf",
         "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    [split] = sort(engagement, today=DAY1).filed
    assert len(split.filed_locations) == 2
    wanderer = drag(engagement / split.filed_locations[0], review_dir(engagement))
    (engagement / split.filed_locations[1]).unlink()
    sort(engagement, today=DAY2)
    return split, wanderer


@pytest.mark.parametrize("action", ("keep", "send to review"))
def test_keep_and_send_to_review_refuse_a_row_with_copies_under_several_requests_by_name(
        engagement, action):
    """Which of a page's copies the person means is not the machine's to
    guess, and put-it-back answers for every one of them."""
    from tracker.filer import (
        SEVERAL_COPIES_REFUSAL,
        FilingError,
        assign_review_file,
        unfile_document,
    )

    split, wanderer = a_moved_split_row(engagement)
    files = every_byte(engagement)

    with pytest.raises(FilingError) as raised:
        if action == "keep":
            assign_review_file(engagement, split.pbc_location, "A01", today=DAY2)
        else:
            unfile_document(engagement, split.pbc_location, today=DAY2)

    assert str(raised.value) == SEVERAL_COPIES_REFUSAL.format(name=split.original_name)
    assert every_byte(engagement) == files


def test_put_it_back_restores_every_copy_of_such_a_row(engagement):
    """One row, one original, one list of copies: put-it-back fills every one
    of them - the wanderer moved into the first, the rest remade from it -
    and the next pass has nothing left to say."""
    from tracker.filer import FILED, restore_working_copy

    split, wanderer = a_moved_split_row(engagement)
    bytes_wanted = wanderer.read_bytes()

    result = restore_working_copy(engagement, split.pbc_location, today=DAY2)

    assert result.moved_home and not wanderer.exists()
    [row] = read_index(engagement)
    assert row.decision == FILED and row.filed_locations == split.filed_locations
    for location in row.filed_locations:
        assert (engagement / location).read_bytes() == bytes_wanted
    report = sort(engagement, today=DAY2 + dt.timedelta(days=1))
    assert report.attention == []                       # every copy proves


@pytest.mark.parametrize("refusal", ("not moved", "stale", "no bytes anywhere", "several copies"))
def test_every_recovery_refusal_leaves_the_file_count_unchanged(engagement, refusal):
    """Standing rule: a refused action moves nothing and overwrites nothing."""
    from tracker.filer import FilingError, restore_working_copy, unfile_document

    entry, wanderer = (a_moved_split_row(engagement) if refusal == "several copies"
                       else a_moved_filed_row(engagement))
    stale = seq_of(engagement, read_index(engagement)[0])
    if refusal == "not moved":
        restore_working_copy(engagement, entry.pbc_location, today=DAY2)   # no longer moved
    elif refusal == "stale":
        moved_again(engagement, wanderer, DAY2 + dt.timedelta(days=1))
    elif refusal == "no bytes anywhere":
        wanderer.write_bytes(b"%PDF-1.4 re-saved\n")
        (originals(engagement) / "w2.pdf").write_bytes(b"%PDF-1.4 replaced\n")

    files = files_under(engagement)
    lines = len(ledger.read_events(engagement))
    with pytest.raises(FilingError):
        if refusal == "several copies":
            unfile_document(engagement, entry.pbc_location, today=DAY2)
        elif refusal == "stale":
            restore_working_copy(engagement, entry.pbc_location, today=DAY2, seq=stale)
        else:
            restore_working_copy(engagement, entry.pbc_location, today=DAY2)

    assert files_under(engagement) == files
    assert len(ledger.read_events(engagement)) == lines


def test_dismiss_still_refuses_a_moved_row_by_name(engagement):
    """Decision 76 unchanged: setting a request aside says nothing about a
    file nobody can find, so a moved row is not dismissable."""
    from tracker.filer import FILE_MOVED, FilingError, dismiss_review_file

    filed, wanderer = a_moved_filed_row(engagement)
    files = every_byte(engagement)

    with pytest.raises(FilingError) as raised:
        dismiss_review_file(engagement, filed.pbc_location, today=DAY2)

    assert "is not waiting for review" in str(raised.value)
    assert FILE_MOVED in str(raised.value)
    assert every_byte(engagement) == files

# ---------------- an interrupted move is finished from the record (119) ----


def digests_under(engagement):
    """Every file the return and its client side hold, by location, with
    its bytes' digest.

    The record aside, which a pass is meant to write. What the three
    conservation checks below are made of.
    """
    from tracker.validators import sha256_of

    return {location_of(engagement, path): sha256_of(path)
            for path in _everything(engagement)}


def conserved(engagement, before, moves, *, added=(), gone=()):
    """The three conservation checks every crash claim below ends with.

    (a) every document that was under the engagement is still under it,
    with exactly the copies the decision meant to make added and the
    stand-downs it recorded gone; (b) nothing that was already there had
    its bytes changed - a recovery never overwrites and never deletes what
    it finds; (c) no intended move was made twice, across the crash and
    the recovery together. And the store agrees with the record with no
    move left open, which is the fixture's question asked here too, where
    its answer is about a folder a run died in the middle of.
    """
    from collections import Counter

    after = digests_under(engagement)
    for path, digest in before.items():
        assert after.get(path, digest) == digest, f"{path}: the bytes changed"
    assert Counter(after.values()) == Counter(before.values()) + Counter(added) - Counter(gone)
    assert len(moves) == len(set(moves)), moves
    assert store.check(store.connect(), engagement.parent, engagement) == []
    assert open_intents(engagement) == []


def open_intents(engagement):
    """The moves this engagement has begun and not finished."""
    return store.open_intents(store.connect(), engagement)


def moves_made(monkeypatch) -> list[tuple[str, str]]:
    """Every rename the filer makes, as it makes it: the check that a move
    the crash made is not made again by the recovery."""
    import tracker.filer as filer_module

    real = filer_module._move_whole
    made: list[tuple[str, str]] = []

    def counted(source, target, *, within):
        made.append((str(source), str(target)))
        return real(source, target, within=within)

    monkeypatch.setattr(filer_module, "_move_whole", counted)
    return made


def killed_after_ops(monkeypatch, after=1):
    """The machine dies once ``after`` file operations of one decision have
    been made and before the row that explains them is recorded.

    The only faithful place to inject it: a rollback cannot run on a power
    cut, so the kill goes where no ``except`` of the caller's can catch it,
    between the work and the record. Once only, so the pass that recovers
    runs for real.
    """
    import tracker.filer as filer_module

    real = filer_module._do_op
    state = {"made": 0, "died": False}

    def dying(engagement_dir, op, *, cache=None):
        real(engagement_dir, op, cache=cache)
        state["made"] += 1
        if not state["died"] and state["made"] >= after:
            state["died"] = True
            raise KeyboardInterrupt

    monkeypatch.setattr(filer_module, "_do_op", dying)
    return state


def killed_after_the_move(monkeypatch):
    """The machine dies once the drop has been moved out of the inbox and
    before anything else: the one move no intent covers since decision 125."""
    import tracker.filer as filer_module

    real = filer_module._move_whole
    state = {"died": False}

    def dying(source, target, *, within):
        real(source, target, within=within)
        if not state["died"]:
            state["died"] = True
            raise KeyboardInterrupt

    monkeypatch.setattr(filer_module, "_move_whole", dying)
    return state


def killed_at_the_intent(monkeypatch, kind=None):
    """The machine dies with an intent on the record and not one step of
    what it stands for done. ``kind`` picks which intent."""
    real = store.record
    state = {"died": False}

    def killing(conn, engagement_dir, *events):
        result = real(conn, engagement_dir, *events)
        this_one = events[0][ledger.EVENT_KEY] == ledger.MOVING and (
            kind is None
            or any(op[ledger.OP_KEY] == kind for op in events[0][ledger.OPS_KEY]))
        if this_one and not state["died"]:
            state["died"] = True
            raise KeyboardInterrupt
        return result

    monkeypatch.setattr(store, "record", killing)
    return state


def killed_at_the_record(monkeypatch):
    """The machine dies as the rows of a decision are recorded: the files
    have moved, the intent is open, the index says nothing yet."""
    real = store.record
    state = {"died": False}

    def killing(conn, engagement_dir, *events):
        if events[0][ledger.EVENT_KEY] != ledger.MOVING and not state["died"]:
            state["died"] = True
            raise KeyboardInterrupt
        return real(conn, engagement_dir, *events)

    monkeypatch.setattr(store, "record", killing)
    return state


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
from tests.conftest import sort
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


def test_a_copy_of_a_read_only_original_is_writable_and_the_original_stays_read_only(engagement):
    """Decision 155, F-2. ``copy2`` carried a read-only original's attribute
    onto its working copy - a file from a CD, one Explorer took out of a
    zip - and removing that copy later ("Access is denied") jammed the
    household every pass. The copy is the firm's and is writable; the
    original is only read, and stays exactly as the client sent it."""
    import stat as stat_module

    from tracker.filer import unfile_document

    original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    os.chmod(original, stat_module.S_IREAD)
    try:
        [filed] = sort(engagement, today=DAY1).filed
        kept = originals(engagement) / "w2.pdf"
        copy = engagement / filed.prepared_location
        assert not os.stat(kept).st_mode & stat_module.S_IWRITE     # the original: untouched
        assert os.stat(copy).st_mode & stat_module.S_IWRITE         # the copy: writable
        # And what jammed the household: a step that takes the copy away.
        unfile_document(engagement, filed.pbc_location, today=DAY2)
        assert not copy.exists()
        assert not os.stat(kept).st_mode & stat_module.S_IWRITE
    finally:
        for path in (originals(engagement) / "w2.pdf", original):
            if path.exists():
                os.chmod(path, stat_module.S_IREAD | stat_module.S_IWRITE)


def test_the_trackers_own_temp_files_are_swept_and_nothing_else(engagement):
    """Decision 155, A-F6. A killed write leaves its temp for ever - one in
    the client's own Drop folder, counted as "syncing" every pass. The
    household pass takes away the tracker's own temps and nothing else: the
    exact shape (``fsio.TEMP_NAME``), older than the pass, left by a
    process that is gone, and only in the return's folder, the household's
    ``_Opened``, or beside the README. A client's file is never touched,
    whatever it is called, and nothing in the year's folder, where the
    originals rest, is ever looked at."""
    import subprocess
    import time

    from tracker.filer import sweep_stranded_temps
    from tracker.layout import opened_dir_of

    pid = os.getpid()
    ours = [
        prepared(engagement, "A01") / f"A01 - W-2 Wage Statements - TY2025.pdf.{pid}.0a1b2c3d.tmp",
        review_dir(engagement) / f"scan.pdf.{pid}.1b2c3d4e.tmp",
        engagement / f"Status Report.html.{pid}.2c3d4e5f.tmp",
        opened_dir_of(engagement) / "statement" / f"page.pdf.{pid}.3d4e5f6a.tmp",
        inbox_of(engagement) / f"{README_NAME}.{pid}.4e5f6a7b.tmp",
    ]
    theirs = [
        inbox_of(engagement) / "W-2 scan.pdf.tmp",                          # a client's .tmp
        inbox_of(engagement) / f"photo.jpg.{pid}.5f6a7b8c.tmp",             # the shape, not the README's
        inbox_of(engagement) / f"{README_NAME.upper()}.{pid}.6a7b8c9d.tmp",  # not the README's name
        originals(engagement) / f"W2.pdf.{pid}.7b8c9d0e.tmp",               # the year's folder: never
        prepared(engagement, "A01") / "notes.tmp",                          # not the shape
        prepared(engagement, "A01") / f"x.pdf.{pid}.8C9D0E1F.tmp",          # not the shape (case)
        prepared(engagement, "A01") / f"x.pdf.{pid}.8c9d0e.tmp",            # not the shape (length)
    ]
    for path in [*ours, *theirs]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"half")
    # The README's own temp holds the README's text: in the client's inbox a
    # name is not enough to make a file ours (decision 190).
    from tracker.scaffold import README_FIRST_LINE
    ours[-1].write_bytes(README_FIRST_LINE.encode("ascii") + b"\r\nhalf")

    # A temp that came to be after the pass started, and one whose writer is
    # still running, are somebody's write in progress: left.
    started = time.time() - 60
    with subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"]) as live:
        try:
            alive = engagement / f"view.html.{live.pid}.9d0e1f2a.tmp"
            alive.write_bytes(b"being written")
            assert sweep_stranded_temps(household_of(engagement), [engagement],
                                        started=started) == []
            assert all(path.exists() for path in [*ours, *theirs, alive])
            taken = sweep_stranded_temps(household_of(engagement), [engagement],
                                         started=time.time() + 1)
            assert sorted(map(str, taken)) == sorted(map(str, ours))
            assert alive.exists()
        finally:
            live.kill()

    assert not any(path.exists() for path in ours)
    assert all(path.read_bytes() == b"half" for path in theirs)


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are Windows'")
def test_the_sweep_never_walks_through_a_junction(engagement, tmp_path):
    """Decision 155's review, FIX 1. A junction under a return's folder or
    under ``_Opened`` points anywhere - at a client's folder, at another
    household's - and a temp-shaped file behind it is not this household's
    to take. The walk asks the one link test the package has
    (``fsio.is_link``, read from the reparse tag), which every supported
    Python answers: ``DirEntry.is_junction()`` does not exist on 3.11."""
    import _winapi
    import time

    from tracker.filer import sweep_stranded_temps
    from tracker.fsio import is_link
    from tracker.layout import opened_dir_of

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    behind = elsewhere / f"statement.pdf.{os.getpid()}.0a1b2c3d.tmp"
    behind.write_bytes(b"somebody else's")
    opened_dir_of(engagement).mkdir(parents=True, exist_ok=True)
    links = [prepared(engagement, "A01") / "linked", opened_dir_of(engagement) / "linked"]
    for link in links:
        _winapi.CreateJunction(str(elsewhere), str(link))
    try:
        assert all(is_link(link) for link in links)
        taken = sweep_stranded_temps(household_of(engagement), [engagement],
                                     started=time.time() + 1)
        assert taken == [] and behind.read_bytes() == b"somebody else's"
    finally:
        for link in links:
            os.rmdir(link)


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
    import tracker.filer as filer_module

    monkeypatch.setattr(filer_module, "pid_alive", lambda pid: False)
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
    import tracker.filer as filer_module
    from tracker.scaffold import README_FIRST_LINE

    monkeypatch.setattr(filer_module, "pid_alive", lambda pid: False)
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
    import tracker.filer as filer_module
    from tracker import reasons
    from tracker.manifest import Status
    from tracker.scanner import scan_engagement

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    def power_loss(source, target, *, expect="", cache=None):
        Path(target).write_bytes(b"%PDF-1.4 half")   # nothing tidies up after a power cut
        raise KeyboardInterrupt

    monkeypatch.setattr(filer_module, "_copy_whole", power_loss)
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


def test_an_assign_killed_between_the_move_and_the_record_is_finished_as_the_persons_filing(
        engagement, monkeypatch):
    """A person filed it and the machine died with the copy moved. The next
    pass records the filing as theirs, dated the day they made it, with the
    keyword it taught in the same transaction."""
    from tracker.filer import ASSIGNED_BY_PERSON, assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_ops(monkeypatch, after=1)

    with pytest.raises(KeyboardInterrupt):
        assign_review_file(engagement, parked.pbc_location, "C01",
                           keyword="lender", today=DAY2)

    [waiting] = read_index(engagement)
    assert waiting.decision == NEEDS_REVIEW          # the record has not moved
    assert open_intents(engagement)
    calls = counted_records(monkeypatch)

    sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == FILED and row.identifier == "C01"
    assert row.reason.startswith(f"{ASSIGNED_BY_PERSON} on {DAY2.isoformat()}")
    assert calls == [(ledger.ASSIGNED_BY_PERSON, ledger.KEYWORD_LEARNED)]
    assert {i.identifier: i.any_keywords for i in load_manifest(engagement)}["C01"] == ("lender",)
    conserved(engagement, before, moves)


def test_recovery_runs_before_the_sweep_so_an_interrupted_action_is_never_called_a_hand_move(
        engagement, monkeypatch):
    """Decision 109's sweep would read a person's half-made filing as a copy
    somebody dragged, and 110 would ask them to put it back. The recovery
    runs first, so the sweep never sees it."""
    from tracker.filer import FILE_MOVED, assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_ops(monkeypatch, after=1)
    with pytest.raises(KeyboardInterrupt):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)

    report = sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == FILED and row.decision != FILE_MOVED
    assert events_named(engagement, ledger.COPY_MOVED) == []
    assert events_named(engagement, ledger.ASSIGNED_BY_PERSON)
    assert report.attention == []
    conserved(engagement, before, moves)


def test_an_unfile_killed_between_the_move_and_the_record_is_finished_and_no_second_parked_copy_is_made(
        engagement, monkeypatch):
    """The copy went back to review and the row was never rewritten. The
    next pass records the unfiling as the person's; nothing parks a second
    copy beside the one already there."""
    from tracker.filer import UNFILED_BY_PERSON, unfile_document

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_ops(monkeypatch, after=1)

    with pytest.raises(KeyboardInterrupt):
        unfile_document(engagement, filed.pbc_location, today=DAY2)

    assert read_index(engagement)[0].decision == FILED       # the record has not moved
    assert open_intents(engagement)

    sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == ""
    assert row.reason.startswith(f"{UNFILED_BY_PERSON} on {DAY2.isoformat()}")
    assert [p.name for p in review_dir(engagement).iterdir()] == ["w2.pdf"]
    assert not list(prepared(engagement, "A01").iterdir())
    conserved(engagement, before, moves)


def test_an_unfile_killed_between_two_stand_downs_finishes_the_removals_it_recorded(
        engagement, monkeypatch):
    """Decision 94's several copies: one goes back under the client's name
    and the rest stand down, being those same bytes again. A kill between
    them leaves a copy in a request folder the row no longer claims, and
    the next pass finishes the stand-down the record already carries."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.filer import unfile_document

    drop(engagement, "scan0003.pdf",
         "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    (filed,) = sort(engagement, today=DAY1).filed
    assert len(filed.filed_locations) == 2
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_ops(monkeypatch, after=1)           # the move home, not the stand-down

    with pytest.raises(KeyboardInterrupt):
        unfile_document(engagement, filed.pbc_location, today=DAY2)

    assert (engagement / filed.filed_locations[1]).is_file()      # not stood down yet

    sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.also_filed == ""
    assert not (engagement / filed.filed_locations[1]).exists()
    assert [p.name for p in review_dir(engagement).iterdir()] == ["scan0003.pdf"]
    conserved(engagement, before, moves,
              gone=[before[filed.filed_locations[1]]])


def test_a_restore_killed_between_the_move_and_the_record_is_finished(engagement, monkeypatch):
    """Decision 110's put-it-back, killed with the copy home and the row
    still saying it is not. The next pass records the person's answer."""
    from tracker.filer import PUT_BACK, restore_working_copy

    filed, wanderer = a_moved_filed_row(engagement)
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_ops(monkeypatch, after=1)

    with pytest.raises(KeyboardInterrupt):
        restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert (engagement / filed.prepared_location).is_file() and not wanderer.exists()
    assert open_intents(engagement)

    sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == FILED and row.prepared_location == filed.prepared_location
    assert row.reason.endswith(PUT_BACK.format(
        home=filed.prepared_location, date=DAY2.isoformat(),
        now=location_of(engagement, wanderer)))
    assert len(events_named(engagement, ledger.RESTORED_BY_PERSON)) == 1
    conserved(engagement, before, moves)


def test_a_destination_holding_other_bytes_is_never_touched_and_the_row_parks_naming_it(
        engagement, monkeypatch):
    """The contradiction: the step never happened and somebody else's file
    is where it was going. Nothing there is touched, the row parks naming
    it, and the copy waiting in review is used rather than doubled."""
    from tracker import reasons
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    killed_at_the_intent(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)

    stranger = engagement / PREPARED_DIR_NAME / "C01 - Mortgage Interest - TY2025.pdf"
    stranger.parent.mkdir(parents=True, exist_ok=True)
    stranger.write_bytes(b"%PDF-1.4 somebody elses file")
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)

    report = sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == ""
    assert row.code == reasons.INTERRUPTED_MOVE.code
    assert location_of(engagement, stranger) in row.reason
    assert stranger.read_bytes() == b"%PDF-1.4 somebody elses file"     # untouched
    assert row.prepared_location == parked.prepared_location            # the copy waiting is used
    assert [p.name for p in review_dir(engagement).iterdir()] == ["scan0012.pdf"]
    assert any(reasons.INTERRUPTED_MOVE.marker in e.error for e in report.attention)
    conserved(engagement, before, moves)


def test_bytes_gone_from_both_places_park_the_row_and_say_so(engagement, monkeypatch):
    """Neither end of the step holds those bytes now. Nothing is guessed:
    the row parks, the sentence says whether the client's own original is
    still there, and the copy a person acts on is made from it."""
    from tracker import reasons
    from tracker.filer import INTERRUPTED_ORIGINAL_HELD, unfile_document

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    killed_at_the_intent(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        unfile_document(engagement, filed.pbc_location, today=DAY2)

    (engagement / filed.prepared_location).unlink()       # and a person deletes the copy
    original = originals(engagement) / "w2.pdf"
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)

    report = sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW
    assert row.code == reasons.INTERRUPTED_MOVE_LOST.code
    assert INTERRUPTED_ORIGINAL_HELD in row.reason
    assert filed.prepared_location in row.reason
    assert (engagement / row.prepared_location).read_bytes() == original.read_bytes()
    assert any(reasons.INTERRUPTED_MOVE_LOST.marker in e.error for e in report.attention)
    conserved(engagement, before, moves,
              added=[digests_under(engagement)[row.prepared_location]])


def test_a_person_action_refuses_while_an_intent_is_open_and_the_next_pass_clears_it(
        engagement, monkeypatch):
    """One answer for all four actions instead of five recovery paths: the
    record is in the middle of a decision here, and a pass - which the app's
    Run now is - finishes it first."""
    from tracker.filer import (
        OPEN_INTENT_REFUSAL,
        FilingError,
        assign_review_file,
        dismiss_review_file,
        restore_working_copy,
        unfile_document,
    )

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    killed_after_ops(monkeypatch, after=1)
    with pytest.raises(KeyboardInterrupt):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    files = every_byte(engagement)

    for act in (lambda: assign_review_file(engagement, parked.pbc_location, "C01", today=DAY3),
                lambda: dismiss_review_file(engagement, parked.pbc_location, today=DAY3),
                lambda: unfile_document(engagement, parked.pbc_location, today=DAY3),
                lambda: restore_working_copy(engagement, parked.pbc_location, today=DAY3)):
        with pytest.raises(FilingError) as raised:
            act()
        assert str(raised.value) == OPEN_INTENT_REFUSAL
    assert every_byte(engagement) == files               # and none of them touched anything

    sort(engagement, today=DAY3)

    assert open_intents(engagement) == []
    # And the row is a person's to act on again.
    result = unfile_document(engagement, parked.pbc_location, today=DAY3)
    assert result.moved_working_copy is True


def test_a_refused_record_still_rolls_the_copy_back_and_leaves_no_intent_open(
        engagement, monkeypatch):
    """A refusal is not a crash. The files go back where the record says and
    the move is closed with ``move_abandoned``, so the next pass does not
    finish forward a move the record would not take - and where even that
    line cannot be written, the move stays open and the next pass finishes
    it forward as the record decided, recording the row the person made.
    """
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "notice.pdf", "an agency notice nothing asks for")
    parked = {e.original_name: e for e in sort(engagement, today=DAY1).review}
    real = store.record

    def the_rows_are_refused(conn, engagement_dir, *events):
        # The journal is writable; it is the decision's own record that is
        # refused - a store behind its journal, a line it will not fold.
        if events[0][ledger.EVENT_KEY] in (ledger.MOVING, ledger.MOVE_ABANDONED):
            return real(conn, engagement_dir, *events)
        raise store.StoreError("the store will not take this decision")

    monkeypatch.setattr(store, "record", the_rows_are_refused)
    with pytest.raises(store.StoreError):
        assign_review_file(engagement, parked["scan0012.pdf"].pbc_location, "C01", today=DAY2)
    monkeypatch.undo()

    assert (engagement / parked["scan0012.pdf"].prepared_location).is_file()   # put back
    assert open_intents(engagement) == []                                      # and closed
    assert [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)][-2:] == [
        ledger.MOVING, ledger.MOVE_ABANDONED]

    # And the other way: the abandonment itself cannot be written either.
    def nothing_is_recorded(conn, engagement_dir, *events):
        if events[0][ledger.EVENT_KEY] == ledger.MOVING:
            return real(conn, engagement_dir, *events)
        raise store.StoreError("the store will not take this decision")

    monkeypatch.setattr(store, "record", nothing_is_recorded)
    with pytest.raises(store.StoreError):
        assign_review_file(engagement, parked["notice.pdf"].pbc_location, "C01", today=DAY2)
    monkeypatch.undo()
    assert open_intents(engagement)

    sort(engagement, today=DAY3)

    rows = {e.original_name: e for e in read_index(engagement)}
    assert rows["notice.pdf"].decision == FILED and rows["notice.pdf"].identifier == "C01"
    assert open_intents(engagement) == []


#: Where a run is killed, for the conservation claim: every step of a
#: pass's own decision, and a person's.
CRASH_POINTS = ("after the move out of the inbox",
                "the intent before the copy", "after the copy",
                "the record of the rows", "after a person's move")


@pytest.mark.parametrize("point", CRASH_POINTS)
def test_the_conservation_helper_holds_across_every_injected_crash_point(
        engagement, monkeypatch, point):
    """Whichever step a run dies on, the engagement holds the same documents
    afterwards: nothing overwritten, nothing deleted, nothing moved twice,
    nothing copied twice, and the store saying what the record says."""
    from tracker.filer import assign_review_file

    if point == "after a person's move":
        drop(engagement, "scan0012.pdf", "nothing the rules recognise")
        parked = sort(engagement, today=DAY1).review[0]
        before = digests_under(engagement)
        added = []
        moves = moves_made(monkeypatch)
        killed_after_ops(monkeypatch, after=1)
        with pytest.raises(KeyboardInterrupt):
            assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    else:
        original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
        before = digests_under(engagement)
        added = [before[location_of(engagement, original)]]      # one working copy
        moves = moves_made(monkeypatch)
        if point == "after the move out of the inbox":
            killed_after_the_move(monkeypatch)
        elif point == "the intent before the copy":
            killed_at_the_intent(monkeypatch, ledger.OP_COPY)
        elif point == "after the copy":
            killed_after_ops(monkeypatch, after=1)
        else:
            killed_at_the_record(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            sort(engagement, today=DAY1)

    sort(engagement, today=DAY2)

    assert len(read_index(engagement)) == 1
    conserved(engagement, before, moves, added=added)


# ============ one inbox, several returns (decision 125) ====================
#
# A household with a business and its owner's 1040 has one folder to drop
# into, so the sort judges each drop against every return of the open year
# and files it where exactly one accepts it. These are the claims about
# that, and about what a person's actions and a killed run do once an
# original lives in the other tree.

BUSINESS = [
    RequestItem(
        identifier="B01", document="Trial Balance", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("trial balance",),
    ),
]


@pytest.fixture
def two_returns(tmp_path):
    """One household with two returns of the open year: a 1040 and an 1120S."""
    personal = make_engagement(tmp_path, ITEMS, household="Park Family",
                               return_name="1040 - John Park")
    business = make_engagement(tmp_path, BUSINESS, household="Park Family",
                               return_name="1120S - Park Landscaping")
    return personal, business


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


def test_the_originals_folder_is_shared_and_another_returns_original_is_never_a_stray(two_returns):
    """One folder of originals serves the household-year, so a file one
    return's row holds must never look like another return's stray."""
    from tracker.filer import unrecorded_in_pbc

    personal, business = two_returns
    drop(personal, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(personal, "tb.pdf", "Trial balance as of December 31 2025")
    sort_all(two_returns, today=DAY1)

    rows = [(one, read_index(one)) for one in two_returns]
    assert unrecorded_in_pbc(originals(personal), rows) == []
    # A second pass changes nothing: neither return sorts the other's.
    assert all(report.handled == 0 for report in sort_all(two_returns, today=DAY2).values())
    assert len(read_index(personal)) == 1 and len(read_index(business)) == 1


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


def test_a_persons_filing_unfiling_and_restore_still_work_with_originals_across_the_trees(engagement):
    """Decisions 110 and 112 through the API, one each, with the original
    in the tree the client can see."""
    import tracker.api as api_module
    from tracker.filer import FILE_MOVED, assign_review_file, restore_working_copy, unfile_document

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    assert parked.pbc_location.startswith("../")

    filed = assign_review_file(engagement, parked.pbc_location, "A01", today=DAY2).entry
    assert filed.decision == FILED and (engagement / filed.prepared_location).is_file()

    back = unfile_document(engagement, filed.pbc_location, today=DAY2).entry
    assert back.decision == NEEDS_REVIEW and (engagement / back.prepared_location).is_file()

    # And a copy somebody dragged: the sweep says where it is, and a person
    # puts it back - all of it keyed on an original in the other tree.
    again = assign_review_file(engagement, back.pbc_location, "A01", today=DAY2).entry
    home = engagement / again.prepared_location
    wandered = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME / "dragged.pdf"
    wandered.parent.mkdir(parents=True, exist_ok=True)
    home.rename(wandered)
    sort(engagement, today=DAY2)
    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED
    put_back = restore_working_copy(engagement, row.pbc_location, today=DAY2).entry
    assert put_back.decision == FILED and home.is_file()
    assert api_module._state(engagement)["moved"] == []


# ============ the name on the page (decision 128) ==========================
#
# Two 1040s share every row of their request lists, so the keywords cannot
# say whose W-2 this is. The name on the page can: every return carries the
# people it is for, and a request that asks for a named document files only
# where one of that return's spellings is on the page.

JOHN = Person("taxpayer", "John Park", propose_spellings("John Park", "taxpayer"))
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
    """Decision 50 through decision 128: OCR's reading routes on required
    keywords alone, and the name check reads the same words - so a scan
    OCR rescued files where its name confirms and nowhere else."""
    import tracker.content_check as content_check

    engagement = make_engagement(tmp_path, ITEMS, people=(JOHN,))
    text_pdf(inbox_of(engagement) / "scan0012.pdf", "")            # no text layer
    read_by_ocr = "Form W-2 Wage and Tax Statement 2025 Employee: John Park"
    monkeypatch.setattr(content_check, "_ocr_pdf", lambda path: read_by_ocr)

    [filed] = sort(engagement, today=DAY1).filed

    assert filed.identifier == "A01"
    assert filed.reason.endswith("; name confirmed (John Park)")


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


@pytest.mark.parametrize("earlier", ("set aside", "working copy deleted"))
@pytest.mark.parametrize("who, confirms", (("Sofia Ruiz", False), ("John Park", True)))
def test_a_re_send_after_a_set_aside_is_name_checked_before_it_files(
        tmp_path, monkeypatch, earlier, who, confirms):
    """Decision 111's two roads route a re-send afresh inside the one
    return, and both of them are name-checked before they file (decision
    128). Without the check a W-2 set aside the day the list had no row for
    it, or one whose working copy a preparer deleted, would file on its
    keywords alone whoever the page named - the very failure the name tier
    exists to stop, arriving by the back door. (Since decision 157 a deleted
    copy is made again from its original first; the re-file road is the
    one a copy takes while its original cannot be read, as here.)"""
    import tracker.filer as filer_module
    from tracker.filer import dismiss_review_file

    page = "Form W-2 Wage and Tax Statement 2025"
    w2 = RequestItem(identifier="A01", document="W-2 Wage Statements", period="TY2025",
                     allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("W-2",))
    if earlier == "set aside":
        # Nothing on the list asks for a W-2 yet, so the first arrival
        # parks whoever it names and a person sets it aside; then the list
        # gains the row.
        engagement = make_engagement(tmp_path, [ITEMS[1]], people=(JOHN,))
        drop(engagement, "w2.pdf", page, who=who)
        parked = sort(engagement, today=DAY1).review[0]
        dismiss_review_file(engagement, parked.pbc_location, today=DAY1)
        rows = [ITEMS[1], w2]
    else:
        # The row is on the list but nobody had marked it Named, so the
        # first arrival files on its keywords alone; a preparer deletes the
        # working copy and a person ticks Named in the editor.
        engagement = make_engagement(tmp_path, [replace(w2, named=False)], people=(JOHN,))
        drop(engagement, "w2.pdf", page, who=who)
        filed = sort(engagement, today=DAY1).filed[0]
        (engagement / filed.prepared_location).unlink()
        syncing = locate(engagement, filed.pbc_location)
        real = filer_module.is_cloud_placeholder
        monkeypatch.setattr(filer_module, "is_cloud_placeholder", lambda p: p == syncing or real(p))
        rows = [w2]
    save_rules(engagement, rows, load_engagement_info(engagement))

    drop(engagement, "w2.pdf", page, who=who)          # the same bytes again
    report = sort(engagement, today=DAY2)

    if confirms:
        [again] = report.filed
        assert again.identifier == "A01"
        assert again.reason.endswith("; name confirmed (John Park)")
    else:
        assert report.filed == []
        [again] = report.review
        assert again.decision == NEEDS_REVIEW
        assert again.code == reasons.NAME_NOT_ON_PAGE.code


# ====== the household routes: the feed list (decisions 129 and 132) =======
#
# A client with a co-owned business keeps one drop folder, and the business
# lives in a household shared to its co-owners. So a household's drop folder
# feeds its own returns unless a person extends it to named return lines in
# other households - and a document filed to one of those rests under the
# folder that return lives in, seen by exactly that folder's sharing.

FATHER = (Person("taxpayer", "John Park", propose_spellings("John Park", "taxpayer")),)
LLC_PEOPLE = (Person("entity", "Park & Lee LLC",
                     propose_spellings("Park & Lee LLC", "entity")),)


def feeding(tmp_path, feeds):
    """Park Family's drop folder, extended to these return lines by a
    person - one ``household_changed`` event, exactly as the editor
    records it."""
    from tracker.households import load_household_info, save_household
    from tracker.layout import private_household_dir

    folder = private_household_dir(tmp_path, "Park Family")
    save_household(folder, replace(load_household_info(folder), feeds=tuple(feeds)))
    return folder


@pytest.fixture
def fed(tmp_path):
    """The plan's example: a father's household with his own 1040, the
    co-owned LLC in a household of its own, and the father's drop folder
    feeding the LLC's return line."""
    from tracker.records import Feed

    father = make_engagement(tmp_path, ITEMS, household="Park Family",
                             return_name="1040 - John Park", people=FATHER)
    llc = make_engagement(tmp_path, BUSINESS, household="Park & Lee LLC",
                          return_name="1120S - Park & Lee LLC", people=LLC_PEOPLE)
    feeding(tmp_path, [Feed("Park & Lee LLC", "1120S - Park & Lee LLC")])
    return father, llc


LLC_LABEL = "Park & Lee LLC 2025 1120S - Park & Lee LLC"


def click(home, row, target, *, today=DAY2, seq=None):
    """The one click (decision 204), as the API makes it: the row's own
    Waits For claim handed to the return it names, nothing picked."""
    from tracker.filer import hand_over

    claim = row.waiting_for
    return hand_over(home, row.pbc_location, target, claim.identifiers[0],
                     also=claim.identifiers[1:], answers=claim.answers, waiting=True,
                     seq=seq, today=today)


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


def test_the_one_click_is_refused_on_a_row_rewritten_since_it_was_shown(fed):
    """UX 1: the click carries the row's version, and a row a person set
    aside since the card was drawn is refused before a file is touched.
    Without a version, a row that no longer waits refuses too."""
    from tracker.filer import NOT_WAITING, StaleRowError, dismiss_review_file

    father, llc = fed
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    [waiting] = sort_all([father, llc], home=[father], today=DAY1)[father].review
    shown = seq_of(father, waiting)
    dismiss_review_file(father, waiting.pbc_location, "not theirs", today=DAY2)
    files, lines = every_byte(father), len(ledger.read_events(father))

    with pytest.raises(StaleRowError):
        click(father, waiting, llc, seq=shown)
    with pytest.raises(FilingError, match=NOT_WAITING.format(name="tb.pdf")):
        click(father, waiting, llc)

    assert every_byte(father) == files and len(ledger.read_events(father)) == lines
    assert read_index(llc) == [] and not open_intents(llc)
    [row] = read_index(father)
    assert row.waits_for == ""                  # set aside, it waits for nothing


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


def test_a_set_aside_re_send_naming_a_fed_households_person_parks_too(fed):
    """The _sort_one road (decision 137 B#5's reasoning, now for a named
    page): the LLC set a notice aside, its list gained the row that takes
    it, and the father sends the same bytes. Routed afresh against the
    LLC's list and naming the LLC, it is not filed there: it parks at home
    for one click, saying it was sent again."""
    from tracker.filer import RESENT_AFTER_SET_ASIDE, dismiss_review_file

    father, llc = fed
    notice = "Agency notice of adjustment 2025"
    drop(llc, "notice.pdf", notice, who="Park & Lee LLC")
    [parked] = sort_all([llc], today=DAY1)[llc].review
    dismiss_review_file(llc, parked.pbc_location, "nothing asks for it", today=DAY1)
    notices = RequestItem(identifier="B02", document="Agency Notices", period="TY2025",
                          allowed_extensions=("pdf",), min_size_kb=0,
                          required_keywords=("agency notice",))
    save_rules(llc, [*BUSINESS, notices], load_engagement_info(llc))
    before = read_index(llc)

    drop(father, "notice.pdf", notice, who="Park & Lee LLC")
    done = sort_all([father, llc], home=[father], today=DAY2)

    assert read_index(llc) == before and done[llc].filed == []
    [row] = read_index(father)
    assert row.decision == NEEDS_REVIEW
    assert row.code == reasons.NAMED_ACROSS_HOUSEHOLDS.code
    assert row.reason.startswith(RESENT_AFTER_SET_ASIDE.split("{")[0])
    assert row.waiting_for.identifiers == ("B02",)
    assert row.pbc_location == original_at(father, "notice.pdf")
    rows_rest_at_home(father, llc)


def test_a_re_send_through_a_feed_of_a_document_the_other_household_lost_parks_and_the_click_counts_it_once(
        fed, monkeypatch):
    """The LLC's filed copy is gone and its original cannot be read to make
    it again (still syncing). The father sends the same bytes: routed afresh
    in the LLC's record, it parks at home for the click rather than filing
    there, and after the click the LLC's request counts the document once."""
    import tracker.filer as filer_module
    from tracker.scanner import scan_engagement

    father, llc = fed
    first = filed_across(father, llc, "tb.pdf", "Trial balance as of December 31 2025")
    (llc / first.prepared_location).unlink()
    syncing = locate(llc, first.pbc_location)
    real = filer_module.is_cloud_placeholder
    monkeypatch.setattr(filer_module, "is_cloud_placeholder", lambda p: p == syncing or real(p))

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


# ------------- File under another return (decisions 129 and 132) -----------


def parked_notice(father):
    """One document nothing asks for, waiting for a person in the father's
    own return - the row a hand-over acts on."""
    drop(father, "notice.pdf", "an agency notice nothing asks for")
    return sort(father, returns=[father], today=DAY1).review[0]


def rows_rest_at_home(*returns):
    """Claim 27's invariant (decision 132), asked of every record named:
    once no intent is open, every row a record holds names an original
    under **that record's own** household-year folder. A row about a
    document resting under another household is the one thing the owner's
    sentence rules out."""
    for engagement in returns:
        assert open_intents(engagement) == [], engagement.name
        home = originals_of(engagement)
        for row in read_index(engagement):
            assert locate(engagement, row.pbc_location).parent == home, (engagement.name, row)


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


def test_a_released_row_is_gone_from_the_index_the_queue_and_every_count_and_the_journal_says_where_it_went(
        fed):
    """The document is the other return's now, and this return holds
    nothing about it (decision 132): not a row, not a place in the queue,
    not a count, not a second decision. Only the journal keeps the line,
    and it names the return and the request - never a person."""
    from tracker import review
    from tracker.filer import RELEASED_TO, FilingError, assign_review_file, hand_over

    father, llc = fed
    parked = parked_notice(father)
    done = hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)

    assert read_index(father) == []
    assert store.documents(store.connect(), father) == []
    assert review.triage(father, read_index(father), items=load_manifest(father)) == []
    assert [e for e in read_index(father) if e.decision in (NEEDS_REVIEW, DUPLICATE)] == []
    with pytest.raises(FilingError, match="nothing in the index is called"):
        hand_over(father, parked.pbc_location, llc, "B01", today=DAY3)
    with pytest.raises(FilingError, match="nothing in the index is called"):
        assign_review_file(father, parked.pbc_location, "A01", today=DAY3)
    said = [e for e in ledger.read_events(father) if e[ledger.EVENT_KEY] == ledger.RELEASED]
    assert [e[ledger.REASON_KEY] for e in said] == [
        RELEASED_TO.format(label=done.label, identifier="B01")]
    assert "John Park" not in said[0][ledger.REASON_KEY]


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

        monkeypatch.setattr(filer_module, "_record", interleaved)
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


# ============== what we have received (decision 130) ======================


def test_received_for_reads_each_index_once(tmp_path, monkeypatch):
    """The README's received list is a rendering of the index and nothing
    else (S-2): one index read and one request-list read per return, and
    no second copy anywhere."""
    import tracker.filer as filer_module
    from tests.conftest import seed_index
    from tracker.filer import received_for
    from tracker.records import IndexEntry

    items = [RequestItem(identifier="A01", document="W-2")]
    first = make_engagement(tmp_path, items, return_name="1040 - First")
    second = make_engagement(tmp_path, items, return_name="1040 - Second")
    for folder in (first, second):
        seed_index(folder, [IndexEntry(
            received="2026-09-23", original_name="w2.pdf", size_kb=1.0, digest=("1" if folder == first else "2") * 64,
            identifier="A01", prepared_location="PBC/A01 - W-2/A01 - W-2.pdf",
            pbc_location=location_of(folder, originals(folder) / f"w2 {folder.name}.pdf"),
            decision=FILED, reason="")])

    read = []
    lists = []
    real_read, real_list = filer_module.read_index, filer_module.load_manifest
    monkeypatch.setattr(filer_module, "read_index",
                        lambda folder: read.append(Path(folder)) or real_read(folder))
    monkeypatch.setattr(filer_module, "load_manifest",
                        lambda folder: lists.append(Path(folder)) or real_list(folder))

    received = received_for([first, second])

    assert read == [first, second]
    assert lists == [first, second]
    assert [(line.return_path, line.label) for line in received.lines] == [
        (first, "A01 - W-2"), (second, "A01 - W-2")]
    assert received.under_review == ()

    # And the refresh reads each return's details and list once, handing
    # that one read to both received_for and write_readme (the review's F3).
    import tracker.scaffold as scaffold_module
    from tracker.filer import refresh_household_readme
    from tracker.layout import household_of

    read.clear()
    lists.clear()
    details = []
    real_scaffold_list = scaffold_module.load_manifest
    real_details = scaffold_module.load_engagement_info
    monkeypatch.setattr(scaffold_module, "load_manifest",
                        lambda folder: lists.append(Path(folder)) or real_scaffold_list(folder))
    monkeypatch.setattr(scaffold_module, "load_engagement_info",
                        lambda folder: details.append(Path(folder)) or real_details(folder))

    assert refresh_household_readme(household_of(first)) is not None

    assert sorted(read) == sorted([first, second])
    assert sorted(lists) == sorted([first, second])
    assert sorted(details) == sorted([first, second])


def test_a_second_copy_whose_request_was_deleted_reads_other_document_never_another_request(
        tmp_path):
    """The review's F1 (decision 130). A two-form page was filed under A02
    with a second copy under A01-B; A01-B has since been deleted from the
    list. The copy's folder, ``A01-B - Loan Statement``, starts with
    ``A01`` - but a bare prefix proves nothing, and the README must never
    tell the client their W-2 arrived when none did. A copy names a request
    only when its folder is that request's own folder name, or the text
    after the identifier begins with the label separator. Since decision
    168 the test is made of the copy's own name, in Prepared itself."""
    from tests.conftest import seed_index
    from tracker.filer import received_for
    from tracker.records import IndexEntry
    from tracker.scaffold import OTHER_DOCUMENT, PREPARED_DIR_NAME

    items = [RequestItem(identifier="A01", document="W-2 Wage Statement"),
             RequestItem(identifier="A02", document="1098 Mortgage Interest")]
    engagement = make_engagement(tmp_path, items, return_name="1040 - Smith")
    seed_index(engagement, [IndexEntry(
        received="2026-09-23", original_name="combo.pdf", size_kb=12.0,
        digest="c" * 64, identifier="A02",
        prepared_location=f"{PREPARED_DIR_NAME}/A02 - 1098 Mortgage Interest.pdf",
        pbc_location=location_of(engagement, originals(engagement) / "combo.pdf"), decision=FILED, reason="a reason",
        also_filed=f"{PREPARED_DIR_NAME}/A01-B - Loan Statement.pdf")])

    labels = [line.label for line in received_for([engagement]).lines]

    assert labels == ["A02 - 1098 Mortgage Interest", OTHER_DOCUMENT]
    assert "A01 - W-2 Wage Statement" not in labels

    # A copy a person renamed within the shape still names its request.
    seed_index(engagement, [IndexEntry(
        received="2026-09-24", original_name="combo2.pdf", size_kb=12.0,
        digest="e" * 64, identifier="A02",
        prepared_location=f"{PREPARED_DIR_NAME}/A02 - 1098 Mortgage Interest (2).pdf",
        pbc_location=location_of(engagement, originals(engagement) / "combo2.pdf"), decision=FILED, reason="a reason",
        also_filed=f"{PREPARED_DIR_NAME}/a01 - my w2s.pdf")])

    labels = [line.label for line in received_for([engagement]).lines]

    assert labels.count("A01 - W-2 Wage Statement") == 1
# ------------------------------------ decision 131: the room a return has ----


#: One request with no second file expected, as the room's claims want it:
#: its canonical copy is ``Prepared/A01 - W-2 Wage Statements - TY2025.pdf``,
#: 48 characters below the return folder (74 while it sat in a request
#: folder of its own, before decision 168).
ROOM_ITEMS = [
    RequestItem(
        identifier="A01", document="W-2 Wage Statements", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0,
        required_keywords=("W-2",), date_pattern=r"(?i)\b2025\b",
    ),
]
#: Below the return folder: the canonical copy's path, and the folder it
#: sits in - Prepared itself since decision 168.
CANONICAL_BELOW = 48
FOLDER_BELOW = 9
#: A period long enough that ``A01 - <period>.pdf`` (29 characters) does not
#: fit the 28 a return of 222 characters leaves in Prepared - while its
#: review folder still has room (decision 131's floor, 260 exactly). Since
#: decision 168 that is the only way a request is left no room: Prepared is
#: shallower than the review folder, so an ordinary TY2025 name fits
#: wherever a review copy does.
LONG_PERIOD = "Jan 2025 - Dec 2025"


def with_the_long_period(item):
    """``item`` asking for :data:`LONG_PERIOD`, its year check stated - a
    period this long would derive a month check a year-end form does not
    pass, and the claims here are about room, not about the check."""
    return replace(item, period=LONG_PERIOD, date_pattern=r"(?i)\b2025\b")
NO_ROOM_RETURN = 222


def tight_return(base, over: int, items=ROOM_ITEMS, **kwargs):
    """A return whose A01 canonical copy passes Windows's limit by ``over``
    characters: its folder is ``260 + over - 48`` characters long."""
    from tests.conftest import root_for_a_return_of

    root = root_for_a_return_of(base, 260 + over - CANONICAL_BELOW)
    engagement = make_engagement(root, items, **kwargs)
    assert len(str(engagement)) + CANONICAL_BELOW == 260 + over
    return engagement


def test_the_room_is_measured_from_the_list_alone_and_creations_figure_is_unchanged(tmp_path):
    """``room_for`` reads no disk: a return folder that does not exist is
    measured as readily as one that does. Its ``need`` is creation's figure
    exactly - the deepest canonical copy: 138 for the example row, 138 for
    the whole 1040 core list at its longest extension, 215 for a row whose
    name is a hundred characters - each copy in Prepared itself (decision
    168; 164, 163 and 316 while each request had a folder, 223 for the core
    list with the full titles before decision 144)."""
    from tracker.filer import Room, room_for, shortest_name_for
    from tracker.layout import MAX_PATH_LENGTH, deepest_path_length, limit_for, return_dir_for
    from tracker.templates import template_items

    root = Path("G:/Shared drives/JPA Clients")
    engagement = return_dir_for(root, "Park Family", 2026, "1040 - John & Maria Park")
    assert not engagement.exists()

    w2 = replace(ITEMS[0], period="TY2026", expected_count=1)
    room = room_for(engagement, [w2])
    assert room.need == 138 and room.limit == MAX_PATH_LENGTH and room.short == 0
    # The shortest name: the identifier, the period, a two-digit suffix, the extension.
    assert shortest_name_for(w2, "pdf") == "A01 - TY2026 (99).pdf"
    assert room.least == len(str(engagement / PREPARED_DIR_NAME / "A01 - TY2026 (99).pdf"))
    assert room.floor == len(str(engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME / "x (99).pdf"))
    assert room.floor == 128 and room.parks == 0

    core = [replace(item, allowed_extensions=("xlsx",))
            for item in template_items("1040", core_only=True)]
    subpaths = [f"{PREPARED_DIR_NAME}/{prepared_name_for(item, 'xlsx', set())}" for item in core]
    assert room_for(engagement, core).need == deepest_path_length(engagement, subpaths) == 138
    # Every copy is a workbook, and a workbook's reader allows 218: with the
    # short names every one fits (it was five short with the full titles).
    assert limit_for("xlsx") == 218
    assert room_for(engagement, core).short == 0

    # A name of a hundred characters: no short title typed in the editor may
    # be one (it is refused past twenty), but the measure is arithmetic on
    # whatever name a row carries, and is held to it here.
    long_row = replace(template_items("1040", core_only=True)[0], document="x" * 100,
                       short_title="x" * 100, allowed_extensions=("xlsx",))
    long = room_for(engagement, [long_row])
    # With no folder named after the hundred characters too, the name is in
    # the path once, capped: it fits even a workbook's reader, where it was
    # 98 characters short and a workbook parked.
    assert long.need == 215 and long.short == 0
    assert long.least == len(str(engagement / PREPARED_DIR_NAME / "A01 - TY2026 (99).xlsx"))
    assert long.parks == 0

    # A row set aside is not measured, as creation does not measure it.
    from tracker.manifest import Override

    aside = replace(long_row, manual_override=Override.NOT_APPLICABLE)
    nothing = len(str(engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME / "x (99).xlsx"))
    assert room_for(engagement, [aside]) == Room(need=0, least=0, floor=nothing, parks=0, short=0)


def test_a_working_copy_is_named_to_fit_the_room_left_under_its_folder(tmp_path):
    """A root long enough that the canonical name does not fit: the pass
    files all the same, under a name that keeps the identifier, the period
    and the extension and loses the tail of the document label. The row
    names the copy on disk, the scan proves it, and the next pass's reuse
    check finds it."""
    from tracker.filer import _existing_copy
    from tracker.manifest import Status
    from tracker.scanner import scan_engagement
    from tracker.validators import sha256_of

    engagement = tight_return(tmp_path, 10)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    report = sort(engagement, today=DAY1)

    [entry] = report.filed
    folder = prepared(engagement, "A01")
    [copy] = list(folder.iterdir())
    assert copy.name == "A01 - W-2 Wage - TY2025.pdf"             # " Statements" cut, then the space
    assert len(str(copy)) <= 260
    assert entry.prepared_location == f"{PREPARED_DIR_NAME}/{copy.name}"
    assert locate(engagement, entry.prepared_location) == copy

    scan_engagement(engagement, today=DAY1)
    assert load_manifest(engagement)[0].status == Status.RECEIVED

    original = originals(engagement) / "w2.pdf"
    assert _existing_copy(copy.parent, original, sha256_of(original)) == copy


def test_the_numbered_suffix_is_counted_when_a_name_is_cut(tmp_path):
    """Two files for one request under the same tight root: the second's
    ``(2)`` is counted in the same loop that cuts, so its document part
    gives up the suffix's four characters (less what the cut had to spare)
    and the pair is still one series - the same stem cut further, and the
    number after it."""
    items = [replace(ROOM_ITEMS[0], expected_count=2)]
    engagement = tight_return(tmp_path, 10, items=items)
    drop(engagement, "w2-a.pdf", "Form W-2 Wage and Tax Statement 2025 employer one")
    drop(engagement, "w2-b.pdf", "Form W-2 Wage and Tax Statement 2025 employer two")

    report = sort(engagement, today=DAY1)

    assert len(report.filed) == 2
    folder = prepared(engagement, "A01")
    room = 260 - len(str(engagement / PREPARED_DIR_NAME)) - 1
    names = sorted(p.name for p in folder.iterdir())
    assert names == ["A01 - W-2 W - TY2025 (2).pdf", "A01 - W-2 Wage - TY2025.pdf"]
    assert all(len(name) <= room for name in names)
    second, first = names
    # One series: the second is the first's stem, cut further, numbered.
    assert second.removesuffix(" - TY2025 (2).pdf") in first.removesuffix(" - TY2025.pdf")
    assert len(first.removesuffix(" - TY2025.pdf")) - len(second.removesuffix(" - TY2025 (2).pdf")) == 3
    assert sorted(e.prepared_location.rsplit("/", 1)[1] for e in report.filed) == names


def test_a_request_with_no_room_for_its_shortest_name_parks_with_the_sentence(tmp_path):
    """Every rule accepted the W-2 and Prepared leaves no room for even
    ``A01 - Jan 2025 - Dec 2025.pdf``: it parks, with PATH_NO_ROOM naming
    both numbers, the request as its candidate, a review copy a person can
    open and the original where every original rests."""
    from tests.conftest import root_for_a_return_of
    from tracker.filer import PATH_NO_ROOM

    # Prepared is 231 characters: 28 left for a name that needs 29.
    items = [replace(ROOM_ITEMS[0], period=LONG_PERIOD)]
    engagement = make_engagement(root_for_a_return_of(tmp_path, NO_ROOM_RETURN), items)
    assert len(str(engagement)) + FOLDER_BELOW == 231
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    report = sort(engagement, today=DAY1)

    assert report.filed == []
    [parked] = report.review
    assert parked.reason == PATH_NO_ROOM.format(
        length=231 + 1 + len(f"A01 - {LONG_PERIOD}.pdf"), limit=260, ext=".pdf")
    assert parked.candidates == "A01"
    copy = locate(engagement, parked.prepared_location)
    assert copy.is_file() and copy.parent.name == REVIEW_DIR_NAME
    assert (originals(engagement) / "w2.pdf").is_file()
    assert list(prepared(engagement, "A01").iterdir()) == []


def test_a_review_copy_is_named_to_fit_and_the_row_keeps_the_clients_name(short_root):
    """A client's file name of 150 characters under a root that leaves the
    review folder less room than that: the document parks, its review copy
    is cut to fit - the extension kept - and the row's ``original_name`` is
    the client's whole name, which is what the queue's *what the name says*
    line reads."""
    from tests.conftest import root_for_a_return_of
    from tracker import review

    root = root_for_a_return_of(short_root, 109)                  # the review folder: 135
    engagement = make_engagement(root, ROOM_ITEMS)
    review_dir = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    name = "letter " + "n" * 139 + ".pdf"
    assert len(name) == 150 and len(str(review_dir)) + 1 + len(name) > 260
    drop(engagement, name, "A letter about nothing on the list")

    report = sort(engagement, today=DAY1)

    [parked] = report.review
    assert parked.original_name == name
    copy = locate(engagement, parked.prepared_location)
    assert copy.is_file() and copy.suffix == ".pdf"
    assert copy.name.startswith("letter nnn") and len(str(copy)) == 260
    assert (originals(engagement) / name).is_file()                # the original, uncut
    [triaged] = review.triage(engagement, read_index(engagement), items=load_manifest(engagement))
    assert triaged.entry.original_name == name


def test_a_persons_filing_and_the_hand_over_are_named_to_fit_and_refuse_only_below_the_floor(tmp_path):
    """A person's filing and a hand-over name the working copy the way the
    pass does: cut to fit where the canonical name does not, and refused
    - nothing moved - only where not even the shortest name fits: a
    person's filing with PATH_NO_ROOM, a hand-over with PATH_NO_ROOM_IN
    naming the taking return, since the person reads it on another
    return's page (decision 204's review, S-1)."""
    from tests.conftest import root_for_a_return_of
    from tracker.filer import PATH_NO_ROOM_IN, _details_of, _label_of, assign_review_file, hand_over

    # One household, three returns: home fits; ``cut`` leaves A01 ten short;
    # ``none`` leaves its Prepared 28 characters for a 29-character name.
    # Ten characters of the length are the root's, not the names': a name
    # is at most eighty characters since decision 188.
    root = root_for_a_return_of(tmp_path, 160, return_name="1040 - Home")
    home = make_engagement(root, ROOM_ITEMS, return_name="1040 - Home")
    cut = make_engagement(root, ROOM_ITEMS, return_name="1040 - " + "s" * 66)
    none = make_engagement(root, [replace(ROOM_ITEMS[0], period=LONG_PERIOD)],
                           return_name="1040 - " + "t" * 66)
    assert len(str(cut)) + CANONICAL_BELOW == 270
    assert len(str(none)) + FOLDER_BELOW == 231
    drop(home, "note.pdf", "A letter the list does not ask for")
    drop(home, "other.pdf", "Another letter the list does not ask for")
    sort_all([home, cut, none], today=DAY1)
    parked = {e.original_name: e for e in read_index(home) if e.decision == NEEDS_REVIEW}
    assert set(parked) == {"note.pdf", "other.pdf"}

    # Refused below the floor, with the sentence, and nothing moved.
    before = sorted(str(p) for p in root.rglob("*"))
    with pytest.raises(FilingError) as refused:
        hand_over(home, parked["note.pdf"].pbc_location, none, "A01", today=DAY2)
    assert str(refused.value) == PATH_NO_ROOM_IN.format(
        label=_label_of(none, _details_of(none)),
        length=231 + 1 + len(f"A01 - {LONG_PERIOD}.pdf"), limit=260, ext=".pdf")
    assert sorted(str(p) for p in root.rglob("*")) == before

    # Handed to the return with room for a cut name: named to fit.
    handed = hand_over(home, parked["note.pdf"].pbc_location, cut, "A01", today=DAY2)
    copy = locate(cut, handed.target_entry.prepared_location)
    assert copy.is_file() and copy.name == "A01 - W-2 Wage - TY2025.pdf" and len(str(copy)) <= 260

    # A person's filing in a return with no room: refused, nothing moved.
    tight = make_engagement(root_for_a_return_of(tmp_path / "t", NO_ROOM_RETURN),
                            [replace(ROOM_ITEMS[0], period=LONG_PERIOD)])
    drop(tight, "note.pdf", "A letter the list does not ask for")
    sort(tight, today=DAY1)
    [waiting] = [e for e in read_index(tight) if e.decision == NEEDS_REVIEW]
    before = sorted(str(p) for p in (tmp_path / "t").rglob("*"))
    with pytest.raises(FilingError, match="at its shortest"):
        assign_review_file(tight, waiting.pbc_location, "A01", today=DAY2)
    assert sorted(str(p) for p in (tmp_path / "t").rglob("*")) == before

    # And one with room for a cut name: filed under it.
    roomy = tight_return(tmp_path / "r", 10)
    drop(roomy, "note.pdf", "A letter the list does not ask for")
    sort(roomy, today=DAY1)
    [waiting] = [e for e in read_index(roomy) if e.decision == NEEDS_REVIEW]
    done = assign_review_file(roomy, waiting.pbc_location, "A01", today=DAY2)
    assert done.entry.prepared_location.endswith("/A01 - W-2 Wage - TY2025.pdf")
    assert locate(roomy, done.entry.prepared_location).is_file()


def test_creation_and_the_rollover_still_refuse_the_canonical_name_past_the_limit(tmp_path):
    """Creation's and the rollover's refusal are unchanged: the canonical
    name at each row's longest extension, against Windows's 260 - not a
    reader's 218, which only cuts a name - with decision 125's words."""
    from tracker.filer import refuse_a_path_past_the_limit
    from tracker.layout import PATH_TOO_LONG, return_dir_for
    from tracker.manifest import ManifestError
    from tracker.templates import template_items

    # A household name fifty characters longer than the example's: the
    # core list still fits (138 at the example's, 188 here), and a row named
    # by a hundred characters - 215 at the example's since decision 168 -
    # is past the limit (the measure is arithmetic on the name the row
    # carries; a typed short title is refused past twenty).
    root = Path("G:/Shared drives/JPA Clients")
    engagement = return_dir_for(root, "Park Family " + "p" * 49, 2026, "1040 - John & Maria Park")
    core = [replace(item, allowed_extensions=("xlsx",))
            for item in template_items("1040", core_only=True)]
    refuse_a_path_past_the_limit(engagement, core)          # 188 - accepted

    long_row = replace(core[0], document="x" * 100, short_title="x" * 100)
    with pytest.raises(ManifestError) as refused:
        refuse_a_path_past_the_limit(engagement, [long_row])
    assert str(refused.value) == PATH_TOO_LONG.format(folder=engagement, length=265, limit=260)


# --------------------------- decision 131's review: the lead's rulings ----


def test_unfiling_a_long_named_document_cuts_its_review_copy_to_fit(tmp_path):
    """F1: a person's unfiling names the review copy the way the pass's park
    does - the client's name cut to the room the review folder leaves,
    the extension kept - where before it was written under the whole name,
    past the limit. The row keeps the client's whole name."""
    from tests.conftest import root_for_a_return_of
    from tracker.filer import unfile_document

    engagement = make_engagement(root_for_a_return_of(tmp_path, 180), ROOM_ITEMS)
    inbox = inbox_of(engagement)
    name = "W-2 " + "w" * (255 - len(str(inbox)) - 1 - len("W-2 .pdf")) + ".pdf"
    assert len(str(inbox / name)) == 255
    assert len(str(review_dir(engagement))) + 1 + len(name) > 260
    drop(engagement, name, "Form W-2 Wage and Tax Statement 2025")
    [filed] = sort(engagement, today=DAY1).filed

    result = unfile_document(engagement, filed.pbc_location, today=DAY2)

    copy = locate(engagement, result.entry.prepared_location)
    assert copy.is_file() and copy.parent == review_dir(engagement)
    assert copy.suffix == ".pdf" and copy.name.startswith("W-2 www")
    assert len(str(copy)) == 260
    assert result.entry.original_name == name
    assert (originals(engagement) / name).is_file()                  # the original, uncut


def test_a_recovery_copy_is_cut_to_fit_and_one_that_cannot_be_made_names_no_copy(tmp_path, monkeypatch):
    """F1: the recovery's copy to act on is named as every review copy is;
    and where none can be made the row names **no** copy - never the one
    the interrupted step was making, which is not there - and says why in
    a fixed sentence."""
    from tests.conftest import root_for_a_return_of
    from tracker import filer
    from tracker.filer import REVIEW_NO_ROOM, NoRoom

    engagement = make_engagement(root_for_a_return_of(tmp_path, 180), ROOM_ITEMS)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    [filed] = sort(engagement, today=DAY1).filed
    locate(engagement, filed.prepared_location).unlink()       # the copy the step was making: gone
    long_named = replace(filed, original_name="letter " + "n" * 150 + ".pdf")

    location, said = filer._a_copy_to_act_on(engagement, long_named, None)

    copy = locate(engagement, location)
    assert said == "" and copy.is_file() and copy.parent == review_dir(engagement)
    assert copy.name.startswith("letter nnn") and copy.suffix == ".pdf" and len(str(copy)) == 260

    copy.unlink()
    sentence = REVIEW_NO_ROOM.format(name="w2.pdf", length=270, limit=260, ext=".pdf")

    def no_room(_folder, _name):
        raise NoRoom(270, 260, "pdf", sentence=sentence)

    monkeypatch.setattr(filer, "_review_copy_path", no_room)
    assert filer._a_copy_to_act_on(engagement, filed, None) == ("", sentence)


def test_a_spreadsheet_limit_is_never_called_what_windows_allows():
    """F2: since the owner's Q-A a workbook's limit is a reader's 218, so
    every sentence of decision 131 names the limit as that kind of copy's,
    never as what Windows allows."""
    from tracker.filer import (
        HOUSEHOLD_NO_ROOM,
        PATH_NO_ROOM,
        PATH_NO_ROOM_IN,
        REVIEW_NO_ROOM,
        NoRoom,
    )

    for sentence in (PATH_NO_ROOM, PATH_NO_ROOM_IN, HOUSEHOLD_NO_ROOM, REVIEW_NO_ROOM):
        assert "Windows" not in sentence
    workbook = replace(ROOM_ITEMS[0], allowed_extensions=("xlsx",))
    with pytest.raises(NoRoom) as refused:
        prepared_name_for(workbook, "xlsx", set(), room=5)
    said = str(refused.value)
    assert refused.value.limit == 218 and "past the 218 characters a .xlsx copy may have" in said
    assert "Windows" not in said
    with pytest.raises(NoRoom) as refused:
        prepared_name_for(ROOM_ITEMS[0], "pdf", set(), room=5)
    assert "past the 260 characters a .pdf copy may have" in str(refused.value)
    with pytest.raises(NoRoom) as refused:
        prepared_name_for(ROOM_ITEMS[0], "", set(), room=5)
    assert "a working copy may have" in str(refused.value)


def test_a_review_copy_with_an_odd_suffix_is_cut_to_fit_or_said_as_a_review_copy(tmp_path):
    """F4: the pass's floor proves room for a short extension, not for
    whatever a client's file name ends in. A name whose "suffix" is not an
    extension is cut as one stem to fit; a real extension is kept whole,
    and where not even one character of stem fits beside it the sentence
    says a *review copy* could not be made - never a request's label."""
    from tracker.filer import REVIEW_NO_ROOM, NoRoom, _review_copy_path, _unique_path

    folder = tmp_path / "review"
    folder.mkdir()
    odd = "Scan 2026.01.15 from the phone of the client for the W-2"
    cut = _unique_path(folder, odd, room=30)
    assert len(cut.name) <= 30 and cut.name.startswith("Scan 2026.01")
    cut.write_text("one")
    again = _unique_path(folder, odd, room=30)
    assert again != cut and len(again.name) <= 30 and again.name.endswith("(2)")
    # Through the one function every review copy is named by.
    fitted, said = _review_copy_path(folder, odd * 5)
    assert said == "" and len(str(fitted)) <= 260

    with pytest.raises(NoRoom) as refused:
        _unique_path(folder, "statement.pdf", room=4)
    assert str(refused.value) == REVIEW_NO_ROOM.format(
        name="statement.pdf", length=len(str(folder / "s.pdf")), limit=len(str(folder)) + 1 + 4,
        ext=".pdf")
    assert "label" not in str(refused.value)
    # Without a room nothing changes: an original keeps its own name, always.
    assert _unique_path(folder, odd).name == odd


def test_an_existing_copy_is_found_before_a_name_is_measured(tmp_path):
    """F5: a killed run left the copy, under the request's name, in a
    Prepared that has no room for a new name. The pass finds it by its
    bytes first - as the hand-over already did - and files under the name
    it has, rather than parking a document whose copy is already there."""
    from tests.conftest import root_for_a_return_of

    items = [replace(ROOM_ITEMS[0], period=LONG_PERIOD)]
    engagement = make_engagement(root_for_a_return_of(tmp_path, NO_ROOM_RETURN), items)
    folder = prepared(engagement, "A01")
    assert len(str(engagement / PREPARED_DIR_NAME)) == 231   # no room for "A01 - <period>.pdf"
    dropped = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    (folder / "c.pdf").write_bytes(dropped.read_bytes())

    report = sort(engagement, today=DAY1)

    assert report.review == []
    [entry] = report.filed
    assert entry.prepared_location == f"{PREPARED_DIR_NAME}/A01 - c.pdf"
    assert [p.name for p in folder.iterdir()] == ["A01 - c.pdf"]


def test_a_filing_that_parks_for_room_leaves_nothing_it_made(short_root):
    """F6: decision 94 files one page under two requests. The first has room
    and the second has none, so the filing parks - and nothing the attempt
    would have made for the first is left behind: nothing is made until
    every copy of the filing is named. Since decision 168 there is no
    request folder to make either, only the copy."""
    from tests.conftest import root_for_a_return_of
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.filer import PATH_NO_ROOM

    # C01's period leaves it no room in a Prepared of 231 characters, where
    # A01's name is cut to fit.
    long_c01 = with_the_long_period(ITEMS[1])
    items = [ITEMS[0], long_c01]
    engagement = make_engagement(root_for_a_return_of(short_root, NO_ROOM_RETURN), items,
                                 scaffold=False)
    assert len(str(engagement / PREPARED_DIR_NAME)) == 231
    inbox_of(engagement).mkdir(parents=True, exist_ok=True)
    drop(engagement, "scan0003.pdf", "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))

    report = sort(engagement, today=DAY1)

    assert report.filed == []
    [parked] = report.review
    assert parked.reason == PATH_NO_ROOM.format(length=231 + 1 + len(f"C01 - {LONG_PERIOD}.pdf"),
                                                limit=260, ext=".pdf")
    made = sorted(p.name for p in (engagement / PREPARED_DIR_NAME).iterdir())
    assert made == [REVIEW_DIR_NAME]                          # no A01 copy left behind


def test_the_period_survives_a_long_label():
    """F6: the cap on a working copy's name cuts the document label, never
    the period - the one part that says which year a copy belongs to."""
    from tracker.filer import _MAX_STEM

    long = RequestItem(identifier="A01", document="X" * 120, short_title="X" * 120, period="TY2026")
    name = prepared_name_for(long, "pdf", set())
    assert name.endswith(" - TY2026.pdf") and len(name) == _MAX_STEM + len(".pdf")
    assert name.startswith("A01 - XXX")
    fitted = prepared_name_for(long, "pdf", set(), room=40)
    assert fitted.endswith(" - TY2026.pdf") and len(fitted) <= 40


def test_a_workbook_review_copy_fitted_past_a_readers_limit_says_so(tmp_path):
    """Deviation 4: a reader's shorter limit never stops a park - the copy
    is fitted to Windows's own - but the row says the copy is longer than
    a spreadsheet program may open, and what to do about it."""
    from tests.conftest import root_for_a_return_of
    from tracker.filer import REVIEW_COPY_PAST_READER

    engagement = make_engagement(root_for_a_return_of(tmp_path, 200), ROOM_ITEMS)   # review: 227
    assert len(str(review_dir(engagement))) == 227
    inbox_of(engagement).mkdir(parents=True, exist_ok=True)
    (inbox_of(engagement) / "note.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    report = sort(engagement, today=DAY1)

    [parked] = report.review
    copy = locate(engagement, parked.prepared_location)
    assert copy.is_file() and copy.name == "note.csv" and len(str(copy)) > 218
    assert parked.reason.endswith("; " + REVIEW_COPY_PAST_READER)


def test_a_fed_return_with_no_room_parks_at_home_naming_the_fed_return(tmp_path):
    """Deviation 5, since decision 204: the fed return's request accepts the
    trial balance and its folder has no room even for the shortest name.
    The pass never files across households, so the document parks where it
    was dropped for one click, the row naming the fed return by its label;
    and the click itself refuses on the room, with nothing moved."""
    from tests.conftest import root_for_a_return_of
    from tracker.filer import PATH_NO_ROOM_IN, NoRoom
    from tracker.records import Feed
    from tracker.registry import discover_engagements

    llc_name = "1120S - Park & Lee LLC " + "l" * 20
    root = root_for_a_return_of(tmp_path, NO_ROOM_RETURN, household="Park & Lee LLC",
                                return_name=llc_name)
    father = make_engagement(root, ITEMS, household="Park Family",
                             return_name="1040 - John Park", people=FATHER)
    business = [with_the_long_period(BUSINESS[0])]
    llc = make_engagement(root, business, household="Park & Lee LLC",
                          return_name=llc_name, people=LLC_PEOPLE)
    feeding(root, [Feed("Park & Lee LLC", llc_name)])
    b01 = prepared(llc, "B01")
    assert len(str(llc / PREPARED_DIR_NAME)) + 1 + len(f"B01 - {LONG_PERIOD}.pdf") == 261
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
    assert str(refused.value) == PATH_NO_ROOM_IN.format(label=label, length=261, limit=260, ext=".pdf")
    assert read_index(father) == [parked] and read_index(llc) == []
    assert [p.name for p in originals(father).iterdir()] == ["tb.pdf"]


def test_a_sibling_return_with_no_room_parks_in_the_home_return_naming_it(tmp_path):
    """Deviation 5 inside one household (the review of decision 204, S-2):
    a W-2 naming Maria, whose return has no room even for the shortest
    name, while John's list also accepts it. The name vetoes John's return,
    Maria's has no room, and the row parks in John's - the home return -
    naming Maria's return by its label, never "this request"."""
    from tests.conftest import root_for_a_return_of
    from tracker.filer import PATH_NO_ROOM_IN
    from tracker.registry import discover_engagements

    long_name = "1040 - Maria Park " + "m" * 24
    root = root_for_a_return_of(tmp_path, NO_ROOM_RETURN, household="Park Family",
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
        label=label, length=261, limit=260, ext=".pdf"))
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


def _link_to(target, link):
    """A junction on Windows, a symlink elsewhere: a folder that is a link."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def test_a_move_whose_source_is_now_behind_a_link_moves_nothing(engagement, tmp_path, monkeypatch):
    """Decision 137 (L2): the link check is made again immediately before
    the rename. The walk refuses what lies behind a junction, but the move
    comes later; a drop's folder swapped for a junction in between must not
    have the rename fetch a file from wherever the junction points."""
    import tracker.filer as filer

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "theirs.pdf").write_bytes(b"%PDF-1.4 somebody else's file")
    inbox = inbox_of(engagement)
    _link_to(outside, inbox / "swapped")
    behind = inbox / "swapped" / "theirs.pdf"

    # Directly: the move itself refuses, and says why.
    with pytest.raises(filer.MovedThroughALinkError, match="reached through a link"):
        filer._move_whole(behind, originals(engagement) / "theirs.pdf", within=inbox)
    assert (outside / "theirs.pdf").exists()

    # Through a pass whose listing was made before the swap: left in place.
    monkeypatch.setattr(filer, "iter_drops", lambda folder, **_: [behind])
    report = sort(engagement, today=DAY1)
    assert [e.name for e in report.errors] == ["theirs.pdf"]
    assert report.errors[0].left_in_place and "(MovedThroughALinkError" in report.errors[0].error
    assert (outside / "theirs.pdf").exists()
    assert report.filed == [] and report.review == []


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
    _link_to(real, tmp_path / "linked")                  # a link ABOVE the clients root
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

    import tracker.filer as filer_module
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
    monkeypatch.setattr(filer_module, "is_cloud_placeholder", lambda p: p == held or real(p))

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
    from tests.test_catalog import cp_notice_lines
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


def test_a_re_sent_set_aside_document_files_under_its_not_asked_row_and_the_earlier_entry_keeps_its_answer(
        tmp_path):
    """Decision 111 is untouched by decision 142. A document a person set
    aside as Not requested - the day the list had no row for it - keeps
    that row and its answer. The client sending it again is a new arrival,
    routed afresh as 111 says: once the catalog's row is on the return as
    not asked, the re-send files there, and its row quotes the earlier
    decision whole."""
    from tracker.filer import NOT_REQUESTED, RESENT_AFTER_SET_ASIDE, dismiss_review_file

    engagement = make_engagement(tmp_path, [ITEMS[0]])
    drop(engagement, "1098.pdf", "Form 1098 Mortgage Interest Statement 2025")
    parked = sort(engagement, today=DAY1).review[0]
    dismissed = dismiss_review_file(engagement, parked.pbc_location, "not ours", today=DAY2).entry

    save_rules(engagement, [*load_manifest(engagement), replace(ITEMS[1], asked=False)],
               load_engagement_info(engagement))
    drop(engagement, "1098.pdf", "Form 1098 Mortgage Interest Statement 2025")   # the same bytes
    report = sort(engagement, today=DAY2)

    [again] = report.filed
    assert again.identifier == "C01"
    assert RESENT_AFTER_SET_ASIDE.format(earlier=dismissed.reason) in again.reason
    earlier = [row for row in read_index(engagement) if row.decision == NOT_REQUESTED]
    assert [row.reason for row in earlier] == [dismissed.reason]


# ------------------------------------------------ decision 144: short names ----


def _catalog_w2(**changes):
    """The 1040 catalog's A01, as a return created today would have it."""
    from tracker.templates import template_items

    return replace(template_items("1040", year=2025)[0], **changes)


def test_the_working_copy_uses_the_short_title(short_root):
    """Decision 144, claim 2: the owner's example. A W-2 filed on the
    catalog's A01 is ``A01 - W-2 - TY2025.pdf`` - the request's short name
    where the full title "W-2 Wage Statements - All Employers" used to be -
    and since decision 168 it sits in Prepared itself, where 144 put it in
    a folder ``A01 - W-2``."""
    w2 = _catalog_w2(expected_count=1, min_size_kb=0)
    assert w2.short_title == "W-2" and w2.document == "W-2 Wage Statements - All Employers"
    assert prepared_name_for(w2, "pdf", set()) == "A01 - W-2 - TY2025.pdf"

    engagement = make_engagement(short_root, [w2])
    drop(engagement, "scan.pdf", "Form W-2 Wage and Tax Statement 2025 wages, tips, other "
                                 "compensation employee's social security number")
    [entry] = sort(engagement, today=DAY1).filed
    assert entry.prepared_location == f"{PREPARED_DIR_NAME}/A01 - W-2 - TY2025.pdf"
    assert (engagement / PREPARED_DIR_NAME / "A01 - W-2 - TY2025.pdf").is_file()


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
    from tracker.filer import room_for
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

SCHWAB_146 = "\n".join([
    "Charles Schwab", "2025 Consolidated Form 1099", "Form 1099-DIV Dividends and Distributions",
    "Form 1099-INT Interest Income", "Form 1099-B Proceeds From Broker and Barter Exchange Transactions",
    "Form 1099-MISC Miscellaneous Information", "Realized Gain and Loss",
])


def _consolidated_return(tmp_path, *, int_div_expected=2):
    """A 1040 on the shipped catalog, the Schwab statement dropped, sorted
    and scanned. A02 expects two statements here: the consolidated one
    carries two of them, its 1099-INT and its 1099-DIV."""
    from tracker.manifest import validated
    from tracker.scanner import scan_engagement
    from tracker.templates import template_items

    items = [replace(i, min_size_kb=0,
                     expected_count=int_div_expected if i.identifier == "A02" else i.expected_count)
             for i in validated(template_items("1040", year=2025))]
    engagement = make_engagement(tmp_path, items)
    drop(engagement, "Schwab 2025 1099.pdf", SCHWAB_146)
    sort(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY1)
    return engagement


def _status(engagement, identifier):
    return next(i for i in load_manifest(engagement) if i.identifier == identifier)


def test_the_statement_answers_the_int_div_row_and_the_letter_does_not_ask_for_it(tmp_path):
    """d146, claim 6. E01 holds the one copy; A02 (its interest and dividend
    sections) and A04 (its miscellaneous section) read Received, each saying
    it is in E01's consolidated statement, and neither folder holds a file.
    The letter asks for none of them, the client's received list shows each
    as included in their consolidated brokerage statement - naming no
    request, in the client's words (Jason's Q-L) - and a store rebuilt from
    the journal agrees with the live one."""
    from tracker.filer import received_for
    from tracker.layout import root_of
    from tracker.manifest import Status
    from tracker.reasons import IN_CONSOLIDATED, IN_CONSOLIDATED_CLIENT
    from tracker.reminder import draft_reminder
    from tracker.scaffold import write_readme

    engagement = _consolidated_return(tmp_path)
    [row] = [r for r in read_index(engagement) if r.decision == FILED]
    assert row.identifier == "E01" and row.also_filed == ""
    assert row.answers == "A02 (1099-int, 1099-div); A04 (1099-misc)"

    prepared = engagement / PREPARED_DIR_NAME
    copies = [p for p in prepared.rglob("*.pdf") if REVIEW_DIR_NAME not in p.parts]
    assert len(copies) == 1 and copies[0].parent == prepared and copies[0].name.startswith("E01 - ")

    for identifier, count in (("E01", 1), ("A02", 2), ("A04", 1)):
        item = _status(engagement, identifier)
        assert item.status == Status.RECEIVED, (identifier, item.validation_notes)
        assert item.file_count == count
    assert IN_CONSOLIDATED.format(row="E01") in _status(engagement, "A02").validation_notes
    assert IN_CONSOLIDATED.format(row="E01") in _status(engagement, "A04").validation_notes

    draft = draft_reminder(engagement, today=DAY1)
    assert not {"E01", "A02", "A04"} & set(draft.asked)
    assert not {"E01", "A02", "A04"} & {flag.item.identifier for flag in draft.held}

    received = received_for([engagement])
    inside = {line.identifier: line.inside for line in received.lines}
    e01 = _status(engagement, "E01").label
    assert inside == {"E01": "", "A02": e01, "A04": e01}
    household = engagement.parents[1]
    text = write_readme(household, received).read_text(encoding="utf-8")
    for identifier in ("A02", "A04"):
        label = _status(engagement, identifier).label
        [said] = [one for one in text.splitlines() if one.strip().startswith(label)]
        assert said.endswith(f", {IN_CONSOLIDATED_CLIENT}"), said
    assert text.count(IN_CONSOLIDATED_CLIENT) == 2
    assert IN_CONSOLIDATED.format(row=e01) not in text
    assert IN_CONSOLIDATED.format(row="E01") not in text
    assert "'s consolidated" not in text

    root = root_of(engagement)
    live = store.connect()
    assert store.check(live, root, engagement) == []
    db = os.environ[store.ENV_STORE]
    store.close()
    os.unlink(db)
    fresh = store.connect()
    store.rebuild_engagement(fresh, root, engagement)
    assert [r.answers for r in read_index(engagement) if r.decision == FILED] == [row.answers]
    assert _status(engagement, "A02").status == Status.RECEIVED
    assert store.check(fresh, root, engagement) == []


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


def test_a_person_can_still_mark_that_row_missing(tmp_path):
    """d146, claim 6. A person marks A02 missing again: the statement stays
    filed under E01 with its copy where it is, A02 comes off its Also
    Answers cell on the record (one answer_withdrawn_by_person line), A02
    goes back to Missing with the regression note, the letter asks for it
    again, and A04 is still answered. Asking twice is refused by name, and
    a rebuilt store agrees with the person."""
    from tracker.filer import MARKED_MISSING, mark_missing_again, received_for
    from tracker.layout import root_of
    from tracker.manifest import Status
    from tracker.reminder import draft_reminder
    from tracker.scanner import REGRESSION_NOTE

    engagement = _consolidated_return(tmp_path)
    copies_before = sorted((engagement / PREPARED_DIR_NAME).rglob("*.pdf"))

    result = mark_missing_again(engagement, "Schwab 2025 1099.pdf", "A02",
                                note="no interest detail", today=DAY2)
    assert result.scan_note == ""
    [row] = [r for r in read_index(engagement) if r.decision == FILED]
    assert row.identifier == "E01" and row.answers == "A04 (1099-misc)"
    assert row.reason.endswith(MARKED_MISSING.format(
        identifier="A02", date=DAY2.isoformat(), note=" (no interest detail)"))
    assert len(events_named(engagement, ledger.ANSWER_WITHDRAWN_BY_PERSON)) == 1
    assert sorted((engagement / PREPARED_DIR_NAME).rglob("*.pdf")) == copies_before

    a02 = _status(engagement, "A02")
    assert a02.status == Status.MISSING
    assert a02.validation_notes.startswith(REGRESSION_NOTE.split(" {date}")[0].format(
        status=Status.RECEIVED))
    assert _status(engagement, "A04").status == Status.RECEIVED
    assert _status(engagement, "E01").status == Status.RECEIVED
    assert "A02" in draft_reminder(engagement, today=DAY2).asked
    assert "A02" not in {line.identifier for line in received_for([engagement]).lines}

    with pytest.raises(FilingError, match="does not answer A02"):
        mark_missing_again(engagement, "Schwab 2025 1099.pdf", "A02", today=DAY2)

    root = root_of(engagement)
    db = os.environ[store.ENV_STORE]
    store.close()
    os.unlink(db)
    fresh = store.connect()
    store.rebuild_engagement(fresh, root, engagement)
    assert [r.answers for r in read_index(engagement) if r.decision == FILED] == ["A04 (1099-misc)"]
    assert store.check(fresh, root, engagement) == []


def test_unfiling_the_statement_takes_its_answers_with_it(tmp_path):
    """d146. The answers are the filed row's: unfile the statement and its
    row parks with no answers, so A02 and A04 go back to what their own
    folders hold rather than staying Received on a document in review."""
    from tracker.filer import unfile_document
    from tracker.manifest import Status

    engagement = _consolidated_return(tmp_path)
    unfile_document(engagement, "Schwab 2025 1099.pdf", today=DAY2)
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.answers == ""
    assert _status(engagement, "A02").status == Status.MISSING
    assert _status(engagement, "A04").status == Status.MISSING


# ------------- a name a row still names is taken (decision 147, ruling 9) ----
# The one numbering function counts a name as taken when the disk holds it
# or a row of the household-year names it as its original's resting place,
# wherever it is used: the inbox move (above), a filing's second move into
# another household (decision 129) and a person's hand-over (decision 132)
# - both in test_a_filing_never_takes_a_name_a_vanished_original_left_behind
# - and what is taken out of an email or a zip (decision 143).

def test_the_one_numbering_function_takes_a_name_a_row_still_names(tmp_path):
    from tracker.filer import _unique_path

    folder = tmp_path / "2025"
    folder.mkdir()
    gone = folder / "W2.pdf"                                    # a row names it; the file is gone
    assert _unique_path(folder, "W2.pdf", recorded={gone: "a" * 64}, digest="b" * 64).name == "W2 (2).pdf"
    # The row's own bytes are no exception since decision 157: they go home
    # through _put_back_home, which writes no new row, and never here.
    assert _unique_path(folder, "W2.pdf", recorded={gone: "a" * 64}, digest="a" * 64).name == "W2 (2).pdf"
    # A row with no fingerprint is nobody's (decision 65): its name stays taken.
    assert _unique_path(folder, "W2.pdf", recorded={gone: ""}, digest="").name == "W2 (2).pdf"
    # The digest is asked for only when a file on the disk might be reused.
    asked = []
    assert _unique_path(folder, "W2.pdf", recorded={gone: "a" * 64},
                        digest=lambda: asked.append(1) or "a" * 64).name == "W2 (2).pdf"
    assert asked == []


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
    target, _digest = _take_out(folder, new, set(), recorded={gone: "a" * 64})
    assert target.name == "W2 (2).pdf" and target.read_bytes() == new.data
    same = Attachment("W2.pdf", b"%PDF-1.4 the row's own")
    own = hashlib.sha256(same.data).hexdigest()
    target, _digest = _take_out(folder, same, set(), recorded={gone: own})
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
    import tracker.filer as filer_module

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
    monkeypatch.setattr(filer_module, "is_cloud_placeholder", lambda p: p == waiting or real(p))
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


def _only_the_review_folder(engagement) -> None:
    """No folder per request (decision 168): the one folder inside Prepared
    is the review folder."""
    folders = [p.name for p in (engagement / PREPARED_DIR_NAME).iterdir() if p.is_dir()]
    assert folders == [REVIEW_DIR_NAME], folders


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
    assert store.check(fresh, root, engagement) == []


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


def test_a_copy_already_there_is_reused_only_under_its_own_request(engagement):
    """Every request's copies share Prepared (decision 168), so the check
    for a killed run's copy looks only among the request's own: decision
    94's page filed under A01 and C01 has the same bytes under both names,
    and C01's filing never takes A01's copy for its own."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.filer import _existing_copy, copies_of
    from tracker.validators import sha256_of

    original = drop(engagement, "scan0003.pdf",
                    "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    (entry,) = sort(engagement, today=DAY1).filed
    a01, c01 = (engagement / location for location in entry.filed_locations)
    kept = originals(engagement) / original.name
    prepared_dir = engagement / PREPARED_DIR_NAME

    c01.unlink()                                      # as if the pass was killed before it
    assert _existing_copy(prepared_dir, kept, sha256_of(kept),
                          among=copies_of(ITEMS[1], ITEMS, prepared_dir)) is None
    assert _existing_copy(prepared_dir, kept, sha256_of(kept),
                          among=copies_of(ITEMS[0], ITEMS, prepared_dir)) == a01


def test_an_also_filed_copy_is_read_back_by_its_own_name(engagement):
    """Claim 4: decision 94's two-form page counts once under each request
    in the received list, read from each copy's own name; and a copy whose
    name a person changed to one no request begins reads "Other
    document", never a guessed request."""
    from tests.conftest import seed_index
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.filer import received_for
    from tracker.records import IndexEntry
    from tracker.scaffold import OTHER_DOCUMENT

    drop(engagement, "scan0003.pdf", "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    (entry,) = sort(engagement, today=DAY1).filed
    assert [location.rsplit("/", 1)[-1] for location in entry.filed_locations] == [
        "A01 - W-2 Wage Statements - TY2025.pdf", "C01 - Mortgage Interest - TY2025.pdf"]

    labels = [line.label for line in received_for([engagement]).lines]
    assert sorted(labels) == sorted(item.label for item in ITEMS)

    seed_index(engagement, [IndexEntry(
        received="2026-07-09", original_name="combo.pdf", size_kb=12.0,
        digest="c" * 64, identifier="A01",
        prepared_location=f"{PREPARED_DIR_NAME}/A01 - W-2 Wage Statements - TY2025 (2).pdf",
        pbc_location=location_of(engagement, originals(engagement) / "combo.pdf"), decision=FILED, reason="a reason",
        also_filed=f"{PREPARED_DIR_NAME}/the 1098 I renamed.pdf")])
    labels = [line.label for line in received_for([engagement]).lines]
    assert labels.count(OTHER_DOCUMENT) == 1
    assert labels.count(ITEMS[1].label) == 1                 # only the real copy's


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


def test_a_respelled_identifier_renames_the_copies_only(engagement):
    """Claim 8: decision 160's rename, flat. Each copy the record names
    under the old identifier takes the new one at the front of its name,
    beside where it was; no folder is made, none is renamed or removed; a
    file named for the old identifier that no row names is left and
    named."""
    from tracker.filer import rename_request
    from tracker.manifest import list_head

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025 Acme Corp")
    drop(engagement, "w2 second job.pdf", "Form W-2 Wage and Tax Statement 2025 Birch LLC")
    assert len(sort(engagement, today=DAY1).filed) == 2
    prepared_dir = engagement / PREPARED_DIR_NAME
    (prepared_dir / "A01 - my own notes.pdf").write_bytes(b"a person's file")

    result = rename_request(engagement, "A01", "A1", head=list_head(engagement), today=DAY2)

    assert result.moved == 2 and result.rows == 2
    assert result.left == (f"{PREPARED_DIR_NAME}/A01 - my own notes.pdf",)
    assert sorted(p.name for p in prepared_dir.iterdir() if p.is_file()) == [
        "A01 - my own notes.pdf",
        "A1 - W-2 Wage Statements - TY2025 (2).pdf",
        "A1 - W-2 Wage Statements - TY2025.pdf",
    ]
    _only_the_review_folder(engagement)
    assert sorted(r.prepared_location for r in read_index(engagement)) == [
        f"{PREPARED_DIR_NAME}/A1 - W-2 Wage Statements - TY2025 (2).pdf",
        f"{PREPARED_DIR_NAME}/A1 - W-2 Wage Statements - TY2025.pdf",
    ]
    assert {r.identifier for r in read_index(engagement)} == {"A1"}


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

    from tests.conftest import seed_index

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


def test_room_is_measured_without_a_request_folder():
    """Claim 9: ``room_for(...).need`` for the 1040 core list under the
    firm's 28-character root is decision 144's figure (163) less the folder
    the deepest copy sat in: 138. The deepest row is still B01, whose
    folder ``B01 - Prior-Year Returns/`` was 25 characters."""
    from tracker.filer import room_for
    from tracker.layout import return_dir_for
    from tracker.manifest import label_for
    from tracker.scaffold import sanitize_component
    from tracker.templates import template_items

    root = Path("G:/Shared drives/JPA Clients")
    engagement = return_dir_for(root, "Park Family", 2026, "1040 - John & Maria Park")
    core = [replace(item, allowed_extensions=("xlsx",))
            for item in template_items("1040", core_only=True)]

    def with_a_folder(item):
        folder = label_for(sanitize_component(item.identifier), sanitize_component(item.short_name))
        return len(str(engagement / PREPARED_DIR_NAME / folder / prepared_name_for(item, "xlsx", set())))

    deepest = max(core, key=with_a_folder)
    folder = label_for(deepest.identifier, deepest.short_name) + "/"
    assert with_a_folder(deepest) == 163                        # decision 144's figure
    assert room_for(engagement, core).need == 163 - len(folder) == 138
    assert folder == "B01 - Prior-Year Returns/"


def test_an_old_return_with_request_folders_is_named_and_left_alone(engagement):
    """Claim 10, ruling 10: a return made before decision 168 has a folder
    per request. Nothing is moved or migrated, nothing in the folders is
    counted - the recorded copy there included - and the pass names each
    folder, once."""
    from tests.conftest import seed_index
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


def test_a_copy_cut_to_its_identifier_alone_still_reads_under_its_request():
    """The review of 168, N-4: decision 131's room can cut a short name away
    whole on a row with no period, leaving ``A01.pdf`` or ``A01 (2).pdf``.
    Such a copy still names its request - its stem is the identifier alone,
    or the identifier and a number - and the longest identifier wins, as it
    does for every file; a bare prefix still proves nothing."""
    from tracker.filer import _request_of_copy

    items = [RequestItem(identifier="A01", document="W-2"),
             RequestItem(identifier="A01-B", document="Loan")]
    assert _request_of_copy("A01.pdf", items) == "A01"
    assert _request_of_copy("a01 (2).pdf", items) == "A01"
    assert _request_of_copy("A01-B.pdf", items) == "A01-B"
    assert _request_of_copy("A01-B (3).pdf", items) == "A01-B"
    assert _request_of_copy("A01 - W-2 - TY2025.pdf", items) == "A01"
    assert _request_of_copy("A01x.pdf", items) == ""
    assert _request_of_copy("A01-C.pdf", items) == ""           # a bare prefix: nobody's
    assert _request_of_copy("A01B - Loan.pdf", items) == ""


def test_a_rename_refused_because_the_target_name_is_taken_moves_nothing(engagement):
    """The review of 168, N-5: every request's copies share Prepared, so a
    file nothing recorded may already hold the name a rename would give a
    copy. The rename is refused by name before anything is written: no
    copy moves, the list keeps the old identifier and the record gains no
    line."""
    from tracker.filer import RENAME_COPY_TAKEN, rename_request
    from tracker.manifest import list_head

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025 Acme Corp")
    [filed] = sort(engagement, today=DAY1).filed
    prepared_dir = engagement / PREPARED_DIR_NAME
    squatter = prepared_dir / "A1 - W-2 Wage Statements - TY2025.pdf"
    squatter.write_bytes(b"a person's own file")
    before = files_under(engagement)
    lines = len(ledger.read_events(engagement))

    with pytest.raises(FilingError) as refused:
        rename_request(engagement, "A01", "A1", head=list_head(engagement), today=DAY2)

    assert str(refused.value) == RENAME_COPY_TAKEN.format(location=location_of(engagement, squatter))
    assert files_under(engagement) == before
    assert len(ledger.read_events(engagement)) == lines
    assert [r.prepared_location for r in read_index(engagement)] == [filed.prepared_location]
    assert [i.identifier for i in load_manifest(engagement)] == ["A01", "C01"]
    assert squatter.read_bytes() == b"a person's own file"


# ------------- decision 157: a missing working copy is made again ----
# A working copy is the firm's and disposable; the client's original in
# their folder for the year is the record. So a copy that is simply gone -
# trashed on Drive's web, lost from Drive's cache, deleted by hand, the
# whole Prepared folder deleted - is made again from the original, proved
# against the row's fingerprint, and the client is never asked for a
# document the firm holds. Where the original is gone too, a person decides;
# and an original that comes back into the inbox goes home. Every case is d157.

MORTGAGE = "Form 1098 Mortgage Interest Statement 2025"


def _filed_1098(engagement, name="1098.pdf"):
    """C01's one document, sorted and scanned the ordinary way: Received."""
    from tracker.manifest import Status
    from tracker.scanner import scan_engagement

    drop(engagement, name, MORTGAGE)
    [filed] = sort(engagement, today=DAY1).filed
    scan_engagement(engagement, today=DAY1)
    assert filed.identifier == "C01" and _status(engagement, "C01").status == Status.RECEIVED
    return filed


def _a_pass(engagement, today):
    """The pass as the runner makes it: the sort, whose sweep proves every
    copy first, and then the scan."""
    from tracker.scanner import scan_engagement

    report = sort(engagement, today=today)
    return report, scan_engagement(engagement, today=today)


def _asked(engagement, today):
    from tracker.reminder import draft_reminder

    return set(draft_reminder(engagement, today=today).asked)


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
    assert store.check(store.connect(), root_of(engagement), engagement) == []

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


def test_a_copy_and_original_both_gone_is_named_not_chased(engagement):
    """d157, claim 3 (ruling B5). The copy is gone and so is the client's
    original: nothing can be made again and nothing is guessed. The row is
    File Moved with the both-gone sentence, said once; the request reads
    Missing with a firm-side note that is not decision 110's put-it-back
    wording; the letter does not ask - a person looks first. Put it back,
    keep it here and send to review each refuse in the one sentence."""
    from tracker.manifest import Status
    from tracker.reminder import draft_reminder

    filed = _filed_1098(engagement)
    (engagement / filed.prepared_location).unlink()
    (originals(engagement) / "1098.pdf").unlink()

    report, _scanned = _a_pass(engagement, DAY2)

    draft = draft_reminder(engagement, today=DAY2)
    assert "C01" not in draft.asked
    assert "C01" in {flag.item.identifier for flag in draft.needs_attention}
    from tracker.filer import (
        BOTH_GONE_SENTENCE,
        FILE_MOVED,
        NOTHING_TO_PUT_BACK,
        assign_review_file,
        both_gone,
        restore_working_copy,
        unfile_document,
    )

    sentence = BOTH_GONE_SENTENCE.format(home=filed.prepared_location, prepared=PREPARED_DIR_NAME,
                                         pbc=filed.pbc_location, date=DAY2.isoformat())
    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED and both_gone(row)
    assert row.reason == f"{filed.reason}; {sentence}"
    assert sentence in [e.error for e in report.attention]
    item = _status(engagement, "C01")
    assert item.status == Status.MISSING
    assert reasons.COPY_AND_ORIGINAL_GONE.code in item.note_code_list
    assert reasons.FILE_MOVED.code not in item.note_code_list
    assert events_named(engagement, ledger.COPY_REMADE) == []

    lines = len(ledger.read_events(engagement))
    again, _ = _a_pass(engagement, DAY3)
    assert len(ledger.read_events(engagement)) == lines         # said once
    assert sentence not in [e.error for e in again.attention]

    files = files_under(engagement)
    refusal = NOTHING_TO_PUT_BACK.format(prepared=PREPARED_DIR_NAME, pbc=filed.pbc_location)
    for answer in (lambda: restore_working_copy(engagement, filed.pbc_location, today=DAY3),
                   lambda: assign_review_file(engagement, filed.pbc_location, "C01", today=DAY3),
                   lambda: unfile_document(engagement, filed.pbc_location, today=DAY3)):
        with pytest.raises(FilingError) as refused:
            answer()
        assert str(refused.value) == refusal
    assert files_under(engagement) == files
    assert len(ledger.read_events(engagement)) == lines


def test_an_original_dragged_back_into_the_inbox_returns_to_its_place(engagement):
    """d157, claim 4 (the audit's C5). Drive undoes a refused move, or a
    colleague drags the filed 1098 back into the drop folder. It is that
    row's own original coming back, so it goes back to the very place the
    row names, as one intent, and no new row is written: the Filed row
    keeps its place and gains one sentence. The pass does not end saying
    the original is missing, and the next pass has nothing to say. Until
    157 it was filed as a Duplicate at the same place, which replaced the
    Filed row, the client's README said the 1098 never arrived, and every
    pass warned about an unrecorded copy."""
    from tracker.filer import received_for
    from tracker.manifest import Status

    filed = _filed_1098(engagement)
    original = originals(engagement) / "1098.pdf"
    body = original.read_bytes()
    original.rename(inbox_of(engagement) / "1098.pdf")

    report, _scanned = _a_pass(engagement, DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILED and report.duplicates == []
    assert original.read_bytes() == body
    assert [p.name for p in originals(engagement).iterdir()] == ["1098.pdf"]
    assert not (inbox_of(engagement) / "1098.pdf").exists()
    from tracker.filer import RETURNED_SENTENCE

    sentence = RETURNED_SENTENCE.format(drop="1098.pdf", date=DAY2.isoformat(),
                                        pbc=filed.pbc_location)
    assert row.reason == f"{filed.reason}; {sentence}"
    assert ledger_key(row) == ledger_key(filed)
    assert report.duplicates == [] and report.filed == []
    assert [e.error for e in report.attention] == [sentence]     # no MISSING_IN_PBC left behind
    assert len(events_named(engagement, ledger.ORIGINAL_RETURNED)) == 1
    assert _status(engagement, "C01").status == Status.RECEIVED
    assert "C01" in {line.identifier for line in received_for([engagement]).lines}
    assert open_intents(engagement) == []

    quiet, _ = _a_pass(engagement, DAY3)
    assert quiet.attention == [] and quiet.errors == []


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


def test_marking_a_both_gone_row_missing_asks_the_client_and_the_readme_agrees(engagement):
    """d157, ruling B6. Mark missing (decision 146's action) takes the row's
    own request, on a row whose copy and original are both gone and only
    there. The row stays on the record with the person's sentence and one
    ``answer_withdrawn_by_person`` line; it stops counting, stops holding the
    request firm-side and leaves the client's received list; the request
    reads Missing and the letter asks; the pass never makes it again or
    flags it again. The client's answer - the same bytes - is filed as a
    new arrival under a place of its own."""
    from tracker.filer import (
        MARKED_MISSING,
        REFILED_AFTER_GONE,
        mark_missing_again,
        marked_missing,
        received_for,
    )
    from tracker.manifest import Status

    filed = _filed_1098(engagement)
    with pytest.raises(FilingError, match="does not answer C01"):
        mark_missing_again(engagement, filed.pbc_location, "C01", today=DAY1)   # its copy is here
    body = (originals(engagement) / "1098.pdf").read_bytes()
    (engagement / filed.prepared_location).unlink()
    (originals(engagement) / "1098.pdf").unlink()
    _a_pass(engagement, DAY2)
    assert "C01" not in _asked(engagement, DAY2)
    assert "C01" in {line.identifier for line in received_for([engagement]).lines}

    result = mark_missing_again(engagement, filed.pbc_location, "C01", note="gone from Drive",
                                today=DAY3)

    assert result.scan_note == ""
    [row] = read_index(engagement)
    assert marked_missing(row) and row.identifier == "C01" and row.prepared_location == ""
    assert row.reason.endswith(MARKED_MISSING.format(
        identifier="C01", date=DAY3.isoformat(), note=" (gone from Drive)"))
    assert len(events_named(engagement, ledger.ANSWER_WITHDRAWN_BY_PERSON)) == 1
    item = _status(engagement, "C01")
    assert item.status == Status.MISSING and reasons.first_of(item.note_code_list) is None
    assert "C01" in _asked(engagement, DAY3)
    assert "C01" not in {line.identifier for line in received_for([engagement]).lines}
    with pytest.raises(FilingError):
        mark_missing_again(engagement, filed.pbc_location, "C01", today=DAY3)   # once is enough
    assert store.check(store.connect(), root_of(engagement), engagement) == []

    lines = len(ledger.read_events(engagement))
    quiet, _ = _a_pass(engagement, DAY3)
    assert quiet.attention == [] and len(ledger.read_events(engagement)) == lines

    (inbox_of(engagement) / "1098.pdf").write_bytes(body)            # the client answers
    report, _ = _a_pass(engagement, DAY3 + dt.timedelta(days=1))
    [again] = report.filed
    assert again.pbc_location == original_at(engagement, "1098 (2).pdf")
    assert REFILED_AFTER_GONE.format(name="1098.pdf") in again.reason
    assert read_index(engagement)[0] == row                          # the marked row is untouched
    assert _status(engagement, "C01").status == Status.RECEIVED


def test_put_it_back_on_a_filed_row_whose_copy_was_deleted_makes_it_again(engagement):
    """d157, ruling B8 (the audit's D-3: Restore refused "not a moved copy (it
    is Filed)"). Put it back on a Filed row whose copy is gone makes it
    again through the pass's own function, with the pass's sentence and
    event, decided by the person; the re-scan finds the request Received.
    A Filed row whose copy is home has nothing to put back, as before."""
    from tracker.filer import REMADE_SENTENCE, restore_working_copy
    from tracker.manifest import Status

    filed = _filed_1098(engagement)
    copy = engagement / filed.prepared_location
    copy.unlink()

    result = restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert result.copied_from_original and not result.moved_home and not result.already_home
    assert result.parked_as == "" and result.scan_note == ""
    assert copy.read_bytes() == (originals(engagement) / "1098.pdf").read_bytes()
    [row] = read_index(engagement)
    assert row.decision == FILED and row.reason == "{}; {}".format(filed.reason, REMADE_SENTENCE.format(
        home=filed.prepared_location, pbc=filed.pbc_location, date=DAY2.isoformat(),
        prepared=PREPARED_DIR_NAME))
    assert len(events_named(engagement, ledger.COPY_REMADE)) == 1
    assert events_named(engagement, ledger.RESTORED_BY_PERSON) == []
    [intent] = [e for e in events_named(engagement, ledger.MOVING)
                if e[ledger.EVENT_KEY_AFTER] == ledger.COPY_REMADE]
    assert intent[ledger.DECIDED_BY_KEY] == ledger.BY_PERSON
    assert _status(engagement, "C01").status == Status.RECEIVED
    assert open_intents(engagement) == []

    with pytest.raises(FilingError, match="is not a moved copy"):
        restore_working_copy(engagement, filed.pbc_location, today=DAY2)


def test_an_original_that_cannot_be_read_holds_the_request_and_is_never_read(
        engagement, monkeypatch):
    """d157, rulings B3 and B9. The copy is gone and the original is a
    placeholder the sync client has not brought down: it is never read
    (that would download it), nothing is made and nothing is written. The
    request is held firm-side - a missing copy is never by itself a letter
    to the client - and the pass after the original is back makes the copy."""
    import tracker.filer as filer_module
    from tracker.manifest import Status

    filed = _filed_1098(engagement)
    copy = engagement / filed.prepared_location
    copy.unlink()
    original = originals(engagement) / "1098.pdf"
    real = filer_module.is_cloud_placeholder
    monkeypatch.setattr(filer_module, "is_cloud_placeholder", lambda p: p == original or real(p))
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
    import tracker.filer as filer_module
    from tracker.manifest import Status
    from tracker.reasons import IN_CONSOLIDATED
    from tracker.scanner import ANSWER_WHY_MISSING, ANSWERED_BY, scan_engagement

    engagement = _consolidated_return(tmp_path)
    [row] = [r for r in read_index(engagement) if r.decision == FILED]
    (engagement / row.prepared_location).unlink()
    original = locate(engagement, row.pbc_location)
    real = filer_module.is_cloud_placeholder
    monkeypatch.setattr(filer_module, "is_cloud_placeholder", lambda p: p == original or real(p))

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
    assert store.SCHEMA_VERSION == 18
    live = read_index(engagement)
    root = root_of(engagement)
    assert store.check(store.connect(), root, engagement) == []
    db = os.environ[store.ENV_STORE]
    store.close()
    os.unlink(db)
    fresh = store.connect()
    store.rebuild_engagement(fresh, root, engagement)
    assert read_index(engagement) == live
    assert [ledger_key(r) for r in live] == [ledger_key(filed), ledger_key(w2)]
    assert store.check(fresh, root, engagement) == []


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


def test_the_both_gone_sentence_is_read_behind_a_persons_marks_and_never_swallowed_by_one():
    """d157. The both-gone sentence is read off the row the way decision
    109's moved sentences are, from its own template. A person's mark
    (decision 146) may sit after it or before it: after it, the sentence is
    read behind the mark; before it, the mark's note in brackets never
    swallows the sentence's own bracket. A sentence added to such a row goes
    before the moved sentence, so the row still reads as it did."""
    from tracker.filer import (
        BOTH_GONE_SENTENCE,
        FILE_MOVED,
        MARKED_MISSING,
        _before_the_moved_sentence,
        _without_moved_sentence,
        both_gone,
    )
    from tracker.records import IndexEntry

    gone = BOTH_GONE_SENTENCE.format(home=f"{PREPARED_DIR_NAME}/E01 - Brokerage - TY2025.pdf",
                                     prepared=PREPARED_DIR_NAME, pbc="../../2025/schwab.pdf",
                                     date=DAY2.isoformat())
    mark = MARKED_MISSING.format(identifier="A02", date=DAY1.isoformat(), note=" (no interest detail)")
    row = IndexEntry(received=DAY1.isoformat(), original_name="schwab.pdf", size_kb=1.0,
                     digest="a" * 64, identifier="E01",
                     prepared_location=f"{PREPARED_DIR_NAME}/E01 - Brokerage - TY2025.pdf",
                     pbc_location="../../2025/schwab.pdf", decision=FILE_MOVED,
                     reason=f"filed whole; {mark}; {gone}")
    assert both_gone(row)
    assert _without_moved_sentence(row.reason) == f"filed whole; {mark}"

    after = replace(row, reason=f"filed whole; {gone}; {mark}")
    assert both_gone(after)
    assert _without_moved_sentence(after.reason) == f"filed whole; {mark}"
    assert _before_the_moved_sentence(after.reason, "said") == f"filed whole; said; {gone}; {mark}"
    assert not both_gone(replace(after, prepared_location=""))          # marked missing
    assert not both_gone(replace(after, decision=FILED))


# Decision 180: every step an intent names stays in its return's places.


@pytest.mark.parametrize("location, writes, allowed", [
    ("Prepared/A01 - W-2/x.pdf", True, True),                                  # the return itself
    ("../_Opened/mail/x.pdf", True, True),                                     # its year's _Opened
    ("../../2024/_Opened/mail/x.pdf", False, True),                            # another year's, to read
    ("../../2024/_Opened/mail/x.pdf", True, False),                            # never to write
    ("../../../Other Household/2025/_Opened/mail/x.pdf", False, False),        # another household's
    ("../../../../Clients/Test Household/Drop files here/x.pdf", False, True),  # its inbox
    ("../../../../Clients/Test Household/Drop files here/sub/x.pdf", False, True),
    ("../../../../Clients/Test Household/2025/x.pdf", True, True),             # its year folder
    ("../../../../Clients/Other Household/2025/x.pdf", False, True),           # a feed's original
    ("../../../../Clients/Other Household/2025/x.pdf", True, False),           # never written to
    ("../../../../Clients/Test Household/x.pdf", False, False),                # beside the inbox
    ("../1040 - Someone Else/Prepared/x.pdf", False, False),                    # another return
    ("../../_ledger.jsonl", True, False),                                      # the household's record
    ("../../../../../outside/secret.pdf", False, False),                       # above the root
    ("/etc/passwd", False, False),
    ("C:/Windows/win.ini", False, False),
    ("C:x.pdf", False, False),
    ("\\\\host\\share\\x.pdf", False, False),
    ("", False, False),
])
def test_a_step_may_touch_only_its_returns_places(engagement, location, writes, allowed):
    from tracker.filer import _may_touch

    assert _may_touch(engagement, location, writes=writes) is allowed


def test_the_filer_asks_the_layout_where_a_step_may_act(engagement, monkeypatch):
    """Decision 187: the place rule has one wording, the layout's. The
    filer holds none of its own - change the layout's answer and the
    filer's changes with it."""
    import tracker.filer as filer

    asked = []

    def answer(return_dir, location, *, writes):
        asked.append((return_dir, location, writes))
        return "not-a-place"

    monkeypatch.setattr(filer, "place_problem", answer)
    assert filer._may_touch(engagement, "Prepared/x.pdf", writes=True) is False
    assert asked == [(engagement, "Prepared/x.pdf", True)]


def test_a_step_outside_its_places_moves_copies_and_removes_nothing(engagement, tmp_path):
    """The integrity review's exp6: a ``moving`` line appended to a journal
    by hand, by another machine or from a restored copy made the next
    recovery copy a file from outside the clients root into the client's
    year folder, and move another household's original away. Every step is
    now held to its return's places before anything is looked at, in the
    recovery and in the one function every step goes through."""
    from tracker.filer import OP_OUTSIDE, _do_op, _finish_the_ops
    from tracker.validators import sha256_of

    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.pdf"
    secret.write_bytes(b"%PDF-1.4 not the client's")
    digest = sha256_of(secret)
    escape = location_of(engagement, secret)
    assert escape.startswith("../")
    forged = [
        {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: escape,
         ledger.TO_KEY: "../../../../Clients/Test Household/2025/secret.pdf", ledger.DIGEST_KEY: digest},
        {ledger.OP_KEY: ledger.OP_MOVE, ledger.FROM_KEY: escape,
         ledger.TO_KEY: "Prepared/secret.pdf", ledger.DIGEST_KEY: digest},
        {ledger.OP_KEY: ledger.OP_REMOVE, ledger.FROM_KEY: escape, ledger.DIGEST_KEY: digest},
    ]
    before = sorted(p for p in tmp_path.rglob("*"))
    for op in forged:
        with pytest.raises(FilingError) as refused:
            _do_op(engagement, op)
        assert refused.value.args[0] == OP_OUTSIDE.format(name=engagement.name, location=escape,
                                                           reason="not-a-place")
        with pytest.raises(FilingError):
            _finish_the_ops(engagement, [op], None)
    assert sorted(p for p in tmp_path.rglob("*")) == before
    assert secret.read_bytes() == b"%PDF-1.4 not the client's"


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

    from tests.samples import text_pdf
    from tracker import store
    from tracker.filer import hand_over

    a = make_engagement(tmp_path, ITEMS, year=2025, return_name="1040 - A")
    b = make_engagement(tmp_path, ITEMS, year=2024, return_name="1040 - B")
    page = text_pdf(tmp_path / "page.pdf", ["Form W-2 Wage and Tax Statement 2025", "nobody"])
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


def test_a_recovery_never_copies_an_original_the_row_names_outside_its_places(engagement, tmp_path):
    """The cloud branch's own review of decision 180: the recovery's copy to act on read the
    row's own original, not a step, so an intent whose row named a file
    outside the clients root had that file copied into Needs Review. The
    row's original is held to the same places as a step's source."""
    from tracker.filer import _intend
    from tracker.locking import engagement_lock
    from tracker.records import IndexEntry, entry_to_json, ledger_key
    from tracker.validators import sha256_of

    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.pdf"
    secret.write_bytes(b"%PDF-1.4 not the client's")
    digest = sha256_of(secret)
    row = IndexEntry(received="2026-07-01", original_name="secret.pdf", size_kb=0.1, digest=digest,
                     identifier="A01", prepared_location="Prepared/A01/W-2.pdf",
                     pbc_location=location_of(engagement, secret), decision=FILED, reason="filed")
    lost = [{ledger.OP_KEY: ledger.OP_COPY,
             ledger.FROM_KEY: "../../../../Clients/Test Household/2025/nothing.pdf",
             ledger.TO_KEY: row.prepared_location, ledger.DIGEST_KEY: digest}]
    # Since decision 187 the store refuses to record such a row at all, so
    # the line is forged into the journal as a restored copy would be - and
    # the gate refuses it before the recovery reads a word of it.
    journal = ledger.path_for(engagement)
    honest = journal.read_bytes()
    with engagement_lock(engagement):
        with pytest.raises(store.StoreError, match="outside this return's places"):
            _intend(engagement, ledger_key(row), lost, by=ledger.BY_PASS, row=entry_to_json(row),
                    then=ledger.PARKED)
        assert journal.read_bytes() == honest
    # Forged as another machine's line (decision 159): one appended here,
    # past the store, would be refused first as a line claiming this
    # machine that this machine did not write.
    _forge_line(engagement, ledger.new(ledger.MOVING, **{
        ledger.KEY_KEY: ledger_key(row), ledger.OPS_KEY: lost, ledger.DECIDED_BY_KEY: ledger.BY_PASS,
        ledger.ROW_KEY: entry_to_json(row), ledger.EVENT_KEY_AFTER: ledger.PARKED}))

    with pytest.raises(store.StoreError, match="outside this return's places"):
        sort(engagement, today=DAY2)

    copies = [path for path in (engagement / "Prepared").rglob("*") if path.is_file()]
    assert not any(path.read_bytes() == secret.read_bytes() for path in copies)
    # The recovery's own check stands behind the gate: handed the row
    # directly, it still copies nothing from outside the return's places.
    from tracker.filer import _a_copy_to_act_on
    assert _a_copy_to_act_on(engagement, row, None)[0] == ""
    journal.write_bytes(honest)


# Decision 187: the record is untrusted input - every place and link is
# checked before a step is obeyed, and every copy is proved.


def _forge_line(engagement, event: dict) -> bytes:
    """Put one line in the journal past the store, as another machine
    would; returns the journal as it was. Linked to the line before
    (decision 159), so it is the store's admission and the filer's own
    checks that judge it, not the ledger's link."""
    from tests.conftest import written_elsewhere

    honest = ledger.path_for(engagement).read_bytes()
    written_elsewhere(engagement, event)
    return honest


def _elsewhere(tmp_path, name="elsewhere"):
    """A folder a junction may point at, holding one file of its own."""
    folder = tmp_path.parent / f"{tmp_path.name}-{name}"
    folder.mkdir()
    (folder / "x.pdf").write_bytes(b"%PDF-1.4 somebody else's file")
    return folder


FORGED = ["absolute", "climb", "link", "removal-behind-a-link", "removal-of-an-original"]


@pytest.mark.parametrize("which", FORGED)
def test_a_forged_step_is_carried_out_nowhere(engagement, tmp_path, which):
    """The ruling's first proof, one forged ``moving`` line per step, every
    digest right (the review's S5): a copy from an absolute path, a move
    whose ``to`` climbs into another household's inbox, a copy out of the
    return's own Prepared folder reached through a link, a removal behind
    that link (M3) and a removal of the client's own original (M4). The
    pass refuses each - at the gate, or where the recovery would carry it
    out - and nothing on disk changes; handed straight to the one function
    every step goes through, each is refused too."""
    from tracker.filer import OP_OUTSIDE, MovedThroughALinkError, _do_op
    from tracker.layout import CLIENTS_TREE, INBOX_DIR_NAME
    from tracker.registry import discover_engagements
    from tracker.runner import RECORD_UNREADABLE, run_registry
    from tracker.validators import sha256_of

    secret = _elsewhere(tmp_path, "outside") / "x.pdf"
    original = originals(engagement) / "w2.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"%PDF-1.4 the client's W-2")
    behind = _elsewhere(tmp_path)
    _link_to(behind, engagement / PREPARED_DIR_NAME / "linked")
    other_inbox = root_of(engagement) / CLIENTS_TREE / "Other Household" / INBOX_DIR_NAME
    climbing = location_of(engagement, other_inbox / "w2.pdf")
    step, refusal = {
        "absolute": ({ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: secret.as_posix(),
                      ledger.TO_KEY: f"{PREPARED_DIR_NAME}/secret.pdf", ledger.DIGEST_KEY: sha256_of(secret)},
                     OP_OUTSIDE.format(name=engagement.name, location=secret.as_posix(), reason="absolute")),
        "climb": ({ledger.OP_KEY: ledger.OP_MOVE, ledger.FROM_KEY: location_of(engagement, original),
                   ledger.TO_KEY: climbing, ledger.DIGEST_KEY: sha256_of(original)},
                  OP_OUTSIDE.format(name=engagement.name, location=climbing, reason="other-household")),
        "link": ({ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: f"{PREPARED_DIR_NAME}/linked/x.pdf",
                  ledger.TO_KEY: location_of(engagement, originals(engagement) / "x.pdf"),
                  ledger.DIGEST_KEY: sha256_of(behind / "x.pdf")}, MovedThroughALinkError),
        "removal-behind-a-link": ({ledger.OP_KEY: ledger.OP_REMOVE,
                                   ledger.FROM_KEY: f"{PREPARED_DIR_NAME}/linked/x.pdf",
                                   ledger.DIGEST_KEY: sha256_of(behind / "x.pdf")}, MovedThroughALinkError),
        "removal-of-an-original": ({ledger.OP_KEY: ledger.OP_REMOVE,
                                    ledger.FROM_KEY: location_of(engagement, original),
                                    ledger.DIGEST_KEY: sha256_of(original)},
                                   OP_OUTSIDE.format(name=engagement.name,
                                                     location=location_of(engagement, original),
                                                     reason="client-tree")),
    }[which]
    from tracker.runner import PASS_ORDER_FILENAME

    def _tree() -> list:
        # The pass's own order hint (decision 189) is its bookkeeping, not a step.
        return sorted(p for p in tmp_path.rglob("*") if p.name != PASS_ORDER_FILENAME)

    before = _tree()
    honest = _forge_line(engagement, ledger.new(ledger.MOVING, **{
        ledger.KEY_KEY: "forged", ledger.OPS_KEY: [step], ledger.DECIDED_BY_KEY: ledger.BY_PASS}))

    report = run_registry(discover_engagements(tmp_path), today=DAY1)

    (run,) = [one for one in report.runs if one.engagement.path == engagement]
    if isinstance(refusal, str):                     # refused at the gate, by the place rule
        assert run.error.startswith(RECORD_UNREADABLE.split("{")[0])
        assert "outside this return's places" in run.error
    else:                                            # admitted, and refused where it is carried out
        # Since decision 189 a run's error is said as its class (principle 7).
        assert run.error == MovedThroughALinkError.__name__
    ledger.path_for(engagement).write_bytes(honest)
    assert _tree() == before
    assert (behind / "x.pdf").is_file() and original.is_file()

    if isinstance(refusal, str):
        with pytest.raises(FilingError) as refused:
            _do_op(engagement, step)
        assert refused.value.args[0] == refusal
    else:
        with pytest.raises(refusal):
            _do_op(engagement, step)
    assert _tree() == before
    assert original.read_bytes() == b"%PDF-1.4 the client's W-2"


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
        assert store.check(store.connect(), root_of(folder), folder) == []


def test_a_copy_through_a_link_copies_nothing(engagement, tmp_path):
    """B-11: a copy followed a junction at either end. Its source behind a
    link, or its target folder behind one, and nothing is read or written."""
    from tracker.filer import MovedThroughALinkError, _do_op
    from tracker.validators import sha256_of

    behind = _elsewhere(tmp_path)
    _link_to(behind, engagement / PREPARED_DIR_NAME / "linked")
    original = originals(engagement) / "w2.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"%PDF-1.4 the client's W-2")
    reading = {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: f"{PREPARED_DIR_NAME}/linked/x.pdf",
               ledger.TO_KEY: f"{PREPARED_DIR_NAME}/copy.pdf", ledger.DIGEST_KEY: sha256_of(behind / "x.pdf")}
    writing = {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: location_of(engagement, original),
               ledger.TO_KEY: f"{PREPARED_DIR_NAME}/linked/sub/w2.pdf", ledger.DIGEST_KEY: sha256_of(original)}

    for op in (reading, writing):
        with pytest.raises(MovedThroughALinkError, match="nothing was moved, copied or removed"):
            _do_op(engagement, op)

    assert not (engagement / PREPARED_DIR_NAME / "copy.pdf").exists()
    assert sorted(p.name for p in behind.iterdir()) == ["x.pdf"]      # no folder made behind it


def test_a_removal_through_a_link_removes_nothing(engagement, tmp_path):
    from tracker.filer import MovedThroughALinkError, _do_op
    from tracker.validators import sha256_of

    behind = _elsewhere(tmp_path)
    _link_to(behind, engagement / PREPARED_DIR_NAME / "linked")
    removal = {ledger.OP_KEY: ledger.OP_REMOVE, ledger.FROM_KEY: f"{PREPARED_DIR_NAME}/linked/x.pdf",
               ledger.DIGEST_KEY: sha256_of(behind / "x.pdf")}

    with pytest.raises(MovedThroughALinkError):
        _do_op(engagement, removal)

    assert (behind / "x.pdf").is_file()


def test_a_move_into_a_linked_folder_moves_nothing(engagement, tmp_path):
    """B-11: a lexical rule cannot see a junction, so a year folder swapped
    for one would have the rename land wherever it points. The target's
    folders are asked before any is made."""
    from tracker.filer import MovedThroughALinkError, _do_op
    from tracker.validators import sha256_of

    original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    behind = _elsewhere(tmp_path)
    originals(engagement).rmdir()                     # the year's folder, swapped for a junction
    _link_to(behind, originals(engagement))
    for target in (originals(engagement) / "w2.pdf", originals(engagement) / "new" / "w2.pdf"):
        move = {ledger.OP_KEY: ledger.OP_MOVE, ledger.FROM_KEY: location_of(engagement, original),
                ledger.TO_KEY: location_of(engagement, target), ledger.DIGEST_KEY: sha256_of(original)}
        with pytest.raises(MovedThroughALinkError):
            _do_op(engagement, move)

    assert original.is_file()
    assert sorted(p.name for p in behind.iterdir()) == ["x.pdf"]
    originals(engagement).unlink()
    originals(engagement).mkdir()


def test_a_recovery_copies_no_original_behind_a_link(engagement, tmp_path):
    """A-7: the recovery's copy to act on read the row's original with no
    link check, so a year folder swapped for a junction had whatever it
    pointed at copied into Needs Review. The row's original is held to the
    link check as a step's source is."""
    from tracker.filer import MOVE_THROUGH_A_LINK, _a_copy_to_act_on
    from tracker.records import IndexEntry
    from tracker.validators import sha256_of

    behind = _elsewhere(tmp_path)
    originals(engagement).rmdir()                     # the year's folder, swapped for a junction
    _link_to(behind, originals(engagement))
    row = IndexEntry(received="2026-07-01", original_name="x.pdf", size_kb=0.1,
                     digest=sha256_of(behind / "x.pdf"), identifier="A01",
                     prepared_location=f"{PREPARED_DIR_NAME}/A01 - W-2.pdf",
                     pbc_location=location_of(engagement, originals(engagement) / "x.pdf"),
                     decision=FILED, reason="filed")

    location, said = _a_copy_to_act_on(engagement, row, None)

    assert location == ""
    assert said == MOVE_THROUGH_A_LINK.format(name="x.pdf", within=root_of(engagement))
    review = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    assert not review.exists() or not any(review.iterdir())
    originals(engagement).unlink()
    originals(engagement).mkdir()


def test_an_open_copy_with_no_digest_is_refused_where_it_is_carried_out(engagement):
    """A copy with nothing to prove it against could be anything the line
    pointed at, so it is refused before a folder is made - by the one
    function every step goes through, and by the copy itself."""
    from tracker.filer import COPY_UNPROVED, _copy_whole, _do_op

    original = originals(engagement) / "w2.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"%PDF-1.4 the client's W-2")
    target = engagement / PREPARED_DIR_NAME / "new" / "w2.pdf"
    copy = {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: location_of(engagement, original),
            ledger.TO_KEY: location_of(engagement, target), ledger.DIGEST_KEY: ""}

    with pytest.raises(FilingError) as refused:
        _do_op(engagement, copy)
    assert refused.value.args[0] == COPY_UNPROVED.format(source="w2.pdf", target="w2.pdf")
    with pytest.raises(FilingError):
        _copy_whole(original, target, expect="")
    assert not target.parent.exists()


def test_a_row_recorded_without_its_bytes_still_gets_a_proved_working_copy(engagement):
    """Decision 65's row has no digest, and its copy is still proved: the
    intent takes the fingerprint from the step that brings the original in,
    or from the original itself - and an intent with neither is never
    written."""
    from tracker.filer import COPY_UNPROVED, _do_op, _intend
    from tracker.locking import engagement_lock
    from tracker.validators import sha256_of

    dropped = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    digest = sha256_of(dropped)
    original = originals(engagement) / "w2.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    working = engagement / PREPARED_DIR_NAME / "A01 - W-2.pdf"
    ops = [
        {ledger.OP_KEY: ledger.OP_MOVE, ledger.FROM_KEY: location_of(engagement, dropped),
         ledger.TO_KEY: location_of(engagement, original), ledger.DIGEST_KEY: ""},
        {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: location_of(engagement, original),
         ledger.TO_KEY: location_of(engagement, working), ledger.DIGEST_KEY: ""},
    ]
    lines = len(ledger.read_events(engagement))

    with engagement_lock(engagement):
        _intend(engagement, location_of(engagement, original), ops, by=ledger.BY_PASS)
        (intent,) = ledger.replay(ledger.read_events(engagement)).intents.values()
        assert [op[ledger.DIGEST_KEY] for op in intent[ledger.OPS_KEY]] == ["", digest]
        for op in ops:
            _do_op(engagement, op)
        assert sha256_of(working) == digest
        ledger.append(engagement, ledger.new(ledger.MOVE_ABANDONED, key=location_of(engagement, original)))

        nowhere = [{ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: f"{PREPARED_DIR_NAME}/gone.pdf",
                    ledger.TO_KEY: f"{PREPARED_DIR_NAME}/copy.pdf", ledger.DIGEST_KEY: ""}]
        with pytest.raises(FilingError) as refused:
            _intend(engagement, "gone", nowhere, by=ledger.BY_PASS)
    assert refused.value.args[0] == COPY_UNPROVED.format(source="gone.pdf", target="copy.pdf")
    assert len(ledger.read_events(engagement)) == lines + 2


def test_a_recovery_removes_nothing_behind_a_link(engagement, tmp_path):
    """The review's M3: the recovery carries a removal out itself, not
    through _do_op, so it asks the link check of every step before it reads
    or removes a byte."""
    from tracker.filer import MovedThroughALinkError, _finish_the_ops
    from tracker.validators import sha256_of

    behind = _elsewhere(tmp_path)
    _link_to(behind, engagement / PREPARED_DIR_NAME / "linked")
    removal = {ledger.OP_KEY: ledger.OP_REMOVE, ledger.FROM_KEY: f"{PREPARED_DIR_NAME}/linked/x.pdf",
               ledger.DIGEST_KEY: sha256_of(behind / "x.pdf")}

    with pytest.raises(MovedThroughALinkError):
        _finish_the_ops(engagement, [removal], None)

    assert (behind / "x.pdf").is_file()


def test_a_removal_never_acts_in_the_client_tree(engagement):
    """The review's M4: every removal the tracker writes takes away one of
    the firm's own copies, so one naming a client's original - even in this
    return's own household and year - is refused before it is recorded."""
    from tracker.filer import OP_OUTSIDE, _intend
    from tracker.locking import engagement_lock
    from tracker.validators import sha256_of

    original = originals(engagement) / "w2.pdf"
    original.write_bytes(b"%PDF-1.4 the client's W-2")
    location = location_of(engagement, original)
    removal = {ledger.OP_KEY: ledger.OP_REMOVE, ledger.FROM_KEY: location,
               ledger.DIGEST_KEY: sha256_of(original)}
    lines = len(ledger.read_events(engagement))

    with engagement_lock(engagement), pytest.raises(FilingError) as refused:
        _intend(engagement, location, [removal], by=ledger.BY_PASS)

    assert refused.value.args[0] == OP_OUTSIDE.format(name=engagement.name, location=location,
                                                      reason="client-tree")
    assert len(ledger.read_events(engagement)) == lines and original.is_file()


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
    import tracker.filer as filer_module
    from tracker.filer import COPY_UNREAD

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    real = filer_module.sha256_of

    def unreadable(path):
        if path.parent == originals(engagement):
            raise PermissionError("held by the sync client")
        return real(path)

    monkeypatch.setattr(filer_module, "sha256_of", unreadable)
    report = sort(engagement, today=DAY1)
    monkeypatch.undo()

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.prepared_location == "" and row.digest == ""
    assert COPY_UNREAD.format(source="w2.pdf") in row.reason
    assert "checks the record" not in row.reason
    assert (originals(engagement) / "w2.pdf").is_file()
    assert [error.name for error in report.errors] == ["w2.pdf"]


def test_the_inbox_count_of_names_left_alone_skips_what_is_named_as_syncing(engagement):
    """``ignored_in_inbox`` counts what the sort leaves alone by name and
    nothing it already names (decision 190): an unfinished transfer is in
    the report by name as syncing, so it is not in the count as well, and
    the README and a real drop are neither."""
    from tracker.filer import ignored_in_inbox

    inbox = inbox_of(engagement)
    before = ignored_in_inbox(inbox)
    for name in ("desktop.ini", ".DS_Store", "~$budget.xlsx", "statement.pdf.driveupload", "w2.pdf"):
        (inbox / name).write_bytes(b"x")
    (inbox / ".tmp.drive1").mkdir()
    (inbox / ".tmp.drive1" / "w2.pdf.tmp").write_bytes(b"x")

    assert ignored_in_inbox(inbox) - before == 4
    assert ignored_in_inbox(inbox / "no such folder") == 0


# ------------------------------- decision 190: programs, names, Protected View ----


def _review_folder_files(engagement):
    review = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    return sorted(p.name for p in review.iterdir()) if review.exists() else []


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
    import tracker.filer as filer_module

    marked = []
    monkeypatch.setattr(filer_module, "mark_from_internet", lambda path: marked.append(path) or True)
    (inbox_of(engagement) / "budget.docm").write_bytes(b"PK not really a document")
    drop(engagement, "vacation.pdf", "Photos from Maui, the hotel pool and the beach at sunset")

    sort(engagement, today=DAY1)

    assert _review_folder_files(engagement) == ["budget.docm", "vacation.pdf"]
    assert len(marked) == 1 and marked[0].name.startswith("budget.docm")


def test_a_macro_copy_that_cannot_be_marked_is_not_made(engagement, monkeypatch):
    """Fail closed (decision 190): on a volume that will not hold the mark,
    no review copy is made - the drop is a "could not be filed" row the
    pass report names - and the original rests safe."""
    import tracker.filer as filer_module
    from tracker.filer import MARK_REFUSED_STEP

    def refused(path):
        raise OSError(95, "Operation not supported", str(path))

    monkeypatch.setattr(filer_module, "mark_from_internet", refused)
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


def test_no_review_copy_is_ever_named_for_a_program(tmp_path):
    """The review's M1, in depth: the one function that names a review copy
    refuses a program - whatever road asked, and whatever the row says -
    loudly, as a FilingError naming it."""
    from tracker.filer import REVIEW_OF_A_PROGRAM, _review_copy_path

    with pytest.raises(FilingError) as refused:
        _review_copy_path(tmp_path, "Pay.scr\ufeff")
    assert str(refused.value) == REVIEW_OF_A_PROGRAM.format(name="Pay.scr")
    assert list(tmp_path.iterdir()) == []


def test_a_program_sent_again_after_it_was_set_aside_parks_again_unread_with_no_copy(engagement):
    """The review's M2: a program a person set aside, sent again, is asked
    before it is read - so its name reaches no request, it gets no review
    copy and it holds nothing - and its row says it was sent again."""
    from tracker import reminder
    from tracker.filer import RESENT_AFTER_SET_ASIDE, dismiss_review_file

    program = b"MZ Form W-2 Wage and Tax Statement 2025"
    (inbox_of(engagement) / "W-2 2025.pdf.exe").write_bytes(program)
    sort(engagement, today=DAY1)
    [first] = read_index(engagement)
    dismiss_review_file(engagement, first.pbc_location)

    (inbox_of(engagement) / "W-2 2025.pdf.exe").write_bytes(program)
    sort(engagement, today=DAY2)

    again = read_index(engagement)[-1]
    assert again.decision == NEEDS_REVIEW and again.code == reasons.NOT_A_DOCUMENT.code
    assert again.prepared_location == "" and again.candidates == "" and again.evidence == ""
    assert again.reason.startswith(RESENT_AFTER_SET_ASIDE.split("{")[0])
    assert again.reason.endswith(reasons.NOT_A_DOCUMENT.template)
    assert _review_folder_files(engagement) == []
    assert reminder._parked_holds(load_manifest(engagement), [again]) == {}


def test_two_programs_in_one_zip_each_answer_to_their_own_handle(engagement):
    """The review's M3: a program taken from an email or a zip has no
    location, so its handle is its record key - unique, where "" named
    every such row at once. Setting the first aside by its handle and seq
    sets aside exactly that row, and an empty handle names none."""
    import io
    import zipfile

    from tracker.filer import NO_HANDLE, NOT_REQUESTED, dismiss_review_file, find_parked

    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        archive.writestr("invoice.js", b"WScript.Echo(1)")
        archive.writestr("payroll.exe", b"MZ")
    (inbox_of(engagement) / "docs.zip").write_bytes(packed.getvalue())
    sort(engagement, today=DAY1)

    rows = read_index(engagement)
    programs = [row for row in rows if row.code == reasons.NOT_A_DOCUMENT.code]
    assert [row.original_name for row in programs] == ["invoice.js", "payroll.exe"]
    assert all(row.pbc_location == "" for row in programs)
    handles = [ledger_key(row) for row in programs]
    assert len(set(handles)) == 2 and "" not in handles

    seqs = store.document_seqs(store.connect(), engagement)
    result = dismiss_review_file(engagement, handles[0], seq=seqs[handles[0]])

    assert result.entry.original_name == "invoice.js"
    after = {row.original_name: row.decision for row in read_index(engagement)
             if row.code in (reasons.NOT_A_DOCUMENT.code, reasons.DISMISSED_BY_PERSON_CODE)}
    assert after == {"invoice.js": NOT_REQUESTED, "payroll.exe": NEEDS_REVIEW}
    with pytest.raises(FilingError, match=NO_HANDLE):
        find_parked(read_index(engagement), "")


@pytest.mark.parametrize("refuse", [False, True], ids=["marked", "refused"])
def test_a_macro_working_copy_moved_into_review_is_marked_or_not_moved(engagement, monkeypatch, refuse):
    """The review's S2: a working copy moved into review - a person's
    unfiling, a refused put-back - goes through the one marking path, like
    a copy made there: marked before the rename, and a mark refused moves
    nothing (fail closed)."""
    import tracker.filer as filer_module
    from tracker.filer import MarkRefusedError, _do_op, _op

    marked = []

    def mark(path):
        if refuse:
            raise OSError(95, "Operation not supported", str(path))
        marked.append(path.name)
        return True

    monkeypatch.setattr(filer_module, "mark_from_internet", mark)
    working = engagement / PREPARED_DIR_NAME / "A01 - W-2 Wage Statements.xlsm"
    working.parent.mkdir(parents=True, exist_ok=True)
    working.write_bytes(b"PK a workbook with macros")
    parked = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME / "budget.xlsm"
    move = _op(engagement, ledger.OP_MOVE, working, parked, "")

    if refuse:
        with pytest.raises(MarkRefusedError):
            _do_op(engagement, move)
        assert working.exists() and not parked.exists()
    else:
        _do_op(engagement, move)
        assert marked == [working.name] and parked.exists() and not working.exists()


def _a_filed_macro_workbook(engagement, monkeypatch):
    """A macro workbook parked, then filed under A01 by a person, with the
    mark working; returns its row."""
    import tracker.filer as filer_module
    from tracker.filer import assign_review_file

    monkeypatch.setattr(filer_module, "mark_from_internet", lambda path: True)
    (inbox_of(engagement) / "budget.xlsm").write_bytes(b"PK a workbook with macros")
    sort(engagement, today=DAY1)
    [parked] = read_index(engagement)
    assign_review_file(engagement, parked.pbc_location, "A01", today=DAY1)
    [row] = read_index(engagement)
    assert row.decision == FILED
    return row


def _refuse_the_mark(monkeypatch):
    import tracker.filer as filer_module

    def refused(path):
        raise OSError(95, "Operation not supported", str(path))

    monkeypatch.setattr(filer_module, "mark_from_internet", refused)


def test_a_refused_mark_on_an_unfile_records_nothing_and_the_next_pass_runs(engagement, monkeypatch):
    """The re-check's M-N1: unfiling a macro working copy on a volume that
    will not hold the mark is refused before anything is written down - no
    open intent, the row still Filed at its copy - so the passes after it
    run, where before every one of them raised on the intent it left."""
    from tracker.filer import MarkRefusedError, unfile_document

    row = _a_filed_macro_workbook(engagement, monkeypatch)
    _refuse_the_mark(monkeypatch)

    with pytest.raises(MarkRefusedError):
        unfile_document(engagement, row.pbc_location, today=DAY2)

    assert store.open_intents(store.connect(), engagement) == []
    assert read_index(engagement) == [row]
    assert locate(engagement, row.prepared_location).read_bytes() == b"PK a workbook with macros"
    for _ in range(2):
        report = sort(engagement, today=DAY3)
        assert report.errors == [] and report.attention == []
    assert read_index(engagement) == [row] and _review_folder_files(engagement) == []


def test_a_refused_mark_on_an_interrupted_step_is_said_once_and_the_pass_goes_on(engagement, monkeypatch):
    """The re-check's M-N1, for an intent already open: an unfiling killed
    after it was written down, finished by a pass on a volume that now
    refuses the mark. The recovery abandons it and says so once - the
    mark's own sentence - and the pass goes on; the row stays Filed at its
    copy, and the next pass has nothing to say."""
    import tracker.filer as filer_module
    from tracker.filer import INTERRUPTED_MARK_REFUSED, unfile_document

    row = _a_filed_macro_workbook(engagement, monkeypatch)

    def killed(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(filer_module, "_carry_out_a_persons_ops", killed)
    with pytest.raises(KeyboardInterrupt):
        unfile_document(engagement, row.pbc_location, today=DAY2)
    assert len(store.open_intents(store.connect(), engagement)) == 1
    monkeypatch.undo()
    _refuse_the_mark(monkeypatch)

    report = sort(engagement, today=DAY3)

    [said] = report.attention
    assert said.name == "budget.xlsm"
    assert "could not be marked as from the internet" in said.error
    assert said.error.endswith(INTERRUPTED_MARK_REFUSED)
    assert store.open_intents(store.connect(), engagement) == []
    assert read_index(engagement) == [row] and _review_folder_files(engagement) == []
    assert locate(engagement, row.prepared_location).read_bytes() == b"PK a workbook with macros"
    again = sort(engagement, today=DAY3)
    assert again.errors == [] and again.attention == []
