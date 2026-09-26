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
   is not one computer's name, or a ``schtasks`` that refuses, is a
   failure.
2. **The record check** - decision 187's ``store.check`` for every folder
   with a record, and ``store.gone_journals``, as the store's command line
   runs them; read-only. It runs only when a root is set **and** the store
   file is there: this step never creates a store (a fresh machine's first
   pass builds it and judges every line as it goes). A folder the store has
   never met is left to that same first catch-up rather than named - its
   lines were never applied, so there is nothing an earlier version let
   through, and after a store set aside by an upgrade every return would
   otherwise be named at once.

**A finding is not a failure.** The check naming a line is the step doing
its job: exit 0, the finding printed at the end of Setup and shown in the
app until a later run finds nothing. Exit 1 only when a job could not run
at all, each in one plain sentence naming the job - never a traceback, and
never the content of a file a person or a sync client wrote.

**Three doors, one function.** ``Setup.bat`` runs it last (``--reason
setup``); the app runs it at every launch through the API's
``after-install`` command, which returns at once when the program is the
one that last ran it cleanly (:func:`program_identity` against the
record) - that is what makes the packaged app, which has no Setup, and a
source checkout updated by a pull that left the locks alone, run it once;
and saving the clients root runs it, so the first root saved on the
office computer registers the schedule with no button. The app's
**Repair the schedule** runs it deliberately.

**It records what it did** beside the store, in :data:`RECORD_FILENAME`,
as the scheduled pass records its own note beside the store: the program
identity only when nothing failed, so a run that failed is tried again at
the next launch.

It imports ``scheduling`` and the layers below it; the API imports it, and
nothing lower does (layer 4, ``tests/test_layers.py``).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tracker import door, ledger, registry, scheduling, settings, store
from tracker.fsio import write_json_atomically
from tracker.locking import this_host

#: The note of the last run, beside the store.
RECORD_FILENAME = "after-install.json"
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
CHECK_FOUND_KEY = "found"
CHECK_FAILED_KEY = "failed"
CHECK_CLEAN = "The record check found nothing to repair."
CHECK_SKIPPED_NO_ROOT = "The record check waits until the clients folder is chosen in the app."
CHECK_SKIPPED_NO_STORE = ("There is no store on this computer yet; the first pass builds it and judges "
                          "every line as it does.")
CHECK_FOUND = "The record check found {n} line(s) a person must look at:"
FINDINGS_WAIT = ("These households wait in the app until a person repairs them (runbook §9); the rest "
                 "of the practice runs as normal.")

#: The failures, one sentence each, naming the job and what to do.
ROOT_REFUSED = ("The clients folder saved in the app cannot be used ({refusal}); the schedule and the "
                "record check wait until it is chosen again in the app.")
SETTINGS_UNREADABLE = ("The app's settings file could not be read, so neither the schedule nor the "
                       "record check could run; choose the clients folder again in the app.")
SCHEDULE_FAILED = ("The schedule could not be registered on this computer ({problem}). Start the app: "
                   "it tries again at launch, and Repair the schedule tries at once.")
DESIGNATION_UNWRITABLE = ("The file naming the computer that runs the schedule ({file}) could not be "
                          "written; no schedule was changed. Start the app: it tries again at launch.")
CHECK_FAILED = ("The record check could not run: {problem} Nothing was changed; runbook §6 says what "
                "to do with a store that will not open, and the app tries again at its next start.")
RECORD_UNWRITABLE = ("What the after-install step did could not be recorded in {file}; the app runs it "
                     "again at its next start.")
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


def _schedule(root: Path | None, start: str, every: int) -> _Step:
    """The first job: register, re-register, remove, or say why not."""
    decision = scheduling.schedule_decision(root)
    outcome = decision.outcome
    if outcome == scheduling.NO_ROOT:
        return _Step(outcome, scheduling.SCHEDULE_WAITS_FOR_ROOT)
    if outcome == scheduling.NO_TASK_SCHEDULER:
        return _Step(outcome, scheduling.SCHEDULE_NOT_HERE)
    if outcome == scheduling.UNREADABLE:
        return _Step(outcome, scheduling.DESIGNATION_UNREADABLE.format(
            file=scheduling.designation_file(root)), failed=True)
    try:
        if outcome == scheduling.ELSEWHERE:
            removed = scheduling.remove_task()
            return _Step(outcome, scheduling.SCHEDULE_ELSEWHERE.format(
                host=decision.host, removed=scheduling.SCHEDULE_REMOVED if removed else ""))
        if outcome == scheduling.CLAIMED:
            scheduling.claim(root)
        folder = settings.settings_dir()
        command = scheduling.register_here(folder, start=start, every=every)
    except scheduling.DesignationError as exc:
        return _Step(scheduling.UNREADABLE, str(exc), failed=True)
    except RuntimeError as exc:
        return _Step(outcome, SCHEDULE_FAILED.format(problem=exc), failed=True)
    except OSError:
        return _Step(outcome, DESIGNATION_UNWRITABLE.format(file=scheduling.designation_file(root)),
                     failed=True)
    sentence = (scheduling.SCHEDULE_CLAIMED if outcome == scheduling.CLAIMED
                else scheduling.SCHEDULE_REGISTERED)
    return _Step(outcome, sentence.format(host=decision.host, start=start, every=every),
                 command=tuple(command), xml=str(scheduling.schedule_xml_path(folder)))


def _check(root: Path | None) -> _Step:
    """The second job: decision 187's record check, read-only, when a root
    is set and the store is there. Never creates a store."""
    if root is None:
        return _Step(CHECK_NO_ROOT_KEY, CHECK_SKIPPED_NO_ROOT)
    if not Path(store.store_path()).is_file():
        return _Step(CHECK_NO_STORE_KEY, CHECK_SKIPPED_NO_STORE)
    try:
        conn = store.connect()
        folders = registry.record_dirs(root)
        findings: list[str] = []
        for folder in folders:
            try:
                if store.holds(conn, root, folder):
                    findings += store.check(conn, root, folder)
            except (ledger.LedgerError, OSError) as exc:
                # A record the reader refuses is that household's to wait
                # on, as the pass makes it: named, and the rest go on.
                findings.append(f"{folder.name}: {exc}")
        findings += store.gone_journals(conn, root)
    except (store.StoreError, ledger.LedgerError, OSError) as exc:
        problem = str(exc).rstrip(".") + "."
        return _Step(CHECK_FAILED_KEY, CHECK_FAILED.format(problem=problem), failed=True)
    if not findings:
        return _Step(CHECK_CLEAN_KEY, CHECK_CLEAN)
    return _Step(CHECK_FOUND_KEY, CHECK_FOUND.format(n=len(findings)), findings=tuple(findings))


def run(*, reason: str, start: str = scheduling.DEFAULT_START,
        every: int = scheduling.DEFAULT_REPEAT_MINUTES) -> AfterInstall:
    """Every one-time job, in order, and the record of what they did.

    Idempotent: registering is ``schtasks /create ... /f``, the check only
    reads, and the record is replaced whole - twice in a row is once.
    """
    if reason not in REASONS:
        raise ValueError(f"reason must be one of {', '.join(REASONS)}, not {reason!r}")
    ran_at = dt.datetime.now().isoformat(timespec="seconds")
    root, refused = _saved_root()
    if refused:
        schedule = _Step(scheduling.NO_ROOT, refused, failed=True)
        check = _Step(CHECK_FAILED_KEY, refused, failed=True)
    else:
        schedule = _schedule(root, start, every)
        check = _check(root)
    failed = list(dict.fromkeys(step.sentence for step in (schedule, check) if step.failed))
    identity = "" if failed else program_identity()
    try:
        path = record_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomically(path, {
            "program": identity, "ran_at": ran_at, "reason": reason, "schedule": schedule.key,
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
    lines += [sentence for sentence in failed if sentence not in lines]
    return AfterInstall(reason=reason, ran_at=ran_at, schedule=schedule.key,
                        schedule_sentence=schedule.sentence, check=check.key,
                        check_sentence=check.sentence, findings=check.findings,
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
    return data if isinstance(data, dict) else None


def launch() -> AfterInstall | None:
    """The app's launch door: nothing, at once, when this program is the
    one that last ran the step cleanly; otherwise the step, as a launch."""
    record = read_record()
    if record is not None and record.get("program") == program_identity():
        return None
    return run(reason=REASON_LAUNCH)


def notice() -> dict | None:
    """What the app's first screen shows, from the note of the last run:
    its findings and failures while there are any, else ``None``. Not
    dismissible - it is true until a later run finds nothing."""
    record = read_record()
    if record is None:
        return None
    findings = [str(one) for one in record.get("findings") or [] if isinstance(one, str)]
    failed = [str(one) for one in record.get("failed") or [] if isinstance(one, str)]
    if not findings and not failed:
        return None
    return {"findings": findings, "failed": failed, "ran_at": str(record.get("ran_at") or ""),
            "wait": FINDINGS_WAIT if findings else ""}


def move_schedule_here() -> tuple[str, bool]:
    """``--move-schedule-here``: name this computer in the designation
    file; the sentence saying which computer it replaces, and whether the
    file was written. The caller then runs the step, so this computer
    registers; the old one removes its own task the next time it runs it."""
    root, refused = _saved_root()
    if refused:
        return refused, False
    if root is None:
        return scheduling.SCHEDULE_WAITS_FOR_ROOT, False
    try:
        before = scheduling.move_here(root)
    except OSError:
        return DESIGNATION_UNWRITABLE.format(file=scheduling.designation_file(root)), False
    here = this_host()
    if before is None:
        return scheduling.MOVED_FROM_NOBODY.format(here=here), True
    return scheduling.MOVED_FROM.format(host=before, here=here), True


if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a finding can name a client's folder

    parser = argparse.ArgumentParser(
        prog="python -m tracker.after_install",
        description="Run every one-time step after installing or upgrading: register the "
                    "schedule on the computer that runs it, and check the record.")
    parser.add_argument("--reason", choices=REASONS, default=REASON_SETUP,
                        help="which door ran it (default: setup)")
    parser.add_argument("--move-schedule-here", action="store_true",
                        help="make this computer the one that runs the schedule for the clients "
                             "folder, then register it here (a deliberate move, runbook section 6)")
    ns = parser.parse_args()
    try:
        if ns.move_schedule_here:
            said, moved = move_schedule_here()
            print(said)
            if not moved:
                raise SystemExit(1)
        result = run(reason=REASON_REPAIR if ns.move_schedule_here else ns.reason)
    finally:
        store.close()
    for line in result.lines:
        print(line)
    raise SystemExit(result.exit_code)
