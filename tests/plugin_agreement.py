"""The agreement checks every test in the suite pays for once: the view and the store held to the record
(decisions 89, 91, 101, 102, 103 and 104).

The third plugin in ``tests/conftest.py``'s ``pytest_plugins``: its two autouse fixtures are set up last, so they are
torn down first, while every stand-in is still in place (``tests/test_suite_shape.py``'s ``AUTOUSE_ORDER`` pins the
order). It imports ``_ALSO_WALK`` from ``plugin_isolation`` (listed before it): one list object, cleared and appended
to, never rebound, so a from-import shares it. A plugin may import from one listed before it, never from one listed
after.

`tracker/ledger.py` is the engagement's own record. Since decision 102 it
is the whole of the index, since decision 103 the whole of the statuses,
and since decision 104 the whole of the person's rules and the engagement's
details too - there is nothing anywhere else for it to disagree with.
Two autouse fixtures hold that honest after **every** test.

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

Looking changes nothing: these fixtures read the record and never write in
an engagement folder.

"""
from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

import pytest

from tests.plugin_isolation import _ALSO_WALK
from tracker import ledger, store, store_check, view
from tracker.ledger import LedgerError

#: Engagements the comparison passes over, by folder name, with the decision
#: that will make them agree. Empty: the fixture found nothing the writers and
#: the record disagreed about.
KNOWN_DISAGREEMENTS: dict[str, str] = {}

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
    said = store_check.check(conn, root, engagement_dir)
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
