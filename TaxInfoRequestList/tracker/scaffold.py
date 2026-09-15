"""Folder scaffolding for the Client Document Tracker (component 2, docs/ROADMAP.md).

Reads an engagement's ``_manifest.xlsx`` and creates the client-facing
``Shared/`` tree: one ``{Identifier} - {Document}`` folder per request row,
plus an auto-generated ``_README.txt`` with client instructions.

Guarantees:

- **Idempotent.** Re-running recreates deleted folders and refreshes the
  README, and does nothing else. Existing folders and the files inside them
  are never touched, renamed, or deleted.
- **Rename-tolerant.** A folder counts as existing if its name starts with
  the item's identifier followed by a non-alphanumeric boundary — the same
  prefix rule the scanner uses — so a client rename like
  ``A01 - bank stuff`` never causes a duplicate ``A01`` folder.
- **Windows-safe names.** Illegal characters (``\\ / : * ? " < > |``) are
  replaced, trailing dots/spaces stripped, and names length-capped.

Waived items (Manual Override = Waived) get no new folder; their existing
folders are left alone and they are dropped from the README.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from tracker.manifest import Override, RequestItem, load_manifest

MANIFEST_FILENAME = "_manifest.xlsx"
SHARED_DIR_NAME = "Shared"
README_NAME = "_README.txt"

#: Characters Windows forbids in file/folder names, plus control chars.
_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
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
    shared_dir: Path, identifiers: Sequence[str]
) -> dict[str, list[Path]]:
    """Map each identifier to the existing folders that belong to it.

    Every subfolder of ``shared_dir`` is assigned to the *longest* matching
    identifier, so with identifiers ``A01`` and ``A01-B`` a folder named
    ``A01-B - Loan Docs`` belongs to ``A01-B`` only. Folders matching no
    identifier are ignored here (the scanner reports them, component 5).
    """
    assigned: dict[str, list[Path]] = {ident: [] for ident in identifiers}
    if not shared_dir.is_dir():
        return assigned
    for child in sorted(shared_dir.iterdir()):
        if not child.is_dir():
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
    created: list[Path] = field(default_factory=list)       # new folders made
    existing: list[str] = field(default_factory=list)       # identifiers already present
    waived: list[str] = field(default_factory=list)         # skipped (Override=Waived)
    readme: Path | None = None


def scaffold_engagement(
    engagement_dir: Path | str,
    *,
    contact: str = "",
) -> ScaffoldResult:
    """Create/refresh the ``Shared/`` tree for one engagement.

    ``engagement_dir`` must contain ``_manifest.xlsx``. Raises
    :class:`tracker.manifest.ManifestError` if it is missing or invalid —
    scaffolding never proceeds from a manifest it can't fully validate.
    """
    engagement_dir = Path(engagement_dir)
    items = load_manifest(engagement_dir / MANIFEST_FILENAME)

    shared_dir = engagement_dir / SHARED_DIR_NAME
    shared_dir.mkdir(parents=True, exist_ok=True)
    result = ScaffoldResult(shared_dir=shared_dir)

    assigned = assign_folders(shared_dir, [i.identifier for i in items])
    for item in items:
        if item.manual_override == Override.WAIVED:
            result.waived.append(item.identifier)
            continue
        if assigned[item.identifier]:
            result.existing.append(item.identifier)
            continue
        folder = shared_dir / folder_name_for(item)
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
        "1. Each document we need has its own folder here.",
        "2. Drag each file INTO its matching folder.",
        "   Please don't leave files loose in this top-level folder.",
        "3. Please don't create new folders or rename these ones.",
        "4. Original PDFs or Excel files are preferred; scans and photos",
        "   are fine as long as they are readable.",
        "5. You can replace a file at any time by dropping in a new copy.",
        "",
        "DOCUMENTS REQUESTED",
        "-" * 45,
    ]
    for item in items:
        entry = f"{item.identifier} - {item.document}"
        if item.period:
            entry += f"  ({item.period})"
        if item.expected_count > 1:
            entry += f"  [{item.expected_count} files expected]"
        lines.append(entry)
    lines.append("")
    if contact:
        lines.append(f"Questions? Contact {contact}.")
        lines.append("")
    lines.append("(This file is generated automatically - edits will be overwritten.)")

    readme = shared_dir / README_NAME
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\r\n")
    return readme


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Scaffold the client-facing Shared/ tree from _manifest.xlsx"
    )
    parser.add_argument("engagement_dir", help="folder containing _manifest.xlsx")
    parser.add_argument("--contact", default="", help="contact line for _README.txt")
    ns = parser.parse_args()

    res = scaffold_engagement(ns.engagement_dir, contact=ns.contact)
    print(f"Shared tree: {res.shared_dir}")
    for folder in res.created:
        print(f"  + created  {folder.name}")
    for ident in res.existing:
        print(f"  = exists   {ident}")
    for ident in res.waived:
        print(f"  ~ waived   {ident} (no folder created)")
    print(f"  * refreshed {res.readme.name}")
