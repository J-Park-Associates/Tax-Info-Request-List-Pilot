"""Tests for tracker/locking.py — one lock per engagement, shared by sort and scan.

The claim: two runs cannot work the same engagement at once, a run that
died does not block the next one for ever, the lock is always released -
and only by the run that holds it.
"""

import datetime as dt
import os

import pytest

from tracker.locking import (
    LOCK_FILENAME,
    RUN_TIME_LIMIT_SECONDS,
    STALE_LOCK_SECONDS,
    EngagementLockedError,
    acquire_lock,
    engagement_lock,
    lock_line,
)

on_windows = pytest.mark.skipif(os.name != "nt", reason="Windows refuses to delete an open file")


def test_lock_is_taken_and_released(tmp_path):
    with engagement_lock(tmp_path) as lock:
        assert lock.path == tmp_path / LOCK_FILENAME
        assert lock.path.exists()
        assert "pid=" in lock.path.read_text(encoding="utf-8")
    assert not lock.path.exists()


def test_a_fresh_lock_blocks_a_second_run(tmp_path):
    (tmp_path / LOCK_FILENAME).write_text(f"pid={os.getpid()}", encoding="utf-8")
    with pytest.raises(EngagementLockedError, match="another scan or sort"):
        acquire_lock(tmp_path)


def test_a_stale_lock_is_replaced(tmp_path):
    lock = tmp_path / LOCK_FILENAME
    lock.write_text(f"pid={os.getpid()}", encoding="utf-8")
    old = (dt.datetime.now() - dt.timedelta(seconds=STALE_LOCK_SECONDS + 1)).timestamp()
    os.utime(lock, (old, old))
    with engagement_lock(tmp_path):
        assert str(os.getpid()) in lock.read_text(encoding="utf-8")
    assert not lock.exists()


def test_lock_is_released_when_the_body_raises(tmp_path):
    with pytest.raises(RuntimeError):
        with engagement_lock(tmp_path):
            raise RuntimeError("boom")
    assert not (tmp_path / LOCK_FILENAME).exists()


def test_lock_status_reads_what_the_lock_says(tmp_path):
    from tracker.locking import lock_status

    assert lock_status(tmp_path) is None
    with engagement_lock(tmp_path):
        status = lock_status(tmp_path)
        assert status is not None and not status.stale
        assert status.pid == str(os.getpid()) and status.started
        assert status.age_seconds < 5


def test_a_fresh_lock_is_refused_and_a_stale_one_cleared(tmp_path):
    from tracker.locking import clear_stale_lock, lock_status

    with pytest.raises(EngagementLockedError, match="no lock to clear"):
        clear_stale_lock(tmp_path)
    lock = tmp_path / LOCK_FILENAME
    lock.write_text(f"pid={os.getpid()} started=2026-03-14T07:03:00", encoding="utf-8")
    with pytest.raises(EngagementLockedError, match="may still be going"):
        clear_stale_lock(tmp_path)
    old = (dt.datetime.now() - dt.timedelta(seconds=STALE_LOCK_SECONDS + 1)).timestamp()
    os.utime(lock, (old, old))
    cleared = clear_stale_lock(tmp_path)
    assert cleared.stale and cleared.started == "2026-03-14T07:03:00"
    assert lock_status(tmp_path) is None


# ---------------------------------------------------------- held, and owned ----


def test_the_stale_threshold_outlives_the_scheduled_jobs_time_limit():
    # A lock younger than the limit can belong to a run Task Scheduler has
    # not killed yet; calling it stale would let the next repeat race it.
    assert STALE_LOCK_SECONDS > RUN_TIME_LIMIT_SECONDS


def test_a_lock_replaced_while_held_is_not_released_by_its_old_owner(tmp_path, caplog):
    lock = tmp_path / LOCK_FILENAME
    with engagement_lock(tmp_path):
        theirs = lock_line(os.getpid(), dt.datetime(2026, 3, 14, 7, 3))
        lock.write_text(theirs, encoding="utf-8")       # another run took it over
    assert lock.exists() and lock.read_text(encoding="utf-8") == theirs
    assert "replaced by another run" in caplog.text


@on_windows
def test_a_held_lock_cannot_be_deleted_from_outside(tmp_path):
    lock = tmp_path / LOCK_FILENAME
    with engagement_lock(tmp_path):
        with pytest.raises(PermissionError):
            lock.unlink()
        # Even one that looks stale by age is refused while its owner holds it.
        old = (dt.datetime.now() - dt.timedelta(seconds=STALE_LOCK_SECONDS + 1)).timestamp()
        os.utime(lock, (old, old))
        with pytest.raises(EngagementLockedError, match="still held by a running process"):
            acquire_lock(tmp_path)
    assert not lock.exists()


@on_windows
def test_clearing_a_stale_lock_that_is_still_held_is_refused(tmp_path):
    from tracker.locking import clear_stale_lock

    lock = tmp_path / LOCK_FILENAME
    with engagement_lock(tmp_path):
        old = (dt.datetime.now() - dt.timedelta(seconds=STALE_LOCK_SECONDS + 1)).timestamp()
        os.utime(lock, (old, old))
        with pytest.raises(EngagementLockedError, match="still held by a running process"):
            clear_stale_lock(tmp_path)
        assert lock.exists()


def test_a_lock_whose_owner_is_gone_is_stale_at_any_age(tmp_path):
    # The desktop shell kills the API at its own timeout, long before the
    # scheduled job's limit; the lock it leaves names a process that is not
    # running, and nobody should wait two hours for it.
    import subprocess
    import sys

    from tracker.locking import clear_stale_lock, lock_status

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    lock = tmp_path / LOCK_FILENAME
    lock.write_text(lock_line(child.pid, dt.datetime.now()), encoding="utf-8")
    try:
        assert lock_status(tmp_path).stale is False
        with pytest.raises(EngagementLockedError):
            clear_stale_lock(tmp_path)
    finally:
        child.kill()
        child.wait()
    assert lock_status(tmp_path).stale is True and lock_status(tmp_path).owner_gone
    with engagement_lock(tmp_path):                       # replaced, not refused
        assert str(os.getpid()) in lock.read_text(encoding="utf-8")
    lock.write_text(lock_line(child.pid, dt.datetime.now()), encoding="utf-8")
    assert clear_stale_lock(tmp_path).owner_gone
    assert not lock.exists()


def test_a_lock_naming_no_process_falls_back_to_its_age(tmp_path):
    from tracker.locking import lock_status

    lock = tmp_path / LOCK_FILENAME
    lock.write_text("started=2026-03-14T07:03:00", encoding="utf-8")
    assert lock_status(tmp_path).stale is False
    with pytest.raises(EngagementLockedError):
        with engagement_lock(tmp_path):
            pass
