"""Tests for tracker/scheduling.py — the generated unattended job.

A scheduled task nobody can read is a task nobody can fix, so what matters
here is that the generated definition is well-formed, points at the right
command, and says plainly that it drafts rather than sends.
"""

import json
import os
from xml.etree import ElementTree

import pytest

from tracker.scheduling import (
    DEFAULT_START,
    N8N_RUN_NODE,
    N8N_TRIGGER_NODE,
    TASK_NAME,
    TASK_XML_NAMESPACE,
    is_absolute_path,
    n8n_workflow,
    resolve_folder,
    task_scheduler_xml,
)

NS = {"t": TASK_XML_NAMESPACE}

ARGS = dict(
    python=r"C:\Python311\python.exe",
    settings=r"C:\Tools\tax-tracker",
    working_dir=r"C:\Tools\tax-tracker",
)
#: A clients root, to show that no job ever carries one (decision 131).
ROOT = r"D:\OneDrive\Clients"


def parsed(**overrides):
    return ElementTree.fromstring(task_scheduler_xml(**{**ARGS, **overrides}))


def test_the_xml_is_well_formed_and_runs_the_runner():
    root = parsed()
    command = root.find(".//t:Exec/t:Command", NS).text
    arguments = root.find(".//t:Exec/t:Arguments", NS).text

    assert command == ARGS["python"]
    assert "-m tracker.runner" in arguments
    assert ARGS["settings"] in arguments


def test_the_job_runs_daily_so_saturday_is_never_missed():
    """The runner decides the day, so one daily task covers the weekly draft."""
    root = parsed()
    assert root.find(".//t:ScheduleByDay/t:DaysInterval", NS).text == "1"
    assert root.find(".//t:CalendarTrigger/t:StartBoundary", NS).text.endswith(f"T{DEFAULT_START}:00")


def test_a_repeat_interval_is_optional_and_well_formed():
    assert parsed().find(".//t:Repetition", NS) is None

    root = parsed(repeat_minutes=120)
    assert root.find(".//t:Repetition/t:Interval", NS).text == "PT120M"
    assert root.find(".//t:Repetition/t:Duration", NS).text == "P1D"


def test_overlapping_runs_are_refused_by_the_task_itself():
    """The scanner already holds a lock; the task should not queue runs either."""
    assert parsed().find(".//t:MultipleInstancesPolicy", NS).text == "IgnoreNew"


def test_a_missed_run_is_picked_up_rather_than_skipped():
    assert parsed().find(".//t:StartWhenAvailable", NS).text == "true"


def test_a_too_frequent_repeat_is_refused():
    with pytest.raises(ValueError, match="stack runs"):
        task_scheduler_xml(**ARGS, repeat_minutes=1)


def test_the_description_says_it_drafts_and_does_not_send():
    description = parsed().find(".//t:Description", NS).text
    assert "drafts" in description
    assert "never sends" in description


def test_paths_with_xml_characters_are_escaped():
    root = parsed(author="Park & Associates")
    assert root.find(".//t:RegistrationInfo/t:Author", NS).text == "Park & Associates"


def test_the_start_time_can_be_moved():
    root = parsed(start_time="18:30")
    assert root.find(".//t:CalendarTrigger/t:StartBoundary", NS).text.endswith("T18:30:00")


# ----------------------------------------------------------------- the paths ----


@pytest.mark.parametrize("text", [
    r"D:\OneDrive\Clients",
    r"\\server\share\Clients",
    "/srv/clients",
])
def test_absolute_paths_are_recognized_in_either_flavour(text):
    """A Windows path is absolute even when the XML is generated on Linux."""
    assert is_absolute_path(text) is True


@pytest.mark.parametrize("text", ["Clients", r"OneDrive\Clients", "OneDrive/Clients"])
def test_relative_paths_are_not_mistaken_for_absolute(text):
    assert is_absolute_path(text) is False


def test_an_absolute_folder_is_left_exactly_as_given():
    folder = r"D:\Apps\Tracker"
    assert resolve_folder(folder, r"C:\Tools\tax-tracker") == folder


def test_a_relative_folder_joins_in_the_flavour_of_the_working_directory():
    assert resolve_folder("app", r"C:\Tools\tax-tracker") == (
        r"C:\Tools\tax-tracker\app"
    )
    assert resolve_folder("app", "/opt/tracker") == "/opt/tracker/app"


# ---------------------------------------------------------------------- n8n ----


def test_the_n8n_workflow_is_valid_json_with_one_wired_connection():
    workflow = json.loads(json.dumps(n8n_workflow(**ARGS)))

    assert workflow["name"] == TASK_NAME
    assert [node["name"] for node in workflow["nodes"]] == [N8N_TRIGGER_NODE, N8N_RUN_NODE]
    wired = workflow["connections"][N8N_TRIGGER_NODE]["main"][0][0]["node"]
    assert wired == N8N_RUN_NODE


def test_the_n8n_command_runs_the_runner_from_the_working_directory():
    command = n8n_workflow(**ARGS)["nodes"][1]["parameters"]["command"]
    assert ARGS["working_dir"] in command
    assert "-m tracker.runner" in command
    assert ARGS["settings"] in command


def test_the_n8n_hour_is_validated():
    assert n8n_workflow(**ARGS, hour=18)["nodes"][0]["parameters"]["rule"][
        "interval"][0]["triggerAtHour"] == 18
    with pytest.raises(ValueError, match="hour must be 0-23"):
        n8n_workflow(**ARGS, hour=25)


def test_the_n8n_command_reads_the_same_in_cmd_and_sh():
    """D-11: n8n hands the one line to cmd on Windows and to sh elsewhere.
    Every value is quoted by the settings folder's rule, and the line holds
    none of the characters the two shells read differently - so what is
    inside each pair of quotes is the value itself, in either shell."""
    from tracker.scheduling import SHELL_SPECIAL, quote_argument, runner_arguments

    command = n8n_workflow(**ARGS)["nodes"][1]["parameters"]["command"]
    assert command == (f"cd {quote_argument(ARGS['working_dir'])} && {quote_argument(ARGS['python'])} "
                       f"{runner_arguments(ARGS['settings'])}")
    outside = command.split('"')[0::2]                      # the text outside every quoted value
    assert command.count('"') == 6                          # three values, each quoted once
    for char, _kind in SHELL_SPECIAL:
        assert all(char not in part for part in outside), char
    drive = "D:" + chr(92)
    assert f"cd {quote_argument(drive)} &&" in n8n_workflow(**{**ARGS, "working_dir": drive})[
        "nodes"][1]["parameters"]["command"]


@pytest.mark.parametrize("field", ["working_dir", "python", "settings"])
@pytest.mark.parametrize("char, kind", [('"', "a double quote"), ("%", "a percent sign"),
                                        ("$", "a dollar sign"), ("`", "a backtick"),
                                        ("!", "an exclamation mark"), ("\n", "a control character"),
                                        ("\x07", "a control character")])
def test_a_value_that_means_something_else_in_a_shell_is_refused(field, char, kind):
    """Refused, naming the field and the kind of character - never the value,
    which is a path and can carry a client's name."""
    value = ARGS[field] + char + "Secret Name"
    with pytest.raises(ValueError) as refused:
        n8n_workflow(**{**ARGS, field: value})
    message = str(refused.value)
    assert message.startswith(f"{field} holds {kind}")
    assert "Secret Name" not in message and ARGS[field] not in message


def test_install_runs_schtasks_on_windows_and_only_shows_the_command_elsewhere(monkeypatch, tmp_path):
    import platform
    import subprocess

    from tracker.scheduling import install_task

    calls = []
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    assert install_task(tmp_path / "t.xml", "Tax Tracker")[:3] == ["schtasks", "/create", "/xml"]
    assert calls == []

    monkeypatch.setattr(platform, "system", lambda: "Windows")

    class Done:
        returncode = 0
        stdout = "SUCCESS"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: (calls.append(cmd), Done())[1])
    command = install_task(tmp_path / "t.xml", "Tax Tracker")
    assert calls == [command]
    assert command[-3:] == ["/tn", "Tax Tracker", "/f"]

    class Failed(Done):
        returncode = 1
        stderr = "ERROR: Access is denied."

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: Failed())
    with pytest.raises(RuntimeError, match="Access is denied"):
        install_task(tmp_path / "t.xml")


def test_the_command_line_is_built_once_for_both_schedulers():
    from tracker.scheduling import runner_arguments, start_hour

    xml = task_scheduler_xml(**ARGS)
    flow = n8n_workflow(**ARGS)
    command = flow["nodes"][1]["parameters"]["command"]
    assert runner_arguments(ARGS["settings"]) in xml
    assert runner_arguments(ARGS["settings"]) in command
    assert start_hour(DEFAULT_START) == int(DEFAULT_START.split(":")[0]) and start_hour("18:30") == 18
    assert flow["nodes"][0]["parameters"]["rule"]["interval"][0]["triggerAtHour"] == start_hour()


def test_the_packaged_job_is_the_same_command_line_behind_the_api_executable():
    # The packaged app has no Python: its schedule runs its own executable
    # in runner mode. Same arguments after the program, one way in per host.
    from tracker.runner import LOG_FLAG, RUNNER_MODE_FLAG
    from tracker.scheduling import runner_arguments

    exe = r"C:\Apps\Tracker\resources\api\api.exe"
    root = parsed(python=exe, frozen=True)
    arguments = root.find(".//t:Exec/t:Arguments", NS).text
    assert root.find(".//t:Exec/t:Command", NS).text == exe
    assert arguments.startswith(RUNNER_MODE_FLAG) and "-m tracker.runner" not in arguments
    assert arguments == runner_arguments(ARGS["settings"], frozen=True)
    flow = n8n_workflow(**{**ARGS, "python": exe}, frozen=True)
    assert runner_arguments(ARGS["settings"], frozen=True) in flow["nodes"][1]["parameters"]["command"]

    tail = f'"{ARGS["settings"]}" {LOG_FLAG}'
    assert runner_arguments(ARGS["settings"]).endswith(tail)
    assert runner_arguments(ARGS["settings"], frozen=True).endswith(tail)


def test_the_time_limit_is_the_locks_run_limit_rendered():
    from tracker.locking import RUN_TIME_LIMIT_SECONDS
    from tracker.scheduling import EXECUTION_TIME_LIMIT, iso_duration

    limit = parsed().find(".//t:Settings/t:ExecutionTimeLimit", NS).text
    assert limit == EXECUTION_TIME_LIMIT == iso_duration(RUN_TIME_LIMIT_SECONDS)
    assert iso_duration(2 * 3600) == "PT2H" and iso_duration(90 * 60) == "PT90M"
    with pytest.raises(ValueError):
        iso_duration(61)


def test_the_description_names_the_drafting_day_from_the_runner():
    from tracker.runner import DRAFT_WEEKDAY, WEEKDAY_NAMES

    xml = task_scheduler_xml(**ARGS)
    assert f"On {WEEKDAY_NAMES[DRAFT_WEEKDAY].capitalize()}s it also drafts" in xml


@pytest.mark.skipif(os.name != "nt", reason="the Windows argument parser is the thing under test")
def test_a_clients_root_ending_in_a_backslash_survives_the_argument_parser():
    # A drive root or a share ends in a backslash; quoted as-is, the
    # Windows argument parser reads the backslash as escaping the quote and
    # the job gets one mangled argument. Proven against a real child process.
    import subprocess
    import sys

    from tracker.runner import RUNNER_MODE_FLAG
    from tracker.scheduling import quote_argument, runner_arguments

    sep = chr(92)
    for root in ("D:" + sep, "D:" + sep + "Clients", sep * 2 + "server" + sep + "share" + sep):
        command = f'"{sys.executable}" -c "import sys; print(sys.argv[1:])" {quote_argument(root)} --log'
        argv = subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()
        assert argv == repr([root, "--log"]), (root, argv)
    assert runner_arguments("D:" + "\\", frozen=True).startswith(f"{RUNNER_MODE_FLAG} ")


def test_the_scheduled_job_names_the_settings_folder_and_no_clients_root():
    """Decision 131: the clients root has one home, the settings file, and
    the job reads it at every run. The command line names the app's
    settings folder after ``SETTINGS_FLAG`` and carries no root; a folder
    ending in a backslash still has its backslash doubled before the
    closing quote; the description names the settings file."""
    from tracker.runner import LOG_FLAG, SETTINGS_FLAG
    from tracker.scheduling import quote_argument, runner_arguments
    from tracker.settings import SETTINGS_FILENAME

    root = parsed()
    arguments = root.find(".//t:Exec/t:Arguments", NS).text
    assert arguments == f'-m tracker.runner {SETTINGS_FLAG} "{ARGS["settings"]}" {LOG_FLAG}'
    assert ROOT not in task_scheduler_xml(**ARGS)
    description = root.find(".//t:Description", NS).text
    assert description.startswith("Files and scans every engagement under the clients root named in "
                                  + ARGS["settings"] + "\\" + SETTINGS_FILENAME)

    sep = chr(92)
    drive = "D:" + sep
    assert quote_argument(drive) == '"D:' + sep * 2 + '"'
    assert runner_arguments(drive, frozen=True).endswith(
        f'{SETTINGS_FLAG} "D:{sep * 2}" {LOG_FLAG}')
    # From anywhere: a POSIX settings folder is named in its own flavour.
    posix = task_scheduler_xml(**{**ARGS, "settings": "/srv/tracker"})
    assert f"/srv/tracker/{SETTINGS_FILENAME}" in posix
