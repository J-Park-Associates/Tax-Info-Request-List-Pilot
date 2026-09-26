"""Generate the scheduled job that runs the tracker unattended (component 10).

Emits a Windows Task Scheduler job definition, or the n8n equivalent, for::

    python -m tracker.runner --settings <the app's settings folder> --log

**The job names no clients root** (decision 131). The root has one home,
the settings file beside the app, and the job reads it from there at every
run. It used to be a second home - quoted into the job's command line when
the job was registered - so a root changed in the app left the job
walking the old one, red every night, until somebody remembered to press
the button again. Now changing the root in the app is enough.

**One task, not two.** The runner decides for itself whether today is the day
to draft reminders (``tracker.runner.DRAFT_WEEKDAY``), so the schedule does not
need a second weekly job — a single daily task files, scans, and quietly drafts
the chase emails when that day comes around. Keeping the day in one tested function beats keeping
it in a calendar entry nobody can read, and it means a run that Task Scheduler
misses (laptop closed on the draft day) still drafts when it next runs, rather than
skipping the week.

Paths differ on every machine, so the definition is generated rather than
committed: point it at the Python you use and the app's settings folder
(the one whose settings file names the clients root), and ``--install``
registers it with Task Scheduler in the same
step (``schtasks /create /xml ... /f``, so re-running is also how you change
the schedule). The packaged app has no Python: it registers the app's own
API executable in runner mode
(``tracker.runner.RUNNER_MODE_FLAG``, dispatched by ``api_entry.py`` before
the API - and this module - is imported, so the job needs none of the
environment the Electron shell gives the API). ``TASK_NAME`` is read at
import from ``settings.product_name()``; that is safe because the only
process that imports this module is the API the shell launched with the
product name in its environment, or a source checkout beside ``app/package.json``.

Nothing generated here sends email. The scheduled command files documents,
updates the manifest and writes draft text files; a person still sends them.

**Which computer runs the schedule is one file** (decision 209). Setup, the
app's first start after an upgrade and the first clients root saved all
register the task through :func:`register_here` - but only on the computer
the designation file names (``layout.designation_file``, in the firm's
private tree, which every desk that has the root syncs). The first Windows
computer to register claims it; any other registers none and removes its
own; moving is one deliberate command on the new machine
(``python -m tracker.after_install --move-schedule-here``). Before this,
the question was answered by a function named for "the scheduling host"
whose body asked only "is this Windows": every Windows desk that pressed
the button got a second unattended pass. It is renamed
:func:`task_scheduler_here` so the name says only what it answers.

The file is **checked when it is written, read and acted on**: one
machine name as ``locking.this_host`` normalises it, or
:data:`DESIGNATION_UNREADABLE` - a failure, never a guess, and never the
file's content quoted back (it is whatever a person or a sync client left
there). **Residual risk, stated plainly:** the designation is detection,
not a lock. Two desks that both set a root before the sync client carries
the first claim can both claim; Drive then keeps one file and renames the
other ("... (1).txt"), which nothing reads. The runbook's one-machine rule
still holds; the file makes following it the default. A pass on a
computer the file does not name is not refused here - that is the runner's
question, left to its own decision.

``schtasks`` is local and run through :mod:`subprocess` alone
(:func:`_schtasks`, the one seam the tests replace); nothing here reaches
the network.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from xml.sax.saxutils import escape

from tracker.fsio import write_text_atomically
from tracker.layout import designation_file
from tracker.locking import RUN_TIME_LIMIT_SECONDS, this_host
from tracker.runner import DRAFT_DAY_NAME, LOG_FLAG, RUNNER_MODE_FLAG, SETTINGS_FLAG
from tracker.settings import SETTINGS_FILENAME, product_name

#: The scheduled task is named after the product, wherever that is set.
TASK_NAME = product_name()
DEFAULT_START = "07:00"
#: Filing and scanning repeat through the day this often (minutes); the
#: reminder still drafts only on the drafting day. 0 = once a day.
DEFAULT_REPEAT_MINUTES = 120
#: The generated Task Scheduler definition, beside the app's settings.
SCHEDULE_XML_FILENAME = "tax-tracker.xml"
#: Any date in the past will do for a daily trigger; it is when the series began.
_START_BOUNDARY_DATE = "2026-01-01"


def iso_duration(seconds: int) -> str:
    """The ISO-8601 duration Task Scheduler's schema reads: ``PT2H``, or ``PT90M``
    when the seconds are not whole hours."""
    minutes, remainder = divmod(int(seconds), 60)
    if remainder:
        raise ValueError(f"a task limit is whole minutes, not {seconds}s")
    hours, minutes = divmod(minutes, 60)
    return f"PT{hours}H" if hours and not minutes else f"PT{hours * 60 + minutes}M"


#: The job never overruns the next daily start - and a lock is presumed dead
#: only after this (tracker.locking derives STALE_LOCK_SECONDS from the same
#: number), so the limit is the lock's, rendered here rather than typed twice.
EXECUTION_TIME_LIMIT = iso_duration(RUN_TIME_LIMIT_SECONDS)


def start_hour(start_time: str = DEFAULT_START) -> int:
    """The hour of an ``HH:MM`` start time - the n8n form of the same default."""
    return int(start_time.split(":")[0])


#: The two n8n nodes the workflow is made of; the connection names them again.
TASK_XML_NAMESPACE = "http://schemas.microsoft.com/windows/2004/02/mit/task"
N8N_TRIGGER_NODE = "Every day"
N8N_RUN_NODE = "File, scan, draft"
#: How a person is told to install the schedule, wherever they are told.
#: Task Scheduler imports XML in this encoding; the declaration and both
#: writers (CLI and app) say so from here.
SCHEDULE_XML_ENCODING = "utf-16"
#: How the scheduler module is invoked, for every hint that says so.
MODULE_INVOCATION = "python -m tracker.scheduling"
INSTALL_FLAG = "--install"
OUT_FLAG = "--out"
FORMAT_FLAG = "--format"
START_FLAG = "--start"
FORMAT_XML = "xml"
FORMAT_N8N = "n8n"
FORMATS = (FORMAT_XML, FORMAT_N8N)
INSTALL_HINT = f"{MODULE_INVOCATION} {INSTALL_FLAG}"

def task_scheduler_here() -> bool:
    """Whether this computer has Task Scheduler at all - that is, whether it
    is Windows. Nothing more: whether this is the computer that *runs* the
    schedule is :func:`schedule_decision`'s question (decision 209)."""
    import platform

    return platform.system() == "Windows"


def runner_arguments(settings_dir: str | Path, *, frozen: bool = False) -> str:
    """The one command line the scheduled job runs, whoever schedules it.

    After the program that runs it: ``-m tracker.runner`` for a Python
    checkout, ``RUNNER_MODE_FLAG`` for the packaged app's own executable
    (``api_entry.py`` in runner mode). The runner's arguments are the same
    either way; only the way in differs.

    It names the app's settings folder and **no clients root** (decision
    131): the runner reads the root from the settings file there at every
    run, so the root has one home.
    """
    program = RUNNER_MODE_FLAG if frozen else "-m tracker.runner"
    return f'{program} {SETTINGS_FLAG} {quote_argument(settings_dir)} {LOG_FLAG}'


def quote_argument(value: str | Path) -> str:
    """``value`` as one quoted Windows command-line argument.

    A drive root (``D:\\``) or a share (``\\\\server\\share\\``) ends in a
    backslash, and ``"D:\\"`` reads to the Windows argument parser as an
    escaped quote: the job would receive ``D:" --log`` as its one argument
    and refuse the clients folder every run. A backslash before the closing
    quote is doubled, which is what the parser undoes.
    """
    text = str(value)
    if text.endswith("\\"):
        trailing = len(text) - len(text.rstrip("\\"))
        text += "\\" * trailing
    return f'"{text}"'


#: What a value in the n8n command may not hold, by what it is (D-11): each
#: means one thing to ``cmd`` and another to ``sh``, or ends the quoting in
#: one of them, so a command holding it would not read the same in both.
#: A Windows path cannot hold ``"``, so refusing these loses nothing real.
SHELL_SPECIAL = (
    ('"', "a double quote"),
    ("%", "a percent sign"),
    ("$", "a dollar sign"),
    ("`", "a backtick"),
    ("!", "an exclamation mark"),
)


def refuse_shell_special(field: str, value: str | Path) -> None:
    """Refuse ``value`` if it holds a character ``cmd`` and ``sh`` read differently.

    The ``ValueError`` names the field and the kind of character, never the
    value: a path can carry a client's name, and an error is printed.
    """
    text = str(value)
    for char, kind in SHELL_SPECIAL:
        if char in text:
            raise ValueError(f"{field} holds {kind}, which a shell would read as something else")
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise ValueError(f"{field} holds a control character, which a shell would read as something else")


def _xml_escape(value: str) -> str:
    return escape(str(value))


def _settings_file(settings: str | Path) -> str:
    """The settings file inside the settings folder, spelled in the folder's
    own flavour - the job is generated for Windows, from anywhere."""
    text = str(settings)
    windows = bool(PureWindowsPath(text).drive) or text.startswith("\\\\")
    flavour = PureWindowsPath if windows else PurePosixPath
    return str(flavour(text) / SETTINGS_FILENAME)


def is_absolute_path(text: str) -> bool:
    """True for an absolute path in *either* flavour, whatever OS we are on.

    The job is generated for Windows but may well be generated from anywhere,
    and ``pathlib`` on Linux does not consider ``D:\\Clients`` absolute — which
    would silently graft the working directory onto the front of it.
    """
    return PureWindowsPath(text).is_absolute() or PurePosixPath(text).is_absolute()


def resolve_folder(folder: str, working_dir: str) -> str:
    """A folder the command line was given, as the scheduled job will see it
    - the app's settings folder since decision 131.

    A relative folder hangs off the working directory, joined in the
    flavour of that directory so a Windows task never ends up with a mixed
    separator.
    """
    if is_absolute_path(folder):
        return folder
    flavour = PureWindowsPath if is_absolute_path(working_dir) and (
        PureWindowsPath(working_dir).drive or working_dir.startswith("\\\\")
    ) else PurePosixPath
    return str(flavour(working_dir) / folder)


def task_scheduler_xml(
    *,
    python: str | Path,
    settings: str | Path,
    working_dir: str | Path,
    start_time: str = DEFAULT_START,
    repeat_minutes: int = 0,
    author: str = "",
    task_name: str = TASK_NAME,
    frozen: bool = False,
) -> str:
    """A Windows Task Scheduler definition, ready for ``schtasks /create /xml``.

    ``repeat_minutes`` adds an intra-day repetition so filing and scanning can
    run through the day; the reminder step still only drafts on ``DRAFT_WEEKDAY``.
    ``frozen`` means ``python`` is the packaged app's executable, run in
    runner mode (see :func:`runner_arguments`). ``settings`` is the app's
    settings folder: the job reads the clients root from the settings file
    there at every run (decision 131).
    """
    settings_file = _settings_file(settings)
    if repeat_minutes and repeat_minutes < 5:
        raise ValueError("repeat_minutes below 5 would stack runs on top of each other")
    draft_day = DRAFT_DAY_NAME.capitalize()
    repetition = ""
    if repeat_minutes:
        repetition = (
            "\n      <Repetition>"
            f"\n        <Interval>PT{repeat_minutes}M</Interval>"
            "\n        <Duration>P1D</Duration>"
            "\n        <StopAtDurationEnd>true</StopAtDurationEnd>"
            "\n      </Repetition>"
        )

    return f"""<?xml version="1.0" encoding="{SCHEDULE_XML_ENCODING.upper()}"?>
<Task version="1.4" xmlns="{TASK_XML_NAMESPACE}">
  <RegistrationInfo>
    <Author>{_xml_escape(author)}</Author>
    <Description>Files and scans every engagement under the clients root named in {_xml_escape(settings_file)}.
On {draft_day}s it also drafts the client reminder emails. It never sends them.</Description>
    <URI>\\{_xml_escape(task_name)}</URI>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{_START_BOUNDARY_DATE}T{_xml_escape(start_time)}:00</StartBoundary>
      <Enabled>true</Enabled>{repetition}
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>{EXECUTION_TIME_LIMIT}</ExecutionTimeLimit>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <WakeToRun>false</WakeToRun>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{_xml_escape(python)}</Command>
      <Arguments>{_xml_escape(runner_arguments(settings, frozen=frozen))}</Arguments>
      <WorkingDirectory>{_xml_escape(working_dir)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def n8n_workflow(
    *,
    python: str | Path,
    settings: str | Path,
    working_dir: str | Path,
    hour: int | None = None,
    task_name: str = TASK_NAME,
    frozen: bool = False,
) -> dict:
    """An n8n workflow: one cron trigger into one Execute Command node.

    n8n runs the command through the host's shell - ``cmd`` on Windows,
    ``sh`` elsewhere - so the one line has to read the same in both (D-11).
    Every value is quoted by the rule the settings folder is
    (:func:`quote_argument`), and a value holding a character the two
    shells read differently is refused (:func:`refuse_shell_special`)
    rather than escaped for one of them and wrong in the other.
    """
    if hour is None:
        hour = start_hour()
    if not 0 <= hour <= 23:
        raise ValueError(f"hour must be 0-23, got {hour}")
    for field, value in (("working_dir", working_dir), ("python", python), ("settings", settings)):
        refuse_shell_special(field, value)

    command = (f"cd {quote_argument(working_dir)} && {quote_argument(python)} "
               f"{runner_arguments(settings, frozen=frozen)}")
    return {
        "name": task_name,
        "nodes": [
            {
                "parameters": {
                    "rule": {"interval": [{"field": "days", "triggerAtHour": hour}]}
                },
                "name": N8N_TRIGGER_NODE,
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.1,
                "position": [260, 300],
            },
            {
                "parameters": {"command": command},
                "name": N8N_RUN_NODE,
                "type": "n8n-nodes-base.executeCommand",
                "typeVersion": 1,
                "position": [500, 300],
            },
        ],
        "connections": {
            N8N_TRIGGER_NODE: {
                "main": [[{"node": N8N_RUN_NODE, "type": "main", "index": 0}]]
            }
        },
        "settings": {"executionOrder": "v1"},
    }


# ---------------------------------------------------------------- install ----


def install_task(xml_path: Path | str, task_name: str = TASK_NAME) -> list[str]:
    """Register the generated XML with Task Scheduler. Returns the command run.

    ``schtasks /create /xml <file> /tn <name> /f`` - the ``/f`` replaces an
    existing task of the same name, so re-running after changing the
    schedule is the whole upgrade path. Only meaningful on Windows; anywhere
    else the command is returned unrun so it can be shown.
    """
    command = ["schtasks", "/create", "/xml", str(xml_path), "/tn", task_name, "/f"]
    if not task_scheduler_here():
        return command
    completed = _schtasks(command)
    if completed.returncode != 0:
        raise RuntimeError(
            f"schtasks failed ({completed.returncode}): "
            f"{(completed.stderr or completed.stdout).strip()}"
        )
    return command


def _schtasks(command: list[str]) -> subprocess.CompletedProcess:
    """Run one ``schtasks`` command line and hand back what it said. The one
    place this module starts a process: the tests replace it, so no test
    ever reaches a real Task Scheduler."""
    return subprocess.run(command, capture_output=True, text=True)


def _working_dir(frozen: bool) -> Path:
    """The folder the job runs in: the packaged executable's own folder, or
    this checkout (the folder holding the package)."""
    return Path(sys.executable).resolve().parent if frozen else Path(__file__).resolve().parent.parent


def schedule_xml_path(settings_folder: str | Path) -> Path:
    """Where the generated job definition is written: beside the settings
    file in the app's settings folder."""
    return Path(settings_folder) / SCHEDULE_XML_FILENAME


def register_here(settings_folder: str | Path, *, start: str = DEFAULT_START,
                  every: int = DEFAULT_REPEAT_MINUTES) -> list[str]:
    """Write the job for this app's settings folder and register it with
    Task Scheduler; the command run (or, off Windows, the one that would
    be). **The one registration** (decision 209): the app's repair path
    and the after-install step both come here, so the job is spelled once.

    The job names the settings folder, never the root (decision 131). From
    a source checkout it is the Python this process runs under; in the
    packaged app it is this same executable in runner mode, which needs
    none of the environment the shell gives the API. A ``schtasks`` that
    refuses raises ``RuntimeError`` with what it said.
    """
    frozen = bool(getattr(sys, "frozen", False))
    xml_path = schedule_xml_path(settings_folder)
    write_text_atomically(
        xml_path,
        task_scheduler_xml(python=sys.executable, settings=settings_folder,
                           working_dir=_working_dir(frozen), start_time=start,
                           repeat_minutes=every, frozen=frozen),
        encoding=SCHEDULE_XML_ENCODING,
    )
    return install_task(xml_path)


def remove_task(task_name: str = TASK_NAME) -> bool:
    """Delete this computer's own task, if it has one; whether one was removed.

    ``schtasks /query`` first (exit 0 is "it exists"), then ``/delete /f``.
    Off Windows there is nothing to remove. A delete that fails raises
    ``RuntimeError``: a task left running on a computer that no longer runs
    the schedule is a second pass, and that is said, not swallowed.
    """
    if not task_scheduler_here():
        return False
    if _schtasks(["schtasks", "/query", "/tn", task_name]).returncode != 0:
        return False
    completed = _schtasks(["schtasks", "/delete", "/tn", task_name, "/f"])
    if completed.returncode != 0:
        raise RuntimeError(
            f"schtasks could not delete the task ({completed.returncode}): "
            f"{(completed.stderr or completed.stdout).strip()}"
        )
    return True


# ------------------------------------------- which computer runs it (209) ----

#: A computer's name as the designation file holds it: what
#: ``locking.this_host`` makes of the machine's own name, and nothing else.
HOST_NAME = re.compile(r"[a-z0-9._-]{1,63}")
#: More than this is not one line naming one computer, whatever it says.
MAX_DESIGNATION_BYTES = 256

#: The outcomes of :func:`schedule_decision`, by key.
NO_ROOT = "no_root"
NO_TASK_SCHEDULER = "no_task_scheduler"
CLAIMED = "claimed"
REGISTERED = "registered"
ELSEWHERE = "elsewhere"
UNREADABLE = "unreadable"
#: The outcomes that register a task on this computer.
REGISTERING = frozenset({CLAIMED, REGISTERED})

SCHEDULE_WAITS_FOR_ROOT = ("The schedule will be set up when the clients folder is chosen in the app, "
                           "on the computer that runs it.")
SCHEDULE_NOT_HERE = ("This computer has no Task Scheduler; the schedule runs on the office computer.")
SCHEDULE_CLAIMED = ("This computer ({host}) now runs the schedule for this clients folder: every day "
                    "from {start}, every {every} minutes.")
SCHEDULE_REGISTERED = ("The schedule is set: every day from {start}, every {every} minutes, with this "
                       "computer's copy of the app.")
SCHEDULE_ELSEWHERE = "{host} runs the schedule for this clients folder, so this computer registers none{removed}."
SCHEDULE_REMOVED = " and removed the one it had"
#: The file's path is named; its content never is (it is whatever was left there).
DESIGNATION_UNREADABLE = ("The file naming the computer that runs the schedule ({file}) is not one "
                          "computer's name; a person must fix or delete it. No schedule was changed.")
#: A claim that found another computer had claimed first.
CLAIM_TAKEN = ("{host} claimed the schedule for this clients folder first, so this computer registers "
               "none. No schedule was changed.")
#: What ``--move-schedule-here`` says before it registers.
MOVED_FROM = "The schedule for this clients folder moves from {host} to this computer ({here})."
MOVED_FROM_NOBODY = "No computer ran the schedule for this clients folder; this computer ({here}) now does."


class DesignationError(ValueError):
    """The designation file is not one computer's name, or a claim lost a race.
    The message is the whole sentence a person is shown."""


def checked_host(text: str) -> str:
    """``text`` as one computer's name - stripped and casefolded as
    ``locking.this_host`` makes one - or ``DesignationError``. A second
    non-blank line, more than :data:`MAX_DESIGNATION_BYTES` or a character
    outside ``[a-z0-9._-]`` is not a name."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(text.encode("utf-8", "surrogatepass")) > MAX_DESIGNATION_BYTES or len(lines) != 1:
        raise DesignationError("not one line")
    host = lines[0].casefold()
    if not HOST_NAME.fullmatch(host):
        raise DesignationError("not a computer's name")
    return host


def designated_machine(root: str | Path) -> str | None:
    """The computer the designation file under ``root`` names, or ``None``
    when there is no file. **The one reader** (decisions 209 and 210): pure
    apart from reading the file. A file that is there but is not one
    computer's name raises :class:`DesignationError` with
    :data:`DESIGNATION_UNREADABLE`, naming the path and never the content."""
    path = designation_file(root)
    unreadable = DesignationError(DESIGNATION_UNREADABLE.format(file=path))
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        raise unreadable from None
    if len(raw) > MAX_DESIGNATION_BYTES:
        raise unreadable
    try:
        return checked_host(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, DesignationError):
        raise unreadable from None


def _write_designation(root: str | Path, host: str) -> None:
    """Write ``host`` as the one line of the designation file, whole or not
    at all - checked as it is written, as it is when it is read. A root
    whose firm's tree is not made yet (no household so far) gets that one
    folder, as the first household would make it; never the root itself."""
    path = designation_file(root)
    path.parent.mkdir(exist_ok=True)
    write_text_atomically(path, checked_host(host) + "\n")


def claim(root: str | Path) -> None:
    """Name this computer as the one that runs the schedule, when no file
    names one: read, compare, write. A file that now names another computer
    is refused (:data:`CLAIM_TAKEN`) and left alone; one that already names
    this computer is left as it is."""
    named = designated_machine(root)
    if named is not None and named != this_host():
        raise DesignationError(CLAIM_TAKEN.format(host=named))
    if named is None:
        _write_designation(root, this_host())


def move_here(root: str | Path) -> str | None:
    """Name this computer as the one that runs the schedule, whatever the
    file said before; the computer it named, or ``None``. A deliberate act
    (runbook §6), never an after-install step. A file that is not one
    computer's name is replaced too - that is the repair it asks for."""
    try:
        before = designated_machine(root)
    except DesignationError:
        before = None
    _write_designation(root, this_host())
    return before


@dataclass(frozen=True, slots=True)
class ScheduleDecision:
    """What :func:`schedule_decision` found: the outcome's key, and the
    computer the designation names (this one for :data:`CLAIMED`), or ""."""

    outcome: str
    host: str = ""


def schedule_decision(root: str | Path | None) -> ScheduleDecision:
    """Whether this computer registers the schedule for ``root``, in order:
    no root (:data:`NO_ROOT`); no Task Scheduler (:data:`NO_TASK_SCHEDULER`);
    no designation, so this computer claims it (:data:`CLAIMED`); the file
    names this computer (:data:`REGISTERED`) or another (:data:`ELSEWHERE`);
    or the file is not one computer's name (:data:`UNREADABLE`). Decides
    only: claiming, registering and removing are the caller's."""
    if root is None:
        return ScheduleDecision(NO_ROOT)
    if not task_scheduler_here():
        return ScheduleDecision(NO_TASK_SCHEDULER)
    try:
        named = designated_machine(root)
    except DesignationError:
        return ScheduleDecision(UNREADABLE)
    here = this_host()
    if named is None:
        return ScheduleDecision(CLAIMED, here)
    return ScheduleDecision(REGISTERED if named == here else ELSEWHERE, named)


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate the scheduled job that runs the tracker unattended"
    )
    parser.add_argument(SETTINGS_FLAG, default="", metavar="FOLDER",
                        help=f"the app's settings folder, whose {SETTINGS_FILENAME} names the clients "
                             "root the job walks (default: this checkout's)")
    parser.add_argument("--python", default=sys.executable,
                        help="the Python to run it with (default: this one)")
    parser.add_argument("--working-dir", default=str(Path.cwd()),
                        help="the folder holding the tracker package")
    parser.add_argument(START_FLAG, default=DEFAULT_START,
                        help=f"daily start time, HH:MM (default: {DEFAULT_START})")
    parser.add_argument("--every", type=int, default=DEFAULT_REPEAT_MINUTES, metavar="MINUTES",
                        help=f"repeat filing and scanning through the day (default: "
                             f"{DEFAULT_REPEAT_MINUTES}; 0 = once a day)")
    parser.add_argument("--author", default="", help="task author, for the XML")
    parser.add_argument("--name", default=TASK_NAME, help="task name")
    parser.add_argument(FORMAT_FLAG, choices=FORMATS, default=FORMAT_XML,
                        help="Windows Task Scheduler XML (default) or an n8n workflow")
    parser.add_argument(OUT_FLAG, default="",
                        help="write to this file instead of standard output")
    parser.add_argument(INSTALL_FLAG, action="store_true",
                        help=f"also register the task with Task Scheduler (Windows; needs {OUT_FLAG})")
    ns = parser.parse_args()
    if ns.install and (ns.format != FORMAT_XML or not ns.out):
        parser.error(f"{INSTALL_FLAG} needs {FORMAT_FLAG} xml and {OUT_FLAG}")

    if not ns.settings:
        # None given: this checkout's own settings folder, which must already
        # name a clients root - a job pointed at a settings file with none
        # would fail every run.
        from tracker.settings import NO_ROOT_HINT, clients_root, settings_dir, settings_path

        if clients_root() is None:
            parser.error(f"no {SETTINGS_FLAG} given and no clients root in {settings_path()}; "
                         f"{NO_ROOT_HINT}")
        ns.settings = str(settings_dir())
    settings_arg = resolve_folder(ns.settings, ns.working_dir)

    try:
        if ns.format == FORMAT_XML:
            hhmm = ns.start.strip()
            if len(hhmm) != 5 or hhmm[2] != ":" or not hhmm.replace(":", "").isdigit():
                parser.error(f"{START_FLAG} must be HH:MM, got {ns.start!r}")
            payload = task_scheduler_xml(
                python=ns.python,
                settings=settings_arg,
                working_dir=ns.working_dir,
                start_time=hhmm,
                repeat_minutes=ns.every,
                author=ns.author,
                task_name=ns.name,
            )
            encoding = SCHEDULE_XML_ENCODING
        else:
            payload = json.dumps(
                n8n_workflow(
                    python=ns.python,
                    settings=settings_arg,
                    working_dir=ns.working_dir,
                    hour=start_hour(ns.start),
                    task_name=ns.name,
                ),
                indent=2,
            ) + "\n"
            encoding = "utf-8"
    except ValueError as exc:
        parser.error(str(exc))

    if ns.out:
        # Task Scheduler wants SCHEDULE_XML_ENCODING for an XML it will import.
        write_text_atomically(Path(ns.out), payload, encoding=encoding)
        print(f"Wrote {ns.out}")
        if ns.install:
            try:
                command = install_task(ns.out, ns.name)
            except RuntimeError as exc:
                raise SystemExit(f"Not installed: {exc}") from None
            if task_scheduler_here():
                print(f'Installed as "{ns.name}" - it runs daily from {ns.start}.')
            else:
                print("Not Windows; run this on the scheduling machine:  " + " ".join(command))
        elif ns.format == FORMAT_XML:
            print(f'Install it with:  {MODULE_INVOCATION} {SETTINGS_FLAG} "{ns.settings}" '
                  f'{OUT_FLAG} "{ns.out}" {INSTALL_FLAG}')
    else:
        print(payload, end="")
