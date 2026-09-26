"""Every household and return the scheduled run should touch, found rather
than listed (component 10).

There is no registry file. The unattended run is pointed at the folder the
firm keeps its clients in and walks it. What the run needs to know about
each return (who the client is, the share link, the due date, whether to
chase them by email, whether it is still active) is that return's details
in its own record, written by the wizard when it is created and edited in
the app.

That is the whole point. The previous ``engagements.yaml`` was a second list
a person had to keep in step with the folders on disk: a mistyped path or a
client nobody added was a client silently skipped until a filing deadline.
A folder with a record in it is a return; nothing else has to be told.

**The walk is positional** (decision 125). It knows what every level of the
layout is - the two trees, the household, the year, the return - so it
never has to guess what a folder holding a record is, and it never stops at
one on the way down:

``root / PRIVATE_TREE(1) / household(2) / year(3) / return(4)``

:data:`tracker.layout.CLIENTS_TREE` is skipped by name and never listed: it
holds no record by design, and the guarantee that nothing under it is ever
a record, a working copy, a draft, a lock or a page is what makes it safe
to share. Anything else at that level is a misfit.

**Every folder that does not fit is listed with one sentence and left
alone** (the owner's rule). A stray tree, a record in the place the layout
before decision 125 put one, a household with no record, a year folder not
named as a year, a return folder with no record, a folder holding only the
workbook the tracker no longer reads (``LEGACY_MANIFEST_FILENAME``), a
folder the walk cannot list: each is a :class:`Misfit` with its sentence,
shown on the practice page, in the app and on the command line. Nothing in
a misfit is ever read, moved or renamed; a person fixes it. There is no
migration and no importer - decision 104 refused one and decision 125
refused it again.

**The folder is the identity and the record's labels are a claim**
(decision 188, overruling decision 125's "the record wins"). A household
whose record, or any of whose returns' details, names another household,
return name or year than its folders do is paused (:attr:`Registry.paused`,
``tracker.households.pause_of``): the pass touches nothing of it until a
person accepts the folder's name in the app or gives the folder back its
name. Two household folders that are one name by the layout's key are
stopped, and so is a household position whose record is gone
(:attr:`Registry.stopped`). The client tree's first level is listed by
name, and a client folder no household owns is a misfit. Nothing is ever
renamed. **Where anything is written is positional** (decision 125) - its inbox, its originals, its
README - and a return rolls forward where it sits, never where its record
says it once sat (decision 177): a folder dragged into another household
is a move a person made, and the record cannot tell a move from a rename.

A record that cannot be read is still listed: with its error, so the runner
reports it and moves on, exactly as it would for a folder-level problem. A
root that is not a folder, or one with nothing at all under it, raises
:class:`RegistryError` - that is a typo in the scheduled task, not an empty
practice.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field, replace
from pathlib import Path

from tracker import layout, ledger, store
from tracker.households import load_household_info, pause_of
from tracker.ledger import LedgerError
from tracker.manifest import ManifestError, load_engagement_info
from tracker.records import EngagementInfo, HouseholdInfo
from tracker.store import StoreError

#: The workbook the request list lived in until decision 104. Its only
#: reader in the package is the walk below, which uses it to say what a
#: folder holding one and no record is: a legacy folder, not a return.
LEGACY_MANIFEST_FILENAME = "_manifest.xlsx"
#: How such a folder is listed, and what the misfit list says of it.
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

#: How far below the root discovery looks, and what each level is:
#: ``root(0) / PRIVATE_TREE(1) / household(2) / year(3) / return(4)``.
#: Nothing below a return is ever walked - it is the return's own folders -
#: so a record nested deeper sits inside a folder already listed as holding
#: no return.
MAX_DEPTH = 4

#: A folder at the top of the clients root that is neither of the two trees.
MISFIT_NOT_A_TREE = "is not one of the two trees the tracker reads ({clients} and {private}); left alone"
#: A record where the layout before decision 125 put one: straight under a
#: tree, at the household level, at the year level.
MISFIT_RECORD_MISPLACED = ("holds a record in the layout before decision 125; set the household up again "
                           "in the app and drop the originals into its inbox")
#: A folder where a household would be, with nothing the tracker can read.
#: Corrected by decision 188: the old advice (set the household up in the
#: app) is what decision 137 refuses over a folder the tracker did not make.
MISFIT_NO_HOUSEHOLD_RECORD = ("sits where a household would but holds no household record; left alone - "
                              "the app will not set a household up over it, so move it aside first")
#: A folder in the client tree that is no discovered household's client
#: folder (decision 188, R8): listed by name only - nothing in it is read.
MISFIT_CLIENT_NO_RECORD = ("is a client folder no household record owns; nothing in it is read, and "
                           "the app will not set a household up over it")
#: A household or return folder whose name the layout's one rule refuses
#: (decision 188): the reason is the rule's own phrase.
MISFIT_BAD_NAME = ("is named in a way the tracker does not accept for a household or a return "
                   "({reason}); left alone")
#: A folder where a year would be, named as something else.
MISFIT_NOT_A_YEAR = "sits where a year folder would but is not named as a four-digit year; left alone"
#: A return folder with no record, and a household with no return under any
#: of its years.
MISFIT_NO_RETURN = "holds no return the tracker can read"
#: A folder the walk cannot list: an ACL that denies the run's account, a
#: folder moved in from elsewhere carrying its own. Every document inside
#: would be invisible to every list, so it is said rather than passed over.
UNLISTED = "could not be listed ({error})"
#: A client folder whose name only reads as a household's by the layout's
#: key (the re-check of decision 188, R1): another folder, never adopted.
MISFIT_CLIENT_LOOK_ALIKE = ("is a look-alike of the client folder of the household {household} but is "
                            "another folder; nothing in it is read, and it is never taken for that "
                            "household's")
#: Two household folders whose names or claims are one name by the
#: layout's key (SPEC-162 ruling 3, widened by decision 188): every one of
#: them is stopped, naming each folder.
TWO_CLAIM = ("Two folders claim the household `{name}`: `{a}` and `{b}`. Keep one; a copy of a "
             "household folder is never a second household.")
#: A household's position holding returns' records and no household record
#: (SPEC-162 ruling 4, kept by decision 188): a stopped entry, counted in
#: the pass's errors, never a household to set up again.
HOUSEHOLD_RECORD_MISSING = (f"The household record `{ledger.LEDGER_FILENAME}` of `{{folder}}` is missing. "
                            "Restore it from Drive's trash or version history; do not create the "
                            "household again.")


class RegistryError(Exception):
    """The clients root could not be walked, or holds nothing at all."""


@dataclass(frozen=True, slots=True)
class Misfit:
    """One folder that does not fit the layout, and the one sentence saying
    why it is left alone."""

    path: Path
    sentence: str


@dataclass(frozen=True, slots=True)
class Household:
    """One household found under the private tree: its folder and what its
    own record says about it."""

    path: Path
    info: HouseholdInfo = HouseholdInfo()
    problem: str = ""        # why the record could not be read, if it could not

    @property
    def name(self) -> str:
        """The household's name: its folder's, which is what every path
        under it is built from."""
        return self.path.name


@dataclass(frozen=True, slots=True)
class Engagement:
    """One return the scheduled run should process.

    Everything about the client is the return's details, held here as
    ``info`` and reachable as attributes (``engagement.client``) so a field
    added to the details is one edit, in one dataclass.
    """

    path: Path
    info: EngagementInfo = EngagementInfo()
    problem: str = ""        # why the record could not be read, if it could not
    superseded_by: str = ""  # the engagement this one was rolled forward INTO
    warning: str = ""        # what its details say that the registry could not act on
    #: The household folder this return sits under, in the private tree.
    #: Positional (``layout.household_of``) and never guessed. Left out,
    #: it is read off ``path`` by that same rule rather than left as the
    #: working folder: a pass given ``Path()`` here would lay a household
    #: out wherever the process happens to be standing, which is how an
    #: empty client tree appeared once in a repository checkout.
    household_path: Path = Path()

    def __post_init__(self) -> None:
        if self.household_path == Path():
            object.__setattr__(self, "household_path", layout.household_of(self.path))

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
        """The household, the year and the return, as everything that lists
        returns says it (``layout.ENGAGEMENT_LABEL_PATTERN``).

        The record's three details where it carries them, the folders'
        names where it does not - so a return recorded before decision 125,
        or one whose record could not be read, still has a label a person
        can act on.
        """
        year = self.info.tax_year if self.info.tax_year is not None else layout.year_of(self.path)
        return layout.label_for(
            self.info.household or self.household_path.name or _household_name(self.path),
            year,
            self.info.return_name or self.path.name,
        )


def _household_name(return_dir: Path) -> str:
    """The household a return folder sits under, by position, or "" when
    the path is too short to hold one (a folder somebody named by hand)."""
    return layout.household_of(return_dir).name if len(return_dir.parts) >= 3 else ""


@dataclass(slots=True)
class Registry:
    """Every household, return and misfit found under one clients root."""

    source: Path                       # the root that was walked
    engagements: list[Engagement] = field(default_factory=list)
    households: list[Household] = field(default_factory=list)
    misfits: list[Misfit] = field(default_factory=list)
    #: Household folder -> why it is paused: its folders and its record's
    #: claims disagree (decision 188, R6). The pass touches nothing of it.
    paused: dict[Path, str] = field(default_factory=dict)
    #: Household folder -> why it is stopped: two folders claim one
    #: household, or its record is gone (SPEC-162 rulings 3 and 4).
    stopped: dict[Path, str] = field(default_factory=dict)

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

    def by_household(self) -> dict[Path, list[Engagement]]:
        """Every household's returns, by the household's folder, in the
        walk's order: household folder, then year, then return name.

        What the pass iterates (``tracker.runner.run_registry``): one
        inbox feeds every return of a household, so the household is the
        unit a pass takes locks over and sorts under.
        """
        grouped: dict[Path, list[Engagement]] = {
            household.path: [] for household in self.households
        }
        for engagement in self.engagements:
            grouped.setdefault(engagement.household_path, []).append(engagement)
        return grouped


# ------------------------------------------------------------- discovery ----


def _skip(folder: Path) -> bool:
    """Names the walk passes over without a word: hidden state, sync
    staging, an office lock file's folder. They are the machine's, not a
    household's, and listing them as misfits would be noise a person
    cannot act on. The one list is the layout's
    (``layout.MACHINE_PREFIXES``, decision 188), whose name rule refuses
    every such name for a household or a return - so a folder the walk
    never lists is never one somebody was allowed to create."""
    return folder.name.startswith(layout.MACHINE_PREFIXES)


def _badly_named(folder: Path, found: _Walk) -> bool:
    """``True`` once a household or return folder whose name the layout's
    rule refuses (decision 188) is listed as a misfit with the reason: the
    constructors refuse to build a path through such a name, so the pass
    never reaches it, and a person is told why."""
    reason = layout.segment_problem(folder.name)
    if reason is None:
        return False
    found.misfits.append(Misfit(folder, MISFIT_BAD_NAME.format(reason=reason)))
    return True


@dataclass(slots=True)
class _Walk:
    """What one walk of a clients root found, before anything is read."""

    returns: list[Path] = field(default_factory=list)
    households: list[Path] = field(default_factory=list)
    misfits: list[Misfit] = field(default_factory=list)
    #: household folder -> the return folders under it, in order.
    under: dict[Path, list[Path]] = field(default_factory=dict)
    #: The client tree's first level, by name (decision 188): listed once,
    #: never walked deeper and never read.
    client_folders: list[Path] = field(default_factory=list)
    #: Household positions holding returns' records and no household record.
    record_missing: dict[Path, list[Path]] = field(default_factory=dict)


def _children(folder: Path, found: _Walk) -> list[Path] | None:
    """The folders inside ``folder``, sorted, or ``None`` when the walk
    cannot list it - which is a misfit with its own sentence, because every
    document inside would otherwise be invisible to every list."""
    try:
        return sorted((p for p in folder.iterdir() if p.is_dir()), key=lambda p: p.name.lower())
    except OSError as exc:
        found.misfits.append(Misfit(folder, UNLISTED.format(error=exc.strerror or exc)))
        return None


def _has_record(folder: Path) -> bool | None:
    """Whether a journal sits in ``folder`` - or ``None`` when the folder
    cannot be read at all.

    The three answers are three different things and the walk says each of
    them differently: a folder with a record, a folder without one, and a
    folder an ACL keeps the run out of. Asked through ``os.stat`` and not
    ``Path.is_file()``, which answers "no" to every error it meets from
    Python 3.13 on - so a client's folder the run is locked out of would
    read as a household with no record, and be left alone under the wrong
    sentence, on a new interpreter and listed properly on an old one.
    """
    try:
        return stat.S_ISREG(os.stat(ledger.path_for(folder)).st_mode)
    except FileNotFoundError:
        return False
    except NotADirectoryError:
        return False
    except OSError:
        return None


def _cannot_be_read(folder: Path, found: _Walk) -> bool:
    """``True`` once the folder has been listed as one the walk cannot
    read - the sentence with the platform's own words - and ``False`` when
    it turns out to be readable after all.

    The walk reaches here when it could not even ask whether a record sits
    in the folder. Listing it is the same question put the other way, and
    it is the question that carries the message, so it is the one that is
    asked and the one the person is told about.
    """
    return _children(folder, found) is None


def _walk_root(root: Path) -> _Walk:
    """Walk one clients root by position: the two trees, the households,
    their years, their returns, and every folder that fits none of them."""
    found = _Walk()
    children = _children(root, found)
    if children is None:
        return found
    for child in children:
        kind = layout.place_of(root, child).kind
        if kind == layout.CLIENTS:
            # The client tree holds no record, by design: its first level
            # is listed by name and nothing below it is walked or read.
            found.client_folders.extend(_client_folders(child))
            continue
        if _skip(child):
            continue
        if kind != layout.PRIVATE:
            found.misfits.append(Misfit(child, MISFIT_NOT_A_TREE.format(
                clients=layout.CLIENTS_TREE, private=layout.PRIVATE_TREE)))
            continue
        _walk_private(child, found)
    return found


def _client_folders(tree: Path) -> list[Path]:
    """The client tree's first level: its folders, by name, from one
    listing - ``os.scandir``'s own entry types, so nothing below is
    opened or even asked about. The machine's own names are passed over."""
    try:
        with os.scandir(tree) as entries:
            return sorted((Path(entry.path) for entry in entries
                           if entry.is_dir(follow_symlinks=False)
                           and not entry.name.startswith(layout.MACHINE_PREFIXES)),
                          key=lambda p: p.name.lower())
    except OSError:
        return []


def _returns_with_records(household: Path) -> list[Path]:
    """The return folders under a household position that hold a record."""
    from tracker.households import household_returns

    return household_returns(household)


def _walk_private(private: Path, found: _Walk) -> None:
    """Every household folder under the private tree."""
    children = _children(private, found)
    if children is None:
        return
    for child in children:
        if _skip(child) or _badly_named(child, found):
            continue
        record = _has_record(child)
        if record is None and _cannot_be_read(child, found):
            continue
        if record:
            found.households.append(child)
            found.under[child] = []
            _walk_household(child, found)
            continue
        # A household whose record is gone and whose returns still hold
        # theirs is stopped, not left alone (SPEC-162 ruling 4).
        if returns := _returns_with_records(child):
            found.record_missing[child] = returns
            continue
        found.misfits.append(Misfit(child, MISFIT_NO_HOUSEHOLD_RECORD))


def _walk_household(household: Path, found: _Walk) -> None:
    """Every year folder under one household, and the returns under each."""
    children = _children(household, found)
    if children is None:
        return
    for child in children:
        if _skip(child):
            continue
        record = _has_record(child)
        if record is None and _cannot_be_read(child, found):
            continue
        if record:
            found.misfits.append(Misfit(child, MISFIT_RECORD_MISPLACED))
            continue
        if not layout.is_year_folder(child.name):
            found.misfits.append(Misfit(child, MISFIT_NOT_A_YEAR))
            continue
        _walk_year(child, household, found)
    if not found.under.get(household):
        found.misfits.append(Misfit(household, MISFIT_NO_RETURN))


def _walk_year(year: Path, household: Path, found: _Walk) -> None:
    """Every return folder under one year. A return is terminal: nothing
    below it is ever walked - it is the return's own folders."""
    children = _children(year, found)
    if children is None:
        return
    for child in children:
        if _skip(child) or _badly_named(child, found):
            continue
        record = _has_record(child)
        if record is None and _cannot_be_read(child, found):
            continue
        if record:
            found.returns.append(child)
            found.under[household].append(child)
            continue
        if (child / LEGACY_MANIFEST_FILENAME).is_file():
            found.misfits.append(Misfit(child, LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME)))
            continue
        found.misfits.append(Misfit(child, MISFIT_NO_RETURN))


def engagement_dirs(root: Path | str, *, max_depth: int = MAX_DEPTH) -> list[Path]:
    """Every return folder under ``root``, in the walk's order.

    ``max_depth`` is the layout's and is not a dial any more: a return is
    the fourth level and nothing else is a return. It is kept in the
    signature because every caller passes the default and a keyword that
    disappeared would be an import error in a script nobody reran.
    """
    return _walk_root(Path(root)).returns


def record_dirs(root: Path | str) -> list[Path]:
    """Every folder under ``root`` that has a record: the households first,
    then the returns, in the walk's order.

    A household's record is a journal held in the same table a return's is
    (decision 125), so the store's own command line - rebuild, check,
    state - has to be able to name every one of them. Reading only the
    returns would leave each household's row unchecked in silence, which
    is the one thing the check exists not to do.
    """
    found = _walk_root(Path(root))
    return [*found.households, *found.returns]


def household_from(folder: Path) -> Household:
    """One household from its folder and the details its record holds.

    A record the readers refuse - a journal that will not parse, a store
    that will not open, anything else one synced folder can surprise a
    reader with - is listed with the sentence, not dropped: one
    household's record must not end the whole practice's pass inside
    discovery, and the returns under it have records of their own.
    """
    folder = Path(folder)
    try:
        info = load_household_info(folder)
        if store.kind(store.connect(), folder) != store.KIND_HOUSEHOLD:
            return Household(path=folder, problem=MISFIT_RECORD_MISPLACED)
    except (ManifestError, LedgerError, StoreError) as exc:
        return Household(path=folder, problem=str(exc))
    except Exception as exc:        # one folder's surprise, said, not fatal
        return Household(path=folder, problem=f"{type(exc).__name__}: {exc}")
    return Household(path=folder, info=info)


def engagement_from(folder: Path) -> Engagement:
    """One return from its folder and the details its record holds.

    A record the readers refuse - a journal that will not parse, a store
    that will not open, a line of the wrong shape, anything else one
    synced folder can surprise a reader with - is listed with the
    sentence, not dropped: one client's record must not end the whole
    practice's pass inside discovery. A record that carries no rules with
    the old workbook beside it is a legacy folder: an engagement made
    before decision 103 whose rules never reached the journal, which the
    owner's word says is set up again in the app rather than imported.
    """
    folder = Path(folder)
    household_path = layout.household_of(folder) if len(folder.parts) >= 3 else Path()
    try:
        info: EngagementInfo = load_engagement_info(folder)
        rules = store.rules(store.connect(), folder) or []
    except (ManifestError, LedgerError, StoreError) as exc:
        return Engagement(path=folder, problem=str(exc), household_path=household_path)
    except Exception as exc:        # one folder's surprise, said, not fatal
        return Engagement(path=folder, problem=f"{type(exc).__name__}: {exc}",
                          household_path=household_path)
    if not rules and (folder / LEGACY_MANIFEST_FILENAME).is_file():
        return Engagement(path=folder, info=info, household_path=household_path,
                          problem=LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME))
    return Engagement(path=folder, info=info, household_path=household_path)


def _same_folder(a: str, b: Path) -> bool:
    try:
        return Path(a).resolve() == b.resolve()
    except OSError:
        return False


def _prior_of(candidate: Engagement, index: int, engagements: list[Engagement]) -> int | None:
    """Which engagement ``candidate`` was rolled forward from, as an index.

    By the resolved path first. Failing that - Rolled From is written
    absolute, and a clients root that has moved to another drive would
    otherwise bring every retired prior back to life for the draft day -
    by the folder names: the engagement, other than the candidate itself,
    whose path ends in the most of Rolled From's names, at least
    ``layout.ROLLED_FROM_TAIL`` (the household's, the year's and the
    return's - worded once at layer 0 since decision 131, so the scaffold
    retires a prior by the same rule), and only when that engagement is the
    only one to do so. Two that tie decide nothing.
    """
    # A folder the walk could not list, or whose record it could not
    # read, is never taken as the prior: retiring it would turn its report
    # into a benign skip.
    readable = [(position, prior) for position, prior in enumerate(engagements)
                if position != index and not prior.problem]
    for position, prior in readable:
        if _same_folder(candidate.rolled_from, prior.path):
            return position
    tails = {position: layout.shared_tail(candidate.rolled_from, prior.path) for position, prior in readable}
    if not tails:
        return None
    longest = max(tails.values())
    if longest < layout.ROLLED_FROM_TAIL:
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
    """Walk ``root`` and return every household, return and misfit under it."""
    root = Path(root)
    if not root.is_dir():
        raise RegistryError(f"clients root is not a folder: {root}")
    found = _walk_root(root)
    if not found.returns and not found.households and not found.misfits:
        raise RegistryError(
            f"nothing found under {root} ({layout.PRIVATE_TREE}/<household>/<year>/<return> "
            f"holding {ledger.LEDGER_FILENAME}) - is this the right folder?"
        )
    households = [household_from(folder) for folder in found.households]
    misfits = list(found.misfits)
    # A household whose record is a return's is the layout before decision
    # 125, and it is a misfit rather than a household the pass would run.
    # One sentence per folder: the misplaced record is what a person acts
    # on, so it replaces the "holds no return" the walk had already said of
    # the same folder.
    keep: list[Household] = []
    for household in households:
        if household.problem == MISFIT_RECORD_MISPLACED:
            misfits = [m for m in misfits if m.path != household.path]
            misfits.append(Misfit(household.path, MISFIT_RECORD_MISPLACED))
            continue
        keep.append(household)
    running = {household.path for household in keep}
    engagements = mark_superseded([
        engagement_from(folder) for folder in found.returns
        if folder.parent.parent in running
    ])
    stopped = _two_claims(keep)
    # A household whose record is gone: its returns are listed, each
    # carrying the sentence, so the pass counts them as failed.
    for household, returns in found.record_missing.items():
        said = HOUSEHOLD_RECORD_MISSING.format(folder=household.name)
        stopped[household] = said
        engagements.extend(Engagement(path=one, problem=said, household_path=household)
                           for one in returns)
    grouped: dict[Path, list[Engagement]] = {}
    for one in engagements:
        grouped.setdefault(one.household_path, []).append(one)
    paused = {household.path: why for household in keep if household.path not in stopped
              and (why := pause_of(household.path, household.info,
                                   [(one.path, one.info) for one in grouped.get(household.path, [])
                                    if not one.problem]))}
    # Every client folder that is no discovered household's is listed by
    # name (decision 188, R8): a household renamed in the firm's tree
    # leaves its old client folder here, and a folder nobody set up is
    # never adopted.
    # A household's client folder is the one whose name the file system
    # takes for its own (``os.path.normcase``: Windows folds case, so
    # Clients\park is the household Park's). The comparison key refuses,
    # it never identifies (the re-check's R1): a folder that only reads as
    # a household's - a Cyrillic letter, a second space - is another folder,
    # listed with its own sentence and never adopted or read.
    names = [one.name for one in [*(household.path for household in keep), *found.record_missing]]
    by_key = {layout.name_key(name): name for name in names}
    for folder in found.client_folders:
        if any(layout.names_one_folder(folder.name, name) for name in names):
            continue
        like = by_key.get(layout.name_key(folder.name))
        misfits.append(Misfit(folder, MISFIT_CLIENT_LOOK_ALIKE.format(household=like)
                              if like else MISFIT_CLIENT_NO_RECORD))
    return Registry(
        source=root,
        engagements=engagements,
        households=keep,
        misfits=sorted(misfits, key=lambda m: str(m.path).lower()),
        paused=paused,
        stopped=stopped,
    )


def held_back(household_dir: Path | str) -> str:
    """Why nothing may be written for this household now, or ``""``: it is
    stopped (its record gone while its returns hold theirs, or two folders
    claim it), paused (its folders and its record disagree), or its client
    folder is gone when its record shows it had one (the review's M3 and
    S4). The one question a new return into it and every form of Roll
    Forward ask before anything is written, with the sentence each stop
    has in the pass."""
    from tracker.households import client_folder_missing, household_pause, household_returns

    folder = Path(household_dir)
    if not ledger.path_for(folder).is_file():
        returns = household_returns(folder)
        return HOUSEHOLD_RECORD_MISSING.format(folder=folder.name) if returns else ""
    try:
        stopped = discover_engagements(folder.parent.parent).stopped
    except RegistryError:
        stopped = {}
    if said := stopped.get(folder):
        return said
    return household_pause(folder) or client_folder_missing(folder)


def _two_claims(households: list[Household]) -> dict[Path, str]:
    """Every household whose folder name or record's name is, by the
    layout's key, another household's too - each stopped with
    :data:`TWO_CLAIM` naming every such folder (SPEC-162 ruling 3, widened
    by decision 188). A copy of a household folder is never a second
    household, and which one is the real one is a person's to say."""
    keys = [{layout.name_key(one.path.name)} | ({layout.name_key(one.info.name)} if one.info.name
                                                 else set()) for one in households]
    group = list(range(len(households)))

    def top(i: int) -> int:
        while group[i] != i:
            i = group[i]
        return i

    for i in range(len(households)):
        for j in range(i + 1, len(households)):
            if keys[i] & keys[j]:
                group[top(j)] = top(i)
    stopped: dict[Path, str] = {}
    for i, one in enumerate(households):
        together = [other for j, other in enumerate(households) if top(j) == top(i)]
        if len(together) > 1:
            first = together[0]
            stopped[one.path] = TWO_CLAIM.format(
                name=first.info.name or first.path.name, a=first.path.name,
                b="`, `".join(other.path.name for other in together[1:]))
    return stopped


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description="List every household, return and left-alone folder the scheduled run "
                    "would find under a clients folder"
    )
    parser.add_argument("root", help="the folder the firm keeps its clients in")
    ns = parser.parse_args()

    # The root through the one door (decision 188): held to the settings'
    # rule, one level too deep included.
    from tracker import door

    try:
        loaded = discover_engagements(door.checked_root(ns.root))
    except door.DoorError as exc:
        raise SystemExit(str(exc)) from None
    except RegistryError as exc:
        raise SystemExit(f"Registry problem: {exc}") from None

    print(f"{loaded.source}: {len(loaded.households)} household(s), {len(loaded.active)} active "
          f"of {len(loaded.engagements)} return(s)")
    grouped = loaded.by_household()
    for household in loaded.households:
        head = household.name
        if household.problem:
            head += f"  (RECORD PROBLEM: {household.problem})"
        for word, said in (("STOPPED", loaded.stopped), ("PAUSED", loaded.paused)):
            if household.path in said:
                head += f"  ({word}: {said[household.path]})"
        print(f"  {head}")
        for engagement in grouped.get(household.path, []):
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
            print(f"    {engagement.label}{suffix}")
            print(f"        {engagement.path}")
    print(f"\n  Folders the tracker leaves alone ({len(loaded.misfits)})")
    for misfit in loaded.misfits:
        print(f"    {misfit.path}")
        print(f"        {misfit.sentence}")
