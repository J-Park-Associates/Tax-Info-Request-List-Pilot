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

from tests.conftest import make_engagement, seed_index
from tests.samples import DEMO_ITEMS, PRIOR_YEAR, YEAR, build_samples
from tracker import ledger, store
from tracker.filer import NEEDS_REVIEW, IndexEntry, read_index
from tracker.manifest import (
    EngagementInfo,
    Override,
    RequestItem,
    Status,
    load_engagement_info,
    save_rules,
)
from tracker.records import YES, rule_from_json
from tracker.registry import SKIP_ROLLED_FORWARD, Engagement, Registry, discover_engagements
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
    run_engagement,
    run_registry,
    should_draft,
    write_status_page,
)
from tracker.scaffold import (
    PBC_DIR_NAME,
    PREPARED_DIR_NAME,
    SHARED_DIR_NAME,
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


def pass_on(stamped_on, engagement, day, **kwargs):
    """One pass on ``day``, with the record stamped that day."""
    stamped_on(day)
    return run_engagement(engagement, today=day, **kwargs)


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
                     name="Smith TY2025", **kwargs):
    """A scaffolded engagement with files waiting in the client's drop folder."""
    # The engagement's details in the record are where the draft learns
    # who the client is; the Engagement dataclass only echoes it.
    folder = make_engagement(tmp_path / name, DEMO_ITEMS,
                             EngagementInfo(client="John Smith", firm="J Park"), scaffold=False)
    result = scaffold_engagement(folder)
    for drop in drops:
        (result.shared_dir / drop).write_bytes((samples / drop).read_bytes())
    return Engagement(path=folder, info=EngagementInfo(client="John Smith", firm="J Park", **kwargs))


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
    run = run_engagement(engagement, today=FRIDAY)

    assert run.ok and run.filed == 1
    assert run.statuses[Status.PARTIAL] == 1
    assert run.drafted is None
    assert f"not {DRAFT_DAY}" in run.draft_note.lower()
    assert not (engagement.path / DRAFT_FILENAME).exists()


def test_the_saturday_run_writes_a_draft(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    run = run_engagement(engagement, today=SATURDAY)

    assert run.drafted == engagement.path / DRAFT_FILENAME
    text = run.drafted.read_text(encoding="utf-8")
    assert text.startswith(DRAFT_BANNER)
    assert "Hi John Smith," in text


def test_a_manual_run_drafts_on_a_weekday(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    run = run_engagement(engagement, today=FRIDAY, reminders=REMINDERS_ALWAYS)
    assert run.drafted == engagement.path / DRAFT_FILENAME


def test_an_edited_draft_survives_the_next_weekly_run(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    first = run_engagement(engagement, today=SATURDAY).drafted
    # Read and write the bytes as they are: these drafts are CRLF for Windows,
    # and universal-newline translation would make this test lie.
    edited = first.read_bytes() + b"\r\nPS: ask about the rental.\r\n"
    first.write_bytes(edited)

    second = run_engagement(engagement, today=SATURDAY + dt.timedelta(days=7))

    assert first.read_bytes() == edited, "an edit must never be clobbered"
    assert second.drafted.name == NEW_DRAFT_FILENAME
    assert "has been edited" in second.draft_note


def test_an_edited_second_draft_is_never_clobbered_by_the_next_repeat(tmp_path, samples):
    # The draft day's repeat runs several times. The first made room for the
    # person's edits by writing NEW; the next must not take NEW's edits too.
    from tracker.reminder import BOTH_DRAFTS_EDITED

    engagement = build_engagement(tmp_path, samples)
    first = run_engagement(engagement, today=SATURDAY).drafted
    first.write_bytes(first.read_bytes() + b"\r\nPS: ask about the rental.\r\n")
    second = run_engagement(engagement, today=SATURDAY).drafted
    assert second.name == NEW_DRAFT_FILENAME
    edited_new = second.read_bytes() + b"\r\nPPS: and the boat.\r\n"
    second.write_bytes(edited_new)

    third = run_engagement(engagement, today=SATURDAY)
    assert third.drafted is None and third.ok
    assert third.draft_note == BOTH_DRAFTS_EDITED
    assert second.read_bytes() == edited_new


def test_a_draft_day_with_nothing_to_chase_refreshes_the_runs_own_stale_draft(tmp_path, samples, stamped_on):
    # Last week's draft asked for a document that has since arrived. The
    # run's own unedited draft is rewritten as today's (nothing to chase),
    # so it is neither stale text nor an old date; a draft a person edited
    # is theirs and stays exactly as it is.
    only_the_return = [i for i in DEMO_ITEMS if i.identifier == "B01"]
    folder = make_engagement(tmp_path / "Settled TY2025", only_the_return, scaffold=False)
    scaffolded = scaffold_engagement(folder)
    engagement = Engagement(path=folder, info=EngagementInfo(client="John Smith"))
    drafted = pass_on(stamped_on, engagement, SATURDAY - dt.timedelta(days=7)).drafted
    stale = drafted.read_bytes()

    name = f"{PRIOR_YEAR} Form 1040 Tax Return.pdf"
    (scaffolded.shared_dir / name).write_bytes((samples / name).read_bytes())
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
    first = run_engagement(engagement, today=SATURDAY).drafted
    second = run_engagement(engagement, today=SATURDAY + dt.timedelta(days=7))

    assert second.drafted == first
    assert not (engagement.path / NEW_DRAFT_FILENAME).exists()


def test_nothing_outstanding_means_no_draft_file(tmp_path, samples):
    """Everything in: there is nothing to chase, so no draft is written."""
    only_the_return = [i for i in DEMO_ITEMS if i.identifier == "B01"]
    folder = make_engagement(tmp_path / "Settled TY2025", only_the_return, scaffold=False)
    scaffolded = scaffold_engagement(folder)
    name = f"{PRIOR_YEAR} Form 1040 Tax Return.pdf"
    (scaffolded.shared_dir / name).write_bytes((samples / name).read_bytes())

    run = run_engagement(Engagement(path=folder, info=EngagementInfo(client="John Smith")), today=SATURDAY)

    assert run.statuses == {Status.RECEIVED: 1}
    assert run.outstanding == 0
    assert run.drafted is None
    assert run.draft_note == NOTHING_OUTSTANDING
    assert not (folder / DRAFT_FILENAME).exists()


def test_a_dry_run_writes_nothing_at_all(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    run = run_engagement(engagement, today=SATURDAY, dry_run=True)

    assert run.drafted is None
    assert "would draft" in run.draft_note
    assert not (engagement.path / DRAFT_FILENAME).exists()
    assert (engagement.path / SHARED_DIR_NAME / f"W-2 John Smith {YEAR}.pdf").exists(), (
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
    run_engagement(engagement, today=SATURDAY, dry_run=True)
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
    run = run_engagement(Engagement(path=tmp_path / "no-such-client"), today=SATURDAY)
    assert run.error.startswith("folder not found")


def test_an_unreadable_record_is_recorded_not_raised(tmp_path):
    folder = tmp_path / "Broken 2025"
    folder.mkdir()
    ledger.path_for(folder).write_text("this is not a record\n", encoding="utf-8")
    run = run_engagement(Engagement(path=folder), today=SATURDAY)
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
    run = run_engagement(engagement, today=SATURDAY)
    assert run.ok and run.skipped.startswith("inactive")
    assert run.filed == 0


def test_only_selects_a_subset(tmp_path, samples):
    smith = build_engagement(tmp_path, samples, name="Smith TY2025")
    jones = build_engagement(tmp_path, samples, name="Jones TY2025")
    registry = Registry(source=tmp_path,
                        engagements=[smith, jones])

    report = run_registry(registry, today=SATURDAY, only="jones")

    assert len(report.runs) == 1
    assert (jones.path / DRAFT_FILENAME).exists()
    assert not (smith.path / DRAFT_FILENAME).exists()


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
    engagement = build_engagement(tmp_path / "Clients" / "Smith", samples)
    edit_details(engagement.path, client="John Smith", due=dt.date(2026, 4, 15),
                 firm="J Park & Associates, CPA")

    report = run_registry(discover_engagements(tmp_path / "Clients"), today=SATURDAY)

    assert len(report.processed) == 1
    draft = (engagement.path / DRAFT_FILENAME).read_text(encoding="utf-8")
    assert "Hi John Smith," in draft
    assert "April 15, 2026" in draft
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
    folder = make_engagement(tmp_path / "Loose 2025", [RequestItem(identifier="A01", document="Anything")])
    engagement = Engagement(path=folder)
    run = run_engagement(engagement, today=FRIDAY)
    assert run.ok
    assert any("never be filed automatically" in w for w in run.warnings)
    text = format_report(run_registry(Registry(source=tmp_path, engagements=[engagement]), today=FRIDAY))
    assert "! Row 1 (A01)" in text


def test_not_applicable_and_accepted_rows_are_not_outstanding(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples, drops=())
    edit_rows(engagement.path, A01={"manual_override": Override.ACCEPTED,
                                    "override_reason": "Client confirmed this is the final version"},
              A02={"manual_override": Override.NOT_APPLICABLE})
    run = run_engagement(engagement, today=FRIDAY)
    assert run.ok
    assert run.statuses.get(Status.RECEIVED) == 1          # the accepted row
    assert Override.NOT_APPLICABLE not in run.statuses
    assert run.outstanding == len(DEMO_ITEMS) - 2


def test_a_row_added_in_the_editor_has_its_folder_by_the_next_run(tmp_path, samples):
    from tracker.scaffold import README_NAME

    engagement = build_engagement(tmp_path, samples, drops=())
    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement.path)]
    rows.append(RequestItem(identifier="Z01", document="Rental Property Records", period="TY2025",
                            allowed_extensions=("pdf",), any_keywords=("schedule e",)))
    save_rules(engagement.path, rows, load_engagement_info(engagement.path))
    run = run_engagement(engagement, today=FRIDAY)
    assert run.ok
    assert any(p.name.startswith("Z01") for p in (engagement.path / PREPARED_DIR_NAME).iterdir())
    assert "Z01 - Rental Property Records" in (engagement.path / SHARED_DIR_NAME / README_NAME).read_text(encoding="utf-8")
    assert run.statuses.get(Status.MISSING, 0) >= 1 and "folder not found" not in str(run.statuses)


def test_a_rolled_forward_engagement_is_retired_by_its_successor(tmp_path, samples):
    from tracker.registry import discover_engagements

    prior = build_engagement(tmp_path / "Clients", samples, name="Smith 2025")
    edit_details(prior.path, client="John")
    new = build_engagement(tmp_path / "Clients", samples, name="Smith 2026", drops=())
    edit_details(new.path, client="John", rolled_from=str(prior.path))

    registry = discover_engagements(tmp_path / "Clients")
    by_name = {e.path.name: e for e in registry.engagements}
    assert by_name["Smith 2025"].active is False
    assert by_name["Smith 2025"].superseded_by == "Smith 2026"
    assert by_name["Smith 2026"].active is True

    report = run_registry(registry, today=SATURDAY)
    outcomes = {r.engagement.path.name: r for r in report.runs}
    assert outcomes["Smith 2025"].skipped == SKIP_ROLLED_FORWARD.format(successor="Smith 2026")
    assert not (prior.path / DRAFT_FILENAME).exists()          # last year is not chased
    assert (prior.path / SHARED_DIR_NAME / f"W-2 John Smith {YEAR}.pdf").exists()   # and not touched
    assert outcomes["Smith 2026"].ok


def test_strays_in_prepared_reach_the_run_report(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples, drops=())
    (engagement.path / PREPARED_DIR_NAME / "loose.txt").write_text("x", encoding="utf-8")
    run = run_engagement(engagement, today=FRIDAY)
    assert run.ok
    assert any(f"loose.txt is loose in {PREPARED_DIR_NAME}/" in w for w in run.warnings)


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
    build_engagement(clients, samples, name="Good TY2025")
    bad = clients / "Bad TY2025"
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
    older = build_engagement(tmp_path, samples, drops=("vacation photo.jpg",), name="Older TY2025")
    newer = build_engagement(tmp_path, samples, drops=("Mortgage Notes.docx",), name="Newer TY2025")
    first = run_engagement(older, today=FRIDAY, reminders=REMINDERS_NEVER)
    second = run_engagement(newer, today=SATURDAY, reminders=REMINDERS_NEVER)
    assert first.review == 1 and second.review == 1

    page = write_status_page(tmp_path, RunReport(today=SATURDAY, runs=[first, second]))
    text = page.read_text(encoding="utf-8")

    assert text.index("Mortgage Notes.docx") < text.index("vacation photo.jpg")
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
    run = run_engagement(engagement, today=FRIDAY, reminders=REMINDERS_NEVER)

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
    run = run_engagement(engagement, today=FRIDAY, reminders=REMINDERS_NEVER, dry_run=True)

    assert run.ok and taken == [True]


def test_a_file_named_like_markup_is_shown_as_a_name_not_rendered(tmp_path):
    """Every value on the page goes through html.escape. The name cannot be
    made on Windows, so it arrives the way it would in life: an index row
    written elsewhere, from a client's folder that is not this machine's."""
    folder = make_engagement(tmp_path / "Evil TY2025", DEMO_ITEMS, scaffold=False)
    name = "<b>evil</b>.pdf"
    reason = "<i>nothing matched</i>"
    seed_index(folder, [IndexEntry(
        received=FRIDAY.isoformat(), original_name=name, size_kb=1.0, digest="0" * 8,
        identifier="", prepared_location="",
        pbc_location=f"{SHARED_DIR_NAME}/{PBC_DIR_NAME}/{name}",
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
    earlier = run_engagement(untouched, today=FRIDAY, reminders=REMINDERS_NEVER)
    run = run_engagement(scanned, today=FRIDAY, reminders=REMINDERS_NEVER)

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
