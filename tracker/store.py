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

**Rebuild is recovery.** :func:`rebuild_engagement` deletes one
engagement's rows and builds them again from seq 1 - the journal
replayed, and nothing else. That single function is the answer to two
questions: how a store deleted by accident comes back, and how a store
somebody doubts is proved. It writes nothing to the journal.

**The check is the gate.** :func:`check` compares these tables with
:func:`tracker.ledger.replay` over the journal and names every place they
disagree, in sentences. Each stage was built on a store that had been
silent there across the whole suite - which is what the agreement fixture
in ``tests/conftest.py`` does after every test: rebuild, check, and fail
on a sentence.

**The index is here** (decision 102, stage 2). The filer's ``read_index()``
answers from the ``documents`` table, and every writer calls
:func:`record` - one call per decision, so one transaction.

**And so are the statuses and the person's rules** (decisions 103 and
104). ``statuses`` is what the scans recorded, ``learned_keywords`` what
people's filings taught, and ``requests`` is the fold of every
``rules_changed`` event (and of the ``rules_imported`` lines older
journals carry, which fold the same way and are never written again):
the app's editor is where a rule is typed, and
the manifest's ``save_rules()`` journals what moved. So every table here
is a derivation of the journal beside the engagement, and nothing is
passed in from anywhere else - no workbook reading, no first reading, no
digest of a file. An engagement whose journal carries no rules event has
no rules, on either side of the check.

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
load time. Everything it holds comes out of the journal, so the store
never depends on the modules that walk folders and move files;
:func:`connect` reads :mod:`tracker.settings` at call time and the
command line at the bottom imports the registry at call time to find the
folders, which is where an edge is allowed to point the other way.
``RequestItem`` is the manifest's own schema and deliberately stays there
(:mod:`tracker.records` says why), so the rule columns are the one field
list written out here - ``tests/test_store.py`` holds that list to the
record's fields, so the table cannot drift away from the list in silence.
Every other column list is derived from the frozen record it stores.
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
    RULE_FIELDS,
    RULE_FLAG_FIELDS,
    RULE_LIST_FIELDS,
    UNKNOWN,
    EngagementInfo,
    IndexEntry,
    StatusUpdate,
    identifier_key,
    info_from_json,
    status_from_json,
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
#: Version 2 (decision 104) dropped the workbook digest from ``engagements``;
#: a version-1 file is deleted and rebuilt, which costs nothing because the
#: store is a derivation of the journals.
SCHEMA_VERSION = 2

#: How long a writer waits for another connection's lock before giving up.
#: There is one writer per clients root by design, so this is slack for the
#: app and a pass overlapping by a moment, not a queue.
BUSY_TIMEOUT_MS = 5000


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
#: The engagement's details', likewise.
ENGAGEMENT_COLUMNS = _column_types(EngagementInfo)
#: One identifier's scanner columns, likewise.
STATUS_COLUMNS = _column_types(StatusUpdate)

#: What each of the person's own rule fields is stored as. The *names* are
#: ``records.RULE_FIELDS``' - the record owns which fields a rule has, now
#: that a rule row travels in the journal - and the affinities are this
#: module's, because only the store has columns. A field added there with
#: no affinity here fails loudly at import rather than landing as text.
_RULE_AFFINITIES: dict[str, str] = {
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
RULE_COLUMNS: dict[str, str] = {name: _RULE_AFFINITIES[name] for name in RULE_FIELDS}


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
    in, at load time, the chain that walks folders and moves files.
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


def _recorded_root_over(folder: Path) -> Path | None:
    """The clients root the settings file names, when ``folder`` is under it.

    :mod:`tracker.settings` is imported at call time for the same reason
    :func:`store_path` does it: this module must not pull in, at load time,
    the chain that walks folders and moves files.
    """
    from tracker.settings import clients_root

    root = clients_root()
    if root is None:
        return None
    try:
        folder.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return root


def key_root(engagement_dir: Path | str, root: Path | str | None = None) -> Path:
    """The clients root this engagement's rows are keyed under.

    An engagement is named in the ``engagements`` table by its path
    *relative to the clients root*, so that a database copied to another
    machine or another drive letter still names the same folders. Almost
    nothing in the package carries that root around - a pass is handed an
    engagement, not a registry - so it is worked out here, once, and the
    same way for every caller, because two spellings of one folder must
    never be two rows:

    - **the root the settings file names, when this folder is under it**
      (decision 106) - the record's own root, and it wins over the root a
      caller has in hand. The runner is handed a root on its command line
      and ``check`` on its own, and either may be a wider folder, or a
      narrower one somebody ran a single client's folder through; the key
      is the same whichever was typed;
    - else the ``root`` the caller was given, when it has one;
    - else the folder's own parent (a test's temporary tree, a folder
      somebody named by hand, a machine with no settings file). Keying by
      the parent is keying by name, and decision 104 records what that
      means on such a machine: two folders of one name under different
      parents are one row. The runner and the app never work that way,
      because they always have a root.
    """
    folder = Path(engagement_dir)
    recorded = _recorded_root_over(folder)
    if recorded is not None:
        return recorded
    if root is not None:
        return Path(root)
    return folder.parent


def root_for(engagement_dir: Path | str) -> Path:
    """The clients root a caller with no root in hand keys this folder
    under: :func:`key_root` with nothing else known. The name the readers
    have always called it by."""
    return key_root(engagement_dir)


def engagement_path(root: Path | str, engagement_dir: Path | str) -> str:
    """The engagement folder as the store keys it: relative to the clients
    root, with forward slashes, so a store copied to another machine or
    another drive letter still names the same engagements."""
    root, folder = Path(root).resolve(), Path(engagement_dir).resolve()
    try:
        return folder.relative_to(root).as_posix()
    except ValueError:
        raise StoreError(f"{folder} is not under the clients root {root}") from None


def _engagement_row(conn: sqlite3.Connection, engagement_dir: Path | str,
                    root: Path | str | None = None) -> sqlite3.Row | None:
    """The stored engagement a folder on disk is, or None.

    **One rule for every caller.** The stored key is relative to a
    clients root, and not every caller has the same root in hand: the
    runner has the one it was run against, the command line the one it
    was given, and a reader deep in the package only the folder. So every
    caller is answered by the exact key under :func:`key_root` first.

    **Under the recorded root, the exact key is the only answer**
    (decision 106). A folder under the clients root the settings file
    names is exactly one stored path, and a folder there with no row is
    an engagement the store has not met - never another engagement whose
    key its path happens to end with. The pre-integration audit of
    2026-09-19 found ``Clients/Archive/Smith 2025``, never seen, answered
    as ``Clients/Smith 2025``'s row: its reads refused the journal as
    truncated, and a longer journal would have been applied onto the
    other engagement. The store cannot tell "one folder named by a wider
    root" from "a different folder nested under the root" by the paths
    alone, so under the recorded root it does not try.

    Where no recorded root covers the folder, everyone is answered by the
    tail: the one stored path the folder ends with, on a folder boundary.
    The longest match wins, which is the only one that can be right - two
    different stored paths cannot both be the tail of one folder unless
    one is the tail of the other, and the longer is then the engagement
    and the shorter is its parent. Why the tail stays: an end-to-end run
    after decision 103 found the pass keying one engagement by the root it
    was run against while ``check`` looked it up by the root on its
    command line, and the two disagreed on a machine with no settings
    file. Two spellings of one folder must never be two rows.
    """
    folder = Path(engagement_dir)
    exact = conn.execute("SELECT * FROM engagements WHERE path = ?",
                         (engagement_path(key_root(folder, root), folder),)).fetchone()
    if exact is not None or _recorded_root_over(folder) is not None:
        return exact
    resolved = folder.resolve().as_posix()
    matches = [row for row in conn.execute("SELECT * FROM engagements")
               if resolved == row["path"] or resolved.endswith("/" + row["path"])]
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


def _rule_from_sql(stored: sqlite3.Row) -> dict:
    """One stored rule row in the shape a ``rules_changed`` event carries it.

    The inverse of :func:`_to_sql` for the rule columns, and only for
    those: SQLite cannot tell a JSON array in a text column from a string,
    nor a yes/no from a number, so the columns that hold one are named
    once, by the record that owns them (``records.RULE_LIST_FIELDS``,
    ``records.RULE_FLAG_FIELDS``). Everything else comes back as the
    column's own affinity gave it, and ``records.rule_from_json`` turns the
    whole into the arguments the manifest's record takes. The row is the
    shape the API hands the editor, so a flag is a boolean and not a 1.
    """
    row: dict[str, object] = {}
    for name in RULE_COLUMNS:
        value = stored[name]
        if name in RULE_LIST_FIELDS:
            row[name] = json.loads(value or "[]")
        elif name in RULE_FLAG_FIELDS:
            row[name] = bool(value)
        else:
            row[name] = value
    return row


#: A cell beginning with one of these is a formula to a spreadsheet opening
#: the CSV, whatever the quoting - so the export prefixes it with an
#: apostrophe, which Excel shows as text and drops.
FORMULA_LEADS = ("=", "+", "-", "@", "\t", "\r")


def _as_text(value: object) -> str:
    """One stored value as a CSV cell: text, always, and an empty one for
    nothing at all. A file name a client chose may begin with anything -
    a name typed like a formula is a name - and quoting does not protect
    it: a spreadsheet evaluates a cell that begins like a formula on the
    way in. So a cell that begins with one of ``FORMULA_LEADS`` is written
    behind an apostrophe, the mark a spreadsheet reads as "text follows"
    and shows without; the name is one character away and never runs."""
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(FORMULA_LEADS) else text


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


def rules(conn: sqlite3.Connection, engagement_dir: Path | str) -> list[dict] | None:
    """One engagement's request rules, in the list's own order, or ``None``.

    The read the manifest's ``load_manifest()`` answers from, and what the
    app's editor shows. Each row is the dict ``records.rule_to_json``
    writes, which is what a ``rules_changed`` event carries and what
    ``rule_from_json`` reads back, so the row the edit recorded and the
    row a reader gets are one shape. Ordered by ``row``, the position the
    person gave each: the list a person sees in the app is the list they
    made.

    ``[]`` for an engagement the store holds and no rule has reached, and
    ``None`` only for one it does not hold at all.
    """
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        return None
    return [
        _rule_from_sql(one)
        for one in conn.execute(
            'SELECT * FROM requests WHERE engagement_id = ? ORDER BY "row", "identifier"',
            (row["id"],),
        )
    ]


def statuses(conn: sqlite3.Connection, engagement_dir: Path | str) -> dict[str, StatusUpdate]:
    """Every identifier's status, by the identifier folded without case.

    Empty for an engagement nothing has scanned, which is what an
    unscanned engagement is. The rows come back as the record's own
    :class:`tracker.records.StatusUpdate`, through the one deserialiser, so
    a blank File Count means the same number here as it did in the event.
    """
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        return {}
    return {
        stored["identifier"]: status_from_json(
            {name: stored[name] for name in STATUS_COLUMNS})
        for stored in conn.execute(
            "SELECT * FROM statuses WHERE engagement_id = ?", (row["id"],))
    }


def learned_keywords(
    conn: sqlite3.Connection, engagement_dir: Path | str
) -> dict[str, tuple[str, ...]]:
    """The keywords people's filings taught each request, oldest first.

    Keyed by the identifier folded without case, as the statuses are.
    ``load_manifest`` adds them to the row's Any Keywords, so a keyword
    somebody typed in the app works on the next pass without anybody
    editing the list; the editor shows them beside the row as taught, and
    never as typed.
    """
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        return {}
    out: dict[str, tuple[str, ...]] = {}
    for stored in conn.execute(
        "SELECT identifier, keyword FROM learned_keywords WHERE engagement_id = ? ORDER BY seq, keyword",
        (row["id"],),
    ):
        out[stored["identifier"]] = out.get(stored["identifier"], ()) + (stored["keyword"],)
    return out


def engagement_info(conn: sqlite3.Connection, engagement_dir: Path | str) -> EngagementInfo | None:
    """The engagement's details as the store holds them, or ``None`` for an
    engagement it does not hold.

    What ``load_engagement_info()`` answers from, and what a save diffs
    the editor's details against.
    """
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        return None
    return info_from_json({name: row[name] for name in ENGAGEMENT_COLUMNS})


def has_rules_event(conn: sqlite3.Connection, engagement_dir: Path | str) -> bool:
    """Whether this engagement's journal has ever carried a rules event -
    a ``rules_changed``, or the ``rules_imported`` an older journal holds.

    Asked of the ``events`` table rather than of the journal file, because
    folding a season of lines to learn it is the cost the store exists to
    remove. It is the same answer: the store is synced to the journal
    before this is asked.

    What it decides is what a save is a difference *from*: every field of
    the details where the record has never carried any, and what the store
    holds where it has.
    """
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        return False
    return conn.execute(
        'SELECT 1 FROM events WHERE engagement_id = ? AND "event" IN (?, ?) LIMIT 1',
        (row["id"], ledger.RULES_CHANGED, ledger.RULES_IMPORTED),
    ).fetchone() is not None


def forget(conn: sqlite3.Connection, engagement_dir: Path | str) -> bool:
    """Delete one engagement's rows, and every row that hangs off them.

    What a failed create leaves behind: nothing. The API makes the folder,
    records the list, scaffolds, and on any failure removes the folder -
    and this removes the store's row for it, so the next create of the
    same name meets no ghost. Writes nothing to any journal. True when a
    row was there to delete.
    """
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        return False
    with _transaction(conn):
        conn.execute("DELETE FROM engagements WHERE id = ?", (row["id"],))
    return True


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
             position, seqs[key])
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


def _write_rule(conn: sqlite3.Connection, engagement_id: int, row: dict) -> None:
    """One rule row, as ``records.rule_to_json`` shapes it, into ``requests``."""
    columns = f"engagement_id, {_names(RULE_COLUMNS)}"
    conn.execute(
        f"INSERT OR REPLACE INTO requests ({columns}) VALUES ({_marks(len(RULE_COLUMNS) + 1)})",
        (engagement_id, *[_to_sql(row.get(name)) for name in RULE_COLUMNS]),
    )


def _write_engagement_info(conn: sqlite3.Connection, engagement_id: int, info: dict) -> None:
    """The engagement's details, as ``records.info_to_json`` shapes them.

    Only the fields the caller carries: a ``rules_changed`` event names
    what changed, and a field nothing has ever spoken for keeps whatever
    the row was built with.
    """
    named = [name for name in ENGAGEMENT_COLUMNS if name in info]
    if not named:
        return
    assignments = ", ".join(f'"{name}" = ?' for name in named)
    conn.execute(
        f"UPDATE engagements SET {assignments} WHERE id = ?",
        (*[_to_sql(info[name]) for name in named], engagement_id),
    )


MALFORMED_LINE = "{where}: line {seq} ({event}) {problem}; the journal is not applied past it"


def _refuse_a_malformed_line(event: dict, seq: int, where: str) -> None:
    """A line that parses as JSON and names an event but carries the wrong
    shape is refused by name, before a value of it reaches a table.

    The engagement folder is synced, so a line another machine wrote is
    not trusted to be well formed: a ``rules_changed`` whose ``rules`` holds
    a string, a ``scanned`` whose statuses are a list. Left to the writers
    below, such a line surfaces as an AttributeError inside discovery and
    ends the whole practice's pass before one document is filed. Refused
    here it is one folder's problem, said in a sentence that names the
    line, and the pass goes on to the next engagement.
    """
    name = event.get(ledger.EVENT_KEY)

    def refuse(problem: str) -> None:
        raise StoreError(MALFORMED_LINE.format(where=where, seq=seq, event=name, problem=problem))

    if name in (ledger.RULES_CHANGED, ledger.RULES_IMPORTED):
        rows = event.get(ledger.RULES_KEY)
        if rows is not None and not isinstance(rows, list):
            refuse(f"carries {ledger.RULES_KEY!r} that is not a list")
        for row in rows or []:
            if not isinstance(row, dict):
                refuse(f"carries a rule that is not a row: {row!r:.60}")
        removed = event.get(ledger.REMOVED_KEY)
        if removed is not None and not isinstance(removed, list):
            refuse(f"carries {ledger.REMOVED_KEY!r} that is not a list")
        for identifier in removed or []:
            if not isinstance(identifier, str):
                refuse(f"names a removed identifier that is not text: {identifier!r:.60}")
        info = event.get(ledger.INFO_KEY)
        if info is not None and not isinstance(info, dict):
            refuse(f"carries {ledger.INFO_KEY!r} that is not a mapping")
    elif name == ledger.SCANNED:
        statuses = event.get(ledger.STATUSES_KEY)
        if statuses is not None and not isinstance(statuses, dict):
            refuse(f"carries {ledger.STATUSES_KEY!r} that is not a mapping")
        for identifier, stored in (statuses or {}).items():
            if not isinstance(stored, dict):
                refuse(f"carries a status for {identifier!r:.40} that is not a mapping")


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
    An edit of the person's rules is written as it is met too: the rows it
    carries replace those identifiers, the ones it names as removed go,
    and the engagement's own columns follow, so a save costs one upsert per
    changed row rather than a rewrite of the list.
    """
    state = ledger.Folded(rows=_stored_rows(conn, engagement_id), statuses={})
    seqs = _stored_seqs(conn, engagement_id)
    status_seqs: dict[str, int] = {}
    where = conn.execute("SELECT path FROM engagements WHERE id = ?", (engagement_id,)).fetchone()[0]
    seq = start - 1
    for event in events:
        seq += 1
        _refuse_a_malformed_line(event, seq, where)
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
        elif name in (ledger.RULES_CHANGED, ledger.RULES_IMPORTED):
            _apply_rules_event(conn, engagement_id, event)
        ledger.apply(state, event)
    if any(event.get(ledger.EVENT_KEY) in ledger.ROW_EVENTS for event in events):
        _write_documents(conn, engagement_id, state.rows, seqs)
    for identifier, stored in state.statuses.items():
        _write_status(conn, engagement_id, identifier, stored, status_seqs[identifier_key(identifier)])
    return seq


def _apply_rules_event(conn: sqlite3.Connection, engagement_id: int, event: dict) -> None:
    """One edit of the person's rules, written into the tables: the
    identifiers it names as removed are deleted first, then the rows the
    event carries are upserted, and the Engagement fields it carries are
    set. Removals first for the same reason :func:`tracker.ledger.apply`
    folds them first: an edit that respells an identifier by case names
    the old spelling as removed and carries the new. The delete is by the
    identifier's exact spelling - the one keying rule the diff, the
    journal's fold and this fold share; SQLite's ``lower()`` folds ASCII
    only, so a delete by the folded key would leave a non-ASCII
    identifier the journal had dropped. The same for a ``rules_changed`` line and for the
    retired ``rules_imported`` an older journal carries; a digest on the
    latter is not read.
    """
    for identifier in event.get(ledger.REMOVED_KEY) or []:
        conn.execute('DELETE FROM requests WHERE engagement_id = ? AND "identifier" = ?',
                     (engagement_id, str(identifier)))
    for row in event.get(ledger.RULES_KEY) or []:
        _write_rule(conn, engagement_id, row)
    _write_engagement_info(conn, engagement_id, dict(event.get(ledger.INFO_KEY) or {}))


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
        if name in ledger.RETIRED_EVENTS:
            raise StoreError(ledger.RETIRED_EVENT.format(name=name) + "; nothing was written")
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
    rel = engagement_path(key_root(engagement_dir, root), engagement_dir)
    row = _engagement_row(conn, engagement_dir, root)
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

    **The reader's top-up.** The store is a derivation of the journal, so
    a reader that finds it missing or behind can make it right from the
    journal alone - no lock, nothing written in the engagement folder. The
    filer's ``read_index()`` and the manifest's readers call this before
    every read, which is why no reader in the package has to know whether
    somebody ensured the engagement first. The journal is the whole of it:
    the rows, the statuses, the person's rules and the engagement's
    details all come out of the lines.
    """
    engagement_dir = Path(engagement_dir)
    rel = engagement_path(key_root(engagement_dir, root), engagement_dir)
    row = _engagement_row(conn, engagement_dir, root)
    if row is not None:
        # The journal's digest first, and the lines only if it moved: this
        # runs before every read, and parsing a season of events to learn
        # that nothing has happened is the cost the store exists to remove.
        if row["ledger_head"] == ledger.head(engagement_dir):
            return row["applied_seq"]
        return sync(conn, root, engagement_dir)
    events = ledger.read_events(engagement_dir)
    with _transaction(conn):
        columns = f'"path", {_names(ENGAGEMENT_COLUMNS)}, ledger_head, applied_seq, built_at'
        cursor = conn.execute(
            f"INSERT INTO engagements ({columns}) VALUES ({_marks(len(ENGAGEMENT_COLUMNS) + 4)})",
            (rel, *[_to_sql(getattr(EngagementInfo(), name)) for name in ENGAGEMENT_COLUMNS],
             ledger.head(engagement_dir), len(events), ledger.stamp()),
        )
        if events:
            _apply(conn, cursor.lastrowid, events, start=1)
    return len(events)


# ------------------------------------------------------------- the rebuild ----


def rebuild_engagement(
    conn: sqlite3.Connection,
    root: Path | str,
    engagement_dir: Path | str,
) -> None:
    """Build one engagement's rows again from the record. Idempotent.

    The journal is replayed from its first line, and what it says is what
    the rows are - the index, the statuses, the keywords people taught,
    the person's rules and the engagement's details. The journal is the
    whole of it (decision 104): nothing is passed in from anywhere, and an
    engagement whose journal carries no rules event is rebuilt with none.
    That is what makes the store rebuildable from the journals alone,
    which is the claim ``docs/storage.md`` makes for it.

    **Nothing is written to the journal.** A rebuild is a reading of the
    record, not an event in it, and a rebuild that appended would make the
    record grow every time somebody checked it.
    """
    engagement_dir = Path(engagement_dir)
    rel = engagement_path(key_root(engagement_dir, root), engagement_dir)
    events = ledger.read_events(engagement_dir)
    head = ledger.head(engagement_dir)
    built_at = ledger.stamp()
    with _transaction(conn):
        # The children go with it: every table references the engagement
        # with ON DELETE CASCADE and foreign keys are on, so one delete is
        # the whole of "forget what you knew about this folder".
        known = _engagement_row(conn, engagement_dir, root)
        if known is not None:
            conn.execute("DELETE FROM engagements WHERE id = ?", (known["id"],))
        columns = f'"path", {_names(ENGAGEMENT_COLUMNS)}, ledger_head, applied_seq, built_at'
        cursor = conn.execute(
            f"INSERT INTO engagements ({columns}) VALUES ({_marks(len(ENGAGEMENT_COLUMNS) + 4)})",
            (rel, *[_to_sql(getattr(EngagementInfo(), name)) for name in ENGAGEMENT_COLUMNS],
             head, len(events), built_at),
        )
        if events:
            _apply(conn, cursor.lastrowid, events, start=1)


# --------------------------------------------------------------- the check ----


def check(conn: sqlite3.Connection, root: Path | str, engagement_dir: Path | str) -> list[str]:
    """Every place the store and the journal disagree, as sentences.

    The gate. An empty list is the claim that these tables say exactly
    what the engagement's own record says - the same index rows in the
    same order, field for field; the same status for every identifier; the
    same rule, where the record carries one. Anything else is named in a
    sentence a person can act on: which engagement, which row or
    identifier, which field, what each side says.

    **The other copy is the journal, and it is the only one.** The
    readers answer from these very tables, so asking them would be the
    store compared with itself. This replays the lines and compares the
    fold, which is what a rebuild is made of and what a rebuild must come
    back to - the rules included, always: an engagement with no rules
    event has none on either side.
    """
    name = Path(engagement_dir).name
    rel = engagement_path(key_root(engagement_dir, root), engagement_dir)
    engagement = _engagement_row(conn, engagement_dir, root)
    folded = ledger.replay(ledger.read_events(engagement_dir))
    if engagement is None:
        return [f"{rel}: the store does not hold this engagement, and its record carries "
                f"{len(folded.rows)} index row(s) and {len(folded.rules)} request row(s)"]
    problems = _check_documents(conn, engagement["id"], name, folded.rows)
    problems += _check_statuses(conn, engagement["id"], name, folded.statuses)
    problems += _check_rules(conn, engagement["id"], name, folded)
    return problems


def _check_documents(
    conn: sqlite3.Connection, engagement_id: int, name: str, recorded: dict[str, dict]
) -> list[str]:
    stored = list(conn.execute(
        'SELECT * FROM documents WHERE engagement_id = ? ORDER BY "position"', (engagement_id,)))
    rows = list(recorded.items())
    problems = []
    if len(stored) != len(rows):
        problems.append(
            f"{name}: the store holds {len(stored)} index row(s), the record carries {len(rows)}")
    for position, (key, row) in enumerate(rows[:len(stored)]):
        held = stored[position]
        if held["key"] != key:
            problems.append(
                f"{name}: index row {position + 1}: the store holds {held['key']!r}, "
                f"the record carries {key!r}")
            continue
        for field in DOCUMENT_COLUMNS:
            theirs = _to_sql(row.get(field))
            if held[field] != theirs:
                problems.append(
                    f"{name}: index row {key!r}, {field}: the store says {held[field]!r}, "
                    f"the record says {theirs!r}")
    for held in stored[len(rows):]:
        problems.append(
            f"{name}: index row {held['key']!r} is in the store and not in the record")
    return problems


def _check_statuses(
    conn: sqlite3.Connection, engagement_id: int, name: str, recorded: dict[str, dict]
) -> list[str]:
    stored = {row["identifier"]: row for row in conn.execute(
        "SELECT * FROM statuses WHERE engagement_id = ?", (engagement_id,))}
    problems = []
    seen = set()
    for identifier, status in recorded.items():
        key = identifier_key(identifier)
        seen.add(key)
        held = stored.get(key)
        if held is None:
            problems.append(f"{name}: request {identifier} has a status in the record and none in the store")
            continue
        for field in STATUS_COLUMNS:
            theirs = _to_sql(status.get(field))
            if held[field] != theirs:
                problems.append(
                    f"{name}: request {identifier}, {field}: the store says {held[field]!r}, "
                    f"the record says {theirs!r}")
    for key in sorted(set(stored) - seen):
        problems.append(f"{name}: request {key} has a status in the store and none in the record")
    return problems


def _check_rules(
    conn: sqlite3.Connection, engagement_id: int, name: str, folded: ledger.Folded
) -> list[str]:
    stored = {identifier_key(row["identifier"]): row for row in conn.execute(
        "SELECT * FROM requests WHERE engagement_id = ?", (engagement_id,))}
    problems = []
    if len(stored) != len(folded.rules):
        problems.append(
            f"{name}: the store holds {len(stored)} request row(s), "
            f"the record's edits fold to {len(folded.rules)}")
    seen = set()
    for identifier, rule in folded.rules.items():
        key = identifier_key(identifier)
        seen.add(key)
        held = stored.get(key)
        if held is None:
            problems.append(f"{name}: request {identifier} is in the record and not in the store")
            continue
        for field in RULE_COLUMNS:
            theirs = _to_sql(rule.get(field))
            if held[field] != theirs:
                problems.append(
                    f"{name}: request {identifier}, {field}: the store says {held[field]!r}, "
                    f"the record says {theirs!r}")
    for key in sorted(set(stored) - seen):
        problems.append(
            f"{name}: request {stored[key]['identifier']} is in the store and not in the record")
    row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    for field, value in folded.info.items():
        if field in ENGAGEMENT_COLUMNS and row[field] != _to_sql(value):
            problems.append(
                f"{name}: engagement {field}: the store says {row[field]!r}, "
                f"the record says {_to_sql(value)!r}")
    return problems


def state(
    conn: sqlite3.Connection,
    engagement_dir: Path | str,
    *,
    ledger_head_now: str,
) -> str:
    """Whether the store still describes the engagement: one of the three words.

    The same question the page answers about itself, asked of the rows: the
    store is a derivation of the journal, which moves with every pass and
    every edit, so "there are rows" is not an answer. The journal's head as
    it was when the rows were built and as it is now: the same, and the
    store is current; moved, and it is behind; no rows for this folder at
    all, and it is unknown. One stamp since decision 104 - a rules edit is
    an event, so the head moves with it.
    """
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        return UNKNOWN
    if row["ledger_head"] == ledger_head_now:
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
    read everything as a page, and decision 104 that they edit the one
    list in the app; a pass that wrote spreadsheets nobody asked for would
    be inventing a second thing to keep in step. This is for the moment
    somebody wants the season's filings in a pivot table.

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

    engagement_columns = ["path", *ENGAGEMENT_COLUMNS, "ledger_head", "applied_seq", "built_at"]
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
    # bottom of the package beside the journal and the lock; a command line
    # nobody imports is the one place that may look upwards, and finding
    # the engagement folders under a root is what it looks up for.
    from tracker import registry
    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

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
                    rebuild_engagement(connection, clients_root, engagement)
                    print(f"  built {engagement.name}")
                elif ns.command == "state":
                    print(f"  {state(connection, engagement, ledger_head_now=ledger.head(engagement))}"
                          f"  {engagement.name}")
                else:
                    said = check(connection, clients_root, engagement)
                    failures += len(said)
                    for line in said:
                        print(f"  {line}")
                    if not said:
                        print(f"  agrees  {engagement.name}")
    finally:
        close()
    if failures:
        print(f"\n  the store and the record do not agree ({failures})\n")
    else:
        print()
    raise SystemExit(1 if failures else 0)
