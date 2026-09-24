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
people's filings taught and nobody has taken back (decision 113: a
``keyword_unlearned`` deletes the row, and :func:`check` compares the
table with the journal's own fold of the two events), and ``requests`` is
the fold of every
``rules_changed`` event (and of the ``rules_imported`` lines older
journals carry, which fold the same way and are never written again):
the app's editor is where a rule is typed, and
the manifest's ``save_rules()`` journals what moved. So every table here
is a derivation of the journal beside the engagement, and nothing is
passed in from anywhere else - no workbook reading, no first reading, no
digest of a file. An engagement whose journal carries no rules event has
no rules, on either side of the check.

**And the moves begun and not finished** (decision 119). ``intents`` is
the fold of the journal's ``moving`` lines: what a pass or a person was
about to do to the disk, written before the first file operation and
deleted by the row event that completes it. It is a derivation of the
journal like the rest - :func:`rebuild_engagement` gives the same open
set and :func:`check` compares the two folds - and it is what the next
pass finishes a half-made move from.

**And the verdict cache, which is not the record's** (decision 107). The
tier-3 verdict cache - the per-path memo of size, mtime and digest that
spares an unchanged file its hash, and the verdicts keyed by content
digest and rules fingerprint - lived in a JSON file the pass rewrote in
the engagement folder every two hours, which is the synced-database
failure one file over. It is two tables here now, ``verdicts`` and
``file_memos``, and they are the one thing in this file that is **not a
derivation of the journal**: a verdict is a derivation of the bytes in
the folder and the rules in ``requests``, not a fact about the
engagement, so nothing is journalled, :func:`rebuild_engagement` leaves
the two tables empty (the next pass reads each document once - slower,
never wrong), and :func:`check`, :func:`state` and :func:`export` neither
read nor compare them. Their write, :func:`remember_verdicts`, is one
immediate transaction of its own and never :func:`record` - there is no
journal line and no ``seq`` - but it still refuses outside the engagement
lock, because the memo ties a path to bytes and every writer already
holds it. The version each verdict was written under is carried per row
(``tracker.content_check.CACHE_VERSION``), so a matcher change still
invalidates without a store version.

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

from tracker import ledger, records
from tracker.locking import lock_is_held
from tracker.records import (
    BEHIND,
    CURRENT,
    RULE_FIELDS,
    RULE_FLAG_DEFAULTS,
    RULE_FLAG_FIELDS,
    RULE_LIST_FIELDS,
    UNKNOWN,
    EngagementInfo,
    HouseholdInfo,
    IndexEntry,
    StatusUpdate,
    household_from_json,
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
#: Version 3 (decision 107) added the verdict cache's two tables,
#: ``verdicts`` and ``file_memos``; a version-2 file is refused by the same
#: sentence and deleted and rebuilt the same way - the cache it never held
#: is refilled by the next pass, one reading per document.
#: Version 4 (decision 116) added the ``override_reason`` column to
#: ``requests``: a version-3 file has no column for the reason a person
#: gives, so it is refused, deleted and rebuilt from the journals like the
#: others - the reason itself travels in the ``rules_changed`` event.
#: Version 5 (decision 117) added the Filing Deadline to the engagement's
#: details, which is a column of ``engagements``: a version-4 file has no
#: column for it, so it is refused, deleted and rebuilt from the journals
#: like every version before it - the date itself travels in the
#: ``rules_changed`` event, so nothing is lost and only the first pass is
#: slower.
#: Version 6 (decision 119) added the ``intents`` table, the moves begun
#: and not yet finished: ``CREATE TABLE IF NOT EXISTS`` on open would make
#: the table and leave a version-5 file's earlier lines unfolded into it,
#: so the file is refused, deleted and rebuilt from the journals like the
#: others - the intents are ``moving`` lines in them.
#: Version 7 (decision 125) added the household, the tax year and the
#: return name to the engagement's details, which are columns of
#: ``engagements``, and the household record's own columns and ``kind``: a
#: version-6 file has none of them, so it is refused, deleted and rebuilt
#: from the journals like every version before it - the details travel in
#: the ``rules_changed`` and ``household_changed`` lines.
#: Version 8 (decision 128) added the return's people to the engagement's
#: details - one column of ``engagements``, holding the list as JSON text -
#: and the ``named`` mark to ``requests``: a version-7 file has neither, so
#: it is refused, deleted and rebuilt from the journals like every version
#: before it, and both travel in the ``rules_changed`` lines.
#: Version 9 (decision 129) added the household's feed list - the return
#: lines in other households its drop folder also feeds - which is one
#: column of ``engagements`` holding the list as JSON text: a version-8
#: file has no column for it, so it is refused, deleted and rebuilt from
#: the journals like every version before it, and the feeds travel in the
#: ``household_changed`` lines.
#: Version 10 (decision 132) changed no column and changed the fold: a
#: ``released`` line takes a row out of the index, and a version-9 file
#: folded by the old code may hold ``Handed Over`` rows this version never
#: produces - so it is refused, deleted and rebuilt from the journals like
#: every version before it, and the retired ``handed_over_by_person`` lines
#: in them are folded as the releases they meant.
#: Version 11 (decision 134) changed no column and changed the key: a
#: return is keyed by where it sits in the layout when no root is in
#: hand, where it was keyed by its parent - its year folder - so a
#: version-10 file may hold two years of one return as one row. It is
#: refused, deleted and rebuilt from the journals like every version
#: before it, and each return is keyed by household, year and return.
SCHEMA_VERSION = 11

#: What a row of ``engagements`` holds the record of: one return, or one
#: household (decision 125). Both are folders with a journal, keyed by
#: path and folded by the same machinery, and this is what tells a reader
#: which of the two it has. A row is a return until a ``household_changed``
#: line says otherwise.
KIND_RETURN = "return"
KIND_HOUSEHOLD = "household"

#: The verdict cache's two tables (decision 107). Named once, here, because
#: the cache in :mod:`tracker.content_check` and the tests both speak of
#: them, and a table name typed twice is a table name that drifts.
VERDICTS_TABLE = "verdicts"
FILE_MEMOS_TABLE = "file_memos"

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
    # A list of words is one JSON array in one text column, as a rule
    # row's keywords already are: SQLite has no list, and a second table
    # for four names a person typed would be a join to read a card.
    "tuple[str, ...]": "TEXT",
    # The return's people (decision 128), likewise: a list of small
    # objects in one text column, read back by the record's own reader
    # (``records.people_from_json``). A table of its own would be a join
    # to answer one question - whose page is this - that is asked once per
    # drop while the lock is already held, and nothing else joins on a
    # person.
    "tuple[Person, ...]": "TEXT",
    # The household's feed list (decision 129), for the same reason: a
    # list of two-field objects in one text column, read back by the
    # record's own reader (``records.feeds_from_json``). A table of its
    # own would be a join to answer a question the pass asks once, while
    # it already holds the household's lock.
    "tuple[Feed, ...]": "TEXT",
}
#: The record fields held as a JSON array in a text column, by name. Named
#: because SQLite cannot tell one from a string on the way back, exactly as
#: ``records.RULE_LIST_FIELDS`` says it for a rule row.
_LIST_COLUMNS: frozenset[str] = frozenset({"members", "feeds"})


def _column_types(record: type, *, prefix: str = "") -> dict[str, str]:
    """One frozen record's fields as columns: name -> affinity, in field order.

    ``prefix`` is for a record that shares a table with another: the
    household's details sit in ``engagements`` beside a return's, and a
    ``name`` column belongs to neither on its own.
    """
    out: dict[str, str] = {}
    for one in fields(record):
        affinity = _AFFINITY.get(str(one.type))
        if affinity is None:
            raise StoreError(
                f"{record.__name__}.{one.name} is typed {one.type!r}, which the store has no "
                f"column for; teach it one before storing that record"
            )
        out[f"{prefix}{one.name}"] = affinity
    return out


#: The index row's own columns, straight off the record that defines it, so
#: a column added to the row is a column here without another edit.
DOCUMENT_COLUMNS = _column_types(IndexEntry)
#: The engagement's details', likewise.
ENGAGEMENT_COLUMNS = _column_types(EngagementInfo)
#: The household's details, in the same table under their own prefix
#: (decision 125): a household folder and a return folder are both rows of
#: ``engagements``, keyed by path, and ``kind`` says which.
HOUSEHOLD_PREFIX = "household_"
HOUSEHOLD_COLUMNS = _column_types(HouseholdInfo, prefix=HOUSEHOLD_PREFIX)
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
    "override_reason": "TEXT",
    "named": "INTEGER",
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
        {_quoted(HOUSEHOLD_COLUMNS)},
        kind TEXT NOT NULL DEFAULT '{KIND_RETURN}',
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
    # The moves begun and not finished (decision 119). One row per index
    # row's identity, holding the ``moving`` line whole: the operations, the
    # row the decision will record and the event that completes it. The row
    # event that names the key deletes it, so this table is empty after
    # every pass that was not interrupted.
    """CREATE TABLE IF NOT EXISTS intents (
        engagement_id INTEGER NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
        "key" TEXT NOT NULL,
        seq INTEGER NOT NULL,
        payload TEXT NOT NULL,
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
    # The verdict cache (decision 107). Per engagement, not per root, so the
    # cascade, the prune and "the same bytes in two engagements" all keep the
    # semantics the per-engagement file had. The store knows nothing of the
    # verdict's record: ``verdict`` is JSON text the cache hands in and reads
    # back, and ``version`` is the cache's own layout version, per row.
    f"""CREATE TABLE IF NOT EXISTS {VERDICTS_TABLE} (
        engagement_id INTEGER NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
        digest TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        version INTEGER NOT NULL,
        verdict TEXT NOT NULL,
        PRIMARY KEY (engagement_id, digest, fingerprint)
    )""",
    f"""CREATE TABLE IF NOT EXISTS {FILE_MEMOS_TABLE} (
        engagement_id INTEGER NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
        path_key TEXT NOT NULL,
        size INTEGER NOT NULL,
        mtime_ns INTEGER NOT NULL,
        digest TEXT NOT NULL,
        PRIMARY KEY (engagement_id, path_key)
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
    - else **the root the folder's position names** (decision 134), when it
      sits in the layout of decision 125 - a year folder above it and the
      private tree above its household (:func:`_positional_root`). Every
      reader reaches this step, because none of them is handed the
      runner's root; and since decision 125 a return's parent is its year
      and rollover keeps a return's name every year, so keying by the
      parent made two years of one return one row. Keyed by position, the
      key carries household, year and return;
    - else the folder's own parent, for a folder outside that layout (a
      test's temporary tree, a folder somebody named by hand). Keying by
      the parent is keying by name, and decision 104 records what that
      means: two folders of one name under different parents are one row.
      Decision 134 narrowed that note to folders the layout does not read.
    """
    folder = Path(engagement_dir)
    recorded = _recorded_root_over(folder)
    if recorded is not None:
        return recorded
    if root is not None:
        return Path(root)
    positional = _positional_root(folder)
    if positional is not None:
        return positional
    return folder.parent


def _positional_root(folder: Path) -> Path | None:
    """The clients root ``folder`` sits under when it is a return in the
    layout of decision 125 - its parent named as a year and its
    household's parent named :data:`tracker.layout.PRIVATE_TREE` - else
    ``None``.

    Both names are asked: a folder that happens to sit four levels deep is
    not a return unless the layout's own words say so. They are asked of
    the folder **resolved**, the spelling :func:`engagement_path` keys it
    by: a relative path (``2025/1040 - Smith``, typed from inside the
    household) has no private tree above it as written, and a private
    tree typed in another case (``j park & associates`` on a filesystem
    that does not tell the two apart) is not the layout's name as typed.
    Either, asked as given, would fall back to the year folder - the very
    collision decision 134 removes. The review of decision 134 found both.
    :mod:`tracker.layout` is imported at call time because this module
    imports ``records``, ``ledger`` and ``locking`` and nothing else at
    load time (``tests/test_layers.py``); ``layout`` stays the one place
    the shape is worded.
    """
    from tracker import layout

    try:
        folder = folder.resolve()
    except OSError:
        return None
    if len(folder.parents) < 4:
        return None
    if not layout.is_year_folder(folder.parent.name):
        return None
    if folder.parent.parent.parent.name != layout.PRIVATE_TREE:
        return None
    return layout.root_of(folder)


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
    2026-09-19 found an archived copy of one engagement's folder, one
    level deeper under the root and never seen, answered as that
    engagement's own row: its reads refused the journal as
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
        # Sorted keys, exactly as the journal writes a line
        # (``ledger.append``), so a list of small objects - the return's
        # people (decision 128) - has one text form whichever side wrote
        # it, and ``check()`` compares the column with the fold rather
        # than two orderings of the same fact. A list of words is
        # unaffected: there are no keys to sort.
        return json.dumps(list(value), ensure_ascii=False, sort_keys=True)
    raise StoreError(f"the store has no column form for {type(value).__name__} ({value!r})")


#: The columns every new row of ``engagements`` is laid out with, and the
#: record defaults behind them. One home for the list, because three
#: writers insert a row - the reader's top-up, the rebuild and nothing
#: else - and a column added to either record must reach all of them.
_NEW_ENGAGEMENT_COLUMNS = f'"path", {_names(ENGAGEMENT_COLUMNS)}, {_names(HOUSEHOLD_COLUMNS)}, ' \
                          "kind, ledger_head, applied_seq, built_at"


def _new_engagement_defaults() -> list[object]:
    """Both records at their defaults, in ``_NEW_ENGAGEMENT_COLUMNS`` order.

    A folder the store has just met is a return until a
    ``household_changed`` line says otherwise, and every detail of it is
    the record's own default until an event speaks for it.
    """
    return (
        [_to_sql(getattr(EngagementInfo(), name)) for name in ENGAGEMENT_COLUMNS]
        + [_to_sql(getattr(HouseholdInfo(), name.removeprefix(HOUSEHOLD_PREFIX)))
           for name in HOUSEHOLD_COLUMNS]
        + [KIND_RETURN]
    )


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
            # A null is a line that never said - a journal from before the
            # field existed - and what that means is the record's answer,
            # not this module's (``records.RULE_FLAG_DEFAULTS``): a rule
            # stored before decision 128 reads as named.
            row[name] = RULE_FLAG_DEFAULTS[name] if value is None else bool(value)
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


def document_seqs(conn: sqlite3.Connection, engagement_dir: Path | str) -> dict[str, int]:
    """Each index row's identity -> the journal line that last wrote it: the
    freshness handle a person's action carries back (decision 112).

    The number was already here - :func:`_apply` sets it as each row event
    is folded - and nothing outside this module could read it. It is the
    record's own bookkeeping and not a fact about the document, so it
    never joins the row: it rides beside it in the state the app reads,
    comes back with the person's click, and the filer refuses an action
    made against a row the record has rewritten since. Per row, because a
    scan moves the engagement's head and no row's number, and refusing on
    the head would refuse every click made during a pass.

    Keyed through the recorded root as :func:`documents` is, so one folder
    is one key here too, and ``{}`` for an engagement the store does not
    hold - a folder nothing has been recorded for yet, which is what a
    brand new engagement is. A read: no lock.
    """
    row = _engagement_row(conn, engagement_dir)
    return {} if row is None else _stored_seqs(conn, row["id"])


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
    never as typed. A word a person took back in the editor is gone from
    here - ``manifest.unlearn_keyword`` records one ``keyword_unlearned``
    and this fold deletes the row (decision 113) - and a word taught again
    afterwards comes back last, because the insert carries the new line's
    sequence number.
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


def household_info(conn: sqlite3.Connection, folder: Path | str) -> HouseholdInfo | None:
    """The household's details as the store holds them, or ``None`` for a
    folder it does not hold - and for one it holds as a return.

    What ``tracker.households.load_household_info()`` answers from and what
    a save diffs against. ``None`` rather than a blank household, because
    a return folder is not a household with nothing typed in it: the
    registry has to tell the two apart to know what a folder at the
    household level is (decision 125).
    """
    row = _engagement_row(conn, folder)
    if row is None or row["kind"] != KIND_HOUSEHOLD:
        return None
    return household_from_json(_household_from_sql(row))


def _household_from_sql(row: sqlite3.Row) -> dict:
    """One stored household row in the shape a ``household_changed`` event
    carries it: the prefix off, the members back from JSON text.

    The inverse of :func:`_to_sql` for these columns, for the reason
    :func:`_rule_from_sql` exists: SQLite cannot tell a JSON array in a
    text column from a string.
    """
    out: dict[str, object] = {}
    for column in HOUSEHOLD_COLUMNS:
        name = column.removeprefix(HOUSEHOLD_PREFIX)
        value = row[column]
        out[name] = json.loads(value or "[]") if name in _LIST_COLUMNS else value
    return out


def kind(conn: sqlite3.Connection, folder: Path | str) -> str | None:
    """Whether the store holds this folder as a return or as a household,
    or ``None`` when it holds it at all.

    The one question discovery asks of a folder at the household level: a
    journal alone does not say which of the two a folder is, and a return
    record sitting where a household record belongs is a misfit from the
    layout before decision 125, not a household.
    """
    row = _engagement_row(conn, folder)
    return None if row is None else row["kind"]


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


def last_event(conn: sqlite3.Connection, engagement_dir: Path | str, name: str,
               *, carrying: str | None = None) -> dict | None:
    """The newest event of ``name`` this engagement's journal carries, as
    the line was written, or ``None`` when it never carried one (or the
    store does not hold the engagement). With ``carrying``, the newest one
    whose payload has that key: the last ``drafted`` that wrote a file,
    rather than the last hold.

    Asked of the ``events`` table for the reason :func:`has_rules_event`
    is: folding a season of lines to find the last ``drafted`` is the cost
    the store exists to remove, and the store is synced to the journal
    before a writer asks. What it answers is what the reminder compares
    this week's draft with (decision 115): whether anything moved since
    the last one, and what.
    """
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        return None
    for found in conn.execute(
        'SELECT payload FROM events WHERE engagement_id = ? AND "event" = ? ORDER BY seq DESC',
        (row["id"], name),
    ):
        event = json.loads(found["payload"])
        if carrying is None or carrying in event:
            return event
    return None


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


def _write_intent(conn: sqlite3.Connection, engagement_id: int, event: dict, seq: int) -> None:
    """One move begun, or one abandoned (decision 119).

    The whole line is kept, because what a recovery needs is the whole of
    it: the operations, the row the decision will record, the event that
    completes it and the day it was written. Replaced rather than added to
    - a key is one row and a row is one decision at a time - and deleted on
    the abandonment, as it is on the row event that completes it. The same
    fold as :func:`tracker.ledger._apply_intent_event`, which is what
    :func:`check` holds this table to.
    """
    key = event.get(ledger.KEY_KEY)
    if event.get(ledger.EVENT_KEY) != ledger.MOVING:
        _close_intent(conn, engagement_id, key)
        return
    conn.execute(
        'INSERT OR REPLACE INTO intents (engagement_id, "key", seq, payload) VALUES (?, ?, ?, ?)',
        (engagement_id, key, seq, json.dumps(event, ensure_ascii=False, sort_keys=True)),
    )


def _close_intent(conn: sqlite3.Connection, engagement_id: int, key: str | None) -> None:
    """The intent this key had open, if it had one, is finished with."""
    if key:
        conn.execute('DELETE FROM intents WHERE engagement_id = ? AND "key" = ?',
                     (engagement_id, key))


def open_intents(conn: sqlite3.Connection, engagement_dir: Path | str) -> list[dict]:
    """The moves this engagement began and has not finished, oldest first.

    What the filer's recovery works from at the
    start of every pass, and what the person's actions refuse on: a folder
    with an intent open is a folder the record is in the middle of a
    decision about, and the honest answer to a click on it is "the next
    pass finishes that first". Oldest first, because the operations of one
    decision may sit on the ones of another (a copy from a path an earlier
    intent put a file at).

    A read: no lock. ``[]`` for an engagement the store does not hold, and
    for the ordinary case of a record where every decision that began has
    ended.
    """
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        return []
    return [json.loads(one["payload"]) for one in conn.execute(
        "SELECT payload FROM intents WHERE engagement_id = ? ORDER BY seq", (row["id"],))]


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


def _write_household_info(conn: sqlite3.Connection, engagement_id: int, info: dict) -> None:
    """The household's details, as ``records.household_to_json`` shapes
    them, and the row said to be a household's (decision 125).

    Only the fields the line carries, as a return's details are written:
    a ``household_changed`` event names what moved. The ``kind`` is set on
    every one of them rather than only the first, because it is what a
    reader asks the row and setting it once would depend on which line the
    store happened to fold first after a rebuild.
    """
    named = [name for name in HOUSEHOLD_COLUMNS if name.removeprefix(HOUSEHOLD_PREFIX) in info]
    assignments = ", ".join(f'"{name}" = ?' for name in [*named, "kind"])
    conn.execute(
        f"UPDATE engagements SET {assignments} WHERE id = ?",
        (*[_household_cell(name.removeprefix(HOUSEHOLD_PREFIX), info) for name in named],
         KIND_HOUSEHOLD, engagement_id),
    )


def _household_cell(name: str, info: dict) -> object:
    """One household field as its column holds it.

    The two fields that are lists - the members and the feeds (decision
    129) - are stored as JSON arrays, and a line that wrote one name as a
    string is read as one member on both sides
    (``records.household_from_json``) - so the column holds a list either
    way and :func:`check` compares like with like.
    """
    value = info[name]
    if name not in _LIST_COLUMNS:
        return _to_sql(value)
    return _to_sql([value] if isinstance(value, str) else list(value or []))


MALFORMED_LINE = "{where}: line {seq} ({event}) {problem}; the journal is not applied past it"
#: The key decision 129's hand-over intent carried the other record's half
#: under. Named here, by the one reader that still speaks of it, so that
#: the refusal says it by name (decision 132).
ALSO_IN = "also_in"


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

    A keyword taught or taken back is checked here for the first time with
    decision 113: until then the two tables this file writes from a line
    were the rules and the statuses, and a ``keyword_learned`` of any shape
    at all was written with ``str()`` around whatever it carried - a number
    for a keyword became the text of that number in the table while the
    journal's own fold kept the number, which is a disagreement
    :func:`check` would now report and nobody could act on. Both keyword
    events name a request and a word, both as text and neither blank, or
    the line is refused like any other.
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
        # The return's people (decision 128). The journal is a synced file
        # somebody may have opened, and a person of a kind nothing knows or
        # a spelling of one word is a line the name check would either pass
        # over or misfile on - so it is refused here, by the record's own
        # reader, rather than written into a column a later pass trusts.
        if isinstance(info, dict) and "people" in info:
            try:
                records.people_from_json(info["people"])
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                refuse(f"carries people this version cannot read ({exc})")
    elif name == ledger.SCANNED:
        statuses = event.get(ledger.STATUSES_KEY)
        if statuses is not None and not isinstance(statuses, dict):
            refuse(f"carries {ledger.STATUSES_KEY!r} that is not a mapping")
        for identifier, stored in (statuses or {}).items():
            if not isinstance(stored, dict):
                refuse(f"carries a status for {identifier!r:.40} that is not a mapping")
    elif name == ledger.MOVING:
        # The intent is what a later pass will finish a half-made move
        # from, so its shape is checked here rather than trusted in the
        # middle of a recovery with a file already moved: the operations
        # are a list, each one names what it does, where from and - unless
        # it is a stand-down - where to, and the row it carries is a row.
        ops = event.get(ledger.OPS_KEY)
        if not isinstance(ops, list):
            refuse(f"carries {ledger.OPS_KEY!r} that is not a list")
        for op in ops:
            if not isinstance(op, dict):
                refuse(f"carries an operation that is not one: {op!r:.60}")
            kind = op.get(ledger.OP_KEY)
            if kind not in (ledger.OP_MOVE, ledger.OP_COPY, ledger.OP_REMOVE):
                refuse(f"carries an operation this version does not know: {kind!r:.40}")
            if not isinstance(op.get(ledger.FROM_KEY), str):
                refuse(f"carries a {kind} with no {ledger.FROM_KEY!r}")
            if kind != ledger.OP_REMOVE and not isinstance(op.get(ledger.TO_KEY), str):
                refuse(f"carries a {kind} with no {ledger.TO_KEY!r}")
            if not isinstance(op.get(ledger.DIGEST_KEY, ""), str):
                refuse(f"carries a {kind} whose {ledger.DIGEST_KEY!r} is not text")
        row = event.get(ledger.ROW_KEY)
        if row is not None and not isinstance(row, dict):
            refuse(f"carries {ledger.ROW_KEY!r} that is not a row")
        leaving = event.get(ledger.WAS_KEY)
        if leaving is not None and not isinstance(leaving, str):
            refuse(f"carries {ledger.WAS_KEY!r} that is not a location")
        also = event.get(ledger.ALSO_KEY)
        if also is not None and not isinstance(also, list):
            refuse(f"carries {ledger.ALSO_KEY!r} that is not a list")
        reason = event.get(ledger.REASON_KEY)
        if reason is not None and not isinstance(reason, str):
            refuse(f"carries {ledger.REASON_KEY!r} that is not text")
        # Decision 129's intent carried the events it would write into
        # another return's record. Decision 132 retired that: nothing ever
        # writes into another record, and an intent whose second half this
        # version cannot write must not be recovered as if it had none.
        if ALSO_IN in event:
            refuse(f"carries {ALSO_IN!r}, the other record's half of a decision 129 "
                   f"hand-over, which this version does not write; finish it with the "
                   f"version that began it")
    elif name == ledger.RELEASED:
        # A release names the row it takes out and says where it went -
        # and carries no row, because there is none left to carry.
        if not isinstance(event.get(ledger.KEY_KEY), str) or not event.get(ledger.KEY_KEY):
            refuse(f"carries no {ledger.KEY_KEY!r}")
        if ledger.ROW_KEY in event:
            refuse(f"carries {ledger.ROW_KEY!r}; a release carries no row")
        if not isinstance(event.get(ledger.REASON_KEY, ""), str):
            refuse(f"carries {ledger.REASON_KEY!r} that is not text")
    elif name in (ledger.KEYWORD_LEARNED, ledger.KEYWORD_UNLEARNED):
        for key in (ledger.IDENTIFIER_KEY, ledger.KEYWORD_KEY):
            value = event.get(key)
            if not isinstance(value, str):
                refuse(f"carries {key!r} that is not text: {value!r:.60}")
            if not value:
                refuse(f"carries a blank {key!r}")
    elif name == ledger.HOUSEHOLD_CHANGED:
        # The household's details travel exactly as a return's do, so the
        # line is checked exactly as one: a mapping of fields, and the one
        # field that is a list of words is a list of words.
        household = event.get(ledger.HOUSEHOLD_KEY)
        if household is not None and not isinstance(household, dict):
            refuse(f"carries {ledger.HOUSEHOLD_KEY!r} that is not a mapping")
        members = (household or {}).get("members")
        # A hand-written line naming one person is read as one member
        # (``records.household_from_json``) rather than refused: the
        # journal is a synced file somebody may have opened. A list
        # holding something that is not a name is not a members list.
        if members is not None and not isinstance(members, (list, str)):
            refuse("carries 'members' that is neither a list nor a name")
        for member in members if isinstance(members, list) else []:
            if not isinstance(member, str):
                refuse(f"names a member that is not text: {member!r:.60}")
        # The feed list (decision 129). A feed naming no household or no
        # return line points at nothing a pass could resolve, so it is
        # refused here by the record's own reader rather than written into
        # a column the sort would later read as a route.
        if isinstance(household, dict) and "feeds" in household:
            try:
                records.feeds_from_json(household["feeds"])
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                refuse(f"carries feeds this version cannot read ({exc})")
    elif name == ledger.SHARING_CONFIRMED:
        # The firm's word, dated, and nothing else (decision 126): the
        # stamp is the whole of it. A line carrying a payload is either a
        # newer version's or a hand-written one, and either way this
        # version would be storing something it cannot fold - so it is
        # refused by name here rather than silently kept in the events
        # table where a reader would later trust it.
        carried = sorted(set(event) - {ledger.EVENT_KEY, ledger.AT_KEY})
        if carried:
            refuse(f"carries {', '.join(repr(key) for key in carried)}; it carries nothing")


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

    A keyword a person's filing taught is inserted as it is met and deleted
    again when a person takes it back (decision 113): the insert carries the
    line's own sequence number, so a word taught again comes back last -
    whether or not it was taken back first - which is the order
    ``tracker.ledger.apply`` folds it in and what :func:`check` holds the
    two to.

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
            # The decision this key was moving under is recorded now, so
            # there is nothing left to finish (decision 119).
            _close_intent(conn, engagement_id, event.get(ledger.KEY_KEY))
            _close_intent(conn, engagement_id, was)
        elif name in ledger.RELEASE_EVENTS:
            # The row leaves the index and its intent closes (decision
            # 132): the ``was`` path's deletion, with no row to follow.
            for gone in (event.get(ledger.KEY_KEY), event.get(ledger.WAS_KEY)):
                if gone:
                    seqs.pop(gone, None)
                    _close_intent(conn, engagement_id, gone)
        elif name in (ledger.MOVING, ledger.MOVE_ABANDONED):
            _write_intent(conn, engagement_id, event, seq)
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
        elif name == ledger.KEYWORD_UNLEARNED:
            conn.execute(
                'DELETE FROM learned_keywords WHERE engagement_id = ? AND "identifier" = ? '
                "AND keyword = ?",
                (engagement_id, identifier_key(str(event.get(ledger.IDENTIFIER_KEY, ""))),
                 str(event.get(ledger.KEYWORD_KEY, ""))),
            )
        elif name in (ledger.RULES_CHANGED, ledger.RULES_IMPORTED):
            _apply_rules_event(conn, engagement_id, event)
        elif name == ledger.HOUSEHOLD_CHANGED:
            _write_household_info(conn, engagement_id, dict(event.get(ledger.HOUSEHOLD_KEY) or {}))
        ledger.apply(state, event)
    if any(event.get(ledger.EVENT_KEY) in ledger.ROW_EVENTS | ledger.RELEASE_EVENTS
           for event in events):
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


def _held_under_the_lock(conn: sqlite3.Connection, engagement_dir: Path,
                         *, unwritten: str, doing: str) -> sqlite3.Row:
    """The engagement's row, for a writer: refused by name outside the
    engagement lock and for an engagement the store does not hold.

    The two sentences every writer here refuses with - :func:`record` and
    :func:`remember_verdicts` - worded once so they are the same sentence.
    """
    if not lock_is_held(engagement_dir):
        raise StoreError(
            f"{engagement_dir.name}: the record is written to only while this run holds the "
            f"engagement lock; {unwritten} not written"
        )
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        raise StoreError(
            f"{engagement_dir.name}: the store does not hold this engagement; build it with "
            f"rebuild_engagement() before {doing}"
        )
    return row


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
    row = _held_under_the_lock(conn, engagement_dir,
                               unwritten=f"{len(events)} event(s) were", doing="recording to it")
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
    defaults = _new_engagement_defaults()
    with _transaction(conn):
        cursor = conn.execute(
            f"INSERT INTO engagements ({_NEW_ENGAGEMENT_COLUMNS}) "
            f"VALUES ({_marks(len(defaults) + 4)})",
            (rel, *defaults, ledger.head(engagement_dir), len(events), ledger.stamp()),
        )
        if events:
            _apply(conn, cursor.lastrowid, events, start=1)
    return len(events)


# --------------------------------------------------------- the verdict cache ----


def cached_verdicts(
    conn: sqlite3.Connection, engagement_dir: Path | str, *, version: int
) -> tuple[dict[str, dict], dict[str, dict[str, dict]]]:
    """One engagement's verdict cache at ``version``: the memos and the verdicts.

    The two shapes ``tracker.content_check.ContentCache`` holds in memory -
    ``path_key -> {size, mtime_ns, digest}`` and ``digest -> fingerprint ->
    verdict`` - so the cache is loaded once when it is built and the pass's
    hot path stays in memory exactly as it was when the cache was a file.
    The verdict comes back as the dict the cache handed in; this module
    never learns the record it is (:mod:`tracker.content_check` is above it).
    A row at another ``version`` is not returned: a verdict written under
    an older reading of the rules is not a verdict, and :func:`remember_verdicts`
    deletes such rows on the next save.

    No lock: a read is a read. An engagement the store does not hold is
    refused by name rather than answered with an empty cache that has
    nowhere to be saved - both writers ``ensure()`` before building one.
    """
    engagement_dir = Path(engagement_dir)
    row = _engagement_row(conn, engagement_dir)
    if row is None:
        raise StoreError(
            f"{engagement_dir.name}: the store does not hold this engagement; build it with "
            f"rebuild_engagement() before caching verdicts for it"
        )
    memos = {
        memo["path_key"]: {"size": memo["size"], "mtime_ns": memo["mtime_ns"],
                           "digest": memo["digest"]}
        for memo in conn.execute(
            f"SELECT path_key, size, mtime_ns, digest FROM {FILE_MEMOS_TABLE} "
            f"WHERE engagement_id = ?", (row["id"],))
    }
    verdicts: dict[str, dict[str, dict]] = {}
    for stored in conn.execute(
        f"SELECT digest, fingerprint, verdict FROM {VERDICTS_TABLE} "
        f"WHERE engagement_id = ? AND version = ?", (row["id"], version),
    ):
        verdicts.setdefault(stored["digest"], {})[stored["fingerprint"]] = json.loads(stored["verdict"])
    return memos, verdicts


def remember_verdicts(
    conn: sqlite3.Connection,
    engagement_dir: Path | str,
    *,
    version: int,
    memos: dict[str, dict],
    verdicts: dict[str, dict[str, dict]],
    forget_paths: set[str],
    forget_digests: set[str],
) -> None:
    """Write one save of the verdict cache: what it learned and what it forgot.

    **One immediate transaction, and never** :func:`record`. A cache save
    has no journal line and no ``seq`` - a verdict is a derivation of the
    bytes and the rules, not a fact about the engagement - so it goes in
    a transaction of its own, which is SQLite's whole-or-nothing, the
    property the atomic file write used to give it. In it: the
    engagement's verdict rows at any other ``version`` are deleted (a
    matcher change invalidates every verdict from before it, as it always
    has), the paths and digests the cache pruned are deleted, and the
    memos and verdicts given are upserted.

    **Under the engagement lock all the same.** Every writer already holds
    it, so the rule costs nothing; and the memo ties a *path* to a digest,
    so a writer racing a pass over the same files could memo a path
    against bytes the pass has just replaced. Refused by the same two
    sentences :func:`record` uses. The caller must not be inside
    :func:`record`'s transaction (a nested ``BEGIN`` fails), and no caller is.
    """
    engagement_dir = Path(engagement_dir)
    row = _held_under_the_lock(conn, engagement_dir,
                               unwritten="the verdicts were", doing="caching verdicts for it")
    with _transaction(conn):
        conn.execute(f"DELETE FROM {VERDICTS_TABLE} WHERE engagement_id = ? AND version != ?",
                     (row["id"], version))
        for path_key in sorted(forget_paths):
            conn.execute(f"DELETE FROM {FILE_MEMOS_TABLE} WHERE engagement_id = ? AND path_key = ?",
                         (row["id"], path_key))
        for digest in sorted(forget_digests):
            conn.execute(f"DELETE FROM {VERDICTS_TABLE} WHERE engagement_id = ? AND digest = ?",
                         (row["id"], digest))
        for path_key, memo in memos.items():
            _write_memo(conn, row["id"], path_key, memo)
        for digest, by_fingerprint in verdicts.items():
            for fingerprint, verdict in by_fingerprint.items():
                _write_verdict(conn, row["id"], digest, fingerprint, version, verdict)


def _write_memo(conn: sqlite3.Connection, engagement_id: int, path_key: str, memo: dict) -> None:
    conn.execute(
        f"INSERT OR REPLACE INTO {FILE_MEMOS_TABLE} (engagement_id, path_key, size, mtime_ns, digest) "
        f"VALUES (?, ?, ?, ?, ?)",
        (engagement_id, path_key, int(memo["size"]), int(memo["mtime_ns"]), str(memo["digest"])),
    )


def _write_verdict(conn: sqlite3.Connection, engagement_id: int, digest: str, fingerprint: str,
                   version: int, verdict: dict) -> None:
    conn.execute(
        f"INSERT OR REPLACE INTO {VERDICTS_TABLE} (engagement_id, digest, fingerprint, version, verdict) "
        f"VALUES (?, ?, ?, ?, ?)",
        (engagement_id, digest, fingerprint, version,
         json.dumps(verdict, ensure_ascii=False, sort_keys=True)),
    )


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

    **The verdict cache goes with the rows and is not refilled** (decision
    107): its two tables cascade with the engagement like every other, and
    nothing in the journal can rebuild them, because nothing in the
    journal ever held them. The next pass reads each document once.
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
        defaults = _new_engagement_defaults()
        cursor = conn.execute(
            f"INSERT INTO engagements ({_NEW_ENGAGEMENT_COLUMNS}) "
            f"VALUES ({_marks(len(defaults) + 4)})",
            (rel, *defaults, head, len(events), built_at),
        )
        if events:
            _apply(conn, cursor.lastrowid, events, start=1)


# --------------------------------------------------------------- the check ----


def check(conn: sqlite3.Connection, root: Path | str, engagement_dir: Path | str) -> list[str]:
    """Every place the store and the journal disagree, as sentences.

    The gate. An empty list is the claim that these tables say exactly
    what the engagement's own record says - the same index rows in the
    same order, field for field; the same status for every identifier; the
    same rule, where the record carries one; and, since decision 113, the
    same keywords taught to each request, in the same order. Anything else
    is named in a sentence a person can act on: which engagement, which row
    or identifier, which field, what each side says.

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
    problems += _check_intents(conn, engagement["id"], name, folded.intents)
    problems += _check_learned(conn, engagement["id"], name, folded.learned)
    problems += _check_household(conn, engagement["id"], name, folded.household)
    return problems


def _check_household(
    conn: sqlite3.Connection, engagement_id: int, name: str, recorded: dict[str, object]
) -> list[str]:
    """The household's details, table against journal (decision 125).

    A folder whose journal carries a ``household_changed`` line is a
    household, and the row must say so as well as holding what the line
    said: a row the store still calls a return would be a household
    discovery walks straight past. A folder with no such line is compared
    about nothing, which is every return in the practice.
    """
    if not recorded:
        return []
    row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    problems = []
    if row["kind"] != KIND_HOUSEHOLD:
        problems.append(
            f"{name}: the record carries the household's details and the store holds the "
            f"folder as {row['kind']!r}")
    for field in recorded:
        column = f"{HOUSEHOLD_PREFIX}{field}"
        if column not in HOUSEHOLD_COLUMNS:
            continue
        theirs = _household_cell(field, recorded)
        if row[column] != theirs:
            problems.append(
                f"{name}: household {field}: the store says {row[column]!r}, "
                f"the record says {theirs!r}")
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


def _check_intents(
    conn: sqlite3.Connection, engagement_id: int, name: str, recorded: dict[str, dict]
) -> list[str]:
    """The moves this engagement has open, both ways round (decision 119).

    The two folds have to agree about exactly this: a recovery finishes
    what the table says is open, and a table that had kept an intent the
    journal closed would move a file the record has already recorded - the
    one thing this whole decision exists to stop. So the line is compared
    whole, as the documents' fields are.
    """
    stored = {row["key"]: row["payload"] for row in conn.execute(
        'SELECT "key", payload FROM intents WHERE engagement_id = ?', (engagement_id,))}
    problems = []
    for key, event in recorded.items():
        held = stored.get(key)
        theirs = json.dumps(event, ensure_ascii=False, sort_keys=True)
        if held is None:
            problems.append(f"{name}: the move open on {key!r} is in the record and not in the store")
        elif held != theirs:
            problems.append(
                f"{name}: the move open on {key!r}: the store holds {held!r:.120}, "
                f"the record carries {theirs!r:.120}")
    for key in sorted(set(stored) - set(recorded)):
        problems.append(f"{name}: the move open on {key!r} is in the store and not in the record")
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


def _check_learned(
    conn: sqlite3.Connection, engagement_id: int, name: str, recorded: dict[str, tuple[str, ...]]
) -> list[str]:
    """The keywords filings taught, table against journal (decision 113).

    The one thing in this database the record could not vouch for until
    now: the table only ever grew, the journal's fold did not know the
    event, and this function did not exist - so a row planted or dropped
    behind the journal's back was invisible to the gate. One sentence per
    request whose words differ, naming both sides in the order each holds
    them, because the order is part of the answer: a word taught, taken
    back and taught again belongs last on both sides.

    The table keys a request without case and the journal's fold keys it
    exactly as each line spells it (:class:`tracker.ledger.Folded`), so the
    record's side is folded here, by the one rule that owns it. Two
    spellings of one request - which takes a case-respelling of an
    identifier between two filings - are joined in the order the fold met
    them.
    """
    stored: dict[str, tuple[str, ...]] = {}
    for row in conn.execute(
        'SELECT "identifier", keyword FROM learned_keywords WHERE engagement_id = ? '
        "ORDER BY seq, keyword", (engagement_id,),
    ):
        stored[row["identifier"]] = stored.get(row["identifier"], ()) + (row["keyword"],)
    folded: dict[str, tuple[str, ...]] = {}
    for identifier, taught in recorded.items():
        key = identifier_key(identifier)
        folded[key] = folded.get(key, ()) + tuple(taught)
    return [
        f"{name}: request {key}, the keywords filings taught: the store says "
        f"{list(stored.get(key, ()))!r}, the record says {list(folded.get(key, ()))!r}"
        for key in sorted(set(stored) | set(folded))
        if stored.get(key, ()) != folded.get(key, ())
    ]


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


def store_named(given: Path) -> Path | None:
    """The store file a command-line argument means, or None for one it cannot mean.

    Three spellings, because the runbook says "the app folder" and a person
    at the office will type any of them: an existing folder is the app
    folder and the store is :data:`STORE_FILENAME` inside it; a path named
    :data:`STORE_FILENAME` is the store itself, whether or not it exists yet
    (``rebuild`` creates it); an existing file is the settings file and the
    store sits beside it (:func:`path_for`). Anything else is refused rather
    than resolved, because the resolution used to be ``with_name`` on
    whatever was typed, and the integration run of decision 107 typed the
    app folder as the runbook said and silently got an empty store *beside*
    it - ``check`` then reported an engagement the store did not hold, and a
    ``rebuild`` typed next would have built into the wrong file. A typo must
    never create a store.
    """
    if given.is_dir():
        return given / STORE_FILENAME
    if given.name == STORE_FILENAME:
        return given
    if given.is_file():
        return path_for(given)
    return None


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
    parser.add_argument("store", help="the app folder, the settings file in it, or the store file itself")
    parser.add_argument("command", choices=("rebuild", "check", "export", "state"))
    parser.add_argument("root", help="the clients root")
    parser.add_argument("--engagement", help="one engagement folder instead of every one")
    parser.add_argument("--out", help="where export writes its files")
    ns = parser.parse_args()

    given = Path(ns.store)
    chosen = store_named(given)
    if chosen is None:
        parser.error(f"{given} is not the app folder, a settings file in it, or a {STORE_FILENAME}; "
                     f"nothing was opened and no store was created")
    clients_root = Path(ns.root)
    # Every folder with a record, households included (decision 125): a
    # household's row is held in this same table and folded by the same
    # machinery, so a check that walked only the returns would leave each
    # of them unchecked without saying so.
    folders = ([Path(ns.engagement)] if ns.engagement
               else registry.record_dirs(clients_root))

    print(f"\n{chosen}")
    failures = 0
    try:
        # A store this code cannot open - another version's, a file that is
        # not one - is refused by open() in a sentence; the command line
        # says that sentence and exits 1, never a traceback (decision 107).
        connection = connect(chosen)
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
    except StoreError as exc:
        parser.exit(1, f"{exc}\n")
    finally:
        close()
    if failures:
        print(f"\n  the store and the record do not agree ({failures})\n")
    else:
        print()
    raise SystemExit(1 if failures else 0)
