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
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from tests.conftest import make_engagement
from tests.test_scanner import text_pdf
from tracker import ledger, store
from tracker.filer import (
    ASSIGNED_BY_PERSON,
    FILED,
    assign_review_file,
    file_drops,
    ledger_key,
    read_index,
)
from tracker.locking import engagement_lock
from tracker.manifest import (
    RequestItem,
    Status,
    load_engagement_info,
    load_manifest,
    save_rules,
)
from tracker.records import rule_from_json, rule_to_json
from tracker.scaffold import SHARED_DIR_NAME
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
    return make_engagement(tmp_path / "Smith Family 2025", ITEMS)


@pytest.fixture
def bare(tmp_path):
    """A folder with no record yet, for the claims about the first line."""
    folder = tmp_path / "Bare 2025"
    folder.mkdir()
    return folder


def drop(engagement, name, text):
    return text_pdf(engagement / SHARED_DIR_NAME / name, text)


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


def row(**fields) -> dict:
    base = {"received": "2026-07-01", "original_name": "w2.pdf", "size_kb": 1.0,
            "digest": "abc", "identifier": "", "prepared_location": "",
            "pbc_location": "Shared/PBC/w2.pdf", "decision": "Needs Review",
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


# ------------------------------------------------------------------- head ----


def test_the_head_changes_with_every_append_and_not_otherwise(bare):
    assert ledger.head(bare) == ""
    with engagement_lock(bare):
        ledger.append(bare, a_keyword(1))
        first = ledger.head(bare)
        assert first and ledger.head(bare) == first    # looking changes nothing
        ledger.append(bare, a_keyword(2))
        assert ledger.head(bare) != first


# -------------------------------------------------------------- the writers ----


def test_a_pass_records_what_it_filed_and_what_it_parked(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    file_drops(engagement, today=DAY1)

    events = ledger.read_events(engagement)
    names = [e[ledger.EVENT_KEY] for e in events if e[ledger.EVENT_KEY] in ledger.ROW_EVENTS]
    assert sorted(names) == [ledger.FILED, ledger.PARKED]
    folded = ledger.fold(events)
    assert folded == {ledger_key(e): asdict(e) for e in read_index(engagement)}


def test_a_person_filing_a_parked_file_is_recorded_as_theirs(engagement):
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = file_drops(engagement, today=DAY1).review[0]

    assign_review_file(engagement, parked.pbc_location, "C01", keyword="lender", today=DAY2)

    names = [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)]
    assert names[-2:] == [ledger.ASSIGNED_BY_PERSON, ledger.KEYWORD_LEARNED]
    assert ledger.read_events(engagement)[-1]["keyword"] == "lender"


def test_a_quiet_pass_appends_no_scan(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
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
    file_drops(engagement, today=DAY2)
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
    file_drops(engagement, today=DAY1)
    drop(engagement, "1098.pdf", "Form 1098 Mortgage Interest Statement 2025")
    file_drops(engagement, today=DAY2)

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
    file_drops(engagement, today=DAY1)
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
    file_drops(engagement, today=DAY1)
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
    file_drops(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY1)

    def prior_status(report):
        return {r.item.identifier: r.prior_status for r in report.rolled}["A01"]

    assert prior_status(roll_forward(engagement)) == Status.RECEIVED


def test_the_app_shows_a_persons_filing_the_moment_they_make_it(engagement):
    from tracker import api

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = file_drops(engagement, today=DAY1).review[0]
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
    file_drops(engagement, today=DAY1)

    out = subprocess.run(
        [sys.executable, "-m", "tracker.ledger", str(engagement)],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    assert f"events: {len(ledger.read_events(engagement))}" in out
    assert "rows:     1" in out
    assert f"rules:    {len(ledger.rules(ledger.read_events(engagement)))}" in out
    assert ledger.head(engagement) in out
