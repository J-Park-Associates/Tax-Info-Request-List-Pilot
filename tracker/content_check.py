"""Tier-3 content validation for the Client Document Tracker (component 4).

Extracts text from client documents (read-only) and applies the deterministic
rules from the manifest row: Required Keywords (ALL must appear), Any
Keywords (at least ONE), and Date Pattern (regex). No rule logic is
hardcoded — everything comes from the manifest.

Extractors by extension:

- ``.pdf``            → pdfplumber; if the PDF has no text layer (a scan),
                        fall back to OCR *if available* (pytesseract +
                        pypdfium2 + Tesseract). The OCR stack is entirely
                        optional: when absent, the file is reported as
                        unverifiable with a clear note — nothing breaks.
- ``.xlsx`` / ``.xlsm`` → openpyxl (all sheets, cached formula values);
                        date cells are rendered in both ISO (2025-12-31)
                        and US (12/31/2025) forms so either pattern style
                        matches.
- ``.csv/.tsv/.txt``  → plain text (utf-8, then cp1252 fallback).
- anything else       → no extractor; reported unverifiable, review manually.

Keyword matching is case-insensitive. Date Pattern is applied to the raw
text as-is, so authors control case sensitivity with inline flags (``(?i)``).

Caching: :class:`ContentCache` stores only *verdicts* — pass/fail + reason —
keyed by ``(path, size, mtime, rules-fingerprint)``. Extracted client text is
deliberately never persisted anywhere. Editing a row's rules changes the
fingerprint and triggers one re-extraction; unchanged files on unchanged
rules are never re-read, which keeps a 15-minute scan cadence cheap.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from tracker.manifest import RequestItem

log = logging.getLogger("tracker.content_check")

# pdfplumber/pdfminer warn loudly on ugly-but-parseable PDFs; failures are
# already surfaced through ContentResult.reason.
logging.getLogger("pdfminer").setLevel(logging.ERROR)

#: A "text" PDF with fewer stripped characters than this is treated as a
#: scan/image-only PDF and routed to the OCR fallback.
_MIN_TEXT_CHARS = 20

#: OCR at most this many pages — identifying keywords/dates live up front,
#: and OCR-ing a 300-page ledger would stall the scan.
_MAX_OCR_PAGES = 10


@dataclass(frozen=True, slots=True)
class ContentResult:
    """Verdict of tier-3 rules for one file."""

    ok: bool
    reason: str = ""
    extractable: bool = True  # False: could not get text (no extractor / no OCR)


# ------------------------------------------------------------------ rules ----


def has_content_rules(item: RequestItem) -> bool:
    return bool(item.required_keywords or item.any_keywords or item.date_pattern)


def rules_fingerprint(item: RequestItem) -> str:
    """Stable hash of the row's tier-3 rules; part of the cache key."""
    blob = json.dumps(
        [list(item.required_keywords), list(item.any_keywords), item.date_pattern]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def evaluate_rules(text: str, item: RequestItem) -> ContentResult:
    """Apply the manifest row's content rules to extracted text."""
    lowered = text.lower()

    missing = [k for k in item.required_keywords if k.lower() not in lowered]
    if missing:
        listed = ", ".join(f"'{k}'" for k in missing)
        return ContentResult(
            ok=False,
            reason=f"required keyword(s) {listed} not found; possible wrong document",
        )

    if item.any_keywords and not any(k.lower() in lowered for k in item.any_keywords):
        listed = ", ".join(item.any_keywords)
        return ContentResult(
            ok=False,
            reason=f"none of the expected keywords found ({listed})",
        )

    if item.date_pattern and not re.search(item.date_pattern, text):
        return ContentResult(
            ok=False,
            reason=(
                f"expected period not found (pattern: {item.date_pattern}); "
                "possible wrong period"
            ),
        )

    return ContentResult(ok=True)


# ------------------------------------------------------------- extraction ----


def _extract_pdf(path: Path) -> str:
    import pdfplumber  # deferred: heavy import, only needed for PDFs

    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


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
    """Extract text from a supported file; None if no extractor exists."""
    extension = path.suffix.lower().lstrip(".")
    if extension == "pdf":
        return _extract_pdf(path)
    if extension in ("xlsx", "xlsm"):
        return _extract_xlsx(path)
    if extension in ("csv", "tsv", "txt"):
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
        return ""  # stack available, this file just wouldn't OCR


# ---------------------------------------------------------------- checking ----


def check_content(
    path: Path, item: RequestItem, cache: "ContentCache | None" = None
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

    if cache is not None:
        cache.put(path, fingerprint, result)
    return result


def _check_uncached(path: Path, item: RequestItem) -> ContentResult:
    extension = path.suffix.lower().lstrip(".")
    try:
        text = extract_text(path)
    except Exception as exc:
        return ContentResult(
            ok=False,
            reason=f"text extraction failed ({exc.__class__.__name__}: {exc})",
            extractable=False,
        )

    if text is None:
        return ContentResult(
            ok=False,
            reason=f"content rules cannot be checked on .{extension} files; review manually",
            extractable=False,
        )

    if extension == "pdf" and len(text.strip()) < _MIN_TEXT_CHARS:
        ocr_text = _ocr_pdf(path)
        if ocr_text is None:
            return ContentResult(
                ok=False,
                reason=(
                    "PDF appears to be a scan with no text layer and OCR is "
                    "not installed; review manually"
                ),
                extractable=False,
            )
        if not ocr_text.strip():
            return ContentResult(
                ok=False,
                reason="no readable text found in PDF, even after OCR; review manually",
                extractable=False,
            )
        text = ocr_text

    return evaluate_rules(text, item)


# ------------------------------------------------------------------- cache ----


class ContentCache:
    """Verdict cache: ``(path, size, mtime, rules-fingerprint) -> ContentResult``.

    Stores only pass/fail verdicts and reasons — never extracted client
    text. Disposable by design: a corrupt or missing cache file simply
    means re-extraction, so it is reset silently.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._dirty = False
        self._entries: dict[str, dict] = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("files"), dict):
                    self._entries = data["files"]
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Content cache reset (unreadable): %s", exc)

    @staticmethod
    def _key(file: Path) -> str:
        return str(file.resolve()).lower()  # Windows paths are case-insensitive

    def get(self, file: Path, fingerprint: str) -> ContentResult | None:
        entry = self._entries.get(self._key(file))
        if entry is None:
            return None
        try:
            stat = file.stat()
        except OSError:
            return None
        if (
            entry.get("size") != stat.st_size
            or entry.get("mtime_ns") != stat.st_mtime_ns
            or entry.get("fp") != fingerprint
        ):
            return None
        return ContentResult(
            ok=bool(entry["ok"]),
            reason=entry.get("reason", ""),
            extractable=bool(entry.get("extractable", True)),
        )

    def put(self, file: Path, fingerprint: str, result: ContentResult) -> None:
        stat = file.stat()
        self._entries[self._key(file)] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "fp": fingerprint,
            "ok": result.ok,
            "reason": result.reason,
            "extractable": result.extractable,
        }
        self._dirty = True

    def prune(self, existing: set[Path]) -> None:
        """Drop entries for files that no longer exist (scanner calls this)."""
        keep = {self._key(p) for p in existing}
        stale = [k for k in self._entries if k not in keep]
        for key in stale:
            del self._entries[key]
            self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return
        payload = json.dumps({"version": 1, "files": self._entries}, indent=1)
        self.path.write_text(payload, encoding="utf-8")
        self._dirty = False
