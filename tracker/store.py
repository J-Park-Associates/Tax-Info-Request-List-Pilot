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

**Rebuild is recovery - compared first.** :func:`rebuild_engagement`
deletes one engagement's rows and builds them again from seq 1 - the
journal replayed, and nothing else. That single function is the answer to
two questions: how a store deleted by accident comes back, and how a store
somebody doubts is proved. It writes nothing to the journal. Since
decision 159 it is held first to **this machine's checkpoint**
(:mod:`tracker.checkpoint`, beside this file): a record shorter than what
this machine saw, rewritten under it, or carrying a line that claims this
machine and that this machine did not write, is refused - by every
catch-up and by a rebuild alike - because a rebuilt store trusts whatever
it is built from, and the store about to be deleted may be the only other
copy of what was lost. :func:`recover` is the one way past: it exports
the store's lines and the record as it is, prints the lines that differ
(never a payload value), and replays only when a person types the
return's name. :func:`verify` is the same proof firm-wide, read-only, with
every recorded file held to its bytes.

**An older version is set aside and rebuilt - with one kind of
exception** (decisions 159 and 204; one policy). A store an earlier version
wrote is renamed out of the way (``.v<N>.old``, never deleted) and a fresh
one built from the journals, which also empties the verdict cache it
keeps, so the next pass reads and OCRs every document again; a newer one
is refused by name. A version is instead **upgraded in
place** only where the change is new columns, each of which is additive
and that no journal line written before the new version can carry - so
every existing row's true value is empty, which the column holds as NULL
exactly as a rebuild would, and :func:`check` holds the columns to the
journal from then on (decision 204's one column; decision 190's three). Each such step
is written out by name in :data:`_IN_PLACE` (from-version -> statements),
never inferred; every other older version is set aside, and a newer one
refused.

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

**The engine's errors leave as the package's** (decision 189). Every
``sqlite3.Error`` a statement here raises - the file locked past the busy
timeout, a disk error, a file that is not a database - leaves as
:class:`StoreUnavailable`, a :class:`StoreError` carrying the SQLite
error's name as its ``code`` and a fixed sentence, because a raw
``OperationalError`` was a class no pass caught and one bad database ended
the whole practice pass with no log and no page. The wrap is the
connection itself (``_Connection``, the factory :func:`open` hands
SQLite), not each call site, so the next query written here is covered
without anyone remembering to.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import logging
import os
import sqlite3
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, fields
from dataclasses import field as _default
from pathlib import Path

from tracker import checkpoint, ledger, records
from tracker.locking import is_this_host, lock_is_held
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

log = logging.getLogger("tracker.store")

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
#: column for it, so it is refused, moved aside and rebuilt from the
#: journals like every version before it - the date itself travels in the
#: ``rules_changed`` event, and only the first pass is slower.
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
#: Version 12 (decision 137, A3) added ``applied_digest`` to
#: ``engagements``: the running chain over the journal lines the store has
#: applied (``ledger.read_with_chain``), so a journal rewritten or reordered
#: to the same length is refused rather than blessed. A version-11 file has
#: no such column, so it is refused, deleted and rebuilt from the journals
#: like every version before it, and the rebuild computes the chain as it
#: replays.
#: Version 13 (decision 142) added the ``asked`` mark to ``requests``: a
#: version-12 file has no column for it, so it is refused, deleted and
#: rebuilt from the journals like every version before it - the mark
#: travels in the ``rules_changed`` lines, and a line written before it
#: existed reads as asked.
#: Version 14 (decision 143) added ``container`` to ``documents``: where
#: the email or zip a document came out of rests, and the ``opened`` row
#: event that records the container itself. A version-13 file has no such
#: column, so it is refused, deleted and rebuilt from the journals like
#: every version before it - the field travels in the row events, and a
#: row written before it existed reads as having come on its own.
#: Version 15 (decision 144) added ``short_title`` to ``requests``: the
#: short name the working folder and copies are named by. A version-14
#: file has no column for it, so it is refused, deleted and rebuilt from
#: the journals like every version before it - the field travels in the
#: ``rules_changed`` lines, and a line written before it existed reads as
#: blank, which derives the short name from the document title.
#: Version 16 (decision 146) added ``answers`` to ``documents``: the other
#: requests a broker's consolidated statement answers without a copy, and
#: the sections that answered each. A version-15 file has no such column,
#: so it is refused, deleted and rebuilt from the journals like every
#: version before it - the field travels in the row events, and a row
#: written before it existed reads as answering nothing.
#: Version 17 (decision 204) added ``waits_for`` to ``documents``: what a
#: row parked because it names another household's person waits for - the
#: fed return line and what its list accepted. It is the store's first
#: **in-place** step (the module docstring's rule, :data:`_IN_PLACE`): no
#: journal line before 204 carries the field, so every version-16 row
#: waits for nothing, and a version-16 file gains the column (NULL, as a
#: rebuild writes it - decision 190) and keeps its verdict cache. Every
#: other earlier version is set aside and rebuilt (decision 159, E3); a
#: newer one refused.
#: Version 18 (decision 190) added ``code`` and ``subfolder`` to
#: ``documents`` and ``note_codes`` to ``statuses``: a row's cause, the
#: client subfolder it came from and the causes a request's notes say, each
#: a column rather than a phrase inside a sentence. It is an in-place step
#: too, by the same rule applied to each column: all three are additive,
#: and no journal line before 190 carries any of them, so
#: every version-17 row's cause reads as ``""`` - not recorded, and nothing
#: reads one out of its words - which is what a rebuild from the journals
#: would give. The verdicts a version-17 file cached are kept as rows but no
#: longer answer: they were cached before a verdict carried its code, and
#: :data:`tracker.content_check.CACHE_VERSION` moved with this step.
SCHEMA_VERSION = 18

#: The explicit in-place upgrades (the module docstring's rule): the
#: version a file is at, and the statements that bring it to the next one.
#: Only new additive columns that no earlier journal line can carry
#: qualify; anything else is a delete-and-rebuild bump. Each is added with
#: no default - NULL on every existing row, which is exactly what a rebuild
#: writes for a line that does not carry the field, and what the records
#: read back as empty - so ``store check`` compares the upgraded file with
#: the journal and finds nothing. (A default of ``''`` would not be what a
#: rebuild writes, and the check named every earlier row; decision 190
#: found that in 204's step and made both steps add NULL.)
_IN_PLACE: dict[int, tuple[str, ...]] = {
    16: ("""ALTER TABLE documents ADD COLUMN "waits_for" TEXT""",),
    17: ("""ALTER TABLE documents ADD COLUMN "code" TEXT""",
         """ALTER TABLE documents ADD COLUMN "subfolder" TEXT""",
         """ALTER TABLE statuses ADD COLUMN "note_codes" TEXT"""),
}

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


#: What a database the engine refused says (decision 189): the SQLite
#: error's name and nothing else. The engine's own text can carry a path
#: or a fragment of a statement, so it stays on ``__cause__`` for a person
#: debugging and is never quoted into a reason, a page or the run log.
STORE_UNAVAILABLE = "the database could not be used ({code})"


class StoreUnavailable(StoreError):
    """The engine refused the store: locked past the busy timeout, a disk
    error, a file that is not a database (decision 189, A-9).

    A :class:`StoreError`, so every pass that already catches one catches
    this and the household it happened in carries it, not the practice
    pass. ``code`` is ``sqlite3.Error.sqlite_errorname`` (``SQLITE_BUSY``,
    ``SQLITE_IOERR_WRITE``); an error that did not come from the engine -
    a closed connection - has none and reads ``SQLITE_ERROR``.
    """

    #: Said as ``<class> (<code>)`` by :func:`tracker.errors.error_class`
    #: (the marker :data:`tracker.errors.SAYS_ITS_CODE`, decision 190).
    says_its_code = True

    def __init__(self, code: str) -> None:
        super().__init__(STORE_UNAVAILABLE.format(code=code))
        self.code = code


def _unavailable(exc: sqlite3.Error) -> StoreUnavailable:
    return StoreUnavailable(getattr(exc, "sqlite_errorname", None) or "SQLITE_ERROR")


class _Cursor(sqlite3.Cursor):
    """A cursor whose rows fail as :class:`StoreUnavailable` too: SQLite
    steps a query as its rows are read, so a disk error can arrive on the
    second row as well as on the statement."""

    def execute(self, sql, parameters=(), /):
        try:
            return super().execute(sql, parameters)
        except sqlite3.Error as exc:
            raise _unavailable(exc) from exc

    def executemany(self, sql, parameters, /):
        try:
            return super().executemany(sql, parameters)
        except sqlite3.Error as exc:
            raise _unavailable(exc) from exc

    def fetchone(self):
        try:
            return super().fetchone()
        except sqlite3.Error as exc:
            raise _unavailable(exc) from exc

    def fetchall(self):
        try:
            return super().fetchall()
        except sqlite3.Error as exc:
            raise _unavailable(exc) from exc

    def fetchmany(self, size=None):
        try:
            return super().fetchmany(self.arraysize if size is None else size)
        except sqlite3.Error as exc:
            raise _unavailable(exc) from exc

    def __next__(self):
        try:
            return super().__next__()
        except sqlite3.Error as exc:
            raise _unavailable(exc) from exc


class _Connection(sqlite3.Connection):
    """The store's connection: **the one choke point** every statement in
    this module goes through (decision 189). Every query here is
    ``conn.execute`` on a connection :func:`open` made, so wrapping the
    connection's own calls - rather than two hundred call sites - is what
    makes "no ``sqlite3.Error`` leaves this module raw" true of the next
    query somebody writes too."""

    def cursor(self, factory=_Cursor):
        try:
            return super().cursor(factory)
        except sqlite3.Error as exc:
            raise _unavailable(exc) from exc

    def execute(self, sql, parameters=(), /):
        return self.cursor().execute(sql, parameters)

    def executemany(self, sql, parameters, /):
        return self.cursor().executemany(sql, parameters)

    def executescript(self, script, /):
        try:
            return super().executescript(script)
        except sqlite3.Error as exc:
            raise _unavailable(exc) from exc

    def commit(self):
        try:
            return super().commit()
        except sqlite3.Error as exc:
            raise _unavailable(exc) from exc

    def close(self):
        try:
            return super().close()
        except sqlite3.Error as exc:
            raise _unavailable(exc) from exc


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
    "asked": "INTEGER",
    "short_title": "TEXT",
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
        applied_digest TEXT NOT NULL DEFAULT '',
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

    Refuses, by name, a file a later version wrote: it holds rows this one
    would fold wrongly, and a silent open is how that becomes a wrong
    answer on a client's file. **A file an earlier version wrote is set
    aside, not refused** (decision 159, E3): it is renamed to
    its name with ``.v<N>.old`` after it - never overwritten, never deleted - and a
    fresh store is opened, which every return's next catch-up builds from
    its record, proved against this machine's checkpoint. Until 159 an
    older store was refused until a person deleted it, and the sentence
    that told them to also offered "or run that version". **Except a
    version upgraded in place** (decisions 204 and 190, :data:`_IN_PLACE`):
    versions 16 and 17 gain their columns where they stand; only
    an older version no in-place step reaches is set aside. The record
    checkpoint beside it is another file with its own version, and no step
    here touches it. The caller closes the connection.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None: no implicit transactions. Every write in this
    # module says BEGIN IMMEDIATE itself, because the guarantee is the
    # whole batch or none of it and a driver-invented transaction boundary
    # is not a guarantee anybody wrote down.
    conn = _connect(path)
    # Closed on any failure below, not left to the garbage collector: on
    # Windows an open handle keeps the file from being renamed or deleted,
    # so a store that could not be opened stayed locked by this process -
    # a long pass included - for the person told to move it aside
    # (decision 159, Windows).
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        while version in _IN_PLACE and version < SCHEMA_VERSION:
            # One transaction per step: the column and the version land
            # together or not at all.
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Read again under the write lock: another opener (the app and
                # a pass starting at once) may have made this step since the
                # version was read, and a step made twice would fail on the
                # column it already added. Theirs stands; this one goes on.
                now = conn.execute("PRAGMA user_version").fetchone()[0]
                if now == version:
                    for statement in _IN_PLACE[version]:
                        conn.execute(statement)
                    conn.execute(f"PRAGMA user_version = {version + 1}")
                    now = version + 1
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                conn.close()
                raise
            version = now
        # **One upgrade policy** (decisions 204 and 159): a version
        # :data:`_IN_PLACE` names is upgraded where it stands, above; an older
        # one it does not name is set aside and rebuilt; a newer one refused.
        if 0 < version < SCHEMA_VERSION:
            conn.close()
            aside = checkpoint.set_aside(path, version)
            log.warning("%s was written by an older version (user_version %d); it is set aside as %s "
                        "and the store is rebuilt from the records", path, version, aside.name)
            conn = _connect(path)
            version = 0
        if version == 0:
            for statement in SCHEMA:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        elif version != SCHEMA_VERSION:
            conn.close()
            raise StoreError(checkpoint.NEWER_FILE.format(path=path, version=version, known=SCHEMA_VERSION,
                                                          what="store"))
    except BaseException:
        _close_after_failure(conn)
        raise
    return conn


def _connect(path: Path) -> sqlite3.Connection:
    # The factory is the one choke point (decision 189): every statement
    # below and in every function of this module goes through it.
    try:
        conn = sqlite3.connect(path, isolation_level=None, factory=_Connection)
    except sqlite3.Error as exc:
        raise _unavailable(exc) from exc
    try:
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
    except BaseException:
        _close_after_failure(conn)       # a file that is not a database: see open()
        raise
    return conn


def _close_after_failure(conn: sqlite3.Connection) -> None:
    """Close a connection whose opening failed, keeping the failure that is
    being raised as the one reported.

    Why not leave it to Python: the connection is still referenced from the
    exception's traceback and a cursor's cycle, so it stays open until the
    garbage collector runs. On Windows an open SQLite handle is an open
    file, and an open file cannot be renamed or deleted (WinError 32): the
    damaged file this process refused would stay locked against the very
    step the refusal names (decision 159, Windows). A close that fails
    itself says nothing new; the error already being raised does.
    """
    try:
        conn.close()
    except (sqlite3.Error, StoreError):
        pass


def open_read_only(path: Path | str) -> sqlite3.Connection:
    """The store opened so that nothing can be written through it: what the
    read-only verify uses (decision 159, G-10). Never creates a store; a
    store of another version is refused by name."""
    path = Path(path)
    if not path.is_file():
        raise StoreError(f"there is no store at {path}; nothing was created")
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, isolation_level=None,
                               factory=_Connection)
    except sqlite3.Error as exc:
        raise _unavailable(exc) from exc
    try:
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    except BaseException:
        _close_after_failure(conn)
        raise
    if version != SCHEMA_VERSION:
        conn.close()
        raise StoreError(f"{path} is a store at user_version {version}; this version reads "
                         f"{SCHEMA_VERSION}, and verify changes nothing")
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
    from tracker import layout
    from tracker.settings import clients_root

    root = clients_root()
    if root is None:
        return None
    try:
        under = layout.parts_below(root.resolve(), folder.resolve())
    except OSError:
        return None
    return root if under is not None else None


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
    # The layout's own parser says whether it is a return (decision 188).
    if layout.place_of(folder.parents[3], folder).kind != layout.RETURN:
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
    from tracker import layout

    root, folder = Path(root).resolve(), Path(engagement_dir).resolve()
    below = layout.parts_below(root, folder)
    if below is None:
        raise StoreError(f"{folder} is not under the clients root {root}")
    return "/".join(below) or "."


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
                          "kind, ledger_head, applied_seq, applied_digest, built_at"


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
            # Read back as it was written: a list of words (decision 137, L4).
            if problem := records.word_list_problem(row[name]):
                raise StoreError(f"the stored rule {stored['identifier']!r}'s {name!r} {problem}; "
                                 f"run the store check, then rebuild")
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
    if row is not None:
        with _transaction(conn):
            conn.execute("DELETE FROM engagements WHERE id = ?", (row["id"],))
    # And what this machine vouched for about it (decision 159) - whether or
    # not the store holds it (the review's M2): after a store was set aside
    # or deleted, a return created again under a removed one's name must
    # not be held to the removed one's record.
    key = row["path"] if row is not None else engagement_path(key_root(engagement_dir), engagement_dir)
    with _beside(conn) as held:
        if held is not None:
            checkpoint.forget(held, key)
    return row is not None


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
    """One rule row, as ``records.rule_to_json`` shapes it, into ``requests``.

    Its list fields are lists of words, or nothing is written (decision
    137, L4): the line was checked on its way in, and this is the same
    rule said where the row reaches the table."""
    for name in RULE_LIST_FIELDS:
        if problem := records.word_list_problem(row.get(name)):
            raise StoreError(f"the rule {row.get('identifier')!r}'s {name!r} {problem}")
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


#: The one sentence a line the store will not apply is refused with
#: (decision 137, L4): which line of which record, that it is malformed,
#: and what is wrong with it.
MALFORMED_LINE = ("{where}: line {seq} of the record is malformed ({event} {problem}); "
                  "the journal is not applied past it")
#: What :data:`MALFORMED_LINE` calls an event whose name this version does
#: not know, rather than quoting it (decision 187).
UNKNOWN_EVENT = "an event this version does not know"
#: The key decision 129's hand-over intent carried the other record's half
#: under. Named here, by the one reader that still speaks of it, so that
#: the refusal says it by name (decision 132).
ALSO_IN = "also_in"


def _line_keys_problem(event: dict) -> str:
    """What is wrong with the three keys the record itself writes on every
    line since decision 159 (``ledger.LINE_KEYS``), said as the gate says a
    problem, or ``""``: a link that is not blank or a digest, a format that
    is not one this version writes, and - on a line that carries a link or
    a writer - a writer that is not a machine's name
    (``records.host_problem``). Part of the one admission
    (:func:`_refuse_a_malformed_line`), and asked by the checkpoint's
    judgment of a line before it trusts its writer (:func:`_judge`), so no
    line is judged this machine's or another's on a name the rule refuses.
    The link's *place* in the chain is the ledger reader's, which alone
    has the chain."""
    if ledger.LINK_KEY in event and (problem := records.digest_problem(event[ledger.LINK_KEY])):
        return f"carries {ledger.LINK_KEY!r} that {problem}"
    if ledger.FORMAT_KEY in event and (
            problem := records.count_problem(event[ledger.FORMAT_KEY], 1, ledger.RECORD_FORMAT)):
        return f"carries {ledger.FORMAT_KEY!r} that {problem}"
    if (ledger.LINK_KEY in event or ledger.HOST_KEY in event) and (
            problem := records.host_problem(event.get(ledger.HOST_KEY))):
        return f"carries {ledger.HOST_KEY!r} that {problem}"
    return ""


def _refuse_a_malformed_line(event: dict, seq: int, where: str, *, kind: str = KIND_RETURN) -> None:
    """A line that parses as JSON and names an event but carries the wrong
    shape, an impossible value or a place outside its return's is refused
    by name, before a value of it reaches a table.

    The engagement folder is synced, so a line another machine wrote is
    not trusted to be well formed: a ``rules_changed`` whose ``rules`` holds
    a string, a ``scanned`` whose statuses are a list. Left to the writers
    below, such a line surfaces as an AttributeError inside discovery and
    ends the whole practice's pass before one document is filed. Refused
    here it is one folder's problem, said in a sentence that names the
    line, and the pass goes on to the next engagement.

    **The record is untrusted input** (decision 187). A line of the right
    shape is still obeyed: a count is stored in a column SQLite bounds, a
    date is parsed by every reader, a Date Pattern is run over a client's
    pages, a step is carried out on the disk. So every value is held to the
    value rule (``tracker.records``: the bounds the editor holds a person
    to) and every location to the layout's rule for where a step of this
    return may act (``tracker.layout.place_problem``, asked at call time as
    this module already asks the layout); a household or return label must
    be one folder name (``layout.segment_problem``), because a label is
    joined onto a path; and a household's record, which has no steps,
    carries no ``moving`` line. This is the one admission, run by
    :func:`record` before anything is appended, by :func:`_apply` on every
    line read in and by :func:`check` over every journal. Each refusal names
    the field and the class of problem and never quotes the value, which is
    whatever the line said (security principle 7).

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
    from tracker import layout, reasons

    name = event.get(ledger.EVENT_KEY)

    # The event's name is said only when it is one this version knows: an
    # unknown one is whatever the line said (security principle 7).
    known = name if name in ledger.EVENTS | ledger.RETIRED_EVENTS else UNKNOWN_EVENT

    def refuse(problem: str) -> None:
        raise StoreError(MALFORMED_LINE.format(where=where, seq=seq, event=known, problem=problem))

    def a_place(field: str, location: object, *, writes: bool, what: str = "a step",
                removes: bool = False) -> None:
        if (problem := records.name_problem(location)):
            refuse(f"carries {what} whose {field!r} {problem}")
        if (code := layout.place_problem(where, str(location), writes=writes,
                                         removes=removes)) is not None:
            refuse(f"carries {what} whose {field!r} is outside this return's places ({code})")

    def a_segment(field: str, label: object) -> None:
        if label in (None, ""):
            return
        if (problem := records.text_problem(label)):
            refuse(f"carries {field!r} that {problem}")
        if (code := layout.segment_problem(str(label))) is not None:
            refuse(f"carries {field!r} that is not one folder name ({code})")

    def a_code(field: str, code: object, what: str) -> None:
        # A cause's code is read by the letter, its holds and the review
        # card (decision 190), so it is one this version names, or none.
        if code and code not in reasons.KNOWN_CODES:
            refuse(f"carries {what} whose {field!r} is not a cause's code")

    def a_row(row: dict) -> None:
        if problem := records.entry_problem(row):
            refuse(f"carries a row whose {problem}")
        a_code("code", row.get("code"), "a row")
        # The client's subfolder is written as the record keeps a name
        # (decision 190, layout.recorded_name), one folder name per part
        # (decision 187's one name rule, layout.segment_problem): a part
        # either would change, "/", "." or ".." among them, is a name no
        # writer wrote - the filer joins Path.parts with a backslash.
        subfolder = row.get("subfolder")
        if subfolder and any(layout.segment_problem(part) is not None or layout.recorded_name(part) != part
                             for part in str(subfolder).split("\\")):
            refuse("carries a row whose 'subfolder' is not a name as the record keeps one")
        for field in ("pbc_location", "prepared_location", "container"):
            if row.get(field):
                a_place(field, row[field], writes=False, what="a row")
        for part in str(row.get("also_filed") or "").split(records.CANDIDATE_SEP):
            if part.strip():
                a_place("also_filed", part.strip(), writes=False, what="a row")

    if ledger.AT_KEY in event and (problem := records.stamp_problem(event[ledger.AT_KEY])):
        refuse(f"carries {ledger.AT_KEY!r} that {problem}")
    # A person's word that a folder's name is accepted (decision 188): on
    # the two events that name a household or a return, with the one value.
    if ledger.ACCEPTED_KEY in event and (
            name not in (ledger.RULES_CHANGED, ledger.HOUSEHOLD_CHANGED)
            or event[ledger.ACCEPTED_KEY] != ledger.FOLDER_NAME_ACCEPTED):
        refuse(f"carries {ledger.ACCEPTED_KEY!r} that is not a folder's name accepted")
    if problem := _line_keys_problem(event):
        refuse(problem)
    if name in (ledger.RULES_CHANGED, ledger.RULES_IMPORTED):
        rows = event.get(ledger.RULES_KEY)
        if rows is not None and not isinstance(rows, list):
            refuse(f"carries {ledger.RULES_KEY!r} that is not a list")
        for row in rows or []:
            if not isinstance(row, dict):
                refuse("carries a rule that is not a row")
            # A list field that is not a list of words (decision 137, L4):
            # a string there would be read as one keyword per letter.
            for field_name in sorted(RULE_LIST_FIELDS):
                if problem := records.word_list_problem(row.get(field_name)):
                    refuse(f"carries a rule whose {field_name!r} {problem}")
            if problem := records.rule_row_problem(row):
                refuse(f"carries a rule whose {problem}")
        removed = event.get(ledger.REMOVED_KEY)
        if removed is not None and not isinstance(removed, list):
            refuse(f"carries {ledger.REMOVED_KEY!r} that is not a list")
        for identifier in removed or []:
            if records.text_problem(identifier):
                refuse("names a removed identifier that is not one line of text")
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
            except (ValueError, TypeError, json.JSONDecodeError):
                refuse("carries people this version cannot read")
        if isinstance(info, dict):
            if problem := records.info_problem(info):
                refuse(f"carries details whose {problem}")
            a_segment("household", info.get("household"))
            a_segment("return_name", info.get("return_name"))
    elif name in ledger.ROW_EVENTS:
        # An index row (decision 137, L4). Its key is the row's identity and
        # its row is a mapping; left to the fold, a row that is a string or
        # a key that is missing ended the whole pass inside discovery.
        key = event.get(ledger.KEY_KEY)
        if not isinstance(key, str) or not key:
            refuse(f"carries no {ledger.KEY_KEY!r}")
        if problem := records.name_problem(key):
            refuse(f"carries {ledger.KEY_KEY!r} that {problem}")
        if not isinstance(event.get(ledger.ROW_KEY), dict):
            refuse(f"carries {ledger.ROW_KEY!r} that is not a row")
        leaving = event.get(ledger.WAS_KEY)
        if leaving is not None and records.name_problem(leaving):
            refuse(f"carries {ledger.WAS_KEY!r} that is not a location")
        a_row(event[ledger.ROW_KEY])
    elif name == ledger.SCANNED:
        statuses = event.get(ledger.STATUSES_KEY)
        if statuses is not None and not isinstance(statuses, dict):
            refuse(f"carries {ledger.STATUSES_KEY!r} that is not a mapping")
        for identifier, stored in (statuses or {}).items():
            if records.text_problem(identifier):
                refuse("carries a status for an identifier that is not one line of text")
            if not isinstance(stored, dict):
                refuse("carries a status that is not a mapping")
            if problem := records.status_problem(stored):
                refuse(f"carries a status whose {problem}")
            for code in records.split_codes(stored.get("note_codes")):
                a_code("note_codes", code, "a status")
    elif name == ledger.MOVING:
        # The intent is what a later pass will finish a half-made move
        # from, so its shape is checked here rather than trusted in the
        # middle of a recovery with a file already moved: the operations
        # are a list, each one names what it does, where from and - unless
        # it is a stand-down - where to, and the row it carries is a row.
        # Since decision 187 every place a step names is one this return's
        # steps may act in, and a household's record - which has no steps -
        # carries none.
        if kind == KIND_HOUSEHOLD:
            refuse("in a household's record, which has no steps")
        key = event.get(ledger.KEY_KEY)
        if key is not None and records.name_problem(key):
            refuse(f"carries {ledger.KEY_KEY!r} that is not one line of text")
        ops = event.get(ledger.OPS_KEY)
        if not isinstance(ops, list):
            refuse(f"carries {ledger.OPS_KEY!r} that is not a list")
        for op in ops:
            if not isinstance(op, dict):
                refuse("carries an operation that is not one")
            step = op.get(ledger.OP_KEY)
            if step not in (ledger.OP_MOVE, ledger.OP_COPY, ledger.OP_REMOVE):
                refuse("carries an operation this version does not know")
            if not isinstance(op.get(ledger.FROM_KEY), str):
                refuse(f"carries a {step} with no {ledger.FROM_KEY!r}")
            if step != ledger.OP_REMOVE and not isinstance(op.get(ledger.TO_KEY), str):
                refuse(f"carries a {step} with no {ledger.TO_KEY!r}")
            if not isinstance(op.get(ledger.DIGEST_KEY, ""), str):
                refuse(f"carries a {step} whose {ledger.DIGEST_KEY!r} is not text")
            if problem := records.digest_problem(op.get(ledger.DIGEST_KEY, "")):
                refuse(f"carries a {step} whose {ledger.DIGEST_KEY!r} {problem}")
            named = (ledger.FROM_KEY,) if step == ledger.OP_REMOVE else (ledger.FROM_KEY, ledger.TO_KEY)
            for field, (location, writes) in zip(named, ledger.op_ends(op), strict=True):
                a_place(field, location, writes=writes, removes=step == ledger.OP_REMOVE)
        row = event.get(ledger.ROW_KEY)
        if row is not None and not isinstance(row, dict):
            refuse(f"carries {ledger.ROW_KEY!r} that is not a row")
        if isinstance(row, dict):
            a_row(row)
        leaving = event.get(ledger.WAS_KEY)
        if leaving is not None and records.name_problem(leaving):
            refuse(f"carries {ledger.WAS_KEY!r} that is not a location")
        also = event.get(ledger.ALSO_KEY)
        if also is not None and not isinstance(also, list):
            refuse(f"carries {ledger.ALSO_KEY!r} that is not a list")
        for one in also or []:
            # What travels with the row is recorded as it stands, so it is
            # admitted as it stands - by this same rule, now.
            if not isinstance(one, dict) or one.get(ledger.EVENT_KEY) not in ledger.EVENTS:
                refuse(f"carries {ledger.ALSO_KEY!r} holding something that is not an event")
            _refuse_a_malformed_line(one, seq, where, kind=kind)
        reason = event.get(ledger.REASON_KEY)
        if reason is not None and records.text_problem(reason, long=True):
            refuse(f"carries {ledger.REASON_KEY!r} that is not text")
        # Decision 129's intent carried the events it would write into
        # another return's record. Decision 132 retired that: nothing ever
        # writes into another record, and an intent whose second half this
        # version cannot write must not be recovered as if it had none.
        if ALSO_IN in event:
            refuse(f"carries {ALSO_IN!r}, the other record's half of a decision 129 "
                   f"hand-over, which this version does not write; finish it with the "
                   f"version that began it")
    elif name == ledger.MOVE_ABANDONED:
        key = event.get(ledger.KEY_KEY)
        if not isinstance(key, str) or not key or records.name_problem(key):
            refuse(f"carries no {ledger.KEY_KEY!r}")
    elif name == ledger.RELEASED:
        # A release names the row it takes out and says where it went -
        # and carries no row, because there is none left to carry.
        if not isinstance(event.get(ledger.KEY_KEY), str) or not event.get(ledger.KEY_KEY):
            refuse(f"carries no {ledger.KEY_KEY!r}")
        if ledger.ROW_KEY in event:
            refuse(f"carries {ledger.ROW_KEY!r}; a release carries no row")
        if records.text_problem(event.get(ledger.REASON_KEY, ""), long=True):
            refuse(f"carries {ledger.REASON_KEY!r} that is not text")
    elif name in (ledger.KEYWORD_LEARNED, ledger.KEYWORD_UNLEARNED):
        for key in (ledger.IDENTIFIER_KEY, ledger.KEYWORD_KEY):
            value = event.get(key)
            if not isinstance(value, str):
                refuse(f"carries {key!r} that is not text")
            if not value:
                refuse(f"carries a blank {key!r}")
            if problem := records.text_problem(value):
                refuse(f"carries {key!r} that {problem}")
    elif name in (ledger.DRAFTED, ledger.DRAFT_APPROVED):
        # A week's draft (decision 118): what was asked and held, the file,
        # its fingerprint and the stage - each read back by the app - and,
        # on an approval, the fingerprint of the letter approved (decision
        # 190), which the pass compares.
        for key in (ledger.ASKED_KEY, ledger.HELD_KEY):
            if key in event and (problem := records.text_list_problem(event[key])):
                refuse(f"carries {key!r} that {problem}")
        for key in (ledger.FILE_KEY, ledger.FINGERPRINT_KEY, ledger.TEXT_FINGERPRINT_KEY):
            if key in event and (problem := records.text_problem(event[key])):
                refuse(f"carries {key!r} that {problem}")
        if event.get(ledger.STAGE_KEY) is not None and (
                problem := records.count_problem(event[ledger.STAGE_KEY], 0, records.MAX_STAGE)):
            refuse(f"carries {ledger.STAGE_KEY!r} that {problem}")
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
                refuse("names a member that is not text")
        # The feed list (decision 129). A feed naming no household or no
        # return line points at nothing a pass could resolve, so it is
        # refused here by the record's own reader rather than written into
        # a column the sort would later read as a route.
        if isinstance(household, dict) and "feeds" in household:
            try:
                feeds = records.feeds_from_json(household["feeds"])
            except (ValueError, TypeError, json.JSONDecodeError):
                refuse("carries feeds this version cannot read")
            for feed in feeds:
                a_segment("feeds.household", feed.household)
                a_segment("feeds.return_name", feed.return_name)
        if isinstance(household, dict):
            if problem := records.household_problem(household):
                refuse(f"carries details whose {problem}")
            a_segment("name", household.get("name"))
    elif name == ledger.SHARING_CONFIRMED:
        # The firm's word, dated, and nothing else (decision 126): the
        # stamp is the whole of it. A line carrying a payload is either a
        # newer version's or a hand-written one, and either way this
        # version would be storing something it cannot fold - so it is
        # refused by name here rather than silently kept in the events
        # table where a reader would later trust it.
        # The three keys the record itself writes on every line since
        # decision 159 (``ledger.LINE_KEYS``) are the line's, not a payload.
        if set(event) - {ledger.EVENT_KEY, ledger.AT_KEY} - ledger.LINE_KEYS:
            refuse("carries fields; it carries nothing")


def _apply(conn: sqlite3.Connection, engagement_id: int, events: list[dict], *, start: int) -> int:
    """Fold ``events`` into the engagement's tables. Returns the last seq used.

    The caller holds the transaction. The fold itself is
    :func:`tracker.ledger.apply` - the store loads what it holds into the
    shape that function folds, hands it one event at a time, and writes the
    result back - so an index replayed a line at a time here and one folded
    from the first line by a reader cannot come out different. The statuses
    are the exception (decision 138): ``ledger.Folded.statuses`` is keyed by
    the exact spelling, because the ledger imports nothing that could fold
    case, so a batch scanning ``A01``, ``a01`` and ``A01`` again would hold
    two entries and write the second scan's status last. What these events
    changed is taken instead from :func:`_recorded_statuses` - the rule
    :func:`check` holds the table to, one entry per ``identifier_key`` with
    the last scan's spelling and status - and upserted onto what the table
    already said, so the writer and the check cannot disagree.

    A keyword a person's filing taught is inserted as it is met and deleted
    again when a person takes it back (decision 113): the insert carries the
    line's own sequence number, so a word taught again comes back last -
    whether or not it was taken back first - which is the order
    ``tracker.ledger.apply`` folds it in for one spelling. :func:`check`
    holds the two to its own fold of the same lines, keyed by
    ``records.identifier_key`` as this table is (decision 136).

    An edit of the person's rules is written as it is met too: the rows it
    carries replace those identifiers, the ones it names as removed go,
    and the engagement's own columns follow, so a save costs one upsert per
    changed row rather than a rewrite of the list.
    """
    state = ledger.Folded(rows=_stored_rows(conn, engagement_id), statuses={})
    seqs = _stored_seqs(conn, engagement_id)
    status_seqs: dict[str, int] = {}
    where, kind = conn.execute("SELECT path, kind FROM engagements WHERE id = ?",
                               (engagement_id,)).fetchone()
    seq = start - 1
    for event in events:
        seq += 1
        _refuse_a_malformed_line(event, seq, where, kind=kind)
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
    for key, (identifier, stored) in _recorded_statuses(events).items():
        _write_status(conn, engagement_id, identifier, stored, status_seqs[key])
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

    The apply reads the journal again inside its transaction and applies
    from the store's applied seq as it is then (decision 135), so a reader
    that caught up part of this batch meanwhile has none of it re-applied.
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
    lines, _head, chain = ledger.read_with_chain(engagement_dir)
    already = len(lines)
    if already != row["applied_seq"]:
        raise StoreError(
            f"{engagement_dir.name}: the store has applied {row['applied_seq']} of the journal's "
            f"{already} line(s); sync() it before recording to it"
        )
    # The same count is not the same lines (decision 137, A3): a journal
    # rewritten to its own length would otherwise have this call's line
    # appended to it and its head blessed.
    _refuse_a_rewrite(conn, row, lines, chain, engagement_dir.name)
    if not events:
        return row["applied_seq"]
    # The one door in (decision 187): every event is admitted by the rule
    # every line read back is held to, before the first is appended - a
    # line the store would refuse is never put into the journal, where it
    # would sit ahead of the store and fail every later sync. What is
    # admitted is the line exactly as it will be written (decision 159,
    # ``ledger.line_of``: the event with its link, this machine's name and
    # the record's format), so the writer's name is held to the same rule
    # as every other value, at the same door.
    before = ledger.chain_at(chain, already)
    for number, event in enumerate(events, start=already + 1):
        line = ledger.line_of(event, before)
        try:
            _refuse_a_malformed_line(json.loads(line), number, row["path"], kind=row["kind"])
        except StoreError as exc:
            raise StoreError(f"{exc}; nothing was written") from None
        before = ledger.chain_link(before, line)
    # This machine vouches for the record as it is before a line is added
    # to it, and says how far it is about to take it (decision 159, the
    # intent): a run killed between these appends and the checkpoint's
    # advance leaves lines of this host that are this machine's own.
    #
    # The intent is exact (the review's M1): the chain after each line this
    # call will write, from the very bytes the append writes
    # (``ledger.intended_heads``), so a line forged later into the same
    # place is not mistaken for one of these. An append that fails - rather
    # than a run that is killed - trims the intent to the lines that did
    # reach the file.
    heads = ledger.intended_heads(ledger.chain_at(chain, already), list(events))
    with _beside(conn) as held:
        _prove_against_checkpoint(conn, row["path"], lines, chain, row=row, held=held)
        start, said = _intend(conn, row["path"], chain, already, heads, held=held)
    try:
        for event in events:
            ledger.append(engagement_dir, event)
    except Exception:
        try:
            written = max(0, len(ledger.read_events(engagement_dir)) - already)
        except ledger.LedgerError:
            written = 0
        _expect(conn, row["path"], start, said[:already - start + written])
        raise
    # What the journal holds past the store, not what this call was handed
    # (decision 135): the two are the same lines unless a reader caught up
    # some of them between the appends and this transaction, and a start
    # read before the appends would then apply those lines a second time.
    with _transaction(conn):
        return _catch_up(conn, None, engagement_dir, build=False)


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

    **By count, not by head.** It compares the number of lines the store
    has applied with the number the journal holds, whatever the stored head
    says - which is what repairs a store an earlier version left with a
    head that names a line it never applied (decision 135). A look that
    finds nothing to apply takes no lock; everything it writes from, it
    reads again inside its own transaction (:func:`_look_then_catch_up`).
    """
    return _look_then_catch_up(conn, root, engagement_dir, build=False)


def catch_up(conn: sqlite3.Connection, root: Path | str, engagement_dir: Path | str) -> int:
    """:func:`sync` for an engagement the store holds, a first build for
    one it does not. Returns the applied seq.

    The full catch-up the filer's ``ensure()`` runs at the start of
    every pass (decision 135): it parses the journal and compares by count,
    so a store whose head matches while its applied seq is short is
    repaired by the next pass rather than refusing it for the rest of the
    season. A pass parses the journal anyway, so this costs it one parse -
    and, when there is nothing to apply, no lock (:func:`_look_then_catch_up`).
    """
    return _look_then_catch_up(conn, root, engagement_dir, build=True)


def _look_then_catch_up(conn: sqlite3.Connection, root: Path | str, engagement_dir: Path | str,
                        *, build: bool) -> int:
    """:func:`_catch_up` behind a look that takes no lock.

    ``filer.ensure()`` runs :func:`catch_up` after nearly every action in
    the app, for every engagement in the Status Report and for every dry
    run, and the pass's ``record()`` waits on the same immediate lock. So
    the row and the journal are read first **outside** any transaction,
    and when the store holds the engagement and has applied exactly as many
    lines as the journal holds, the answer is returned with no ``BEGIN
    IMMEDIATE`` at all (decision 135, review fix 2). A decision *not* to
    write, made on a look another process has since overtaken, writes
    nothing, and the line it missed is caught by the next call. Only a
    decision *to* write takes the lock, and it reads the row and the
    journal again inside (:func:`_catch_up`) - the look's lines are reused
    there only when the file still digests to the look's head, so the
    bytes are the same and the journal is parsed once. Healing by count is
    unchanged: a store whose head matches while its applied seq is short
    fails the look and is caught up.
    """
    row = _engagement_row(conn, engagement_dir, root)
    look = ledger.read_with_chain(engagement_dir)
    if row is not None and len(look[0]) == row["applied_seq"]:
        # Equal counts are "nothing to do" only when they are the same
        # lines (decision 137, A3; SPEC-135's no-lock look): a journal
        # rewritten to its own length is refused here, and nothing is
        # written, exactly as it is inside the transaction.
        _refuse_a_rewrite(conn, row, look[0], look[2],
                          engagement_path(key_root(engagement_dir, root), engagement_dir))
        return row["applied_seq"]
    with _transaction(conn):
        return _catch_up(conn, root, engagement_dir, build=build, known=look)


def _catch_up(conn: sqlite3.Connection, root: Path | str | None, engagement_dir: Path | str,
              *, build: bool, known: tuple[list[dict], str, list[str]] | None = None) -> int:
    """:func:`_catching_up`, with this machine's checkpoint open once for
    the proof before and the vouching after (decision 159)."""
    with _beside(conn) as held:
        return _catching_up(conn, root, engagement_dir, build=build, known=known, held=held)


def _catching_up(conn: sqlite3.Connection, root: Path | str | None, engagement_dir: Path | str,
                 *, build: bool, known: tuple[list[dict], str, list[str]] | None,
                 held: sqlite3.Connection | None) -> int:
    """Apply what the journal holds past the store. The caller holds the transaction.

    **One read, inside the transaction** (decision 135). The row, the
    journal's lines and the journal's head are all read here, after the
    caller's ``BEGIN IMMEDIATE``, and the lines and the head come from the
    same bytes (:func:`tracker.ledger.read_with_head`). Readers take no
    lock, and the app and the pass share this store: a row or a slice of
    lines read before waiting on another process's transaction is a
    picture of before that transaction, and applying it afterwards re-files
    a row under a line the journal has already overtaken, then saves a
    head that says nothing is missing. Read inside, nothing can land
    between the look and the write - every writer of the store is behind
    the same immediate lock - and a line appended to the journal after the
    read is simply not applied yet, with a head that says so.

    ``build`` is what an engagement the store does not hold gets: a first
    build from the lines (a reader's top-up, :func:`catch_up`) or the
    refusal :func:`sync` and :func:`record` give. A refusal raised here
    rolls the caller's transaction back, and nothing was written.

    ``known`` is the look :func:`_look_then_catch_up` made outside; it
    saves a second parse of the same bytes and nothing else - the file is
    read here all the same (:func:`tracker.ledger.read_with_chain`).

    **The prefix is proved before the tail is replayed** (decision 137,
    A3). The store keeps the chain over the lines it has applied
    (``applied_digest``); the chain over the same number of lines of the
    journal read now must equal it, or the journal was rewritten behind the
    store's back and nothing is applied (:func:`_refuse_a_rewrite`). It is
    never repaired here: a rebuild is the answer, after the check.
    """
    engagement_dir = Path(engagement_dir)
    row = _engagement_row(conn, engagement_dir, root)
    events, head, chain = ledger.read_with_chain(engagement_dir, known=known)
    if row is None:
        rel = engagement_path(key_root(engagement_dir, root), engagement_dir)
        if not build:
            raise StoreError(f"{rel}: the store does not hold this engagement; rebuild it")
        # A first build trusts nothing the store kept, because there is
        # nothing: the record is held to this machine's checkpoint first
        # (decision 159), which survives the store being deleted.
        foreign = _prove_against_checkpoint(conn, rel, events, chain, held=held)
        defaults = _new_engagement_defaults()
        cursor = conn.execute(
            f"INSERT INTO engagements ({_NEW_ENGAGEMENT_COLUMNS}) "
            f"VALUES ({_marks(len(defaults) + 5)})",
            (rel, *defaults, head, len(events), ledger.chain_at(chain, len(events)), ledger.stamp()),
        )
        if events:
            _apply(conn, cursor.lastrowid, events, start=1)
        _vouch_for(conn, rel, events, chain, foreign, held=held)
        return len(events)
    # A journal shorter than the store applied is said first in decision
    # 188's sentence, which says to restore it before anything else and
    # how many lines a rebuild would lose; then the checkpoint's refusals
    # (decision 159), which survive a rebuild of the store where the
    # store's own below do not.
    applied = row["applied_seq"]
    if len(events) < applied:
        rel = engagement_path(key_root(engagement_dir, root), engagement_dir)
        raise StoreError(TRUNCATED.format(engagement=rel, n=len(events), m=applied,
                                          k=applied - len(events)))
    foreign = _prove_against_checkpoint(conn, row["path"], events, chain, row=row, held=held)
    _refuse_a_rewrite(conn, row, events, chain,
                      engagement_path(key_root(engagement_dir, root), engagement_dir))
    if len(events) == applied:
        return applied
    seq = _apply(conn, row["id"], events[applied:], start=applied + 1)
    conn.execute(
        "UPDATE engagements SET applied_seq = ?, ledger_head = ?, applied_digest = ? WHERE id = ?",
        (seq, head, ledger.chain_at(chain, seq), row["id"]),
    )
    _vouch_for(conn, row["path"], events, chain, foreign, held=held)
    return seq


#: What the store says of a journal whose applied lines no longer chain to
#: the digest it kept (decision 137, A3). The same shape as the refusal of a
#: truncated journal: what happened, that nothing was applied, what to do.
REWRITTEN = ("The record for {rel} was changed behind the tracker's back (line {line} onward "
             "no longer matches). Nothing was applied. " + ledger.RUN_RECOVER)


def _only_the_store_holds(conn: sqlite3.Connection, engagement_id: int, events: list[dict]) -> bool:
    """Whether the store's own copy of the record's lines holds a line the
    record now lacks, or holds one differently - what a rebuild would drop
    without anybody having exported it."""
    for one in conn.execute("SELECT seq, payload FROM events WHERE engagement_id = ?", (engagement_id,)):
        seq = one["seq"]
        if seq > len(events) or one["payload"] != json.dumps(events[seq - 1], ensure_ascii=False,
                                                              sort_keys=True):
            return True
    return False


def _rewritten_from(conn: sqlite3.Connection, engagement_id: int, events: list[dict],
                    applied: int) -> int:
    """The first applied line whose event the store holds differently, by
    the events table's own copy - or 1 when the lines differ only in their
    bytes (a key reordered, a space), which the table cannot tell apart."""
    stored = conn.execute("SELECT seq, payload FROM events WHERE engagement_id = ? ORDER BY seq",
                          (engagement_id,)).fetchall()
    held = {one["seq"]: one["payload"] for one in stored}
    for seq, event in enumerate(events[:applied], start=1):
        if held.get(seq) != json.dumps(event, ensure_ascii=False, sort_keys=True):
            return seq
    return 1


def _refuse_a_rewrite(conn: sqlite3.Connection, row: sqlite3.Row, events: list[dict],
                      chain: list[str], rel: str) -> None:
    """Refuse, by :data:`REWRITTEN`, a journal whose first ``applied_seq``
    lines are not the lines the store applied (decision 137, A3).

    The chain over those lines as the file holds them now is compared with
    the one the store kept. A journal shorter than that is the truncation
    the callers already refuse, and is left to them."""
    applied = row["applied_seq"]
    if len(events) < applied:
        return
    if ledger.chain_at(chain, applied) == row["applied_digest"]:
        return
    raise StoreError(REWRITTEN.format(rel=rel, line=_rewritten_from(conn, row["id"], events, applied)))


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

    **By head, and only the fast path outside a transaction** (decision
    135). The digest check only reads, and a matching head is proof
    because no writer saves a head that is ahead of its lines. Anything
    else is :func:`catch_up`: a look with no lock, and - only when there
    is something to apply - the row and the journal read again inside its
    own transaction, since another process may have built or advanced the
    rows while this one waited for the lock.
    """
    row = _engagement_row(conn, engagement_dir, root)
    # The journal's digest first, and the lines only if it moved: this
    # runs before every read, and parsing a season of events to learn
    # that nothing has happened is the cost the store exists to remove.
    if row is not None and row["ledger_head"] == ledger.head(engagement_dir):
        return row["applied_seq"]
    return catch_up(conn, root, engagement_dir)


# ------------------------------------------------------- the checkpoint ----

#: The checkpoint's refusals (decision 159, §4.3). Each says what happened,
#: that nothing was applied, and what a person does - and each is a
#: StoreError, so the pass names it as that return's problem and goes on.
SHORTER = ("The record for {rel} is shorter than this machine last saw it ({n} of {count} lines). "
           "Nothing was applied. " + ledger.RUN_RECOVER)
REWRITTEN_SINCE = ("The record for {rel} no longer matches what this machine last saw from {line} "
                   "onward. Nothing was applied. " + ledger.RUN_RECOVER)
#: Where the rewrite starts when the store holds no copy to find it by.
AN_EARLIER_LINE = "an earlier line"
CLAIMS_THIS_MACHINE = ("Line {n} of the record for {rel} says it was written on this machine, and "
                       "this machine did not write it. Nothing was applied. " + ledger.RUN_RECOVER)
NO_WRITER = ("Line {n} of the record for {rel} carries no writer - written by an older version of "
             "the tracker or by hand. Nothing was applied. " + ledger.RUN_RECOVER)
FOREIGN = ("Line {n} of the record for {rel} was written on {host}; this machine is the one that "
           "writes (decision 159). Nothing was applied. " + ledger.RUN_RECOVER)
#: What a rebuild says instead of losing what the checkpoint vouches for.
REBUILD_WOULD_LOSE = ("The record for {rel} does not match what this machine last saw; rebuild "
                      "would lose that. " + ledger.RUN_RECOVER)
#: The settings name a root this machine's checkpoint does not belong to
#: (decision 159, E5).
ROOT_NOT_CLAIMED = ("this machine's record checkpoint belongs to {claimed}; this was asked to work in "
                    "{now}. "
                    "If the clients root really moved, see runbook 'If the clients root moves'.")


def _checkpoint_file(conn: sqlite3.Connection) -> Path | None:
    """The checkpoint beside the store ``conn`` is open on, or None for a
    store that is not a file."""
    for row in conn.execute("PRAGMA database_list"):
        if row[1] == "main":
            return checkpoint.path_for(row[2]) if row[2] else None
    return None


@contextmanager
def _beside(conn: sqlite3.Connection, held: sqlite3.Connection | None = None):
    """The checkpoint beside ``conn``'s store, opened for one question and
    closed after it - or ``held``, when the caller already has it open for
    several (a catch-up proves, applies, then vouches: one open). None for
    a store that is not a file."""
    if held is not None:
        yield held
        return
    where = _checkpoint_file(conn)
    if where is None:
        yield None
        return
    try:
        opened = checkpoint.open(where)
    except checkpoint.CheckpointError as exc:
        # One return's problem, said by name (the review's S4).
        raise StoreError(str(exc)) from None
    try:
        yield opened
    except checkpoint.CheckpointError as exc:
        # A read or a write that failed after the open (the rebase review's
        # MF1): the same return's problem, in the same sentence.
        raise StoreError(str(exc)) from None
    finally:
        try:
            opened.close()
        except checkpoint.CheckpointError as exc:
            log.warning("Could not close the record checkpoint (%s)", exc.code
                        if isinstance(exc, checkpoint.CheckpointUnavailable) else type(exc).__name__)


@dataclass
class _Judgment:
    """What the checkpoint makes of a record read now (decision 159): the
    kind of refusal (empty for none), the line it is about, and the lines
    another machine wrote that are accepted."""

    kind: str = ""
    seq: int = 0
    host: str = ""
    foreign: list[tuple[int, str, str]] = _default(default_factory=list)
    problem: str = ""


_SHORTER, _REWRITTEN, _CLAIMS, _NO_WRITER, _FOREIGN = "shorter", "rewritten", "claims", "no writer", "foreign"
#: A line past the checkpoint whose writer or link the gate's rule refuses
#: (decision 187): judged by nobody, refused as the gate refuses it.
_MALFORMED = "malformed"


def _judge(vouched: tuple[int, str], intent: checkpoint.Intent | None, events: list[dict],
           chain: list[str]) -> _Judgment:
    """The one judgment of a record against this machine's checkpoint -
    the pass's and :func:`verify`'s alike (the review's S3), so neither has
    a copy of the rule.

    - **Shorter** than the lines vouched for; **rewritten**: the chain
      through them is not the one kept.
    - **Longer:** a line naming this machine (``locking.is_this_host``,
      any case - the review's S1) is its own only when it is exactly one of
      the lines the intent said it would write (:meth:`Intent.owns`);
      otherwise it **claims** this machine. A line naming no host has **no
      writer**. A line naming another host is accepted and named unless
      :func:`tracker.checkpoint.foreign_lines_refused` says otherwise.
    """
    count, head = vouched
    if len(events) < count:
        return _Judgment(_SHORTER, count)
    if ledger.chain_at(chain, count) != head:
        return _Judgment(_REWRITTEN, count)
    foreign = []
    for seq in range(count + 1, len(events) + 1):
        # The gate's rule of a writer first (decisions 159 and 187): a
        # name it refuses - ``"VM "`` on the machine ``vm`` - is neither
        # this machine's nor another's, and is never named for a person.
        if problem := _line_keys_problem(events[seq - 1]):
            return _Judgment(_MALFORMED, seq, problem=problem)
        host = events[seq - 1].get(ledger.HOST_KEY)
        if is_this_host(host):
            if intent is None or not intent.owns(seq, ledger.chain_at(chain, seq)):
                return _Judgment(_CLAIMS, seq)
        elif not isinstance(host, str) or not host:
            return _Judgment(_NO_WRITER, seq)
        elif checkpoint.foreign_lines_refused():
            return _Judgment(_FOREIGN, seq, host)
        else:
            foreign.append((seq, host, str(events[seq - 1].get(ledger.AT_KEY, ""))))
    return _Judgment(foreign=foreign)


def _prove_against_checkpoint(conn: sqlite3.Connection, key: str, events: list[dict],
                              chain: list[str], *, row: sqlite3.Row | None = None,
                              held: sqlite3.Connection | None = None,
                              ) -> list[tuple[int, str, str]]:
    """Hold the record to what this machine last saw of it (decision 159).

    Called before any line is applied - by every catch-up, a first build,
    :func:`record` before it appends, and :func:`rebuild_engagement` - with
    the lines and their chain from the one read the caller made. A record
    never seen seeds the checkpoint as it is - the moment of trust, logged.
    Otherwise :func:`_judge` decides, and a refusal is raised by its
    sentence. Returns the lines past the checkpoint that another machine
    wrote, for :func:`_vouch_for` to record once they are applied.
    """
    with _beside(conn, held) as held:
        if held is None:
            return []
        vouched = checkpoint.vouched(held, key)
        if vouched is None:
            checkpoint.advance(held, key, len(events), ledger.chain_at(chain, len(events)), seeded=True)
            log.warning("checkpoint seeded for %s at %d line(s)", key, len(events))
            return []
        judged = _judge(vouched, checkpoint.intent(held, key), events, chain)
    if judged.kind == _SHORTER:
        raise StoreError(SHORTER.format(rel=key, n=len(events), count=judged.seq))
    if judged.kind == _REWRITTEN:
        # N2: the first line the store's own copy holds differently, when it
        # holds one; else no line number is claimed that is not known.
        line = (f"line {_rewritten_from(conn, row['id'], events, judged.seq)}" if row is not None
                else AN_EARLIER_LINE)
        raise StoreError(REWRITTEN_SINCE.format(rel=key, line=line))
    if judged.kind == _CLAIMS:
        raise StoreError(CLAIMS_THIS_MACHINE.format(n=judged.seq, rel=key))
    if judged.kind == _MALFORMED:
        name = events[judged.seq - 1].get(ledger.EVENT_KEY)
        known = name if name in ledger.EVENTS | ledger.RETIRED_EVENTS else UNKNOWN_EVENT
        raise StoreError(MALFORMED_LINE.format(where=key, seq=judged.seq, event=known,
                                               problem=judged.problem))
    if judged.kind == _NO_WRITER:
        raise StoreError(NO_WRITER.format(n=judged.seq, rel=key))
    if judged.kind == _FOREIGN:
        raise StoreError(FOREIGN.format(n=judged.seq, rel=key, host=judged.host))
    return judged.foreign


def _vouch_for(conn: sqlite3.Connection, key: str, events: list[dict], chain: list[str],
               foreign: list[tuple[int, str, str]], *,
               held: sqlite3.Connection | None = None) -> None:
    """After the lines are applied: record the lines another machine wrote,
    and vouch for the whole record - as written here when this machine
    wrote its last line, as taken on trust otherwise."""
    with _beside(conn, held) as held:
        if held is None:
            return
        if foreign:
            checkpoint.note_foreign(held, key, foreign)
        last_host = events[-1].get(ledger.HOST_KEY) if events else None
        checkpoint.advance(held, key, len(events), ledger.chain_at(chain, len(events)),
                           seeded=not is_this_host(last_host))


def _intend(conn: sqlite3.Connection, key: str, chain: list[str], already: int, heads: list[str], *,
            held: sqlite3.Connection | None = None) -> tuple[int, list[str]]:
    """Say what :func:`record` is about to write: from the count this
    machine vouches for, the chain after each line already proved its own
    but not yet vouched for (an earlier batch a killed run left), then
    ``heads``. A new intent never disowns lines an earlier one owned.
    Returns the start and the heads said."""
    with _beside(conn, held) as held:
        if held is None:
            return already, heads
        vouched = checkpoint.vouched(held, key)
        start = min(vouched[0], already) if vouched is not None else already
        said = [ledger.chain_at(chain, seq) for seq in range(start + 1, already + 1)] + list(heads)
        checkpoint.expect(held, key, start, said)
        return start, said


def _expect(conn: sqlite3.Connection, key: str, start: int, heads: list[str], *,
            held: sqlite3.Connection | None = None) -> None:
    """:func:`tracker.checkpoint.expect`, beside this store."""
    with _beside(conn, held) as held:
        if held is not None:
            checkpoint.expect(held, key, start, heads)


def prove_the_root(root: Path | str, *, claim: bool = True) -> None:
    """Refuse a clients root this machine's checkpoint does not belong to
    (decision 159, E5); claim it on first use when ``claim``.

    **The one proof of a root** (the review's S2): the pass asks it of the
    root it is about to walk, whether the settings named it or a person
    typed it, and every writing command of the app of the settings' root.
    **Only the settings' root claims** (the final review's SF1): the pass
    proves a typed root with ``claim=False``, so a first pass typed on one
    client's folder claims nothing and cannot lock out the scheduled one.
    Keys are relative to the root, so a copy of the root elsewhere would
    otherwise read as the same records and advance the same rows; the
    refusal names both folders and the runbook's move procedure
    (``python -m tracker.checkpoint <store> move-root <new root>``). The
    claimed root itself, or a folder inside it (one client's folder run by
    hand), is not a copy - asked of the layout (decision 188), which alone
    says whether one folder lies under another.
    A checkpoint that will not open is refused by name (the review's S4) -
    and **left as the checkpoint's own error** (``checkpoint.CheckpointError``,
    busy or unreadable; the rebase review's SF1), never turned into this
    function's :class:`StoreError`, which means only "not the root this
    machine's checkpoint belongs to": the caller says each state in its own
    sentence.
    """
    from tracker import layout

    now = Path(root).resolve()
    where = checkpoint.path_for(store_path())
    if not claim and not where.is_file():
        return
    with checkpoint.opened(where) as held:
        claimed = checkpoint.claim_root(held, str(now)) if claim else checkpoint.root_of(held)
    # Whether the root is the claimed one or inside it is decision 188's
    # one question of a path under another (``layout.parts_below``); only
    # whether this machine's checkpoint belongs to it is this function's.
    if claimed is not None and layout.parts_below(Path(claimed), now) is None:
        raise StoreError(ROOT_NOT_CLAIMED.format(claimed=claimed, now=now))


def foreign_lines() -> list[checkpoint.Foreign]:
    """Every line written on another machine that this machine accepted and
    no person has acknowledged yet (decision 159, C-1 (a)) - what the
    practice page names every pass. Creates nothing where there is no
    checkpoint yet."""
    where = checkpoint.path_for(store_path())
    if not where.is_file():
        return []
    with checkpoint.opened(where) as held:
        return checkpoint.unacknowledged(held)


def acknowledge_foreign(engagement_dir: Path | str) -> int:
    """A person has looked at the lines another machine wrote in one
    record: they stop being named. Returns how many. The caller holds the
    return's lock (the API's writing command does)."""
    conn = connect()
    row = _engagement_row(conn, engagement_dir)
    key = row["path"] if row is not None else engagement_path(key_root(engagement_dir), engagement_dir)
    with checkpoint.opened(checkpoint.path_for(store_path())) as held:
        return checkpoint.acknowledge(held, key)


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


#: What a journal shorter than what the store applied is told (SPEC-162
#: ruling 5, kept by decision 188): restore first, and what a rebuild
#: would lose. It replaces "rebuild the engagement", which discarded them.
TRUNCATED = ("The journal of `{engagement}` holds fewer lines than the store has applied "
             "(the journal {n}, the store {m}). First restore the journal from Drive's trash or "
             "version history. `rebuild` would discard the {k} line(s) only the store still holds. "
             + ledger.RUN_RECOVER)
#: What the check says of a stored engagement whose journal is gone.
JOURNAL_GONE = ("The store holds {n} line(s) for `{engagement}` and its record is not there. "
                f"Restore `{ledger.LEDGER_FILENAME}` from Drive's trash or version history.")
#: What a rebuild that would discard lines only the store holds is told
#: (SPEC-162 ruling 6): nothing is discarded silently.
WOULD_DISCARD = ("`{engagement}`: the store holds {k} line(s) the journal does not; rebuild would "
                 "discard them (listed above). Nothing was changed. " + ledger.RUN_RECOVER)
#: A recover whose export could not be written (the port review's S2): by
#: the error's class and the export's folder, and nothing was discarded.
EXPORT_NOT_WRITTEN = ("the export could not be written into {folder} ({kind}); nothing was "
                      "discarded and nothing was changed")
#: How each such line is listed before that sentence.
DISCARDED_LINE = "  {kind}  {document}  {date}"


class WouldDiscard(StoreError):
    """A rebuild refused because it would discard lines only the store
    holds; ``lines`` lists them (:data:`DISCARDED_LINE`)."""

    def __init__(self, message: str, lines: list[str]) -> None:
        super().__init__(message)
        self.lines = lines


def only_in_the_store(conn: sqlite3.Connection, root: Path | str,
                      engagement_dir: Path | str) -> list[str]:
    """The lines the store applied that the journal no longer holds at all -
    a journal cut short, or gone - each as :data:`DISCARDED_LINE`, from the
    store's own copy of every applied line. Empty where the journal holds
    at least as many lines as the store applied: a journal rewritten to the
    same length still holds its lines, and decision 137's check-then-rebuild
    is its answer (``REWRITTEN``)."""
    row = _engagement_row(conn, engagement_dir, root)
    if row is None:
        return []
    events, _head, _chain = ledger.read_with_chain(engagement_dir)
    if row["applied_seq"] <= len(events):
        return []
    stored = conn.execute("SELECT seq, payload FROM events WHERE engagement_id = ? ORDER BY seq",
                          (row["id"],)).fetchall()
    lines = []
    for one in stored:
        if one["seq"] <= len(events):
            continue
        event = json.loads(one["payload"])
        document = (event.get(ledger.ROW_KEY) or {}).get("original_name", "") \
            if isinstance(event.get(ledger.ROW_KEY), dict) else ""
        lines.append(DISCARDED_LINE.format(kind=event.get(ledger.EVENT_KEY, ""),
                                           document=document or "-",
                                           date=event.get(ledger.AT_KEY, "")))
    return lines


def gone_journals(conn: sqlite3.Connection, root: Path | str) -> list[str]:
    """:data:`JOURNAL_GONE` for every engagement the store holds under
    ``root`` whose journal (``ledger.LEDGER_FILENAME``) is not there
    (SPEC-162 ruling 5): a walk of the root cannot find a record that is
    gone, so the store's own list is asked. Only rows keyed by their place
    below the root - a household's or a return's, by the layout's parser -
    are judged; a row keyed some other way names no folder under it."""
    from tracker import layout

    said = []
    for row in conn.execute("SELECT path, applied_seq FROM engagements ORDER BY path"):
        if layout.place_of("", row["path"]).kind not in (layout.HOUSEHOLD, layout.RETURN):
            continue
        folder = Path(root) / row["path"]
        if not ledger.path_for(folder).exists():
            said.append(JOURNAL_GONE.format(n=row["applied_seq"], engagement=row["path"]))
    return said


def rebuild_engagement(
    conn: sqlite3.Connection,
    root: Path | str,
    engagement_dir: Path | str,
    *,
    discard: bool = False,
) -> list[str]:
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

    **Never discards silently** (SPEC-162 ruling 6, kept by decision 188).
    Where the store holds lines the journal does not - a journal truncated,
    replaced or gone - a rebuild would lose them, so it is refused with
    :class:`WouldDiscard`, which lists them. The answer to a lost journal
    is Drive's trash or version history, never a rebuild.

    **Compare, then replay** (decision 159, G-2). Before a row is deleted
    the record is held to this machine's checkpoint: a record shorter than
    what it vouches for, rewritten under it, or carrying a line that claims
    this machine and that this machine did not write is refused
    (:data:`REBUILD_WOULD_LOSE`), because the store about to be deleted may
    be the only other copy of what was lost. A record the reader refuses (a
    broken link) raises the reader's own refusal.

    **A loss is accepted only by the return's name, typed** (the council's
    Solution 3, approved by Jason; the port review's M1). ``discard`` is the
    one way past both refusals, and only :func:`recover` passes it - after
    its export and its difference, and only when the return folder's own
    name was typed exactly; it then returns what it discarded, and the
    checkpoint is seeded again from the record as it is. This narrows
    decision 188's ``--discard``: on the command line it is
    ``rebuild --engagement <return> --discard --accept-loss "<its name>"``,
    which is recover's own path, and without ``--engagement`` or the name
    it is refused. Nothing a person does not type discards a line.
    """
    engagement_dir = Path(engagement_dir)
    rel = engagement_path(key_root(engagement_dir, root), engagement_dir)
    lost = only_in_the_store(conn, root, engagement_dir)
    if lost and not discard:
        raise WouldDiscard(WOULD_DISCARD.format(engagement=rel, k=len(lost)), lost)
    built_at = ledger.stamp()
    with _transaction(conn), ExitStack() as stack:
        # The lines and their head from one read, inside the transaction
        # (decision 135): a line a writer records while this waits for the
        # lock is in the rows, not only in the head.
        events, head, chain = ledger.read_with_chain(engagement_dir)
        known = _engagement_row(conn, engagement_dir, root)
        # Asked of this record's own row: a row a wider root's tail-match
        # found under another key is another record's lines.
        if (not discard and known is not None and known["path"] == rel
                and _only_the_store_holds(conn, known["id"], events)):
            # Never delete rows that have not been exported (the final
            # review's MF2): whatever the checkpoint says - no row at all
            # included - a store holding a line the record lacks or holds
            # differently is recover's to export first.
            raise StoreError(REBUILD_WOULD_LOSE.format(rel=rel)
                             + " (the store holds lines the record does not)")
        held = stack.enter_context(_beside(conn))
        if discard and held is not None:
            checkpoint.forget(held, rel)
        try:
            foreign = _prove_against_checkpoint(conn, rel, events, chain, held=held,
                                                row=_engagement_row(conn, engagement_dir, root))
        except StoreError as exc:
            raise StoreError(REBUILD_WOULD_LOSE.format(rel=rel) + f" ({exc})") from exc
        # The children go with it: every table references the engagement
        # with ON DELETE CASCADE and foreign keys are on, so one delete is
        # the whole of "forget what you knew about this folder".
        known = _engagement_row(conn, engagement_dir, root)
        if known is not None:
            conn.execute("DELETE FROM engagements WHERE id = ?", (known["id"],))
        defaults = _new_engagement_defaults()
        # The applied chain is computed as the lines are replayed
        # (decision 137, A3): a rebuild is how an older store upgrades.
        cursor = conn.execute(
            f"INSERT INTO engagements ({_NEW_ENGAGEMENT_COLUMNS}) "
            f"VALUES ({_marks(len(defaults) + 5)})",
            (rel, *defaults, head, len(events), ledger.chain_at(chain, len(events)), built_at),
        )
        if events:
            _apply(conn, cursor.lastrowid, events, start=1)
        _vouch_for(conn, rel, events, chain, foreign, held=held)
    return lost


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

    **A request is one request whatever its case** (decision 136). The
    journal's own fold keys a status and a taught word by the spelling
    each line carries, because :mod:`tracker.ledger` sits below
    :mod:`tracker.records` and has no case rule; the store keys both by
    ``records.identifier_key``. So those two are folded again here, from
    the same lines, by the store's rule (:func:`_recorded_statuses`,
    :func:`_recorded_learned`) - otherwise a request the person retyped by
    case is two requests to the check and one to the store, and the gate
    names a disagreement no rebuild can clear. The lines are read once
    (:func:`tracker.ledger.read_with_head`, decision 135) and the same list
    is handed to the replay and to both folds, so no two of them can be
    looking at two different moments of the journal.
    """
    name = Path(engagement_dir).name
    rel = engagement_path(key_root(engagement_dir, root), engagement_dir)
    engagement = _engagement_row(conn, engagement_dir, root)
    # A journal that is gone is one sentence, not a list of every row the
    # store holds and the record does not (SPEC-162 ruling 5).
    if engagement is not None and not ledger.path_for(engagement_dir).exists():
        return [JOURNAL_GONE.format(n=engagement["applied_seq"], engagement=rel)]
    events, _head, chain = ledger.read_with_chain(engagement_dir)
    folded = ledger.replay(events)
    if engagement is None:
        return [f"{rel}: the store does not hold this engagement, and its record carries "
                f"{len(folded.rows)} index row(s) and {len(folded.rules)} request row(s)"]
    problems: list[str] = []
    applied = engagement["applied_seq"]
    if applied <= len(events) and ledger.chain_at(chain, applied) != engagement["applied_digest"]:
        # The applied chain (decision 137, A3): the lines the store applied
        # are not the lines the journal holds now.
        problems.append(REWRITTEN.format(
            rel=rel, line=_rewritten_from(conn, engagement["id"], events, applied)))
    problems += _check_documents(conn, engagement["id"], name, folded.rows)
    problems += _check_statuses(conn, engagement["id"], name, _recorded_statuses(events))
    problems += _check_rules(conn, engagement["id"], name, folded)
    problems += _check_intents(conn, engagement["id"], name, folded.intents)
    problems += _check_learned(conn, engagement["id"], name, _recorded_learned(events))
    problems += _check_household(conn, engagement["id"], name, folded.household)
    # Every line judged again by today's admission (decision 187), so a line
    # an earlier version applied that the rule now refuses is named on the
    # day of the upgrade, without deleting the store to find it.
    for seq, event in enumerate(events, start=1):
        try:
            _refuse_a_malformed_line(event, seq, engagement["path"], kind=engagement["kind"])
        except StoreError as exc:
            problems.append(str(exc))
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


def _recorded_statuses(events: list[dict]) -> dict[str, tuple[str, dict]]:
    """The record's status for each request, keyed as the store keys it
    (decision 136): ``identifier_key`` -> (the spelling the last scan used,
    what it recorded).

    Every ``scanned`` line in order, each identifier's status replacing
    whatever its key held, so the last write per request wins whichever
    case it was spelt in - the store's ``INSERT OR REPLACE`` by the folded
    key. It is also what :func:`_apply` writes for a batch of lines
    (decision 138), so the writer and the check read the one rule.
    """
    statuses: dict[str, tuple[str, dict]] = {}
    for event in events:
        if event.get(ledger.EVENT_KEY) == ledger.SCANNED:
            for identifier, status in (event.get(ledger.STATUSES_KEY) or {}).items():
                statuses[identifier_key(identifier)] = (identifier, status)
    return statuses


def _recorded_learned(events: list[dict]) -> dict[str, tuple[str, ...]]:
    """The words filings taught each request, keyed as the store keys it
    (decision 136), in the order they were taught.

    ``ledger._apply_keyword_event``'s rule applied per ``identifier_key``:
    a word taught is moved last, a word taken back is removed and a
    request left with none is dropped - which is the store's
    ``INSERT OR REPLACE ... seq`` read back ``ORDER BY seq``.
    """
    learned: dict[str, tuple[str, ...]] = {}
    for event in events:
        name = event.get(ledger.EVENT_KEY)
        if name not in (ledger.KEYWORD_LEARNED, ledger.KEYWORD_UNLEARNED):
            continue
        key = identifier_key(str(event.get(ledger.IDENTIFIER_KEY, "")))
        keyword = str(event.get(ledger.KEYWORD_KEY, ""))
        left = tuple(word for word in learned.get(key, ()) if word != keyword)
        if name == ledger.KEYWORD_LEARNED:
            learned[key] = left + (keyword,)
        elif left:
            learned[key] = left
        else:
            learned.pop(key, None)
    return learned


def _check_statuses(
    conn: sqlite3.Connection, engagement_id: int, name: str,
    recorded: dict[str, tuple[str, dict]],
) -> list[str]:
    stored = {row["identifier"]: row for row in conn.execute(
        "SELECT * FROM statuses WHERE engagement_id = ?", (engagement_id,))}
    problems = []
    for key, (identifier, status) in recorded.items():
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
    for key in sorted(set(stored) - set(recorded)):
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
    record's side is folded from the lines by the table's own rule
    (:func:`_recorded_learned`, decision 136): two spellings of one request
    are one list, in the order the words were taught, and a word taken
    back under either spelling is gone from it.
    """
    stored: dict[str, tuple[str, ...]] = {}
    for row in conn.execute(
        'SELECT "identifier", keyword FROM learned_keywords WHERE engagement_id = ? '
        "ORDER BY seq, keyword", (engagement_id,),
    ):
        stored[row["identifier"]] = stored.get(row["identifier"], ()) + (row["keyword"],)
    return [
        f"{name}: request {key}, the keywords filings taught: the store says "
        f"{list(stored.get(key, ()))!r}, the record says {list(recorded.get(key, ()))!r}"
        for key in sorted(set(stored) | set(recorded))
        if stored.get(key, ()) != recorded.get(key, ())
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
    """One spreadsheet, whole or not written (decision 155): through the
    one atomic replacement, flushed before it takes the name. Reached at
    call time - the store imports the record, the journal and the lock and
    nothing else at load time (decision 101), and this is the one file it
    writes that is not the database."""
    from tracker.fsio import atomic_replacement

    with atomic_replacement(path) as temp:
        with temp.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(header)
            for row in rows:
                writer.writerow([_as_text(value) for value in row])
            handle.flush()
            os.fsync(handle.fileno())


# ------------------------------------------------------------ recover ----

#: Where ``recover`` writes what it keeps, beside the store (decision 159):
#: the data home, never the client tree.
RECOVERED_DIR = "recovered"
#: The sides of a difference, as ``recover`` prints them.
ON_STORE, ON_RECORD, BOTH_DIFFERENT = "store", "record", "both-different"
#: What ``recover`` says when the record itself does not read. The program
#: never rewrites a record; restoring one is a person's act.
RECORD_DOES_NOT_READ = ("the record itself does not read ({problem}); nothing can be replayed "
                        "from it and nothing was changed. {restore} (runbook §6).")
#: Where to restore an unreadable record from - named only when it is a copy
#: worth restoring (the final review's MF3): the store's export holds every
#: line the record still reads, and more.
RESTORE_FROM_EXPORT = ("Compare it with {record_now} first; the store's export {export} holds every "
                       "line the record still reads, and may be copied over it")
#: Otherwise no file the tracker wrote is one to restore from.
NO_USABLE_COPY = ("This machine's store holds no copy of this return that covers what the record "
                  "still reads; restore from a conflict copy or the firm's off-drive copy, and ask "
                  "Jason")
ACCEPTED = "accepted: {n} line(s) the store had that the record does not"
WRONG_NAME = ("the loss is accepted only by the return's own folder name, typed exactly "
              "({given!r} is not it); nothing was changed")


@dataclass
class Difference:
    """One line the store and the record do not agree on - by its number,
    which side has it, and what kind of line it is. Never a payload value
    (principle 7): a forged line's text is exactly what must not be echoed."""

    seq: int
    side: str
    event: str
    at: str
    host: str


@dataclass
class Recovery:
    """What ``recover`` did, for the command line to say."""

    export: Path | None
    record_copy: Path | None
    differences: list[Difference]
    lost: int
    accepted: bool = False
    refusal: str = ""


def _store_file(conn: sqlite3.Connection) -> Path:
    for row in conn.execute("PRAGMA database_list"):
        if row[1] == "main" and row[2]:
            return Path(row[2])
    raise StoreError("this store is not a file; there is nowhere beside it to recover into")


def _exclusively(path: Path, data: bytes) -> Path:
    """Write ``data`` to a new file, never over one: the next free
    ``-1``, ``-2`` name when the second is taken."""
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate, n = path, 0
    while True:
        try:
            with candidate.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            return candidate
        except FileExistsError:
            n += 1
            candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")


def _described(payload: str | None) -> tuple[str, str, str]:
    """A line's event name, time and host, each shown only when it has the
    shape one of them has - so nothing a line carries is echoed as it is."""
    try:
        event = json.loads(payload) if payload is not None else None
    except (ValueError, RecursionError):
        event = None
    if not isinstance(event, dict):
        return "(does not read)", "", ""
    name = event.get(ledger.EVENT_KEY)
    at, host = event.get(ledger.AT_KEY), event.get(ledger.HOST_KEY)
    # The gate's own rules of a writer and a time (the review's S5; one
    # rule each, in ``records``, since decision 187). A line whose writer or
    # time fails its rule shows neither: the two are judged together.
    if host is None:
        return (name if name in ledger.EVENTS else "(unknown event)",
                at if not records.stamp_problem(at) else "?", "")
    written = not records.stamp_problem(at) and not records.host_problem(host)
    return (name if name in ledger.EVENTS else "(unknown event)",
            at if written else "?", host if written else "?")


def recover(conn: sqlite3.Connection, root: Path | str, engagement_dir: Path | str, *,
            accept_loss: str | None = None, now: dt.datetime | None = None) -> Recovery:
    """Compare, export, and replay only when the loss is accepted by name
    (decision 159, G-2). The runbook's recovery; what ``rebuild`` refuses
    to do silently.

    1. **Export first, always**: the store's copy of the return's lines -
       each payload is the writer's own line - and the record file as it
       is now, both into :data:`RECOVERED_DIR` beside the store, never
       over an existing file. A store holding nothing for the return
       writes no export - an empty file is never offered as a copy.
    2. **The difference**: each line the two do not agree on, by seq, side,
       event, time and host (:class:`Difference`) - no payload value.
    3. Only when ``accept_loss`` is the return folder's own name, typed
       exactly, and the record reads: the return's rows are rebuilt from
       the record and the checkpoint is seeded again from it (the moment of
       trust), its lines from other machines cleared.

    A record that does not read is said so by the first look already, and
    never offered a replay (:data:`RECORD_DOES_NOT_READ`): nothing here
    rewrites a record, and the export is named as the copy to restore from
    only when it holds every line the record still reads
    (:data:`RESTORE_FROM_EXPORT`, else :data:`NO_USABLE_COPY`).
    """
    engagement_dir = Path(engagement_dir)
    rel = engagement_path(key_root(engagement_dir, root), engagement_dir)
    row = _engagement_row(conn, engagement_dir, root)
    held = {} if row is None else {
        one["seq"]: one["payload"]
        for one in conn.execute("SELECT seq, payload FROM events WHERE engagement_id = ? ORDER BY seq",
                                (row["id"],))}
    stamp = (now or dt.datetime.now()).strftime("%Y-%m-%d-%H%M%S")
    base = _store_file(conn).parent / RECOVERED_DIR / f"{rel.replace('/', '__')}-{stamp}.jsonl"
    now_bytes = ledger._bytes_of(ledger.path_for(engagement_dir))
    try:
        export = (_exclusively(base, "".join(f"{held[seq]}\n" for seq in sorted(held)).encode("utf-8"))
                  if held else None)
        record_copy = (None if now_bytes is None else
                       _exclusively((export or base).with_name(base.stem + ".record-now.jsonl"),
                                    now_bytes))
    except OSError as exc:
        # Said by its class and the folder, never a traceback, and nothing
        # was discarded: the replay comes only after the export (S2).
        raise StoreError(EXPORT_NOT_WRITTEN.format(folder=base.parent,
                                                   kind=exc.__class__.__name__)) from None

    problem, readable = "", 0
    try:
        events = ledger.read_events(engagement_dir)
        on_record = [json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events]
    except ledger.LedgerError as exc:
        # The reader's own sentence, without its pointer back to recover.
        problem = str(exc).removesuffix(" " + ledger.RUN_RECOVER).rstrip(".")
        readable = max(0, (exc.line or 1) - 1)
        on_record = [line.decode("utf-8", "replace") for line in (now_bytes or b"").split(b"\n")
                     if line.strip()]
    differences: list[Difference] = []
    lost = 0
    for seq in range(1, max(len(held), len(on_record)) + 1):
        mine = held.get(seq)
        theirs = on_record[seq - 1] if seq <= len(on_record) else None
        if mine == theirs:
            continue
        if mine is not None:
            lost += 1
        side = ON_STORE if theirs is None else ON_RECORD if mine is None else BOTH_DIFFERENT
        for payload in (mine, theirs):
            if payload is not None:
                differences.append(Difference(seq, side, *_described(payload)))
    result = Recovery(export=export, record_copy=record_copy, differences=differences, lost=lost)
    if problem:
        # Said by the first look, and no replay offered (MF3).
        restore = (RESTORE_FROM_EXPORT.format(record_now=record_copy, export=export)
                   if export is not None and len(held) >= readable
                   and all(held.get(seq) == on_record[seq - 1] for seq in range(1, readable + 1))
                   else NO_USABLE_COPY)
        result.refusal = RECORD_DOES_NOT_READ.format(problem=problem, restore=restore)
        return result
    if accept_loss is None:
        return result
    if accept_loss != engagement_dir.name:
        result.refusal = WRONG_NAME.format(given=accept_loss)
        return result
    rebuild_engagement(conn, root, engagement_dir, discard=True)
    log.warning("%s: recovered by a person's acceptance; %d line(s) the store had are not in the "
                "record, kept in %s", rel, lost, export)
    result.accepted = True
    return result


# ------------------------------------------------------------- verify ----

#: The classes of problem ``verify`` names, one per line with a path below
#: the root and never a word of a document.
V_RECORD = "the record does not read"
V_SHORTER = "the record is shorter than this machine last saw"
V_REWRITTEN = "the record no longer matches what this machine last saw"
V_CLAIMS = "a line says it was written on this machine and was not"
V_NO_WRITER = "a line past what this machine saw carries no writer"
V_FOREIGN = "a line was written on another machine, which is refused"
#: A line the store's admission refuses (decision 187), named by the gate's
#: own sentence - which names the field and the class, never the value.
V_MALFORMED = "a line is outside the record's rule"
V_STORE = "the store has applied lines the record does not hold"
V_MISSING = "a recorded file is missing"
V_CHANGED = "a recorded file holds other bytes"
V_BY_KIND = {_CLAIMS: V_CLAIMS, _NO_WRITER: V_NO_WRITER, _FOREIGN: V_FOREIGN, _MALFORMED: V_MALFORMED}


def verify(conn: sqlite3.Connection, held: sqlite3.Connection | None, root: Path | str) -> list[str]:
    """Every problem, firm-wide, as ``class: path below the root``
    (decision 159, G-10). Read-only: ``conn`` and ``held`` are opened
    read-only by the caller, no lock is taken, nothing is seeded, copied,
    moved or created, and a cloud placeholder is never read (reading one
    downloads it).

    For every folder with a record: the record reads (links, format);
    every line is inside the store's admission (decision 187); it extends
    what the checkpoint vouches for; the store has applied a prefix of it. For every row: its original and each working copy it claims are
    there and hold the row's bytes - proved by the filer's own proof of a
    row's bytes (``filer.holds_the_row``, decision 109's reading), not a
    second one.
    """
    from tracker import layout, registry
    from tracker.filer import FILE_MOVED, holds_the_row
    from tracker.layout import locate
    from tracker.validators import is_cloud_placeholder

    root = Path(root)

    def below(path: Path) -> str:
        # The layout's one question of a path under another (decision 188).
        parts = layout.parts_below(root, path)
        return str(path) if parts is None else "/".join(parts) or "."

    problems: list[str] = []
    for folder in registry.record_dirs(root):
        try:
            events, _head, chain = ledger.read_with_chain(folder)
        except ledger.LedgerError as exc:
            problems.append(f"{V_RECORD}: {below(folder)} ({exc})")
            continue
        row = _engagement_row(conn, folder, root)
        key = row["path"] if row is not None else engagement_path(key_root(folder, root), folder)
        # Every line held to the one admission first (decision 187), as
        # ``check`` holds it: no place a line names is looked at, and no
        # writer judged, before the line's values are inside the rule.
        refused = ""
        for seq, event in enumerate(events, start=1):
            try:
                _refuse_a_malformed_line(event, seq, key,
                                         kind=row["kind"] if row is not None else KIND_RETURN)
            except StoreError as exc:
                refused = str(exc)
                break
        if refused:
            problems.append(f"{V_MALFORMED}: {below(folder)} ({refused})")
            continue
        vouched = checkpoint.vouched(held, key) if held is not None else None
        if vouched is not None:
            # The pass's own judgment, not a copy of it (the review's S3).
            judged = _judge(vouched, checkpoint.intent(held, key), events, chain)
            if judged.kind == _SHORTER:
                problems.append(f"{V_SHORTER}: {below(folder)} ({len(events)} of {judged.seq})")
            elif judged.kind == _REWRITTEN:
                problems.append(f"{V_REWRITTEN}: {below(folder)}")
            elif judged.kind:
                problems.append(f"{V_BY_KIND[judged.kind]}: {below(folder)} line {judged.seq}")
        if row is not None and (row["applied_seq"] > len(events) or
                                ledger.chain_at(chain, row["applied_seq"]) != row["applied_digest"]):
            problems.append(f"{V_STORE}: {below(folder)}")
        entries = [records.entry_from_json(one) for one in ledger.replay(events).rows.values()]
        claims: dict[str, int] = {}
        for position, entry in enumerate(entries):
            if entry.digest and entry.decision != FILE_MOVED:
                for location in entry.filed_locations:
                    claims[location] = position
        for position, entry in enumerate(entries):
            if not entry.digest:
                continue
            places = [location for location in entry.filed_locations if claims.get(location) == position]
            if entry.pbc_location:
                places.insert(0, entry.pbc_location)
            for location in places:
                path = locate(folder, location)
                if not path.is_file():
                    problems.append(f"{V_MISSING}: {below(path)}")
                elif is_cloud_placeholder(path):
                    continue
                elif not holds_the_row(path, entry.digest):
                    problems.append(f"{V_CHANGED}: {below(path)}")
    return problems


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
        description="Build, check, verify, recover and export the store: one database on this "
                    "machine, rebuilt from each engagement's own record.",
    )
    parser.add_argument("store", help="the app folder, the settings file in it, or the store file itself")
    parser.add_argument("command", choices=("rebuild", "check", "export", "state", "verify", "recover"))
    parser.add_argument("root", help="the clients root")
    parser.add_argument("--engagement", help="one engagement folder instead of every one "
                                             "(recover: the return to recover)")
    parser.add_argument("--out", help="where export writes its files")
    parser.add_argument("--discard", action="store_true",
                        help="rebuild one return (--engagement) from its record, discarding the lines "
                             "only the store holds - only with --accept-loss and the return's name")
    parser.add_argument("--accept-loss", metavar="NAME",
                        help="recover: replay from the record, accepting the loss of the lines "
                             "only the store had; NAME is the return folder's name, typed exactly")
    ns = parser.parse_args()

    given = Path(ns.store)
    chosen = store_named(given)
    if chosen is None:
        parser.error(f"{given} is not the app folder, a settings file in it, or a {STORE_FILENAME}; "
                     f"nothing was opened and no store was created")
    # The root and a typed folder through the one door (decision 188): the
    # root held to the settings' rule, the folder a return's or a
    # household's place under it, rebuilt from its own names.
    from tracker import door
    from tracker.layout import LayoutError
    try:
        clients_root = door.checked_root(ns.root)
        if ns.engagement:
            try:
                one = door.return_dir(Path(ns.engagement).absolute(), root=clients_root)
            except ValueError:
                one = door.household_dir(Path(ns.engagement).absolute(), root=clients_root)
    except (door.DoorError, LayoutError) as exc:     # the door's own sentences
        parser.error(str(exc))
    if ns.command == "recover" and not ns.engagement:
        parser.error("recover needs --engagement <the return folder>")
    # Decision 188's --discard, narrowed (the port review's M1): a loss is
    # accepted only for one return, by its name typed - recover's own path,
    # its export and its difference first. Anything less is refused here.
    if ns.command == "rebuild" and ns.discard:
        if not ns.engagement or not ns.accept_loss:
            parser.error('rebuild --discard needs --engagement <the return folder> and '
                         '--accept-loss "<its folder name, typed exactly>"; nothing was changed')
        ns.command = "recover"
    elif ns.accept_loss and ns.command != "recover":
        parser.error("--accept-loss goes with recover, or with rebuild --discard")

    if ns.command == "verify":
        # Read-only (decision 159, G-10): both files opened so that nothing
        # can be written through them, no lock, nothing created.
        try:
            reading = open_read_only(chosen)
            heads = checkpoint.open_read_only(checkpoint.path_for(chosen))
        except (StoreError, checkpoint.CheckpointError) as exc:
            parser.exit(1, f"{exc}\n")
        try:
            found = verify(reading, heads, clients_root)
        finally:
            reading.close()
            if heads is not None:
                heads.close()
        print(f"\n{chosen}")
        for line in found:
            print(f"  {line}")
        print(f"\n  {len(found)} problem(s)\n" if found else "\n  nothing to report\n")
        raise SystemExit(1 if found else 0)

    # Every folder with a record, households included (decision 125): a
    # household's row is held in this same table and folded by the same
    # machinery, so a check that walked only the returns would leave each
    # of them unchecked without saying so.
    folders = [one] if ns.engagement else registry.record_dirs(clients_root)

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
        elif ns.command == "recover":
            done = recover(connection, clients_root, folders[0], accept_loss=ns.accept_loss)
            if done.export is not None:
                print(f"  kept the store's lines in {done.export}")
            else:
                print("  the store holds no line of this return; no export was written")
            if done.record_copy is not None:
                print(f"  kept the record as it is now in {done.record_copy}")
            if done.differences:
                print(f"  {'seq':>6}  {'side':<15} {'event':<28} {'at':<22} host")
                for one in done.differences:
                    print(f"  {one.seq:>6}  {one.side:<15} {one.event:<28} {one.at:<22} {one.host}")
            else:
                print("  the store and the record hold the same lines")
            if done.accepted:
                print(f"  {ACCEPTED.format(n=done.lost)}")
            elif done.refusal:
                print(f"  {done.refusal}")
                failures = 1
            else:
                print(f"  nothing was changed; to replay from the record and accept the loss, "
                      f"run again with --accept-loss \"{folders[0].name}\"")
                failures = 1
        else:
            for engagement in folders:
                if ns.command == "rebuild":
                    # Never discards silently (SPEC-162 ruling 6, decision
                    # 159): what would go is listed, a record that does not
                    # extend what this machine saw is refused by name and the
                    # rest are still built. --discard with the typed name is
                    # recover's path, above.
                    try:
                        lost = rebuild_engagement(connection, clients_root, engagement)
                    except WouldDiscard as refused:
                        for line in refused.lines:
                            print(line)
                        print(f"  {refused}")
                        failures += 1
                        continue
                    except (StoreError, ledger.LedgerError) as exc:
                        failures += 1
                        print(f"  refused {engagement.name}: {exc}")
                        continue
                    for line in lost:
                        print(f"  discarded{line}")
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
            # One report (decision 188 with 187's re-judging): every stored
            # engagement under the root whose journal is gone, which no walk
            # of the root can find.
            if ns.command == "check" and not ns.engagement:
                for line in gone_journals(connection, clients_root):
                    print(f"  {line}")
                    failures += 1
    except StoreError as exc:
        parser.exit(1, f"{exc}\n")
    finally:
        close()
    if failures and ns.command == "check":
        print(f"\n  the store and the record do not agree ({failures})\n")
    elif failures and ns.command == "rebuild":
        print(f"\n  {failures} record(s) refused; nothing of theirs was rebuilt\n")
    else:
        print()
    raise SystemExit(1 if failures else 0)
