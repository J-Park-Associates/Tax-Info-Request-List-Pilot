"""The machine's own record of one engagement, appended to and never rewritten.

Every fact the system holds about an engagement lives today in a workbook a
person can open, sort, re-type and save from Excel - and each of the readings
in the decision log found another way that ends with a row lost. The
workbooks stay; beside them each engagement now keeps ``LEDGER_FILENAME``, one
JSON object per line, in the order the writers wrote them. It is the record
of *what was decided*; the workbooks remain the thing a person reads and the
thing every reader still reads today.

**Nothing reads it in production yet.** It is written alongside the files
that already exist, and the whole suite checks after every test that folding
it back gives exactly what the index and the manifest say (the agreement
fixture in ``tests/conftest.py``). The record is proved before anything is
allowed to depend on it; until then it costs one append per decision and
changes no behaviour at all.

**Append-only, one line per event.** A line is written with a single
``os.write`` under ``O_APPEND`` and then ``fsync``-ed, so a run killed
mid-append leaves at most a torn last line - bytes with no newline after
them. :func:`read_events` ignores such a tail and the next :func:`append`
truncates it first. Nothing else ever rewrites the file. A record's own JSON
never contains a newline (``json.dumps`` escapes them), so an unterminated
tail is the only shape a torn write can take.

**Written only under the engagement lock.** ``O_APPEND`` is atomic for
concurrent writers on POSIX and is *not* on Windows, where two appends can
interleave; the writer holds the engagement lock (:mod:`tracker.locking`),
which already forbids two runs on one engagement, so there is one writer and
one protocol rather than two. :func:`append` refuses when this process does
not hold it, because a silent append outside the lock is exactly the row that
goes missing later.

**Not a database.** SQLite was the obvious answer and is the wrong one here:
the engagement folders are synced by a cloud client between the office
machine and the drive, and a synced database file is a corrupted database
file. One database per clients root would be worse still - every client's
history in one file, which is the opposite of the rule that an engagement
folder carries everything about that engagement and nothing about anyone
else's. A text file that only ever grows is what a sync client can carry.

**Plain dicts, and no imports above this module.** The events are dicts of
JSON values, so this module sits at the bottom beside :mod:`tracker.locking`
and imports nothing else of the package: :mod:`tracker.filer` and
:mod:`tracker.manifest` both call it, and each serialises its own rows with
the function that already owns that shape (the index's sidecar rows, the
manifest's deferred updates). One owner per fact, and no cycle.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path

from tracker.locking import lock_is_held

log = logging.getLogger("tracker.ledger")

#: The engagement's own record, beside its workbooks. A person never edits it.
LEDGER_FILENAME = "_ledger.jsonl"

#: Keys every event carries.
EVENT_KEY = "event"
AT_KEY = "at"
#: Keys an index-shaped event carries: the identity the row is recorded under,
#: the whole row as the index's own sidecar serialises it, and - when the
#: client moved the original and the row followed it - the identity the row
#: is leaving, so the fold does not keep the vacated one for ever.
KEY_KEY = "key"
ROW_KEY = "row"
WAS_KEY = "was"
#: What a ``SCANNED`` event carries: identifier -> the scanner columns applied.
STATUSES_KEY = "statuses"

#: One original was preserved and its record says where it now is. A pass
#: that sorts a drop decides and preserves in one row, so it appends one of
#: the three decisions below instead; this is what a row gets when the client
#: renamed or moved an original inside the folder they can see and the row
#: followed the bytes.
PRESERVED = "preserved"
#: A drop was filed against exactly one request.
FILED = "filed"
#: A drop nothing could be sure of is waiting for a person.
PARKED = "parked"
#: A drop whose bytes were already recorded under another row.
DUPLICATE = "duplicate"
#: A person filed a parked document under a request.
ASSIGNED_BY_PERSON = "assigned_by_person"
#: A person said no request asks for a parked document.
DISMISSED_BY_PERSON = "dismissed_by_person"
#: A person sent a filed document back for review.
UNFILED_BY_PERSON = "unfiled_by_person"
#: A row preserved without its bytes was tied to them by a later pass.
BYTES_RECORDED = "bytes_recorded"
#: The statuses one scan applied. Appended only when something changed, so a
#: quiet pass appends nothing at all.
SCANNED = "scanned"
#: A person's filing taught a request a keyword.
KEYWORD_LEARNED = "keyword_learned"
#: A reminder was drafted. Reserved: the reminder writes files and holds no
#: lock, so nothing appends it yet.
DRAFTED = "drafted"
#: The bootstrap: what the workbooks already said when the ledger began.
IMPORTED = "imported"
#: Reserved for the migration that renames the engagement's files later.
MIGRATED = "migrated"

#: The events that carry a whole index row. Their fold is the index.
ROW_EVENTS = frozenset({
    PRESERVED, FILED, PARKED, DUPLICATE, ASSIGNED_BY_PERSON, DISMISSED_BY_PERSON,
    UNFILED_BY_PERSON, BYTES_RECORDED, IMPORTED, MIGRATED,
})
#: Every event name this version writes or reads.
EVENTS = ROW_EVENTS | frozenset({SCANNED, KEYWORD_LEARNED, DRAFTED})

#: ``O_BINARY`` exists on Windows only; everywhere else the flag is not a flag.
_BINARY = getattr(os, "O_BINARY", 0)
_NEWLINE = b"\n"


class LedgerError(RuntimeError):
    """The record could not be appended to, or does not read as one."""


def path_for(engagement_dir: Path | str) -> Path:
    """Where one engagement's record lives."""
    return Path(engagement_dir) / LEDGER_FILENAME


def new(name: str, **payload: object) -> dict:
    """An event of ``name``, stamped now, carrying ``payload``.

    The stamp is UTC because the office machine's clock is local and a
    daylight-saving hour would otherwise put two passes out of order.
    """
    if name not in EVENTS:
        raise LedgerError(f"{name!r} is not an event this version writes ({', '.join(sorted(EVENTS))})")
    return {EVENT_KEY: name, AT_KEY: _now(), **payload}


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


# ----------------------------------------------------------------- write ----


def append(engagement_dir: Path | str, event: dict, *, seed=None) -> Path:
    """Append one event to the engagement's record. Returns the file.

    ``seed`` is the bootstrap, and is called at most once: when the record
    holds no event of this event's family yet - no index-shaped event for an
    index-shaped event, no ``SCANNED`` for a ``SCANNED`` - whatever it
    returns is appended first. That is how an engagement that has been
    running for a season, with an index full of rows and no record beside it,
    ends up with a record whose fold is that index: the first writer imports
    what the workbooks already say, then writes what it just did. It is not
    the migration (nothing is renamed here); it is what makes the record true
    from its first line.

    Refuses unless this process holds the engagement lock: the record is
    written in the same locked section as the write it records, after that
    write has succeeded - including when Excel held the workbook and the
    write went to a sidecar, because the sidecar is the workaround and this
    is the record.
    """
    engagement_dir = Path(engagement_dir)
    name = event.get(EVENT_KEY)
    if name not in EVENTS:
        raise LedgerError(f"{name!r} is not an event this version writes ({', '.join(sorted(EVENTS))})")
    if not lock_is_held(engagement_dir):
        raise LedgerError(
            f"{engagement_dir.name}: the record is appended to only while this run holds the "
            f"engagement lock; {name!r} was not written"
        )
    path = path_for(engagement_dir)
    _truncate_torn_tail(path)
    if seed is not None:
        family = ROW_EVENTS if name in ROW_EVENTS else {name}
        if not any(e.get(EVENT_KEY) in family for e in read_events(engagement_dir)):
            for earlier in seed():
                _write_line(path, earlier)
    _write_line(path, event)
    return path


def _write_line(path: Path, event: dict) -> None:
    """One event, one line, one write, flushed to the platter before we go on."""
    line = json.dumps(event, ensure_ascii=False, sort_keys=True).encode("utf-8") + _NEWLINE
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | _BINARY, 0o666)
    try:
        os.write(fd, line)
        os.fsync(fd)
    finally:
        os.close(fd)


def _truncate_torn_tail(path: Path) -> None:
    """Drop bytes a killed run left with no newline after them.

    Only ever the tail, and only under the lock: a torn line is the one thing
    a crash can leave behind, and appending after it would bury the damage in
    the middle of the file where no reader could tell it from a record.
    """
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return
    if not data or data.endswith(_NEWLINE):
        return
    keep = data.rfind(_NEWLINE) + 1
    log.warning("%s ended mid-line (%d byte(s)); the torn tail is dropped", path.name, len(data) - keep)
    with open(path, "r+b") as handle:
        handle.truncate(keep)
        handle.flush()
        os.fsync(handle.fileno())


# ------------------------------------------------------------------ read ----


def read_events(engagement_dir: Path | str) -> list[dict]:
    """Every event in the engagement's record, oldest first; [] if there is none.

    A torn last line - bytes a killed run left with no newline after them -
    is ignored. Anything else that does not read as one JSON object per line
    is corruption in the middle of the file and is refused loudly: this is
    the record, and nothing is guessed past it.
    """
    path = path_for(engagement_dir)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise LedgerError(f"could not read {path.name}: {exc}") from exc
    if not data:
        return []
    lines = data.split(_NEWLINE)
    if lines[-1]:
        log.warning("%s ends mid-line; the torn last line is ignored", path.name)
    lines.pop()                       # the tail after the last newline: empty, or torn
    events = []
    for number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LedgerError(f"{path.name} line {number} does not read as an event: {exc}") from exc
        if not isinstance(event, dict) or event.get(EVENT_KEY) is None:
            raise LedgerError(f"{path.name} line {number} is not an event")
        events.append(event)
    return events


def fold(events: list[dict]) -> dict[str, dict]:
    """The index the events add up to: the last index-shaped event per original.

    Keyed by the identity the writer recorded the row under (the index's own,
    its location among the client's preserved originals). An event carrying
    ``WAS_KEY`` says the row arrived from another identity - the client moved
    the original and the row followed the bytes - and the one it left is
    dropped, exactly as the index has only the one row for it.

    An event whose name this version does not know as index-shaped is passed
    over rather than refused: a later version may write one, and a reader
    that refuses what it does not know cannot read a record written by the
    run after it.
    """
    rows: dict[str, dict] = {}
    for event in events:
        if event.get(EVENT_KEY) not in ROW_EVENTS:
            continue
        key = event.get(KEY_KEY)
        if key is None:
            raise LedgerError(f"an index-shaped {event[EVENT_KEY]!r} event carries no {KEY_KEY!r}")
        was = event.get(WAS_KEY)
        if was and was != key:
            rows.pop(was, None)
        rows[key] = event[ROW_KEY]
    return rows


def statuses(events: list[dict]) -> dict[str, dict]:
    """The last status each identifier was scanned to, by identifier.

    A pass appends only what it changed, so the answer is built up across
    every ``SCANNED`` event rather than read off the last one.
    """
    out: dict[str, dict] = {}
    for event in events:
        if event.get(EVENT_KEY) == SCANNED:
            out.update(event.get(STATUSES_KEY) or {})
    return out


def head(engagement_dir: Path | str) -> str:
    """A digest of the record's bytes: the same for two folders holding the
    same history, different the moment either is appended to. Empty where
    there is no record yet."""
    path = path_for(engagement_dir)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return ""
    except OSError as exc:
        raise LedgerError(f"could not read {path.name}: {exc}") from exc
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Show one engagement's own record")
    parser.add_argument("engagement_dir", help="the engagement folder")
    ns = parser.parse_args()

    folder = Path(ns.engagement_dir)
    recorded = read_events(folder)
    print(f"\n{path_for(folder)}")
    print(f"  events: {len(recorded)}")
    if recorded:
        print(f"  first:  {recorded[0][AT_KEY]}  ({recorded[0][EVENT_KEY]})")
        print(f"  last:   {recorded[-1][AT_KEY]}  ({recorded[-1][EVENT_KEY]})")
        counts: dict[str, int] = {}
        for one in recorded:
            counts[one[EVENT_KEY]] = counts.get(one[EVENT_KEY], 0) + 1
        print("  by event: " + ", ".join(f"{k} {n}" for k, n in sorted(counts.items())))
    print(f"  rows:   {len(fold(recorded))}")
    print(f"  statuses: {len(statuses(recorded))}")
    print(f"  head:   {head(folder) or '(none)'}\n")
