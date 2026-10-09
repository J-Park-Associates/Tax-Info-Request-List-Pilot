"""Every one-time step after installing or upgrading, run by the install itself (decision 209).

Jason's standing preference (2026-09-26): *any one-time step that must run
after installing or upgrading is built into installation. An in-app
reset/repair path may remain for re-running it deliberately; the first run
never depends on a person remembering it.* Two steps used to depend on a
person: pressing **Install Schedule** once after upgrading, and running the
store check once after installing decision 187. A button a person must
remember is a step that is skipped on the one machine where it mattered,
and nothing says so until a filing deadline.

**One function, every job, in order** (:func:`run`): the schedule, then the
record check. A future one-time step is a third job added here and nowhere
else - not a line in the runbook, not a button.

1. **The schedule** - registered only on the computer the designation file
   in the firm's private tree names (``scheduling.schedule_decision``): the
   first Windows computer to run this with a root set claims it, any other
   registers none and removes its own. No root, no Task Scheduler, or
   another computer named are outcomes, not failures; a designation that
   is not one computer's name, a computer whose own name the file cannot
   hold, or a ``schtasks`` that refuses, is a failure - each in its own
   sentence, so a file that was written is never said to be unwritten.
   What it registers is the choice saved in the settings file (pilot P21:
   on or off, the first run's time, how often), read at every run, so no
   door can undo the Schedule button; **off** removes this computer's own
   task, leaves the designation alone and says so. A saved choice that is
   refused (a hand-edited file) is a failure and registers nothing from a
   guess.
2. **The record check** - decision 187's ``store.check`` for every folder
   with a record, and ``store.gone_journals``, as the store's command line
   runs them. It changes no record (opening the store may set an older one
   aside, as every opener does). It runs only when a root is set **and**
   the store file is there: this step never creates a store (a fresh
   machine's first pass builds it and judges every line as it goes). A
   folder the store has never met is left to that same first catch-up
   rather than named - its lines were never applied, so there is nothing
   an earlier version let through, and after a store set aside by an
   upgrade every return would otherwise be named at once. It says how many
   records it judged, and a store that held none is said as that, never as
   "nothing to repair".

3. **The test cache** (Jason's answer A (a), SPEC-209 R8) - before
   decision 185 some test runs wrote the anonymised corpus's file names
   into the checkout's ``.pytest_cache``; it holds nothing the app needs,
   and pytest makes it again. Only ``<the app folder>/.pytest_cache`` of
   the checkout this runs from (:data:`CHECKOUT`), never a path from the
   settings, the root or the environment; from source only - the packaged
   app has no checkout. It never follows a link out of the folder: a
   linked cache loses only the link, and inside it a link or junction is
   unlinked as an entry and never descended into, by a small explicit walk
   rather than ``shutil.rmtree`` (whose handling of junctions differs by
   version). Absent is nothing to do and says nothing.

**What it does not carry over** (P235). An install older than decision 186
(its store, run log and checkpoint beside the program) or older than the
rename to Tax Document Console (the earlier name's settings file and its
scheduled task) is set up fresh: this step moves, copies and removes
nothing of theirs. The first screen still names whatever an old install left
beside the program, for a person to move or delete (runbook).

**A finding names a household that waits** - for the kinds that do. A
line an earlier version applied that today's admission refuses stops its
household - at the pass, in the app's walk of the clients folder and on
the return's page, which refuses it with 187's sentence, while the notice
at the top of the first screen names it - because the store
judges every applied line again when its admission changes (decision 209,
R3b, ``store.ADMISSION_VERSION``); a record changed behind the tracker's
back is refused by the same sync. :data:`FINDINGS_WAIT` claims that for
those two kinds and no more: a gone record or another disagreement is
named for a person and is not said to wait.

**A finding is not a failure.** The check naming a line is the step doing
its job: exit 0, the finding printed at the end of Setup and shown in the
app until a later run finds nothing. Exit 1 only when a job could not run
at all, each in one plain sentence naming the job - never a traceback, and
never the content of a file a person or a sync client wrote.

**Three doors, one function.** ``Setup.bat`` runs it last (``--reason
setup``); the app runs it at every launch through the API's
``after-install`` command - in the background, never holding the first
screen - which returns at once when the program is the one that last ran
it cleanly (:func:`program_identity` against the record) **and** the
designation file names the computer the record says it named. That is what
makes the packaged app, which has no Setup, and a source checkout updated
by a pull that left the locks alone, run it once; and it is what makes the
old computer, after the schedule was moved to a new one, remove its own
task at its next start rather than at its next upgrade (two computers
running the pass is the hazard this decision closes). On the computer the
record says registered the schedule it also asks Windows, last, whether the
task is still there (P198, F6): an uninstall deletes the task and keeps
this record, so the same build reinstalled - or a task deleted by hand -
registers again at the next start, never only at Repair;
and saving the clients root runs it, so the first root saved on the
office computer registers the schedule with no button. The app's
**Repair the Schedule** runs it deliberately.

**It records what it did** beside the store, in :data:`RECORD_FILENAME`,
as the scheduled pass records its own note beside the store: the program
identity only when nothing failed, so a run that failed is tried again at
the next launch, the computer the designation named after it, and the
schedule choice it registered (``preference``): the launch door runs the
step again when the saved choice differs from the recorded one, so a choice
changed by hand or by another door is registered at the next start, and does
nothing (no ``schtasks`` call) when program, designation and choice are all
as recorded.

**One run at a time** (pilot P47). Every door - the launch in the
background, Setup, saving the root, Repair, the Schedule button - is its own
process, and two of them can overlap: the app's launch step runs unwaited
and outlives its window, and a restart starts another. A run reads the saved
choice and then acts on it, so a run that read "off" and acted after another
had registered "on" removed the task the Schedule button still showed. So
:func:`run` and :func:`launch` take one lock (:data:`LOCK_FILENAME`, beside
the record, with ``locking``'s rules for a lock its owner left) and read the
choice **inside** it: whichever run acts last acts on the choice saved last.
A run that cannot have the lock within :data:`LOCK_WAIT_SECONDS` changes
nothing and says so (:data:`STEP_BUSY`). Every task this step removes is
noted on the local debug log with why, so a task that goes is never a
mystery again.

It imports ``scheduling`` and the layers below it; the API imports it, and
nothing lower does (layer 4, ``tests/test_layers.py``).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tracker import door, errors, fsio, ledger, registry, runner, scheduling, settings, store
from tracker.fsio import write_json_atomically
from tracker.locking import EngagementLockedError, acquire_lock, release_lock, this_host

#: The note of the last run, beside the store - in the data home (decision
#: 186) - and named by ``runner.left_behind`` when an old copy is beside
#: the program. One spelling, the runner's.
RECORD_FILENAME = runner.AFTER_INSTALL_FILENAME
#: The checkout this step runs from - the folder holding ``tracker/`` - and
#: the one folder the test-cache job may clear inside it (R8).
CHECKOUT = Path(__file__).resolve().parent.parent
TEST_CACHE_DIRNAME = ".pytest_cache"
#: Written by the packaged build beside the app (``Build App.bat``): which
#: commit and which tools made it. The packaged program's identity.
BUILD_INFO_FILENAME = "BUILD-INFO.txt"

#: Why it ran - the three doors, and the deliberate re-run.
REASON_SETUP = "setup"
REASON_LAUNCH = "launch"
REASON_ROOT = "root"
REASON_REPAIR = "repair"
REASONS = (REASON_SETUP, REASON_LAUNCH, REASON_ROOT, REASON_REPAIR)

#: The record check's outcomes, by key, and what each says.
CHECK_CLEAN_KEY = "clean"
CHECK_NO_ROOT_KEY = "no_root"
CHECK_NO_STORE_KEY = "no_store"
CHECK_NOTHING_HELD_KEY = "nothing_held"
CHECK_FOUND_KEY = "found"
CHECK_FAILED_KEY = "failed"
CHECK_CLEAN = "The record check judged {n} record(s) and found nothing to repair."
#: A store that holds no record yet (a fresh one, or one an upgrade set
#: aside): nothing was judged, which is not the same as nothing found.
CHECK_NOTHING_HELD = ("The record check had no record to judge: the store on this computer holds none "
                      "yet, and the first pass judges every line as it builds it.")
CHECK_SKIPPED_NO_ROOT = "The record check waits until the clients folder is chosen in the app."
CHECK_SKIPPED_NO_STORE = ("There is no store on this computer yet; the first pass builds it and judges "
                          "every line as it does.")
CHECK_FOUND = "The record check found {n} line(s) a person must look at:"
#: True for the two kinds it names, and proved for each in
#: ``tests/test_after_install.py``: a malformed line (decision 209, R3b)
#: and a record changed behind the tracker's back (decision 137) stop their
#: household. It claims nothing for any other finding.
FINDINGS_WAIT = ("A household named above as malformed or as changed behind the app's back waits "
                 "in the app until a person repairs it (runbook §9); any other line above is for a "
                 "person to look at. The rest of the practice runs as normal.")

#: The failures, one sentence each, naming the job and what to do.
ROOT_REFUSED = ("The clients folder saved in the app cannot be used ({refusal}); the schedule and the "
                "record check wait until it is chosen again in the app.")
SETTINGS_UNREADABLE = ("The app's settings file could not be read, so neither the schedule nor the "
                       "record check could run; choose the clients folder again in the app.")
SETTINGS_UNWRITABLE = ("The app's settings file ({file}) could not be written, so the schedule choice was "
                       "not saved and nothing was changed. Try again, or check the folder's permissions.")
SCHEDULE_OFF_HERE = ("The schedule is off on this computer; turn it on in Tools > Schedule before "
                     "moving it here.")
PREFERENCE_UNUSABLE = ("The schedule setting in the app's settings file cannot be used ({problem}) No "
                       "schedule was changed. Choose it again in Tools > Schedule.")
#: The schedule key the record holds when the saved choice was refused.
PREFERENCE_KEY = "preference_unusable"
SCHEDULE_FAILED = ("The schedule could not be registered on this computer ({problem}). Start the app: "
                   "it tries again at launch, and Repair the Schedule tries at once.")
DESIGNATION_UNWRITABLE = ("The file naming the computer that runs the schedule ({file}) could not be "
                          "written; no schedule was changed. Start the app: it tries again at launch.")
#: What :data:`SCHEDULE_FAILED` says when the job file could not be written
#: or ``schtasks`` could not be started - the operating system's words are
#: not a sentence for a person.
SCHEDULE_UNREACHABLE = "the job file could not be written, or Task Scheduler could not be started"
#: What the launch door records when the step itself raised something it
#: does not name (the review's N1), so the notice says it rather than the
#: launch dropping it.
LAUNCH_FAILED = ("The after-install step stopped before it finished; the app tries again at its next "
                 "start, and Repair the Schedule tries at once.")
CHECK_FAILED = ("The record check could not run: {problem} Nothing was changed; runbook §6 says what "
                "to do with a store that will not open, and the app tries again at its next start.")
RECORD_UNWRITABLE = ("What the after-install step did could not be recorded in {file}; the app runs it "
                     "again at its next start.")
#: The test-cache job (R8): what it says when it removed something, and
#: when it could not (no operating-system message is quoted).
CACHE_CLEARED_KEY = "cleared"
CACHE_FAILED_KEY = "failed"
CACHE_CLEARED = ("Removed the test cache left in the app's folder by earlier versions (.pytest_cache); "
                 "nothing the app uses was in it.")
CACHE_NOT_CLEARED = ("The test cache left in the app's folder by earlier versions (.pytest_cache) could "
                     "not be removed; the app tries again at its next start.")
#: The setup door's last job (pilot P218, S3): the Overview made ready, so
#: the first one after an install opens at once - console only (Setup
#: prints ``lines``; the app's notice shows findings and failures, never
#: this). ``{why}`` is :func:`tracker.runner.fill_firm_cache`'s own kind
#: sentence.
OVERVIEW_READY = "Made the Overview ready, so the first one after this install opens at once."
OVERVIEW_NOT_READY = ("The Overview could not be made ready ({why}); the first one reads every "
                      "household and takes a little longer.")
#: The one lock every run of the step holds (pilot P47), beside the record;
#: how long a run waits for another to finish, and how often it looks.
LOCK_FILENAME = "after-install.lock"
LOCK_WAIT_SECONDS = 10 * 60
LOCK_POLL_SECONDS = 0.25
#: The step's key, and its one sentence, when another run held the lock
#: for longer than a run waits: nothing was changed and nothing recorded.
BUSY_KEY = "busy"
STEP_BUSY = ("Another run of the after-install step on this computer was still going after {minutes} "
             "minutes, so this one changed nothing on the schedule. A choice just saved stays saved and "
             "takes effect at the next start, or press Repair the Schedule.")
#: The same, when the lock itself could not be made in the data home.
LOCK_UNAVAILABLE = ("The after-install step could not take its lock ({file}), so it changed nothing. "
                    "Start the app: it tries again at launch.")
#: What Setup prints when the step exits 1 (``Setup.bat`` echoes the same words).
SETUP_RETRY = "The after-install step could not finish (above). Start the app: it tries again at launch."


def record_path() -> Path:
    """Where the note of the last run is: beside the store, so it moves
    wherever the store does."""
    return Path(store.store_path()).with_name(RECORD_FILENAME)


def _package_version() -> str:
    """``app/package.json``'s version from a checkout; "" when there is
    none to read (the packaged program, whose build info says it)."""
    try:
        return str(json.loads(settings.PACKAGE_JSON.read_text(encoding="utf-8"))["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def build_info(executable: Path) -> Path | None:
    """The packaged build's :data:`BUILD_INFO_FILENAME`: beside the
    executable, or at the top of the package, where ``Build App.bat``
    writes it (the API's executable sits two folders down, in
    ``resources``). ``None`` when neither is there."""
    for folder in (executable.parent, *executable.parents[1:3]):
        candidate = folder / BUILD_INFO_FILENAME
        if candidate.is_file():
            return candidate
    return None


def program_identity() -> str:
    """Which program this is, as a SHA-256: the interpreter or executable,
    the app's version, the store's schema and - from a checkout - the bytes
    of every module in the package, in path order; when frozen, the build
    info (or, without it, the executable's size and time). A launch whose
    identity matches the record's has nothing to do."""
    digest = hashlib.sha256()

    def part(label: str, data: bytes) -> None:
        digest.update(label.encode("utf-8") + b"\0" + data + b"\0")

    executable = Path(sys.executable).resolve()
    part("executable", str(executable).encode("utf-8", "surrogatepass"))
    part("version", _package_version().encode("utf-8"))
    part("schema", str(store.SCHEMA_VERSION).encode("ascii"))
    if getattr(sys, "frozen", False):
        info = build_info(executable)
        if info is not None:
            part("build", info.read_bytes())
        else:
            stat = executable.stat()
            part("size-and-time", f"{stat.st_size}:{stat.st_mtime_ns}".encode("ascii"))
    else:
        # By full path: a checkout moved to another folder is another
        # program too - the job it registered runs in the old folder.
        for path in sorted(Path(__file__).resolve().parent.rglob("*.py")):
            part(path.as_posix(), path.read_bytes())
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class AfterInstall:
    """What one run did: the schedule's outcome and sentence, the check's,
    every finding and every failure, in the words a person is shown."""

    reason: str
    ran_at: str
    schedule: str
    schedule_sentence: str
    check: str
    check_sentence: str
    #: The computer the designation names when this one registers none
    #: because of it (:data:`scheduling.ELSEWHERE`), for the app's offer to
    #: move the schedule here; else "".
    schedule_host: str = ""
    cache_sentence: str = ""
    #: The setup door's Overview job (P218): :data:`OVERVIEW_READY`,
    #: :data:`OVERVIEW_NOT_READY`, or "" where it did not run.
    overview_sentence: str = ""
    findings: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    program: str = ""
    command: tuple[str, ...] = ()
    xml: str = ""
    lines: tuple[str, ...] = field(default=(), compare=False)

    @property
    def exit_code(self) -> int:
        """0 when every job ran, findings or not; 1 when one could not."""
        return 1 if self.failed else 0

    @property
    def installed(self) -> bool:
        """Whether a task was registered on this computer by this run."""
        return self.schedule in scheduling.REGISTERING and not self.failed_schedule

    @property
    def failed_schedule(self) -> bool:
        return self.schedule_sentence in self.failed

    def reply(self) -> dict:
        """The run as the API hands it to the app."""
        said = asdict(self)
        said.update(lines=list(self.lines), findings=list(self.findings), failed=list(self.failed),
                    command=list(self.command), installed=self.installed, exit=self.exit_code)
        return said


@dataclass(frozen=True, slots=True)
class _Step:
    key: str
    sentence: str
    host: str = ""
    findings: tuple[str, ...] = ()
    failed: bool = False
    command: tuple[str, ...] = ()
    xml: str = ""


def _saved_root() -> tuple[Path | None, str]:
    """The clients root the settings name, held to the door's rule, or the
    one sentence saying why none can be used."""
    try:
        if settings.clients_root() is None:
            return None, ""
        return door.checked_root(), ""
    except settings.SettingsError:
        return None, SETTINGS_UNREADABLE
    except door.DoorError as exc:
        return None, ROOT_REFUSED.format(refusal=exc)


def _saved_preference() -> tuple[scheduling.SchedulePreference | None, str]:
    """The schedule choice the settings file holds, or the one sentence
    saying why none can be used. Never a guess: a choice that is refused
    registers nothing."""
    try:
        return settings.schedule_preference(), ""
    except settings.SettingsError:
        return None, SETTINGS_UNREADABLE
    except scheduling.ScheduleChoiceError as exc:
        return None, PREFERENCE_UNUSABLE.format(problem=exc)


def _save_choice(start: object, every: object) -> str:
    """A start or interval the caller names outright (the command line's
    Repair) is saved first, so the step never registers something the
    Schedule button does not show; "" when saved, else the sentence."""
    try:
        current = settings.schedule_preference()
        settings.set_schedule(current.enabled, current.start if start is None else start,
                              current.every if every is None else every)
    except settings.SettingsError:
        return SETTINGS_UNREADABLE
    except scheduling.ScheduleChoiceError as exc:
        return str(exc)
    except OSError:
        return SETTINGS_UNWRITABLE.format(file=settings.SETTINGS_FILENAME)
    return ""


def _preference_record(preference: scheduling.SchedulePreference | None) -> dict | None:
    """The choice as the record holds it, for :func:`launch` to compare."""
    return None if preference is None else asdict(preference)


def _note_removed(why: str) -> None:
    """Keep on the local debug log that this step removed this computer's
    task, and why (pilot P47): a task that disappears is a question a
    person asks later, and this is its answer."""
    errors.keep("after_install: removed this computer's scheduled task",
                f"{why}; process {os.getpid()}")


def _off() -> _Step:
    """The schedule is switched off: this computer's own task goes, the
    designation is left as it is (turning it off on the designated computer
    leaves no computer running it, which the sentence says), and nothing is
    registered."""
    try:
        if scheduling.remove_task():
            _note_removed("the saved schedule choice is off")
    except RuntimeError as exc:
        return _Step(scheduling.OFF, SCHEDULE_FAILED.format(problem=exc), failed=True)
    except OSError as exc:
        errors.keep("after_install: removing the task", exc)
        return _Step(scheduling.OFF, SCHEDULE_FAILED.format(problem=SCHEDULE_UNREACHABLE), failed=True)
    return _Step(scheduling.OFF, scheduling.SCHEDULE_OFF)


def _schedule(root: Path | None, preference: scheduling.SchedulePreference) -> _Step:
    """The first job: register, re-register, remove, or say why not."""
    if not preference.enabled:
        return _off()
    start, every = preference.start, preference.every
    decision = scheduling.schedule_decision(root)
    outcome = decision.outcome
    if outcome == scheduling.REFUSED_DRIVE:
        # Decision 186: the schedule runs whatever program sits here, every
        # pass - never from a stick or a network drive. Nothing is written.
        return _Step(outcome, decision.sentence, failed=True)
    if outcome == scheduling.NO_ROOT:
        return _Step(outcome, scheduling.SCHEDULE_WAITS_FOR_ROOT)
    if outcome == scheduling.NO_TASK_SCHEDULER:
        return _Step(outcome, scheduling.SCHEDULE_NOT_HERE)
    if outcome == scheduling.UNREADABLE:
        return _Step(outcome, scheduling.DESIGNATION_UNREADABLE.format(
            file=scheduling.designation_file(root)), failed=True)
    if outcome == scheduling.UNNAMED_HOST:
        return _Step(outcome, scheduling.HOST_UNNAMED.format(
            file=scheduling.designation_file(root)), failed=True)
    if outcome == scheduling.CLAIMED:
        # Only the claim writes the designation file, so only its OSError
        # says that file could not be written (the review's S2).
        try:
            scheduling.claim(root)
        except scheduling.DesignationError as exc:
            return _Step(outcome, str(exc), failed=True)
        except OSError as exc:
            errors.keep("after_install: claiming the schedule", exc)
            return _Step(outcome, DESIGNATION_UNWRITABLE.format(
                file=scheduling.designation_file(root)), failed=True)
    try:
        if outcome == scheduling.ELSEWHERE:
            removed = scheduling.remove_task()
            if removed:
                _note_removed(f"the designation names {decision.host}")
            return _Step(outcome, scheduling.SCHEDULE_ELSEWHERE.format(
                host=decision.host, removed=scheduling.SCHEDULE_REMOVED if removed else ""),
                host=decision.host)
        folder = settings.settings_dir()
        command = scheduling.register_here(folder, start=start, every=every)
    except RuntimeError as exc:
        return _Step(outcome, SCHEDULE_FAILED.format(problem=exc), failed=True)
    except OSError as exc:
        errors.keep("after_install: registering the schedule", exc)
        return _Step(outcome, SCHEDULE_FAILED.format(problem=SCHEDULE_UNREACHABLE), failed=True)
    claimed = outcome == scheduling.CLAIMED
    if every:
        sentence = scheduling.SCHEDULE_CLAIMED if claimed else scheduling.SCHEDULE_REGISTERED
    else:
        sentence = scheduling.SCHEDULE_CLAIMED_DAILY if claimed else scheduling.SCHEDULE_REGISTERED_DAILY
    return _Step(outcome, sentence.format(host=decision.host, start=start, every=every),
                 command=tuple(command), xml=str(scheduling.schedule_xml_path()))


def _check(root: Path | None) -> _Step:
    """The second job: decision 187's record check, which changes no
    record, when a root is set and the store is there. Never creates a
    store. Says how many records it judged."""
    if root is None:
        return _Step(CHECK_NO_ROOT_KEY, CHECK_SKIPPED_NO_ROOT)
    if not Path(store.store_path()).is_file():
        return _Step(CHECK_NO_STORE_KEY, CHECK_SKIPPED_NO_STORE)
    try:
        conn = store.connect()
        folders = registry.record_dirs(root)
        findings: list[str] = []
        judged = 0
        for folder in folders:
            try:
                if store.holds(conn, root, folder):
                    judged += 1
                    findings += store.check(conn, root, folder)
            except (ledger.LedgerError, OSError) as exc:
                # A record the reader refuses is that household's to wait
                # on, as the pass makes it: named, and the rest go on.
                # The record's own refusal whole; an OS error by its class
                # (decision 190: its message can spell a client's path), and
                # the whole of it kept on the local debug log, never shown.
                errors.keep("after_install: the record check", exc, name=folder.name)
                findings.append(f"{folder.name}: {errors.said(exc, (ledger.LedgerError,))}")
        findings += store.gone_journals(conn, root)
    except (store.StoreError, ledger.LedgerError, OSError) as exc:
        errors.keep("after_install: the record check", exc)
        problem = errors.said(exc, (store.StoreError, ledger.LedgerError)).rstrip(".") + "."
        return _Step(CHECK_FAILED_KEY, CHECK_FAILED.format(problem=problem), failed=True)
    if not findings and not judged:
        return _Step(CHECK_NOTHING_HELD_KEY, CHECK_NOTHING_HELD)
    if not findings:
        return _Step(CHECK_CLEAN_KEY, CHECK_CLEAN.format(n=judged))
    return _Step(CHECK_FOUND_KEY, CHECK_FOUND.format(n=len(findings)), findings=tuple(findings))


def _ready_the_overview(root: Path | None, reason: str, check: _Step) -> str:
    """The setup door's last job (pilot P218, S3; Q1 for the pilot's own
    installer): ask the firm summary once, so the first Overview after an
    install or an upgrade is warm instead of reading every household.

    **Only the setup door.** The launch door runs beside the app's own
    first Overview, which the app asks at once (P221) - a fill there would
    be a second cold walk of the firm at the same moment; the root door
    and the Repair door are followed at once by an Overview that fills the
    cache likewise. Setup is the one door with no Overview after it.

    **Only with somewhere to read**: a saved root that was not refused and
    a store already on this computer (the check's own rule) - the summary
    of a firm with no store would build one.

    **Never a failure.** The summary is :func:`tracker.runner.fill_firm_cache`
    - the app's own ``firm`` as its own process, the cache's own staleness
    rules, its own time limit - and one that did not finish is a console
    line, never a failed job: the step's identity is still recorded, so the
    app does not run the whole step again at every launch for a cache.
    Returns the sentence, or "" where the job did not run."""
    if reason != REASON_SETUP or root is None or check.key == CHECK_NO_STORE_KEY:
        return ""
    if not Path(store.store_path()).is_file():
        return ""
    # Let go of the store and the checkpoint first (P214): the summary is
    # another process, and nothing of this one's is held across it.
    store.close()
    why = runner.fill_firm_cache(str(root))
    return OVERVIEW_NOT_READY.format(why=why) if why else OVERVIEW_READY


def _is_link(path: Path) -> bool:
    """:func:`tracker.fsio.is_link`, but failing closed: a name that cannot be
    looked at for any reason but being absent raises, so the test-cache delete
    stops rather than going through something it could not prove is no link
    (the package's own test reads an unreadable name as no link)."""
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    return fsio.is_link(path)


def _unlink(path: Path) -> None:
    """Remove one entry - a file or a link - never what a link points at.
    A directory link on Windows (a junction) is removed as a directory
    entry, which removes the link alone."""
    try:
        os.unlink(path)
    except (IsADirectoryError, PermissionError):
        if not _is_link(path):
            raise
        os.rmdir(path)


def _remove_tree(folder: Path) -> None:
    """Remove ``folder`` and everything in it, bottom up, descending only
    into real directories: a link or junction inside is unlinked as an
    entry and never entered."""
    with os.scandir(folder) as scanned:
        entries = list(scanned)
    for entry in entries:
        path = Path(entry.path)
        if not _is_link(path) and entry.is_dir(follow_symlinks=False):
            _remove_tree(path)
        else:
            _unlink(path)
    os.rmdir(folder)


def _clear_test_cache(checkout: Path | None = None) -> _Step | None:
    """The third job (R8): remove ``<checkout>/.pytest_cache``, where
    ``checkout`` is :data:`CHECKOUT` unless a test names its own. ``None``
    when there is nothing to do - the packaged app, or no cache - so it
    says nothing; its sentence when it removed something; a failure, in
    one constant sentence, when it could not."""
    if getattr(sys, "frozen", False):
        return None
    folder = Path(checkout if checkout is not None else CHECKOUT) / TEST_CACHE_DIRNAME
    try:
        if _is_link(folder) or folder.is_file():
            _unlink(folder)
        elif folder.is_dir():
            _remove_tree(folder)
        else:
            return None
    except OSError:
        return _Step(CACHE_FAILED_KEY, CACHE_NOT_CLEARED, failed=True)
    return _Step(CACHE_CLEARED_KEY, CACHE_CLEARED)


class _Busy(Exception):
    """This run could not have the step's lock; the sentence saying why."""


@contextmanager
def _one_at_a_time() -> Iterator[None]:
    """Hold the step's lock (pilot P47) for a ``with`` block, waiting up to
    :data:`LOCK_WAIT_SECONDS` for a run that holds it; :class:`_Busy` when
    it cannot be had. With no data home there is no record to keep either,
    and the run goes on as it always has (its record says it could not be
    written)."""
    try:
        folder = record_path().parent
    except settings.SettingsError:
        folder = None
    if folder is None:
        yield
        return
    lock_file = folder / LOCK_FILENAME
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            held = acquire_lock(folder, LOCK_FILENAME)
            break
        except EngagementLockedError:
            if time.monotonic() >= deadline:
                raise _Busy(STEP_BUSY.format(minutes=LOCK_WAIT_SECONDS // 60)) from None
            time.sleep(LOCK_POLL_SECONDS)
        except OSError as exc:
            errors.keep("after_install: taking the step's lock", exc)
            raise _Busy(LOCK_UNAVAILABLE.format(file=lock_file)) from None
    try:
        yield
    finally:
        release_lock(held)


def _busy(reason: str, sentence: str) -> AfterInstall:
    """A run that could not have the lock: it changed nothing, recorded
    nothing (the run that holds it records), and says why."""
    return AfterInstall(reason=reason, ran_at=dt.datetime.now().isoformat(timespec="seconds"),
                        schedule=BUSY_KEY, schedule_sentence=sentence, check=BUSY_KEY,
                        check_sentence=sentence, failed=(sentence,), lines=(sentence,))


def run(*, reason: str, start: str | None = None, every: int | None = None,
        checkout: Path | None = None) -> AfterInstall:
    """Every one-time job, in order, and the record of what they did - one
    run at a time (pilot P47): the step's lock is held from before the
    saved choice is read until the record is written."""
    if reason not in REASONS:
        raise ValueError(f"reason must be one of {', '.join(REASONS)}, not {reason!r}")
    try:
        with _one_at_a_time():
            return _run(reason=reason, start=start, every=every, checkout=checkout)
    except _Busy as busy:
        return _busy(reason, str(busy))


def _run(*, reason: str, start: str | None = None, every: int | None = None,
         checkout: Path | None = None) -> AfterInstall:
    """Every one-time job, in order, and the record of what they did.

    The schedule registers the choice saved in the settings file (pilot
    P21) - on or off, the first run's time, how often - so every door
    registers what the Schedule button shows. ``start`` and ``every``, when
    a caller names them outright (the command line's Repair), are checked
    and saved first.

    Idempotent: registering is ``schtasks /create ... /f``, the check
    changes no record, and the note is replaced whole - twice in a row is
    once. The caller holds the step's lock.
    """
    ran_at = dt.datetime.now().isoformat(timespec="seconds")
    unusable = _save_choice(start, every) if start is not None or every is not None else ""
    preference, unreadable = _saved_preference()
    root, refused = _saved_root()
    if refused:
        schedule = _Step(scheduling.NO_ROOT, refused, failed=True)
        check = _Step(CHECK_FAILED_KEY, refused, failed=True)
    else:
        if preference is None or unusable:
            schedule = _Step(PREFERENCE_KEY, unusable or unreadable, failed=True)
        else:
            schedule = _schedule(root, preference)
        check = _check(root)
    cache = _clear_test_cache(checkout)
    # The last job before the record (P218, S3): never a failure.
    overview = "" if refused else _ready_the_overview(root, reason, check)
    failed = list(dict.fromkeys(step.sentence for step in (schedule, check, cache)
                                if step is not None and step.failed))
    identity = "" if failed else program_identity()
    now = designation_now(root)
    try:
        path = record_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomically(path, {
            "program": identity, "ran_at": ran_at, "reason": reason, "schedule": schedule.key,
            "designated": now if isinstance(now, str) else None,
            "preference": _preference_record(preference),
            "findings": list(check.findings), "failed": failed,
        })
    except OSError:
        failed.append(RECORD_UNWRITABLE.format(file=record_path()))
        identity = ""
    lines = [schedule.sentence]
    if check.sentence != schedule.sentence:
        lines.append(check.sentence)
    lines += [f"  {finding}" for finding in check.findings]
    if check.findings:
        lines.append(FINDINGS_WAIT)
    if cache is not None and not cache.failed:
        lines.append(cache.sentence)
    if overview:
        lines.append(overview)
    lines += [sentence for sentence in failed if sentence not in lines]
    return AfterInstall(reason=reason, ran_at=ran_at, schedule=schedule.key,
                        schedule_sentence=schedule.sentence, check=check.key,
                        check_sentence=check.sentence, schedule_host=schedule.host,
                        cache_sentence=cache.sentence if cache is not None else "",
                        overview_sentence=overview,
                        findings=check.findings,
                        failed=tuple(failed), program=identity, command=schedule.command,
                        xml=schedule.xml, lines=tuple(lines))


def read_record() -> dict | None:
    """The note of the last run, or ``None`` when there is none a program
    could trust (missing, unreadable, not one object) - which is the same as
    never having run."""
    try:
        data = json.loads(record_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


#: What :func:`designation_now` says of a file that names no computer it
#: can read: never equal to anything a record holds, so the step runs.
_UNREADABLE_NOW = object()


def designation_now(root: Path | None) -> str | None | object:
    """The computer the designation file under ``root`` names now: its
    name, ``None`` when there is no root or no file, or a marker equal to
    nothing when the file is not one computer's name. One small file read
    (the review's M1: well under a millisecond)."""
    if root is None:
        return None
    try:
        return scheduling.designated_machine(root)
    except scheduling.DesignationError:
        return _UNREADABLE_NOW


def launch() -> AfterInstall | None:
    """The app's launch door: nothing when this program is the one that
    last ran the step cleanly, **and** the designation names the computer
    it named then, **and** a task it registered here is still there;
    otherwise the step, as a launch. The second
    condition is the review's M1: after the schedule moves to a new
    computer nothing about the old one's program changed, and without it
    the old computer kept its task - two computers running the pass -
    until its next upgrade. The third is P198 (F6): on the computer that
    registered the schedule, the task itself must still be there - an
    uninstall deletes it and keeps the note. Compared and run under the
    step's lock (pilot P47), so what it compares is not changing under it."""
    try:
        with _one_at_a_time():
            if _unchanged(read_record()):
                return None
            return _run(reason=REASON_LAUNCH)
    except _Busy as busy:
        return _busy(REASON_LAUNCH, str(busy))


def _unchanged(record: dict | None) -> bool:
    """Whether the program, the designation and the saved choice are all
    what ``record`` says the last clean run left - and, where it registered
    the schedule, the task is still there (:func:`_task_missing`, asked
    last so a launch that runs the step anyway never asks)."""
    if record is None or record.get("program") != program_identity():
        return False
    root, refused = _saved_root()
    now = None if refused else designation_now(root)
    preference, _ = _saved_preference()
    return (now is not _UNREADABLE_NOW and record.get("designated") == now
            and preference is not None and record.get("preference") == _preference_record(preference)
            and not _task_missing(record))


def _task_missing(record: dict) -> bool:
    """Whether the task the last clean run registered on this computer is
    gone (P198, F6). Asked only when ``record`` says this computer claimed
    or registered the schedule - the designation already matched it, so a
    computer the designation does not name, a schedule that is off, no root
    and no Task Scheduler expect no task and are never asked (decision 159,
    M1). One ``schtasks /query`` on the designated computer, in the launch
    step's background run.

    Anything but "it exists" is missing: a query that fails runs the step,
    whose ``/create /f`` either registers the task again or says in
    :data:`SCHEDULE_FAILED` why it cannot - never a silent skip. A
    ``schtasks`` that cannot be started, or that does not answer within its
    limit (:data:`tracker.scheduling.SCHTASKS_TIME_LIMIT_SECONDS`), is kept
    on the local error log and runs the step the same way; the step's own
    ``schtasks`` then says it as :data:`SCHEDULE_UNREACHABLE`. A query that
    is refused keeps its exit code on the error log, once per start (the
    engine review's NIT-2), so a task registered again at every start has
    its reason written down."""
    if record.get("schedule") not in scheduling.REGISTERING:
        return False
    try:
        code = scheduling.task_query()
    except OSError as exc:
        errors.keep(ASKING_FOR_THE_TASK, exc)
        return True
    if code:
        errors.keep(ASKING_FOR_THE_TASK, QUERY_REFUSED.format(code=code))
    return code != 0


#: Where the launch's question to Task Scheduler is said on the error log.
ASKING_FOR_THE_TASK = "after_install: asking whether the scheduled task exists"
#: A refused query, by its exit code only: ``schtasks``'s own words are not kept.
QUERY_REFUSED = "schtasks /query refused with exit code {code}; the step runs to register the task again"


def record_failure(sentence: str) -> None:
    """Record a launch the step could not finish, in ``sentence`` - one of
    this module's constants - so the first screen's notice says it and the
    next launch tries again (no identity is recorded). The API's launch
    door calls it for anything :func:`launch` raised (the review's N1). A
    note that cannot be written either is left: the next launch runs the
    step again all the same."""
    try:
        path = record_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomically(path, {
            "program": "", "ran_at": dt.datetime.now().isoformat(timespec="seconds"),
            "reason": REASON_LAUNCH, "schedule": "", "designated": None, "findings": [],
            "failed": [sentence],
        })
    except OSError:
        pass


def notice() -> dict | None:
    """What the app's first screen shows, from the note of the last run:
    its findings and failures while there are any, else ``None``. Not
    dismissible - it is true until a later run finds nothing. With no data
    home to hold the note (decision 186's review, M1) there is none to show:
    the first screen's ``machine_warnings`` already says why, and ``list``
    still arrives."""
    try:
        record = read_record()
    except settings.SettingsError:
        return None
    if record is None:
        return None
    findings = [str(one) for one in record.get("findings") or [] if isinstance(one, str)]
    failed = [str(one) for one in record.get("failed") or [] if isinstance(one, str)]
    if not findings and not failed:
        return None
    return {"findings": findings, "failed": failed, "ran_at": str(record.get("ran_at") or ""),
            "wait": FINDINGS_WAIT if findings else ""}


def move_schedule_here() -> tuple[str, bool]:
    """``--move-schedule-here`` and the API's ``move-schedule-here``: name
    this computer in the designation file; the sentence saying which
    computer it replaces, and whether the file was written. The caller then
    runs the step, so this computer registers; the old one removes its own
    task at its next start, because the file no longer names what its
    record says it named (:func:`launch`).

    A program on a removable, network or unnamed drive (decision 186) is
    asked first and changes nothing: a move from a stick would name this
    computer, register no task here, and the old one would remove its own
    at its next start - no computer would run the schedule (the merge
    review's SF2)."""
    if refusal := settings.program_drive_refusal():
        return refusal, False
    root, refused = _saved_root()
    if refused:
        return refused, False
    if root is None:
        return scheduling.SCHEDULE_WAITS_FOR_ROOT, False
    preference, _ = _saved_preference()
    if preference is not None and not preference.enabled:
        return SCHEDULE_OFF_HERE, False
    try:
        moved = scheduling.move_here(root)
    except scheduling.DesignationError as exc:
        return str(exc), False
    except OSError:
        return DESIGNATION_UNWRITABLE.format(file=scheduling.designation_file(root)), False
    here = this_host()
    if moved.unreadable:
        return scheduling.MOVED_FROM_UNREADABLE.format(here=here), True
    if moved.before is None:
        return scheduling.MOVED_FROM_NOBODY.format(here=here), True
    return scheduling.MOVED_FROM.format(host=moved.before, here=here), True


#: The pilot installer's door asks for :func:`installer_exit_code` instead
#: of :attr:`AfterInstall.exit_code`; ``api_entry``'s setup mode passes it.
INSTALLER_CODES_FLAG = "--installer-codes"


def installer_exit_code(result: AfterInstall) -> int:
    """What the pilot installer reads to show its failure window (Jason,
    2026-10-08): :data:`runner.SETUP_STEP_FAILED` when a job could not run,
    :data:`runner.SETUP_OVERVIEW_NOT_READY` when every job ran but the
    setup door's Overview could not be prepared, else 0. The Overview is
    still never a failed job (``exit_code`` is untouched, so ``Setup.bat``
    and the app's own doors see what they always saw): only the installer
    is told, so a person installing knows the first Overview will be slow."""
    if result.failed:
        return runner.SETUP_STEP_FAILED
    if result.overview_sentence and result.overview_sentence != OVERVIEW_READY:
        return runner.SETUP_OVERVIEW_NOT_READY
    return 0


def main(argv: list[str]) -> int:
    """``python -m tracker.after_install``: the step, and its exit code.

    Here, in the imported module, not in the ``__main__`` block: a block
    run by ``runpy`` is a second copy of the module with its own globals,
    so a test that points :data:`CHECKOUT` at a fabricated folder never
    reached it, and the suite cleared this checkout's real test cache (the
    re-review's MF1). One module, one set of globals."""
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a finding can name a client's folder

    parser = argparse.ArgumentParser(
        prog="python -m tracker.after_install",
        description="Run every one-time step after installing or upgrading: register the "
                    "schedule on the computer that runs it, check the record, clear the "
                    "test cache earlier versions left, and make the Overview ready.")
    parser.add_argument("--reason", choices=REASONS, default=REASON_SETUP,
                        help="which door ran it (default: setup)")
    parser.add_argument("--move-schedule-here", action="store_true",
                        help="make this computer the one that runs the schedule for the clients "
                             "folder, then register it here (a deliberate move, runbook section 6)")
    parser.add_argument(INSTALLER_CODES_FLAG, action="store_true",
                        help="exit with the pilot installer's codes: 10 when the step could not "
                             "finish, 11 when the Overview could not be prepared")
    ns = parser.parse_args(argv)
    try:
        if ns.move_schedule_here:
            said, moved = move_schedule_here()
            print(said)
            if not moved:
                return 1
        result = run(reason=REASON_REPAIR if ns.move_schedule_here else ns.reason)
    finally:
        store.close()
    for line in result.lines:
        print(line)
    return installer_exit_code(result) if ns.installer_codes else result.exit_code


if __name__ == "__main__":
    from tracker.after_install import main as _main

    raise SystemExit(_main(sys.argv[1:]))
