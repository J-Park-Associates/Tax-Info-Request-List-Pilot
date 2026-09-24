"""The agreement checks every test in the suite pays for once.

`tracker/ledger.py` is the engagement's own record. Since decision 102 it
is the whole of the index, since decision 103 the whole of the statuses,
and since decision 104 the whole of the person's rules and the engagement's
details too - there is nothing anywhere else for it to disagree with.
Three autouse fixtures hold that honest after **every** test.

**A store of its own** (``a_store_of_its_own``). The store keeps one
connection per process and the file it would otherwise open sits beside
the settings file, which on a developer's machine is the repository.
``TRACKER_STORE`` points it at this test's own ``tmp_path`` instead, and
the connection is closed at teardown before the temporary folder goes,
because Windows will not delete a database a handle is open on. No test
can see another's rows.

**And the view agrees with the readers** (decisions 89 and 91). Wherever a
test left a view behind, the page is **drawn again from the live readers**
through ``view.render_page()`` - the one function that writes it - and the
two texts must be the same bytes. Comparing a fresh render rather than
parsing the page back is what keeps the check honest: a page showing a row
the readers do not have, or missing one they do, differs somewhere in those
bytes, while a reader written in the test would only ever check the part
somebody thought to parse. The one thing excluded is the clock: the
generated time is read out of the page's own stamp and handed back to the
render. A view ``view_state()`` does not call current is passed over,
because that is exactly what a pass reports as ``view_stale``.

**The store agrees with the record** (``the_store_agrees_with_the_record``,
decision 101, re-aimed by 102, 103 and 104). Every engagement folder under
``tmp_path`` that carries a journal is built into a store in a throwaway
database - ``rebuild_engagement()``, from the journal and nothing else -
and ``check()`` must return nothing at all. The other copy is
``ledger.replay()`` over the journal, for all three halves: the
**documents**, the **statuses** and the **rules** the edits fold to. It is
the only other copy there is, because the readers answer from these very
tables and asking them would be the store compared with itself. A journal
the reader refuses raises, which is what that test is about.

One store per test rather than one for the suite, because the claim is
about a build from nothing. This runs the store over every drop sorted,
every file a person filed, every rules edit and every ledger path the
suite has, and it is the gate each stage was built on.

**Making an engagement** (``make_engagement``) **is one call**: the
household's record where its folder has none, the return folder under its
year, the list and the details recorded through ``create_engagement()`` -
the same calls the API makes - and the scaffold on top when asked. It
takes the **clients root**, not a folder, because since decision 125 where
a return goes is the layout's answer and not a test's: a household, a
year, a return. Two returns in one household is the same call twice with
the same ``household``.

**Sorting one household's inbox** (``sort``) is the pass's own call
(``file_household_drops``) under the locks the pass holds, over whichever
returns the test names. One return is the ordinary case and reads as one
line.

**Seeding an index** (``seed_index``) **and a status**
(``seed_statuses``). A test that needs rows or statuses to exist records
them, because recording them is the only way they can exist: the helpers
append ``imported`` and ``scanned`` events under the engagement lock
through the store, which is the same call every writer in the package
makes.

Looking changes nothing: these fixtures read the record and never write in
an engagement folder.
"""
from __future__ import annotations

import datetime as dt
import shutil
import tempfile
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path

import pytest

from tracker import ledger, store, view
from tracker.filer import ensure, file_household_drops, refresh_household_readme
from tracker.households import create_household
from tracker.layout import (
    inbox_of,
    lock_order_key,
    originals_of,
    private_household_dir,
    return_dir_for,
)
from tracker.ledger import LedgerError
from tracker.locking import engagement_lock
from tracker.manifest import EngagementInfo, create_engagement
from tracker.names import propose_spellings
from tracker.records import HouseholdInfo, Person, entry_to_json, ledger_key, status_to_json
from tracker.scaffold import scaffold_engagement


@pytest.fixture(autouse=True)
def a_store_of_its_own(tmp_path):
    """Every test gets its own database, and no test leaks one into another.

    ``tracker.store`` keeps one connection per process, to the file beside
    the settings file - which on a developer's machine is the repository
    itself. A suite that used it would write every test's rows into one
    database, and the next test would read the last one's engagements.
    ``TRACKER_STORE`` is what the store reads instead, and it is pointed at
    a file under this test's own ``tmp_path``.

    Defined first in this file so it is set up before every other autouse
    fixture and torn down after all of them: the connection is closed
    before the temporary folder goes, because Windows will not delete a
    database a handle is open on. It is closed on the way in too, in case
    a test left one open to a file that no longer exists.

    A ``MonkeyPatch`` of its own, not the ``monkeypatch`` fixture: that one
    is shared with the test, and a test calling ``monkeypatch.undo()`` -
    several do, to put a patched writer back - would take this variable
    with it and point the next line at the repository's own database.

    It sets up first and tears down last, so it is also where the short
    clients roots of :func:`short_root` are cleared and removed: the
    agreement fixtures below have to still see them when they run.
    """
    patch = pytest.MonkeyPatch()
    patch.setenv(store.ENV_STORE, str(tmp_path / "app" / store.STORE_FILENAME))
    store.close()
    _ALSO_WALK.clear()
    try:
        yield
    finally:
        store.close()
        patch.undo()
        for folder in _ALSO_WALK:
            shutil.rmtree(folder, ignore_errors=True)
        _ALSO_WALK.clear()


#: Engagements the comparison passes over, by folder name, with the decision
#: that will make them agree. Empty: the fixture found nothing the writers and
#: the record disagreed about.
KNOWN_DISAGREEMENTS: dict[str, str] = {}

#: Folders outside this test's ``tmp_path`` the agreement fixtures walk too.
#: A pytest temporary folder is ninety characters before the layout starts,
#: and creation refuses a return whose deepest working copy would pass what
#: Windows will open (decision 125) - which is a refusal about the whole
#: path, so a test that creates a real catalog needs a root as short as the
#: office's. Registered here rather than moved out of the suite's sight:
#: the store and the view are held to the record inside them exactly as
#: they are under ``tmp_path``.
_ALSO_WALK: list[Path] = []


@pytest.fixture
def short_root():
    """A clients root short enough that a real request list fits inside
    what Windows will open.

    Straight in the machine's temporary folder, not under pytest's own:
    ``tmp_path`` is the test's name spelled out under two more folders,
    and even ``tmp_path_factory.mktemp`` keeps ``pytest-of-<user>/pytest-N/``
    above it - which is seventy-odd characters on a build runner whose
    account is called ``runneradmin``, and the 1040 core list went five
    characters past the limit there while it fitted on this machine. One
    short folder in the temporary directory is about what the office's own
    root costs. It is walked by the agreement fixtures and removed when
    the test ends.
    """
    import tempfile

    # Resolved, because a build runner's TEMP is the 8.3 short name
    # (``C:\Users\RUNNER~1\...``) while the recorded root is the long one,
    # and the two would not compare equal.
    root = Path(tempfile.mkdtemp(prefix="c", dir=tempfile.gettempdir())).resolve()
    _ALSO_WALK.append(root)
    return root


#: What a test's household and return are called when it does not care.
TEST_HOUSEHOLD = "Test Household"
TEST_RETURN = "1040 - Test Client"
TEST_YEAR = 2025
#: Who a test's return is for when it does not care (decision 128). Every
#: named request files only where one of this person's spellings is on the
#: page, so the suite's documents carry this name - ``named_page()`` puts
#: it there - exactly as a real W-2 carries its employee's.
TEST_CLIENT = "Test Client"
TEST_PEOPLE = (Person("taxpayer", TEST_CLIENT, propose_spellings(TEST_CLIENT, "taxpayer")),)


def named_page(text: str, who: str = TEST_CLIENT) -> str:
    """``text`` as a page addressed to somebody - the document's words with
    the name on it, which is what a real named document has.

    Every helper that drops a document into an inbox goes through this, so
    the suite's pages are pages the name tier can confirm (decision 128)
    and a test that means "a page naming nobody" says so by not using it.
    """
    return f"{text}\n{who}" if text else who


def make_engagement(root, items, info: EngagementInfo | None = None, *,
                    household: str = TEST_HOUSEHOLD, year: int = TEST_YEAR,
                    return_name: str = TEST_RETURN,
                    people: tuple[Person, ...] | None = None,
                    members: tuple[str, ...] = (), contact: str = "", link: str = "",
                    form: str = "", scaffold: bool = True) -> Path:
    """The one way a test makes a return: its household's record where the
    household has none, the return folder under its year, its record and,
    unless told not to, its scaffold. Returns the **return folder**.

    ``create_household()`` and ``create_engagement()`` are the API's own
    creates, so what a test seeds is exactly what the app would have made:
    one ``household_changed`` event carrying the whole household, one
    ``rules_changed`` event carrying the whole list and the details,
    validated on the way in. The scaffold is the folders the filer and the
    scanner need, and the README the app writes after them (decision 130);
    a test that wants only the record says ``scaffold=False``.

    A test that wants two returns in one household calls this twice with
    the same ``household`` - the second finds the household's record
    already there and leaves it alone.
    """
    root = Path(root)
    household_dir = private_household_dir(root, household)
    household_dir.mkdir(parents=True, exist_ok=True)
    if not ledger.path_for(household_dir).is_file():
        create_household(household_dir, HouseholdInfo(
            name=household, members=tuple(members), contact=contact, link=link))
    folder = return_dir_for(root, household, year, return_name)
    folder.mkdir(parents=True, exist_ok=True)
    details = info or EngagementInfo()
    # Who the return is for (decision 128). ``people=()`` is a test saying
    # "nobody is listed yet", which is a real state and parks every named
    # request; anything else, said or unsaid, is the one test person.
    if people is None:
        people = details.people or TEST_PEOPLE
    create_engagement(folder, list(items),
                      replace(details, household=household, tax_year=year,
                              return_name=return_name, people=tuple(people)),
                      form=form)
    if scaffold:
        # What the app's create does: the folders, then the README from its
        # one composer (decision 130).
        scaffold_engagement(folder)
        refresh_household_readme(household_dir)
    return folder


def root_for_a_return_of(base, length: int, *, household: str = TEST_HOUSEHOLD,
                         year: int = TEST_YEAR, return_name: str = TEST_RETURN) -> Path:
    """A clients root under ``base`` whose return folder is exactly
    ``length`` characters (decision 131).

    The room a return has is arithmetic on the whole path, so a claim about
    it is made at a known length rather than at whatever the machine's
    temporary folder happens to spend: one folder of padding is added under
    ``base`` to reach it. A machine whose ``base`` is already longer than
    the claim can use says so by name and skips.
    """
    base = Path(base)
    below = len(str(return_dir_for(Path("r"), household, year, return_name))) - 1
    pad = length - below - len(str(base)) - 1
    if pad < 1:
        pytest.skip(f"{base} is too long to make a return folder of {length} characters under it")
    return base / ("r" * pad)


def sort_all(returns, *, home=None, today=None, dry_run: bool = False):
    """One pass of the household's sort over these returns, answering for
    every one of them: the mapping ``file_household_drops`` returns.

    One inbox feeds them all (decision 125), so one call is the whole
    sort - a second would find nothing left to do. The first return's
    household is the one whose inbox is sorted; ``home`` names that
    household's **own** returns when the list also holds returns it feeds
    (decision 129) - handed down as the two lists the sort takes since
    decision 132, own and fed, in the order they are listed here - and
    the locks are taken in the one global order, as the pass takes them.
    """
    folders = [Path(one) for one in returns]
    own = folders if home is None else [one for one in folders if one in set(map(Path, home))]
    with ExitStack() as locks:
        if not dry_run:
            for folder in sorted(folders, key=lock_order_key):
                locks.enter_context(engagement_lock(folder))
        return file_household_drops(
            inbox_of(folders[0]), originals_of(folders[0]),
            own=own, fed=[one for one in folders if one not in own],
            today=today, dry_run=dry_run,
        )


def sort(engagement, *, returns=None, home=None, today=None, dry_run: bool = False):
    """Sort one household's inbox the way a pass does, and answer for
    ``engagement``.

    The pass takes every open return's lock before anything is read
    (decision 125), so this does too; ``returns`` names the household's
    returns when a test has more than one, and one return is the ordinary
    case. A dry run takes no lock, as the pass takes none.
    """
    engagement = Path(engagement)
    folders = returns if returns is not None else [engagement]
    return sort_all(folders, home=home, today=today, dry_run=dry_run)[engagement]


def _check_view(engagement_dir) -> None:
    """The view a test left behind is the page the readers draw now.

    **Drawn again and compared whole**, rather than parsed back: the page
    is rendered from the live readers through ``view.render_page()`` - the
    one function ``write_view()`` writes - and the two texts must be the
    same bytes. A page showing a row the readers do not have, missing one
    they do, or showing a different cell of one, differs somewhere in those
    bytes and fails here; a test-side HTML reader would only ever check the
    part somebody thought to parse. The generated time is not re-invented:
    it is read back out of the page's own stamp and handed to the render,
    so the only thing excluded from the comparison is the clock.
    """
    name = engagement_dir.name
    if view.view_state(engagement_dir) != view.CURRENT:
        return          # behind: the replace did not land, which is view_stale
    path = view.path_for(engagement_dir)
    stamp = view.read_stamp(engagement_dir)
    assert stamp is not None, f"{name}: the view carries no stamp"
    drawn = view.render_page(
        engagement_dir, now=dt.datetime.fromisoformat(stamp[view.LABEL_GENERATED])
    )
    assert drawn == path.read_text(encoding="utf-8"), (
        f"{name}: the view is not the page the readers draw now"
    )


@pytest.fixture(autouse=True)
def the_view_agrees_with_the_readers(tmp_path):
    """After every test: every view the test left behind is the page the
    readers draw now.

    Its other half - the record's statuses against the scanner columns a
    workbook used to carry - went with those columns in decision 103.
    There is no second copy of a status to disagree with any more, and
    what took its place is the store fixture below, which holds all three
    halves of the store to the journal.
    """
    yield
    for root in (tmp_path, *_ALSO_WALK):
        for path in sorted(root.rglob(view.VIEW_FILENAME)):
            if path.parent.name not in KNOWN_DISAGREEMENTS:
                _check_view(path.parent)


def _store_check(root, engagement_dir, conn) -> None:
    """Build one engagement into the store, from its journal alone, and
    hold it to the record."""
    try:
        store.rebuild_engagement(conn, root, engagement_dir)
    except LedgerError:
        return          # a journal the reader refuses is what that test is about
    said = store.check(conn, root, engagement_dir)
    assert said == [], "; ".join(said)


@pytest.fixture(autouse=True)
def the_store_agrees_with_the_record(tmp_path):
    """After every test: a store built from the journal alone, for every
    engagement the test left behind, says what the journal says."""
    yield
    for root in (tmp_path, *_ALSO_WALK):
        folders = sorted({path.parent for path in root.rglob(ledger.LEDGER_FILENAME)})
        if not folders:
            continue
        with tempfile.TemporaryDirectory() as scratch:
            conn = store.open(Path(scratch) / store.STORE_FILENAME)
            try:
                for folder in folders:
                    _store_check(root, folder, conn)
            finally:
                conn.close()


def seed_index(engagement_dir, entries):
    """Put ``entries`` in the engagement's record, the way a pass would.

    The one way a test seeds an index. There is no workbook to write any
    more, so a test that wants rows to exist records them: ``imported``
    events, under the engagement lock, through the store - the same call
    every writer in the package makes, so a seeded engagement is
    indistinguishable from one a pass left behind. Returns the entries, so
    a test can seed and keep them in one line.
    """
    engagement_dir = Path(engagement_dir)
    entries = list(entries)
    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        store.record(store.connect(), engagement_dir, *[
            ledger.new(ledger.IMPORTED, **{ledger.KEY_KEY: ledger_key(entry),
                                           ledger.ROW_KEY: entry_to_json(entry)})
            for entry in entries
        ])
    return entries


def seed_statuses(engagement_dir, updates):
    """Put ``updates`` in the engagement's record, the way a scan would.

    The one way a test seeds a status. There are no scanner columns to
    write any more (decision 103), so a test that wants a row to be
    Received records it: one ``scanned`` event, under the engagement
    lock, through the store - the same call ``tracker.scanner`` makes.
    Returns the updates, so a test can seed and keep them in one line.
    """
    engagement_dir = Path(engagement_dir)
    updates = dict(updates)
    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        store.record(store.connect(), engagement_dir, ledger.new(
            ledger.SCANNED,
            **{ledger.STATUSES_KEY: {i: status_to_json(u) for i, u in updates.items()}},
        ))
    return updates
