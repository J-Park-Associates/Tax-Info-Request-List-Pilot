"""The reader bench: which reading settings help on the firm's own paper (P283, P285).

The firm's own pre-processing notes end with the open item "how to measure
which steps actually help". This tool is that measurement. It reads a folder
of already-sorted documents once per combination of settings - the dots per
inch a page is drawn at, the confidence floor, the page prepared or raw, the
small or the medium models - and writes down, in counts and seconds only, how
many landed where a person had put them and how long each took. The product
reads prepared (P285): a page is drawn at 300 dots per inch, turned level,
made black and white, cleared of specks and of a form's box lines, in memory
(:func:`tracker.ocr.prepared`). **Raw** is the reading before P285 - 144
dots per inch, no step (:data:`tracker.ocr.RAW`) - and the 300 dpi raw rows
are P283's reading at the sharper render, so P285 needs no second checkout:
its "before" is on the same code. The settings live in
:class:`tracker.ocr.ReaderSettings`, the product reads with the shipped ones,
and :func:`tracker.ocr.use_settings` is for this tool and the suite. P284
ships whatever the office numbers favour, in a SPEC of its own, now choosing
among prepared settings.

**It reads in its own process, and that is the whole reason it cannot use
the backtest's reading.** A reading child imports :mod:`tracker.ocr` afresh,
at the shipped settings, so a setting changed in this process would never
reach it. For the whole run the bench therefore turns
``content_check.READ_IN_A_CHILD`` off (the switch the suite throws) and opens
``ocr.reading_session(in_a_child=False)`` around each variant, and puts both
back, and the settings, in a ``finally``. What that costs, said plainly:
the safety stop is still armed (no page starts after the one before it
overran 60 seconds or after the document's 600), but a page already under
way is unbounded, so a slow variant can park a multi-page scan through the
stop, and that counts as a park (a person is watching a measurement, not a
pass). The bench reads on the processor only
(``ocr.gpu_pack()`` is None run from source), which is the conservative
number for the firm's ceiling of 6 seconds a page.

**What it reuses from** ``tools/backtest.py``, imported by name, private
helpers included, so there is one owner of each: ``_harness`` (the suite's
reader of the expectations file and its catalog builder),
``_document_path``, ``_linked_under_a_neutral_name`` (every document read
through a hard link named ``document.<ext>``, so no client's file name
reaches the router or the report), ``_temp_pointed_at`` (what a library
writes through the temp folder lands in this process's scratch and goes
with the run), ``_outside_the_repository``, ``_corpus``, ``write_json``,
``_unknown_catalog`` (the sentence for a bad catalog column: a row number,
never the value), ``BacktestError`` and the ``READING_*`` kinds. A rename there
is a change to both files.

**The report is rewritten after every variant**, so a crash, an out-of-memory
or a Ctrl-C costs the variant under way and no earlier one. A variant whose
reading raised is in the report as not measured, with the exception's class
and never its message; the run goes on to the next. A Ctrl-C writes the
report so far and exits 130 with one sentence.

**The corpus** is a folder and its expectations file in the backtest's
format. Before any variant each document is linked once and read once with
OCR withheld (:func:`tracker.content_check.extract`). A document with a
usable text layer is counted and never routed again - the reader's settings
cannot change it. The rest are the scans (a PDF with no usable text) and the
photos (an image extension), whose pages are counted once (capped at
``content_check.MAX_PAGES``; a photo is one page; a PDF the page counter
cannot open counts as one, and the router parks it whatever the settings).
A document that is neither - one no extractor reads, or whose reading
failed - is in the document count and in none of the three kinds: no setting
changes what becomes of it and nothing is read for it.

**The variants** are a fixed grid (:func:`grid`): every combination of
:data:`DPIS`, :data:`FLOORS`, :data:`PREPS` and :data:`TIERS` (2 x 2 x 2 x 2 =
16), then the **ablation**: the shipped settings at 300 dpi, floor 0.5, small
models, with one step turned off, or Otsu's threshold in Sauvola's place
(:data:`ABLATIONS`, 5 rows) - 21 in all, which say which step earns its place.
A name is ``dpi<d>-floor<f>-<prep>-<tier>``, ``<prep>`` being ``prep``,
``raw`` or ``prep-<ablation>``; the shipped one, ``dpi300-floor0.50-prep-small``,
is always measured first. A ``prep`` variant is built from
:data:`tracker.ocr.SHIPPED`, a ``raw`` one from :data:`tracker.ocr.RAW`, so
``dpi144-floor0.50-raw-small`` is exactly the reading before P285 in its
settings and pixels, but not in the detector's own setting (``Det.limit_type``
``"max"``, 9.1), which is the engine's and not a field: the detector no longer
enlarges a page whose shorter side is under 736 px, which P283's default did;
measured on drawn pages the same words are read. A variant's
long side is ``max(2000, ceil(11 * dpi))``, a letter page's long side at that
dpi, so 300 dpi is not silently shrunk back to 182 by the reader. The medium
models are never shipped and never fetched: a person puts them in a folder
(``--models``), and a variant for them without the folder, or with a file
missing, is in the report as not measured with :data:`MEDIUM_NOT_MEASURED`.
``ocr._refuse_downloads`` stands under the bench, and it calls nothing of
rapidocr's downloader.

**Each routing is scored** against what a person did, in four outcomes
(:func:`outcome_of`): ``right`` (it filed under the expected row, or the
row is meant to park and parked), ``parked_shortlist`` (parked, with the
expected row among the leads a review card offers), ``parked_no_lead``
(parked, with no lead) and ``wrong`` (it filed, and not under the expected
row). "Filed under" is the routing's own identifier, as the backtest scores
it. Seconds are the reading's own (``Routing.seconds``), per document and
per page, against the ceiling of :data:`CEILING_SECONDS_PER_PAGE`.

**Nothing identifying leaves this tool.** The report and the printed table
hold counts and seconds, the variants' settings (never the models folder)
and the routing codes parked documents carry; no document name, folder
below the corpus, row number, word of a document or path. ``review-codes``
holds to the same rule for what the ``firm`` command prints, reply and stderr
alike, and says a refusal by its kind alone.

::

    python tools/reader_bench.py variants
    python tools/reader_bench.py run <folder> --out <report> [--expectations <file>]
           [--models <folder>] [--dpi 300,144] [--floor 0.5,0.7] [--prep prep,raw]
           [--ablation on|off] [--tier small,medium]
    python tools/reader_bench.py review-codes [--out <file>]
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import json
import math
import re
import shutil
import statistics
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))   # run as a script: the package and the suite must import

from tools.backtest import (  # noqa: E402
    EXPECTATIONS_FILENAME,
    READING_IMAGE,
    READING_OCR,
    BacktestError,
    _corpus,
    _document_path,
    _harness,
    _linked_under_a_neutral_name,
    _outside_the_repository,
    _temp_pointed_at,
    _unknown_catalog,
    write_json,
)
from tracker import content_check, errors, ocr, reasons  # noqa: E402
from tracker.router import route_file  # noqa: E402
from tracker.settings import process_scratch  # noqa: E402

SCHEMA_VERSION = 2
#: The grid: every combination of these four. The first of each is the
#: shipped value (``ocr.SHIPPED``), which is how the shipped variant is found.
#: 300 is the notes' target and the shipped dpi; 144 is P283's, so its raw
#: rows are the reading before P285.
DPIS = (300, 144)
FLOORS = (0.5, 0.7)
#: ``prep`` is ``ocr.SHIPPED``'s steps, ``raw`` is every step off.
PREPS = ("prep", "raw")
TIERS = ("small", "medium")
#: The ablation rows, each the shipped settings at 300 dpi, floor 0.5, small,
#: with one step off (or, for ``otsu``, Otsu in Sauvola's place).
ABLATIONS = ("no-deskew", "no-binarize", "otsu", "no-denoise", "no-delining")
#: A page of letter paper is 11 inches long: its long side at ``dpi``.
LETTER_LONG_SIDE_INCHES = 11
#: The long side no variant goes under (the raw reading's ``Global.max_side_len``).
MINIMUM_LONG_SIDE = 2000
#: Jason's ceiling (decision 127 D-2): 6 seconds a photo, 60 for a ten-page scan.
CEILING_SECONDS_PER_PAGE = 6.0

#: The four ways a routing is scored, in the order the report lists them.
RIGHT = "right"
PARKED_SHORTLIST = "parked_shortlist"
PARKED_NO_LEAD = "parked_no_lead"
WRONG = "wrong"
OUTCOMES = (RIGHT, PARKED_SHORTLIST, PARKED_NO_LEAD, WRONG)

#: What the report says of itself, and of a variant it could not measure.
BENCH_NOTE = ("How the reader's settings fared on the firm's own documents: counts and seconds only. "
              "No document name, no folder, no row number, no word of any document and no path is "
              "recorded here.")
MEDIUM_NOT_MEASURED = ("the medium models are not in a folder the bench was given; a person fetches "
                       "them with rapidocr download_models")
#: The code a parked routing carries when it carries none (never expected).
NO_CODE = "none"
#: What a code in a ``firm`` reply must look like to be printed: the
#: tracker's own codes are all lower-case words and digits joined by dashes.
CODE_SHAPE = re.compile(r"[a-z0-9][a-z0-9-]*")
#: Where ``review-codes`` counts a code that does not look like one.
OTHER_CODE = "other"

DPI_FLAG = "--dpi"
FLOOR_FLAG = "--floor"
PREP_FLAG = "--prep"
ABLATION_FLAG = "--ablation"
TIER_FLAG = "--tier"
MODELS_FLAG = "--models"
EXPECTATIONS_FLAG = "--expectations"
OUT_FLAG = "--out"


# ------------------------------------------------------------- the grid ----


@dataclass(frozen=True, slots=True)
class Variant:
    """One combination of settings, with the name the report knows it by."""

    name: str
    settings: ocr.ReaderSettings


def long_side(dpi: int) -> int:
    """The ``max_side_len`` a variant reads at: a letter page's long side at
    ``dpi``, never under the raw reading's 2000, so a sharper render is not
    shrunk back by the reader before detection."""
    return max(MINIMUM_LONG_SIDE, math.ceil(LETTER_LONG_SIDE_INCHES * dpi))


def name_of(dpi: int, floor: float, prep: str, tier: str) -> str:
    """``dpi300-floor0.50-prep-small``; ``prep`` is ``prep``, ``raw`` or
    ``prep-<ablation>``."""
    return f"dpi{dpi}-floor{floor:.2f}-{prep}-{tier}"


def _variant(dpi: int, floor: float, prep: str, tier: str, models: str = "") -> Variant:
    """A ``prep`` variant is the shipped settings, a ``raw`` one the reading
    before P285, each with the dpi, floor, long side and tier of its own."""
    settings = dataclasses.replace(
        ocr.RAW if prep == "raw" else ocr.SHIPPED, render_dpi=dpi, confident_score=floor,
        max_side_len=long_side(dpi), model_tier=tier, model_folder=models if tier != "small" else "")
    return Variant(name_of(dpi, floor, prep, tier), settings)


#: What each ablation changes in the shipped settings.
_ABLATION_CHANGES = {
    "no-deskew": {"deskew": False}, "no-binarize": {"binarize": "off"}, "otsu": {"binarize": "otsu"},
    "no-denoise": {"denoise": False}, "no-delining": {"delining": False}}


def _ablation(ablation: str) -> Variant:
    """The shipped variant with one step off (or Otsu for Sauvola)."""
    shipped = _variant(DPIS[0], FLOORS[0], PREPS[0], TIERS[0])
    return Variant(name_of(DPIS[0], FLOORS[0], f"{PREPS[0]}-{ablation}", TIERS[0]),
                   dataclasses.replace(shipped.settings, **_ABLATION_CHANGES[ablation]))


def grid(dpis=DPIS, floors=FLOORS, preps=PREPS, tiers=TIERS, *, ablation: bool = True,
         models: str = "") -> list[Variant]:
    """The variants of the chosen values, the shipped one always first.

    The shipped variant is in the list whatever the choice leaves out; the
    rest of the main grid follows in the order dpi, floor, prep, tier (the
    constants' order, whatever order the choice was given in), then the
    ablation rows in :data:`ABLATIONS`' order unless ``ablation`` is off.
    ``models`` is the folder a medium variant reads its models from."""
    shipped = _variant(DPIS[0], FLOORS[0], PREPS[0], TIERS[0])
    assert shipped.settings == ocr.SHIPPED, "the grid's first values must be the shipped settings"
    rest = [_variant(dpi, floor, prep, tier, models)
            for dpi, floor, prep, tier in itertools.product(DPIS, FLOORS, PREPS, TIERS)
            if dpi in dpis and floor in floors and prep in preps and tier in tiers]
    rows = [_ablation(name) for name in ABLATIONS] if ablation else []
    return [shipped, *(variant for variant in rest if variant.name != shipped.name), *rows]


def medium_models_in(folder: str) -> bool:
    """Whether ``folder`` holds both of the medium tier's model files."""
    if not folder:
        return False
    return all((Path(folder) / name).is_file() for name in ocr.MODEL_TIERS["medium"])


# ----------------------------------------------------------- the corpus ----


@dataclass(frozen=True, slots=True)
class Document:
    """One scan or photo of the corpus, linked under a neutral name."""

    link: Path
    kind: str                 # READING_OCR (a scan) or READING_IMAGE (a photo)
    pages: int
    items: list
    expected: str | None      # None: the document is meant to park


def _pages_of(link: Path, kind: str) -> int:
    """How many pages the reader reads of a scan: its pages up to
    ``content_check.MAX_PAGES``; a photo is one. A PDF that cannot be opened
    counts one: the router parks it whatever the settings."""
    if kind == READING_IMAGE:
        return 1
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(link)
        try:
            return max(1, min(len(document), content_check.MAX_PAGES))
        finally:
            document.close()
    except Exception:       # a count, never a reason to stop a night's run
        return 1


def survey(folder: Path, rows: list, scratch: Path) -> tuple[list[Document], dict]:
    """Link every document once, read it once with OCR withheld, and sort
    it: a usable text layer is counted and set aside, a scan or a photo is
    kept for the variants. Returns the kept documents and the corpus counts."""
    catalog_rows, _read = _harness()
    workspace = scratch / "catalogs"
    workspace.mkdir()
    built: dict = {}
    kept: list[Document] = []
    counts = {"documents": 0, "text_layer": 0, "scans": 0, "photos": 0, "pages": 0}
    for row, (name, catalog, year, expected) in enumerate(rows, start=1):
        counts["documents"] += 1
        link = _linked_under_a_neutral_name(_document_path(folder, name, row), scratch, row)
        reading = content_check.extract(link, ocr=False)
        if reading.needs_ocr:
            kind = (READING_IMAGE if content_check.extension_of(link) in content_check.IMAGE_EXTENSIONS
                    else READING_OCR)
            pages = _pages_of(link, kind)
            kept.append(Document(link, kind, pages, catalog_rows(workspace, catalog, year, built), expected))
            counts["photos" if kind == READING_IMAGE else "scans"] += 1
            counts["pages"] += pages
        elif reading.text is not None:
            counts["text_layer"] += 1
    return kept, counts


# ---------------------------------------------------------- the scoring ----


def outcome_of(expected: str | None, routing) -> str:
    """Which of :data:`OUTCOMES` ``routing`` is, against what a person did.

    ``expected`` None means the document is meant to park. The shortlist is
    what the review card offers: the routing's candidates and the keys of its
    evidence record (decision 140 included)."""
    if routing.identifier is not None:
        return RIGHT if routing.identifier == expected else WRONG
    if expected is None:
        return RIGHT
    if expected in routing.candidates or expected in routing.evidence_record:
        return PARKED_SHORTLIST
    return PARKED_NO_LEAD


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def _worst(values: list[float]) -> float | None:
    return round(max(values), 3) if values else None


def _settings_of(variant: Variant) -> dict:
    """The settings the report states: never the models folder."""
    settings = variant.settings
    return {"render_dpi": settings.render_dpi, "confident_score": settings.confident_score,
            "max_side_len": settings.max_side_len, "deskew": settings.deskew,
            "binarize": settings.binarize, "denoise": settings.denoise,
            "delining": settings.delining, "model_tier": settings.model_tier}


def _unmeasured(variant: Variant, note: str) -> dict:
    return {"name": variant.name, "settings": _settings_of(variant), "measured": False, "note": note}


def measure(variant: Variant, documents: list[Document], first_load: float) -> dict:
    """One variant's entry of the report: each document routed with no
    reading handed in, so the router reads it - OCR, in this process, under
    the variant's settings - and applies its own rule, P282's included;
    no verdict cache, so nothing is kept between variants."""
    outcomes: Counter = Counter()
    parked: Counter = Counter()
    ocr_only = 0
    per_page: list[float] = []
    by_kind: dict[str, list[float]] = {READING_OCR: [], READING_IMAGE: []}
    for document in documents:
        routing = route_file(document.link, document.items)
        outcomes[outcome_of(document.expected, routing)] += 1
        if routing.identifier is None:
            parked[routing.code or NO_CODE] += 1
        if routing.code == reasons.OCR_ONLY_CODE:
            ocr_only += 1
        by_kind[document.kind].append(routing.seconds)
        per_page.append(routing.seconds / document.pages)
    read = len(documents)
    return {
        "name": variant.name, "settings": _settings_of(variant), "measured": True, "note": "",
        "outcomes": {name: outcomes[name] for name in OUTCOMES},
        "ocr_only": ocr_only,
        "ocr_only_share": round(ocr_only / read, 4) if read else None,
        "parked_by_code": dict(sorted(parked.items())),
        "seconds": {
            "first_load": round(first_load, 3),
            "per_page_median": _median(per_page), "per_page_worst": _worst(per_page),
            "scan_median": _median(by_kind[READING_OCR]), "scan_worst": _worst(by_kind[READING_OCR]),
            "photo_median": _median(by_kind[READING_IMAGE]), "photo_worst": _worst(by_kind[READING_IMAGE]),
            "over_ceiling": sum(1 for seconds in per_page if seconds > CEILING_SECONDS_PER_PAGE),
        },
    }


# ------------------------------------------------------------ the table ----

_TABLE_HEAD = (f"{'variant':<42}{'right':>7}{'shortlist':>11}{'no lead':>9}{'wrong':>7}"
               f"{'ocr only':>10}{'s/page med':>12}{'s/page worst':>14}{'over ceiling':>14}")


def table_row(entry: dict) -> str:
    """One variant as a line of the printed table: numbers and its name only."""
    if not entry["measured"]:
        return f"{entry['name']:<42}  not measured"
    outcome, seconds = entry["outcomes"], entry["seconds"]

    def said(value):
        return "-" if value is None else f"{value:.2f}"

    return (f"{entry['name']:<42}{outcome[RIGHT]:>7}{outcome[PARKED_SHORTLIST]:>11}"
            f"{outcome[PARKED_NO_LEAD]:>9}{outcome[WRONG]:>7}{entry['ocr_only']:>10}"
            f"{said(seconds['per_page_median']):>12}{said(seconds['per_page_worst']):>14}"
            f"{seconds['over_ceiling']:>14}")


# ------------------------------------------------------------- the run ----


def run_bench(folder: Path, expectations: Path, variants: list[Variant], *, models: str = "",
              out=None, report_to: Path | None = None) -> dict:
    """Measure every variant on the corpus and return the report.

    The reading is in this process (see the module's text): the switch, the
    session and the settings are put back however the run ends. Each
    variant's row is printed to ``out`` (standard output by default) the
    moment it is measured, so a long run shows its progress, and the report
    is rewritten to ``report_to`` at the same moment: an abort, an
    out-of-memory or a Ctrl-C costs the variant under way and no earlier one.
    A Ctrl-C writes the report so far and is raised again."""
    stream = out or sys.stdout
    write = stream.write
    _catalog_rows, read_expectations = _harness()
    try:
        rows = read_expectations(expectations)
    except ValueError as exc:
        raise BacktestError(str(exc)) from None     # the reader's sentences name a row, never a file
    if (unknown := _unknown_catalog(rows)):
        raise BacktestError(unknown)

    entries: list[dict] = []
    report: dict = {}
    previous_switch = content_check.READ_IN_A_CHILD
    previous_settings = ocr.SETTINGS
    own = process_scratch()
    own.mkdir(parents=True, exist_ok=True)
    try:
        content_check.READ_IN_A_CHILD = False
        with _temp_pointed_at(own), tempfile.TemporaryDirectory(prefix="bench-", dir=own) as scratch_name:
            documents, corpus = survey(folder, rows, Path(scratch_name))
            report = {"schema": SCHEMA_VERSION, "note": BENCH_NOTE, "corpus": corpus, "variants": entries}
            write(_TABLE_HEAD + "\n")
            try:
                for variant in variants:
                    entry = _one_variant(variant, documents, models)
                    entries.append(entry)
                    write(table_row(entry) + "\n")
                    stream.flush()
                    if report_to is not None:
                        write_json(report_to, report)
            except KeyboardInterrupt:
                if report_to is not None:
                    write_json(report_to, report)
                raise
    finally:
        content_check.READ_IN_A_CHILD = previous_switch
        ocr.use_settings(previous_settings)
        shutil.rmtree(own, ignore_errors=True)    # a folder still held is swept later by its dead pid
    return report


def _one_variant(variant: Variant, documents: list[Document], models: str) -> dict:
    """:func:`measure` for one variant, or why it was not measured: a medium
    variant with no models, a reader that could not be built, or a reading
    that raised - said by the exception's class and never its message, which
    could carry a path - so the run goes on to the next variant."""
    if variant.settings.model_tier == "medium" and not medium_models_in(models):
        return _unmeasured(variant, MEDIUM_NOT_MEASURED)
    ocr.use_settings(variant.settings)
    with ocr.reading_session(in_a_child=False):
        started = time.perf_counter()
        try:
            ocr.warm_up()
        except ocr.ReaderUnavailable as exc:
            return _unmeasured(variant, errors.error_class(exc, with_code=False))
        except Exception as exc:
            return _unmeasured(variant, f"the reader stopped with {errors.error_class(exc, with_code=False)}")
        try:
            return measure(variant, documents, time.perf_counter() - started)
        except Exception as exc:
            return _unmeasured(variant, f"the reading stopped with {errors.error_class(exc, with_code=False)}")


# ---------------------------------------------------------- review-codes ----


#: What ``review-codes`` says when the firm command gives it nothing to count.
#: Every sentence is by kind and exit code only (P286): ``firm`` names folders in
#: its own sentences, so none of its words is ever quoted.
FIRM_NOT_STARTED = "the firm command could not start ({kind}); nothing was counted"
FIRM_TOO_LONG = "the firm command gave no reply within {minutes} minutes and was stopped; nothing was counted"
FIRM_NO_REPLY = "the firm command printed no reply (exit {code}); nothing was counted"
FIRM_NOT_AN_OBJECT = "the firm command's reply is not a JSON object (exit {code}); nothing was counted"
FIRM_REFUSED = ("the tracker refused the firm summary ({kind}, exit {code}); the app's Overview says why, "
                "and an unexpected failure is in the tracker's error log")
FIRM_STDERR_ON_FAILURE = " (it also wrote {lines} on stderr, not shown)"
FIRM_STDERR_ON_SUCCESS = "the firm command also wrote {lines} on stderr, not shown"
#: The kind of a refusal whose envelope carries none of ``progress.FAILURE_KINDS``.
UNKNOWN_KIND = "unknown"


def _lines(n: int) -> str:
    """``1 line`` or ``n lines``: what the stderr suffixes count."""
    return "1 line" if n == 1 else f"{n} lines"


def _run_firm():
    """Start ``python -m tracker.api firm`` as the cache fill does
    (``runner.fill_firm_cache``): input closed, so the page spec it reads to
    the end of its input is empty and the reply is the whole one (P278); the
    current environment, so the person's settings and data folders reach it;
    the repository as its folder; under the fill's time limit. Unlike the
    fill, stdout and stderr are kept, and only the bench reads them. Returns
    the finished process, or raises :class:`BacktestError` by kind."""
    import subprocess

    from tracker import runner
    try:
        return subprocess.run([sys.executable, "-m", "tracker.api", runner.FIRM_COMMAND],
                              stdin=subprocess.DEVNULL, capture_output=True, cwd=ROOT,
                              timeout=runner.FILL_TIME_LIMIT_SECONDS,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise BacktestError(FIRM_TOO_LONG.format(minutes=runner.FILL_TIME_LIMIT_SECONDS // 60)) from None
    except OSError as exc:
        raise BacktestError(FIRM_NOT_STARTED.format(kind=errors.error_class(exc))) from None


def _json_object_of(line: bytes) -> dict | None:
    """The line as a JSON object, or None when it is not one."""
    try:
        value = json.loads(line.decode("utf-8"))
    except ValueError:      # UnicodeDecodeError and JSONDecodeError are both ValueErrors
        return None
    return value if isinstance(value, dict) else None


def firm_reply_of(stdout: bytes, returncode: int) -> dict:
    """The ``firm`` command's reply out of its stdout, by the progress
    contract (``tracker/progress.py``): a line that is a JSON object under
    :data:`progress.PROGRESS_KEY` is a count line (none on a warm cache, two
    or more on a cold one) and is ignored; the reply is the last line left.
    Blank lines are ignored, and a Windows ``\\r\\n`` is no part of a line.
    Raises :class:`BacktestError`, saying what happened by kind and exit code
    and never by a word of the output, when there is no reply, it is not a
    JSON object, or it is a refusal (a ``failure`` or ``error``, or a
    nonzero exit)."""
    from tracker import progress
    lines = [line for line in stdout.splitlines() if line.strip()]
    rest = [line for line in lines if not ((obj := _json_object_of(line)) and progress.PROGRESS_KEY in obj)]
    if not rest:
        raise BacktestError(FIRM_NO_REPLY.format(code=returncode))
    reply = _json_object_of(rest[-1])
    if reply is None:
        raise BacktestError(FIRM_NOT_AN_OBJECT.format(code=returncode))
    if "failure" in reply or "error" in reply or returncode != 0:
        failure = reply.get("failure")
        kind = failure.get("kind") if isinstance(failure, dict) else None
        raise BacktestError(FIRM_REFUSED.format(kind=kind if kind in progress.FAILURE_KINDS else UNKNOWN_KIND,
                                                code=returncode))
    return reply


def review_codes(reply: object) -> dict[str, int]:
    """Needs Review, counted by code, from the ``firm`` command's reply:
    the codes of its ``files`` list - the rows waiting for a person - and
    nothing else. A code that does not look like one of the tracker's is
    counted as :data:`OTHER_CODE`, so no sentence, name or path in a reply
    can be carried into the counts."""
    files = reply.get("files") if isinstance(reply, dict) else None
    if not isinstance(files, list):
        raise BacktestError("the firm command's reply holds no list of files")
    counted: Counter = Counter()
    for one in files:
        code = one.get("code") if isinstance(one, dict) else None
        counted[code if isinstance(code, str) and CODE_SHAPE.fullmatch(code) else OTHER_CODE] += 1
    return dict(sorted(counted.items()))


# ----------------------------------------------------------------- CLI ----


def _chosen(text: str, allowed: tuple, convert, flag: str) -> tuple:
    """A comma list of values for ``flag``, each one of the grid's."""
    chosen = []
    for part in (piece.strip() for piece in text.split(",")):
        try:
            value = convert(part)
        except ValueError:
            raise BacktestError(f"{flag}: {part!r} is not one of {', '.join(map(str, allowed))}") from None
        if value not in allowed:
            raise BacktestError(f"{flag}: {part!r} is not one of {', '.join(map(str, allowed))}")
        chosen.append(value)
    return tuple(chosen)


def _on_or_off(text: str) -> bool:
    if text not in ("on", "off"):
        raise BacktestError(f"{ABLATION_FLAG}: {text!r} is not one of on, off")
    return text == "on"


def _models_of(ns: argparse.Namespace) -> str:
    """The folder ``--models`` names, or "" (``variants`` has no such flag)."""
    models = getattr(ns, "models", "")
    return str(Path(models).expanduser()) if models else ""


def _variants_of(ns: argparse.Namespace) -> list[Variant]:
    return grid(
        _chosen(ns.dpi, DPIS, int, DPI_FLAG), _chosen(ns.floor, FLOORS, float, FLOOR_FLAG),
        _chosen(ns.prep, PREPS, str, PREP_FLAG), _chosen(ns.tier, TIERS, str, TIER_FLAG),
        ablation=_on_or_off(ns.ablation), models=_models_of(ns))


def _cmd_variants(ns: argparse.Namespace) -> int:
    for variant in _variants_of(ns):
        print(variant.name)
    return 0


def _cmd_run(ns: argparse.Namespace) -> int:
    out = _outside_the_repository(Path(ns.out))     # before anything is read
    folder = _corpus(ns.folder)
    expectations = Path(ns.expectations).expanduser() if ns.expectations else folder / EXPECTATIONS_FILENAME
    if not expectations.is_file():
        raise BacktestError(f"no expectations file at {expectations}; write one with the backtest's collect command")
    run_bench(folder, expectations, _variants_of(ns), models=_models_of(ns), report_to=out)
    print(f"\nWrote {out}")
    return 0


def _cmd_review_codes(ns: argparse.Namespace) -> int:
    out = _outside_the_repository(Path(ns.out)) if ns.out else None   # before firm's wait, as `run` does
    done = _run_firm()
    wrote = len([line for line in done.stderr.splitlines() if line.strip()])
    try:
        counts = review_codes(firm_reply_of(done.stdout, done.returncode))
    except BacktestError as exc:
        raise BacktestError(str(exc) + (FIRM_STDERR_ON_FAILURE.format(lines=_lines(wrote)) if wrote else "")) from None
    print(json.dumps(counts, indent=1, sort_keys=True))
    if wrote:
        print(f"reader bench: {FIRM_STDERR_ON_SUCCESS.format(lines=_lines(wrote))}", file=sys.stderr)
    if out:
        write_json(out, counts)
    return 0


def _restrictions(command: argparse.ArgumentParser) -> None:
    command.add_argument(DPI_FLAG, default=",".join(map(str, DPIS)), help="dots per inch, comma list")
    command.add_argument(FLOOR_FLAG, default=",".join(map(str, FLOORS)), help="confidence floors, comma list")
    command.add_argument(PREP_FLAG, default=",".join(PREPS),
                         help="prep (the shipped steps), raw (every step off), or prep,raw")
    command.add_argument(ABLATION_FLAG, default="on",
                         help="on: also measure the shipped settings with one step off, five rows; off: leave them out")
    command.add_argument(TIER_FLAG, default=",".join(TIERS), help="model tiers: small, medium")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    variants = sub.add_parser("variants", help="the grid's names, one a line")
    _restrictions(variants)

    run = sub.add_parser("run", help="read the corpus once per variant and count where each landed")
    run.add_argument("folder", help="the folder holding the firm's sorted documents")
    run.add_argument(OUT_FLAG, required=True, help="write the report here, outside the repository")
    run.add_argument(EXPECTATIONS_FLAG, default="",
                     help=f"the expectations file (default: {EXPECTATIONS_FILENAME} in the folder)")
    run.add_argument(MODELS_FLAG, default="", help="a folder holding the medium models")
    _restrictions(run)

    codes = sub.add_parser("review-codes", help="count Needs Review by code; runs the firm command itself")
    codes.add_argument(OUT_FLAG, default="", help="also write the counts here, outside the repository")

    ns = parser.parse_args(argv)
    commands = {"variants": _cmd_variants, "run": _cmd_run, "review-codes": _cmd_review_codes}
    try:
        return commands[ns.command](ns)
    except BacktestError as exc:
        print(f"reader bench: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("reader bench: interrupted; the variants measured so far are in the report", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
