"""Tests for tracker/inbox.py - the inbox walked, and what in it or the year's folder cannot be sorted or tied to its row.

The promises being tested: only a name the journal cannot hold is refused;
the walk of the folders the run cannot list covers the same ground as the
other walks, and never walks behind a junction; a folder the run cannot
list is reported every pass while what can be read beside it files; one
folder of originals serves the household-year, so a file one return's row
holds is never another return's stray; and the count of names left alone
skips what is already named as syncing.

These tests came from ``tests/test_filer.py`` with the code they drive
(SPEC-architecture-p4 P4.7, P333): each one whose highest home, by section
4.1's rule, is ``tracker/inbox.py``, cut and pasted with its name. The
``two_returns`` fixture one of them takes is ``tests/filer_helpers.py``'s
now, named here as in ``tests/test_filer.py``, and so is ``originals``. The
section comments they sat under in ``tests/test_filer.py`` stay there above
the tests of those sections that stay; decision 102's, which headed only the
first of them there, went (``tests/test_index.py`` carries it above that
section's tests). Two of them drive the code through a pass, as they did;
the claim each makes is about the code here. Each imports what it reads
of the inbox from ``tracker.inbox`` (``_storable``, ``unlistable_folders``,
``unrecorded_in_pbc``, ``ignored_in_inbox``), never through the filer's
import-back.
"""

import sys

from tests import filer_helpers
from tests.builders import (
    DAY1,
    DAY2,
    ITEMS,
    drop,
    engagement_fixture,
    sort,
    sort_all,
)
from tests.filer_helpers import originals
from tests.samples import text_pdf
from tracker.index import read_index
from tracker.layout import inbox_of

engagement = engagement_fixture(ITEMS)

#: One household with two returns of the open year, from
#: ``tests/filer_helpers.py``: named once so that a test here can ask for it.
two_returns = filer_helpers.two_returns


def test_only_a_name_the_journal_cannot_hold_is_refused(engagement):
    """The journal is UTF-8 JSON: an unpaired surrogate cannot be written
    into it, and such a name once took the whole index down. A control
    character files again (decision 104): the refusal of one existed
    because a workbook is XML, and there is no workbook."""
    from tracker.inbox import _storable

    inbox = inbox_of(engagement)
    assert _storable(inbox / "scan\x072025.pdf")
    assert _storable(inbox / "scan 2025.pdf")
    assert not _storable(inbox / "scan\udcff2025.pdf")


def test_the_unlistable_walk_covers_the_same_ground_as_the_others(engagement, tmp_path):
    from tests.samples import listing_denied
    from tracker.inbox import unlistable_folders

    inbox = inbox_of(engagement)
    inside = inbox / "from my phone" / "scans"
    inside.mkdir(parents=True)
    staging = inbox / ".tmp.driveupload"
    staging.mkdir()
    assert unlistable_folders(inbox) == []
    with listing_denied(inside):                     # a folder the client dragged in, denied
        assert unlistable_folders(inbox) == [inside]
    if sys.platform == "win32":
        import _winapi

        outside = tmp_path / "outside" / "deep"
        outside.mkdir(parents=True)
        _winapi.CreateJunction(str(tmp_path / "outside"), str(inbox / "link"))
        assert unlistable_folders(inbox) == []                        # never walks behind the junction


def test_a_folder_the_run_cannot_list_is_reported_every_pass(engagement):
    from tests.samples import listing_denied
    from tracker.inbox import unlistable_folders

    denied = inbox_of(engagement) / "from my accountant"
    denied.mkdir()
    text_pdf(denied / "inside-w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "readable-w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    with listing_denied(denied):
        assert unlistable_folders(inbox_of(engagement)) == [denied]
        report = sort(engagement, today=DAY1)
    assert [e.original_name for e in report.filed] == ["readable-w2.pdf"]
    assert [(e.name, e.left_in_place) for e in report.errors] == [(denied.name, True)]
    assert "cannot list" in report.errors[0].error


def test_the_originals_folder_is_shared_and_another_returns_original_is_never_a_stray(two_returns):
    """One folder of originals serves the household-year, so a file one
    return's row holds must never look like another return's stray."""
    from tracker.inbox import unrecorded_in_pbc

    personal, business = two_returns
    drop(personal, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(personal, "tb.pdf", "Trial balance as of December 31 2025")
    sort_all(two_returns, today=DAY1)

    rows = [(one, read_index(one)) for one in two_returns]
    assert unrecorded_in_pbc(originals(personal), rows) == []
    # A second pass changes nothing: neither return sorts the other's.
    assert all(report.handled == 0 for report in sort_all(two_returns, today=DAY2).values())
    assert len(read_index(personal)) == 1 and len(read_index(business)) == 1


def test_the_inbox_count_of_names_left_alone_skips_what_is_named_as_syncing(engagement):
    """``ignored_in_inbox`` counts what the sort leaves alone by name and
    nothing it already names (decision 190): an unfinished transfer is in
    the report by name as syncing, so it is not in the count as well, and
    the README and a real drop are neither."""
    from tracker.inbox import ignored_in_inbox

    inbox = inbox_of(engagement)
    before = ignored_in_inbox(inbox)
    for name in ("desktop.ini", ".DS_Store", "~$budget.xlsx", "statement.pdf.driveupload", "w2.pdf"):
        (inbox / name).write_bytes(b"x")
    (inbox / ".tmp.drive1").mkdir()
    (inbox / ".tmp.drive1" / "w2.pdf.tmp").write_bytes(b"x")

    assert ignored_in_inbox(inbox) - before == 4
    assert ignored_in_inbox(inbox / "no such folder") == 0
