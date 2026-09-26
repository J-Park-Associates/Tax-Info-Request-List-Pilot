"""The household's own record: who it is, who it is shared with, where its
inbox is (decision 125).

A client folder is a household, and a household is the set of returns whose
people may all see each other's documents - because everyone shared on the
household's folder sees everything filed under it. It has a record of its
own, a journal in its folder in the private tree
(:data:`tracker.layout.PRIVATE_TREE`), carrying
:data:`tracker.ledger.HOUSEHOLD_CHANGED` lines:

- its **name**;
- its **members**: who a person typed as the people this folder is meant to
  be shared with. The tracker never makes, reads or changes a Drive share,
  so this is the firm's own note about what a person did, and it is
  labelled as one wherever it is shown;
- the **contact** every return's letter greets, and the **inbox link** every
  letter pastes. Both are copied into a return's own details when it is
  made and when it is rolled forward, so the reminder reads the five
  details it has always read and knows nothing about households;
- its **feeds** (decision 129): the return *lines* in other households this
  household's drop folder also feeds. A client with a co-owned business
  keeps one drop folder and the business lives in a household shared to
  its co-owners, so one inbox must be able to feed a return that lives
  somewhere else. A feed is ``Feed(household, return_name)``, resolved
  each pass to that household's open-year return of that name
  (:func:`resolve_feeds`), so the rollover carries nothing and a retired
  line is said. **Nothing infers one**: a household is assembled by a
  person and so is a feed.

**One journal machinery, two kinds of folder.** The household's record is a
journal under :data:`tracker.ledger.LEDGER_FILENAME`, beside a lock of the
same name a return's folder holds, folded by
:func:`tracker.ledger.apply` and held by :mod:`tracker.store` exactly as a
return's is - the store keys both by path and its ``kind`` column says
which. A second file format for four fields would have been a second thing
to keep honest; discovery tells the two apart positionally (it knows what
each level of the layout is) rather than by a file name.

**The firm's word about the share** (decision 126) is the one thing here
that is not a field. The tracker cannot see Drive's sharing, so pressing
*Mark as shared* records a :data:`tracker.ledger.SHARING_CONFIRMED` event
carrying nothing but its stamp, folded by nothing and read back by day
(:func:`shared_on`) - the pattern an approved draft uses. A field would
have claimed the household *is* shared; a dated event says only that a
person said so, which is the whole of what can honestly be recorded.

**What is never in it.** Not one word of a client's document, and no
document at all: a household record is about the folder, not about the
papers in it. The returns under it hold those.

This module sits at layer 1 beside :mod:`tracker.manifest`, which it is the
counterpart of - the manifest owns a return's list and details, this owns
the household's - and it reaches :mod:`tracker.store`, :mod:`tracker.ledger`
and :mod:`tracker.locking` at call time for exactly the reason the manifest
does.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from tracker.layout import CLIENT_FOLDER_MISSING as _CLIENT_FOLDER_MISSING
from tracker.layout import household_name_of, household_of, is_year_folder, name_key, year_of
from tracker.records import HouseholdInfo, household_to_json, link_problem


@dataclass(frozen=True, slots=True)
class HouseholdSaved:
    """What one save of a household recorded: the fields that moved, and
    whether anything was written at all."""

    fields: tuple[str, ...]
    recorded: bool


def _the_record(household_dir: Path | str):
    """The store's connection, brought up to this household's journal.

    Imported here and not at the top, exactly as ``tracker.manifest``
    does it: this module owns the household, the store owns the tables,
    and the two sit in one layer with no load-time edge between them. A
    folder with no journal is refused: it has nothing to fold and is
    nobody's household.
    """
    from tracker import ledger, store
    from tracker.manifest import NOT_AN_ENGAGEMENT, ManifestError

    folder = Path(household_dir)
    if not ledger.path_for(folder).exists():
        raise ManifestError(NOT_AN_ENGAGEMENT.format(name=folder.name,
                                                     ledger=ledger.LEDGER_FILENAME))
    conn = store.connect()
    store.follow_the_journal(conn, store.root_for(folder), folder)
    return conn


def create_household(household_dir: Path | str, info: HouseholdInfo) -> None:
    """Write a household's first record into its folder.

    The folder must exist and hold no journal: a live household carries a
    season of somebody's returns under it and must never be written over
    by a re-run. Under the household lock - the same lock file, in the
    household's own folder - the store is brought up to the (empty)
    journal and **one** ``household_changed`` event carries the whole of
    ``info``. That first event is what every later edit is a difference
    from, and what makes the fold of every event the household.
    """
    from tracker import ledger, store
    from tracker.locking import engagement_lock
    from tracker.manifest import ManifestError

    folder = Path(household_dir)
    if problem := link_problem(info.link):
        raise ManifestError(problem)       # decision 137, L5: a web address or nothing
    if not folder.is_dir():
        raise ManifestError(f"{folder} is not a folder; make it before creating the household")
    if ledger.path_for(folder).exists():
        raise ManifestError(f"Refusing to overwrite a household that already has a record: {folder}")
    conn = store.connect()
    with engagement_lock(folder):
        # A row the store may still hold for this folder - a household
        # whose folder was deleted by hand and is being set up again -
        # would read the new, shorter journal as truncated; forget it first.
        store.forget(conn, folder)
        store.follow_the_journal(conn, store.root_for(folder), folder)
        store.record(conn, folder, ledger.new(ledger.HOUSEHOLD_CHANGED, **{
            ledger.HOUSEHOLD_KEY: household_to_json(info),
        }))


def load_household_info(household_dir: Path | str) -> HouseholdInfo:
    """The household's details, as the record holds them.

    What the app's card shows, what a return's greeting and link are
    filled from at creation and at rollover, and what the client README's
    contact line falls back to. Every field is at its default on a
    household nothing has recorded details for. Raises
    :class:`tracker.manifest.ManifestError` for a folder that holds no
    record.
    """
    from tracker import store

    folder = Path(household_dir)
    conn = _the_record(folder)
    return store.household_info(conn, folder) or HouseholdInfo()


def save_household(
    household_dir: Path | str, info: HouseholdInfo, *, lock_held: bool = False
) -> HouseholdSaved:
    """Record a person's edit of the household as one event.

    Under the household lock (taken here unless the caller already holds
    it), the details are diffed against what the store holds and one
    ``household_changed`` event carries exactly the fields that moved.
    Nothing changed, nothing written: a save of the same household is not
    an event, which is ``save_rules``' rule and is what keeps a journal a
    record of decisions rather than of clicks.

    The name is never a field that moves here: the folder is the name
    (decision 188). The one writer of it after creation is the app's
    *Accept the folder's name*, which records the folder's name with the
    person's word (``ledger.ACCEPTED_KEY``) when a record claimed another.
    """
    from contextlib import nullcontext

    from tracker import ledger, store
    from tracker.locking import engagement_lock

    folder = Path(household_dir)
    now = household_to_json(info)
    with nullcontext() if lock_held else engagement_lock(folder):
        conn = _the_record(folder)
        before = household_to_json(store.household_info(conn, folder) or HouseholdInfo())
        moved = {name: value for name, value in now.items() if before.get(name) != value}
        if not moved:
            return HouseholdSaved(fields=(), recorded=False)
        # The inbox link is a web address or nothing (decision 137, L5),
        # refused when a save changes it.
        if "link" in moved and (problem := link_problem(str(moved["link"] or ""))):
            from tracker.manifest import ManifestError

            raise ManifestError(problem)
        store.record(conn, folder, ledger.new(ledger.HOUSEHOLD_CHANGED, **{
            ledger.HOUSEHOLD_KEY: moved,
        }))
    return HouseholdSaved(fields=tuple(moved), recorded=True)


def shared_on(household_dir: Path | str) -> dt.date | None:
    """The day the firm said it had shared this household, or ``None``.

    Decision 126. The tracker cannot see Drive's sharing - Drive for
    desktop exposes no permission to a program - so the two grants are a
    person's to make, once, and *Mark as shared* records that they did.
    The record of it is one :data:`tracker.ledger.SHARING_CONFIRMED` event
    carrying nothing but its stamp, **folded by nothing**, exactly as an
    approved draft is (:data:`tracker.ledger.DRAFT_APPROVED`): it is not a
    field of the household, so it costs the store no column and the
    journal no new shape, and it is read back by name out of the events.

    The newest one, as a local day, because the day is what a person
    reads; a household nobody has marked answers ``None`` and the card
    says so. **Nothing in the pass reads this.** It is the firm's note to
    itself, dated - not a condition of sorting, filing or drafting, none
    of which the tracker could make wait on a share it cannot see.
    """
    from tracker import ledger, store

    folder = Path(household_dir)
    conn = _the_record(folder)
    event = store.last_event(conn, folder, ledger.SHARING_CONFIRMED)
    return ledger.day_of(str(event.get(ledger.AT_KEY, ""))) if event else None


def household_returns(household_dir: Path | str) -> list[Path]:
    """Every return folder under one household, by year then name.

    **Positional, like discovery** (decision 125): a return is
    ``<household>/<YYYY>/<return>`` and a folder holding a journal
    anywhere else is not one. The order is the year's, then the folder
    name without case - the order the pass takes the locks in and the
    order a person reads the household's returns in, so "the first return
    by order" means one thing wherever it is said.
    """
    from tracker import ledger

    folder = Path(household_dir)
    found: list[Path] = []
    try:
        years = sorted((p for p in folder.iterdir() if p.is_dir() and is_year_folder(p.name)),
                       key=lambda p: p.name)
    except OSError:
        return []
    for year in years:
        try:
            children = sorted((p for p in year.iterdir() if p.is_dir()),
                              key=lambda p: p.name.lower())
        except OSError:
            continue
        found.extend(child for child in children if ledger.path_for(child).is_file())
    return found


#: What a feed nothing answers is said with, on every return of the
#: household whose drop folder carries it. Said rather than silently
#: dropped (decision 129): a feed is a return *line*, so a year the other
#: household has not opened yet, a line it retired, and a name somebody
#: mistyped all look the same from here and all deserve a sentence a
#: person can act on.
FEED_UNRESOLVED = ("this drop folder is set to feed {household} / {return_name}, which has no "
                   "active return for {year}")


def resolve_feeds(
    household_dir: Path | str, feeds: Iterable[object], year: int, registry: object
) -> tuple[list[object], list[str]]:
    """The returns this household's drop folder also feeds this year, and
    what could not be resolved.

    **A feed is a return line** (decision 129): ``Feed(household,
    return_name)`` names the line a return keeps every year, and this is
    where it becomes a return - the active, unsuperseded return that
    discovery found at ``<private tree>/<household>/<year>/<return name>``,
    matched by those folders' names under the layout's one comparison key
    (``layout.name_key``, decision 188) and never by a path made from the
    record's labels (decision 187). So the rollover
    carries nothing about feeds and a line the other household retired is
    said (:data:`FEED_UNRESOLVED`) rather than quietly feeding nothing.

    A feed naming **this** household resolves to nothing and is not
    warned about: a household's own returns are fed already, and the API
    refuses one being added.

    A fed household with **two open years** leaves its feed unresolved for
    this pass, for the reason its own inbox sorts nothing (decision 125):
    a household nobody can say the year of is not one a document may be
    filed into. The rest of the feed list proceeds.

    ``registry`` is duck-typed on ``engagements``, for the reason
    :func:`open_years` is duck-typed on its returns: :mod:`tracker.registry`
    sits above this module and the three facts read here - where a return
    is, whether it is still open, and which household it is under - are
    the record's own.
    """
    folder = Path(household_dir)
    every = list(getattr(registry, "engagements", []))
    wanted: list[object] = []
    said: list[str] = []
    for feed in feeds:
        if name_key(feed.household) == name_key(folder.name):
            continue
        # **By position, never built from the labels** (decision 187): the
        # feed's two names are compared with the folders discovery found,
        # and a label that is not a folder name matches nothing - it is
        # never joined onto the root to make a path of its own.
        theirs = [one for one in every
                  if household_of(one.path).parent == folder.parent
                  and name_key(household_name_of(one.path)) == name_key(feed.household)]
        found = next((one for one in theirs
                      if one.active and one.tax_year == year and year_of(one.path) == year
                      and name_key(Path(one.path).name) == name_key(feed.return_name)), None)
        if found is None or len(open_years(theirs)) != 1:
            said.append(FEED_UNRESOLVED.format(household=feed.household,
                                               return_name=feed.return_name, year=year))
        else:
            wanted.append(found)
    return wanted, said


def fed_by(registry: object, household_dir: Path | str) -> list[object]:
    """The households whose drop folders feed a return of this one.

    What the **destination's** card says (``tracker.api.FED_BY_LINE``):
    anyone who can drop into one of these folders can drop for a return
    that lives here, so the household whose documents rest here is told
    who else may send them. The evidence and the record name a return by
    its label and never a household's members; who is shared on a
    household is on that household's own card.

    ``registry`` is duck-typed on ``households``, as
    :func:`resolve_feeds` is on its engagements.
    """
    name = name_key(Path(household_dir).name)
    return [one for one in getattr(registry, "households", [])
            if any(name_key(feed.household) == name for feed in one.info.feeds)]


def return_name_taken(year_dir: Path | str, return_name: str) -> str | None:
    """The name of a return folder already in ``year_dir`` that is
    ``return_name`` by the layout's key (decision 188), or ``None``.

    A return is unique within its household-year by the key and not by
    its spelling, so ``1040 - Park`` and ``1040 - PARK`` - or a look-alike
    typed in another script - are one return, and the second is refused
    where the first already is. Asked by the new-return dialog and the rollover
    before anything is made; a year folder not there yet holds nothing.
    """
    wanted = name_key(return_name)
    try:
        folders = [one.name for one in Path(year_dir).iterdir() if one.is_dir()]
    except FileNotFoundError:
        return None
    return next((name for name in sorted(folders) if name_key(name) == wanted), None)


def open_years(returns: Iterable[object]) -> list[int]:
    """The tax years this household still has work in, ascending.

    The distinct years of its **active, unsuperseded** returns: a prior a
    rollover retired is not an open year, and neither is one a person
    switched off in the editor. Two open years is what the pass refuses to
    sort from one inbox on, because the inbox cannot say which year a
    document is for (``tracker.runner.TWO_OPEN_YEARS``).

    Duck-typed on ``active`` and ``tax_year`` rather than typed on
    ``tracker.registry.Engagement``, because that module sits three layers
    above this one and the two facts it reads are the record's own.
    """
    years = {one.tax_year for one in returns if one.active and one.tax_year is not None}
    return sorted(years)


# ------------------------------------------------ the folder is the name ----

#: What every run of a household whose folders and record disagree carries
#: as its error (decision 188, R6): the folder is the identity and the
#: record's labels are a claim, and a claim that disagrees pauses the
#: whole household - red, every pass - until a person acts.
HOUSEHOLD_PAUSED = ("Paused: this folder's name and its record's name disagree. Nothing is sorted, "
                    "laid out or drafted for the household until a person opens it in the app and "
                    "accepts the folder's name, or gives the folder back the name its record holds.")
#: The same pause where a return's folder sits under a year its record
#: does not hold: a return's year is its record's (decisions 126 and 177),
#: so it is never accepted in the app.
HOUSEHOLD_PAUSED_YEAR = ("Paused: a return's folder sits under a year its record does not hold. "
                         "Nothing is sorted, laid out or drafted for the household until the folder "
                         "goes back under the year its record holds; a return in the wrong year is "
                         "retired and made again.")
#: What every run of a household carries when its client folder is gone
#: and the household had one: the layout's sentence since the review of
#: decision 188, named here still.
CLIENT_FOLDER_MISSING = _CLIENT_FOLDER_MISSING


def claim_disagrees(claim: object, folder_name: str) -> bool:
    """Whether a record's label claims another name than its folder's: by
    the layout's one key (decision 188), and never for a blank claim,
    which claims nothing (a record from before decision 125)."""
    return bool(claim) and name_key(str(claim)) != name_key(folder_name)


def return_disagrees(return_dir: Path | str, info: object) -> str:
    """``"name"`` when a return's record claims another household or return
    name than its folders', ``"year"`` when it claims another year than
    the folder above it, else ``""``. Duck-typed on the details' three
    fields."""
    folder = Path(return_dir)
    year = getattr(info, "tax_year", None)
    if year is not None and year != year_of(folder):
        return "year"
    if (claim_disagrees(getattr(info, "household", ""), household_name_of(folder))
            or claim_disagrees(getattr(info, "return_name", ""), folder.name)):
        return "name"
    return ""


def pause_of(household_dir: Path | str, info: HouseholdInfo,
             returns: Iterable[tuple[Path, object]]) -> str:
    """Why this household is paused - :data:`HOUSEHOLD_PAUSED` or
    :data:`HOUSEHOLD_PAUSED_YEAR` - or ``""`` when every claim agrees
    (decision 188, R6).

    The household's claim is its record's name; each return's are its
    household, its return name and its year. **Any disagreement pauses
    the whole household**, because its returns share one inbox, one
    client folder and one README: the pass does not sweep, lay out, sort,
    scan, draft or refresh anything for it, and Roll forward and a new
    return into it refuse, until a person accepts the folder's name in
    the app or gives the folder back its name. This overrides decision
    177's warning and decision 125's "the record wins".
    """
    kinds = {return_disagrees(path, one) for path, one in returns} - {""}
    if "year" in kinds:
        return HOUSEHOLD_PAUSED_YEAR
    if kinds or claim_disagrees(info.name, Path(household_dir).name):
        return HOUSEHOLD_PAUSED
    return ""


def household_pause(household_dir: Path | str) -> str:
    """:func:`pause_of` read off the disk: the household's record and each
    of its returns' details. A record that cannot be read claims nothing
    here; the pass says its own problem."""
    from tracker.manifest import ManifestError, load_engagement_info

    folder = Path(household_dir)
    try:
        info = load_household_info(folder)
    except Exception:
        info = HouseholdInfo()
    returns = []
    for one in household_returns(folder):
        try:
            returns.append((one, load_engagement_info(one)))
        except (ManifestError, ValueError, OSError):
            continue
    return pause_of(folder, info, returns)


def client_side_expected(household_dir: Path | str, returns: Iterable[Path]) -> bool:
    """Whether this household's client folder is known to have existed
    (SPEC-162 ruling 2, kept by decision 188): the firm said it shared the
    household, or a recorded original of one of its returns rests under
    ``Clients\\<its folder name>``. Then a missing client folder is a
    household renamed or moved - :data:`CLIENT_FOLDER_MISSING`, and nothing
    is made - and never a new household to lay out again."""
    from tracker import layout, store

    folder = Path(household_dir)
    try:
        if shared_on(folder) is not None:
            return True
    except Exception:                   # a household whose record cannot be read
        pass
    root = folder.parent.parent
    for one in returns:
        try:
            held = store.documents(_the_record(one), one)
        except Exception:
            continue
        for row in held:
            if row.get("pbc_location"):
                place = layout.place_of(root, layout.locate(one, row["pbc_location"]))
                if place.kind in layout.CLIENT_KINDS and not claim_disagrees(place.household,
                                                                             folder.name):
                    return True
    return False


def client_folder_missing(household_dir: Path | str, returns: Iterable[Path] | None = None) -> str:
    """``door.client_folder_missing`` for this household, the record's half
    read here (:func:`client_side_expected`): the one verdict every writer
    asks before it writes (the review's M3)."""
    from tracker import door

    folder = Path(household_dir)
    folders = list(returns) if returns is not None else household_returns(folder)
    return door.client_folder_missing(folder.parent.parent, folder.name,
                                      had_one=client_side_expected(folder, folders))
