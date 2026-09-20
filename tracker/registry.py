"""Every engagement the scheduled run should touch, found rather than listed (component 10).

There is no registry file. The unattended run is pointed at the folder the
firm keeps its clients in and walks it for engagement folders - any folder
holding the engagement's own record (``ledger.LEDGER_FILENAME``). What the
run needs to know about each one (who the client is, the share link, the
due date, whether to chase them by email, whether the engagement is still
active) is the engagement's details in that record, written by the wizard
when the engagement is created and edited in the app.

That is the whole point. The previous ``engagements.yaml`` was a second list
a person had to keep in step with the folders on disk: a mistyped path or a
client nobody added was a client silently skipped until a filing deadline.
A folder with a record in it is an engagement; nothing else has to be
told.

**A folder from before decision 104** may hold only the workbook the
tracker used to read (``LEGACY_MANIFEST_FILENAME``) and no record. It is
terminal too - the walk does not descend into it - and it is listed as a
legacy folder with the sentence that says to set it up again in the app
(``LEGACY_FOLDER``), never as an engagement and never imported: the owner
said so. A folder that holds a record with no rules in it and that workbook
beside it is listed the same way, because its rules never reached the
journal.

Discovery is bounded and predictable:

- It never descends into an engagement folder once found (``PREPARED_DIR_NAME/`` and
  ``SHARED_DIR_NAME/`` are the engagement's, not other engagements).
- Folders whose names start with ``.`` or ``_`` are skipped (sync staging,
  hidden state).
- Depth is capped so a mistaken root (a whole drive) fails fast instead of
  crawling for an hour.

A record that cannot be read is still an engagement: it is listed with its
error so the runner reports it and moves on, exactly as it would for a
folder-level problem. A root that is not a folder, or one with no record
under it at all, raises :class:`RegistryError` - that is a typo in the
scheduled task, not an empty practice.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from tracker import ledger, store
from tracker.ledger import LedgerError
from tracker.manifest import ManifestError, load_engagement_info
from tracker.records import EngagementInfo
from tracker.scaffold import PREPARED_DIR_NAME, SHARED_DIR_NAME
from tracker.store import StoreError
from tracker.validators import OFFICE_LOCK_PREFIX, is_sync_staging

#: The workbook the request list lived in until decision 104. Its only
#: reader in the package is the walk below, which uses it to say what a
#: folder holding one and no record is: a legacy folder, not an engagement.
LEGACY_MANIFEST_FILENAME = "_manifest.xlsx"
#: How such a folder is listed, and what the Status Report's "Problem or
#: skipped" cell says of it.
LEGACY_FOLDER = (
    "holds a request list in a workbook the tracker no longer reads ({name}) and no "
    "record; set the engagement up again in the app"
)

#: How a superseded engagement is described, by the run and the app alike.
SKIP_ROLLED_FORWARD = "rolled forward into {successor}"
#: The warning an engagement carries when its Rolled From names no engagement
#: under the root: the prior it was rolled from is not retired and, if it is
#: still under the root by another name, is still chased.
ROLLED_FROM_UNMATCHED = (
    "Rolled From names {rolled_from!r}, which matches no engagement the run can read under this root; "
    "whichever engagement that was is not retired"
)

#: How far below the root discovery looks: Clients/{Client}/{Engagement}
#: is two; four leaves room for a year or office level above that.
MAX_DEPTH = 4


class RegistryError(Exception):
    """The clients root could not be walked, or holds no engagement at all."""


@dataclass(frozen=True, slots=True)
class Engagement:
    """One engagement the scheduled run should process.

    Everything about the client is the engagement's details, held here as
    ``info`` and reachable as attributes (``engagement.client``) so a field
    added to the details is one edit, in one dataclass.
    """

    path: Path
    info: EngagementInfo = EngagementInfo()
    problem: str = ""        # why the record could not be read, if it could not
    superseded_by: str = ""  # the engagement this one was rolled forward INTO
    warning: str = ""        # what its details say that the registry could not act on

    def __getattr__(self, name: str):
        try:
            return getattr(self.info, name)
        except AttributeError:
            raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}") from None

    @property
    def active(self) -> bool:
        return self.info.active and not self.superseded_by

    @property
    def label(self) -> str:
        return self.info.name or self.path.name


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
    return (
        name.startswith((".", "_", OFFICE_LOCK_PREFIX))
        or is_sync_staging(name)
        or name in (PREPARED_DIR_NAME, SHARED_DIR_NAME)
    )


def _walk_engagements(
    root: Path, max_depth: int
) -> tuple[list[Path], list[Path], list[tuple[Path, str]]]:
    """Every folder under ``root`` holding a record, sorted, without
    descending into one; every folder holding only the workbook the
    tracker no longer reads, likewise terminal; and every folder the walk
    could not list, with why. A client's folder an ACL denies the run's
    account would otherwise vanish from the run without a word (the tenth
    reading)."""
    found: list[Path] = []
    legacy: list[Path] = []
    unlisted: list[tuple[Path, str]] = []

    def walk(folder: Path, depth: int) -> None:
        try:
            # A folder that denies the account raises here on POSIX (no
            # search permission) and only on listing on Windows.
            if ledger.path_for(folder).is_file():
                found.append(folder)
                return
            if (folder / LEGACY_MANIFEST_FILENAME).is_file():
                legacy.append(folder)
                return
            if depth >= max_depth:
                return
            children = sorted(p for p in folder.iterdir() if p.is_dir())
        except OSError as exc:
            unlisted.append((folder, f"could not be listed ({exc.strerror or exc})"))
            return
        for child in children:
            if not _skip(child):
                walk(child, depth + 1)

    walk(root, 0)
    return found, legacy, unlisted


def engagement_dirs(root: Path | str, *, max_depth: int = MAX_DEPTH) -> list[Path]:
    """Every folder under ``root`` holding a record, sorted, without descending into one."""
    return _walk_engagements(Path(root), max_depth)[0]


def engagement_from(folder: Path) -> Engagement:
    """One engagement from its folder and the details its record holds.

    A record the readers refuse - a journal that will not parse, a store
    that will not open, a line of the wrong shape, anything else one
    synced folder can surprise a reader with - is listed with the
    sentence, not dropped: one client's record must not end the whole
    practice's pass inside discovery. A record
    that carries no rules with the old workbook beside it is a legacy
    folder: an engagement made before decision 103 whose rules never
    reached the journal, which the owner's word says is set up again in
    the app rather than imported.
    """
    folder = Path(folder)
    try:
        info: EngagementInfo = load_engagement_info(folder)
        rules = store.rules(store.connect(), folder) or []
    except (ManifestError, LedgerError, StoreError) as exc:
        return Engagement(path=folder, problem=str(exc))
    except Exception as exc:        # one folder's surprise, said, not fatal
        return Engagement(path=folder, problem=f"{type(exc).__name__}: {exc}")
    if not rules and (folder / LEGACY_MANIFEST_FILENAME).is_file():
        return Engagement(path=folder, info=info,
                          problem=LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME))
    return Engagement(path=folder, info=info)


def _same_folder(a: str, b: Path) -> bool:
    try:
        return Path(a).resolve() == b.resolve()
    except OSError:
        return False


def _shared_tail(a: str, b: Path) -> int:
    """How many trailing folder names ``a`` and ``b`` have in common."""
    named = [os.path.normcase(part) for part in Path(a).parts]
    folder = [os.path.normcase(part) for part in b.parts]
    count = 0
    while count < len(named) and count < len(folder) and named[-1 - count] == folder[-1 - count]:
        count += 1
    return count


#: How much of a Rolled From path must match an engagement folder, by
#: name, when the path itself no longer resolves: the client's folder and
#: the engagement's.
_TAIL_NAMES = 2


def _prior_of(candidate: Engagement, index: int, engagements: list[Engagement]) -> int | None:
    """Which engagement ``candidate`` was rolled forward from, as an index.

    By the resolved path first. Failing that - Rolled From is written
    absolute, and a clients root that has moved to another drive would
    otherwise bring every retired prior back to life for the draft day -
    by the folder names: the engagement, other than the candidate itself,
    whose path ends in the most of Rolled From's names, at least
    ``_TAIL_NAMES``, and only when that engagement is the only one to do
    so. A layout with a year level above the client (``2025/Smith/1040``
    and ``2026/Smith/1040``) has two engagements sharing the last two
    names, and the third name decides; two that tie decide nothing.
    """
    # A folder the walk could not list, or whose record it could not
    # read, is never taken as the prior: retiring it would turn its report
    # into a benign skip.
    readable = [(position, prior) for position, prior in enumerate(engagements)
                if position != index and not prior.problem]
    for position, prior in readable:
        if _same_folder(candidate.rolled_from, prior.path):
            return position
    tails = {position: _shared_tail(candidate.rolled_from, prior.path) for position, prior in readable}
    if not tails:
        return None
    longest = max(tails.values())
    if longest < _TAIL_NAMES:
        return None
    matches = [position for position, tail in tails.items() if tail == longest]
    return matches[0] if len(matches) == 1 else None


def mark_superseded(engagements: list[Engagement]) -> list[Engagement]:
    """An engagement another one was rolled forward from is finished.

    The rollover never writes to the prior year (it is read-only history),
    so the prior cannot mark itself done. The new engagement's details say
    what it was rolled from, and that is enough: nobody should be chasing
    last year's list once this year's exists. Marked inactive here, with
    the successor named, rather than by a person remembering to open last
    year's engagement and set it inactive.
    """
    successors: dict[int, str] = {}
    unmatched: dict[int, str] = {}
    for index, candidate in enumerate(engagements):
        if not candidate.rolled_from:
            continue
        prior = _prior_of(candidate, index, engagements)
        if prior is not None:
            successors[prior] = candidate.label
        else:
            # Retiring nothing in silence is how last year's list stays
            # chased; the engagement that names the prior carries the word.
            unmatched[index] = ROLLED_FROM_UNMATCHED.format(rolled_from=candidate.rolled_from)
    return [
        replace(e, superseded_by=successors.get(i, ""), warning=unmatched.get(i, e.warning))
        if i in successors or i in unmatched else e
        for i, e in enumerate(engagements)
    ]


def discover_engagements(root: Path | str, *, max_depth: int = MAX_DEPTH) -> Registry:
    """Walk ``root`` and return every engagement found under it."""
    root = Path(root)
    if not root.is_dir():
        raise RegistryError(f"clients root is not a folder: {root}")
    folders, legacy, unlisted = _walk_engagements(root, max_depth)
    if not folders and not legacy and not unlisted:
        raise RegistryError(
            f"no engagement found under {root} (no folder holding {ledger.LEDGER_FILENAME} "
            f"within {max_depth} levels) - is this the right folder?"
        )
    # A folder the walk could not list is listed with its problem, as an
    # unreadable record is, and so is a folder holding only the workbook
    # the tracker no longer reads: whatever engagements they hold are not
    # run, and the run must say so rather than report success without them.
    return Registry(
        source=root,
        engagements=mark_superseded(
            [engagement_from(f) for f in folders]
            + [Engagement(path=folder, problem=LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME))
               for folder in legacy]
            + [Engagement(path=folder, problem=problem) for folder, problem in unlisted]
        ),
    )


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description="List every engagement the scheduled run would find under a clients folder"
    )
    parser.add_argument("root", help="the folder the firm keeps its clients in")
    ns = parser.parse_args()

    try:
        loaded = discover_engagements(ns.root)
    except RegistryError as exc:
        raise SystemExit(f"Registry problem: {exc}") from None

    print(f"{loaded.source}: {len(loaded.active)} active "
          f"of {len(loaded.engagements)} engagement(s)")
    for engagement in loaded.engagements:
        flags = []
        if engagement.superseded_by:
            flags.append(SKIP_ROLLED_FORWARD.format(successor=engagement.superseded_by))
        elif not engagement.active:
            flags.append("inactive")
        if not engagement.reminders:
            flags.append("no reminders")
        if engagement.problem:
            flags.append(f"RECORD PROBLEM: {engagement.problem}")
        if engagement.warning:
            flags.append(f"WARNING: {engagement.warning}")
        suffix = f"  ({', '.join(flags)})" if flags else ""
        print(f"  {engagement.label}{suffix}")
        print(f"      {engagement.path}")
