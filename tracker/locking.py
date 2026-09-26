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
"""

from __future__ import annotations

import collections
import datetime as dt
import logging
import os
import platform
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
#: What a lock file says when its owner let go but could not delete it.
RELEASED_LINE = "released=1"
_RELEASE_RETRIES = 10
_RELEASE_RETRY_DELAY = 0.2
#: How many times, in total, taking the lock is tried while Windows refuses
#: the create because the file is being deleted at that instant (F2).
_CHANGING_HANDS_ATTEMPTS = 3
_CHANGING_HANDS_DELAY = 0.2
#: The tokens (the exact lock lines) of the locks this process holds right
#: now, each with how many takes wrote it (decision 171): a lock file naming
#: this process whose text is not here is a leftover, not a run. Counted, so
#: two takes in the same microsecond, which write the same line, are two.
_held: collections.Counter[str] = collections.Counter()
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
    return dict(part.split("=", 1) for part in text.split() if "=" in part)


def _status_of(lock: Path) -> LockStatus | None:
    """What one lock file says, or None when there is none to read."""
    try:
        age = time.time() - lock.stat().st_mtime
        text = lock.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    fields = _fields(text)
    released = text.strip() == RELEASED_LINE
    return LockStatus(
        path=lock, age_seconds=max(age, 0.0),
        started=fields.get(_STARTED_KEY, ""), pid=fields.get(_PID_KEY, ""),
        host=fields.get(_HOST_KEY, ""), released=released,
        unwritten=not released and _PID_KEY not in fields,
    )


def _owner_gone(lock: Path) -> bool:
    """True when the lock's owner is judged gone - the one judgement
    :attr:`LockStatus.owner_gone` makes, so a take and the app's page
    never disagree about the same file."""
    status = _status_of(lock)
    return status is not None and status.owner_gone


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
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue  # lock vanished between checks; retry
            with _held_guard:
                # Under the guard, so no thread of this process is between
                # writing its own new lock and recording it as held.
                leftover = _a_leftover_of_this_process(lock)
                if leftover:
                    _replace_stale(lock, age, "; left by this process")
            if leftover:
                continue
            gone = _owner_gone(lock)
            if age < STALE_LOCK_SECONDS and not gone:
                raise EngagementLockedError(
                    f"another scan or sort appears to be running ({lock.name} is "
                    f"{age:.0f}s old); if not, delete the lock file"
                ) from None
            _replace_stale(lock, age, "; its owner is no longer running" if gone else "")
            continue
        token = lock_line(os.getpid(), dt.datetime.now())
        try:
            with _held_guard:
                os.write(fd, token.encode("utf-8"))
                # On the disk before the take counts (decision 189): a
                # power cut must not leave an empty file behind a run.
                os.fsync(fd)
                _held[token] += 1
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


def _a_leftover_of_this_process(lock: Path) -> bool:
    """The lock file names this process on this machine, and its line is not
    one this process holds: a release of ours that did not take. Asked under
    ``_held_guard``."""
    try:
        text = lock.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    fields = _fields(text)
    return (
        fields.get(_HOST_KEY, "") == _this_host()
        and fields.get(_PID_KEY, "") == str(os.getpid())
        and _held[text] == 0
    )


def _replace_stale(lock: Path, age: float, why: str) -> None:
    """Delete a stale lock so the caller can take it; refuse one still held.

    This delete is not proved the way a release is: one that reports
    success and leaves the file (F1) ends in "could not acquire" after the
    caller's two tries, and the next take tries again.
    """
    log.warning("Replacing stale engagement lock (%.0f s old%s)", age, why)
    try:
        lock.unlink(missing_ok=True)
    except PermissionError:
        # Windows: the owner still has it open, so it is not dead after all.
        raise EngagementLockedError(
            f"{lock.name} looks stale ({age:.0f}s old) but is still held "
            "by a running process"
        ) from None


def release_lock(lock: EngagementLock) -> None:
    """Let go: close the handle, then remove the file only if it is still ours,
    and make sure it really went (F1). This lock's own token, and only that,
    stops being held."""
    try:
        _release(lock)
    finally:
        with _held_guard:
            if _held[lock.token] > 1:
                _held[lock.token] -= 1
            else:
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
        log.warning("%s could not be removed or marked on release (%s; %s)", lock.path, why, exc)


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
        if self.host != _this_host():
            # Another machine's process (a synced clients root): whether it
            # is running cannot be known from here, so the age rule decides.
            return False
        return _started_before_boot(self.started) or pid_alive(self.pid) is False

    @property
    def stale(self) -> bool:
        return self.age_seconds >= STALE_LOCK_SECONDS or self.owner_gone


def lock_status(engagement_dir: Path | str) -> LockStatus | None:
    """The engagement's lock if one is present, else None. Never raises."""
    return _status_of(Path(engagement_dir) / LOCK_FILENAME)


def lock_is_held(engagement_dir: Path | str) -> bool:
    """Whether *this* process holds this engagement's lock right now.

    Asked by a writer that must not write outside the lock and cannot be
    handed the lock itself (:mod:`tracker.ledger`, called from deep inside
    the filer and the manifest). It is the lock file's own line that answers
    - this host, this process id, not marked released - so it is the same
    fact :func:`release_lock` and :func:`lock_status` read, not a second one
    kept in a variable that a raised exception could leave true.

    Never raises: a folder that is not there, or a lock file that cannot be
    read, is a lock this process does not hold.
    """
    status = lock_status(engagement_dir)
    return (
        status is not None
        and not status.released
        and status.host == _this_host()
        and status.pid == str(os.getpid())
    )


def _this_host() -> str:
    """This machine's name, as the lock line carries it. From ``platform``,
    not ``socket``: the name is a local fact, and no module under the
    package imports a network module (decision 115's guard)."""
    return platform.node().lower()


def lock_line(pid: int, started: dt.datetime) -> str:
    """What the lock file says: who took it and when, as ``lock_status`` reads it back."""
    return f"{_PID_KEY}={pid} {_STARTED_KEY}={started.isoformat()} {_HOST_KEY}={_this_host()}"


def clear_stale_lock(engagement_dir: Path | str) -> LockStatus:
    """Remove a lock older than :data:`STALE_LOCK_SECONDS` or whose owner is
    gone; refuse a fresh one.

    A fresh lock is a run in progress; clearing it would let two runs race,
    which is the one thing the lock exists to prevent. The caller is told
    how long to wait instead. A stale-looking lock its owner still holds
    open (Windows refuses the delete) is refused for the same reason.
    """
    status = lock_status(engagement_dir)
    if status is None:
        raise EngagementLockedError("there is no lock to clear")
    if not status.stale:
        wait = int((STALE_LOCK_SECONDS - status.age_seconds) // 60) + 1
        raise EngagementLockedError(
            f"a run started {int(status.age_seconds // 60)} minute(s) ago may still be "
            f"going; if it has really died, try again in {wait} minute(s)"
        )
    try:
        status.path.unlink(missing_ok=True)
    except PermissionError:
        raise EngagementLockedError(
            f"{status.path.name} is still held by a running process; it is not stale"
        ) from None
    log.warning("Stale engagement lock cleared by hand (%.0f s old)", status.age_seconds)
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
