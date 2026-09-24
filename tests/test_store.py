"""Tests for tracker/store.py - the database on this machine, rebuilt from the record.

The store's main claim is not made here either: it is the autouse fixture
in tests/conftest.py, which builds a store for every engagement the suite
leaves behind and holds it to what the readers say. What is made here is
the store's own behaviour - the schema it refuses to guess at, the
journal-then-apply guarantee and the replay that repairs a torn one, the
rebuild that is also the recovery and takes the journal alone, the order a
row that changed identity keeps, the three words it answers its own state
in, the export, and the one placement rule: the file is never under the
clients root, because that folder syncs.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import make_engagement, named_page, seed_statuses, sort
from tests.test_scanner import text_pdf
from tracker import ledger, store
from tracker.filer import read_index
from tracker.layout import inbox_of, location_of, originals_of
from tracker.locking import engagement_lock
from tracker.manifest import (
    RequestItem,
    Status,
    load_engagement_info,
    load_manifest,
    save_rules,
)
from tracker.records import RULE_FIELDS, StatusUpdate, entry_to_json, rule_from_json

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
def root(tmp_path):
    """The clients root - the folder a cloud client syncs."""
    folder = tmp_path / "Clients"
    folder.mkdir()
    return folder


@pytest.fixture
def engagement(root):
    return make_engagement(root, ITEMS, household="Smith Family")


def original_at(engagement, name):
    """How a row names an original: relative to the return folder, POSIX,
    and across the two trees since decision 125."""
    return location_of(engagement, originals_of(engagement) / name)


@pytest.fixture
def by_hand(engagement):
    """An engagement whose record this test writes itself.

    These tests are about the store's fold, not the filer's, so they append
    rows no pass ever made - and the suite's own fixture holds every
    record to its journal. The record is removed when the test ends, the
    way the journal's own tests put back what they tore, so the folder the
    fixtures then see holds no record to check.
    """
    yield engagement
    ledger.path_for(engagement).unlink(missing_ok=True)


@pytest.fixture
def conn(tmp_path):
    """A store beside the app, which is not under the clients root."""
    connection = store.open(tmp_path / "app" / store.STORE_FILENAME)
    yield connection
    connection.close()


def drop(engagement, name, text):
    """One document into the household's inbox, with the return's person on
    the page - a named request files only where a name confirms (128)."""
    return text_pdf(inbox_of(engagement) / name, named_page(text))


def build(conn, root, engagement):
    store.rebuild_engagement(conn, root, engagement)


def edit_rules(engagement, **fields_by_identifier):
    """A person's edit of one or more rows, saved in the app as one event."""
    from dataclasses import replace

    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement)]
    edited = [replace(row, **fields_by_identifier.get(row.identifier, {})) for row in rows]
    return save_rules(engagement, edited, load_engagement_info(engagement))


def said(conn, root, engagement):
    return store.check(conn, root, engagement)


def rows(conn, table):
    return [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]


def id_of(conn, folder):
    """The store's id for one folder.

    Since decision 125 a household is a row of ``engagements`` too - the
    same table, keyed by path, with ``kind`` saying which - so a question
    about one return's rows names that return rather than reading the
    first row of a table."""
    return store._engagement_row(conn, folder)["id"]


def learned(identifier: str, keyword: str) -> dict:
    """A person's filing teaching one request one word."""
    return ledger.new(ledger.KEYWORD_LEARNED, **{ledger.IDENTIFIER_KEY: identifier,
                                                 ledger.KEYWORD_KEY: keyword})


def unlearned(identifier: str, keyword: str) -> dict:
    """A person taking one of those words back, in the editor (decision 113)."""
    return ledger.new(ledger.KEYWORD_UNLEARNED, **{ledger.IDENTIFIER_KEY: identifier,
                                                   ledger.KEYWORD_KEY: keyword})


#: How the store keys the one return these tests make: its path below the
#: clients root, in the layout of decision 125.
KEY = "J Park & Associates/Smith Family/2025/1040 - Test Client"

#: Where the original of the row these tests write by hand sits: in the
#: household's folder for the year, which is across the two trees from the
#: return - so the location begins with ``..`` (decision 125).
A_ROW_ORIGINAL = "../../../../Clients/Smith Family/2025/w2.pdf"


def a_row(**fields) -> dict:
    base = {"received": "2026-07-01", "original_name": "w2.pdf", "size_kb": 1.0,
            "digest": "abc", "identifier": "", "prepared_location": "",
            "pbc_location": A_ROW_ORIGINAL, "decision": "Needs Review",
            "reason": "", "candidates": "", "evidence": "", "also_filed": ""}
    return {**base, **fields}


# --------------------------------------------------------------- the schema ----


def test_opening_a_file_that_is_not_there_creates_the_schema(tmp_path):
    path = tmp_path / "app" / store.STORE_FILENAME
    assert not path.exists()

    conn = store.open(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION == 11
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert tables == {"engagements", "requests", "statuses", "learned_keywords",
                          "documents", "events", "intents",
                          store.VERDICTS_TABLE, store.FILE_MEMOS_TABLE}
    finally:
        conn.close()


def test_a_store_at_a_version_this_code_does_not_know_is_refused_by_name(tmp_path):
    path = tmp_path / "app" / store.STORE_FILENAME
    store.open(path).close()
    written_later = sqlite3.connect(path)
    written_later.execute(f"PRAGMA user_version = {store.SCHEMA_VERSION + 1}")
    written_later.close()

    with pytest.raises(store.StoreError) as raised:
        store.open(path)
    assert str(path) in str(raised.value) and str(store.SCHEMA_VERSION + 1) in str(raised.value)


def test_a_version_nine_store_is_refused_and_rebuilt(tmp_path):
    """Decision 107 added the verdict cache's two tables; a file from before
    it has no ``verdicts`` table, and is refused by the same sentence a
    version-1 file was - delete it and rebuild, nothing is lost.

    And so is a file at the version before this one, whatever that is
    today: decision 132 changed the fold rather than a column - a
    ``released`` line takes a row out of the index - and a version-9 file
    folded by the old code may hold ``Handed Over`` rows this version never
    produces. Rebuilt from the journals, the retired lines fold as the
    releases they meant.
    """
    path = tmp_path / "app" / store.STORE_FILENAME
    for version in (2, store.SCHEMA_VERSION - 1):
        store.open(path).close()
        written_earlier = sqlite3.connect(path)
        written_earlier.execute(f"PRAGMA user_version = {version}")
        written_earlier.close()

        with pytest.raises(store.StoreError, match=f"user_version {version}") as raised:
            store.open(path)
        assert str(path) in str(raised.value) and "delete it and rebuild" in str(raised.value)
        path.unlink()


def test_a_record_whose_type_the_store_cannot_store_is_refused_before_it_is_written():
    """A field added to a frozen record with no column form fails loudly
    rather than landing as text nothing can compare."""
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Unstorable:
        whatever: complex = 0j

    with pytest.raises(store.StoreError, match="no column form|has no column"):
        store._column_types(Unstorable)


# ------------------------------------------------------- journal then apply ----


def test_recording_outside_the_lock_writes_to_neither_the_journal_nor_the_store(
        conn, root, engagement):
    build(conn, root, engagement)
    before = ledger.path_for(engagement).read_bytes()
    events = rows(conn, "events")

    with pytest.raises(store.StoreError, match="engagement lock"):
        store.record(conn, engagement, ledger.new(
            ledger.KEYWORD_LEARNED, **{ledger.IDENTIFIER_KEY: "A01",
                                       ledger.KEYWORD_KEY: "lender"}))

    assert ledger.path_for(engagement).read_bytes() == before
    assert rows(conn, "events") == events and rows(conn, "learned_keywords") == []


def test_one_call_is_one_transaction_over_the_journal_and_the_tables(conn, root, by_hand):
    build(conn, root, by_hand)
    filed = ledger.new(ledger.FILED, key=A_ROW_ORIGINAL,
                       row=a_row(decision="Filed", identifier="A01"))
    taught = ledger.new(ledger.KEYWORD_LEARNED, **{ledger.IDENTIFIER_KEY: "A01",
                                                   ledger.KEYWORD_KEY: "lender"})

    with engagement_lock(by_hand):
        applied = store.record(conn, by_hand, filed, taught)

    assert applied == 3                                   # after the create's own line
    assert len(ledger.read_events(by_hand)) == 3
    mine = (id_of(conn, by_hand),)
    assert [row["seq"] for row in conn.execute(
        "SELECT seq FROM events WHERE engagement_id = ? ORDER BY seq", mine)] == [1, 2, 3]
    assert conn.execute(
        "SELECT decision FROM documents WHERE engagement_id = ?", mine).fetchone()[0] == "Filed"
    assert conn.execute(
        "SELECT keyword FROM learned_keywords WHERE engagement_id = ?", mine).fetchone()[0] == "lender"
    assert conn.execute(
        "SELECT applied_seq FROM engagements WHERE id = ?", mine).fetchone()[0] == 3


def test_a_failure_after_the_journal_leaves_the_store_behind_and_sync_catches_it_up(
        conn, root, by_hand, monkeypatch):
    """The journal-then-apply guarantee: the line survives, the tables lag,
    and nothing has to be reconstructed from anything but the journal."""
    build(conn, root, by_hand)
    filed = ledger.new(ledger.FILED, key="Shared/PBC/w2.pdf",
                       row=a_row(decision="Filed", identifier="A01"))

    def _died(*args, **kwargs):
        raise OSError("the machine went down between the two writes")

    monkeypatch.setattr(store, "_apply", _died)
    with engagement_lock(by_hand), pytest.raises(OSError):
        store.record(conn, by_hand, filed)

    assert len(ledger.read_events(by_hand)) == 2        # the journal holds it, after the create
    assert rows(conn, "documents") == []                   # the store does not
    monkeypatch.undo()

    assert store.sync(conn, root, by_hand) == 2
    mine = (id_of(conn, by_hand),)
    assert conn.execute(
        "SELECT decision FROM documents WHERE engagement_id = ?", mine).fetchone()[0] == "Filed"
    assert conn.execute(
        "SELECT applied_seq FROM engagements WHERE id = ?", mine).fetchone()[0] == 2
    assert store.sync(conn, root, by_hand) == 2         # and again changes nothing


def test_a_torn_last_line_is_not_replayed_until_it_is_whole(conn, root, by_hand):
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, ledger.new(
            ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed")))
    path = ledger.path_for(by_hand)
    path.write_bytes(path.read_bytes() + b'{"event": "filed", "key": "../../../../Clients/tor')

    assert store.sync(conn, root, by_hand) == 2           # the create's line and the filing
    assert len(rows(conn, "documents")) == 1


def test_recording_while_the_store_is_behind_the_journal_is_refused(conn, root, by_hand):
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        ledger.append(by_hand, ledger.new(
            ledger.FILED, key=A_ROW_ORIGINAL, row=a_row()))
        with pytest.raises(store.StoreError, match="sync"):
            store.record(conn, by_hand, ledger.new(
                ledger.FILED, key=A_ROW_ORIGINAL.replace("w2.pdf", "other.pdf"), row=a_row()))


# ------------------------------------------------------------- the rebuild ----


def test_a_rebuild_run_twice_says_and_holds_exactly_the_same(conn, root, engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    sort(engagement, today=DAY1)

    build(conn, root, engagement)
    first = (said(conn, root, engagement), rows(conn, "documents"),
             rows(conn, "requests"), rows(conn, "statuses"), rows(conn, "events"))
    build(conn, root, engagement)
    second = (said(conn, root, engagement), rows(conn, "documents"),
              rows(conn, "requests"), rows(conn, "statuses"), rows(conn, "events"))

    assert first[0] == []
    assert first == second


def test_a_reader_finding_no_rows_at_all_builds_them_from_the_journal_alone(
        conn, root, engagement):
    """What ``read_index()`` does before every read: the store is a
    derivation of the journal, so a database that has never seen this
    engagement is made to describe it without taking a lock or writing a
    byte in the folder."""
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    recorded = len(ledger.read_events(engagement))
    fresh = store.open(tmp_store(engagement))
    try:
        assert store.documents(fresh, engagement) == []

        assert store.follow_the_journal(fresh, root, engagement) == recorded

        rows = store.documents(fresh, engagement)
        assert [row["pbc_location"] for row in rows] == [
            entry.pbc_location for entry in read_index(engagement)]
        # The person's half comes back too: the create recorded the
        # request list, and an edit is a line in the journal like any
        # other (decisions 103 and 104).
        assert fresh.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == len(ITEMS)
        # And again is a digest of the journal and nothing else.
        assert store.follow_the_journal(fresh, root, engagement) == recorded
    finally:
        fresh.close()


def tmp_store(engagement: Path) -> Path:
    return engagement.parent.parent / "another" / store.STORE_FILENAME


def test_one_process_has_one_connection_and_a_second_file_is_refused(tmp_path):
    """One store per process: every writer deep in the package asks for the
    connection by name rather than being handed one, so two files open at
    once would mean two answers to the same question."""
    first = store.connect()
    assert store.connect() is first                 # the same one, not another

    with pytest.raises(store.StoreError, match="close"):
        store.connect(tmp_path / "elsewhere" / store.STORE_FILENAME)

    store.close()
    second = store.connect(tmp_path / "elsewhere" / store.STORE_FILENAME)
    assert second is not first
    store.close()


def test_the_store_is_the_one_the_environment_names(tmp_path, monkeypatch):
    """The suite gives every test its own database this way, and a person
    asking a question of a copy does the same."""
    named = tmp_path / "somewhere else" / store.STORE_FILENAME
    monkeypatch.setenv(store.ENV_STORE, str(named))
    store.close()

    assert store.store_path() == named
    store.connect().execute("SELECT 1")
    assert named.exists()
    store.close()


def test_a_row_that_changed_identity_keeps_the_place_the_index_keeps_it_in(
        conn, root, by_hand):
    """Mirrors the fold's own claim: the store's order is the index's order."""
    build(conn, root, by_hand)
    one = ledger.new(ledger.PARKED, key="p/one", row=a_row(pbc_location="p/one"))
    two = ledger.new(ledger.FILED, key="p/two", row=a_row(pbc_location="p/two"))
    three = ledger.new(ledger.FILED, key="p/three", row=a_row(pbc_location="p/three"))
    moved = ledger.new(ledger.PRESERVED, key="p/elsewhere", was="p/one",
                       row=a_row(pbc_location="p/elsewhere"))
    with engagement_lock(by_hand):
        store.record(conn, by_hand, one, two, three)
        store.record(conn, by_hand, moved)

    order = [row[0] for row in conn.execute(
        'SELECT key FROM documents ORDER BY "position"')]
    assert order == ["p/elsewhere", "p/two", "p/three"]
    assert order == list(ledger.fold(ledger.read_events(by_hand)))


# ----------------------------------------------------------------- the state ----


def test_the_state_is_current_behind_or_unknown(conn, root, by_hand):
    def now():
        return store.state(conn, by_hand, ledger_head_now=ledger.head(by_hand))

    assert store.state(conn, root / "nobody", ledger_head_now="") == store.UNKNOWN
    build(conn, root, by_hand)
    assert now() == store.CURRENT       # the journal is the whole of it

    # A person edits the request list in the app: the edit is an event,
    # recorded through the store, so the rows follow it in the same call
    # and the one stamp - the journal's head - is what says so.
    edit_rules(by_hand, A01={"any_keywords": ("lender",)})
    assert now() == store.CURRENT
    assert conn.execute(
        "SELECT ledger_head FROM engagements WHERE id = ?",
        (id_of(conn, by_hand),)).fetchone()[0] == ledger.head(by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, ledger.new(
            ledger.FILED, key="p/one", row=a_row(pbc_location="p/one")))
    assert now() == store.CURRENT                      # recorded through the store
    with engagement_lock(by_hand):
        ledger.append(by_hand, ledger.new(
            ledger.FILED, key="p/two", row=a_row(pbc_location="p/two")))
    assert now() == store.BEHIND                       # the record moved without it


# ---------------------------------------------------------------- the export ----


def test_the_export_writes_every_cell_as_text_and_a_formula_shaped_name_stays_a_name(
        conn, root, engagement, tmp_path):
    drop(engagement, "=SUM scan.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    build(conn, root, engagement)

    written = store.export(conn, tmp_path / "out")

    assert [path.name for path in written] == [
        store.DOCUMENTS_CSV, store.REQUESTS_CSV, store.ENGAGEMENTS_CSV]
    for path in written:
        raw = path.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf")         # Excel opens it as UTF-8
        assert b"\r\n" not in raw
    documents = list(csv.DictReader(
        (tmp_path / "out" / store.DOCUMENTS_CSV).read_text(encoding="utf-8-sig").splitlines()))
    assert len(documents) == 1
    # Behind an apostrophe: a spreadsheet shows the name and never runs it.
    assert documents[0]["original_name"] == "'=SUM scan.pdf"
    assert all(isinstance(value, str) for value in documents[0].values())


def test_the_export_disarms_a_request_named_like_a_command(conn, root, engagement, tmp_path):
    """A document name typed into the request list as a DDE formula reaches
    requests.csv behind an apostrophe, whatever the quoting: a spreadsheet
    evaluates a cell that begins with = + - @ or a tab on the way in."""
    edit_rules(engagement, A01={"document": "=cmd|' /C calc'!A0"})
    build(conn, root, engagement)
    store.export(conn, tmp_path / "out")
    text = (tmp_path / "out" / store.REQUESTS_CSV).read_text(encoding="utf-8-sig")
    assert "'=cmd|' /C calc'!A0" in text.replace('""', "'")
    assert not any(line.split(",")[2].startswith(('"=', "=")) for line in text.splitlines()[1:])


def test_the_export_carries_nothing_the_index_and_the_request_list_do_not(
        conn, root, engagement, tmp_path):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025 Jane Q Client")
    sort(engagement, today=DAY1)
    build(conn, root, engagement)

    store.export(conn, tmp_path / "out")

    for path in (tmp_path / "out").iterdir():
        text = path.read_text(encoding="utf-8-sig")
        # A word out of the document itself, which no reading of the index
        # or the request list ever carries.
        assert "Jane Q Client" not in text


def test_a_rebuild_from_the_journal_alone_equals_the_store(root, engagement):
    """Create, edit twice, file a drop, scan; delete the database; rebuild
    from the journal; the check says nothing and every table is what it was."""
    from tracker.scanner import scan_engagement

    edit_rules(engagement, A01={"any_keywords": ("wage statement",)})
    edit_rules(engagement, C01={"expected_count": 2}, A01={"period": "TY2025 "})
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY1)

    live = store.connect()
    before = (store.rules(live, engagement), store.statuses(live, engagement),
              store.documents(live, engagement), store.engagement_info(live, engagement))
    assert before[0] and before[1] and before[2]
    db = Path(os.environ[store.ENV_STORE])
    store.close()
    db.unlink()

    fresh = store.open(db)
    try:
        store.rebuild_engagement(fresh, root, engagement)
        assert store.check(fresh, root, engagement) == []
        assert (store.rules(fresh, engagement), store.statuses(fresh, engagement),
                store.documents(fresh, engagement), store.engagement_info(fresh, engagement)) == before
    finally:
        fresh.close()


# ----------------------------------------------------------- the verdict cache ----


def cache_rows(engagement):
    """The engagement's verdict cache as the store holds it: (memos, verdicts)."""
    from tracker.content_check import CACHE_VERSION

    return store.cached_verdicts(store.connect(), engagement, version=CACHE_VERSION)


def a_pass(engagement):
    from tracker.scanner import scan_engagement

    sort(engagement, today=DAY1)
    return scan_engagement(engagement, today=DAY1)


def test_a_rebuild_forgets_the_engagements_verdicts_and_the_next_pass_reads_again(
        root, engagement, monkeypatch):
    """The cache is not the record's (decision 107): nothing in the journal
    holds it, so a rebuild leaves the two tables empty, the check has
    nothing to say about them, and the next pass reads each document once
    and comes to the same statuses."""
    from tests.test_content_check import counting_extractor

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    before = a_pass(engagement).updates
    live = store.connect()
    memos, verdicts = cache_rows(engagement)
    assert memos and verdicts

    store.rebuild_engagement(live, root, engagement)

    assert cache_rows(engagement) == ({}, {})
    assert store.check(live, root, engagement) == []
    # The create, the one intent the filing wrote before it copied
    # (decision 119 - the move out of the inbox writes none since 125),
    # the filing itself and the scan.
    assert len(ledger.read_events(engagement)) == 4

    calls = counting_extractor(monkeypatch)
    from tracker.scanner import scan_engagement
    after = scan_engagement(engagement, today=DAY1).updates
    assert calls["n"] == 1                                    # read again, once
    assert after == before
    # Refilled with the scan's own verdicts - the working copy's memo and
    # its verdict for the row that holds it - every one the same row the
    # sort had left (the sort also kept the router's verdict for the other
    # row, which a scan of an empty folder has no cause to reach).
    refilled_memos, refilled_verdicts = cache_rows(engagement)
    assert refilled_memos == memos and refilled_verdicts
    assert all(verdicts[digest][fingerprint] == verdict
               for digest, by_fingerprint in refilled_verdicts.items()
               for fingerprint, verdict in by_fingerprint.items())


def test_the_verdict_tables_are_not_in_the_check_and_not_in_the_export(root, engagement, tmp_path):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025 Jane Q Client")
    a_pass(engagement)
    live = store.connect()
    engagement_id = store._engagement_row(live, engagement)["id"]
    stored = list(live.execute(f"SELECT digest, fingerprint, verdict FROM {store.VERDICTS_TABLE} "
                               "WHERE engagement_id = ?", (engagement_id,)))
    assert stored
    # No client text: a verdict row carries the firm's words - the keyword,
    # the Period - and never a word of the document that is not a keyword.
    for row in stored:
        assert "Jane" not in row["verdict"] and "Client" not in row["verdict"]

    assert store.check(live, root, engagement) == []
    live.execute(f"DELETE FROM {store.VERDICTS_TABLE} WHERE engagement_id = ?", (engagement_id,))
    live.execute(f"DELETE FROM {store.FILE_MEMOS_TABLE} WHERE engagement_id = ?", (engagement_id,))
    assert store.check(live, root, engagement) == []          # the check never looked
    live.execute(f"INSERT INTO {store.VERDICTS_TABLE} VALUES (?, ?, ?, ?, ?)",
                 (engagement_id, "feedface", "0123456789abcdef", 1, '{"ok": false}'))
    assert store.check(live, root, engagement) == []          # nor at a row nothing wrote

    written = store.export(live, tmp_path / "out")
    assert [path.name for path in written] == [store.DOCUMENTS_CSV, store.REQUESTS_CSV,
                                               store.ENGAGEMENTS_CSV]
    for path in written:
        text = path.read_text(encoding="utf-8-sig")
        assert "feedface" not in text and "0123456789abcdef" not in text
        assert stored[0]["fingerprint"] not in text


def test_remembering_verdicts_refuses_outside_the_lock_and_for_an_unknown_engagement(
        conn, root, engagement, tmp_path):
    from tracker.content_check import CACHE_VERSION

    build(conn, root, engagement)
    a_save = dict(version=CACHE_VERSION, memos={"k": {"size": 1, "mtime_ns": 2, "digest": "d"}},
                  verdicts={"d": {"f": {"ok": True}}}, forget_paths=set(), forget_digests=set())

    with pytest.raises(store.StoreError, match="engagement lock"):
        store.remember_verdicts(conn, engagement, **a_save)
    assert rows(conn, store.VERDICTS_TABLE) == [] and rows(conn, store.FILE_MEMOS_TABLE) == []

    stranger = tmp_path / "Clients" / "Nobody 2025"
    stranger.mkdir(parents=True)
    with engagement_lock(stranger):
        with pytest.raises(store.StoreError, match="does not hold this engagement"):
            store.remember_verdicts(conn, stranger, **a_save)
    with pytest.raises(store.StoreError, match="does not hold this engagement"):
        store.cached_verdicts(conn, stranger, version=CACHE_VERSION)

    with engagement_lock(engagement):
        store.remember_verdicts(conn, engagement, **a_save)   # the same save, held and known
    assert store.cached_verdicts(conn, engagement, version=CACHE_VERSION) == (
        {"k": {"size": 1, "mtime_ns": 2, "digest": "d"}}, {"d": {"f": {"ok": True}}})
    assert store.cached_verdicts(conn, engagement, version=CACHE_VERSION + 1) == (
        {"k": {"size": 1, "mtime_ns": 2, "digest": "d"}}, {})  # the memo is versionless


def test_the_request_tables_hold_every_field_the_request_item_has():
    """The guard the store used to make at rebuild time: a field added to
    the manifest's record and not to the tables would be dropped on the
    floor by every rebuild, and the check would go on passing because both
    sides would be missing the same value."""
    from dataclasses import fields

    assert {f.name for f in fields(RequestItem)} == set(store.RULE_COLUMNS) | set(store.STATUS_COLUMNS)
    assert tuple(store.RULE_COLUMNS) == RULE_FIELDS


def test_last_event_returns_the_newest_of_that_name_or_none(conn, root, by_hand):
    """Decision 115: what the reminder compares this week's draft with. The
    newest line of the name, as written; with ``carrying``, the newest that
    has the key; None for a name the journal never carried, and None for an
    engagement the store does not hold."""
    build(conn, root, by_hand)
    assert store.last_event(conn, by_hand, ledger.DRAFTED) is None
    assert store.last_event(conn, root / "Nobody TY2025", ledger.DRAFTED) is None

    first = ledger.new(ledger.DRAFTED, **{ledger.ASKED_KEY: ["A01"], ledger.FILE_KEY: "reminder-draft.txt",
                                          ledger.FINGERPRINT_KEY: "abc"})
    hold = ledger.new(ledger.DRAFTED, **{ledger.HELD_KEY: ["C01"]})
    taught = ledger.new(ledger.KEYWORD_LEARNED, **{ledger.IDENTIFIER_KEY: "A01",
                                                   ledger.KEYWORD_KEY: "lender"})
    with engagement_lock(by_hand):
        store.record(conn, by_hand, first, hold, taught)

    assert store.last_event(conn, by_hand, ledger.DRAFTED) == hold
    assert store.last_event(conn, by_hand, ledger.DRAFTED, carrying=ledger.FILE_KEY) == first
    assert store.last_event(conn, by_hand, ledger.DRAFTED, carrying="nothing-carries-this") is None
    assert store.last_event(conn, by_hand, ledger.KEYWORD_LEARNED) == taught
    assert store.last_event(conn, by_hand, ledger.SCANNED) is None


def test_a_failed_create_is_forgotten_and_a_retired_event_is_refused(conn, root, engagement):
    assert store.forget(conn, root / "nobody") is False
    build(conn, root, engagement)
    assert store.forget(conn, engagement) is True
    assert store.rules(conn, engagement) is None and store.forget(conn, engagement) is False
    build(conn, root, engagement)
    with engagement_lock(engagement):
        with pytest.raises(store.StoreError, match="retired"):
            store.record(conn, engagement, {ledger.EVENT_KEY: ledger.RULES_IMPORTED, ledger.AT_KEY: "now"})
    assert store.check(conn, root, engagement) == []


# ------------------------------------------------------------------- the CLI ----


def cli(*argv):
    return subprocess.run([sys.executable, "-m", "tracker.store", *[str(a) for a in argv]],
                          cwd=REPO, capture_output=True, text=True)


def test_the_command_line_builds_every_engagement_under_a_root(root, tmp_path):
    for household in ("Smith Family", "Jones Family"):
        make_engagement(root, ITEMS, household=household)
    path = tmp_path / "app" / store.STORE_FILENAME

    built = cli(path, "rebuild", root)
    assert built.returncode == 0, built.stdout + built.stderr

    conn = store.open(path)
    try:
        # Two returns and the two household records they sit under: both
        # kinds of folder are rows of this table, keyed by path, and
        # ``kind`` says which (decision 125).
        assert {row[0] for row in conn.execute(
            "SELECT path FROM engagements WHERE kind = ?", (store.KIND_RETURN,))} == {
            "J Park & Associates/Smith Family/2025/1040 - Test Client",
            "J Park & Associates/Jones Family/2025/1040 - Test Client",
        }
    finally:
        conn.close()
    assert cli(path, "check", root).returncode == 0


def test_the_command_line_builds_and_checks_the_household_records_too(root, tmp_path):
    """A household's record is a journal held in this same table, so the
    one check the runbook tells an operator to run has to reach it: a
    household row nobody compares is a row that can rot in silence."""
    from tracker.layout import private_household_dir

    for household in ("Smith Family", "Jones Family"):
        make_engagement(root, ITEMS, household=household, members=("A Person",),
                        contact="A Person", link="https://drive.example/inbox")
    path = tmp_path / "app" / store.STORE_FILENAME
    assert cli(path, "rebuild", root).returncode == 0

    conn = store.open(path)
    try:
        assert {row[0] for row in conn.execute(
            "SELECT path FROM engagements WHERE kind = ?", (store.KIND_HOUSEHOLD,))} == {
            "J Park & Associates/Smith Family",
            "J Park & Associates/Jones Family",
        }
    finally:
        conn.close()

    built = cli(path, "check", root)
    assert built.returncode == 0
    assert "agrees  Smith Family" in built.stdout          # named, not skipped

    # A household column made to say something the journal never said.
    conn = store.open(path)
    try:
        conn.execute("UPDATE engagements SET household_contact = ? WHERE kind = ?",
                     ("Somebody Else", store.KIND_HOUSEHOLD))
    finally:
        conn.close()

    disagreed = cli(path, "check", root)
    assert disagreed.returncode == 1
    assert "contact" in disagreed.stdout and "Somebody Else" in disagreed.stdout
    assert private_household_dir(root, "Smith Family").name in disagreed.stdout


def test_the_command_lines_check_exits_one_and_names_what_disagrees(root, engagement, tmp_path):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    path = tmp_path / "app" / store.STORE_FILENAME
    assert cli(path, "rebuild", root).returncode == 0
    assert cli(path, "check", root).returncode == 0

    # A row the readers give and the store has been made to forget.
    conn = store.open(path)
    try:
        conn.execute("DELETE FROM documents")
    finally:
        conn.close()

    disagreed = cli(path, "check", root)
    assert disagreed.returncode == 1
    assert "index row" in disagreed.stdout


def test_the_command_line_takes_the_app_folder_the_settings_file_or_the_store_and_refuses_a_typo(
        root, engagement, tmp_path):
    """The runbook says "the app folder"; the integration run of decision 107
    typed it and got an empty store beside the folder, because the argument
    was resolved with ``with_name``. Three spellings mean one file, and a
    typo means no file at all."""
    from tracker.settings import SETTINGS_FILENAME

    app = tmp_path / "app"                                          # where the suite's store already is
    app.mkdir(exist_ok=True)
    settings = app / SETTINGS_FILENAME
    settings.write_text("{}", encoding="utf-8")
    the_store = app / store.STORE_FILENAME

    assert store.store_named(app) == the_store
    assert store.store_named(settings) == the_store
    assert store.store_named(the_store) == the_store                # exists or not: rebuild creates it
    assert store.store_named(tmp_path / "apps") is None            # a typo of a folder
    assert store.store_named(app / f"{store.STORE_FILENAME}x") is None   # a typo of the file

    assert cli(app, "rebuild", root).returncode == 0                # the runbook's line, in fact
    assert the_store.exists()
    assert cli(settings, "check", root).returncode == 0
    assert cli(the_store, "check", root).returncode == 0

    refused = cli(tmp_path / "apps", "check", root)
    assert refused.returncode == 2 and "nothing was opened" in refused.stderr
    assert set(tmp_path.rglob(store.STORE_FILENAME)) == {the_store}  # and no store beside the typo


def test_the_command_line_says_a_refused_store_in_one_sentence(root, tmp_path):
    """A version this code does not know is refused by open() in a sentence;
    the command line repeats it and exits 1 - never a traceback."""
    path = tmp_path / "app" / store.STORE_FILENAME
    store.open(path).close()
    older = sqlite3.connect(path)
    older.execute("PRAGMA user_version = 2")
    older.close()

    refused = cli(path, "check", root)
    assert refused.returncode == 1
    assert "user_version 2" in refused.stderr and "delete it and rebuild" in refused.stderr
    assert "Traceback" not in refused.stderr and "Traceback" not in refused.stdout


# -------------------------------------------------------------- the placement ----


def test_the_store_is_placed_beside_the_settings_file_and_never_in_the_synced_folder(
        root, by_hand, tmp_path):
    settings = tmp_path / "app" / "settings.json"
    assert store.path_for(settings) == settings.with_name(store.STORE_FILENAME)
    assert root not in store.path_for(settings).parents

    conn = store.open(store.path_for(settings))
    try:
        build(conn, root, by_hand)
        with engagement_lock(by_hand):
            store.record(conn, by_hand, ledger.new(
                ledger.FILED, key="p/one", row=a_row(pbc_location="p/one")))
        # While it is open, which is when the write-ahead log exists.
        assert _database_files_under(root) == []
    finally:
        conn.close()
    assert _database_files_under(root) == []


def _database_files_under(folder: Path) -> list[str]:
    suffixes = (store.STORE_FILENAME, "-wal", "-shm", ".db")
    return sorted(path.name for path in folder.rglob("*")
                  if path.is_file() and path.name.endswith(suffixes))


# --------------------------------------------------------------- the layers ----


def test_the_store_names_no_reader_at_load_time():
    """The explicit form of the layers test's claim: nothing that walks
    folders or moves files is reachable from importing this module."""
    source = (Path(store.__file__)).read_text(encoding="utf-8")
    top, _, command_line = source.partition('if __name__ == "__main__":')
    for module in ("filer", "manifest", "view", "validators", "registry", "scaffold"):
        assert f"tracker.{module}" not in top.replace(":mod:`tracker.", "")
        assert f"tracker import {module}" not in top
    assert "from tracker import registry" in command_line      # and the CLI does reach one
    assert "filer" not in command_line                         # and no longer the filer


# ------------------------------------------------------- the readers, checked ----


def test_the_check_names_the_engagement_the_row_and_the_field(conn, root, engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    build(conn, root, engagement)
    assert said(conn, root, engagement) == []

    conn.execute("UPDATE documents SET reason = 'something else'")
    sentence = said(conn, root, engagement)[0]
    assert engagement.name in sentence and "reason" in sentence and "something else" in sentence


def test_an_engagement_the_store_has_never_seen_is_said_so_rather_than_passed(
        conn, root, engagement):
    store.forget(conn, engagement)                # the create's row, gone
    sentence = said(conn, root, engagement)
    assert len(sentence) == 1 and "does not hold this engagement" in sentence[0]


def test_an_unlearn_deletes_the_row_and_a_rebuild_from_the_journal_agrees(conn, root, by_hand):
    """Decision 113: a word taught by an event is taken back by an event.

    Deleting the row alone would be a fact only the database held, and the
    next rebuild would put it back. The journal carries the unlearn, so a
    store built from nothing agrees - and a word taught again after it
    comes back last, on both sides.
    """
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand,
                     learned("A01", "lender"), learned("A01", "escrow"),
                     unlearned("A01", "lender"))

    assert store.learned_keywords(conn, by_hand) == {"a01": ("escrow",)}
    assert said(conn, root, by_hand) == []

    with engagement_lock(by_hand):
        store.record(conn, by_hand, learned("A01", "lender"))
    assert store.learned_keywords(conn, by_hand) == {"a01": ("escrow", "lender")}

    build(conn, root, by_hand)                    # from the journal and nothing else
    assert store.learned_keywords(conn, by_hand) == {"a01": ("escrow", "lender")}
    assert said(conn, root, by_hand) == []


def test_check_reports_a_learned_keyword_in_the_store_and_not_in_the_record_and_the_other_way_round(
        conn, root, by_hand):
    """The gate reaches the learned table at last (decision 113).

    Until now it compared the documents, the statuses and the rules, and
    this table was the one thing in the store the record could not vouch
    for: a row planted or dropped behind the journal's back said nothing.
    """
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, learned("A01", "lender"))
    assert said(conn, root, by_hand) == []

    held = conn.execute("SELECT engagement_id, seq FROM learned_keywords").fetchone()
    conn.execute('INSERT INTO learned_keywords (engagement_id, "identifier", keyword, seq) '
                 "VALUES (?, ?, ?, ?)", (held["engagement_id"], "a01", "escrow", held["seq"] + 1))
    (sentence,) = said(conn, root, by_hand)
    assert by_hand.name in sentence and "a01" in sentence
    assert "'lender', 'escrow'" in sentence and "['lender']" in sentence

    conn.execute("DELETE FROM learned_keywords")
    (sentence,) = said(conn, root, by_hand)
    assert "a01" in sentence and "[]" in sentence and "['lender']" in sentence

    store.rebuild_engagement(conn, root, by_hand)
    assert said(conn, root, by_hand) == []


def test_a_malformed_unlearn_line_is_refused_by_name(conn, root, by_hand):
    """A keyword line of the wrong shape is one folder's problem, said in a
    sentence that names it - the rule every other event's shape follows.

    It is checked here for the first time with decision 113: a keyword that
    is not text was written into the table as ``str()`` made it while the
    journal's fold kept what the line carried, which is a disagreement the
    check would now report and nobody could act on.
    """
    build(conn, root, by_hand)
    path = ledger.path_for(by_hand)
    path.write_bytes(path.read_bytes() + json.dumps({
        ledger.EVENT_KEY: ledger.KEYWORD_UNLEARNED, ledger.AT_KEY: ledger.stamp(),
        ledger.IDENTIFIER_KEY: "A01", ledger.KEYWORD_KEY: 7,
    }).encode("utf-8") + b"\n")

    with pytest.raises(store.StoreError) as refused:
        store.sync(conn, root, by_hand)
    said_so = str(refused.value)
    assert ledger.KEYWORD_UNLEARNED in said_so and "line 2" in said_so
    assert repr(ledger.KEYWORD_KEY) in said_so and "not applied past it" in said_so
    # And the same shape for the event it takes back, which nothing checked
    # before: a request nobody named is refused rather than stored blank.
    with pytest.raises(store.StoreError, match="blank"):
        store._refuse_a_malformed_line(
            {ledger.EVENT_KEY: ledger.KEYWORD_LEARNED, ledger.IDENTIFIER_KEY: "",
             ledger.KEYWORD_KEY: "lender"}, 3, by_hand.name)


def test_the_rebuilt_rows_are_the_readers_rows_after_a_person_files_a_parked_one(
        conn, root, engagement):
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    assign_review_file(engagement, parked.pbc_location, "C01", keyword="lender", today=DAY2)

    build(conn, root, engagement)

    assert said(conn, root, engagement) == []
    assert conn.execute("SELECT keyword FROM learned_keywords").fetchone()[0] == "lender"
    assert conn.execute("SELECT identifier FROM documents").fetchone()[0] == "C01"


def test_every_request_the_manifest_holds_has_a_rule_in_the_store(conn, root, engagement):
    build(conn, root, engagement)

    assert conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == len(ITEMS)
    # And no status: a status is something a scan recorded, not something
    # the list carries (decision 103). An unscanned engagement has none.
    assert conn.execute("SELECT COUNT(*) FROM statuses").fetchone()[0] == 0
    stored = conn.execute('SELECT * FROM requests WHERE "identifier" = ?', ("A01",)).fetchone()
    item = next(i for i in load_manifest(engagement) if i.identifier == "A01")
    assert stored["required_keywords"] == '["W-2"]' == store._to_sql(item.required_keywords)
    assert stored["date_pattern_derived"] == int(item.date_pattern_derived)


def test_a_status_the_record_holds_is_in_the_store_and_answers_load_manifest(
        conn, root, engagement):
    seed_statuses(engagement, {"A01": StatusUpdate(
        status=Status.RECEIVED, file_count=1, received_date=DAY1)})
    build(conn, root, engagement)

    assert said(conn, root, engagement) == []
    held = conn.execute('SELECT * FROM statuses WHERE "identifier" = ?', ("a01",)).fetchone()
    assert held["status"] == Status.RECEIVED and held["file_count"] == 1
    answered = {i.identifier: i for i in load_manifest(engagement)}
    assert answered["A01"].status == Status.RECEIVED
    assert answered["A01"].received_date == DAY1
    assert answered["C01"].status == ""


def test_the_documents_table_holds_every_column_the_index_row_has(conn, root, engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    build(conn, root, engagement)

    entry = read_index(engagement)[0]
    row = conn.execute("SELECT * FROM documents").fetchone()
    for field, value in entry_to_json(entry).items():
        assert row[field] == store._to_sql(value), field


def test_a_pass_and_the_command_line_key_one_engagement_the_same_way(root, engagement):
    """The pass keys the engagement by the root it was run against; the
    command line, handed that same root, finds it - and so does a caller
    with no root at all. Found by an end-to-end run after decision 103: on
    a machine with no settings file the pass fell back to the folder's
    parent for its key and ``check`` looked the engagement up by the root
    on its command line, so ``state`` said current and ``check`` said the
    store did not hold it. One folder is one row, however it is named."""
    from tracker.manifest import Status, load_manifest
    from tracker.runner import REMINDERS_NEVER, main

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    assert main([str(root), "--reminders", REMINDERS_NEVER]) == 0
    store.close()

    db = Path(os.environ[store.ENV_STORE])
    checked = cli(db, "check", root)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "agrees" in checked.stdout
    assert "current" in cli(db, "state", root).stdout
    # and the same engagement named by a different root is still that row
    conn = store.connect()
    # One row for the return, and one for the household record above it.
    assert conn.execute("SELECT COUNT(*) FROM engagements").fetchone()[0] == 2
    assert store.check(conn, root.parent, engagement) == []
    assert next(i.status for i in load_manifest(engagement) if i.identifier == "A01") == Status.RECEIVED


@pytest.fixture
def recorded_root(root, tmp_path, monkeypatch):
    """The clients root as the office has it: named in the settings file.

    The suite's other tests run with no settings file, which is a machine
    keying by the folder's parent; these run the way the app and the
    scheduled pass do, with the record's own root written down."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    (tmp_path / "app").mkdir(exist_ok=True)
    set_clients_root(root)
    return root


def test_a_folder_nested_under_the_clients_root_is_never_another_engagement(recorded_root, engagement):
    """Decision 106. ``Clients/Archive/Smith 2025`` ends the way
    ``Clients/Smith 2025``'s key does, and the pre-integration audit of
    2026-09-19 found the store answering the one as the other: its reads
    refused the journal as truncated, and a longer journal would have been
    applied onto the other engagement's rows. Under the recorded root a
    folder is exactly one key, and a folder with no row is one the store
    has not met."""
    from tracker.manifest import load_manifest

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    conn = store.connect()
    assert store._engagement_row(conn, engagement)["path"] == KEY

    deep = recorded_root / "Archive" / KEY
    deep.mkdir(parents=True)
    assert store._engagement_row(conn, deep) is None                       # not met, never a tail
    assert store._engagement_row(conn, deep, recorded_root) is None
    assert store.state(conn, deep, ledger_head_now="") == store.UNKNOWN

    # Now it is its own return, under its own household, in a tree of its
    # own below the root: its key ends with the other's and is not it.
    nested = make_engagement(recorded_root / "Archive", ITEMS, household="Smith Family")
    assert [r["path"] for r in conn.execute(
        "SELECT path FROM engagements WHERE kind = ? ORDER BY path", (store.KIND_RETURN,))] == [
        f"Archive/{KEY}", KEY,
    ]
    assert read_index(nested) == []
    assert [e.original_name for e in read_index(engagement)] == ["w2.pdf"]
    assert store.check(conn, recorded_root, engagement) == []
    assert store.check(conn, recorded_root, nested) == []
    assert {i.identifier for i in load_manifest(nested)} == {i.identifier for i in ITEMS}


def test_a_pass_keys_one_return_the_same_way_whichever_root_is_named(recorded_root, engagement):
    """Decision 106: the root a caller has in hand is not the key when the
    settings file names one. ``check`` given the return folder, the drive
    above the root, or the recorded root keys the return exactly as the
    app and the scheduled pass do - one folder, one row, whichever root
    was named - because under the recorded root nothing but the exact key
    answers, and two spellings of one folder must never be two rows."""
    from tracker.runner import REMINDERS_NEVER, main

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    assert main([str(recorded_root), "--reminders", REMINDERS_NEVER]) == 0
    conn = store.connect()
    assert [r["path"] for r in conn.execute(
        "SELECT path FROM engagements WHERE kind = ?", (store.KIND_RETURN,))] == [KEY]
    assert store.check(conn, engagement, engagement) == []                # the narrowest root
    assert store.check(conn, recorded_root.parent, engagement) == []      # a wider one
    assert store.check(conn, recorded_root, engagement) == []             # the recorded one
    assert [e.original_name for e in read_index(engagement)] == ["w2.pdf"]
    # Two rows: this return, and the household record above it.
    assert conn.execute("SELECT COUNT(*) FROM engagements").fetchone()[0] == 2


# ------------------------------------------------- the key by position (d134) ----


def _one_filed_row(period: str):
    """One index row a pass could have written, for a return of ``period``."""
    from tracker.filer import FILED
    from tracker.records import IndexEntry

    return IndexEntry(received="2026-09-23 10:00:00", original_name="x.pdf", size_kb=5.0,
                      digest="abc", identifier="A01",
                      prepared_location="Prepared/A01 - W-2 Wages/A01 - W-2.pdf",
                      pbc_location="x.pdf", decision=FILED, reason=f"filed for {period}")


def _one_request(year: int) -> list[RequestItem]:
    return [RequestItem(identifier="A01", document="W-2 Wages", period=str(year),
                        allowed_extensions=("pdf",))]


def test_two_years_of_one_return_are_two_rows_when_the_settings_name_no_root(root, caplog):
    """Decision 134, the review of decision 130's reproduction. Rollover
    keeps a return's name every year, so ``Smith/2025/1040 - Smith`` and
    ``Smith/2026/1040 - Smith`` are the normal case. With no settings file
    and no root in hand - every reader - the key used to fall back to the
    folder's parent, which since decision 125 is the year: both were keyed
    ``1040 - Smith``, one row, and the earlier year's reads refused its own
    journal ("the store has applied 2 line(s) and the journal holds 1").
    The second symptom was the household's README: its reader could not
    read the earlier return and dropped it with a warning. Keyed by where
    it sits, each carries household, year and return, and the README reads
    both."""
    import logging

    from tests.conftest import seed_index

    caplog.set_level(logging.WARNING, logger="tracker.scaffold")
    earlier = make_engagement(root, _one_request(2025), household="Smith", year=2025,
                              return_name="1040 - Smith")
    seed_index(earlier, [_one_filed_row("2025")])
    later = make_engagement(root, _one_request(2026), household="Smith", year=2026,
                            return_name="1040 - Smith")

    assert [e.reason for e in read_index(earlier)] == ["filed for 2025"]
    assert read_index(later) == []
    assert [i.period for i in load_manifest(earlier)] == ["2025"]
    assert [i.period for i in load_manifest(later)] == ["2026"]
    assert [e.reason for e in read_index(earlier)] == ["filed for 2025"]      # and again
    conn = store.connect()
    assert [r["path"] for r in conn.execute(
        "SELECT path FROM engagements WHERE kind = ? ORDER BY path", (store.KIND_RETURN,))] == [
        "J Park & Associates/Smith/2025/1040 - Smith", "J Park & Associates/Smith/2026/1040 - Smith",
    ]
    assert store.check(conn, root, earlier) == [] and store.check(conn, root, later) == []
    assert store.key_root(earlier) == root and store.key_root(later) == root
    assert [r.getMessage() for r in caplog.records
            if r.name == "tracker.scaffold" and r.levelno >= logging.WARNING] == []


def _two_years_rebuilt_without_a_root(conn, earlier, later):
    """Both years of one return built into ``conn`` the way a reader meets
    them - no root in hand - and the return paths the store then holds."""
    store.rebuild_engagement(conn, None, earlier)
    store.rebuild_engagement(conn, None, later)
    return [r["path"] for r in conn.execute(
        "SELECT path FROM engagements WHERE kind = ? ORDER BY path", (store.KIND_RETURN,))]


def test_a_return_typed_relative_to_its_household_is_keyed_by_where_it_sits(root, tmp_path, monkeypatch):
    """The review of decision 134. A folder typed from inside the household
    (``2025/1040 - Smith``) has no private tree above it as written, so
    asked as given it fell back to the year folder and two years of one
    return were one row again. It is resolved before the layout is asked."""
    earlier = make_engagement(root, _one_request(2025), household="Smith", year=2025,
                              return_name="1040 - Smith")
    make_engagement(root, _one_request(2026), household="Smith", year=2026, return_name="1040 - Smith")
    monkeypatch.chdir(earlier.parent.parent)
    typed_earlier, typed_later = Path("2025/1040 - Smith"), Path("2026/1040 - Smith")

    assert store.key_root(typed_earlier) == root.resolve() == store.key_root(typed_later)
    conn = store.open(tmp_path / "fresh" / store.STORE_FILENAME)
    try:
        assert _two_years_rebuilt_without_a_root(conn, typed_earlier, typed_later) == [
            "J Park & Associates/Smith/2025/1040 - Smith", "J Park & Associates/Smith/2026/1040 - Smith",
        ]
        assert store._engagement_row(conn, typed_earlier)["path"].endswith("/2025/1040 - Smith")
        assert store._engagement_row(conn, typed_later)["path"].endswith("/2026/1040 - Smith")
    finally:
        conn.close()


def test_a_private_tree_typed_in_another_case_is_keyed_by_where_it_sits(root, tmp_path):
    """The review of decision 134. On a filesystem that does not tell
    ``j park & associates`` from the layout's own name, the folder is the
    same return whichever way it was typed, and it is keyed by where it
    sits rather than by its year folder. Asked where the filesystem tells
    the two apart, or does not give back a folder's own spelling, there is
    nothing to ask."""
    from tracker.layout import PRIVATE_TREE

    earlier = make_engagement(root, _one_request(2025), household="Smith", year=2025,
                              return_name="1040 - Smith")
    make_engagement(root, _one_request(2026), household="Smith", year=2026, return_name="1040 - Smith")
    typed = [root / PRIVATE_TREE.lower() / "Smith" / str(year) / "1040 - Smith" for year in (2025, 2026)]
    if not typed[0].is_dir() or typed[0].resolve() != earlier.resolve() \
            or typed[0].resolve().parts[-4] != PRIVATE_TREE:
        pytest.skip("this filesystem tells the two spellings apart, or does not give back a folder's own")

    assert store.key_root(typed[0]) == root.resolve() == store.key_root(typed[1])
    conn = store.open(tmp_path / "fresh" / store.STORE_FILENAME)
    try:
        assert _two_years_rebuilt_without_a_root(conn, *typed) == [
            "J Park & Associates/Smith/2025/1040 - Smith", "J Park & Associates/Smith/2026/1040 - Smith",
        ]
    finally:
        conn.close()


def test_the_settings_root_still_wins_over_the_position(root, engagement, tmp_path, monkeypatch):
    """Decision 106 unchanged: the root the settings file names is the key
    whenever the folder is under it - here a wider folder than the one the
    layout reads - and it wins over a root a caller has in hand too."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    (tmp_path / "app").mkdir(exist_ok=True)
    set_clients_root(tmp_path)

    assert store.key_root(engagement) == tmp_path
    assert store.key_root(engagement, root) == tmp_path
    assert store.engagement_path(store.key_root(engagement), engagement) == f"Clients/{KEY}"


def test_a_caller_root_still_wins_over_the_position(root, engagement, tmp_path):
    """With no settings file, a caller's root is the key, as it was: the
    position is asked only when nobody has a root in hand."""
    assert store.key_root(engagement, tmp_path) == tmp_path
    assert store.key_root(engagement, root) == root
    assert store.key_root(engagement) == root


def test_a_folder_outside_the_layout_still_keys_by_its_parent(root, tmp_path):
    """The parent fallback remains for a folder the layout does not read: a
    test tree, a folder named by hand. Both names are asked - the private
    tree four levels up and a year above - and a folder missing either is
    keyed by its parent."""
    by_hand = tmp_path / "Smith 2025"
    not_a_year = root / "J Park & Associates" / "Smith" / "Drafts" / "1040 - Smith"
    not_the_tree = root / "Clients" / "Smith" / "2025" / "1040 - Smith"
    for folder in (by_hand, not_a_year, not_the_tree):
        folder.mkdir(parents=True)
        assert store.key_root(folder) == folder.parent, folder


def test_a_store_of_the_previous_version_is_refused_and_rebuilt(root, engagement, tmp_path):
    """Decision 134 changed the key, not a column: a store of the version
    before it may hold two years of one return as one row, keyed by the
    return's name alone. So it is refused by the sentence every older store
    is, and the rebuild from the journals keys each return where it sits -
    even with no root in hand, the way a reader meets a folder: the next
    year of the same return is a row of its own, not the same row twice."""
    next_year = make_engagement(root, _one_request(2026), household="Smith Family", year=2026,
                                return_name=engagement.name)
    path = tmp_path / "older" / store.STORE_FILENAME        # not this process's own store
    store.open(path).close()
    written_earlier = sqlite3.connect(path)
    written_earlier.execute(f"PRAGMA user_version = {store.SCHEMA_VERSION - 1}")
    written_earlier.close()

    with pytest.raises(store.StoreError, match=f"user_version {store.SCHEMA_VERSION - 1}") as raised:
        store.open(path)
    assert "delete it and rebuild" in str(raised.value)

    path.unlink()
    conn = store.open(path)
    try:
        assert _two_years_rebuilt_without_a_root(conn, engagement, next_year) == [
            KEY, KEY.replace("/2025/", "/2026/"),
        ]
        assert store._engagement_row(conn, engagement)["path"] == KEY     # the exact key, no tail
        assert store.check(conn, root, engagement) == [] and store.check(conn, root, next_year) == []
    finally:
        conn.close()


# ------------------------------------------------ the freshness handle (d112) ----


def test_document_seqs_names_the_line_that_last_wrote_each_row_and_agrees_after_a_rebuild(
        conn, root, engagement):
    """The handle a person's action is judged against (decision 112).

    Per row, and only the row: a scan between two readings appends a line
    and moves the engagement's head, and no row's number with it - which
    is why a click made during a pass is not refused. A rebuild numbers
    the same lines the same way, so the mapping survives the recovery.
    """
    from tracker.records import ledger_key

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    [parked] = sort(engagement, today=DAY1).review
    key = ledger_key(parked)
    written = store.document_seqs(conn, engagement)
    assert list(written) == [key]
    assert written[key] == len(ledger.read_events(engagement))

    # A scan is a line of its own and rewrites no row.
    seed_statuses(engagement, {"A01": StatusUpdate(status=Status.MISSING)})
    head = len(ledger.read_events(engagement))
    assert head > written[key]
    assert store.document_seqs(conn, engagement) == written

    # The row rewritten: its number is the line that rewrote it, and the head.
    from tracker.filer import dismiss_review_file

    dismiss_review_file(engagement, parked.pbc_location, today=DAY2)
    rewritten = store.document_seqs(conn, engagement)
    assert rewritten[key] > written[key]
    assert rewritten[key] == len(ledger.read_events(engagement))

    # The recovery agrees with the reader, line for line.
    build(conn, root, engagement)
    assert store.document_seqs(conn, engagement) == rewritten

    # And an engagement the store does not hold has no rows to be stale.
    store.forget(conn, engagement)
    assert store.document_seqs(conn, engagement) == {}


def test_the_check_names_a_move_the_two_sides_do_not_agree_is_open(conn, root, engagement,
                                                                   monkeypatch):
    """Decision 119: a recovery finishes what this table says is open, so a
    table that kept an intent the journal has closed would move a file the
    record has already recorded. The check compares the two folds and says
    which key they disagree about."""
    from tests.test_filer import killed_at_the_record

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    killed_at_the_record(monkeypatch)
    with pytest.raises(KeyboardInterrupt):
        sort(engagement, today=DAY1)
    build(conn, root, engagement)
    assert said(conn, root, engagement) == []
    [open_move] = store.open_intents(conn, engagement)

    conn.execute("DELETE FROM intents")
    sentence = said(conn, root, engagement)[0]
    assert engagement.name in sentence and open_move[ledger.KEY_KEY] in sentence
    assert "not in the store" in sentence

    build(conn, root, engagement)                    # and a rebuild puts it back
    assert said(conn, root, engagement) == []
    assert store.open_intents(conn, engagement) == [open_move]


def test_the_two_retired_names_read_once_and_are_never_written(conn, root, by_hand):
    """Decision 132 retired two things decision 129 wrote. A journal from
    before it may carry a ``handed_over_by_person`` line: it is read, folded
    as the release it meant - the row goes, under both the identity it
    re-keyed to and the one it left - and never written again. An intent
    carrying the other record's half (``also_in``) is refused by name: its
    second half is nothing this version can write, and recovering it as if
    it had none would finish half a decision."""
    build(conn, root, by_hand)
    elsewhere = "../../../../Clients/Park & Lee LLC/2025/w2.pdf"
    handed = {ledger.EVENT_KEY: ledger.HANDED_OVER_BY_PERSON_EVENT, ledger.AT_KEY: ledger.stamp(),
              ledger.KEY_KEY: elsewhere, ledger.WAS_KEY: A_ROW_ORIGINAL,
              ledger.ROW_KEY: a_row(decision="Handed Over", pbc_location=elsewhere)}
    with engagement_lock(by_hand):
        store.record(conn, by_hand, ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row()))
        ledger._write_line(ledger.path_for(by_hand), handed)       # as 129 wrote it
    store.sync(conn, root, by_hand)

    assert ledger.replay(ledger.read_events(by_hand)).rows == {}
    assert store.documents(conn, by_hand) == []
    assert store.check(conn, root, by_hand) == []

    # Never written: not by the journal, not by the store.
    with pytest.raises(ledger.LedgerError, match="retired"):
        ledger.new(ledger.HANDED_OVER_BY_PERSON_EVENT, key=elsewhere)
    with engagement_lock(by_hand):
        with pytest.raises(store.StoreError, match="retired"):
            store.record(conn, by_hand, handed)
    assert ledger.HANDED_OVER_BY_PERSON_EVENT not in ledger.ROW_EVENTS

    # And an intent with the other record's half is refused by that name.
    moving = ledger.new(ledger.MOVING, **{
        ledger.KEY_KEY: A_ROW_ORIGINAL, ledger.DECIDED_BY_KEY: ledger.BY_PERSON,
        ledger.OPS_KEY: [], ledger.ROW_KEY: a_row(), store.ALSO_IN: {"../x": []}})
    with engagement_lock(by_hand):
        ledger._write_line(ledger.path_for(by_hand), moving)
    with pytest.raises(store.StoreError, match=repr(store.ALSO_IN)):
        store.sync(conn, root, by_hand)


def test_a_released_line_takes_the_row_out_and_closes_its_intent_in_both_folds(
        conn, root, by_hand):
    """The fold decision 132 adds: ``released`` carries a key and a reason
    and no row, removes the row under that key from the index and closes
    the intent the key had open - in the journal's fold and the store's
    alike, which ``check`` holds the two to. A release carrying a row is a
    line this version refuses."""
    build(conn, root, by_hand)
    release = ledger.new(ledger.MOVING, **{
        ledger.KEY_KEY: A_ROW_ORIGINAL, ledger.DECIDED_BY_KEY: ledger.BY_PERSON,
        ledger.OPS_KEY: [], ledger.ROW_KEY: a_row(), ledger.EVENT_KEY_AFTER: ledger.RELEASED,
        ledger.REASON_KEY: "released to X (B01) by a person"})
    with engagement_lock(by_hand):
        store.record(conn, by_hand, ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row()))
        store.record(conn, by_hand, release)
        assert store.open_intents(conn, by_hand) == [release]
        store.record(conn, by_hand, ledger.new(ledger.RELEASED, **{
            ledger.KEY_KEY: A_ROW_ORIGINAL, ledger.REASON_KEY: "released to X (B01) by a person"}))

    folded = ledger.replay(ledger.read_events(by_hand))
    assert folded.rows == {} and folded.intents == {}
    assert store.documents(conn, by_hand) == [] and store.open_intents(conn, by_hand) == []
    assert store.check(conn, root, by_hand) == []
    with engagement_lock(by_hand):
        with pytest.raises(store.StoreError, match="carries no row"):
            store.record(conn, by_hand, ledger.new(ledger.RELEASED, **{
                ledger.KEY_KEY: A_ROW_ORIGINAL, ledger.ROW_KEY: a_row()}))
