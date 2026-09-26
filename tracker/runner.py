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

**What a killed write left is swept first** (decision 155). Every file
the tracker writes goes through a temp beside it and is renamed into
place whole, so a pass killed half way - Task Scheduler's limit, a power
cut, a restart - leaves a temp and never half a file under its name. The
household pass takes those temps away under its locks before anything is
read (``tracker.filer.sweep_stranded_temps``): only the tracker's own
exact shape, only in the household's firm folders and beside the README,
never in a year's folder where the originals rest.

**Every folder that does not fit the layout is listed and left alone.** The
practice page ends with them, each with the one sentence saying why
(``tracker.registry``). Nothing in one is ever read, moved or renamed.

One engagement's failure never stops the others. An unreadable record, a
scan already running, a drop that would not sort — each is recorded against
that engagement and the run moves on, because one client's problem must not
be the reason nine other clients went unprocessed. The command exits non-zero
if anything failed, so the scheduler shows a red run instead of a silent one.

**And the pass cannot go quiet** (decision 189). Whatever stops it - a
surprise in the runner's own code, a database the engine refuses, a run
log that cannot be written - the run log and the practice page are each
still attempted, in a guard of their own, and each says what the other
could not do: :data:`PASS_STOPPED` names the class of what stopped the
pass, :data:`LOG_NOT_WRITTEN` puts a log that failed on the page. The
store's and the record's own errors are classes the pass catches
(``store.StoreUnavailable``, ``ledger.RecordNotWritten``), so one bad
database or a full disk costs the household it happened in. Every verdict
is saved the moment the next file is taken, so a pass killed half way
reads again only what it was killed on. The pass's own sentences name a
class or a code, never an exception's text, which can carry a client's
path.

**And no household holds up the rest** (decision 189, the bounded
household). Each household has :data:`HOUSEHOLD_BUDGET_SECONDS` of a
pass, on the awake clock, checked between files; one out of time stops
taking files, records what it did, drafts nothing and says so
(:data:`OUT_OF_TIME`), and the rest wait for the next pass. Households
run least recently completed first, from a hint beside the store
(:data:`PASS_ORDER_FILENAME`, safe to delete); one skipped for a held
lock is tried once more at the end of the pass; and one not served two
passes running exits the pass with :data:`NOT_SERVED_TWICE_EXIT_CODE`
and is named on the page. A logged pass says it started, and the next
one says when a start never finished (:data:`PASS_DID_NOT_FINISH`).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import sys
import time
from collections.abc import Iterable
from contextlib import ExitStack, nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from tracker import checkpoint, content_check, door, ledger, ocr, store
from tracker.filer import (
    HOUSEHOLD_NO_ROOM,
    NEEDS_REVIEW,
    ROOM_PARKS,
    ensure,
    file_household_drops,
    read_index,
    refresh_household_readme,
    room_for,
    sweep_stranded_temps,
)
from tracker.fsio import write_json_atomically, write_text_atomically
from tracker.households import (
    client_folder_missing,
    load_household_info,
    open_years,
    resolve_feeds,
)
from tracker.layout import (
    LayoutError,
    client_household_dir,
    household_of,
    inbox_of,
    lock_order_key,
    originals_dir_for,
    parts_below,
    root_of,
)
from tracker.ledger import LedgerError
from tracker.locking import RUN_TIME_LIMIT_SECONDS, engagement_lock
from tracker.manifest import (
    ISO_DATE_HINT,
    ManifestError,
    check_rules,
    load_manifest,
    summarize,
)
from tracker.page import esc, page_text, table, tolerant_console
from tracker.progress import APP_CLOSED, Watch, failure_reply
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
    DRAFT_WRITTEN_BESIDE,
    NEW_DRAFT_FILENAME,
    DraftsEditedError,
    ReminderError,
    draft_changed,
    draft_reminder,
    drafted_event,
    held_refusal,
    held_too_long,
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
    error_log,
    firm,
    product_name,
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
#: The app's Run now (decision 203): this same pass for one household,
#: named by its folder in the firm's tree and checked through the one door
#: (``door.household_dir``) as any path from outside is. Always written
#: ``--household=<folder>``, one argument, so a folder whose name begins
#: with ``-`` is a value and never a flag.
HOUSEHOLD_FLAG = "--household"
#: Run now's other addition: the pass prints decision 193's progress lines
#: on stdout, the shell's way of watching it, and ends with one final JSON
#: line - every return of the household, the pass's warnings and the exit
#: code - in place of the console report. Its refusals are the one failure
#: envelope (``tracker.progress.failure_reply``).
PROGRESS_LINES_FLAG = "--progress-lines"
#: A household the walk did not find under the root: said, never guessed.
NOT_THAT_HOUSEHOLD = "{name} is not a household the walk found in {root}"
#: A household flag with nothing after it: refused, never read as the whole
#: practice (decision 203's review, S1).
NO_HOUSEHOLD_NAMED = f"{HOUSEHOLD_FLAG} names no household; Run now runs one, named by its folder"
#: What the scheduled job installed before decision 131 is told. That job
#: named a clients root on its command line with ``--log``; after the root
#: moves in the app it would go on sorting the old tree silently, so a run
#: of that shape whose root is not the settings file's is refused, red,
#: until *Install Schedule* is pressed once (decision 131's review, F3).
OLD_JOB_ROOT = ("the scheduled job still names an old clients root ({root}); open the app and "
                "press Install Schedule")

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
#: ago than this. The schedule repeats every two hours by default, so four
#: hours is one missed run and a margin.
LAST_PASS_AMBER_HOURS = 4
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
PASS_RETURN_ERRORS = "return-errors"
PASS_NOT_SERVED = "not-served-twice"
#: This machine's record checkpoint could not be asked whether the root is
#: its own (the rebase review's MF1 and SF1): busy, or unreadable. Each its
#: own code and sentence - never "not the root", which sends a person to
#: move-root.
PASS_CHECKPOINT_BUSY = "checkpoint-busy"
PASS_CHECKPOINT_UNREADABLE = "checkpoint-unreadable"
PASS_ENDED_EARLY = "stopped"
PASS_REASONS = {
    PASS_SETTINGS: "the settings file could not be read",
    PASS_NO_ROOT: "no clients folder is set",
    PASS_ROOT_REFUSED: "the clients folder was refused",
    PASS_ROOT_NOT_CLAIMED: "the clients folder is not the one this machine's record checkpoint belongs to",
    PASS_ROOT_UNREADABLE: "the clients folder could not be walked",
    PASS_RETURN_ERRORS: ("the pass ended with a problem - a return that failed, or a log or page it "
                         "could not write; the practice page and runs.log say which"),
    PASS_NOT_SERVED: ("a household has not been served two passes running; the practice page says "
                      "which and why"),
    PASS_ENDED_EARLY: "the pass stopped with an error before it began; runs.log names its kind",
    PASS_CHECKPOINT_BUSY: ("this machine's record checkpoint was busy - another run was using it; "
                           "no household was served, and the next pass tries again"),
    PASS_CHECKPOINT_UNREADABLE: ("this machine's record checkpoint could not be read; no household "
                                 "was served - the practice page says what to do (runbook §6)"),
}
LAST_PASS_LINE = "Last scheduled pass: {when}, {result}."
LAST_PASS_FAILED_LINE = "Last scheduled pass: {when}, failed ({reason})."
LAST_PASS_RUNNING_LINE = "Last scheduled pass: started {when}, not finished."
LAST_PASS_OLD = (f" Nothing newer for over {LAST_PASS_AMBER_HOURS} hours: check that the schedule "
                 "is still installed on the office machine (runbook, 'The last-pass line').")
LAST_PASS_NEVER = ("No scheduled pass has run on this machine yet. If the schedule is installed "
                   "here, one will run within two hours.")
LAST_PASS_UNREADABLE = "The last scheduled pass could not be read ({error})."
#: How the app colours the line: the API says it, the page only draws it.
LEVEL_OK, LEVEL_WARN, LEVEL_ERR = "ok", "warn", "err"


def _refuse_an_old_jobs_root(root: str) -> None:
    """Refuse a run shaped like the job installed before decision 131 - a
    root on the command line together with ``--log`` - whose root differs
    from the settings file's, or that has no settings root to agree with.

    A person running one folder by hand leaves ``--log`` off and is never
    refused here - though since decision 159 (E5) a folder outside the
    root this machine's record checkpoint belongs to is refused by
    :func:`tracker.store.prove_the_root`.
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


def run_now_arguments(settings_dir: Path | str, household: Path | str) -> list[str]:
    """The runner's command line for the app's Run now (decision 203).

    The first three are the scheduled job's own, in its order
    (``tracker.scheduling.runner_arguments``, decision 131): the settings
    folder the clients root is read from, and the run log. The rest are
    what Run now adds - no draft (as Run now never drafted), the progress
    lines the shell watches, and the one household, as one argument.
    """
    return [SETTINGS_FLAG, str(settings_dir), LOG_FLAG, "--reminders", REMINDERS_NEVER,
            PROGRESS_LINES_FLAG, f"{HOUSEHOLD_FLAG}={household}"]
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
#: What a pass says, once, when the reader could not start for some of its
#: files (decision 150): the machine's fault, not the files'. Nothing was
#: kept or recorded about them; they wait and are read again on the next
#: pass.
READER_COULD_NOT_START = ("the reader could not start on this machine for {n} file(s) this pass "
                          "({names}); nothing was kept about them and they wait for the next "
                          "pass - look at the machine")


#: What a pass says when something in the runner's own code stopped it
#: (decision 189): the class of what stopped it, never its text. Every
#: household that finished is still reported, logged and drawn.
PASS_STOPPED = ("the pass stopped early ({kind}); the households after it were not looked at "
                "this pass")
#: What the run log's failure says, on the page and in the console
#: (decision 189): the log is how an unattended failure leaves a trace,
#: so one that could not be written is itself a problem to see.
LOG_NOT_WRITTEN = "the run log could not be written ({kind})"
#: What the practice page's failure says where it can be said: the app's
#: reply after Run now, and the console (decision 189).
PAGE_NOT_WRITTEN = "the practice page could not be written ({kind})"

#: Each household's share of a pass (decision 189), on ``ocr.awake_clock``
#: from the household's start and checked **between files**: a household
#: can run at most this plus one document's stop (600 s), 25 minutes -
#: and Run now is this same pass for one household (decision 203), so it
#: has the same share - and four stalled households fit in the schedule's
#: two hours while the order below serves the rest next pass. A threshold
#: stated in advance (UX 9), not measured into place.
HOUSEHOLD_BUDGET_SECONDS = 15 * 60
#: What each working return of a household out of time says. ``n`` is the
#: files its sort took this pass; nothing is drafted for it this pass.
OUT_OF_TIME = ("this household's time for this pass ran out after {n} file(s); the rest wait "
               "for the next pass")
#: Its draft note: a letter built on an unfinished pass could chase what
#: already arrived, and the next pass's draft rule catches the week up.
OUT_OF_TIME_NO_DRAFT = "not drafted this pass: the household's time ran out"
#: A pass a person stopped (decision 193): the household's deadline brought
#: to now, so it is said as :data:`OUT_OF_TIME` is, with who stopped it.
PASS_CANCELLED = "stopped by a person after {n} file(s); the rest wait for the next pass"
CANCELLED_NO_DRAFT = "not drafted this pass: a person stopped it"
#: A pass whose app closed (decision 203): the progress pipe broke, which
#: is a stop like a person's, at the next file, counted the same way.
PASS_APP_CLOSED = ("stopped when the app that started it closed, after {n} file(s); the rest wait "
                   "for the next pass")
APP_CLOSED_NO_DRAFT = "not drafted this pass: the app that started it closed"
#: The hint of when each household last completed a pass (decision 189),
#: beside the store, so it holds household names only where the store
#: already does and moves with it. A hint, never a record: nothing but the
#: order and the not-served count reads it, and deleting it resets both.
PASS_ORDER_FILENAME = "pass-order.json"
PASS_ORDER_VERSION = 1
#: The largest hint read (the review's S1): a file past it is not parsed.
#: A real hint is one short line per household, well under a kilobyte for
#: a practice's worth; anything this large is not one.
PASS_ORDER_MAX_BYTES = 64 * 1024
ORDER_HINT_UNREADABLE = ("the pass order could not be read; households ran in folder order "
                         "this pass")
#: The exit code of a pass in which some household was not served for the
#: second pass running (decision 189): Task Scheduler's Last Run Result
#: reads 0x3. 1 is a return that failed; 2 is argparse's; 3 wins over 1.
NOT_SERVED_TWICE_EXIT_CODE = 3
NOT_SERVED_TWICE = "{household} has not been served for {n} passes running ({why})"
#: Why a household was not served, as the sentence above says it.
WHY_OUT_OF_TIME = "ran out of time"
WHY_HELD_LOCK = "held lock"
WHY_NO_ROOM = "no room"
WHY_FAILED = "failed"
WHY_CANCELLED = "stopped by a person"
#: The run log's line before a logged pass does anything, and what the
#: next pass says when the last such line has no pass summary after it
#: (decision 189, SPEC-161 ruling 3): killed, or the machine went off.
PASS_STARTED_LINE = "[{stamp}] pass started"
PASS_DID_NOT_FINISH = ("the pass that started at {stamp} did not finish (it was stopped or the "
                       "machine went off); this pass picks up where it left off")
#: How much of the run log's end is read for that question.
LOG_TAIL_BYTES = 64 * 1024


def reader_start_warning() -> str:
    """The pass's one warning about readers that could not start since it
    last asked (decision 150), or "" when every reader started."""
    names = content_check.readers_that_could_not_start()
    if not names:
        return ""
    return READER_COULD_NOT_START.format(n=len(names), names=", ".join(sorted(set(names))[:5]))


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
    #: Skipped because another run held a lock this household needed
    #: (decision 189): a typed flag, not the text of ``skipped``, so the
    #: pass can try the household once more at its end.
    locked_out: bool = False
    #: The household's time for this pass ran out (decision 189).
    out_of_time: bool = False
    #: A person stopped the pass before this household's work was done
    #: (decision 193): what was done is recorded, the rest waits.
    cancelled: bool = False
    #: The return whose lock a take met, when ``locked_out`` (decision
    #: 193): the app's notice says who holds it and since when.
    locked_at: Path | None = None
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
        if self.opened:
            parts.append(f"opened {self.opened}")
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
    #: What the pass says once, about the pass rather than one return: a
    #: reader that could not start on this machine (decision 150), the
    #: graphics card failing mid-pass (decision 169).
    warnings: list[str] = field(default_factory=list)
    #: Which device the reader used this pass (decision 169): the run
    #: log's first line says it, ``reader=processor`` or
    #: ``reader=graphics card``.
    reader: str = ocr.DEVICE_PROCESSOR
    #: The one run-log line when the graphics card pack is there and could
    #: not be used (``ocr.PACK_UNUSABLE``), or "". Not a pass warning.
    reader_note: str = ""
    #: The households not served for the second pass running or more
    #: (decision 189): the pass exits :data:`NOT_SERVED_TWICE_EXIT_CODE`.
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
    created: dt.date | None = None,
) -> bool:
    """Whether the automated run drafts a reminder for this engagement today.

    ``Reminders`` set to ``NO`` in the engagement's details wins over every
    mode. It is a standing decision that this client is not chased by email,
    and a command line flag is not the place to reverse it —
    ``python -m tracker.reminder`` still drafts one on demand for anybody.

    Weekly means once a week, not only on the day: a machine that was off
    on the draft day drafts on its next pass, when ``drafted`` (the day the
    last draft was written) is older than the draft day that went by. An
    engagement never drafted is owed its first draft once a draft day has
    come since it was ``created`` (the day of its first rules event,
    :func:`created_on`), so a client set up mid-week is not chased the same
    afternoon, and one whose first draft day the machine missed is drafted
    on the next pass rather than a week late (decision 189, SPEC-161 A-F8).
    The record saying its draft day came and the draft was ``held``
    (decision 115) owes it too: the first pass after a person clears the
    question writes it.
    """
    if not engagement.reminders or mode == REMINDERS_NEVER:
        return False
    if mode == REMINDERS_ALWAYS:
        return True
    if is_draft_day(today, weekday):
        return True
    if held:
        return True
    if drafted is None:
        return created is not None and created <= last_draft_day(today, weekday)
    return drafted < last_draft_day(today, weekday)


def created_on(engagement_dir: Path) -> dt.date | None:
    """The day this return was created: the day of the first rules event on
    its record (``rules_changed``, or the retired ``rules_imported`` an
    older journal opens with), or None when the record has none or cannot
    be read - and then no first draft is owed by this rule."""
    try:
        events = ledger.read_events(engagement_dir)
    except (LedgerError, OSError):
        return None
    for event in events:
        if event.get(ledger.EVENT_KEY) in (ledger.RULES_CHANGED, ledger.RULES_IMPORTED):
            return ledger.day_of(str(event.get(ledger.AT_KEY, "")))
    return None


# --------------------------------------------------------------- one pass ----


#: What every return of a household is warned with while two of its years
#: are open. One inbox feeds the household (decision 125) and it cannot say
#: which year a document is for, so nothing is sorted from it until a year
#: is retired in the editor - which is a person's decision and never the
#: machine's guess.
TWO_OPEN_YEARS = ("two years are open in this household ({years}); nothing is sorted from its "
                  "inbox until one is retired in the editor")

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
    budget: float | None = None,
    watch: Watch | None = None,
    place: tuple[int, int] = (1, 1),
) -> list[EngagementRun]:
    """One pass over a whole household: sort its one inbox across every
    return it feeds, then scan, draft and draw each of its own returns.

    **Watched, and stoppable** (decision 193). ``watch`` is told the
    household (``place``: its position in the pass) and, through the sort
    and the scan, each file and request; a stop a person asked for through
    it brings the household's deadline to now, and every working return
    then says :data:`PASS_CANCELLED` instead of :data:`OUT_OF_TIME` and is
    not drafted.

    **Bounded** (decision 189). ``budget`` seconds - by default
    :data:`HOUSEHOLD_BUDGET_SECONDS`, the scheduled pass and Run now alike
    - on ``ocr.awake_clock`` from the household's start, checked by the
    sort and the scan before each file that would need a new judgment (a
    cache miss; ruling 2.2): a kept verdict is taken whatever the time.
    Past it they read no more, what they did is recorded, every working return says
    :data:`OUT_OF_TIME` and is not drafted, and the README is still
    refreshed. And **every pre-check is inside the guard**: the record,
    the room, the years, the lock order and the feed list failing cost
    this household, never the practice pass.

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

    Never raises: anything that goes wrong is recorded on the returns'
    runs so the caller can keep going through the
    rest of the practice.
    """
    today = today or dt.date.today()
    # This pass's start, for the sweep (decision 155): a temp that came to
    # be after it is nothing a killed write left.
    started = time.time()
    deadline = ocr.awake_clock() + (HOUSEHOLD_BUDGET_SECONDS if budget is None else budget)
    # Stamped before anything is touched, so a return that fails its
    # pre-checks still says when it was last looked at.
    runs = [EngagementRun(engagement=one, last_pass=dt.datetime.now()) for one in returns]
    if watch is not None:
        watch.say("household", household=household.name, n=place[0], of=place[1])
    if registry is None:
        for run in runs:
            run.error = NO_PRACTICE
        return runs
    working: list[EngagementRun] = []
    sorting: list[EngagementRun] = []
    taken = unreached = 0
    try:
        # A household stopped (two folders claim it, its record is gone) or
        # paused (its folders and its record disagree) is not touched at all
        # - no sweep, no layout, no sort, no scan, no draft, no README - and
        # every run of it is red until a person acts (decision 188, R6 and
        # R10). Inside the household's guard and budget (decision 189), and
        # before anything is sorted.
        held_back = (getattr(registry, "stopped", {}).get(household)
                     or getattr(registry, "paused", {}).get(household))
        # A household whose client folder is gone, when it has had one, was
        # renamed or moved in the client tree: nothing is made again under
        # the old name (SPEC-162 ruling 2, kept by decision 188).
        client_side_there = client_household_dir(household.parent.parent, household.name).is_dir()
        if not held_back and not client_side_there:
            held_back = client_folder_missing(household, [run.engagement.path for run in runs])
        if held_back:
            for run in runs:
                run.error = held_back
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
        # (decision 129), resolved to this year's returns; a line that
        # answers to nothing is said on every one of the household's own
        # returns.
        fed: list[Engagement] = []
        if sorting:
            fed, unresolved = _feeds_of(household, years[0], registry)
            for run in working:
                run.warnings.extend(unresolved)

        with ExitStack() as locks:
            # A dry run takes none: it writes nothing and must never block
            # a real run.
            if not dry_run:
                for folder in sorted([*(run.engagement.path for run in working),
                                      *(one.path for one in fed)],
                                     key=lock_order_key):
                    locks.enter_context(engagement_lock(folder))
            # What a killed write left - a working copy's temp, the README's
            # in the client's inbox - goes first, under the locks and before
            # anything is read, so nothing below counts it (decision 155).
            # The household's own returns only: a fed return's household
            # sweeps its own.
            if not dry_run:
                sweep_stranded_temps(household, [run.engagement.path for run in working],
                                     started=started, said=working[0].warnings)
            # The household's own side - the inbox and the year's folder -
            # is laid out once for the lot, before the inbox is read. The
            # fed returns are not in it: a fed return's own household lays
            # out its own folders, and its request list is not this
            # client's to read.
            if not dry_run:
                scaffold_household(household, returns=[run.engagement.path for run in working],
                                   may_make_household=not client_side_there)
            if sorting:
                taken, unreached = _sort_step(household, sorting, fed, today=today,
                                              dry_run=dry_run, deadline=deadline, watch=watch)
            for run in working:
                run_engagement(run.engagement, root=root, today=today, dry_run=dry_run,
                               reminders=reminders, weekday=weekday, lock_held=not dry_run,
                               run=run, deadline=deadline, unfinished=bool(unreached),
                               watch=watch)
            # The README, once, after the sort and after every return's
            # scan and draft, still inside the locks (decision 130): what
            # the client reads is current as of this pass, never one pass
            # behind. A household this inbox fed a document into is told
            # too - the document is in its index now, so it is on its list
            # (132's F-4 ruling), and it should not wait for its own pass.
            # Each writes only when its text changed.
            if not dry_run:
                for one in dict.fromkeys([household, *(household_of(f.path) for f in fed)]):
                    refresh_household_readme(one, said=working[0].warnings)
    except ScanLockedError as exc:
        held = exc.lock.parent if getattr(exc, "lock", None) else None
        for run in working:
            run.skipped = f"another run is still going ({exc})"
            run.locked_out = True
            run.locked_at = held
    except Exception as exc:  # the household's surprise must not stop the practice
        # Before ``working`` is known - a pre-check that raised - every
        # return not already skipped or failed carries it.
        for run in working or [one for one in runs if not one.skipped and not one.error]:
            if not run.error:
                # Its class and code, never its message (security principle
                # 7; the review's S2): the message can name a client's
                # folder, and this reaches the page and the run log. The
                # whole trace is on stderr for a person.
                run.error = content_check.said_as_class(exc)
        log.error("A household stopped early (%s)", content_check.said_as_class(exc),
                  exc_info=True)
    stopped = watch is not None and watch.stop_asked()
    closed = stopped and watch.why_stopped == APP_CLOSED
    if unreached or any(run.out_of_time for run in working):
        # The household's time ran out (decision 189), or a person stopped
        # it (decision 193, the same deadline brought to now): every working
        # return says which, whichever step it ended in, and the rest waits.
        for run in working:
            if stopped:
                run.cancelled = True
                run.out_of_time = False
                run.warnings.append((PASS_APP_CLOSED if closed else PASS_CANCELLED).format(n=taken))
                if run.draft_note == OUT_OF_TIME_NO_DRAFT:
                    run.draft_note = APP_CLOSED_NO_DRAFT if closed else CANCELLED_NO_DRAFT
            else:
                run.out_of_time = True
                run.warnings.append(OUT_OF_TIME.format(n=taken))
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
               today: dt.date, dry_run: bool,
               deadline: float | None = None,
               watch: Watch | None = None) -> tuple[int, int]:
    """The household's one inbox, sorted across the returns of its open year
    and the returns it feeds.

    One call, under the locks the caller holds, and one transaction per
    return inside it (decision 102, unchanged). Each of this household's
    own returns fills its own run; a fed return's report belongs to the
    pass of the household it lives in.

    This pass files nothing into a fed return (decision 204, revising
    129's second move and 132's pass filing): a document only a fed return
    wants parks in this household's own queue and is counted there, as
    under review, until a person hands it over. So there is nothing filed
    elsewhere for this pass to say - the sentence that said it
    (``FILED_INTO_FED``) went with the move - and "filed 0" is the truth
    about this inbox.

    Returns how many files the sort took and how many the household's
    time did not reach (decision 189).
    """
    first = sorting[0].engagement.path
    # The year the record says, which is the year folder's name: a folder
    # somebody renamed pauses the household (decision 188) and never
    # reaches here, and nothing is ever renamed.
    year = sorting[0].engagement.tax_year
    originals = originals_dir_for(root_of(first), household.name, year)
    reports = file_household_drops(
        inbox_of(first), originals,
        own=[run.engagement.path for run in sorting], fed=[one.path for one in fed],
        today=today, dry_run=dry_run, deadline=deadline, watch=watch,
    )
    for run in sorting:
        filed = reports.get(run.engagement.path)
        if filed is None:
            continue
        run.filed = len(filed.filed)
        run.opened = len(filed.opened)
        run.review = len(filed.review)
        run.waiting = len(filed.waiting)
        run.file_errors = [f"{e.name}: {e.error}" for e in filed.errors]
        run.slowest = filed.slowest
        # An original already sorted whose record no longer fits the disk
        # is for a person to look at, every pass - but nothing was left
        # unsorted, so it rides the warnings rather than failing the run.
        run.warnings.extend(f"{e.name}: {e.error}" for e in filed.attention)
    own = [reports[run.engagement.path] for run in sorting if run.engagement.path in reports]
    return (sum(one.handled + len(one.errors) for one in own),
            sum(one.unreached for one in own))


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
    deadline: float | None = None,
    unfinished: bool = False,
    watch: Watch | None = None,
) -> EngagementRun:
    """Scaffold, scan and (on the draft day) draft and draw one return.

    ``deadline`` is the household's (decision 189), handed to the scan;
    ``unfinished`` says the household's sort ran out of time. Either way
    short, the return is not drafted this pass (``out_of_time``).

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
                                      lock_held=not dry_run, deadline=deadline, watch=watch)
            summary = scanned.summary
            run.statuses = summary.counts
            run.outstanding = summary.outstanding
            run.warnings.extend(scanned.warnings)
            run.out_of_time = unfinished or scanned.unreached > 0

            drafted = last_drafted(engagement.path)
            if run.out_of_time:
                # A letter built on an unfinished pass could chase what
                # already arrived; the next pass's rule catches the week up.
                run.draft_note = OUT_OF_TIME_NO_DRAFT
            elif should_draft(engagement, today, reminders, weekday,
                            drafted=drafted, held=draft_is_held(engagement.path),
                            created=created_on(engagement.path) if drafted is None else None):
                _draft_step(run, dry_run=dry_run, today=today, weekday=weekday)
            else:
                run.draft_note = _why_no_draft(engagement, today, reminders, weekday)

            if not dry_run and not run.error:
                _view_step(run)
    except ScanLockedError as exc:
        run.skipped = f"another run is still going ({exc})"
        run.locked_at = exc.lock.parent if getattr(exc, "lock", None) else None
    except (ManifestError, ReminderError) as exc:
        run.error = str(exc)
    except Exception as exc:  # one client's surprise must not stop the rest
        # Its class and code, never its message (decision 193, security
        # principle 7): this reaches the page and the run log, and the
        # message can name a client's folder. The whole trace goes to the
        # local error log - the same rule as run_household's.
        run.error = content_check.said_as_class(exc)
        log.error("A return's pass stopped early (%s)", run.error, exc_info=True)
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
        # A hold older than a week is said on the page and in the log too
        # (decision 193), by the one rule the app says it by.
        if late := held_too_long(engagement.path, today, created=created_on(engagement.path)):
            run.warnings.append(late)
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
        run.draft_note = DRAFT_WRITTEN_BESIDE
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
    report: RunReport | None = None,
    watch: Watch | None = None,
    household: Path | None = None,
) -> RunReport:
    """Run every household in the registry, least recently completed first.

    ``household`` (decision 203) is the app's Run now: that household's
    returns are the ones selected and it is the only one walked. Its order
    mark, the end-of-pass lock retry and the order hint run unchanged, as
    for an ``only`` run.

    ``watch`` (decision 193) is told each household and, through it, each
    file; a stop seen through it ends the loop after the household it
    stopped, and the lock retry at the end is not made.

    **The order** (decision 189, SPEC-161 ruling 2): by when each household
    last completed a pass, oldest first, one never completed first, ties in
    the walk's order - from :data:`PASS_ORDER_FILENAME` beside the store, a
    hint: missing, unreadable or stale, the walk's order, and one warning
    (:data:`ORDER_HINT_UNREADABLE`) when it is there and cannot be read.
    A household whose every working return was skipped for a held lock is
    run once more at the end, with a fresh budget, and its runs replace the
    first attempt's. A household not served two passes running or more is
    named (:data:`NOT_SERVED_TWICE`) and the pass exits
    :data:`NOT_SERVED_TWICE_EXIT_CODE`. A dry run reads the hint for its
    order and writes, counts and names nothing; an ``only`` run updates the households it served.

    ``report`` is the caller's, filled as each household finishes
    (decision 189): when something in this function's own code raises,
    the caller still holds every run that finished, and logs and draws
    them. ``run_household`` itself never raises.

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
    if household is not None:
        chosen = registry.by_household().get(household, [])
    else:
        chosen = registry.find(only) if only else registry.engagements
    selected = {e.path for e in chosen}

    if report is None:
        report = RunReport(today=today, dry_run=dry_run, reminders=reminders)
    report.misfits = list(registry.misfits)
    report.siblings, report.foreign, report.unread = records_needing_a_person(registry)
    reader_start_warning()          # this pass's count starts here
    if warning := ocr.reader_path_warning():
        # The app sits too deep for its reader: said once, loudly, rather
        # than every scan waiting as "the reader could not run" (SPEC-169 section 9).
        report.warnings.append(warning)
    # Least recently completed first (decision 189), ties in the walk's order.
    hint_path, hint = _read_order_hint(report)
    walk = [(household, returns) for household, returns in registry.by_household().items()
            if any(one.path in selected for one in returns)]
    order = sorted(range(len(walk)), key=lambda at: _completed_key(hint, walk[at][0], at))

    def one_household(household: Path, returns: list[Engagement],
                      place: tuple[int, int] = (1, 1)) -> list[EngagementRun]:
        return run_household(household, returns, root=registry.source, today=today,
                             dry_run=dry_run, reminders=reminders, weekday=weekday,
                             registry=registry, watch=watch, place=place)

    # One reading child for the whole pass (decision 169, R-4), ended with
    # it. With a graphics card pack it starts now and settles the device,
    # so the run log's first line says which reader read.
    served: dict[Path, list[EngagementRun]] = {}
    with ocr.reading_session(settle=True, in_a_child=content_check.READ_IN_A_CHILD) as reader:
        report.reader, report.reader_note = reader.device, reader.note
        for n, at in enumerate(order, start=1):
            household, returns = walk[at]
            _mark_started(hint_path, hint, household, write=not dry_run)
            served[household] = one_household(household, returns, (n, len(order)))
            report.runs.extend(run for run in served[household]
                               if run.engagement.path in selected)
            if watch is not None and watch.stop_asked():
                break
        # Held by a lock the first time: once more, at the end (Dana's
        # amendment), and the second attempt is the one reported.
        for household, returns in walk:
            if household not in served or (watch is not None and watch.stop_asked()):
                continue
            working = _working(served[household])
            if working and all(run.locked_out for run in working):
                first = [run for run in served[household] if run.engagement.path in selected]
                served[household] = one_household(household, returns)
                again = [run for run in served[household] if run.engagement.path in selected]
                at = next(k for k, run in enumerate(report.runs) if run is first[0])
                report.runs[at:at + len(first)] = again
        report.warnings.extend(reader.warnings())
        report.reader_note = report.reader_note or reader.note
    if warning := reader_start_warning():
        report.warnings.append(warning)
    _keep_the_order(report, hint_path, hint, served, write=not dry_run)
    return report


def _working(runs: list[EngagementRun]) -> list[EngagementRun]:
    """A household's runs that were owed a pass: not rolled forward, not
    inactive - those skips are not failures and serve nothing."""
    return [run for run in runs if not skipped_because(run.engagement)]


def _read_order_hint(report: RunReport) -> tuple[Path | None, dict]:
    """Where the pass-order hint lives and what it says, by household
    folder name. Missing is the walk's order in silence; there and
    unreadable is the walk's order and :data:`ORDER_HINT_UNREADABLE`.

    **Only ever a hint** (SPEC 2.3; the review's S1): a file past
    :data:`PASS_ORDER_MAX_BYTES` is not parsed, and every error reading or
    parsing it - a nested file's ``RecursionError`` and a ``MemoryError``
    included - is the walk's order, said once. Nothing in it can stop a
    pass before its first household."""
    try:
        path = store.store_path().parent / PASS_ORDER_FILENAME
    except Exception as exc:
        log.warning("Could not tell where the pass order lives (%s)", exc.__class__.__name__)
        report.warnings.append(ORDER_HINT_UNREADABLE)
        return None, {}
    try:
        with path.open("rb") as handle:
            raw = handle.read(PASS_ORDER_MAX_BYTES + 1)
        if len(raw) > PASS_ORDER_MAX_BYTES:
            raise ValueError("past the hint's size")
        payload = json.loads(raw.decode("utf-8"))
    except FileNotFoundError:
        return path, {}
    except Exception as exc:
        log.warning("Could not read %s (%s)", path.name, exc.__class__.__name__)
        report.warnings.append(ORDER_HINT_UNREADABLE)
        return path, {}
    households = payload.get("households") if isinstance(payload, dict) else None
    if not isinstance(households, dict) or payload.get("version") != PASS_ORDER_VERSION:
        report.warnings.append(ORDER_HINT_UNREADABLE)
        return path, {}
    return path, {name: entry for name, entry in households.items() if isinstance(entry, dict)}


def _completed_key(hint: dict, household: Path, at: int) -> tuple:
    """Oldest completion first; never completed before any; ties in the
    walk's order (``at``). An entry that does not read is never completed.

    **A household a pass ended in goes last** (decision 189): its entry
    says it was ``started`` and never ``ended`` - the pass was killed in
    it, or the machine went off - so, for the order, it was served when it
    started. Without this a household that stalls past Task Scheduler's
    limit would be first, and killed, every pass, and every household
    after it in the walk would starve.
    """
    entry = hint.get(household.name, {})
    completed = entry.get("completed") if isinstance(entry.get("completed"), str) else ""
    started, ended = entry.get("started"), entry.get("ended")
    if isinstance(started, str) and not (isinstance(ended, str) and ended >= started):
        return (True, max(completed, started), at)
    return (bool(completed), completed, at)


def _mark_started(path: Path | None, hint: dict, household: Path, *, write: bool) -> None:
    """Say in the hint that this household's pass began, before it does
    anything, so a pass killed in it leaves the mark :func:`_completed_key`
    reads. Not on a dry run; a hint that cannot be written is a log line."""
    if not write or path is None:
        return
    hint[household.name] = {**hint.get(household.name, {}),
                            "started": dt.datetime.now().isoformat(timespec="seconds")}
    _write_order_hint(path, hint)


def _write_order_hint(path: Path, hint: dict) -> None:
    try:
        write_json_atomically(path, {"version": PASS_ORDER_VERSION, "households": hint})
    except OSError as exc:
        # A hint: a pass that cannot keep it runs in the walk's order next
        # time, which is where every pass started before decision 189.
        log.warning("Could not write %s (%s)", path.name, exc.__class__.__name__)


def _why_not_served(runs: list[EngagementRun]) -> str:
    """Why a household was not served this pass, or "" when it was: every
    working return ended with no error, no skip and not out of time."""
    working = _working(runs)
    if any(run.cancelled for run in working):
        return WHY_CANCELLED
    if any(run.out_of_time for run in working):
        return WHY_OUT_OF_TIME
    if any(run.locked_out for run in working):
        return WHY_HELD_LOCK
    if any(run.skipped for run in working):
        return WHY_NO_ROOM
    if any(run.error for run in working):
        return WHY_FAILED
    return ""


def _keep_the_order(report: RunReport, path: Path | None, hint: dict,
                    served: dict[Path, list[EngagementRun]], *, write: bool) -> None:
    """Fold this pass into the hint, name every household not served two
    passes running, and write the hint whole. A dry run does none of it
    (the review's N4): it keeps nothing, so it counts nothing, names no
    household and never exits :data:`NOT_SERVED_TWICE_EXIT_CODE`."""
    if not write:
        return
    now = dt.datetime.now().isoformat(timespec="seconds")
    for household, runs in served.items():
        entry = dict(hint.get(household.name, {}))
        entry["ended"] = now
        why = _why_not_served(runs)
        if why:
            count = entry.get("not_served")
            entry["not_served"] = (count if isinstance(count, int) and count >= 0 else 0) + 1
            entry.setdefault("completed", None)
            if entry["not_served"] >= 2:
                report.not_served_twice.append(household.name)
                report.warnings.append(NOT_SERVED_TWICE.format(
                    household=household.name, n=entry["not_served"], why=why))
        else:
            entry.update(completed=now, not_served=0)
        hint[household.name] = entry
    if path is not None:
        _write_order_hint(path, hint)


def records_needing_a_person(
        registry: Registry) -> tuple[list[Path], list[checkpoint.Foreign], list[str]]:
    """The copies beside every household's and every return's record and
    lock, the lines from another machine not yet acknowledged (decision
    159, §4.4), and - when the checkpoint cannot be read - the sentence
    that says those lines could not be listed (:data:`FOREIGN_UNLISTED`;
    the rebase review's SF3), so they never vanish from the page in
    silence. Reads only: a copy is never deleted, moved or renamed, because
    the tracker cannot know which one is right."""
    folders = [household.path for household in registry.households]
    folders += [engagement.path for engagement in registry.engagements]
    siblings = [copy for folder in folders for copy in ledger.siblings(folder)]
    try:
        return siblings, store.foreign_lines(), []
    except Exception as exc:
        # Nothing may stop a pass before its first household (decision
        # 189): the pass goes on, and the page says why the lines from
        # other machines are not listed.
        log.warning("Could not read the record checkpoint (%s)", content_check.said_as_class(exc))
        return siblings, [], [FOREIGN_UNLISTED.format(why=checkpoint_said(exc))]


def checkpoint_said(exc: BaseException) -> str:
    """How a checkpoint that could not be read is said on the page: its own
    fixed sentence (the file, the engine's code, the runbook's step - busy
    or unreadable), or, for anything else, its class and code alone."""
    if isinstance(exc, checkpoint.CheckpointError):
        return str(exc)
    return content_check.said_as_class(exc)


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
    for warning in report.warnings:
        lines.append(f"  ! {warning}")

    lines += [
        "",
        f"  {len(report.processed)} processed, {len(report.errors)} failed, "
        f"{len(report.drafted)} draft(s) written, "
        + (f"{len(report.held)} held, " if report.held else "")
        + f"{report.outstanding} request(s) outstanding",
    ]
    if report.drafted:
        lines.append("  Drafts are drafts: nothing has been sent to anyone.")
    # Every folder the walk left alone, at the end of every pass, as the
    # runbook says (decision 188): a client folder no household owns, a
    # name the rule refuses, a household position with no record.
    if report.misfits:
        lines += ["", f"  {STATUS_MISFITS_HEADING} ({len(report.misfits)})"]
        for misfit in report.misfits:
            lines.append(f"    {misfit.path}")
            lines.append(f"        {misfit.sentence}")
    return "\n".join(lines)


def append_log(path: Path | str, report: RunReport) -> Path:
    """Append this pass to a run log, so an unattended failure leaves a trace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"[{stamp}] {report.today.isoformat()} "
             f"reminders={report.reminders} dry_run={report.dry_run} reader={report.reader}"]
    if report.reader_note:
        # The graphics card pack is here and could not be used (decision
        # 169): the machine's to look at, said once, and not a warning.
        lines.append(f"    {report.reader_note}")
    for run in report.runs:
        # A count, never the sentences (decision 189): a warning can name a
        # client's file, and the page carries the words.
        lines.append(f"    {run.summary()}"
                     + (f" (warnings: {len(run.warnings)})" if run.warnings else ""))
        if run.held and not run.error:
            # A hold is said with its rows (decision 115): the log is where
            # a person finds out which request wants their decision.
            lines.append(f"            {run.draft_note}")
    for warning in report.warnings:
        lines.append(f"    ! {warning}")
    for unread in report.unread:
        lines.append(f"    ! {unread}")
    if report.siblings or report.foreign or report.refused:
        # The counts; the practice page names each (decision 159).
        counts = STATUS_RECORDS_COUNTS.format(copies=len(report.siblings), foreign=len(report.foreign),
                                              refused=len(report.refused))
        lines.append(f"    ! {counts}")
    # A summary names client files, and a name NTFS holds is not always
    # one UTF-8 can (a lone surrogate); the log takes what it can write
    # rather than lose every engagement's line to one name.
    with path.open("a", encoding="utf-8", errors="backslashreplace") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


class PassFailed(SystemExit):
    """A pass that stops before it reaches the root, with the reason's code.

    It is a ``SystemExit`` so the command line behaves exactly as it did -
    the message printed, a non-zero exit, the scheduler's red run - and
    :func:`main` can still write the code into the last-pass file."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


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


def _log_a_failed_pass(root: str, reason_code: str, kind: str) -> None:
    """The run log's line for a pass that stopped early: the reason's code,
    its fixed sentence and the class of what stopped it - never the
    exception's message, which can name a client's folder (decision 189,
    security principle 7). The log lives in the clients root, so a pass
    that never found a root has nowhere to write it; the last-pass file and
    the scheduler's red run still say it."""
    if not root or not Path(root).is_dir():
        return
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    said = PASS_REASONS.get(reason_code, PASS_REASONS[PASS_ENDED_EARLY])
    try:
        with (Path(root) / LOG_FILENAME).open("a", encoding="utf-8", errors="backslashreplace") as handle:
            handle.write(f"[{stamp}] ! pass failed ({reason_code}): {said} ({kind})\n")
    except OSError as exc:
        log.warning("Could not write %s (%s)", LOG_FILENAME, exc.__class__.__name__)


def last_pass_line(path: Path | None = None, *, now: dt.datetime | None = None) -> dict:
    """The app's one line about the schedule: ``{"text", "level"}``.

    Red when the last scheduled pass failed or the file cannot be read;
    amber when the last one started more than :data:`LAST_PASS_AMBER_HOURS`
    ago, or none has run; plain otherwise. The words are here so the app
    types none of them (UX principle 6).

    Read as decision 189 reads its order hint: at most
    :data:`PASS_ORDER_MAX_BYTES`, every error - a nested file's
    ``RecursionError`` included - is "could not be read", said by its
    class, and nothing the file holds is echoed: a result is one of the
    three this module writes, a reason one of its codes. Never raises: it
    is part of the app's first call."""
    now = now or dt.datetime.now()
    try:
        path = path or last_pass_path()
        with path.open("rb") as handle:
            raw = handle.read(PASS_ORDER_MAX_BYTES + 1)
    except FileNotFoundError:
        return {"text": LAST_PASS_NEVER, "level": LEVEL_WARN}
    except Exception as exc:
        return {"text": LAST_PASS_UNREADABLE.format(error=exc.__class__.__name__), "level": LEVEL_ERR}
    try:
        if len(raw) > PASS_ORDER_MAX_BYTES:
            raise ValueError("past the file's size")
        data = json.loads(raw.decode("utf-8"))
        started = dt.datetime.fromisoformat(data["started"])
        result = data["result"]
        if result not in (PASS_RUNNING, PASS_SUCCEEDED, PASS_FAILED):
            raise ValueError("not a result this version writes")
        old = now - started > dt.timedelta(hours=LAST_PASS_AMBER_HOURS)
    except Exception as exc:
        return {"text": LAST_PASS_UNREADABLE.format(error=exc.__class__.__name__), "level": LEVEL_ERR}
    when = started.strftime("%Y-%m-%d %H:%M")
    if result == PASS_FAILED:
        code = data.get("reason_code")
        reason = PASS_REASONS.get(code if isinstance(code, str) else "", PASS_REASONS[PASS_ENDED_EARLY])
        return {"text": LAST_PASS_FAILED_LINE.format(when=when, reason=reason), "level": LEVEL_ERR}
    text = (LAST_PASS_RUNNING_LINE.format(when=when) if result == PASS_RUNNING
            else LAST_PASS_LINE.format(when=when, result=result))
    if old:
        return {"text": text + LAST_PASS_OLD, "level": LEVEL_WARN}
    return {"text": text, "level": LEVEL_OK}


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
#: Records that need a person (decision 159, §4.4): drawn first, before the
#: counts, and only when there is one - on a good day there is nothing.
STATUS_RECORDS_HEADING = "Records that need a person"
RECORD_SIBLING = ("{path}: a copy beside a record or its lock, left by a sync client or a second "
                  "machine. The tracker never deletes one; a person decides which copy is right.")
RECORD_FOREIGN = ("{key}: line {seq} was written on {host} ({at}). Once a person has looked, "
                  "acknowledge it: {command}")
#: The command that acknowledges, with this machine's own store in it - no
#: placeholder a person would have to fill in (the review's N7).
ACKNOWLEDGE_COMMAND = 'python -m tracker.checkpoint "{store}" acknowledge "{key}"'
#: Where the lines from other machines would be, when the checkpoint could
#: not be read this pass (the rebase review's SF3).
FOREIGN_UNLISTED = "Lines from other machines could not be listed this pass: {why}"
#: What a pass that could not prove its root says, first in the records
#: section and in the problems list (the rebase review's MF1).
CHECKPOINT_NOT_PROVED = "No household was served this pass: {why}"
STATUS_RECORDS_COUNTS = ("records that need a person: {copies} copy(ies) beside a record, {foreign} "
                         "line(s) from another machine, {refused} record(s) refused")

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

    **Read from the store as the walk left it** (decision 192): the walk
    that found these engagements followed every journal moments before,
    and the pass's own writes went into the same store, so the index is
    read without following the journal again (``follow=False``, the
    page's alone); a return the store does not hold is followed as ever.
    An index that cannot be read is said by its class and code, never its
    message, which can name a client's folder (security principle 7).
    """
    parked: dict[Path, list[ParkedFile]] = {}
    problems: list[str] = []
    for run in report.runs:
        engagement = run.engagement
        try:
            entries = read_index(engagement.path, follow=False)
        except Exception as exc:
            problems.append(STATUS_INDEX_UNREADABLE.format(
                label=engagement.label, error=content_check.said_as_class(exc)))
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
    here takes a lock or writes anything but this page. The parked files
    are each return's index as the store holds it after the walk and the
    pass (decision 192), read once per return and never followed again.
    """
    root = Path(root)
    stamp = (now or dt.datetime.now()).isoformat(sep=" ", timespec="seconds")
    parked, problems = _parked_files(report)
    # The pass's own sentences first (decision 189): a pass that stopped, a
    # run log that could not be written - what a person must see before
    # any one return's problem.
    problems = [*report.warnings,
                *(f"{run.engagement.label}: {run.error}" for run in report.errors), *problems]

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
        *_records_needing_a_person(root, report),
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


def _records_needing_a_person(root: Path, report: RunReport) -> list[str]:
    """The page's first section (decision 159), one sentence per thing a
    person must look at: a copy beside a record or a lock, a record refused
    as altered, a line from another machine. Nothing when there is none."""
    said = list(report.unread)
    said += [RECORD_SIBLING.format(path=_under(root, copy)) for copy in report.siblings]
    said += [f"{run.engagement.label}: {run.error}" for run in report.refused]
    said += [RECORD_FOREIGN.format(key=line.key, seq=line.seq, host=line.host, at=line.at,
                                   command=ACKNOWLEDGE_COMMAND.format(store=store.store_path(),
                                                                      key=line.key))
             for line in report.foreign]
    if not said:
        return []
    return [f"<h2>{esc(STATUS_RECORDS_HEADING)} ({len(said)})</h2>",
            "<ul>", *(f"<li>{esc(one)}</li>" for one in said), "</ul>"]


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
        summary = summarize(load_manifest(engagement.path, follow=False))
    except (ManifestError, LedgerError, StoreError, OSError) as exc:
        # One bad record costs its own row, never the page (decision 189),
        # said by its class and code: the message can name the record's
        # path, a client's folder (security principle 7; the review's S2).
        run.error = RECORD_UNREADABLE.format(problem=content_check.said_as_class(exc))
        return run
    run.statuses = summary.counts
    run.outstanding = summary.outstanding
    if engagement.warning:
        run.warnings.append(engagement.warning)
    return run


def _under(root: Path, path: Path) -> str:
    """A folder as a person reads it on the practice page: its path below
    the clients root, or the whole path when it is not under one."""
    below = parts_below(root, path)
    return str(Path(*below)) if below else str(path)


def status_report(registry: Registry, *, passed: Iterable[EngagementRun] = (),
                  today: dt.date | None = None, warnings: Iterable[str] = (),
                  unread: Iterable[str] = ()) -> RunReport:
    """Every engagement in ``registry``, with the runs in ``passed`` folded in.

    The page is about the practice, not about whichever engagement was
    just run: a pass over one engagement (the app's button) or over a
    subset (``--only``) still draws every engagement the registry found.
    An engagement this pass did not touch is read, not run, so the page
    can be regenerated as often as anyone likes. ``warnings`` are the
    pass's own sentences, for the page's problems list (decision 189);
    ``unread`` what the pass could not ask of the record checkpoint, drawn
    first in the records section.

    **Each part from one source** (decision 192). Which returns exist,
    their labels, the problem rows, a stopped household's returns and the
    misfits come from the walk, ``registry``: discovery is positional and
    only a walk knows (decision 125). A return the pass ran is the pass's
    own run. Every other return's counts are read from the store as the
    walk left it - the walk followed every journal, moments before for
    *Run now* and at the start for the schedule - with no second read of
    its journal; a return the store does not hold is followed. So a
    return the pass did not run shows as its record stood when the pass
    began, plus anything recorded on this computer since.
    """
    ran = {run.engagement.path: run for run in passed}
    siblings, foreign, not_listed = records_needing_a_person(registry)
    return RunReport(
        today=today or dt.date.today(),
        runs=[ran[engagement.path] if engagement.path in ran else _engagement_status(engagement)
              for engagement in registry.engagements],
        misfits=list(registry.misfits),
        warnings=list(warnings),
        siblings=siblings,
        foreign=foreign,
        unread=[*unread, *(one for one in not_listed if one not in unread)],
    )


# --------------------------------------------------------------------- CLI ----

def _parser():
    """The runner's command line, built apart from :func:`main` so a test
    can read what a line means without running it (decision 203)."""
    import argparse

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
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--only", default="",
                       help="just the engagements matching this text")
    which.add_argument(HOUSEHOLD_FLAG, default=None, metavar="FOLDER",
                       help="just this household, by its folder in the firm's tree (the app's "
                            "Run now)")
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
    parser.add_argument(PROGRESS_LINES_FLAG, action="store_true",
                        help="print the pass's progress lines and end with one final JSON line "
                             "(what the app's Run now reads)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """The command line, as a function: ``python -m tracker.runner`` and the
    packaged executable in runner mode (``api_entry.py``) both call this.
    Returns the exit code - non-zero if any engagement failed, so the
    scheduler shows a red run, and :data:`NOT_SERVED_TWICE_EXIT_CODE` when
    a household has not been served two passes running.

    **Each ending in a guard of its own** (decision 189): the pass, the
    console, the run log, the page and the store's close are each tried
    whatever happened before them, so a pass that stopped still leaves its
    log and its page, and a log that could not be written is said on the
    page.

    **Run now is this pass** (decision 203): with :data:`PROGRESS_LINES_FLAG`
    it prints its progress lines and one final line instead of the console
    report, and a refusal on the way in is the one failure envelope."""
    # The report names client files, and the scheduler's console is not
    # UTF-8: a name it cannot encode must not turn a finished run into a
    # traceback after every original has been moved (the tenth reading).
    # The guard is the page's (decision 108): one home, every command line.
    tolerant_console()

    parser = _parser()
    ns = parser.parse_args(argv)

    # The clients root has one home (decision 131): the scheduled job names
    # the app's settings folder, and this process reads everything the app
    # reads from there - the root and the store beside it - before anything
    # reads settings at all. A root on the command line is walked instead -
    # a person running one folder by hand - as long as it is the root this
    # machine's record checkpoint belongs to, or inside it (decision 159).
    if ns.settings:
        os.environ[ENV_SETTINGS_DIR] = ns.settings
    # The local error log beside the tracker's database, for the pass's
    # lifetime (decision 193): every warning the package logs, and a
    # traceback in full, go there and never to the page or the run log.
    with error_log("tracker"):
        # The scheduled job's shape - the settings folder, no root, no
        # household (Run now names one, decision 203), not a dry run - says
        # when it started and how it ended (decision 159, E4). The
        # file is written first, so a pass that dies anywhere after this line
        # leaves "not finished" or "failed" behind, never an old "succeeded".
        last = (last_pass_path() if ns.settings and not ns.root and ns.household is None
                and not ns.dry_run else None)
        started = dt.datetime.now()
        reached = {"root": ""}
        if last is not None:
            _say_last_pass(last, started=started, ended=None, root="", result=PASS_RUNNING)
        try:
            code = _pass(ns, parser, reached)
        except BaseException as exc:
            if last is not None:
                reason = getattr(exc, "reason_code", PASS_ENDED_EARLY)
                _say_last_pass(last, started=started, ended=dt.datetime.now(), root=reached["root"],
                               result=PASS_FAILED, reason_code=reason)
                # Only into a root that was allowed and proved (the final
                # review's SF2): a refused root is never written into, even
                # to log its refusal - last-pass.json carries the reason.
                _log_a_failed_pass(reached["root"], reason, exc.__class__.__name__)
            if ns.progress_lines and isinstance(exc, SystemExit) and isinstance(exc.code, str):
                # A refusal before the pass began (decision 203): said as the
                # one failure envelope the shell reads, and nothing was touched.
                _print_line(json.dumps(failure_reply(exc.code, "refused"), ensure_ascii=True))
                return 1
            raise
        if last is not None:
            reason = (PASS_NOT_SERVED if code == NOT_SERVED_TWICE_EXIT_CODE
                      else reached.get("reason") or PASS_RETURN_ERRORS if code else "")
            _say_last_pass(last, started=started, ended=dt.datetime.now(), root=reached["root"],
                           result=PASS_FAILED if code else PASS_SUCCEEDED, reason_code=reason)
        return code

def _emit_line(text: str) -> None:
    """A progress line on stdout, flushed at once, so the shell hears it
    while the pass runs. A pipe whose reader has gone raises, which the
    watch takes as the app closing (decision 203); stdout is then pointed
    at nothing, so the interpreter's own last flush has nowhere to fail."""
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except OSError:
        try:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
        except OSError:
            pass
        raise


def _print_line(text: str) -> None:
    """The final line or the refusal, guarded as a progress line is: a
    reader that has gone costs the line, never the pass's ending."""
    try:
        _emit_line(text + "\n")
    except (OSError, ValueError) as exc:
        log.debug("Could not print the final line (%s)", exc.__class__.__name__)


def _final_line(report: RunReport, code: int, pass_id: int | None = None) -> str:
    """The pass's last line for the app (decision 203): no ``progress``
    key, so the shell reads it as the reply - every return the pass ran,
    the pass's own warnings and its exit code. The sentences are the
    runner's, the same the run log and the page carry."""
    runs = [{
        "label": run.engagement.label,
        "path": str(run.engagement.path),
        "ok": run.ok,
        "error": run.error,
        "skipped": run.skipped,
        "filed": run.filed,
        "review": run.review,
        "waiting": run.waiting,
        "file_errors": list(run.file_errors),
        "warnings": list(run.warnings),
        "statuses": dict(run.statuses),
        "outstanding": run.outstanding,
        "cancelled": run.cancelled,
        "locked_out": run.locked_out,
        "locked_at": str(run.locked_at) if run.locked_at else None,
    } for run in report.runs]
    return json.dumps({"pass": int(pass_id if pass_id is not None else os.getpid()), "exit": code,
                       "runs": runs, "pass_warnings": list(report.warnings), "warnings": []},
                      ensure_ascii=True)


def _say_last_pass(path: Path, **said) -> None:
    """:func:`write_last_pass` in a guard of its own (decision 189): a file
    that cannot be written is a log line, and never stops the pass or
    changes its exit code."""
    try:
        write_last_pass(path, **said)
    except Exception as exc:
        log.warning("Could not write %s (%s)", path.name, exc.__class__.__name__)


def _pass(ns, parser, reached: dict) -> int:
    """The pass itself, after the command line is read: :func:`main`'s body,
    apart so ``main`` can record how it ended. ``reached["root"]`` is set
    once the root is known and allowed."""
    root = ns.root
    if not root:
        try:
            configured = clients_root()
        except SettingsError as exc:
            raise PassFailed(PASS_SETTINGS, f"Clients folder problem: {exc}") from None
        if configured is None:
            raise PassFailed(PASS_NO_ROOT,
                             f"no clients root given and none in {settings_path()}; {NO_ROOT_HINT}")
    elif ns.log:
        _refuse_an_old_jobs_root(root)
    # A saved root is held to the rule at the start of every pass (decision
    # 137's review, F12), and a typed one to the same rule (decision 176): a
    # root a person or another program hands straight through would otherwise
    # be walked in full. Both through the one door (decision 188), which also
    # refuses a root one level too deep, inside a tree of a real root.
    try:
        root = str(door.checked_root(root or None))
    except door.DoorError as exc:
        raise PassFailed(PASS_ROOT_REFUSED, str(exc)) from None

    # This machine's record checkpoint belongs to one clients root (decision
    # 159, E5). Only the settings' root claims it, on the first real pass
    # (the final review's SF1); the root this pass walks - the settings' or
    # one typed by hand (the review's S2) - is held to that claim before
    # anything is walked and never claims. A checkpoint that will not open
    # is refused here by name (S4). The saved root is the one the door
    # checks (decision 188): a saved root the door refuses claims nothing.
    try:
        saved = door.checked_root(None) if clients_root() is not None else None
    except (SettingsError, door.DoorError):
        saved = None
    #
    # A checkpoint that is busy or cannot be read (the rebase review's MF1
    # and SF1) is not "another root": the root is still the one allowed
    # above, so the pass reaches it, writes its log and its page (decision
    # 189) with the checkpoint's own sentence first, and serves no
    # household - none can be proved against a checkpoint nobody can read.
    unproved: checkpoint.CheckpointError | None = None
    try:
        if saved is not None:
            store.prove_the_root(saved, claim=not ns.dry_run)
        store.prove_the_root(root, claim=False)
    except checkpoint.CheckpointError as exc:
        unproved = exc
        reached["reason"] = (PASS_CHECKPOINT_BUSY if getattr(exc, "busy", False)
                             else PASS_CHECKPOINT_UNREADABLE)
    except StoreError as exc:
        raise PassFailed(PASS_ROOT_NOT_CLAIMED, f"Clients folder problem: {exc}") from None

    reached["root"] = root
    try:
        loaded = discover_engagements(root)
    except RegistryError as exc:
        raise PassFailed(PASS_ROOT_UNREADABLE, f"Clients folder problem: {exc}") from None
    # Run now's household (decision 203): named, never guessed, and held
    # to the door again here, since this is a command line of its own.
    household: Path | None = None
    if ns.household is not None:
        if not ns.household.strip():
            raise SystemExit(NO_HOUSEHOLD_NAMED)
        try:
            household = door.household_dir(ns.household, root=root)
        except (door.DoorError, LayoutError) as exc:
            raise SystemExit(str(exc)) from None
        why = loaded.stopped.get(household) or loaded.paused.get(household)
        if why:
            raise SystemExit(why)
        if household not in loaded.by_household():
            raise SystemExit(NOT_THAT_HOUSEHOLD.format(name=household.name, root=loaded.source))

    when = dt.date.today()
    if ns.date:
        try:
            when = dt.date.fromisoformat(ns.date)
        except ValueError:
            parser.error(f"{DATE_FLAG} must be {ISO_DATE_HINT}, got {ns.date!r}")

    day = WEEKDAY_NAMES.index(ns.weekday) if ns.weekday else DRAFT_WEEKDAY

    if ns.only and not loaded.find(ns.only):
        raise SystemExit(f"Nothing in {loaded.source} matches {ns.only!r}")

    log_path: Path | None = None
    if ns.log:
        log_path = Path(ns.log)
        if not log_path.is_absolute() and ns.log == LOG_FILENAME:
            log_path = loaded.source / LOG_FILENAME

    # The report is made here and filled by the pass as each household
    # finishes (decision 189), so a pass stopped half way still hands the
    # log and the page every household it finished.
    result = RunReport(today=when, dry_run=ns.dry_run, reminders=ns.reminders)
    failed = False
    if log_path is not None:
        # A pass says it started (decision 189, SPEC-161 ruling 3), after
        # asking whether the last one that said so ever finished.
        _say_the_pass_started(log_path, result)
    # The reader writes no temporary file (decision 169), so there is no
    # scratch folder to point it at any more (decision 137's L7 is retired).
    # Watched from outside (decision 193): the progress file beside the
    # tracker's database names the household and the file, for the app's
    # lock notice. The scheduled pass prints nothing and nothing can stop
    # it from the app; Run now prints its lines (decision 203), may be
    # stopped, and stops at its next file when the app that started it
    # closes. A dry run keeps no file.
    lines = ns.progress_lines
    watch = Watch(None if ns.dry_run else store.store_path().parent,
                  emit=_emit_line if lines else None, limit_seconds=RUN_TIME_LIMIT_SECONDS)
    outcome = "failed"
    unread: list[str] = []
    try:
        if unproved is not None:
            unread = [CHECKPOINT_NOT_PROVED.format(why=checkpoint_said(unproved))]
            result.warnings.append(unread[0])
            failed = True
        else:
            watch.say("started", started=dt.datetime.now().isoformat(timespec="seconds"),
                      households=1 if household is not None else len(loaded.by_household()))
            run_registry(loaded, today=when, dry_run=ns.dry_run, reminders=ns.reminders,
                         weekday=day, only=ns.only, report=result, watch=watch,
                         household=household)
            outcome = ("stopped" if any(run.cancelled for run in result.runs)
                       else "out_of_time" if any(run.out_of_time for run in result.runs)
                       else "finished")
    except Exception as exc:
        # The runner's own code, not a household's (each of those is
        # caught where it happens): said by its class, the whole trace on
        # stderr for a person, and every ending below still attempted.
        log.error("The pass stopped early", exc_info=True)
        result.warnings.append(PASS_STOPPED.format(kind=exc.__class__.__name__))
        failed = True
    finally:
        watch.close(outcome)
    if watch.why_stopped == APP_CLOSED:
        # Said as the pass's own (decision 203's review, M1): the run log
        # gives a return's warnings as a count and the page as a number,
        # and the app that would have shown the sentence is gone - so it
        # goes where 189's pass warnings go, into the log's text and onto
        # the page, before either is written.
        closed = [said for run in result.runs for said in run.warnings
                  if said.startswith(PASS_APP_CLOSED.split("{", 1)[0])]
        result.warnings.extend(dict.fromkeys(closed or [PASS_APP_CLOSED.format(n=0)]))
    # With progress lines the console is the shell's pipe (decision 203):
    # what is said below goes in the final line instead.
    say = (lambda text: None) if lines else print
    say(format_report(result))

    if log_path is not None:
        try:
            append_log(log_path, result)
        except Exception as exc:
            log.warning("Could not write %s (%s)", log_path.name, exc.__class__.__name__)
            result.warnings.append(LOG_NOT_WRITTEN.format(kind=exc.__class__.__name__))
            say(f"\n  ! {result.warnings[-1]}")
            failed = True
        else:
            say(f"\n  Logged to {log_path}")

    if not ns.dry_run:
        # Every real pass, whether or not it was asked to log, whether or
        # not an engagement failed, and whether or not the pass itself was
        # stopped: the page is how a person finds out that one did. A dry
        # run writes nothing, this included.
        try:
            page = write_status_page(loaded.source, status_report(
                loaded, passed=result.runs, warnings=result.warnings, unread=unread))
        except Exception as exc:
            # Every original has already been moved and every status written
            # by the time we get here, so nothing about drawing a page may
            # end this in a traceback. But a page stuck on yesterday must not
            # look green (security principle 6; the review's S3): it is said
            # in the run log, by its class only, and the pass exits 1.
            kind = exc.__class__.__name__
            log.warning("Could not write %s (%s)", STATUS_PAGE_FILENAME, kind)
            say(f"\n  ! {PAGE_NOT_WRITTEN.format(kind=kind)}")
            if lines:
                result.warnings.append(PAGE_NOT_WRITTEN.format(kind=kind))
            failed = True
            if log_path is not None:
                try:
                    with log_path.open("a", encoding="utf-8") as handle:
                        handle.write(f"    ! {PAGE_NOT_WRITTEN.format(kind=kind)}\n")
                except Exception as late:
                    log.warning("Could not write %s (%s)", log_path.name, late.__class__.__name__)
        else:
            say(f"\n  The practice: {page}")

    # Checkpoint the store's write-ahead log and take its two side files
    # with it: a scheduled pass leaves the app's folder as it found it.
    try:
        store.close()
    except Exception as exc:
        log.warning("Could not close the store (%s)", exc.__class__.__name__)
    if result.not_served_twice:
        code = NOT_SERVED_TWICE_EXIT_CODE
    else:
        code = 1 if failed or result.errors else 0
    if lines:
        # After the log, the page and the store's close (decision 203): the
        # app redraws from a record that is already whole.
        _print_line(_final_line(result, code, watch.pass_id))
    return code


_STARTED = re.compile(r"^\[(?P<stamp>[^\]]+)\] pass started$")
_SUMMARY_HEAD = re.compile(r"^\[[^\]]+\] \d{4}-\d{2}-\d{2} reminders=")


def _say_the_pass_started(log_path: Path, report: RunReport) -> None:
    """Read the run log's end: a ``pass started`` line with no pass summary
    after it is a pass that never finished, said as
    :data:`PASS_DID_NOT_FINISH`. Then append this pass's own line. Each
    in its own guard: neither may stop the pass."""
    try:
        with log_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - LOG_TAIL_BYTES))
            tail = handle.read().decode("utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        tail = []
    except OSError as exc:
        log.warning("Could not read %s (%s)", log_path.name, exc.__class__.__name__)
        tail = []
    unfinished = ""
    for line in tail:
        if found := _STARTED.match(line):
            unfinished = found.group("stamp")
        elif _SUMMARY_HEAD.match(line):
            unfinished = ""
    if unfinished:
        report.warnings.append(PASS_DID_NOT_FINISH.format(stamp=unfinished))
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            stamp = dt.datetime.now().isoformat(timespec="seconds")
            handle.write(PASS_STARTED_LINE.format(stamp=stamp) + "\n")
    except OSError as exc:
        log.warning("Could not write %s (%s)", log_path.name, exc.__class__.__name__)


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
