"""The agreement checks every test in the suite pays for once.

`tracker/ledger.py` is the engagement's own record. Since decision 102 it
is the whole of the index, since decision 103 the whole of the statuses,
and since decision 104 the whole of the person's rules and the engagement's
details too - there is nothing anywhere else for it to disagree with.
Three autouse fixtures hold that honest after **every** test.

**An app folder of its own** (``an_app_folder_of_its_own``). The store keeps one
connection per process and the file it would otherwise open sits beside
the settings file, which on a developer's machine is the repository.
``TRACKER_STORE`` points it at this test's own ``tmp_path`` instead, and
the connection is closed at teardown before the temporary folder goes,
because Windows will not delete a database a handle is open on. No test
can see another's rows. The settings folder is ``tmp_path / "app"``, the
same folder as the store, so no test reads the checkout's ``settings.json``
(decision 185).

**And the suite can never see a real root** (decision 185). The session
points itself at a folder of its own before collection, and a tripwire
(``tests/tripwire/sitecustomize.py``), armed here and in every Python child
that inherits the suite's environment (the tripwire's docstring lists what
escapes), stops and records any reach for a place
:func:`real_places` names; any record, or any folder the session leaves in
the checkout, fails the whole session.

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
journal: ``ledger.replay()`` for the **documents** and the **rules** the
edits fold to, and the same lines folded by the store's case rule for the
**statuses** and the taught keywords (decision 136). It is
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

**Reading in the test's own process** (``reading_in_this_process``,
decision 150). The pass reads each document in a child process it can
stop, and the suite's stand-in readers - a fake OCR, a slow reader, a
reader that must never be called - are patched into the test's process,
which a child started fresh never sees. So every test reads in its own
process, and the tests about the child (``tests/test_content_check.py``,
the decision-150 section) turn the child back on.

Looking changes nothing: these fixtures read the record and never write in
an engagement folder.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path

import pytest

from tests.tripwire import sitecustomize as tripwire
from tracker import after_install, content_check, ledger, scheduling, settings, store, view
from tracker.filer import ensure, file_household_drops, refresh_household_readme
from tracker.households import create_household
from tracker.layout import (
    CLIENTS_TREE,
    PRIVATE_TREE,
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

REPO = Path(__file__).resolve().parent.parent
#: The folder, inside a test's tmp_path or the session's folder, that plays
#: "beside the app": the settings file and the store live in it. Most tests
#: that set TRACKER_SETTINGS_DIR themselves already name this one.
APP_FOLDER = "app"
TRIPWIRE_DIR = Path(__file__).resolve().parent / "tripwire"


def own_folders(patch: pytest.MonkeyPatch, folder: Path) -> None:
    """Point this process, and every child it starts, at ``folder`` for the
    settings file and the store (decision 185): the one place the suite says
    where "beside the app" is - and at :func:`data_home_for` ``folder`` for
    the data home (decision 186), never the account's own."""
    patch.setenv(settings.ENV_SETTINGS_DIR, str(folder))
    patch.setenv(store.ENV_STORE, str(folder / store.STORE_FILENAME))
    patch.setenv(settings.ENV_DATA_HOME, str(data_home_for(folder)))


def data_home_for(folder: Path) -> Path:
    """The suite's data home for the app folder ``folder``: a sibling of the
    folder that holds it (``<tmp_path>-data`` for a test's
    ``<tmp_path>/app``), never inside it - many tests make ``tmp_path``
    itself the clients root, and a root may not hold the data home
    (``settings.ROOT_HOLDS_DATA``, decision 186)."""
    holder = Path(folder).parent
    return holder.with_name(holder.name + "-data")


@pytest.fixture(autouse=True)
def an_app_folder_of_its_own(tmp_path):
    """Every test gets its own settings folder and its own database, and no
    test leaks either into another - nor reads the checkout's (decision 185).

    Both sit in ``tmp_path / "app"``, set through :func:`own_folders`, the
    one place the suite says where "beside the app" is. This is the one
    fixture that does it for a test, and it cannot be taken away: a test's
    ``monkeypatch.undo()`` restores what was there before the test, which is
    this fixture's value, never the checkout's.

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
    own_folders(patch, tmp_path / APP_FOLDER)
    # The firm's corpus is seen only by tests/test_real_corpus.py's rows,
    # which captured it at collection; no other test, and no tool a test
    # calls, reads it by accident.
    patch.delenv(settings.ENV_REAL_CORPUS, raising=False)
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


@pytest.fixture(autouse=True)
def reading_in_this_process():
    """Every test reads a document in its own process (decision 150).

    ``content_check.extract_bounded()`` reads in a child process in the
    tracker, and a child imports the reader afresh: the patches the suite
    makes to it would not be there. A ``MonkeyPatch`` of its own, like the
    store's, so a test calling ``monkeypatch.undo()`` does not turn the
    child on by accident; a test about the child turns it on with its own.
    """
    patch = pytest.MonkeyPatch()
    patch.setattr(content_check, "READ_IN_A_CHILD", False)
    try:
        yield
    finally:
        patch.undo()


#: The real answer to "is there a Task Scheduler here", for the one test
#: that asks it of the platform (decision 209).
REAL_TASK_SCHEDULER_HERE = scheduling.task_scheduler_here


def _schtasks_unfaked(command):
    raise AssertionError(f"a test reached schtasks without faking it: {command}")


@pytest.fixture(autouse=True)
def no_task_scheduler_unless_faked():
    """No test registers or deletes a real scheduled task (decision 209).

    Saving a clients root, the app's launch and Setup all run the
    after-install step, which registers the daily job on a Windows machine
    that has Task Scheduler - the Windows CI runner included. Every test
    starts on a computer with none; a test about registering says it is on
    Windows and fakes ``schtasks`` itself, and one that forgets fails here
    rather than reaching the real one. A ``MonkeyPatch`` of its own, like
    the store's, so ``monkeypatch.undo()`` in a test cannot lift it.
    """
    patch = pytest.MonkeyPatch()
    patch.setattr(scheduling, "task_scheduler_here", lambda: False)
    patch.setattr(scheduling, "_schtasks", _schtasks_unfaked)
    try:
        yield
    finally:
        patch.undo()


@pytest.fixture(autouse=True)
def no_real_test_cache_is_cleared(tmp_path_factory):
    """No test clears this checkout's own ``.pytest_cache`` (SPEC-209 R8).

    Every door of the after-install step runs its test-cache job, and the
    suite is running from that very checkout: left alone, the first test
    to save a root would remove the cache pytest is writing. The job is
    pointed at a folder that is never made; a test about the job names its
    own fabricated checkout. Its own ``MonkeyPatch``, as above."""
    patch = pytest.MonkeyPatch()
    patch.setattr(after_install, "CHECKOUT", tmp_path_factory.getbasetemp() / "no-checkout-here")
    try:
        yield
    finally:
        patch.undo()


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


#: The code page Python reads a pipe in on the firm's Windows machine,
#: whatever the machine running the suite uses.
WINDOWS_PIPE_ENCODING = "cp1252"


def app_stdin(spec) -> io.TextIOWrapper:
    """``spec`` as the tracker's stdin sees it when the app sends it (decision
    176): the UTF-8 bytes ``JSON.stringify`` and Node's pipe produce, under a
    text stream in Windows' ANSI code page. A command that reads the text
    rather than the bytes turns ``Muñoz`` into ``MuÃ±oz`` here as it would
    at the office, so every API claim in the suite is made through the
    reading the office gets.
    """
    raw = json.dumps(spec, ensure_ascii=False).encode("utf-8")
    return io.TextIOWrapper(io.BytesIO(raw), encoding=WINDOWS_PIPE_ENCODING)


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


def written_elsewhere(engagement_dir, event, host="another-machine"):
    """Put one line in a record the way the tracker on another machine
    writes it: linked to the line before, with that machine's host and the
    record's format (decision 159). The one way a test puts a line in a
    record that no writer on this machine would make - a line of the wrong
    shape, a retired name - without it reading as a hand edit."""
    _lines, _head, chain = ledger.read_with_chain(engagement_dir)
    ledger._write_line(ledger.path_for(engagement_dir), {
        **event, ledger.LINK_KEY: ledger.chain_at(chain, len(chain)), ledger.HOST_KEY: host,
        ledger.FORMAT_KEY: ledger.RECORD_FORMAT})


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


# ------------------------------------------- the suite can never see a real root ----


def real_places(repo: Path) -> tuple[tuple[str, Path], ...]:
    """Every place a real settings file, store, scratch folder or client tree
    resolves to on this machine when nothing of the suite's overrides it:
    beside the app as the checkout resolves it, and wherever the shell running
    the suite names instead. The tripwire guards each; decision 186 adds the
    data home - the account's real one, worked out with ``ENV_DATA_HOME``
    set aside (none, if this machine has none), and one the shell names."""
    from tracker.checkpoint import CHECKPOINT_FILENAME
    from tracker.progress import PASSES_DIRNAME
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.runner import AFTER_INSTALL_FILENAME, LAST_PASS_FILENAME, LOG_FILENAME, STATUS_PAGE_FILENAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME

    named = settings.settings_path()                     # the shell's, if it sets one
    with pytest.MonkeyPatch.context() as bare:
        bare.delenv(settings.ENV_SETTINGS_DIR, raising=False)
        beside = settings.settings_path()                 # the checkout's own
    places = []
    for where in dict.fromkeys((beside, named)):          # one entry when they agree
        places += [("settings file", where),
                   ("store", where.with_name(store.STORE_FILENAME)),
                   ("store's write-ahead log", where.with_name(store.STORE_WAL_FILENAME)),
                   ("store's shared memory", where.with_name(store.STORE_SHM_FILENAME)),
                   ("scheduled task file", where.with_name(SCHEDULE_XML_FILENAME)),
                   # Decision 159 writes these beside the store: the record
                   # checkpoint, the last pass's outcome, and the recovered
                   # copies of a return's lines (record-derived, like the store).
                   ("record checkpoint", where.with_name(CHECKPOINT_FILENAME)),
                   ("last-pass file", where.with_name(LAST_PASS_FILENAME)),
                   # Decision 209's note of the last after-install run, beside the store too.
                   ("after-install note", where.with_name(AFTER_INSTALL_FILENAME)),
                   ("recovered record copies", where.with_name(store.RECOVERED_DIR)),
                   # Decision 193 writes these beside the store too: the error
                   # log (its rotated copies share its name) and the passes' progress.
                   ("error log", where.with_name(settings.ERROR_LOG_FILENAME)),
                   ("passes folder", where.with_name(PASSES_DIRNAME))]
    if os.environ.get(store.ENV_STORE):
        places.append(("store", Path(os.environ[store.ENV_STORE])))
    # The data home (decision 186, SPEC-186 section 9): the real one, which
    # default_data_home() works out without ENV_DATA_HOME; a machine that has
    # none (a SettingsError) adds nothing. Then whatever the shell names.
    try:
        places.append(("data home", settings.default_data_home()))
    except settings.SettingsError:
        pass
    if os.environ.get(settings.ENV_DATA_HOME, "").strip():
        places.append(("data home", Path(os.environ[settings.ENV_DATA_HOME])))
    app = settings.app_dir()
    places += [("OCR scratch folder", app / settings.OCR_SCRATCH_DIRNAME),
               ("client tree", repo / CLIENTS_TREE),
               ("private tree", repo / PRIVATE_TREE),
               ("run log", repo / LOG_FILENAME),
               ("status page", repo / STATUS_PAGE_FILENAME),
               ("reminder draft", repo / DRAFT_FILENAME),
               ("reminder draft", repo / NEW_DRAFT_FILENAME)]
    return tuple(places)


#: Folders the walk of the checkout never enters: another tool's, and big.
_NEVER_ENTERED = {".git", "node_modules", ".venv", "venv"}
#: Folders the interpreter and pytest make of their own accord, not a test's doing.
_CACHES = {"__pycache__", ".pytest_cache", ".ruff_cache"}
#: Folders whose files change for reasons that are nobody's doing.
_UNWATCHED = {".claude", "build-portable", "dist", "build"}


def _walk_checkout(repo: Path, places):
    """Yield ``(relative path, DirEntry)`` for everything in the checkout, never
    entering ``.git``, the environments or a guarded place: listing a client
    tree or the scratch folder would trip the wire itself."""
    guarded = {os.path.normcase(os.path.abspath(path)) for _label, path in places}
    pending = [Path(repo)]
    while pending:
        folder = pending.pop()
        with os.scandir(folder) as entries:
            for entry in entries:
                if os.path.normcase(os.path.abspath(entry.path)) in guarded:
                    continue
                rel = os.path.relpath(entry.path, repo)
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in _NEVER_ENTERED:
                        continue
                    yield rel, entry
                    pending.append(Path(entry.path))
                else:
                    yield rel, entry


def checkout_folders(repo: Path, places) -> frozenset[str]:
    """Every folder in the checkout by relative path, the caches left out."""
    return frozenset(rel for rel, entry in _walk_checkout(repo, places)
                     if entry.is_dir(follow_symlinks=False)
                     and not _CACHES.intersection(Path(rel).parts))


def checkout_snapshot(repo: Path, places) -> dict[str, tuple[int, int]]:
    """Every file in the checkout by relative path, as ``(size, mtime_ns)``,
    the caches and the unwatched folders left out."""
    skip = _CACHES | _UNWATCHED
    found = {}
    for rel, entry in _walk_checkout(repo, places):
        if entry.is_dir(follow_symlinks=False) or skip.intersection(Path(rel).parts):
            continue
        stat = entry.stat(follow_symlinks=False)
        found[rel] = (stat.st_size, stat.st_mtime_ns)
    return found


def child_env(*, drop: tuple[str, ...] = (), **extra: str) -> dict[str, str]:
    """The environment every Python child the suite starts gets (decision 185):
    this process's, less ``drop``, with the tripwire first on the path and the
    repository after it, plus ``extra``."""
    env = {name: value for name, value in os.environ.items() if name not in drop}
    env["PYTHONPATH"] = os.pathsep.join([str(TRIPWIRE_DIR), str(REPO)])
    env.update(extra)
    return env


_STATE = pytest.StashKey[dict]()
#: The heading the session's verdict is printed under.
TRIPWIRE_HEADING = "decision 185: the suite reached a real place"


def pytest_configure(config):
    places = real_places(REPO)                     # before own_folders(): the shell's own values count
    session = Path(tempfile.mkdtemp(prefix="tracker-suite-"))
    log = session / "tripwire.log"
    patch = pytest.MonkeyPatch()
    own_folders(patch, session / APP_FOLDER)
    patch.setenv(tripwire.ENV_TRIPWIRE, json.dumps(
        {"places": [[label, str(path)] for label, path in places], "log": str(log)}))
    patch.setenv("PYTHONPATH", os.pathsep.join(
        [str(TRIPWIRE_DIR), *filter(None, [os.environ.get("PYTHONPATH")])]))
    before = checkout_folders(REPO, places)
    # In-process: SEEN, and a Python child this process starts through a
    # watched route is judged (the tripwire's docstring lists the routes).
    # The log is written only from a process this one forks (a fork that execs).
    tripwire.install(tripwire.prepare(places), log=str(log), children=os.environ[tripwire.ENV_TRIPWIRE])
    config.stash[_STATE] = {"patch": patch, "session": session, "log": log,
                            "places": places, "before": before, "said": []}


#: What the session says of a line in the tripwire's log it cannot read.
UNREADABLE_LOG_LINE = "the tripwire's log has a line it cannot read"
#: What the session says when the tripwire's log cannot be read at all.
UNREADABLE_LOG = "the tripwire's log could not be read"


def _hit_said(test: str, event: str, label: str) -> str:
    """One hit as the session says it: a reach for a place, or a child
    started around the wire."""
    if label.startswith(tripwire.UNARMED):
        return f"{test}: {event} started an {label}"
    return f"{test}: {event} of the checkout's {label}"


def tripwire_log_said(lines) -> list[str]:
    """Each line of the session's tripwire log as the session says it. A line
    that is not a hit the wire wrote - a torn write, a stray byte - is said
    plainly as a violation, never an internal error: an unread line might
    have been a hit."""
    said = []
    for number, line in enumerate(lines, start=1):
        try:
            hit = json.loads(line)
            said.append(f"{_hit_said(hit['test'], hit['event'], hit['label'])} (pid {hit['pid']})")
        except (ValueError, TypeError, KeyError, AttributeError):
            said.append(f"{UNREADABLE_LOG_LINE} (line {number})")
    return said


def read_tripwire_log(log: Path) -> list[str]:
    """The session's tripwire log as the session says it. No file is no hit;
    a log that exists and cannot be read might hold one, so it is said as a
    violation, never skipped and never an internal error."""
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return []                      # nothing was ever written: no child hit anything
    except OSError as exc:
        return [f"{UNREADABLE_LOG} ({type(exc).__name__})"]
    return tripwire_log_said(lines)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session):
    state = session.config.stash[_STATE]
    said = [_hit_said(test, event, label) for test, event, label in tripwire.SEEN]
    said += read_tripwire_log(state["log"])
    said += [f"the session left a new folder in the checkout: {rel}"
             for rel in sorted(checkout_folders(REPO, state["places"]) - state["before"])]
    if said:
        state["said"] = said
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, config):
    said = config.stash[_STATE]["said"]
    if said:
        terminalreporter.write_sep("=", TRIPWIRE_HEADING, red=True)
        for line in said:
            terminalreporter.write_line(line)


def pytest_unconfigure(config):
    state = config.stash.get(_STATE, None)
    if state is None:
        return
    store.close()
    state["patch"].undo()
    shutil.rmtree(state["session"], ignore_errors=True)
    shutil.rmtree(data_home_for(state["session"] / APP_FOLDER), ignore_errors=True)


# ---------------------------------------------------- the office-shaped copy ----

#: Set to run the whole suite, not the bounded set, in the office-shaped copy.
ENV_OFFICE_SHAPED_FULL = "TRACKER_OFFICE_SHAPED_FULL"


@pytest.fixture(scope="session")
def office_shaped_copy(tmp_path_factory):
    """The checkout copied with fabricated, real-looking files beside the app
    (decision 185): a settings file naming a clients root with one
    engagement, a store, the retired scratch folder with a page in it, the
    scheduled task's file, a client tree and a run log - everything the
    tripwire guards, in the shape an office checkout has it. Returns the copy
    and a ``{relative path: bytes}`` record of the fabricated files, so a
    nested run can be shown to have changed none of them.

    The copy is a Git repository of its own (``git init``, ``git add -A``) so
    a test that asks ``git ls-files`` gets the copy's answer."""
    from tracker.manifest import RequestItem

    base = tmp_path_factory.mktemp("office")
    copy = base / "checkout"
    listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                            cwd=REPO, capture_output=True, text=True, check=True).stdout
    for rel in filter(None, listed.split("\0")):
        source = REPO / rel
        if not source.is_file():
            continue                       # deleted in the working tree, not yet staged
        target = copy / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    office_root = base / "office-root"
    make_engagement(office_root, [RequestItem(identifier="A01", document="W-2")])
    (copy / settings.SETTINGS_FILENAME).write_text(json.dumps(
        {settings.KEY_CLIENTS_ROOT: str(office_root), settings.KEY_FIRM: PRIVATE_TREE}), encoding="utf-8")
    store.open(copy / store.STORE_FILENAME).close()
    (copy / settings.OCR_SCRATCH_DIRNAME).mkdir()
    (copy / settings.OCR_SCRATCH_DIRNAME / "page-1.png").write_bytes(b"fabricated")
    from tracker.runner import LOG_FILENAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    (copy / SCHEDULE_XML_FILENAME).write_text("<Task/>", encoding="utf-8")
    (copy / CLIENTS_TREE / TEST_HOUSEHOLD).mkdir(parents=True)
    (copy / CLIENTS_TREE / TEST_HOUSEHOLD / "note.txt").write_text("fabricated", encoding="utf-8")
    (copy / LOG_FILENAME).write_text("fabricated\n", encoding="utf-8")
    fabricated = {}
    for path in (copy / settings.SETTINGS_FILENAME, copy / store.STORE_FILENAME,
                 copy / settings.OCR_SCRATCH_DIRNAME / "page-1.png", copy / SCHEDULE_XML_FILENAME,
                 copy / CLIENTS_TREE / TEST_HOUSEHOLD / "note.txt", copy / LOG_FILENAME):
        fabricated[path.relative_to(copy).as_posix()] = path.read_bytes()

    for command in (["git", "init", "-q"], ["git", "add", "-A"]):
        subprocess.run(command, cwd=copy, capture_output=True, check=True)
    return copy, fabricated


def run_in_copy(copy: Path, *args: str, timeout: int = 600, **extra: str) -> subprocess.CompletedProcess:
    """``python -m pytest -q <args>`` in the copy, started as a fresh shell
    would start it: no settings folder, store or data home of the suite's.
    The outer tripwire's variable is kept, so this session watches the
    nested one."""
    env = child_env(drop=(settings.ENV_SETTINGS_DIR, store.ENV_STORE, settings.ENV_DATA_HOME,
                          "PYTEST_CURRENT_TEST"), **extra)
    return subprocess.run([sys.executable, "-m", "pytest", "-q", *args], cwd=copy, env=env,
                          capture_output=True, text=True, timeout=timeout)
