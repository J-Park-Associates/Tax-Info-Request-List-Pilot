"""The records the system keeps, apart from the behaviour that writes them.

Every fact this package holds about a client's documents travels as one of
a handful of small frozen dataclasses: an index row, the evidence behind a
verdict, a routing decision, the engagement's own details, one identifier's
status. Until now each of them lived in the module that happened to write
it first - ``IndexEntry`` in the filer, ``Evidence`` in the content check,
``Routing`` in the router, ``EngagementInfo`` in the manifest - so a module
that only wanted to *name* a record had to import the module that opens
workbooks, walks folders and takes the engagement lock to produce it. The
structural review of 2026-09-18 called that D4: the record and the
behaviour are one file, so the import graph says every reader depends on
every writer, and nothing can be read back without the machinery that
wrote it.

This module is the record half. **Nothing here reads a file, opens a
workbook, takes a lock or knows where the engagement folder is.** It holds
the shapes, the names of their values, and each record's own
serialisation - the cell format for the Evidence column, the JSON an index
row is stored as, the identity a row is recorded under - because those are
facts about the record and not about the file it lands in. So is the other
direction: :func:`as_pattern` turns a sentence's own template into the
pattern that reads it back, because how a sentence the machine wrote is
read is a fact about the shape it was stored in, and two modules read one
back (decisions 108 and 109) without retyping a word of either. The writers
stay where they are: the journal is written by :mod:`tracker.filer`, the
scanner and :mod:`tracker.manifest`, which is where the lock and the
atomic replace belong.

It sits at layer 1 and imports nothing of the package (``tests/test_layers.py``
pins that), so every layer above may name a record without reaching for the
module that produces it. :mod:`tracker.manifest` imports it, which is an
in-layer edge and allowed; nothing here imports the manifest, so the edge
cannot become a cycle.

**``RequestItem`` stays in the manifest.** It is not a record of what the
machine decided - it is the *schema* of the list a person edits, made
out of plain values with the manifest's own defaults, validation and
column names, and it means nothing away from that list. The
same goes for ``FileError``, ``FileReport`` and ``ContentResult``: they are
one run's report of what it did, produced and consumed inside the module
that did it, and never stored.

Its **rows** travel all the same since decision 103: the person's half of
a request row is what a ``rules_changed`` event carries - and the
``rules_imported`` lines journals from before decision 104 carry - so
:data:`RULE_FIELDS`, :func:`rule_to_json` and :func:`rule_from_json` are
here - the serialisation is a fact about the record, the parsing is a fact
about the list, and the two live where each belongs. The pair is
deliberately duck-typed on the field names rather than on the class, so
this module still imports nothing of the package.

**The old names still work where a module still uses them.** A module a
record left keeps a re-export of the names it still reads - ``from
tracker.filer import IndexEntry`` resolves to exactly this class, the same
object, not a copy. The names nothing used any more (the manifest's copies
of the details' field table and the yes/no words) went with decision 104;
``tests/test_records.py`` lists what is still offered.

**What this is for.** The store of decision 101 reads and writes these
records; it imports them from here and never from :mod:`tracker.filer`,
because a store that had to import the filer to name a row would import
the module that moves the client's files.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import re._parser as _re_parser
from dataclasses import MISSING, asdict, dataclass, field, fields
from pathlib import Path

# ------------------------------------------------------------ derivations ----

#: The three words a derivation of the record may be described in. A
#: derivation is never simply "there": a person, and the app, have to know
#: whether the thing in front of them still describes what is recorded. The
#: page (:func:`tracker.view.view_state`) says it of itself, and the store
#: (:func:`tracker.store.state`) says it of one engagement's rows; they are
#: the same three answers about the same two stamps, so the words live here
#: rather than in either of them. Decision 101 moved them out of the view.
CURRENT = "current"
BEHIND = "behind"
UNKNOWN = "unknown"
STATES = (CURRENT, BEHIND, UNKNOWN)

#: What the machine keeps about an engagement, in the words the owner
#: settled on 2026-09-19: **the record** is the journal
#: (``tracker.ledger``) and the store (``tracker.store``) together; the
#: *ledger* is the journal alone and the *store* is the database alone.
#: Standing rule 2 says "every move is recorded in the record" and fills
#: the phrase from here, because it used to name the index workbook and
#: there is no such file any more (decision 102). One home for the phrase: the
#: rule, the runbook, the README and ``docs/storage.md`` all use these
#: words and ``tests/test_single_source.py`` holds them to it.
THE_RECORD = "the record"

# ------------------------------------------------------ a sentence read back ----


def as_pattern(template: str, **groups: str) -> str:
    """A note's template as a regular expression: every word of it escaped,
    every ``{name}`` the pattern given for it.

    The words have one home - the constant the template is - and a reader of
    a sentence the machine wrote never retypes them. Two readers use it, and
    both derive their pattern from the very template that wrote the sentence,
    so rewording one moves its reader with it:
    :mod:`tracker.scanner` reads the regression sentence off the front of a
    row's validation notes (decision 108), and :mod:`tracker.filer` reads the
    path a moved working copy is at now off the end of its Reason
    (:func:`tracker.filer.moved_to`, decision 109).

    It belongs here because how a sentence the machine wrote is read back is
    a fact about the shape a record is stored in, not about either reader.
    """
    # re.split with one group alternates: words, name, words, name, words.
    words_and_names = re.split(r"\{(\w+)\}", template)
    return "".join(groups[part] if i % 2 else re.escape(part)
                   for i, part in enumerate(words_and_names))


# ---------------------------------------------------------------- evidence ----

#: Which of the manifest row's rules found the term. ``required`` and ``any``
#: are the row's keyword lists, ``date`` its Period check, ``filename`` the
#: router's by-name fallback, ``refused`` a tier-2 refusal travelling as
#: evidence (the Reason's code) and ``name`` the people list of the return
#: the document was judged against (decision 128). One list, named once, so
#: the router, the index and the app's vocabulary all say the same words.
RULE_REQUIRED = "required"
RULE_ANY = "any"
RULE_DATE = "date"
RULE_FILENAME = "filename"
RULE_REFUSED = "refused"
#: The name tier (decision 128). Not a rule of the request row at all - it
#: is the return's own people list, checked after the request lists have
#: accepted a document - but it is evidence of the same kind: a term the
#: firm typed, found in the document, in a place the record can name. It
#: rides the Evidence cell rather than a column of its own, and
#: ``tracker.review`` ranks it above every keyword, because a name is the
#: strongest thing a page can say about *whose* it is.
RULE_NAME = "name"
EVIDENCE_RULES: tuple[str, ...] = (
    RULE_REQUIRED, RULE_ANY, RULE_DATE, RULE_FILENAME, RULE_REFUSED, RULE_NAME,
)

#: Where in the document the term was said. ``title`` is within
#: ``content_check.TITLE_CHARS`` of the start - a form printing its own
#: name; ``footer`` is the last ``content_check._FOOTER_LINES`` non-blank
#: lines of a page, where a form repeats its number on every copy;
#: ``first_page`` is the rest of page 1 and ``deep`` is anything further
#: in, which is the weakest place a keyword can be said and the one a
#: person most wants to see named. Evidence about a file's name or a
#: refusal has no place and carries "".
WHERE_TITLE = "title"
WHERE_FIRST_PAGE = "first_page"
WHERE_FOOTER = "footer"
WHERE_DEEP = "deep"
EVIDENCE_PLACES: tuple[str, ...] = (
    WHERE_TITLE, WHERE_FIRST_PAGE, WHERE_FOOTER, WHERE_DEEP,
)


@dataclass(frozen=True, slots=True)
class Evidence:
    """One reason a verdict went the way it did.

    ``term`` is the firm's own word - a keyword off the manifest row, the
    row's Period, a Reason's code - never a word read out of the client's
    document. ``page`` is 1-based, counted from the page breaks
    ``content_check._extract_pdf`` writes, and 0 where a page means nothing
    (a file name, a refusal).
    """

    rule: str
    term: str
    where: str = ""
    page: int = 0


#: How one Evidence is written into a single cell, and how the whole record
#: for a decision is: ``A01: 1098@title:1 required, TY2025@first_page:1
#: date; L01: 1098-t@title filename``. Compact because it shares one
#: column with every other candidate's evidence, and parsed back by
#: :func:`parse_evidence` so the shape has one owner rather than a writer
#: here and a reader in the app. The page is left off when it is 0. Terms
#: are catalog words and file names, which carry none of these separators.
_EVIDENCE_AT = "@"
_EVIDENCE_PAGE = ":"
_EVIDENCE_SEP = ", "
_RECORD_SEP = "; "
_RECORD_AT = ": "


def format_evidence(record: dict[str, tuple[Evidence, ...]]) -> str:
    """The evidence behind one decision, as the index's Evidence cell."""
    return _RECORD_SEP.join(
        identifier + _RECORD_AT + _EVIDENCE_SEP.join(_format_one(e) for e in found)
        for identifier, found in record.items() if found
    )


def _format_one(evidence: Evidence) -> str:
    page = f"{_EVIDENCE_PAGE}{evidence.page}" if evidence.page else ""
    return f"{evidence.term}{_EVIDENCE_AT}{evidence.where}{page} {evidence.rule}"


def parse_evidence(text: str) -> dict[str, tuple[Evidence, ...]]:
    """An Evidence cell read back, exactly as :func:`format_evidence` wrote it.

    Lenient about what it cannot understand: the index is an audit trail a
    person may have typed into, and half a record read is better than a
    row that will not load.
    """
    record: dict[str, tuple[Evidence, ...]] = {}
    for group in (text or "").split(_RECORD_SEP):
        identifier, _, listed = group.partition(_RECORD_AT)
        identifier = identifier.strip()
        if not identifier or not listed.strip():
            continue
        found = tuple(e for e in (_parse_one(part) for part in listed.split(_EVIDENCE_SEP))
                      if e is not None)
        if found:
            record[identifier] = record.get(identifier, ()) + found
    return record


def _parse_one(part: str) -> Evidence | None:
    body, _, rule = part.strip().rpartition(" ")
    term, at, place = body.rpartition(_EVIDENCE_AT)
    if not rule or not at or not term:
        return None
    where, _, page = place.partition(_EVIDENCE_PAGE)
    return Evidence(rule, term, where, int(page) if page.isdigit() else 0)


# --------------------------------------------------------------- index row ----

#: The column both records are joined by: the manifest's request rows carry
#: it and so does every index row, which is how a filed document is tied
#: back to the request that asked for it. Named here rather than beside the
#: manifest's other column headers because both layouts need it and a
#: second copy of the word would let one table drift from the other;
#: :mod:`tracker.manifest` imports it and lists it first in ``HEADERS``.
COL_IDENTIFIER = "Identifier"


def identifier_key(identifier: str) -> str:
    """The identity two readings of one request are matched on.

    Without case, because a request's identifier becomes the prefix of a
    Windows folder name and Windows folder names are case-insensitive: a
    list holding both spellings would have two rows claiming one folder.
    Every reading that joins a status to a request folds it this way - the
    manifest refusing a duplicate row, a save diffing the list against
    what the store holds, and the store keying a status to its request -
    so the rule is worded once here rather than as a ``.lower()`` at each
    of them.
    """
    return identifier.strip().lower()


#: How candidate identifiers are joined in the Candidates cell, and the
#: other working copies in Also Filed.
CANDIDATE_SEP = ", "

#: How the Also Answers cell (decision 146) sets one answered request apart
#: from the next, and brackets the sections that answered it:
#: ``A02 (1099-int, 1099-div); A04 (1099-misc)``. A request's identifier
#: never holds a bracket or a semicolon, and a section is the row's own
#: keyword - a catalog word, never a word of the document - so the cell
#: reads back exactly as it was written.
ANSWER_SEP = "; "
_ANSWER = re.compile(r"^\s*([^()]+?)\s*(?:\((.*)\))?\s*$")

#: One request a consolidated statement answers without a copy (decision
#: 146): its identifier, and the sections of the statement that answer it -
#: the row's own form-number keywords that accepted the statement, such as
#: ``("1099-int", "1099-div")``. Empty where the row accepted it on a phrase
#: that names no form; it is answered all the same, by one section.
Answer = tuple[str, tuple[str, ...]]


def format_answers(answers: tuple[Answer, ...] | list[Answer]) -> str:
    """The Also Answers cell, written from the answers a routing carried."""
    return ANSWER_SEP.join(
        f"{identifier} ({CANDIDATE_SEP.join(sections)})" if sections else identifier
        for identifier, sections in answers
    )


def parse_answers(text: str) -> tuple[Answer, ...]:
    """The Also Answers cell read back, exactly as :func:`format_answers`
    wrote it; lenient, as :func:`parse_evidence` is, about a part it cannot
    read."""
    found: list[Answer] = []
    for part in (text or "").split(ANSWER_SEP.strip()):
        match = _ANSWER.match(part)
        if not match or not match.group(1).strip():
            continue
        sections = tuple(s.strip() for s in (match.group(2) or "").split(CANDIDATE_SEP.strip())
                         if s.strip())
        found.append((match.group(1).strip(), sections))
    return tuple(found)


def answer_count(answer: Answer) -> int:
    """How many documents one answer counts toward its request: one per
    section that answered it, and one where a phrase did (decision 146,
    the owner's rule that a consolidated statement satisfies what each
    statement inside it would on its own)."""
    return max(1, len(answer[1]))


@dataclass(frozen=True, slots=True)
class IndexEntry:
    """One row of the index — the audit trail for one original file.

    The fields ARE the columns: their order is the column order, the
    ``INDEX_LAYOUT`` table below gives each its header and width (the
    width is what the Status Report's table inherits), so a column added
    here is one edit.
    Nothing stored here is a copy of something stored elsewhere: the
    working copy's name is the basename of its location, and the request's
    Document lives in the manifest, joined by Identifier.
    """

    received: str
    original_name: str
    size_kb: float
    digest: str
    identifier: str
    prepared_location: str
    pbc_location: str
    decision: str
    reason: str
    candidates: str = ""     # identifiers the router named, for a person to choose from
    #: Why each candidate was one: the keywords that matched and where they
    #: were said, written as format_evidence() writes it. The Reason
    #: sentence says what was decided; this says what it was decided on,
    #: and a parked row carries it as much as a filed one, because the
    #: parked row is the one a person has to work out.
    evidence: str = ""
    #: The *other* working copies this one original has (decision 94): a
    #: page that prints two forms' own names is two documents, and each
    #: form's request gets a copy of it. ``prepared_location`` names the
    #: first, this names the rest, and the Reason sentence names the
    #: requests - so the row stays one row for one original, which is what
    #: the record keys on, what the client's folder holds one of, and what
    #: a person unfiles in one click. Empty on every ordinary row, which
    #: is every row written before decision 94.
    also_filed: str = ""
    #: Where the email or zip this document came out of rests (decision
    #: 143): the container row's own location, relative to the return as
    #: every location is. Empty on every document that arrived on its own,
    #: which is every row written before decision 143. The row's own
    #: ``pbc_location`` is the attachment's file, taken out into the
    #: household-year's hidden folder in the private tree, so the key stays
    #: one location per row and every reader that holds an original to its
    #: fingerprint reads an attachment unchanged.
    container: str = ""
    #: The other requests this one document answers without a copy of its
    #: own (decision 146, the owner's answer to 146-Q): a broker's
    #: consolidated statement files whole under the request its 1099-B
    #: asks for, and each other asked request on the return that one of its
    #: sections would satisfy alone counts it as received. Written by
    #: :func:`format_answers` - the request and the sections that answered
    #: it - and read by the status, the letter and the client's received
    #: list through :attr:`answered`, so all of them read the one cell.
    #: Nothing is copied: one original, one working copy, one folder. A
    #: person takes one request back out of it by marking that request
    #: missing again. Empty on every other row, which is every row written
    #: before decision 146.
    answers: str = ""

    @property
    def answered(self) -> tuple[Answer, ...]:
        """The Also Answers cell read back (:func:`parse_answers`)."""
        return parse_answers(self.answers)

    @property
    def candidate_list(self) -> list[str]:
        """The router's candidates as the list they were joined from."""
        return [c for c in (part.strip() for part in self.candidates.split(CANDIDATE_SEP)) if c]

    @property
    def filed_locations(self) -> list[str]:
        """Every working copy this original has, in the order they were
        made: the one ``prepared_location`` names, then ``also_filed``'s.
        One row, one original, one list - the shape every reader that has
        to touch all of them (unfiling, the app's filed list, the status
        report) asks for, so none of them splits a cell of its own."""
        if not self.prepared_location:
            return []
        return [self.prepared_location] + [
            part.strip() for part in self.also_filed.split(CANDIDATE_SEP) if part.strip()
        ]

    @property
    def filed_names(self) -> list[str]:
        """The file name of each working copy - the basename of each of
        ``filed_locations``. The one place a location is cut to a name."""
        return [location.rsplit("/", 1)[-1] for location in self.filed_locations]

    @property
    def evidence_record(self) -> dict[str, tuple[Evidence, ...]]:
        """The Evidence cell read back, by candidate identifier."""
        return parse_evidence(self.evidence)

    @property
    def filed_as(self) -> str:
        """The working copy's file name - the basename of where it went.
        The first one, where decision 94 made several; ``filed_names`` is
        every one of them."""
        return next(iter(self.filed_names), "")

    def as_row(self) -> list[object]:
        return [getattr(self, f.name) for f in fields(IndexEntry)]


#: field name -> (column header, column width). One table, in field order.
INDEX_LAYOUT: dict[str, tuple[str, int]] = {
    "received": ("Received", 12),
    "original_name": ("Original Name", 40),
    "size_kb": ("Size KB", 9),
    "digest": ("SHA-256", 18),
    "identifier": (COL_IDENTIFIER, 10),
    "prepared_location": ("Prepared Location", 40),
    "pbc_location": ("PBC Location", 26),
    "decision": ("Decision", 14),
    "reason": ("Reason", 60),
    "candidates": ("Candidates", 14),
    "evidence": ("Evidence", 50),
    "also_filed": ("Also Filed", 40),
    "container": ("Came Inside", 30),
    "answers": ("Also Answers", 30),
}
assert tuple(INDEX_LAYOUT) == tuple(f.name for f in fields(IndexEntry))
INDEX_COLUMNS = tuple(header for header, _ in INDEX_LAYOUT.values())


def entry_to_json(entry: IndexEntry) -> dict:
    """An index row as it is stored: every field, by name.

    The one shape for it. The engagement's record writes it and
    :func:`entry_from_json` reads it back, so a field added to the row
    above is carried by both without another edit.
    A plain dict of the fields rather than ``dataclasses.asdict`` spelled
    out at each call site, because two call sites are two owners.
    """
    return {f.name: getattr(entry, f.name) for f in fields(IndexEntry)}


def entry_from_json(row: object) -> IndexEntry:
    """An IndexEntry from a stored row, ignoring keys a later version may add:
    a row for an original already moved must never be thrown away over a
    field this version does not know."""
    if not isinstance(row, dict):
        raise TypeError(f"index row is {type(row).__name__}, not an object")
    known = {f.name for f in fields(IndexEntry)}
    # A column a later version added holds nothing for a row written before
    # it (the store keeps what the line said: no such key). A field with a
    # default reads that as its default - ``container`` is ``""`` on a row
    # from before decision 143 - rather than as None.
    defaulted = {f.name for f in fields(IndexEntry) if f.default is not MISSING}
    return IndexEntry(**{key: value for key, value in row.items()
                         if key in known and not (value is None and key in defaulted)})


def ledger_key(entry: IndexEntry) -> str:
    """The identity the engagement's record keeps this row under.

    The index's own: where the client's preserved original is, which is what
    the fold keys on and what the app joins a review card back by. A row
    that names no original (only a record somebody built by hand has one)
    falls back to what else the row says about the document, so two such
    rows are not folded into one.

    It is still one location per row after decision 94, and that is why the
    index keeps one row for a page filed under several requests rather than
    one row per copy: two rows naming one preserved original would collide
    here, and the collision would be silent - the record would fold them
    into one. The copies are a column of that row
    (``IndexEntry.also_filed``), not rows of their own.
    """
    return entry.pbc_location or f"{entry.received}|{entry.original_name}|{entry.digest}"


# ------------------------------------------------------- what has arrived ----
# Decision 130. The client README acknowledges what has arrived, and these
# are the shapes it is told in: plain data read out of the index by
# ``tracker.filer.received_for`` (layer 3) and rendered by
# ``tracker.scaffold.write_readme`` (layer 1), which never reads the index
# itself. They live here because both of those may import this module, and
# because nothing about them is stored: the README is a rendering of the
# index, with no counter and no copy that could drift from it.


@dataclass(frozen=True, slots=True)
class ReceivedLine:
    """One document confirmed into one request, as the client is told it.

    ``label`` is the request's own label - the words the client read under
    *REQUESTED, NOT YET RECEIVED* - and never the client's file name nor
    the firm's working name. ``day`` is the date part of the row's received
    stamp, or ``None`` where the stamp does not read as a date.
    ``identifier`` is the request's, which takes it off that list; empty
    for a line said as "Other document", whose request is not on it.
    Required, so no caller can build a line that shows a request as
    Received while leaving it on the first list.
    """

    return_path: Path
    label: str
    day: dt.date | None
    identifier: str
    #: The label of the request whose consolidated statement answered this
    #: one without a copy (decision 146); the client's received list then
    #: says ``reasons.IN_CONSOLIDATED_CLIENT`` after the date, naming no
    #: request. Empty on every document that was filed under this request
    #: itself.
    inside: str = ""


@dataclass(frozen=True, slots=True)
class UnderReview:
    """How many documents that arrived on one day a person is looking at.
    Counted, never named: a parked document's only name is the client's own."""

    day: dt.date | None
    count: int


@dataclass(frozen=True, slots=True)
class Received:
    """Everything the README's *WHAT WE HAVE RECEIVED* section says. Both
    lists empty means the section is not there at all (decision 130, D-f)."""

    lines: tuple[ReceivedLine, ...] = ()
    under_review: tuple[UnderReview, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.lines or self.under_review)


# --------------------------------------------------------------- routing ----

#: What a routing decision rested on. There is one: the document's own
#: words. A file name was a tier of its own until decision 92 and is not
#: one any more, because nothing is filed on a name - what the name says
#: is kept as evidence for a person (``RULE_FILENAME``, which is what an
#: index row carries and is untouched), never as a tier.
EVIDENCE_CONTENT = "content"


@dataclass(frozen=True, slots=True)
class Routing:
    """Where one dropped file belongs, and why."""

    path: Path
    identifier: str | None          # None → needs human review
    reason: str                     # plain English, safe to show a client
    candidates: tuple[str, ...] = ()  # identifiers that accepted the file
    evidence: str = ""              # EVIDENCE_CONTENT | ""
    #: What each candidate's evidence actually was, by identifier: the
    #: keywords that matched, where they were said, the tier-2 reason that
    #: refused the file. ``evidence`` above says which *tier* the decision
    #: rested on and nothing more; this says why, and only for the
    #: identifiers the decision names, so the index's cell stays readable.
    evidence_record: dict[str, tuple[Evidence, ...]] = field(default_factory=dict)
    pending: bool = False           # still syncing; leave it where it is
    #: The *other* requests one document belongs to (decision 94, the
    #: owner's): a page that prints two forms' own names is two documents,
    #: and each form's request gets a working copy of it. Empty on every
    #: ordinary decision, which is nearly all of them - ``identifier`` is
    #: the first request either way, so a reader that knows only about it
    #: reads a real request and a real filing, never half a sentence.
    also: tuple[str, ...] = ()
    #: How long reading the document took, in seconds (decision 127), so
    #: the pass can name its slowest readings. It decides nothing: no
    #: reading is cut short for being slow, and a routing is what it is
    #: whether the reading took a tenth of a second or a minute.
    seconds: float = 0.0
    #: The other requests a consolidated statement answers without a copy
    #: (decision 146): each asked row on the return that accepted the
    #: statement beside the one it filed under, with the sections that
    #: answered it. Never a filing - ``filed_to`` does not name them, and
    #: nothing is copied into their folders - and empty on every other
    #: decision.
    answers: tuple[Answer, ...] = ()

    @property
    def routed(self) -> bool:
        return self.identifier is not None

    @property
    def filed_to(self) -> tuple[str, ...]:
        """Every request this document is filed under, in the order the
        page names their forms; empty when it is not filed at all."""
        return () if self.identifier is None else (self.identifier, *self.also)


# ---------------------------------------------------------------- people ----

#: What a person on a return can be (decision 128). A return's documents
#: are addressed to somebody - a taxpayer, a spouse, a dependent, a company,
#: the name a company trades under, whoever an account is held in the name
#: of, a decedent, a trust or estate, the fiduciary acting for one - and the
#: kind is what the editor labels the row with. It never changes a filing:
#: every kind's spellings are matched the same way.
PERSON_KINDS: tuple[str, ...] = (
    "taxpayer", "spouse", "dependent", "entity", "dba", "owner", "decedent", "trust", "fiduciary",
)
PERSON_KIND_LABELS = {"taxpayer": "Taxpayer", "spouse": "Spouse", "dependent": "Dependent",
                      "entity": "Entity (legal name)", "dba": "DBA or abbreviation",
                      "owner": "Owner (accounts held so)", "decedent": "Decedent",
                      "trust": "Trust or estate", "fiduciary": "Fiduciary"}
assert set(PERSON_KIND_LABELS) == set(PERSON_KINDS)

#: How few words a spelling may have, and the one way a name is cut into
#: them. A family name alone (``Park``) is a whole phrase inside ``Park
#: Landscaping LLC``, so a one-word spelling would confirm a business's
#: bank statement as the family's; two words is the floor everything that
#: reads a spelling holds to (``tracker.names``, the API's refusal, the
#: store's guard against a hand-edited journal).
MIN_SPELLING_WORDS = 2


def name_parts(text: str) -> list[tuple[str, int]]:
    """Each letters-and-digits word of a name, lower-cased, with where in
    ``text`` it begins.

    **The one cut.** Everything that is not a letter or a digit is a
    separator, so ``O'Brien``, ``Park, John A.`` and ``PARK JOHN A`` all
    come apart the same way and case and punctuation never decide whether
    a page names somebody. The offsets travel with the words because the
    matcher has to say *where* on the page a spelling was found
    (:data:`RULE_NAME` evidence) and the page is counted in the text the
    reader produced, not in the folded copy.

    It lives here rather than beside the matcher because it is a fact
    about the record - what a spelling's words are is what
    :data:`MIN_SPELLING_WORDS` counts, and this module imports nothing.
    """
    out: list[tuple[str, int]] = []
    word: list[str] = []
    start = 0
    for at, char in enumerate(text or ""):
        if char.isalnum():
            if not word:
                start = at
            word.append(char.lower())
            continue
        if word:
            out.append(("".join(word), start))
            word = []
    if word:
        out.append(("".join(word), start))
    return out


def name_words(text: str) -> tuple[str, ...]:
    """The words of a name, lower-cased, in order (:func:`name_parts`)."""
    return tuple(word for word, _at in name_parts(text))


def is_a_spelling(text: str) -> bool:
    """Whether ``text`` is long enough to be a spelling: two words or more."""
    return len(name_words(text)) >= MIN_SPELLING_WORDS


@dataclass(frozen=True, slots=True)
class Person:
    """One person a return is for, and the spellings their documents use.

    ``name`` is the display form, as a person typed it; ``spellings`` are
    the forms a document may print it in, proposed by the app and ticked
    by a person (:func:`tracker.names.propose_spellings`) - never inferred
    from a document and never one word.

    There is no family-name-first mark: a page printing the family name
    first is matched already, because the matcher reads punctuation as a
    space and ``Park John A`` and ``Park, John A.`` are therefore one
    spelling.

    Nothing here is read out of a client's document: a spelling is the
    firm's own term, exactly as a keyword is, which is why the matched one
    may be recorded as evidence.
    """

    kind: str                       # one of PERSON_KINDS
    name: str                       # as typed, the display form
    spellings: tuple[str, ...] = ()  # the confirmed spellings that match


def person_to_json(person: Person) -> dict:
    """One person as the record stores them: the fields, the spellings as a list."""
    return {"kind": person.kind, "name": person.name,
            "spellings": list(person.spellings)}


def person_from_json(raw: object) -> Person:
    """One stored person read back, refusing a shape no reader could use.

    A kind this version does not know, or a spelling of one word, is a
    line the matcher would either ignore or misfile on, so it is refused
    here - which is where :func:`tracker.store._refuse_a_malformed_line`
    sends a hand-edited journal's people to be judged.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"a person is {type(raw).__name__}, not an object")
    kind = str(raw.get("kind", ""))
    if kind not in PERSON_KINDS:
        raise ValueError(f"{kind!r} is not one of {', '.join(PERSON_KINDS)}")
    spellings = raw.get("spellings") or ()
    if isinstance(spellings, str):
        spellings = (spellings,)
    listed = tuple(str(one) for one in spellings)
    for spelling in listed:
        if not is_a_spelling(spelling):
            raise ValueError(f"{spelling!r} is one word; a spelling needs two or more")
    return Person(kind=kind, name=str(raw.get("name", "")), spellings=listed)


def people_from_json(raw: object) -> tuple[Person, ...]:
    """A return's people as the record holds them: a list of objects from a
    journal line, or the JSON text one column holds.

    SQLite cannot tell a JSON array in a text column from a string, so the
    text is read back here for the same reason a rule row's keywords are
    (:data:`RULE_LIST_FIELDS`).
    """
    if raw in (None, "", ()):
        return ()
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, (list, tuple)):
        raise ValueError(f"the people are {type(raw).__name__}, not a list")
    return tuple(person_from_json(one) for one in raw)


# ------------------------------------------------------------ engagement ----

#: The two yes/no words the engagement's details are described in: the
#: notes below are written from them and a record's own words are the
#: record's.
YES = "yes"
NO = "no"

#: The only kinds of address a reminder's link may be (decision 137, L5).
#: The link is pasted into a letter a client clicks; ``file:``, a mail
#: link or a script address is not an inbox, and a letter that opened one
#: would be the firm's letter doing it.
LINK_SCHEMES: tuple[str, ...] = ("http://", "https://")
#: What a link of any other kind is refused with, when the details are saved.
LINK_REFUSED = ("The link '{link}' is not a web address; a link must start with "
                "http:// or https://")


def link_problem(link: str) -> str:
    """:data:`LINK_REFUSED` for a link that is not a web address, or
    ``""`` - for one that is, and for no link at all."""
    text = str(link or "").strip()
    if not text or text.lower().startswith(LINK_SCHEMES):
        return ""
    return LINK_REFUSED.format(link=text)


@dataclass(frozen=True, slots=True)
class EngagementInfo:
    """The engagement's details: who this is for and how the run should treat it.

    Every field is optional. An engagement nothing has recorded details
    for reads as all defaults and is still processed.
    """

    # What each field is for is said once, in ENGAGEMENT_HELP below.
    client: str = ""
    name: str = ""
    link: str = ""
    due: dt.date | None = None
    #: The statutory date the return has to be filed by (decision 117).
    #: Blank is silence: the reminder never mentions a deadline nobody
    #: recorded. Added after ``due``; a stored record from before it reads
    #: as blank, as ``form`` does.
    filing_deadline: dt.date | None = None
    sender: str = ""
    firm: str = ""
    reminders: bool = True
    active: bool = True
    rolled_from: str = ""
    #: Which catalog the request list was cut from, as the catalog keys it.
    #: Blank on an engagement made before it was recorded, and blank is
    #: unknown to every reader - nothing refuses an engagement for it.
    form: str = ""
    #: Which household this return belongs to, which year it is for and
    #: what the return is called (decision 125). Filled at creation and at
    #: rollover from the folders they name, and **the record wins** over a
    #: folder somebody renamed: the registry processes the return as these
    #: three say and warns about the disagreement rather than renaming
    #: anything. Added last, so a record written before them reads as
    #: blank, as ``form`` does.
    household: str = ""
    tax_year: int | None = None
    return_name: str = ""
    #: Who this return is for, with the spellings their documents use
    #: (decision 128). Added last, so a record written before it reads as
    #: nobody - and a return that lists nobody parks every named request
    #: until a person adds them, which is the strict rule the owner asked
    #: for rather than a silent filing on keywords alone.
    people: tuple[Person, ...] = ()


#: What the return's own name is called and what it is for. Named here
#: because the details' table below carries it, and read back out of here
#: by the API's vocabulary, so the label a person reads in the editor and
#: the one the wizard's box carries are one string.
RETURN_NAME_LABEL = "Return"
RETURN_NAME_HELP = "the return's folder name, form first; the same name every year"

#: What the return's people list is called and what it is for (decision
#: 128). One home for both, read back by the editor's block and the
#: wizard's, so the words a person sees are the record's.
PEOPLE_LABEL = "People"
PEOPLE_HELP = ("who this return is for, with the spellings documents use; a named request "
               "files only where one of these is on the page")

#: The details' labels, in the order the editor and the README show them.
ENGAGEMENT_FIELDS = (
    ("Client", "client"),
    ("Engagement Name", "name"),
    ("Share Link", "link"),
    ("Due Date", "due"),
    ("Filing Deadline", "filing_deadline"),
    ("Sender", "sender"),
    ("Firm", "firm"),
    ("Reminders", "reminders"),
    ("Active", "active"),
    ("Rolled From", "rolled_from"),
    # Added last (decision 86); a stored record that lacks it reads as a
    # blank value (info_from_json ignores what it does not carry).
    ("Form", "form"),
    # The three the layout of decision 125 records: where this return sits
    # and what it is called. None of them is editable - the folders are
    # the names.
    ("Household", "household"),
    ("Tax Year", "tax_year"),
    (RETURN_NAME_LABEL, "return_name"),
    # Who the return is for (decision 128). Edited through its own block
    # rather than a text box: a person is a kind, a name, and the
    # spellings the app proposed and somebody ticked.
    (PEOPLE_LABEL, "people"),
)
#: field name -> the label, for messages that name a field.
ENGAGEMENT_LABELS = {field_name: label for label, field_name in ENGAGEMENT_FIELDS}
#: What the yes/no and Rolled From fields mean, said in the editor and in the README.
ENGAGEMENT_NOTES = {
    "reminders": f"{NO} = this client is not chased by email",
    "active": f"{NO} = the scheduled run skips this folder",
    "rolled_from": "written by the rollover; the engagement it names is no longer chased",
}
#: What each field is for, as the README and the editor tell it.
ENGAGEMENT_HELP = {
    "client": "greeting name in the reminder",
    "name": "label; the folder name if blank",
    "link": "pasted into the reminder",
    "due": "the date the reminder asks the client to send things by",
    "filing_deadline": ("the statutory filing date; named in the reminder from the third stage on; "
                        "blank = not mentioned (defaults from the form, weekends shifted; "
                        "holidays are yours to edit)"),
    "sender": "who the reminder is from",
    "firm": "the sign-off line and the client README's contact (typed once at setup)",
    "form": "which catalog the request list was cut from; blank if it was never recorded",
    "household": "the household this return belongs to; the folder above the year",
    "tax_year": "the year the return is for; the year folder's name",
    "return_name": RETURN_NAME_HELP,
    "people": PEOPLE_HELP,
    **ENGAGEMENT_NOTES,
}
#: The fields a person may change in the app's editor once the engagement
#: exists. ``name`` is not among them because the folder is the name;
#: ``rolled_from`` because the rollover writes it and it is what retires
#: the prior; ``form`` because it records which catalog the list was cut
#: from, once; and the three of decision 125 because the folders are the
#: names - a person who wants a return in another household or another
#: year makes one there. ``people`` is among them (decision 128) and is
#: edited through its own block rather than a box, because a person is
#: three values and a list of ticked spellings. The API's ``edit`` refuses
#: any other key by name.
ENGAGEMENT_EDITABLE: tuple[str, ...] = ("client", "link", "due", "filing_deadline", "sender",
                                        "firm", "reminders", "active", "people")
assert set(ENGAGEMENT_EDITABLE) <= {field_name for _, field_name in ENGAGEMENT_FIELDS}

#: Which details are dates, said once (decision 117). The record's
#: serialisation, the API's reading of a spec and the editor's choice of
#: box all ask this question, and each answered it by naming ``due``; a
#: second date added to the record then meant finding all three. One home:
#: a date field added above is a date field everywhere.
DATE_FIELDS: tuple[str, ...] = ("due", "filing_deadline")
assert set(DATE_FIELDS) <= {field_name for _, field_name in ENGAGEMENT_FIELDS}


def info_to_json(info: EngagementInfo) -> dict:
    """The engagement's details as they are stored: the fields, the dates as text.

    The shape a ``rules_changed`` event carries the engagement's own
    details in (and a ``rules_imported`` line from before decision 104),
    and the shape the store folds back. One owner, as
    :func:`status_to_json` is one owner for a status.
    """
    payload = asdict(info)
    for name in DATE_FIELDS:
        value = getattr(info, name)
        payload[name] = value.isoformat() if value else None
    # The people as a list of objects, through their own writer, so the
    # journal's line and the store's column hold exactly one shape
    # (``asdict`` would give the same keys and no owner for them).
    payload["people"] = [person_to_json(one) for one in info.people]
    return payload


def info_from_json(raw: dict) -> EngagementInfo:
    """An EngagementInfo from a stored one, ignoring a field this version
    does not know: details an older or newer run recorded must not be
    thrown away over one field."""
    known = {f.name for f in fields(EngagementInfo)}
    values = {key: value for key, value in raw.items() if key in known}
    for name in DATE_FIELDS:
        values[name] = dt.date.fromisoformat(raw[name]) if raw.get(name) else None
    # The two yes/no fields come back as 0 and 1 from a column and as
    # booleans from a journal line; a reader gets a boolean either way, so
    # a record read from the store is the record that was written.
    for name in ("reminders", "active"):
        if name in values:
            values[name] = bool(values[name])
    # The tax year is a number, and a JSON line may carry the digits as
    # text. Nothing at all stays nothing: a return whose year nobody
    # recorded has none, and blank is unknown to every reader.
    if values.get("tax_year") in (None, ""):
        values["tax_year"] = None
    elif "tax_year" in values:
        values["tax_year"] = int(values["tax_year"])
    # The people come back as a list of objects from a journal line and as
    # JSON text from the store's column; both are read the one way, and a
    # shape no matcher could use raises rather than being half-read
    # (``people_from_json``).
    if "people" in values:
        values["people"] = people_from_json(values["people"])
    return EngagementInfo(**values)


# ------------------------------------------------------------ household ----


@dataclass(frozen=True, slots=True)
class Feed:
    """One return line in another household that this household's drop
    folder also feeds (decision 129).

    **A return line, not a return.** A client with a co-owned business
    keeps one drop folder and the business lives in a household shared to
    its co-owners, so one inbox has to be able to feed a return in another
    household. What is recorded is the household and the return's name -
    the name a return keeps every year - and the pass resolves it to that
    household's open-year return of that name. Year-independent by
    construction: the rollover carries nothing, and a line that is retired
    is *said* (``tracker.households.FEED_UNRESOLVED``) rather than
    silently dropped.

    Never inferred. A household is assembled by a person and so is a feed:
    nothing anywhere looks at two households and suggests one.
    """

    household: str                  # the household whose return is fed
    return_name: str                # the return's folder name, the same every year


#: What a feed that is not a return line another household can feed is
#: refused with: a household feeding itself (its own returns are fed
#: already), a blank name, or one the list already holds.
FEED_REFUSED = "{household} / {return_name} is not a return line another household can feed"


def feed_to_json(feed: Feed) -> dict:
    """One feed as the record stores it: the household and the return line."""
    return {"household": feed.household, "return_name": feed.return_name}


def feed_from_json(raw: object) -> Feed:
    """One stored feed read back, refusing a shape no reader could use.

    A feed naming no household or no return line points at nothing the
    pass could resolve, so it is refused here - where
    :func:`tracker.store._refuse_a_malformed_line` sends a hand-edited
    journal's feeds to be judged - rather than written into a column a
    later pass trusts.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"a feed is {type(raw).__name__}, not an object")
    household = str(raw.get("household", "")).strip()
    return_name = str(raw.get("return_name", "")).strip()
    if not household or not return_name:
        raise ValueError(FEED_REFUSED.format(household=household or "(blank)",
                                             return_name=return_name or "(blank)"))
    return Feed(household=household, return_name=return_name)


def feeds_from_json(raw: object) -> tuple[Feed, ...]:
    """A household's feed list as the record holds it: a list of objects
    from a journal line, or the JSON text one column holds.

    SQLite cannot tell a JSON array in a text column from a string, so the
    text is read back here for the same reason the people are
    (:func:`people_from_json`).
    """
    if raw in (None, "", ()):
        return ()
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, (list, tuple)):
        raise ValueError(f"the feeds are {type(raw).__name__}, not a list")
    return tuple(feed_from_json(one) for one in raw)


@dataclass(frozen=True, slots=True)
class HouseholdInfo:
    """What the firm records about one household (decision 125).

    A household is the set of returns whose people may all see each
    other's documents, because everyone shared on the household's folder
    sees everything filed under it. Its record lives in the private tree,
    at the household level, and is folded by the same machinery a return's
    journal is.

    ``members`` is **a person's claim, not the tracker's knowledge**: the
    tracker never makes, reads or changes a Drive share, so this is the
    firm's own note of who the folder is meant to be shared with, labelled
    as one wherever it is shown.
    """

    name: str = ""
    members: tuple[str, ...] = ()
    contact: str = ""
    link: str = ""
    #: The return lines in **other** households this household's drop
    #: folder also feeds (decision 129). Empty for nearly every household:
    #: a drop folder feeds its own returns unless a person extends it, and
    #: nothing ever infers one.
    feeds: tuple[Feed, ...] = ()


#: The household's labels, in the order a reader shows them.
HOUSEHOLD_FIELDS = (
    ("Household", "name"),
    ("Members", "members"),
    ("Contact", "contact"),
    ("Inbox Link", "link"),
    ("Also feeds", "feeds"),
)
#: field name -> the label, for messages that name a field.
HOUSEHOLD_LABELS = {field_name: label for label, field_name in HOUSEHOLD_FIELDS}
#: The fields a person may change once the household exists. The name is
#: not among them: the folder is the name, exactly as a return's is.
#: ``feeds`` is (decision 129) and is edited through its own list rather
#: than a box, because a feed is a household and a return line picked from
#: what is already there.
HOUSEHOLD_EDITABLE: tuple[str, ...] = ("members", "contact", "link", "feeds")
assert set(HOUSEHOLD_EDITABLE) <= {field_name for _, field_name in HOUSEHOLD_FIELDS}


def household_to_json(info: HouseholdInfo) -> dict:
    """The household's details as they are stored: the fields, the members
    as a JSON list.

    The shape a ``household_changed`` event carries and the shape the
    store folds back, as :func:`info_to_json` is for a return's details.
    """
    payload = asdict(info)
    payload["members"] = list(info.members)
    # The feeds as a list of objects, through their own writer, so the
    # journal's line and the store's column hold exactly one shape
    # (decision 129).
    payload["feeds"] = [feed_to_json(one) for one in info.feeds]
    return payload


def household_from_json(raw: dict) -> HouseholdInfo:
    """A HouseholdInfo from a stored one, ignoring a field this version
    does not know.

    A ``members`` that is one string is read as one member rather than
    refused: the journal is a synced file a person may have opened, and a
    hand-written line naming one person must not cost the household its
    whole record.
    """
    known = {f.name for f in fields(HouseholdInfo)}
    values = {key: value for key, value in raw.items() if key in known}
    members = values.get("members")
    if isinstance(members, str):
        values["members"] = (members,) if members else ()
    elif members is None:
        values.pop("members", None)
    else:
        values["members"] = tuple(str(one) for one in members)
    # The feeds come back as a list of objects from a journal line and as
    # JSON text from the store's column; both are read the one way, and a
    # shape no pass could resolve raises rather than being half-read
    # (``feeds_from_json``). A household record from before decision 129
    # names none, which reads as none.
    if "feeds" in values:
        values["feeds"] = feeds_from_json(values["feeds"])
    return HouseholdInfo(**values)


#: The person's half of a request row: everything the manifest's
#: ``RequestItem`` holds that is not a status the machine decided. It is
#: named here rather than beside that class because these rows now *travel*
#: - a ``rules_changed`` event carries them (and the ``rules_imported``
#: lines journals from before decision 104 carry) and the store's
#: ``requests`` table is these columns - while the parsing of the values
#: they came from stays with the manifest. ``tracker.store`` builds its
#: column list from this, so a field added to the row is added in one place.
#: ``override_reason`` (decision 116) is last but one: every row stored
#: before it existed reads as blank through :func:`rule_from_json`'s
#: default. ``named`` (decision 128) is last for the same reason, and its
#: default is **strict**: a row stored before the mark existed reads as
#: named, so a W-2 in an old engagement needs the name on the page exactly
#: as a new one does. ``asked`` (decision 142) comes after it, and its
#: default is **yes**: every row written before the mark existed was a row a
#: person ticked, so it reads as asked and no existing list changes meaning.
#: A row that is not asked is on the return, accepts what arrives for it
#: and files it, but is never listed as needed and never chased.
#: ``short_title`` (decision 144) is last, and its default is **blank**:
#: a row stored before it existed derives its short name from its document
#: title, and an existing working copy is found by its identifier, so
#: nothing already on disk is renamed.
RULE_FIELDS: tuple[str, ...] = (
    "identifier",
    "document",
    "period",
    "expected_count",
    "allowed_extensions",
    "min_size_kb",
    "required_keywords",
    "any_keywords",
    "date_pattern",
    "date_pattern_derived",
    "manual_override",
    "row",
    "override_reason",
    "named",
    "asked",
    "short_title",
)


#: The rule fields that hold a list of words rather than one value. Named
#: because JSON and SQLite both lose the difference between a tuple and a
#: string: stored, they are a JSON array in a text column, and this is what
#: says which columns to read back that way.
RULE_LIST_FIELDS: frozenset[str] = frozenset({
    "allowed_extensions", "required_keywords", "any_keywords",
})
#: The rule fields that are yes/no. Stored as 0 and 1, like every other
#: flag the store holds, and turned back into booleans here so a row read
#: from the record is the row that was written and not a near-enough copy.
RULE_FLAG_FIELDS: frozenset[str] = frozenset({"date_pattern_derived", "named", "asked"})
#: What a yes/no rule field means when the line that wrote the row never
#: said - a journal from before the field existed, and so a column holding
#: null. The record owns the answer, because it is the record's default:
#: ``named`` is **true**, so a row written before decision 128 is strict,
#: and ``asked`` is **true**, so a row written before decision 142 is the
#: request a person ticked.
RULE_FLAG_DEFAULTS: dict[str, bool] = {"date_pattern_derived": False, "named": True, "asked": True}
assert set(RULE_FLAG_DEFAULTS) == set(RULE_FLAG_FIELDS)


def word_list_problem(value: object) -> str:
    """Why ``value`` is not a rule's list of words, or ``""`` when it is.

    A list field travels as a JSON array and is read back as one (decision
    137, L4). A string in its place is the one that does harm without a
    sound: ``tuple("W-2")`` is three one-character keywords, and every
    document with a hyphen in it would match. So the shape is checked where
    a row is written into the record and where it is read back out, and a
    row that fails is refused by name rather than read as letters.
    """
    if value is None:
        return ""
    if not isinstance(value, (list, tuple)):
        return f"is {type(value).__name__}, not a list of words"
    for word in value:
        if not isinstance(word, str):
            return f"holds {word!r:.40}, which is not a word"
    return ""


def rule_to_json(item: object) -> dict:
    """One request row's *rules* as they are stored: the person's fields,
    the word lists as JSON lists.

    Duck-typed on :data:`RULE_FIELDS` rather than typed on ``RequestItem``,
    because that class is the manifest's and this module imports nothing of
    the package. The pair with :func:`rule_from_json` is what lets a rule
    row travel in the journal and come back the same row.
    """
    payload: dict[str, object] = {}
    for name in RULE_FIELDS:
        value = getattr(item, name)
        payload[name] = list(value) if name in RULE_LIST_FIELDS else value
    return payload


def rule_from_json(raw: dict) -> dict:
    """A stored rule row as keyword arguments for ``RequestItem``.

    Keyword arguments rather than the record itself, for the same reason:
    the class lives in the module that owns the list. A field this
    version does not know is ignored and one it does not carry is left to
    the record's own default, so a row written by another version still
    loads.
    """
    values: dict[str, object] = {}
    for name in RULE_FIELDS:
        if name not in raw:
            continue
        value = raw[name]
        if name in RULE_LIST_FIELDS:
            if problem := word_list_problem(value):
                raise ValueError(f"the rule's {name!r} {problem}")
            values[name] = tuple(value or ())
        elif name in RULE_FLAG_FIELDS:
            values[name] = bool(value)
        else:
            values[name] = value
    return values


@dataclass(frozen=True, slots=True)
class StatusUpdate:
    """Scanner output for one identifier, as the record holds it.

    Named for the scanner columns it used to be written into; since
    decision 103 there are no such columns and this is simply what the
    record says about one request.
    """

    status: str
    file_count: int = 0
    received_date: dt.date | None = None
    validation_notes: str = ""


def status_to_json(update: StatusUpdate) -> dict:
    """One identifier's status as it is stored: its fields, the date as text.

    The one shape for it, as :func:`entry_to_json` is the one shape for an
    index row. The engagement's record writes it inside a ``scanned``
    event and the store reads it back through :func:`status_from_json`, so
    a field added above is carried by both without another edit.
    """
    payload = asdict(update)
    payload["received_date"] = update.received_date.isoformat() if update.received_date else None
    # A blank File Count reaches here as nothing at all, and no files
    # is a number. Coerced on the way out as well as on the way in, so
    # that reading a stored status back gives the record it was made from
    # and two readings of one blank cannot differ.
    payload["file_count"] = int(update.file_count or 0)
    return payload


def status_from_json(raw: dict) -> StatusUpdate:
    """A StatusUpdate from a stored one, tolerant of a field it does not carry.

    A status is only ever read back to decide what a client still owes, and
    an event written by an older version must not be thrown away over a
    field that version did not have. The status itself is the one value
    with no sensible default: a stored update without one is not a status.
    """
    values = {f.name: raw.get(f.name, f.default) for f in fields(StatusUpdate) if f.name != "status"}
    values["received_date"] = dt.date.fromisoformat(raw["received_date"]) if raw.get("received_date") else None
    values["file_count"] = int(values["file_count"] or 0)
    return StatusUpdate(status=raw["status"], **values)


# ------------------------------------------------------------ the value rule ----
#
# Decision 187: the record is untrusted input. A journal is a synced file, so
# a line may have been written by another machine, restored from a copy or
# typed by hand - and every value in it is obeyed by something: a count is
# stored in a column SQLite bounds, a date is parsed by the readers, a Date
# Pattern is run over a client's pages. So each value is held here to the
# bounds the editor holds a person to, worded once: the editor
# (``tracker.manifest``) refuses a value it would never write with these, and
# the store's gate (``tracker.store._refuse_a_malformed_line``) refuses a line
# carrying one before a table is touched. Each check returns a fixed phrase
# naming the class of problem and never the value, because the value is
# whatever the line said, and ``""`` for a value that is fine.

#: The years a tax year can be. ``tracker.manifest.YEAR_PATTERN`` is built from
#: them, the app's year inputs are bounded by them, and every path that takes a
#: year from a person checks it against them (``manifest.check_tax_year``).
YEAR_MIN = 1900
YEAR_MAX = 2099
#: What a year outside those bounds is told, wherever it was typed.
YEAR_OUT_OF_RANGE = "Tax year must be between {minimum} and {maximum}, got {year}"
#: The years a date or a stamp in the record may fall in: a tax year's, and
#: the year after the last one, where its deadlines fall.
DATE_YEAR_MIN = YEAR_MIN
DATE_YEAR_MAX = YEAR_MAX + 1
#: The first year a stamp may fall in: the epoch, before which Windows
#: cannot give a time its local day.
STAMP_YEAR_MIN = 1970

#: Characters Windows forbids in file and folder names, plus control
#: characters - the one list, for identifiers and for sanitising names.
_ILLEGAL_PUNCTUATION = '\\/:*?"<>|'
WINDOWS_ILLEGAL_CHARS = re.compile("[" + re.escape(_ILLEGAL_PUNCTUATION) + r"\x00-\x1f]")
WINDOWS_ILLEGAL_CHARS_TEXT = " ".join(_ILLEGAL_PUNCTUATION)
#: The names Windows keeps for devices (decision 137, L6). A folder or a
#: file named one of them - with or without an extension, in any case - is
#: not a folder at all: ``NUL`` is the null device, ``COM1`` a serial port,
#: and a working copy, a household or a return named one could never
#: hold a document.
WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{n}" for n in range(1, 10)}
    | {f"LPT{n}" for n in range(1, 10)}
    # The superscript digits Windows reserves too (the review's F6).
    | {f"{port}{digit}" for port in ("COM", "LPT") for digit in "¹²³"}
)
WINDOWS_RESERVED_NAMES_TEXT = ("CON, PRN, AUX, NUL, CONIN$, CONOUT$, COM1-COM9, LPT1-LPT9 "
                               "and their superscript-1, 2 and 3 forms")


def is_reserved_name(name: str) -> bool:
    """Whether Windows reads ``name`` as a device rather than a file or a
    folder: a reserved name, alone or before an extension (``nul.txt``),
    whatever its case and any spaces before the dot."""
    stem = str(name).split(".", 1)[0].rstrip(" ")
    return stem.upper() in WINDOWS_RESERVED_NAMES


def identifier_problem(identifier: str) -> str:
    """Why ``identifier`` cannot begin a working copy's name, or "" if it can.

    Shared by ``manifest.validated``, the desktop app's create path and the
    store's gate, so a bad identifier is refused with the same sentence
    wherever it is typed or read.
    """
    if WINDOWS_ILLEGAL_CHARS.search(identifier):
        return f"may not contain any of {WINDOWS_ILLEGAL_CHARS_TEXT} (it begins a file name)"
    if identifier != identifier.rstrip(". "):
        return "may not end with a dot or a space (Windows drops them from file names)"
    if is_reserved_name(identifier):
        return (f"may not be a name Windows keeps for a device ({WINDOWS_RESERVED_NAMES_TEXT}); "
                f"it begins a file name")
    return ""


#: The most characters a short title may have (decision 144). The owner's
#: style: ``A01 - W-2\A01 - W-2 - TY2025.pdf``, a short title of about
#: twenty characters, so a real household's name fits under the real root.
SHORT_TITLE_MAX = 20


def short_title_problem(short_title: str) -> str:
    """Why ``short_title`` cannot name a working copy, or "" if it can.

    Refused rather than sanitised, as an identifier is: the name a person
    types is the name every working copy carries, or they are told why not.
    """
    if len(short_title) > SHORT_TITLE_MAX:
        return f"may have at most {SHORT_TITLE_MAX} characters, got {len(short_title)}"
    if WINDOWS_ILLEGAL_CHARS.search(short_title):
        return f"may not contain any of {WINDOWS_ILLEGAL_CHARS_TEXT} (it is part of a file name)"
    if short_title != short_title.rstrip(". "):
        return "may not end with a dot or a space (Windows drops them from file names)"
    if short_title and is_reserved_name(short_title):
        return (f"may not be a name Windows keeps for a device ({WINDOWS_RESERVED_NAMES_TEXT}); "
                f"it is part of a file name")
    return ""


class Override:
    """Accountant judgment values that beat the automated rules.

    ``ACCEPTED`` treats the row as Received despite the checks, and carries
    a reason (``manifest.OVERRIDE_REASONS``, decision 116). ``NOT_APPLICABLE``
    says the request does not apply this year - shown to people with the
    row's own year (``manifest.override_label``) - and takes the row out of
    every count, every reminder and the active table.

    ``RETIRED`` is the retired-value rule of decision 104 applied to a
    value: the spelling journals written before decision 116 hold for the
    second value, folded to its successor on every read by
    ``manifest._override`` and never written again.
    """

    ACCEPTED = "Accepted"
    NOT_APPLICABLE = "Not Applicable"

    ALL = (ACCEPTED, NOT_APPLICABLE)
    RETIRED: dict[str, str] = {"Waived": NOT_APPLICABLE}


#: The bounds on a request's two numbers, and where the editor's number
#: inputs take theirs from - through the API's vocabulary, never typed in
#: the page. The maximums are decision 187's: a count no statement reaches
#: and a size past any document, so no value a person typed is refused, and
#: SQLite's own limit (past 2**63) is never met.
MIN_EXPECTED_COUNT = 1
MAX_EXPECTED_COUNT = 9_999
MIN_SIZE_KB_FLOOR = 0
MAX_SIZE_KB = 1_048_576
#: The other numbers the record holds: how many files a request has, the
#: stage of a draft, a request's position in its list.
MAX_FILE_COUNT = 9_999
MAX_STAGE = 9
MAX_ROW = 9_999
#: An original's size as its row records it: any file the inbox can hold.
MAX_ROW_SIZE_KB = 1_073_741_824
#: One line of text (a name, a label, a location) and long text (a reason,
#: a note, the evidence).
TEXT_MAX = 1_000
LONG_TEXT_MAX = 20_000
#: A Date Pattern's shape (decision 187). It is run over every line of a
#: client's page, so a pattern that backtracks without end would hold a pass
#: on one document; the shape rule below admits every pattern the Period
#: derives and every one a person plausibly types, and nothing that can run
#: away. Measured on a 500-character line: three open-ended repetitions take
#: 9.6 s, one open-ended and two bounded to 20 take 0.22 s - and so does one
#: open-ended beside seven ``?``, because an optional is a choice point too
#: (the review's M1): ``\d?`` twenty-four times took 3.3 s on 24 digits.
DATE_PATTERN_MAX = 200
#: Repetitions that can repeat more than once.
DATE_PATTERN_REPEATS_MAX = 3
#: Every variable repetition, ``?`` included (the orchestrator's amendment
#: of SPEC-187 ruling 5).
DATE_PATTERN_VARIABLE_MAX = 8
DATE_PATTERN_OPEN_MAX = 1
DATE_PATTERN_BOUND_MAX = 20
#: How many ways one start of a line may be tried, at most (:func:`_ways`):
#: counted through every repetition - a fixed ``{1}`` included, so wrapping
#: a chain hides nothing - an alternation's branches added, an open-ended
#: repetition counted as the longest line a pattern is run over
#: (``content_check.DATE_LINE_MAX``). The limit is measured on 500-character
#: lines of digits with no literal ending the engine can short-cut (the
#: re-check of decision 187's review, M1b): at 16,384 ways the slowest
#: pattern admitted took about a quarter of a second, where 220,500 ways -
#: one open-ended and two bounded to 20 - took 0.85 s. Every pattern the
#: Period derives is tried at most 176 ways.
DATE_PATTERN_OPEN_WIDTH = 500
DATE_PATTERN_WAYS_MAX = 16_384
#: What a pattern may cost, at most: its ways times the widest match of its
#: bounded parts (:func:`_width`), because every way tried may be followed
#: by that much matching (the second re-check of decision 187's review,
#: M1c: ``(?:\d\d){200}`` adds no way and 400 characters of work to each,
#: 15 s on one line). A fixed ``{n}`` and a lookaround count toward the
#: width; an open-ended part counts one, its length being in the ways
#: already. Every derived pattern costs at most 6,688.
DATE_PATTERN_COST_MAX = 200_000

#: The fixed phrases. Each names the class of problem; none names the value.
COUNT_BOUNDS = "must be a whole number from {minimum} to {maximum}"
NUMBER_BOUNDS = "must be a number from {minimum} to {maximum}"
DATE_BOUNDS = f"must be a date written YYYY-MM-DD, from {DATE_YEAR_MIN} to {DATE_YEAR_MAX}"
STAMP_BOUNDS = f"must be a time written YYYY-MM-DDTHH:MM:SSZ, from {STAMP_YEAR_MIN} to {DATE_YEAR_MAX}"
FLAG_BOUNDS = "must be true or false"
DIGEST_BOUNDS = "must be blank or 64 lowercase hexadecimal characters"
TEXT_BOUNDS = f"must be one line of text of at most {TEXT_MAX} characters, with no control character"
LONG_TEXT_BOUNDS = f"must be text of at most {LONG_TEXT_MAX} characters, with no NUL"
TEXT_LIST_BOUNDS = "must be a list of text"
NAME_BOUNDS = f"must be text of at most {TEXT_MAX} characters, with no NUL"
OVERRIDE_BOUNDS = f"must be blank, {Override.ACCEPTED} or {Override.NOT_APPLICABLE}"
BLANK_BOUNDS = "may not be blank"
DATE_PATTERN_TOO_LONG = f"may have at most {DATE_PATTERN_MAX} characters"
DATE_PATTERN_NOT_A_REGEX = "is not a valid regex"
DATE_PATTERN_NESTED = "repeats something that itself repeats"
DATE_PATTERN_ALTERNATES = "repeats an alternation (a | inside a repetition)"
DATE_PATTERN_REFERS_BACK = "repeats a back-reference"
DATE_PATTERN_TOO_MANY = f"has more than {DATE_PATTERN_REPEATS_MAX} repetitions"
DATE_PATTERN_TOO_MANY_OPTIONAL = (f"has more than {DATE_PATTERN_VARIABLE_MAX} variable repetitions "
                                  f"(?, *, + or {{m,n}})")
DATE_PATTERN_TOO_MANY_WAYS = "could try too many ways to match one line"
DATE_PATTERN_TOO_COSTLY = "could do too much matching on one line"
DATE_PATTERN_TOO_OPEN = f"has more than {DATE_PATTERN_OPEN_MAX} open-ended repetition (+, * or {{n,}})"
DATE_PATTERN_TOO_WIDE = f"repeats more than {DATE_PATTERN_BOUND_MAX} times in a bounded repetition"

_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_ONE_LINE_REFUSED = re.compile(r"[\x00-\x1f\x7f  ]")


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def count_problem(value: object, minimum: int, maximum: int) -> str:
    """:data:`COUNT_BOUNDS` for anything but a whole number from ``minimum``
    to ``maximum`` - a number, never its text, never a boolean."""
    if (not _is_number(value) or not math.isfinite(value) or value != int(value)
            or not minimum <= value <= maximum):
        return COUNT_BOUNDS.format(minimum=minimum, maximum=maximum)
    return ""


def number_problem(value: object, minimum: float, maximum: float) -> str:
    """:data:`NUMBER_BOUNDS` for anything but a finite number in the bounds."""
    if not _is_number(value) or not math.isfinite(value) or not minimum <= value <= maximum:
        return NUMBER_BOUNDS.format(minimum=minimum, maximum=maximum)
    return ""


def date_problem(value: object) -> str:
    """:data:`DATE_BOUNDS` for anything but a real calendar date in the
    record's years, as a date or as its ISO text. Blank is the caller's to
    allow."""
    if isinstance(value, dt.datetime):
        return DATE_BOUNDS
    if isinstance(value, dt.date):
        day = value
    elif isinstance(value, str) and _ISO_DATE.fullmatch(value):
        try:
            day = dt.date.fromisoformat(value)
        except ValueError:
            return DATE_BOUNDS
    else:
        return DATE_BOUNDS
    return "" if DATE_YEAR_MIN <= day.year <= DATE_YEAR_MAX else DATE_BOUNDS


def stamp_problem(value: object) -> str:
    """:data:`STAMP_BOUNDS` for anything but a stamp as ``ledger.stamp``
    writes it - ``YYYY-MM-DDTHH:MM:SSZ``, the one form it has ever written -
    in 1970 to 2100. Not before 1970, because Windows cannot turn a time
    before the epoch into a local day (the review's S1)."""
    if not isinstance(value, str) or not _STAMP.fullmatch(value):
        return STAMP_BOUNDS
    try:
        moment = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return STAMP_BOUNDS
    return "" if STAMP_YEAR_MIN <= moment.year <= DATE_YEAR_MAX else STAMP_BOUNDS


def received_problem(value: object) -> str:
    """:data:`DATE_BOUNDS` for an index row's Received that is neither a
    date nor an ISO date and time. The pass writes the day; a row seeded
    from the index workbook (``ledger.IMPORTED``, decisions 87 and 102) may
    carry the cell's time after it, and a row already moved must not be
    refused for that."""
    if not date_problem(value):
        return ""
    if isinstance(value, str) and len(value) <= 40 and _ISO_DATE.match(value):
        try:
            moment = dt.datetime.fromisoformat(value)
        except ValueError:
            return DATE_BOUNDS
        return "" if DATE_YEAR_MIN <= moment.year <= DATE_YEAR_MAX else DATE_BOUNDS
    return DATE_BOUNDS


def flag_problem(value: object) -> str:
    """:data:`FLAG_BOUNDS` for anything but ``true``, ``false``, 0 or 1. Never
    ``"no"``: the word is truthy, so a reader that asked ``bool()`` would
    read a hand-typed no as yes."""
    if isinstance(value, bool) or (type(value) is int and value in (0, 1)):
        return ""
    return FLAG_BOUNDS


def digest_problem(value: object) -> str:
    """:data:`DIGEST_BOUNDS` for anything but blank or a SHA-256 in hex."""
    if value == "" or (isinstance(value, str) and _HEX_DIGEST.fullmatch(value)):
        return ""
    return DIGEST_BOUNDS


def text_problem(value: object, *, long: bool = False) -> str:
    """Why ``value`` is not text the record may hold, or ``""``.

    One line (a name, a label, a location): no line break or control
    character, at most :data:`TEXT_MAX` characters. ``long`` (a reason, a
    note, the evidence): no NUL, at most :data:`LONG_TEXT_MAX`."""
    if long:
        if not isinstance(value, str) or len(value) > LONG_TEXT_MAX or "\x00" in value:
            return LONG_TEXT_BOUNDS
        return ""
    if not isinstance(value, str) or len(value) > TEXT_MAX or _ONE_LINE_REFUSED.search(value):
        return TEXT_BOUNDS
    return ""


def name_problem(value: object) -> str:
    """:data:`NAME_BOUNDS` for anything but a file's own name, a key or a
    location: text of at most :data:`TEXT_MAX` characters with no NUL.

    Wider than one line on purpose (the review's M5): these come from real
    files, and decision 104 files a POSIX name holding a control character.
    They are never joined onto a path as a label is - a location is judged
    by the layout's place rule instead - so refusing one would stop the
    household every pass with an original already moved and no row."""
    if not isinstance(value, str) or len(value) > TEXT_MAX or "\x00" in value:
        return NAME_BOUNDS
    return ""


def text_list_problem(value: object, *, long: bool = False) -> str:
    """:data:`TEXT_LIST_BOUNDS` for anything but a list of text - one-line,
    or ``long``."""
    if not isinstance(value, (list, tuple)) or any(text_problem(one, long=long) for one in value):
        return TEXT_LIST_BOUNDS
    return ""


_REPEATS = frozenset({_re_parser.MAX_REPEAT, _re_parser.MIN_REPEAT, _re_parser.POSSESSIVE_REPEAT})
_REFERS_BACK = frozenset({_re_parser.GROUPREF, _re_parser.GROUPREF_EXISTS})


def _walk(pattern: object):
    """Every ``(op, argument)`` of a parsed pattern, at any depth."""
    if isinstance(pattern, _re_parser.SubPattern):
        for op, argument in pattern:
            yield op, argument
            yield from _walk(argument)
    elif isinstance(pattern, (tuple, list)):
        for one in pattern:
            yield from _walk(one)


def _ways(pattern: object) -> int:
    """How many ways one start of a line may be tried, at most - a
    sequence's parts multiplied, a branch's alternatives added, and every
    repetition counted through what it holds: an optional as skipping it or
    any way through it, a counted ``{m,n}`` as its choice of count times the
    ways through each copy, an open-ended one as the longest line. Nothing
    inside a repetition is left uncounted, ``{1}`` included."""
    if not isinstance(pattern, _re_parser.SubPattern):
        return 1
    total = 1
    for op, argument in pattern:
        if op in _REPEATS:
            low, high, inside = argument
            if high == _re_parser.MAXREPEAT:
                total *= DATE_PATTERN_OPEN_WIDTH
            elif high == 1:
                total *= (1 - low) + _ways(inside)
            else:
                total *= (high - low + 1) * _ways(inside) ** high
        elif op is _re_parser.BRANCH:
            total *= sum(_ways(one) for one in argument[1])
        elif op is _re_parser.GROUPREF_EXISTS:
            total *= max(_ways(argument[1]), _ways(argument[2]))
        elif op is _re_parser.SUBPATTERN:
            total *= _ways(argument[-1])
        elif op in (_re_parser.ASSERT, _re_parser.ASSERT_NOT):
            total *= _ways(argument[1])
        elif op is _re_parser.ATOMIC_GROUP:
            total *= _ways(argument)
    return total


def _width(pattern: object) -> int:
    """The widest match of a pattern's bounded parts - how much matching may
    follow each way it is tried. A fixed ``{n}`` counts n times what it
    holds, a lookaround its own width, a branch its widest alternative, a
    back-reference 20, an open-ended part one, and a zero-width assertion
    one."""
    if not isinstance(pattern, _re_parser.SubPattern):
        return 1
    width = 0
    for op, argument in pattern:
        if op in _REPEATS:
            _low, high, inside = argument
            width += _width(inside) * (1 if high == _re_parser.MAXREPEAT else high)
        elif op is _re_parser.BRANCH:
            width += max(_width(one) for one in argument[1])
        elif op is _re_parser.SUBPATTERN:
            width += _width(argument[-1])
        elif op is _re_parser.ATOMIC_GROUP:
            width += _width(argument)
        elif op in (_re_parser.ASSERT, _re_parser.ASSERT_NOT):
            width += _width(argument[1])
        elif op is _re_parser.GROUPREF_EXISTS:
            width += max(_width(argument[1]), _width(argument[2]))
        elif op is _re_parser.GROUPREF:
            width += DATE_PATTERN_BOUND_MAX
        else:
            # Everything else counts one - a zero-width assertion (\b, \B,
            # ^, $, \A, \Z) included, because it is a test at every step
            # though it matches nothing (the third re-check: a group padded
            # with \B did unbounded work per counted character).
            width += 1
    return width


def date_pattern_problem(pattern: object) -> str:
    """Why a Date Pattern may not be run over a client's page, or ``""``.

    It must be text of at most :data:`DATE_PATTERN_MAX` characters that
    compiles, and pass a shape rule read off the standard library's own
    parser (``re._parser``) - no second engine and no whitelist. A
    repetition is anything that can repeat more than once or can match a
    varying number of times - ``?`` included, because an optional is a
    choice point (the review's M1):

    - a repetition may not contain another or a back-reference, at any
      depth, nor an alternation unless it is a plain optional (``?``), whose
      ways are counted like any other (``(?:Dec|12)?`` is a date pattern);
    - at most :data:`DATE_PATTERN_VARIABLE_MAX` variable repetitions, of
      which at most :data:`DATE_PATTERN_REPEATS_MAX` can repeat more than
      once and at most :data:`DATE_PATTERN_OPEN_MAX` is open-ended (``+``,
      ``*``, ``{n,}``);
    - every bounded one repeats at most :data:`DATE_PATTERN_BOUND_MAX` times;
    - the ways one start of a line may be tried, counted through every
      repetition, stay within :data:`DATE_PATTERN_WAYS_MAX` (:func:`_ways`);
    - and those ways times the widest match of the bounded parts
      (:func:`_width`) stay within :data:`DATE_PATTERN_COST_MAX`.

    The rule bounds the cost by reading the pattern; it is not a clock
    (principle 8). A time bound that needs no analysis comes with the
    judgment in a child the pass can stop.

    It applies to a derived pattern too, and every pattern the Period
    derives passes.
    """
    if not isinstance(pattern, str):
        return TEXT_BOUNDS
    if len(pattern) > DATE_PATTERN_MAX:
        return DATE_PATTERN_TOO_LONG
    try:
        re.compile(pattern)
        parsed = _re_parser.parse(pattern)
    except (re.error, RecursionError, OverflowError):
        return DATE_PATTERN_NOT_A_REGEX

    def repeats(argument) -> bool:
        low, high, _inside = argument
        return low != high or high > 1

    found = [argument for op, argument in _walk(parsed) if op in _REPEATS and repeats(argument)]
    for _low, high, inside in found:
        for op, argument in _walk(inside):
            if op in _REPEATS and repeats(argument):
                return DATE_PATTERN_NESTED
            if op is _re_parser.BRANCH and high > 1:
                return DATE_PATTERN_ALTERNATES
            if op in _REFERS_BACK:
                return DATE_PATTERN_REFERS_BACK
    variable = [(low, high) for low, high, _inside in found if low != high]
    if len(variable) > DATE_PATTERN_VARIABLE_MAX:
        return DATE_PATTERN_TOO_MANY_OPTIONAL
    if sum(high > 1 for _low, high in variable) > DATE_PATTERN_REPEATS_MAX:
        return DATE_PATTERN_TOO_MANY
    if sum(high == _re_parser.MAXREPEAT for _low, high in variable) > DATE_PATTERN_OPEN_MAX:
        return DATE_PATTERN_TOO_OPEN
    if any(high != _re_parser.MAXREPEAT and high > DATE_PATTERN_BOUND_MAX for _low, high in variable):
        return DATE_PATTERN_TOO_WIDE
    ways = _ways(parsed)
    if ways > DATE_PATTERN_WAYS_MAX:
        return DATE_PATTERN_TOO_MANY_WAYS
    if ways * max(1, _width(parsed)) > DATE_PATTERN_COST_MAX:
        return DATE_PATTERN_TOO_COSTLY
    return ""


def _field(name: str, problem: str) -> str:
    return f"'{name}' {problem}" if problem else ""


def _first(*problems: str) -> str:
    return next((one for one in problems if one), "")


#: A rule row's fields by the check each is held to: one-line text, long
#: text, and the flags. The numbers, the word lists, the override and the
#: Date Pattern have checks of their own below.
#: A rule row's descriptive fields: text a person writes, never joined onto
#: a path, so held to the long-text rule (the review's M6) - a line break
#: typed in a cell is not a danger, and refusing it would wedge a return.
_RULE_TEXT = ("document", "period", "override_reason")


def rule_row_fault(row: dict) -> tuple[str, str]:
    """The first field of a stored rule row outside the value rule and its
    phrase, or ``("", "")``. A field the row does not carry is left to the
    record's default and is not checked. The editor (``manifest.validated``)
    names the field by its column; the gate by :func:`rule_row_problem`."""
    def given(name: str) -> bool:
        return name in row

    checks: list[tuple[str, str]] = []
    if given("identifier"):
        value = row["identifier"]
        checks.append(("identifier", text_problem(value)
                       or (BLANK_BOUNDS if not value.strip() else identifier_problem(value.strip()))))
    for name in _RULE_TEXT:
        if given(name):
            checks.append((name, text_problem(row[name], long=True)))
    if given("expected_count"):
        checks.append(("expected_count",
                       count_problem(row["expected_count"], MIN_EXPECTED_COUNT, MAX_EXPECTED_COUNT)))
    if given("min_size_kb"):
        checks.append(("min_size_kb", count_problem(row["min_size_kb"], MIN_SIZE_KB_FLOOR, MAX_SIZE_KB)))
    if given("row"):
        checks.append(("row", count_problem(row["row"], 0, MAX_ROW)))
    for name in RULE_LIST_FIELDS:
        if given(name) and row[name] is not None:
            checks.append((name, word_list_problem(row[name]) or text_list_problem(row[name], long=True)))
    for name in sorted(RULE_FLAG_FIELDS):
        if given(name):
            checks.append((name, flag_problem(row[name])))
    if given("manual_override"):
        value = row["manual_override"]
        known = ("", *Override.ALL, *Override.RETIRED)
        checks.append(("manual_override", "" if value in known else OVERRIDE_BOUNDS))
    if given("short_title"):
        value = row["short_title"]
        checks.append(("short_title", text_problem(value) or short_title_problem(value)))
    if given("date_pattern"):
        value = row["date_pattern"]
        checks.append(("date_pattern", text_problem(value, long=True) or
                       (date_pattern_problem(value) if value else "")))
    return next(((name, problem) for name, problem in checks if problem), ("", ""))


def rule_row_problem(row: dict) -> str:
    """The first field of a stored rule row outside the value rule, as
    ``"'<field>' <phrase>"``, or ``""`` (:func:`rule_row_fault`)."""
    return _field(*rule_row_fault(row))


#: A return's details, by the check each is held to.
_INFO_TEXT = ("household", "return_name")
#: Descriptive details a person writes, held to the long-text rule (M6).
_INFO_LONG_TEXT = ("client", "name", "sender", "firm", "form")


def info_problem(info: dict) -> str:
    """The first field of a return's stored details outside the value rule,
    or ``""``. Whether ``household`` and ``return_name`` are each one folder
    name is the layout's to say (``layout.segment_problem``), asked by the
    store beside this."""
    checks = [_field(name, text_problem(info[name])) for name in _INFO_TEXT if name in info]
    checks += [_field(name, text_problem(info[name], long=True)) for name in _INFO_LONG_TEXT
               if name in info]
    # Rolled From is a path the rollover wrote, not a label (M5).
    if "rolled_from" in info:
        checks.append(_field("rolled_from", name_problem(info["rolled_from"])))
    # A link is text here and nothing more: one that is not a web address is
    # dropped with the reason where it is read (decision 176), not refused.
    if "link" in info:
        checks.append(_field("link", text_problem(info["link"])))
    for name in DATE_FIELDS:
        if info.get(name) not in (None, ""):
            checks.append(_field(name, date_problem(info[name])))
    for name in ("reminders", "active"):
        if name in info:
            checks.append(_field(name, flag_problem(info[name])))
    year = info.get("tax_year")
    if year not in (None, ""):
        if isinstance(year, str) and year.isascii() and year.isdigit():
            year = int(year)
        checks.append(_field("tax_year", count_problem(year, YEAR_MIN, YEAR_MAX)))
    return _first(*checks)


def household_problem(household: dict) -> str:
    """The first field of a household's stored details outside the value
    rule, or ``""``. Whether its name and each feed's two names are each one
    folder name is the layout's to say, asked by the store beside this."""
    checks = [_field("name", text_problem(household["name"]))] if "name" in household else []
    if "contact" in household:
        checks.append(_field("contact", text_problem(household["contact"], long=True)))
    if "link" in household:
        checks.append(_field("link", text_problem(household["link"])))
    members = household.get("members")
    if members is not None:
        checks.append(_field("members", text_problem(members) if isinstance(members, str)
                             else text_list_problem(members)))
    return _first(*checks)


#: An index row's fields by the check each is held to. Where a location
#: points is not a value: the store asks the layout (``place_problem``).
_ENTRY_TEXT = ("identifier", "decision", "candidates")
#: A file's own name and the locations of real files (M5).
_ENTRY_NAMES = ("original_name", "prepared_location", "pbc_location", "container")
_ENTRY_LONG_TEXT = ("reason", "evidence", "also_filed", "answers")


def entry_problem(row: dict) -> str:
    """The first value of a stored index row outside the value rule, or
    ``""``. Values only: whether its locations are this return's places is
    the store's to judge, through the layout."""
    checks = []
    if row.get("received") not in (None, ""):
        checks.append(_field("received", received_problem(row["received"])))
    if "size_kb" in row:
        checks.append(_field("size_kb", number_problem(row["size_kb"], 0, MAX_ROW_SIZE_KB)))
    if "digest" in row:
        checks.append(_field("digest", digest_problem(row["digest"])))
    checks += [_field(name, text_problem(row[name])) for name in _ENTRY_TEXT
               if row.get(name) is not None]
    checks += [_field(name, name_problem(row[name])) for name in _ENTRY_NAMES
               if row.get(name) is not None]
    checks += [_field(name, text_problem(row[name], long=True)) for name in _ENTRY_LONG_TEXT
               if row.get(name) is not None]
    return _first(*checks)


def status_problem(status: dict) -> str:
    """The first field of one identifier's stored status outside the value
    rule, or ``""``."""
    # Blank is a status: a scan writes it for a row it did not judge.
    checks = [_field("status", text_problem(status.get("status")))]
    if status.get("file_count") is not None:
        checks.append(_field("file_count", count_problem(status["file_count"], 0, MAX_FILE_COUNT)))
    if status.get("received_date") not in (None, ""):
        checks.append(_field("received_date", date_problem(status["received_date"])))
    if status.get("validation_notes") is not None:
        checks.append(_field("validation_notes", text_problem(status["validation_notes"], long=True)))
    return _first(*checks)
