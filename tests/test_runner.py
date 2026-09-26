"""Tests for tracker/runner.py — the weekly pass over every engagement.

The rules that matter here: reminders are drafted on Saturday and only on
Saturday, an edited draft survives the weekly run, one client's failure never
stops another client's run, an ambiguous request holds the whole reminder
and the draft is on the record (decision 115), and nothing is ever sent.

The pass reads the day of the last draft from the record, so a test that
tells the pass ``today`` is a day in March must stamp what the pass records
on that day: ``stamped_on`` does, and ``pass_on`` is a pass with it.
"""

import datetime as dt
import html
import re
from pathlib import Path

import pytest

import tracker.runner as runner_module
from tests.conftest import make_engagement, seed_index, written_elsewhere
from tests.samples import DEMO_ITEMS, PRIOR_YEAR, SCRATCH_PEOPLE, YEAR, build_samples
from tracker import ledger, store
from tracker.filer import NEEDS_REVIEW, IndexEntry, read_index
from tracker.layout import household_of, inbox_of, originals_of, root_of
from tracker.manifest import (
    EngagementInfo,
    Override,
    RequestItem,
    Status,
    load_engagement_info,
    save_rules,
)
from tracker.records import YES, rule_from_json
from tracker.registry import (
    SKIP_ROLLED_FORWARD,
    Engagement,
    Registry,
    discover_engagements,
    engagement_from,
)
from tracker.reminder import (
    CHANGED_ADDED,
    CHANGED_HEADING,
    DRAFT_BANNER,
    DRAFT_FILENAME,
    HELD_REFUSAL,
    NEW_DRAFT_FILENAME,
    is_unedited,
)
from tracker.runner import (
    DRAFT_WEEKDAY,
    LOG_FILENAME,
    NOTHING_OUTSTANDING,
    RECORD_UNREADABLE,
    REMINDERS_ALWAYS,
    REMINDERS_AUTO,
    REMINDERS_NEVER,
    SETTINGS_FLAG,
    STAGE_NOTE,
    STATUS_GENERATED,
    STATUS_HELD,
    STATUS_PAGE_FILENAME,
    WEEKDAY_NAMES,
    EngagementRun,
    RunReport,
    append_log,
    format_report,
    is_draft_day,
    last_drafted,
    main,
    run_household,
    run_registry,
    should_draft,
    write_status_page,
)
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    scaffold_engagement,
)
from tracker.settings import product_name

DRAFT_DAY = WEEKDAY_NAMES[DRAFT_WEEKDAY]

# The draft day is whatever the runner says it is; the dates follow it.
_WEEK_START = dt.date(2026, 3, 9)                      # a Monday
SATURDAY = _WEEK_START + dt.timedelta(days=DRAFT_WEEKDAY)  # the draft day
FRIDAY = SATURDAY - dt.timedelta(days=1)                # the day before
SUNDAY = SATURDAY + dt.timedelta(days=1)                # the day after


@pytest.fixture(scope="session")
def samples(tmp_path_factory):
    folder = tmp_path_factory.mktemp("samples")
    build_samples(folder)
    return folder


@pytest.fixture
def stamped_on(monkeypatch):
    """Stamp every line the record writes as if written at noon on ``day``.

    Since decision 115 the pass reads the day of the last draft from the
    ``drafted`` event's own stamp, not from a file time - so a test that
    tells the pass today is a Saturday in March must let the record say
    March too. ``ledger.stamp()`` is the one place a stamp is made.
    """
    def _on(day: dt.date) -> None:
        noon = dt.datetime.combine(day, dt.time(12)).astimezone(dt.UTC)
        monkeypatch.setattr(
            ledger, "stamp", lambda: noon.isoformat(timespec="seconds").replace("+00:00", "Z"))
    return _on


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


def a_pass(engagement, **kwargs):
    """One pass over this return's household, answering for the return.

    A pass is the household's since decision 125 - one inbox feeds every
    return of it - so this is what the scheduled job does to one folder,
    and the claims below are about the run it hands back for the return
    they named.
    """
    # A pass needs the practice (decision 132): the walk of the root this
    # return sits under, as the scheduled job hands it.
    kwargs.setdefault("registry", discover_engagements(root_of(engagement.path)))
    runs = run_household(household_of(engagement.path), [engagement], **kwargs)
    return next(run for run in runs if run.engagement.path == engagement.path)


def pass_on(stamped_on, engagement, day, **kwargs):
    """One pass on ``day``, with the record stamped that day."""
    stamped_on(day)
    return a_pass(engagement, today=day, **kwargs)


def drafted_events(engagement_dir):
    """The ``drafted`` lines on the record, without their stamps."""
    return [{k: v for k, v in e.items()
             if k not in (ledger.EVENT_KEY, ledger.AT_KEY) and k not in ledger.LINE_KEYS}
            for e in ledger.read_events(engagement_dir) if e[ledger.EVENT_KEY] == ledger.DRAFTED]


def test_the_runner_has_a_main_the_frozen_entry_can_call(tmp_path, samples, capsys):
    # api_entry.py runs the scheduled job through this function, so the
    # command line has to be one, not code under __main__.
    build_engagement(tmp_path, samples)
    assert main([str(tmp_path), "--dry-run", "--reminders", REMINDERS_NEVER]) == 0
    assert "Smith TY2025" in capsys.readouterr().out


def test_the_runners_console_guard_is_the_pages(tmp_path, samples, monkeypatch):
    # The scheduler's console is cp1252 and the report names the client's
    # folder. The guard that made this a run instead of a traceback (the
    # tenth reading) is tracker.page's now, shared by every command line.
    import io
    import sys

    # An arrow and a check mark: no letter of a second alphabet (decision 188).
    build_engagement(tmp_path, samples, name="Smith TY2025 \u2192 \u2713")
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", console)
    code = main([str(tmp_path), "--dry-run", "--reminders", REMINDERS_NEVER])
    console.flush()
    shown = console.buffer.getvalue().decode("cp1252")
    assert code == 0
    assert "Smith TY2025 \\u2192 \\u2713" in shown


def build_engagement(tmp_path, samples, drops=(f"W-2 John Smith {YEAR}.pdf",),
                     name="Smith TY2025", household="Test Household", **kwargs):
    """A scaffolded return with files waiting in its household's inbox."""
    # The return's details in the record are where the draft learns who the
    # client is; the Engagement dataclass only echoes it. It is read back
    # out of the record rather than typed here, because since decision 125
    # the pass reads the household, the year and the return name off it.
    from dataclasses import replace

    # The pile is addressed to the two people the samples name, so the
    # return lists them (decision 128) as the office's would.
    folder = make_engagement(tmp_path, DEMO_ITEMS,
                             EngagementInfo(client="John Smith", firm="J Park"),
                             household=household, return_name=name,
                             people=SCRATCH_PEOPLE, scaffold=False)
    result = scaffold_engagement(folder)
    for drop in drops:
        (result.inbox / drop).write_bytes((samples / drop).read_bytes())
    found = engagement_from(folder)
    return replace(found, info=replace(found.info, **kwargs)) if kwargs else found


def edit_rows(engagement_dir, **fields_by_identifier):
    """A person's edit of one or more rows in the app, saved as one event."""
    from dataclasses import replace

    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement_dir)]
    edited = [replace(row, **fields_by_identifier.get(row.identifier, {})) for row in rows]
    return save_rules(engagement_dir, edited, load_engagement_info(engagement_dir))


def edit_details(engagement_dir, **fields):
    """A person's edit of the engagement's details in the app."""
    from dataclasses import replace

    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement_dir)]
    return save_rules(engagement_dir, rows, replace(load_engagement_info(engagement_dir), **fields))


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


def test_the_draft_step_hands_the_pass_day_to_the_drafter_and_records_the_stage(tmp_path, samples, stamped_on):
    """Decision 117: the stage is measured from the day the pass is making,
    not from the clock - so a dated run writes the letter that day was
    owed - and the run says which rung it wrote, in its own line, on the
    practice page and on the record."""
    from tracker.reminder import STAGE_KEY, STAGE_LINE, stage_named
    from tracker.runner import STAGE_NOTE

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


def make_ambiguous(engagement_dir, identifier="C01"):
    """Edit the rule under a filed copy so the copy no longer satisfies it:
    the fingerprint moves, the copy is re-read, and the row fails the
    content check with a client-side reason nobody put there. The copy must
    already be filed - a pass has run - or the edited rule simply parks it."""
    return edit_rows(engagement_dir, **{identifier: {"required_keywords": ("form 8889",)}})


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
    assert "held 1" in logged and run.draft_note in logged
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
    from tracker.filer import unfile_document

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


def test_the_log_takes_a_name_utf8_cannot_hold(tmp_path, samples):
    # The eleventh reading: a lone surrogate in a client's file name is
    # reported every pass by name, and the run log - the unattended run's
    # only trace - died on it, losing every engagement's line.
    engagement = build_engagement(tmp_path, samples)
    run = EngagementRun(engagement=engagement)
    run.error = "bank statement \ud83d.pdf: cannot be handled under this name"
    report = RunReport(today=FRIDAY, reminders=REMINDERS_AUTO, dry_run=False, runs=[run])
    log = tmp_path / LOG_FILENAME
    append_log(log, report)
    text = log.read_text(encoding="utf-8")
    assert "bank statement" in text and "cannot be handled" in text


def test_the_log_appends_rather_than_replaces(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    registry = Registry(source=tmp_path, engagements=[engagement])
    log = tmp_path / LOG_FILENAME

    append_log(log, run_registry(registry, today=FRIDAY))
    append_log(log, run_registry(registry, today=SATURDAY))

    text = log.read_text(encoding="utf-8")
    assert text.count("Smith TY2025") == 2
    assert "2026-03-13" in text and "2026-03-14" in text


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


# ----------------------------------------------------- the practice on a page ----


def test_a_real_pass_writes_the_status_page_into_the_root_and_a_dry_run_does_not(tmp_path, samples, capsys):
    """The page is the pass's standing answer, so a pass that changed nothing
    on disk must not leave one - a dry run writes nothing, this included."""
    build_engagement(tmp_path, samples)
    page = tmp_path / STATUS_PAGE_FILENAME

    assert main([str(tmp_path), "--date", FRIDAY.isoformat(), "--dry-run"]) == 0
    assert not page.exists()

    assert main([str(tmp_path), "--date", FRIDAY.isoformat()]) == 0
    text = page.read_text(encoding="utf-8")
    assert product_name() in text
    assert STATUS_GENERATED.split("{")[0].strip() in text
    assert "Smith TY2025" in text
    assert "<script" not in text and "http" not in text, "one file, nothing fetched to render it"
    capsys.readouterr()


def test_the_page_lists_every_engagement_the_registry_finds_including_an_unreadable_one(
    tmp_path, samples, capsys
):
    """An engagement missing from the page is an engagement nobody chases. One
    whose record cannot be read is on it by name, and named as a problem."""
    clients = tmp_path / "Clients"
    good = build_engagement(clients, samples, name="Good TY2025")
    # A return of the same household whose journal will not parse: it sits
    # where a return sits, because a folder anywhere else is a misfit the
    # walk leaves alone rather than an engagement (decision 125).
    bad = good.path.parent / "Bad TY2025"
    bad.mkdir(parents=True)
    ledger.path_for(bad).write_text("{this line is not an event}\n", encoding="utf-8")

    assert main([str(clients), "--date", FRIDAY.isoformat()]) == 1
    text = (clients / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")

    assert "Good TY2025" in text
    assert text.count("Bad TY2025") >= 2            # its row, and the problems list
    assert RECORD_UNREADABLE.split("{")[0] in text
    capsys.readouterr()


def test_the_review_queue_lists_parked_files_newest_first_with_their_reasons(tmp_path, samples):
    """One queue across the practice, because the work is one queue: the file
    that arrived last night is at the top, whichever client sent it."""
    # Two households, because one inbox feeds every return of a household
    # since decision 125 and this claim is about two clients' files.
    older = build_engagement(tmp_path, samples, drops=("vacation photo.bmp",),
                             household="Older Family", name="Older TY2025")
    newer = build_engagement(tmp_path, samples, drops=("Mortgage Notes.docx",),
                             household="Newer Family", name="Newer TY2025")
    first = a_pass(older, today=FRIDAY, reminders=REMINDERS_NEVER)
    second = a_pass(newer, today=SATURDAY, reminders=REMINDERS_NEVER)
    assert first.review == 1 and second.review == 1

    page = write_status_page(tmp_path, RunReport(today=SATURDAY, runs=[first, second]))
    text = page.read_text(encoding="utf-8")

    assert text.index("Mortgage Notes.docx") < text.index("vacation photo.bmp")
    assert SATURDAY.isoformat() in text and FRIDAY.isoformat() in text
    for engagement in (older, newer):
        parked = [e for e in read_index(engagement.path)
                  if e.decision == NEEDS_REVIEW]
        assert parked
        for entry in parked:
            assert html.escape(entry.reason) in text, entry.reason


def test_the_pass_holds_one_lock_from_the_sort_through_the_scan(tmp_path, samples, monkeypatch):
    """Decision 102: one lock across the whole pass, not one per step.

    The filer and the scanner used to take it one after the other, and the
    gap between them is a real one: a click in the app could file something
    into a folder the scan was about to read but had not decided from. The
    test asks the only question that distinguishes the two - while the scan
    step is running, can anybody else take this engagement's lock?
    """
    from tracker import runner as runner_module
    from tracker.locking import EngagementLockedError, acquire_lock

    engagement = build_engagement(tmp_path, samples)

    refused: list[bool] = []
    real = runner_module.scan_engagement

    def scan(engagement_dir, **kwargs):
        try:
            acquire_lock(Path(engagement_dir))
        except EngagementLockedError:
            refused.append(True)
        else:
            refused.append(False)
        return real(engagement_dir, **kwargs)

    monkeypatch.setattr(runner_module, "scan_engagement", scan)
    run = a_pass(engagement, today=FRIDAY, reminders=REMINDERS_NEVER)

    assert run.ok, run.error
    assert refused == [True], "the scan step ran with the pass's lock let go"


def test_a_dry_run_takes_no_lock_at_all(tmp_path, samples, monkeypatch):
    """It writes nothing, so it must never block a real pass."""
    from tracker import runner as runner_module
    from tracker.locking import acquire_lock, release_lock

    engagement = build_engagement(tmp_path, samples)

    taken: list[bool] = []
    real = runner_module.scan_engagement

    def scan(engagement_dir, **kwargs):
        held = acquire_lock(Path(engagement_dir))
        taken.append(True)
        release_lock(held)
        return real(engagement_dir, **kwargs)

    monkeypatch.setattr(runner_module, "scan_engagement", scan)
    run = a_pass(engagement, today=FRIDAY, reminders=REMINDERS_NEVER, dry_run=True)

    assert run.ok and taken == [True]


def test_a_file_named_like_markup_is_shown_as_a_name_not_rendered(tmp_path):
    """Every value on the page goes through html.escape. The name cannot be
    made on Windows, so it arrives the way it would in life: an index row
    written elsewhere, from a client's folder that is not this machine's."""
    folder = make_engagement(tmp_path, DEMO_ITEMS, return_name="Evil TY2025", scaffold=False)
    name = "<b>evil</b>.pdf"
    reason = "<i>nothing matched</i>"
    seed_index(folder, [IndexEntry(
        received=FRIDAY.isoformat(), original_name=name, size_kb=1.0, digest="0" * 64,
        identifier="", prepared_location="",
        pbc_location=f"../../../../Clients/Test Household/2025/{name}",
        decision=NEEDS_REVIEW, reason=reason,
    )])

    report = RunReport(today=FRIDAY, runs=[EngagementRun(engagement=Engagement(path=folder))])
    text = write_status_page(tmp_path, report).read_text(encoding="utf-8")

    assert name not in text and reason not in text
    assert "&lt;b&gt;evil&lt;/b&gt;.pdf" in text
    assert "&lt;i&gt;nothing matched&lt;/i&gt;" in text


def test_the_page_is_written_even_when_an_engagements_pass_failed(tmp_path, samples, capsys):
    """The pass that errored is exactly the one a person has to find out about,
    so the page it would have been written by is still written, with the error.
    A typo cannot reach the record (decision 104); what can is a journal
    line something else wrote badly."""
    build_engagement(tmp_path, samples, name="Good TY2025")
    broken = build_engagement(tmp_path, samples, name="Broken TY2025")
    with ledger.path_for(broken.path).open("ab") as handle:
        handle.write(b"{this line is not an event}\n")

    assert main([str(tmp_path), "--date", FRIDAY.isoformat()]) == 1
    text = (tmp_path / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")

    assert "Good TY2025" in text and text.count("Broken TY2025") >= 2
    assert "does not read as an event" in text
    capsys.readouterr()


def test_the_page_still_has_a_heading_where_nothing_can_say_what_the_product_is_called(
    tmp_path, monkeypatch
):
    """The packaged app's scheduled job runs without the Electron shell, which
    is the only thing that knows the product's name there. A pass that has
    already moved the client's files must not end in a traceback over a
    heading, so the firm's name - and then the folder - stand in."""
    from tracker.settings import SettingsError

    def unknown():
        raise SettingsError("no shell, no package.json")

    folder = tmp_path / "Clients"
    folder.mkdir()
    report = RunReport(today=FRIDAY, runs=[])

    monkeypatch.setattr("tracker.runner.product_name", unknown)
    monkeypatch.setattr("tracker.runner.firm", lambda: "J Park & Associates, CPA")
    assert "J Park &amp; Associates, CPA" in write_status_page(folder, report).read_text(encoding="utf-8")

    monkeypatch.setattr("tracker.runner.firm", lambda: "")
    assert folder.name in write_status_page(folder, report).read_text(encoding="utf-8")


def test_an_engagement_nobody_passed_is_read_rather_than_run(tmp_path, samples):
    """The app scans one engagement; the page is still about the practice. The
    others are read - manifest and sidecar, no lock, no scaffold, no scan -
    and say so by carrying no pass time."""
    from tracker.registry import discover_engagements
    from tracker.runner import STATUS_NOT_PASSED, status_report

    clients = tmp_path / "Clients"
    scanned = build_engagement(clients, samples, name="Scanned TY2025")
    untouched = build_engagement(clients, samples, name="Untouched TY2025")
    earlier = a_pass(untouched, today=FRIDAY, reminders=REMINDERS_NEVER)
    run = a_pass(scanned, today=FRIDAY, reminders=REMINDERS_NEVER)

    report = status_report(discover_engagements(clients), passed=[run])
    rows = {r.engagement.path.name: r for r in report.runs}
    assert set(rows) == {"Scanned TY2025", "Untouched TY2025"}
    assert rows["Scanned TY2025"].last_pass is not None
    # Read back from the manifest its own earlier pass wrote, without a pass.
    assert rows["Untouched TY2025"].outstanding == earlier.outstanding > 0
    assert rows["Untouched TY2025"].statuses == earlier.statuses
    assert rows["Untouched TY2025"].last_pass is None

    text = write_status_page(clients, report).read_text(encoding="utf-8")
    assert STATUS_NOT_PASSED in text


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


def test_the_practice_page_says_approved_where_it_would_say_the_stage(tmp_path, samples):
    """One column, one answer per engagement: held, then approved, then the
    rung the letter was written at."""
    from tracker.reminder import APPROVED_NOTE
    from tracker.runner import _drafted_cell

    engagement = build_engagement(tmp_path, samples)
    run = EngagementRun(engagement=engagement, drafted=engagement.path / DRAFT_FILENAME, stage=3)
    assert _drafted_cell(run) == STAGE_NOTE.format(n=3)
    run.approved = True
    assert _drafted_cell(run) == APPROVED_NOTE
    run.held = 2
    assert _drafted_cell(run) == STATUS_HELD.format(n=2)
    assert APPROVED_NOTE in run.summary()


# ============ the household pass (decision 125) ============================


def a_household(tmp_path, samples, household="Park Family", drops=()):
    """One household with a 1040 and an 1120S of the same open year, and
    whatever the client has dropped into its one inbox."""
    from tracker.manifest import RequestItem
    from tracker.scaffold import scaffold_engagement

    personal = make_engagement(tmp_path, DEMO_ITEMS,
                               EngagementInfo(client="John Park", firm="J Park"),
                               household=household, return_name="1040 - John Park",
                               people=SCRATCH_PEOPLE, scaffold=False)
    business = make_engagement(
        tmp_path,
        [RequestItem(identifier="B01", document="Trial Balance", period="TY2025",
                     allowed_extensions=("pdf",), min_size_kb=0,
                     required_keywords=("trial balance",))],
        EngagementInfo(client="Park Landscaping", firm="J Park"),
        household=household, return_name="1120S - Park Landscaping", scaffold=False)
    result = scaffold_engagement(personal)
    scaffold_engagement(business)
    for name in drops:
        (result.inbox / name).write_bytes((samples / name).read_bytes())
    return engagement_from(personal), engagement_from(business)


def test_the_household_pass_takes_every_open_returns_lock_in_name_order_and_releases_them(
        tmp_path, samples, monkeypatch):
    """One inbox feeds every return of the household, so the pass holds
    every open return's lock across the whole of it - taken in folder-name
    order without case, so two passes can never hold each other's returns
    the wrong way round - and lets go of all of them at the end."""
    from tracker.locking import LOCK_FILENAME

    personal, business = a_household(tmp_path, samples,
                                     drops=(f"W-2 John Smith {YEAR}.pdf",))
    household = household_of(personal.path)
    taken = []
    real = runner_module.engagement_lock

    def watched(folder, **kwargs):
        taken.append(Path(folder).name)
        return real(folder, **kwargs)

    monkeypatch.setattr(runner_module, "engagement_lock", watched)
    runs = run_household(household, [personal, business], today=FRIDAY,
                         reminders=REMINDERS_NEVER, registry=discover_engagements(tmp_path))

    assert taken == ["1040 - John Park", "1120S - Park Landscaping"]
    assert taken == sorted(taken, key=str.lower)
    assert [run.ok for run in runs] == [True, True]
    assert sum(run.filed for run in runs) == 1
    assert not any((one.path / LOCK_FILENAME).exists() for one in (personal, business))


def test_a_lock_held_on_one_return_skips_the_whole_household_and_touches_nothing(
        tmp_path, samples):
    """What a pass decides from must not change under it, and the section
    is the household's: one return held elsewhere means nothing of the
    household is sorted this pass, and every return says why."""
    import os

    from tracker.locking import LOCK_FILENAME

    personal, business = a_household(tmp_path, samples,
                                     drops=(f"W-2 John Smith {YEAR}.pdf",))
    household = household_of(personal.path)
    (business.path / LOCK_FILENAME).write_text(f"pid={os.getpid()}", encoding="utf-8")

    runs = run_household(household, [personal, business], today=FRIDAY,
                         reminders=REMINDERS_NEVER, registry=discover_engagements(tmp_path))

    assert all(run.skipped.startswith("another run is still going") for run in runs)
    assert all(run.filed == 0 for run in runs)
    assert (inbox_of(personal.path) / f"W-2 John Smith {YEAR}.pdf").is_file()
    assert read_index(personal.path) == []


def test_two_open_years_sort_nothing_and_say_so_on_every_return(tmp_path, samples, monkeypatch):
    """One inbox cannot say which year a document is for, so nothing is
    sorted from it until a person retires a year in the editor - and every
    return of the household says so, on the page and in the run."""
    from tracker.runner import TWO_OPEN_YEARS
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    # The root is recorded the way the app records it: a return keeps its
    # name every year, and the store keys a folder by its path below that
    # root - with none written down, this year's and next year's would be
    # one row.
    # The settings beside the root, not inside it: a root that holds the
    # app's settings is refused (decision 137).
    settings = tmp_path.parent / f"{tmp_path.name}-app"
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    settings.mkdir(exist_ok=True)
    set_clients_root(tmp_path)

    personal, business = a_household(tmp_path, samples,
                                     drops=(f"W-2 John Smith {YEAR}.pdf",))
    household = household_of(personal.path)
    next_year = make_engagement(tmp_path, DEMO_ITEMS,
                                EngagementInfo(client="John Park", firm="J Park"),
                                household="Park Family", year=2026,
                                return_name="1040 - John Park", scaffold=False)
    every = [personal, business, engagement_from(next_year)]

    runs = run_household(household, every, today=FRIDAY, reminders=REMINDERS_NEVER,
                         registry=discover_engagements(tmp_path))

    said = TWO_OPEN_YEARS.format(years="2025, 2026")
    assert all(said in run.warnings for run in runs)
    assert all(run.filed == 0 for run in runs)
    assert (inbox_of(personal.path) / f"W-2 John Smith {YEAR}.pdf").is_file()
    # The page says it too, and the app reads it from the state.
    page = write_status_page(tmp_path, RunReport(today=FRIDAY, runs=runs)).read_text(encoding="utf-8")
    assert str(len(runs[0].warnings)) in page
    state = api_state(personal.path)
    assert state["household"]["open_years"] == [2025, 2026]

    # A person retires the year in the editor, and the next pass sorts.
    edit_details(next_year, active=False)
    runs = run_household(household, [personal, business, engagement_from(next_year)],
                         today=FRIDAY, reminders=REMINDERS_NEVER,
                         registry=discover_engagements(tmp_path))
    assert not any(said in run.warnings for run in runs)
    assert sum(run.filed for run in runs) == 1


# Decision 133: the reminder waits for the sort. A pass drafts after it
# sorts, but when the sort does not take what the client sent, the letter
# could ask for a document sitting in the client's own drop folder.


def test_a_household_with_two_open_years_and_a_waiting_file_drafts_no_reminder_and_says_why(
        tmp_path, samples, stamped_on, monkeypatch):
    from tracker.reminder import INBOX_HOLD
    from tracker.runner import TWO_OPEN_YEARS
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    # The settings beside the root, not inside it: a root that holds the
    # app's settings is refused (decision 137).
    settings = tmp_path.parent / f"{tmp_path.name}-app"
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    settings.mkdir(exist_ok=True)
    set_clients_root(tmp_path)
    personal, business = a_household(tmp_path, samples,
                                     drops=(f"W-2 John Smith {YEAR}.pdf",))
    household = household_of(personal.path)
    next_year = make_engagement(tmp_path, DEMO_ITEMS,
                                EngagementInfo(client="John Park", firm="J Park"),
                                household="Park Family", year=2026,
                                return_name="1040 - John Park", scaffold=False)
    every = [personal, business, engagement_from(next_year)]

    stamped_on(SATURDAY)
    runs = run_household(household, every, today=SATURDAY,
                         registry=discover_engagements(tmp_path))

    # The inbox was not read, so the W-2 still waits in it - and no return
    # of the household is asked for anything while it does.
    assert (inbox_of(personal.path) / f"W-2 John Smith {YEAR}.pdf").is_file()
    said = INBOX_HOLD.format(n=1)
    for run in runs:
        assert run.ok and run.drafted is None and run.held == 1
        assert run.draft_note == said
        assert TWO_OPEN_YEARS.format(years="2025, 2026") in run.warnings
        assert list(run.engagement.path.glob("reminder-draft*")) == []
        assert drafted_events(run.engagement.path) == [{ledger.HELD_KEY: []}]
    # Said where a person looks: the run log, and the practice page's cell.
    logged = append_log(tmp_path / LOG_FILENAME,
                        RunReport(today=SATURDAY, runs=runs)).read_text(encoding="utf-8")
    assert logged.count(said) == len(runs)
    page = html.unescape(write_status_page(tmp_path, RunReport(today=SATURDAY, runs=runs))
                         .read_text(encoding="utf-8"))
    assert f"<td>{STATUS_HELD.format(n=1)}</td>" in page


def test_the_pass_that_sorts_the_inbox_drafts_the_held_reminder_the_same_day(
        tmp_path, samples, stamped_on, monkeypatch):
    import tracker.filer as filer_module
    from tracker.layout import README_NAME
    from tracker.reminder import INBOX_HOLD

    engagement = build_engagement(tmp_path, samples)
    inbox = inbox_of(engagement.path)
    real = filer_module._move_whole

    def refused_once(source, target, *, within):
        if Path(source).parent == inbox:
            raise PermissionError("held open by the sync client")
        return real(source, target, within=within)

    # The draft day's first pass: the drop cannot be moved, so it fails to
    # sort and stays in the inbox - and the reminder waits for it.
    monkeypatch.setattr(filer_module, "_move_whole", refused_once)
    held = pass_on(stamped_on, engagement, SATURDAY)
    monkeypatch.undo()
    assert held.file_errors and held.drafted is None
    assert held.held == 1 and held.draft_note == INBOX_HOLD.format(n=1)
    assert (inbox / f"W-2 John Smith {YEAR}.pdf").is_file()
    assert not (engagement.path / DRAFT_FILENAME).exists()

    # The next pass that same day sorts it, and drafts: a hold is not a
    # draft, so the week's draft is still owed.
    run = pass_on(stamped_on, engagement, SATURDAY)
    assert run.ok and run.filed == 1 and run.held == 0
    assert run.drafted == engagement.path / DRAFT_FILENAME
    assert [one.name for one in inbox.iterdir() if one.name != README_NAME] == []
    events = drafted_events(engagement.path)
    assert [ledger.HELD_KEY in e for e in events] == [True, False]
    assert last_drafted(engagement.path) == SATURDAY


def api_state(engagement):
    """The state the app reads for one return."""
    import tracker.api as api_module

    return api_module._state(Path(engagement))


def test_after_any_pass_nothing_under_the_client_tree_is_a_record_a_copy_a_draft_a_lock_or_a_page(
        tmp_path, samples):
    """**The guarantee** (decision 125, claim 1): a folder shared one level
    too high by mistake still exposes only the client's own material. After
    a whole pass over two households - three returns, drops filed, one
    parked, a draft day - everything under the tree a client is shared is
    the README, the year's originals and whatever they have just dropped.
    """
    from tracker.layout import CLIENTS_TREE
    from tracker.ledger import LEDGER_FILENAME
    from tracker.locking import LOCK_FILENAME
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.scaffold import README_NAME
    from tracker.view import VIEW_FILENAME

    personal, business = a_household(
        tmp_path, samples, drops=(f"W-2 John Smith {YEAR}.pdf", "vacation photo.bmp"))
    alone = build_engagement(tmp_path, samples, household="Vega Landscaping LLC",
                             name="1120S - Vega Landscaping")
    run_registry(discover_engagements(tmp_path), today=SATURDAY)

    client_tree = tmp_path / CLIENTS_TREE
    assert client_tree.is_dir()
    everything = sorted(p for p in client_tree.rglob("*") if p.is_file())
    assert everything, "the client tree holds the README and the originals"
    for path in everything:
        assert path.name not in {LEDGER_FILENAME, LOCK_FILENAME, DRAFT_FILENAME,
                                 NEW_DRAFT_FILENAME, VIEW_FILENAME}, path
        assert path.suffix.lower() != ".html", path
        assert PREPARED_DIR_NAME not in path.parts, path
        # Every file is the README, or an original where the pass put it.
        assert path.name == README_NAME or path.parent.name.isdigit(), path
    # And what the pass did is still on the record, in the other tree.
    assert sum(len(read_index(one.path)) for one in (personal, business)) >= 2
    assert any(row.decision == NEEDS_REVIEW
               for one in (personal, business, alone) for row in read_index(one.path))


# ============ the household routes: the feed list (decision 129) ===========
#
# A household's drop folder feeds its own returns unless a person extends it
# to named return lines in other households. The pass then judges the inbox
# against those returns too - under every lock it needs, taken in one global
# order - and says so when a line answers to nothing.

TRIAL_BALANCE = [RequestItem(identifier="B01", document="Trial Balance", period=f"TY{YEAR}",
                             allowed_extensions=("pdf",), min_size_kb=0,
                             required_keywords=("trial balance",))]


def a_fed_household(tmp_path, samples, *, years=(YEAR,), drops=()):
    """Park Family with its own 1040, an Aaa Holdings household with an
    1120S of each of ``years``, and Park Family's drop folder feeding the
    Aaa Holdings return line.

    "Aaa Holdings" sorts before "Park Family" as a household and its return
    sorts after Park's as a return: the two orders disagree, which is what
    the global lock order is for.
    """
    from dataclasses import replace

    from tracker.households import load_household_info, save_household
    from tracker.layout import private_household_dir
    from tracker.records import Feed
    from tracker.scaffold import scaffold_engagement

    personal = make_engagement(tmp_path, DEMO_ITEMS,
                               EngagementInfo(client="John Park", firm="J Park"),
                               household="Park Family", return_name="1040 - John Park",
                               people=SCRATCH_PEOPLE, scaffold=False)
    fed = [make_engagement(tmp_path, TRIAL_BALANCE,
                           EngagementInfo(client="Aaa Holdings", firm="J Park"),
                           household="Aaa Holdings", year=year,
                           return_name="1120S - Aaa Holdings", people=SCRATCH_PEOPLE,
                           scaffold=False)
           for year in years]
    result = scaffold_engagement(personal)
    for one in fed:
        scaffold_engagement(one)
    home = private_household_dir(tmp_path, "Park Family")
    save_household(home, replace(load_household_info(home),
                                 feeds=(Feed("Aaa Holdings", "1120S - Aaa Holdings"),)))
    for name in drops:
        (result.inbox / name).write_bytes((samples / name).read_bytes())
    return engagement_from(personal), [engagement_from(one) for one in fed]


def test_the_pass_takes_every_lock_it_needs_in_one_global_order_across_households(
        tmp_path, samples, monkeypatch):
    """A drop folder may feed a return in another household, so a pass
    holds locks in two households at once. Every one of them is taken in
    the one global order - the household's folder name, then the return's,
    without case - before anything is read, so two passes running at once
    can never take the same two returns the other way round."""
    from tracker.layout import lock_order_key
    from tracker.locking import LOCK_FILENAME

    personal, [fed] = a_fed_household(tmp_path, samples,
                                      drops=(f"W-2 John Smith {YEAR}.pdf",))
    household = household_of(personal.path)
    taken = []
    real = runner_module.engagement_lock

    def watched(folder, **kwargs):
        taken.append(Path(folder))
        return real(folder, **kwargs)

    monkeypatch.setattr(runner_module, "engagement_lock", watched)
    runs = run_household(household, [personal], today=FRIDAY, reminders=REMINDERS_NEVER,
                         registry=discover_engagements(tmp_path))

    assert [one.name for one in taken] == ["1120S - Aaa Holdings", "1040 - John Park"]
    assert taken == sorted(taken, key=lock_order_key)
    # And the return-folder name alone would have ordered them the other
    # way round, which is why the household is the first part of the key.
    assert [one.name for one in taken] != sorted(one.name for one in taken)
    assert [run.ok for run in runs] == [True]
    assert not any((one / LOCK_FILENAME).exists() for one in (personal.path, fed.path))


def test_a_fed_household_with_two_open_years_leaves_that_feed_unresolved_and_the_rest_proceeds(
        tmp_path, samples):
    """A household with two open years sorts nothing from its own inbox
    because nothing can say which year a document is for (decision 125) -
    and for the same reason a feed into one of its returns resolves to
    nothing this pass. It is said on every return of the household that
    feeds it, and that household's own sort goes ahead."""
    from tracker.households import FEED_UNRESOLVED

    personal, _fed = a_fed_household(tmp_path, samples, years=(YEAR, YEAR + 1),
                                     drops=(f"W-2 John Smith {YEAR}.pdf",))
    household = household_of(personal.path)

    [run] = run_household(household, [personal], today=FRIDAY, reminders=REMINDERS_NEVER,
                          registry=discover_engagements(tmp_path))

    assert FEED_UNRESOLVED.format(household="Aaa Holdings",
                                  return_name="1120S - Aaa Holdings", year=YEAR) in run.warnings
    assert run.ok and run.filed == 1        # the rest of the pass proceeded


def test_the_dropping_households_pass_files_nothing_into_a_fed_return_and_the_document_waits_in_its_queue(
        tmp_path, samples):
    """Decision 204, revising 129 and 132: a document only a fed return
    wants, naming that return's person, is not filed there by the pass. It
    waits in this household's own queue for one click, so this pass files
    nothing and says nothing about filing elsewhere - "filed 0" is the
    truth about this inbox, and the document is counted here, under review."""
    from tests.samples import SCRATCH_CLIENT, text_pdf
    from tracker import reasons
    from tracker.filer import NEEDS_REVIEW

    personal, [fed] = a_fed_household(tmp_path, samples)
    text_pdf(inbox_of(personal.path) / "trial balance.pdf",
             [f"Trial balance as of December 31 {YEAR}", SCRATCH_CLIENT])
    household = household_of(personal.path)

    [run] = run_household(household, [personal], today=FRIDAY, reminders=REMINDERS_NEVER,
                          registry=discover_engagements(tmp_path))

    assert run.ok and run.filed == 0 and run.review == 1
    assert read_index(fed.path) == []
    [row] = read_index(personal.path)
    assert row.decision == NEEDS_REVIEW and reasons.NAMED_ACROSS_HOUSEHOLDS.matches(row.reason)
    assert row.waiting_for.identifiers == ("B01",)
    assert not any(fed.label in warning for warning in run.warnings)


def _click(personal, fed, today=FRIDAY):
    """The one click (decision 204) as the app makes it: the waiting row
    handed over, the taking return re-scanned and both READMEs rewritten."""
    from tracker.filer import NEEDS_REVIEW, hand_over, refresh_household_readme
    from tracker.scanner import scan_engagement

    [row] = [one for one in read_index(personal.path)
             if one.decision == NEEDS_REVIEW and one.waiting_for is not None]
    claim = row.waiting_for
    hand_over(personal.path, row.pbc_location, fed.path, claim.identifiers[0],
              also=claim.identifiers[1:], answers=claim.answers, waiting=True, today=today)
    scan_engagement(fed.path, today=today)
    for one in (personal.path, fed.path):
        refresh_household_readme(household_of(one))


def test_a_pass_cannot_be_run_without_the_practice(tmp_path, samples):
    """There is one way to call a pass (decision 132): the practice is
    required, so *Run now* and the schedule cannot differ by construction.
    Left out, the call does not run; handed ``None`` - a root that could
    not be walked - every run says so in one sentence and nothing is
    sorted, scanned or written."""
    from tracker.runner import NO_PRACTICE

    personal, _fed = a_fed_household(tmp_path, samples,
                                     drops=(f"W-2 John Smith {YEAR}.pdf",))
    household = household_of(personal.path)

    with pytest.raises(TypeError, match="registry"):
        run_household(household, [personal], today=FRIDAY, reminders=REMINDERS_NEVER)
    [run] = run_household(household, [personal], today=FRIDAY, reminders=REMINDERS_NEVER,
                          registry=None)

    assert run.error == NO_PRACTICE and not run.ok
    assert run.filed == 0
    assert (inbox_of(personal.path) / f"W-2 John Smith {YEAR}.pdf").is_file()
    assert read_index(personal.path) == []


def test_a_feed_list_the_pass_cannot_read_is_said_on_every_own_return(tmp_path, samples):
    """A household whose own record is there and will not read feeds only
    its own returns this pass - and says so on every one of them (decision
    132), exactly as a feed that resolves to nothing is said. Silence about
    a route is the thing the feed list forbids."""
    from tracker.layout import private_household_dir
    from tracker.runner import FEEDS_UNREAD

    personal, [fed] = a_fed_household(tmp_path, samples,
                                      drops=(f"W-2 John Smith {YEAR}.pdf",))
    registry = discover_engagements(tmp_path)
    household = household_of(personal.path)
    journal = ledger.path_for(private_household_dir(tmp_path, "Park Family"))
    with open(journal, "ab") as handle:              # a line that is not an event
        handle.write(b"this is not a line of the record\n")

    [run] = run_household(household, [personal], today=FRIDAY, reminders=REMINDERS_NEVER,
                          registry=registry)

    unread = [w for w in run.warnings if w.startswith(FEEDS_UNREAD.split("(")[0])]
    assert len(unread) == 1 and unread[0].endswith(FEEDS_UNREAD.split(")")[-1])
    assert run.filed == 1                              # its own returns were fed
    assert read_index(fed.path) == []                  # and nothing else


def test_a_cross_fed_document_is_on_no_list_of_the_dropping_households_readme_and_a_parked_one_is_its_own(
        tmp_path, samples):
    """F-4, ruled by decision 132: the README in the drop folder is read by
    everyone shared on the dropping household, and a document filed into
    another household's return is seen only by that folder's sharing. So
    the dropping client's README carries neither the document's own name
    nor the firm's name for it - before the one click (decision 204), while
    it waits here, or after it; the household that holds it lists it as its
    own. A document parked at home is the dropping household's, in its own
    record, until a person decides. (Decision 130 extends this claim to the
    received list once there is one.)"""
    from tests.samples import SCRATCH_CLIENT, text_pdf
    from tracker.filer import FILED, NEEDS_REVIEW
    from tracker.scaffold import README_NAME

    personal, [fed] = a_fed_household(tmp_path, samples)
    text_pdf(inbox_of(personal.path) / "trial balance.pdf",
             [f"Trial balance as of December 31 {YEAR}", SCRATCH_CLIENT])
    text_pdf(inbox_of(personal.path) / "unnamed w2.pdf",
             [f"Form W-2 Wage and Tax Statement {YEAR}"])
    household = household_of(personal.path)

    [run] = run_household(household, [personal], today=FRIDAY, reminders=REMINDERS_NEVER,
                          registry=discover_engagements(tmp_path))

    assert run.ok and read_index(fed.path) == []
    for clicked in (False, True):
        if clicked:
            _click(personal, fed)
            [filed] = read_index(fed.path)
            assert filed.decision == FILED and filed.original_name == "trial balance.pdf"
            [parked] = read_index(personal.path)
            assert parked.decision == NEEDS_REVIEW and parked.original_name == "unnamed w2.pdf"
        readme = (inbox_of(personal.path) / README_NAME).read_text(encoding="utf-8")
        assert "trial balance.pdf" not in readme
        assert "Trial Balance" not in readme
        assert "Aaa Holdings" not in readme


def test_in_a_household_a_slow_reading_is_said_once_on_the_first_own_returns_line(
        tmp_path, samples, monkeypatch):
    """SPEC-127.1 §9.2, folded in with decision 132: a reading is the
    household's cost, paid once in the dropping household's pass, and said
    once - on the line of the household's first own return (``first``, the
    run the inbox's own notes ride), never on each return that judged it and
    never cut short. Nothing about it reaches the record."""
    import time

    from tests.test_content_check import photo
    from tracker.filer import FILED
    from tracker.records import entry_to_json
    from tracker.runner import SLOW_READING_NOTE

    personal, business = a_household(tmp_path, samples,
                                      drops=(f"W-2 John Smith {YEAR}.pdf",))
    photo(inbox_of(personal.path) / "A photo.png", words="Trial balance")
    monkeypatch.setattr(runner_module, "SLOW_READING_SECONDS", 0.05)
    # The business's own name is on the page, as it is on a real trial
    # balance: the request is named (decision 128).
    [entity] = load_engagement_info(business.path).people

    def a_slow_reader(path):
        time.sleep(0.2)
        return f"Trial balance as of December 31 {YEAR} {entity.name}"

    monkeypatch.setattr("tracker.content_check._ocr_image", a_slow_reader)

    report = run_registry(discover_engagements(tmp_path), today=FRIDAY,
                          reminders=REMINDERS_NEVER)

    first = next(run for run in report.runs if run.engagement.path == personal.path)
    other = next(run for run in report.runs if run.engagement.path == business.path)
    [row] = [one for one in read_index(business.path) if one.original_name == "A photo.png"]
    assert row.decision == FILED and row.identifier == "B01"     # nothing was cut short
    assert first.filed == 1                                      # the W-2, read after it
    assert first.slowest[0][0] == "A photo.png"                  # the slow one, not the last
    name, seconds = first.slowest[0]
    note = SLOW_READING_NOTE.format(name=name, seconds=seconds)
    assert first.summary().count(note) == 1
    assert "slow reading" not in other.summary()
    assert [one for run in (first, other) for one, _s in run.slowest].count("A photo.png") == 1
    # Seconds are a fact about the machine and the pass, not the document.
    assert "seconds" not in entry_to_json(row)
    [event] = [e for e in ledger.read_events(business.path)
               if e[ledger.EVENT_KEY] == ledger.FILED
               and e[ledger.ROW_KEY]["original_name"] == "A photo.png"]
    assert "seconds" not in event and "seconds" not in event[ledger.ROW_KEY]
    assert all("seconds" not in stored for stored in store.documents(store.connect(),
                                                                     business.path))


# ============== what we have received, live (decision 130) ================
#
# The README is refreshed once by the household pass, after the sort and
# after every return's scan and draft, still inside the locks: what the
# client reads is current as of the pass, never one pass behind (D-d).


def test_a_document_sorted_this_pass_is_on_the_readme_when_the_pass_ends(tmp_path, samples):
    from tracker.filer import FILED
    from tracker.manifest import load_manifest
    from tracker.scaffold import README_NAME, RECEIVED_HEADING, day_text

    engagement = build_engagement(tmp_path, samples)
    readme = inbox_of(engagement.path) / README_NAME
    assert not readme.exists() or RECEIVED_HEADING not in readme.read_text(encoding="utf-8")

    run = a_pass(engagement, today=FRIDAY, reminders=REMINDERS_NEVER)

    assert run.ok and run.filed == 1
    [row] = read_index(engagement.path)
    assert row.decision == FILED
    label = next(i.label for i in load_manifest(engagement.path) if i.identifier == row.identifier)
    text = readme.read_text(encoding="utf-8")
    assert RECEIVED_HEADING in text
    assert f"  {label}  Received {day_text(FRIDAY)}" in text
    assert row.original_name not in text


def test_a_document_dropped_here_and_filed_into_another_households_return_is_on_neither_list_of_this_readme_and_on_that_households(
        tmp_path, samples):
    """132's F-4 ruling, carried into the received list, with decision 204's
    click: until a person clicks, the document waiting for the other
    household is this household's, counted under review with the rest.
    After the click it is in the other household's index, so it is on that
    household's list - at once - and on no list of the README in the folder
    it was dropped in, which never names the other household or its
    return."""
    from tests.samples import SCRATCH_CLIENT, text_pdf
    from tracker.filer import FILED
    from tracker.manifest import load_manifest
    from tracker.scaffold import (
        README_NAME,
        RECEIVED_HEADING,
        UNDER_REVIEW_HEADING,
        day_text,
    )

    personal, [fed] = a_fed_household(tmp_path, samples)
    text_pdf(inbox_of(personal.path) / "trial balance.pdf",
             [f"Trial balance as of December 31 {YEAR}", SCRATCH_CLIENT])
    text_pdf(inbox_of(personal.path) / "unnamed w2.pdf",
             [f"Form W-2 Wage and Tax Statement {YEAR}"])
    household = household_of(personal.path)

    [run] = run_household(household, [personal], today=FRIDAY, reminders=REMINDERS_NEVER,
                          registry=discover_engagements(tmp_path))

    assert run.ok and read_index(fed.path) == []
    here = (inbox_of(personal.path) / README_NAME).read_text(encoding="utf-8")
    received_here = here[here.index(RECEIVED_HEADING):]
    assert received_here.splitlines()[2:4] == [UNDER_REVIEW_HEADING,
                                               f"  2 documents received {day_text(FRIDAY)}"]
    assert "Aaa Holdings" not in here and "trial balance.pdf" not in here

    _click(personal, fed)
    [filed] = read_index(fed.path)
    assert filed.decision == FILED and filed.identifier == "B01"
    [b01] = [i for i in load_manifest(fed.path) if i.identifier == "B01"]

    here = (inbox_of(personal.path) / README_NAME).read_text(encoding="utf-8")
    received_here = here[here.index(RECEIVED_HEADING):]
    assert b01.label not in here and "Trial Balance" not in here
    assert "Aaa Holdings" not in here and "trial balance.pdf" not in here
    assert received_here.splitlines()[2:4] == [UNDER_REVIEW_HEADING,
                                               f"  1 document received {day_text(FRIDAY)}"]
    assert "unnamed w2" not in here

    there = (inbox_of(fed.path) / README_NAME).read_text(encoding="utf-8")
    assert f"  {b01.label}  Received {day_text(FRIDAY)}" in there
    assert "trial balance.pdf" not in there and "Park Family" not in there
# ------------------------------------ decision 131: the room a return has ----


def _a_pass_over(engagement, **kwargs):
    """One household pass over one return, the way the practice runs it."""
    from tracker.layout import root_of

    registry = discover_engagements(root_of(engagement))
    [found] = registry.engagements
    return run_household(household_of(engagement), [found], today=FRIDAY,
                         reminders=REMINDERS_NEVER, registry=registry, **kwargs)


def test_a_return_short_of_room_files_everything_and_is_not_warned(tmp_path):
    """Ten characters short: the W-2 files all the same, under a name cut
    to fit - and the pass does **not** warn (the lead's L-1 on decision
    131): nothing in the run's warnings, the run log's lines or the
    practice page's Warnings column. With a reader's 218 for spreadsheets
    every 1040 at the firm's root would warn every pass, and a warning that
    is always on is a warning nobody reads."""
    from tests.test_filer import drop, tight_return
    from tracker.filer import ROOM_SHORT

    engagement = tight_return(tmp_path, 10)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    [run] = _a_pass_over(engagement)

    said = ROOM_SHORT.format(short=10)
    assert run.warnings == [] and not run.skipped and not run.error
    assert run.filed == 1
    [entry] = read_index(engagement)
    assert entry.prepared_location.endswith("/A01 - W-2 Wage - TY2025.pdf")
    report = RunReport(today=FRIDAY, runs=[run])
    assert said not in format_report(report)
    page = write_status_page(tmp_path, report).read_text(encoding="utf-8")
    assert "characters short of the room" not in page


def test_a_return_with_requests_that_cannot_receive_says_how_many(tmp_path):
    """A request that Prepared leaves no room for even its shortest name is
    counted and said: a document for it parks until the root is shorter."""
    from tests.conftest import root_for_a_return_of
    from tests.test_filer import NO_ROOM_RETURN, ROOM_ITEMS, with_the_long_period
    from tracker.filer import ROOM_PARKS, ROOM_SHORT, room_for
    from tracker.manifest import load_manifest

    engagement = make_engagement(root_for_a_return_of(tmp_path, NO_ROOM_RETURN),
                                 [with_the_long_period(ROOM_ITEMS[0])])   # Prepared: 231
    room = room_for(engagement, load_manifest(engagement))
    assert room.parks == 1 and room.short > 0

    [run] = _a_pass_over(engagement)

    assert ROOM_PARKS.format(count=1) in run.warnings
    assert ROOM_SHORT.format(short=room.short) not in run.warnings   # L-1: the figure is no warning
    assert not run.skipped and not run.error


def test_a_household_with_no_room_for_a_review_copy_is_skipped_whole_before_anything_is_read(
    tmp_path, monkeypatch,
):
    """A return whose review folder leaves no room for even ``x (99).pdf``
    stops its household: every working return carries HOUSEHOLD_NO_ROOM,
    the inbox is untouched, no lock is taken, and nothing is scaffolded,
    scanned, drafted or drawn - the held-lock shape."""
    from tests.conftest import root_for_a_return_of
    from tests.test_filer import ROOM_ITEMS, drop
    from tracker.filer import HOUSEHOLD_NO_ROOM
    from tracker.layout import README_NAME
    from tracker.locking import LOCK_FILENAME
    from tracker.page import esc
    from tracker.view import VIEW_FILENAME

    root = root_for_a_return_of(tmp_path, 223)          # its floor: 223 + 38 = 261
    engagement = make_engagement(root, ROOM_ITEMS, scaffold=False)
    inbox = inbox_of(engagement)
    inbox.mkdir(parents=True)
    dropped = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    events = len(ledger.read_events(engagement))
    locks = []
    real_lock = runner_module.engagement_lock
    monkeypatch.setattr(runner_module, "engagement_lock",
                        lambda folder: (locks.append(folder), real_lock(folder))[1])

    [run] = _a_pass_over(engagement)

    said = HOUSEHOLD_NO_ROOM.format(label=run.engagement.label, length=261, limit=260)
    assert run.skipped == said and not run.error
    assert locks == []
    assert dropped.is_file() and [p.name for p in inbox.iterdir()] == ["w2.pdf"]
    assert not (inbox / README_NAME).exists()
    assert not (engagement / LOCK_FILENAME).exists()
    assert not (engagement / VIEW_FILENAME).exists()
    assert not (engagement / DRAFT_FILENAME).exists()
    assert not (engagement / PREPARED_DIR_NAME).exists()
    assert len(ledger.read_events(engagement)) == events        # no scan, nothing recorded
    page = write_status_page(tmp_path, RunReport(today=FRIDAY, runs=[run])).read_text(encoding="utf-8")
    assert esc(said) in page


def test_the_runner_reads_the_clients_root_from_the_settings_file_when_given_none(
    tmp_path, monkeypatch, capsys,
):
    """The job names the app's settings folder and no root (decision 131):
    with a root recorded there the pass runs over it; with none it exits
    saying how to set one. A root on the command line used to win over it;
    since decision 159 (E5, the review's S2) one outside the root this
    machine's record checkpoint belongs to is refused by name."""
    from tracker.settings import ENV_SETTINGS_DIR, NO_ROOT_HINT, SET_ROOT_HINT, set_clients_root

    recorded = tmp_path / "Recorded"
    by_hand = tmp_path / "ByHand"
    # Two households, so the one store the test has keys them apart.
    for folder, name in ((recorded, "Recorded"), (by_hand, "By Hand")):
        make_engagement(folder, [RequestItem(identifier="A01", document="W-2")],
                        household=f"{name} Household", return_name=f"1040 - {name}")
    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))     # put back when the test ends
    set_clients_root(recorded)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "elsewhere"))

    assert main([SETTINGS_FLAG, str(settings), "--reminders", "never"]) == 0
    assert (recorded / STATUS_PAGE_FILENAME).is_file()
    assert not (by_hand / STATUS_PAGE_FILENAME).exists()

    with pytest.raises(SystemExit, match="record checkpoint belongs to"):
        main([str(by_hand), SETTINGS_FLAG, str(settings), "--reminders", "never"])
    assert not (by_hand / STATUS_PAGE_FILENAME).exists()

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SystemExit) as refused:
        main([SETTINGS_FLAG, str(empty)])
    assert "no clients root given" in str(refused.value) and SET_ROOT_HINT in str(refused.value)
    # The app first - the packaged app has no python to type - the command second.
    assert str(refused.value).endswith(NO_ROOT_HINT)
    assert NO_ROOT_HINT.startswith("set the clients folder in the app")
    capsys.readouterr()


def test_the_old_scheduled_job_naming_another_root_is_refused_and_says_install_schedule(
    tmp_path, monkeypatch, capsys,
):
    """F3: the job installed before decision 131 names a clients root on its
    command line with ``--log``. After the root moves in the app that job
    would go on sorting the old tree without a word, so a run of that shape
    whose root is not the settings file's - or that has no settings root to
    agree with - is refused, red, naming Install Schedule. The same root is
    run; a person's hand-run without ``--log`` is never refused."""
    import os

    from tracker.runner import LOG_FLAG, OLD_JOB_ROOT
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    current = tmp_path / "Current"
    old = tmp_path / "Old"
    for folder, name in ((current, "Current"), (old, "Old")):
        make_engagement(folder, [RequestItem(identifier="A01", document="W-2")],
                        household=f"{name} Household", return_name=f"1040 - {name}")
    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))

    # No root in the settings file: nothing to agree with, refused.
    with pytest.raises(SystemExit) as refused:
        main([str(old), LOG_FLAG, "--reminders", "never"])
    assert str(refused.value) == OLD_JOB_ROOT.format(root=str(old))
    assert not (old / STATUS_PAGE_FILENAME).exists()

    set_clients_root(current)
    with pytest.raises(SystemExit) as refused:
        main([str(old), LOG_FLAG, "--reminders", "never"])
    assert str(refused.value) == OLD_JOB_ROOT.format(root=str(old))
    assert "press Install Schedule" in str(refused.value)
    assert not (old / STATUS_PAGE_FILENAME).exists()

    # The settings file's own root, spelled another way, runs.
    assert main([str(current) + os.sep, LOG_FLAG, "--reminders", "never"]) == 0
    assert (current / STATUS_PAGE_FILENAME).is_file()

    # A person running another folder by hand, no log: not the job's refusal,
    # but since decision 159 (E5) the checkpoint's - it belongs to Current.
    with pytest.raises(SystemExit, match="record checkpoint belongs to"):
        main([str(old), "--reminders", "never"])
    assert not (old / STATUS_PAGE_FILENAME).exists()
    capsys.readouterr()


def test_the_room_is_measured_from_the_list_the_pass_already_loaded(tmp_path, monkeypatch):
    """One read of each return's list for the pass's own checks: the room is
    measured from the list ``check_rules`` was handed, not a second read."""
    from tests.test_filer import ROOM_ITEMS

    root = tmp_path / "Clients"
    make_engagement(root, ROOM_ITEMS, return_name="1040 - One")
    make_engagement(root, ROOM_ITEMS, return_name="1040 - Two")
    registry = discover_engagements(root)
    reads = []
    real = runner_module.load_manifest
    monkeypatch.setattr(runner_module, "load_manifest", lambda folder: (reads.append(folder), real(folder))[1])

    [(household, returns)] = registry.by_household().items()
    runs = run_household(household, returns, today=FRIDAY, reminders=REMINDERS_NEVER, registry=registry)

    assert all(not run.error for run in runs)
    assert sorted(reads) == sorted(one.path for one in returns)
    assert all(run.items for run in runs)


def test_the_pass_refuses_a_saved_clients_root_the_rule_now_refuses(tmp_path, monkeypatch):
    """Decision 137's review (F12): a root saved before the rule - here the
    folder that holds the app's own settings, written straight into the
    settings file - is held to it at the start of every pass. The pass
    refuses to walk it, in the sentence the app would have given."""
    import json

    from tracker.settings import ENV_SETTINGS_DIR, SETTINGS_FILENAME

    settings = tmp_path / "app"
    settings.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    (settings / SETTINGS_FILENAME).write_text(json.dumps({"clients_root": str(tmp_path)}),
                                              encoding="utf-8")
    with pytest.raises(SystemExit) as refused:
        main(["--reminders", "never"])
    assert "Clients folder problem" in str(refused.value)
    assert "holds the app's own settings" in str(refused.value)


def test_a_root_typed_on_the_command_line_is_held_to_the_same_rule(tmp_path, monkeypatch):
    """Decision 176: only the saved root was held to decision 137's rule, so
    a root typed on the command line - a person's, or another program's -
    would walk the folder holding the app's settings, or the system drive.
    A typed root is refused in the same sentence, before anything is read."""
    from tracker.settings import ENV_SETTINGS_DIR

    settings = tmp_path / "app"
    settings.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    with pytest.raises(SystemExit) as refused:
        main(["--dry-run", "--", str(tmp_path)])
    assert "Clients folder problem" in str(refused.value)
    assert "holds the app's own settings" in str(refused.value)


def test_an_option_after_the_end_of_options_is_a_root_and_writes_no_log(tmp_path, monkeypatch):
    """Decision 176: the preview action appends its root after '--', so a
    root the operator typed as '--log=<anywhere>' names a folder that is
    not there and writes nothing - it used to append the run summary,
    client names and all, to whatever path it named."""
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    target = tmp_path / "leak" / "summary.txt"
    with pytest.raises(SystemExit) as refused:
        main(["--dry-run", "--", f"--log={target}"])
    assert "Clients folder problem" in str(refused.value)
    assert not target.exists() and not target.parent.exists()


# ------------------------------------------- the pass cannot go quiet (189) ----


def _two_households(tmp_path, samples):
    """Two households, each with a W-2 waiting in its inbox."""
    first = build_engagement(tmp_path, samples, household="Alder Household", name="Alder TY2025")
    second = build_engagement(tmp_path, samples, household="Birch Household", name="Birch TY2025")
    return first, second


def _page(root) -> str:
    return html.unescape((root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8"))


def _the_scheduled_job(root, monkeypatch, *args) -> int:
    """``main`` as the scheduled job calls it: the settings folder beside
    ``root``, whose file names ``root`` as the clients root, and the flags."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    settings = root.parent / "settings"
    settings.mkdir(exist_ok=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    set_clients_root(root)
    return main([SETTINGS_FLAG, str(settings), *args])


def test_an_injected_database_error_in_one_household_leaves_the_others_processed_and_the_page_written(
    tmp_path, samples, monkeypatch, capsys,
):
    """The security council's proof line (A-9, D-2): the database refuses
    one household's pre-checks. That household carries the store's own
    class and code; the other is sorted and scanned; the page is written."""
    import tracker.runner as runner

    first, second = _two_households(tmp_path, samples)
    real = runner.load_manifest

    def refused_for_the_first(folder, *args, **kwargs):
        if folder == first.path:
            store.connect().execute("SELECT * FROM a_table_the_store_never_had")
        return real(folder, *args, **kwargs)

    monkeypatch.setattr(runner, "load_manifest", refused_for_the_first)

    assert main([str(tmp_path), "--reminders", REMINDERS_NEVER]) == 1
    page = _page(tmp_path)
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
    assert said in (root / LOG_FILENAME).read_text(encoding="utf-8")
    assert "not a sentence" not in _page(root)
    assert "Smith TY2025: filed 1" in (root / LOG_FILENAME).read_text(encoding="utf-8"), (
        "the household that finished is logged")
    capsys.readouterr()


def test_one_unreadable_record_costs_one_row_of_the_page(tmp_path, samples, monkeypatch):
    import tracker.runner as runner
    from tracker.ledger import RecordNotWritten
    from tracker.runner import status_report

    first, second = _two_households(tmp_path, samples)
    real = runner.load_manifest

    def unreadable_first(folder, *args, **kwargs):
        if folder == first.path:
            raise RecordNotWritten("EACCES")
        return real(folder, *args, **kwargs)

    monkeypatch.setattr(runner, "load_manifest", unreadable_first)
    report = status_report(discover_engagements(tmp_path))
    write_status_page(tmp_path, report)

    by_label = {run.engagement.label: run for run in report.runs}
    assert by_label[first.label].error == RECORD_UNREADABLE.format(
        problem="RecordNotWritten (EACCES)")
    assert by_label[second.label].ok and not by_label[second.label].error
    assert second.label in _page(tmp_path)


def test_a_record_the_disk_refuses_is_said_by_its_class_and_code_never_its_path(
        tmp_path, samples, monkeypatch):
    """The page's per-row error names the class and the errno's code, never
    the operating system's message, which names the record's path - a
    client's folder (security principle 7; the review's S2)."""
    import errno

    import tracker.runner as runner
    from tracker.runner import status_report

    engagement = build_engagement(tmp_path, samples)
    where = str(engagement.path / "journal.jsonl")

    def refused(folder, *args, **kwargs):
        raise PermissionError(errno.EACCES, "Permission denied", where)

    monkeypatch.setattr(runner, "load_manifest", refused)
    report = status_report(discover_engagements(tmp_path))
    write_status_page(tmp_path, report)

    [row] = report.runs
    assert row.error == RECORD_UNREADABLE.format(problem="PermissionError (EACCES)")
    assert where not in _page(tmp_path) and engagement.path.name not in row.error


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
    log_text = (root / LOG_FILENAME).read_text(encoding="utf-8")
    assert "OSError (EIO)" in log_text and "OSError (EIO)" in _page(root)
    for said in (log_text, _page(root)):
        assert where not in said and "a file the disk refused" not in said
    capsys.readouterr()


def test_a_page_that_cannot_be_written_is_said_in_the_log_and_fails_the_run(
        tmp_path, samples, monkeypatch, capsys):
    """The page is how a person finds out; one stuck on yesterday must not
    look green (security principle 6; the review's S3). A page that cannot
    be written is said in the run log by its class alone, and the pass
    exits 1."""
    import tracker.runner as runner
    from tracker.runner import PAGE_NOT_WRITTEN

    root = tmp_path / "Clients"
    build_engagement(root, samples)

    def cannot_write(*args, **kwargs):
        raise PermissionError(13, "Permission denied", str(root / "a client's folder"))

    monkeypatch.setattr(runner, "write_status_page", cannot_write)

    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 1
    log_text = (root / LOG_FILENAME).read_text(encoding="utf-8")
    assert PAGE_NOT_WRITTEN.format(kind="PermissionError") in log_text
    assert "a client's folder" not in log_text
    capsys.readouterr()


def test_the_run_log_carries_a_count_of_warnings_never_their_words(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    run = EngagementRun(engagement=engagement, warnings=["a sentence naming W-2 Client.pdf"] * 3)
    log_path = append_log(tmp_path / LOG_FILENAME, RunReport(today=SATURDAY, runs=[run]))
    text = log_path.read_text(encoding="utf-8")
    assert "(warnings: 3)" in text
    assert "W-2 Client.pdf" not in text


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

    from tests.samples import text_pdf
    from tracker import content_check

    folder = make_engagement(tmp_path, [RequestItem(identifier="A01", document="W-2")],
                             household="Cedar Household", return_name="Cedar TY2025")
    for n in range(1, 6):
        text_pdf(inbox_of(folder) / f"statement {n}.pdf", [f"Brokerage letter number {n}"])
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


# ---------------------------------------------- the bounded household (189) ----


def _three_households(tmp_path, samples):
    return [build_engagement(tmp_path, samples, household=f"{name} Household", name=f"{name} TY2025")
            for name in ("Alder", "Birch", "Cedar")]


@pytest.fixture
def a_clock(monkeypatch):
    """The awake clock, held still unless a test moves it (decision 189)."""
    from tracker import ocr

    now = [1000.0]
    monkeypatch.setattr(ocr, "awake_clock", lambda: now[0])
    return now


def slow_for(monkeypatch, clock, household: str, seconds: float) -> None:
    """Every reading of a file under ``household`` takes ``seconds`` on the
    awake clock: a hostile upload, without the wait."""
    from tracker import content_check

    real = content_check.extract

    def reading(path, **kwargs):
        if household in str(path):
            clock[0] += seconds
        return real(path, **kwargs)

    monkeypatch.setattr(content_check, "extract", reading)


def households_in_order(monkeypatch) -> list[str]:
    """The households a pass takes, in the order it takes them."""
    import tracker.runner as runner

    taken, real = [], runner.run_household

    def recorded(household, *args, **kwargs):
        taken.append(household.name)
        return real(household, *args, **kwargs)

    monkeypatch.setattr(runner, "run_household", recorded)
    return taken


def by_label(report):
    return {run.engagement.label: run for run in report.runs}


def test_a_hostile_first_household_does_not_starve_the_second(tmp_path, samples, monkeypatch, a_clock):
    """The council's proof line (G-11): the first household's readings take
    past its budget. It stops between files and says so; the second is
    sorted, scanned and drafted in the same pass."""
    from tracker.runner import HOUSEHOLD_BUDGET_SECONDS, OUT_OF_TIME

    first = build_engagement(tmp_path, samples, household="Alder Household", name="Alder TY2025",
                             drops=(f"W-2 John Smith {YEAR}.pdf", "Form 1098 Mortgage Interest.pdf"))
    second = build_engagement(tmp_path, samples, household="Birch Household", name="Birch TY2025")
    slow_for(monkeypatch, a_clock, "Alder", HOUSEHOLD_BUDGET_SECONDS + 1)

    report = run_registry(discover_engagements(tmp_path), today=SATURDAY)

    stalled, served = by_label(report)[first.label], by_label(report)[second.label]
    assert stalled.out_of_time and OUT_OF_TIME.format(n=1) in stalled.warnings
    assert len(list(inbox_of(first.path).iterdir())) >= 1, "the rest waits in the inbox"
    assert served.ok and served.filed == 1 and not served.out_of_time
    assert served.drafted == second.path / DRAFT_FILENAME


def test_a_household_out_of_time_drafts_nothing_and_says_so(tmp_path, samples, monkeypatch, a_clock):
    from tracker.runner import HOUSEHOLD_BUDGET_SECONDS, OUT_OF_TIME, OUT_OF_TIME_NO_DRAFT

    engagement = build_engagement(tmp_path, samples,
                                  drops=(f"W-2 John Smith {YEAR}.pdf", "Form 1098 Mortgage Interest.pdf"))
    slow_for(monkeypatch, a_clock, "Test Household", HOUSEHOLD_BUDGET_SECONDS + 1)

    run = a_pass(engagement, today=SATURDAY)

    assert run.out_of_time and run.drafted is None
    assert run.draft_note == OUT_OF_TIME_NO_DRAFT
    assert OUT_OF_TIME.format(n=1) in run.warnings
    assert not (engagement.path / DRAFT_FILENAME).exists()
    assert run.ok, "out of time is not a failure; it is said, and the rest waits"


def test_an_attachment_that_waits_for_time_makes_its_return_out_of_time(
        tmp_path, samples, monkeypatch, a_clock, caplog):
    """A zip is the only drop, and its first attachment's reading takes past
    the household's time (decision 189, ruling 2.2; the review's M2). The
    attachment after it waits for the next pass exactly as an unreached drop
    waits: the return is out of time, that is said, no draft is made, the
    zip gets no row so the next pass opens it again, and the wait is not
    called a reader that could not start."""
    import zipfile

    from tracker.filer import read_index
    from tracker.runner import HOUSEHOLD_BUDGET_SECONDS, OUT_OF_TIME, OUT_OF_TIME_NO_DRAFT

    engagement = build_engagement(tmp_path, samples, drops=())
    with zipfile.ZipFile(inbox_of(engagement.path) / "papers.zip", "w") as packed:
        for name in (f"W-2 John Smith {YEAR}.pdf", "Form 1098 Mortgage Interest.pdf"):
            packed.writestr(name, (samples / name).read_bytes())
    slow_for(monkeypatch, a_clock, "Test Household", HOUSEHOLD_BUDGET_SECONDS + 1)

    with caplog.at_level("WARNING"):
        run = a_pass(engagement, today=SATURDAY)

    assert run.out_of_time and OUT_OF_TIME.format(n=1) in run.warnings
    assert run.drafted is None and run.draft_note == OUT_OF_TIME_NO_DRAFT
    assert not (engagement.path / DRAFT_FILENAME).exists()
    assert "papers.zip" not in [row.original_name for row in read_index(engagement.path)]
    assert "could not start" not in caplog.text


def test_run_now_uses_the_same_budget(tmp_path, samples, monkeypatch, a_clock):
    import tracker.runner as runner

    engagement = build_engagement(tmp_path, samples,
                                  drops=(f"W-2 John Smith {YEAR}.pdf", "Form 1098 Mortgage Interest.pdf"))
    monkeypatch.setattr(runner, "HOUSEHOLD_BUDGET_SECONDS", 5)
    slow_for(monkeypatch, a_clock, "Test Household", 6)
    assert a_pass(engagement, today=FRIDAY).out_of_time


def test_a_household_out_of_time_still_takes_every_cached_verdict(tmp_path, samples, monkeypatch, a_clock):
    """Ruling 2.2: the deadline stops only a file that would need a new
    judgment. A household already past its time from its first moment
    still decides a re-sent drop from its record and scans every request
    from its kept verdicts - and is not out of time, because nothing
    waited."""
    import tracker.runner as runner
    from tracker import content_check
    from tracker.manifest import load_manifest
    from tracker.runner import OUT_OF_TIME_NO_DRAFT

    w2 = f"W-2 John Smith {YEAR}.pdf"
    engagement = build_engagement(tmp_path, samples, drops=(w2,))
    assert a_pass(engagement, today=FRIDAY).filed == 1
    (inbox_of(engagement.path) / w2).write_bytes((samples / w2).read_bytes())

    def no_new_judgment(*args, **kwargs):
        raise AssertionError("a new judgment was started")

    monkeypatch.setattr(content_check, "judge", no_new_judgment)
    monkeypatch.setattr(content_check, "_read_in_a_child", no_new_judgment)
    monkeypatch.setattr(runner, "HOUSEHOLD_BUDGET_SECONDS", 0)

    run = a_pass(engagement, today=SATURDAY)

    assert run.ok and not run.out_of_time and run.draft_note != OUT_OF_TIME_NO_DRAFT
    assert not (inbox_of(engagement.path) / w2).exists(), "the re-send was taken"
    assert [row.decision for row in read_index(engagement.path)] == ["Filed", "Duplicate"]
    assert sum(run.statuses.values()) == len(load_manifest(engagement.path))


def test_pre_checks_that_raise_cost_only_their_household(tmp_path, samples, monkeypatch):
    import tracker.runner as runner

    first, second = _two_households(tmp_path, samples)
    real = runner.open_years

    def surprise(engagements):
        if any(one.path == first.path for one in engagements):
            raise RuntimeError("a pre-check nobody expected")
        return real(engagements)

    monkeypatch.setattr(runner, "open_years", surprise)
    report = run_registry(discover_engagements(tmp_path), today=FRIDAY)

    assert by_label(report)[first.label].error.startswith("RuntimeError")
    assert by_label(report)[second.label].ok and by_label(report)[second.label].filed == 1


def test_the_household_killed_every_pass_goes_last_and_the_others_are_served(
    tmp_path, samples, monkeypatch,
):
    """SPEC-161 ruling 2: a pass killed in a household - past Task
    Scheduler's limit, the machine going off - leaves it marked started and
    never ended, and the next pass takes it last, so the households after
    it in the walk are served."""
    import tracker.runner as runner

    alder, birch, cedar = _three_households(tmp_path, samples)
    real = runner.run_household
    taken = []

    def killed_in_alder(household, *args, **kwargs):
        taken.append(household.name)
        if household.name == "Alder Household":
            raise SystemExit("killed")            # nothing after this line of the pass runs
        return real(household, *args, **kwargs)

    monkeypatch.setattr(runner, "run_household", killed_in_alder)
    for _ in range(2):
        with pytest.raises(SystemExit):
            run_registry(discover_engagements(tmp_path), today=FRIDAY)
    assert taken == ["Alder Household", "Birch Household", "Cedar Household", "Alder Household"]
    for served in (birch, cedar):
        assert [row.decision for row in read_index(served.path)] == ["Filed"]


def test_households_run_least_recently_completed_first(tmp_path, samples, monkeypatch):
    from tracker.runner import PASS_ORDER_FILENAME

    _three_households(tmp_path, samples)
    hint = store.store_path().parent / PASS_ORDER_FILENAME
    hint.parent.mkdir(parents=True, exist_ok=True)
    hint.write_text(
        '{"version": 1, "households": {'
        '"Alder Household": {"completed": "2026-03-13T09:00:00", "not_served": 0},'
        '"Birch Household": {"completed": "2026-03-12T09:00:00", "not_served": 0},'
        '"A household long gone": {"completed": "2026-01-01T09:00:00", "not_served": 0}}}',
        encoding="utf-8")
    taken = households_in_order(monkeypatch)
    run_registry(discover_engagements(tmp_path), today=FRIDAY)
    assert taken == ["Cedar Household", "Birch Household", "Alder Household"]


def test_a_missing_or_broken_pass_order_file_falls_back_to_folder_order(tmp_path, samples, monkeypatch):
    from tracker.runner import ORDER_HINT_UNREADABLE, PASS_ORDER_FILENAME

    _three_households(tmp_path, samples)
    walk = ["Alder Household", "Birch Household", "Cedar Household"]
    hint = store.store_path().parent / PASS_ORDER_FILENAME
    hint.unlink(missing_ok=True)

    taken = households_in_order(monkeypatch)
    report = run_registry(discover_engagements(tmp_path), today=FRIDAY, dry_run=True)
    assert taken == walk and ORDER_HINT_UNREADABLE not in report.warnings
    assert not hint.exists(), "a dry run writes nothing, the hint included"

    hint.parent.mkdir(parents=True, exist_ok=True)
    hint.write_text("{ this is not the hint", encoding="utf-8")
    taken.clear()
    report = run_registry(discover_engagements(tmp_path), today=FRIDAY)
    assert taken == walk
    assert report.warnings.count(ORDER_HINT_UNREADABLE) == 1


def _a_lock_held_by_another_run(engagement_dir):
    """A live process that is not this one, named in the return's lock."""
    import subprocess
    import sys

    from tracker.locking import LOCK_FILENAME, lock_line

    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    (engagement_dir / LOCK_FILENAME).write_text(lock_line(other.pid, dt.datetime.now()),
                                                encoding="utf-8")
    return other


def test_a_household_held_by_a_lock_is_retried_once_at_the_end_of_the_pass(
    tmp_path, samples, monkeypatch,
):
    """Dana's amendment: the other run lets go while the pass works on the
    next household; the held household is tried again at the end, and its
    second attempt is the one reported."""
    import tracker.runner as runner
    from tracker.locking import LOCK_FILENAME

    alder, birch = _two_households(tmp_path, samples)
    other = _a_lock_held_by_another_run(alder.path)
    real, taken = runner.run_household, []

    def the_other_run_finishes_during_birch(household, *args, **kwargs):
        taken.append(household.name)
        runs = real(household, *args, **kwargs)
        if household.name == "Birch Household":
            (alder.path / LOCK_FILENAME).unlink()
        return runs

    monkeypatch.setattr(runner, "run_household", the_other_run_finishes_during_birch)
    try:
        report = run_registry(discover_engagements(tmp_path), today=FRIDAY)
    finally:
        other.kill()
        other.wait()

    assert taken == ["Alder Household", "Birch Household", "Alder Household"]
    assert [run.engagement.label for run in report.runs] == [alder.label, birch.label]
    retried = by_label(report)[alder.label]
    assert retried.ok and not retried.skipped and retried.filed == 1


def test_a_household_not_served_twice_running_exits_three_and_is_named_on_the_page(
    tmp_path, samples, monkeypatch, capsys,
):
    from tracker.locking import LOCK_FILENAME
    from tracker.runner import NOT_SERVED_TWICE, NOT_SERVED_TWICE_EXIT_CODE, WHY_HELD_LOCK

    root = tmp_path / "Clients"
    alder, _birch = _two_households(root, samples)
    other = _a_lock_held_by_another_run(alder.path)
    try:
        assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER) == 0
        assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER) \
            == NOT_SERVED_TWICE_EXIT_CODE == 3
    finally:
        other.kill()
        other.wait()
    assert NOT_SERVED_TWICE.format(household="Alder Household", n=2, why=WHY_HELD_LOCK) \
        in _page(root)

    (alder.path / LOCK_FILENAME).unlink()
    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER) == 0
    assert "has not been served" not in _page(root)
    capsys.readouterr()


def test_a_dry_run_never_names_a_household_not_served_nor_exits_three(
        tmp_path, samples, monkeypatch, a_clock):
    """A dry run keeps nothing, so it counts nothing (the review's N4): a
    household already not served five passes running, out of time again in
    a dry run, is not named, the pass is not an exit 3, and the hint is as
    it was."""
    import json

    from tracker.runner import HOUSEHOLD_BUDGET_SECONDS, PASS_ORDER_FILENAME

    build_engagement(tmp_path, samples, household="Alder Household",
                     drops=(f"W-2 John Smith {YEAR}.pdf", "Form 1098 Mortgage Interest.pdf"))
    hint = store.store_path().parent / PASS_ORDER_FILENAME
    hint.parent.mkdir(parents=True, exist_ok=True)
    before = json.dumps({"version": 1, "households": {
        "Alder Household": {"completed": None, "not_served": 5}}})
    hint.write_text(before, encoding="utf-8")
    slow_for(monkeypatch, a_clock, "Alder", HOUSEHOLD_BUDGET_SECONDS + 1)

    report = run_registry(discover_engagements(tmp_path), today=FRIDAY, dry_run=True)

    assert any(run.out_of_time for run in report.runs)
    assert report.not_served_twice == []
    assert not any("has not been served" in warning for warning in report.warnings)
    assert hint.read_text(encoding="utf-8") == before


def test_a_nested_pass_order_file_is_only_a_hint(tmp_path, samples, monkeypatch):
    """The hint is never a record (SPEC 2.3; the review's S1): a file nested
    past the parser's depth, one past the hint's size and one whose parse
    runs out of memory each give the walk's order and the one sentence -
    none stops the pass before its first household."""
    import tracker.runner as runner
    from tracker.runner import ORDER_HINT_UNREADABLE, PASS_ORDER_FILENAME, PASS_ORDER_MAX_BYTES

    _three_households(tmp_path, samples)
    walk = ["Alder Household", "Birch Household", "Cedar Household"]
    hint = store.store_path().parent / PASS_ORDER_FILENAME
    hint.parent.mkdir(parents=True, exist_ok=True)
    taken = households_in_order(monkeypatch)

    def out_of_memory(*_args, **_kwargs):
        raise MemoryError

    for body, parse in (("[" * (PASS_ORDER_MAX_BYTES - 1), None),
                        (" " * (PASS_ORDER_MAX_BYTES + 1), None),
                        ('{"version": 1, "households": {}}', out_of_memory)):
        hint.write_text(body, encoding="utf-8")
        with monkeypatch.context() as patched:
            if parse is not None:
                patched.setattr(runner.json, "loads", parse)
            taken.clear()
            report = run_registry(discover_engagements(tmp_path), today=FRIDAY, dry_run=True)
        assert taken == walk
        assert report.warnings.count(ORDER_HINT_UNREADABLE) == 1


def test_a_served_household_resets_its_count(tmp_path, samples):
    import json

    from tracker.runner import PASS_ORDER_FILENAME

    engagement = build_engagement(tmp_path, samples, household="Alder Household")
    hint = store.store_path().parent / PASS_ORDER_FILENAME
    hint.parent.mkdir(parents=True, exist_ok=True)
    hint.write_text(json.dumps({"version": 1, "households": {
        "Alder Household": {"completed": None, "not_served": 5}}}), encoding="utf-8")

    report = run_registry(discover_engagements(tmp_path), today=FRIDAY)

    assert report.not_served_twice == [] and by_label(report)[engagement.label].ok
    entry = json.loads(hint.read_text(encoding="utf-8"))["households"]["Alder Household"]
    assert entry["not_served"] == 0 and entry["completed"]


def test_a_pass_that_never_ended_is_said_by_the_next_one(tmp_path, samples, monkeypatch, capsys):
    from tracker.runner import PASS_DID_NOT_FINISH

    root = tmp_path / "Clients"
    build_engagement(root, samples)
    root_log = root / LOG_FILENAME
    root_log.write_text("[2026-03-13T02:00:00] pass started\n", encoding="utf-8")   # then killed

    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 0
    said = PASS_DID_NOT_FINISH.format(stamp="2026-03-13T02:00:00")
    assert said in _page(root)
    text = root_log.read_text(encoding="utf-8")
    assert said in text
    assert text.count("pass started") == 2, "this pass said it started too"

    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 0
    assert "did not finish" not in _page(root), "a pass that finished is never said to have not"
    capsys.readouterr()


# ---------------------- decision 188: the folder is the name, one door ----


def _fabricated_filed_original(engagement_dir, household):
    """One recorded original resting in the household's client folder."""
    seed_index(engagement_dir, [IndexEntry(
        received="2026-02-02", original_name="w2.pdf", size_kb=5.0, digest="ab" * 32,
        identifier="A01", prepared_location="Prepared/A01 - W-2.pdf",
        pbc_location=f"../../../../Clients/{household}/{YEAR}/w2.pdf", decision="filed",
        reason="filed")])


def _whole_pass(root, capsys):
    """The scheduled job's command line over ``root``: exit code, console."""
    code = main([str(root), "--reminders", REMINDERS_NEVER])
    return code, capsys.readouterr().out


def test_a_household_renamed_in_the_firm_tree_pauses_and_makes_no_client_folder(
        tmp_path, samples, capsys):
    """T6 (SPEC-162's claim, overruled by decision 188): a household folder
    renamed in the firm's tree is paused - its record claims the old name -
    and the pass makes no client folder for the new name, sorts nothing out
    of the old one's inbox, and lists the old client folder as one no
    household owns."""
    from tracker.households import HOUSEHOLD_PAUSED
    from tracker.layout import CLIENTS_TREE, PRIVATE_TREE
    from tracker.registry import MISFIT_CLIENT_NO_RECORD

    engagement = build_engagement(tmp_path, samples)
    (tmp_path / PRIVATE_TREE / "Test Household").rename(tmp_path / PRIVATE_TREE / "Test Home")
    inbox = tmp_path / CLIENTS_TREE / "Test Household" / "Drop files here"
    waiting = sorted(p.name for p in inbox.iterdir())

    code, said = _whole_pass(tmp_path, capsys)

    assert code == 1 and HOUSEHOLD_PAUSED in said
    assert not (tmp_path / CLIENTS_TREE / "Test Home").exists()
    assert sorted(p.name for p in inbox.iterdir()) == waiting
    assert MISFIT_CLIENT_NO_RECORD in said and engagement


def test_a_household_renamed_in_the_client_tree_stops_with_one_sentence(tmp_path, samples, capsys):
    """T7 (SPEC-162 ruling 2): a household that had a client folder - a
    recorded original rests there - whose client folder was renamed is
    stopped with the one sentence naming the folder to give back, and no
    client folder of the old name is made again."""
    from tracker.households import CLIENT_FOLDER_MISSING
    from tracker.layout import CLIENTS_TREE

    engagement = build_engagement(tmp_path, samples)
    _fabricated_filed_original(engagement.path, "Test Household")
    (tmp_path / CLIENTS_TREE / "Test Household").rename(tmp_path / CLIENTS_TREE / "Test Hh")

    code, said = _whole_pass(tmp_path, capsys)

    assert code == 1 and CLIENT_FOLDER_MISSING.format(name="Test Household") in said
    assert not (tmp_path / CLIENTS_TREE / "Test Household").exists()


def test_a_new_household_is_still_scaffolded(tmp_path, capsys):
    """T8 (SPEC-162 ruling 2): a household that never had a client folder -
    nothing shared, nothing received - is laid out as it always was."""
    from tracker.layout import inbox_dir_for

    make_engagement(tmp_path, DEMO_ITEMS, household="New Household", people=SCRATCH_PEOPLE,
                    scaffold=False)
    code, said = _whole_pass(tmp_path, capsys)
    assert code == 0, said
    assert inbox_dir_for(tmp_path, "New Household").is_dir()


def test_two_folders_claiming_one_household_stop_both(tmp_path, samples, capsys):
    """T9 (SPEC-162 ruling 3, widened by decision 188): a copy of a
    household folder claims the household too, so both are stopped, each
    run naming both folders - and neither's inbox is sorted."""
    import shutil

    from tracker.layout import CLIENTS_TREE, PRIVATE_TREE
    from tracker.registry import TWO_CLAIM

    build_engagement(tmp_path, samples)
    private = tmp_path / PRIVATE_TREE
    shutil.copytree(private / "Test Household", private / "Test Household - Copy")
    inbox = tmp_path / CLIENTS_TREE / "Test Household" / "Drop files here"
    waiting = sorted(p.name for p in inbox.iterdir())

    code, said = _whole_pass(tmp_path, capsys)

    sentence = TWO_CLAIM.format(name="Test Household", a="Test Household",
                                b="Test Household - Copy")
    assert code == 1 and said.count(sentence) == 2, said
    assert sorted(p.name for p in inbox.iterdir()) == waiting


def test_a_household_without_its_record_fails_the_pass_and_says_restore(tmp_path, samples, capsys):
    """T10 (SPEC-162 ruling 4): a household whose record is gone and whose
    return still holds its own fails the pass - red - with the sentence
    that says to restore it, and the console lists what is left alone at
    the end of the pass."""
    from tracker.layout import CLIENTS_TREE, PRIVATE_TREE
    from tracker.registry import HOUSEHOLD_RECORD_MISSING
    from tracker.runner import STATUS_MISFITS_HEADING

    build_engagement(tmp_path, samples)
    ledger.path_for(tmp_path / PRIVATE_TREE / "Test Household").unlink()
    (tmp_path / CLIENTS_TREE / "Nobody Family").mkdir()

    code, said = _whole_pass(tmp_path, capsys)

    assert code == 1
    assert HOUSEHOLD_RECORD_MISSING.format(folder="Test Household") in said
    assert said.index(STATUS_MISFITS_HEADING) > said.index("processed,")
    assert "Nobody Family" in said.split(STATUS_MISFITS_HEADING, 1)[1]


def test_a_paused_household_makes_the_run_red(tmp_path, samples, capsys):
    """T16 (D-9, the part decision 188 owns): a return folder renamed by
    hand pauses its household, and a paused household is an error on
    every pass until a person acts - never a warning the job's exit code
    hides."""
    from tracker.households import HOUSEHOLD_PAUSED

    engagement = build_engagement(tmp_path, samples)
    engagement.path.rename(engagement.path.parent / "1040 - Someone Else")
    # Red on every pass: 1 the first time, and from the second pass the
    # not-served-twice code, which wins over 1 (decision 189).
    from tracker.runner import NOT_SERVED_TWICE_EXIT_CODE

    for expected in (1, NOT_SERVED_TWICE_EXIT_CODE):
        code, said = _whole_pass(tmp_path, capsys)
        assert code == expected and "ERROR   " in said and HOUSEHOLD_PAUSED in said


def test_every_write_into_the_client_tree_went_through_the_door(tmp_path, samples, monkeypatch):
    """T13 (R9): a full pass - the sweep, the layout, the sort, the README -
    and a Roll Forward on a fabricated root create or change nothing under
    the client tree that the one door did not approve: every file and
    folder there, before and after, by size and time."""
    from tracker import door
    from tracker.layout import CLIENTS_TREE
    from tracker.rollover import ReturnPlan, roll_household

    approved: set[Path] = set()
    real = door.client_write

    def watching(root, household, target, **kwargs):
        approved.add(Path(real(root, household, target, **kwargs)))
        return Path(target)

    def snapshot():
        found = {}
        for path in (tmp_path / CLIENTS_TREE).rglob("*"):
            info = path.stat()
            found[path] = "folder" if path.is_dir() else (info.st_size, info.st_mtime_ns)
        return found

    engagement = build_engagement(tmp_path, samples)
    # A drop in a folder the client dragged in, so the pass also removes the
    # folders it empties (the review's S2): a removal is a write too.
    dragged = inbox_of(engagement.path) / "Bank statements" / str(YEAR)
    dragged.mkdir(parents=True)
    (dragged / f"W-2 John Smith {YEAR}.pdf").write_bytes(
        (samples / f"W-2 John Smith {YEAR}.pdf").read_bytes())
    monkeypatch.setattr(door, "client_write", watching)
    before = snapshot()
    a_pass(engagement)
    roll_household(household_of(engagement.path), target_year=YEAR + 1,
                   plans=[ReturnPlan(prior=engagement.path)])
    after = snapshot()

    changed = {path for path, seen in after.items() if before.get(path) != seen}
    removed = {path for path in before if path not in after and before[path] == "folder"}
    assert changed, "the pass wrote nothing under the client tree"
    assert dragged in removed and dragged.parent in removed
    assert changed | removed <= approved, sorted(str(p) for p in (changed | removed) - approved)



def test_a_new_return_or_a_roll_forward_never_makes_a_gone_client_folder_again(
        tmp_path, samples, capsys, monkeypatch):
    """T7's twins (the review's M3): a household whose client folder was
    renamed after an original came to rest there is refused a new return
    and every form of Roll Forward with the one sentence, before anything
    is written - no client folder of the old name is made again."""
    import io
    import runpy
    import sys

    import tracker.api as api
    from tests.conftest import app_stdin
    from tracker.households import CLIENT_FOLDER_MISSING
    from tracker.layout import CLIENTS_TREE, PRIVATE_TREE
    from tracker.manifest import ManifestError
    from tracker.rollover import ReturnPlan, roll_household
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    # The settings beside the root, never inside it (decision 137).
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path.parent / f"{tmp_path.name} settings"))
    engagement = build_engagement(tmp_path, samples)
    set_clients_root(tmp_path)
    _fabricated_filed_original(engagement.path, "Test Household")
    (tmp_path / CLIENTS_TREE / "Test Household").rename(tmp_path / CLIENTS_TREE / "Test Hh")
    household = tmp_path / PRIVATE_TREE / "Test Household"
    said = CLIENT_FOLDER_MISSING.format(name="Test Household")
    before = sorted(tmp_path.rglob("*"))

    def api_run(*argv, stdin):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("sys.stdin", app_stdin(stdin))
            code = api.main(list(argv))
        return code, capsys.readouterr().out

    code, out = api_run("create", stdin={
        "household_path": str(household), "return_name": "1065 - Test LLC", "form": "1040",
        "people": [{"kind": "taxpayer", "name": "John Smith", "spellings": ["John Smith"]}],
        "items": [{"identifier": "A01", "document": "W-2"}]})
    assert code == 1 and said.replace("\\", "\\\\") in out, out
    code, out = api_run("rollover", stdin={"prior": str(engagement.path), "year": YEAR + 1})
    assert code == 1 and said.replace("\\", "\\\\") in out, out
    with pytest.raises(ManifestError, match="is missing"):
        roll_household(household, target_year=YEAR + 1,
                       plans=[ReturnPlan(prior=engagement.path)])
    console = io.StringIO()
    monkeypatch.setattr(sys, "stderr", console)
    monkeypatch.setattr(sys, "argv", ["rollover", str(household), "--year", str(YEAR + 1), "--all"])
    with pytest.raises(SystemExit):
        runpy.run_module("tracker.rollover", run_name="__main__")
    assert said in console.getvalue()
    assert sorted(tmp_path.rglob("*")) == before


def test_roll_forward_refuses_a_stopped_household_with_its_own_sentence(tmp_path, samples):
    """The review's S4: a household whose record is gone, or one of two
    folders claiming one household, is refused Roll Forward with the stop's
    own sentence, and no new year is made."""
    import shutil

    from tracker.layout import PRIVATE_TREE
    from tracker.manifest import ManifestError
    from tracker.registry import HOUSEHOLD_RECORD_MISSING, TWO_CLAIM
    from tracker.rollover import ReturnPlan, roll_household

    engagement = build_engagement(tmp_path, samples)
    household = tmp_path / PRIVATE_TREE / "Test Household"
    copy = tmp_path / PRIVATE_TREE / "Test Household - Copy"
    shutil.copytree(household, copy)
    with pytest.raises(ManifestError) as refused:
        roll_household(household, target_year=YEAR + 1, plans=[ReturnPlan(prior=engagement.path)])
    assert str(refused.value) == TWO_CLAIM.format(name="Test Household", a="Test Household",
                                                 b="Test Household - Copy")
    shutil.rmtree(copy)
    ledger.path_for(household).unlink()
    with pytest.raises(ManifestError) as refused:
        roll_household(household, target_year=YEAR + 1, plans=[ReturnPlan(prior=engagement.path)])
    assert str(refused.value) == HOUSEHOLD_RECORD_MISSING.format(folder="Test Household")
    assert not (household / str(YEAR + 1)).exists()
# ------------------------------------------- decision 159: records that need a person ----


def test_conflict_copies_and_lock_siblings_are_named_every_pass_and_never_deleted(tmp_path, samples):
    """A-8 / G-5: what a sync client leaves beside a return's record and
    lock, and beside a household's, is named on the practice page and
    counted in the run log every pass - and no pass deletes, moves or
    renames one; only a person does."""
    from tracker.layout import household_of
    from tracker.page import esc
    from tracker.runner import (
        RECORD_SIBLING,
        STATUS_RECORDS_HEADING,
        append_log,
        status_report,
        write_status_page,
    )

    repo = Path(__file__).resolve().parents[1]

    engagement = build_engagement(tmp_path, samples)
    left = [engagement.path / "_ledger (1).jsonl", engagement.path / "_scan (conflict).lock",
            household_of(engagement.path) / "_LEDGER_conflict-2026.jsonl"]
    for copy in left:
        copy.write_text('{"event": "scanned"}\n', encoding="utf-8")
    log = tmp_path / "logs" / "runs.log"

    for _week in range(2):
        report = run_registry(discover_engagements(tmp_path), today=FRIDAY)
        append_log(log, report)
        write_status_page(tmp_path, status_report(discover_engagements(tmp_path), passed=report.runs))
        text = (tmp_path / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
        assert STATUS_RECORDS_HEADING in text
        for copy in left:
            assert esc(RECORD_SIBLING.format(path=copy.relative_to(tmp_path))) in text
            assert copy.read_text(encoding="utf-8") == '{"event": "scanned"}\n'
    assert log.read_text(encoding="utf-8").count("3 copy(ies) beside a record") == 2

    source = "\n".join(path.read_text(encoding="utf-8") for path in (repo / "tracker").glob("*.py"))
    assert "siblings(" in source and not any(
        f"{call}(" in line for line in source.splitlines() if "sibling" in line
        for call in ("unlink", "rename", "replace", "rmtree", "move"))


def test_a_line_written_on_another_machine_is_named_until_acknowledged(tmp_path, samples):
    """Decision 159, C-1 (a): a line another machine wrote is accepted - the
    pass files on - and named on the practice page every pass until a
    person acknowledges it; then it is not."""
    from tests.conftest import written_elsewhere
    from tracker import checkpoint
    from tracker.runner import STATUS_RECORDS_HEADING

    engagement = build_engagement(tmp_path, samples)
    assert main([str(tmp_path), "--date", FRIDAY.isoformat()]) == 0
    written_elsewhere(engagement.path, ledger.new(ledger.SCANNED, **{ledger.STATUSES_KEY: {}}),
                      host="laptop-2")
    seq = len(ledger.read_events(engagement.path))

    for _pass in range(2):
        assert main([str(tmp_path), "--date", FRIDAY.isoformat()]) == 0
        text = (tmp_path / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
        assert STATUS_RECORDS_HEADING in text
        assert f"line {seq} was written on laptop-2" in text

    with checkpoint.opened(checkpoint.path_for(store.store_path())) as held:
        (line,) = checkpoint.unacknowledged(held)
        assert checkpoint.acknowledge(held, line.key) == 1
    assert main([str(tmp_path), "--date", FRIDAY.isoformat()]) == 0
    text = (tmp_path / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
    assert STATUS_RECORDS_HEADING not in text and "laptop-2" not in text


def test_a_refused_record_is_named_among_the_records_that_need_a_person(tmp_path, samples):
    """A record cut short behind the pass's back is that return's problem -
    the pass goes on - and it is listed first, with what to do."""
    from tracker.runner import STATUS_RECORDS_HEADING

    engagement = build_engagement(tmp_path, samples)
    other = build_engagement(tmp_path, samples, name="Other TY2025")
    assert main([str(tmp_path), "--date", FRIDAY.isoformat()]) == 0
    path = ledger.path_for(engagement.path)
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:-1]))

    assert main([str(tmp_path), "--date", FRIDAY.isoformat()]) == 1
    text = (tmp_path / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
    first, _rest = text.split(f"<h2>{STATUS_RECORDS_HEADING}", 1)[1].split("</ul>", 1)
    # Decision 188's sentence for a journal shorter than the store, with the
    # recover pointer every refused record ends with.
    assert "holds fewer lines than the store has applied" in first and ledger.RUN_RECOVER in first
    assert other.path.name not in first
    path.unlink()                    # the fixtures' own fresh store would read it as it now is


def test_a_root_the_checkpoint_does_not_belong_to_is_refused_by_the_pass(tmp_path, samples, monkeypatch):
    """E5: the settings naming another folder than the one this machine's
    checkpoint belongs to - a copy of the root - stop the pass by name
    before anything is walked."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    settings = tmp_path.parent / f"{tmp_path.name}-app"
    settings.mkdir(exist_ok=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    clients, copy = tmp_path / "Clients", tmp_path / "Clients copy"
    build_engagement(clients, samples)
    copy.mkdir()
    set_clients_root(clients)
    assert main(["--date", FRIDAY.isoformat()]) == 0
    set_clients_root(copy)
    with pytest.raises(SystemExit, match="record checkpoint belongs to .*If the clients root really moved"):
        main(["--date", FRIDAY.isoformat()])
    assert not (copy / STATUS_PAGE_FILENAME).exists()


def test_a_failure_before_the_root_is_written_to_the_last_pass_file(tmp_path, monkeypatch, capsys):
    """The scheduled job's shape writes the last-pass file beside the store
    (decision 159, E4): a pass that stops before it reaches a root says so
    with a reason code, and one that runs says when and how it ended. A
    pass run by hand writes nothing there, so it cannot make a stopped
    schedule look alive."""
    import json

    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    beside_the_store = Path(store.store_path()).with_name(runner_module.LAST_PASS_FILENAME)
    assert runner_module.last_pass_path() == beside_the_store

    empty = tmp_path / "empty-settings"
    empty.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(empty))
    with pytest.raises(SystemExit):
        main([SETTINGS_FLAG, str(empty), "--reminders", "never"])
    failed = json.loads(beside_the_store.read_text(encoding="utf-8"))
    assert failed["result"] == runner_module.PASS_FAILED
    assert failed["reason_code"] == runner_module.PASS_NO_ROOT
    assert failed["root"] == "" and failed["started"] and failed["ended"] and failed["build"]

    clients = tmp_path / "Clients"
    make_engagement(clients, [RequestItem(identifier="A01", document="W-2")])
    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    set_clients_root(clients)
    assert main([SETTINGS_FLAG, str(settings), "--reminders", "never"]) == 0
    ran = json.loads(beside_the_store.read_text(encoding="utf-8"))
    assert ran["result"] == runner_module.PASS_SUCCEEDED and ran["reason_code"] == ""
    assert Path(ran["root"]) == clients

    # By hand, or a dry run: the file is left as the schedule wrote it.
    before = beside_the_store.read_bytes()
    assert main([str(clients), "--reminders", "never"]) == 0
    assert main([SETTINGS_FLAG, str(settings), "--dry-run", "--reminders", "never"]) == 0
    assert beside_the_store.read_bytes() == before
    capsys.readouterr()


def test_the_last_pass_line_is_amber_when_old_and_red_when_failed(tmp_path):
    """The app's one line: plain when recent, amber after
    LAST_PASS_AMBER_HOURS or when no pass has run, red on a failure or a
    file that does not read - every word the runner's."""
    now = dt.datetime(2026, 3, 2, 12, 0)
    path = tmp_path / runner_module.LAST_PASS_FILENAME
    assert runner_module.last_pass_line(path, now=now) == {
        "text": runner_module.LAST_PASS_NEVER, "level": runner_module.LEVEL_WARN}

    recent = now - dt.timedelta(hours=1)
    runner_module.write_last_pass(path, started=recent, ended=recent, root="R",
                                  result=runner_module.PASS_SUCCEEDED)
    line = runner_module.last_pass_line(path, now=now)
    assert line["level"] == runner_module.LEVEL_OK and "2026-03-02 11:00" in line["text"]

    old = now - dt.timedelta(hours=runner_module.LAST_PASS_AMBER_HOURS, minutes=1)
    runner_module.write_last_pass(path, started=old, ended=old, root="R",
                                  result=runner_module.PASS_SUCCEEDED)
    line = runner_module.last_pass_line(path, now=now)
    assert line["level"] == runner_module.LEVEL_WARN and line["text"].endswith(runner_module.LAST_PASS_OLD)

    runner_module.write_last_pass(path, started=recent, ended=recent, root="",
                                  result=runner_module.PASS_FAILED,
                                  reason_code=runner_module.PASS_SETTINGS)
    line = runner_module.last_pass_line(path, now=now)
    assert line["level"] == runner_module.LEVEL_ERR
    assert runner_module.PASS_REASONS[runner_module.PASS_SETTINGS] in line["text"]

    path.write_text("{not json", encoding="utf-8")
    assert runner_module.last_pass_line(path, now=now)["level"] == runner_module.LEVEL_ERR


def test_a_pass_over_a_root_the_checkpoint_does_not_belong_to_is_refused_however_the_root_is_given(
        tmp_path, samples, monkeypatch):
    """The review's S2 (probe C7): a copy of the root typed on the command
    line is held to the checkpoint exactly as the settings' root is; one
    client's folder inside the claimed root is not a copy."""
    import shutil

    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    settings = tmp_path.parent / f"{tmp_path.name}-app"
    settings.mkdir(exist_ok=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    clients, copy = tmp_path / "Clients", tmp_path / "Clients copy"
    build_engagement(clients, samples)
    set_clients_root(clients)
    assert main(["--date", FRIDAY.isoformat()]) == 0
    shutil.copytree(clients, copy)
    with pytest.raises(SystemExit, match="record checkpoint belongs to"):
        main([str(copy), "--date", FRIDAY.isoformat()])
    with pytest.raises(SystemExit, match="record checkpoint belongs to"):
        main([str(copy), "--date", FRIDAY.isoformat(), "--dry-run"])
    assert main([str(clients), "--date", FRIDAY.isoformat(), "--dry-run"]) == 0
    shutil.rmtree(copy)


def test_a_checkpoint_that_will_not_open_stops_the_pass_by_name(tmp_path, samples):
    """The review's S4: the file and the runbook's step, never a traceback;
    the file is left where it is for a person. Since the rebase review's
    MF1 the pass does not stop at the proof: it serves no household, exits
    1, and says it first on the practice page it still writes."""
    from tracker import checkpoint

    build_engagement(tmp_path, samples)
    where = checkpoint.path_for(store.store_path())
    where.parent.mkdir(parents=True, exist_ok=True)
    where.write_bytes(b"fabricated garbage, not a database" * 40)
    assert main([str(tmp_path), "--date", FRIDAY.isoformat()]) == 1
    page = html.unescape((tmp_path / STATUS_PAGE_FILENAME).read_text(encoding="utf-8"))
    assert re.search("No household was served this pass: .*cannot read this machine's record "
                     "checkpoint.*runbook §6", page)
    assert where.read_bytes().startswith(b"fabricated garbage")
    where.unlink()


def test_a_record_that_does_not_read_is_among_the_records_that_need_a_person(tmp_path, samples):
    """The review's S6: a careless hand edit that leaves a line unreadable is
    listed first with what to do, and the page never quotes the parser."""
    from tracker.runner import STATUS_RECORDS_HEADING

    engagement = build_engagement(tmp_path, samples)
    with ledger.path_for(engagement.path).open("ab") as handle:
        handle.write(b'{"event": "scanned", "note": "Fabricated" "x"}\n')
    assert main([str(tmp_path), "--date", FRIDAY.isoformat()]) == 1
    text = (tmp_path / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
    first = text.split(f"<h2>{STATUS_RECORDS_HEADING}", 1)[1].split("</ul>", 1)[0]
    assert "does not read as an event (it is not JSON)" in first and ledger.RUN_RECOVER in first
    assert "Fabricated" not in text and "column" not in first
    ledger.path_for(engagement.path).unlink()


def test_the_page_names_the_acknowledge_command_with_this_machines_store(tmp_path, samples):
    """The review's N7: no placeholder a person has to fill in."""
    from tests.conftest import written_elsewhere

    engagement = build_engagement(tmp_path, samples)
    assert main([str(tmp_path), "--date", FRIDAY.isoformat()]) == 0
    written_elsewhere(engagement.path, ledger.new(ledger.SCANNED, **{ledger.STATUSES_KEY: {}}),
                      host="laptop-2")
    assert main([str(tmp_path), "--date", FRIDAY.isoformat()]) == 0
    text = (tmp_path / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
    assert "&lt;store&gt;" not in text and "<store>" not in text
    assert f"python -m tracker.checkpoint &quot;{store.store_path()}&quot; acknowledge" in text


def test_a_first_pass_typed_on_one_clients_folder_claims_nothing(tmp_path, samples, monkeypatch):
    """The final review's SF1: only the settings' root claims this machine's
    record checkpoint. A first real pass typed on a folder inside it claims
    nothing, so the scheduled pass over the whole root still runs. Since
    decision 188 the door refuses such a root itself - inside a tree of the
    real root - before the checkpoint is asked, so nothing is claimed."""
    from tracker import checkpoint
    from tracker.layout import PRIVATE_TREE
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    settings = tmp_path.parent / f"{tmp_path.name}-app"
    settings.mkdir(exist_ok=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    clients = tmp_path / "Clients"
    build_engagement(clients, samples)
    set_clients_root(clients)
    with pytest.raises(SystemExit, match="is inside the"):
        main([str(clients / PRIVATE_TREE), "--date", FRIDAY.isoformat()])
    where = checkpoint.path_for(store.store_path())
    if where.is_file():
        with checkpoint.opened(where) as held:
            assert checkpoint.root_of(held) is None
    assert main([SETTINGS_FLAG, str(settings), "--date", FRIDAY.isoformat()]) == 0
    with checkpoint.opened(where) as held:
        assert checkpoint.root_of(held) == str(clients.resolve())


def test_a_refused_root_is_never_written_into_even_to_log_the_refusal(tmp_path, monkeypatch):
    """The final review's SF2: a settings root refused by decision 137's
    rule gets no run-log line; the last-pass file beside the store carries
    the reason code."""
    import json

    from tracker.runner import LAST_PASS_FILENAME, LOG_FILENAME, last_pass_path
    from tracker.settings import ENV_SETTINGS_DIR, KEY_CLIENTS_ROOT, settings_path

    settings = tmp_path / "appdata" / "settings"
    settings.mkdir(parents=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    around = settings.parent
    settings_path().write_text(json.dumps({KEY_CLIENTS_ROOT: str(around)}), encoding="utf-8")
    with pytest.raises(SystemExit):
        main([SETTINGS_FLAG, str(settings), "--reminders", "never"])
    assert not (around / LOG_FILENAME).exists()
    assert last_pass_path().name == LAST_PASS_FILENAME
    assert json.loads(last_pass_path().read_text(encoding="utf-8"))["result"] == "failed"


# ------------------- the last-pass file beside 189's log and page (159 on 189) ----


def _a_scheduled_main(tmp_path, monkeypatch, body):
    """Run ``main`` in the scheduled job's shape with ``_pass`` replaced by
    ``body`` (what the pass itself does is 189's, tested above)."""
    from tracker.settings import ENV_SETTINGS_DIR

    settings = tmp_path / "settings"
    settings.mkdir(exist_ok=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    monkeypatch.setattr(runner_module, "_pass", body)
    return main([SETTINGS_FLAG, str(settings), "--reminders", "never"])


def test_a_household_not_served_twice_is_the_last_pass_files_reason(tmp_path, monkeypatch):
    """Decision 189's exit 3 is its own reason in the file, not "a return
    failed": the app's line points at the page, which names the household."""
    import json

    assert _a_scheduled_main(tmp_path, monkeypatch,
                             lambda ns, parser, reached: runner_module.NOT_SERVED_TWICE_EXIT_CODE) == 3
    written = json.loads(runner_module.last_pass_path().read_text(encoding="utf-8"))
    assert written["result"] == runner_module.PASS_FAILED
    assert written["reason_code"] == runner_module.PASS_NOT_SERVED
    line = runner_module.last_pass_line()
    assert runner_module.PASS_REASONS[runner_module.PASS_NOT_SERVED] in line["text"]


def test_a_last_pass_file_that_cannot_be_written_never_stops_the_pass(tmp_path, monkeypatch):
    """Decision 189: nothing but the pass's own work decides its exit."""
    def refused(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(runner_module, "write_last_pass", refused)
    assert _a_scheduled_main(tmp_path, monkeypatch, lambda ns, parser, reached: 0) == 0


def test_a_pass_that_stops_after_its_root_logs_the_kind_never_the_words(tmp_path, monkeypatch):
    """The run log's early-failure line carries the reason's code, its fixed
    sentence and the class of what stopped the pass - never the message,
    which can name a client's folder (decision 189, security principle 7)."""
    clients = tmp_path / "Clients"
    clients.mkdir()

    def stopped(ns, parser, reached):
        reached["root"] = str(clients)
        raise RuntimeError("Fabricated Client, 1040 - Fabricated Name")

    with pytest.raises(RuntimeError):
        _a_scheduled_main(tmp_path, monkeypatch, stopped)
    said = (clients / LOG_FILENAME).read_text(encoding="utf-8")
    assert f"pass failed ({runner_module.PASS_ENDED_EARLY})" in said and "(RuntimeError)" in said
    assert "Fabricated" not in said


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
    line = runner_module.last_pass_line(path, now=dt.datetime(2026, 3, 2, 12, 0))
    assert line["level"] == runner_module.LEVEL_ERR and "Fabricated" not in line["text"]


# ------------- a checkpoint that cannot be asked (the rebase review's MF1-SF3) ----


def _the_scheduled_pass_with(tmp_path, monkeypatch, spoil):
    """Two households, the settings naming their root, and ``spoil`` done to
    this machine's record checkpoint; then the scheduled job's pass, logged.
    Returns the exit, the page, the log and the last-pass file."""
    import json

    from tracker import checkpoint
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    clients = tmp_path / "Clients"
    make_engagement(clients, [RequestItem(identifier="A01", document="W-2")], household="Smith Family")
    make_engagement(clients, [RequestItem(identifier="A01", document="W-2")], household="Jones Family")
    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    set_clients_root(clients)
    monkeypatch.setattr(checkpoint, "BUSY_TIMEOUT_MS", 100)
    where = checkpoint.path_for(store.store_path())
    checkpoint.open(where).close()
    with spoil(where):
        code = main([SETTINGS_FLAG, str(settings), "--reminders", "never", "--log"])
    page = html.unescape((clients / STATUS_PAGE_FILENAME).read_text(encoding="utf-8"))
    logged = (clients / LOG_FILENAME).read_text(encoding="utf-8")
    written = json.loads(runner_module.last_pass_path().read_text(encoding="utf-8"))
    return code, page, logged, written


def test_a_damaged_checkpoint_ends_the_pass_named_with_its_page_and_log_written(tmp_path, monkeypatch):
    """MF1: a record-heads.db damaged past its first page used to end every
    scheduled pass as a traceback before the first household, with no page
    and no log. Now the pass reaches its root, serves no household, writes
    both - the checkpoint's own sentence first under Records that need a
    person - and the last-pass file carries its own reason."""
    from contextlib import contextmanager

    @contextmanager
    def damaged(where):
        data = bytearray(where.read_bytes())
        for i in range(4096, len(data)):
            data[i] = 0xA5
        where.write_bytes(bytes(data))
        yield

    code, page, logged, written = _the_scheduled_pass_with(tmp_path, monkeypatch, damaged)
    assert code == 1
    records = page[page.index(runner_module.STATUS_RECORDS_HEADING):]
    first = records.split("<li>", 2)[1]
    assert first.startswith("No household was served this pass") and "Set the file aside" in first
    assert "No household was served this pass" in logged and "Traceback" not in logged
    assert written["reason_code"] == runner_module.PASS_CHECKPOINT_UNREADABLE
    assert runner_module.PASS_REASONS[runner_module.PASS_CHECKPOINT_UNREADABLE] in \
        runner_module.last_pass_line()["text"]


def test_a_busy_checkpoint_is_never_called_another_root(tmp_path, monkeypatch):
    """SF1: three states, three sentences. Busy says try again and never
    set-aside; it is never "not the root", which sends a person to
    move-root."""
    import sqlite3
    from contextlib import contextmanager

    @contextmanager
    def held_elsewhere(where):
        holder = sqlite3.connect(where, isolation_level=None)
        holder.execute("BEGIN EXCLUSIVE")
        try:
            yield
        finally:
            holder.execute("ROLLBACK")
            holder.close()

    code, page, _logged, written = _the_scheduled_pass_with(tmp_path, monkeypatch, held_elsewhere)
    assert code == 1
    assert written["reason_code"] == runner_module.PASS_CHECKPOINT_BUSY
    assert "the next pass tries again" in page and "Set the file aside" not in page
    assert "belongs to" not in runner_module.last_pass_line()["text"]


def test_lines_from_other_machines_that_cannot_be_listed_are_said_where_they_would_be(
        tmp_path, samples, monkeypatch):
    """SF3: a checkpoint that fails only when asked for the lines from other
    machines leaves a sentence in their place on the page, never nothing."""
    from tracker import checkpoint

    clients = tmp_path / "Clients"
    build_engagement(clients, samples)

    def unlisted():
        raise checkpoint.CheckpointUnavailable("record-heads.db", "SQLITE_IOERR_READ")

    monkeypatch.setattr(store, "foreign_lines", unlisted)
    report = runner_module.status_report(discover_engagements(clients))
    page = html.unescape(write_status_page(clients, report).read_text(encoding="utf-8"))
    assert "Lines from other machines could not be listed this pass: record-heads.db" in page
    assert "SQLITE_IOERR_READ" in page


# ------------------- the page reads the store the walk left (decision 192) ----


def _count_journal_reads(monkeypatch) -> list[Path]:
    """Every journal read from now on: each goes through ``Path.read_bytes``
    (``ledger._bytes_of``)."""
    read: list[Path] = []
    real = Path.read_bytes

    def counting(self):
        if self.name == ledger.LEDGER_FILENAME:
            read.append(Path(self))
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    return read


def _a_parked_file(engagement_dir) -> str:
    """One file parked for a person in this return's record."""
    seed_index(engagement_dir, [IndexEntry(
        received="2026-02-02", original_name="unclear scan.pdf", size_kb=5.0, digest="cd" * 32,
        identifier="", prepared_location="", pbc_location="unclear scan.pdf",
        decision=NEEDS_REVIEW, reason="no request matched")])
    return "unclear scan.pdf"


def test_the_practice_page_reads_no_journal_the_walk_has_followed(tmp_path, samples, monkeypatch):
    """F-M-3: the page read every return's journal four more times after
    the walk had followed each one. It now reads the store the walk left -
    and still carries each return's counts and parked files."""
    first, second = _two_households(tmp_path, samples)
    for one in (first, second):
        a_pass(one, today=FRIDAY, reminders=REMINDERS_NEVER)
    parked = _a_parked_file(first.path)
    registry = discover_engagements(tmp_path)
    read = _count_journal_reads(monkeypatch)

    report = runner_module.status_report(registry)
    write_status_page(tmp_path, report)

    assert read == []
    assert all(run.statuses for run in report.runs)
    assert parked in _page(tmp_path)
    # The recorder sees a journal read when one is made.
    read_index(first.path)
    assert ledger.path_for(first.path) in read


def test_the_page_follows_a_journal_the_store_does_not_hold(tmp_path, samples):
    """R5: a return the store has no row for is built from its journal
    for the page, as every reader builds one - never shown blank."""
    first, second = _two_households(tmp_path, samples)
    earlier = a_pass(first, today=FRIDAY, reminders=REMINDERS_NEVER)
    parked = _a_parked_file(first.path)
    registry = discover_engagements(tmp_path)
    assert store.forget(store.connect(), first.path)

    report = runner_module.status_report(registry)
    write_status_page(tmp_path, report)

    row = next(run for run in report.runs if run.engagement.path == first.path)
    assert row.statuses == earlier.statuses and row.outstanding == earlier.outstanding
    assert parked in _page(tmp_path)


def test_an_index_the_page_cannot_read_is_said_by_its_class_never_its_message(
        tmp_path, samples, monkeypatch):
    """R7: the page's unreadable-index sentence names the class and the
    errno's code - an OSError's message names a client's folder (security
    principle 7)."""
    import errno

    import tracker.runner as runner

    engagement = build_engagement(tmp_path, samples)
    where = str(engagement.path / "somewhere private")

    def refused(folder, *args, **kwargs):
        raise PermissionError(errno.EACCES, "Permission denied", where)

    monkeypatch.setattr(runner, "read_index", refused)
    write_status_page(tmp_path, runner_module.status_report(discover_engagements(tmp_path)))

    page = _page(tmp_path)
    assert runner.STATUS_INDEX_UNREADABLE.format(
        label=engagement.label, error="PermissionError (EACCES)") in page
    assert where not in page


def test_only_the_practice_page_reads_the_store_without_following_the_journal():
    """R6: a writer or a card that read without following could act on
    rows behind the journal, so ``follow=False`` is passed in the runner's
    page and nowhere else in the package."""
    package = Path(runner_module.__file__).parent
    passing = sorted(one.name for one in package.glob("*.py")
                     if "follow=False" in one.read_text(encoding="utf-8"))
    assert passing == ["runner.py"]


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
    from tracker.runner import CANCELLED_NO_DRAFT, WHY_CANCELLED, _why_not_served

    engagement = build_engagement(tmp_path / "Clients", samples, drops=THREE_DROPS)
    run = a_pass(engagement, today=SATURDAY, reminders=REMINDERS_ALWAYS,
                 watch=StopAt(tmp_path / "data").watch)
    assert run.cancelled and run.drafted is None and run.draft_note == CANCELLED_NO_DRAFT
    assert not (engagement.path / DRAFT_FILENAME).exists()
    assert _why_not_served([run]) == WHY_CANCELLED


def test_the_scheduled_pass_fills_the_progress_file_and_prints_no_progress_line(
        tmp_path, samples, capsys, monkeypatch):
    from tracker.progress import PROGRESS_KEY, Watch

    build_engagement(tmp_path, samples)
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
    assert main([str(tmp_path), "--date", FRIDAY.isoformat(), "--reminders", "never"]) == 0
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
    from tests.conftest import seed_statuses
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
