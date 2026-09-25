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
    release_lock,
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


def test_a_lock_from_another_machine_is_judged_by_its_age_alone(tmp_path):
    # A synced clients root: the other machine's pid is never alive here,
    # and that must not read as "gone". Only the age rule may replace it.
    from tracker.locking import lock_status

    lock = tmp_path / LOCK_FILENAME
    import platform

    theirs = lock_line(424242, dt.datetime.now()).replace(
        f"host={platform.node().lower()}", "host=other-pc")
    assert "host=other-pc" in theirs
    lock.write_text(theirs, encoding="utf-8")
    assert lock_status(tmp_path).owner_gone is False and lock_status(tmp_path).stale is False
    with pytest.raises(EngagementLockedError):
        with engagement_lock(tmp_path):
            pass


def test_a_lock_that_cannot_be_deleted_on_release_does_not_block_its_own_process(tmp_path, monkeypatch):
    # A sync client held the file while the sort let go; the scan that
    # follows in the same process must not find its own live pid and wait.
    import tracker.locking as locking_module
    from tracker.locking import lock_status

    lock = tmp_path / LOCK_FILENAME
    real_unlink = locking_module.Path.unlink

    def held(self, *args, **kwargs):
        if self == lock:
            raise PermissionError("[WinError 32] being uploaded")
        return real_unlink(self, *args, **kwargs)
    monkeypatch.setattr(locking_module, "_RELEASE_RETRY_DELAY", 0)
    monkeypatch.setattr(locking_module.Path, "unlink", held)
    with engagement_lock(tmp_path):
        pass
    assert lock.exists() and lock_status(tmp_path).released and lock_status(tmp_path).stale
    monkeypatch.undo()
    with engagement_lock(tmp_path):                          # the next step, same process
        assert str(os.getpid()) in lock.read_text(encoding="utf-8")
    assert not lock.exists()


# ------------------------------------------- the Drive test (decision 171) ----
# The Drive test of 2026-09-25: on Google Drive for desktop a contended
# release's unlink can report success and leave the file (F1), and on any
# Windows drive taking the lock while another process deletes it raises
# PermissionError rather than FileExistsError (F2).


def _unlink_that_does_not_take(lock, monkeypatch, then=None):
    """Make ``Path.unlink`` on ``lock`` return without removing it, as G: did."""
    import tracker.locking as locking_module

    real_unlink = locking_module.Path.unlink

    def ghost(self, *args, **kwargs):
        if self == lock:
            if then is not None:
                then()
            return None
        return real_unlink(self, *args, **kwargs)
    monkeypatch.setattr(locking_module, "_RELEASE_RETRY_DELAY", 0)
    monkeypatch.setattr(locking_module.Path, "unlink", ghost)


def test_a_release_whose_unlink_did_not_take_marks_the_lock_released(tmp_path, monkeypatch, caplog):
    from tracker.locking import RELEASED_LINE, lock_status

    lock = tmp_path / LOCK_FILENAME
    _unlink_that_does_not_take(lock, monkeypatch)
    with engagement_lock(tmp_path):
        pass
    assert lock.read_text(encoding="utf-8") == RELEASED_LINE
    assert lock_status(tmp_path).released and lock_status(tmp_path).stale
    assert "reported done but the file stayed" in caplog.text and str(lock) in caplog.text
    monkeypatch.undo()
    with engagement_lock(tmp_path):                          # the next step, same process
        assert str(os.getpid()) in lock.read_text(encoding="utf-8")
    assert not lock.exists()


def test_a_release_leaves_a_lock_another_run_took_alone(tmp_path, monkeypatch):
    # The delete "failed", and by the time the file is read back another run
    # has taken the lock: its lock, not ours to mark or remove.
    lock = tmp_path / LOCK_FILENAME
    theirs = lock_line(424242, dt.datetime(2026, 3, 14, 7, 3))
    _unlink_that_does_not_take(lock, monkeypatch,
                               then=lambda: lock.write_text(theirs, encoding="utf-8"))
    with engagement_lock(tmp_path):
        pass
    assert lock.read_text(encoding="utf-8") == theirs


def test_a_read_refused_after_the_delete_is_no_proof_it_went(tmp_path, monkeypatch):
    # G: refused the read-back right after a "successful" delete while the
    # delete was pending. Only the file's absence proves it went, so the
    # release looks again - here the first delete did not take, and the
    # second one does.
    import tracker.locking as locking_module

    lock = tmp_path / LOCK_FILENAME
    real_unlink, real_read = locking_module.Path.unlink, locking_module.Path.read_text
    calls = {"unlink": 0, "refuse_next_read": False}

    def unlink(self, *args, **kwargs):
        if self == lock:
            calls["unlink"] += 1
            if calls["unlink"] == 1:
                calls["refuse_next_read"] = True
                return None                                  # reported done, did not take
        return real_unlink(self, *args, **kwargs)

    def read_text(self, *args, **kwargs):
        if self == lock and calls["refuse_next_read"]:
            calls["refuse_next_read"] = False
            raise PermissionError(13, "Permission denied", str(self))
        return real_read(self, *args, **kwargs)
    monkeypatch.setattr(locking_module, "_RELEASE_RETRY_DELAY", 0)
    monkeypatch.setattr(locking_module.Path, "unlink", unlink)
    monkeypatch.setattr(locking_module.Path, "read_text", read_text)
    with engagement_lock(tmp_path):
        pass
    assert calls["unlink"] == 2
    assert not lock.exists()


def test_a_process_is_never_refused_by_its_own_leftover_lock(tmp_path, caplog):
    # A fresh lock naming this very process, which does not hold it: the
    # ghost of a release that did not take. Waiting two hours for it would
    # lock the app's API process out of its own engagement.
    lock = tmp_path / LOCK_FILENAME
    ghost = lock_line(os.getpid(), dt.datetime.now())
    lock.write_text(ghost, encoding="utf-8")
    with engagement_lock(tmp_path):
        assert lock.read_text(encoding="utf-8") != ghost
        assert str(os.getpid()) in lock.read_text(encoding="utf-8")
    assert "Replacing stale engagement lock" in caplog.text
    assert "left by this process" in caplog.text
    assert not lock.exists()


def test_a_lock_this_process_really_holds_is_still_refused(tmp_path):
    # A double acquire is a bug, and stays loud.
    first = acquire_lock(tmp_path)
    try:
        with pytest.raises(EngagementLockedError, match="another scan or sort"):
            acquire_lock(tmp_path)
    finally:
        release_lock(first)
    assert not (tmp_path / LOCK_FILENAME).exists()
    with engagement_lock(tmp_path):                          # released means free again
        pass


def test_a_permission_error_while_taking_the_lock_is_a_lock_not_a_crash(tmp_path, monkeypatch):
    # Windows refuses the create while another process's delete of the lock
    # file is pending: the file is still at its name, and then it is gone.
    import tracker.locking as locking_module

    lock = tmp_path / LOCK_FILENAME
    real_open = os.open
    refusals = {"left": 1}

    def delete_pending(path, *args, **kwargs):
        if os.fspath(path) == os.fspath(lock):
            if refusals["left"]:
                refusals["left"] -= 1
                raise PermissionError(13, "Permission denied", os.fspath(path))
            lock.unlink(missing_ok=True)                     # the other run's delete finished
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr(locking_module, "_CHANGING_HANDS_DELAY", 0)
    monkeypatch.setattr(locking_module.os, "open", delete_pending)
    lock.write_text(lock_line(424242, dt.datetime.now()), encoding="utf-8")   # being deleted
    with engagement_lock(tmp_path):                          # refused once, then taken
        assert str(os.getpid()) in lock.read_text(encoding="utf-8")
    assert not lock.exists()

    lock.write_text(lock_line(424242, dt.datetime.now()), encoding="utf-8")   # and stays pending
    refusals["left"] = 10**6                                 # refused every time
    with pytest.raises(EngagementLockedError, match="is changing hands; another scan or sort is finishing") as raised:
        acquire_lock(tmp_path)
    assert not isinstance(raised.value, PermissionError)
    assert refusals["left"] == 10**6 - locking_module._CHANGING_HANDS_ATTEMPTS


def test_an_unwritable_folder_is_a_run_error_not_another_run(tmp_path, monkeypatch):
    # No lock file is there, and the create is still refused: this account
    # cannot write to the folder. Called "another run", every pass would skip
    # the return quietly, for a run that does not exist.
    import tracker.locking as locking_module
    from tests.conftest import make_engagement
    from tests.samples import DEMO_ITEMS
    from tracker.registry import engagement_from
    from tracker.runner import REMINDERS_NEVER, run_engagement

    folder = make_engagement(tmp_path, DEMO_ITEMS)
    lock = folder / LOCK_FILENAME
    real_open = os.open
    refused = []

    def unwritable(path, *args, **kwargs):
        if os.fspath(path) == os.fspath(lock):
            refused.append(PermissionError(13, "Permission denied", os.fspath(path)))
            raise refused[-1]
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr(locking_module, "_CHANGING_HANDS_DELAY", 0)
    monkeypatch.setattr(locking_module.os, "open", unwritable)

    with pytest.raises(PermissionError) as raised:
        acquire_lock(folder)
    assert not isinstance(raised.value, EngagementLockedError)
    assert raised.value is refused[0]                        # the original refusal
    assert len(refused) == 2                                 # once more at once, then no more
    assert not lock.exists()

    run = run_engagement(engagement_from(folder), root=tmp_path, reminders=REMINDERS_NEVER)
    assert run.error.startswith("PermissionError") and not run.skipped


def test_a_lock_taken_while_another_is_let_go_is_still_held(tmp_path, monkeypatch, caplog):
    # A lets go: its file is deleted, and before A stops counting the lock as
    # held, B takes the lock. A's release must not make B's lock look like a
    # leftover: a third taker C is refused with the ordinary sentence.
    import tracker.locking as locking_module

    lock = tmp_path / LOCK_FILENAME
    a = acquire_lock(tmp_path)
    taken = {}
    real_release = locking_module._release

    def release_then_b_takes(held):
        real_release(held)                                   # A's file is gone ...
        taken["b"] = acquire_lock(tmp_path)                  # ... and B takes the name
    monkeypatch.setattr(locking_module, "_release", release_then_b_takes)
    release_lock(a)                                          # ... before A's entry is dropped
    monkeypatch.undo()
    b = taken["b"]
    try:
        caplog.clear()
        with pytest.raises(EngagementLockedError, match="another scan or sort appears to be running"):
            acquire_lock(tmp_path)                           # C
        assert "left by this process" not in caplog.text
        assert lock.read_text(encoding="utf-8") == b.token
    finally:
        release_lock(b)
    assert not lock.exists()


def test_a_retried_delete_never_lands_on_a_lock_another_run_took(tmp_path, monkeypatch):
    # The first delete is refused; while the release waits, ours goes and
    # another run takes the name. The retry reads the file first and leaves
    # theirs alone.
    import tracker.locking as locking_module

    lock = tmp_path / LOCK_FILENAME
    theirs = lock_line(424242, dt.datetime(2026, 3, 14, 7, 3))
    real_unlink = locking_module.Path.unlink
    deletes = []

    def refused_then_taken(self, *args, **kwargs):
        if self == lock:
            deletes.append(self)
            if len(deletes) == 1:
                lock.write_text(theirs, encoding="utf-8")    # ours went; theirs came
                raise PermissionError("[WinError 32] being uploaded")
        return real_unlink(self, *args, **kwargs)
    monkeypatch.setattr(locking_module, "_RELEASE_RETRY_DELAY", 0)
    monkeypatch.setattr(locking_module.Path, "unlink", refused_then_taken)
    with engagement_lock(tmp_path):
        pass
    assert len(deletes) == 1
    assert lock.read_text(encoding="utf-8") == theirs


_CONTENDER = """
import sys, time
from pathlib import Path
from tracker.locking import EngagementLockedError, acquire_lock, release_lock

root, me, cycles = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
deadline = time.monotonic() + 150
done = 0
while done < cycles:
    if time.monotonic() > deadline:
        sys.exit(f"{me} timed out after {done} cycles")
    try:
        lock = acquire_lock(root)
    except EngagementLockedError:
        time.sleep(0.001)
        continue
    try:
        with open(root / "journal.txt", "a", encoding="utf-8") as journal:
            journal.write(f"{me} {done}\\n")
    finally:
        release_lock(lock)
    done += 1
    time.sleep(0.001)
"""


def test_two_processes_contending_for_one_lock_lose_no_line_and_leave_no_lock(tmp_path):
    # The Drive test's contention on the local disk: two processes take,
    # append and release in turn. No raw PermissionError may escape (F2),
    # every line lands, and the last release leaves nothing behind.
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    cycles = 50
    children = [
        subprocess.Popen([sys.executable, "-c", _CONTENDER, str(tmp_path), name, str(cycles)],
                         cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for name in ("a", "b")
    ]
    try:
        for child in children:
            out, err = child.communicate(timeout=240)
            assert child.returncode == 0, err
    finally:
        for child in children:                               # never leave one running
            if child.poll() is None:
                child.kill()
                child.wait()
    lines = (tmp_path / "journal.txt").read_text(encoding="utf-8").splitlines()
    assert sorted(lines) == sorted(f"{name} {i}" for name in ("a", "b") for i in range(cycles))
    assert not (tmp_path / LOCK_FILENAME).exists()
