"""One lock per engagement, shared by every step that changes it (component 12).

The filer moves the client's originals and records where each one went;
the scanner records each request's status; the manifest records a person's
edit of the list. Two of any of them running at once on the same
engagement - a scheduled run overlapping a click in the desktop app, or
Task Scheduler's repeat firing while an OCR-heavy pass is still going -
would race on the same files and the same journal, and the loser's rows
would be written from a stale picture. That is the one way an original can
end up in the client's folder for the year with no record of how it got
there, so the lock
is not optional and it is not per step: whoever holds ``LOCK_FILENAME``
owns the engagement until they let go.

**Taken before anything is read.** A run decides what to do from the
request list, the index and the drop folder; if it read those first and
locked afterwards, a run that finished in between would be invisible to it
and its rows written from a stale picture. So the lock comes first, and every
read a decision rests on happens inside it. Dry runs never take the lock -
they write nothing, so they cannot race.

**Held, and owned.** The lock is a file created with ``O_EXCL`` (atomic on
NTFS and POSIX) that names the process and the time, and the descriptor
stays open for as long as the lock is held. On Windows that makes the file
undeletable by anyone else, so a lock that merely *looks* stale but belongs
to a run still going cannot be swept aside. Release removes the file only
if it still carries this run's own line; a lock another run replaced in the
meantime is theirs to remove.

**Older than the job's kill time.** ``STALE_LOCK_SECONDS`` is derived from
``RUN_TIME_LIMIT_SECONDS``, the limit the scheduled task is generated with
(``tracker.scheduling`` renders it as the task's ExecutionTimeLimit) - so a
lock is presumed dead only once Task Scheduler must already have killed its
owner. The accepted cost: after a run is killed at the limit, the repeat
that fires at that same moment still respects the lock, logs that another
run appears to be going, and the one after proceeds. The two numbers used to
be typed apart (3600 s against a two-hour limit), and a legitimately long
scan could have its lock replaced under it by the next repeat.

**Dead owners are not waited for.** The file names its owner's process
id. A lock whose owner is no longer running - the desktop shell killed the
API at its own timeout, a power cut, a crash - is stale at any age: waiting
out the run limit for a process that is gone only blocks the engagement.
A process id the system has since reused looks alive, and then the age
rule above applies, which is the safe direction. **The stale rules rest on
the one-machine rule below** (decision 137, L6): "is that process still
running" can only be asked of this machine's process table, so a lock
naming another host is left to the age rule - and the age rule's promise,
that Task Scheduler has killed the owner by then, is this machine's
schedule's promise. A second machine writing under the same clients root
is held to neither, and its lock can be taken as stale while it writes.

**One machine per clients root.** ``O_EXCL`` is atomic on one filesystem. A
lock file that a cloud client syncs between two machines is not a lock:
both can create theirs before either copy arrives. Run the schedule, and the
app's Scan button, from one machine per clients root.

**A release is proved, not assumed (decision 171, F1).** The Drive test of
2026-09-25 had two processes take, append and release one engagement's lock
over and over on the Google Drive for desktop drive (G:). There,
``Path.unlink()`` on the lock file sometimes *returned success and left the
file in place*: 6 times in 200 contended releases, 0 in 200 on NTFS, 0 in
150 releases on G: with nobody else touching the file. The file left behind
names a live process - the one that released it - so while that process
lives every taker is refused, its own next take included, until the age
rule clears it after two hours and five minutes. The trigger is ordinary: a
scheduled pass and a click in the app on the same engagement at once. The
scheduled pass is the process that lives long - up to the run limit - and
while it lives a lock it left would refuse the app's clicks on that
engagement for the rest of the pass. So :func:`release_lock` reads the
file back after the unlink, and only its absence proves it went (a read
refused while a delete is pending is looked at again, and the file is read
again before every retried delete, so a delete never lands on a lock
another run has taken since). Still there with this lock's own token means
the delete did not take, and it is handled exactly as a refused delete
always was: retry within the same budget, then mark the file
``RELEASED_LINE``, which every reader takes as an owner that is gone. A file
now carrying another token is another run's lock, and is left alone. The
delete in the stale-replace path is not proved this way: a replace that did
not take ends in "could not acquire" after two tries, and the next take
tries again.

**A process never locks itself out (decision 171, F1's worst case).** One
process takes the same lock twice in a row in ordinary work: an app command
that unfiles, marks missing, assigns or renames takes the lock and then
rescans, which takes it again (``tracker.filer._rescan``); the scheduled
pass locks a fed return beside the household that fed it, and again when
it reaches that return's own household; and a release that ran out of
tries, and could not even mark the file released, leaves this process's
own lock behind for its next take. Each app
command is its own short process (the desktop app starts one
``python -m tracker.api`` per command), so a leftover from an *earlier*
command names a process that has ended and the dead-owner rule clears it;
it is the second take inside one process that would find its own live pid.
So the module keeps the exact lock line - the token - of every lock this
process holds right now, added when a lock is taken and removed, token by
token, when it is let go. A lock file naming this process on this host
whose text is *not* one of those tokens cannot be a run in progress - this
process would know - so it is a leftover of a release that did not take,
and it is replaced as stale ("left by this process"). One whose text *is* a
held token is a real double acquire, a bug, and is refused as loudly as
ever. The record is by token, not by path, so no second spelling of the
same folder (a mapped drive and its UNC path, a short name) can hide a lock
this process holds, and one release can only ever remove its own entry. It
is kept behind a thread lock, as cheap insurance: the module promises to be
safe across threads, though nothing in the app takes locks on two threads
today. The check, and the write that makes a new lock this process's own,
happen under that one thread lock, so a thread can never take another
thread's lock, taken a moment ago, for a leftover.

**A lock changing hands is a lock (decision 171, F2).** On Windows,
``os.open(O_CREAT|O_EXCL)`` on a lock file another process is deleting at
that instant raises ``PermissionError`` (errno 13, delete pending), not
``FileExistsError``: seen on G: and on NTFS alike (2 in 200 contended
acquires on NTFS). Caught as nothing, it reached the caller as a bare
"permission denied". It is the lock being released or taken, so
:func:`acquire_lock` tries up to ``_CHANGING_HANDS_ATTEMPTS`` times about
``_CHANGING_HANDS_DELAY`` apart and then raises
:class:`EngagementLockedError` saying the lock is changing hands - never
retrying for ever, because a stuck lock must say so, not hang a pass. Only
a lock file that is *there* can be changing hands: a create refused while
the name is free (tried once more, in case the delete finished in between)
is a folder this account cannot write to, and the original
``PermissionError`` goes to the caller, which reports it as the run's
error. Called "another run", it would be skipped quietly on every pass, for
a run that does not exist.
**A lock is on disk, and one older than the machine's last start is dead
(decision 189, SPEC-161 A-F3).** The lock line is ``fsync``-ed as it is
written: a power cut after the take must not leave an empty file that
waits out two hours and five minutes. And a lock this machine wrote whose
``started=`` is before this machine last started cannot belong to a
running process, whatever its process id says now - Windows reuses ids,
and a reused one looked alive to the dead-owner rule, so after a power
cut the household waited out the age rule. :func:`boot_time` is now
minus the time since boot (``GetTickCount64`` on Windows,
``/proc/uptime`` elsewhere); where neither can be read there is no boot
rule and the age rule decides, as before. A lock file with no line at
all - empty, or holding no ``pid=`` - is a take the machine never
finished writing, and is stale once its file is older than
:data:`EMPTY_LOCK_SECONDS`; younger, it may be a take in the instant
between the create and the write. Another host's lock keeps the age
rule: its boot is not this machine's to know.

Refused: a Windows named mutex or a byte-range lock instead of the file. It
would not reach a second machine through Drive either, and the one-machine
rule is where that is answered; F1 and F2 needed two local repairs, not a
new mechanism.

**A stale lock is taken by one run only (decision 159, A-2).** Judging a
lock stale and deleting it are two steps. Every racer that judged the same
dead lock used to delete it and then create its own, and a racer whose
delete landed after another's create deleted a live lock: both then held
it. So a stale lock is removed only under a short **breaker** -
the breaker (:data:`BREAKER_SUFFIX` after the lock's name) beside the lock, created with the same
``O_EXCL`` - and only if, read again under the breaker, it is still the
very file that was judged stale. **The very file, not only the same
text** (the review's M2): what is judged and compared is the text *and*
the file's modification time and file number, read from one open handle.
Every lock is empty for an instant between its create and its token, so
an old empty lock compared by text alone would let a racer delete the
empty lock another racer had just made. A lock that changed in between is
someone else's by now and is refused, never deleted; a lock gone in
between is left to the ``O_EXCL`` create to decide.

What *stale* means is judged once, by decision 189's rule
(:class:`LockStatus`: let go, a line never written and older than
:data:`EMPTY_LOCK_SECONDS`, this machine's and older than its boot or its
process ended, or older than :data:`STALE_LOCK_SECONDS`), read by
:func:`_status_from` from the very handle the breaker compares: a take,
the app's page, the clear button and a breaker's abandonment all ask that
one judgment, never a second copy of it.

**An abandoned breaker is cleared by exactly one racer** (the review's
M1). A breaker whose owner on this machine is gone, or older than
``BREAKER_STALE_SECONDS``, was left by a run that died holding it - or by
a release whose delete reported success and left the file, which decision
171 saw on the synced drive. Deleting it on a judgment alone is the
original race again one level up: two racers judge the same old breaker,
the second deletes the breaker the first just made, and both are inside.
So the racers that judged one abandoned breaker compete, with ``O_EXCL``,
for a marker named for that breaker's identity (its text, modification
time and file number, read from one handle); only the marker's creator
deletes the breaker, and only if it is still that same file; everyone
else is refused as "being cleared by another run". The marker is left in
place - deleting it at once would let a racer that judged the same old
breaker win a fresh marker - and swept once it is older than
``BREAKER_STALE_SECONDS``. A breaker is released only if it still holds
its own run's token, so a run whose breaker was cleared under it never
deletes the next run's.

:func:`clear_stale_lock`, the app's button, goes through the same breaker
and the same comparison. The breaker and its markers are siblings of the
lock, never locks of their own: nothing shows them or waits on them.
**What this buys, and what it does not:** on one disk, where ``O_EXCL``
and the file's identity are exact, a stale lock is taken by one run -
the test races eight processes for thirty rounds at a dead lock, at a
dead lock behind an abandoned breaker, and at an old empty lock, and
``python -m tracker.locking race`` does the same on the synced drive
letter as one of the owner's live checks. It is not a lock across
machines: nothing file-based is (decision 171), and that is the
multi-writer study's subject, not this module's. The one window left is
a breaker's owner that was only slow, not dead, releasing its own breaker
at the instant its marker's winner checks and deletes it.

**Held means this process took this lock (decision 159, A-5).**
:func:`holds`, and :func:`lock_is_held` which every writer asks, answer
from the tokens this process recorded when it took its locks, not from
what the file says: a lock file written by hand with this machine's name
and this process's id is not a lock this process holds, and no writer
writes under it. Every token carries a random id of its own take, so two
takes in one clock tick never write the same line, and each token is
recorded with the lock file it was written to: a held token copied into
another folder's lock is not held there. That is checked with
``os.path.samefile``, not by comparing spellings, so no second spelling of
a folder (a short name, a link, a mapped drive) can hide a held lock -
the reason decision 171 keyed the record by token and not by path.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import os
import platform
import secrets
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("tracker.locking")

#: Kept under the scanner's old name so existing engagements and habits still apply.
LOCK_FILENAME = "_scan.lock"
_PID_KEY = "pid"
_STARTED_KEY = "started"
_HOST_KEY = "host"
#: A random id of one take (decision 159, the review's S5): two takes in one
#: clock tick never write the same token. Read by nothing but the eye.
_ID_KEY = "id"
#: What a lock file says when its owner let go but could not delete it.
RELEASED_LINE = "released=1"
_RELEASE_RETRIES = 10
_RELEASE_RETRY_DELAY = 0.2
#: How many times, in total, taking the lock is tried while Windows refuses
#: the create because the file is being deleted at that instant (F2), or a
#: delete is tried while another process has the file open for a moment
#: (decision 159, Windows).
_CHANGING_HANDS_ATTEMPTS = 3
_CHANGING_HANDS_DELAY = 0.2
#: The tokens (the exact lock lines) of the locks this process holds right
#: now, each with the lock file it was written to (decisions 171 and 159): a
#: lock file naming this process whose text is not here is a leftover, not a
#: run. Every token carries its own take's random id, so no two takes share
#: one.
_held: dict[str, Path] = {}
_held_guard = threading.Lock()
#: How long Task Scheduler lets one pass run before killing it. It lives
#: here, not in tracker.scheduling, because the stale threshold below is
#: derived from it and this module imports nothing from the package.
RUN_TIME_LIMIT_SECONDS = 2 * 60 * 60
#: A little past the limit, so a run killed at the limit has let go of its
#: handle before anyone calls its lock stale.
STALE_LOCK_GRACE_SECONDS = 5 * 60
STALE_LOCK_SECONDS = RUN_TIME_LIMIT_SECONDS + STALE_LOCK_GRACE_SECONDS
#: How old an empty or line-less lock file must be before it is stale
#: (decision 189): long enough for a take between its create and its
#: write, far short of the two hours an unwritten lock used to wait.
EMPTY_LOCK_SECONDS = 60
#: The breaker beside a lock, under which a stale lock is removed
#: (decision 159): the lock is cleared under its name with this suffix.
BREAKER_SUFFIX = ".breaking"
#: A breaker is held for a read and a delete; one this old was left by a
#: run that died holding it, whatever machine it names.
BREAKER_STALE_SECONDS = 60
#: The marker the one racer clearing an abandoned breaker creates, named
#: for that breaker's identity: the breaker's name, this, and 16 hex digits.
BREAKER_CLEARED_INFIX = ".cleared-"

#: What a lock file is, as judged: its text, and the file's modification
#: time in nanoseconds and file number, all from one open handle
#: (decision 159, the review's M2).
Identity = tuple[str, int, int]


def _look(path: Path) -> Identity | None:
    """``path``'s identity from one open handle, or ``None`` if it is gone.
    Any other failure to read it is raised."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
            seen = os.fstat(handle.fileno())
    except FileNotFoundError:
        return None
    return data.decode("utf-8", errors="replace"), seen.st_mtime_ns, seen.st_ino


def _age_of(identity: Identity) -> float:
    return time.time() - identity[1] / 1e9


class EngagementLockedError(RuntimeError):
    """Another sort or scan of this engagement appears to be running."""


@dataclass(frozen=True, slots=True)
class EngagementLock:
    """A held lock: the file, the open descriptor that keeps it ours, and
    exactly what we wrote in it (release checks the file still says so)."""

    path: Path
    fd: int
    token: str


def pid_alive(pid: str | int) -> bool | None:
    """Whether the process a lock names is still running; None if unknowable."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        ERROR_INVALID_PARAMETER = 87           # no such process
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            # Access denied and the like: it exists, we just cannot ask.
            return False if ctypes.get_last_error() == ERROR_INVALID_PARAMETER else None
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return None
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def boot_time() -> float | None:
    """When this machine last started, as a ``time.time()`` stamp, or None
    when it cannot be read (then there is no boot rule; the age rule
    decides). The suite replaces this function to state a boot."""
    try:
        if os.name == "nt":
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32")
            kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            up = kernel32.GetTickCount64() / 1000.0
        else:
            with open("/proc/uptime", encoding="ascii") as handle:
                up = float(handle.read().split()[0])
    except (OSError, ValueError, IndexError, AttributeError):
        return None
    return time.time() - up


#: How far before this machine's boot a lock's ``started=`` must be for
#: the boot rule to judge it dead (the review's N2). ``started=`` is naive
#: local time and the boot is ``time.time()`` less the uptime, so a clock
#: corrected just after boot (w32time) or the fall-back hour of daylight
#: saving can put a live lock of this machine a little before its boot. A
#: lock a restart really left behind is hours older, so the margin costs
#: nothing; within it, the age rule decides.
BOOT_MARGIN_SECONDS = 120


def _started_before_boot(started: str) -> bool:
    """Whether a lock line's ``started=`` is before this machine last
    started, by more than :data:`BOOT_MARGIN_SECONDS`. False when either
    cannot be read: no rule is no guess."""
    booted = boot_time()
    if booted is None or not started:
        return False
    try:
        when = dt.datetime.fromisoformat(started)
    except ValueError:
        return False
    return when.timestamp() < booted - BOOT_MARGIN_SECONDS


def _fields(text: str) -> dict[str, str]:
    """A lock line's ``key=value`` fields."""
    return dict(part.split("=", 1) for part in text.split() if "=" in part)


def _status_from(path: Path, seen: Identity) -> LockStatus:
    """What one lock file says, from the identity it was read as: the one
    reading behind every judgment of a lock - a take's, the app's page's,
    the clear button's and a breaker's (decisions 159 and 189), so no two
    of them ever disagree about the same file. A take's random id is not
    part of the status: nothing shows it."""
    text = seen[0]
    fields = _fields(text)
    released = text.strip() == RELEASED_LINE
    return LockStatus(
        path=path, age_seconds=max(_age_of(seen), 0.0),
        started=fields.get(_STARTED_KEY, ""), pid=fields.get(_PID_KEY, ""),
        host=fields.get(_HOST_KEY, ""), released=released,
        unwritten=not released and _PID_KEY not in fields,
    )


def acquire_lock(engagement_dir: Path, name: str = LOCK_FILENAME) -> EngagementLock:
    """Take the engagement lock or raise :class:`EngagementLockedError`.

    The returned handle stays open until :func:`release_lock`; use
    :func:`engagement_lock` unless there is a reason not to. ``name`` is
    the lock file's name: the engagement's own by default; another name
    is another lock with the same guarantees, in whatever folder it guards
    (the household README's, ``tracker.filer.README_LOCK_FILENAME``).
    """
    lock = engagement_dir / name
    for _attempt in (1, 2):
        try:
            fd = _open_exclusively(lock)
        except FileExistsError:
            try:
                # Text, time and file number from one handle: what is
                # judged is one file, and the breaker compares that file
                # (decision 159).
                judged = _look(lock)
            except OSError:
                judged = None
            if judged is None:
                continue  # lock vanished between checks; retry
            # One judgment of a lock (decisions 159 and 189): the status the
            # app's page reads, made from the very file the breaker compares.
            status = _status_from(lock, judged)
            text, age = judged[0], status.age_seconds
            with _held_guard:
                # Under the guard, so no thread of this process is between
                # writing its own new lock and recording it as held.
                leftover = _a_leftover_of_this_process(text)
                if leftover:
                    # Other threads of this process wait on the guard while
                    # this runs: about 3 s at worst when Windows refuses
                    # every delete (the clear 0.6 s, the stale delete 0.4 s,
                    # the breaker's release 1.8 s) - bounded, and rare.
                    _replace_stale(lock, judged, age, "; left by this process")
            if leftover:
                continue
            gone = status.owner_gone
            if not status.stale:
                raise EngagementLockedError(
                    f"another scan or sort appears to be running ({lock.name} is "
                    f"{age:.0f}s old); if not, delete the lock file"
                ) from None
            _replace_stale(lock, judged, age, "; its owner is no longer running" if gone else "")
            continue
        token = lock_line(os.getpid(), dt.datetime.now())
        try:
            with _held_guard:
                os.write(fd, token.encode("utf-8"))
                # On the disk before the take counts (decision 189): a
                # power cut must not leave an empty file behind a run.
                os.fsync(fd)
                _held[token] = lock
        except OSError:
            os.close(fd)
            lock.unlink(missing_ok=True)
            raise
        return EngagementLock(path=lock, fd=fd, token=token)
    raise EngagementLockedError(f"could not acquire {lock.name}")


def _open_exclusively(lock: Path) -> int:
    """Create the lock file, or raise ``FileExistsError`` when one is there.

    Windows refuses the create with ``PermissionError`` while another
    process is deleting the file (F2): the lock is changing hands, so it is
    tried again briefly, and then reported as a lock. Only a lock that is
    there can be changing hands: a create refused while the name is free is
    tried once more at once (the delete may have finished in between), and
    refused again with the name still free it is a folder this account
    cannot write to - the original ``PermissionError`` goes to the caller,
    which reports it as the run's error.
    """
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    refused_while_there = 0
    first_refused_while_free: PermissionError | None = None
    while True:
        try:
            return os.open(lock, flags)
        except PermissionError as exc:
            if not _name_taken(lock):
                if first_refused_while_free is not None:
                    raise first_refused_while_free from None
                first_refused_while_free = exc
                continue
            refused_while_there += 1
            if refused_while_there >= _CHANGING_HANDS_ATTEMPTS:
                raise EngagementLockedError(
                    f"{lock.name} is changing hands; another scan or sort is finishing - try again"
                ) from exc
            time.sleep(_CHANGING_HANDS_DELAY)


def _name_taken(lock: Path) -> bool:
    """Something is at the lock's name: a file, or one being deleted (a look
    refused is a name taken - Windows refuses it while a delete is pending)."""
    try:
        os.lstat(lock)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def _a_leftover_of_this_process(text: str) -> bool:
    """The lock line ``text`` names this process on this machine, and it is
    not a line this process holds: a release of ours that did not take.
    Asked under ``_held_guard``."""
    fields = _fields(text)
    return (
        fields.get(_HOST_KEY, "") == this_host()
        and fields.get(_PID_KEY, "") == str(os.getpid())
        and text not in _held
    )


def _replace_stale(lock: Path, judged: Identity, age: float, why: str) -> None:
    """Delete a stale lock so the caller can take it - only under the
    breaker, and only if it is still the very file judged (its text, time
    and file number; decision 159); refuse one that changed, and one still
    held.

    A lock gone by the time the breaker is held is left to the caller's
    ``O_EXCL`` create. This delete is not proved the way a release is: one
    that reports success and leaves the file (F1) ends in "could not
    acquire" after the caller's two tries, and the next take tries again.
    """
    breaker, token = _take_breaker(lock)
    try:
        try:
            now = _look(lock)
        except OSError as exc:
            # At call time: locking imports nothing of the package at load.
            from tracker import errors

            errors.keep("locking", exc, name=lock.name)
            raise EngagementLockedError(
                f"{lock.name} could not be read again before clearing it "
                f"({errors.error_class(exc)}) - try again"
            ) from None
        if now is None:
            return
        if now != judged:
            raise EngagementLockedError(
                f"another scan or sort appears to be running ({lock.name} was taken "
                "while it was being judged stale)"
            )
        log.warning("Replacing stale engagement lock (%.0f s old%s)", age, why)
        for attempt in range(1, _CHANGING_HANDS_ATTEMPTS + 1):
            try:
                lock.unlink(missing_ok=True)
                return
            except PermissionError:
                # Windows refuses a delete while any process has the file
                # open: its owner - then it is not dead after all - or,
                # for the moment one read takes, another run judging this
                # same lock (decision 159, Windows). An owner keeps it open;
                # a reader lets go at once. So it is looked at again and
                # tried again briefly, and refused as held only after that.
                if attempt == _CHANGING_HANDS_ATTEMPTS:
                    raise EngagementLockedError(
                        f"{lock.name} looks stale ({age:.0f}s old) but is still held "
                        "by a running process"
                    ) from None
            time.sleep(_CHANGING_HANDS_DELAY)
            try:
                again = _look(lock)
            except OSError:
                continue                 # refused a read too: try the delete again
            if again is None:
                return
            if again != judged:
                raise EngagementLockedError(
                    f"another scan or sort appears to be running ({lock.name} was taken "
                    "while it was being judged stale)"
                )
            # Still the lock judged. The name cannot change hands before the
            # next delete: the dead file stands until it is deleted, and
            # every other take's O_EXCL create is refused while it does.
    finally:
        _release_breaker(breaker, token)


def breaker_of(lock: Path) -> Path:
    """The breaker beside ``lock``: its name with :data:`BREAKER_SUFFIX` after it."""
    return lock.with_name(lock.name + BREAKER_SUFFIX)


def _take_breaker(lock: Path) -> tuple[Path, str]:
    """Create ``lock``'s breaker and return it with the token written in it,
    or raise :class:`EngagementLockedError` while another run is clearing
    ``lock``.

    A breaker its owner left behind - gone on this machine, or older than
    :data:`BREAKER_STALE_SECONDS` - is cleared by exactly one racer: the one
    that creates the marker named for that breaker's identity
    (:func:`_clear_abandoned`); that racer tries the create once more, and
    every other is refused.
    """
    breaker = breaker_of(lock)
    for _attempt in (1, 2):
        try:
            fd = _open_exclusively(breaker)
        except FileExistsError:
            try:
                seen = _look(breaker)
            except OSError:
                break
            if seen is None:
                continue                 # let go in between: simply try again
            if not _abandoned(breaker, seen) or not _clear_abandoned(breaker, seen):
                break
            continue
        token = lock_line(os.getpid(), dt.datetime.now())
        try:
            os.write(fd, token.encode("utf-8"))
        except OSError:
            os.close(fd)
            breaker.unlink(missing_ok=True)
            raise
        os.close(fd)
        _sweep_markers(breaker)
        return breaker, token
    raise EngagementLockedError(f"{lock.name} is being cleared by another run - try again")


def _abandoned(breaker: Path, seen: Identity) -> bool:
    """The breaker is older than :data:`BREAKER_STALE_SECONDS`, whoever it
    names, or its owner is judged gone by the one judgment a lock gets
    (:attr:`LockStatus.owner_gone`: a process on this machine that has
    ended or started before this machine last did). An empty one is judged
    by its age alone: it is a breaker being written this instant."""
    if _age_of(seen) >= BREAKER_STALE_SECONDS:
        return True
    return _status_from(breaker, seen).owner_gone


def _marker_of(breaker: Path, seen: Identity) -> Path:
    """The marker for one abandoned breaker: named for its identity, so every
    racer that judged that very file competes for the same name."""
    text, mtime_ns, ino = seen
    digest = hashlib.sha256(f"{text}|{mtime_ns}|{ino}".encode()).hexdigest()[:16]
    return breaker.with_name(breaker.name + BREAKER_CLEARED_INFIX + digest)


def _clear_abandoned(breaker: Path, seen: Identity) -> bool:
    """Delete the abandoned breaker ``seen`` if this racer is the one that
    clears it; ``False`` when another racer is (the caller refuses).

    Only the creator of the marker for ``seen`` deletes, and only if the
    breaker is still that same file. The marker stays after a clear, and
    :func:`_sweep_markers` removes it once it is old; it goes at once if the
    delete was refused throughout.
    """
    marker = _marker_of(breaker, seen)
    try:
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except OSError:
        return False                     # another racer is clearing this very breaker
    try:
        now = _look(breaker)
    except OSError:
        return False
    if now is None:
        return True                      # gone already: the create decides
    if now[1:] != seen[1:]:
        return False                     # a newer breaker: another run's, live
    log.warning("%s was left by a run that is gone; it is cleared", breaker.name)
    for _attempt in range(_CHANGING_HANDS_ATTEMPTS):
        try:
            breaker.unlink(missing_ok=True)
            return True
        except PermissionError:
            # Windows: open in another process - another racer reading it
            # to judge it, for a moment, or its owner. Waited out briefly
            # (decision 159, Windows).
            time.sleep(_CHANGING_HANDS_DELAY)
        try:
            now = _look(breaker)
        except OSError:
            continue
        if now is None:
            return True
        if now[1:] != seen[1:]:
            return False
        # Between this look and the next delete the name could change hands
        # (the window a single delete always had). Safe all the same: two
        # racers in _replace_stale cannot make two holders, because the
        # lock's holder keeps its handle open and Windows refuses the
        # second racer's delete of it.
    # Still refused. The marker goes with this racer's claim: kept, it would
    # refuse every later racer's claim on this very breaker, and a breaker
    # nobody may clear, and so nobody may take, would refuse every stale
    # take of this lock for good. Without it, the next take judges again.
    try:
        marker.unlink(missing_ok=True)
    except OSError as exc:
        # At call time: locking imports nothing of the package at load.
        from tracker import errors

        errors.keep("locking", exc, name=marker.name)
        log.warning("%s could not be removed (%s); it is swept when old", marker.name,
                    errors.error_class(exc))
    return False


def _sweep_markers(breaker: Path) -> None:
    """Remove this breaker's markers older than :data:`BREAKER_STALE_SECONDS`.
    Asked while holding the breaker; a marker that will not go is left for
    the next sweep."""
    for marker in breaker.parent.glob(breaker.name + BREAKER_CLEARED_INFIX + "*"):
        try:
            if time.time() - marker.stat().st_mtime >= BREAKER_STALE_SECONDS:
                marker.unlink(missing_ok=True)
        except OSError:
            continue


def _release_breaker(breaker: Path, token: str) -> None:
    """Remove the breaker - only if it still holds this run's own token, so
    a run whose breaker was cleared under it never deletes the next run's. A
    removal that fails is said, not raised: the lock's own work is done, and
    the age rule clears the breaker.

    **A delete refused on Windows is waited out (decision 159, Windows).**
    Every racer refused the breaker opens it to judge whether it was
    abandoned (:func:`_look`), and Windows refuses to delete a file any
    process has open (a sharing violation, ``PermissionError``). The race
    test left the breaker behind in 2 of 10 runs on the office PC (NTFS),
    and for the next minute every stale take of that lock
    was refused as "being cleared by another run". A reader lets go at
    once, so the delete is tried again within the release's own budget,
    the token read again before every try - the breaker is never deleted
    once it is another run's. A breaker still left after that (the budget
    spent, or a crash between the take and this) names this run: while the
    run lives the age rule clears it after :data:`BREAKER_STALE_SECONDS`,
    and once it has ended the next taker clears it at once as abandoned.
    """
    trouble: OSError | None = None
    for attempt in range(_RELEASE_RETRIES):
        if attempt:
            time.sleep(_RELEASE_RETRY_DELAY)
        try:
            if breaker.read_text(encoding="utf-8", errors="replace") != token:
                log.warning("%s was replaced by another run; leaving theirs in place", breaker.name)
                return
            breaker.unlink(missing_ok=True)
            return
        except FileNotFoundError:
            return
        except PermissionError as exc:
            trouble = exc                # open in another process for a moment: again
        except OSError as exc:
            trouble = exc
            break
    log.warning("%s could not be removed (%s); it is cleared after %d s",
                breaker, trouble, BREAKER_STALE_SECONDS)


def release_lock(lock: EngagementLock) -> None:
    """Let go: close the handle, then remove the file only if it is still ours,
    and make sure it really went (F1). This lock's own token, and only that,
    stops being held."""
    try:
        _release(lock)
    finally:
        with _held_guard:
            _held.pop(lock.token, None)


#: Why a release ended by marking the file released instead of deleting it.
_KEPT_OPEN = "another program kept it open"
_STAYED = "the delete was reported done but the file stayed"
_UNCONFIRMED = "could not confirm the lock was removed"


def _release(lock: EngagementLock) -> None:
    try:
        os.close(lock.fd)
    except OSError:
        pass  # already closed; the file is what matters
    try:
        current = lock.path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return  # already gone
    if current != lock.token:
        log.warning(
            "%s was replaced by another run while held; leaving theirs in place",
            lock.path.name,
        )
        return
    stayed = False
    trouble = _KEPT_OPEN
    for attempt in range(_RELEASE_RETRIES):
        if attempt:
            # Read again before every retried delete: while we waited, ours
            # may have gone and another run's lock taken the name.
            try:
                now = lock.path.read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                return
            except OSError:
                trouble = _UNCONFIRMED
                time.sleep(_RELEASE_RETRY_DELAY)
                continue
            if now != lock.token:
                return            # another run's lock now; theirs
        try:
            lock.path.unlink(missing_ok=True)
        except PermissionError:
            # A sync client reading the file for upload: brief, so wait it out.
            trouble = _KEPT_OPEN
            time.sleep(_RELEASE_RETRY_DELAY)
            continue
        # The delete reported success. On Google Drive that is not proof
        # (F1), so the file is read back. Only its absence proves it went;
        # another run's token means ours went and theirs came; this lock's
        # own token means the delete did not take. A read refused is not an
        # absence: on G: the read-back right after a "successful" delete was
        # refused (delete pending) in 8 of 200 contended releases in this
        # decision's live check, and a refusal proves nothing about what is
        # there after it - so it is looked at again, in the same budget,
        # exactly like a delete refused.
        try:
            after = lock.path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return
        except OSError:
            trouble = _UNCONFIRMED
            time.sleep(_RELEASE_RETRY_DELAY)
            continue
        if after != lock.token:
            return                # another run took it after ours went; theirs
        stayed = True
        time.sleep(_RELEASE_RETRY_DELAY)
    # Still there. This process may take the next lock itself (a sort, then
    # a scan) and would find its own live pid in the file; so the file is
    # marked released, which every reader takes as an owner that is gone.
    why = _STAYED if stayed else trouble
    try:
        if lock.path.read_text(encoding="utf-8", errors="replace") != lock.token:
            return                # another run took it while we waited; theirs now
        lock.path.write_text(RELEASED_LINE, encoding="utf-8")
        log.warning("%s could not be removed on release (%s); marked released instead",
                    lock.path, why)
    except FileNotFoundError:
        return                    # it went while we waited
    except OSError as exc:
        # At call time: locking imports nothing of the package at load.
        from tracker import errors

        errors.keep("locking", exc, name=lock.path.name)
        log.warning("%s could not be removed or marked on release (%s; %s)",
                    lock.path, why, errors.error_class(exc))


@dataclass(frozen=True, slots=True)
class LockStatus:
    """What the lock file says, for the app to show instead of a mystery."""

    path: Path
    age_seconds: float
    started: str        # ISO time the run began, if the file said
    pid: str            # process id, if the file said
    host: str = ""      # the machine that took it, if the file said
    released: bool = False   # its owner let go but could not delete it
    unwritten: bool = False  # empty, or no pid= line: a take never finished

    @property
    def owner_gone(self) -> bool:
        """The lock's owner is judged gone (False if unknowable, including a
        process on another machine): it let go; its line was never written
        and the file is older than :data:`EMPTY_LOCK_SECONDS`; or it is this
        machine's and it started before the machine last did, or its
        process is no longer running (decision 189)."""
        if self.released:
            return True
        if self.unwritten:
            return self.age_seconds >= EMPTY_LOCK_SECONDS
        if not is_this_host(self.host):
            # Another machine's process (a synced clients root): whether it
            # is running cannot be known from here, so the age rule decides.
            return False
        return _started_before_boot(self.started) or pid_alive(self.pid) is False

    @property
    def stale(self) -> bool:
        return self.age_seconds >= STALE_LOCK_SECONDS or self.owner_gone


def lock_status(engagement_dir: Path | str) -> LockStatus | None:
    """The engagement's lock if one is present, else None. Never raises.

    Only the lock itself: its breaker (decision 159) is a sibling held for a
    moment while a stale lock is cleared, and is never shown as a lock."""
    found = _status_and_identity(Path(engagement_dir) / LOCK_FILENAME)
    return None if found is None else found[0]


def _status_and_identity(lock: Path) -> tuple[LockStatus, Identity] | None:
    """The lock's status and the identity it was read from, from one handle."""
    try:
        seen = _look(lock)
    except OSError:
        return None
    if seen is None:
        return None
    return _status_from(lock, seen), seen


def holds(engagement_dir: Path | str, name: str = LOCK_FILENAME) -> bool:
    """Whether *this* process holds the lock ``name`` in ``engagement_dir``
    right now: the file's exact text is a token this process recorded when
    it took the lock, and has not let go of, **and** that token was written
    to this very file (``os.path.samefile``; decision 159, A-5). A held
    token copied into another folder's lock is not held there.

    Read under the thread lock that guards the tokens, so no take or
    release of this process is half done while it answers. Never raises: a
    folder that is not there, or a lock file that cannot be read, is a lock
    this process does not hold.
    """
    try:
        lock = Path(engagement_dir) / name
    except (TypeError, ValueError):
        return False
    with _held_guard:
        try:
            text = lock.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            return False
        written_to = _held.get(text)
        if text == RELEASED_LINE or written_to is None:
            return False
        try:
            return os.path.samefile(written_to, lock)
        except (OSError, ValueError):
            return False


def lock_is_held(engagement_dir: Path | str) -> bool:
    """Whether *this* process holds this engagement's lock right now.

    Asked by a writer that must not write outside the lock and cannot be
    handed the lock itself (:mod:`tracker.ledger`, called from deep inside
    the filer and the manifest). It answers from the held token
    (:func:`holds`), not from the file's text alone (decision 159): the
    file must say exactly what this process wrote when it took the lock,
    and this process must not have let it go. A lock file written by hand
    with this machine's name and this process's id is therefore not held.
    Until decision 159 the file's own line answered - this host, this
    process id - and anything could write that line.

    Never raises: a folder that is not there, or a lock file that cannot be
    read, is a lock this process does not hold.
    """
    return holds(engagement_dir)


def this_host() -> str:
    """This machine's name, as the lock line carries it. From ``platform``,
    not ``socket``: the name is a local fact, and no module under the
    package imports a network module (decision 115's guard)."""
    return platform.node().strip().casefold()


def is_this_host(host: object) -> bool:
    """Whether a name is this machine's, in any case (decision 159, the
    review's S1): ``OFFICE-PC`` on the machine ``office-pc`` is this
    machine, never "another machine", and so is ``"OFFICE-PC "`` (the final
    review's SF3; the ledger refuses such a line when it reads it anyway).
    The one comparison of a host, normalised as :func:`this_host` is."""
    return isinstance(host, str) and host.strip().casefold() == this_host()


def lock_line(pid: int, started: dt.datetime) -> str:
    """What the lock file says: who took it and when, as ``lock_status`` reads
    it back, and a random id of this one take (decision 159), so no two
    takes ever write the same token. A line without the id - written before
    159 - still reads."""
    return (f"{_PID_KEY}={pid} {_STARTED_KEY}={started.isoformat()} {_HOST_KEY}={this_host()} "
            f"{_ID_KEY}={secrets.token_hex(8)}")


def clear_stale_lock(engagement_dir: Path | str) -> LockStatus:
    """Remove a lock older than :data:`STALE_LOCK_SECONDS` or whose owner is
    gone; refuse a fresh one.

    A fresh lock is a run in progress; clearing it would let two runs race,
    which is the one thing the lock exists to prevent. The caller is told
    how long to wait instead. A stale-looking lock its owner still holds
    open (Windows refuses the delete) is refused for the same reason. The
    removal goes through the breaker and is made only if the lock still
    says what was judged stale (decision 159), exactly as a take's is.
    """
    found = _status_and_identity(Path(engagement_dir) / LOCK_FILENAME)
    if found is None:
        raise EngagementLockedError("there is no lock to clear")
    status, judged = found
    if not status.stale:
        wait = int((STALE_LOCK_SECONDS - status.age_seconds) // 60) + 1
        raise EngagementLockedError(
            f"a run started {int(status.age_seconds // 60)} minute(s) ago may still be "
            f"going; if it has really died, try again in {wait} minute(s)"
        )
    _replace_stale(status.path, judged, status.age_seconds, "; cleared by hand")
    return status


@contextmanager
def engagement_lock(engagement_dir: Path) -> Iterator[EngagementLock]:
    """Hold the engagement lock for the duration of a ``with`` block.

    Open it *before* reading the request list, the index or the drop
    folder: what a run decides from must not change under it.
    """
    lock = acquire_lock(Path(engagement_dir))
    try:
        yield lock
    finally:
        release_lock(lock)


# ------------------------------------------------------------------ race ----

#: The lock the race check takes: its own name, so running the check in a
#: live return folder can never touch that return's real lock.
RACE_LOCK_FILENAME = "_race.lock"
#: How long any one step of the race check waits for the others before it
#: calls the check failed rather than hanging.
_RACE_STEP_SECONDS = 60
_HELD = "held"
#: The stale locks the race takes turns at, one per round.
RACE_SHAPES = ("dead lock", "dead lock behind an abandoned breaker", "old empty lock")


def race(folder: Path | str, *, processes: int = 8, rounds: int = 20,
         name: str = RACE_LOCK_FILENAME) -> list[str]:
    """Race ``processes`` processes at one stale lock in ``folder``,
    ``rounds`` times, and say every round that did not end with exactly one
    holder (decision 159's proof, and the owner's live check L1 on the
    synced drive letter). ``[]`` is one holder in every round.

    The rounds take turns at the three shapes of stale lock (:data:`RACE_SHAPES`):
    a lock naming a process of this machine that has ended; the same behind
    an abandoned breaker, which exactly one racer may clear (the review's
    M1); and an old empty lock, the one text that is not unique (M2). Each
    round releases every racer at once from a barrier and has each call
    :func:`acquire_lock`: the one that takes it holds it until every racer
    has answered, so a late racer cannot take it after a release and look
    like a second holder. Every other racer must be refused with
    :class:`EngagementLockedError`; anything else raised is a failure too.
    After each round neither the lock nor its breaker may be left behind
    (a clearing marker may: it is swept when old, and the race removes its
    own at the end).
    """
    import multiprocessing

    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"{folder} is not a folder to race in")
    lock = folder / name
    if lock.exists() or breaker_of(lock).exists():
        raise EngagementLockedError(
            f"{lock.name} or its breaker is already in {folder}; the race writes its own")
    ctx = multiprocessing.get_context("spawn")
    ended = ctx.Process(target=_race_nothing)
    ended.start()
    ended.join()
    dead_pid = ended.pid
    if pid_alive(dead_pid) is not False:
        raise RuntimeError(f"process {dead_pid} ended but is still reported running; "
                           "no dead lock can be written")
    barriers = [ctx.Barrier(processes + 1) for _ in range(3)]
    answers = ctx.Queue()
    racers = [ctx.Process(target=_racer, args=(str(folder), name, rounds, barriers, answers))
              for _ in range(processes)]
    for racer in racers:
        racer.start()
    failed: list[str] = []
    breaker = breaker_of(lock)
    try:
        for number in range(1, rounds + 1):
            shape = RACE_SHAPES[(number - 1) % len(RACE_SHAPES)]
            if shape == "old empty lock":
                lock.write_bytes(b"")
                old = time.time() - STALE_LOCK_SECONDS - 60
                os.utime(lock, (old, old))
            else:
                lock.write_text(lock_line(dead_pid, dt.datetime.now()), encoding="utf-8")
            if shape == "dead lock behind an abandoned breaker":
                breaker.write_text(lock_line(dead_pid, dt.datetime.now()), encoding="utf-8")
            barriers[0].wait(_RACE_STEP_SECONDS)           # go
            said = [answers.get(timeout=_RACE_STEP_SECONDS) for _ in racers]
            barriers[1].wait(_RACE_STEP_SECONDS)           # every racer answered
            barriers[2].wait(_RACE_STEP_SECONDS)           # the holder let go
            holders = said.count(_HELD)
            odd = sorted({one for one in said if one != _HELD and not one.startswith("refused")})
            left = [one.name for one in (lock, breaker_of(lock)) if one.exists()]
            if holders != 1 or odd or left:
                failed.append(
                    f"round {number} ({shape}): {holders} holder(s)"
                    + (f"; raised {odd}" if odd else "")
                    + (f"; left behind {left}" if left else ""))
                for one in (lock, breaker_of(lock)):
                    one.unlink(missing_ok=True)
    finally:
        for barrier in barriers:
            barrier.abort()
        for racer in racers:
            racer.join(timeout=10)
            if racer.is_alive():
                racer.kill()
                racer.join()
        for one in (lock, breaker, *folder.glob(breaker.name + BREAKER_CLEARED_INFIX + "*")):
            one.unlink(missing_ok=True)
    return failed


def _race_nothing() -> None:
    """A process that ends at once: its id is the dead owner the race uses."""


def _racer(folder: str, name: str, rounds: int, barriers: list, answers) -> None:
    """One racer of :func:`race`: every round, take the lock at the barrier,
    say what happened, hold it until every racer has said, then let go.
    Quiet: a replaced stale lock is the expected event here, every round."""
    log.setLevel(logging.ERROR)
    for _round in range(rounds):
        try:
            barriers[0].wait(_RACE_STEP_SECONDS)
        except threading.BrokenBarrierError:
            return
        taken = None
        try:
            taken = acquire_lock(Path(folder), name)
            answers.put(_HELD)
        except EngagementLockedError as exc:
            answers.put(f"refused: {exc}")
        except Exception as exc:          # said to the race, which fails the round
            # By its class (decision 190); the words go to the debug sink.
            from tracker import errors

            errors.keep("locking race", exc, name=name)
            answers.put(errors.error_class(exc))
        try:
            barriers[1].wait(_RACE_STEP_SECONDS)
        finally:
            if taken is not None:
                release_lock(taken)
        try:
            barriers[2].wait(_RACE_STEP_SECONDS)
        except threading.BrokenBarrierError:
            return


if __name__ == "__main__":
    import argparse
    import sys

    # Imported by name so the racers, started by "spawn", find their
    # function in the module and not in this __main__.
    from tracker import locking
    from tracker.page import tolerant_console

    tolerant_console()   # a return folder names a client

    parser = argparse.ArgumentParser(
        description="The engagement lock: race processes at one dead lock (decision 159)")
    commands = parser.add_subparsers(dest="command", required=True)
    racing = commands.add_parser(
        "race", help="race processes at a dead lock in FOLDER and say whether one held it")
    racing.add_argument("folder", type=Path, help="a folder to race in, e.g. a return on G:")
    racing.add_argument("--processes", type=int, default=8)
    racing.add_argument("--rounds", type=int, default=30,
                        help="rounds, taking turns at a dead lock, one behind an abandoned "
                             "breaker, and an old empty lock")
    ns = parser.parse_args()
    if ns.processes < 2 or ns.rounds < 1:
        parser.error("race at least 2 processes for at least 1 round")
    try:
        failures = locking.race(ns.folder, processes=ns.processes, rounds=ns.rounds)
    except (OSError, RuntimeError) as exc:
        # race() raises RuntimeError only with its own sentence, said whole;
        # the OS's error by its class (decision 190).
        from tracker import errors

        errors.keep("locking race", exc, name=ns.folder.name)
        parser.error(errors.said(exc, (RuntimeError,)))
    if failures:
        for failure in failures:
            print(failure)
        print(f"FAILED: {len(failures)} of {ns.rounds} round(s) did not end with one holder")
        sys.exit(1)
    print(f"one holder in every round ({ns.rounds} rounds, {ns.processes} processes)")
