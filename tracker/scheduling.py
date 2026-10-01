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

Importing this module loads no network library (decision 194):
``tests/test_layers.py::test_importing_the_api_loads_no_network_module``
holds it there.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from tracker.fsio import write_text_atomically
from tracker.layout import designation_file
from tracker.locking import RUN_TIME_LIMIT_SECONDS, is_this_host, this_host
from tracker.runner import DRAFT_DAY_NAME, LOG_FLAG, RUNNER_MODE_FLAG, SETTINGS_FLAG

# The schedule choice and its checks live in ``settings`` - the runner reads
# the saved choice too, and the runner may not import this module - and are
# named here as well (``as`` marks the re-export), because this is where the
# schedule is spelled.
from tracker.settings import (
    DEFAULT_SCHEDULE_EVERY,
    DEFAULT_SCHEDULE_START,
    SETTINGS_FILENAME,
    app_dir,
    data_home,
    product_name,
    program_drive_refusal,
)
from tracker.settings import EVERY_CHOICES as EVERY_CHOICES
from tracker.settings import ScheduleChoiceError as ScheduleChoiceError
from tracker.settings import SchedulePreference as SchedulePreference
from tracker.settings import check_every as check_every
from tracker.settings import check_start as check_start

#: The scheduled task is named after the product, wherever that is set.
TASK_NAME = product_name()
DEFAULT_START = DEFAULT_SCHEDULE_START
#: Filing and scanning repeat through the day this often (minutes); the
#: reminder still drafts only on the drafting day. 0 = once a day.
DEFAULT_REPEAT_MINUTES = DEFAULT_SCHEDULE_EVERY
#: The generated Task Scheduler definition, in the tracker's data home (decision 186).
SCHEDULE_XML_FILENAME = "tax-tracker.xml"
#: Any date in the past will do for a daily trigger; it is when the series began.
_START_BOUNDARY_DATE = "2026-01-01"


def schedule_xml_path() -> Path:
    """Where Install Schedule writes the task's file: the data home (decision
    186), never beside the program. Only a path; the installer makes the folder."""
    return data_home() / SCHEDULE_XML_FILENAME


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
    """``&``, ``<`` and ``>`` escaped, and nothing else - byte for byte what
    ``xml.sax.saxutils.escape`` gave (decision 194, D8).

    Not saxutils: it imports ``urllib.request``, which loads ``http.client``
    and ``ssl``, and even at call time (decision 193's review, S2) that is a
    network library in the process for one escape. ``quote=False``, because
    ``quote=True`` would turn a ``"`` inside ``<Arguments>`` into ``&quot;``:
    valid XML, but a changed task file for no reason."""
    return html.escape(str(value), quote=False)


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
    start = check_start(start)
    every = check_every(every)
    frozen = bool(getattr(sys, "frozen", False))
    # The task's file goes into the data home (decision 186), never beside
    # the program; its folder is made as the installer makes it.
    xml_path = schedule_xml_path()
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomically(
        xml_path,
        task_scheduler_xml(python=sys.executable, settings=settings_folder,
                           working_dir=app_dir(), start_time=start,
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


NEXT_RUN_TODAY = "Next run: today at {time}"
NEXT_RUN_TOMORROW = "Next run: tomorrow at {time}"


def next_run(preference: SchedulePreference, now: dt.datetime | None = None) -> str:
    """When the setting next runs, in a sentence, from the start, the
    interval and the local time: "Next run: today at 13:00" or "tomorrow at
    07:00", and "" when the schedule is off.

    The task starts a series at the start time every day and repeats it for
    a day (:func:`task_scheduler_xml`), so the runs are the start plus whole
    intervals, each day's series ending where the next begins. The series
    that began yesterday still counts before today's start."""
    if not preference.enabled:
        return ""
    now = now or dt.datetime.now()
    hour, minute = (int(part) for part in check_start(preference.start).split(":"))
    step = dt.timedelta(minutes=preference.every) if preference.every else dt.timedelta(days=1)
    coming = []
    for days in (-1, 0, 1):
        day = now.date() + dt.timedelta(days=days)
        begin = dt.datetime.combine(day, dt.time(hour, minute))
        at = begin
        while at < begin + dt.timedelta(days=1):
            if at > now:
                coming.append(at)
            at += step
    soonest = min(coming)
    template = NEXT_RUN_TODAY if soonest.date() == now.date() else NEXT_RUN_TOMORROW
    return template.format(time=soonest.strftime("%H:%M"))


# ------------------------------------------- which computer runs it (209) ----

#: A computer's name as the designation file holds it: what
#: ``locking.this_host`` makes of the machine's own name, and nothing else.
HOST_NAME = re.compile(r"[a-z0-9._-]{1,63}")
#: More than this is not one line naming one computer, whatever it says.
MAX_DESIGNATION_BYTES = 256

#: The outcomes of :func:`schedule_decision`, by key.
#: The program is on a drive the schedule may not run it from (decision
#: 186's ``settings.program_drive_refusal``, its sentence): a failure.
REFUSED_DRIVE = "refused_drive"
NO_ROOT = "no_root"
NO_TASK_SCHEDULER = "no_task_scheduler"
CLAIMED = "claimed"
REGISTERED = "registered"
ELSEWHERE = "elsewhere"
UNREADABLE = "unreadable"
UNNAMED_HOST = "unnamed_host"
#: The outcomes that register a task on this computer.
REGISTERING = frozenset({CLAIMED, REGISTERED})
#: The schedule is switched off in the setting (pilot P21): this computer's
#: task is removed and nothing is registered, whichever computer is named.
OFF = "off"

SCHEDULE_WAITS_FOR_ROOT = ("The schedule will be set up when the clients folder is chosen in the app, "
                           "on the computer that runs it.")
SCHEDULE_NOT_HERE = ("This computer has no Task Scheduler; the schedule runs on the office computer.")
SCHEDULE_CLAIMED = ("This computer ({host}) now runs the schedule for this clients folder: every day "
                    "from {start}, every {every} minutes.")
SCHEDULE_REGISTERED = ("The schedule is set: every day from {start}, every {every} minutes, with this "
                       "computer's copy of the app.")
#: The same two for a schedule that runs once a day (``every`` 0): no
#: repeat to state, so "every day at {start}".
SCHEDULE_CLAIMED_DAILY = ("This computer ({host}) now runs the schedule for this clients folder: every day "
                          "at {start}.")
SCHEDULE_REGISTERED_DAILY = ("The schedule is set: every day at {start}, with this computer's copy of "
                             "the app.")
#: The app's words since the shell (P133): the pass is Sort, and Schedule is
#: a Tools menu item, not a button.
SCHEDULE_OFF = "The schedule is off on this computer. Sort still works. Turn it on in Tools > Schedule."
SCHEDULE_ELSEWHERE = "{host} runs the schedule for this clients folder, so this computer registers none{removed}."
SCHEDULE_REMOVED = " and removed the one it had"
#: The file's path is named; its content never is (it is whatever was left there).
DESIGNATION_UNREADABLE = ("The file naming the computer that runs the schedule ({file}) is not one "
                          "computer's name; a person must fix or delete it. No schedule was changed.")
#: This computer's own name is not one the file can hold (a Windows name
#: with a space or an accent, or none at all): asked before the file is
#: read, so the file is never written with a name it would then refuse.
HOST_UNNAMED = ("This computer's name cannot be written as one computer's name in {file}; the "
                "schedule was not changed. Rename the computer, or run the schedule on the office "
                "computer.")
#: A claim that found another computer had claimed first.
CLAIM_TAKEN = ("{host} claimed the schedule for this clients folder first, so this computer registers "
               "none. No schedule was changed.")
#: What ``--move-schedule-here`` says before it registers.
MOVED_FROM = "The schedule for this clients folder moves from {host} to this computer ({here})."
MOVED_FROM_NOBODY = "No computer ran the schedule for this clients folder; this computer ({here}) now does."
#: A move over a file that named no computer it could read: said as that,
#: not as "no computer ran it" (the file was there, and was not a name).
MOVED_FROM_UNREADABLE = ("The file naming the computer that ran the schedule for this clients folder "
                         "was not one computer's name; this computer ({here}) now runs it.")


class DesignationError(ValueError):
    """The designation file is not one computer's name, this computer's name
    cannot be written in it, or a claim lost a race. The message is always
    the whole sentence a person is shown - one of this module's constants."""


def _host_name(text: str) -> str | None:
    """``text`` as one computer's name - stripped and casefolded as
    ``locking.this_host`` makes one - or ``None``. A second non-blank line,
    more than :data:`MAX_DESIGNATION_BYTES` or a character outside
    ``[a-z0-9._-]`` is not a name. Private: each caller says its own whole
    sentence (the file is unreadable, or this computer is unnamed)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(text.encode("utf-8", "surrogatepass")) > MAX_DESIGNATION_BYTES or len(lines) != 1:
        return None
    host = lines[0].casefold()
    return host if HOST_NAME.fullmatch(host) else None


def host_is_nameable() -> bool:
    """Whether this computer's own name is one the designation file can
    hold (:data:`HOST_NAME`)."""
    return _host_name(this_host()) is not None


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
        host = _host_name(raw.decode("utf-8-sig"))
    except UnicodeDecodeError:
        raise unreadable from None
    if host is None:
        raise unreadable
    return host


def _this_line(root: str | Path) -> str:
    """This computer's name as the designation file's one line - checked as
    it is written, as it is when it is read - or :data:`HOST_UNNAMED`. It
    is the one place this computer's name is *written*; every comparison
    of a name with this computer is ``locking.is_this_host``."""
    host = _host_name(this_host())
    if host is None:
        raise DesignationError(HOST_UNNAMED.format(file=designation_file(root)))
    return host + "\n"


def claim(root: str | Path) -> None:
    """Name this computer as the one that runs the schedule, when no file
    names one. The file is **created exclusively** (``O_EXCL``, the review's
    N3): of two claims on one computer's disk at once, the second finds the
    file there and is answered by what it says - this computer, left as it
    is, or another, refused (:data:`CLAIM_TAKEN`) and left alone. A root
    whose firm's tree is not made yet (no household so far) gets that one
    folder, as the first household would make it; never the root itself.
    Two computers claiming through a sync client at once is the residual
    race the runbook states; this closes the local half."""
    line = _this_line(root)
    named = designated_machine(root)
    if named is None:
        path = designation_file(root)
        path.parent.mkdir(exist_ok=True)
        try:
            handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))
        except FileExistsError:
            named = designated_machine(root)
        else:
            with os.fdopen(handle, "wb") as written:
                written.write(line.encode("utf-8"))
                written.flush()
                os.fsync(written.fileno())
            return
    if named is not None and not is_this_host(named):
        raise DesignationError(CLAIM_TAKEN.format(host=named))


@dataclass(frozen=True, slots=True)
class Moved:
    """What :func:`move_here` replaced: the computer the file named, or
    ``None``; and whether the file was there but named no computer."""

    before: str | None
    unreadable: bool = False


def move_here(root: str | Path) -> Moved:
    """Name this computer as the one that runs the schedule, whatever the
    file said before, whole or not at all. A deliberate act (runbook §6),
    never an after-install step. A file that is not one computer's name is
    replaced too - that is the repair it asks for - and said as that."""
    line = _this_line(root)
    try:
        moved = Moved(designated_machine(root))
    except DesignationError:
        moved = Moved(None, unreadable=True)
    path = designation_file(root)
    path.parent.mkdir(exist_ok=True)
    write_text_atomically(path, line)
    return moved


@dataclass(frozen=True, slots=True)
class ScheduleDecision:
    """What :func:`schedule_decision` found: the outcome's key, and the
    computer the designation names (this one for :data:`CLAIMED`), or "";
    for :data:`REFUSED_DRIVE`, decision 186's sentence saying why."""

    outcome: str
    host: str = ""
    sentence: str = ""


def schedule_decision(root: str | Path | None) -> ScheduleDecision:
    """Whether this computer registers the schedule for ``root``, in order:
    the program on a removable, network or unnamed drive
    (:data:`REFUSED_DRIVE`, decision 186's ``program_drive_refusal`` - the
    one authority, asked here once for every door of the after-install
    step); no root (:data:`NO_ROOT`); no Task Scheduler (:data:`NO_TASK_SCHEDULER`);
    this computer's own name is not one the file can hold
    (:data:`UNNAMED_HOST`), asked before the file is read; no designation,
    so this computer claims it (:data:`CLAIMED`); the file names this
    computer (:data:`REGISTERED`, by ``locking.is_this_host``) or another
    (:data:`ELSEWHERE`); or the file is not one computer's name
    (:data:`UNREADABLE`). Decides only: claiming, registering and removing
    are the caller's."""
    if refusal := program_drive_refusal():
        return ScheduleDecision(REFUSED_DRIVE, sentence=refusal)
    if root is None:
        return ScheduleDecision(NO_ROOT)
    if not task_scheduler_here():
        return ScheduleDecision(NO_TASK_SCHEDULER)
    if not host_is_nameable():
        return ScheduleDecision(UNNAMED_HOST)
    try:
        named = designated_machine(root)
    except DesignationError:
        return ScheduleDecision(UNREADABLE)
    if named is None:
        return ScheduleDecision(CLAIMED, this_host())
    return ScheduleDecision(REGISTERED if is_this_host(named) else ELSEWHERE, named)


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate the scheduled job that runs the app unattended"
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
    parser.add_argument("--every", default=DEFAULT_REPEAT_MINUTES, metavar="MINUTES",
                        help=f"repeat filing and scanning through the day (default: "
                             f"{DEFAULT_REPEAT_MINUTES}; 0 = once a day)")
    parser.add_argument("--author", default="", help="task author, for the XML")
    parser.add_argument("--name", default=TASK_NAME, help="task name")
    parser.add_argument(FORMAT_FLAG, choices=FORMATS, default=FORMAT_XML,
                        help="Windows Task Scheduler XML (default) or an n8n workflow")
    parser.add_argument(OUT_FLAG, default="",
                        help="write to this file instead of standard output")
    parser.add_argument(INSTALL_FLAG, action="store_true",
                        help="also register the task with Task Scheduler (Windows); the task's file "
                             f"goes into the app's data folder unless {OUT_FLAG} names another")
    ns = parser.parse_args()
    if ns.install and ns.format != FORMAT_XML:
        parser.error(f"{INSTALL_FLAG} needs {FORMAT_FLAG} xml")
    if ns.install and not ns.out:
        from tracker.settings import SettingsError

        try:
            ns.out = str(schedule_xml_path())
        except SettingsError as exc:
            parser.error(str(exc))

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
    if ns.install:
        # The task runs whatever program sits there, every pass: never one on
        # a removable or network drive (decision 186). Refused before writing.
        if refusal := program_drive_refusal(settings=Path(settings_arg)):
            parser.error(refusal)

    try:
        if ns.format == FORMAT_XML:
            hhmm = check_start(ns.start)
            payload = task_scheduler_xml(
                python=ns.python,
                settings=settings_arg,
                working_dir=ns.working_dir,
                start_time=hhmm,
                repeat_minutes=check_every(ns.every),
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
                    hour=start_hour(check_start(ns.start)),
                    task_name=ns.name,
                ),
                indent=2,
            ) + "\n"
            encoding = "utf-8"
    except ValueError as exc:
        parser.error(str(exc))

    if ns.out:
        # Task Scheduler wants SCHEDULE_XML_ENCODING for an XML it will import.
        Path(ns.out).parent.mkdir(parents=True, exist_ok=True)
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
