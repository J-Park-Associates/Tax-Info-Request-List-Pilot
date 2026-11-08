"""Tests for tracker/runner.py: the pass over a household and the routes that feed it.

The household pass (decision 125), the household routes (decision 129), what a household has received (decision 130),
the room a return has (decision 131), the bounded household (decision 189) and one door for a folder's name (decision 188).

Split from ``tests/test_runner.py`` by SPEC-architecture-p5 P5.14 (E-3), by the banners the old file kept its
sections under, each test moved byte for byte with its section, so that each family runs as its own process
(Jason, 2026-09-29) and an affected-tests run reaches only the family a change touched. The map owns this file
as ``tracker/runner.py``'s test by its name (decision P350). What more than one family reads is
``tests/passes.py``'s, because a test file may not import another (``tests/test_suite_shape.py``).
"""

import datetime as dt
import html
from pathlib import Path

import pytest

import tracker.runner as runner_module
from tests import passes
from tests.builders import make_engagement, seed_index
from tests.passes import (
    FRIDAY,
    SATURDAY,
    _page,
    _the_scheduled_job,
    _three_households,
    _two_households,
    a_pass,
    build_engagement,
    drafted_events,
    edit_details,
    households_in_order,
    pass_on,
)
from tests.samples import DEMO_ITEMS, SCRATCH_PEOPLE, YEAR
from tracker import ledger, run_log, status_page, store
from tracker.index import NEEDS_REVIEW, read_index
from tracker.layout import household_of, inbox_of
from tracker.manifest import EngagementInfo, RequestItem, load_engagement_info
from tracker.records import IndexEntry
from tracker.registry import discover_engagements, engagement_from
from tracker.reminder import DRAFT_FILENAME
from tracker.run_log import log_path
from tracker.runner import (
    CODE_PASS_DID_NOT_FINISH,
    LOG_FILENAME,
    REMINDERS_NEVER,
    SETTINGS_FLAG,
    STATUS_PAGE_FILENAME,
    RunReport,
    append_log,
    last_drafted,
    main,
    run_household,
    run_registry,
    write_status_page,
)
from tracker.scaffold import PREPARED_DIR_NAME
from tracker.status_page import STATUS_HELD

#: The sample pile, built once per session: a fixture of ``tests/passes.py``, named here
#: so every claim below can ask for it.
samples = passes.samples

#: A fixture of ``tests/passes.py``, named here so every claim below can ask for it.
stamped_on = passes.stamped_on


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


def test_ignored_names_are_counted_once_per_pass(tmp_path, samples, capsys):
    """The files the sort leaves alone by name - a system file, an Office
    lock file (a client's own ``~$W2.pdf`` among them), anything under a
    sync client's staging folder - are counted once per household per pass
    (decision 190): one line in the run's report and on the practice page,
    a count and never a name. An unfinished transfer is named as syncing
    already, so it is not counted twice."""
    from tracker.run_log import IGNORED_NOTE
    from tracker.status_page import STATUS_IGNORED_HEADING
    # A root of its own: tmp_path holds the suite's app folder (decision 185).
    root = tmp_path / "root"

    personal, business = a_household(root, samples, drops=(f"W-2 John Smith {YEAR}.pdf",))
    inbox = inbox_of(personal.path)
    junk = ["desktop.ini", "Thumbs.db", "~$W2 for the year.pdf"]
    for name in junk:
        (inbox / name).write_bytes(b"left alone")
    staging = inbox / ".tmp.drivedownload"
    staging.mkdir()
    (staging / "part-of-a-statement.pdf").write_bytes(b"left alone")
    (inbox / "bank statement.pdf.driveupload").write_bytes(b"still coming")

    assert main([str(root), "--date", FRIDAY.isoformat()]) == 0
    said = capsys.readouterr().out

    line = IGNORED_NOTE.format(n=4)
    assert said.count(line) == 1, said
    page = (root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
    assert STATUS_IGNORED_HEADING in page and page.count(line) == 1
    for name in [*junk, "part-of-a-statement.pdf"]:
        assert html.escape(name) not in page and name not in said, name
    assert (inbox / "~$W2 for the year.pdf").read_bytes() == b"left alone"


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
    # Said where a person looks, the practice page's cell, and counted in
    # the run log, which names nothing (decision 186).
    logged = append_log(tmp_path / LOG_FILENAME,
                        RunReport(today=SATURDAY, runs=runs)).read_text(encoding="utf-8")
    assert f" held={len(runs)} " in logged and said not in logged
    page = html.unescape(write_status_page(tmp_path, RunReport(today=SATURDAY, runs=runs))
                         .read_text(encoding="utf-8"))
    assert f"<td>{STATUS_HELD.format(n=1)}</td>" in page


def test_the_pass_that_sorts_the_inbox_drafts_the_held_reminder_the_same_day(
        tmp_path, samples, stamped_on, monkeypatch):
    import tracker.actions as actions_module
    import tracker.filer as filer_module
    import tracker.intents as intents_module
    from tracker import copies
    from tracker.layout import README_NAME
    from tracker.reminder import INBOX_HOLD

    engagement = build_engagement(tmp_path, samples)
    inbox = inbox_of(engagement.path)
    real = copies._move_whole

    def refused_once(source, target, *, within):
        if Path(source).parent == inbox:
            raise PermissionError("held open by the sync client")
        return real(source, target, within=within)

    # The draft day's first pass: the drop cannot be moved, so it fails to
    # sort and stays in the inbox - and the reminder waits for it.
    for module in (filer_module, intents_module, actions_module):
        monkeypatch.setattr(module, "_move_whole", refused_once)
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

    return api_module.state(Path(engagement))


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
    from tracker.index import NEEDS_REVIEW

    personal, [fed] = a_fed_household(tmp_path, samples)
    text_pdf(inbox_of(personal.path) / "trial balance.pdf",
             [f"Trial balance as of December 31 {YEAR}", SCRATCH_CLIENT], style="padded")
    household = household_of(personal.path)

    [run] = run_household(household, [personal], today=FRIDAY, reminders=REMINDERS_NEVER,
                          registry=discover_engagements(tmp_path))

    assert run.ok and run.filed == 0 and run.review == 1
    assert read_index(fed.path) == []
    [row] = read_index(personal.path)
    assert row.decision == NEEDS_REVIEW and row.code == reasons.NAMED_ACROSS_HOUSEHOLDS.code
    assert row.waiting_for.identifiers == ("B01",)
    assert not any(fed.label in warning for warning in run.warnings)


def _click(personal, fed, today=FRIDAY):
    """The one click (decision 204) as the app makes it: the waiting row
    handed over, the taking return re-scanned and both READMEs rewritten."""
    from tracker.filer import hand_over
    from tracker.index import NEEDS_REVIEW
    from tracker.readme_ack import refresh_household_readme
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
    from tracker.index import FILED, NEEDS_REVIEW
    from tracker.scaffold import README_NAME

    personal, [fed] = a_fed_household(tmp_path, samples)
    text_pdf(inbox_of(personal.path) / "trial balance.pdf",
             [f"Trial balance as of December 31 {YEAR}", SCRATCH_CLIENT], style="padded")
    text_pdf(inbox_of(personal.path) / "unnamed w2.pdf",
             [f"Form W-2 Wage and Tax Statement {YEAR}"], style="padded")
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

    from tests.samples import photo
    from tracker.index import FILED
    from tracker.records import entry_to_json
    from tracker.run_log import SLOW_READING_NOTE

    personal, business = a_household(tmp_path, samples,
                                      drops=(f"W-2 John Smith {YEAR}.pdf",))
    photo(inbox_of(personal.path) / "A photo.png", words="Trial balance")
    monkeypatch.setattr(run_log, "SLOW_READING_SECONDS", 0.05)
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
    from tracker.index import FILED
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
    from tracker.index import FILED
    from tracker.manifest import load_manifest
    from tracker.scaffold import (
        README_NAME,
        RECEIVED_HEADING,
        UNDER_REVIEW_HEADING,
        day_text,
    )

    personal, [fed] = a_fed_household(tmp_path, samples)
    text_pdf(inbox_of(personal.path) / "trial balance.pdf",
             [f"Trial balance as of December 31 {YEAR}", SCRATCH_CLIENT], style="padded")
    text_pdf(inbox_of(personal.path) / "unnamed w2.pdf",
             [f"Form W-2 Wage and Tax Statement {YEAR}"], style="padded")
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


def test_a_return_short_of_room_files_everything_and_is_not_warned(tmp_path, path_setting):
    """Nine characters short: the W-2 files all the same, under a name cut
    to fit - and the pass does **not** warn (the lead's L-1 on decision
    131): nothing in the run's warnings. With a reader's 218 for
    spreadsheets every 1040 at the firm's root would warn every pass, and a
    warning that is always on is a warning nobody reads."""
    from tests.builders import OVER, TIGHT_PERIOD, drop, tight_return

    engagement = tight_return(tmp_path, OVER)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    [run] = _a_pass_over(engagement)

    assert run.warnings == [] and not run.skipped and not run.error
    assert run.filed == 1
    [entry] = read_index(engagement)
    assert entry.prepared_location.endswith(f"/A01 - W-2 Wage S - {TIGHT_PERIOD}.pdf")


def test_a_return_with_requests_that_cannot_receive_says_how_many(tmp_path, path_setting):
    """A request that Prepared leaves no room for even its shortest name is
    counted and said: a document for it parks until the root is shorter."""
    from tests.builders import ROOM_ITEMS, no_room_return, root_for_a_return_of, with_the_long_period
    from tracker.copies import ROOM_PARKS, room_for
    from tracker.manifest import load_manifest

    engagement = make_engagement(root_for_a_return_of(tmp_path, no_room_return()),
                                 [with_the_long_period(ROOM_ITEMS[0])])   # Prepared: 216
    room = room_for(engagement, load_manifest(engagement))
    assert room.parks == 1 and room.short > 0

    [run] = _a_pass_over(engagement)

    assert run.warnings == [ROOM_PARKS.format(count=1)]       # L-1: the short-of-room figure is no warning
    assert not run.skipped and not run.error


def test_a_household_with_no_room_for_a_review_copy_is_skipped_whole_before_anything_is_read(
    tmp_path, monkeypatch, path_setting,
):
    """A return whose review folder leaves no room for even ``x (99).pdf``
    stops its household: every working return carries HOUSEHOLD_NO_ROOM,
    the inbox is untouched, no lock is taken, and nothing is scaffolded,
    scanned, drafted or drawn - the held-lock shape."""
    from tests.builders import ROOM_ITEMS, drop, floor_return, root_for_a_return_of
    from tracker.copies import HOUSEHOLD_NO_ROOM
    from tracker.layout import README_NAME, path_limit
    from tracker.locking import LOCK_FILENAME
    from tracker.page import esc
    from tracker.view import VIEW_FILENAME

    # Its floor: 223 + 38 = 261; with long paths off 207 + 27 + 26 = 260,
    # the review folder measured with the temp names written into it (P29).
    root = root_for_a_return_of(tmp_path, floor_return() + 1)
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

    said = HOUSEHOLD_NO_ROOM.format(label=run.engagement.label, length=path_limit() + 1,
                                    limit=path_limit())
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
    agree with - is refused, red, naming the repair path. The same root is
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
    from tracker.api import SCHEDULE_REPAIR_LABEL

    assert SCHEDULE_REPAIR_LABEL in str(refused.value)
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
    from tests.builders import ROOM_ITEMS

    root = tmp_path / "Clients"
    make_engagement(root, ROOM_ITEMS, return_name="1040 - One")
    make_engagement(root, ROOM_ITEMS, return_name="1040 - Two")
    registry = discover_engagements(root)
    reads = []
    real = runner_module.load_manifest
    for module in (runner_module, status_page):
        monkeypatch.setattr(module, "load_manifest", lambda folder: (reads.append(folder), real(folder))[1])

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


# ---------------------------------------------- the bounded household (189) ----


@pytest.fixture
def a_clock(monkeypatch):
    """The awake clock, held still unless a test moves it (decision 189)."""
    from tracker import reader_child

    now = [1000.0]
    monkeypatch.setattr(reader_child, "awake_clock", lambda: now[0])
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

    from tracker.index import read_index
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
    from tracker.pass_order import ORDER_HINT_UNREADABLE
    from tracker.runner import PASS_ORDER_FILENAME

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
    from tracker.pass_order import NOT_SERVED_TWICE, WHY_HELD_LOCK
    from tracker.runner import NOT_SERVED_TWICE_EXIT_CODE

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
    from tracker.pass_order import ORDER_HINT_UNREADABLE, PASS_ORDER_MAX_BYTES
    from tracker.runner import PASS_ORDER_FILENAME

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
    root_log = log_path()
    root_log.parent.mkdir(parents=True)
    root_log.write_text("[2026-03-13T02:00:00] pass started\n", encoding="utf-8")   # then killed

    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 0
    said = PASS_DID_NOT_FINISH.format(stamp="2026-03-13T02:00:00")
    assert said in _page(root)
    text = root_log.read_text(encoding="utf-8")
    assert said not in text and f"{CODE_PASS_DID_NOT_FINISH}=1" in text
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

    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    engagement = build_engagement(root, samples)
    (root / PRIVATE_TREE / "Test Household").rename(root / PRIVATE_TREE / "Test Home")
    inbox = root / CLIENTS_TREE / "Test Household" / "Drop files here"
    waiting = sorted(p.name for p in inbox.iterdir())

    code, said = _whole_pass(root, capsys)

    assert code == 1 and HOUSEHOLD_PAUSED in said
    assert not (root / CLIENTS_TREE / "Test Home").exists()
    assert sorted(p.name for p in inbox.iterdir()) == waiting
    assert MISFIT_CLIENT_NO_RECORD in said and engagement


def test_a_household_renamed_in_the_client_tree_stops_with_one_sentence(tmp_path, samples, capsys):
    """T7 (SPEC-162 ruling 2): a household that had a client folder - a
    recorded original rests there - whose client folder was renamed is
    stopped with the one sentence naming the folder to give back, and no
    client folder of the old name is made again."""
    from tracker.households import CLIENT_FOLDER_MISSING
    from tracker.layout import CLIENTS_TREE

    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    engagement = build_engagement(root, samples)
    _fabricated_filed_original(engagement.path, "Test Household")
    (root / CLIENTS_TREE / "Test Household").rename(root / CLIENTS_TREE / "Test Hh")

    code, said = _whole_pass(root, capsys)

    assert code == 1 and CLIENT_FOLDER_MISSING.format(name="Test Household") in said
    assert not (root / CLIENTS_TREE / "Test Household").exists()


def test_a_shared_household_whose_record_cannot_be_read_is_held_back_and_its_client_folder_is_not_remade(
        tmp_path, samples, capsys):
    """P296 (the error-handling audit's E1): a household the firm marked
    shared, whose client folder is gone and whose record has one unlinked
    line. The pass used to read the failure as "never had one" and make
    `Clients\\<name>` again, empty and unshared, while warning the record
    could not be read. Now every run of the household carries the one
    sentence that says both, under the record-unreadable code, nothing is
    filed, and no client folder is made."""
    import json
    import shutil

    from tracker.households import CLIENT_SIDE_UNKNOWN
    from tracker.layout import CLIENTS_TREE, PRIVATE_TREE
    from tracker.locking import engagement_lock
    from tracker.runner import CODE_RECORD_UNREADABLE

    root = tmp_path / "root"
    engagement = build_engagement(root, samples)
    private = root / PRIVATE_TREE / "Test Household"
    with engagement_lock(private):
        store.record(store.connect(), private, ledger.new(ledger.SHARING_CONFIRMED))
    ledger._write_raw(ledger.path_for(private), json.dumps(
        {ledger.EVENT_KEY: ledger.SHARING_CONFIRMED, ledger.AT_KEY: "2026-01-01T00:00:00Z"}
    ).encode("utf-8"))
    with pytest.raises(ledger.LedgerError) as refused:
        ledger.read_events(private)
    shutil.rmtree(root / CLIENTS_TREE / "Test Household")

    run = a_pass(engagement, today=FRIDAY, reminders=REMINDERS_NEVER)

    said = CLIENT_SIDE_UNKNOWN.format(name="Test Household", whose="the household",
                                      problem=str(refused.value))
    assert run.error == said and run.code == CODE_RECORD_UNREADABLE
    assert run.filed == 0
    assert not (root / CLIENTS_TREE / "Test Household").exists()


def test_a_new_household_is_still_scaffolded(tmp_path, capsys):
    """T8 (SPEC-162 ruling 2): a household that never had a client folder -
    nothing shared, nothing received - is laid out as it always was."""
    from tracker.layout import inbox_dir_for

    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    make_engagement(root, DEMO_ITEMS, household="New Household", people=SCRATCH_PEOPLE,
                    scaffold=False)
    code, said = _whole_pass(root, capsys)
    assert code == 0, said
    assert inbox_dir_for(root, "New Household").is_dir()


def test_two_folders_claiming_one_household_stop_both(tmp_path, samples, capsys):
    """T9 (SPEC-162 ruling 3, widened by decision 188): a copy of a
    household folder claims the household too, so both are stopped, each
    run naming both folders - and neither's inbox is sorted."""
    import shutil

    from tracker.layout import CLIENTS_TREE, PRIVATE_TREE
    from tracker.registry import TWO_CLAIM

    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    build_engagement(root, samples)
    private = root / PRIVATE_TREE
    shutil.copytree(private / "Test Household", private / "Test Household - Copy")
    inbox = root / CLIENTS_TREE / "Test Household" / "Drop files here"
    waiting = sorted(p.name for p in inbox.iterdir())

    code, said = _whole_pass(root, capsys)

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

    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    build_engagement(root, samples)
    ledger.path_for(root / PRIVATE_TREE / "Test Household").unlink()
    (root / CLIENTS_TREE / "Nobody Family").mkdir()

    code, said = _whole_pass(root, capsys)

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

    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    engagement = build_engagement(root, samples)
    engagement.path.rename(engagement.path.parent / "1040 - Someone Else")
    # Red on every pass: 1 the first time, and from the second pass the
    # not-served-twice code, which wins over 1 (decision 189).
    from tracker.runner import NOT_SERVED_TWICE_EXIT_CODE

    for expected in (1, NOT_SERVED_TWICE_EXIT_CODE):
        code, said = _whole_pass(root, capsys)
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
    from tests.builders import app_stdin
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
    # The app's own folder (the store, the checkpoint, and since decision
    # 193 the error log that 159's "checkpoint seeded" warning lands in) is
    # not a client folder: the claim is about the two trees.
    app = tmp_path / "app"

    def folders():
        return sorted(path for path in tmp_path.rglob("*") if app not in path.parents)

    before = folders()

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
    assert folders() == before


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
