"""Waiting for, and counting, the reading children a test starts.

A reading runs in a child process (decision 137), and a claim about it has to
ask the system whether the child is still there, wait for it to be gone, and
know the stop it was given. ``test_content_check`` wrote those helpers and
``test_containers`` and ``test_ocr`` borrowed them (``from
tests.test_content_check import no_child_left``); they live here so the
borrowing names a module that is not a test file (SPEC-architecture E-4,
R2.1). The stand-in readers a child runs are in ``tests/child_readers.py``,
because a patch made in the test never reaches the child.

Moved with their words from ``tests/test_content_check.py``; nothing here is new.
"""

from pathlib import Path

#: The stop these claims patch in, in seconds. A child starts in about half
#: a second on the office machine; this leaves a slow build runner room to
#: reach the stage it is claimed to be stopped in.
STOP_IN_TESTS = 5.0


#: What a reading stopped at a stop under a minute says.
STOPPED = "The reader stopped after 1 minute on this file. A person reads it."


CRASHED = "The reader could not read this file (it stopped unexpectedly). A person reads it."


def no_child_left():
    """No reading's child of this process is still running."""
    import multiprocessing

    return multiprocessing.active_children() == []


#: Where Linux keeps what it knows of a process. A Mac has no such folder, and
#: a test stands in for one by pointing this at a place that is not there (the
#: suite stands in for a platform by a seam, never by changing ``sys.platform``).
PROC = Path("/proc")


def _ps_state(pid: int) -> str | None:
    """The state letters ``ps`` gives process ``pid`` (a zombie's start with
    "Z"), "" for a process that is not there, None when ``ps`` cannot say.
    A Mac's way to ask, and Linux's when there is no ``/proc``; ``ps -o stat=``
    is the form both understand."""
    import subprocess

    try:
        done = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False)
    except OSError:
        return None
    return done.stdout.strip() if done.returncode in (0, 1) else None


def process_state(pid: int) -> str | None:
    """What the system says of process ``pid``: its state letters (a zombie's
    start with "Z"), "" for a process that is not there, None when it cannot
    be asked. Linux is asked in ``/proc``; anywhere that has none (a Mac), in
    ``ps``. Before this, a Mac fell back to "alive" for a zombie and every test
    waiting for a stopped reader's child to end waited out its whole fifteen
    seconds."""
    if not PROC.is_dir():
        return _ps_state(pid)
    try:
        return (PROC / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[0]
    except FileNotFoundError:
        return ""
    except (OSError, IndexError):
        return None


def running(pid: int) -> bool:
    """Whether the process ``pid`` is still running, asked of the system.

    Every caller asks about a process this test did not start - a reader's
    helper, the pass's child - so the system is asked, and a zombie has ended
    though its number is still taken. (A child the test started itself could
    be asked exactly by ``os.waitpid(pid, os.WNOHANG)``; none is asked today,
    and a parameter nothing uses was not kept for the one that will.)"""
    import os
    import sys

    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        handle = kernel32.OpenProcess(0x1000, False, pid)     # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == 259                          # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    state = process_state(pid)
    return state is None or (state != "" and not state.startswith("Z"))   # a zombie has ended


def eventually(check, within: float = 15.0) -> bool:
    import time

    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.1)
    return check()


def _a_reader_only_the_pass_has(monkeypatch):
    """A reader the child can never import: its module is in the pass's
    process only, so the child ends while it is still being set up - the
    shape of a frozen build missing a module, or a machine that cannot
    start the reader - before it has said "started"."""
    import sys
    import types

    module = types.ModuleType("only_in_the_pass_150")

    def reader(path, *, ocr=True):          # never runs: the child cannot find it
        raise AssertionError("unreachable")

    reader.__module__ = module.__name__
    reader.__qualname__ = "reader"
    module.reader = reader
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return reader
