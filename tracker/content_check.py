"""Tier-3 content validation for the tracker (component 4).

Extracts text from client documents (read-only) and applies the deterministic
rules from the manifest row: Required Keywords (ALL must appear), Any
Keywords (at least ONE), and Date Pattern (regex). No rule logic is
hardcoded — everything comes from the manifest.

Extractors by extension:

- ``.pdf``            → pdfplumber, first ``MAX_PAGES`` pages only; if the
                        PDF has no text layer (a scan), fall back to OCR
                        (decision 169: RapidOCR through :mod:`tracker.ocr`,
                        with its models shipped in the app, so the reader
                        runs on every machine). When it cannot - a model
                        missing or broken - the file is reported as
                        unverifiable with a clear note, and nothing breaks.
- ``XLSX_EXTENSIONS``   → openpyxl (all sheets, cached formula values);
                        date cells are rendered in both ISO (2025-12-31)
                        and US (12/31/2025) forms so either pattern style
                        matches.
- ``TEXT_EXTENSIONS``   → plain text (utf-8, then cp1252 fallback).
- anything else       → no extractor; reported unverifiable, for a person (``reasons.UNCHECKABLE_TYPE``).

**One way of reading a document.** :func:`extract` is what both the router
(deciding where a drop goes) and the scanner (deciding a row's status) call,
so the two can never disagree about what a file says. The router asks for
the text layer and, for a scan or a photo, the reader; OCR's words are read
under decision 50 as P282 revised it (:mod:`tracker.router` says how); the
scanner always finishes the job.

**One place the words are judged** (decision 189). The pass never holds a
document's words: :func:`judge` reads the file and asks it every rule, form
scan and name the pass will want, in the pass's reader child and under the
document's stop, and hands back a :class:`Judgment` that carries no word
of the document. A text that makes a rule crawl - a typed Date Pattern
that backtracks, a one-line workbook - costs one stop and parks its file;
before, the rules ran in the pass's own process, where nothing could stop
them. The verdicts are the ones the pass reached itself, answer for
answer, which is why :data:`tracker.verdicts.CACHE_VERSION` did not move.

The judgment's shapes - what a reading says (:class:`Extraction`), the
questions the pass asks and the :class:`Judgment` that crosses back from
the reading's child - and the verdict cache that keeps a judgment's
verdicts in the store (:class:`ContentCache`, decision 107) live in
:mod:`tracker.verdicts` since P337.

:class:`Evidence` itself, the rule and place vocabularies and the cell format
it is written into live in :mod:`tracker.records` since decision 100 - they
are the shape of a verdict, not the reading of a document. This module
imports the ones it writes into a verdict, and a reader imports them from
there (P322).

The matcher and the rules a reading is judged by - a keyword said whole, a
form's number and its variants, which forms a page counts as its own, and
the keyword and date rules with their verdict, :class:`ContentResult` -
live in :mod:`tracker.keywords` since P336.
"""

from __future__ import annotations

import logging
import time
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import cast

from tracker import errors, ocr, reasons

# The matcher and the rules live in tracker/keywords.py (P336). This module
# imports back what its own code reads - the rules' verdict, the questions a
# judgment answers and the fingerprint the cache is keyed by - and offers
# none of them on: every other reader imports them from tracker.keywords.
from tracker.keywords import (
    ContentResult,
    any_keyword_matched,
    carries_a_1099b_section,
    dominant_forms,
    evaluate_rules,
    has_content_rules,
    own_forms,
    required_matched,
    rules_fingerprint,
    self_named_forms,
)
from tracker.manifest import RequestItem

# The Evidence record and the cell format it is written in live in
# tracker/records.py (decision 100): they are the shape of a verdict, not the
# reading of a document. This module imports the page break it counts pages
# by; Evidence, which a kept verdict's evidence is rebuilt as, is the verdict
# cache's (tracker/verdicts.py), and the rules and places a verdict says it
# rested on are the matcher's (tracker/keywords.py). It offers none of them
# on (P322).
from tracker.records import PAGE_BREAK
from tracker.validators import (
    IMAGE_EXTENSIONS,
    PDF_EXTENSION,
    TEXT_READ_CAP_MB,
    extension_of,
    open_test,
    picture_too_large_reason,
    said_extension,
    too_large_reason,
)

# The judgment's shapes and the verdict cache live in tracker/verdicts.py
# (P337). This module imports back what its own code reads - the reading's
# shape, the questions a judgment answers, the judgment itself and the cache
# a check consults - and offers none of them on: every other reader imports
# them from tracker.verdicts.
from tracker.verdicts import (
    ContentCache,
    Extraction,
    Judgment,
    NameQuestion,
    Questions,
    RowJudgment,
    RowQuestion,
    row_question,
    unjudged,
)

log = logging.getLogger("tracker.content_check")

# pdfplumber/pdfminer warn loudly on ugly-but-parseable PDFs; failures are
# already surfaced through ContentResult.reason.
logging.getLogger("pdfminer").setLevel(logging.ERROR)

#: A "text" PDF with fewer stripped characters than this *per page read*
#: is a scan: what little it has is a scanner's stamp ("Scanned by
#: CamScanner", "Page 1 of 2"), not the document, and is not read as one.
#: Pages are counted from the page breaks ``_extract_pdf`` writes.
_MIN_TEXT_CHARS = 25

#: Read at most this many pages of any PDF, with or without OCR. The words
#: that identify a document - its form number, the tax year, the payer -
#: are on its first pages; a 500-page general ledger dropped by a client
#: used to be read cover to cover on every route and scan, and that is what
#: stalled a run. A keyword deep in a long document is not evidence the
#: router should be acting on anyway.
MAX_PAGES = 10
#: The other file types whose text can be read (PDF_EXTENSION is the third).
XLSX_EXTENSIONS = ("xlsx", "xlsm")
TEXT_EXTENSIONS = ("csv", "tsv", "txt")
#: The most pixels one page or one photo is read at (decision 137, B1).
#: Rendering has to stay bounded: a PDF page may be 14,400 points square,
#: which at the old fixed scale of 2 is some 830 million pixels, and
#: ``bitmap.to_pil()`` hands Pillow an image without its decompression-bomb
#: guard ever being asked. Forty million is a letter page at about 600 dpi -
#: far past what the reader needs - so an ordinary page is read exactly as
#: before, and a giant one is read smaller rather than refused.
PIXEL_BUDGET = 40_000_000
#: The reader's safety stop (decision 137, B1.2; the owner's Q-1 of
#: 2026-09-24): ten times the ceiling he approved for decision 127 (6 s a
#: photo, 60 s a ten-page scan). A page - a photo is one page - gets a
#: minute and a document ten, rendering included. A reading that reaches
#: either is **abandoned**: a kept verdict, ``reasons.READING_STOPPED``,
#: not read again until the file changes. Under the stop nothing changes:
#: a slow reading is finished and named (``runner.SLOW_READING_SECONDS``).
#: Before this, the only stop was Task Scheduler's two-hour kill, which
#: ended the whole pass and met the same file again next time. Since
#: decision 150 the same two numbers bound the **whole** reading as well -
#: text layer, render and OCR - because the pass reads in a child process
#: it ends at the stop (:func:`judge_bounded` since decision 189, which
#: judges there too): ten minutes a file, one a photo.
READING_STOP_PAGE_SECONDS = 60.0
READING_STOP_DOCUMENT_SECONDS = 600.0
#: The most text one reading hands back, in characters, whatever it read
#: (decision 178): the number of megabytes a text file is read to
#: (``validators.TEXT_READ_CAP_MB``), counted in characters, so no reading
#: of any kind says more than a text file may. The workbook reader had no
#: bound at all: a 14.7 KB ``.xlsx`` whose one shared string of ten million
#: characters sat in twenty cells read to two hundred million, and every
#: rule the pass then asked of it ran in the pass's own process, outside
#: the stop. A reading past it is cut there and marked ``cut``, as a text
#: file past its cap always was.
READING_CHAR_BUDGET = TEXT_READ_CAP_MB * 1024 * 1024
#: The only ways a zip's part may be packed for a reading to unpack it
#: (decision 178): stored, and deflated - what Windows, macOS, Excel and
#: every mail client write. The standard library bounds a deflated read at
#: the size asked for; a bzip2 or LZMA part it inflates a whole compressed
#: chunk at a time, so one 64 KB read of 905 bytes of bzip2 grew past 2 GB
#: before any count could stop it. A workbook is a zip and is held to the
#: same list (:func:`_extract_xlsx`), and so is an attached zip
#: (:mod:`tracker.containers`).
PACKINGS = (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
#: What a workbook packed any other way fails with.
UNKNOWN_PACKING = "a part of it is packed in a way only a person's zip program opens"


class UnknownPacking(ValueError):
    """A workbook packed a way :data:`PACKINGS` does not hold (decision
    178). Its message is the firm's own sentence (:data:`UNKNOWN_PACKING`),
    the one error a reading says in words rather than by its class
    (:func:`tracker.errors.said`, decisions 189 and 190)."""


#: The clock the stop reads: the awake clock every part of a reading's
#: stop reads (decision 189), so a machine that slept does not end a
#: reading it never gave any time to. A name of its own so the suite can
#: move it rather than wait ten minutes.
_clock = ocr.awake_clock



# ------------------------------------------------------------- judgment ----
#
# Decision 189. Everything that reads a client's words - the form scan, the
# rules, the name - runs where the reading ran: in the pass's one reader
# child, under the document's stop and the child's memory cap
# (:func:`judge`). So a typed Date Pattern that backtracks, or a one-line
# workbook the form scan crawls through, costs one stop and never the pass,
# and the pass holds no text. What crosses is the answer to the questions the
# pass asked (:class:`Judgment`), in the firm's own words - a row's keyword,
# a reason sentence, a form number the catalog knows, one of the firm's
# spellings - and never a word of the document.
#
# Each question is answered by the very function the rules always called, on
# the same text (``tests/test_content_check.py`` compares the two on the
# suite's corpus). Callers outside the pass - the command lines, the
# backtest, the vocabulary report - read and judge in their own process
# (:func:`judgment_of` on an :class:`Extraction`, or
# :func:`tracker.keywords.says` itself).


def judgment_of(reading: Extraction, questions: Questions) -> Judgment:
    """Judge ``reading`` against ``questions`` and let its words go.

    Where the words are judged: :func:`judge` calls this in the reader
    child, and a caller outside the pass that already holds a reading (the
    backtest, :func:`tracker.router.route_file` handed one) calls it in its
    own process. The questions are answered by the functions the pass
    called before decision 189, with the arguments it gave them, so every
    answer is the one the pass reached; what changed is the cost (the
    SPEC's two costs): :func:`dominant_forms` - a whole scan of the text -
    is read **once** and handed to every question that read it again for
    itself, :func:`self_named_forms` once for both :func:`own_forms` and
    the split, and the page's names are parsed once for every return
    (:func:`tracker.names.read_names`).
    """
    # A scan with no text layer, read without OCR, is no reading at all
    # (the router's words, decision 92): nothing of it is judged.
    base = unjudged(reading)
    if reading.text is None or reading.needs_ocr:
        return base
    words = reading.text
    dominant = dominant_forms(words)
    self_named = self_named_forms(words) if words else ()
    own = own_forms(self_named)
    rows: dict[RowQuestion, RowJudgment] = {}
    for question in questions.rows:
        if question in rows:
            continue
        item = question.as_item()
        rows[question] = RowJudgment(
            verdict=evaluate_rules(words, item, own if own is not None else dominant),
            required_matched=required_matched(words, item, dominant),
            any_matched=any_keyword_matched(words, item, dominant),
        )
    names: dict[NameQuestion, object] = {}
    if questions.names:
        # names never imports this module, so the call-time import here
        # closes no cycle; it stays at call time, as every import this
        # phase does not need to move does.
        from tracker.names import check_name, read_names

        page = read_names(words)
        for asked in questions.names:
            if asked not in names:
                names[asked] = check_name(words, asked.own, dict(asked.others), page=page)
    return replace(
        base,
        has_words=bool(words),
        own=frozenset(own) if own is not None else None,
        self_named=self_named,
        carries_1099b=bool(words) and carries_a_1099b_section(words, dominant),
        rows=rows,
        names=names,
    )


# ------------------------------------------------------------- extraction ----


def _extract_pdf(path: Path) -> str:
    import pdfplumber  # deferred: heavy import, only needed for PDFs

    parts: list[str] = []
    said = 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:MAX_PAGES]:
            parts.append(page.extract_text() or "")
            said += len(parts[-1]) + 1
            if _past_budget(said):
                break           # :func:`_extract` cuts it and says so
    return PAGE_BREAK.join(parts)


def _past_budget(said: int) -> bool:
    """Whether the parts read so far - ``said`` counts each part and the one
    character that joins it to the next - already make a reading longer than
    ``READING_CHAR_BUDGET``. A reader stops only then, so whatever it leaves
    unread always leaves the reading past the budget and :func:`_extract`
    marks it ``cut``. Stopping the moment ``said`` passed the budget left a
    reading exactly at the budget, with more to come, marked whole."""
    return said - 1 > READING_CHAR_BUDGET


def _extract_xlsx(path: Path) -> str:
    import datetime as dt

    from openpyxl import load_workbook

    # A sheet's row is a line and its cells are set apart by a tab: a
    # keyword's words may run across a row's cells ("Fixed Asset" beside
    # "Schedule") and never down its rows.
    with zipfile.ZipFile(path) as archive:
        if any(info.compress_type not in PACKINGS for info in archive.infolist()):
            raise UnknownPacking(UNKNOWN_PACKING)
    parts: list[str] = []
    said = 0
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            parts.append(str(ws.title))
            said += len(parts[-1]) + 1
            for row in ws.iter_rows(values_only=True):
                if _past_budget(said):
                    return "\n".join(parts)      # :func:`_extract` cuts it and says so
                cells: list[str] = []
                wide = said
                for value in row:
                    if value is None:
                        continue
                    if isinstance(value, (dt.datetime, dt.date)):
                        # Both forms, so ISO- and US-style patterns match.
                        d = value.date() if isinstance(value, dt.datetime) else value
                        cells.append(f"{d.isoformat()} {d.month}/{d.day}/{d.year}")
                    else:
                        cells.append(str(value))
                    # Asked after every cell, not only between rows: one row
                    # may hold 16,384 cells of 32,767 characters each.
                    wide += len(cells[-1]) + 1
                    if _past_budget(wide):
                        parts.append("\t".join(cells))
                        return "\n".join(parts)  # :func:`_extract` cuts it and says so
                if cells:
                    parts.append("\t".join(cells))
                    said += len(parts[-1]) + 1
    finally:
        wb.close()
    return "\n".join(parts)


def _text_cap_bytes() -> int:
    return TEXT_READ_CAP_MB * 1024 * 1024


def _is_cut(path: Path) -> bool:
    """Whether :func:`_extract_textfile` reads less than the whole file."""
    try:
        return path.stat().st_size > _text_cap_bytes()
    except OSError:
        return False


def _extract_textfile(path: Path) -> str:
    """The text of a ``.csv``/``.tsv``/``.txt``, **up to its first**
    ``TEXT_READ_CAP_MB`` (decision 137): enough for any real statement, and
    a file past it is read that far and no further. A UTF-8 character the
    cut split in two is left off rather than turning the whole reading
    into another encoding."""
    cap = _text_cap_bytes()
    with path.open("rb") as handle:
        raw = handle.read(cap + 1)
    cut = len(raw) > cap
    raw = raw[:cap]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        if cut and exc.start >= len(raw) - 3:
            try:
                return raw[:exc.start].decode("utf-8")
            except UnicodeDecodeError:
                pass
    try:
        return raw.decode("cp1252")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def extract_text(path: Path) -> str | None:
    """Extract the text layer from a supported file; None if no extractor exists.

    A photo comes back None **on purpose** (decision 127): an image has no
    text layer to extract, ever, and :func:`extract` reads that None as
    "this is a scan" rather than "no extractor for this type" - the one
    place the two answers have to be told apart.
    """
    extension = extension_of(path)
    if extension == PDF_EXTENSION:
        return _extract_pdf(path)
    if extension in XLSX_EXTENSIONS:
        return _extract_xlsx(path)
    if extension in TEXT_EXTENSIONS:
        return _extract_textfile(path)
    return None


class ReadingStopped(Exception):
    """A reading reached the safety stop (decision 137, B1.2). ``seconds``
    is how long it had been reading the file when it stopped."""

    def __init__(self, seconds: float):
        super().__init__(f"the reading stopped after {seconds:.0f} s")
        self.seconds = seconds


class _SafetyStop:
    """The time one document's reading may take: a document deadline and,
    within it, one page's (decision 137, B1.2)."""

    def __init__(self) -> None:
        self.started = _clock()
        self.deadline = self.started + READING_STOP_DOCUMENT_SECONDS
        self.page_deadline = self.deadline

    def page(self) -> None:
        """A page is about to start: none starts past the stop - the page
        before it overran its minute, or the document its ten (decision
        169, ruling 5; the reader takes no timeout of its own, so a page
        under way is bounded by the child's end at the document's stop).
        Then it has a minute, or what is left of the ten."""
        self.remaining()
        self.page_deadline = min(_clock() + READING_STOP_PAGE_SECONDS, self.deadline)

    def remaining(self) -> float:
        """Seconds left for the page now being read, or the stop."""
        left = self.page_deadline - _clock()
        if left <= 0:
            raise ReadingStopped(_clock() - self.started)
        return left


#: The stop of the reading under way, set by :func:`extract_by_ocr`. None
#: outside a reading (a test's call straight into a reader).
_STOP: _SafetyStop | None = None


def render_scale(width: float, height: float) -> float:
    """The scale a PDF page of ``width`` x ``height`` points is rendered at
    for OCR: the settings' dpi over 72 (``ocr.SETTINGS.render_dpi``, 300 as
    shipped, so 300/72), or less, so the page never passes :data:`PIXEL_BUDGET`
    (decision 137, B1), which stays the hard ceiling. At scale 1 a point is a
    pixel, so the budget over the page's own area is the square of the most
    it may be scaled by. Read at call time: the reader bench changes the
    settings between its variants (P283)."""
    area = max(float(width), 1.0) * max(float(height), 1.0)
    return min(ocr.SETTINGS.render_dpi / 72, (PIXEL_BUDGET / area) ** 0.5)


def _within_budget(image):
    """``image``, reduced to :data:`PIXEL_BUDGET` if it is larger (decision
    137, B1): a photo past it is read smaller, never refused."""
    pixels = image.width * image.height
    if pixels <= PIXEL_BUDGET:
        return image
    factor = (PIXEL_BUDGET / pixels) ** 0.5
    size = (max(1, int(image.width * factor)), max(1, int(image.height * factor)))
    return image.resize(size)


def _ocr_pdf(path: Path) -> str | None:
    """OCR the first pages of a PDF. None when the reader cannot run on
    this machine (:class:`tracker.ocr.ReaderUnavailable`: a model missing or
    broken) - a normal, reported condition, never an error.

    Each page is rendered at :func:`render_scale` of its own size (decision
    137), so no page is ever drawn past :data:`PIXEL_BUDGET`: an ordinary
    page at the settings' dpi (300 as shipped), a giant one smaller. It is read as it
    comes (decision 169, ruling 6): the reader keeps the words of a page
    scanned sideways, and nothing turns it. The pages are joined with a
    line break, not :data:`PAGE_BREAK`, as they always were (SPEC-127.2X
    D9.2): the footer and first-page rules read an OCR reading as one page.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return None

    parts: list[str] = []
    doc = pdfium.PdfDocument(path)
    try:
        for index in range(min(len(doc), MAX_PAGES)):
            if _STOP is not None:
                _STOP.page()              # no page starts past the stop
            page_of = doc[index]
            bitmap = page_of.render(scale=render_scale(*page_of.get_size()))
            if _STOP is not None:
                _STOP.remaining()         # the render counts against the budget
            parts.append(ocr.read_page(bitmap.to_pil().convert("RGB"), name=path.name))
    finally:
        doc.close()
    return "\n".join(parts)


def _ocr_image(path: Path) -> str | None:
    """OCR one photo. None when the reader cannot run on this machine.

    One photo is one page. The phone's own rotation flag is undone first
    (``exif_transpose``) - a photo held upright and recorded sideways is
    the commonest case there is, and EXIF alone settles it - and the photo
    is read as it then stands (decision 169, ruling 6).

    Nothing is written: the photo on disk is the client's original. The reader
    prepares the photo (:func:`tracker.ocr.prepared`, P285) in memory, as it
    does a scanned page; the dpi does not apply to a photo, whose pixels are
    what the phone took, and the preparation never enlarges it.

    Its size is checked against :data:`PIXEL_BUDGET` **before** it is
    decoded (decision 137): a JPEG past it is decoded smaller by its own
    decoder (``draft``), any other photo is reduced to the budget the moment
    it is decoded, and Pillow's own decompression-bomb guard stays on for
    both. A photo too large even for that is refused by Pillow rather than
    decoded, and that refusal is a kept "Too large to read" verdict for a
    person (:class:`TooLargeToRead`), not a retry every pass.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None

    try:
        with Image.open(path) as opened:
            if opened.width * opened.height > PIXEL_BUDGET and opened.format == "JPEG":
                factor = (PIXEL_BUDGET / (opened.width * opened.height)) ** 0.5
                opened.draft("RGB", (int(opened.width * factor), int(opened.height * factor)))
            image = _within_budget(ImageOps.exif_transpose(opened).convert("RGB"))
        return ocr.read_page(image, name=path.name)
    except Image.DecompressionBombError as exc:
        # Pillow's own guard, which stays on (decision 137, B1): a picture
        # too large even to decode smaller. A size rule, so it is a kept
        # verdict for a person, not a retry every pass.
        raise TooLargeToRead(picture_too_large_reason(exc)) from exc


class TooLargeToRead(Exception):
    """The file is too large to read at all (decision 137): its reason is
    ``reasons.TOO_LARGE``, and it is the file's, not the machine's - a kept
    verdict, not retried until the file changes."""


def extract(path: Path, *, ocr: bool = True) -> Extraction:
    """What ``path`` says - the one reading both the router and the scanner use.

    With ``ocr=False`` a scan (a PDF with no text layer, or a photo, which
    never has one) comes back with ``needs_ocr`` set and whatever little
    text there was, so the caller can decide - the router first tries the
    file's name - and then call :func:`extract_by_ocr` if it still needs
    the words.

    Every reading is timed and the seconds ride back on the
    :class:`Extraction` (decision 127). Nothing acts on the number: no
    reading is cut short for being slow - a pass says its slowest reading
    and finishes it. The one exception is the safety stop, ten times the
    owner's ceiling (decision 137, B1.2, :data:`READING_STOP_PAGE_SECONDS`
    and :data:`READING_STOP_DOCUMENT_SECONDS`): a reading that reaches it
    is abandoned, and its verdict kept. **What the stop covers here:** no
    OCR page starts past it (decision 169, ruling 5), and an overrun is
    noticed between pages. It cannot interrupt a page being read, the PDF
    text layer (pdfplumber), a workbook's reading, or a single page render,
    which run inside the reading's own process and can only be seen to
    have overrun once they return. The bound on the whole reading is the process
    itself: the pass reads through :func:`judge_bounded`, which runs
    this function in a child it ends at the stop (decisions 150 and 189).
    """
    started = time.perf_counter()
    # A file past the ceiling is never opened (decision 137, M5): the
    # reason is the whole reading, and it is the file's, not the machine's,
    # so the verdict is kept and the file is not tried again next pass.
    if too_large := too_large_reason(path):
        return Extraction(None, reason=too_large, extractable=False, code=reasons.TOO_LARGE.code)
    reading = _extract(path, ocr=ocr)
    return replace(reading, seconds=time.perf_counter() - started)


def _extract(path: Path, *, ocr: bool) -> Extraction:
    """:func:`extract`'s reading, untimed."""
    extension = extension_of(path)
    if extension in IMAGE_EXTENSIONS:
        # A photo is a scan with no text layer to be disappointed by: it
        # goes the way a scanned PDF goes, and with ocr=False it is
        # unrouted for the same reason a scan is - there are no words yet.
        return Extraction(None, needs_ocr=True) if not ocr else extract_by_ocr(path)
    try:
        text = extract_text(path)
    except MemoryError:
        raise           # the child's memory limit: a crash, not a corrupt file (SPEC-169 section 9)
    except Exception as exc:  # a corrupt file is a reason, not a crash
        # Its class, never its message (decisions 189 and 190): a parser
        # quotes the cell or the line it choked on, which is the document's
        # words. UnknownPacking's message is the firm's own sentence, said
        # whole. The words are kept apart, on the debug log.
        errors.keep("content_check: extraction", exc, name=path.name)
        error = errors.said(exc, (UnknownPacking,))
        return Extraction(
            None, reason=reasons.EXTRACTION_FAILED.format(error=error),
            extractable=False, error=error, code=reasons.EXTRACTION_FAILED.code,
        )
    if text is None:
        return Extraction(
            None, reason=reasons.UNCHECKABLE_TYPE.format(extension=said_extension(path)), extractable=False,
            code=reasons.UNCHECKABLE_TYPE.code,
        )
    pages = text.count(PAGE_BREAK) + 1
    if extension == PDF_EXTENSION and len(text.strip()) < _MIN_TEXT_CHARS * pages:
        if not ocr:
            return Extraction(text, needs_ocr=True)
        return extract_by_ocr(path)
    cut = extension in TEXT_EXTENSIONS and _is_cut(path)
    if len(text) > READING_CHAR_BUDGET:
        text, cut = text[:READING_CHAR_BUDGET], True
    return Extraction(text, cut=cut)


def extract_by_ocr(path: Path) -> Extraction:
    """Read a scan or a photo by OCR; says why when it cannot (the reader
    cannot run on this machine, no words, or the safety stop)."""
    global _STOP

    reader = _ocr_image if extension_of(path) in IMAGE_EXTENSIONS else _ocr_pdf
    # The safety stop (decision 137, B1.2): one per document, and a photo
    # is its own one page.
    _STOP = _SafetyStop()
    _STOP.page()
    try:
        ocr_text = reader(path)
    except ocr.ReaderUnavailable as exc:
        log.warning("The reader cannot run on this machine (%s)", exc)
        ocr_text = None
    except ReadingStopped as exc:
        return abandoned(exc.seconds)
    except TooLargeToRead as exc:
        return Extraction(None, reason=str(exc), extractable=False, code=reasons.TOO_LARGE.code)
    except MemoryError:
        raise           # the child's memory limit: a crash, not a retry (SPEC-169 section 9)
    except Exception as exc:
        # Ours to retry, not the client's to resend: the file may be fine.
        # The class alone is the reason (decisions 189 and 190): a reader's
        # message can quote the document or its path. The run log names the
        # class; the words stay on the debug log.
        error = errors.error_class(exc)
        log.warning("OCR failed on %s (%s)", path.name, error)
        errors.keep("content_check: OCR", exc, name=path.name)
        return Extraction(
            None, reason=reasons.OCR_FAILED.format(error=error),
            extractable=False, error=error, transient=True, code=reasons.OCR_FAILED.code,
        )
    finally:
        _STOP = None
    if ocr_text is None:
        # The reader cannot run on this machine: a fact about the machine,
        # remembered by nobody, so the day it is mended the scan reads the file.
        return Extraction(None, reason=reasons.NO_TEXT_LAYER.format(), extractable=False, transient=True,
                          code=reasons.NO_TEXT_LAYER.code)
    if not ocr_text.strip():
        return Extraction(None, reason=reasons.NO_TEXT_AFTER_OCR.format(), extractable=False,
                          code=reasons.NO_TEXT_AFTER_OCR.code)
    if len(ocr_text) > READING_CHAR_BUDGET:
        # Cut like every other reading (decision 178's budget; decision 189
        # closed the gap): OCR's words are held and judged like a text
        # layer's, and a reading past the budget is marked cut, so a verdict
        # reached on its first part says so.
        return Extraction(ocr_text[:READING_CHAR_BUDGET], from_ocr=True, cut=True)
    return Extraction(ocr_text, from_ocr=True)


def abandoned(seconds: float) -> Extraction:
    """The reading the safety stop abandoned after ``seconds`` (decision
    137, B1.2): no text, and a verdict that is the file's, so it is kept
    and the file is not read again until it changes. One sentence, whether
    the stop was noticed between pages inside the reading or was the end of
    the reading's own process (decision 150)."""
    minutes = max(1, round(seconds / 60))
    said = "1 minute" if minutes == 1 else f"{minutes} minutes"
    return Extraction(None, reason=reasons.READING_STOPPED.format(minutes=said),
                      extractable=False, seconds=seconds, code=reasons.READING_STOPPED.code)


# ----------------------------------------------- a reading the pass can stop ----
#
# Decision 150. The stop above is noticed between pages, and nothing in the
# reading's own process can interrupt a page being read, the PDF text layer,
# a render or a workbook (a few megabytes of PDF can hold hours of drawing
# commands). So the pass reads and judges in a child process, one per pass
# (tracker.ocr, which also says how it is replaced and how it never outlives
# its pass: a lifeline pipe and, on Windows, a job object), and waits for each
# document at most its stop. Over time the child is ended with everything it
# started and the reading is abandoned, the kept verdict above; a child that
# ends after "started" without answering is a reading that failed, kept the
# same way. A child that never says "started" is the machine's fault and not
# the file's: reasons.READER_UNAVAILABLE, transient, nothing kept, the drop
# left for the next pass and the pass warned once.
#
# The open test (a PDF parsed, decision 150) and the opening of an email or a
# zip (decision 154, in_a_child) are parsing a client's file too, so they run
# in the same child under the same stop: nothing of a client's file is parsed
# in the pass's own process.

#: Whether :func:`judge_bounded` reads in a child process (decision 150).
#: Always, in the tracker. The suite turns it off for every test but the
#: ones about the child (``tests/plugin_fakes.py``): its stand-in readers are
#: patched into the test's own process, which a child never shares.
READ_IN_A_CHILD = True
#: What reads in the child: the open test and the one reading
#: (:func:`open_and_read`), which :func:`judge` then judges there. A name of its own, handed to the child by
#: reference, so the suite can give the child a reader that never finishes
#: or dies - a patch made in the pass's process is not in the child's,
#: which imports this module afresh.
_CHILD_READER = None     # open_and_read, set below it
#: The fingerprint the open test's verdict is kept under in the verdict
#: cache (decision 150). It is about the file, whatever the row, so it
#: sits beside the rows' verdicts under a name no rules fingerprint - a
#: SHA-256 - can ever be.
OPEN_TEST_FINGERPRINT = "open-test"
#: The files whose reader could not start this pass, by name (decision
#: 150). The pass says it once (``runner``), taking the list as it goes.
_COULD_NOT_START: list[str] = []
def reading_stop_seconds(path: Path) -> float:
    """How long the whole reading of ``path`` may take (decision 150): a
    photo is one page - :data:`READING_STOP_PAGE_SECONDS` - and any other
    file is a document - :data:`READING_STOP_DOCUMENT_SECONDS`."""
    if extension_of(path) in IMAGE_EXTENSIONS:
        return READING_STOP_PAGE_SECONDS
    return READING_STOP_DOCUMENT_SECONDS


def open_and_read(path: Path, *, ocr: bool = True) -> Extraction:
    """Tier 2's open test, then the reading: what a reading's child does
    with the file (decision 150). The open test first, as tier 2 comes
    before tier 3; its verdict rides back on the reading as ``opened``."""
    opened = open_test(path)
    return replace(extract(path, ocr=ocr), opened=opened)


_CHILD_READER = open_and_read


def judge(path: Path, questions: Questions, *, reader=None) -> Judgment:
    """The reader child's one job for a document the pass decides
    (decision 189): the open test and the reading (``reader``, by default
    :func:`open_and_read`, exactly as decision 150 made them), then the
    judgment of the words against ``questions`` (:func:`judgment_of`).
    The words stay here; the :class:`Judgment` is all that crosses the
    pipe. So the document's stop bounds the reading **and** every rule
    asked of it, together: a Date Pattern that backtracks for a day, or a
    form scan over a one-line workbook, costs one stop and parks the file
    with the stop's kept verdict (:func:`abandoned`), never the pass."""
    reading = (open_and_read if reader is None else reader)(Path(path), ocr=questions.ocr)
    return judgment_of(reading, questions)


def judge_bounded(path: Path, questions: Questions) -> Judgment:
    """:func:`judge`, in the pass's reader child, waiting at most the
    file's stop: what the pass reads and judges every document through
    (decision 189) - the router's one judgment of a drop
    (:func:`tracker.router.read_once`) and the scanner's on a cache miss
    (:func:`open_verdict`, :func:`check_content`). A stop, a crash or a
    child that never started is the unjudged reading that says so
    (:func:`unjudged`), with 150's three outcomes unchanged. With the
    suite's ``READ_IN_A_CHILD`` off it judges in this process, as the
    reading did."""
    if not READ_IN_A_CHILD:
        return judge(Path(path), questions)
    return _read_in_a_child(Path(path), questions)


class OutOfTime(Exception):
    """The household's time for this pass ran out before a new judgment
    (decision 189, ruling 2.2).

    Raised at the one point a judgment job would start - a cache miss -
    and never at a hit: a verdict the cache holds costs no reading, so a
    household past its deadline still takes every one of them, and stops
    only where it would have to read. The sort and the scan catch it
    between files, record what they did, and leave the rest for the next
    pass."""


def before_a_judgment(cache: ContentCache | None) -> None:
    """Raise :class:`OutOfTime` if ``cache``'s household is past its
    deadline (:attr:`ContentCache.deadline`, on ``ocr.awake_clock``):
    called just before a judgment job would start, and nowhere else."""
    if cache is not None and cache.deadline is not None and ocr.awake_clock() >= cache.deadline:
        raise OutOfTime


def could_not_start(seconds: float, error: str, name: str) -> Extraction:
    """The reading whose child never started (decision 150): the machine's
    doing, so transient - nothing is kept - and the pass says it once."""
    _COULD_NOT_START.append(name)
    return Extraction(None, reason=reasons.READER_UNAVAILABLE.format(), extractable=False,
                      error=error, transient=True, seconds=seconds,
                      code=reasons.READER_UNAVAILABLE.code)


def readers_that_could_not_start() -> list[str]:
    """The files whose reader could not start since this was last asked,
    and forget them: the pass asks once, at its end, and says it once."""
    names = list(_COULD_NOT_START)
    _COULD_NOT_START.clear()
    return names


def open_verdict(path: Path, cache: ContentCache, item: RequestItem | None = None) -> str:
    """Tier 2's open test of ``path`` for the scanner: ``""`` or the
    refusal, never made in this process (decision 150).

    Kept in ``cache`` by the file's content digest, like a reading's
    verdicts: a hit starts no child. On a miss the file is read and judged
    in the child (:func:`judge_bounded`) - the open test, the reading and,
    since decision 189, the rules of ``item``, the row the working copy
    sits under, all in one job - and the judgment is held in memory for
    the content check that follows, so the file is read once. A stopped or
    crashed child is the verdict, kept; a child that could not start, or a
    machine without the HEIC decoder, is the machine's, said and not kept.

    The refusal is a :class:`tracker.reasons.Said`, carrying its code
    (decision 190): a kept one is said again with the code it was kept
    with, so the row the scanner writes knows its cause either way.
    """
    digest = cache.digest_of(path)
    if digest:
        hit = cache.get_by_digest(digest, OPEN_TEST_FINGERPRINT)
        if hit is not None:
            return reasons.Said(hit.reason, hit.code) if hit.reason else ""
    rows = (row_question(item),) if item is not None and has_content_rules(item) else ()
    before_a_judgment(cache)
    judgment = judge_bounded(path, Questions(rows=rows))
    reading = judgment.extraction
    if reading.opened is not None:
        verdict, code = reading.opened, reasons.code_of(reading.opened)
    else:
        verdict, code = reading.reason, reading.code
    if digest:
        cache.hold_reading(digest, judgment)
        if not reading.transient and code != reasons.HEIC_NOT_SUPPORTED.code:
            cache.put_by_digest(digest, OPEN_TEST_FINGERPRINT,
                                ContentResult(ok=not verdict, reason=verdict, code=code))
    return reasons.Said(verdict, code) if verdict else ""


def reading_failed(seconds: float, error: str) -> Extraction:
    """The reading whose process ended without an answer (decision 150):
    the file's verdict, kept like an abandoned one, for a person to read."""
    return Extraction(None, reason=reasons.READING_CRASHED.format(), extractable=False,
                      error=error, seconds=seconds, code=reasons.READING_CRASHED.code)


def _read_in_a_child(path: Path, questions: Questions) -> Judgment:
    """Read and judge ``path`` in the reader child, waiting at most its
    stop: :func:`judge`, handed the reader by reference
    (``_CHILD_READER``, which the suite swaps for a stand-in)."""
    answer, failed = in_a_child(path, judge, questions=questions, reader=_CHILD_READER)
    return unjudged(failed) if failed is not None else cast(Judgment, answer)   # judge returns a Judgment


def in_a_child(path: Path, job, *, stop: float | None = None, **kwargs) -> tuple[object, Extraction | None]:
    """Run ``job(path, **kwargs)`` in the pass's reading child
    (:func:`tracker.ocr.run_in_child`), waiting at most ``stop`` seconds (by
    default the file's own, :func:`reading_stop_seconds`). The one mechanism
    for every parse of a client's file (decision 150): the reading, and the
    opening of an email or a zip (decision 154,
    :func:`tracker.containers.open_bounded`).

    Gives ``(answer, None)`` on time, ``answer`` being what the job
    returned, and ``(None, why)`` otherwise, ``why`` the Extraction that
    says it: the stop (:func:`abandoned`), an end after "started"
    (:func:`reading_failed`), or a child that never started
    (:func:`could_not_start`, transient, nothing to keep). ``job`` is a
    module-level function, handed to the child by reference; what it
    returns crosses the pipe, so it is plain data.
    """
    path = Path(path)
    stop = reading_stop_seconds(path) if stop is None else stop
    outcome = ocr.run_in_child(job, (path,), kwargs, stop)
    if outcome.kind == "read":
        return outcome.answer, None
    if outcome.kind == "not_started":
        errors.keep("content_check: the reader could not start", outcome.error, name=path.name)
        return None, could_not_start(outcome.seconds, outcome.error, path.name)
    if outcome.kind == "stopped":
        log.warning("Reading %s stopped at the safety stop (%.0f s)", path.name, stop)
        return None, abandoned(outcome.seconds)
    # What crosses the pipe is the class and nothing after it (decisions
    # 189, M1, and 190): the child sends its class, message and trace apart,
    # and the partition still cuts anything after a colon.
    error = outcome.error.partition(":")[0]
    if outcome.kind == "failed":
        # The class is the row's; the words and the trace are the debug
        # log's (decision 190). The run log names the class only.
        log.warning("The reader failed on %s (%s)", path.name, error)
        errors.keep("content_check: the reader failed",
                    f"{outcome.message}\n{outcome.trace}", name=path.name)
        return None, reading_failed(outcome.seconds, error)
    log.warning("The reader stopped unexpectedly on %s (%s)", path.name, error)
    errors.keep("content_check: the reader stopped unexpectedly", outcome.error, name=path.name)
    return None, reading_failed(outcome.seconds, error)


# ---------------------------------------------------------------- checking ----


def check_content(
    path: Path, item: RequestItem, cache: ContentCache | None = None
) -> ContentResult:
    """Tier-3 verdict for one file, using the cache when possible.

    Files for items with no content rules pass immediately — no extraction,
    no file read. Callers must only pass files that already cleared the
    tier-2 placeholder check (reading a cloud-only file would hydrate it).
    """
    if not has_content_rules(item):
        return ContentResult(ok=True)

    fingerprint = rules_fingerprint(item)
    if cache is not None:
        hit = cache.get(path, fingerprint)
        if hit is not None:
            return hit

    result = _check_uncached(path, item, cache.held_reading(path) if cache is not None else None,
                             cache=cache)

    if cache is not None and not result.transient:
        cache.put(path, fingerprint, result)
    return result


def _check_uncached(
    path: Path, item: RequestItem, held: Judgment | None = None,
    cache: ContentCache | None = None,
) -> ContentResult:
    """The scan's verdict on a cache miss: the reading the router made.

    A page that names two forms as itself is read with both counted as its
    own (:func:`own_forms`), which is the verdict the router filed the
    second copy on; every other page reads exactly as it always did. So a
    verdict from an empty cache and a verdict the router kept are one
    verdict, and a rebuilt store cannot turn a filed copy into a failure.

    Judged in the reader child (decision 189): ``held`` is the judgment
    :func:`open_verdict` made of the same bytes a moment ago, used when it
    answers this row - or when there were no words to judge, which is the
    answer whatever the row. A row it was not asked is a new judgment, and
    only a new judgment is stopped by the household's deadline (``cache``,
    :func:`before_a_judgment`).
    """
    question = row_question(item)
    judgment = held
    if judgment is None or (judgment.extraction.text is not None and question not in judgment.rows):
        before_a_judgment(cache)
        judgment = judge_bounded(path, Questions(rows=(question,)))
    reading = judgment.extraction
    if reading.text is None:
        return ContentResult(
            ok=False, reason=reading.reason, extractable=False, transient=reading.transient,
            code=reading.code,
        )
    verdict = judgment.rows[question].verdict
    if reading.cut and not verdict.ok:
        # The rules were asked of the first part only, and a person reading
        # the reason must know that before believing "not found".
        verdict = replace(verdict, reason=f"{verdict.reason}; "
                                          f"{reasons.TEXT_CUT.format(limit=TEXT_READ_CAP_MB)}")
    return verdict


# ------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.manifest import load_manifest
    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description="What does this document say, and which rows accept it? "
                    "Read-only: no cache is written, nothing moves."
    )
    parser.add_argument("engagement_dir", help="the engagement folder")
    parser.add_argument("file", help="the document to read")
    ns = parser.parse_args()
    # A typed folder is parsed, never trusted (decision 188).
    from tracker import door

    ns.engagement_dir = door.typed_return(parser, ns.engagement_dir)

    document = Path(ns.file)
    reading = extract(document)
    if reading.text is None:
        print(f"{document.name}: {reading.reason}")
        raise SystemExit(1)
    how = "OCR" if reading.from_ocr else "text layer"
    print(f"{document.name}: {len(reading.text)} characters from the {how}\n")
    for row in load_manifest(Path(ns.engagement_dir)):
        if not has_content_rules(row):
            continue
        verdict = evaluate_rules(reading.text, row)
        mark = "ok" if verdict.ok else f"no - {verdict.reason}"
        print(f"[{row.identifier}] {row.document}: {mark}")
