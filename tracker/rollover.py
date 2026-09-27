"""Carry a returning client's request list into the next year (component 8).

A client who filed with us last year is not a blank form. What they actually
sent, what we set aside, how many W-2s really turned up — that is better
information than any generic checklist, so for an existing client **the prior
year takes precedence and the form template does not get a vote.**

Precedence, precisely:

- Every field the prior year specifies is carried forward untouched. The
  template never overwrites a value that already exists.
- The template may only *fill blanks* — a keyword or extension the prior
  list simply never had. Filling an empty field overrides nothing.
- Periods, date rules and any year inside a document name are shifted by the
  same number of years, so ``TY2025`` becomes ``TY2026`` and the row asking
  for the ``TY2024`` prior-year return now asks for ``TY2025``.
- Counts learn from reality: a row that expected 2 W-2s and received 3 asks
  for 3 next year. Counts are never lowered — a client who under-delivered
  still owes what was asked.
- ``Override.NOT_APPLICABLE`` is a decision about the client, so it carries
  forward - under its own heading, for a fresh decision: the row keeps the
  override and its note says so, and a person clears it in the editor if
  this year is different (decision 116; decision 10 stands).
  ``Override.ACCEPTED`` is a judgment about specific files from one particular year,
  so it does not.
- **A keyword a person's filing taught last year is carried as an ordinary
  Any Keyword.** Those live in the engagement's record (decision 103), and
  ``load_manifest()`` lays them over the row's typed keywords - so they
  reach ``_carry`` as keywords like any other and land in next year's
  list, in the record, where the editor shows them and a person can edit
  them. That is the one moment a taught keyword becomes something typed;
  a learned row would be invisible in the editor.

- **Whether a row is asked carries** (decision 142), and so does whether
  its document is named (decision 128, which this line used to drop, so a
  ``named=no`` row came back ``named=yes``). **A row nobody asked for
  that received a document this year is asked next year**: the client
  sent one, so asking is the likelier need, and a person unticks it in
  the editor if not - the count-learning above reads Received the same
  way.

A template row the client has never had is **added as not asked**
(decision 142, rewording decision 9, which offered those rows and added
none). Every catalog row is on every return: a row nobody asked for is
never listed as needed and never chased, so it pads nothing the client
sees, and a document that arrives for it files there instead of parking.
A person asks for one by setting Asked in the editor. (Until decision 142
those rows were *offers*, reported once and added only with
``include_new``; until decision 104 the offers and last year's unfiled
files were also written to a Carried Forward sheet of next year's
workbook. Neither exists now.)

Nothing here writes to the prior year's engagement — it is read-only history.

**A household rolls as a household** (decision 126). A client sees one
folder and one inbox, so Roll forward takes the household's open year and
rolls every ticked return into the next one by the rule above, and
retires every return left unticked with a single details edit
(``active: no``) — so the household has exactly one open year again when
it is done and its inbox goes on being sorted. :func:`roll_household` is
that roll; :func:`roll_forward` stays the primitive it plans with and the
per-return command line still rolls one. **It is every ticked return or
none** (decision 159, amending 126's "one return's refusal undoes none of
the others"): every refusal is found before anything is written, the
household's lock and every open return's are taken before the first
write, and a failure while making one new return removes the ones made
before it. A half-rolled household is the two-open-years state the roll
exists to end, and a pass could sort it between two rolls. A return that
*was* rolled needs no edit: its successor's Rolled From is what retires
it, exactly as it always has been.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
from collections.abc import Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from pathlib import Path

from tracker import errors
from tracker.fsio import make_new_folders
from tracker.households import (
    household_returns,
    load_household_info,
    open_years,
    return_name_taken,
)
from tracker.layout import (
    LayoutError,
    household_of,
    name_key,
    normalised_name,
    return_dir_for,
    root_of,
)
from tracker.manifest import (  # shift_years/detect_year re-exported: they live in manifest
    ManifestError,
    Override,
    RequestItem,
    Status,
    check_tax_year,
    create_engagement,
    detect_year,
    has_arrived,
    item_from_record,
    load_engagement_info,
    load_manifest,
    override_label,
    save_rules,
    shift_item,
    shift_years,
    validated,
)
from tracker.records import EngagementInfo, HouseholdInfo, link_problem
from tracker.templates import ask_by_for, filing_deadline_for, template_items

#: Why a row is on the new list. Reported in the CLI and the API's reply.
ORIGIN_PRIOR = "carried from last year"
ORIGIN_NOT_APPLICABLE = "not applicable last year"
ORIGIN_NEW = "new this year"
#: The note on a catalog row the client never had, added as not asked
#: (decision 142).
NEW_NOT_ASKED_NOTE = "not on last year's list: added as not asked; set Asked in the editor to ask for it"
#: The notes on a row nobody asked for last year: still not asked, or
#: asked now because a document arrived for it (decision 142).
NOT_ASKED_NOTE = "not asked last year; still not asked"
NOW_ASKED_NOTE = "not asked last year, but received ({n} file(s)); asked for this year"
#: The note on a row carried as not applicable: last year's call, named
#: with its year, and the two things a person may do about it.
NOT_APPLICABLE_NOTE = (
    "{label} last year - decide afresh: clear the override in the editor to ask for it, "
    "or leave it set aside"
)
#: Heads the CLI's list of those rows, printed after the carried and new ones.
PREVIOUS_NOT_APPLICABLE_HEADING = "Previous Year Not Applicable - decide afresh:"

#: What stands in for the target year when the prior list gave none away.
UNKNOWN_YEAR_LABEL = "next year"
#: Heads the CLI's list of last year's unmatched documents.
UNFILED_HEADING = "Sent last year but never filed — check these are covered:"

#: Why a household cannot be rolled: the inbox cannot say which year a
#: document is for, and neither can a rollover say which year it is
#: rolling. A person retires a year before rolling the household
#: (decision 126; ``tracker.runner.TWO_OPEN_YEARS`` is the pass's half of
#: the same rule).
ROLLOVER_TWO_OPEN_YEARS = (
    "this household has two open years ({years}); retire one in the editor before rolling forward"
)
#: Why one plan is not this household's business: a household rollover
#: rolls the returns of its own open year and nothing else.
ROLLOVER_NOT_THIS_HOUSEHOLD = "{prior} is not an open-year return of {household}"
#: What a return left unticked by a household rollover is retired with.
#: The retirement itself is an ordinary details edit (``active: no``) and
#: the reason is not a detail field, so it is said where a person reads
#: it: beside the retired return on the command line, and in the runbook.
RETIRED_BY_ROLLOVER = "retired by the household's rollover on {day}: it was not rolled into {year}"
#: The command line's headings over what one household rollover did.
ROLLED_HEADING = "ROLLED"
NOT_ROLLED_HEADING = "NOT ROLLED"
#: Every ticked return was rolled and a retirement failed (decision 159).
NOT_ALL_RETIRED_HEADING = "ROLLED, NOT ALL RETIRED"
RETIRED_HEADING = "RETIRED (not rolled into {year})"
#: A household roll is every ticked return or none (decision 159): one
#: return's refusal is the whole call's, said with that return's sentence.
NOTHING_ROLLED = "{prior}: {why}. Nothing was rolled."
#: Every return was rolled, and a retirement then failed: a retirement is a
#: record line and is not undone, so the sentence says where it stopped.
ROLLOVER_NOT_RETIRED = (
    "Rolled into {year}: {rolled}. Retired: {retired}. Not retired: {left} ({why}); "
    "retire those in the editor (Active: no) so the household has one open year"
)


@dataclass(frozen=True, slots=True)
class RolledItem:
    """One row of next year's list, and where it came from."""

    item: RequestItem
    origin: str
    note: str = ""
    prior_status: str = ""
    prior_file_count: int | None = None


@dataclass(slots=True)
class RolloverReport:
    """Next year's request list, built from last year's engagement."""

    prior_dir: Path
    prior_year: int | None = None
    target_year: int | None = None
    rolled: list[RolledItem] = field(default_factory=list)
    unfiled_last_year: list[str] = field(default_factory=list)
    #: :data:`LINK_NOT_CARRIED` when the prior's link was left behind
    #: because it is not a web address (decision 137, L5), else ``""``.
    link_dropped: str = ""
    #: What creating the new year said of the rows carried (decision 201):
    #: a same-name issuer pair last year's list already held, carried as it
    #: was, in :data:`tracker.manifest.ISSUER_NAMED_TWICE`'s words.
    warnings: list[str] = field(default_factory=list)

    @property
    def items(self) -> list[RequestItem]:
        return [r.item for r in self.rolled]

    @property
    def from_last_year(self) -> list[RequestItem]:
        """Every row that was on last year's list - active or set aside -
        and not a row this roll added from the catalog (decision 201): the
        rows whose names nobody touched, which ``create_engagement`` carries
        as they were."""
        return [r.item for r in self.rolled if r.origin != ORIGIN_NEW]

    @property
    def carried(self) -> list[RolledItem]:
        """Last year's active rows, carried: not the new ones, and not the
        rows set aside, which are their own list (``not_applicable``)."""
        return [r for r in self.rolled if r.origin == ORIGIN_PRIOR]

    @property
    def added(self) -> list[RolledItem]:
        return [r for r in self.rolled if r.origin == ORIGIN_NEW]

    @property
    def not_applicable(self) -> list[RolledItem]:
        return [r for r in self.rolled if r.origin == ORIGIN_NOT_APPLICABLE]


@dataclass(frozen=True, slots=True)
class ReturnPlan:
    """One return a household rollover was asked to roll.

    ``prior`` is the return folder the new year is built from; ``form`` is
    the catalog template consulted to fill blanks and to add, as not asked,
    the rows the client never had (blank: last year's list as it stands);
    ``return_name`` renames the return, and blank keeps the name
    it has had every year, which is the ordinary case - the app's
    checklist sends no name at all.
    """

    prior: Path
    form: str = ""
    return_name: str = ""


@dataclass(slots=True)
class HouseholdRollover:
    """What one household rollover did: what rolled, what was left behind,
    and what refused.

    ``rolled`` is ``(prior, created, report)`` per return, in the order
    they were rolled; ``retired`` is every open-year return that was not
    planned, each now ``active: no`` by one event of its own. ``skipped``
    is kept for the reply's shape and is always empty since decision 159:
    a household roll is every ticked return or none, and a refusal is
    raised for the whole call.
    """

    target_year: int
    rolled: list[tuple[Path, Path, RolloverReport]] = field(default_factory=list)
    retired: list[Path] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)


# ------------------------------------------------------------- carry rules ----

#: What a rollover says of a link it did not carry (decision 137, L5, the
#: owner's ruling on phase 1): a link recorded before the rule that is not a
#: web address is dropped, with this reason, rather than refusing the roll -
#: the same treatment an existing letter gives it.
LINK_NOT_CARRIED = ("The link '{link}' was not carried into the new year: it is not a web "
                    "address (http:// or https://). Paste the inbox's link into the "
                    "household's or the return's details.")


def carried_link(link: str) -> tuple[str, str]:
    """The link a rolled return starts with, and why it was dropped when it
    was: a web address is carried as it is; anything else is dropped with
    :data:`LINK_NOT_CARRIED` (decision 137, L5)."""
    if link_problem(link):
        return "", LINK_NOT_CARRIED.format(link=str(link).strip())
    return link, ""


def next_tax_year(prior_year: int) -> int:
    """The year a rolled engagement is for: the one after the prior's."""
    return prior_year + 1


def carry_engagement_info(
    prior: EngagementInfo, *, rolled_from: str, tax_year: int | None = None
) -> EngagementInfo:
    """Last year's details as this year's starting point.

    The client, the sender, the firm and the reminders decision are about
    the client and carry forward. So does the catalog the list was cut from:
    a returning client files the same return next year, and the rolled list
    is last year's list. So do the household and the return's own name
    (decision 125): a return keeps its name every year, under the same
    household, which is what lets one return line be followed and named.
    So do the **people** (decision 128): the same person files the same
    return next year and their documents print their name the same way, so
    the list carries unchanged and the card's roll fold asks for one
    look at it - nothing blocks on that look, because strict parking is
    the safety net if nobody gives it.
    The share link, the due date and the filing
    deadline are this year's to set - a statutory date is the year's, and
    one carried forward would put a date twelve months gone into a client's
    reminder (decision 117). The name is never written (the folder is the
    name), and Rolled From is what retires the prior
    (tracker.registry.mark_superseded).

    A prior that never recorded a form carries a blank one - nothing here
    guesses which catalog an older engagement was built from.

    The two dates are cleared here and refilled for the target year by
    :func:`with_default_dates`, whichever way the rollover is run. The tax
    year is the target's, and the caller passes it: it is the year folder
    the new return is made under.
    """
    return replace(prior, name="", link="", due=None, filing_deadline=None,
                   active=True, rolled_from=rolled_from, tax_year=tax_year)


def with_default_dates(info: EngagementInfo, form: str, year: int | None) -> EngagementInfo:
    """The details with the two dates the form implies, where they are blank.

    Decision 117. The reminder's ladder is measured against the Due Date,
    so an engagement nobody typed a date into would sit on its first rung
    for ever and the escalation would be a feature nobody switched on. The
    Filing Deadline comes from the form's own table for the year after the
    tax year, and the Due Date from it - the firm's ask-by target. Both are
    ordinary details afterwards: editable, clearable, and never written
    over once they hold anything.

    A form the catalog has no deadline for fills nothing: a guessed
    statutory date is worse than a blank one, because the blank is silent
    and the guess is read out to a client.

    It lives here, beside the carry rule that clears the two dates, and it
    serves both ways an engagement is made from a form and a year: the
    app's create and rollover commands and this module's command line
    (decision 123).
    """
    if not form or year is None:
        return info
    deadline = info.filing_deadline or filing_deadline_for(form, year)
    if deadline is None:
        return info
    return replace(info, filing_deadline=deadline, due=info.due or ask_by_for(deadline))


def _carry(
    prior: RequestItem, template: RequestItem | None, delta: int, tmpl_delta: int
) -> tuple[RequestItem, str, str]:
    """Build next year's row from last year's, filling only true blanks."""
    # Counts learn from what actually arrived, and never shrink.
    expected = prior.expected_count
    if prior.status == Status.RECEIVED and (prior.file_count or 0) > expected:
        expected = prior.file_count

    # The template fills a blank; it never replaces a value.
    def fill(mine, theirs):
        return mine if mine else (theirs or ())

    # A year check derived from Period is not carried as text: the shifted
    # Period derives it again when the list is validated, so the new list
    # stays as sparse as the old one was.
    date_pattern = "" if prior.date_pattern_derived else shift_years(prior.date_pattern, delta)
    if not date_pattern and template and not template.date_pattern_derived:
        date_pattern = shift_years(template.date_pattern, tmpl_delta)

    item = RequestItem(
        identifier=prior.identifier,
        document=shift_years(prior.document, delta),
        period=shift_years(prior.period, delta) or (
            shift_years(template.period, tmpl_delta) if template else ""
        ),
        expected_count=expected,
        allowed_extensions=fill(prior.allowed_extensions,
                                template.allowed_extensions if template else ()),
        min_size_kb=prior.min_size_kb,
        required_keywords=fill(prior.required_keywords,
                               template.required_keywords if template else ()),
        any_keywords=fill(prior.any_keywords,
                          template.any_keywords if template else ()),
        date_pattern=date_pattern,
        # Not Applicable is about the client and persists, with its reason
        # if one was given. Accepted was a call on last year's particular
        # files and must not pre-approve this year's, so neither it nor its
        # reason carries.
        manual_override=(
            Override.NOT_APPLICABLE if prior.manual_override == Override.NOT_APPLICABLE else ""
        ),
        override_reason=(
            prior.override_reason if prior.manual_override == Override.NOT_APPLICABLE else ""
        ),
        # Both marks carry (decision 142; ``named`` was dropped here until
        # then). A row nobody asked for that a document arrived for is
        # asked next year: the client sent one.
        named=prior.named,
        asked=prior.asked or has_arrived(prior),
        # The short name carries, its years moving with the document's
        # (decision 144). A row with none takes the catalog's, but only
        # where the row still asks for the catalog's document: a row a
        # person renamed under the same identifier keeps deriving its own.
        short_title=shift_years(prior.short_title, delta) or (
            template.short_title
            if template and shift_years(template.document, tmpl_delta) == shift_years(prior.document, delta)
            else ""
        ),
    )

    if prior.manual_override == Override.NOT_APPLICABLE:
        return item, ORIGIN_NOT_APPLICABLE, NOT_APPLICABLE_NOTE.format(label=override_label(prior))
    if not prior.asked:
        if item.asked:
            return item, ORIGIN_PRIOR, NOW_ASKED_NOTE.format(n=prior.file_count or 0)
        return item, ORIGIN_PRIOR, NOT_ASKED_NOTE
    if prior.status == Status.RECEIVED:
        note = f"received last year ({prior.file_count or 0} file(s))"
        if expected > prior.expected_count:
            note += f"; asking for {expected} this year to match"
        return item, ORIGIN_PRIOR, note
    if prior.status:
        return (
            item,
            ORIGIN_PRIOR,
            f"last year: {prior.status} — confirm it still applies",
        )
    return item, ORIGIN_PRIOR, "on last year's list"


# ---------------------------------------------------------------- rollover ----


def roll_forward(
    prior_engagement_dir: Path | str,
    *,
    target_year: int | None = None,
    template: Sequence[RequestItem] = (),
) -> RolloverReport:
    """Build next year's request list from ``prior_engagement_dir``.

    ``template`` is the form's standard checklist. It fills blanks on
    carried rows and never overrides prior-year data; the rows the client
    has never had are added as not asked (decision 142).
    """
    prior_dir = Path(prior_engagement_dir)
    # A year is bounded wherever it is typed (decision 68 bounded the
    # app's year box; the flag on this command line was the other door).
    # Unbounded, --year 20265 shifts every Period and every document name
    # by eighteen thousand years, writes the folders under those names and
    # retires the live engagement behind them.
    if target_year is not None:
        check_tax_year(target_year)
    # Last year, as its record has it: the statuses the last scan wrote,
    # the file counts it saw, and the keywords somebody's filings taught
    # the rows. The taught keywords matter here more than anywhere - they
    # are what a person had to teach one engagement by hand, and carrying
    # them forward is the whole reason a returning client's list beats a
    # template. Nothing in the prior year is opened for writing.
    prior_items = load_manifest(prior_dir)

    prior_year = detect_year(prior_items)
    if target_year is None and prior_year is not None:
        target_year = next_tax_year(prior_year)
    if prior_year and target_year and target_year <= prior_year:
        # A roll into the same year would retire the live engagement in
        # favour of a copy of itself; into an earlier one would shift every
        # period backwards. Neither is a rollover.
        raise ManifestError(
            f"Roll forward to a year after {prior_year}; {target_year} is not later"
        )
    delta = (target_year - prior_year) if (prior_year and target_year) else 0

    template_year = detect_year(template) if template else None
    tmpl_delta = (
        target_year - template_year if (template_year and target_year) else 0
    )

    report = RolloverReport(
        prior_dir=prior_dir, prior_year=prior_year, target_year=target_year
    )
    by_id = {t.identifier: t for t in template}

    for prior in prior_items:
        item, origin, note = _carry(prior, by_id.get(prior.identifier), delta, tmpl_delta)
        report.rolled.append(
            RolledItem(
                item=item, origin=origin, note=note,
                prior_status=prior.status, prior_file_count=prior.file_count,
            )
        )

    # By the identifier as validated() compares it - without case - or a
    # template row differing from a prior's only in case would be added
    # beside it and the new list refused as a duplicate.
    seen = {p.identifier.upper() for p in prior_items}
    for spec in template:
        if spec.identifier.upper() in seen:
            continue
        report.rolled.append(RolledItem(
            item=replace(shift_item(spec, tmpl_delta), asked=False),
            origin=ORIGIN_NEW,
            note=NEW_NOT_ASKED_NOTE,
        ))

    report.unfiled_last_year = _unfiled_last_year(prior_dir)
    return report


def _unfiled_last_year(prior_dir: Path) -> list[str]:
    """Documents the client sent last year that were never filed.

    Reported, never acted on: a request row needs a name and rules a person
    chooses. But a document that arrived and fitted nowhere is exactly the
    gap next year's list should close.

    One line per original, keyed by where the original rests
    (``pbc_location``, the record's own key), never by the name the client
    gave it (decision 190): two different files called ``scan.pdf`` are two
    documents never filed, and counting them as one would under-state the
    gap. The line quotes the row's Reason, which since 190 carries no
    subfolder - that is its own column, and the client's folder name is not
    a reason anything was not filed.
    """
    from tracker.filer import NEEDS_REVIEW, ensure, read_index

    try:
        # A rollover only reads the prior year, and it reads it without
        # touching it: the store is built out of the record beside it and
        # nothing is written in the folder.
        ensure(prior_dir)
        rows = read_index(prior_dir)
    except Exception:  # an unreadable index must never block a rollover
        return []
    seen: dict[str, tuple[str, str]] = {}
    for row in rows:
        key = row.pbc_location or row.digest or row.original_name
        if row.decision == NEEDS_REVIEW and key not in seen:
            seen[key] = (row.original_name, row.reason)
    return [f"{name} — {reason}" for name, reason in seen.values()]


# ------------------------------------------------------- the household roll ----


def _same_folder(path: Path) -> str:
    """One folder, as two spellings of it compare: resolved, and without
    case, because Windows hands the same folder back under either."""
    try:
        return os.path.normcase(str(Path(path).resolve()))
    except OSError:                       # an unreachable drive is not a match
        return os.path.normcase(str(Path(path)))


def _rows_as_stored(return_dir: Path) -> list[RequestItem]:
    """The return's rules exactly as the record holds them.

    Not :func:`tracker.manifest.load_manifest`, which lays the keywords a
    person's filing taught over each row's typed ones: saving those back
    would turn a taught word into a typed one and make a retirement carry
    a list somebody has to read. The retirement changes one field, so the
    rows it saves must be the rows already stored, byte for byte.
    """
    from tracker import store

    return [item_from_record(row)
            for row in store.rules(store.connect(), return_dir) or []]


def open_year_returns(household_dir: Path | str) -> tuple[list[int], list]:
    """The household's one open year and its active returns, or a refusal.

    The first thing a household rollover reads, and what the command line
    asks to turn ``--all`` and ``--only`` into plans - one reading of the
    household, used by both, so what the CLI offers and what the roll
    accepts cannot drift apart. More than one open year is refused here
    (:data:`ROLLOVER_TWO_OPEN_YEARS`): there is no single year to roll, and
    a person retires one in the editor first.
    """
    from tracker.registry import engagement_from, mark_superseded

    folder = Path(household_dir)
    returns = mark_superseded([engagement_from(one) for one in household_returns(folder)])
    years = open_years(returns)
    if len(years) > 1:
        raise ManifestError(ROLLOVER_TWO_OPEN_YEARS.format(
            years=", ".join(str(year) for year in years)))
    return years, [one for one in returns
                   if one.active and years and one.tax_year == years[0]]


def roll_household(
    household_dir: Path | str,
    *,
    target_year: int,
    plans: Sequence[ReturnPlan],
    today: dt.date | None = None,
) -> HouseholdRollover:
    """Roll one household's year forward, every ticked return or none, and
    retire what it leaves behind (decisions 126 and 159).

    **The household is what a person rolls**, because the household is what
    the client sees: one inbox, one folder, and however many returns the
    firm keeps under it. Roll forward takes the open year's active returns,
    rolls each ticked one into ``target_year`` exactly as the per-return
    rollover does - the same carry rule, the same defaults - and sets every
    unticked one ``active: no`` with one details edit. So the household has
    **exactly one open year again** when it is done, whichever returns were
    ticked, and the next pass sorts its inbox instead of refusing on two
    open years.

    **All or nothing (decision 159, amending 126).** Until 159 a refusal on
    one return was recorded in ``skipped`` and the loop went on, and a pass
    could sort the household between two rolls: the household was left half
    in one year and half in the next, which is the two-open-years state the
    roll exists to end. Now, in this order:

    1. **Plan, writing nothing.** Every refusal a roll can make - a target
       that already exists, a path past what Windows will open, a year that
       is not after the prior's, a list that does not validate, and a
       return that cannot be retired - is found for every return first
       (:func:`_plan_one`). Any refusal raises :class:`ManifestError`
       naming the return, with its sentence and :data:`NOTHING_ROLLED`.
    2. **Every lock, before any write**: the household's own (its journal
       is guarded by the same lock file), then every open return's, ticked
       or not, in folder-name order without case. A lock another run holds
       raises ``EngagementLockedError`` and nothing is written.
    3. **Make every new return** (:func:`_make_one`). A failure on any one
       removes every return this call made - the folders only its own
       ``make_new_folders`` made, and their store rows - and raises. A new
       return's record is inside its new folder, so this undo removes only
       what this call made (decision 137 M1).
    4. **Only then retire** the unticked returns, under the locks already
       held, each from its rows and details **read again under its lock**,
       so an edit a person saved while the roll was planning is kept. A
       retirement is a record line and cannot be undone: one that fails
       raises :class:`RolledNotAllRetired`, naming what was rolled, which
       returns were retired and which were not, and a person retires the
       rest in the editor. The household scaffold and README refresh still
       run first, because the new year's returns exist.

    ``HouseholdRollover.skipped`` stays for the reply's shape and is always
    empty: a refusal is now the whole call's.

    **A return rolled here needs no retiring:** its successor's Rolled
    From is what retires it, as it always has been
    (``tracker.registry.mark_superseded``). Only a return left out of the
    plan gets the details edit.

    Refuses the whole call when the household has more than one open year
    (:data:`ROLLOVER_TWO_OPEN_YEARS` - there is no one year to roll) and
    when a plan names a return that is not one of that year's active ones
    (:data:`ROLLOVER_NOT_THIS_HOUSEHOLD`). **No permission is changed and
    nothing under the client tree is touched but the new year's folder**,
    which the first scaffold makes and the rest find; the inbox's README
    is rewritten once at the end, so the client sees the new year's lists
    in the same folder they have always used.
    """
    from tracker.filer import refresh_household_readme
    from tracker.locking import engagement_lock
    from tracker.scaffold import scaffold_household

    household_dir = Path(household_dir)
    today = today or dt.date.today()
    check_tax_year(target_year)
    # A household paused (its folders and its record disagree), stopped
    # (its record gone, two folders claiming it) or whose client folder is
    # gone (decision 188 and its review's M3, S4): refused before anything
    # is read further or written, with the sentence the pass says.
    from tracker.registry import held_back

    if said := held_back(household_dir):
        raise ManifestError(said)

    _, open_returns = open_year_returns(household_dir)
    by_folder = {_same_folder(one.path): one for one in open_returns}

    planned: list[tuple[object, ReturnPlan]] = []
    for plan in plans:
        prior = Path(plan.prior)
        one = by_folder.get(_same_folder(prior))
        if one is None:
            raise ManifestError(ROLLOVER_NOT_THIS_HOUSEHOLD.format(
                prior=prior.name, household=household_dir.name))
        planned.append((one, plan))
    # Folder-name order without case: the order the pass takes the locks
    # in and the order a person reads the household's returns in, so "the
    # first return by order" means one thing wherever it is said.
    planned.sort(key=lambda pair: pair[0].path.name.lower())

    try:
        household_info = load_household_info(household_dir)
    except ManifestError:                 # a household whose record cannot be read
        household_info = HouseholdInfo()

    # 1. Every refusal, before anything is written.
    rolls: list[_PlannedRoll] = []
    targets: set[str] = set()
    for one, plan in planned:
        try:
            roll = _plan_one(one.path, one.info, plan, household_dir.name, household_info,
                             target_year=target_year)
            # Two ticked returns into one name - by the layout's one key
            # (decision 188), so a case or a look-alike letter is the same.
            if name_key(roll.target.name) in targets:
                raise ManifestError(
                    f"another ticked return is also rolled into '{roll.target.name}'")
        # A name the layout refuses (decision 188) is the plan's refusal too,
        # in the same voice (the port review's note).
        except (ManifestError, OSError, LayoutError) as exc:
            errors.keep("rollover", exc, name=one.path.name)
            raise ManifestError(_nothing_rolled(
                one.path.name, errors.said(exc, (ManifestError, LayoutError)))) from exc
        targets.add(name_key(roll.target.name))
        rolls.append(roll)
    # What nobody ticked is finished with: one details edit on its own
    # record, carrying the one field that moved. A return that *was* ticked
    # is never retired here - rolled, its successor's Rolled From retires it.
    ticked = {_same_folder(one.path) for one, _ in planned}
    retiring: list[Path] = []
    for one in open_returns:
        if _same_folder(one.path) in ticked:
            continue
        try:
            # The up-front refusal only: what is saved is read again under
            # the lock (step 4), so an edit made meanwhile is never undone.
            # Judged as held (decision 201): a same-name pair the list
            # already holds is the retirement's to carry, not to refuse.
            stored = _rows_as_stored(one.path)
            validated(stored, recorded=stored)
        except (ManifestError, OSError) as exc:
            errors.keep("rollover", exc, name=one.path.name)
            raise ManifestError(_nothing_rolled(one.path.name, errors.said(exc, (ManifestError,)))) from exc
        retiring.append(one.path)

    result = HouseholdRollover(target_year=target_year)
    with ExitStack() as locks:
        # 2. Every lock before any write: the household's, then its returns'.
        for folder in [household_dir, *sorted((one.path for one in open_returns),
                                              key=lambda path: path.name.lower())]:
            locks.enter_context(engagement_lock(folder))

        # 3. Every new return, or none.
        made: list[tuple[Path, list[Path]]] = []
        for roll in rolls:
            try:
                made.append((roll.target, _make_one(roll)))
            except Exception as exc:
                for target, folders in reversed(made):
                    _unmake(target, folders)
                if isinstance(exc, (ManifestError, OSError)):
                    errors.keep("rollover", exc, name=roll.prior.name)
                    raise ManifestError(_nothing_rolled(
                        roll.prior.name, errors.said(exc, (ManifestError,)))) from exc
                raise
            result.rolled.append((roll.prior, roll.target, roll.report))

        # 4. Only now, retire - under the locks already held (decision 102).
        # The rows and the details saved are read here, under the lock
        # (the review's S1): read at the plan, a person's edit saved between
        # the plan and the locks would be diffed away by the retirement.
        not_retired: RolledNotAllRetired | None = None
        for folder in retiring:
            try:
                info = load_engagement_info(folder)
                save_rules(folder, _rows_as_stored(folder), replace(info, active=False),
                           lock_held=True)
            except Exception as exc:
                errors.keep("rollover", exc, name=folder.name)
                not_retired = RolledNotAllRetired(
                    result, [one for one in retiring if one not in result.retired],
                    errors.said(exc, (ManifestError,)))
                break
            result.retired.append(folder)

    # The client's side, once, at the end: the year folders the rolls made
    # are already there, and the README - its one composer, decision 130 -
    # now lists the new year's returns. Whenever a return was rolled, even
    # when a retirement failed (the review's S3): the new year's returns
    # exist and the client's README should list them. A failure here does
    # not hide the retirement's; it is added to it.
    if not_retired is None:
        scaffold_household(household_dir)
        refresh_household_readme(household_dir)
        return result
    for step in (scaffold_household, refresh_household_readme):
        try:
            step(household_dir)
        except Exception as exc:
            errors.keep("rollover", exc, name=household_dir.name)
            not_retired.also.append(f"{step.__name__} failed ({errors.said(exc, (ManifestError,))})")
    raise not_retired


class RolledNotAllRetired(ManifestError):
    """Every ticked return was rolled, and then a retirement failed (decision
    159, the review's S2).

    Not "nothing was rolled": the new year's returns exist, and a
    retirement is a record line that is not undone. So it is its own
    error, carrying what was done - ``result`` (rolled, and retired so
    far) and ``not_retired`` - for the command line's heading and the
    app's banner, and its sentence (:data:`ROLLOVER_NOT_RETIRED`) says the
    same in words. ``also`` holds any failure of the scaffold or README
    refresh that ran after it.
    """

    def __init__(self, result: HouseholdRollover, not_retired: list[Path], why: object):
        self.result = result
        self.not_retired = not_retired
        self.why = str(why)
        self.also: list[str] = []
        super().__init__(self.sentence())

    def sentence(self) -> str:
        said = ROLLOVER_NOT_RETIRED.format(
            year=self.result.target_year,
            rolled=", ".join(was.name for was, _, _ in self.result.rolled) or "none",
            retired=", ".join(path.name for path in self.result.retired) or "none",
            left=", ".join(path.name for path in self.not_retired),
            why=self.why)
        return "; ".join([said, *self.also])

    def __str__(self) -> str:
        return self.sentence()


def _nothing_rolled(name: str, why: object) -> str:
    """One return's refusal, said as the whole household roll's."""
    return NOTHING_ROLLED.format(prior=name, why=str(why).rstrip(". "))


@dataclass(frozen=True, slots=True)
class _PlannedRoll:
    """One ticked return's roll, worked out whole before anything is written."""

    prior: Path
    target: Path
    report: RolloverReport
    info: EngagementInfo


def _plan_one(prior: Path, prior_info: EngagementInfo, plan: ReturnPlan,
              household_name: str, household_info: HouseholdInfo, *,
              target_year: int) -> _PlannedRoll:
    """Everything one return's roll decides, and every refusal it makes,
    with nothing written (decision 159): last year's rows, the target the
    layout computes, the refusals creation makes, the details carried and
    refilled from the household, and the dates the form implies."""
    from tracker.filer import refuse_a_path_past_the_limit

    report = roll_forward(prior, target_year=target_year,
                          template=template_items(plan.form) if plan.form else [])
    # **A return rolls forward where it sits** (decision 177): the
    # household being rolled and the prior's own folder name, never the
    # names its record carries. A return a person dragged into another
    # household still names the old one in its record, and the new year
    # went back there - under the other household's inbox, README and
    # client folder.
    household = household_name
    return_name = plan.return_name or prior.name
    target = return_dir_for(root_of(prior), household, target_year, return_name)
    # Unique by the layout's key within the household-year (decision 188),
    # asked here, in the plan, so a name taken refuses the whole roll before
    # any lock is taken or anything written (decision 159).
    if (taken := return_name_taken(target.parent, return_name)) is not None:
        raise ManifestError(
            f"A return named '{taken}' already exists for {household} {target_year}")
    refuse_a_path_past_the_limit(target, report.items)
    # Last year's rows carried as they were - a same-name issuer pair the
    # list already held among them - are judged as create_engagement will
    # judge them (decision 201), so the plan refuses nothing the make keeps.
    validated(report.items, recorded=report.from_last_year or None)

    carried = carry_engagement_info(prior_info, rolled_from=str(prior), tax_year=target_year)
    # The inbox is the household's and does not change from one year to
    # the next, so its link and its greeting are refilled here rather than
    # left blank for somebody to notice in February.
    link, report.link_dropped = carried_link(carried.link or household_info.link)
    carried = replace(carried,
                      client=carried.client or household_info.contact,
                      link=link,
                      household=household, return_name=return_name)
    info = with_default_dates(carried, carried.form or plan.form, target_year)
    return _PlannedRoll(prior=prior, target=target, report=report, info=info)


def _make_one(roll: _PlannedRoll) -> list[Path]:
    """Make one planned return: its folders, its record under its own new
    lock, and its scaffold. Returns the folders this call's own mkdir made,
    for :func:`roll_household` to remove again should a later return fail.
    A failure here removes this return first and raises."""
    from tracker.scaffold import scaffold_engagement

    # The return and, in a new year, its year folder - and only what this
    # call's own mkdir made is removed again (decision 137).
    made = make_new_folders(roll.target)
    try:
        roll.report.warnings = list(create_engagement(roll.target, roll.report.items, roll.info,
                                                      carried=roll.report.from_last_year))
        scaffold_engagement(roll.target)
    except Exception:
        _unmake(roll.target, made)
        raise
    return made


def _unmake(target: Path, made: list[Path]) -> None:
    """Remove a return this roll made: never a half-built return, in the
    folder or in the store. The folder first, so the name is free again
    whatever happens next, then the store's row in its own try, because a
    store that cannot be reached at this moment must not replace the
    refusal the person is owed with its own. The return is this call's; a
    year folder above it goes only when it is empty (the review's F4)."""
    from tracker import store

    for folder in reversed(made):
        if folder == target:
            shutil.rmtree(folder, ignore_errors=True)
            continue
        try:
            folder.rmdir()
        except OSError:
            pass
    try:
        store.forget(store.connect(), target)
    except Exception:
        pass


# --------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker import ledger, store
    from tracker.page import tolerant_console
    from tracker.registry import engagement_from
    from tracker.templates import require_form

    # The report names the client's folders and carries an arrow a cp1252
    # console cannot encode; the record is written before a word is
    # printed, and a re-run into that folder is refused (decision 108).
    tolerant_console()

    # **Two forms, one command line** (decision 126): a household's private
    # folder rolls the household's year, a return folder rolls that one
    # return. They are told apart by what the path holds - the record's own
    # answer (``store.kind``), not the folder's position - so a person who
    # points this at the wrong level is refused rather than surprised.
    parser = argparse.ArgumentParser(
        description="Roll a returning client forward: one household's year, or one return"
    )
    parser.add_argument("folder",
                        help="the household's folder in the private tree, or last year's return")
    parser.add_argument("--year", type=int, default=None, help="target tax year")
    parser.add_argument("--form", action="append", default=[],
                        help="form template used to fill blanks (e.g. 1040); on a household, "
                             "once for every return or one per --only, in the same order")
    parser.add_argument("--all", action="store_true",
                        help="household: roll every return of the open year")
    parser.add_argument("--only", action="append", default=[], metavar="RETURN",
                        help="household: roll this return by name (repeat for several); "
                             "every return left out is retired")
    parser.add_argument("--scaffold", action="store_true",
                        help="one return: also build the folders (a household always does)")
    ns = parser.parse_args()
    forms: list[str] = list(ns.form)
    for named in forms:
        try:
            require_form(named)
        except ManifestError as exc:
            parser.error(str(exc))

    # A typed folder is parsed, never trusted (decision 188): a household's
    # or a return's place under the checked clients root, rebuilt from its
    # own names - a folder in the client tree is neither, whatever journal
    # somebody put in it.
    from tracker import door
    from tracker.layout import LayoutError
    try:
        try:
            given = door.household_dir(Path(ns.folder).absolute())
        except ValueError:
            given = door.return_dir(Path(ns.folder).absolute())
    except (door.DoorError, LayoutError) as exc:     # the door's own sentences
        parser.error(str(exc))
    if not ledger.path_for(given).is_file():
        parser.error(f"no record in {given}")
    store.follow_the_journal(store.connect(), store.root_for(given), given)
    # Paused, stopped or its client folder gone (decision 188): refused
    # before anything is written, in both forms of the command.
    from tracker.registry import held_back

    if said := held_back(given if store.kind(store.connect(), given) == store.KIND_HOUSEHOLD
                         else household_of(given)):
        parser.error(said)

    if store.kind(store.connect(), given) == store.KIND_HOUSEHOLD:
        if ns.year is None:
            parser.error("give the year to roll this household into (--year)")
        if bool(ns.all) == bool(ns.only):
            parser.error("say which returns to roll: --all, or --only \"<return name>\" for each")
        try:
            open_years_now, open_now = open_year_returns(given)
        except ManifestError as exc:
            parser.error(str(exc))
        chosen = list(open_now)
        if ns.only:
            # By the layout's one key (decision 188): a name typed with
            # another case or a look-alike letter is the same return.
            by_name = {name_key(one.path.name): one for one in open_now}
            chosen = []
            for name in ns.only:
                one = by_name.get(name_key(normalised_name(name)))
                if one is None:
                    parser.error(ROLLOVER_NOT_THIS_HOUSEHOLD.format(prior=name,
                                                                    household=given.name))
                chosen.append(one)
        if len(forms) > 1 and len(forms) != len(chosen):
            parser.error("give --form once for every return, or one per --only in the same order")
        day = dt.date.today()
        from tracker.locking import EngagementLockedError

        try:
            done = roll_household(given, target_year=ns.year, today=day, plans=[
                ReturnPlan(prior=one.path,
                           form=forms[n] if len(forms) > 1 else (forms[0] if forms else ""))
                for n, one in enumerate(chosen)
            ])
        except RolledNotAllRetired as exc:
            # Rolled, and a retirement failed: not "nothing was rolled".
            print(f"{given.name} was rolled forward, but not every return left out was "
                  f"retired\n\n  {NOT_ALL_RETIRED_HEADING}\n    {exc}\n")
            raise SystemExit(1) from None
        except (ManifestError, EngagementLockedError) as exc:
            # Every ticked return or none (decision 159): the refusal is
            # the whole roll's, said under the heading a person looks for.
            print(f"{given.name} was not rolled forward\n\n  {NOT_ROLLED_HEADING}\n    {exc}\n")
            raise SystemExit(1) from None

        span = (f"{open_years_now[0]} → {ns.year}" if open_years_now
                else f"{UNKNOWN_YEAR_LABEL} ({ns.year})")
        print(f"Rolled {given.name} forward ({span})\n")
        print(f"  {ROLLED_HEADING}")
        for was, created, one_report in done.rolled:
            print(f"    {was.name} → {created}")
            print(f"      {len(one_report.carried)} carried, "
                  f"{len(one_report.added)} new (not asked), "
                  f"{len(one_report.unfiled_last_year)} never filed last year")
            if warning := engagement_from(was).warning:
                print(f"      WARNING: {warning}")
        if done.skipped:
            print(f"\n  {NOT_ROLLED_HEADING}")
            for was, why in done.skipped:
                print(f"    {was.name}: {why}")
        if done.retired:
            print(f"\n  {RETIRED_HEADING.format(year=ns.year)}")
            for one in done.retired:
                print(f"    {one.name}")
                print(f"      {RETIRED_BY_ROLLOVER.format(day=day.isoformat(), year=ns.year)}")
        print()
        raise SystemExit(0)

    template = template_items(forms[0]) if forms else []
    ns.form = forms[0] if forms else ""

    result = roll_forward(
        given,
        target_year=ns.year,
        template=template,
    )

    from tracker.layout import household_name_of

    # Next year's list, in the record, where the editor shows it: the rows
    # this rollover built and last year's details carried by the one rule.
    # Resolved before any of the layout's arithmetic: the command line may
    # be given a relative folder, and where a return sits is read off its
    # own path (the root is four levels up).
    prior_dir = result.prior_dir.resolve()
    prior_info = load_engagement_info(prior_dir)
    carried = carry_engagement_info(
        prior_info,
        rolled_from=str(prior_dir),                    # the runner's cwd is not this one
        tax_year=result.target_year,
    )
    # **The target is computed, never typed** (decision 125). A return
    # keeps its name every year, under the same household, so the folder
    # the new year goes in is the layout's answer and not a person's: the
    # household's folder, the target year, the prior's own return name.
    if result.target_year is None:
        parser.error("the prior year could not be read off the list; give --year")
    # Where the prior sits, never what its record names (decision 177).
    carried = replace(carried, household=household_name_of(prior_dir),
                      return_name=prior_dir.name)
    target = return_dir_for(root_of(prior_dir), carried.household, result.target_year,
                            carried.return_name)
    if target.exists():
        parser.error(f"{target} already exists")
    target.mkdir(parents=True, exist_ok=True)
    # Last year's dates did not carry, and the new year's are the form's:
    # the catalog the prior recorded, or the one asked for here. The
    # command line defaults them exactly as the app's rollover does, so an
    # engagement is on the reminder's ladder however it was made
    # (decision 123).
    result.warnings = list(create_engagement(
        target, result.items,
        with_default_dates(carried, carried.form or ns.form, result.target_year),
        carried=result.from_last_year))

    # All of the work before any of the report: the folders are made now,
    # so nothing about printing can leave a folder with a record and no
    # scaffold - create_engagement() refuses a folder that already holds a
    # record, so that folder could not be tried again (decision 108).
    scaffolded = None
    if ns.scaffold:
        from tracker.filer import refresh_household_readme
        from tracker.scaffold import scaffold_engagement as scaffold_one

        scaffolded = scaffold_one(target)
        # Folders only since decision 130; the README is its one composer's.
        refresh_household_readme(household_of(target))

    span = f"{result.prior_year} → {result.target_year}" if result.prior_year else UNKNOWN_YEAR_LABEL
    print(f"Rolled {result.prior_dir.name} forward ({span})\n")
    if warning := engagement_from(prior_dir).warning:
        print(f"  WARNING: {warning}\n")      # decision 177: it rolled where it sits
    for warning in result.warnings:           # decision 201: a same-name pair carried
        print(f"  WARNING: {warning}\n")
    for rolled in result.carried:
        print(f"  CARRIED {rolled.item.label}")
        print(f"          {rolled.note}")
    for rolled in result.added:
        print(f"  NEW     {rolled.item.label}")
        print(f"          {rolled.note}")
    if result.not_applicable:
        # Last year's set-aside rows, after the active list and under their
        # own heading: shown for a fresh decision, never back in the list.
        print(f"\n  {PREVIOUS_NOT_APPLICABLE_HEADING}")
        for rolled in result.not_applicable:
            print(f"    ~ {override_label(rolled.item)}  {rolled.item.label}")
            print(f"          {rolled.note}")
    if result.unfiled_last_year:
        print(f"\n  {UNFILED_HEADING}")
        for line in result.unfiled_last_year:
            print(f"    ? {line}")
    print(f"\n  Engagement: {target}")

    if scaffolded is not None:
        for line in scaffolded.describe():
            print(f"  {line}")
