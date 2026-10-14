"""The index as the record holds it: the words its rows carry, and their readers.

Every row of an engagement's index says what became of one original: its
decision (:data:`FILED`, :data:`NEEDS_REVIEW`, :data:`DUPLICATE`,
:data:`NOT_REQUESTED`, :data:`FILE_MOVED`) and, in its Reason, the firm's
own sentences about where its working copy is. This module holds those
words and everything that reads a row back by them:

- :func:`read_index`, which answers from the store (decision 102), and
  :func:`ensure`, which brings the store up to the journal and says whether
  it describes the engagement;
- :func:`prepared_location`, where a working copy is, as a row writes it;
- the moved sentences (:data:`MOVED_SENTENCE`, :data:`MOVED_GONE_SENTENCE`,
  :data:`BOTH_GONE_SENTENCE`) and a person's mark (:data:`MARKED_MISSING`),
  read back by :func:`moved_to`, :func:`both_gone` and
  :func:`marked_missing`, each pattern derived from the template that
  writes its sentence, so rewording one moves its reader with it;
- :data:`INTERRUPTED_MOVE_DETAIL` and :func:`interrupted`, the path a step
  a pass recovers names (decision 119);
- :func:`holds_the_row`, the one proof of a row's bytes, which the store's
  ``verify`` holds every recorded file to (decision 159);
- and :data:`INDEX_HEADING`, what the index is called wherever it is shown.

**Why it is its own module** (SPEC-architecture-p2 P2.9, P319; the
architecture audit's A-2, step 1). These words sat in the filer, at layer
3, so every module that reads a row - the scanner, the review, the
reminder, the view, the rollover and, at call time, the store - imported
the sorter to read one, and none of them sorts anything. Here they are at
layer 1: this module reads the store, the journal, the record types and
the validators, all layer 1, and the layout and the reasons, layer 0, and
nothing that sorts, moves or reads a document. ``PREPARED_DIR_NAME`` comes
from :mod:`tracker.layout`, where it is defined, not through the
scaffold's import of it as the filer takes it.

**The filer-scanner cycle becomes one way** (the architecture SPEC's Q-A).
The scanner's half of that cycle is reading the index, not sorting: once
the scanner reads it from here (P2.10), the filer still asks for a rescan
at call time and the scanner never imports the filer.

**The filer still offers every name** until P2.14. It imports from here
what it reads itself and re-exports :data:`INDEX_HEADING` and
:func:`interrupted`, each the very object defined here, so
``from tracker.filer import read_index`` is this function, and a stand-in
on ``filer.read_index`` still reaches the filer's own callers.

**Three private names cross the boundary,** and nowhere else does one.
The filer writes the moved sentences, and when it takes one off a Reason,
adds a sentence before one or asks whether a row already says its bytes are
nowhere, it asks :func:`_without_moved_sentence`,
:func:`_before_the_moved_sentence` and :func:`_says_it_is_nowhere`. Each
reads only the moved tail's grammar (:func:`_moved_part`), so each lives
beside it, and the filer imports them by those names. They stay private:
they are for the writer of a Reason, not for its readers.

The comments and docstrings below came with the code, word for word.
Where :data:`INTERRUPTED_MOVE_DETAIL`'s says it is "composed here because
the filer is what knows the paths", the filer still composes it: this
module holds the sentence's words and reads them back.
"""

from __future__ import annotations

import re
from pathlib import Path

from tracker import ledger, reasons, store
from tracker.layout import PREPARED_DIR_NAME
from tracker.records import IndexEntry, as_pattern, entry_from_json
from tracker.validators import is_cloud_placeholder, sha256_of

# ---------------------------------------------------- the decision words ----

#: What the index's section is called wherever it is shown - the word a
#: person knows it by and the Status Report's own section heading
#: (:mod:`tracker.view`).
INDEX_HEADING = "Index"
#: Decision values written to the index.
FILED = "Filed"
NEEDS_REVIEW = "Needs Review"
DUPLICATE = "Duplicate"
#: A parked document no request asks for - an agency notice, an extra
#: statement. The working copy stays in ``REVIEW_DIR_NAME`` (nothing a
#: client sent is ever deleted) and the original in the year's folder is
#: untouched; what changes is that the draft stops counting it. It says
#: nobody asked for this document *that day*, not that these bytes are
#: settled for ever: the same bytes sent again are routed afresh and the
#: new row names this decision (decision 111). Filing it is how the
#: decision is undone.
NOT_REQUESTED = "Not Requested"
#: A document whose working copy is not where the record put it, and whose
#: bytes a pass found at a path no row names (decision 109). A decision on
#: the document and never a status of a request (the owner's rule,
#: 2026-09-19): what the scanner says about a request is what Prepared
#: holds under its name, and "the copy is not where I put it" is a fact about the
#: document. The row keeps its home in ``prepared_location`` and says where
#: the bytes are now in its Reason (:func:`moved_to` reads it back);
#: nothing is moved, and a person decides. A copy dragged back is filed
#: again on the next pass.
FILE_MOVED = "File Moved"
#: What a consolidated statement's row says when a person marks one of the
#: requests it answered missing again (decision 146): appended to the
#: Reason, so the row keeps why it was filed and says what the person took
#: back, when, and why if they said.
MARKED_MISSING = "{identifier} marked missing again by a person on {date}{note}"


def prepared_location(folder: Path, name: str) -> str:
    """Where a working copy is, relative to the engagement:
    ``PREPARED_DIR_NAME/<name>`` for a copy in the firm's folder itself
    (decision 168), ``PREPARED_DIR_NAME/<folder>/<name>`` for one in a
    folder inside it - the review folder, or a person's (one a person
    named ``Prepared`` too is still inside it)."""
    if folder.name == PREPARED_DIR_NAME and folder.parent.name != PREPARED_DIR_NAME:
        return f"{PREPARED_DIR_NAME}/{name}"
    return f"{PREPARED_DIR_NAME}/{folder.name}/{name}"


# ------------------------------------------------------------------ index ----


def read_index(engagement: Path | str, *, follow: bool = True) -> list[IndexEntry]:
    """Every index row, oldest first. Empty where nothing is recorded yet.

    **The record answers this, and there is no workbook behind it**
    (decision 102). The rows come from the store's ``documents`` table in
    the index's own order, which is the order
    :func:`tracker.ledger.replay` puts the journal's events in; the store is
    a derivation of the journal and :func:`tracker.store.follow_the_journal`
    makes it one again before every read, building the engagement's rows
    from the journal where the database has none and replaying the lines
    it has not applied where it is behind. That costs one digest of the
    journal file when nothing has happened, which is nearly always.

    So no reader has to know whether anybody prepared this engagement
    first: the pass, the app's state, the triage, the reminder, the
    rollover and the Status Report all come through here and all get the
    same rows.

    Reading with ``follow`` false is the practice page's alone (decision
    192): the walk has just followed every journal, so the page reads the
    rows as the store holds them; a return the store does not hold is
    followed all the same. Nothing that files, parks or tells the client
    passes it.
    """
    folder = Path(engagement)
    conn = store.connect()
    if follow or store.kind(conn, folder) is None:
        store.follow_the_journal(conn, store.root_for(folder), folder)
    # Built once per state of the record inside a hold (pilot P215, E2):
    # the journal was followed above, every time.
    return store.held_read(conn, folder, "index",
                           lambda: [entry_from_json(row) for row in store.documents(conn, folder)])


# ----------------------------------------------------------------- ensure ----


def ensure(engagement_dir: Path | str, root: Path | None = None) -> str:
    """Make the store describe this engagement, and say which of the three
    words it is in (:data:`tracker.records.CURRENT` and its two siblings).

    Run at the start of every pass and by every command that names an
    engagement, before anything reads the index or the request list: an
    engagement the store has never seen is built from its record, and one
    the store is behind on has the lines it has not applied replayed
    (:func:`tracker.store.catch_up`). Nothing is written in the
    engagement folder - the store is the machine's own derivation and
    building it moves nothing of the client's - so a dry run, the Status
    Report and the app showing an engagement another run is holding all
    call it as freely as a pass does.

    **By count, not by head** (decision 135). The readers trust a stored
    head that matches the journal's and parse nothing; this compares the
    number of lines applied with the number the journal holds, every
    time. So a store an earlier version left with a head naming a line it
    never applied - current by its head, refusing every writer by its
    count - is repaired by the next pass, with no rebuild. A pass parses
    the journal anyway, so the cost is one parse per engagement per pass,
    and a store with nothing to apply is answered without the store's
    write lock, so the app's views and the Status Report never queue a
    pass's ``record()`` behind them.
    """
    folder = Path(engagement_dir)
    root = Path(root) if root is not None else store.root_for(folder)
    conn = store.connect()
    store.catch_up(conn, root, folder)
    return store.state(conn, folder, ledger_head_now=ledger.head(folder))


# ----------------------------------------------------- the working copies ----


#: The moved sentence on a ``FILE_MOVED`` row: the row keeps its home in
#: the Prepared Location column and says here where its bytes are now.
#: Read back by :func:`moved_to`, from this very template.
MOVED_SENTENCE = "{home} no longer holds this row's bytes; they are at {now} (found {date})"
#: The same row when the bytes are nowhere in the firm's folder any more.
#: The original is untouched wherever the client put it, which is the
#: sentence's whole comfort: a working copy is disposable.
MOVED_GONE_SENTENCE = ("{home} no longer holds this row's bytes and nothing under {prepared} does; "
                       "the original is safe in {pbc} (found {date})")
#: And when it cannot be: the copy is gone, nothing under the firm's folder
#: holds its bytes, and the original is gone too or holds other bytes
#: (decision 157, ruling B5). The row is ``FILE_MOVED`` with this sentence,
#: said once, and the request is held firm-side until a person looks
#: (``reasons.COPY_AND_ORIGINAL_GONE``); only their Mark missing asks the
#: client again. Read back by :func:`both_gone`, from this very template.
BOTH_GONE_SENTENCE = ("{home} no longer holds this row's bytes, nothing under {prepared} does, and "
                      "the original {pbc} is gone or holds other bytes (found {date})")

_MOVED_DATE = r"\d{4}-\d{2}-\d{2}"


def _moved_tail(template: str) -> re.Pattern[str]:
    """One of the moved sentences, where a row's Reason ends with it.

    The pattern is derived from the template that wrote the sentence, so
    rewording the sentence moves its reader with it (decision 108's
    precedent, :func:`tracker.records.as_pattern`). ``base`` is greedy, so
    what matches is the *last* such sentence on the row: a copy that has
    moved before carries its history and only the sentence this pass
    replaces comes off.
    """
    return re.compile(
        "^(?P<base>.*); " + as_pattern(
            template, home=r".+?", now=r"(?P<now>.+?)", prepared=r".+?", pbc=r".+?",
            date=_MOVED_DATE,
        ) + "$",
        re.DOTALL,
    )


_MOVED_TAIL = _moved_tail(MOVED_SENTENCE)
_MOVED_GONE_TAIL = _moved_tail(MOVED_GONE_SENTENCE)
_BOTH_GONE_TAIL = _moved_tail(BOTH_GONE_SENTENCE)
#: A person's mark (decision 146's MARKED_MISSING) at the end of a Reason.
#: Decision 146 lets a person mark an answer missing on a ``FILE_MOVED``
#: row too, and the mark is appended after whatever the row said, so the
#: moved sentence is looked for behind any such marks (:func:`_moved_part`).
#: The note is read up to its own closing bracket and no further: the
#: moved sentences end in brackets too, and a mark made *before* one must
#: never be read as swallowing it. A note that itself holds brackets is not
#: read as a mark, and the row is read as it always was.
_MARKED_TAIL = re.compile(
    "^(?P<base>.*); " + as_pattern(
        MARKED_MISSING, identifier=r"[^;]+?", date=_MOVED_DATE, note=r"(?: \([^()]*\))?",
    ) + "$",
    re.DOTALL,
)


def _moved_part(reason: str) -> tuple[str, re.Pattern[str] | None, str, str]:
    """A Reason split round the moved sentence it ends with: what came
    before it, which of the three it is (``None`` where there is none),
    the sentence itself, and any person's marks after it (decision 157).

    Each of the three patterns comes from the template that writes the
    sentence (:func:`_moved_tail`), so rewording a sentence moves this
    reader with it.
    """
    rest, marks = reason, ""
    while (found := _MARKED_TAIL.match(rest)) is not None:
        marks = rest[len(found.group("base")):] + marks
        rest = found.group("base")
    for pattern in (_MOVED_TAIL, _MOVED_GONE_TAIL, _BOTH_GONE_TAIL):
        found = pattern.match(rest)
        if found:
            return found.group("base"), pattern, rest[len(found.group("base")) + 2:], marks
    return reason, None, "", ""


def moved_to(entry: IndexEntry) -> str | None:
    """Where this row's working copy is now, or None.

    The row's home stays in ``prepared_location`` - every reader treats
    that column as "where this row's copy belongs", and rewriting it to the
    path somebody dragged the copy to would make each of them read a drag
    as a filing. So where the bytes *are* is a sentence on the row, and this
    is its reader (the scanner keeps the wanderer out of the count of
    whatever request it sits in). None for a row that is not ``FILE_MOVED``,
    and for one whose bytes are nowhere in the firm's folder at all.
    """
    if entry.decision != FILE_MOVED:
        return None
    found = _MOVED_TAIL.match(entry.reason)
    return found.group("now") if found else None


def _without_moved_sentence(reason: str) -> str:
    """The Reason without the moved sentence this pass is replacing.

    What a row said before it moved - the routing reason, a person's own
    sentence, whatever it was - is what the next moved sentence is appended
    to, so a row that has been dragged about does not accumulate one
    "no longer holds" after another for the same copy. A person's mark
    after it (decision 146) stays, after what came before (decision 157).
    """
    base, pattern, _sentence, marks = _moved_part(reason)
    return f"{base}{marks}" if pattern is not None else reason


def _before_the_moved_sentence(reason: str, sentence: str) -> str:
    """``sentence`` added to a Reason, before the moved sentence it ends
    with where it ends with one (decision 157), so :func:`moved_to` and
    :func:`both_gone` read that row as they did: a sentence appended after
    it would hide where the copy is from both."""
    base, pattern, moved, marks = _moved_part(reason)
    if pattern is None:
        return f"{reason}; {sentence}"
    return f"{base}; {sentence}; {moved}{marks}"


def _says_it_is_nowhere(entry: IndexEntry) -> bool:
    """Whether this row already says its bytes are nowhere in the folder -
    the original safe (decision 109) or gone too (decision 157)."""
    if entry.decision != FILE_MOVED:
        return False
    return _moved_part(entry.reason)[1] in (_MOVED_GONE_TAIL, _BOTH_GONE_TAIL)


def both_gone(entry: IndexEntry) -> bool:
    """Whether this row says its working copy and its original are both
    gone (decision 157, ruling B5), and a person has not yet marked it
    missing.

    The scanner reads it to hold the request firm-side with
    ``reasons.COPY_AND_ORIGINAL_GONE`` rather than decision 110's
    put-it-back wording, the app to offer Mark missing, and Mark missing to
    accept the row's own request. Read off the row's own sentence
    (:data:`BOTH_GONE_SENTENCE`), behind any marks a person added.
    """
    return (entry.decision == FILE_MOVED and bool(entry.prepared_location)
            and _moved_part(entry.reason)[1] is _BOTH_GONE_TAIL)


def marked_missing(entry: IndexEntry) -> bool:
    """Whether a person marked this row's own request missing (decision 157,
    ruling B6): a ``FILE_MOVED`` row that names no working copy.

    Mark missing takes the row's claim on its copies away - its Prepared
    Location, its other copies and what it answered - so the row stays on
    the record and counts for nothing: the sweep never makes its copy again
    or flags it, the scanner reads no copy of it, the client README leaves
    it out, and the same bytes sent again are filed as a new arrival.
    Nothing else ever writes a ``FILE_MOVED`` row without a copy, so the
    shape is the mark.
    """
    return entry.decision == FILE_MOVED and not entry.prepared_location


# --------------------------------------------------- an interrupted move ----

#: What the row says when the place an interrupted step was putting its
#: working copy holds a different file. The detail of
#: :data:`tracker.reasons.INTERRUPTED_MOVE`, composed here because the
#: filer is what knows the paths; each name is said once, so the reader
#: below can be derived from this very template.
INTERRUPTED_MOVE_DETAIL = ("{name} at {to}, which now holds a different file ({size} KB) - "
                           "the original is safe in {pbc}")
_INTERRUPTED_TAIL = re.compile(
    "^(?P<base>.*); " + as_pattern(
        reasons.INTERRUPTED_MOVE.template,
        listed=as_pattern(INTERRUPTED_MOVE_DETAIL, name=r".+?", to=r"(?P<to>.+?)",
                          size=r"[\d.]+", pbc=r".+?"),
    ) + "$",
    re.DOTALL,
)


def interrupted(entry: IndexEntry) -> tuple[str, str] | None:
    """``(path, sentence)`` of the step that was interrupted putting this
    row's copy somewhere, or None: the path it was putting it at, and the
    interrupted-step sentence the row ends with.

    The file at that path is not this row's - that is the whole of why the
    row parked - and it is not the request's either: nothing on the record
    filed it, and counting it would be the corruption decision 109's sweep
    exists to stop, with a truncated copy standing in for the document the
    client sent. So the scanner keeps it out of the count and says the
    firm-side sentence instead, exactly as it does for a copy somebody
    dragged (:func:`moved_to`). The sentence is read off the row rather
    than written again, so the request's note and the row's Reason are one
    sentence.

    Only while the row is still parked. Once a person has filed it, set it
    aside or sent it back, what sits in that folder is a file they have
    seen, and the sweep goes on naming it until they take it out.
    """
    if entry.decision != NEEDS_REVIEW:
        return None
    found = _INTERRUPTED_TAIL.match(entry.reason)
    return (found.group("to"), entry.reason[len(found.group("base")) + 2:]) if found else None


# --------------------------------------------------- the row's own bytes ----


def holds_the_row(path: Path, digest: str) -> bool:
    """Whether this file is here, readable now, and the row's own bytes.

    A person's click, not the unchanged-tree path: the file is read rather
    than remembered, because what is about to be moved is proved in the
    moment it is moved. A placeholder is never read (hashing one would make
    the sync client download it); the caller refuses first.

    Public because it is the one proof of a row's bytes: ``tracker.store.verify``
    (decision 159) holds every recorded original and working copy to it.
    """
    return path.is_file() and not is_cloud_placeholder(path) and sha256_of(path) == digest
