"""Every engagement the scheduled run should touch, found rather than listed (component 10).

There is no registry file. The unattended run is pointed at the folder the
firm keeps its clients in and walks it for engagement folders - any folder
holding ``_manifest.xlsx``. What the run needs to know about each one (who
the client is, the share link, the due date, whether to chase them by email,
whether the engagement is still active) lives on the manifest's own
**Engagement** sheet, written by the wizard when the engagement is created.

That is the whole point. The previous ``engagements.yaml`` was a second list
a person had to keep in step with the folders on disk: a mistyped path or a
client nobody added was a client silently skipped until a filing deadline.
A folder with a manifest in it is an engagement; nothing else has to be
told.

Discovery is bounded and predictable:

- It never descends into an engagement folder once found (``Prepared/`` and
  ``Shared/`` are the engagement's, not other engagements).
- Folders whose names start with ``.`` or ``_`` are skipped (sync staging,
  hidden state).
- Depth is capped so a mistaken root (a whole drive) fails fast instead of
  crawling for an hour.

A manifest that cannot be read is still an engagement: it is listed with its
error so the runner reports it and moves on, exactly as it would for a
folder-level problem. A root that is not a folder, or one with no manifest
under it at all, raises :class:`RegistryError` - that is a typo in the
scheduled task, not an empty practice.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from tracker.manifest import EngagementInfo, ManifestError, load_engagement_info
from tracker.scaffold import MANIFEST_FILENAME, PREPARED_DIR_NAME, SHARED_DIR_NAME

#: How far below the root discovery looks: Clients/{Client}/{Engagement}
#: is two; four leaves room for a year or office level above that.
MAX_DEPTH = 4


class RegistryError(Exception):
    """The clients root could not be walked, or holds no engagement at all."""


@dataclass(frozen=True, slots=True)
class Engagement:
    """One engagement the scheduled run should process."""

    path: Path
    name: str = ""
    client: str = ""
    link: str = ""
    due: dt.date | None = None
    sender: str = ""
    firm: str = ""
    reminders: bool = True
    active: bool = True
    problem: str = ""   # why the manifest could not be read, if it could not

    @property
    def label(self) -> str:
        return self.name or self.path.name


@dataclass(slots=True)
class Registry:
    """Every engagement found under one clients root."""

    source: Path                       # the root that was walked
    engagements: list[Engagement] = field(default_factory=list)

    @property
    def active(self) -> list[Engagement]:
        return [e for e in self.engagements if e.active]

    def find(self, needle: str) -> list[Engagement]:
        """Engagements whose label or path contains ``needle``, case-insensitively."""
        lowered = needle.lower()
        return [
            e for e in self.engagements
            if lowered in e.label.lower() or lowered in str(e.path).lower()
        ]


# ------------------------------------------------------------- discovery ----


def _skip(folder: Path) -> bool:
    name = folder.name
    return name.startswith((".", "_", "~$")) or name in (PREPARED_DIR_NAME, SHARED_DIR_NAME)


def engagement_dirs(root: Path | str, *, max_depth: int = MAX_DEPTH) -> list[Path]:
    """Every folder under ``root`` holding a manifest, sorted, without descending into one."""
    root = Path(root)
    found: list[Path] = []

    def walk(folder: Path, depth: int) -> None:
        if (folder / MANIFEST_FILENAME).is_file():
            found.append(folder)
            return
        if depth >= max_depth:
            return
        try:
            children = sorted(p for p in folder.iterdir() if p.is_dir())
        except OSError:
            return
        for child in children:
            if not _skip(child):
                walk(child, depth + 1)

    walk(root, 0)
    return found


def engagement_from(folder: Path) -> Engagement:
    """One engagement from its folder and Engagement sheet."""
    folder = Path(folder)
    try:
        info: EngagementInfo = load_engagement_info(folder / MANIFEST_FILENAME)
    except ManifestError as exc:
        return Engagement(path=folder, problem=str(exc))
    return Engagement(
        path=folder,
        name=info.name,
        client=info.client,
        link=info.link,
        due=info.due,
        sender=info.sender,
        firm=info.firm,
        reminders=info.reminders,
        active=info.active,
    )


def discover_engagements(root: Path | str, *, max_depth: int = MAX_DEPTH) -> Registry:
    """Walk ``root`` and return every engagement found under it."""
    root = Path(root)
    if not root.is_dir():
        raise RegistryError(f"clients root is not a folder: {root}")
    folders = engagement_dirs(root, max_depth=max_depth)
    if not folders:
        raise RegistryError(
            f"no engagement found under {root} (no folder holding {MANIFEST_FILENAME} "
            f"within {max_depth} levels) - is this the right folder?"
        )
    return Registry(source=root, engagements=[engagement_from(f) for f in folders])


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="List every engagement the scheduled run would find under a clients folder"
    )
    parser.add_argument("root", help="the folder the firm keeps its clients in")
    ns = parser.parse_args()

    try:
        loaded = discover_engagements(ns.root)
    except RegistryError as exc:
        raise SystemExit(f"Registry problem: {exc}")

    print(f"{loaded.source}: {len(loaded.active)} active "
          f"of {len(loaded.engagements)} engagement(s)")
    for engagement in loaded.engagements:
        flags = []
        if not engagement.active:
            flags.append("inactive")
        if not engagement.reminders:
            flags.append("no reminders")
        if engagement.problem:
            flags.append(f"MANIFEST PROBLEM: {engagement.problem}")
        suffix = f"  ({', '.join(flags)})" if flags else ""
        print(f"  {engagement.label}{suffix}")
        print(f"      {engagement.path}")
