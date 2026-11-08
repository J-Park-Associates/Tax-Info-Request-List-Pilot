"""Tests for tracker/runner.py: Run now, a pass that is watched and stoppable, and a scheduled pass off Windows.

Run now (decision 203), a pass watched and stoppable (decision 193) and a scheduled pass off Windows that ends itself
(SPEC-mac R26, R30).

Split from ``tests/test_runner.py`` by SPEC-architecture-p5 P5.14 (E-3), by the banners the old file kept its
sections under, each test moved byte for byte with its section, so that each family runs as its own process
(Jason, 2026-09-29) and an affected-tests run reaches only the family a change touched. The map owns this file
as ``tracker/runner.py``'s test by its name (decision P350). What more than one family reads is
``tests/passes.py``'s, because a test file may not import another (``tests/test_suite_shape.py``).
"""

import datetime as dt
import json
from pathlib import Path

import pytest

import tracker.runner as runner_module
from tests import passes
from tests.builders import make_engagement
from tests.passes import (
    FRIDAY,
    SATURDAY,
    SUNDAY,
    _lines,
    _page,
    _run_now,
    _settings_for,
    _the_scheduled_job,
    _two_households,
    a_pass,
    build_engagement,
    pass_on,
)
from tests.samples import DEMO_ITEMS, YEAR, text_pdf
from tracker import ledger, run_log, status_page, store
from tracker.index import read_index
from tracker.layout import household_of, inbox_of, originals_of
from tracker.manifest import EngagementInfo, RequestItem
from tracker.registry import Engagement, discover_engagements, engagement_from
from tracker.reminder import DRAFT_FILENAME
from tracker.run_log import log_path
from tracker.runner import (
    CODE_PAGE_NOT_WRITTEN,
    CODE_PASS_STOPPED,
    LOG_FILENAME,
    RECORD_UNREADABLE,
    REMINDERS_ALWAYS,
    REMINDERS_AUTO,
    REMINDERS_NEVER,
    SETTINGS_FLAG,
    STATUS_PAGE_FILENAME,
    main,
    run_household,
    run_registry,
    should_draft,
)

#: The sample pile, built once per session: a fixture of ``tests/passes.py``, named here
#: so every claim below can ask for it.
samples = passes.samples

#: A fixture of ``tests/passes.py``, named here so every claim below can ask for it.
stamped_on = passes.stamped_on


# --------------------------------------------------- Run now (decision 203) ----


def test_the_household_flag_passes_through_the_door(tmp_path, samples, monkeypatch, capsys):
    """Decision 203, R2: the household is named, never guessed, and the
    runner checks it through the door as any path from outside. A return's
    folder, the client tree's household folder, a path outside the root, a
    ``..`` climb, a stopped household and a value that looks like a flag
    are each refused in one envelope: nothing leaves any inbox and no
    ``pass started`` line is written."""
    from tracker.layout import client_household_dir
    from tracker.progress import PROGRESS_KEY
    from tracker.runner import HOUSEHOLD_FLAG, LOG_FLAG, PROGRESS_LINES_FLAG

    root = tmp_path / "root"
    first = build_engagement(root, samples, household="Alder Household", name="Alder TY2025")
    build_engagement(root, samples, household="Birch Household", name="Birch TY2025")
    settings = _settings_for(root, monkeypatch)
    household = household_of(first.path)
    # Birch's record is taken away: a household the walk stops (SPEC-162).
    birch = household.parent / "Birch Household"
    ledger.path_for(birch).unlink()
    waiting = {one: sorted(p.name for p in inbox_of(one).iterdir())
               for one in (first.path, birch / str(YEAR) / "Birch TY2025")}

    for value in (first.path, client_household_dir(root, "Alder Household"), tmp_path / "elsewhere",
                  household / ".." / "Birch Household" / ".." / ".." / "..", birch, "--dry-run", ""):
        capsys.readouterr()
        code = main([SETTINGS_FLAG, str(settings), LOG_FLAG, "--reminders", REMINDERS_NEVER,
                     PROGRESS_LINES_FLAG, f"{HOUSEHOLD_FLAG}={value}"])
        [said] = _lines(capsys.readouterr().out)
        assert code == 1, value
        assert PROGRESS_KEY not in said and said["failure"]["kind"] == "refused", value
        assert said["error"] == said["failure"]["sentence"] and said["error"], value
    for folder, names in waiting.items():
        assert sorted(p.name for p in inbox_of(folder).iterdir()) == names
    assert not (root / LOG_FILENAME).exists(), "no pass started"
    capsys.readouterr()
    main([SETTINGS_FLAG, str(settings), LOG_FLAG, PROGRESS_LINES_FLAG, f"{HOUSEHOLD_FLAG}="])
    from tracker.runner import NO_HOUSEHOLD_NAMED
    assert _lines(capsys.readouterr().out)[-1]["error"] == NO_HOUSEHOLD_NAMED, "empty is never the practice"


def test_run_now_arguments_are_the_schedules_plus_three(tmp_path):
    """Decision 203, R1 and R8: Run now's command line is the scheduled
    job's, in its order, plus no draft, the progress lines and the one
    household - read by the same parser to the same pass otherwise."""
    from tracker.runner import LOG_FLAG, _parser, run_now_arguments
    from tracker.scheduling import quote_argument, runner_arguments

    settings = tmp_path / "settings folder"
    household = tmp_path / "-Odd Household"
    scheduled = [SETTINGS_FLAG, str(settings), LOG_FLAG]
    run_now = run_now_arguments(settings, household)
    assert run_now[:3] == scheduled
    assert runner_arguments(settings).endswith(f"{SETTINGS_FLAG} {quote_argument(str(settings))} {LOG_FLAG}")
    one, other = vars(_parser().parse_args(scheduled)), vars(_parser().parse_args(run_now))
    assert {key for key in one if one[key] != other[key]} == {"household", "reminders", "progress_lines"}
    assert other["household"] == str(household), "a folder beginning with - is a value"
    assert other["reminders"] == REMINDERS_NEVER and other["progress_lines"] is True


def test_run_now_leaves_the_schedules_log_line_and_page(tmp_path, tmp_path_factory, samples, monkeypatch,
                                                       capsys):
    """Decision 203, F-M-3: two identical trees, one sorted by the scheduled
    job's command line and one by Run now's. With the stamps and the pass
    id taken out, the run logs match line for line - ``pass started`` in
    both - and so do the practice pages' rows."""
    import re

    from tracker.run_log import log_path
    from tracker.runner import LOG_FLAG

    # The second tree outside ``tmp_path``: the same household by name is a
    # second practice, with a store of its own, which the checks made after
    # every test (plugin_agreement) do not hold to the first's.
    scheduled_root = tmp_path / "scheduled" / "root"
    run_now_root = tmp_path_factory.mktemp("run-now") / "root"
    build_engagement(scheduled_root, samples)
    settings = _settings_for(scheduled_root, monkeypatch)
    assert main([SETTINGS_FLAG, str(settings), LOG_FLAG, "--reminders", REMINDERS_NEVER]) == 0
    store.close()
    # The run log is the data home's (decision 186), so each pass's is read
    # as it ends, and the first set aside before the second is written.
    scheduled_log = log_path().read_text(encoding="utf-8")
    log_path().unlink()
    monkeypatch.setenv(store.ENV_STORE, str(run_now_root.parent / store.STORE_FILENAME))
    run_now_return = build_engagement(run_now_root, samples)
    code, lines = _run_now(run_now_root, household_of(run_now_return.path), monkeypatch, capsys)
    assert code == 0 and lines[-1]["exit"] == 0, lines[-1]
    run_now_log = log_path().read_text(encoding="utf-8")

    def plain(text: str, root: Path) -> list[str]:
        text = text.replace(str(root), "<root>")
        text = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?", "<when>", text)
        return text.splitlines()

    logs = [plain(scheduled_log, scheduled_root), plain(run_now_log, run_now_root)]
    assert logs[0] == logs[1]
    assert logs[0][0] == "[<when>] pass started"

    def rows(root: Path) -> list[str]:
        page = (root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
        return plain("\n".join(re.findall(r"<tr>.*?</tr>", page, flags=re.S)), root)

    assert rows(scheduled_root) and rows(scheduled_root) == rows(run_now_root)


def test_progress_lines_end_with_one_final_line_after_the_page(tmp_path, samples, monkeypatch, capsys):
    """Decision 203, R5: Run now's stdout is 193's protocol - progress
    lines, then one final line without ``progress``, carrying the exit code,
    every return of the household and the pass's warnings. A page that
    could not be written is one of them, and the pass is red."""
    import tracker.runner as runner
    from tracker.progress import PROGRESS_KEY
    from tracker.runner import PAGE_NOT_WRITTEN

    root = tmp_path / "root"
    engagement = build_engagement(root, samples)
    code, lines = _run_now(root, household_of(engagement.path), monkeypatch, capsys)
    assert code == 0
    assert all(PROGRESS_KEY in line for line in lines[:-1]) and PROGRESS_KEY not in lines[-1]
    said = [line[PROGRESS_KEY] for line in lines[:-1]]
    assert said[0]["event"] == "started" and said[0]["households"] == 1
    assert said[-1]["event"] == "ended" and said[-1]["outcome"] == "finished"
    final = lines[-1]
    assert final["exit"] == 0 and final["pass"] == said[0]["pass"] and final["warnings"] == []
    [ran] = final["runs"]
    assert ran["label"] == engagement.label and ran["path"] == str(engagement.path)
    assert ran["filed"] >= 1 and ran["ok"] and ran["cancelled"] is False
    assert ran["code"] == "", "a good run has no failure kind"

    def refused(*args, **kwargs):
        raise PermissionError("a sync client holds it")

    monkeypatch.setattr(runner, "write_status_page", refused)
    code, lines = _run_now(root, household_of(engagement.path), monkeypatch, capsys)
    assert code == 1 and lines[-1]["exit"] == 1
    assert PAGE_NOT_WRITTEN.format(kind="PermissionError") in lines[-1]["pass_warnings"]


def test_the_final_line_carries_the_kind_of_a_failed_run_and_no_path(tmp_path, samples, monkeypatch, capsys):
    """Ruling 29: the app says a short reason after "Sort Failed" chosen by
    the run's ``code`` - the kind the runner already logs. A household whose
    client folder is gone fails with that kind, and the code is a slug, never
    a sentence or a path."""
    import shutil

    from tracker.layout import client_household_dir

    root = tmp_path / "root"
    engagement = build_engagement(root, samples)
    _run_now(root, household_of(engagement.path), monkeypatch, capsys)    # it has had its client folder
    shutil.rmtree(client_household_dir(root, household_of(engagement.path).name))
    code, lines = _run_now(root, household_of(engagement.path), monkeypatch, capsys)
    [ran] = lines[-1]["runs"]
    assert ran["error"] and ran["code"] == "client-folder-missing"
    assert "/" not in ran["code"] and "\\" not in ran["code"]


def test_a_pass_whose_watcher_is_gone_stops_at_the_next_file(tmp_path, samples, monkeypatch, capsys):
    """Decision 203, R6: the app that started the pass closed, and its pipe
    broke on the second file. The pass stops there, as a person's Stop
    would: the first file is recorded, the rest wait in the inbox, the
    return says :data:`PASS_APP_CLOSED`, its lock is let go, and the run log
    and the page are written."""
    import json

    import tracker.runner as runner
    from tracker.locking import lock_status
    from tracker.run_log import log_path
    from tracker.runner import PASS_APP_CLOSED, run_now_arguments

    root = tmp_path / "root"
    engagement = build_engagement(root, samples, drops=(f"W-2 John Smith {YEAR}.pdf",
                                                        "1099-INT First National.pdf",
                                                        "Form 1098 Mortgage Interest.pdf"))
    drops = {f"W-2 John Smith {YEAR}.pdf", "1099-INT First National.pdf",
             "Form 1098 Mortgage Interest.pdf"}
    files: list[str] = []

    printed: list[str] = []

    def emit(text: str) -> None:
        printed.append(text)
        if '"event": "file"' in text and '"step": "sort"' in text:
            files.append(text)
            if len(files) >= 2:
                raise BrokenPipeError(32, "Broken pipe")

    monkeypatch.setattr(runner, "_emit_line", emit)
    settings = _settings_for(root, monkeypatch)
    code = main(run_now_arguments(settings, household_of(engagement.path)))
    capsys.readouterr()
    assert len(files) == 2, "no progress line is printed once the pipe broke"
    [ran] = json.loads(printed[-1])["runs"]
    assert ran["cancelled"] is True and PASS_APP_CLOSED.format(n=1) in ran["warnings"]
    assert printed[-2] is files[-1], "after the break, only the final line is tried"
    run = engagement_from(engagement.path)
    left = drops & {p.name for p in inbox_of(engagement.path).iterdir()}
    assert len(left) == 2, "the first file was taken, the rest wait"
    assert (root / STATUS_PAGE_FILENAME).is_file()
    log_text = log_path().read_text(encoding="utf-8")
    assert "pass started" in log_text and "reminders=never" in log_text
    assert lock_status(run.path) is None, "its lock was let go"
    assert code in (0, 1)


def test_a_pass_whose_app_closed_says_so_in_the_run_log_and_on_the_page_and_leaves_the_rest_for_the_next_pass(
        tmp_path, samples, monkeypatch, capsys):
    """Decision 203's review, M1: the app that would have shown the sentence
    is gone, and a return's warnings are only a count in the log and a
    number on the page - so the pass says it as its own: its code in the run
    log, which names no client (decision 186), and its sentence on the
    page. The next pass files what waited."""
    import tracker.runner as runner
    from tracker.run_log import log_path
    from tracker.runner import CODE_PASS_APP_CLOSED, PASS_APP_CLOSED, run_now_arguments

    root = tmp_path / "root"
    drops = (f"W-2 John Smith {YEAR}.pdf", "1099-INT First National.pdf", "Form 1098 Mortgage Interest.pdf")
    engagement = build_engagement(root, samples, drops=drops)
    sorted_ = []

    def emit(text: str) -> None:
        if '"event": "file"' in text and '"step": "sort"' in text:
            sorted_.append(text)
            if len(sorted_) >= 2:
                raise BrokenPipeError(32, "Broken pipe")

    monkeypatch.setattr(runner, "_emit_line", emit)
    settings = _settings_for(root, monkeypatch)
    main(run_now_arguments(settings, household_of(engagement.path)))
    said = PASS_APP_CLOSED.format(n=1)
    logged = log_path().read_text(encoding="utf-8")
    assert f"{CODE_PASS_APP_CLOSED}=1" in logged and said not in logged
    assert said in _page(root)
    assert set(drops) & {p.name for p in inbox_of(engagement.path).iterdir()}, "the rest waited"

    monkeypatch.undo()
    _settings_for(root, monkeypatch)
    main([SETTINGS_FLAG, str(settings), "--reminders", REMINDERS_NEVER])
    capsys.readouterr()
    assert not set(drops) & {p.name for p in inbox_of(engagement.path).iterdir()}, "the next pass took them"


def test_an_injected_database_error_in_one_household_leaves_the_others_processed_and_the_page_written(
    tmp_path, samples, monkeypatch, capsys,
):
    """The security council's proof line (A-9, D-2): the database refuses
    one household's pre-checks. That household carries the store's own
    class and code; the other is sorted and scanned; the page is written."""
    import tracker.runner as runner

    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    first, second = _two_households(root, samples)
    real = runner.load_manifest

    def refused_for_the_first(folder, *args, **kwargs):
        if folder == first.path:
            store.connect().execute("SELECT * FROM a_table_the_store_never_had")
        return real(folder, *args, **kwargs)

    for module in (runner, status_page):
        monkeypatch.setattr(module, "load_manifest", refused_for_the_first)

    assert main([str(root), "--reminders", REMINDERS_NEVER]) == 1
    page = _page(root)
    said = RECORD_UNREADABLE.format(problem=store.STORE_UNAVAILABLE.format(code="SQLITE_ERROR"))
    assert f"{first.label}: {said}" in page
    assert "a_table_the_store_never_had" not in page, "the engine's text is never quoted"
    assert [row.decision for row in read_index(second.path)] == ["Filed"]
    assert "Birch TY2025" in capsys.readouterr().out


def test_a_run_log_that_cannot_be_written_still_leaves_the_page_and_says_so(
    tmp_path, samples, monkeypatch, capsys,
):
    from tracker.runner import LOG_NOT_WRITTEN

    root = tmp_path / "Clients"
    build_engagement(root, samples)
    a_folder_where_the_log_goes = tmp_path / "logs"
    a_folder_where_the_log_goes.mkdir()

    code = _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER,
                              "--log", str(a_folder_where_the_log_goes))

    assert code == 1, "a log that could not be written is a red run"
    head = LOG_NOT_WRITTEN.split("(")[0]
    assert head in _page(root)
    assert head in capsys.readouterr().out


def test_a_pass_whose_own_code_raises_still_writes_its_log_and_its_page(
    tmp_path, samples, monkeypatch, capsys,
):
    """D-2: the runner's own code - not a household's - raises. What
    finished is logged and drawn, the page names the stop by its class,
    and the exit code is not 0."""
    import tracker.runner as runner
    from tracker.runner import PASS_STOPPED

    root = tmp_path / "Clients"
    build_engagement(root, samples)

    asked = []

    def fails_at_the_end_of_the_pass():
        asked.append(True)
        if len(asked) == 2:          # the first ask starts the count; the second ends the pass
            raise KeyError("not a sentence anybody should read")
        return ""

    monkeypatch.setattr(runner, "reader_start_warning", fails_at_the_end_of_the_pass)

    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 1
    said = PASS_STOPPED.format(kind="KeyError")
    assert said in _page(root)
    logged = log_path().read_text(encoding="utf-8")
    assert f"{CODE_PASS_STOPPED}=1" in logged
    assert "not a sentence" not in _page(root)
    assert " ok=1 " in logged and " filed=1 " in logged, "the household that finished is logged"
    capsys.readouterr()


#: A fabricated OS error's path, shaped like a client's inbox (decision 190).
A_CLIENT_PATH = "/Clients/Test Household/Drop files here/W2.pdf"


def _refused_with_a_client_path():
    import errno

    return PermissionError(errno.EACCES, "Permission denied", A_CLIENT_PATH)


def _says_no_client_path(**said: str) -> None:
    for where, text in said.items():
        assert A_CLIENT_PATH not in text and "Drop files here/W2.pdf" not in text, (
            f"a client's folder reached {where}: {text}")


def test_a_record_the_registry_cannot_read_is_said_by_its_class_never_its_path(
        tmp_path, samples, monkeypatch, capsys):
    """A record the registry cannot read for a reason of the disk's is the
    return's problem by its class and errno alone: the OS error's message is
    a client's folder, and neither the problem, the page, the run log nor
    the console quotes it (decision 190, the review's S1)."""
    import tracker.registry as registry
    from tracker.registry import engagement_from

    root = tmp_path / "Clients"
    engagement = build_engagement(root, samples)
    real = registry.load_engagement_info

    def refused(folder, *args, **kwargs):
        if Path(folder).name == engagement.path.name:
            raise _refused_with_a_client_path()
        return real(folder, *args, **kwargs)

    monkeypatch.setattr(registry, "load_engagement_info", refused)

    found = engagement_from(engagement.path)
    assert found.problem == "PermissionError (EACCES)"
    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 1
    page = _page(root)
    assert RECORD_UNREADABLE.format(problem="PermissionError (EACCES)") in page
    printed = capsys.readouterr()
    _says_no_client_path(problem=found.problem, page=page, stdout=printed.out, stderr=printed.err,
                         run_log=log_path().read_text(encoding="utf-8"))


def test_a_feed_list_the_disk_refuses_is_said_by_its_class_never_its_path(tmp_path, samples, monkeypatch):
    """The feed list's warning, which reaches the page and the run log,
    names a disk's refusal by its class and errno, never the message that
    carries a client's folder (decision 190, the review's S1)."""
    import tracker.runner as runner
    from tracker.runner import FEEDS_UNREAD

    def refused(*_args, **_kwargs):
        raise _refused_with_a_client_path()

    monkeypatch.setattr(runner, "load_household_info", refused)
    found, said = runner._feeds_of(tmp_path / "Test Household", YEAR, None)
    assert found == [] and said == [FEEDS_UNREAD.format(error="PermissionError (EACCES)")]
    _says_no_client_path(warning=said[0])


def test_a_pass_that_stops_prints_no_trace_and_no_message(tmp_path, samples, monkeypatch, capsys, caplog):
    """The pass-level catch says the stop by its class; the trace, which
    quotes the message, goes to the debug log alone - one rule for where a
    trace goes (decision 190, the review's S2)."""
    import logging

    import tracker.runner as runner
    from tracker.errors import DEBUG_LOGGER
    from tracker.runner import PASS_STOPPED

    root = tmp_path / "Clients"
    build_engagement(root, samples)
    asked = []

    def fails_at_the_end_of_the_pass():
        asked.append(True)
        if len(asked) == 2:
            raise _refused_with_a_client_path()
        return ""

    monkeypatch.setattr(runner, "reader_start_warning", fails_at_the_end_of_the_pass)
    with caplog.at_level(logging.DEBUG):
        assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 1
    assert PASS_STOPPED.format(kind="PermissionError (EACCES)") in _page(root)
    logged = [record for record in caplog.records if record.name != DEBUG_LOGGER]
    assert not any(record.exc_info for record in logged), "a trace was printed"
    printed = capsys.readouterr()
    assert "Traceback" not in printed.err
    _says_no_client_path(page=_page(root), stdout=printed.out, stderr=printed.err,
                         logged="\n".join(record.getMessage() for record in logged),
                         run_log=log_path().read_text(encoding="utf-8"))

def test_a_household_that_stops_is_said_by_its_class_never_its_message(
        tmp_path, samples, monkeypatch, capsys):
    """A household's surprise costs its returns, and each carries the class
    and code alone: an OSError's text names a client's folder, and neither
    the page nor the run log quotes it (security principle 7; the review's
    S2)."""
    import errno

    import tracker.runner as runner

    root = tmp_path / "Clients"
    engagement = build_engagement(root, samples)
    where = str(engagement.path / "a file the disk refused.pdf")

    def refused(*args, **kwargs):
        raise OSError(errno.EIO, "Input/output error", where)

    monkeypatch.setattr(runner, "_sort_step", refused)

    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 1
    log_text = log_path().read_text(encoding="utf-8")
    assert "crashed:OSError=1" in log_text and "OSError (EIO)" in _page(root)
    for said in (log_text, _page(root)):
        assert where not in said and "a file the disk refused" not in said
    capsys.readouterr()


def test_a_page_that_cannot_be_written_is_said_in_the_log_and_fails_the_run(
        tmp_path, samples, monkeypatch, capsys):
    """The page is how a person finds out; one stuck on yesterday must not
    look green (security principle 6; the review's S3). A page that cannot
    be written is said in the run log by its class alone - in the one
    spelling, errors.error_class, with its errno (decision 190, the
    review's M1) - and the pass exits 1."""
    import tracker.runner as runner
    from tracker.runner import PAGE_NOT_WRITTEN

    root = tmp_path / "Clients"
    build_engagement(root, samples)

    def cannot_write(*args, **kwargs):
        raise PermissionError(13, "Permission denied", str(root / "a client's folder"))

    monkeypatch.setattr(runner, "write_status_page", cannot_write)

    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 1
    log_text = log_path().read_text(encoding="utf-8")
    assert f"codes {CODE_PAGE_NOT_WRITTEN}=1" in log_text
    assert "a client's folder" not in log_text
    assert PAGE_NOT_WRITTEN.format(kind="PermissionError (EACCES)") in capsys.readouterr().out
    capsys.readouterr()


def test_a_first_draft_missed_on_its_day_is_drafted_on_the_next_run():
    """SPEC-161 A-F8: a return set up before a draft day the machine was
    off for is owed its first draft on the next run, not a week later; one
    set up since the last draft day still waits for its first."""
    engagement = Engagement(path=Path("/x"))
    set_up_before = SATURDAY - dt.timedelta(days=3)
    set_up_after = SATURDAY + dt.timedelta(days=1)
    assert should_draft(engagement, SUNDAY, REMINDERS_AUTO, created=set_up_before) is True
    assert should_draft(engagement, SUNDAY, REMINDERS_AUTO, created=SATURDAY) is True
    assert should_draft(engagement, SUNDAY, REMINDERS_AUTO, created=set_up_after) is False
    assert should_draft(engagement, FRIDAY, REMINDERS_AUTO, created=set_up_before) is False


def test_a_first_draft_missed_on_its_day_is_drafted_by_the_next_pass(tmp_path, samples, stamped_on):
    stamped_on(SATURDAY - dt.timedelta(days=3))          # the day the return was set up
    engagement = build_engagement(tmp_path, samples)
    run = pass_on(stamped_on, engagement, SUNDAY)          # the Saturday went by, machine off
    assert run.drafted == engagement.path / DRAFT_FILENAME


def test_reminders_no_still_wins_over_a_missed_first_draft():
    quiet = Engagement(path=Path("/x"), info=EngagementInfo(reminders=False))
    before = SATURDAY - dt.timedelta(days=3)
    assert should_draft(quiet, SUNDAY, REMINDERS_AUTO, created=before) is False
    assert should_draft(Engagement(path=Path("/x")), SUNDAY, REMINDERS_NEVER, created=before) is False


_KILLED_ON_THE_THIRD_READING = """
import os, sys
from tracker import content_check
from tracker.registry import discover_engagements
from tracker.runner import run_registry

content_check.READ_IN_A_CHILD = False
real, readings = content_check.extract, []

def extract(path, **kwargs):
    readings.append(path)
    if len(readings) == 3:
        os._exit(9)            # a hard kill: no finally, no atexit
    return real(path, **kwargs)

content_check.extract = extract
run_registry(discover_engagements(sys.argv[1]), reminders="never")
"""


def test_a_pass_killed_mid_sort_keeps_every_reading_it_finished(tmp_path, monkeypatch):
    """SPEC-161 ruling 1 (E-4): a pass killed after the second of five
    readings - Task Scheduler's limit, the app's kill - kept both, so the
    next pass reads only the last three."""
    import subprocess
    import sys

    from tracker import content_check

    folder = make_engagement(tmp_path, [RequestItem(identifier="A01", document="W-2")],
                             household="Cedar Household", return_name="Cedar TY2025")
    for n in range(1, 6):
        text_pdf(inbox_of(folder) / f"statement {n}.pdf", [f"Brokerage letter number {n}"], style="padded")
    store.close()

    repo = Path(__file__).resolve().parents[1]
    killed = subprocess.run([sys.executable, "-c", _KILLED_ON_THE_THIRD_READING, str(tmp_path)],
                            cwd=repo, capture_output=True, text=True, timeout=240)
    assert killed.returncode == 9, killed.stderr

    real, readings = content_check.extract, []

    def counted(path, **kwargs):
        readings.append(Path(path).name)
        return real(path, **kwargs)

    monkeypatch.setattr(content_check, "extract", counted)
    run_registry(discover_engagements(tmp_path), reminders=REMINDERS_NEVER)
    assert sorted(readings) == ["statement 3.pdf", "statement 4.pdf", "statement 5.pdf"]


# ------------------------------------ watched, and stoppable (decision 193) ----


class StopAt:
    """A Watch that has a person ask the pass to stop just as it comes to
    the ``at``-th file of ``step`` - after it finished the one before."""

    def __init__(self, folder, step="sort", at=2, emit=None):
        from tracker.progress import Watch, ask_to_stop

        outer = self
        self.seen: list[dict] = []

        class _Watch(Watch):
            def say(self, event, **fields):
                super().say(event, **fields)
                outer.seen.append({"event": event, **fields})
                if event == "file" and fields.get("step") == step:
                    if sum(1 for one in outer.seen
                           if one["event"] == "file" and one.get("step") == step) == at:
                        assert ask_to_stop(self.folder, self.pass_id)

        self.watch = _Watch(folder, emit=emit or (lambda line: None), limit_seconds=60)


THREE_DROPS = (f"W-2 John Smith {YEAR}.pdf", "Form 1098 Mortgage Interest.pdf", "1099-INT First National.pdf")


def test_a_stop_between_files_ends_the_sort_at_the_next_file_and_the_next_pass_sorts_the_rest(
        tmp_path, samples):
    from tracker.runner import PASS_CANCELLED

    engagement = build_engagement(tmp_path / "Clients", samples, drops=THREE_DROPS)
    inbox = inbox_of(engagement.path)
    stop = StopAt(tmp_path / "data")

    run = a_pass(engagement, today=FRIDAY, reminders=REMINDERS_NEVER, watch=stop.watch)

    assert run.cancelled and not run.out_of_time and run.ok
    assert PASS_CANCELLED.format(n=1) in run.warnings
    assert run.filed + run.review == 1
    assert len([p for p in inbox.iterdir() if p.name in THREE_DROPS]) == 2, "two wait in the inbox"
    assert len(read_index(engagement.path)) == 1

    again = a_pass(engagement, today=FRIDAY, reminders=REMINDERS_NEVER)
    assert again.ok and not again.cancelled
    assert not [p for p in inbox.iterdir() if p.name in THREE_DROPS]
    rows = read_index(engagement.path)
    assert sorted(Path(row.original_name).name for row in rows) == sorted(THREE_DROPS)
    originals = originals_of(engagement.path)
    assert sorted(p.name for p in originals.iterdir() if p.is_file()) == sorted(THREE_DROPS), \
        "every original once, none missing and no stray"


def test_a_stopped_scan_keeps_the_status_the_record_holds_for_the_rest(tmp_path, samples):
    from tracker.manifest import load_manifest
    from tracker.runner import PASS_CANCELLED

    engagement = build_engagement(tmp_path / "Clients", samples, drops=THREE_DROPS)
    first = a_pass(engagement, today=FRIDAY, reminders=REMINDERS_NEVER)
    assert first.ok
    held = dict(first.statuses)
    before = {item.identifier: item.status for item in load_manifest(engagement.path)}
    # Nothing kept: every request that holds a document needs a new judgment.
    conn = store.connect()
    with conn:
        conn.execute(f"DELETE FROM {store.VERDICTS_TABLE}")
        conn.execute(f"DELETE FROM {store.FILE_MEMOS_TABLE}")
    stop = StopAt(tmp_path / "data", step="scan", at=1)

    run = a_pass(engagement, today=FRIDAY, reminders=REMINDERS_NEVER, watch=stop.watch)

    assert run.cancelled and PASS_CANCELLED.format(n=0) in run.warnings
    after = {item.identifier: item.status for item in load_manifest(engagement.path)}
    assert after == before, "a request the stop did not reach keeps the status the record holds"
    assert held


def test_a_stopped_household_says_so_and_is_not_drafted(tmp_path, samples):
    from tracker.pass_order import WHY_CANCELLED, _why_not_served
    from tracker.runner import CANCELLED_NO_DRAFT

    engagement = build_engagement(tmp_path / "Clients", samples, drops=THREE_DROPS)
    run = a_pass(engagement, today=SATURDAY, reminders=REMINDERS_ALWAYS,
                 watch=StopAt(tmp_path / "data").watch)
    assert run.cancelled and run.drafted is None and run.draft_note == CANCELLED_NO_DRAFT
    assert not (engagement.path / DRAFT_FILENAME).exists()
    assert _why_not_served([run]) == WHY_CANCELLED


def test_the_scheduled_pass_fills_the_progress_file_and_prints_no_progress_line(
        tmp_path, samples, capsys, monkeypatch):
    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    from tracker.progress import PROGRESS_KEY, Watch

    build_engagement(root, samples)
    made: list[Watch] = []
    kept: list[dict] = []

    class Spied(Watch):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            made.append(self)

        def _keep(self, said):
            super()._keep(said)
            kept.append(said)

    monkeypatch.setattr(runner_module, "Watch", Spied)
    assert main([str(root), "--date", FRIDAY.isoformat(), "--reminders", "never"]) == 0
    [watch] = made
    assert watch.emit is None and not watch.stoppable
    assert watch.folder == store.store_path().parent
    assert {"started", "household", "file", "ended"} <= {said["event"] for said in kept}
    assert f'"{PROGRESS_KEY}"' not in capsys.readouterr().out
    assert not list((watch.folder / "passes").glob("*.json")), "gone when the pass ends"


def test_run_engagement_says_an_unexpected_error_by_class_only(tmp_path, samples, monkeypatch, caplog):
    from tracker.runner import run_engagement

    engagement = build_engagement(tmp_path, samples, drops=())

    def surprise(*args, **kwargs):
        raise ValueError(f"a fabricated message naming {engagement.path}")

    monkeypatch.setattr(runner_module, "scan_engagement", surprise)
    run = run_engagement(engagement, reminders=REMINDERS_NEVER)
    assert run.error == "ValueError"
    assert "fabricated" not in run.error and "fabricated" not in run.draft_note
    assert "fabricated message" in caplog.text        # the whole of it, for the log only


def test_a_hold_older_than_seven_days_is_on_the_page(tmp_path, samples, monkeypatch):
    from tests.builders import seed_statuses
    from tracker import reasons
    from tracker.locking import engagement_lock
    from tracker.manifest import Status, StatusUpdate
    from tracker.reminder import HELD_TOO_LONG, HELD_WARN_DAYS
    from tracker.runner import EngagementRun, RunReport, _draft_step, format_report

    engagement = build_engagement(tmp_path, samples, drops=())
    identifier = DEMO_ITEMS[0].identifier
    seed_statuses(engagement.path, {identifier: StatusUpdate(
        status=Status.FAILED, file_count=1,
        validation_notes="x.pdf: " + reasons.WRONG_DOCUMENT.format(listed="'1098'"))})
    days = HELD_WARN_DAYS + 2
    monkeypatch.setattr(runner_module, "created_on", lambda path: SATURDAY - dt.timedelta(days=days))
    run = EngagementRun(engagement=engagement)
    with engagement_lock(engagement.path):
        _draft_step(run, dry_run=False, today=SATURDAY)
    said = HELD_TOO_LONG.format(days=days)
    assert run.held and said in run.warnings
    # The page counts it with the run's warnings; the run log says it.
    assert said in format_report(RunReport(today=SATURDAY, runs=[run]))

    fresh = EngagementRun(engagement=engagement)
    monkeypatch.setattr(runner_module, "created_on", lambda path: SATURDAY)
    with engagement_lock(engagement.path):
        _draft_step(fresh, dry_run=False, today=SATURDAY)
    assert fresh.held and not fresh.warnings


def test_a_rolled_from_naming_nothing_is_on_the_page(tmp_path, samples):
    from tracker.registry import ROLLED_FROM_UNMATCHED, mark_superseded
    from tracker.runner import RunReport, format_report

    engagement = build_engagement(tmp_path, samples, drops=(), rolled_from="1040 - Nobody Sample")
    runs = run_household(household_of(engagement.path), mark_superseded([engagement]),
                         today=FRIDAY, reminders=REMINDERS_NEVER,
                         registry=discover_engagements(tmp_path))
    said = ROLLED_FROM_UNMATCHED.format(rolled_from="1040 - Nobody Sample")
    [run] = runs
    assert said in run.warnings
    # The page counts it with the run's warnings; the run log says it.
    assert said in format_report(RunReport(today=FRIDAY, runs=runs))


# ------------------------------- a scheduled pass off Windows ends itself (SPEC-mac R26, R30) ----


def _the_scheduled_args(*extra):
    return [runner_module.SETTINGS_FLAG, "<settings>", runner_module.LOG_FLAG, *extra]


def test_only_a_scheduled_pass_off_windows_limits_itself(monkeypatch):
    """R26 is the scheduled job's shape - the settings folder, no root, no household,
    not a dry run - on any system but Windows, whose Task Scheduler kills the job at
    its own limit. Run now (the app can Stop it), a dry run and a typed root are not it."""
    from tracker import settings
    from tracker.runner import _limited_from, _parser

    monkeypatch.setattr(runner_module, "wall_clock", lambda: 1234.5)

    def shaped(*args):
        return _limited_from(_parser().parse_args(args))

    for system, expected in (("posix", 1234.5), ("darwin", 1234.5), ("nt", None)):
        monkeypatch.setattr(settings, "host_system", lambda system=system: system)
        assert shaped(*_the_scheduled_args()) == expected, system
    monkeypatch.setattr(settings, "host_system", lambda: "darwin")
    assert shaped(runner_module.SETTINGS_FLAG, "s", runner_module.HOUSEHOLD_FLAG, "Alder") is None
    assert shaped(runner_module.SETTINGS_FLAG, "s", "--dry-run") is None
    assert shaped("/some/root", runner_module.SETTINGS_FLAG, "s") is None
    assert shaped("/some/root") is None


def test_a_scheduled_pass_off_windows_stops_itself_before_the_run_limit(tmp_path, samples, monkeypatch, capsys):
    """R26: at the run limit less one household's budget, on the wall clock, the pass
    stops as Stop does - after the file it is on, recording the stop and letting go of
    its locks - and the next pass files the rest."""
    from tracker import settings
    from tracker.locking import RUN_TIME_LIMIT_SECONDS, lock_status
    from tracker.run_log import log_path
    from tracker.runner import (
        CODE_PASS_RUN_LIMIT,
        HOUSEHOLD_BUDGET_SECONDS,
        PASS_RUN_LIMIT,
        SELF_STOP_AFTER_SECONDS,
        SelfLimitedWatch,
    )

    assert SELF_STOP_AFTER_SECONDS == RUN_TIME_LIMIT_SECONDS - HOUSEHOLD_BUDGET_SECONDS
    monkeypatch.setattr(settings, "host_system", lambda: "posix")       # off Windows, on any runner
    root = tmp_path / "root"
    engagement = build_engagement(root, samples, drops=THREE_DROPS)
    clock = [1_700_000_000.0]
    monkeypatch.setattr(runner_module, "wall_clock", lambda: clock[0])
    monkeypatch.setattr(runner_module, "WATCHDOG_SLICE_SECONDS", 3600.0)
    sorted_ = []
    real_say = SelfLimitedWatch.say

    def say(self, event, **fields):
        real_say(self, event, **fields)
        if event == "file" and fields.get("step") == "sort":
            sorted_.append(fields)
            if len(sorted_) == 2:      # on the second file, an hour and three quarters in
                clock[0] += SELF_STOP_AFTER_SECONDS

    monkeypatch.setattr(SelfLimitedWatch, "say", say)

    code = _the_scheduled_job(root, monkeypatch, runner_module.LOG_FLAG, "--reminders", REMINDERS_NEVER)

    assert code == 0 and len(sorted_) == 2, "the first was taken; it stopped at the second"
    said = PASS_RUN_LIMIT.format(n=1)
    assert said in _page(root) and f"{CODE_PASS_RUN_LIMIT}=1" in log_path().read_text(encoding="utf-8")
    assert "stopped by a person" not in _page(root), "no person stopped it"
    assert said not in log_path().read_text(encoding="utf-8"), "the log keeps the code, never a sentence"
    assert len([p for p in inbox_of(engagement.path).iterdir() if p.name in THREE_DROPS]) == 2, "two wait"
    assert lock_status(engagement.path) is None, "its locks are let go"
    assert "succeeded" in run_log.last_pass_line(runner_module.last_pass_path())["text"]
    capsys.readouterr()

    monkeypatch.setattr(SelfLimitedWatch, "say", real_say)
    assert main([runner_module.SETTINGS_FLAG, str(tmp_path / "settings"), "--reminders", REMINDERS_NEVER]) == 0
    assert not [p for p in inbox_of(engagement.path).iterdir() if p.name in THREE_DROPS], "the next pass took them"


def test_a_pass_before_the_run_limit_is_not_stopped_early(tmp_path, samples, monkeypatch):
    from tracker import settings

    monkeypatch.setattr(settings, "host_system", lambda: "posix")
    root = tmp_path / "root"
    engagement = build_engagement(root, samples, drops=THREE_DROPS)
    monkeypatch.setattr(runner_module, "wall_clock", lambda: 1_700_000_000.0)
    monkeypatch.setattr(runner_module, "WATCHDOG_SLICE_SECONDS", 3600.0)
    assert _the_scheduled_job(root, monkeypatch, runner_module.LOG_FLAG, "--reminders", REMINDERS_NEVER) == 0
    assert not [p for p in inbox_of(engagement.path).iterdir() if p.name in THREE_DROPS]
    assert runner_module.PASS_RUN_LIMIT.split("{")[0] not in _page(root)


def test_the_watchdog_ends_the_process_at_the_run_limit_on_the_wall_clock(monkeypatch):
    """R26: looked at in slices, so a clock that jumped while the Mac slept is seen;
    never before the limit, and not at all once the pass is done."""
    import threading

    from tracker.locking import RUN_TIME_LIMIT_SECONDS
    from tracker.runner import RUN_LIMIT_EXIT_CODE, _watch_the_run_limit

    clock = [100.0]
    ended = []
    fired = threading.Event()
    monkeypatch.setattr(runner_module, "wall_clock", lambda: clock[0])
    monkeypatch.setattr(runner_module, "WATCHDOG_SLICE_SECONDS", 0.01)
    monkeypatch.setattr(runner_module, "_end_the_process", lambda code: (ended.append(code), fired.set()))

    quiet = threading.Event()
    thread = _watch_the_run_limit(100.0, quiet)
    clock[0] = 100.0 + RUN_TIME_LIMIT_SECONDS - 1
    assert not fired.wait(0.3) and ended == [], "not before the limit"
    quiet.set()
    clock[0] = 100.0 + RUN_TIME_LIMIT_SECONDS + 5
    thread.join(5)
    assert not thread.is_alive() and ended == [], "a pass that is done is not ended"

    thread = _watch_the_run_limit(100.0, threading.Event())
    assert fired.wait(5) and ended == [RUN_LIMIT_EXIT_CODE]
    thread.join(5)
    assert not thread.is_alive(), "it ends after it has fired"


def test_a_scheduled_pass_off_windows_ends_at_the_run_limit_and_its_lock_is_cleared_as_dead(tmp_path):
    """R26 and R19: a real process holds a return's lock and is ended by the watchdog at
    the limit. The kernel lets go of its lock, and the next pass finds its owner gone and
    clears it, as it would one Task Scheduler killed."""
    import subprocess
    import sys
    import time

    from tests.plugin_session import REPO, child_env
    from tracker.locking import acquire_lock, lock_status, release_lock
    from tracker.runner import RUN_LIMIT_EXIT_CODE

    folder = tmp_path / "return"
    folder.mkdir()
    child = (
        "import sys, threading, time\n"
        "from pathlib import Path\n"
        "import tracker.runner as runner\n"
        "from tracker.locking import acquire_lock\n"
        "acquire_lock(Path(sys.argv[1]))\n"
        "runner.WATCHDOG_SLICE_SECONDS = 0.05\n"
        "runner.RUN_TIME_LIMIT_SECONDS = 1\n"
        "runner._watch_the_run_limit(runner.wall_clock() - 0.5, threading.Event())\n"
        "time.sleep(60)\n"
    )
    began = time.monotonic()
    done = subprocess.run([sys.executable, "-c", child, str(folder)], cwd=REPO, env=child_env(),
                          capture_output=True, text=True, timeout=120, check=False)
    assert done.returncode == RUN_LIMIT_EXIT_CODE, done.stderr
    assert time.monotonic() - began < 60, "it did not wait out its sleep"

    status = lock_status(folder)
    assert status is not None and status.owner_gone and status.stale, "a lock whose owner is dead"
    release_lock(acquire_lock(folder))               # the next pass takes it over without a word


def test_a_mac_pass_refused_the_root_says_macos_did_not_allow_it(tmp_path, samples, monkeypatch):
    """R30: on a Mac a clients folder macOS will not let this program list is
    ``root-not-permitted``, not "could not be walked": the permission is the
    program's own, and for the pass launchd starts that is the API."""
    from tracker import settings
    from tracker.runner import PASS_REASONS, PASS_ROOT_NOT_PERMITTED, PASS_ROOT_UNREADABLE

    assert PASS_ROOT_NOT_PERMITTED == "root-not-permitted" != PASS_ROOT_UNREADABLE
    assert PASS_REASONS[PASS_ROOT_NOT_PERMITTED] == (
        "macOS did not let the schedule read the clients folder; open the app, and allow it when macOS "
        "asks (runbook, 'On a Mac')")
    root = tmp_path / "root"
    build_engagement(root, samples)
    monkeypatch.setattr(settings, "host_system", lambda: "darwin")
    monkeypatch.setattr(settings, "drive_type", lambda path: settings.DRIVE_FIXED)
    listed = []

    def refused(folder):
        listed.append(folder)
        raise PermissionError(1, "Operation not permitted", folder)

    monkeypatch.setattr(runner_module, "_list_the_root", refused)
    walked = []
    monkeypatch.setattr(runner_module, "discover_engagements", lambda *args: walked.append(args))

    with pytest.raises(SystemExit) as stopped:
        _the_scheduled_job(root, monkeypatch, runner_module.LOG_FLAG)

    assert stopped.value.reason_code == PASS_ROOT_NOT_PERMITTED and listed and not walked, "nothing was walked"
    assert str(stopped.value) == f"Clients folder problem: {PASS_REASONS[PASS_ROOT_NOT_PERMITTED]}"
    path = runner_module.last_pass_path()
    assert json.loads(path.read_text(encoding="utf-8"))["reason_code"] == PASS_ROOT_NOT_PERMITTED
    line = run_log.last_pass_line(path)
    assert line["level"] == run_log.LEVEL_ERR and PASS_REASONS[PASS_ROOT_NOT_PERMITTED] in line["text"]
    assert PASS_REASONS[PASS_ROOT_NOT_PERMITTED] in run_log.log_path().read_text(encoding="utf-8")


def test_a_root_that_lists_is_walked_on_a_mac_and_a_refusal_off_a_mac_is_the_walks_own(
        tmp_path, samples, monkeypatch):
    from tracker import settings

    root = tmp_path / "root"
    engagement = build_engagement(root, samples)
    monkeypatch.setattr(settings, "host_system", lambda: "darwin")
    monkeypatch.setattr(settings, "drive_type", lambda path: settings.DRIVE_FIXED)
    assert _the_scheduled_job(root, monkeypatch, runner_module.LOG_FLAG, "--reminders", REMINDERS_NEVER) == 0
    assert not [p for p in inbox_of(engagement.path).iterdir() if p.name.startswith("W-2")]

    monkeypatch.setattr(settings, "host_system", lambda: "posix")

    def refused(folder):
        raise AssertionError("only a Mac asks")

    monkeypatch.setattr(runner_module, "_list_the_root", refused)
    assert _the_scheduled_job(root, monkeypatch, runner_module.LOG_FLAG, "--reminders", REMINDERS_NEVER) == 0
