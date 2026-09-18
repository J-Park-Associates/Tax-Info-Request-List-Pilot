"""Tests for tracker/ledger.py - the engagement's own append-only record.

The record's main claim is not made here: it is the autouse fixture in
tests/conftest.py, which folds the record back after every test in the suite
and compares it with the index and the manifest. What is made here is the
record's own behaviour - one line per event, a torn tail nobody trips over,
the bootstrap that makes an engagement already a season old agree from its
first line, and the refusal to write a word outside the engagement lock.
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from tests.test_scanner import text_pdf
from tracker import ledger
from tracker.filer import (
    INDEX_FILENAME,
    assign_review_file,
    file_drops,
    ledger_key,
    read_index,
)
from tracker.locking import engagement_lock
from tracker.manifest import RequestItem, create_template
from tracker.scaffold import MANIFEST_FILENAME, SHARED_DIR_NAME, scaffold_engagement
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
    eng = tmp_path / "Smith Family 2025"
    eng.mkdir()
    create_template(eng / MANIFEST_FILENAME, ITEMS)
    scaffold_engagement(eng)
    return eng


def drop(engagement, name, text):
    return text_pdf(engagement / SHARED_DIR_NAME / name, text)


def lines(engagement):
    return ledger.path_for(engagement).read_bytes().split(b"\n")


def a_keyword(n: int) -> dict:
    return ledger.new(ledger.KEYWORD_LEARNED, identifier=f"A{n:02d}", keyword="lender")


# ------------------------------------------------------------ one line each ----


def test_an_append_is_one_line_and_reads_back_as_it_was_written(engagement):
    with engagement_lock(engagement):
        ledger.append(engagement, a_keyword(1))

    assert lines(engagement)[-1] == b""             # newline-terminated, nothing after it
    assert len(lines(engagement)) == 2
    events = ledger.read_events(engagement)
    assert [e[ledger.EVENT_KEY] for e in events] == [ledger.KEYWORD_LEARNED]
    assert events[0]["identifier"] == "A01" and events[0]["keyword"] == "lender"
    assert events[0][ledger.AT_KEY].endswith("Z")


def test_two_appends_are_two_lines_in_the_order_they_happened(engagement):
    with engagement_lock(engagement):
        ledger.append(engagement, a_keyword(1))
        ledger.append(engagement, a_keyword(2))

    assert len([raw for raw in lines(engagement) if raw]) == 2
    assert [e["identifier"] for e in ledger.read_events(engagement)] == ["A01", "A02"]


def test_an_append_outside_the_engagement_lock_refuses_loudly(engagement):
    with pytest.raises(ledger.LedgerError, match="engagement lock"):
        ledger.append(engagement, a_keyword(1))
    assert not ledger.path_for(engagement).exists()


def test_an_event_this_version_does_not_know_is_refused(engagement):
    with pytest.raises(ledger.LedgerError, match="not an event"):
        ledger.new("invented")
    with engagement_lock(engagement), pytest.raises(ledger.LedgerError, match="not an event"):
        ledger.append(engagement, {ledger.EVENT_KEY: "invented", ledger.AT_KEY: "now"})


# ------------------------------------------------------------------- torn ----


def test_a_torn_last_line_is_ignored_by_the_reader_and_truncated_by_the_next_append(engagement):
    with engagement_lock(engagement):
        ledger.append(engagement, a_keyword(1))
    path = ledger.path_for(engagement)
    whole = path.read_bytes()
    # A run killed mid-append: bytes with no newline after them.
    path.write_bytes(whole + b'{"event": "keyword_lear')

    assert [e["identifier"] for e in ledger.read_events(engagement)] == ["A01"]

    with engagement_lock(engagement):
        ledger.append(engagement, a_keyword(2))
    assert path.read_bytes().startswith(whole)
    assert b"keyword_lear\n" not in path.read_bytes()
    assert [e["identifier"] for e in ledger.read_events(engagement)] == ["A01", "A02"]


def test_a_line_that_is_not_an_event_in_the_middle_is_refused(engagement):
    with engagement_lock(engagement):
        ledger.append(engagement, a_keyword(1))
        ledger.append(engagement, a_keyword(2))
    path = ledger.path_for(engagement)
    whole = path.read_bytes()
    path.write_bytes(whole.replace(b'"A01"', b'"A01', 1))

    with pytest.raises(ledger.LedgerError, match="line 1"):
        ledger.read_events(engagement)
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


def test_the_statuses_are_built_up_across_the_passes_that_changed_something():
    one = ledger.new(ledger.SCANNED, statuses={"A01": {"status": "Missing"}})
    two = ledger.new(ledger.SCANNED, statuses={"A01": {"status": "Received"}})

    assert ledger.statuses([one, two]) == {"A01": {"status": "Received"}}


# ------------------------------------------------------------------- head ----


def test_the_head_changes_with_every_append_and_not_otherwise(engagement):
    assert ledger.head(engagement) == ""
    with engagement_lock(engagement):
        ledger.append(engagement, a_keyword(1))
        first = ledger.head(engagement)
        assert first and ledger.head(engagement) == first    # looking changes nothing
        ledger.append(engagement, a_keyword(2))
        assert ledger.head(engagement) != first


# -------------------------------------------------------------- the writers ----


def test_a_pass_records_what_it_filed_and_what_it_parked(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    file_drops(engagement, today=DAY1)

    events = ledger.read_events(engagement)
    names = [e[ledger.EVENT_KEY] for e in events if e[ledger.EVENT_KEY] in ledger.ROW_EVENTS]
    assert sorted(names) == [ledger.FILED, ledger.PARKED]
    folded = ledger.fold(events)
    assert folded == {ledger_key(e): asdict(e) for e in read_index(engagement / INDEX_FILENAME)}


def test_a_person_filing_a_parked_file_is_recorded_as_theirs(engagement):
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = file_drops(engagement, today=DAY1).review[0]

    assign_review_file(engagement, parked.pbc_location, "C01", keyword="lender", today=DAY2)

    names = [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)]
    assert names[-2:] == [ledger.ASSIGNED_BY_PERSON, ledger.KEYWORD_LEARNED]
    assert ledger.read_events(engagement)[-1]["keyword"] == "lender"


def test_an_engagement_with_rows_and_no_record_is_seeded_before_its_first_new_event(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
    # A folder that has been running a season: the index is full, the record
    # has not been invented yet.
    ledger.path_for(engagement).unlink()
    assert read_index(engagement / INDEX_FILENAME)

    drop(engagement, "1098.pdf", "Form 1098 Mortgage Interest Statement 2025")
    file_drops(engagement, today=DAY2)

    events = ledger.read_events(engagement)
    assert events[0][ledger.EVENT_KEY] == ledger.IMPORTED
    assert events[-1][ledger.EVENT_KEY] == ledger.FILED
    assert len(ledger.fold(events)) == len(read_index(engagement / INDEX_FILENAME)) == 2


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


# -------------------------------------------------------------------- CLI ----


def test_the_cli_prints_what_the_folder_holds(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)

    out = subprocess.run(
        [sys.executable, "-m", "tracker.ledger", str(engagement)],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    assert f"events: {len(ledger.read_events(engagement))}" in out
    assert "rows:   1" in out
    assert ledger.head(engagement) in out
