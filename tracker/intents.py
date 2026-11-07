"""Write down what a decision is about to do, carry it out, record it, and
finish it after a crash.

Every decision that moves or copies a file - a pass's copy, a person's
filing, unfiling or put-back, a hand-over's release - passes through here,
in four parts, each upholding the decision rows it names:

- **The write-ahead intent** (decisions 119, 132 and 187). :func:`_intend`
  writes the operations down before the first one is made, keyed by the
  row's own identity, with the row the decision will record, the event
  that will complete it and who decided; :func:`_prove` gives every copy in
  it the fingerprint it will be proved against, or refuses it before
  anything is recorded. :func:`_do_op` is the one place a plan is carried
  out, by the decision and by the recovery alike. :func:`_abandon` says a
  move the record refused is not to be finished forward;
  :func:`_carry_out_a_persons_ops` abandons a person's intent whose first
  step's mark is refused (decision 190); and
  :func:`_refuse_if_a_move_is_open` refuses a person's action while a run
  that was interrupted here has a move still open.
- **The places a step may touch** (decisions 180, 187 and 188).
  :func:`_may_touch` and :func:`_refuse_a_step_outside` hold every step to
  its return's places in the layout's one wording (:data:`OP_OUTSIDE`);
  :func:`_refuse_a_step_through_a_link` refuses a step either of whose ends
  is reached through a link below the clients root; :func:`_door_for` asks
  the one door into the client tree before a folder is made there; and
  :func:`_mark_a_move_into_review` marks a working copy moved into review
  for Protected View, or moves nothing (decision 190).
- **The record's one write** (decisions 87 and 102). :func:`_record` writes
  what the index now says and the record does not, in one call and one
  transaction; :func:`_rows_changed` reads the events off the rows by one
  rule, :func:`_ledger_event` composes each row's event by its decision
  (:data:`_LEDGER_EVENT_FOR`), and :func:`_the_record_holds` answers the
  rollback's one question.
- **Finishing an interrupted move** (decision 119).
  :func:`_finish_interrupted_moves` runs at the start of every pass:
  :func:`_finish_the_ops` checks each step by bytes and makes only what the
  record decided, :func:`_a_copy_to_act_on` finds or makes the copy a
  person acts on where a step cannot be finished, and :func:`_the_trouble`
  says why. :class:`FileError` is what it hands back - one drop the run
  could not deal with - and the filer's report carries it.

**An interrupted move is finished from the record, never guessed**
(decision 119). Before the first file operation of any decision - a
pass's copy, a person's filing, unfiling or put-back - what it is about
to do is written down: the operations in order with the bytes each
expects, the row it will record, the event that will complete it and who
decided. A run killed in between is finished at the start of the next
pass (:func:`_finish_interrupted_moves`), by bytes, before anything else
looks - and the row is recorded as the intent said, a person's as theirs
and dated their day. **The fingerprint identifies; the record decides:**
where a destination holds a different file nothing there is touched, the
row parks and says so; where the bytes are at neither end the row parks
and says that. A person's action refuses while a move is open here, and
the next pass - or Run now - clears it.

**Why it is its own module** (SPEC-architecture-p4 P4.6, P332; the
architecture audit's A-1, step 3). This code sat in the filer, and the pass
and a person's actions share it (decision 119): both write an intent, carry
it out through :func:`_do_op` and record it through :func:`_record`, and a
person's actions left the filer for :mod:`tracker.actions` in P4.9 (P335),
so what they share sits below both. Nothing here routes or decides where a document
goes: every function carries out, records or finishes a decision its caller
made, and none of it reads a name the filer defines. The record's write
came with the intents because :func:`_finish_interrupted_moves` and the
hand-over both compose through :func:`_ledger_event`, and
:mod:`tracker.index` composes nothing (P319). ``OPENED``, a decision word
:data:`_LEDGER_EVENT_FOR` and the filer both read, went down to the index
beside ``FILED`` and the others.

**It composes the record's events** (P327). The intent
(``ledger.MOVING``), the abandon (``ledger.MOVE_ABANDONED``), the finish of
an interrupted move and each row's event are calls of ``ledger.new`` here,
so it is one of the record's writers, named in ``tests/test_layers.py``'s
``COMPOSERS`` beside the filer.

**It upholds "Originals are never altered"** beside the filer and
:mod:`tracker.copies`: an original's move is intended, done and proved
here, and a destination that holds somebody else's bytes is never touched.

**Why it sits at layer 3.** It reads :mod:`tracker.copies` and
:class:`tracker.content_check.ContentCache` (layer 2: the cache is handed
down the copy path), the record types, the index, the store, the journal,
the scaffold's folder names and the validators (layer 1), and the layout,
the door, the disk writes, the reasons and the errors (layer 0). It may
import nothing above layer 2 and nothing of the filer, at load time or at
call time: the filer imports it, and so do a person's actions. Layer 2
would pass the layer test too; layer 3 keeps it beside the filer and the
actions it serves, and keeps layer 2 to what a reading or a routing needs
(SPEC-architecture-p4 section 2.1).

**Every reader asks this module.** The filer imports back from here only
what its own remaining code reads, and offers none of it on, and a person's
actions import only what theirs reads. A stand-in follows the name's readers
(the audit's A-4): one for a name this module reads as a global is set on
this module, and where the filer or a person's actions read it too, on them
as well.

**One private name of the index crosses into it**: the index's
``_without_moved_sentence``, which :func:`_finish_interrupted_moves` asks
when it parks a row, as the filer does (P319's one exception;
``tests/test_index.py`` pins the crossing over the filer's family).

**Why it logs as ``tracker.filer``** (SPEC-architecture-p4 section 2.1).
The run log and the error log print each line's logger name, so a name of
this module's own would change the lines a person and the office read. It
is the same logger object as the filer's, so no handler and no test sees a
difference.

The comments and docstrings below came with the code, word for word. Where
one names the pass, a person's action or a function of the filer's, that is
the caller it describes; the code it describes is here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from tracker import door, errors, ledger, reasons, store
from tracker.content_check import ContentCache
from tracker.copies import (
    COPY_UNPROVED,
    COPY_UNREAD,
    FIRM_WRITTEN,
    MOVE_THROUGH_A_LINK,
    REVIEW_COPY_FAILED,
    FilingError,
    MarkRefusedError,
    MovedThroughALinkError,
    NoRoom,
    _copy_whole,
    _digest_or_none,
    _existing_copy,
    _here,
    _mark_for_review,
    _may_carry_code,
    _move_whole,
    _review_copy_path,
    _shown,
)
from tracker.door import through_a_link
from tracker.fsio import is_link

# The index's words and its readers live in tracker/index.py (P319). One
# private name crosses here, as it does into the filer: _without_moved_sentence,
# which finishing an interrupted move asks when it parks a row.
from tracker.index import (
    DUPLICATE,
    FILE_MOVED,
    FILED,
    INTERRUPTED_MOVE_DETAIL,
    NEEDS_REVIEW,
    NOT_REQUESTED,
    OPENED,
    _without_moved_sentence,
    prepared_location,
    read_index,
)
from tracker.layout import (
    CLIENT_KINDS,
    household_name_of,
    locate,
    location_of,
    place_of,
    place_problem,
    recorded_name,
    room_root,
    root_of,
)
from tracker.records import (
    IndexEntry,
    entry_from_json,
    entry_to_json,
    ledger_key,
)
from tracker.scaffold import PREPARED_DIR_NAME, REVIEW_DIR_NAME
from tracker.validators import is_cloud_placeholder, sha256_of

# The filer's logger, by its name (SPEC-architecture-p4 section 2.1): the run
# log and the error log print each line's logger name, so a name of this
# module's own would change the lines a person and the office read. It is the
# same logger object, so no handler and no test sees a difference.
log = logging.getLogger("tracker.filer")


@dataclass(frozen=True, slots=True)
class FileError:
    """One drop the run could not deal with, and what became of it."""

    name: str
    error: str
    left_in_place: bool   # True: untouched in the inbox, retried next run


# ------------------------------------------------------------------ record ----


#: Which event a row's decision is recorded as, when a pass reaches it. The
#: decisions a person makes are recorded under their own names, at the call
#: that makes them, so the record says who decided and not only what.
_LEDGER_EVENT_FOR = {
    FILED: ledger.FILED,
    NEEDS_REVIEW: ledger.PARKED,
    DUPLICATE: ledger.DUPLICATE,
    NOT_REQUESTED: ledger.PARKED,
    FILE_MOVED: ledger.COPY_MOVED,
    OPENED: ledger.OPENED,
}


def _ledger_event(name: str, entry: IndexEntry, *, was: str = "") -> dict:
    event = ledger.new(name, **{ledger.KEY_KEY: ledger_key(entry), ledger.ROW_KEY: entry_to_json(entry)})
    if was and was != event[ledger.KEY_KEY]:
        event[ledger.WAS_KEY] = was
    return event


def _rows_changed(
    before: dict[str, dict],
    entries: list[IndexEntry],
    moved: dict[str, str],
    decided: dict[str, str],
    extra: dict[str, dict] | None = None,
) -> list[dict]:
    """One event per row the index now holds that ``before`` does not already say.

    Read off the rows themselves rather than collected as the caller goes,
    so every road a row travels - a drop sorted, bytes recorded on a row
    preserved without them, a row that followed an original the client moved,
    a row a person rewrote - is recorded by the one rule and none of them can
    be forgotten by a later edit somewhere else.

    ``moved`` maps a row's new identity to the one it is leaving; ``decided``
    names the event for the row this call decided itself, so a person's
    decision is recorded as theirs and not as the decision it happens to
    write. ``extra`` is what an event carries beside its row, by the row's
    key: what an opened email or zip held (decision 143), which the journal
    keeps and the fold does not.
    """
    events = []
    for entry in entries:
        key = ledger_key(entry)
        was = moved.get(key, "")
        row = entry_to_json(entry)
        earlier = before.get(was or key)
        if earlier == row:
            continue
        if key in decided:
            name = decided[key]
        elif was:
            name = ledger.PRESERVED          # the original is elsewhere; the row followed it
        elif earlier is not None and not earlier["digest"] and row["digest"]:
            name = ledger.BYTES_RECORDED
        else:
            name = _LEDGER_EVENT_FOR.get(entry.decision, ledger.PARKED)
        event = _ledger_event(name, entry, was=was)
        # What an opened email or zip held travels on its own line, beside
        # the row (decision 143): the journal keeps it, the fold does not.
        event.update((extra or {}).get(key, {}))
        events.append(event)
    return events


def _record(
    engagement_dir: Path,
    before: dict[str, dict],
    entries: list[IndexEntry],
    *,
    moved: dict[str, str] | None = None,
    decided: dict[str, str] | None = None,
    also: list[dict] | None = None,
    extra: dict[str, dict] | None = None,
) -> None:
    """Write what the index now says and the record does not - in one call.

    **One decision, one call, one transaction.**
    :func:`tracker.store.record` appends every event to the journal, under
    the lock this caller already holds, and then folds them all into the
    store inside a single immediate transaction: either the whole of what
    this call decided is recorded or none of it is. There is no second
    copy to keep in step and nothing to defer (decision 102).

    ``before`` is the engagement's rows as this call found them, which is
    the store's own answer, because that is what :func:`read_index` gave
    the caller. A call that changed nothing writes nothing at all.

    ``also`` is for the events a decision produces that are not index
    rows - today the one keyword a person's filing teaches a request
    (decision 103). They go in this call, not a call of their own,
    because the filing and what it taught are one decision and the
    rollback that puts a moved file back asks exactly that question.
    """
    events = _rows_changed(before, entries, moved or {}, decided or {}, extra) + list(also or [])
    if events:
        store.record(store.connect(), engagement_dir, *events)


# ------------------------------------------------------------------ intent ----

#: What a person is told while a run that was interrupted here has a move
#: still open. The next pass finishes it from the record, and the app's own
#: Run now is a pass, so the remedy is one click and needs no explaining of
#: what a half-made move is.
OPEN_INTENT_REFUSAL = ("a run was interrupted here; the next pass finishes it first "
                       "(or press Run now)")


def _op(engagement_dir: Path, kind: str, source: Path,
        target: Path | None = None, digest: str = "") -> ledger.IntentOp:
    """One file operation of a decision, as the record carries it.

    Paths relative to the engagement folder and POSIX, as every path the
    record holds is, so an intent written on one machine reads on another;
    the digest is what the bytes are expected to be at both ends, which is
    the whole of how a recovery tells a step that happened from one that
    did not.
    """
    op: ledger.IntentOp = {ledger.OP_KEY: kind, ledger.FROM_KEY: location_of(engagement_dir, source),
                           ledger.DIGEST_KEY: digest}
    if target is not None:
        op[ledger.TO_KEY] = location_of(engagement_dir, target)
    return op


#: What an operation naming a place outside its return's own is refused
#: with (decision 180).
OP_OUTSIDE = ("the record of {name} names {location} for a step ({reason}), which is outside the places "
              "a step of this return may touch; nothing was moved, copied or removed. "
              "A person checks the record")


def _may_touch(engagement_dir: Path, location: str, *, writes: bool) -> bool:
    """Whether a location an operation names lands where a step of this
    return may act (decision 180): the layout's rule, worded once in
    :func:`tracker.layout.place_problem` (decision 187)."""
    return place_problem(engagement_dir, location, writes=writes) is None


def _refuse_a_step_outside(engagement_dir: Path, op: ledger.IntentOp) -> None:
    """:data:`OP_OUTSIDE` for the first place in ``op`` a step of this
    return may not touch, before any of it is done."""
    removes = op.get(ledger.OP_KEY) == ledger.OP_REMOVE
    for location, write in ledger.op_ends(op):
        code = place_problem(engagement_dir, location, writes=write, removes=removes)
        if code is not None:
            raise FilingError(OP_OUTSIDE.format(name=Path(engagement_dir).name, location=_shown(location),
                                                reason=code))


def _refuse_a_step_through_a_link(engagement_dir: Path, op: ledger.IntentOp) -> None:
    """:class:`MovedThroughALinkError` for a step either of whose ends is
    reached through a link below the clients root (decision 187, B-11).

    A source that is itself a link is refused, and so is any folder between
    the root and either end - including folders a copy or a move would
    still make, which are not there and so are not links - so a junction
    swapped in for a year folder or a return's ``Prepared`` has nothing
    read through it, written through it or made behind it. Asked before
    any ``mkdir``, which would otherwise follow the junction.
    """
    root = root_of(engagement_dir)
    for location, writes in ledger.op_ends(op):
        path = locate(engagement_dir, location)
        if (not writes and is_link(path)) or through_a_link(path.parent, root):
            raise MovedThroughALinkError(MOVE_THROUGH_A_LINK.format(name=path.name, within=root))


def _door_for(root: Path, household: str, target: Path) -> None:
    """Ask the one door into the client tree (``door.client_write``,
    decision 188) for ``target`` and every folder a write there would make
    above it, before anything is made; a :class:`FilingError` with its
    sentence when it refuses. A destination in the firm's tree is not the
    door's to ask: the place rule and the link check already confined it."""
    if place_of(root, target).kind not in CLIENT_KINDS:
        return
    for folder in (*reversed(target.parents), target):
        if place_of(root, folder).kind in CLIENT_KINDS and (folder == target or not folder.exists()):
            try:
                door.client_write(root, household, folder)
            except door.DoorError as exc:
                raise FilingError(str(exc)) from None


def _mark_a_move_into_review(engagement_dir: Path, op: ledger.IntentOp) -> None:
    """Mark the working copy a move is carrying into review, or raise
    :class:`MarkRefusedError` (decision 190's review, S2).

    A working copy moved into review - a person's unfiling, a refused
    put-back - is marked like a copy made there, where it stands, before
    the rename: it is the firm's working copy, never an original, and a
    mark refused moves nothing. Asked twice for a person's move: by
    :func:`_intend`, before the move is written down, so a refused mark is
    a decision that records nothing (the re-check's M-N1) - and by
    :func:`_do_op`, which carries the move out, so a recovery that finishes
    an older intent marks it too. A second mark is the same mark.
    """
    if op[ledger.OP_KEY] != ledger.OP_MOVE:
        return
    source = locate(engagement_dir, op[ledger.FROM_KEY])
    target = locate(engagement_dir, op[ledger.TO_KEY])
    if target.parent.name == REVIEW_DIR_NAME and source.is_file() and _may_carry_code(source):
        _mark_for_review(source, name=target.name)


def _do_op(engagement_dir: Path, op: ledger.IntentOp, *, cache: ContentCache | None = None) -> None:
    """Carry out one operation of an intent.

    The one place the plan an intent wrote down and the work it stands for
    meet: the pass and the person's actions hand their operations here, and
    so does the recovery that finishes them, so a move a recovery makes is
    the move the decision would have made and not a second implementation
    of it. A copy is proved against the digest the intent recorded
    (decision 109); a move is a rename and nothing else (the caller has
    checked the destination by bytes).

    **Confined again where it is carried out** (decision 187). The place
    rule is lexical and cannot see a junction, so before any folder is made
    each end of the step is asked whether it is reached through a link
    below the clients root (:func:`_refuse_a_step_through_a_link`), and a
    copy with no fingerprint is refused (:data:`COPY_UNPROVED`): every
    caller already reads either refusal as "left in place".
    """
    _refuse_a_step_outside(engagement_dir, op)
    _refuse_a_step_through_a_link(engagement_dir, op)
    kind = op[ledger.OP_KEY]
    source = locate(engagement_dir, op[ledger.FROM_KEY])
    if kind == ledger.OP_REMOVE:
        source.unlink(missing_ok=True)
        return
    target = locate(engagement_dir, op[ledger.TO_KEY])
    if kind == ledger.OP_COPY and not op.get(ledger.DIGEST_KEY):
        raise FilingError(COPY_UNPROVED.format(
            source=recorded_name(source.name), target=recorded_name(target.name)))
    _door_for(root_of(engagement_dir), household_name_of(engagement_dir), target)    # the door, before any folder is made
    target.parent.mkdir(parents=True, exist_ok=True)
    if kind == ledger.OP_MOVE:
        _mark_a_move_into_review(engagement_dir, op)
        _move_whole(source, target, within=root_of(engagement_dir))
    else:
        _copy_whole(source, target, expect=op[ledger.DIGEST_KEY], cache=cache,
                    root=room_root(engagement_dir))


def _intend(
    engagement_dir: Path,
    key: str,
    ops: list[ledger.IntentOp],
    *,
    by: str,
    row: dict | None = None,
    then: str = "",
    was: str = "",
    also: list[dict] | None = None,
    reason: str = "",
) -> None:
    """Write down what this decision is about to do, before it does it -
    once every step is known to stay in its return's places (decision
    180), so a step refused is never an intent left open.

    **The intent is the decision** (decision 119). The record was already
    all-or-nothing and the disk was already atomic step by step; what sat
    between them was a run killed after a file had moved and before the
    row that explains it was written. So the operations go down first,
    keyed by the row's own identity, with the row the decision will record
    and the event that will complete it - and the next pass finishes from
    the record what the fingerprints say is still undone.

    Its own call, before the operations, which is the one place decision
    102's "one decision, one call, one transaction" is deliberately two:
    the second call is the decision's existing one, and it closes this.
    A decision that moves nothing writes none of this - there is nothing to
    finish - which is why ``dismiss`` never appears here.

    **Every intent carries a row** since decision 125. A pass's move of a
    drop out of the inbox wrote one without one until then; that intent is
    retired with the inbox it belonged to - it belonged to the one
    engagement whose folder the inbox was in, and the inbox is the
    household's now - and what it bought is stated where it went: a drop a
    killed run had already moved is sorted as a stray on the next pass,
    dated that day.

    ``was`` is the identity the row is leaving, where a decision re-keys
    the row. It travels here for the reason the row does: a recovery has
    to write the row event the decision would have written, and one
    without it would leave the record holding the row twice. No writer
    passes one since decision 132 took the hand-over's re-key away; the
    shape and the recovery's reading of it stay.

    **A release is written even with nothing to move** (decision 132). A
    hand-over is two intents in two records, and the one here - ``then``
    :data:`tracker.ledger.RELEASED` - is what lets this household's own
    pass finish its half after a kill, whether or not there was a parked
    copy to remove. ``reason`` is the sentence the release will say.
    Nothing here ever writes into another return's record: each record's
    half of a decision is that record's own intent.
    """
    for op in ops:
        _refuse_a_step_outside(engagement_dir, op)
    _prove(engagement_dir, ops)
    # A working copy this decision moves into review is marked before the
    # decision is written down (decision 190's re-check, M-N1): a refused
    # mark is then a refusal that records nothing, never an open intent
    # that every later pass would try to finish and fail on.
    for op in ops:
        _mark_a_move_into_review(engagement_dir, op)
    if not ops and then != ledger.RELEASED:
        return
    event = ledger.new(ledger.MOVING, **{
        ledger.KEY_KEY: key, ledger.OPS_KEY: ops, ledger.DECIDED_BY_KEY: by,
    })
    if row is not None:
        event[ledger.ROW_KEY] = row
    if was and was != key:
        event[ledger.WAS_KEY] = was
    if then:
        event[ledger.EVENT_KEY_AFTER] = then
    if also:
        event[ledger.ALSO_KEY] = list(also)
    if reason:
        event[ledger.REASON_KEY] = reason
    store.record(store.connect(), engagement_dir, event)


def _prove(engagement_dir: Path, ops: list[ledger.IntentOp]) -> None:
    """Give every copy in ``ops`` the fingerprint it will be proved against
    (decision 187), or raise :data:`COPY_UNPROVED` before anything is
    recorded. In place, because the caller carries out the very operations
    the intent records.

    A copy whose caller named no digest - a row recorded without its bytes
    (decision 65) - takes it from an earlier step of the same intent whose
    target is this copy's source (the move that brings the original in):
    that step's digest, or the bytes of that step's own source; failing
    that, from the copy's source itself where it is there to be read. A copy
    with neither has nothing to be proved against, and an intent that
    would carry one is never written.
    """
    came_from: dict[str, ledger.IntentOp] = {}   # a step's target -> the step that brings it there

    def fingerprint(location: str) -> str:
        step = came_from.get(location)
        if step is not None:
            return step.get(ledger.DIGEST_KEY) or fingerprint(step[ledger.FROM_KEY])
        return _digest_or_none(locate(engagement_dir, location)) or ""

    unproved = []
    for op in ops:
        if op[ledger.OP_KEY] == ledger.OP_COPY and not op.get(ledger.DIGEST_KEY):
            digest = fingerprint(op[ledger.FROM_KEY])
            if not digest and locate(engagement_dir, op[ledger.FROM_KEY]).exists():
                # There, and not readable now - a sync client or a scanner
                # holding it. Said as that, never as a record to check.
                raise FilingError(COPY_UNREAD.format(
                    source=locate(engagement_dir, op[ledger.FROM_KEY]).name))
            if not digest:
                raise FilingError(COPY_UNPROVED.format(
                    source=recorded_name(locate(engagement_dir, op[ledger.FROM_KEY]).name),
                    target=recorded_name(locate(engagement_dir, op[ledger.TO_KEY]).name)))
            unproved.append((op, digest))
        if ledger.TO_KEY in op:
            came_from[op[ledger.TO_KEY]] = op
    for op, digest in unproved:          # every one known before any is changed
        op[ledger.DIGEST_KEY] = digest


def _abandon(engagement_dir: Path, key: str) -> None:
    """Say the move this key had open is not to be finished forward.

    Written by the rollback on a *refused* record, which puts the files
    back: without it the next pass would finish a move the record would
    not take. A refusal is not a crash, and this is how the two are told
    apart. Best effort by design - the append can itself fail, and the
    answer to that is in the recovery: the intent stays open, the next
    pass finishes the move forward and records the row the intent carried,
    which is the row the person decided.
    """
    try:
        store.record(store.connect(), engagement_dir, ledger.new(
            ledger.MOVE_ABANDONED, **{ledger.KEY_KEY: key}))
    except Exception as exc:          # the real error is the one the caller is raising
        errors.keep("filer", exc, name=key)
        log.error("Could not record that a move was abandoned (%s)", errors.error_class(exc))


def _carry_out_a_persons_ops(engagement_dir: Path, key: str, ops: list[ledger.IntentOp]) -> None:
    """Carry out the operations of a person's unfiling or put-back, whose
    first step is the one that may go into review (decision 190's
    re-check, M-N1).

    A move into review was marked before the intent was written
    (:func:`_intend`); a *copy* into review can only be marked on its temp,
    so a refusal comes here, from the first step, before anything of the
    decision has happened - and the intent is abandoned, so the refusal
    records nothing and no later pass tries to finish it. The person sees
    the refusal; the row stands as it was. A refusal on a later step
    (none of today's decisions has one) leaves the intent open for the
    recovery, which stops on it once (:func:`_finish_interrupted_moves`).
    """
    for index, op in enumerate(ops):
        try:
            _do_op(engagement_dir, op)
        except MarkRefusedError:
            if index == 0:
                _abandon(engagement_dir, key)
            raise


def _refuse_if_a_move_is_open(engagement_dir: Path) -> None:
    """Refuse a person's action while a run that was interrupted here has
    a move still open (decision 119).

    Asked before the row is found and so before 112's freshness check: the
    record is in the middle of a decision about this folder, and a click
    made on what the app last drew is a click made on a row that may be
    about to be rewritten by the recovery. Finishing the move is a pass's
    work, the pass runs it first thing, and the app's Run now is a pass -
    which is simpler and safer than five recovery paths, one per action.
    """
    if store.open_intents(store.connect(), engagement_dir):
        raise FilingError(OPEN_INTENT_REFUSAL)


def _the_record_holds(engagement_dir: Path, entry: IndexEntry) -> bool:
    """True when the engagement's record already carries ``entry`` as written.

    Asked in the moment after a failed :func:`_record`, to decide whether
    the file this call moved has to go back. A transaction either
    committed or it did not, so the answer is never half a write - and the
    whole row is compared, because an older row for the same original is
    not it.
    """
    try:
        return entry in read_index(engagement_dir)
    except Exception:
        return False


# --------------------------------------------------- an interrupted move ----

#: And when neither end of the step holds those bytes any more. Nothing is
#: guessed from that: what the sentence adds is whether the client's own
#: original is still where the record says.
INTERRUPTED_MOVE_LOST_DETAIL = ("{name} from {source} to {to} and neither holds it now; "
                                "the original {pbc} {held}")
INTERRUPTED_ORIGINAL_HELD = "is still there"
INTERRUPTED_ORIGINAL_GONE = "is not there either"
#: Attention, for an interrupted step whose file is a cloud placeholder:
#: reading one would make the sync client download it, so nothing is
#: touched and nothing is decided, and the move stays open for the pass
#: after the sync has finished.
INTERRUPTED_SYNCING = ("an interrupted step was moving {name} and {location} is still "
                       "syncing; nothing was touched and the next pass finishes it")
#: Attention, for an interrupted step into review whose copy could not be
#: marked for Protected View (decision 190's re-check, M-N1): it follows
#: :data:`tracker.copies.MARK_REFUSED`, once, and the pass goes on.
INTERRUPTED_MARK_REFUSED = ("an interrupted step was putting it into review; nothing was moved, "
                            "the step was abandoned and the row stands as it was")


#: What :func:`_finish_the_ops` found: every step is done, a file at one
#: end is still syncing, the destination holds somebody else's bytes, or
#: neither end holds the bytes the step was moving.
_FINISHED = "finished"
_SYNCING = "syncing"
_TAKEN = "taken"
_LOST = "lost"


def _waiting_on_sync(path: Path) -> bool:
    """Whether this path is a placeholder the sync client has not brought
    down. Never read: hashing one downloads it."""
    return path.is_file() and is_cloud_placeholder(path)


def _the_bytes(path: Path) -> str | None:
    """What this file holds, or None where there is nothing to read - no
    file, a placeholder, or a file this host cannot read now."""
    if not _here(path):
        return None
    return _digest_or_none(path)


def _finish_the_ops(
    engagement_dir: Path, ops: list[ledger.IntentOp], cache: ContentCache | None
) -> tuple[str, ledger.IntentOp | None]:
    """Finish the steps of one intent that reality says are not done.

    Each step is checked by bytes and only then acted on, in the order the
    decision wrote them - a step may stand on the one before it. Four
    answers, and only these:

    - the destination holds the digest: done, and nothing is touched;
    - the destination is not there and the source holds the digest: the
      move or the copy is made now, which is what the record decided;
    - a stand-down whose file is gone is done, and one that still holds the
      digest is made now (the row says those bytes live elsewhere);
    - anything else stops this intent where it stands and is answered by
      the caller - never by moving something.

    A destination that holds *other* bytes is the contradiction, and a
    destination this host cannot read is treated as one: it is somebody's
    file either way, and the machine never overwrites and never deletes
    what it finds. A step whose row carried no digest (decision 65) can be
    proved by nothing, so the file has only to be there for the step to be
    made and any file at the destination stops it - except a copy, which
    since decision 187 is proved against its source's bytes, read now.
    """
    # Every step is held to its return's places before any is looked at
    # (decision 180): a recovery acts on lines another machine or a
    # restored copy may have written, and a step outside them is the
    # record's problem for a person, never a move.
    # And through no link (decision 187, the review's M3): a removal is
    # carried out here rather than through _do_op, and its digest is read
    # before it is removed, so both ends are asked before any byte is read.
    for op in ops:
        _refuse_a_step_outside(engagement_dir, op)
        _refuse_a_step_through_a_link(engagement_dir, op)
    for op in ops:
        kind = op[ledger.OP_KEY]
        source = locate(engagement_dir, op[ledger.FROM_KEY])
        digest = op.get(ledger.DIGEST_KEY, "")
        if _waiting_on_sync(source):
            return _SYNCING, op
        if kind == ledger.OP_COPY and not digest and source.is_file():
            # An intent from before decision 187 may hold a copy with no
            # fingerprint (decision 65). The original is the record, so the
            # copy is proved against its bytes as _prove() would have done
            # when the intent was written; one that cannot be read now is
            # left for a person, never copied unproved.
            digest = _digest_or_none(source) or ""
            if not digest:
                return _LOST, op
            op = {**op, ledger.DIGEST_KEY: digest}
        if kind == ledger.OP_REMOVE:
            if digest and _the_bytes(source) == digest:
                source.unlink(missing_ok=True)
            continue                 # gone already, or not provably the row's to take
        target = locate(engagement_dir, op[ledger.TO_KEY])
        if target.exists():
            if _waiting_on_sync(target):
                return _SYNCING, op
            # With a digest, the bytes say whether this step happened.
            # Without one - a drop nobody has hashed yet, a row recorded
            # without its bytes - a move that has happened is a source that
            # is gone, and anything else at a destination this decision
            # chose because it was free is somebody's.
            if (_the_bytes(target) == digest) if digest else not source.exists():
                continue             # this step happened
            return _TAKEN, op
        if not source.is_file() or (digest and _the_bytes(source) != digest):
            return _LOST, op
        _do_op(engagement_dir, op, cache=cache)
    return _FINISHED, None


def _a_copy_to_act_on(
    engagement_dir: Path, entry: IndexEntry, cache: ContentCache | None
) -> tuple[str, str]:
    """Where the person's copy of this document is, making one if there is
    none this row can prove.

    A row the recovery parks has to have a working copy a person can open
    and file, and the one the interrupted step was making is not there -
    the place it was going holds somebody else's file. The original in
    The year's folder is the record, so the copy comes from it, into
    ``REVIEW_DIR_NAME`` under the client's own name, never over anything.
    The copy is named as every review copy is (:func:`_review_copy_path`,
    decision 131): cut to the room the review folder leaves. A copy that
    cannot be made leaves the row naming **no** copy - never the one the
    interrupted step was making, which is not there (decision 131's review,
    F1) - and the second value is the sentence its reason gains; so is a
    copy fitted past a reader's limit. Inventing a path would be worse than
    an honest one that is empty.
    """
    for location in entry.filed_locations:
        if (entry.digest and _may_touch(engagement_dir, location, writes=False)
                and _the_bytes(locate(engagement_dir, location)) == entry.digest):
            return location, ""
    review_dir = engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    # The original is read from where the row says only where a step of
    # this return may read (decision 180): a row another machine or a
    # restored copy wrote is held to the same places as its steps.
    code = place_problem(engagement_dir, entry.pbc_location, writes=False)
    if code is not None:
        return "", OP_OUTSIDE.format(name=engagement_dir.name, location=_shown(entry.pbc_location),
                                     reason=code)
    source = locate(engagement_dir, entry.pbc_location)
    # Nor through a link (decision 187, A-7): the place rule is lexical,
    # and a junction swapped in for the year's folder would have the copy
    # read whatever it points at.
    if is_link(source) or through_a_link(source.parent, root_of(engagement_dir)):
        return "", MOVE_THROUGH_A_LINK.format(name=source.name, within=root_of(engagement_dir))
    # The copy the interrupted step was about to carry out of review is
    # still there when the step never happened: it is these bytes and it
    # is the copy a person may have written on, so it is used rather than
    # doubled (:func:`_existing_copy`, as everywhere else).
    waiting = _existing_copy(review_dir, source, entry.digest) if entry.digest else None
    if waiting is not None:
        return prepared_location(review_dir, waiting.name), ""
    try:
        parked, past_reader = _review_copy_path(review_dir, entry.original_name,
                                                room_root(engagement_dir))
        review_dir.mkdir(parents=True, exist_ok=True)
        _copy_whole(source, parked, expect=entry.digest or sha256_of(source), cache=cache,
                    root=room_root(engagement_dir))
    except NoRoom as exc:
        errors.keep("filer", exc, name=entry.original_name)
        log.error("Could not park a review copy (%s)", errors.error_class(exc))
        return "", str(exc)
    except (OSError, FilingError) as exc:
        # An OS error's words spell out the path - a client's folder, and
        # whatever its name holds - so the row says its class; a
        # FilingError is the firm's own sentence and is said whole
        # (decision 190).
        errors.keep("filer: review copy", exc, name=entry.original_name)
        return "", REVIEW_COPY_FAILED.format(name=entry.original_name,
                                             problem=errors.said(exc, FIRM_WRITTEN))
    return prepared_location(review_dir, parked.name), past_reader


def _finish_interrupted_moves(
    engagement_dir: Path,
    entries: list[IndexEntry],
    before: dict[str, dict],
    cache: ContentCache | None,
) -> list[FileError]:
    """Finish, from the record, every move a killed run left half made.

    **The fingerprint identifies; the record decides** (decision 119). What
    is finished here is a decision the record already holds - the intent a
    pass or a person wrote before touching a file - and the fingerprint
    says only which half of it happened. Where it cannot say, nothing moves
    and a person decides: a destination holding another file is never
    touched, and bytes that are at neither end are never guessed at. It is
    the same line decision 109 draws (the sweep identifies a moved copy and
    a person decides), 110 (the person acts) and 111 (the earlier row's
    decision decides a re-send).

    Runs at the start of every pass, under the lock, before anything else
    looks: before the digests of rows recorded without them are filled in,
    before the client's folder is read for strays, and before the sweep -
    so an interrupted person's filing is finished and recorded as theirs
    rather than swept up as a copy somebody dragged.

    The row each intent carries is recorded as the intent recorded it - the
    event it named, the row it named, dated the day the person made the
    decision - in one call with the events that travelled with it, so a
    filing recovered is a filing, and the keyword it taught is taught.
    Every intent carries one: the move of a drop out of the inbox wrote one
    without a row until decision 125 retired it, and what that costs is
    stated there - a drop a killed run had already moved is sorted as a
    stray on the next pass, dated that day rather than the day it arrived.

    Mutates ``entries`` and ``before`` to what the record holds after it,
    so the pass that follows reads the rows this finished. Returns the
    attention lines.
    """
    conn = store.connect()
    intents = store.open_intents(conn, engagement_dir)
    if not intents:
        return []
    attention: list[FileError] = []
    rows_recorded = False
    for intent in intents:
        key = str(intent.get(ledger.KEY_KEY) or "")
        row = intent.get(ledger.ROW_KEY)
        try:
            outcome, op = _finish_the_ops(engagement_dir, intent.get(ledger.OPS_KEY) or [], cache)
        except MarkRefusedError as exc:
            # A copy this intent was carrying into review could not be
            # marked for Protected View (decision 190's re-check, M-N1):
            # the step moved nothing, and finishing it forward would fail
            # on every pass after this one. The intent is abandoned - the
            # row stands as the record held it - and the pass says so
            # once and goes on.
            _abandon(engagement_dir, key)
            name = entry_from_json(row).original_name if row else key
            attention.append(FileError(
                name, f"{errors.said(exc, FIRM_WRITTEN)}; {INTERRUPTED_MARK_REFUSED}", True))
            errors.keep("filer", exc, name=name)
            log.warning("An interrupted step was abandoned (%s)", errors.error_class(exc))
            continue
        if outcome == _SYNCING:
            op = cast(ledger.IntentOp, op)   # every outcome but _FINISHED names the step it stopped at
            attention.append(FileError(Path(op[ledger.FROM_KEY]).name, INTERRUPTED_SYNCING.format(
                name=Path(op[ledger.FROM_KEY]).name,
                location=op.get(ledger.TO_KEY) or op[ledger.FROM_KEY],
            ), True))
            continue                 # the move stays open; the next pass looks again
        entry = entry_from_json(row)
        if outcome == _FINISHED and intent.get(ledger.EVENT_KEY_AFTER) == ledger.RELEASED:
            # This record's half of a hand-over (decision 132): the parked
            # copy is gone - removed now, or already - so the row is
            # released, in the words the person's click would have written.
            # Nothing of the other record is read or written here: its half
            # is its own intent, finished by its own pass.
            store.record(conn, engagement_dir, ledger.new(ledger.RELEASED, **{
                ledger.KEY_KEY: key,
                ledger.REASON_KEY: str(intent.get(ledger.REASON_KEY) or ""),
            }))
            rows_recorded = True
            log.warning("Finished the interrupted release of %s from the record",
                        entry.original_name)
            continue
        if outcome == _FINISHED:
            # The identity the row is leaving travels with the intent
            # where a decision re-keyed the row, so the row the recovery
            # writes re-keys exactly as the decision's own would have and
            # the record does not end holding it twice.
            leaving = str(intent.get(ledger.WAS_KEY) or "")
            events = [ledger.new(str(intent.get(ledger.EVENT_KEY_AFTER) or ledger.PARKED),
                                 **{ledger.KEY_KEY: key, ledger.ROW_KEY: row,
                                    **({ledger.WAS_KEY: leaving} if leaving else {})})]
            events += list(intent.get(ledger.ALSO_KEY) or [])
            store.record(conn, engagement_dir, *events)
            rows_recorded = True
            log.warning("Finished the interrupted %s of %s from the record",
                        intent.get(ledger.EVENT_KEY_AFTER), entry.original_name)
            continue
        op = cast(ledger.IntentOp, op)       # _FINISHED, the one outcome with no step, went on above
        sentence = _the_trouble(engagement_dir, entry, op, outcome)
        parked, copy_said = _a_copy_to_act_on(engagement_dir, entry, cache)
        new_entry = replace(
            entry, decision=NEEDS_REVIEW, identifier="", also_filed="", answers="",
            prepared_location=parked,
            reason="; ".join(part for part in (
                _without_moved_sentence(entry.reason), sentence, copy_said) if part),
            code=reasons.code_of(sentence),
        )
        store.record(conn, engagement_dir, _ledger_event(ledger.PARKED, new_entry))
        rows_recorded = True
        attention.append(FileError(
            Path(op.get(ledger.TO_KEY) or entry.original_name).name, sentence, True))
        log.warning("An interrupted step on %s could not be finished: %s",
                    entry.original_name, sentence)
    if rows_recorded:
        fresh = read_index(engagement_dir)
        entries[:] = fresh
        before.clear()
        before.update({ledger_key(one): entry_to_json(one) for one in fresh})
    return attention


def _the_trouble(engagement_dir: Path, entry: IndexEntry, op: ledger.IntentOp, outcome: str) -> str:
    """The sentence a row gets when its step could not be finished: the
    destination holds a different file, or neither end holds the bytes."""
    if outcome == _TAKEN:
        where = op[ledger.TO_KEY]
        try:
            size = round(locate(engagement_dir, where).stat().st_size / 1024, 1)
        except OSError:
            size = 0.0
        return reasons.INTERRUPTED_MOVE.format(listed=INTERRUPTED_MOVE_DETAIL.format(
            name=entry.original_name, to=where, size=size, pbc=_shown(entry.pbc_location)))
    held = (INTERRUPTED_ORIGINAL_HELD
            if _may_touch(engagement_dir, entry.pbc_location, writes=False)
            and _the_bytes(locate(engagement_dir, entry.pbc_location)) == entry.digest
            else INTERRUPTED_ORIGINAL_GONE)
    return reasons.INTERRUPTED_MOVE_LOST.format(listed=INTERRUPTED_MOVE_LOST_DETAIL.format(
        name=entry.original_name, source=_shown(op[ledger.FROM_KEY]),
        to=op.get(ledger.TO_KEY, ""), pbc=_shown(entry.pbc_location), held=held))
