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
import socket
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
    assert reasons.NO_TEXT_LAYER.matches(reading.reason)
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
    assert log.count("the graphics card failed while reading one.pdf") == 1
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
