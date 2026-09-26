"""The reader (decision 169): RapidOCR, on the graphics card when it works
and on the processor when it does not, and the one child process the pass
reads in.

**What reads.** RapidOCR - PaddleOCR's detection, direction and recognition
models in ONNX form, run by ONNX Runtime - with the three models shipped
inside the app (``rapidocr``'s own package folder, collected as data by
``api_entry.spec``). Nothing is downloaded, ever: every model is named by
path, and rapidocr's own downloader is replaced by a refusal before any
engine is built (:func:`_refuse_downloads`), so a missing or broken model is
"the reader could not run on this machine" (``reasons.NO_TEXT_LAYER``,
transient) and never a request to the network. Tesseract, which read
before this decision, is gone from the product.

**Which device.** The app ships ``onnxruntime-gpu`` and not the NVIDIA
libraries it needs (about 1.6 GB). Those are the *graphics card pack*: a
folder, :data:`GPU_PACK_DIR_NAME`, beside ``tracker-api.exe``, copied only
onto a machine with a supported NVIDIA card (:func:`gpu_pack`).

- No pack: the reader never asks for the graphics card. It builds the
  processor's engine, says nothing, and the run log says "processor".
- A pack: its libraries are loaded (``onnxruntime.preload_dlls``), the
  engine is built asking for CUDA, each of its three sessions must really
  have got ``CUDAExecutionProvider`` first, and a one-page self-test must
  read (:func:`_self_test`), which also takes the first page's warm-up.
  Any failure there builds the processor's engine instead and leaves one
  run-log line (:data:`PACK_UNUSABLE`), not a pass warning. "Offered" is
  never the test: ``onnxruntime-gpu`` offers CUDA on every machine, with
  or without the libraries (Step 0, SPEC-169 section 6).

**A fault on the graphics card** (ruling 3). ONNX Runtime on a card that
has faulted once fails every later page in the same process ("CUDA failure
999", seen on the office machine during the benchmark). So any exception
from the graphics card's engine is a fault: the engine is discarded, the
processor's engine is built, and the same page is read again on it. The
pass then reads on the processor for the rest of the pass (every later
child included) and says so once (:data:`GPU_FAULT_WARNING`); the next pass
tries the card again. A reading is never failed by a fault alone.

**Lines, not a turn** (ruling 6 as re-ruled). RapidOCR turns tall crops and
flips upside-down crops itself, and reads nearly every word of a rotated
page; what a rotated page loses is the order of its lines. The one seam,
:func:`_upright_lines`, builds lines in reading order from the boxes as they
come. It never turns a page and never costs a second reading; the turning
rule arrives later as the amendment "169, upright", in the seam only.

**The reading's child** (decision 150, decision 169 R-4). The pass reads in
a child process it can stop - the safety stop bounds the whole reading,
and a reader that crashes parks the file rather than ending the pass. Since
this decision there is **one** child per pass (:class:`ReadingChild`),
serving documents one at a time: a fresh child per document would pay the
engine's load (about a second on either device) every time. It is replaced
after a stop, a crash, a fault on the graphics card, and every
:data:`DOCUMENTS_PER_CHILD` documents. What made decision 150's promises
still holds, for this child:

- the document's stop ends the child, and the next document gets a fresh
  one;
- a crash parks only the document being read - and only a crash on a
  fresh processor child is the file's own. A child on the graphics card
  that ends without an answer is a fault on the card (the pass moves to
  the processor), and a child that had already served a document may
  have died of what the earlier ones left behind; either way the document
  is read once more on a fresh child before it is blamed;
- it never outlives the pass. It watches a lifeline pipe the pass never
  writes to, and on Windows it sits in a job object that kills everything
  in it when the pass's only handle closes. The same job caps its memory
  (:data:`PROCESSOR_CHILD_MEMORY`, :data:`GRAPHICS_CARD_CHILD_MEMORY`): a
  child past it fails its reading, ends and is replaced, as a crash.

**Nothing a reading does may outlive it in the child.** The child serves
many documents, so a reader must never change module state (a global, a
patched function) for one document and leave it for the next.

The pass opens its child with :func:`reading_session` (the runner for a
pass, the app for one command); a reading made with none open gets a
session of its own for that one reading. The pass and the child talk over
``multiprocessing``'s ``Pipe`` - a named pipe on Windows - never a socket.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from tracker import errors

log = logging.getLogger(__name__)

# ----------------------------------------------------------------- devices ----

#: What the run log calls the two devices (its first line, ``reader=``).
DEVICE_PROCESSOR = "processor"
DEVICE_GRAPHICS_CARD = "graphics card"
#: The folder beside ``tracker-api.exe`` holding the graphics card's
#: libraries (CUDA 13 and cuDNN 9, made from the pinned NVIDIA wheels in
#: ``requirements-gpu.txt``). Copied only onto a machine with an NVIDIA card.
GPU_PACK_DIR_NAME = "gpu-runtime"
#: The run-log line when the pack is there and the card could not be used.
PACK_UNUSABLE = ("the graphics card pack is here but could not be used: {reason}; "
                 "reading on the processor")
#: The pass's one warning after a fault on the graphics card (ruling 3).
GPU_FAULT_WARNING = ("the graphics card failed while reading {file}; "
                     "the rest of this pass read on the processor")
#: The run-log line when not even the processor's engine can be built.
READER_CANNOT_RUN = "the reader could not run on this machine: {reason}"

#: The three models, shipped in ``rapidocr``'s own package folder.
MODEL_DIR_NAME = "models"
DETECTION_MODEL = "PP-OCRv6_det_small.onnx"
RECOGNITION_MODEL = "PP-OCRv6_rec_small.onnx"
DIRECTION_MODEL = "ch_ppocr_mobile_v2.0_cls_mobile.onnx"
#: The engine's sessions, by rapidocr's own attribute names: detection,
#: direction ("cls") and recognition. Each must be on CUDA for the card.
SESSIONS = ("text_det", "text_cls", "text_rec")
CUDA_PROVIDER = "CUDAExecutionProvider"

#: The self-test page: a line of a form's own words, drawn here.
SELF_TEST_TEXT = "Wage and Tax Statement 2025"
SELF_TEST_WORDS = ("wage", "statement")


class ReaderUnavailable(Exception):
    """The reader cannot run on this machine: a package or a model file is
    missing or broken. The machine's fault, never the file's."""


#: The longest full path a library inside the frozen app may have. Loading
#: failed from 252-255 characters on the office machine (REVIEW-169, N-5),
#: below Windows' 260, so this leaves a margin.
READER_PATH_LIMIT = 240
#: What the app and the pass say when the app sits too deep to read.
READER_PATH_WARNING = ("Move the app to a shorter folder, for example C:\\JPA Tracker; "
                       "scans can't be read from here")


def reader_path_warning(root: Path | None = None) -> str:
    """:data:`READER_PATH_WARNING` when the frozen app sits in a folder so
    deep that the reader's libraries cannot load, else "".

    It walks the app's own folder (``sys._MEIPASS``), **resolved** first -
    a short junction to a deep folder does not help, because the app loads
    from its real folder - and warns when any ``.dll`` or ``.pyd`` there has
    a full path longer than :data:`READER_PATH_LIMIT`, or a folder cannot
    even be listed. Run from source (no ``root`` given) it never warns."""
    if root is None:
        if not getattr(sys, "frozen", False):
            return ""
        root = Path(getattr(sys, "_MEIPASS", "") or Path(sys.executable).parent)
    root = Path(root).resolve()
    unlisted: list[OSError] = []
    for folder, _dirs, files in os.walk(root, onerror=unlisted.append):
        for name in files:
            if (name.lower().endswith((".dll", ".pyd"))
                    and len(os.path.join(folder, name)) > READER_PATH_LIMIT):
                return READER_PATH_WARNING
    return READER_PATH_WARNING if unlisted else ""


def gpu_pack() -> Path | None:
    """The graphics card pack beside the frozen app, or None when there is
    none. Run from source there is never one: the pack is the frozen app's."""
    if not getattr(sys, "frozen", False):
        return None
    folder = Path(sys.executable).resolve().parent / GPU_PACK_DIR_NAME
    return folder if folder.is_dir() else None


def models_folder() -> Path:
    """Where the three models are: inside the ``rapidocr`` package."""
    import rapidocr

    return Path(rapidocr.__file__).resolve().parent / MODEL_DIR_NAME


def _refuse_downloads() -> None:
    """Replace rapidocr's downloader with a refusal. Every model is named by
    path, so it is never reached; this makes "never" a fact rather than a
    reading of rapidocr's code. ``rapidocr`` imports ``requests`` for it at
    load time, which cannot be avoided; the call never happens."""
    from rapidocr.utils import download_file

    def refused(cls, params) -> None:
        raise ReaderUnavailable(f"the reader asked to download {getattr(params, 'file_url', 'a file')}; "
                                "nothing is fetched at run time")

    download_file.DownloadFile.run = classmethod(refused)


def _build_engine(*, cuda: bool):
    """A RapidOCR engine on the models shipped with the app: SPEC-127.2X
    section 13 O1's defaults, and on the card the benchmark harness's
    settings (a heuristic cuDNN search, since page shapes change every
    page, and batches of 32)."""
    try:
        import onnxruntime
        from rapidocr import RapidOCR
    except ImportError as exc:
        raise ReaderUnavailable(f"{errors.error_class(exc)}: {exc}") from exc
    _refuse_downloads()
    onnxruntime.set_default_logger_severity(3)
    folder = models_folder()
    paths = {name: folder / name for name in (DETECTION_MODEL, RECOGNITION_MODEL, DIRECTION_MODEL)}
    for name, path in paths.items():
        if not path.is_file():
            raise ReaderUnavailable(f"the model {name} is missing")
    params = {
        "Global.log_level": "critical",
        "Global.model_root_dir": str(folder),
        "Det.model_path": str(paths[DETECTION_MODEL]),
        "Rec.model_path": str(paths[RECOGNITION_MODEL]),
        "Cls.model_path": str(paths[DIRECTION_MODEL]),
        "EngineConfig.onnxruntime.use_cuda": cuda,
    }
    if cuda:
        params.update({
            "EngineConfig.onnxruntime.cuda_ep_cfg.cudnn_conv_algo_search": "HEURISTIC",
            "Rec.rec_batch_num": 32,
            "Cls.cls_batch_num": 32,
        })
    try:
        return RapidOCR(params=params)
    except ReaderUnavailable:
        raise
    except Exception as exc:
        raise ReaderUnavailable(f"{errors.error_class(exc)}: {exc}") from exc


def _providers(engine) -> dict[str, list[str]]:
    """The execution providers each of the engine's sessions really got."""
    found = {}
    for part in SESSIONS:
        session = getattr(getattr(getattr(engine, part, None), "session", None), "session", None)
        found[part] = list(session.get_providers()) if session is not None else []
    return found


def _self_test_page():
    """A line of a form's own words, drawn in memory."""
    from PIL import Image, ImageDraw, ImageFont

    page = Image.new("RGB", (900, 120), "white")
    ImageDraw.Draw(page).text((20, 30), SELF_TEST_TEXT, font=ImageFont.load_default(size=40),
                              fill="black")
    return page


def _self_test(engine) -> str:
    """"" when ``engine`` reads the self-test page, or what it read instead."""
    said = _text_of(engine(_pixels(_self_test_page()))).lower()
    missing = [word for word in SELF_TEST_WORDS if word not in said]
    return f"the self-test read {said!r}" if missing else ""


def _on_the_card(pack: Path):
    """The graphics card's engine, proved: loaded from ``pack``, every
    session on CUDA, and the self-test read. Raises with the reason."""
    import onnxruntime

    # preload_dlls prints what it could not load; the reason goes in the
    # run log, not on a console nobody reads.
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        onnxruntime.preload_dlls(directory=str(pack))
    try:
        engine = _build_engine(cuda=True)
    except ReaderUnavailable as exc:
        raise RuntimeError(f"{exc} {printed.getvalue().strip()}".strip()) from exc
    for part, providers in _providers(engine).items():
        if not providers or providers[0] != CUDA_PROVIDER:
            got = providers[0] if providers else "nothing"
            loaded = printed.getvalue().strip()
            raise RuntimeError(f"the {part} session got {got}" + (f" ({loaded})" if loaded else ""))
    if failed := _self_test(engine):
        raise RuntimeError(failed)
    return engine


# --------------------------------------------- the engine in this process ----

#: This process's engine and the device it runs on, built on first use.
_ENGINE = None
_DEVICE = ""
#: Set when this process may use the processor only: a child started after
#: a fault on the card, or this process after one.
_PROCESSOR_ONLY = False
#: What this process has to tell its pass, taken with :func:`take_notes`:
#: ("pack-unusable", reason) and ("gpu-fault", file name).
_NOTES: list[tuple[str, str]] = []


def _engine():
    """This process's engine, built on first use (see the module's text for
    which device). Raises :class:`ReaderUnavailable` when none can be built."""
    global _ENGINE, _DEVICE
    if _ENGINE is not None:
        return _ENGINE
    pack = None if _PROCESSOR_ONLY else gpu_pack()
    if pack is not None:
        try:
            _ENGINE, _DEVICE = _on_the_card(pack), DEVICE_GRAPHICS_CARD
            return _ENGINE
        except Exception as exc:
            # The reasons this module words itself are sentences already.
            reason = (str(exc) if isinstance(exc, RuntimeError) and str(exc)
                      else f"{errors.error_class(exc)}: {exc}")
            log.warning(PACK_UNUSABLE.format(reason=reason))
            _NOTES.append(("pack-unusable", reason))
    _ENGINE, _DEVICE = _build_engine(cuda=False), DEVICE_PROCESSOR
    return _ENGINE


def device() -> str:
    """The device this process's engine runs on ("" before it is built)."""
    return _DEVICE


def take_notes() -> list[tuple[str, str]]:
    """What this process has to tell its pass since it was last asked."""
    notes = list(_NOTES)
    _NOTES.clear()
    return notes


def processor_only() -> None:
    """From now on this process reads on the processor (a child started
    after a fault on the card, for the rest of its pass)."""
    global _PROCESSOR_ONLY, _ENGINE, _DEVICE
    _PROCESSOR_ONLY = True
    if _DEVICE == DEVICE_GRAPHICS_CARD:
        _ENGINE, _DEVICE = None, ""


def reset() -> None:
    """A new pass in this process: the card may be tried again. An engine
    built on the processor because of a fault, or while a pack is here, is
    let go, so the next pass settles its device afresh."""
    global _PROCESSOR_ONLY, _ENGINE, _DEVICE
    if _PROCESSOR_ONLY or gpu_pack() is not None:
        _ENGINE, _DEVICE = None, ""
    _PROCESSOR_ONLY = False
    _NOTES.clear()


def warm_up() -> tuple[str, str]:
    """Build this process's engine now: (the device, why the pack could not
    be used or ""). The pass asks its child this at its start when there is
    a pack, so the self-test settles the device before the run log's first
    line is written."""
    _engine()
    unusable = [reason for kind, reason in _NOTES if kind == "pack-unusable"]
    return _DEVICE, unusable[-1] if unusable else ""


def _pixels(image):
    """A PIL image as the engine takes it: BGR, the way OpenCV reads a file."""
    import numpy

    return numpy.asarray(image.convert("RGB"))[:, :, ::-1].copy()


def read_page(image, *, name: str = "") -> str:
    """One page or photo's words, a line per line of print, in reading order.

    ``image`` is a PIL image the right way up as far as the file says (a
    photo's EXIF turn already undone); ``name`` is the document's, for the
    one warning a fault on the card gives. Raises
    :class:`ReaderUnavailable` when no engine can be built on this machine,
    and whatever the processor's engine raised when it fails on the page."""
    global _ENGINE, _DEVICE
    engine = _engine()
    pixels = _pixels(image)
    try:
        return _text_of(engine(pixels))
    except Exception as exc:
        if _DEVICE != DEVICE_GRAPHICS_CARD:
            raise
        # A fault on the card poisons the engine, not the page: every later
        # page in this process would fail the same way. Read this page
        # again on the processor, and stay there for the rest of the pass.
        # Its class only: this runs in the reading child, on a client's page,
        # and the child keeps no words of an error (decision 190).
        log.warning("The graphics card failed while reading %s (%s); reading on the processor",
                    name or "a page", errors.error_class(exc))
        _NOTES.append(("gpu-fault", name or "a page"))
        processor_only()
        del engine
        _ENGINE, _DEVICE = _build_engine(cuda=False), DEVICE_PROCESSOR
        return _text_of(_ENGINE(pixels))


def _text_of(result) -> str:
    """The engine's answer as text: its boxes, in lines (:func:`_upright_lines`)."""
    return "\n".join(_upright_lines(result))


def _upright_lines(page_result) -> list[str]:
    """The page's lines in reading order, built from the engine's boxes.

    The seam of ruling 6: today it only orders what it is given - a box
    joins the line whose centre is within half a typical box height of its
    own, lines run top to bottom and a line's boxes left to right (the
    benchmark harness's ``lines_from_boxes``, which Part 1 measured). It
    never turns a page. The turning rule lands here, and only here, with
    the amendment "169, upright"."""
    boxes = getattr(page_result, "boxes", None)
    texts = getattr(page_result, "txts", None)
    if boxes is None or texts is None:
        return []
    items = []
    for quad, text in zip(boxes, texts, strict=False):
        if not text or not str(text).strip():
            continue
        xs = [float(point[0]) for point in quad]
        ys = [float(point[1]) for point in quad]
        items.append((min(xs), min(ys), max(xs), max(ys), str(text).strip()))
    if not items:
        return []
    heights = sorted(max(1.0, bottom - top) for _left, top, _right, bottom, _text in items)
    typical = heights[len(heights) // 2]
    items.sort(key=lambda box: ((box[1] + box[3]) / 2, box[0]))
    lines: list[list[tuple]] = []
    centres: list[float] = []
    for box in items:
        centre = (box[1] + box[3]) / 2
        if lines and abs(centre - centres[-1]) <= typical * 0.5:
            lines[-1].append(box)
            centres[-1] += (centre - centres[-1]) / len(lines[-1])
        else:
            lines.append([box])
            centres.append(centre)
    return [" ".join(box[4] for box in sorted(line, key=lambda box: box[0])) for line in lines]


# ------------------------------------------------------ the reading's child ----

#: A child serves this many documents and is then replaced (R-4's hygiene).
DOCUMENTS_PER_CHILD = 100
#: The most memory a reading child may commit (SPEC-169 section 9), set on
#: its job object: a processor child, and a child on the graphics card.
#: Past it the child's allocations fail; it ends and is replaced.
PROCESSOR_CHILD_MEMORY = 2 * 1024**3
GRAPHICS_CARD_CHILD_MEMORY = 6 * 1024**3
#: How long the pass gives its child to build the engine and read the
#: self-test at the start of a pass with a graphics card pack.
WARM_UP_STOP_SECONDS = 120.0
#: How long an ended child is waited for, and how long one told to finish
#: is given to exit on its own, before the pass goes on.
CHILD_EXIT_SECONDS = 30.0
#: The exit code of a child that ended itself because its pass was gone.
ORPHANED_EXIT_CODE = 86
#: The exit code of a child handed a job it could not even unpack - a
#: reader whose module it cannot import: the machine's, before "started".
UNREADABLE_JOB_EXIT_CODE = 87
#: The exit code of a child that ran out of memory and ended itself after
#: saying so: its heap is not to be trusted with another document.
OUT_OF_MEMORY_EXIT_CODE = 88


def _awake_clock_source():
    """The clock :func:`awake_clock` reads: on Windows
    ``QueryUnbiasedInterruptTime`` (100 ns units), which stands still while
    the machine sleeps; elsewhere ``time.monotonic``, which on Linux
    already does. A Windows that will not answer the call falls back to
    ``time.monotonic`` rather than to no stop at all."""
    if os.name != "nt":
        return time.monotonic
    try:
        import ctypes

        query = ctypes.WinDLL("kernel32").QueryUnbiasedInterruptTime
        query.argtypes = (ctypes.POINTER(ctypes.c_ulonglong),)
        ticks = ctypes.c_ulonglong()
        if not query(ctypes.byref(ticks)):
            return time.monotonic
    except (OSError, AttributeError):
        return time.monotonic

    def unbiased() -> float:
        query(ctypes.byref(ticks))
        return ticks.value / 10_000_000
    return unbiased


_AWAKE = _awake_clock_source()


def awake_clock() -> float:
    """Seconds on a clock that counts only time the machine is awake
    (decision 189, SPEC-161 A-F9).

    **Every stop that bounds a reading reads this**, and the household's
    time budget with them: :meth:`ReadingChild.run` and
    :meth:`Session._run_once` in the pass, the child's own safety stop
    (``content_check._clock``), and ``runner.HOUSEHOLD_BUDGET_SECONDS``.
    ``time.monotonic`` on Windows counts sleep, so a laptop that slept
    through the night woke to every reading in flight judged past its stop
    and parked as a file that stalled the reader - a verdict about the
    machine's lid, kept as one about the client's file. Task Scheduler's
    own limit stays wall-clock: that is its business.
    """
    return _AWAKE()


@dataclass(slots=True)
class Outcome:
    """What became of one job sent to the child.

    ``kind`` is ``"read"`` (``answer`` is what the job returned),
    ``"failed"`` (the job raised: ``error`` is its class, ``message`` and
    ``trace`` its words, which only the debug log may hold - decision 190), ``"stopped"``
    (ended at the stop), ``"died"`` (ended without an answer after it
    started) or ``"not_started"`` (never started the job: the machine's)."""

    kind: str
    answer: object = None
    error: str = ""
    #: A failed job's own message: never shown, only kept (decision 190).
    message: str = ""
    trace: str = ""
    seconds: float = 0.0
    #: What the reader said with its answer (:func:`take_notes`).
    notes: list = field(default_factory=list)


class ReadingChild:
    """One reading child process and the pass's ends of its three pipes:
    jobs in, answers out, and the lifeline the pass never writes to."""

    def __init__(self, *, processor_only: bool) -> None:
        import multiprocessing

        context = multiprocessing.get_context("spawn")          # Windows has no fork
        self._answers, sender = context.Pipe(duplex=False)
        jobs, self._jobs = context.Pipe(duplex=False)
        lifeline, self._held = context.Pipe(duplex=False)
        self.served = 0
        self._done = False
        #: A child that may build the graphics card's engine (a pack is
        #: here and the card has not failed this pass).
        self.on_the_card = not processor_only and gpu_pack() is not None
        self.memory_limit = GRAPHICS_CARD_CHILD_MEMORY if self.on_the_card else PROCESSOR_CHILD_MEMORY
        self._process = context.Process(
            target=_the_child, args=(jobs, sender, lifeline, processor_only),
            name="tracker-reading", daemon=True)
        try:
            self._process.start()
        except Exception:
            for end in (self._answers, self._jobs, self._held):
                end.close()
            raise
        finally:
            # The child holds its own ends: end-of-file means it is gone.
            for end in (sender, jobs, lifeline):
                end.close()
        self._job_object = _kill_on_close_job(self._process.pid, memory_limit=self.memory_limit)

    @property
    def pid(self) -> int | None:
        return self._process.pid

    def run(self, job, args: tuple, kwargs: dict, stop: float, *, since: float | None = None) -> Outcome:
        """Send ``job(*args, **kwargs)`` and wait for it at most ``stop``
        seconds from ``since`` (by default now). A stop ends the child."""
        started = awake_clock() if since is None else since
        try:
            self._jobs.send((job, args, kwargs))
        except OSError as exc:
            return Outcome("not_started", error=f"the reading's process was gone ({errors.error_class(exc)})",
                           seconds=awake_clock() - started)
        kind, answer, begun, over = "died", (), False, False
        while True:
            # Measured again after every message and every wake, on the
            # awake clock (decision 189): a wait the machine slept through
            # is not the file's time.
            left = started + stop - awake_clock()
            if left <= 0:
                over = True
                self.end()
                break
            if not self._answers.poll(left):
                continue
            try:
                kind, *answer = self._answers.recv()
            except (EOFError, OSError):
                kind, answer = "died", ()
                break
            if kind != "started":
                break
            begun = True            # from here on, what happens is the file's
        seconds = awake_clock() - started
        if not begun:
            exit_code = None if over else self._exit_code()
            error = ("the reader did not start within the safety stop" if over else
                     f"the reading's process ended with exit code {exit_code} before it started")
            if not over:
                self.end()
            return Outcome("not_started", error=error, seconds=seconds)
        if over:
            return Outcome("stopped", seconds=seconds)
        self.served += 1
        if kind == "read":
            return Outcome("read", answer=answer[0], notes=answer[1], seconds=seconds)
        if kind == "failed":
            return Outcome("failed", error=answer[0], message=answer[1], trace=answer[2],
                           notes=answer[3], seconds=seconds)
        error = f"the reading's process ended with exit code {self._exit_code()}"
        if _job_memory(self._job_object)[1] >= self.memory_limit * 0.9:
            error += f"; it had reached its memory limit ({self.memory_limit / 1024**3:.0f} GB)"
        self.end()
        return Outcome("died", error=error, seconds=seconds)

    def _exit_code(self) -> int | None:
        self._process.join(CHILD_EXIT_SECONDS)
        return self._process.exitcode

    def finish(self) -> None:
        """Tell the child it is done and let it exit; end it if it will not."""
        if self._done:
            return
        with contextlib.suppress(OSError, ValueError):
            self._jobs.send(None)
        self._process.join(CHILD_EXIT_SECONDS)
        self.end()

    def end(self) -> None:
        """End the child and everything it started, and close every end.
        Once: a child is ended at a stop and then let go by its session."""
        if self._done:
            return
        self._done = True
        if self._process.is_alive():
            _end(self._process)
        for end in (self._jobs, self._answers, self._held):
            with contextlib.suppress(OSError):
                end.close()
        _close_job(self._job_object)
        self._job_object = None
        if self._process.exitcode is not None:
            with contextlib.suppress(ValueError):
                self._process.close()


def _the_child(jobs, sender, lifeline, processor_only_: bool) -> None:
    """The child's whole life: serve jobs one at a time until the pass says
    it is done, or is gone.

    On POSIX it leads a process group of its own first, so ending it ends
    whatever it started. It watches its lifeline from a thread of its own
    (:func:`_watch_the_pass`). For each job it says "started" before
    anything touches the file - an end before it is the machine's, after it
    the file's - and hands back the answer, or what the job raised as
    words, never left to end the process in silence. Every answer carries
    what the reader has to tell the pass (:func:`take_notes`)."""
    if hasattr(os, "setsid"):
        os.setsid()
    threading.Thread(target=_watch_the_pass, args=(lifeline,), name="tracker-lifeline",
                     daemon=True).start()
    if processor_only_:
        processor_only()
    try:
        while True:
            try:
                message = jobs.recv()
            except (EOFError, OSError):
                break                           # the pass closed its end: done
            except Exception:
                # A job it cannot unpack names a reader this process cannot
                # import: the machine's fault, before "started".
                os._exit(UNREADABLE_JOB_EXIT_CODE)
            if message is None:
                break
            job, args, kwargs = message
            _answer(sender, ("started",))
            try:
                answer = job(*args, **kwargs)
            except BaseException as exc:
                # The class, and apart from it the words and the trace: the
                # pass shows the first and keeps the rest on its debug log.
                # This process never opens a log of its own (decision 190).
                _answer(sender, ("failed", errors.error_class(exc), _message_of(exc),
                                 traceback.format_exc(), take_notes()))
                if isinstance(exc, MemoryError):
                    # Past its memory limit: said, and done - the pass
                    # replaces it (SPEC-169 section 9).
                    os._exit(OUT_OF_MEMORY_EXIT_CODE)
            else:
                _answer(sender, ("read", answer, take_notes()))
    finally:
        sender.close()


def _message_of(exc: BaseException) -> str:
    """An exception's own words, for the pass's debug log; an exception
    whose ``__str__`` itself fails is said by its class."""
    try:
        return str(exc)
    except Exception:
        return errors.error_class(exc)


def _answer(sender, message) -> None:
    """Hand the pass an answer - or, when the pass is gone and the pipe
    broken, end: there is nobody left to read it for."""
    try:
        sender.send(message)
    except OSError:
        _orphaned()


def _watch_the_pass(lifeline) -> None:
    """The child's lifeline thread. The pass never writes to it, so the
    wait ends only when the pass's end closes - the pass finished with the
    child, or the pass is gone. Either way the child has nothing left to do."""
    try:
        lifeline.recv()
    except (EOFError, OSError):
        pass
    _orphaned()


def _orphaned() -> None:
    """End this child now, and on POSIX the process group it leads, so
    whatever it started ends with it (on Windows its job does that)."""
    if hasattr(os, "killpg"):
        try:
            os.killpg(os.getpgrp(), signal.SIGKILL)
        except OSError:
            pass
    os._exit(ORPHANED_EXIT_CODE)


def _extended_limits():
    """``kernel32``'s JOBOBJECT_EXTENDED_LIMIT_INFORMATION, as ``ctypes``
    lays it out (Windows only)."""
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BasicLimits),
                    ("IoInfo", IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    return ExtendedLimits


def _kill_on_close_job(pid: int, *, memory_limit: int = 0):
    """On Windows, a job object holding the child ``pid`` that kills every
    process in it when its last handle closes - the handle returned here,
    which only the pass holds (it is not inheritable) - and, given
    ``memory_limit``, lets no process in it commit more than that many
    bytes. None elsewhere, or where Windows refuses; the lifeline still
    stands then, and it is said.

    The standard library's ``ctypes`` and nothing else: ``kernel32``'s
    CreateJobObject, SetInformationJobObject with
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (and JOB_OBJECT_LIMIT_PROCESS_MEMORY),
    and AssignProcessToJobObject."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    ExtendedLimits = _extended_limits()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                                 wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        log.warning("No job object for the reading (Windows error %d); its lifeline stands",
                    ctypes.get_last_error())
        return None
    limits = ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if memory_limit:
        limits.BasicLimitInformation.LimitFlags |= _JOB_OBJECT_LIMIT_PROCESS_MEMORY
        limits.ProcessMemoryLimit = memory_limit
    process = kernel32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid)
    placed = bool(process) and bool(
        kernel32.SetInformationJobObject(job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                         ctypes.byref(limits), ctypes.sizeof(limits))
        and kernel32.AssignProcessToJobObject(job, process))
    error = ctypes.get_last_error()
    if process:
        kernel32.CloseHandle(process)
    if not placed:
        kernel32.CloseHandle(job)
        log.warning("The reading could not be put in a job object (Windows error %d); "
                    "its lifeline stands", error)
        return None
    return job


#: kernel32's numbers for :func:`_kill_on_close_job`.
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x0100
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001


def _job_memory(job) -> tuple[int, int]:
    """A reading's job's (memory limit per process, the most any process in
    it has committed), in bytes; (0, 0) with no job or where Windows will
    not say. Read before the job is closed."""
    if job is None:
        return 0, 0
    import ctypes
    from ctypes import wintypes

    ExtendedLimits = _extended_limits()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.QueryInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                                   wintypes.DWORD, wintypes.LPVOID)
    limits = ExtendedLimits()
    if not kernel32.QueryInformationJobObject(job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                              ctypes.byref(limits), ctypes.sizeof(limits), None):
        return 0, 0
    return limits.ProcessMemoryLimit, limits.PeakProcessMemoryUsed


def _close_job(job) -> None:
    """Close the pass's handle on a reading's job: anything still in it ends."""
    if job is None:
        return
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle(job)


def _end(process) -> None:
    """End a reading's child and everything it started, the whole tree."""
    if sys.platform == "win32":
        system = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32"
        try:
            subprocess.run([str(system / "taskkill.exe"), "/F", "/T", "/PID", str(process.pid)],
                           capture_output=True, timeout=CHILD_EXIT_SECONDS, check=False,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("Could not end the reading's process tree (%s)", exc)
    else:
        try:
            if os.getpgid(process.pid) == process.pid:      # it leads its own group
                os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass                                            # already gone
    process.kill()                                          # the child itself, whatever happened above
    process.join(CHILD_EXIT_SECONDS)


# -------------------------------------------------------- the pass's reader ----


@dataclass(slots=True)
class Session:
    """The reader for one pass (or one app command): its child, the device,
    and what the pass says about the reader."""

    in_a_child: bool = True
    child: ReadingChild | None = None
    #: The device the run log's first line names.
    device: str = DEVICE_PROCESSOR
    #: The run-log line when the pack could not be used, or "".
    note: str = ""
    #: The document a fault on the card happened on, or "".
    gpu_failed_on: str = ""
    _processor_only: bool = False
    _said: list[str] = field(default_factory=list)

    def settle(self) -> None:
        """At a pass's start: with a graphics card pack, start the child
        and have it build its engine and read the self-test, so the device
        is known before the run log's first line. Without one, nothing
        starts: the reader will read on the processor."""
        if gpu_pack() is None:
            return
        cannot_run = ""
        if self.in_a_child:
            outcome = self.run(warm_up, (), {}, stop=WARM_UP_STOP_SECONDS, retry=False)
            if outcome.kind == "read":
                self.device, why = outcome.answer
            else:
                # The warm-up reads the firm's own self-test, never a client's
                # file, so its words are the machine's and are said in full.
                said = ": ".join(part for part in (outcome.error, outcome.message) if part)
                self.device, why = DEVICE_PROCESSOR, said or "the reader did not answer"
                if outcome.error == ReaderUnavailable.__name__:
                    cannot_run = outcome.message or outcome.error
        else:
            try:
                self.device, why = warm_up()
            except ReaderUnavailable as exc:
                self.device, why = DEVICE_PROCESSOR, str(exc)
                cannot_run = str(exc)
            take_notes()
        if cannot_run:
            # Not the card's fault: nothing can read here (REVIEW-169, N-1).
            self.note = READER_CANNOT_RUN.format(reason=cannot_run)
            self._processor_only = True
        elif why:
            self.note = PACK_UNUSABLE.format(reason=why)
            self._processor_only = True

    def run(self, job, args: tuple, kwargs: dict, stop: float, *, retry: bool = True) -> Outcome:
        """Run one job in this session's child, starting one if there is none.

        A child that ends without an answer (or runs out of memory) is not
        always the document's fault (REVIEW-169, M-1 and S-1). On the
        graphics card it is a fault on the card: the rest of the pass reads
        on the processor, and the pass says so once. In a child that had
        already served a document it may be what the earlier ones left
        behind. Either way the document is read once more, on a fresh child
        with a fresh stop, and only what that says is kept. ``retry=False``
        is the warm-up's: its answer settles the device instead."""
        outcome, child = self._run_once(job, args, kwargs, stop)
        if not retry or child is None or not _crashed(outcome):
            return outcome
        on_the_card, used = child.on_the_card, child.served > 1
        if not (on_the_card or used):
            return outcome                  # a fresh processor child: the file's own
        name = _document_name(args)
        if on_the_card:
            self.gpu_failed_on = self.gpu_failed_on or name
            self._processor_only = True
            log.warning("The reading's process on the graphics card ended while reading %s (%s); "
                        "reading it again on the processor", name, outcome.error)
        else:
            log.warning("The reading's process ended while reading %s after serving %d document(s) "
                        "(%s); reading it again in a fresh one", name, child.served - 1, outcome.error)
        again, _child = self._run_once(job, args, kwargs, stop)
        again.seconds += outcome.seconds
        return again

    def _run_once(self, job, args: tuple, kwargs: dict,
                  stop: float) -> tuple[Outcome, ReadingChild | None]:
        """:meth:`run`'s one try: the outcome, and the child that ran it."""
        started = awake_clock()
        fresh = self.child is None
        if fresh:
            try:
                self.child = ReadingChild(processor_only=self._processor_only)
            except Exception as exc:
                # The class travels towards the row; the words are kept apart
                # (decision 190).
                errors.keep("ocr: the reading child could not be made", exc)
                return Outcome("not_started", error=errors.error_class(exc),
                               seconds=awake_clock() - started), None
        child = self.child
        outcome = child.run(job, args, kwargs, stop, since=started if fresh else None)
        self.hear(outcome.notes)
        # Replaced after a stop, a crash, running out of memory or a child
        # that never started, a fault on the card, and every
        # DOCUMENTS_PER_CHILD documents (R-4).
        if (outcome.kind not in ("read", "failed") or _crashed(outcome)
                or child.served >= DOCUMENTS_PER_CHILD
                or (self.gpu_failed_on and not self._processor_only)):
            self._replace()
        return outcome, child

    def hear(self, notes: list[tuple[str, str]]) -> None:
        """Take what a reader said: a fault on the card sends the rest of the
        pass to the processor."""
        for kind, what in notes:
            if kind == "gpu-fault" and not self.gpu_failed_on:
                self.gpu_failed_on = what
            elif kind == "pack-unusable":
                # The card cannot be used here: no later child tries it
                # again inside a document's own stop (REVIEW-169, S-3).
                self.note = self.note or PACK_UNUSABLE.format(reason=what)
                self._processor_only = True
                if self.child is not None:
                    self.child.on_the_card = False      # it reads on the processor now

    def _replace(self) -> None:
        """Let the child go; the next document starts a fresh one, on the
        processor only once the card has failed this pass."""
        child, self.child = self.child, None
        if self.gpu_failed_on:
            self._processor_only = True
        if child is not None:
            child.finish()

    def warnings(self) -> list[str]:
        """What the pass says once about its reader: a fault on the card."""
        if not self.in_a_child:
            self.hear(take_notes())
        if self.gpu_failed_on and GPU_FAULT_WARNING not in self._said:
            self._said.append(GPU_FAULT_WARNING)
            return [GPU_FAULT_WARNING.format(file=self.gpu_failed_on)]
        return []

    def close(self) -> None:
        """The pass is over: no child outlives it."""
        if self.child is not None:
            child, self.child = self.child, None
            child.finish()
        if not self.in_a_child:
            reset()


def _crashed(outcome: Outcome) -> bool:
    """A child that ended without an answer, or ran out of memory (it then
    says so and ends: SPEC-169 section 9)."""
    return outcome.kind == "died" or (outcome.kind == "failed"
                                      and outcome.error.startswith(MemoryError.__name__))


def _document_name(args: tuple) -> str:
    """The name of the file a job was handed, for the pass's words."""
    if args and isinstance(args[0], (str, os.PathLike)):
        return Path(args[0]).name
    return "a document"


#: The session open in this process, or None.
_SESSION: Session | None = None


@contextmanager
def reading_session(*, settle: bool = False, in_a_child: bool = True) -> Iterator[Session]:
    """The reader for a pass or an app command: one child, started when the
    first reading needs it (or at once, with a graphics card pack, when
    ``settle`` asks for the device up front), and ended when the block
    ends. A session opened inside another is the outer one."""
    global _SESSION
    if _SESSION is not None:
        yield _SESSION
        return
    session = Session(in_a_child=in_a_child)
    _SESSION = session
    try:
        if settle:
            session.settle()
        yield session
    finally:
        _SESSION = None
        session.close()


def current_session() -> Session | None:
    """The session open in this process, or None."""
    return _SESSION


def run_in_child(job, args: tuple, kwargs: dict, stop: float) -> Outcome:
    """Run one job in the open session's child - or, with none open, in a
    session of its own that ends with the job."""
    if _SESSION is not None:
        return _SESSION.run(job, args, kwargs, stop)
    with reading_session() as session:
        return session.run(job, args, kwargs, stop)


if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    # It prints the name of the photo it is given, which may be a client's.
    tolerant_console()
    parser = argparse.ArgumentParser(
        prog="python -m tracker.ocr",
        description="Which reader this machine uses: builds the engine the way a pass does - "
                    "the graphics card pack if it is here, its self-test, else the processor - "
                    "and says which. Given a photo, it also times one reading of it. "
                    "Read-only: nothing is written, nothing is fetched.")
    parser.add_argument("photo", nargs="?", default="", help="a photo or page image to read once")
    ns = parser.parse_args()
    started = time.perf_counter()
    try:
        used, why = warm_up()
    except ReaderUnavailable as exc:
        print(f"The reader cannot run on this machine: {exc}")
        raise SystemExit(1) from None
    print(f"reader={used} (ready in {time.perf_counter() - started:.1f} s)")
    if why:
        print(PACK_UNUSABLE.format(reason=why))
    if ns.photo:
        from PIL import Image, ImageOps

        with Image.open(ns.photo) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        started = time.perf_counter()
        lines = read_page(image, name=Path(ns.photo).name).splitlines()
        print(f"{Path(ns.photo).name}: {len(lines)} line(s) in {time.perf_counter() - started:.2f} s")
