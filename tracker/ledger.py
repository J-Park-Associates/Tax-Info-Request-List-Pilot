"""The machine's own record of one engagement, appended to and never rewritten.

Every fact the system holds about an engagement used to live in a workbook a
person can open, sort, re-type and save from Excel - and each of the readings
in the decision log found another way that ends with a row lost. Each
engagement now keeps ``LEDGER_FILENAME`` instead, one JSON object per line,
in the order the writers wrote them. It is the record of *what was decided*.

**It is the index** (decision 102). What a pass decides about a document is
appended here and folded into :mod:`tracker.store`, and
:func:`tracker.filer.read_index` answers from those folded rows. The
journal and the store are the only two copies of the index, and the store
is rebuilt from the journal. (A journal from before decision 104 may carry
a :data:`MIGRATED` event, from the one-time migration of an index
workbook; nothing writes one now.)

**It is the statuses too** (decision 103). A scan appends one
:data:`SCANNED` event with what it changed, a person's filing appends
:data:`KEYWORD_LEARNED` beside the row it taught, and
:func:`tracker.manifest.load_manifest` answers from the store these lines
are folded into. A word that seemed distinctive and was not is taken back
in the app's editor as one :data:`KEYWORD_UNLEARNED` (decision 113), and
both folds - this module's and the store's - read the pair the same way,
so the check can hold one to the other.

**And it is the week's reminder** (decision 115). The pass appends one
:data:`DRAFTED` event saying which requests the draft asked for, or which
held the whole draft back for a person, and which file it wrote - when
that differs from the last one - so ``tracker.runner.last_drafted()`` reads
the day of the draft from the record rather than from a file time a sync
client may have set, and the next draft can say what changed since it. A
person who reads that draft in the app and approves it appends one
:data:`DRAFT_APPROVED` beside it (decision 118), and for the rest of that
draft week the pass leaves the file it names exactly as it leaves one
somebody edited. Neither line carries a word of the letter.

**And it is the person's own rules** (decisions 103 and 104). The request
list and the engagement's details are created, edited and read only here:
the app's editor is the one way a rule is entered, and every save is one
:data:`RULES_CHANGED` event carrying exactly the difference - the changed
and added rows whole, the removed identifiers, the Engagement fields that
moved. That is what makes the store rebuildable from the journals alone -
without it, an engagement's rules would live only in a database that is
meant to be disposable. Until decision 104 the list was a workbook read
once a pass and its differences were journalled as :data:`RULES_IMPORTED`;
that name is retired (:data:`RETIRED_EVENTS`): this version folds it,
because journals from before today carry it, and refuses to write it.

**And it is what a decision is about to do** (decision 119). A pass or a
person that is about to move a file appends one :data:`MOVING` line first -
the operations in order with the bytes each expects, the row the decision
will record and the event that will complete it - so a run killed between
the disk and the record leaves the *intent* behind rather than a folder
nobody can explain. The row event that follows completes it; both folds
here and in :mod:`tracker.store` keep the same set of open intents, and
the next pass finishes them from the record before it looks at anything.

**And it is the household's own details** (decision 125). A household is a
folder in the private tree with a journal of its own, holding
:data:`HOUSEHOLD_CHANGED` lines - its name, the members a person typed as
who the folder is meant to be shared with, the contact the letters greet
and the inbox link they paste. It is the same machinery a return's journal
uses, folded by the same functions and rebuilt by the same store, because
one journal machinery for the two is one thing to keep honest instead of
two. Nothing about a document goes in it, and no client's text ever does.

What keeps it honest is the agreement fixture in ``tests/conftest.py``:
after every test in the suite a store built from nothing is held to
:func:`replay` over these lines - the index rows, the statuses and the
rules alike. ``python -m tracker.store <store> check <root>`` is that check
for one practice, for a person.

**Append-only, one line per event.** A line is written with a single
``os.write`` under ``O_APPEND`` and then ``fsync``-ed, so a run killed
mid-append leaves at most a torn last line - bytes with no newline after
them. :func:`read_events` ignores such a tail and the next :func:`append`
truncates it first. Nothing else ever rewrites the file. A record's own JSON
never contains a newline (``json.dumps`` escapes them), so an unterminated
tail is the only shape a torn write can take. A tail that is one whole
event is not torn - a sync client or an editor dropped only its newline -
and is read as a line, and the next append gives it its newline back
(decision 159).

**Every line carries its link, its host and its format** (decision 159).
:func:`append` writes three keys of its own beside the caller's event:
:data:`LINK_KEY`, the applied chain through every line before it (the
number the store already keeps as ``applied_digest``, computed by
:func:`chain_link` and nowhere else); :data:`HOST_KEY`, the machine that
wrote it (``locking.this_host()``); and :data:`FORMAT_KEY`,
:data:`RECORD_FORMAT`. Every reader checks them while it parses
(:func:`_parse_lines`): a line whose link is not the chain before it was
reordered, cut or edited; a line with no link after one that has it was
written by an older version or by hand; a line of a newer format is not
read rather than misread. Each is
refused by name - its class and line, never the parser's own text - ending
with :data:`RUN_RECOVER`, and a record refused is that return's problem,
never the practice's. The link detects accidents; a rewrite that
recomputes it is :mod:`tracker.checkpoint`'s to catch. Lines from before 159 carry
no link and are read as they always were; the first linked line's link
covers all of them. What the link cannot tell - whether the record is the
one *this machine* wrote - is :mod:`tracker.checkpoint`'s.

**The chain here, the values at the gate** (decision 159 carried onto
decision 187). What this reader checks is what only the chain can say:
the link, a line without one after a linked one, a newer format. What the
three keys and a line's time *hold* - a link blank or a digest, a format
this version writes, a writer that is a machine's name
(``records.host_problem``), a time as :func:`stamp` writes it
(``records.stamp_problem``) - is a value like every other value a line
carries, and is held to its rule in one place: the store's admission
(``store._refuse_a_malformed_line``), which :func:`tracker.store.record`
runs on each line exactly as :func:`line_of` will write it, and every
catch-up, check and verify runs on every line read in. A reader that
shows a writer or a time without the store (the view's Summary) asks the
same two rules first.

**Written only under the engagement lock.** ``O_APPEND`` is atomic for
concurrent writers on POSIX and is *not* on Windows, where two appends can
interleave; the writer holds the engagement lock (:mod:`tracker.locking`),
which already forbids two runs on one engagement, so there is one writer and
one protocol rather than two. :func:`append` refuses when this process does
not hold it, because a silent append outside the lock is exactly the row that
goes missing later.

**Not a database, here.** SQLite was the obvious answer and is the wrong
one *in the engagement folder*: the folders are synced by a cloud client
between the office machine and the drive, and a synced database file is a
corrupted database file. A text file that only ever grows is what a sync
client can carry. Decision 101 adds the database the other side of that
line - :mod:`tracker.store`, one file per clients root on the designated
machine's own disk, never synced and never in a folder - and it is built
*from* this file: the journal is what is written first and what survives,
the store is what is rebuilt. Together they are the record; this file
alone is the ledger.

**Plain dicts, and no imports above this module.** The events are dicts of
JSON values, so this module sits at the bottom beside :mod:`tracker.locking`
and imports nothing else of the package: every writer serialises its own
rows with the function in :mod:`tracker.records` that already owns that
shape (an index row, a status, a rule row, the engagement's details). One
owner per fact, and no cycle.
"""

from __future__ import annotations

import datetime as dt
import errno
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from tracker.locking import (
    BREAKER_CLEARED_INFIX,
    BREAKER_STALE_SECONDS,
    BREAKER_SUFFIX,
    LOCK_FILENAME,
    lock_is_held,
    this_host,
)

log = logging.getLogger("tracker.ledger")

#: The engagement's own record, beside the client's files. A person never edits it.
LEDGER_FILENAME = "_ledger.jsonl"

#: Keys every event carries.
EVENT_KEY = "event"
AT_KEY = "at"
#: Keys an index-shaped event carries: the identity the row is recorded under,
#: the whole row as the index's own sidecar serialises it, and - when the
#: client moved the original and the row followed it - the identity the row
#: is leaving, so the fold does not keep the vacated one for ever.
KEY_KEY = "key"
ROW_KEY = "row"
WAS_KEY = "was"
#: What a ``SCANNED`` event carries: identifier -> the scanner columns applied.
STATUSES_KEY = "statuses"
#: What a ``KEYWORD_LEARNED`` event carries, and a ``KEYWORD_UNLEARNED``
#: with it: the request a person's filing taught, and the word it was
#: taught - the same two keys, because taking a word back names exactly
#: what teaching it named. Named here beside the other event keys so the
#: writer and every reader of the record spell them once.
IDENTIFIER_KEY = "identifier"
KEYWORD_KEY = "keyword"
#: What a ``MOVING`` event carries besides ``KEY_KEY`` and ``ROW_KEY``
#: (decision 119). ``OPS_KEY`` is the file operations the decision is about
#: to make, in order, each ``{OP_KEY: "move"|"copy"|"remove", FROM_KEY: …,
#: TO_KEY: …, DIGEST_KEY: …}`` with paths relative to the engagement folder,
#: POSIX, and the digest the bytes are expected to have (a ``remove`` has no
#: ``TO_KEY``). ``EVENT_KEY_AFTER`` names the row event that will complete
#: the decision and ``DECIDED_BY_KEY`` says who decided it, so a recovered
#: person's filing is still recorded as theirs. ``ALSO_KEY`` carries the
#: events that travel with the row - today the one keyword a person's
#: filing teaches - whole, as they would have been written.
#: Nothing an intent carries is ever written into **another** return's
#: record (decision 132): a decision that touches two records is two
#: intents, one in each, each finished by its own household's pass. The
#: key decision 129 wrote the other record's half under is refused by
#: name (``tracker.store.ALSO_IN``) wherever it is met.
OPS_KEY = "ops"
OP_KEY = "op"
FROM_KEY = "from"
TO_KEY = "to"
DIGEST_KEY = "digest"
EVENT_KEY_AFTER = "then"
DECIDED_BY_KEY = "by"
ALSO_KEY = "also"
#: What a :data:`RELEASED` line carries besides its key, and what the
#: release intent that it closes carries for it (decision 132): which
#: return took the document and under which request, in the person's
#: words, so a release finished by a recovery says what the click said.
REASON_KEY = "reason"
#: The three operations an intent can carry.
OP_MOVE = "move"
OP_COPY = "copy"
OP_REMOVE = "remove"
#: What :data:`DECIDED_BY_KEY` says: a pass decided it, or a person did.
BY_PASS = "pass"
BY_PERSON = "person"

#: What a ``RULES_CHANGED`` event carries. The rows are whole records -
#: every one that was added or changed, as ``tracker.records.rule_to_json``
#: serialises it - rather than a patch, because a patch cannot be read
#: without the row it patches and the whole point of the journal is that a
#: line means something on its own. ``REMOVED_KEY`` is the identifiers the
#: person removed from the list, ``INFO_KEY`` the Engagement fields that
#: changed (``tracker.records.info_to_json``'s names). A retired
#: ``RULES_IMPORTED`` line carries the same three and a workbook digest
#: under a fourth key, which is simply not read.
RULES_KEY = "rules"
REMOVED_KEY = "removed"
INFO_KEY = "info"

#: A person's word that a household or a return is now called by its
#: folder's name (decision 188): carried on the ``HOUSEHOLD_CHANGED`` and
#: ``RULES_CHANGED`` lines the app's *Accept the folder's name* writes,
#: with the one value :data:`FOLDER_NAME_ACCEPTED`, and dated by the
#: line's own stamp. The store admits the key on those two events with
#: that value and no other; the pass never writes it.
ACCEPTED_KEY = "accepted"
FOLDER_NAME_ACCEPTED = "folder_name"

#: What a ``HOUSEHOLD_CHANGED`` event carries: the household fields that
#: moved, as ``tracker.records.household_to_json`` names them. The same
#: shape ``RULES_CHANGED`` carries its details in, because it is the same
#: kind of fact - the first one, written when the household is made,
#: carries the whole of it and every one after it only what moved, so the
#: fold of them all is the household.
HOUSEHOLD_KEY = "household"

#: One original was preserved and its record says where it now is. A pass
#: that sorts a drop decides and preserves in one row, so it appends one of
#: the three decisions below instead; this is what a row gets when the client
#: renamed or moved an original inside the folder they can see and the row
#: followed the bytes.
PRESERVED = "preserved"
#: A drop was filed against exactly one request.
FILED = "filed"
#: A drop nothing could be sure of is waiting for a person.
PARKED = "parked"
#: A drop whose bytes were already recorded under another row.
DUPLICATE = "duplicate"
#: An email or a zip was opened and each attachment taken out as a
#: document of its own (decision 143). The row is the container's - it
#: belongs to no request - and the line carries, besides it, what was taken
#: out (:data:`ATTACHMENTS_KEY`: each one's name, size and fingerprint) and
#: what was skipped and why (:data:`SKIPPED_KEY`). Those two travel in the
#: journal only: the fold keeps the row, as for every row event, and the
#: attachments are rows of their own that name the container.
OPENED = "opened"
ATTACHMENTS_KEY = "attachments"
SKIPPED_KEY = "skipped"
#: A person filed a parked document under a request.
ASSIGNED_BY_PERSON = "assigned_by_person"
#: A person said no request asks for a parked document.
DISMISSED_BY_PERSON = "dismissed_by_person"
#: A person sent a filed document back for review.
UNFILED_BY_PERSON = "unfiled_by_person"
#: A person filed a parked document under a return in another record, and
#: the row here is **released** (decision 132): it leaves the index, and
#: this line - ``{event, key, reason}``, no row, the shape
#: :data:`MOVE_ABANDONED` has - says which return took it and under which
#: request (:data:`REASON_KEY`). The owner's sentence is that the dropping
#: household keeps no copy and no row; the journal keeps the line, and
#: the record holds nothing about a document that rests elsewhere. It
#: closes the release intent under the same key. **Not a row event**: a
#: reader that folded it as one would look for a row that is not there.
RELEASED = "released"
#: What decision 129 wrote when a person handed a parked document to a
#: return this drop folder feeds: a terminal row kept here about a
#: document that had moved elsewhere. **Retired by decision 132**: read
#: once - folded as a :data:`RELEASED` of its key, because that is what the
#: built row meant - and never written again.
HANDED_OVER_BY_PERSON_EVENT = "handed_over_by_person"
#: A person put a working copy the record had lost track of back where the
#: record put it (decision 110). One name for the whole of that answer,
#: whatever the click found: the bytes moved home, or were copied home from
#: the client's original, or were already home, or a different file at home
#: was refused an overwrite and this document's copy went to review. The row
#: the line carries says which, and three names for one button would be a
#: vocabulary of outcomes the row already states. The pass's own
#: :data:`COPY_MOVED` stays what it is - the machine noticing - and this is
#: the person answering.
RESTORED_BY_PERSON = "restored_by_person"
#: A person gave a request another identifier with the rename action, and
#: the row names it by its new one (decision 160): the working copies it
#: holds under the request moved into the request's renamed folder under
#: renamed names, or - for a row with no copy there, a duplicate of one -
#: only the identifier it names changed. The ``rules_changed`` that renames
#: the request and one :data:`MOVING` intent per row are written first, in
#: one write, and each of these closes one intent; so a rename a run was
#: killed in the middle of is finished by the next pass like any other
#: person's decision, and recorded as this.
RENAMED_BY_PERSON = "renamed_by_person"
#: A person marked a request missing again that a consolidated statement
#: filed under another request was answering without a copy (decision 146,
#: the owner's answer to 146-Q). The row the line carries is the
#: statement's, with that request taken off its Also Answers cell and the
#: person's sentence on its Reason; nothing moves on disk. A row event, so
#: a store rebuilt from the journal and ``store check`` both hold the
#: statement to what the person said. Since decision 157 the same line
#: says a person marked a row's **own** request missing, on a row whose
#: working copy and original are both gone: the row it carries names no
#: working copy and answers nothing any more, so it stops counting and the
#: next letter asks the client for the document.
ANSWER_WITHDRAWN_BY_PERSON = "answer_withdrawn_by_person"
#: A row preserved without its bytes was tied to them by a later pass.
BYTES_RECORDED = "bytes_recorded"
#: The pass found this row's working copy somewhere other than where the
#: record last said - away from where it was filed, away again, or back
#: where it belongs (decision 109). One name in either direction: the row
#: the event carries says which way it went, the fold is the same fold
#: whichever it is, and a reader of the journal wants the whereabouts of a
#: copy said once rather than a vocabulary of drags. Nothing was moved to
#: learn it and nothing is moved because of it.
COPY_MOVED = "copy_moved"
#: A working copy that had gone from where the record put it, whose bytes
#: were nowhere else in the firm's folder, was made again from the row's
#: own original, proved against the row's fingerprint (decision 157). The
#: pass writes it, and so does a person's Put it back on a deleted copy -
#: the same function, the same sentence on the row - with a ``moving``
#: intent before the copy, like every other decision that touches a file.
#: The client is never asked for a document the firm can make again.
COPY_REMADE = "copy_remade"
#: A drop in the inbox was a row's own original coming back - its bytes,
#: the one row whose recorded original was no longer where the row said -
#: and it was moved back to that exact place (decision 157). No new row is
#: written: this line carries the row it went home to, with one sentence
#: added, and closes the ``moving`` intent the move was written down in.
ORIGINAL_RETURNED = "original_returned"
#: The statuses one scan applied. Appended only when something changed, so a
#: quiet pass appends nothing at all.
SCANNED = "scanned"
#: A person's filing taught a request a keyword.
KEYWORD_LEARNED = "keyword_learned"
#: A person took one of those keywords back, in the app's editor (decision
#: 113). A word that seemed distinctive and was not - a common word on many
#: unrelated documents - is untaught the way it was taught, by an event, so
#: a store rebuilt from these lines agrees and the record says who took it
#: back and when. Per engagement: the firm-wide vocabulary is
#: ``tracker.templates`` and changes only by a commit. Unfiling still
#: unlearns nothing (decision 77) - the request still wants the word.
KEYWORD_UNLEARNED = "keyword_unlearned"
#: The person's request list or Engagement details were edited in the app
#: (decision 104): the changed and added rows whole (``RULES_KEY``), the
#: removed identifiers (``REMOVED_KEY``), the Engagement fields that moved
#: (``INFO_KEY``). The first one - the create - carries the whole list and
#: every field, every one after it only what moved, so the fold of them
#: all is the list. Written by ``tracker.manifest.create_engagement``,
#: ``save_rules`` and the rename (``renamed_rules``, decision 160), by a
#: filing that teaches a spelling (decision 128) or adds its issuer row
#: (decision 201) in ``tracker.filer.assign_review_file``, and by the API's
#: *Accept the folder's name* (decision 188) - and by nothing else.
RULES_CHANGED = "rules_changed"
#: The household's own details were recorded or edited (decision 125): its
#: name, the members a person typed as who the folder is meant to be
#: shared with, the contact the letters greet and the inbox link they
#: paste, under :data:`HOUSEHOLD_KEY`. Written into the household's
#: journal, in the private tree, by ``tracker.households.create_household``
#: and ``save_household`` - and, carrying only the name and
#: :data:`ACCEPTED_KEY`, by the API's *Accept the folder's name* (decision
#: 188) - and by nothing else. Not a row event: it carries
#: no index row and says nothing about a document.
HOUSEHOLD_CHANGED = "household_changed"
#: The firm says it has shared this household's folders with the client
#: (decision 126). Written into the household's journal by
#: ``tracker.api``'s ``mark-shared`` command and by nothing else, when a
#: person presses *Mark as shared*. **Folded by nothing**, exactly as
#: :data:`DRAFT_APPROVED` is: it is the firm's own dated word, not a field
#: of the household and not a row of any index, and it is read back by
#: name out of the events (``tracker.households.shared_on``). It carries
#: nothing at all but the stamp - no member list, no link, not one word a
#: client would read - because the tracker cannot see Drive's sharing and
#: must not pretend to have recorded what it cannot check.
SHARING_CONFIRMED = "sharing_confirmed"
#: What decision 103 called the same event, when the list was a workbook
#: read once a pass. Retired by decision 104: journals from before it
#: carry these lines, so :func:`apply` folds them exactly as
#: ``RULES_CHANGED``, and :func:`new`, :func:`append` and
#: ``tracker.store.record`` refuse to write one.
RULES_IMPORTED = "rules_imported"
#: The week's reminder was decided (decision 115). Reserved since decision
#: 87 because the reminder wrote files and held no lock; written since 115
#: by the pass, under the lock it has held across the whole pass since
#: decision 102, and by ``python -m tracker.reminder --write`` under a lock
#: it takes. It carries identifiers and nothing a client would read: the
#: requests the draft asked for (:data:`ASKED_KEY`, in the draft's order,
#: ``[]`` on a quiet week), or the requests that held the whole draft back
#: for a person (:data:`HELD_KEY`, present only on a hold), and - when a file
#: was written - which draft file (:data:`FILE_KEY`) and the fingerprint in
#: its header (:data:`FINGERPRINT_KEY`). Appended only when something moved:
#: a repeat on the draft day that finds the engagement as the last draft
#: left it appends nothing (the ``scanned`` rule).
DRAFTED = "drafted"
ASKED_KEY = "asked"
HELD_KEY = "held"
FILE_KEY = "file"
FINGERPRINT_KEY = "fingerprint"
#: The key a :data:`DRAFTED` or :data:`DRAFT_APPROVED` line carries the
#: stage under: a number, never a word of the letter. Here since decision
#: 187, beside the event it belongs to, so the store's gate can bound it
#: without reaching up to the reminder; ``tracker.reminder`` re-exports it.
STAGE_KEY = "stage"
#: The fingerprint of the letter a person approved, as they read it
#: (decision 190): carried by :data:`DRAFT_APPROVED` alone, so an edit made
#: after the approval lapses it. A hash - no word of the letter.
TEXT_FINGERPRINT_KEY = "text_fingerprint"
#: A person read the week's draft in the app and approved it (decision
#: 118). Folded by nothing, exactly as :data:`DRAFTED` is: it is a fact
#: about a week, not a row of the index. It carries the same four keys a
#: written draft does - the stage (:data:`STAGE_KEY`), the
#: file, the fingerprint in that file's header and the identifiers asked -
#: and the fingerprint of the letter approved (:data:`TEXT_FINGERPRINT_KEY`,
#: decision 190), and, like every event here, not one word a client would read. Until the
#: next draft day the pass treats the file it names as it treats one a
#: person edited: never overwritten, a regenerated draft beside it.
DRAFT_APPROVED = "draft_approved"
#: What one decision is about to do to the disk, written before the first
#: file operation (decision 119). **The intent is the decision.** The disk
#: and the record are two things, and a run killed between them used to
#: leave the disk ahead: a person's filing that had moved its copy and not
#: yet recorded it was finished only by another person, and a copy that
#: stopped half way was counted as the document. So the operations are
#: written down first - what will move where and which bytes each step
#: expects (:data:`OPS_KEY`), the row the decision will record
#: (:data:`ROW_KEY`), the event that will complete it
#: (:data:`EVENT_KEY_AFTER`) and who decided (:data:`DECIDED_BY_KEY`) -
#: keyed by the row's own identity, and the next pass finishes from the
#: record what the fingerprints say is still undone.
#:
#: **Not a row event**: it carries what a row *will* say, not what it
#: says, so folding it as one would put a row in the index that no
#: decision has been taken on yet. It folds into ``Folded.intents``
#: instead, and the row event that names its key closes it.
MOVING = "moving"
#: An intent the record refused (decision 119). The rollback on a refused
#: record puts the files back, and this says so, so the next pass does not
#: finish forward a move the record would not take. ``KEY_KEY`` only: the
#: intent it closes is named, and nothing else about it is a fact.
MOVE_ABANDONED = "move_abandoned"
#: A row seeded into the record from an earlier reading of the index: the
#: bootstrap of decision 87 and the migration of decision 102 wrote these,
#: and the suite's ``seed_index`` still does.
IMPORTED = "imported"
#: The index workbook was moved aside, and this engagement's index now lives
#: in the record alone (decision 102). Written once per engagement, after the
#: rename. It carries no row, so it is
#: deliberately *not* a row event: a reader that folded it as one would
#: look for a row that was never there. Nothing writes one since decision
#: 104 took the migration out of the tree; it stays readable.
MIGRATED = "migrated"

#: The events that carry a whole index row. Their fold is the index.
ROW_EVENTS = frozenset({
    PRESERVED, FILED, PARKED, DUPLICATE, OPENED, ASSIGNED_BY_PERSON, DISMISSED_BY_PERSON,
    UNFILED_BY_PERSON, RESTORED_BY_PERSON, RENAMED_BY_PERSON, ANSWER_WITHDRAWN_BY_PERSON,
    BYTES_RECORDED,
    COPY_MOVED, COPY_REMADE, ORIGINAL_RETURNED, IMPORTED,
})
#: The events that take a row out of the index by its key (decision 132):
#: the release, and the retired hand-over it replaced.
RELEASE_EVENTS = frozenset({RELEASED, HANDED_OVER_BY_PERSON_EVENT})
#: Every event name this version reads.
EVENTS = ROW_EVENTS | RELEASE_EVENTS | frozenset({
    SCANNED, KEYWORD_LEARNED, KEYWORD_UNLEARNED, DRAFTED, DRAFT_APPROVED,
    MIGRATED, RULES_CHANGED, RULES_IMPORTED, MOVING,
    MOVE_ABANDONED, HOUSEHOLD_CHANGED, SHARING_CONFIRMED})
#: The names this version reads and never writes: an older journal may
#: carry them, a new line may not.
RETIRED_EVENTS = frozenset({RULES_IMPORTED, HANDED_OVER_BY_PERSON_EVENT})
#: How a retired name is refused, wherever it is offered for writing.
RETIRED_EVENT = "{name!r} is retired; this version reads it and never writes it"

#: ``O_BINARY`` exists on Windows only; everywhere else the flag is not a flag.
_BINARY = getattr(os, "O_BINARY", 0)
_NEWLINE = b"\n"


#: The three keys every line since decision 159 carries, written by
#: :func:`append` and never by a caller: the applied chain through the line
#: before (``""`` on a record's first line), the machine that wrote it, and
#: the record's format.
LINK_KEY = "prev"
HOST_KEY = "host"
FORMAT_KEY = "fmt"
LINE_KEYS = frozenset({LINK_KEY, HOST_KEY, FORMAT_KEY})
#: The format this version writes and the newest it reads (decision 159, E1).
RECORD_FORMAT = 1

#: What a person does about a record that does not read or does not match:
#: the one pointer every refusal of a record ends with, so the practice page
#: can list those refusals apart from every other problem.
RUN_RECOVER = "Run recover (runbook §6)."
#: The record's own refusals (decision 159). Each names the line and what it
#: means; nothing past such a line is read.
BROKEN_LINK = ("{name} line {line} does not follow the line before it (the record was reordered, "
               "cut or edited). Nothing past it is read. " + RUN_RECOVER)
UNLINKED_LINE = ("{name} line {line} was written without the record's link - by an older version "
                 "of the app or by hand. Nothing past it is read. " + RUN_RECOVER)
NEWER_FORMAT = ("{name} line {line} was written by a newer version of the app (format {fmt}); "
                "this version reads format {known} and stops here rather than misread it. "
                + RUN_RECOVER)
#: A line that does not read at all, by class only - never the parser's own
#: text, which quotes the line (decision 159, principle 7); that goes to the
#: local log.
NOT_AN_EVENT = "{name} line {line} does not read as an event ({why}). " + RUN_RECOVER
LINE_KEY_GIVEN = ("{keys} are written by the record itself (decision 159); an event may not carry "
                  "them, and {event!r} was not written")


class LedgerError(RuntimeError):
    """The record could not be appended to, or does not read as one.

    ``line`` is the line a reader stopped at, when it stopped at one: what
    ``store.recover`` needs to know how much of a record still reads.
    """

    def __init__(self, message: str, *, line: int | None = None) -> None:
        super().__init__(message)
        self.line = line


#: What a record the disk refused says (decision 189): the error's class
#: code and nothing else. The operating system's own text names the
#: record's path - a client's folder - so it stays on ``__cause__`` for a
#: person debugging and is never quoted into a reason, a page or the run
#: log.
RECORD_NOT_WRITTEN = "the record could not be written ({code})"


class RecordNotWritten(LedgerError):
    """The disk refused the record's append or its torn-tail repair
    (decision 189, A-9). A :class:`LedgerError`, so every pass that
    already catches one catches this - a full disk or a sync client's
    lock costs its household, never the practice pass - and ``code`` is
    the errno's name (``ENOSPC``, ``EACCES``), data rather than prose."""

    #: Said as ``<class> (<code>)`` by :func:`tracker.errors.error_class`
    #: (the marker :data:`tracker.errors.SAYS_ITS_CODE`, decision 190).
    says_its_code = True

    def __init__(self, code: str) -> None:
        super().__init__(RECORD_NOT_WRITTEN.format(code=code))
        self.code = code


def _not_written(exc: OSError) -> RecordNotWritten:
    return RecordNotWritten(errno.errorcode.get(exc.errno or 0, "OSError"))


def op_ends(op: dict) -> tuple[tuple[str, bool], ...]:
    """The places one step of an intent names, each with whether the step
    writes there: ``(location, writes)`` for its ``from`` and its ``to``
    (decision 187).

    Said once, here, because both the filer - before it carries a step out
    - and the store - before it admits the line - ask where a step reads
    and where it writes. A copy or a move reads its ``from`` and writes its
    ``to``; a removal writes its ``from``, because taking a file away is a
    write to the place it was. A missing ``from`` is the blank location, so
    it is refused as blank rather than skipped.
    """
    source = str(op.get(FROM_KEY, ""))
    if op.get(OP_KEY) == OP_REMOVE:
        return ((source, True),)
    ends: tuple[tuple[str, bool], ...] = ((source, False),)
    if TO_KEY in op:
        ends += ((str(op[TO_KEY]), True),)
    return ends


def path_for(engagement_dir: Path | str) -> Path:
    """Where one engagement's record lives."""
    return Path(engagement_dir) / LEDGER_FILENAME


def new(name: str, **payload: object) -> dict:
    """An event of ``name``, stamped now, carrying ``payload``.

    The stamp is UTC because the office machine's clock is local and a
    daylight-saving hour would otherwise put two passes out of order.
    """
    _writable(name)
    return {EVENT_KEY: name, AT_KEY: stamp(), **payload}


def _writable(name: object) -> None:
    """Refuse a name this version does not write: an unknown one, or a
    retired one an older journal may carry but a new line may not."""
    if name in RETIRED_EVENTS:
        raise LedgerError(RETIRED_EVENT.format(name=name))
    if name not in EVENTS:
        raise LedgerError(f"{name!r} is not an event this version writes ({', '.join(sorted(EVENTS - RETIRED_EVENTS))})")


def stamp() -> str:
    """Now, as everything the record stamps says it: UTC, to the second.

    UTC because the office machine's clock is local and a daylight-saving
    hour would otherwise put two passes out of order. Public because the
    store (:func:`tracker.store.rebuild_engagement`) stamps when it built
    its rows, and two stamps in one record written two ways would be two
    formats to read back.
    """
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def day_of(at: str) -> dt.date:
    """The local calendar day a :func:`stamp` fell on.

    The stamp is UTC and the runner's day is the office's: a draft written
    late on the draft day is that day's draft, not the next one's. The one
    reading of a stamp, beside the one writing of it; a stamp that will not
    parse is the earliest day there is, so a reader that compares dates
    treats it as long ago rather than failing on it.
    """
    try:
        return dt.datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone().date()
    except (ValueError, OSError, OverflowError):
        # OSError: Windows cannot give a time before the epoch its local
        # day (decision 187's review, S1).
        return dt.date.min


# ----------------------------------------------------------------- write ----


def append(engagement_dir: Path | str, event: dict) -> Path:
    """Append one event to the engagement's record. Returns the file.

    Refuses unless this process holds the engagement lock: the record is
    written in the same locked section as the decision it records, after
    that decision's files have been moved. A silent append outside the lock
    is exactly the line that goes missing later.

    There is no bootstrap here any more. Decision 87 let the first writer
    seed the record with what the workbooks already said; since decision
    104 nothing but the record holds anything, so there is nothing to seed
    from. A retired name is refused by sentence.
    """
    engagement_dir = Path(engagement_dir)
    name = event.get(EVENT_KEY)
    _writable(name)
    if given := sorted(LINE_KEYS & set(event)):
        raise LedgerError(LINE_KEY_GIVEN.format(keys=", ".join(map(repr, given)), event=name))
    if not lock_is_held(engagement_dir):
        raise LedgerError(
            f"{engagement_dir.name}: the record is appended to only while this run holds the "
            f"engagement lock; {name!r} was not written"
        )
    path = path_for(engagement_dir)
    # One read of the file, parsed by the one reader: a record that does not
    # read - a broken link, a newer format - is refused here too, before a
    # line is put after it (decision 159, E1), and the link written is the
    # chain over exactly the lines that reader returned.
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        data = b""
    except OSError as exc:
        # The disk's error leaves as the record's, by its code (decision 189).
        raise _not_written(exc) from exc
    before = ""
    for _event, raw in _parse_lines(data, path.name):
        before = chain_link(before, raw)
    _truncate_torn_tail(path, data)
    _write_raw(path, line_of(event, before))
    return path


def line_of(event: dict, before: str) -> bytes:
    """The exact bytes :func:`append` writes for ``event`` after a record
    whose chain is ``before``, without the newline: the event with its link,
    this machine's name and the format (decision 159). One function, so the
    intent :func:`intended_heads` records is made of the very bytes the
    append writes (principle 2)."""
    return json.dumps({**event, LINK_KEY: before, HOST_KEY: this_host(), FORMAT_KEY: RECORD_FORMAT},
                      ensure_ascii=False, sort_keys=True).encode("utf-8")


def intended_heads(before: str, events: list[dict]) -> list[str]:
    """The chain after each of ``events``, appended in order to a record
    whose chain is ``before``: what ``store.record`` says it is about to
    write, so a line of this machine past the checkpoint is accepted only
    when it is exactly one of those lines (decision 159, the review's M1)."""
    heads = []
    for event in events:
        before = chain_link(before, line_of(event, before))
        heads.append(before)
    return heads


def _write_raw(path: Path, line: bytes) -> None:
    line = line + _NEWLINE
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | _BINARY, 0o666)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise _not_written(exc) from exc


def _truncate_torn_tail(path: Path, data: bytes) -> None:
    """Drop bytes a killed run left with no newline after them - unless they
    are a whole line that lost only its newline, which is kept.

    Only ever the tail, and only under the lock: a torn line is the one thing
    a crash can leave behind, and appending after it would bury the damage in
    the middle of the file where no reader could tell it from a record.

    **A line that lost only its newline is not torn (decision 159, A-4).** A
    sync client or an editor that saves a file without its last newline
    leaves the last event whole; dropping it would delete a decision the
    record had already made. So a tail that reads as one complete event
    (:func:`_a_complete_tail`) gets its newline back - one write, flushed -
    with a warning naming the file, and the next line goes after it. A
    genuinely torn line never reads as a whole object, and is dropped as
    before.

    ``data`` is the file's bytes as :func:`append` read them, under the
    lock, so the tail judged is the tail its link was computed over.
    """
    if not data or data.endswith(_NEWLINE):
        return
    keep = data.rfind(_NEWLINE) + 1
    if _a_complete_tail(data[keep:]):
        log.warning("%s ended without its last newline; the line is whole and is kept", path.name)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | _BINARY)
            try:
                os.write(fd, _NEWLINE)
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError as exc:
            # The disk's error leaves as the record's (decision 189).
            raise _not_written(exc) from exc
        return
    log.warning("%s ended mid-line (%d byte(s)); the torn tail is dropped", path.name, len(data) - keep)
    try:
        with open(path, "r+b") as handle:
            handle.truncate(keep)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise _not_written(exc) from exc


def _a_complete_tail(tail: bytes) -> bool:
    """The bytes after the last newline are one whole event: they parse as
    one JSON object carrying :data:`EVENT_KEY`. Its link is checked where
    every line's is (:func:`_parse_lines`), so a kept tail that carries a
    link must carry the right one or the record is refused. A tail nested too
    deep to parse is torn, never a crash: before 159 no tail was parsed at
    all, and a record's tail is exactly the bytes nobody vouches for."""
    if not tail.strip():
        return False
    try:
        event = json.loads(tail.decode("utf-8"))
    except (ValueError, RecursionError):
        return False
    return isinstance(event, dict) and event.get(EVENT_KEY) is not None


# ------------------------------------------------------------------ read ----


def _bytes_of(path: Path) -> bytes | None:
    """The record's bytes as they are this moment, or None where there is
    no record. The one read every reader below is made of."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise LedgerError(f"could not read {path.name}: {exc}") from exc


def _parse(data: bytes, name: str) -> list[dict]:
    """The events ``data`` holds, oldest first: the one parser of a record.

    A torn last line - bytes a killed run left with no newline after them -
    is ignored. Anything else that does not read as one JSON object per line
    is corruption in the middle of the file and is refused loudly: this is
    the record, and nothing is guessed past it.
    """
    return [event for event, _raw in _parse_lines(data, name)]


def _parse_lines(data: bytes, name: str) -> list[tuple[dict, bytes]]:
    """:func:`_parse`, with each event's own line as it is in the file
    (without its newline): what :func:`read_with_chain` digests.

    **Each line is checked in its place while it is read** (decision 159):
    its format (:data:`NEWER_FORMAT`), then its link - a line carrying
    :data:`LINK_KEY` must name the chain through the lines before it
    (:data:`BROKEN_LINK`) and a host, and once one line has carried a link
    every line after it must (:data:`UNLINKED_LINE`). The lines before the
    first linked one are the record from before 159 and read as they always
    did.
    """
    if not data:
        return []
    lines = data.split(_NEWLINE)
    if lines[-1] and _a_complete_tail(lines[-1]):
        # A whole line that lost only its newline is a line (decision 159);
        # the next append gives it its newline back.
        log.warning("%s ends without its last newline; the last line is whole and is read", name)
    else:
        if lines[-1]:
            log.warning("%s ends mid-line; the torn last line is ignored", name)
        lines.pop()                   # the tail after the last newline: empty, or torn
    events = []
    before, linked = "", False
    for number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            # Not only a decoding or a JSON error (both are ValueErrors): a
            # number past the interpreter's digit limit raises a bare one,
            # which escaped every reader as something other than a record
            # that does not read (decision 180). Said by its class; the
            # parser's text quotes the line and goes to the local log only.
            why = ("it is not UTF-8" if isinstance(exc, UnicodeDecodeError) else
                   "it is not JSON" if isinstance(exc, json.JSONDecodeError) else
                   "it holds a number too long to read")
            # At call time: the ledger imports nothing of the package but
            # the lock at load. The words go to the debug sink only (190).
            from tracker import errors

            errors.keep("ledger", exc, name=f"{name} line {number}")
            log.warning("%s line %d does not read (%s)", name, number, errors.error_class(exc))
            raise LedgerError(NOT_AN_EVENT.format(name=name, line=number, why=why), line=number) from None
        except RecursionError:
            # Nested past the interpreter's limit: a line that does not
            # read, said as one, never a bare RecursionError (decision 159).
            raise LedgerError(NOT_AN_EVENT.format(name=name, line=number,
                                                  why="it is nested too deeply"), line=number) from None
        if not isinstance(event, dict) or event.get(EVENT_KEY) is None:
            raise LedgerError(f"{name} line {number} is not an event. " + RUN_RECOVER, line=number)
        try:
            linked = _in_its_place(event, name, number, before, linked)
        except LedgerError as exc:
            exc.line = number
            raise
        before = chain_link(before, raw)
        events.append((event, raw))
    return events


def _in_its_place(event: dict, name: str, number: int, before: str, linked: bool) -> bool:
    """Refuse a line of a newer format, a line whose link is not ``before``,
    and a line with no link once the record is linked. Returns whether the
    record is linked from this line on."""
    fmt = event.get(FORMAT_KEY)
    # A format that is not a number is a value out of its rule, and the
    # store's gate refuses it with every other (decision 187); here only a
    # number this version does not read stops the reader.
    if isinstance(fmt, int) and not isinstance(fmt, bool) and fmt > RECORD_FORMAT:
        raise LedgerError(NEWER_FORMAT.format(name=name, line=number, fmt=fmt, known=RECORD_FORMAT))
    if LINK_KEY not in event:
        if linked:
            raise LedgerError(UNLINKED_LINE.format(name=name, line=number))
        return False
    if event[LINK_KEY] != before:
        raise LedgerError(BROKEN_LINK.format(name=name, line=number))
    return True


def siblings(folder: Path | str) -> list[Path]:
    """Every copy of the record or the lock beside the real ones in one
    folder: what a sync client leaves when two machines disagree (decision
    159, A-8 / G-5).

    Non-recursive and case-insensitive: every file whose name starts with
    the record's stem and ends ``.jsonl`` but is not :data:`LEDGER_FILENAME`
    (Drive's ``_ledger (1).jsonl``, ``_ledger_conflict-....jsonl``), and
    every file whose name starts with the lock's stem and ends ``.lock``, or
    is the lock's name with anything after it - except the lock itself, its
    breaker, and a breaker's cleared-marker younger than
    ``locking.BREAKER_STALE_SECONDS`` (both are the lock at work; an older
    one was left behind and is named like any other). **Nothing ever
    deletes, moves or renames one**: the tracker cannot know which copy is
    right, so each is named every pass until a person deals with it.
    """
    folder = Path(folder)
    record_stem = Path(LEDGER_FILENAME).stem.casefold()
    lock_name = LOCK_FILENAME.casefold()
    lock_stem = Path(LOCK_FILENAME).stem.casefold()
    breaker = (LOCK_FILENAME + BREAKER_SUFFIX).casefold()
    marker = breaker + BREAKER_CLEARED_INFIX.casefold()
    try:
        children = sorted(folder.iterdir())
    except OSError:
        return []
    found = []
    for child in children:
        name = child.name.casefold()
        if name in (LEDGER_FILENAME.casefold(), lock_name, breaker) or not child.is_file():
            continue
        if name.startswith(marker) and not _left_behind(child):
            continue
        if (name.startswith(record_stem) and name.endswith(".jsonl")) or (
                name.startswith(lock_stem) and (name.endswith(".lock") or name.startswith(lock_name))):
            found.append(child)
    return found


def _left_behind(path: Path) -> bool:
    """A breaker's marker older than the lock says one lives."""
    try:
        return time.time() - path.stat().st_mtime >= BREAKER_STALE_SECONDS
    except OSError:
        return False


def chain_link(before: str, line: bytes) -> str:
    """One step of the applied chain (decision 137, A3): ``sha256(before ||
    line)`` as hex, where ``before`` is the chain up to the line before
    (``""`` before the first) and ``line`` is the line's own bytes as the
    file holds them, without the newline."""
    return hashlib.sha256(before.encode("ascii") + line).hexdigest()


def _digest(data: bytes | None) -> str:
    """The head of ``data``: its SHA-256, or empty where there is no record."""
    return "" if data is None else hashlib.sha256(data).hexdigest()


def read_events(engagement_dir: Path | str) -> list[dict]:
    """Every event in the engagement's record, oldest first; [] if there is none.

    A torn last line - bytes a killed run left with no newline after them -
    is ignored. Anything else that does not read as one JSON object per line
    is corruption in the middle of the file and is refused loudly: this is
    the record, and nothing is guessed past it.
    """
    path = path_for(engagement_dir)
    data = _bytes_of(path)
    return [] if data is None else _parse(data, path.name)


def read_with_head(engagement_dir: Path | str) -> tuple[list[dict], str]:
    """The record's events and its head, both from **one** read of the file.

    What the store applies and the head it saves beside them (decision
    135). Read as two calls - :func:`read_events`, then :func:`head` - the
    two are two moments, and a line appended between them leaves a head
    that names a line nobody applied: the store then calls itself current
    while it is behind, and refuses every later writer. One read cannot
    disagree with itself. Parsed exactly as :func:`read_events` parses (a
    torn tail is not a line, corruption is refused) and digested exactly as
    :func:`head` digests, torn tail included, so the pair equals the two
    calls on a file nobody is writing.
    """
    path = path_for(engagement_dir)
    data = _bytes_of(path)
    now = _digest(data)
    return ([] if data is None else _parse(data, path.name)), now


def read_with_chain(
    engagement_dir: Path | str,
    *,
    known: tuple[list[dict], str, list[str]] | None = None,
) -> tuple[list[dict], str, list[str]]:
    """:func:`read_with_head`, and the running **applied chain** after each
    line, all from one read (decision 137, A3).

    ``chain[n - 1]`` is the chain over the first ``n`` lines
    (:func:`chain_link`, from ``""``). The store keeps the chain over the
    lines it has applied and compares it with this one before it applies
    another: a rewrite or a reorder of the journal that keeps the line
    count - a sync client resolving a conflict - changes the chain even
    where it leaves the count, and is refused rather than blessed. The
    chain lives in the store, which is rebuildable, and not in the journal,
    whose format is the record's and unchanged.

    ``known`` is a triple this function returned earlier: when the bytes
    read now still digest to its head, they are the bytes its events came
    from, and those events are returned without parsing the file a second
    time - the store's look outside its transaction and its read inside are
    then one parse, and still one read of the file each.
    """
    path = path_for(engagement_dir)
    data = _bytes_of(path)
    now = _digest(data)
    if known is not None and known[1] == now:
        return known[0], now, known[2]
    events: list[dict] = []
    chain: list[str] = []
    before = ""
    for event, raw in ([] if data is None else _parse_lines(data, path.name)):
        before = chain_link(before, raw)
        events.append(event)
        chain.append(before)
    return events, now, chain


def chain_at(chain: list[str], count: int) -> str:
    """The applied chain over the first ``count`` lines: ``""`` for none."""
    return chain[count - 1] if count else ""


@dataclass
class Folded:
    """What the record adds up to: the index, the statuses, the rules and
    the keywords filings taught.

    One state rather than five answers, because :func:`apply` folds one
    event into all of them and a reader replaying the record line by line
    (:mod:`tracker.store`) needs to carry the lot between lines.
    """

    #: The index the events add up to: the last index-shaped event per
    #: original, keyed by the identity the writer recorded the row under
    #: (its location among the client's preserved originals). An event
    #: carrying ``WAS_KEY`` says the row arrived from another identity - the
    #: client moved the original and the row followed the bytes - and the one
    #: it left is dropped, as the index has only the one row for it.
    #:
    #: **In the index's order.** The rows come back in the order the record
    #: first saw each original, and a row that changed identity keeps the
    #: place the one it left held: the writer rewrites that row where it sits
    #: rather than moving it to the end. The order is the audit trail's own
    #: and there is no second copy of it to drift from - :mod:`tracker.store`
    #: lays its ``position`` column from this fold, and
    #: :func:`tracker.filer.read_index` reads it back.
    rows: dict[str, dict] = field(default_factory=dict)
    #: The last status each identifier was scanned to, by identifier. A pass
    #: appends only what it changed, so the answer is built up across every
    #: ``SCANNED`` event rather than read off the last one.
    statuses: dict[str, dict] = field(default_factory=dict)
    #: identifier -> the person's rule row, as ``records.rule_to_json``
    #: writes it, in the order the record first saw each one; empty where no
    #: rules event has ever been appended. Keyed by the identifier as the person spelt it; the
    #: validation refuses two rows whose identifiers differ only in case,
    #: so one spelling per row is all there can be.
    rules: dict[str, dict] = field(default_factory=dict)
    #: The engagement's details, as ``records.info_to_json`` writes them.
    #: Only the ones any edit has ever recorded: a field nothing has spoken
    #: for is the record's default, not a blank somebody typed.
    info: dict[str, object] = field(default_factory=dict)
    #: The household's own details, as ``records.household_to_json`` writes
    #: them, folded the same way ``info`` is (decision 125). Empty on every
    #: return's journal - a household record is a journal of its own, in
    #: the household's folder in the private tree - and empty on a
    #: household nothing has recorded yet.
    household: dict[str, object] = field(default_factory=dict)
    #: The moves begun and not finished, by the row's identity: the whole
    #: :data:`MOVING` line, so a reader has the operations, the row, the
    #: event that completes it and the day it was written (decision 119).
    #: One per key - a key is one row, and a row is one decision at a time -
    #: and empty on a record where every decision that began has ended,
    #: which is every record after an uninterrupted pass.
    intents: dict[str, dict] = field(default_factory=dict)
    #: identifier -> the keywords filings taught that request and nobody
    #: has taken back, in the order they were taught (decision 113).
    #: Keyed by the identifier exactly as the event spells it: this module
    #: sits below :mod:`tracker.records` and may not borrow its
    #: case-folding. This is the journal's own fold, what
    #: ``python -m tracker.ledger`` prints; the store's check does not
    #: compare against it but folds the same lines again by
    #: ``records.identifier_key``, as the store keys them
    #: (``tracker.store._recorded_learned``, decision 136).
    learned: dict[str, tuple[str, ...]] = field(default_factory=dict)


def apply(state: Folded, event: dict) -> Folded:
    """One event folded into what the record said before it. Returns ``state``.

    **The whole of both fold rules, in one place.** :func:`replay` is this
    function over a whole file, and the store of
    decision 101 is this function over the lines it has not applied yet -
    so an index that is replayed a line at a time and one that is folded
    from the start cannot come out different. Anything that has to change
    about what an event means changes here.

    ``state.rows`` is mutated where it can be; a row that arrived from
    another identity is the one case that cannot be, because a dict cannot
    re-key in place and the row keeps the place the one it left held, so
    the mapping is rebuilt around it and assigned back.

    An event whose name this version does not know as index-shaped, and is
    not a scan, a rules edit or a keyword taught or taken back, is passed
    over rather than refused: a later version may write one, and a reader
    that refuses what it does not know cannot read a record written by the
    run after it.
    """
    name = event.get(EVENT_KEY)
    if name == SCANNED:
        state.statuses.update(event.get(STATUSES_KEY) or {})
        return state
    if name in (RULES_CHANGED, RULES_IMPORTED):
        return _apply_rules_event(state, event)
    if name == HOUSEHOLD_CHANGED:
        # The same fold the details take: what the line carries is set,
        # and a field it does not name keeps what the household had.
        state.household.update(event.get(HOUSEHOLD_KEY) or {})
        return state
    if name in (MOVING, MOVE_ABANDONED):
        return _apply_intent_event(state, event)
    if name in (KEYWORD_LEARNED, KEYWORD_UNLEARNED):
        return _apply_keyword_event(state, event)
    if name in RELEASE_EVENTS:
        return _apply_release(state, event)
    if name not in ROW_EVENTS:
        return state
    key = event.get(KEY_KEY)
    if key is None:
        raise LedgerError(f"an index-shaped {name!r} event carries no {KEY_KEY!r}")
    was = event.get(WAS_KEY)
    if was and was != key:
        if was in state.rows and key not in state.rows:
            # Renamed where it stands: a dict cannot re-key in place, so
            # the row order is rebuilt around it rather than the row
            # being dropped and appended at the end.
            state.rows = {(key if held == was else held): row for held, row in state.rows.items()}
        else:
            state.rows.pop(was, None)
    state.rows[key] = event[ROW_KEY]
    # The row event completes the intent this key was moving under: what it
    # was about to do to the disk is what it has now recorded, so there is
    # nothing left for a later pass to finish (decision 119). The identity
    # a row left closes its intent too - the row is the same row, and it
    # has been written.
    state.intents.pop(key, None)
    if was:
        state.intents.pop(was, None)
    return state


def _apply_release(state: Folded, event: dict) -> Folded:
    """One row released (decision 132): it leaves the index, and the intent
    its key had open is finished with.

    The same deletion the ``was`` of a row event makes, without a row to
    put in its place. A retired ``handed_over_by_person`` line is folded
    here too: it carried the row re-keyed under the place the original
    went, and the identity it left, so both go - which is what the built
    row meant, a document this record no longer holds.
    """
    key = event.get(KEY_KEY)
    if key is None:
        raise LedgerError(f"a {event.get(EVENT_KEY)!r} event carries no {KEY_KEY!r}")
    for gone in (key, event.get(WAS_KEY)):
        if gone:
            state.rows.pop(gone, None)
            state.intents.pop(gone, None)
    return state


def _apply_intent_event(state: Folded, event: dict) -> Folded:
    """One move begun, or one abandoned (decision 119).

    ``MOVING`` replaces whatever this key had open: a key is one row and a
    row is one decision at a time, so the newest intent for it is the one
    a recovery has to finish. ``MOVE_ABANDONED`` closes it - the record
    refused the decision and the files went back, so the next pass must
    not finish forward a move that was undone.
    """
    key = event.get(KEY_KEY)
    if key is None:
        raise LedgerError(f"a {event.get(EVENT_KEY)!r} event carries no {KEY_KEY!r}")
    if event.get(EVENT_KEY) == MOVING:
        state.intents[key] = event
    else:
        state.intents.pop(key, None)
    return state


def _apply_rules_event(state: Folded, event: dict) -> Folded:
    """One edit folded: the identifiers it names as removed go first, then
    the rows it carried replace the rows of those identifiers, and the
    Engagement fields it carried are set. The same fold for a
    ``RULES_CHANGED`` line and for the retired ``RULES_IMPORTED`` an older
    journal carries.

    Removals before rows, because a rule is keyed by its identifier's
    exact spelling and an edit that respells one by case names the old
    spelling as removed and carries the new: applied the other way round,
    a removal spelled the way the store held it would delete the row just
    written and the list would lose the rule.

    A row the edit does not mention is untouched: an edit carries what
    moved and nothing else, so the fold of every edit is the list. The
    list's own order is not this mapping's - it is the ``row`` each rule
    carries, its position in the list - so a row added in the middle folds
    at the end here and still comes back in its place
    (:func:`tracker.store.rules`).
    """
    for identifier in event.get(REMOVED_KEY) or []:
        state.rules.pop(str(identifier), None)
    for row in event.get(RULES_KEY) or []:
        identifier = str(row.get("identifier", ""))
        if identifier:
            state.rules[identifier] = row
    state.info.update(event.get(INFO_KEY) or {})
    return state


def _apply_keyword_event(state: Folded, event: dict) -> Folded:
    """One keyword taught or taken back, folded into ``state.learned``.

    **In the order they were taught.** A word is appended, or moved last
    when it is already there, as the store's re-insert orders it, and an
    unlearn removes it - so teaching, taking back and teaching again
    leaves it last, and so does teaching it twice. That is what the
    store's own fold says, where a re-learned row is inserted again and
    carries the new sequence number (``ORDER BY seq``). For lines that
    spell the request alike the two folds agree by construction rather
    than because no writer here teaches a word twice; across spellings
    the store's check folds by ``records.identifier_key`` (decision 136).

    The keyword is matched exactly, as the store keys it; the identifier is
    the event's own spelling, for the reason :class:`Folded` gives - so
    this fold keys a request by the exact spelling each line carries, and
    ``tracker.store.check()`` applies this same rule per
    ``records.identifier_key`` instead (``_recorded_learned``, decision
    136), which is how the store keys it. An
    unlearn of a word nothing taught folds to nothing: the writer
    (``tracker.manifest.unlearn_keyword``) refuses the pair by name before
    a line is written, and a reader that met one anyway is reading a
    record, not deciding anything.
    """
    identifier = str(event.get(IDENTIFIER_KEY, ""))
    keyword = str(event.get(KEYWORD_KEY, ""))
    taught = state.learned.get(identifier, ())
    left = tuple(word for word in taught if word != keyword)
    if event.get(EVENT_KEY) == KEYWORD_LEARNED:
        state.learned[identifier] = left + (keyword,)
        return state
    if left:
        state.learned[identifier] = left
    else:
        state.learned.pop(identifier, None)
    return state


def replay(events: list[dict]) -> Folded:
    """Every event folded, oldest first: the index, the statuses, the rules
    and the keywords filings taught.

    One walk for a caller that wants all of them, and the definition
    of what the rows, the statuses and the rules each are.
    """
    state = Folded()
    for event in events:
        apply(state, event)
    return state


def head(engagement_dir: Path | str) -> str:
    """A digest of the record's bytes: the same for two folders holding the
    same history, different the moment either is appended to. Empty where
    there is no record yet. Whoever saves a head beside lines it applied
    takes both from :func:`read_with_head` instead (decision 135)."""
    return _digest(_bytes_of(path_for(engagement_dir)))


# ------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(description="Show one engagement's own record")
    parser.add_argument("engagement_dir", help="the engagement folder")
    ns = parser.parse_args()
    # A typed folder is parsed, never trusted (decision 188).
    from tracker import door

    ns.engagement_dir = door.typed_return(parser, ns.engagement_dir)

    # There is nothing left here to compare with a workbook. Until decision
    # 103 the manifest carried each request's status as well, and
    # ``--compare`` was the operator's check that the two agreed; the
    # record holds everything now, the person's rules included, and the
    # check that matters is the store against this file - ``python -m
    # tracker.store <store> check <clients root>``.
    folder = Path(ns.engagement_dir)
    recorded = read_events(folder)
    folded = replay(recorded)
    print(f"\n{path_for(folder)}")
    print(f"  events: {len(recorded)}")
    if recorded:
        print(f"  first:  {recorded[0][AT_KEY]}  ({recorded[0][EVENT_KEY]})")
        print(f"  last:   {recorded[-1][AT_KEY]}  ({recorded[-1][EVENT_KEY]})")
        counts: dict[str, int] = {}
        for one in recorded:
            counts[one[EVENT_KEY]] = counts.get(one[EVENT_KEY], 0) + 1
        print("  by event: " + ", ".join(f"{k} {n}" for k, n in sorted(counts.items())))
    print(f"  rows:     {len(folded.rows)}")
    print(f"  statuses: {len(folded.statuses)}")
    print(f"  rules:    {len(folded.rules)}")
    print(f"  learned:  {sum(len(words) for words in folded.learned.values())}")
    print(f"  head:     {head(folder) or '(none)'}\n")
