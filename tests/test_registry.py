"""Tests for tracker/registry.py — an engagement is a folder with a record in it.

The rule under test: nothing has to be registered. The scheduled run walks
the clients folder, finds every record, and reads each one's engagement
details. A client nobody typed into a list is still found; a record nobody
can read is still reported; a folder holding only the workbook the tracker
no longer reads is listed as a legacy folder, not an engagement.
"""

import datetime as dt
from pathlib import Path

import pytest

from tests.conftest import make_engagement
from tracker import ledger
from tracker.manifest import EngagementInfo, RequestItem
from tracker.registry import (
    LEGACY_FOLDER,
    LEGACY_MANIFEST_FILENAME,
    MAX_DEPTH,
    Engagement,
    RegistryError,
    discover_engagements,
    engagement_dirs,
)
from tracker.scaffold import PREPARED_DIR_NAME

ITEMS = [RequestItem(identifier="A01", document="W-2")]


def make(root, *parts, info=None, scaffold=False):
    return make_engagement(root.joinpath(*parts), ITEMS, info, scaffold=scaffold)


def test_a_rolled_forward_prior_stays_retired_when_the_clients_root_moves(tmp_path):
    # Rolled From is written as an absolute path. A root moved to another
    # drive (or renamed) would otherwise bring every prior back to life and
    # the draft day would chase last year's list (the ninth reading).
    from tracker.registry import engagement_from, mark_superseded

    root = tmp_path / "Clients"
    prior = make(root, "Smith", "Smith - 2025")
    make(root, "Smith", "Smith - 2026", info=EngagementInfo(rolled_from=str(prior.resolve())))
    moved = tmp_path / "Moved"
    root.rename(moved)

    found = [engagement_from(p) for p in engagement_dirs(moved)]
    retired = {e.path.name: e.superseded_by for e in mark_superseded(found)}
    assert retired["Smith - 2025"] and not retired["Smith - 2026"]


def test_a_year_level_above_the_client_never_retires_the_new_engagement_itself(tmp_path, monkeypatch):
    # The tenth reading: with Clients/2025/Smith/1040 and Clients/2026/Smith/1040
    # the last two names are the same every year, and the two-name fallback
    # retired the new engagement into itself; the run then skipped both.
    from tracker.registry import engagement_from, mark_superseded
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    root = tmp_path / "Clients"
    # Three engagements called "1040": the store keys them by their path
    # under the clients root, so the root is recorded the way the app
    # records it before any of them is made.
    root.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    set_clients_root(root)
    prior = make(root, "2025", "Smith", "1040")
    make(root, "2026", "Smith", "1040", info=EngagementInfo(rolled_from=str(prior.resolve())))
    make(root, "Chicago", "Smith", "1040")                 # another office's live client of the same name
    found = [engagement_from(p) for p in engagement_dirs(root)]
    retired = {str(e.path.relative_to(root)): e.superseded_by for e in mark_superseded(found)}
    assert retired == {str(Path("2025", "Smith", "1040")): "1040", str(Path("2026", "Smith", "1040")): "",
                       str(Path("Chicago", "Smith", "1040")): ""}

    root.rename(tmp_path / "Moved")                        # the root moves: the third name still decides
    moved = tmp_path / "Moved"
    found = [engagement_from(p) for p in engagement_dirs(moved)]
    retired = {str(e.path.relative_to(moved)): e.superseded_by for e in mark_superseded(found)}
    assert retired[str(Path("2025", "Smith", "1040"))] == "1040"
    assert retired[str(Path("2026", "Smith", "1040"))] == "" and retired[str(Path("Chicago", "Smith", "1040"))] == ""


def test_a_rolled_from_that_matches_nothing_is_a_warning_not_a_silence(tmp_path):
    # The eleventh reading: a Rolled From that resolved to nothing and
    # tail-matched nothing retired nothing and said nothing, and the
    # scheduled run kept chasing last year's list.
    from tracker.registry import ROLLED_FROM_UNMATCHED, engagement_from, mark_superseded

    root = tmp_path / "Clients"
    make(root, "Smith", "Smith - 2025")
    make(root, "Smith", "Smith - 2026", info=EngagementInfo(rolled_from="Smith - 2025"))   # hand-typed, relative
    found = [engagement_from(p) for p in engagement_dirs(root)]
    marked = {e.path.name: e for e in mark_superseded(found)}
    assert marked["Smith - 2025"].superseded_by == "" and marked["Smith - 2025"].warning == ""
    assert marked["Smith - 2026"].warning == ROLLED_FROM_UNMATCHED.format(rolled_from="Smith - 2025")
    assert marked["Smith - 2026"].active

    # A folder the walk could not list is never taken as the prior: its
    # report survives rather than becoming a benign skip.
    unlisted = Engagement(path=root / "Jones" / "Jones - 2025", problem="could not be listed (Access is denied)")
    successor = engagement_from(make(root, "Jones", "Jones - 2026",
                                     info=EngagementInfo(rolled_from=str(unlisted.path))))
    marked = {e.path.name: e for e in mark_superseded([unlisted, successor])}
    assert marked["Jones - 2025"].superseded_by == "" and marked["Jones - 2025"].problem
    assert marked["Jones - 2026"].warning


def test_a_client_folder_the_walk_cannot_list_is_a_problem_row_not_a_silence(tmp_path):
    # The tenth reading: an ACL that denies the run's account made a whole
    # client vanish from the registry, and the run reported success.
    from tests.samples import listing_denied

    root = tmp_path / "Clients"
    make(root, "Jones", "Jones - 2025")
    smith = root / "Smith"
    make(root, "Smith", "Smith - 2025")

    with listing_denied(smith):
        registry = discover_engagements(root)
    by_name = {e.path.name: e for e in registry.engagements}
    assert by_name["Jones - 2025"].problem == ""
    assert "could not be listed" in by_name["Smith"].problem      # the run reports it as an error, by name
    assert [e.path.name for e in registry.engagements if not e.problem] == ["Jones - 2025"]


def test_every_folder_with_a_record_is_an_engagement(tmp_path):
    a = make(tmp_path, "Smith", "Smith 2025")
    b = make(tmp_path, "Acme Corp TY2025")
    c = make(tmp_path, "Office B", "Trusts", "Jones Trust 2025")
    assert engagement_dirs(tmp_path) == sorted([a, b, c])


def test_an_engagements_own_subfolders_are_never_engagements(tmp_path):
    outer = make(tmp_path, "Smith 2025", scaffold=True)
    # A stray record inside Prepared/ (or anywhere below) does not split
    # the engagement in two.
    ledger.path_for(outer / PREPARED_DIR_NAME).write_text("", encoding="utf-8")
    assert engagement_dirs(tmp_path) == [outer]


def test_hidden_and_underscore_folders_are_skipped(tmp_path):
    make(tmp_path, ".tmp.driveupload", "Ghost 2025")
    make(tmp_path, "_archive", "Old 2019")
    real = make(tmp_path, "Real 2025")
    assert engagement_dirs(tmp_path) == [real]


def test_discovery_is_depth_limited(tmp_path):
    deep = make(tmp_path, *[f"level{i}" for i in range(MAX_DEPTH + 1)], "Too Deep 2025")
    shallow = make(tmp_path, "Shallow 2025")
    assert engagement_dirs(tmp_path) == [shallow]
    assert deep not in engagement_dirs(tmp_path)


def test_the_engagement_details_drive_the_run(tmp_path):
    make(tmp_path, "Smith 2025", info=EngagementInfo(
        client="John Smith", link="https://drive.example/abc",
        due=dt.date(2026, 3, 15), sender="Jason Park", firm="J Park",
    ))
    make(tmp_path, "Acme TY2025", info=EngagementInfo(client="Dana Lee", reminders=False))
    make(tmp_path, "Old 2024", info=EngagementInfo(active=False))

    registry = discover_engagements(tmp_path)
    by_label = {e.label: e for e in registry.engagements}
    smith = by_label["Smith 2025"]
    assert smith.client == "John Smith" and smith.due == dt.date(2026, 3, 15)
    assert smith.link == "https://drive.example/abc" and smith.sender == "Jason Park"
    assert by_label["Acme TY2025"].reminders is False
    assert by_label["Old 2024"].active is False
    assert [e.label for e in registry.active] == ["Acme TY2025", "Smith 2025"]
    assert registry.source == tmp_path


def test_an_unreadable_record_is_listed_with_its_problem_not_dropped(tmp_path):
    folder = tmp_path / "Broken 2025"
    folder.mkdir()
    ledger.path_for(folder).write_text("{this line is not an event}\n", encoding="utf-8")
    make(tmp_path, "Fine 2025")
    registry = discover_engagements(tmp_path)
    broken = next(e for e in registry.engagements if e.path == folder)
    assert "does not read as an event" in broken.problem
    assert len(registry.engagements) == 2


def test_a_folder_with_only_a_legacy_workbook_is_not_an_engagement_and_is_named_as_such(tmp_path):
    """Decision 104: a folder from before it, holding the workbook the
    tracker no longer reads and no record, is listed as a legacy folder -
    not descended into, not run, and never imported. A folder whose record
    carries no rules with that workbook beside it is listed the same way."""
    from tracker.runner import run_engagement

    legacy = tmp_path / "Smith 2024"
    (legacy / "Prepared").mkdir(parents=True)
    (legacy / LEGACY_MANIFEST_FILENAME).write_bytes(b"PK any bytes at all")
    make(legacy, "Prepared", "Inner 2024")             # below it: never reached

    registry = discover_engagements(tmp_path)          # a problem row is a found row
    [found] = registry.engagements
    assert found.path == legacy
    assert found.problem == LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME)
    assert engagement_dirs(tmp_path) == []             # the store's CLI and the app list none
    run = run_engagement(found, today=dt.date(2026, 3, 13))
    assert found.problem in run.error and run.ok is False
    assert list(legacy.glob("*.jsonl")) == []           # nothing imported, nothing written

    half = tmp_path / "Jones 2024"
    half.mkdir()
    ledger.path_for(half).write_text("", encoding="utf-8")     # a record with no rules in it
    (half / LEGACY_MANIFEST_FILENAME).write_bytes(b"PK")
    listed = {e.path.name: e for e in discover_engagements(tmp_path).engagements}
    assert listed["Jones 2024"].problem == LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME)
    assert engagement_dirs(tmp_path) == [half]          # it holds a record, so the walk finds it


def test_find_matches_label_or_path(tmp_path):
    make(tmp_path, "Smith Family 2025", info=EngagementInfo(name="Smiths"))
    make(tmp_path, "Acme 2025")
    registry = discover_engagements(tmp_path)
    assert [e.label for e in registry.find("smith")] == ["Smiths"]
    assert [e.label for e in registry.find("acme")] == ["Acme 2025"]
    assert registry.find("nobody") == []


def test_label_falls_back_to_the_folder_name(tmp_path):
    folder = tmp_path / "Smith 2025"
    assert Engagement(path=folder).label == "Smith 2025"
    assert Engagement(path=folder, info=EngagementInfo(name="The Smiths")).label == "The Smiths"


def test_a_root_that_is_not_a_folder_is_an_error(tmp_path):
    with pytest.raises(RegistryError, match="not a folder"):
        discover_engagements(tmp_path / "nowhere")


def test_a_root_with_no_engagement_is_an_error_not_a_quiet_no_op(tmp_path):
    (tmp_path / "Empty").mkdir()
    with pytest.raises(RegistryError, match="no engagement found"):
        discover_engagements(tmp_path)


def test_an_engagement_is_its_details(tmp_path):
    # Every field of the engagement's details is reachable on the Engagement
    # without being declared a second time.
    from dataclasses import fields

    make(tmp_path, "Smith 2025", info=EngagementInfo(client="John", sender="Jason"))
    [engagement] = discover_engagements(tmp_path).engagements
    for field in fields(EngagementInfo):
        assert getattr(engagement, field.name) == getattr(engagement.info, field.name)
    assert engagement.client == "John" and engagement.sender == "Jason"
    with pytest.raises(AttributeError):
        _ = engagement.no_such_field
