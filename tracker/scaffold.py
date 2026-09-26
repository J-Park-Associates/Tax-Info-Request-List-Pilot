"""Folder scaffolding for the tracker (component 2, docs/ROADMAP.md).

Reads an engagement's request list from the record
(:func:`tracker.manifest.load_manifest`) and lays out both sides of one
household - the two trees :mod:`tracker.layout` names:

- **Client side** — the household's folder, its one permanent inbox
  (``layout.INBOX_DIR_NAME``), one folder per open tax year holding the
  originals once :mod:`tracker.filer` has moved them out of that inbox,
  and an auto-generated ``README_NAME`` in the inbox telling the client
  they need not sort anything.
- **Firm side** — inside each return, ``PREPARED_DIR_NAME``, where the
  renamed working copies sit side by side, each named by its request
  (``A01 - W-2 - TY2025.pdf``), plus ``REVIEW_DIR_NAME`` for anything the
  rules could not confidently identify.

**No folder per request** (decision 168). Until then every request had a
folder in ``PREPARED_DIR_NAME`` named ``<identifier> - <short name>``, made
by this module on every pass, and every copy inside it began with the same
words again. The name already says which request a copy is for - decision
19 made every identifier survive as a prefix, and decision 144 put it at
the front of every copy's name - so the folder was a second copy of the
name's first half. A file belongs to the request whose identifier its name
starts with, the longest one at a word boundary (:func:`assign_files`, the
rule ``assign_folders`` applied to folders until then), and every
reader asks that one function. A folder a person makes inside
``PREPARED_DIR_NAME`` is theirs: nothing is filed into it and nothing in it
is counted (``reasons.PERSONS_FOLDER``). A return made before 168 keeps
its request folders exactly as they are, and they are read as a person's
folders: there is no migration (decision 125's one layout).

One inbox serves every return of the household, so the README is written
once for the household and lists what each return has not yet received under
its own sub-heading: a client is told about one folder and keeps using it, whether
they have one return or ten (decision 125).

**The README has one composer** (decision 130): :func:`write_readme` is the
only function that writes ``README_NAME``, and laying out folders no longer
writes it. Since 130 the README also acknowledges what has arrived - a
*WHAT WE HAVE RECEIVED* section after the list - and what has arrived is
the index's to say, which this module may not read (it sits at layer 1,
the filer at layer 3). So the section is handed in as plain data
(:class:`tracker.records.Received`, read by ``tracker.filer.received_for``)
and only rendered here; ``tracker.filer.refresh_household_readme`` is the
one call every caller makes - the household pass once after its sort, the
rollover, and every app action that changes a return or a document's row.
A second writer would be a second opinion of what the client was told.

Guarantees:

- **Idempotent.** Re-running recreates deleted folders, and does nothing
  else. Existing folders and the files inside them are never touched,
  renamed, or deleted. The scheduled run scaffolds on every pass; the
  README is refreshed (only when its text changed) by the same pass.
- **Rename-tolerant.** A file belongs to a request if its name starts with
  the identifier followed by a non-alphanumeric boundary, so a copy a
  person renamed ``A01 - bank stuff.pdf`` is still A01's.
- **Windows-safe names.** Illegal characters (``layout.WINDOWS_ILLEGAL_CHARS``)
  are replaced and trailing dots/spaces stripped (:func:`sanitize_component`)
  in a working copy's file name. A household or a return name is never
  sanitised: it is held to the layout's one name rule and refused
  (``layout.segment_problem``, decision 188).

Not Applicable items (``Override.NOT_APPLICABLE``) are dropped from the
README.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from tracker import door
from tracker.fsio import write_text_atomically
from tracker.layout import (
    INBOX_DIR_NAME,
    PREPARED_DIR_NAME,
    README_NAME,
    REVIEW_DIR_NAME,
    WINDOWS_ILLEGAL_CHARS,
    client_household_dir,
    clients_tree_of,
    household_of,
    inbox_dir_for,
    is_reserved_name,
    originals_dir_for,
    root_of,
    same_folder_name,
    same_return,
    year_of,
)
from tracker.manifest import (
    Override,
    RequestItem,
    load_engagement_info,
    load_manifest,
)
from tracker.reasons import GOOGLE_EXPORT_HINT, IN_CONSOLIDATED_CLIENT
from tracker.records import Received, ReceivedLine
from tracker.validators import google_stub_examples, is_ignored

log = logging.getLogger("tracker.scaffold")

#: Heads the client README's request list, in Jason's words (decision 130,
#: his decision of 2026-09-23, which replaces decision 124's D-1 for the
#: README): the list holds only the requests nothing has been received for,
#: so a client never reads a document as both needed and received.
README_HEADING = "REQUESTED, NOT YET RECEIVED"
#: The first line of every README the firm writes (decision 179), and how
#: a file at ``README_NAME`` in an inbox is told to be the firm's rather
#: than one the client dropped under that name: the README was skipped by
#: the sort and written over by every refresh, so a client's own file of
#: that name was replaced unread - a client's file destroyed, which
#: the standing rules forbid - and one past a gigabyte was read whole into
#: memory on every refresh to decide whether to rewrite it.
README_FIRST_LINE = "HOW TO SEND US YOUR DOCUMENTS"
#: The most a README the firm writes could hold - every request of every
#: return in a household is a few kilobytes. A file past it at the
#: README's name is the client's, whatever it begins with.
README_MAX_BYTES = 256 * 1024
#: The three answers of :func:`whose_readme` (decision 179): the firm's
#: README; a file the client dropped under its name; and one that could
#: not be opened just now - held by a sync client or a viewer, access
#: refused, gone mid-look - which is neither written over nor moved.
README_FIRMS = "firm's"
README_CLIENTS = "client's"
README_UNKNOWN = "cannot tell"
#: The one line under :data:`README_HEADING` when no request is left on it.
NOTHING_OUTSTANDING_LINE = "  Nothing at the moment."
#: Step 2 of the client README, in Jason's words (decision 130, D-b): no
#: timing clause and nothing more. Until then the step promised the move
#: "on the next scheduled pass" and explained the filing in two more
#: lines; the owner's sentence is the whole step. A constant, so a test
#: holds the code to it.
README_STEP_2 = (
    "2. We will examine and place all documents into the current year's\n"
    "   folder."
)
#: Step 3, in the owner's words (decision 130, 2026-09-23): it keeps asking
#: for what is outstanding, and names the list that holds it - the old "until
#: the lists below are covered" stopped reading right once the first list
#: began to shrink as documents arrive. A constant, so a test holds it.
README_STEP_3 = (
    "3. Please keep sending the documents listed under REQUESTED,\n"
    "   NOT YET RECEIVED. Send them as you find them; there's no\n"
    "   need to wait and send everything at once."
)
#: Step 4 of the client README, first part, in the owner's own words
#: (decision 127, his sign-off item; reworded by decision 130, D-c, which
#: dropped "one document per photo", "straight on" and "in good light" -
#: the reader benchmark measures what that costs). Until 127 the step said
#: "scans and photos are fine as long as they are readable" while every
#: request refused an image, so the one sentence the client actually read
#: was the one thing the software would not do. It is a constant because a
#: person's promise to a client belongs where a test can hold the code to it.
README_PHOTO_LINE = (
    "4. Original PDFs or Excel files are preferred. A clear photo from your\n"
    "   phone is fine too, just get the whole page in the frame."
)
#: Decision 130: the section that acknowledges what has arrived. Two
#: states only (D-a): a document confirmed into its request is Received,
#: one a person is looking at is Under Review. Neither says whether a
#: request is complete or where anything was filed. A request with a
#: Received line leaves *REQUESTED, NOT YET RECEIVED* and is shown here, so
#: no *asked* request is ever on neither list. A row nobody asked for
#: (decision 142) is never on the first list: with nothing received it is
#: on neither, by the owner's rule, and a document filed under it is a
#: Received line here under its own title, exactly as under an asked one.
RECEIVED_HEADING = "WHAT WE HAVE RECEIVED"
RECEIVED_WORD = "Received"
UNDER_REVIEW_HEADING = "Under Review"
#: An Under Review document is counted by the day it arrived and never
#: named: its only name is the client's own file name (decision 130, D-e).
UNDER_REVIEW_LINE = "{n} document{s} received {day}"
#: What a Received line says of a document whose request is no longer on
#: the return's list.
OTHER_DOCUMENT = "Other document"
#: The month abbreviations a day is written with - fixed English, never
#: the machine's locale, so the office's settings cannot change a client's
#: README (``"%d %b %Y"`` read through strftime would).
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# ``PREPARED_DIR_NAME``, ``REVIEW_DIR_NAME`` and ``README_NAME`` are
# imported above rather than declared here: the shape of the clients root
# is worded once, in tracker.layout, since decision 125. They are still
# read from this module by the callers that have always read them from it.

#: The one list of characters Windows forbids lives in tracker.layout (decision 188).
_ILLEGAL_CHARS = WINDOWS_ILLEGAL_CHARS


# ----------------------------------------------------------------- naming ----


def sanitize_component(text: str) -> str:
    """Make ``text`` safe as (part of) a Windows folder name.

    A name Windows keeps for a device (``CON``, ``NUL``, ``COM1`` ...,
    ``layout.WINDOWS_RESERVED_NAMES``) is never handed back as itself
    (decision 137, L6): it gains a trailing ``_``, so a folder is made
    rather than a device opened - and every caller that refuses a name the
    sanitiser changed (a household, a return, a feed) refuses it.
    """
    cleaned = _ILLEGAL_CHARS.sub("-", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip(". ")
    if cleaned and is_reserved_name(cleaned):
        stem, dot, rest = cleaned.partition(".")
        cleaned = f"{stem.rstrip(' ')}_{dot}{rest}"
    return cleaned


def matches_identifier(name: str, identifier: str) -> bool:
    """True if ``name`` starts with ``identifier`` at a word boundary.

    Case-insensitive (Windows filesystems are). ``A1`` does not match
    ``A10 - ...`` because the character after the prefix must be
    non-alphanumeric (or end of string).
    """
    name = name.strip().lower()
    prefix = identifier.strip().lower()
    if not prefix or not name.startswith(prefix):
        return False
    rest = name[len(prefix):]
    return rest == "" or not rest[0].isalnum()


def owner_of(name: str, identifiers: Sequence[str]) -> str | None:
    """The request a working copy's name belongs to: the *longest*
    identifier it starts with at a word boundary, or None.

    Longest, so with ``A01`` and ``A01-B`` on the list
    ``A01-B - Loan - TY2025.pdf`` belongs to ``A01-B`` only. The rule
    :func:`assign_files` applies to every file in ``PREPARED_DIR_NAME``;
    it is here on its own for the two readers that ask it of a name whose
    file may not be there any more - the rename moving a recorded copy, and
    the scan saying a recorded copy has gone.
    """
    best: str | None = None
    for ident in identifiers:
        if matches_identifier(name, ident) and (best is None or len(ident) > len(best)):
            best = ident
    return best


def assign_files(
    prepared_dir: Path, identifiers: Sequence[str]
) -> dict[str, list[Path]]:
    """Map each identifier to the files directly in ``prepared_dir`` whose
    names belong to it (decision 168) - **the one answer** to "which files
    are this request's", which the scanner counts, the filer files beside,
    the rename moves, the app's "Keep it here" offers and the dry-run
    validator lists.

    Each file goes to the longest identifier its name starts with at a word
    boundary (:func:`owner_of`); a name no identifier starts is nobody's
    and the scanner names it. Only files **directly** in the folder: a
    folder inside it - the review folder, a folder a person made, a request
    folder of a return made before decision 168 - holds nothing of any
    request's. Junk is left out (``validators.is_ignored``): the sync
    client's and Office's own files, and every temp an atomic write makes
    (decision 155), whose name is the target's with ``.<pid>.<tag>.tmp``
    after it - it starts with the identifier like the copy it was going to
    be, and a copy the power cut in half must never be counted as one.
    """
    assigned: dict[str, list[Path]] = {ident: [] for ident in identifiers}
    if not prepared_dir.is_dir():
        return assigned
    for child in sorted(prepared_dir.iterdir()):
        if not child.is_file() or is_ignored(child):
            continue
        best = owner_of(child.name, identifiers)
        if best is not None:
            assigned[best].append(child)
    return assigned


def persons_folders(prepared_dir: Path) -> list[Path]:
    """Every folder inside ``prepared_dir`` other than the review folder:
    a person's folder (decision 168), where the tracker files nothing and
    counts nothing - a request folder of a return made before 168 among
    them. Sorted; empty where the folder is not there."""
    if not prepared_dir.is_dir():
        return []
    return [child for child in sorted(prepared_dir.iterdir())
            if child.is_dir() and not same_folder_name(child.name, REVIEW_DIR_NAME)]


# --------------------------------------------------------------- scaffold ----


@dataclass(slots=True)
class ScaffoldResult:
    inbox: Path                                             # the household's one drop folder
    prepared_dir: Path | None = None                        # firm-side working set
    originals_dir: Path | None = None                       # the year's originals, client-side
    readme: Path | None = None

    def describe(self) -> list[str]:
        """The three lines every CLI prints about a laid-out return."""
        return [f"Client inbox:     {self.inbox}",
                f"Originals folder: {self.originals_dir}",
                f"Prepared tree:    {self.prepared_dir}"]


@dataclass(slots=True)
class HouseholdScaffold:
    """What one household's client side is: its folder, its inbox and
    where the README in it is."""

    client_dir: Path
    inbox: Path
    #: Where the README is, or would be. Never written by the scaffold
    #: since decision 130: :func:`write_readme` is its one composer.
    readme: Path | None = None
    #: One per open year of the household's returns, in year order.
    originals: list[Path] = field(default_factory=list)


class ClientFolderMissing(RuntimeError):
    """A household's client folder is gone and is not to be made again
    (SPEC-162 ruling 2, kept by decision 188); the message is
    ``households.CLIENT_FOLDER_MISSING``."""


def scaffold_household(
    household_dir: Path | str,
    *,
    returns: list[Path] | None = None,
    may_make_household: bool = True,
) -> HouseholdScaffold:
    """Create/refresh one household's client side: its folder, its inbox and
    a year folder per open year. **Folders only** (decision 130): the README
    in the inbox is :func:`write_readme`'s, reached through
    ``tracker.filer.refresh_household_readme`` once what it says is known.

    ``household_dir`` is the household's folder in the **private** tree -
    the one holding its record - because that is what every caller has in
    hand: the return folder knows its household positionally
    (``layout.household_of``). ``returns`` is the household's return
    folders when the caller has read them; left out, they are found on
    disk (``households.household_returns``).

    Idempotent: re-running makes back a folder somebody deleted and does
    nothing else. Nothing already there is touched, renamed or deleted.

    **Except the household's client folder, once it has had one**
    (``may_make_household=False``, SPEC-162 ruling 2 kept by decision 188):
    a household that was shared, or whose originals rest in its client
    folder, whose client folder is gone was renamed or moved, and making a
    new empty one would hide that - :class:`ClientFolderMissing` is raised
    and nothing is made. The inbox inside an existing client folder is
    still remade: it lies inside the shared folder.
    """
    household_dir = Path(household_dir)
    # The private household folder is root/PRIVATE_TREE/<household>, so the
    # root is two levels up: the one arithmetic this needs, and it is the
    # same positional rule discovery walks by.
    root = household_dir.parent.parent
    household = household_dir.name
    client_dir = client_household_dir(root, household)
    inbox = inbox_dir_for(root, household)
    # One level at a time, each through the one door into the client tree
    # (decision 188): the household's client folder only while it is being
    # made, its inbox and its year folders always. The tree itself is no
    # household's place; a new root gets it once.
    if not may_make_household and not client_dir.is_dir():
        from tracker.households import CLIENT_FOLDER_MISSING

        raise ClientFolderMissing(CLIENT_FOLDER_MISSING.format(name=household))
    clients_tree_of(root).mkdir(exist_ok=True)
    _make(root, household, client_dir, making=True)
    _make(root, household, inbox)

    years, _engagements = _open_year_of(household_dir, returns)
    result = HouseholdScaffold(client_dir=client_dir, inbox=inbox, readme=inbox / README_NAME)
    for year in years:
        originals = originals_dir_for(root, household, year)
        _make(root, household, originals)
        result.originals.append(originals)
    return result


def _make(root: Path, household: str, folder: Path, *, making: bool = False) -> None:
    """Make one folder of a household's client side, when it is not there,
    once the door has approved it (``door.client_write``)."""
    if not folder.is_dir():
        door.client_write(root, household, folder, making=making).mkdir(exist_ok=True)


def _open_year_of(household_dir: Path, returns: list[Path] | None = None
                  ) -> tuple[list[int], list[_ReturnLine]]:
    """The household's open years and every return that could be read, each
    marked superseded where another return was rolled forward from it."""
    from tracker.households import household_returns, open_years

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
    # would otherwise read as two open years and be told nothing. By the
    # same rule discovery uses (decision 131): the path, else its three
    # trailing names, so a clients root that has moved - which leaves every
    # absolute Rolled From naming a folder that is not there - still
    # retires the prior, and the README is written for the one open year.
    for one in engagements:
        one.superseded = any(same_return(other.info.rolled_from, one.path)
                             for other in engagements
                             if other is not one and other.info.rolled_from)
    return open_years(engagements), engagements


def _readme_returns(household_dir: Path) -> tuple[int, list[_ReturnLine]] | None:
    """The one open year and its active returns, in the household's order -
    or ``None`` when the household has not exactly one open year."""
    years, engagements = _open_year_of(household_dir)
    if len(years) != 1:
        return None
    [year] = years
    return year, [one for one in engagements if one.active and one.tax_year == year]


def readme_returns(household_dir: Path | str) -> list[_ReturnLine] | None:
    """The returns the household's README speaks for - the active returns
    of its one open year, in the order the README lists them, each with its
    details and its request list read once - or ``None`` when the
    household has two open years (or none), where the README is left as it
    is.

    Read once per refresh and handed to both
    ``tracker.filer.received_for`` and :func:`write_readme` (decision 130,
    the review's F3), so one refresh reads each return's details and list
    once."""
    found = _readme_returns(Path(household_dir))
    return None if found is None else found[1]


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


def scaffold_engagement(engagement_dir: Path | str) -> ScaffoldResult:
    """Create/refresh one return's ``PREPARED_DIR_NAME/`` and its review
    folder, and its household's client side with it. **Folders only**
    (decision 130).

    **No request gets a folder** (decision 168): a working copy sits in
    ``PREPARED_DIR_NAME`` itself, named by its request, so a request with
    nothing in yet has nothing here and is simply Missing - the app and the
    Status Report are the list of what is still to come. Until 168 every
    asked row had an empty folder made for it on every pass (decisions 34
    and 142), and a request whose folder somebody deleted read "request
    folder not found" until the next pass made it again.

    ``engagement_dir`` must hold a record. Raises
    :class:`tracker.manifest.ManifestError` if it holds none — scaffolding
    never proceeds from a list nobody has recorded.

    The household's side is laid out too, so a return made on its own
    still has its inbox and its year folder. The README lists every return
    of the open year and what has arrived for each, which is why neither
    this nor :func:`scaffold_household` writes it: whoever made the change
    calls ``tracker.filer.refresh_household_readme`` afterwards.
    """
    engagement_dir = Path(engagement_dir)
    load_manifest(engagement_dir)       # a return with no recorded list is refused here

    # Firm side: where the working copies sit, and somewhere for the unclear.
    prepared_dir = engagement_dir / PREPARED_DIR_NAME
    prepared_dir.mkdir(parents=True, exist_ok=True)
    (prepared_dir / REVIEW_DIR_NAME).mkdir(exist_ok=True)

    # Client side: the household's one inbox and the year's originals.
    household = scaffold_household(household_of(engagement_dir))
    year = year_of(engagement_dir)
    originals_dir = (originals_dir_for(root_of(engagement_dir),
                                       household_of(engagement_dir).name, year)
                     if year is not None else None)

    return ScaffoldResult(
        inbox=household.inbox, prepared_dir=prepared_dir, originals_dir=originals_dir,
        readme=household.readme,
    )


# ----------------------------------------------------------------- README ----


def write_readme(
    household_dir: Path | str,
    received: Received | None = None,
    *,
    contact: str | None = None,
    returns: Sequence[_ReturnLine] | None = None,
) -> Path | None:
    """Write the household's client README - **the only function that
    writes** ``README_NAME`` (decision 130) - and return where it is.

    It reads the household's returns as the scaffold does, decides the
    open year by the same rule, and renders the steps, *REQUESTED, NOT
    YET RECEIVED* and, when anything has arrived, *WHAT WE HAVE RECEIVED* from
    ``received``: plain data, read out of the index one layer up
    (``tracker.filer.received_for``). Nothing here reads the index.

    Written only when the text changed, whole and with CRLF line ends; a
    write the client's side refuses is a log line and ``None``.

    **With two open years nothing is written** and ``None`` comes back.
    The pass sorts nothing from an inbox that cannot say which year a
    document is for, so the README would be telling the client to send
    things into a folder the pass is not reading; the app and the practice
    page say why instead (``tracker.runner.TWO_OPEN_YEARS``). The first
    pass after the old year retires rewrites it.

    ``contact`` overrides the household's contact line; left out, it is
    the household's, else the firm named on the first active return.
    ``returns`` is :func:`readme_returns`' answer when the caller has
    already read it (the refresh has); left out, it is read here.
    """
    from tracker.households import load_household_info

    household_dir = Path(household_dir)
    root = household_dir.parent.parent
    household = household_dir.name
    if returns is None:
        found = _readme_returns(household_dir)
        if found is None:
            return None
        returns = found[1]
    active = list(returns)
    if contact is None:
        try:
            contact = load_household_info(household_dir).contact
        except Exception:               # a household with no record yet
            contact = ""
    fallback = next((one.info.firm or one.info.sender for one in active), "")
    returns = [(one, [i for i in one.items if i.manual_override != Override.NOT_APPLICABLE])
               for one in active]
    text = _readme_text(household, returns, received or Received(), contact or fallback)

    inbox = inbox_dir_for(root, household)
    readme = inbox / README_NAME
    # A client's own file of that name is never written over (decision
    # 179): the sort takes it, as it takes every other drop, and the next
    # refresh after it writes the README. One whose owner cannot be told
    # just now is not written over either; the next refresh looks again.
    whose = whose_readme(readme) if readme.exists() else README_FIRMS
    if whose == README_CLIENTS:
        log.warning("%s in %s's inbox is a file the client dropped; it is sorted like any "
                    "other and the README is written after it", readme.name, household)
        return None
    if whose == README_UNKNOWN:
        log.warning("%s in %s's inbox could not be read just now; it is not written over, "
                    "and the next refresh looks again", readme.name, household)
        return None
    # The pass and every app action refresh it; rewriting an unchanged
    # README would make the sync client push a "new" file to the client
    # every time. Read only once it is known to be the firm's, and so small.
    try:
        if readme.read_text(encoding="utf-8") == text:
            return readme
    except (OSError, UnicodeDecodeError):
        pass
    # Client-visible and cosmetic: a sync client uploading it, a viewer
    # holding it, or a folder the client made under its name must not stop
    # the sort and the scan behind it. Written whole; a failure is a log line.
    try:
        # Through the one door (decision 188): the README, and so the folder
        # its temp is written in, is this household's inbox and nothing else.
        # The inbox is remade inside an existing client folder; the client
        # folder itself is never made here.
        door.client_write(root, household, readme)
        inbox.mkdir(exist_ok=True)
        write_text_atomically(readme, text, encoding="utf-8", newline="\r\n")
    except (OSError, door.DoorError) as exc:
        log.warning("Could not refresh %s (%s); the pass goes on", readme.name, exc)
        return None
    return readme


def whose_readme(path: Path) -> str:
    """Whose the file at ``path`` - an inbox's ``README_NAME`` - is
    (decision 179), one of three answers. :data:`README_FIRMS`: no larger
    than :data:`README_MAX_BYTES` and beginning with
    :data:`README_FIRST_LINE`, a byte-order mark an editor added allowed.
    :data:`README_CLIENTS`: larger than that, or read and beginning
    otherwise - the sort takes it and the refresh never writes over it.
    :data:`README_UNKNOWN`: its size or its first bytes could not be read
    just now (a sync client or a viewer holding it, access refused, gone
    mid-look) - it is left where it is, neither moved nor written over,
    and looked at again next time. Only the first line is ever read."""
    first = README_FIRST_LINE.encode("ascii")
    try:
        if Path(path).stat().st_size > README_MAX_BYTES:
            return README_CLIENTS
        with Path(path).open("rb") as handle:
            head = handle.read(len(first) + 3)
    except OSError:
        return README_UNKNOWN
    return README_FIRMS if head.removeprefix(b"\xef\xbb\xbf").startswith(first) else README_CLIENTS


def day_text(day) -> str:
    """``23 Sep 2026`` - a day as the client README writes it, with fixed
    English month names whatever the machine's locale."""
    return f"{day.day:02d} {_MONTHS[day.month - 1]} {day.year}"


def _received_lines(returns: Sequence[_ReturnLine], received: Received) -> list[str]:
    """The *WHAT WE HAVE RECEIVED* section, or nothing when no line would
    render under its heading (decision 130, D-f; the review's F4).

    Received lines per return, under the return's name, in the order
    *REQUESTED, NOT YET RECEIVED* lists the returns, by day and then label; a return with
    none has no heading here. Under Review documents belong to no settled
    return, so they are one trailing block, one line per arrival day.
    """
    by_return: dict[Path, list[ReceivedLine]] = {}
    for line in received.lines:
        by_return.setdefault(Path(line.return_path), []).append(line)
    lines: list[str] = []
    for one in returns:
        mine = by_return.get(Path(one.path))
        if not mine:
            continue
        lines.append(one.return_name)
        for line in sorted(mine, key=lambda one: (one.day is None, one.day or 0, one.label)):
            said = f"{RECEIVED_WORD} {day_text(line.day)}" if line.day else RECEIVED_WORD
            if line.inside:
                said = f"{said}, {IN_CONSOLIDATED_CLIENT}"
            lines.append(f"  {line.label}  {said}")
    waiting = [one for one in received.under_review if one.count > 0]
    if waiting:
        lines.append(UNDER_REVIEW_HEADING)
        for one in sorted(waiting, key=lambda u: (u.day is None, u.day or 0)):
            said = UNDER_REVIEW_LINE.format(n=one.count, s="" if one.count == 1 else "s",
                                            day=day_text(one.day) if one.day else "")
            lines.append(f"  {said}".rstrip())
    # The heading only over a line (the review's F4): a Received line for a
    # return the README does not speak for, or an Under Review day counted
    # zero, renders nothing, and a heading over nothing tells the client
    # something arrived when the section says nothing did.
    return ["", RECEIVED_HEADING, "-" * 45, *lines] if lines else []


def _outstanding(
    returns: Sequence[tuple[_ReturnLine, list[RequestItem]]], received: Received,
) -> list[tuple[_ReturnLine, list[RequestItem]]]:
    """The returns and requests *REQUESTED, NOT YET RECEIVED* lists
    (decision 130, Jason's decision of 2026-09-23): every active *asked*
    request (decision 142) with no Received line - no Filed or File Moved row naming it, by its
    identifier or by an also-filed copy - and only the returns with one
    left. Under Review does not take a request off: nothing is confirmed
    into it yet. A request that expects several documents leaves after its
    first, which the owner accepted.

    Read from the same :class:`Received` the section below renders, so an
    asked request that leaves this list is always a line there - never on
    neither. A row nobody asked for is never listed here: the client is
    not asked for it, and sees it only as received."""
    have: dict[Path, set[str]] = {}
    for line in received.lines:
        if line.identifier:
            have.setdefault(Path(line.return_path), set()).add(line.identifier)
    left = []
    for one, items in returns:
        mine = have.get(Path(one.path), set())
        waiting = [item for item in items if item.asked and item.identifier not in mine]
        if waiting:
            left.append((one, waiting))
    return left


def _readme_text(
    household: str,
    returns: Iterable[tuple[_ReturnLine, list[RequestItem]]],
    received: Received,
    contact: str,
) -> str:
    returns = list(returns)
    lines = [
        README_FIRST_LINE,
        "=" * 45,
        "",
        f"Household: {household}",
        "",
        "Just drop everything into this folder. One folder, that's it -",
        "you don't need to sort anything or name anything. We sort it.",
        "",
        "1. Drag your documents anywhere in this folder.",
        *README_STEP_2.split("\n"),
        *README_STEP_3.split("\n"),
        *README_PHOTO_LINE.split("\n"),
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
    outstanding = _outstanding(returns, received)
    for one, items in outstanding:
        lines.append(one.return_name)
        for item in items:
            entry = f"  {item.label}"
            if item.expected_text:
                entry += f"  [{item.expected_text}]"
            lines.append(entry)
    if not outstanding:
        lines.append(NOTHING_OUTSTANDING_LINE)
    lines.extend(_received_lines([one for one, _ in returns], received))
    lines.append("")
    if contact:
        lines.append(f"Questions? Contact {contact}.")
        lines.append("")
    lines.append("(This file is generated automatically - edits will be overwritten.)")
    return "\n".join(lines) + "\n"


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description=f"Lay out the household's {INBOX_DIR_NAME!r} inbox and this return's "
                    f"{PREPARED_DIR_NAME}/ from the request list. Folders only: the "
                    f"{README_NAME} is written by the pass and the app (decision 130)."
    )
    parser.add_argument("engagement_dir", help="the return folder")
    ns = parser.parse_args()
    # A typed folder is parsed, never trusted: it must be a return's
    # place under the checked clients root (decision 188).
    from tracker import door

    try:
        ns.engagement_dir = door.return_dir(Path(ns.engagement_dir).absolute())
    except ValueError as exc:
        parser.error(str(exc))

    res = scaffold_engagement(ns.engagement_dir)
    for line in res.describe():
        print(line)
    print(f"  (no folder per request: working copies sit in {PREPARED_DIR_NAME}/ itself, "
          "named by their request)")
    print(f"  (folders only: {res.readme.name} is written by the pass and the app)")
