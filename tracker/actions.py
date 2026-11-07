"""A person's actions on the record, and the re-scan after them: file a
parked document by hand, set one aside, unfile one, mark a request missing
again, put a moved or deleted copy back, and give a request another
identifier with its documents.

Each is a decision a person makes about one row in the app, carried out
here under the engagement lock and recorded as that person's, in five
parts, each upholding the decision rows it names:

- **Filing by hand** (decisions 103, 110, 112, 128, 168 and 201).
  :func:`assign_review_file` files a parked document under a request the
  way the filer would have, with the keyword it teaches (decision 103) and
  a spelling (decision 128) in the same transaction; it is also decision
  110's keep-it-here for a moved copy, and with ``adding=`` it puts an
  issuer row on the list first (decision 201, :func:`_issuer_to_add`).
  :class:`AssignResult` says what it did.
- **Setting aside and unfiling** (decisions 76, 77, 94 and 113).
  :func:`dismiss_review_file` says no request asks for a parked document
  and moves nothing (``NOT_REQUESTED``); :func:`unfile_document` takes a
  filed one back to the review folder, every copy decision 94 made of it
  leaving its place, and never unlearns a keyword (:data:`LEFT_FILED`,
  :func:`find_filed`).
- **Mark missing** (decisions 146 and 157). :func:`mark_missing_again`
  takes one request off what a consolidated statement answers, or a row's
  own request off a row whose copy and original are both gone, so the
  letter asks for it again.
- **Putting back** (decisions 110 and 157). :func:`restore_working_copy`
  returns a moved copy's bytes to where the record put them
  (:func:`_put_back_a_moved_copy`, :func:`find_moved`) or makes a deleted
  copy again from the row's proved original (:func:`_find_to_put_back`,
  :func:`_gone_copies`, :func:`_make_a_gone_copy_again`), and never
  overwrites, deletes or guesses (:data:`PUT_BACK_REFUSED`,
  :data:`PUT_BACK_ALREADY`).
- **Renaming a request** (decisions 119, 146, 160 and 168).
  :func:`rename_request` gives a request another identifier in one act
  finished forward: the list renamed and one intent per row in one write,
  then the copies renamed in place (:data:`RENAME_UNFINISHED` when a move
  fails after it). :func:`documents_by_request` is what a save of the list
  asks first (decision 160): how many filed documents each request holds,
  counted by the client README's own rule.

Unfiling, Mark missing, a put-back and a rename end with :func:`_rescan`,
which puts the request's status back at once, outside the lock the scan
takes for itself (:data:`RESCAN_REFUSED` when another run holds it).

**A filed document can go back for review, on the record.**
``unfile_document()`` moves the working copy back to ``REVIEW_DIR_NAME``
under the client's own name and rewrites the row, so the correction people
used to make by dragging in Explorer - which the index never learned - is
one the index knows about. The request is re-scanned straight after, and
goes back to what it is without the document.

**A person puts a moved copy back, keeps it, or sends it to review - on
the record.** ``restore_working_copy()`` returns the bytes to where the
record put them; ``assign_review_file()`` files the wanderer where it now
sits (or under another request the person picks); ``unfile_document()``
sends it back to ``REVIEW_DIR_NAME``. Each is one event of the person's
own, each checks the row's sequence number first and every byte it is
about to move second, and a home holding a different file is never
overwritten - that file stays and this document's copy goes to review.

**Why it is its own module** (SPEC-architecture-p4 P4.9, P335; the
architecture audit's A-1, step 6). This code sat in the filer, and none of
it sorts: the pass decides where a drop goes, and these are a person's
answers to a row the pass or another person already wrote. The pieces a
person's action shares with the hand-over stay in the filer, because the
hand-over is the filer's (decision 132): the freshness check
(:func:`_refuse_if_stale`), the review lookups (:func:`find_parked`,
:func:`_find_row`, :func:`_names_row`, :func:`_wanted`), the spelling a
filing teaches (:class:`Spelling`, :func:`_taught_spelling`), the pass's
own remaking of a gone copy (:func:`_make_again`, :func:`_remade`,
:func:`_the_original_now`) and the reason sentences a person's decision
writes. This module imports them from the filer by name, and the filer
never imports this one. What a person's action shares with the pass sits
below both: the write-ahead intents and the record's one write in
:mod:`tracker.intents` (decision 119), naming and copying in
:mod:`tracker.copies`.

**It composes the record's events** (P327). The issuer row a filing adds
(``ledger.RULES_CHANGED``), the keyword it teaches
(``ledger.KEYWORD_LEARNED``) and a rename's intent for each row it renames
(``ledger.MOVING``) are calls of ``ledger.new`` here, so it is one of the
record's writers, named in ``tests/test_layers.py``'s ``COMPOSERS``; the
filer stays one, for the spelling a filing teaches and the hand-over.

**It upholds no standing rule of its own.** A person's action is a
person's decision, not a guess, and the code that keeps an original
untouched and a move finished from the record - the filer, :mod:`tracker.copies`
and :mod:`tracker.intents` - still does that work for it, so this module
is not among any rule's enforcers.

**The one way to the scanner** (P313's Q-A, P335). :func:`_rescan` imports
:mod:`tracker.scanner` inside the call, so a person's action is scanned
the moment it lands; the scanner reads the index from :mod:`tracker.index`
and imports neither this module nor the filer, and the filer no longer
reaches the scanner at all. ``tests/test_layers.py`` holds all three.

**Why it sits at layer 3.** It reads the filer, :mod:`tracker.intents`,
:mod:`tracker.inbox` (``_absent`` and ``_copy_taken_by_a_later_row``) and
:mod:`tracker.readme_ack` (the received rule, ``_counts_as_received`` and
``_requests_of``) in-layer, :mod:`tracker.copies` (layer 2), the index, the
request list, the record types, the store, the journal, the scaffold and
the validators (layer 1), and the layout, the lock, the bounds, the reasons
and the errors (layer 0) at load time, and the scanner (layer 3) at call
time. Only the API imports it. It is at layer 3 because the filer it reads
is; nothing below may import it, and the filer may not either, or the two
would import each other.

**Every reader asks this module.** The API imports the seven actions from
here, and the filer offers none of them on. A stand-in follows the name's
readers (the audit's A-4): one for a name this module reads as a global is
set on this module, beside the filer and the others that read it.

**One private name of the index crosses into it**: the index's
``_without_moved_sentence``, which a put-back asks when it takes the moved
sentence off the row it restores, as the filer does (P319's one exception;
``tests/test_index.py`` pins the crossing over the filer's family).

**Why it logs as ``tracker.filer``** (SPEC-architecture-p4 section 2.1).
The run log and the error log print each line's logger name, so a name of
this module's own would change the lines a person and the office read. It
is the same logger object as the filer's, so no handler and no test sees a
difference.

The comments and docstrings below came with the code, word for word. Where
one names the pass, the filer or "this module" as the caller of a scan or
the reader of a name, it is this module's code it describes; a function of
the filer's that it names is imported from there.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from tracker import errors, ledger, reasons, store
from tracker.bounds import typed_identifier_problem
from tracker.copies import (
    COPY_SYNCING,
    FIRM_WRITTEN,
    ORIGINAL_GONE,
    ORIGINAL_SYNCING,
    FilingError,
    _copy_whole,
    _digest_or_none,
    _existing_copy,
    _here,
    _move_whole,
    _review_copy_path,
    _room_in,
    _shown,
    copies_of,
    prepared_name_for,
)

# The pieces a person's action shares with the hand-over stay in the filer
# (decision 132): the freshness check, the review lookups, the spelling a
# filing teaches, the pass's remaking of a gone copy and the sentences a
# person's decision writes. They are imported by name; the filer never
# imports this module.
from tracker.filer import (
    _ORIGINAL_GONE,
    _ORIGINAL_PROVED,
    _ORIGINAL_UNREAD,
    _PARKED,
    ASSIGNED_BY_PERSON,
    DISMISSED_BY_PERSON,
    MARKED_REFUSAL,
    MOVED_BACK_SENTENCE,
    NOTHING_TO_PUT_BACK,
    OVERRODE_SHORTLIST,
    UNFILED_BY_PERSON,
    Spelling,
    _find_row,
    _make_again,
    _names_row,
    _refuse_if_stale,
    _remade,
    _taught_spelling,
    _the_original_now,
    _wanted,
    find_parked,
)
from tracker.inbox import _absent, _copy_taken_by_a_later_row

# The index's words and its readers live in tracker/index.py (P319); the one
# private name that crosses, _without_moved_sentence, among them.
from tracker.index import (
    DUPLICATE,
    FILE_MOVED,
    FILED,
    MARKED_MISSING,
    NEEDS_REVIEW,
    NOT_REQUESTED,
    _without_moved_sentence,
    both_gone,
    ensure,
    holds_the_row,
    marked_missing,
    moved_to,
    prepared_location,
    read_index,
)

# The write-ahead intents and the record's one write live in
# tracker/intents.py (P332): a person's action writes its intent, carries it
# out and records it through them, as the pass does.
from tracker.intents import (
    _abandon,
    _carry_out_a_persons_ops,
    _do_op,
    _intend,
    _op,
    _record,
    _refuse_if_a_move_is_open,
    _the_bytes,
    _the_record_holds,
)
from tracker.layout import locate, location_of, measured_length, path_limit, recorded_name, room_root
from tracker.locking import engagement_lock
from tracker.manifest import (
    Override,
    RequestItem,
    list_head,
    load_manifest,
    narrowing_rows,
    override_label,
    refuse_a_stale_list,
    renamed_rules,
    validated,
)

# The received rule a save of the list counts by is the client README's, in
# tracker/readme_ack.py (P334), so the two count a received document alike.
from tracker.readme_ack import _counts_as_received, _requests_of
from tracker.records import (
    CANDIDATE_SEP,
    COL_IDENTIFIER,
    IndexEntry,
    entry_to_json,
    format_answers,
    format_evidence,
    identifier_key,
    ledger_key,
    quoted,
    rule_to_json,
)
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
    assign_files,
    matches_identifier,
    owner_of,
    sanitize_component,
)
from tracker.validators import extension_of, is_cloud_placeholder, sha256_of

# The filer's logger, by its name (SPEC-architecture-p4 section 2.1): the run
# log and the error log print each line's logger name, so a name of this
# module's own would change the lines a person and the office read. It is the
# same logger object, so no handler and no test sees a difference.
log = logging.getLogger("tracker.filer")


# ----------------------------------------------------------------- assign ----


@dataclass(frozen=True, slots=True)
class AssignResult:
    """What filing one parked document by hand did."""

    entry: IndexEntry            # the rewritten index row
    moved_review_copy: bool      # True: the parked copy (REVIEW_DIR_NAME) became the working copy
    keyword: str = ""            # keyword added to the row's Any Keywords, if any
    keyword_note: str = ""       # why it was not added, when it was not
    left_in_review: str = ""     # a parked copy that no longer held the row's bytes, and stayed
    overrode_shortlist: str = ""  # the sentence written when the pick was off the shortlist
    spelling: str = ""           # spelling added to one of the return's people, if any
    spelling_note: str = ""      # why it was not added, when it was not


def _issuer_to_add(
    engagement_dir: Path, original: str, identifier: str, items: dict[str, RequestItem], *,
    adding: RequestItem, head: str | None, seq: int | None,
) -> tuple[dict[str, RequestItem], list[dict]]:
    """The list with a card's issuer row in it, and the ``rules_changed``
    event that adds it - or the refusal, before any file is read (decision
    201). Called under the engagement lock :func:`assign_review_file` holds.

    In the order the ruling gives: the list's version, the row's own, the
    card's reason now, the editor's own ``validated()`` on the list with
    the row last, and whether the row narrows a row the card's candidates
    name. A refusal names what moved and says nothing was added or filed.
    """
    if not isinstance(head, str) or head.strip() != list_head(engagement_dir):
        raise FilingError(ISSUER_LIST_MOVED)
    entries = read_index(engagement_dir)
    entry = entries[find_parked(entries, original, accepting=(FILE_MOVED,))]
    _refuse_if_stale(engagement_dir, entry, seq)
    if entry.decision != NEEDS_REVIEW or entry.code != reasons.ISSUER_NOT_NAMED.code:
        raise FilingError(NOT_AN_ISSUER_CARD.format(name=entry.original_name))
    if adding.identifier != identifier:
        raise FilingError(f"the row to add is {adding.identifier}, not {identifier}")
    listed = list(items.values())
    # The editor's own rules, the ones a save runs, with the list as it
    # stands as the record: a same-name pair already on it is not this
    # card's to refuse, and the new row's own name is.
    checked = validated([*listed, adding], recorded=listed)
    row = checked[-1]
    narrowed = narrowing_rows(checked)
    candidates = entry.candidate_list
    if not any(row.identifier in narrowed.get(broad, ()) for broad in candidates):
        raise FilingError(ISSUER_DOES_NOT_NARROW.format(
            identifier=row.identifier, listed=", ".join(candidates) or "-"))
    event = ledger.new(ledger.RULES_CHANGED, **{
        ledger.RULES_KEY: [rule_to_json(row)], ledger.REMOVED_KEY: [], ledger.INFO_KEY: {},
    })
    return {i.identifier: i for i in checked}, [event]


def assign_review_file(
    engagement_dir: Path | str,
    original: str,
    identifier: str,
    *,
    keyword: str = "",
    spelling: Spelling | None = None,
    today: dt.date | None = None,
    seq: int | None = None,
    shortlist: Sequence[str] | None = None,
    adding: RequestItem | None = None,
    head: str | None = None,
) -> AssignResult:
    """File a parked document under a request, the way the filer would have.

    ``original`` is the index row to act on: its PBC location
    (the year's folder and the original's name) or, failing that, its original name among
    the rows still marked Needs Review. The working copy is created under the
    canonical name in ``PREPARED_DIR_NAME`` (decision 168) - moved from ``REVIEW_DIR_NAME`` when it is still there, copied from the year's folder when it is not -
    and the index row is rewritten as Filed with the decision attributed to
    a person. The original in the year's folder is not touched.

    ``keyword`` is optional: recorded against the request so the next
    document like this one routes itself, and laid over the row's typed
    Any Keywords by every reader (``manifest.load_manifest``). It is
    recorded, never typed into the row (decision 103): the one note left
    is that the request already had the word.

    ``spelling`` is optional too, and rides the same transaction
    (decision 128): a spelling the page printed, added to one of the
    return's people, so the next document that prints it confirms itself.
    A spelling of one word and a person the return does not list are both
    refused before a byte is read. Unfiling never takes a spelling back,
    exactly as it never takes a keyword back (decision 77); a spelling is
    removed in the editor.

    A ``FILE_MOVED`` row is filed from here too - decision 110's "keep it
    here", the answer to a copy somebody renamed under a request's name on
    purpose (decision 168; dragged into a request's folder until then). The
    copy that moves is then the wanderer the row's reason names
    (:func:`moved_to`), which takes the request's canonical name beside
    where it sits, or another request's when the person picks one instead:
    the picker is the same picker, so keeping the file
    and correcting the request is one click. A page decision 94 filed
    under several requests is refused here (``SEVERAL_COPIES_REFUSAL``) and
    put back with :func:`restore_working_copy` first.

    ``seq`` is the row's sequence number as the person saw it and ``shortlist``
    the identifiers the evidence pointed at when they were shown the card,
    both from the caller that drew it (decision 112). A ``seq`` that is not
    the record's refuses before a byte is read (:func:`_refuse_if_stale`); a
    pick that is not on a **non-empty** shortlist is recorded on the row as
    the person's override, with the identifiers it overruled. Neither is
    computed here: the shortlist is :mod:`tracker.review`'s answer and this
    module does not import it, so the caller that shows the suggestions is
    the caller that says what was overruled. A caller with no view - a
    script, a test - passes neither and is checked against nothing.

    ``adding`` is an issuer row to add to the list and file under, for a
    card parked because the K-1 names none of the list's issuers (decision
    201): the API builds it (``templates.issuer_item``) and ``identifier``
    is its identifier. Under the same lock, before a byte is read, it is
    refused unless ``head`` is the list's version now
    (:data:`ISSUER_LIST_MOVED`; ``manifest.list_head`` stays the one
    authority), the row is the one the person saw (``seq``), it is still
    parked for an unnamed issuer (:data:`NOT_AN_ISSUER_CARD`), the list
    with it passes the editor's own ``validated()`` - nested or repeated
    issuer names among them - and it narrows a row this card's candidates
    name (:data:`ISSUER_DOES_NOT_NARROW`). The row goes in as a
    ``rules_changed`` event in ``taught``, so it rides the intent and the
    one ``store.record()`` call after the row's own event, exactly as a
    spelling does (decision 128): the list gains the row only if the
    filing lands.

    The rules the filer lives by still hold: nothing is guessed (the person
    chose), the engagement lock is held, and the row, the move and the
    keyword are recorded in one transaction.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    prepared_dir = engagement_dir / PREPARED_DIR_NAME

    # Everything - the request list, the row, the keyword recorded - under
    # the one lock, so a scheduled pass cannot slip in between.
    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        _refuse_if_a_move_is_open(engagement_dir)
        items = {i.identifier: i for i in load_manifest(engagement_dir)}
        grown: list[dict] = []
        if adding is not None:
            items, grown = _issuer_to_add(engagement_dir, original, identifier, items,
                                          adding=adding, head=head, seq=seq)
        item = items.get(identifier)
        if item is None:
            raise FilingError(f"no request {identifier!r} in the request list")
        if item.manual_override == Override.NOT_APPLICABLE:
            # A row a person set aside does not take a filing: the person
            # clears the override in the editor and files, or leaves it.
            raise FilingError(f"{identifier} is {override_label(item)}; clear the override first")

        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}
        position = find_parked(entries, original, accepting=(FILE_MOVED,))
        entry = entries[position]
        _refuse_if_stale(engagement_dir, entry, seq)
        if entry.decision == FILE_MOVED and entry.also_filed:
            # Decision 110: a page decision 94 filed under several requests
            # has a copy in each, and which of them the person means by
            # "keep it here" is not the machine's to guess. Put it back
            # answers for every copy, and unfiling starts from there.
            raise FilingError(SEVERAL_COPIES_REFUSAL.format(name=entry.original_name))
        if both_gone(entry) and _the_original_now(engagement_dir, entry)[0] != _ORIGINAL_PROVED:
            # Decision 157, B5: nothing to keep - the copy and the original
            # are both gone - in the one sentence the three answers share.
            raise FilingError(NOTHING_TO_PUT_BACK.format(
                prepared=PREPARED_DIR_NAME, pbc=_shown(entry.pbc_location)))
        source = locate(engagement_dir, entry.pbc_location)
        if not source.is_file():
            raise FilingError(ORIGINAL_GONE.format(original=_shown(entry.pbc_location)))
        if is_cloud_placeholder(source):
            raise FilingError(ORIGINAL_SYNCING.format(original=_shown(entry.pbc_location)))
        digest, size_kb = entry.digest, entry.size_kb
        # The copy to move is the one the record says this row's bytes are
        # at. For nearly every row that is the Prepared Location column;
        # for a ``FILE_MOVED`` row it is the wanderer the reason names
        # (decision 110's keep-it-here), and a row whose bytes are nowhere
        # under the firm's folder has none, so the copy comes from the
        # client's original exactly as it does for a parked copy that went.
        here = moved_to(entry) if entry.decision == FILE_MOVED else entry.prepared_location
        parked = locate(engagement_dir, here) if here else None
        # The parked copy is only ever read when it is here, hydrated
        # (hashing a dehydrated one would make the sync client download
        # it), and still this row's - a later row at the same path means
        # this row's copy is gone and what sits there is the later row's.
        # A later row can only take a path the index *names*, which is the
        # Prepared Location column; a wanderer is by definition a path no
        # row names, so that question is not asked of one - and its bytes
        # are checked below either way, which is the stronger test.
        parked_here = (
            parked is not None and _here(parked)
            and (entry.decision == FILE_MOVED
                 or not _copy_taken_by_a_later_row(entries, position))
        )
        if not digest:
            # The pass that preserved this original could not read it back
            # (decision 65) and recorded no digest. A row a person files
            # must carry one: the scanner honours the person's filing only
            # while the copy holds the bytes the row recorded, and a row
            # with none is honoured never. The bytes are the parked copy's
            # - what the pass handled - and the original must still hold
            # them; the original alone is trusted only when no copy is
            # left to check it against.
            evidence = cast(Path, parked) if parked_here else source   # parked_here: a path
            try:
                digest = sha256_of(evidence)
                size_kb = round(evidence.stat().st_size / 1024, 1)
                replaced = evidence is not source and sha256_of(source) != digest
            except OSError as exc:
                raise FilingError(
                    f"the original {_shown(entry.pbc_location)} could not be read "
                    f"({errors.error_class(exc)}); try again when it can"
                ) from exc
            if replaced:
                raise FilingError(
                    f"the original {_shown(entry.pbc_location)} and its parked copy no longer hold the same "
                    "bytes, and the row recorded none - one of them changed after it arrived; "
                    "look at both files first"
                )
        elif sha256_of(source) != entry.digest:
            # The client replaced the original after it was parked (the pass
            # reports it as REPLACED_IN_PBC). Filing the new bytes under the
            # old row's record would be a lie in the audit trail; a person
            # decides which document this is now.
            raise FilingError(
                f"the original {_shown(entry.pbc_location)} no longer holds the bytes this row "
                "recorded - it was replaced after it arrived; look at the file first"
            )

        # The copy goes in the firm's folder itself, named by its request
        # (decision 168) - and so does a mislaid copy a person keeps where
        # it is, which only ever sits there (the app offers Keep it here
        # for nothing else): it takes the request's canonical name beside it.
        dest_folder = prepared_dir
        # Named to fit the room the folder leaves, before anything is made
        # (decision 131): no room even for the shortest name refuses with
        # copies.PATH_NO_ROOM, and nothing has moved.
        taken = {p.name.lower() for p in dest_folder.iterdir()} if dest_folder.is_dir() else set()
        # A copy with these bytes already there is found before a name is
        # measured (decision 131's review, F5): it is reused under its own
        # name, so a folder short of room never refuses a filing it holds.
        # Only this request's own copies are looked at (decision 168).
        existing = _existing_copy(dest_folder, source, digest,
                                  ignore=parked if parked_here else None,
                                  among=copies_of(item, list(items.values()), dest_folder))
        extension = extension_of(source)
        filed_as = existing.name if existing is not None else prepared_name_for(
            item, extension, taken,
            room=_room_in(dest_folder, extension, room_root(engagement_dir)))
        dest_folder.mkdir(parents=True, exist_ok=True)
        target = dest_folder / filed_as

        moved = reused = parked_stood_in = False
        left_in_review = ""
        ops: list[ledger.IntentOp] = []
        # A copy with these bytes already in the folder is a killed earlier
        # attempt's, and is reused rather than doubled. Otherwise the parked
        # copy is moved, but only while it holds the row's bytes: its name
        # is the client's, and a freed name is taken by the next drop called
        # the same, so a person filing row A would carry document B into
        # Prepared under A's canonical name (the eleventh reading); a
        # copy a reviewer's app re-saved is not the row's bytes either and
        # is left where it is, said so, for the person to keep or discard.
        # What will move is decided here and written down before any of it
        # happens (decision 119), so a kill in between is finished from the
        # record rather than left for another person to notice.
        if existing is not None:
            filed_as, target = existing.name, existing
            reused = True
            # ``parked`` is a path wherever ``parked_here`` holds, and only there is it read.
            if parked_here and sha256_of(cast(Path, parked)) == digest:
                # The attempt's copy stands in for it, byte for byte.
                parked_stood_in = True
                ops.append(_op(engagement_dir, ledger.OP_REMOVE, cast(Path, parked), digest=digest))
        elif parked_here and sha256_of(cast(Path, parked)) == digest:
            moved = True                  # keeps any notes a person made on it
            ops.append(_op(engagement_dir, ledger.OP_MOVE, cast(Path, parked), target, digest))
        else:
            if parked_here:
                left_in_review = (
                    f"the parked copy {here} no longer holds the bytes this row "
                    f"recorded (annotated, or re-saved) and was left there; {filed_as} was copied from the original"
                )
            ops.append(_op(engagement_dir, ledger.OP_COPY, source, target, digest))

        # A pick the evidence did not point at, when the evidence pointed
        # somewhere, is the person overruling the shortlist, and the row
        # says so in words (decision 112). An empty shortlist is never an
        # override: with nothing suggested there is nothing to overrule
        # (decision 83's "no need prior"). ASSIGNED_BY_PERSON stays the
        # prefix either way - the scanner honours a person's filing by
        # what the reason starts with.
        overrode = (OVERRODE_SHORTLIST.format(listed=", ".join(shortlist))
                    if shortlist and identifier not in shortlist else "")
        attributed = f"{ASSIGNED_BY_PERSON} on {today.isoformat()}"
        if overrode:
            attributed = f"{attributed}; {overrode}"
        new_entry = replace(
            entry,
            digest=digest,
            size_kb=size_kb,
            identifier=item.identifier,
            prepared_location=prepared_location(dest_folder, filed_as),
            decision=FILED,
            reason=f"{attributed}; was: {entry.reason}",
            candidates="", code=reasons.ASSIGNED_BY_PERSON_CODE,
            # Filed here, it waits for nothing (decision 204).
            waits_for="",
        )
        entries[position] = new_entry
        # The keyword travels with the filing, in the same call and so in
        # the same transaction: a filing that teaches a keyword is one
        # decision, and the rollback below asks whether that decision
        # landed, not whether half of it did. It is recorded, never typed
        # into the row, and load_manifest() lays the taught keywords over
        # the typed ones.
        keyword = keyword.strip()
        note = ""
        if keyword and keyword.lower() in {k.lower() for k in item.any_keywords}:
            note = f"{identifier} already had the keyword {keyword!r}"
        # An issuer row added with the filing (decision 201) goes first, so
        # the record reads the row before anything taught to it.
        taught = [*grown, *([] if note or not keyword else [ledger.new(ledger.KEYWORD_LEARNED, **{
            ledger.IDENTIFIER_KEY: item.identifier, ledger.KEYWORD_KEY: keyword,
        })])]
        # A spelling taught here rides the same transaction, for the same
        # reason the keyword does: a filing that teaches is one decision,
        # and half of it would be a return that never learned the name.
        spelled, said, spelling_note = _taught_spelling(engagement_dir, spelling)
        taught += spelled
        # The intent carries the keyword too: a filing recovered from the
        # record is the whole of the decision the person made, and half of
        # it would be a request that never learned the word.
        _intend(engagement_dir, ledger_key(new_entry), ops, by=ledger.BY_PERSON,
                row=entry_to_json(new_entry), then=ledger.ASSIGNED_BY_PERSON, also=taught)
        for op in ops:
            _do_op(engagement_dir, op)
        try:
            _record(engagement_dir, before, entries,
                    decided={ledger_key(new_entry): ledger.ASSIGNED_BY_PERSON},
                    also=taught)
        except BaseException:
            # The record either took the decision or it did not - one
            # transaction, no third state - so the file goes back where the
            # record says it is, and a retry files it once rather than
            # copying it twice. A killed attempt's copy that stood in for
            # the parked one leaves the row still naming a parked copy that
            # is no longer there, so it is put back from the copy that
            # stood in for it, which is it byte for byte.
            if not _the_record_holds(engagement_dir, new_entry):
                try:
                    if moved:                 # moved and parked_stood_in each needed parked_here
                        _move_whole(target, cast(Path, parked), within=engagement_dir)
                    elif parked_stood_in:
                        _copy_whole(target, cast(Path, parked), expect=digest or sha256_of(target),
                                    root=room_root(engagement_dir))
                    elif not reused:          # a copy that was already there stays
                        target.unlink(missing_ok=True)
                except (OSError, FilingError) as undo:  # the copy stays where it is; the real error is the one to hear
                    errors.keep("filer", undo, name=target.name)
                    log.error("Could not put a file back after the record refused it (%s)",
                              errors.error_class(undo))
                # The files are back where the record says, so the move is
                # not to be finished forward by the next pass (decision 119).
                _abandon(engagement_dir, ledger_key(new_entry))
            raise
    return AssignResult(
        entry=new_entry, moved_review_copy=moved, keyword=keyword if not note else "",
        keyword_note=note, left_in_review=left_in_review, overrode_shortlist=overrode,
        spelling=said, spelling_note=spelling_note,
    )


# ---------------------------------------------------------- not requested ----


def _said(note: str) -> str:
    """A person's note, in the one shape a rewritten Reason carries it."""
    note = note.strip()
    return f" ({note})" if note else ""


@dataclass(frozen=True, slots=True)
class DismissResult:
    """What saying one parked document is not requested did."""

    entry: IndexEntry            # the rewritten index row


def dismiss_review_file(
    engagement_dir: Path | str,
    original: str,
    note: str = "",
    *,
    today: dt.date | None = None,
    seq: int | None = None,
) -> DismissResult:
    """Record that no request asks for one parked document.

    ``original`` names the index row the way :func:`assign_review_file` takes
    it: its PBC location, or failing that its original name among the rows
    still parked. The row is rewritten as ``NOT_REQUESTED`` with the decision
    attributed to a person and what the row said before kept after it.

    Nothing moves. The working copy stays in ``REVIEW_DIR_NAME`` and the
    original in the year's folder is untouched, because a document the client
    sent is never deleted over a decision about a *request*: an agency notice
    or an extra statement is still theirs, and a person who was wrong files it
    afterwards with :func:`assign_review_file`. What changes is what the
    system says about it - the weekly draft stops warning about a file
    somebody has already looked at, and the same bytes sent again come back
    for a fresh look, naming this decision (decision 111): it is a decision
    about one document on one day, not a standing rule that silences that
    document for the rest of the engagement.

    Because nothing moves, nothing is checked against the bytes: this is a
    statement about the request list, not about the file. The engagement lock
    is held and the row is recorded in one transaction, as everywhere else.

    ``seq`` is the row's sequence number as the person saw it (decision
    112): a row rewritten since is refused by name before anything is
    written, and a caller with no view passes none.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()

    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        _refuse_if_a_move_is_open(engagement_dir)
        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}
        position = find_parked(entries, original)
        entry = entries[position]
        _refuse_if_stale(engagement_dir, entry, seq)
        new_entry = replace(
            entry,
            decision=NOT_REQUESTED,
            reason=f"{DISMISSED_BY_PERSON} on {today.isoformat()}{_said(note)}; was: {entry.reason}",
            # Set aside, it waits for nothing (decision 204): the one click
            # is offered only on the row the pass parked.
            waits_for="",
            code=reasons.DISMISSED_BY_PERSON_CODE,
        )
        entries[position] = new_entry
        # Nothing was moved, so there is nothing to put back: a record that
        # refuses the decision leaves the folder as it was and the row as
        # the record still has it.
        _record(engagement_dir, before, entries,
                decided={ledger_key(new_entry): ledger.DISMISSED_BY_PERSON})
    return DismissResult(entry=new_entry)


# ----------------------------------------------------------------- unfile ----


#: What an unfiling says about a working copy whose bytes are not the ones
#: the row recorded. A reviewer's notes are work, and which of the two files
#: the firm wants is not the filer's to decide: the copy stays where it
#: is, a fresh one goes back to review, and a person is told so
#: they can keep or discard it - and knows the row is still counted until
#: they do.
LEFT_FILED = (
    "the working copy {location} no longer holds the bytes this row recorded (annotated, "
    "or re-saved) and was left there; {parked} went back to review from the original"
)
#: What an unfiling says when the re-scan did not happen. The row is
#: rewritten and the file is back in review either way; it is the request's
#: status that waits. There is one reason left - another run holds the
#: engagement - because since decision 103 no scan writes anything but
#: the record.
RESCAN_REFUSED = "the status was not put back now ({why}); the next pass does it"


@dataclass(frozen=True, slots=True)
class UnfileResult:
    """What taking one filed document back for review did."""

    entry: IndexEntry            # the rewritten index row
    moved_working_copy: bool     # True: the working copy itself went back to REVIEW_DIR_NAME
    left_filed: str = ""         # a working copy that was not the row's bytes, and stayed
    scan_note: str = ""          # why the re-scan did not land, when it did not


def unfile_document(
    engagement_dir: Path | str,
    original: str,
    note: str = "",
    *,
    today: dt.date | None = None,
    seq: int | None = None,
) -> UnfileResult:
    """Take one filed document back to ``REVIEW_DIR_NAME``, on the record.

    ``original`` names the index row the way :func:`assign_review_file` takes
    it: its PBC location, or failing that its original name among the rows
    the index says are ``FILED`` - whether a pass filed it or a person did.

    The working copy goes back under the client's own name, the name a parked
    copy has always had, and the row is rewritten ``NEEDS_REVIEW`` with no
    identifier, the reason attributed to a person and what the row said
    before kept after it. A page decision 94 filed under several requests
    has a copy in each and **every one of them leaves its place in Prepared**:
    one goes back to ``REVIEW_DIR_NAME`` under the client's name and the
    rest, being those same bytes again, stand down. Then the engagement is re-scanned, so the request
    the document was answering goes back to what it is without it, with the
    regression note that pass would have written; nothing else waits for the
    scheduled run to notice.

    This is the correction that had no home. A document the router filed
    under the wrong request, or a person filed in a hurry, was put right by
    dragging it in Explorer - which the index never learns, so it went on
    saying Filed at a path that holds nothing and the scan went on counting a
    file that had moved. The keyword a person taught the request when they
    filed it is *not* unlearned: it is a rule about documents, the request
    still wants it, and guessing which keyword to take back would be
    guessing. A person who wants one back says which, in the app's editor,
    where each taught word has its own button (decision 113,
    ``manifest.unlearn_keyword``); unfiling takes nothing back.
    Refiling is unfiling and then filing.

    A ``FILE_MOVED`` row comes back from here too - decision 110's "send
    it to review", for a copy that was moved by mistake and belongs under
    nothing in particular: the copy that goes back is then the wanderer the
    row's reason names, and a row whose bytes are nowhere under
    ``PREPARED_DIR_NAME`` is copied from the original, exactly as this
    already does for a row whose working copy is no longer its own. A page
    decision 94 filed under several requests is refused
    (``SEVERAL_COPIES_REFUSAL``) and put back with
    :func:`restore_working_copy` first.

    ``seq`` is the row's sequence number as the person saw it (decision
    112). A row somebody re-filed between the card being drawn and the
    click is a newer filing, and unfiling it would undo a decision this
    person never saw; the refusal names what the record now says and
    nothing is moved. A caller with no view passes none.

    The engagement lock is held for the move and the row, as everywhere else;
    the re-scan takes it again on its own, exactly as the app's filing does.
    Every copy this makes is proved against the bytes the row recorded
    before it is trusted (decision 109) - except on a row recorded without
    them (decision 65), which has no bytes to be proved against and is said
    out loud by the pass instead.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    review_dir = engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME

    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        _refuse_if_a_move_is_open(engagement_dir)
        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}
        position = find_filed(entries, original, accepting=(FILE_MOVED,))
        entry = entries[position]
        _refuse_if_stale(engagement_dir, entry, seq)
        if entry.decision == FILE_MOVED and entry.also_filed:
            # As for keep-it-here: which of a decision-94 page's copies is
            # meant is not guessable, and put-it-back answers for all of them.
            raise FilingError(SEVERAL_COPIES_REFUSAL.format(name=entry.original_name))
        source = locate(engagement_dir, entry.pbc_location)
        # Every working copy this row has: one, or one per request where
        # decision 94 filed the page under several. A copy is only this
        # row's while it is here, hydrated, not claimed by a later row,
        # and still the bytes the row recorded. Any other file at that
        # path is somebody else's document and is not carried back to
        # review under this row's name. The path check is the first copy's
        # (the index's own column is what a later row can take); for the
        # rest the bytes are the whole test, and they are the stronger one.
        taken = _copy_taken_by_a_later_row(entries, position)
        # Where to look, and which of those paths the index itself can say
        # is somebody else's. On a ``FILE_MOVED`` row (decision 110's "send
        # it to review") the copy that goes back is the wanderer, and it is
        # looked at first; a row whose bytes are nowhere has none, and the
        # copy comes from the original exactly as it does for any row whose
        # working copy is no longer its own.
        candidates: list[tuple[str, bool]] = [
            (location, index == 0) for index, location in enumerate(entry.filed_locations)
        ]
        if entry.decision == FILE_MOVED:
            now = moved_to(entry)
            if now:
                candidates.insert(0, (now, False))
        mine: list[Path] = []
        strangers: list[str] = []
        for location, is_the_named_copy in candidates:
            copy = locate(engagement_dir, location)
            if not _here(copy):
                continue
            if is_the_named_copy and taken:
                continue
            if entry.digest and sha256_of(copy) == entry.digest:
                mine.append(copy)
            else:
                strangers.append(location)
        working = mine[0] if mine else None
        still_the_rows = working is not None
        if not still_the_rows:
            # Nothing else can be parked but a copy of the original, so the
            # original has to be here before anything is moved or written.
            # A row whose copy and original are both gone (decision 157,
            # B5) is refused in the one sentence all three answers use.
            if both_gone(entry) and _the_original_now(engagement_dir, entry)[0] != _ORIGINAL_PROVED:
                raise FilingError(NOTHING_TO_PUT_BACK.format(
                    prepared=PREPARED_DIR_NAME, pbc=_shown(entry.pbc_location)))
            if not source.is_file():
                raise FilingError(
                    f"the working copy is not the one this row recorded and the original "
                    f"{_shown(entry.pbc_location)} is no longer there; there is nothing to put back"
                )
            if is_cloud_placeholder(source):
                raise FilingError(ORIGINAL_SYNCING.format(original=_shown(entry.pbc_location)))
            if entry.digest and _digest_or_none(source) != entry.digest:
                # Proved before the intent is written, not by the copy after
                # it: a copy of other bytes would fail half way through a
                # decision the record already holds (decision 157).
                raise FilingError(NOTHING_TO_PUT_BACK.format(
                    prepared=PREPARED_DIR_NAME, pbc=_shown(entry.pbc_location)))

        # Named as every review copy is, to fit (decision 131): no room
        # refuses with the review copy's sentence, and nothing has moved.
        parked, past_reader = _review_copy_path(review_dir, entry.original_name,
                                                room_root(engagement_dir))
        review_dir.mkdir(parents=True, exist_ok=True)
        left_filed = "; ".join(
            LEFT_FILED.format(location=location, parked=parked.name) for location in strangers
        )
        # A page decision 94 filed under several requests has a copy in
        # each, and every one of them has to leave Prepared or
        # the scan goes on counting the document this row no longer
        # claims. One goes back under the client's name; the rest are
        # these same bytes over again, and a copy is disposable - the
        # original in the year's folder is the record, and the copy that
        # went back is byte for byte the one removed here.
        stood_down: list[Path] = list(mine[1:]) if still_the_rows else []
        if still_the_rows:
            # The move keeps any notes a person made on the copy. (still_the_rows: working is a path.)
            ops = [_op(engagement_dir, ledger.OP_MOVE, cast(Path, working), parked, entry.digest)]
            ops += [_op(engagement_dir, ledger.OP_REMOVE, copy, digest=entry.digest)
                    for copy in stood_down]
        else:
            ops = [_op(engagement_dir, ledger.OP_COPY, source, parked, entry.digest)]

        new_entry = replace(
            entry,
            identifier="",
            prepared_location=prepared_location(review_dir, parked.name),
            decision=NEEDS_REVIEW,
            reason=(f"{UNFILED_BY_PERSON} on {today.isoformat()}{_said(note)}; was: {entry.reason}"
                    + (f"; {past_reader}" if past_reader else "")),
            also_filed="", answers="", code=reasons.UNFILED_BY_PERSON_CODE,
        )
        entries[position] = new_entry
        _intend(engagement_dir, ledger_key(new_entry), ops, by=ledger.BY_PERSON,
                row=entry_to_json(new_entry), then=ledger.UNFILED_BY_PERSON)
        _carry_out_a_persons_ops(engagement_dir, ledger_key(new_entry), ops)
        try:
            _record(engagement_dir, before, entries,
                    decided={ledger_key(new_entry): ledger.UNFILED_BY_PERSON})
        except BaseException:
            # The same rule as filing: leave the file where the record says
            # it is, so a retry does this once rather than twice.
            if not _the_record_holds(engagement_dir, new_entry):
                try:
                    if still_the_rows:        # working is a path
                        _move_whole(parked, cast(Path, working), within=engagement_dir)
                    else:
                        parked.unlink(missing_ok=True)
                    # The copies that stood down with it come back from the
                    # one that went back, which is them byte for byte.
                    for copy in stood_down:
                        _copy_whole(working or source, copy,
                                    expect=entry.digest or sha256_of(working or source),
                                    root=room_root(engagement_dir))
                except (OSError, FilingError) as undo:
                    errors.keep("filer", undo, name=parked.name)
                    log.error("Could not put a file back after the record refused it (%s)",
                              errors.error_class(undo))
                _abandon(engagement_dir, ledger_key(new_entry))
            raise

    # Outside the lock: the scan takes it for itself. A pass that slips in
    # between reads the rows this one has already recorded, so it sees the
    # document in review, as this scan will.
    return UnfileResult(
        entry=new_entry, moved_working_copy=still_the_rows, left_filed=left_filed,
        scan_note=_rescan(engagement_dir, today),
    )


@dataclass(frozen=True, slots=True)
class MarkedMissingResult:
    """What marking one answered request missing again did."""

    entry: IndexEntry            # the statement's row, rewritten
    identifier: str              # the request marked missing again
    scan_note: str = ""          # why the re-scan did not land, when it did not


def mark_missing_again(
    engagement_dir: Path | str,
    original: str,
    identifier: str,
    note: str = "",
    *,
    today: dt.date | None = None,
    seq: int | None = None,
) -> MarkedMissingResult:
    """Take one request off what a consolidated statement answers (decision
    146, the owner's answer to 146-Q: "a person can still mark it missing").

    ``original`` names the statement's row the way :func:`unfile_document`
    takes it, and ``identifier`` the request on its Also Answers cell that
    the statement does not in fact answer - a consolidated statement whose
    interest section lacks what the preparer needs, say. The row keeps its
    filing, its copy and every other answer; only that request comes off,
    and the Reason says who took it off and when. Nothing moves on disk,
    because nothing was ever copied for an answer.

    One ``answer_withdrawn_by_person`` line, a row event, so the store
    rebuilt from the journal and ``store check`` agree with the person.
    Then the re-scan, as unfiling does it, so the request reads what its
    own folder holds - Missing, most often, with the regression note that
    says it was Received - and the letter asks for it again from the next
    draft on. A request the row does not answer is refused by name, and so
    is a row somebody re-filed since the person saw it (``seq``, decision
    112).

    **A row's own request, on a row whose copy and original are both gone**
    (decision 157, ruling B6). The pass holds such a request for a person
    rather than asking the client (:func:`both_gone`); this is the person's
    answer. The row stays on the record with the person's sentence, and its
    claim on any working copy and every answer it gave come off
    (:func:`marked_missing`): it counts for nothing, holds nothing
    firm-side, leaves the client README, and the pass never makes it again
    or flags it again - so the request reads Missing and the letter asks.
    On any other row its own request is refused, as it always was. One
    ``answer_withdrawn_by_person`` line records it, the event decision 146
    gave a request taken off a row.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    wanted = identifier.strip()
    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        _refuse_if_a_move_is_open(engagement_dir)
        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}
        position = find_filed(entries, original, accepting=(FILE_MOVED,))
        entry = entries[position]
        _refuse_if_stale(engagement_dir, entry, seq)
        answered = entry.answered
        kept = [one for one in answered if identifier_key(one[0]) != identifier_key(wanted)]
        own = bool(entry.identifier) and identifier_key(wanted) == identifier_key(entry.identifier)
        if own and both_gone(entry):
            new_entry = replace(
                entry, prepared_location="", also_filed="", answers="",
                reason="; ".join(part for part in (entry.reason, MARKED_MISSING.format(
                    identifier=entry.identifier, date=today.isoformat(), note=_said(note))) if part),
            )
            wanted = entry.identifier
        elif len(kept) == len(answered):
            raise FilingError(f"{entry.original_name} does not answer {wanted}")
        else:
            new_entry = replace(
                entry,
                answers=format_answers(kept),
                reason="; ".join(part for part in (entry.reason, MARKED_MISSING.format(
                    identifier=wanted, date=today.isoformat(), note=_said(note))) if part),
            )
        entries[position] = new_entry
        _record(engagement_dir, before, entries,
                decided={ledger_key(new_entry): ledger.ANSWER_WITHDRAWN_BY_PERSON})
    return MarkedMissingResult(entry=new_entry, identifier=wanted,
                               scan_note=_rescan(engagement_dir, today))


def _rescan(engagement_dir: Path, today: dt.date) -> str:
    """Put the request's status back now, and say so if it could not be."""
    # The scan reads the index from tracker.index, never from this module,
    # and this module asks for the scan. The import stays inside the call, where
    # it has always been, and tests/test_layers.py holds it there.
    from tracker.scanner import ScanLockedError, scan_engagement

    try:
        scan_engagement(engagement_dir, today=today)
    except ScanLockedError as exc:
        return RESCAN_REFUSED.format(why=exc)
    return ""


def find_filed(
    entries: list[IndexEntry], original: str, *, accepting: Sequence[str] = ()
) -> int:
    """Index of the row ``original`` names; the newest ``FILED`` row wins a name.

    :func:`find_parked`'s shape over the other decision: what a person may
    unfile is what the index says is filed, whoever filed it. A row that is
    anything else names what it is in the refusal, because the answer to
    "this is in the wrong place" is different for each of them.
    ``accepting`` widens it exactly as it widens the other (decision 110):
    send-to-review passes ``FILE_MOVED``, because a copy nobody meant to
    move is a copy that may go back to review.

    Public since decision 112, beside :func:`find_parked`.
    """
    return _find_row(entries, original, (FILED, *accepting),
                     lambda entry: f"{entry.original_name} is not filed (it is {entry.decision})")



# --------------------------------------------------------------- recovery ----


#: What a put-back says when the wanderer itself went home. The row keeps
#: the history it had (109's sentence is taken off and this one appended in
#: its place), so what a person reads is where the copy is now and what it
#: was before it wandered.
PUT_BACK = "put back at {home} on {date} from {now}"
#: The same, for a row whose copy is nowhere in the firm's folder any more:
#: a working copy is a copy of the original, and the original is the record.
PUT_BACK_FROM_ORIGINAL = ("put back at {home} on {date} from the original {pbc}; "
                          "nothing under {prepared} held it")
#: The row when the bytes were already home. Nothing is moved and nothing
#: is deleted - the machine never deletes - so the wanderer stays where it
#: is and the sweep goes on naming it until a person removes it by hand.
PUT_BACK_ALREADY = ("already back at {home} on {date}; {now} holds the same bytes and was "
                    "left for a person to remove")
#: The owner's rule, 2026-09-19: nothing is overwritten. A file at home
#: that is not this document is somebody's - the sweep says every pass that
#: nothing on the record put it there - so it stays, this document's copy
#: goes to review under the client's own name, and the row parks naming
#: both, so a person answers it with File it or Not requested.
PUT_BACK_REFUSED = ("put back refused on {date}: {home} holds a different file, which was left; "
                    "this document's copy went to review as {parked}")
#: Why keep-it-here and send-to-review refuse a page decision 94 filed under
#: several requests: which of its copies the person means is not the
#: machine's to guess, and put-it-back answers for every one of them.
SEVERAL_COPIES_REFUSAL = "{name} has copies under several requests; put it back, then unfile it"
#: What adding a card's issuer row and filing under it refuses (decision
#: 201): a list changed since the card was drawn, a row no longer waiting
#: for an issuer, and a row that would not be read as an issuer row of the
#: row that accepted the K-1 - a return whose K-1 row is not the catalog's,
#: whose issuer rows a person copies in the editor. Each says that nothing
#: was added and nothing was filed.
ISSUER_LIST_MOVED = ("the request list changed since this card was drawn; no row was added and "
                     "nothing was filed - look at the card again")
NOT_AN_ISSUER_CARD = "{name} is no longer waiting for an issuer row; no row was added and nothing was filed"
ISSUER_DOES_NOT_NARROW = ("{identifier} would not be read as an issuer row of {listed} on this list, so no "
                          "row was added and nothing was filed; add it in Edit Request List")


@dataclass(frozen=True, slots=True)
class RestoreResult:
    """What putting one moved working copy back did."""

    entry: IndexEntry            # the rewritten index row
    moved_home: bool             # the wanderer itself was moved to the home path
    copied_from_original: bool   # nothing under Prepared/ held the bytes; the year's folder did
    already_home: bool           # home held the bytes; the wanderer was left alone
    parked_as: str = ""          # the refusal: where this document's copy went instead
    scan_note: str = ""          # why the re-scan did not land, when it did not


def find_moved(entries: list[IndexEntry], original: str) -> int:
    """Index of the row ``original`` names; the newest ``FILE_MOVED`` row wins.

    :func:`find_parked`'s shape over the decision the sweep writes. A row
    that is anything else names what it is in the refusal: put-it-back is an
    answer to "the copy is not where the record put it", and a row nobody
    said that about has nothing to put back.
    """
    return _find_row(entries, original, (FILE_MOVED,),
                     lambda entry: f"{entry.original_name} is not a moved copy (it is {entry.decision})")


def _gone_copies(engagement_dir: Path, entries: list[IndexEntry], position: int) -> list[str]:
    """The places this row names as its working copies that are simply gone
    and that no later row names instead (a later row's claim on a place is
    the newest, as everywhere else) - what Put it back makes again on a row
    that did not move (decision 157, ruling B8)."""
    entry = entries[position]
    later = {location for one in entries[position + 1:] for location in one.filed_locations}
    return [location for location in entry.filed_locations
            if location not in later and _absent(locate(engagement_dir, location))]


def _find_to_put_back(engagement_dir: Path, entries: list[IndexEntry], original: str) -> int:
    """:func:`find_moved`, widened by decision 157 (ruling B8): a Filed or
    parked row with a fingerprint one of whose own working copies is simply
    gone is Put it back's too. Anything else is refused exactly as
    :func:`find_moved` refuses it - a Filed row whose copy is where the
    record put it has nothing to put back."""
    try:
        return find_moved(entries, original)
    except FilingError:
        wanted = _wanted(original)
        for position in range(len(entries) - 1, -1, -1):
            entry = entries[position]
            if not _names_row(entry, original, wanted, recorded=False):
                continue
            if entry.decision == DUPLICATE and entry.original_name in (wanted, recorded_name(wanted)):
                continue
            if (entry.decision in (FILED, *_PARKED) and entry.digest
                    and _gone_copies(engagement_dir, entries, position)):
                return position
            break
        raise


def _make_a_gone_copy_again(
    engagement_dir: Path, entries: list[IndexEntry], before: dict[str, dict], position: int,
    stamp: str,
) -> RestoreResult:
    """Put it back on a Filed or parked row whose copy was deleted (decision
    157, ruling B8), under the lock :func:`restore_working_copy` holds: the
    copy made again from the proved original, through the pass's own
    :func:`_make_again`, with the pass's sentence and event, decided by the
    person. Refused before anything is written where the original cannot
    be copied from - still syncing, unreadable, or gone (naming both, as
    :data:`NOTHING_TO_PUT_BACK` does). A record that refuses the decision
    takes the copies back. Mutates ``entries``; the caller re-scans."""
    entry = entries[position]
    gone = _gone_copies(engagement_dir, entries, position)
    outcome, source = _the_original_now(engagement_dir, entry)
    if outcome == _ORIGINAL_GONE:
        raise FilingError(NOTHING_TO_PUT_BACK.format(prepared=PREPARED_DIR_NAME,
                                                     pbc=_shown(entry.pbc_location)))
    if outcome == _ORIGINAL_UNREAD:
        raise FilingError(f"the original {_shown(entry.pbc_location)} is still syncing or cannot be read "
                          "now; try again when it can")
    remade, _sentence = _remade(entry, gone, stamp)
    entries[position] = remade
    _make_again(engagement_dir, entry, remade, cast(Path, source), gone,   # proved: a path
                by=ledger.BY_PERSON, then=ledger.COPY_REMADE, cache=None)
    try:
        _record(engagement_dir, before, entries, decided={ledger_key(remade): ledger.COPY_REMADE})
    except BaseException:
        # The record took it or it did not: a copy it did not take is
        # removed by its bytes, so a retry makes it once.
        if not _the_record_holds(engagement_dir, remade):
            for location in gone:
                made = locate(engagement_dir, location)
                if _the_bytes(made) == entry.digest:
                    made.unlink(missing_ok=True)
            _abandon(engagement_dir, ledger_key(remade))
        raise
    return RestoreResult(entry=remade, moved_home=False, copied_from_original=True,
                         already_home=False)


def restore_working_copy(
    engagement_dir: Path | str,
    original: str,
    *,
    seq: int | None = None,
    today: dt.date | None = None,
) -> RestoreResult:
    """Put one moved working copy back where the record put it.

    The first of decision 110's three answers to a ``FILE_MOVED`` row, and
    the only one that needs no other place for the file to go: the bytes
    return to the path the row's Prepared Location names - the wanderer
    moved home when it still holds them, a fresh copy made from the
    client's original when nothing under ``PREPARED_DIR_NAME`` does - and
    the row goes back to what it was before it wandered, ``FILED`` when it
    names a request and ``NEEDS_REVIEW`` when it does not (109's rule for a
    copy dragged back by hand).

    Three things it will not do, each one the owner's, 2026-09-19:

    - **It never overwrites.** A file already at home that is *not* this
      document is somebody's, and it stays exactly where it is; this
      document's copy goes to ``REVIEW_DIR_NAME`` under the client's own
      name instead and the row parks naming both, so both files are on
      disk and a person decides with the card.
    - **It never deletes.** Where home already holds these bytes there is
      nothing to move: the row is restored and the wanderer is left, and
      the sweep goes on saying it is unrecorded until a person removes it.
    - **It never guesses.** ``seq`` is checked first (decision 112), every
      byte it is about to move is read second, and only then does anything
      move; a record that refuses the decision puts the file back.

    A page decision 94 filed under several requests has a copy in each, and
    every one of them is put back - which is why keep-it-here and
    send-to-review refuse such a row and point here.

    **And a copy that was simply deleted** (decision 157, ruling B8; the
    audit's D-3, which found this refusing "not a moved copy (it is
    Filed)"). A Filed or parked row one of whose own copies is gone is
    accepted too, and the copy is made again from the row's proved original
    through the very function the pass uses (:func:`_make_again`), with the
    same sentence (:data:`REMADE_SENTENCE`) and the same event
    (``ledger.COPY_REMADE``), decided by the person. A row whose copy and
    original are both gone is refused naming both
    (:data:`NOTHING_TO_PUT_BACK`); its one answer is Mark missing.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    stamp = today.isoformat()

    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        _refuse_if_a_move_is_open(engagement_dir)
        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}
        position = _find_to_put_back(engagement_dir, entries, original)
        entry = entries[position]
        _refuse_if_stale(engagement_dir, entry, seq)
        if not entry.digest:
            # Decision 65: a row preserved without its bytes is tied to
            # nothing, so there is nothing to prove a copy against and
            # nothing this may safely move. It is said out loud every pass.
            raise FilingError(
                f"{entry.original_name} was recorded without its bytes, so nothing can be proved "
                "to be its working copy; the pass says so every run"
            )
        if marked_missing(entry):
            raise FilingError(MARKED_REFUSAL.format(name=entry.original_name))
        if entry.decision == FILE_MOVED:
            done = _put_back_a_moved_copy(engagement_dir, entries, before, position, stamp)
        else:
            done = _make_a_gone_copy_again(engagement_dir, entries, before, position, stamp)

    # Outside the lock, as the unfiling's is: the request this row answers
    # has its file again (or has lost it to review), and the status says so
    # now rather than at the next scheduled pass.
    return replace(done, scan_note=_rescan(engagement_dir, today))


def _put_back_a_moved_copy(
    engagement_dir: Path, entries: list[IndexEntry], before: dict[str, dict], position: int,
    stamp: str,
) -> RestoreResult:
    """Decision 110's put-it-back of a ``FILE_MOVED`` row, under the lock
    :func:`restore_working_copy` holds: the wanderer home, a copy from the
    original, already home, or refused and parked. Mutates ``entries``
    and records the person's decision; the caller re-scans."""
    review_dir = engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    entry = entries[position]
    source = locate(engagement_dir, entry.pbc_location)
    now = moved_to(entry)
    wanderer = locate(engagement_dir, now) if now else None

    # Every location this row claims - one for nearly every row, one per
    # request for a page decision 94 filed under several - sorted into
    # what is already right, what is not there, and what is somebody
    # else's file. A placeholder is not read and not overwritten either:
    # the sync client has not finished, and the answer is to wait.
    absent: list[str] = []
    different: list[str] = []
    for location in entry.filed_locations:
        path = locate(engagement_dir, location)
        if not path.is_file():
            absent.append(location)
        elif is_cloud_placeholder(path):
            raise FilingError(COPY_SYNCING.format(location=location))
        elif sha256_of(path) != entry.digest:
            different.append(location)

    def the_original() -> Path:
        """The client's original, proved, or the refusal that names why."""
        looked = f"the copy at {now}" if now else f"nothing under {PREPARED_DIR_NAME}"
        if not now and _the_original_now(engagement_dir, entry)[0] == _ORIGINAL_GONE:
            # Nothing under the firm's folder and not the original either
            # (decision 157, B5): the one sentence, naming both.
            raise FilingError(NOTHING_TO_PUT_BACK.format(
                prepared=PREPARED_DIR_NAME, pbc=_shown(entry.pbc_location)))
        if not source.is_file():
            raise FilingError(
                f"{looked} holds this row's bytes and the original {_shown(entry.pbc_location)} is no "
                f"longer there; there is nothing to put back"
            )
        if is_cloud_placeholder(source):
            raise FilingError(ORIGINAL_SYNCING.format(original=_shown(entry.pbc_location)))
        if sha256_of(source) != entry.digest:
            raise FilingError(
                f"neither {looked} nor the original {_shown(entry.pbc_location)} holds the bytes this "
                "row recorded; look at the files first"
            )
        return source

    moved_home = copied_from_original = wanderer_moved = False
    parked: Path | None = None
    filled: list[Path] = []
    ops: list[ledger.IntentOp] = []
    if different:
        # Refused, and nothing is touched at home. This document's copy
        # goes to review under the client's own name - the wanderer
        # itself when it still holds the bytes, a fresh one from the
        # original when nothing does - so the person has a working copy
        # to act on and both files are still on disk.
        # Named as every review copy is, to fit (decision 131): no room
        # refuses with the review copy's sentence, nothing touched.
        parked, past_reader = _review_copy_path(review_dir, entry.original_name,
                                                room_root(engagement_dir))
        review_dir.mkdir(parents=True, exist_ok=True)
        if wanderer is not None and holds_the_row(wanderer, entry.digest):
            ops.append(_op(engagement_dir, ledger.OP_MOVE, wanderer, parked, entry.digest))
            wanderer_moved = True
        else:
            ops.append(_op(engagement_dir, ledger.OP_COPY, the_original(), parked,
                           entry.digest))
            copied_from_original = True
        sentence = PUT_BACK_REFUSED.format(
            date=stamp, home=different[0],
            parked=prepared_location(review_dir, parked.name))
        if past_reader:
            sentence = f"{sentence}; {past_reader}"
        new_entry = replace(
            entry, decision=NEEDS_REVIEW, identifier="", also_filed="", answers="",
            prepared_location=prepared_location(review_dir, parked.name),
            reason=f"{_without_moved_sentence(entry.reason)}; {sentence}",
            code=reasons.PUT_BACK_REFUSED_CODE,
        )
    elif not absent:
        # Already home: no file operation at all, and the wanderer -
        # a copy of the same document, by its bytes - is left for a
        # person to remove. A row that says its bytes are nowhere and
        # has them home again is the sweep's own sentence, worded once.
        sentence = (PUT_BACK_ALREADY.format(home=entry.prepared_location, date=stamp, now=now)
                    if now else MOVED_BACK_SENTENCE.format(
                        home=entry.prepared_location, date=stamp))
        new_entry = replace(
            entry, decision=FILED if entry.identifier else NEEDS_REVIEW,
            reason=f"{_without_moved_sentence(entry.reason)}; {sentence}",
        )
    else:
        home = locate(engagement_dir, absent[0])
        if wanderer is not None and holds_the_row(wanderer, entry.digest):
            ops.append(_op(engagement_dir, ledger.OP_MOVE, wanderer, home, entry.digest))
            moved_home = wanderer_moved = True
            sentence = PUT_BACK.format(home=absent[0], date=stamp, now=now)
        else:
            ops.append(_op(engagement_dir, ledger.OP_COPY, the_original(), home,
                           entry.digest))
            copied_from_original = True
            sentence = PUT_BACK_FROM_ORIGINAL.format(
                home=absent[0], date=stamp, pbc=_shown(entry.pbc_location),
                prepared=PREPARED_DIR_NAME)
        filled.append(home)
        # Decision 94's other copies, if this row has any: each is these
        # same bytes over again, and the one just put back is them - so
        # each is copied from it, in the order the intent says, and a
        # recovery that finishes this finds them in that order too.
        for location in absent[1:]:
            other = locate(engagement_dir, location)
            ops.append(_op(engagement_dir, ledger.OP_COPY, home, other, entry.digest))
            filled.append(other)
        new_entry = replace(
            entry, decision=FILED if entry.identifier else NEEDS_REVIEW,
            reason=f"{_without_moved_sentence(entry.reason)}; {sentence}",
        )

    entries[position] = new_entry
    _intend(engagement_dir, ledger_key(new_entry), ops, by=ledger.BY_PERSON,
            row=entry_to_json(new_entry), then=ledger.RESTORED_BY_PERSON)
    _carry_out_a_persons_ops(engagement_dir, ledger_key(new_entry), ops)
    try:
        _record(engagement_dir, before, entries,
                decided={ledger_key(new_entry): ledger.RESTORED_BY_PERSON})
    except BaseException:
        # The same rule as every other person's decision: the record
        # took it or it did not, so exactly what moved goes back and a
        # retry does this once rather than twice.
        if not _the_record_holds(engagement_dir, new_entry):
            try:
                # wanderer_moved is set only where the wanderer was a path that held the row.
                if parked is not None:
                    if wanderer_moved:
                        _move_whole(parked, cast(Path, wanderer), within=engagement_dir)
                    else:
                        parked.unlink(missing_ok=True)
                else:
                    for copy in filled[1:]:
                        copy.unlink(missing_ok=True)
                    if wanderer_moved and filled:
                        _move_whole(filled[0], cast(Path, wanderer), within=engagement_dir)
                    elif filled:
                        filled[0].unlink(missing_ok=True)
            except (OSError, FilingError) as undo:
                errors.keep("filer", undo, name=entry.original_name)
                log.error("Could not put a file back after the record refused it (%s)",
                          errors.error_class(undo))
            _abandon(engagement_dir, ledger_key(new_entry))
        raise
    return RestoreResult(
        entry=new_entry, moved_home=moved_home, copied_from_original=copied_from_original,
        already_home=not different and not absent,
        parked_as=prepared_location(review_dir, parked.name) if parked is not None else "",
    )


# ------------------------------------------------------------------ rename ----


def documents_by_request(engagement_dir: Path | str,
                         items: Sequence[RequestItem] | None = None) -> dict[str, int]:
    """How many filed documents each request holds, keyed without case
    (``records.identifier_key``): every Filed and File Moved row, once per
    request it satisfied - its own, and one per copy decision 94 filed
    under another - read as the client README reads them
    (:func:`_requests_of`).

    What a save of the list asks before it takes a request off the list or
    gives it another identifier (decision 160, the audit's D-7): the
    index, not the status, because the index is the record of what was
    filed and a status is only as fresh as the last scan.

    A request a consolidated statement answers through its Also Answers
    cell (decision 146) holds that statement too, once per statement, even
    with no copy of its own (SPEC-146 R-2): the client has sent it, so a
    save may not drop it - a person marks it missing again first. A row a
    person marked missing because its copy and its original were both gone
    holds nothing (decision 157): the client is being asked for it again.
    """
    folder = Path(engagement_dir)
    items = load_manifest(folder) if items is None else list(items)
    held: dict[str, int] = {}
    for entry in read_index(folder):
        if _counts_as_received(entry):
            for identifier in _requests_of(entry, items):
                if identifier:
                    key = identifier_key(identifier)
                    held[key] = held.get(key, 0) + 1
            for key in dict.fromkeys(identifier_key(one) for one, _sections in entry.answered):
                held[key] = held.get(key, 0) + 1
    return held


RENAME_CASE_ONLY = ("{old} and {new} differ only in case; change it in the list and save - "
                    "a change of case needs no rename")
RENAME_NOTHING = "Pick the request to rename and type its new identifier"
RENAME_COPY_TAKEN = "{location} is already there; move it or rename it first"
RENAME_COPY_MOVED = ("{name} is not where the record put it; put it back or send it to review "
                     "before renaming {old}")
RENAME_COPY_MISSING = ("{location} is not there, so it cannot move with {old}; the next pass says "
                       "where it went - rename after it")
RENAME_COPY_CHANGED = ("{location} no longer holds the file the record filed there; look at it "
                       "before renaming {old}")
RENAME_PATH_TOO_LONG = ("{location} would be {length} characters, past what Windows opens "
                        "({limit}); choose a shorter identifier")
#: What a rename says when the record took it and a file would not move
#: yet: the rename is the record's from its first write (decision 119's
#: intent), so it is finished forward - by the next pass - never undone.
RENAME_UNFINISHED = ("{old} is renamed {new} on the record, but {name} could not be moved yet "
                     "({problem}); the next pass finishes it (or press Run now)")


@dataclass(frozen=True, slots=True)
class RenameResult:
    """What one rename did: the two identifiers, how many working copies
    moved, how many index rows now name the new identifier, the files
    named for the old identifier left as they are because no row names
    them, the list's new version (``manifest.list_head``) and the re-scan's
    note."""

    old: str
    new: str
    moved: int
    rows: int
    left: tuple[str, ...]
    head: str
    scan_note: str


def _renamed(name: str, old: str, new: str) -> str:
    """``name`` with the request's identifier at its front given as ``new``,
    where it begins with ``old`` at a word boundary (the one shape a
    working copy is made in); otherwise as it is."""
    if not matches_identifier(name, old):
        return name
    rest = name.strip()[len(old.strip()):]
    return sanitize_component(new) + rest


def rename_request(
    engagement_dir: Path | str,
    old: str,
    new: str,
    *,
    head: object,
    today: dt.date | None = None,
) -> RenameResult:
    """Give a request another identifier, and move its documents with it.

    A save of the list may not take a request that holds documents off the
    list, and a respelt identifier is exactly that to a save: the old one
    removed, a new one added, the documents orphaned under a folder no
    request names and the letter and the README asking the client again
    (decision 160, the audit's D-7). This is the other way, and the only
    one: every working copy the record names whose name belongs to the
    request (directly in ``PREPARED_DIR_NAME``, by
    ``tracker.scaffold.owner_of`` - the rule ``assign_files`` applies)
    takes the new identifier at the front of its name, beside where it was,
    and every index row that names the request, or one of those copies,
    names the new one - in its Also Answers cell too, where a consolidated statement
    filed under another request answers this one (decision 146, SPEC-146
    R-1), so the answer and its sections carry and a killed rename finishes
    it from the row its intent holds.

    **One act, finished forward** (decision 119). Checked first, under the
    lock: no move open, the list the version the person's editor was
    opened on (``head``, decision 160's freshness check), the new
    identifier legal and free (the list's own validation), every copy that
    is to move there and holding the row's bytes, no destination taken and
    none past what Windows opens. Then one write carries the list renamed
    - with the keywords a filing taught it - and one intent per row that
    changes, so a run killed after it is finished by the next pass from
    the record, as any person's decision is; then the moves; then each
    row, recorded as :data:`tracker.ledger.RENAMED_BY_PERSON`, which closes
    its intent. A move that fails after the write is not undone: the
    record has decided, and the refusal says the next pass finishes it.

    A change of case only is refused: it is the same request everywhere
    (``records.identifier_key``), and the editor saves it. A row whose copy
    is not where the record put it (File Moved) is refused by name, as
    every other action on such a copy is. A file named for the request
    that no row names is left where it is and named in the result, never
    moved and never deleted.

    **No folder moves** (decision 168): a request has none, so there is
    nothing to rename and no emptied folder to take away - the copies are
    renamed in place, each one an ordinary move in the intent, and a run
    killed half way is finished by the next pass from those moves exactly
    as any interrupted filing is (:func:`_finish_interrupted_moves`),
    nothing lost and nothing doubled. An intent written before 168 names
    folder-shaped paths (``PREPARED_DIR_NAME/A01 - W-2/...`` to ``PREPARED_DIR_NAME/B01 -
    W-2/...``); it is finished as written, because the record decided it -
    the copy lands in the folder the intent names, which is then a
    person's folder of a return made before 168 (decision 168's ruling 10),
    and the emptied old folder stays, empty, until a person takes it away.
    A copy recorded in such a folder is never renamed by a rename made
    after 168: it is not in ``PREPARED_DIR_NAME`` itself, and its row
    takes the new identifier all the same.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    old = str(old or "").strip()
    new = str(new or "").strip()
    if not old or not new:
        raise FilingError(RENAME_NOTHING)
    if identifier_key(old) == identifier_key(new):
        raise FilingError(RENAME_CASE_ONLY.format(old=quoted(old), new=quoted(new)))
    # The new identifier is one a person typed, so it is held to the typing
    # limit (P291) before anything moves; the old one, however long the list
    # already holds it, is only ever renamed away from.
    if problem := typed_identifier_problem(new):
        raise FilingError(f"{COL_IDENTIFIER} '{quoted(new)}' {problem}")
    prepared = engagement_dir / PREPARED_DIR_NAME

    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        _refuse_if_a_move_is_open(engagement_dir)
        conn = store.connect()
        refuse_a_stale_list(conn, engagement_dir, head)
        list_events = renamed_rules(engagement_dir, old, new)
        items = load_manifest(engagement_dir)
        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}

        # Which copies are the request's is their names' to say (decision
        # 168): a copy directly in the firm's folder whose name belongs to
        # the old identifier - the longest that fits, so renaming A01 never
        # touches A01-B's - takes the new one at its front, beside where it
        # is. Asked of the name, not of the disk, so a copy the record put
        # there that has gone is refused below rather than passed over.
        identifiers = [item.identifier for item in items]

        def belongs_to_old(path: Path) -> bool:
            owner = owner_of(path.name, identifiers)
            return path.parent == prepared and owner is not None \
                and identifier_key(owner) == identifier_key(old)

        def moved_to_new(location: str) -> str | None:
            path = locate(engagement_dir, location)
            if not belongs_to_old(path):
                return None
            return location_of(engagement_dir, prepared / _renamed(path.name, old, new))

        # Every file named for the request now, recorded or not - what is
        # not moved below is named in the result.
        spelled = next((one for one in identifiers if identifier_key(one) == identifier_key(old)), old)
        owned = [location_of(engagement_dir, path)
                 for path in assign_files(prepared, identifiers).get(spelled, [])]

        renamed_entries: list[IndexEntry] = []
        ops_for: dict[str, list[ledger.IntentOp]] = {}
        destinations: set[str] = set()
        for position, entry in enumerate(entries):
            locations = entry.filed_locations
            asked = {location: moved_to_new(location) for location in locations}
            mapped = {was: now for was, now in asked.items() if now}
            names_it = bool(entry.identifier) and identifier_key(entry.identifier) == identifier_key(old)
            candidates = [new if identifier_key(one) == identifier_key(old) else one
                          for one in entry.candidate_list]
            evidence = entry.evidence
            record = entry.evidence_record
            if any(identifier_key(one) == identifier_key(old) for one in record) \
                    and format_evidence(record) == entry.evidence:
                evidence = format_evidence({new if identifier_key(one) == identifier_key(old) else one: found
                                            for one, found in record.items()})
            # The Also Answers cell names the request too (decision 146 over
            # 160, SPEC-146 R-1): a consolidated statement filed under another
            # request that answers this one answers it under its new name,
            # each answer keeping its sections - or the request reads Missing
            # again and the letter asks for what the client already sent.
            answered = entry.answered
            answers = entry.answers
            if any(identifier_key(one) == identifier_key(old) for one, _sections in answered):
                answers = format_answers([(new if identifier_key(one) == identifier_key(old) else one,
                                           sections) for one, sections in answered])
            if not (mapped or names_it or candidates != entry.candidate_list
                    or evidence != entry.evidence or answers != entry.answers):
                continue
            if mapped and entry.decision == FILE_MOVED:
                raise FilingError(RENAME_COPY_MOVED.format(name=entry.original_name, old=old))
            ops: list[ledger.IntentOp] = []
            for was, now in mapped.items():
                source, target = locate(engagement_dir, was), locate(engagement_dir, now)
                if not source.is_file():
                    raise FilingError(RENAME_COPY_MISSING.format(location=was, old=old))
                if is_cloud_placeholder(source):
                    raise FilingError(COPY_SYNCING.format(location=was))
                if entry.digest and sha256_of(source) != entry.digest:
                    raise FilingError(RENAME_COPY_CHANGED.format(location=was, old=old))
                if target.exists() or now.casefold() in destinations:
                    raise FilingError(RENAME_COPY_TAKEN.format(location=now))
                length = measured_length(target, room_root(engagement_dir))
                if length > path_limit():
                    raise FilingError(RENAME_PATH_TOO_LONG.format(
                        location=now, length=length, limit=path_limit()))
                destinations.add(now.casefold())
                ops.append(_op(engagement_dir, ledger.OP_MOVE, source, target, entry.digest))
            now_locations = [mapped.get(location, location) for location in locations]
            renamed = replace(
                entry,
                identifier=new if names_it else entry.identifier,
                prepared_location=now_locations[0] if now_locations else entry.prepared_location,
                also_filed=CANDIDATE_SEP.join(now_locations[1:]) if mapped else entry.also_filed,
                candidates=CANDIDATE_SEP.join(candidates) if candidates != entry.candidate_list
                else entry.candidates,
                evidence=evidence,
                answers=answers,
            )
            entries[position] = renamed
            renamed_entries.append(renamed)
            ops_for[ledger_key(renamed)] = ops

        # One write: the list renamed and every row's intent. The intents
        # are written whole here rather than through _intend(), because a
        # row whose only change is the identifier it names has nothing to
        # move and still has to be finished with the rest.
        intents = []
        for renamed in renamed_entries:
            key = ledger_key(renamed)
            intents.append(ledger.new(ledger.MOVING, **{
                ledger.KEY_KEY: key, ledger.OPS_KEY: ops_for[key], ledger.DECIDED_BY_KEY: ledger.BY_PERSON,
                ledger.ROW_KEY: entry_to_json(renamed), ledger.EVENT_KEY_AFTER: ledger.RENAMED_BY_PERSON,
            }))
        store.record(conn, engagement_dir, *list_events, *intents)

        moved = 0
        for renamed in renamed_entries:
            for op in ops_for[ledger_key(renamed)]:
                try:
                    _do_op(engagement_dir, op)
                except (OSError, FilingError) as exc:
                    raise FilingError(RENAME_UNFINISHED.format(
                        old=old, new=new, name=Path(op[ledger.FROM_KEY]).name,
                        problem=errors.said(exc, FIRM_WRITTEN))) from exc
                moved += 1
        _record(engagement_dir, before, entries,
                decided={ledger_key(one): ledger.RENAMED_BY_PERSON for one in renamed_entries})

        # A file named for the old identifier that no row names stays as it
        # is, and is named: it is somebody's, and nothing proves whose.
        moving = {op[ledger.FROM_KEY].casefold() for ops in ops_for.values() for op in ops}
        left = [location for location in owned if location.casefold() not in moving]
        now_head = list_head(engagement_dir)
        rows = sum(1 for entry in entries
                   if entry.identifier and identifier_key(entry.identifier) == identifier_key(new))

    return RenameResult(old=old, new=new, moved=moved, rows=rows, left=tuple(left),
                        head=now_head, scan_note=_rescan(engagement_dir, today))
