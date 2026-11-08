"""A household's own edits - its members, the returns its inbox also feeds,
the households a person marked related - and the mirror that writes a
related mark onto every other household's record.

What the new-household dialog and the Edit Household modal send about a
household is read here, in parts that each uphold the decision rows they
name:

- **A household or return name** (decisions 125 and 188).
  :func:`_folder_name` is the layout's one name rule
  (``layout.checked_name``): a household and a return are each one folder
  name, refused in the same sentence wherever a name is typed - the
  dialog, a new return, a rolled return's new name, a feed.
- **The members** (P287). :func:`_members_from_spec` reads a list of names
  or one text with a name per line, the one parser for New Household and
  Edit Household alike.
- **The feeds** (decision 129). :func:`_feeds_from_spec` refuses a feed
  list that is not one: a household feeding itself, a blank half, a line
  the list already holds, and each half is held to the one name rule.
- **The related households** (pilot P141 and P170).
  :func:`_related_from_spec` refuses a list that is not other households'
  folder names, and every name must be a household under the clients root,
  read fresh from the private tree (``registry.households_named``), never
  inferred and never from the store.
- **P170's mirror.** :func:`_mirror_related` makes every other household's
  record agree with the related list just saved here. It reconciles rather
  than diffs, so a save that stopped between its two writes is repaired by
  saving either side again. It takes each other household's engagement
  lock in turn - one at a time and never two at once, so no lock order is
  needed - and reads that record fresh under it; a household whose record
  already agrees is left alone, with no lock taken and nothing written. A
  lock another pass holds is not waited on: that household comes back as
  pending, and the household edited stays saved.

**Why it is its own module** (SPEC-architecture-p5 P5.5, P342; the
architecture audit's C-1 item 3). These rules sat in ``tracker.api`` at
layer 5, where only the app's commands could reach them - the bug class
decision 123 found, when a rollover run on the command line missed a rule
the API alone applied. Here, a command line could reach them. The handler,
``tracker.api._cmd_edit_household``, keeps its body and calls these by
import: the body writes the command's warnings into the reply's envelope
(each household the mirror returns as pending is said as a notice), which
is the API's per-command state (the audit's C-3). ``tracker.api._cmd_create``
reads a new household's name and members here too, and the roll-household
command and :func:`tracker.creation._new_return_dir` (P343) read
:func:`_folder_name`.

**Why it sits at layer 3.** It asks :func:`tracker.registry.households_named`
in its own layer (the households a related list names, walked as the
practice's walk walks them); the household record (``households``), the
request list's refusal (``manifest``), the record types (``records``) and
:mod:`tracker.screen_words` (layer 1; the members' and the feeds' labels
and the three related refusals) below it; and the engagement lock and the
layout (layer 0). It imports nothing above layer 3, and never the API,
which imports from here by name what its handlers call. A stand-in follows
the name's readers (the audit's A-4): ``households_named`` and
``load_household_info`` are read here as well as in the API, so a stand-in
for either is set on both. It does not log.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tracker import layout
from tracker.households import load_household_info, save_household
from tracker.locking import EngagementLockedError, engagement_lock
from tracker.manifest import ManifestError
from tracker.records import FEED_REFUSED, Feed
from tracker.registry import households_named
from tracker.screen_words import (
    FEEDS_LABEL,
    MEMBERS_LABEL,
    RELATED_NOT_A_LIST,
    RELATED_REFUSED,
    RELATED_UNKNOWN,
)


def _folder_name(value: object, what: str) -> str:
    """One household or return name from what a person typed (``what`` is
    ``household`` or ``return``), or the refusal that says why.

    A household and a return are each **one** folder name: the layout puts
    them where they go (decision 125), and the layout's one name rule
    (decision 188, ``layout.checked_name``) says what one may be - the
    same sentence wherever a name is typed: the dialog, a new return, a
    rolled return's new name, a feed.
    """
    try:
        return layout.checked_name(value, what)
    except layout.LayoutError as exc:
        raise ManifestError(str(exc)) from None


def _members_from_spec(sent: object) -> tuple[str, ...]:
    """The household's members as the dialog and the editor send them:
    a list of names, or one text with a name per line (the editor's box).
    Anything else is refused by name; each name is whitespace-folded and
    a blank one is dropped.

    One helper for New household and Edit household (P287): a string is
    iterable, so reading it as a list made ``"Jane"`` the four members
    ``J``, ``a``, ``n``, ``e`` in one form while the other split it into
    lines. Nothing else parses members.
    """
    if sent is None or sent == "":
        return ()
    if isinstance(sent, str):
        sent = sent.splitlines()
    elif not isinstance(sent, (list, tuple)):
        raise ManifestError(f"{MEMBERS_LABEL} must be a list of names")
    folded = (" ".join(str(one).split()) for one in sent)
    return tuple(one for one in folded if one)


def _feeds_from_spec(sent: object, household_dir: Path) -> tuple[Feed, ...]:
    """The feed list a person built in the editor, refused where it is not
    one (decision 129).

    A household cannot feed itself - its own returns are fed already - and
    a blank household or return line names nothing a pass could resolve.
    A line the list already holds is refused rather than folded away, so a
    person sees that the one they picked was already there instead of
    wondering which of two rows is the real one.
    """
    if not isinstance(sent, (list, tuple)):
        raise ManifestError(f"{FEEDS_LABEL} is a list of returns this drop folder feeds")
    wanted: list[Feed] = []
    for one in sent:
        raw = one if isinstance(one, dict) else {}
        household = layout.normalised_name(raw.get("household", "") or "")
        return_name = layout.normalised_name(raw.get("return_name", "") or "")
        refusal = FEED_REFUSED.format(household=household or "(blank)",
                                      return_name=return_name or "(blank)")
        if not household or not return_name:
            raise ManifestError(refusal)
        # A feed names two folders, so each half is held to the layout's
        # one name rule (decision 188), and says why as a typed name does;
        # identity is the layout's one key, never a spelling.
        _folder_name(household, "household")
        _folder_name(return_name, "return")
        if layout.name_key(household) == layout.name_key(household_dir.name):
            raise ManifestError(refusal)
        if any(layout.name_key(held.household) == layout.name_key(household)
               and layout.name_key(held.return_name) == layout.name_key(return_name)
               for held in wanted):
            raise ManifestError(refusal)
        wanted.append(Feed(household=household, return_name=return_name))
    return tuple(wanted)


def _related_from_spec(sent: object, household_dir: Path) -> tuple[str, ...]:
    """The related households a person picked in the editor (pilot P170),
    refused where it is not a list of other households' folder names.

    Each name is held to the layout's one name rule, as a feed's halves
    are; the household itself, a blank and a name twice are refused by
    name; and every name must be a household under the clients root,
    read fresh from the private tree (never inferred, never from the
    store), so a link always points at a household that exists.
    """
    if not isinstance(sent, (list, tuple)) or not all(isinstance(one, str) for one in sent):
        raise ManifestError(RELATED_NOT_A_LIST)
    wanted: list[str] = []
    for one in sent:
        name = layout.normalised_name(one)
        if not name:
            raise ManifestError(RELATED_REFUSED.format(household="(blank)"))
        _folder_name(name, "household")
        if layout.name_key(name) == layout.name_key(household_dir.name) or \
                any(layout.name_key(held) == layout.name_key(name) for held in wanted):
            raise ManifestError(RELATED_REFUSED.format(household=name))
        wanted.append(name)
    if not wanted:
        return ()
    found = {layout.name_key(one.name): one.name
             for one in households_named(household_dir.parent, wanted).households}
    for name in wanted:
        if layout.name_key(name) not in found:
            raise ManifestError(RELATED_UNKNOWN.format(household=name))
    return tuple(found[layout.name_key(name)] for name in wanted)


def _mirror_related(household_dir: Path, after: tuple[str, ...]) -> list[str]:
    """Make every other household's record agree with the related list a
    person just saved here (pilot P170): each household it names names this
    one, and every other household no longer names this one. It reconciles
    rather than diffs, so a save that stopped between its two writes - one
    record naming the other, the other not - is repaired by saving either
    side again, and a removal made on the side that lacked the link clears
    the side that had it (the review's M1).

    The candidates are the households this list names and every household
    whose record names this one, found in one listing of the private tree
    (``households_named``). Each is then read and written **inside its own
    lock** (the review's S1): one lock at a time, never two, so no lock
    order is needed, and a change another writer made to that household
    before the lock is kept, since the record is read fresh under it. A
    lock that is held elsewhere is not waited on: that household is
    returned as pending, the household edited stays saved, and the caller
    says the link is not yet made (the re-check's MUST-R1)."""
    here = layout.name_key(household_dir.name)
    wanted = {layout.name_key(one) for one in after}
    private = household_dir.parent
    names = [one.name for one in private.iterdir() if one.is_dir() and layout.name_key(one.name) != here]
    practice = households_named(private, names).households if names else []
    pending: list[str] = []
    for other in practice:
        # A household whose record already agrees - it names this one
        # exactly when the saved list names it - is left alone: no lock is
        # taken and nothing is written (the re-check's MUST-R1: a
        # contact-only save touches no other household).
        named = any(layout.name_key(one) == here for one in other.info.related)
        if named == (layout.name_key(other.name) in wanted):
            continue
        # A household another pass holds is not waited on and does not undo
        # this save: its link is said as not yet made, and saving again
        # after its sort completes it (the repair above).
        try:
            with engagement_lock(other.path):
                info = load_household_info(other.path)
                kept = tuple(one for one in info.related if layout.name_key(one) != here)
                if layout.name_key(other.name) in wanted:
                    kept += (household_dir.name,)
                if kept != info.related:
                    save_household(other.path, replace(info, related=kept), lock_held=True)
        except EngagementLockedError:
            pending.append(other.name)
    return pending
