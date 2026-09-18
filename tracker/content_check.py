"""Tier-3 content validation for the tracker (component 4).

Extracts text from client documents (read-only) and applies the deterministic
rules from the manifest row: Required Keywords (ALL must appear), Any
Keywords (at least ONE), and Date Pattern (regex). No rule logic is
hardcoded — everything comes from the manifest.

Extractors by extension:

- ``.pdf``            → pdfplumber, first ``MAX_PAGES`` pages only; if the
                        PDF has no text layer (a scan), fall back to OCR
                        *if available* (pytesseract + pypdfium2 + Tesseract).
                        The OCR stack is entirely optional: when absent, the
                        file is reported as unverifiable with a clear note —
                        nothing breaks.
- ``XLSX_EXTENSIONS``   → openpyxl (all sheets, cached formula values);
                        date cells are rendered in both ISO (2025-12-31)
                        and US (12/31/2025) forms so either pattern style
                        matches.
- ``TEXT_EXTENSIONS``   → plain text (utf-8, then cp1252 fallback).
- anything else       → no extractor; reported unverifiable, for a person (``reasons.UNCHECKABLE_TYPE``).

**One way of reading a document.** :func:`extract` is what both the router
(deciding where a drop goes) and the scanner (deciding a row's status) call,
so the two can never disagree about what a file says. The router asks for
the text layer first and OCR only when the file's name tells it nothing
(:mod:`tracker.router` explains why); the scanner always finishes the job.

Keyword matching is case-insensitive. Date Pattern is applied to the raw
text as-is, so authors control case sensitivity with inline flags (``(?i)``).

Caching: :class:`ContentCache` stores only *verdicts* — pass/fail + reason —
keyed by the file's **content digest** and the row's rules fingerprint, with
a per-path memo of (size, mtime, digest) so an unchanged file is not
re-hashed. Keyed on content, not path, because the same bytes are read
twice in this system: once as a drop the router routes, once as the
working copy the scanner checks. A verdict the router reached is the
verdict the scanner finds. Extracted client text is deliberately never
persisted anywhere. Editing a row's rules changes the fingerprint and
triggers one re-extraction; unchanged files on unchanged rules are never
re-read, which keeps the scheduled cadence cheap.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import MISSING, asdict, dataclass, fields
from pathlib import Path

from tracker import reasons
from tracker.manifest import RequestItem, has_routing_rules, write_json_atomically
from tracker.validators import PDF_EXTENSION, extension_of, sha256_of

log = logging.getLogger("tracker.content_check")

# pdfplumber/pdfminer warn loudly on ugly-but-parseable PDFs; failures are
# already surfaced through ContentResult.reason.
logging.getLogger("pdfminer").setLevel(logging.ERROR)

#: The verdict cache beside the manifest, shared by the filer and the scanner.
CACHE_FILENAME = "_content_cache.json"
#: Its layout; an older layout is simply reset (the cache is disposable).
#: 3: verdicts that were the machine's (no OCR, OCR failed) are no longer
#: stored; a cache written before that carried them for ever.
#: 4: says() changed what a keyword verdict means (a form number is title evidence).
#: 5: a form number in the title is weighed by its shape too; a keyword's words sit on one line.
CACHE_VERSION = 5

#: A "text" PDF with fewer stripped characters than this *per page read*
#: is a scan: what little it has is a scanner's stamp ("Scanned by
#: CamScanner", "Page 1 of 2"), not the document, and is not read as one.
#: Pages are counted from the page breaks ``_extract_pdf`` writes.
_MIN_TEXT_CHARS = 25
_PAGE_BREAK = "\f"

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
_MAX_OCR_PAGES = MAX_PAGES


@dataclass(frozen=True, slots=True)
class ContentResult:
    """Verdict of tier-3 rules for one file."""

    ok: bool
    reason: str = ""
    extractable: bool = True  # False: could not get text (no extractor / no OCR)
    #: True when the verdict is about the machine, not the document: OCR is
    #: not installed, or it failed this once. Never cached - installing OCR
    #: or a second try must be able to change the answer.
    transient: bool = False


@dataclass(frozen=True, slots=True)
class Extraction:
    """What one document says, or why it could not be read.

    ``text`` is None when there is nothing usable and ``reason`` then says
    why in the words the scanner writes. ``needs_ocr`` marks a PDF whose
    text layer is empty when the caller asked not to OCR yet.
    """

    text: str | None
    from_ocr: bool = False       # the text came from OCR, not a text layer
    needs_ocr: bool = False      # a scan; OCR was not attempted (ocr=False)
    reason: str = ""             # why there is no usable text, if there is none
    extractable: bool = True     # False: no extractor, no OCR, or extraction failed
    error: str = ""              # the exception, when extraction raised
    transient: bool = False      # the machine's doing (no OCR, OCR failed), not the file's


# ------------------------------------------------------------------ rules ----


def has_content_rules(item: RequestItem) -> bool:
    """Whether tier 3 has anything to check on this row at all: a routing
    rule, or a year check derived from Period (which checks but never routes)."""
    return has_routing_rules(item) or bool(item.date_pattern)


def rules_fingerprint(item: RequestItem) -> str:
    """Stable hash of the row's tier-3 rules; part of the cache key."""
    blob = json.dumps(
        [list(item.required_keywords), list(item.any_keywords), item.date_pattern]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


#: The variants the IRS joins to a form's number: ``1098-T`` is the tuition
#: form, not the mortgage form ``1098``; ``1099-R`` is not ``1099-INT``. A
#: keyword of the bare number means the bare form and must not match a
#: variant. Keyed by the number with its dashes removed (``w2`` for W-2), so
#: a keyword written either way is found. Any other hyphen-joined neighbour
#: - an employer, a bank, a person (``1098-Citi``, ``W2-Tom``) - is a
#: separator's hyphen and still matches, which is what a client's file
#: name usually carries. One list, in the one module that reads keywords.
FORM_VARIANTS: dict[str, tuple[str, ...]] = {
    "1098": ("t", "e", "c", "f", "q", "ma"),
    "1099": ("int", "div", "b", "r", "misc", "nec", "oid", "k", "g", "s", "sa",
             "q", "ltc", "patr", "cap", "c", "a", "h", "da", "ls", "sb", "qa"),
    "1095": ("a", "b", "c"),
    "1040": ("sr", "nr", "x", "es", "v", "ss", "c"),
    "1041": ("a", "es", "n", "qft", "t", "v"),
    "1065": ("x", "b"),
    "1120": ("s", "x", "f", "h", "w", "c", "l", "pc", "pol", "reit", "ric", "sf", "nd"),
    "940": ("pr", "ss"),
    "941": ("x", "ss", "pr"),
    "990": ("ez", "pf", "t", "n"),
    "5498": ("sa", "esa", "qa"),
    "w2": ("g", "gu", "as", "vi", "c"),
    "w3": ("c", "ss", "pr"),
}
#: What may sit between a number and its variant, or between a keyword's
#: words: nothing ("1098T"), spaces, or any dash a PDF or a keyboard yields
#: - not a line break, unless the phrase is a heading that wraps. A
#: keyword names one thing, and its words are printed together; a line
#: break is where one label ends and the next begins. A K-1's box "19
#: Distributions" above its footer "Schedule K-1" is not a distribution
#: schedule, and "Items affecting shareholder basis" above the same
#: footer is not a shareholder basis schedule. A heading set in its own
#: box wraps - "Balance Sheet" over "As of December 31, 2025" - and a
#: heading begins its line with two words or more; a phrase that begins
#: mid-line and runs on to the next is a sentence, and one word over
#: another is two labels. (The IRS sets the 1098's title one word per
#: line, "Mortgage / Interest / Statement"; that form is known by its
#: number, as every form in tests/irs/ is.)
_DASH_CHARS = "".join(("-", chr(0x2010), chr(0x2011), chr(0x2012), chr(0x2013), chr(0x2014), chr(0x2212), chr(0xAD)))   # hyphen, the Unicode dashes, minus, soft hyphen
#: An apostrophe as a keyboard types it, as a PDF prints it, and as OCR reads it.
_APOSTROPHES = "".join(("'", chr(0x2019), chr(0x2018), chr(0x02BC), chr(0x60)))
_SAME_LINE = r"[^\S\r\n\f\v]"   # whitespace that is not a line break (a no-break space included)
_JOINER = rf"(?:{_SAME_LINE}|[{re.escape(_DASH_CHARS)}])*"
_WRAPPING_JOINER = rf"[\s{re.escape(_DASH_CHARS)}]*"
#: A heading begins its line, after nothing but blank space, a bullet, a
#: pipe or a rule (OCR reads a box's edge as "|", a list as "-" or "•").
_LINE_START = rf"(?:^|(?<=[\r\n\f\v]))(?:{_SAME_LINE}|[{re.escape(_DASH_CHARS)}•*|_])*"
_DASHES = re.compile(rf"[\s{re.escape(_DASH_CHARS)}]")


def _joined_to_a_variant(text: str, keyword: str, match: re.Match[str]) -> bool:
    """True when the matched keyword ends in a form number that ``text``
    continues with one of that form's variants: ``1098`` in "1098-T" or
    "1098 T", ``form 1040`` in "Form-1040-SR"."""
    variants = FORM_VARIANTS.get(_DASHES.sub("", keyword.strip().lower().split()[-1]))
    if not variants:
        return False
    tail = re.compile(rf"{_JOINER}(?:{'|'.join(variants)})(?![a-z0-9])")
    return tail.match(text, match.end()) is not None


def keyword_pattern(keyword: str, *, wrapping: bool = False) -> str | None:
    """The regular expression one keyword is looked for with, or None if blank.

    Whole tokens only. Between a keyword's words, and on either side of a
    dash inside a word, anything a dash can become: ``interest income``
    matches "interest-income" in a file name, ``w-2`` matches "W2" and
    "W–2", ``1099-int`` matches "1099INT". A keyword's words are on one
    line (``_JOINER``); the ``wrapping`` pattern is the other reading, a
    heading that begins its line with two words or more of the keyword
    and wraps the rest on to the next, and is None for a keyword that
    cannot wrap. Two one-word lines are two labels, not one phrase.
    """
    # Only the letters and digits are the keyword; a "-" or "$" typed into
    # a keyword cell is nothing to look for, and must not match everything.
    keyword = keyword.strip().lower()
    if not any(ch.isalnum() for ch in keyword):
        return None
    words = [_JOINER.join(_seams(part) for part in _DASHES.split(w) if part) for w in keyword.split()]
    words = [w for w in words if w]
    if not wrapping:
        return rf"(?<![a-z0-9]){_JOINER.join(words)}(?![a-z0-9])"
    if len(words) < 3:
        return None
    first_line = _JOINER.join(words[:2])
    return rf"{_LINE_START}(?<![a-z0-9]){first_line}{_WRAPPING_JOINER}{_WRAPPING_JOINER.join(words[2:])}(?![a-z0-9])"


def _seams(part: str) -> str:
    """``part`` escaped, with a dash allowed where letters meet digits (a
    keyword typed ``w2`` finds "W-2" as ``w-2`` finds "W2"), a plural
    allowed on a word (``fixed asset`` finds "Fixed Assets"), and a number
    kept out of a larger amount (``704`` is not in "20,704" or "704.50")."""
    pieces = re.findall(r"[a-z]+|[0-9]+|[^a-z0-9]+", part)
    out = []
    for piece in pieces:
        if piece.isalpha() and len(piece) >= 3:
            out.append(re.escape(piece) + "(?:e?s)?")
        elif piece.isdigit():
            out.append(rf"(?<![0-9][,.]){re.escape(piece)}(?![,.][0-9])")
        elif all(ch in _APOSTROPHES for ch in piece):
            out.append(f"[{re.escape(_APOSTROPHES)}]?")   # typed straight, printed curly, or dropped
        else:
            out.append(re.escape(piece))
    return _JOINER.join(out)


def contains_keyword(text: str, keyword: str) -> bool:
    """True if ``keyword`` appears in ``text`` as a whole token.

    Matched on token boundaries rather than as a bare substring, so ``EIN``
    does not match "being", ``1098`` does not match "10983", and ``W-2``
    still matches "W-2 Wage and Tax Statement". A form's own variant is
    part of its name, not a boundary: ``1098`` does not match "1098-T"
    and ``1099`` does not match "1099-R" (``FORM_VARIANTS``), because a
    tuition statement filed as mortgage interest is exactly the misfiling
    the keywords exist to prevent. A row that means every 1099 lists them.
    Keywords drive both status and — via :mod:`tracker.router` — where a
    document gets filed, so a coincidental substring must never count as
    evidence.
    """
    text = text.lower()
    for pattern in (keyword_pattern(keyword), keyword_pattern(keyword, wrapping=True)):
        if pattern is None:
            continue
        if any(not _joined_to_a_variant(text, keyword, m) for m in re.finditer(pattern, text)):
            return True
    return False


#: A form number a keyword names is content evidence only where a form
#: prints its own: in the title - the first ``TITLE_CHARS`` of the text -
#: or as the number the document prints most, on every copy and every
#: page's footer (a W-2 prints its title at the foot of the form, below
#: the boxes). Every 1040 says "Attach Form(s) W-2", every 1095-C's
#: instructions name "Form 1095-A", every 1099's say "Form 1040-ES", and
#: those are single mentions of other forms, not the form this is. In the
#: title as everywhere, a mention counts only when its shape is a form
#: naming itself, not a sentence about another form (``_mention_weight``):
#: the IRS prints an "Attention" page ahead of every information return
#: that names Form 1099-NEC by way of example, an organizer's first lines
#: say "attach Form 1098", a bank's letter says "reported on Form
#: 1099-INT". A file name is read whole: it is all title.
TITLE_CHARS = 400
_FORM_NUMBER = re.compile(r"^(?:form\s+)?([a-z]?\d{3,4}|w\d)(?:[a-z]{1,4})?$")
_FORM_MENTION = re.compile(
    rf"(?<![a-z0-9])(?:form\s+)?(w[{re.escape(_DASH_CHARS)}]?[23]|\d{{3,4}})"
    rf"(?:[\s{re.escape(_DASH_CHARS)}]?([a-z]{{1,4}}))?(?![a-z0-9])"
)


def is_form_number(keyword: str) -> bool:
    """True for a keyword that is a form's number: ``1098``, ``form 1095-a``,
    ``W-2``, ``form 940``. A bare number counts only for a known family
    (``FORM_VARIANTS``); ``form`` in front makes any number one."""
    bare = _DASHES.sub("", keyword.strip().lower())
    if bare.startswith("form"):
        return _FORM_NUMBER.match("form " + bare[4:]) is not None
    match = _FORM_NUMBER.match(bare)
    return match is not None and match.group(1) in FORM_VARIANTS


def _form_key(number: str, variant: str | None) -> str:
    return _DASHES.sub("", number) + (variant or "")


def _title(text: str) -> str:
    """The first ``TITLE_CHARS``, extended to the end of the word it cuts."""
    if len(text) <= TITLE_CHARS:
        return text
    space = re.compile(r"\s").search(text, TITLE_CHARS)
    return text[:space.start()] if space else text


#: How a form names itself, and how it names another form. Its own number
#: is followed by its year or revision - "Form 1040 (2025)", "Form 1099-DIV
#: (Rev. January 2024)", "941 for 2026:" - on the title and on every page's
#: footer. Another form's number is quoted: "(Form 1040)", "Form 1040 or
#: 1040-SR", "Form 1040 instructions", "Form 1040, line 8" - or told to
#: the reader: "attach Form 1098", "Forms W-2", "reported on Form
#: 1099-INT", "a 1098". The two shapes are told apart here, because a
#: W-2's instruction pages name Form 1040 thirty times and the W-2 itself
#: a dozen. A self-mention's year is on the same line as its number.
_SELF_WEIGHT, _PLAIN_WEIGHT, _REFERENCE_WEIGHT = 3, 1, 0
_SELF_AFTER = re.compile(
    rf"{_SAME_LINE}*(?:\({_SAME_LINE}*)?(?:rev\b|(?:19|20)\d{{2}}\b)|{_SAME_LINE}+for{_SAME_LINE}+(?:19|20)\d{{2}}\b"
)
_REFERENCE_AFTER = re.compile(
    r"\s*[,.;)]|\s+(?:or|and|line|lines|instructions?|to|if|is|are|was|were|schedule|box|boxes|page|"
    r"worksheet|for|with|at|by|filers?|must|may|should)\b"
)
#: The words a document prints before a form it is telling the reader
#: about; a form never names itself after them.
_REFERENCE_BEFORE = re.compile(
    r"(?<![a-z0-9])(?:forms|attach|attached|see|file|files|filed|use|of|on|from|with|to|and|or|a|an|the|"
    r"include|including|per|report|reported)\s+$"
)
_BEFORE_CHARS = 12   # room for the longest word above and the space after it


def _mention_weight(text: str, match: re.Match[str], end: int) -> int:
    """``end`` is where the form number (with its real variant) stops."""
    start = match.start()
    if start > 0 and text[start - 1] == "(":
        return _REFERENCE_WEIGHT
    # What comes before is read first: "attach Form 1098 (2025)" is told to
    # the reader, year or no year (the tenth reading added the year).
    if _REFERENCE_BEFORE.search(text, max(0, start - _BEFORE_CHARS), start):
        return _REFERENCE_WEIGHT
    if _SELF_AFTER.match(text, end):
        return _SELF_WEIGHT
    if _REFERENCE_AFTER.match(text, end):
        return _REFERENCE_WEIGHT
    return _PLAIN_WEIGHT


def _mentions(low: str):
    """Every form number ``low`` (lower-cased text) mentions, as
    ``(key, start, weight)``.

    A known family (``FORM_VARIANTS``) is a mention bare or after "Form":
    "W-2", "941 for 2026", "Form 1099-DIV". Any other number is one only
    after "Form" and takes a variant only joined by a dash - "Form 4562",
    "Form 1125-E" - because a bare 4562 is as likely a year, an OMB number
    or an amount, and "Form 4562 line" is not Form 4562-LINE.
    """
    for match in _FORM_MENTION.finditer(low):
        number, variant = match.group(1), match.group(2)
        base = _DASHES.sub("", number)
        end = match.end()
        if base in FORM_VARIANTS:
            if variant and variant not in FORM_VARIANTS[base]:
                variant, end = None, match.end(1)   # "1040 line" is Form 1040, not a variant
        else:
            if not match.group(0).startswith("form"):
                continue
            if variant and low[match.start(2) - 1].isspace():
                variant, end = None, match.end(1)
        yield _form_key(number, variant), match.start(), _mention_weight(low, match, end)


def dominant_forms(text: str) -> set[str]:
    """The form number ``text`` is about, normalised (``w2``, ``1099int``),
    as a set of at most one.

    Mentions are weighed by their shape (``_mention_weight``): a form's
    own number, dated, on the title and every footer outweighs the other
    forms its instructions quote. The heaviest is its own; among equals,
    the first mentioned. A number that never appears in its own right and
    only once in passing is nobody's - an IRS notice that lists three
    forms to file is about none of them.
    """
    scores: dict[str, int] = {}
    first: dict[str, int] = {}
    for key, start, weight in _mentions(text.lower()):
        scores[key] = scores.get(key, 0) + weight
        first.setdefault(key, start)
    if not scores:
        return set()
    top = max(scores.values())
    if top < 2:
        return set()
    return {min((key for key, n in scores.items() if n == top), key=first.get)}


#: A title that names this many forms in their own right is a list of
#: forms - an organizer's checklist ("Form W-2 - Wage and Tax Statement",
#: "Form 1098 - Mortgage Interest Statement", ...), a transmittal's
#: "Enclosed: Form W-2 2025, Form 1098 2025, Form 1099-INT 2025" - and
#: is none of them, as decision 63 says of a notice that lists three
#: forms to file. A composite 1099 names two or three and parks on the
#: rows' own tie.
_LIST_OF_FORMS = 3


def _title_forms(low: str) -> set[str]:
    """The form numbers the title (``_title``) of ``low`` (lower-cased
    text) names in their own right: a mention there that is not a
    sentence about another form. None when the title names
    ``_LIST_OF_FORMS`` or more."""
    stop = len(_title(low))
    forms = set()
    for key, start, weight in _mentions(low):
        if start >= stop:
            break
        if weight > _REFERENCE_WEIGHT:
            forms.add(key)
    return forms if len(forms) < _LIST_OF_FORMS else set()


def says(text: str, keyword: str, dominant: set[str] | None = None) -> bool:
    """``contains_keyword`` as content evidence: a form number counts only
    where the title names it in its own right (``_title_forms``) or as the
    document's own (dominant) number."""
    if not is_form_number(keyword):
        return contains_keyword(text, keyword)
    if not contains_keyword(text, keyword):
        return False
    bare = _DASHES.sub("", keyword.strip().lower())
    key = bare[4:] if bare.startswith("form") else bare
    if key in _title_forms(text.lower()):
        return True
    return key in (dominant_forms(text) if dominant is None else dominant)


def evaluate_rules(text: str, item: RequestItem) -> ContentResult:
    """Apply the manifest row's content rules to extracted text."""
    dominant = dominant_forms(text)
    missing = [k for k in item.required_keywords if not says(text, k, dominant)]
    if missing:
        listed = ", ".join(f"'{k}'" for k in missing)
        return ContentResult(ok=False, reason=reasons.WRONG_DOCUMENT.format(listed=listed))

    if item.any_keywords and not any(
        says(text, k, dominant) for k in item.any_keywords
    ):
        listed = ", ".join(item.any_keywords)
        return ContentResult(ok=False, reason=reasons.NO_EXPECTED_KEYWORD.format(listed=listed))

    if item.date_pattern and not re.search(item.date_pattern, text):
        return ContentResult(ok=False, reason=reasons.WRONG_PERIOD.format(pattern=item.date_pattern))

    return ContentResult(ok=True)


# ------------------------------------------------------------- extraction ----


def _extract_pdf(path: Path) -> str:
    import pdfplumber  # deferred: heavy import, only needed for PDFs

    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:MAX_PAGES]:
            parts.append(page.extract_text() or "")
    return _PAGE_BREAK.join(parts)


def _extract_xlsx(path: Path) -> str:
    import datetime as dt

    from openpyxl import load_workbook

    # A sheet's row is a line and its cells are set apart by a tab: a
    # keyword's words may run across a row's cells ("Fixed Asset" beside
    # "Schedule") and never down its rows.
    parts: list[str] = []
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            parts.append(str(ws.title))
            for row in ws.iter_rows(values_only=True):
                cells: list[str] = []
                for value in row:
                    if value is None:
                        continue
                    if isinstance(value, (dt.datetime, dt.date)):
                        # Both forms, so ISO- and US-style patterns match.
                        d = value.date() if isinstance(value, dt.datetime) else value
                        cells.append(f"{d.isoformat()} {d.month}/{d.day}/{d.year}")
                    else:
                        cells.append(str(value))
                if cells:
                    parts.append("\t".join(cells))
    finally:
        wb.close()
    return "\n".join(parts)


def _extract_textfile(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def extract_text(path: Path) -> str | None:
    """Extract the text layer from a supported file; None if no extractor exists."""
    extension = extension_of(path)
    if extension == PDF_EXTENSION:
        return _extract_pdf(path)
    if extension in XLSX_EXTENSIONS:
        return _extract_xlsx(path)
    if extension in TEXT_EXTENSIONS:
        return _extract_textfile(path)
    return None


def _ocr_pdf(path: Path) -> str | None:
    """OCR the first pages of a PDF. None if the OCR stack is unavailable.

    Requires pytesseract + pypdfium2 + Pillow (pip) AND the Tesseract
    engine (Windows installer). All optional — absence is a normal,
    reported condition, never an error.
    """
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError:
        return None

    try:
        parts: list[str] = []
        doc = pdfium.PdfDocument(path)
        try:
            for index in range(min(len(doc), _MAX_OCR_PAGES)):
                bitmap = doc[index].render(scale=2.0)
                parts.append(pytesseract.image_to_string(bitmap.to_pil()))
        finally:
            doc.close()
        return "\n".join(parts)
    except pytesseract.TesseractNotFoundError:
        return None  # pip packages present but the Tesseract engine is not
    except Exception as exc:
        log.warning("OCR failed on %s: %s", path.name, exc)
        raise OcrError(f"{exc.__class__.__name__}: {exc}") from exc


class OcrError(RuntimeError):
    """OCR is installed but failed on this file this time; try again later."""


def extract(path: Path, *, ocr: bool = True) -> Extraction:
    """What ``path`` says - the one reading both the router and the scanner use.

    With ``ocr=False`` a scan (a PDF with no text layer) comes back with
    ``needs_ocr`` set and whatever little text there was, so the caller can
    decide - the router first tries the file's name - and then call
    :func:`extract_by_ocr` if it still needs the words.
    """
    extension = extension_of(path)
    try:
        text = extract_text(path)
    except Exception as exc:  # a corrupt file is a reason, not a crash
        error = f"{exc.__class__.__name__}: {exc}"
        return Extraction(
            None, reason=reasons.EXTRACTION_FAILED.format(error=error),
            extractable=False, error=error,
        )
    if text is None:
        return Extraction(
            None, reason=reasons.UNCHECKABLE_TYPE.format(extension=extension), extractable=False,
        )
    pages = text.count(_PAGE_BREAK) + 1
    if extension == PDF_EXTENSION and len(text.strip()) < _MIN_TEXT_CHARS * pages:
        if not ocr:
            return Extraction(text, needs_ocr=True)
        return extract_by_ocr(path)
    return Extraction(text)


def extract_by_ocr(path: Path) -> Extraction:
    """Read a scan by OCR; says why when it cannot (no OCR installed, or no words)."""
    try:
        ocr_text = _ocr_pdf(path)
    except OcrError as exc:
        # Ours to retry, not the client's to resend: the file may be fine.
        return Extraction(
            None, reason=reasons.OCR_FAILED.format(error=str(exc)),
            extractable=False, error=str(exc), transient=True,
        )
    if ocr_text is None:
        # No OCR on this machine: a fact about the machine, remembered by
        # nobody, so the day it is installed the scan reads the file.
        return Extraction(None, reason=reasons.NO_TEXT_LAYER.format(), extractable=False, transient=True)
    if not ocr_text.strip():
        return Extraction(None, reason=reasons.NO_TEXT_AFTER_OCR.format(), extractable=False)
    return Extraction(ocr_text, from_ocr=True)


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

    result = _check_uncached(path, item)

    if cache is not None and not result.transient:
        cache.put(path, fingerprint, result)
    return result


def _check_uncached(path: Path, item: RequestItem) -> ContentResult:
    reading = extract(path)
    if reading.text is None:
        return ContentResult(
            ok=False, reason=reading.reason, extractable=False, transient=reading.transient,
        )
    return evaluate_rules(reading.text, item)


# ------------------------------------------------------------------- cache ----


class ContentCache:
    """Verdict cache: ``(content digest, rules-fingerprint) -> ContentResult``.

    Stores only pass/fail verdicts and reasons — never extracted client
    text. A per-path memo of (size, mtime, digest) spares the hashing of a
    file that has not changed; the verdicts themselves are keyed by what
    the file *is*, so a working copy of a routed drop is a hit under its
    new name. Disposable by design: a corrupt, missing or older-layout
    cache file simply means re-extraction, so it is reset silently.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._dirty = False
        self._files: dict[str, dict] = {}                # path key -> size, mtime_ns, digest
        self._verdicts: dict[str, dict[str, dict]] = {}  # digest -> fingerprint -> verdict
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Content cache reset (unreadable): %s", exc)
                return
            if (
                isinstance(data, dict) and data.get("version") == CACHE_VERSION
                and isinstance(data.get("files"), dict) and isinstance(data.get("verdicts"), dict)
            ):
                self._files = data["files"]
                self._verdicts = data["verdicts"]
            else:
                log.info("Content cache reset (older layout); verdicts are recomputed")

    @staticmethod
    def _key(file: Path) -> str:
        return str(file.resolve()).lower()  # Windows paths are case-insensitive

    def digest_of(self, file: Path) -> str | None:
        """The file's content digest, hashed once per (size, mtime); None if it vanished."""
        try:
            stat = file.stat()
        except OSError:
            return None
        key = self._key(file)
        memo = self._files.get(key)
        if memo and memo.get("size") == stat.st_size and memo.get("mtime_ns") == stat.st_mtime_ns:
            return str(memo["digest"])
        try:
            digest = sha256_of(file)
        except OSError:
            return None
        self._files[key] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "digest": digest}
        self._dirty = True
        return digest

    def get(self, file: Path, fingerprint: str) -> ContentResult | None:
        digest = self.digest_of(file)
        return self.get_by_digest(digest, fingerprint) if digest else None

    def get_by_digest(self, digest: str, fingerprint: str) -> ContentResult | None:
        entry = self._verdicts.get(digest, {}).get(fingerprint)
        if entry is None:
            return None
        defaults = {f.name: f.default for f in fields(ContentResult)}
        return ContentResult(**{name: entry.get(name, default) for name, default in defaults.items()
                                if name in entry or default is not MISSING})

    def put(self, file: Path, fingerprint: str, result: ContentResult) -> None:
        digest = self.digest_of(file)
        if digest:
            self.put_by_digest(digest, fingerprint, result)

    def put_by_digest(self, digest: str, fingerprint: str, result: ContentResult) -> None:
        self._verdicts.setdefault(digest, {})[fingerprint] = asdict(result)
        self._dirty = True

    def prune(self, existing: set[Path]) -> None:
        """Forget files that are no longer there, and verdicts nothing there refers to."""
        keep = {self._key(p) for p in existing}
        for key in [k for k in self._files if k not in keep]:
            del self._files[key]
            self._dirty = True
        referenced = {str(memo.get("digest")) for memo in self._files.values()}
        for digest in [d for d in self._verdicts if d not in referenced]:
            del self._verdicts[digest]
            self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return
        # Whole or nothing: a scan killed mid-save must not leave a cache
        # the next scan reads as empty and then re-extracts everything.
        write_json_atomically(
            self.path,
            {"version": CACHE_VERSION, "files": self._files, "verdicts": self._verdicts},
            indent=1,
        )
        self._dirty = False


# ------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.manifest import load_manifest
    from tracker.scaffold import MANIFEST_FILENAME

    parser = argparse.ArgumentParser(
        description="What does this document say, and which rows accept it? "
                    "Read-only: no cache is written, nothing moves."
    )
    parser.add_argument("engagement_dir", help=f"folder containing {MANIFEST_FILENAME}")
    parser.add_argument("file", help="the document to read")
    ns = parser.parse_args()

    document = Path(ns.file)
    reading = extract(document)
    if reading.text is None:
        print(f"{document.name}: {reading.reason}")
        raise SystemExit(1)
    how = "OCR" if reading.from_ocr else "text layer"
    print(f"{document.name}: {len(reading.text)} characters from the {how}\n")
    for row in load_manifest(Path(ns.engagement_dir) / MANIFEST_FILENAME):
        if not has_content_rules(row):
            continue
        verdict = evaluate_rules(reading.text, row)
        mark = "ok" if verdict.ok else f"no - {verdict.reason}"
        print(f"[{row.identifier}] {row.document}: {mark}")
