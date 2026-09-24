"""The unattended run across every engagement in the registry (component 10).

One command does a full pass — file the drop folder, scan, and on the draft day
draft the week's chase email — for every engagement found under the firm's
clients folder:

    python -m tracker.runner <clients root>

That is the whole pass. The scheduled task names no root at all (decision
131): it runs ``python -m tracker.runner --settings <the app's settings
folder> --log`` and reads the clients root from the settings file at every
run, so the root has one home and changing it in the app is enough. There
is nothing to register: a folder
holding the engagement's own record is an engagement, and the details in
that record say who the client is and how they are chased. Creating an
engagement in the desktop app is all it takes for the nightly run to pick
it up.

**Drafting is weekly, on ``DRAFT_WEEKDAY``.** A reminder that lands in the accountant's
lap every night is noise that gets ignored; one a week, waiting over the weekend
for a start-of-week send, is a thing someone actually reads. The filing and scanning
steps still run on whatever schedule the task is set to — only the drafting
step looks at the day. ``--reminders always`` forces a draft on any day and
``--reminders never`` suppresses it, so the schedule is a default, not a cage.

**Nothing is ever sent.** The draft step writes ``DRAFT_FILENAME`` into
the engagement folder and stops there. A person opens it, edits it and sends
it. An engagement whose details say ``Reminders`` set to ``NO`` is left out of
the automated draft entirely — that is a standing decision about that client,
and neither the schedule nor ``--reminders always`` overrides it. Drafting one by hand for
anybody, any time, is still just:

    python -m tracker.reminder <engagement_dir> --write

**A draft you have edited is never overwritten.** The weekly run recognizes
its own unedited output by the fingerprint in the header; anything else it
leaves alone and writes ``NEW_DRAFT_FILENAME`` beside it instead.

**An ambiguous request holds the whole reminder** (decision 115). A row the
drafter cannot put to one side - something arrived and the rules refused
it, with no firm-side marker - holds that client's draft: no file is
written, the run's own unedited draft from an earlier week is retired, an
edited one is left, and the hold is said here, in the run log, on the
practice page and in the app with the rows named. ``--reminders always``
is held too; a person clears the question, never the guard. **The draft is
on the record**: what the week's draft asked, or what held it, and which
file it wrote is one ``ledger.DRAFTED`` event under the pass's lock, only
when that moved; the day of the last draft is read from it, and the first
pass after a hold clears drafts the client by the catch-up rule.

**And the reminder waits for the sort** (decision 133). While the
household's own ``Drop files here`` holds a file the sort has not taken -
two open years, a drop that failed, a transfer in flight, a name the
machine cannot handle - the draft is held the same way, whole, and the
note says how many files wait. ``tracker.reminder`` counts them, so this
module only reports the hold; the next pass that sorts the inbox drafts
that same day, because a hold is not a draft.

**Every real pass leaves the practice on one page.** ``STATUS_PAGE_FILENAME``
is written into the clients root at the end of the pass: every engagement
with what it owes, every file parked for a person across the whole
practice, and everything that failed. The desktop app shows one engagement
at a time, which is the wrong shape for the question a person actually has
in March - what needs me this morning, across two hundred engagements. It
is one self-contained file with no script and nothing fetched when it is
opened, because a page about the firm's clients must not reach the network
to render, and it is written from a report rather than from a lock: drawing
the page never changes what it describes.

**Every real pass leaves one page per engagement.** The last thing each
engagement's pass does is regenerate its view (``VIEW_FILENAME``,
:mod:`tracker.view`) from what the readers now say - the same kind of
self-contained page as the practice's, about one engagement. A person
opens that rather than the index, and a view whose replace does not land
is simply not replaced: the run carries ``view_stale`` and succeeds,
because the view holds no fact of its own.

**A household at a time** (decision 125). A client folder is a household
with one folder per tax year inside it and one folder per return inside
that, and the household has one permanent inbox. So a pass is over a
household: it takes every open return's lock, sorts the one inbox across
all of them at once - a drop is filed where exactly one return's requests
accept it, and parked where several or none do - and then scans, drafts
and draws each return in turn. A household with two open years sorts
nothing from its inbox and says so on every return, until a person retires
a year in the editor.

**And a drop folder may feed further than its own household** (decision
129). A person may extend it to named return lines in other households -
the co-owned business, the adult daughter's return a parent relays - and
the pass judges the inbox against those returns too, files into them, and
moves the original under the household the return that took it lives in.
Every lock it needs, its own and the fed ones, is taken in one global
order - household folder name, then return folder name, without case -
before anything is read, so two passes running at once cannot take the
same two returns the other way round. Nothing is ever inferred into that
list: a household is assembled by a person, and so is a feed.

**Every folder that does not fit the layout is listed and left alone.** The
practice page ends with them, each with the one sentence saying why
(``tracker.registry``). Nothing in one is ever read, moved or renamed.

One engagement's failure never stops the others. An unreadable record, a
scan already running, a drop that would not sort — each is recorded against
that engagement and the run moves on, because one client's problem must not
be the reason nine other clients went unprocessed. The command exits non-zero
if anything failed, so the scheduler shows a red run instead of a silent one.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import traceback
from collections.abc import Iterable
from contextlib import ExitStack, nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from tracker import content_check, ledger, store
from tracker.content_check import OCR_SCRATCH_DIR_NAME, ocr_scratch
from tracker.filer import (
    HOUSEHOLD_NO_ROOM,
    NEEDS_REVIEW,
    ROOM_PARKS,
    ensure,
    file_household_drops,
    read_index,
    refresh_household_readme,
    room_for,
)
from tracker.fsio import write_text_atomically
from tracker.households import load_household_info, open_years, resolve_feeds
from tracker.layout import household_of, inbox_of, lock_order_key, originals_dir_for, root_of
from tracker.ledger import LedgerError
from tracker.locking import engagement_lock
from tracker.manifest import (
    ISO_DATE_HINT,
    ManifestError,
    check_rules,
    load_manifest,
    summarize,
)
from tracker.page import esc, page_text, table, tolerant_console
from tracker.records import ENGAGEMENT_LABELS, NO, YES
from tracker.registry import (
    SKIP_ROLLED_FORWARD,
    Engagement,
    Misfit,
    Registry,
    RegistryError,
    discover_engagements,
)
from tracker.reminder import (
    APPROVED_NOTE,
    DRAFT_FILENAME,
    NEW_DRAFT_FILENAME,
    DraftsEditedError,
    ReminderError,
    draft_changed,
    draft_reminder,
    drafted_event,
    held_refusal,
    is_approved_this_week,
    is_protected,
    last_draft_event,
    record_draft,
    write_draft,
)
from tracker.scaffold import scaffold_engagement, scaffold_household
from tracker.scanner import ScanLockedError, scan_engagement
from tracker.settings import (
    ENV_SETTINGS_DIR,
    NO_ROOT_HINT,
    SettingsError,
    clients_root,
    firm,
    product_name,
    settings_dir,
    settings_path,
)
from tracker.store import StoreError
from tracker.view import VIEW_FILENAME, write_view

log = logging.getLogger("tracker.runner")

#: ``dt.date.weekday()`` counts from the start of the week as 0.
DRAFT_WEEKDAY = 5

WEEKDAY_NAMES = ("monday", "tuesday", "wednesday", "thursday",
                 "friday", "saturday", "sunday")
#: The draft day as a word, for help text and the app.
DRAFT_DAY_NAME = WEEKDAY_NAMES[DRAFT_WEEKDAY]

#: When the run drafts reminders.
REMINDERS_AUTO = "auto"      # only on DRAFT_WEEKDAY — the scheduled default
REMINDERS_ALWAYS = "always"  # draft today, whatever day it is
REMINDERS_NEVER = "never"    # file and scan only
REMINDER_MODES = (REMINDERS_AUTO, REMINDERS_ALWAYS, REMINDERS_NEVER)

#: The run log, written into the clients root (the folder the job is given)
#: so the firm finds it beside the engagements it describes.
LOG_FILENAME = "runs.log"
#: The firm-wide status page, written into the same folder as the log at the
#: end of every real pass. The log is the trace of one run; this is the
#: standing answer to what the practice owes and what needs a person.
STATUS_PAGE_FILENAME = "status.html"
#: The runner's own flags, named once so the scheduler builds a command
#: line the parser below still accepts.
LOG_FLAG = "--log"
DATE_FLAG = "--date"
#: The app's settings folder, which the scheduled job names instead of a
#: clients root (decision 131): the root has one home, the settings file,
#: and the job reads it at every run - so changing it in the app is enough,
#: and no re-install is remembered or forgotten.
SETTINGS_FLAG = "--settings"
#: What the scheduled job installed before decision 131 is told. That job
#: named a clients root on its command line with ``--log``; after the root
#: moves in the app it would go on sorting the old tree silently, so a run
#: of that shape whose root is not the settings file's is refused, red,
#: until *Install Schedule* is pressed once (decision 131's review, F3).
OLD_JOB_ROOT = ("the scheduled job still names an old clients root ({root}); open the app and "
                "press Install Schedule")


def _refuse_an_old_jobs_root(root: str) -> None:
    """Refuse a run shaped like the job installed before decision 131 - a
    root on the command line together with ``--log`` - whose root differs
    from the settings file's, or that has no settings root to agree with.

    A person running one folder by hand leaves ``--log`` off and is never
    refused: a root on the command line still wins for them.
    """
    try:
        configured = clients_root()
    except SettingsError as exc:
        raise SystemExit(f"Clients folder problem: {exc}") from None
    if configured is None or _one_folder(configured) != _one_folder(Path(root)):
        raise SystemExit(OLD_JOB_ROOT.format(root=root))


def _one_folder(path: Path) -> str:
    """A folder as two spellings of it compare: absolute, normalised, case-folded."""
    return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))


#: How the packaged app's one executable (api_entry.py) is told to be the
#: scheduled job rather than the API: this flag first, then the runner's own
#: arguments. tracker.scheduling builds the packaged command line from it.
RUNNER_MODE_FLAG = "--run"
#: What the run says about an engagement it drafted nothing for.
NOTHING_OUTSTANDING = "nothing outstanding; no reminder needed"
#: Which rung of the reminder a draft was written at (decision 117), said
#: once: the run's own line names it after the file, and the practice
#: page's Drafted cell says it instead of a bare yes, so the one screen a
#: person looks at on the draft day says how hard each client is being
#: asked.
STAGE_NOTE = "stage {n}"
#: Why an engagement is passed over, and why one cannot be run at all -
#: worded once, because the pass and the status page must agree about the
#: same engagement.
SKIP_INACTIVE = f"inactive (the engagement's details say {ENGAGEMENT_LABELS['active']}: {NO})"
RECORD_UNREADABLE = "the record could not be read: {problem}"
#: What a pass says about a view whose replace did not land. Not an error:
#: the view carries no fact, so the old one standing costs a person one pass.
VIEW_NOT_REGENERATED = "status report open (not regenerated)"
#: When a reading is slow enough to be worth saying (decision 127). A
#: scanned page costs about a second to read on the office machine, so
#: twenty seconds is a document doing something unusual - a long scan, a
#: photo of a whole desk, a page the four-way scorer had to read four
#: times. **Nothing is cut short at this number**: it decides only whether
#: the run's line mentions the document. Photos and scans are the readings
#: the owner's speed ceiling will be measured against, and a pass that
#: quietly abandoned the slow ones could not measure them. The one stop is
#: the safety stop beside it, ten times that ceiling (decision 137, B1.2).
SLOW_READING_SECONDS = 20.0
#: The safety stop, a minute a page and ten minutes a document: the reader
#: owns them (``tracker.content_check``) and they are named here beside the
#: number a slow reading is said at, so the two are read together.
READING_STOP_PAGE_SECONDS = content_check.READING_STOP_PAGE_SECONDS
READING_STOP_DOCUMENT_SECONDS = content_check.READING_STOP_DOCUMENT_SECONDS
SLOW_READING_NOTE = "slow reading: {name} took {seconds:.0f} s"


@dataclass(slots=True)
class EngagementRun:
    """What one engagement's pass did, including how it went wrong."""

    engagement: Engagement
    filed: int = 0
    review: int = 0
    waiting: int = 0
    file_errors: list[str] = field(default_factory=list)  # drops that went wrong
    warnings: list[str] = field(default_factory=list)     # rows the rules cannot act on; strays in Prepared/
    #: The request list :func:`_worth_a_pass` loaded for ``check_rules``,
    #: kept so the room is measured from the same list (decision 131) and
    #: the record is not read a second time for it.
    items: list = field(default_factory=list)
    #: The view was not regenerated because somebody had it open. Not a
    #: failure: it holds no fact of its own, so it simply stays one pass
    #: behind until the next pass lands one.
    view_stale: bool = False
    statuses: dict[str, int] = field(default_factory=dict)
    outstanding: int = 0             # from tracker.manifest.summarize, the one count
    drafted: Path | None = None
    #: Which of the reminder's four stages the draft was written at
    #: (decision 117), and 0 when no draft was written at all.
    stage: int = 0
    #: Whether this week's standing draft is one a person approved in the
    #: app (decision 118). The pass leaves it exactly as it leaves an
    #: edited one, and the practice page says so instead of a stage.
    approved: bool = False
    #: How many things hold this engagement's reminder: its ambiguous rows
    #: (decision 115) and the files still waiting in its household's inbox
    #: (decision 133); ``draft_note`` names them.
    held: int = 0
    #: This engagement's slowest readings, longest first (decision 127):
    #: (the document's own name, seconds). Carried from the filing report
    #: so the run's own line can say when one passed
    #: :data:`SLOW_READING_SECONDS`.
    slowest: list[tuple[str, float]] = field(default_factory=list)
    draft_note: str = ""      # why there is no draft, when there is a reason
    skipped: str = ""         # why the whole engagement was passed over
    error: str = ""           # what went wrong, if anything did
    #: When this engagement was passed over. None on a row the status page
    #: read rather than ran, so the page never dates a pass that never was.
    last_pass: dt.datetime | None = None

    @property
    def ok(self) -> bool:
        return not self.error

    def summary(self) -> str:
        if self.error:
            return f"ERROR   {self.engagement.label}: {self.error}"
        if self.skipped:
            return f"SKIP    {self.engagement.label}: {self.skipped}"
        parts = [f"filed {self.filed}"]
        if self.review:
            parts.append(f"review {self.review}")
        if self.waiting:
            parts.append(f"syncing {self.waiting}")
        if self.file_errors:
            parts.append(f"could not sort {len(self.file_errors)}")
        if self.view_stale:
            parts.append(VIEW_NOT_REGENERATED)
        parts.append(f"outstanding {self.outstanding}")
        if self.drafted:
            parts.append(f"drafted {self.drafted.name}")
            if self.stage:
                parts.append(STAGE_NOTE.format(n=self.stage))
        if self.approved:
            parts.append(APPROVED_NOTE)
        if self.held:
            parts.append(f"held {self.held}")
        # A reading that took its time is said, once, with the document
        # that took it (decision 127). It was never cut short: the words
        # are in the record and the row was decided on them.
        for name, seconds in self.slowest[:1]:
            if seconds >= SLOW_READING_SECONDS:
                parts.append(SLOW_READING_NOTE.format(name=name, seconds=seconds))
        return f"OK      {self.engagement.label}: {', '.join(parts)}"


@dataclass(slots=True)
class RunReport:
    """One pass over the whole registry."""

    today: dt.date
    dry_run: bool = False
    reminders: str = REMINDERS_AUTO
    runs: list[EngagementRun] = field(default_factory=list)
    #: The folders the walk left alone, each with the one sentence saying
    #: why (decision 125). Carried on the report because the practice page
    #: is drawn from the report and never from a fresh walk.
    misfits: list[Misfit] = field(default_factory=list)

    @property
    def processed(self) -> list[EngagementRun]:
        return [r for r in self.runs if r.ok and not r.skipped]

    @property
    def errors(self) -> list[EngagementRun]:
        return [r for r in self.runs if r.error]

    @property
    def drafted(self) -> list[EngagementRun]:
        return [r for r in self.runs if r.drafted]

    @property
    def held(self) -> list[EngagementRun]:
        return [r for r in self.runs if r.held]

    @property
    def outstanding(self) -> int:
        return sum(r.outstanding for r in self.processed)


# ------------------------------------------------------------- scheduling ----


def is_draft_day(today: dt.date, weekday: int = DRAFT_WEEKDAY) -> bool:
    """True on the day of the week reminders are drafted (``DRAFT_WEEKDAY``)."""
    return today.weekday() == weekday


def last_draft_day(today: dt.date, weekday: int = DRAFT_WEEKDAY) -> dt.date:
    """The most recent draft day on or before ``today``."""
    return today - dt.timedelta(days=(today.weekday() - weekday) % 7)


def last_drafted(engagement_dir: Path) -> dt.date | None:
    """The day this engagement's reminder was last drafted; None if it never was.

    From the record first (decision 115): the day of the last ``DRAFTED``
    event that wrote a file. A hold is not a draft, so a held client stays
    "not drafted this week" and the catch-up rule drafts it on the first
    pass after the hold clears. A journal from before the event existed
    answers from the draft files' own times, as it always did - a time a
    sync client may have set, which is why the record comes first.
    """
    event = last_draft_event(engagement_dir, carrying=ledger.FILE_KEY)
    if event is not None:
        return ledger.day_of(str(event.get(ledger.AT_KEY, "")))
    stamps = []
    for name in (DRAFT_FILENAME, NEW_DRAFT_FILENAME):
        try:
            stamps.append(dt.date.fromtimestamp((engagement_dir / name).stat().st_mtime))
        except OSError:
            continue
    return max(stamps) if stamps else None


def draft_is_held(engagement_dir: Path) -> bool:
    """Whether the record's last word on this engagement's reminder is a
    hold: the draft day came, an ambiguous row held the draft, and no draft
    has been written since. The week's draft is still owed."""
    event = last_draft_event(engagement_dir)
    return event is not None and ledger.HELD_KEY in event


def should_draft(
    engagement: Engagement,
    today: dt.date,
    mode: str = REMINDERS_AUTO,
    weekday: int = DRAFT_WEEKDAY,
    *,
    drafted: dt.date | None = None,
    held: bool = False,
) -> bool:
    """Whether the automated run drafts a reminder for this engagement today.

    ``Reminders`` set to ``NO`` in the engagement's details wins over every
    mode. It is a standing decision that this client is not chased by email,
    and a command line flag is not the place to reverse it —
    ``python -m tracker.reminder`` still drafts one on demand for anybody.

    Weekly means once a week, not only on the day: a machine that was off
    on the draft day drafts on its next pass, when ``drafted`` (the day the
    last draft was written) is older than the draft day that went by. An
    engagement never drafted waits for its first draft day, so a client set
    up mid-week is not chased the same afternoon - unless the record says
    its draft day came and the draft was ``held`` (decision 115): that
    draft is owed, and the first pass after a person clears the question
    writes it.
    """
    if not engagement.reminders or mode == REMINDERS_NEVER:
        return False
    if mode == REMINDERS_ALWAYS:
        return True
    if is_draft_day(today, weekday):
        return True
    if held:
        return True
    return drafted is not None and drafted < last_draft_day(today, weekday)


# --------------------------------------------------------------- one pass ----


#: What every return of a household is warned with while two of its years
#: are open. One inbox feeds the household (decision 125) and it cannot say
#: which year a document is for, so nothing is sorted from it until a year
#: is retired in the editor - which is a person's decision and never the
#: machine's guess.
TWO_OPEN_YEARS = ("two years are open in this household ({years}); nothing is sorted from its "
                  "inbox until one is retired in the editor")

#: What a household's pass says about a document it filed into a return it
#: feeds (decision 129). The row belongs to the return that took it and the
#: report of it belongs to that return's own pass, so without this sentence
#: the household that sorted the drop said "filed 0" of a pass that filed
#: something - true of its own returns and misleading about the pass. One
#: sentence per fed return that received a filing, on the first of this
#: household's own returns, in the warnings: the channel the unresolved
#: feed already speaks through.
FILED_INTO_FED = "{n} document(s) filed into {label} from this drop folder"
#: What every one of a household's own returns is warned with when its
#: own record - the one holding the feed list - is there and will not read
#: (decision 132). The pass goes on with the household's own returns, and
#: says so: a route the pass cannot read is never skipped in silence.
#: Discovery's misfit list covers a household *without* a record; this is
#: one whose record is there and refuses to parse.
FEEDS_UNREAD = ("this drop folder's record could not be read ({error}); it feeds only its own "
                "returns this pass")
#: What a pass handed no practice to walk says, on every return it was
#: asked about, and does nothing else (decision 132). The feed list is
#: resolved against the practice, and a pass that cannot honour the feed
#: list is a second definition of a pass - which is how *Run now* and the
#: schedule came to disagree once. So there is one way to call a pass.
NO_PRACTICE = ("the practice could not be walked, so this household's feed list cannot be "
               "resolved; nothing was sorted or scanned this pass")


def run_household(
    household: Path,
    returns: list[Engagement],
    *,
    root: Path | None = None,
    today: dt.date | None = None,
    dry_run: bool = False,
    reminders: str = REMINDERS_AUTO,
    weekday: int = DRAFT_WEEKDAY,
    registry: object,
) -> list[EngagementRun]:
    """One pass over a whole household: sort its one inbox across every
    return it feeds, then scan, draft and draw each of its own returns.

    **The household is the unit of a pass** (decision 125). A household has
    one inbox, so the sort has to judge each drop against every open-year
    return under their locks together: taking them one at a time would let
    a click in the app step between two returns that one document was
    being judged against.

    **And the inbox may feed further** (decision 129). A person may extend
    a household's drop folder to named return lines in other households -
    the co-owned business, the adult daughter's return a parent relays -
    and those returns are judged, locked and filed into exactly like the
    household's own; ``registry`` is the walk the feeds are resolved
    against (a :class:`tracker.registry.Registry`, or anything with its
    ``engagements`` and ``households``). **It is required** (decision 132):
    a pass that could be called without the practice silently fed nothing,
    which is how *Run now* and the schedule once disagreed; a ``None`` -
    a root that could not be walked - is refused with one sentence
    (:data:`NO_PRACTICE`) on every run, and nothing is touched.
    The locks - its own and every fed one - are taken in the **one global
    order** (``layout.lock_order_key``: the household's folder name, then
    the return's, without case) before anything is read, so two processes
    can never take the same two returns the other way round, and one held
    elsewhere skips the whole household this pass, with nothing touched.

    **Two open years sorts nothing.** The inbox cannot say which year a
    document is for, so every return of the household is warned and the
    inbox is not read; the scan, the draft and the page still run, because
    what each return already holds is still true.

    **The room is measured before anything is read** (decision 131,
    :func:`_no_room`): a return short of room is still sorted, its copies
    named to fit, and is not warned; a request that cannot receive is; a return with no room for even a review copy
    skips the whole household, as a held lock does.

    Never raises for a return-level problem: anything that goes wrong is
    recorded on that return's :class:`EngagementRun` so the caller can keep
    going through the rest of the practice.
    """
    today = today or dt.date.today()
    # Stamped before anything is touched, so a return that fails its
    # pre-checks still says when it was last looked at.
    runs = [EngagementRun(engagement=one, last_pass=dt.datetime.now()) for one in returns]
    if registry is None:
        for run in runs:
            run.error = NO_PRACTICE
        return runs
    working = [run for run in runs if _worth_a_pass(run)]
    if not working:
        return runs
    if _no_room(working):
        return runs

    years = open_years([run.engagement for run in working])
    if len(years) > 1:
        note = TWO_OPEN_YEARS.format(years=", ".join(str(year) for year in years))
        for run in working:
            run.warnings.append(note)
    # The one global lock order: the household's folder name, then the
    # return's, without case. Within one household that is the return
    # folder's own order, which is what the sort calls "first by order"
    # too, so the return a contested drop parks in is the return whose
    # lock was taken first.
    working.sort(key=lambda run: lock_order_key(run.engagement.path))
    sorting = [run for run in working
               if len(years) == 1 and run.engagement.tax_year == years[0]]
    # The return lines in other households this drop folder also feeds
    # (decision 129), resolved to this year's returns; a line that answers
    # to nothing is said on every one of the household's own returns.
    fed: list[Engagement] = []
    if sorting:
        fed, unresolved = _feeds_of(household, years[0], registry)
        for run in working:
            run.warnings.extend(unresolved)

    try:
        with ExitStack() as locks:
            # A dry run takes none: it writes nothing and must never block
            # a real run.
            if not dry_run:
                for folder in sorted([*(run.engagement.path for run in working),
                                      *(one.path for one in fed)],
                                     key=lock_order_key):
                    locks.enter_context(engagement_lock(folder))
            # The household's own side - the inbox and the year's folder -
            # is laid out once for the lot, before the inbox is read. The
            # fed returns are not in it: a fed return's own household lays
            # out its own folders, and its request list is not this
            # client's to read.
            if not dry_run:
                scaffold_household(household, returns=[run.engagement.path for run in working])
            if sorting:
                _sort_step(household, sorting, fed, today=today, dry_run=dry_run)
            for run in working:
                run_engagement(run.engagement, root=root, today=today, dry_run=dry_run,
                               reminders=reminders, weekday=weekday, lock_held=not dry_run,
                               run=run)
            # The README, once, after the sort and after every return's
            # scan and draft, still inside the locks (decision 130): what
            # the client reads is current as of this pass, never one pass
            # behind. A household this inbox fed a document into is told
            # too - the document is in its index now, so it is on its list
            # (132's F-4 ruling), and it should not wait for its own pass.
            # Each writes only when its text changed.
            if not dry_run:
                for one in dict.fromkeys([household, *(household_of(f.path) for f in fed)]):
                    refresh_household_readme(one)
    except ScanLockedError as exc:
        for run in working:
            run.skipped = f"another run is still going ({exc})"
    except Exception as exc:  # the household's surprise must not stop the practice
        for run in working:
            if not run.error:
                run.error = f"{exc.__class__.__name__}: {exc}"
                run.draft_note = traceback.format_exc(limit=3).strip().splitlines()[-1]
    for run in working:
        if run.file_errors and not run.error:
            # The rest of the pass went ahead, but a drop that could not be
            # sorted is a failure the scheduler must show, not a footnote.
            run.error = (
                f"{len(run.file_errors)} file(s) could not be sorted "
                f"(filed {run.filed}, review {run.review}): "
                + "; ".join(run.file_errors[:3])
            )
    return runs


def _no_room(working: list[EngagementRun]) -> bool:
    """Measure every working return's room before anything is read, and
    say whether the household must stop (decision 131).

    Each return's room is one number from one function
    (``filer.room_for``), measured from the list :func:`_worth_a_pass`
    already loaded. A return merely short of room is **not warned** (the
    lead's L-1 on decision 131): its names are cut to fit where they are
    written and everything still files, and with a reader's 218 for
    spreadsheets every 1040 at the firm's root would carry the sentence
    every pass - a warning always on is a warning nobody reads. The
    return's page in the app and the reply to setting the root say the
    figure as information. Warned: :data:`ROOM_PARKS`, when some request
    cannot receive at all. A
    return whose review folder leaves no room for even a review copy stops
    its whole household, exactly as a lock held elsewhere does: one inbox
    feeds every return, and a pass that cannot park cannot honour a scan
    that regresses a copy either, so nothing is read, scanned, drafted or
    drawn, and every working return carries :data:`HOUSEHOLD_NO_ROOM`.
    """
    stopped = ""
    for run in working:
        room = room_for(run.engagement.path, run.items)
        if room.parks:
            run.warnings.append(ROOM_PARKS.format(count=room.parks))
        if room.floor > room.limit and not stopped:
            stopped = HOUSEHOLD_NO_ROOM.format(label=run.engagement.label, length=room.floor,
                                               limit=room.limit)
    if stopped:
        for run in working:
            run.skipped = stopped
    return bool(stopped)


def _feeds_of(household: Path, year: int, registry: object) -> tuple[list[Engagement], list[str]]:
    """The returns this household's drop folder also feeds this year, and
    the sentences for the feeds nothing answers (decision 129).

    Each one whole, not only its folder: the sort needs the path and the
    pass needs the label, because a filing into a fed return is reported
    on the dropping household's own run by the name a person reads.

    A household whose own record cannot be read feeds nothing but its own
    - a feed nobody can prove is a route nothing should take - and **says
    so** (decision 132, :data:`FEEDS_UNREAD`), on every own return, exactly
    as a feed that resolves to nothing is said.
    """
    try:
        feeds = load_household_info(household).feeds
    except Exception as exc:
        return [], [FEEDS_UNREAD.format(error=f"{exc.__class__.__name__}: {exc}")]
    if not feeds:
        return [], []
    found, said = resolve_feeds(household, feeds, year, registry)
    return found, said


def _sort_step(household: Path, sorting: list[EngagementRun], fed: list[Engagement], *,
               today: dt.date, dry_run: bool) -> None:
    """The household's one inbox, sorted across the returns of its open year
    and the returns it feeds.

    One call, under the locks the caller holds, and one transaction per
    return inside it (decision 102, unchanged). Each of this household's
    own returns fills its own run; a fed return's report belongs to the
    pass of the household it lives in, which records what it filed for it.

    What this pass filed into a fed return is still this pass's to say
    (decision 129): the rows are the other return's, but the drop folder
    was this household's, and a pass that reported "filed 0" of documents
    it had just filed elsewhere was telling a person the wrong thing about
    their own inbox. One sentence per fed return that received something,
    on the first own return's run, in its warnings.
    """
    first = sorting[0].engagement.path
    # The year the record says, not the year folder's name: a folder
    # somebody renamed is processed as the record says and warned about
    # (``tracker.registry.NAME_DISAGREES``), never renamed.
    year = sorting[0].engagement.tax_year
    originals = originals_dir_for(root_of(first), household.name, year)
    reports = file_household_drops(
        inbox_of(first), originals,
        own=[run.engagement.path for run in sorting], fed=[one.path for one in fed],
        today=today, dry_run=dry_run,
    )
    sorting[0].warnings.extend(
        FILED_INTO_FED.format(n=len(reports[one.path].filed), label=one.label)
        for one in fed
        if one.path in reports and reports[one.path].filed
    )
    for run in sorting:
        filed = reports.get(run.engagement.path)
        if filed is None:
            continue
        run.filed = len(filed.filed)
        run.review = len(filed.review)
        run.waiting = len(filed.waiting)
        run.file_errors = [f"{e.name}: {e.error}" for e in filed.errors]
        run.slowest = filed.slowest
        # An original already sorted whose record no longer fits the disk
        # is for a person to look at, every pass - but nothing was left
        # unsorted, so it rides the warnings rather than failing the run.
        run.warnings.extend(f"{e.name}: {e.error}" for e in filed.attention)


def run_engagement(
    engagement: Engagement,
    *,
    root: Path | None = None,
    today: dt.date | None = None,
    dry_run: bool = False,
    reminders: str = REMINDERS_AUTO,
    weekday: int = DRAFT_WEEKDAY,
    lock_held: bool = False,
    run: EngagementRun | None = None,
) -> EngagementRun:
    """Scaffold, scan and (on the draft day) draft and draw one return.

    **The per-return half of a pass** since decision 125: the sort is the
    household's, because one inbox feeds every return of it, and
    :func:`run_household` does that half under every open return's lock and
    hands each run here. ``lock_held`` says the caller already holds this
    return's lock and this must not take it again - which is what decision
    102 has said since a pass became one locked section.

    Never raises for a return-level problem: anything that goes wrong is
    recorded on the returned :class:`EngagementRun` so the caller can keep
    going through the rest of the practice.
    """
    today = today or dt.date.today()
    # Stamped before anything is touched, so a return that fails its
    # pre-checks still says when it was last looked at.
    if run is None:
        run = EngagementRun(engagement=engagement, last_pass=dt.datetime.now())
        if not _worth_a_pass(run):
            return run
    try:
        # A dry run takes no lock: it writes nothing and must never block
        # a real run.
        with nullcontext() if dry_run or lock_held else engagement_lock(engagement.path):
            # **The store is brought up to the record first.** Everything
            # below answers from it; a rules edit a person saved since the
            # last pass is already in the journal (decision 104).
            ensure(engagement.path, root)
            # A row added, or made applicable again, in the app gets its
            # folder here, on the next pass, rather than when somebody
            # remembers to re-run scaffold. Idempotent: nothing existing is
            # touched. It writes no README (decision 130): the household
            # pass refreshes that once, after every return has run.
            if not dry_run:
                scaffold_engagement(engagement.path)   # contact from the household
            scanned = scan_engagement(engagement.path, root=root, today=today, dry_run=dry_run,
                                      lock_held=not dry_run)
            summary = scanned.summary
            run.statuses = summary.counts
            run.outstanding = summary.outstanding
            run.warnings.extend(scanned.warnings)

            if should_draft(engagement, today, reminders, weekday,
                            drafted=last_drafted(engagement.path),
                            held=draft_is_held(engagement.path)):
                _draft_step(run, dry_run=dry_run, today=today, weekday=weekday)
            else:
                run.draft_note = _why_no_draft(engagement, today, reminders, weekday)

            if not dry_run and not run.error:
                _view_step(run)
    except ScanLockedError as exc:
        run.skipped = f"another run is still going ({exc})"
    except (ManifestError, ReminderError) as exc:
        run.error = str(exc)
    except Exception as exc:  # one client's surprise must not stop the rest
        run.error = f"{exc.__class__.__name__}: {exc}"
        run.draft_note = traceback.format_exc(limit=3).strip().splitlines()[-1]
    return run


def _view_step(run: EngagementRun) -> None:
    """Regenerate the engagement's own page: the last thing a pass does.

    After the statuses and after the draft, because the view is drawn from
    what the pass has already written and a view drawn halfway through would
    describe a state that never existed. It takes no lock - the pass takes
    one per step for its own writes, and this writes nothing anybody reads
    back - so it follows the status page (decision 75): drawn from what the
    readers now say, never taking a lock, and never able to fail a pass.

    A view somebody had open is not regenerated and is not an error; it
    carries no fact, so the old one standing is the whole cost. Anything
    else that goes wrong here is a log line for the same reason the page's
    is: every original has been moved and every status written by now.
    """
    try:
        run.view_stale = write_view(run.engagement.path).stale
    except Exception as exc:
        log.warning("Could not write %s for %s (%s)",
                    VIEW_FILENAME, run.engagement.label, exc)


def skipped_because(engagement: Engagement) -> str:
    """Why this engagement is passed over, or "" if it is not.

    The pass and the status page ask the same question of the same
    engagement, so they ask it in one place: a prior year its successor
    retired, and a client the details say is finished with, are neither
    failures nor work outstanding, and neither should read as one.
    """
    if engagement.superseded_by:
        return SKIP_ROLLED_FORWARD.format(successor=engagement.superseded_by)
    if not engagement.active:
        return SKIP_INACTIVE
    return ""


def _worth_a_pass(run: EngagementRun) -> bool:
    """Whether this engagement gets a pass at all; if not, ``run`` says why.

    Skips (rolled forward, inactive) are not failures; a missing folder or
    an unreadable record are - named before a single file is touched.
    Warnings - the rows the rules cannot act on, the same list the app's
    ``state`` carries - ride the report rather than being noticed at a
    deadline.
    """
    engagement = run.engagement
    run.skipped = skipped_because(engagement)
    if run.skipped:
        return False
    if not engagement.path.is_dir():
        run.error = f"folder not found: {engagement.path}"
        return False
    if engagement.problem:
        run.error = RECORD_UNREADABLE.format(problem=engagement.problem)
        return False
    try:
        run.items = load_manifest(engagement.path)
        run.warnings = check_rules(run.items)
    except (ManifestError, LedgerError, StoreError) as exc:
        # A folder with no record, a journal line that will not parse, a
        # store that will not open: the registry names these as the
        # engagement's problem when it found the folder, and a caller that
        # handed the folder over directly hears the same sentence here.
        run.error = RECORD_UNREADABLE.format(problem=exc)
        return False
    if engagement.warning:
        run.warnings.append(engagement.warning)
    return True


def _draft_step(run: EngagementRun, *, dry_run: bool, today: dt.date,
                weekday: int = DRAFT_WEEKDAY) -> None:
    """Draft the reminder for a pass that has decided today is the day. Never sends.

    Runs inside the pass's lock (decision 102), which is what lets the
    draft go on the record (decision 115): one ``DRAFTED`` event through
    the store, appended only when it says something the last one did not.
    """
    # A dry run recorded nothing, so there is nothing in the record for
    # the drafter to read. Report from the scan we just did in memory
    # rather than reading back statuses that were deliberately not saved.
    if dry_run:
        run.draft_note = (
            f"would draft {run.outstanding} item(s)" if run.outstanding
            else NOTHING_OUTSTANDING
        )
        return

    engagement = run.engagement
    # What the record last said (a draft or a hold), and the last draft a
    # person could have sent: the first is what only-what-changed compares
    # with, the second is what the header's what-changed block compares
    # with, so the draft after a hold says what the resolution changed.
    previous = last_draft_event(engagement.path)
    last_asked = last_draft_event(engagement.path, carrying=ledger.ASKED_KEY)
    # The pass's own day, not the clock's: the stage is measured from it,
    # so a catch-up pass writes the letter the missed draft day was owed
    # and a dated run says what it would have said on that date.
    draft = draft_reminder(engagement.path, today=today)   # reads the details itself
    week = last_draft_day(today, weekday)
    # A draft a person approved in the app this week is this week's answer
    # (decision 118): the pass leaves the file alone exactly as it leaves
    # one somebody edited, and the page says so.
    run.approved = is_approved_this_week(engagement.path, engagement.path / DRAFT_FILENAME,
                                         since=week)

    if draft.is_held:
        # One ambiguous row holds the whole reminder: nothing that reads
        # like a sendable email may exist for this client, so the run's
        # own unedited drafts from an earlier week go; a person's edited
        # one is theirs (decision 15). Said in the note, counted on the
        # page, and on the record. The same path serves --reminders
        # always: the mode forces the attempt, and the attempt is held.
        # What holds it: the rows (decision 115) and the files still
        # waiting in the household's inbox (decision 133), counted
        # together, and the sentence names both.
        run.held = len(draft.held) + draft.unsorted
        run.draft_note = held_refusal(draft)
        _retire_unedited_drafts(engagement.path, approved_since=week)
        _record(engagement.path, previous, drafted_event(draft, None))
        return

    if not draft.has_outstanding:
        run.draft_note = NOTHING_OUTSTANDING
        refreshed = _refresh_stale_draft(draft, engagement.path, changed_from=last_asked,
                                         approved_since=week)
        _record(engagement.path, previous,
                drafted_event(draft, refreshed[0] if refreshed else None), since=week)
        return

    try:
        written = write_draft(draft, engagement_dir=engagement.path, preserve_edits=True,
                              changed_from=last_asked, approved_since=week)
    except DraftsEditedError as exc:
        run.draft_note = str(exc)
        return
    run.drafted = written
    run.stage = draft.stage
    if written.name == NEW_DRAFT_FILENAME:
        run.draft_note = (
            f"{DRAFT_FILENAME} has been edited, so this week's draft was "
            f"written to {NEW_DRAFT_FILENAME} instead"
        )
    _record(engagement.path, previous, drafted_event(draft, written), since=week)


def _record(engagement_dir: Path, previous: dict | None, event: dict, *,
            since: dt.date | None = None) -> None:
    """Put the draft on the record when it says something new (decision 115).

    Only what changed, as the scanner's statuses are: the same hold, or the
    same draft rewritten by the draft day's repeat, appends nothing. A file
    written in a new draft week is something new - it is the week's draft,
    and ``last_drafted()`` reads the week from it - so ``since`` is the
    draft day that went by.
    """
    if draft_changed(previous, event, since=since):
        record_draft(engagement_dir, event)


def _retire_unedited_drafts(engagement_dir: Path, *,
                            approved_since: dt.date | None = None) -> None:
    """A held client has no draft file (decision 115): the run's own
    unedited drafts from an earlier week are removed, and one a person has
    edited - or approved this week (decision 118) - is left byte for byte;
    it is their work, not the run's."""
    for name in (DRAFT_FILENAME, NEW_DRAFT_FILENAME):
        path = engagement_dir / name
        if not path.is_file() or is_protected(engagement_dir, path, approved_since=approved_since):
            continue
        try:
            path.unlink()
        except OSError as exc:    # open in Word, or a sync client mid-upload: next time
            log.warning("Could not retire %s (%s)", path.name, exc)


def _refresh_stale_draft(draft, engagement_dir: Path, *, changed_from: dict | None = None,
                         approved_since: dt.date | None = None) -> list[Path]:
    """Nothing is outstanding, and a draft from a week that had something to
    chase is still there. The run's own unedited draft is rewritten as what
    the run would say today - the same text ``python -m tracker.reminder``
    writes - so it is neither stale nor dated as if untouched; one a person
    has edited, or approved this week, is theirs and is left exactly as it
    is. Returns the files it
    refreshed: the first is what the ``DRAFTED`` event names, so
    ``last_drafted`` reads this draft day and no weekday pass mistakes the
    quiet week for a missed one.
    """
    refreshed: list[Path] = []
    for name in (DRAFT_FILENAME, NEW_DRAFT_FILENAME):
        path = engagement_dir / name
        if not path.is_file() or is_protected(engagement_dir, path, approved_since=approved_since):
            continue
        try:
            refreshed.append(write_draft(draft, path=path, changed_from=changed_from))
        except OSError as exc:    # open in Word, or a sync client mid-upload: next time
            log.warning("Could not refresh %s (%s)", path.name, exc)
    return refreshed


def _why_no_draft(engagement: Engagement, today: dt.date,
                  mode: str, weekday: int) -> str:
    if not engagement.reminders:
        return "reminders are off for this engagement"
    if mode == REMINDERS_NEVER:
        return "reminders suppressed for this run"
    return f"not {WEEKDAY_NAMES[weekday]}; reminders are drafted weekly"


def run_registry(
    registry: Registry,
    *,
    today: dt.date | None = None,
    dry_run: bool = False,
    reminders: str = REMINDERS_AUTO,
    weekday: int = DRAFT_WEEKDAY,
    only: str = "",
) -> RunReport:
    """Run every household in the registry, in the order it lists them.

    **A household at a time** (decision 125), because its returns share one
    inbox and the sort has to judge a drop against all of them at once.
    ``only`` still selects returns and the report still holds those: what
    it cannot do is sort half a household's inbox, so the household the
    selected return is in gets a whole pass and the report says what was
    asked about.
    """
    if reminders not in REMINDER_MODES:
        raise ValueError(
            f"reminders must be one of {', '.join(REMINDER_MODES)}, got {reminders!r}"
        )
    today = today or dt.date.today()
    selected = {e.path for e in (registry.find(only) if only else registry.engagements)}

    report = RunReport(today=today, dry_run=dry_run, reminders=reminders,
                       misfits=list(registry.misfits))
    for household, returns in registry.by_household().items():
        if not any(one.path in selected for one in returns):
            continue
        report.runs.extend(
            run for run in run_household(household, returns, root=registry.source, today=today,
                                         dry_run=dry_run, reminders=reminders, weekday=weekday,
                                         registry=registry)
            if run.engagement.path in selected
        )
    return report


# ------------------------------------------------------------------ output ----


def format_report(report: RunReport) -> str:
    """The console (and log) rendering of one pass."""
    mode = {
        REMINDERS_AUTO: ("drafting reminders" if is_draft_day(report.today) or report.drafted
                         else "no reminders today"),
        REMINDERS_ALWAYS: "drafting reminders (forced)",
        REMINDERS_NEVER: "reminders suppressed",
    }[report.reminders]
    head = f"{report.today.isoformat()} ({WEEKDAY_NAMES[report.today.weekday()]}) - {mode}"
    if report.dry_run:
        head += " - DRY RUN, nothing written"

    lines = [head, ""]
    for run in report.runs:
        lines.append("  " + run.summary())
        if run.draft_note and not run.error:
            lines.append(f"            {run.draft_note}")
        for warning in run.warnings:
            lines.append(f"            ! {warning}")

    lines += [
        "",
        f"  {len(report.processed)} processed, {len(report.errors)} failed, "
        f"{len(report.drafted)} draft(s) written, "
        + (f"{len(report.held)} held, " if report.held else "")
        + f"{report.outstanding} request(s) outstanding",
    ]
    if report.drafted:
        lines.append("  Drafts are drafts: nothing has been sent to anyone.")
    return "\n".join(lines)


def append_log(path: Path | str, report: RunReport) -> Path:
    """Append this pass to a run log, so an unattended failure leaves a trace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"[{stamp}] {report.today.isoformat()} "
             f"reminders={report.reminders} dry_run={report.dry_run}"]
    for run in report.runs:
        lines.append(f"    {run.summary()}")
        if run.held and not run.error:
            # A hold is said with its rows (decision 115): the log is where
            # a person finds out which request wants their decision.
            lines.append(f"            {run.draft_note}")
    # A summary names client files, and a name NTFS holds is not always
    # one UTF-8 can (a lone surrogate); the log takes what it can write
    # rather than lose every engagement's line to one name.
    with path.open("a", encoding="utf-8", errors="backslashreplace") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


# ------------------------------------------------------------- status page ----

#: Every word the page shows that is not data. A person reads this page and
#: nothing else does, so the sentences are worded here rather than buried in
#: the markup that renders them.
STATUS_GENERATED = "Generated {stamp}"
STATUS_ENGAGEMENTS_HEADING = "Engagements"
STATUS_REVIEW_HEADING = "Waiting for a person"
STATUS_PROBLEMS_HEADING = "Problems"
STATUS_NOTHING_PARKED = "Nothing is waiting for a person."
STATUS_NO_PROBLEMS = "Nothing failed."
#: The folders the walk left alone (decision 125), and what is said when
#: there are none. The sentence on each is the registry's; this is only the
#: heading a person reads and the two columns it is drawn in.
STATUS_MISFITS_HEADING = "Folders the tracker leaves alone"
STATUS_NO_MISFITS = "Every folder fits the layout."
MISFIT_COLUMNS = ("Folder", "Why it is left alone")
#: What the last-pass cell says for an engagement the page read rather than ran.
STATUS_NOT_PASSED = "not this pass"
#: What the Drafted cell says for an engagement whose reminder is held (decision 115).
STATUS_HELD = "held ({n})"
STATUS_INDEX_UNREADABLE = "{label}: the index could not be read ({error})"

#: The two tables, column by column, in the order they are drawn. There is
#: no "Deferred writes" column any more: nothing a pass decides waits for
#: anything (decision 103 took the last deferred write).
STATUS_COLUMNS = (
    "Engagement", "Client", "Outstanding", STATUS_REVIEW_HEADING, "Still syncing",
    "Problem or skipped", "Warnings", "Last pass", "Drafted",
)
REVIEW_COLUMNS = ("Received", "Engagement", "File the client sent", "Reason", "Candidates")

#: Inline, because the page is one file that must render from a share, a
#: memory stick or an email attachment with nothing fetched: a page about
#: the firm's clients that reaches the network to look right is a page that
#: tells somebody else which firm is reading what.
_STATUS_STYLE = """
body { font-family: "Segoe UI", system-ui, sans-serif; margin: 2rem 2.5rem; color: #1c1c1c;
       background: #fbfbfa; line-height: 1.45; }
h1 { font-size: 1.35rem; margin: 0 0 0.2rem; }
h2 { font-size: 1.05rem; margin: 2rem 0 0.6rem; border-bottom: 1px solid #d8d6d1; padding-bottom: 0.3rem; }
p.stamp { margin: 0 0 0.5rem; color: #6b6862; font-size: 0.85rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.87rem; }
th, td { text-align: left; padding: 0.35rem 0.6rem; border-bottom: 1px solid #e6e4df; vertical-align: top; }
th { background: #f0eeea; font-weight: 600; white-space: nowrap; }
tr:hover td { background: #f6f5f2; }
ul { margin: 0; padding-left: 1.2rem; }
li { margin-bottom: 0.3rem; }
"""


@dataclass(frozen=True, slots=True)
class ParkedFile:
    """One file waiting for a person, and the engagement it is waiting in."""

    engagement: str
    received: str
    original_name: str
    reason: str
    candidates: str


def _parked_files(report: RunReport) -> tuple[dict[Path, list[ParkedFile]], list[str]]:
    """Every file parked for a person, by engagement folder, and what could
    not be read.

    Each engagement's index is read the way every reader reads it - no
    lock, no quarantine of a sidecar it cannot parse - because drawing the
    practice must never move a client's file or stand in the way of the
    pass that is filing one. An index that cannot be read is said rather
    than skipped: an engagement missing from the queue for a reason nobody
    can see is how a document waits a month.
    """
    parked: dict[Path, list[ParkedFile]] = {}
    problems: list[str] = []
    for run in report.runs:
        engagement = run.engagement
        try:
            ensure(engagement.path)
            entries = read_index(engagement.path)
        except Exception as exc:
            problems.append(STATUS_INDEX_UNREADABLE.format(label=engagement.label, error=exc))
            continue
        parked[engagement.path] = [
            ParkedFile(engagement=engagement.label, received=entry.received,
                       original_name=entry.original_name, reason=entry.reason,
                       candidates=entry.candidates)
            for entry in entries if entry.decision == NEEDS_REVIEW
        ]
    return parked, problems


def _page_title(root: Path) -> str:
    """What the page calls itself.

    The product's name, which the Electron shell passes in and a source
    checkout reads from the app's own package.json. The packaged app's
    scheduled job has neither (``api_entry.py`` says why it must not need
    them), and a pass that has finished its work must not end in a
    traceback over a heading: the firm's name, and then the folder the
    practice lives in, are names for the same thing that are always there.
    """
    for named in (product_name, firm):
        try:
            name = named()
        except SettingsError:
            continue
        if name:
            return name
    return root.name


def _drafted_cell(run: EngagementRun) -> str:
    """What the practice page's Drafted column says about one engagement:
    the hold and its count, else that a person has approved this week's
    draft, else the stage the draft was written at, else yes for a draft
    from before the stages, else nothing at all."""
    if run.held:
        return STATUS_HELD.format(n=run.held)
    if run.approved:
        return APPROVED_NOTE
    if run.stage:
        return STAGE_NOTE.format(n=run.stage)
    return YES if run.drafted else ""


def _engagement_cells(run: EngagementRun, parked: list[ParkedFile]) -> tuple:
    """One engagement's row, in ``STATUS_COLUMNS`` order."""
    return (
        run.engagement.label,
        run.engagement.client,
        run.outstanding,
        len(parked),
        run.waiting,
        run.error or run.skipped,
        len(run.warnings),
        run.last_pass.isoformat(sep=" ", timespec="seconds") if run.last_pass else STATUS_NOT_PASSED,
        _drafted_cell(run),
    )


def write_status_page(root: Path | str, report: RunReport, *,
                      now: dt.datetime | None = None) -> Path:
    """Write the practice on one page into ``root``, and return where it went.

    One self-contained file: no script, no style sheet, no image, nothing
    fetched when it is opened. It names client files, which is why it is
    written into the firm's own clients folder and never into the
    repository, and why every value on it goes through :func:`tracker.page.esc`
    - a document called like a tag is shown as its name, not rendered as one.

    Drawn from ``report``, never from a fresh pass: the caller decides what
    was run and what was only read (see :func:`status_report`), so nothing
    here takes a lock or writes anything but this page.
    """
    root = Path(root)
    stamp = (now or dt.datetime.now()).isoformat(sep=" ", timespec="seconds")
    parked, problems = _parked_files(report)
    problems = [f"{run.engagement.label}: {run.error}" for run in report.errors] + problems

    # Newest first, across the practice: what arrived last night is what
    # nobody has looked at. Reversed first, so that among files received on
    # the same day the later index row comes first - the sort is stable and
    # leaves them in the order it is given.
    queue = [file for run in report.runs for file in parked.get(run.engagement.path, ())][::-1]
    queue.sort(key=lambda file: file.received, reverse=True)

    title = _page_title(root)
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{esc(title)}</title>",
        f"<style>{_STATUS_STYLE}</style>",
        "</head>",
        "<body>",
        f"<h1>{esc(title)}</h1>",
        f'<p class="stamp">{esc(STATUS_GENERATED.format(stamp=stamp))}</p>',
        f"<h2>{esc(STATUS_ENGAGEMENTS_HEADING)} ({len(report.runs)})</h2>",
        *table(STATUS_COLUMNS,
               (_engagement_cells(run, parked.get(run.engagement.path, []))
                for run in report.runs)),
        f"<h2>{esc(STATUS_REVIEW_HEADING)} ({len(queue)})</h2>",
        *(table(REVIEW_COLUMNS,
                ((f.received, f.engagement, f.original_name, f.reason, f.candidates)
                 for f in queue))
          if queue else [f"<p>{esc(STATUS_NOTHING_PARKED)}</p>"]),
        f"<h2>{esc(STATUS_PROBLEMS_HEADING)} ({len(problems)})</h2>",
        *(["<ul>", *(f"<li>{esc(problem)}</li>" for problem in problems), "</ul>"]
          if problems else [f"<p>{esc(STATUS_NO_PROBLEMS)}</p>"]),
        # Every folder that does not fit the layout, with the one sentence
        # saying why it is left alone (decision 125, the owner's rule).
        # Nothing in one is ever read, moved or renamed; a person fixes it.
        f"<h2>{esc(STATUS_MISFITS_HEADING)} ({len(report.misfits)})</h2>",
        *(table(MISFIT_COLUMNS,
                ((_under(root, misfit.path), misfit.sentence) for misfit in report.misfits))
          if report.misfits else [f"<p>{esc(STATUS_NO_MISFITS)}</p>"]),
        "</body>",
        "</html>",
    ]
    path = root / STATUS_PAGE_FILENAME
    write_text_atomically(path, page_text(lines))
    return path


def _engagement_status(engagement: Engagement) -> EngagementRun:
    """One engagement's line, read rather than run.

    The record, the way the app reads it for one engagement - no lock, no
    scaffold, no scan, nothing written in the folder. A row the page read
    carries no pass time, because no pass was made.
    """
    run = EngagementRun(engagement=engagement)
    run.skipped = skipped_because(engagement)
    if run.skipped:
        return run           # a prior year's numbers are not this year's work
    if engagement.problem:
        run.error = RECORD_UNREADABLE.format(problem=engagement.problem)
        return run
    try:
        summary = summarize(load_manifest(engagement.path))
    except (ManifestError, OSError) as exc:
        run.error = str(exc)
        return run
    run.statuses = summary.counts
    run.outstanding = summary.outstanding
    if engagement.warning:
        run.warnings.append(engagement.warning)
    return run


def _under(root: Path, path: Path) -> str:
    """A folder as a person reads it on the practice page: its path below
    the clients root, or the whole path when it is not under one."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def status_report(registry: Registry, *, passed: Iterable[EngagementRun] = (),
                  today: dt.date | None = None) -> RunReport:
    """Every engagement in ``registry``, with the runs in ``passed`` folded in.

    The page is about the practice, not about whichever engagement was
    just run: a pass over one engagement (the app's button) or over a
    subset (``--only``) still draws every engagement the registry found.
    An engagement this pass did not touch is read, not run, so the page
    can be regenerated as often as anyone likes.
    """
    ran = {run.engagement.path: run for run in passed}
    return RunReport(
        today=today or dt.date.today(),
        runs=[ran[engagement.path] if engagement.path in ran else _engagement_status(engagement)
              for engagement in registry.engagements],
        misfits=list(registry.misfits),
    )


# --------------------------------------------------------------------- CLI ----

def main(argv: list[str] | None = None) -> int:
    """The command line, as a function: ``python -m tracker.runner`` and the
    packaged executable in runner mode (``api_entry.py``) both call this.
    Returns the exit code - non-zero if any engagement failed, so the
    scheduler shows a red run."""
    import argparse

    # The report names client files, and the scheduler's console is not
    # UTF-8: a name it cannot encode must not turn a finished run into a
    # traceback after every original has been moved (the tenth reading).
    # The guard is the page's (decision 108): one home, every command line.
    tolerant_console()

    parser = argparse.ArgumentParser(
        prog="python -m tracker.runner",
        description=f"File, scan and (on {DRAFT_DAY_NAME}s) draft reminders for every "
                    "engagement found under the clients folder. Never sends anything."
    )
    parser.add_argument("root", nargs="?", default="",
                        help="the folder the firm keeps its clients in (default: the one in the "
                             "settings file)")
    parser.add_argument(SETTINGS_FLAG, default="", metavar="FOLDER",
                        help="the app's settings folder, whose settings file names the clients root "
                             "(what the scheduled job passes)")
    parser.add_argument("--only", default="",
                        help="just the engagements matching this text")
    parser.add_argument("--dry-run", action="store_true",
                        help="decide everything, write and move nothing")
    parser.add_argument("--reminders", choices=REMINDER_MODES, default=REMINDERS_AUTO,
                        help=f"auto: {DRAFT_DAY_NAME}s only (default); always: today too; "
                             "never: file and scan only")
    parser.add_argument("--weekday", default="", choices=("",) + WEEKDAY_NAMES,
                        help=f"draft on this day instead of {DRAFT_DAY_NAME}")
    parser.add_argument(DATE_FLAG, default="",
                        help=f"pretend today is this {ISO_DATE_HINT} (for testing a schedule)")
    parser.add_argument(LOG_FLAG, nargs="?", const=LOG_FILENAME, default="",
                        help=f"append the run summary to a log (default: {LOG_FILENAME})")
    ns = parser.parse_args(argv)

    # The clients root has one home (decision 131): the scheduled job names
    # the app's settings folder, and this process reads everything the app
    # reads from there - the root and the store beside it - before anything
    # reads settings at all. A root on the command line still wins: a
    # person running one folder by hand.
    if ns.settings:
        os.environ[ENV_SETTINGS_DIR] = ns.settings
    root = ns.root
    if not root:
        try:
            configured = clients_root()
        except SettingsError as exc:
            raise SystemExit(f"Clients folder problem: {exc}") from None
        if configured is None:
            raise SystemExit(f"no clients root given and none in {settings_path()}; {NO_ROOT_HINT}")
        root = str(configured)
    elif ns.log:
        _refuse_an_old_jobs_root(root)

    try:
        loaded = discover_engagements(root)
    except RegistryError as exc:
        raise SystemExit(f"Clients folder problem: {exc}") from None

    when = dt.date.today()
    if ns.date:
        try:
            when = dt.date.fromisoformat(ns.date)
        except ValueError:
            parser.error(f"{DATE_FLAG} must be {ISO_DATE_HINT}, got {ns.date!r}")

    day = WEEKDAY_NAMES.index(ns.weekday) if ns.weekday else DRAFT_WEEKDAY

    if ns.only and not loaded.find(ns.only):
        raise SystemExit(f"Nothing in {loaded.source} matches {ns.only!r}")

    # OCR's temporary page images go to the app's own folder for the
    # pass, which is emptied first (decision 137, L7): a pass the scheduler
    # killed mid-page leaves a client's page there, not in %TEMP%.
    with ocr_scratch(settings_dir() / OCR_SCRATCH_DIR_NAME):
        result = run_registry(loaded, today=when, dry_run=ns.dry_run,
                              reminders=ns.reminders, weekday=day, only=ns.only)
    print(format_report(result))

    if ns.log:
        log_path = Path(ns.log)
        if not log_path.is_absolute() and ns.log == LOG_FILENAME:
            log_path = loaded.source / LOG_FILENAME
        append_log(log_path, result)
        print(f"\n  Logged to {log_path}")

    if not ns.dry_run:
        # Every real pass, whether or not it was asked to log, and whether
        # or not an engagement failed: the page is how a person finds out
        # that one did. A dry run writes nothing, this included.
        try:
            page = write_status_page(loaded.source, status_report(loaded, passed=result.runs))
        except Exception as exc:
            # The page is a courtesy; the pass is the job. Every original has
            # already been moved and every status written by the time we get
            # here, so nothing about drawing a page may end this in a
            # traceback - it is said in the log and the run stands.
            log.warning("Could not write %s (%s)", STATUS_PAGE_FILENAME, exc)
        else:
            print(f"\n  The practice: {page}")

    # Checkpoint the store's write-ahead log and take its two side files
    # with it: a scheduled pass leaves the app's folder as it found it.
    store.close()
    return 1 if result.errors else 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
