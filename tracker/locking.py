"""One lock per engagement, shared by every step that changes it (component 12).

The filer moves the client's originals and rewrites ``INDEX_FILENAME``; the
scanner rewrites ``MANIFEST_FILENAME``. Two of either running at once on the
same engagement - a scheduled run overlapping a click in the desktop app,
or Task Scheduler's repeat firing while an OCR-heavy pass is still going -
would race on the same files, and the loser's index rows would be
overwritten by the winner's. That is the one way an original can end up in
``PBC_DIR_NAME/`` with no record of how it got there, so the lock is not optional
and it is not per step: whoever holds ``LOCK_FILENAME`` owns the engagement
until they let go.

**Taken before anything is read.** A run decides what to do from the
manifest, the index and the drop folder; if it read those first and locked
afterwards, a run that finished in between would be invisible to it and its
rows rewritten from a stale picture. So the lock comes first, and every
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
rule above applies, which is the safe direction.

**One machine per clients root.** ``O_EXCL`` is atomic on one filesystem. A
lock file that a cloud client syncs between two machines is not a lock:
both can create theirs before either copy arrives. Run the schedule, and the
app's Scan button, from one machine per clients root.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import socket
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
#: How long Task Scheduler lets one pass run before killing it. It lives
#: here, not in tracker.scheduling, because the stale threshold below is
#: derived from it and this module imports nothing from the package.
RUN_TIME_LIMIT_SECONDS = 2 * 60 * 60
#: A little past the limit, so a run killed at the limit has let go of its
#: handle before anyone calls its lock stale.
STALE_LOCK_GRACE_SECONDS = 5 * 60
STALE_LOCK_SECONDS = RUN_TIME_LIMIT_SECONDS + STALE_LOCK_GRACE_SECONDS


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


def _owner_gone(lock: Path) -> bool:
    """True when the lock names a process that is no longer running."""
    try:
        text = lock.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    fields = dict(part.split("=", 1) for part in text.split() if "=" in part)
    if text.strip() == RELEASED_LINE:
        return True
    if fields.get(_HOST_KEY, "") != _this_host():
        # Another machine's process (a synced clients root): whether it is
        # running cannot be known from here, so the age rule decides.
        return False
    return pid_alive(fields.get(_PID_KEY, "")) is False


def acquire_lock(engagement_dir: Path) -> EngagementLock:
    """Take the engagement lock or raise :class:`EngagementLockedError`.

    The returned handle stays open until :func:`release_lock`; use
    :func:`engagement_lock` unless there is a reason not to.
    """
    lock = engagement_dir / LOCK_FILENAME
    for _attempt in (1, 2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue  # lock vanished between checks; retry
            gone = _owner_gone(lock)
            if age < STALE_LOCK_SECONDS and not gone:
                raise EngagementLockedError(
                    f"another scan or sort appears to be running ({lock.name} is "
                    f"{age:.0f}s old); if not, delete the lock file"
                ) from None
            log.warning(
                "Replacing stale engagement lock (%.0f s old%s)", age,
                "; its owner is no longer running" if gone else "",
            )
            try:
                lock.unlink(missing_ok=True)
            except PermissionError:
                # Windows: the owner still has it open, so it is not dead after all.
                raise EngagementLockedError(
                    f"{lock.name} looks stale ({age:.0f}s old) but is still held "
                    "by a running process"
                ) from None
            continue
        token = lock_line(os.getpid(), dt.datetime.now())
        try:
            os.write(fd, token.encode("utf-8"))
        except OSError:
            os.close(fd)
            lock.unlink(missing_ok=True)
            raise
        return EngagementLock(path=lock, fd=fd, token=token)
    raise EngagementLockedError(f"could not acquire {lock.name}")


def release_lock(lock: EngagementLock) -> None:
    """Let go: close the handle, then remove the file only if it is still ours."""
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
    for _attempt in range(_RELEASE_RETRIES):
        try:
            lock.path.unlink(missing_ok=True)
            return
        except PermissionError:
            # A sync client reading the file for upload: brief, so wait it out.
            time.sleep(_RELEASE_RETRY_DELAY)
    # Still held. This process may take the next lock itself (a sort, then
    # a scan) and would find its own live pid in the file; so the file is
    # marked released, which every reader takes as an owner that is gone.
    try:
        if lock.path.read_text(encoding="utf-8", errors="replace") != lock.token:
            return                # another run took it while we waited; theirs now
        lock.path.write_text(RELEASED_LINE, encoding="utf-8")
        log.warning("%s could not be removed on release; marked released instead", lock.path.name)
    except OSError as exc:
        log.warning("%s could not be removed or marked on release (%s)", lock.path.name, exc)


@dataclass(frozen=True, slots=True)
class LockStatus:
    """What the lock file says, for the app to show instead of a mystery."""

    path: Path
    age_seconds: float
    started: str        # ISO time the run began, if the file said
    pid: str            # process id, if the file said
    host: str = ""      # the machine that took it, if the file said
    released: bool = False   # its owner let go but could not delete it

    @property
    def owner_gone(self) -> bool:
        """The process the lock names is no longer running (False if unknowable,
        including a process on another machine)."""
        return self.released or (self.host == _this_host() and pid_alive(self.pid) is False)

    @property
    def stale(self) -> bool:
        return self.age_seconds >= STALE_LOCK_SECONDS or self.owner_gone


def lock_status(engagement_dir: Path | str) -> LockStatus | None:
    """The engagement's lock if one is present, else None. Never raises."""
    lock = Path(engagement_dir) / LOCK_FILENAME
    try:
        age = time.time() - lock.stat().st_mtime
        text = lock.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    fields = dict(part.split("=", 1) for part in text.split() if "=" in part)
    return LockStatus(
        path=lock, age_seconds=max(age, 0.0),
        started=fields.get(_STARTED_KEY, ""), pid=fields.get(_PID_KEY, ""),
        host=fields.get(_HOST_KEY, ""), released=text.strip() == RELEASED_LINE,
    )


def _this_host() -> str:
    return socket.gethostname().lower()


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

    Open it *before* reading the manifest, the index or the drop folder:
    what a run decides from must not change under it.
    """
    lock = acquire_lock(Path(engagement_dir))
    try:
        yield lock
    finally:
        release_lock(lock)
