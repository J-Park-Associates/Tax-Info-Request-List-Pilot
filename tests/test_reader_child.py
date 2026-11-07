"""Tests for tracker/reader_child.py - the pass's one reading child, its
supervisor and the pass's session (decisions 150, 169 R-4, 186 and 189).

The child claims run a real child process, as the pass makes it, with the
stand-in readers of tests/child_readers.py and the stops patched down to
seconds. The graphics card's claims cross into a real spawned child too; the
parent is told there is a pack, which is what makes a child "on the card".

They came from tests/test_ocr.py with P338 (SPEC-architecture-p4 P4.12), cut
and pasted with their names: the tests whose highest home, by section 4.1's
rule, is tracker/reader_child.py. The fixtures both files take -
``in_a_child``, ``a_short_stop`` and ``a_card`` - are tests/ocr_helpers.py's,
named here by assignment.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import ocr_helpers
from tests.children import CRASHED, STOP_IN_TESTS, STOPPED, eventually, no_child_left, running
from tests.samples import text_pdf
from tracker import content_check, locking, ocr, reader_child, verdicts

in_a_child = ocr_helpers.in_a_child
a_short_stop = ocr_helpers.a_short_stop
a_card = ocr_helpers.a_card


# ----------------------------------------------- one child for the pass ----


def pid_of_the_reader(path: Path) -> int:
    """Which child read ``path`` (the stand-in answers with its process id)."""
    from tests import child_readers

    answer, failed = content_check.in_a_child(path, child_readers.the_childs_process_id)
    assert failed is None, failed.reason
    return int(answer.text)


def test_one_child_reads_every_document_of_a_pass_and_ends_with_it(tmp_path, in_a_child):
    """R-4: one reading child per pass, serving documents one at a time -
    a child per document paid the engine's load every time - and none left
    when the pass ends. A reading made with no pass open has a child of its
    own, ended with it."""
    pages = [text_pdf(tmp_path / f"page {n}.pdf", "Form W-2 2025", style="bare") for n in range(3)]
    with reader_child.reading_session():
        pids = [pid_of_the_reader(page) for page in pages]
        assert len(set(pids)) == 1 and running(pids[0])
    assert eventually(lambda: not running(pids[0]))
    assert no_child_left()

    alone = pid_of_the_reader(pages[0])
    assert alone != pids[0] and no_child_left()


def test_a_long_lived_reader_is_replaced_every_hundred_documents(tmp_path, in_a_child):
    """R-4's hygiene: a child that has served its count is let go and the
    next document gets a fresh one. (The count is patched down from 100.)"""
    in_a_child.setattr(reader_child, "DOCUMENTS_PER_CHILD", 2)
    pages = [text_pdf(tmp_path / f"page {n}.pdf", "Form W-2 2025", style="bare") for n in range(3)]
    with reader_child.reading_session():
        first, second, third = (pid_of_the_reader(page) for page in pages)
    assert first == second != third
    assert no_child_left()


def test_a_long_lived_reader_is_replaced_after_a_stop(tmp_path, a_short_stop):
    """150's first guarantee, for the one child: the document's stop ends
    it - and everything it started - the document is abandoned, and the
    next document gets a fresh child that reads it."""
    from tests import child_readers

    stuck = text_pdf(tmp_path / "stuck.pdf", "Form W-2 2025", style="bare")
    after = text_pdf(tmp_path / "after.pdf", "Form W-2 2025", style="bare")
    with reader_child.reading_session():
        before = pid_of_the_reader(after)
        answer, failed = content_check.in_a_child(stuck, child_readers.a_text_layer_that_never_finishes)
        assert answer is None and failed.reason == STOPPED
        assert eventually(lambda: not running(before)), "the stopped child is still running"
        fresh = pid_of_the_reader(after)
        assert fresh != before and running(fresh)
    assert no_child_left()


def test_a_long_lived_reader_is_replaced_after_a_crash(tmp_path, in_a_child):
    """150's second guarantee, for the one child: a crash parks only the
    document being read, and the next document is read by a fresh child."""
    from tests import child_readers

    crash = text_pdf(tmp_path / "a crash.pdf", "Form W-2 Wage and Tax Statement 2025", style="bare")
    after = text_pdf(tmp_path / "after.pdf", "Form W-2 Wage and Tax Statement 2025", style="bare")
    with reader_child.reading_session():
        before = pid_of_the_reader(after)
        answer, failed = content_check.in_a_child(crash, child_readers.a_reader_that_dies_on_a_crash)
        assert answer is None and failed.reason == CRASHED and not failed.transient
        judgment = content_check.judge_bounded(after, verdicts.Questions())
        assert judgment.has_words and "w2" in judgment.self_named
        assert pid_of_the_reader(after) != before
    assert no_child_left()


# -------------------------------- the graphics card, in a real child (S-2) ----
#
# REVIEW-169: every claim above about the card runs in the test's own
# process, where the fakes live. These cross into a real spawned child, so
# the path the pass takes - the child's notes, the pipe, the session's
# hearing, the replacement - is what is proved. The child has no pack (it
# is not the frozen app); the parent is told there is one, which is what
# makes a child "on the card" to the session.


def who_read(session: reader_child.Session, path: Path, reader) -> tuple[int, bool]:
    """(the child's process id, whether it was kept on the processor)."""
    outcome = session.run(reader, (path,), {}, STOP_IN_TESTS * 6)
    assert outcome.kind == "read", (outcome.kind, outcome.error)
    pid, processor_only = outcome.answer.text.split()
    return int(pid), processor_only == "True"


@pytest.fixture
def a_pack_here(monkeypatch, tmp_path):
    pack = tmp_path / ocr.GPU_PACK_DIR_NAME
    pack.mkdir()
    for module in (ocr, reader_child):
        monkeypatch.setattr(module, "gpu_pack", lambda: pack)
    return pack


def test_a_card_fault_in_a_child_moves_the_rest_of_the_pass_to_the_processor(tmp_path, a_pack_here):
    """Ruling 3, end to end: the child's note of a fault crosses the pipe,
    the session hears it, lets that child go, and the next document is read
    by a new child told to keep to the processor. One warning."""
    from tests import child_readers

    fault, after = tmp_path / "a fault.pdf", tmp_path / "after.pdf"
    with reader_child.reading_session() as session:
        first, first_off_the_card = who_read(session, fault, child_readers.a_reader_that_tells_the_pass)
        second, second_off_the_card = who_read(session, after, child_readers.a_reader_that_tells_the_pass)
        assert not first_off_the_card and second_off_the_card and second != first
        assert session.warnings() == [ocr.GPU_FAULT_WARNING.format(file="a fault.pdf")]
        assert session.warnings() == []
        assert who_read(session, after, child_readers.a_reader_that_tells_the_pass) == (second, True)
    assert no_child_left()


def test_a_pack_found_unusable_in_a_child_keeps_every_later_child_off_the_card(tmp_path, a_pack_here):
    """S-3: an app command opens its session without the warm-up, so the
    first child finds the pack unusable. Every child after it - after a
    crash, a stop or its hundred documents - reads on the processor, rather
    than trying the card again inside a document's own stop."""
    from tests import child_readers

    unusable, crash = tmp_path / "unusable.pdf", tmp_path / "a crash.pdf"
    with reader_child.reading_session() as session:
        _pid, off_the_card = who_read(session, unusable, child_readers.a_reader_that_tells_the_pass)
        assert not off_the_card and "could not be used" in session.note
        session.run(child_readers.a_reader_that_dies_on_a_crash, (crash,), {}, STOP_IN_TESTS * 6)
        assert who_read(session, unusable, child_readers.a_reader_that_tells_the_pass)[1] is True
        assert session.warnings() == []                   # a run-log line, not a warning
    assert no_child_left()


def test_a_card_child_that_dies_is_a_card_fault_and_the_document_is_read_on_the_processor(
        tmp_path, a_pack_here):
    """M-1: a child on the card that ends with no answer - a native CUDA
    crash, or the card child's memory limit - is a fault on the card, not
    the file's. The same document is read once more on a fresh processor
    child, the pass warns once, and every later document stays there."""
    from tests import child_readers

    scan = text_pdf(tmp_path / "scan.pdf", "Form W-2 2025", style="bare")
    after = text_pdf(tmp_path / "after.pdf", "Form W-2 2025", style="bare")
    with reader_child.reading_session() as session:
        answer, failed = content_check.in_a_child(scan, child_readers.a_card_that_dies)
        assert failed is None, failed.reason
        pid, off_the_card = answer.text.split()
        assert off_the_card == "True"
        assert session.warnings() == [ocr.GPU_FAULT_WARNING.format(file="scan.pdf")]
        assert who_read(session, after, child_readers.a_card_that_dies) == (int(pid), True)
        assert session.warnings() == []
    assert no_child_left()


def test_a_death_in_a_used_child_is_retried_once_on_a_fresh_one(tmp_path):
    """S-1: a child that has served a document may die of what the earlier
    ones left behind. The document is read again on a fresh child before it
    is blamed; only a death on a fresh processor child is the file's own
    (the crash test above: its second try dies too, and it is kept)."""
    from tests import child_readers

    one, two = tmp_path / "one.pdf", tmp_path / "two.pdf"
    with reader_child.reading_session() as session:
        first, _ = who_read(session, one, child_readers.a_reader_that_dies_once_used)
        second, off_the_card = who_read(session, two, child_readers.a_reader_that_dies_once_used)
        assert second != first and off_the_card is False     # no pack: not the card's
        assert session.warnings() == []
    assert no_child_left()


@pytest.mark.skipif(sys.platform != "win32", reason="the memory cap is the Windows job object's")
def test_the_reading_childs_job_caps_its_memory(a_pack_here):
    """SPEC-169 section 9, amended by P285: 4 GB for a processor child, 6 GB for a child on
    the graphics card, set on the job object that already ends it."""
    for processor_only, cap in ((True, reader_child.PROCESSOR_CHILD_MEMORY),
                                (False, reader_child.GRAPHICS_CARD_CHILD_MEMORY)):
        child = reader_child.ReadingChild(processor_only=processor_only)
        try:
            assert reader_child._job_memory(child._job_object)[0] == cap
        finally:
            child.finish()
    assert (reader_child.PROCESSOR_CHILD_MEMORY, reader_child.GRAPHICS_CARD_CHILD_MEMORY) == (4 * 1024**3, 6 * 1024**3)


@pytest.mark.skipif(sys.platform != "win32", reason="the memory cap is the Windows job object's")
def test_a_child_over_its_memory_limit_is_replaced_and_the_next_document_reads(tmp_path):
    """SPEC-169 section 9: a document that wants more than the child's 4 GB
    fails in that child, which says so and ends; the document gets the
    crash's "could not be read", kept for a person, and the next document
    is read by a fresh child."""
    from tests import child_readers

    big = text_pdf(tmp_path / "big.pdf", "Form W-2 2025", style="bare")
    after = text_pdf(tmp_path / "after.pdf", "Form W-2 2025", style="bare")
    with reader_child.reading_session() as session:
        answer, failed = content_check.in_a_child(big, child_readers.a_reader_that_needs_too_much_memory)
        assert answer is None and failed.reason == CRASHED and not failed.transient
        assert failed.error.startswith("MemoryError")
        assert session.child is None                      # let go, not asked again
        pid, _ = who_read(session, after, child_readers.a_reader_that_needs_too_much_memory)
        assert running(pid)
    assert no_child_left()


# ----------------------------- the memory watch off Windows (R31, SPEC-mac) ----

OFF_WINDOWS = pytest.mark.skipif(sys.platform == "win32", reason="Windows' cap is the job object's")


def a_footprint_that_is_over_for(pid_mark: Path, over: int):
    """A stand-in for the child's memory reading: ``over`` for the one
    process whose id the mark file holds (the child that is reading the
    runaway document), a few bytes for every other. The seam is the
    reading, not the platform."""
    def footprint(pid, system=None):
        try:
            return over if int(pid_mark.read_text()) == pid else 1
        except (OSError, ValueError):
            return 1

    return footprint


@OFF_WINDOWS
def test_the_posix_watch_caps_a_child_the_way_the_job_object_does(a_pack_here):
    """R31: the same 4 GB for a processor child and 6 GB for a child on the
    graphics card, held by the pass's watch where Windows holds it in a job
    object - and no job object here to hold it."""
    for processor_only, cap in ((True, reader_child.PROCESSOR_CHILD_MEMORY),
                                (False, reader_child.GRAPHICS_CARD_CHILD_MEMORY)):
        child = reader_child.ReadingChild(processor_only=processor_only)
        try:
            assert child.memory_limit == cap
            assert child._watches_memory and child._job_object is None
        finally:
            child.finish()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc/<pid>/statm is Linux's")
def test_a_linux_childs_memory_is_its_resident_pages():
    """R31: the second field of /proc/<pid>/statm, in bytes. A process that
    touches 64 MB holds at least that much more than it did."""
    before = reader_child._footprint(os.getpid())
    held = bytearray(b"x" * (64 * 1024**2))
    after = reader_child._footprint(os.getpid())
    assert before > 0 and after - before >= 48 * 1024**2, (before, after)
    del held
    with pytest.raises(OSError):
        reader_child._footprint(2**22 + os.getpid())               # past pid_max: no such process


def test_a_macs_memory_is_the_physical_footprint_libproc_reports(monkeypatch):
    """R31: proc_pid_rusage(pid, RUSAGE_INFO_V2) through ctypes, the field
    Activity Monitor calls Memory - not the resident size beside it. The
    library is handed in; the structure is the real one."""
    asked = []

    def proc_pid_rusage(pid, flavor, buffer):
        info = buffer._obj
        info.ri_resident_size, info.ri_phys_footprint = 111, 987_654_321
        asked.append((pid, flavor))
        return 0

    monkeypatch.setattr(reader_child, "_libproc", lambda: SimpleNamespace(proc_pid_rusage=proc_pid_rusage))
    assert reader_child._footprint(4242, "darwin") == 987_654_321
    assert asked == [(4242, 2)]                           # RUSAGE_INFO_V2

    monkeypatch.setattr(reader_child, "_libproc", lambda: SimpleNamespace(proc_pid_rusage=lambda *a: -1))
    with pytest.raises(OSError, match="refused process 4242"):
        reader_child._footprint(4242, "darwin")


def test_a_platform_with_no_way_to_read_memory_says_so():
    with pytest.raises(OSError, match="plan9"):
        reader_child._footprint(1, "plan9")


@OFF_WINDOWS
def test_a_reading_past_its_memory_on_posix_ends_as_a_crash_and_is_replaced(tmp_path, in_a_child):
    """R31, the twin of the Windows job object's test: the child that is
    past the limit when the pass looks is ended whole, the document gets
    the crash's "could not be read" with today's words, kept for a person,
    and the next document is read by a fresh child."""
    from tests import child_readers

    in_a_child.setattr(reader_child, "MEMORY_WATCH_SECONDS", 0.1)
    big = text_pdf(tmp_path / "big.pdf", "Form W-2 2025", style="bare")
    again = text_pdf(tmp_path / "again.pdf", "Form W-2 2025", style="bare")
    after = text_pdf(tmp_path / "after.pdf", "Form W-2 2025", style="bare")
    over = reader_child.PROCESSOR_CHILD_MEMORY + 1
    in_a_child.setattr(reader_child, "_footprint", a_footprint_that_is_over_for(
        child_readers.reached(big, "text-layer"), over))
    with reader_child.reading_session() as session:
        outcome = session.run(child_readers.a_text_layer_that_never_finishes, (big,), {}, 60)
        assert outcome.kind == "died" and outcome.seconds < 30
        assert outcome.error.endswith("; it had reached its memory limit (4 GB)"), outcome.error
        assert session.child is None                      # let go, not asked again
        in_a_child.setattr(reader_child, "_footprint", a_footprint_that_is_over_for(
            child_readers.reached(again, "text-layer"), over))
        answer, failed = content_check.in_a_child(again, child_readers.a_text_layer_that_never_finishes,
                                                  stop=60)
        assert answer is None and failed.reason == CRASHED and not failed.transient
        pid, _ = who_read(session, after, child_readers.a_reader_that_tells_the_pass)
        assert running(pid)
    assert no_child_left()


@OFF_WINDOWS
def test_a_child_under_its_limit_is_left_to_read(tmp_path, in_a_child):
    """R31: the watch ends a child only when its memory is past the limit -
    a figure at the limit itself is a reading that goes on."""
    from tests import child_readers

    in_a_child.setattr(reader_child, "MEMORY_WATCH_SECONDS", 0.1)
    in_a_child.setattr(reader_child, "_footprint", lambda pid, system=None: reader_child.PROCESSOR_CHILD_MEMORY)
    slow = text_pdf(tmp_path / "slow.pdf", "Form W-2 2025", style="bare")
    child = reader_child.ReadingChild(processor_only=True)
    try:
        assert child.run(child_readers.the_childs_process_id, (slow,), {}, 60).kind == "read"
        outcome = child.run(child_readers.a_text_layer_that_never_finishes, (slow,), {}, 1.0)
        assert outcome.kind == "stopped"                  # by the stop, not by the memory
    finally:
        child.finish()


@OFF_WINDOWS
def test_the_watch_does_not_stretch_a_readings_stop(tmp_path, in_a_child):
    """R31: the wait is in slices, never longer than what is left of the
    stop, so a slice longer than the stop still ends the reading at the stop."""
    from tests import child_readers

    in_a_child.setattr(reader_child, "MEMORY_WATCH_SECONDS", 30.0)
    in_a_child.setattr(reader_child, "_footprint", lambda pid, system=None: 1)
    slow = text_pdf(tmp_path / "slow.pdf", "Form W-2 2025", style="bare")
    child = reader_child.ReadingChild(processor_only=True)
    try:
        assert child.run(child_readers.the_childs_process_id, (slow,), {}, 60).kind == "read"
        outcome = child.run(child_readers.a_text_layer_that_never_finishes, (slow,), {}, 0.6)
        assert outcome.kind == "stopped" and 0.5 <= outcome.seconds < 5, outcome.seconds
    finally:
        child.finish()


@OFF_WINDOWS
def test_a_footprint_that_cannot_be_read_is_no_cap_and_is_said_once(tmp_path, in_a_child, caplog):
    """R31: when the child's memory cannot be read the reading goes on to
    the stop - no guessed figure ends it - and the error log says so once,
    however many slices and children it happens in."""
    from tests import child_readers

    def unreadable(pid, system=None):
        raise OSError("no /proc")

    in_a_child.setattr(reader_child, "MEMORY_WATCH_SECONDS", 0.1)
    in_a_child.setattr(reader_child, "_footprint", unreadable)
    in_a_child.setattr(reader_child, "_SAID", set())
    slow = text_pdf(tmp_path / "slow.pdf", "Form W-2 2025", style="bare")
    for _ in range(2):
        child = reader_child.ReadingChild(processor_only=True)
        try:
            assert child.run(child_readers.the_childs_process_id, (slow,), {}, 60).kind == "read"
            with caplog.at_level("WARNING", logger=ocr.log.name):
                outcome = child.run(child_readers.a_text_layer_that_never_finishes, (slow,), {}, 0.8)
            assert outcome.kind == "stopped"
        finally:
            child.finish()
    said = [r.getMessage() for r in caplog.records if "memory could not be read" in r.getMessage()]
    assert said == [reader_child.MEMORY_UNREADABLE.format(reason="OSError")]


def test_a_reader_that_cannot_run_is_not_blamed_on_the_card(monkeypatch, a_card):
    """N-1: with a pack here and not even the processor's engine buildable
    (a model missing), the run log says the reader could not run on this
    machine - not that the card's pack could not be used."""
    def nothing_builds(*, cuda):
        raise ocr.ReaderUnavailable("the model PP-OCRv6_det_small.onnx is missing")

    monkeypatch.setattr(ocr, "_build_engine", nothing_builds)
    session = reader_child.Session(in_a_child=False)
    session.settle()
    assert session.note == ocr.READER_CANNOT_RUN.format(
        reason="the model PP-OCRv6_det_small.onnx is missing")
    assert session.device == ocr.DEVICE_PROCESSOR and "graphics card" not in session.note

    in_a_child = reader_child.Session()
    monkeypatch.setattr(reader_child.Session, "run", lambda *a, **k: reader_child.Outcome(
        "failed", error="ReaderUnavailable", message="the model PP-OCRv6_det_small.onnx is missing"))
    in_a_child.settle()
    assert in_a_child.note == session.note


# ------------------------------------------------ the awake clock (189) ----


@pytest.mark.parametrize("watches_memory", [False, True], ids=["one wait (Windows)", "watch slices"])
def test_time_asleep_does_not_count_toward_the_reading_stop(monkeypatch, watches_memory):
    """SPEC-161 A-F9: the machine sleeps mid-reading. The biased clock (the
    wall, and ``time.monotonic`` on Windows) jumps past the stop; the awake
    clock moves one second. The reading is not ended, and its answer is
    taken when the machine wakes. Both waits are held, on every platform:
    the single ``poll(left)`` Windows keeps, and the watch's slices (R31),
    where the memory is never read on Windows."""
    import time

    awake = [1000.0]
    biased = [5000.0]
    monkeypatch.setattr(reader_child, "awake_clock", lambda: awake[0])
    monkeypatch.setattr(time, "monotonic", lambda: biased[0])
    stop = 60.0

    class Answers:
        """The pipe: the first wait is slept through, then the child answers."""

        def __init__(self):
            self.said = [("started",), ("read", "the words", [], [])]
            self.waits = 0

        def poll(self, left):
            self.waits += 1
            if self.waits == 1:
                biased[0] += stop * 100       # a night asleep
                awake[0] += 1.0
                return False
            return True

        def recv(self):
            return self.said.pop(0)

    ended = []
    child = object.__new__(reader_child.ReadingChild)
    child._jobs = SimpleNamespace(send=lambda job: None)
    child._answers = Answers()
    child.served = 0
    child._watches_memory = watches_memory

    def past_its_memory(self):
        assert watches_memory, "Windows' job object caps the child; the pass never reads its memory"
        return False

    monkeypatch.setattr(reader_child.ReadingChild, "_past_its_memory", past_its_memory)
    monkeypatch.setattr(reader_child.ReadingChild, "end", lambda self: ended.append(True))

    outcome = child.run(len, ("x",), {}, stop)

    assert not ended, "a stop the machine slept through must not end the reading"
    assert outcome.kind == "read" and outcome.answer == "the words"
    assert outcome.seconds == pytest.approx(1.0)


def test_the_readings_own_stop_reads_the_awake_clock():
    assert content_check._clock is reader_child.awake_clock
    assert reader_child.awake_clock() <= reader_child.awake_clock()


# --------------------------------------- the reading child's scratch (decision 186) ----


def test_a_reading_child_keeps_every_temporary_file_in_its_own_folder_in_the_data_home(in_a_child):
    from tests import child_readers
    from tracker.settings import inside, scratch_root

    child = reader_child.ReadingChild(processor_only=True)
    try:
        own = scratch_root() / str(child.pid)
        outcome = child.run(child_readers.where_temporary_files_go, (), {}, 60)
        assert outcome.kind == "read", outcome
        *places, pid = outcome.answer
        assert int(pid) == child.pid
        for place in places:
            assert inside(Path(place), own), place
        assert Path(places[-1]).is_file()                          # made, and made there
    finally:
        child.finish()
    assert not own.exists()                                        # gone when the child ends


def test_a_sweep_never_empties_the_folder_of_a_process_that_is_alive(tmp_path, monkeypatch):
    """D-14: a preview's child sweeps while a pass's child is reading. Only
    a folder whose process is known to be gone is removed."""
    import subprocess

    ended = subprocess.Popen([sys.executable, "-c", "pass"])
    ended.wait()
    root = tmp_path / "scratch"
    alive, dead, unknown = (root / str(os.getpid()), root / str(ended.pid), root / "4000000000")
    for folder in (alive, dead, unknown):
        folder.mkdir(parents=True)
        (folder / "a-page.tmp").write_bytes(b"a page")
    real = locking.pid_alive
    monkeypatch.setattr(reader_child, "pid_alive", lambda pid: None if pid == "4000000000" else real(pid))

    assert reader_child.sweep_scratch(root) == [dead]
    assert alive.is_dir() and unknown.is_dir() and not dead.exists()


def test_a_folder_the_tracker_did_not_name_is_never_swept(tmp_path):
    root = tmp_path / "scratch"
    for name in ("notes", "123abc"):
        (root / name).mkdir(parents=True)
    (root / "42").write_bytes(b"a file, not a folder")
    assert reader_child.sweep_scratch(root) == []
    assert {path.name for path in root.iterdir()} == {"notes", "123abc", "42"}
    assert reader_child.sweep_scratch(tmp_path / "nothing-here") == []


def test_a_child_that_is_killed_leaves_its_folder_for_the_next_childs_sweep(in_a_child):
    from tests import child_readers
    from tracker.settings import scratch_root

    first = reader_child.ReadingChild(processor_only=True)
    try:
        assert first.run(child_readers.where_temporary_files_go, (), {}, 60).kind == "read"
        folder = scratch_root() / str(first.pid)
        assert folder.is_dir()
        reader_child._end(first._process)                                   # killed: nothing of the pass removes it
        assert folder.is_dir()
    finally:
        first._done = True                                         # the pass never got to end it
        for end in (first._jobs, first._answers, first._held):
            end.close()
        reader_child._close_job(first._job_object)
    second = reader_child.ReadingChild(processor_only=True)
    try:
        assert second.run(child_readers.where_temporary_files_go, (), {}, 60).kind == "read"
        assert not folder.exists()                                 # swept by the next child
        assert (scratch_root() / str(second.pid)).is_dir()
    finally:
        second.finish()


def test_no_reading_child_starts_without_a_data_home(tmp_path, in_a_child, monkeypatch):
    """A relative data home is refused before any process starts: the
    reading is the machine's "not started", the file waits, and nothing is
    made in the temp folder or the checkout instead."""
    from tests import child_readers
    from tracker.settings import ENV_DATA_HOME, app_dir

    monkeypatch.setenv(ENV_DATA_HOME, "data")
    monkeypatch.chdir(tmp_path)
    session = reader_child.Session(in_a_child=True)
    try:
        outcome = session.run(child_readers.where_temporary_files_go, (), {}, 30)
    finally:
        session.close()
    assert outcome.kind == "not_started" and "must name a whole path" in outcome.error
    assert session.child is None                                    # no process was ever started
    for fallback in (Path(tempfile.gettempdir()), app_dir(), tmp_path):
        assert not (fallback / "data").exists(), fallback           # nothing made instead
        assert not any(fallback.glob("reading-*")), fallback
