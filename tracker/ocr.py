"""The reader (decision 169): RapidOCR, on the graphics card when it works
and on the processor when it does not, and the one child process the pass
reads in.

**What reads.** RapidOCR - PaddleOCR's detection, direction and recognition
models in ONNX form, run by ONNX Runtime - with the three models shipped
inside the app (``rapidocr``'s own package folder, collected as data by
``api_entry.spec``). Nothing is downloaded, ever: every model is named by
path, and rapidocr's own downloader is replaced by a refusal before any
engine is built (:func:`_refuse_downloads`), and the ONNX Runtime library is
told to send no telemetry of its own (:func:`_telemetry_off`, P263), so a
missing or broken model is "the reader could not run on this machine"
(``reasons.NO_TEXT_LAYER``, transient) and never a request to the network. Tesseract, which read
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
come, and drops every box the reader scored under the settings' floor
(:data:`CONFIDENT_SCORE` as shipped; P282's guard 2: rapidocr's own floor,
held here so the product owns the number). It never turns a page and never
costs a second reading; the turning rule arrives later as the amendment
"169, upright", in the seam only.

**The reader's settings are one place** (P283). How a page is drawn and
read - the dots per inch a PDF page is drawn at, the confidence floor, the
long side rapidocr shrinks an image to, the steps of preparation below, and
which tier of models reads - are the fields of :class:`ReaderSettings`, and
the ones this process reads with are :data:`SETTINGS`. The product reads with
:data:`SHIPPED` and never changes them. :func:`use_settings` is for the
reader bench (``tools/reader_bench.py``) and the suite, which try other
settings in their own process; it must never run in a reading child, which
imports this module afresh and so always reads at :data:`SHIPPED`.

**A page is prepared before the reader reads it** (P285, Jason's ruling:
"ocr dcouments should be preppred before feeing the machine,"). :func:`prepared`
is the stage every page and photo goes through in :func:`read_page`, in
memory and on a copy - the file is never touched and nothing is written. In
the order each step needs its input in: the page is made grey and held to
the settings' long side (:func:`_held`, so the threshold is taken at the
resolution the engine reads); turned level if it leans a little
(:func:`_skew_degrees`, :func:`_levelled`: a projection profile, which
refuses to guess - no plain winner, or a lean past five degrees, leaves the
page as it is); made black and white by a threshold that follows the
paper's own shading (:func:`_sauvola`, or :func:`_otsu` for the bench's
comparison); cleared of lone specks (:func:`_despeckled`: a count of
connected pixels, not a median, which would erase a faded one-pixel stroke);
and cleared of a form's long box rules (:func:`delined`, last, because a
rule is a long run of ink and crisp on the thresholded page). Each step is a
switch of :class:`ReaderSettings`; none of the constants is. :data:`RAW` is
the reading P283 shipped (144 dpi, no step of preparation); :data:`SHIPPED`
is the prepared one at 300 dpi. The verdict cache moved with it
(``content_check.CACHE_VERSION``), because every verdict on a scan or a photo
was reached on other pixels. The trade-off, said plainly: PP-OCR's models
were trained on grey and colour crops, so pure black and white can lower
recognition on a clean sharp scan while it helps a faded or shadowed one, a
wrong turn is worse than none, and removing a rule can clip a letter it ran
through - which is why each step is a switch and the bench measures each one.
No model is added and no generative AI reads a page: every step is fixed
pixel arithmetic in OpenCV and numpy, the same page prepared twice is the
same pixels.

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
  child past it fails its reading, ends and is replaced, as a crash. Off
  Windows there is no job object, so the pass waits in slices of
  :data:`MEMORY_WATCH_SECONDS` and reads the child's memory between them
  (R31 of SPEC-mac): ``ri_phys_footprint`` from libproc on a Mac, the
  resident pages of ``/proc/<pid>/statm`` on Linux. Past the same limit the
  child is ended and the reading is a crash with the same words.
  ``setrlimit(RLIMIT_AS)`` was the rejected alternative - macOS does not
  honour it reliably, and it would cap address space, not memory. A
  footprint that cannot be read is no cap, and the error log says so once.

**Nothing a reading does may outlive it in the child.** The child serves
many documents, so a reader must never change module state (a global, a
patched function) for one document and leave it for the next.

**Nor may anything it writes.** The child points the temp folder - ``TMP``,
``TEMP``, ``TMPDIR`` and :data:`tempfile.tempdir` - at a folder of its own,
``scratch_root() / <its pid>`` in the data home, before it serves anything
(decision 186). The reader writes no temporary file today (SPEC-169 section
6); that was a measurement, and this makes it a place: whatever a library
writes *through the temp folder* (``tempfile``, ``GetTempPath``, ``TMPDIR``)
lands in the child's folder, which is removed when the child ends, and never
in the machine's temp folder. One folder per process, and only a folder
whose process is gone is ever swept, so a preview's child can never empty the
folder under a running pass (D-14).

What this does not cover (SPEC-186 section 10, the review's S2): a library
that writes to a path of its own choosing is not caught. A reading made in
this process (``reading_session(in_a_child=False)``) redirects nothing - the
backtest, which reads in its own process, points the temp folder at its own
scratch for the run instead. A killed child's folder lives until the next
child starts and sweeps it; a folder whose process number Windows has reused
for a live process lives until that process ends.

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
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from tracker import errors
from tracker.locking import pid_alive
from tracker.settings import SettingsError, scratch_root

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
#: The detection and recognition files of each tier of models. The medium
#: names are the files rapidocr's ``download_models`` writes (the last part
#: of the ``model_dir`` URLs in its ``default_models.yaml``); they are never
#: shipped and never fetched here - a person puts them in a folder the
#: bench is given. The direction model is always the shipped one.
MODEL_TIERS: dict[str, tuple[str, str]] = {
    "small": (DETECTION_MODEL, RECOGNITION_MODEL),
    "medium": ("PP-OCRv6_det_medium.onnx", "PP-OCRv6_rec_medium.onnx"),
}
#: The engine's sessions, by rapidocr's own attribute names: detection,
#: direction ("cls") and recognition. Each must be on CUDA for the card.
SESSIONS = ("text_det", "text_cls", "text_rec")
CUDA_PROVIDER = "CUDAExecutionProvider"

#: The self-test page: a line of a form's own words, drawn here.
SELF_TEST_TEXT = "Wage and Tax Statement 2025"
SELF_TEST_WORDS = ("wage", "statement")

#: The lowest recognition score a box may have and still be read (P282's
#: guard 2). It is rapidocr's own default floor (``Global.text_score``),
#: held here so the product owns the number and a test can see it applied;
#: Part C may raise it from the office measurement.
CONFIDENT_SCORE = 0.5
#: The lowest dots per inch a page may be drawn at (a PDF point is 1/72 inch).
MINIMUM_DPI = 72


#: The ways a page is made black and white (:class:`ReaderSettings`'s
#: ``binarize``): not at all, one threshold for the page (Otsu), or one per
#: pixel from its neighbourhood (Sauvola, the shipped one).
BINARIZERS = ("off", "otsu", "sauvola")


@dataclass(frozen=True, slots=True)
class ReaderSettings:
    """Every setting of how a page is drawn, prepared and read, in one place
    (P283, extended by P285), in the order a page is processed in.

    ``render_dpi``: a PDF page is drawn at ``render_dpi / 72``
    (:func:`tracker.content_check.render_scale`, which also holds it inside
    the pixel budget); a photo has no dpi. ``confident_score``: the floor
    under which a box is not read, given to rapidocr as ``Global.text_score``
    and held again in :func:`_upright_lines`. ``max_side_len``: rapidocr's
    ``Global.max_side_len``, and the long side :func:`prepared` holds a page
    to. ``deskew``: turn a page leaning up to five degrees level.
    ``binarize``: one of :data:`BINARIZERS`. ``denoise``: whiten lone specks.
    ``delining``: whiten a form's long box rules (:func:`delined`).
    ``model_tier``: a key of :data:`MODEL_TIERS`. ``model_folder``: where the
    tier's detection and recognition models are; ``""`` is the app's own
    :func:`models_folder`.

    The defaults are :data:`RAW`, the reading as it was before the page was
    prepared."""

    render_dpi: int = 144
    confident_score: float = CONFIDENT_SCORE
    max_side_len: int = 2000
    deskew: bool = False
    binarize: str = "off"
    denoise: bool = False
    delining: bool = False
    model_tier: str = "small"
    model_folder: str = ""


#: The reading P283 shipped: 144 dpi, floor 0.5, long side 2000, no step of
#: preparation, the small models. The bench's raw rows are built from it.
RAW = ReaderSettings()
#: What the product reads with (P285, Jason's ruling): the page drawn at 300
#: dpi and prepared. 3300 is a letter page's long side at 300 dpi
#: (``ceil(11 * 300)``, the bench's ``long_side(300)``), so a 300 dpi page is
#: not shrunk back to 2000 (182 dpi) by rapidocr; a legal page (14 in, 4200
#: px) is still held to 3300, about 236 dpi.
SHIPPED = ReaderSettings(render_dpi=300, confident_score=0.5, max_side_len=3300, deskew=True,
                         binarize="sauvola", denoise=True, delining=True, model_tier="small",
                         model_folder="")
#: What this process reads with. The product never changes it.
SETTINGS: ReaderSettings = SHIPPED


class ReaderUnavailable(Exception):
    """The reader cannot run on this machine: a package or a model file is
    missing or broken. The machine's fault, never the file's."""


#: The longest full path a library inside the frozen app may have. Loading
#: failed from 252-255 characters on the office machine (REVIEW-169, N-5),
#: below Windows' 260, so this leaves a margin.
READER_PATH_LIMIT = 240
#: What the app and the pass say when the app sits too deep to read.
READER_PATH_WARNING = ("Move the app to a shorter folder, for example C:\\JPA App; "
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


def _telemetry_off(onnxruntime) -> None:
    """Tell ONNX Runtime never to send its own telemetry (P263), the first
    thing done with the module after it is imported and before any session
    is made. The macOS wheel carries a telemetry client with an HTTP path
    (re-run 1 of the Mac check saw it abort a child at exit), and nothing in
    the reader's path talks to the network. A library without the switch is
    a :class:`ReaderUnavailable`, said loudly like a missing import: none we
    lock lacks it, and a silent skip would leave the client free to send."""
    switch = getattr(onnxruntime, "disable_telemetry_events", None)
    if switch is None:
        raise ReaderUnavailable("onnxruntime has no disable_telemetry_events; "
                                "the reader will not run with its telemetry on")
    switch()


def _build_engine(*, cuda: bool):
    """A RapidOCR engine on the models of :data:`SETTINGS` (the shipped ones
    unless the bench asked for another tier): SPEC-127.2X section 13 O1's
    defaults, the settings' floor and long side, and on the card the
    benchmark harness's settings (a heuristic cuDNN search, since page
    shapes change every page, and batches of 32). A model file that is not
    there is :class:`ReaderUnavailable`; nothing is fetched."""
    try:
        import onnxruntime
        from rapidocr import RapidOCR
        from rapidocr.utils.typings import ModelType
    except ImportError as exc:
        raise ReaderUnavailable(f"{errors.error_class(exc)}: {exc}") from exc
    _telemetry_off(onnxruntime)
    _refuse_downloads()
    onnxruntime.set_default_logger_severity(3)
    own = models_folder()
    tier_folder = Path(SETTINGS.model_folder) if SETTINGS.model_folder else own
    detection, recognition = MODEL_TIERS[SETTINGS.model_tier]
    paths = {detection: tier_folder / detection, recognition: tier_folder / recognition,
             DIRECTION_MODEL: own / DIRECTION_MODEL}
    for name, path in paths.items():
        if not path.is_file():
            raise ReaderUnavailable(f"the model {name} is missing")
    params = {
        "Global.log_level": "critical",
        "Global.model_root_dir": str(tier_folder),
        "Global.text_score": SETTINGS.confident_score,
        "Global.max_side_len": SETTINGS.max_side_len,
        # P285: the detector reads a copy held to rapidocr's own 2000-pixel
        # long side, as under P283; recognition still crops its words from
        # the page at SETTINGS.max_side_len. Under rapidocr's default ("min",
        # 736) a page whose shorter side is already past 736 is never shrunk
        # for detection, so the detector ran on the whole 3300 x 2550 page and
        # the process reached 2.4 GB, past the reading child's 2 GB; under
        # "max" its own get_preprocess holds any page over 1500 px to a 2000
        # px copy (Det.limit_side_len is ignored there and is not set), maps
        # the boxes back, and the crops come from the 3300 page. Measured on a
        # drawn letter page: peak 1.03 GB against 2.43 GB, the same lines read.
        "Det.limit_type": "max",
        # rapidocr takes a model type as its own enum, never as text.
        "Det.model_type": ModelType(SETTINGS.model_tier),
        "Rec.model_type": ModelType(SETTINGS.model_tier),
        "Det.model_path": str(paths[detection]),
        "Rec.model_path": str(paths[recognition]),
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

    _telemetry_off(onnxruntime)
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


def use_settings(settings: ReaderSettings) -> ReaderSettings:
    """Make ``settings`` this process's, drop the built engine so the next
    reading builds one with them, and return the settings it replaced.

    Refuses (``ValueError``) a ``model_tier`` that is not in
    :data:`MODEL_TIERS`, a ``binarize`` that is not in :data:`BINARIZERS`, a
    ``render_dpi`` under :data:`MINIMUM_DPI` and a ``confident_score``
    outside 0-1.

    **For the reader bench and the suite only.** The product reads with
    :data:`SHIPPED`. This must never run in a reading child: the module's
    rule is that a reading leaves no module state behind for the next
    document, and a child imports this module afresh, as :data:`SHIPPED`, so
    a setting changed in the pass's process would never reach it anyway."""
    global SETTINGS, _ENGINE, _DEVICE
    if settings.model_tier not in MODEL_TIERS:
        raise ValueError(f"no such model tier {settings.model_tier!r}; the tiers are "
                         f"{', '.join(MODEL_TIERS)}")
    if settings.binarize not in BINARIZERS:
        raise ValueError(f"no such way to make a page black and white {settings.binarize!r}; "
                         f"the ways are {', '.join(BINARIZERS)}")
    if settings.render_dpi < MINIMUM_DPI:
        raise ValueError(f"a page cannot be drawn at {settings.render_dpi} dpi; "
                         f"the least is {MINIMUM_DPI}")
    if not 0 <= settings.confident_score <= 1:
        raise ValueError(f"the confidence floor {settings.confident_score} is not between 0 and 1")
    previous, SETTINGS = SETTINGS, settings
    _ENGINE, _DEVICE = None, ""
    return previous


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


#: A stroke longer than a fortieth of the page's side is a rule; shorter is
#: a letter (P283, :func:`delined`).
DELINE_FRACTION = 40
#: The square a found rule is grown by once, so its anti-aliased edge goes
#: with it.
DELINE_GROW = 3
#: The rule thickness, in pixels, the repair always allows for, however small
#: the page: a rule up to this thick is bridged where it crossed a letter.
DELINE_RULE_FLOOR = 3
#: A rule is allowed to be this fraction of the page's shorter side thick
#: (a 250th: about 4 px at 144 dpi, 10 px at 300) before the repair leaves
#: its cut alone as a border, not a rule.
DELINE_RULE_DIVISOR = 250
#: A rule is also at least this many pixels long, however small the page: a
#: fifth of an inch at 300 dpi, shorter than the shortest cell edge a tax
#: form draws and longer than any stroke of 40 px type. It only bites on a
#: canvas under 2400 px, where a fortieth falls below it.
DELINE_RULE_LEAST = 60
#: A rule is thin: a run of ink thicker than the larger of this many pixels
#: and a five-hundredth of the page's longer side (plus one) is type. A printed
#: rule is 2 to 6 px at 300 dpi, the stem of 28 pt bold type about 16.
DELINE_THICK_FLOOR = 3
DELINE_THICK_DIVISOR = 500

#: The long side the lean is measured on (:func:`_skew_degrees`): the page is
#: reduced to this, so the 34 trial turns cost milliseconds.
DESKEW_SAMPLE_SIDE = 1000
#: The search reaches this far either side of level, half a degree past the
#: limit, so a page leaning more shows its best at the search's edge.
DESKEW_SEARCH_DEGREES = 5.5
#: The steps of the coarse search and then of the fine one around its best.
DESKEW_COARSE_STEP = 0.5
DESKEW_FINE_STEP = 0.1
#: A page leaning more than this is left as it is: a wrong turn is worse
#: than none.
DESKEW_LIMIT_DEGREES = 5.0
#: The best angle's score must beat the level score by this factor; a page
#: with no plain winner (turned a quarter) is left alone.
DESKEW_GAIN = 1.10
#: A lean under this is not worth a resampling of the page.
DESKEW_LEAST_DEGREES = 0.25

#: Sauvola's window is a hundredth of the page's shorter side (25 px, one
#: character, on a 300 dpi letter page), never under the floor, which keeps
#: enough neighbourhood for a standard deviation to mean something.
SAUVOLA_WINDOW_DIVISOR = 100
SAUVOLA_WINDOW_FLOOR = 15
#: Sauvola's k: 0.2 keeps a faded stroke black (0.5, the paper's value,
#: lowers the threshold and drops the faint parts of a stroke).
SAUVOLA_K = 0.2
#: Sauvola's R: the largest standard deviation an 8-bit grey can show.
SAUVOLA_R = 128

#: A component of ink this many pixels or fewer is a speck (a dust mark the
#: threshold left); an i's dot is three or four pixels across at 300 dpi.
DENOISE_SPECK_AREA = 2


def _delined_grey(grey):
    """:func:`delined` on a greyscale array: a new array, the same size."""
    import cv2
    import numpy

    grey = grey.copy()
    height, width = grey.shape
    _level, ink = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    across = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_RECT,
                                                        (max(DELINE_RULE_LEAST, width // DELINE_FRACTION), 1)))
    down = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_RECT,
                                                      (1, max(DELINE_RULE_LEAST, height // DELINE_FRACTION))))
    # Thin: whatever lies inside a t x t square of ink is thicker than a
    # printed rule, so it is type, however long its stem.
    thick = max(DELINE_THICK_FLOOR, max(width, height) // DELINE_THICK_DIVISOR) + 1
    heavy = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                             cv2.getStructuringElement(cv2.MORPH_RECT, (thick, thick)))
    rules = cv2.dilate(cv2.bitwise_and(cv2.bitwise_or(across, down), cv2.bitwise_not(heavy)),
                       numpy.ones((DELINE_GROW, DELINE_GROW), numpy.uint8))
    # The even opening kernel of a tall page drifts a pixel past the end of
    # a stroke, and the growth would carry that into the stem's last row: type
    # is never whitened, whatever lies beside it.
    rules[heavy > 0] = 0
    grey[rules > 0] = 255
    span = DELINE_GROW + max(DELINE_RULE_FLOOR, min(width, height) // DELINE_RULE_DIVISOR) + 1
    _level, left = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    for column in (True, False):
        # An even kernel's closing drifts a pixel unless the erosion's anchor
        # mirrors the dilation's, so the two are anchored by hand.
        kernel = numpy.ones((span, 1) if column else (1, span), numpy.uint8)
        grown, eroded = ((span // 2, 0), (span - 1 - span // 2, 0)) if column else \
            ((0, span // 2), (0, span - 1 - span // 2))
        left = cv2.erode(cv2.dilate(left, kernel, anchor=grown[::-1]), kernel, anchor=eroded[::-1])
    grey[(left > 0) & (rules > 0)] = 0
    return grey


def delined(image):
    """A copy of ``image`` with a form's long box rules whitened (P283), the
    last step of :func:`prepared`.

    Jason's step 5. Pure and in memory: the page it is given is never
    touched and nothing is written.

    Ink is found as white on black (Otsu); a horizontal and a vertical
    opening whose length is a fortieth of the page's side (never under
    :data:`DELINE_RULE_LEAST` pixels) keep only strokes longer than a letter.
    A rule is long *and thin*: an opening with a square a little thicker than
    a printed rule finds the ink that is thicker, the stems of large type,
    and those are taken out of the mask, so a bold title is not mistaken for
    a rule (the first build took a 28 pt title's stems for rules and the
    reader lost the form number). The two masks are joined, grown once, and
    whitened in a greyscale copy. A letter a rule crossed lost a sliver as
    thick as the rule plus the growth's margin, so a closing on the ink that
    remains, a column then a row, as long as that sliver can be, rejoins the
    stroke;
    only the bridging pixels inside the whitened rule are laid back as black,
    so nothing outside the rule changes and two letters that merely sit close
    are never joined. On a black-and-white page its two Otsu steps split
    exactly black from white - redundant there, harmless, and needed when the
    bench de-lines a grey page. Returns an ``RGB`` image the size of the
    input."""
    import numpy
    from PIL import Image

    grey = _delined_grey(numpy.asarray(image.convert("L")))
    return Image.fromarray(grey, "L").convert("RGB")


def _held(grey, long_side: int):
    """``grey``, resized to ``long_side`` on its longer side if it is longer
    (``INTER_AREA``), else as it is. Never enlarged: upscaling recovers
    nothing. Why here: rapidocr shrinks any image past ``Global.max_side_len``
    anyway, so doing it first takes the threshold at the resolution the
    engine reads (a black-and-white page resampled afterwards turns grey at
    every edge again), and it bounds the stage's memory - a photo may be 40
    million pixels, and Sauvola's float arrays at that size would near the
    reading child's cap."""
    import cv2

    height, width = grey.shape
    longest = max(height, width)
    if longest <= long_side:
        return grey
    ratio = long_side / longest
    return cv2.resize(grey, (max(1, round(width * ratio)), max(1, round(height * ratio))),
                      interpolation=cv2.INTER_AREA)


def _skew_scores(ink, angles) -> list[float]:
    """The variance of the row sums of ``ink`` turned by each of ``angles``
    about its centre: lines of print stacked level make tall, separate peaks,
    and a lean smears them."""
    import cv2
    import numpy

    height, width = ink.shape
    centre = (width / 2, height / 2)
    scores = []
    for angle in angles:
        turned = cv2.warpAffine(ink, cv2.getRotationMatrix2D(centre, float(angle), 1.0), (width, height),
                                flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        scores.append(float(numpy.var(turned.sum(axis=1, dtype=numpy.float64))))
    return scores


def _skew_gain(grey) -> tuple[float, float]:
    """(the best angle, the best score over the level score) - the numbers
    :func:`_skew_degrees` judges. The angle is the one the page leans by,
    counter-clockwise positive as ``PIL.Image.rotate`` turns; ``(0.0, 0.0)``
    when the sample has no ink."""
    import cv2
    import numpy

    height, width = grey.shape
    ratio = DESKEW_SAMPLE_SIDE / max(height, width)
    if ratio < 1:
        grey = cv2.resize(grey, (max(1, round(width * ratio)), max(1, round(height * ratio))),
                          interpolation=cv2.INTER_AREA)
    _level, ink = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    if not ink.any():
        return 0.0, 0.0
    coarse = numpy.arange(-DESKEW_SEARCH_DEGREES, DESKEW_SEARCH_DEGREES + DESKEW_COARSE_STEP / 2,
                          DESKEW_COARSE_STEP)
    scores = _skew_scores(ink, coarse)
    best = float(coarse[int(numpy.argmax(scores))])
    fine = numpy.arange(best - DESKEW_COARSE_STEP, best + DESKEW_COARSE_STEP + DESKEW_FINE_STEP / 2,
                        DESKEW_FINE_STEP)
    fine_scores = _skew_scores(ink, fine)
    top = int(numpy.argmax(fine_scores))
    level = _skew_scores(ink, [0.0])[0]
    # The trial turn that levels the page is the opposite of the way it leans.
    return -round(float(fine[top]), 1), (fine_scores[top] / level if level > 0 else 0.0)


def _skew_degrees(grey) -> float:
    """The angle ``grey`` leans by, counter-clockwise positive as
    ``PIL.Image.rotate`` turns (a level page turned by ``rotate(2)`` gives
    about 2.0), or **0.0 - leave it alone** when the sample has no ink, the
    best angle is past :data:`DESKEW_LIMIT_DEGREES`, its score does not beat
    the level score by :data:`DESKEW_GAIN` (no plain winner: a page turned a
    quarter has none, and is left for the engine, which already reads it), or
    the angle is under :data:`DESKEW_LEAST_DEGREES`.

    A projection profile, not ``minAreaRect`` (the outline of everything
    inked - a logo or a stamp sways it - and OpenCV changed its angle
    convention in 4.5) and not a Hough transform (it needs long straight
    edges, which a letter or a receipt may not have). The profile asks the
    question directly: at which angle do the lines of print stack most
    sharply. The search reaches half a degree past the limit so a page
    leaning more shows its best at the search's edge, not inside it. It
    matters for P282: ``_upright_lines`` groups boxes into lines by their
    centres, and a 2 degree lean drifts two lines' height over a page's width."""
    angle, gain = _skew_gain(grey)
    if (gain < DESKEW_GAIN or abs(angle) > DESKEW_LIMIT_DEGREES
            or abs(angle) < DESKEW_LEAST_DEGREES):
        return 0.0
    return angle


def _levelled(grey, degrees: float):
    """``grey`` turned back by ``degrees`` (what :func:`_skew_degrees` said it
    leans by), on the same canvas, the new corners paper white. The same size,
    not expanded: nothing printed is cut that the scanner had not already cut,
    and the boxes keep the page's frame."""
    import cv2

    height, width = grey.shape
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), -degrees, 1.0)
    return cv2.warpAffine(grey, matrix, (width, height), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=255)


def _otsu(grey):
    """One threshold for the whole page, from its histogram: black and white."""
    import cv2

    _level, bright = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return bright


def _sauvola_window(height: int, width: int) -> int:
    """Sauvola's window: a hundredth of the shorter side, never under the
    floor, always odd so a pixel sits at its window's centre."""
    return max(SAUVOLA_WINDOW_FLOOR, min(height, width) // SAUVOLA_WINDOW_DIVISOR) | 1


def _sauvola(grey):
    """A threshold per pixel from its window (Sauvola): ``T = m (1 + k (s / R
    - 1))``, ``m`` and ``s`` the window's mean and standard deviation, from
    integral images, so constant time per pixel whatever the window. A pixel
    at or under its threshold is ink (0), any other paper (255); ``<=`` so a
    solid black fill stays black.

    R is the largest standard deviation an 8-bit grey can show, so ``T`` stays
    between ``0.8 m`` and ``m``: a flat region - clean paper, or a smooth
    shadow - is never darker than its own threshold and stays white, while a
    stroke beside paper raises ``s`` and falls under it. A dark fill wider
    than the window keeps only its edges; tax forms print few."""
    import cv2
    import numpy

    height, width = grey.shape
    window = _sauvola_window(height, width)
    margin = window // 2
    padded = cv2.copyMakeBorder(grey, margin, margin, margin, margin, cv2.BORDER_REFLECT_101)
    total, squares = cv2.integral2(padded, sdepth=cv2.CV_64F)

    def window_sums(integral):
        return (integral[window:window + height, window:window + width]
                - integral[:height, window:window + width]
                - integral[window:window + height, :width]
                + integral[:height, :width])

    count = float(window * window)
    mean = window_sums(total) / count
    deviation = numpy.sqrt(numpy.maximum(0.0, window_sums(squares) / count - mean * mean))
    threshold = mean * (1.0 + SAUVOLA_K * (deviation / SAUVOLA_R - 1.0))
    return numpy.where(grey <= threshold, 0, 255).astype(numpy.uint8)


def _despeckled(grey):
    """``grey`` with every lone speck whitened: the ink (Otsu's, which on a
    black-and-white page is exactly black from white) is labelled by connected
    pixels, and a component of :data:`DENOISE_SPECK_AREA` pixels or fewer is
    whitened. Nothing else changes, pixel for pixel. A median or an opening
    was rejected: both erase a one-pixel-wide stroke and round every letter's
    corners, which is exactly the fragile faded text to protect."""
    import cv2

    _level, ink = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    _count, labels, stats, _centres = cv2.connectedComponentsWithStats(ink, connectivity=8)
    speck = stats[:, cv2.CC_STAT_AREA] <= DENOISE_SPECK_AREA
    speck[0] = False                        # label 0 is the paper
    cleaned = grey.copy()
    cleaned[speck[labels]] = 255
    return cleaned


def prepared(image, settings: ReaderSettings):
    """``image`` prepared for the reader (P285): a grey copy, held to the
    settings' long side, then - each only when its switch is on, in this
    order - levelled, made black and white, cleared of specks and cleared of
    box lines; returned as an ``RGB`` image. The order is the order each step
    needs its input in: level before black and white (a black-and-white page
    turned by a fraction of a degree gets jagged, grey-edged strokes), black
    and white before specks (a speck is only a speck once paper and ink are
    told apart), box lines last (a rule is a long run of ink, crisp on the
    thresholded page).

    With every step off it returns ``image`` itself, untouched: that is what
    makes the bench's raw rows exactly the reading before P285. With any step
    on the page is grey - deskew alone included - replicated to RGB for the
    engine. Pure, in memory: ``image`` is never touched and nothing is
    written; the same page prepared twice is the same pixels."""
    import numpy
    from PIL import Image

    if (not settings.deskew and settings.binarize == "off" and not settings.denoise
            and not settings.delining):
        return image
    grey = _held(numpy.asarray(image.convert("L")).copy(), settings.max_side_len)
    if settings.deskew and (lean := _skew_degrees(grey)):
        grey = _levelled(grey, lean)
    if settings.binarize == "otsu":
        grey = _otsu(grey)
    elif settings.binarize == "sauvola":
        grey = _sauvola(grey)
    if settings.denoise:
        grey = _despeckled(grey)
    if settings.delining:
        grey = _delined_grey(grey)
    return Image.fromarray(grey, "L").convert("RGB")


def _pixels(image):
    """A PIL image as the engine takes it: BGR, the way OpenCV reads a file."""
    import numpy

    return numpy.asarray(image.convert("RGB"))[:, :, ::-1].copy()


def read_page(image, *, name: str = "") -> str:
    """One page or photo's words, a line per line of print, in reading order.

    ``image`` is a PIL image the right way up as far as the file says (a
    photo's EXIF turn already undone); the page is prepared first
    (:func:`prepared`, in memory, the image itself untouched). ``name`` is the
    document's, for the one warning a fault on the card gives. Raises
    :class:`ReaderUnavailable` when no engine can be built on this machine,
    and whatever the processor's engine raised when it fails on the page."""
    global _ENGINE, _DEVICE
    engine = _engine()
    pixels = _pixels(prepared(image, SETTINGS))
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

    The seam of ruling 6: today it orders what it is given - a box
    joins the line whose centre is within half a typical box height of its
    own, lines run top to bottom and a line's boxes left to right (the
    benchmark harness's ``lines_from_boxes``, which Part 1 measured). It
    drops the boxes the reader was not confident of (a recognition score
    under the settings' ``confident_score``, :data:`CONFIDENT_SCORE` as shipped,
    P282's guard 2) and blank ones; it never
    turns a page. The turning rule lands here, and only here, with
    the amendment "169, upright".

    Fails loudly when boxes and words come with no scores: rapidocr always
    gives one score per box, and a reading that silently skipped the floor
    would file on words the floor exists to drop."""
    boxes = getattr(page_result, "boxes", None)
    texts = getattr(page_result, "txts", None)
    scores = getattr(page_result, "scores", None)
    if boxes is None or texts is None:
        return []
    if scores is None:
        raise ValueError("the reader gave no confidence scores")
    items = []
    for quad, text, score in zip(boxes, texts, scores, strict=False):
        if float(score) < SETTINGS.confident_score:
            continue
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
#: its job object on Windows and watched by the pass elsewhere: a processor
#: child, and a child on the graphics card. Past it the child ends and is
#: replaced.
PROCESSOR_CHILD_MEMORY = 2 * 1024**3
GRAPHICS_CARD_CHILD_MEMORY = 6 * 1024**3
#: Off Windows no job object caps a child, so the pass reads the child's
#: memory itself, between the slices it waits for an answer in (R31). Half a
#: second: a reading that runs away is ended within the second, while the
#: cost is one small read of /proc (or one call into libproc) per slice.
MEMORY_WATCH_SECONDS = 0.5
#: What the error log says, once, when the child's memory cannot be read: the
#: cap is then off, and the log says so rather than guessing a figure.
MEMORY_UNREADABLE = ("the reading's memory could not be read ({reason}); "
                     "its memory limit is not enforced")
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
    :meth:`Session._run_once`, the child's own safety stop
    (``content_check._clock``) and ``runner.HOUSEHOLD_BUDGET_SECONDS``.
    ``time.monotonic`` on Windows counts sleep, so a laptop that slept
    through the night would wake to every reading in flight parked as a file
    that stalled the reader - a verdict about the machine's lid, kept as one
    about the client's file. Task Scheduler's own limit stays wall-clock.
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
    #: What the child kept while it served this job (:func:`tracker.errors.take_kept`):
    #: words for the pass's debug log, which the pass keeps (decision 190, Part 4).
    kept: list = field(default_factory=list)


#: Every way a library finds the temp folder, pointed by a reading child at
#: its own folder in the data home (decision 186), with :data:`tempfile.tempdir`.
SCRATCH_ENV = ("TMP", "TEMP", "TMPDIR")


def sweep_scratch(root: Path) -> list[Path]:
    """Remove the folders under ``root`` whose process is gone, and say which.

    Only a folder named by a process number, and only when
    :func:`tracker.locking.pid_alive` answers that the process is gone:
    a live process's folder, or one whose process cannot be known, is
    kept, so a preview's child never empties a running pass's (D-14). A
    name that is not a number is not the tracker's and is never touched. A
    folder that cannot be removed now - a dying process still holds it - is
    logged and left for the next sweep; nothing here raises."""
    removed: list[Path] = []
    try:
        folders = sorted(root.iterdir())
    except OSError:
        return removed                          # no scratch yet: nothing to sweep
    for folder in folders:
        name = folder.name
        if not (name.isascii() and name.isdigit()) or not folder.is_dir():
            continue
        if pid_alive(name) is not False:
            continue
        try:
            shutil.rmtree(folder)
        except OSError as exc:
            errors.keep("ocr: the scratch sweep", exc, name=folder.name)
            log.warning("Could not remove the scratch folder %s (%s); the next reading sweeps it",
                        folder, errors.error_class(exc))
            continue
        removed.append(folder)
    return removed


def _take_scratch(root: Path) -> Path:
    """Make this process's own temp folder under ``root`` and point every way
    a library finds the temp folder at it. Sweeps first (:func:`sweep_scratch`)."""
    sweep_scratch(root)
    own = root / str(os.getpid())
    own.mkdir(parents=True, exist_ok=True)
    for name in SCRATCH_ENV:
        os.environ[name] = str(own)
    tempfile.tempdir = str(own)
    return own


def _remove_scratch(folder: Path) -> None:
    """Remove an ended child's own folder; a warning, never a raise, when it cannot be."""
    try:
        shutil.rmtree(folder)
    except FileNotFoundError:
        pass
    except OSError as exc:
        errors.keep("ocr: the reading's scratch", exc, name=folder.name)
        log.warning("Could not remove the reading's scratch folder %s (%s); the next reading sweeps it",
                    folder, errors.error_class(exc))


class ReadingChild:
    """One reading child process and the pass's ends of its three pipes:
    jobs in, answers out, and the lifeline the pass never writes to."""

    def __init__(self, *, processor_only: bool) -> None:
        import multiprocessing

        # Where the child keeps whatever a library writes (decision 186),
        # asked before any process or pipe exists: no data home is a child
        # that cannot start - the machine's fault, and the file waits.
        self._scratch_root = scratch_root()
        self._pid: int | None = None
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
            target=_the_child, args=(jobs, sender, lifeline, processor_only, str(self._scratch_root)),
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
        self._pid = self._process.pid
        self._job_object = _kill_on_close_job(self._process.pid, memory_limit=self.memory_limit)
        #: Windows caps the child in its job object; everywhere else the
        #: pass watches (R31).
        self._watches_memory = sys.platform != "win32"

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
        kind, answer, begun, over, capped = "died", (), False, False, False
        while True:
            # Measured again after every message and every wake, on the
            # awake clock (decision 189): a wait the machine slept through
            # is not the file's time. Off Windows the wait is in slices of
            # MEMORY_WATCH_SECONDS, never longer than what is left, so the
            # watch cannot stretch the stop.
            left = started + stop - awake_clock()
            if left <= 0:
                over = True
                self.end()
                break
            if not self._answers.poll(min(left, MEMORY_WATCH_SECONDS) if self._watches_memory else left):
                if self._watches_memory and self._past_its_memory():
                    # Ended here, joined below with today's words: the
                    # whole tree, as a stop ends it.
                    capped = True
                    _end(self._process)
                    break
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
            if capped:
                error += self._memory_words()
            if not over:
                self.end()
            return Outcome("not_started", error=error, seconds=seconds)
        if over:
            return Outcome("stopped", seconds=seconds)
        self.served += 1
        if kind == "read":
            return Outcome("read", answer=answer[0], notes=answer[1], kept=answer[2],
                           seconds=seconds)
        if kind == "failed":
            return Outcome("failed", error=answer[0], message=answer[1], trace=answer[2],
                           notes=answer[3], kept=answer[4], seconds=seconds)
        error = f"the reading's process ended with exit code {self._exit_code()}"
        if capped or _job_memory(self._job_object)[1] >= self.memory_limit * 0.9:
            error += self._memory_words()
        self.end()
        return Outcome("died", error=error, seconds=seconds)

    def _memory_words(self) -> str:
        """The words a crash at the memory limit carries, on Windows and off."""
        return f"; it had reached its memory limit ({self.memory_limit / 1024**3:.0f} GB)"

    def _past_its_memory(self) -> bool:
        """Whether the child's memory is past ``memory_limit`` (R31). A
        footprint that cannot be read is no cap: said once on the error log
        (:data:`MEMORY_UNREADABLE`), never replaced by a guess - unless the
        child is simply gone, which is no news."""
        try:
            return _footprint(self._process.pid) > self.memory_limit
        except (OSError, ValueError, AttributeError) as exc:
            if self._process.is_alive():
                _say_once(MEMORY_UNREADABLE.format(reason=errors.error_class(exc)))
            return False

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
        if self._pid is not None and not self._process.is_alive():
            _remove_scratch(self._scratch_root / str(self._pid))
        if self._process.exitcode is not None:
            with contextlib.suppress(ValueError):
                self._process.close()


def _the_child(jobs, sender, lifeline, processor_only_: bool, scratch: str) -> None:
    """The child's whole life: serve jobs one at a time until the pass says
    it is done, or is gone.

    First it takes a temp folder of its own under ``scratch``
    (:func:`_take_scratch`, decision 186); a folder it cannot make ends it
    before "started", as a job it cannot unpack does. On POSIX it leads a process group of its own first, so ending it ends
    whatever it started. It watches its lifeline from a thread of its own
    (:func:`_watch_the_pass`). For each job it says "started" before
    anything touches the file - an end before it is the machine's, after it
    the file's - and hands back the answer, or what the job raised as
    words, never left to end the process in silence. Every answer carries
    what the reader has to tell the pass (:func:`take_notes`)."""
    # Every keep in this process travels back with an answer, and none is
    # logged here: the child never opens a log (decision 190, Part 4).
    errors.keep_for_the_parent()
    try:
        _take_scratch(Path(scratch))
    except OSError:
        os._exit(UNREADABLE_JOB_EXIT_CODE)      # the machine's, never the file's
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
                                 traceback.format_exc(), take_notes(), errors.take_kept()))
                if isinstance(exc, MemoryError):
                    # Past its memory limit: said, and done - the pass
                    # replaces it (SPEC-169 section 9).
                    os._exit(OUT_OF_MEMORY_EXIT_CODE)
            else:
                _answer(sender, ("read", answer, take_notes(), errors.take_kept()))
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


#: The memory limit's warnings already said by this process (R31's "once").
_SAID: set[str] = set()


def forget_said() -> None:
    """Forget the memory-limit warnings this process has said (P276), so the
    next ``_say_once`` says them again. The app's engine answers many commands
    in one process; a process per command said each of the reader's warnings
    once per command, and the engine calls this before each command to keep
    its error log reading the same."""
    _SAID.clear()


def _say_once(words: str) -> None:
    """Put ``words`` on the error log the first time this process has them."""
    if words not in _SAID:
        _SAID.add(words)
        log.warning("%s", words)


#: libproc's number for the rusage record carrying ``ri_phys_footprint``.
_RUSAGE_INFO_V2 = 2


def _libproc():
    """The library holding ``proc_pid_rusage``: a macOS system library,
    named apart so a test can hand the watch one of its own."""
    import ctypes

    return ctypes.CDLL("libSystem.dylib", use_errno=True)


def _rusage_info_v2():
    """libproc's ``rusage_info_v2``, whose field after ``ri_resident_size``
    is ``ri_phys_footprint`` - what Activity Monitor calls Memory."""
    import ctypes

    class RusageInfoV2(ctypes.Structure):
        _fields_ = [("ri_uuid", ctypes.c_uint8 * 16)] + [
            (name, ctypes.c_uint64) for name in (
                "ri_user_time", "ri_system_time", "ri_pkg_idle_wkups", "ri_interrupt_wkups",
                "ri_pageins", "ri_wired_size", "ri_resident_size", "ri_phys_footprint",
                "ri_proc_start_abstime", "ri_proc_exit_abstime", "ri_child_user_time",
                "ri_child_system_time", "ri_child_pkg_idle_wkups", "ri_child_interrupt_wkups",
                "ri_child_pageins", "ri_child_elapsed_abstime", "ri_diskio_bytesread",
                "ri_diskio_byteswritten")]

    return RusageInfoV2


def _darwin_footprint(pid: int) -> int:
    """A process's physical footprint in bytes on macOS, from
    ``proc_pid_rusage(pid, RUSAGE_INFO_V2)`` through ``ctypes`` (R31).
    ``ri_phys_footprint`` rather than the resident size: it is the figure
    Activity Monitor shows as Memory, and counts compressed pages the
    resident size forgets. ``setrlimit(RLIMIT_AS)`` was rejected: macOS does
    not honour it reliably. Raises OSError for a process that cannot be read."""
    import ctypes

    info = _rusage_info_v2()()
    libproc = _libproc()
    libproc.proc_pid_rusage.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_void_p)
    if libproc.proc_pid_rusage(pid, _RUSAGE_INFO_V2, ctypes.byref(info)) != 0:
        raise OSError(ctypes.get_errno(), f"proc_pid_rusage refused process {pid}")
    return info.ri_phys_footprint


def _linux_footprint(pid: int) -> int:
    """A process's resident memory in bytes on Linux: the second field of
    ``/proc/<pid>/statm`` (resident pages) times the page size (R31).
    Raises OSError for a process that is gone, ValueError for a file that
    is not a statm."""
    fields = Path(f"/proc/{pid}/statm").read_text(encoding="ascii").split()
    return int(fields[1]) * os.sysconf("SC_PAGE_SIZE")


def _footprint(pid: int, system: str = sys.platform) -> int:
    """The memory ``pid`` holds, in bytes (R31). ``system`` is the seam a
    test hands a platform's name; a platform with no reader raises OSError,
    which the watch turns into "no cap, said once" rather than a guess."""
    if system == "darwin":
        return _darwin_footprint(pid)
    if system.startswith("linux"):
        return _linux_footprint(pid)
    raise OSError(f"no way to read a process's memory on {system}")


def _end(process) -> None:
    """End a reading's child and everything it started, the whole tree."""
    if sys.platform == "win32":
        system = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32"
        try:
            subprocess.run([str(system / "taskkill.exe"), "/F", "/T", "/PID", str(process.pid)],
                           capture_output=True, timeout=CHILD_EXIT_SECONDS, check=False,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError, subprocess.SubprocessError) as exc:
            errors.keep("ocr", exc)
            log.warning("Could not end the reading's process tree (%s)", errors.error_class(exc))
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
                # (decision 190) - except a data home the firm's own settings
                # refused (decision 186), whose sentence is the firm's.
                errors.keep("ocr: the reading child could not be made", exc)
                return Outcome("not_started", error=errors.said(exc, (SettingsError,)),
                               seconds=awake_clock() - started), None
        child = self.child
        outcome = child.run(job, args, kwargs, stop, since=started if fresh else None)
        self.hear(outcome.notes)
        # The child keeps nothing itself: what it kept crossed with its
        # answer, and lands on this process's debug log (decision 190, Part 4).
        for entry in outcome.kept:
            errors.keep("ocr: the reading child", entry)
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
