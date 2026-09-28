"""Tests for tracker/after_install.py - every one-time step, run by the install (decision 209).

Every root here is fabricated (``short_root``), the settings and the store
are this test's own, and ``schtasks`` is a fake: the suite's autouse guard
fails any test that reaches the real one. The computer's name is faked by
``platform.node`` - the one place ``locking.this_host`` reads it - so the
designation is judged exactly as it is on the office computer.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

import pytest

from tests.conftest import TEST_HOUSEHOLD, make_engagement
from tracker import after_install, ledger, scheduling, settings, store
from tracker.layout import PRIVATE_TREE, designation_file
from tracker.locking import engagement_lock
from tracker.records import rule_to_json
from tracker.settings import ENV_SETTINGS_DIR, set_clients_root
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
    """``python -m tracker.after_install`` in this process: its ``main``,
    in the imported module, so the fakes and the fabricated checkout hold.
    Never ``runpy`` - a module run again as ``__main__`` has globals of its
    own, and cleared the real checkout's test cache (the re-review's MF1)."""
    code = after_install.main(list(argv))
    return code, capsys.readouterr().out


# ------------------------------------------------------------ the schedule ----


def test_setup_registers_the_schedule_on_the_designated_computer(root, windows, monkeypatch, capsys):
    designation_file(root).write_text(f"{HERE}\n", encoding="utf-8")

    code, out = cli(monkeypatch, capsys, "--reason", "setup")

    assert code == 0, out
    said = scheduling.SCHEDULE_REGISTERED.format(start=scheduling.DEFAULT_START,
                                                every=scheduling.DEFAULT_REPEAT_MINUTES)
    assert out.splitlines()[0] == said
    assert len(creates(windows["calls"])) == 1
    assert scheduling.schedule_xml_path().is_file()
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


def test_a_removable_drive_is_still_refused(root, windows, monkeypatch):
    """Decision 186 inside 209 (SPEC-209 section 9): the schedule runs
    whatever program sits where the app is, so a program on a stick is the
    step's first answer - ``refused_drive``, in 186's own sentence, a
    failure - asked before the designation, so nothing is claimed, no task
    file is written and no task is registered, from every door."""
    from tracker import settings as settings_module

    program = settings_module.app_dir()
    monkeypatch.setattr(settings_module, "drive_type",
                        lambda path: settings_module.DRIVE_REMOVABLE if Path(path) == program
                        else settings_module.DRIVE_FIXED)
    said = settings_module.PROGRAM_ON_REMOVABLE.format(folder=program)
    for reason in (after_install.REASON_SETUP, after_install.REASON_REPAIR, after_install.REASON_ROOT):
        done = after_install.run(reason=reason)
        assert done.schedule == scheduling.REFUSED_DRIVE and done.schedule_sentence == said
        assert said in done.failed and done.exit_code == 1 and not done.installed
    assert windows["calls"] == []
    assert not designation_file(root).exists()
    assert not scheduling.schedule_xml_path().exists()


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
    row is left as a version-17 store left every row - judged by no
    admission this version knows (``admitted_by`` 0) - which is what an
    upgrade finds. The record is removed when the test ends, as the store's
    own tests do, so the suite's agreement check does not rebuild from it."""
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
    conn.execute("UPDATE engagements SET admitted_by = 0")
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


def test_a_household_whose_applied_line_the_rule_refuses_waits_in_the_app(malformed, capsys):
    """R3 and R3b: the check names the household at the end of Setup and in
    the app's notice; the household itself waits because the store judges
    every applied line again under today's admission (decision 209, R3b) -
    which this proves after a pass, on a fabricated root. It was a strict
    xfail until R3b: :data:`FINDINGS_WAIT` claims it."""
    [finding] = after_install.run(reason=after_install.REASON_SETUP).findings
    assert "is malformed" in finding
    _waits(malformed, capsys, "line 2 of the record is malformed")


def _waits(engagement, capsys, sentence):
    """The household waits where 187 makes a new malformed line wait: the
    pass sorts nothing of the return and says ``sentence`` for it, the app's
    walk lists the return with it, and the return's page answers it - and
    it goes on waiting at the next pass."""
    from tracker import api, runner
    from tracker.registry import discover_engagements

    root = engagement.parents[3]
    for _ in range(2):
        report = runner.run_registry(discover_engagements(root), reminders="never")
        [one] = report.runs
        assert sentence in one.error and one.engagement.problem
    [listed] = discover_engagements(root).engagements
    assert sentence in listed.problem
    capsys.readouterr()
    assert api.main(["state", api.ENGAGEMENT_FLAG, str(engagement)]) == 1
    assert sentence in json.loads(capsys.readouterr().out.strip().splitlines()[-1])["error"]


def test_a_household_whose_record_changed_behind_the_trackers_back_waits_in_the_app(root, capsys):
    """The other kind :data:`FINDINGS_WAIT` claims (decision 137): the store
    kept a fingerprint of the lines it applied, the record no longer chains
    to it, and the same sync that refuses a malformed line refuses this."""
    [engagement] = _returns(root)
    conn = store.connect()
    store.rebuild_engagement(conn, root, engagement)
    # What a record rewritten to its own length leaves, seen from the store:
    # neither the head nor the chain it kept is the record's any more.
    conn.execute("UPDATE engagements SET applied_digest = ?, ledger_head = ? WHERE path LIKE ?",
                 ("0" * 64, "0" * 64, f"{PRIVATE_TREE}/%/%"))

    [finding] = after_install.run(reason=after_install.REASON_SETUP).findings

    assert "changed behind the tracker's back" in finding
    _waits(engagement, capsys, "changed behind the tracker's back")
    store.rebuild_engagement(store.connect(), root, engagement)     # put back for the agreement check


# ------------------------------------------------ the review's fixes (209) ----


def test_a_move_elsewhere_removes_this_computers_task_at_its_next_start(root, windows):
    """The review's M1: after the schedule moves to another computer nothing
    about this one's program changed, yet its next start removes its own
    task - the designation no longer names what its record says it named -
    so two computers never both run the pass until the next upgrade."""
    assert after_install.run(reason=after_install.REASON_SETUP).schedule == scheduling.CLAIMED
    assert after_install.launch() is None                 # nothing changed: nothing to do
    windows["exists"] = True
    windows["calls"].clear()

    designation_file(root).write_text(f"{ELSEWHERE}\n", encoding="utf-8")   # moved on the new one
    moved = after_install.launch()

    assert moved is not None and moved.schedule == scheduling.ELSEWHERE
    assert ["schtasks", "/delete", "/tn", scheduling.TASK_NAME, "/f"] in windows["calls"]
    assert after_install.launch() is None                 # and once is enough


def test_a_failed_job_file_is_not_said_to_be_an_unwritten_designation(root, windows, monkeypatch):
    """The review's S2: only the claim writes the designation file, so only
    its failure says that file could not be written. A job file that could
    not be written after a claim that was, or a ``schtasks`` that cannot be
    started, is the schedule's failure, in a constant sentence."""
    def unwritable(*args, **kwargs):
        raise PermissionError("the settings folder is read-only")

    monkeypatch.setattr(scheduling, "register_here", unwritable)
    done = after_install.run(reason=after_install.REASON_SETUP)
    said = after_install.SCHEDULE_FAILED.format(problem=after_install.SCHEDULE_UNREACHABLE)
    assert done.failed == (said,) and done.schedule_sentence == said
    assert designation_file(root).read_text(encoding="utf-8") == f"{HERE}\n"     # it was written
    assert "read-only" not in " ".join(done.lines)

    designation_file(root).write_text(f"{ELSEWHERE}\n", encoding="utf-8")
    windows["exists"] = True

    def missing(command):
        raise FileNotFoundError("schtasks")

    monkeypatch.setattr(scheduling, "_schtasks", missing)
    assert after_install.run(reason=after_install.REASON_LAUNCH).failed == (said,)


def test_a_claim_that_cannot_write_says_the_designation_was_not_written(root, windows, monkeypatch):
    real_open = os.open

    def refused(path, *args, **kwargs):
        if str(path) == str(designation_file(root)):
            raise PermissionError("no")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", refused)
    done = after_install.run(reason=after_install.REASON_SETUP)
    assert done.failed == (after_install.DESIGNATION_UNWRITABLE.format(file=designation_file(root)),)
    assert creates(windows["calls"]) == []


@pytest.mark.parametrize("name", ["Büro-PC", "office pc", ""])
def test_a_computer_whose_name_the_file_cannot_hold_is_said_whole(root, windows, monkeypatch, name):
    """The review's S3: a computer's own name the designation cannot hold
    is asked before the file is read, and said in one whole sentence -
    never a fragment, and never as a file that could not be read."""
    monkeypatch.setattr(platform, "node", lambda: name)

    done = after_install.run(reason=after_install.REASON_SETUP)

    sentence = scheduling.HOST_UNNAMED.format(file=designation_file(root))
    assert done.schedule == scheduling.UNNAMED_HOST and done.failed == (sentence,)
    assert not designation_file(root).exists() and windows["calls"] == []


def test_the_designation_asks_is_this_host(root, windows):
    """Every comparison of the designated computer with this one is 159's
    ``locking.is_this_host``: a name written by hand in capitals, or with a
    space after it, is this computer."""
    designation_file(root).write_text("OFFICE-PC \n", encoding="utf-8")

    done = after_install.run(reason=after_install.REASON_SETUP)

    assert done.schedule == scheduling.REGISTERED and done.installed
    scheduling.claim(root)                   # a claim over it is no race lost
    assert designation_file(root).read_text(encoding="utf-8") == "OFFICE-PC \n"


def test_two_claims_on_one_disk_create_the_file_once(root, windows, monkeypatch):
    """The review's N3: the claim creates the file exclusively, so a claim
    that arrives after another made it is answered by what that one wrote."""
    real_open = os.open

    def another_computer_first(path, flags, *args, **kwargs):
        if str(path) == str(designation_file(root)) and flags & os.O_EXCL:
            designation_file(root).write_text(f"{ELSEWHERE}\n", encoding="utf-8")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", another_computer_first)
    with pytest.raises(scheduling.DesignationError) as lost:
        scheduling.claim(root)
    assert str(lost.value) == scheduling.CLAIM_TAKEN.format(host=ELSEWHERE)
    assert designation_file(root).read_text(encoding="utf-8") == f"{ELSEWHERE}\n"


def test_a_move_over_an_unreadable_file_says_so(root, windows, monkeypatch, capsys):
    """The review's N4: a move over a file that named no computer it could
    read says that, not that no computer ran the schedule."""
    designation_file(root).write_text("not one name at all", encoding="utf-8")

    code, out = cli(monkeypatch, capsys, "--move-schedule-here")

    assert code == 0, out
    assert out.splitlines()[0] == scheduling.MOVED_FROM_UNREADABLE.format(here=HERE)
    assert "not one name" not in out


def test_a_store_holding_no_record_is_not_said_to_be_clean(root):
    """The review's N2: a store that holds no record yet - fresh, or set
    aside by an upgrade - had nothing judged, and says so; a clean check
    says how many records it judged."""
    store.close()
    for side in ("", "-wal", "-shm"):
        store.store_path().with_name(store.store_path().name + side).unlink(missing_ok=True)
    store.connect()                                  # there, and holding nothing

    empty = after_install.run(reason=after_install.REASON_SETUP)
    assert empty.check == after_install.CHECK_NOTHING_HELD_KEY
    assert empty.check_sentence == after_install.CHECK_NOTHING_HELD

    for one in _returns(root):
        store.catch_up(store.connect(), root, one)
    judged = after_install.run(reason=after_install.REASON_SETUP)
    assert judged.check == after_install.CHECK_CLEAN_KEY
    assert judged.check_sentence == after_install.CHECK_CLEAN.format(n=1)


# ------------------------------------------------- the test cache (R8) ----


@pytest.fixture
def checkout(tmp_path):
    """A fabricated checkout folder - never this checkout's own cache."""
    folder = tmp_path / "checkout"
    (folder / "tracker").mkdir(parents=True)
    return folder


def test_setup_clears_the_checkouts_test_cache(app, checkout):
    cache = checkout / after_install.TEST_CACHE_DIRNAME
    (cache / "v" / "cache").mkdir(parents=True)
    (cache / "v" / "cache" / "nodeids").write_text('["tests/test_x.py::test_a_client_name"]',
                                                   encoding="utf-8")
    (cache / "README.md").write_text("pytest cache", encoding="utf-8")

    done = after_install.run(reason=after_install.REASON_SETUP, checkout=checkout)

    assert not cache.exists() and (checkout / "tracker").is_dir()
    assert done.cache_sentence == after_install.CACHE_CLEARED and done.exit_code == 0
    assert after_install.CACHE_CLEARED in done.lines
    again = after_install.run(reason=after_install.REASON_SETUP, checkout=checkout)
    assert again.cache_sentence == "" and after_install.CACHE_CLEARED not in again.lines


def test_a_missing_test_cache_is_nothing_to_do(app, checkout):
    done = after_install.run(reason=after_install.REASON_SETUP, checkout=checkout)

    assert done.cache_sentence == "" and done.exit_code == 0
    assert not any("pytest_cache" in line for line in done.lines)


def _link_or_skip(link, target):
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"this machine cannot make a symbolic link ({type(exc).__name__})")


def test_a_link_in_the_test_cache_is_removed_not_followed(app, checkout, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("not the cache's", encoding="utf-8")
    cache = checkout / after_install.TEST_CACHE_DIRNAME
    cache.mkdir()
    _link_or_skip(cache / "linked", outside)

    done = after_install.run(reason=after_install.REASON_SETUP, checkout=checkout)

    assert not cache.exists() and done.cache_sentence == after_install.CACHE_CLEARED
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "not the cache's"


def test_a_linked_test_cache_removes_only_the_link(app, checkout, tmp_path):
    outside = tmp_path / "elsewhere-cache"
    (outside / "v").mkdir(parents=True)
    (outside / "v" / "keep.txt").write_text("not the checkout's", encoding="utf-8")
    cache = checkout / after_install.TEST_CACHE_DIRNAME
    _link_or_skip(cache, outside)

    done = after_install.run(reason=after_install.REASON_SETUP, checkout=checkout)

    assert not os.path.lexists(cache) and done.cache_sentence == after_install.CACHE_CLEARED
    assert (outside / "v" / "keep.txt").read_text(encoding="utf-8") == "not the checkout's"


def test_the_packaged_app_has_no_checkout_to_clear(app, checkout, monkeypatch):
    cache = checkout / after_install.TEST_CACHE_DIRNAME
    cache.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    done = after_install.run(reason=after_install.REASON_SETUP, checkout=checkout)

    assert cache.is_dir() and done.cache_sentence == ""


def test_a_test_cache_that_cannot_be_removed_is_a_failure(app, checkout, monkeypatch):
    cache = checkout / after_install.TEST_CACHE_DIRNAME
    cache.mkdir()
    (cache / "held.txt").write_text("", encoding="utf-8")

    def held(path):
        raise PermissionError("in use by another process")

    monkeypatch.setattr(os, "unlink", held)
    done = after_install.run(reason=after_install.REASON_SETUP, checkout=checkout)

    assert done.failed == (after_install.CACHE_NOT_CLEARED,) and done.exit_code == 1
    assert done.program == "" and "in use" not in " ".join(done.lines)


def test_no_test_reaches_the_real_checkouts_test_cache(app, tmp_path, monkeypatch, capsys):
    """The re-review's MF1: the command line runs in the imported module, so
    the suite's fabricated checkout holds for it too. A marker in a
    fabricated stand-in is the only thing removed; the real checkout's
    cache, whatever it holds, is left exactly as it was - nothing real is
    made or deleted here."""
    real = Path(after_install.__file__).resolve().parent.parent
    assert after_install.CHECKOUT != real            # the suite's own guard (tests/conftest.py)
    real_cache = real / after_install.TEST_CACHE_DIRNAME
    before = sorted(os.listdir(real_cache)) if real_cache.is_dir() else None

    stand_in = tmp_path / "stand-in"
    (stand_in / after_install.TEST_CACHE_DIRNAME / "marker").mkdir(parents=True)
    monkeypatch.setattr(after_install, "CHECKOUT", stand_in)
    code, out = cli(monkeypatch, capsys, "--reason", "setup")

    assert code == 0, out
    assert after_install.CACHE_CLEARED in out
    assert not (stand_in / after_install.TEST_CACHE_DIRNAME).exists()
    assert (sorted(os.listdir(real_cache)) if real_cache.is_dir() else None) == before


def test_a_reparse_folder_that_is_no_link_is_walked_as_a_folder(app, checkout, monkeypatch):
    """The re-review's SF3: only a symbolic link or a junction is a link. A
    folder carrying some other reparse tag (a cloud placeholder) is cleared
    as the folder it is, not refused as a link that will not unlink."""
    import stat as _stat

    cache = checkout / after_install.TEST_CACHE_DIRNAME
    (cache / "v").mkdir(parents=True)
    (cache / "v" / "nodeids").write_text("[]", encoding="utf-8")
    real_lstat = os.lstat

    class Placeholder:
        """What lstat says of a cloud placeholder folder: a folder, with a
        reparse tag that is not a link's."""

        def __init__(self, status):
            self.st_mode = status.st_mode
            self.st_reparse_tag = 0x9000001A          # a cloud-files tag
            self.st_file_attributes = getattr(_stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

    monkeypatch.setattr(os, "lstat", lambda path, *a, **k: Placeholder(real_lstat(path, *a, **k))
                        if os.path.basename(path) == "v" else real_lstat(path, *a, **k))
    done = after_install.run(reason=after_install.REASON_SETUP, checkout=checkout)

    assert done.failed == () and not cache.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="a junction is a Windows link; mklink /J exists only there")
def test_a_junction_in_the_test_cache_is_removed_not_followed(app, checkout, tmp_path):
    """The re-review's SF3, on a real junction (``mklink /J``): the junction
    goes, and the folder it pointed at keeps every file."""
    import subprocess

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("not the cache's", encoding="utf-8")
    cache = checkout / after_install.TEST_CACHE_DIRNAME
    cache.mkdir()
    made = subprocess.run(["cmd", "/c", "mklink", "/J", str(cache / "joined"), str(outside)],
                          capture_output=True, text=True)
    if made.returncode != 0:
        pytest.skip(f"this machine could not make a junction ({made.returncode})")

    done = after_install.run(reason=after_install.REASON_SETUP, checkout=checkout)

    assert done.failed == () and not cache.exists()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "not the cache's"


def test_setup_moves_what_186_lists_to_move_and_nothing_it_lists_to_delete(app, monkeypatch, capsys):
    """R9 wired: the step's first job moves decision 186's move group - the
    record checkpoint, its journal and ``recovered/``, as
    ``runner.left_behind_to_move`` lists them - from beside a fabricated
    program folder into the folder the store lives in (the suite's data
    home), and leaves 186's delete group - an old store, last-pass and
    after-install notes - exactly where it was, for a person to delete."""
    from tracker import runner, store
    from tracker.settings import data_home

    monkeypatch.setenv(store.ENV_STORE, str(data_home() / store.STORE_FILENAME))
    store.close()
    beside = app.resolve()
    moving = left_behind(beside)
    deleting = {store.STORE_FILENAME: b"an old store", runner.LAST_PASS_FILENAME: b"{}",
                runner.AFTER_INSTALL_FILENAME: b"{}"}
    for name, data in deleting.items():
        (beside / name).write_bytes(data)
    assert sorted(runner.left_behind_to_move(None)) == sorted(moving)
    home = store.store_path().parent
    assert home == data_home() and home != beside

    code, out = cli(monkeypatch, capsys, "--reason", "setup")

    assert code == 0, out
    assert after_install.LEFT_BEHIND_MOVED.format(home=home) in out.splitlines()
    assert not any(os.path.lexists(item) for item in moving)
    assert (home / CHECKPOINT).read_bytes() == b"checkpoint\x00heads"
    assert (home / JOURNAL).read_bytes() == b"journal"
    assert (home / "recovered" / "Household A" / "record.json").is_file()
    for name, data in deleting.items():                       # 186's delete group: untouched
        assert (beside / name).read_bytes() == data, name
    assert runner.left_behind_to_move(None) == []
    assert [code for code, _ in runner.left_behind_warnings(None)] == [runner.CODE_LEFT_BEHIND]
    assert after_install.record_path() == home / after_install.RECORD_FILENAME
    assert after_install.record_path().is_file()


# --- The careful mover (R9): decision 186's move group into the data home ---

CHECKPOINT = "record-heads.db"
JOURNAL = "record-heads.db-journal"


def left_behind(beside):
    """A fabricated checkpoint, its journal and ``recovered/`` beside a
    fabricated program folder, as an earlier version left them."""
    beside.mkdir(parents=True, exist_ok=True)
    (beside / CHECKPOINT).write_bytes(b"checkpoint\x00heads")
    (beside / JOURNAL).write_bytes(b"journal")
    (beside / "recovered" / "Household A").mkdir(parents=True)
    (beside / "recovered" / "Household A" / "record.json").write_text('{"fabricated": 1}', encoding="utf-8")
    return [beside / CHECKPOINT, beside / JOURNAL, beside / "recovered"]


def test_the_left_behind_checkpoint_moves_into_the_data_home(tmp_path):
    items = left_behind(tmp_path / "program")
    home = tmp_path / "data home"
    done = after_install.move_left_behind(items, home)
    assert done == after_install.MoveOutcome(
        moved=tuple(items), sentence=after_install.LEFT_BEHIND_MOVED.format(home=home))
    assert not any(os.path.lexists(item) for item in items)
    assert (home / CHECKPOINT).read_bytes() == b"checkpoint\x00heads"
    assert (home / JOURNAL).read_bytes() == b"journal"
    assert (home / "recovered" / "Household A" / "record.json").read_text(encoding="utf-8") == '{"fabricated": 1}'
    # Run again: what was moved is no longer left behind.
    assert after_install.move_left_behind(items, home) == after_install.MoveOutcome()


def test_a_taken_destination_moves_nothing_and_says_so(tmp_path):
    items = left_behind(tmp_path / "program")
    home = tmp_path / "data home"
    (home / "recovered").mkdir(parents=True)
    (home / "recovered" / "own.json").write_bytes(b"the data home's own")
    done = after_install.move_left_behind(items, home)
    assert done.failed and done.moved == ()
    assert done.sentence == after_install.LEFT_BEHIND_DESTINATION_TAKEN.format(name="recovered", home=home)
    assert all(os.path.lexists(item) for item in items)
    assert sorted(os.listdir(home)) == ["recovered"]
    assert (home / "recovered" / "own.json").read_bytes() == b"the data home's own"
    # A part of the checkpoint already in the home is the unit's refusal (MF1).
    (home / JOURNAL).write_bytes(b"the data home's own")
    done = after_install.move_left_behind(items, home)
    assert done.failed and done.sentence == after_install.LEFT_BEHIND_JOURNAL_ALONE.format(home=home)
    assert all(os.path.lexists(item) for item in items)


def test_a_lone_journal_never_moves_beside_another_checkpoint(tmp_path):
    """The merge review's MF1, probe 1: a rollback journal left beside the
    program without its checkpoint, while the data home holds a checkpoint
    of its own, would be replayed into that checkpoint at its next open. It
    moves nothing and fails in one sentence; the home is untouched."""
    beside, home = tmp_path / "program", tmp_path / "data home"
    beside.mkdir()
    home.mkdir()
    (beside / JOURNAL).write_bytes(b"an old journal")
    (home / CHECKPOINT).write_bytes(b"the home's own checkpoint")
    done = after_install.move_left_behind([beside / JOURNAL], home)
    assert done == after_install.MoveOutcome(
        sentence=after_install.LEFT_BEHIND_JOURNAL_ALONE.format(home=home), failed=True)
    assert (beside / JOURNAL).read_bytes() == b"an old journal"
    assert sorted(os.listdir(home)) == [CHECKPOINT]
    # With no checkpoint in the home either, a journal alone still moves nothing.
    (home / CHECKPOINT).unlink()
    assert after_install.move_left_behind([beside / JOURNAL], home).failed
    assert os.listdir(home) == []


def test_a_checkpoint_never_moves_beside_another_journal(tmp_path):
    """MF1, probe 2, the reverse: the checkpoint left behind while the data
    home holds a lone journal moves nothing - it would meet a journal that
    is not its own."""
    beside, home = tmp_path / "program", tmp_path / "data home"
    beside.mkdir()
    home.mkdir()
    (beside / CHECKPOINT).write_bytes(b"checkpoint\x00heads")
    (home / JOURNAL).write_bytes(b"a stranger's journal")
    done = after_install.move_left_behind([beside / CHECKPOINT], home)
    assert done == after_install.MoveOutcome(
        sentence=after_install.LEFT_BEHIND_JOURNAL_ALONE.format(home=home), failed=True)
    assert (beside / CHECKPOINT).read_bytes() == b"checkpoint\x00heads"
    assert sorted(os.listdir(home)) == [JOURNAL]


def test_move_schedule_here_from_a_removable_drive_changes_nothing(root, windows, monkeypatch, capsys):
    """The merge review's SF2: from a copy on a stick, ``--move-schedule-here``
    asks decision 186's refusal first - the designation still names the old
    computer, no task is registered, and the command says 186's sentence."""
    from tracker import settings as settings_module

    designation_file(root).write_text(f"{ELSEWHERE}\n", encoding="utf-8")
    program = settings_module.app_dir()
    monkeypatch.setattr(settings_module, "drive_type",
                        lambda path: settings_module.DRIVE_REMOVABLE if Path(path) == program
                        else settings_module.DRIVE_FIXED)
    code, out = cli(monkeypatch, capsys, "--move-schedule-here")
    assert code == 1
    assert out.splitlines()[0] == settings_module.PROGRAM_ON_REMOVABLE.format(folder=program)
    assert designation_file(root).read_text(encoding="utf-8") == f"{ELSEWHERE}\n"
    assert windows["calls"] == []


def test_an_os_error_in_the_record_check_is_said_by_class_and_kept_whole(root, monkeypatch, caplog):
    """The merge review's SF3: the check says an OSError by its class, never
    its words (they can spell a client's path), and keeps the whole of it
    on the local debug log (decision 190's ``errors.keep``)."""
    import errno
    import logging

    from tracker import errors, store

    secret = "C:/Clients/Jane Roe/SSN 123-45-6789"

    def refused(*args, **kwargs):
        raise PermissionError(errno.EACCES, "denied", secret)

    after_install.run(reason=after_install.REASON_SETUP)      # a store to check
    monkeypatch.setattr(store, "holds", refused)
    with caplog.at_level(logging.WARNING, logger=errors.DEBUG_LOGGER):
        done = after_install.run(reason=after_install.REASON_SETUP)
    assert done.findings and all(secret not in finding for finding in done.findings)
    assert any("PermissionError (EACCES)" in finding for finding in done.findings)
    assert secret not in "\n".join(done.lines)
    assert secret in caplog.text


def test_a_linked_left_behind_item_is_refused(tmp_path):
    beside = tmp_path / "program"
    items = left_behind(beside)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "keep.json").write_text("not the program's", encoding="utf-8")
    after_install._remove_tree(beside / "recovered")
    try:
        os.symlink(outside, beside / "recovered", target_is_directory=True)
    except OSError:
        pytest.skip("this computer cannot make a symbolic link")
    home = tmp_path / "data home"
    done = after_install.move_left_behind(items, home)
    assert done.failed and done.moved == ()
    assert done.sentence == after_install.LEFT_BEHIND_IS_LINK.format(name="recovered", home=home)
    assert all(os.path.lexists(item) for item in items) and not home.exists()
    assert (outside / "keep.json").read_text(encoding="utf-8") == "not the program's"


def test_nothing_left_behind_is_nothing_to_do(tmp_path):
    beside = tmp_path / "program"
    beside.mkdir()
    home = tmp_path / "data home"
    items = [beside / CHECKPOINT, beside / JOURNAL, beside / "recovered"]
    assert after_install.move_left_behind(items, home) == after_install.MoveOutcome()
    assert after_install.move_left_behind([], home) == after_install.MoveOutcome()
    assert not home.exists()


def test_a_copy_across_volumes_is_verified_before_the_source_goes(tmp_path, monkeypatch):
    beside = tmp_path / "program"
    items = left_behind(beside)
    try:
        os.symlink("Household A", beside / "recovered" / "linked", target_is_directory=True)
        linked = True
    except OSError:
        linked = False
    home = tmp_path / "data home"
    monkeypatch.setattr(after_install, "_same_volume", lambda source, folder: False)

    def no_rename(*args, **kwargs):
        raise AssertionError("a move across volumes must never rename")

    monkeypatch.setattr(os, "replace", no_rename)
    compared = []
    real_match = after_install._copies_match

    def watched(source, copy):
        compared.append((source.name, os.path.lexists(source)))
        return real_match(source, copy)

    monkeypatch.setattr(after_install, "_copies_match", watched)
    done = after_install.move_left_behind(items, home)
    assert not done.failed and done.moved == tuple(items)
    assert [name for name, _ in compared[:1]] == [CHECKPOINT]
    assert all(present for _, present in compared), "a source went before its copy was compared"
    assert not any(os.path.lexists(item) for item in items)
    assert (home / CHECKPOINT).read_bytes() == b"checkpoint\x00heads"
    assert (home / "recovered" / "Household A" / "record.json").read_text(encoding="utf-8") == '{"fabricated": 1}'
    if linked:
        assert os.path.islink(home / "recovered" / "linked")
        assert os.readlink(home / "recovered" / "linked") == "Household A"


def test_a_failed_copy_keeps_the_source_and_cleans_the_destination(tmp_path, monkeypatch):
    items = left_behind(tmp_path / "program")
    home = tmp_path / "data home"
    monkeypatch.setattr(after_install, "_same_volume", lambda source, folder: False)
    real_match = after_install._copies_match
    # The folder's copy comes out wrong; the two files before it copied cleanly.
    monkeypatch.setattr(after_install, "_copies_match",
                        lambda source, copy: not source.name.startswith("recovered") and real_match(source, copy))
    done = after_install.move_left_behind(items, home)
    assert done == after_install.MoveOutcome(
        sentence=after_install.LEFT_BEHIND_MOVE_FAILED.format(home=home), failed=True)
    assert TRACEBACK not in done.sentence
    assert items[0].read_bytes() == b"checkpoint\x00heads"
    assert items[1].read_bytes() == b"journal"
    assert (items[2] / "Household A" / "record.json").read_text(encoding="utf-8") == '{"fabricated": 1}'
    assert os.listdir(home) == []
    assert sorted(os.listdir(items[0].parent)) == [CHECKPOINT, JOURNAL, "recovered"]


def test_a_file_whose_source_cannot_be_removed_leaves_no_copy_behind(tmp_path, monkeypatch):
    """Review MF1 (probe P3): the journal's copy is verified but its source
    is locked. The copy goes, the source stays whole, the checkpoint moved
    before it comes back, and the next run simply moves everything."""
    items = left_behind(tmp_path / "program")
    home = tmp_path / "data home"
    monkeypatch.setattr(after_install, "_same_volume", lambda source, folder: False)
    real_unlink = after_install._unlink

    def locked(path):
        if path == items[1]:
            raise PermissionError(13, "locked")
        real_unlink(path)

    monkeypatch.setattr(after_install, "_unlink", locked)
    done = after_install.move_left_behind(items, home)
    assert done == after_install.MoveOutcome(
        sentence=after_install.LEFT_BEHIND_MOVE_FAILED.format(home=home), failed=True)
    assert items[0].read_bytes() == b"checkpoint\x00heads" and items[1].read_bytes() == b"journal"
    assert os.listdir(home) == []
    monkeypatch.setattr(after_install, "_unlink", real_unlink)
    assert after_install.move_left_behind(items, home).moved == tuple(items)
    assert (home / JOURNAL).read_bytes() == b"journal"


def test_a_copy_never_removes_a_destination_it_did_not_make(tmp_path, monkeypatch):
    """Review MF2 (probe P7): a destination that appeared after the first
    check - a folder or a file - is refused and left exactly as it was."""
    monkeypatch.setattr(after_install, "_same_volume", lambda source, folder: False)
    (tmp_path / "src" / "a").mkdir(parents=True)
    (tmp_path / "src.txt").write_text("ours", encoding="utf-8")
    there = tmp_path / "dst"
    (there / "src").mkdir(parents=True)
    (there / "src" / "theirs").write_text("keep", encoding="utf-8")
    (there / "src.txt").write_text("theirs", encoding="utf-8")
    for name in ("src", "src.txt"):
        with pytest.raises(OSError):
            after_install._move_one(tmp_path / name, there / name)
    assert (there / "src" / "theirs").read_text(encoding="utf-8") == "keep"
    assert (there / "src.txt").read_text(encoding="utf-8") == "theirs"
    assert (tmp_path / "src" / "a").is_dir() and (tmp_path / "src.txt").read_text(encoding="utf-8") == "ours"
    assert sorted(os.listdir(tmp_path)) == ["dst", "src", "src.txt"]


def test_nothing_is_ever_overwritten_forward_or_back(tmp_path, monkeypatch):
    """Review SF2 (probe P6): on one volume, an old pass writes a new
    checkpoint beside the program while the journal's move fails. The move
    back finds the name taken and leaves the moved checkpoint whole in the
    data home; the new one is untouched. A rename onto a taken name is
    refused."""
    items = left_behind(tmp_path / "program")
    home = tmp_path / "data home"
    real_rename = after_install._rename

    def racing(source, destination):
        if source == items[1]:
            items[0].write_bytes(b"new from an old pass")
            raise PermissionError(13, "locked")
        real_rename(source, destination)

    monkeypatch.setattr(after_install, "_rename", racing)
    done = after_install.move_left_behind(items, home)
    assert done.failed and done.moved == ()
    assert items[0].read_bytes() == b"new from an old pass"
    assert (home / CHECKPOINT).read_bytes() == b"checkpoint\x00heads"
    assert items[1].read_bytes() == b"journal"
    monkeypatch.setattr(after_install, "_rename", real_rename)
    with pytest.raises(OSError):
        after_install._rename(items[1], home / CHECKPOINT)
    assert items[1].read_bytes() == b"journal"
    assert (home / CHECKPOINT).read_bytes() == b"checkpoint\x00heads"


def test_a_folder_partly_removed_after_its_copy_is_said_so(tmp_path, monkeypatch):
    """Review SF1 (probe P4): the folder is renamed aside before it is
    copied, so when removing the old copy fails part way, the name 186
    lists is gone, the data home holds the whole verified copy, and the
    sentence names the leftover."""
    beside = tmp_path / "program"
    items = left_behind(beside)
    (beside / "recovered" / "Household A" / "second.json").write_text("{}", encoding="utf-8")
    home = tmp_path / "data home"
    monkeypatch.setattr(after_install, "_same_volume", lambda source, folder: False)
    real_unlink = after_install._unlink
    removed = []

    def partly(path):
        if ".moving-" in str(path) and path.suffix == ".json":
            removed.append(path)
            if len(removed) == 2:
                raise PermissionError(13, "locked")
        real_unlink(path)

    monkeypatch.setattr(after_install, "_unlink", partly)
    done = after_install.move_left_behind(items, home)
    aside = f"recovered.moving-{os.getpid()}"
    assert done == after_install.MoveOutcome(
        moved=tuple(items), failed=True,
        sentence=after_install.LEFT_BEHIND_PARTLY_REMOVED.format(home=home, name="recovered", aside=aside))
    assert sorted(os.listdir(home / "recovered" / "Household A")) == ["record.json", "second.json"]
    assert sorted(os.listdir(beside)) == [aside]
    monkeypatch.setattr(after_install, "_unlink", real_unlink)
    assert after_install.move_left_behind(items, home) == after_install.MoveOutcome()


def test_two_left_behind_items_of_one_name_move_nothing(tmp_path):
    """Review SF3 (probe P8): the second would land on the first."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "x").write_text("A", encoding="utf-8")
    (tmp_path / "b" / "x").write_text("B", encoding="utf-8")
    home = tmp_path / "data home"
    done = after_install.move_left_behind([tmp_path / "a" / "x", tmp_path / "b" / "x"], home)
    assert done == after_install.MoveOutcome(
        sentence=after_install.LEFT_BEHIND_MOVE_FAILED.format(home=home), failed=True)
    assert (tmp_path / "a" / "x").read_text(encoding="utf-8") == "A"
    assert (tmp_path / "b" / "x").read_text(encoding="utf-8") == "B"
    assert not home.exists()


# ------------------------------------------ the schedule setting (P21) ----


def registered_xml() -> str:
    return scheduling.schedule_xml_path().read_text(encoding=scheduling.SCHEDULE_XML_ENCODING)


def test_every_door_registers_the_saved_choice_not_the_defaults(root, windows, monkeypatch, capsys):
    settings.set_schedule(True, "06:30", 60)
    designation_file(root).write_text(f"{HERE}\n", encoding="utf-8")
    doors = [
        lambda: cli(monkeypatch, capsys, "--reason", "setup"),               # Setup.bat
        lambda: after_install.run(reason=after_install.REASON_ROOT),         # saving the root
        lambda: after_install.run(reason=after_install.REASON_REPAIR),       # Repair the schedule
        lambda: cli(monkeypatch, capsys, "--move-schedule-here"),            # Move schedule here
        lambda: after_install.run(reason=after_install.REASON_LAUNCH),       # the app's launch
    ]
    for door in doors:
        scheduling.schedule_xml_path().unlink(missing_ok=True)
        door()
        xml = registered_xml()
        assert "T06:30:00" in xml and "PT60M" in xml and "T07:00:00" not in xml and "PT120M" not in xml


def test_a_launch_registers_the_saved_choice(root, windows):
    settings.set_schedule(True, "05:45", 240)
    after_install.launch()
    assert "T05:45:00" in registered_xml() and "PT240M" in registered_xml()


def test_once_a_day_registers_no_repeat_and_says_every_day_at_the_start(root, windows):
    settings.set_schedule(True, "06:30", 0)
    designation_file(root).write_text(f"{HERE}\n", encoding="utf-8")

    done = after_install.run(reason=after_install.REASON_REPAIR)

    assert done.installed and "<Repetition>" not in registered_xml()
    assert done.schedule_sentence == scheduling.SCHEDULE_REGISTERED_DAILY.format(start="06:30")
    designation_file(root).unlink()
    claimed = after_install.run(reason=after_install.REASON_REPAIR)
    assert claimed.schedule_sentence == scheduling.SCHEDULE_CLAIMED_DAILY.format(host=HERE, start="06:30")


def test_off_removes_this_computers_task_claims_nothing_and_says_so(root, windows):
    settings.set_schedule(False, "07:00", 120)
    windows["exists"] = True
    assert not designation_file(root).exists()

    done = after_install.run(reason=after_install.REASON_REPAIR)

    assert done.schedule == scheduling.OFF and done.exit_code == 0 and not done.installed
    assert done.schedule_sentence == scheduling.SCHEDULE_OFF
    assert creates(windows["calls"]) == []
    assert ["schtasks", "/delete", "/tn", scheduling.TASK_NAME, "/f"] in windows["calls"]
    assert not designation_file(root).exists()                    # not claimed, not changed
    assert done.lines[0] == scheduling.SCHEDULE_OFF


def test_off_leaves_the_designation_as_it_was(root, windows):
    designation_file(root).write_text(f"{HERE}\n", encoding="utf-8")
    settings.set_schedule(False, "07:00", 120)

    after_install.run(reason=after_install.REASON_REPAIR)

    assert designation_file(root).read_text(encoding="utf-8") == f"{HERE}\n"


def test_off_with_no_task_here_deletes_nothing(root, windows):
    settings.set_schedule(False, "07:00", 120)
    after_install.run(reason=after_install.REASON_REPAIR)
    assert all(command[1] == "/query" for command in windows["calls"])


def test_turning_it_on_again_registers_as_before(root, windows):
    settings.set_schedule(False, "07:00", 120)
    after_install.run(reason=after_install.REASON_REPAIR)
    settings.set_schedule(True, "07:00", 120)

    done = after_install.run(reason=after_install.REASON_REPAIR)

    assert done.schedule == scheduling.CLAIMED and done.installed
    assert len(creates(windows["calls"])) == 1


def test_a_task_that_cannot_be_removed_is_a_failure_not_a_silent_off(root, windows, monkeypatch):
    settings.set_schedule(False, "07:00", 120)

    def refuse(*args, **kwargs):
        raise RuntimeError("schtasks could not delete the task (1): denied")

    monkeypatch.setattr(scheduling, "remove_task", refuse)
    done = after_install.run(reason=after_install.REASON_REPAIR)
    assert done.exit_code == 1 and "denied" in done.schedule_sentence


def test_the_launch_door_runs_again_when_the_choice_changed(root, windows):
    assert after_install.run(reason=after_install.REASON_SETUP).exit_code == 0
    assert after_install.launch() is None

    settings.set_schedule(True, "09:00", 30)
    rerun = after_install.launch()

    assert rerun is not None and rerun.installed and "T09:00:00" in registered_xml()
    assert after_install.launch() is None
    settings.set_schedule(False, "09:00", 30)
    assert after_install.launch().schedule == scheduling.OFF
    assert after_install.launch() is None


def test_the_launch_door_makes_no_schtasks_call_when_nothing_changed(root, windows, monkeypatch):
    settings.set_schedule(True, "09:00", 30)
    assert after_install.run(reason=after_install.REASON_SETUP).exit_code == 0
    recorded = json.loads(after_install.record_path().read_text(encoding="utf-8"))
    assert recorded["preference"] == {"enabled": True, "start": "09:00", "every": 30}
    calls_before = len(windows["calls"])

    assert after_install.launch() is None

    assert len(windows["calls"]) == calls_before


def test_a_record_from_before_the_setting_is_run_again_once(root, windows):
    assert after_install.run(reason=after_install.REASON_SETUP).exit_code == 0
    record = json.loads(after_install.record_path().read_text(encoding="utf-8"))
    del record["preference"]
    after_install.record_path().write_text(json.dumps(record), encoding="utf-8")

    assert after_install.launch() is not None
    assert after_install.launch() is None


@pytest.mark.parametrize("bad", [{"schedule_start": "7pm"}, {"schedule_every": 45}, {"schedule_enabled": "no"}])
def test_an_unreadable_choice_is_a_recorded_failure_and_no_task_is_registered(root, windows, bad):
    saved = json.loads(settings.settings_path().read_text(encoding="utf-8"))
    settings.settings_path().write_text(json.dumps({**saved, **bad}), encoding="utf-8")

    done = after_install.run(reason=after_install.REASON_LAUNCH)

    assert done.exit_code == 1 and done.schedule == after_install.PREFERENCE_KEY
    assert creates(windows["calls"]) == []
    assert str(settings.settings_path()) in done.schedule_sentence and "Schedule button" in done.schedule_sentence
    assert after_install.notice()["failed"] == [done.schedule_sentence]
    assert after_install.launch() is not None                       # tried again at the next start
    # the record check still ran
    assert done.check != "" and done.check_sentence != done.schedule_sentence


def test_repair_with_a_named_start_and_interval_saves_them_first(root, windows):
    settings.set_schedule(True, "07:00", 120)

    done = after_install.run(reason=after_install.REASON_REPAIR, start="06:15", every=30)

    assert done.installed and "T06:15:00" in registered_xml() and "PT30M" in registered_xml()
    assert settings.schedule_preference() == scheduling.SchedulePreference(True, "06:15", 30)


def test_repair_with_a_named_choice_that_is_not_allowed_saves_and_registers_nothing(root, windows):
    settings.set_schedule(True, "07:00", 120)

    done = after_install.run(reason=after_install.REASON_REPAIR, start="6pm")

    assert done.exit_code == 1 and creates(windows["calls"]) == []
    assert "'6pm'" in done.schedule_sentence
    assert settings.schedule_preference() == scheduling.SchedulePreference(True, "07:00", 120)
