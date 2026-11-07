"""Tell the client what has arrived: the README's received list, and the
refresh that rewrites the README from it.

Decision 130. The client README acknowledges what has arrived, and the
index is the one source of it: nothing new is stored, no counter and no
copy, so the README is a rendering of the record. This module reads that
rendering out of the record and has it written, in two parts, each
upholding the decision rows it names:

- **The received list** (decisions 130, 94, 146, 157, 160 and 168).
  :func:`received_for` reads each return's index and request list once and
  answers plain data (:class:`tracker.records.Received`). A Filed or File
  Moved row (:data:`_RECEIVED_DECISIONS`) is **Received** once per request
  it satisfied (:func:`_requests_of`), under the request's own label; an
  also-filed copy's request is read from the copy's own name
  (:func:`_request_of_copy`, decision 168), and a name no request of
  today's list provably names reads ``tracker.scaffold.OTHER_DOCUMENT``.
  Each request a consolidated statement answers is Received as inside the
  statement's own request (decision 146). A Needs Review row is **Under
  Review**, counted by the day it arrived (:func:`_day_of`) and never
  named. A row a person marked missing is not counted
  (:func:`_counts_as_received`, decision 157), and a save of the list asks
  the same rule.
- **The refresh** (decisions 130 and 193). :func:`refresh_household_readme`
  is the one call every caller makes: the household pass once after its
  sort, the rollover after it rolls a household, and the app after every
  action that creates or edits a return or changes a document's row. It
  reads :func:`tracker.scaffold.readme_returns` once and hands that one
  read to :func:`received_for` and :func:`tracker.scaffold.write_readme`,
  under the household README's lock, and it never raises: a failure is
  logged in full and said by class (:data:`README_NOT_REWRITTEN`).

**Why it is its own module** (SPEC-architecture-p4 P4.8, P334; the
architecture audit's A-1, step 5). This code sat in the filer, and none of
it sorts: it reads the record that a pass and a person's actions wrote, and
renders what the client is told. The filer itself never calls the refresh;
the runner calls it after the household's pass, the rollover after it rolls
a household, and the API after each action, and the rollover reached the
sorter only to call it. Nothing here moves, copies, removes or records a
file. The one file it has written is the client's README, and only
through the scaffold's one composer (decision 130); nothing here reads a
name the filer defines. A person's actions (:mod:`tracker.actions`) import
the two names their ``documents_by_request`` reads, :func:`_counts_as_received`
and :func:`_requests_of`, so that a save of the list and the README count a
received document by one rule.

**Why it sits at layer 3.** It reads :mod:`tracker.copies` (layer 2: the
household README's lock, ``_readme_lock``, and ``_AN_EXTENSION``, what a
file name's suffix must look like), the index, the request list, the
record types and the scaffold (layer 1), and the lock's release and the
error log (layer 0). It may import nothing above layer 2 and nothing of
the filer, at load time or at call time: a person's actions, the runner and
the API import it at load time, and the rollover at call time. Layer 2 would pass
the layer test too; layer 3 keeps it beside the filer and the pass it
serves, and keeps layer 2 to what a reading, a routing or a copy needs
(SPEC-architecture-p4 section 2.1). The lock itself stays in
:mod:`tracker.copies`, with the stranded-temp sweep that reads it (P331).

**Every reader asks this module.** A person's actions import from here only
what their own code reads, and offer none of it on; the runner, the API and
the rollover import the refresh from here. A stand-in follows
the name's readers (the audit's A-4): one for a name this module reads as a
global is set on this module. So ``received_for``, ``readme_returns`` and
``write_readme`` are set here alone, ``read_index`` and ``load_manifest``
here beside the filer and the others that read them, on every loop that
sets them on the filer, and one on the refresh, which the rollover imports
at call time, is set here too.

**Why it logs as ``tracker.filer``** (SPEC-architecture-p4 section 2.1).
The run log and the error log print each line's logger name, so a name of
this module's own would change the lines a person and the office read. It
is the same logger object as the filer's, so no handler and no test sees a
difference.

The comments and docstrings below came with the code, word for word. Where
one names the pass, the filer or a function of the filer's, that is the
caller it describes; the code it describes is here.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence
from pathlib import Path

from tracker import errors
from tracker.copies import _AN_EXTENSION, _readme_lock

# The index's words and its readers live in tracker/index.py (P319).
from tracker.index import FILE_MOVED, FILED, NEEDS_REVIEW, marked_missing, read_index
from tracker.locking import release_lock
from tracker.manifest import LABEL_SEPARATOR, RequestItem, load_manifest
from tracker.records import IndexEntry, Received, ReceivedLine, UnderReview, identifier_key
from tracker.scaffold import OTHER_DOCUMENT, readme_returns, sanitize_component, write_readme

# The filer's logger, by its name (SPEC-architecture-p4 section 2.1): the run
# log and the error log print each line's logger name, so a name of this
# module's own would change the lines a person and the office read. It is the
# same logger object, so no handler and no test sees a difference.
log = logging.getLogger("tracker.filer")


# ------------------------------------------------- what the client is told ----
# Decision 130. The client README acknowledges what has arrived. The index
# is the one source of it: nothing new is stored, no counter and no copy,
# so the README is a rendering of the record and cannot drift from it.


#: The decisions a client is told a document was **Received** under: it was
#: confirmed into its request. A working copy moving afterwards
#: (``FILE_MOVED``) is the firm's business, not the client's.
_RECEIVED_DECISIONS = (FILED, FILE_MOVED)


def _day_of(stamp: str) -> dt.date | None:
    """The date part of a row's received stamp, or ``None`` where the stamp
    does not read as one - never a guessed day."""
    try:
        return dt.date.fromisoformat(str(stamp)[:10])
    except ValueError:
        return None


def _request_of_copy(name: str, items: Sequence[RequestItem]) -> str:
    """The request an ``also_filed`` copy's own name names, or ``""``.

    Read from the copy's file name since decision 168, by the test decision
    130 applied to its request folder until then, and only what the name
    can prove (130, the review's F1): it begins with the request's
    identifier followed by ``LABEL_SEPARATOR`` - which the canonical prefix
    (``A01 - W-2``, the identifier and the short name) always does, and is
    the one shape a working copy is made in and a person renames within.
    Or its stem is the identifier alone, or the identifier followed by
    `` (`` - ``A01.pdf``, ``A01 (2).pdf``: a copy whose short name decision
    131's room cut away whole on a row with no period (the review of 168,
    N-4). A bare prefix proves nothing: once ``A01-B`` is deleted from the
    list, ``A01-B - Loan - TY2025.pdf`` starts with ``A01`` too, and the
    README would tell the client their W-2 arrived. The longest identifier
    that fits wins, as it does for every file (``tracker.scaffold.owner_of``).
    Without case, as Windows compares names.
    """
    name = name.strip().casefold()
    stem = Path(name).stem if _AN_EXTENSION.fullmatch(Path(name).suffix) else name
    separator = LABEL_SEPARATOR.casefold()
    best = ""
    for item in items:
        identifier = sanitize_component(item.identifier).casefold()
        if not identifier or len(item.identifier) <= len(best):
            continue
        if (name.startswith(identifier + separator) or stem == identifier
                or stem.startswith(identifier + " (")):
            best = item.identifier
    return best


def _requests_of(entry: IndexEntry, items: Sequence[RequestItem]) -> list[str]:
    """Every request a filed row satisfied: its identifier, then one per
    ``also_filed`` copy (decision 94).

    ``also_filed`` holds the copies' locations, not their requests, so each
    is read back from the copy's own file name by :func:`_request_of_copy`
    (decision 168; from the request folder it sat in until then). A name
    no request of today's list provably names answers ``""``, which the
    README says as :data:`OTHER_DOCUMENT` - never a guessed request. A copy
    recorded in a request folder before 168 is read by its name too, and
    its name was always made in the same shape.
    """
    found = [entry.identifier]
    for location in entry.filed_locations[1:]:
        found.append(_request_of_copy(location.rsplit("/", 1)[-1], items))
    return found


def received_for(returns: Sequence) -> Received:
    """What has arrived for these returns, as the client README says it
    (decision 130): one index read and one request-list read per return,
    plain data out.

    Each of ``returns`` is a return folder, or a return as
    :func:`tracker.scaffold.readme_returns` read it (its ``path`` and
    ``items``), whose list is then not read a second time.

    - ``Filed`` and ``File Moved`` are **Received**, once per request the
      document satisfied, under the request's own label - the words the
      client read under *REQUESTED, NOT YET RECEIVED* - and never the
      client's file name or the firm's working name. A request no longer on
      the list reads :data:`OTHER_DOCUMENT`. Each request the row's Also
      Answers cell names (decision 146) is Received too, with the
      statement's own request as its ``inside``; the client's README says it
      as included in their consolidated brokerage statement
      (``reasons.IN_CONSOLIDATED_CLIENT``, Jason's Q-L), naming no request.
    - ``Needs Review`` is **Under Review**, counted by the day it arrived and
      never named: its only name is the client's own.
    - ``Duplicate``, ``Not Requested`` and anything else is not shown, and
      neither is a row a person marked missing because its working copy and
      its original were both gone (decision 157, :func:`marked_missing`):
      the letter asks for that document again, and the README agrees.

    A document this household's inbox fed into another household's return
    - by a person's hand-over, the only road across since decision 204 -
    is in that return's index and so on that household's list, never on
    this one (decision 132's F-4 ruling).
    """
    lines: list[ReceivedLine] = []
    waiting: dict[dt.date | None, int] = {}
    for one in returns:
        if isinstance(one, (str, Path)):
            folder, items = Path(one), None
        else:
            folder, items = Path(one.path), one.items
        entries = read_index(folder)
        if not entries:
            continue
        if items is None:
            items = load_manifest(folder)
        # Without case, as the status and the letter join a row to its
        # request (``records.identifier_key``), and under the list's own
        # spelling: a request respelt C01 -> c01 is the same request here
        # too, and the README no longer says "not received" of what the
        # letter counts as received (decision 160, the audit's D-8).
        requests = {identifier_key(item.identifier): item for item in items}
        for entry in entries:
            day = _day_of(entry.received)
            if _counts_as_received(entry):
                for identifier in _requests_of(entry, items):
                    item = requests.get(identifier_key(identifier))
                    lines.append(ReceivedLine(return_path=folder,
                                              label=item.label if item else OTHER_DOCUMENT,
                                              day=day,
                                              identifier=item.identifier if item else ""))
                # A consolidated statement answers other asked requests
                # without a copy (decision 146): each is received, said as
                # inside the statement's own request. A request no longer
                # on the list is not said at all - "Other document" would be
                # a second line for the one document the line above names.
                # Joined without case, as the line above (decision 160).
                host = requests.get(identifier_key(entry.identifier))
                for identifier, _sections in entry.answered:
                    item = requests.get(identifier_key(identifier))
                    if item is not None:
                        lines.append(ReceivedLine(return_path=folder, label=item.label,
                                                  day=day, identifier=item.identifier,
                                                  inside=host.label if host else OTHER_DOCUMENT))
            elif entry.decision == NEEDS_REVIEW:
                waiting[day] = waiting.get(day, 0) + 1
    return Received(
        lines=tuple(lines),
        under_review=tuple(UnderReview(day=day, count=n) for day, n in waiting.items()),
    )


#: What a pass or an app action says when the client's README could not be
#: rewritten (decision 193): by class, never by the text, which can name a
#: client's folder; the whole of it goes to the error log.
README_NOT_REWRITTEN = "the client's README could not be rewritten this time ({kind})"


def refresh_household_readme(household_dir: Path | str, *,
                             said: list[str] | None = None) -> Path | None:
    """Rewrite one household's client README from the record - **the one
    call every caller makes** (decision 130): the household pass once after
    its sort, the rollover after it rolls a household, and the app after
    every action that creates or edits a return or changes a document's row.

    The README speaks for the active returns of the household's one open
    year, read once (:func:`tracker.scaffold.readme_returns`) and handed to
    :func:`received_for` and :func:`tracker.scaffold.write_readme` both
    (the review's F3); ``write_readme`` renders and writes only when the
    text changed. With two open years it is left as it is.

    **Under the household README's lock** (:data:`tracker.copies.README_LOCK_FILENAME`,
    the review's F2), from the read to the write: two refreshes of one
    household - the pass and an app action, or two app actions - would
    otherwise interleave, and the one that read the older record could
    write last. A refresh waits up to :data:`tracker.copies.README_LOCK_WAIT_SECONDS` for
    the other to let go, then reads the record itself; one still busy
    after that skips with a log line, and the holder writes.

    **Never raises.** The README is client-visible and cosmetic; a failure
    is logged in full and, when the caller hands ``said``, said there by
    class (:data:`README_NOT_REWRITTEN`, decision 193), and the caller goes
    on. A refresh skipped because another holds the README's lock says
    nothing: the holder writes.
    """
    household_dir = Path(household_dir)
    try:
        lock = _readme_lock(household_dir)
        if lock is None:
            log.warning("The README of %s is being refreshed by another run, which "
                        "writes it; this refresh is skipped", household_dir.name)
            return None
        try:
            returns = readme_returns(household_dir)
            if returns is None:
                return None
            return write_readme(household_dir, received_for(returns), returns=returns)
        finally:
            release_lock(lock)
    except Exception as exc:
        kind = errors.error_class(exc)
        errors.keep("filer: the README refresh", exc, name=household_dir.name)
        log.warning("Could not refresh the README of %s (%s); carrying on",
                    household_dir.name, kind)
        if said is not None and (sentence := README_NOT_REWRITTEN.format(kind=kind)) not in said:
            said.append(sentence)
        return None


def _counts_as_received(entry: IndexEntry) -> bool:
    """Whether a row is one the client README and a save of the list count
    as a document the client sent: Filed or File Moved (decision 130), and
    not a row a person has marked missing (decision 157)."""
    return entry.decision in _RECEIVED_DECISIONS and not marked_missing(entry)
