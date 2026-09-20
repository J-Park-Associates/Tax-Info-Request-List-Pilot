"""The unattended run across every engagement in the registry (component 10).

One command does a full pass — file the drop folder, scan, and on the draft day
draft the week's chase email — for every engagement found under the firm's
clients folder:

    python -m tracker.runner <clients root>

That is the whole scheduled task. There is nothing to register: a folder
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

One engagement's failure never stops the others. An unreadable record, a
scan already running, a drop that would not sort — each is recorded against
that engagement and the run moves on, because one client's problem must not
be the reason nine other clients went unprocessed. The command exits non-zero
if anything failed, so the scheduler shows a red run instead of a silent one.
"""

from __future__ import annotations

import datetime as dt
import logging
import traceback
from collections.abc import Iterable
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from tracker import store
from tracker.filer import NEEDS_REVIEW, ensure, file_drops, read_index
from tracker.ledger import LedgerError
from tracker.locking import engagement_lock
from tracker.manifest import (
    ISO_DATE_HINT,
    ManifestError,
    check_rules,
    load_manifest,
    summarize,
    write_text_atomically,
)
from tracker.page import esc, page_text, table, tolerant_console
from tracker.records import ENGAGEMENT_LABELS, NO, YES
from tracker.registry import (
    SKIP_ROLLED_FORWARD,
    Engagement,
    Registry,
    RegistryError,
    discover_engagements,
)
from tracker.reminder import (
    DRAFT_FILENAME,
    NEW_DRAFT_FILENAME,
    DraftsEditedError,
    ReminderError,
    draft_reminder,
    is_unedited,
    write_draft,
)
from tracker.scaffold import scaffold_engagement
from tracker.scanner import ScanLockedError, scan_engagement
from tracker.settings import SettingsError, firm, product_name
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
#: How the packaged app's one executable (api_entry.py) is told to be the
#: scheduled job rather than the API: this flag first, then the runner's own
#: arguments. tracker.scheduling builds the packaged command line from it.
RUNNER_MODE_FLAG = "--run"
#: What the run says about an engagement it drafted nothing for.
NOTHING_OUTSTANDING = "nothing outstanding; no reminder needed"
#: Why an engagement is passed over, and why one cannot be run at all -
#: worded once, because the pass and the status page must agree about the
#: same engagement.
SKIP_INACTIVE = f"inactive (the engagement's details say {ENGAGEMENT_LABELS['active']}: {NO})"
RECORD_UNREADABLE = "the record could not be read: {problem}"
#: What a pass says about a view whose replace did not land. Not an error:
#: the view carries no fact, so the old one standing costs a person one pass.
VIEW_NOT_REGENERATED = "status report open (not regenerated)"


@dataclass(slots=True)
class EngagementRun:
    """What one engagement's pass did, including how it went wrong."""

    engagement: Engagement
    filed: int = 0
    review: int = 0
    waiting: int = 0
    file_errors: list[str] = field(default_factory=list)  # drops that went wrong
    warnings: list[str] = field(default_factory=list)     # rows the rules cannot act on; strays in Prepared/
    #: The view was not regenerated because somebody had it open. Not a
    #: failure: it holds no fact of its own, so it simply stays one pass
    #: behind until the next pass lands one.
    view_stale: bool = False
    statuses: dict[str, int] = field(default_factory=dict)
    outstanding: int = 0             # from tracker.manifest.summarize, the one count
    drafted: Path | None = None
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
        return f"OK      {self.engagement.label}: {', '.join(parts)}"


@dataclass(slots=True)
class RunReport:
    """One pass over the whole registry."""

    today: dt.date
    dry_run: bool = False
    reminders: str = REMINDERS_AUTO
    runs: list[EngagementRun] = field(default_factory=list)

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
    """The day this engagement's reminder was last drafted, from the draft
    files themselves; None if it never was."""
    stamps = []
    for name in (DRAFT_FILENAME, NEW_DRAFT_FILENAME):
        try:
            stamps.append(dt.date.fromtimestamp((engagement_dir / name).stat().st_mtime))
        except OSError:
            continue
    return max(stamps) if stamps else None


def should_draft(
    engagement: Engagement,
    today: dt.date,
    mode: str = REMINDERS_AUTO,
    weekday: int = DRAFT_WEEKDAY,
    *,
    drafted: dt.date | None = None,
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
    up mid-week is not chased the same afternoon.
    """
    if not engagement.reminders or mode == REMINDERS_NEVER:
        return False
    if mode == REMINDERS_ALWAYS:
        return True
    if is_draft_day(today, weekday):
        return True
    return drafted is not None and drafted < last_draft_day(today, weekday)


# --------------------------------------------------------------- one pass ----


def run_engagement(
    engagement: Engagement,
    *,
    root: Path | None = None,
    today: dt.date | None = None,
    dry_run: bool = False,
    reminders: str = REMINDERS_AUTO,
    weekday: int = DRAFT_WEEKDAY,
) -> EngagementRun:
    """File, scan and (on the draft day) draft for one engagement.

    Never raises for an engagement-level problem: anything that goes wrong is
    recorded on the returned :class:`EngagementRun` so the caller can keep
    going through the rest of the registry.
    """
    today = today or dt.date.today()
    # Stamped before anything is touched, so an engagement that fails its
    # pre-checks still says when it was last looked at.
    run = EngagementRun(engagement=engagement, last_pass=dt.datetime.now())
    if not _worth_a_pass(run):
        return run

    try:
        # **One lock, across the whole pass** (decision 102). The filer and
        # the scanner used to take the engagement's lock one after the
        # other, which left a gap between them that a click in the app
        # could step into: the sort's rows landed, another run filed
        # something, and the scan then read a folder neither of them had
        # decided from. What a pass decides from must not change under it,
        # and that is one section, not two. Each step is told the lock is
        # already held so it does not try to take it again. A dry run takes
        # none: it writes nothing and must never block a real run.
        with nullcontext() if dry_run else engagement_lock(engagement.path):
            # **The store is brought up to the record first.** Everything
            # below answers from it; a rules edit a person saved since the
            # last pass is already in the journal (decision 104).
            ensure(engagement.path, root)
            # A row added or un-waived in the app gets its folder and its
            # README line here, on the next pass, rather than when somebody
            # remembers to re-run scaffold. Idempotent: nothing existing is
            # touched.
            if not dry_run:
                scaffold_engagement(engagement.path)   # contact line from the details
            filed = file_drops(engagement.path, today=today, dry_run=dry_run,
                               lock_held=not dry_run)
            run.filed = len(filed.filed)
            run.review = len(filed.review)
            run.waiting = len(filed.waiting)
            run.file_errors = [f"{e.name}: {e.error}" for e in filed.errors]
            # An original already sorted whose record no longer fits the disk
            # is for a person to look at, every pass - but nothing was left
            # unsorted, so it rides the warnings rather than failing the run.
            run.warnings.extend(f"{e.name}: {e.error}" for e in filed.attention)

            scanned = scan_engagement(engagement.path, root=root, today=today, dry_run=dry_run,
                                      lock_held=not dry_run)
            summary = scanned.summary
            run.statuses = summary.counts
            run.outstanding = summary.outstanding
            run.warnings.extend(scanned.warnings)

            if should_draft(engagement, today, reminders, weekday,
                            drafted=last_drafted(engagement.path)):
                _draft_step(run, dry_run=dry_run)
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

    if run.file_errors and not run.error:
        # The rest of the pass went ahead, but a drop that could not be
        # sorted is a failure the scheduler must show, not a footnote.
        run.error = (
            f"{len(run.file_errors)} file(s) could not be sorted "
            f"(filed {run.filed}, review {run.review}): "
            + "; ".join(run.file_errors[:3])
        )
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
        run.warnings = check_rules(load_manifest(engagement.path))
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


def _draft_step(run: EngagementRun, *, dry_run: bool) -> None:
    """Draft the reminder for a pass that has decided today is the day. Never sends."""
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
    draft = draft_reminder(engagement.path)   # reads the engagement's details itself
    if not draft.has_outstanding:
        run.draft_note = NOTHING_OUTSTANDING
        _refresh_stale_draft(draft, engagement.path)
        return

    try:
        written = write_draft(draft, engagement_dir=engagement.path, preserve_edits=True)
    except DraftsEditedError as exc:
        run.draft_note = str(exc)
        return
    run.drafted = written
    if written.name == NEW_DRAFT_FILENAME:
        run.draft_note = (
            f"{DRAFT_FILENAME} has been edited, so this week's draft was "
            f"written to {NEW_DRAFT_FILENAME} instead"
        )


def _refresh_stale_draft(draft, engagement_dir: Path) -> None:
    """Nothing is outstanding, and a draft from a week that had something to
    chase is still there. The run's own unedited draft is rewritten as what
    the run would say today - the same text ``python -m tracker.reminder``
    writes - so it is neither stale nor dated as if untouched; one a person
    has edited is theirs and is left exactly as it is. With the file
    current, ``last_drafted`` reads this draft day and no weekday pass
    mistakes the quiet week for a missed one.
    """
    for name in (DRAFT_FILENAME, NEW_DRAFT_FILENAME):
        path = engagement_dir / name
        if not path.is_file() or not is_unedited(path):
            continue
        try:
            write_draft(draft, path=path)
        except OSError as exc:    # open in Word, or a sync client mid-upload: next time
            log.warning("Could not refresh %s (%s)", path.name, exc)


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
    """Run every engagement in the registry, in the order it lists them."""
    if reminders not in REMINDER_MODES:
        raise ValueError(
            f"reminders must be one of {', '.join(REMINDER_MODES)}, got {reminders!r}"
        )
    today = today or dt.date.today()
    selected = registry.find(only) if only else registry.engagements

    report = RunReport(today=today, dry_run=dry_run, reminders=reminders)
    report.runs = [
        run_engagement(engagement, root=registry.source, today=today, dry_run=dry_run,
                       reminders=reminders, weekday=weekday)
        for engagement in selected
    ]
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
        f"{report.outstanding} request(s) outstanding",
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
    lines += [f"    {run.summary()}" for run in report.runs]
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
#: What the last-pass cell says for an engagement the page read rather than ran.
STATUS_NOT_PASSED = "not this pass"
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
        YES if run.drafted else "",
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
    parser.add_argument("root", help="the folder the firm keeps its clients in")
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

    try:
        loaded = discover_engagements(ns.root)
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
