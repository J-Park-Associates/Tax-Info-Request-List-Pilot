"""Generate the scheduled job that runs the tracker unattended (component 10).

Emits a Windows Task Scheduler job definition, or the n8n equivalent, for::

    python -m tracker.runner <clients root>

**One task, not two.** The runner decides for itself whether today is the day
to draft reminders, so the schedule does not need a second weekly job — a
single daily task files, scans, and quietly drafts the chase emails when
Saturday comes around. Keeping the day in one tested function beats keeping
it in a calendar entry nobody can read, and it means a run that Task Scheduler
misses (laptop closed on Saturday) still drafts when it next runs, rather than
skipping the week.

Paths differ on every machine, so the definition is generated rather than
committed: point it at the Python you use and the folder you keep your
clients in, and import the XML with ``schtasks /create /xml``.

Nothing generated here sends email. The scheduled command files documents,
updates the manifest and writes draft text files; a person still sends them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from xml.sax.saxutils import escape

TASK_NAME = "Tax Document Tracker"
DEFAULT_START = "07:00"


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
    run through the day; the reminder step still only drafts on Saturday.
    """
    if repeat_minutes and repeat_minutes < 5:
        raise ValueError("repeat_minutes below 5 would stack runs on top of each other")

    repetition = ""
    if repeat_minutes:
        repetition = (
            "\n      <Repetition>"
            f"\n        <Interval>PT{repeat_minutes}M</Interval>"
            "\n        <Duration>P1D</Duration>"
            "\n        <StopAtDurationEnd>true</StopAtDurationEnd>"
            "\n      </Repetition>"
        )

    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>{_xml_escape(author)}</Author>
    <Description>Files and scans every engagement found under {_xml_escape(root)}.
On Saturdays it also drafts the client reminder emails. It never sends them.</Description>
    <URI>\\{_xml_escape(task_name)}</URI>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T{_xml_escape(start_time)}:00</StartBoundary>
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
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <WakeToRun>false</WakeToRun>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{_xml_escape(python)}</Command>
      <Arguments>-m tracker.runner "{_xml_escape(root)}" --log</Arguments>
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
    hour: int = 7,
    task_name: str = TASK_NAME,
) -> dict:
    """An n8n workflow: one cron trigger into one Execute Command node."""
    if not 0 <= hour <= 23:
        raise ValueError(f"hour must be 0-23, got {hour}")

    command = f'cd "{working_dir}" && "{python}" -m tracker.runner "{root}" --log'
    return {
        "name": task_name,
        "nodes": [
            {
                "parameters": {
                    "rule": {"interval": [{"field": "days", "triggerAtHour": hour}]}
                },
                "name": "Every day",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.1,
                "position": [260, 300],
            },
            {
                "parameters": {"command": command},
                "name": "File, scan, draft",
                "type": "n8n-nodes-base.executeCommand",
                "typeVersion": 1,
                "position": [500, 300],
            },
        ],
        "connections": {
            "Every day": {
                "main": [[{"node": "File, scan, draft", "type": "main", "index": 0}]]
            }
        },
        "settings": {"executionOrder": "v1"},
    }


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate the scheduled job that runs the tracker unattended"
    )
    parser.add_argument("--root", required=True,
                        help="the folder the firm keeps its clients in")
    parser.add_argument("--python", default=sys.executable,
                        help="the Python to run it with (default: this one)")
    parser.add_argument("--working-dir", default=str(Path.cwd()),
                        help="the folder holding the tracker package")
    parser.add_argument("--start", default=DEFAULT_START,
                        help=f"daily start time, HH:MM (default: {DEFAULT_START})")
    parser.add_argument("--every", type=int, default=0, metavar="MINUTES",
                        help="also repeat through the day, e.g. 120 for every 2 hours")
    parser.add_argument("--author", default="", help="task author, for the XML")
    parser.add_argument("--name", default=TASK_NAME, help="task name")
    parser.add_argument("--format", choices=("xml", "n8n"), default="xml",
                        help="Windows Task Scheduler XML (default) or an n8n workflow")
    parser.add_argument("--out", default="",
                        help="write to this file instead of standard output")
    ns = parser.parse_args()

    root_arg = resolve_root(ns.root, ns.working_dir)

    try:
        if ns.format == "xml":
            hhmm = ns.start.strip()
            if len(hhmm) != 5 or hhmm[2] != ":" or not hhmm.replace(":", "").isdigit():
                parser.error(f"--start must be HH:MM, got {ns.start!r}")
            payload = task_scheduler_xml(
                python=ns.python,
                root=root_arg,
                working_dir=ns.working_dir,
                start_time=hhmm,
                repeat_minutes=ns.every,
                author=ns.author,
                task_name=ns.name,
            )
            encoding = "utf-16"
        else:
            payload = json.dumps(
                n8n_workflow(
                    python=ns.python,
                    root=root_arg,
                    working_dir=ns.working_dir,
                    hour=int(ns.start.split(":")[0]),
                    task_name=ns.name,
                ),
                indent=2,
            ) + "\n"
            encoding = "utf-8"
    except ValueError as exc:
        parser.error(str(exc))

    if ns.out:
        # Task Scheduler wants UTF-16 for an XML it will import.
        Path(ns.out).write_text(payload, encoding=encoding)
        print(f"Wrote {ns.out}")
        if ns.format == "xml":
            print(f'Import it with:  schtasks /create /xml "{ns.out}" /tn "{ns.name}"')
    else:
        print(payload, end="")
