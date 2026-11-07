"""The store's fixtures and helpers, in one place: the clients root, a return, a store beside the app.

``tests/test_store.py`` wrote these for itself, and with P324
(SPEC-architecture-p3 P3.4) the check's and the export's tests left it for
``tests/test_store_check.py``, and one test of the admission for
``tests/test_admission.py`` - each still reading the fixtures and helpers it
was written against. A test file may not import another
(``tests/test_suite_shape.py``), so what more than one of them reads sits
here, in a module that is not a test file, and every user names it; the map
draws the edge as "exercised by". With P325 (SPEC-architecture-p3 P3.5)
the verify tests left it too, for ``tests/test_verify.py``, and the three
helpers the one that writes a row by hand shares with the store's tests
came here with their words: :func:`unlinked`, :func:`a_row` and
:data:`A_ROW_ORIGINAL`.

Nothing here is new behaviour: each fixture and helper is test_store's own,
moved with its words. The one edit is :func:`said`, which asks
``tracker.store_check`` for the check the store no longer holds.

**The fixtures are named, not imported.** ``root``, ``engagement``,
``by_hand`` and ``conn`` are fixtures, and a test file that wants one names
it once by assignment (``conn = store_helpers.conn``), as
``tests/passes.py``'s ``samples`` is named: a fixture imported by name, which
a test then takes as a parameter, trips ruff's F811 at every such test. A
file names every fixture the ones it uses ask for - ``by_hand`` asks for
``engagement``, which asks for ``root`` - because pytest finds a fixture in
the test's own module, not in the module that defined it.
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest

from tests.builders import engagement_fixture
from tests.conftest import child_env, sort
from tracker import ledger, store, store_check
from tracker.manifest import RequestItem, load_engagement_info, save_rules
from tracker.records import rule_from_json, rule_to_json

REPO = Path(__file__).resolve().parents[1]
DAY1 = dt.date(2026, 7, 1)
DAY2 = dt.date(2026, 7, 9)

ITEMS = [
    RequestItem(
        identifier="A01", document="W-2 Wage Statements", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("W-2",),
        date_pattern=r"(?i)\b2025\b",
    ),
    RequestItem(
        identifier="C01", document="Mortgage Interest Statement", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("1098",),
    ),
]

#: Where the original of the row these tests write by hand sits: in the
#: household's folder for the year, which is across the two trees from the
#: return - so the location begins with ``..`` (decision 125).
A_ROW_ORIGINAL = "../../../../Clients/Smith Family/2025/w2.pdf"


@pytest.fixture
def root(tmp_path):
    """The clients root - the folder a cloud client syncs."""
    folder = tmp_path / "Clients"
    folder.mkdir()
    return folder


engagement = engagement_fixture(ITEMS, household="Smith Family", root="root")


@pytest.fixture
def by_hand(engagement):
    """An engagement whose record this test writes itself.

    These tests are about the store's fold, not the filer's, so they append
    rows no pass ever made - and the suite's own fixture holds every
    record to its journal. The record is removed when the test ends, the
    way the journal's own tests put back what they tore, so the folder the
    fixtures then see holds no record to check.
    """
    yield engagement
    ledger.path_for(engagement).unlink(missing_ok=True)


@pytest.fixture
def conn(tmp_path):
    """A store beside the app, which is not under the clients root."""
    connection = store.open(tmp_path / "app" / store.STORE_FILENAME)
    yield connection
    connection.close()


def build(conn, root, engagement):
    store.rebuild_engagement(conn, root, engagement)


def edit_rules(engagement, **fields_by_identifier):
    """A person's edit of one or more rows, saved in the app as one event."""
    from dataclasses import replace

    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement)]
    edited = [replace(row, **fields_by_identifier.get(row.identifier, {})) for row in rows]
    return save_rules(engagement, edited, load_engagement_info(engagement))


def said(conn, root, engagement):
    return store_check.check(conn, root, engagement)


def id_of(conn, folder):
    """The store's id for one folder.

    Since decision 125 a household is a row of ``engagements`` too - the
    same table, keyed by path, with ``kind`` saying which - so a question
    about one return's rows names that return rather than reading the
    first row of a table."""
    return store._engagement_row(conn, folder)["id"]


def learned(identifier: str, keyword: str) -> dict:
    """A person's filing teaching one request one word."""
    return ledger.new(ledger.KEYWORD_LEARNED, **{ledger.IDENTIFIER_KEY: identifier,
                                                 ledger.KEYWORD_KEY: keyword})


def unlearned(identifier: str, keyword: str) -> dict:
    """A person taking one of those words back, in the editor (decision 113)."""
    return ledger.new(ledger.KEYWORD_UNLEARNED, **{ledger.IDENTIFIER_KEY: identifier,
                                                   ledger.KEYWORD_KEY: keyword})


def a_pass(engagement):
    from tracker.scanner import scan_engagement

    sort(engagement, today=DAY1)
    return scan_engagement(engagement, today=DAY1)


def cli(*argv):
    return subprocess.run([sys.executable, "-m", "tracker.store", *[str(a) for a in argv]],
                          cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                          env=child_env(PYTHONIOENCODING="utf-8"))


def scanned(**statuses) -> dict:
    """One scan's line, the statuses it changed by the spelling it met."""
    return ledger.new(ledger.SCANNED, **{ledger.STATUSES_KEY: {
        identifier: {"status": status, "file_count": 0} for identifier, status in statuses.items()}})


def _a_rule(**fields) -> dict:
    return {**rule_to_json(ITEMS[0]), **fields}


def unlinked(events):
    """``events`` as a journal from before decision 159 held them: without
    the three keys every line now carries."""
    return [{k: v for k, v in event.items() if k not in ledger.LINE_KEYS} for event in events]


def a_row(**fields) -> dict:
    base = {"received": "2026-07-01", "original_name": "w2.pdf", "size_kb": 1.0,
            "digest": "ab" * 32, "identifier": "", "prepared_location": "",
            "pbc_location": A_ROW_ORIGINAL, "decision": "Needs Review",
            "reason": "", "candidates": "", "evidence": "", "also_filed": ""}
    return {**base, **fields}
