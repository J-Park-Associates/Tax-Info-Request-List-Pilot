"""The agreement checks every test in the suite pays for once.

`tracker/ledger.py` is the engagement's own record. Since decision 102 it
is the whole of the index - there is no ``_index.xlsx`` to disagree with
any more - and since decision 88 it is what ``load_manifest()`` answers
each identifier's status from, with the workbook behind it. Three autouse
fixtures hold all of that honest after **every** test.

**A store of its own** (``a_store_of_its_own``). The store keeps one
connection per process and the file it would otherwise open sits beside
the settings file, which on a developer's machine is the repository.
``TRACKER_STORE`` points it at this test's own ``tmp_path`` instead, and
the connection is closed at teardown before the temporary folder goes,
because Windows will not delete a database a handle is open on. No test
can see another's rows.

**The record agrees with the manifest**
(``the_record_agrees_with_the_manifest``). For every engagement the test
left a record in, the statuses the record's ``scanned`` events add up to
are compared with the workbook's scanner columns, the pending sidecar
overlaid, for every identifier the record has ever seen a status for. An
identifier the manifest no longer carries is passed over: a row deleted or
renamed in Excel since the scan is dropped by ``_apply_updates`` and by
``with_pending`` alike, and the record is right that it was written. The
comparison is against ``manifest.statuses_from_workbook()``, never
``load_manifest()``, which would be the record compared with itself. The
index half of this check is gone with the workbook it compared against;
the store fixture below is what took its place.

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
decision 101, re-aimed by 102). Every engagement folder under ``tmp_path``
that carries a request list is built into a store in a throwaway database -
``rebuild_engagement()`` from the record and the workbooks - and ``check()``
against the other copies must return nothing at all. The two sides are
deliberately different readings, and since the index left the workbook
each half has a different other copy: the **documents** are compared with
``ledger.replay()`` over the journal, which is now the only second copy
of them; the **requests and statuses** are compared with the live manifest
readers, which answer from the record and fall back to the sheet per
identifier while the rebuild is fed the sheet's own reading. Both sides see
the deferred sidecar, because a status a locked Excel kept out of the
workbook is a status that was applied. An engagement the readers themselves
refuse is passed over: that refusal is what the test is about.

One store per test rather than one for the suite, because the claim is
about a build from nothing. This runs the store over every drop sorted,
every file a person filed, every locked-Excel sidecar and every ledger path
the suite has, and it is the gate decision 102 was built on.

**Seeding an index** (``seed_index``). A test that needs rows to exist
records them, because recording them is the only way they can exist: the
helper appends ``imported`` events under the engagement lock through the
store, which is the same call every writer in the package makes.

Looking changes nothing: the workbooks are read with ``quarantine=False``, so
a sidecar this fixture cannot parse is reported and left exactly where the
test put it.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import sys
import tempfile
from pathlib import Path

import pytest

from tracker import ledger, store, view
from tracker.filer import FilingError, ensure, workbook_readings
from tracker.locking import engagement_lock
from tracker.manifest import (
    ManifestError,
    load_manifest,
    pending_updates,
    statuses_from_workbook,
    with_pending,
)
from tracker.records import entry_from_json, entry_to_json, ledger_key
from tracker.scaffold import MANIFEST_FILENAME


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


def _manifest_statuses(engagement_dir):
    """The *workbook's* scanner columns with the pending sidecar overlaid.
    Never ``load_manifest()``, which answers from the record."""
    path = engagement_dir / MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        recorded = statuses_from_workbook(path)
    except ManifestError:
        return None        # a manifest the loader refuses; that is what the test is about
    return {identifier.lower(): status for identifier, status in recorded.items()}


def _compare_statuses(name, recorded, actual):
    for identifier, status in recorded.items():
        expected = actual.get(identifier.lower())
        if expected is None:
            continue           # the row is not in the manifest any more
        assert status == expected, (
            f"{name}: {identifier} - the record says {status!r}, the manifest says {expected!r}"
        )


def _check(engagement_dir) -> None:
    name = engagement_dir.name
    if name in KNOWN_DISAGREEMENTS:
        return
    recorded = ledger.statuses(ledger.read_events(engagement_dir))
    if recorded:
        actual = _manifest_statuses(engagement_dir)
        if actual is not None:
            _compare_statuses(name, recorded, actual)


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
def the_record_agrees_with_the_manifest(tmp_path):
    """After every test: every status the record holds is the status the
    manifest workbook holds, and every view the test left behind says what
    the readers say."""
    yield
    for path in sorted(tmp_path.rglob(ledger.LEDGER_FILENAME)):
        _check(path.parent)
    for path in sorted(tmp_path.rglob(view.VIEW_FILENAME)):
        _check_view(path.parent)


def live_readings(engagement_dir) -> dict:
    """The other copies of what the store holds, as ``check()`` takes them.

    Two different readings, because since decision 102 the two halves have
    two different other copies. The **index rows** come from the journal
    replayed - the only other copy there is, now that the workbook is gone
    and ``read_index()`` answers from the store's own tables. The
    **request rows** come from the live manifest readers, which still
    answer from the record and fall back to the sheet per identifier, with
    a status a locked Excel deferred overlaid on top.
    """
    manifest_path = engagement_dir / MANIFEST_FILENAME
    return {
        "live_items": with_pending(
            load_manifest(manifest_path), pending_updates(manifest_path, quarantine=False)),
        "live_rows": [entry_from_json(row) for row in
                      ledger.replay(ledger.read_events(engagement_dir)).rows.values()],
    }


def _store_check(root, engagement_dir, conn) -> None:
    """Build one engagement into the store and hold it to the other copies."""
    try:
        readings, live = workbook_readings(engagement_dir), live_readings(engagement_dir)
    except (ManifestError, FilingError, OSError):
        return          # what the readers refuse is what that test is about
    store.rebuild_engagement(conn, root, engagement_dir, **readings)
    said = store.check(conn, root, engagement_dir, **live)
    assert said == [], "; ".join(said)


@pytest.fixture(autouse=True)
def the_store_agrees_with_the_record(tmp_path):
    """After every test: a store built from the record and the workbooks for
    every engagement the test left behind says what the other copies say."""
    yield
    folders = sorted({path.parent for path in tmp_path.rglob(MANIFEST_FILENAME)})
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


def write_a_legacy_index(engagement_dir, entries):
    """Write the index workbook nothing writes any more, for the migration
    to find. Returns the file.

    Decision 102 deleted ``write_index()``, and with it the only way to
    produce an ``_index.xlsx``. A folder from before that decision still
    has one, so the suite has to be able to make one: the header row and
    the columns in ``INDEX_LAYOUT``'s order, which is exactly what the
    workbook always held. Nothing in the package calls this - it is the
    shape of the past, kept only so the migration can be tested against
    it.
    """
    from openpyxl import Workbook

    from tracker.filer import INDEX_FILENAME, INDEX_SHEET
    from tracker.records import INDEX_COLUMNS

    path = Path(engagement_dir) / INDEX_FILENAME
    wb = Workbook()
    ws = wb.active
    ws.title = INDEX_SHEET
    ws.append(list(INDEX_COLUMNS))
    for entry in entries:
        ws.append(entry.as_row())
    wb.save(path)
    return path


@pytest.fixture
def held_like_excel():
    """A context manager that holds a file the way Excel holds a workbook it
    has open: ``CreateFileW`` with ``GENERIC_READ`` and share mode
    ``FILE_SHARE_READ`` and nothing else. Another reader still opens the
    file; a writer's ``os.replace`` onto it is refused for as long as the
    handle is held, which is the refusal every lock-retry path in the
    package is written for.

    The one real evidence of Windows share modes the suite has. Every other
    "Excel has it open" test monkeypatches ``Workbook.save`` or the atomic
    replace and so proves the retry logic, never the file system; the
    tests that take this fixture prove both, one workbook each. It skips
    off Windows, because share modes are a Windows file-system behaviour
    and CI runs the Windows jobs.
    """
    if sys.platform != "win32":
        pytest.skip("Excel's share modes are a Windows file-system behaviour")
    import ctypes
    from ctypes import wintypes

    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.HANDLE)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    @contextlib.contextmanager
    def hold(path):
        handle = kernel32.CreateFileW(str(path), GENERIC_READ, FILE_SHARE_READ, None,
                                      OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
        assert handle != INVALID_HANDLE_VALUE, ctypes.get_last_error()
        try:
            yield
        finally:
            kernel32.CloseHandle(handle)

    return hold
