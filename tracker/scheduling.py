"""Generate the scheduled job that runs the tracker unattended (component 10).

Emits a Windows Task Scheduler job definition, or the n8n equivalent, for::

    python -m tracker.runner <clients root>

**One task, not two.** The runner decides for itself whether today is the day
to draft reminders (``tracker.runner.DRAFT_WEEKDAY``), so the schedule does not
need a second weekly job — a single daily task files, scans, and quietly drafts
the chase emails when that day comes around. Keeping the day in one tested function beats keeping
it in a calendar entry nobody can read, and it means a run that Task Scheduler
misses (laptop closed on the draft day) still drafts when it next runs, rather than
skipping the week.

Paths differ on every machine, so the definition is generated rather than
committed: point it at the Python you use and the folder you keep your
clients in, and ``--install`` registers it with Task Scheduler in the same
step (``schtasks /create /xml ... /f``, so re-running is also how you change
the schedule).

Nothing generated here sends email. The scheduled command files documents,
updates the manifest and writes draft text files; a person still sends them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from xml.sax.saxutils import escape

from tracker.manifest import write_text_atomically
from tracker.runner import DRAFT_DAY_NAME, LOG_FLAG
from tracker.settings import SETTINGS_FILENAME, product_name

#: The scheduled task is named after the product, wherever that is set.
TASK_NAME = product_name()
DEFAULT_START = "07:00"
#: Filing and scanning repeat through the day this often (minutes); the
#: reminder still drafts only on the drafting day. 0 = once a day.
DEFAULT_REPEAT_MINUTES = 120
#: The generated Task Scheduler definition, beside the app's settings.
SCHEDULE_XML_FILENAME = "tax-tracker.xml"
#: The job never overruns the next daily start.
EXECUTION_TIME_LIMIT = "PT2H"
#: Any date in the past will do for a daily trigger; it is when the series began.
_START_BOUNDARY_DATE = "2026-01-01"


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
ROOT_FLAG = "--root"
OUT_FLAG = "--out"
FORMAT_FLAG = "--format"
START_FLAG = "--start"
FORMAT_XML = "xml"
FORMAT_N8N = "n8n"
FORMATS = (FORMAT_XML, FORMAT_N8N)
INSTALL_HINT = f"{MODULE_INVOCATION} {INSTALL_FLAG}"

def is_scheduling_host() -> bool:
    """Whether this machine can register the task (Task Scheduler is Windows only)."""
    import platform

    return platform.system() == "Windows"


def runner_arguments(root: str | Path) -> str:
    """The one command line the scheduled job runs, whoever schedules it."""
    return f'-m tracker.runner "{root}" {LOG_FLAG}'


def _xml_escape(value: str) -> str:
    return escape(str(value))


def is_absolute_path(text: str) -> bool:
    """True for an absolute path in *either* flavour, whatever OS we are on.

    The job is generated for Windows but may well be generated from anywhere,
    and ``pathlib`` on Linux does not consider ``D:\\Clients`` absolute — which
    would silently graft the working directory onto the front of it.
    """
    return PureWindowsPath(text).is_absolute() or PurePosixPath(text).is_absolute()


def resolve_root(root: str, working_dir: str) -> str:
    """The clients root as the scheduled job will see it.

    A relative root hangs off the working directory, joined in the flavour
    of that directory so a Windows task never ends up with a mixed separator.
    """
    if is_absolute_path(root):
        return root
    flavour = PureWindowsPath if is_absolute_path(working_dir) and (
        PureWindowsPath(working_dir).drive or working_dir.startswith("\\\\")
    ) else PurePosixPath
    return str(flavour(working_dir) / root)


def task_scheduler_xml(
    *,
    python: str | Path,
    root: str | Path,
    working_dir: str | Path,
    start_time: str = DEFAULT_START,
    repeat_minutes: int = 0,
    author: str = "",
    task_name: str = TASK_NAME,
) -> str:
    """A Windows Task Scheduler definition, ready for ``schtasks /create /xml``.

    ``repeat_minutes`` adds an intra-day repetition so filing and scanning can
    run through the day; the reminder step still only drafts on ``DRAFT_WEEKDAY``.
    """
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
    <Description>Files and scans every engagement found under {_xml_escape(root)}.
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
      <Arguments>{_xml_escape(runner_arguments(root))}</Arguments>
      <WorkingDirectory>{_xml_escape(working_dir)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def n8n_workflow(
    *,
    python: str | Path,
    root: str | Path,
    working_dir: str | Path,
    hour: int | None = None,
    task_name: str = TASK_NAME,
) -> dict:
    """An n8n workflow: one cron trigger into one Execute Command node."""
    if hour is None:
        hour = start_hour()
    if not 0 <= hour <= 23:
        raise ValueError(f"hour must be 0-23, got {hour}")

    command = f'cd "{working_dir}" && "{python}" {runner_arguments(root)}'
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
    import platform
    import subprocess

    command = ["schtasks", "/create", "/xml", str(xml_path), "/tn", task_name, "/f"]
    if not is_scheduling_host():
        return command
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"schtasks failed ({completed.returncode}): "
            f"{(completed.stderr or completed.stdout).strip()}"
        )
    return command


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate the scheduled job that runs the tracker unattended"
    )
    parser.add_argument(ROOT_FLAG, default="",
                        help="the folder the firm keeps its clients in "
                             f"(default: the one in {SETTINGS_FILENAME})")
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

    if not ns.root:
        from tracker.settings import clients_root, settings_path

        configured = clients_root()
        if configured is None:
            parser.error(f"no {ROOT_FLAG} given and none in {settings_path()}")
        ns.root = str(configured)
    root_arg = resolve_root(ns.root, ns.working_dir)

    try:
        if ns.format == FORMAT_XML:
            hhmm = ns.start.strip()
            if len(hhmm) != 5 or hhmm[2] != ":" or not hhmm.replace(":", "").isdigit():
                parser.error(f"{START_FLAG} must be HH:MM, got {ns.start!r}")
            payload = task_scheduler_xml(
                python=ns.python,
                root=root_arg,
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
                    root=root_arg,
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
            import platform

            try:
                command = install_task(ns.out, ns.name)
            except RuntimeError as exc:
                raise SystemExit(f"Not installed: {exc}")
            if is_scheduling_host():
                print(f'Installed as "{ns.name}" - it runs daily from {ns.start}.')
            else:
                print("Not Windows; run this on the scheduling machine:  " + " ".join(command))
        elif ns.format == FORMAT_XML:
            print(f'Install it with:  {MODULE_INVOCATION} {ROOT_FLAG} "{ns.root}" '
                  f'{OUT_FLAG} "{ns.out}" {INSTALL_FLAG}')
    else:
        print(payload, end="")
