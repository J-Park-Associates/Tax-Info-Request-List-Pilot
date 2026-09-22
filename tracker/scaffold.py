"""Folder scaffolding for the tracker (component 2, docs/ROADMAP.md).

Reads an engagement's request list from the record
(:func:`tracker.manifest.load_manifest`) and lays out both sides of one
household - the two trees :mod:`tracker.layout` names:

- **Client side** — the household's folder, its one permanent inbox
  (``layout.INBOX_DIR_NAME``), one folder per open tax year holding the
  originals once :mod:`tracker.filer` has moved them out of that inbox,
  and an auto-generated ``README_NAME`` in the inbox telling the client
  they need not sort anything.
- **Firm side** — inside each return, ``PREPARED_DIR_NAME``, one folder per
  request row (named by ``folder_name_for``) for the renamed working copies,
  plus ``REVIEW_DIR_NAME`` for anything the rules could not confidently
  identify.

One inbox serves every return of the household, so the README is written
once for the household and lists what each return still needs under its own
sub-heading: a client is told about one folder and keeps using it, whether
they have one return or ten (decision 125).

Guarantees:

- **Idempotent.** Re-running recreates deleted folders and refreshes the
  README (only when its text changed), and does nothing else. Existing
  folders and the files inside them are never touched, renamed, or deleted.
  The scheduled run scaffolds on every pass, so a row added in the app has
  its folder and its README line by the next run without anyone asking.
- **Rename-tolerant.** A folder counts as existing if its name starts with
  the item's identifier followed by a non-alphanumeric boundary — the same
  prefix rule the scanner uses — so a client rename like
  ``A01 - bank stuff`` never causes a duplicate ``A01`` folder.
- **Windows-safe names.** Illegal characters (``manifest.WINDOWS_ILLEGAL_CHARS``)
  are replaced, trailing dots/spaces stripped, and names length-capped.

Not Applicable items (``Override.NOT_APPLICABLE``) get no new folder;
their existing folders are left alone and they are dropped from the README.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from tracker.fsio import write_text_atomically
from tracker.layout import (
    INBOX_DIR_NAME,
    PREPARED_DIR_NAME,
    README_NAME,
    REVIEW_DIR_NAME,
    client_household_dir,
    household_of,
    inbox_dir_for,
    originals_dir_for,
    root_of,
    year_of,
)
from tracker.manifest import (
    WINDOWS_ILLEGAL_CHARS,
    Override,
    RequestItem,
    label_for,
    load_engagement_info,
    load_manifest,
)
from tracker.reasons import GOOGLE_EXPORT_HINT
from tracker.validators import google_stub_examples

log = logging.getLogger("tracker.scaffold")

#: Heads the client README's request list.
README_HEADING = "WHAT WE STILL NEED"

# ``PREPARED_DIR_NAME``, ``REVIEW_DIR_NAME`` and ``README_NAME`` are
# imported above rather than declared here: the shape of the clients root
# is worded once, in tracker.layout, since decision 125. They are still
# read from this module by the callers that have always read them from it.

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
    """Canonical folder name for a request item: identifier and document, joined."""
    name = label_for(sanitize_component(item.identifier), sanitize_component(item.document))
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
    inbox: Path                                             # the household's one drop folder
    prepared_dir: Path | None = None                        # firm-side working set
    originals_dir: Path | None = None                       # the year's originals, client-side
    created: list[Path] = field(default_factory=list)       # new folders made
    existing: list[str] = field(default_factory=list)       # identifiers already present
    not_applicable: list[str] = field(default_factory=list)  # skipped (Override.NOT_APPLICABLE)
    readme: Path | None = None

    def describe(self) -> list[str]:
        """The three lines every CLI prints about a laid-out return."""
        return [f"Client inbox:     {self.inbox}",
                f"Originals folder: {self.originals_dir}",
                f"Prepared tree:    {self.prepared_dir}"]


@dataclass(slots=True)
class HouseholdScaffold:
    """What one household's client side is: its folder, its inbox and the
    README in it."""

    client_dir: Path
    inbox: Path
    readme: Path | None = None
    #: One per open year of the household's returns, in year order.
    originals: list[Path] = field(default_factory=list)


def scaffold_household(
    household_dir: Path | str,
    *,
    returns: list[Path] | None = None,
    contact: str | None = None,
) -> HouseholdScaffold:
    """Create/refresh one household's client side: its folder, its inbox and
    a year folder per open year, with the README in the inbox.

    ``household_dir`` is the household's folder in the **private** tree -
    the one holding its record - because that is what every caller has in
    hand: the return folder knows its household positionally
    (``layout.household_of``). ``returns`` is the household's return
    folders when the caller has read them; left out, they are found on
    disk (``households.household_returns``).

    Idempotent: re-running makes back a folder somebody deleted and
    refreshes the README only when its text changed, and does nothing
    else. Nothing already there is touched, renamed or deleted.

    **With two open years nothing is rewritten.** The pass sorts nothing
    from an inbox that cannot say which year a document is for, so the
    README would be telling the client to send things into a folder the
    pass is not reading; the app and the practice page say why instead
    (``tracker.runner.TWO_OPEN_YEARS``).
    """
    from tracker.households import household_returns, load_household_info, open_years

    household_dir = Path(household_dir)
    # The private household folder is root/PRIVATE_TREE/<household>, so the
    # root is two levels up: the one arithmetic this needs, and it is the
    # same positional rule discovery walks by.
    root = household_dir.parent.parent
    household = household_dir.name
    client_dir = client_household_dir(root, household)
    inbox = inbox_dir_for(root, household)
    inbox.mkdir(parents=True, exist_ok=True)

    folders = list(returns) if returns is not None else household_returns(household_dir)
    # A return whose record the readers refuse is passed over rather than
    # taking the household's own side down with it: the pass says that
    # return's problem in its own row, and the client's inbox is still
    # laid out for the returns that can be read.
    engagements = [one for one in (_ReturnLine.of(folder) for folder in folders) if one is not None]
    # A prior another return of this household was rolled forward from is
    # finished with, exactly as ``tracker.registry.mark_superseded`` says:
    # the rollover never writes to last year, so the successor's own Rolled
    # From is what retires it - and a household the year after a rollover
    # would otherwise read as two open years and be told nothing.
    retired = {_resolved(one.info.rolled_from) for one in engagements if one.info.rolled_from}
    for one in engagements:
        one.superseded = _resolved(one.path) in retired
    years = open_years(engagements)
    result = HouseholdScaffold(client_dir=client_dir, inbox=inbox)
    for year in years:
        originals = originals_dir_for(root, household, year)
        originals.mkdir(parents=True, exist_ok=True)
        result.originals.append(originals)

    if contact is None:
        try:
            contact = load_household_info(household_dir).contact
        except Exception:               # a household with no record yet
            contact = ""
    if len(years) != 1:
        # Nothing is sorted from this inbox, so the README says nothing new.
        result.readme = inbox / README_NAME
        return result
    [year] = years
    active = [(one, [i for i in one.items if i.manual_override != Override.NOT_APPLICABLE])
              for one in engagements if one.active and one.tax_year == year]
    fallback = next((one.info.firm or one.info.sender for one, _ in active), "")
    result.readme = _write_readme(inbox, household, year, active, contact or fallback)
    return result


def _resolved(path) -> Path:
    """One folder as a comparison can use it. Rolled From is written
    absolute, and a root that has moved would otherwise resolve to
    nothing: an unresolvable path compares as itself."""
    try:
        return Path(path).resolve()
    except OSError:
        return Path(path)


@dataclass(slots=True)
class _ReturnLine:
    """One return as the README and the open-year rule read it: its folder,
    its details and its list. Read once per return, here, so the scaffold
    does not open the record twice for one folder."""

    path: Path
    info: object
    items: list[RequestItem]
    #: Whether another return of this household was rolled forward from it.
    superseded: bool = False

    @classmethod
    def of(cls, folder: Path) -> _ReturnLine | None:
        try:
            return cls(path=folder, info=load_engagement_info(folder), items=load_manifest(folder))
        except Exception as exc:
            log.warning("Could not read %s for the household's README (%s)", folder.name, exc)
            return None

    @property
    def active(self) -> bool:
        return bool(self.info.active) and not self.superseded

    @property
    def tax_year(self) -> int | None:
        return self.info.tax_year if self.info.tax_year is not None else year_of(self.path)

    @property
    def return_name(self) -> str:
        return self.info.return_name or self.path.name


def scaffold_engagement(
    engagement_dir: Path | str,
    *,
    contact: str | None = None,
) -> ScaffoldResult:
    """Create/refresh one return's ``PREPARED_DIR_NAME/`` tree, and its
    household's client side with it.

    ``engagement_dir`` must hold a record. Raises
    :class:`tracker.manifest.ManifestError` if it holds none — scaffolding
    never proceeds from a list nobody has recorded.

    The household's side is laid out too, so a return made on its own
    still has its inbox and its year folder; the README lists every return
    of the open year, which is why it is written there and not here.
    ``contact`` overrides the household's contact line, so the client's
    README and the reminder's sign-off never disagree.
    """
    engagement_dir = Path(engagement_dir)
    items = load_manifest(engagement_dir)

    # Firm side: one folder per request, plus somewhere for the unclear.
    prepared_dir = engagement_dir / PREPARED_DIR_NAME
    prepared_dir.mkdir(parents=True, exist_ok=True)
    (prepared_dir / REVIEW_DIR_NAME).mkdir(exist_ok=True)

    # Client side: the household's one inbox and the year's originals.
    household = scaffold_household(household_of(engagement_dir), contact=contact)
    year = year_of(engagement_dir)
    originals_dir = (originals_dir_for(root_of(engagement_dir),
                                       household_of(engagement_dir).name, year)
                     if year is not None else None)

    result = ScaffoldResult(
        inbox=household.inbox, prepared_dir=prepared_dir, originals_dir=originals_dir,
        readme=household.readme,
    )

    assigned = assign_folders(prepared_dir, [i.identifier for i in items])
    for item in items:
        if item.manual_override == Override.NOT_APPLICABLE:
            result.not_applicable.append(item.identifier)
            continue
        if assigned[item.identifier]:
            result.existing.append(item.identifier)
            continue
        folder = prepared_dir / folder_name_for(item)
        folder.mkdir(exist_ok=True)  # identifiers are unique, so names are too
        result.created.append(folder)
    return result


def _write_readme(
    inbox: Path,
    household: str,
    year: int,
    returns: Iterable[tuple[_ReturnLine, list[RequestItem]]],
    contact: str,
) -> Path:
    lines = [
        "HOW TO SEND US YOUR DOCUMENTS",
        "=" * 45,
        "",
        f"Household: {household}",
        "",
        "Just drop everything into this folder. One folder, that's it -",
        "you don't need to sort anything or name anything. We sort it.",
        "",
        "1. Drag your documents anywhere in this folder.",
        f"2. Each file moves into your {year} folder on the next scheduled pass.",
        "   That is us filing it - your file is safe, unchanged, and still",
        "   yours to look at. Nothing is ever renamed or deleted.",
        "3. Keep going until the lists below are covered. Send them as you",
        "   find them; there's no need to wait and send everything at once.",
        "4. Original PDFs or Excel files are preferred; scans and photos",
        "   are fine as long as they are readable.",
        # Decision 128, Jason's sign-off: a named request files only where
        # the name is on the page, and a report sent as its middle pages
        # has no name on it. Asked once, in the client's own words.
        "   Statements and reports should show the name they were issued",
        "   to - please send the whole page, with its header.",
        "5. If a document lives in Google Docs or Google Sheets, please",
        f"   download it first ({GOOGLE_EXPORT_HINT}) and upload",
        f"   that copy - Google shortcut files ({google_stub_examples()}) can't be read.",
        "6. To replace something, just drop in the new copy.",
        "",
        README_HEADING,
        "-" * 45,
    ]
    for one, items in returns:
        lines.append(one.return_name)
        for item in items:
            entry = f"  {item.label}"
            if item.expected_text:
                entry += f"  [{item.expected_text}]"
            lines.append(entry)
    lines.append("")
    if contact:
        lines.append(f"Questions? Contact {contact}.")
        lines.append("")
    lines.append("(This file is generated automatically - edits will be overwritten.)")

    readme = inbox / README_NAME
    text = "\n".join(lines) + "\n"
    # Scaffolding now runs on every scheduled pass; rewriting an unchanged
    # README would make the sync client push a "new" file to the client
    # every time.
    try:
        if readme.read_text(encoding="utf-8") == text:
            return readme
    except OSError:
        pass
    # Client-visible and cosmetic: a sync client uploading it, a viewer
    # holding it, or a folder the client made under its name must not stop
    # the sort and the scan behind it. Written whole; a failure is a log line.
    try:
        write_text_atomically(readme, text, encoding="utf-8", newline="\r\n")
    except OSError as exc:
        log.warning("Could not refresh %s (%s); the pass goes on", readme.name, exc)
    return readme


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description=f"Lay out the household's {INBOX_DIR_NAME!r} inbox and this return's "
                    f"{PREPARED_DIR_NAME}/ from the request list"
    )
    parser.add_argument("engagement_dir", help="the return folder")
    parser.add_argument("--contact", default=None,
                        help=f"contact line for {README_NAME} (default: the household's contact)")
    ns = parser.parse_args()

    res = scaffold_engagement(ns.engagement_dir, contact=ns.contact)
    for line in res.describe():
        print(line)
    for folder in res.created:
        print(f"  + created  {folder.name}")
    for ident in res.existing:
        print(f"  = exists   {ident}")
    for ident in res.not_applicable:
        print(f"  ~ set aside {ident} (no folder created)")
    print(f"  * refreshed {res.readme.name}")
