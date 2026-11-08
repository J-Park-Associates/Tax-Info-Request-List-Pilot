"""Tests for tracker/intents.py - the write-ahead intents, and an interrupted move finished from the record.

The promises being tested: every step an intent names stays in its return's
places, in the layout's one wording, and a step outside them - forged into
the record by another machine, a restored copy or a hand edit - moves,
copies and removes nothing, at the gate or where it would be carried out; a
step either of whose ends is reached through a link does nothing; a copy is
proved against a digest or refused where it is carried out, and a row
recorded without its bytes still gets a proved working copy; a removal never
acts in the client tree; the recovery's copy to act on is cut to fit, or
named as no copy at all, and never copies an original from outside the
row's places or behind a link; and a working copy moved into review is
marked for Protected View or not moved.

These tests came from ``tests/test_filer.py`` with the code they drive
(SPEC-architecture-p4 P4.6, P332): each one whose highest home, by section
4.1's rule, is ``tracker/intents.py``, cut and pasted with its name and its
decorators, with ``_elsewhere`` and ``FORGED``, which only they read. The
helpers they share with the filer's tests are ``tests/filer_helpers.py``'s,
``_forge_line`` among them. The section comments they sat under in
``tests/test_filer.py`` (decisions 180 and 187) stay there above the tests
of those sections that stay. Many drive the code through a pass or a
person's action, as they did; the claim each makes is about the code here.
Where a body still imports a name through the filer that the filer imports
back for its own code (``_intend``, ``_do_op``, ``_op``), it reads the very
object defined here.
"""

from dataclasses import replace

import pytest

from tests.builders import (
    DAY1,
    DAY2,
    ITEMS,
    ROOM_ITEMS,
    drop,
    engagement_fixture,
    link_to,
    make_engagement,
    sort,
)
from tests.filer_helpers import (
    _forge_line,
    originals,
    review_dir,
)
from tracker import ledger, store
from tracker.copies import FilingError
from tracker.index import FILED
from tracker.layout import locate, location_of, root_of
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
)

engagement = engagement_fixture(ITEMS)


def test_a_recovery_copy_is_cut_to_fit_and_one_that_cannot_be_made_names_no_copy(
        tmp_path, monkeypatch, path_setting):
    """F1: the recovery's copy to act on is named as every review copy is;
    and where none can be made the row names **no** copy - never the one
    the interrupted step was making, which is not there - and says why in
    a fixed sentence."""
    from tests.builders import root_for_a_return_of
    from tracker import actions, filer, intents
    from tracker.copies import REVIEW_NO_ROOM, NoRoom
    from tracker.layout import path_limit

    engagement = make_engagement(root_for_a_return_of(tmp_path, 180), ROOM_ITEMS)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    [filed] = sort(engagement, today=DAY1).filed
    locate(engagement, filed.prepared_location).unlink()       # the copy the step was making: gone
    long_named = replace(filed, original_name="letter " + "n" * 150 + ".pdf")

    location, said = intents._a_copy_to_act_on(engagement, long_named, None)

    copy = locate(engagement, location)
    assert said == "" and copy.is_file() and copy.parent == review_dir(engagement)
    assert copy.name.startswith("letter nnn") and copy.suffix == ".pdf" and len(str(copy)) == path_limit()

    copy.unlink()
    sentence = REVIEW_NO_ROOM.format(name="w2.pdf", length=270, limit=260, ext=".pdf")

    def no_room(_folder, _name, _root):
        raise NoRoom(270, 260, "pdf", sentence=sentence)

    for module in (filer, intents, actions):
        monkeypatch.setattr(module, "_review_copy_path", no_room)
    assert intents._a_copy_to_act_on(engagement, filed, None) == ("", sentence)


@pytest.mark.parametrize("location, writes, allowed", [
    ("Prepared/A01 - W-2/x.pdf", True, True),                                  # the return itself
    ("../_Opened/mail/x.pdf", True, True),                                     # its year's _Opened
    ("../../2024/_Opened/mail/x.pdf", False, True),                            # another year's, to read
    ("../../2024/_Opened/mail/x.pdf", True, False),                            # never to write
    ("../../../Other Household/2025/_Opened/mail/x.pdf", False, False),        # another household's
    ("../../../../Clients/Test Household/Drop files here/x.pdf", False, True),  # its inbox
    ("../../../../Clients/Test Household/Drop files here/sub/x.pdf", False, True),
    ("../../../../Clients/Test Household/2025/x.pdf", True, True),             # its year folder
    ("../../../../Clients/Other Household/2025/x.pdf", False, True),           # a feed's original
    ("../../../../Clients/Other Household/2025/x.pdf", True, False),           # never written to
    ("../../../../Clients/Test Household/x.pdf", False, False),                # beside the inbox
    ("../1040 - Someone Else/Prepared/x.pdf", False, False),                    # another return
    ("../../_ledger.jsonl", True, False),                                      # the household's record
    ("../../../../../outside/secret.pdf", False, False),                       # above the root
    ("/etc/passwd", False, False),
    ("C:/Windows/win.ini", False, False),
    ("C:x.pdf", False, False),
    ("\\\\host\\share\\x.pdf", False, False),
    ("", False, False),
])
def test_a_step_may_touch_only_its_returns_places(engagement, location, writes, allowed):
    from tracker.intents import _may_touch

    assert _may_touch(engagement, location, writes=writes) is allowed


def test_the_filer_asks_the_layout_where_a_step_may_act(engagement, monkeypatch):
    """Decision 187: the place rule has one wording, the layout's. The
    filer holds none of its own - change the layout's answer and the
    filer's changes with it."""
    import tracker.intents as intents

    asked = []

    def answer(return_dir, location, *, writes):
        asked.append((return_dir, location, writes))
        return "not-a-place"

    monkeypatch.setattr(intents, "place_problem", answer)
    assert intents._may_touch(engagement, "Prepared/x.pdf", writes=True) is False
    assert asked == [(engagement, "Prepared/x.pdf", True)]


def test_a_step_outside_its_places_moves_copies_and_removes_nothing(engagement, tmp_path):
    """The integrity review's exp6: a ``moving`` line appended to a journal
    by hand, by another machine or from a restored copy made the next
    recovery copy a file from outside the clients root into the client's
    year folder, and move another household's original away. Every step is
    now held to its return's places before anything is looked at, in the
    recovery and in the one function every step goes through."""
    from tracker.intents import OP_OUTSIDE, _do_op, _finish_the_ops
    from tracker.validators import sha256_of

    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.pdf"
    secret.write_bytes(b"%PDF-1.4 not the client's")
    digest = sha256_of(secret)
    escape = location_of(engagement, secret)
    assert escape.startswith("../")
    forged = [
        {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: escape,
         ledger.TO_KEY: "../../../../Clients/Test Household/2025/secret.pdf", ledger.DIGEST_KEY: digest},
        {ledger.OP_KEY: ledger.OP_MOVE, ledger.FROM_KEY: escape,
         ledger.TO_KEY: "Prepared/secret.pdf", ledger.DIGEST_KEY: digest},
        {ledger.OP_KEY: ledger.OP_REMOVE, ledger.FROM_KEY: escape, ledger.DIGEST_KEY: digest},
    ]
    before = sorted(p for p in tmp_path.rglob("*"))
    for op in forged:
        with pytest.raises(FilingError) as refused:
            _do_op(engagement, op)
        assert refused.value.args[0] == OP_OUTSIDE.format(name=engagement.name, location=escape,
                                                           reason="not-a-place")
        with pytest.raises(FilingError):
            _finish_the_ops(engagement, [op], None)
    assert sorted(p for p in tmp_path.rglob("*")) == before
    assert secret.read_bytes() == b"%PDF-1.4 not the client's"


def test_a_recovery_never_copies_an_original_the_row_names_outside_its_places(engagement, tmp_path):
    """The cloud branch's own review of decision 180: the recovery's copy to act on read the
    row's own original, not a step, so an intent whose row named a file
    outside the clients root had that file copied into Needs Review. The
    row's original is held to the same places as a step's source."""
    from tracker.intents import _intend
    from tracker.locking import engagement_lock
    from tracker.records import IndexEntry, entry_to_json, ledger_key
    from tracker.validators import sha256_of

    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.pdf"
    secret.write_bytes(b"%PDF-1.4 not the client's")
    digest = sha256_of(secret)
    row = IndexEntry(received="2026-07-01", original_name="secret.pdf", size_kb=0.1, digest=digest,
                     identifier="A01", prepared_location="Prepared/A01/W-2.pdf",
                     pbc_location=location_of(engagement, secret), decision=FILED, reason="filed")
    lost = [{ledger.OP_KEY: ledger.OP_COPY,
             ledger.FROM_KEY: "../../../../Clients/Test Household/2025/nothing.pdf",
             ledger.TO_KEY: row.prepared_location, ledger.DIGEST_KEY: digest}]
    # Since decision 187 the store refuses to record such a row at all, so
    # the line is forged into the journal as a restored copy would be - and
    # the gate refuses it before the recovery reads a word of it.
    journal = ledger.path_for(engagement)
    honest = journal.read_bytes()
    with engagement_lock(engagement):
        with pytest.raises(store.StoreError, match="outside this return's places"):
            _intend(engagement, ledger_key(row), lost, by=ledger.BY_PASS, row=entry_to_json(row),
                    then=ledger.PARKED)
        assert journal.read_bytes() == honest
    # Forged as another machine's line (decision 159): one appended here,
    # past the store, would be refused first as a line claiming this
    # machine that this machine did not write.
    _forge_line(engagement, ledger.new(ledger.MOVING, **{
        ledger.KEY_KEY: ledger_key(row), ledger.OPS_KEY: lost, ledger.DECIDED_BY_KEY: ledger.BY_PASS,
        ledger.ROW_KEY: entry_to_json(row), ledger.EVENT_KEY_AFTER: ledger.PARKED}))

    with pytest.raises(store.StoreError, match="outside this return's places"):
        sort(engagement, today=DAY2)

    copies = [path for path in (engagement / "Prepared").rglob("*") if path.is_file()]
    assert not any(path.read_bytes() == secret.read_bytes() for path in copies)
    # The recovery's own check stands behind the gate: handed the row
    # directly, it still copies nothing from outside the return's places.
    from tracker.intents import _a_copy_to_act_on
    assert _a_copy_to_act_on(engagement, row, None)[0] == ""
    journal.write_bytes(honest)


def _elsewhere(tmp_path, name="elsewhere"):
    """A folder a junction may point at, holding one file of its own."""
    folder = tmp_path.parent / f"{tmp_path.name}-{name}"
    folder.mkdir()
    (folder / "x.pdf").write_bytes(b"%PDF-1.4 somebody else's file")
    return folder


FORGED = ["absolute", "climb", "link", "removal-behind-a-link", "removal-of-an-original"]


@pytest.mark.parametrize("which", FORGED)
def test_a_forged_step_is_carried_out_nowhere(engagement, tmp_path, which):
    """The ruling's first proof, one forged ``moving`` line per step, every
    digest right (the review's S5): a copy from an absolute path, a move
    whose ``to`` climbs into another household's inbox, a copy out of the
    return's own Prepared folder reached through a link, a removal behind
    that link (M3) and a removal of the client's own original (M4). The
    pass refuses each - at the gate, or where the recovery would carry it
    out - and nothing on disk changes; handed straight to the one function
    every step goes through, each is refused too."""
    from tracker.copies import MovedThroughALinkError
    from tracker.intents import OP_OUTSIDE, _do_op
    from tracker.layout import CLIENTS_TREE, INBOX_DIR_NAME
    from tracker.registry import discover_engagements
    from tracker.runner import run_registry
    from tracker.status_page import RECORD_UNREADABLE
    from tracker.validators import sha256_of

    secret = _elsewhere(tmp_path, "outside") / "x.pdf"
    original = originals(engagement) / "w2.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"%PDF-1.4 the client's W-2")
    behind = _elsewhere(tmp_path)
    link_to(behind, engagement / PREPARED_DIR_NAME / "linked")
    other_inbox = root_of(engagement) / CLIENTS_TREE / "Other Household" / INBOX_DIR_NAME
    climbing = location_of(engagement, other_inbox / "w2.pdf")
    step, refusal = {
        "absolute": ({ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: secret.as_posix(),
                      ledger.TO_KEY: f"{PREPARED_DIR_NAME}/secret.pdf", ledger.DIGEST_KEY: sha256_of(secret)},
                     OP_OUTSIDE.format(name=engagement.name, location=secret.as_posix(), reason="absolute")),
        "climb": ({ledger.OP_KEY: ledger.OP_MOVE, ledger.FROM_KEY: location_of(engagement, original),
                   ledger.TO_KEY: climbing, ledger.DIGEST_KEY: sha256_of(original)},
                  OP_OUTSIDE.format(name=engagement.name, location=climbing, reason="other-household")),
        "link": ({ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: f"{PREPARED_DIR_NAME}/linked/x.pdf",
                  ledger.TO_KEY: location_of(engagement, originals(engagement) / "x.pdf"),
                  ledger.DIGEST_KEY: sha256_of(behind / "x.pdf")}, MovedThroughALinkError),
        "removal-behind-a-link": ({ledger.OP_KEY: ledger.OP_REMOVE,
                                   ledger.FROM_KEY: f"{PREPARED_DIR_NAME}/linked/x.pdf",
                                   ledger.DIGEST_KEY: sha256_of(behind / "x.pdf")}, MovedThroughALinkError),
        "removal-of-an-original": ({ledger.OP_KEY: ledger.OP_REMOVE,
                                    ledger.FROM_KEY: location_of(engagement, original),
                                    ledger.DIGEST_KEY: sha256_of(original)},
                                   OP_OUTSIDE.format(name=engagement.name,
                                                     location=location_of(engagement, original),
                                                     reason="client-tree")),
    }[which]
    from tracker.pass_order import PASS_ORDER_FILENAME

    def _tree() -> list:
        # The pass's own order hint (decision 189) is its bookkeeping, not a step.
        return sorted(p for p in tmp_path.rglob("*") if p.name != PASS_ORDER_FILENAME)

    before = _tree()
    honest = _forge_line(engagement, ledger.new(ledger.MOVING, **{
        ledger.KEY_KEY: "forged", ledger.OPS_KEY: [step], ledger.DECIDED_BY_KEY: ledger.BY_PASS}))

    report = run_registry(discover_engagements(tmp_path), today=DAY1)

    (run,) = [one for one in report.runs if one.engagement.path == engagement]
    if isinstance(refusal, str):                     # refused at the gate, by the place rule
        assert run.error.startswith(RECORD_UNREADABLE.split("{")[0])
        assert "outside this return's places" in run.error
    else:                                            # admitted, and refused where it is carried out
        # Since decision 189 a run's error is said as its class (principle 7).
        assert run.error == MovedThroughALinkError.__name__
    ledger.path_for(engagement).write_bytes(honest)
    assert _tree() == before
    assert (behind / "x.pdf").is_file() and original.is_file()

    if isinstance(refusal, str):
        with pytest.raises(FilingError) as refused:
            _do_op(engagement, step)
        assert refused.value.args[0] == refusal
    else:
        with pytest.raises(refusal):
            _do_op(engagement, step)
    assert _tree() == before
    assert original.read_bytes() == b"%PDF-1.4 the client's W-2"


def test_a_copy_through_a_link_copies_nothing(engagement, tmp_path):
    """B-11: a copy followed a junction at either end. Its source behind a
    link, or its target folder behind one, and nothing is read or written."""
    from tracker.copies import MovedThroughALinkError
    from tracker.intents import _do_op
    from tracker.validators import sha256_of

    behind = _elsewhere(tmp_path)
    link_to(behind, engagement / PREPARED_DIR_NAME / "linked")
    original = originals(engagement) / "w2.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"%PDF-1.4 the client's W-2")
    reading = {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: f"{PREPARED_DIR_NAME}/linked/x.pdf",
               ledger.TO_KEY: f"{PREPARED_DIR_NAME}/copy.pdf", ledger.DIGEST_KEY: sha256_of(behind / "x.pdf")}
    writing = {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: location_of(engagement, original),
               ledger.TO_KEY: f"{PREPARED_DIR_NAME}/linked/sub/w2.pdf", ledger.DIGEST_KEY: sha256_of(original)}

    for op in (reading, writing):
        with pytest.raises(MovedThroughALinkError, match="nothing was moved, copied or removed"):
            _do_op(engagement, op)

    assert not (engagement / PREPARED_DIR_NAME / "copy.pdf").exists()
    assert sorted(p.name for p in behind.iterdir()) == ["x.pdf"]      # no folder made behind it


def test_a_removal_through_a_link_removes_nothing(engagement, tmp_path):
    from tracker.copies import MovedThroughALinkError
    from tracker.intents import _do_op
    from tracker.validators import sha256_of

    behind = _elsewhere(tmp_path)
    link_to(behind, engagement / PREPARED_DIR_NAME / "linked")
    removal = {ledger.OP_KEY: ledger.OP_REMOVE, ledger.FROM_KEY: f"{PREPARED_DIR_NAME}/linked/x.pdf",
               ledger.DIGEST_KEY: sha256_of(behind / "x.pdf")}

    with pytest.raises(MovedThroughALinkError):
        _do_op(engagement, removal)

    assert (behind / "x.pdf").is_file()


def test_a_move_into_a_linked_folder_moves_nothing(engagement, tmp_path):
    """B-11: a lexical rule cannot see a junction, so a year folder swapped
    for one would have the rename land wherever it points. The target's
    folders are asked before any is made."""
    from tracker.copies import MovedThroughALinkError
    from tracker.intents import _do_op
    from tracker.validators import sha256_of

    original = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    behind = _elsewhere(tmp_path)
    originals(engagement).rmdir()                     # the year's folder, swapped for a junction
    link_to(behind, originals(engagement))
    for target in (originals(engagement) / "w2.pdf", originals(engagement) / "new" / "w2.pdf"):
        move = {ledger.OP_KEY: ledger.OP_MOVE, ledger.FROM_KEY: location_of(engagement, original),
                ledger.TO_KEY: location_of(engagement, target), ledger.DIGEST_KEY: sha256_of(original)}
        with pytest.raises(MovedThroughALinkError):
            _do_op(engagement, move)

    assert original.is_file()
    assert sorted(p.name for p in behind.iterdir()) == ["x.pdf"]
    originals(engagement).unlink()
    originals(engagement).mkdir()


def test_a_recovery_copies_no_original_behind_a_link(engagement, tmp_path):
    """A-7: the recovery's copy to act on read the row's original with no
    link check, so a year folder swapped for a junction had whatever it
    pointed at copied into Needs Review. The row's original is held to the
    link check as a step's source is."""
    from tracker.copies import MOVE_THROUGH_A_LINK
    from tracker.intents import _a_copy_to_act_on
    from tracker.records import IndexEntry
    from tracker.validators import sha256_of

    behind = _elsewhere(tmp_path)
    originals(engagement).rmdir()                     # the year's folder, swapped for a junction
    link_to(behind, originals(engagement))
    row = IndexEntry(received="2026-07-01", original_name="x.pdf", size_kb=0.1,
                     digest=sha256_of(behind / "x.pdf"), identifier="A01",
                     prepared_location=f"{PREPARED_DIR_NAME}/A01 - W-2.pdf",
                     pbc_location=location_of(engagement, originals(engagement) / "x.pdf"),
                     decision=FILED, reason="filed")

    location, said = _a_copy_to_act_on(engagement, row, None)

    assert location == ""
    assert said == MOVE_THROUGH_A_LINK.format(name="x.pdf", within=root_of(engagement))
    review = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    assert not review.exists() or not any(review.iterdir())
    originals(engagement).unlink()
    originals(engagement).mkdir()


def test_an_open_copy_with_no_digest_is_refused_where_it_is_carried_out(engagement):
    """A copy with nothing to prove it against could be anything the line
    pointed at, so it is refused before a folder is made - by the one
    function every step goes through, and by the copy itself."""
    from tracker.copies import COPY_UNPROVED, _copy_whole
    from tracker.intents import _do_op

    original = originals(engagement) / "w2.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"%PDF-1.4 the client's W-2")
    target = engagement / PREPARED_DIR_NAME / "new" / "w2.pdf"
    copy = {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: location_of(engagement, original),
            ledger.TO_KEY: location_of(engagement, target), ledger.DIGEST_KEY: ""}

    with pytest.raises(FilingError) as refused:
        _do_op(engagement, copy)
    assert refused.value.args[0] == COPY_UNPROVED.format(source="w2.pdf", target="w2.pdf")
    with pytest.raises(FilingError):
        _copy_whole(original, target, expect="", root=engagement.parents[3])
    assert not target.parent.exists()


def test_a_row_recorded_without_its_bytes_still_gets_a_proved_working_copy(engagement):
    """Decision 65's row has no digest, and its copy is still proved: the
    intent takes the fingerprint from the step that brings the original in,
    or from the original itself - and an intent with neither is never
    written."""
    from tracker.copies import COPY_UNPROVED
    from tracker.intents import _do_op, _intend
    from tracker.locking import engagement_lock
    from tracker.validators import sha256_of

    dropped = drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    digest = sha256_of(dropped)
    original = originals(engagement) / "w2.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    working = engagement / PREPARED_DIR_NAME / "A01 - W-2.pdf"
    ops = [
        {ledger.OP_KEY: ledger.OP_MOVE, ledger.FROM_KEY: location_of(engagement, dropped),
         ledger.TO_KEY: location_of(engagement, original), ledger.DIGEST_KEY: ""},
        {ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: location_of(engagement, original),
         ledger.TO_KEY: location_of(engagement, working), ledger.DIGEST_KEY: ""},
    ]
    lines = len(ledger.read_events(engagement))

    with engagement_lock(engagement):
        _intend(engagement, location_of(engagement, original), ops, by=ledger.BY_PASS)
        (intent,) = ledger.replay(ledger.read_events(engagement)).intents.values()
        assert [op[ledger.DIGEST_KEY] for op in intent[ledger.OPS_KEY]] == ["", digest]
        for op in ops:
            _do_op(engagement, op)
        assert sha256_of(working) == digest
        ledger.append(engagement, ledger.new(ledger.MOVE_ABANDONED, key=location_of(engagement, original)))

        nowhere = [{ledger.OP_KEY: ledger.OP_COPY, ledger.FROM_KEY: f"{PREPARED_DIR_NAME}/gone.pdf",
                    ledger.TO_KEY: f"{PREPARED_DIR_NAME}/copy.pdf", ledger.DIGEST_KEY: ""}]
        with pytest.raises(FilingError) as refused:
            _intend(engagement, "gone", nowhere, by=ledger.BY_PASS)
    assert refused.value.args[0] == COPY_UNPROVED.format(source="gone.pdf", target="copy.pdf")
    assert len(ledger.read_events(engagement)) == lines + 2


def test_a_recovery_removes_nothing_behind_a_link(engagement, tmp_path):
    """The review's M3: the recovery carries a removal out itself, not
    through _do_op, so it asks the link check of every step before it reads
    or removes a byte."""
    from tracker.copies import MovedThroughALinkError
    from tracker.intents import _finish_the_ops
    from tracker.validators import sha256_of

    behind = _elsewhere(tmp_path)
    link_to(behind, engagement / PREPARED_DIR_NAME / "linked")
    removal = {ledger.OP_KEY: ledger.OP_REMOVE, ledger.FROM_KEY: f"{PREPARED_DIR_NAME}/linked/x.pdf",
               ledger.DIGEST_KEY: sha256_of(behind / "x.pdf")}

    with pytest.raises(MovedThroughALinkError):
        _finish_the_ops(engagement, [removal], None)

    assert (behind / "x.pdf").is_file()


def test_a_removal_never_acts_in_the_client_tree(engagement):
    """The review's M4: every removal the tracker writes takes away one of
    the firm's own copies, so one naming a client's original - even in this
    return's own household and year - is refused before it is recorded."""
    from tracker.intents import OP_OUTSIDE, _intend
    from tracker.locking import engagement_lock
    from tracker.validators import sha256_of

    original = originals(engagement) / "w2.pdf"
    original.write_bytes(b"%PDF-1.4 the client's W-2")
    location = location_of(engagement, original)
    removal = {ledger.OP_KEY: ledger.OP_REMOVE, ledger.FROM_KEY: location,
               ledger.DIGEST_KEY: sha256_of(original)}
    lines = len(ledger.read_events(engagement))

    with engagement_lock(engagement), pytest.raises(FilingError) as refused:
        _intend(engagement, location, [removal], by=ledger.BY_PASS)

    assert refused.value.args[0] == OP_OUTSIDE.format(name=engagement.name, location=location,
                                                      reason="client-tree")
    assert len(ledger.read_events(engagement)) == lines and original.is_file()


@pytest.mark.parametrize("refuse", [False, True], ids=["marked", "refused"])
def test_a_macro_working_copy_moved_into_review_is_marked_or_not_moved(engagement, monkeypatch, refuse):
    """The review's S2: a working copy moved into review - a person's
    unfiling, a refused put-back - goes through the one marking path, like
    a copy made there: marked before the rename, and a mark refused moves
    nothing (fail closed)."""
    import tracker.copies as copies_module
    from tracker.copies import MarkRefusedError
    from tracker.intents import _do_op, _op

    marked = []

    def mark(path):
        if refuse:
            raise OSError(95, "Operation not supported", str(path))
        marked.append(path.name)
        return True

    monkeypatch.setattr(copies_module, "mark_from_internet", mark)
    working = engagement / PREPARED_DIR_NAME / "A01 - W-2 Wage Statements.xlsm"
    working.parent.mkdir(parents=True, exist_ok=True)
    working.write_bytes(b"PK a workbook with macros")
    parked = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME / "budget.xlsm"
    move = _op(engagement, ledger.OP_MOVE, working, parked, "")

    if refuse:
        with pytest.raises(MarkRefusedError):
            _do_op(engagement, move)
        assert working.exists() and not parked.exists()
    else:
        _do_op(engagement, move)
        assert marked == [working.name] and parked.exists() and not working.exists()
