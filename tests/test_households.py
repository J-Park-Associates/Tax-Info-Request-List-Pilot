"""Tests for tracker/households.py — the household's own record.

A client folder is a household (decision 125), and a household has a record
of its own: its name, the members a person typed as who its folder is meant
to be shared with, the contact its letters greet and the inbox link they
paste. It is a journal in the private tree, folded by the same functions and
held by the same store a return's is - which is the claim these make.
"""

import datetime as dt

import pytest

from tests.conftest import make_engagement
from tracker import ledger, store
from tracker.households import (
    create_household,
    household_returns,
    load_household_info,
    open_years,
    save_household,
)
from tracker.layout import private_household_dir, return_dir_for
from tracker.locking import engagement_lock
from tracker.manifest import EngagementInfo, ManifestError, RequestItem
from tracker.records import HouseholdInfo, household_to_json

ITEMS = [RequestItem(identifier="A01", document="W-2")]
SMITHS = HouseholdInfo(name="Smith Family", members=("John Smith", "Jane Smith"),
                       contact="John & Jane", link="https://drive.example/inbox")


@pytest.fixture
def household(tmp_path):
    """One household's folder in the private tree, with its record in it."""
    folder = private_household_dir(tmp_path, "Smith Family")
    folder.mkdir(parents=True)
    create_household(folder, SMITHS)
    return folder


def test_a_household_record_is_one_event_and_reads_back(household):
    """The create is one ``household_changed`` line carrying the whole of
    it - what every later edit is a difference from - and the store's own
    columns say the same thing, with nothing for the check to report."""
    [event] = ledger.read_events(household)
    assert event[ledger.EVENT_KEY] == ledger.HOUSEHOLD_CHANGED
    assert event[ledger.HOUSEHOLD_KEY] == household_to_json(SMITHS)
    assert ledger.HOUSEHOLD_CHANGED not in ledger.ROW_EVENTS

    assert load_household_info(household) == SMITHS
    conn = store.connect()
    assert store.kind(conn, household) == store.KIND_HOUSEHOLD
    assert store.household_info(conn, household) == SMITHS
    assert store.check(conn, household.parent.parent, household) == []
    # A household holds no documents and no requests: it is a fact about a
    # folder, not about any paper in it.
    assert store.documents(conn, household) == [] and store.rules(conn, household) == []


def test_a_household_that_already_has_a_record_is_never_written_over(household):
    with pytest.raises(ManifestError, match="Refusing to overwrite a household"):
        create_household(household, HouseholdInfo(name="Somebody Else"))
    assert load_household_info(household) == SMITHS


def test_a_folder_with_no_household_record_is_refused_by_name(tmp_path):
    folder = private_household_dir(tmp_path, "Nobody")
    folder.mkdir(parents=True)
    with pytest.raises(ManifestError, match="no record here"):
        load_household_info(folder)


def test_saving_a_household_records_only_the_fields_that_moved_or_nothing(household):
    """One event per edit, carrying exactly the difference - and a save of
    the same household is not an event, which is what keeps the journal a
    record of decisions rather than of clicks."""
    same = save_household(household, SMITHS)
    assert same.recorded is False and same.fields == ()
    assert len(ledger.read_events(household)) == 1

    from dataclasses import replace

    moved = save_household(household, replace(SMITHS, members=("John Smith",),
                                              contact="John"))
    assert moved.recorded is True and sorted(moved.fields) == ["contact", "members"]
    events = ledger.read_events(household)
    assert len(events) == 2
    assert events[-1][ledger.HOUSEHOLD_KEY] == {"members": ["John Smith"], "contact": "John"}
    assert load_household_info(household).link == SMITHS.link      # untouched
    assert store.check(store.connect(), household.parent.parent, household) == []


def test_a_household_journal_folds_the_same_in_the_ledger_and_the_store(household, tmp_path):
    """The two folds agree about a household exactly as they agree about a
    return: the store is rebuilt from the journal alone and says what the
    journal says."""
    from dataclasses import replace

    save_household(household, replace(SMITHS, link="https://drive.example/moved"))
    folded = ledger.replay(ledger.read_events(household)).household
    assert folded["link"] == "https://drive.example/moved"
    assert folded["members"] == ["John Smith", "Jane Smith"]

    conn = store.connect()
    store.rebuild_engagement(conn, tmp_path, household)
    assert store.check(conn, tmp_path, household) == []
    assert load_household_info(household).link == "https://drive.example/moved"
    assert store.kind(conn, household) == store.KIND_HOUSEHOLD


def test_a_members_list_written_by_hand_as_one_name_is_read_as_one_member(household):
    """The journal is a synced file a person may open: a line naming one
    person must not cost the household its whole record."""
    from tracker.records import household_from_json

    assert household_from_json({"members": "John Smith"}).members == ("John Smith",)
    assert household_from_json({"members": None}).members == ()
    assert household_from_json({}).members == ()


def test_a_household_line_of_the_wrong_shape_is_one_folders_problem(household, tmp_path):
    """A line that parses as JSON and carries the wrong shape is refused by
    name, before a value of it reaches a table."""
    import json

    # A name written as one string is read as one member, so it is no
    # refusal at all: the journal is a synced file somebody may have
    # opened, and one hand-written line must not cost a household its
    # whole record.
    with ledger.path_for(household).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({ledger.EVENT_KEY: ledger.HOUSEHOLD_CHANGED,
                                 ledger.AT_KEY: "2026-01-01T00:00:00",
                                 ledger.HOUSEHOLD_KEY: {"members": "John Smith"}}) + "\n")
    store.rebuild_engagement(store.connect(), tmp_path, household)
    assert load_household_info(household).members == ("John Smith",)
    # A list holding something that is not a name is refused by name.
    with ledger.path_for(household).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({ledger.EVENT_KEY: ledger.HOUSEHOLD_CHANGED,
                                 ledger.AT_KEY: "2026-01-01T00:00:00",
                                 ledger.HOUSEHOLD_KEY: {"members": [17]}}) + "\n")
    with pytest.raises(store.StoreError, match="names a member that is not text"):
        store.rebuild_engagement(store.connect(), tmp_path, household)
    ledger.path_for(household).unlink()          # the fixtures must not meet it


def test_household_returns_are_the_returns_under_it_by_year_then_name(tmp_path, household):
    """Positional, like discovery: a return is ``<household>/<YYYY>/<return>``
    and the order is the year's, then the folder name without case - which
    is the order the pass takes the locks in."""
    first = make_engagement(tmp_path, ITEMS, household="Smith Family", year=2025,
                            return_name="1120S - Park Landscaping", scaffold=False)
    second = make_engagement(tmp_path, ITEMS, household="Smith Family", year=2025,
                             return_name="1040 - John", scaffold=False)
    later = make_engagement(tmp_path, ITEMS, household="Smith Family", year=2026,
                            return_name="1040 - John", scaffold=False)
    # Folders in the wrong places are not returns.
    (household / "Archive").mkdir()
    ledger.path_for(household / "Archive").write_text("", encoding="utf-8")
    (household / "2025" / "1040 - John" / "Prepared").mkdir(parents=True, exist_ok=True)
    ledger.path_for(household / "2025" / "1040 - John" / "Prepared").write_text("", encoding="utf-8")

    assert household_returns(household) == [second, first, later]
    assert household_returns(private_household_dir(tmp_path, "Nobody")) == []


def test_open_years_are_the_active_returns_years(tmp_path):
    """The years a household still has work in: the distinct years of its
    active, unsuperseded returns, ascending. Two of them is what the pass
    refuses to sort from one inbox on."""
    from tracker.registry import discover_engagements

    make_engagement(tmp_path, ITEMS, household="Smith Family", year=2025,
                    return_name="1040 - John", scaffold=False)
    make_engagement(tmp_path, ITEMS, household="Smith Family", year=2025,
                    return_name="1120S - Park Landscaping", scaffold=False)
    prior = make_engagement(tmp_path, ITEMS, EngagementInfo(active=False),
                            household="Smith Family", year=2023,
                            return_name="1040 - Retired", scaffold=False)
    make_engagement(tmp_path, ITEMS, household="Smith Family", year=2026,
                    return_name="1040 - Next", scaffold=False)

    registry = discover_engagements(tmp_path)
    returns = registry.by_household()[private_household_dir(tmp_path, "Smith Family")]
    # 2023 is switched off in the editor, so it is not an open year.
    assert open_years(returns) == [2025, 2026]
    assert prior.parent.name == "2023"

    # And a year whose returns were all rolled forward is finished with.
    from dataclasses import replace

    from tracker.registry import mark_superseded

    rolled = [replace(one, superseded_by="somewhere") if one.tax_year == 2026 else one
              for one in returns]
    assert open_years(rolled) == [2025]
    assert open_years(mark_superseded(returns)) == [2025, 2026]


def test_sharing_confirmed_is_an_event_folded_by_nothing_and_read_back_by_day(household, tmp_path):
    """The firm's word that it shared this household (decision 126): one
    event carrying nothing but its stamp, which changes no field of the
    household and is read back by the day it fell on - the pattern an
    approved draft uses, and the reason this needed no schema change."""
    from tracker.households import shared_on

    assert shared_on(household) is None

    before = ledger.replay(ledger.read_events(household)).household
    with engagement_lock(household):
        store.record(store.connect(), household, ledger.new(ledger.SHARING_CONFIRMED))

    events = ledger.read_events(household)
    assert events[-1][ledger.EVENT_KEY] == ledger.SHARING_CONFIRMED
    assert set(events[-1]) == {ledger.EVENT_KEY, ledger.AT_KEY}
    # Folded by nothing: the household is exactly what it was.
    assert ledger.replay(events).household == before
    assert load_household_info(household) == SMITHS
    assert shared_on(household) == ledger.day_of(events[-1][ledger.AT_KEY])
    assert shared_on(household) == dt.date.today()
    assert store.check(store.connect(), tmp_path, household) == []

    # A line carrying anything at all is not this version's, and is
    # refused by name rather than kept where a reader would trust it.
    import json

    with ledger.path_for(household).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({ledger.EVENT_KEY: ledger.SHARING_CONFIRMED,
                                 ledger.AT_KEY: "2026-01-01T00:00:00",
                                 "members": ["John Smith"]}) + "\n")
    with pytest.raises(store.StoreError, match="it carries nothing"):
        store.rebuild_engagement(store.connect(), tmp_path, household)
    ledger.path_for(household).unlink()          # the fixtures must not meet it


def test_a_household_journal_with_a_sharing_event_still_folds_the_same_in_both_readers(
    household, tmp_path,
):
    """An edit before the word and an edit after it fold to one household
    in the ledger and in the store alike: the sharing event is a fact
    about a day, and it sits between two edits without disturbing either."""
    from dataclasses import replace

    save_household(household, replace(SMITHS, contact="John"))
    with engagement_lock(household):
        store.record(store.connect(), household, ledger.new(ledger.SHARING_CONFIRMED))
    save_household(household, replace(SMITHS, contact="John", link="https://drive.example/new"))

    events = ledger.read_events(household)
    assert [e[ledger.EVENT_KEY] for e in events] == [
        ledger.HOUSEHOLD_CHANGED, ledger.HOUSEHOLD_CHANGED,
        ledger.SHARING_CONFIRMED, ledger.HOUSEHOLD_CHANGED]
    folded = ledger.replay(events).household
    assert folded["contact"] == "John" and folded["link"] == "https://drive.example/new"

    conn = store.connect()
    store.rebuild_engagement(conn, tmp_path, household)
    assert store.check(conn, tmp_path, household) == []
    assert store.household_info(conn, household) == replace(
        SMITHS, contact="John", link="https://drive.example/new")


def test_a_return_and_its_household_are_two_rows_of_one_table(tmp_path, household):
    """Both are folders with a journal, keyed by path and folded by the same
    machinery; ``kind`` is what tells a reader which it is holding."""
    engagement = make_engagement(tmp_path, ITEMS, household="Smith Family", scaffold=False)
    conn = store.connect()
    assert store.kind(conn, engagement) == store.KIND_RETURN
    assert store.kind(conn, household) == store.KIND_HOUSEHOLD
    assert store.household_info(conn, engagement) is None      # a return is not a household
    assert store.kind(conn, return_dir_for(tmp_path, "Smith Family", 2030, "nobody")) is None


# ============ the feed list (decision 129) =================================
#
# A client with a co-owned business keeps one drop folder, and the business
# lives in a household shared to its co-owners: so a household's drop folder
# may feed named return lines in other households. What is recorded is the
# line, not the return, and the pass resolves it each time.


def _feeding(tmp_path, feeds):
    """Park Family's household record, feeding whatever this test says.

    A person extends the feed list in the editor, which is one
    ``household_changed`` event of exactly what moved - so this is a save,
    not a second create.
    """
    from dataclasses import replace

    folder = private_household_dir(tmp_path, "Park Family")
    held = load_household_info(folder)
    save_household(folder, replace(held, feeds=tuple(feeds)))
    return folder


def test_a_feed_is_a_return_line_and_resolves_to_the_open_years_return_or_is_said(tmp_path):
    """A feed names a household and a return line - the name a return keeps
    every year - and the pass resolves it to that household's open-year
    return of that name. So the rollover carries nothing about feeds, and a
    line that answers to no active return this year is said rather than
    quietly feeding nothing."""
    from tracker.households import FEED_UNRESOLVED, resolve_feeds
    from tracker.records import Feed
    from tracker.registry import discover_engagements

    make_engagement(tmp_path, ITEMS, household="Park Family",
                    return_name="1040 - John Park", year=2025, scaffold=False)
    llc = make_engagement(tmp_path, ITEMS, household="Park & Lee LLC",
                          return_name="1120S - Park & Lee LLC", year=2025, scaffold=False)
    household = _feeding(tmp_path, [
        Feed("Park & Lee LLC", "1120S - Park & Lee LLC"),
        Feed("Park & Lee LLC", "1065 - a line nobody has"),
    ])
    registry = discover_engagements(tmp_path)

    found, said = resolve_feeds(household, load_household_info(household).feeds, 2025, registry)

    assert [one.path for one in found] == [llc]
    assert said == [FEED_UNRESOLVED.format(household="Park & Lee LLC",
                                           return_name="1065 - a line nobody has", year=2025)]
    # The same list, a year the other household has not opened: the line is
    # the same line, and it is said rather than resolved to last year's.
    _found, later = resolve_feeds(household, load_household_info(household).feeds, 2026, registry)
    assert len(later) == 2 and all("2026" in one for one in later)


def test_a_household_cannot_feed_itself_and_a_duplicate_feed_is_refused(tmp_path):
    """Its own returns are fed already, so a household feeding itself names
    nothing; a line the list already holds is refused rather than folded
    away, so a person sees that the one they picked was already there. Both
    are the API's refusal, in the record's own words."""
    from tracker.api import _feeds_from_spec
    from tracker.households import resolve_feeds
    from tracker.records import FEED_REFUSED, Feed
    from tracker.registry import discover_engagements

    make_engagement(tmp_path, ITEMS, household="Park Family",
                    return_name="1040 - John Park", year=2025, scaffold=False)
    household = _feeding(tmp_path, [Feed("Park Family", "1040 - John Park")])
    registry = discover_engagements(tmp_path)

    # A feed naming this household resolves to nothing and is not warned
    # about: there is nothing to say about a return that is fed already.
    assert resolve_feeds(household, load_household_info(household).feeds, 2025, registry) == ([], [])

    for sent, refused in (
        ([{"household": "Park Family", "return_name": "1040 - John Park"}],
         FEED_REFUSED.format(household="Park Family", return_name="1040 - John Park")),
        ([{"household": "", "return_name": "1120S - x"}],
         FEED_REFUSED.format(household="(blank)", return_name="1120S - x")),
        ([{"household": "Park & Lee LLC", "return_name": "1120S - L"},
          {"household": "park & lee llc", "return_name": "1120S - L"}],
         FEED_REFUSED.format(household="park & lee llc", return_name="1120S - L")),
    ):
        with pytest.raises(ManifestError) as raised:
            _feeds_from_spec(sent, household)
        assert str(raised.value) == refused

    assert _feeds_from_spec([{"household": "Park & Lee LLC", "return_name": "1120S - L"}],
                            household) == (Feed("Park & Lee LLC", "1120S - L"),)


def test_a_feed_is_resolved_by_position_never_built_from_its_labels(tmp_path):
    """Decision 187 (C-14): a feed's two names are compared with the folders
    discovery found - household, year and return, by position - and never
    joined onto the root to make a path. A label spelled in another case
    names the same folder, as Windows would; a label that climbs or holds a
    separator names no folder and is said, never followed."""
    import tracker.households as households
    from tracker.households import FEED_UNRESOLVED, resolve_feeds
    from tracker.records import Feed
    from tracker.registry import discover_engagements

    make_engagement(tmp_path, ITEMS, household="Park Family",
                    return_name="1040 - John Park", year=2025, scaffold=False)
    llc = make_engagement(tmp_path, ITEMS, household="Park & Lee LLC",
                          return_name="1120S - Park & Lee LLC", year=2025, scaffold=False)
    household = private_household_dir(tmp_path, "Park Family")
    registry = discover_engagements(tmp_path)
    climbing = Feed("Park Family/../Park & Lee LLC", "1120S - Park & Lee LLC")
    nested = Feed("Park & Lee LLC", "../2025/1120S - Park & Lee LLC")

    found, said = resolve_feeds(household, [Feed("park & lee llc", "1120s - PARK & LEE LLC"),
                                            climbing, nested], 2025, registry)

    assert [one.path for one in found] == [llc]
    assert said == [FEED_UNRESOLVED.format(household=one.household, return_name=one.return_name,
                                           year=2025) for one in (climbing, nested)]
    assert not hasattr(households, "return_dir_for")
