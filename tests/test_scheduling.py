"""Tests for tracker/scheduling.py — the generated unattended job.

A scheduled task nobody can read is a task nobody can fix, so what matters
here is that the generated definition is well-formed, points at the right
command, and says plainly that it drafts rather than sends.
"""

import datetime as dt
import json
import os
from xml.etree import ElementTree

import pytest

# At collection, before any test's fixtures replace it (decision 209).
from tests.conftest import REAL_TASK_SCHEDULER_HERE
from tracker import scheduling
from tracker import settings as settings_module
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


class Said:
    """What a faked ``schtasks`` answers: an exit code and what it printed."""

    def __init__(self, returncode=0, stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, "", stderr


def fake_schtasks(monkeypatch, *, exists=False, delete_fails=False, create_fails=False):
    """This computer has Task Scheduler, and its ``schtasks`` is this fake:
    every command it is given is kept, in order (decision 209 - no test
    reaches the real one)."""
    from tracker import scheduling

    calls = []

    def answer(command):
        calls.append(command)
        verb = command[1]
        if verb == "/query":
            return Said(0 if exists else 1)
        if verb == "/delete":
            return Said(1, "ERROR: Access is denied.") if delete_fails else Said()
        return Said(1, "ERROR: Access is denied.") if create_fails else Said()

    monkeypatch.setattr(scheduling, "task_scheduler_here", lambda: True)
    monkeypatch.setattr(scheduling, "_schtasks", answer)
    return calls


def test_install_runs_schtasks_on_windows_and_only_shows_the_command_elsewhere(monkeypatch, tmp_path):
    from tracker.scheduling import install_task

    assert install_task(tmp_path / "t.xml", "Tax Tracker")[:3] == ["schtasks", "/create", "/xml"]
    calls = fake_schtasks(monkeypatch)
    command = install_task(tmp_path / "t.xml", "Tax Tracker")
    assert calls == [command]
    assert command[-3:] == ["/tn", "Tax Tracker", "/f"]

    fake_schtasks(monkeypatch, create_fails=True)
    with pytest.raises(RuntimeError, match="Access is denied"):
        install_task(tmp_path / "t.xml")


def test_task_scheduler_here_answers_only_whether_windows(monkeypatch):
    """Decision 209 renamed the function whose name said "the scheduling
    host" and whose body asked "is this Windows": it answers the second
    question, and nothing about which computer runs the schedule."""
    import platform

    from tracker import scheduling

    assert not hasattr(scheduling, "is_scheduling_host")
    for system, answer in (("Windows", True), ("Linux", False), ("Darwin", False)):
        monkeypatch.setattr(platform, "system", lambda system=system: system)
        assert REAL_TASK_SCHEDULER_HERE() is answer


def test_remove_task_deletes_only_an_existing_task(monkeypatch):
    from tracker import scheduling

    assert scheduling.remove_task() is False              # no Task Scheduler: nothing asked
    calls = fake_schtasks(monkeypatch, exists=False)
    assert scheduling.remove_task() is False
    assert calls == [["schtasks", "/query", "/tn", TASK_NAME]]

    calls = fake_schtasks(monkeypatch, exists=True)
    assert scheduling.remove_task() is True
    assert calls == [["schtasks", "/query", "/tn", TASK_NAME],
                     ["schtasks", "/delete", "/tn", TASK_NAME, "/f"]]

    fake_schtasks(monkeypatch, exists=True, delete_fails=True)
    with pytest.raises(RuntimeError, match="could not delete"):
        scheduling.remove_task()


def test_task_exists_asks_schtasks_and_only_exit_zero_is_yes(monkeypatch):
    """P198 (F6): the launch door's one question. Only exit 0 is "it is
    there"; any refusal is "not confirmed", so the caller registers again
    rather than trusting a task that may be gone."""
    from tracker import scheduling

    assert scheduling.task_exists() is False              # no Task Scheduler: nothing asked
    calls = fake_schtasks(monkeypatch, exists=True)
    assert scheduling.task_exists() is True
    assert calls == [["schtasks", "/query", "/tn", TASK_NAME]]
    fake_schtasks(monkeypatch, exists=False)
    assert scheduling.task_exists() is False
    monkeypatch.setattr(scheduling, "_schtasks", lambda command: Said(1, "ERROR: Access is denied."))
    assert scheduling.task_exists() is False

    def cannot_start(command):
        raise FileNotFoundError(2, "No such file", "schtasks")

    monkeypatch.setattr(scheduling, "_schtasks", cannot_start)
    with pytest.raises(OSError):
        scheduling.task_exists()


def test_task_query_hands_back_the_exit_code_and_asks_nothing_off_windows(monkeypatch):
    """The engine review's NIT-2: the launch keeps a refusal's exit code on
    the error log, so the question hands the code back, not just yes or no."""
    from tracker import scheduling

    assert scheduling.task_query() is None                 # no Task Scheduler: nothing asked
    fake_schtasks(monkeypatch, exists=True)
    assert scheduling.task_query() == 0
    monkeypatch.setattr(scheduling, "_schtasks", lambda command: Said(5, "ERROR: Access is denied."))
    assert scheduling.task_query() == 5 and scheduling.task_exists() is False


def test_a_schtasks_that_hangs_is_stopped_at_its_limit_as_an_os_error(monkeypatch):
    """The engine review's SHOULD-2: ``schtasks`` runs at every start inside
    the step's lock, so it is given :data:`SCHTASKS_TIME_LIMIT_SECONDS` and
    one that runs past it raises ``TimeoutError`` (an ``OSError``), which
    every caller says as Task Scheduler that cannot be reached - never "the
    task exists". The real ``_schtasks`` is asked; ``subprocess.run`` is
    the stand-in, so no real Task Scheduler is reached."""
    import subprocess

    from tests.conftest import REAL_SCHTASKS
    from tracker import scheduling

    given = {}

    def hangs(command, **kwargs):
        given.update(kwargs)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(scheduling.subprocess, "run", hangs)
    with pytest.raises(TimeoutError) as stopped:
        REAL_SCHTASKS(["schtasks", "/query", "/tn", TASK_NAME])
    assert isinstance(stopped.value, OSError)
    assert given["timeout"] == scheduling.SCHTASKS_TIME_LIMIT_SECONDS == 60
    assert str(stopped.value) == scheduling.SCHTASKS_TOO_LONG.format(seconds=60)

    monkeypatch.setattr(scheduling, "task_scheduler_here", lambda: True)
    monkeypatch.setattr(scheduling, "_schtasks", REAL_SCHTASKS)
    with pytest.raises(OSError):
        scheduling.task_exists()


def test_register_here_is_the_one_registration(monkeypatch, tmp_path):
    """Decision 209: the repair path and the after-install step both come
    through ``register_here``. The job names the app's settings folder and
    no clients root (decision 131), from source with this Python and in the
    packaged app with its own executable in runner mode. The task's file
    goes where decision 186 puts it."""
    import sys

    from tracker.runner import LOG_FLAG, RUNNER_MODE_FLAG, SETTINGS_FLAG
    from tracker.scheduling import (
        SCHEDULE_XML_ENCODING,
        quote_argument,
        register_here,
        schedule_xml_path,
    )

    folder = tmp_path / "app"
    folder.mkdir()
    calls = fake_schtasks(monkeypatch)
    command = register_here(folder, start="06:30", every=60)
    xml_path = schedule_xml_path()                   # the data home (decision 186), never the settings folder
    assert not (folder / xml_path.name).exists()
    assert calls == [command] and command[:4] == ["schtasks", "/create", "/xml", str(xml_path)]
    xml = xml_path.read_text(encoding=SCHEDULE_XML_ENCODING)
    assert f"{SETTINGS_FLAG} {quote_argument(folder)}" in xml
    assert "T06:30:00" in xml and "PT60M" in xml and "-m tracker.runner" in xml

    exe = tmp_path / "package" / "resources" / "api" / "api.exe"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    register_here(folder)
    xml = xml_path.read_text(encoding=SCHEDULE_XML_ENCODING)
    assert f"<Command>{exe}</Command>" in xml
    assert f"<Arguments>{RUNNER_MODE_FLAG} " in xml and LOG_FLAG in xml and str(folder) in xml
    assert f"<WorkingDirectory>{exe.parent}</WorkingDirectory>" in xml
    assert "-m tracker.runner" not in xml


@pytest.mark.parametrize(("content", "named"), [
    ("office-pc\n", "office-pc"),
    ("  OFFICE-PC  \r\n\n", "office-pc"),
    ("\ufeffjppc", "jppc"),
    ("a" * 63, "a" * 63),
    ("a" * 64, None),
    ("", None),
    ("office-pc\nlaptop\n", None),
    ("office pc", None),
    ("office-pc;rm", None),
    ("office-pc\n" + " " * 300, None),
])
def test_the_designation_is_one_computer_name(tmp_path, content, named):
    """Decision 209: the designation file is one line naming one computer as
    ``locking.this_host`` normalises it - or it is unreadable, a failure,
    never a guess, and its content is never quoted back."""
    from tracker.layout import designation_file
    from tracker.scheduling import DESIGNATION_UNREADABLE, DesignationError, designated_machine

    root = tmp_path / "Clients"
    designation_file(root).parent.mkdir(parents=True)
    assert designated_machine(root) is None
    designation_file(root).write_bytes(content.encode("utf-8"))
    if named is not None:
        assert designated_machine(root) == named
        return
    with pytest.raises(DesignationError) as refused:
        designated_machine(root)
    assert str(refused.value) == DESIGNATION_UNREADABLE.format(file=designation_file(root))
    for word in ("office", "laptop", ";rm", "aaa"):
        assert word not in str(refused.value)


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


def test_the_packaged_job_names_the_product_for_the_fill_and_the_source_job_does_not():
    """P201 R6 (``pilot/SPEC-firm-cache-fill.md``): the pass fills the firm
    cache through a child that imports the API, which reads the product's
    name at import; a frozen build has no package.json and Task Scheduler
    passes no environment, so the packaged line names it - before the
    settings folder, so the line still ends as decision 131's does. A
    checkout reads package.json, so its line (and the README's quotation
    of it) is unchanged."""
    from tracker.runner import PRODUCT_FLAG, RUNNER_MODE_FLAG, SETTINGS_FLAG, _parser
    from tracker.scheduling import quote_argument, runner_arguments
    from tracker.settings import product_name

    packaged = runner_arguments(ARGS["settings"], frozen=True)
    assert packaged.startswith(f"{RUNNER_MODE_FLAG} {PRODUCT_FLAG} {quote_argument(product_name())} {SETTINGS_FLAG} ")
    assert PRODUCT_FLAG not in runner_arguments(ARGS["settings"])
    said = _parser().parse_args([PRODUCT_FLAG, product_name(), SETTINGS_FLAG, ARGS["settings"]])
    assert said.product == product_name()


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


def test_the_task_xml_is_escaped_exactly_as_before():
    """Decision 194 (D8): the escape moved off ``xml.sax.saxutils`` - which
    loads a network library - to ``html.escape(quote=False)``, and the task
    file is byte-identical: ``&``, ``<`` and ``>`` escaped, quotes left as
    they are, so a quoted Windows path in ``<Arguments>`` reads the same.
    The test may import saxutils; ``tracker/`` may not."""
    from xml.sax.saxutils import escape

    from tracker import scheduling

    for text in ('A & B <Park> "quoted" \'single\'',
                 '--settings "C:\\Program Files\\J Park & Associates\\" --log',
                 "&amp; already escaped &lt;", "", "plain"):
        assert scheduling._xml_escape(text) == escape(text)
    assert scheduling._xml_escape(2026) == escape("2026")
def test_install_without_out_writes_the_task_file_into_the_data_home(monkeypatch, tmp_path, capsys):
    """Decision 186: ``--install`` alone writes the task's file into the
    tracker's data home, making the folder as it writes, and registers that
    file - never one beside the program or in the working folder."""
    import platform
    import runpy
    import sys

    from tracker.runner import SETTINGS_FLAG
    from tracker.scheduling import INSTALL_FLAG, SCHEDULE_XML_FILENAME, schedule_xml_path
    from tracker.settings import ENV_DATA_HOME

    home = tmp_path / "account-data"
    monkeypatch.setenv(ENV_DATA_HOME, str(home))
    monkeypatch.setattr(platform, "system", lambda: "Linux")    # install_task only shows its command
    monkeypatch.chdir(tmp_path)
    settings = tmp_path / "app"
    settings.mkdir()
    monkeypatch.setattr(sys, "argv", ["tracker.scheduling", SETTINGS_FLAG, str(settings), INSTALL_FLAG])

    runpy.run_module("tracker.scheduling", run_name="__main__")

    written = schedule_xml_path()
    assert written == home / SCHEDULE_XML_FILENAME and written.is_file()
    out = capsys.readouterr().out
    assert f"Wrote {written}" in out and f"/xml {written}" in out
    assert not (settings / SCHEDULE_XML_FILENAME).exists()
    assert not (tmp_path / SCHEDULE_XML_FILENAME).exists()


def test_the_command_line_install_refuses_a_program_on_a_removable_drive(monkeypatch, tmp_path, capsys):
    """Decision 186: the command line's ``--install`` refuses a program on a
    stick with the app's own sentence, before any file is written."""
    import runpy
    import sys

    from tracker import settings as settings_module
    from tracker.runner import SETTINGS_FLAG
    from tracker.scheduling import INSTALL_FLAG, schedule_xml_path

    monkeypatch.chdir(tmp_path)
    settings = tmp_path / "app"
    settings.mkdir()
    program = {settings_module.app_dir(), settings}     # the data home stays on the fixed disk
    monkeypatch.setattr(settings_module, "drive_type",
                        lambda path: settings_module.DRIVE_REMOVABLE if path in program
                        else settings_module.DRIVE_FIXED)
    monkeypatch.setattr(sys, "argv", ["tracker.scheduling", SETTINGS_FLAG, str(settings), INSTALL_FLAG])

    with pytest.raises(SystemExit) as stopped:
        runpy.run_module("tracker.scheduling", run_name="__main__")

    assert stopped.value.code == 2
    said = capsys.readouterr().err
    assert settings_module.PROGRAM_ON_REMOVABLE.format(folder=settings_module.app_dir()) in said
    assert not schedule_xml_path().exists()
    assert list(settings.iterdir()) == []


# ------------------------------------------- the schedule setting (P21) ----


@pytest.mark.parametrize("value", ["00:00", "07:00", "13:45", "23:59", " 06:30 "])
def test_every_allowed_start_time_is_accepted(value):
    assert scheduling.check_start(value) == value.strip()


@pytest.mark.parametrize("value", ["", "7:00", "24:00", "12:60", "12-30", "0700", "07:00:00", "ab:cd",
                                   "٠٧:٠٠", None, 700])
def test_a_start_time_that_is_not_hh_mm_is_refused_naming_the_value(value):
    with pytest.raises(scheduling.ScheduleChoiceError) as refused:
        scheduling.check_start(value)
    assert repr(value) in str(refused.value) and "HH:MM" in str(refused.value)


@pytest.mark.parametrize("value", [0, 30, 60, 120, 240, 480, "120", " 0 "])
def test_every_allowed_interval_is_accepted(value):
    assert scheduling.check_every(value) == int(value)
    assert scheduling.EVERY_CHOICES == (0, 30, 60, 120, 240, 480)


@pytest.mark.parametrize("value", [15, -30, 90, 1440, 1.5, "1.5", "", "often", None, True, False])
def test_an_interval_that_is_not_a_choice_is_refused_naming_the_value(value):
    with pytest.raises(scheduling.ScheduleChoiceError) as refused:
        scheduling.check_every(value)
    assert repr(value) in str(refused.value) and "once a day" in str(refused.value)


def test_a_once_a_day_task_has_no_repetition_and_a_repeating_one_has():
    assert parsed(repeat_minutes=0).find(".//t:Repetition", NS) is None
    assert parsed(repeat_minutes=480).find(".//t:Repetition/t:Interval", NS).text == "PT480M"


def test_once_a_day_is_said_as_every_day_at_the_start_time():
    daily = scheduling.SCHEDULE_REGISTERED_DAILY.format(start="06:30")
    assert daily == "The schedule is set: every day at 06:30, with this computer's copy of the app."
    assert "minutes" not in daily and "minutes" not in scheduling.SCHEDULE_CLAIMED_DAILY
    assert scheduling.SCHEDULE_CLAIMED_DAILY.format(host="pc", start="06:30").endswith("every day at 06:30.")


def test_register_here_refuses_a_bad_choice_before_writing_anything(monkeypatch, tmp_path):
    fake_schtasks(monkeypatch)
    monkeypatch.setattr(scheduling, "task_scheduler_here", lambda: True)
    with pytest.raises(scheduling.ScheduleChoiceError):
        scheduling.register_here(tmp_path, start="25:00")
    with pytest.raises(scheduling.ScheduleChoiceError):
        scheduling.register_here(tmp_path, every=17)
    assert not scheduling.schedule_xml_path().exists()


def test_the_command_line_uses_the_one_start_time_check(monkeypatch, tmp_path, capsys):
    import runpy
    import sys

    from tracker.runner import SETTINGS_FLAG

    app = tmp_path / "app"
    app.mkdir()
    monkeypatch.setattr(sys, "argv", ["tracker.scheduling", SETTINGS_FLAG, str(app),
                                      scheduling.START_FLAG, "7pm"])
    with pytest.raises(SystemExit) as stopped:
        runpy.run_module("tracker.scheduling", run_name="__main__")
    assert stopped.value.code == 2
    assert settings_module.START_REFUSED.format(value="7pm") in capsys.readouterr().err


def test_the_command_line_uses_the_one_interval_check(monkeypatch, tmp_path, capsys):
    import runpy
    import sys

    from tracker.runner import SETTINGS_FLAG

    app = tmp_path / "app"
    app.mkdir()
    monkeypatch.setattr(sys, "argv", ["tracker.scheduling", SETTINGS_FLAG, str(app), "--every", "45"])
    with pytest.raises(SystemExit) as stopped:
        runpy.run_module("tracker.scheduling", run_name="__main__")
    assert stopped.value.code == 2
    assert settings_module.EVERY_REFUSED.format(value="45") in capsys.readouterr().err


NOW = dt.datetime(2026, 3, 2, 10, 0)


@pytest.mark.parametrize(("start", "every", "now", "expected"), [
    ("07:00", 120, NOW, "Next run: today at 11:00"),                       # 07, 09, 11
    ("07:00", 120, dt.datetime(2026, 3, 2, 6, 0), "Next run: today at 07:00"),
    ("07:00", 120, dt.datetime(2026, 3, 2, 23, 30), "Next run: tomorrow at 01:00"),  # yesterday's series runs on
    ("07:00", 480, dt.datetime(2026, 3, 2, 23, 30), "Next run: tomorrow at 07:00"),  # 07, 15, 23, then 07
    ("13:00", 0, NOW, "Next run: today at 13:00"),
    ("07:00", 0, NOW, "Next run: tomorrow at 07:00"),
    ("07:00", 0, dt.datetime(2026, 3, 2, 7, 0), "Next run: tomorrow at 07:00"),   # a run at this minute has begun
    ("07:00", 60, dt.datetime(2026, 3, 2, 3, 15), "Next run: today at 04:00"),
])
def test_the_next_run_is_worked_out_from_the_start_the_interval_and_the_time(start, every, now, expected):
    chosen = scheduling.SchedulePreference(True, start, every)
    assert scheduling.next_run(chosen, now) == expected


def test_no_next_run_is_promised_while_the_schedule_is_off():
    assert scheduling.next_run(scheduling.SchedulePreference(False, "07:00", 120), NOW) == ""
