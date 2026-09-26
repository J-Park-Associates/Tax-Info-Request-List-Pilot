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
from pathlib import Path

import pytest

import tracker.runner as runner_module
from tests.conftest import make_engagement, seed_index
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
    FILED_INTO_FED,
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
    return [{k: v for k, v in e.items() if k not in (ledger.EVENT_KEY, ledger.AT_KEY)}
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

    build_engagement(tmp_path, samples, name="Smith TY2025 \u2192 Ω")
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", console)
    code = main([str(tmp_path), "--dry-run", "--reminders", REMINDERS_NEVER])
    console.flush()
    shown = console.buffer.getvalue().decode("cp1252")
    assert code == 0
    assert "Smith TY2025 \\u2192 \\u03a9" in shown


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
    import json
    import shutil

    build_engagement(tmp_path / "Clients", samples, name="Good")
    bad = build_engagement(tmp_path / "Clients", samples, name="Bad 2025", drops=())
    lines = ledger.read_events(bad.path)
    with ledger.path_for(bad.path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({ledger.EVENT_KEY: line.pop("event"), ledger.AT_KEY: "2026-01-01T00:00:00",
                                 **line}) + "\n")
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
        "carries a status for 'A01' that is not a mapping")


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
        received=FRIDAY.isoformat(), original_name=name, size_kb=1.0, digest="0" * 8,
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


def test_the_dropping_households_pass_says_what_it_filed_into_a_fed_return(tmp_path, samples):
    """A filing into a fed return is the other return's row and the other
    household's report - but it came out of *this* drop folder, and a pass
    that said "filed 0" of a document it had just filed elsewhere told the
    person watching the wrong thing about their own inbox. One sentence per
    fed return that received something, on the first of this household's
    own returns. The same sentence rides the app's *Run now* reply, which
    ``tests/test_api.py`` pins from the other side."""
    from tests.samples import SCRATCH_CLIENT, text_pdf
    from tracker.filer import FILED

    personal, [fed] = a_fed_household(tmp_path, samples)
    text_pdf(inbox_of(personal.path) / "trial balance.pdf",
             [f"Trial balance as of December 31 {YEAR}", SCRATCH_CLIENT])
    household = household_of(personal.path)

    [run] = run_household(household, [personal], today=FRIDAY, reminders=REMINDERS_NEVER,
                          registry=discover_engagements(tmp_path))

    assert run.ok and run.filed == 0 and read_index(personal.path) == []
    assert FILED_INTO_FED.format(n=1, label=fed.label) in run.warnings
    [row] = read_index(fed.path)
    assert row.decision == FILED and row.identifier == "B01"


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
    nor the firm's name for it; the household that holds it lists it as its
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

    assert run.ok
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
    """132's F-4 ruling, carried into the received list: the document is in
    the other household's index, so it is on that household's list - at
    once, by the pass that filed it - and on no list of the README in the
    folder it was dropped in, which never names the other household or its
    return. A document parked at home is this household's, counted under
    review."""
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

    assert run.ok
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
    saying how to set one; a root on the command line still wins."""
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

    assert main([str(by_hand), SETTINGS_FLAG, str(settings), "--reminders", "never"]) == 0
    assert (by_hand / STATUS_PAGE_FILENAME).is_file()

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

    # A person running one folder by hand, no log: a root on the command line still wins.
    assert main([str(old), "--reminders", "never"]) == 0
    assert (old / STATUS_PAGE_FILENAME).is_file()
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
