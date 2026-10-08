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
import os

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


def test_a_folder_whose_name_disagrees_with_its_record_pauses_its_household(root):
    """Decision 188 (R6) overrules "the record wins": the folder is the
    identity and the record's labels are a claim, and a claim that
    disagrees pauses the whole household - a renamed return folder, a
    renamed household folder, a year folder renamed (with its own
    sentence) - and nothing is ever renamed back."""
    from tracker.households import HOUSEHOLD_PAUSED, HOUSEHOLD_PAUSED_YEAR

    engagement = make(root, year=2025)
    make(root, household="Jones Family", name="1040 - Jones")
    household = private_household_dir(root, "Smith Family")
    assert discover_engagements(root).paused == {}

    (household / "2025").rename(household / "2027")             # a year folder, renamed
    moved = household / "2027" / "1040 - Smith"
    found = discover_engagements(root)
    assert found.paused == {household: HOUSEHOLD_PAUSED_YEAR}
    [smith] = [e for e in found.engagements if e.path == moved]
    assert smith.problem == "" and smith.tax_year == 2025        # still an engagement
    assert smith.warning == ""
    assert moved.is_dir()                                        # nothing was renamed

    (household / "2027").rename(household / "2025")
    (household / "2025" / "1040 - Smith").rename(household / "2025" / "1040 - Smyth")
    assert discover_engagements(root).paused == {household: HOUSEHOLD_PAUSED}
    (household / "2025" / "1040 - Smyth").rename(engagement)
    # Case alone, or a look-alike, is not a disagreement: one key.
    (household / "2025" / "1040 - Smith").rename(household / "2025" / "1040 - SMITH")
    assert discover_engagements(root).paused == {}


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
    assert "Folders the app leaves alone (1)" in printed
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
    said = {os.path.normcase(m.path): m.sentence for m in found.misfits}

    # On Windows the file system itself refuses some of these names: it
    # drops a trailing dot or space (``Jr.`` is made as ``Jr``), and will
    # not make a device name at all. So the claim is made of each folder as
    # it actually exists on the disk, named as the disk names it - every
    # one of them, and each still refused by the rule for what it is.
    on_disk = [one for folder in (bad_household, bad_return) for one in folder.parent.iterdir()
               if os.path.normcase(one.name) in {os.path.normcase(folder.name),
                                                 os.path.normcase(folder.name.rstrip(". "))}]
    assert len(on_disk) == 2, on_disk
    for folder in on_disk:
        reason = segment_problem(folder.name)
        assert reason is not None, folder
        assert said[os.path.normcase(folder)] == MISFIT_BAD_NAME.format(reason=reason), folder
    assert [e.path.name for e in found.engagements] == ["1040 - Smith"]
    assert [h.path.name for h in found.households] == ["Smith Family"]


def test_a_client_folder_with_no_record_is_listed_by_name_only(root, monkeypatch):
    """Decision 188 (R8, T12): the client tree's first level is listed by
    name, and a client folder no household owns is a misfit with its own
    sentence - while nothing under the client tree is opened, or even
    asked about: the walk never walks it."""
    import builtins
    import os

    from tracker.layout import CLIENTS_TREE
    from tracker.registry import MISFIT_CLIENT_NO_RECORD

    make(root, scaffold=True)
    stray = root / CLIENTS_TREE / "Nobody Family"
    (stray / "2025").mkdir(parents=True)
    (stray / "2025" / "w2.pdf").write_bytes(b"%PDF-1.4 a client's own file")
    (root / CLIENTS_TREE / ".tmp.driveupload").mkdir()
    clients = str(root / CLIENTS_TREE)
    touched: list[str] = []
    real_stat, real_open = os.stat, builtins.open

    def watching_stat(path, *args, **kwargs):
        if str(path).startswith(clients + os.sep):
            touched.append(str(path))
        return real_stat(path, *args, **kwargs)

    def watching_open(path, *args, **kwargs):
        if str(path).startswith(clients + os.sep):
            touched.append(str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", watching_stat)
    monkeypatch.setattr(builtins, "open", watching_open)
    found = discover_engagements(root)
    monkeypatch.undo()

    said = {m.path: m.sentence for m in found.misfits}
    assert said == {stray: MISFIT_CLIENT_NO_RECORD}
    assert touched == []


def test_a_client_folder_that_only_looks_like_a_households_is_still_listed(root):
    """The re-check of decision 188 (R1), correcting the review's S5: a
    household's client folder is the one the file system takes for its
    own name (``os.path.normcase``). A sibling that only reads as it by the
    comparison key - ``P\u0430rk`` with a Cyrillic a beside ``Park``, a
    second space - is another folder: listed as a look-alike, never adopted,
    and nothing in it is read. A folder of another name is listed as before."""
    import os

    from tracker.layout import CLIENTS_TREE, INBOX_DIR_NAME
    from tracker.registry import MISFIT_CLIENT_LOOK_ALIKE, MISFIT_CLIENT_NO_RECORD

    make(root, household="Park", scaffold=True)
    clients = root / CLIENTS_TREE
    for sibling in ("P\u0430rk", "Park  Old", "Lee"):
        (clients / sibling / INBOX_DIR_NAME).mkdir(parents=True)
        (clients / sibling / INBOX_DIR_NAME / "w2.pdf").write_bytes(b"%PDF-1.4 an upload")
    said = {m.path.name: m.sentence for m in discover_engagements(root).misfits}
    assert "Park" not in said
    assert said["P\u0430rk"] == MISFIT_CLIENT_LOOK_ALIKE.format(household="Park")
    assert said["Lee"] == MISFIT_CLIENT_NO_RECORD
    assert "Park  Old" in said
    if os.name == "nt":
        (clients / "Park").rename(clients / "PARK")
        assert "PARK" not in {m.path.name for m in discover_engagements(root).misfits}


# ------------------------------------ the households a feed names (192) ----


def test_households_named_finds_a_feed_exactly_as_the_walk_does(root):
    """Decision 192 (R9): the card resolves a feed over the households the
    feed list names, and over those it must resolve exactly as the pass
    does over the whole practice - a prior rolled forward, two open years,
    a spelling of the name that is not the folder's, two folders claiming
    one household, a folder the name rule refuses, a record in the old
    layout and a household that is not there at all."""
    import shutil

    from tracker.households import resolve_feeds
    from tracker.records import Feed
    from tracker.registry import households_named

    asker = make(root, household="Asker Family", name="1040 - Asker").parent.parent
    prior = make(root, household="Park & Lee LLC", year=2024, name="1120S - Park & Lee LLC")
    make(root, household="Park & Lee LLC", year=2025, name="1120S - Park & Lee LLC",
         info=EngagementInfo(rolled_from=str(prior.resolve())))
    make(root, household="Two Years", year=2024, name="1040 - Two")
    make(root, household="Two Years", year=2025, name="1040 - Two")
    make(root, household="Lee Family", name="1040 - Sam Lee")
    private = root / PRIVATE_TREE
    # A copy of a household under a name its key cannot tell apart.
    shutil.copytree(private / "Lee Family", private / "Lee Fami1y")
    make(root, household="Smith Family", name="1040 - Smith")
    bad = private / "Smith​ Family"
    (bad / "2025" / "1040 - Smith").mkdir(parents=True)
    ledger.path_for(bad).write_text("", encoding="utf-8")
    misplaced = private / "Old Client 2024"
    misplaced.mkdir()
    ledger.path_for(misplaced).write_text("", encoding="utf-8")
    make(root, household="Unasked Family", name="1040 - Unasked")

    feeds = [Feed("Park & Lee LLC", "1120S - Park & Lee LLC"),
             Feed("PARK & LEE LLC", "1120S - Park & Lee LLC"),
             Feed("Two Years", "1040 - Two"),
             Feed("Lee Family", "1040 - Sam Lee"),
             Feed("Smith Family", "1040 - Smith"),
             Feed("Old Client 2024", "1040 - Old"),
             Feed("Nobody Family", "1040 - Nobody")]
    practice = discover_engagements(root)

    def said(registry, feed):
        found, sentences = resolve_feeds(asker, [feed], 2025, registry)
        return [one.path for one in found], sentences

    resolved = 0
    for feed in feeds:
        named = households_named(private, [feed.household])
        assert said(named, feed) == said(practice, feed), feed
        resolved += bool(said(named, feed)[0])
    # The LLC by either spelling, Smith Family past its refused look-alike,
    # and Lee Family, whose copy the pass stops but the resolver does not see.
    assert resolved == 4
    both = households_named(private, ["Lee Family"])
    assert sorted(one.name for one in both.households) == ["Lee Fami1y", "Lee Family"]


def test_households_named_reads_no_household_it_was_not_asked_for(root, monkeypatch):
    """Decision 192: the card's feed costs the households it names and no
    other - no walk of the practice and no journal read outside them."""
    from pathlib import Path

    from tracker import registry
    from tracker.registry import households_named

    llc = make(root, household="Park & Lee LLC", name="1120S - Park & Lee LLC")
    make(root, household="Kim Household", name="1040 - Dana Kim")
    make(root, household="Smith Family", name="1040 - Smith")
    walked: list[Path] = []
    real_walk = registry._walk_root
    monkeypatch.setattr(registry, "_walk_root", lambda one: walked.append(one) or real_walk(one))
    read: list[Path] = []
    real_read = Path.read_bytes

    def counting(self):
        if self.name == ledger.LEDGER_FILENAME:
            read.append(Path(self))
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", counting)

    found = households_named(root / PRIVATE_TREE, ["Park & Lee LLC"])

    assert [one.path for one in found.engagements] == [llc]
    assert walked == []
    household = llc.parent.parent
    assert read and ledger.path_for(household) in read
    assert all(household in one.parents or one.parent == household for one in read), read


def test_a_folder_that_cannot_be_listed_is_said_by_class_never_by_its_text(root, monkeypatch):
    # Decision 193 (security principle 7): the operating system's text
    # names the folder, and the misfit's sentence reaches the app, the page
    # and the run log - so it carries the class and the code only.
    import errno
    from pathlib import Path

    make(root, household="Smith Family")
    denied = private_household_dir(root, "Smith Family")
    real = Path.iterdir

    def refuse(self):
        if self == denied:
            raise PermissionError(errno.EACCES, "Permission denied", str(self))
        return real(self)

    monkeypatch.setattr(Path, "iterdir", refuse)
    registry = discover_engagements(root)
    said = next(m.sentence for m in registry.misfits if m.path == denied)
    assert said == UNLISTED.format(error="PermissionError (EACCES)")
    assert "Permission denied" not in said and str(denied) not in said


def test_a_root_whose_only_household_lost_its_record_says_restore_never_nothing_found(tmp_path):
    """Decision 185's port: a household whose record is gone is something
    found. A root holding only it is discovered, the household stopped with
    the sentence that says restore it - never "is this the right folder?"."""
    from tracker.registry import HOUSEHOLD_RECORD_MISSING

    root = tmp_path / "root"
    folder = make_engagement(root, [RequestItem(identifier="A01", document="W-2")], scaffold=False)
    household = private_household_dir(root, TEST_HOUSEHOLD)
    ledger.path_for(household).unlink()

    registry = discover_engagements(root)
    said = HOUSEHOLD_RECORD_MISSING.format(folder=TEST_HOUSEHOLD)
    assert registry.stopped == {household: said}
    assert [(one.path, one.problem) for one in registry.engagements] == [(folder, said)]


# ---- P208: the stopped households, without reading a return -------------

def _a_firm_with_every_kind_of_stop(root):
    """A household copied whole (two folders, one record name: two claims),
    one whose record is gone, one whose record is a return's (a misfit,
    never a household), and households with nothing wrong."""
    import shutil

    make(root, household="Park Family", name="1040 - Park")
    make(root, household="Lee Family", name="1040 - Lee")
    make(root, household="Kim Family", name="1040 - Kim")
    ortiz = make(root, household="Ortiz Family", name="1040 - Ortiz")
    shutil.copytree(private_household_dir(root, "Park Family"), private_household_dir(root, "Park Family (1)"))
    ledger.path_for(private_household_dir(root, "Lee Family")).unlink()
    # A household folder holding a return's record (Ortiz's, copied): kept
    # out of the households before the two claims are judged. Not named
    # "Ortiz family", which Windows would take for Ortiz's own folder.
    misplaced = private_household_dir(root, "Ortiz Family Records")
    misplaced.mkdir()
    shutil.copyfile(ledger.path_for(ortiz), ledger.path_for(misplaced))
    return root


def test_stopped_households_is_the_walks_own_answer(root):
    from tracker.registry import stopped_households

    _a_firm_with_every_kind_of_stop(root)
    registry = discover_engagements(root)
    walked = registry.stopped
    assert len(walked) == 3, "two claims stop both copies; a lost record stops its household"
    assert any(m.code == "record_misplaced" for m in registry.misfits), "the misplaced record is a misfit"
    assert stopped_households(root) == walked


def test_stopped_households_reads_no_return(root, monkeypatch):
    """At 1,000 households the walk read every return's record before New
    Return or Roll Forward could ask whether one household is stopped;
    nothing about a return decides it."""
    from tracker import registry
    from tracker.registry import stopped_households

    _a_firm_with_every_kind_of_stop(root)
    walked = discover_engagements(root).stopped

    def refuse(*args, **kwargs):
        raise AssertionError("a return was read")

    monkeypatch.setattr(registry, "engagement_from", refuse)
    monkeypatch.setattr(registry, "mark_superseded", refuse)
    assert stopped_households(root) == walked


def test_stopped_households_is_one_reading(root, monkeypatch):
    from tracker import registry, settings
    from tracker.registry import stopped_households

    make(root)
    seen = []
    real = registry.household_from

    def watched(folder):
        seen.append(settings._HOLDING)
        return real(folder)

    monkeypatch.setattr(registry, "household_from", watched)
    stopped_households(root)
    assert seen == [settings.HOLD_READING]
    assert settings._HELD is None


def test_stopped_households_of_an_empty_root_stops_nothing_and_a_missing_one_is_an_error(root, tmp_path):
    from tracker.registry import stopped_households

    assert stopped_households(root) == {}
    with pytest.raises(RegistryError):
        stopped_households(tmp_path / "not there")


def test_held_back_names_a_copied_household_without_the_whole_walk(root, monkeypatch):
    from tracker import registry
    from tracker.registry import TWO_CLAIM, held_back

    _a_firm_with_every_kind_of_stop(root)

    def refuse(*args, **kwargs):
        raise AssertionError("the whole firm was walked")

    monkeypatch.setattr(registry, "discover_engagements", refuse)
    said = held_back(private_household_dir(root, "Park Family (1)"))
    assert said == TWO_CLAIM.format(name="Park Family", a="Park Family", b="Park Family (1)")
    assert held_back(private_household_dir(root, "Kim Family")) == ""


# ---- S8b: every misfit carries a stable code (ruling 18) -----------------

def _misfit_calls():
    import ast
    from pathlib import Path

    tree = ast.parse((Path(__file__).parent.parent / "tracker" / "registry.py").read_text("utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and getattr(n.func, "id", "") == "Misfit"]


def test_a_misfit_cannot_be_built_without_a_code(tmp_path):
    from tracker.registry import Misfit

    with pytest.raises(TypeError):
        Misfit(tmp_path, "left alone")  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        Misfit(tmp_path, "left alone", "")


def test_every_misfit_the_registry_builds_names_its_code_as_a_literal():
    """Every `Misfit(` in the registry passes a non-empty string literal code
    as its third argument, so a new construction cannot slip in without one."""
    import ast

    calls = _misfit_calls()
    assert len(calls) == 12
    for call in calls:
        assert len(call.args) == 3, call.lineno
        code = call.args[2]
        assert isinstance(code, ast.Constant) and isinstance(code.value, str) and code.value, call.lineno


def test_the_misfit_codes_are_the_ones_the_app_words_in_two_title_case_words():
    from tracker import api

    codes = {c.args[2].value for c in _misfit_calls()}
    # Every code has its words (ruling 18a: "Bad Year" for not_a_year).
    reasons = api._vocab()["screen"]["misfits"]["reasons"]
    assert set(reasons) == codes
    assert reasons["not_a_year"] == "Bad Year"
    for phrase in reasons.values():
        assert len(phrase.split()) == 2, phrase
        assert phrase == phrase.title(), phrase


# ------------------------------------ one answer, asked faster (P119) ----

def _prior_as_every_pair_compared(candidate, index, engagements):
    """The rule ``_prior_of`` was before P119, word for word: every readable
    return resolved against the Rolled From, pair by pair."""
    from pathlib import Path

    from tracker import layout

    def same(a, b):
        try:
            return Path(a).resolve() == b.resolve()
        except OSError:
            return False

    readable = [(position, prior) for position, prior in enumerate(engagements)
                if position != index and not prior.problem]
    for position, prior in readable:
        if same(candidate.rolled_from, prior.path):
            return position
    tails = {position: layout.shared_tail(candidate.rolled_from, prior.path) for position, prior in readable}
    if not tails:
        return None
    longest = max(tails.values())
    if longest < layout.ROLLED_FROM_TAIL:
        return None
    matches = [position for position, tail in tails.items() if tail == longest]
    return matches[0] if len(matches) == 1 else None


def test_the_rolled_forward_prior_is_found_as_every_pair_compared_found_it(root, tmp_path):
    """P119: each return's folder is resolved once, not once per pair (7 s at
    150 rolled-forward returns, growing with the square). The answer is the
    old one for every candidate: an exact folder, the first in walk order; a
    tail match after the root moved; a tie deciding nothing; a problem
    return never the prior; a Rolled From naming itself, or nothing."""
    from tracker.registry import _prior_of, _Priors, engagement_from

    a = make(root, household="Park Family", year=2025, name="1040 - John Park")
    make(root, household="Park Family", year=2026, name="1040 - John Park",
         info=EngagementInfo(rolled_from=str(a.resolve())))
    b = make(root, household="Lee Family", year=2025, name="1040 - Ann Lee")
    make(root, household="Lee Family", year=2026, name="1040 - Ann Lee",
         info=EngagementInfo(rolled_from=str(tmp_path / "Old root" / b.relative_to(root))))
    make(root, household="Kim Family", year=2025, name="1040 - Kim")
    make(root, household="Kim Family", year=2026, name="1040 - Kim",
         info=EngagementInfo(rolled_from="1040 - Kim"))
    found = [engagement_from(p) for p in engagement_dirs(root)]
    found.append(Engagement(path=root / "gone", problem="could not be listed"))
    found.append(Engagement(path=root / "twin", info=EngagementInfo(rolled_from=str(root / "gone"))))
    found.append(Engagement(path=a, info=EngagementInfo(rolled_from=str(a))))   # itself, once more
    priors = _Priors(found)
    for index, candidate in enumerate(found):
        if candidate.rolled_from:
            assert _prior_of(candidate, index, priors) == _prior_as_every_pair_compared(candidate, index, found)


def test_two_claims_are_grouped_as_every_pair_compared_grouped_them(root):
    """P119: households sharing a name key are joined through the first
    household holding it, not pair by pair - the same groups, listed in walk
    order, so each sentence names the same folders."""
    from tracker.layout import name_key
    from tracker.records import HouseholdInfo
    from tracker.registry import TWO_CLAIM, Household, _two_claims

    households = [Household(path=root / name, info=HouseholdInfo(name=claimed))
                  for name, claimed in [("Park", ""), ("Lee", "Park"), ("Kim", ""), ("Kim 2", "Lee"),
                                        ("Cho", "Cho Family"), ("Cho Family", ""), ("Moon", "")]]
    keys = [{name_key(one.path.name)} | ({name_key(one.info.name)} if one.info.name else set())
            for one in households]
    together = {}
    for i, one in enumerate(households):
        group = {i}
        while True:
            grown = {j for j in range(len(households)) if any(keys[j] & keys[k] for k in group)}
            if grown == group:
                break
            group = grown
        together[one.path] = [households[j] for j in sorted(group)]
    expected = {path: TWO_CLAIM.format(name=group[0].info.name or group[0].path.name, a=group[0].path.name,
                                       b="`, `".join(other.path.name for other in group[1:]))
                for path, group in together.items() if len(group) > 1}
    assert _two_claims(households) == expected
    assert set(expected) == {root / name for name in ("Park", "Lee", "Kim 2", "Cho", "Cho Family")}


def test_household_positions_are_the_walks_households_in_the_walks_order(root):
    """P120's cache asks the households the practice walk asks, in its order,
    and says when it cannot be sure (no private tree)."""
    from tracker.registry import household_positions

    for name in ("lee Family", "Park Family", "Kim Family"):
        make(root, household=name)
    # The review's SHOULD-1: a folder the walk passes over is no household
    # position; one whose name the layout refuses is listed, as the walk
    # lists it (a misfit).
    (root / PRIVATE_TREE / "_Archive").mkdir()
    (root / PRIVATE_TREE / "~$lock").mkdir()
    (root / PRIVATE_TREE / "2019").mkdir()
    private, folders = household_positions(root)
    assert private == root / PRIVATE_TREE
    assert [f.name for f in folders] == ["2019", "Kim Family", "lee Family", "Park Family"]
    folders = [f for f in folders if f.name != "2019"]
    walked = []
    for one in discover_engagements(root).households:
        walked.append(one.path)
    assert folders == walked
    assert household_positions(root / "nothing here") is None
    empty = root.parent / "Empty root"
    empty.mkdir()
    assert household_positions(empty) is None


def test_a_legacy_folder_is_still_found_by_whether_it_has_rules(root, monkeypatch):
    """P219: discovery asks whether a record has rules, not for its rules -
    and a record with none beside the old workbook is still the legacy
    folder, while one with rules is an engagement like any other."""
    from tracker import store

    make(root)
    year = private_household_dir(root, "Smith Family") / "2025"
    half = year / "1065 - Half Set Up"
    half.mkdir()
    ledger.path_for(half).write_text("", encoding="utf-8")
    (half / LEGACY_MANIFEST_FILENAME).write_bytes(b"PK")
    (year / "1040 - Smith" / LEGACY_MANIFEST_FILENAME).write_bytes(b"PK")

    def parsed(*_args, **_kwargs):
        raise AssertionError("discovery parsed every rule to learn whether there was one")

    monkeypatch.setattr(store, "rules", parsed)
    listed = {e.path.name: e for e in discover_engagements(root).engagements}
    assert listed["1065 - Half Set Up"].problem == LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME)
    assert not listed["1040 - Smith"].problem
