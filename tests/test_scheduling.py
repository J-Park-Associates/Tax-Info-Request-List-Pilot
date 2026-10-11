"""Tests for tracker/scheduling.py — the generated unattended job.

A scheduled task nobody can read is a task nobody can fix, so what matters
here is that the generated definition is well-formed, points at the right
command, and says plainly that it drafts rather than sends.
"""

import datetime as dt
import os
import platform
from pathlib import Path
from xml.etree import ElementTree

import pytest

# At collection, before any test's fixtures replace it (decision 209).
from tests.conftest import REAL_SCHEDULER_HERE
from tracker import scheduling
from tracker import settings as settings_module
from tracker.scheduling import (
    DEFAULT_START,
    TASK_NAME,
    TASK_XML_NAMESPACE,
    is_absolute_path,
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

    # Windows' scheduler, whatever this is; a Windows runner stays Windows.
    monkeypatch.setattr(settings_module, "host_system", lambda: "nt" if os.name == "nt" else "posix")
    monkeypatch.setattr(scheduling, "scheduler_here", lambda: True)
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


def test_scheduler_here_answers_only_whether_this_computer_has_one(monkeypatch):
    """Decision 209 renamed the function whose name said "the scheduling
    host" and whose body asked "is this Windows"; SPEC-mac R24 renamed it
    again because a Mac has a scheduler too (launchd). It answers that
    question and nothing about which computer runs the schedule - and asks
    it through ``settings.host_system``, never the platform."""
    assert not hasattr(scheduling, "is_scheduling_host") and not hasattr(scheduling, "task_scheduler_here")
    for system, answer in (("nt", True), ("darwin", True), ("posix", False)):
        monkeypatch.setattr(settings_module, "host_system", lambda system=system: system)
        assert REAL_SCHEDULER_HERE() is answer


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

    monkeypatch.setattr(scheduling, "scheduler_here", lambda: True)
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


def test_the_job_carries_the_runners_command_line_as_the_runner_builds_it():
    from tracker.scheduling import runner_arguments

    assert runner_arguments(ARGS["settings"]) in task_scheduler_xml(**ARGS)


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
    monkeypatch.setattr(scheduling, "scheduler_here", lambda: True)
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


# ------------------------------------------------- the Mac: launchd (SPEC-mac R23-R25) ----

REPO = Path(__file__).resolve().parent.parent


def _plist(**overrides):
    import plistlib

    given = {"program": "/Applications/App.app/Contents/Resources/tracker-api/tracker-api",
             "settings": "/Users/office/Library/Application Support/Tax Document Console",
             "working_dir": "/Applications/App.app/Contents/Resources/tracker-api"}
    return plistlib.loads(scheduling.launch_agent_plist(**{**given, **overrides}))


def _minutes_the_windows_task_runs(xml: str) -> set[int]:
    """The minutes of the day the Task Scheduler XML implies: the start, and -
    with a ``Repetition`` of ``Interval`` for ``Duration P1D`` - every interval
    after it for a day, round the clock (not until midnight)."""
    task = ElementTree.fromstring(xml)
    hour, minute = (int(part) for part in
                    task.find(".//t:StartBoundary", NS).text.split("T")[1].split(":")[:2])
    begin = hour * 60 + minute
    repetition = task.find(".//t:Repetition", NS)
    if repetition is None:
        return {begin}
    interval = int(repetition.find("t:Interval", NS).text.removeprefix("PT").removesuffix("M"))
    assert repetition.find("t:Duration", NS).text == "P1D"
    return {(begin + k * interval) % 1440 for k in range(1440 // interval)}


@pytest.mark.parametrize("every", scheduling.EVERY_CHOICES)
@pytest.mark.parametrize("start", ["07:00", "23:30", "00:15"])
def test_the_mac_agent_runs_the_times_the_windows_task_runs(start, every):
    """R23: Task Scheduler's ``Duration P1D`` repeats around the clock from the
    start, so launchd - which has only calendar entries - is given the same
    set of times, 1440 / every of them, one for "once a day"."""
    xml = task_scheduler_xml(**ARGS, start_time=start, repeat_minutes=every)
    entries = _plist(start=start, every=every)["StartCalendarInterval"]
    minutes = [entry["Hour"] * 60 + entry["Minute"] for entry in entries]
    assert set(minutes) == _minutes_the_windows_task_runs(xml)
    assert len(minutes) == len(set(minutes)) == (1440 // every if every else 1)
    assert all(set(entry) == {"Hour", "Minute"} for entry in entries)
    assert all(0 <= entry["Hour"] < 24 and 0 <= entry["Minute"] < 60 for entry in entries)


def test_the_mac_agent_names_the_settings_folder_and_no_root():
    """R23 and decision 131: the job names the app's settings folder and the
    clients root is read from the settings file at every run."""
    packaged = _plist(frozen=True)
    folder = "/Users/office/Library/Application Support/Tax Document Console"
    assert packaged["ProgramArguments"] == [
        "/Applications/App.app/Contents/Resources/tracker-api/tracker-api",
        "--run", "--product", settings_module.product_name(), "--settings", folder, "--log"]
    source = _plist(frozen=False, program="/usr/bin/python3")["ProgramArguments"]
    assert source == ["/usr/bin/python3", "-m", "tracker.runner", "--settings", folder, "--log"]
    assert packaged["WorkingDirectory"].endswith("tracker-api")
    assert ROOT not in str(packaged) and "Clients" not in str(packaged)


def test_the_mac_agent_is_a_standard_process_with_no_run_at_load_named_for_the_app():
    plist = _plist()
    assert plist["Label"] == scheduling.LAUNCH_AGENT_LABEL == "com.jparkassociates.taxdocumentconsole.schedule"
    assert plist["ProcessType"] == "Standard"
    assert "RunAtLoad" not in plist and "KeepAlive" not in plist
    assert plist["AssociatedBundleIdentifiers"] == [scheduling.APP_BUNDLE_ID]
    assert set(plist) == {"Label", "ProgramArguments", "WorkingDirectory", "StartCalendarInterval",
                          "ProcessType", "AssociatedBundleIdentifiers"}


def test_the_bundle_id_is_the_one_the_shell_and_the_mac_build_name():
    """The agent names the app by the id the shell sets and the build gives
    the bundle, so Allow in the Background lists the schedule under the app."""
    assert f'app.setAppUserModelId("{scheduling.APP_BUNDLE_ID}")' in (REPO / "app" / "main.js").read_text("utf-8")
    assert f'APP_ID="{scheduling.APP_BUNDLE_ID}"' in (REPO / "build-mac.sh").read_text("utf-8")


@pytest.mark.parametrize("settings_folder", ["/Users/o/Library/Application Support/Tax Document Console",
                                             r"D:\Apps\Tracker", "D:\\", "/with space/and\"quote"])
def test_the_argument_list_and_the_windows_quoted_line_are_the_same_command(settings_folder):
    """``runner_arguments`` is the Windows-quoted join it always was, byte for byte,
    and ``runner_argv`` is the same tokens as the list launchd takes."""
    from tracker.runner import LOG_FLAG, PRODUCT_FLAG, RUNNER_MODE_FLAG, SETTINGS_FLAG

    quoted = scheduling.quote_argument(settings_folder)
    assert scheduling.runner_arguments(settings_folder) == f"-m tracker.runner {SETTINGS_FLAG} {quoted} {LOG_FLAG}"
    assert scheduling.runner_arguments(settings_folder, frozen=True) == (
        f'{RUNNER_MODE_FLAG} {PRODUCT_FLAG} "{settings_module.product_name()}" {SETTINGS_FLAG} {quoted} {LOG_FLAG}')
    assert scheduling.runner_argv(settings_folder) == ["-m", "tracker.runner", SETTINGS_FLAG, settings_folder, LOG_FLAG]
    assert scheduling.runner_argv(settings_folder, frozen=True) == [
        RUNNER_MODE_FLAG, PRODUCT_FLAG, settings_module.product_name(), SETTINGS_FLAG, settings_folder, LOG_FLAG]


def test_a_mac_registers_through_launchctl_bootstrap(a_mac, tmp_path):
    """R24: the plist is written to ``~/Library/LaunchAgents`` (never the data
    home); then ``bootout`` (nothing loaded: that answer is ignored), ``bootstrap``
    and ``enable`` for the signed-in person's ``gui/<uid>`` domain."""
    import plistlib

    folder = tmp_path / "app"
    folder.mkdir()
    command = scheduling.register_here(folder, start="06:30", every=60)

    agent = tmp_path / "home" / "Library" / "LaunchAgents" / f"{scheduling.LAUNCH_AGENT_LABEL}.plist"
    assert scheduling.launch_agent_path() == agent and agent.is_file()
    assert not (scheduling.schedule_xml_path()).exists(), "the Windows task file is not written on a Mac"
    assert not list(agent.parent.glob("*.tmp")) and scheduling.schedule_file() == agent
    domain = scheduling._domain()
    service = f"{domain}/{scheduling.LAUNCH_AGENT_LABEL}"
    assert a_mac.launchd.calls == [["launchctl", "bootout", service],
                                   ["launchctl", "bootstrap", domain, str(agent)],
                                   ["launchctl", "enable", service]]
    assert command == a_mac.launchd.calls[1]
    on_disk = plistlib.loads(agent.read_bytes())
    assert on_disk["ProgramArguments"][-3:] == [scheduling.SETTINGS_FLAG, str(folder), "--log"]
    assert len(on_disk["StartCalendarInterval"]) == 24

    # Registering again unloads the loaded agent first, and loads it again.
    a_mac.launchd.calls.clear()
    scheduling.register_here(folder)
    assert a_mac.launchd.verbs() == ["bootout", "bootstrap", "enable"] and a_mac.launchd.loaded


def test_a_mac_refusal_to_load_the_agent_is_said_with_what_launchctl_said(a_mac, tmp_path):
    a_mac.launchd.refuse["bootstrap"] = (5, "Bootstrap failed: 5: Input/output error")
    with pytest.raises(RuntimeError, match=r"could not load the agent \(5\): Bootstrap failed: 5"):
        scheduling.register_here(tmp_path)
    a_mac.launchd.refuse = {"enable": (1, "Could not enable")}
    with pytest.raises(RuntimeError, match=r"could not enable the agent \(1\)"):
        scheduling.register_here(tmp_path)


def test_the_agents_domain_is_the_signed_in_persons_through_the_one_user_id_seam(a_mac):
    """Windows has no ``os.getuid``; the Mac branch asks only ``scheduling._uid``."""
    assert scheduling._domain() == "gui/501" and scheduling._service() == (
        f"gui/501/{scheduling.LAUNCH_AGENT_LABEL}")


def test_a_mac_asks_whether_its_agent_is_loaded_with_launchctl_print(a_mac):
    assert scheduling.task_query() == 113 and scheduling.task_exists() is False
    assert a_mac.launchd.calls[0] == ["launchctl", "print", scheduling._service()]
    a_mac.launchd.loaded = True
    assert scheduling.task_query() == 0 and scheduling.task_exists() is True
    a_mac.launchd.refuse["print"] = (5, "Operation not permitted")
    assert scheduling.task_query() == 5 and scheduling.task_exists() is False


def test_a_mac_removes_its_agent_and_its_file(a_mac, tmp_path):
    assert scheduling.remove_task() is False and a_mac.launchd.verbs() == ["print"], \
        "nothing loaded and no file: nothing is removed"
    scheduling.register_here(tmp_path)
    a_mac.launchd.calls.clear()
    assert scheduling.remove_task() is True
    assert a_mac.launchd.verbs() == ["print", "bootout"] and not a_mac.launchd.loaded
    assert not scheduling.launch_agent_path().exists()

    scheduling.register_here(tmp_path)
    a_mac.launchd.refuse["bootout"] = (1, "Boot-out failed")
    with pytest.raises(RuntimeError, match="could not unload the agent"):
        scheduling.remove_task()
    assert scheduling.launch_agent_path().exists(), "a file whose agent would not unload is kept"

    a_mac.launchd.refuse = {}
    a_mac.launchd.loaded = False                       # unloaded by hand, the file left behind
    assert scheduling.remove_task() is True and not scheduling.launch_agent_path().exists()


def test_a_mac_has_a_scheduler_and_the_windows_install_command_is_only_shown(a_mac, tmp_path):
    assert scheduling.scheduler_here() is True
    assert scheduling.install_task(tmp_path / "t.xml")[0] == "schtasks"      # shown, never run (no fake is given)


def test_a_launchctl_that_hangs_is_stopped_at_its_limit_as_an_os_error(monkeypatch):
    """R24: the same 60 seconds as ``schtasks`` - it runs at every start inside
    the after-install step's lock."""
    import subprocess

    from tests.conftest import REAL_LAUNCHCTL

    given = {}

    def hangs(command, **kwargs):
        given.update(kwargs)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(scheduling.subprocess, "run", hangs)
    with pytest.raises(TimeoutError) as stopped:
        REAL_LAUNCHCTL(["launchctl", "print", "gui/501/x"])
    assert isinstance(stopped.value, OSError)
    assert given["timeout"] == scheduling.SCHTASKS_TIME_LIMIT_SECONDS == 60
    assert str(stopped.value) == scheduling.LAUNCHCTL_TOO_LONG.format(seconds=60)


@pytest.mark.parametrize(("listed", "off"), [
    ('"{label}" => disabled', True),
    ('"{label}" => true', True),
    ('"{label}" => enabled', False),
    ('"{label}" => false', False),
    ('"com.example.other" => disabled', False),
    ('"{label}.other" => disabled', False),
])
def test_the_switch_in_login_items_is_read_from_print_disabled(a_mac, monkeypatch, listed, off):
    from tests.conftest import Said

    line = listed.format(label=scheduling.LAUNCH_AGENT_LABEL)
    monkeypatch.setattr(scheduling, "_launchctl",
                        lambda command: Said(0, stdout=f"disabled services = {{\n\t{line}\n}}\n"))
    assert scheduling.agent_switched_off() is off


def test_the_switch_is_read_from_the_fake_launchd_too(a_mac):
    assert scheduling.agent_switched_off() is False
    a_mac.launchd.switched_off = True
    assert scheduling.agent_switched_off() is True
    assert a_mac.launchd.calls[-1] == ["launchctl", "print-disabled", scheduling._domain()]
    a_mac.launchd.refuse["print-disabled"] = (1, "Unrecognized")
    with pytest.raises(RuntimeError, match="could not list the switched-off items"):
        scheduling.agent_switched_off()


def test_the_first_pass_is_started_with_launchctl_kickstart(a_mac, tmp_path):
    with pytest.raises(RuntimeError, match="could not start the first pass"):
        scheduling.start_agent_now()                  # nothing loaded: kickstart says so
    scheduling.register_here(tmp_path)
    a_mac.launchd.calls.clear()
    assert scheduling.start_agent_now() == ["launchctl", "kickstart",
                                            scheduling._service()]
    assert a_mac.launchd.verbs() == ["kickstart"]


def test_a_mac_names_its_designation_as_a_windows_computer_does(a_mac, tmp_path, monkeypatch, short_root):
    """R25: the first Mac to register claims the schedule by ``locking.this_host``; the Mac
    the file names registers; any other does not. Nothing about the file changes on a Mac."""
    from tests.conftest import make_engagement
    from tracker.layout import designation_file
    from tracker.locking import this_host
    from tracker.templates import template_items

    make_engagement(short_root, template_items("1040", core_only=True))
    monkeypatch.setattr(platform, "node", lambda: "Office-Mac.local")
    decision = scheduling.schedule_decision(short_root)
    assert decision.outcome == scheduling.CLAIMED and decision.host == this_host()
    scheduling.claim(short_root)
    assert designation_file(short_root).read_text(encoding="utf-8") == f"{this_host()}\n"
    assert scheduling.schedule_decision(short_root).outcome == scheduling.REGISTERED
    designation_file(short_root).write_text("front-desk-mac\n", encoding="utf-8")
    other = scheduling.schedule_decision(short_root)
    assert other.outcome == scheduling.ELSEWHERE and other.host == "front-desk-mac"
    with pytest.raises(scheduling.DesignationError, match="front-desk-mac claimed the schedule"):
        scheduling.claim(short_root)
    moved = scheduling.move_here(short_root)
    assert moved.before == "front-desk-mac"
    assert scheduling.schedule_decision(short_root).outcome == scheduling.REGISTERED
