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
CACHE_VERSION = 3

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
#: name usually carries. One list; the manifest check consults it too.
FORM_VARIANTS: dict[str, tuple[str, ...]] = {
    "1098": ("t", "e", "c", "f", "q"),
    "1099": ("int", "div", "b", "r", "misc", "nec", "oid", "k", "g", "s", "sa",
             "q", "ltc", "patr", "cap", "c", "a", "h", "da"),
    "1095": ("a", "b", "c"),
    "1040": ("sr", "nr", "x", "es", "v", "ss"),
    "1041": ("a", "es", "n", "qft", "t", "v"),
    "1065": ("x", "b"),
    "1120": ("s", "x", "f", "h", "w", "c", "l", "pc", "pol", "reit", "ric", "sf"),
    "941": ("x", "ss", "pr"),
    "990": ("ez", "pf", "t", "n"),
    "5498": ("sa", "esa", "qa"),
    "w2": ("g", "gu", "as", "vi", "c"),
    "w3": ("c", "ss", "pr"),
}
#: What may sit between a number and its variant, or between a keyword's
#: words: nothing ("1098T"), spaces, or any dash a PDF or a keyboard yields.
_JOINER = r"[\s\-‐‑‒–—]*"
_DASHES = re.compile(r"[\s\-‐‑‒–—]")


def _joined_to_a_variant(text: str, keyword: str, match: re.Match[str]) -> bool:
    """True when the matched keyword ends in a form number that ``text``
    continues with one of that form's variants: ``1098`` in "1098-T" or
    "1098 T", ``form 1040`` in "Form-1040-SR"."""
    variants = FORM_VARIANTS.get(_DASHES.sub("", keyword.strip().lower().split()[-1]))
    if not variants:
        return False
    tail = re.compile(rf"{_JOINER}(?:{'|'.join(variants)})(?![a-z0-9])")
    return tail.match(text, match.end()) is not None


def keyword_pattern(keyword: str) -> str | None:
    """The regular expression one keyword is looked for with, or None if blank.

    Whole tokens only. Between a keyword's words, and on either side of a
    dash inside a word, anything a dash can become: ``interest income``
    matches "interest-income" in a file name, ``w-2`` matches "W2" and
    "W–2", ``1099-int`` matches "1099INT".
    """
    words = [_JOINER.join(re.escape(part) for part in w.split("-"))
             for w in keyword.strip().lower().split()]
    if not words or not any(words):
        return None
    return rf"(?<![a-z0-9]){_JOINER.join(words)}(?![a-z0-9])"


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
    pattern = keyword_pattern(keyword)
    if pattern is None:
        return False
    text = text.lower()
    return any(not _joined_to_a_variant(text, keyword, m) for m in re.finditer(pattern, text))


def evaluate_rules(text: str, item: RequestItem) -> ContentResult:
    """Apply the manifest row's content rules to extracted text."""
    missing = [k for k in item.required_keywords if not contains_keyword(text, k)]
    if missing:
        listed = ", ".join(f"'{k}'" for k in missing)
        return ContentResult(ok=False, reason=reasons.WRONG_DOCUMENT.format(listed=listed))

    if item.any_keywords and not any(
        contains_keyword(text, k) for k in item.any_keywords
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

    parts: list[str] = []
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            parts.append(str(ws.title))
            for row in ws.iter_rows(values_only=True):
                for value in row:
                    if value is None:
                        continue
                    if isinstance(value, (dt.datetime, dt.date)):
                        # Both forms, so ISO- and US-style patterns match.
                        d = value.date() if isinstance(value, dt.datetime) else value
                        parts.append(f"{d.isoformat()} {d.month}/{d.day}/{d.year}")
                    else:
                        parts.append(str(value))
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
