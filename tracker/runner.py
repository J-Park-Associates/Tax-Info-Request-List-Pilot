"""The unattended run across every engagement in the registry (component 10).

One command does a full pass — file the drop folder, scan, and on the draft day
draft the week's chase email — for every engagement found under the firm's
clients folder:

    python -m tracker.runner <clients root>

That is the whole scheduled task. There is nothing to register: a folder
holding ``MANIFEST_FILENAME`` is an engagement, and the manifest's Engagement
sheet says who the client is and how they are chased. Creating an engagement
in the desktop app is all it takes for the nightly run to pick it up.

**Drafting is weekly, on ``DRAFT_WEEKDAY``.** A reminder that lands in the accountant's
lap every night is noise that gets ignored; one a week, waiting over the weekend
for a start-of-week send, is a thing someone actually reads. The filing and scanning
steps still run on whatever schedule the task is set to — only the drafting
step looks at the day. ``--reminders always`` forces a draft on any day and
``--reminders never`` suppresses it, so the schedule is a default, not a cage.

**Nothing is ever sent.** The draft step writes ``DRAFT_FILENAME`` into
the engagement folder and stops there. A person opens it, edits it and sends
it. An engagement whose Engagement sheet says ``Reminders`` set to ``NO`` is left out of
the automated draft entirely — that is a standing decision about that client,
and neither the schedule nor ``--reminders always`` overrides it. Drafting one by hand for
anybody, any time, is still just:

    python -m tracker.reminder <engagement_dir> --write

**A draft you have edited is never overwritten.** The weekly run recognizes
its own unedited output by the fingerprint in the header; anything else it
leaves alone and writes ``NEW_DRAFT_FILENAME`` beside it instead.

One engagement's failure never stops the others. An unreadable manifest, a
scan already running, a drop that would not sort — each is recorded against
that engagement and the run moves on, because one client's problem must not
be the reason nine other clients went unprocessed. The command exits non-zero
if anything failed, so the scheduler shows a red run instead of a silent one.
"""

from __future__ import annotations

import datetime as dt
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from tracker.filer import file_drops
from tracker.manifest import (
    ENGAGEMENT_LABELS,
    ENGAGEMENT_SHEET_NAME,
    ISO_DATE_HINT,
    NO,
    ManifestError,
    check_manifest,
)
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
    ReminderError,
    draft_reminder,
    write_draft,
)
from tracker.scaffold import MANIFEST_FILENAME, scaffold_engagement
from tracker.scanner import ScanLockedError, scan_engagement

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


@dataclass(slots=True)
class EngagementRun:
    """What one engagement's pass did, including how it went wrong."""

    engagement: Engagement
    filed: int = 0
    review: int = 0
    waiting: int = 0
    file_errors: list[str] = field(default_factory=list)  # drops that went wrong
    warnings: list[str] = field(default_factory=list)     # rows the rules cannot act on; strays in Prepared/
    index_deferred: bool = False     # the index was locked; rows in the sidecar
    manifest_deferred: bool = False  # the manifest was locked; statuses in the sidecar
    statuses: dict[str, int] = field(default_factory=dict)
    outstanding: int = 0             # from tracker.manifest.summarize, the one count
    drafted: Path | None = None
    draft_note: str = ""      # why there is no draft, when there is a reason
    skipped: str = ""         # why the whole engagement was passed over
    error: str = ""           # what went wrong, if anything did

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
        if self.index_deferred:
            parts.append("index locked (rows deferred)")
        if self.manifest_deferred:
            parts.append("manifest locked (statuses deferred)")
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


def should_draft(
    engagement: Engagement,
    today: dt.date,
    mode: str = REMINDERS_AUTO,
    weekday: int = DRAFT_WEEKDAY,
) -> bool:
    """Whether the automated run drafts a reminder for this engagement today.

    ``Reminders`` set to ``NO`` on the manifest's Engagement sheet wins over every
    mode. It is a standing decision that this client is not chased by email,
    and a command line flag is not the place to reverse it —
    ``python -m tracker.reminder`` still drafts one on demand for anybody.
    """
    if not engagement.reminders or mode == REMINDERS_NEVER:
        return False
    if mode == REMINDERS_ALWAYS:
        return True
    return is_draft_day(today, weekday)


# --------------------------------------------------------------- one pass ----


def run_engagement(
    engagement: Engagement,
    *,
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
    run = EngagementRun(engagement=engagement)

    if engagement.superseded_by:
        run.skipped = SKIP_ROLLED_FORWARD.format(successor=engagement.superseded_by)
        return run
    if not engagement.active:
        run.skipped = f"inactive ({ENGAGEMENT_SHEET_NAME} sheet says {ENGAGEMENT_LABELS['active']}: {NO})"
        return run
    if not engagement.path.is_dir():
        run.error = f"folder not found: {engagement.path}"
        return run
    if engagement.problem:
        run.error = f"manifest could not be read: {engagement.problem}"
        return run

    # The same check the app's button runs: a typo made in Excel is named
    # with its row before a single file is touched, and rows the rules
    # cannot act on are carried into the report rather than left to be
    # noticed at a deadline.
    checked = check_manifest(engagement.path / MANIFEST_FILENAME)
    if not checked.ok:
        run.error = "; ".join(checked.problems)
        return run
    run.warnings = checked.warnings

    try:
        # A row added or un-waived in Excel gets its folder and its README
        # line here, on the next pass, rather than when somebody remembers
        # to re-run scaffold. Idempotent: nothing existing is touched.
        if not dry_run:
            scaffold_engagement(engagement.path)   # contact line from the Engagement sheet
        filed = file_drops(engagement.path, today=today, dry_run=dry_run)
        run.filed = len(filed.filed)
        run.review = len(filed.review)
        run.waiting = len(filed.waiting)
        run.file_errors = [f"{e.name}: {e.error}" for e in filed.errors]
        run.index_deferred = filed.index_deferred

        scanned = scan_engagement(engagement.path, today=today, dry_run=dry_run)
        summary = scanned.summary
        run.statuses = summary.counts
        run.outstanding = summary.outstanding
        run.warnings.extend(scanned.warnings)
        run.manifest_deferred = scanned.deferred

        if not should_draft(engagement, today, reminders, weekday):
            run.draft_note = _why_no_draft(engagement, today, reminders, weekday)
            return run

        # A dry run left the manifest unwritten, so there is nothing on disk
        # for the drafter to read. Report from the scan we just did in memory
        # rather than reading back statuses that were deliberately not saved.
        if dry_run:
            run.draft_note = (
                f"would draft {run.outstanding} item(s)" if run.outstanding
                else NOTHING_OUTSTANDING
            )
            return run

        draft = draft_reminder(engagement.path)   # reads the Engagement sheet itself
        if not draft.has_outstanding:
            run.draft_note = NOTHING_OUTSTANDING
            return run

        written = write_draft(draft, engagement_dir=engagement.path,
                              preserve_edits=True)
        run.drafted = written
        if written.name == NEW_DRAFT_FILENAME:
            run.draft_note = (
                f"{DRAFT_FILENAME} has been edited, so this week's draft was "
                f"written to {NEW_DRAFT_FILENAME} instead"
            )

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
        run_engagement(engagement, today=today, dry_run=dry_run,
                       reminders=reminders, weekday=weekday)
        for engagement in selected
    ]
    return report


# ------------------------------------------------------------------ output ----


def format_report(report: RunReport) -> str:
    """The console (and log) rendering of one pass."""
    mode = {
        REMINDERS_AUTO: ("drafting reminders" if is_draft_day(report.today)
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
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


# --------------------------------------------------------------------- CLI ----

def main(argv: list[str] | None = None) -> int:
    """The command line, as a function: ``python -m tracker.runner`` and the
    packaged executable in runner mode (``api_entry.py``) both call this.
    Returns the exit code - non-zero if any engagement failed, so the
    scheduler shows a red run."""
    import argparse

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

    return 1 if result.errors else 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
