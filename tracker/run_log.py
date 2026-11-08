"""What one pass reports: its records, the run log's codes, the run log, and
the last-pass file the app reads.

Each part upholds the decision rows it names:

- **The pass's report** (decisions 89, 115, 127, 189). :class:`EngagementRun`
  is what one return's pass did - what it filed, parked and drafted, why it
  was passed over or failed - and :class:`RunReport` is one pass over the
  whole registry: the runs, the folders the walk left alone, the pass's own
  warnings and the records that need a person. The console
  (``tracker.runner.format_report``), the practice page and the run log are
  each drawn from these records and never from a second look at the disk,
  so the three cannot disagree about one pass. :func:`why_skipped` is the
  one wording of why a return is passed over; the pass and the page both
  ask it.
- **Codes for the log, sentences for the page** (decision 186). Every
  return's trouble and every pass warning carries a code from the
  ``CODE_*`` table: a return's ``code`` is set wherever its ``error`` or
  ``skipped`` is, and a pass warning is added only through :func:`_warn`,
  which puts its code beside its sentence. The page and the console say
  the sentence, which can name a client; the run log says the code, which
  cannot.
- **The run log and its rotation** (decisions 186 and 189). :func:`append_log`
  adds one pass to :data:`LOG_FILENAME` in the data home (:func:`log_path`):
  its first line, the reader's note, a counts line (:func:`log_counts`) and
  a codes line (:func:`log_codes`) - numbers and codes, never a client's
  name. :func:`_log_a_failed_pass` writes the one line of a pass that
  stopped before it began. Both append through ``fsio.append_rotating``,
  which keeps at most :data:`LOG_KEEP` older files of :data:`LOG_MAX_BYTES`.
- **The last-pass file** (decision 159's E4; pilot P21, P256).
  :func:`write_last_pass` writes, all or nothing and beside the store
  (:func:`last_pass_path`), when the scheduled pass started and ended and
  how - a result and a reason's code from :data:`PASS_REASONS`.
  :func:`last_pass_line` is the app's one line about the schedule, amber
  after :func:`amber_hours`, read bounded and echoing nothing the file
  holds. The shell watches the file's folder and asks again when it
  changes (pilot P277); the API's ``list`` and ``last-pass`` replies read
  it through these, so a pass still running is never drawn as a failure
  (pilot P256).

**Why the records sit here** (SPEC-architecture-p5 P5.8 and its section
2.1, P345; the architecture audit's C-5). The run log, the practice page
and the pass order hint all read the report records, and each leaves the
runner in its own job (P5.8, P5.9, P5.10), so the records must sit below
all three: the first of them to move takes the records with it.
``tracker.runner.format_report`` stayed in the runner, because it reads the
draft-day rule (``is_draft_day``), which is the runner's (decision 12); so
did ``tracker.runner.PassFailed``, which only the runner raises and
catches, and ``tracker.runner.AFTER_INSTALL_FILENAME``, which
``tracker.runner.left_behind`` names. The runner imports back by name what
its own code still reads.

**Why it sits at layer 3.** It imports the registry's engagement and misfit
and the reminder's two approval words (layer 3, its own layer), the
reader's device name (``ocr``, layer 2), the store, the record types and the
ledger (layer 1), and the checkpoint, ``fsio``, ``errors`` and ``settings``
(layer 0). It imports neither ``scheduling`` nor the API (P313), nor the
runner, which imports it, nor :mod:`tracker.screen_words`: the scheduled
pass loads this module, and ``tests/test_layers.py`` keeps the product's
name, which that pass is not given (P220), out of everything it loads.

It logs as ``tracker.runner`` (``logging.getLogger("tracker.runner")``), the
name its lines have always carried: the error log prints each line's logger
name, so a new one would change lines a person reads (P331's rule;
SPEC-architecture-p5 section 2.1).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tracker import checkpoint, errors, ledger, ocr, store
from tracker.fsio import append_rotating, write_json_atomically
from tracker.records import ENGAGEMENT_LABELS, NO
from tracker.registry import SKIP_ROLLED_FORWARD, Engagement, Misfit
from tracker.reminder import APPROVED_NOTE, APPROVED_THEN_EDITED
from tracker.settings import ScheduleChoiceError, SettingsError, logs_dir, schedule_preference

log = logging.getLogger("tracker.runner")


#: When the run drafts reminders.
REMINDERS_AUTO = "auto"      # only on DRAFT_WEEKDAY — the scheduled default
REMINDERS_ALWAYS = "always"  # draft today, whatever day it is
REMINDERS_NEVER = "never"    # file and scan only
REMINDER_MODES = (REMINDERS_AUTO, REMINDERS_ALWAYS, REMINDERS_NEVER)

#: The run log, in the tracker's data home (decision 186): one entry per pass,
#: counts and codes, never a client's name. Rotated: LOG_MAX_BYTES, LOG_KEEP
#: old files (about a megabyte in all; at twelve passes a day plus the app's,
#: the better part of a year of entries).
LOG_FILENAME = "runs.log"
LOG_MAX_BYTES = 256 * 1024
LOG_KEEP = 3


def log_path() -> Path:
    """The run log: :data:`LOG_FILENAME` in the data home's logs folder
    (decision 186). Only a path; the writer makes the folder."""
    return logs_dir() / LOG_FILENAME


#: The scheduled pass says when it ran and how it ended (decision 159, E4):
#: a job that stops - settings unreadable, the root gone, the task deleted -
#: otherwise stops in silence, and the office finds out at a deadline. The
#: file sits beside the store, the same rule the record checkpoint follows,
#: so it moves with the store and never enters the clients tree. Only the
#: scheduled job's shape writes it (``--settings``, no root, not a dry
#: run): a pass run by hand must not make a stopped schedule look alive.
#:
#: **Beside decision 189's log and page, not instead of them.** 189 made
#: the run log and the practice page always written - but both live in the
#: clients root, so a pass that stops before it has a root (settings that
#: will not read, no root, a root refused or not this machine's) writes
#: neither, and the app, which shows neither, cannot say it. This file is
#: the one status of the pass the app reads, it says only when and how the
#: pass ended - by a code - and for everything else it points at the log
#: and the page, which say the rest; ``pass-order.json`` beside it is 189's
#: order hint per household, not a status of the pass.
LAST_PASS_FILENAME = "last-pass.json"
#: The app's line turns amber when the last scheduled pass started longer
#: ago than two missed runs of the saved interval, and never sooner than
#: this. The schedule repeats every two hours by default, so four hours is
#: one missed run and a margin.
LAST_PASS_AMBER_HOURS = 4
#: A schedule that runs once a day is amber after two days.
LAST_PASS_AMBER_HOURS_DAILY = 48
#: The file's ``result``: a pass that started and has not ended (or was
#: killed), one that ended cleanly, one that did not.
PASS_RUNNING = "running"
PASS_SUCCEEDED = "succeeded"
PASS_FAILED = "failed"
#: Why a pass failed, as a code (the file) and a sentence (the app). The
#: codes are the file's vocabulary, so a later reader matches on them and
#: never on words.
PASS_SETTINGS = "settings-unreadable"
PASS_NO_ROOT = "no-root"
PASS_ROOT_REFUSED = "root-refused"
PASS_ROOT_NOT_CLAIMED = "root-not-claimed"
PASS_ROOT_UNREADABLE = "root-unreadable"
#: On a Mac, macOS refused the schedule's own program the clients folder
#: (SPEC-mac R30): its Files and Folders permission for Google Drive is
#: granted to the program asking, which for the pass launchd starts is the
#: API itself, not the app. Its own code, because "could not be walked" sends
#: a person to the folder and this one sends them to the permission prompt.
PASS_ROOT_NOT_PERMITTED = "root-not-permitted"
PASS_RETURN_ERRORS = "return-errors"
PASS_NOT_SERVED = "not-served-twice"
#: This machine's record checkpoint could not be asked whether the root is
#: its own (the rebase review's MF1 and SF1): busy, or unreadable. Each its
#: own code and sentence - never "not the root", which sends a person to
#: move-root.
PASS_CHECKPOINT_BUSY = "checkpoint-busy"
PASS_CHECKPOINT_UNREADABLE = "checkpoint-unreadable"
#: The checkpoint an earlier version kept still sits beside the program, and
#: a fresh one is refused until it is moved (the rebase review of 186, MF1).
PASS_CHECKPOINT_LEFT_BEHIND = "checkpoint-left-behind"
PASS_ENDED_EARLY = "stopped"
PASS_REASONS = {
    PASS_SETTINGS: "the settings file could not be read",
    PASS_NO_ROOT: "no clients folder is set",
    PASS_ROOT_REFUSED: "the clients folder was refused",
    PASS_ROOT_NOT_CLAIMED: "the clients folder is not the one this machine's record checkpoint belongs to",
    PASS_ROOT_UNREADABLE: "the clients folder could not be walked",
    PASS_ROOT_NOT_PERMITTED: ("macOS did not let the schedule read the clients folder; open the app, and "
                              "allow it when macOS asks (runbook, 'On a Mac')"),
    PASS_RETURN_ERRORS: ("the pass ended with a problem - a return that failed, or a log or page it "
                         "could not write; the practice page and runs.log say which"),
    PASS_NOT_SERVED: ("a household has not been served two passes running; the practice page says "
                      "which and why"),
    PASS_ENDED_EARLY: "the pass stopped with an error before it began; runs.log names its kind",
    PASS_CHECKPOINT_BUSY: ("this machine's record checkpoint was busy - another run was using it; "
                           "no household was served, and the next pass tries again"),
    PASS_CHECKPOINT_UNREADABLE: ("this machine's record checkpoint could not be read; no household "
                                 "was served - the practice page says what to do (runbook §6)"),
    PASS_CHECKPOINT_LEFT_BEHIND: ("the record checkpoint an earlier version kept is still beside the "
                                  "program; no household was served until it is moved into the data "
                                  "folder (the runbook's decision-186 upgrade step)"),
}
LAST_PASS_LINE = "Last scheduled pass: {when}, {result}."
LAST_PASS_FAILED_LINE = "Last scheduled pass: {when}, failed ({reason})."
LAST_PASS_RUNNING_LINE = "Last scheduled pass: started {when}, not finished."
#: ``{hours}`` is the wait the line assumed, from the saved interval.
LAST_PASS_OLD = (" Nothing newer for over {hours} hours: check that the schedule "
                 "is still installed on the office machine (runbook, 'The last-pass line').")
LAST_PASS_NEVER = ("No scheduled pass has run on this machine yet. If the schedule is installed "
                   "here, one will run at its next scheduled time.")
LAST_PASS_OFF = "The schedule is off on this computer, so no pass runs by itself. Scan still works."
LAST_PASS_UNREADABLE = "The last scheduled pass could not be read ({error})."
#: How the app colours the line: the API says it, the page only draws it.
LEVEL_OK, LEVEL_WARN, LEVEL_ERR = "ok", "warn", "err"


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
#: What a pass says about a view whose replace did not land. Not an error:
#: the view carries no fact, so the old one standing costs a person one pass.
VIEW_NOT_REGENERATED = "status report open (not regenerated)"
#: The household's system and temporary files the sort left alone by name
#: (decision 190): one line per household per pass, in the run's own line
#: and on the practice page. A count and never a name - a person who
#: expected a file to be sorted sees that something was left and looks.
IGNORED_NOTE = "{n} system or temporary files in the inbox were left alone"
#: When a reading is slow enough to be worth saying (decision 127). A
#: scanned page costs about a second to read on the office machine, so
#: twenty seconds is a document doing something unusual - a long scan, a
#: photo of a whole desk, a page the four-way scorer had to read four
#: times. **Nothing is cut short at this number**: it decides only whether
#: the run's line mentions the document. Photos and scans are the readings
#: the owner's speed ceiling will be measured against, and a pass that
#: quietly abandoned the slow ones could not measure them. The one stop is
#: the reader's safety stop (``content_check.READING_STOP_*``), ten times that
#: ceiling (decision 137, B1.2).
SLOW_READING_SECONDS = 20.0
SLOW_READING_NOTE = "slow reading: {name} took {seconds:.0f} s"


#: The largest last-pass file read (:func:`last_pass_line`): what the hint's
#: cap was before P217 raised it; a last-pass file is one short object.
LAST_PASS_MAX_BYTES = 64 * 1024


#: The run log's codes: classes, never a message (decision 186; Solution 6
#: extends it). Each is the name of the sentence constant it stands for, in
#: lower kebab case, so the log and the code can be read against each other;
#: a return's failure that is an exception is ``crashed:<class>``, or
#: ``refused:<class>`` for the request list's and the reminder's own
#: refusals. A return's code is set wherever its ``error`` or ``skipped``
#: is; a pass warning's goes with it through :func:`_warn`.
CODE_NO_PRACTICE = "no-practice"
CODE_HOUSEHOLD_STOPPED = "household-stopped"
CODE_HOUSEHOLD_PAUSED = "household-paused"
CODE_CLIENT_FOLDER_MISSING = "client-folder-missing"
CODE_LOCK_HELD = "lock-held"
CODE_CRASHED = "crashed:{kind}"
CODE_REFUSED = "refused:{kind}"
CODE_UNSORTED_FILES = "unsorted-files"
CODE_NO_ROOM = "no-room"
CODE_ROLLED_FORWARD = "rolled-forward"
CODE_INACTIVE = "inactive"
CODE_FOLDER_MISSING = "folder-missing"
CODE_RECORD_UNREADABLE = "record-unreadable"
#: The pass's own warnings, one code per sentence.
CODE_LEFT_BEHIND = "left-behind"
CODE_LEFT_BEHIND_TO_MOVE = "left-behind-to-move"
CODE_NO_DATA_HOME = "no-data-home"
CODE_READER_PATH_WARNING = "reader-path-warning"
CODE_GRAPHICS_CARD_FAULT = "graphics-card-fault"
CODE_READER_COULD_NOT_START = "reader-could-not-start"
CODE_ORDER_HINT_UNREADABLE = "order-hint-unreadable"
CODE_NOT_SERVED_TWICE = "not-served-twice"
CODE_PASS_STOPPED = "pass-stopped"
CODE_PASS_APP_CLOSED = "pass-app-closed"
CODE_PASS_RUN_LIMIT = "pass-run-limit"
CODE_PASS_DID_NOT_FINISH = "pass-did-not-finish"
CODE_LOG_NOT_WRITTEN = "log-not-written"
CODE_PAGE_NOT_WRITTEN = "page-not-written"
CODE_CHECKPOINT_NOT_PROVED = "checkpoint-not-proved"
CODE_CACHE_NOT_FILLED = "cache-not-filled"


@dataclass(slots=True)
class EngagementRun:
    """What one engagement's pass did, including how it went wrong."""

    engagement: Engagement
    filed: int = 0
    review: int = 0
    #: Emails and zips this pass opened (decision 143); what came out of
    #: each is counted in ``filed`` and ``review`` like any drop.
    opened: int = 0
    waiting: int = 0
    #: The household's files left alone as system or temporary by name
    #: (decision 190), counted on its first return's run only.
    ignored: int = 0
    file_errors: list[str] = field(default_factory=list)  # drops that went wrong
    warnings: list[str] = field(default_factory=list)     # rows the rules cannot act on; strays in Prepared/
    #: The request list :func:`tracker.runner._worth_a_pass` loaded for ``check_rules``,
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
    #: Whether a person approved this week's draft and then edited it
    #: (decision 190): the approval no longer covers the file, and the log
    #: and the page say "approved, then edited" rather than "approved".
    approval_lapsed: bool = False
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
    #: Skipped because another run held a lock this household needed
    #: (decision 189): a typed flag, not the text of ``skipped``, so the
    #: pass can try the household once more at its end.
    locked_out: bool = False
    #: The household's time for this pass ran out (decision 189).
    out_of_time: bool = False
    #: A person stopped the pass before this household's work was done
    #: (decision 193): what was done is recorded, the rest waits.
    cancelled: bool = False
    #: The pass ended itself at the run limit before this household's work was
    #: done (SPEC-mac R26): a stop like a person's, but nobody's, so it is not
    #: ``cancelled`` and the run log does not count it as one.
    run_limit: bool = False
    #: The return whose lock a take met, when ``locked_out`` (decision
    #: 193): the app's notice says who holds it and since when.
    locked_at: Path | None = None
    #: When this engagement was passed over. None on a row the status page
    #: read rather than ran, so the page never dates a pass that never was.
    last_pass: dt.datetime | None = None
    #: The class of ``error`` or ``skipped`` (a ``CODE_*``), set with it:
    #: what the run log says, never the sentence (decision 186).
    code: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    def summary(self) -> str:
        if self.error:
            return f"ERROR   {self.engagement.label}: {self.error}"
        if self.skipped:
            return f"SKIP    {self.engagement.label}: {self.skipped}"
        parts = [f"filed {self.filed}"]
        if self.opened:
            parts.append(f"opened {self.opened}")
        if self.review:
            parts.append(f"review {self.review}")
        if self.waiting:
            parts.append(f"syncing {self.waiting}")
        if self.ignored:
            parts.append(IGNORED_NOTE.format(n=self.ignored))
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
        elif self.approval_lapsed:
            parts.append(APPROVED_THEN_EDITED)
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
    #: What the pass says once, about the pass rather than one return: a
    #: reader that could not start on this machine (decision 150), the
    #: graphics card failing mid-pass (decision 169).
    warnings: list[str] = field(default_factory=list)
    #: Which device the reader used this pass (decision 169): the pass's
    #: summary line in the run log says it, ``reader=processor`` or
    #: ``reader=graphics card``.
    reader: str = ocr.DEVICE_PROCESSOR
    #: The one run-log line when the graphics card pack is there and could
    #: not be used (``ocr.PACK_UNUSABLE``), or "". Not a pass warning.
    reader_note: str = ""
    #: The households not served for the second pass running or more
    #: (decision 189): the pass exits :data:`tracker.runner.NOT_SERVED_TWICE_EXIT_CODE`.
    not_served_twice: list[str] = field(default_factory=list)
    #: Records that need a person (decision 159, A-8 / G-5): every copy a
    #: sync client left beside a record or its lock (``ledger.siblings``),
    #: never deleted by anything, and every line written on another machine
    #: that no person has acknowledged. Named every pass until a person acts.
    siblings: list[Path] = field(default_factory=list)
    foreign: list[checkpoint.Foreign] = field(default_factory=list)
    #: What could not be asked of this machine's record checkpoint this pass
    #: (the rebase review's MF1 and SF3), drawn first in the page's records
    #: section: never a list dropped in silence (UX 4).
    unread: list[str] = field(default_factory=list)

    #: One code for each of ``warnings``, in step (decision 186): what the
    #: run log says of them. Filled only through :func:`_warn`.
    warning_codes: list[str] = field(default_factory=list)

    @property
    def refused(self) -> list[EngagementRun]:
        """The returns whose record was refused as altered or out of place
        (decision 159): each such sentence ends with ``ledger.RUN_RECOVER``."""
        return [r for r in self.runs if r.error and ledger.RUN_RECOVER in r.error]

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


def _warn(report: RunReport, code: str, sentence: str) -> None:
    """Say ``sentence`` once for the pass, with its ``code`` beside it: the
    page and the console read the sentence, the run log the code. The one
    way a pass warning is added, so none goes unlogged (decision 186)."""
    report.warnings.append(sentence)
    report.warning_codes.append(code)


def why_skipped(engagement: Engagement) -> tuple[str, str]:
    """Why this engagement is passed over, as (code, sentence), or
    ("", "") if it is not.

    The pass and the status page ask the same question of the same
    engagement, so they ask it in one place: a prior year its successor
    retired, and a client the details say is finished with, are neither
    failures nor work outstanding, and neither should read as one. The
    code is what the run log says (decision 186); the sentence names the
    successor, a client's return, so only the page and the console say it.
    """
    if engagement.superseded_by:
        return CODE_ROLLED_FORWARD, SKIP_ROLLED_FORWARD.format(successor=engagement.superseded_by)
    if not engagement.active:
        return CODE_INACTIVE, SKIP_INACTIVE
    return "", ""


def log_counts(report: RunReport) -> dict[str, int]:
    """The run log's counts for one pass, in the order the line says them:
    numbers only (decision 186)."""
    runs = report.runs
    return {
        "returns": len(runs),
        "ok": len(report.processed),
        "skipped": sum(1 for run in runs if run.skipped and not run.error),
        "failed": len(report.errors),
        "filed": sum(run.filed for run in runs),
        "opened": sum(run.opened for run in runs),
        "review": sum(run.review for run in runs),
        "syncing": sum(run.waiting for run in runs),
        "unsorted": sum(len(run.file_errors) for run in runs),
        "drafted": len(report.drafted),
        "held": len(report.held),
        "outstanding": report.outstanding,
        # Decision 189's own: the returns whose household's time ran out,
        # and the households not served two passes running.
        "out_of_time": sum(1 for run in runs if run.out_of_time),
        # Decision 193's: the returns a person stopped from the app.
        "cancelled": sum(1 for run in runs if run.cancelled),
        "not_served_twice": len(report.not_served_twice),
        "misfits": len(report.misfits),
        "warnings": sum(len(run.warnings) for run in runs) + len(report.warnings),
        # Decision 159's records that need a person, counted: the practice
        # page names each; the log never does.
        "record_copies": len(report.siblings),
        "foreign_lines": len(report.foreign),
        "refused_records": len(report.refused),
        "checkpoint_unread": len(report.unread),
    }


def log_codes(report: RunReport) -> dict[str, int]:
    """Every return's code and every pass warning's, counted, by code."""
    codes = [run.code for run in report.runs if run.code] + list(report.warning_codes)
    return {code: codes.count(code) for code in sorted(set(codes))}


def append_log(path: Path | str, report: RunReport) -> Path:
    """Append this pass to the run log, so an unattended failure leaves a
    trace: its first line (when, the reminder mode, dry run, which reader),
    the reader's note when there is one, a counts line and - when anything
    went wrong - a codes line.

    A name is never quoted into the run log (security principle 7): which
    client is always read on the status page. The log carries **no
    client-derived text** - no label, no file name, no draft's name, no
    slow reading's name and no household's error - only :func:`log_counts`
    and :func:`log_codes` (decision 186). **The one exception is the
    reader's note**, kept verbatim, and it can hold an exception's text
    (``ocr.PACK_UNUSABLE``'s reason, a reading child's error): a machine
    path, a provider's message, the account's profile folder. It is the
    machine's own, never a document's - the warm-up reads a drawn page and
    building the engine reads no document (decision 186's review, S4).
    Appended through ``fsio.append_rotating``, so the log keeps at most
    :data:`LOG_KEEP` older files of :data:`LOG_MAX_BYTES`.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"[{stamp}] {report.today.isoformat()} "
             f"reminders={report.reminders} dry_run={report.dry_run} reader={report.reader}"]
    if report.reader_note:
        # The graphics card pack is here and could not be used (decision
        # 169): the machine's to look at, said once, and not a warning.
        lines.append(f"    {report.reader_note}")
    lines.append("    counts " + " ".join(f"{key}={value}" for key, value in log_counts(report).items()))
    if codes := log_codes(report):
        lines.append("    codes " + " ".join(f"{code}={n}" for code, n in codes.items()))
    return append_rotating(path, "\n".join(lines) + "\n", max_bytes=LOG_MAX_BYTES, keep=LOG_KEEP)


def last_pass_path() -> Path:
    """Where this machine's last-pass file is: beside the store, the same
    rule as the record checkpoint, so it is right wherever the store is."""
    return Path(store.store_path()).with_name(LAST_PASS_FILENAME)


def _this_build() -> str:
    """The program that ran: the packaged executable, or this source tree."""
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve())
    return str(Path(__file__).resolve().parent.parent)


def write_last_pass(path: Path, *, started: dt.datetime, ended: dt.datetime | None,
                    root: str, result: str, reason_code: str = "") -> None:
    """Write the last-pass file all-or-nothing (decision 155's replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomically(path, {
        "started": started.isoformat(timespec="seconds"),
        "ended": ended.isoformat(timespec="seconds") if ended else None,
        "build": _this_build(),
        "root": root,
        "result": result,
        "reason_code": reason_code,
    })


def _log_file(ns) -> Path | None:
    """The run log this pass writes, from its ``--log`` (decision 186): the
    flag alone is :func:`log_path` in the data home, a whole path is that
    file (CI names one), no flag is no log. A relative path is ``None``
    here - :func:`tracker.runner._pass` refuses it before anything is written."""
    if not ns.log:
        return None
    if ns.log == LOG_FILENAME:
        return log_path()
    named = Path(ns.log)
    return named if named.is_absolute() else None


def _log_a_failed_pass(log_file: Path | None, reason_code: str, kind: str) -> None:
    """The run log's line for a pass that stopped early: the reason's code,
    its fixed sentence and the class of what stopped it - never the
    exception's message, which can name a client's folder (decision 189,
    security principle 7). The log is the data home's (decision 186), so a
    pass that stopped before it found a root is logged too; a pass run
    without ``--log``, or whose data home cannot be had, writes none, and
    the last-pass file and the scheduler's red run still say it."""
    if log_file is None:
        return
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    said = PASS_REASONS.get(reason_code, PASS_REASONS[PASS_ENDED_EARLY])
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        append_rotating(log_file, f"[{stamp}] ! pass failed ({reason_code}): {said} ({kind})\n",
                        max_bytes=LOG_MAX_BYTES, keep=LOG_KEEP)
    except Exception as exc:
        log.warning("Could not write %s (%s)", log_file.name, errors.error_class(exc))


def amber_hours(every: int) -> float:
    """How long since the last pass began before the line turns amber: two
    missed runs of the saved interval, never under
    :data:`LAST_PASS_AMBER_HOURS`, and :data:`LAST_PASS_AMBER_HOURS_DAILY`
    for a schedule that runs once a day (``every`` 0)."""
    return LAST_PASS_AMBER_HOURS_DAILY if not every else max(LAST_PASS_AMBER_HOURS, 2 * every / 60)


def last_pass_line(path: Path | None = None, *, now: dt.datetime | None = None) -> dict:
    """The app's one line about the schedule: ``{"text", "level"}``.

    Red when the last scheduled pass failed or the file cannot be read;
    amber when the last one started more than :func:`amber_hours` ago - two
    missed runs of the saved interval - or none has run; plain otherwise.
    With the schedule off the line says so and is plain: no pass is due.
    The words are here so the app types none of them (UX principle 6).

    Read as decision 189 reads its order hint: at most
    :data:`LAST_PASS_MAX_BYTES`, every error - a nested file's
    ``RecursionError`` included - is "could not be read", said by its
    class, and nothing the file holds is echoed: a result is one of the
    three this module writes, a reason one of its codes. Never raises: it
    is part of the app's first call."""
    now = now or dt.datetime.now()
    try:
        preference = schedule_preference()
    except ScheduleChoiceError as exc:
        return {"text": str(exc), "level": LEVEL_ERR}
    except SettingsError as exc:
        return {"text": LAST_PASS_UNREADABLE.format(error=errors.error_class(exc)), "level": LEVEL_ERR}
    if not preference.enabled:
        return {"text": LAST_PASS_OFF, "level": LEVEL_OK}
    try:
        path = path or last_pass_path()
        with path.open("rb") as handle:
            raw = handle.read(LAST_PASS_MAX_BYTES + 1)
    except FileNotFoundError:
        return {"text": LAST_PASS_NEVER, "level": LEVEL_WARN}
    except Exception as exc:
        return {"text": LAST_PASS_UNREADABLE.format(error=errors.error_class(exc)), "level": LEVEL_ERR}
    try:
        if len(raw) > LAST_PASS_MAX_BYTES:
            raise ValueError("past the file's size")
        data = json.loads(raw.decode("utf-8"))
        started = dt.datetime.fromisoformat(data["started"])
        result = data["result"]
        if result not in (PASS_RUNNING, PASS_SUCCEEDED, PASS_FAILED):
            raise ValueError("not a result this version writes")
        hours = amber_hours(preference.every)
        old = now - started > dt.timedelta(hours=hours)
    except Exception as exc:
        return {"text": LAST_PASS_UNREADABLE.format(error=errors.error_class(exc)), "level": LEVEL_ERR}
    when = started.strftime("%Y-%m-%d %H:%M")
    if result == PASS_FAILED:
        code = data.get("reason_code")
        reason = PASS_REASONS.get(code if isinstance(code, str) else "", PASS_REASONS[PASS_ENDED_EARLY])
        return {"text": LAST_PASS_FAILED_LINE.format(when=when, reason=reason), "level": LEVEL_ERR}
    text = (LAST_PASS_RUNNING_LINE.format(when=when) if result == PASS_RUNNING
            else LAST_PASS_LINE.format(when=when, result=result))
    if old:
        return {"text": text + LAST_PASS_OLD.format(hours=f"{hours:g}"), "level": LEVEL_WARN}
    return {"text": text, "level": LEVEL_OK}
