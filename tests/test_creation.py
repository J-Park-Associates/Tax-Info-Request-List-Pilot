"""Tests for tracker/creation.py - the folder a new return takes, the
refusals it meets, and decision 137's undo of what a failed create or
rollover made.

Most of what the module promises is held by tests/test_api.py, whose tests
drive the create and rollover commands and so are about the command: a
name that is not one folder, a year out of bounds, a return or a household
name already taken, a list past the room, and every refusal and failure
leaving no folder and no store row behind. None of them moved here by the
SPEC's rule, because each runs a command. One test moved here from
tests/test_api.py (SPEC-architecture-p5 R5.6.4, P343): it calls
:func:`tracker.creation._undo_create` and nothing else. The others call
:func:`tracker.creation._undo_made` directly, on folders made the way
``create`` makes them (``fsio.make_new_folders``), for the claims its
docstring makes: only the folders the call reports it made are removed, a
folder it owns goes whole, and a level above one goes only when empty.
"""

from tests.builders import make_engagement
from tracker import creation, ledger, store
from tracker.fsio import make_new_folders
from tracker.households import create_household
from tracker.layout import private_household_dir, return_dir_for
from tracker.manifest import EngagementInfo, RequestItem, create_engagement
from tracker.records import HouseholdInfo

ITEMS = [RequestItem(identifier="A01", document="W-2")]
RETURN = "1040 - John & Maria Park"


def test_a_failed_create_that_cannot_forget_its_store_row_still_cleans_up_and_logs_it(
        tmp_path, monkeypatch, caplog):
    """E3 (P297): the cleanup finishes and raises nothing in place of the
    refusal; the row it could not drop is kept on the error log."""
    import logging

    from tracker import errors

    folder = tmp_path / "half-made"
    folder.mkdir()

    def locked(*_args, **_kwargs):
        raise store.StoreUnavailable("SQLITE_BUSY")

    monkeypatch.setattr(store, "forget", locked)
    with caplog.at_level(logging.WARNING, logger=errors.DEBUG_LOGGER):
        creation._undo_create(folder)
    assert not folder.exists()
    assert "api: forgetting a failed return (half-made)" in caplog.text
    assert "StoreUnavailable" in caplog.text


def test_undo_made_removes_only_the_folders_the_call_made_and_leaves_an_existing_household_alone(tmp_path):
    """Decision 137 (M1): a new return in a household that was already
    there makes only its year and itself, and a failure undoes those two -
    the return whole, with what the call recorded in it, and the year it
    had to make - while the household's folder, its record, a person's own
    file in it and last year's return are left as they were."""
    older = make_engagement(tmp_path, ITEMS, household="Park Family", year=2025,
                            return_name=RETURN, scaffold=False)
    household = private_household_dir(tmp_path, "Park Family")
    (household / "a person's note.txt").write_text("mine", encoding="utf-8")
    before = sorted(path.relative_to(household) for path in household.rglob("*"))

    engagement = return_dir_for(tmp_path, "Park Family", 2026, RETURN)
    made = make_new_folders(engagement)
    assert made == [engagement.parent, engagement]
    create_engagement(engagement, ITEMS, EngagementInfo(household="Park Family", tax_year=2026,
                                                        return_name=RETURN))
    assert store.rules(store.connect(), engagement) is not None

    creation._undo_made(made, {engagement})

    assert not engagement.parent.exists()
    assert sorted(path.relative_to(household) for path in household.rglob("*")) == before
    assert ledger.path_for(household).is_file() and ledger.path_for(older).is_file()
    assert store.rules(store.connect(), engagement) is None
    assert store.rules(store.connect(), older) is not None


def test_a_year_folder_the_call_made_stays_while_another_return_is_in_it(tmp_path):
    """The review's F4: a year folder the call had to make is not the call's
    to take once a second create running at the same moment has put its own
    return there - it is removed only when empty, and the other return stays."""
    make_engagement(tmp_path, ITEMS, household="Park Family", year=2025, return_name=RETURN,
                    scaffold=False)
    engagement = return_dir_for(tmp_path, "Park Family", 2026, RETURN)
    made = make_new_folders(engagement)
    theirs = return_dir_for(tmp_path, "Park Family", 2026, "1065 - Park LLC")
    theirs.mkdir()

    creation._undo_made(made, {engagement})

    assert not engagement.exists()
    assert theirs.is_dir() and engagement.parent.is_dir()


def test_a_household_the_call_made_and_recorded_goes_whole_and_no_other_does(tmp_path):
    """A household the call made and wrote the record of is the call's, so
    it goes whole with its record; the household beside it, which the call
    did not make, is untouched."""
    neighbour = make_engagement(tmp_path, ITEMS, household="Lee Family", year=2025,
                                return_name="1040 - Lee", scaffold=False)
    household = private_household_dir(tmp_path, "Park Family")
    made = make_new_folders(household)
    create_household(household, HouseholdInfo(name="Park Family"))
    engagement = return_dir_for(tmp_path, "Park Family", 2026, RETURN)
    made += make_new_folders(engagement)
    assert made == [household, engagement.parent, engagement]

    creation._undo_made(made, {engagement, household})

    assert not household.exists()
    assert ledger.path_for(neighbour).is_file()
    assert private_household_dir(tmp_path, "Lee Family").is_dir()
