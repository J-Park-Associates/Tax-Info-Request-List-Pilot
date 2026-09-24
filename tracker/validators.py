"""Tier 1-2 file validation for the tracker (component 3).

Pure, read-only functions over local paths — no dependency on any one sync
provider (OneDrive and Google Drive for desktop both work). Cloud awareness
is limited to :func:`is_cloud_placeholder`, a passive check of Windows
file-attribute flags: on an ordinary desktop file it returns False and
validation proceeds normally, so the whole layer is fully testable with
File Explorer and Excel alone.

- Tier 1 (existence): :func:`iter_candidate_files` / :func:`check_folder` —
  which real files does a request folder contain (junk like the names in ``_IGNORED_NAMES``,
  ``OFFICE_LOCK_PREFIX`` locks excluded)?
- Tier 2 (integrity): :func:`check_file` — extension whitelist, minimum
  size, a ``pypdf`` open test for PDFs and a Pillow open test for photos.

A photo is a scan of a document (decision 127), so ``IMAGE_EXTENSIONS`` is
accepted by every request that accepts a PDF and opened the way a PDF is
opened: nothing is typed on a row for it, no stored rule changes, and a
file Pillow cannot open is refused with a sentence of its own rather than
reaching the reader as a document.

Nothing here moves, renames, deletes, or writes client files. Cloud-only
placeholders are never read (reading would force the sync client to download
them); they are reported as ``pending_sync`` and skipped.

Status resolution (Missing/Partial/Received/...) is NOT done here — these
functions report facts; the scanner (component 5) applies policy.
"""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from tracker import reasons
from tracker.fsio import TEMP_SUFFIX
from tracker.manifest import RequestItem

# pypdf logs its own warnings while parsing corrupt files; we already surface
# every failure as a FileResult.reason, so keep the console clean.
logging.getLogger("pypdf").setLevel(logging.ERROR)

#: Whether an iPhone's HEIC/HEIF photo can be opened on this machine.
#: ``pillow_heif`` teaches Pillow the format, once, at import - Pillow has
#: no HEIC decoder of its own - and the package is pinned and bundled, so
#: False means somebody is running from a checkout without it. Then a HEIC
#: photo is refused as the firm's problem (``reasons.HEIC_NOT_SUPPORTED``),
#: never the client's: they sent a perfectly ordinary photo.
try:  # pragma: no cover - the absent branch needs the package uninstalled
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIC_READABLE = True
except Exception:  # not installed, or installed and unusable on this machine
    HEIC_READABLE = False

#: The largest drop the reader will open, in megabytes (decision 137, M5).
#: A bigger one is still counted, moved out of the inbox and parked for a
#: person like any other drop - it is never *read*: no text layer, no OCR,
#: no page rendered. Real client documents are far below it (a 30-page
#: scan is a few megabytes); what is above it is a video, a disk image or a
#: whole mailbox, and reading one is how a pass stops. A constant beside
#: the smallest-size rule (each row's ``min_size_kb``), not a setting.
MAX_READ_MB = 250
#: How much of a ``.csv``/``.tsv``/``.txt`` the reader takes, in megabytes
#: (decision 137): enough for any real statement. The rest is not read, and
#: a verdict on a cut text says so (``reasons.TEXT_CUT``).
TEXT_READ_CAP_MB = 20
_MB = 1024 * 1024


def size_mb(path: Path) -> float:
    """The file's size in megabytes, or 0.0 when it cannot be read."""
    try:
        return path.stat().st_size / _MB
    except OSError:
        return 0.0


def too_large_reason(path: Path) -> str:
    """``reasons.TOO_LARGE`` when the file is past :data:`MAX_READ_MB`,
    else ``""``. Asked before anything opens the file."""
    size = size_mb(path)
    if size > MAX_READ_MB:
        return reasons.TOO_LARGE.format(size=f"{size:,.0f} MB")
    return ""


def picture_too_large_reason(exc: BaseException) -> str:
    """``reasons.TOO_LARGE`` for a picture Pillow refused as a decompression
    bomb (decision 137, B1, the owner's ruling on phase 1): a size rule, so
    a kept verdict for a person and never a retry. The pixel count is the
    one Pillow's own sentence names."""
    import re

    said = re.search(r"\((\d+) pixels\)", str(exc))
    if said:
        return reasons.TOO_LARGE.format(size=f"{int(said.group(1)) / 1_000_000:,.0f} megapixels")
    return reasons.TOO_LARGE.format(size="too many pixels")


# Junk that never counts as a client document.
_IGNORED_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
#: Office lock files.
OFFICE_LOCK_PREFIX = "~$"
#: The one file type whose integrity (and text) can be checked in depth.
PDF_EXTENSION = "pdf"
#: An image is a scan of a document: it is accepted by every request that
#: accepts a PDF (decision 127), so a person types nothing new on a row and
#: a list recorded before this decision admits photos the day it lands.
IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "heic", "heif", "tif", "tiff")
#: Google Drive stages in-flight transfers inside hidden ".tmp.drive*"
#: folders (.tmp.driveupload / .tmp.drivedownload); anything under one is a
#: partial transfer, not a delivered document, and the folder itself is
#: the sync client's, never the client's.
_SYNC_STAGING_PREFIX = ".tmp.drive"
_IGNORED_PREFIXES = (OFFICE_LOCK_PREFIX, _SYNC_STAGING_PREFIX)
#: A transfer still in progress, by its name: a sync client's or a browser's
#: partial file. Never sorted, and named in the report as waiting.
UNFINISHED_SUFFIXES = (TEMP_SUFFIX, ".driveupload", ".drivedownload")
_IGNORED_SUFFIXES = UNFINISHED_SUFFIXES

# Google-native documents sync down as tiny shortcut/stub files, not real
# documents. Validating them is impossible locally, so tier 2 fails them with
# an actionable note instead of a confusing size/extension error.
_GOOGLE_STUB_EXTENSIONS = {
    "gdoc", "gsheet", "gslides", "gdraw", "gform",
    "gtable", "gjam", "gsite", "glink", "gshortcut",
}

# Windows file-attribute flags marking cloud-only placeholders. OneDrive
# Files On-Demand and Google Drive for desktop (streaming mode) both mark
# online-only files with these attributes.
_FILE_ATTRIBUTE_OFFLINE = 0x00001000
_FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000
_FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000
_PLACEHOLDER_MASK = (
    _FILE_ATTRIBUTE_OFFLINE
    | _FILE_ATTRIBUTE_RECALL_ON_OPEN
    | _FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
)


# ---------------------------------------------------------------- results ----


@dataclass(frozen=True, slots=True)
class FileResult:
    """Facts about one candidate file."""

    path: Path
    ok: bool
    reason: str = ""            # human-readable tier-2 failure, if any
    pending_sync: bool = False  # cloud-only placeholder; skipped, not failed


@dataclass(slots=True)
class FolderResult:
    """Facts about one request folder (tier 1 + per-file tier 2)."""

    folder: Path
    exists: bool
    files: list[FileResult] = field(default_factory=list)

    @property
    def valid(self) -> list[FileResult]:
        return [f for f in self.files if f.ok]

    @property
    def failed(self) -> list[FileResult]:
        return [f for f in self.files if not f.ok and not f.pending_sync]

    @property
    def pending(self) -> list[FileResult]:
        return [f for f in self.files if f.pending_sync]


# ----------------------------------------------------------------- tier 1 ----





def google_stub_examples(limit: int = 2) -> str:
    """``.gdoc, .gsheet`` - the commonest stub types, for a sentence to a client."""
    common = [ext for ext in ("gdoc", "gsheet", "gslides") if ext in _GOOGLE_STUB_EXTENSIONS]
    return ", ".join(f".{ext}" for ext in common[:limit])


def is_sync_staging(name: str) -> bool:
    """True for a folder name the sync client uses for transfers in flight."""
    return name.lower().startswith(_SYNC_STAGING_PREFIX)


def extension_of(path: Path) -> str:
    """The extension the rules see: lower-case, no dot (``"pdf"``)."""
    return path.suffix.lower().lstrip(".")


def is_ignored(path: Path) -> bool:
    """True for OS/Office/sync junk that never counts as a client document."""
    name = path.name.lower()
    if (
        name in _IGNORED_NAMES
        or name.startswith(_IGNORED_PREFIXES)
        or name.endswith(_IGNORED_SUFFIXES)
    ):
        return True
    return any(is_sync_staging(part) for part in path.parts[:-1])


def google_stub_reason(path: Path) -> str:
    """Why this file is a Google Docs shortcut rather than a document.

    Empty string for anything else. Shared by tier-2 validation and the
    router so the client gets the same actionable sentence either way.
    """
    extension = extension_of(path)
    if extension not in _GOOGLE_STUB_EXTENSIONS:
        return ""
    return reasons.GOOGLE_STUB.format(extension=extension)


def is_cloud_placeholder(path: Path) -> bool:
    """True if ``path`` is a cloud-only placeholder (OneDrive Files
    On-Demand or Google Drive for desktop streaming mode).

    Passive: inspects Windows file-attribute flags only, never opens the
    file (opening would force a download). On non-Windows platforms, or on
    any ordinary local file, this is simply False.
    """
    try:
        attrs = getattr(path.stat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attrs & _PLACEHOLDER_MASK)


def iter_candidate_files(folder: Path) -> list[Path]:
    """All non-junk files under ``folder``, recursively, sorted.

    Recursive because clients drop extracted subfolders inside request
    folders; those files still belong to the request.
    """
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob("*") if p.is_file() and not is_ignored(p))


# ----------------------------------------------------------------- tier 2 ----


class PdfVerdictCache:
    """Readability verdicts for one run, keyed by (path, size, mtime_ns).

    The router asks :func:`check_file` once per manifest row for the same
    file, and the scanner asks again; parsing a PDF fifteen times to learn
    the same thing is the cost this saves. It belongs to a run - the filer
    and the scanner each make one and pass it down - rather than to the
    process, so nothing is shared between runs that might one day be
    concurrent, and a test can never see another test's verdict. Bounded;
    a changed file gets a fresh key.
    """

    def __init__(self, limit: int = 512):
        self._limit = limit
        self._verdicts: OrderedDict[tuple[str, int, int], str] = OrderedDict()

    def get(self, key: tuple[str, int, int]) -> str | None:
        if key not in self._verdicts:
            return None
        self._verdicts.move_to_end(key)
        return self._verdicts[key]

    def put(self, key: tuple[str, int, int], verdict: str) -> None:
        self._verdicts[key] = verdict
        self._verdicts.move_to_end(key)
        while len(self._verdicts) > self._limit:
            self._verdicts.popitem(last=False)


def _pdf_error(path: Path, cache: PdfVerdictCache | None) -> str:
    """Empty string if the PDF opens cleanly, else a failure reason.

    With a cache, keyed by file identity (path, size, mtime), so the same
    file checked against every manifest row is parsed once.
    """
    if cache is None:
        return _pdf_error_uncached(path)
    try:
        stat = path.stat()
        key = (str(path), stat.st_size, stat.st_mtime_ns)
    except OSError:
        return _pdf_error_uncached(path)
    verdict = cache.get(key)
    if verdict is None:
        verdict = _pdf_error_uncached(path)
        cache.put(key, verdict)
    return verdict


def _pdf_error_uncached(path: Path) -> str:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            if not reader.decrypt(""):
                return reasons.PASSWORD_PROTECTED.format()
        if len(reader.pages) == 0:
            return reasons.NO_PAGES.format()
    except Exception as exc:  # pypdf raises many types on corrupt input
        return reasons.UNREADABLE_PDF.format(error=f"{exc.__class__.__name__}: {exc}")
    return ""


def _image_error(path: Path) -> str | None:
    """None if the photo opens cleanly, else the reason it was refused.

    What a PDF gets from ``_pdf_error``, a photo gets here: the file is
    opened and ``verify()``-ed and nothing else - no pixels are decoded, no
    reader is called, and the file on disk is not touched. A HEIC photo an
    iPhone sent needs the local decoder, and a machine without it says so
    as the firm's problem rather than asking the client to re-shoot a
    perfectly good photo.

    No ``PdfVerdictCache``-style memo: ``verify()`` reads a header, which
    is cheap enough to do once per manifest row.
    """
    if extension_of(path) in ("heic", "heif") and not HEIC_READABLE:
        return reasons.HEIC_NOT_SUPPORTED.format()
    try:
        from PIL import Image  # deferred: the reader is only needed for photos

        with Image.open(path) as image:
            image.verify()
    except Image.DecompressionBombError as exc:
        # Past Pillow's own limit (decision 137, B1): a size, not a broken
        # file, so it is ours to look at rather than the client's to resend.
        return picture_too_large_reason(exc)
    except Exception as exc:  # Pillow raises many types on a file that is not one
        return reasons.UNREADABLE_IMAGE.format(error=f"{exc.__class__.__name__}: {exc}")
    return None


def _extension_allowed(extension: str, allowed: tuple[str, ...]) -> bool:
    """Whether a row's whitelist takes this file (decision 127).

    An image is a scan, so a row that accepts a PDF accepts a photo of the
    same document - which is what lets a request list recorded before this
    decision admit photos the day it lands, with no row edited. A row that
    names an image type itself is taken at its word, and a row listing
    ``xlsx, csv`` alone still refuses a photo with the sentence it always
    refused it with.
    """
    if extension in allowed:
        return True
    return extension in IMAGE_EXTENSIONS and PDF_EXTENSION in allowed


def check_file(
    path: Path, item: RequestItem, *, pdf_cache: PdfVerdictCache | None = None
) -> FileResult:
    """Tier-2 validation of a single file against one manifest row.

    ``pdf_cache`` is the run's :class:`PdfVerdictCache`; without one every
    call parses the PDF afresh.
    """
    if is_cloud_placeholder(path):
        return FileResult(
            path=path,
            ok=False,
            pending_sync=True,
            reason=reasons.PENDING_SYNC.format(),
        )

    extension = extension_of(path)
    if stub := google_stub_reason(path):
        return FileResult(path=path, ok=False, reason=stub)
    if item.allowed_extensions and not _extension_allowed(extension, item.allowed_extensions):
        return FileResult(
            path=path,
            ok=False,
            reason=reasons.EXTENSION_NOT_ALLOWED.format(
                extension=extension, allowed=", ".join(item.allowed_extensions)
            ),
        )

    try:
        size = path.stat().st_size
    except OSError as exc:
        # Listed a moment ago, gone now: the sync client is replacing it or
        # the client withdrew it. Either way the row should wait, not fail,
        # and a scheduled scan must never die on one vanished file.
        return FileResult(
            path=path,
            ok=False,
            pending_sync=True,
            reason=reasons.VANISHED.format(error=exc.__class__.__name__),
        )
    if size < item.min_size_kb * 1024:
        return FileResult(
            path=path,
            ok=False,
            reason=reasons.TOO_SMALL.format(size_kb=size / 1024, minimum=item.min_size_kb),
        )

    if extension == PDF_EXTENSION:
        error = _pdf_error(path, pdf_cache)
        if error:
            return FileResult(path=path, ok=False, reason=error)
    elif extension in IMAGE_EXTENSIONS:
        # The same tier, one file type along: a photo that will not open is
        # refused here rather than reaching the reader as a document.
        if photo_error := _image_error(path):
            return FileResult(path=path, ok=False, reason=photo_error)

    return FileResult(path=path, ok=True)


def check_folder(
    folder: Path, item: RequestItem, *, pdf_cache: PdfVerdictCache | None = None
) -> FolderResult:
    """Tier 1 + 2 for one request folder. Read-only; policy-free."""
    exists = folder.is_dir()
    files = [check_file(p, item, pdf_cache=pdf_cache) for p in iter_candidate_files(folder)]
    return FolderResult(folder=folder, exists=exists, files=files)


# ------------------------------------------------------------------ hashes ----


def sha256_of(path: Path) -> str:
    """Content hash used by the scanner to de-duplicate versioned uploads.

    Only call on files that passed the placeholder check — reading a
    cloud-only file forces the sync client to download it.
    """
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------- CLI ----
# Read-only dry-run preview so the whole flow can be exercised from the
# Desktop today. The real scan (status resolution, recorded) is component
# 5; this prints facts and changes nothing.

if __name__ == "__main__":
    import argparse

    from tracker.manifest import Override, load_manifest, override_label
    from tracker.page import tolerant_console
    from tracker.scaffold import (
        PREPARED_DIR_NAME,
        README_NAME,
        REVIEW_DIR_NAME,
        assign_folders,
    )

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description="Dry-run validation preview (read-only; writes nothing)"
    )
    parser.add_argument("engagement_dir", help="the engagement folder")
    ns = parser.parse_args()

    engagement = Path(ns.engagement_dir)
    items = load_manifest(engagement)
    prepared = engagement / PREPARED_DIR_NAME
    assigned = assign_folders(prepared, [i.identifier for i in items])

    print(f"Dry-run validation of {prepared}  (nothing is written)\n")
    for item in items:
        if item.manual_override == Override.NOT_APPLICABLE:
            print(f"[{item.identifier}] {item.document}")
            print(f"    ~ {override_label(item)} - skipped\n")
            continue
        folders = assigned[item.identifier]
        print(f"[{item.identifier}] {item.document}")
        if not folders:
            print(f"    ! {reasons.NO_REQUEST_FOLDER.format()}\n")
            continue
        for folder in folders:
            result = check_folder(folder, item)
            if not result.files:
                print(f"    folder: {folder.name}  -- empty")
            for fr in result.files:
                rel = fr.path.relative_to(folder)
                if fr.pending_sync:
                    print(f"    PEND  {rel}  ({fr.reason})")
                elif fr.ok:
                    print(f"    OK    {rel}")
                else:
                    print(f"    FAIL  {rel}  ({fr.reason})")
            n = len(result.valid)
            print(f"    => {n} valid file(s), expected {item.expected_count}\n")

    # Anything loose in PREPARED_DIR_NAME or in folders matching no identifier.
    claimed = {f for folders in assigned.values() for f in folders}
    if prepared.is_dir():
        loose = [
            p.name
            for p in sorted(prepared.iterdir())
            if (p.is_file() and not is_ignored(p) and p.name != README_NAME)
            or (p.is_dir() and p not in claimed)
        ]
        if loose:
            print(f"Not matched to a request (see {REVIEW_DIR_NAME}):")
            for name in loose:
                print(f"    ? {name}")
