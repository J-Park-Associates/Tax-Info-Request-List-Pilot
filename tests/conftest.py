"""The agreement check every test in the suite pays for once.

`tracker/ledger.py` is written beside the files that already exist and is
read by nothing in production. What makes it trustworthy before anything
depends on it is this: after **every** test, every engagement folder the test
left under its ``tmp_path`` that carries a record is folded back and compared
with what the index and the manifest say. One fixture, and the whole suite -
every drop sorted, every parked file filed, every scan, every locked-Excel
sidecar, every one of the storage readings in the decision log - becomes a
test of the record too.

What is compared, and what is not:

- The fold of the record's index-shaped events against ``read_index()`` with
  its snapshot overlay: the same identities, and for each the same row, field
  for field. Only when the record carries at least one index-shaped event -
  an engagement whose record holds nothing but a scan has had no index write
  go through a writer that records.
- The statuses the record's ``scanned`` events add up to against the
  manifest's scanner columns with the pending sidecar overlaid, for every
  identifier the record has ever seen a status for. An identifier the
  manifest no longer carries is passed over: a row deleted or renamed in
  Excel since the scan is dropped by ``_apply_updates`` and by
  ``with_pending`` alike, and the record is right that it was written.

An engagement with no record at all is skipped - a test that hand-builds a
legacy workbook and never writes through the writers has nothing to agree
with - and so is one whose index the tracker refuses to read, which is itself
what that test is about.

Looking changes nothing: the index is read with ``quarantine=False``, so a
sidecar this fixture cannot parse is reported and left exactly where the test
put it.
"""

from __future__ import annotations

import pytest

from tracker import ledger
from tracker.filer import INDEX_FILENAME, FilingError, ledger_key, read_index
from tracker.manifest import (
    ManifestError,
    _load_pending,
    _update_to_json,
    load_manifest,
    with_pending,
)
from tracker.manifest import StatusUpdate as _StatusUpdate
from tracker.scaffold import MANIFEST_FILENAME

#: Engagements the comparison passes over, by folder name, with the decision
#: that will make them agree. Empty: the fixture found nothing the writers and
#: the index disagreed about.
KNOWN_DISAGREEMENTS: dict[str, str] = {}


def _index_rows(engagement_dir):
    """The index as it now reads, by the identity the record keys rows on."""
    return {
        ledger_key(entry): {f: getattr(entry, f) for f in entry.__dataclass_fields__}
        for entry in read_index(engagement_dir / INDEX_FILENAME, quarantine=False)
    }


def _manifest_statuses(engagement_dir):
    """The manifest's scanner columns with the pending sidecar overlaid."""
    path = engagement_dir / MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        items = with_pending(load_manifest(path), _load_pending(path, quarantine=False))
    except ManifestError:
        return None        # a manifest the loader refuses; that is what the test is about
    return {
        item.identifier.lower(): _update_to_json(_StatusUpdate(
            status=item.status, file_count=item.file_count,
            received_date=item.received_date, validation_notes=item.validation_notes,
        ))
        for item in items
    }


def _compare_rows(name, folded, actual):
    assert set(folded) == set(actual), (
        f"{name}: the record and the index do not hold the same originals; "
        f"only in the record: {sorted(set(folded) - set(actual))}; "
        f"only in the index: {sorted(set(actual) - set(folded))}"
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


@pytest.fixture(autouse=True)
def the_record_agrees_with_the_workbooks(tmp_path):
    """After every test: every engagement it wrote a record for still agrees."""
    yield
    for path in sorted(tmp_path.rglob(ledger.LEDGER_FILENAME)):
        _check(path.parent)
