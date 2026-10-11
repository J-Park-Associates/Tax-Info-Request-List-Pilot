"""Generate the scheduled job that runs the tracker unattended (component 10).

Emits a Windows Task Scheduler job definition for::

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
:func:`scheduler_here` (``task_scheduler_here`` until a Mac had a scheduler of
its own) so the name says only what it answers.

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

**On a Mac the job is a launchd agent** (SPEC-mac R23-R25, P238). The same
:func:`register_here`, :func:`task_query` and :func:`remove_task` do the same
three things through ``launchctl`` (:func:`_launchctl`, the second and last
seam, which the suite fakes as it fakes ``schtasks``): the plist is written
atomically to ``~/Library/LaunchAgents`` - the one place launchd reads it,
never the data home - then ``bootout``, ``bootstrap`` and ``enable``. It runs
the same times as the Windows task, round the clock from the start
(:func:`agent_times`). The designation is unchanged: the first Mac to
register claims the schedule, by ``locking.this_host``. launchd has no
execution time limit, which the lock's stale rule assumes; ``runner`` stops
its own scheduled pass off Windows (R26). A person can switch the agent off
under Login Items, and :func:`agent_switched_off` is how the launch door
knows to leave it so (R27). Which of the two schedulers a computer has is
asked through ``settings.host_system`` and nowhere else.

Importing this module loads no network library (decision 194):
``tests/test_layers.py::test_importing_the_api_loads_no_network_module``
holds it there.
"""

from __future__ import annotations

import datetime as dt
import html
import os
import plistlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from tracker import settings as settings_module
from tracker.fsio import full_sync, write_bytes_atomically, write_text_atomically
from tracker.layout import designation_file
from tracker.locking import RUN_TIME_LIMIT_SECONDS, is_this_host, this_host
from tracker.runner import DRAFT_DAY_NAME, LOG_FLAG, PRODUCT_FLAG, RUNNER_MODE_FLAG, SETTINGS_FLAG

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

#: The namespace of Task Scheduler's task XML.
TASK_XML_NAMESPACE = "http://schemas.microsoft.com/windows/2004/02/mit/task"
#: Task Scheduler imports XML in this encoding; the declaration and both
#: writers (CLI and app) say so from here.
SCHEDULE_XML_ENCODING = "utf-16"
#: How a person is told to install the schedule, wherever they are told:
#: how the scheduler module is invoked, for every hint that says so.
MODULE_INVOCATION = "python -m tracker.scheduling"
INSTALL_FLAG = "--install"
OUT_FLAG = "--out"
START_FLAG = "--start"


def scheduler_here() -> bool:
    """Whether this computer has a scheduler at all: Task Scheduler on
    Windows, launchd on a Mac (SPEC-mac R24). Nothing more: whether this is
    the computer that *runs* the schedule is :func:`schedule_decision`'s
    question (decision 209). Asked through ``settings.host_system``, the one
    seam every platform branch goes through, so a test stands in for either
    machine by patching that and never the platform."""
    return settings_module.host_system() in ("nt", "darwin")


def _launchd_here() -> bool:
    """Whether this computer's scheduler is launchd: it is a Mac."""
    return settings_module.host_system() == "darwin"


def _task_scheduler_here() -> bool:
    """Whether this computer's scheduler is Windows' Task Scheduler: it has
    one that is not launchd. (A test that fakes the first answer and leaves
    the machine a Linux one stands in for Windows, as it always has.)"""
    return scheduler_here() and not _launchd_here()


def _runner_parts(settings_dir: str | Path, *, frozen: bool) -> list[tuple[str, bool]]:
    """The scheduled job's command line after the program, token by token,
    each with whether it is a value (quoted for Windows) or a flag. The one
    spelling behind both :func:`runner_argv` and :func:`runner_arguments`."""
    program = ([(RUNNER_MODE_FLAG, False), (PRODUCT_FLAG, False), (product_name(), True)] if frozen
               else [("-m", False), ("tracker.runner", False)])
    return [*program, (SETTINGS_FLAG, False), (str(settings_dir), True), (LOG_FLAG, False)]


def runner_argv(settings_dir: str | Path, *, frozen: bool = False) -> list[str]:
    """The one command line the scheduled job runs, whoever schedules it, as
    the argument list launchd wants (SPEC-mac R23): everything after the
    program. :func:`runner_arguments` is the same tokens as Windows' one
    quoted string.

    After the program that runs it: ``-m tracker.runner`` for a Python
    checkout, ``RUNNER_MODE_FLAG`` for the packaged app's own executable
    (``api_entry.py`` in runner mode; on a Mac that is the API in
    ``Contents/Resources/tracker-api/``). The runner's arguments are the same
    either way; only the way in differs.

    It names the app's settings folder and **no clients root** (decision
    131): the runner reads the root from the settings file there at every
    run, so the root has one home.

    The packaged line also names the product (P201,
    ``pilot/SPEC-firm-cache-fill.md`` R6), before the settings folder so
    the line still ends as above: the pass asks the firm summary at its end
    in a child that imports the API, which reads the product's name at
    import, and the scheduler gives the job none of the shell's
    environment. A checkout reads it from ``app/package.json``, so the
    source line is unchanged.
    """
    return [text for text, _ in _runner_parts(settings_dir, frozen=frozen)]


def runner_arguments(settings_dir: str | Path, *, frozen: bool = False) -> str:
    """:func:`runner_argv` as the one string Task Scheduler's ``<Arguments>``
    holds: the flags bare and each value quoted for the Windows argument
    parser (:func:`quote_argument`)."""
    return " ".join(quote_argument(text) if value else text
                    for text, value in _runner_parts(settings_dir, frozen=frozen))


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


# ---------------------------------------------------------------- install ----


def install_task(xml_path: Path | str, task_name: str = TASK_NAME) -> list[str]:
    """Register the generated XML with Task Scheduler. Returns the command run.

    ``schtasks /create /xml <file> /tn <name> /f`` - the ``/f`` replaces an
    existing task of the same name, so re-running after changing the
    schedule is the whole upgrade path. Only meaningful on Windows; anywhere
    else the command is returned unrun so it can be shown.
    """
    command = ["schtasks", "/create", "/xml", str(xml_path), "/tn", task_name, "/f"]
    if not _task_scheduler_here():
        return command
    _schtasks_or_raise(command, "schtasks failed")
    return command


#: How long one ``schtasks`` command may take before it is stopped (the
#: engine review's SHOULD-2): the launch asks it at every start, inside the
#: after-install step's lock, so a Task Scheduler service that hangs must
#: not hold that lock - and a later Repair or root save - for ever. A
#: healthy ``schtasks`` answers in well under a second.
SCHTASKS_TIME_LIMIT_SECONDS = 60
#: What a ``schtasks`` that ran past the limit raises, by its class only
#: (``TimeoutError``, an ``OSError``), so every caller's ``OSError`` path
#: says it as Task Scheduler that cannot be reached - never "it exists".
SCHTASKS_TOO_LONG = "schtasks did not answer within {seconds} seconds"


def _run_within_the_limit(command: list[str], too_long: str) -> subprocess.CompletedProcess:
    """One scheduler command, with :data:`SCHTASKS_TIME_LIMIT_SECONDS` to
    answer; ``TimeoutError`` (an ``OSError``) saying ``too_long`` past it. The
    one place this module starts a process, for Task Scheduler and launchd
    alike."""
    try:
        return subprocess.run(command, capture_output=True, text=True,
                              timeout=SCHTASKS_TIME_LIMIT_SECONDS)
    except subprocess.TimeoutExpired:
        raise TimeoutError(too_long.format(seconds=SCHTASKS_TIME_LIMIT_SECONDS)) from None


def _schtasks(command: list[str]) -> subprocess.CompletedProcess:
    """Run one ``schtasks`` command line and hand back what it said. The seam
    for Task Scheduler: the tests replace it, so no test ever reaches a real
    one. One that does not answer within :data:`SCHTASKS_TIME_LIMIT_SECONDS`
    is stopped and raises ``TimeoutError``."""
    return _run_within_the_limit(command, SCHTASKS_TOO_LONG)


def register_here(settings_folder: str | Path, *, start: str = DEFAULT_START,
                  every: int = DEFAULT_REPEAT_MINUTES) -> list[str]:
    """Write the job for this app's settings folder and register it with
    this computer's scheduler; the command run (or, off Windows and Mac,
    the one that would be). **The one registration** (decision 209): the
    app's repair path and the after-install step both come here, so the job
    is spelled once.

    The job names the settings folder, never the root (decision 131). From
    a source checkout it is the Python this process runs under; in the
    packaged app it is this same executable in runner mode, which needs
    none of the environment the shell gives the API. A ``schtasks`` that
    refuses raises ``RuntimeError`` with what it said. On a Mac the job is a
    launchd agent (:func:`_register_agent`, SPEC-mac R24).
    """
    start = check_start(start)
    every = check_every(every)
    frozen = bool(getattr(sys, "frozen", False))
    if _launchd_here():
        return _register_agent(settings_folder, start=start, every=every, frozen=frozen)
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


def _raise_unless_done(completed: subprocess.CompletedProcess, failure: str) -> None:
    """A non-zero exit raises ``RuntimeError`` naming ``failure``, the code,
    and what the command said (its stderr, else its stdout)."""
    if completed.returncode != 0:
        raise RuntimeError(
            f"{failure} ({completed.returncode}): {(completed.stderr or completed.stdout).strip()}"
        )


def _schtasks_or_raise(command: list[str], failure: str) -> None:
    """Run one ``schtasks`` command that must succeed, as :func:`_raise_unless_done`."""
    _raise_unless_done(_schtasks(command), failure)


def task_exists(task_name: str = TASK_NAME) -> bool:
    """Whether the scheduler holds a task of this name: ``schtasks /query
    /tn`` exits 0 for one that exists (on a Mac, ``launchctl print`` of the
    agent). Where there is no scheduler there is none.

    Any other answer - not found, access denied, Task Scheduler stopped - is
    ``False``, "not confirmed", never "it is there" (P198, F6): the callers
    act on it by registering again (``/create /f``, which says in its own
    words why it cannot) or by having nothing to remove. A ``schtasks`` that
    cannot be started at all, or does not answer in time, raises ``OSError``
    for the caller to say.
    """
    return task_query(task_name) == 0


def task_query(task_name: str = TASK_NAME) -> int | None:
    """The scheduler's exit code for this computer's task - 0 when it exists,
    any other a refusal (not found, access denied, scheduler stopped) - or
    ``None`` where there is no scheduler, where nothing is asked. On Windows
    that is ``schtasks /query /tn``'s; on a Mac, ``launchctl print`` of the
    agent's service (``task_name`` is Windows' name; a Mac has the one
    :data:`LAUNCH_AGENT_LABEL`). The launch keeps a refusal's code on the
    error log (the engine review's NIT-2); its words are not kept. Raises
    ``OSError`` as :func:`task_exists` does."""
    if not scheduler_here():
        return None
    if _launchd_here():
        return _launchctl(["launchctl", "print", _service()]).returncode
    return _schtasks(["schtasks", "/query", "/tn", task_name]).returncode


def remove_task(task_name: str = TASK_NAME) -> bool:
    """Delete this computer's own task, if it has one; whether one was removed.

    :func:`task_exists` first, then ``/delete /f``. Off Windows and Mac there
    is nothing to remove. A delete that fails raises ``RuntimeError``: a task
    left running on a computer that no longer runs the schedule is a second
    pass, and that is said, not swallowed. On a Mac it is the agent's
    ``bootout`` (when it is loaded) and its file (SPEC-mac R24)."""
    if _launchd_here():
        return _remove_agent()
    if not task_exists(task_name):
        return False
    _schtasks_or_raise(["schtasks", "/delete", "/tn", task_name, "/f"],
                       "schtasks could not delete the task")
    return True


# ------------------------------------------------------ the Mac: launchd ----

#: The app's bundle identifier, the one the shell sets as the Windows
#: taskbar id and ``build-mac.sh`` gives the bundle (a test holds the three
#: equal). The agent names it so that System Settings > General > Login
#: Items > Allow in the Background lists the schedule under the app.
APP_BUNDLE_ID = "com.jparkassociates.taxdocumentconsole"
#: The agent's label, a constant (SPEC-mac R23): the name of its plist, of
#: its launchd service and of the one thing a person can switch off.
LAUNCH_AGENT_LABEL = f"{APP_BUNDLE_ID}.schedule"
#: What a ``launchctl`` that ran past the limit raises, by its class only
#: (``TimeoutError``, an ``OSError``), as :data:`SCHTASKS_TOO_LONG` does.
LAUNCHCTL_TOO_LONG = "launchctl did not answer within {seconds} seconds"
_MINUTES_A_DAY = 24 * 60
#: ``launchctl print-disabled`` lists a service the person switched off as
#: ``"label" => disabled`` (macOS 13 on), or ``=> true`` in its older words.
_DISABLED_LINE = re.compile(rf'"{re.escape(LAUNCH_AGENT_LABEL)}"\s*=>\s*(?:disabled|true)\b')


def _launchctl(command: list[str]) -> subprocess.CompletedProcess:
    """Run one ``launchctl`` command line and hand back what it said. **The
    one seam for launchd** (SPEC-mac R24), as :func:`_schtasks` is for Task
    Scheduler: the suite's autouse guard (``tests/conftest.py``) fails a test
    that reaches the real one. One that does not answer within the same
    limit is stopped and raises ``TimeoutError``."""
    return _run_within_the_limit(command, LAUNCHCTL_TOO_LONG)


def _launchctl_or_raise(command: list[str], failure: str) -> None:
    """Run one ``launchctl`` command that must succeed, as :func:`_raise_unless_done`."""
    _raise_unless_done(_launchctl(command), failure)


def _uid() -> int:
    """The signed-in person's user id (``os.getuid``), which only a Mac has to
    answer. A seam, so the suite stands in for a Mac on a Windows runner, which
    has no ``os.getuid``."""
    return os.getuid()


def _domain() -> str:
    """The launchd domain of the signed-in person: ``gui/<uid>``. The agent
    lives in it, so it runs only while that person is signed in - what Task
    Scheduler's ``InteractiveToken`` said."""
    return f"gui/{_uid()}"


def _service() -> str:
    """The agent's service target, ``gui/<uid>/<label>``."""
    return f"{_domain()}/{LAUNCH_AGENT_LABEL}"


def launch_agent_path() -> Path:
    """Where the agent's plist lives: ``~/Library/LaunchAgents/<label>.plist``,
    the one place launchd reads it from - never the data home (SPEC-mac R23).
    Only a path."""
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def schedule_file() -> Path:
    """The file the registered schedule is, on this computer: the agent's
    plist on a Mac, else the task's XML in the data home."""
    return launch_agent_path() if _launchd_here() else schedule_xml_path()


def agent_times(start: str, every: int) -> list[tuple[int, int]]:
    """Every time of day the agent runs, as ``(hour, minute)``, soonest first:
    the start plus a whole number of intervals, round the clock.

    Task Scheduler's ``Repetition`` with ``Duration P1D`` repeats around the
    clock from the start, not until midnight, so launchd, which has only
    calendar entries, is given the same set: 1440 / ``every`` of them, and
    one when it runs once a day (``every`` 0)."""
    hour, minute = (int(part) for part in check_start(start).split(":"))
    begin = hour * 60 + minute
    step = check_every(every)
    minutes = {begin} if not step else {(begin + k * step) % _MINUTES_A_DAY
                                         for k in range(-(-_MINUTES_A_DAY // step))}
    return [divmod(at, 60) for at in sorted(minutes)]


def launch_agent_plist(*, program: str | Path, settings: str | Path, working_dir: str | Path,
                       start: str = DEFAULT_START, every: int = DEFAULT_REPEAT_MINUTES,
                       frozen: bool = False) -> bytes:
    """The agent's property list, rendered with ``plistlib`` (SPEC-mac R23).

    It runs ``program`` with :func:`runner_argv` and names the app's settings
    folder and **no clients root** (decision 131). ``StartCalendarInterval``
    is :func:`agent_times`. ``ProcessType`` is ``Standard`` and there is no
    ``RunAtLoad``: the first pass is the after-install step's own
    ``kickstart``, once, never a pass every time the agent loads.
    ``AssociatedBundleIdentifiers`` is the app's id, so Allow in the
    Background names the app.

    Three of Task Scheduler's settings need no entry, because launchd does
    them itself: ``IgnoreNew`` (one label is one process at a time),
    ``InteractiveToken`` (the ``gui/<uid>`` domain runs only while the person
    is signed in) and ``StartWhenAvailable`` (a time missed while asleep runs
    on wake; one missed while the Mac was off is not made up, and the
    draft-day logic already covers that). launchd has **no execution time
    limit**: the runner enforces the lock's own (``runner``, SPEC-mac R26)."""
    return plistlib.dumps({
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": [str(program), *runner_argv(settings, frozen=frozen)],
        "WorkingDirectory": str(working_dir),
        "StartCalendarInterval": [{"Hour": hour, "Minute": minute}
                                  for hour, minute in agent_times(start, every)],
        "ProcessType": "Standard",
        "AssociatedBundleIdentifiers": [APP_BUNDLE_ID],
    }, fmt=plistlib.FMT_XML, sort_keys=False)


def _register_agent(settings_folder: str | Path, *, start: str, every: int, frozen: bool) -> list[str]:
    """Write the agent's file and load it (SPEC-mac R24): the plist, atomically,
    into ``~/Library/LaunchAgents``; ``bootout`` of the service (where none is
    loaded launchctl says so, and that answer is ignored); then ``bootstrap``
    and ``enable``, each of which must succeed. Returns the ``bootstrap``
    command. A ``launchctl`` that cannot be started raises ``OSError`` for the
    caller to say; one that refuses raises ``RuntimeError`` with what it said."""
    path = launch_agent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_bytes_atomically(path, launch_agent_plist(
        program=sys.executable, settings=settings_folder, working_dir=app_dir(),
        start=start, every=every, frozen=frozen))
    _launchctl(["launchctl", "bootout", _service()])
    bootstrap = ["launchctl", "bootstrap", _domain(), str(path)]
    _launchctl_or_raise(bootstrap, "launchctl could not load the agent")
    _launchctl_or_raise(["launchctl", "enable", _service()], "launchctl could not enable the agent")
    return bootstrap


def _remove_agent() -> bool:
    """Unload the agent if it is loaded and delete its file; whether either
    was there. A ``bootout`` that fails raises ``RuntimeError``, as a failed
    ``/delete`` does."""
    loaded = task_exists()
    if loaded:
        _launchctl_or_raise(["launchctl", "bootout", _service()], "launchctl could not unload the agent")
    path = launch_agent_path()
    there = path.exists()
    path.unlink(missing_ok=True)
    return loaded or there


def agent_switched_off(unloaded: bool | None = None) -> bool:
    """Whether the person switched the agent off in System Settings > General >
    Login Items > Allow in the Background (SPEC-mac R27). A switch is theirs:
    the after-install step does not load the agent again over it.

    Two signals, either of which is the switch. ``launchctl print-disabled``
    lists the label as disabled: the rule R27 first asked, kept for a macOS
    that says so. Or launchd no longer has the agent while its plist is still
    where :func:`register_here` put it: on macOS 26 the switch unloads the
    agent and leaves the file, while ``print-disabled`` keeps answering
    ``enabled`` (re-run 1, kit step H5), so the first signal alone read the
    switch as a missing agent and registered over it. An agent whose file is
    gone is missing, not switched off - :func:`remove_task` unlinks the file,
    so a schedule removed in the app is never read as the switch.

    ``unloaded`` is what the caller already knows from :func:`task_query`
    (its exit code was not 0); ``None`` asks ``task_query`` here, only when
    ``print-disabled`` did not already answer. ``launchctl`` refusing a
    question raises ``RuntimeError``; one that cannot be started, ``OSError``."""
    completed = _launchctl(["launchctl", "print-disabled", _domain()])
    _raise_unless_done(completed, "launchctl could not list the switched-off items")
    if _DISABLED_LINE.search(completed.stdout or ""):
        return True
    if unloaded is None:
        unloaded = task_query() != 0
    return unloaded and launch_agent_path().exists()


def start_agent_now() -> list[str]:
    """Run the agent's job once, now (``launchctl kickstart``), and return the
    command: the first pass of a program it has not run before, while a person
    is at the Mac, so any permission macOS asks of the schedule's own program
    is asked then (SPEC-mac R27, R30). Refused: ``RuntimeError``."""
    command = ["launchctl", "kickstart", _service()]
    _launchctl_or_raise(command, "launchctl could not start the first pass")
    return command


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
                full_sync(written.fileno())
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
    if not scheduler_here():
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
    parser.add_argument(OUT_FLAG, default="",
                        help="write to this file instead of standard output")
    parser.add_argument(INSTALL_FLAG, action="store_true",
                        help="also register the task with Task Scheduler (Windows); the task's file "
                             f"goes into the app's data folder unless {OUT_FLAG} names another")
    ns = parser.parse_args()
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
        payload = task_scheduler_xml(
            python=ns.python,
            settings=settings_arg,
            working_dir=ns.working_dir,
            start_time=check_start(ns.start),
            repeat_minutes=check_every(ns.every),
            author=ns.author,
            task_name=ns.name,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if ns.out:
        # Task Scheduler wants SCHEDULE_XML_ENCODING for an XML it will import.
        Path(ns.out).parent.mkdir(parents=True, exist_ok=True)
        write_text_atomically(Path(ns.out), payload, encoding=SCHEDULE_XML_ENCODING)
        print(f"Wrote {ns.out}")
        if ns.install:
            try:
                command = install_task(ns.out, ns.name)
            except RuntimeError as exc:
                raise SystemExit(f"Not installed: {exc}") from None
            if _task_scheduler_here():
                print(f'Installed as "{ns.name}" - it runs daily from {ns.start}.')
            else:
                print("Not Windows; run this on the scheduling machine:  " + " ".join(command))
        else:
            print(f'Install it with:  {MODULE_INVOCATION} {SETTINGS_FLAG} "{ns.settings}" '
                  f'{OUT_FLAG} "{ns.out}" {INSTALL_FLAG}')
    else:
        print(payload, end="")
