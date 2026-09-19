"""The machine's own record of one engagement, appended to and never rewritten.

Every fact the system holds about an engagement lives today in a workbook a
person can open, sort, re-type and save from Excel - and each of the readings
in the decision log found another way that ends with a row lost. The
workbooks stay; beside them each engagement now keeps ``LEDGER_FILENAME``, one
JSON object per line, in the order the writers wrote them. It is the record
of *what was decided*; the workbooks remain the thing a person reads.

**The readers believe it, and fall back to the workbooks** (decision 88,
stage A step 2). :func:`tracker.filer.read_index` answers from :func:`fold`
wherever the record holds an index-shaped event, and
:func:`tracker.manifest.load_manifest` takes each identifier's scanner
columns from :func:`statuses` wherever the record has ever recorded one -
per identifier, so a row the record has never seen still reads off the
workbook. An engagement with no record here reads exactly as it always did,
which is what makes the step reversible: delete the file and the workbooks
answer again. Both workbooks are still written exactly as before; dropping a
write is stage B.

What made that safe to switch on is the agreement fixture in
``tests/conftest.py``: after every test in the suite, the record is folded
back and compared with the *workbooks' own* readings
(``filer.read_index_from_workbook()``, ``manifest.statuses_from_workbook()``,
kept public for exactly this). ``python -m tracker.ledger <folder> --compare``
is the same check for one engagement, for a person.

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

**Not a database, here.** SQLite was the obvious answer and is the wrong
one *in the engagement folder*: the folders are synced by a cloud client
between the office machine and the drive, and a synced database file is a
corrupted database file. A text file that only ever grows is what a sync
client can carry. Decision 101 adds the database the other side of that
line - :mod:`tracker.store`, one file per clients root on the designated
machine's own disk, never synced and never in a folder - and it is built
*from* this file: the journal is what is written first and what survives,
the store is what is rebuilt. Together they are the record; this file
alone is the ledger.

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
from dataclasses import dataclass, field
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
#: What a ``KEYWORD_LEARNED`` event carries: the request a person's filing
#: taught, and the word it was taught. Named here beside the other event
#: keys so the writer and every reader of the record spell them once.
IDENTIFIER_KEY = "identifier"
KEYWORD_KEY = "keyword"

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
    return {EVENT_KEY: name, AT_KEY: stamp(), **payload}


def stamp() -> str:
    """Now, as everything the record stamps says it: UTC, to the second.

    UTC because the office machine's clock is local and a daylight-saving
    hour would otherwise put two passes out of order. Public because the
    store (:func:`tracker.store.rebuild_engagement`) stamps when it built
    its rows, and two stamps in one record written two ways would be two
    formats to read back.
    """
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

    **In the index's order.** The rows come back in the order the record
    first saw each original, and a row that changed identity keeps the place
    the one it left held, because the index keeps it too: the writer rewrites
    that row where it sits rather than moving it to the end. Since
    :func:`tracker.filer.read_index` answers from this fold, an order that
    drifted from the workbook's would reorder the audit trail on the next
    write.

    An event whose name this version does not know as index-shaped is passed
    over rather than refused: a later version may write one, and a reader
    that refuses what it does not know cannot read a record written by the
    run after it.
    """
    return replay(events).rows


def statuses(events: list[dict]) -> dict[str, dict]:
    """The last status each identifier was scanned to, by identifier.

    A pass appends only what it changed, so the answer is built up across
    every ``SCANNED`` event rather than read off the last one.
    """
    return replay(events).statuses


@dataclass
class Folded:
    """What the record adds up to so far: the index, and the statuses.

    A plain pair rather than two answers, because :func:`apply` folds one
    event into both and a reader replaying the record line by line
    (:mod:`tracker.store`) needs to carry both between lines.
    """

    rows: dict[str, dict] = field(default_factory=dict)
    statuses: dict[str, dict] = field(default_factory=dict)


def apply(state: Folded, event: dict) -> Folded:
    """One event folded into what the record said before it. Returns ``state``.

    **The whole of both fold rules, in one place.** :func:`fold` and
    :func:`statuses` are this function over a whole file, and the store of
    decision 101 is this function over the lines it has not applied yet -
    so an index that is replayed a line at a time and one that is folded
    from the start cannot come out different. Anything that has to change
    about what an event means changes here.

    ``state.rows`` is mutated where it can be; a row that arrived from
    another identity is the one case that cannot be, because a dict cannot
    re-key in place and the row keeps the place the one it left held, so
    the mapping is rebuilt around it and assigned back.

    An event whose name this version does not know as index-shaped and is
    not a scan is passed over rather than refused: a later version may
    write one, and a reader that refuses what it does not know cannot read
    a record written by the run after it.
    """
    name = event.get(EVENT_KEY)
    if name == SCANNED:
        state.statuses.update(event.get(STATUSES_KEY) or {})
        return state
    if name not in ROW_EVENTS:
        return state
    key = event.get(KEY_KEY)
    if key is None:
        raise LedgerError(f"an index-shaped {name!r} event carries no {KEY_KEY!r}")
    was = event.get(WAS_KEY)
    if was and was != key:
        if was in state.rows and key not in state.rows:
            # Renamed where it stands: a dict cannot re-key in place, so
            # the row order is rebuilt around it rather than the row
            # being dropped and appended at the end.
            state.rows = {(key if held == was else held): row for held, row in state.rows.items()}
        else:
            state.rows.pop(was, None)
    state.rows[key] = event[ROW_KEY]
    return state


def replay(events: list[dict]) -> Folded:
    """Every event folded, oldest first: the index and the statuses together.

    One walk for a caller that wants both, and the definition :func:`fold`
    and :func:`statuses` are each one half of.
    """
    state = Folded()
    for event in events:
        apply(state, event)
    return state


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

    def _compare_with_the_workbooks(folder: Path, events: list[dict]) -> int:
        """Print whether the record and the workbooks agree, and name every
        place they do not. Returns the exit code: 0 agree, 1 disagree.

        The operator's check (``docs/runbook.md``). Both sides of it are the
        workbooks' *own* readings - ``filer.read_index_from_workbook()`` and
        ``manifest.statuses_from_workbook()`` - because since decision 88 the
        live readers answer from the record, and asking them would only be
        the record compared with itself.

        Imported here rather than at the top of the module: this module sits
        at the bottom of the package beside :mod:`tracker.locking` and
        imports nothing else of it, and a command line nobody imports is the
        one place that may look upwards.
        """
        from tracker.filer import INDEX_FILENAME, ledger_key, read_index_from_workbook
        from tracker.manifest import statuses_from_workbook
        from tracker.scaffold import MANIFEST_FILENAME

        disagreements: list[str] = []
        index_path, manifest_path = folder / INDEX_FILENAME, folder / MANIFEST_FILENAME

        folded = fold(events)
        workbook_rows = {
            ledger_key(entry): {f: getattr(entry, f) for f in entry.__dataclass_fields__}
            for entry in read_index_from_workbook(index_path, quarantine=False)
        }
        print(f"  rows:     {len(folded)} recorded, {len(workbook_rows)} in {INDEX_FILENAME}")
        for key in folded:
            if key not in workbook_rows:
                disagreements.append(f"  rows      {key}: recorded, and {INDEX_FILENAME} does not hold it")
        for key, row in workbook_rows.items():
            if key not in folded:
                disagreements.append(f"  rows      {key}: in {INDEX_FILENAME}, and the record does not hold it")
                continue
            for field, value in row.items():
                if folded[key].get(field) != value:
                    disagreements.append(
                        f"  rows      {key}, {field}: the record says {folded[key].get(field)!r}, "
                        f"{INDEX_FILENAME} says {value!r}"
                    )
        if set(folded) == set(workbook_rows) and list(folded) != list(workbook_rows):
            disagreements.append(
                f"  rows      the same originals in a different order: the record has "
                f"{list(folded)}, {INDEX_FILENAME} has {list(workbook_rows)}"
            )

        recorded_statuses = statuses(events)
        workbook_statuses = (
            {i.lower(): s for i, s in statuses_from_workbook(manifest_path).items()}
            if manifest_path.is_file() else {}
        )
        gone = 0
        for identifier, status in recorded_statuses.items():
            theirs = workbook_statuses.get(identifier.lower())
            if theirs is None:
                # A row deleted or renamed in Excel since the scan is dropped
                # by the write-back and by the pending overlay alike; the
                # record is right that the status was written.
                gone += 1
            elif theirs != status:
                disagreements.append(
                    f"  statuses  {identifier}: the record says {status!r}, "
                    f"{MANIFEST_FILENAME} says {theirs!r}"
                )
        print(f"  statuses: {len(recorded_statuses)} recorded, {len(workbook_statuses)} in {MANIFEST_FILENAME}"
              + (f" ({gone} recorded for a row the manifest no longer carries)" if gone else ""))

        if disagreements:
            print(f"\n  they do not agree ({len(disagreements)}):")
            for line in disagreements:
                print(line)
            print()
            return 1
        print("\n  the record and the workbooks agree\n")
        return 0

    parser = argparse.ArgumentParser(description="Show one engagement's own record")
    parser.add_argument("engagement_dir", help="the engagement folder")
    parser.add_argument(
        "--compare", action="store_true",
        help="check the record against _index.xlsx and _manifest.xlsx, row by row and "
             "status by status, naming every disagreement; exit 1 if they disagree",
    )
    ns = parser.parse_args()

    folder = Path(ns.engagement_dir)
    recorded = read_events(folder)
    if ns.compare:
        print(f"\n{path_for(folder)} against the workbooks beside it")
        raise SystemExit(_compare_with_the_workbooks(folder, recorded))
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
