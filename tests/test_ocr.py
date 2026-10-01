"""Tests for tracker/ocr.py - the reader (decision 169) and the pass's one
reading child.

Two kinds of claim. The reading claims run the **real** engine on the
processor - RapidOCR and its shipped models - over pages drawn here with
Pillow: no binary is committed and no client's document is near the suite.
The graphics card claims cannot run on the real card (CI has none), so the
card's engine is a fake that says which providers its sessions got and
fails the way a card that has faulted fails; everything around it - the
pack, the self-test, the switch to the processor, the run log and the
pass's warning - is the real code.

The child claims run a real child process, as the pass makes it, with the
stand-in readers of tests/child_readers.py and the stops patched down to
seconds.
"""

from __future__ import annotations

import datetime as dt
import os
import socket
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.conftest import make_engagement, named_page
from tests.samples import scanned_pdf
from tests.test_content_check import (
    CRASHED,
    STOP_IN_TESTS,
    STOPPED,
    eventually,
    no_child_left,
    running,
    text_pdf,
)
from tracker import content_check, ocr, reasons
from tracker.content_check import check_content, contains_keyword, extract
from tracker.manifest import RequestItem

W2_WORDS = ["Form W-2 Wage and Tax Statement 2025",
            "b Employer identification number (EIN)",
            "1 Wages, tips, other compensation"]


def w2_scan(path: Path) -> Path:
    """A one-page scanned W-2: no text layer, only pixels."""
    return scanned_pdf(path, W2_WORDS)


def w2_photo(path: Path, *, turn: int = 0) -> Path:
    """A photo of a W-2's head, turned ``turn`` degrees in its pixels."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1100, 260), "white")
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(W2_WORDS):
        draw.text((30, 30 + 70 * i), line, font=ImageFont.load_default(size=40), fill="black")
    if turn:
        image = image.rotate(turn, expand=True, fillcolor="white")
    image.save(path)
    return path


# ------------------------------------------------------ the real reader ----


def test_a_scan_is_read_by_rapidocr(tmp_path):
    """A PDF with no text layer is read by the reader shipped in the app,
    on the processor, and the reading is OCR's (``from_ocr``: decision 50's
    stricter rule still applies to it)."""
    scan = w2_scan(tmp_path / "scan.pdf")

    assert extract(scan, ocr=False).needs_ocr                     # no words without the reader
    reading = extract(scan)
    assert reading.from_ocr and not reading.transient, reading.reason
    assert contains_keyword(reading.text, "wage and tax statement")
    assert contains_keyword(reading.text, "employer identification number")
    rules = RequestItem(identifier="A01", document="W-2", required_keywords=("W-2", "wage and tax statement"))
    assert check_content(scan, rules).ok


def test_a_photo_is_read_by_rapidocr(tmp_path):
    """A photo takes the scan's path: read by the same reader, from_ocr."""
    for name in ("w-2.png", "w-2.jpg"):
        reading = extract(w2_photo(tmp_path / name))
        assert reading.from_ocr, (name, reading.reason)
        assert contains_keyword(reading.text, "wage and tax statement"), name


def test_a_sideways_page_keeps_its_words(tmp_path, monkeypatch):
    """Ruling 6 as re-ruled: RapidOCR turns tall crops and flips upside-down
    ones itself, so a page photographed a quarter turn or a half turn round
    keeps the words its keywords are found in. Nothing turns the page: the
    engine is handed the pixels as they stand. (What such a page loses is
    the order of its lines - the gap the amendment "169, upright" closes.)"""
    from PIL import Image

    handed = []
    real = ocr._pixels
    monkeypatch.setattr(ocr, "_pixels", lambda image: handed.append(image.size) or real(image))
    for turn in (90, 180):
        picture = w2_photo(tmp_path / f"turned {turn}.png", turn=turn)
        reading = extract(picture)
        assert reading.from_ocr, (turn, reading.reason)
        assert contains_keyword(reading.text, "wage and tax statement"), (turn, reading.text)
        assert contains_keyword(reading.text, "W-2"), (turn, reading.text)
        assert handed[-1] == Image.open(picture).size             # not turned
    assert handed[0][1] > handed[0][0]                              # the quarter turn stayed tall


def test_a_full_read_opens_no_socket_writes_no_temporary_file_and_fetches_nothing(tmp_path, monkeypatch):
    """Decision 169, rulings 1 and 8. RapidOCR imports ``requests`` for a
    model downloader; the reader names every model by path and replaces the
    downloader with a refusal, so a whole reading - the engine built from
    nothing, a page read - opens no socket. And it writes no temporary file,
    which is why decision 137's scratch folder for OCR is gone."""
    import rapidocr.utils.download_file as download_file

    monkeypatch.setattr(ocr, "_ENGINE", None)                      # the engine's build is in the claim
    monkeypatch.setattr(ocr, "_DEVICE", "")
    monkeypatch.setattr(download_file.DownloadFile, "run", download_file.DownloadFile.run)
    scan = w2_scan(tmp_path / "scan.pdf")
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temporary))
    for name in ("TMP", "TEMP", "TMPDIR"):
        monkeypatch.setenv(name, str(temporary))

    class NoSocket(socket.socket):
        def __init__(self, *args, **kwargs):
            raise AssertionError("the reader opened a socket")

    monkeypatch.setattr(socket, "socket", NoSocket)
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: pytest.fail("the reader opened a connection"))
    reading = extract(scan)

    assert reading.from_ocr and contains_keyword(reading.text, "wage and tax statement")
    assert list(temporary.iterdir()) == []
    with pytest.raises(ocr.ReaderUnavailable, match="nothing is fetched"):
        download_file.DownloadFile.run(SimpleNamespace(file_url="https://example.invalid/model.onnx"))


def test_a_missing_model_means_the_reader_cannot_run_and_the_scan_waits(tmp_path, monkeypatch):
    """Ruling 9: the reader ships inside the app, so "cannot run" is a
    model missing or broken - the machine's fault, transient, never kept,
    and never a download. The sentence is reader-neutral."""
    monkeypatch.setattr(ocr, "_ENGINE", None)
    monkeypatch.setattr(ocr, "models_folder", lambda: tmp_path / "no models here")
    scan = w2_scan(tmp_path / "scan.pdf")

    reading = extract(scan)
    assert reading.text is None and reading.transient
    assert reading.code == reasons.NO_TEXT_LAYER.code
    assert "the reader could not run on this machine" in reading.reason
    assert "OCR is not installed" not in reading.reason


def test_the_lines_are_built_from_the_boxes_in_reading_order():
    """The seam of ruling 6 builds lines only: boxes on one line (centres
    within half a typical height) join left to right, lines run top to
    bottom, and nothing is turned or dropped but blank text."""
    def box(left, top, right, bottom):
        return [(left, top), (right, top), (right, bottom), (left, bottom)]

    result = SimpleNamespace(
        boxes=[box(300, 100, 400, 120), box(10, 10, 100, 30), box(110, 12, 200, 32),
               box(10, 102, 90, 121), box(10, 200, 50, 220)],
        txts=("second-right", "first-left", "first-right", "second-left", "  "))
    assert ocr._upright_lines(result) == ["first-left first-right", "second-left second-right"]
    assert ocr._upright_lines(SimpleNamespace(boxes=None, txts=None)) == []


# ----------------------------------------------------- the graphics card ----


class FakeEngine:
    """An engine whose sessions say which provider they got, reading every
    page as ``lines``; from its ``fail_from``-th call it raises what a
    faulted card raises, for ever (the card poisons the engine)."""

    def __init__(self, provider: str, lines: list[str], *, fail_from: int = 0):
        self.calls = 0
        self.lines = lines
        self.fail_from = fail_from
        self.providers = {part: [provider, "CPUExecutionProvider"] for part in ocr.SESSIONS}
        for part in ocr.SESSIONS:
            session = SimpleNamespace(get_providers=lambda part=part: self.providers[part])
            setattr(self, part, SimpleNamespace(session=SimpleNamespace(session=session)))

    def __call__(self, pixels):
        self.calls += 1
        if self.fail_from and self.calls >= self.fail_from:
            raise RuntimeError("[ONNXRuntimeError] : 1 : FAIL : CUDA failure 999: unknown error ; GPU=0")
        boxes = [[(0, 40 * i), (500, 40 * i), (500, 40 * i + 30), (0, 40 * i + 30)]
                 for i in range(len(self.lines))]
        return SimpleNamespace(boxes=boxes, txts=tuple(self.lines))


PAGE_WORDS = named_page("Form W-2 Wage and Tax Statement 2025").splitlines()


@pytest.fixture
def a_card(monkeypatch, tmp_path):
    """A machine with a graphics card pack beside the app, a card engine
    and a processor engine that are fakes, and a record of what was built
    and what was loaded. ``card.gpu`` is set by each test before the pass."""
    import onnxruntime

    pack = tmp_path / ocr.GPU_PACK_DIR_NAME
    pack.mkdir()
    card = SimpleNamespace(pack=pack, built=[], loaded=[], gpu=None, cpu=FakeEngine("CPUExecutionProvider", PAGE_WORDS))

    def build(*, cuda):
        card.built.append("card" if cuda else "processor")
        return card.gpu if cuda else card.cpu

    monkeypatch.setattr(ocr, "_ENGINE", None)
    monkeypatch.setattr(ocr, "_DEVICE", "")
    monkeypatch.setattr(ocr, "_PROCESSOR_ONLY", False)
    monkeypatch.setattr(ocr, "_NOTES", [])
    monkeypatch.setattr(ocr, "_build_engine", build)
    monkeypatch.setattr(ocr, "gpu_pack", lambda: card.pack)
    monkeypatch.setattr(onnxruntime, "preload_dlls",
                        lambda **kwargs: card.loaded.append(kwargs.get("directory")))
    return card


def w2_rows():
    return [RequestItem(identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
                        min_size_kb=0, required_keywords=("W-2",), expected_count=5)]


def scans_in_the_inbox(engagement, names_and_pages: dict[str, int]):
    """Scanned PDFs of ``pages`` pages each, dropped in the inbox."""
    from PIL import Image

    from tracker.layout import inbox_of

    for name, pages in names_and_pages.items():
        sheets = [Image.new("RGB", (400, 500 + 10 * i + len(name)), "white") for i in range(pages)]
        sheets[0].save(inbox_of(engagement) / name, "PDF", save_all=True, append_images=sheets[1:])


def a_pass(root: Path, day: int = 1):
    from tracker.registry import discover_engagements
    from tracker.runner import REMINDERS_NEVER, run_registry

    return run_registry(discover_engagements(root), today=dt.date(2026, 7, day), reminders=REMINDERS_NEVER)


def test_no_gpu_pack_means_the_cpu_without_a_word(tmp_path, monkeypatch, a_card):
    """R-2: with no ``gpu-runtime`` folder the reader never asks for the
    card - no library loaded, no CUDA engine requested, so no error lines -
    and says nothing but "processor" in the run log's first line."""
    from tracker.runner import append_log

    monkeypatch.setattr(ocr, "gpu_pack", lambda: None)
    engagement = make_engagement(tmp_path / "root", w2_rows())
    scans_in_the_inbox(engagement, {"one.pdf": 1})

    report = a_pass(tmp_path / "root")

    assert a_card.built == ["processor"] and a_card.loaded == []
    assert report.reader == ocr.DEVICE_PROCESSOR and report.reader_note == ""
    assert report.warnings == []
    first, *rest = append_log(tmp_path / "runs.log", report).read_text(encoding="utf-8").splitlines()
    assert first.endswith("reader=processor")
    assert not any("graphics card" in line for line in rest)


def test_a_pack_is_used_only_when_every_session_is_on_cuda_and_the_self_test_reads(tmp_path, a_card):
    """R-2: with the pack, its libraries are loaded, the engine is built
    asking for CUDA, each of the three sessions must have got
    ``CUDAExecutionProvider`` first, and the one-page self-test must read.
    Then the run log says "graphics card"; anything less is the processor
    and one run-log line saying why - never a pass warning."""
    from tracker.runner import append_log

    engagement = make_engagement(tmp_path / "root", w2_rows())
    scans_in_the_inbox(engagement, {"one.pdf": 1})

    a_card.gpu = FakeEngine(ocr.CUDA_PROVIDER, PAGE_WORDS)
    report = a_pass(tmp_path / "root")
    assert a_card.loaded == [str(a_card.pack)]
    assert a_card.built == ["card"] and a_card.gpu.calls >= 2      # the self-test, and the scan
    assert report.reader == ocr.DEVICE_GRAPHICS_CARD and report.reader_note == ""
    assert append_log(tmp_path / "card.log", report).read_text(encoding="utf-8").splitlines()[0] \
        .endswith("reader=graphics card")

    # One session quietly on the processor: not the card.
    a_card.built.clear()
    a_card.gpu = FakeEngine(ocr.CUDA_PROVIDER, PAGE_WORDS)
    a_card.gpu.providers["text_rec"] = ["CPUExecutionProvider"]
    scans_in_the_inbox(engagement, {"two.pdf": 1})
    report = a_pass(tmp_path / "root", day=2)
    assert a_card.built == ["card", "processor"]
    assert report.reader == ocr.DEVICE_PROCESSOR and report.warnings == []
    said = ocr.PACK_UNUSABLE.format(reason="the text_rec session got CPUExecutionProvider")
    assert report.reader_note == said
    lines = append_log(tmp_path / "rec.log", report).read_text(encoding="utf-8").splitlines()
    assert lines[0].endswith("reader=processor") and lines[1].strip() == said

    # Every session on CUDA, and the self-test reads nonsense.
    a_card.built.clear()
    a_card.gpu = FakeEngine(ocr.CUDA_PROVIDER, ["nonsense"])
    scans_in_the_inbox(engagement, {"three.pdf": 1})
    report = a_pass(tmp_path / "root", day=3)
    assert a_card.built == ["card", "processor"]
    assert report.reader == ocr.DEVICE_PROCESSOR and report.warnings == []
    assert report.reader_note == ocr.PACK_UNUSABLE.format(reason="the self-test read 'nonsense'")


def test_a_gpu_fault_switches_the_rest_of_the_pass_to_the_cpu(tmp_path, a_card):
    """Ruling 3. The card faults on the second page of the first scan
    (ONNX Runtime's "CUDA failure 999", after which every later call in the
    process fails). That page is read again on the processor, the rest of
    the scan and the next scan are read on the processor from the start,
    the pass says so once, and no reading failed. The next pass tries the
    card again."""
    from tracker.filer import read_index
    from tracker.runner import append_log

    engagement = make_engagement(tmp_path / "root", w2_rows())
    scans_in_the_inbox(engagement, {"one.pdf": 3, "two.pdf": 1})
    # Call 1 is the self-test, call 2 the first page, call 3 the second.
    a_card.gpu = FakeEngine(ocr.CUDA_PROVIDER, PAGE_WORDS, fail_from=3)

    report = a_pass(tmp_path / "root")

    assert a_card.gpu.calls == 3                                   # never asked again after the fault
    assert a_card.built == ["card", "processor"]
    assert a_card.cpu.calls == 3                                   # page 2 again, page 3, the next scan
    assert report.reader == ocr.DEVICE_GRAPHICS_CARD                 # it began on the card
    assert report.warnings == [ocr.GPU_FAULT_WARNING.format(file="one.pdf")]
    log = append_log(tmp_path / "runs.log", report).read_text(encoding="utf-8")
    # Counted by its code, the file never named (decision 186).
    assert "one.pdf" not in log and "graphics-card-fault=1" in log
    rows = read_index(engagement)
    assert sorted(row.original_name for row in rows) == ["one.pdf", "two.pdf"]
    assert all(row.identifier == "A01" for row in rows), [row.reason for row in rows]

    # The next pass: the card again.
    a_card.built.clear()
    a_card.gpu = FakeEngine(ocr.CUDA_PROVIDER, PAGE_WORDS)
    scans_in_the_inbox(engagement, {"three.pdf": 1})
    report = a_pass(tmp_path / "root", day=2)
    assert a_card.built == ["card"] and report.warnings == []


# ----------------------------------------------- one child for the pass ----


@pytest.fixture
def in_a_child(monkeypatch):
    """The reading in a real child process, as the pass makes it."""
    monkeypatch.setattr(content_check, "READ_IN_A_CHILD", True)
    return monkeypatch


@pytest.fixture
def a_short_stop(in_a_child):
    in_a_child.setattr(content_check, "READING_STOP_DOCUMENT_SECONDS", STOP_IN_TESTS)
    in_a_child.setattr(content_check, "READING_STOP_PAGE_SECONDS", STOP_IN_TESTS)
    return in_a_child


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
    pages = [text_pdf(tmp_path / f"page {n}.pdf", "Form W-2 2025") for n in range(3)]
    with ocr.reading_session():
        pids = [pid_of_the_reader(page) for page in pages]
        assert len(set(pids)) == 1 and running(pids[0])
    assert eventually(lambda: not running(pids[0]))
    assert no_child_left()

    alone = pid_of_the_reader(pages[0])
    assert alone != pids[0] and no_child_left()


def test_a_long_lived_reader_is_replaced_every_hundred_documents(tmp_path, in_a_child):
    """R-4's hygiene: a child that has served its count is let go and the
    next document gets a fresh one. (The count is patched down from 100.)"""
    in_a_child.setattr(ocr, "DOCUMENTS_PER_CHILD", 2)
    pages = [text_pdf(tmp_path / f"page {n}.pdf", "Form W-2 2025") for n in range(3)]
    with ocr.reading_session():
        first, second, third = (pid_of_the_reader(page) for page in pages)
    assert first == second != third
    assert no_child_left()


def test_a_long_lived_reader_is_replaced_after_a_stop(tmp_path, a_short_stop):
    """150's first guarantee, for the one child: the document's stop ends
    it - and everything it started - the document is abandoned, and the
    next document gets a fresh child that reads it."""
    from tests import child_readers

    stuck = text_pdf(tmp_path / "stuck.pdf", "Form W-2 2025")
    after = text_pdf(tmp_path / "after.pdf", "Form W-2 2025")
    with ocr.reading_session():
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

    crash = text_pdf(tmp_path / "a crash.pdf", "Form W-2 Wage and Tax Statement 2025")
    after = text_pdf(tmp_path / "after.pdf", "Form W-2 Wage and Tax Statement 2025")
    with ocr.reading_session():
        before = pid_of_the_reader(after)
        answer, failed = content_check.in_a_child(crash, child_readers.a_reader_that_dies_on_a_crash)
        assert answer is None and failed.reason == CRASHED and not failed.transient
        reading = content_check.extract_bounded(after)
        assert reading.text and "W-2" in reading.text
        assert pid_of_the_reader(after) != before
    assert no_child_left()


def test_the_document_stop_ends_a_page_the_reader_never_finishes(tmp_path, a_short_stop):
    """Ruling 5: RapidOCR takes no timeout, and nothing inside the child can
    interrupt a page it is reading. The document's stop ends the child: the
    reading is abandoned, and nothing is left running."""
    from tests import child_readers

    a_short_stop.setattr(content_check, "_CHILD_READER", child_readers.a_page_read_that_never_finishes)
    scan = w2_scan(tmp_path / "scan.pdf")

    reading = content_check.extract_bounded(scan)

    mark = child_readers.reached(scan, "page")
    assert mark.is_file()                                          # it was inside the page
    assert reading.text is None and reading.reason == STOPPED and not reading.transient
    assert eventually(lambda: not running(int(mark.read_text(encoding="utf-8"))))
    assert no_child_left()


#: A pass, as a process of its own, that opens its reading session, reads
#: one document - so its child is alive and idle, waiting for the next -
#: says the child's process id, and waits to be killed.
A_PASS_BETWEEN_DOCUMENTS = """
import sys, time
from pathlib import Path
sys.path[:0] = [sys.argv[2]]
from tests import child_readers
from tracker import content_check, ocr
with ocr.reading_session():
    answer, failed = content_check.in_a_child(Path(sys.argv[1]), child_readers.the_childs_process_id)
    Path(sys.argv[1] + ".child").write_text(answer.text, encoding="utf-8")
    time.sleep(600)
"""


def test_no_reading_child_outlives_the_pass(tmp_path):
    """150's third guarantee, for the long-lived child: killed the way Task
    Scheduler kills it - outright, no code of the pass's runs - the pass
    takes its child with it, even one idle between documents."""
    import subprocess
    import sys

    repo = str(Path(__file__).resolve().parents[1])
    page = text_pdf(tmp_path / "page.pdf", "Form W-2 2025")
    mark = Path(f"{page}.child")
    the_pass = subprocess.Popen([sys.executable, "-c", A_PASS_BETWEEN_DOCUMENTS, str(page), repo])
    try:
        assert eventually(mark.is_file, within=60), "the pass never read its document"
        child = int(mark.read_text(encoding="utf-8"))
        assert running(child)                                      # alive, between documents

        the_pass.kill()
        the_pass.wait(30)

        assert eventually(lambda: not running(child), within=10), "the child outlived its pass"
    finally:
        if the_pass.poll() is None:
            the_pass.kill()


# -------------------------------- the graphics card, in a real child (S-2) ----
#
# REVIEW-169: every claim above about the card runs in the test's own
# process, where the fakes live. These cross into a real spawned child, so
# the path the pass takes - the child's notes, the pipe, the session's
# hearing, the replacement - is what is proved. The child has no pack (it
# is not the frozen app); the parent is told there is one, which is what
# makes a child "on the card" to the session.


def who_read(session: ocr.Session, path: Path, reader) -> tuple[int, bool]:
    """(the child's process id, whether it was kept on the processor)."""
    outcome = session.run(reader, (path,), {}, STOP_IN_TESTS * 6)
    assert outcome.kind == "read", (outcome.kind, outcome.error)
    pid, processor_only = outcome.answer.text.split()
    return int(pid), processor_only == "True"


@pytest.fixture
def a_pack_here(monkeypatch, tmp_path):
    pack = tmp_path / ocr.GPU_PACK_DIR_NAME
    pack.mkdir()
    monkeypatch.setattr(ocr, "gpu_pack", lambda: pack)
    return pack


def test_a_card_fault_in_a_child_moves_the_rest_of_the_pass_to_the_processor(tmp_path, a_pack_here):
    """Ruling 3, end to end: the child's note of a fault crosses the pipe,
    the session hears it, lets that child go, and the next document is read
    by a new child told to keep to the processor. One warning."""
    from tests import child_readers

    fault, after = tmp_path / "a fault.pdf", tmp_path / "after.pdf"
    with ocr.reading_session() as session:
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
    with ocr.reading_session() as session:
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

    scan = text_pdf(tmp_path / "scan.pdf", "Form W-2 2025")
    after = text_pdf(tmp_path / "after.pdf", "Form W-2 2025")
    with ocr.reading_session() as session:
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
    with ocr.reading_session() as session:
        first, _ = who_read(session, one, child_readers.a_reader_that_dies_once_used)
        second, off_the_card = who_read(session, two, child_readers.a_reader_that_dies_once_used)
        assert second != first and off_the_card is False     # no pack: not the card's
        assert session.warnings() == []
    assert no_child_left()


@pytest.mark.skipif(sys.platform != "win32", reason="the memory cap is the Windows job object's")
def test_the_reading_childs_job_caps_its_memory(a_pack_here):
    """SPEC-169 section 9: 2 GB for a processor child, 6 GB for a child on
    the graphics card, set on the job object that already ends it."""
    for processor_only, cap in ((True, ocr.PROCESSOR_CHILD_MEMORY),
                                (False, ocr.GRAPHICS_CARD_CHILD_MEMORY)):
        child = ocr.ReadingChild(processor_only=processor_only)
        try:
            assert ocr._job_memory(child._job_object)[0] == cap
        finally:
            child.finish()
    assert (ocr.PROCESSOR_CHILD_MEMORY, ocr.GRAPHICS_CARD_CHILD_MEMORY) == (2 * 1024**3, 6 * 1024**3)


@pytest.mark.skipif(sys.platform != "win32", reason="the memory cap is the Windows job object's")
def test_a_child_over_its_memory_limit_is_replaced_and_the_next_document_reads(tmp_path):
    """SPEC-169 section 9: a document that wants more than the child's 2 GB
    fails in that child, which says so and ends; the document gets the
    crash's "could not be read", kept for a person, and the next document
    is read by a fresh child."""
    from tests import child_readers

    big = text_pdf(tmp_path / "big.pdf", "Form W-2 2025")
    after = text_pdf(tmp_path / "after.pdf", "Form W-2 2025")
    with ocr.reading_session() as session:
        answer, failed = content_check.in_a_child(big, child_readers.a_reader_that_needs_too_much_memory)
        assert answer is None and failed.reason == CRASHED and not failed.transient
        assert failed.error.startswith("MemoryError")
        assert session.child is None                      # let go, not asked again
        pid, _ = who_read(session, after, child_readers.a_reader_that_needs_too_much_memory)
        assert running(pid)
    assert no_child_left()


def test_a_reader_that_cannot_run_is_not_blamed_on_the_card(monkeypatch, a_card):
    """N-1: with a pack here and not even the processor's engine buildable
    (a model missing), the run log says the reader could not run on this
    machine - not that the card's pack could not be used."""
    def nothing_builds(*, cuda):
        raise ocr.ReaderUnavailable("the model PP-OCRv6_det_small.onnx is missing")

    monkeypatch.setattr(ocr, "_build_engine", nothing_builds)
    session = ocr.Session(in_a_child=False)
    session.settle()
    assert session.note == ocr.READER_CANNOT_RUN.format(
        reason="the model PP-OCRv6_det_small.onnx is missing")
    assert session.device == ocr.DEVICE_PROCESSOR and "graphics card" not in session.note

    in_a_child = ocr.Session()
    monkeypatch.setattr(ocr.Session, "run", lambda *a, **k: ocr.Outcome(
        "failed", error="ReaderUnavailable", message="the model PP-OCRv6_det_small.onnx is missing"))
    in_a_child.settle()
    assert in_a_child.note == session.note


# ------------------------------------------- the short-path warning (§9) ----


def test_run_from_source_the_app_is_never_too_deep():
    assert not getattr(sys, "frozen", False)
    assert ocr.reader_path_warning() == ""


def test_a_library_past_the_limit_means_the_app_must_move(tmp_path, monkeypatch):
    """SPEC-169 section 9 and REVIEW-169 N-5: any library of the app's
    whose full path passes the limit (240, a margin below where loading was
    seen to fail) is the warning. (The limit is patched down to the test's
    own folder.)"""
    app = tmp_path / "tracker-api" / "_internal"
    (app / "cv2").mkdir(parents=True)
    library = app / "cv2" / "opencv_world.dll"
    library.write_bytes(b"")
    (app / "cv2" / "a very long name that is not a library at all.txt").write_bytes(b"")
    monkeypatch.setattr(ocr, "READER_PATH_LIMIT", len(str(library.resolve())))
    assert ocr.reader_path_warning(app) == ""
    monkeypatch.setattr(ocr, "READER_PATH_LIMIT", len(str(library.resolve())) - 1)
    assert ocr.reader_path_warning(app) == ocr.READER_PATH_WARNING
    assert ocr.READER_PATH_WARNING.startswith(
        "Move the app to a shorter folder, for example C:\\JPA App")


@pytest.mark.skipif(sys.platform != "win32", reason="a directory junction is Windows'")
def test_a_short_junction_to_a_deep_folder_is_still_too_deep(tmp_path, monkeypatch):
    """N-5: the frozen app loads from its real folder, so a short junction
    to a deep one does not help, and the check reads the real path."""
    import subprocess

    deep = tmp_path / "a deep folder a deep folder a deep folder" / "tracker-api" / "_internal"
    deep.mkdir(parents=True)
    (deep / "onnxruntime.dll").write_bytes(b"")
    short = tmp_path / "s"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(short), str(deep)], check=True,
                   capture_output=True)
    try:
        monkeypatch.setattr(ocr, "READER_PATH_LIMIT", len(str(short / "onnxruntime.dll")) + 5)
        assert ocr.reader_path_warning(short) == ocr.READER_PATH_WARNING
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(short)], check=True, capture_output=True)


# ------------------------------------------------ the awake clock (189) ----


def test_time_asleep_does_not_count_toward_the_reading_stop(monkeypatch):
    """SPEC-161 A-F9: the machine sleeps mid-reading. The biased clock (the
    wall, and ``time.monotonic`` on Windows) jumps past the stop; the awake
    clock moves one second. The reading is not ended, and its answer is
    taken when the machine wakes."""
    import time

    awake = [1000.0]
    biased = [5000.0]
    monkeypatch.setattr(ocr, "awake_clock", lambda: awake[0])
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
    child = object.__new__(ocr.ReadingChild)
    child._jobs = SimpleNamespace(send=lambda job: None)
    child._answers = Answers()
    child.served = 0
    monkeypatch.setattr(child.__class__, "end", lambda self: ended.append(True))

    outcome = child.run(len, ("x",), {}, stop)

    assert not ended, "a stop the machine slept through must not end the reading"
    assert outcome.kind == "read" and outcome.answer == "the words"
    assert outcome.seconds == pytest.approx(1.0)


def test_the_readings_own_stop_reads_the_awake_clock():
    assert content_check._clock is ocr.awake_clock
    assert ocr.awake_clock() <= ocr.awake_clock()


# --------------------------------------- the reading child's scratch (decision 186) ----


def test_a_reading_child_keeps_every_temporary_file_in_its_own_folder_in_the_data_home(in_a_child):
    from tests import child_readers
    from tracker.settings import _inside, scratch_root

    child = ocr.ReadingChild(processor_only=True)
    try:
        own = scratch_root() / str(child.pid)
        outcome = child.run(child_readers.where_temporary_files_go, (), {}, 60)
        assert outcome.kind == "read", outcome
        *places, pid = outcome.answer
        assert int(pid) == child.pid
        for place in places:
            assert _inside(Path(place), own), place
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
    real = ocr.pid_alive
    monkeypatch.setattr(ocr, "pid_alive", lambda pid: None if pid == "4000000000" else real(pid))

    assert ocr.sweep_scratch(root) == [dead]
    assert alive.is_dir() and unknown.is_dir() and not dead.exists()


def test_a_folder_the_tracker_did_not_name_is_never_swept(tmp_path):
    root = tmp_path / "scratch"
    for name in ("notes", "123abc"):
        (root / name).mkdir(parents=True)
    (root / "42").write_bytes(b"a file, not a folder")
    assert ocr.sweep_scratch(root) == []
    assert {path.name for path in root.iterdir()} == {"notes", "123abc", "42"}
    assert ocr.sweep_scratch(tmp_path / "nothing-here") == []


def test_a_child_that_is_killed_leaves_its_folder_for_the_next_childs_sweep(in_a_child):
    from tests import child_readers
    from tracker.settings import scratch_root

    first = ocr.ReadingChild(processor_only=True)
    try:
        assert first.run(child_readers.where_temporary_files_go, (), {}, 60).kind == "read"
        folder = scratch_root() / str(first.pid)
        assert folder.is_dir()
        ocr._end(first._process)                                   # killed: nothing of the pass removes it
        assert folder.is_dir()
    finally:
        first._done = True                                         # the pass never got to end it
        for end in (first._jobs, first._answers, first._held):
            end.close()
        ocr._close_job(first._job_object)
    second = ocr.ReadingChild(processor_only=True)
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
    session = ocr.Session(in_a_child=True)
    try:
        outcome = session.run(child_readers.where_temporary_files_go, (), {}, 30)
    finally:
        session.close()
    assert outcome.kind == "not_started" and "must name a whole path" in outcome.error
    assert session.child is None                                    # no process was ever started
    for fallback in (Path(tempfile.gettempdir()), app_dir(), tmp_path):
        assert not (fallback / "data").exists(), fallback           # nothing made instead
        assert not any(fallback.glob("reading-*")), fallback
