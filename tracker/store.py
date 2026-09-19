"""The store: one database on the machine, rebuilt from the record.

**The words.** *The record* is what the machine keeps about an engagement:
the journal and the store together. *The ledger* is the journal file alone
(:mod:`tracker.ledger`). *The store* is this database alone. They are not
two copies of one fact and they are not rivals - the journal is what is
written, the store is what is queried, and either can be thrown away and
made again from the other in only one direction: **the store is rebuilt
from the journal, never the reverse.**

**Why a database at all.** The journal answers "what happened" perfectly
and answers "what does this engagement owe" by reading every line of it.
Across a hundred engagements in March, every reader - the pass, the app,
the practice page - folds every line of every journal to draw one screen.
That is the cost the store removes, and the only reason it exists.

**Why here and not in the engagement folder.** The engagement folders are
synced between the office machine and the drive by a cloud client, and a
synced SQLite file is a corrupted SQLite file: the client copies a page at
a time, has no idea what a write-ahead log is, and will happily resurrect
an old copy over a live one. That is decision 87's finding and it stands.
So the store is **one file per clients root, on the designated machine's
own local disk, beside the settings file** - never under the clients root,
never in a folder anything syncs. :func:`path_for` is the whole of that
rule. One machine per clients root is already the law (:mod:`tracker.locking`
says why the lock needs it), so one store per clients root takes nothing
away. The owner settled this on 2026-09-19: the journal stays where it is,
in the folder, synced; the store is local and disposable.

**Journal first, then apply.** :func:`record` appends every event to the
journal - under the engagement lock, fsync-ed, one line each - and only
then opens a single immediate transaction that inserts those same events
and folds them into the tables. If the machine dies between the two, the
journal is ahead of the store by some lines and nothing is lost:
:func:`sync` compares the journal's line count with what the store says it
has applied and replays the difference. The reverse order would lose the
event itself, which is the one thing that cannot be recovered. This is
also why the store may run with ``synchronous`` at NORMAL: a write-ahead
log the operating system has not flushed costs at most a replay.

**Rebuild is recovery, and recovery is the migration.**
:func:`rebuild_engagement` deletes one engagement's rows and builds them
again from seq 1 - the journal replayed, then the workbook's own reading
for every index row and every identifier's status the journal does not
carry (decision 88's per-row, per-identifier fallback, applied once at
build time instead of on every read). That single function is the answer
to three different questions: how an engagement that predates the store
gets into it, how a store deleted by accident comes back, and how a store
somebody doubts is proved. It writes nothing to the journal.

**The check is the gate.** :func:`check` asks what else holds the same
facts and names every place the store disagrees, in sentences. Stage 2 was
built on a store that had been silent there across the whole suite - which
is what the agreement fixture in ``tests/conftest.py`` does after every
test: rebuild, check, and fail on a sentence.

**The index is here now** (decision 102, stage 2). The index workbook is
never written again; the filer's ``read_index()`` answers from the
``documents`` table, and every writer that used to rewrite the workbook
calls :func:`record` instead - one call per decision, so one transaction.
An engagement that still has the old workbook beside it is migrated once
by the filer's ``ensure()``: its rows are imported into the journal,
the workbook is renamed aside and a ``migrated`` event says which files
were moved. The manifest's scanner columns are still the workbook's
(decision 103 takes them), so ``requests`` and ``statuses`` are still
rebuilt from the sheet the person edits.

**One store per process.** :func:`connect` hands out one connection to one
file for the life of the process, created on first use and closed by
:func:`close`. One file per clients root is the placement rule and one
connection per process is what makes it cheap: a pass over two hundred
engagements opens the database once, and the app's command opens it once.
Where that file is comes from :func:`path_for` over the settings file,
**unless** the environment variable :data:`ENV_STORE` names an absolute
path. The variable exists because two callers legitimately need a store
that is not the machine's: the suite, which gives every test a database
under its own temporary folder so no test can leak rows into another, and
a person on the command line asking a question of a copy. It is read on
the first :func:`connect` and nowhere else.

**What it imports, and why so little.** ``records``, ``ledger``,
``locking`` and the standard library - nothing else of the package, at
load time. The workbook readings it needs are **passed in** as records by
the caller, so the store never depends on the modules that open workbooks,
walk folders and take locks; :func:`connect` reads
:mod:`tracker.settings` at call time and the command line at the bottom
imports the readers at call time to feed it, which is where an edge is
allowed to point the other way. ``RequestItem`` is the manifest's own
schema and deliberately stays there (:mod:`tracker.records` says why), so
the rule columns are the one field list written out here - and
:func:`_refuse_a_request_schema_that_moved` refuses a rebuild whose rows
carry a different set, so the table cannot drift away from the sheet in
silence. Every other column list is derived from the frozen record it
stores.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import fields
from pathlib import Path

from tracker import ledger
from tracker.locking import lock_is_held
from tracker.records import (
    BEHIND,
    CURRENT,
    UNKNOWN,
    EngagementInfo,
    IndexEntry,
    StatusUpdate,
    entry_to_json,
    identifier_key,
    ledger_key,
    status_to_json,
)

#: The database, on the designated machine's local disk beside the settings
#: file. One per clients root; a person never opens it and never backs it up
#: (the journals are the backup).
STORE_FILENAME = "tracker.db"
#: The two files SQLite keeps beside it while a write-ahead log is live.
#: Named here because ``.gitignore`` has to know all three and a name typed
#: twice is a name that drifts.
STORE_WAL_FILENAME = f"{STORE_FILENAME}-wal"
STORE_SHM_FILENAME = f"{STORE_FILENAME}-shm"

#: An absolute path to a store to use instead of the one beside the settings
#: file. The suite sets it per test; a person may set it to ask a question of
#: a copy. Read by :func:`connect` and nowhere else.
ENV_STORE = "TRACKER_STORE"

#: What this version of the code knows how to read, written into the file as
#: ``user_version``. A file carrying anything else is refused by name rather
#: than opened hopefully: a schema this code does not understand is not a
#: store, and guessing past it would write rows a later version cannot fold.
SCHEMA_VERSION = 1

#: How long a writer waits for another connection's lock before giving up.
#: There is one writer per clients root by design, so this is slack for the
#: app and a pass overlapping by a moment, not a queue.
BUSY_TIMEOUT_MS = 5000

#: The workbook's own reading, taken where the journal has never spoken for
#: a row or an identifier, is recorded at this sequence number: before every
#: event there is. It is what "the record does not carry this; the workbook
#: does" looks like in a column, and it is how a rebuilt row says which of
#: the two readings it came from.
WORKBOOK_SEQ = 0


class StoreError(RuntimeError):
    """The store could not be opened, written to, or read as one."""


# --------------------------------------------------------------- columns ----

#: Python annotation -> SQLite affinity. Spelled out rather than guessed so
#: a field added to a record with a type this cannot store fails loudly at
#: import instead of silently landing as text (a size stored under TEXT
#: affinity comes back as a string and no comparison of it ever matches).
_AFFINITY: dict[str, str] = {
    "str": "TEXT",
    "int": "INTEGER",
    "float": "REAL",
    "bool": "INTEGER",
    "int | None": "INTEGER",
    "dt.date | None": "TEXT",
}


def _column_types(record: type) -> dict[str, str]:
    """One frozen record's fields as columns: name -> affinity, in field order."""
    out: dict[str, str] = {}
    for one in fields(record):
        affinity = _AFFINITY.get(str(one.type))
        if affinity is None:
            raise StoreError(
                f"{record.__name__}.{one.name} is typed {one.type!r}, which the store has no "
                f"column for; teach it one before storing that record"
            )
        out[one.name] = affinity
    return out


#: The index row's own columns, straight off the record that defines it, so
#: a column added to the row is a column here without another edit.
DOCUMENT_COLUMNS = _column_types(IndexEntry)
#: The Engagement sheet's, likewise.
ENGAGEMENT_COLUMNS = _column_types(EngagementInfo)
#: One identifier's scanner columns, likewise.
STATUS_COLUMNS = _column_types(StatusUpdate)

#: The person's half of a request row - everything the manifest's own
#: ``RequestItem`` holds that is not a scanner column. It is the one field
#: list this module writes out, because that record is the schema of a sheet
#: a person edits and stays in the module that parses it; every rebuild
#: checks the rows it is handed against this, so the two cannot part
#: company quietly.
RULE_COLUMNS: dict[str, str] = {
    "identifier": "TEXT",
    "document": "TEXT",
    "period": "TEXT",
    "expected_count": "INTEGER",
    "allowed_extensions": "TEXT",
    "min_size_kb": "INTEGER",
    "required_keywords": "TEXT",
    "any_keywords": "TEXT",
    "date_pattern": "TEXT",
    "date_pattern_derived": "INTEGER",
    "manual_override": "TEXT",
    "row": "INTEGER",
}


def _refuse_a_request_schema_that_moved(item: object) -> None:
    """Refuse a request row whose fields are not the ones the tables hold.

    The manifest owns that record; this module owns the columns. A field
    added to the sheet's record and not here would be dropped on the floor
    by every rebuild, and the check would go on passing because both sides
    of it would be missing the same value.
    """
    carried = {one.name for one in fields(item)}
    expected = set(RULE_COLUMNS) | set(STATUS_COLUMNS)
    if carried != expected:
        raise StoreError(
            f"{type(item).__name__} carries {sorted(carried)}; the store's request tables hold "
            f"{sorted(expected)} - the sheet's record moved and the schema did not"
        )


def _quoted(columns: dict[str, str]) -> str:
    return ", ".join(f'"{name}" {affinity}' for name, affinity in columns.items())


def _names(columns: dict[str, str]) -> str:
    return ", ".join(f'"{name}"' for name in columns)


def _marks(count: int) -> str:
    return ", ".join("?" * count)


SCHEMA: tuple[str, ...] = (
    f"""CREATE TABLE IF NOT EXISTS engagements (
        id INTEGER PRIMARY KEY,
        "path" TEXT UNIQUE NOT NULL,
        {_quoted(ENGAGEMENT_COLUMNS)},
        manifest_digest TEXT NOT NULL DEFAULT '',
        ledger_head TEXT NOT NULL DEFAULT '',
        applied_seq INTEGER NOT NULL DEFAULT 0,
        built_at TEXT NOT NULL
    )""",
    f"""CREATE TABLE IF NOT EXISTS requests (
        engagement_id INTEGER NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
        {_quoted(RULE_COLUMNS)},
        PRIMARY KEY (engagement_id, "identifier")
    )""",
    f"""CREATE TABLE IF NOT EXISTS statuses (
        engagement_id INTEGER NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
        "identifier" TEXT NOT NULL,
        {_quoted(STATUS_COLUMNS)},
        seq INTEGER NOT NULL,
        PRIMARY KEY (engagement_id, "identifier")
    )""",
    """CREATE TABLE IF NOT EXISTS learned_keywords (
        engagement_id INTEGER NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
        "identifier" TEXT NOT NULL,
        keyword TEXT NOT NULL,
        seq INTEGER NOT NULL,
        PRIMARY KEY (engagement_id, "identifier", keyword)
    )""",
    f"""CREATE TABLE IF NOT EXISTS documents (
        engagement_id INTEGER NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
        "key" TEXT NOT NULL,
        {_quoted(DOCUMENT_COLUMNS)},
        "position" INTEGER NOT NULL,
        seq INTEGER NOT NULL,
        PRIMARY KEY (engagement_id, "key")
    )""",
    """CREATE TABLE IF NOT EXISTS events (
        engagement_id INTEGER NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
        seq INTEGER NOT NULL,
        at TEXT,
        "event" TEXT NOT NULL,
        "key" TEXT,
        payload TEXT NOT NULL,
        PRIMARY KEY (engagement_id, seq)
    )""",
    'CREATE INDEX IF NOT EXISTS documents_by_decision ON documents (engagement_id, "decision")',
    'CREATE INDEX IF NOT EXISTS documents_by_digest ON documents ("digest")',
    'CREATE INDEX IF NOT EXISTS statuses_by_status ON statuses ("status")',
)


# ------------------------------------------------------------ open, place ----


def path_for(settings_path: Path | str) -> Path:
    """Where the store lives for the clients root the settings file names.

    **Beside the settings file**, which is beside the app on the machine
    that runs the schedule - not under the clients root, which syncs. The
    settings module is not imported to ask where that is: the caller has
    the path already, and this module stays at the bottom of the package.
    """
    return Path(settings_path).with_name(STORE_FILENAME)


def open(path: Path | str) -> sqlite3.Connection:  # noqa: A001 - the store is opened
    """Open the store at ``path``, creating the schema when it is not there.

    Refuses, by name, a file whose ``user_version`` this code does not
    know: a store written by a later version holds rows this one would
    fold wrongly, and a silent open is how that becomes a wrong answer on
    a client's file. The caller closes the connection.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None: no implicit transactions. Every write in this
    # module says BEGIN IMMEDIATE itself, because the guarantee is the
    # whole batch or none of it and a driver-invented transaction boundary
    # is not a guarantee anybody wrote down.
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        for statement in SCHEMA:
            conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    elif version != SCHEMA_VERSION:
        conn.close()
        raise StoreError(
            f"{path} is a store at user_version {version}; this code knows {SCHEMA_VERSION}. "
            f"It was written by another version - delete it and rebuild, or run that version."
        )
    return conn


#: The one connection this process has, and the file it is to. Module level
#: rather than passed down from an entry point because every writer deep in
#: the package needs it and threading a handle through twelve signatures is
#: how one of them ends up opening a second.
_CONNECTION: sqlite3.Connection | None = None
_CONNECTION_PATH: Path | None = None


def store_path() -> Path:
    """The store this process uses: :data:`ENV_STORE` if it is set, else the
    one beside the settings file.

    :mod:`tracker.settings` is imported here rather than at the top of the
    module: this module sits at the bottom of the package and must not pull
    in, at load time, the chain that opens workbooks.
    """
    override = os.environ.get(ENV_STORE)
    if override:
        return Path(override)
    from tracker.settings import settings_path

    return path_for(settings_path())


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """The process's one connection to the store, opened on first use.

    ``path`` is for a caller that knows which file it means (the command
    line); everything else asks for the machine's. Asking for a *different*
    file while one is open is refused rather than quietly answered from the
    wrong database - :func:`close` first.
    """
    global _CONNECTION, _CONNECTION_PATH
    wanted = Path(path) if path is not None else store_path()
    if _CONNECTION is not None:
        if _CONNECTION_PATH != wanted:
            raise StoreError(
                f"this process already has {_CONNECTION_PATH} open; it cannot also answer "
                f"from {wanted} - close() the first one"
            )
        return _CONNECTION
    _CONNECTION = open(wanted)
    _CONNECTION_PATH = wanted
    return _CONNECTION


def close() -> None:
    """Let go of the process's connection. Safe to call when there is none.

    A database with an open connection cannot be deleted on Windows, which
    is why the suite closes it before the temporary folder goes.
    """
    global _CONNECTION, _CONNECTION_PATH
    if _CONNECTION is not None:
        _CONNECTION.close()
    _CONNECTION, _CONNECTION_PATH = None, None


@contextmanager
def _transaction(conn: sqlite3.Connection):
    """One immediate transaction: everything in it, or none of it.

    IMMEDIATE rather than DEFERRED because every caller here is about to
    write, and a deferred transaction that discovers that on its first
    write can fail to upgrade against a concurrent reader.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def engagement_path(root: Path | str, engagement_dir: Path | str) -> str:
    """The engagement folder as the store keys it: relative to the clients
    root, with forward slashes, so a store copied to another machine or
    another drive letter still names the same engagements."""
    root, folder = Path(root).resolve(), Path(engagement_dir).resolve()
    try:
        return folder.relative_to(root).as_posix()
    except ValueError:
        raise StoreError(f"{folder} is not under the clients root {root}") from None


def _engagement_row(conn: sqlite3.Connection, engagement_dir: Path | str) -> sqlite3.Row | None:
    """The stored engagement a folder on disk is, or None.

    The stored key is relative to the clients root and the caller of
    :func:`record` has only the folder, so the match is on the tail: the
    one stored path the folder ends with, on a folder boundary. The
    longest match wins, which is the only one that can be right - two
    different stored paths cannot both be the tail of one folder unless
    one is the tail of the other, and the longer is then the engagement
    and the shorter is its parent.
    """
    folder = Path(engagement_dir).resolve().as_posix()
    matches = [row for row in conn.execute("SELECT * FROM engagements")
               if folder == row["path"] or folder.endswith("/" + row["path"])]
    return max(matches, key=lambda row: len(row["path"]), default=None)


# ------------------------------------------------------------- values ----


def _to_sql(value: object) -> object:
    """One record's value as the column holds it: dates as ISO text, the
    yes/no cells as 0 and 1, the keyword and extension tuples as JSON text.
    Every shape a record carries has exactly one of these forms, so nothing
    else is guessed at - an unknown type is refused rather than stringified
    into a cell nobody can read back."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        return json.dumps(list(value), ensure_ascii=False)
    raise StoreError(f"the store has no column form for {type(value).__name__} ({value!r})")


def _as_text(value: object) -> str:
    """One stored value as a CSV cell: text, always, and an empty one for
    nothing at all. A file name a client chose may begin with anything -
    the index already has to keep such a name a name and not a formula
    (``as_text`` in the manifest does it for a workbook cell) - so the
    export writes every value as a text field and never as a number, a
    date or a blank that a spreadsheet would re-type on the way in."""
    return "" if value is None else str(value)


# -------------------------------------------------------------- reading ----


def _stored_rows(conn: sqlite3.Connection, engagement_id: int) -> dict[str, dict]:
    """The engagement's index rows in the shape the journal records them:
    keyed by the row's identity, in the index's own order, each one the
    dict a row event carries. That is the shape :func:`tracker.ledger.apply`
    folds, so the store's own rows and the journal's next line meet in one
    place and the fold rule has one owner."""
    return {
        row["key"]: {name: row[name] for name in DOCUMENT_COLUMNS}
        for row in conn.execute(
            'SELECT * FROM documents WHERE engagement_id = ? ORDER BY "position"', (engagement_id,)
        )
    }


def documents(conn: sqlite3.Connection, engagement_dir: Path | str) -> list[dict]:
    """One engagement's index rows, in the index's own order.

    The read the filer's ``read_index()`` answers from. Each row is the
    dict an index-shaped event carries, which is what
    :func:`tracker.records.entry_from_json` reads back, so the row the
    writer recorded and the row a reader gets are one shape.

    An engagement the store has never seen has no rows and says so with an
    empty list rather than an error: it is a folder nothing has been
    recorded for yet, which is what a brand new engagement is.
    """
    row = _engagement_row(conn, engagement_dir)
    return [] if row is None else list(_stored_rows(conn, row["id"]).values())


def _stored_seqs(conn: sqlite3.Connection, engagement_id: int) -> dict[str, int]:
    return {row["key"]: row["seq"] for row in conn.execute(
        "SELECT key, seq FROM documents WHERE engagement_id = ?", (engagement_id,))}


# -------------------------------------------------------------- writing ----


def _write_documents(
    conn: sqlite3.Connection, engagement_id: int, rows: dict[str, dict], seqs: dict[str, int]
) -> None:
    """Replace the engagement's index rows with the fold, in the fold's order.

    Written whole rather than row by row because the order is part of the
    answer: a row that changed identity keeps the place the one it left
    held, and the place is the fold's, not this table's. Re-laying the
    positions from 0 each time is what keeps them the index's own.
    """
    conn.execute("DELETE FROM documents WHERE engagement_id = ?", (engagement_id,))
    columns = f'engagement_id, "key", {_names(DOCUMENT_COLUMNS)}, "position", seq'
    conn.executemany(
        f"INSERT INTO documents ({columns}) VALUES ({_marks(len(DOCUMENT_COLUMNS) + 4)})",
        [
            (engagement_id, key, *[_to_sql(row.get(name)) for name in DOCUMENT_COLUMNS],
             position, seqs.get(key, WORKBOOK_SEQ))
            for position, (key, row) in enumerate(rows.items())
        ],
    )


def _write_status(
    conn: sqlite3.Connection, engagement_id: int, identifier: str, stored: dict, seq: int
) -> None:
    columns = f'engagement_id, "identifier", {_names(STATUS_COLUMNS)}, seq'
    conn.execute(
        f"INSERT OR REPLACE INTO statuses ({columns}) VALUES ({_marks(len(STATUS_COLUMNS) + 3)})",
        (engagement_id, identifier_key(identifier),
         *[_to_sql(stored.get(name)) for name in STATUS_COLUMNS], seq),
    )


def _write_request(conn: sqlite3.Connection, engagement_id: int, item: object) -> None:
    columns = f"engagement_id, {_names(RULE_COLUMNS)}"
    conn.execute(
        f"INSERT OR REPLACE INTO requests ({columns}) VALUES ({_marks(len(RULE_COLUMNS) + 1)})",
        (engagement_id, *[_to_sql(getattr(item, name)) for name in RULE_COLUMNS]),
    )


def _apply(conn: sqlite3.Connection, engagement_id: int, events: list[dict], *, start: int) -> int:
    """Fold ``events`` into the engagement's tables. Returns the last seq used.

    The caller holds the transaction. The fold itself is
    :func:`tracker.ledger.apply` - the store loads what it holds into the
    shape that function folds, hands it one event at a time, and writes the
    result back - so an index replayed a line at a time here and one folded
    from the first line by a reader cannot come out different. The statuses
    are folded from an empty start, which gives exactly what these events
    changed, and that is upserted onto what the table already said, because
    the status fold is that update and nothing else.

    A keyword a person's filing taught is the one thing here the journal has
    no fold for - it only ever accumulates - so it is inserted as it is met.
    """
    state = ledger.Folded(rows=_stored_rows(conn, engagement_id), statuses={})
    seqs = _stored_seqs(conn, engagement_id)
    status_seqs: dict[str, int] = {}
    seq = start - 1
    for event in events:
        seq += 1
        name = event.get(ledger.EVENT_KEY)
        conn.execute(
            'INSERT OR REPLACE INTO events (engagement_id, seq, at, "event", "key", payload) '
            "VALUES (?, ?, ?, ?, ?, ?)",
            (engagement_id, seq, event.get(ledger.AT_KEY), name, event.get(ledger.KEY_KEY),
             json.dumps(event, ensure_ascii=False, sort_keys=True)),
        )
        if name in ledger.ROW_EVENTS:
            was = event.get(ledger.WAS_KEY)
            if was:
                seqs.pop(was, None)
            seqs[event.get(ledger.KEY_KEY)] = seq
        elif name == ledger.SCANNED:
            for identifier in (event.get(ledger.STATUSES_KEY) or {}):
                status_seqs[identifier_key(identifier)] = seq
        elif name == ledger.KEYWORD_LEARNED:
            conn.execute(
                'INSERT OR REPLACE INTO learned_keywords (engagement_id, "identifier", keyword, seq) '
                "VALUES (?, ?, ?, ?)",
                (engagement_id, identifier_key(str(event.get(ledger.IDENTIFIER_KEY, ""))),
                 str(event.get(ledger.KEYWORD_KEY, "")), seq),
            )
        ledger.apply(state, event)
    if any(event.get(ledger.EVENT_KEY) in ledger.ROW_EVENTS for event in events):
        _write_documents(conn, engagement_id, state.rows, seqs)
    for identifier, stored in state.statuses.items():
        _write_status(conn, engagement_id, identifier, stored, status_seqs[identifier_key(identifier)])
    return seq


# --------------------------------------------------------------- the write ----


def record(conn: sqlite3.Connection, engagement_dir: Path | str, *events: dict) -> int:
    """Append ``events`` to the journal, then apply them. Returns the new applied seq.

    **The journal first, always.** Each event is appended by
    :func:`tracker.ledger.append` - one fsync-ed line, under the engagement
    lock - and only then does one immediate transaction insert them all and
    fold them into the tables. A crash between the two leaves the journal
    ahead by some lines, which :func:`sync` replays; a crash the other way
    round would lose the event, which nothing can replay.

    Refuses outside the engagement lock, and writes nothing to either side
    when it does: the journal already refuses, and saying so here means a
    caller that had no lock does not discover it half way through a batch.
    Refuses too when the store has not been built for this engagement, or
    when it is behind the journal - a batch numbered from a stale seq would
    collide with lines already there. :func:`rebuild_engagement` and
    :func:`sync` are the two answers to that.
    """
    engagement_dir = Path(engagement_dir)
    for event in events:
        name = event.get(ledger.EVENT_KEY)
        if name not in ledger.EVENTS:
            raise StoreError(f"{name!r} is not an event this version writes; nothing was written")
    if not lock_is_held(engagement_dir):
        raise StoreError(
            f"{engagement_dir.name}: the record is written to only while this run holds the "
            f"engagement lock; {len(events)} event(s) were not written"
        )
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        raise StoreError(
            f"{engagement_dir.name}: the store does not hold this engagement; build it with "
            f"rebuild_engagement() before recording to it"
        )
    already = len(ledger.read_events(engagement_dir))
    if already != row["applied_seq"]:
        raise StoreError(
            f"{engagement_dir.name}: the store has applied {row['applied_seq']} of the journal's "
            f"{already} line(s); sync() it before recording to it"
        )
    if not events:
        return row["applied_seq"]
    for event in events:
        ledger.append(engagement_dir, event)
    with _transaction(conn):
        seq = _apply(conn, row["id"], list(events), start=row["applied_seq"] + 1)
        conn.execute(
            "UPDATE engagements SET applied_seq = ?, ledger_head = ? WHERE id = ?",
            (seq, ledger.head(engagement_dir), row["id"]),
        )
    return seq


def sync(conn: sqlite3.Connection, root: Path | str, engagement_dir: Path | str) -> int:
    """Apply the journal lines the store has not. Returns the new applied seq.

    The repair for the one gap :func:`record` can leave - the journal
    written, the transaction not - and the cheap thing to do before
    trusting the store for an engagement. A torn last line is not a line:
    :func:`tracker.ledger.read_events` ignores bytes a killed run left with
    no newline after them, so the tail is replayed once it is whole.

    A store that has applied *more* than the journal holds is not something
    to patch up: the journal has been truncated or replaced under it, and
    what the store says about the lines that are gone cannot be checked
    against anything. It is refused by name, and a rebuild is the answer.
    """
    engagement_dir = Path(engagement_dir)
    rel = engagement_path(root, engagement_dir)
    row = conn.execute("SELECT * FROM engagements WHERE path = ?", (rel,)).fetchone()
    if row is None:
        raise StoreError(f"{rel}: the store does not hold this engagement; rebuild it")
    events = ledger.read_events(engagement_dir)
    applied = row["applied_seq"]
    if len(events) < applied:
        raise StoreError(
            f"{rel}: the store has applied {applied} line(s) and the journal holds {len(events)}; "
            f"the journal was truncated or replaced - rebuild the engagement"
        )
    if len(events) == applied:
        return applied
    with _transaction(conn):
        seq = _apply(conn, row["id"], events[applied:], start=applied + 1)
        conn.execute(
            "UPDATE engagements SET applied_seq = ?, ledger_head = ? WHERE id = ?",
            (seq, ledger.head(engagement_dir), row["id"]),
        )
    return seq


def follow_the_journal(conn: sqlite3.Connection, root: Path | str, engagement_dir: Path | str) -> int:
    """Bring one engagement's rows up to its journal, building them if there
    are none. Returns the applied seq.

    **The reader's top-up, and it never opens a workbook.** The store is a
    derivation of the journal, so a reader that finds it missing or behind
    can make it right from the journal alone - no manifest, no index, no
    lock, nothing written in the engagement folder.
    the filer's ``read_index()`` calls this before every read, which is
    why no reader in the package has to know whether somebody ensured the
    engagement first.

    The engagement's own details and the person's rules are *not* filled in
    here: they are the workbook's and this must not open one. A row built
    this way carries an empty ``manifest_digest``, which is exactly how
    the filer's ``ensure()`` knows to read the sheet and fill them.
    """
    engagement_dir = Path(engagement_dir)
    rel = engagement_path(root, engagement_dir)
    row = conn.execute("SELECT * FROM engagements WHERE path = ?", (rel,)).fetchone()
    if row is not None:
        # The journal's digest first, and the lines only if it moved: this
        # runs before every read, and parsing a season of events to learn
        # that nothing has happened is the cost the store exists to remove.
        if row["ledger_head"] == ledger.head(engagement_dir):
            return row["applied_seq"]
        return sync(conn, root, engagement_dir)
    events = ledger.read_events(engagement_dir)
    with _transaction(conn):
        columns = f'"path", {_names(ENGAGEMENT_COLUMNS)}, manifest_digest, ledger_head, applied_seq, built_at'
        cursor = conn.execute(
            f"INSERT INTO engagements ({columns}) VALUES ({_marks(len(ENGAGEMENT_COLUMNS) + 5)})",
            (rel, *[_to_sql(getattr(EngagementInfo(), name)) for name in ENGAGEMENT_COLUMNS],
             "", ledger.head(engagement_dir), len(events), ledger.stamp()),
        )
        if events:
            _apply(conn, cursor.lastrowid, events, start=1)
    return len(events)


# ------------------------------------------------------------- the rebuild ----


def rebuild_engagement(
    conn: sqlite3.Connection,
    root: Path | str,
    engagement_dir: Path | str,
    *,
    rules: list,
    info: EngagementInfo,
    manifest_digest: str,
    workbook_statuses: dict[str, StatusUpdate],
    workbook_rows: list[IndexEntry] = (),
) -> None:
    """Build one engagement's rows again from the record. Idempotent.

    The journal is replayed from its first line, and then - for every
    identifier's status the journal does not carry - the workbook reading
    the caller passed in is taken instead, at :data:`WORKBOOK_SEQ`. That is
    decision 88's rule ("the record answers, the workbook falls back, per
    row and per identifier") done once here rather than on every read.

    ``workbook_rows`` is the **migration's** argument and nobody else's
    (decision 102): the index is the record's now, so an ordinary rebuild
    is handed none and takes every row from the journal. The one caller
    with rows the journal has never seen is the filer's migration, which
    reads the old workbook once - and it appends them to the journal
    first, so even there this fallback finds nothing left to do.

    The rules and the Engagement sheet are the person's and are never the
    journal's: they come from the workbook every time, through the values
    passed in. The caller reads them, because this module does not open
    workbooks.

    **Nothing is written to the journal.** A rebuild is a reading of the
    record, not an event in it, and a rebuild that appended would make the
    record grow every time somebody checked it.
    """
    engagement_dir = Path(engagement_dir)
    rel = engagement_path(root, engagement_dir)
    for item in rules:
        _refuse_a_request_schema_that_moved(item)
    events = ledger.read_events(engagement_dir)
    head = ledger.head(engagement_dir)
    built_at = ledger.stamp()
    with _transaction(conn):
        # The children go with it: every table references the engagement
        # with ON DELETE CASCADE and foreign keys are on, so one delete is
        # the whole of "forget what you knew about this folder".
        conn.execute("DELETE FROM engagements WHERE path = ?", (rel,))
        columns = f'"path", {_names(ENGAGEMENT_COLUMNS)}, manifest_digest, ledger_head, applied_seq, built_at'
        cursor = conn.execute(
            f"INSERT INTO engagements ({columns}) VALUES ({_marks(len(ENGAGEMENT_COLUMNS) + 5)})",
            (rel, *[_to_sql(getattr(info, name)) for name in ENGAGEMENT_COLUMNS],
             manifest_digest, head, len(events), built_at),
        )
        engagement_id = cursor.lastrowid
        for item in rules:
            _write_request(conn, engagement_id, item)
        if events:
            _apply(conn, engagement_id, events, start=1)
        _fall_back_to_the_workbook(conn, engagement_id, workbook_rows, workbook_statuses)


def _fall_back_to_the_workbook(
    conn: sqlite3.Connection,
    engagement_id: int,
    workbook_rows: list[IndexEntry],
    workbook_statuses: dict[str, StatusUpdate],
) -> None:
    """Take the workbook's reading for what the journal never recorded.

    Per row and per identifier, exactly as the live readers fall back: a
    folder from before the record, or one row added to the list since, is
    read off the sheet and marked :data:`WORKBOOK_SEQ` so the store can
    always say which of the two readings a value came from. Rows the
    journal does carry are left alone - the journal wins, which is the
    whole point of having one.
    """
    held = {row["key"] for row in conn.execute(
        "SELECT key FROM documents WHERE engagement_id = ?", (engagement_id,))}
    position = conn.execute(
        'SELECT COALESCE(MAX("position"), -1) + 1 FROM documents WHERE engagement_id = ?',
        (engagement_id,)).fetchone()[0]
    columns = f'engagement_id, "key", {_names(DOCUMENT_COLUMNS)}, "position", seq'
    for entry in workbook_rows:
        key = ledger_key(entry)
        if key in held:
            continue
        held.add(key)
        row = entry_to_json(entry)
        conn.execute(
            f"INSERT INTO documents ({columns}) VALUES ({_marks(len(DOCUMENT_COLUMNS) + 4)})",
            (engagement_id, key, *[_to_sql(row.get(name)) for name in DOCUMENT_COLUMNS],
             position, WORKBOOK_SEQ),
        )
        position += 1
    carried = {row["identifier"] for row in conn.execute(
        "SELECT identifier FROM statuses WHERE engagement_id = ?", (engagement_id,))}
    for identifier, update in workbook_statuses.items():
        if identifier_key(identifier) in carried:
            continue
        _write_status(conn, engagement_id, identifier, status_to_json(update), WORKBOOK_SEQ)


def reimport_rules(
    conn: sqlite3.Connection,
    root: Path | str,
    engagement_dir: Path | str,
    *,
    rules: list,
    info: EngagementInfo,
    manifest_digest: str,
    workbook_statuses: dict[str, StatusUpdate],
) -> None:
    """Read the person's sheet into the store again, leaving the record alone.

    The rules and the Engagement sheet are the person's and never the
    journal's, so when the workbook's digest moves the store has to read
    them again - but replaying the whole journal to do it would make every
    pass after every edit cost the engagement's whole history. This
    replaces the ``requests`` rows and the engagement's own columns, and
    takes the workbook's status for an identifier the record has never
    spoken for (:data:`WORKBOOK_SEQ`, the same per-identifier fallback
    :func:`rebuild_engagement` applies). ``documents`` and ``events`` are
    not touched: they are the record's.
    """
    rel = engagement_path(root, engagement_dir)
    row = conn.execute("SELECT * FROM engagements WHERE path = ?", (rel,)).fetchone()
    if row is None:
        raise StoreError(f"{rel}: the store does not hold this engagement; rebuild it")
    for item in rules:
        _refuse_a_request_schema_that_moved(item)
    with _transaction(conn):
        conn.execute("DELETE FROM requests WHERE engagement_id = ?", (row["id"],))
        for item in rules:
            _write_request(conn, row["id"], item)
        assignments = ", ".join(f'"{name}" = ?' for name in ENGAGEMENT_COLUMNS)
        conn.execute(
            f"UPDATE engagements SET {assignments}, manifest_digest = ?, built_at = ? WHERE id = ?",
            (*[_to_sql(getattr(info, name)) for name in ENGAGEMENT_COLUMNS],
             manifest_digest, ledger.stamp(), row["id"]),
        )
        carried = {stored["identifier"] for stored in conn.execute(
            "SELECT identifier FROM statuses WHERE engagement_id = ? AND seq > ?",
            (row["id"], WORKBOOK_SEQ))}
        for identifier, update in workbook_statuses.items():
            if identifier_key(identifier) not in carried:
                _write_status(conn, row["id"], identifier, status_to_json(update), WORKBOOK_SEQ)


# --------------------------------------------------------------- the check ----


def check(
    conn: sqlite3.Connection,
    root: Path | str,
    engagement_dir: Path | str,
    *,
    live_rows: list[IndexEntry],
    live_items: list,
) -> list[str]:
    """Every place the store and the live readers disagree, as sentences.

    The gate. An empty list is the claim that a reader switched over to
    these tables would answer exactly what it answers today - the same
    index rows, in the same order, field for field; the same status and
    the same rule for every identifier; the same counts. Anything else is
    named in a sentence a person can act on: which engagement, which row or
    identifier, which field, what each side says.

    **The two sides have to be different readings, and since decision 102
    each half gets its own.** The index rows are compared with
    :func:`tracker.ledger.replay` over the journal - the only other copy
    there is, now that the workbook is gone and ``read_index()`` answers
    from these very tables. The request rows and their statuses are
    compared with the live manifest readers, which still answer from the
    journal and fall back to the sheet per identifier, while a rebuild is
    fed the sheet's own reading; comparing a rebuild against the readings
    it was built from would be the store compared with itself.
    """
    name = Path(engagement_dir).name
    rel = engagement_path(root, engagement_dir)
    engagement = conn.execute("SELECT * FROM engagements WHERE path = ?", (rel,)).fetchone()
    if engagement is None:
        return [f"{rel}: the store does not hold this engagement, and the readers give "
                f"{len(live_rows)} index row(s) and {len(live_items)} request row(s)"]
    problems = _check_documents(conn, engagement["id"], name, live_rows)
    problems += _check_requests(conn, engagement["id"], name, live_items)
    return problems


def _check_documents(
    conn: sqlite3.Connection, engagement_id: int, name: str, live_rows: list[IndexEntry]
) -> list[str]:
    stored = list(conn.execute(
        'SELECT * FROM documents WHERE engagement_id = ? ORDER BY "position"', (engagement_id,)))
    problems = []
    if len(stored) != len(live_rows):
        problems.append(
            f"{name}: the store holds {len(stored)} index row(s), the reader gives {len(live_rows)}")
    for position, entry in enumerate(live_rows[:len(stored)]):
        row, key = stored[position], ledger_key(entry)
        if row["key"] != key:
            problems.append(
                f"{name}: index row {position + 1}: the store holds {row['key']!r}, "
                f"the reader gives {key!r}")
            continue
        for field in DOCUMENT_COLUMNS:
            theirs = _to_sql(getattr(entry, field))
            if row[field] != theirs:
                problems.append(
                    f"{name}: index row {key!r}, {field}: the store says {row[field]!r}, "
                    f"the reader says {theirs!r}")
    for row in stored[len(live_rows):]:
        problems.append(f"{name}: index row {row['key']!r} is in the store and the reader does not give it")
    return problems


def _check_requests(
    conn: sqlite3.Connection, engagement_id: int, name: str, live_items: list
) -> list[str]:
    rules = {identifier_key(row["identifier"]): row for row in conn.execute(
        "SELECT * FROM requests WHERE engagement_id = ?", (engagement_id,))}
    statuses = {row["identifier"]: row for row in conn.execute(
        "SELECT * FROM statuses WHERE engagement_id = ?", (engagement_id,))}
    problems = []
    if len(rules) != len(live_items):
        problems.append(
            f"{name}: the store holds {len(rules)} request row(s), the reader gives {len(live_items)}")
    seen = set()
    for item in live_items:
        key = identifier_key(item.identifier)
        seen.add(key)
        rule = rules.get(key)
        if rule is None:
            problems.append(f"{name}: request {item.identifier} is not in the store")
            continue
        for field in RULE_COLUMNS:
            theirs = _to_sql(getattr(item, field))
            if rule[field] != theirs:
                problems.append(
                    f"{name}: request {item.identifier}, {field}: the store says {rule[field]!r}, "
                    f"the reader says {theirs!r}")
        status = statuses.get(key)
        if status is None:
            problems.append(f"{name}: request {item.identifier} has no status in the store")
            continue
        # Through the record's own serialisation, not field by field off the
        # sheet's row: a blank File Count cell reaches the reader as nothing
        # and the record as no files, and comparing the two raw would report
        # every unscanned row in the firm as a disagreement.
        reading = status_to_json(StatusUpdate(
            status=item.status, file_count=item.file_count,
            received_date=item.received_date, validation_notes=item.validation_notes))
        for field in STATUS_COLUMNS:
            theirs = _to_sql(reading[field])
            if status[field] != theirs:
                problems.append(
                    f"{name}: request {item.identifier}, {field}: the store says {status[field]!r}, "
                    f"the reader says {theirs!r}")
    for key in sorted(set(rules) - seen):
        problems.append(f"{name}: request {rules[key]['identifier']} is in the store and the reader does not give it")
    return problems


def state(
    conn: sqlite3.Connection,
    engagement_dir: Path | str,
    *,
    rules_digest_now: str,
    ledger_head_now: str,
) -> str:
    """Whether the store still describes the engagement: one of the three words.

    The same question the page answers about itself, asked of the rows: the
    store is a derivation of two things that both move - the workbook a
    person edits and the journal the passes append to - so "there are rows"
    is not an answer. Both stamps as they were when the rows were built and
    as they are now: the same, and the store is current; either moved, and
    it is behind; no rows for this folder at all, and it is unknown.
    """
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        return UNKNOWN
    if row["manifest_digest"] == rules_digest_now and row["ledger_head"] == ledger_head_now:
        return CURRENT
    return BEHIND


# -------------------------------------------------------------- the export ----

#: What :func:`export` writes, in the order it writes them.
DOCUMENTS_CSV = "documents.csv"
REQUESTS_CSV = "requests.csv"
ENGAGEMENTS_CSV = "engagements.csv"


def export(conn: sqlite3.Connection, out_dir: Path | str) -> list[Path]:
    """Write the store out as three spreadsheets. Returns the files written.

    **On demand only, and never by a pass.** Decision 91 settled that staff
    open Excel to edit one workbook and read everything else as a page; a
    pass that wrote spreadsheets nobody asked for would be inventing a
    fourth thing to keep in step. This is for the moment somebody wants the
    season's filings in a pivot table.

    Every cell is written as text, with a byte-order mark so that Excel
    opens the file as UTF-8 without being asked, and LF line endings like
    every other file this repository writes. Nothing is in these files that
    is not already in the index and the request list.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / DOCUMENTS_CSV, out_dir / REQUESTS_CSV, out_dir / ENGAGEMENTS_CSV]
    folders = {row["id"]: row["path"] for row in conn.execute("SELECT id, path FROM engagements")}

    _write_csv(paths[0], ["engagement", "key", *DOCUMENT_COLUMNS, "position", "seq"], (
        [folders[row["engagement_id"]], row["key"],
         *[row[name] for name in DOCUMENT_COLUMNS], row["position"], row["seq"]]
        for row in conn.execute('SELECT * FROM documents ORDER BY engagement_id, "position"')
    ))

    statuses = {(row["engagement_id"], row["identifier"]): row
                for row in conn.execute("SELECT * FROM statuses")}
    _write_csv(paths[1], ["engagement", *RULE_COLUMNS, *STATUS_COLUMNS, "status_seq"], (
        [folders[row["engagement_id"]], *[row[name] for name in RULE_COLUMNS],
         *[(status[name] if status else None) for name in STATUS_COLUMNS],
         (status["seq"] if status else None)]
        for row, status in (
            (row, statuses.get((row["engagement_id"], identifier_key(row["identifier"]))))
            for row in conn.execute('SELECT * FROM requests ORDER BY engagement_id, "row"')
        )
    ))

    engagement_columns = ["path", *ENGAGEMENT_COLUMNS,
                          "manifest_digest", "ledger_head", "applied_seq", "built_at"]
    _write_csv(paths[2], engagement_columns, (
        [row[name] for name in engagement_columns]
        for row in conn.execute('SELECT * FROM engagements ORDER BY "path"')
    ))
    return paths


def _write_csv(path: Path, header: list[str], rows) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow([_as_text(value) for value in row])


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    # Imported here and nowhere else in the file. This module sits at the
    # bottom of the package beside the journal and the lock and imports
    # nothing that opens a workbook; a command line nobody imports is the
    # one place that may look upwards, and feeding the store its workbook
    # readings is exactly what it is for.
    from tracker import registry
    from tracker.filer import rules_digest, workbook_readings
    from tracker.manifest import load_manifest
    from tracker.records import entry_from_json
    from tracker.scaffold import MANIFEST_FILENAME

    def _live_readings(folder: Path) -> dict:
        """The other copies of what the store holds - the check's right side.

        The index rows come from the journal, which is the only other copy
        of them since decision 102; the request rows come from the live
        manifest readers, which still have the sheet behind them.
        """
        return {
            "live_items": load_manifest(folder / MANIFEST_FILENAME),
            "live_rows": [entry_from_json(row)
                          for row in ledger.replay(ledger.read_events(folder)).rows.values()],
        }

    parser = argparse.ArgumentParser(
        prog="python -m tracker.store",
        description="Build, check and export the store: one database on this machine, "
                    "rebuilt from each engagement's own record.",
    )
    parser.add_argument("store", help="the store file, or the settings file it sits beside")
    parser.add_argument("command", choices=("rebuild", "check", "export", "state"))
    parser.add_argument("root", help="the clients root")
    parser.add_argument("--engagement", help="one engagement folder instead of every one")
    parser.add_argument("--out", help="where export writes its files")
    ns = parser.parse_args()

    given = Path(ns.store)
    chosen = given if given.name == STORE_FILENAME else path_for(given)
    clients_root = Path(ns.root)
    folders = ([Path(ns.engagement)] if ns.engagement
               else registry.engagement_dirs(clients_root))

    print(f"\n{chosen}")
    connection = connect(chosen)
    failures = 0
    try:
        if ns.command == "export":
            if not ns.out:
                parser.error("export needs --out")
            for written in export(connection, Path(ns.out)):
                print(f"  wrote {written}")
        else:
            for engagement in folders:
                if ns.command == "rebuild":
                    rebuild_engagement(connection, clients_root, engagement,
                                       **workbook_readings(engagement))
                    print(f"  built {engagement.name}")
                elif ns.command == "state":
                    print(f"  {state(connection, engagement, rules_digest_now=rules_digest(engagement), ledger_head_now=ledger.head(engagement))}"
                          f"  {engagement.name}")
                else:
                    said = check(connection, clients_root, engagement, **_live_readings(engagement))
                    failures += len(said)
                    for line in said:
                        print(f"  {line}")
                    if not said:
                        print(f"  agrees  {engagement.name}")
    finally:
        close()
    if failures:
        print(f"\n  the store and the readers do not agree ({failures})\n")
    else:
        print()
    raise SystemExit(1 if failures else 0)
