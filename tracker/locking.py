"""One lock per engagement, shared by every step that changes it (component 12).

The filer moves the client's originals and rewrites ``_index.xlsx``; the
scanner rewrites ``_manifest.xlsx``. Two of either running at once on the
same engagement - a scheduled run overlapping a click in the desktop app,
or Task Scheduler's repeat firing while an OCR-heavy pass is still going -
would race on the same files, and the loser's index rows would be
overwritten by the winner's. That is the one way an original can end up in
``PBC/`` with no record of how it got there, so the lock is not optional
and it is not per step: whoever holds ``_scan.lock`` owns the engagement
until they let go.

The lock is a file created with ``O_EXCL`` (atomic on NTFS and POSIX) that
names the process and the time. A lock older than an hour is assumed to
belong to a run that died without cleaning up and is replaced with a
warning; a younger one is respected and the caller is told to wait.

Dry runs never take the lock - they write nothing, so they cannot race.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

log = logging.getLogger("tracker.locking")

#: Kept as ``_scan.lock`` so existing engagements, docs and habits still apply.
LOCK_FILENAME = "_scan.lock"
STALE_LOCK_SECONDS = 3600


class EngagementLockedError(RuntimeError):
    """Another sort or scan of this engagement appears to be running."""


def acquire_lock(engagement_dir: Path) -> Path:
    """Take the engagement lock or raise :class:`EngagementLockedError`."""
    lock = engagement_dir / LOCK_FILENAME
    for _attempt in (1, 2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as fh:
                fh.write(f"pid={os.getpid()} started={dt.datetime.now().isoformat()}")
            return lock
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue  # lock vanished between checks; retry
            if age < STALE_LOCK_SECONDS:
                raise EngagementLockedError(
                    f"another scan or sort appears to be running ({lock.name} is "
                    f"{age:.0f}s old); if not, delete the lock file"
                ) from None
            log.warning("Replacing stale engagement lock (%.0f s old)", age)
            lock.unlink(missing_ok=True)
    raise EngagementLockedError(f"could not acquire {lock.name}")


@contextmanager
def engagement_lock(engagement_dir: Path) -> Iterator[Path]:
    """Hold the engagement lock for the duration of a ``with`` block."""
    lock = acquire_lock(Path(engagement_dir))
    try:
        yield lock
    finally:
        lock.unlink(missing_ok=True)
