"""The machine's own record of one engagement, appended to and never rewritten.

Every fact the system holds about an engagement used to live in a workbook a
person can open, sort, re-type and save from Excel - and each of the readings
in the decision log found another way that ends with a row lost. Each
engagement now keeps ``LEDGER_FILENAME`` instead, one JSON object per line,
in the order the writers wrote them. It is the record of *what was decided*.

**It is the index** (decision 102). What a pass decides about a document is
appended here and folded into :mod:`tracker.store`, and
:func:`tracker.filer.read_index` answers from those folded rows. The
journal and the store are the only two copies of the index, and the store
is rebuilt from the journal. (A journal from before decision 104 may carry
a :data:`MIGRATED` event, from the one-time migration of an index
workbook; nothing writes one now.)

**It is the statuses too** (decision 103). A scan appends one
:data:`SCANNED` event with what it changed, a person's filing appends
:data:`KEYWORD_LEARNED` beside the row it taught, and
:func:`tracker.manifest.load_manifest` answers from the store these lines
are folded into.

**And it is the person's own rules** (decisions 103 and 104). The request
list and the engagement's details are created, edited and read only here:
the app's editor is the one way a rule is entered, and every save is one
:data:`RULES_CHANGED` event carrying exactly the difference - the changed
and added rows whole, the removed identifiers, the Engagement fields that
moved. That is what makes the store rebuildable from the journals alone -
without it, an engagement's rules would live only in a database that is
meant to be disposable. Until decision 104 the list was a workbook read
once a pass and its differences were journalled as :data:`RULES_IMPORTED`;
that name is retired (:data:`RETIRED_EVENTS`): this version folds it,
because journals from before today carry it, and refuses to write it.

What keeps it honest is the agreement fixture in ``tests/conftest.py``:
after every test in the suite a store built from nothing is held to
:func:`replay` over these lines - the index rows, the statuses and the
rules alike. ``python -m tracker.store <store> check <root>`` is that check
for one practice, for a person.

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
and imports nothing else of the package: every writer serialises its own
rows with the function in :mod:`tracker.records` that already owns that
shape (an index row, a status, a rule row, the engagement's details). One
owner per fact, and no cycle.
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

#: The engagement's own record, beside the client's files. A person never edits it.
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
#: What a ``MIGRATED`` event carried: the files the migration moved aside,
#: by the names they then had. It carries no row - it is a statement about
#: the folder, not about a document - which is why it is not a row event.
FILES_KEY = "files"
#: What a ``RULES_CHANGED`` event carries. The rows are whole records -
#: every one that was added or changed, as ``tracker.records.rule_to_json``
#: serialises it - rather than a patch, because a patch cannot be read
#: without the row it patches and the whole point of the journal is that a
#: line means something on its own. ``REMOVED_KEY`` is the identifiers the
#: person removed from the list, ``INFO_KEY`` the Engagement fields that
#: changed (``tracker.records.info_to_json``'s names). A retired
#: ``RULES_IMPORTED`` line carries the same three and a workbook digest
#: under a fourth key, which is simply not read.
RULES_KEY = "rules"
REMOVED_KEY = "removed"
INFO_KEY = "info"

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
#: The person's request list or Engagement details were edited in the app
#: (decision 104): the changed and added rows whole (``RULES_KEY``), the
#: removed identifiers (``REMOVED_KEY``), the Engagement fields that moved
#: (``INFO_KEY``). The first one - the create - carries the whole list and
#: every field, every one after it only what moved, so the fold of them
#: all is the list. Written by ``tracker.manifest.create_engagement`` and
#: ``save_rules`` and by nothing else.
RULES_CHANGED = "rules_changed"
#: What decision 103 called the same event, when the list was a workbook
#: read once a pass. Retired by decision 104: journals from before it
#: carry these lines, so :func:`apply` folds them exactly as
#: ``RULES_CHANGED``, and :func:`new`, :func:`append` and
#: ``tracker.store.record`` refuse to write one.
RULES_IMPORTED = "rules_imported"
#: A reminder was drafted. Reserved: the reminder writes files and holds no
#: lock, so nothing appends it yet.
DRAFTED = "drafted"
#: A row seeded into the record from an earlier reading of the index: the
#: bootstrap of decision 87 and the migration of decision 102 wrote these,
#: and the suite's ``seed_index`` still does.
IMPORTED = "imported"
#: The index workbook was moved aside, and this engagement's index now lives
#: in the record alone (decision 102). Written once per engagement, after the
#: rename, carrying :data:`FILES_KEY`. It carries no row, so it is
#: deliberately *not* a row event: a reader that folded it as one would
#: look for a row that was never there. Nothing writes one since decision
#: 104 took the migration out of the tree; it stays readable.
MIGRATED = "migrated"

#: The events that carry a whole index row. Their fold is the index.
ROW_EVENTS = frozenset({
    PRESERVED, FILED, PARKED, DUPLICATE, ASSIGNED_BY_PERSON, DISMISSED_BY_PERSON,
    UNFILED_BY_PERSON, BYTES_RECORDED, IMPORTED,
})
#: Every event name this version reads.
EVENTS = ROW_EVENTS | frozenset({SCANNED, KEYWORD_LEARNED, DRAFTED, MIGRATED, RULES_CHANGED,
                                 RULES_IMPORTED})
#: The names this version reads and never writes: an older journal may
#: carry them, a new line may not.
RETIRED_EVENTS = frozenset({RULES_IMPORTED})
#: How a retired name is refused, wherever it is offered for writing.
RETIRED_EVENT = "{name!r} is retired; this version reads it and never writes it"

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
    _writable(name)
    return {EVENT_KEY: name, AT_KEY: stamp(), **payload}


def _writable(name: object) -> None:
    """Refuse a name this version does not write: an unknown one, or a
    retired one an older journal may carry but a new line may not."""
    if name in RETIRED_EVENTS:
        raise LedgerError(RETIRED_EVENT.format(name=name))
    if name not in EVENTS:
        raise LedgerError(f"{name!r} is not an event this version writes ({', '.join(sorted(EVENTS - RETIRED_EVENTS))})")


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


def append(engagement_dir: Path | str, event: dict) -> Path:
    """Append one event to the engagement's record. Returns the file.

    Refuses unless this process holds the engagement lock: the record is
    written in the same locked section as the decision it records, after
    that decision's files have been moved. A silent append outside the lock
    is exactly the line that goes missing later.

    There is no bootstrap here any more. Decision 87 let the first writer
    seed the record with what the workbooks already said; since decision
    104 nothing but the record holds anything, so there is nothing to seed
    from. A retired name is refused by sentence.
    """
    engagement_dir = Path(engagement_dir)
    name = event.get(EVENT_KEY)
    _writable(name)
    if not lock_is_held(engagement_dir):
        raise LedgerError(
            f"{engagement_dir.name}: the record is appended to only while this run holds the "
            f"engagement lock; {name!r} was not written"
        )
    path = path_for(engagement_dir)
    _truncate_torn_tail(path)
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
    the one it left held: the writer rewrites that row where it sits rather
    than moving it to the end. The order is the audit trail's own and there
    is no second copy of it to drift from - :mod:`tracker.store` lays its
    ``position`` column from this fold, and
    :func:`tracker.filer.read_index` reads it back.

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


def rules(events: list[dict]) -> dict[str, dict]:
    """The person's request rows as the record last left them, by
    identifier, in the order the record first saw each one.

    Empty where no rules event has ever been appended: an engagement whose
    list nobody has recorded, which since decision 104 is not an
    engagement anything runs.
    """
    return replay(events).rules


@dataclass
class Folded:
    """What the record adds up to: the index, the statuses and the rules.

    One state rather than four answers, because :func:`apply` folds one
    event into all of them and a reader replaying the record line by line
    (:mod:`tracker.store`) needs to carry the lot between lines.
    """

    rows: dict[str, dict] = field(default_factory=dict)
    statuses: dict[str, dict] = field(default_factory=dict)
    #: identifier -> the person's rule row, as ``records.rule_to_json``
    #: writes it. Keyed by the identifier as the person spelt it; the
    #: validation refuses two rows whose identifiers differ only in case,
    #: so one spelling per row is all there can be.
    rules: dict[str, dict] = field(default_factory=dict)
    #: The engagement's details, as ``records.info_to_json`` writes them.
    #: Only the ones any edit has ever recorded: a field nothing has spoken
    #: for is the record's default, not a blank somebody typed.
    info: dict[str, object] = field(default_factory=dict)


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
    if name in (RULES_CHANGED, RULES_IMPORTED):
        return _apply_rules_event(state, event)
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


def _apply_rules_event(state: Folded, event: dict) -> Folded:
    """One edit folded: the identifiers it names as removed go first, then
    the rows it carried replace the rows of those identifiers, and the
    Engagement fields it carried are set. The same fold for a
    ``RULES_CHANGED`` line and for the retired ``RULES_IMPORTED`` an older
    journal carries.

    Removals before rows, because a rule is keyed by its identifier's
    exact spelling and an edit that respells one by case names the old
    spelling as removed and carries the new: applied the other way round,
    a removal spelled the way the store held it would delete the row just
    written and the list would lose the rule.

    A row the edit does not mention is untouched: an edit carries what
    moved and nothing else, so the fold of every edit is the list. The
    list's own order is not this mapping's - it is the ``row`` each rule
    carries, its position in the list - so a row added in the middle folds
    at the end here and still comes back in its place
    (:func:`tracker.store.rules`).
    """
    for identifier in event.get(REMOVED_KEY) or []:
        state.rules.pop(str(identifier), None)
    for row in event.get(RULES_KEY) or []:
        identifier = str(row.get("identifier", ""))
        if identifier:
            state.rules[identifier] = row
    state.info.update(event.get(INFO_KEY) or {})
    return state


def replay(events: list[dict]) -> Folded:
    """Every event folded, oldest first: the index, the statuses and the rules.

    One walk for a caller that wants all of them, and the definition
    :func:`fold`, :func:`statuses` and :func:`rules` are each one part of.
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

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(description="Show one engagement's own record")
    parser.add_argument("engagement_dir", help="the engagement folder")
    ns = parser.parse_args()

    # There is nothing left here to compare with a workbook. Until decision
    # 103 the manifest carried each request's status as well, and
    # ``--compare`` was the operator's check that the two agreed; the
    # record holds everything now, the person's rules included, and the
    # check that matters is the store against this file - ``python -m
    # tracker.store <store> check <clients root>``.
    folder = Path(ns.engagement_dir)
    recorded = read_events(folder)
    folded = replay(recorded)
    print(f"\n{path_for(folder)}")
    print(f"  events: {len(recorded)}")
    if recorded:
        print(f"  first:  {recorded[0][AT_KEY]}  ({recorded[0][EVENT_KEY]})")
        print(f"  last:   {recorded[-1][AT_KEY]}  ({recorded[-1][EVENT_KEY]})")
        counts: dict[str, int] = {}
        for one in recorded:
            counts[one[EVENT_KEY]] = counts.get(one[EVENT_KEY], 0) + 1
        print("  by event: " + ", ".join(f"{k} {n}" for k, n in sorted(counts.items())))
    print(f"  rows:     {len(folded.rows)}")
    print(f"  statuses: {len(folded.statuses)}")
    print(f"  rules:    {len(folded.rules)}")
    print(f"  head:     {head(folder) or '(none)'}\n")
