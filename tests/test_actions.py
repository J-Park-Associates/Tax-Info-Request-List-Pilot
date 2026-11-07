"""Tests for tracker/actions.py - a person's actions on the record, and the re-scan after them.

The promises being tested: a person's filing, setting aside, unfiling, Mark
missing, put-back and rename are each one decision, recorded as that
person's in one transaction with what it taught; each is judged against the
row the person saw (decision 112) and refuses, touching nothing, while a
move is open or the row has moved on; none of them overwrites, deletes or
guesses - a home holding a different file keeps it, a re-saved working copy
is left and said, and a copy deleted by hand is made again from the proved
original (decisions 110 and 157); a run killed in the middle of one is
finished forward from the record by the next pass, nothing lost and nothing
doubled (decision 119); and a rename moves a request's copies with it in one
act, or refuses and moves nothing (decision 160).

These tests came from ``tests/test_filer.py`` with the code they drive
(SPEC-architecture-p4 P4.9, P335): each one whose highest home, by section
4.1's rule, is ``tracker/actions.py``, cut and pasted with its name, in the
order they stood. The helpers only they read came with them. The helpers
they share with ``tests/test_filer.py`` - the conservation checks and the
crash points' kills, the sequence number a person's action carries, the
dragging hand, the hash counter, the household feed and its one click, and
the few others ``tests/filer_helpers.py``'s docstring names - are
``tests/filer_helpers.py``'s now. Decision 112's and decision 110's section
headers, which headed only tests that moved, came with them; the section
comments the others sat under stay in ``tests/test_filer.py`` above the
tests of those sections that stay. Many of them drive the code through a
pass first, to park or file the document a person then acts on; the claim
each makes is about the action.
"""

import datetime as dt
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from tests import filer_helpers
from tests.builders import (
    BUSINESS,
    DAY1,
    DAY2,
    FOLDER_BELOW,
    ITEMS,
    LONG_PERIOD,
    OVER,
    ROOM_ITEMS,
    TEST_CLIENT,
    TEST_YEAR,
    TIGHT_PERIOD,
    _consolidated_return,
    drop,
    engagement_fixture,
    killed_at_the_record,
    make_engagement,
    no_room_prepared,
    no_room_return,
    original_at,
    sort,
    sort_all,
    tight_return,
)
from tests.filer_helpers import (
    DAY3,
    JOHN,
    _a_pass,
    _asked,
    _filed_1098,
    _only_the_review_folder,
    _review_folder_files,
    _status,
    click,
    conserved,
    counted_records,
    counting_hashes,
    digests_under,
    drag,
    events_named,
    files_under,
    kept_files,
    killed_after_ops,
    killed_after_the_move,
    killed_at_the_intent,
    moves_made,
    open_intents,
    originals,
    parked_notice,
    prepared,
    review_dir,
    rows_rest_at_home,
    seq_of,
)
from tests.samples import text_pdf
from tracker import ledger, reasons, store, store_check
from tracker.copies import FilingError
from tracker.index import DUPLICATE, FILED, NEEDS_REVIEW, read_index
from tracker.layout import inbox_of, locate, location_of, root_of
from tracker.manifest import (
    RequestItem,
    load_engagement_info,
    load_manifest,
    save_rules,
)
from tracker.records import ledger_key, rule_from_json, rule_to_json
from tracker.router import UNMATCHED
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
)

engagement = engagement_fixture(ITEMS)

#: The father's household feeding the co-owned LLC's return line, from
#: ``tests/filer_helpers.py``: named once so that a test here can ask for it.
fed = filer_helpers.fed


def test_a_person_filing_dismissing_or_unfiling_is_one_call_each(engagement, monkeypatch):
    from tracker.actions import assign_review_file, dismiss_review_file, unfile_document

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "notice.pdf", "an agency notice nothing asks for")
    parked = {e.original_name: e for e in sort(engagement, today=DAY1).review}
    calls = counted_records(monkeypatch)

    assign_review_file(engagement, parked["scan0012.pdf"].pbc_location, "C01", today=DAY2)
    dismiss_review_file(engagement, parked["notice.pdf"].pbc_location, today=DAY2)
    unfile_document(engagement, parked["scan0012.pdf"].pbc_location, today=DAY2)

    # The unfiling's re-scan is a call of its own, and rightly: it is the
    # pass's decision about the request, not the person's about the row.
    # Each action that moves a file writes its intent first (decision 119)
    # and dismissing moves nothing, so it writes none.
    assert calls == [(ledger.MOVING,), (ledger.ASSIGNED_BY_PERSON,),
                     (ledger.DISMISSED_BY_PERSON,),
                     (ledger.MOVING,), (ledger.UNFILED_BY_PERSON,), (ledger.SCANNED,)]


def test_a_persons_keyword_is_recorded_in_the_same_call_as_the_filing(engagement, monkeypatch):
    """One decision, one call, one transaction (decision 103).

    The filing and the word it taught are the same decision, so they are
    the same ``store.record()`` - which means the rollback that puts a
    moved file back asks one question and not two. The word is recorded,
    never typed into the row: the rules the record holds are as they were.
    """
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    before = store.rules(store.connect(), engagement)
    calls = counted_records(monkeypatch)

    result = assign_review_file(engagement, parked.pbc_location, "C01", keyword="lender")

    assert result.keyword == "lender" and result.keyword_note == ""
    # The intent goes down before the copy moves and carries the keyword
    # with it (decision 119), so a filing finished from the record teaches
    # the request the word as well; the decision itself is still one call.
    assert calls == [(ledger.MOVING,), (ledger.ASSIGNED_BY_PERSON, ledger.KEYWORD_LEARNED)]
    assert store.rules(store.connect(), engagement) == before
    assert {i.identifier: i.any_keywords for i in load_manifest(engagement)}["C01"] == ("lender",)


def test_a_keyword_the_request_already_has_is_said_and_not_recorded_twice(engagement, monkeypatch):
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "notice.pdf", "an agency notice nothing asks for")
    parked = {e.original_name: e for e in sort(engagement, today=DAY1).review}
    assign_review_file(engagement, parked["scan0012.pdf"].pbc_location, "C01", keyword="lender")
    calls = counted_records(monkeypatch)

    again = assign_review_file(engagement, parked["notice.pdf"].pbc_location, "C01",
                               keyword="LENDER", today=DAY2)

    assert again.keyword == "" and "already had the keyword" in again.keyword_note
    assert calls == [(ledger.MOVING,), (ledger.ASSIGNED_BY_PERSON,)]


def test_assigning_a_parked_file_moves_it_under_the_canonical_name(engagement):
    from tracker.actions import assign_review_file
    from tracker.filer import ASSIGNED_BY_PERSON

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    review_copy = engagement / parked.prepared_location
    assert review_copy.exists()

    result = assign_review_file(engagement, parked.pbc_location, "C01", keyword="Home Lending", today=DAY2)

    assert result.moved_review_copy is True
    assert not review_copy.exists()
    working = engagement / result.entry.prepared_location
    assert working.name == "C01 - Mortgage Interest - TY2025.pdf"
    assert working.read_bytes() == (engagement / parked.pbc_location).read_bytes()
    assert (engagement / parked.pbc_location).exists()               # original untouched
    [row] = read_index(engagement)
    assert row.decision == FILED and row.identifier == "C01"
    assert row.reason.startswith(f"{ASSIGNED_BY_PERSON} on {DAY2.isoformat()}; was: ")
    assert result.keyword == "Home Lending" and result.keyword_note == ""
    from tracker.manifest import load_manifest
    assert next(i for i in load_manifest(engagement) if i.identifier == "C01").any_keywords == ("Home Lending",)


def test_assigning_copies_from_pbc_when_the_review_copy_is_gone(engagement):
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    (engagement / parked.prepared_location).unlink()
    result = assign_review_file(engagement, "scan0012.pdf", "A01")   # by original name
    assert result.moved_review_copy is False
    assert (engagement / result.entry.prepared_location).exists()


def test_assigning_refuses_what_a_person_should_not_do(engagement):
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    with pytest.raises(FilingError, match="no request 'Z99'"):
        assign_review_file(engagement, "scan0012.pdf", "Z99")
    with pytest.raises(FilingError, match="is not waiting for review"):
        assign_review_file(engagement, "w2.pdf", "C01")               # already filed
    with pytest.raises(FilingError, match="nothing in the index is called"):
        assign_review_file(engagement, "ghost.pdf", "C01")


def test_filing_to_a_not_applicable_row_is_refused_with_its_label(tmp_path):
    from tracker.actions import assign_review_file
    from tracker.manifest import Override

    set_aside = make_engagement(tmp_path / "Set aside 2025", [
        RequestItem(identifier="A01", document="W-2", period="TY2025",
                    manual_override=Override.NOT_APPLICABLE)])
    drop(set_aside, "x.pdf", "nothing")
    sort(set_aside, today=DAY1)
    with pytest.raises(FilingError, match="A01 is Not Applicable in TY2025; clear the override first"):
        assign_review_file(set_aside, "x.pdf", "A01")


def test_a_failed_record_puts_the_filed_copy_back_where_the_record_says(engagement, monkeypatch):
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    def disk_full(*args, **kwargs):
        raise OSError(28, "No space left on device")
    # One transaction: it either committed or it did not, and it did not,
    # so the copy goes back to review and a retry files it once.
    monkeypatch.setattr(store, "record", disk_full)
    with pytest.raises(OSError):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    monkeypatch.undo()
    assert (engagement / parked.prepared_location).exists()
    c01 = engagement / PREPARED_DIR_NAME / "C01 - Mortgage Interest"
    assert not c01.exists() or not any(c01.iterdir())

    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    assert result.moved_review_copy is True
    assert [p.name for p in prepared(engagement, "C01").iterdir()] == [result.entry.filed_as]


def test_an_interrupt_after_the_record_landed_does_not_undo_the_filing(engagement, monkeypatch):
    # The transaction committed and then the interrupt hit. The record says
    # Filed at the request folder, so the copy stays there - moving it back
    # would leave the record lying about where the document is.
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    real = store.record

    def interrupted(conn, engagement_dir, *events):
        # After the decision's own record, not after the intent it wrote
        # before it moved anything (decision 119): the claim is about a
        # transaction that committed.
        real(conn, engagement_dir, *events)
        if events[0][ledger.EVENT_KEY] != ledger.MOVING:
            raise KeyboardInterrupt
    monkeypatch.setattr(store, "record", interrupted)
    with pytest.raises(KeyboardInterrupt):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    monkeypatch.undo()
    [row] = read_index(engagement)
    assert row.decision == FILED and (engagement / row.prepared_location).exists()
    assert not (engagement / parked.prepared_location).exists()


def test_assigning_reuses_a_copy_an_earlier_attempt_left_and_leaves_no_half_copy(engagement, monkeypatch):
    # The same two guarantees the sort path has (decisions 54, 56), on the
    # path a person drives: a kill after the move made a copy the index
    # never learned of, and a copy that fails half-way leaves nothing.
    import tracker.filer as filer_module
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    c01 = prepared(engagement, "C01")
    earlier = engagement / PREPARED_DIR_NAME / "C01 - Mortgage Interest - TY2025.pdf"
    (engagement / parked.prepared_location).rename(earlier)      # the killed attempt's move
    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    assert [p.name for p in c01.iterdir()] == [earlier.name] and result.entry.filed_as == earlier.name

    drop(engagement, "scan0013.pdf", "nothing the rules recognise either")
    parked = sort(engagement, today=DAY2).review[0]
    (engagement / parked.prepared_location).unlink()             # a person removed the parked copy

    def half(src, dst):
        filer_module.Path(dst).write_bytes(b"%PDF-1.4 half")
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(shutil, "copy2", half)
    with pytest.raises(OSError):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    monkeypatch.undo()
    assert [p.name for p in c01.iterdir()] == [earlier.name]     # no half copy beside it


def test_a_persons_filing_of_an_original_recorded_without_its_bytes_records_them(engagement, monkeypatch):
    # Decision 65 records an original the pass could not read back with no
    # digest. The ninth reading found that row carried through a person's
    # filing with no digest still, so the scanner never honoured the person
    # and the client was asked again. Assign records the bytes; and a later
    # pass that can read the original records them too.
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module
    from tracker.actions import assign_review_file
    from tracker.validators import sha256_of

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    real = filer_module.sha256_of

    held = set()

    def unreadable_once(path):
        if path.parent == originals(engagement) and path not in held:
            # Held for the one read that records the row: since decision
            # 187 the intent fingerprints a copy's source itself, a moment
            # later, so the copy is proved and the row keeps no bytes.
            held.add(path)
            raise PermissionError("held by the sync client")
        return real(path)
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "sha256_of", unreadable_once)
    parked = sort(engagement, today=DAY1).review[0]
    monkeypatch.undo()
    assert parked.digest == "" and parked.size_kb == 0.0

    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    original = engagement / parked.pbc_location
    assert result.entry.digest == sha256_of(original) and result.entry.size_kb > 0
    (row,) = read_index(engagement)
    assert row.digest == result.entry.digest

    # And a pass, with nothing to sort, fills in the row the earlier pass could not.
    drop(engagement, "scan0013.pdf", "nothing the rules recognise either")
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "sha256_of", unreadable_once)
    sort(engagement, today=DAY2)
    monkeypatch.undo()
    assert [r.digest for r in read_index(engagement) if r.original_name == "scan0013.pdf"] == [""]
    sort(engagement, today=DAY2)
    later = next(r for r in read_index(engagement) if r.original_name == "scan0013.pdf")
    assert later.digest == sha256_of(engagement / later.pbc_location) and later.size_kb > 0


def test_bytes_recorded_after_the_fact_are_tied_to_the_row_or_not_recorded(engagement, monkeypatch):
    # The tenth reading: the digest filled in on a later pass came from the
    # original as it was THEN, so a client's replacement was adopted into
    # the old row. The eleventh: the working copy alone is no better - its
    # name is the client's and a freed name is taken by the next drop
    # called the same. A row is tied to its bytes only while its copy and
    # its original still agree; where they do not, nothing is adopted and
    # the row is said out loud, every pass.
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module
    from tracker.actions import assign_review_file
    from tracker.filer import UNTIED_IN_PBC
    from tracker.validators import sha256_of

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "scan0013.pdf", "nothing the rules recognise either")
    real = filer_module.sha256_of

    held = set()

    def unreadable(path):
        if path.parent == originals(engagement) and path not in held:
            # Held for the one read that records the row: since decision
            # 187 the intent fingerprints a copy's source itself, a moment
            # later, so the copy is proved and the row keeps no bytes.
            held.add(path)
            raise PermissionError("held by the sync client")
        return real(path)
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "sha256_of", unreadable)
    report = sort(engagement, today=DAY1)
    monkeypatch.undo()
    filed = report.filed[0]
    parked = {r.original_name: r for r in report.review}
    assert filed.digest == "" and all(r.digest == "" for r in parked.values())
    first_bytes = (engagement / filed.prepared_location).read_bytes()

    # The client replaces the W-2 under its own name; a reviewer's app re-saves scan0012's parked copy.
    text_pdf(originals(engagement) / "w2.pdf", "Form W-2 Wage and Tax Statement 2025 corrected")
    text_pdf(engagement / parked["scan0012.pdf"].prepared_location, "nothing the rules recognise, annotated")

    report = sort(engagement, today=DAY2)
    rows = {r.original_name: r for r in read_index(engagement)}
    assert rows["w2.pdf"].digest == "" and rows["scan0012.pdf"].digest == ""              # nothing adopted
    assert rows["scan0013.pdf"].digest == sha256_of(originals(engagement) / "scan0013.pdf")   # tied: copy and original agree
    assert (engagement / filed.prepared_location).read_bytes() == first_bytes            # untouched
    said = sorted(e.name for e in report.attention if e.error.startswith(UNTIED_IN_PBC.split("{")[0]))
    assert said == ["scan0012.pdf", "w2.pdf"] and report.errors == []   # for a person, not a failed pass

    # A person cannot file either untied row under it; the tied one files and carries its bytes.
    with pytest.raises(FilingError, match="look at both files first"):
        assign_review_file(engagement, parked["scan0012.pdf"].pbc_location, "C01", today=DAY2)
    result = assign_review_file(engagement, parked["scan0013.pdf"].pbc_location, "C01", today=DAY2)
    assert result.entry.digest == rows["scan0013.pdf"].digest


def test_a_persons_filing_moves_the_parked_copy_only_while_it_holds_the_rows_bytes(engagement):
    # The eleventh reading: a parked name is the client's, so once row A's
    # copy is gone the next drop called the same parks under that very
    # path, and filing row A carried document B into the request folder
    # under A's canonical name.
    #
    # Since decision 157 the pass makes a parked copy that went again from
    # its original before it parks anything, so the freed name is taken
    # only while A's original cannot be read - still syncing, here.
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module
    from tracker.actions import assign_review_file
    from tracker.validators import sha256_of

    drop(engagement, "Scan.pdf", "document A, nothing the rules recognise")
    row_a = sort(engagement, today=DAY1).review[0]
    (engagement / row_a.prepared_location).unlink()                  # a person took it away to read
    drop(engagement, "Scan.pdf", "document B, unrelated")
    syncing = locate(engagement, row_a.pbc_location)
    real = filer_module.is_cloud_placeholder
    with pytest.MonkeyPatch.context() as sync:
        for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
            sync.setattr(module, "is_cloud_placeholder", lambda p: p == syncing or real(p))
        row_b = sort(engagement, today=DAY2).review[0]
    assert row_b.prepared_location == row_a.prepared_location         # the freed name, taken

    result = assign_review_file(engagement, row_a.pbc_location, "C01", today=DAY2)
    filed = engagement / result.entry.prepared_location
    assert result.moved_review_copy is False
    assert sha256_of(filed) == row_a.digest                            # document A, copied from its original
    assert (engagement / row_b.prepared_location).exists()            # document B still waits for a person
    assert sha256_of(engagement / row_b.prepared_location) == row_b.digest


def test_a_parked_path_a_later_row_claims_means_the_earlier_copy_is_gone(engagement, monkeypatch):
    # The twelfth reading: a digest-less row A whose parked copy a person
    # removed, then a same-named drop B parked under the freed name, was
    # "untied" every pass and refused for ever - though the index itself
    # says whose the file at that path is.
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module
    from tracker.actions import assign_review_file
    from tracker.validators import sha256_of

    drop(engagement, "Scan.pdf", "document A, nothing the rules recognise")
    real = filer_module.sha256_of

    held = set()

    def unreadable(path):
        if path.parent == originals(engagement) and path not in held:
            # Held for the one read that records the row: since decision
            # 187 the intent fingerprints a copy's source itself, a moment
            # later, so the copy is proved and the row keeps no bytes.
            held.add(path)
            raise PermissionError("held by the sync client")
        return real(path)
    for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
        monkeypatch.setattr(module, "sha256_of", unreadable)
    row_a = sort(engagement, today=DAY1).review[0]
    monkeypatch.undo()
    assert row_a.digest == ""
    (engagement / row_a.prepared_location).unlink()
    drop(engagement, "Scan.pdf", "document B, unrelated")
    report = sort(engagement, today=DAY2)
    row_b = report.review[0]
    assert row_b.prepared_location == row_a.prepared_location
    assert report.attention == [] and report.errors == []          # not untied: its copy is gone

    result = assign_review_file(engagement, row_a.pbc_location, "C01", today=DAY2)
    assert result.entry.digest == sha256_of(originals(engagement) / "Scan.pdf")   # document A, from its original
    assert sha256_of(engagement / result.entry.prepared_location) == result.entry.digest
    assert (engagement / row_b.prepared_location).exists()          # document B still waits


def test_an_annotated_parked_copy_is_left_behind_and_said_so(engagement):
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    text_pdf(engagement / parked.prepared_location, "nothing the rules recognise, with a reviewer's note")
    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    assert result.moved_review_copy is False and "left there" in result.left_in_review
    assert (engagement / parked.prepared_location).exists()
    assert (engagement / result.entry.prepared_location).read_bytes() == (originals(engagement) / "scan0012.pdf").read_bytes()


def test_assigning_a_replaced_original_is_refused_not_recorded_under_the_old_bytes(engagement):
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    (engagement / parked.prepared_location).unlink()             # the parked copy is gone
    text_pdf(originals(engagement) / "scan0012.pdf", "the client replaced it with something else")
    with pytest.raises(FilingError, match="replaced after it arrived"):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.digest == parked.digest


def test_a_failed_record_puts_back_a_parked_copy_a_reused_one_stood_in_for(engagement, monkeypatch):
    # Assign reuses a killed attempt's copy and removes the parked one it
    # stands in for (decision 69). The rollback covered the moved copy and
    # the fresh copy but not that removal, so a refused write left the row
    # still naming a parked copy that was no longer there.
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    c01 = engagement / PREPARED_DIR_NAME / "C01 - Mortgage Interest"
    c01.mkdir(parents=True, exist_ok=True)
    attempt = c01 / "C01 - Mortgage Interest - TY2025.pdf"
    attempt.write_bytes((engagement / parked.prepared_location).read_bytes())

    def disk_full(*args, **kwargs):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(store, "record", disk_full)
    with pytest.raises(OSError):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    monkeypatch.undo()

    back = engagement / parked.prepared_location
    assert back.is_file() and back.read_bytes() == attempt.read_bytes()
    assert [p.name for p in c01.iterdir()] == [attempt.name]      # the reused copy stays where it is
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and (engagement / row.prepared_location).is_file()

    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    assert result.entry.filed_as == attempt.name and not back.exists()


def test_dismissing_a_parked_file_rewrites_its_row_and_moves_nothing(engagement):
    """Not Requested is a decision about the request list, not about the file.

    An agency notice the client sent is still the client's: the working copy
    stays parked and the original stays in PBC. What the row says changes,
    and what it said before is kept after it.
    """
    from tracker.actions import dismiss_review_file
    from tracker.filer import DISMISSED_BY_PERSON
    from tracker.index import NOT_REQUESTED

    drop(engagement, "irs-notice.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    copy = engagement / parked.prepared_location
    original = engagement / parked.pbc_location
    assert copy.is_file()

    result = dismiss_review_file(engagement, parked.pbc_location, "an IRS notice", today=DAY2)

    assert result.entry.decision == NOT_REQUESTED
    assert result.entry.reason == (
        f"{DISMISSED_BY_PERSON} on {DAY2.isoformat()} (an IRS notice); was: {parked.reason}"
    )
    assert copy.is_file() and copy.read_bytes() == original.read_bytes()
    assert original.is_file()
    [row] = read_index(engagement)
    assert row.decision == NOT_REQUESTED
    assert row.prepared_location == parked.prepared_location


def test_the_same_document_sent_again_after_a_dismissal_parks_again_and_names_the_earlier_decision(
    engagement,
):
    """Not requested is a decision about one document on one day (decision 111).

    The client was never told the document was unnecessary, so they send it
    again; a silent Duplicate would tell nobody. It is routed like any drop,
    and where no request takes it the row says what was decided before -
    the date and the person's note, as they wrote them - so the person who
    set it aside decides again with both facts in front of them.
    """
    from tracker.actions import dismiss_review_file
    from tracker.filer import RESENT_AFTER_SET_ASIDE
    from tracker.index import NOT_REQUESTED

    drop(engagement, "notice.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    dismissed = dismiss_review_file(
        engagement, parked.pbc_location, "an IRS notice", today=DAY2
    ).entry
    set_aside_copy = engagement / dismissed.prepared_location
    before = set_aside_copy.read_bytes()

    drop(engagement, "notice.pdf", "nothing the rules recognise")   # same bytes, same name
    report = sort(engagement, today=DAY2)

    (again,) = report.review
    assert report.duplicates == []
    assert again.decision == NEEDS_REVIEW
    assert again.reason.startswith(RESENT_AFTER_SET_ASIDE.format(earlier=dismissed.reason))
    assert DAY2.isoformat() in again.reason and "an IRS notice" in again.reason
    assert UNMATCHED in again.reason                    # and why it parked, as always

    # The set-aside row and its copy are exactly as they were.
    assert set_aside_copy.read_bytes() == before
    rows = read_index(engagement)
    assert [r.decision for r in rows] == [NOT_REQUESTED, NEEDS_REVIEW]
    assert rows[0].reason == dismissed.reason
    assert rows[0].prepared_location == dismissed.prepared_location

    # Two arrivals, two preserved originals, two parked copies - and
    # _unique_path never overwrote the copy that was already there.
    assert kept_files(engagement) == [
        original_at(engagement, "notice (2).pdf"),
        original_at(engagement, "notice.pdf"),
        f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/notice (2).pdf",
        f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/notice.pdf",
    ]


def test_a_resend_after_a_dismissal_owns_its_own_working_copy(engagement):
    """One row, one working copy.

    If the re-parked row named the set-aside row's file, filing either one
    would carry the other's copy out from under it.
    """
    from tracker.actions import assign_review_file, dismiss_review_file

    drop(engagement, "notice.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    dismissed = dismiss_review_file(engagement, parked.pbc_location, today=DAY2).entry
    drop(engagement, "notice.pdf", "nothing the rules recognise")
    again = sort(engagement, today=DAY2).review[0]
    assert again.prepared_location != dismissed.prepared_location
    resent_copy = engagement / again.prepared_location
    before = resent_copy.read_bytes()

    # A person files the *dismissed* row: only its own copy moves.
    result = assign_review_file(engagement, dismissed.pbc_location, "C01", today=DAY2)

    assert result.moved_review_copy is True
    assert not (engagement / dismissed.prepared_location).exists()
    assert resent_copy.is_file() and resent_copy.read_bytes() == before
    still = {r.pbc_location: r for r in read_index(engagement)}[again.pbc_location]
    assert still.decision == NEEDS_REVIEW and still.reason == again.reason
    assert still.prepared_location == again.prepared_location
    assert kept_files(engagement) == [
        original_at(engagement, "notice (2).pdf"),
        original_at(engagement, "notice.pdf"),
        f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/notice (2).pdf",
        f"{PREPARED_DIR_NAME}/{result.entry.filed_as}",
    ]


def test_a_resend_after_a_dismissal_files_when_the_list_now_asks_for_it(engagement):
    """The person may have taught the list since they set it aside.

    Parking what exactly one request now accepts would be guessing that the
    earlier decision still stands over the later rule, so the re-send is
    routed first - and the row still says it was set aside before.
    """
    from tracker.actions import dismiss_review_file
    from tracker.filer import RESENT_AFTER_SET_ASIDE

    drop(engagement, "notice.pdf", "an agency notice about your account, 2025")
    parked = sort(engagement, today=DAY1).review[0]
    dismissed = dismiss_review_file(engagement, parked.pbc_location, today=DAY2).entry

    # A person edits the request list in the app: C01 now asks for it.
    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement)]
    save_rules(engagement, [
        RequestItem(**{**rule_from_json(rule_to_json(row)),
                       "required_keywords": ("agency notice",)})
        if row.identifier == "C01" else row
        for row in rows
    ], load_engagement_info(engagement))

    drop(engagement, "notice.pdf", "an agency notice about your account, 2025")
    report = sort(engagement, today=DAY2)

    (filed,) = report.filed
    assert report.review == [] and report.duplicates == []
    assert filed.identifier == "C01"
    # The re-send is name-checked before it files (decision 128), so the
    # confirmation follows the sentence that says it was set aside.
    assert f"; {RESENT_AFTER_SET_ASIDE.format(earlier=dismissed.reason)}" in filed.reason
    assert filed.reason.endswith(f"; name confirmed ({TEST_CLIENT})")
    copy = engagement / filed.prepared_location
    assert copy.is_file() and copy.read_bytes() == (originals(engagement) / "notice (2).pdf").read_bytes()
    # The set-aside row keeps its own parked copy; only the re-send was filed.
    assert (engagement / dismissed.prepared_location).is_file()
    assert kept_files(engagement) == [
        original_at(engagement, "notice (2).pdf"),
        original_at(engagement, "notice.pdf"),
        f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/notice.pdf",
        f"{PREPARED_DIR_NAME}/{filed.filed_as}",
    ]


def test_set_aside_bytes_sent_again_after_their_original_went_are_routed_afresh(engagement):
    """d157's review, S-2 (its probe P5). The client deletes the original
    of a document a person set aside, the list then gains its request, and
    the client sends the same bytes again. Decision 157's put-back is for a
    row's own original coming home; a set-aside row is a person's answer
    about one day's document, and decision 111 routes the same bytes sent
    again afresh. So the re-send files to the request the list now asks
    for, under a name of its own, the set-aside row stays as it was, and
    the letter no longer asks for a document the client sent twice."""
    from tracker.actions import dismiss_review_file
    from tracker.filer import RESENT_AFTER_SET_ASIDE
    from tracker.index import NOT_REQUESTED
    from tracker.manifest import Status

    drop(engagement, "notice.pdf", "an agency notice about your account, 2025")
    parked = sort(engagement, today=DAY1).review[0]
    dismissed = dismiss_review_file(engagement, parked.pbc_location, today=DAY2).entry

    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement)]
    save_rules(engagement, [
        RequestItem(**{**rule_from_json(rule_to_json(row)),
                       "required_keywords": ("agency notice",)})
        if row.identifier == "C01" else row
        for row in rows
    ], load_engagement_info(engagement))

    (originals(engagement) / "notice.pdf").unlink()
    drop(engagement, "notice.pdf", "an agency notice about your account, 2025")
    report, _scanned = _a_pass(engagement, DAY2)

    (filed,) = report.filed
    assert filed.identifier == "C01" and report.review == [] and report.duplicates == []
    assert f"; {RESENT_AFTER_SET_ASIDE.format(earlier=dismissed.reason)}" in filed.reason
    assert filed.pbc_location == original_at(engagement, "notice (2).pdf")
    assert events_named(engagement, ledger.ORIGINAL_RETURNED) == []
    assert not (originals(engagement) / "notice.pdf").exists()
    [kept] = [row for row in read_index(engagement) if ledger_key(row) == ledger_key(dismissed)]
    assert kept.decision == NOT_REQUESTED
    assert _status(engagement, "C01").status == Status.RECEIVED
    assert "C01" not in _asked(engagement, DAY2)


def test_a_third_send_of_set_aside_bytes_is_a_duplicate_of_the_parked_row(engagement):
    """The queue holds a document once: the second arrival is where the work is."""
    from tracker.actions import dismiss_review_file
    from tracker.filer import DUPLICATE_OF_PARKED

    drop(engagement, "notice.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    dismiss_review_file(engagement, parked.pbc_location, today=DAY2)
    drop(engagement, "notice.pdf", "nothing the rules recognise")
    again = sort(engagement, today=DAY2).review[0]

    drop(engagement, "notice.pdf", "nothing the rules recognise")
    report = sort(engagement, today=DAY2)

    (dup,) = report.duplicates
    assert report.review == []
    assert dup.decision == DUPLICATE and dup.prepared_location == ""
    assert dup.reason == DUPLICATE_OF_PARKED.format(
        name=again.original_name, copy=again.filed_as
    )
    assert sorted(p.name for p in review_dir(engagement).iterdir()) == ["notice (2).pdf", "notice.pdf"]


def test_filing_a_dismissed_document_is_how_the_decision_is_undone(engagement):
    """A person who was wrong files it; there is no second undo path to build."""
    from tracker.actions import assign_review_file, dismiss_review_file
    from tracker.filer import ASSIGNED_BY_PERSON

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    dismiss_review_file(engagement, parked.pbc_location, today=DAY2)

    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)

    assert result.moved_review_copy is True
    assert result.entry.filed_as == "C01 - Mortgage Interest - TY2025.pdf"
    [row] = read_index(engagement)
    assert row.decision == FILED and row.identifier == "C01"
    assert row.reason.startswith(f"{ASSIGNED_BY_PERSON} on {DAY2.isoformat()}; was: ")
    assert (engagement / row.prepared_location).is_file()


def test_dismissing_something_that_is_not_parked_says_what_it_is(engagement):
    """A filed document is not a person's to dismiss without unfiling it first."""
    from tracker.actions import dismiss_review_file

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    with pytest.raises(FilingError, match=f"is not waiting for review \\(it is {FILED}"):
        dismiss_review_file(engagement, "w2.pdf", today=DAY2)
    with pytest.raises(FilingError, match="nothing in the index is called"):
        dismiss_review_file(engagement, "ghost.pdf", today=DAY2)


def test_dismissing_takes_the_engagement_lock(engagement):
    """A decision is written to the index, so it queues behind a run like every other."""
    from tracker.actions import dismiss_review_file
    from tracker.index import NOT_REQUESTED
    from tracker.locking import LOCK_FILENAME, EngagementLockedError

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    (engagement / LOCK_FILENAME).write_text(f"pid={os.getpid()}", encoding="utf-8")
    with pytest.raises(EngagementLockedError):
        dismiss_review_file(engagement, parked.pbc_location, today=DAY2)
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW               # nothing was written

    (engagement / LOCK_FILENAME).unlink()
    result = dismiss_review_file(engagement, parked.pbc_location, today=DAY2)
    assert result.entry.decision == NOT_REQUESTED
    assert not (engagement / LOCK_FILENAME).exists()


def test_unfiling_puts_the_working_copy_back_under_the_clients_own_name(engagement):
    """The parked name is the client's, whichever direction the document travels."""
    from tracker.actions import unfile_document
    from tracker.filer import UNFILED_BY_PERSON

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    working = engagement / filed.prepared_location
    assert working.is_file()

    result = unfile_document(engagement, filed.pbc_location, "wrong client", today=DAY2)

    assert result.moved_working_copy is True and result.left_filed == ""
    assert not working.exists()
    parked = engagement / result.entry.prepared_location
    assert parked.name == "w2 john.pdf" and parked.parent == review_dir(engagement)
    assert parked.read_bytes() == (engagement / filed.pbc_location).read_bytes()
    assert (engagement / filed.pbc_location).is_file()          # the original is untouched
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == ""
    assert row.reason == (
        f"{UNFILED_BY_PERSON} on {DAY2.isoformat()} (wrong client); was: {filed.reason}"
    )


def test_filing_an_unfiled_document_puts_it_under_the_canonical_name_again(engagement):
    """Refiling is unfiling and then filing; there is no third path to keep honest."""
    from tracker.actions import (
        assign_review_file,
        unfile_document,
    )
    from tracker.filer import (
        ASSIGNED_BY_PERSON,
        UNFILED_BY_PERSON,
    )

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    unfile_document(engagement, filed.pbc_location, today=DAY2)

    result = assign_review_file(engagement, filed.pbc_location, "C01", today=DAY2)

    assert result.moved_review_copy is True
    assert result.entry.filed_as == "C01 - Mortgage Interest - TY2025.pdf"
    assert not list(review_dir(engagement).iterdir())
    [row] = read_index(engagement)
    assert row.decision == FILED and row.identifier == "C01"
    assert row.reason.startswith(
        f"{ASSIGNED_BY_PERSON} on {DAY2.isoformat()}; was: {UNFILED_BY_PERSON}"
    )


def test_a_page_that_prints_two_forms_files_a_copy_under_each_and_unfiles_as_one(engagement):
    """Decision 94: one original, one index row, one working copy per request
    that asked for a form the page names - and unfiling takes every copy
    back with the row, because the row is one row."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.actions import unfile_document
    from tracker.validators import sha256_of

    original = drop(engagement, "scan0003.pdf",
                    "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    before = original.read_bytes()

    (entry,) = sort(engagement, today=DAY1).filed

    assert entry.identifier == "A01"
    assert entry.filed_names == [
        "A01 - W-2 Wage Statements - TY2025.pdf",
        "C01 - Mortgage Interest - TY2025.pdf",
    ]
    assert entry.filed_as == entry.filed_names[0]
    copies = [engagement / location for location in entry.filed_locations]
    assert all(copy.read_bytes() == before for copy in copies)
    assert "A01, C01" in entry.reason
    [row] = read_index(engagement)
    assert row.also_filed == entry.also_filed and row.also_filed
    assert row.filed_locations == entry.filed_locations

    unfile_document(engagement, entry.pbc_location, today=DAY2)

    assert not any(copy.exists() for copy in copies)
    [parked] = list(review_dir(engagement).iterdir())
    assert parked.name == "scan0003.pdf" and sha256_of(parked) == entry.digest
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.also_filed == "" and row.identifier == ""


def test_unfiling_something_that_is_not_filed_says_what_it_is(engagement):
    """Each of the other decisions needs a different answer, so none of them is guessed."""
    from tracker.actions import (
        dismiss_review_file,
        unfile_document,
    )
    from tracker.index import NOT_REQUESTED

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    with pytest.raises(FilingError, match=rf"is not filed \(it is {NEEDS_REVIEW}\)"):
        unfile_document(engagement, parked.pbc_location, today=DAY2)

    dismiss_review_file(engagement, parked.pbc_location, today=DAY2)
    with pytest.raises(FilingError, match=rf"is not filed \(it is {NOT_REQUESTED}\)"):
        unfile_document(engagement, parked.pbc_location, today=DAY2)

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025")
    duplicate = sort(engagement, today=DAY2).duplicates[0]
    with pytest.raises(FilingError, match=rf"is not filed \(it is {DUPLICATE}\)"):
        unfile_document(engagement, duplicate.pbc_location, today=DAY2)

    with pytest.raises(FilingError, match="nothing in the index is called"):
        unfile_document(engagement, "ghost.pdf", today=DAY2)


def test_a_working_copy_somebody_re_saved_is_left_where_it_is_and_said_so(engagement):
    """A reviewer's notes are work. Which of the two files the firm wants is not ours."""
    from tracker.actions import LEFT_FILED, unfile_document

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    working = engagement / filed.prepared_location
    working.write_bytes(working.read_bytes() + b"% a reviewer's note\n")

    result = unfile_document(engagement, filed.pbc_location, today=DAY2)

    assert result.moved_working_copy is False
    assert working.is_file()                                   # the notes are not thrown away
    parked = engagement / result.entry.prepared_location
    assert parked.is_file()
    assert parked.read_bytes() == (engagement / filed.pbc_location).read_bytes()
    assert result.left_filed == LEFT_FILED.format(
        location=filed.prepared_location, parked=parked.name)


def test_after_unfiling_the_request_is_not_received_and_the_note_says_why(engagement):
    """The status is put back in the same breath; nothing waits for the next pass."""
    from tracker.actions import unfile_document
    from tracker.manifest import Status, load_manifest
    from tracker.scanner import REGRESSION_FILES_CHANGED, REGRESSION_NOTE, scan_engagement

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025 John")
    drop(engagement, "w2 jane.pdf", "Form W-2 Wage and Tax Statement 2025 Jane")
    filed = sort(engagement, today=DAY1).filed
    assert {e.identifier for e in filed} == {"A01"}            # the row expects two
    scan_engagement(engagement, today=DAY1)
    a01 = next(i for i in load_manifest(engagement) if i.identifier == "A01")
    assert a01.status == Status.RECEIVED

    result = unfile_document(engagement, filed[0].pbc_location, today=DAY2)

    assert result.scan_note == ""
    a01 = next(i for i in load_manifest(engagement) if i.identifier == "A01")
    assert a01.status == Status.PARTIAL
    assert REGRESSION_NOTE.format(
        status=Status.RECEIVED, date=DAY1.isoformat(), why=REGRESSION_FILES_CHANGED,
    ) in a01.validation_notes


def taught_keywords(engagement) -> dict[str, tuple[str, ...]]:
    return {i.identifier: i.any_keywords for i in load_manifest(engagement)}


def test_unfiling_still_unlearns_nothing(engagement):
    """Decision 77's second half, prose until decision 113 gave it a way back.

    A keyword is a rule about documents: the request wanted the word when
    the document was filed and wants it still, and guessing which word to
    take back would be guessing. A person who wants one back says which,
    in the editor.
    """
    from tracker.actions import assign_review_file, unfile_document

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    assign_review_file(engagement, parked.pbc_location, "C01", keyword="lender", today=DAY2)
    assert taught_keywords(engagement)["C01"] == ("lender",)

    unfile_document(engagement, parked.pbc_location, today=DAY2)

    assert taught_keywords(engagement)["C01"] == ("lender",)
    assert store.learned_keywords(store.connect(), engagement) == {"c01": ("lender",)}
    names = [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)]
    assert ledger.KEYWORD_UNLEARNED not in names


def test_the_next_pass_leaves_an_unfiled_original_where_the_row_says(engagement):
    """It is still in PBC with a row, so it is nobody's stray and no second copy is made."""
    from tracker.actions import unfile_document

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    unfile_document(engagement, filed.pbc_location, today=DAY2)
    parked = sorted(p.name for p in review_dir(engagement).iterdir())

    report = sort(engagement, today=DAY2)

    assert report.handled == 0 and report.errors == [] and report.attention == []
    assert sorted(p.name for p in review_dir(engagement).iterdir()) == parked
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW

    # And the same document sent again is what a re-send of a parked one is.
    drop(engagement, "w2 again.pdf", "Form W-2 Wage and Tax Statement 2025")
    again = sort(engagement, today=DAY2)
    assert [e.original_name for e in again.duplicates] == ["w2 again.pdf"]
    assert sorted(p.name for p in review_dir(engagement).iterdir()) == parked


def test_a_failed_record_puts_the_unfiled_copy_back_where_the_record_says(engagement, monkeypatch):
    """A retry does this once, not twice: the file goes where the record says."""
    from tracker.actions import unfile_document

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    working = engagement / filed.prepared_location

    def disk_full(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(store, "record", disk_full)
    with pytest.raises(OSError):
        unfile_document(engagement, filed.pbc_location, today=DAY2)
    monkeypatch.undo()

    assert working.is_file()
    assert not list(review_dir(engagement).iterdir())
    [row] = read_index(engagement)
    assert row.decision == FILED and row.prepared_location == filed.prepared_location

# ------------- a person's action is judged against the record (d112) ----


def every_byte(folder):
    """Every file under the engagement, by path, with its bytes."""
    return {path.relative_to(folder).as_posix(): path.read_bytes()
            for path in sorted(folder.rglob("*")) if path.is_file()}


def test_an_assign_with_a_stale_seq_refuses_naming_what_the_record_now_says_and_touches_nothing(
        engagement):
    """The harm decision 112 is about: a person opened the card, was called
    away, and came back to File it on a row somebody had meanwhile set
    aside. The row is still parked, so the by-name refusal says nothing
    about it; its sequence number has moved, and that is what catches it."""
    from tracker.actions import (
        assign_review_file,
        dismiss_review_file,
    )
    from tracker.filer import StaleRowError
    from tracker.index import NOT_REQUESTED

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    as_the_person_saw_it = seq_of(engagement, parked)

    dismiss_review_file(engagement, parked.pbc_location, "an IRS notice", today=DAY2)
    lines = len(ledger.read_events(engagement))
    files = every_byte(engagement)

    with pytest.raises(StaleRowError) as raised:
        assign_review_file(engagement, parked.pbc_location, "C01",
                           today=DAY2, seq=as_the_person_saw_it)

    # The sentence says what the record now holds, not only that it said no.
    said = str(raised.value)
    assert parked.original_name in said and NOT_REQUESTED in said and "an IRS notice" in said
    # And nothing happened: no file moved, no copy made, no line appended.
    assert every_byte(engagement) == files
    assert len(ledger.read_events(engagement)) == lines
    [row] = read_index(engagement)
    assert row.decision == NOT_REQUESTED


def test_an_assign_with_the_current_seq_proceeds(engagement):
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    result = assign_review_file(engagement, parked.pbc_location, "C01",
                                today=DAY2, seq=seq_of(engagement, parked))

    assert result.entry.decision == FILED and result.entry.identifier == "C01"
    assert (engagement / result.entry.prepared_location).is_file()


@pytest.mark.parametrize("action", ("dismiss", "unfile"))
def test_a_dismiss_and_an_unfile_with_a_stale_seq_refuse_likewise(engagement, action):
    """The same check on the other two decisions: a row dismissed twice from
    one stale card, and a row somebody re-filed between the list being drawn
    and Unfile being pressed."""
    from tracker.actions import (
        assign_review_file,
        dismiss_review_file,
        unfile_document,
    )
    from tracker.filer import StaleRowError

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    if action == "dismiss":
        as_the_person_saw_it = seq_of(engagement, parked)
        dismiss_review_file(engagement, parked.pbc_location, "somebody else", today=DAY2)
    else:
        filed = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2).entry
        as_the_person_saw_it = seq_of(engagement, filed)
        unfile_document(engagement, parked.pbc_location, today=DAY2)
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)

    lines = len(ledger.read_events(engagement))
    with pytest.raises(StaleRowError) as raised:
        if action == "dismiss":
            dismiss_review_file(engagement, parked.pbc_location,
                                today=DAY2, seq=as_the_person_saw_it)
        else:
            unfile_document(engagement, parked.pbc_location,
                            today=DAY2, seq=as_the_person_saw_it)

    assert parked.original_name in str(raised.value)
    assert len(ledger.read_events(engagement)) == lines


def test_an_action_with_no_seq_skips_the_check(engagement):
    """A caller with no view - a script, every other call in this file - has
    nothing to be stale against and is not checked."""
    from tracker.actions import assign_review_file, dismiss_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    dismiss_review_file(engagement, parked.pbc_location, today=DAY2)   # the row moves on

    result = assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)

    assert result.entry.decision == FILED


def honoured_by_the_scan(engagement, identifier):
    """One scan, and what it said about the request a person filed into.

    Asked through the pass itself rather than the helper behind it: what the
    scan writes about the row is where a person's filing is honoured or not,
    and the copy here answers none of the row's content rules, so Received
    with the accepted note is the person's decision and nothing else.
    """
    from tracker.manifest import Status
    from tracker.scanner import ACCEPTED_NOTE, scan_engagement

    said = scan_engagement(engagement, today=DAY2).updates[identifier]
    assert said.status == Status.RECEIVED, said
    assert ACCEPTED_NOTE.format(n=1) in said.validation_notes, said


def test_a_pick_off_a_non_empty_shortlist_is_recorded_as_an_override_and_a_pick_on_it_is_not(
        engagement):
    """Decision 84 lets a person file to any row; the record now says when
    they did so against the evidence, and the scanner still honours it."""
    from tracker.actions import (
        assign_review_file,
        unfile_document,
    )
    from tracker.filer import (
        ASSIGNED_BY_PERSON,
        OVERRODE_SHORTLIST,
    )

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]

    off = assign_review_file(engagement, parked.pbc_location, "C01",
                             today=DAY2, shortlist=["A01"])

    assert off.overrode_shortlist == OVERRODE_SHORTLIST.format(listed="A01")
    assert off.overrode_shortlist in off.entry.reason
    # The acceptance keys on the reason's prefix and the override clause
    # sits after it, so the pass still takes the copy as a person's filing.
    assert off.entry.reason.startswith(ASSIGNED_BY_PERSON)
    honoured_by_the_scan(engagement, "C01")

    unfile_document(engagement, parked.pbc_location, today=DAY2)
    on = assign_review_file(engagement, parked.pbc_location, "C01",
                            today=DAY2, shortlist=["C01", "A01"])

    # Only this decision's own clause: what the row said before is kept
    # after "was: ", and the override it carried is part of that history.
    assert on.overrode_shortlist == ""
    assert OVERRODE_SHORTLIST.split("(")[0] not in on.entry.reason.split("; was: ")[0]
    honoured_by_the_scan(engagement, "C01")


def test_an_empty_shortlist_is_never_an_override(engagement):
    """Decision 83's "no need prior": with nothing suggested there is nothing
    to overrule, so a filing off nothing says nothing."""
    from tracker.actions import assign_review_file, unfile_document
    from tracker.filer import OVERRODE_SHORTLIST

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    the_clause = OVERRODE_SHORTLIST.split("(")[0]

    for shortlist in ([], None):
        result = assign_review_file(engagement, parked.pbc_location, "C01",
                                    today=DAY2, shortlist=shortlist)
        assert result.overrode_shortlist == ""
        assert the_clause not in result.entry.reason.split("; was: ")[0]
        unfile_document(engagement, parked.pbc_location, today=DAY2)


def test_a_refused_action_leaves_the_file_count_and_every_byte_unchanged(engagement):
    """The first standing rule of a refusal, over all three: nothing moved,
    nothing overwritten, nothing recorded."""
    from tracker.actions import (
        assign_review_file,
        dismiss_review_file,
        unfile_document,
    )
    from tracker.filer import StaleRowError

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "notice.pdf", "nothing the rules recognise either")
    review = {e.original_name: e for e in sort(engagement, today=DAY1).review}
    parked, other = review["scan0012.pdf"], review["notice.pdf"]

    stale_parked = seq_of(engagement, parked)
    dismiss_review_file(engagement, parked.pbc_location, today=DAY2)   # parked still, seq moved
    filed = assign_review_file(engagement, other.pbc_location, "C01", today=DAY2).entry
    stale_filed = seq_of(engagement, filed)
    unfile_document(engagement, other.pbc_location, today=DAY2)
    assign_review_file(engagement, other.pbc_location, "C01", today=DAY2)

    files = every_byte(engagement)
    lines = len(ledger.read_events(engagement))

    for refuse in ("assign", "dismiss", "unfile"):
        with pytest.raises(StaleRowError):
            if refuse == "assign":
                assign_review_file(engagement, parked.pbc_location, "A01",
                                   today=DAY2, seq=stale_parked)
            elif refuse == "dismiss":
                dismiss_review_file(engagement, parked.pbc_location,
                                    today=DAY2, seq=stale_parked)
            else:
                unfile_document(engagement, other.pbc_location, today=DAY2, seq=stale_filed)
        assert every_byte(engagement) == files, refuse
        assert len(ledger.read_events(engagement)) == lines, refuse


def test_a_second_and_a_third_pass_over_an_unchanged_tree_hash_only_the_pbc_originals(
        engagement, monkeypatch):
    """Step 0's measure. Every hash of a file in the firm's folder goes
    through the store's memo, so a warm pass reads one file per preserved
    original - decision 68's per-pass reading of the client's own folder,
    accepted unchanged - and no working copy at all."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.actions import assign_review_file
    from tracker.scanner import scan_engagement

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "notice.pdf", "an agency notice nothing asks for")
    drop(engagement, "scan0003.pdf", "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    first = sort(engagement, today=DAY1)
    assert len(first.filed) == 2 and len(first.review) == 2
    assert any(e.also_filed for e in first.filed)            # the decision-94 split
    parked = next(e for e in first.review if e.original_name == "scan0012.pdf")
    assign_review_file(engagement, parked.pbc_location, "C01", today=DAY1)
    scan_engagement(engagement, today=DAY1)                  # the warm pass
    arrivals = sorted(p.name for p in originals(engagement).iterdir())
    assert len(arrivals) == 4

    read = counting_hashes(monkeypatch)
    for day in (DAY2, DAY2 + dt.timedelta(days=1)):          # the second pass, and the third
        read.clear()
        sort(engagement, today=day)
        scan_engagement(engagement, today=day)
        assert sorted(Path(path).name for path in read) == arrivals, read
        assert not any(PREPARED_DIR_NAME in path for path in read), read

# ------------------------------ recovery is the person's (decision 110) ----


def a_moved_filed_row(engagement, folder="C01"):
    """A Filed document whose working copy somebody dragged, as the sweep
    leaves it: the row it made, and the file where the hand put it."""
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    wanderer = drag(engagement / filed.prepared_location, prepared(engagement, folder))
    sort(engagement, today=DAY2)
    return filed, wanderer


def test_put_it_back_moves_the_wanderer_home_and_the_row_is_filed_again(engagement):
    """The first answer, and the one that needs nowhere else for the file to
    go: the bytes return to where the record put them, the row is Filed
    again, and the next pass has nothing left to say about it."""
    from tracker.actions import PUT_BACK, restore_working_copy
    from tracker.index import FILED

    filed, wanderer = a_moved_filed_row(engagement)
    home = engagement / filed.prepared_location
    bytes_before = wanderer.read_bytes()
    lines = len(ledger.read_events(engagement))

    result = restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert result.moved_home and not result.copied_from_original
    assert not result.already_home and result.parked_as == ""
    assert home.read_bytes() == bytes_before and not wanderer.exists()
    [row] = read_index(engagement)
    assert row.decision == FILED and row.prepared_location == filed.prepared_location
    assert row.reason.endswith(PUT_BACK.format(
        home=filed.prepared_location, date=DAY2.isoformat(),
        now=location_of(engagement, wanderer)))
    assert row.reason.startswith(filed.reason)          # and its history is kept
    assert len(events_named(engagement, ledger.RESTORED_BY_PERSON)) == 1
    # One decision of the person's, and the re-scan that puts the request's
    # status back in the same breath. Nothing else was written.
    assert [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)[lines:]] == [
        ledger.MOVING, ledger.RESTORED_BY_PERSON, ledger.SCANNED
    ]
    assert result.entry == row
    # The request has its file again, and the pass that follows says nothing
    # about it: the copy is where the record put it, so it simply proves.
    lines = len(ledger.read_events(engagement))
    quiet = sort(engagement, today=DAY2 + dt.timedelta(days=1))
    assert quiet.attention == []
    assert len(ledger.read_events(engagement)) == lines


def test_put_it_back_on_a_parked_copy_dragged_into_a_request_folder_returns_it_to_review_as_needs_review(
        engagement):
    """A parked copy that wandered comes back parked. Which of the two parked
    decisions it was is not guessable (109's rule), so it waits for review
    and a person re-decides in one click."""
    from tracker.actions import restore_working_copy

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    wanderer = drag(engagement / parked.prepared_location, prepared(engagement, "C01"))
    sort(engagement, today=DAY2)

    result = restore_working_copy(engagement, parked.pbc_location, today=DAY2)

    assert result.moved_home
    assert (engagement / parked.prepared_location).is_file() and not wanderer.exists()
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == ""
    assert row.prepared_location == parked.prepared_location


def test_put_it_back_copies_from_the_original_when_nothing_under_prepared_holds_the_bytes(
        engagement):
    """A working copy is a copy of the original and the original is safe in
    the client's own folder (rule 2), so a row whose bytes are nowhere under
    the firm's folder is still restorable."""
    from tracker.actions import PUT_BACK_FROM_ORIGINAL, restore_working_copy
    from tracker.index import FILED

    filed, wanderer = a_moved_filed_row(engagement)
    wanderer.unlink()                                   # and now it is nowhere
    sort(engagement, today=DAY2)
    original = (originals(engagement) / "w2.pdf").read_bytes()

    result = restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert result.copied_from_original and not result.moved_home
    home = engagement / filed.prepared_location
    assert home.read_bytes() == original
    assert (originals(engagement) / "w2.pdf").read_bytes() == original    # untouched, as ever
    [row] = read_index(engagement)
    assert row.decision == FILED
    assert row.reason.endswith(PUT_BACK_FROM_ORIGINAL.format(
        home=filed.prepared_location, date=DAY2.isoformat(),
        pbc=filed.pbc_location, prepared=PREPARED_DIR_NAME))


def test_put_it_back_with_the_same_bytes_already_home_restores_the_row_and_leaves_the_wanderer_for_a_person(
        engagement):
    """The machine deletes nothing. Home holds these bytes, so there is
    nothing to move; the copy somebody left behind stays where it is and the
    sweep goes on naming it until a person removes it."""
    from tracker.actions import PUT_BACK_ALREADY, restore_working_copy
    from tracker.filer import UNRECORDED_COPY
    from tracker.index import FILED

    filed, wanderer = a_moved_filed_row(engagement)
    home = engagement / filed.prepared_location
    home.write_bytes(wanderer.read_bytes())             # put back by hand, the copy left over
    untouched = files_under(engagement)

    result = restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert result.already_home and not result.moved_home and not result.copied_from_original
    assert files_under(engagement) == untouched         # nothing moved, nothing deleted
    [row] = read_index(engagement)
    assert row.decision == FILED
    assert row.reason.endswith(PUT_BACK_ALREADY.format(
        home=filed.prepared_location, date=DAY2.isoformat(),
        now=location_of(engagement, wanderer)))
    assert len(events_named(engagement, ledger.RESTORED_BY_PERSON)) == 1

    report = sort(engagement, today=DAY2 + dt.timedelta(days=1))
    assert [e.error for e in report.attention] == [
        UNRECORDED_COPY.format(location=location_of(engagement, wanderer))
    ]


@pytest.mark.parametrize("held_by", ("the wanderer", "nowhere"))
def test_put_it_back_never_overwrites_a_different_file_at_home_and_parks_this_documents_copy(
        engagement, held_by):
    """The owner's rule, 2026-09-19: nothing is overwritten. The file at home
    is somebody's, whatever the record says about it, so it stays exactly
    as it is; this document's copy goes to review under the client's own
    name and the row parks naming both, and both files are on disk.

    Runs on Windows and on Linux alike, because the refusal is the byte
    check this makes before ``os.rename`` and never the rename's own: on
    Linux a rename overwrites silently and there would be nothing to see.
    """
    from tracker.actions import PUT_BACK_REFUSED, restore_working_copy

    filed, wanderer = a_moved_filed_row(engagement)
    if held_by == "nowhere":
        wanderer.unlink()
        sort(engagement, today=DAY2)
    home = engagement / filed.prepared_location
    somebody_elses = b"%PDF-1.4 a different document entirely\n"
    home.write_bytes(somebody_elses)
    before = home.stat().st_mtime_ns

    result = restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    # The file at home is byte for byte, mtime and all, what it was.
    assert home.read_bytes() == somebody_elses and home.stat().st_mtime_ns == before
    parked = engagement / result.parked_as
    assert parked.parent == review_dir(engagement)
    assert parked.read_bytes() == (originals(engagement) / "w2.pdf").read_bytes()
    assert parked.name == "w2.pdf"                      # the client's own name
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == "" and row.also_filed == ""
    assert row.prepared_location == result.parked_as
    assert row.reason.endswith(PUT_BACK_REFUSED.format(
        date=DAY2.isoformat(), home=filed.prepared_location, parked=result.parked_as))
    assert len(events_named(engagement, ledger.RESTORED_BY_PERSON)) == 1


def test_put_it_back_refuses_a_row_that_is_not_moved_by_name(engagement):
    from tracker.actions import restore_working_copy
    from tracker.filer import FilingError

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    files = every_byte(engagement)

    with pytest.raises(FilingError) as raised:
        restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert "is not a moved copy" in str(raised.value) and FILED in str(raised.value)
    assert every_byte(engagement) == files


def moved_again(engagement, wanderer, day):
    """The copy dragged a second time, and the pass that rewrites the row:
    still File Moved, still this person's row to act on - and no longer the
    row they were looking at."""
    moved = drag(wanderer, review_dir(engagement))
    sort(engagement, today=day)
    return moved


def test_put_it_back_refuses_a_stale_seq_and_touches_nothing(engagement):
    """Still moved, so the by-name refusal says nothing about it; the row's
    own sequence number has moved, and that is what catches it."""
    from tracker.actions import restore_working_copy
    from tracker.filer import StaleRowError
    from tracker.index import FILE_MOVED

    filed, wanderer = a_moved_filed_row(engagement)
    [row] = read_index(engagement)
    as_the_person_saw_it = seq_of(engagement, row)
    moved_again(engagement, wanderer, DAY2 + dt.timedelta(days=1))
    [now_row] = read_index(engagement)
    assert now_row.decision == FILE_MOVED
    assert seq_of(engagement, now_row) != as_the_person_saw_it
    files = every_byte(engagement)
    lines = len(ledger.read_events(engagement))

    with pytest.raises(StaleRowError) as raised:
        restore_working_copy(engagement, filed.pbc_location, today=DAY2,
                             seq=as_the_person_saw_it)

    assert filed.original_name in str(raised.value)
    assert every_byte(engagement) == files
    assert len(ledger.read_events(engagement)) == lines


def test_put_it_back_refuses_a_row_without_a_digest(engagement, monkeypatch):
    """Decision 65: a row recorded without its bytes is tied to nothing, so
    nothing can be proved to be its working copy and nothing here may move."""
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.intents as intents_module
    import tracker.readme_ack as readme_ack_module
    from tracker.actions import restore_working_copy
    from tracker.filer import FilingError
    from tracker.index import FILE_MOVED

    filed, wanderer = a_moved_filed_row(engagement)
    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED
    for module in (filer_module, copies_module, intents_module, readme_ack_module, actions_module):
        monkeypatch.setattr(module, "read_index",
                            lambda *a, **k: [replace(row, digest="")])
    files = every_byte(engagement)

    with pytest.raises(FilingError) as raised:
        restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert "without its bytes" in str(raised.value)
    assert every_byte(engagement) == files


def test_put_it_back_refuses_when_neither_the_wanderer_nor_the_original_holds_the_bytes_and_names_which(
        engagement):
    from tracker.actions import restore_working_copy
    from tracker.filer import FilingError

    filed, wanderer = a_moved_filed_row(engagement)
    wanderer.write_bytes(b"%PDF-1.4 somebody re-saved it\n")
    (originals(engagement) / "w2.pdf").write_bytes(b"%PDF-1.4 and the client replaced this\n")
    files = every_byte(engagement)

    with pytest.raises(FilingError) as raised:
        restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    said = str(raised.value)
    assert location_of(engagement, wanderer) in said and filed.pbc_location in said
    assert every_byte(engagement) == files


def test_a_refused_record_rolls_the_put_back_move_back(engagement, monkeypatch):
    """The record took the decision or it did not - one transaction, no third
    state - so the file goes back where the record says it is."""
    import tracker.store as store_module
    from tracker.actions import restore_working_copy
    from tracker.index import FILE_MOVED

    filed, wanderer = a_moved_filed_row(engagement)
    files = every_byte(engagement)
    lines = len(ledger.read_events(engagement))

    def refuse(*a, **k):
        raise RuntimeError("the record said no")

    monkeypatch.setattr(store_module, "record", refuse)
    with pytest.raises(RuntimeError):
        restore_working_copy(engagement, filed.pbc_location, today=DAY2)
    monkeypatch.undo()

    assert every_byte(engagement) == files              # the wanderer is where it was
    assert len(ledger.read_events(engagement)) == lines
    assert events_named(engagement, ledger.RESTORED_BY_PERSON) == []
    assert read_index(engagement)[0].decision == FILE_MOVED


def test_keep_it_here_files_the_wanderer_under_the_request_whose_folder_holds_it_as_the_persons(
        engagement):
    """The second answer: the copy is where somebody meant it to be, so it
    takes the canonical name there and the row is Filed by a person."""
    from tracker.actions import assign_review_file
    from tracker.filer import ASSIGNED_BY_PERSON
    from tracker.index import FILED
    from tracker.manifest import load_manifest

    filed, wanderer = a_moved_filed_row(engagement)

    result = assign_review_file(engagement, filed.pbc_location, "C01",
                                keyword="escrow", today=DAY2)

    assert result.moved_review_copy and not wanderer.exists()
    kept = engagement / result.entry.prepared_location
    assert kept.parent == engagement / PREPARED_DIR_NAME          # beside the others (decision 168)
    assert kept.name.startswith("C01 - ")
    [row] = read_index(engagement)
    assert row.decision == FILED and row.identifier == "C01"
    assert row.reason.startswith(ASSIGNED_BY_PERSON)
    assert len(events_named(engagement, ledger.ASSIGNED_BY_PERSON)) == 1
    c01 = {i.identifier: i for i in load_manifest(engagement)}["C01"]
    assert "escrow" in c01.any_keywords


def test_keep_it_here_may_pick_another_request_and_the_wanderer_moves_there(engagement):
    """The picker is the same picker: keeping the file and correcting the
    request it answers is one click."""
    from tracker.actions import assign_review_file
    from tracker.index import FILED

    filed, wanderer = a_moved_filed_row(engagement)

    result = assign_review_file(engagement, filed.pbc_location, "A01", today=DAY2)

    assert not wanderer.exists()
    kept = engagement / result.entry.prepared_location
    assert kept.parent == engagement / PREPARED_DIR_NAME and kept.name.startswith("A01 - ")
    [row] = read_index(engagement)
    assert row.decision == FILED and row.identifier == "A01"


@pytest.mark.parametrize("where", ("the wanderer", "nowhere"))
def test_send_to_review_parks_the_wanderer_under_the_clients_name_as_the_persons(
        engagement, where):
    """The third answer: the copy goes back to the review folder under the
    client's own name, and a row whose bytes are nowhere is copied from the
    original, exactly as an unfiling already does."""
    from tracker.actions import unfile_document
    from tracker.filer import UNFILED_BY_PERSON

    filed, wanderer = a_moved_filed_row(engagement)
    if where == "nowhere":
        wanderer.unlink()
        sort(engagement, today=DAY2)

    result = unfile_document(engagement, filed.pbc_location, today=DAY2)

    assert result.moved_working_copy is (where == "the wanderer")
    parked = engagement / result.entry.prepared_location
    assert parked.parent == review_dir(engagement) and parked.name == "w2.pdf"
    assert parked.read_bytes() == (originals(engagement) / "w2.pdf").read_bytes()
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == ""
    assert row.reason.startswith(UNFILED_BY_PERSON)
    assert len(events_named(engagement, ledger.UNFILED_BY_PERSON)) == 1


def a_moved_split_row(engagement):
    """A page decision 94 filed under two requests, one copy dragged away and
    the other deleted: the row the sweep leaves, and the wanderer."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines

    drop(engagement, "scan0003.pdf",
         "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    [split] = sort(engagement, today=DAY1).filed
    assert len(split.filed_locations) == 2
    wanderer = drag(engagement / split.filed_locations[0], review_dir(engagement))
    (engagement / split.filed_locations[1]).unlink()
    sort(engagement, today=DAY2)
    return split, wanderer


@pytest.mark.parametrize("action", ("keep", "send to review"))
def test_keep_and_send_to_review_refuse_a_row_with_copies_under_several_requests_by_name(
        engagement, action):
    """Which of a page's copies the person means is not the machine's to
    guess, and put-it-back answers for every one of them."""
    from tracker.actions import (
        SEVERAL_COPIES_REFUSAL,
        assign_review_file,
        unfile_document,
    )
    from tracker.filer import FilingError

    split, wanderer = a_moved_split_row(engagement)
    files = every_byte(engagement)

    with pytest.raises(FilingError) as raised:
        if action == "keep":
            assign_review_file(engagement, split.pbc_location, "A01", today=DAY2)
        else:
            unfile_document(engagement, split.pbc_location, today=DAY2)

    assert str(raised.value) == SEVERAL_COPIES_REFUSAL.format(name=split.original_name)
    assert every_byte(engagement) == files


def test_put_it_back_restores_every_copy_of_such_a_row(engagement):
    """One row, one original, one list of copies: put-it-back fills every one
    of them - the wanderer moved into the first, the rest remade from it -
    and the next pass has nothing left to say."""
    from tracker.actions import restore_working_copy
    from tracker.index import FILED

    split, wanderer = a_moved_split_row(engagement)
    bytes_wanted = wanderer.read_bytes()

    result = restore_working_copy(engagement, split.pbc_location, today=DAY2)

    assert result.moved_home and not wanderer.exists()
    [row] = read_index(engagement)
    assert row.decision == FILED and row.filed_locations == split.filed_locations
    for location in row.filed_locations:
        assert (engagement / location).read_bytes() == bytes_wanted
    report = sort(engagement, today=DAY2 + dt.timedelta(days=1))
    assert report.attention == []                       # every copy proves


@pytest.mark.parametrize("refusal", ("not moved", "stale", "no bytes anywhere", "several copies"))
def test_every_recovery_refusal_leaves_the_file_count_unchanged(engagement, refusal):
    """Standing rule: a refused action moves nothing and overwrites nothing."""
    from tracker.actions import restore_working_copy, unfile_document
    from tracker.filer import FilingError

    entry, wanderer = (a_moved_split_row(engagement) if refusal == "several copies"
                       else a_moved_filed_row(engagement))
    stale = seq_of(engagement, read_index(engagement)[0])
    if refusal == "not moved":
        restore_working_copy(engagement, entry.pbc_location, today=DAY2)   # no longer moved
    elif refusal == "stale":
        moved_again(engagement, wanderer, DAY2 + dt.timedelta(days=1))
    elif refusal == "no bytes anywhere":
        wanderer.write_bytes(b"%PDF-1.4 re-saved\n")
        (originals(engagement) / "w2.pdf").write_bytes(b"%PDF-1.4 replaced\n")

    files = files_under(engagement)
    lines = len(ledger.read_events(engagement))
    with pytest.raises(FilingError):
        if refusal == "several copies":
            unfile_document(engagement, entry.pbc_location, today=DAY2)
        elif refusal == "stale":
            restore_working_copy(engagement, entry.pbc_location, today=DAY2, seq=stale)
        else:
            restore_working_copy(engagement, entry.pbc_location, today=DAY2)

    assert files_under(engagement) == files
    assert len(ledger.read_events(engagement)) == lines


def test_dismiss_still_refuses_a_moved_row_by_name(engagement):
    """Decision 76 unchanged: setting a request aside says nothing about a
    file nobody can find, so a moved row is not dismissable."""
    from tracker.actions import dismiss_review_file
    from tracker.filer import FilingError
    from tracker.index import FILE_MOVED

    filed, wanderer = a_moved_filed_row(engagement)
    files = every_byte(engagement)

    with pytest.raises(FilingError) as raised:
        dismiss_review_file(engagement, filed.pbc_location, today=DAY2)

    assert "is not waiting for review" in str(raised.value)
    assert FILE_MOVED in str(raised.value)
    assert every_byte(engagement) == files


def test_a_copy_of_a_read_only_original_is_writable_and_the_original_stays_read_only(engagement):
    """Decision 155, F-2. ``copy2`` carried a read-only original's attribute
    onto its working copy - a file from a CD, one Explorer took out of a
    zip - and removing that copy later ("Access is denied") jammed the
    household every pass. The copy is the firm's and is writable; the
    original is only read, and stays exactly as the client sent it."""
    import stat as stat_module

    from tracker.actions import unfile_document

    original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    os.chmod(original, stat_module.S_IREAD)
    try:
        [filed] = sort(engagement, today=DAY1).filed
        kept = originals(engagement) / "w2.pdf"
        copy = engagement / filed.prepared_location
        assert not os.stat(kept).st_mode & stat_module.S_IWRITE     # the original: untouched
        assert os.stat(copy).st_mode & stat_module.S_IWRITE         # the copy: writable
        # And what jammed the household: a step that takes the copy away.
        unfile_document(engagement, filed.pbc_location, today=DAY2)
        assert not copy.exists()
        assert not os.stat(kept).st_mode & stat_module.S_IWRITE
    finally:
        for path in (originals(engagement) / "w2.pdf", original):
            if path.exists():
                os.chmod(path, stat_module.S_IREAD | stat_module.S_IWRITE)


def test_an_assign_killed_between_the_move_and_the_record_is_finished_as_the_persons_filing(
        engagement, monkeypatch):
    """A person filed it and the machine died with the copy moved. The next
    pass records the filing as theirs, dated the day they made it, with the
    keyword it taught in the same transaction."""
    from tracker.actions import assign_review_file
    from tracker.filer import ASSIGNED_BY_PERSON

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_ops(monkeypatch, after=1)

    with pytest.raises(KeyboardInterrupt):
        assign_review_file(engagement, parked.pbc_location, "C01",
                           keyword="lender", today=DAY2)

    [waiting] = read_index(engagement)
    assert waiting.decision == NEEDS_REVIEW          # the record has not moved
    assert open_intents(engagement)
    calls = counted_records(monkeypatch)

    sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == FILED and row.identifier == "C01"
    assert row.reason.startswith(f"{ASSIGNED_BY_PERSON} on {DAY2.isoformat()}")
    assert calls == [(ledger.ASSIGNED_BY_PERSON, ledger.KEYWORD_LEARNED)]
    assert {i.identifier: i.any_keywords for i in load_manifest(engagement)}["C01"] == ("lender",)
    conserved(engagement, before, moves)


def test_recovery_runs_before_the_sweep_so_an_interrupted_action_is_never_called_a_hand_move(
        engagement, monkeypatch):
    """Decision 109's sweep would read a person's half-made filing as a copy
    somebody dragged, and 110 would ask them to put it back. The recovery
    runs first, so the sweep never sees it."""
    from tracker.actions import assign_review_file
    from tracker.index import FILE_MOVED

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_ops(monkeypatch, after=1)
    with pytest.raises(KeyboardInterrupt):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)

    report = sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == FILED and row.decision != FILE_MOVED
    assert events_named(engagement, ledger.COPY_MOVED) == []
    assert events_named(engagement, ledger.ASSIGNED_BY_PERSON)
    assert report.attention == []
    conserved(engagement, before, moves)


def test_an_unfile_killed_between_the_move_and_the_record_is_finished_and_no_second_parked_copy_is_made(
        engagement, monkeypatch):
    """The copy went back to review and the row was never rewritten. The
    next pass records the unfiling as the person's; nothing parks a second
    copy beside the one already there."""
    from tracker.actions import unfile_document
    from tracker.filer import UNFILED_BY_PERSON

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_ops(monkeypatch, after=1)

    with pytest.raises(KeyboardInterrupt):
        unfile_document(engagement, filed.pbc_location, today=DAY2)

    assert read_index(engagement)[0].decision == FILED       # the record has not moved
    assert open_intents(engagement)

    sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == ""
    assert row.reason.startswith(f"{UNFILED_BY_PERSON} on {DAY2.isoformat()}")
    assert [p.name for p in review_dir(engagement).iterdir()] == ["w2.pdf"]
    assert not list(prepared(engagement, "A01").iterdir())
    conserved(engagement, before, moves)


def test_an_unfile_killed_between_two_stand_downs_finishes_the_removals_it_recorded(
        engagement, monkeypatch):
    """Decision 94's several copies: one goes back under the client's name
    and the rest stand down, being those same bytes again. A kill between
    them leaves a copy in a request folder the row no longer claims, and
    the next pass finishes the stand-down the record already carries."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.actions import unfile_document

    drop(engagement, "scan0003.pdf",
         "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    (filed,) = sort(engagement, today=DAY1).filed
    assert len(filed.filed_locations) == 2
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_ops(monkeypatch, after=1)           # the move home, not the stand-down

    with pytest.raises(KeyboardInterrupt):
        unfile_document(engagement, filed.pbc_location, today=DAY2)

    assert (engagement / filed.filed_locations[1]).is_file()      # not stood down yet

    sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.also_filed == ""
    assert not (engagement / filed.filed_locations[1]).exists()
    assert [p.name for p in review_dir(engagement).iterdir()] == ["scan0003.pdf"]
    conserved(engagement, before, moves,
              gone=[before[filed.filed_locations[1]]])


def test_a_restore_killed_between_the_move_and_the_record_is_finished(engagement, monkeypatch):
    """Decision 110's put-it-back, killed with the copy home and the row
    still saying it is not. The next pass records the person's answer."""
    from tracker.actions import PUT_BACK, restore_working_copy

    filed, wanderer = a_moved_filed_row(engagement)
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_ops(monkeypatch, after=1)

    with pytest.raises(KeyboardInterrupt):
        restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert (engagement / filed.prepared_location).is_file() and not wanderer.exists()
    assert open_intents(engagement)

    sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == FILED and row.prepared_location == filed.prepared_location
    assert row.reason.endswith(PUT_BACK.format(
        home=filed.prepared_location, date=DAY2.isoformat(),
        now=location_of(engagement, wanderer)))
    assert len(events_named(engagement, ledger.RESTORED_BY_PERSON)) == 1
    conserved(engagement, before, moves)


def test_a_destination_holding_other_bytes_is_never_touched_and_the_row_parks_naming_it(
        engagement, monkeypatch):
    """The contradiction: the step never happened and somebody else's file
    is where it was going. Nothing there is touched, the row parks naming
    it, and the copy waiting in review is used rather than doubled."""
    from tracker import reasons
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    killed_at_the_intent(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)

    stranger = engagement / PREPARED_DIR_NAME / "C01 - Mortgage Interest - TY2025.pdf"
    stranger.parent.mkdir(parents=True, exist_ok=True)
    stranger.write_bytes(b"%PDF-1.4 somebody elses file")
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)

    report = sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.identifier == ""
    assert row.code == reasons.INTERRUPTED_MOVE.code
    assert location_of(engagement, stranger) in row.reason
    assert stranger.read_bytes() == b"%PDF-1.4 somebody elses file"     # untouched
    assert row.prepared_location == parked.prepared_location            # the copy waiting is used
    assert [p.name for p in review_dir(engagement).iterdir()] == ["scan0012.pdf"]
    assert any(reasons.INTERRUPTED_MOVE.marker in e.error for e in report.attention)
    conserved(engagement, before, moves)


def test_bytes_gone_from_both_places_park_the_row_and_say_so(engagement, monkeypatch):
    """Neither end of the step holds those bytes now. Nothing is guessed:
    the row parks, the sentence says whether the client's own original is
    still there, and the copy a person acts on is made from it."""
    from tracker import reasons
    from tracker.actions import unfile_document
    from tracker.intents import INTERRUPTED_ORIGINAL_HELD

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    filed = sort(engagement, today=DAY1).filed[0]
    killed_at_the_intent(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        unfile_document(engagement, filed.pbc_location, today=DAY2)

    (engagement / filed.prepared_location).unlink()       # and a person deletes the copy
    original = originals(engagement) / "w2.pdf"
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)

    report = sort(engagement, today=DAY3)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW
    assert row.code == reasons.INTERRUPTED_MOVE_LOST.code
    assert INTERRUPTED_ORIGINAL_HELD in row.reason
    assert filed.prepared_location in row.reason
    assert (engagement / row.prepared_location).read_bytes() == original.read_bytes()
    assert any(reasons.INTERRUPTED_MOVE_LOST.marker in e.error for e in report.attention)
    conserved(engagement, before, moves,
              added=[digests_under(engagement)[row.prepared_location]])


def test_a_person_action_refuses_while_an_intent_is_open_and_the_next_pass_clears_it(
        engagement, monkeypatch):
    """One answer for all four actions instead of five recovery paths: the
    record is in the middle of a decision here, and a pass - which the app's
    Run now is - finishes it first."""
    from tracker.actions import (
        assign_review_file,
        dismiss_review_file,
        restore_working_copy,
        unfile_document,
    )
    from tracker.copies import FilingError
    from tracker.intents import OPEN_INTENT_REFUSAL

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    killed_after_ops(monkeypatch, after=1)
    with pytest.raises(KeyboardInterrupt):
        assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    files = every_byte(engagement)

    for act in (lambda: assign_review_file(engagement, parked.pbc_location, "C01", today=DAY3),
                lambda: dismiss_review_file(engagement, parked.pbc_location, today=DAY3),
                lambda: unfile_document(engagement, parked.pbc_location, today=DAY3),
                lambda: restore_working_copy(engagement, parked.pbc_location, today=DAY3)):
        with pytest.raises(FilingError) as raised:
            act()
        assert str(raised.value) == OPEN_INTENT_REFUSAL
    assert every_byte(engagement) == files               # and none of them touched anything

    sort(engagement, today=DAY3)

    assert open_intents(engagement) == []
    # And the row is a person's to act on again.
    result = unfile_document(engagement, parked.pbc_location, today=DAY3)
    assert result.moved_working_copy is True


def test_a_refused_record_still_rolls_the_copy_back_and_leaves_no_intent_open(
        engagement, monkeypatch):
    """A refusal is not a crash. The files go back where the record says and
    the move is closed with ``move_abandoned``, so the next pass does not
    finish forward a move the record would not take - and where even that
    line cannot be written, the move stays open and the next pass finishes
    it forward as the record decided, recording the row the person made.
    """
    from tracker.actions import assign_review_file

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    drop(engagement, "notice.pdf", "an agency notice nothing asks for")
    parked = {e.original_name: e for e in sort(engagement, today=DAY1).review}
    real = store.record

    def the_rows_are_refused(conn, engagement_dir, *events):
        # The journal is writable; it is the decision's own record that is
        # refused - a store behind its journal, a line it will not fold.
        if events[0][ledger.EVENT_KEY] in (ledger.MOVING, ledger.MOVE_ABANDONED):
            return real(conn, engagement_dir, *events)
        raise store.StoreError("the store will not take this decision")

    monkeypatch.setattr(store, "record", the_rows_are_refused)
    with pytest.raises(store.StoreError):
        assign_review_file(engagement, parked["scan0012.pdf"].pbc_location, "C01", today=DAY2)
    monkeypatch.undo()

    assert (engagement / parked["scan0012.pdf"].prepared_location).is_file()   # put back
    assert open_intents(engagement) == []                                      # and closed
    assert [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)][-2:] == [
        ledger.MOVING, ledger.MOVE_ABANDONED]

    # And the other way: the abandonment itself cannot be written either.
    def nothing_is_recorded(conn, engagement_dir, *events):
        if events[0][ledger.EVENT_KEY] == ledger.MOVING:
            return real(conn, engagement_dir, *events)
        raise store.StoreError("the store will not take this decision")

    monkeypatch.setattr(store, "record", nothing_is_recorded)
    with pytest.raises(store.StoreError):
        assign_review_file(engagement, parked["notice.pdf"].pbc_location, "C01", today=DAY2)
    monkeypatch.undo()
    assert open_intents(engagement)

    sort(engagement, today=DAY3)

    rows = {e.original_name: e for e in read_index(engagement)}
    assert rows["notice.pdf"].decision == FILED and rows["notice.pdf"].identifier == "C01"
    assert open_intents(engagement) == []


#: Where a run is killed, for the conservation claim: every step of a
#: pass's own decision, and a person's.
CRASH_POINTS = ("after the move out of the inbox",
                "the intent before the copy", "after the copy",
                "the record of the rows", "after a person's move")


@pytest.mark.parametrize("point", CRASH_POINTS)
def test_the_conservation_helper_holds_across_every_injected_crash_point(
        engagement, monkeypatch, point):
    """Whichever step a run dies on, the engagement holds the same documents
    afterwards: nothing overwritten, nothing deleted, nothing moved twice,
    nothing copied twice, and the store saying what the record says."""
    from tracker.actions import assign_review_file

    if point == "after a person's move":
        drop(engagement, "scan0012.pdf", "nothing the rules recognise")
        parked = sort(engagement, today=DAY1).review[0]
        before = digests_under(engagement)
        added = []
        moves = moves_made(monkeypatch)
        killed_after_ops(monkeypatch, after=1)
        with pytest.raises(KeyboardInterrupt):
            assign_review_file(engagement, parked.pbc_location, "C01", today=DAY2)
    else:
        original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
        before = digests_under(engagement)
        added = [before[location_of(engagement, original)]]      # one working copy
        moves = moves_made(monkeypatch)
        if point == "after the move out of the inbox":
            killed_after_the_move(monkeypatch)
        elif point == "the intent before the copy":
            killed_at_the_intent(monkeypatch, ledger.OP_COPY)
        elif point == "after the copy":
            killed_after_ops(monkeypatch, after=1)
        else:
            killed_at_the_record(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            sort(engagement, today=DAY1)

    sort(engagement, today=DAY2)

    assert len(read_index(engagement)) == 1
    conserved(engagement, before, moves, added=added)


def test_a_persons_filing_unfiling_and_restore_still_work_with_originals_across_the_trees(engagement):
    """Decisions 110 and 112 through the API, one each, with the original
    in the tree the client can see."""
    import tracker.api as api_module
    from tracker.actions import assign_review_file, restore_working_copy, unfile_document
    from tracker.index import FILE_MOVED

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    assert parked.pbc_location.startswith("../")

    filed = assign_review_file(engagement, parked.pbc_location, "A01", today=DAY2).entry
    assert filed.decision == FILED and (engagement / filed.prepared_location).is_file()

    back = unfile_document(engagement, filed.pbc_location, today=DAY2).entry
    assert back.decision == NEEDS_REVIEW and (engagement / back.prepared_location).is_file()

    # And a copy somebody dragged: the sweep says where it is, and a person
    # puts it back - all of it keyed on an original in the other tree.
    again = assign_review_file(engagement, back.pbc_location, "A01", today=DAY2).entry
    home = engagement / again.prepared_location
    wandered = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME / "dragged.pdf"
    wandered.parent.mkdir(parents=True, exist_ok=True)
    home.rename(wandered)
    sort(engagement, today=DAY2)
    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED
    put_back = restore_working_copy(engagement, row.pbc_location, today=DAY2).entry
    assert put_back.decision == FILED and home.is_file()
    assert api_module._state(engagement)["moved"] == []


@pytest.mark.parametrize("earlier", ("set aside", "working copy deleted"))
@pytest.mark.parametrize("who, confirms", (("Sofia Ruiz", False), ("John Park", True)))
def test_a_re_send_after_a_set_aside_is_name_checked_before_it_files(
        tmp_path, monkeypatch, earlier, who, confirms):
    """Decision 111's two roads route a re-send afresh inside the one
    return, and both of them are name-checked before they file (decision
    128). Without the check a W-2 set aside the day the list had no row for
    it, or one whose working copy a preparer deleted, would file on its
    keywords alone whoever the page named - the very failure the name tier
    exists to stop, arriving by the back door. (Since decision 157 a deleted
    copy is made again from its original first; the re-file road is the
    one a copy takes while its original cannot be read, as here.)"""
    import tracker.actions as actions_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.intents as intents_module
    from tracker.actions import dismiss_review_file

    page = "Form W-2 Wage and Tax Statement 2025"
    w2 = RequestItem(identifier="A01", document="W-2 Wage Statements", period="TY2025",
                     allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("W-2",))
    if earlier == "set aside":
        # Nothing on the list asks for a W-2 yet, so the first arrival
        # parks whoever it names and a person sets it aside; then the list
        # gains the row.
        engagement = make_engagement(tmp_path, [ITEMS[1]], people=(JOHN,))
        drop(engagement, "w2.pdf", page, who=who)
        parked = sort(engagement, today=DAY1).review[0]
        dismiss_review_file(engagement, parked.pbc_location, today=DAY1)
        rows = [ITEMS[1], w2]
    else:
        # The row is on the list but nobody had marked it Named, so the
        # first arrival files on its keywords alone; a preparer deletes the
        # working copy and a person ticks Named in the editor.
        engagement = make_engagement(tmp_path, [replace(w2, named=False)], people=(JOHN,))
        drop(engagement, "w2.pdf", page, who=who)
        filed = sort(engagement, today=DAY1).filed[0]
        (engagement / filed.prepared_location).unlink()
        syncing = locate(engagement, filed.pbc_location)
        real = filer_module.is_cloud_placeholder
        for module in (filer_module, copies_module, intents_module, inbox_module, actions_module):
            monkeypatch.setattr(module, "is_cloud_placeholder", lambda p: p == syncing or real(p))
        rows = [w2]
    save_rules(engagement, rows, load_engagement_info(engagement))

    drop(engagement, "w2.pdf", page, who=who)          # the same bytes again
    report = sort(engagement, today=DAY2)

    if confirms:
        [again] = report.filed
        assert again.identifier == "A01"
        assert again.reason.endswith("; name confirmed (John Park)")
    else:
        assert report.filed == []
        [again] = report.review
        assert again.decision == NEEDS_REVIEW
        assert again.code == reasons.NAME_NOT_ON_PAGE.code


def test_the_one_click_is_refused_on_a_row_rewritten_since_it_was_shown(fed):
    """UX 1: the click carries the row's version, and a row a person set
    aside since the card was drawn is refused before a file is touched.
    Without a version, a row that no longer waits refuses too."""
    from tracker.actions import dismiss_review_file
    from tracker.filer import NOT_WAITING, StaleRowError

    father, llc = fed
    drop(father, "tb.pdf", "Trial balance as of December 31 2025", who="Park & Lee LLC")
    [waiting] = sort_all([father, llc], home=[father], today=DAY1)[father].review
    shown = seq_of(father, waiting)
    dismiss_review_file(father, waiting.pbc_location, "not theirs", today=DAY2)
    files, lines = every_byte(father), len(ledger.read_events(father))

    with pytest.raises(StaleRowError):
        click(father, waiting, llc, seq=shown)
    with pytest.raises(FilingError, match=NOT_WAITING.format(name="tb.pdf")):
        click(father, waiting, llc)

    assert every_byte(father) == files and len(ledger.read_events(father)) == lines
    assert read_index(llc) == [] and not open_intents(llc)
    [row] = read_index(father)
    assert row.waits_for == ""                  # set aside, it waits for nothing


def test_a_set_aside_re_send_naming_a_fed_households_person_parks_too(fed):
    """The _sort_one road (decision 137 B#5's reasoning, now for a named
    page): the LLC set a notice aside, its list gained the row that takes
    it, and the father sends the same bytes. Routed afresh against the
    LLC's list and naming the LLC, it is not filed there: it parks at home
    for one click, saying it was sent again."""
    from tracker.actions import dismiss_review_file
    from tracker.filer import RESENT_AFTER_SET_ASIDE

    father, llc = fed
    notice = "Agency notice of adjustment 2025"
    drop(llc, "notice.pdf", notice, who="Park & Lee LLC")
    [parked] = sort_all([llc], today=DAY1)[llc].review
    dismiss_review_file(llc, parked.pbc_location, "nothing asks for it", today=DAY1)
    notices = RequestItem(identifier="B02", document="Agency Notices", period="TY2025",
                          allowed_extensions=("pdf",), min_size_kb=0,
                          required_keywords=("agency notice",))
    save_rules(llc, [*BUSINESS, notices], load_engagement_info(llc))
    before = read_index(llc)

    drop(father, "notice.pdf", notice, who="Park & Lee LLC")
    done = sort_all([father, llc], home=[father], today=DAY2)

    assert read_index(llc) == before and done[llc].filed == []
    [row] = read_index(father)
    assert row.decision == NEEDS_REVIEW
    assert row.code == reasons.NAMED_ACROSS_HOUSEHOLDS.code
    assert row.reason.startswith(RESENT_AFTER_SET_ASIDE.split("{")[0])
    assert row.waiting_for.identifiers == ("B02",)
    assert row.pbc_location == original_at(father, "notice.pdf")
    rows_rest_at_home(father, llc)


def test_a_released_row_is_gone_from_the_index_the_queue_and_every_count_and_the_journal_says_where_it_went(
        fed):
    """The document is the other return's now, and this return holds
    nothing about it (decision 132): not a row, not a place in the queue,
    not a count, not a second decision. Only the journal keeps the line,
    and it names the return and the request - never a person."""
    from tracker import review
    from tracker.actions import assign_review_file
    from tracker.filer import RELEASED_TO, FilingError, hand_over

    father, llc = fed
    parked = parked_notice(father)
    done = hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)

    assert read_index(father) == []
    assert store.documents(store.connect(), father) == []
    assert review.triage(father, read_index(father), items=load_manifest(father)) == []
    assert [e for e in read_index(father) if e.decision in (NEEDS_REVIEW, DUPLICATE)] == []
    with pytest.raises(FilingError, match="nothing in the index is called"):
        hand_over(father, parked.pbc_location, llc, "B01", today=DAY3)
    with pytest.raises(FilingError, match="nothing in the index is called"):
        assign_review_file(father, parked.pbc_location, "A01", today=DAY3)
    said = [e for e in ledger.read_events(father) if e[ledger.EVENT_KEY] == ledger.RELEASED]
    assert [e[ledger.REASON_KEY] for e in said] == [
        RELEASED_TO.format(label=done.label, identifier="B01")]
    assert "John Park" not in said[0][ledger.REASON_KEY]


def test_a_persons_filing_and_the_hand_over_are_named_to_fit_and_refuse_only_below_the_floor(
        tmp_path, path_setting):
    """A person's filing and a hand-over name the working copy the way the
    pass does: cut to fit where the canonical name does not, and refused
    - nothing moved - only where not even the shortest name fits: a
    person's filing with PATH_NO_ROOM, a hand-over with PATH_NO_ROOM_IN
    naming the taking return, since the person reads it on another
    return's page (decision 204's review, S-1)."""
    from tests.builders import root_for_a_return_of
    from tracker.actions import assign_review_file
    from tracker.filer import PATH_NO_ROOM_IN, _details_of, _label_of, hand_over
    from tracker.layout import path_limit

    # One household, three returns: home fits; ``cut`` leaves A01 nine short;
    # ``none`` leaves its Prepared 43 characters for a 44-character name.
    # Some characters of the length are the root's, not the names': a name
    # is at most eighty characters since decision 188.
    root = root_for_a_return_of(tmp_path, no_room_return() - 62, return_name="1040 - Home")
    home = make_engagement(root, ROOM_ITEMS, return_name="1040 - Home")
    cut = make_engagement(root, [replace(ROOM_ITEMS[0], period=TIGHT_PERIOD)],
                          return_name="1040 - " + "s" * 66)
    none = make_engagement(root, [replace(ROOM_ITEMS[0], period=LONG_PERIOD)],
                           return_name="1040 - " + "t" * 66)
    assert len(str(cut / PREPARED_DIR_NAME / f"A01 - W-2 Wage Statements - {TIGHT_PERIOD}.pdf")) \
        == path_limit() + OVER
    assert len(str(none)) + FOLDER_BELOW == no_room_prepared()
    drop(home, "note.pdf", "A letter the list does not ask for")
    drop(home, "other.pdf", "Another letter the list does not ask for")
    sort_all([home, cut, none], today=DAY1)
    parked = {e.original_name: e for e in read_index(home) if e.decision == NEEDS_REVIEW}
    assert set(parked) == {"note.pdf", "other.pdf"}

    # Refused below the floor, with the sentence, and nothing moved.
    before = sorted(str(p) for p in root.rglob("*"))
    with pytest.raises(FilingError) as refused:
        hand_over(home, parked["note.pdf"].pbc_location, none, "A01", today=DAY2)
    assert str(refused.value) == PATH_NO_ROOM_IN.format(
        label=_label_of(none, _details_of(none)),
        length=path_limit() + 1, limit=path_limit(), ext=".pdf")
    assert sorted(str(p) for p in root.rglob("*")) == before

    # Handed to the return with room for a cut name: named to fit.
    handed = hand_over(home, parked["note.pdf"].pbc_location, cut, "A01", today=DAY2)
    copy = locate(cut, handed.target_entry.prepared_location)
    assert copy.is_file() and copy.name == "A01 - W-2 Wage S - Jan 2025 to Dec 2025.pdf"
    assert len(str(copy)) == path_limit()

    # A person's filing in a return with no room: refused, nothing moved.
    tight = make_engagement(root_for_a_return_of(tmp_path / "t", no_room_return()),
                            [replace(ROOM_ITEMS[0], period=LONG_PERIOD)])
    drop(tight, "note.pdf", "A letter the list does not ask for")
    sort(tight, today=DAY1)
    [waiting] = [e for e in read_index(tight) if e.decision == NEEDS_REVIEW]
    before = sorted(str(p) for p in (tmp_path / "t").rglob("*"))
    with pytest.raises(FilingError, match="at its shortest"):
        assign_review_file(tight, waiting.pbc_location, "A01", today=DAY2)
    assert sorted(str(p) for p in (tmp_path / "t").rglob("*")) == before

    # And one with room for a cut name: filed under it.
    roomy = tight_return(tmp_path / "r", OVER)
    drop(roomy, "note.pdf", "A letter the list does not ask for")
    sort(roomy, today=DAY1)
    [waiting] = [e for e in read_index(roomy) if e.decision == NEEDS_REVIEW]
    done = assign_review_file(roomy, waiting.pbc_location, "A01", today=DAY2)
    assert done.entry.prepared_location.endswith("/A01 - W-2 Wage S - Jan 2025 to Dec 2025.pdf")
    assert locate(roomy, done.entry.prepared_location).is_file()


def test_unfiling_a_long_named_document_cuts_its_review_copy_to_fit(tmp_path, path_setting):
    """F1: a person's unfiling names the review copy the way the pass's park
    does - the client's name cut to the room the review folder leaves,
    the extension kept - where before it was written under the whole name,
    past the limit. The row keeps the client's whole name."""
    from tests.builders import root_for_a_return_of
    from tracker.actions import unfile_document
    from tracker.layout import path_limit

    engagement = make_engagement(root_for_a_return_of(tmp_path, 180), ROOM_ITEMS)
    inbox = inbox_of(engagement)
    name = "W-2 " + "w" * (255 - len(str(inbox)) - 1 - len("W-2 .pdf")) + ".pdf"
    assert len(str(inbox / name)) == 255
    assert len(str(review_dir(engagement))) + 1 + len(name) > path_limit()
    drop(engagement, name, "Form W-2 Wage and Tax Statement 2025")
    [filed] = sort(engagement, today=DAY1).filed

    result = unfile_document(engagement, filed.pbc_location, today=DAY2)

    copy = locate(engagement, result.entry.prepared_location)
    assert copy.is_file() and copy.parent == review_dir(engagement)
    assert copy.suffix == ".pdf" and copy.name.startswith("W-2 www")
    assert len(str(copy)) == path_limit()
    assert result.entry.original_name == name
    assert (originals(engagement) / name).is_file()                  # the original, uncut


def test_a_re_sent_set_aside_document_files_under_its_not_asked_row_and_the_earlier_entry_keeps_its_answer(
        tmp_path):
    """Decision 111 is untouched by decision 142. A document a person set
    aside as Not requested - the day the list had no row for it - keeps
    that row and its answer. The client sending it again is a new arrival,
    routed afresh as 111 says: once the catalog's row is on the return as
    not asked, the re-send files there, and its row quotes the earlier
    decision whole."""
    from tracker.actions import dismiss_review_file
    from tracker.filer import RESENT_AFTER_SET_ASIDE
    from tracker.index import NOT_REQUESTED

    engagement = make_engagement(tmp_path, [ITEMS[0]])
    drop(engagement, "1098.pdf", "Form 1098 Mortgage Interest Statement 2025")
    parked = sort(engagement, today=DAY1).review[0]
    dismissed = dismiss_review_file(engagement, parked.pbc_location, "not ours", today=DAY2).entry

    save_rules(engagement, [*load_manifest(engagement), replace(ITEMS[1], asked=False)],
               load_engagement_info(engagement))
    drop(engagement, "1098.pdf", "Form 1098 Mortgage Interest Statement 2025")   # the same bytes
    report = sort(engagement, today=DAY2)

    [again] = report.filed
    assert again.identifier == "C01"
    assert RESENT_AFTER_SET_ASIDE.format(earlier=dismissed.reason) in again.reason
    earlier = [row for row in read_index(engagement) if row.decision == NOT_REQUESTED]
    assert [row.reason for row in earlier] == [dismissed.reason]


def test_a_person_can_still_mark_that_row_missing(tmp_path):
    """d146, claim 6. A person marks A02 missing again: the statement stays
    filed under E01 with its copy where it is, A02 comes off its Also
    Answers cell on the record (one answer_withdrawn_by_person line), A02
    goes back to Missing with the regression note, the letter asks for it
    again, and A04 is still answered. Asking twice is refused by name, and
    a rebuilt store agrees with the person."""
    from tracker.actions import mark_missing_again
    from tracker.index import MARKED_MISSING
    from tracker.layout import root_of
    from tracker.manifest import Status
    from tracker.readme_ack import received_for
    from tracker.reminder import draft_reminder
    from tracker.scanner import REGRESSION_NOTE

    engagement = _consolidated_return(tmp_path)
    copies_before = sorted((engagement / PREPARED_DIR_NAME).rglob("*.pdf"))

    result = mark_missing_again(engagement, "Schwab 2025 1099.pdf", "A02",
                                note="no interest detail", today=DAY2)
    assert result.scan_note == ""
    [row] = [r for r in read_index(engagement) if r.decision == FILED]
    assert row.identifier == "E01" and row.answers == "A04 (1099-misc)"
    assert row.reason.endswith(MARKED_MISSING.format(
        identifier="A02", date=DAY2.isoformat(), note=" (no interest detail)"))
    assert len(events_named(engagement, ledger.ANSWER_WITHDRAWN_BY_PERSON)) == 1
    assert sorted((engagement / PREPARED_DIR_NAME).rglob("*.pdf")) == copies_before

    a02 = _status(engagement, "A02")
    assert a02.status == Status.MISSING
    assert a02.validation_notes.startswith(REGRESSION_NOTE.split(" {date}")[0].format(
        status=Status.RECEIVED))
    assert _status(engagement, "A04").status == Status.RECEIVED
    assert _status(engagement, "E01").status == Status.RECEIVED
    assert "A02" in draft_reminder(engagement, today=DAY2).asked
    assert "A02" not in {line.identifier for line in received_for([engagement]).lines}

    with pytest.raises(FilingError, match="does not answer A02"):
        mark_missing_again(engagement, "Schwab 2025 1099.pdf", "A02", today=DAY2)

    root = root_of(engagement)
    db = os.environ[store.ENV_STORE]
    store.close()
    os.unlink(db)
    fresh = store.connect()
    store.rebuild_engagement(fresh, root, engagement)
    assert [r.answers for r in read_index(engagement) if r.decision == FILED] == ["A04 (1099-misc)"]
    assert store_check.check(fresh, root, engagement) == []


def test_unfiling_the_statement_takes_its_answers_with_it(tmp_path):
    """d146. The answers are the filed row's: unfile the statement and its
    row parks with no answers, so A02 and A04 go back to what their own
    folders hold rather than staying Received on a document in review."""
    from tracker.actions import unfile_document
    from tracker.manifest import Status

    engagement = _consolidated_return(tmp_path)
    unfile_document(engagement, "Schwab 2025 1099.pdf", today=DAY2)
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.answers == ""
    assert _status(engagement, "A02").status == Status.MISSING
    assert _status(engagement, "A04").status == Status.MISSING


def test_a_respelled_identifier_renames_the_copies_only(engagement):
    """Claim 8: decision 160's rename, flat. Each copy the record names
    under the old identifier takes the new one at the front of its name,
    beside where it was; no folder is made, none is renamed or removed; a
    file named for the old identifier that no row names is left and
    named."""
    from tracker.actions import rename_request
    from tracker.manifest import list_head

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025 Acme Corp")
    drop(engagement, "w2 second job.pdf", "Form W-2 Wage and Tax Statement 2025 Birch LLC")
    assert len(sort(engagement, today=DAY1).filed) == 2
    prepared_dir = engagement / PREPARED_DIR_NAME
    (prepared_dir / "A01 - my own notes.pdf").write_bytes(b"a person's file")

    result = rename_request(engagement, "A01", "A1", head=list_head(engagement), today=DAY2)

    assert result.moved == 2 and result.rows == 2
    assert result.left == (f"{PREPARED_DIR_NAME}/A01 - my own notes.pdf",)
    assert sorted(p.name for p in prepared_dir.iterdir() if p.is_file()) == [
        "A01 - my own notes.pdf",
        "A1 - W-2 Wage Statements - TY2025 (2).pdf",
        "A1 - W-2 Wage Statements - TY2025.pdf",
    ]
    _only_the_review_folder(engagement)
    assert sorted(r.prepared_location for r in read_index(engagement)) == [
        f"{PREPARED_DIR_NAME}/A1 - W-2 Wage Statements - TY2025 (2).pdf",
        f"{PREPARED_DIR_NAME}/A1 - W-2 Wage Statements - TY2025.pdf",
    ]
    assert {r.identifier for r in read_index(engagement)} == {"A1"}


def test_a_rename_refusal_quotes_at_most_eighty_characters_of_what_was_typed(engagement):
    """P293, the third review's H2: the two rename sentences that echo an
    identifier go through ``quoted``, so 120-character names (or a 10,000
    character one) come back cut with ASCII dots, never whole."""
    from tracker.actions import RENAME_CASE_ONLY, rename_request
    from tracker.layout import QUOTE_MAX_CHARS, quoted
    from tracker.manifest import RENAME_NOT_ON_THE_LIST, ManifestError, list_head, renamed_rules

    before = files_under(engagement)
    lines = len(ledger.read_events(engagement))
    with pytest.raises(FilingError) as refused:
        rename_request(engagement, "L" * 120, "l" * 120, head=list_head(engagement), today=DAY2)
    said = str(refused.value)
    assert said == RENAME_CASE_ONLY.format(old=quoted("L" * 120), new=quoted("l" * 120))
    assert len(said) < 260 and said.count("...") == 2   # 2 x 80 of echo + the fixed words
    assert "L" * (QUOTE_MAX_CHARS - 3) + "..." in said and "L" * QUOTE_MAX_CHARS not in said
    with pytest.raises(ManifestError) as absent:
        renamed_rules(engagement, "Z" * 10_000, "Y01")
    assert str(absent.value) == RENAME_NOT_ON_THE_LIST.format(old=quoted("Z" * 10_000))
    assert len(str(absent.value)) < 240
    assert files_under(engagement) == before
    assert len(ledger.read_events(engagement)) == lines


def test_a_rename_refused_because_the_target_name_is_taken_moves_nothing(engagement):
    """The review of 168, N-5: every request's copies share Prepared, so a
    file nothing recorded may already hold the name a rename would give a
    copy. The rename is refused by name before anything is written: no
    copy moves, the list keeps the old identifier and the record gains no
    line."""
    from tracker.actions import RENAME_COPY_TAKEN, rename_request
    from tracker.manifest import list_head

    drop(engagement, "w2 john.pdf", "Form W-2 Wage and Tax Statement 2025 Acme Corp")
    [filed] = sort(engagement, today=DAY1).filed
    prepared_dir = engagement / PREPARED_DIR_NAME
    squatter = prepared_dir / "A1 - W-2 Wage Statements - TY2025.pdf"
    squatter.write_bytes(b"a person's own file")
    before = files_under(engagement)
    lines = len(ledger.read_events(engagement))

    with pytest.raises(FilingError) as refused:
        rename_request(engagement, "A01", "A1", head=list_head(engagement), today=DAY2)

    assert str(refused.value) == RENAME_COPY_TAKEN.format(location=location_of(engagement, squatter))
    assert files_under(engagement) == before
    assert len(ledger.read_events(engagement)) == lines
    assert [r.prepared_location for r in read_index(engagement)] == [filed.prepared_location]
    assert [i.identifier for i in load_manifest(engagement)] == ["A01", "C01"]
    assert squatter.read_bytes() == b"a person's own file"


def test_a_rename_to_an_identifier_past_the_typing_limit_is_refused_and_moves_nothing(engagement):
    """P291, the review's F1: the new identifier is one a person typed, so it
    is held to the typing limit and the editor's wording (without a row)
    before anything is written."""
    from tracker.actions import rename_request
    from tracker.manifest import list_head

    lines = len(ledger.read_events(engagement))
    with pytest.raises(FilingError) as refused:
        rename_request(engagement, "A01", "B" * 120, head=list_head(engagement), today=DAY2)
    said = str(refused.value)
    assert said.startswith("Identifier '" + "B" * 77 + "...' may have at most 80 characters, got 120")
    assert len(said) < 200
    with pytest.raises(FilingError, match="U\\+00A0 NO-BREAK SPACE"):
        rename_request(engagement, "A01", "B\u00a001", head=list_head(engagement), today=DAY2)
    assert len(ledger.read_events(engagement)) == lines
    assert [i.identifier for i in load_manifest(engagement)] == ["A01", "C01"]


def test_a_copy_and_original_both_gone_is_named_not_chased(engagement):
    """d157, claim 3 (ruling B5). The copy is gone and so is the client's
    original: nothing can be made again and nothing is guessed. The row is
    File Moved with the both-gone sentence, said once; the request reads
    Missing with a firm-side note that is not decision 110's put-it-back
    wording; the letter does not ask - a person looks first. Put it back,
    keep it here and send to review each refuse in the one sentence."""
    from tracker.manifest import Status
    from tracker.reminder import draft_reminder

    filed = _filed_1098(engagement)
    (engagement / filed.prepared_location).unlink()
    (originals(engagement) / "1098.pdf").unlink()

    report, _scanned = _a_pass(engagement, DAY2)

    draft = draft_reminder(engagement, today=DAY2)
    assert "C01" not in draft.asked
    assert "C01" in {flag.item.identifier for flag in draft.needs_attention}
    from tracker.actions import (
        assign_review_file,
        restore_working_copy,
        unfile_document,
    )
    from tracker.filer import NOTHING_TO_PUT_BACK
    from tracker.index import BOTH_GONE_SENTENCE, FILE_MOVED, both_gone

    sentence = BOTH_GONE_SENTENCE.format(home=filed.prepared_location, prepared=PREPARED_DIR_NAME,
                                         pbc=filed.pbc_location, date=DAY2.isoformat())
    [row] = read_index(engagement)
    assert row.decision == FILE_MOVED and both_gone(row)
    assert row.reason == f"{filed.reason}; {sentence}"
    assert sentence in [e.error for e in report.attention]
    item = _status(engagement, "C01")
    assert item.status == Status.MISSING
    assert reasons.COPY_AND_ORIGINAL_GONE.code in item.note_code_list
    assert reasons.FILE_MOVED.code not in item.note_code_list
    assert events_named(engagement, ledger.COPY_REMADE) == []

    lines = len(ledger.read_events(engagement))
    again, _ = _a_pass(engagement, DAY3)
    assert len(ledger.read_events(engagement)) == lines         # said once
    assert sentence not in [e.error for e in again.attention]

    files = files_under(engagement)
    refusal = NOTHING_TO_PUT_BACK.format(prepared=PREPARED_DIR_NAME, pbc=filed.pbc_location)
    for answer in (lambda: restore_working_copy(engagement, filed.pbc_location, today=DAY3),
                   lambda: assign_review_file(engagement, filed.pbc_location, "C01", today=DAY3),
                   lambda: unfile_document(engagement, filed.pbc_location, today=DAY3)):
        with pytest.raises(FilingError) as refused:
            answer()
        assert str(refused.value) == refusal
    assert files_under(engagement) == files
    assert len(ledger.read_events(engagement)) == lines


def test_marking_a_both_gone_row_missing_asks_the_client_and_the_readme_agrees(engagement):
    """d157, ruling B6. Mark missing (decision 146's action) takes the row's
    own request, on a row whose copy and original are both gone and only
    there. The row stays on the record with the person's sentence and one
    ``answer_withdrawn_by_person`` line; it stops counting, stops holding the
    request firm-side and leaves the client's received list; the request
    reads Missing and the letter asks; the pass never makes it again or
    flags it again. The client's answer - the same bytes - is filed as a
    new arrival under a place of its own."""
    from tracker.actions import mark_missing_again
    from tracker.filer import REFILED_AFTER_GONE
    from tracker.index import MARKED_MISSING, marked_missing
    from tracker.manifest import Status
    from tracker.readme_ack import received_for

    filed = _filed_1098(engagement)
    with pytest.raises(FilingError, match="does not answer C01"):
        mark_missing_again(engagement, filed.pbc_location, "C01", today=DAY1)   # its copy is here
    body = (originals(engagement) / "1098.pdf").read_bytes()
    (engagement / filed.prepared_location).unlink()
    (originals(engagement) / "1098.pdf").unlink()
    _a_pass(engagement, DAY2)
    assert "C01" not in _asked(engagement, DAY2)
    assert "C01" in {line.identifier for line in received_for([engagement]).lines}

    result = mark_missing_again(engagement, filed.pbc_location, "C01", note="gone from Drive",
                                today=DAY3)

    assert result.scan_note == ""
    [row] = read_index(engagement)
    assert marked_missing(row) and row.identifier == "C01" and row.prepared_location == ""
    assert row.reason.endswith(MARKED_MISSING.format(
        identifier="C01", date=DAY3.isoformat(), note=" (gone from Drive)"))
    assert len(events_named(engagement, ledger.ANSWER_WITHDRAWN_BY_PERSON)) == 1
    item = _status(engagement, "C01")
    assert item.status == Status.MISSING and reasons.first_of(item.note_code_list) is None
    assert "C01" in _asked(engagement, DAY3)
    assert "C01" not in {line.identifier for line in received_for([engagement]).lines}
    with pytest.raises(FilingError):
        mark_missing_again(engagement, filed.pbc_location, "C01", today=DAY3)   # once is enough
    assert store_check.check(store.connect(), root_of(engagement), engagement) == []

    lines = len(ledger.read_events(engagement))
    quiet, _ = _a_pass(engagement, DAY3)
    assert quiet.attention == [] and len(ledger.read_events(engagement)) == lines

    (inbox_of(engagement) / "1098.pdf").write_bytes(body)            # the client answers
    report, _ = _a_pass(engagement, DAY3 + dt.timedelta(days=1))
    [again] = report.filed
    assert again.pbc_location == original_at(engagement, "1098 (2).pdf")
    assert REFILED_AFTER_GONE.format(name="1098.pdf") in again.reason
    assert read_index(engagement)[0] == row                          # the marked row is untouched
    assert _status(engagement, "C01").status == Status.RECEIVED


def test_put_it_back_on_a_filed_row_whose_copy_was_deleted_makes_it_again(engagement):
    """d157, ruling B8 (the audit's D-3: Restore refused "not a moved copy (it
    is Filed)"). Put it back on a Filed row whose copy is gone makes it
    again through the pass's own function, with the pass's sentence and
    event, decided by the person; the re-scan finds the request Received.
    A Filed row whose copy is home has nothing to put back, as before."""
    from tracker.actions import restore_working_copy
    from tracker.filer import REMADE_SENTENCE
    from tracker.manifest import Status

    filed = _filed_1098(engagement)
    copy = engagement / filed.prepared_location
    copy.unlink()

    result = restore_working_copy(engagement, filed.pbc_location, today=DAY2)

    assert result.copied_from_original and not result.moved_home and not result.already_home
    assert result.parked_as == "" and result.scan_note == ""
    assert copy.read_bytes() == (originals(engagement) / "1098.pdf").read_bytes()
    [row] = read_index(engagement)
    assert row.decision == FILED and row.reason == "{}; {}".format(filed.reason, REMADE_SENTENCE.format(
        home=filed.prepared_location, pbc=filed.pbc_location, date=DAY2.isoformat(),
        prepared=PREPARED_DIR_NAME))
    assert len(events_named(engagement, ledger.COPY_REMADE)) == 1
    assert events_named(engagement, ledger.RESTORED_BY_PERSON) == []
    [intent] = [e for e in events_named(engagement, ledger.MOVING)
                if e[ledger.EVENT_KEY_AFTER] == ledger.COPY_REMADE]
    assert intent[ledger.DECIDED_BY_KEY] == ledger.BY_PERSON
    assert _status(engagement, "C01").status == Status.RECEIVED
    assert open_intents(engagement) == []

    with pytest.raises(FilingError, match="is not a moved copy"):
        restore_working_copy(engagement, filed.pbc_location, today=DAY2)


def test_a_program_sent_again_after_it_was_set_aside_parks_again_unread_with_no_copy(engagement):
    """The review's M2: a program a person set aside, sent again, is asked
    before it is read - so its name reaches no request, it gets no review
    copy and it holds nothing - and its row says it was sent again."""
    from tracker import reminder
    from tracker.actions import dismiss_review_file
    from tracker.filer import RESENT_AFTER_SET_ASIDE

    program = b"MZ Form W-2 Wage and Tax Statement 2025"
    (inbox_of(engagement) / "W-2 2025.pdf.exe").write_bytes(program)
    sort(engagement, today=DAY1)
    [first] = read_index(engagement)
    dismiss_review_file(engagement, first.pbc_location)

    (inbox_of(engagement) / "W-2 2025.pdf.exe").write_bytes(program)
    sort(engagement, today=DAY2)

    again = read_index(engagement)[-1]
    assert again.decision == NEEDS_REVIEW and again.code == reasons.NOT_A_DOCUMENT.code
    assert again.prepared_location == "" and again.candidates == "" and again.evidence == ""
    assert again.reason.startswith(RESENT_AFTER_SET_ASIDE.split("{")[0])
    assert again.reason.endswith(reasons.NOT_A_DOCUMENT.template)
    assert _review_folder_files(engagement) == []
    assert reminder._parked_holds(load_manifest(engagement), [again]) == {}


def test_two_programs_in_one_zip_each_answer_to_their_own_handle(engagement):
    """The review's M3: a program taken from an email or a zip has no
    location, so its handle is its record key - unique, where "" named
    every such row at once. Setting the first aside by its handle and seq
    sets aside exactly that row, and an empty handle names none."""
    import io
    import zipfile

    from tracker.actions import dismiss_review_file
    from tracker.filer import NO_HANDLE, find_parked
    from tracker.index import NOT_REQUESTED

    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        archive.writestr("invoice.js", b"WScript.Echo(1)")
        archive.writestr("payroll.exe", b"MZ")
    (inbox_of(engagement) / "docs.zip").write_bytes(packed.getvalue())
    sort(engagement, today=DAY1)

    rows = read_index(engagement)
    programs = [row for row in rows if row.code == reasons.NOT_A_DOCUMENT.code]
    assert [row.original_name for row in programs] == ["invoice.js", "payroll.exe"]
    assert all(row.pbc_location == "" for row in programs)
    handles = [ledger_key(row) for row in programs]
    assert len(set(handles)) == 2 and "" not in handles

    seqs = store.document_seqs(store.connect(), engagement)
    result = dismiss_review_file(engagement, handles[0], seq=seqs[handles[0]])

    assert result.entry.original_name == "invoice.js"
    after = {row.original_name: row.decision for row in read_index(engagement)
             if row.code in (reasons.NOT_A_DOCUMENT.code, reasons.DISMISSED_BY_PERSON_CODE)}
    assert after == {"invoice.js": NOT_REQUESTED, "payroll.exe": NEEDS_REVIEW}
    with pytest.raises(FilingError, match=NO_HANDLE):
        find_parked(read_index(engagement), "")


def _a_filed_macro_workbook(engagement, monkeypatch):
    """A macro workbook parked, then filed under A01 by a person, with the
    mark working; returns its row."""
    import tracker.copies as copies_module
    from tracker.actions import assign_review_file

    monkeypatch.setattr(copies_module, "mark_from_internet", lambda path: True)
    (inbox_of(engagement) / "budget.xlsm").write_bytes(b"PK a workbook with macros")
    sort(engagement, today=DAY1)
    [parked] = read_index(engagement)
    assign_review_file(engagement, parked.pbc_location, "A01", today=DAY1)
    [row] = read_index(engagement)
    assert row.decision == FILED
    return row


def _refuse_the_mark(monkeypatch):
    import tracker.copies as copies_module

    def refused(path):
        raise OSError(95, "Operation not supported", str(path))

    monkeypatch.setattr(copies_module, "mark_from_internet", refused)


def test_a_refused_mark_on_an_unfile_records_nothing_and_the_next_pass_runs(engagement, monkeypatch):
    """The re-check's M-N1: unfiling a macro working copy on a volume that
    will not hold the mark is refused before anything is written down - no
    open intent, the row still Filed at its copy - so the passes after it
    run, where before every one of them raised on the intent it left."""
    from tracker.actions import unfile_document
    from tracker.filer import MarkRefusedError

    row = _a_filed_macro_workbook(engagement, monkeypatch)
    _refuse_the_mark(monkeypatch)

    with pytest.raises(MarkRefusedError):
        unfile_document(engagement, row.pbc_location, today=DAY2)

    assert store.open_intents(store.connect(), engagement) == []
    assert read_index(engagement) == [row]
    assert locate(engagement, row.prepared_location).read_bytes() == b"PK a workbook with macros"
    for _ in range(2):
        report = sort(engagement, today=DAY3)
        assert report.errors == [] and report.attention == []
    assert read_index(engagement) == [row] and _review_folder_files(engagement) == []


def test_a_refused_mark_on_an_interrupted_step_is_said_once_and_the_pass_goes_on(engagement, monkeypatch):
    """The re-check's M-N1, for an intent already open: an unfiling killed
    after it was written down, finished by a pass on a volume that now
    refuses the mark. The recovery abandons it and says so once - the
    mark's own sentence - and the pass goes on; the row stays Filed at its
    copy, and the next pass has nothing to say."""
    import tracker.actions as actions_module
    from tracker.actions import unfile_document
    from tracker.intents import INTERRUPTED_MARK_REFUSED

    row = _a_filed_macro_workbook(engagement, monkeypatch)

    def killed(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(actions_module, "_carry_out_a_persons_ops", killed)
    with pytest.raises(KeyboardInterrupt):
        unfile_document(engagement, row.pbc_location, today=DAY2)
    assert len(store.open_intents(store.connect(), engagement)) == 1
    monkeypatch.undo()
    _refuse_the_mark(monkeypatch)

    report = sort(engagement, today=DAY3)

    [said] = report.attention
    assert said.name == "budget.xlsm"
    assert "could not be marked as from the internet" in said.error
    assert said.error.endswith(INTERRUPTED_MARK_REFUSED)
    assert store.open_intents(store.connect(), engagement) == []
    assert read_index(engagement) == [row] and _review_folder_files(engagement) == []
    assert locate(engagement, row.prepared_location).read_bytes() == b"PK a workbook with macros"
    again = sort(engagement, today=DAY3)
    assert again.errors == [] and again.attention == []


def _issuer_list(tmp_path):
    """A return whose list asks for K-1s one row per issuer: the catalog's
    K-1 row and one issuer row, both as the catalog builds them, taking a
    test page of any size."""
    from tracker.templates import issuer_row, item_from_spec, k1_row

    rows = [item_from_spec(k1_row()), item_from_spec(issuer_row("F02", "Ashford Holdings"))]
    return make_engagement(tmp_path, [replace(row, min_size_kb=0) for row in rows])


def _an_unnamed_issuers_k1(engagement):
    """A K-1 from an issuer the list does not name, parked for a person."""
    drop(engagement, "k-1 dunmore.pdf",
         f"Schedule K-1 {TEST_YEAR} (Form 1065) Partner's Share of Income, Deductions, Credits "
         "Part I Information About the Partnership Dunmore Capital Group")
    parked = sort(engagement, today=DAY1).review[0]
    assert parked.code == reasons.ISSUER_NOT_NAMED.code
    return parked


def test_a_killed_filing_that_adds_its_row_is_finished_forward_with_the_row(tmp_path, monkeypatch):
    """The issuer row rides the filing's intent (decision 201): a machine
    that dies with the copy moved and nothing recorded is finished by the
    next pass as the person's filing, the row's event and the new row's
    ``rules_changed`` in the one record call, so the list gains the row
    exactly when the filing lands."""
    from tracker.actions import assign_review_file
    from tracker.filer import ASSIGNED_BY_PERSON
    from tracker.manifest import list_head
    from tracker.templates import issuer_item

    engagement = _issuer_list(tmp_path)
    parked = _an_unnamed_issuers_k1(engagement)
    row = issuer_item("F03", "Dunmore Capital", TEST_YEAR)
    before = digests_under(engagement)
    moves = moves_made(monkeypatch)
    killed_after_ops(monkeypatch, after=1)

    with pytest.raises(KeyboardInterrupt):
        assign_review_file(engagement, parked.pbc_location, "F03", today=DAY2,
                           adding=row, head=list_head(engagement))

    [intent] = open_intents(engagement)
    assert "F03" not in {i.identifier for i in load_manifest(engagement)}      # nothing recorded yet
    calls = counted_records(monkeypatch)

    sort(engagement, today=DAY3)

    [filed] = read_index(engagement)
    assert filed.decision == FILED and filed.identifier == "F03"
    assert filed.reason.startswith(f"{ASSIGNED_BY_PERSON} on {DAY2.isoformat()}")
    assert calls[0] == (ledger.ASSIGNED_BY_PERSON, ledger.RULES_CHANGED)
    added = {i.identifier: i for i in load_manifest(engagement)}["F03"]
    assert added.required_keywords == ("Dunmore Capital",)
    conserved(engagement, before, moves)


def test_a_refused_issuer_filing_leaves_the_list_the_index_and_the_folders_as_they_were(
        tmp_path, monkeypatch):
    """Every refusal of the issuer path comes before a byte is read or
    written (decision 201): the list, the index and every file are exactly
    as they were, whichever check refuses."""
    from tracker.actions import (
        ISSUER_DOES_NOT_NARROW,
        ISSUER_LIST_MOVED,
        NOT_AN_ISSUER_CARD,
        assign_review_file,
    )
    from tracker.filer import FilingError
    from tracker.manifest import ISSUER_NAMED_TWICE, ManifestError, list_head
    from tracker.records import entry_to_json
    from tracker.templates import issuer_item

    engagement = _issuer_list(tmp_path)
    parked = _an_unnamed_issuers_k1(engagement)
    drop(engagement, "notice.pdf", "an agency notice nothing asks for")
    notice = next(e for e in sort(engagement, today=DAY1).review if e.original_name == "notice.pdf")
    seqs = store.document_seqs(store.connect(), engagement)
    head = list_head(engagement)
    rules = [records_rule(i) for i in load_manifest(engagement)]
    index = [entry_to_json(e) for e in read_index(engagement)]
    files = digests_under(engagement)

    def refused(match, original, row, **given):
        with pytest.raises((FilingError, ManifestError), match=match):
            assign_review_file(engagement, original, row.identifier, today=DAY2, adding=row,
                               **{"head": head, "seq": seqs[ledger_key(parked)], **given})
        assert [records_rule(i) for i in load_manifest(engagement)] == rules
        assert [entry_to_json(e) for e in read_index(engagement)] == index
        assert digests_under(engagement) == files

    dunmore = issuer_item("F03", "Dunmore Capital", TEST_YEAR)
    refused(re_escape(ISSUER_LIST_MOVED), parked.pbc_location, dunmore, head="0" * 64)
    refused("is not as you saw it", parked.pbc_location, dunmore, seq=seqs[ledger_key(parked)] + 1)
    refused(re_escape(NOT_AN_ISSUER_CARD.format(name="notice.pdf")), notice.pbc_location, dunmore,
            seq=seqs[ledger_key(notice)])
    refused("is inside", parked.pbc_location, issuer_item("F03", "Ashford", TEST_YEAR))
    refused(re_escape(ISSUER_NAMED_TWICE.split("{name}")[1]), parked.pbc_location,
            issuer_item("F03", "Ashford Holdings", TEST_YEAR))
    stray = replace(dunmore, any_keywords=("an unrelated phrase",))
    refused(re_escape(ISSUER_DOES_NOT_NARROW.split("{listed}")[1]), parked.pbc_location, stray)


def records_rule(item):
    from tracker.records import rule_to_json

    return rule_to_json(item)


def re_escape(text):
    import re

    return re.escape(text)
