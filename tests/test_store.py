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
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from tests.conftest import child_env, make_engagement, named_page, seed_statuses, sort, written_elsewhere
from tests.test_scanner import text_pdf
from tracker import checkpoint, ledger, store
from tracker.filer import ensure, read_index
from tracker.layout import inbox_of, location_of, originals_of
from tracker.locking import engagement_lock
from tracker.manifest import (
    RequestItem,
    Status,
    load_engagement_info,
    load_manifest,
    save_rules,
)
from tracker.records import RULE_FIELDS, StatusUpdate, entry_to_json, rule_from_json, rule_to_json

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


def one_value(database: Path, sql: str, *parameters):
    """One value read from ``database`` on a connection closed at once.

    Not ``sqlite3.connect(p).execute(...)`` on one line: on current Python that
    connection stays open until the garbage collector runs, and on Windows
    an open file cannot be renamed or deleted, so the store's own set-aside
    of the same file, a moment later, failed with WinError 32 - the test's
    handle, not the product's (decision 159, Windows)."""
    conn = sqlite3.connect(database)
    try:
        return conn.execute(sql, parameters).fetchone()[0]
    finally:
        conn.close()


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


def key_of(folder):
    """The key the store and the checkpoint name a folder by, with no root in hand."""
    return store.engagement_path(store.key_root(folder), folder)


def unapplied(conn, folder, *events):
    """What ``record()`` leaves when a run dies between its appends and its
    apply: this machine's word that it was about to write the lines
    (decision 159's intent), and the lines in the journal but not the store.
    The caller holds the engagement lock."""
    lines, _head, chain = ledger.read_with_chain(folder)
    store._prove_against_checkpoint(conn, key_of(folder), lines, chain)
    store._intend(conn, key_of(folder), chain, len(lines),
                  ledger.intended_heads(ledger.chain_at(chain, len(lines)), list(events)))
    for event in events:
        ledger.append(folder, event)


def unlinked(events):
    """``events`` as a journal from before decision 159 held them: without
    the three keys every line now carries."""
    return [{k: v for k, v in event.items() if k not in ledger.LINE_KEYS} for event in events]


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
#: The latest earlier version a store is set aside at and rebuilt from
#: (decision 159, E3; until 159 it was refused and deleted by hand): the one
#: before the first in-place step (decision 204 upgrades a version-16 file
#: where it stands, so "the version before this one" is not set aside).
REFUSED_EARLIER = min(store._IN_PLACE) - 1
#: What turns a store of this version back into one at version 19: the
#: column pilot P170 added in place (the related households), taken off.
AS_AT_19 = ('ALTER TABLE engagements DROP COLUMN "household_related"',)
#: ... and back to version 18: the column decision 209 (R3b) added in
#: place, taken off again.
AS_AT_18 = (*AS_AT_19, 'ALTER TABLE engagements DROP COLUMN "admitted_by"')
#: ... and back to version 17: the columns decision 190's in-place step
#: adds, taken off again.
AS_AT_17 = (*AS_AT_18,
            'ALTER TABLE documents DROP COLUMN "code"',
            'ALTER TABLE documents DROP COLUMN "subfolder"',
            'ALTER TABLE statuses DROP COLUMN "note_codes"')
#: ... and back to version 16: decision 204's column too.
AS_AT_16 = (*AS_AT_17, 'ALTER TABLE documents DROP COLUMN "waits_for"')


def journal_as_written_before(engagement, fields: tuple[str, ...]) -> None:
    """Take ``fields`` back out of every line of a journal this version
    wrote - wherever a row, an intent or a status carries them - so it
    reads as one written before the decision that added them."""
    def before(value):
        if isinstance(value, dict):
            return {key: before(one) for key, one in value.items() if key not in fields}
        if isinstance(value, list):
            return [before(one) for one in value]
        return value

    events = [before(event) for event in ledger.read_events(engagement)]
    # Each line linked again, as the version that wrote it would have
    # linked it (decision 159): a rewrite the chain does not see, so the
    # rebuild reads it as that version's record rather than refusing an edit.
    ledger.path_for(engagement).write_bytes(b"")
    for event in events:
        written_elsewhere(engagement, {k: v for k, v in event.items() if k not in ledger.LINE_KEYS},
                          host=event.get(ledger.HOST_KEY) or ledger.this_host())


#: The fields decision 190 added to the record, and decision 204's.
FIELDS_OF_190 = ("code", "subfolder", "note_codes")
FIELDS_OF_204 = ("waits_for",)


def as_a_rebuild_leaves_it(conn, root, engagement, tmp_path) -> bool:
    """Whether ``conn``'s rows and statuses are, cell for cell - NULL as
    NULL - what a store rebuilt from the engagement's journal holds: the
    claim an in-place step makes (the store's rule, decisions 204 and 190).
    ``store check`` cannot be asked here, because the fixture's journal was
    rewritten after the store applied it, which the check rightly names."""
    rebuilt = store.open(tmp_path / "rebuilt" / store.STORE_FILENAME)
    try:
        store.rebuild_engagement(rebuilt, root, engagement)

        def cells(one):
            return {table: sorted(tuple(sorted((k, row[k]) for k in row.keys()
                                               if k not in ("engagement_id",)))
                                  for row in one.execute(f"SELECT * FROM {table}"))
                    for table in ("documents", "statuses")}

        return cells(conn) == cells(rebuilt)
    finally:
        rebuilt.close()


def a_row(**fields) -> dict:
    base = {"received": "2026-07-01", "original_name": "w2.pdf", "size_kb": 1.0,
            "digest": "ab" * 32, "identifier": "", "prepared_location": "",
            "pbc_location": A_ROW_ORIGINAL, "decision": "Needs Review",
            "reason": "", "candidates": "", "evidence": "", "also_filed": ""}
    return {**base, **fields}


# --------------------------------------------------------------- the schema ----


def test_opening_a_file_that_is_not_there_creates_the_schema(tmp_path):
    path = tmp_path / "app" / store.STORE_FILENAME
    assert not path.exists()

    conn = store.open(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION == 20
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


def test_a_version_nine_store_is_set_aside_and_rebuilt(tmp_path):
    """Decision 107 added the verdict cache's two tables; a file from before
    it has no ``verdicts`` table. Since decision 159 (E3) it is not refused
    until a person deletes it: it is set aside under its version's name,
    never overwritten, and a fresh store is opened in its place.

    And so is a file at the latest version no in-place step reaches
    (``REFUSED_EARLIER``; decision 204 upgrades the one after it where it
    stands): decision 132 changed the fold rather than a column - a
    ``released`` line takes a row out of the index - and a version-9 file
    folded by the old code may hold ``Handed Over`` rows this version never
    produces. Rebuilt from the journals, the retired lines fold as the
    releases they meant.
    """
    path = tmp_path / "app" / store.STORE_FILENAME
    for version in (2, REFUSED_EARLIER):
        store.open(path).close()
        written_earlier = sqlite3.connect(path)
        written_earlier.execute(f"PRAGMA user_version = {version}")
        written_earlier.close()

        store.open(path).close()
        aside = path.with_name(f"{store.STORE_FILENAME}.v{version}.old")
        assert aside.is_file()
        assert one_value(aside, "PRAGMA user_version") == version
        assert one_value(path, "PRAGMA user_version") \
            == store.SCHEMA_VERSION
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

    # As written: the event, and the three keys the record adds to every line.
    assert unlinked([store.last_event(conn, by_hand, ledger.DRAFTED)]) == [hold]
    assert unlinked([store.last_event(conn, by_hand, ledger.DRAFTED,
                                      carrying=ledger.FILE_KEY)]) == [first]
    assert store.last_event(conn, by_hand, ledger.DRAFTED, carrying="nothing-carries-this") is None
    assert unlinked([store.last_event(conn, by_hand, ledger.KEYWORD_LEARNED)]) == [taught]
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
                          cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                          env=child_env(PYTHONIOENCODING="utf-8"))


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


@pytest.fixture
def this_account(tmp_path, monkeypatch):
    """The app's settings folder and this account's data home, as a machine
    with no ``TRACKER_STORE`` has them (decision 186): the store is the data
    home's, and the settings folder holds only the pointer."""
    from tracker.settings import ENV_DATA_HOME, ENV_SETTINGS_DIR, SETTINGS_FILENAME

    app, home = tmp_path / "app", tmp_path / "account-data"
    app.mkdir(exist_ok=True)
    (app / SETTINGS_FILENAME).write_text("{}", encoding="utf-8")
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(app))
    monkeypatch.setenv(ENV_DATA_HOME, str(home))
    monkeypatch.delenv(store.ENV_STORE)
    store.close()
    yield app, home
    store.close()


def test_the_command_line_takes_the_app_folder_to_mean_the_data_homes_store(this_account, root, engagement,
                                                                            tmp_path):
    """The runbook says "the app folder"; the integration run of decision 107
    typed it and got an empty store beside the folder. Since decision 186
    the app folder and its settings file both mean this account's store, in
    the data home; a store file named elsewhere is that copy, and a typo
    means no file at all."""
    from tracker.settings import SETTINGS_FILENAME

    app, home = this_account
    settings = app / SETTINGS_FILENAME
    the_store = home / store.STORE_FILENAME
    assert store.store_path() == the_store

    assert store.store_named(app) == the_store
    assert store.store_named(settings) == the_store
    a_copy = tmp_path / "copy" / store.STORE_FILENAME
    assert store.store_named(a_copy) == a_copy                      # exists or not: rebuild creates it
    assert store.store_named(tmp_path / "apps") is None            # a typo of a folder
    assert store.store_named(app / f"{store.STORE_FILENAME}x") is None   # a typo of the file

    assert cli(app, "rebuild", root).returncode == 0                # the runbook's line, in fact
    assert the_store.exists()
    assert cli(settings, "check", root).returncode == 0
    assert cli(the_store, "check", root).returncode == 0

    refused = cli(tmp_path / "apps", "check", root)
    assert refused.returncode == 2 and "nothing was opened" in refused.stderr
    assert not list(app.rglob(store.STORE_FILENAME))                # nothing beside the program


def test_the_command_line_refuses_the_old_store_beside_the_program_and_creates_nothing(
        this_account, root, engagement):
    app, home = this_account
    old = app / store.STORE_FILENAME
    assert store.store_named(old) == store.OLD_STORE_NAMED.format(path=old, store=home / store.STORE_FILENAME)

    refused = cli(old, "rebuild", root)
    assert refused.returncode == 1
    assert store.OLD_STORE_NAMED.format(path=old, store=home / store.STORE_FILENAME) in refused.stderr
    assert "Traceback" not in refused.stderr and "Traceback" not in refused.stdout
    assert not old.exists()                                         # never opened, so never made


def test_the_command_line_refuses_a_copy_inside_the_apps_own_folder_and_creates_nothing(
        this_account, root, engagement):
    """Decision 186's review, N4: a folder or a store file inside the app's
    own folder - on a source install, the checkout - is refused in a
    sentence, so a ``rebuild`` never creates client data there."""
    from tracker.settings import app_dir

    inside = app_dir() / "docs"
    copy = inside / store.STORE_FILENAME
    said = store.COPY_INSIDE_APP.format(path=copy, app=app_dir())
    assert store.store_named(inside) == said
    assert store.store_named(copy) == said

    refused = cli(inside, "rebuild", root)
    assert refused.returncode == 1
    assert said in refused.stderr
    assert "Traceback" not in refused.stderr and "Traceback" not in refused.stdout
    assert not copy.exists()


def test_a_store_the_environment_names_is_held_to_the_data_homes_two_checks(tmp_path, monkeypatch):
    """Decision 186's review, N4: ``TRACKER_STORE`` is a second answer to
    "where is the store", so it is held to the data home's checks - a whole
    path, not inside the program, on a fixed disk - and refused, as the data
    home is, with a SettingsError that says why."""
    from tracker import settings

    store.close()
    allowed = tmp_path / "elsewhere" / store.STORE_FILENAME
    monkeypatch.setenv(store.ENV_STORE, str(allowed))
    assert store.store_path() == allowed

    monkeypatch.setenv(store.ENV_STORE, "relative/tracker.db")
    with pytest.raises(settings.SettingsError) as refused:
        store.store_path()
    assert str(refused.value) == store.STORE_OVERRIDE_NOT_ABSOLUTE.format(value="relative/tracker.db")

    in_the_program = settings.app_dir() / store.STORE_FILENAME
    monkeypatch.setenv(store.ENV_STORE, str(in_the_program))
    with pytest.raises(settings.SettingsError) as refused:
        store.store_path()
    assert str(refused.value) == store.STORE_OVERRIDE_IN_PROGRAM.format(path=in_the_program,
                                                                       program=settings.app_dir())

    monkeypatch.setenv(store.ENV_STORE, str(allowed))
    monkeypatch.setattr(settings, "drive_type", lambda path: settings.DRIVE_REMOVABLE)
    with pytest.raises(settings.SettingsError) as refused:
        store.store_path()
    assert str(refused.value) == store.STORE_OVERRIDE_NOT_LOCAL.format(path=allowed)
    assert not allowed.exists() and not in_the_program.exists()


def test_the_command_line_says_a_refused_store_in_one_sentence(root, tmp_path):
    """A version newer than this code is refused by open() in a sentence;
    the command line repeats it and exits 1 - never a traceback."""
    path = tmp_path / "app" / store.STORE_FILENAME
    store.open(path).close()
    newer = sqlite3.connect(path)
    newer.execute(f"PRAGMA user_version = {store.SCHEMA_VERSION + 1}")
    newer.close()

    refused = cli(path, "check", root)
    assert refused.returncode == 1
    assert f"version {store.SCHEMA_VERSION + 1}" in refused.stderr
    assert "install that version again" in refused.stderr
    assert "Traceback" not in refused.stderr and "Traceback" not in refused.stdout


# -------------------------------------------------------------- the placement ----


def test_the_store_is_placed_in_the_data_home_and_never_beside_the_settings_file(
        this_account, root, by_hand):
    from tracker.settings import data_home, settings_path

    app, home = this_account
    placed = store.store_path()
    assert placed == data_home() / store.STORE_FILENAME == home / store.STORE_FILENAME
    assert root not in placed.parents
    assert placed.parent != settings_path().parent

    conn = store.open(placed)
    try:
        build(conn, root, by_hand)
        with engagement_lock(by_hand):
            store.record(conn, by_hand, ledger.new(
                ledger.FILED, key="p/one", row=a_row(pbc_location="p/one")))
        # While it is open, which is when the write-ahead log exists.
        assert _database_files_under(root) == []
        assert _database_files_under(app) == []
    finally:
        conn.close()
    assert _database_files_under(root) == []
    assert _database_files_under(app) == []


def test_a_store_left_behind_is_rebuilt_from_the_record_in_its_new_home(root, engagement, tmp_path,
                                                                         monkeypatch):
    """Nothing is carried over (decision 186): the store an earlier version
    kept beside the settings file is never read, and the empty one in the
    data home is built from the engagement's own record on first use."""
    from tracker.settings import ENV_DATA_HOME, ENV_SETTINGS_DIR

    app = tmp_path / "app"
    old = app / store.STORE_FILENAME                                # the fixture's store: the old place
    conn = store.connect()
    assert Path(store.store_path()) == old
    build(conn, root, engagement)
    store.close()
    before = old.read_bytes()

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(app))
    monkeypatch.setenv(ENV_DATA_HOME, str(tmp_path / "account-data"))
    monkeypatch.delenv(store.ENV_STORE)
    # The checkpoint is moved, as the runbook's upgrade step says: one left
    # beside the program refuses a fresh one (186's rebase review, MF1).
    (tmp_path / "account-data").mkdir()
    os.replace(app / checkpoint.CHECKPOINT_FILENAME, tmp_path / "account-data" / checkpoint.CHECKPOINT_FILENAME)
    fresh = store.connect()
    try:
        assert store.store_path() == tmp_path / "account-data" / store.STORE_FILENAME
        assert store.catch_up(fresh, root, engagement) >= 1
        assert store.check(fresh, root, engagement) == []
    finally:
        store.close()
    assert old.read_bytes() == before


def _database_files_under(folder: Path) -> list[str]:
    suffixes = (store.STORE_FILENAME, "-wal", "-shm", ".db")
    return sorted(path.name for path in folder.rglob("*")
                  if path.is_file() and path.name.endswith(suffixes))


# --------------------------------------------------------------- the layers ----


def test_the_store_names_no_reader_at_load_time():
    """The explicit form of the layers test's claim: nothing that walks
    folders or moves files is reachable from importing this module.

    Read from the text with the one function exempted that decision 159
    added on purpose: ``verify``, the read-only firm-wide proof, reaches
    the registry's walk and the filer's own proof of a row's bytes at call
    time - reusing them rather than writing a second walk and a second
    fingerprint - and only when a person runs it."""
    import ast

    source = (Path(store.__file__)).read_text(encoding="utf-8")
    top, _, command_line = source.partition('if __name__ == "__main__":')
    tree = ast.parse(top)
    verify = next(node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name == "verify")
    lines = top.splitlines()
    top = "\n".join(lines[:verify.lineno - 1] + lines[verify.end_lineno:])
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
    written_elsewhere(by_hand, {
        ledger.EVENT_KEY: ledger.KEYWORD_UNLEARNED, ledger.AT_KEY: ledger.stamp(),
        ledger.IDENTIFIER_KEY: "A01", ledger.KEYWORD_KEY: 7,
    })

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


# ------------------------------------------- a request respelled by case (136) ----


def scanned(**statuses) -> dict:
    """One scan's line, the statuses it changed by the spelling it met."""
    return ledger.new(ledger.SCANNED, **{ledger.STATUSES_KEY: {
        identifier: {"status": status, "file_count": 0} for identifier, status in statuses.items()}})


def test_a_status_scanned_under_a_case_respelled_identifier_is_one_request_to_the_check(
        conn, root, by_hand):
    """Decision 136: ``A01`` and ``a01`` are one request, so the later scan
    is its status. The store keys it that way; the check used to fold the
    two spellings apart and name the earlier one as the record's word."""
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, scanned(A01=Status.RECEIVED))
        store.record(conn, by_hand, scanned(a01=Status.MISSING))

    held = conn.execute('SELECT status FROM statuses WHERE "identifier" = ?', ("a01",)).fetchone()
    assert held["status"] == Status.MISSING
    assert said(conn, root, by_hand) == []


def test_keywords_taught_under_two_spellings_of_one_request_are_checked_in_the_order_they_were_taught(
        conn, root, by_hand):
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, learned("A01", "alpha"), learned("a01", "beta"),
                     learned("A01", "gamma"))

    assert store.learned_keywords(conn, by_hand) == {"a01": ("alpha", "beta", "gamma")}
    assert said(conn, root, by_hand) == []


def test_a_word_retaught_under_the_other_spelling_is_checked_last_once(conn, root, by_hand):
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, learned("A01", "alpha"), learned("a01", "beta"),
                     learned("A01", "gamma"), learned("a01", "alpha"))

    assert store.learned_keywords(conn, by_hand) == {"a01": ("beta", "gamma", "alpha")}
    assert said(conn, root, by_hand) == []


def test_a_word_taken_back_under_the_other_spelling_is_gone_from_both_sides(conn, root, by_hand):
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, learned("A01", "alpha"), learned("A01", "beta"),
                     unlearned("a01", "alpha"))

    assert store.learned_keywords(conn, by_hand) == {"a01": ("beta",)}
    assert said(conn, root, by_hand) == []
    build(conn, root, by_hand)                    # and a store built from nothing agrees
    assert said(conn, root, by_hand) == []


def test_the_check_still_names_a_status_planted_in_the_store_behind_the_journals_back(
        conn, root, by_hand):
    """The gate keeps its teeth: keying the record's side without case
    joins two spellings of one request, and nothing else."""
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, scanned(A01=Status.RECEIVED), learned("A01", "lender"))
    assert said(conn, root, by_hand) == []
    engagement_id = id_of(conn, by_hand)

    conn.execute('INSERT INTO statuses (engagement_id, "identifier", status, file_count, seq) '
                 "VALUES (?, ?, ?, ?, ?)", (engagement_id, "c01", Status.RECEIVED, 1, 99))
    (sentence,) = said(conn, root, by_hand)
    assert "c01" in sentence and "in the store and none in the record" in sentence
    conn.execute('DELETE FROM statuses WHERE "identifier" = ?', ("c01",))

    conn.execute('UPDATE statuses SET status = ? WHERE "identifier" = ?', (Status.MISSING, "a01"))
    (sentence,) = said(conn, root, by_hand)
    assert "A01" in sentence and repr(Status.MISSING) in sentence and repr(Status.RECEIVED) in sentence

    conn.execute("DELETE FROM statuses")
    (sentence,) = said(conn, root, by_hand)
    assert "A01" in sentence and "in the record and none in the store" in sentence

    conn.execute("DELETE FROM learned_keywords")
    problems = said(conn, root, by_hand)
    assert any("a01" in p and "[]" in p and "['lender']" in p for p in problems)

    store.rebuild_engagement(conn, root, by_hand)
    assert said(conn, root, by_hand) == []


def test_an_end_to_end_respelling_leaves_the_check_empty(conn, root, engagement):
    """The way it happens in the app: a scan and a filing that taught a
    word under ``A01``, the person retypes it ``a01``, then a scan, a
    filing that teaches, and the first word taken back in the editor."""
    from dataclasses import replace

    from tracker.filer import assign_review_file
    from tracker.manifest import unlearn_keyword

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    assign_review_file(engagement, parked.pbc_location, "A01", keyword="lender", today=DAY1)
    seed_statuses(engagement, {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1,
                                                   received_date=DAY1)})

    rules = load_manifest(engagement)
    respelled = [replace(row, identifier="a01") if row.identifier == "A01" else row for row in rules]
    assert save_rules(engagement, respelled, load_engagement_info(engagement)).removed == ("A01",)

    seed_statuses(engagement, {"a01": StatusUpdate(status=Status.PARTIAL, file_count=1,
                                                   received_date=DAY2)})
    drop(engagement, "scan0013.pdf", "nothing the rules recognise either")
    parked = sort(engagement, today=DAY2).review[0]
    assign_review_file(engagement, parked.pbc_location, "a01", keyword="escrow", today=DAY2)
    unlearn_keyword(engagement, "a01", "lender")

    build(conn, root, engagement)
    assert store.learned_keywords(conn, engagement) == {"a01": ("escrow",)}
    assert store.check(conn, root, engagement) == []
    live = store.connect()                        # the store as the app left it, not a rebuild
    assert store.check(live, root, engagement) == []


# ------------------------------- a batch of lines across two spellings (138) ----


#: ``A01``, then ``a01``, then ``A01`` again: one request scanned three
#: times, the last to ``PARTIAL``. A fold keyed by the exact spelling holds
#: ``{A01: PARTIAL, a01: MISSING}`` and, written in that order, left the
#: second scan's status standing.
THREE_SCANS = (("A01", Status.RECEIVED), ("a01", Status.MISSING), ("A01", Status.PARTIAL))


def three_scans() -> list[dict]:
    return [scanned(**{identifier: status}) for identifier, status in THREE_SCANS]


def held_statuses(conn, folder) -> list[tuple[str, str]]:
    return [(row["identifier"], row["status"]) for row in conn.execute(
        'SELECT "identifier", status FROM statuses WHERE engagement_id = ? ORDER BY "identifier"',
        (id_of(conn, folder),))]


def test_a_rebuild_keeps_the_last_scans_status_across_spellings(conn, root, by_hand):
    """Decision 138: a rebuild applies the journal as one batch, and the
    batch writes each request's last scan, whatever case it was spelt in.
    The table keys the row without case (``_write_status``), so the one
    row is ``a01``."""
    with engagement_lock(by_hand):
        unapplied(conn, by_hand, *three_scans())
    build(conn, root, by_hand)

    assert held_statuses(conn, by_hand) == [("a01", Status.PARTIAL)]
    assert said(conn, root, by_hand) == []


@pytest.mark.parametrize("apply", [store.catch_up, store.sync], ids=["catch_up", "sync"])
def test_catch_up_keeps_the_last_scans_status_across_spellings(conn, root, by_hand, apply):
    """The store built, then behind the journal by the three lines, which
    the top-up applies as one batch (decision 138)."""
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        unapplied(conn, by_hand, *three_scans())
    apply(conn, root, by_hand)

    assert held_statuses(conn, by_hand) == [("a01", Status.PARTIAL)]
    assert said(conn, root, by_hand) == []


def test_one_record_of_several_scan_lines_keeps_the_last(conn, root, by_hand):
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, *three_scans())

    assert held_statuses(conn, by_hand) == [("a01", Status.PARTIAL)]
    assert said(conn, root, by_hand) == []


def test_the_writer_and_the_check_use_one_rule(conn, root):
    """Forty seeded journals of mixed-spelling scans, each written as a few
    batches - some by ``record()``, some appended and then ``sync()``-ed -
    and the store the batches left agrees with the check, as does a store
    rebuilt from nothing (decision 138). The seed is fixed so a failure
    names the same journal every run."""
    import random

    chance = random.Random(138)
    spellings = ("A01", "a01", "B02", "b02")
    kinds = (Status.RECEIVED, Status.MISSING, Status.PARTIAL)
    for number in range(40):
        folder = make_engagement(root, ITEMS, household=f"Fuzz {number:02d}", scaffold=False)
        try:
            build(conn, root, folder)
            for _batch in range(chance.randint(1, 3)):
                lines = [
                    scanned(**{identifier: chance.choice(kinds)
                               for identifier in chance.sample(spellings, chance.randint(1, 2))})
                    for _line in range(chance.randint(2, 5))
                ]
                with engagement_lock(folder):
                    if chance.random() < 0.5:
                        store.record(conn, folder, *lines)
                    else:
                        unapplied(conn, folder, *lines)
                        store.sync(conn, root, folder)
                assert said(conn, root, folder) == [], f"journal {number}"
            build(conn, root, folder)
            assert said(conn, root, folder) == [], f"journal {number}, rebuilt"
        finally:
            ledger.path_for(folder).unlink(missing_ok=True)


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

    return IndexEntry(received="2026-09-23", original_name="x.pdf", size_kb=5.0,
                      digest="ab" * 32, identifier="A01",
                      prepared_location="Prepared/A01 - W-2.pdf",
                      pbc_location=f"../../../../Clients/Smith/{period}/x.pdf", decision=FILED,
                      reason=f"filed for {period}")


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

    # The settings beside the root, not inside it: a root that holds the
    # app's settings is refused (decision 137).
    settings = tmp_path.parent / f"{tmp_path.name}-app"
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    settings.mkdir(exist_ok=True)
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


def test_a_store_of_the_previous_version_is_set_aside_and_rebuilt(root, engagement, tmp_path):
    """Decision 134 changed the key, not a column: a store of the version
    before it may hold two years of one return as one row, keyed by the
    return's name alone. So it is set aside like every older store (decision
    159, E3), and the rebuild from the journals keys each return where it sits -
    even with no root in hand, the way a reader meets a folder: the next
    year of the same return is a row of its own, not the same row twice."""
    next_year = make_engagement(root, _one_request(2026), household="Smith Family", year=2026,
                                return_name=engagement.name)
    path = tmp_path / "older" / store.STORE_FILENAME        # not this process's own store
    store.open(path).close()
    written_earlier = sqlite3.connect(path)
    written_earlier.execute(f"PRAGMA user_version = {REFUSED_EARLIER}")
    written_earlier.close()

    conn = store.open(path)            # set aside (decision 159, E3), and a fresh one opened
    assert path.with_name(f"{store.STORE_FILENAME}.v{REFUSED_EARLIER}.old").is_file()
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
        written_elsewhere(by_hand, handed)                           # as 129 wrote it
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
        written_elsewhere(by_hand, moving)
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
        assert unlinked(store.open_intents(conn, by_hand)) == [release]
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


# ------------------------------------------- a read never outruns a write ----
#
# Decision 135. Readers take no lock, and the app's process and the pass's
# share one store: every function that applies journal lines reads the row,
# the lines and the head inside its own immediate transaction, the lines and
# the head from one read of the file. The races below are staged in one
# process with two connections to one store file - the second one is the
# other process - and the other process acts at the one moment the old code
# was exposed: after the first look at the row, before the transaction.


def the_other_process_first(monkeypatch, on, then):
    """Run ``then()`` once, the moment connection ``on`` is about to begin a
    transaction - after anything it read outside one, before anything it
    reads inside. Nothing holds the lock yet, so the other process's own
    ``BEGIN IMMEDIATE`` cannot wait on this one."""
    real = store._transaction
    fired = []

    @contextmanager
    def interleaved(connection):
        if connection is on and not fired:
            fired.append(True)
            then()
        with real(connection):
            yield

    monkeypatch.setattr(store, "_transaction", interleaved)
    return fired


def the_store_is_the_journal(conn, root, engagement):
    """The four things a store that kept up says: every line applied, the
    head of exactly those lines, nothing the check can name."""
    stored = store._engagement_row(conn, engagement)
    assert stored["applied_seq"] == len(ledger.read_events(engagement))
    assert stored["ledger_head"] == ledger.head(engagement)
    assert store.check(conn, root, engagement) == []
    assert store.state(conn, engagement, ledger_head_now=ledger.head(engagement)) == store.CURRENT


def test_a_reader_that_syncs_while_a_writer_records_leaves_the_store_at_the_journals_last_line(
        conn, root, by_hand, tmp_path, monkeypatch):
    """The probe of 2026-09-23. The pass has appended line 2 (a filing) and
    not yet applied it; the app's reader looks at the row and the journal;
    before the reader's transaction the pass applies line 2 and records
    line 3, which parks the same row. Read outside, the reader re-applied
    its stale slice and saved the head of all three lines: the store said
    'Filed' against a journal saying 'Needs Review', called itself current
    and refused every later pass for that return."""
    build(conn, root, by_hand)
    writer = store.open(tmp_path / "app" / store.STORE_FILENAME)
    try:
        with engagement_lock(by_hand):
            unapplied(conn, by_hand, ledger.new(
                ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed", identifier="A01")))

            def the_pass_finishes_and_parks_it():
                store.sync(writer, root, by_hand)
                store.record(writer, by_hand, ledger.new(
                    ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row(decision="Needs Review")))

            fired = the_other_process_first(monkeypatch, conn, the_pass_finishes_and_parks_it)
            store.follow_the_journal(conn, root, by_hand)
            assert fired
            monkeypatch.undo()

            the_store_is_the_journal(conn, root, by_hand)
            assert [row["decision"] for row in store.documents(conn, by_hand)] == ["Needs Review"]
            store.record(conn, by_hand, learned("A01", "lender"))     # and the next write is taken
    finally:
        writer.close()


def test_a_reader_building_an_engagement_while_a_writer_records_misses_no_line(
        root, by_hand, tmp_path, monkeypatch):
    """The first-build branch. A reader that finds no row reads the journal,
    and the pass builds the row and records a line before the reader's
    transaction: the reader finds the row inside and catches it up rather
    than building a second one from lines the journal has overtaken."""
    path = tmp_path / "fresh" / store.STORE_FILENAME
    reader, writer = store.open(path), store.open(path)
    try:
        def the_pass_builds_and_records():
            store.follow_the_journal(writer, root, by_hand)
            with engagement_lock(by_hand):
                store.record(writer, by_hand, ledger.new(
                    ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed", identifier="A01")))

        fired = the_other_process_first(monkeypatch, reader, the_pass_builds_and_records)
        assert store.follow_the_journal(reader, root, by_hand) == 2
        assert fired
        monkeypatch.undo()

        the_store_is_the_journal(reader, root, by_hand)
        assert [row["decision"] for row in store.documents(reader, by_hand)] == ["Filed"]
    finally:
        reader.close()
        writer.close()


def test_a_rebuild_racing_a_writer_saves_the_head_of_the_lines_it_applied(
        conn, root, by_hand, tmp_path, monkeypatch):
    """A rebuild waiting on the pass's transaction reads the journal after
    it, so the line the pass recorded meanwhile is in the rows the rebuild
    writes and not only in the head it saves beside them."""
    build(conn, root, by_hand)
    writer = store.open(tmp_path / "app" / store.STORE_FILENAME)
    try:
        def the_pass_records():
            with engagement_lock(by_hand):
                store.record(writer, by_hand, ledger.new(
                    ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed", identifier="A01")))

        fired = the_other_process_first(monkeypatch, conn, the_pass_records)
        store.rebuild_engagement(conn, root, by_hand)
        assert fired
        monkeypatch.undo()

        the_store_is_the_journal(conn, root, by_hand)
        assert [row["decision"] for row in store.documents(conn, by_hand)] == ["Filed"]
    finally:
        writer.close()


def test_a_writer_whose_lines_a_reader_already_applied_applies_none_of_them_twice(
        conn, root, by_hand, tmp_path, monkeypatch):
    """``record()`` applies what the journal holds past the store when its
    transaction begins, not the batch it was handed from where the store
    stood before its appends. A reader that caught the whole batch up in
    between - the move begun and the filing that ends it - leaves the
    writer nothing to apply: the intent the move opened stays closed and
    every line is in the events table once, at its own number."""
    build(conn, root, by_hand)
    reader = store.open(tmp_path / "app" / store.STORE_FILENAME)
    moving = ledger.new(ledger.MOVING, **{
        ledger.KEY_KEY: A_ROW_ORIGINAL, ledger.DECIDED_BY_KEY: ledger.BY_PASS,
        ledger.OPS_KEY: [], ledger.ROW_KEY: a_row(decision="Filed", identifier="A01"),
        ledger.EVENT_KEY_AFTER: ledger.FILED})
    filed = ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed", identifier="A01"))
    try:
        applied_by_the_reader = []

        def the_reader_catches_up():
            applied_by_the_reader.append(store.follow_the_journal(reader, root, by_hand))

        fired = the_other_process_first(monkeypatch, conn, the_reader_catches_up)
        with engagement_lock(by_hand):
            assert store.record(conn, by_hand, moving, filed) == 3
        assert fired and applied_by_the_reader == [3]
        monkeypatch.undo()

        the_store_is_the_journal(conn, root, by_hand)
        assert store.open_intents(conn, by_hand) == []
        mine = (id_of(conn, by_hand),)
        assert [row["seq"] for row in conn.execute(
            "SELECT seq FROM events WHERE engagement_id = ? ORDER BY seq", mine)] == [1, 2, 3]
    finally:
        reader.close()


def test_a_pass_heals_a_store_whose_head_names_a_line_it_never_applied(root, by_hand):
    """What a build before decision 135 could leave: the head of the whole
    journal saved beside one line fewer applied. The readers trust the head
    and call it current; every writer counts and refuses. The pass's own
    ensure() compares by count, so the next pass repairs it with no rebuild
    and records after it."""
    conn = store.connect()
    store.rebuild_engagement(conn, root, by_hand)
    with engagement_lock(by_hand):
        unapplied(conn, by_hand, ledger.new(
            ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed", identifier="A01")))
    conn.execute("UPDATE engagements SET ledger_head = ? WHERE id = ?",
                 (ledger.head(by_hand), id_of(conn, by_hand)))
    parked = ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row(decision="Needs Review"))
    assert store.follow_the_journal(conn, root, by_hand) == 1          # the reader is fooled
    with engagement_lock(by_hand), pytest.raises(store.StoreError, match="applied 1 of"):
        store.record(conn, by_hand, parked)                             # the writer is not

    assert ensure(by_hand, root) == store.CURRENT

    the_store_is_the_journal(conn, root, by_hand)
    with engagement_lock(by_hand):
        assert store.record(conn, by_hand, parked) == 3
    the_store_is_the_journal(conn, root, by_hand)
    assert [row["decision"] for row in store.documents(conn, by_hand)] == ["Needs Review"]


def test_a_reader_keeps_the_fast_path_and_parses_nothing_when_the_head_has_not_moved(
        conn, root, by_hand, monkeypatch):
    """The cost ``follow_the_journal`` exists to keep off every read: a head
    that has not moved is a digest of the file and nothing else - not one
    line parsed. The moment it moves, the lines are parsed once."""
    build(conn, root, by_hand)
    parses = []
    # The one parser every reading goes through (with each line's bytes
    # since decision 137, for the applied chain).
    real = ledger._parse_lines

    def counted(data, name):
        parses.append(name)
        return real(data, name)

    monkeypatch.setattr(ledger, "_parse_lines", counted)
    assert store.follow_the_journal(conn, root, by_hand) == 1
    assert store.follow_the_journal(conn, root, by_hand) == 1
    assert parses == []

    with engagement_lock(by_hand):
        unapplied(conn, by_hand, ledger.new(
            ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed", identifier="A01")))
    parses.clear()                     # the append parses the record it links to (decision 159)
    assert store.follow_the_journal(conn, root, by_hand) == 2
    assert len(parses) == 1


def the_pass_appends_during_the_read(monkeypatch, conn, engagement, event):
    """Append ``event`` to the journal, under the engagement lock, the first
    time ``conn``'s side reads the journal's bytes inside a transaction -
    after that read has its bytes, before anything else is read. That is
    the pass: it appends under its own lock *before* its own transaction,
    so a reader holding the store's lock cannot keep a line out of the file."""
    real = ledger._bytes_of
    fired = []

    def and_then_a_line(path):
        data = real(path)
        if conn.in_transaction and not fired:
            fired.append(True)
            with engagement_lock(engagement):
                unapplied(conn, engagement, event)
        return data

    monkeypatch.setattr(ledger, "_bytes_of", and_then_a_line)
    return fired


def the_head_of_the_first(engagement, lines):
    """The head of the journal as it was when it held its first ``lines`` lines."""
    data = ledger.path_for(engagement).read_bytes()
    return hashlib.sha256(b"".join(data.splitlines(keepends=True)[:lines])).hexdigest()


def test_a_line_appended_between_a_readers_lines_and_its_head_is_left_for_the_next_read(
        conn, root, by_hand, monkeypatch):
    """The one read of decision 135, pinned (review fix 1). The pass appends
    a line while the reader holds the store's lock and reads the journal:
    the head the reader saves is the head of exactly the lines it applied,
    so the store says it is behind rather than calling itself current, and
    the next read applies the line. Read as two calls - the lines, then the
    head - the head would name the line nobody applied: the stuck return."""
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        unapplied(conn, by_hand, ledger.new(
            ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed", identifier="A01")))
    parked = ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row(decision="Needs Review"))

    fired = the_pass_appends_during_the_read(monkeypatch, conn, by_hand, parked)
    assert store.follow_the_journal(conn, root, by_hand) == 2
    assert fired
    monkeypatch.undo()

    assert len(ledger.read_events(by_hand)) == 3
    assert store._engagement_row(conn, by_hand)["ledger_head"] == the_head_of_the_first(by_hand, 2)
    assert store.state(conn, by_hand, ledger_head_now=ledger.head(by_hand)) == store.BEHIND
    assert store.follow_the_journal(conn, root, by_hand) == 3
    the_store_is_the_journal(conn, root, by_hand)
    assert [row["decision"] for row in store.documents(conn, by_hand)] == ["Needs Review"]


def test_a_line_appended_while_a_rebuild_reads_the_journal_is_left_for_the_next_read(
        conn, root, by_hand, monkeypatch):
    """The same one read in the rebuild: a line the pass appends while the
    rebuild reads the journal is neither in its rows nor in the head it
    saves beside them, and the next read applies it."""
    build(conn, root, by_hand)
    filed = ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed", identifier="A01"))

    fired = the_pass_appends_during_the_read(monkeypatch, conn, by_hand, filed)
    store.rebuild_engagement(conn, root, by_hand)
    assert fired
    monkeypatch.undo()

    assert len(ledger.read_events(by_hand)) == 2
    rebuilt = store._engagement_row(conn, by_hand)
    assert rebuilt["applied_seq"] == 1
    assert rebuilt["ledger_head"] == the_head_of_the_first(by_hand, 1)
    assert store.state(conn, by_hand, ledger_head_now=ledger.head(by_hand)) == store.BEHIND
    assert store.follow_the_journal(conn, root, by_hand) == 2
    the_store_is_the_journal(conn, root, by_hand)
    assert [row["decision"] for row in store.documents(conn, by_hand)] == ["Filed"]


def test_a_catch_up_with_nothing_to_apply_takes_no_lock(root, by_hand, tmp_path):
    """Review fix 2. ``ensure()`` runs after nearly every action in the app
    and for every engagement in the Status Report, and a pass's ``record()``
    waits on the same immediate lock. A store that has applied every line
    is answered from a look that takes no lock: with another connection
    holding ``BEGIN IMMEDIATE`` - and no patience at all for waiting on it -
    the caught-up store's catch-up, sync and top-up all still answer."""
    path = tmp_path / "shared" / store.STORE_FILENAME
    looker, the_pass = store.open(path), store.open(path)
    try:
        assert store.catch_up(looker, root, by_hand) == 1
        looker.execute("PRAGMA busy_timeout = 0")
        the_pass.execute("BEGIN IMMEDIATE")
        try:
            assert store.catch_up(looker, root, by_hand) == 1
            assert store.sync(looker, root, by_hand) == 1
            assert store.follow_the_journal(looker, root, by_hand) == 1
            assert not looker.in_transaction
        finally:
            the_pass.execute("ROLLBACK")
    finally:
        looker.close()
        the_pass.close()


# ---------------------------------------------- decision 137: the security review ----


def test_a_malformed_row_or_rule_line_is_refused_as_line_n_of_the_record(conn, root, by_hand):
    """Decision 137 (L4): one malformed index-row line, or one rule whose
    list field is not a list of words, is refused with the sentence "line N
    of the record is malformed" - one folder's problem, before a value of it
    reaches a table. A rule's list fields are held to that shape when a row
    is written into the table and when it is read back out."""
    build(conn, root, by_hand)
    path = ledger.path_for(by_hand)
    first = path.read_bytes()

    def refused_at_line_2(event: dict) -> str:
        path.write_bytes(first)
        written_elsewhere(by_hand, event)
        with pytest.raises(store.StoreError) as refused:
            store.sync(conn, root, by_hand)
        said_so = str(refused.value)
        assert "line 2 of the record is malformed" in said_so, said_so
        assert "not applied past it" in said_so
        return said_so

    stamp = ledger.stamp()
    assert "not a row" in refused_at_line_2({
        ledger.EVENT_KEY: ledger.IMPORTED, ledger.AT_KEY: stamp,
        ledger.KEY_KEY: A_ROW_ORIGINAL, ledger.ROW_KEY: "w2.pdf"})
    assert repr(ledger.KEY_KEY) in refused_at_line_2({
        ledger.EVENT_KEY: ledger.IMPORTED, ledger.AT_KEY: stamp, ledger.ROW_KEY: a_row()})
    rule = rule_to_json(ITEMS[0])
    said_so = refused_at_line_2({
        ledger.EVENT_KEY: ledger.RULES_CHANGED, ledger.AT_KEY: stamp,
        ledger.RULES_KEY: [{**rule, "any_keywords": "W-2"}], ledger.REMOVED_KEY: []})
    assert "'any_keywords'" in said_so and "not a list of words" in said_so
    path.write_bytes(first)
    store.sync(conn, root, by_hand)                   # the record as it was still reads

    # Written: the table refuses a row whose list is a string.
    with pytest.raises(store.StoreError, match="not a list of words"):
        store._write_rule(conn, id_of(conn, by_hand), {**rule, "required_keywords": "W-2"})
    # Read: a column that holds a string comes back refused, never as letters.
    conn.execute('UPDATE requests SET any_keywords = ? WHERE engagement_id = ?',
                 (json.dumps("W-2"), id_of(conn, by_hand)))
    with pytest.raises(store.StoreError, match="not a list of words"):
        store.rules(conn, by_hand)
    with pytest.raises(ValueError, match="not a list of words"):
        rule_from_json({**rule, "any_keywords": "W-2"})


def test_a_journal_rewritten_to_the_same_length_is_refused_by_sync_and_by_record(
        conn, root, by_hand):
    """Decision 137 (A3): a rewrite or a reorder of the journal that keeps
    its line count - a sync client resolving a conflict - is refused, by
    the sentence a truncated journal gets, and nothing is applied: by
    ``sync``, by the pass's full catch-up and its no-lock look (equal
    counts with a different chain is never "nothing to do", SPEC §5.0), by
    a reader whose head moved, and by ``record``, which would otherwise
    append to it and bless the new head. The check names it."""
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, ledger.new(
            ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed", identifier="A01")))
        store.record(conn, by_hand, ledger.new(
            ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row(decision="Needs Review")))
    assert [row["decision"] for row in store.documents(conn, by_hand)] == ["Needs Review"]
    path = ledger.path_for(by_hand)
    lines = path.read_bytes().split(b"\n")
    first, filed, parked = lines[0], lines[1], lines[2]
    events = unlinked(ledger.read_events(by_hand))
    path.write_bytes(b"\n".join([first, parked, filed]) + b"\n")     # reordered, same length

    # The link in every line refuses a reorder first (decision 159).
    for reading in (store.sync, store.catch_up, store.follow_the_journal):
        with pytest.raises(ledger.LedgerError, match="line 2 does not follow the line before it"):
            reading(conn, root, by_hand)

    # A reorder whose links were made again to match - which nothing but a
    # hand that knows the chain does - is refused by the store's own chain.
    path.write_bytes(first + b"\n")
    written_elsewhere(by_hand, events[2])
    written_elsewhere(by_hand, events[1])
    sentence = "was changed behind the app's back (line 2 onward no longer matches)"
    for reading in (store.sync, store.catch_up, store.follow_the_journal):
        with pytest.raises(store.StoreError, match=re.escape(sentence)) as refused:
            reading(conn, root, by_hand)
        assert str(refused.value).endswith("Nothing was applied. " + ledger.RUN_RECOVER)
    with engagement_lock(by_hand), pytest.raises(store.StoreError, match=re.escape(sentence)):
        store.record(conn, by_hand, ledger.new(
            ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed", identifier="A01")))
    assert len(ledger.read_events(by_hand)) == 3                     # nothing appended
    assert [row["decision"] for row in store.documents(conn, by_hand)] == ["Needs Review"]
    assert any(sentence in problem for problem in said(conn, root, by_hand))

    # A rebuild would lose what this machine saw, so it is refused
    # (decision 159); recover's accepted loss is the answer - and then all is well.
    with pytest.raises(store.StoreError, match="rebuild would lose that"):
        build(conn, root, by_hand)
    store.rebuild_engagement(conn, root, by_hand, discard=True)
    assert said(conn, root, by_hand) == []
    assert store.sync(conn, root, by_hand) == 3


def test_a_rebuild_computes_the_applied_digest_and_an_old_store_upgrades(
        conn, root, by_hand, tmp_path):
    """Decision 137 (A3): the store keeps the running chain over the lines
    it has applied - ``d0 = ""``, ``dn = sha256(dn-1 || line n)`` over each
    line's own bytes - and a rebuild computes it as it replays. A store of
    the version before has no column for it, so it is set aside and a fresh
    one rebuilt (decision 159, E3)."""
    import hashlib

    def chain_of(folder, count):
        digest = ""
        for raw in ledger.path_for(folder).read_bytes().split(b"\n")[:count]:
            digest = hashlib.sha256(digest.encode("ascii") + raw).hexdigest()
        return digest

    def kept(folder):
        return conn.execute("SELECT applied_digest, applied_seq FROM engagements WHERE path = ?",
                            (store.engagement_path(store.key_root(folder, root), folder),)).fetchone()

    build(conn, root, by_hand)
    assert tuple(kept(by_hand)) == (chain_of(by_hand, 1), 1)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, ledger.new(
            ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed", identifier="A01")))
    assert tuple(kept(by_hand)) == (chain_of(by_hand, 2), 2)
    build(conn, root, by_hand)
    assert tuple(kept(by_hand)) == (chain_of(by_hand, 2), 2)

    old = tmp_path / "old" / store.STORE_FILENAME
    store.open(old).close()
    before = sqlite3.connect(old)
    before.execute(f"PRAGMA user_version = {REFUSED_EARLIER}")
    before.close()
    upgraded = store.open(old)              # set aside and opened fresh (decision 159, E3)
    try:
        store.rebuild_engagement(upgraded, root, by_hand)
        assert upgraded.execute("SELECT applied_digest FROM engagements").fetchone()[0] \
            == chain_of(by_hand, 2)
    finally:
        upgraded.close()


# --------------------------------------------- decision 142: the Asked mark ----


def test_a_row_written_without_asked_reads_as_asked(conn, root, by_hand):
    """Every row a journal holds from before decision 142 was a row a person
    ticked, so a line without the mark folds to asked. The store is at the
    new version, rebuilt from that journal, and agrees with it; the list
    read back and saved unchanged records nothing."""
    events = unlinked(ledger.read_events(by_hand))       # a journal from before 142 and 159
    for event in events:
        for row in event.get(ledger.RULES_KEY) or []:
            row.pop("asked", None)
    store.forget(conn, by_hand)          # a store, and a checkpoint, that never met it
    ledger.path_for(by_hand).write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    assert "asked" not in ledger.path_for(by_hand).read_text(encoding="utf-8")

    build(conn, root, by_hand)
    build(store.connect(), root, by_hand)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION == 20
    assert all(row["asked"] is True for row in store.rules(conn, by_hand))
    assert all(item.asked for item in load_manifest(by_hand))
    assert store.check(conn, root, by_hand) == []

    before = ledger.path_for(by_hand).read_bytes()
    assert save_rules(by_hand, load_manifest(by_hand), load_engagement_info(by_hand)).recorded is False
    assert ledger.path_for(by_hand).read_bytes() == before


# ------------------------------------------ decision 144: the short title ----


def test_a_row_written_without_a_short_title_reads_as_blank(conn, root, by_hand):
    """Every row a journal holds from before decision 144 has no short
    title, so a line without it folds to blank - which derives the short
    name from the document title. The store is at the current version, rebuilt
    from that journal, and agrees with it; the list read back and saved
    unchanged records nothing."""
    events = unlinked(ledger.read_events(by_hand))       # a journal from before 142 and 159
    for event in events:
        for row in event.get(ledger.RULES_KEY) or []:
            row.pop("short_title", None)
    store.forget(conn, by_hand)          # a store, and a checkpoint, that never met it
    ledger.path_for(by_hand).write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    assert "short_title" not in ledger.path_for(by_hand).read_text(encoding="utf-8")

    build(conn, root, by_hand)
    build(store.connect(), root, by_hand)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION == 20
    assert all(item.short_title == "" for item in load_manifest(by_hand))
    assert all(item.short_name for item in load_manifest(by_hand))
    assert store.check(conn, root, by_hand) == []

    before = ledger.path_for(by_hand).read_bytes()
    assert save_rules(by_hand, load_manifest(by_hand), load_engagement_info(by_hand)).recorded is False
    assert ledger.path_for(by_hand).read_bytes() == before


# -------------------------------------- the engine's refusal is a class (189) ----


def test_a_locked_database_is_a_store_error_with_its_code(tmp_path, monkeypatch):
    """A-9: another connection holds the write lock past the busy timeout.
    The pass hears a StoreError it already catches, with SQLite's own name
    for the error as its code, and a sentence that quotes no path."""
    path = tmp_path / "app" / store.STORE_FILENAME
    monkeypatch.setattr(store, "BUSY_TIMEOUT_MS", 50)
    holder = store.open(path)
    holder.execute("BEGIN IMMEDIATE")
    waiter = store.open(path)
    try:
        with pytest.raises(store.StoreError) as refused:
            with store._transaction(waiter):
                pass
    finally:
        holder.execute("ROLLBACK")
        holder.close()
        waiter.close()
    assert isinstance(refused.value, store.StoreUnavailable)
    assert refused.value.code == "SQLITE_BUSY"
    assert str(refused.value) == "the database could not be used (SQLITE_BUSY)"
    assert str(tmp_path) not in str(refused.value)
    assert isinstance(refused.value.__cause__, sqlite3.OperationalError)


def test_a_file_that_is_not_a_database_is_a_store_error_not_a_raw_one(tmp_path):
    path = tmp_path / "app" / store.STORE_FILENAME
    path.parent.mkdir(parents=True)
    path.write_bytes(b"this was never a database, " * 200)
    with pytest.raises(store.StoreUnavailable) as refused:
        store.open(path)
    assert refused.value.code == "SQLITE_NOTADB"


def test_a_row_read_that_fails_mid_query_is_a_store_error_too(tmp_path):
    conn = store.open(tmp_path / "app" / store.STORE_FILENAME)
    try:
        rows = conn.execute("SELECT 1 UNION ALL SELECT abs(-9223372036854775808)")
        with pytest.raises(store.StoreUnavailable):
            list(rows)
    finally:
        conn.close()


# ----------------------------------- the record is untrusted input (187) ----


def _forge(engagement, event: dict) -> None:
    """Put one line in the journal the way another machine would: past the
    store, without asking it. Linked to the line before (decision 159), so
    it is the store's admission that judges it and not the ledger's link -
    a hand edit without the link is refused by the reader before a value is
    looked at."""
    written_elsewhere(engagement, event)


def _tables(conn, engagement) -> list:
    mine = (id_of(conn, engagement),)
    return [
        [tuple(row) for row in conn.execute(
            f"SELECT * FROM {table} WHERE engagement_id = ? ORDER BY rowid", mine)]
        for table in ("documents", "requests")
    ] + [tuple(conn.execute("SELECT * FROM engagements WHERE id = ?", mine).fetchone())]


def _a_rule(**fields) -> dict:
    return {**rule_to_json(ITEMS[0]), **fields}


IMPOSSIBLE = [
    ("expected_count", ledger.new(ledger.RULES_CHANGED, rules=[_a_rule(expected_count=10**20)])),
    ("expected_count", ledger.new(ledger.RULES_CHANGED, rules=[_a_rule(expected_count="x")])),
    ("due", ledger.new(ledger.RULES_CHANGED, rules=[], info={"due": "2025-02-30"})),
    ("reminders", ledger.new(ledger.RULES_CHANGED, rules=[], info={"reminders": "no"})),
    ("received", ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(received="13/45/2025"))),
    ("size_kb", ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(size_kb="x"))),
    ("digest", ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(digest=5))),
    ("file_count", ledger.new(ledger.SCANNED, statuses={
        "A01": {"status": Status.MISSING, "file_count": -1}})),
    ("at", {**learned("A01", "lender"), ledger.AT_KEY: 12345}),
    # Decision 190's columns, held to 187's rule: a cause's code is one this
    # version names, and the client's subfolder is one line of text.
    ("code", ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(code="not-a-cause"))),
    ("subfolder", ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(subfolder="Scans\n2025"))),
    ("subfolder", ledger.new(ledger.FILED, key=A_ROW_ORIGINAL,
                             row=a_row(subfolder="Scans\\W2\u202efdp.exe"))),
    ("subfolder", ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(subfolder="a/../../x"))),
    ("note_codes", ledger.new(ledger.SCANNED, statuses={
        "A01": {"status": Status.MISSING, "note_codes": "not-a-cause"}})),
    ("at", {**learned("A01", "lender"), ledger.AT_KEY: "1900-01-01T00:00:00Z"}),
]


@pytest.mark.parametrize("subfolder", ["a/../../x", "..", "Scans\\.", "Scans\\..\\..", "C:\\Scans"])
def test_a_subfolder_part_that_is_a_path_of_its_own_is_a_name_no_writer_wrote(conn, root, by_hand, subfolder):
    """The filer writes a client's subfolder as its folder names joined with
    a backslash, each one folder name, so a part holding "/", naming "." or
    "..", or a drive is refused at the door in and on every read, even
    though the recorded-name rule alone would keep it (the review's S3,
    decision 190). A subfolder the filer does write is admitted - a client's
    folder named like a year, or beginning with "_" or "(", included, which
    decision 188's household-name rule would refuse."""
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        for written in ("Scans\\2025", "2025\\_old\\(scans) \u00a0x"):
            store.record(conn, by_hand, ledger.new(ledger.FILED, key=A_ROW_ORIGINAL,
                                                   row=a_row(subfolder=written)))
        with pytest.raises(store.StoreError) as refused:
            store.record(conn, by_hand, ledger.new(ledger.FILED, key=A_ROW_ORIGINAL,
                                                   row=a_row(subfolder=subfolder)))
    assert "'subfolder'" in str(refused.value), f"{subfolder!r} was admitted: {refused.value}"


@pytest.mark.parametrize("field, event", IMPOSSIBLE, ids=[f"{field}-{n}" for n, (field, _) in
                                                         enumerate(IMPOSSIBLE)])
def test_an_impossible_value_is_refused_before_any_table_is_touched(conn, root, by_hand, field, event):
    """Decision 187 (A-6, A-10): a line of the right shape carrying a value
    no writer writes - a count past SQLite, a date no calendar has, "no" for
    a flag, a stamp that is a number - is refused by the one admission, at
    the door in and on every read, naming the field; the journal and every
    table stay as they were."""
    build(conn, root, by_hand)
    before = _tables(conn, by_hand)
    lines = len(ledger.read_events(by_hand))

    with engagement_lock(by_hand):
        with pytest.raises(store.StoreError) as refused:
            store.record(conn, by_hand, event)
    assert f"'{field}'" in str(refused.value) and "nothing was written" in str(refused.value)
    assert len(ledger.read_events(by_hand)) == lines

    _forge(by_hand, event)
    with pytest.raises(store.StoreError) as refused:
        store.sync(conn, root, by_hand)
    said_so = str(refused.value)
    assert "is malformed" in said_so and f"'{field}'" in said_so and f"line {lines + 1}" in said_so
    assert _tables(conn, by_hand) == before


def test_a_step_that_escapes_its_return_is_refused_at_admission(conn, root, by_hand):
    """Decision 180 recommended it and 187 does it: the store refuses a step
    outside its return's places before the line is in the journal, so a
    recovery never meets it. The reason is the layout's code."""
    build(conn, root, by_hand)
    lines = len(ledger.read_events(by_hand))
    for step, code in [
        ({ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: "/etc/passwd",
          ledger.TO_KEY: "Prepared/x.pdf", ledger.DIGEST_KEY: "ab" * 32}, "absolute"),
        ({ledger.OP_KEY: ledger.OP_MOVE, ledger.FROM_KEY: A_ROW_ORIGINAL,
          ledger.TO_KEY: "../../../../Clients/Other Household/Drop files here/w2.pdf",
          ledger.DIGEST_KEY: "ab" * 32}, "other-household"),
        ({ledger.OP_KEY: ledger.OP_REMOVE, ledger.FROM_KEY: "../../../../../w2.pdf",
          ledger.DIGEST_KEY: "ab" * 32}, "above-root"),
        ({ledger.OP_KEY: ledger.OP_REMOVE, ledger.FROM_KEY: A_ROW_ORIGINAL,
          ledger.DIGEST_KEY: "ab" * 32}, "client-tree"),
    ]:
        moving = ledger.new(ledger.MOVING, key=A_ROW_ORIGINAL, ops=[step], by=ledger.BY_PASS)
        with engagement_lock(by_hand), pytest.raises(store.StoreError) as refused:
            store.record(conn, by_hand, moving)
        assert f"outside this return's places ({code})" in str(refused.value)
    assert len(ledger.read_events(by_hand)) == lines


def test_a_moving_line_in_a_households_record_is_refused():
    """A household has no steps, so its record carries none."""
    from tracker.layout import PRIVATE_TREE

    moving = ledger.new(ledger.MOVING, key="k", ops=[], by=ledger.BY_PASS)
    with pytest.raises(store.StoreError, match="in a household's record, which has no steps"):
        store._refuse_a_malformed_line(moving, 2, f"{PRIVATE_TREE}/Smith Family",
                                       kind=store.KIND_HOUSEHOLD)
    store._refuse_a_malformed_line(moving, 2, f"{PRIVATE_TREE}/Smith Family/2025/1040 - Smith",
                                   kind=store.KIND_RETURN)


def test_a_label_that_is_not_one_segment_is_refused_at_admission(conn, root, by_hand):
    """A household or a return label is joined onto a path somewhere, so one
    that is a path of its own - a separator, a climb, a drive - is refused
    at the door, naming the field and the layout's reason - since decision
    188 the one name rule a person's typing gets, so an invisible or a
    look-alike-script label is refused here too."""
    from tracker.layout import NAME_FIRST_CHARACTER, NAME_ILLEGAL, NAME_SCRIPTS, PRIVATE_TREE

    household = f"{PRIVATE_TREE}/Smith Family"
    for event, field, code in [
        (ledger.new(ledger.RULES_CHANGED, rules=[], info={"household": "../Jones"}), "household",
         NAME_ILLEGAL),
        (ledger.new(ledger.RULES_CHANGED, rules=[], info={"return_name": ".."}), "return_name",
         NAME_FIRST_CHARACTER),
        (ledger.new(ledger.HOUSEHOLD_CHANGED, household={"name": "C:Jones"}), "name", NAME_ILLEGAL),
        (ledger.new(ledger.HOUSEHOLD_CHANGED, household={"feeds": [
            {"household": "Jones/..", "return_name": "1040 - Jones"}]}), "feeds.household",
         NAME_ILLEGAL),
        (ledger.new(ledger.HOUSEHOLD_CHANGED, household={"name": "J\u043ehnson"}), "name",
         NAME_SCRIPTS.format(first="Latin", second="Cyrillic")),
    ]:
        with pytest.raises(store.StoreError) as refused:
            store._refuse_a_malformed_line(event, 2, household, kind=store.KIND_HOUSEHOLD)
        assert f"'{field}' that is not one folder name ({code})" in str(refused.value)
    build(conn, root, by_hand)
    with engagement_lock(by_hand), pytest.raises(store.StoreError, match="not one folder name"):
        store.record(conn, by_hand, ledger.new(ledger.RULES_CHANGED, rules=[],
                                               info={"household": "a/b"}))


def test_a_refusal_never_quotes_the_value_it_refused(by_hand):
    """Security principle 7: the value is whatever the line said, so the
    sentence names the field and the class of problem and never repeats it."""
    marker = "Marker-7731"
    where = "J Park & Associates/Smith Family/2025/1040 - Smith"
    for event in [
        ledger.new(ledger.RULES_CHANGED, rules=[marker]),
        ledger.new(ledger.RULES_CHANGED, rules=[_a_rule(date_pattern=f"({marker}+)+")]),
        ledger.new(ledger.RULES_CHANGED, rules=[], info={"people": marker}),
        ledger.new(ledger.RULES_CHANGED, rules=[], removed=[{marker: 1}]),
        ledger.new(ledger.MOVING, key="k", by=ledger.BY_PASS, ops=[marker]),
        ledger.new(ledger.MOVING, key="k", by=ledger.BY_PASS, ops=[{ledger.OP_KEY: marker}]),
        ledger.new(ledger.MOVING, key="k", by=ledger.BY_PASS, ops=[
            {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: f"/{marker}.pdf",
             ledger.TO_KEY: "Prepared/x.pdf", ledger.DIGEST_KEY: "ab" * 32}]),
        ledger.new(ledger.SCANNED, statuses={marker: marker}),
        ledger.new(ledger.KEYWORD_LEARNED, identifier="A01", keyword=[marker]),
        ledger.new(ledger.HOUSEHOLD_CHANGED, household={"members": [{marker: 1}]}),
        ledger.new(ledger.HOUSEHOLD_CHANGED, household={"feeds": marker}),
        ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(digest=marker)),
        # The review's S2: an event name this version does not know, and the
        # fields a line that carries nothing carries.
        {ledger.EVENT_KEY: f"{marker}-event", ledger.AT_KEY: 5},
        {ledger.EVENT_KEY: ledger.SHARING_CONFIRMED, ledger.AT_KEY: ledger.stamp(), marker: 1},
    ]:
        with pytest.raises(store.StoreError) as refused:
            store._refuse_a_malformed_line(event, 2, where)
        assert marker not in str(refused.value), str(refused.value)


def test_the_store_check_names_a_line_the_gate_now_refuses(conn, root, by_hand, monkeypatch):
    """A line an earlier version applied that today's rule refuses is named
    by ``check`` on the day of the upgrade (decision 187), without the store
    being deleted to find it: every line of every journal is judged again."""
    build(conn, root, by_hand)
    runaway = ledger.new(ledger.RULES_CHANGED, rules=[_a_rule(date_pattern=r"(\d+)+x")])
    monkeypatch.setattr(store, "_refuse_a_malformed_line", lambda *args, **kwargs: None)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, runaway)
    monkeypatch.undo()

    problems = store.check(conn, root, by_hand)

    assert len(problems) == 1
    assert "line 2 of the record is malformed" in problems[0] and "'date_pattern'" in problems[0]


def _applied_before_the_rule(conn, root, by_hand, monkeypatch):
    """A return with a line an earlier version applied that today's
    admission refuses - a Date Pattern that could run away, at line 2 - as
    a version-18 store left it: ``admitted_by`` 0, judged by no admission
    this version knows."""
    build(conn, root, by_hand)
    runaway = ledger.new(ledger.RULES_CHANGED, rules=[_a_rule(date_pattern=r"(\d+)+x")])
    monkeypatch.setattr(store, "_refuse_a_malformed_line", lambda *args, **kwargs: None)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, runaway)
    monkeypatch.undo()
    conn.execute("UPDATE engagements SET admitted_by = 0")


def admitted_by(conn, folder):
    return conn.execute("SELECT admitted_by FROM engagements WHERE path = ?",
                        (key_of(folder),)).fetchone()[0]


def test_an_applied_line_the_rule_now_refuses_stops_its_household(conn, root, by_hand, monkeypatch):
    """Decision 209, R3b: the store applies only lines past what it applied,
    so a line an earlier version applied was never judged again. Now the
    sync judges every applied line again when the row's admission is older
    than today's, and a refused line stops its household exactly as a new
    malformed line does - by the same sentence, from every door, pass after
    pass - with nothing written: not the version, and no line appended."""
    _applied_before_the_rule(conn, root, by_hand, monkeypatch)
    sentence = "line 2 of the record is malformed"

    for _ in range(2):
        for reading in (store.sync, store.catch_up, store.follow_the_journal):
            with pytest.raises(store.StoreError, match=sentence):
                reading(conn, root, by_hand)
    assert admitted_by(conn, by_hand) == 0

    before = ledger.path_for(by_hand).read_bytes()
    with engagement_lock(by_hand), pytest.raises(store.StoreError, match=f"{sentence}.*nothing was written"):
        store.record(conn, by_hand, ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row()))
    assert ledger.path_for(by_hand).read_bytes() == before


def test_a_repaired_line_lets_the_household_go_on_and_is_not_judged_again(conn, root, by_hand, monkeypatch):
    """Decision 209, R3b: once the record holds no line the rule refuses -
    here a row a version-18 store left, whose lines all pass - the next sync
    judges them, passes, and records today's admission in the same
    transaction; after that no sync judges an applied line again."""
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row()))
    conn.execute("UPDATE engagements SET admitted_by = 0")

    assert store.sync(conn, root, by_hand) == 2
    assert admitted_by(conn, by_hand) == store.ADMISSION_VERSION

    def judged(*args, **kwargs):
        raise AssertionError("an applied line was judged again")

    monkeypatch.setattr(store, "_judge_the_applied_lines", judged)
    for reading in (store.sync, store.catch_up, store.follow_the_journal):
        assert reading(conn, root, by_hand) == 2
    with engagement_lock(by_hand):
        store.record(conn, by_hand, ledger.new(ledger.FILED, key=A_ROW_ORIGINAL,
                                               row=a_row(decision="Filed", identifier="A01")))
    assert said(conn, root, by_hand) == []


def test_a_store_at_version_18_gains_admitted_by_in_place(conn, root, by_hand, tmp_path):
    """Decision 209, R3b: version 19's column is added where the file
    stands, like 204's - nothing set aside, the verdict cache kept - and
    every row it held reads 0, so its applied lines are judged at its next
    sync, which then records today's admission."""
    build(conn, root, by_hand)
    path = tmp_path / "app" / store.STORE_FILENAME
    conn.close()
    written = sqlite3.connect(path)
    for statement in AS_AT_18:
        written.execute(statement)
    written.execute("PRAGMA user_version = 18")
    written.commit()
    written.close()

    upgraded = store.open(path)
    try:
        assert upgraded.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION == 20
        assert not list(path.parent.glob(f"{store.STORE_FILENAME}.v*.old*"))
        assert admitted_by(upgraded, by_hand) == 0
        store.sync(upgraded, root, by_hand)
        assert admitted_by(upgraded, by_hand) == store.ADMISSION_VERSION
    finally:
        upgraded.close()


def test_a_new_engagement_is_admitted_by_construction(conn, root, by_hand):
    """Decision 209, R3b: a first build and a rebuild put every line through
    the door as they apply it, so the row is inserted as judged by today's
    admission."""
    store.catch_up(conn, root, by_hand)
    assert admitted_by(conn, by_hand) == store.ADMISSION_VERSION
    conn.execute("UPDATE engagements SET admitted_by = 0")
    build(conn, root, by_hand)
    assert admitted_by(conn, by_hand) == store.ADMISSION_VERSION


#: The admission, part by part (:func:`admission_closure`), as the first 16
#: hexadecimal characters of each part's SHA-256, by the version it is. A
#: change to any part moves its digest; the test below names every part
#: that moved and says which of two things to do.
ADMISSION_PIN: dict[int, dict[str, str]] = {2: {
    "tracker.layout.CLIENTS": "3b8264d65abeec66",
    "tracker.layout.CLIENTS_TREE": "488530d6164e0dd6",
    "tracker.layout.CLIENT_HOUSEHOLD": "2c784f90e61ac610",
    "tracker.layout.HOUSEHOLD": "8de5259835758e72",
    "tracker.layout.INBOX": "d9c4d1b7a70cb6f2",
    "tracker.layout.INBOX_DIR_NAME": "919dcb2c2a774098",
    "tracker.layout.IN_INBOX": "fc74c5d3e9ae9444",
    "tracker.layout.IN_OPENED": "633c5d64586b470a",
    "tracker.layout.IN_ORIGINALS": "20496354d6f1b26b",
    "tracker.layout.IN_RETURN": "155a1bfd542aaa0d",
    "tracker.layout.LOOK_ALIKES": "54c49454cf2f5689",
    "tracker.layout.MISPLACED": "b8ca0cd70606f6d7",
    "tracker.layout.NAMELESS": "1bad7ce20105964a",
    "tracker.layout.NAME_COMPATIBILITY": "ec65d3d71fd72b3d",
    "tracker.layout.NAME_DEVICE": "620b97404635bcec",
    "tracker.layout.NAME_EMPTY": "aa82b128dcf1c993",
    "tracker.layout.NAME_FIRST_CHARACTER": "bd62babfb5664dc1",
    "tracker.layout.NAME_ILLEGAL": "305df1e9431d3276",
    "tracker.layout.NAME_INVISIBLE": "2401333e2c513d23",
    "tracker.layout.NAME_LAYOUT_WORD": "978aa80c1fbb2b52",
    "tracker.layout.NAME_MAX_CHARS": "48449a14a4ff7d79",
    "tracker.layout.NAME_SCRIPTS": "3de824b29b62bb49",
    "tracker.layout.NAME_TOO_LONG": "7a5e00d8497fbe2d",
    "tracker.layout.NAME_TRAILING": "7fafe7cda3544c33",
    "tracker.layout.OPENED": "33bdc49eaabcbced",
    "tracker.layout.OPENED_DIR_NAME": "5ef673f341874a6f",
    "tracker.layout.ORIGINALS": "535087da73c5868d",
    "tracker.layout.OUTSIDE": "2f2e7ba21585ff28",
    "tracker.layout.PRIVATE": "68a262e0c0fb929f",
    "tracker.layout.PRIVATE_TREE": "27c7f0479a0c896f",
    "tracker.layout.RETURN": "08633b69eed18c1b",
    "tracker.layout.ROOT": "11ccb349ede85740",
    "tracker.layout.STEP_ABOVE_ROOT": "1385e84ae7f46b2d",
    "tracker.layout.STEP_ABSOLUTE": "f523898e69fbc750",
    "tracker.layout.STEP_BLANK": "a4e9e11cd18fd75b",
    "tracker.layout.STEP_CLIENT_TREE": "5f51b518f9526119",
    "tracker.layout.STEP_NOT_A_PLACE": "d1aa6f26861ccbee",
    "tracker.layout.STEP_NOT_A_RETURN": "1e7d015db6355c80",
    "tracker.layout.STEP_OTHER_HOUSEHOLD": "a0f05df5e57d787b",
    "tracker.layout.STEP_OTHER_YEAR": "7994492387ba5850",
    "tracker.layout.WINDOWS_ILLEGAL_CHARS": "0852803faa2a184a",
    "tracker.layout.WINDOWS_RESERVED_NAMES": "99bf9abac32f89f2",
    "tracker.layout.WINDOWS_RESERVED_NAMES_TEXT": "c9d9ad8d312ac5a8",
    "tracker.layout.YEAR": "74c6b2f8351bcc6d",
    "tracker.layout._ASCII_LOOK_ALIKES": "5333fd34ff62ce29",
    "tracker.layout._IGNORABLE_CODES": "999fbf22e2feeb49",
    "tracker.layout._INVISIBLE_CATEGORIES": "bb62d3360fd14a4d",
    "tracker.layout._LAYOUT_WORD_KEYS": "a6d47e2209691833",
    "tracker.layout._ONE_SCRIPT": "17235d2097441c94",
    "tracker.layout._character": "bd5a8cc4e82855fc",
    "tracker.layout._parts": "a2847013a67202c7",
    "tracker.layout._script": "f890f9bb62d24799",
    "tracker.layout.is_invisible": "2b17b033d61a3df2",
    "tracker.layout.is_reserved_name": "3ee144cf8f5c095d",
    "tracker.layout.is_year_folder": "c89c110db3cb607d",
    "tracker.layout.name_key": "749d88cbbd6eb3c3",
    "tracker.layout.parts_below": "522d9b67dfe50b6a",
    "tracker.layout.place_of": "fc1a78ab7179dd32",
    "tracker.layout.place_problem": "2e94883c849c9d08",
    "tracker.layout.recorded_name": "84bfdf3a851f4652",
    "tracker.layout.recorded_subfolder_part": "50620c73d7ae6dab",
    "tracker.layout.root_of": "a6c7013a757965b4",
    "tracker.layout.segment_problem": "13e273e844d2cc2b",
    "tracker.ledger.ACCEPTED_KEY": "f4764fc7a8ddd588",
    "tracker.ledger.ALSO_KEY": "da42922852e5dfcd",
    "tracker.ledger.ASKED_KEY": "46da5b49eea2fbee",
    "tracker.ledger.AT_KEY": "22eb1fa0c521db09",
    "tracker.ledger.DIGEST_KEY": "889a0f98aa32537e",
    "tracker.ledger.DRAFTED": "ef02a62df7dc350b",
    "tracker.ledger.DRAFT_APPROVED": "41bf68b11dd88d88",
    "tracker.ledger.EVENTS": "c6d719a66bc0b51d",
    "tracker.ledger.EVENT_KEY": "9e0d5d1c8d94a5b6",
    "tracker.ledger.FILE_KEY": "0efde3f4308de780",
    "tracker.ledger.FINGERPRINT_KEY": "7df2d13d670e5ed4",
    "tracker.ledger.FOLDER_NAME_ACCEPTED": "b7b92a8807e8bbf9",
    "tracker.ledger.FORMAT_KEY": "04fc6c808adf51ac",
    "tracker.ledger.FROM_KEY": "8ecb478c3dc0d3ae",
    "tracker.ledger.HELD_KEY": "85c4d432c47707ee",
    "tracker.ledger.HOST_KEY": "e293b75405af70cd",
    "tracker.ledger.HOUSEHOLD_CHANGED": "783c776c223a869f",
    "tracker.ledger.HOUSEHOLD_KEY": "8de5259835758e72",
    "tracker.ledger.IDENTIFIER_KEY": "123a87f051936a7e",
    "tracker.ledger.INFO_KEY": "ef3370879a96cf2e",
    "tracker.ledger.KEYWORD_KEY": "a51a9ff6a628d820",
    "tracker.ledger.KEYWORD_LEARNED": "7a5d6590fc40e09a",
    "tracker.ledger.KEYWORD_UNLEARNED": "ce11d4a4c4da44a9",
    "tracker.ledger.KEY_KEY": "632a3e84412d6ea8",
    "tracker.ledger.LINE_KEYS": "bfa2973d92dd93ad",
    "tracker.ledger.LINK_KEY": "67b4e6e1e90cbc98",
    "tracker.ledger.MOVE_ABANDONED": "a11db9ac01cd5285",
    "tracker.ledger.MOVING": "d290155f3097fcde",
    "tracker.ledger.OPS_KEY": "2c35289e43246c9f",
    "tracker.ledger.OP_COPY": "477c02e96b3c4061",
    "tracker.ledger.OP_KEY": "b27b68850018781c",
    "tracker.ledger.OP_MOVE": "c4a4adaf72f566c1",
    "tracker.ledger.OP_REMOVE": "e8c2c1465f168081",
    "tracker.ledger.REASON_KEY": "ffa78aeaf553b544",
    "tracker.ledger.RECORD_FORMAT": "6b86b273ff34fce1",
    "tracker.ledger.RELEASED": "81acce4087249f66",
    "tracker.ledger.REMOVED_KEY": "760f3c525ed93b07",
    "tracker.ledger.RETIRED_EVENTS": "ca06b9854a7990f9",
    "tracker.ledger.ROW_EVENTS": "b53cc1cb7387825b",
    "tracker.ledger.ROW_KEY": "e4d99047ca6a3721",
    "tracker.ledger.RULES_CHANGED": "e4535fc89d8ef96d",
    "tracker.ledger.RULES_IMPORTED": "cddb10ca0e4c2100",
    "tracker.ledger.RULES_KEY": "a29e7581476cd7ad",
    "tracker.ledger.SCANNED": "7e17f4790bff13d5",
    "tracker.ledger.SHARING_CONFIRMED": "c8027ef3eb13f5e3",
    "tracker.ledger.STAGE_KEY": "874095181f94a63d",
    "tracker.ledger.STATUSES_KEY": "18c7785691d58b80",
    "tracker.ledger.TEXT_FINGERPRINT_KEY": "0db6b5095dc3896e",
    "tracker.ledger.TO_KEY": "e28f3243b469e21d",
    "tracker.ledger.WAS_KEY": "1d383f963e096e21",
    "tracker.ledger.op_ends": "a4e5e845ab4c8deb",
    "tracker.reasons.KNOWN_CODES": "4ad3f21d00c7f8e5",
    "tracker.records.BLANK_BOUNDS": "cec8e55a02712202",
    "tracker.records.CANDIDATE_SEP": "3c01b9ef061065a0",
    "tracker.records.COUNT_BOUNDS": "66fbd6100ed5379b",
    "tracker.records.DATE_BOUNDS": "14ca9c3c8c63da08",
    "tracker.records.DATE_FIELDS": "f0aaa0cb84de4063",
    "tracker.records.DATE_PATTERN_ALTERNATES": "6d1924b141e16df5",
    "tracker.records.DATE_PATTERN_BOUND_MAX": "f5ca38f748a1d6ea",
    "tracker.records.DATE_PATTERN_COST_MAX": "b552e632666bbf61",
    "tracker.records.DATE_PATTERN_MAX": "27badc983df1780b",
    "tracker.records.DATE_PATTERN_NESTED": "7b1330f7983d042e",
    "tracker.records.DATE_PATTERN_NOT_A_REGEX": "a158e00f56bf6ba7",
    "tracker.records.DATE_PATTERN_OPEN_MAX": "6b86b273ff34fce1",
    "tracker.records.DATE_PATTERN_OPEN_WIDTH": "0604cd3138feed20",
    "tracker.records.DATE_PATTERN_REFERS_BACK": "25a2057a272ff94c",
    "tracker.records.DATE_PATTERN_REPEATS_MAX": "4e07408562bedb8b",
    "tracker.records.DATE_PATTERN_TOO_COSTLY": "3e2d8a14b8d6a5a6",
    "tracker.records.DATE_PATTERN_TOO_LONG": "02239fb8cdceefd8",
    "tracker.records.DATE_PATTERN_TOO_MANY": "ba11446dcfecda24",
    "tracker.records.DATE_PATTERN_TOO_MANY_OPTIONAL": "eb3c2f5771c5d09f",
    "tracker.records.DATE_PATTERN_TOO_MANY_WAYS": "a322d9761b272d91",
    "tracker.records.DATE_PATTERN_TOO_OPEN": "fcaa25330d84e4d0",
    "tracker.records.DATE_PATTERN_TOO_WIDE": "f7af15030b186a35",
    "tracker.records.DATE_PATTERN_VARIABLE_MAX": "2c624232cdd22177",
    "tracker.records.DATE_PATTERN_WAYS_MAX": "ca902d4a8acbdea1",
    "tracker.records.DATE_YEAR_MAX": "4f5131ea0c5a3e7f",
    "tracker.records.DATE_YEAR_MIN": "e41d64db5703c644",
    "tracker.records.DIGEST_BOUNDS": "677bb2233d3c0d23",
    "tracker.records.FEED_REFUSED": "d601e93b18987f24",
    "tracker.records.FLAG_BOUNDS": "2bfdeea59997694f",
    "tracker.records.HOST_BOUNDS": "72219f0e2bcda110",
    "tracker.records.HOST_MAX": "a68b412c4282555f",
    "tracker.records.LONG_TEXT_BOUNDS": "3de4da1af0b30ef2",
    "tracker.records.LONG_TEXT_MAX": "876c9b16254e157d",
    "tracker.records.MAX_EXPECTED_COUNT": "888df25ae3577242",
    "tracker.records.MAX_FILE_COUNT": "888df25ae3577242",
    "tracker.records.MAX_ROW": "888df25ae3577242",
    "tracker.records.MAX_ROW_SIZE_KB": "02bfbb85ecfba2af",
    "tracker.records.MAX_SIZE_KB": "50b4b069390c1d79",
    "tracker.records.MAX_STAGE": "19581e27de7ced00",
    "tracker.records.MIN_EXPECTED_COUNT": "6b86b273ff34fce1",
    "tracker.records.MIN_SIZE_KB_FLOOR": "5feceb66ffc86f38",
    "tracker.records.MIN_SPELLING_WORDS": "d4735e3a265e16ee",
    "tracker.records.NAME_BOUNDS": "fab0c3e598d1038c",
    "tracker.records.NUMBER_BOUNDS": "d7d2f825d092e462",
    "tracker.records.OVERRIDE_BOUNDS": "22a3650c5fc6e021",
    "tracker.records.PERSON_KINDS": "11ac10e2383de5cc",
    "tracker.records.RULE_FLAG_FIELDS": "c500b9a01ed742b3",
    "tracker.records.RULE_LIST_FIELDS": "8b3d25ca8662bd02",
    "tracker.records.SHORT_TITLE_MAX": "f5ca38f748a1d6ea",
    "tracker.records.STAMP_BOUNDS": "7c7cf7f161dd3671",
    "tracker.records.STAMP_YEAR_MIN": "ad1f3889d0032e7c",
    "tracker.records.TEXT_BOUNDS": "ce369c3539b412af",
    "tracker.records.TEXT_LIST_BOUNDS": "196f901bd54f0f8c",
    "tracker.records.TEXT_MAX": "40510175845988f1",
    "tracker.records.WAITS_FOR_ANSWERS": "f0615f5bcc293884",
    "tracker.records.WAITS_FOR_BOUNDS": "6f57ee0ee5ca0bbc",
    "tracker.records.WAITS_FOR_SEP": "de9881cacd5c858e",
    "tracker.records.WINDOWS_ILLEGAL_CHARS": "0852803faa2a184a",
    "tracker.records.WINDOWS_ILLEGAL_CHARS_TEXT": "e4b68ca2e1ff6518",
    "tracker.records.WINDOWS_RESERVED_NAMES_TEXT": "c9d9ad8d312ac5a8",
    "tracker.records.YEAR_MAX": "1aaf97e300d50bac",
    "tracker.records.YEAR_MIN": "e41d64db5703c644",
    "tracker.records._ENTRY_LONG_TEXT": "108c25e4b80db4c6",
    "tracker.records._ENTRY_NAMES": "5980f2d1176281a2",
    "tracker.records._ENTRY_TEXT": "68e0df1c43ff5282",
    "tracker.records._HEX_DIGEST": "286fa658d6b7911b",
    "tracker.records._INFO_LONG_TEXT": "69674950c21f7eae",
    "tracker.records._INFO_TEXT": "cbdf6035c202636d",
    "tracker.records._ISO_DATE": "3ca3c91bdac79395",
    "tracker.records._ONE_LINE_REFUSED": "f912910f93b16ff7",
    "tracker.records._REFERS_BACK": "6a5a714c08b4ca99",
    "tracker.records._REPEATS": "0429e0cc33348e07",
    "tracker.records._RULE_TEXT": "4dbd8ce696bb0f8e",
    "tracker.records._STAMP": "36e48aca67f1ef08",
    "tracker.records._field": "190cfe96c598c222",
    "tracker.records._first": "afafd6bbd03b4d5a",
    "tracker.records._is_number": "b55a28bc0ae446c7",
    "tracker.records._walk": "58be230437faa42c",
    "tracker.records._ways": "73d93a78035726fd",
    "tracker.records._width": "971b31440953101e",
    "tracker.records.count_problem": "89257d6ec9bdd711",
    "tracker.records.date_pattern_problem": "fa02803a1a99c545",
    "tracker.records.date_problem": "0bf005c4a966d7f8",
    "tracker.records.digest_problem": "217cc9c49f9a6e20",
    "tracker.records.entry_problem": "a79ea9e62a85223a",
    "tracker.records.feed_from_json": "b2e5148af638d97c",
    "tracker.records.feeds_from_json": "b108fd6888f95ec6",
    "tracker.records.flag_problem": "1082a26284942f5c",
    "tracker.records.format_waits_for": "a9f50749433f46ce",
    "tracker.records.host_problem": "7d98945bc57bd382",
    "tracker.records.household_problem": "1188cd47c1c4b37f",
    "tracker.records.identifier_problem": "f8ee13a768acea53",
    "tracker.records.info_problem": "a14147da699ad792",
    "tracker.records.is_a_spelling": "9872f0754c1f928d",
    "tracker.records.name_parts": "2fb3aa450c490a16",
    "tracker.records.name_problem": "435e57a752b587c2",
    "tracker.records.name_words": "888ff2df30e14d73",
    "tracker.records.number_problem": "b8e64da5f5e20b1a",
    "tracker.records.parse_waits_for": "fe2da49df5b9f8ce",
    "tracker.records.people_from_json": "f450ab3614ffbb7c",
    "tracker.records.person_from_json": "7e7a8fed1cb8c27a",
    "tracker.records.received_problem": "2fe803ce248363ca",
    "tracker.records.rule_row_fault": "e63ac46148a8c37f",
    "tracker.records.rule_row_problem": "bfbfa65df0936781",
    "tracker.records.short_title_problem": "cee1ccd1dc44eedd",
    "tracker.records.split_codes": "ac4f6152bb7ad6ee",
    "tracker.records.stamp_problem": "2d66f0bfa7df3a4f",
    "tracker.records.status_from_json": "18fe07346092ffad",
    "tracker.records.status_problem": "0a4507873e497b78",
    "tracker.records.text_list_problem": "5c6a2aa819ebb0cf",
    "tracker.records.text_problem": "3af72e89b781e54e",
    "tracker.records.waits_for_problem": "463d041ef7fa9219",
    "tracker.records.word_list_problem": "64d72805fbba0527",
    "tracker.settings.ENV_SETTINGS_DIR": "b654987367e5160b",
    "tracker.settings.KEY_CLIENTS_ROOT": "3b8f548e07b39dbf",
    "tracker.settings.SETTINGS_FILENAME": "ddf9dfc4d857c464",
    "tracker.settings._SETTINGS_HELD": "6c71e2207cf64f31",
    "tracker.settings._held": "379fbddee2b4b987",
    "tracker.settings._read": "9a09d08e256be9de",
    "tracker.settings.clients_root": "8fbaef8c43dcb573",
    "tracker.settings.resolved": "e42941a71b19eac8",
    "tracker.settings.settings_dir": "0468e63b780056c5",
    "tracker.settings.settings_path": "8a79e7ca2ca7f66a",
    "tracker.store.ALSO_IN": "f91e15416cd81c44",
    "tracker.store.KIND_HOUSEHOLD": "8de5259835758e72",
    "tracker.store.KIND_RETURN": "08633b69eed18c1b",
    "tracker.store.MALFORMED_LINE": "7af462b999c9799b",
    "tracker.store.RULE_LIST_FIELDS": "8b3d25ca8662bd02",
    "tracker.store.STATUS_COLUMNS": "072efbf3b12ac0bd",
    "tracker.store.UNKNOWN_EVENT": "099e89ceccd1e5e9",
    "tracker.store._engagement_row": "e7254ccc28e41fad",
    "tracker.store._line_keys_problem": "0d6016b3dab0c236",
    "tracker.store._positional_root": "f2fce089ca54ef5a",
    "tracker.store._recorded_root_over": "6447409cff0d940e",
    "tracker.store._refuse_a_malformed_line": "3691dbc864c8530f",
    "tracker.store.engagement_path": "354415605ca56669",
    "tracker.store.key_root": "13d66deeca51405a",
    "tracker.store.kind": "c5781c37870424f8",
    "tracker.store.statuses": "d99730d725daf407",
}, 3: {
    "tracker.layout.CLIENTS": "3b8264d65abeec66",
    "tracker.layout.CLIENTS_TREE": "488530d6164e0dd6",
    "tracker.layout.CLIENT_HOUSEHOLD": "2c784f90e61ac610",
    "tracker.layout.HOUSEHOLD": "8de5259835758e72",
    "tracker.layout.INBOX": "d9c4d1b7a70cb6f2",
    "tracker.layout.INBOX_DIR_NAME": "919dcb2c2a774098",
    "tracker.layout.IN_INBOX": "fc74c5d3e9ae9444",
    "tracker.layout.IN_OPENED": "633c5d64586b470a",
    "tracker.layout.IN_ORIGINALS": "20496354d6f1b26b",
    "tracker.layout.IN_RETURN": "155a1bfd542aaa0d",
    "tracker.layout.LOOK_ALIKES": "54c49454cf2f5689",
    "tracker.layout.MISPLACED": "b8ca0cd70606f6d7",
    "tracker.layout.NAMELESS": "1bad7ce20105964a",
    "tracker.layout.NAME_COMPATIBILITY": "ec65d3d71fd72b3d",
    "tracker.layout.NAME_DEVICE": "620b97404635bcec",
    "tracker.layout.NAME_EMPTY": "aa82b128dcf1c993",
    "tracker.layout.NAME_FIRST_CHARACTER": "bd62babfb5664dc1",
    "tracker.layout.NAME_ILLEGAL": "305df1e9431d3276",
    "tracker.layout.NAME_INVISIBLE": "2401333e2c513d23",
    "tracker.layout.NAME_LAYOUT_WORD": "978aa80c1fbb2b52",
    "tracker.layout.NAME_MAX_CHARS": "48449a14a4ff7d79",
    "tracker.layout.NAME_SCRIPTS": "3de824b29b62bb49",
    "tracker.layout.NAME_TOO_LONG": "7a5e00d8497fbe2d",
    "tracker.layout.NAME_TRAILING": "7fafe7cda3544c33",
    "tracker.layout.OPENED": "33bdc49eaabcbced",
    "tracker.layout.OPENED_DIR_NAME": "5ef673f341874a6f",
    "tracker.layout.ORIGINALS": "535087da73c5868d",
    "tracker.layout.OUTSIDE": "2f2e7ba21585ff28",
    "tracker.layout.PRIVATE": "68a262e0c0fb929f",
    "tracker.layout.PRIVATE_TREE": "27c7f0479a0c896f",
    "tracker.layout.RETURN": "08633b69eed18c1b",
    "tracker.layout.ROOT": "11ccb349ede85740",
    "tracker.layout.STEP_ABOVE_ROOT": "1385e84ae7f46b2d",
    "tracker.layout.STEP_ABSOLUTE": "f523898e69fbc750",
    "tracker.layout.STEP_BLANK": "a4e9e11cd18fd75b",
    "tracker.layout.STEP_CLIENT_TREE": "5f51b518f9526119",
    "tracker.layout.STEP_NOT_A_PLACE": "d1aa6f26861ccbee",
    "tracker.layout.STEP_NOT_A_RETURN": "1e7d015db6355c80",
    "tracker.layout.STEP_OTHER_HOUSEHOLD": "a0f05df5e57d787b",
    "tracker.layout.STEP_OTHER_YEAR": "7994492387ba5850",
    "tracker.layout.WINDOWS_ILLEGAL_CHARS": "0852803faa2a184a",
    "tracker.layout.WINDOWS_RESERVED_NAMES": "99bf9abac32f89f2",
    "tracker.layout.WINDOWS_RESERVED_NAMES_TEXT": "c9d9ad8d312ac5a8",
    "tracker.layout.YEAR": "74c6b2f8351bcc6d",
    "tracker.layout._ASCII_LOOK_ALIKES": "5333fd34ff62ce29",
    "tracker.layout._IGNORABLE_CODES": "999fbf22e2feeb49",
    "tracker.layout._INVISIBLE_CATEGORIES": "bb62d3360fd14a4d",
    "tracker.layout._LAYOUT_WORD_KEYS": "a6d47e2209691833",
    "tracker.layout._ONE_SCRIPT": "17235d2097441c94",
    "tracker.layout._character": "bd5a8cc4e82855fc",
    "tracker.layout._parts": "a2847013a67202c7",
    "tracker.layout._script": "f890f9bb62d24799",
    "tracker.layout.is_invisible": "2b17b033d61a3df2",
    "tracker.layout.is_reserved_name": "3ee144cf8f5c095d",
    "tracker.layout.is_year_folder": "c89c110db3cb607d",
    "tracker.layout.name_key": "749d88cbbd6eb3c3",
    "tracker.layout.parts_below": "522d9b67dfe50b6a",
    "tracker.layout.place_of": "fc1a78ab7179dd32",
    "tracker.layout.place_problem": "2e94883c849c9d08",
    "tracker.layout.recorded_name": "84bfdf3a851f4652",
    "tracker.layout.recorded_subfolder_part": "50620c73d7ae6dab",
    "tracker.layout.root_of": "a6c7013a757965b4",
    "tracker.layout.segment_problem": "13e273e844d2cc2b",
    "tracker.ledger.ACCEPTED_KEY": "f4764fc7a8ddd588",
    "tracker.ledger.ALSO_KEY": "da42922852e5dfcd",
    "tracker.ledger.ASKED_KEY": "46da5b49eea2fbee",
    "tracker.ledger.AT_KEY": "22eb1fa0c521db09",
    "tracker.ledger.DIGEST_KEY": "889a0f98aa32537e",
    "tracker.ledger.DRAFTED": "ef02a62df7dc350b",
    "tracker.ledger.DRAFT_APPROVED": "41bf68b11dd88d88",
    "tracker.ledger.EVENTS": "c6d719a66bc0b51d",
    "tracker.ledger.EVENT_KEY": "9e0d5d1c8d94a5b6",
    "tracker.ledger.FILE_KEY": "0efde3f4308de780",
    "tracker.ledger.FINGERPRINT_KEY": "7df2d13d670e5ed4",
    "tracker.ledger.FOLDER_NAME_ACCEPTED": "b7b92a8807e8bbf9",
    "tracker.ledger.FORMAT_KEY": "04fc6c808adf51ac",
    "tracker.ledger.FROM_KEY": "8ecb478c3dc0d3ae",
    "tracker.ledger.HELD_KEY": "85c4d432c47707ee",
    "tracker.ledger.HOST_KEY": "e293b75405af70cd",
    "tracker.ledger.HOUSEHOLD_CHANGED": "783c776c223a869f",
    "tracker.ledger.HOUSEHOLD_KEY": "8de5259835758e72",
    "tracker.ledger.IDENTIFIER_KEY": "123a87f051936a7e",
    "tracker.ledger.INFO_KEY": "ef3370879a96cf2e",
    "tracker.ledger.KEYWORD_KEY": "a51a9ff6a628d820",
    "tracker.ledger.KEYWORD_LEARNED": "7a5d6590fc40e09a",
    "tracker.ledger.KEYWORD_UNLEARNED": "ce11d4a4c4da44a9",
    "tracker.ledger.KEY_KEY": "632a3e84412d6ea8",
    "tracker.ledger.LINE_KEYS": "bfa2973d92dd93ad",
    "tracker.ledger.LINK_KEY": "67b4e6e1e90cbc98",
    "tracker.ledger.MOVE_ABANDONED": "a11db9ac01cd5285",
    "tracker.ledger.MOVING": "d290155f3097fcde",
    "tracker.ledger.OPS_KEY": "2c35289e43246c9f",
    "tracker.ledger.OP_COPY": "477c02e96b3c4061",
    "tracker.ledger.OP_KEY": "b27b68850018781c",
    "tracker.ledger.OP_MOVE": "c4a4adaf72f566c1",
    "tracker.ledger.OP_REMOVE": "e8c2c1465f168081",
    "tracker.ledger.REASON_KEY": "ffa78aeaf553b544",
    "tracker.ledger.RECORD_FORMAT": "6b86b273ff34fce1",
    "tracker.ledger.RELEASED": "81acce4087249f66",
    "tracker.ledger.REMOVED_KEY": "760f3c525ed93b07",
    "tracker.ledger.RETIRED_EVENTS": "ca06b9854a7990f9",
    "tracker.ledger.ROW_EVENTS": "b53cc1cb7387825b",
    "tracker.ledger.ROW_KEY": "e4d99047ca6a3721",
    "tracker.ledger.RULES_CHANGED": "e4535fc89d8ef96d",
    "tracker.ledger.RULES_IMPORTED": "cddb10ca0e4c2100",
    "tracker.ledger.RULES_KEY": "a29e7581476cd7ad",
    "tracker.ledger.SCANNED": "7e17f4790bff13d5",
    "tracker.ledger.SHARING_CONFIRMED": "c8027ef3eb13f5e3",
    "tracker.ledger.STAGE_KEY": "874095181f94a63d",
    "tracker.ledger.STATUSES_KEY": "18c7785691d58b80",
    "tracker.ledger.TEXT_FINGERPRINT_KEY": "0db6b5095dc3896e",
    "tracker.ledger.TO_KEY": "e28f3243b469e21d",
    "tracker.ledger.WAS_KEY": "1d383f963e096e21",
    "tracker.ledger.op_ends": "a4e5e845ab4c8deb",
    "tracker.reasons.KNOWN_CODES": "4ad3f21d00c7f8e5",
    "tracker.records.BLANK_BOUNDS": "cec8e55a02712202",
    "tracker.records.CANDIDATE_SEP": "3c01b9ef061065a0",
    "tracker.records.COUNT_BOUNDS": "66fbd6100ed5379b",
    "tracker.records.DATE_BOUNDS": "14ca9c3c8c63da08",
    "tracker.records.DATE_FIELDS": "f0aaa0cb84de4063",
    "tracker.records.DATE_PATTERN_ALTERNATES": "6d1924b141e16df5",
    "tracker.records.DATE_PATTERN_BOUND_MAX": "f5ca38f748a1d6ea",
    "tracker.records.DATE_PATTERN_COST_MAX": "b552e632666bbf61",
    "tracker.records.DATE_PATTERN_MAX": "27badc983df1780b",
    "tracker.records.DATE_PATTERN_NESTED": "7b1330f7983d042e",
    "tracker.records.DATE_PATTERN_NOT_A_REGEX": "a158e00f56bf6ba7",
    "tracker.records.DATE_PATTERN_OPEN_MAX": "6b86b273ff34fce1",
    "tracker.records.DATE_PATTERN_OPEN_WIDTH": "0604cd3138feed20",
    "tracker.records.DATE_PATTERN_REFERS_BACK": "25a2057a272ff94c",
    "tracker.records.DATE_PATTERN_REPEATS_MAX": "4e07408562bedb8b",
    "tracker.records.DATE_PATTERN_TOO_COSTLY": "3e2d8a14b8d6a5a6",
    "tracker.records.DATE_PATTERN_TOO_LONG": "02239fb8cdceefd8",
    "tracker.records.DATE_PATTERN_TOO_MANY": "ba11446dcfecda24",
    "tracker.records.DATE_PATTERN_TOO_MANY_OPTIONAL": "eb3c2f5771c5d09f",
    "tracker.records.DATE_PATTERN_TOO_MANY_WAYS": "a322d9761b272d91",
    "tracker.records.DATE_PATTERN_TOO_OPEN": "fcaa25330d84e4d0",
    "tracker.records.DATE_PATTERN_TOO_WIDE": "f7af15030b186a35",
    "tracker.records.DATE_PATTERN_VARIABLE_MAX": "2c624232cdd22177",
    "tracker.records.DATE_PATTERN_WAYS_MAX": "ca902d4a8acbdea1",
    "tracker.records.DATE_YEAR_MAX": "4f5131ea0c5a3e7f",
    "tracker.records.DATE_YEAR_MIN": "e41d64db5703c644",
    "tracker.records.DIGEST_BOUNDS": "677bb2233d3c0d23",
    "tracker.records.FEED_REFUSED": "d601e93b18987f24",
    "tracker.records.FLAG_BOUNDS": "2bfdeea59997694f",
    "tracker.records.HOST_BOUNDS": "72219f0e2bcda110",
    "tracker.records.HOST_MAX": "a68b412c4282555f",
    "tracker.records.LONG_TEXT_BOUNDS": "3de4da1af0b30ef2",
    "tracker.records.LONG_TEXT_MAX": "876c9b16254e157d",
    "tracker.records.MAX_EXPECTED_COUNT": "888df25ae3577242",
    "tracker.records.MAX_FILE_COUNT": "888df25ae3577242",
    "tracker.records.MAX_ROW": "888df25ae3577242",
    "tracker.records.MAX_ROW_SIZE_KB": "02bfbb85ecfba2af",
    "tracker.records.MAX_SIZE_KB": "50b4b069390c1d79",
    "tracker.records.MAX_STAGE": "19581e27de7ced00",
    "tracker.records.MIN_EXPECTED_COUNT": "6b86b273ff34fce1",
    "tracker.records.MIN_SIZE_KB_FLOOR": "5feceb66ffc86f38",
    "tracker.records.MIN_SPELLING_WORDS": "d4735e3a265e16ee",
    "tracker.records.NAME_BOUNDS": "fab0c3e598d1038c",
    "tracker.records.NUMBER_BOUNDS": "d7d2f825d092e462",
    "tracker.records.OVERRIDE_BOUNDS": "22a3650c5fc6e021",
    "tracker.records.PERSON_KINDS": "11ac10e2383de5cc",
    "tracker.records.RULE_FLAG_FIELDS": "c500b9a01ed742b3",
    "tracker.records.RULE_LIST_FIELDS": "8b3d25ca8662bd02",
    "tracker.records.SHORT_TITLE_MAX": "f5ca38f748a1d6ea",
    "tracker.records.STAMP_BOUNDS": "7c7cf7f161dd3671",
    "tracker.records.STAMP_YEAR_MIN": "ad1f3889d0032e7c",
    "tracker.records.TEXT_BOUNDS": "ce369c3539b412af",
    "tracker.records.TEXT_LIST_BOUNDS": "196f901bd54f0f8c",
    "tracker.records.TEXT_MAX": "40510175845988f1",
    "tracker.records.WAITS_FOR_ANSWERS": "f0615f5bcc293884",
    "tracker.records.WAITS_FOR_BOUNDS": "6f57ee0ee5ca0bbc",
    "tracker.records.WAITS_FOR_SEP": "de9881cacd5c858e",
    "tracker.records.WINDOWS_ILLEGAL_CHARS": "0852803faa2a184a",
    "tracker.records.WINDOWS_ILLEGAL_CHARS_TEXT": "e4b68ca2e1ff6518",
    "tracker.records.WINDOWS_RESERVED_NAMES_TEXT": "c9d9ad8d312ac5a8",
    "tracker.records.YEAR_MAX": "1aaf97e300d50bac",
    "tracker.records.YEAR_MIN": "e41d64db5703c644",
    "tracker.records._ENTRY_LONG_TEXT": "108c25e4b80db4c6",
    "tracker.records._ENTRY_NAMES": "5980f2d1176281a2",
    "tracker.records._ENTRY_TEXT": "68e0df1c43ff5282",
    "tracker.records._HEX_DIGEST": "286fa658d6b7911b",
    "tracker.records._INFO_LONG_TEXT": "69674950c21f7eae",
    "tracker.records._INFO_TEXT": "cbdf6035c202636d",
    "tracker.records._ISO_DATE": "3ca3c91bdac79395",
    "tracker.records._ONE_LINE_REFUSED": "f912910f93b16ff7",
    "tracker.records._REFERS_BACK": "6a5a714c08b4ca99",
    "tracker.records._REPEATS": "0429e0cc33348e07",
    "tracker.records._RULE_TEXT": "4dbd8ce696bb0f8e",
    "tracker.records._STAMP": "36e48aca67f1ef08",
    "tracker.records._field": "190cfe96c598c222",
    "tracker.records._first": "afafd6bbd03b4d5a",
    "tracker.records._is_number": "b55a28bc0ae446c7",
    "tracker.records._walk": "58be230437faa42c",
    "tracker.records._ways": "73d93a78035726fd",
    "tracker.records._width": "971b31440953101e",
    "tracker.records.count_problem": "89257d6ec9bdd711",
    "tracker.records.date_pattern_problem": "fa02803a1a99c545",
    "tracker.records.date_problem": "0bf005c4a966d7f8",
    "tracker.records.digest_problem": "217cc9c49f9a6e20",
    "tracker.records.entry_problem": "a79ea9e62a85223a",
    "tracker.records.feed_from_json": "b2e5148af638d97c",
    "tracker.records.feeds_from_json": "b108fd6888f95ec6",
    "tracker.records.flag_problem": "1082a26284942f5c",
    "tracker.records.format_waits_for": "a9f50749433f46ce",
    "tracker.records.host_problem": "7d98945bc57bd382",
    "tracker.records.household_problem": "d341e98e6700e560",
    "tracker.records.identifier_problem": "f8ee13a768acea53",
    "tracker.records.info_problem": "a14147da699ad792",
    "tracker.records.is_a_spelling": "9872f0754c1f928d",
    "tracker.records.name_parts": "2fb3aa450c490a16",
    "tracker.records.name_problem": "435e57a752b587c2",
    "tracker.records.name_words": "888ff2df30e14d73",
    "tracker.records.number_problem": "b8e64da5f5e20b1a",
    "tracker.records.parse_waits_for": "fe2da49df5b9f8ce",
    "tracker.records.people_from_json": "f450ab3614ffbb7c",
    "tracker.records.person_from_json": "7e7a8fed1cb8c27a",
    "tracker.records.received_problem": "2fe803ce248363ca",
    "tracker.records.rule_row_fault": "e63ac46148a8c37f",
    "tracker.records.rule_row_problem": "bfbfa65df0936781",
    "tracker.records.short_title_problem": "cee1ccd1dc44eedd",
    "tracker.records.split_codes": "ac4f6152bb7ad6ee",
    "tracker.records.stamp_problem": "2d66f0bfa7df3a4f",
    "tracker.records.status_from_json": "18fe07346092ffad",
    "tracker.records.status_problem": "0a4507873e497b78",
    "tracker.records.text_list_problem": "5c6a2aa819ebb0cf",
    "tracker.records.text_problem": "3af72e89b781e54e",
    "tracker.records.waits_for_problem": "463d041ef7fa9219",
    "tracker.records.word_list_problem": "64d72805fbba0527",
    "tracker.settings.ENV_SETTINGS_DIR": "b654987367e5160b",
    "tracker.settings.HOLD_READING": "635bd5450bece8e4",
    "tracker.settings.KEY_CLIENTS_ROOT": "3b8f548e07b39dbf",
    "tracker.settings.SETTINGS_FILENAME": "ddf9dfc4d857c464",
    "tracker.settings._HOLDING": "6f49cdbd80e1b95d",
    "tracker.settings._SETTINGS_HELD": "6c71e2207cf64f31",
    "tracker.settings._read": "9a09d08e256be9de",
    "tracker.settings.clients_root": "8fbaef8c43dcb573",
    "tracker.settings.held": "19183d0915cfb77e",
    "tracker.settings.resolved": "dc9902a73c0115e2",
    "tracker.settings.settings_dir": "0468e63b780056c5",
    "tracker.settings.settings_path": "8a79e7ca2ca7f66a",
    "tracker.store.ALSO_IN": "f91e15416cd81c44",
    "tracker.store.KIND_HOUSEHOLD": "8de5259835758e72",
    "tracker.store.KIND_RETURN": "08633b69eed18c1b",
    "tracker.store.MALFORMED_LINE": "7af462b999c9799b",
    "tracker.store.RULE_LIST_FIELDS": "8b3d25ca8662bd02",
    "tracker.store.STATUS_COLUMNS": "072efbf3b12ac0bd",
    "tracker.store.UNKNOWN_EVENT": "099e89ceccd1e5e9",
    "tracker.store._engagement_row": "f7af91c2d1b8ade0",
    "tracker.store._line_keys_problem": "0d6016b3dab0c236",
    "tracker.store._positional_root": "f2fce089ca54ef5a",
    "tracker.store._recorded_root_over": "6447409cff0d940e",
    "tracker.store._refuse_a_malformed_line": "1fa3ee39286cc582",
    "tracker.store.engagement_path": "354415605ca56669",
    "tracker.store.key_root": "13d66deeca51405a",
    "tracker.store.kind": "c5781c37870424f8",
    "tracker.store.statuses": "d99730d725daf407",
}}


def admission_closure() -> dict[str, str]:
    """Every part of the store's admission, by its qualified name: the
    source of every package function reachable from
    ``store._refuse_a_malformed_line`` - through the store, ``records``,
    ``ledger``, ``layout`` or anything else under ``tracker/``, including
    modules it imports at call time - and the ``repr`` of every package
    constant those functions read (a bound, a limit, a pattern). Found by
    walking each function's syntax tree, so a new callee joins by itself
    (the re-review's SF1: the rule R3b was built for lives in ``records``,
    not in the two functions a narrower pin hashed)."""
    import ast
    import importlib
    import inspect
    import re as _re
    import textwrap
    import types

    parts: dict[str, str] = {}
    todo = [store._refuse_a_malformed_line, store._line_keys_problem]
    seen: set[str] = set()
    while todo:
        function = todo.pop()
        name = f"{function.__module__}.{function.__qualname__}"
        if name in seen:
            continue
        seen.add(name)
        source = textwrap.dedent(inspect.getsource(function))
        parts[name] = source
        tree = ast.parse(source)
        names = dict(function.__globals__)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("tracker"):
                module = importlib.import_module(node.module)
                for alias in node.names:
                    names[alias.asname or alias.name] = getattr(module, alias.name, None) \
                        or importlib.import_module(f"{node.module}.{alias.name}")
        for node in ast.walk(tree):
            found = None
            # A dunder (``__file__``, ``__name__``) is where the code sits, not a rule,
            # and ``__file__`` differs on every machine.
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in names                     and not node.id.startswith("__"):
                found = (f"{function.__module__}.{node.id}", names[node.id])
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and \
                    isinstance(names.get(node.value.id), types.ModuleType):
                module = names[node.value.id]
                if module.__name__.startswith("tracker") and hasattr(module, node.attr)                         and not node.attr.startswith("__"):
                    found = (f"{module.__name__}.{node.attr}", getattr(module, node.attr))
            if found is None:
                continue
            where, value = found
            if inspect.isfunction(value) and value.__module__.startswith("tracker"):
                todo.append(value)
            elif isinstance(value, (set, frozenset)):
                parts.setdefault(where, repr(sorted(map(repr, value))))
            elif isinstance(value, (str, int, float, bytes, tuple, dict, _re.Pattern)):
                parts.setdefault(where, repr(value))
    return parts


def admission_digests() -> dict[str, str]:
    import hashlib

    return {name: hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            for name, text in sorted(admission_closure().items())}


def test_admission_version_changes_with_the_admission():
    """Decision 209, R3b: every applied line is judged again only when
    ``ADMISSION_VERSION`` rises, so a change that makes the admission - or
    anything it calls - refuse something it used to admit must raise it in
    the same commit, or a line applied before the change stands for good."""
    now = admission_digests()
    pinned = ADMISSION_PIN.get(store.ADMISSION_VERSION, {})
    moved = sorted(name for name in now.keys() | pinned.keys() if now.get(name) != pinned.get(name))
    assert not moved, (
        f"The store's admission changed in: {', '.join(moved)}. If it now refuses anything it used "
        f"to admit, raise store.ADMISSION_VERSION by one and pin admission_digests() under the new "
        f"version, so every line an earlier version applied is judged again. If it refuses nothing "
        f"new (a comment, a rewording, a wider admission, a part that is not a rule), pin "
        f"admission_digests() under version {store.ADMISSION_VERSION} instead.")


def test_the_admission_pin_reaches_the_rules_it_calls():
    """The re-review's SF1: the pin reaches past the two functions into the
    rules they delegate to - the Date Pattern rule R3b was built for, the
    place and label rules, a move's two ends - and the bounds they read."""
    parts = admission_closure()
    for name in ("tracker.records.date_pattern_problem", "tracker.records.rule_row_problem",
                 "tracker.layout.place_problem", "tracker.layout.segment_problem",
                 "tracker.ledger.op_ends", "tracker.records.MAX_EXPECTED_COUNT"):
        assert name in parts, name


def test_holds_says_whether_the_store_has_met_a_folder(conn, root, by_hand):
    """The after-install check asks :func:`store.holds` first (decision
    209): a folder the store never met is left to its first catch-up."""
    build(conn, root, by_hand)
    assert store.holds(conn, root, by_hand) is True
    store.forget(conn, by_hand)
    assert store.holds(conn, root, by_hand) is False
    assert store.holds(conn, root, by_hand.parent / "1040 - Nobody") is False


def test_an_old_closed_copy_without_a_digest_is_still_admitted(conn, root, by_hand):
    """A copy intent with no fingerprint, closed by the row it wrote, is
    history from an earlier version and not an instruction: the store admits
    it, and only an open one is refused - where it would be carried out."""
    build(conn, root, by_hand)
    copy = {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: A_ROW_ORIGINAL,
            ledger.TO_KEY: "Prepared/A01 - W-2.pdf", ledger.DIGEST_KEY: ""}
    moving = ledger.new(ledger.MOVING, key=A_ROW_ORIGINAL, ops=[copy], by=ledger.BY_PASS,
                        row=a_row(), then=ledger.FILED)
    filed = ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row())

    with engagement_lock(by_hand):
        store.record(conn, by_hand, moving, filed)

    assert said(conn, root, by_hand) == []


def test_the_store_admits_the_accepted_key_with_one_value():
    """Decision 188 (T15): a person's word that a folder's name is accepted
    is admitted on the two events that name a household or a return, with
    its one value - and refused with any other value, or on any other
    event, without quoting what the line said."""
    from tracker.layout import PRIVATE_TREE

    household = f"{PRIVATE_TREE}/Park Household"
    word = {ledger.ACCEPTED_KEY: ledger.FOLDER_NAME_ACCEPTED}
    store._refuse_a_malformed_line(ledger.new(
        ledger.HOUSEHOLD_CHANGED, household={"name": "Park Household"}, **word), 2, household,
        kind=store.KIND_HOUSEHOLD)
    store._refuse_a_malformed_line(ledger.new(
        ledger.RULES_CHANGED, info={"household": "Park Household"}, **word), 2,
        f"{household}/2025/1040 - Park", kind=store.KIND_RETURN)
    for event in (
        ledger.new(ledger.HOUSEHOLD_CHANGED, household={"name": "X"},
                   **{ledger.ACCEPTED_KEY: "everything"}),
        ledger.new(ledger.RULES_CHANGED, info={}, **{ledger.ACCEPTED_KEY: True}),
        ledger.new(ledger.SHARING_CONFIRMED, **word),
    ):
        with pytest.raises(store.StoreError) as refused:
            store._refuse_a_malformed_line(event, 2, household, kind=store.KIND_HOUSEHOLD)
        assert "'accepted' that is not a folder's name accepted" in str(refused.value)
        assert "everything" not in str(refused.value)


# ------------------------ SPEC-162 rulings 5 and 6, kept by decision 188 ----


def _two_lines_then_one(conn, root, engagement):
    """The store applies two lines; the journal is then cut back to one."""
    build(conn, root, engagement)
    with engagement_lock(engagement):
        store.record(conn, engagement, ledger.new(ledger.SCANNED, statuses={}))
    journal = ledger.path_for(engagement)
    lines = journal.read_bytes().splitlines(keepends=True)
    applied = store._engagement_row(conn, engagement, root)["applied_seq"]
    journal.write_bytes(b"".join(lines[:applied - 1]))
    return applied


def test_store_check_reports_a_journal_that_is_gone(conn, root, by_hand, tmp_path):
    """T11 (ruling 5): a journal that is gone is one sentence naming the
    engagement and what the store still holds, saying where to restore it
    from - from the check of the folder, and from the command line's check
    of the whole root, which no walk would otherwise reach."""
    build(conn, root, by_hand)
    applied = store._engagement_row(conn, by_hand, root)["applied_seq"]
    ledger.path_for(by_hand).unlink()
    rel = store.engagement_path(root, by_hand)
    said = store.JOURNAL_GONE.format(n=applied, engagement=rel)

    assert store.check(conn, root, by_hand) == [said]
    assert said in store.gone_journals(conn, root)
    conn.commit()
    result = cli(tmp_path / "app" / store.STORE_FILENAME, "check", root)
    assert result.returncode == 1 and said in result.stdout, result.stdout + result.stderr


def test_the_truncation_error_says_restore_first(conn, root, by_hand):
    """T11 (ruling 5): a journal shorter than what the store applied is
    refused with the sentence that says to restore it first, and what a
    rebuild would discard."""
    applied = _two_lines_then_one(conn, root, by_hand)
    rel = store.engagement_path(root, by_hand)
    with pytest.raises(store.StoreError) as refused:
        store.follow_the_journal(conn, root, by_hand)
    assert str(refused.value) == store.TRUNCATED.format(engagement=rel, n=applied - 1, m=applied,
                                                        k=1)
    assert "First restore the journal from Drive's trash" in str(refused.value)


def test_rebuild_lists_what_it_would_discard_and_needs_discard(conn, root, by_hand, tmp_path):
    """T11 (ruling 6): a rebuild never discards silently - it lists each line
    only the store holds, refuses, and changes nothing; the command line
    does the same and exits 1. Since the port review's M1 (decision 159's
    ruling), ``--discard`` rebuilds only with the return's name typed -
    ``--accept-loss``, recover's own path - and alone it is refused."""
    applied = _two_lines_then_one(conn, root, by_hand)
    rel = store.engagement_path(root, by_hand)
    with pytest.raises(store.WouldDiscard) as refused:
        store.rebuild_engagement(conn, root, by_hand)
    assert str(refused.value) == store.WOULD_DISCARD.format(engagement=rel, k=1)
    [line] = refused.value.lines
    assert line.startswith(f"  {ledger.SCANNED}  -  ")
    assert store._engagement_row(conn, by_hand, root)["applied_seq"] == applied
    conn.commit()

    path = tmp_path / "app" / store.STORE_FILENAME
    result = cli(path, "rebuild", root, "--engagement", by_hand)
    assert result.returncode == 1
    assert line in result.stdout and str(refused.value) in result.stdout, result.stdout
    result = cli(path, "rebuild", root, "--engagement", by_hand, "--discard")
    assert result.returncode == 2 and "--accept-loss" in result.stderr
    assert store._engagement_row(store.connect(path), by_hand, root)["applied_seq"] == applied
    store.close()
    result = cli(path, "rebuild", root, "--engagement", by_hand, "--discard",
                 "--accept-loss", by_hand.name)
    assert result.returncode == 0, result.stdout + result.stderr
    assert store.ACCEPTED.format(n=1) in result.stdout


# ------------------------------------------ decision 204: the Waits For cell ----


def test_an_index_of_the_previous_version_reads_with_waits_for_empty(conn, root, by_hand, tmp_path):
    """Decision 204 added ``waits_for`` to ``documents`` (version 17). A row
    a journal holds from before it carries no such field and folds to
    waiting for nothing, and the store rebuilt from that journal agrees
    with it."""
    from tracker.records import entry_from_json

    with engagement_lock(by_hand):
        store.record(conn, by_hand, ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row()))
    assert "waits_for" not in ledger.path_for(by_hand).read_text(encoding="utf-8")

    build(conn, root, by_hand)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION == 20
    [row] = [entry_from_json(one) for one in store.documents(conn, by_hand)]
    assert row.waits_for == "" and row.waiting_for is None
    assert store.check(conn, root, by_hand) == []



def test_a_version_16_store_is_upgraded_in_place_and_keeps_its_cached_verdicts(tmp_path):
    """Decision 204, the store's first in-place step (the module docstring's
    rule): a version-16 file gains ``waits_for``, NULL on every row as a
    rebuild writes it, and becomes version 17 where it stands - its verdict cache kept, so the
    first pass after the upgrade reads nothing again - and every row it
    held reads as waiting for nothing, which is what the journal - one
    written before 204 - says, cell for cell as a rebuild leaves it. It goes on
    through decision 190's step and 209's to this version. Any other earlier
    version is set aside and rebuilt (decision 159, E3)."""
    from tests.conftest import sort
    from tests.test_scanner import text_pdf
    from tracker.layout import inbox_of
    from tracker.records import entry_from_json

    engagement = make_engagement(tmp_path / "root", [RequestItem(
        identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
        min_size_kb=0, required_keywords=("W-2",))])
    text_pdf(inbox_of(engagement) / "w2.pdf", "Form W-2 Wage and Tax Statement 2025 Test Client")
    text_pdf(inbox_of(engagement) / "notice.pdf", "an agency notice nothing asks for")
    sort(engagement)
    live = store.connect()
    cached = live.execute(f"SELECT COUNT(*) FROM {store.VERDICTS_TABLE}").fetchone()[0]
    memos = live.execute(f"SELECT COUNT(*) FROM {store.FILE_MEMOS_TABLE}").fetchone()[0]
    assert cached > 0

    old = tmp_path / "v16" / store.STORE_FILENAME
    old.parent.mkdir()
    written = sqlite3.connect(old)
    live.backup(written)
    for statement in AS_AT_16:                                           # what version 16 was
        written.execute(statement)
    written.execute("PRAGMA user_version = 16")
    written.commit()
    written.close()
    journal_as_written_before(engagement, FIELDS_OF_190 + FIELDS_OF_204)

    conn = store.open(old)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION == 20
        assert conn.execute(f"SELECT COUNT(*) FROM {store.VERDICTS_TABLE}").fetchone()[0] == cached
        assert conn.execute(f"SELECT COUNT(*) FROM {store.FILE_MEMOS_TABLE}").fetchone()[0] == memos
        rows = [entry_from_json(one) for one in store.documents(conn, engagement)]
        assert len(rows) == 2 and all(row.waits_for == "" for row in rows)
        assert as_a_rebuild_leaves_it(conn, tmp_path / "root", engagement, tmp_path)
    finally:
        conn.close()
    reopened = store.open(old)                   # a second open finds nothing to do
    reopened.close()

    # Any earlier version no in-place step reaches is set aside and opened
    # fresh (decision 159, E3): one upgrade policy, not two.
    refused = tmp_path / "v15" / store.STORE_FILENAME
    store.open(refused).close()
    earlier = sqlite3.connect(refused)
    earlier.execute(f"PRAGMA user_version = {REFUSED_EARLIER}")
    earlier.close()
    store.open(refused).close()
    assert refused.with_name(f"{store.STORE_FILENAME}.v{REFUSED_EARLIER}.old").is_file()


def test_two_openers_of_one_version_16_store_both_succeed(tmp_path, monkeypatch):
    """The in-place step re-reads the version under the write lock (the port
    review's should-fix): an opener that read 16 before another opener
    upgraded the file finds the step made and goes on, rather than failing
    on the column the other added. Both end at this version (19
    since decision 209: each step is re-read the same way)."""
    path = tmp_path / "shared" / store.STORE_FILENAME
    store.open(path).close()
    written = sqlite3.connect(path)
    for statement in AS_AT_16:
        written.execute(statement)
    written.execute("PRAGMA user_version = 16")
    written.commit()
    written.close()
    real_execute = store._Connection.execute
    raced = {"done": False}

    def the_other_opener_first(self, sql, *args):
        if sql == "BEGIN IMMEDIATE" and not raced["done"]:
            raced["done"] = True
            store.open(path).close()         # it read 16 too, and upgraded first
        return real_execute(self, sql, *args)

    monkeypatch.setattr(store._Connection, "execute", the_other_opener_first)
    conn = store.open(path)
    try:
        assert raced["done"]
        assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION == 20
        columns = [row[1] for row in conn.execute("PRAGMA table_info(documents)")]
        assert columns.count("waits_for") == 1 and columns.count("code") == 1
    finally:
        conn.close()


def test_a_version_17_store_gains_the_cause_columns_in_place_and_every_old_row_reads_not_recorded(
        tmp_path):
    """Decision 190's in-place step (the store's rule, applied to each of
    its three columns): a version-17 file gains ``code`` and ``subfolder``
    on its rows and ``note_codes`` on its statuses, all empty, and becomes
    version 18 where it stands. That is what a rebuild from a journal
    written before 190 gives, cell for cell - no such line carries a cause -
    and no row's cause is read out of its words."""
    from tests.conftest import sort
    from tests.test_scanner import text_pdf
    from tracker.layout import inbox_of
    from tracker.records import entry_from_json

    engagement = make_engagement(tmp_path / "root", [RequestItem(
        identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
        min_size_kb=0, required_keywords=("W-2",))])
    text_pdf(inbox_of(engagement) / "notice.pdf", "an agency notice nothing asks for")
    sort(engagement)
    live = store.connect()

    old = tmp_path / "v17" / store.STORE_FILENAME
    old.parent.mkdir()
    written = sqlite3.connect(old)
    live.backup(written)
    for statement in AS_AT_17:                                           # what version 17 was
        written.execute(statement)
    written.execute("PRAGMA user_version = 17")
    written.commit()
    written.close()
    journal_as_written_before(engagement, FIELDS_OF_190)

    conn = store.open(old)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION == 20
        [row] = [entry_from_json(one) for one in store.documents(conn, engagement)]
        assert row.original_name == "notice.pdf" and row.code == "" and row.subfolder == ""
        assert "note_codes" in [one[1] for one in conn.execute("PRAGMA table_info(statuses)")]
        assert as_a_rebuild_leaves_it(conn, tmp_path / "root", engagement, tmp_path)
    finally:
        conn.close()


def test_a_store_that_204s_old_step_upgraded_with_empty_cells_passes_check_after_190s_step(tmp_path):
    """Decision 190's review of the port, S3. Main's 204 step added
    ``waits_for`` with ``DEFAULT ''``, so a file it upgraded holds ``''``
    on every earlier row where a rebuild from the journal writes NULL. After
    190's step that file must pass ``store check``: NULL and ``''`` are the
    one value in the columns an in-place step added, and in those only - a
    real value there, and NULL against ``''`` in any other column, are
    still named."""
    from tests.conftest import sort
    from tests.test_scanner import text_pdf
    from tracker.layout import inbox_of

    root = tmp_path / "root"
    engagement = make_engagement(root, [RequestItem(
        identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
        min_size_kb=0, required_keywords=("W-2",))])
    text_pdf(inbox_of(engagement) / "w2.pdf", "Form W-2 Wage and Tax Statement 2025 Test Client")
    text_pdf(inbox_of(engagement) / "notice.pdf", "an agency notice nothing asks for")
    sort(engagement)
    journal_as_written_before(engagement, FIELDS_OF_190 + FIELDS_OF_204)

    old = tmp_path / "v16" / store.STORE_FILENAME
    built = store.open(old)
    try:
        store.rebuild_engagement(built, root, engagement)          # what version 16 held, cell for cell
    finally:
        built.close()
    written = sqlite3.connect(old)
    for statement in AS_AT_16:
        written.execute(statement)
    written.execute("""ALTER TABLE documents ADD COLUMN "waits_for" TEXT DEFAULT ''""")    # 204's old step
    written.execute("PRAGMA user_version = 17")
    written.commit()
    assert {row[0] for row in written.execute('SELECT "waits_for" FROM documents')} == {""}
    written.close()

    conn = store.open(old)                                          # 190's step: NULL columns
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION
        conn.execute("""UPDATE statuses SET "note_codes" = ''""")
        conn.commit()
        assert store.check(conn, root, engagement) == []

        conn.execute("""UPDATE documents SET "waits_for" = 'A01' WHERE "position" = 0""")
        conn.commit()
        named = store.check(conn, root, engagement)
        assert len(named) == 1 and "waits_for: the store says 'A01'" in named[0], named
        conn.execute("""UPDATE documents SET "waits_for" = ''""")
        conn.execute("""UPDATE documents SET "candidates" = NULL WHERE "candidates" = ''""")
        conn.commit()
        named = store.check(conn, root, engagement)
        assert len(named) == 1 and all("candidates: the store says None, the record says ''" in one
                             for one in named), named
    finally:
        conn.close()


# ------------------------------- decision 159: the record can show it was not altered ----
#
# Each "refused by a fresh store" case builds a store from nothing beside the
# existing checkpoint - which is what deleting ``tracker.db`` leaves, and the
# case a store's own applied chain cannot answer: it has nothing to compare.


def recorded(conn, folder, *events):
    with engagement_lock(folder):
        store.record(conn, folder, *events)


def three_lines(conn, folder):
    """The create's line, then two filings, all through the store."""
    recorded(conn, folder, ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed")))
    recorded(conn, folder, ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row()))
    assert len(ledger.read_events(folder)) == 3


@pytest.fixture
def fresh(tmp_path):
    """A store built from nothing, beside the checkpoint the test's own store keeps."""
    connection = store.open(tmp_path / "app" / "fresh.db")
    yield connection
    connection.close()


def relinked(folder, lines: list[bytes]):
    """Write ``lines`` as the record, each given the link it needs to read -
    a rewrite by a hand that knows the chain (the only rewrite the link
    alone cannot see)."""
    import json as _json

    ledger.path_for(folder).write_bytes(b"")
    for raw in lines:
        event = {k: v for k, v in _json.loads(raw).items() if k not in ledger.LINE_KEYS}
        written_elsewhere(folder, event, host=_json.loads(raw)[ledger.HOST_KEY])


def test_a_truncated_record_is_refused_by_a_fresh_store(conn, fresh, root, by_hand):
    three_lines(conn, by_hand)
    path = ledger.path_for(by_hand)
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:2]))
    with pytest.raises(store.StoreError, match=r"shorter than this machine last saw it \(2 of 3"):
        store.catch_up(fresh, root, by_hand)
    assert store._engagement_row(fresh, by_hand) is None                # nothing was applied


def test_a_reordered_record_is_refused_by_a_fresh_store(conn, fresh, root, by_hand):
    three_lines(conn, by_hand)
    path = ledger.path_for(by_hand)
    first, filed, parked = path.read_bytes().splitlines()
    path.write_bytes(b"\n".join([first, parked, filed]) + b"\n")
    with pytest.raises(ledger.LedgerError, match="line 2 does not follow"):
        store.catch_up(fresh, root, by_hand)
    relinked(by_hand, [first, parked, filed])                             # and made to read again
    with pytest.raises(store.StoreError, match="no longer matches what this machine last saw"):
        store.catch_up(fresh, root, by_hand)
    assert store._engagement_row(fresh, by_hand) is None


def test_a_hand_appended_line_is_refused_by_a_fresh_store(conn, fresh, root, by_hand):
    """Both shapes: a line without the link (the ledger refuses it) and a
    line with the right link that says this machine wrote it (the
    checkpoint refuses it - this machine did not)."""
    import json as _json

    from tracker.locking import this_host

    three_lines(conn, by_hand)
    path = ledger.path_for(by_hand)
    kept = path.read_bytes()
    line = ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed"))
    path.write_bytes(kept + _json.dumps(line).encode() + b"\n")
    with pytest.raises(ledger.LedgerError, match="line 4 was written without the record's link"):
        store.catch_up(fresh, root, by_hand)
    path.write_bytes(kept)
    written_elsewhere(by_hand, line, host=this_host())
    with pytest.raises(store.StoreError, match="Line 4 .* says it was written on this machine"):
        store.catch_up(fresh, root, by_hand)
    with pytest.raises(store.StoreError, match="says it was written on this machine"):
        store.sync(conn, root, by_hand)                                   # and the store in use too
    assert store._engagement_row(fresh, by_hand) is None


def test_a_same_length_rewrite_is_refused_by_a_fresh_store(conn, fresh, root, by_hand):
    import json as _json

    three_lines(conn, by_hand)
    lines = ledger.path_for(by_hand).read_bytes().splitlines()
    edited = _json.loads(lines[1])
    edited[ledger.ROW_KEY]["decision"] = "Needs Review"
    relinked(by_hand, [lines[0], _json.dumps(edited).encode(), lines[2]])
    with pytest.raises(store.StoreError, match="no longer matches what this machine last saw"):
        store.catch_up(fresh, root, by_hand)
    assert store._engagement_row(fresh, by_hand) is None


def test_the_one_switch_refuses_a_line_from_another_machine(conn, root, by_hand, monkeypatch):
    """``checkpoint.foreign_lines_refused`` is the one place the answer lives
    (decision 159, §0): turned on, a line another machine wrote is refused
    by name and nothing is applied."""
    build(conn, root, by_hand)
    written_elsewhere(by_hand, ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row()),
                      host="laptop-2")
    monkeypatch.setattr(checkpoint, "foreign_lines_refused", lambda: True)
    with pytest.raises(store.StoreError, match="was written on laptop-2; this machine is the one"):
        store.sync(conn, root, by_hand)
    monkeypatch.undo()
    assert store.sync(conn, root, by_hand) == 2                          # (a): accepted, and named
    assert [(one.seq, one.host) for one in store.foreign_lines()] == [(2, "laptop-2")]


def test_an_append_interrupted_before_the_checkpoint_moved_is_this_machines_own(
        conn, fresh, root, by_hand, monkeypatch):
    """The intent (decision 159, §4.3): ``record()`` says how far it is
    about to take the record before it appends, so a run killed between
    its append and its apply leaves lines this machine accepts as its own
    - a crash is not a forgery."""
    build(conn, root, by_hand)

    def killed(*_args, **_kwargs):
        raise KeyboardInterrupt("the machine went down")

    monkeypatch.setattr(store, "_catch_up", killed)
    with pytest.raises(KeyboardInterrupt):
        recorded(conn, by_hand, ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed")))
    monkeypatch.undo()
    assert len(ledger.read_events(by_hand)) == 2
    assert store.catch_up(fresh, root, by_hand) == 2                     # a fresh store accepts it
    assert store.sync(conn, root, by_hand) == 2                          # and so does the one in use
    the_store_is_the_journal(conn, root, by_hand)


def test_rebuild_refuses_a_record_that_does_not_extend_the_checkpoint(conn, root, by_hand, tmp_path):
    three_lines(conn, by_hand)
    path = ledger.path_for(by_hand)
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:2]))
    before = rows(conn, "documents")
    # A record shorter than the store: decision 188's refusal, which lists
    # what would go (the checkpoint's own stands behind it).
    with pytest.raises(store.WouldDiscard, match="rebuild would discard them"):
        build(conn, root, by_hand)
    assert rows(conn, "documents") == before                             # nothing was deleted

    refused = cli(tmp_path / "app" / store.STORE_FILENAME, "rebuild", root, "--engagement", by_hand)
    assert refused.returncode == 1 and "rebuild would discard them" in refused.stdout


def test_rebuild_refuses_a_broken_chain(conn, root, by_hand):
    three_lines(conn, by_hand)
    path = ledger.path_for(by_hand)
    first, filed, parked = path.read_bytes().splitlines()
    path.write_bytes(b"\n".join([first, parked]) + b"\n")                # a line cut from the middle
    before = rows(conn, "documents")
    with pytest.raises(ledger.LedgerError, match="does not follow the line before it"):
        build(conn, root, by_hand)
    assert rows(conn, "documents") == before


FABRICATED_NAME = "Confidential W-2 for Maria Fabricated.pdf"


def a_store_ahead_of_its_record(conn, by_hand):
    """Three lines through the store, the last naming a fabricated file; then
    the record loses that line - the store holds one the record does not."""
    recorded(conn, by_hand, ledger.new(ledger.FILED, key=A_ROW_ORIGINAL,
                                       row=a_row(decision="Filed", original_name=FABRICATED_NAME)))
    recorded(conn, by_hand, ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL,
                                       row=a_row(original_name=FABRICATED_NAME)))
    path = ledger.path_for(by_hand)
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:2]))


def test_recover_writes_the_export_and_the_difference_before_anything(conn, root, by_hand, tmp_path):
    a_store_ahead_of_its_record(conn, by_hand)
    record_now = ledger.path_for(by_hand).read_bytes()
    before = (rows(conn, "events"), rows(conn, "documents"))

    done = store.recover(conn, root, by_hand)
    assert done.export.parent == tmp_path / "app" / store.RECOVERED_DIR
    assert len(done.export.read_text(encoding="utf-8").splitlines()) == 3   # the store's lines
    assert done.record_copy.read_bytes() == record_now
    assert [(one.seq, one.side, one.event) for one in done.differences] == [
        (3, store.ON_STORE, ledger.PARKED)]
    assert not done.accepted and done.lost == 1
    assert (rows(conn, "events"), rows(conn, "documents")) == before       # nothing changed
    assert ledger.path_for(by_hand).read_bytes() == record_now
    with pytest.raises(store.StoreError, match="holds fewer lines than the store has applied"):
        store.sync(conn, root, by_hand)                                    # still refused

    again = store.recover(conn, root, by_hand)                             # never over the first
    assert again.export != done.export and done.export.is_file()


def test_recover_replays_only_when_the_loss_is_accepted_by_the_returns_name(conn, root, by_hand):
    a_store_ahead_of_its_record(conn, by_hand)
    before = rows(conn, "events")
    wrong = store.recover(conn, root, by_hand, accept_loss=by_hand.name.upper() + " ")
    assert not wrong.accepted and "typed exactly" in wrong.refusal
    assert rows(conn, "events") == before

    done = store.recover(conn, root, by_hand, accept_loss=by_hand.name)
    assert done.accepted and done.lost == 1
    assert store.ACCEPTED.format(n=1).startswith("accepted: 1 line(s)")
    _events, _head, chain = ledger.read_with_chain(by_hand)
    with checkpoint.opened(checkpoint.path_for(conn.execute("PRAGMA database_list").fetchone()[2])) \
            as held:
        assert checkpoint.vouched(held, KEY) == (2, ledger.chain_at(chain, 2))   # seeded again
    assert store.sync(conn, root, by_hand) == 2
    assert said(conn, root, by_hand) == []


def test_recover_refuses_to_replay_a_record_that_does_not_read(conn, root, by_hand):
    three_lines(conn, by_hand)
    path = ledger.path_for(by_hand)
    first, filed, parked = path.read_bytes().splitlines()
    path.write_bytes(b"\n".join([first, parked]) + b"\n")
    done = store.recover(conn, root, by_hand, accept_loss=by_hand.name)
    assert not done.accepted and "the record itself does not read" in done.refusal
    assert str(done.export) in done.refusal
    assert path.read_bytes() == b"\n".join([first, parked]) + b"\n"       # never rewritten


def test_recover_prints_no_payload_value(conn, root, by_hand, tmp_path):
    """Principle 7: the difference names seq, side, event, time and host -
    never a file name, a reason or any other value a line carries."""
    a_store_ahead_of_its_record(conn, by_hand)
    conn.close()
    store.close()
    shown = cli(tmp_path / "app" / store.STORE_FILENAME, "recover", root, "--engagement", by_hand)
    assert shown.returncode == 1, shown.stderr
    assert "parked" in shown.stdout and "store" in shown.stdout and "--accept-loss" in shown.stdout
    assert FABRICATED_NAME not in shown.stdout + shown.stderr
    assert "Maria" not in shown.stdout + shown.stderr

    accepted = cli(tmp_path / "app" / store.STORE_FILENAME, "recover", root, "--engagement", by_hand,
                   "--accept-loss", by_hand.name)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "accepted: 1 line(s)" in accepted.stdout
    assert FABRICATED_NAME not in accepted.stdout + accepted.stderr


def _tree(folder: Path) -> dict[str, tuple]:
    """Every file and folder under ``folder``: bytes and modification time."""
    return {str(path.relative_to(folder)): ((path.read_bytes(), path.stat().st_mtime_ns)
                                            if path.is_file() else ("dir",))
            for path in sorted(folder.rglob("*"))}


def test_verify_changes_nothing_and_names_every_mismatch(root, engagement, tmp_path):
    """G-10: a read-only verify, firm-wide. Nothing under the clients root
    changes - not a byte, not a time - and neither the store nor the
    checkpoint is written; every problem is named by class and path below
    the root, and any problem exits 1."""
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "1098.pdf", "Form 1098 Mortgage Interest Statement 2025")
    sort(engagement, today=DAY1)
    store.close()
    home = tmp_path / "app"
    kept = {name: (home / name).read_bytes()
            for name in (store.STORE_FILENAME, checkpoint.CHECKPOINT_FILENAME)}

    tree = _tree(root)
    clean = cli(home / store.STORE_FILENAME, "verify", root)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert "nothing to report" in clean.stdout
    assert _tree(root) == tree

    entries = read_index(engagement)
    store.close()
    copy = next(entry for entry in entries if entry.prepared_location)
    (engagement / copy.prepared_location).unlink()                          # a working copy gone
    original = locate_original(engagement, entries[-1])
    original.write_bytes(original.read_bytes() + b"changed")                # an original changed
    household_record = ledger.path_for(engagement.parents[1])               # a record cut short
    target = household_record if household_record.is_file() else ledger.path_for(engagement)
    lines = target.read_bytes().splitlines(keepends=True)
    target.write_bytes(b"".join(lines[:-1]))

    tree = _tree(root)
    found = cli(home / store.STORE_FILENAME, "verify", root)
    assert found.returncode == 1
    said_now = found.stdout
    assert store.V_MISSING in said_now and store.V_CHANGED in said_now and store.V_SHORTER in said_now
    assert Path(copy.prepared_location).name in said_now
    assert _tree(root) == tree                                              # nothing moved, nothing made
    assert {name: (home / name).read_bytes() for name in kept} == kept
    assert not (home / store.RECOVERED_DIR).exists()


def locate_original(engagement, entry):
    from tracker.layout import locate

    return locate(engagement, entry.pbc_location)


def test_an_older_store_is_set_aside_and_rebuilt(conn, root, by_hand, tmp_path):
    """E3: an older store is renamed out of the way, never deleted, and the
    return is built again from its record - proved against the checkpoint,
    which the set-aside did not touch."""
    three_lines(conn, by_hand)
    conn.close()
    store.close()
    path = tmp_path / "app" / store.STORE_FILENAME
    older = sqlite3.connect(path)
    older.execute(f"PRAGMA user_version = {REFUSED_EARLIER}")         # no in-place step reaches it
    older.close()

    reopened = store.connect()
    assert path.with_name(f"{store.STORE_FILENAME}.v{REFUSED_EARLIER}.old").is_file()
    assert store.catch_up(reopened, root, by_hand) == 3
    assert said(reopened, root, by_hand) == []


def test_a_newer_store_is_still_refused(tmp_path):
    path = tmp_path / "app" / store.STORE_FILENAME
    store.open(path).close()
    newer = sqlite3.connect(path)
    newer.execute(f"PRAGMA user_version = {store.SCHEMA_VERSION + 1}")
    newer.close()
    with pytest.raises(store.StoreError, match="newer version of the app's store; install"):
        store.open(path)
    assert not path.with_name(f"{store.STORE_FILENAME}.v{store.SCHEMA_VERSION + 1}.old").exists()


def test_a_root_the_checkpoint_does_not_belong_to_is_refused(tmp_path):
    """E5: the checkpoint belongs to the root it first served; the settings
    naming another folder - a copy of the root, say - is refused by name,
    and one spelling of the same folder is not another."""
    first, copy = tmp_path / "Clients", tmp_path / "Clients copy"
    first.mkdir()
    copy.mkdir()
    store.prove_the_root(first)
    store.prove_the_root(tmp_path / "." / "Clients")
    with pytest.raises(store.StoreError, match="belongs to .*Clients; this was asked to work in .*Clients copy"):
        store.prove_the_root(copy)
    with pytest.raises(store.StoreError, match="If the clients root really moved"):
        store.prove_the_root(copy, claim=False)


# ------------------------------------------ decision 159: the part-3 review's fixes ----


def test_a_failed_append_leaves_no_intent_behind(conn, fresh, root, by_hand):
    """M1 (probe P2): an append that fails - a refused line, a file another
    program holds - leaves no intent that a line forged later into the same
    place could pass under. Such a line is refused, by a fresh store too."""
    from tracker.locking import this_host

    three_lines(conn, by_hand)
    refused = ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed"))
    refused[ledger.HOST_KEY] = "x"                                       # the append refuses it
    with pytest.raises(ledger.LedgerError):
        recorded(conn, by_hand, refused)
    with checkpoint.opened(store._checkpoint_file(conn)) as held:
        assert checkpoint.intent(held, KEY) is None
    store.catch_up(conn, root, by_hand)
    written_elsewhere(by_hand, ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed")),
                      host=this_host())
    with pytest.raises(store.StoreError, match="Line 4 .* says it was written on this machine"):
        store.catch_up(fresh, root, by_hand)


def test_a_line_forged_into_an_interrupted_batch_is_refused_and_the_batch_is_its_own(
        conn, fresh, root, by_hand, monkeypatch):
    """M1 (probe P2b): a batch of three killed after its first line leaves
    that line this machine's own, and a line forged into the second place
    - the right link, this machine's name, not the bytes the batch said -
    is refused. The intent is the chain the lines will have, not a count."""
    from tracker.locking import this_host

    three_lines(conn, by_hand)
    real = ledger.append
    calls = []

    def dies_on_the_second(folder, event):
        calls.append(event)
        if len(calls) == 2:
            raise KeyboardInterrupt("the machine went down")
        return real(folder, event)

    monkeypatch.setattr(ledger, "append", dies_on_the_second)
    parked = ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row())
    with pytest.raises(KeyboardInterrupt):
        recorded(conn, by_hand, parked, dict(parked), dict(parked))
    monkeypatch.undo()
    assert store.catch_up(fresh, root, by_hand) == 4                    # its own line, accepted
    written_elsewhere(by_hand, ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL,
                                          row=a_row(reason="not the line the batch said")),
                      host=this_host())
    with pytest.raises(store.StoreError, match="Line 5 .* says it was written on this machine"):
        store.catch_up(fresh, root, by_hand)


def test_a_new_batch_keeps_an_earlier_batchs_unvouched_lines_its_own(conn, root, by_hand, monkeypatch):
    """A later ``record()`` after a kill must not disown the killed batch's
    line before any reader vouched for it."""
    build(conn, root, by_hand)
    monkeypatch.setattr(store, "_catch_up", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        recorded(conn, by_hand, ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row()))
    monkeypatch.undo()
    conn.execute("UPDATE engagements SET applied_seq = 2, applied_digest = ? WHERE path = ?",
                 (ledger.read_with_chain(by_hand)[2][1], KEY))        # a reader applied the store only
    recorded(conn, by_hand, ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed")))
    assert len(ledger.read_events(by_hand)) == 3


def test_a_return_created_again_after_its_store_row_is_gone_is_not_held_to_the_old_checkpoint(
        root, tmp_path, monkeypatch):
    """M2 (probe P3): a return removed while its store was set aside or
    deleted is created again under the same name; ``forget`` clears the
    checkpoint's row whether or not the store holds one."""
    import shutil

    folder = make_engagement(root, ITEMS, household="Smith Family", return_name="Again")
    with engagement_lock(folder):
        store.record(store.connect(), folder, ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row()))
    shutil.rmtree(folder)
    store.close()
    monkeypatch.setenv(store.ENV_STORE, str(tmp_path / "app" / "second.db"))   # the same checkpoint
    again = make_engagement(root, ITEMS, household="Smith Family", return_name="Again")
    assert len(ledger.read_events(again)) == 1


def test_a_differently_cased_name_of_this_machine_is_this_machine(conn, fresh, root, by_hand):
    """S1 (probe P1b): ``OFFICE-PC`` on the machine ``office-pc`` is not
    "another machine" - a forged line in any case is refused, never named
    for a person to acknowledge."""
    from tracker.locking import is_this_host, this_host

    assert is_this_host(this_host().upper()) and not is_this_host("another-machine")
    three_lines(conn, by_hand)
    written_elsewhere(by_hand, ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed")),
                      host=this_host().swapcase() if this_host().swapcase() != this_host()
                      else this_host().upper())
    with pytest.raises(store.StoreError, match="says it was written on this machine"):
        store.catch_up(fresh, root, by_hand)
    assert store.foreign_lines() == []


def test_a_rewrite_on_a_fresh_store_claims_no_line_number_it_does_not_know(conn, fresh, root, by_hand):
    """N2: with no store copy to find it by, the refusal says "an earlier line"."""
    import json as _json

    three_lines(conn, by_hand)
    lines = ledger.path_for(by_hand).read_bytes().splitlines()
    edited = _json.loads(lines[2])
    edited[ledger.ROW_KEY]["reason"] = "fabricated edit"
    relinked(by_hand, [lines[0], lines[1], _json.dumps(edited).encode()])
    with pytest.raises(store.StoreError, match="from an earlier line onward"):
        store.catch_up(fresh, root, by_hand)
    with pytest.raises(store.StoreError, match="from line 3 onward|line 3 onward"):
        store.catch_up(conn, root, by_hand)


def test_verify_names_a_line_with_no_writer_as_the_pass_refuses_it(conn, root, by_hand, tmp_path):
    """S3 (probe Q5b): verify asks the pass's own judgment, so a line with no
    link and no writer after a record from before 159 is named by both."""
    import json as _json

    events = unlinked(ledger.read_events(by_hand))
    store.forget(conn, by_hand)          # a store, and a checkpoint, that never met it
    ledger.path_for(by_hand).write_text(
        "".join(_json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    build(conn, root, by_hand)
    with ledger.path_for(by_hand).open("a", encoding="utf-8") as handle:
        handle.write(_json.dumps(ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row())) + "\n")
    with pytest.raises(store.StoreError, match="Line 2 .* carries no writer"):
        store.sync(conn, root, by_hand)
    conn.close()
    store.close()
    shown = cli(tmp_path / "app" / store.STORE_FILENAME, "verify", root)
    assert shown.returncode == 1 and store.V_NO_WRITER in shown.stdout and "line 2" in shown.stdout


def test_a_checkpoint_that_will_not_open_is_that_returns_problem_by_name(conn, root, by_hand, tmp_path):
    """S4: a damaged checkpoint is refused naming the file and the runbook's
    step - a StoreError, one return's problem - and is never set aside. The
    root proof leaves it as the checkpoint's own error (the rebase review's
    SF1), so its caller never says it as a root the checkpoint does not
    belong to."""
    where = checkpoint.path_for(tmp_path / "app" / store.STORE_FILENAME)
    store.close()           # the checkpoint the setup held (P214), as a person closes the app first
    where.write_bytes(b"fabricated garbage, not a database" * 40)
    with pytest.raises(store.StoreError, match="cannot read this machine's record checkpoint"):
        build(conn, root, by_hand)
    with pytest.raises(checkpoint.CheckpointUnavailable, match="runbook §6") as refused:
        store.prove_the_root(root)
    assert not isinstance(refused.value, store.StoreError) and not refused.value.busy
    assert where.read_bytes().startswith(b"fabricated garbage")
    where.unlink()


def _still_open(kind) -> int:
    """Connections of the product's ``kind`` this process still has open,
    collected or not: an open one found among the objects the garbage
    collector has not yet reached is exactly the handle that locks a file
    on Windows."""
    import gc

    count = 0
    for candidate in gc.get_objects():
        if isinstance(candidate, kind):
            try:
                candidate.execute("SELECT 1")
            except (sqlite3.ProgrammingError, store.StoreError, checkpoint.CheckpointError):
                continue                               # closed
            count += 1
    return count


@pytest.mark.parametrize("which", ["store", "checkpoint"])
def test_a_file_that_will_not_open_is_not_held_open_after_the_refusal(tmp_path, which):
    """Decision 159, Windows: a store or record checkpoint that is not a
    database is refused by name, and the refusing process lets go of it at
    once. Left to the garbage collector, the connection stayed open behind
    the exception, and Windows refused the rename the refusal tells a
    person to make (WinError 32)."""
    module, kind = ((store, store._Connection) if which == "store"
                    else (checkpoint, checkpoint._Connection))
    damaged = tmp_path / f"{which}.db"
    damaged.write_bytes(b"fabricated garbage, not a database" * 40)
    before = _still_open(kind)
    with pytest.raises((store.StoreError, checkpoint.CheckpointError)):
        module.open(damaged)
    assert _still_open(kind) == before
    os.replace(damaged, tmp_path / f"{which}.db.set-aside")     # WinError 32 while held
    assert not damaged.exists()


# --------------------------------------- decision 159: the final review's fixes ----


def test_a_rewrite_the_checkpoint_never_saw_is_refused_by_rebuild_and_points_to_recover(
        conn, root, by_hand, tmp_path):
    """MF2: with no checkpoint row at all - the first pass after installing
    159, a new machine, a damaged checkpoint set aside - a rebuild still
    never drops lines it has not exported, and decision 137's own refusals
    point to recover, not to rebuild."""
    three_lines(conn, by_hand)
    where = checkpoint.path_for(tmp_path / "app" / store.STORE_FILENAME)
    where.rename(where.with_name(where.name + ".damaged"))                # no row for anything
    path = ledger.path_for(by_hand)
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:2]))
    with pytest.raises(store.StoreError) as truncated:
        store.catch_up(conn, root, by_hand)
    assert str(truncated.value).endswith(ledger.RUN_RECOVER)
    before = rows(conn, "events")
    with pytest.raises(store.WouldDiscard, match="rebuild would discard them"):
        build(conn, root, by_hand)
    assert rows(conn, "events") == before
    done = store.recover(conn, root, by_hand)                              # recover exports first
    assert len(done.export.read_text(encoding="utf-8").splitlines()) == 3
    assert [(one.seq, one.side) for one in done.differences] == [(3, store.ON_STORE)]


def test_recover_never_names_an_export_shorter_than_the_record_as_the_one_to_restore(
        conn, fresh, root, by_hand):
    """MF3: an unreadable record is said by the first look, with no replay
    offered; the store's export is named as a copy to restore from only
    when it holds every line the record still reads - and a store holding
    nothing for the return writes no export at all."""
    three_lines(conn, by_hand)
    path = ledger.path_for(by_hand)
    with path.open("ab") as handle:
        handle.write(b'{"event": "scanned", "note": "Fabricated" "x"}\n')

    covered = store.recover(conn, root, by_hand)                            # the store holds all 3
    assert "the record itself does not read" in covered.refusal
    assert "(it is not JSON)" in covered.refusal and ledger.RUN_RECOVER not in covered.refusal
    assert str(covered.export) in covered.refusal and str(covered.record_copy) in covered.refusal

    nothing = store.recover(fresh, root, by_hand)                           # a store that never met it
    assert nothing.export is None and nothing.record_copy.is_file()
    assert "holds no copy of this return" in nothing.refusal and "off-drive copy" in nothing.refusal
    assert not any(p.stat().st_size == 0 for p in nothing.record_copy.parent.iterdir())

    conn.execute("DELETE FROM events WHERE seq > 1")                       # a store behind the record
    short = store.recover(conn, root, by_hand)
    assert str(short.export) not in short.refusal and "holds no copy" in short.refusal
    for done in (covered, nothing, short):
        assert not done.accepted
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:3]))


def test_recover_looking_at_an_unreadable_record_offers_no_replay(conn, root, by_hand, tmp_path):
    three_lines(conn, by_hand)
    with ledger.path_for(by_hand).open("ab") as handle:
        handle.write(b'{"event": "scanned", "note": "Fabricated" "x"}\n')
    conn.close()
    store.close()
    shown = cli(tmp_path / "app" / store.STORE_FILENAME, "recover", root, "--engagement", by_hand)
    assert shown.returncode == 1
    assert "the record itself does not read" in shown.stdout and "--accept-loss" not in shown.stdout
    ledger.path_for(by_hand).write_bytes(
        b"".join(ledger.path_for(by_hand).read_bytes().splitlines(keepends=True)[:3]))


@pytest.mark.parametrize("pad", [" {}", "{} ", "{}\t"], ids=["leading", "trailing", "tab"])
def test_a_spaced_name_of_this_machine_never_passes_for_another_machine(conn, fresh, root, by_hand, pad):
    """SF3: ``"VM "`` on the machine ``vm`` is refused as a line whose
    writer is in a shape the tracker never writes - by the store's one
    admission, whose rule of a writer the checkpoint's judgment asks first
    (decision 187) - and is never named for a person to acknowledge;
    compared, it is this machine."""
    from tracker.locking import is_this_host, this_host

    assert is_this_host(pad.format(this_host().upper()))
    three_lines(conn, by_hand)
    written_elsewhere(by_hand, ledger.new(ledger.FILED, key=A_ROW_ORIGINAL, row=a_row(decision="Filed")),
                      host=pad.format(this_host().upper()))
    with pytest.raises(store.StoreError, match="line 4 of the record is malformed .*carries 'host' "
                                               "that must be a machine's name"):
        store.catch_up(fresh, root, by_hand)
    assert store.foreign_lines() == []
    path = ledger.path_for(by_hand)
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:3]))


def test_a_machine_whose_name_no_line_may_carry_writes_nothing(conn, root, by_hand, monkeypatch):
    """Decision 159 carried onto 187: the line admitted at the door is the
    line exactly as ``ledger.line_of`` will write it, writer included, so
    this machine's own name is held to the one rule of a writer - and a
    name it refuses writes nothing, to the record or the store."""
    build(conn, root, by_hand)
    before = ledger.path_for(by_hand).read_bytes()
    monkeypatch.setattr(ledger, "this_host", lambda: "office pc")
    with engagement_lock(by_hand), pytest.raises(store.StoreError) as refused:
        store.record(conn, by_hand, learned("A01", "lender"))
    assert "carries 'host' that must be a machine's name" in str(refused.value)
    assert "nothing was written" in str(refused.value)
    assert ledger.path_for(by_hand).read_bytes() == before



def test_one_upgrade_policy_a_version_sixteen_store_is_upgraded_in_place_and_never_set_aside(tmp_path):
    """Decisions 204, 190 and 159: a version :data:`store._IN_PLACE` names gains
    its columns where it stands - never set aside, its verdict cache kept -
    and only an older version is set aside and rebuilt. The record
    checkpoint beside it is a file of its own with its own version, and no
    step of the store's upgrade touches it."""
    path = tmp_path / "app" / store.STORE_FILENAME
    store.open(path).close()
    heads = checkpoint.path_for(path)
    checkpoint.open(heads).close()
    before = heads.read_bytes()
    written_at_sixteen = sqlite3.connect(path)
    for statement in AS_AT_16:                     # 204's column and 190's three
        written_at_sixteen.execute(statement)
    written_at_sixteen.execute("PRAGMA user_version = 16")
    written_at_sixteen.close()

    store.open(path).close()
    assert one_value(path, "PRAGMA user_version") == store.SCHEMA_VERSION
    assert not list(path.parent.glob(f"{store.STORE_FILENAME}.v*.old*"))
    assert one_value(path, "SELECT count(*) FROM sqlite_master WHERE name = ?",
                     store.VERDICTS_TABLE) == 1
    assert heads.read_bytes() == before
    assert one_value(heads, "PRAGMA user_version") \
        == checkpoint.CHECKPOINT_VERSION

    older = sqlite3.connect(path)
    older.execute(f"PRAGMA user_version = {REFUSED_EARLIER}")
    older.close()
    store.open(path).close()
    assert path.with_name(f"{store.STORE_FILENAME}.v{REFUSED_EARLIER}.old").is_file()
    assert heads.read_bytes() == before


def test_188s_accepted_word_and_204s_waiting_row_are_lines_like_any_other(conn, root, by_hand, fresh):
    """Decisions 188 and 204 carried under 159: a person's word that a
    folder's name is accepted, and a row parked waiting for a click, are
    written through ``store.record`` - so each carries the record's link, its
    writer and its format, is admitted by the one gate, and is caught up by
    a store built from nothing beside this machine's checkpoint."""
    from tracker.records import WaitsFor, format_waits_for

    waiting = format_waits_for(WaitsFor(household="Jones Family", return_name="1040 - Jones",
                                        identifiers=("A01",)))
    recorded(conn, by_hand,
             ledger.new(ledger.RULES_CHANGED, info={"client": "Test Client"},
                        **{ledger.ACCEPTED_KEY: ledger.FOLDER_NAME_ACCEPTED}),
             ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL,
                        row=a_row(decision="Needs Review", waits_for=waiting)))
    for line in ledger.read_events(by_hand)[-2:]:
        assert ledger.LINE_KEYS <= set(line)
    assert said(conn, root, by_hand) == []
    assert store.catch_up(fresh, root, by_hand) == len(ledger.read_events(by_hand))
    assert [row["waits_for"] for row in store.documents(fresh, by_hand)] == [waiting]


def _a_forged_this_host_rewrite(conn, by_hand):
    """The port review's M1 probe: three lines recorded, the third replaced
    by a linked line claiming this machine that it never wrote."""
    from tracker.locking import this_host

    three_lines(conn, by_hand)
    path = ledger.path_for(by_hand)
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:2]))
    written_elsewhere(by_hand, ledger.new(ledger.FILED, key=A_ROW_ORIGINAL,
                                          row=a_row(decision="Filed", original_name="forged.pdf")),
                      host=this_host())


@pytest.mark.parametrize("extra", [
    (), ("--accept-loss", "1040 - Test Client "), ("--accept-loss", "1040 - TEST CLIENT"), ("whole root",),
], ids=["no-name", "a-trailing-space", "another-case", "the-whole-root"])
def test_rebuild_discard_accepts_nothing_without_the_returns_name_typed(conn, root, by_hand, tmp_path,
                                                                         extra):
    """The port review's M1, ruled: decision 188's --discard passes nothing
    on its own. A loss is accepted only for one return and only by its
    folder's name typed exactly (the council's Solution 3) - so with no
    name, a wrong name or no --engagement, a forged rewrite is refused,
    nothing is applied, and the checkpoint is unchanged."""
    _a_forged_this_host_rewrite(conn, by_hand)
    before = rows(conn, "events")
    heads = checkpoint.path_for(tmp_path / "app" / store.STORE_FILENAME)
    with checkpoint.opened(heads) as held:
        vouched = checkpoint.vouched(held, key_of(by_hand))
    conn.close()
    store.close()
    target = [] if extra == ("whole root",) else ["--engagement", by_hand]
    said = cli(tmp_path / "app" / store.STORE_FILENAME, "rebuild", root, *target, "--discard",
               *(() if extra == ("whole root",) else extra))
    assert said.returncode != 0, said.stdout
    assert "built" not in said.stdout
    again = store.connect(tmp_path / "app" / store.STORE_FILENAME)
    assert rows(again, "events") == before
    assert not any("forged.pdf" in str(row) for row in rows(again, "events"))
    with checkpoint.opened(heads) as held:
        assert checkpoint.vouched(held, key_of(by_hand)) == vouched
    store.close()


def test_rebuild_discard_with_the_name_typed_is_recovers_path(conn, root, by_hand, tmp_path):
    """The one way a loss is accepted on the command line: one return, its
    name typed exactly - recover's own path, its export and its difference
    first."""
    a_store_ahead_of_its_record(conn, by_hand)
    conn.close()
    store.close()
    said = cli(tmp_path / "app" / store.STORE_FILENAME, "rebuild", root, "--engagement", by_hand,
               "--discard", "--accept-loss", by_hand.name)
    assert said.returncode == 0, said.stdout + said.stderr
    assert "kept the store's lines in" in said.stdout and store.ON_STORE in said.stdout
    assert store.ACCEPTED.format(n=1) in said.stdout


def test_an_export_that_cannot_be_written_is_refused_by_name_and_discards_nothing(
        conn, root, by_hand, monkeypatch):
    """The port review's S2: a recover whose export cannot be written says
    so - the class and the folder - and nothing is discarded; never a
    traceback."""
    a_store_ahead_of_its_record(conn, by_hand)
    before = rows(conn, "events")

    def refused(path, data):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(store, "_exclusively", refused)
    with pytest.raises(store.StoreError, match=r"the export could not be written into .*"
                                               r"\(PermissionError \(EACCES\)\); nothing was discarded"):
        store.recover(conn, root, by_hand, accept_loss=by_hand.name)
    assert rows(conn, "events") == before


def test_households_are_every_stored_household_row_read_as_it_stands(root, monkeypatch):
    """Decision 192: the card's *Fed by* asks every household who feeds it,
    and may not walk the practice or read every journal to learn it. The
    store answers with its household rows - never a return's - exactly as
    they stand, even with a line behind them it has not applied."""
    from dataclasses import replace

    from tests.conftest import written_elsewhere
    from tracker.households import load_household_info, save_household
    from tracker.layout import private_household_dir
    from tracker.records import Feed

    make_engagement(root, ITEMS, household="Park Family")
    make_engagement(root, ITEMS, household="Park & Lee LLC")
    family = private_household_dir(root, "Park Family")
    feed = Feed("Park & Lee LLC", "1120S - Park & Lee LLC")
    save_household(family, replace(load_household_info(family), feeds=(feed,)))
    # A line behind the store is one another machine wrote: every line this
    # machine writes goes through the store (decision 159's checkpoint).
    written_elsewhere(family, ledger.new(ledger.HOUSEHOLD_CHANGED, **{
        ledger.HOUSEHOLD_KEY: {"feeds": []}}))
    read: list[Path] = []
    real = Path.read_bytes

    def counting(self):
        if self.name == ledger.LEDGER_FILENAME:
            read.append(Path(self))
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", counting)

    rows = dict(store.households(store.connect()))

    assert sorted(key.rsplit("/", 1)[-1] for key in rows) == ["Park & Lee LLC", "Park Family"]
    by_name = {key.rsplit("/", 1)[-1]: info for key, info in rows.items()}
    assert by_name["Park Family"].feeds == (feed,)       # the store's, not the line behind it
    assert by_name["Park & Lee LLC"].feeds == ()
    assert read == []
    # The recorder sees a journal read when one is made, and the line
    # behind the store is there to be read.
    assert load_household_info(family).feeds == ()
    assert ledger.path_for(family) in read


# ------------------- decision 186's rebase review: the checkpoint left beside the program ----


def _upgraded_before_the_move(monkeypatch) -> tuple[Path, Path]:
    """A machine that ran 159 before 186, upgraded before its checkpoint was
    moved: the store and checkpoint the fixture made beside the settings
    file (159's layout), and the store now asked of the data home, where no
    checkpoint is yet. Returns the old checkpoint and where the new one
    would be."""
    from tracker import settings

    old = settings.settings_dir() / checkpoint.CHECKPOINT_FILENAME
    assert old.is_file()
    store.close()
    monkeypatch.setenv(store.ENV_STORE, str(settings.data_home() / store.STORE_FILENAME))
    return old, checkpoint.path_for(store.store_path())


def test_no_fresh_checkpoint_is_made_while_the_old_one_sits_beside_the_program(root, engagement,
                                                                                monkeypatch):
    """MF1: a fresh checkpoint would seed every record "as it is" and drop
    what the old one vouched for. Every open that could make one refuses -
    the root's proof, claiming or not, and a person's acknowledgement -
    naming the old file and the folder it belongs in; nothing is made and
    the old file is not touched."""
    old, new = _upgraded_before_the_move(monkeypatch)
    before = old.read_bytes()
    said = checkpoint.LEFT_BEHIND.format(old=old.resolve(), home=new.parent)
    for attempt in (lambda: store.prove_the_root(root), lambda: store.prove_the_root(root, claim=False),
                    lambda: store.acknowledge_foreign(engagement)):
        with pytest.raises(checkpoint.CheckpointLeftBehind) as refused:
            attempt()
        assert str(refused.value) == said
    assert not new.exists() and old.read_bytes() == before


def test_a_catch_up_says_the_checkpoint_left_behind_as_that_returns_problem(root, engagement, monkeypatch):
    """MF1: the catch-up every reader runs first (a read-only view of one
    return included) makes no checkpoint either; it says so as a
    :class:`store.StoreError`, so every caller that names one return's
    problem names this, and carries the two folders for the app."""
    old, new = _upgraded_before_the_move(monkeypatch)
    with pytest.raises(store.CheckpointNotMade) as refused:
        ensure(engagement)
    assert isinstance(refused.value, store.StoreError)
    assert (refused.value.old, refused.value.home) == (old.resolve(), new.parent)
    assert not new.exists()


def test_moving_or_renaming_the_old_checkpoint_lifts_the_refusal(root, engagement, monkeypatch):
    """MF1's escape: the runbook's move - or keeping it under a dated name -
    is all it takes; moved into the data home, it is the checkpoint, with
    the root it claimed."""
    old, new = _upgraded_before_the_move(monkeypatch)
    kept = old.with_name(old.name + ".2026-09-27")
    old.rename(kept)
    store.prove_the_root(root, claim=False)                  # nothing to refuse, nothing made
    assert not new.exists()
    kept.rename(old)
    new.parent.mkdir(parents=True, exist_ok=True)
    os.replace(old, new)
    store.prove_the_root(root)
    with checkpoint.opened(new) as held:
        assert checkpoint.root_of(held) == str(root.resolve())
    ensure(engagement)


def test_the_store_beside_the_settings_file_is_never_refused_its_checkpoint(root, engagement):
    """The suite's own shape (``TRACKER_STORE`` beside the settings file):
    the old place and the new are the same file, so a checkpoint missing
    there is simply made."""
    where = checkpoint.path_for(store.store_path())
    store.close()
    where.unlink()
    store.prove_the_root(root)
    assert where.is_file()


def test_a_record_written_inside_a_read_only_reply_is_refused_before_anything_is_written(tmp_path):
    """The review of P118, SHOULD-3: a read-only reply records nothing."""
    from tracker.settings import one_reading

    folder = tmp_path / "return"
    folder.mkdir()
    with one_reading(), pytest.raises(RuntimeError, match="read-only reply"):
        store.record(None, folder, {"event": "anything"})
    assert list(folder.iterdir()) == []


# ------------------------------- pilot P170: the related households (schema 20, admission 3) ----


def test_a_households_related_list_is_stored_and_read_back_as_it_was_saved(root):
    """Pilot P170: the related households are one JSON list in one column of
    the household's row, read back through the record's own reader, and a
    household saved before the field existed reads as related to none."""
    from dataclasses import replace

    from tracker.households import load_household_info, save_household
    from tracker.layout import private_household_dir

    make_engagement(root, ITEMS, household="Park Family")
    make_engagement(root, ITEMS, household="Lee Family")
    family = private_household_dir(root, "Park Family")
    assert load_household_info(family).related == ()
    save_household(family, replace(load_household_info(family), related=("Lee Family",)))
    by_name = {key.rsplit("/", 1)[-1]: info for key, info in store.households(store.connect())}
    assert by_name["Park Family"].related == ("Lee Family",)
    assert by_name["Lee Family"].related == ()
    assert load_household_info(family).related == ("Lee Family",)


def test_a_related_list_that_is_not_folder_names_is_refused_at_admission():
    """Pilot P170 (admission 3): a ``household_changed`` line whose related
    list is not a list of text, or names something that is not one folder
    name, is refused by name before it reaches a column."""
    from tracker.layout import NAME_ILLEGAL, PRIVATE_TREE

    household = f"{PRIVATE_TREE}/Smith Family"
    for related in ("Lee Family", [1], [{"name": "Lee"}]):
        with pytest.raises(store.StoreError, match="'related' that is not a list of household names"):
            store._refuse_a_malformed_line(ledger.new(ledger.HOUSEHOLD_CHANGED, household={"related": related}),
                                           2, household, kind=store.KIND_HOUSEHOLD)
    with pytest.raises(store.StoreError) as refused:
        store._refuse_a_malformed_line(ledger.new(ledger.HOUSEHOLD_CHANGED, household={"related": ["Lee/.."]}),
                                       2, household, kind=store.KIND_HOUSEHOLD)
    assert f"'related' that is not one folder name ({NAME_ILLEGAL})" in str(refused.value)
    store._refuse_a_malformed_line(ledger.new(ledger.HOUSEHOLD_CHANGED, household={"related": ["Lee Family"]}),
                                   2, household, kind=store.KIND_HOUSEHOLD)


def test_a_store_at_version_19_gains_the_related_column_in_place_as_a_rebuild_writes_it(conn, root, by_hand, tmp_path):
    """Pilot P170: version 20's column is added where the file stands -
    nothing set aside, the verdict cache kept - holding the record's own
    default, ``[]``, on every row, which is what a rebuild writes, so
    ``store check`` finds nothing on the upgraded file."""
    build(conn, root, by_hand)
    path = tmp_path / "app" / store.STORE_FILENAME
    conn.close()
    written = sqlite3.connect(path)
    for statement in AS_AT_19:
        written.execute(statement)
    written.execute("PRAGMA user_version = 19")
    written.commit()
    written.close()

    upgraded = store.open(path)
    try:
        assert upgraded.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION == 20
        assert not list(path.parent.glob(f"{store.STORE_FILENAME}.v*.old*"))
        assert {row[0] for row in upgraded.execute("SELECT household_related FROM engagements")} == {"[]"}
        assert store.check(upgraded, root, by_hand) == []
    finally:
        upgraded.close()


# ------------------------------------- the checkpoint held a command (P214) ----


def _counting_opens(monkeypatch) -> list[Path]:
    """Every checkpoint connection opened from here on, by file."""
    opened: list[Path] = []
    real = checkpoint._connect

    def counted(path):
        opened.append(Path(path))
        return real(path)

    monkeypatch.setattr(checkpoint, "_connect", counted)
    return opened


def test_one_command_opens_the_checkpoint_once(root, by_hand, monkeypatch):
    """P214: the checkpoint is held beside the store for the command - one
    open, however many records are proved, written and read."""
    store.close()                                   # what the fixtures' setup held
    opened = _counting_opens(monkeypatch)
    conn = store.connect()
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, scanned(A01=Status.RECEIVED))
        store.record(conn, by_hand, scanned(C01=Status.RECEIVED))
    load_manifest(by_hand)
    store.foreign_lines()
    store.prove_the_root(root)
    assert len(opened) == 1
    assert store._CHECKPOINT is not None


def test_closing_the_store_closes_the_checkpoint_and_takes_its_side_files(root, by_hand):
    """The last connection's close folds the write-ahead log into the file
    and removes it: with the app closed the checkpoint is one file."""
    conn = store.connect()
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, scanned(A01=Status.RECEIVED))
    where = checkpoint.path_for(store.store_path())
    assert where.with_name(checkpoint.CHECKPOINT_WAL_FILENAME).exists()
    store.close()
    assert store._CHECKPOINT is None
    assert where.is_file()
    for side in (checkpoint.CHECKPOINT_WAL_FILENAME, checkpoint.CHECKPOINT_SHM_FILENAME,
                 checkpoint.CHECKPOINT_JOURNAL_FILENAME):
        assert not where.with_name(side).exists(), side
    with checkpoint.opened(where) as again:
        assert checkpoint.vouched(again, key_of(by_hand))[0] == len(ledger.read_events(by_hand))


def test_a_checkpoint_error_drops_the_held_connection_and_the_next_question_opens_it_again(
        root, by_hand, monkeypatch):
    """A busy or damaged checkpoint is never held open against the
    runbook's set-aside step: the error is said as before, the connection
    let go of, and the next question opens the file afresh."""
    conn = store.connect()
    build(conn, root, by_hand)
    store.close()
    conn = store.connect()
    opened = _counting_opens(monkeypatch)
    real = checkpoint.vouched
    refusals = iter([checkpoint.CheckpointUnavailable("record-heads.db", "SQLITE_BUSY")])

    def busy_once(held, key):
        for refusal in refusals:
            raise refusal
        return real(held, key)

    monkeypatch.setattr(checkpoint, "vouched", busy_once)
    with engagement_lock(by_hand), pytest.raises(store.StoreError, match="checkpoint is busy"):
        store.record(conn, by_hand, scanned(A01=Status.RECEIVED))
    assert store._CHECKPOINT is None
    with engagement_lock(by_hand):
        store.record(conn, by_hand, scanned(A01=Status.RECEIVED))
    assert len(opened) == 2 and store._CHECKPOINT is not None     # the first open, then afresh


def test_expect_is_on_disk_before_the_journal_line_and_advance_after_it(root, by_hand, monkeypatch):
    """``record()``'s two checkpoint transactions keep their order and
    number: the intent is committed - another connection sees it - before
    the journal line is appended, and the advance after it."""
    conn = store.connect()
    build(conn, root, by_hand)
    where = checkpoint.path_for(store.store_path())
    key = key_of(by_hand)
    seen = []
    real_append = ledger.append

    def watched(engagement_dir, event):
        with checkpoint.opened(where) as other:
            seen.append((checkpoint.vouched(other, key), checkpoint.intent(other, key)))
        return real_append(engagement_dir, event)

    already = len(ledger.read_events(by_hand))
    monkeypatch.setattr(ledger, "append", watched)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, scanned(A01=Status.RECEIVED))
    (vouched_before, intent_before), = seen
    assert vouched_before[0] == already
    assert intent_before is not None and intent_before.start == already and len(intent_before.heads) == 1
    with checkpoint.opened(where) as other:
        assert checkpoint.vouched(other, key)[0] == already + 1 and checkpoint.intent(other, key) is None


# ----------------------------------------- answers kept for one hold (P215) ----


def _counting(monkeypatch, module, name) -> list:
    calls = []
    real = getattr(module, name)

    def counted(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(module, name, counted)
    return calls


def test_an_engagements_key_is_worked_out_once_per_hold(root, by_hand, monkeypatch):
    """P215 (findings-2 #2): inside a household's hold the key is worked
    out once; the row itself is read every time."""
    from tracker import settings

    conn = store.connect()
    build(conn, root, by_hand)
    asked = _counting(monkeypatch, store, "engagement_path")
    with settings.one_household():
        first = store._engagement_row(conn, by_hand)
        again = store._engagement_row(conn, by_hand)
    assert first is not None and dict(first) == dict(again)
    assert len(asked) == 1
    store._engagement_row(conn, by_hand)                       # outside a hold: asked afresh
    assert len(asked) == 2


def test_a_key_asked_before_its_folder_existed_is_asked_again_after(root, monkeypatch):
    """A folder the pass makes later is never answered from before it
    existed (P207's rule 2): its key is kept only once it is there."""
    from tracker import settings

    conn = store.connect()
    later = root / "J Park & Associates" / "Later Family" / "2025" / "1040 - Later Client"
    asked = _counting(monkeypatch, store, "engagement_path")
    with settings.one_household():
        assert store._engagement_row(conn, later) is None
        assert store._engagement_row(conn, later) is None
        assert len(asked) == 2
        later.mkdir(parents=True)
        store._engagement_row(conn, later)
        store._engagement_row(conn, later)
    assert len(asked) == 3


def test_a_record_read_is_never_kept_past_a_rebuild_of_its_row(root, by_hand):
    """P215 (E2): a held read is kept while the row's head and applied
    lines are as they were, built again once a line is recorded, and built
    again after the row is rebuilt from the same journal."""
    from tracker import settings

    conn = store.connect()
    build(conn, root, by_hand)
    built = []

    def read():
        built.append(1)
        return [len(built)]

    with settings.one_household():
        assert store.held_read(conn, by_hand, "probe", read) == [1]
        kept = store.held_read(conn, by_hand, "probe", read)
        assert kept == [1] and len(built) == 1
        kept.append("a caller's own change")
        assert store.held_read(conn, by_hand, "probe", read) == [1]       # each caller its own list
        with engagement_lock(by_hand):
            store.record(conn, by_hand, scanned(A01=Status.RECEIVED))
        assert store.held_read(conn, by_hand, "probe", read) == [2]
        build(conn, root, by_hand)                                        # the same journal, rebuilt
        assert store.held_read(conn, by_hand, "probe", read) == [3]
        assert store.held_read(conn, by_hand, "probe", read) == [3]
    assert store.held_read(conn, by_hand, "probe", read) == [4]           # nothing past the hold
