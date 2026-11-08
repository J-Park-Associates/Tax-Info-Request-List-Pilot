"""Tests for tracker/runner.py — the weekly pass over every engagement.

The rules that matter here: reminders are drafted on Saturday and only on
Saturday, an edited draft survives the weekly run, one client's failure never
stops another client's run, an ambiguous request holds the whole reminder
and the draft is on the record (decision 115), and nothing is ever sent.

The pass reads the day of the last draft from the record, so a test that
tells the pass ``today`` is a day in March must stamp what the pass records
on that day: ``stamped_on`` does, and ``pass_on`` is a pass with it.

What stays here is the pass itself: the Saturday, the full pass, the gate and the record,
failure isolation, reporting, discovery end to end, an approved draft, errors as classes,
what an earlier version left and a budget in counts. The rest of the file was split by its
section banners into ``tests/test_runner_household.py``, ``test_runner_watch.py`` and
``test_runner_reports.py`` (SPEC-architecture-p5 P5.14, E-3), so each family runs as its own
process; ``stamped_on``, ``a_pass``, ``pass_on`` and the other helpers more than one of them
reads are ``tests/passes.py``'s.
"""

import datetime as dt
import html
from pathlib import Path

import pytest

import tracker.runner as runner_module
from tests import passes
from tests.builders import make_engagement, written_elsewhere
from tests.passes import (
    FRIDAY,
    SATURDAY,
    SUNDAY,
    _the_scheduled_job,
    _three_households,
    a_pass,
    build_engagement,
    drafted_events,
    edit_details,
    edit_rows,
    make_ambiguous,
    pass_on,
)
from tests.samples import DEMO_ITEMS, PRIOR_YEAR, SCRATCH_PEOPLE, YEAR
from tracker import fsio, ledger, pass_order, run_log, status_page, store
from tracker.index import read_index
from tracker.layout import inbox_of, originals_of
from tracker.manifest import EngagementInfo, Override, RequestItem, Status, load_engagement_info, save_rules
from tracker.records import YES, rule_from_json
from tracker.registry import SKIP_ROLLED_FORWARD, Engagement, Registry, discover_engagements, engagement_from
from tracker.reminder import (
    CHANGED_ADDED,
    CHANGED_HEADING,
    DRAFT_BANNER,
    DRAFT_FILENAME,
    HELD_REFUSAL,
    NEW_DRAFT_FILENAME,
    is_unedited,
)
from tracker.run_log import LOG_FILENAME, REMINDERS_ALWAYS, REMINDERS_AUTO, REMINDERS_NEVER, RunReport, append_log
from tracker.runner import (
    DRAFT_WEEKDAY,
    NOTHING_OUTSTANDING,
    SETTINGS_FLAG,
    WEEKDAY_NAMES,
    format_report,
    is_draft_day,
    last_drafted,
    main,
    run_registry,
    should_draft,
)
from tracker.scaffold import PREPARED_DIR_NAME, scaffold_engagement
from tracker.status_page import RECORD_UNREADABLE, STATUS_HELD, STATUS_PAGE_FILENAME, write_status_page

DRAFT_DAY = WEEKDAY_NAMES[DRAFT_WEEKDAY]


def as_engagement(folder, **fields):
    """The return as the registry reads it, with a detail or two of the
    test's own laid over.

    Read from the record rather than typed, because the pass reads the
    household, the year and the return name off it since decision 125 -
    a hand-built Engagement with none of them is a return no inbox feeds.
    """
    from dataclasses import replace

    found = engagement_from(folder)
    return replace(found, info=replace(found.info, **fields)) if fields else found


def test_the_runner_has_a_main_the_frozen_entry_can_call(tmp_path, samples, capsys):
    # api_entry.py runs the scheduled job through this function, so the
    # command line has to be one, not code under __main__.
    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    build_engagement(root, samples)
    assert main([str(root), "--dry-run", "--reminders", REMINDERS_NEVER]) == 0
    assert "Smith TY2025" in capsys.readouterr().out


def test_the_runners_console_guard_is_the_pages(tmp_path, samples, monkeypatch):
    # The scheduler's console is cp1252 and the report names the client's
    # folder. The guard that made this a run instead of a traceback (the
    # tenth reading) is tracker.page's now, shared by every command line.
    import io
    import sys

    # An arrow and a check mark: no letter of a second alphabet (decision 188).
    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    build_engagement(root, samples, name="Smith TY2025 \u2192 \u2713")
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", console)
    code = main([str(root), "--dry-run", "--reminders", REMINDERS_NEVER])
    console.flush()
    shown = console.buffer.getvalue().decode("cp1252")
    assert code == 0
    assert "Smith TY2025 \\u2192 \\u2713" in shown


#: The sample pile, built once per session: a fixture of ``tests/passes.py``, named here
#: so every claim below can ask for it.
samples = passes.samples

#: A fixture of ``tests/passes.py``, named here so every claim below can ask for it.
stamped_on = passes.stamped_on


# ------------------------------------------------------------ the Saturday ----


def test_saturday_is_the_draft_day():
    assert is_draft_day(SATURDAY) is True
    assert is_draft_day(FRIDAY) is False
    assert is_draft_day(SUNDAY) is False


@pytest.mark.parametrize("day, expected", [(FRIDAY, False), (SATURDAY, True),
                                           (SUNDAY, False)])
def test_auto_mode_drafts_only_on_saturday(day, expected):
    engagement = Engagement(path=Path("/x"))
    assert should_draft(engagement, day, REMINDERS_AUTO) is expected


def test_always_mode_drafts_on_any_day():
    assert should_draft(Engagement(path=Path("/x")), FRIDAY, REMINDERS_ALWAYS) is True


def test_never_mode_suppresses_even_on_saturday():
    assert should_draft(Engagement(path=Path("/x")), SATURDAY, REMINDERS_NEVER) is False


def test_reminders_off_beats_every_mode():
    """A standing decision not to chase this client by email is not a flag."""
    quiet = Engagement(path=Path("/x"), info=EngagementInfo(reminders=False))
    assert should_draft(quiet, SATURDAY, REMINDERS_AUTO) is False
    assert should_draft(quiet, SATURDAY, REMINDERS_ALWAYS) is False


def test_a_draft_day_the_machine_missed_is_caught_up_on_the_next_pass():
    # Weekly, not only on the day. The machine was off on Saturday: Sunday's
    # pass drafts, because the last draft is older than the Saturday that
    # went by. Monday after a Saturday that did draft: nothing, until next
    # week. Never drafted: wait for the first Saturday.
    from tracker.runner import last_draft_day

    engagement = Engagement(path=Path("/x"))
    assert last_draft_day(SUNDAY) == SATURDAY and last_draft_day(SATURDAY) == SATURDAY
    assert last_draft_day(FRIDAY) == SATURDAY - dt.timedelta(days=7)
    assert should_draft(engagement, SUNDAY, REMINDERS_AUTO, drafted=SATURDAY - dt.timedelta(days=7)) is True
    assert should_draft(engagement, SUNDAY, REMINDERS_AUTO, drafted=SATURDAY) is False
    assert should_draft(engagement, FRIDAY, REMINDERS_AUTO, drafted=SATURDAY - dt.timedelta(days=7)) is False
    assert should_draft(engagement, SUNDAY, REMINDERS_AUTO, drafted=None) is False


def test_a_pass_after_a_missed_saturday_writes_the_weeks_draft(tmp_path, samples, stamped_on):
    engagement = build_engagement(tmp_path, samples)
    drafted = pass_on(stamped_on, engagement, SATURDAY - dt.timedelta(days=7)).drafted
    assert drafted is not None                          # on the record as last Saturday's
    assert pass_on(stamped_on, engagement, FRIDAY).drafted is None      # this week not yet due
    run = pass_on(stamped_on, engagement, SUNDAY)      # Saturday was missed
    assert run.drafted == engagement.path / DRAFT_FILENAME


def test_the_draft_day_can_be_moved():
    monday = dt.date(2026, 3, 16)
    assert should_draft(Engagement(path=Path("/x")), monday, REMINDERS_AUTO, weekday=0) is True
    assert should_draft(Engagement(path=Path("/x")), SATURDAY, REMINDERS_AUTO, weekday=0) is False


# ------------------------------------------------------------- the full pass ----


def test_a_weekday_run_files_and_scans_but_writes_no_draft(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    run = a_pass(engagement, today=FRIDAY)

    assert run.ok and run.filed == 1
    assert run.statuses[Status.PARTIAL] == 1
    assert run.drafted is None
    assert f"not {DRAFT_DAY}" in run.draft_note.lower()
    assert not (engagement.path / DRAFT_FILENAME).exists()


def test_the_saturday_run_writes_a_draft(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    run = a_pass(engagement, today=SATURDAY)

    assert run.drafted == engagement.path / DRAFT_FILENAME
    text = run.drafted.read_text(encoding="utf-8")
    assert text.startswith(DRAFT_BANNER)
    assert "Hi John Smith," in text


def test_a_manual_run_drafts_on_a_weekday(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    run = a_pass(engagement, today=FRIDAY, reminders=REMINDERS_ALWAYS)
    assert run.drafted == engagement.path / DRAFT_FILENAME


def test_an_edited_draft_survives_the_next_weekly_run(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    first = a_pass(engagement, today=SATURDAY).drafted
    # Read and write the bytes as they are: these drafts are CRLF for Windows,
    # and universal-newline translation would make this test lie.
    edited = first.read_bytes() + b"\r\nPS: ask about the rental.\r\n"
    first.write_bytes(edited)

    second = a_pass(engagement, today=SATURDAY + dt.timedelta(days=7))

    assert first.read_bytes() == edited, "an edit must never be clobbered"
    assert second.drafted.name == NEW_DRAFT_FILENAME
    assert "has been edited" in second.draft_note


def test_an_edited_second_draft_is_never_clobbered_by_the_next_repeat(tmp_path, samples):
    # The draft day's repeat runs several times. The first made room for the
    # person's edits by writing NEW; the next must not take NEW's edits too.
    from tracker.reminder import BOTH_DRAFTS_EDITED

    engagement = build_engagement(tmp_path, samples)
    first = a_pass(engagement, today=SATURDAY).drafted
    first.write_bytes(first.read_bytes() + b"\r\nPS: ask about the rental.\r\n")
    second = a_pass(engagement, today=SATURDAY).drafted
    assert second.name == NEW_DRAFT_FILENAME
    edited_new = second.read_bytes() + b"\r\nPPS: and the boat.\r\n"
    second.write_bytes(edited_new)

    third = a_pass(engagement, today=SATURDAY)
    assert third.drafted is None and third.ok
    assert third.draft_note == BOTH_DRAFTS_EDITED
    assert second.read_bytes() == edited_new


def test_a_draft_day_with_nothing_to_chase_refreshes_the_runs_own_stale_draft(tmp_path, samples, stamped_on):
    # Last week's draft asked for a document that has since arrived. The
    # run's own unedited draft is rewritten as today's (nothing to chase),
    # so it is neither stale text nor an old date; a draft a person edited
    # is theirs and stays exactly as it is.
    only_the_return = [i for i in DEMO_ITEMS if i.identifier == "B01"]
    folder = make_engagement(tmp_path, only_the_return, return_name="Settled TY2025",
                             people=SCRATCH_PEOPLE, scaffold=False)
    scaffolded = scaffold_engagement(folder)
    engagement = as_engagement(folder, client="John Smith")
    drafted = pass_on(stamped_on, engagement, SATURDAY - dt.timedelta(days=7)).drafted
    stale = drafted.read_bytes()

    name = f"{PRIOR_YEAR} Form 1040 Tax Return.pdf"
    (scaffolded.inbox / name).write_bytes((samples / name).read_bytes())
    run = pass_on(stamped_on, engagement, SATURDAY)
    assert run.draft_note == NOTHING_OUTSTANDING and run.drafted is None
    assert drafted.exists() and drafted.read_bytes() != stale          # today's words
    # The quiet week is on the record - asked nothing, this file - and that
    # is where the day of the last draft is read from (decision 115).
    assert drafted_events(folder)[-1][ledger.ASKED_KEY] == [] and last_drafted(folder) == SATURDAY
    assert pass_on(stamped_on, engagement, SATURDAY + dt.timedelta(days=3)).drafted is None

    drafted.write_bytes(b"a person's own words")
    pass_on(stamped_on, engagement, SATURDAY)
    assert drafted.read_bytes() == b"a person's own words"
    assert last_drafted(folder) == SATURDAY


def test_an_untouched_draft_is_refreshed_in_place(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    first = a_pass(engagement, today=SATURDAY).drafted
    second = a_pass(engagement, today=SATURDAY + dt.timedelta(days=7))

    assert second.drafted == first
    assert not (engagement.path / NEW_DRAFT_FILENAME).exists()


def test_nothing_outstanding_means_no_draft_file(tmp_path, samples):
    """Everything in: there is nothing to chase, so no draft is written."""
    only_the_return = [i for i in DEMO_ITEMS if i.identifier == "B01"]
    folder = make_engagement(tmp_path, only_the_return, return_name="Settled TY2025",
                             people=SCRATCH_PEOPLE, scaffold=False)
    scaffolded = scaffold_engagement(folder)
    name = f"{PRIOR_YEAR} Form 1040 Tax Return.pdf"
    (scaffolded.inbox / name).write_bytes((samples / name).read_bytes())

    run = a_pass(as_engagement(folder, client="John Smith"), today=SATURDAY)

    assert run.statuses == {Status.RECEIVED: 1}
    assert run.outstanding == 0
    assert run.drafted is None
    assert run.draft_note == NOTHING_OUTSTANDING
    assert not (folder / DRAFT_FILENAME).exists()


def test_a_week_whose_only_ask_is_a_program_writes_its_draft_at_no_stage(tmp_path, samples):
    """The re-check's S-N1: every request is in and the client dropped a
    program. The letter asks about it, so the week's draft is written - not
    recorded as nothing outstanding while the file says otherwise - and it
    is at no stage, because a file that is not a document is no rung."""
    from tracker.reminder import SECTION_FAILED

    only_the_return = [i for i in DEMO_ITEMS if i.identifier == "B01"]
    folder = make_engagement(tmp_path, only_the_return, return_name="Settled TY2025",
                             people=SCRATCH_PEOPLE, scaffold=False)
    scaffolded = scaffold_engagement(folder)
    name = f"{PRIOR_YEAR} Form 1040 Tax Return.pdf"
    (scaffolded.inbox / name).write_bytes((samples / name).read_bytes())
    (scaffolded.inbox / "setup.exe").write_bytes(b"MZ not a document")

    run = a_pass(as_engagement(folder, client="John Smith"), today=SATURDAY)

    assert run.statuses == {Status.RECEIVED: 1} and run.outstanding == 0
    assert run.draft_note != NOTHING_OUTSTANDING
    assert run.drafted == folder / DRAFT_FILENAME and run.stage == 0
    text = run.drafted.read_text(encoding="utf-8")
    assert SECTION_FAILED in text and "setup.exe" in text


def test_the_draft_step_hands_the_pass_day_to_the_drafter_and_records_the_stage(tmp_path, samples, stamped_on):
    """Decision 117: the stage is measured from the day the pass is making,
    not from the clock - so a dated run writes the letter that day was
    owed - and the run says which rung it wrote, in its own line, on the
    practice page and on the record."""
    from tracker.reminder import STAGE_KEY, STAGE_LINE, stage_named
    from tracker.run_log import STAGE_NOTE

    engagement = build_engagement(tmp_path, samples)
    # The draft day is thirteen days before the date this client was asked
    # to send by: the second rung.
    edit_details(engagement.path, due=SATURDAY + dt.timedelta(days=13))
    run = pass_on(stamped_on, engagement, SATURDAY)
    assert run.stage == 2
    assert STAGE_NOTE.format(n=2) in run.summary()
    assert STAGE_LINE.format(number=2, name=stage_named(2).name) in run.drafted.read_text(encoding="utf-8")
    assert drafted_events(engagement.path)[-1][STAGE_KEY] == 2
    page = html.unescape(write_status_page(tmp_path, RunReport(today=SATURDAY, runs=[run])).read_text(encoding="utf-8"))
    assert f"<td>{STAGE_NOTE.format(n=2)}</td>" in page

    # A week later, inside the last ten days: the same rows, a harder
    # letter, and the record says so rather than saying nothing happened.
    later = SATURDAY + dt.timedelta(days=7)
    after = pass_on(stamped_on, engagement, later)
    assert after.stage == 3 and after.drafted is not None
    events = drafted_events(engagement.path)
    assert [event[STAGE_KEY] for event in events] == [2, 3]
    assert events[0][ledger.ASKED_KEY] == events[1][ledger.ASKED_KEY]


def test_a_dry_run_writes_nothing_at_all(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    run = a_pass(engagement, today=SATURDAY, dry_run=True)

    assert run.drafted is None
    assert "would draft" in run.draft_note
    assert not (engagement.path / DRAFT_FILENAME).exists()
    assert (inbox_of(engagement.path) / f"W-2 John Smith {YEAR}.pdf").exists(), (
        "a dry run must not move the client's file"
    )


# ---------------------------------------------- the gate, and the record ----
# Decision 115: an ambiguous request holds the whole reminder, and the draft
# is on the record. A copy the router filed cannot fail the content rules on
# its own filing, so the way a filed copy comes to fail is the firm's own
# doing - here, a rule edited after filing.


def build_chased_engagement(tmp_path, samples, name="Smith TY2025"):
    """A W-2 filed under A01 (Partial, 1 of 2) and a 1098 filed under C01
    (Received), with A02, B01 and D01 still Missing."""
    return build_engagement(tmp_path, samples, name=name,
                            drops=(f"W-2 John Smith {YEAR}.pdf", "Form 1098 Mortgage Interest.pdf"))


def resolve_by_fixing_the_rule(engagement_dir, identifier, keywords):
    return edit_rows(engagement_dir, **{identifier: {"required_keywords": keywords}})


def test_a_held_engagement_writes_no_draft_retires_its_own_stale_draft_and_leaves_an_edited_one(
        tmp_path, samples, stamped_on):
    engagement = build_chased_engagement(tmp_path, samples)
    first = pass_on(stamped_on, engagement, SATURDAY).drafted
    assert first == engagement.path / DRAFT_FILENAME and is_unedited(first)
    # Somebody's edited draft beside the run's own unedited one.
    edited = engagement.path / NEW_DRAFT_FILENAME
    edited.write_bytes(first.read_bytes() + b"\r\nPS: ask about the rental.\r\n")
    kept = edited.read_bytes()

    make_ambiguous(engagement.path)
    run = pass_on(stamped_on, engagement, SATURDAY + dt.timedelta(days=7))

    assert run.ok and run.drafted is None and run.held == 1
    assert run.draft_note.startswith(HELD_REFUSAL.split("{")[0]) and "C01" in run.draft_note
    assert not first.exists(), "the run's own unedited draft reads like a sendable email"
    assert edited.read_bytes() == kept, "a person's work is theirs"
    log_path = append_log(tmp_path / LOG_FILENAME, RunReport(today=SATURDAY, runs=[run]))
    logged = log_path.read_text(encoding="utf-8")
    # Counted, never named (decision 186): which rows hold it is the page's.
    assert " held=1 " in logged and run.draft_note not in logged
    assert format_report(RunReport(today=SATURDAY, runs=[run])).count("1 held") == 1


def test_reminders_always_is_held_too(tmp_path, samples, stamped_on):
    """Decision 13, amended: the mode forces the attempt, and the attempt is held."""
    engagement = build_chased_engagement(tmp_path, samples)
    pass_on(stamped_on, engagement, FRIDAY, reminders=REMINDERS_NEVER)      # files the two drops
    make_ambiguous(engagement.path)
    run = pass_on(stamped_on, engagement, FRIDAY, reminders=REMINDERS_ALWAYS)
    assert run.ok and run.drafted is None and run.held == 1
    assert "C01" in run.draft_note
    assert not (engagement.path / DRAFT_FILENAME).exists()
    assert drafted_events(engagement.path) == [{ledger.HELD_KEY: ["C01"]}]


def test_two_ambiguities_one_resolved_still_holds_and_both_resolved_drafts_on_the_next_pass(
        tmp_path, samples, stamped_on):
    from tracker.actions import unfile_document

    engagement = build_chased_engagement(tmp_path, samples)
    pass_on(stamped_on, engagement, SATURDAY)            # asked A02, B01, D01 and A01 (1 of 2)
    make_ambiguous(engagement.path, "A01")
    make_ambiguous(engagement.path, "C01")
    week_two = SATURDAY + dt.timedelta(days=7)
    held = pass_on(stamped_on, engagement, week_two)
    assert held.held == 2 and "A01" in held.draft_note and "C01" in held.draft_note

    # One resolved - the rule put back - and the other still open: held.
    resolve_by_fixing_the_rule(engagement.path, "A01", DEMO_ITEMS[0].required_keywords)
    still = pass_on(stamped_on, engagement, week_two + dt.timedelta(days=1))
    assert still.held == 1 and still.drafted is None and "C01" in still.draft_note

    # The other resolved by unfiling the copy: C01 goes Missing and is asked.
    filed = next(e for e in read_index(engagement.path) if e.identifier == "C01")
    unfile_document(engagement.path, filed.pbc_location, today=week_two)
    monday = week_two + dt.timedelta(days=2)
    run = pass_on(stamped_on, engagement, monday)
    assert run.held == 0 and run.drafted == engagement.path / DRAFT_FILENAME
    text = run.drafted.read_text(encoding="utf-8")
    header, _, body = text.partition("=" * 60)
    assert CHANGED_HEADING.format(date=SATURDAY.isoformat()) in header
    assert CHANGED_ADDED.format(label="C01 - Mortgage Interest Statement - Form 1098 (TY2025)") in header
    assert "(now asked)" not in body and is_unedited(run.drafted)
    # The draft after the hold is on the record, asked and file; the two
    # holds before it are one line each - the second Saturday's and the
    # Sunday's, which said something new.
    events = drafted_events(engagement.path)
    assert [ledger.HELD_KEY in e for e in events] == [False, True, True, False]
    assert events[1][ledger.HELD_KEY] == ["A01", "C01"] and events[2][ledger.HELD_KEY] == ["C01"]
    assert events[-1][ledger.ASKED_KEY] == ["A02", "B01", "C01", "D01", "A01"]
    assert events[-1][ledger.FILE_KEY] == DRAFT_FILENAME
    # And Tuesday finds this week drafted: nothing more until the next draft day.
    assert pass_on(stamped_on, engagement, monday + dt.timedelta(days=1)).drafted is None


def test_the_drafted_event_is_written_under_the_pass_lock_and_only_when_something_changed(
        tmp_path, samples, stamped_on):
    engagement = build_chased_engagement(tmp_path, samples)
    first = pass_on(stamped_on, engagement, SATURDAY)
    assert first.drafted is not None
    (events,) = drafted_events(engagement.path)
    assert events[ledger.ASKED_KEY] == ["A02", "B01", "D01", "A01"]
    assert events[ledger.FILE_KEY] == DRAFT_FILENAME
    assert events[ledger.FINGERPRINT_KEY] and events[ledger.FINGERPRINT_KEY] in first.drafted.read_text(encoding="utf-8")
    assert ledger.HELD_KEY not in events
    # The draft day's repeat, and the repeat's repeat: nothing moved, nothing appended.
    pass_on(stamped_on, engagement, SATURDAY)
    pass_on(stamped_on, engagement, SATURDAY)
    assert len(drafted_events(engagement.path)) == 1
    # A week later the same reminder is this week's reminder: one more line,
    # because the day of the last draft is read from it.
    pass_on(stamped_on, engagement, SATURDAY + dt.timedelta(days=7))
    assert len(drafted_events(engagement.path)) == 2
    assert last_drafted(engagement.path) == SATURDAY + dt.timedelta(days=7)
    # Written through the store under the pass's lock: the store and the journal agree.
    conn = store.connect()
    assert store.last_event(conn, engagement.path, ledger.DRAFTED)[ledger.ASKED_KEY] == events[ledger.ASKED_KEY]
    # A dry run records nothing.
    a_pass(engagement, today=SATURDAY, dry_run=True)
    assert len(drafted_events(engagement.path)) == 2


def test_last_drafted_answers_from_the_record_and_falls_back_to_the_files(tmp_path, samples, stamped_on):
    import os

    engagement = build_chased_engagement(tmp_path, samples)
    assert last_drafted(engagement.path) is None
    # No event yet (a journal from before decision 115): the file's time answers.
    stale = engagement.path / DRAFT_FILENAME
    stale.write_text("an old draft", encoding="utf-8")
    then = dt.datetime.combine(FRIDAY, dt.time(9)).timestamp()
    os.utime(stale, (then, then))
    assert last_drafted(engagement.path) == FRIDAY
    stale.unlink()

    drafted = pass_on(stamped_on, engagement, SATURDAY).drafted
    assert last_drafted(engagement.path) == SATURDAY
    # A sync client re-dating the file changes nothing once the record speaks.
    future = dt.datetime.combine(SATURDAY + dt.timedelta(days=30), dt.time(9)).timestamp()
    os.utime(drafted, (future, future))
    assert last_drafted(engagement.path) == SATURDAY
    # A hold is not a draft: the held week's line leaves the last draft where it was.
    make_ambiguous(engagement.path)
    pass_on(stamped_on, engagement, SATURDAY + dt.timedelta(days=7))
    assert last_drafted(engagement.path) == SATURDAY


def test_a_held_engagement_does_not_stop_the_next_engagements_draft(tmp_path, samples, stamped_on):
    """Decision 16: the hold is one engagement's, inside its own pass."""
    held = build_chased_engagement(tmp_path, samples, name="Held TY2025")
    pass_on(stamped_on, held, FRIDAY, reminders=REMINDERS_NEVER)             # files the two drops
    make_ambiguous(held.path)
    clean = build_engagement(tmp_path, samples, name="Clean TY2025")
    stamped_on(SATURDAY)
    report = run_registry(Registry(source=tmp_path, engagements=[held, clean]), today=SATURDAY)
    first, second = report.runs
    assert first.ok and first.held == 1 and first.drafted is None
    assert second.ok and second.drafted == clean.path / DRAFT_FILENAME
    assert report.errors == [] and len(report.drafted) == 1 and len(report.held) == 1


def test_the_practice_page_says_held_with_the_count(tmp_path, samples, stamped_on):
    engagement = build_chased_engagement(tmp_path, samples)
    pass_on(stamped_on, engagement, FRIDAY, reminders=REMINDERS_NEVER)      # files the two drops
    make_ambiguous(engagement.path)
    run = pass_on(stamped_on, engagement, SATURDAY)
    page = write_status_page(tmp_path, RunReport(today=SATURDAY, runs=[run]))
    text = html.unescape(page.read_text(encoding="utf-8"))
    assert f"<td>{STATUS_HELD.format(n=1)}</td>" in text
    assert f"<td>{YES}</td>" not in text, "a held engagement was not drafted"


# --------------------------------------------------------- failure isolation ----


def test_a_missing_folder_is_recorded_not_raised(tmp_path):
    run = a_pass(Engagement(path=tmp_path / "no-such-client"), today=SATURDAY)
    assert run.error.startswith("folder not found")


def test_a_missing_folder_is_said_without_its_path(tmp_path):
    """The row already names the return; the folder's path is a client's
    name and never reaches the page (decision 190)."""
    from tracker.runner import FOLDER_NOT_FOUND

    run = a_pass(Engagement(path=tmp_path / "Test Household" / "no-such-client"), today=SATURDAY)
    assert run.error == FOLDER_NOT_FOUND
    assert "Test Household" not in run.error and "no-such-client" not in run.error


def test_an_unreadable_record_is_recorded_not_raised(tmp_path):
    folder = tmp_path / "Broken 2025"
    folder.mkdir()
    ledger.path_for(folder).write_text("this is not a record\n", encoding="utf-8")
    run = a_pass(Engagement(path=folder), today=SATURDAY)
    assert run.error and run.ok is False


def test_one_broken_engagement_does_not_stop_the_others(tmp_path, samples):
    good = build_engagement(tmp_path, samples, name="Smith TY2025")
    broken = Engagement(path=tmp_path / "Ghost 2025")
    later = build_engagement(tmp_path, samples, name="Jones TY2025")

    report = run_registry(
        Registry(source=tmp_path,
                 engagements=[good, broken, later]),
        today=SATURDAY,
    )

    assert len(report.errors) == 1
    assert len(report.processed) == 2
    assert (good.path / DRAFT_FILENAME).exists()
    assert (later.path / DRAFT_FILENAME).exists(), (
        "an engagement after the broken one must still be processed"
    )


def test_inactive_engagements_are_skipped_not_failed(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples, active=False)
    run = a_pass(engagement, today=SATURDAY)
    assert run.ok and run.skipped.startswith("inactive")
    assert run.filed == 0


def test_only_selects_a_subset(tmp_path, samples):
    # Two households: a pass is a household's since decision 125, so
    # ``--only`` picks the household the named return is in and the other
    # is never touched.
    smith = build_engagement(tmp_path, samples, household="Smith Family", name="Smith TY2025")
    jones = build_engagement(tmp_path, samples, household="Jones Family", name="Jones TY2025")
    registry = Registry(source=tmp_path,
                        engagements=[smith, jones])

    report = run_registry(registry, today=SATURDAY, only="jones")

    assert len(report.runs) == 1
    assert (jones.path / DRAFT_FILENAME).exists()
    assert not (smith.path / DRAFT_FILENAME).exists()


def test_the_pass_holds_the_machines_answers_for_one_household_at_a_time(tmp_path, samples, monkeypatch):
    """P207: at 1,000 households a pass with nothing new asked the disk 6.9
    million times, nearly all of them the same few questions. Each
    household is served inside its own hold, dropped before the next, so a
    change a person makes between two households is seen by the second."""
    from tracker import hold, runner

    smith = build_engagement(tmp_path, samples, household="Smith Family", name="Smith TY2025")
    jones = build_engagement(tmp_path, samples, household="Jones Family", name="Jones TY2025")
    holds = []
    real = runner.run_household

    def watched(household, returns, **kwargs):
        kind, before = hold._HOLDING, dict(hold._HELD)
        runs = real(household, returns, **kwargs)
        holds.append((household.name, kind, before, len(hold._HELD)))
        return runs

    monkeypatch.setattr(runner, "run_household", watched)
    report = run_registry(Registry(source=tmp_path, engagements=[smith, jones]), today=SATURDAY)

    assert sorted(name for name, _, _, _ in holds) == ["Jones Family", "Smith Family"]
    assert all(kind == hold.HOLD_HOUSEHOLD for _, kind, _, _ in holds)
    assert [before for _, _, before, _ in holds] == [{}, {}], \
        "each household starts from nothing held: what the first held is dropped before the second"
    assert all(after > 0 for _, _, _, after in holds), "and each holds the answers it asked"
    assert hold._HELD is None
    assert all(not run.error for run in report.runs)


def test_an_app_too_deep_for_its_reader_is_warned_of_once_in_the_pass(tmp_path, samples, monkeypatch):
    """SPEC-169 section 9: an app whose folder is too deep for the
    reader's libraries says so once in the pass's warnings - and so in the
    console and the run log - rather than every scan waiting in silence."""
    from tracker import ocr

    monkeypatch.setattr(ocr, "reader_path_warning", lambda: ocr.READER_PATH_WARNING)
    smith = build_engagement(tmp_path, samples, household="Smith Family", name="Smith TY2025")

    report = run_registry(Registry(source=tmp_path, engagements=[smith]), today=SATURDAY)

    assert report.warnings.count(ocr.READER_PATH_WARNING) == 1
    assert ocr.READER_PATH_WARNING in format_report(report)


def test_an_unknown_reminder_mode_fails_loudly(tmp_path):
    registry = Registry(source=tmp_path, engagements=[])
    with pytest.raises(ValueError, match="reminders must be one of"):
        run_registry(registry, reminders="sometimes")


# ---------------------------------------------------------------- reporting ----


def test_the_report_says_what_day_it_is_and_never_claims_a_send(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    text = format_report(run_registry(
        Registry(source=tmp_path, engagements=[engagement]),
        today=SATURDAY,
    ))
    assert DRAFT_DAY in text
    assert "drafting reminders" in text
    assert "nothing has been sent to anyone" in text.lower()
    assert "1 processed, 0 failed, 1 draft(s) written" in text


def test_a_weekday_report_says_why_there_are_no_drafts(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    text = format_report(run_registry(
        Registry(source=tmp_path, engagements=[engagement]),
        today=FRIDAY,
    ))
    assert "no reminders today" in text
    assert "0 draft(s) written" in text


def test_the_log_appends_rather_than_replaces(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    registry = Registry(source=tmp_path, engagements=[engagement])
    log = tmp_path / LOG_FILENAME

    append_log(log, run_registry(registry, today=FRIDAY))
    append_log(log, run_registry(registry, today=SATURDAY))

    lines = log.read_text(encoding="utf-8").splitlines()
    firsts = [line for line in lines if line.startswith("[")]
    assert [line.split("] ")[1][:10] for line in firsts] == ["2026-03-13", "2026-03-14"]
    assert len([line for line in lines if line.strip().startswith("counts ")]) == 2


# ------------------------------------------------------- discovery end to end ----


def test_a_clients_folder_drives_a_real_run_with_nothing_registered(tmp_path, samples):
    engagement = build_engagement(tmp_path / "Clients", samples, household="Smith Family")
    # Thirteen days from the draft day, so the pass writes the stage that
    # names the target (decision 117) and the date in the record is one a
    # person can read in the letter.
    due = SATURDAY + dt.timedelta(days=13)
    edit_details(engagement.path, client="John Smith", due=due,
                 firm="J Park & Associates, CPA")

    report = run_registry(discover_engagements(tmp_path / "Clients"), today=SATURDAY)

    assert len(report.processed) == 1
    draft = (engagement.path / DRAFT_FILENAME).read_text(encoding="utf-8")
    assert "Hi John Smith," in draft
    assert due.strftime("%B %d, %Y") in draft
    assert "J Park & Associates, CPA" in draft


def test_an_engagement_whose_record_cannot_be_read_fails_alone(tmp_path, samples):
    build_engagement(tmp_path / "Clients", samples, name="Good")
    bad = build_engagement(tmp_path / "Clients", samples, name="Bad 2025", drops=())
    with ledger.path_for(bad.path).open("ab") as handle:
        handle.write(b"{this line is not an event}\n")           # a corrupt journal line

    report = run_registry(discover_engagements(tmp_path / "Clients"), today=FRIDAY)
    outcomes = {r.engagement.path.name: r for r in report.runs}
    assert outcomes["Good"].ok
    assert outcomes["Bad 2025"].error.startswith(RECORD_UNREADABLE.split("{")[0])
    assert "does not read as an event" in outcomes["Bad 2025"].error


def _a_malformed_line_is_one_folders_problem(tmp_path, samples, line: dict, said: str) -> None:
    """One synced journal carrying a line of the right JSON and the wrong
    shape: that engagement is listed with a problem that names the line,
    every other engagement is run, and the pass ends by its own rule (an
    engagement error is exit 1) rather than in a traceback inside
    discovery before one document is filed."""
    import shutil

    build_engagement(tmp_path / "Clients", samples, name="Good")
    bad = build_engagement(tmp_path / "Clients", samples, name="Bad 2025", drops=())
    lines = ledger.read_events(bad.path)
    written_elsewhere(bad.path, {ledger.EVENT_KEY: line.pop("event"),
                                 ledger.AT_KEY: "2026-01-01T00:00:00Z", **line})
    try:
        loaded = discover_engagements(tmp_path / "Clients")
        problems = {e.path.name: e.problem for e in loaded.engagements}
        assert problems["Good"] == ""
        assert f"line {len(lines) + 1}" in problems["Bad 2025"] and said in problems["Bad 2025"], problems
        assert main([str(tmp_path / "Clients"), "--date", FRIDAY.isoformat(), "--dry-run"]) == 1
        report = run_registry(discover_engagements(tmp_path / "Clients"), today=FRIDAY)
        outcomes = {r.engagement.path.name: r for r in report.runs}
        assert outcomes["Good"].ok
        assert outcomes["Bad 2025"].error.startswith(RECORD_UNREADABLE.split("{")[0])
        assert said in outcomes["Bad 2025"].error
    finally:
        shutil.rmtree(bad.path)          # the store cannot hold it, so the after-test check must not meet it


def test_a_rules_line_of_the_wrong_shape_is_one_folders_problem_and_the_pass_goes_on(tmp_path, samples):
    _a_malformed_line_is_one_folders_problem(
        tmp_path, samples, {"event": ledger.RULES_CHANGED, ledger.RULES_KEY: ["not-a-row"],
                            ledger.REMOVED_KEY: [], ledger.INFO_KEY: {}},
        "carries a rule that is not a row")


def test_a_statuses_entry_of_the_wrong_shape_is_one_folders_problem_and_the_pass_goes_on(tmp_path, samples):
    _a_malformed_line_is_one_folders_problem(
        tmp_path, samples, {"event": ledger.SCANNED, ledger.STATUSES_KEY: {"A01": ["Received"]}},
        "carries a status that is not a mapping")


def test_rows_the_rules_cannot_act_on_are_reported_not_buried(tmp_path, samples):
    folder = make_engagement(tmp_path, [RequestItem(identifier="A01", document="Anything")],
                             return_name="Loose 2025")
    engagement = Engagement(path=folder)
    run = a_pass(engagement, today=FRIDAY)
    assert run.ok
    assert any("never be filed automatically" in w for w in run.warnings)
    text = format_report(run_registry(Registry(source=tmp_path, engagements=[engagement]), today=FRIDAY))
    assert "! Row 1 (A01)" in text


def test_not_applicable_and_accepted_rows_are_not_outstanding(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples, drops=())
    edit_rows(engagement.path, A01={"manual_override": Override.ACCEPTED,
                                    "override_reason": "Client confirmed this is the final version"},
              A02={"manual_override": Override.NOT_APPLICABLE})
    run = a_pass(engagement, today=FRIDAY)
    assert run.ok
    assert run.statuses.get(Status.RECEIVED) == 1          # the accepted row
    assert Override.NOT_APPLICABLE not in run.statuses
    assert run.outstanding == len(DEMO_ITEMS) - 2


def test_a_row_added_in_the_editor_is_asked_for_by_the_next_run(tmp_path, samples):
    """Decision 168: no folder is made for it - its copies will sit in
    Prepared itself - and it is Missing, never "folder not found"."""
    from tracker.scaffold import README_NAME

    engagement = build_engagement(tmp_path, samples, drops=())
    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement.path)]
    rows.append(RequestItem(identifier="Z01", document="Rental Property Records", period="TY2025",
                            allowed_extensions=("pdf",), any_keywords=("schedule e",)))
    save_rules(engagement.path, rows, load_engagement_info(engagement.path))
    run = a_pass(engagement, today=FRIDAY)
    assert run.ok
    assert not any(p.name.startswith("Z01") for p in (engagement.path / PREPARED_DIR_NAME).iterdir())
    assert "Z01 - Rental Property Records" in (inbox_of(engagement.path) / README_NAME).read_text(encoding="utf-8")
    assert run.statuses.get(Status.MISSING, 0) >= 1 and "folder not found" not in str(run.statuses)


def test_a_rolled_forward_engagement_is_retired_by_its_successor(tmp_path, samples):
    from tracker.registry import discover_engagements

    prior = build_engagement(tmp_path / "Clients", samples, household="Smith Family",
                             name="Smith 2025")
    edit_details(prior.path, client="John")
    new = build_engagement(tmp_path / "Clients", samples, household="Smith Family",
                           name="Smith 2026", drops=())
    edit_details(new.path, client="John", rolled_from=str(prior.path))

    registry = discover_engagements(tmp_path / "Clients")
    by_name = {e.path.name: e for e in registry.engagements}
    assert by_name["Smith 2025"].active is False
    # The successor is named as everything that names a return names one
    # since decision 125: the household, the year and the return.
    assert by_name["Smith 2025"].superseded_by == by_name["Smith 2026"].label
    assert by_name["Smith 2026"].active is True

    report = run_registry(registry, today=SATURDAY)
    outcomes = {r.engagement.path.name: r for r in report.runs}
    assert outcomes["Smith 2025"].skipped == SKIP_ROLLED_FORWARD.format(
        successor=by_name["Smith 2026"].label)
    assert not (prior.path / DRAFT_FILENAME).exists()          # last year is not chased
    # The inbox is the household's since decision 125, so what was waiting
    # in it was sorted by the return that is still open; the prior's own
    # folder was not touched, and its record says nothing new.
    assert (originals_of(new.path) / f"W-2 John Smith {YEAR}.pdf").exists()
    assert read_index(prior.path) == []
    assert outcomes["Smith 2026"].ok


def test_strays_in_prepared_reach_the_run_report(tmp_path, samples):
    from tracker import reasons
    from tracker.scanner import UNCLAIMED_FILE

    engagement = build_engagement(tmp_path, samples, drops=())
    (engagement.path / PREPARED_DIR_NAME / "loose.txt").write_text("x", encoding="utf-8")
    (engagement.path / PREPARED_DIR_NAME / "my notes").mkdir()
    run = a_pass(engagement, today=FRIDAY)
    assert run.ok
    assert UNCLAIMED_FILE.format(name="loose.txt", prepared=PREPARED_DIR_NAME) in run.warnings
    assert reasons.PERSONS_FOLDER.format(folder="my notes", prepared=PREPARED_DIR_NAME) in run.warnings


# ----------------------------- an approved draft, in the pass (decision 118) ----
# A person read this week's draft in the app and approved it. Until the next
# draft day the pass treats it exactly as it treats one somebody edited:
# never overwritten, a regenerated draft beside it, and the practice page
# says so instead of a stage.


def approve_the_standing_draft(engagement_dir, today):
    """What the app's approve command leaves behind, without the app: the
    draft_approved event for the file that is standing, under the lock."""
    from tracker.locking import engagement_lock
    from tracker.reminder import approved_event, draft_reminder

    draft = draft_reminder(engagement_dir, today=today)
    with engagement_lock(engagement_dir):
        store.record(store.connect(), engagement_dir,
                     approved_event(draft, engagement_dir / DRAFT_FILENAME))


def test_an_approved_draft_is_not_overwritten_by_the_days_repeat_and_is_superseded_next_week(
        tmp_path, samples, stamped_on):
    engagement = build_engagement(tmp_path, samples)
    first = pass_on(stamped_on, engagement, SATURDAY).drafted
    assert first == engagement.path / DRAFT_FILENAME
    kept = first.read_bytes()
    approve_the_standing_draft(engagement.path, SATURDAY)

    # The draft day's repeat: the approved file is left, and the week's
    # regenerated draft lands beside it exactly as it does beside an edit.
    repeat = pass_on(stamped_on, engagement, SATURDAY)
    assert first.read_bytes() == kept, "an approval must never be clobbered"
    assert repeat.drafted.name == NEW_DRAFT_FILENAME
    assert repeat.approved is True

    # Next draft week the approval is spent: the week's draft is written
    # as the week's draft, and the page stops saying approved.
    (engagement.path / NEW_DRAFT_FILENAME).unlink()
    later = pass_on(stamped_on, engagement, SATURDAY + dt.timedelta(days=7))
    assert later.drafted == first and later.approved is False
    assert first.read_bytes() != kept or is_unedited(first)


def test_a_draft_edited_after_its_approval_is_left_alone_and_said_as_approved_then_edited(
        tmp_path, samples, stamped_on):
    """An edit after the approval lapses it (decision 190): the pass leaves
    the file as it leaves any edited one, and the run log and the practice
    page say "Approved, Then Edited" rather than "approved"."""
    from tracker.reminder import APPROVED_THEN_EDITED
    from tracker.status_page import _drafted_cell

    engagement = build_engagement(tmp_path, samples)
    first = pass_on(stamped_on, engagement, SATURDAY).drafted
    approve_the_standing_draft(engagement.path, SATURDAY)
    first.write_bytes(first.read_bytes() + b"\r\nPS: one more thing.\r\n")
    kept = first.read_bytes()

    repeat = pass_on(stamped_on, engagement, SATURDAY)
    assert first.read_bytes() == kept, "an edited draft is never overwritten"
    assert repeat.approved is False and repeat.approval_lapsed is True
    assert APPROVED_THEN_EDITED in repeat.summary()
    assert _drafted_cell(repeat) == APPROVED_THEN_EDITED


def test_an_approved_draft_survives_a_hold_like_an_edited_one(tmp_path, samples, stamped_on):
    """A hold retires the run's own unedited drafts. One a person approved
    is not the run's - it is this week's answer, and it stays."""
    engagement = build_chased_engagement(tmp_path, samples)
    first = pass_on(stamped_on, engagement, SATURDAY).drafted
    assert first == engagement.path / DRAFT_FILENAME
    kept = first.read_bytes()
    approve_the_standing_draft(engagement.path, SATURDAY)

    make_ambiguous(engagement.path)
    run = pass_on(stamped_on, engagement, SATURDAY)
    assert run.held and run.drafted is None
    assert first.exists() and first.read_bytes() == kept


# ------------------------------- errors are classes, end to end (decision 190) ----


def test_no_byte_of_a_damaged_document_reaches_the_record_store_pages_or_run_log(
        tmp_path, tmp_path_factory, monkeypatch, capsys):
    """A broken PDF, a zip and an email, each of whose parser is made to
    raise with words in a W-2's shape (fabricated: nobody's number, nobody's
    name), and a PDF the filer itself fails on. After a real pass, the run
    log, the practice page and the app, not a byte of those words is in any
    file under the root - the record, the store, both pages, the log - nor
    in what the app says. They reach the debug log, and only it."""
    import io
    import json
    import logging
    import zipfile

    from tracker import api, containers, content_check, errors, filer, validators
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    number, name = "123-45-6789", "Jane Fabricated"
    quoted = f"bad object near 'SSN {number} {name}'"

    def quotes_the_document(*_args, **_kwargs):
        raise ValueError(quoted)

    real_zip = zipfile.ZipFile

    def zip_that_quotes(file, *args, **kwargs):
        if isinstance(file, io.BytesIO):            # the container's own opening, nothing else
            raise zipfile.BadZipFile(quoted)
        return real_zip(file, *args, **kwargs)

    real_decide = filer._decide_across

    def decide(drop, *args, **kwargs):
        if drop.name == "boom.pdf":
            raise ValueError(quoted)
        return real_decide(drop, *args, **kwargs)

    monkeypatch.setattr(validators, "PdfReader", quotes_the_document)
    monkeypatch.setattr(content_check, "extract_text", quotes_the_document)
    monkeypatch.setattr(containers.zipfile, "ZipFile", zip_that_quotes)
    import email  # imported at call time since decision 193 (S2): patched where it is read

    monkeypatch.setattr(email, "message_from_bytes", quotes_the_document)
    monkeypatch.setattr(filer, "_decide_across", decide)

    kept: list[str] = []

    class Keeper(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            kept.append(record.getMessage())

    keeper = Keeper(level=logging.DEBUG)
    logging.getLogger(errors.DEBUG_LOGGER).addHandler(keeper)
    try:
        w2 = RequestItem(identifier="A01", document="W-2", period="TY2025", allowed_extensions=("pdf",),
                         min_size_kb=0, required_keywords=("W-2",))
        engagement = make_engagement(tmp_path, [w2])
        inbox = inbox_of(engagement)
        (inbox / "W2.pdf").write_bytes(b"%PDF-1.4\nbroken\n%%EOF\n")
        (inbox / "boom.pdf").write_bytes(b"%PDF-1.4\nalso broken\n%%EOF\n")
        (inbox / "docs.zip").write_bytes(b"PK\x03\x04 broken")
        (inbox / "mail.eml").write_bytes(b"From: someone@example.invalid\n\nbody\n")

        report = run_registry(discover_engagements(tmp_path), today=FRIDAY, reminders=REMINDERS_NEVER)
        append_log(tmp_path / LOG_FILENAME, report)
        write_status_page(tmp_path, report)
        monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path_factory.mktemp("app")))
        set_clients_root(tmp_path)
        assert api.main(["state", api.ENGAGEMENT_FLAG, str(engagement)]) == 0
        said_to_the_app = capsys.readouterr().out
    finally:
        logging.getLogger(errors.DEBUG_LOGGER).removeHandler(keeper)

    rows = {row.original_name: row.reason for row in read_index(engagement)}
    assert "(ValueError)" in rows["W2.pdf"]
    assert "could not be filed (ValueError)" in rows["boom.pdf"]
    assert "(BadZipFile)" in rows["docs.zip"]
    assert "(ValueError)" in rows["mail.eml"]
    written = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert any(path.name == STATUS_PAGE_FILENAME for path in written)
    assert any(path.name == LOG_FILENAME for path in written)
    for path in written:
        data = path.read_bytes()
        assert number.encode() not in data and name.encode() not in data, path
    json.loads(said_to_the_app)
    assert number not in said_to_the_app and name not in said_to_the_app
    assert any(quoted in one for one in kept)


# ------------------------------------ what an earlier version left (decision 186) ----


def test_what_an_earlier_version_left_is_named_for_deletion_and_never_deleted(tmp_path, monkeypatch):
    """Decision 186: the delete group - the store and its side files, the
    pass-order hint, 159's last-pass file, 193's error log (and a rotated
    copy) and ``passes`` folder, the OCR scratch folder and the root's old
    run log - is named in :data:`LEFT_BEHIND`, never touched."""
    from tracker.errlog import ERROR_LOG_FILENAME
    from tracker.progress import PASSES_DIRNAME
    from tracker.settings import ENV_SETTINGS_DIR, OCR_SCRATCH_DIRNAME, data_home

    settings = tmp_path / "settings"
    (settings / OCR_SCRATCH_DIRNAME).mkdir(parents=True)
    (settings / OCR_SCRATCH_DIRNAME / "page-1.png").write_bytes(b"a client's page")
    (settings / PASSES_DIRNAME).mkdir()
    (settings / PASSES_DIRNAME / "7.progress.json").write_bytes(b"a pass's last line")
    left = {name: settings / name for name in (store.STORE_FILENAME, store.STORE_WAL_FILENAME,
                                                pass_order.PASS_ORDER_FILENAME,
                                                run_log.LAST_PASS_FILENAME,
                                                ERROR_LOG_FILENAME, f"{ERROR_LOG_FILENAME}.1")}
    for name, path in left.items():
        path.write_bytes(name.encode())
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    monkeypatch.setenv(store.ENV_STORE, str(data_home() / store.STORE_FILENAME))
    store.close()
    old_log = tmp_path / "Clients" / LOG_FILENAME        # the run log before 186d named clients
    old_log.parent.mkdir()
    old_log.write_text("an old log naming a client\n", encoding="utf-8")

    report = run_registry(Registry(source=tmp_path / "Clients", engagements=[]), today=SATURDAY,
                          dry_run=True)

    named = [warning for warning in report.warnings if warning.startswith(runner_module.LEFT_BEHIND[:20])]
    assert named == [runner_module.LEFT_BEHIND.format(
        paths="; ".join(str(settings.resolve() / name) for name in (
            store.STORE_FILENAME, store.STORE_WAL_FILENAME, pass_order.PASS_ORDER_FILENAME,
            run_log.LAST_PASS_FILENAME, ERROR_LOG_FILENAME, f"{ERROR_LOG_FILENAME}.1",
            PASSES_DIRNAME, OCR_SCRATCH_DIRNAME)) + f"; {old_log}",
        home=data_home())]
    assert run_log.CODE_LEFT_BEHIND_TO_MOVE not in report.warning_codes    # nothing to move
    assert (settings / PASSES_DIRNAME / "7.progress.json").read_bytes() == b"a pass's last line"
    assert old_log.read_text(encoding="utf-8") == "an old log naming a client\n"
    for name, path in left.items():
        assert path.read_bytes() == name.encode()                 # named, never touched
    assert (settings / OCR_SCRATCH_DIRNAME / "page-1.png").read_bytes() == b"a client's page"


def test_the_checkpoint_and_recovered_records_left_behind_are_named_to_move_never_to_delete(
        tmp_path, monkeypatch):
    """Decision 186 on 159 (security principle 10): the record checkpoint
    cannot be made again and ``recovered`` holds evidence, so one an older
    version left beside the settings file is named in its own sentence,
    :data:`LEFT_BEHIND_TO_MOVE`, with its own code - never in the sentence
    that says delete - and is never touched."""
    from tracker import checkpoint
    from tracker.settings import ENV_SETTINGS_DIR, data_home

    settings = tmp_path / "settings"
    (settings / store.RECOVERED_DIR).mkdir(parents=True)
    (settings / store.RECOVERED_DIR / "Test Household-export.jsonl").write_bytes(b"a record's lines")
    (settings / checkpoint.CHECKPOINT_FILENAME).write_bytes(b"an old checkpoint")
    (settings / store.STORE_FILENAME).write_bytes(b"an old store")
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    monkeypatch.setenv(store.ENV_STORE, str(data_home() / store.STORE_FILENAME))
    store.close()

    report = run_registry(Registry(source=tmp_path / "Clients", engagements=[]), today=SATURDAY,
                          dry_run=True)

    home = data_home()
    to_delete = runner_module.LEFT_BEHIND.format(paths=str(settings.resolve() / store.STORE_FILENAME),
                                                 home=home)
    to_move = runner_module.LEFT_BEHIND_TO_MOVE.format(
        paths=f"{settings.resolve() / checkpoint.CHECKPOINT_FILENAME}; "
              f"{settings.resolve() / store.RECOVERED_DIR}", home=home)
    said = dict(zip(report.warning_codes, report.warnings, strict=True))
    assert said[run_log.CODE_LEFT_BEHIND] == to_delete
    assert said[run_log.CODE_LEFT_BEHIND_TO_MOVE] == to_move
    assert checkpoint.CHECKPOINT_FILENAME not in to_delete and store.RECOVERED_DIR not in to_delete
    assert "never delete" in to_move
    assert (settings / checkpoint.CHECKPOINT_FILENAME).read_bytes() == b"an old checkpoint"
    assert (settings / store.RECOVERED_DIR / "Test Household-export.jsonl").read_bytes() == b"a record's lines"


def test_the_store_in_use_is_never_named_as_left_behind(tmp_path, monkeypatch):
    """The suite's own default puts the store beside a settings folder; the
    store a pass is using, its side files, the hint and decision 159's
    checkpoint, ``recovered`` and last-pass file, and decision 193's error
    log and ``passes`` folder, beside it are never "left over"."""
    from tracker import checkpoint
    from tracker.errlog import ERROR_LOG_FILENAME
    from tracker.progress import PASSES_DIRNAME
    from tracker.settings import ENV_SETTINGS_DIR

    app = tmp_path / "app"
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(app))
    store.connect()                                              # the fixture's store, in use
    for name in (store.STORE_WAL_FILENAME, pass_order.PASS_ORDER_FILENAME,
                 checkpoint.CHECKPOINT_FILENAME, checkpoint.CHECKPOINT_JOURNAL_FILENAME,
                 checkpoint.CHECKPOINT_DAMAGED_FILENAME, run_log.LAST_PASS_FILENAME,
                 ERROR_LOG_FILENAME, f"{ERROR_LOG_FILENAME}.1",
                 f"{store.STORE_FILENAME}.v3.old", f"{checkpoint.CHECKPOINT_FILENAME}.v1.old"):
        if not (app / name).exists():                              # the store may have made one
            (app / name).write_bytes(b"")
    (app / store.RECOVERED_DIR).mkdir(exist_ok=True)
    (app / PASSES_DIRNAME).mkdir(exist_ok=True)
    assert Path(store.store_path()).parent == app
    assert runner_module.left_behind(tmp_path) == []
    assert runner_module.left_behind_warnings(tmp_path) == []


def test_159s_set_asides_and_the_checkpoints_journal_left_behind_are_named_in_their_groups(
        tmp_path, monkeypatch):
    """The rebase review of 186 (SF3, N1): what 159's set-aside renamed out of
    the way beside the program is client data too. The store's (rebuilt from
    the records) is named to delete; the checkpoint's set-asides, a copy a
    person renamed ``.damaged`` and its rollback journal are named to move,
    with it - none is ever touched."""
    from tracker import checkpoint
    from tracker.settings import ENV_SETTINGS_DIR, data_home

    settings = tmp_path / "settings"
    settings.mkdir()
    to_delete = [f"{store.STORE_FILENAME}.v3.old", f"{store.STORE_FILENAME}.v3.old-wal",
                 f"{store.STORE_FILENAME}.v3.old.1"]
    to_move = [checkpoint.CHECKPOINT_FILENAME, checkpoint.CHECKPOINT_JOURNAL_FILENAME,
               checkpoint.CHECKPOINT_DAMAGED_FILENAME, f"{checkpoint.CHECKPOINT_FILENAME}.v1.old"]
    for name in to_delete + to_move:
        (settings / name).write_bytes(name.encode())
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    monkeypatch.setenv(store.ENV_STORE, str(data_home() / store.STORE_FILENAME))
    store.close()

    said = dict(runner_module.left_behind_warnings(None))

    def named(code, before):
        return sorted(Path(one).name for one in said[code].split(": ", 1)[1].split(before, 1)[0].split("; "))

    assert named(run_log.CODE_LEFT_BEHIND, ". They hold") == sorted(to_delete)
    assert named(run_log.CODE_LEFT_BEHIND_TO_MOVE, ". These cannot") == sorted(to_move)
    for name in to_delete + to_move:
        assert (settings / name).read_bytes() == name.encode()      # named, never touched


def test_the_checkpoints_side_files_beside_the_store_in_use_are_never_named_left_behind(tmp_path, monkeypatch):
    """P214: while a command runs, the live checkpoint keeps its write-ahead
    log and shared memory beside the store in use (the suite's own fixture
    puts it beside the settings folder); neither is "left over"."""
    from tracker import checkpoint
    from tracker.settings import ENV_SETTINGS_DIR

    app = tmp_path / "app"
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(app))
    store.connect()
    for name in (checkpoint.CHECKPOINT_FILENAME, checkpoint.CHECKPOINT_WAL_FILENAME,
                 checkpoint.CHECKPOINT_SHM_FILENAME):
        if not (app / name).exists():
            (app / name).write_bytes(b"")
    assert Path(store.store_path()).parent == app
    assert runner_module.left_behind(tmp_path) == []
    assert runner_module.left_behind_warnings(tmp_path) == []


def test_a_checkpoint_log_left_beside_the_program_is_named_to_move_never_to_delete(tmp_path, monkeypatch):
    """P214: a write-ahead log holds committed writes its checkpoint does
    not yet, so one an earlier version left beside the program - with its
    shared memory - is named in the move group with the checkpoint, never
    in the sentence that says delete, and is never touched."""
    from tracker import checkpoint
    from tracker.settings import ENV_SETTINGS_DIR, data_home

    settings = tmp_path / "settings"
    settings.mkdir()
    to_move = [checkpoint.CHECKPOINT_FILENAME, checkpoint.CHECKPOINT_WAL_FILENAME,
               checkpoint.CHECKPOINT_SHM_FILENAME]
    for name in to_move:
        (settings / name).write_bytes(name.encode())
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    monkeypatch.setenv(store.ENV_STORE, str(data_home() / store.STORE_FILENAME))
    store.close()

    said = dict(runner_module.left_behind_warnings(None))
    assert run_log.CODE_LEFT_BEHIND not in said
    moving = said[run_log.CODE_LEFT_BEHIND_TO_MOVE].split(": ", 1)[1].split(". These cannot", 1)[0]
    assert sorted(Path(one).name for one in moving.split("; ")) == sorted(to_move)
    for name in to_move:
        assert (settings / name).read_bytes() == name.encode()


def test_a_pass_serves_no_household_while_the_old_checkpoint_sits_beside_the_program(tmp_path, monkeypatch):
    """The rebase review of 186 (MF1): a machine upgraded before its
    checkpoint was moved. The scheduled pass makes no fresh checkpoint - that
    would trust every record "as it is" - reaches its root, writes its page
    (the refusal first) and its log (the code, never the sentence), serves
    no household, exits non-zero and says why in the last-pass file."""
    import json

    from tracker import checkpoint
    from tracker.settings import data_home, set_clients_root, settings_dir

    clients = tmp_path / "Clients"
    make_engagement(clients, [RequestItem(identifier="A01", document="W-2")], household="Smith Family")
    set_clients_root(clients)
    old = settings_dir() / checkpoint.CHECKPOINT_FILENAME    # the fixture's: 159's layout
    store.close()           # its write-ahead log folded in and let go of first (P214)
    before = old.read_bytes()
    monkeypatch.setenv(store.ENV_STORE, str(data_home() / store.STORE_FILENAME))
    new = checkpoint.path_for(store.store_path())

    code = main([SETTINGS_FLAG, str(settings_dir()), "--reminders", "never", "--log"])

    assert code == 1
    page = html.unescape((clients / STATUS_PAGE_FILENAME).read_text(encoding="utf-8"))
    first = page[page.index(status_page.STATUS_RECORDS_HEADING):].split("<li>", 2)[1]
    assert first.startswith("No household was served this pass") and "No record checkpoint was made" in first
    logged = run_log.log_path().read_text(encoding="utf-8")
    assert f"{run_log.CODE_CHECKPOINT_NOT_PROVED}=1" in logged
    assert "No record checkpoint was made" not in logged
    written = json.loads(run_log.last_pass_path().read_text(encoding="utf-8"))
    assert written["reason_code"] == run_log.PASS_CHECKPOINT_LEFT_BEHIND
    assert not new.exists() and old.read_bytes() == before


# ------------------------------------------- a budget in counts (P223) ----


def _an_idle_pass_counted(tmp_path, samples, monkeypatch) -> dict:
    """One scheduled pass with nothing new over the suite's three-household
    made-up firm, after one settling pass: what the budget counts, by the
    code alone - never seconds, never questions to the disk."""
    import math

    from tracker import checkpoint, hold, settings

    root = tmp_path / "Clients"
    _three_households(root, samples)
    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER) == 0     # settles
    store.close()
    counted = {"statements": 0, "rules": [], "checkpoints": 0, "hint writes": 0, "unheld": 0}
    real_execute = store._Cursor.execute

    def execute(self, *args, **kwargs):
        counted["statements"] += 1
        return real_execute(self, *args, **kwargs)

    real_rules, real_connect = store.rules, checkpoint._connect
    real_write = fsio.write_text_atomically
    real_resolved, real_data_home = hold.resolved, settings.data_home

    def rules(conn, folder):
        counted["rules"].append(str(folder))
        return real_rules(conn, folder)

    def connect(path):
        counted["checkpoints"] += 1
        return real_connect(path)

    def write(path, *args, **kwargs):
        counted["hint writes"] += Path(path).name == pass_order.PASS_ORDER_FILENAME
        return real_write(path, *args, **kwargs)

    def unheld(real):
        def asked(*args, **kwargs):
            counted["unheld"] += hold._HELD is None
            return real(*args, **kwargs)
        return asked

    with monkeypatch.context() as patch:
        patch.setattr(store._Cursor, "execute", execute)
        patch.setattr(store, "rules", rules)
        patch.setattr(checkpoint, "_connect", connect)
        for module in (pass_order, status_page):
            patch.setattr(module, "write_text_atomically", write)
        patch.setattr(hold, "resolved", unheld(real_resolved))
        patch.setattr(settings, "data_home", unheld(real_data_home))
        assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER) == 0
    returns = len(set(counted["rules"])) or 1
    return {"statements per household": math.ceil(counted["statements"] / 3),
            "rules per return": max((counted["rules"].count(one) for one in set(counted["rules"])), default=0),
            "returns": returns, "checkpoints": counted["checkpoints"],
            "hint writes": counted["hint writes"], "unheld": counted["unheld"]}


#: The idle pass's counts measured once the speed round was built (pilot
#: P223), on Python 3.11 and 3.13 alike; the budget is each times 1.2,
#: rounded up, where a count is a measure rather than a rule.
IDLE_PASS_MEASURED = {"statements per household": 89, "unheld": 3}


def test_an_idle_pass_stays_within_its_budget(tmp_path, samples, monkeypatch):
    """P223: a budget in counts, so a change that quietly undoes the speed
    round fails here - in counts the code alone decides, the same on
    Windows and Linux, never seconds (four shared cores, the office PC's
    Defender) and never questions to the disk (one ``lstat`` a segment on
    Linux, two handle opens on Windows, and the test folder's depth).

    Measured after the build, one idle pass over three households: 89 store
    statements a household (123 before the round), ``store.rules`` once a
    return (9 before), one checkpoint connection for the whole pass (4
    before, one a question), one whole write of the pass-order hint, and 3
    machine questions (``hold.resolved``, ``settings.data_home``)
    outside any hold for the pass (111 before). A change that needs a
    higher budget raises it in the same commit with a decision row saying
    why. Run locally, in the gate, like every test (decisions 207, 211)."""
    import math

    counted = _an_idle_pass_counted(tmp_path, samples, monkeypatch)
    assert counted["returns"] == 3
    assert counted["statements per household"] <= math.ceil(
        IDLE_PASS_MEASURED["statements per household"] * 1.2), counted
    assert counted["rules per return"] <= 2, counted
    assert counted["checkpoints"] == 1, counted
    assert counted["hint writes"] == 1, counted
    assert counted["unheld"] <= math.ceil(IDLE_PASS_MEASURED["unheld"] * 1.2), counted
