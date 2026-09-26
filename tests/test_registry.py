"""Tests for tracker/registry.py — the walk knows what every level is.

The rule under test: nothing has to be registered. The scheduled run walks
the clients folder **by position** (decision 125) - the two trees, the
household, the year, the return - finds every record where one belongs, and
reads each return's details. A client nobody typed into a list is still
found; a record nobody can read is still reported; **every folder that does
not fit the layout is listed with one sentence and left alone**, which is
the owner's rule and the whole of what a misfit is.
"""

import datetime as dt

import pytest

from tests.conftest import TEST_HOUSEHOLD, make_engagement
from tracker import ledger
from tracker.layout import CLIENTS_TREE, PRIVATE_TREE, client_household_dir, private_household_dir
from tracker.manifest import EngagementInfo, RequestItem
from tracker.registry import (
    LEGACY_FOLDER,
    LEGACY_MANIFEST_FILENAME,
    MISFIT_NO_HOUSEHOLD_RECORD,
    MISFIT_NO_RETURN,
    MISFIT_NOT_A_TREE,
    MISFIT_NOT_A_YEAR,
    MISFIT_RECORD_MISPLACED,
    NAME_DISAGREES,
    UNLISTED,
    Engagement,
    RegistryError,
    discover_engagements,
    engagement_dirs,
)
from tracker.scaffold import PREPARED_DIR_NAME

ITEMS = [RequestItem(identifier="A01", document="W-2")]


@pytest.fixture
def root(tmp_path, monkeypatch):
    """The clients root these claims walk, recorded the way the app records it.

    A folder of its own under the test's temporary one, because the
    suite's own database sits in ``tmp_path/app`` and a walk pointed at
    ``tmp_path`` would have to leave that folder alone - which is true and
    is not what any of these claims is about.

    Recorded, because a return keeps its name every year under the same
    household (decision 125) and the store keys a folder by its path below
    the clients root: with no root written down it keys by the folder's
    parent, and ``2025/1040 - Smith`` and ``2026/1040 - Smith`` would be
    one row. The office always has one; so do these claims.
    """
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    folder = tmp_path / "Clients root"
    folder.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    (tmp_path / "app").mkdir(exist_ok=True)
    set_clients_root(folder)
    return folder


def make(root, household="Smith Family", year=2025, name="1040 - Smith", info=None, scaffold=False):
    return make_engagement(root, ITEMS, info, household=household, year=year,
                           return_name=name, scaffold=scaffold)


def misfits(root):
    """Every folder the walk left alone, by name, with its sentence."""
    return {m.path.name: m.sentence for m in discover_engagements(root).misfits}


# ------------------------------------------------------------ the walk ----


def test_discovery_is_positional_and_finds_a_return_only_at_the_fourth_level(root):
    """A return is ``root/J Park & Associates/<household>/<year>/<return>``
    and nothing else is one: not a record above it, not one below it."""
    engagement = make(root)
    # A record inside the return's own folders does not split it in two.
    (engagement / PREPARED_DIR_NAME).mkdir(parents=True, exist_ok=True)
    ledger.path_for(engagement / PREPARED_DIR_NAME).write_text("", encoding="utf-8")

    assert engagement_dirs(root) == [engagement]
    registry = discover_engagements(root)
    assert [e.path for e in registry.engagements] == [engagement]
    assert [h.path for h in registry.households] == [private_household_dir(root, "Smith Family")]
    assert {h: [e.path for e in found] for h, found in registry.by_household().items()} == {
        private_household_dir(root, "Smith Family"): [engagement]}
    assert registry.source == root


def test_the_client_tree_is_never_walked(root):
    """Nothing under the tree a client is shared is ever a record, and the
    walk does not go looking: a journal planted there is neither an
    engagement nor a misfit, because the guarantee is what makes the tree
    safe to share."""
    make(root, scaffold=True)
    planted = client_household_dir(root, "Smith Family") / "2025"
    planted.mkdir(parents=True, exist_ok=True)
    ledger.path_for(planted).write_text("", encoding="utf-8")

    registry = discover_engagements(root)
    assert [e.path.name for e in registry.engagements] == ["1040 - Smith"]
    assert not any(CLIENTS_TREE in m.path.parts for m in registry.misfits)


def test_every_misfit_is_listed_once_with_its_sentence_and_walked_no_further(root):
    """One of each shape the walk can meet, each with the one sentence a
    person acts on - and nothing inside any of them is read."""
    from tests.samples import listing_denied

    make(root)
    private = root / PRIVATE_TREE

    # A folder at the top that is neither tree.
    stray = root / "Archive"
    (stray / "anything").mkdir(parents=True)
    ledger.path_for(stray / "anything").write_text("", encoding="utf-8")

    # A record in the place the layout before decision 125 put one.
    misplaced = private / "Old Client 2024"
    misplaced.mkdir(parents=True)
    ledger.path_for(misplaced).write_text("", encoding="utf-8")

    # A folder where a household would be, with nothing the tracker reads.
    (private / "No Record Family").mkdir()

    # A year folder not named as one, under a real household.
    household = private_household_dir(root, "Smith Family")
    (household / "Archive 2024").mkdir()

    # A return folder with no record, and one with only the old workbook.
    (household / "2025" / "1120S - Nothing Here").mkdir(parents=True)
    legacy = household / "2025" / "1065 - From The Excel Days"
    legacy.mkdir(parents=True)
    (legacy / LEGACY_MANIFEST_FILENAME).write_bytes(b"PK any bytes at all")

    found = misfits(root)
    assert found["Archive"] == MISFIT_NOT_A_TREE.format(clients=CLIENTS_TREE, private=PRIVATE_TREE)
    assert found["Old Client 2024"] == MISFIT_RECORD_MISPLACED
    assert found["No Record Family"] == MISFIT_NO_HOUSEHOLD_RECORD
    assert found["Archive 2024"] == MISFIT_NOT_A_YEAR
    assert found["1120S - Nothing Here"] == MISFIT_NO_RETURN
    assert found["1065 - From The Excel Days"] == LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME)
    # Nothing inside a misfit is read: the record under the stray tree is
    # not an engagement, and the walk lists each folder once.
    assert [e.path.name for e in discover_engagements(root).engagements] == ["1040 - Smith"]
    assert len(discover_engagements(root).misfits) == len(found)

    # A folder the walk cannot list is said, with its own sentence.
    denied = household / "2026"
    denied.mkdir()
    with listing_denied(denied):
        said = {m.path.name: m.sentence for m in discover_engagements(root).misfits}
    assert said["2026"].startswith(UNLISTED.split("{")[0])


def test_a_household_with_no_return_anywhere_is_said_and_is_still_a_household(root):
    """A household set up and never given a return is a folder a person has
    to finish, not a silence."""
    from tracker.households import create_household
    from tracker.records import HouseholdInfo

    household = private_household_dir(root, "Empty Family")
    household.mkdir(parents=True)
    create_household(household, HouseholdInfo(name="Empty Family"))
    make(root)

    registry = discover_engagements(root)
    assert {h.name for h in registry.households} == {"Empty Family", "Smith Family"}
    assert misfits(root)["Empty Family"] == MISFIT_NO_RETURN


def test_a_folder_whose_name_disagrees_with_its_record_is_processed_as_the_record_says_and_warned(root):
    """The record wins over a folder somebody renamed, and nothing is ever
    renamed back: the return is processed as its details say and the
    disagreement is one sentence a person reads."""
    engagement = make(root, year=2025)
    household = private_household_dir(root, "Smith Family")
    (household / "2025").rename(household / "2027")             # a year folder, renamed
    moved = household / "2027" / "1040 - Smith"

    [found] = discover_engagements(root).engagements
    assert found.path == moved
    assert found.problem == ""                                   # still an engagement
    assert found.tax_year == 2025 and found.label.endswith("1040 - Smith")
    assert found.warning == NAME_DISAGREES.format(
        folder="Smith Family/2027/1040 - Smith", recorded=found.label)
    assert moved.is_dir()                                        # nothing was renamed
    assert engagement.parent.parent == household


def test_hidden_and_underscore_folders_are_skipped(root):
    """Sync staging and hidden state are the machine's, not a household's:
    passed over without a word, because a misfit list a person cannot act
    on is noise."""
    make(root)
    private = root / PRIVATE_TREE
    (private / ".tmp.driveupload").mkdir()
    (private / "_archive").mkdir()

    registry = discover_engagements(root)
    assert [e.path.name for e in registry.engagements] == ["1040 - Smith"]
    assert registry.misfits == []


# ----------------------------------------------------------- the details ----


def test_the_engagement_details_drive_the_run(root):
    make(root, household="Smith Family", info=EngagementInfo(
        client="John Smith", link="https://drive.example/abc",
        due=dt.date(2026, 3, 15), sender="Jason Park", firm="J Park",
    ))
    make(root, household="Acme", name="1120S - Acme",
         info=EngagementInfo(client="Dana Lee", reminders=False))
    make(root, household="Old Client", name="1040 - Old", year=2024,
         info=EngagementInfo(active=False))

    registry = discover_engagements(root)
    by_return = {e.path.name: e for e in registry.engagements}
    smith = by_return["1040 - Smith"]
    assert smith.client == "John Smith" and smith.due == dt.date(2026, 3, 15)
    assert smith.link == "https://drive.example/abc" and smith.sender == "Jason Park"
    assert by_return["1120S - Acme"].reminders is False
    assert by_return["1040 - Old"].active is False
    assert sorted(e.path.name for e in registry.active) == ["1040 - Smith", "1120S - Acme"]


def test_an_engagement_is_its_details(root):
    # Every field of the return's details is reachable on the Engagement
    # without being declared a second time.
    from dataclasses import fields

    make(root, info=EngagementInfo(client="John", sender="Jason"))
    [engagement] = discover_engagements(root).engagements
    for field in fields(EngagementInfo):
        assert getattr(engagement, field.name) == getattr(engagement.info, field.name)
    assert engagement.client == "John" and engagement.sender == "Jason"
    with pytest.raises(AttributeError):
        _ = engagement.no_such_field


def test_the_label_is_the_household_the_year_and_the_return(root):
    """Everything that lists returns says the same three things, so nobody
    reads a column of years or two identical return names."""
    engagement = make(root)
    [found] = discover_engagements(root).engagements
    assert found.label == "Smith Family 2025 1040 - Smith"
    # Read off the folders where the record carries none of the three.
    assert Engagement(path=engagement,
                      household_path=private_household_dir(root, "Smith Family")
                      ).label == "Smith Family 2025 1040 - Smith"


def test_an_engagement_built_without_its_household_reads_it_off_its_own_path(root):
    """The household is positional, so it is never left blank. A caller
    that built an Engagement from a folder alone used to carry the working
    folder as its household, and a pass given that would lay an inbox and
    a year folder out wherever the process happened to be standing - which
    is how an empty ``Clients`` folder turned up in a checkout."""
    from pathlib import Path

    engagement = make(root, household="Smith Family")

    bare = Engagement(path=engagement)
    assert bare.household_path == private_household_dir(root, "Smith Family")
    assert bare.household_path != Path()
    assert bare.label == "Smith Family 2025 1040 - Smith"
    # A household named by the caller is still the caller's.
    named = private_household_dir(root, "Somebody Else")
    assert Engagement(path=engagement, household_path=named).household_path == named


def test_find_matches_label_or_path(root):
    make(root, household="Smith Family")
    make(root, household="Acme", name="1120S - Acme")
    registry = discover_engagements(root)
    assert [e.path.name for e in registry.find("smith")] == ["1040 - Smith"]
    assert [e.path.name for e in registry.find("acme")] == ["1120S - Acme"]
    assert registry.find("nobody") == []


def test_an_unreadable_record_is_listed_with_its_problem_not_dropped(root):
    make(root, name="1040 - Fine")
    broken = private_household_dir(root, "Smith Family") / "2025" / "1040 - Broken"
    broken.mkdir(parents=True)
    ledger.path_for(broken).write_text("{this line is not an event}\n", encoding="utf-8")

    registry = discover_engagements(root)
    found = next(e for e in registry.engagements if e.path == broken)
    assert "does not read as an event" in found.problem
    assert len(registry.engagements) == 2


def test_a_household_folder_the_walk_cannot_list_is_a_misfit_not_a_silence(root):
    # The tenth reading: an ACL that denies the run's account made a whole
    # client vanish from the registry, and the run reported success.
    from tests.samples import listing_denied

    make(root, household="Jones Family", name="1040 - Jones")
    make(root, household="Smith Family")
    denied = private_household_dir(root, "Smith Family")

    with listing_denied(denied):
        registry = discover_engagements(root)
    assert [e.path.name for e in registry.engagements] == ["1040 - Jones"]
    assert any(m.path == denied and m.sentence.startswith(UNLISTED.split("{")[0])
               for m in registry.misfits)


def test_a_folder_with_only_a_legacy_workbook_is_a_misfit_and_is_never_imported(root):
    """Decision 104: a folder from before it, holding the workbook the
    tracker no longer reads and no record, is listed with its sentence -
    not descended into, not run, and never imported. A folder whose record
    carries no rules with that workbook beside it is still an engagement
    and carries the same sentence as its problem."""
    make(root)
    year = private_household_dir(root, "Smith Family") / "2025"
    legacy = year / "1040 - From The Excel Days"
    (legacy / PREPARED_DIR_NAME).mkdir(parents=True)
    (legacy / LEGACY_MANIFEST_FILENAME).write_bytes(b"PK any bytes at all")

    registry = discover_engagements(root)
    assert [e.path.name for e in registry.engagements] == ["1040 - Smith"]
    assert misfits(root)[legacy.name] == LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME)
    assert list(legacy.glob("*.jsonl")) == []           # nothing imported, nothing written

    half = year / "1065 - Half Set Up"
    half.mkdir()
    ledger.path_for(half).write_text("", encoding="utf-8")     # a record with no rules in it
    (half / LEGACY_MANIFEST_FILENAME).write_bytes(b"PK")
    listed = {e.path.name: e for e in discover_engagements(root).engagements}
    assert listed["1065 - Half Set Up"].problem == LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME)
    assert half in engagement_dirs(root)            # it holds a record, so the walk finds it


# ---------------------------------------------------------- the rollover ----


def test_a_rolled_forward_prior_stays_retired_when_the_clients_root_moves(root, tmp_path):
    # Rolled From is written as an absolute path. A root moved to another
    # drive (or renamed) would otherwise bring every prior back to life and
    # the draft day would chase last year's list (the ninth reading).
    from tracker.registry import engagement_from, mark_superseded

    prior = make(root, year=2025)
    make(root, year=2026, info=EngagementInfo(rolled_from=str(prior.resolve())))
    moved = tmp_path / "Moved"
    root.rename(moved)

    found = [engagement_from(p) for p in engagement_dirs(moved)]
    retired = {e.path.parent.name: e.superseded_by for e in mark_superseded(found)}
    assert retired["2025"] and not retired["2026"]


def test_a_rolled_forward_prior_is_retired_across_two_households_with_the_same_return_name(root):
    """A return keeps its name every year, so two households may each hold
    ``2025/1040 - John Park``: the last two names tie and the third - the
    household's - decides (``layout.ROLLED_FROM_TAIL`` is three since decision
    125, worded at layer 0 since decision 131)."""
    from tracker.registry import engagement_from, mark_superseded

    prior = make(root, household="Park Family", year=2025, name="1040 - John Park")
    make(root, household="Park Family", year=2026, name="1040 - John Park",
         info=EngagementInfo(rolled_from=str(prior.resolve())))
    make(root, household="Lee Family", year=2025, name="1040 - John Park")  # another household

    found = [engagement_from(p) for p in engagement_dirs(root)]
    retired = {e.path.relative_to(root).as_posix(): e.superseded_by
               for e in mark_superseded(found)}

    private = PRIVATE_TREE
    assert retired[f"{private}/Park Family/2025/1040 - John Park"] == "Park Family 2026 1040 - John Park"
    assert retired[f"{private}/Park Family/2026/1040 - John Park"] == ""
    assert retired[f"{private}/Lee Family/2025/1040 - John Park"] == ""


def test_discovery_retires_a_prior_by_the_layout_rule(root, tmp_path, monkeypatch):
    """Discovery and the scaffold read one rule (decision 131): the tail a
    Rolled From path must share with a return folder is
    ``layout.ROLLED_FROM_TAIL``, counted by ``layout.shared_tail``, and the
    registry keeps no copy of either - so moving the number moves both."""
    import tracker.layout as layout
    import tracker.registry as registry
    from tracker.registry import engagement_from, mark_superseded

    assert not hasattr(registry, "_TAIL_NAMES") and not hasattr(registry, "_shared_tail")
    prior = make(root, year=2025)
    make(root, year=2026, info=EngagementInfo(rolled_from=str(prior.resolve())))
    moved = tmp_path / "Moved"
    root.rename(moved)

    def retired():
        found = [engagement_from(p) for p in engagement_dirs(moved)]
        return {e.path.parent.name: e.superseded_by for e in mark_superseded(found)}

    # Four names in common - the private tree's, the household's, the
    # year's, the return's - and the root's own name differs.
    assert retired()["2025"]
    monkeypatch.setattr(layout, "ROLLED_FROM_TAIL", 5)
    assert not retired()["2025"]                     # the layout's rule is the rule


def test_a_rolled_from_that_matches_nothing_is_a_warning_not_a_silence(root):
    # The eleventh reading: a Rolled From that resolved to nothing and
    # tail-matched nothing retired nothing and said nothing, and the
    # scheduled run kept chasing last year's list.
    from tracker.registry import ROLLED_FROM_UNMATCHED, engagement_from, mark_superseded

    make(root, year=2025)
    make(root, year=2026, info=EngagementInfo(rolled_from="1040 - Smith"))   # hand-typed, relative
    found = [engagement_from(p) for p in engagement_dirs(root)]
    marked = {e.path.parent.name: e for e in mark_superseded(found)}
    assert marked["2025"].superseded_by == "" and marked["2025"].warning == ""
    assert marked["2026"].warning == ROLLED_FROM_UNMATCHED.format(rolled_from="1040 - Smith")
    assert marked["2026"].active

    # A folder the walk could not list is never taken as the prior: its
    # report survives rather than becoming a benign skip.
    unlisted = Engagement(path=root / "gone", problem="could not be listed (Access is denied)")
    successor = engagement_from(make(root, household="Jones Family", year=2026,
                                     name="1040 - Jones",
                                     info=EngagementInfo(rolled_from=str(unlisted.path))))
    marked = {e.path.name: e for e in mark_superseded([unlisted, successor])}
    assert marked["gone"].superseded_by == "" and marked["gone"].problem
    assert marked["1040 - Jones"].warning


# --------------------------------------------------------------- refusals ----


def test_a_root_that_is_not_a_folder_is_an_error(root):
    with pytest.raises(RegistryError, match="not a folder"):
        discover_engagements(root / "nowhere")


def test_a_root_with_nothing_under_it_is_an_error_not_a_quiet_no_op(root):
    """A root the walk finds nothing at all in - no return, no household,
    not even a folder to leave alone - is a typo in the scheduled task."""
    (root / "Empty").mkdir()
    with pytest.raises(RegistryError, match="nothing found"):
        discover_engagements(root / "Empty")


# -------------------------------------------------------------------- CLI ----


def test_the_registry_command_line_prints_households_returns_and_misfits(root, capsys):
    """One command says what the scheduled run would find: each household,
    its returns under it, and every folder left alone with its sentence."""
    import runpy
    import sys

    make(root, household=TEST_HOUSEHOLD)
    (root / "Archive").mkdir()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, "argv", ["tracker.registry", str(root)])
        runpy.run_module("tracker.registry", run_name="__main__")
    printed = capsys.readouterr().out
    assert "1 household(s)" in printed
    assert TEST_HOUSEHOLD in printed
    assert f"{TEST_HOUSEHOLD} 2025 1040 - Smith" in printed
    assert "Folders the tracker leaves alone (1)" in printed
    assert MISFIT_NOT_A_TREE.format(clients=CLIENTS_TREE, private=PRIVATE_TREE) in printed


def test_fed_by_lists_the_households_whose_feeds_name_this_one(tmp_path):
    """The other direction of the feed list (decision 129): a household
    whose return another drop folder feeds is told whose, by household
    name - because anyone with access to that folder may drop for a return
    that lives here. Who is shared on *that* household is on its own card,
    never on this one."""
    from dataclasses import replace

    from tracker.households import fed_by, load_household_info, save_household
    from tracker.layout import private_household_dir
    from tracker.records import Feed

    make_engagement(tmp_path, ITEMS, household="Park Family",
                    return_name="1040 - John Park", scaffold=False)
    make_engagement(tmp_path, ITEMS, household="Lee Family",
                    return_name="1040 - Sam Lee", scaffold=False)
    make_engagement(tmp_path, ITEMS, household="Park & Lee LLC",
                    return_name="1120S - Park & Lee LLC", scaffold=False)
    llc = private_household_dir(tmp_path, "Park & Lee LLC")
    for name in ("Park Family", "Lee Family"):
        folder = private_household_dir(tmp_path, name)
        save_household(folder, replace(
            load_household_info(folder),
            feeds=(Feed("Park & Lee LLC", "1120S - Park & Lee LLC"),)))

    registry = discover_engagements(tmp_path)

    assert [one.name for one in fed_by(registry, llc)] == ["Lee Family", "Park Family"]
    assert fed_by(registry, private_household_dir(tmp_path, "Park Family")) == []
    # The households come back whole, so the card that shows them can name
    # the folder and nothing about anybody's family.
    assert all(one.info.feeds for one in fed_by(registry, llc))


def test_a_household_or_return_folder_the_name_rule_refuses_is_a_misfit_with_the_reason(root):
    """Decision 188 (R2, R8): a folder put on disk by hand under a name the
    rule refuses - an invisible character, letters of two alphabets, a
    trailing dot - is listed with the rule's own reason and left alone:
    the constructors refuse to build a path through it, so the pass never
    reaches it, and nothing inside it is read."""
    from tracker.layout import segment_problem
    from tracker.registry import MISFIT_BAD_NAME

    make(root)
    private = root / PRIVATE_TREE
    bad_household = private / "Smith​ Family"
    (bad_household / "2025" / "1040 - Smith").mkdir(parents=True)
    ledger.path_for(bad_household).write_text("", encoding="utf-8")
    bad_return = private / "Smith Family" / "2025" / "1040 - Smіth Jr."
    bad_return.mkdir(parents=True)
    ledger.path_for(bad_return).write_text("", encoding="utf-8")

    found = discover_engagements(root)
    said = {m.path: m.sentence for m in found.misfits}

    for folder in (bad_household, bad_return):
        assert said[folder] == MISFIT_BAD_NAME.format(reason=segment_problem(folder.name)), folder
    assert [e.path.name for e in found.engagements] == ["1040 - Smith"]
    assert [h.path.name for h in found.households] == ["Smith Family"]
