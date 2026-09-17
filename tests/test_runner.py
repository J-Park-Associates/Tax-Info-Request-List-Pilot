"""Tests for tracker/runner.py — the weekly pass over every engagement.

The rules that matter here: reminders are drafted on Saturday and only on
Saturday, an edited draft survives the weekly run, one client's failure never
stops another client's run, and nothing is ever sent.
"""

import datetime as dt

import pytest

from tracker.api import DEMO_ITEMS, _build_samples
from tracker.manifest import Status, create_template
from tracker.manifest import EngagementInfo, write_engagement_info
from tracker.registry import Engagement, Registry, discover_engagements
from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
from tracker.runner import (
    REMINDERS_ALWAYS,
    REMINDERS_AUTO,
    REMINDERS_NEVER,
    append_log,
    format_report,
    is_draft_day,
    run_engagement,
    run_registry,
    should_draft,
)
from tracker.scaffold import MANIFEST_FILENAME, scaffold_engagement

SATURDAY = dt.date(2026, 3, 14)
FRIDAY = dt.date(2026, 3, 13)
SUNDAY = dt.date(2026, 3, 15)


@pytest.fixture(scope="session")
def samples(tmp_path_factory):
    folder = tmp_path_factory.mktemp("samples")
    _build_samples(folder)
    return folder


def build_engagement(tmp_path, samples, drops=("W-2 John Smith 2025.pdf",),
                     name="Smith TY2025", **kwargs):
    """A scaffolded engagement with files waiting in the client's drop folder."""
    folder = tmp_path / name
    folder.mkdir(parents=True)
    # The Engagement sheet is where the draft learns who the client is; the
    # Engagement dataclass only echoes it.
    create_template(folder / MANIFEST_FILENAME, DEMO_ITEMS,
                    EngagementInfo(client="John Smith", firm="J Park"))
    result = scaffold_engagement(folder)
    for drop in drops:
        (result.shared_dir / drop).write_bytes((samples / drop).read_bytes())
    return Engagement(path=folder, client="John Smith", firm="J Park", **kwargs)


# ------------------------------------------------------------ the Saturday ----


def test_saturday_is_the_draft_day():
    assert is_draft_day(SATURDAY) is True
    assert is_draft_day(FRIDAY) is False
    assert is_draft_day(SUNDAY) is False


@pytest.mark.parametrize("day, expected", [(FRIDAY, False), (SATURDAY, True),
                                           (SUNDAY, False)])
def test_auto_mode_drafts_only_on_saturday(day, expected):
    engagement = Engagement(path="/x")
    assert should_draft(engagement, day, REMINDERS_AUTO) is expected


def test_always_mode_drafts_on_any_day():
    assert should_draft(Engagement(path="/x"), FRIDAY, REMINDERS_ALWAYS) is True


def test_never_mode_suppresses_even_on_saturday():
    assert should_draft(Engagement(path="/x"), SATURDAY, REMINDERS_NEVER) is False


def test_reminders_off_beats_every_mode():
    """A standing decision not to chase this client by email is not a flag."""
    quiet = Engagement(path="/x", reminders=False)
    assert should_draft(quiet, SATURDAY, REMINDERS_AUTO) is False
    assert should_draft(quiet, SATURDAY, REMINDERS_ALWAYS) is False


def test_the_draft_day_can_be_moved():
    monday = dt.date(2026, 3, 16)
    assert should_draft(Engagement(path="/x"), monday, REMINDERS_AUTO, weekday=0) is True
    assert should_draft(Engagement(path="/x"), SATURDAY, REMINDERS_AUTO, weekday=0) is False


# ------------------------------------------------------------- the full pass ----


def test_a_weekday_run_files_and_scans_but_writes_no_draft(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    run = run_engagement(engagement, today=FRIDAY)

    assert run.ok and run.filed == 1
    assert run.statuses[Status.PARTIAL] == 1
    assert run.drafted is None
    assert "not saturday" in run.draft_note.lower()
    assert not (engagement.path / DRAFT_FILENAME).exists()


def test_the_saturday_run_writes_a_draft(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    run = run_engagement(engagement, today=SATURDAY)

    assert run.drafted == engagement.path / DRAFT_FILENAME
    text = run.drafted.read_text(encoding="utf-8")
    assert text.startswith("DRAFT - NOTHING HAS BEEN SENT.")
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


def test_an_untouched_draft_is_refreshed_in_place(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    first = run_engagement(engagement, today=SATURDAY).drafted
    second = run_engagement(engagement, today=SATURDAY + dt.timedelta(days=7))

    assert second.drafted == first
    assert not (engagement.path / NEW_DRAFT_FILENAME).exists()


def test_nothing_outstanding_means_no_draft_file(tmp_path, samples):
    """Everything in: there is nothing to chase, so no draft is written."""
    only_the_return = [i for i in DEMO_ITEMS if i.identifier == "B01"]
    folder = tmp_path / "Settled TY2025"
    folder.mkdir()
    create_template(folder / MANIFEST_FILENAME, only_the_return)
    scaffolded = scaffold_engagement(folder)
    name = "2024 Form 1040 Tax Return.pdf"
    (scaffolded.shared_dir / name).write_bytes((samples / name).read_bytes())

    run = run_engagement(Engagement(path=folder, client="John Smith"), today=SATURDAY)

    assert run.statuses == {Status.RECEIVED: 1}
    assert run.outstanding == 0
    assert run.drafted is None
    assert "nothing outstanding" in run.draft_note
    assert not (folder / DRAFT_FILENAME).exists()


def test_a_dry_run_writes_nothing_at_all(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples)
    run = run_engagement(engagement, today=SATURDAY, dry_run=True)

    assert run.drafted is None
    assert "would draft" in run.draft_note
    assert not (engagement.path / DRAFT_FILENAME).exists()
    assert (engagement.path / "Shared" / "W-2 John Smith 2025.pdf").exists(), (
        "a dry run must not move the client's file"
    )


# --------------------------------------------------------- failure isolation ----


def test_a_missing_folder_is_recorded_not_raised(tmp_path):
    run = run_engagement(Engagement(path=tmp_path / "no-such-client"), today=SATURDAY)
    assert run.error.startswith("folder not found")


def test_an_unreadable_manifest_is_recorded_not_raised(tmp_path):
    folder = tmp_path / "Broken 2025"
    folder.mkdir()
    (folder / MANIFEST_FILENAME).write_text("this is not a workbook", encoding="utf-8")
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
    assert "saturday" in text
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
    log = tmp_path / "runs.log"

    append_log(log, run_registry(registry, today=FRIDAY))
    append_log(log, run_registry(registry, today=SATURDAY))

    text = log.read_text(encoding="utf-8")
    assert text.count("Smith TY2025") == 2
    assert "2026-03-13" in text and "2026-03-14" in text


# ------------------------------------------------------- discovery end to end ----


def test_a_clients_folder_drives_a_real_run_with_nothing_registered(tmp_path, samples):
    engagement = build_engagement(tmp_path / "Clients" / "Smith", samples)
    write_engagement_info(engagement.path / MANIFEST_FILENAME, EngagementInfo(
        client="John Smith", due=dt.date(2026, 4, 15), firm="J Park & Associates, CPA",
    ))

    report = run_registry(discover_engagements(tmp_path / "Clients"), today=SATURDAY)

    assert len(report.processed) == 1
    draft = (engagement.path / DRAFT_FILENAME).read_text(encoding="utf-8")
    assert "Hi John Smith," in draft
    assert "April 15, 2026" in draft
    assert "J Park & Associates, CPA" in draft


def test_an_engagement_whose_manifest_cannot_be_read_fails_alone(tmp_path, samples):
    good = build_engagement(tmp_path / "Clients", samples, name="Good")
    bad = tmp_path / "Clients" / "Bad 2025"
    bad.mkdir()
    (bad / MANIFEST_FILENAME).write_bytes(b"not a workbook")

    report = run_registry(discover_engagements(tmp_path / "Clients"), today=FRIDAY)
    outcomes = {r.engagement.path.name: r for r in report.runs}
    assert outcomes["Good"].ok
    assert "manifest could not be read" in outcomes["Bad 2025"].error


def test_the_run_names_a_manifest_typo_with_its_row_before_touching_files(tmp_path, samples):
    from openpyxl import load_workbook

    engagement = build_engagement(tmp_path, samples)
    manifest = engagement.path / MANIFEST_FILENAME
    wb = load_workbook(manifest)
    wb["Requests"].cell(row=2, column=9, value="(unclosed")
    wb.save(manifest)
    run = run_engagement(engagement, today=FRIDAY)
    assert run.error.startswith("Row 2: Date Pattern is not a valid regex")
    assert (engagement.path / "Shared" / "W-2 John Smith 2025.pdf").exists()   # nothing moved


def test_rows_the_rules_cannot_act_on_are_reported_not_buried(tmp_path, samples):
    from tracker.manifest import RequestItem, create_template

    folder = tmp_path / "Loose 2025"
    folder.mkdir()
    create_template(folder / MANIFEST_FILENAME, [RequestItem(identifier="A01", document="Anything")])
    scaffold_engagement(folder)
    engagement = Engagement(path=folder)
    run = run_engagement(engagement, today=FRIDAY)
    assert run.ok
    assert any("never be filed automatically" in w for w in run.warnings)
    text = format_report(run_registry(Registry(source=tmp_path, engagements=[engagement]), today=FRIDAY))
    assert "! Row 2 (A01)" in text


def test_waived_and_accepted_rows_are_not_outstanding(tmp_path, samples):
    from openpyxl import load_workbook

    engagement = build_engagement(tmp_path, samples, drops=())
    manifest = engagement.path / MANIFEST_FILENAME
    wb = load_workbook(manifest)
    ws = wb["Requests"]
    ws.cell(row=2, column=10, value="Accepted")   # A01
    ws.cell(row=3, column=10, value="Waived")     # A02
    wb.save(manifest)
    run = run_engagement(engagement, today=FRIDAY)
    assert run.ok
    assert run.statuses.get(Status.RECEIVED) == 1          # the accepted row
    assert "Waived" not in run.statuses
    assert run.outstanding == len(DEMO_ITEMS) - 2


def test_a_row_added_in_excel_has_its_folder_by_the_next_run(tmp_path, samples):
    from openpyxl import load_workbook
    from tracker.scaffold import PREPARED_DIR_NAME, README_NAME, SHARED_DIR_NAME

    engagement = build_engagement(tmp_path, samples, drops=())
    manifest = engagement.path / MANIFEST_FILENAME
    wb = load_workbook(manifest)
    wb["Requests"].append(["Z01", "Rental Property Records", "TY2025", 1, "pdf", 5, None, "schedule e", None, None])
    wb.save(manifest)
    run = run_engagement(engagement, today=FRIDAY)
    assert run.ok
    assert any(p.name.startswith("Z01") for p in (engagement.path / PREPARED_DIR_NAME).iterdir())
    assert "Z01 - Rental Property Records" in (engagement.path / SHARED_DIR_NAME / README_NAME).read_text(encoding="utf-8")
    assert run.statuses.get(Status.MISSING, 0) >= 1 and "folder not found" not in str(run.statuses)


def test_a_rolled_forward_engagement_is_retired_by_its_successor(tmp_path, samples):
    from tracker.manifest import EngagementInfo, write_engagement_info
    from tracker.registry import discover_engagements

    prior = build_engagement(tmp_path / "Clients", samples, name="Smith 2025")
    write_engagement_info(prior.path / MANIFEST_FILENAME, EngagementInfo(client="John"))
    new = build_engagement(tmp_path / "Clients", samples, name="Smith 2026", drops=())
    write_engagement_info(new.path / MANIFEST_FILENAME,
                          EngagementInfo(client="John", rolled_from=str(prior.path)))

    registry = discover_engagements(tmp_path / "Clients")
    by_name = {e.path.name: e for e in registry.engagements}
    assert by_name["Smith 2025"].active is False
    assert by_name["Smith 2025"].superseded_by == "Smith 2026"
    assert by_name["Smith 2026"].active is True

    report = run_registry(registry, today=SATURDAY)
    outcomes = {r.engagement.path.name: r for r in report.runs}
    assert outcomes["Smith 2025"].skipped == "rolled forward into Smith 2026"
    assert not (prior.path / DRAFT_FILENAME).exists()          # last year is not chased
    assert (prior.path / "Shared" / "W-2 John Smith 2025.pdf").exists()   # and not touched
    assert outcomes["Smith 2026"].ok


def test_strays_in_prepared_reach_the_run_report(tmp_path, samples):
    engagement = build_engagement(tmp_path, samples, drops=())
    (engagement.path / "Prepared" / "loose.txt").write_text("x", encoding="utf-8")
    run = run_engagement(engagement, today=FRIDAY)
    assert run.ok
    assert any("loose.txt is loose in Prepared/" in w for w in run.warnings)
