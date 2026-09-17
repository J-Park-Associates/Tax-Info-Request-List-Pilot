"""Folder scaffolding for the Client Document Tracker (component 2, docs/ROADMAP.md).

Reads an engagement's ``_manifest.xlsx`` and lays out both sides of one
engagement:

- **Client side** — ``Shared/``, a single folder the client drops everything
  into, with ``Shared/PBC/`` holding the originals once
  :mod:`tracker.filer` has sorted them, and an auto-generated
  ``_README.txt`` telling the client they need not sort anything.
- **Firm side** — ``Prepared/``, one ``{Identifier} - {Document}`` folder per
  request row for the renamed working copies, plus ``00 - Needs Review``
  for anything the rules could not confidently identify.

Guarantees:

- **Idempotent.** Re-running recreates deleted folders and refreshes the
  README (only when its text changed), and does nothing else. Existing
  folders and the files inside them are never touched, renamed, or deleted.
  The scheduled run scaffolds on every pass, so a row added in Excel has
  its folder and its README line by the next run without anyone asking.
- **Rename-tolerant.** A folder counts as existing if its name starts with
  the item's identifier followed by a non-alphanumeric boundary — the same
  prefix rule the scanner uses — so a client rename like
  ``A01 - bank stuff`` never causes a duplicate ``A01`` folder.
- **Windows-safe names.** Illegal characters (``manifest.WINDOWS_ILLEGAL_CHARS``)
  are replaced, trailing dots/spaces stripped, and names length-capped.

Waived items (Manual Override = Waived) get no new folder; their existing
folders are left alone and they are dropped from the README.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from tracker.reasons import GOOGLE_EXPORT_HINT
from tracker.validators import google_stub_examples
from tracker.manifest import (
    ENGAGEMENT_SHEET_NAME,
    WINDOWS_ILLEGAL_CHARS,
    Override,
    RequestItem,
    load_engagement_info,
    load_manifest,
)

MANIFEST_FILENAME = "_manifest.xlsx"
SHARED_DIR_NAME = "Shared"
README_NAME = "_README.txt"
#: Heads the client README's request list.
README_HEADING = "WHAT WE STILL NEED"

#: The client's untouched originals, inside the folder they can see.
PBC_DIR_NAME = "PBC"
#: The firm's working set: renamed copies, one folder per request.
PREPARED_DIR_NAME = "Prepared"
#: Where anything the rules could not confidently identify waits for a human.
REVIEW_DIR_NAME = "00 - Needs Review"

#: The one list of characters Windows forbids lives in tracker.manifest.
_ILLEGAL_CHARS = WINDOWS_ILLEGAL_CHARS
_MAX_FOLDER_NAME = 100


# ----------------------------------------------------------------- naming ----


def sanitize_component(text: str) -> str:
    """Make ``text`` safe as (part of) a Windows folder name."""
    cleaned = _ILLEGAL_CHARS.sub("-", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.rstrip(". ")


def folder_name_for(item: RequestItem) -> str:
    """Canonical folder name for a request item: ``{Identifier} - {Document}``."""
    name = f"{sanitize_component(item.identifier)} - {sanitize_component(item.document)}"
    return name[:_MAX_FOLDER_NAME].rstrip(". ")


def matches_identifier(folder_name: str, identifier: str) -> bool:
    """True if ``folder_name`` starts with ``identifier`` at a word boundary.

    Case-insensitive (Windows filesystems are). ``A1`` does not match
    ``A10 - ...`` because the character after the prefix must be
    non-alphanumeric (or end of string).
    """
    name = folder_name.strip().lower()
    prefix = identifier.strip().lower()
    if not prefix or not name.startswith(prefix):
        return False
    rest = name[len(prefix):]
    return rest == "" or not rest[0].isalnum()


def assign_folders(
    parent_dir: Path, identifiers: Sequence[str]
) -> dict[str, list[Path]]:
    """Map each identifier to the existing folders that belong to it.

    Every subfolder of ``parent_dir`` is assigned to the *longest* matching
    identifier, so with identifiers ``A01`` and ``A01-B`` a folder named
    ``A01-B - Loan Docs`` belongs to ``A01-B`` only. Folders matching no
    identifier are ignored here (the scanner reports them, component 5).
    """
    assigned: dict[str, list[Path]] = {ident: [] for ident in identifiers}
    if not parent_dir.is_dir():
        return assigned
    for child in sorted(parent_dir.iterdir()):
        if not child.is_dir():
            continue
        # The review folder belongs to nobody. An identifier such as "00"
        # would otherwise claim it and count every parked file as its own.
        if child.name.lower() == REVIEW_DIR_NAME.lower():
            continue
        best: str | None = None
        for ident in identifiers:
            if matches_identifier(child.name, ident):
                if best is None or len(ident) > len(best):
                    best = ident
        if best is not None:
            assigned[best].append(child)
    return assigned


# --------------------------------------------------------------- scaffold ----


@dataclass(slots=True)
class ScaffoldResult:
    shared_dir: Path
    prepared_dir: Path | None = None                        # firm-side working set
    pbc_dir: Path | None = None                             # client's originals
    created: list[Path] = field(default_factory=list)       # new folders made
    existing: list[str] = field(default_factory=list)       # identifiers already present
    waived: list[str] = field(default_factory=list)         # skipped (Override=Waived)
    readme: Path | None = None


def scaffold_engagement(
    engagement_dir: Path | str,
    *,
    contact: str | None = None,
) -> ScaffoldResult:
    """Create/refresh the ``Shared/`` tree for one engagement.

    ``engagement_dir`` must contain ``_manifest.xlsx``. Raises
    :class:`tracker.manifest.ManifestError` if it is missing or invalid —
    scaffolding never proceeds from a manifest it can't fully validate.

    The README's "Questions? Contact ..." line comes from the manifest's
    Engagement sheet (firm, else sender) unless ``contact`` is given, so the
    client's README and the reminder's sign-off never disagree.
    """
    engagement_dir = Path(engagement_dir)
    items = load_manifest(engagement_dir / MANIFEST_FILENAME)
    if contact is None:
        info = load_engagement_info(engagement_dir / MANIFEST_FILENAME)
        contact = info.firm or info.sender

    # Client side: one folder to drop into, plus the originals we keep.
    shared_dir = engagement_dir / SHARED_DIR_NAME
    shared_dir.mkdir(parents=True, exist_ok=True)
    pbc_dir = shared_dir / PBC_DIR_NAME
    pbc_dir.mkdir(exist_ok=True)

    # Firm side: one folder per request, plus somewhere for the unclear.
    prepared_dir = engagement_dir / PREPARED_DIR_NAME
    prepared_dir.mkdir(exist_ok=True)
    (prepared_dir / REVIEW_DIR_NAME).mkdir(exist_ok=True)

    result = ScaffoldResult(
        shared_dir=shared_dir, prepared_dir=prepared_dir, pbc_dir=pbc_dir
    )

    assigned = assign_folders(prepared_dir, [i.identifier for i in items])
    for item in items:
        if item.manual_override == Override.WAIVED:
            result.waived.append(item.identifier)
            continue
        if assigned[item.identifier]:
            result.existing.append(item.identifier)
            continue
        folder = prepared_dir / folder_name_for(item)
        folder.mkdir(exist_ok=True)  # identifiers are unique, so names are too
        result.created.append(folder)

    active = [i for i in items if i.manual_override != Override.WAIVED]
    result.readme = _write_readme(shared_dir, engagement_dir.name, active, contact)
    return result


def _write_readme(
    shared_dir: Path,
    engagement_name: str,
    items: Iterable[RequestItem],
    contact: str,
) -> Path:
    lines = [
        "HOW TO SEND US YOUR DOCUMENTS",
        "=" * 45,
        "",
        f"Engagement: {engagement_name}",
        "",
        "Just drop everything into this folder. One folder, that's it -",
        "you don't need to sort anything or name anything. We sort it.",
        "",
        "1. Drag your documents anywhere in this folder.",
        f"2. Within a few minutes each file moves into the {PBC_DIR_NAME} folder.",
        "   That is us filing it - your file is safe, unchanged, and still",
        "   yours to look at. Nothing is ever renamed or deleted.",
        "3. Keep going until the list below is covered. Send them as you",
        "   find them; there's no need to wait and send everything at once.",
        "4. Original PDFs or Excel files are preferred; scans and photos",
        "   are fine as long as they are readable.",
        "5. If a document lives in Google Docs or Google Sheets, please",
        f"   download it first ({GOOGLE_EXPORT_HINT}) and upload",
        f"   that copy - Google shortcut files ({google_stub_examples()}) can't be read.",
        "6. To replace something, just drop in the new copy.",
        "",
        README_HEADING,
        "-" * 45,
    ]
    for item in items:
        entry = item.label
        if item.expected_text:
            entry += f"  [{item.expected_text}]"
        lines.append(entry)
    lines.append("")
    if contact:
        lines.append(f"Questions? Contact {contact}.")
        lines.append("")
    lines.append("(This file is generated automatically - edits will be overwritten.)")

    readme = shared_dir / README_NAME
    text = "\n".join(lines) + "\n"
    # Scaffolding now runs on every scheduled pass; rewriting an unchanged
    # README would make the sync client push a "new" file to the client
    # every time.
    try:
        if readme.read_text(encoding="utf-8") == text:
            return readme
    except OSError:
        pass
    readme.write_text(text, encoding="utf-8", newline="\r\n")
    return readme


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=f"Lay out {SHARED_DIR_NAME}/ (client drop folder) and {PREPARED_DIR_NAME}/ from {MANIFEST_FILENAME}"
    )
    parser.add_argument("engagement_dir", help=f"folder containing {MANIFEST_FILENAME}")
    parser.add_argument("--contact", default=None,
                        help=f"contact line for {README_NAME} (default: the {ENGAGEMENT_SHEET_NAME} sheet's firm)")
    ns = parser.parse_args()

    res = scaffold_engagement(ns.engagement_dir, contact=ns.contact)
    print(f"Client drop folder: {res.shared_dir}")
    print(f"Prepared tree:      {res.prepared_dir}")
    for folder in res.created:
        print(f"  + created  {folder.name}")
    for ident in res.existing:
        print(f"  = exists   {ident}")
    for ident in res.waived:
        print(f"  ~ waived   {ident} (no folder created)")
    print(f"  * refreshed {res.readme.name}")
