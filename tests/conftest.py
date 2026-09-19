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

**Making an engagement** (``make_engagement``) **is one call**: the folder,
the list and the details recorded through ``create_engagement()`` - the
same call the API makes - and the scaffold on top when asked. It is the
one way a test makes an engagement, so a seeded engagement is the one the
app would have made.

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
import tempfile
from pathlib import Path

import pytest

from tracker import ledger, store, view
from tracker.filer import ensure
from tracker.ledger import LedgerError
from tracker.locking import engagement_lock
from tracker.manifest import EngagementInfo, create_engagement
from tracker.records import entry_to_json, ledger_key, status_to_json
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
    """
    patch = pytest.MonkeyPatch()
    patch.setenv(store.ENV_STORE, str(tmp_path / "app" / store.STORE_FILENAME))
    store.close()
    try:
        yield
    finally:
        store.close()
        patch.undo()


#: Engagements the comparison passes over, by folder name, with the decision
#: that will make them agree. Empty: the fixture found nothing the writers and
#: the record disagreed about.
KNOWN_DISAGREEMENTS: dict[str, str] = {}


def make_engagement(folder, items, info: EngagementInfo | None = None, *,
                    form: str = "", scaffold: bool = True) -> Path:
    """The one way a test makes an engagement: the folder, its record and,
    unless told not to, its scaffold.

    ``create_engagement()`` is the API's own create, so what a test seeds
    is exactly what the app would have made: one ``rules_changed`` event
    carrying the whole list and the details, validated on the way in. The
    scaffold is the folders the filer and the scanner need; a test that
    wants only the record says ``scaffold=False``. Returns the folder.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    create_engagement(folder, list(items), info, form=form)
    if scaffold:
        scaffold_engagement(folder)
    return folder


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
    for path in sorted(tmp_path.rglob(view.VIEW_FILENAME)):
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
    folders = sorted({path.parent for path in tmp_path.rglob(ledger.LEDGER_FILENAME)})
    if not folders:
        return
    with tempfile.TemporaryDirectory() as scratch:
        conn = store.open(Path(scratch) / store.STORE_FILENAME)
        try:
            for folder in folders:
                _store_check(tmp_path, folder, conn)
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
