"""Tests for tracker/locking.py — one lock per engagement, shared by sort and scan.

The claim: two runs cannot work the same engagement at once, a run that
died does not block the next one for ever, and the lock is always released.
"""

import datetime as dt
import os

import pytest

from tracker.locking import (
    LOCK_FILENAME,
    EngagementLockedError,
    acquire_lock,
    engagement_lock,
)


def test_lock_is_taken_and_released(tmp_path):
    with engagement_lock(tmp_path) as lock:
        assert lock == tmp_path / LOCK_FILENAME
        assert lock.exists()
        assert "pid=" in lock.read_text(encoding="utf-8")
    assert not lock.exists()


def test_a_fresh_lock_blocks_a_second_run(tmp_path):
    (tmp_path / LOCK_FILENAME).write_text("pid=999", encoding="utf-8")
    with pytest.raises(EngagementLockedError, match="another scan or sort"):
        acquire_lock(tmp_path)


def test_a_stale_lock_is_replaced(tmp_path):
    lock = tmp_path / LOCK_FILENAME
    lock.write_text("pid=999", encoding="utf-8")
    old = (dt.datetime.now() - dt.timedelta(hours=2)).timestamp()
    os.utime(lock, (old, old))
    with engagement_lock(tmp_path):
        assert str(os.getpid()) in lock.read_text(encoding="utf-8")
    assert not lock.exists()


def test_lock_is_released_when_the_body_raises(tmp_path):
    with pytest.raises(RuntimeError):
        with engagement_lock(tmp_path):
            raise RuntimeError("boom")
    assert not (tmp_path / LOCK_FILENAME).exists()
