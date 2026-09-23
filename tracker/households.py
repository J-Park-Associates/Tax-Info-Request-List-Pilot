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
  details it has always read and knows nothing about households.

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

from tracker.layout import is_year_folder
from tracker.records import HouseholdInfo, household_to_json


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

    The name is never a field that moves: the folder is the name.
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
