"""Tests for tracker/api.py: the clients root, the room a return has and the record's checkpoint.

The root and its settings, the last-pass file the list names, the room a return has (decision 131) and the record's
checkpoint with the derivation of the commands that write it (decision 159).

Split from ``tests/test_api.py`` by SPEC-architecture-p5 P5.14 (E-3), by the banners the old file kept its
sections under, each test moved byte for byte with its section, so that each family runs as its own process
(Jason, 2026-09-29) and an affected-tests run reaches only the family a change touched. The map owns this file
as ``tracker/api.py``'s test by its name (decision P350). What more than one family reads is
``tests/api_driver.py``'s, because a test file may not import another (``tests/test_suite_shape.py``).
"""

import datetime as dt
import json
from pathlib import Path

import pytest

import tracker.api as api
from tests import api_driver
from tests.api_driver import (
    HOUSEHOLD,
    _a_deeper_root,
    _a_renamed_household,
    _on_the_office_computer,
    payload_of_state,
    run,
    where,
)
from tests.builders import make_engagement
from tests.samples import text_pdf
from tracker import ledger, store
from tracker.index import NEEDS_REVIEW, read_index
from tracker.layout import inbox_of, return_dir_for
from tracker.manifest import load_manifest
from tracker.runner import DRAFT_WEEKDAY, WEEKDAY_NAMES
from tracker.scheduling import DEFAULT_REPEAT_MINUTES, DEFAULT_START, SCHEDULE_XML_ENCODING

#: A fixture of ``tests/api_driver.py``, named here so every claim below can ask for it.
demo_root = api_driver.demo_root


# ------------------------------------------------------------------ the root ----


def test_without_a_root_the_app_is_told_to_set_one(capsys, tmp_path, monkeypatch):
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    code, payload = run(capsys, "list")
    assert code == 0 and payload["needs_root"] is True and payload["engagements"] == []
    code, payload = run(capsys, "create", stdin={"items": [{"identifier": "A01", "document": "W-2"}]})
    assert code == 1 and "where your clients live" in payload["error"]


def test_the_app_is_told_at_once_when_it_sits_too_deep_for_its_reader(capsys, tmp_path, monkeypatch):
    """SPEC-169 section 9: ``list``, the app's first call, carries the
    short-path warning (shown in a banner that stays), with a root or
    without one; and nothing when the app's folder is fine."""
    from tracker import ocr
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    assert run(capsys, "list")[1]["reader_warning"] == ""
    monkeypatch.setattr(ocr, "reader_path_warning", lambda: ocr.READER_PATH_WARNING)
    assert run(capsys, "list")[1]["reader_warning"] == ocr.READER_PATH_WARNING
    clients = tmp_path / "Clients"
    clients.mkdir()
    assert run(capsys, "set-root", stdin={"root": str(clients)})[0] == 0
    code, payload = run(capsys, "list")
    assert code == 0 and payload["needs_root"] is False
    assert payload["reader_warning"] == ocr.READER_PATH_WARNING


def test_the_app_state_reports_the_last_pass(capsys, tmp_path, monkeypatch):
    """``list``, the call the main screen is drawn from, carries the one
    line about the scheduled pass (decision 159, E4) in the runner's words
    and colour, with a root or without one: amber before any pass, red
    after a failed one."""
    import datetime as dt

    from tracker import run_log, runner
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    code, payload = run(capsys, "list")
    assert code == 0 and payload["needs_root"] is True
    assert payload["last_pass"] == {"text": run_log.LAST_PASS_NEVER, "level": run_log.LEVEL_WARN,
                                    "ok": False, "running": False, "when": None}

    now = dt.datetime.now()
    runner.write_last_pass(runner.last_pass_path(), started=now, ended=now, root="",
                           result=runner.PASS_FAILED, reason_code=runner.PASS_ROOT_REFUSED)
    clients = tmp_path / "Clients"
    clients.mkdir()
    assert run(capsys, "set-root", stdin={"root": str(clients)})[0] == 0
    code, payload = run(capsys, "list")
    assert code == 0 and payload["needs_root"] is False
    assert payload["last_pass"]["level"] == run_log.LEVEL_ERR
    assert runner.PASS_REASONS[runner.PASS_ROOT_REFUSED] in payload["last_pass"]["text"]
    # The last-sort line needs no parsing of the runner's words: a failed
    # pass is not ok and says when it started (SPEC-shell 9.3).
    assert payload["last_pass"]["ok"] is False and payload["last_pass"]["running"] is False
    assert payload["last_pass"]["when"] == now.isoformat(timespec="seconds")
    runner.write_last_pass(runner.last_pass_path(), started=now, ended=now, root="",
                           result=runner.PASS_SUCCEEDED)
    succeeded = run(capsys, "list")[1]["last_pass"]
    assert succeeded["ok"] is True and succeeded["running"] is False
    # A pass still running is neither well nor failed (pilot P256): the file
    # records three results, and ``running`` is what tells a pass in progress
    # from a failed one, both ``ok: false``.
    runner.write_last_pass(runner.last_pass_path(), started=now, ended=None, root="",
                           result=runner.PASS_RUNNING)
    running = run(capsys, "list")[1]["last_pass"]
    assert running["running"] is True and running["ok"] is False
    assert running["when"] == now.isoformat(timespec="seconds")
    runner.last_pass_path().write_bytes(b"not json")
    unreadable = run(capsys, "list")[1]["last_pass"]
    assert unreadable["running"] is False and unreadable["ok"] is False and unreadable["when"] is None


def test_the_last_pass_reply_and_its_line_agree_on_an_oversized_file(tmp_path, monkeypatch):
    """The reply's ``ok`` and ``when`` read the last-pass file under the cap
    its line reads it under (``run_log.LAST_PASS_MAX_BYTES``): a file past
    it is "could not be read" in the line and neither ok nor dated in the
    reply, never a red line beside a green tick."""
    import datetime as dt
    import json

    from tracker import api, pass_order, run_log, runner
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    now = dt.datetime.now()
    runner.write_last_pass(runner.last_pass_path(), started=now, ended=now, root="",
                           result=runner.PASS_SUCCEEDED)
    data = json.loads(runner.last_pass_path().read_text(encoding="utf-8"))
    padded = json.dumps(data) + " " * run_log.LAST_PASS_MAX_BYTES
    assert len(padded) < pass_order.PASS_ORDER_MAX_BYTES
    runner.last_pass_path().write_text(padded, encoding="utf-8")
    reply = api._last_pass()
    assert reply["level"] == run_log.LEVEL_ERR
    assert reply["ok"] is False and reply["running"] is False and reply["when"] is None


def test_last_pass_is_answered_without_a_root_or_a_store(capsys, tmp_path, monkeypatch):
    """Pilot P256: the shell asks ``last-pass`` when the file changes (P277;
    on a timer before), so it reads the settings and the last-pass file and
    nothing else - no clients root chosen, no store opened - and answers the
    dict ``list`` carries. It is not a writing command."""
    from tracker import runner
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    assert "last-pass" in api.COMMANDS and "last-pass" not in api.WRITING_COMMANDS
    # Asked first, in a fresh data home, with the store made unopenable: an
    # answer at all proves the store was never opened (SPEC-mac-check-fixes
    # 1.3), and no store file is left behind.
    def refuse(*_args, **_kwargs):
        raise AssertionError("the store was opened")

    with monkeypatch.context() as unopenable:
        unopenable.setattr(store, "open", refuse)
        code, asked = run(capsys, "last-pass")
    assert code == 0 and set(asked) == {"last_pass", "warnings"}
    assert not store.store_path().exists(), "the store was never created"
    code, listed = run(capsys, "list")
    assert code == 0 and listed["needs_root"] is True
    assert asked["last_pass"] == listed["last_pass"]
    now = dt.datetime.now()
    runner.write_last_pass(runner.last_pass_path(), started=now, ended=None, root="",
                           result=runner.PASS_RUNNING)
    code, asked = run(capsys, "last-pass")
    assert code == 0 and asked["last_pass"]["running"] is True
    assert asked["last_pass"] == run(capsys, "list")[1]["last_pass"]
    # P277: the polling watch is gone - the key and both constants with it.
    assert "last_pass_watch" not in listed["vocab"]
    assert not hasattr(api, "LAST_PASS_WATCH_RUNNING_SECONDS") and not hasattr(api, "LAST_PASS_WATCH_IDLE_SECONDS")


# ── P277 (SPEC-ui-menu-speed §1): the list names the last-pass file ───────


def test_the_list_names_the_last_pass_file_the_runner_writes(capsys, tmp_path, monkeypatch):
    """P277: ``vocab.shell.last_pass_file`` is the very path the runner writes
    (``runner.last_pass_path()``), so ``main.js`` watches its folder and never
    builds the path itself."""
    from tracker import runner
    from tracker.settings import ENV_DATA_HOME, ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    monkeypatch.delenv(store.ENV_STORE, raising=False)
    monkeypatch.setenv(ENV_DATA_HOME, str(tmp_path / "home"))
    code, listed = run(capsys, "list")
    assert code == 0
    named = listed["vocab"]["shell"]["last_pass_file"]
    assert named == str(runner.last_pass_path())
    assert Path(named).parent == tmp_path / "home" and Path(named).name == runner.LAST_PASS_FILENAME


def test_the_list_names_no_last_pass_file_when_the_data_home_cannot_be_had(capsys, tmp_path, monkeypatch):
    """P277: with no data home to be had, ``list`` still answers (its
    ``machine_warnings`` say why, decision 186) and names no last-pass file,
    which ``main.js`` takes as "watch nothing"."""
    from tracker.settings import DATA_HOME_NOT_ABSOLUTE, ENV_DATA_HOME, ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    monkeypatch.delenv(store.ENV_STORE, raising=False)
    monkeypatch.setenv(ENV_DATA_HOME, "relative-data")
    code, listed = run(capsys, "list")
    assert code == 0 and listed["vocab"]["shell"]["last_pass_file"] is None
    assert listed["machine_warnings"] == [DATA_HOME_NOT_ABSOLUTE.format(value="relative-data")]
    assert api._last_pass_file() is None


def test_the_scheduled_sorting_word_is_in_the_screen_vocabulary():
    """Pilot P256: a pass the schedule is running is drawn as ``Sorting``, a
    word the page does not type; its row is in the wording table."""
    screen = api.vocab()["screen"]
    assert screen["last_sort"]["scheduled"] == "Sorting"
    rows = [line.split("\t") for line in
            (Path(__file__).resolve().parents[1] / "pilot" / "wording-shell.tsv").read_text(
                encoding="utf-8").splitlines()]
    proposed = {row[1]: row[4] for row in rows if len(row) > 4}
    assert proposed["screen.last_sort.scheduled"] == screen["last_sort"]["scheduled"]


def test_the_details_word_is_in_the_screen_vocabulary():
    """Pilot P257: the closed disclosure under a notice's one line is headed
    by the API's word; the page types none."""
    screen = api.vocab()["screen"]
    assert screen["notices"]["details"] == "Details"
    rows = [line.split("\t") for line in
            (Path(__file__).resolve().parents[1] / "pilot" / "wording-shell.tsv").read_text(
                encoding="utf-8").splitlines()]
    proposed = {row[1]: row[4] for row in rows if len(row) > 4}
    assert proposed["screen.notices.details"] == screen["notices"]["details"]


def test_the_short_path_warning_comes_with_the_returns_too(capsys, demo_root, monkeypatch):
    from tracker import ocr

    monkeypatch.setattr(ocr, "reader_path_warning", lambda: ocr.READER_PATH_WARNING)
    spec = {"household": HOUSEHOLD, "return_name": "First", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "list")
    assert code == 0 and payload["engagements"]
    assert payload["reader_warning"] == ocr.READER_PATH_WARNING


def test_set_root_records_the_folder_the_job_will_walk(capsys, tmp_path, monkeypatch):
    from tracker.settings import ENV_SETTINGS_DIR, clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    clients = tmp_path / "Clients"
    clients.mkdir()
    code, payload = run(capsys, "set-root", stdin={"root": str(clients)})
    assert code == 0 and payload["root"] == str(clients)
    assert clients_root() == clients
    code, payload = run(capsys, "set-root", stdin={"root": str(tmp_path / "nope")})
    assert code == 1 and "not a folder" in payload["error"]
    code, payload = run(capsys, "settings")
    assert payload["root"] == str(clients) and payload["exists"] is True


def test_the_firm_is_typed_once_in_settings_and_signs_every_engagement(capsys, demo_root):
    from tracker.settings import firm, set_firm

    set_firm("Park & Daughters CPA")
    assert firm() == "Park & Daughters CPA"
    spec = {"household": HOUSEHOLD, "return_name": "First", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0 and payload["state"]["engagement"]["firm"] == "Park & Daughters CPA"
    # set-root can set it too, once, at first launch.
    code, payload = run(capsys, "set-root", stdin={"root": str(demo_root), "firm": "New Name LLP"})
    assert code == 0 and payload["firm"] == "New Name LLP" == firm()
    assert run(capsys, "list")[1]["vocab"]["firm"] == "New Name LLP"


def test_saving_the_root_registers_the_schedule_on_the_designated_computer(capsys, tmp_path, monkeypatch):
    """Decision 209: the first root saved on the computer that runs the
    schedule registers it with no button - claimed, since no computer is
    named yet - and the reply says so in the scheduler's sentence."""
    from tracker import scheduling
    from tracker.layout import designation_file
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    calls = _on_the_office_computer(monkeypatch)
    clients = tmp_path / "Clients"
    clients.mkdir()
    code, payload = run(capsys, "set-root", stdin={"root": str(clients)})
    assert code == 0, payload
    done = payload["after_install"]
    assert done["schedule"] == scheduling.CLAIMED and done["installed"] is True
    assert done["schedule_sentence"] == scheduling.SCHEDULE_CLAIMED.format(
        host="office-pc", start=DEFAULT_START, every=DEFAULT_REPEAT_MINUTES)
    assert designation_file(clients).read_text(encoding="utf-8") == "office-pc\n"
    assert [command[1] for command in calls] == ["/create"]


def test_set_schedule_saves_the_choice_registers_it_and_says_the_next_run(capsys, demo_root, monkeypatch):
    """Pilot P21: ``set-schedule`` checks, saves, runs the after-install
    step as a repair and answers with its sentence and the next run."""
    from tracker import scheduling, settings
    from tracker.layout import designation_file

    calls = _on_the_office_computer(monkeypatch)
    designation_file(demo_root).parent.mkdir(exist_ok=True)
    designation_file(demo_root).write_text("office-pc\n", encoding="utf-8")

    code, payload = run(capsys, "set-schedule", stdin={"enabled": True, "start": "06:30", "every": 60})

    assert code == 0, payload
    assert (payload["enabled"], payload["start"], payload["every"]) == (True, "06:30", 60)
    assert payload["outcome"] == scheduling.REGISTERED and payload["installed"] is True
    assert payload["sentence"] == scheduling.SCHEDULE_REGISTERED.format(start="06:30", every=60)
    assert payload["next_run"].startswith("Next run: ") and payload["after_install"]["exit"] == 0
    assert settings.schedule_preference() == scheduling.SchedulePreference(True, "06:30", 60)
    assert [command[1] for command in calls] == ["/create"]

    code, off = run(capsys, "set-schedule", stdin={"enabled": False, "start": "06:30", "every": 60})
    assert code == 0, off
    assert off["outcome"] == scheduling.OFF and off["sentence"] == scheduling.SCHEDULE_OFF
    assert off["next_run"] == "" and off["installed"] is False and off["enabled"] is False


def test_set_schedule_promises_no_next_run_on_a_computer_that_registered_nothing(capsys, demo_root, monkeypatch):
    from tracker.layout import designation_file

    calls = _on_the_office_computer(monkeypatch)
    designation_file(demo_root).parent.mkdir(exist_ok=True)
    designation_file(demo_root).write_text("front-desk\n", encoding="utf-8")

    code, payload = run(capsys, "set-schedule", stdin={"enabled": True, "start": "06:30", "every": 60})

    assert code == 0, payload
    assert payload["installed"] is False and payload["next_run"] == ""
    assert not [command for command in calls if command[1] == "/create"]


@pytest.mark.parametrize("stdin", [
    {"enabled": True, "start": "25:00", "every": 60},
    {"enabled": True, "start": "06:30", "every": 45},
    {"enabled": "yes", "start": "06:30", "every": 60},
    {"start": "06:30", "every": 60},
    {},
])
def test_set_schedule_refuses_a_bad_choice_in_a_sentence_and_saves_nothing(capsys, demo_root, stdin):
    from tracker import settings

    before = settings.settings_path().read_text(encoding="utf-8")
    code, payload = run(capsys, "set-schedule", stdin=stdin)
    assert code != 0 and payload["error"] and "allowed" in payload["error"]
    assert settings.settings_path().read_text(encoding="utf-8") == before


def test_settings_returns_the_saved_schedule_and_the_next_run(capsys, demo_root):
    from tracker import settings

    code, payload = run(capsys, "settings")
    assert code == 0 and payload["schedule"] == {"enabled": True, "start": DEFAULT_START,
                                                 "every": DEFAULT_REPEAT_MINUTES}
    assert payload["next_run"].startswith("Next run: ") and payload["schedule_problem"] == ""

    settings.set_schedule(False, "08:00", 0)
    code, payload = run(capsys, "settings")
    assert payload["schedule"] == {"enabled": False, "start": "08:00", "every": 0}
    assert payload["next_run"] == ""


def test_settings_says_a_hand_edited_schedule_is_unusable_rather_than_guessing(capsys, demo_root):
    from tracker import settings

    saved = json.loads(settings.settings_path().read_text(encoding="utf-8"))
    settings.settings_path().write_text(json.dumps({**saved, "schedule_every": 45}), encoding="utf-8")
    code, payload = run(capsys, "settings")
    assert code == 0 and payload["schedule"] is None and payload["next_run"] == ""
    assert "schedule_every" in payload["schedule_problem"]


def test_repair_registers_the_saved_choice_when_the_page_sends_nothing(capsys, demo_root, monkeypatch):
    from tracker import scheduling, settings
    from tracker.layout import designation_file

    settings.set_schedule(True, "05:15", 240)
    _on_the_office_computer(monkeypatch)
    designation_file(demo_root).parent.mkdir(exist_ok=True)
    designation_file(demo_root).write_text("office-pc\n", encoding="utf-8")

    code, payload = run(capsys, "install-schedule", stdin={})

    assert code == 0, payload
    assert payload["start"] == "05:15" and payload["every"] == 240
    xml = Path(payload["xml"]).read_text(encoding=SCHEDULE_XML_ENCODING)
    assert "T05:15:00" in xml and "PT240M" in xml
    assert payload["sentence"] == scheduling.SCHEDULE_REGISTERED.format(start="05:15", every=240)


def test_the_pilot_record_keeps_terms_and_tour_in_the_data_home(capsys):
    """Pilot P46: acceptance and "tour seen" are the tracker's own record,
    per Windows account in the data home, so a restart that cannot reach
    the window's storage still finds them. Read with ``{}``; each write
    answers with the record as it now stands."""
    from tracker.settings import data_home

    code, empty = run(capsys, "pilot-record", stdin={})
    assert code == 0 and (empty["terms"], empty["tour_seen"]) == ("", False)
    assert not (data_home() / api.PILOT_RECORD_FILENAME).exists()      # a read writes nothing

    code, accepted = run(capsys, "pilot-record", stdin={"terms": "1"})
    assert code == 0 and (accepted["terms"], accepted["tour_seen"]) == ("1", False)
    code, seen = run(capsys, "pilot-record", stdin={"tour_seen": True})
    assert code == 0 and (seen["terms"], seen["tour_seen"]) == ("1", True)

    kept = json.loads((data_home() / api.PILOT_RECORD_FILENAME).read_text(encoding="utf-8"))
    assert kept["terms"] == "1" and kept["tour_seen"] is True
    assert kept["terms_accepted_at"] and kept["tour_seen_at"]
    code, again = run(capsys, "pilot-record", stdin={})
    assert (again["terms"], again["tour_seen"]) == ("1", True)


def test_the_pilot_record_keeps_the_signed_name_beside_the_acceptance_time(capsys):
    """P188: the name typed to sign the terms comes with the terms and is
    kept, trimmed, as ``terms_signed_by`` beside ``terms_accepted_at``; the
    reply carries both, so Help, Terms can say who signed and when. An
    acceptance sent without a name keeps none - a name belongs to the
    acceptance it signed."""
    from tracker.settings import data_home

    code, signed = run(capsys, "pilot-record", stdin={"terms": "1", "signed_by": "  Jane Tester "})
    assert code == 0 and signed["terms"] == "1" and signed["terms_signed_by"] == "Jane Tester"
    kept = json.loads((data_home() / api.PILOT_RECORD_FILENAME).read_text(encoding="utf-8"))
    assert kept["terms_signed_by"] == "Jane Tester" and kept["terms_accepted_at"]
    assert signed["terms_accepted_at"] == kept["terms_accepted_at"]
    code, again = run(capsys, "pilot-record", stdin={})
    assert (again["terms_signed_by"], again["terms_accepted_at"]) == ("Jane Tester", kept["terms_accepted_at"])
    code, seen = run(capsys, "pilot-record", stdin={"tour_seen": True})
    assert code == 0 and seen["terms_signed_by"] == "Jane Tester"      # the tour leaves the name alone

    code, unsigned = run(capsys, "pilot-record", stdin={"terms": "2"})
    assert code == 0 and unsigned["terms"] == "2" and unsigned["terms_signed_by"] == ""
    kept = json.loads((data_home() / api.PILOT_RECORD_FILENAME).read_text(encoding="utf-8"))
    assert "terms_signed_by" not in kept


@pytest.mark.parametrize("stdin", [
    {"signed_by": "Jane Tester"}, {"tour_seen": True, "signed_by": "Jane Tester"},
    {"terms": "1", "signed_by": ""}, {"terms": "1", "signed_by": "   "},
    {"terms": "1", "signed_by": "x" * (api.SIGNED_BY_LONGEST + 1)},
    {"terms": "1", "signed_by": None}, {"terms": "1", "signed_by": 7},
])
def test_a_signed_name_without_terms_or_blank_or_too_long_is_refused(capsys, stdin):
    """A name signs the terms or nothing: without them, blank, spaces only,
    not text or past the longest, the whole request is refused in the one
    refusal, which names ``signed_by``, and nothing is written."""
    from tracker.settings import data_home

    code, payload = run(capsys, "pilot-record", stdin=stdin)
    assert code != 0 and payload["error"].startswith("pilot-record takes {} to read")
    assert '"signed_by"' in payload["error"]
    assert not (data_home() / api.PILOT_RECORD_FILENAME).exists()


def test_a_refused_request_never_echoes_the_typed_name(capsys):
    """The refusal is what the page writes to the error log: it echoes the
    rest of the request, with the name in it withheld."""
    name = "Jordan Sample " + "Q" * api.SIGNED_BY_LONGEST
    code, payload = run(capsys, "pilot-record", stdin={"terms": "1", "signed_by": name})
    assert code != 0 and "Jordan Sample" not in payload["error"] and "QQQ" not in payload["error"]
    assert '"signed_by": "(name withheld)"' in payload["error"] and '"terms": "1"' in payload["error"]


def test_a_name_of_the_longest_length_is_kept(capsys):
    name = "J" * api.SIGNED_BY_LONGEST
    code, payload = run(capsys, "pilot-record", stdin={"terms": "1", "signed_by": name})
    assert code == 0 and payload["terms_signed_by"] == name


@pytest.mark.parametrize("stdin", [
    {"terms": "0"}, {"terms": "one"}, {"terms": True}, {"terms": ""}, {"terms": "1234567"},
    {"tour_seen": False}, {"tour_seen": "yes"}, {"terms": "1", "name": "x"},
])
def test_the_pilot_record_refuses_anything_but_a_version_or_tour_seen(capsys, stdin):
    from tracker.settings import data_home

    code, payload = run(capsys, "pilot-record", stdin=stdin)
    assert code != 0 and payload["error"].startswith("pilot-record takes {} to read")
    assert not (data_home() / api.PILOT_RECORD_FILENAME).exists()


def test_an_unreadable_pilot_record_reads_as_not_accepted_and_is_replaced(capsys):
    """Anything wrong with the record is the safe direction: the terms show."""
    from tracker.settings import data_home

    data_home().mkdir(parents=True, exist_ok=True)
    (data_home() / api.PILOT_RECORD_FILENAME).write_text("{not json", encoding="utf-8")
    code, payload = run(capsys, "pilot-record", stdin={})
    assert code == 0 and payload["terms"] == "" and payload["tour_seen"] is False
    code, payload = run(capsys, "pilot-record", stdin={"terms": 2})
    assert code == 0 and payload["terms"] == "2"


def test_the_pilot_record_is_no_client_record(capsys):
    """Not held to the record checkpoint's root: it is this account's own
    app state, and a root the checkpoint refuses must not re-show the terms."""
    assert "pilot-record" in api.COMMANDS and "pilot-record" not in api.WRITING_COMMANDS
    assert "pilot-record" in api.__doc__


def test_the_schedule_dialog_uses_only_the_apis_words(capsys):
    """The page types none of the dialog's words: they come from
    ``vocab.schedule``, and the button sits right after the edit button."""
    here = Path(__file__).resolve().parent.parent / "app" / "renderer"
    js = (here / "app.js").read_text(encoding="utf-8")
    html = (here / "index.html").read_text(encoding="utf-8")
    shell = (here / "shell.js").read_text(encoding="utf-8")
    assert 'id="btn-schedule"' not in html, "the button is Tools > Schedule now (SPEC 5.1)"
    assert "schedule: () => openSchedule()," in shell
    assert 'call(["set-schedule"]' in js and 'call(["settings"]' in js
    # The dialog's help lines are cut (SPEC 2.7, E87): no "Scan works either
    # way" note and no loading sentence (outline rows and one word instead).
    for word in ("words.title", "words.enabled_label", "words.on", "words.off",
                 "words.start_label", "words.every_label", "words.every_choices",
                 "words.save", "words.cancel"):
        assert word in js, word
    assert "words.note" not in js and "words.loading" not in js and "shellSkeleton(3)" in js
    for literal in (api.SCHEDULE_BUTTON, api.SCHEDULE_TITLE, api.SCHEDULE_ENABLED_LABEL,
                    api.SCHEDULE_START_LABEL, api.SCHEDULE_EVERY_LABEL, api.SCHEDULE_NOTE,
                    api.SCHEDULE_LOADING, *api.SCHEDULE_EVERY_LABELS.values()):
        assert f'"{literal}"' not in js and f">{literal}<" not in html, literal
    assert "DEFAULT_START" not in js
    assert "set-schedule" in api.COMMANDS and "set-schedule" in api.WRITING_COMMANDS
    assert "set-schedule" in api.__doc__


def test_install_schedule_is_the_repair_path_and_says_its_outcome(capsys, demo_root, monkeypatch):
    """Decision 209: ``install-schedule`` runs the after-install step again,
    on purpose; the reply carries the outcome's key and the sentence the app
    shows as it is, and ``installed`` only when a task was registered here."""
    from tracker import scheduling
    from tracker.layout import designation_file
    from tracker.settings import settings_dir

    code, payload = run(capsys, "install-schedule", stdin={})     # no Task Scheduler here
    assert code == 0, payload
    assert payload["outcome"] == scheduling.NO_TASK_SCHEDULER and payload["installed"] is False
    assert payload["sentence"] == scheduling.SCHEDULE_NOT_HERE

    calls = _on_the_office_computer(monkeypatch)
    designation_file(demo_root).parent.mkdir(exist_ok=True)
    designation_file(demo_root).write_text("office-pc\n", encoding="utf-8")
    code, payload = run(capsys, "install-schedule", stdin={"start": "06:30", "every": 60})
    assert code == 0, payload
    assert payload["outcome"] == scheduling.REGISTERED and payload["installed"] is True
    assert payload["sentence"] == scheduling.SCHEDULE_REGISTERED.format(start="06:30", every=60)
    assert payload["start"] == "06:30" and payload["every"] == 60
    assert payload["draft_day"] == WEEKDAY_NAMES[DRAFT_WEEKDAY]
    assert payload["xml"] == str(scheduling.schedule_xml_path())
    assert payload["root"] == str(demo_root) and payload["settings"] == str(settings_dir())
    xml = Path(payload["xml"]).read_text(encoding=SCHEDULE_XML_ENCODING)
    assert "T06:30:00" in xml and "PT60M" in xml and str(demo_root) not in xml
    assert calls == [payload["command"]]

    designation_file(demo_root).write_text("front-desk\n", encoding="utf-8")
    calls = _on_the_office_computer(monkeypatch, task_exists=True)
    code, payload = run(capsys, "install-schedule", stdin={})
    assert payload["outcome"] == scheduling.ELSEWHERE and payload["installed"] is False
    assert payload["sentence"] == scheduling.SCHEDULE_ELSEWHERE.format(
        host="front-desk", removed=scheduling.SCHEDULE_REMOVED)
    assert [command[1] for command in calls] == ["/query", "/delete"]
    assert payload["host"] == "front-desk"          # the page's offer to move it names it


def test_install_schedule_writes_the_task_file_into_the_data_home(capsys, demo_root, monkeypatch):
    """Decision 186: the task's file names the program and the settings
    folder, and is written into the tracker's data home - never beside the
    program in the settings folder."""
    from tracker.scheduling import SCHEDULE_XML_FILENAME, schedule_xml_path
    from tracker.settings import settings_dir

    _on_the_office_computer(monkeypatch)            # decision 209: the one computer that registers
    code, payload = run(capsys, "install-schedule", stdin={})
    assert code == 0, payload
    assert payload["installed"] is True, payload
    assert payload["xml"] == str(schedule_xml_path())
    assert Path(payload["xml"]).is_file()
    assert not (settings_dir() / SCHEDULE_XML_FILENAME).exists()


def test_the_app_names_what_an_earlier_version_left_on_its_first_screen(capsys, tmp_path, monkeypatch):
    """Decision 186: ``list``, with a root or without one, carries what an
    earlier version left beside the app in ``machine_warnings`` - a banner
    that stays until the files are gone - and nothing when nothing is there."""
    from tracker import store
    from tracker.runner import CODE_LEFT_BEHIND, LEFT_BEHIND, left_behind_warnings
    from tracker.settings import ENV_SETTINGS_DIR, data_home

    app = tmp_path / "app"
    app.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(app))
    monkeypatch.setenv(store.ENV_STORE, str(data_home() / store.STORE_FILENAME))
    store.close()
    assert run(capsys, "list")[1]["machine_warnings"] == []

    (app / store.STORE_FILENAME).write_bytes(b"an old store")
    expected = LEFT_BEHIND.format(paths=str(app.resolve() / store.STORE_FILENAME), home=data_home())
    assert left_behind_warnings(None) == [(CODE_LEFT_BEHIND, expected)]
    code, payload = run(capsys, "list")
    assert code == 0 and payload["needs_root"] is True
    assert payload["machine_warnings"] == [expected]
    clients = tmp_path / "Clients"
    clients.mkdir()
    assert run(capsys, "set-root", stdin={"root": str(clients)})[0] == 0
    code, payload = run(capsys, "list")
    assert code == 0 and payload["needs_root"] is False
    assert payload["machine_warnings"] == [expected]
    assert (app / store.STORE_FILENAME).read_bytes() == b"an old store"     # named, never deleted


def test_the_first_screen_says_to_move_the_checkpoint_left_behind_never_to_delete_it(
        capsys, tmp_path, monkeypatch):
    """Decision 186 on 159: an old record checkpoint beside the app is its
    own banner, the move sentence, and never in the sentence that says
    delete."""
    from tracker import checkpoint, store
    from tracker.runner import LEFT_BEHIND, LEFT_BEHIND_TO_MOVE
    from tracker.settings import ENV_SETTINGS_DIR, data_home

    app = tmp_path / "app"
    app.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(app))
    monkeypatch.setenv(store.ENV_STORE, str(data_home() / store.STORE_FILENAME))
    store.close()
    (app / checkpoint.CHECKPOINT_FILENAME).write_bytes(b"an old checkpoint")
    code, payload = run(capsys, "list")
    assert code == 0
    assert payload["machine_warnings"] == [LEFT_BEHIND_TO_MOVE.format(
        paths=str(app.resolve() / checkpoint.CHECKPOINT_FILENAME), home=data_home())]
    assert "- delete them." not in payload["machine_warnings"][0] and "- delete them." in LEFT_BEHIND
    assert (app / checkpoint.CHECKPOINT_FILENAME).read_bytes() == b"an old checkpoint"


def test_opening_a_return_never_makes_a_fresh_checkpoint_while_the_old_one_sits_beside_the_program(
        capsys, demo_root, monkeypatch):
    """The rebase review of 186 (MF1): opening one return is a read, yet its
    catch-up would make a fresh checkpoint in the data home and trust every
    record "as it is". It makes none: the view and a writing command are
    each refused in the first screen's own sentence - what to move, and
    where - and the old file is not touched."""
    from tracker import checkpoint
    from tracker.runner import LEFT_BEHIND_TO_MOVE
    from tracker.settings import data_home, settings_dir

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    old = settings_dir() / checkpoint.CHECKPOINT_FILENAME    # the fixture's: 159's layout
    before = old.read_bytes()
    store.close()
    monkeypatch.setenv(store.ENV_STORE, str(data_home() / store.STORE_FILENAME))
    new = checkpoint.path_for(store.store_path())
    said = LEFT_BEHIND_TO_MOVE.format(paths=old.resolve(), home=new.parent)

    for argv in (("state", api.ENGAGEMENT_FLAG, str(engagement)),
                 ("acknowledge-foreign", api.ENGAGEMENT_FLAG, str(engagement))):
        code, payload = run(capsys, *argv)
        assert code == 1 and payload["failure"]["kind"] == "refused", argv
        assert payload["error"] == said, argv
    assert not new.exists() and old.read_bytes() == before


def test_a_data_home_that_cannot_be_had_is_a_banner_on_the_first_screen_never_an_error(
        capsys, tmp_path, monkeypatch):
    """Decision 186's review, M1: with a clients root saved, a data home that
    cannot be had would stop the root's own check - so ``list`` still
    answers, with its vocabulary, keeps the saved root rather than asking for
    it again, walks nothing, and says the data home's sentence in
    ``machine_warnings`` - the API's own words, with no class name in front."""
    from tracker import store
    from tracker.settings import DATA_HOME_NOT_ABSOLUTE, ENV_DATA_HOME, ENV_SETTINGS_DIR

    app = tmp_path / "app"
    app.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(app))
    clients = tmp_path / "Clients"
    clients.mkdir()
    assert run(capsys, "set-root", stdin={"root": str(clients)})[0] == 0
    store.close()
    monkeypatch.delenv(store.ENV_STORE, raising=False)
    monkeypatch.setenv(ENV_DATA_HOME, "relative-data")

    code, payload = run(capsys, "list")
    assert code == 0, payload
    assert "error" not in payload
    assert payload["needs_root"] is False
    assert payload["root"] == str(clients.resolve())
    assert payload["vocab"]
    assert payload["engagements"] == [] and payload["households"] == []
    assert payload["machine_warnings"] == [DATA_HOME_NOT_ABSOLUTE.format(value="relative-data")]


def test_without_a_data_home_the_pages_error_never_points_at_an_error_log_that_is_not_there(monkeypatch):
    """Decision 186: with no data home there is no error log, so none is
    named to the shell; the page's own-error line is the same short line
    either way (SPEC-shell 11.2), and the details are not kept."""
    from tracker import store
    from tracker.api import PAGE_ERROR, vocab
    from tracker.settings import ENV_DATA_HOME

    shell = vocab()["shell"]
    assert shell["error_log"] and shell["page_error"] == PAGE_ERROR
    store.close()
    monkeypatch.delenv(store.ENV_STORE, raising=False)
    monkeypatch.setenv(ENV_DATA_HOME, "relative-data")
    shell = vocab()["shell"]
    assert shell["error_log"] == ""
    assert shell["page_error"] == PAGE_ERROR == "The App Hit an Error"
    assert not hasattr(api, "PAGE_ERROR_NO_LOG")

def test_the_first_screen_says_every_machine_warning_in_a_notice_of_its_own():
    """SPEC 2.2 E30 and 11.1: each machine warning is a notice that stays until
    a person dismisses it (decisions 186 and 193), in its short line; the API's
    sentence, which can name a folder, goes to the error log and is never drawn
    (the drawing is pinned in test_shell)."""
    renderer = Path(__file__).resolve().parent.parent / "app" / "renderer"
    js = (renderer / "app.js").read_text(encoding="utf-8")
    html_text = (renderer / "index.html").read_text(encoding="utf-8")
    assert 'id="machine-warnings"' not in html_text
    body = js[js.index("function renderMachineNotices("):]
    body = body[:body.index("\n}\n")]
    assert 'syncNotices("machine"' in body and 'shortNotice("machine")' in body and "detail: machine.join" in body
    assert "renderMachineNotices(listed);" in js


def test_every_reply_that_runs_the_after_install_step_carries_the_engines_wait(capsys, demo_root, monkeypatch):
    """Pilot P257 (review 1, finding 3): the first-screen notice's Details
    start with the engine's ``FINDINGS_WAIT`` whichever reply drew them, so
    ``set-root``, ``install-schedule``, ``move-schedule-here`` and
    ``set-schedule`` carry ``wait`` in their ``after_install`` as the ``list``
    reply's notice does: the engine's sentence when the run found something
    for a person, "" otherwise."""
    import dataclasses

    from tracker import after_install
    from tracker.layout import designation_file

    _on_the_office_computer(monkeypatch)
    designation_file(demo_root).parent.mkdir(exist_ok=True)
    designation_file(demo_root).write_text("front-desk\n", encoding="utf-8")
    real = after_install.run
    found: list[tuple[str, ...]] = []
    monkeypatch.setattr(after_install, "run", lambda **kwargs: dataclasses.replace(real(**kwargs), findings=tuple(found)))
    commands = [("set-root", {"root": str(demo_root)}), ("install-schedule", {}),
                ("move-schedule-here", {}), ("set-schedule", {"enabled": True, "start": "06:30", "every": 60})]
    for finding, wait in (((), ""), (("Some Household: line 2 of the record is malformed",), after_install.FINDINGS_WAIT)):
        found[:] = finding
        for command, stdin in commands:
            designation_file(demo_root).write_text("front-desk\n", encoding="utf-8")
            code, payload = run(capsys, command, stdin=stdin)
            assert code == 0, (command, payload)
            assert payload["after_install"]["wait"] == wait, command
            assert payload["after_install"]["findings"] == list(finding), command


def test_move_schedule_here_moves_the_schedule_from_the_packaged_app(capsys, demo_root, monkeypatch):
    """Decision 209, the review's S5: the packaged app has no command line,
    so ``move-schedule-here`` is the same move as ``--move-schedule-here`` -
    the designation names this computer, and the step runs as a repair and
    registers here. The page asks only after Repair found another computer
    named, in ``vocab.schedule.move_confirm`` with that computer's name."""
    from tracker import after_install, scheduling
    from tracker.layout import designation_file

    calls = _on_the_office_computer(monkeypatch)
    designation_file(demo_root).parent.mkdir(exist_ok=True)
    designation_file(demo_root).write_text("front-desk\n", encoding="utf-8")

    code, payload = run(capsys, "move-schedule-here", stdin={})

    assert code == 0, payload
    assert payload["moved"] is True and payload["installed"] is True
    assert payload["sentence"] == scheduling.MOVED_FROM.format(host="front-desk", here="office-pc")
    assert payload["outcome"] == scheduling.REGISTERED
    assert payload["after_install"]["reason"] == after_install.REASON_REPAIR
    assert designation_file(demo_root).read_text(encoding="utf-8") == "office-pc\n"
    assert [command[1] for command in calls] == ["/create"]
    js = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(encoding="utf-8")
    assert 'call(["move-schedule-here"]' in js and "vocab.schedule.move_confirm" in js
    assert "confirm(moveScheduleQuestion(result.host))" in js
    assert "front-desk" not in api.SCHEDULE_MOVE_CONFIRM and "{host}" in api.SCHEDULE_MOVE_CONFIRM


def test_a_mac_removes_its_schedule_from_the_tools_menu_and_nothing_else(capsys, demo_root, a_mac, monkeypatch):
    """SPEC-mac R29: ``remove-schedule-here`` is a writing command (the vocabulary says so,
    so the app refreshes after it) that runs ``after_install.remove_here``: the agent and
    its file go, the clients folder and the designation stay, and the page types none of
    the words - the question is the API's, and the sentence is the step's own."""
    import platform

    from tracker import after_install, scheduling
    from tracker.layout import designation_file

    monkeypatch.setattr(platform, "node", lambda: "OFFICE-MAC")
    assert run(capsys, "after-install", stdin={"reason": "launch"})[0] == 0
    assert scheduling.launch_agent_path().is_file() and a_mac.launchd.loaded
    designated = designation_file(demo_root).read_text(encoding="utf-8")

    code, payload = run(capsys, "remove-schedule-here", stdin={})

    assert code == 0, payload
    assert payload["removed"] is True and payload["sentence"] == after_install.SCHEDULE_REMOVED_FROM_MAC
    assert not scheduling.launch_agent_path().exists() and not a_mac.launchd.loaded
    assert designation_file(demo_root).read_text(encoding="utf-8") == designated and demo_root.is_dir()
    assert "remove-schedule-here" in api.WRITING_COMMANDS and "remove-schedule-here" in api.COMMANDS
    assert "remove-schedule-here" in run(capsys, "list")[1]["vocab"]["writing_commands"]
    assert api.vocab()["schedule"]["remove_confirm"] == "Remove the Schedule From This Mac?"
    here = Path(__file__).resolve().parent.parent / "app" / "renderer"
    js, shell = (here / "app.js").read_text(encoding="utf-8"), (here / "shell.js").read_text(encoding="utf-8")
    assert "confirm(vocab.schedule.remove_confirm)" in js and 'call(["remove-schedule-here"]' in js
    assert "remove_schedule_here: () => removeScheduleHere()," in shell
    for literal in (api.SCHEDULE_REMOVE_CONFIRM, after_install.SCHEDULE_REMOVED_FROM_MAC):
        assert literal not in js, literal


def test_removing_the_schedule_where_there_is_no_mac_changes_nothing(capsys, demo_root):
    from tracker import after_install

    code, payload = run(capsys, "remove-schedule-here", stdin={})
    assert code == 0 and payload["removed"] is False and payload["sentence"] == after_install.REMOVE_ONLY_ON_A_MAC


def test_a_launch_step_that_raises_is_recorded_for_the_notice(capsys, tmp_path, monkeypatch):
    """The review's N1: the shell does not read the launch door's reply, so
    anything the step raises is recorded in one constant sentence, which
    the first screen's notice shows, and the next launch tries again."""
    from tracker import after_install
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))

    def broken():
        raise OSError("a pull is rewriting the modules")

    monkeypatch.setattr(after_install, "program_identity", broken)
    code, launched = run(capsys, "after-install", stdin={"reason": "launch"})

    assert code == 0 and launched == {"ran": True, "failed": [after_install.LAUNCH_FAILED], "warnings": []}
    notice = run(capsys, "list")[1]["after_install"]
    assert notice["failed"] == [after_install.LAUNCH_FAILED] and "rewriting" not in str(notice)
    monkeypatch.undo()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    assert run(capsys, "after-install", stdin={"reason": "launch"})[1]["ran"] is True


def test_state_carries_the_after_install_findings_until_a_clean_run(capsys, tmp_path, monkeypatch):
    """Decision 209, R3: the first screen's call carries what the last
    after-install run left for a person - with a root or without one - and
    nothing once a run finds nothing. The launch door does nothing when the
    program has not changed."""
    import json as _json

    from tracker import after_install
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    assert run(capsys, "list")[1]["after_install"] is None

    finding = "Some Household: line 2 of the record is malformed"
    path = after_install.record_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps({"program": "", "ran_at": "2026-09-26T08:00:00", "reason": "setup",
                                 "schedule": "no_root", "findings": [finding], "failed": []}),
                    encoding="utf-8")
    code, listed = run(capsys, "list")
    assert code == 0 and listed["needs_root"] is True
    assert listed["after_install"] == {"findings": [finding], "failed": [], "ran_at": "2026-09-26T08:00:00",
                                       "wait": after_install.FINDINGS_WAIT}
    assert listed["vocab"]["after_install"]["heading"] == api.AFTER_INSTALL_HEADING

    code, launched = run(capsys, "after-install", stdin={"reason": "launch"})
    assert code == 0 and launched["ran"] is True and launched["findings"] == []
    assert run(capsys, "list")[1]["after_install"] is None
    assert run(capsys, "after-install", stdin={"reason": "launch"})[1] == {"ran": False, "warnings": []}   # the envelope (decision 193)


def test_the_schedule_is_repaired_from_the_tools_menu_in_the_apis_words():
    """Decision 209, R4: the Install Schedule button is gone; the repair
    path is Tools > Repair schedule (SPEC 5.1), its confirm dialog is the
    API's word, and the outcome is the API's sentence - the page types none
    of it. What the step left for a person is one notice."""
    here = Path(__file__).resolve().parent.parent / "app" / "renderer"
    js = (here / "app.js").read_text(encoding="utf-8")
    html = (here / "index.html").read_text(encoding="utf-8")
    shell = (here / "shell.js").read_text(encoding="utf-8")
    assert "Install Schedule" not in html and 'id="btn-repair-schedule"' not in html
    assert "repair_schedule: () => repairSchedule()," in shell
    assert "confirm(vocab.schedule.repair_confirm)" in js
    assert "outcome(result.sentence," in js
    for literal in (api.SCHEDULE_REPAIR_LABEL, api.SCHEDULE_REPAIR_HELP, api.AFTER_INSTALL_HEADING):
        assert literal not in js and literal not in html, literal
    assert "vocab.after_install.heading" in js and 'id="after-install"' not in html


# ------------------------------------ decision 131: the room a return has ----


#: How far past the limit ``_a_long_row_return``'s second row's canonical
#: copy is: less than the eighteen characters a two-character document
#: gives back from a twenty-character short name, so shortening the other
#: row's label is a save that fits.
LONG_ROW_OVER = 10
#: The period both of ``_a_long_row_return``'s rows ask for: long enough
#: that a row is past the limit in a return whose review folder has room
#: under either setting - with long paths off a return of 206 characters
#: at most, where a copy named by a short name and a TY2025 never is
#: (pilot decision P29).
LONG_ROW_PERIOD = "Jan 2025 to Dec 2025"


#: What the plain return under that root keeps below the tightest limit
#: that applies to its copies (Excel's, for a spreadsheet), at the least.
FITS_MARGIN = 20


def _a_long_row_return(root, household=HOUSEHOLD, second="B01"):
    """A return made the way a test makes one - past creation's refusal - whose
    second row's canonical copy no longer fits under ``root``: the state a
    root that grew leaves behind.

    Its return name is padded so the return folder leaves the second row's
    canonical copy exactly ``LONG_ROW_OVER`` past the limit: since decision
    144 a row's name in the path is its short name - twenty characters at
    most - so the depth is the folder's, as it is when a root grows, not a
    hundred-character label's. Since decision 168 the copy sits in
    Prepared itself, so the depth below the return is one name, not a
    folder and a name. Both rows ask for :data:`LONG_ROW_PERIOD`. ``second``
    is the long row's identifier, three characters wide whatever it is."""
    from tests.builders import TEST_YEAR
    from tracker.layout import NAME_MAX_CHARS, path_limit
    from tracker.manifest import RequestItem

    # The path length below is computed for a three-character identifier ("B01").
    assert len(second) == 3
    below = len("/Prepared/B01 - " + "y" * 20 + f" - {LONG_ROW_PERIOD}.pdf")
    above = len(str(return_dir_for(Path(root), household, TEST_YEAR, "x"))) - len("x")
    pad = path_limit() + LONG_ROW_OVER - below - above - len("1040 - Long ")
    if pad < 1:
        pytest.skip(f"{root} is too long to make the long-row return under it")
    # A name is at most NAME_MAX_CHARS (decision 188): what the return's
    # name cannot hold pads the household's.
    in_return = min(pad, NAME_MAX_CHARS - len("1040 - Long "))
    if pad > in_return:
        household = household + "h" * (pad - in_return)
        if len(household) > NAME_MAX_CHARS:
            pytest.skip(f"{root} is too short to make the long-row return under it")
    return_name = "1040 - Long " + "g" * in_return
    engagement = make_engagement(root, [
        RequestItem(identifier="A01", document="W-2", period=LONG_ROW_PERIOD,
                    allowed_extensions=("pdf",)),
        RequestItem(identifier=second, document="y" * 100, period=LONG_ROW_PERIOD,
                    allowed_extensions=("pdf",)),
    ], household=household, return_name=return_name)
    assert len(str(engagement)) + below == path_limit() + LONG_ROW_OVER
    return engagement


def test_set_root_answers_with_every_return_short_of_room_under_the_new_root(
    capsys, tmp_path, monkeypatch, path_setting,
):
    """Setting the root is the one moment every move passes through, so its
    reply names every return short of room under the new root, with its
    numbers, in label order - and records the root regardless."""
    from tests.builders import TEST_YEAR
    from tracker.api import ROOM_SHORT_WORDS as ROOM_SHORT
    from tracker.copies import room_for
    from tracker.manifest import RequestItem
    from tracker.settings import ENV_SETTINGS_DIR, clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    root = tmp_path / "Clients"
    fits = make_engagement(root, [RequestItem(identifier="A01", document="W-2")],
                           return_name="1040 - Fits")
    short = _a_long_row_return(root)
    room = room_for(short, load_manifest(short))
    assert room.short > 0 and room_for(fits, load_manifest(fits)).short == 0

    code, payload = run(capsys, "set-root", stdin={"root": str(root)})

    assert code == 0, payload
    assert clients_root() == root.resolve()
    [entry] = payload["short_of_room"]
    assert entry["engagement"] == f"{short.parent.parent.name} {TEST_YEAR} {short.name}"
    assert entry["short"] == room.short and entry["parks"] == room.parks
    assert entry["sentences"][0] == ROOM_SHORT.format(short=room.short)


def test_state_carries_the_returns_room_as_information_and_warns_only_what_cannot_receive(
    capsys, demo_root, path_setting,
):
    """A person opening a return sees its room without waiting for a pass:
    the six numbers, and the figure it is short by as a note on the
    return's page - **not** among the warnings (the lead's L-1: its names
    are cut to fit and everything files). Only requests that cannot
    receive at all are a warning."""
    from tracker.api import ROOM_PARKS_WORDS as ROOM_PARKS
    from tracker.api import ROOM_SHORT_WORDS as ROOM_SHORT
    from tracker.copies import room_for
    from tracker.layout import path_limit
    from tracker.manifest import RequestItem

    root = _a_deeper_root(demo_root)
    engagement = _a_long_row_return(root)
    room = room_for(engagement, load_manifest(engagement))

    state = payload_of_state(capsys, engagement)

    assert state["room"] == {"need": room.need, "least": room.least, "floor": room.floor,
                             "short": room.short, "parks": room.parks, "limit": path_limit()}
    assert room.short > 0
    assert state["room_note"] == ROOM_SHORT.format(short=room.short)
    assert ROOM_SHORT.format(short=room.short) not in state["warnings"]
    assert (ROOM_PARKS.format(count=room.parks) in state["warnings"]) == bool(room.parks)
    assert run(capsys, "list")[1]["vocab"]["room"]["short"] == ROOM_SHORT

    # A return with room: no note at all. It keeps FITS_MARGIN to spare
    # below the tightest limit its copies meet, measured, on any machine.
    from tracker.copies import _extensions_of, prepared_name_for
    from tracker.layout import PREPARED_DIR_NAME, limit_for

    fits = make_engagement(root, [RequestItem(identifier="A01", document="W-2")],
                           return_name="1040 - Fits")
    [item] = load_manifest(fits)
    spare = min(limit_for(ext) - len(str(fits / PREPARED_DIR_NAME / prepared_name_for(item, ext, set())))
                for ext in _extensions_of(item))
    assert spare >= FITS_MARGIN, spare
    assert room_for(fits, load_manifest(fits)).short == 0
    assert payload_of_state(capsys, fits)["room_note"] == ""


def test_saving_a_list_refuses_a_changed_row_whose_path_would_pass_the_limit_and_leaves_an_unchanged_one_alone(
    capsys, demo_root, path_setting,
):
    """The editor's save keeps creation's standard for the rows it changes:
    a hundred-character label typed into one row - named in the path by its
    twenty-character short name since decision 144 - is refused with
    creation's sentence and nothing is recorded; a row already past the
    limit that the person did not touch never traps a save that shortens
    another."""
    from tracker.layout import PATH_TOO_LONG

    engagement = _a_long_row_return(_a_deeper_root(demo_root))
    rows = payload_of_state(capsys, engagement)["rules"]
    by_id = {row["identifier"]: row for row in rows}

    before = ledger.path_for(engagement).read_bytes()
    typed = [{**by_id["A01"], "document": "z" * 100}, by_id["B01"]]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": typed, "engagement": {}})
    assert code == 1
    assert payload["error"].startswith(PATH_TOO_LONG.split("{")[0])
    assert "shorten the household or the return name" in payload["error"]
    assert ledger.path_for(engagement).read_bytes() == before

    shortened = [{**by_id["A01"], "document": "W2"}, by_id["B01"]]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": shortened, "engagement": {}})
    assert code == 0, payload
    assert payload["saved"]["changed"] == ["A01"]


def _a_held_row_past_the_limit(capsys, demo_root, second="B01"):
    """``_a_long_row_return`` under a deep root, and its editor rows by
    identifier: B01's canonical copy (``second``'s) is past the limit,
    A01's is not."""
    engagement = _a_long_row_return(_a_deeper_root(demo_root), second=second)
    rows = payload_of_state(capsys, engagement)["rules"]
    return engagement, {row["identifier"]: row for row in rows}


def test_a_change_of_case_alone_on_a_held_row_past_the_limit_is_the_same_row_and_is_not_measured(
    capsys, demo_root, path_setting,
):
    """P305: the path-room check matches a sent row to the stored one by the
    identifier's key (decision 160: a change of case is the same request),
    so respelling a held row past the limit by case alone is not refused -
    a case change cannot alter a path's length (bar the one pair the next
    test pins). The respelling took: the record holds ``b01``."""
    engagement, by_id = _a_held_row_past_the_limit(capsys, demo_root)
    respelt = [by_id["A01"], {**by_id["B01"], "identifier": "b01"}]

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": respelt, "engagement": {}})

    assert code == 0, payload
    assert [item.identifier for item in load_manifest(engagement)] == ["A01", "b01"]


def test_a_respelling_that_keeps_the_key_but_changes_the_length_is_measured_and_refused(
    capsys, demo_root, path_setting,
):
    """SPEC-form-inputs section 22 (F3): ``"İ".lower()`` is two code points,
    so ``İ01`` and ``i̇01`` are one key and two lengths - the one pair
    where a change of case lengthens a path. A held row past the limit
    respelt that way is a changed row, measured, and refused with creation's
    sentence; nothing is recorded."""
    from tracker.layout import PATH_TOO_LONG
    from tracker.records import identifier_key

    held, respelling = "İ01", "i̇" + "01"
    assert identifier_key(held) == identifier_key(respelling)
    assert len(respelling) == len(held) + 1
    engagement, by_id = _a_held_row_past_the_limit(capsys, demo_root, second=held)
    before = ledger.path_for(engagement).read_bytes()

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": [by_id["A01"], {**by_id[held], "identifier": respelling}],
                               "engagement": {}})

    assert code == 1 and payload["error"].startswith(PATH_TOO_LONG.split("{")[0]), payload
    assert ledger.path_for(engagement).read_bytes() == before


def test_lengthening_a_held_rows_short_title_is_measured_and_refused(
    capsys, demo_root, path_setting,
):
    """P307: a working copy is named by the short name (decision 144) - the
    typed short title or the Document's derivation - so a short title that
    differs from the stored one is a changed row, measured. A01's twenty-
    character short title makes its copy as long as B01's, past the limit."""
    from tracker.layout import PATH_TOO_LONG

    engagement, by_id = _a_held_row_past_the_limit(capsys, demo_root)
    before = ledger.path_for(engagement).read_bytes()

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": [{**by_id["A01"], "short_title": "z" * 20}, by_id["B01"]],
                               "engagement": {}})

    assert code == 1 and payload["error"].startswith(PATH_TOO_LONG.split("{")[0]), payload
    assert ledger.path_for(engagement).read_bytes() == before


def test_a_row_set_not_applicable_saves_unmeasured_and_is_measured_when_cleared(
    capsys, demo_root, path_setting,
):
    """P307: creation does not measure a Not Applicable row (``room_for``
    skips it), so setting a held row past the limit Not Applicable saves;
    clearing it makes it a request creation would have measured, as a row
    newly Asked is (decision 142), so the second save is refused."""
    from tracker.layout import PATH_TOO_LONG
    from tracker.manifest import Override

    engagement, by_id = _a_held_row_past_the_limit(capsys, demo_root)
    set_aside = {**by_id["B01"], "manual_override": Override.NOT_APPLICABLE}
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": [by_id["A01"], set_aside], "engagement": {}})
    assert code == 0, payload
    assert {item.identifier: item.manual_override for item in load_manifest(engagement)} == {
        "A01": "", "B01": Override.NOT_APPLICABLE}
    before = ledger.path_for(engagement).read_bytes()

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": [by_id["A01"], {**set_aside, "manual_override": ""}],
                               "engagement": {}})

    assert code == 1 and payload["error"].startswith(PATH_TOO_LONG.split("{")[0]), payload
    assert ledger.path_for(engagement).read_bytes() == before


def test_a_held_row_past_the_limit_whose_short_title_is_sent_back_unchanged_saves(
    capsys, demo_root, path_setting,
):
    """P307: comparing the short title does not trap a row the person did
    not touch - it is already in the room the page reports - so a save that
    sends every row back as held, and shortens only a label elsewhere, saves."""
    engagement, by_id = _a_held_row_past_the_limit(capsys, demo_root)
    assert by_id["B01"]["short_title"] == ""

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": [{**by_id["A01"], "document": "W2"}, by_id["B01"]],
                               "engagement": {}})

    assert code == 0, payload
    assert payload["saved"]["changed"] == ["A01"]


def test_a_respelt_held_row_past_the_limit_with_its_document_lengthened_is_still_refused(
    capsys, demo_root, path_setting,
):
    """P305: matching by the key does not excuse a row whose path fields
    differ; the respelt row is the same row and a changed one, so it is
    measured and refused with creation's sentence, nothing recorded."""
    from tracker.layout import PATH_TOO_LONG

    engagement, by_id = _a_held_row_past_the_limit(capsys, demo_root)
    before = ledger.path_for(engagement).read_bytes()
    lengthened = [by_id["A01"], {**by_id["B01"], "identifier": "b01", "document": "y" * 101}]

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": lengthened, "engagement": {}})

    assert code == 1 and payload["error"].startswith(PATH_TOO_LONG.split("{")[0]), payload
    assert ledger.path_for(engagement).read_bytes() == before


def test_a_new_row_past_the_limit_is_still_refused_beside_a_held_one(
    capsys, demo_root, path_setting,
):
    """P305: a row the list does not hold is measured as ever."""
    from tracker.layout import PATH_TOO_LONG

    engagement, by_id = _a_held_row_past_the_limit(capsys, demo_root)
    before = ledger.path_for(engagement).read_bytes()
    new_row = {**by_id["B01"], "identifier": "C01", "document": "z" * 100}

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": [by_id["A01"], by_id["B01"], new_row], "engagement": {}})

    assert code == 1 and payload["error"].startswith(PATH_TOO_LONG.split("{")[0]), payload
    assert ledger.path_for(engagement).read_bytes() == before


def test_a_persons_filing_and_the_hand_over_are_named_to_fit_and_refuse_only_below_the_floor(
    capsys, tmp_path, monkeypatch, path_setting,
):
    """The API half: a person's filing into a request with no room for even
    its shortest name comes back as the one error sentence, PATH_NO_ROOM,
    and nothing has moved. Since decision 168 Prepared is the only folder
    a copy is in, and it is shallower than the review folder, so a request
    is left no room only by a period as long as test_filer's LONG_PERIOD."""
    from tests.builders import LONG_PERIOD, named_page, no_room_prepared, no_room_return, root_for_a_return_of, sort
    from tracker.copies import PATH_NO_ROOM
    from tracker.layout import path_limit
    from tracker.manifest import RequestItem
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    root = root_for_a_return_of(tmp_path, no_room_return())      # 43 left in Prepared for a name
    engagement = make_engagement(root, [RequestItem(
        identifier="A01", document="W-2 Wage Statements", period=LONG_PERIOD,
        date_pattern=r"(?i)\b2025\b", allowed_extensions=("pdf",), required_keywords=("W-2",))])
    set_clients_root(root)
    text_pdf(inbox_of(engagement) / "note.pdf", named_page("A letter the list does not ask for"))
    sort(engagement)
    [parked] = [e for e in read_index(engagement) if e.decision == NEEDS_REVIEW]
    seq = next(row["seq"] for row in payload_of_state(capsys, engagement)["index"]
               if row["original_name"] == "note.pdf")
    before = sorted(str(p) for p in root.rglob("*"))

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked.pbc_location, "identifier": "A01", "seq": seq})

    assert code == 1
    assert payload["error"] == PATH_NO_ROOM.format(
        length=no_room_prepared() + 1 + len(f"A01 - {LONG_PERIOD}.pdf"), limit=path_limit(), ext=".pdf")
    assert sorted(str(p) for p in root.rglob("*")) == before


# ------------------------------------------ decision 159: the record's checkpoint ----


def test_a_person_acknowledges_a_line_another_machine_wrote(capsys, demo_root):
    """C-1 (a): the line is accepted and named until a person says they have
    looked; ``acknowledge-foreign`` is that, a writing command under the
    return's lock."""
    from tests.builders import written_elsewhere

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    written_elsewhere(engagement, ledger.new(ledger.SCANNED, **{ledger.STATUSES_KEY: {}}),
                      host="laptop-2")
    assert run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))[0] == 0     # accepted
    assert [(one.host) for one in store.foreign_lines()] == ["laptop-2"]

    code, payload = run(capsys, "acknowledge-foreign", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0 and payload["acknowledged"] == 1
    assert store.foreign_lines() == []
    assert "acknowledge-foreign" in api.WRITING_COMMANDS


def test_a_writing_command_refuses_a_root_the_checkpoint_does_not_belong_to(capsys, demo_root, tmp_path):
    """E5: every writing command holds the settings' root to this machine's
    checkpoint first; a copy of the root is refused by name before anything
    is written."""
    from tracker.settings import set_clients_root

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    copy = tmp_path / "Clients copy"
    copy.mkdir()
    set_clients_root(copy)
    code, payload = run(capsys, "create", stdin={**spec, "return_name": "Jones"})
    assert code == 1 and "record checkpoint belongs to" in payload["error"]
    assert "If the clients root really moved" in payload["error"]
    assert not where(copy, "Jones").exists()
    assert run(capsys, "settings")[0] == 0                              # reading is not refused
    set_clients_root(demo_root)


def test_a_writing_command_says_a_busy_checkpoint_as_busy_not_as_another_root(capsys, demo_root,
                                                                              monkeypatch):
    """The rebase review's SF1: the checkpoint held by another run is said
    as busy - try again - never as a root it does not belong to, and
    nothing is written."""
    import sqlite3

    from tracker import checkpoint

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    monkeypatch.setattr(checkpoint, "BUSY_TIMEOUT_MS", 100)
    holder = sqlite3.connect(checkpoint.path_for(store.store_path()), isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        code, payload = run(capsys, "create", stdin={**spec, "return_name": "Jones"})
    finally:
        holder.execute("ROLLBACK")
        holder.close()
    assert code == 1 and "is busy" in payload["error"] and "belongs to" not in payload["error"]
    assert not where(demo_root, "Jones").exists()


#: Moves that are not a write of a record or a client's file, by (module,
#: function), each with why. The after-install mover (decision 209, R9)
#: renames the tracker's own files - decision 186's move group, the record
#: checkpoint and ``recovered/`` - from beside the program into the data
#: home; it runs before any root is proved, by design, because the
#: checkpoint it moves is what the proof reads.
NOT_A_RECORD_WRITE = {("after_install", "_rename"): "the tracker's own files into the data home"}


def _writers_in_the_package() -> set[str]:
    """Every function in ``tracker/`` that reaches a write of a record or a
    client's file - ``store.record``, ``ledger.append``, a move
    (``os.rename``) or a copy (``shutil.copy2``) - by name, through the
    package's own calls, to a fixed point. Wide on purpose: a name shared by
    two functions counts as the writer's, so a guard built on it errs toward
    naming a command a writer."""
    import ast
    from pathlib import Path

    roots = {("store", "record"), ("ledger", "append"), ("os", "rename"), ("shutil", "copy2")}
    calls: dict[str, set[str]] = {}
    writes: set[str] = set()
    for path in sorted((Path(__file__).resolve().parents[1] / "tracker").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.FunctionDef):
                continue
            named = calls.setdefault(node.name, set())
            if (path.stem, node.name) in NOT_A_RECORD_WRITE:
                continue
            for call in (one for one in ast.walk(node) if isinstance(one, ast.Call)):
                func = call.func
                if isinstance(func, ast.Attribute):
                    named.add(func.attr)
                    if isinstance(func.value, ast.Name) and (func.value.id, func.attr) in roots:
                        writes.add(node.name)
                elif isinstance(func, ast.Name):
                    named.add(func.id)
                    if (path.stem, func.id) in roots:
                        writes.add(node.name)
    grew = True
    while grew:
        grew = False
        for name, called in calls.items():
            if name not in writes and called & writes:
                writes.add(name)
                grew = True
    return writes


def test_every_command_that_writes_holds_the_root_to_the_checkpoint_first():
    """Decision 159 (E5) and the port review's M2: every API command whose
    handler reaches a record's append, a move or a copy is in
    ``WRITING_COMMANDS``, so the settings' root is proved against this
    machine's record checkpoint before it writes. The writers are derived
    from the dispatch table and the package's own calls, never listed by
    hand, so a writing command a later decision adds is caught here."""
    writers = _writers_in_the_package()
    derived = {name for name, handler in api.COMMANDS.items() if handler.__name__ in writers}
    assert "accept-folder-name" in derived, "the derivation must see decision 188's accept"
    assert "mark-shared" in derived, "the derivation must see the sharing command's write"
    assert derived <= api.WRITING_COMMANDS, sorted(derived - api.WRITING_COMMANDS)
    assert api.WRITING_COMMANDS <= set(api.COMMANDS)


def test_accepting_a_folders_name_is_refused_on_a_root_the_checkpoint_does_not_belong_to(
        capsys, demo_root, tmp_path):
    """The port review's M2: decision 188's accept writes the household's and
    its returns' records, so it is held to this machine's record checkpoint
    like every writing command - on a copy of the root it is refused by name
    and writes nothing."""
    import shutil

    from tracker.settings import set_clients_root

    engagement = _a_renamed_household(capsys, demo_root)
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0                     # claims demo_root
    copy = tmp_path / "Clients copy"
    shutil.copytree(demo_root, copy)
    set_clients_root(copy)
    try:
        moved = copy / engagement.relative_to(demo_root)
        pause = run(capsys, "state", api.ENGAGEMENT_FLAG, str(moved))[1]["household"]["pause"]
        household = moved.parent.parent
        before = len(ledger.read_events(household))
        code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, pause["engagement"],
                            stdin={"seq": pause["seq"], "scope": "household"})
        assert code == 1 and "record checkpoint belongs to" in payload["error"]
        assert len(ledger.read_events(household)) == before
    finally:
        set_clients_root(demo_root)
