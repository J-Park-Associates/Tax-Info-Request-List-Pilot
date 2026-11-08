"""Tests for tracker/run_log.py - what one pass reports: its records, the run
log's codes, the run log and the last-pass file the app reads.

Most of what the module promises is held by tests/test_runner.py and the test_runner_<family> files split from it
(SPEC-architecture-p5 P5.14), whose tests
run a pass and read what it left: every failure and skip logged as a code and
every pass warning with its code, no client's file name in any run log line,
the run log in the data home and a relative ``--log`` refused, the line of a
pass that stopped before or after its root, the last-pass file written only
by the scheduled job's shape and its reason codes. None of them moved here by
the SPEC's rule, because each runs the pass or the runner's command line. The
seven tests below moved here from tests/test_runner.py (SPEC-architecture-p5
R5.8.7, P345), byte for byte: each calls the run log or the last-pass line
directly and nothing that stayed in the runner. A read through
``tracker.runner`` of a name the runner imports back is kept as it was, until
SPEC-architecture-p5 P5.16 retargets every such read to its home.
"""

import datetime as dt

import pytest

import tracker.runner as runner_module
from tests import passes
from tests.passes import FRIDAY, SATURDAY, build_engagement
from tracker import run_log
from tracker.run_log import LOG_FILENAME, REMINDERS_AUTO, EngagementRun, RunReport, append_log

#: The sample pile, built once per session: a fixture of ``tests/passes.py``, named here
#: so every claim below can ask for it.
samples = passes.samples


def test_a_name_utf8_cannot_hold_never_reaches_the_log(tmp_path, samples):
    # The eleventh reading: a lone surrogate in a client's file name is
    # reported every pass by name, and the run log - the unattended run's
    # only trace - died on it. Since decision 186 no name reaches the log
    # at all: the failure is counted and coded, and the entry is whole.
    engagement = build_engagement(tmp_path, samples)
    run = EngagementRun(engagement=engagement)
    run.error = "bank statement \ud83d.pdf: cannot be handled under this name"
    run.code = "crashed:UnicodeEncodeError"
    report = RunReport(today=FRIDAY, reminders=REMINDERS_AUTO, dry_run=False, runs=[run])
    log = tmp_path / LOG_FILENAME
    append_log(log, report)
    text = log.read_text(encoding="utf-8")
    assert "bank statement" not in text and "cannot be handled" not in text
    assert " failed=1 " in text and "codes crashed:UnicodeEncodeError=1" in text


def test_the_run_log_carries_a_count_of_warnings_never_their_words(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    run = EngagementRun(engagement=engagement, warnings=["a sentence naming W-2 Client.pdf"] * 3)
    log_path = append_log(tmp_path / LOG_FILENAME, RunReport(today=SATURDAY, runs=[run]))
    text = log_path.read_text(encoding="utf-8")
    assert " warnings=3" in text
    assert "W-2 Client.pdf" not in text


@pytest.mark.parametrize(("every", "hours"), [
    (30, 4), (60, 4), (120, 4),            # never under the floor of four hours
    (240, 8), (480, 16),                   # two missed runs of the saved interval
    (0, 48),                               # once a day: two days
])
def test_the_amber_threshold_is_two_missed_runs_of_the_saved_interval(tmp_path, every, hours):
    """Pilot P21: the line turns amber after two missed runs of the interval
    the person chose - four hours at the two-hour default - and says the
    wait it assumed."""
    from tracker import settings

    settings.set_schedule(True, "07:00", every)
    assert run_log.amber_hours(every) == hours
    now = dt.datetime(2026, 3, 2, 12, 0)
    path = tmp_path / runner_module.LAST_PASS_FILENAME

    inside = now - dt.timedelta(hours=hours) + dt.timedelta(minutes=1)
    runner_module.write_last_pass(path, started=inside, ended=inside, root="R",
                                  result=runner_module.PASS_SUCCEEDED)
    assert run_log.last_pass_line(path, now=now)["level"] == run_log.LEVEL_OK

    outside = now - dt.timedelta(hours=hours, minutes=1)
    runner_module.write_last_pass(path, started=outside, ended=outside, root="R",
                                  result=runner_module.PASS_SUCCEEDED)
    line = run_log.last_pass_line(path, now=now)
    assert line["level"] == run_log.LEVEL_WARN
    assert line["text"].endswith(run_log.LAST_PASS_OLD.format(hours=str(hours)))


def test_the_last_pass_line_says_the_schedule_is_off_instead_of_turning_amber(tmp_path):
    from tracker import settings

    settings.set_schedule(False, "07:00", 120)
    now = dt.datetime(2026, 3, 2, 12, 0)
    path = tmp_path / runner_module.LAST_PASS_FILENAME
    long_ago = now - dt.timedelta(days=30)
    runner_module.write_last_pass(path, started=long_ago, ended=long_ago, root="R",
                                  result=runner_module.PASS_SUCCEEDED)
    assert run_log.last_pass_line(path, now=now) == {
        "text": run_log.LAST_PASS_OFF, "level": run_log.LEVEL_OK}
    assert run_log.last_pass_line(tmp_path / "missing.json", now=now)["text"] == run_log.LAST_PASS_OFF


def test_a_saved_choice_that_will_not_read_turns_the_line_red_and_names_no_guess(tmp_path):
    from tracker import settings

    settings.settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings.settings_path().write_text('{"schedule_every": 45}', encoding="utf-8")
    line = run_log.last_pass_line(tmp_path / runner_module.LAST_PASS_FILENAME)
    assert line["level"] == run_log.LEVEL_ERR
    assert settings.EVERY_REFUSED.format(value=45) in line["text"]      # the refusal's own sentence
    assert line["text"] != run_log.LAST_PASS_UNREADABLE.format(error="ScheduleChoiceError")


def test_the_last_pass_line_is_amber_when_old_and_red_when_failed(tmp_path):
    """The app's one line: plain when recent, amber after
    LAST_PASS_AMBER_HOURS or when no pass has run, red on a failure or a
    file that does not read - every word the runner's."""
    now = dt.datetime(2026, 3, 2, 12, 0)
    path = tmp_path / runner_module.LAST_PASS_FILENAME
    assert run_log.last_pass_line(path, now=now) == {
        "text": run_log.LAST_PASS_NEVER, "level": run_log.LEVEL_WARN}

    recent = now - dt.timedelta(hours=1)
    runner_module.write_last_pass(path, started=recent, ended=recent, root="R",
                                  result=runner_module.PASS_SUCCEEDED)
    line = run_log.last_pass_line(path, now=now)
    assert line["level"] == run_log.LEVEL_OK and "2026-03-02 11:00" in line["text"]

    old = now - dt.timedelta(hours=run_log.LAST_PASS_AMBER_HOURS, minutes=1)
    runner_module.write_last_pass(path, started=old, ended=old, root="R",
                                  result=runner_module.PASS_SUCCEEDED)
    line = run_log.last_pass_line(path, now=now)
    assert line["level"] == run_log.LEVEL_WARN
    assert line["text"].endswith(run_log.LAST_PASS_OLD.format(hours="4"))

    runner_module.write_last_pass(path, started=recent, ended=recent, root="",
                                  result=runner_module.PASS_FAILED,
                                  reason_code=runner_module.PASS_SETTINGS)
    line = run_log.last_pass_line(path, now=now)
    assert line["level"] == run_log.LEVEL_ERR
    assert runner_module.PASS_REASONS[runner_module.PASS_SETTINGS] in line["text"]

    path.write_text("{not json", encoding="utf-8")
    assert run_log.last_pass_line(path, now=now)["level"] == run_log.LEVEL_ERR


@pytest.mark.parametrize("text", [
    '{"started": "2026-03-02T11:00:00", "result": "Fabricated Client says hello"}',
    "[" * 100_000,
    '{"started": "2026-03-02T11:00:00+05:00", "result": "succeeded"}',
], ids=["a-result-not-written-here", "nested-past-the-limit", "an-aware-time"])
def test_the_last_pass_line_echoes_nothing_the_file_holds(tmp_path, text):
    """Read as 189 reads its hint: bounded, never raising, and a result or
    a reason is said only when it is one this module writes."""
    path = tmp_path / runner_module.LAST_PASS_FILENAME
    path.write_text(text, encoding="utf-8")
    line = run_log.last_pass_line(path, now=dt.datetime(2026, 3, 2, 12, 0))
    assert line["level"] == run_log.LEVEL_ERR and "Fabricated" not in line["text"]
