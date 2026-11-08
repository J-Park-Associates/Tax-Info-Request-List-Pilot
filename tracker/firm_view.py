"""The firm view: the Overview's rows, their cache, and the group rule the
return's own page shares - the one builder of what every firm list shows.

Each part upholds the decision rows it names:

- **The group rule** (SPEC-shell 9.1). :func:`item_group` puts a request
  row in one of the four groups (:data:`GROUPS`), and :func:`file_group`
  a file in the index, by the first line of the table that holds. The
  return's page (the API's ``state``) sends each row's group from these
  two and the Overview counts with the same two, so a count on the
  Overview and the group on the return's page cannot disagree.
- **The review buckets and the copy keys** (decisions 184 and 190; rulings
  15 and 24). :func:`review_bucket` decides from a parked row's code and
  its name on disk (:func:`_name_on_disk`) which of the review card's three
  buckets it sits in, never from its sentence; :func:`_review_copy_key`,
  :func:`_shown_copy_key` and :func:`_moved_copy_key` name, under
  ``paths``, the working copy a row's Open or reveal points at. The
  return's page and a firm row build them with the same functions, so one
  file has one key and one kind everywhere.
- **The household links** (pilot P141, P172). :func:`_links_from` gives
  every household its linked households on both ends, from the records the
  walk already read; ``list`` and the firm view both ask it.
- **One return's row** (SPEC-shell 9.2; decision 189). :func:`_firm_row`
  is a return's counts by group, the files waiting for a person, its due
  date and its draft's state (:func:`_firm_draft`). A record that cannot be
  read is its own row, said in :data:`FIRM_UNREADABLE`, and never fails
  the reply.
- **The cache** (P120, P212, P222). :func:`_firm_cached` answers every
  household whose fingerprint is the one kept (:mod:`tracker.firm_cache`)
  from the cache, reads the rest afresh in batches of
  :data:`FIRM_READ_BATCH`, saying how far (:func:`_say_count`), and works
  the practice-wide facts out again on every reply (:func:`_firm_marks`).
  When it is unsure it answers ``None`` and the API reads the whole walk;
  anything unexpected costs speed, never the reply.
- **The last counts** (P229). :func:`_firm_last` answers from the kept
  households alone, with no fingerprint taken and no record read, or
  answers nothing and says why by a name in :data:`FIRM_LAST_REFUSALS`.

**One builder, and a cache that never makes a status wrong** (decision
120). A firm row is built here and nowhere else: the whole walk
(``tracker.api._firm_fresh``) and the cached path both call
:func:`_firm_row`, and ``tests/test_api.py`` holds the cached reply to the
whole walk's, field for field. Every read of a return is its reader's
``follow=False`` form, as the practice page reads: nothing is written in
either client tree, no lock is taken and no document is read - the counts
come from the record, the index and one listing of the inbox.

**Why it is its own module** (SPEC-architecture-p5 P5.7, P344; the
architecture audit's C-2). The builder sat in ``tracker.api`` at layer 5,
where nothing below the door could reach it. The door keeps what is the
door's: ``tracker.api._cmd_firm`` and ``tracker.api._cmd_firm_last`` shape
the reply (``_firm_reply``, ``_firm_key``) and page it
(:mod:`tracker.firm_pages`), and ``tracker.api._firm_fresh`` stayed there,
because it refuses a root that cannot be walked through ``_not_walked``,
which writes the command's warnings - per-command state that is the API's
(the audit's C-3). The API imports back by name what its own code reads.

**The pass still fills the cache in a child of its own** (pilot P201; Q-C,
answered for now by P313 and confirmed by Jason's answer (A) on
2026-11-08). ``runner.fill_firm_cache`` runs ``python -m tracker.api
firm`` at a pass's end - exactly what Overview runs, under its own time
limit - and so reaches this builder through the API. The runner does not
import this module: this module imports the runner, so an import back
would be a cycle.

**Why it sits at layer 4.** It reads the draft-day rule
(``DRAFT_WEEKDAY``, ``last_draft_day``, ``last_drafted``) from
:mod:`tracker.runner`, in its own layer; ``why_skipped`` from
:mod:`tracker.run_log` (since P345), the reminder's stage and hold, the
review shortlist, the registry's walk and the view's file name (layer 3); ``containers`` (layer 2); the index, the
request list, the record types, the household record and ``validators``
(layer 1); and ``firm_cache``, ``layout``, ``reasons``, ``progress``,
``settings`` and ``errors`` (layer 0). It imports neither the API nor
``scheduling`` nor :mod:`tracker.screen_words`: the last two read the
product's name at import, which the scheduled pass is not given (P220), and
``tests/test_layers.py`` keeps them out of everything this module loads,
so the pass could call the builder in its own process (Q-C) and still
start.

It logs as ``tracker.api`` (``logging.getLogger("tracker.api")``), the
name its lines have always carried: the error log prints each line's
logger name, so a new one would change lines a person reads (P331's rule;
SPEC-architecture-p5 section 2.1).
"""

from __future__ import annotations

import datetime as dt
import logging
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast

from tracker import errors, firm_cache, layout, progress, reasons, reminder, review, run_log
from tracker.containers import is_container
from tracker.households import open_years
from tracker.index import FILE_MOVED, NEEDS_REVIEW, NOT_REQUESTED, marked_missing, moved_to, read_index
from tracker.layout import locate, year_of
from tracker.manifest import (
    Override,
    Status,
    effective_status,
    is_idle_unasked,
    load_engagement_info,
    load_manifest,
)
from tracker.reasons import READ_AND_PARKED_CODES
from tracker.records import EngagementInfo, IndexEntry, ledger_key
from tracker.registry import (
    Engagement,
    Household,
    Registry,
    household_positions,
    households_named,
    mark_superseded,
)
from tracker.runner import DRAFT_WEEKDAY, last_draft_day, last_drafted
from tracker.settings import SettingsError
from tracker.validators import is_program
from tracker.view import VIEW_FILENAME

log = logging.getLogger("tracker.api")


#: The review card's three buckets (decision 190), decided here from the
#: row's code and its name on disk - never by the renderer: a document, an
#: email or a zip, and a file that is not a document at all. The keys
#: travel on each parked row as ``bucket``; the headings are the words the
#: card groups them under.
BUCKET_DOCUMENT = "document"
BUCKET_CONTAINER = "container"
BUCKET_NOT_A_DOCUMENT = "not_a_document"


#: The codes a parked email or zip is refused with (decision 143).
_CONTAINER_CODES = frozenset(reason.code for reason in (
    reasons.CONTAINER_LOCKED, reasons.CONTAINER_DAMAGED, reasons.CONTAINER_EMPTY,
    reasons.CONTAINER_LIMIT))


def _name_on_disk(entry: IndexEntry) -> str:
    """The name the row's original has on disk - raw, as the client named
    it - or, for a program never written out of its email or zip, the name
    it was recorded by."""
    return PurePosixPath(entry.pbc_location).name if entry.pbc_location else entry.original_name


def review_bucket(entry: IndexEntry) -> str:
    """Which of the review card's buckets a parked row sits in (decision
    190): read from its code, and from its type on disk, never from its
    sentence. A program recorded before the code existed is still not a
    document, because the card must never offer to open one."""
    name = _name_on_disk(entry)
    # Either name saying program is enough (decision 190's review, M1): the
    # raw one on disk, and the recorded one the review copy was named by.
    if (entry.code == reasons.NOT_A_DOCUMENT.code or is_program(name)
            or is_program(entry.original_name)):
        return BUCKET_NOT_A_DOCUMENT
    if entry.code in _CONTAINER_CODES or is_container(name):
        return BUCKET_CONTAINER
    return BUCKET_DOCUMENT


def _review_copy_key(entry: IndexEntry) -> str:
    """The key under ``paths`` of a parked row's review copy, or ``""``
    where the card offers no Open. The shell opens only a path the API has
    named (``paths``), so the copy is named there and the row carries only
    its key, and the renderer offers Open exactly where there is one.

    Open follows 184 (decision 190): only a document the tracker read and
    parked for a filing reason opens its marked copy on this machine. A
    not-a-document row never does; an email or a zip never does - it is
    opened, if at all, on a machine with no Drive sign-in and no client
    folder; nor does any row whose code is not on the allow-list
    (:data:`READ_AND_PARKED_CODES`) - a refused reading, a file the tracker
    did not read, a code nobody has placed yet; nor a row with no copy."""
    if entry.decision != NEEDS_REVIEW or not entry.prepared_location:
        return ""
    if review_bucket(entry) != BUCKET_DOCUMENT or entry.code not in READ_AND_PARKED_CODES:
        return ""
    return f"review_copy {ledger_key(entry)}"


def _moved_copy_key(entry: IndexEntry) -> str:
    """The key of where a moved-by-hand copy is now, or ``""`` for a row
    whose bytes are nowhere under the firm's folder."""
    return f"moved_copy {ledger_key(entry)}" if moved_to(entry) else ""


def _shown_copy_key(entry: IndexEntry) -> str:
    """The key of a parked or set-aside row's working copy for *showing* it
    in File Explorer, or ``""`` where the row has no copy. Reveal only,
    never Open (review 1, F2): it is what makes every file name a link,
    including the ones :func:`_review_copy_key` must not open (a set-aside
    file). A program has no working copy, so no key. An email or a zip gets
    no key either: its name is plain text (Jason, ruling 24), because one
    more click on a revealed container would open it on the machine signed
    in to Drive, which decision 190 never allows.

    A row whose copy opens (:func:`_review_copy_key`) is shown under that
    same key: the shell's allow-list is keyed by path, so a path reported
    under two kinds would have the reveal-only one overwrite the ``file``
    one and refuse the card's Open (review 2, F1). ``open(path, "reveal")``
    already shows a ``file``."""
    if entry.decision not in (NEEDS_REVIEW, NOT_REQUESTED) or not entry.prepared_location:
        return ""
    if review_bucket(entry) == BUCKET_CONTAINER:
        return ""
    return _review_copy_key(entry) or f"shown_copy {ledger_key(entry)}"


#: The four groups a return's rows and files fall into, in the order the
#: return's page draws them (SPEC-shell 9.1). One grouping rule, in Python:
#: the Overview's counts and the return's page read the same one.
GROUP_NEEDS_YOU = "needs_you"
GROUP_WAITING = "waiting"
GROUP_RECEIVED = "received"
GROUP_SET_ASIDE = "set_aside"
GROUPS = (GROUP_NEEDS_YOU, GROUP_WAITING, GROUP_RECEIVED, GROUP_SET_ASIDE)


def item_group(item, placed: dict) -> str:
    """The group a request row falls in, by the first line that holds
    (SPEC-shell 9.1): set aside by a person or never asked and nothing in;
    then whose move it is - the client's is Waiting, ours or a decision is
    Needs you; then Received (or Accepted); then any other row, asked with
    nothing usable in, is Waiting. ``placed`` is :func:`reminder.sides` of
    the one triage the screen was drawn from, so a row's group and its side
    cannot disagree."""
    if item.manual_override == Override.NOT_APPLICABLE or is_idle_unasked(item):
        return GROUP_SET_ASIDE
    side = placed.get(item.identifier)
    if side is not None:
        return GROUP_WAITING if side[0].key == reminder.SIDE_CLIENT.key else GROUP_NEEDS_YOU
    if effective_status(item) == Status.RECEIVED:
        return GROUP_RECEIVED
    return GROUP_WAITING


def file_group(entry: IndexEntry) -> str:
    """The group a file in the index falls in: parked for a person, or moved
    by hand and not yet answered, is Needs you; set aside by a person (Not
    requested) or marked missing is Set aside; every other file is filed,
    so Received."""
    if entry.decision == NEEDS_REVIEW or (entry.decision == FILE_MOVED and not marked_missing(entry)):
        return GROUP_NEEDS_YOU
    if entry.decision == NOT_REQUESTED or entry.decision == FILE_MOVED:
        return GROUP_SET_ASIDE
    return GROUP_RECEIVED


def _year(one: Engagement) -> int | None:
    """The return's tax year: the record's, or the one its folder is named for."""
    return one.tax_year if one.tax_year is not None else year_of(one.path)


#: The kinds of link between two households (pilot P141, P172), as the
#: ``links`` field says them: this household's drop folder also feeds that
#: one, that one's feeds this one, or a person marked them related.
LINK_FEEDS = "feeds"
LINK_FED_BY = "fed_by"
LINK_RELATED = "related"


def _household_links(registry: Registry) -> dict[Path, list[dict]]:
    """:func:`_links_from` over the households the practice walk read."""
    return _links_from([(one.path, one.name, [feed.household for feed in one.info.feeds], list(one.info.related))
                        for one in registry.households])


def _links_from(households: list[tuple[Path, str, list[str], list[str]]]) -> dict[Path, list[dict]]:
    """Every household's linked households, by the household's folder
    (pilot P141, P172): each ``{"name", "path", "kind"}``, from the records
    the walk already read - no extra disk read, nothing inferred.

    Both kinds are shown on **both** ends. A feed (decision 132) is
    ``feeds`` on the feeding household and ``fed_by`` on the fed one; a
    related mark (P170) is ``related`` on both, whichever record names it,
    so a save that stopped between its two writes still shows. A name no
    household folder answers keeps its words with ``path`` ``""``: the
    panel shows it as text and never guesses where it went.
    """
    @dataclass(frozen=True)
    class _One:
        path: Path
        name: str
        feeds: list[str]
        related: list[str]

    every = [_One(path, name, feeds, related) for path, name, feeds, related in households]
    by_key = {layout.name_key(one.name): one for one in every}
    found: dict[Path, dict[tuple[str, str], dict]] = {one.path: {} for one in every}

    def add(household, name: str, kind: str) -> None:
        other = by_key.get(layout.name_key(name))
        if other is not None and other.path == household.path:
            return
        entry = {"name": other.name if other else name, "path": str(other.path) if other else "", "kind": kind}
        found[household.path].setdefault((layout.name_key(entry["name"]), kind), entry)

    for household in every:
        for fed in household.feeds:
            add(household, fed, LINK_FEEDS)
            other = by_key.get(layout.name_key(fed))
            if other is not None:
                add(other, household.name, LINK_FED_BY)
        for name in household.related:
            add(household, name, LINK_RELATED)
            other = by_key.get(layout.name_key(name))
            if other is not None:
                add(other, household.name, LINK_RELATED)
    return {path: sorted(entries.values(), key=lambda one: (layout.name_key(one["name"]), one["kind"]))
            for path, entries in found.items()}


def _firm_draft(engagement: Path, due: dt.date | None, held_rows: int, today: dt.date) -> dict:
    """The reminder facts one return's row on the Reminders page needs, read
    the way :func:`tracker.api._return_reminder` reads them and never composing the
    letter: the stage the day gives, what holds it (the requests that hold
    it plus the files still in the inbox, a directory listing and no
    document read) and the day it was last drafted. ``ready`` is a draft
    written this draft-week that is not yet approved; a hold does not
    unmake it - the page shows Held beside it (SPEC-shell 6.3)."""
    drafted = last_drafted(engagement)
    week = last_draft_day(today, DRAFT_WEEKDAY)
    this_week = drafted is not None and drafted >= week
    approval = reminder.approval_state(engagement, engagement / reminder.DRAFT_FILENAME, since=week)
    held = held_rows + reminder.unsorted_in_inbox(engagement)
    return {"ready": bool(this_week and approval != reminder.APPROVED_NOTE),
            "stage": reminder.stage_for(due, today), "held": held,
            "drafted": drafted.isoformat() if drafted else None}


#: A return the firm view could not read: a short line of the shell's, the
#: detail going to the error log (SPEC-shell 9.2, 11.1).
FIRM_UNREADABLE = "Could Not Be Read"


def _firm_row(one, household: str, today: dt.date) -> tuple[dict, list[dict], dict[str, str]]:
    """One return's line of the firm view and its parked files: the counts by
    group (:func:`item_group`), the files a person must look at, the record's
    due date and the draft's state. The readers are the ones ``state`` uses,
    with ``follow=False`` as the status page reads (nothing is written, no
    lock is taken, no document is read). A record that cannot be read is its
    own row with ``problem`` set and zero counts, said in :data:`FIRM_UNREADABLE`
    with the detail in the error log (decision 189): it never fails the reply,
    and the total counts it as needing a person, never as complete.

    The third value is the return's own ``paths`` for its files (ruling 15):
    each file's ``open_key`` (``""`` where the row has no copy) names, in it,
    the working copy a click shows in File Explorer. The keys are the ones
    ``state`` builds (:func:`_shown_copy_key`, :func:`_moved_copy_key`), so one
    file has one key and one kind everywhere. They and the paths come from the
    record's ``prepared_location`` / ``moved_to`` alone: no path is stat-ed,
    no document is read."""
    row = {"path": str(one.path), "household": household, "label": one.label,
           "form": one.info.form,
           "year": _year(one),
           "counts": dict.fromkeys(GROUPS, 0), "files": 0, "oldest": None, "due": None,
           "draft": {"ready": False, "stage": 0, "held": 0, "drafted": None}, "problem": ""}
    if one.problem:
        errors.keep("api: firm", one.problem, name=one.path.name)
        row["problem"] = FIRM_UNREADABLE
        return row, [], {}
    try:
        items = load_manifest(one.path, follow=False)
        entries = read_index(one.path, follow=False)
        info = load_engagement_info(one.path)
        triaged = reminder.triage(items, entries)
        placed = reminder.sides(*triaged)
        parked = review.triage(one.path, entries, items=items)
        held = len(triaged[2])
        draft = _firm_draft(one.path, info.due, held, today)
    except Exception as exc:                 # one bad record costs its own row
        errors.keep("api: firm", exc, name=one.path.name)
        log.warning("A return could not be read for the firm view (%s)", errors.error_class(exc))
        row["problem"] = FIRM_UNREADABLE
        return row, [], {}
    for item in items:
        row["counts"][item_group(item, placed)] += 1
    # The files count in their groups too (SPEC-shell 9.1): parked and moved
    # by hand are Needs you, set aside by a person are Set aside, and a filed
    # file is already the Received row it answered. The same file_group the
    # return's ``state`` sends on each index row, so a count here is the tally
    # of that page and the two cannot disagree.
    for entry in entries:
        group = file_group(entry)
        if group != GROUP_RECEIVED:
            row["counts"][group] += 1
    by_name = {item.identifier: item for item in items}
    paths: dict[str, str] = {}

    def shown(key: str, where: str | None) -> str:
        if key:
            # A key is only ever given with the location it names.
            paths[key] = str(locate(one.path, cast(str, where)))
        return key

    files = [{"return": row["path"], "year": row["year"], "name": t.entry.original_name,
              "handle": ledger_key(t.entry), "code": t.entry.code, "received": t.entry.received,
              "suggestion": by_name[t.shortlist[0].identifier].label if t.shortlist else "",
              # The request's short name, for Needs Review's chip (pilot
              # P149); the full label above is the chip's tooltip.
              "suggestion_short": by_name[t.shortlist[0].identifier].short_name if t.shortlist else "",
              "open_key": shown(_shown_copy_key(t.entry), t.entry.prepared_location)}
             for t in parked]
    files.extend({"return": row["path"], "year": row["year"], "name": entry.original_name,
                  "handle": ledger_key(entry), "code": reasons.FILE_MOVED.code,
                  "received": entry.received, "suggestion": "", "suggestion_short": "",
                  "open_key": shown(_moved_copy_key(entry), moved_to(entry))}
                 for entry in entries
                 if file_group(entry) == GROUP_NEEDS_YOU and entry.decision == FILE_MOVED)
    waiting_days = sorted(f["received"] for f in files)
    row["files"] = len(files)
    row["oldest"] = waiting_days[0] if waiting_days else None
    row["due"] = info.due.isoformat() if info.due else None
    row["draft"] = draft
    return row, files, paths


#: One shown return of the firm view: its row (``paused`` set), its files and
#: its own ``paths``, as :func:`_firm_row` built them.
_FirmShown = tuple[dict, list[dict], dict[str, str]]

#: What a firm read answers: the shown returns and what the walk saw of names
#: for P278's pages - ``{"returns": {path: the return's name}, "households":
#: [{"name", "path", "links", "forms"}]}``, the households with their links and
#: the recorded form of every return they hold, shown or not.
_FirmRead = tuple[list[_FirmShown], dict]


def _firm_cached(root: Path, today: dt.date) -> _FirmRead | None:
    """The firm view's returns with every unchanged household answered from
    the cache (P120), or ``None`` when this path is unsure and
    :func:`tracker.api._firm_fresh` must answer. Anything unexpected here is kept on the
    error log and answered fresh: the cache may make a reply slow, never
    wrong. A surprise is said once when it starts and again when it
    changes, not on every reply while it lasts (:func:`firm_cache.first_time_said`)."""
    try:
        said: Path | None = firm_cache.cache_path().with_name(firm_cache.SAID_FILENAME)
    except (SettingsError, OSError):
        said = None             # no data folder: every surprise is said
    try:
        shown = _firm_from_cache(root, today)
    except _FirmUnsure:
        return None
    except Exception as exc:     # the cache's own surprise costs speed, never the reply
        if said is None or firm_cache.first_time_said(said, errors.error_class(exc)):
            errors.keep("api: firm cache", exc)
            log.warning("The firm view's cache was set aside (%s)", errors.error_class(exc))
        return None
    if said is not None:
        firm_cache.first_time_said(said, None)
    return shown


#: What a household's fingerprint leaves out (the review of P120, SHOULD-4):
#: the return's status page, which a pass redraws from the record and no
#: firm reader opens, at the one place the tracker writes it - a return's
#: folder, two levels down (year, return; the re-check's MUST-R1 and
#: NIT-R1). Every other file - every record, the reminder drafts, the
#: inbox's README - is judged by its size and time (P212: Jason reversed
#: P120's whole-bytes rule for speed on 2026-10-07); ``tests/test_api.py``
#: pins that the firm view never opens a file the fingerprint leaves out.
FIRM_JUDGED = firm_cache.Judged(
    private_left_out=frozenset({(firm_cache.ANY, firm_cache.ANY, VIEW_FILENAME)}))


class _FirmUnsure(Exception):
    """The cached path cannot give the walk's answer by itself."""


#: How many households the firm summary reads afresh at a time (pilot
#: P222): after each batch it says how far it is (:func:`_say_count`), so
#: a long wait shows "Reading {n} of {total} Households".
FIRM_READ_BATCH = 25


def _say_count(done: int, total: int) -> None:
    """One count line on stdout before the reply (pilot P222, the lanes'
    contract): flushed, so the shell can show it while the read goes on. A
    stdout that cannot take it - the cache fill's child has none - is
    ignored: the count is for a person watching, never part of the reply."""
    try:
        sys.stdout.write(progress.count_line(done, total))
        sys.stdout.flush()
    except (OSError, ValueError, AttributeError):
        pass


def _firm_from_cache(root: Path, today: dt.date) -> _FirmRead:
    """:func:`_firm_cached`'s work, in four steps.

    1. List the households as the walk lists them
       (:func:`tracker.registry.household_positions`) and fingerprint each
       one's two folders (:func:`tracker.firm_cache.fingerprint`) before
       anything is read, so a change made while this reply reads lands in
       the next reply's fingerprint.
    2. Read fresh every household whose fingerprint is not the one kept,
       by the practice walk's own per-household reading
       (:func:`households_named`).
    3. Work out the practice-wide facts from every household's facts, kept
       or fresh, with the registry's own rules: which prior a Roll Forward
       retired (:func:`mark_superseded`), which return is skipped
       (``run_log.why_skipped``) and which household has two open years
       (``open_years``).
    4. Build each shown return's row that is not kept (:func:`_firm_row`),
       keep every household that read without a problem, and answer.
    """
    positions = household_positions(root)
    if positions is None:
        raise _FirmUnsure
    private, folders = positions
    head = firm_cache.head(root, today)
    where = firm_cache.cache_path()
    kept = firm_cache.load(where, head)
    # A folder whose name no household may have (the walk makes it a
    # misfit) has no client folder to ask about: only its own is taken.
    prints = dict(zip(folders, firm_cache.fingerprints(
        [(folder, None if layout.segment_problem(folder.name)
          else layout.client_household_dir(private.parent, folder.name)) for folder in folders],
        FIRM_JUDGED), strict=True))
    entries: dict[Path, dict] = {}
    for folder in folders:
        entry = kept.get(folder.name)
        if entry is not None and prints[folder] is not None and entry["fingerprint"] == prints[folder]:
            entries[folder] = entry
    # Read afresh in batches (pilot P222), saying how far after each, and
    # the row of every return each batch's own facts would show built at
    # once. The practice-wide step below stays the authority: it uses a row
    # built early for a return it shows and builds any other, and a row
    # built early for a return it does not show is dropped. _firm_row is a
    # function of the household's read and the day, not of the marks, so a
    # row is the same whenever it is built.
    unread = [folder for folder in folders if folder not in entries]
    read: dict[Path, tuple[dict, dict[str, Engagement]]] = {}
    early: dict[tuple[Path, str], _FirmShown] = {}
    if unread:
        _say_count(0, len(unread))
    for start in range(0, len(unread), FIRM_READ_BATCH):
        batch = _firm_read_households(private, unread[start:start + FIRM_READ_BATCH], prints)
        read.update(batch)
        batch_facts = [(folder, one) for folder, (entry, _ones) in batch.items() for one in entry["returns"]]
        batch_marked = mark_superseded([_fact_engagement(one) for _folder, one in batch_facts])
        for (folder, one), engagement in zip(batch_facts, batch_marked, strict=True):
            if not run_log.why_skipped(engagement)[0]:
                early[(folder, one["path"])] = _firm_row(batch[folder][1][one["path"]], batch[folder][0]["name"],
                                                         today)
        _say_count(min(start + FIRM_READ_BATCH, len(unread)), len(unread))
    entries.update({folder: entry for folder, (entry, _ones) in read.items()})
    order = _firm_order(folders, entries)
    facts, marked, paused, showing = _firm_marks(root, order, entries)
    # A return now shown whose row was not kept (it was a retired prior
    # until another household changed): its household is read again.
    short = [folder for folder in dict.fromkeys(folder for (folder, one), show in zip(facts, showing, strict=True)
                                                  if show and one["shown"] is None)
             if folder not in read]
    if short:
        again = _firm_read_households(private, short, prints)
        for folder, (entry, ones) in again.items():
            if (entry["kind"], entry["name"], entry["returns"]) != (
                    entries[folder]["kind"], entries[folder]["name"],
                    [{**one, "shown": None} for one in entries[folder]["returns"]]):
                raise _FirmUnsure       # it changed under this reply: read it all fresh
            # A copy of the kept entry takes the new rows, so what was loaded
            # stays as loaded and the save below sees the change.
            entries[folder] = {**entries[folder], "returns": [dict(one) for one in entries[folder]["returns"]]}
            read[folder] = (entries[folder], ones)
        facts = [(folder, one) for folder in order for one in entries[folder]["returns"]]
    links = _firm_links(order, entries)
    shown: list[_FirmShown] = []
    for (folder, one), engagement, show in zip(facts, marked, showing, strict=True):
        if not show:
            continue
        if folder in read:
            row, files, own = early.get((folder, one["path"])) or _firm_row(
                read[folder][1][one["path"]], entries[folder]["name"], today)
            one["shown"] = {"row": row, "files": files, "paths": own}
        else:
            row, files, own = one["shown"]["row"], one["shown"]["files"], one["shown"]["paths"]
        shown.append(_firm_marked(row, files, own, engagement, paused, links))
    keep = {folder.name: entry for folder, entry in entries.items() if _firm_keepable(entry)}
    # Written only when what is kept changed - or when nothing was kept and
    # the file does not already carry this head, so a practice with nothing
    # to keep yet (every household just changed, or none at all) still
    # leaves today's head, and the pass's fill can tell that from a cache
    # that was never written (P201, SPEC-firm-cache-fill R5a) - once per
    # head, not on every reply while nothing is kept (the review's NIT-1).
    if keep != kept or (not kept and not firm_cache.holds(where, [head])):
        firm_cache.save(where, head, keep)
    return shown, _firm_seen(order, entries, links, facts, showing)


def _firm_seen(order: list[Path], entries: dict[Path, dict], links: dict,
               facts: list[tuple[Path, dict]], showing: list[bool]) -> dict:
    """What the walk saw of names, from the kept facts (:data:`_FirmRead`): each
    shown return's name, and each household with its links and the recorded
    form of every return it holds, shown or not (a Client Type keeps the
    households with a return of one of its forms, P153)."""
    return {"returns": {one["path"]: one["return_name"] for (_folder, one), show in zip(facts, showing, strict=True) if show},
            "households": [{"name": entries[folder]["name"], "path": str(folder), "links": links.get(folder, []),
                            "forms": [one["form"] for one in entries[folder]["returns"]]}
                           for folder in order if entries[folder]["kind"] == "household"]}


def _firm_order(folders: list[Path], entries: dict[Path, dict]) -> list[Path]:
    """The walk's order of the households ``entries`` holds: every
    household with its record, then the returns of households whose record
    is gone (``registry._kept``)."""
    return [folder for folder in folders if entries[folder]["kind"] == "household"] + \
           [folder for folder in folders if entries[folder]["kind"] == "record_missing"]


def _fact_engagement(one: dict) -> Engagement:
    """A kept return's facts as the :class:`Engagement` the registry's rules
    (:func:`mark_superseded`, ``run_log.why_skipped``) judge."""
    return Engagement(path=Path(one["path"]), household_path=Path(one["household"]),
                      problem=one["problem"],
                      info=EngagementInfo(active=one["active"], tax_year=one["tax_year"],
                                          rolled_from=one["rolled_from"]))


def _firm_marks(root: Path, order: list[Path], entries: dict[Path, dict]) \
        -> tuple[list[tuple[Path, dict]], list[Engagement], set[Path], list[bool]]:
    """Step 3 of :func:`_firm_from_cache`, and all of :func:`tracker.api._cmd_firm_last`'s
    deciding: the practice-wide facts worked out from every household's
    facts, kept or fresh, with the registry's own rules - which prior a Roll
    Forward retired (:func:`mark_superseded`), which household has two open
    years (``open_years``) and which return is shown (``run_log.why_skipped``).
    Returns each return's facts in the walk's order, the returns marked,
    the paused households and whether each return is shown."""
    facts = [(folder, one) for folder in order for one in entries[folder]["returns"]]
    marked = mark_superseded([_fact_engagement(one) for _folder, one in facts])
    households = [Household(path=folder) for folder in order if entries[folder]["kind"] == "household"]
    paused = {path for path, theirs in
              Registry(source=root, engagements=marked, households=households).by_household().items()
              if len(open_years(theirs)) > 1}
    showing = [not run_log.why_skipped(one)[0] for one in marked]
    return facts, marked, paused, showing


def _firm_links(order: list[Path], entries: dict[Path, dict]) -> dict:
    """Practice-wide, every reply (pilot P141, P172): a household's links
    depend on other households' records too, so they are never kept."""
    return _links_from([(folder, entries[folder]["name"], entries[folder]["feeds"], entries[folder]["related"])
                        for folder in order if entries[folder]["kind"] == "household"])


def _firm_marked(row: dict, files: list[dict], own: dict[str, str], engagement: Engagement,
                 paused: set[Path], links: dict) -> _FirmShown:
    """One shown return with this reply's practice-wide marks laid over its
    row: whether its household is paused, and its household's links."""
    return ({**row, "paused": engagement.household_path in paused,
             "links": links.get(engagement.household_path, [])}, files, own)


def _firm_keepable(entry: dict) -> bool:
    """Whether a household's entry may be kept: fingerprinted, and none of
    its returns has a problem, read or shown - such a household is read
    fresh every time, so its detail reaches the error log every time."""
    return bool(entry["fingerprint"]) and not any(
        one["problem"] or (one["shown"] is not None and one["shown"]["row"]["problem"])
        for one in entry["returns"])


def _firm_read_households(private: Path, folders: list[Path],
                          prints: dict[Path, str | None]) -> dict[Path, tuple[dict, dict[str, Engagement]]]:
    """Each of ``folders`` read as the practice walk reads it
    (:func:`households_named`, decision 192's one per-household reading):
    its cache entry - the fingerprint taken before the read, its kind, its
    name and each return's facts, no row yet - and its returns by path. A
    household whose record has a problem is given no fingerprint, so it is
    never kept and is read fresh on every reply."""
    if not folders:
        return {}
    found = households_named(private, [folder.name for folder in folders])
    wanted = set(folders)
    kept = {household.path: household for household in found.households if household.path in wanted}
    read: dict[Path, tuple[dict, dict[str, Engagement]]] = {}
    for folder in folders:
        ones = [one for one in found.engagements if one.household_path == folder]
        household = kept.get(folder)
        kind = "household" if household is not None else ("record_missing" if ones else "none")
        troubled = household is not None and bool(household.problem)
        entry = {"fingerprint": "" if troubled else (prints[folder] or ""), "kind": kind,
                 "name": household.name if household is not None else "",
                 "feeds": [feed.household for feed in household.info.feeds] if household is not None else [],
                 "related": list(household.info.related) if household is not None else [],
                 "returns": [{"path": str(one.path), "household": str(one.household_path),
                              "problem": one.problem, "active": one.info.active,
                              "tax_year": one.info.tax_year, "rolled_from": one.info.rolled_from,
                              "return_name": one.info.return_name or one.path.name, "form": one.info.form,
                              "shown": None} for one in ones]}
        read[folder] = (entry, {str(one.path): one for one in ones})
    return read


#: Why :func:`_firm_last` answered nothing, by name, and how loudly: the
#: ordinary ones stay below the error log (``logging.INFO``), the unusual
#: ones reach it (``logging.WARNING``, the error log's floor). ``refuse``
#: looks the name up here, so a refusal never named here cannot be said.
FIRM_LAST_REFUSALS = {
    "no_positions": logging.INFO,        # the fresh reply says why, in its own words
    "no_kept_practice": logging.INFO,    # no cache under today's head, or no household
    "cache_rewritten": logging.INFO,     # a firm write landed while it was read
    "households_differ": logging.WARNING,
    "household_problem": logging.WARNING,
    "row_not_kept": logging.WARNING,
}


def _firm_last(root: Path, today: dt.date) -> tuple[list[_FirmShown], dt.datetime, dict] | None:
    """:func:`tracker.api._cmd_firm_last`'s work: the shown returns from the kept
    households alone, the cache file's last write and what the kept facts
    say of names (:data:`_FirmRead`), or ``None`` - with
    the refusal's name on the log - when any household is not kept.

    The file's time is taken **before** it is loaded and asked again after
    the marks: a ``firm`` reply that saved it in between would otherwise
    label the rows read with its newer time, so a moved time refuses."""
    def refuse(why: str) -> None:
        log.log(FIRM_LAST_REFUSALS[why], "The last counts were not shown (%s)", why)

    positions = household_positions(root)
    if positions is None:
        refuse("no_positions")
        return None
    _private, folders = positions
    where = firm_cache.cache_path()
    try:
        before = where.stat().st_mtime_ns
    except OSError:
        refuse("no_kept_practice")
        return None
    kept = firm_cache.load(where, firm_cache.head(root, today))
    if not kept or not folders:
        refuse("no_kept_practice")
        return None
    if set(kept) != {folder.name for folder in folders} or len(folders) != len(kept):
        refuse("households_differ")
        return None
    entries = {folder: kept[folder.name] for folder in folders}
    if not all(_firm_keepable(entry) for entry in entries.values()):
        refuse("household_problem")
        return None
    order = _firm_order(folders, entries)
    facts, marked, paused, showing = _firm_marks(root, order, entries)
    links = _firm_links(order, entries)
    shown: list[_FirmShown] = []
    for (_folder, one), engagement, show in zip(facts, marked, showing, strict=True):
        if not show:
            continue
        if one["shown"] is None:
            refuse("row_not_kept")
            return None
        shown.append(_firm_marked(one["shown"]["row"], one["shown"]["files"], one["shown"]["paths"],
                                  engagement, paused, links))
    try:
        after = where.stat().st_mtime_ns
    except OSError:
        after = None
    if after != before:
        refuse("cache_rewritten")
        return None
    return shown, dt.datetime.fromtimestamp(before / 1e9), _firm_seen(order, entries, links, facts, showing)
