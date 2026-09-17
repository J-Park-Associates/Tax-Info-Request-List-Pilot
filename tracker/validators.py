"""Tier 1-2 file validation for the Client Document Tracker (component 3).

Pure, read-only functions over local paths — no dependency on any one sync
provider (OneDrive and Google Drive for desktop both work). Cloud awareness
is limited to :func:`is_cloud_placeholder`, a passive check of Windows
file-attribute flags: on an ordinary desktop file it returns False and
validation proceeds normally, so the whole layer is fully testable with
File Explorer and Excel alone.

- Tier 1 (existence): :func:`iter_candidate_files` / :func:`check_folder` —
  which real files does a request folder contain (junk like ``desktop.ini``,
  ``Thumbs.db``, ``~$`` Office locks excluded)?
- Tier 2 (integrity): :func:`check_file` — extension whitelist, minimum
  size, and a ``pypdf`` open test for PDFs.

Nothing here moves, renames, deletes, or writes client files. Cloud-only
placeholders are never read (reading would force the sync client to download
them); they are reported as ``pending_sync`` and skipped.

Status resolution (Missing/Partial/Received/...) is NOT done here — these
functions report facts; the scanner (component 5) applies policy.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from tracker import reasons
from tracker.manifest import RequestItem

# pypdf logs its own warnings while parsing corrupt files; we already surface
# every failure as a FileResult.reason, so keep the console clean.
logging.getLogger("pypdf").setLevel(logging.ERROR)

# Junk that never counts as a client document.
_IGNORED_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
#: Office lock files.
OFFICE_LOCK_PREFIX = "~$"
#: The one file type whose integrity (and text) can be checked in depth.
PDF_EXTENSION = "pdf"
#: Google Drive stages in-flight transfers inside hidden ".tmp.drive*"
#: folders (.tmp.driveupload / .tmp.drivedownload); anything under one is a
#: partial transfer, not a delivered document, and the folder itself is
#: the sync client's, never the client's.
_SYNC_STAGING_PREFIX = ".tmp.drive"
_IGNORED_PREFIXES = (OFFICE_LOCK_PREFIX, _SYNC_STAGING_PREFIX)
_IGNORED_SUFFIXES = (".tmp", ".driveupload", ".drivedownload")

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


#: Readability verdicts keyed by (path, size, mtime_ns). The router asks
#: check_file() once per manifest row for the same file, and the scanner
#: asks again; parsing a PDF fifteen times to learn the same thing is the
#: cost this saves. Bounded, and a changed file gets a fresh key.
_PDF_VERDICTS: dict[tuple[str, int, int], str] = {}
_PDF_VERDICTS_MAX = 512


def _pdf_error(path: Path) -> str:
    """Empty string if the PDF opens cleanly, else a failure reason.

    Cached per file identity (path, size, mtime), so the same file checked
    against every manifest row is parsed once.
    """
    try:
        stat = path.stat()
        key = (str(path), stat.st_size, stat.st_mtime_ns)
    except OSError:
        return _pdf_error_uncached(path)
    if key in _PDF_VERDICTS:
        return _PDF_VERDICTS[key]
    verdict = _pdf_error_uncached(path)
    if len(_PDF_VERDICTS) >= _PDF_VERDICTS_MAX:
        _PDF_VERDICTS.clear()
    _PDF_VERDICTS[key] = verdict
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


def check_file(path: Path, item: RequestItem) -> FileResult:
    """Tier-2 validation of a single file against one manifest row."""
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
    if item.allowed_extensions and extension not in item.allowed_extensions:
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
        error = _pdf_error(path)
        if error:
            return FileResult(path=path, ok=False, reason=error)

    return FileResult(path=path, ok=True)


def check_folder(folder: Path, item: RequestItem) -> FolderResult:
    """Tier 1 + 2 for one request folder. Read-only; policy-free."""
    exists = folder.is_dir()
    files = [check_file(p, item) for p in iter_candidate_files(folder)]
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
# Desktop today. The real scan (status resolution + manifest write-back)
# is component 5; this prints facts and changes nothing.

if __name__ == "__main__":
    import argparse

    from tracker.manifest import Override, load_manifest
    from tracker.scaffold import (
        MANIFEST_FILENAME,
        README_NAME,
        PREPARED_DIR_NAME,
        REVIEW_DIR_NAME,
        assign_folders,
    )

    parser = argparse.ArgumentParser(
        description="Dry-run validation preview (read-only; writes nothing)"
    )
    parser.add_argument("engagement_dir", help=f"folder containing {MANIFEST_FILENAME}")
    ns = parser.parse_args()

    engagement = Path(ns.engagement_dir)
    items = load_manifest(engagement / MANIFEST_FILENAME)
    prepared = engagement / PREPARED_DIR_NAME
    assigned = assign_folders(prepared, [i.identifier for i in items])

    print(f"Dry-run validation of {prepared}  (nothing is written)\n")
    for item in items:
        if item.manual_override == Override.WAIVED:
            print(f"[{item.identifier}] {item.document}")
            print("    ~ waived - skipped\n")
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

    # Anything loose in Prepared/ or in folders matching no identifier.
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
