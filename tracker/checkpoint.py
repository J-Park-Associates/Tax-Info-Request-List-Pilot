"""What this machine last saw of each record: the checkpoint (decision 159).

The record (:mod:`tracker.ledger`) lives in the synced folders, and since
decision 159 every line carries the link to the line before it, the host
that wrote it and its format. The link detects an accidental reorder, a
lost line or a careless edit - by a hand that did not recompute the chain.
It cannot say a record is the one *this machine* wrote: a record restored
from an older copy, cut short at a line, given a well-formed line by
somebody else, or rewritten by a hand that recomputed every link after its
edit still links perfectly, and only this file catches those. Neither
stops a writer who controls this machine (see below). And the store (:mod:`tracker.store`)
cannot say it either, because the store is rebuilt from the record and a
rebuilt store trusts whatever it is built from. So this file keeps, for
each record, how many lines this machine vouches for and the chain through
them (the same number the store keeps as ``applied_digest``, computed in
:func:`tracker.ledger.chain_link` and nowhere else). A record that is
shorter than that, or whose first lines no longer chain to it, or that has
a line past it claiming to come from this machine when this machine did
not write it, is refused by the store before anything is applied.

**Beside the store, and not the store** (:func:`path_for`). Deleting or
setting aside the store file - which the runbook has always allowed -
keeps this file, so a rebuilt store is still held to what this machine saw.
It never syncs: it describes one machine, and a copy of it on another
machine would describe the wrong one.

**Per machine, and a line from another machine is named, not refused.**
Nothing here assumes one writer for ever. Every line names its host, and
the one place that decides whether a line written on another machine is
accepted is :func:`foreign_lines_refused`. Jason decided on 2026-09-26
(decision 159, question C-1 (a)) that until the multi-writer study is
decided such a line is accepted, recorded here in ``foreign_lines`` and named on
the practice page every pass until a person acknowledges it.

**What this buys, said plainly** (decision 159; row 159 and the runbook
carry the same text). The link in every line detects accidents anywhere: a
sync client restoring an older copy, a reorder, a lost tail, a careless
hand edit. The checkpoint on the machine that writes detects a rewrite and
an append that machine did not make. **It does not protect against a
writer who controls that machine itself**: malware or a person at its
keyboard can write the record and the checkpoint together; that is
contained by decision 180, which limits what a forged line can do. It is
**not proof to a third party** of who wrote a line: the host is written by
the program and could be typed by anyone. **The moment of trust:** a first
sight, a new machine or an accepted recovery seeds the checkpoint from the
record as it then is; the export ``recover`` writes, and the off-drive copy
the firm keeps, are what stand behind that moment. **A secret key was
rejected**: it would live on the machine it protects, and a lost key would
make the firm's own record unwritable.

**The bottom of the package.** It imports nothing of the package: it is
handed keys, counts, heads and hosts, and hands them back. The store, which
knows what a record is, does the proving (``store._prove_against_checkpoint``).

**Its own short transactions.** The app and the pass on one machine share
this file, and two returns under two different locks may advance at once,
so every write is one ``BEGIN IMMEDIATE`` with a busy timeout, opened and
closed around the one question - the file is small and asked rarely (only
when a store applies lines), and a connection held for the life of a
process would be one more handle Windows refuses to delete a folder under.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path

#: The file, beside the store in the data home.
CHECKPOINT_FILENAME = "record-heads.db"

#: This file's own layout version, written as ``user_version``.
CHECKPOINT_VERSION = 1

#: How long a writer waits for the other process on this machine.
BUSY_TIMEOUT_MS = 5000

#: What an older file is renamed to when it is set aside (decision 159, E3):
#: the store at version 15 gets ``.v15.old`` after its name, and a second
#: one ``.v15.old.1``. Never overwritten.
SET_ASIDE_SUFFIX = ".v{version}.old"

#: A file written by a newer version of the tracker: refused, never read.
NEWER_FILE = ("{path} was written by a newer version of the tracker (version {version}; this one "
              "knows {known}). This machine has a newer version of the tracker's {what}; install "
              "that version again.")

SCHEMA: tuple[str, ...] = (
    "CREATE TABLE IF NOT EXISTS root (path TEXT NOT NULL, since TEXT NOT NULL)",
    """CREATE TABLE IF NOT EXISTS heads (
        "key" TEXT PRIMARY KEY,
        count INTEGER NOT NULL,
        head TEXT NOT NULL,
        at TEXT NOT NULL,
        seeded INTEGER NOT NULL,
        pending INTEGER NOT NULL DEFAULT 0,
        pending_heads TEXT NOT NULL DEFAULT '[]'
    )""",
    """CREATE TABLE IF NOT EXISTS foreign_lines (
        "key" TEXT NOT NULL,
        seq INTEGER NOT NULL,
        host TEXT NOT NULL,
        at TEXT NOT NULL,
        seen TEXT NOT NULL,
        acknowledged TEXT,
        PRIMARY KEY ("key", seq)
    )""",
)


class CheckpointError(RuntimeError):
    """The checkpoint could not be opened, or refused what it was asked."""


#: A checkpoint file that will not open as one (the review's S4). Refused by
#: name and never set aside automatically: a damaged checkpoint is exactly
#: what a person must see.
UNREADABLE = ("{path}: the tracker cannot read this machine's record checkpoint ({why}). Set the "
              "file aside by hand (runbook §6); the next pass seeds it again from the records - "
              "the moment of trust.")
#: A checkpoint another run holds this moment (``verify``, ``acknowledge``,
#: the app): nothing is wrong with it, and it must never be set aside for
#: it - that would throw a healthy checkpoint away and make the next pass a
#: moment of trust (the rebase review's SF1).
BUSY = ("{path}: this machine's record checkpoint is busy - another run is using it ({why}). "
        "Nothing was changed; the next pass tries again. Do not set the file aside for this.")
#: The engine's codes that mean another connection holds the file.
_BUSY_CODES = ("SQLITE_BUSY", "SQLITE_LOCKED")


class CheckpointUnavailable(CheckpointError):
    """The engine refused the checkpoint: busy past the timeout, or a file
    that is damaged or not a database (the rebase review's MF1). The
    checkpoint's own single error path, as 189 gave the store its
    ``StoreUnavailable``: every ``sqlite3.Error`` from an open, a read or a
    write leaves this module as this, naming the file, the engine's code -
    never its message (principle 7) - and the runbook's step. ``busy`` says
    which of the two sentences it is: :data:`BUSY` (try again) or
    :data:`UNREADABLE` (set it aside by hand)."""

    #: Said as ``<class> (<code>)`` by :func:`tracker.errors.error_class`
    #: (the marker :data:`tracker.errors.SAYS_ITS_CODE`, decision 190).
    says_its_code = True

    def __init__(self, path: Path | str, code: str) -> None:
        self.busy = code.startswith(_BUSY_CODES)
        super().__init__((BUSY if self.busy else UNREADABLE).format(path=path, why=code))
        self.code = code


def _unavailable(exc: sqlite3.Error, path: Path | str) -> CheckpointUnavailable:
    # The engine's code, or - for an error that did not come from the
    # engine - SQLITE_ERROR, as the store says it; never the class named
    # here, which only tracker.errors.error_class says (decision 190).
    return CheckpointUnavailable(path, getattr(exc, "sqlite_errorname", None) or "SQLITE_ERROR")


class _Cursor(sqlite3.Cursor):
    """A cursor whose statements and rows fail as :class:`CheckpointUnavailable`."""

    def _say(self, exc: sqlite3.Error) -> CheckpointUnavailable:
        return _unavailable(exc, getattr(self.connection, "where", "record checkpoint"))

    def execute(self, sql, parameters=(), /):
        try:
            return super().execute(sql, parameters)
        except sqlite3.Error as exc:
            raise self._say(exc) from exc

    def fetchone(self):
        try:
            return super().fetchone()
        except sqlite3.Error as exc:
            raise self._say(exc) from exc

    def fetchall(self):
        try:
            return super().fetchall()
        except sqlite3.Error as exc:
            raise self._say(exc) from exc

    def __next__(self):
        try:
            return super().__next__()
        except sqlite3.Error as exc:
            raise self._say(exc) from exc


class _Connection(sqlite3.Connection):
    """The checkpoint's connection: the one choke point every statement in
    this module goes through, so no ``sqlite3.Error`` leaves it raw."""

    where: str = "record checkpoint"

    def cursor(self, factory=_Cursor):
        try:
            return super().cursor(factory)
        except sqlite3.Error as exc:
            raise _unavailable(exc, self.where) from exc

    def execute(self, sql, parameters=(), /):
        return self.cursor().execute(sql, parameters)

    def executemany(self, sql, parameters, /):
        cursor = self.cursor()
        try:
            return cursor.executemany(sql, parameters)
        except sqlite3.Error as exc:
            raise _unavailable(exc, self.where) from exc

    def close(self):
        try:
            return super().close()
        except sqlite3.Error as exc:
            raise _unavailable(exc, self.where) from exc


def _connected(target: str | Path, where: Path, **options) -> _Connection:
    """A connection through :class:`_Connection`, naming ``where``."""
    try:
        conn = sqlite3.connect(target, isolation_level=None, factory=_Connection, **options)
    except sqlite3.Error as exc:
        raise _unavailable(exc, where) from exc
    try:
        conn.where = str(where)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    except BaseException:
        _close_after_failure(conn)
        raise
    return conn


def _close_after_failure(conn: sqlite3.Connection) -> None:
    """Close a connection whose opening failed, keeping the failure being
    raised as the one reported.

    Not left to Python: the connection is still referenced from the
    exception's traceback, so it stays open until the garbage collector
    runs, and on Windows an open SQLite handle is a file that cannot be
    renamed or deleted (WinError 32). A damaged checkpoint refused by name
    - "set it aside, runbook section 6" - stayed locked by the refusing
    process against exactly that step (decision 159, Windows). A close
    that fails itself says nothing new; the error already raised does.
    """
    try:
        conn.close()
    except (sqlite3.Error, CheckpointError):
        pass


@dataclass(frozen=True)
class Intent:
    """What a writer said it was about to append (:func:`expect`): the line
    count it started from, and the chain after each line it would write."""

    start: int
    heads: tuple[str, ...]

    def owns(self, seq: int, head: str) -> bool:
        """Whether line ``seq``, with the chain ``head`` through it, is one of
        the lines this writer said it would write - exactly those bytes."""
        return self.start < seq <= self.start + len(self.heads) and self.heads[seq - self.start - 1] == head


@dataclass(frozen=True)
class Foreign:
    """One line written on another machine that this machine accepted."""

    key: str
    seq: int
    host: str
    at: str
    seen: str


def path_for(store_file: Path | str) -> Path:
    """Where the checkpoint lives: beside the store, whatever the store's
    folder is (the data home once decision 186 is in)."""
    return Path(store_file).with_name(CHECKPOINT_FILENAME)


def foreign_lines_refused() -> bool:
    """Whether a line written on another machine is refused.

    **The one switch** (decision 159, §0 and question C-1). ``False``: the
    one-machine rule is Jason's open decision, waiting on the multi-writer
    study (``DISCUSSION-multi-writer-2026-09-26.md``), and refusing a line
    from a second machine now would enforce one machine by friction before
    anybody decided it. So such a line is accepted, recorded, and named on
    the practice page every pass until a person acknowledges it. When the
    study is decided, this function and its test are the change.
    """
    return False


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def set_aside(path: Path | str, version: int) -> Path:
    """Rename a database file an older version wrote - and its ``-wal`` and
    ``-shm`` - out of the way, never overwriting anything. Returns where it
    went. The one set-aside, for the store and this file alike (E3)."""
    path = Path(path)
    base = path.with_name(path.name + SET_ASIDE_SUFFIX.format(version=version))
    target, n = base, 0
    while any(Path(str(target) + suffix).exists() for suffix in ("", "-wal", "-shm")):
        n += 1
        target = base.with_name(f"{base.name}.{n}")
    for suffix in ("", "-wal", "-shm"):
        side = Path(str(path) + suffix)
        if side.exists():
            os.replace(side, Path(str(target) + suffix))
    return target


def open(path: Path | str) -> sqlite3.Connection:  # noqa: A001 - the checkpoint is opened
    """Open the checkpoint at ``path``, creating it when it is not there.

    The store's discipline (decision 159, E3): a file an older version wrote
    is set aside and a fresh one made - it is seeded again from the records,
    which is the moment of trust the docstring names; a newer one is
    refused by name. The caller closes the connection.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return _opened(path)


def _opened(path: Path) -> sqlite3.Connection:
    conn = _connect(path)
    # Closed on any failure, never left to the garbage collector: see
    # _close_after_failure (decision 159, Windows).
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if 0 < version < CHECKPOINT_VERSION:
            conn.close()
            set_aside(path, version)
            conn = _connect(path)
            version = 0
        if version == 0:
            with _transaction(conn):
                for statement in SCHEMA:
                    conn.execute(statement)
                conn.execute(f"PRAGMA user_version = {CHECKPOINT_VERSION}")
        elif version != CHECKPOINT_VERSION:
            conn.close()
            raise CheckpointError(NEWER_FILE.format(path=path, version=version, known=CHECKPOINT_VERSION,
                                                    what="record checkpoint"))
    except BaseException:
        _close_after_failure(conn)
        raise
    return conn


def open_read_only(path: Path | str) -> sqlite3.Connection | None:
    """The checkpoint opened so that nothing can be written through it, or
    None where there is none. What the read-only verify uses: it creates
    nothing, not even an empty checkpoint."""
    path = Path(path)
    if not path.is_file():
        return None
    conn = _connected(f"{path.resolve().as_uri()}?mode=ro", path, uri=True)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    except BaseException:
        _close_after_failure(conn)
        raise
    if version != CHECKPOINT_VERSION:
        conn.close()
        raise CheckpointError(f"{path} is a record checkpoint at version {version}; this version "
                              f"reads {CHECKPOINT_VERSION}")
    return conn


def _connect(path: Path) -> sqlite3.Connection:
    return _connected(path, path)


@contextmanager
def opened(path: Path | str) -> Iterator[sqlite3.Connection]:
    """:func:`open`, closed when the block ends."""
    with closing(open(path)) as conn:
        yield conn


@contextmanager
def _transaction(conn: sqlite3.Connection):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


# --------------------------------------------------------------- heads ----


def vouched(conn: sqlite3.Connection, key: str) -> tuple[int, str] | None:
    """How many lines of the record keyed ``key`` this machine vouches for,
    and the chain through them; None where it has never seen that record."""
    row = conn.execute('SELECT count, head FROM heads WHERE "key" = ?', (key,)).fetchone()
    return None if row is None else (row["count"], row["head"])


def intent(conn: sqlite3.Connection, key: str) -> Intent | None:
    """What this machine said it was about to append to one record
    (:func:`expect`), or None: a line of this machine past the count is its
    own only when it is exactly one of those lines (:meth:`Intent.owns`)."""
    row = conn.execute('SELECT pending, pending_heads FROM heads WHERE "key" = ?', (key,)).fetchone()
    if row is None or not row["pending"]:
        return None
    heads = tuple(json.loads(row["pending_heads"]))
    return Intent(start=row["pending"] - len(heads), heads=heads)


def advance(conn: sqlite3.Connection, key: str, count: int, head: str, *, seeded: bool) -> None:
    """Vouch for the first ``count`` lines, chaining to ``head``. Clears the
    intent once the count reaches it - a reader that applied part of a
    writer's batch leaves the rest of the batch still expected. ``seeded`` says the value was taken on trust (a first sight, a
    person's acceptance, or a line from another machine) rather than
    because this machine wrote the last line."""
    with _transaction(conn):
        conn.execute(
            'INSERT INTO heads ("key", count, head, at, seeded, pending) VALUES (?, ?, ?, ?, ?, 0) '
            'ON CONFLICT("key") DO UPDATE SET count = excluded.count, head = excluded.head, '
            "at = excluded.at, seeded = excluded.seeded, "
            "pending = CASE WHEN pending > excluded.count THEN pending ELSE 0 END, "
            "pending_heads = CASE WHEN pending > excluded.count THEN pending_heads ELSE '[]' END",
            (key, count, head, _now(), int(seeded)),
        )


def expect(conn: sqlite3.Connection, key: str, start: int, heads: list[str]) -> None:
    """Say, before appending, that this machine is about to take the record
    from ``start`` lines through ``heads`` - the chain after each line it
    will write (decision 159, §4.3's intent, made exact by the review's M1).
    A run killed between its append and the checkpoint's advance leaves
    lines of this host past the count; they are this machine's own only
    when they are exactly those lines, so a line forged later in the same
    place is still refused. An empty ``heads`` clears the intent. Only for
    a record this machine already vouches for."""
    with _transaction(conn):
        changed = conn.execute('UPDATE heads SET pending = ?, pending_heads = ? WHERE "key" = ?',
                               (start + len(heads) if heads else 0, json.dumps(list(heads)), key))
        if changed.rowcount != 1:
            raise CheckpointError(f"{key}: this machine has no checkpoint for the record yet; "
                                  f"it is seeded before it is written to")


def forget(conn: sqlite3.Connection, key: str) -> None:
    """Drop everything this machine vouched for about one record: a return a
    failed create removed, or one a person's accepted recovery re-seeds."""
    with _transaction(conn):
        conn.execute('DELETE FROM heads WHERE "key" = ?', (key,))
        conn.execute('DELETE FROM foreign_lines WHERE "key" = ?', (key,))


# ------------------------------------------------------------- foreign ----


def note_foreign(conn: sqlite3.Connection, key: str, lines: Iterable[tuple[int, str, str]]) -> int:
    """Record lines written on another machine - each ``(seq, host, at)`` -
    that this machine accepted. A line already recorded is left as it is.
    Returns how many were new."""
    seen = _now()
    added = 0
    with _transaction(conn):
        for seq, host, at in lines:
            cursor = conn.execute(
                'INSERT OR IGNORE INTO foreign_lines ("key", seq, host, at, seen) VALUES (?, ?, ?, ?, ?)',
                (key, int(seq), str(host), str(at), seen),
            )
            added += cursor.rowcount
    return added


def unacknowledged(conn: sqlite3.Connection) -> list[Foreign]:
    """Every accepted line from another machine that no person has
    acknowledged yet, by record and line."""
    return [Foreign(key=row["key"], seq=row["seq"], host=row["host"], at=row["at"], seen=row["seen"])
            for row in conn.execute('SELECT * FROM foreign_lines WHERE acknowledged IS NULL '
                                    'ORDER BY "key", seq')]


def acknowledge(conn: sqlite3.Connection, key: str) -> int:
    """A person has seen every line from another machine in one record.
    Returns how many were acknowledged now."""
    with _transaction(conn):
        return conn.execute('UPDATE foreign_lines SET acknowledged = ? '
                            'WHERE "key" = ? AND acknowledged IS NULL', (_now(), key)).rowcount


# ---------------------------------------------------------------- root ----


def root_of(conn: sqlite3.Connection) -> str | None:
    """The clients root this checkpoint belongs to, or None before one is claimed."""
    row = conn.execute("SELECT path FROM root").fetchone()
    return None if row is None else row["path"]


def claim_root(conn: sqlite3.Connection, root: str) -> str:
    """Claim ``root`` for this checkpoint when none is claimed yet. Returns
    the root it belongs to - the one claimed before, if there was one: a
    claim never moves (:func:`move_root` does, when a person says so)."""
    with _transaction(conn):
        claimed = root_of(conn)
        if claimed is None:
            conn.execute("INSERT INTO root (path, since) VALUES (?, ?)", (str(root), _now()))
            return str(root)
    return claimed


def move_root(conn: sqlite3.Connection, root: str) -> None:
    """The clients root really moved: the checkpoint belongs to ``root`` now.
    The keys are relative to the root, so nothing else changes."""
    with _transaction(conn):
        conn.execute("DELETE FROM root")
        conn.execute("INSERT INTO root (path, since) VALUES (?, ?)", (str(root), _now()))


# ----------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    # The two calls into the package, and only here: a record's key names a
    # client, and the console must not turn that into a traceback; and a
    # typed root is the door's to check (decision 188), never this module's.
    from tracker import door
    from tracker.page import tolerant_console

    tolerant_console()

    parser = argparse.ArgumentParser(
        prog="python -m tracker.checkpoint",
        description="What this machine last saw of each record (decision 159).",
    )
    parser.add_argument("store", help="the store file or the folder it is in")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("state", help="the root it belongs to, the records it vouches for, "
                                 "and the lines from another machine not yet acknowledged")
    ack = sub.add_parser("acknowledge", help="a person has seen the lines from another machine "
                                             "in one record")
    ack.add_argument("key", help="the record's key, as `state` prints it")
    move = sub.add_parser("move-root", help="the clients root really moved")
    move.add_argument("root", help="the clients root as it is now")
    ns = parser.parse_args()

    given = Path(ns.store)
    where = given / CHECKPOINT_FILENAME if given.is_dir() else path_for(given)
    if not where.is_file():
        parser.exit(1, f"there is no record checkpoint at {where}; nothing was created\n")
    try:
        with opened(where) as connection:
            if ns.command == "acknowledge":
                print(f"acknowledged {acknowledge(connection, ns.key)} line(s) of {ns.key}")
            elif ns.command == "move-root":
                try:
                    moved = door.checked_root(ns.root)
                except door.DoorError as exc:
                    parser.exit(1, f"{exc}\n")
                move_root(connection, str(moved))
                print(f"the checkpoint belongs to {moved} now")
            else:
                print(f"{where}\n  root: {root_of(connection) or '(none claimed)'}")
                for one in connection.execute('SELECT * FROM heads ORDER BY "key"'):
                    print(f"  {one['count']:>6} line(s)  {'seeded' if one['seeded'] else 'written'}"
                          f"  {one['at']}  {one['key']}")
                for line in unacknowledged(connection):
                    print(f"  another machine: {line.key} line {line.seq} on {line.host} {line.at}")
    except CheckpointError as exc:
        parser.exit(1, f"{exc}\n")
    except sqlite3.Error as exc:
        # The checkpoint's own single error path: the file and the engine's
        # code, never its message (decision 190).
        unavailable = _unavailable(exc, where)
        parser.exit(1, f"{unavailable}\n")
