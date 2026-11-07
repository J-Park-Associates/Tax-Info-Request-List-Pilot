"""What the filer's family of test files shares, in one place.

``tests/test_filer.py`` wrote these for itself. With P331
(SPEC-architecture-p4 P4.4) the tests that drive only the code that moved to
``tracker/copies.py`` - a working copy's name, the room a return has, the
byte-proved copy, the rename-only move and the stranded-temp sweep - left it
for ``tests/test_copies.py``, each still reading the helpers it was written
against. A test file may not import another (``tests/test_suite_shape.py``),
so what both files read sits here, in a module that is not a test file, and
each names it; the map draws the edge as "exercised by". Each later move out
of the filer (SPEC-architecture-p4 section 4.1) adds here what its split
shares.

From ``tests/test_filer.py``, with their words: :func:`originals` (the
client's folder for a return's year), :class:`RequestFiles` and
:func:`prepared` (a request's files in Prepared, and the review folder),
:func:`review_dir`, :func:`_catalog_w2` (the 1040 catalog's A01, decision
144), and the fabricated client path a refused read names
(:data:`A_CLIENT_PATH`, :func:`_refused_with_a_client_path`) with
:func:`_logged_outside_the_debug_log`, which reads what was logged outside
the debug log (decision 190). Nothing here is new behaviour.

With P332 (SPEC-architecture-p4 P4.6) the tests that drive only the code
that moved to ``tracker/intents.py`` - the write-ahead intents, the places a
step may touch and finishing an interrupted move - left for
``tests/test_intents.py``, and :func:`_forge_line` came here from
``tests/test_filer.py`` with its words: it puts one line in the journal past
the store, as another machine would, and a forged step's tests there and an
old intent's finish in the filer's tests both write with it.

With P333 (SPEC-architecture-p4 P4.7) the tests that drive only the code
that moved to ``tracker/inbox.py`` - the walk, the folders it cannot list
and the folder of originals the household's returns share - left for
``tests/test_inbox.py``, and the :func:`two_returns` fixture came here from
``tests/test_filer.py`` with its words: one household with two returns of
the open year, which the shared folder's test there and the household's
tests in the filer's file both take.

With P334 (SPEC-architecture-p4 P4.8) the tests that drive only the code
that moved to ``tracker/readme_ack.py`` - the client README's received list
and its refresh - left for ``tests/test_readme_ack.py``, and seven helpers
came here from ``tests/test_filer.py`` with their words, because tests in
both files read them: :data:`DAY3` (the day a pass recovers what a run left
half done, decision 119), :func:`events_named` (every journal line of one
event name), :func:`open_intents` (the moves begun and not finished),
:func:`_status` (one request's row in the list), :data:`MORTGAGE` (the
1098's text), :func:`_filed_1098` (C01's one document, sorted and scanned
the ordinary way) and :func:`_a_pass` (the pass as the runner makes it).

**The one fixture here is named, not imported.** ``two_returns`` is a
fixture, and a test file that wants it names it once by assignment
(``two_returns = filer_helpers.two_returns``), as ``tests/store_helpers.py``'s
are named: a fixture imported by name and then taken as a parameter trips
ruff's F811 at every such test. The other fixture both files take,
``engagement``, is ``tests.builders``' ``engagement_fixture(ITEMS)``, named
once in each file.
"""

import datetime as dt
from dataclasses import replace
from pathlib import Path

import pytest

from tests.builders import BUSINESS, DAY1, ITEMS, drop, make_engagement, sort
from tracker import ledger, store
from tracker.layout import originals_of
from tracker.manifest import load_manifest
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
)


def originals(engagement):
    """The folder the client sees for this return's year: where an original
    rests once the pass has moved it out of the inbox (decision 125)."""
    return originals_of(engagement)


class RequestFiles:
    """What one request's folder was, flat (decision 168): its working copies
    sit in Prepared itself, and a file is the request's when its name begins
    with the identifier (``tracker.scaffold.assign_files``). So ``/ name``
    is where a file named for the request goes - ``Prepared/A01 - name``,
    or ``Prepared/<name>`` for a name that already begins with it - and
    ``iterdir()`` is the request's files. Dragging a copy "into C01" is
    renaming it under C01's name beside the others, which is the only way a
    person can move a copy between requests now."""

    def __init__(self, root: Path, identifier: str):
        self.root, self.identifier = root, identifier

    def __truediv__(self, name: str) -> Path:
        from tracker.scaffold import matches_identifier

        if matches_identifier(name, self.identifier):
            return self.root / name
        return self.root / f"{self.identifier} - {name}"

    def iterdir(self):
        from tracker.scaffold import assign_files

        return iter(assign_files(self.root, [self.identifier])[self.identifier])

    def mkdir(self, **_kwargs) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def prepared(engagement, folder_prefix):
    """The review folder itself, or one request's files as a
    :class:`RequestFiles` - there is no folder per request (decision 168)."""
    root = engagement / PREPARED_DIR_NAME
    if folder_prefix == REVIEW_DIR_NAME:
        return root / REVIEW_DIR_NAME
    return RequestFiles(root, folder_prefix.split(" ")[0])


def review_dir(engagement):
    return engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME


def _catalog_w2(**changes):
    """The 1040 catalog's A01, as a return created today would have it."""
    from tracker.templates import template_items

    return replace(template_items("1040", year=2025)[0], **changes)


#: A fabricated OS error's path, shaped like a client's inbox (decision 190).
A_CLIENT_PATH = "/Clients/Test Household/Drop files here/W2.pdf"


def _refused_with_a_client_path(*_args, **_kwargs):
    import errno

    raise PermissionError(errno.EACCES, "Permission denied", A_CLIENT_PATH)


def _logged_outside_the_debug_log(caplog) -> str:
    """Every line logged, but the debug log's, where the words are kept on
    purpose (tracker.errors.keep)."""
    from tracker.errors import DEBUG_LOGGER

    return "\n".join(record.getMessage() for record in caplog.records if record.name != DEBUG_LOGGER)


def _forge_line(engagement, event: dict) -> bytes:
    """Put one line in the journal past the store, as another machine
    would; returns the journal as it was. Linked to the line before
    (decision 159), so it is the store's admission and the filer's own
    checks that judge it, not the ledger's link."""
    from tests.builders import written_elsewhere

    honest = ledger.path_for(engagement).read_bytes()
    written_elsewhere(engagement, event)
    return honest


@pytest.fixture
def two_returns(tmp_path):
    """One household with two returns of the open year: a 1040 and an 1120S."""
    personal = make_engagement(tmp_path, ITEMS, household="Park Family",
                               return_name="1040 - John Park")
    business = make_engagement(tmp_path, BUSINESS, household="Park Family",
                               return_name="1120S - Park Landscaping")
    return personal, business


#: The day a pass recovers what a run left half done (decision 119): the
#: row it records is still dated the day the decision was made.
DAY3 = dt.date(2026, 7, 15)


def events_named(engagement, name):
    """Every journal line of one event name."""
    return [e for e in ledger.read_events(engagement) if e[ledger.EVENT_KEY] == name]


def open_intents(engagement):
    """The moves this engagement has begun and not finished."""
    return store.open_intents(store.connect(), engagement)


def _status(engagement, identifier):
    return next(i for i in load_manifest(engagement) if i.identifier == identifier)


MORTGAGE = "Form 1098 Mortgage Interest Statement 2025"


def _filed_1098(engagement, name="1098.pdf"):
    """C01's one document, sorted and scanned the ordinary way: Received."""
    from tracker.manifest import Status
    from tracker.scanner import scan_engagement

    drop(engagement, name, MORTGAGE)
    [filed] = sort(engagement, today=DAY1).filed
    scan_engagement(engagement, today=DAY1)
    assert filed.identifier == "C01" and _status(engagement, "C01").status == Status.RECEIVED
    return filed


def _a_pass(engagement, today):
    """The pass as the runner makes it: the sort, whose sweep proves every
    copy first, and then the scan."""
    from tracker.scanner import scan_engagement

    report = sort(engagement, today=today)
    return report, scan_engagement(engagement, today=today)
