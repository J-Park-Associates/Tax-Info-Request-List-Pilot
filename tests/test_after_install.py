"""Tests for tracker/after_install.py - every one-time step, run by the install (decision 209).

Every root here is fabricated (``short_root``), the settings and the store
are this test's own, and ``schtasks`` is a fake: the suite's autouse guard
fails any test that reaches the real one. The computer's name is faked by
``platform.node`` - the one place ``locking.this_host`` reads it - so the
designation is judged exactly as it is on the office computer.
"""

from __future__ import annotations

import json
import platform
import runpy
import sys
import time
import warnings

import pytest

from tests.conftest import TEST_HOUSEHOLD, make_engagement
from tracker import after_install, ledger, scheduling, store
from tracker.layout import designation_file
from tracker.locking import engagement_lock
from tracker.records import rule_to_json
from tracker.settings import ENV_SETTINGS_DIR, set_clients_root, settings_dir
from tracker.templates import template_items

HERE = "office-pc"
ELSEWHERE = "front-desk"
#: What the step prints in any sentence, which must never carry a traceback.
TRACEBACK = "Traceback"


class Said:
    """What a faked ``schtasks`` answers."""

    def __init__(self, returncode=0, stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, "", stderr


@pytest.fixture
def windows(monkeypatch):
    """This computer is ``HERE``, has Task Scheduler, and its ``schtasks`` is
    a fake that keeps every command; a task of ours exists when ``has_task``
    is set on the returned list."""
    calls: list[list[str]] = []
    calls_state = {"exists": False}

    def answer(command):
        calls.append(command)
        if command[1] == "/query":
            return Said(0 if calls_state["exists"] else 1)
        return Said()

    monkeypatch.setattr(platform, "node", lambda: HERE.upper())
    monkeypatch.setattr(scheduling, "task_scheduler_here", lambda: True)
    monkeypatch.setattr(scheduling, "_schtasks", answer)
    calls_state["calls"] = calls
    return calls_state


@pytest.fixture
def app(tmp_path, monkeypatch):
    """This app's own settings folder, with no clients root yet."""
    folder = tmp_path / "app"
    folder.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(folder))
    return folder


@pytest.fixture
def root(app, short_root):
    """A clients root with one household and one return, saved in the app."""
    make_engagement(short_root, template_items("1040", core_only=True), household=TEST_HOUSEHOLD)
    set_clients_root(short_root)
    return short_root


def creates(calls):
    return [command for command in calls if command[1] == "/create"]


def cli(monkeypatch, capsys, *argv) -> tuple[int, str]:
    """``python -m tracker.after_install`` in this process, so the fakes hold."""
    monkeypatch.setattr(sys, "argv", ["tracker.after_install", *argv])
    with pytest.raises(SystemExit) as ended, warnings.catch_warnings():
        # The module is already imported (the fakes are set on its imports);
        # runpy says so, and running it again as __main__ is the point.
        warnings.filterwarnings("ignore", message="'tracker.after_install' found in sys.modules",
                                category=RuntimeWarning)
        runpy.run_module("tracker.after_install", run_name="__main__", alter_sys=False)
    return ended.value.code, capsys.readouterr().out


# ------------------------------------------------------------ the schedule ----


def test_setup_registers_the_schedule_on_the_designated_computer(root, windows, monkeypatch, capsys):
    designation_file(root).write_text(f"{HERE}\n", encoding="utf-8")

    code, out = cli(monkeypatch, capsys, "--reason", "setup")

    assert code == 0, out
    said = scheduling.SCHEDULE_REGISTERED.format(start=scheduling.DEFAULT_START,
                                                every=scheduling.DEFAULT_REPEAT_MINUTES)
    assert out.splitlines()[0] == said
    assert len(creates(windows["calls"])) == 1
    assert scheduling.schedule_xml_path(settings_dir()).is_file()
    assert json.loads(after_install.record_path().read_text(encoding="utf-8"))["reason"] == "setup"


def test_the_first_computer_to_register_claims_the_schedule(root, windows):
    assert not designation_file(root).exists()

    done = after_install.run(reason=after_install.REASON_ROOT)

    assert done.schedule == scheduling.CLAIMED and done.exit_code == 0 and done.installed
    assert done.schedule_sentence == scheduling.SCHEDULE_CLAIMED.format(
        host=HERE, start=scheduling.DEFAULT_START, every=scheduling.DEFAULT_REPEAT_MINUTES)
    assert designation_file(root).read_text(encoding="utf-8") == f"{HERE}\n"
    assert len(creates(windows["calls"])) == 1


def test_another_computer_registers_nothing_and_removes_its_own_task(root, windows):
    designation_file(root).write_text(f"{ELSEWHERE}\n", encoding="utf-8")
    windows["exists"] = True

    done = after_install.run(reason=after_install.REASON_LAUNCH)

    assert done.schedule == scheduling.ELSEWHERE and done.exit_code == 0 and not done.installed
    assert done.schedule_sentence == scheduling.SCHEDULE_ELSEWHERE.format(
        host=ELSEWHERE, removed=scheduling.SCHEDULE_REMOVED)
    assert creates(windows["calls"]) == []
    assert ["schtasks", "/delete", "/tn", scheduling.TASK_NAME, "/f"] in windows["calls"]
    assert designation_file(root).read_text(encoding="utf-8") == f"{ELSEWHERE}\n"

    # No task of its own: nothing deleted, and the sentence does not say so.
    windows["exists"] = False
    windows["calls"].clear()
    again = after_install.run(reason=after_install.REASON_LAUNCH)
    assert again.schedule_sentence == scheduling.SCHEDULE_ELSEWHERE.format(host=ELSEWHERE, removed="")
    assert [command[1] for command in windows["calls"]] == ["/query"]


def test_no_root_means_the_schedule_waits_for_the_folder(app, windows, monkeypatch, capsys):
    code, out = cli(monkeypatch, capsys, "--reason", "setup")

    assert code == 0, out
    assert out.splitlines() == [scheduling.SCHEDULE_WAITS_FOR_ROOT, after_install.CHECK_SKIPPED_NO_ROOT]
    assert windows["calls"] == []


def test_a_computer_with_no_task_scheduler_registers_nothing(root, monkeypatch):
    done = after_install.run(reason=after_install.REASON_SETUP)

    assert done.schedule == scheduling.NO_TASK_SCHEDULER and done.exit_code == 0
    assert done.schedule_sentence == scheduling.SCHEDULE_NOT_HERE
    assert not designation_file(root).exists()      # a desk without Task Scheduler never claims


def test_an_unreadable_designation_changes_no_schedule(root, windows, monkeypatch, capsys):
    designation_file(root).write_text("front-desk\nsecret-laptop\n", encoding="utf-8")

    code, out = cli(monkeypatch, capsys, "--reason", "setup")

    assert code == 1
    sentence = scheduling.DESIGNATION_UNREADABLE.format(file=designation_file(root))
    assert out.splitlines()[0] == sentence
    assert "secret-laptop" not in out and "front-desk" not in out and TRACEBACK not in out
    assert windows["calls"] == []
    record = json.loads(after_install.record_path().read_text(encoding="utf-8"))
    assert record["program"] == "" and record["failed"] == [sentence]


def test_move_schedule_here_rewrites_the_designation(root, windows, monkeypatch, capsys):
    designation_file(root).write_text(f"{ELSEWHERE}\n", encoding="utf-8")

    code, out = cli(monkeypatch, capsys, "--move-schedule-here")

    assert code == 0, out
    lines = out.splitlines()
    assert lines[0] == scheduling.MOVED_FROM.format(host=ELSEWHERE, here=HERE)
    assert lines[1] == scheduling.SCHEDULE_REGISTERED.format(
        start=scheduling.DEFAULT_START, every=scheduling.DEFAULT_REPEAT_MINUTES)
    assert designation_file(root).read_text(encoding="utf-8") == f"{HERE}\n"
    assert len(creates(windows["calls"])) == 1


# -------------------------------------------------------- the record check ----


def test_no_store_means_the_check_waits_for_the_first_pass(root):
    store.close()
    for side in ("", "-wal", "-shm"):     # the return's making built one; a fresh machine has none
        store.store_path().with_name(store.store_path().name + side).unlink(missing_ok=True)
    assert not store.store_path().exists()

    done = after_install.run(reason=after_install.REASON_SETUP)

    assert done.check == after_install.CHECK_NO_STORE_KEY and done.exit_code == 0
    assert done.check_sentence == after_install.CHECK_SKIPPED_NO_STORE
    assert not store.store_path().exists()          # the step never creates a store


def test_a_clean_record_is_said_to_be_clean(root):
    conn = store.connect()
    store.rebuild_engagement(conn, root, next(iter(_returns(root))))

    done = after_install.run(reason=after_install.REASON_SETUP)

    assert done.check == after_install.CHECK_CLEAN_KEY and done.findings == ()
    assert after_install.notice() is None


def _returns(root):
    from tracker.registry import engagement_dirs

    return engagement_dirs(root)


@pytest.fixture
def malformed(root, monkeypatch):
    """The return, with a line an earlier version applied that decision
    187's admission now refuses: a Date Pattern that could run away. The
    record is removed when the test ends, as the store's own tests do, so
    the suite's agreement check does not rebuild from it."""
    [engagement] = _returns(root)
    conn = store.connect()
    store.rebuild_engagement(conn, root, engagement)
    rule = {**rule_to_json(template_items("1040", core_only=True)[0]), "date_pattern": r"(\d+)+x"}
    patch = pytest.MonkeyPatch()
    patch.setattr(store, "_refuse_a_malformed_line", lambda *args, **kwargs: None)
    try:
        with engagement_lock(engagement):
            store.record(conn, engagement, ledger.new(ledger.RULES_CHANGED, rules=[rule]))
    finally:
        patch.undo()
    yield engagement
    store.close()
    ledger.path_for(engagement).unlink(missing_ok=True)


def test_a_finding_is_not_a_failure(malformed, monkeypatch, capsys):
    code, out = cli(monkeypatch, capsys, "--reason", "setup")

    assert code == 0, out
    record = json.loads(after_install.record_path().read_text(encoding="utf-8"))
    assert len(record["findings"]) == 1 and "is malformed" in record["findings"][0]
    assert record["failed"] == [] and record["program"] == after_install.program_identity()
    assert after_install.CHECK_FOUND.format(n=1) in out and after_install.FINDINGS_WAIT in out
    assert out.rstrip().splitlines()[-1] == after_install.FINDINGS_WAIT


def test_a_store_that_cannot_open_is_a_failure(root, monkeypatch, capsys):
    store.close()
    for side in ("-wal", "-shm"):
        store.store_path().with_name(store.store_path().name + side).unlink(missing_ok=True)
    store.store_path().write_bytes(b"this is not a database, and never was one" * 100)

    code, out = cli(monkeypatch, capsys, "--reason", "setup")

    assert code == 1
    [check] = [line for line in out.splitlines() if line.startswith("The record check could not run")]
    assert check.endswith(after_install.CHECK_FAILED.split("{problem}")[1])
    assert TRACEBACK not in out
    assert json.loads(after_install.record_path().read_text(encoding="utf-8"))["program"] == ""


# ------------------------------------------------ idempotence and the doors ----


def test_running_it_twice_is_the_same_as_once(root, windows):
    first = after_install.run(reason=after_install.REASON_SETUP)
    written = json.loads(after_install.record_path().read_text(encoding="utf-8"))
    second = after_install.run(reason=after_install.REASON_SETUP)
    again = json.loads(after_install.record_path().read_text(encoding="utf-8"))

    assert first.schedule == scheduling.CLAIMED and second.schedule == scheduling.REGISTERED
    assert first.exit_code == second.exit_code == 0
    assert (first.check, first.findings, first.failed) == (second.check, second.findings, second.failed)
    assert {k: v for k, v in written.items() if k != "ran_at"} == {
        k: v for k, v in again.items() if k != "ran_at"} | {"schedule": scheduling.CLAIMED}
    assert designation_file(root).read_text(encoding="utf-8") == f"{HERE}\n"
    assert creates(windows["calls"])[0] == creates(windows["calls"])[1]


def test_a_failed_run_is_tried_again_at_the_next_launch(root, windows):
    designation_file(root).write_text("not one name at all", encoding="utf-8")
    assert after_install.run(reason=after_install.REASON_SETUP).exit_code == 1

    assert after_install.launch() is not None       # the identity was not recorded
    designation_file(root).write_text(f"{HERE}\n", encoding="utf-8")
    fixed = after_install.launch()
    assert fixed is not None and fixed.exit_code == 0 and fixed.installed
    assert after_install.launch() is None


def test_the_launch_door_does_nothing_when_the_program_is_unchanged(root, windows, monkeypatch):
    assert after_install.run(reason=after_install.REASON_SETUP).exit_code == 0

    def refused(*args, **kwargs):
        raise AssertionError("the launch door reached past the identity")

    monkeypatch.setattr(scheduling, "_schtasks", refused)
    monkeypatch.setattr(store, "connect", refused)
    began = time.perf_counter()
    assert after_install.launch() is None
    took = time.perf_counter() - began
    assert took < 0.25, f"the no-op launch took {took:.3f} s"


def test_a_changed_program_runs_the_step_at_launch(root, tmp_path, monkeypatch):
    # From source: a record from another program runs it.
    assert after_install.run(reason=after_install.REASON_SETUP).exit_code == 0
    assert after_install.launch() is None
    record = json.loads(after_install.record_path().read_text(encoding="utf-8"))
    after_install.record_path().write_text(json.dumps({**record, "program": "0" * 64}), encoding="utf-8")
    ran = after_install.launch()
    assert ran is not None and ran.reason == after_install.REASON_LAUNCH
    assert after_install.launch() is None

    # Frozen: the build's own note, which Build App.bat writes at the top of
    # the package, is the program; a new build is a new program.
    package = tmp_path / "package"
    exe = package / "resources" / "api" / "api.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    info = package / after_install.BUILD_INFO_FILENAME
    info.write_text("commit aaaa\n", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert after_install.build_info(exe) == info
    assert after_install.launch() is not None
    assert after_install.launch() is None
    info.write_text("commit bbbb\n", encoding="utf-8")
    assert after_install.launch() is not None
    assert after_install.launch() is None


@pytest.mark.xfail(strict=True, reason=(
    "BUILD-209's probe (SPEC-209 R3): a line an earlier version applied that decision 187 now "
    "refuses is named by the record check, but the pass does not stop its household - it is "
    "processed as normal and the app shows no waiting sentence for it. Reported, not patched here."))
def test_a_household_whose_applied_line_the_rule_refuses_waits_in_the_app(malformed, capsys):
    """R3: the check names the household at the end of Setup and in the
    app's notice; the household itself waits because decision 187 makes it
    wait - which this proves after a pass, on a fabricated root."""
    from tracker import api, runner

    runner.main([runner.SETTINGS_FLAG, str(settings_dir()), "--reminders", "never"])
    capsys.readouterr()
    assert api.main(["list"]) == 0
    listed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    [household] = listed["households"]
    assert household["problem"], "the household is not waiting"
