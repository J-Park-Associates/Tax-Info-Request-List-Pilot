"""Tests for tracker/api.py: the household in the app, its inbox, its names and its routes.

The household (decision 125), its one inbox and rollover (decision 126), the name on the page (decision 128), the
routes of its feed list (decision 129), what it has received (decision 130), one name rule and one door (decision
188) and the linked households and the form (P141, P170, P172).

Split from ``tests/test_api.py`` by SPEC-architecture-p5 P5.14 (E-3), by the banners the old file kept its
sections under, each test moved byte for byte with its section, so that each family runs as its own process
(Jason, 2026-09-29) and an affected-tests run reaches only the family a change touched. The map owns this file
as ``tracker/api.py``'s test by its name (decision P350). What more than one family reads is
``tests/api_driver.py``'s, because a test file may not import another (``tests/test_suite_shape.py``).
"""

import datetime as dt
import json
import shutil
from pathlib import Path

import tracker.api as api
from tests import api_driver
from tests.api_driver import (
    PEOPLE,
    _a_deeper_root,
    _a_renamed_household,
    _aged,
    _cached_firm,
    _firm_whole,
    _rows_read,
    _tree_hashes,
    _typed_as_a_string,
    client_readme,
    run,
    sample_engagement,
    scan,
    two_households,
    waiting_document,
    where,
)
from tests.builders import TEST_CLIENT, make_engagement
from tests.node_harness import read
from tests.samples import PRIOR_YEAR, text_pdf
from tracker import creation, household_edit, layout, ledger, screen_words
from tracker.index import FILED, NEEDS_REVIEW, read_index
from tracker.layout import PRIVATE_TREE, inbox_of
from tracker.manifest import COL_DATE_PATTERN, load_engagement_info, load_manifest
from tracker.names import propose_spellings
from tracker.rollover import next_tax_year
from tracker.runner import LOG_FILENAME
from tracker.templates import BASE_YEAR, default_tax_year

#: A fixture of ``tests/api_driver.py``, named here so every claim below can ask for it.
demo_root = api_driver.demo_root


# ============ the household, in the app (decision 125) =====================


def test_the_app_lists_misfits_and_households_from_the_same_walk_the_pass_uses(capsys, demo_root):
    """What a person sees and what the scheduled job walks are one list:
    the households with their returns, and every folder left alone with the
    one sentence saying why."""
    from tracker.layout import CLIENTS_TREE, PRIVATE_TREE, client_household_dir, inbox_dir_for, private_household_dir
    from tracker.registry import MISFIT_NOT_A_TREE, MISFIT_NOT_A_YEAR

    assert run(capsys, "create", stdin={
        "household": "Park Family", "members": ["John Park", "Maria Park"],
        "contact": "John & Maria", "link": "https://drive.example/park",
        "return_name": "1040 - John & Maria Park", "form": "1040", "year": 2026,
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Park Family")),
        "return_name": "1120S - Park Landscaping", "year": 2026,
        "items": [{"identifier": "B01", "document": "Trial Balance"}]})[0] == 0
    (demo_root / "Archive").mkdir()
    (private_household_dir(demo_root, "Park Family") / "Old").mkdir()

    code, payload = run(capsys, "list")
    assert code == 0

    [household] = payload["households"]
    assert household["name"] == "Park Family"
    assert household["path"] == str(private_household_dir(demo_root, "Park Family"))
    assert household["client_folder"] == str(client_household_dir(demo_root, "Park Family"))
    assert household["inbox"] == str(inbox_dir_for(demo_root, "Park Family"))
    assert household["members"] == ["John Park", "Maria Park"]
    assert household["contact"] == "John & Maria" and household["link"] == "https://drive.example/park"
    assert household["open_years"] == [2026]
    assert [r["return_name"] for r in household["returns"]] == [
        "1040 - John & Maria Park", "1120S - Park Landscaping"]
    assert all(r["year"] == 2026 and r["active"] for r in household["returns"])

    # The picker's own list carries the label and the household it is in.
    assert [e["name"] for e in payload["engagements"]] == [
        "Park Family 2026 1040 - John & Maria Park",
        "Park Family 2026 1120S - Park Landscaping"]
    assert {e["household"] for e in payload["engagements"]} == {household["path"]}

    said = {Path(m["path"]).name: m["sentence"] for m in payload["misfits"]}
    assert said["Archive"] == MISFIT_NOT_A_TREE.format(
        clients=CLIENTS_TREE, private=PRIVATE_TREE)
    assert said["Old"] == MISFIT_NOT_A_YEAR


def test_the_screens_misfits_heading_is_the_practice_pages_own_word_typed_once():
    """C-6 (P346): the household screen's heading over the folders the app
    leaves alone is the one the practice page draws over the same folders.
    The API sends the status page's word rather than a copy of it, so the
    two cannot drift apart, and the screen's words hold no second typing."""
    from tracker import status_page

    assert api.vocab()["household"]["misfits_heading"] == status_page.STATUS_MISFITS_HEADING
    assert api.MISFITS_HEADING is status_page.STATUS_MISFITS_HEADING
    assert not hasattr(screen_words, "MISFITS_HEADING")


def test_create_makes_a_household_and_its_first_return_and_undoes_both_on_failure(
        capsys, demo_root):
    """The household is written first, so a return never exists under one
    the record does not know - and a create that fails leaves neither."""
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir
    from tracker.records import HouseholdInfo

    spec = {"household": "Park Family", "members": ["John Park", "Maria Park"],
            "contact": "John & Maria", "link": "https://drive.example/park",
            "return_name": "1040 - John & Maria Park", "form": "1040", "year": 2026,
            "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload

    household_dir = private_household_dir(demo_root, "Park Family")
    assert load_household_info(household_dir) == HouseholdInfo(
        name="Park Family", members=("John Park", "Maria Park"),
        contact="John & Maria", link="https://drive.example/park")
    # The return's greeting and link come from the household.
    assert payload["state"]["engagement"]["client"] == "John & Maria"
    assert payload["state"]["engagement"]["link"] == "https://drive.example/park"

    # And a create that fails leaves no folder, no record, and no household
    # it made itself.
    bad = {**spec, "household": "Vega Landscaping LLC", "return_name": "1120S - Vega",
           "items": [{"identifier": "A01", "document": "W-2"},
                     {"identifier": "A02", "document": "x", "date_pattern": "(unclosed"}]}
    code, payload = run(capsys, "create", stdin=bad)
    assert code == 1 and COL_DATE_PATTERN in payload["error"]
    assert not private_household_dir(demo_root, "Vega Landscaping LLC").exists()
    assert not where(demo_root, "1120S - Vega", year=2026,
                     household="Vega Landscaping LLC").exists()
    # The household this call did not make is untouched.
    assert load_household_info(household_dir).name == "Park Family"


def test_create_adds_a_return_to_an_existing_household_and_leaves_its_record_alone(
        capsys, demo_root):
    """A household's details are edited in ``edit-household`` and never
    written over by a return added to it."""
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "members": ["John Park"], "contact": "John",
        "link": "https://drive.example/park", "return_name": "1040 - John Park",
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    household_dir = private_household_dir(demo_root, "Park Family")

    code, payload = run(capsys, "create", stdin={
        "household_path": str(household_dir), "members": ["Somebody Else"],
        "contact": "Nobody", "link": "https://drive.example/wrong",
        "return_name": "1120S - Park Landscaping",
        "items": [{"identifier": "B01", "document": "Trial Balance"}]})
    assert code == 0, payload

    held = load_household_info(household_dir)
    assert held.members == ("John Park",) and held.contact == "John"
    assert held.link == "https://drive.example/park"
    assert len(ledger.read_events(household_dir)) == 1        # one event, still
    assert payload["state"]["household"]["returns"][1]["return_name"] == "1120S - Park Landscaping"

    # A household named again by name is refused since decision 188 (R7):
    # it is picked in the list, and the sentence says so and what to add.
    code, payload = run(capsys, "create", stdin={
        "household": "Park Family", "return_name": "1065 - Park & Lee LLC",
        "items": [{"identifier": "C01", "document": "K-1"}]})
    assert code == 1 and payload["error"] == screen_words.DUPLICATE_HOUSEHOLD.format(existing="Park Family")
    assert len(ledger.read_events(household_dir)) == 1


def test_create_refuses_a_return_whose_deepest_path_would_pass_the_limit_and_says_the_length(
        capsys, demo_root, path_setting):
    """A folder made today that cannot hold a filed document in February is
    a failure at a filing deadline, so it is refused now, with the length."""
    from tracker.layout import path_limit

    # Two names of the longest a name may be (decision 188) pass what
    # Windows will open under a root that grew.
    _a_deeper_root(demo_root)
    code, payload = run(capsys, "create", stdin={
        "household": "Park Family " + "h" * 68, "return_name": "1040 - " + "x" * 73, "form": "1040",
        "items": [{"identifier": "A01", "document": "y" * 90}]})

    assert code == 1
    assert f"past the {path_limit()} Windows allows" in payload["error"]
    assert "shorten the household or the return name" in payload["error"]
    assert "characters" in payload["error"]
    assert not any(demo_root.rglob(ledger.LEDGER_FILENAME))   # nothing was made


def test_create_refuses_a_household_or_return_name_that_is_not_a_folder_name(capsys, demo_root):
    """A household and a return are each one folder name: the layout puts
    them where they go, so a name carrying a separator is a typo."""
    for field, value in (("household", "../outside"), ("return_name", "sub/child")):
        spec = {"household": "Park Family", "return_name": "1040 - John",
                "items": [{"identifier": "A01", "document": "W-2"}], field: value}
        code, payload = run(capsys, "create", stdin=spec)
        what = "household" if field == "household" else "return"
        assert code == 1 and f"is not a {what} name" in payload["error"], field
    assert not any(demo_root.rglob(ledger.LEDGER_FILENAME))


def test_the_returns_details_carry_household_year_and_return_name_and_the_editor_cannot_change_them(
        capsys, demo_root):
    """The folders are the names, and the record is what wins when somebody
    renames one - so the three are written at creation and never edited."""
    from tracker.records import ENGAGEMENT_EDITABLE, ENGAGEMENT_FIELDS

    assert run(capsys, "create", stdin={
        "household": "Park Family", "return_name": "1040 - John Park", "year": 2026,
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    engagement = where(demo_root, "1040 - John Park", year=2026, household="Park Family")

    details = api.state(engagement)["engagement"]
    assert details["household"] == "Park Family"
    assert details["tax_year"] == 2026
    assert details["return_name"] == "1040 - John Park"

    rows = api.state(engagement)["rules"]
    for field in ("household", "tax_year", "return_name"):
        assert field in {name for _, name in ENGAGEMENT_FIELDS}
        assert field not in ENGAGEMENT_EDITABLE
        code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                            stdin={"items": rows, "engagement": {field: "something else"}})
        assert code == 1 and payload["error"] == f"'{field}' is not edited here"
    assert api.state(engagement)["engagement"]["household"] == "Park Family"


def test_edit_household_saves_members_contact_and_link_as_one_event(capsys, demo_root):
    """The household's three editable fields, saved as one recorded event
    carrying exactly what moved - and nothing else is edited here."""
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "contact": "John", "return_name": "1040 - John Park",
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    engagement = where(demo_root, "1040 - John Park", household="Park Family")
    household_dir = private_household_dir(demo_root, "Park Family")

    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"members": ["John Park", "Maria Park"],
                               "contact": "John & Maria",
                               "link": "https://drive.example/park"})
    assert code == 0, payload
    assert sorted(payload["saved"]["household"]) == ["contact", "link", "members"]
    held = load_household_info(household_dir)
    assert held.members == ("John Park", "Maria Park") and held.contact == "John & Maria"
    assert payload["state"]["household"]["members"] == ["John Park", "Maria Park"]
    assert len(ledger.read_events(household_dir)) == 2

    # Nothing changed, nothing written; and a blank clears.
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"members": ["John Park", "Maria Park"],
                               "contact": "John & Maria",
                               "link": "https://drive.example/park"})
    assert code == 0 and payload["saved"]["household"] == []
    assert len(ledger.read_events(household_dir)) == 2

    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"link": ""})
    assert code == 0 and payload["saved"]["household"] == ["link"]
    assert load_household_info(household_dir).link == ""

    # And a key that is not one of the three is refused by name.
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"name": "Somebody Else"})
    assert code == 1 and "Not a household field: name" in payload["error"]


def test_state_carries_the_household_its_open_years_its_returns_and_the_queue_count(
        capsys, demo_root, tmp_path):
    """The card is drawn from the state and types nothing of its own: the
    household's record, the years still open, its returns, and the one
    queue a person works across it."""
    from tests.samples import build_samples
    from tracker.layout import client_household_dir, private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "members": ["John Park"], "contact": "John",
        "link": "https://drive.example/park", "return_name": "1040 - John Park",
        "form": "1040", "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]})[0] == 0
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Park Family")),
        "return_name": "1120S - Park Landscaping",
        "items": [{"identifier": "B01", "document": "Trial Balance"}]})[0] == 0
    personal = where(demo_root, "1040 - John Park", household="Park Family")
    business = where(demo_root, "1120S - Park Landscaping", household="Park Family")

    samples = tmp_path / "samples"
    build_samples(samples)
    for name in ("vacation photo.bmp", "Mortgage Notes.docx"):
        (inbox_of(personal) / name).write_bytes((samples / name).read_bytes())
    assert scan(capsys, business)[0] == 0

    state = api.state(personal)
    household = state["household"]
    assert household["name"] == "Park Family"
    assert household["members"] == ["John Park"] and household["contact"] == "John"
    assert household["open_years"] == [default_tax_year()]
    assert [r["path"] for r in household["returns"]] == [str(personal), str(business)]
    # Each return's form and its people's names, for the card's roll fold
    # (decision 196); and no roll is offered while the open year is the
    # one being prepared.
    assert [r["form"] for r in household["returns"]] == ["1040", ""]
    assert [r["people"] for r in household["returns"]] == [[TEST_CLIENT], [TEST_CLIENT]]
    assert household["roll_year"] is None
    assert household["queue"] == sum(
        1 for one in (personal, business)
        for row in read_index(one) if row.decision == NEEDS_REVIEW)
    assert household["queue"] >= 1

    paths = state["paths"]
    assert paths["inbox"] == str(inbox_of(personal))
    assert paths["client_folder"] == str(client_household_dir(demo_root, "Park Family"))
    assert paths["household"] == str(private_household_dir(demo_root, "Park Family"))
    assert paths["originals"] == str(inbox_of(personal).parent / str(default_tax_year()))
    assert "shared" not in paths and "pbc" not in paths


def test_the_scan_command_runs_the_household_pass_and_answers_for_the_return_it_was_asked_about(
        capsys, demo_root, tmp_path):
    """One folder feeds every return of the household, so Run now on one
    return sorts all of it - which is the only honest thing it can do - and
    the reply is about the return that was asked for."""
    from tests.samples import build_samples
    from tracker.layout import private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "return_name": "1040 - John Park", "form": "1040",
        "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]})[0] == 0
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Park Family")),
        "return_name": "1120S - Park Landscaping",
        # A trial balance is a bookkeeping export with no name on it, which
        # is what every catalog's trial-balance row says (decision 128).
        "items": [{"identifier": "B01", "document": "Trial Balance", "min_size_kb": 0,
                   "named": "no", "required_keywords": "trial balance"}]})[0] == 0
    personal = where(demo_root, "1040 - John Park", household="Park Family")
    business = where(demo_root, "1120S - Park Landscaping", household="Park Family")

    samples = tmp_path / "samples"
    build_samples(samples)
    name = f"W-2 John Smith {BASE_YEAR}.pdf"
    (inbox_of(personal) / name).write_bytes((samples / name).read_bytes())
    text_pdf(inbox_of(personal) / "tb.pdf", f"Trial balance as of December 31 {BASE_YEAR}")

    code, payload = scan(capsys, business)
    assert code == 0, payload

    # The reply is the business return's, and the whole inbox was sorted.
    assert payload["state"]["paths"]["engagement"] == str(business)
    assert payload["run"]["filed"] == 1                       # the trial balance
    assert [row["original_name"] for row in payload["state"]["index"]] == ["tb.pdf"]
    assert [row.original_name for row in read_index(personal)] == [name]
    assert not any(p.suffix == ".pdf" for p in inbox_of(personal).iterdir())


# ---------------- one inbox, the household rollover, the sharing (d126) ----


def a_park_household(capsys, root):
    """Park Family with its three returns for the calendar's default year,
    made through ``create`` exactly as the wizard makes them."""
    from tracker.layout import private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "contact": "John & Maria",
        "link": "https://drive.example/park", "return_name": "1040 - John Park",
        "items": [{"identifier": "A01", "document": "W-2 Wage Statements",
                   "min_size_kb": 0, "any_keywords": "w-2"}]})[0] == 0
    here = str(private_household_dir(root, "Park Family"))
    for name, row in (("1040 - Sofia Park", "W-2 Wage Statements"),
                      ("1120S - Park Landscaping LLC", "Trial Balance")):
        assert run(capsys, "create", stdin={
            "household_path": here, "return_name": name,
            "items": [{"identifier": "A01", "document": row, "min_size_kb": 0,
                       "any_keywords": "w-2"}]})[0] == 0
    return [where(root, name, household="Park Family") for name in
            ("1040 - John Park", "1040 - Sofia Park", "1120S - Park Landscaping LLC")]


def test_roll_household_returns_the_rolled_and_the_retired_and_the_state_of_the_first_new_return(
    capsys, demo_root,
):
    """One call rolls the household's year: the returns it was given, the
    ones it retired - and the state of the first return it made, which is
    where the app lands. A refusal on any ticked return is the whole call's
    error, naming the return, and nothing is rolled or retired (decision
    159); ``skipped`` stays in the reply and is empty."""
    from tracker.manifest import load_engagement_info

    john, sofia, llc = a_park_household(capsys, demo_root)
    year = default_tax_year() + 1
    # The second plan's target is already there, so the whole roll refuses.
    blocking = where(demo_root, "1040 - Sofia Park", year=year, household="Park Family")
    blocking.mkdir(parents=True)
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(llc), stdin={
        "year": year,
        "returns": [{"prior": str(john)}, {"prior": str(sofia)}],
    })
    assert code == 1, payload
    assert payload["error"].startswith("1040 - Sofia Park: ") and "already exists" in payload["error"]
    assert payload["error"].endswith("Nothing was rolled.")
    assert not where(demo_root, "1040 - John Park", year=year, household="Park Family").exists()
    assert load_engagement_info(llc).active is True
    blocking.rmdir()

    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(llc), stdin={
        "year": year,
        "returns": [{"prior": str(john)}, {"prior": str(sofia)}],
    })
    assert code == 0, payload

    assert [one["prior"] for one in payload["rolled"]] == ["1040 - John Park", "1040 - Sofia Park"]
    assert payload["rolled"][0]["label"] == f"Park Family {year} 1040 - John Park"
    assert payload["rolled"][0]["created"] == str(
        where(demo_root, "1040 - John Park", year=year, household="Park Family"))
    assert payload["rolled"][0]["carried"][0]["identifier"] == "A01"
    assert payload["skipped"] == [] and payload["not_retired"] == [] and payload["warning"] == ""
    # The one return nobody ticked is retired, by its label.
    assert payload["retired"] == [f"Park Family {default_tax_year()} 1120S - Park Landscaping LLC"]
    assert load_engagement_info(llc).active is False
    # The state is the first return this call made.
    assert payload["state"]["paths"]["engagement"] == payload["rolled"][0]["created"]
    assert payload["target_year"] == year


def test_roll_household_after_a_failed_retirement_says_what_was_rolled_and_left_open(
    capsys, demo_root, monkeypatch,
):
    """Decision 159, the review's S2. Every ticked return rolled and then a
    retirement failed: the new returns exist, so the reply is not an error.
    It names the return left open and carries the rollover's own sentence,
    which the app shows as its banner, and lands on the first new return."""
    from tracker import rollover
    from tracker.manifest import load_engagement_info

    john, sofia, llc = a_park_household(capsys, demo_root)
    year = default_tax_year() + 1
    real_save = rollover.save_rules

    def llc_fails(folder, *args, **kwargs):
        if folder == llc:
            raise OSError("the disk filled")
        return real_save(folder, *args, **kwargs)

    monkeypatch.setattr(rollover, "save_rules", llc_fails)
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(llc), stdin={
        "year": year,
        "returns": [{"prior": str(john)}, {"prior": str(sofia)}],
    })
    assert code == 0, payload
    assert [one["prior"] for one in payload["rolled"]] == ["1040 - John Park", "1040 - Sofia Park"]
    assert payload["retired"] == []
    assert payload["not_retired"] == [f"Park Family {default_tax_year()} 1120S - Park Landscaping LLC"]
    assert payload["warning"].startswith(f"Rolled into {year}: 1040 - John Park, 1040 - Sofia Park.")
    assert "Not retired: 1120S - Park Landscaping LLC (OSError)" in payload["warning"]
    assert load_engagement_info(llc).active is True
    assert payload["state"]["paths"]["engagement"] == payload["rolled"][0]["created"]


# ------------------ decision 196: the roll is the household on screen ----


def _calendar_a_year_on(monkeypatch):
    """The calendar a year later: the year every return here was made for
    has ended, and so has the one it would roll to."""
    later = default_tax_year() + 1
    monkeypatch.setattr(api, "default_tax_year", lambda today=None: later)


def test_the_household_card_names_the_year_it_rolls_to_and_each_returns_form_and_people(
        capsys, demo_root, monkeypatch):
    """Once the year a roll opens has ended, the card's state names it -
    the next year after the household's one open year - and every return
    carries the form and the people's names the roll fold shows, read from
    the records the card is already drawn from."""
    john, sofia, llc = a_park_household(capsys, demo_root)
    _calendar_a_year_on(monkeypatch)
    household = api.state(john)["household"]
    assert household["open_years"] == [default_tax_year()]
    assert household["roll_year"] == next_tax_year(default_tax_year())
    assert [r["path"] for r in household["returns"]] == [str(john), str(sofia), str(llc)]
    # None of the three was made with a form, and the card says so rather
    # than guessing one; every one of them is carried by the roll.
    assert [one["form"] for one in household["returns"]] == ["", "", ""]
    for one in household["returns"]:
        assert one["people"] == [TEST_CLIENT] and one["rollable"] is True, one


def test_each_return_says_whether_the_offered_roll_carries_it(capsys, demo_root, monkeypatch):
    """Which returns a roll carries is the API's word, per return, so the
    page filters nothing a second time: a return rolled on and a return
    retired are never carried, the open year's are, and while no roll is
    offered no return is."""
    john, sofia, llc = a_park_household(capsys, demo_root)
    year = next_tax_year(default_tax_year())
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(john), stdin={
        "year": year, "returns": [{"prior": str(john)}]})
    assert code == 0, payload
    rolled = Path(payload["rolled"][0]["created"])
    # Mid-season for the year just rolled into: nothing is carried.
    _calendar_a_year_on(monkeypatch)
    household = api.state(rolled)["household"]
    assert household["roll_year"] is None
    assert not any(one["rollable"] for one in household["returns"])
    # Once that year has ended, the new return alone is carried: John's
    # prior was rolled on, Sofia's and the LLC's were retired.
    monkeypatch.setattr(api, "default_tax_year", lambda today=None: year + 1)
    household = api.state(rolled)["household"]
    assert household["roll_year"] == next_tax_year(year)
    assert {one["path"]: one["rollable"] for one in household["returns"]} == {
        str(john): False, str(sofia): False, str(llc): False, str(rolled): True}


def test_no_roll_is_offered_mid_season_on_a_paused_household_or_with_two_open_years(
        capsys, demo_root, monkeypatch):
    """The API says when a roll is offered, and never while the year being
    prepared is still the open one, while the household is paused (decision
    188), or while two years are open - each of which the command refuses
    or would retire the returns being worked on."""
    from tracker.layout import private_household_dir

    # Mid-season: the open year is the calendar's default, whose next year
    # has not ended.
    items = [{"identifier": "A01", "document": "W-2"}]
    assert run(capsys, "create", stdin={"household": "Lee Family", "return_name": "1040 - Ann Lee",
                                        "items": items})[0] == 0
    ann = where(demo_root, "1040 - Ann Lee", household="Lee Family")
    assert api.state(ann)["household"]["roll_year"] is None

    # Two open years: a return for the year before sits beside it.
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Lee Family")),
        "return_name": "1040 - Ben Lee", "year": default_tax_year() - 1, "items": items})[0] == 0
    with monkeypatch.context() as later:
        _calendar_a_year_on(later)
        household = api.state(ann)["household"]
        assert len(household["open_years"]) == 2 and household["roll_year"] is None

    # Paused: the folder renamed under its record (the 188 fixture), with
    # the calendar where a roll would otherwise be offered.
    renamed = _a_renamed_household(capsys, demo_root)
    _calendar_a_year_on(monkeypatch)
    household = api.state(renamed)["household"]
    assert household["pause"]["sentence"] and household["roll_year"] is None


def test_rolling_one_households_return_never_touches_another_household(capsys, demo_root):
    """D1 held at the API end: rolling a return of one household rolls that
    household, and another household's private and client trees - every
    name and every byte, its journal with them - are as they were."""
    from tracker.layout import CLIENTS_TREE, private_household_dir

    john, sofia, llc = a_park_household(capsys, demo_root)
    assert run(capsys, "create", stdin={
        "household": "Lee Family", "return_name": "1040 - Ann Lee",
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    lee_private = private_household_dir(demo_root, "Lee Family")
    lee_client = demo_root / CLIENTS_TREE / "Lee Family"

    def snapshot():
        return {str(path.relative_to(demo_root)): path.read_bytes() if path.is_file() else None
                for tree in (lee_private, lee_client) for path in sorted(tree.rglob("*"))}

    before, journal = snapshot(), ledger.read_events(lee_private)
    year = default_tax_year() + 1
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(john), stdin={
        "year": year, "returns": [{"prior": str(john)}, {"prior": str(sofia)}, {"prior": str(llc)}]})
    assert code == 0, payload
    assert sorted(one["prior"] for one in payload["rolled"]) == [
        "1040 - John Park", "1040 - Sofia Park", "1120S - Park Landscaping LLC"]
    assert snapshot() == before
    assert ledger.read_events(lee_private) == journal


def test_creating_a_households_first_return_hands_back_the_sharing_checklist_and_a_later_return_does_not(
    capsys, demo_root,
):
    """The two grants are made once, when the household is made (decision
    126). A second return added to it gets no checklist: its inbox was
    shared when the household was, and nothing is ever re-shared."""
    from tracker.layout import client_household_dir, inbox_dir_for, private_household_dir

    code, first = run(capsys, "create", stdin={
        "household": "Park Family", "return_name": "1040 - John Park",
        "items": [{"identifier": "A01", "document": "W-2", "min_size_kb": 0,
                   "any_keywords": "w-2"}]})
    assert code == 0, first
    checklist = first["checklist"]
    assert checklist["heading"] == api.SHARING_HEADING
    assert checklist["note"] == api.SHARING_NOTE
    assert str(client_household_dir(demo_root, "Park Family")) in checklist["lines"][0]
    assert "Viewer" in checklist["lines"][0]
    assert str(inbox_dir_for(demo_root, "Park Family")) in checklist["lines"][1]
    assert "Contributor" in checklist["lines"][1]
    assert api.MARK_SHARED_LABEL in checklist["lines"][2]

    code, second = run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Park Family")),
        "return_name": "1040 - Sofia Park",
        "items": [{"identifier": "A01", "document": "W-2", "min_size_kb": 0,
                   "any_keywords": "w-2"}]})
    assert code == 0, second
    assert "checklist" not in second


def test_mark_shared_refuses_without_a_link_records_one_event_and_the_state_says_the_day(
    capsys, demo_root,
):
    """The firm's word, dated, and nothing else: one event carrying only
    its stamp, folded by nothing. The link is the one part of the
    checklist the tracker can see was done, so it insists on that one."""
    from tracker.households import shared_on
    from tracker.layout import private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "return_name": "1040 - John Park",
        "items": [{"identifier": "A01", "document": "W-2", "min_size_kb": 0,
                   "any_keywords": "w-2"}]})[0] == 0
    john = where(demo_root, "1040 - John Park", household="Park Family")
    household = private_household_dir(demo_root, "Park Family")

    code, payload = run(capsys, "mark-shared", api.ENGAGEMENT_FLAG, str(john))
    assert code == 1 and payload["error"] == api.SHARE_LINK_FIRST
    assert shared_on(household) is None

    assert run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(john),
               stdin={"link": "https://drive.example/park"})[0] == 0
    before = len(ledger.read_events(household))
    code, payload = run(capsys, "mark-shared", api.ENGAGEMENT_FLAG, str(john))
    assert code == 0, payload

    today = dt.date.today().isoformat()
    assert payload["shared_on"] == today
    assert payload["state"]["household"]["shared_on"] == today
    # The checklist stops being offered once the word is given.
    assert payload["state"]["household"]["checklist"] is None
    events = ledger.read_events(household)
    assert len(events) == before + 1
    assert events[-1][ledger.EVENT_KEY] == ledger.SHARING_CONFIRMED
    assert set(events[-1]) == {ledger.EVENT_KEY, ledger.AT_KEY} | ledger.LINE_KEYS
    # Folded by nothing: the household reads back exactly as it did.
    assert ledger.replay(events).household == ledger.replay(events[:-1]).household


def test_the_sharing_words_are_the_apis_and_the_renderer_types_none(capsys, demo_root):
    """Every word of the checklist, the two lines about the firm's word and
    the sentence about a return left unticked is Python's; the page shows
    what it is handed and types none of it (decision 126)."""
    words = api.vocab()["household"]
    assert words["sharing_heading"] == api.SHARING_HEADING
    assert words["sharing_note"] == api.SHARING_NOTE
    assert words["mark_shared"] == api.MARK_SHARED_LABEL
    assert words["shared_on_line"] == api.SHARED_ON_LINE
    assert words["not_yet_shared_line"] == api.NOT_YET_SHARED_LINE
    assert words["rollover_unticked"] == api.ROLLOVER_UNTICKED_NOTE

    js = read("app.js")
    html = read("index.html")
    for literal in (*api.SHARING_CHECKLIST, api.SHARING_HEADING, api.SHARING_NOTE,
                    api.MARK_SHARED_LABEL, api.SHARED_ON_LINE, api.NOT_YET_SHARED_LINE,
                    api.SHARE_LINK_FIRST, api.ROLLOVER_UNTICKED_NOTE):
        assert literal not in js, literal
        assert literal not in html, literal


# ------------------------------------------- the name on the page (d128) ----


def test_teaching_a_spelling_from_a_filing_rides_the_filings_transaction_and_a_one_word_spelling_is_refused(
        capsys, demo_root, tmp_path):
    """Decision 128. A filing that teaches a spelling is one decision: the
    row, the move and the return's people are recorded in one transaction,
    exactly as a taught keyword is. A spelling of one word is refused
    before a byte is read - a family name alone would confirm a business -
    and so is a person the return does not list."""
    from tracker.records import ONE_WORD_SPELLING

    engagement = sample_engagement(capsys, demo_root, tmp_path,
                                   f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf")
    assert scan(capsys, engagement)[0] == 0
    state = api.state(engagement)
    [parked] = [e for e in state["index"] if e["decision"] == NEEDS_REVIEW]
    spec = {"original": parked["pbc_location"], "identifier": "A01", "seq": parked["seq"]}

    # One word: refused, and nothing is recorded.
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={**spec, "spelling": {"person": "Jane R. Smith",
                                                    "spelling": "Smith"}})
    assert code == 1 and payload["error"] == ONE_WORD_SPELLING
    # A person the return does not list: refused by name.
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={**spec, "spelling": {"person": "Nobody Here",
                                                    "spelling": "Nobody Here"}})
    assert code == 1 and "Nobody Here is not on this return" in payload["error"]
    assert [e["decision"] for e in api.state(engagement)["index"]] == [NEEDS_REVIEW]

    # And the real thing: one event, in the filing's own transaction.
    before = len(ledger.read_events(engagement))
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={**spec, "spelling": {"person": "Jane R. Smith",
                                                    "spelling": "J. R. Smith"}})
    assert code == 0, payload
    assert payload["assigned"]["spelling"] == "J. R. Smith"
    assert payload["assigned"]["said"]["spelling_added"] == (
        '"J. R. Smith" added so the next page that prints it confirms itself')
    assert payload["assigned"]["said"]["keyword_added"] == "", "no keyword was taught"
    people = load_engagement_info(engagement).people
    assert "J. R. Smith" in next(p for p in people if p.name == "Jane R. Smith").spellings
    # The filing and the teaching are one decision, so one of the new lines
    # is the row and one is the rules edit - and nothing else.
    added = ledger.read_events(engagement)[before:]
    # The intent, the row and the rules edit - one decision. (The re-scan
    # that follows the filing writes its own `scanned` line, as it always
    # has; the teaching is inside the filing's transaction, not beside it.)
    assert [e[ledger.EVENT_KEY] for e in added if e[ledger.EVENT_KEY] != ledger.SCANNED] == [
        ledger.MOVING, ledger.ASSIGNED_BY_PERSON, ledger.RULES_CHANGED]
    assert next(e for e in added if e[ledger.EVENT_KEY] == ledger.RULES_CHANGED
                )[ledger.INFO_KEY].keys() == {"people"}

    # Teaching the same spelling again is a note, not a second event.
    state = api.state(engagement)
    [again] = [e for e in state["index"] if e["decision"] == NEEDS_REVIEW] or [None]
    assert again is None


def test_create_refuses_a_return_with_no_people_and_the_editor_saves_people_as_one_event(
        capsys, demo_root):
    """A return with nobody on it can never file a named request, so it is
    refused at setup rather than left to park every W-2 that arrives; and
    the people are edited in the one editor, saved in the one event that
    carries every other detail."""
    from tracker.names import NO_PEOPLE
    from tracker.records import ONE_WORD_SPELLING

    spec = {"return_name": "No People", "form": "1040", "people": [],
            "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1 and payload["error"] == NO_PEOPLE

    code, payload = run(capsys, "create", stdin={
        **spec, "people": [{"kind": "taxpayer", "name": "John Park", "spellings": ["Park"]}]})
    assert code == 1 and payload["error"] == ONE_WORD_SPELLING

    assert run(capsys, "create", stdin={**spec, "people": PEOPLE})[0] == 0
    engagement = where(demo_root, "No People")
    before = len(ledger.read_events(engagement))

    state = api.state(engagement)
    assert state["engagement"]["people"] == list(PEOPLE)
    edited = [*PEOPLE, {"kind": "spouse", "name": "Maria Park",
                        "spellings": ["Maria Park", "Park, Maria"]}]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": state["rules"], "engagement": {"people": edited}})
    assert code == 0, payload
    assert payload["saved"]["engagement"] == ["people"]
    assert len(ledger.read_events(engagement)) == before + 1       # one event
    assert [p.name for p in load_engagement_info(engagement).people] == [
        TEST_CLIENT, "Maria Park"]


def test_propose_spellings_is_a_read_and_the_renderer_types_no_kind_label_or_note(
        capsys, demo_root):
    """The twenty-third command proposes and records nothing: what a return
    matches on is what somebody ticked. And every word the People block and
    the card show is the API's - the page types none of them."""
    from tracker import review
    from tracker.records import PERSON_KIND_LABELS, PERSON_KINDS

    code, payload = run(capsys, "propose-spellings",
                        stdin={"name": "John A. Park", "kind": "taxpayer"})
    assert code == 0
    assert payload == {"spellings": list(propose_spellings("John A. Park", "taxpayer")),
                       "warnings": []}
    assert not list(demo_root.rglob("*_ledger.jsonl"))         # a read: nothing recorded
    assert run(capsys, "propose-spellings", stdin={"name": "x", "kind": "nope"})[0] == 1

    words = run(capsys, "list")[1]["vocab"]["people"]
    assert [k["value"] for k in words["kinds"]] == list(PERSON_KINDS)
    assert [k["label"] for k in words["kinds"]] == [PERSON_KIND_LABELS[k] for k in PERSON_KINDS]

    js = read("app.js")
    html = read("index.html")
    # Every phrase of the block and the card, from its owner. The one-word
    # labels are not pinned here - "Who" and "Name" are English as much as
    # they are labels, and a guard that fails on a comment teaches nobody;
    # the kinds above prove the page reads the list rather than holding one.
    for literal in ("Entity (legal name)", "DBA or abbreviation",
                    "Owner (accounts held so)", "Trust or estate",
                    api.SPELLINGS_LABEL, api.SPELLINGS_HELP, api.ADD_PERSON_LABEL,
                    api.OWN_SPELLING_HINT, api.REVIEW_PEOPLE_LABEL,
                    api.PEOPLE_ROLLED_NOTE, api.TEACH_SPELLING_LABEL,
                    api.TEACH_SPELLING_HINT, words["one_word"], words["none_yet"],
                    review.NAME_CONFIRMED_NOTE, review.NAME_OTHER_NOTE,
                    review.NAME_ABSENT_NOTE):
        assert not _typed_as_a_string(js, literal), literal
        assert not _typed_as_a_string(html, literal), literal


def test_the_household_card_shows_every_returns_reminder_state(capsys, demo_root):
    """One letter per return, as before - and the household card puts their
    states side by side, in the words the Reminder card already uses, so a
    person can see the household's letters at a glance without a bundle."""
    from tracker import reminder
    from tracker.layout import private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "contact": "John", "return_name": "1040 - John Park",
        "form": "1040", "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]})[0] == 0
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Park Family")),
        "return_name": "1120S - Park Landscaping", "form": "1120S",
        "items": [{"identifier": "B01", "document": "Trial Balance", "named": "no"}]})[0] == 0
    personal = where(demo_root, "1040 - John Park", household="Park Family")

    returns = api.state(personal)["household"]["returns"]

    assert [one["return_name"] for one in returns] == [
        "1040 - John Park", "1120S - Park Landscaping"]
    for one in returns:
        assert one["reminder"] == {"last": None, "approved": None, "lapsed": False,
                                   "held": 0, "unsorted": 0}
    # The words the card fills those numbers into are the reminder's own.
    words = run(capsys, "list")[1]["vocab"]["reminder"]
    assert words["never_drafted_line"] == reminder.NEVER_DRAFTED_LINE
    assert words["held_line"] == reminder.HELD_SUMMARY


# ============ the household routes: the feed list (decision 129) ===========


def test_edit_household_saves_feeds_and_the_state_carries_feeds_and_fed_by_with_the_two_warnings_words(
        capsys, demo_root):
    """The feed list is a household field like the members: saved as one
    recorded event of exactly what moved, resolved for the card into the
    return it names this year, and shown from the other side on the
    household whose return is fed. Both warnings a person reads before
    extending either are the API's words."""
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir
    from tracker.records import Feed

    father, llc = two_households(capsys, demo_root)
    household_dir = private_household_dir(demo_root, "Park Family")
    assert load_household_info(household_dir).feeds == (
        Feed("Park & Lee LLC", "1120S - Park & Lee LLC"),)

    _code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(father))
    [feed] = payload["household"]["feeds"]
    assert feed["household"] == "Park & Lee LLC"
    assert feed["return_name"] == "1120S - Park & Lee LLC"
    assert feed["path"] == str(llc) and feed["warning"] == ""
    assert "1120S - Park & Lee LLC" in feed["label"]

    # And from the other side: the household whose return is fed is told
    # whose drop folder feeds it, by household and never by member.
    _code, other = run(capsys, "state", api.ENGAGEMENT_FLAG, str(llc))
    assert [one["name"] for one in other["household"]["fed_by"]] == ["Park Family"]
    assert other["household"]["feeds"] == []

    words = api.vocab()["household"]
    assert words["feed_warning"] == api.FEED_WARNING
    assert words["return_warning"] == api.RETURN_WARNING
    assert words["feed_warning"] == "Its Members Can Drop Here"   # P84: no placeholder left

    # A feed the other household has no active return for this year is
    # said rather than resolved to nothing in silence.
    assert run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(father),
               stdin={"feeds": [{"household": "Park & Lee LLC",
                                 "return_name": "1065 - nobody"}]})[0] == 0
    _code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(father))
    [gone] = payload["household"]["feeds"]
    assert gone["path"] == "" and "no active return" in gone["warning"]


def test_assign_with_a_target_refuses_an_unfed_return_and_hands_over_to_a_fed_one(
        capsys, demo_root, tmp_path):
    """Nothing routes outside the feed list: a target this drop folder does
    not feed is refused by name, and a target it does feed takes the
    document - the original moving under the household that return lives
    in, and the row here released (decision 132): nothing of it stays."""
    from tracker.layout import originals_of
    father, llc = two_households(capsys, demo_root)
    parked, seq = a_parked_document(capsys, father)

    # A return nobody extended this drop folder to: refused before a byte
    # is read, and the outsider's record is untouched.
    outsider = where(demo_root, "1040 - Sofia Park", household="Sofia Park")
    assert run(capsys, "create", stdin={
        "household": "Sofia Park", "contact": "Sofia", "return_name": "1040 - Sofia Park",
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"original": parked, "identifier": "A01", "seq": seq,
                               "target": str(outsider)})
    assert code == 1 and payload["error"] == api.NOT_FED.format(label=outsider.name)
    assert read_index(outsider) == []

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"original": parked, "identifier": "B01", "seq": seq,
                               "target": str(llc)})
    assert code == 0, payload
    assert payload["handed_over"]["moved_original"] is True
    assert payload["handed_over"]["identifier"] == "B01"
    assert read_index(father) == []
    [taken] = read_index(llc)
    assert taken.decision == FILED and taken.identifier == "B01"
    assert (originals_of(llc) / "notice.pdf").is_file()


def test_run_now_sorts_against_the_feed_list_like_the_scheduled_pass(capsys, demo_root):
    """There is one definition of a pass, and *Run now* is it.

    The button walks the practice and hands it down exactly as the
    scheduled job does, so the same trial balance dropped in the father's
    inbox is judged against the co-owned LLC's list either way - and, since
    decision 204, waits in the father's queue for one click either way,
    rather than parking as a document nothing wants. Without the walk the
    feed list resolves to nothing, which would make the button and the
    schedule disagree about what the household's inbox is for.
    """
    from tracker import reasons

    father, llc = two_households(capsys, demo_root)
    text_pdf(inbox_of(father) / "tb.pdf",
             ["Trial balance as of December 31 2025", TEST_CLIENT], style="padded")

    code, payload = scan(capsys, father)

    assert code == 0, payload
    assert read_index(llc) == []                    # the pass files nothing across
    [row] = read_index(father)
    assert row.decision == NEEDS_REVIEW and row.code == reasons.NAMED_ACROSS_HOUSEHOLDS.code
    assert row.waiting_for.identifiers == ("B01",)
    assert payload["run"]["filed"] == 0


def test_a_waiting_row_offers_one_click_and_assign_waiting_files_it_with_no_target_from_the_page(
        capsys, demo_root):
    """Decision 204's one click. The card carries what the click will do -
    the return, its label and the requests it files under, as data - and
    the page sends back only the row and its version: ``waiting``, no
    target, no identifier. The API resolves the row's own claim through the
    feed list and hands it over; a second click on the gone row is refused."""
    father, llc = two_households(capsys, demo_root)
    waiting = waiting_document(capsys, father)
    offer = waiting["waits_for"]
    assert offer == {"target": str(llc), "label": "Park & Lee LLC 2025 1120S - Park & Lee LLC",
                     "requests": [{"identifier": "B01", "document": "Trial Balance"}], "answers": []}
    assert waiting["waits_for_refused"] == ""

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"original": waiting["pbc_location"], "seq": waiting["seq"],
                               "waiting": True})

    assert code == 0, payload
    done = payload["handed_over"]
    assert done["identifier"] == "B01" and done["label"] == offer["label"]
    assert done["moved_original"] is True
    assert read_index(father) == [] and payload["state"]["review"] == []
    [taken] = read_index(llc)
    assert taken.decision == FILED and taken.identifier == "B01" and taken.waits_for == ""
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"original": waiting["pbc_location"], "seq": waiting["seq"],
                               "waiting": True})
    assert code == 1


def test_a_waiting_row_keeps_its_one_click_in_the_document_bucket_with_open_and_the_handle_it_is_drawn_by(
        capsys, demo_root):
    """Decision 190's three buckets over decision 204's one click: the row
    that waits for another household's return is a document the tracker
    read - the document bucket, with **Open** on its marked copy (its code
    is on the allow-list) - and its triage entry, keyed by the handle the
    card now draws a row by, still carries the click. Sent back with that
    handle, the click files it exactly as 204 built it."""
    from tracker import reasons

    father, llc = two_households(capsys, demo_root)
    waiting = waiting_document(capsys, father)
    code, state = run(capsys, "state", api.ENGAGEMENT_FLAG, str(father))
    assert code == 0, state
    [row] = [e for e in state["index"] if e["decision"] == NEEDS_REVIEW]

    assert row["code"] == reasons.NAMED_ACROSS_HOUSEHOLDS.code in reasons.READ_AND_PARKED_CODES
    assert row["bucket"] == waiting["bucket"] == api.BUCKET_DOCUMENT
    assert row["open_key"] and Path(state["paths"][row["open_key"]]).is_file()
    assert waiting["handle"] == row["handle"]
    assert waiting["waits_for"]["target"] == str(llc) and waiting["waits_for_refused"] == ""

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"original": waiting["handle"], "seq": waiting["seq"], "waiting": True})
    assert code == 0, payload
    assert payload["handed_over"]["identifier"] == "B01"
    [taken] = read_index(llc)
    assert taken.decision == FILED and taken.identifier == "B01"


def test_a_waiting_row_whose_feed_was_trimmed_offers_no_click_and_says_not_fed(capsys, demo_root):
    """R-8: a claim that no longer resolves offers nothing. The card says why
    in the words a hand-over is refused with, the click sent anyway is
    refused in them, and the row stays parked for the picker or for filing
    here."""
    father, llc = two_households(capsys, demo_root)
    waiting = waiting_document(capsys, father)
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"feeds": []})
    assert code == 0, payload

    _code, state = run(capsys, "state", api.ENGAGEMENT_FLAG, str(father))
    [card] = state["review"]
    said = api.NOT_FED.format(label="1120S - Park & Lee LLC")
    assert card["waits_for"] is None and card["waits_for_refused"] == said

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"original": waiting["pbc_location"], "seq": card["seq"],
                               "waiting": True})
    assert code == 1 and payload["error"] == said
    assert [row.decision for row in read_index(father)] == [NEEDS_REVIEW]
    assert read_index(llc) == []


def test_a_claim_is_offered_only_on_the_row_the_click_would_take(capsys, demo_root):
    """The review's S-3: the card offers the click on exactly the rows the
    filer's refusal lets through - still parked, with the named-across
    reason. The same claim on a row a person set aside, or under any other
    cause, draws no button and no sentence. The cause is the row's code
    (decision 190): its sentence reworded changes nothing."""
    from dataclasses import replace

    from tracker import reasons

    father, llc = two_households(capsys, demo_root)
    waiting = waiting_document(capsys, father)
    [row] = read_index(father)
    fed = lambda: {llc: "Park & Lee LLC 2025 1120S - Park & Lee LLC"}  # noqa: E731
    offer, _said = api._waiting_payload(father, row, fed)
    assert offer == waiting["waits_for"]
    for other in (replace(row, decision="Not Requested"),
                  replace(row, code=reasons.UNNAMED_ACROSS_HOUSEHOLDS.code)):
        assert api._waiting_payload(father, other, fed) == (None, "")
    assert api._waiting_payload(father, replace(row, reason="a reason of its own"), fed)[0] == offer


def test_a_waiting_row_whose_return_has_no_room_offers_no_click_and_says_so_in_that_returns_words(
        capsys, demo_root, monkeypatch):
    """The review's S-1: a click bound to fail on the taking return's room is
    not offered. The card says why in the sentence the click would be
    refused with, naming that return - never "this request's Short name"."""
    import tracker.copies as copies_module

    father, llc = two_households(capsys, demo_root)
    waiting_document(capsys, father)
    monkeypatch.setattr(copies_module, "limit_for", lambda _extension: 10)

    _code, state = run(capsys, "state", api.ENGAGEMENT_FLAG, str(father))

    [card] = state["review"]
    assert card["waits_for"] is None
    said = card["waits_for_refused"]
    assert said.startswith("the working copy's path in Park & Lee LLC 2025 1120S - Park & Lee LLC")
    assert "this request" not in said


def a_parked_document(capsys, engagement):
    """One document nothing asks for, dropped in the household's inbox and
    left waiting for a person by a pass - the row a hand-over acts on, with
    the record version the card would have carried out (decision 112)."""

    text_pdf(inbox_of(engagement) / "notice.pdf", ["an agency notice nothing asks for"], style="padded")
    _code, payload = scan(capsys, engagement)
    [row] = [e for e in payload["state"]["index"]
             if e["decision"] == NEEDS_REVIEW]
    return row["pbc_location"], row["seq"]


def test_the_renderer_types_none_of_the_feed_words(capsys, demo_root):
    """Every word the feed list shows is the API's - what a drop folder
    also feeds, who feeds it, the word that adds one, the two warnings and
    the answer that files a document under another return - so the app
    cannot disagree with the tracker about any of them."""
    here = Path(__file__).resolve().parents[1]
    js = (here / "app" / "renderer" / "app.js").read_text(encoding="utf-8")
    html = (here / "app" / "renderer" / "index.html").read_text(encoding="utf-8")
    for word in (api.FEEDS_LABEL, api.FEEDS_HELP, api.FEEDS_LINE, api.FED_BY_LINE,
                 api.ADD_FEED_LABEL, api.FEED_WARNING, api.RETURN_WARNING,
                 api.HAND_OVER_LABEL, api.HAND_OVER_RETURN_LABEL, api.HAND_OVER_REQUEST_LABEL,
                 api.NOBODY_TYPED, api.NOT_FED, api.HANDED_OVER_LINE,
                 api.FILE_WHERE_IT_WAITS_LABEL):
        assert f'"{word}"' not in js and f"'{word}'" not in js, word
        assert word not in html, word
    words = api.vocab()
    assert words["household"]["feeds_line"] == api.FEEDS_LINE
    assert words["household"]["fed_by_line"] == api.FED_BY_LINE
    assert words["household"]["add_feed"] == api.ADD_FEED_LABEL
    assert words["household"]["nobody_typed"] == api.NOBODY_TYPED
    assert words["review_labels"]["hand_over"] == api.HAND_OVER_LABEL
    # The two boxes of the hand-over have their own words since Fable's
    # review of decision 129: the page borrowed the household heading and
    # the editor's title, which read nearly right and would have drifted
    # the moment either was reworded for its own screen.
    assert words["review_labels"]["hand_over_return"] == api.HAND_OVER_RETURN_LABEL
    assert words["review_labels"]["hand_over_request"] == api.HAND_OVER_REQUEST_LABEL
    # And what the page says once a document has gone (decision 132): the
    # row here is released, in the API's words, filled with the reply's
    # label and request.
    assert words["review_labels"]["handed_over"] == api.HANDED_OVER_LINE
    assert "vocab.review_labels.handed_over" in js
    # And decision 204's one click, labelled by the API and filled by the
    # page with the label the card carries.
    assert words["review_labels"]["file_where_it_waits"] == api.FILE_WHERE_IT_WAITS_LABEL
    assert "vocab.review_labels.file_where_it_waits" in js


def test_a_pass_cannot_be_run_without_the_practice(capsys, demo_root, monkeypatch):
    """*Run now* on a root that cannot be walked is refused - nothing is
    sorted (decision 132). Since decision 203 it is the runner's own
    refusal, before its ``pass started`` line, said as the one failure
    envelope: the button and the schedule refuse the same root the same
    way."""
    import tracker.runner as runner
    from tracker.registry import RegistryError

    father, _llc = two_households(capsys, demo_root)
    text_pdf(inbox_of(father) / "tb.pdf", ["Trial balance as of December 31 2025", TEST_CLIENT], style="padded")

    def unwalkable(root):
        raise RegistryError(f"{root} cannot be walked")

    monkeypatch.setattr(runner, "discover_engagements", unwalkable)
    code, payload = scan(capsys, father)

    assert code == 1, payload
    assert payload["error"].startswith("Clients folder problem: ")
    assert payload["failure"]["kind"] == "refused"
    assert (inbox_of(father) / "tb.pdf").is_file()      # nothing was sorted
    assert read_index(father) == []
    assert not (demo_root / LOG_FILENAME).exists(), "no pass started, so no line says one did"


# ============== what we have received, at once (decision 130) =============
#
# A person's action in the app changes the index between passes, so the
# action refreshes the client README itself: the list is never behind the
# record once an action has run.


def test_filing_a_parked_card_moves_it_from_under_review_to_received_at_once(
        capsys, demo_root, tmp_path):
    from tracker.scaffold import RECEIVED_HEADING, UNDER_REVIEW_HEADING

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Mortgage Notes.docx")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    before = client_readme(engagement)
    assert UNDER_REVIEW_HEADING in before and "  1 document received " in before
    d01 = next(i for i in payload["state"]["items"] if i["identifier"] == "D01")
    d01_label = next(item.label for item in load_manifest(engagement) if item.identifier == "D01")
    assert f"  {d01_label}  Received" not in before

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "identifier": d01["identifier"],
                               "seq": parked["seq"]})
    assert code == 0, payload

    after = client_readme(engagement)
    assert RECEIVED_HEADING in after
    assert f"  {d01_label}  Received" in after
    assert UNDER_REVIEW_HEADING not in after
    assert "Mortgage Notes" not in after


def test_unfiling_moves_it_back_to_under_review_at_once(capsys, demo_root, tmp_path):
    from tracker.scaffold import UNDER_REVIEW_HEADING

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Form 1098 Mortgage Interest.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    label = next(item.label for item in load_manifest(engagement)
                 if item.identifier == filed["identifier"])
    before = client_readme(engagement)
    assert f"  {label}  Received" in before and UNDER_REVIEW_HEADING not in before

    code, payload = run(capsys, "unfile", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "seq": filed["seq"]})
    assert code == 0, payload

    after = client_readme(engagement)
    assert f"  {label}  Received" not in after
    assert UNDER_REVIEW_HEADING in after and "  1 document received " in after
    assert filed["original_name"] not in after


# ------------------------------------ decision 188: one name rule ----


def test_one_name_rule_gives_one_sentence_wherever_a_name_is_typed(capsys, demo_root):
    """A household or a return name is held to the layout's one rule
    wherever a person types one - the wizard's household and return, a
    rolled return's new name, a feed - and each box answers with the same
    sentence: the name as typed, what it is, and the rule's reason."""
    from tracker import layout

    bad = "Pa​rk"
    reason = layout.segment_problem(bad)
    # The sentence quotes the name with its hidden character as a code point
    # (P293), never carrying the character it refuses.
    said_household = layout.NAME_REFUSED.format(typed=layout.quoted(bad), what="household", reason=reason)
    said_return = layout.NAME_REFUSED.format(typed=layout.quoted(bad), what="return", reason=reason)
    items = [{"identifier": "A01", "document": "W-2"}]

    code, payload = run(capsys, "create", stdin={"household": bad, "return_name": "1040 - Park",
                                                 "items": items})
    assert code == 1 and payload["error"] == said_household
    code, payload = run(capsys, "create", stdin={"household": "Park Family", "return_name": bad,
                                                 "items": items})
    assert code == 1 and payload["error"] == said_return

    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - Park",
                                        "items": items})[0] == 0
    prior = where(demo_root, "1040 - Park", household="Park Family")
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(prior),
                        stdin={"year": 2026, "returns": [{"prior": str(prior), "return_name": bad}]})
    assert code == 1 and payload["error"] == said_return
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(prior),
                        stdin={"feeds": [{"household": bad, "return_name": "1040 - Lee"}]})
    assert code == 1 and payload["error"] == said_household
    assert not (demo_root / layout.PRIVATE_TREE / bad).exists()


def test_a_name_the_walk_would_pass_over_is_never_created(capsys, demo_root):
    """C-7: a household made under a name discovery passes over - a dot, an
    underscore, an office lock's ``~$`` - would never be listed, sorted or
    chased. The rule refuses every one before anything is written."""
    from tracker import layout

    for hidden in (".Park", "_Park", "~$Park"):
        code, payload = run(capsys, "create", stdin={
            "household": hidden, "return_name": "1040 - Park",
            "items": [{"identifier": "A01", "document": "W-2"}]})
        assert code == 1, hidden
        assert payload["error"] == layout.NAME_REFUSED.format(
            typed=hidden, what="household", reason=layout.NAME_FIRST_CHARACTER)
    assert not any(demo_root.rglob(ledger.LEDGER_FILENAME))


# ------------------------------- decision 188: the door, the checked root ----


def test_a_rollover_from_a_client_inbox_fails_closed(capsys, demo_root):
    """T3: a return's place is the parser's, so a folder in the client's
    inbox holding a fabricated ``_ledger.jsonl`` is never a prior and
    never a household - for ``rollover``, ``roll-household`` and ``create``
    by ``household_path`` alike - and both trees are as they were."""
    from tracker.templates import template_items

    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - Park",
                                        "form": "1040",
                                        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    real = where(demo_root, "1040 - Park", household="Park Family")
    planted = make_engagement(inbox_of(real) / "X", template_items("1040", year=2025),
                              scaffold=False)
    private, clients = demo_root / PRIVATE_TREE, demo_root / layout.CLIENTS_TREE
    before = (_tree_hashes(private), _tree_hashes(clients))

    code, payload = run(capsys, "rollover", stdin={"prior": str(planted), "year": 2026})
    assert code == 1 and payload["error"] == layout.NOT_A_RETURN.format(name=planted.name,
                                                                        tree=PRIVATE_TREE)
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(planted),
                        stdin={"year": 2026, "returns": [{"prior": str(planted)}]})
    assert code == 1 and payload["error"] == layout.NOT_A_RETURN.format(name=planted.name,
                                                                        tree=PRIVATE_TREE)
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(real),
                        stdin={"year": 2026, "returns": [{"prior": str(planted)}]})
    assert code == 1 and "is not a return's folder" in payload["error"]
    code, payload = run(capsys, "create", stdin={
        "household_path": str(planted), "return_name": "1040 - Evil", "form": "1040",
        "items": [{"identifier": "A01", "document": "W-2"}]})
    assert code == 1 and payload["error"] == layout.NOT_A_HOUSEHOLD.format(name=planted.name,
                                                                           tree=PRIVATE_TREE)
    assert (_tree_hashes(private), _tree_hashes(clients)) == before


def test_every_command_that_reads_the_root_rechecks_it(capsys, demo_root):
    """E-13: a root saved while it was fine and made one level too deep
    afterwards - the trees moved around it - is refused by every command
    that reads it, with "Clients folder problem: " and the refusal; the
    first call still hands the app its words and asks for the folder."""
    from tracker.settings import ROOT_INSIDE_A_TREE

    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - Park",
                                        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    engagement = where(demo_root, "1040 - Park", household="Park Family")
    # A person moves the whole root into the firm's tree of a folder that
    # now holds both trees: the saved root is inside a tree of a real root.
    above = demo_root.parent / "Real root"
    (above / layout.CLIENTS_TREE).mkdir(parents=True)
    (above / PRIVATE_TREE).mkdir()
    moved = above / PRIVATE_TREE / demo_root.name
    demo_root.rename(moved)
    from tracker.settings import KEY_CLIENTS_ROOT, settings_path

    settings = json.loads(settings_path().read_text(encoding="utf-8"))
    settings[KEY_CLIENTS_ROOT] = str(moved)
    settings_path().write_text(json.dumps(settings), encoding="utf-8")
    said = "Clients folder problem: " + ROOT_INSIDE_A_TREE.format(
        root=moved.resolve(), tree=PRIVATE_TREE, real=above.resolve())
    engagement = moved / engagement.relative_to(demo_root)
    try:
        for argv, stdin in [
            (["state", api.ENGAGEMENT_FLAG, str(engagement)], None),
            (["edit-household", api.ENGAGEMENT_FLAG, str(engagement)], {"contact": "x"}),
            (["create"], {"household": "Lee Family", "return_name": "1040 - Lee",
                          "items": [{"identifier": "A01", "document": "W-2"}]}),
            (["rollover"], {"prior": str(engagement), "year": 2026}),
            (["priors"], None),
        ]:
            code, payload = run(capsys, *argv, stdin=stdin)
            assert code == 1 and payload["error"] == said, (argv, payload)
        code, payload = run(capsys, "list")
        assert code == 0 and payload["needs_root"] and payload["root_problem"] == said
        assert payload["vocab"]["commands"]
    finally:
        moved.rename(demo_root)
        shutil.rmtree(above, ignore_errors=True)


# ------------------------------- decision 188: the folder is the name ----


def test_typing_an_existing_households_name_is_refused_and_points_at_the_list(capsys, demo_root):
    """T12: a household name typed again - its folder's name or its
    record's claim, in any case or spacing - is refused before anything is
    written, naming the household in the list and what to add to tell two
    households apart: a first name or a middle initial, then the city."""
    items = [{"identifier": "A01", "document": "W-2"}]
    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - Park",
                                        "items": items})[0] == 0
    said = screen_words.DUPLICATE_HOUSEHOLD.format(existing="Park Family")
    assert "add a first name or a middle initial" in said and "add the city" in said
    for typed in ("Park Family", "PARK FAMILY", "  park   family "):
        code, payload = run(capsys, "create", stdin={"household": typed, "return_name": "1040 - X",
                                                     "items": items})
        assert code == 1 and payload["error"] == said, typed
    assert sorted(p.name for p in (demo_root / PRIVATE_TREE).iterdir()) == ["Park Family"]


def test_look_alike_spellings_of_one_name_are_refused_as_one_name(capsys, demo_root):
    """T2: once ``Park`` exists, every spelling that reads as it - case, a
    Cyrillic letter or two (a mixed name is refused by the rule), full-width
    letters, a soft hyphen - is refused, by the key or by the rule; and a
    name all in one look-alike script is the name it imitates too."""
    from tracker import layout

    items = [{"identifier": "A01", "document": "W-2"}]
    for made in ("Park", "Cox", "Woo"):
        assert run(capsys, "create", stdin={"household": made, "return_name": "1040 - One",
                                            "items": items})[0] == 0
    for typed in ("PARK", "\u0420\u0430rk", "P\u0430rk", "\uff30\uff41\uff52\uff4b",
                  "Pa\u00adrk", "\u0421\u041e\u0425", "\u051c\u041e\u041e"):
        code, payload = run(capsys, "create", stdin={"household": typed, "return_name": "1040 - Two",
                                                     "items": items})
        assert code == 1, typed
        named = layout.quoted(layout.normalised_name(typed))
        assert (payload["error"].startswith(f"'{named}' is not a household name: ")
                or payload["error"].startswith("A household with that name is already in the list")
                ), (typed, payload["error"])
    assert sorted(p.name for p in (demo_root / PRIVATE_TREE).iterdir()) == ["Cox", "Park", "Woo"]


def test_a_client_folder_no_household_owns_is_never_adopted(capsys, demo_root):
    """T12 and C-2: a folder in the client tree no household owns is never
    taken for a new household of that name (or a look-alike of it): the
    wizard says where it is listed, and nothing is written in either tree."""
    stray = demo_root / layout.CLIENTS_TREE / "Lee Family"
    (stray / "2025").mkdir(parents=True)
    (stray / "2025" / "w2.pdf").write_bytes(b"%PDF-1.4 somebody's own file")
    for typed in ("Lee Family", "LEE  FAMILY"):
        code, payload = run(capsys, "create", stdin={
            "household": typed, "return_name": "1040 - Lee",
            "items": [{"identifier": "A01", "document": "W-2"}]})
        assert code == 1 and payload["error"] == screen_words.CLIENT_FOLDER_TAKEN, typed
    assert not (demo_root / PRIVATE_TREE).exists() or not any((demo_root / PRIVATE_TREE).iterdir())
    assert sorted(p.name for p in stray.rglob("*")) == ["2025", "w2.pdf"]


def test_accepting_the_folders_name_is_one_dated_event_and_lifts_the_pause(capsys, demo_root):
    """T15: the card shows the pause and what to accept; accepting writes
    one household_changed line naming the folder on the household's record
    and one rules_changed line on each return whose claim disagreed, each
    carrying the person's word - and nothing is moved or renamed. The
    pause is lifted, and the pass would run the household again."""
    from tracker.households import HOUSEHOLD_PAUSED, household_pause

    engagement = _a_renamed_household(capsys, demo_root)
    household = engagement.parent.parent
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    pause = payload["household"]["pause"]
    assert pause["sentence"] == HOUSEHOLD_PAUSED and pause["scope"] == "household"
    before = sorted(p.relative_to(demo_root) for p in demo_root.rglob("*")
                    if p.name != ledger.LEDGER_FILENAME)
    lines = (len(ledger.read_events(household)), len(ledger.read_events(engagement)))

    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, pause["engagement"],
                        stdin={"seq": pause["seq"], "scope": "household"})
    assert code == 0, payload
    [named] = ledger.read_events(household)[lines[0]:]
    [claimed] = ledger.read_events(engagement)[lines[1]:]
    assert named[ledger.EVENT_KEY] == ledger.HOUSEHOLD_CHANGED
    assert named[ledger.HOUSEHOLD_KEY] == {"name": "Park Household"}
    assert claimed[ledger.EVENT_KEY] == ledger.RULES_CHANGED
    assert claimed[ledger.INFO_KEY] == {"household": "Park Household"}
    for line in (named, claimed):
        assert line[ledger.ACCEPTED_KEY] == ledger.FOLDER_NAME_ACCEPTED and line[ledger.AT_KEY]
    assert household_pause(household) == ""
    assert payload["state"]["household"]["pause"]["sentence"] == ""
    assert sorted(p.relative_to(demo_root) for p in demo_root.rglob("*")
                  if p.name != ledger.LEDGER_FILENAME) == before


def test_a_stale_seq_is_refused(capsys, demo_root):
    """T15: an accept drawn from a page the household's record has moved on
    from is refused and writes nothing."""
    engagement = _a_renamed_household(capsys, demo_root)
    household = engagement.parent.parent
    lines = len(ledger.read_events(household))
    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"seq": lines - 1, "scope": "household"})
    assert code == 1 and payload["error"] == api.ACCEPT_STALE
    assert len(ledger.read_events(household)) == lines


def test_a_year_disagreement_is_not_accepted(capsys, demo_root):
    """T15: a return's year is its record's, so a return folder moved under
    another year is never accepted - the folder goes back - and nothing is
    written."""
    from tracker.households import HOUSEHOLD_PAUSED_YEAR

    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - Park",
                                        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    engagement = where(demo_root, "1040 - Park", household="Park Family")
    moved = engagement.parent.parent / "2019" / engagement.name
    moved.parent.mkdir()
    engagement.rename(moved)
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(moved))
    pause = payload["household"]["pause"]
    assert pause["sentence"] == HOUSEHOLD_PAUSED_YEAR
    # No button (the review's S3): nothing to accept, only to put back.
    assert pause["scope"] == "" and pause["seq"] is None
    assert "retired and made again" in pause["sentence"]
    journal = ledger.path_for(moved).read_bytes()
    seq = len(ledger.read_events(moved.parent.parent))
    for scope in ("household", "return"):
        code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, str(moved),
                            stdin={"seq": seq, "scope": scope})
        assert code == 1 and payload["error"] == api.YEAR_NOT_ACCEPTED
    assert ledger.path_for(moved).read_bytes() == journal


def test_accepting_a_household_whose_originals_rest_under_the_old_name_is_refused(
        capsys, demo_root):
    """T15: a household that has received a document is not renamed this
    season - accepting would orphan the originals resting under its client
    folder of the old name - so the folder goes back, and nothing is
    written."""
    engagement = _a_renamed_household(capsys, demo_root, received=True)
    household = engagement.parent.parent
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))
    pause = payload["household"]["pause"]
    lines = len(ledger.read_events(household))
    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"seq": pause["seq"], "scope": "household"})
    assert code == 1 and payload["error"] == api.ORIGINALS_UNDER_OLD_NAME
    assert len(ledger.read_events(household)) == lines


def test_accepting_one_return_never_renames_a_household_that_has_received_a_document(
        capsys, demo_root):
    """The review's M2 (D-1 by the accept route): an accept of one return
    runs the same originals check before it writes anything, so a household
    whose originals rest under its old client folder is not renamed by a
    return's accept either - and a return's accept never writes the
    household's name, so the household stays paused and the pass red."""
    from tracker.households import HOUSEHOLD_PAUSED, household_pause

    engagement = _a_renamed_household(capsys, demo_root, received=True)
    household = engagement.parent.parent
    lines = (len(ledger.read_events(household)), len(ledger.read_events(engagement)))
    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"seq": lines[0], "scope": "return"})
    assert code == 1 and payload["error"] == api.ORIGINALS_UNDER_OLD_NAME
    assert (len(ledger.read_events(household)), len(ledger.read_events(engagement))) == lines
    assert household_pause(household) == HOUSEHOLD_PAUSED


def test_a_returns_accept_writes_only_that_returns_line(capsys, demo_root):
    """A return's accept, where nothing has been received, writes that
    return's own two names and nothing on the household's record: a
    household whose own record claims another name is still paused until
    its own accept."""
    from tracker.households import HOUSEHOLD_PAUSED, household_pause

    engagement = _a_renamed_household(capsys, demo_root)
    household = engagement.parent.parent
    lines = len(ledger.read_events(household))
    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"seq": lines, "scope": "return"})
    assert code == 0, payload
    assert len(ledger.read_events(household)) == lines
    last = ledger.read_events(engagement)[-1]
    assert last[ledger.INFO_KEY] == {"household": "Park Household", "return_name": engagement.name}
    assert household_pause(household) == HOUSEHOLD_PAUSED


def test_the_accept_and_the_share_write_the_lines_they_wrote_before(capsys, demo_root):
    """P327 (SPEC-architecture-p3 R3.7.4): the API asks the household's and
    the return's own writers for the share and the accept, and every line
    they write is the line the API composed itself before - pasted here as
    the dicts it built. A line is compared less its stamp and the keys every
    append adds (``ledger.LINE_KEYS``), each named by its constant. The
    journal writes a line's keys sorted, so their order is not on disk to
    compare: the comparison is the dict's."""
    from tracker.households import household_pause
    from tracker.layout import private_household_dir

    def written(folder, since):
        return [{key: value for key, value in line.items()
                 if key != ledger.AT_KEY and key not in ledger.LINE_KEYS}
                for line in ledger.read_events(folder)[since:]]

    items = [{"identifier": "A01", "document": "W-2"}]
    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - John Park",
                                        "items": items})[0] == 0
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Park Family")),
        "return_name": "1040 - Maria Park", "items": items})[0] == 0
    private = demo_root / PRIVATE_TREE
    (private / "Park Family").rename(private / "Park Household")
    household = private / "Park Household"
    john, maria = (where(demo_root, name, household="Park Household")
                   for name in ("1040 - John Park", "1040 - Maria Park"))

    # One return's accept: that return's two names, and nothing on the
    # household's record or the other return's.
    lines = {one: len(ledger.read_events(one)) for one in (household, john, maria)}
    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, str(john),
                        stdin={"seq": lines[household], "scope": "return"})
    assert code == 0, payload
    assert written(john, lines[john]) == [{
        "event": "rules_changed",
        "info": {"household": "Park Household", "return_name": "1040 - John Park"},
        "accepted": "folder_name"}]
    assert written(household, lines[household]) == written(maria, lines[maria]) == []

    # The household's accept: its own name, and the one return whose claim
    # still disagrees - John's agrees since his own accept.
    lines = {one: len(ledger.read_events(one)) for one in (household, john, maria)}
    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, str(maria),
                        stdin={"seq": lines[household], "scope": "household"})
    assert code == 0, payload
    assert written(household, lines[household]) == [{
        "event": "household_changed",
        "household": {"name": "Park Household"},
        "accepted": "folder_name"}]
    assert written(maria, lines[maria]) == [{
        "event": "rules_changed",
        "info": {"household": "Park Household"},
        "accepted": "folder_name"}]
    assert written(john, lines[john]) == []
    assert household_pause(household) == ""

    # The share: the day and nothing else.
    assert run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(john),
               stdin={"link": "https://drive.example/park"})[0] == 0
    since = len(ledger.read_events(household))
    code, payload = run(capsys, "mark-shared", api.ENGAGEMENT_FLAG, str(john))
    assert code == 0, payload
    assert written(household, since) == [{"event": "sharing_confirmed"}]


# ============ pilot P141, P170, P172: linked households and the form ===========


def three_households(capsys, root):
    """Park Family (a 1040), Park & Lee LLC (an 1120S) and Lee Family (a
    1040), made the way the app makes them, each with its form recorded."""
    for household, return_name, form in (("Park Family", "1040 - John Park", "1040"),
                                         ("Park & Lee LLC", "1120S - Park & Lee LLC", "1120S"),
                                         ("Lee Family", "1040 - Sam Lee", "1040")):
        assert run(capsys, "create", stdin={
            "household": household, "contact": "John", "return_name": return_name, "form": form,
            "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    return (where(root, "1040 - John Park", household="Park Family"),
            where(root, "1120S - Park & Lee LLC", household="Park & Lee LLC"),
            where(root, "1040 - Sam Lee", household="Lee Family"))


def test_a_related_household_is_written_on_both_records_and_removed_from_both(capsys, demo_root):
    """Pilot P170: a person marks two households related in Edit Household;
    the save writes the mark into both records, the state names it, and
    removing it on either side removes it from both. Nothing is inferred."""
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir

    park, llc, lee = three_households(capsys, demo_root)
    park_dir = private_household_dir(demo_root, "Park Family")
    lee_dir = private_household_dir(demo_root, "Lee Family")
    llc_dir = private_household_dir(demo_root, "Park & Lee LLC")
    assert load_household_info(park_dir).related == ()

    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(park),
                        stdin={"related": ["Lee Family", "park & lee llc"]})
    assert code == 0, payload
    assert "related" in payload["saved"]["household"]
    assert load_household_info(park_dir).related == ("Lee Family", "Park & Lee LLC")
    assert load_household_info(lee_dir).related == ("Park Family",)
    assert load_household_info(llc_dir).related == ("Park Family",)
    assert payload["state"]["household"]["related"] == ["Lee Family", "Park & Lee LLC"]

    # Removed from the other side: gone from both records.
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(lee), stdin={"related": []})
    assert code == 0, payload
    assert load_household_info(lee_dir).related == ()
    assert load_household_info(park_dir).related == ("Park & Lee LLC",)
    assert load_household_info(llc_dir).related == ("Park Family",)
    assert api.vocab()["household"]["related_label"] == "Related Households"
    assert api.vocab()["household"]["add_related"] == "Add Related Household"


def test_a_related_list_refuses_itself_a_blank_a_repeat_and_a_household_that_is_not_there(capsys, demo_root):
    """Pilot P170: only another household that exists can be related, each
    once; every refusal says the name and nothing is written."""
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir

    park, _llc, _lee = three_households(capsys, demo_root)
    park_dir = private_household_dir(demo_root, "Park Family")
    for sent, said in ((["Park Family"], screen_words.RELATED_REFUSED.format(household="Park Family")),
                       ([""], screen_words.RELATED_REFUSED.format(household="(blank)")),
                       ("Lee Family", screen_words.RELATED_NOT_A_LIST), ([1], screen_words.RELATED_NOT_A_LIST),
                       (["Lee Family", "lee family"], screen_words.RELATED_REFUSED.format(household="lee family")),
                       (["Nobody Here"], screen_words.RELATED_UNKNOWN.format(household="Nobody Here"))):
        code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(park), stdin={"related": sent})
        assert code == 1 and payload["error"] == said, (sent, payload)
    assert load_household_info(park_dir).related == ()


def test_the_list_and_the_firm_carry_each_households_links_both_ways_and_each_returns_form(capsys, demo_root):
    """Pilot P141, P172: a feed is Also Feeds on the feeding household and
    Fed By on the fed one; a related mark is Related on both, even when
    only one record names it; and every return carries its recorded form.
    The fields are additive: nothing already in either reply moves."""
    from dataclasses import replace

    from tracker.households import load_household_info, save_household
    from tracker.layout import private_household_dir

    park, llc, lee = three_households(capsys, demo_root)
    assert run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(park),
               stdin={"feeds": [{"household": "Park & Lee LLC", "return_name": "1120S - Park & Lee LLC"}]})[0] == 0
    # A related mark on one record only (a save that stopped half way) still shows on both ends.
    lee_dir = private_household_dir(demo_root, "Lee Family")
    save_household(lee_dir, replace(load_household_info(lee_dir), related=("Park Family",)))

    _code, listed = run(capsys, "list")
    links = {one["name"]: [(link["name"], link["kind"]) for link in one["links"]] for one in listed["households"]}
    assert links["Park Family"] == [("Lee Family", "related"), ("Park & Lee LLC", "feeds")]
    assert links["Park & Lee LLC"] == [("Park Family", "fed_by")]
    assert links["Lee Family"] == [("Park Family", "related")]
    paths = {one["name"]: one["path"] for one in listed["households"]}
    assert {link["path"] for one in listed["households"] for link in one["links"]} <= set(paths.values())
    assert {one["return_name"]: one["form"] for one in listed["engagements"]} == {
        "1040 - John Park": "1040", "1120S - Park & Lee LLC": "1120S", "1040 - Sam Lee": "1040"}

    _code, firm = run(capsys, "firm")
    by_return = {Path(one["path"]): one for one in firm["returns"]}
    assert by_return[llc]["form"] == "1120S" and by_return[park]["form"] == "1040"
    assert [(link["name"], link["kind"]) for link in by_return[llc]["links"]] == [("Park Family", "fed_by")]
    assert [(link["name"], link["kind"]) for link in by_return[lee]["links"]] == [("Park Family", "related")]
    assert {"path", "household", "label", "year", "counts", "files", "paused"} <= set(by_return[park])


def test_a_one_sided_related_link_is_repaired_by_saving_either_side(capsys, demo_root):
    """Pilot P170, the review's M1: a save that stopped after its first
    write leaves Park naming Lee and Lee naming nobody. Saving Lee without
    the link (what the editor sends once the person removes it) clears it
    from Park too; saving Park with it completes it on Lee."""
    from dataclasses import replace

    from tracker.households import load_household_info, save_household
    from tracker.layout import private_household_dir

    park, _llc, lee = three_households(capsys, demo_root)
    park_dir = private_household_dir(demo_root, "Park Family")
    lee_dir = private_household_dir(demo_root, "Lee Family")
    save_household(park_dir, replace(load_household_info(park_dir), related=("Lee Family",)))
    assert load_household_info(lee_dir).related == ()

    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(lee), stdin={"related": []})
    assert code == 0, payload
    assert load_household_info(park_dir).related == (), "removed on the side that lacked it: gone from both"
    _code, listed = run(capsys, "list")
    assert all(not one["links"] for one in listed["households"] if one["name"] in ("Park Family", "Lee Family"))

    save_household(park_dir, replace(load_household_info(park_dir), related=("Lee Family",)))
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(park), stdin={"related": ["Lee Family"]})
    assert code == 0, payload
    assert load_household_info(lee_dir).related == ("Park Family",), "re-saving the side that has it completes the other"


def test_the_other_households_record_is_read_and_written_inside_its_own_lock(capsys, demo_root, monkeypatch):
    """Pilot P170, the review's S1: the mirror reads the other household
    under that household's lock, so another writer that tries to change it
    between the read and the write is refused by the lock rather than
    having its change silently reverted by the mirror's save."""
    from dataclasses import replace

    from tracker import households
    from tracker.layout import private_household_dir
    from tracker.locking import EngagementLockedError

    park, _llc, _lee = three_households(capsys, demo_root)
    lee_dir = private_household_dir(demo_root, "Lee Family")
    real = api.load_household_info
    said = []

    def and_another_writer(folder):
        info = real(folder)
        if Path(folder) == lee_dir and not said:
            try:
                households.save_household(lee_dir, replace(households.load_household_info(lee_dir), contact="Changed Meanwhile"))
                said.append("written")
            except EngagementLockedError:
                said.append("refused")
        return info

    for module in (api, creation, household_edit):
        monkeypatch.setattr(module, "load_household_info", and_another_writer)
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(park), stdin={"related": ["Lee Family"]})
    assert code == 0, payload
    after = households.load_household_info(lee_dir)
    assert after.related == ("Park Family",)
    assert said == ["refused"] or after.contact == "Changed Meanwhile", (said, after.contact)


def test_a_contact_only_save_touches_no_linked_household_even_while_its_sort_holds_it(capsys, demo_root):
    """The re-check's MUST-R1 (1): the editor always sends the related list,
    so a save that changes only the contact must not reach a linked
    household whose record already agrees - no lock, no write, no notice -
    and so succeeds while another pass holds that household."""
    from tracker import ledger
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir
    from tracker.locking import acquire_lock, release_lock

    park, _llc, _lee = three_households(capsys, demo_root)
    assert run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(park), stdin={"related": ["Lee Family"]})[0] == 0
    lee_dir = private_household_dir(demo_root, "Lee Family")
    lines = len(ledger.read_events(lee_dir))
    held = acquire_lock(lee_dir)
    try:
        code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(park),
                            stdin={"contact": "John and Mary", "related": ["Lee Family"]})
    finally:
        release_lock(held)
    assert code == 0, payload
    assert payload["warnings"] == [] and payload["saved"]["household"] == ["contact"]
    assert len(ledger.read_events(lee_dir)) == lines
    assert load_household_info(lee_dir).related == ("Park Family",)


def test_a_link_to_a_household_being_sorted_saves_here_says_so_and_a_later_save_completes_it(capsys, demo_root):
    """The re-check's MUST-R1 (2): when the other household's lock is held,
    the household edited is saved, the reply exits 0 with a notice that the
    link is pending on the other, and saving again once its sort is over
    writes the other side."""
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir
    from tracker.locking import acquire_lock, release_lock

    park, _llc, _lee = three_households(capsys, demo_root)
    park_dir = private_household_dir(demo_root, "Park Family")
    lee_dir = private_household_dir(demo_root, "Lee Family")
    held = acquire_lock(lee_dir)
    try:
        code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(park), stdin={"related": ["Lee Family"]})
    finally:
        release_lock(held)
    assert code == 0, payload
    assert load_household_info(park_dir).related == ("Lee Family",)
    assert load_household_info(lee_dir).related == ()
    assert payload["warnings"] == ["Link Pending: Lee Family Is Busy"]
    assert api.SCREEN["notices"]["related_pending"] == "Link Pending: {household} Is Busy"

    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(park), stdin={"related": ["Lee Family"]})
    assert code == 0 and payload["warnings"] == [], payload
    assert load_household_info(lee_dir).related == ("Park Family",)


def test_a_cached_rows_links_follow_a_change_to_another_households_record(capsys, demo_root, monkeypatch):
    """The 0.3 landing's join of the firm cache (P120) and linked households
    (P141, P172): a household's links depend on other households' records,
    so they are worked out practice-wide on every reply and never kept in a
    row. Lee's record gains Park; Park's own folders do not change, yet
    Park's cached row says Related at once, exactly as the whole walk does."""
    from dataclasses import replace

    from tracker.households import load_household_info, save_household
    from tracker.layout import private_household_dir

    park, _llc, _lee = three_households(capsys, demo_root)
    _aged(demo_root)
    whole = _firm_whole(capsys, monkeypatch)
    assert _cached_firm(capsys) == whole
    assert {Path(one["path"]): one["links"] for one in whole["returns"]}[park] == []
    lee_dir = private_household_dir(demo_root, "Lee Family")
    save_household(lee_dir, replace(load_household_info(lee_dir), related=("Park Family",)))
    _aged(demo_root)
    whole = _firm_whole(capsys, monkeypatch)
    by_path = {Path(one["path"]): one for one in whole["returns"]}
    assert [(link["name"], link["kind"]) for link in by_path[park]["links"]] == [("Lee Family", "related")]
    read = _rows_read(monkeypatch)
    assert _cached_firm(capsys) == whole
    assert not any(str(one).startswith(str(park)) for one in read), "Park's row came from the cache"


def test_importing_the_api_loads_no_pdf_reader():
    """P219 (findings-1 #6, findings-3 #6): pypdf, with its cryptography,
    was 136 ms of every command's start; it is imported when the first PDF
    is opened, so a command that opens none never pays it."""
    import subprocess
    import sys

    from tests.plugin_session import REPO, child_env

    probe = "import sys\nimport tracker.api\nprint(sorted(m for m in sys.modules if m.split('.')[0] == 'pypdf'))\n"
    done = subprocess.run([sys.executable, "-c", probe], cwd=REPO, env=child_env(),
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"
