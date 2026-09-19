"""The agreement check every test in the suite pays for once.

`tracker/ledger.py` is the engagement's own record, and since decision 88 it
is what ``read_index()`` and ``load_manifest()`` answer from wherever it has
anything to say. What keeps that honest is this: after **every** test, every
engagement folder the test left under its ``tmp_path`` that carries a record
is folded back and compared with what the *workbooks* say. One fixture, and
the whole suite - every drop sorted, every parked file filed, every scan,
every locked-Excel sidecar, every one of the storage readings in the decision
log - becomes a test of the record too.

**Compared against the workbooks' own readings, never the live ones.** The
live readers now believe the record, so ``read_index()`` and
``load_manifest()`` here would be the record compared with itself - a check
that can only pass. This fixture therefore reads
``filer.read_index_from_workbook()`` and ``manifest.statuses_from_workbook()``
(the reading every reader made before decision 88, kept public for exactly
this) and compares the record with those.

What is compared, and what is not:

- The fold of the record's index-shaped events against the workbook reading
  with its snapshot overlay: the same identities, **in the same order**, and
  for each the same row, field for field. Order matters now that the fold is
  what ``read_index()`` returns and every write rebuilds the workbook from
  it. Only when the record carries at least one index-shaped event - an
  engagement whose record holds nothing but a scan has had no index write go
  through a writer that records.
- The statuses the record's ``scanned`` events add up to against the
  workbook's scanner columns with the pending sidecar overlaid, for every
  identifier the record has ever seen a status for. An identifier the
  manifest no longer carries is passed over: a row deleted or renamed in
  Excel since the scan is dropped by ``_apply_updates`` and by
  ``with_pending`` alike, and the record is right that it was written.

An engagement with no record at all is skipped - a test that hand-builds a
legacy workbook and never writes through the writers has nothing to agree
with - and so is one whose index the tracker refuses to read, which is itself
what that test is about.

**And the view agrees with the readers** (decisions 89 and 91). Wherever a
test left a view behind, the page is **drawn again from the live readers**
through ``view.render_page()`` - the one function that writes it - and the
two texts must be the same bytes. Comparing a fresh render rather than
parsing the page back is what keeps the check honest: a page showing a row
the readers do not have, or missing one they do, differs somewhere in those
bytes, while a reader written in the test would only ever check the part
somebody thought to parse. The one thing excluded is the clock: the
generated time is read out of the page's own stamp and handed back to the
render. Here the *live* readers are the right side to compare against: the
view is a derivation of them, not another record of the same facts, and the
whole claim is that what a person opens says what the readers say.

A view ``view_state()`` does not call current is passed over, because that
is exactly what a pass reports as ``view_stale``: the replace did not land
and the view on disk is honestly one pass behind. Passing it over is not a
hole - the state itself is asserted by ``tests/test_view.py``, including
the Windows test that really holds the file open while a pass tries to
replace it.

**And the store agrees with the readers** (decision 101). After every test,
every engagement folder under ``tmp_path`` that carries a request list is
built into a store in a throwaway database - ``rebuild_engagement()`` from
the *workbooks' own* readings, exactly as the migration will - and
``check()`` against the *live* readers must return nothing at all. The two
sides are deliberately different readings: the rebuild is fed the workbook,
the check asks ``read_index()`` and ``load_manifest()``, which answer from
the record and fall back per row, and the claim is that those two meet.
Both sides see the deferred sidecar - ``statuses_from_workbook()`` overlays
it on the way in and ``with_pending()`` overlays it on the way out -
because a status a locked Excel kept out of the workbook is a status that
was applied, and a store that could not say so would be a store the
reminder could not be moved onto. An engagement the live readers
themselves refuse is passed over, exactly as the record's comparison
passes over an index the tracker will not read: that refusal is what the
test is about.

One store per test rather than one for the suite, because the claim is
about a build from nothing and because a database left open cannot be
deleted on Windows - the connection is closed before the temporary folder
goes. This runs the store over every drop sorted, every file a person
filed, every locked-Excel sidecar and every ledger path the suite has, and
it is the gate stages 2 and 3 are built on.

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
from tracker.filer import (
    INDEX_FILENAME,
    FilingError,
    ledger_key,
    read_index,
    read_index_from_workbook,
)
from tracker.manifest import (
    ManifestError,
    load_engagement_info,
    load_manifest,
    load_manifest_from_workbook,
    pending_updates,
    statuses_from_workbook,
    with_pending,
)
from tracker.records import status_from_json
from tracker.scaffold import MANIFEST_FILENAME

#: Engagements the comparison passes over, by folder name, with the decision
#: that will make them agree. Empty: the fixture found nothing the writers and
#: the index disagreed about.
KNOWN_DISAGREEMENTS: dict[str, str] = {}


def _index_rows(engagement_dir):
    """The index as the *workbook* reads it, by the identity the record keys
    rows on. Never ``read_index()``, which answers from the record."""
    return {
        ledger_key(entry): {f: getattr(entry, f) for f in entry.__dataclass_fields__}
        for entry in read_index_from_workbook(engagement_dir / INDEX_FILENAME, quarantine=False)
    }


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


def _compare_rows(name, folded, actual):
    assert set(folded) == set(actual), (
        f"{name}: the record and the index do not hold the same originals; "
        f"only in the record: {sorted(set(folded) - set(actual))}; "
        f"only in the index: {sorted(set(actual) - set(folded))}"
    )
    assert list(folded) == list(actual), (
        f"{name}: the record and the index hold the same originals in different "
        f"orders; the record says {list(folded)}, the index says {list(actual)}"
    )
    for key, row in actual.items():
        recorded = folded[key]
        for field, value in row.items():
            assert recorded.get(field) == value, (
                f"{name}: row {key!r}, field {field!r}: the record says "
                f"{recorded.get(field)!r}, the index says {value!r}"
            )


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
    events = ledger.read_events(engagement_dir)
    if any(event.get(ledger.EVENT_KEY) in ledger.ROW_EVENTS for event in events):
        try:
            actual = _index_rows(engagement_dir)
        except FilingError:
            return             # an index the tracker refuses to read; that is the test
        _compare_rows(name, ledger.fold(events), actual)
    recorded = ledger.statuses(events)
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
def the_record_agrees_with_the_workbooks(tmp_path):
    """After every test: every engagement it wrote a record for still agrees,
    and every view it left behind says what the readers say."""
    yield
    for path in sorted(tmp_path.rglob(ledger.LEDGER_FILENAME)):
        _check(path.parent)
    for path in sorted(tmp_path.rglob(view.VIEW_FILENAME)):
        _check_view(path.parent)


def workbook_readings(engagement_dir) -> dict:
    """What the *workbooks* say, as ``rebuild_engagement()`` takes it.

    The migration's inputs: the request list, the Engagement sheet, the
    rules workbook's digest, the index as the workbook and its snapshot
    read it, and every identifier's scanner columns with the deferred
    sidecar overlaid. Public because ``tests/test_store.py`` builds the
    same way and two spellings of "what the workbooks say" would be two
    migrations.
    """
    manifest_path = engagement_dir / MANIFEST_FILENAME
    return {
        "rules": load_manifest_from_workbook(manifest_path),
        "info": load_engagement_info(manifest_path),
        "manifest_digest": view.rules_digest(engagement_dir),
        "workbook_rows": read_index_from_workbook(
            engagement_dir / INDEX_FILENAME, quarantine=False),
        "workbook_statuses": {
            identifier: status_from_json(stored)
            for identifier, stored in statuses_from_workbook(manifest_path).items()
        },
    }


def live_readings(engagement_dir) -> dict:
    """What the readers answer today, as ``check()`` takes it.

    The fullest reading the package has, and the one the reminder makes:
    the record's rows and statuses over the workbooks', and over both a
    status a locked Excel deferred to the sidecar.
    """
    manifest_path = engagement_dir / MANIFEST_FILENAME
    return {
        "live_items": with_pending(
            load_manifest(manifest_path), pending_updates(manifest_path, quarantine=False)),
        "live_rows": read_index(engagement_dir / INDEX_FILENAME, quarantine=False),
    }


def _store_check(root, engagement_dir, conn) -> None:
    """Build one engagement into the store and hold it to the readers."""
    try:
        readings, live = workbook_readings(engagement_dir), live_readings(engagement_dir)
    except (ManifestError, FilingError, OSError):
        return          # what the readers refuse is what that test is about
    store.rebuild_engagement(conn, root, engagement_dir, **readings)
    said = store.check(conn, root, engagement_dir, **live)
    assert said == [], "; ".join(said)


@pytest.fixture(autouse=True)
def the_store_agrees_with_the_readers(tmp_path):
    """After every test: a store built from the workbooks and the record for
    every engagement the test left behind says what the readers say."""
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
