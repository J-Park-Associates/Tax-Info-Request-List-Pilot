"""The household order hint: which household a pass serves first, kept
beside the store from one pass to the next.

Each part upholds the decision rows it names:

- **Least recently completed first** (decision 189, SPEC-161 ruling 2).
  :data:`PASS_ORDER_FILENAME` holds, per household folder name, when the
  household last completed a pass, how many passes running it was not
  served, and when the last pass started and ended it. :func:`_completed_key`
  orders a pass by it - the oldest completion first, one never completed
  before any, ties in the walk's order - so a household that ran out of
  time, was stopped or was held by another run's lock goes first next time
  rather than starving behind the same households every pass. A household
  a pass was killed in (started, never ended) goes last, so one that stalls
  past Task Scheduler's limit is not first, and killed, every pass.
- **Only ever a hint** (decision 189; SPEC 2.3, the review's S1).
  :func:`_read_order_hint` reads at most :data:`PASS_ORDER_MAX_BYTES` (4 MiB
  since pilot P217: some 30,000 households), trusts no file past the
  versions it reads (:data:`_PASS_ORDER_READ`), and turns every error
  reading or parsing it into the walk's order and one sentence
  (:data:`ORDER_HINT_UNREADABLE`). Nothing in it can stop a pass before its
  first household, nothing but the order and the not-served count reads
  it, and deleting it only resets both. It lives beside the store, in the
  data home (decision 186), so it names households only where the store
  already does and moves with it.
- **A mark as each household starts, the whole once a pass** (pilot P217).
  :func:`_mark_started` appends one line and flushes it through
  ``fsio.full_sync`` before the household's work begins, so decision 189's
  crash mark reaches the disk for a few dozen bytes rather than a whole
  rewrite; :func:`_write_order_hint` replaces the file whole through
  ``fsio.write_text_atomically``, so a pass killed half way leaves the last
  hint and never half of one; :func:`_parsed_order_hint` folds in the marks
  a killed pass left and skips a torn last one.
- **Who was not served** (decision 189). :func:`_keep_the_order` folds the
  pass into the hint and names every household not served two passes
  running (:data:`NOT_SERVED_TWICE`, with :func:`_why_not_served`'s reason),
  which the pass exits as ``tracker.runner.NOT_SERVED_TWICE_EXIT_CODE``. A
  dry run keeps, counts and names nothing.

**Where it came from** (SPEC-architecture-p5 P5.10, P347; the architecture
audit's C-5). Moved byte for byte out of ``tracker.runner``, with its words
and comments; the runner imports back by name what its own code still
reads - the read, the order key, the mark, the whole write and the fold
that ``tracker.runner.run_registry`` calls, :func:`_working`, which its
retry of a household held by a lock asks too, and
:data:`PASS_ORDER_FILENAME`, which ``tracker.runner.left_behind`` names
beside the settings file. ``tracker.runner.NOT_SERVED_TWICE_EXIT_CODE``
stayed in the runner: the exit code is the pass's to give. The run log's
codes for the hint (``CODE_ORDER_HINT_UNREADABLE``, ``CODE_NOT_SERVED_TWICE``)
are ``tracker.run_log``'s, beside the report records the hint reads and
adds its warnings to (:func:`tracker.run_log._warn`).

**Why it sits at layer 4.** It imports the pass's report records and codes
(``tracker.run_log``, layer 3), the store (layer 1), and ``fsio`` and
``errors`` (layer 0). Nothing it imports is above layer 3, so layer 3 would
hold too; it sits at layer 4, beside the runner that alone calls it, where
the plan put it (SPEC-architecture-p5 section 2.1), and moving it later is
a decision row. It imports neither ``scheduling`` nor the API (P313), nor
the runner, which imports it, nor :mod:`tracker.screen_words`: the
scheduled pass loads this module, and ``tests/test_layers.py`` keeps the
product's name, which that pass is not given (P220), out of everything it
loads.

It logs as ``tracker.runner`` (``logging.getLogger("tracker.runner")``), the
name its lines have always carried: the error log prints each line's logger
name, so a new one would change lines a person reads (P331's rule;
SPEC-architecture-p5 section 2.1).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

from tracker import errors, store
from tracker.fsio import full_sync, write_text_atomically
from tracker.run_log import (
    CODE_NOT_SERVED_TWICE,
    CODE_ORDER_HINT_UNREADABLE,
    EngagementRun,
    RunReport,
    _warn,
    why_skipped,
)

log = logging.getLogger("tracker.runner")


#: The hint of when each household last completed a pass (decision 189),
#: beside the store, so it holds household names only where the store
#: already does and moves with it. A hint, never a record: nothing but the
#: order and the not-served count reads it, and deleting it resets both.
#:
#: **Version 2 is JSON lines** (pilot P217): line 1 is the whole hint,
#: compact, written once a pass; each further line is one household's
#: start mark, appended (and synced) as the household starts, so decision
#: 189's crash mark costs a few dozen bytes instead of a whole rewrite.
#: The next whole write folds the marks into line 1. Version 1 (one
#: indented object) is still read.
PASS_ORDER_FILENAME = "pass-order.json"
PASS_ORDER_VERSION = 2
#: The versions read: today's, and the one indented object before it.
_PASS_ORDER_READ = (1, PASS_ORDER_VERSION)
#: The largest hint read (the review's S1): a file past it is not parsed.
#: About 125 bytes a household on line 1 and a few dozen a mark: room for
#: some 30,000 households (P217 - at 64 KiB a hint was unreadable from
#: about 370 households up, and the order was lost); anything this large
#: is not a hint.
PASS_ORDER_MAX_BYTES = 4 * 1024 * 1024
ORDER_HINT_UNREADABLE = ("the pass order could not be read; households ran in folder order "
                         "this pass")
NOT_SERVED_TWICE = "{household} has not been served for {n} passes running ({why})"
#: Why a household was not served, as the sentence above says it.
WHY_OUT_OF_TIME = "ran out of time"
WHY_HELD_LOCK = "held lock"
WHY_NO_ROOM = "no room"
WHY_FAILED = "failed"
WHY_CANCELLED = "stopped by a person"
#: A scheduled pass off Windows that ended itself at the run limit (SPEC-mac
#: R26): no person stopped it, so it is not :data:`WHY_CANCELLED`.
WHY_RUN_LIMIT = "reached the run limit"


def _working(runs: list[EngagementRun]) -> list[EngagementRun]:
    """A household's runs that were owed a pass: not rolled forward, not
    inactive - those skips are not failures and serve nothing."""
    return [run for run in runs if not why_skipped(run.engagement)[0]]


def _read_order_hint(report: RunReport) -> tuple[Path | None, dict, bool]:
    """Where the pass-order hint lives, what it says, by household folder
    name, and whether it is **settled** - version 2 on one line, with no
    marks after it (P217). Missing is the walk's order in silence; there and
    unreadable is the walk's order and :data:`ORDER_HINT_UNREADABLE`.

    The whole file parsed as one object of a version read
    (:data:`_PASS_ORDER_READ`) is the hint. Otherwise line 1 must be a
    version 2 hint, and each further line naming a string ``household``
    and ``started`` is folded in order, the later winning; a line that does
    not parse - the torn end of an append the machine died in - is skipped
    with a debug line, never a warning.

    **Only ever a hint** (SPEC 2.3; the review's S1): a file past
    :data:`PASS_ORDER_MAX_BYTES` is not parsed, and every error reading or
    parsing it - a nested file's ``RecursionError`` and a ``MemoryError``
    included - is the walk's order, said once. Nothing in it can stop a
    pass before its first household."""
    try:
        path = store.store_path().parent / PASS_ORDER_FILENAME
    except Exception as exc:
        log.warning("Could not tell where the pass order lives (%s)", errors.error_class(exc))
        _warn(report, CODE_ORDER_HINT_UNREADABLE, ORDER_HINT_UNREADABLE)
        return None, {}, False
    try:
        with path.open("rb") as handle:
            raw = handle.read(PASS_ORDER_MAX_BYTES + 1)
        if len(raw) > PASS_ORDER_MAX_BYTES:
            raise ValueError("past the hint's size")
        hint, settled = _parsed_order_hint(raw.decode("utf-8"))
    except FileNotFoundError:
        return path, {}, False
    except Exception as exc:
        log.warning("Could not read %s (%s)", path.name, errors.error_class(exc))
        _warn(report, CODE_ORDER_HINT_UNREADABLE, ORDER_HINT_UNREADABLE)
        return path, {}, False
    if hint is None:
        _warn(report, CODE_ORDER_HINT_UNREADABLE, ORDER_HINT_UNREADABLE)
        return path, {}, False
    return path, hint, settled


def _hint_households(payload, versions: tuple[int, ...]) -> dict | None:
    """The households of one parsed hint object of a version in
    ``versions``, keeping only entries that are objects; None for anything
    else."""
    households = payload.get("households") if isinstance(payload, dict) else None
    if not isinstance(households, dict) or payload.get("version") not in versions:
        return None
    return {name: entry for name, entry in households.items() if isinstance(entry, dict)}


def _parsed_order_hint(text: str) -> tuple[dict | None, bool]:
    """The hint a pass-order file's text holds and whether it is settled,
    or ``(None, False)`` for one that is not a hint (P217)."""
    try:
        whole = json.loads(text)
    except ValueError:
        whole = None
    else:
        hint = _hint_households(whole, _PASS_ORDER_READ)
        one_line = "\n" not in text.rstrip("\n")
        return hint, hint is not None and whole.get("version") == PASS_ORDER_VERSION and one_line
    first, _, rest = text.partition("\n")
    try:
        hint = _hint_households(json.loads(first), (PASS_ORDER_VERSION,))
    except ValueError:
        return None, False
    if hint is None:
        return None, False
    for line in rest.split("\n"):
        if not line.strip():
            continue
        try:
            mark = json.loads(line)
        except ValueError:
            # The torn end of an append the machine died in: the mark is
            # lost, the hint is not (decision 189 puts that household last
            # only when its mark reached the disk).
            log.debug("Skipped a torn mark in %s", PASS_ORDER_FILENAME)
            continue
        name = mark.get("household") if isinstance(mark, dict) else None
        at = mark.get("started") if isinstance(mark, dict) else None
        if isinstance(name, str) and isinstance(at, str):
            hint[name] = {**hint.get(name, {}), "started": at}
    return hint, False


def _completed_key(hint: dict, household: Path, at: int) -> tuple:
    """Oldest completion first; never completed before any; ties in the
    walk's order (``at``). An entry that does not read is never completed.

    **A household a pass ended in goes last** (decision 189): its entry
    says it was ``started`` and never ``ended`` - the pass was killed in
    it, or the machine went off - so, for the order, it was served when it
    started. Without this a household that stalls past Task Scheduler's
    limit would be first, and killed, every pass, and every household
    after it in the walk would starve.
    """
    entry = hint.get(household.name, {})
    completed = entry.get("completed") if isinstance(entry.get("completed"), str) else ""
    started, ended = entry.get("started"), entry.get("ended")
    if isinstance(started, str) and not (isinstance(ended, str) and ended >= started):
        return (True, max(completed, started), at)
    return (bool(completed), completed, at)


def _mark_started(path: Path | None, hint: dict, household: Path, *, write: bool) -> None:
    """Say in the hint that this household's pass began, before it does
    anything, so a pass killed in it leaves the mark :func:`_completed_key`
    reads. One line appended, flushed and synced (P217) - on the disk before
    the household's work begins, as the whole rewrite it replaces was. Not
    on a dry run, nor on a hint that could not be settled; a mark that
    cannot be written is a log line."""
    if not write or path is None:
        return
    at = dt.datetime.now().isoformat(timespec="seconds")
    hint[household.name] = {**hint.get(household.name, {}), "started": at}
    line = json.dumps({"started": at, "household": household.name}, ensure_ascii=True,
                      separators=(",", ":")) + "\n"
    try:
        with path.open("ab") as handle:
            handle.write(line.encode("ascii"))
            handle.flush()
            full_sync(handle.fileno())
    except OSError as exc:
        log.warning("Could not mark %s (%s)", path.name, errors.error_class(exc))


def _write_order_hint(path: Path, hint: dict) -> bool:
    """The whole hint as line 1 of a version 2 file, compact and ASCII,
    replacing the file - and every mark in it, which ``hint`` already
    holds (P217). True when it was written."""
    text = json.dumps({"version": PASS_ORDER_VERSION, "households": hint}, ensure_ascii=True,
                      separators=(",", ":")) + "\n"
    try:
        write_text_atomically(path, text, encoding="ascii", newline="\n")
    except OSError as exc:
        # A hint: a pass that cannot keep it runs in the walk's order next
        # time, which is where every pass started before decision 189.
        log.warning("Could not write %s (%s)", path.name, errors.error_class(exc))
        return False
    return True


def _why_not_served(runs: list[EngagementRun]) -> str:
    """Why a household was not served this pass, or "" when it was: every
    working return ended with no error, no skip and not out of time."""
    working = _working(runs)
    if any(run.cancelled for run in working):
        return WHY_CANCELLED
    if any(run.run_limit for run in working):
        return WHY_RUN_LIMIT
    if any(run.out_of_time for run in working):
        return WHY_OUT_OF_TIME
    if any(run.locked_out for run in working):
        return WHY_HELD_LOCK
    if any(run.skipped for run in working):
        return WHY_NO_ROOM
    if any(run.error for run in working):
        return WHY_FAILED
    return ""


def _keep_the_order(report: RunReport, path: Path | None, hint: dict,
                    served: dict[Path, list[EngagementRun]], *, write: bool) -> None:
    """Fold this pass into the hint, name every household not served two
    passes running, and write the hint whole. A dry run does none of it
    (the review's N4): it keeps nothing, so it counts nothing, names no
    household and never exits :data:`tracker.runner.NOT_SERVED_TWICE_EXIT_CODE`."""
    if not write:
        return
    now = dt.datetime.now().isoformat(timespec="seconds")
    for household, runs in served.items():
        entry = dict(hint.get(household.name, {}))
        entry["ended"] = now
        why = _why_not_served(runs)
        if why:
            count = entry.get("not_served")
            entry["not_served"] = (count if isinstance(count, int) and count >= 0 else 0) + 1
            entry.setdefault("completed", None)
            if entry["not_served"] >= 2:
                report.not_served_twice.append(household.name)
                _warn(report, CODE_NOT_SERVED_TWICE, NOT_SERVED_TWICE.format(
                    household=household.name, n=entry["not_served"], why=why))
        else:
            entry.update(completed=now, not_served=0)
        hint[household.name] = entry
    if path is not None:
        _write_order_hint(path, hint)
