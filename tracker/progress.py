"""How a running pass is watched from outside, and asked to stop (decision 193).

A pass used to be a black box: the app spawned it, heard nothing for up
to thirty minutes, and got one JSON object at exit - or a kill. This
module is the **one format** a pass says where it is in, with two
carriers, so nothing has a second copy of the shape to drift:

* a **stdout line** - ``{"progress": {...}}``, ASCII, one line - printed
  before the reply when the shell spawned the process. The reply is the
  only stdout line without :data:`PROGRESS_KEY`, and it is always last;
* a **progress file** - the latest line, rewritten whole - kept under
  :data:`PASSES_DIRNAME` beside the tracker's database, for any other
  process: the app's lock notice reads it to name the file a pass on this
  machine is on, and decision 203's detached pass reuses it. It is a
  hint: written without a sync to disk, and a write that fails is
  skipped (the next line catches it up).

**Stop is a marker file, not a signal or stdin.** Windows has no SIGINT
for a hidden child, and a stdin reader needs a thread and works only for
a child the shell owns. ``<id>.cancel`` beside the pass's progress file
names that pass and no other, and the sort and the scan look for it once
per file or request (:meth:`Watch.stop_asked`) - so a stop lands between
files, where decision 119 says nothing is half-moved, and it brings
decision 189's household deadline to now rather than adding a second
way to stop. **Only a pass this app started can be stopped** (the lane's
ruling on decision 193): a :class:`Watch` that prints no lines - the
scheduled pass - never looks for a marker, and :func:`ask_to_stop`
refuses one whose progress file does not say it may be stopped.

L0: it imports nothing of the package at load time, so the runner, the
filer and the scanner can take a :class:`Watch` without reaching up to
:mod:`tracker.api`; :func:`tracker.locking.pid_alive` is imported at call
time, to tell a dead pass's leftovers from a live one's. It holds no clock
of its own: the budget stays decision 189's. No network module, like the
rest of the package.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

#: The one key a progress line carries its fields under. The shell types
#: it once too (``app/main.js``), pinned to this by ``test_single_source``.
PROGRESS_KEY = "progress"
FORMAT_VERSION = 1
#: What a line can say: the pass began (with its run limit), it is on a
#: household, it is on a file or request, a stop was seen, it ended.
EVENTS = ("started", "household", "file", "stopping", "ended")
#: How a pass ended, on its ``ended`` line.
OUTCOMES = ("finished", "stopped", "out_of_time", "failed")
#: The folder the progress files and the cancel markers live in, beside
#: the tracker's database - never in either client tree.
PASSES_DIRNAME = "passes"
PROGRESS_SUFFIX = ".json"
CANCEL_SUFFIX = ".cancel"
_TEMP_SUFFIX = ".tmp"
#: A progress file past this is not parsed: a hint, never a burden.
PROGRESS_MAX_BYTES = 4096
#: A name longer than this is cut on a line, so one line stays inside
#: :data:`PROGRESS_MAX_BYTES` whatever a client called a file.
NAME_MAX_CHARS = 200


#: How a failure is said to a person (decision 193): the record moved
#: under them (look again), another pass holds the return (wait), the
#: tracker refused in its own words, or something it did not expect.
FAILURE_KINDS = ("stale", "locked", "refused", "failed")


def failure_reply(sentence: str, kind: str, *, seq: int | None = None,
                  identifier: str | None = None, warnings: list[str] | tuple = (),
                  **extra) -> dict:
    """The one error envelope (decision 193): ``error`` is the sentence,
    ``failure`` carries it again with its kind and the row it was about,
    and ``warnings`` is always a list. Built here, once, so ``error`` and
    ``failure.sentence`` can never disagree, and so a pass that is not the
    API (decision 203's detached runner) says a failure the same way.
    ``extra`` joins ``failure`` (the lock a ``locked`` failure met)."""
    if kind not in FAILURE_KINDS:
        raise ValueError(f"not a failure kind: {kind!r}")
    failure = {"sentence": sentence, "kind": kind,
               "seq": seq if isinstance(seq, int) and not isinstance(seq, bool) else None,
               "identifier": identifier if isinstance(identifier, str) and identifier else None,
               **extra}
    return {"error": sentence, "failure": failure, "warnings": list(warnings)}


def passes_dir(folder: Path) -> Path:
    return Path(folder) / PASSES_DIRNAME


def _progress_file(folder: Path, pass_id: int) -> Path:
    return passes_dir(folder) / f"{int(pass_id)}{PROGRESS_SUFFIX}"


def _cancel_file(folder: Path, pass_id: int) -> Path:
    return passes_dir(folder) / f"{int(pass_id)}{CANCEL_SUFFIX}"


def _fields(pass_id: int, event: str, fields: dict) -> dict:
    if event not in EVENTS:
        raise ValueError(f"not a progress event: {event!r}")
    said = {"v": FORMAT_VERSION, "pass": int(pass_id), "event": event,
            "at": dt.datetime.now().isoformat(timespec="seconds")}
    for key, value in fields.items():
        if isinstance(value, str) and len(value) > NAME_MAX_CHARS:
            value = value[:NAME_MAX_CHARS - 1] + "…"
        said[key] = value
    return said


def line(pass_id: int, event: str, **fields) -> str:
    """One progress line: one ASCII JSON object under :data:`PROGRESS_KEY`,
    ending in a newline, so a reader splitting stdout on newlines can never
    see half of one."""
    return json.dumps({PROGRESS_KEY: _fields(pass_id, event, fields)}, ensure_ascii=True) + "\n"


def _read_bounded(path: Path) -> dict | None:
    try:
        with path.open("rb") as handle:
            raw = handle.read(PROGRESS_MAX_BYTES + 1)
        if len(raw) > PROGRESS_MAX_BYTES:
            return None
        payload = json.loads(raw.decode("utf-8"))
    except Exception:  # a hint: anything wrong with it is no hint
        return None
    return payload if isinstance(payload, dict) else None


def read_latest(folder: Path, pass_id: int) -> dict | None:
    """The latest line a pass wrote to its progress file, or None when
    there is none or it does not read. Bounded, and never raises."""
    try:
        payload = _read_bounded(_progress_file(folder, pass_id))
    except Exception:
        return None
    said = payload.get(PROGRESS_KEY) if payload else None
    return said if isinstance(said, dict) else None


def _alive(pass_id: int) -> bool | None:
    from tracker.locking import pid_alive

    try:
        return pid_alive(pass_id)
    except Exception:
        return None


def ask_to_stop(folder: Path, pass_id: int) -> bool:
    """Write the cancel marker for ``pass_id``, and say whether there was a
    live pass there to ask: False - and nothing written - when it has no
    progress file, its process is gone, or it is a pass that may not be
    stopped from here (one the app did not start)."""
    try:
        payload = _read_bounded(_progress_file(folder, pass_id))
        if not payload or payload.get("stoppable") is not True or _alive(pass_id) is False:
            return False
        _cancel_file(folder, pass_id).write_bytes(b"")
    except (OSError, ValueError, TypeError):
        return False
    return True


class Watch:
    """One pass's progress: said as lines (``emit``) and kept in its
    progress file (``folder``), and its cancel marker looked for.

    ``folder`` None keeps no file (a test, or a pass that could not tell
    where its database lives); ``emit`` None prints nothing - the scheduled
    pass, which still fills the file for the lock notice and is never
    stopped from here. ``pass_id`` is the process id unless given.
    """

    def __init__(self, folder: Path | None, *, emit: Callable[[str], None] | None = None,
                 limit_seconds: int, pass_id: int | None = None) -> None:
        self.folder = Path(folder) if folder is not None else None
        self.emit = emit
        self.limit_seconds = int(limit_seconds)
        self.pass_id = int(pass_id if pass_id is not None else os.getpid())
        #: Only a pass the app started - one that prints its lines - may
        #: be stopped from outside.
        self.stoppable = emit is not None
        self._stop_seen = False
        self._where: dict = {}
        if self.folder is not None:
            self._sweep()

    # -- the progress file ------------------------------------------------

    def _sweep(self) -> None:
        """Take away what dead passes left - their progress files, markers
        and temps - and anything left under this pass's own id by an
        earlier process that had it. A live pass's files are kept."""
        folder = passes_dir(self.folder)
        try:
            names = list(folder.iterdir()) if folder.is_dir() else []
        except OSError:
            return
        for path in names:
            head = path.name.split(".", 1)[0]
            if not head.isdigit():
                continue
            pid = int(head)
            if pid == self.pass_id or _alive(pid) is False:
                try:
                    path.unlink()
                except OSError:
                    log.debug("Could not remove %s", path.name)

    def _keep(self, said: dict) -> None:
        if self.folder is None:
            return
        target = _progress_file(self.folder, self.pass_id)
        temp = target.with_name(target.name + _TEMP_SUFFIX)
        body = json.dumps({PROGRESS_KEY: said, "stoppable": self.stoppable},
                          ensure_ascii=True).encode("ascii")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temp.write_bytes(body)
            try:
                os.replace(temp, target)
            except PermissionError:
                # Windows, while a reader has it open: once more, then the
                # hint lags a line (the next one catches it up).
                os.replace(temp, target)
        except OSError as exc:
            from tracker import errors  # at call time: L0 imports nothing of the package at load

            log.debug("Could not keep the progress file (%s)", errors.error_class(exc))
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

    # -- saying where the pass is ------------------------------------------

    def say(self, event: str, **fields) -> None:
        """Print the line (when the shell is listening) and keep it in the
        progress file. A ``household`` line sets where later ``file`` lines
        are; ``started`` carries the run limit the shell's kill follows."""
        if event == "started":
            fields.setdefault("limit_seconds", self.limit_seconds)
        if event == "household":
            self._where = {key: fields[key] for key in ("household", "n", "of") if key in fields}
        if event == "file":
            fields = {**self._where, **fields}
        said = _fields(self.pass_id, event, fields)
        if self.emit is not None:
            try:
                self.emit(json.dumps({PROGRESS_KEY: said}, ensure_ascii=True) + "\n")
            except (OSError, ValueError) as exc:
                # Nobody is listening any more; the pass goes on and its
                # reply, not a progress line, is what the record keeps.
                from tracker import errors  # at call time, as above

                log.debug("Could not print a progress line (%s)", errors.error_class(exc))
        self._keep(said)

    def stop_asked(self) -> bool:
        """Whether a person asked this pass to stop: one look for its
        cancel marker, and once seen it stays seen. Always False for a
        pass that may not be stopped from here."""
        if self._stop_seen:
            return True
        if not self.stoppable or self.folder is None:
            return False
        try:
            seen = _cancel_file(self.folder, self.pass_id).exists()
        except OSError:
            seen = False
        if seen:
            self._stop_seen = True
            self.say("stopping")
        return seen

    def close(self, outcome: str) -> None:
        """Say the pass ended and how, then take its files away."""
        if outcome not in OUTCOMES:
            raise ValueError(f"not a pass outcome: {outcome!r}")
        self.say("ended", outcome=outcome)
        if self.folder is None:
            return
        for path in (_progress_file(self.folder, self.pass_id),
                     _cancel_file(self.folder, self.pass_id)):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                log.debug("Could not remove %s", path.name)
