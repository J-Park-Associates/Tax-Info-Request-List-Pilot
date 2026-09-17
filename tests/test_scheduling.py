"""Tests for tracker/scheduling.py — the generated unattended job.

A scheduled task nobody can read is a task nobody can fix, so what matters
here is that the generated definition is well-formed, points at the right
command, and says plainly that it drafts rather than sends.
"""

import json
from xml.etree import ElementTree

import pytest

from tracker.scheduling import (
    TASK_NAME,
    is_absolute_path,
    n8n_workflow,
    resolve_root,
    task_scheduler_xml,
)

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}

ARGS = dict(
    python=r"C:\Python311\python.exe",
    root=r"D:\OneDrive\Clients",
    working_dir=r"C:\Tools\tax-tracker",
)


def parsed(**overrides):
    return ElementTree.fromstring(task_scheduler_xml(**{**ARGS, **overrides}))


def test_the_xml_is_well_formed_and_runs_the_runner():
    root = parsed()
    command = root.find(".//t:Exec/t:Command", NS).text
    arguments = root.find(".//t:Exec/t:Arguments", NS).text

    assert command == ARGS["python"]
    assert "-m tracker.runner" in arguments
    assert ARGS["root"] in arguments


def test_the_job_runs_daily_so_saturday_is_never_missed():
    """The runner decides the day, so one daily task covers the weekly draft."""
    root = parsed()
    assert root.find(".//t:ScheduleByDay/t:DaysInterval", NS).text == "1"
    assert root.find(".//t:CalendarTrigger/t:StartBoundary", NS).text.endswith("T07:00:00")


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


def test_an_absolute_root_is_left_exactly_as_given():
    root = r"D:\OneDrive\Clients"
    assert resolve_root(root, r"C:\Tools\tax-tracker") == root


def test_a_relative_root_joins_in_the_flavour_of_the_working_directory():
    assert resolve_root("Clients", r"C:\Tools\tax-tracker") == (
        r"C:\Tools\tax-tracker\Clients"
    )
    assert resolve_root("Clients", "/opt/tracker") == "/opt/tracker/Clients"


# ---------------------------------------------------------------------- n8n ----


def test_the_n8n_workflow_is_valid_json_with_one_wired_connection():
    workflow = json.loads(json.dumps(n8n_workflow(**ARGS)))

    assert workflow["name"] == TASK_NAME
    assert [node["name"] for node in workflow["nodes"]] == ["Every day", "File, scan, draft"]
    wired = workflow["connections"]["Every day"]["main"][0][0]["node"]
    assert wired == "File, scan, draft"


def test_the_n8n_command_runs_the_runner_from_the_working_directory():
    command = n8n_workflow(**ARGS)["nodes"][1]["parameters"]["command"]
    assert ARGS["working_dir"] in command
    assert "-m tracker.runner" in command
    assert ARGS["root"] in command


def test_the_n8n_hour_is_validated():
    assert n8n_workflow(**ARGS, hour=18)["nodes"][0]["parameters"]["rule"][
        "interval"][0]["triggerAtHour"] == 18
    with pytest.raises(ValueError, match="hour must be 0-23"):
        n8n_workflow(**ARGS, hour=25)


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
