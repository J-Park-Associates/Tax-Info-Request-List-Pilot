"""Tests for tracker/readme_ack.py - what the client README says has arrived, and the one refresh that rewrites it.

The promises being tested: the received list is a rendering of the index
and nothing else - one index read and one request-list read per return, and
the refresh hands that one read to both the list and the README; a copy
names a request only by its own name, so a bare prefix or a deleted request
reads "Other document", never a guessed request; the requests a
consolidated statement answers read received inside it, naming no request;
a filed original that comes back into the inbox is still received; and a
README that cannot be rewritten is said by its class, never its path, while
the refresh never raises.

These tests came from ``tests/test_filer.py`` with the code they drive
(SPEC-architecture-p4 P4.8, P334): each one whose highest home, by section
4.1's rule, is ``tracker/readme_ack.py``, cut and pasted with its name. The
helpers they share with ``tests/test_filer.py`` - ``DAY3``,
``events_named``, ``open_intents``, ``_status``, ``MORTGAGE``,
``_filed_1098`` and ``_a_pass`` - are ``tests/filer_helpers.py``'s now, and
so are ``originals`` and the refused read's fabricated client path.
Decision 130's and decision 193's section headers, which headed only tests
that moved, came with them; the section comments the others sat under stay
in ``tests/test_filer.py`` above the tests of those sections that stay.
Three of them drive the code through a pass or a scan, as they did; the
claim each makes is about the code here.
"""

import os
from pathlib import Path

from tests.builders import (
    DAY1,
    DAY2,
    ITEMS,
    _consolidated_return,
    drop,
    engagement_fixture,
    make_engagement,
    sort,
)
from tests.filer_helpers import (
    A_CLIENT_PATH,
    DAY3,
    _a_pass,
    _filed_1098,
    _logged_outside_the_debug_log,
    _refused_with_a_client_path,
    _status,
    events_named,
    open_intents,
    originals,
)
from tracker import ledger, store, store_check
from tracker.index import FILED, read_index
from tracker.layout import household_of, inbox_of, location_of
from tracker.manifest import RequestItem
from tracker.records import ledger_key
from tracker.scaffold import PREPARED_DIR_NAME, REVIEW_DIR_NAME

engagement = engagement_fixture(ITEMS)


# ============== what we have received (decision 130) ======================


def test_received_for_reads_each_index_once(tmp_path, monkeypatch):
    """The README's received list is a rendering of the index and nothing
    else (S-2): one index read and one request-list read per return, and
    no second copy anywhere."""
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.intents as intents_module
    import tracker.readme_ack as readme_ack_module
    from tests.builders import seed_index
    from tracker.readme_ack import received_for
    from tracker.records import IndexEntry

    items = [RequestItem(identifier="A01", document="W-2")]
    first = make_engagement(tmp_path, items, return_name="1040 - First")
    second = make_engagement(tmp_path, items, return_name="1040 - Second")
    for folder in (first, second):
        seed_index(folder, [IndexEntry(
            received="2026-09-23", original_name="w2.pdf", size_kb=1.0, digest=("1" if folder == first else "2") * 64,
            identifier="A01", prepared_location="PBC/A01 - W-2/A01 - W-2.pdf",
            pbc_location=location_of(folder, originals(folder) / f"w2 {folder.name}.pdf"),
            decision=FILED, reason="")])

    read = []
    lists = []
    real_read, real_list = filer_module.read_index, filer_module.load_manifest
    for module in (filer_module, copies_module, intents_module, readme_ack_module, actions_module):
        monkeypatch.setattr(module, "read_index",
                            lambda folder: read.append(Path(folder)) or real_read(folder))
    for module in (filer_module, readme_ack_module, actions_module):
        monkeypatch.setattr(module, "load_manifest",
                            lambda folder: lists.append(Path(folder)) or real_list(folder))

    received = received_for([first, second])

    assert read == [first, second]
    assert lists == [first, second]
    assert [(line.return_path, line.label) for line in received.lines] == [
        (first, "A01 - W-2"), (second, "A01 - W-2")]
    assert received.under_review == ()

    # And the refresh reads each return's details and list once, handing
    # that one read to both received_for and write_readme (the review's F3).
    import tracker.scaffold as scaffold_module
    from tracker.layout import household_of
    from tracker.readme_ack import refresh_household_readme

    read.clear()
    lists.clear()
    details = []
    real_scaffold_list = scaffold_module.load_manifest
    real_details = scaffold_module.load_engagement_info
    monkeypatch.setattr(scaffold_module, "load_manifest",
                        lambda folder: lists.append(Path(folder)) or real_scaffold_list(folder))
    monkeypatch.setattr(scaffold_module, "load_engagement_info",
                        lambda folder: details.append(Path(folder)) or real_details(folder))

    assert refresh_household_readme(household_of(first)) is not None

    assert sorted(read) == sorted([first, second])
    assert sorted(lists) == sorted([first, second])
    assert sorted(details) == sorted([first, second])


def test_a_second_copy_whose_request_was_deleted_reads_other_document_never_another_request(
        tmp_path):
    """The review's F1 (decision 130). A two-form page was filed under A02
    with a second copy under A01-B; A01-B has since been deleted from the
    list. The copy's folder, ``A01-B - Loan Statement``, starts with
    ``A01`` - but a bare prefix proves nothing, and the README must never
    tell the client their W-2 arrived when none did. A copy names a request
    only when its folder is that request's own folder name, or the text
    after the identifier begins with the label separator. Since decision
    168 the test is made of the copy's own name, in Prepared itself."""
    from tests.builders import seed_index
    from tracker.readme_ack import received_for
    from tracker.records import IndexEntry
    from tracker.scaffold import OTHER_DOCUMENT, PREPARED_DIR_NAME

    items = [RequestItem(identifier="A01", document="W-2 Wage Statement"),
             RequestItem(identifier="A02", document="1098 Mortgage Interest")]
    engagement = make_engagement(tmp_path, items, return_name="1040 - Smith")
    seed_index(engagement, [IndexEntry(
        received="2026-09-23", original_name="combo.pdf", size_kb=12.0,
        digest="c" * 64, identifier="A02",
        prepared_location=f"{PREPARED_DIR_NAME}/A02 - 1098 Mortgage Interest.pdf",
        pbc_location=location_of(engagement, originals(engagement) / "combo.pdf"), decision=FILED, reason="a reason",
        also_filed=f"{PREPARED_DIR_NAME}/A01-B - Loan Statement.pdf")])

    labels = [line.label for line in received_for([engagement]).lines]

    assert labels == ["A02 - 1098 Mortgage Interest", OTHER_DOCUMENT]
    assert "A01 - W-2 Wage Statement" not in labels

    # A copy a person renamed within the shape still names its request.
    seed_index(engagement, [IndexEntry(
        received="2026-09-24", original_name="combo2.pdf", size_kb=12.0,
        digest="e" * 64, identifier="A02",
        prepared_location=f"{PREPARED_DIR_NAME}/A02 - 1098 Mortgage Interest (2).pdf",
        pbc_location=location_of(engagement, originals(engagement) / "combo2.pdf"), decision=FILED, reason="a reason",
        also_filed=f"{PREPARED_DIR_NAME}/a01 - my w2s.pdf")])

    labels = [line.label for line in received_for([engagement]).lines]

    assert labels.count("A01 - W-2 Wage Statement") == 1


def test_the_statement_answers_the_int_div_row_and_the_letter_does_not_ask_for_it(tmp_path):
    """d146, claim 6. E01 holds the one copy; A02 (its interest and dividend
    sections) and A04 (its miscellaneous section) read Received, each saying
    it is in E01's consolidated statement, and neither folder holds a file.
    The letter asks for none of them, the client's received list shows each
    as included in their consolidated brokerage statement - naming no
    request, in the client's words (Jason's Q-L) - and a store rebuilt from
    the journal agrees with the live one."""
    from tracker.layout import root_of
    from tracker.manifest import Status
    from tracker.readme_ack import received_for
    from tracker.reasons import IN_CONSOLIDATED, IN_CONSOLIDATED_CLIENT
    from tracker.reminder import draft_reminder
    from tracker.scaffold import write_readme

    engagement = _consolidated_return(tmp_path)
    [row] = [r for r in read_index(engagement) if r.decision == FILED]
    assert row.identifier == "E01" and row.also_filed == ""
    assert row.answers == "A02 (1099-int, 1099-div); A04 (1099-misc)"

    prepared = engagement / PREPARED_DIR_NAME
    copies = [p for p in prepared.rglob("*.pdf") if REVIEW_DIR_NAME not in p.parts]
    assert len(copies) == 1 and copies[0].parent == prepared and copies[0].name.startswith("E01 - ")

    for identifier, count in (("E01", 1), ("A02", 2), ("A04", 1)):
        item = _status(engagement, identifier)
        assert item.status == Status.RECEIVED, (identifier, item.validation_notes)
        assert item.file_count == count
    assert IN_CONSOLIDATED.format(row="E01") in _status(engagement, "A02").validation_notes
    assert IN_CONSOLIDATED.format(row="E01") in _status(engagement, "A04").validation_notes

    draft = draft_reminder(engagement, today=DAY1)
    assert not {"E01", "A02", "A04"} & set(draft.asked)
    assert not {"E01", "A02", "A04"} & {flag.item.identifier for flag in draft.held}

    received = received_for([engagement])
    inside = {line.identifier: line.inside for line in received.lines}
    e01 = _status(engagement, "E01").label
    assert inside == {"E01": "", "A02": e01, "A04": e01}
    household = engagement.parents[1]
    text = write_readme(household, received).read_text(encoding="utf-8")
    for identifier in ("A02", "A04"):
        label = _status(engagement, identifier).label
        [said] = [one for one in text.splitlines() if one.strip().startswith(label)]
        assert said.endswith(f", {IN_CONSOLIDATED_CLIENT}"), said
    assert text.count(IN_CONSOLIDATED_CLIENT) == 2
    assert IN_CONSOLIDATED.format(row=e01) not in text
    assert IN_CONSOLIDATED.format(row="E01") not in text
    assert "'s consolidated" not in text

    root = root_of(engagement)
    live = store.connect()
    assert store_check.check(live, root, engagement) == []
    db = os.environ[store.ENV_STORE]
    store.close()
    os.unlink(db)
    fresh = store.connect()
    store.rebuild_engagement(fresh, root, engagement)
    assert [r.answers for r in read_index(engagement) if r.decision == FILED] == [row.answers]
    assert _status(engagement, "A02").status == Status.RECEIVED
    assert store_check.check(fresh, root, engagement) == []


def test_an_also_filed_copy_is_read_back_by_its_own_name(engagement):
    """Claim 4: decision 94's two-form page counts once under each request
    in the received list, read from each copy's own name; and a copy whose
    name a person changed to one no request begins reads "Other
    document", never a guessed request."""
    from tests.builders import seed_index
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.readme_ack import received_for
    from tracker.records import IndexEntry
    from tracker.scaffold import OTHER_DOCUMENT

    drop(engagement, "scan0003.pdf", "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    (entry,) = sort(engagement, today=DAY1).filed
    assert [location.rsplit("/", 1)[-1] for location in entry.filed_locations] == [
        "A01 - W-2 Wage Statements - TY2025.pdf", "C01 - Mortgage Interest - TY2025.pdf"]

    labels = [line.label for line in received_for([engagement]).lines]
    assert sorted(labels) == sorted(item.label for item in ITEMS)

    seed_index(engagement, [IndexEntry(
        received="2026-07-09", original_name="combo.pdf", size_kb=12.0,
        digest="c" * 64, identifier="A01",
        prepared_location=f"{PREPARED_DIR_NAME}/A01 - W-2 Wage Statements - TY2025 (2).pdf",
        pbc_location=location_of(engagement, originals(engagement) / "combo.pdf"), decision=FILED, reason="a reason",
        also_filed=f"{PREPARED_DIR_NAME}/the 1098 I renamed.pdf")])
    labels = [line.label for line in received_for([engagement]).lines]
    assert labels.count(OTHER_DOCUMENT) == 1
    assert labels.count(ITEMS[1].label) == 1                 # only the real copy's


def test_a_copy_cut_to_its_identifier_alone_still_reads_under_its_request():
    """The review of 168, N-4: decision 131's room can cut a short name away
    whole on a row with no period, leaving ``A01.pdf`` or ``A01 (2).pdf``.
    Such a copy still names its request - its stem is the identifier alone,
    or the identifier and a number - and the longest identifier wins, as it
    does for every file; a bare prefix still proves nothing."""
    from tracker.readme_ack import _request_of_copy

    items = [RequestItem(identifier="A01", document="W-2"),
             RequestItem(identifier="A01-B", document="Loan")]
    assert _request_of_copy("A01.pdf", items) == "A01"
    assert _request_of_copy("a01 (2).pdf", items) == "A01"
    assert _request_of_copy("A01-B.pdf", items) == "A01-B"
    assert _request_of_copy("A01-B (3).pdf", items) == "A01-B"
    assert _request_of_copy("A01 - W-2 - TY2025.pdf", items) == "A01"
    assert _request_of_copy("A01x.pdf", items) == ""
    assert _request_of_copy("A01-C.pdf", items) == ""           # a bare prefix: nobody's
    assert _request_of_copy("A01B - Loan.pdf", items) == ""


def test_an_original_dragged_back_into_the_inbox_returns_to_its_place(engagement):
    """d157, claim 4 (the audit's C5). Drive undoes a refused move, or a
    colleague drags the filed 1098 back into the drop folder. It is that
    row's own original coming back, so it goes back to the very place the
    row names, as one intent, and no new row is written: the Filed row
    keeps its place and gains one sentence. The pass does not end saying
    the original is missing, and the next pass has nothing to say. Until
    157 it was filed as a Duplicate at the same place, which replaced the
    Filed row, the client's README said the 1098 never arrived, and every
    pass warned about an unrecorded copy."""
    from tracker.manifest import Status
    from tracker.readme_ack import received_for

    filed = _filed_1098(engagement)
    original = originals(engagement) / "1098.pdf"
    body = original.read_bytes()
    original.rename(inbox_of(engagement) / "1098.pdf")

    report, _scanned = _a_pass(engagement, DAY2)

    [row] = read_index(engagement)
    assert row.decision == FILED and report.duplicates == []
    assert original.read_bytes() == body
    assert [p.name for p in originals(engagement).iterdir()] == ["1098.pdf"]
    assert not (inbox_of(engagement) / "1098.pdf").exists()
    from tracker.filer import RETURNED_SENTENCE

    sentence = RETURNED_SENTENCE.format(drop="1098.pdf", date=DAY2.isoformat(),
                                        pbc=filed.pbc_location)
    assert row.reason == f"{filed.reason}; {sentence}"
    assert ledger_key(row) == ledger_key(filed)
    assert report.duplicates == [] and report.filed == []
    assert [e.error for e in report.attention] == [sentence]     # no MISSING_IN_PBC left behind
    assert len(events_named(engagement, ledger.ORIGINAL_RETURNED)) == 1
    assert _status(engagement, "C01").status == Status.RECEIVED
    assert "C01" in {line.identifier for line in received_for([engagement]).lines}
    assert open_intents(engagement) == []

    quiet, _ = _a_pass(engagement, DAY3)
    assert quiet.attention == [] and quiet.errors == []


def test_a_readme_refresh_that_fails_logs_the_class_never_the_path(engagement, monkeypatch, caplog):
    """The README refresh's warning names the error by its class and errno,
    never its message, which here is a client's folder (decision 190, the
    review's S1); the words go to the debug log alone."""
    import logging

    import tracker.readme_ack as readme_ack

    monkeypatch.setattr(readme_ack, "readme_returns", _refused_with_a_client_path)
    with caplog.at_level(logging.DEBUG):
        assert readme_ack.refresh_household_readme(household_of(engagement)) is None
    logged = _logged_outside_the_debug_log(caplog)
    assert "PermissionError (EACCES)" in logged, logged
    assert A_CLIENT_PATH not in logged and "Test Household/Drop" not in logged, logged


# ------------------------------- said, never silent (decision 193) ----


def test_a_readme_that_cannot_be_rewritten_is_said_by_class(engagement, monkeypatch, caplog):
    import errno

    import tracker.readme_ack as readme_ack_module
    from tracker.readme_ack import README_NOT_REWRITTEN, refresh_household_readme

    def denied(*args, **kwargs):
        raise PermissionError(errno.EACCES, "a fabricated denial", str(engagement))

    monkeypatch.setattr(readme_ack_module, "write_readme", denied)
    said: list[str] = []
    assert refresh_household_readme(household_of(engagement), said=said) is None
    assert said == [README_NOT_REWRITTEN.format(kind="PermissionError (EACCES)")]
    assert "fabricated denial" in caplog.text            # the whole of it, in the log only
    assert refresh_household_readme(household_of(engagement)) is None   # no list: a log line
