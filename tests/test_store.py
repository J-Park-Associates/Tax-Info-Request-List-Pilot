"""Tests for tracker/store.py - the database on this machine, rebuilt from the record.

The store's main claim is not made here either: it is the autouse fixture
in tests/conftest.py, which builds a store for every engagement the suite
leaves behind and holds it to what the readers say. What is made here is
the store's own behaviour - the schema it refuses to guess at, the
journal-then-apply guarantee and the replay that repairs a torn one, the
rebuild that is also the recovery, which of the record and the workbook
wins a row, the order a row that changed identity keeps, the three words
it answers its own state in, the export, and the one placement rule: the
file is never under the clients root, because that folder syncs.
"""

from __future__ import annotations

import csv
import datetime as dt
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import live_readings, workbook_readings
from tests.test_scanner import text_pdf
from tracker import ledger, store, view
from tracker.filer import INDEX_FILENAME, file_drops, read_index
from tracker.locking import engagement_lock
from tracker.manifest import (
    RequestItem,
    Status,
    create_template,
    load_manifest,
    write_statuses,
)
from tracker.records import StatusUpdate, entry_to_json, ledger_key
from tracker.scaffold import MANIFEST_FILENAME, SHARED_DIR_NAME, scaffold_engagement

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
    eng = root / "Smith Family 2025"
    eng.mkdir()
    create_template(eng / MANIFEST_FILENAME, ITEMS)
    scaffold_engagement(eng)
    return eng


@pytest.fixture
def by_hand(engagement):
    """An engagement whose record this test writes itself.

    These tests are about the store's fold, not the filer's, so they append
    rows no index beside them has ever held - and the suite's own record
    fixture holds every record to the index beside it. The record is
    removed when the test ends, the way the journal's own tests put back
    what they tore, so the folder the fixtures then see is one the
    workbooks answer for.
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
    return text_pdf(engagement / SHARED_DIR_NAME / name, text)


def build(conn, root, engagement):
    store.rebuild_engagement(conn, root, engagement, **workbook_readings(engagement))


def said(conn, root, engagement):
    return store.check(conn, root, engagement, **live_readings(engagement))


def rows(conn, table):
    return [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]


def a_row(**fields) -> dict:
    base = {"received": "2026-07-01", "original_name": "w2.pdf", "size_kb": 1.0,
            "digest": "abc", "identifier": "", "prepared_location": "",
            "pbc_location": "Shared/PBC/w2.pdf", "decision": "Needs Review",
            "reason": "", "candidates": "", "evidence": "", "also_filed": ""}
    return {**base, **fields}


# --------------------------------------------------------------- the schema ----


def test_opening_a_file_that_is_not_there_creates_the_schema(tmp_path):
    path = tmp_path / "app" / store.STORE_FILENAME
    assert not path.exists()

    conn = store.open(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION == 1
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert tables == {"engagements", "requests", "statuses", "learned_keywords",
                          "documents", "events"}
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

    with pytest.raises(store.StoreError, match="engagement lock"):
        store.record(conn, engagement, ledger.new(
            ledger.KEYWORD_LEARNED, **{ledger.IDENTIFIER_KEY: "A01",
                                       ledger.KEYWORD_KEY: "lender"}))

    assert not ledger.path_for(engagement).exists()
    assert rows(conn, "events") == [] and rows(conn, "learned_keywords") == []


def test_one_call_is_one_transaction_over_the_journal_and_the_tables(conn, root, by_hand):
    build(conn, root, by_hand)
    filed = ledger.new(ledger.FILED, key="Shared/PBC/w2.pdf",
                       row=a_row(decision="Filed", identifier="A01"))
    taught = ledger.new(ledger.KEYWORD_LEARNED, **{ledger.IDENTIFIER_KEY: "A01",
                                                   ledger.KEYWORD_KEY: "lender"})

    with engagement_lock(by_hand):
        applied = store.record(conn, by_hand, filed, taught)

    assert applied == 2
    assert len(ledger.read_events(by_hand)) == 2
    assert [row["seq"] for row in conn.execute("SELECT seq FROM events ORDER BY seq")] == [1, 2]
    assert conn.execute("SELECT decision FROM documents").fetchone()[0] == "Filed"
    assert conn.execute("SELECT keyword FROM learned_keywords").fetchone()[0] == "lender"
    assert conn.execute("SELECT applied_seq FROM engagements").fetchone()[0] == 2


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

    assert len(ledger.read_events(by_hand)) == 1        # the journal holds it
    assert rows(conn, "documents") == []                   # the store does not
    monkeypatch.undo()

    assert store.sync(conn, root, by_hand) == 1
    assert conn.execute("SELECT decision FROM documents").fetchone()[0] == "Filed"
    assert conn.execute("SELECT applied_seq FROM engagements").fetchone()[0] == 1
    assert store.sync(conn, root, by_hand) == 1         # and again changes nothing


def test_a_torn_last_line_is_not_replayed_until_it_is_whole(conn, root, by_hand):
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, ledger.new(
            ledger.FILED, key="Shared/PBC/w2.pdf", row=a_row(decision="Filed")))
    path = ledger.path_for(by_hand)
    path.write_bytes(path.read_bytes() + b'{"event": "filed", "key": "Shared/PBC/tor')

    assert store.sync(conn, root, by_hand) == 1
    assert len(rows(conn, "documents")) == 1


def test_recording_while_the_store_is_behind_the_journal_is_refused(conn, root, by_hand):
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        ledger.append(by_hand, ledger.new(
            ledger.FILED, key="Shared/PBC/w2.pdf", row=a_row()))
        with pytest.raises(store.StoreError, match="sync"):
            store.record(conn, by_hand, ledger.new(
                ledger.FILED, key="Shared/PBC/other.pdf", row=a_row()))


# ------------------------------------------------------------- the rebuild ----


def test_a_rebuild_run_twice_says_and_holds_exactly_the_same(conn, root, engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    file_drops(engagement, today=DAY1)

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
    engagement is made to describe it without opening a workbook, taking a
    lock or writing a byte in the folder."""
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
    recorded = len(ledger.read_events(engagement))
    fresh = store.open(tmp_store(engagement))
    try:
        assert store.documents(fresh, engagement) == []

        assert store.follow_the_journal(fresh, root, engagement) == recorded

        rows = store.documents(fresh, engagement)
        assert [row["pbc_location"] for row in rows] == [
            entry.pbc_location for entry in read_index(engagement)]
        # The person's half is left blank on purpose: the journal cannot
        # answer for it, and an empty digest is how ensure() knows to read
        # the sheet.
        assert fresh.execute("SELECT manifest_digest FROM engagements").fetchone()[0] == ""
        assert fresh.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 0
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


def test_a_row_the_record_holds_wins_over_the_workbooks_own_reading(conn, root, by_hand):
    drop(by_hand, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(by_hand, today=DAY1)
    key = ledger_key(read_index(by_hand / INDEX_FILENAME)[0])
    # The record says one thing; the workbook reading handed to the rebuild
    # says another for the same original. The record is the record.
    with engagement_lock(by_hand):
        ledger.append(by_hand, ledger.new(
            ledger.UNFILED_BY_PERSON, key=key,
            row=a_row(pbc_location=key, decision="Needs Review", reason="sent back")))
    readings = workbook_readings(by_hand)
    store.rebuild_engagement(conn, root, by_hand, **readings)

    row = conn.execute("SELECT * FROM documents").fetchone()
    assert row["reason"] == "sent back" and row["seq"] > store.WORKBOOK_SEQ


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
        return store.state(conn, by_hand,
                           rules_digest_now=view.rules_digest(by_hand),
                           ledger_head_now=ledger.head(by_hand))

    assert now() == store.UNKNOWN
    build(conn, root, by_hand)
    assert now() == store.CURRENT

    write_statuses(by_hand / MANIFEST_FILENAME,
                   {"A01": StatusUpdate(status=Status.MISSING)})
    assert now() == store.BEHIND                       # the rules workbook moved

    build(conn, root, by_hand)
    assert now() == store.CURRENT
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
    file_drops(engagement, today=DAY1)
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
    assert documents[0]["original_name"] == "=SUM scan.pdf"
    assert all(isinstance(value, str) for value in documents[0].values())


def test_the_export_carries_nothing_the_index_and_the_request_list_do_not(
        conn, root, engagement, tmp_path):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025 Jane Q Client")
    file_drops(engagement, today=DAY1)
    build(conn, root, engagement)

    store.export(conn, tmp_path / "out")

    for path in (tmp_path / "out").iterdir():
        text = path.read_text(encoding="utf-8-sig")
        # A word out of the document itself, which no reading of the index
        # or the request list ever carries.
        assert "Jane Q Client" not in text


# ------------------------------------------------------------------- the CLI ----


def cli(*argv):
    return subprocess.run([sys.executable, "-m", "tracker.store", *[str(a) for a in argv]],
                          cwd=REPO, capture_output=True, text=True)


def test_the_command_line_builds_every_engagement_under_a_root(root, tmp_path):
    for name in ("Smith Family 2025", "Jones Family 2025"):
        folder = root / name
        folder.mkdir()
        create_template(folder / MANIFEST_FILENAME, ITEMS)
        scaffold_engagement(folder)
    path = tmp_path / "app" / store.STORE_FILENAME

    built = cli(path, "rebuild", root)
    assert built.returncode == 0, built.stdout + built.stderr

    conn = store.open(path)
    try:
        assert {row[0] for row in conn.execute("SELECT path FROM engagements")} == {
            "Smith Family 2025", "Jones Family 2025"}
    finally:
        conn.close()
    assert cli(path, "check", root).returncode == 0


def test_the_command_lines_check_exits_one_and_names_what_disagrees(root, engagement, tmp_path):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
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
    """The explicit form of the layers test's claim: nothing that opens a
    workbook is reachable from importing this module."""
    source = (Path(store.__file__)).read_text(encoding="utf-8")
    top, _, command_line = source.partition('if __name__ == "__main__":')
    for module in ("filer", "manifest", "view", "validators", "registry", "scaffold"):
        assert f"tracker.{module}" not in top.replace(":mod:`tracker.", "")
        assert f"tracker import {module}" not in top
    assert "from tracker.filer import" in command_line       # and the CLI does reach them


# ------------------------------------------------------- the readers, checked ----


def test_the_check_names_the_engagement_the_row_and_the_field(conn, root, engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
    build(conn, root, engagement)
    assert said(conn, root, engagement) == []

    conn.execute("UPDATE documents SET reason = 'something else'")
    sentence = said(conn, root, engagement)[0]
    assert engagement.name in sentence and "reason" in sentence and "something else" in sentence


def test_an_engagement_the_store_has_never_seen_is_said_so_rather_than_passed(
        conn, root, engagement):
    sentence = said(conn, root, engagement)
    assert len(sentence) == 1 and "does not hold this engagement" in sentence[0]


def test_the_rebuilt_rows_are_the_readers_rows_after_a_person_files_a_parked_one(
        conn, root, engagement):
    from tracker.filer import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = file_drops(engagement, today=DAY1).review[0]
    assign_review_file(engagement, parked.pbc_location, "C01", keyword="lender", today=DAY2)

    build(conn, root, engagement)

    assert said(conn, root, engagement) == []
    assert conn.execute("SELECT keyword FROM learned_keywords").fetchone()[0] == "lender"
    assert conn.execute("SELECT identifier FROM documents").fetchone()[0] == "C01"


def test_every_request_the_manifest_holds_has_a_rule_and_a_status_in_the_store(
        conn, root, engagement):
    build(conn, root, engagement)

    assert conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == len(ITEMS)
    assert conn.execute("SELECT COUNT(*) FROM statuses").fetchone()[0] == len(ITEMS)
    stored = conn.execute('SELECT * FROM requests WHERE "identifier" = ?', ("A01",)).fetchone()
    item = next(i for i in load_manifest(engagement / MANIFEST_FILENAME) if i.identifier == "A01")
    assert stored["required_keywords"] == '["W-2"]' == store._to_sql(item.required_keywords)
    assert stored["date_pattern_derived"] == int(item.date_pattern_derived)


def test_the_documents_table_holds_every_column_the_index_row_has(conn, root, engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    file_drops(engagement, today=DAY1)
    build(conn, root, engagement)

    entry = read_index(engagement / INDEX_FILENAME)[0]
    row = conn.execute("SELECT * FROM documents").fetchone()
    for field, value in entry_to_json(entry).items():
        assert row[field] == store._to_sql(value), field
