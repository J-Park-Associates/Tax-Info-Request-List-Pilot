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
    resolve_registry,
    task_scheduler_xml,
)

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}

ARGS = dict(
    python=r"C:\Python311\python.exe",
    registry=r"D:\OneDrive\Clients\engagements.yaml",
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
    assert ARGS["registry"] in arguments


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
    r"D:\OneDrive\Clients\engagements.yaml",
    r"\\server\share\engagements.yaml",
    "/srv/clients/engagements.yaml",
])
def test_absolute_paths_are_recognized_in_either_flavour(text):
    """A Windows path is absolute even when the XML is generated on Linux."""
    assert is_absolute_path(text) is True


@pytest.mark.parametrize("text", ["engagements.yaml", r"Clients\engagements.yaml",
                                  "Clients/engagements.yaml"])
def test_relative_paths_are_not_mistaken_for_absolute(text):
    assert is_absolute_path(text) is False


def test_an_absolute_registry_is_left_exactly_as_given():
    registry = r"D:\OneDrive\Clients\engagements.yaml"
    assert resolve_registry(registry, r"C:\Tools\tax-tracker") == registry


def test_a_relative_registry_joins_in_the_flavour_of_the_working_directory():
    assert resolve_registry("engagements.yaml", r"C:\Tools\tax-tracker") == (
        r"C:\Tools\tax-tracker\engagements.yaml"
    )
    assert resolve_registry("engagements.yaml", "/opt/tracker") == (
        "/opt/tracker/engagements.yaml"
    )


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
    assert ARGS["registry"] in command


def test_the_n8n_hour_is_validated():
    assert n8n_workflow(**ARGS, hour=18)["nodes"][0]["parameters"]["rule"][
        "interval"][0]["triggerAtHour"] == 18
    with pytest.raises(ValueError, match="hour must be 0-23"):
        n8n_workflow(**ARGS, hour=25)
