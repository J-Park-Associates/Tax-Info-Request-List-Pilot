"""Tests for tracker/firm_view.py - the Overview's rows, their cache and the
group rule the return's own page shares.

Most of what the module promises is held by tests/test_api.py and the test_api_<family> files split from it
(SPEC-architecture-p5 P5.14), whose tests
drive the firm, firm-last and state commands and so are about the command:
the counts by group, the files waiting, the draft's state, a record that
cannot be read said as its own row, the cached reply held to the whole
walk's field for field (P120), the batches and their count lines (P222),
the last counts and their refusals (P229), and that a firm read follows no
journal, takes no lock and opens no file the fingerprint leaves out. None
of them moved here by the SPEC's rule, because each runs a command. The
two tests below moved here from tests/test_api.py (SPEC-architecture-p5
R5.7.6, P344): each calls one half of the group rule and nothing else of
the API. They read it through ``tracker.api``, which imports both back,
until SPEC-architecture-p5 P5.16 retargets every such read to its home.
The third holds :func:`tracker.firm_view.tally`, the one count by group
that a firm row and a return's ``state`` both send (SPEC-architecture-p6
P6.5, P354).
"""

import tracker.api as api
import tracker.firm_view as firm_view
from tracker.index import NEEDS_REVIEW
from tracker.manifest import Status
from tracker.records import IndexEntry


def test_item_group_follows_its_table():
    from types import SimpleNamespace

    from tracker.manifest import Override
    from tracker.reminder import SIDE_CLIENT, SIDE_DECIDE, SIDE_US

    def row(status=Status.MISSING, asked=True, override="", identifier="A01"):
        return SimpleNamespace(identifier=identifier, status=status, asked=asked,
                               manual_override=override)

    assert firm_view.item_group(row(override=Override.NOT_APPLICABLE), {}) == "set_aside"
    assert firm_view.item_group(row(status="", asked=False), {}) == "set_aside"       # nothing in
    assert firm_view.item_group(row(), {"A01": (SIDE_CLIENT, "")}) == "waiting"
    assert firm_view.item_group(row(), {"A01": (SIDE_US, "")}) == "needs_you"
    assert firm_view.item_group(row(), {"A01": (SIDE_DECIDE, "")}) == "needs_you"
    assert firm_view.item_group(row(status=Status.RECEIVED), {}) == "received"
    assert firm_view.item_group(row(override=Override.ACCEPTED), {}) == "received"
    assert firm_view.item_group(row(), {}) == "waiting"                                # not yet checked
    # The order of the table: an override beats a side; a side beats Received.
    assert firm_view.item_group(row(override=Override.NOT_APPLICABLE), {"A01": (SIDE_US, "")}) == "set_aside"
    assert firm_view.item_group(row(status=Status.RECEIVED), {"A01": (SIDE_US, "")}) == "needs_you"


def test_a_file_falls_in_the_group_its_decision_says():
    from tracker.index import FILE_MOVED, NOT_REQUESTED

    def entry(decision, home="A01/a.pdf"):
        return IndexEntry(received="2026-02-01", original_name="a.pdf", size_kb=1.0, digest="1" * 64,
                          identifier="A01", prepared_location=home, pbc_location="pbc/a.pdf",
                          decision=decision, reason="")

    assert firm_view.file_group(entry(NEEDS_REVIEW)) == "needs_you"
    assert firm_view.file_group(entry(FILE_MOVED)) == "needs_you"
    assert firm_view.file_group(entry(FILE_MOVED, home="")) == "set_aside"      # marked missing
    assert firm_view.file_group(entry(NOT_REQUESTED)) == "set_aside"
    assert firm_view.file_group(entry(api.FILED)) == "received"


def test_tally_counts_each_row_in_its_group_and_each_file_but_a_filed_one_in_the_groups_order():
    """A request row counts in its ``item_group``, a file in its
    ``file_group`` unless it is filed (its request is already the Received
    row), and every group is there in ``GROUPS``' order, at zero too."""
    from types import SimpleNamespace

    from tracker.index import FILE_MOVED, FILED, NOT_REQUESTED
    from tracker.manifest import Override
    from tracker.reminder import SIDE_CLIENT, SIDE_US

    def row(identifier, status=Status.MISSING, override=""):
        return SimpleNamespace(identifier=identifier, status=status, asked=True, manual_override=override)

    def entry(decision, home="A01/a.pdf"):
        return IndexEntry(received="2026-02-01", original_name="a.pdf", size_kb=1.0, digest="1" * 64,
                          identifier="A01", prepared_location=home, pbc_location="pbc/a.pdf",
                          decision=decision, reason="")

    items = [row("A01"), row("A02"), row("A03", status=Status.RECEIVED), row("A04", override=Override.NOT_APPLICABLE)]
    placed = {"A01": (SIDE_US, ""), "A02": (SIDE_CLIENT, "")}
    files = [entry(NEEDS_REVIEW), entry(FILE_MOVED), entry(FILE_MOVED, home=""), entry(NOT_REQUESTED), entry(FILED)]
    counts = firm_view.tally(items, placed, files)
    assert list(counts) == list(firm_view.GROUPS)
    assert counts == {"needs_you": 1 + 2, "waiting": 1, "received": 1, "set_aside": 1 + 2}
    assert firm_view.tally([], {}, []) == dict.fromkeys(firm_view.GROUPS, 0)
