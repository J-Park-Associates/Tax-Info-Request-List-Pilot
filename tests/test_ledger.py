"""Tests for tracker/ledger.py - the engagement's own append-only record.

The record's main claim is not made here: it is the autouse fixture in
tests/conftest.py, which after every test in the suite holds a store built
from nothing to what these lines fold to. What is made here is the
record's own behaviour - one line per event, a torn tail nobody trips
over, the fold that is the index's own order, and the refusal to write a
word outside the engagement lock - and that every reader answers from it.
Since decisions 103 and 104 there is no second answer to any of it: the
index, the statuses and the person's rules are the record's alone.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from tests.conftest import make_engagement, named_page, sort
from tests.test_scanner import text_pdf
from tracker import ledger, store
from tracker.filer import (
    ASSIGNED_BY_PERSON,
    FILED,
    assign_review_file,
    ledger_key,
    read_index,
)
from tracker.layout import inbox_of
from tracker.locking import engagement_lock
from tracker.manifest import (
    RequestItem,
    Status,
    load_engagement_info,
    load_manifest,
    save_rules,
)
from tracker.records import rule_from_json, rule_to_json
from tracker.scanner import scan_engagement

REPO = Path(__file__).resolve().parents[1]
DAY1 = dt.date(2026, 7, 1)
DAY2 = dt.date(2026, 7, 9)

ITEMS = [
    RequestItem(
        identifier="A01", document="W-2 Wage Statements", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("W-2",),
        date_pattern=r"(?i)\b2025\b",
    ),
    RequestItem(
        identifier="C01", document="Mortgage Interest Statement", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("1098",),
    ),
]


@pytest.fixture
def engagement(tmp_path):
    return make_engagement(tmp_path, ITEMS, household="Smith Family")


@pytest.fixture
def bare(tmp_path):
    """A folder with no record yet, for the claims about the first line."""
    folder = tmp_path / "Bare 2025"
    folder.mkdir()
    return folder


def drop(engagement, name, text):
    """One document into the household's inbox, with the return's person on
    the page - a named request files only where a name confirms (128)."""
    return text_pdf(inbox_of(engagement) / name, named_page(text))


def lines(engagement):
    return ledger.path_for(engagement).read_bytes().split(b"\n")


def a_keyword(n: int) -> dict:
    return ledger.new(ledger.KEYWORD_LEARNED, identifier=f"A{n:02d}", keyword="lender")


# ------------------------------------------------------------ one line each ----


def test_an_append_is_one_line_and_reads_back_as_it_was_written(bare):
    with engagement_lock(bare):
        ledger.append(bare, a_keyword(1))

    assert lines(bare)[-1] == b""             # newline-terminated, nothing after it
    assert len(lines(bare)) == 2
    events = ledger.read_events(bare)
    assert [e[ledger.EVENT_KEY] for e in events] == [ledger.KEYWORD_LEARNED]
    assert events[0]["identifier"] == "A01" and events[0]["keyword"] == "lender"
    assert events[0][ledger.AT_KEY].endswith("Z")


def test_two_appends_are_two_lines_in_the_order_they_happened(bare):
    with engagement_lock(bare):
        ledger.append(bare, a_keyword(1))
        ledger.append(bare, a_keyword(2))

    assert len([raw for raw in lines(bare) if raw]) == 2
    assert [e["identifier"] for e in ledger.read_events(bare)] == ["A01", "A02"]


def test_an_append_outside_the_engagement_lock_refuses_loudly(bare):
    with pytest.raises(ledger.LedgerError, match="engagement lock"):
        ledger.append(bare, a_keyword(1))
    assert not ledger.path_for(bare).exists()


def test_an_event_this_version_does_not_know_is_refused(bare):
    with pytest.raises(ledger.LedgerError, match="not an event"):
        ledger.new("invented")
    with engagement_lock(bare), pytest.raises(ledger.LedgerError, match="not an event"):
        ledger.append(bare, {ledger.EVENT_KEY: "invented", ledger.AT_KEY: "now"})


def test_sharing_confirmed_is_not_a_row_event():
    """The firm's word that a household was shared is a fact about a day,
    not a row of any index (decision 126). A reader that folded it as one
    would look for a row that was never there - which is why it sits
    beside ``draft_approved`` rather than among the row events, and why it
    needed no column anywhere."""
    assert ledger.SHARING_CONFIRMED in ledger.EVENTS
    assert ledger.SHARING_CONFIRMED not in ledger.ROW_EVENTS
    assert ledger.SHARING_CONFIRMED not in ledger.RETIRED_EVENTS
    # It carries nothing but the stamp every event carries.
    assert set(ledger.new(ledger.SHARING_CONFIRMED)) == {ledger.EVENT_KEY, ledger.AT_KEY}
    # And folding one changes nothing at all.
    before = ledger.replay([])
    after = ledger.replay([ledger.new(ledger.SHARING_CONFIRMED)])
    assert (after.rows, after.statuses, after.rules, after.household, after.intents) == (
        before.rows, before.statuses, before.rules, before.household, before.intents)


def test_a_journal_that_carries_rules_imported_still_folds_and_is_never_written_again(tmp_path):
    """The retired event of decision 103: an older journal carries it, this
    version folds it exactly as a ``rules_changed``, and refuses to write
    one by sentence - and a save after it carries only the difference."""
    import json

    from tracker.filer import ensure

    folder = tmp_path / "Older 2025"
    folder.mkdir()
    old = {
        ledger.EVENT_KEY: ledger.RULES_IMPORTED, ledger.AT_KEY: "2026-09-18T09:00:00Z",
        ledger.RULES_KEY: [rule_to_json(RequestItem(**{**rule_to_json(item), "row": n + 2}))
                           for n, item in enumerate(ITEMS)],
        ledger.REMOVED_KEY: [], ledger.INFO_KEY: {"client": "John"},
        "digest": "0" * 64,
    }
    ledger.path_for(folder).write_text(json.dumps(old, sort_keys=True) + "\n", encoding="utf-8")

    folded = ledger.replay(ledger.read_events(folder))
    assert list(folded.rules) == ["A01", "C01"] and folded.info == {"client": "John"}
    assert not hasattr(folded, "rules_digest")
    assert [i.identifier for i in load_manifest(folder)] == ["A01", "C01"]
    assert load_engagement_info(folder).client == "John"

    with pytest.raises(ledger.LedgerError, match="retired"):
        ledger.new(ledger.RULES_IMPORTED)
    ensure(folder)
    with engagement_lock(folder):
        with pytest.raises(store.StoreError, match="retired"):
            store.record(store.connect(), folder, {**old, ledger.AT_KEY: "now"})

    rows = [RequestItem(**rule_from_json(r)) for r in store.rules(store.connect(), folder)]
    saved = save_rules(folder, rows[:1], load_engagement_info(folder))
    # The old line numbered its rows the sheet's way (from 2); the first
    # save gives A01 the position the list gives it, and says so.
    assert saved.recorded and saved.changed == ("A01",) and saved.removed == ("C01",)
    assert saved.info_fields == ()
    assert [i.row for i in load_manifest(folder)] == [1]
    last = ledger.read_events(folder)[-1]
    assert last[ledger.EVENT_KEY] == ledger.RULES_CHANGED and "digest" not in last
    assert [i.identifier for i in load_manifest(folder)] == ["A01"]


# ------------------------------------------------------------------- torn ----


def test_a_torn_last_line_is_ignored_by_the_reader_and_truncated_by_the_next_append(bare):
    with engagement_lock(bare):
        ledger.append(bare, a_keyword(1))
    path = ledger.path_for(bare)
    whole = path.read_bytes()
    # A run killed mid-append: bytes with no newline after them.
    path.write_bytes(whole + b'{"event": "keyword_lear')

    assert [e["identifier"] for e in ledger.read_events(bare)] == ["A01"]

    with engagement_lock(bare):
        ledger.append(bare, a_keyword(2))
    assert path.read_bytes().startswith(whole)
    assert b"keyword_lear\n" not in path.read_bytes()
    assert [e["identifier"] for e in ledger.read_events(bare)] == ["A01", "A02"]


def test_a_line_that_is_not_an_event_in_the_middle_is_refused(bare):
    with engagement_lock(bare):
        ledger.append(bare, a_keyword(1))
        ledger.append(bare, a_keyword(2))
    path = ledger.path_for(bare)
    whole = path.read_bytes()
    path.write_bytes(whole.replace(b'"A01"', b'"A01', 1))

    with pytest.raises(ledger.LedgerError, match="line 1"):
        ledger.read_events(bare)
    path.write_bytes(whole)    # put it back: the suite's own fixture reads this folder too


# ------------------------------------------------------------------- fold ----

#: Where the original of the rows these tests write by hand sits: in
#: the household's folder for the year, which is across the two trees
#: from the return - so the location begins with ``..`` (decision 125).
A_ROW_ORIGINAL = "../../../../Clients/Smith Family/2025/w2.pdf"


def row(**fields) -> dict:
    base = {"received": "2026-07-01", "original_name": "w2.pdf", "size_kb": 1.0,
            "digest": "abc", "identifier": "", "prepared_location": "",
            "pbc_location": A_ROW_ORIGINAL, "decision": "Needs Review",
            "reason": "", "candidates": "", "evidence": ""}
    return {**base, **fields}


def test_the_fold_is_the_last_event_for_each_original():
    first = ledger.new(ledger.PARKED, key="p/one", row=row(decision="Needs Review"))
    later = ledger.new(ledger.ASSIGNED_BY_PERSON, key="p/one", row=row(decision="Filed"))
    other = ledger.new(ledger.FILED, key="p/two", row=row(original_name="1098.pdf"))

    folded = ledger.fold([first, other, later])
    assert set(folded) == {"p/one", "p/two"}
    assert folded["p/one"]["decision"] == "Filed"
    assert folded["p/two"]["original_name"] == "1098.pdf"


def test_a_row_that_followed_a_moved_original_leaves_no_ghost_behind():
    first = ledger.new(ledger.PARKED, key="p/one", row=row())
    moved = ledger.new(ledger.PRESERVED, key="p/moved", was="p/one",
                       row=row(pbc_location="p/moved"))

    assert set(ledger.fold([first, moved])) == {"p/moved"}


def test_a_row_that_changed_identity_keeps_the_place_the_index_keeps_it_in():
    # The index rewrites that row where it sits; the fold is what read_index()
    # returns and what the next write rebuilds the workbook from, so a row
    # that moved to the end here would reorder the audit trail.
    one = ledger.new(ledger.PARKED, key="p/one", row=row())
    two = ledger.new(ledger.FILED, key="p/two", row=row(original_name="1098.pdf"))
    three = ledger.new(ledger.FILED, key="p/three", row=row(original_name="1099.pdf"))
    moved = ledger.new(ledger.PRESERVED, key="p/elsewhere", was="p/one",
                       row=row(pbc_location="p/elsewhere"))

    assert list(ledger.fold([one, two, three, moved])) == ["p/elsewhere", "p/two", "p/three"]


def test_the_statuses_are_built_up_across_the_passes_that_changed_something():
    one = ledger.new(ledger.SCANNED, statuses={"A01": {"status": "Missing"}})
    two = ledger.new(ledger.SCANNED, statuses={"A01": {"status": "Received"}})

    assert ledger.statuses([one, two]) == {"A01": {"status": "Received"}}


def taught(identifier: str, keyword: str) -> dict:
    return ledger.new(ledger.KEYWORD_LEARNED, **{ledger.IDENTIFIER_KEY: identifier,
                                                 ledger.KEYWORD_KEY: keyword})


def taken_back(identifier: str, keyword: str) -> dict:
    return ledger.new(ledger.KEYWORD_UNLEARNED, **{ledger.IDENTIFIER_KEY: identifier,
                                                   ledger.KEYWORD_KEY: keyword})


def test_a_learned_keyword_folds_and_an_unlearned_one_is_removed_and_learned_again_lands_last():
    """Decision 113. The fold the journal had no fold for at all until now.

    Learn appends, unlearn removes, and a word taught again lands at the
    end - which is what the store's own ``ORDER BY seq`` says, because the
    insert carries the new line's number. The two folds have to give the
    same tuple or ``store.check()`` would report a disagreement that is
    nobody's fault but the fold's.
    """
    folded = ledger.replay([
        taught("A01", "lender"), taught("A01", "escrow"), taught("C01", "tuition"),
        taken_back("A01", "lender"), taught("A01", "lender"),
    ])

    assert folded.learned == {"A01": ("escrow", "lender"), "C01": ("tuition",)}
    # A word nobody taught takes nothing back, and the last word taken back
    # leaves the request with no entry at all, as the store's rows do.
    assert ledger.replay([taught("A01", "lender"), taken_back("A01", "escrow")]).learned == {
        "A01": ("lender",)}
    assert ledger.replay([taught("A01", "lender"), taken_back("A01", "lender")]).learned == {}


def test_a_quiet_replay_has_no_learned_keywords():
    """An engagement nobody has taught anything: no entry, not an empty one."""
    assert ledger.replay([]).learned == {}
    assert ledger.replay([ledger.new(ledger.SCANNED, statuses={"A01": {"status": "Missing"}}),
                          ledger.new(ledger.PARKED, key="p/one", row=row())]).learned == {}


def test_a_word_taught_twice_folds_last_on_both_sides(tmp_path, engagement):
    """The two folds agree by construction, not because no writer teaches a
    word twice.

    The store's insert is an ``INSERT OR REPLACE`` carrying the new line's
    sequence number, so a word taught again moves to the end of
    ``ORDER BY seq``; this fold moves it to the end of the tuple for the
    same reason. Nothing in the package writes such a pair - a filing is
    refused the keyword its row already types - but a journal is read from
    a synced folder, and a fold that only held for the lines this version
    happens to write would be a disagreement the gate could not explain.
    """
    from tracker.filer import ensure

    with engagement_lock(engagement):
        ensure(engagement)
        store.record(store.connect(), engagement,
                     taught("A01", "lender"), taught("A01", "escrow"), taught("A01", "lender"))

    conn = store.connect()
    store.rebuild_engagement(conn, tmp_path, engagement)
    assert store.learned_keywords(conn, engagement) == {"a01": ("escrow", "lender")}
    assert ledger.replay(ledger.read_events(engagement)).learned == {"A01": ("escrow", "lender")}
    assert store.check(conn, tmp_path, engagement) == []


# ------------------------------------------------------------------- head ----


def test_the_head_changes_with_every_append_and_not_otherwise(bare):
    assert ledger.head(bare) == ""
    with engagement_lock(bare):
        ledger.append(bare, a_keyword(1))
        first = ledger.head(bare)
        assert first and ledger.head(bare) == first    # looking changes nothing
        ledger.append(bare, a_keyword(2))
        assert ledger.head(bare) != first


def test_the_lines_and_the_head_come_from_one_read(bare):
    """Decision 135: the store saves a head beside the lines it applied, so
    the two are one read of the file, parsed as ``read_events`` parses it and
    digested as ``head`` digests it. A torn tail is not a line and is part of
    the bytes; on a file nobody is writing the pair is the two calls."""
    assert ledger.read_with_head(bare) == ([], "") == (ledger.read_events(bare), ledger.head(bare))
    with engagement_lock(bare):
        ledger.append(bare, a_keyword(1))
        ledger.append(bare, a_keyword(2))
    assert ledger.read_with_head(bare) == (ledger.read_events(bare), ledger.head(bare))

    path = ledger.path_for(bare)
    whole = path.read_bytes()
    path.write_bytes(whole + b'{"event": "keyword_lear')
    events, head = ledger.read_with_head(bare)
    assert [e["identifier"] for e in events] == ["A01", "A02"]       # the torn tail is not a line
    assert head == hashlib.sha256(path.read_bytes()).hexdigest()      # and it is in the head
    assert head != hashlib.sha256(whole).hexdigest()
    assert (events, head) == (ledger.read_events(bare), ledger.head(bare))


# -------------------------------------------------------------- the writers ----


def test_a_pass_records_what_it_filed_and_what_it_parked(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    sort(engagement, today=DAY1)

    events = ledger.read_events(engagement)
    names = [e[ledger.EVENT_KEY] for e in events if e[ledger.EVENT_KEY] in ledger.ROW_EVENTS]
    assert sorted(names) == [ledger.FILED, ledger.PARKED]
    folded = ledger.fold(events)
    assert folded == {ledger_key(e): asdict(e) for e in read_index(engagement)}


def test_a_person_filing_a_parked_file_is_recorded_as_theirs(engagement):
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    assign_review_file(engagement, parked.pbc_location, "C01", keyword="lender", today=DAY2)

    names = [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)]
    assert names[-2:] == [ledger.ASSIGNED_BY_PERSON, ledger.KEYWORD_LEARNED]
    assert ledger.read_events(engagement)[-1]["keyword"] == "lender"


def test_a_quiet_pass_appends_no_scan(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY1)
    scanned = [e for e in ledger.read_events(engagement) if e[ledger.EVENT_KEY] == ledger.SCANNED]
    assert scanned                                   # the first scan said something

    head = ledger.head(engagement)
    scan_engagement(engagement, today=DAY1)          # nothing has changed since
    assert ledger.head(engagement) == head


def test_a_scan_that_changes_a_status_records_it(engagement):
    scan_engagement(engagement, today=DAY1)
    head = ledger.head(engagement)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY2)
    scan_engagement(engagement, today=DAY2)

    assert ledger.head(engagement) != head
    assert ledger.statuses(ledger.read_events(engagement))["A01"]["status"] == "Received"


# --------------------------------------------------------- the readers ----
#
# Decision 88: load_manifest() answered each identifier's status from the
# record wherever it had one and from a workbook wherever it had not.
# Decisions 102 to 104 left every reader with only the first of those two.
# The claims below are about which answered.


def test_the_index_is_the_record_folded_and_nothing_else(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    sort(engagement, today=DAY1)
    drop(engagement, "1098.pdf", "Form 1098 Mortgage Interest Statement 2025")
    sort(engagement, today=DAY2)

    rows = read_index(engagement)
    # The same rows, in the same order. The order is the audit trail's and
    # there is no second copy of it any more: the fold lays it and the
    # store's position column keeps it (decision 102).
    assert [asdict(e) for e in rows] == list(ledger.fold(ledger.read_events(engagement)).values())
    assert list(engagement.glob("*.xlsx")) == []


def test_a_record_holding_only_a_scan_gives_an_index_of_no_rows(engagement):
    """A scan takes the lock and records what it applied; no row event has
    been written, so the engagement has no index rows - and that is an
    answer, not a gap, because there is nowhere else a row could be."""
    scan_engagement(engagement, today=DAY1)
    events = ledger.read_events(engagement)
    assert any(e[ledger.EVENT_KEY] == ledger.SCANNED for e in events)
    assert not any(e[ledger.EVENT_KEY] in ledger.ROW_EVENTS for e in events)

    assert read_index(engagement) == []


def test_every_status_comes_from_the_record_and_nowhere_else(engagement):
    """Decision 103: there is no second reading of a status to prefer.

    A row the record has scanned answers with what it recorded; a row it
    has not is blank, because a blank is what nobody having looked at it
    means. The request itself is always the person's.
    """
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY1)
    assert ledger.statuses(ledger.read_events(engagement))["A01"]["status"] == Status.RECEIVED

    by_id = {item.identifier: item for item in load_manifest(engagement)}
    assert by_id["A01"].status == Status.RECEIVED
    assert by_id["A01"].required_keywords == ("W-2",)
    assert by_id["C01"].status == Status.MISSING     # scanned, and nothing arrived
    assert by_id["C01"].required_keywords == ("1098",)


def test_an_unreadable_record_refuses_every_reader_by_name(engagement):
    """There is one copy of what the machine decided, so a record that does
    not read as one is refused by name and the line rather than guessed
    past: answering a question about a client's documents - or about what
    they still owe - with a shrug is the thing this record exists to stop.
    """
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY1)
    path = ledger.path_for(engagement)
    whole = path.read_bytes()
    path.write_bytes(whole.replace(b'"event"', b'"even', 1))   # corruption in the middle
    store.close()                  # the rows this process already read are not the question

    with pytest.raises(ledger.LedgerError, match="line 1"):
        read_index(engagement)
    with pytest.raises(ledger.LedgerError, match="line 1"):
        load_manifest(engagement)
    with pytest.raises(ledger.LedgerError, match="line 1"):
        load_engagement_info(engagement)

    path.write_bytes(whole)        # put it back: the suite's own fixture reads this folder too


def test_the_rollover_reads_last_years_statuses_from_the_record(engagement):
    from tracker.rollover import roll_forward

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY1)

    def prior_status(report):
        return {r.item.identifier: r.prior_status for r in report.rolled}["A01"]

    assert prior_status(roll_forward(engagement)) == Status.RECEIVED


def test_the_app_shows_a_persons_filing_the_moment_they_make_it(engagement):
    from tracker import api

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)

    [row] = api._state(engagement)["index"]
    assert row["decision"] == FILED and row["identifier"] == "C01"
    # One copy, one answer: what the app shows is the row the person's
    # decision was recorded as, in the same transaction as the move.
    assert read_index(engagement)[0].reason.startswith(ASSIGNED_BY_PERSON)


# -------------------------------------------------------------------- CLI ----


def test_the_command_line_no_longer_offers_a_comparison_with_a_workbook(engagement):
    """``--compare`` went with the columns it compared (decision 103).

    There is no second copy of a status to disagree with. What is left to
    check is the store against this file, and that is
    ``python -m tracker.store <store> check <clients root>``.
    """
    refused = subprocess.run(
        [sys.executable, "-m", "tracker.ledger", str(engagement), "--compare"],
        cwd=REPO, capture_output=True, text=True,
    )
    assert refused.returncode == 2
    assert "unrecognized arguments: --compare" in refused.stderr


def test_the_cli_prints_what_the_folder_holds(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)

    out = subprocess.run(
        [sys.executable, "-m", "tracker.ledger", str(engagement)],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    assert f"events: {len(ledger.read_events(engagement))}" in out
    assert "rows:     1" in out
    assert f"rules:    {len(ledger.rules(ledger.read_events(engagement)))}" in out
    assert ledger.head(engagement) in out


def test_a_copy_moved_event_folds_as_a_row_event_in_both_folds_and_check_agrees(engagement, tmp_path):
    """Decision 109's one event, in either direction. It carries a whole row,
    so it needs no fold of its own: the generic one puts the row where the
    row it replaces was, a store built from the journal alone says the same,
    and the row's own sequence number is this line's."""
    from tracker.filer import FILE_MOVED, PREPARED_DIR_NAME, moved_to
    from tracker.scaffold import REVIEW_DIR_NAME

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    home = engagement / filed.prepared_location
    elsewhere = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    elsewhere.mkdir(parents=True, exist_ok=True)
    home.rename(elsewhere / home.name)

    sort(engagement, today=DAY2)

    events = ledger.read_events(engagement)
    assert [e[ledger.EVENT_KEY] for e in events][-1] == ledger.COPY_MOVED
    assert ledger.COPY_MOVED in ledger.ROW_EVENTS
    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED and moved_to(row)
    # The fold from the first line, and the store's line-at-a-time replay.
    assert ledger.fold(events) == {ledger_key(e): asdict(e) for e in read_index(engagement)}
    conn = store.connect()
    assert store.check(conn, tmp_path, engagement) == []
    assert conn.execute(
        "SELECT seq FROM documents WHERE key = ?", (ledger_key(row),)
    ).fetchone()[0] == len(events)                  # the row's seq is this very line's

    fresh = store.open(tmp_path / "rebuilt.db")
    try:
        store.rebuild_engagement(fresh, tmp_path, engagement)
        assert store.check(fresh, tmp_path, engagement) == []
        assert [e["decision"] for e in store.documents(fresh, engagement)] == [FILE_MOVED]
    finally:
        fresh.close()


def test_a_moving_event_folds_to_an_open_intent_and_the_row_event_that_names_its_key_closes_it(
        engagement, tmp_path, monkeypatch):
    """Decision 119's one non-row event that leaves something behind.

    Both folds keep the same open set - this module's replay from the first
    line and the store's line-at-a-time apply - so a store rebuilt from the
    journal alone finds exactly the moves a recovery has to finish, ``check``
    compares the two, and the row event that names the key closes it.
    """
    from tests.test_filer import killed_at_the_record

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    killed_at_the_record(monkeypatch)
    with pytest.raises(KeyboardInterrupt):
        sort(engagement, today=DAY1)

    events = ledger.read_events(engagement)
    open_now = ledger.replay(events).intents
    assert ledger.MOVING not in ledger.ROW_EVENTS
    assert [e[ledger.EVENT_KEY] for e in events][-1] == ledger.MOVING
    assert list(open_now) == [A_ROW_ORIGINAL]
    assert open_now == {events[-1][ledger.KEY_KEY]: events[-1]}
    assert ledger.fold(events) == {}                 # and no row yet: it was not recorded

    conn = store.connect()
    assert store.open_intents(conn, engagement) == list(open_now.values())
    assert store.check(conn, tmp_path, engagement) == []

    fresh = store.open(tmp_path / "rebuilt.db")
    try:
        store.rebuild_engagement(fresh, tmp_path, engagement)
        assert store.open_intents(fresh, engagement) == list(open_now.values())
        assert store.check(fresh, tmp_path, engagement) == []
    finally:
        fresh.close()

    sort(engagement, today=DAY2)               # the pass finishes it and records the row

    closed = ledger.read_events(engagement)
    assert ledger.replay(closed).intents == {}
    assert store.open_intents(store.connect(), engagement) == []
    assert list(ledger.fold(closed)) == [A_ROW_ORIGINAL]
    assert store.check(store.connect(), tmp_path, engagement) == []
