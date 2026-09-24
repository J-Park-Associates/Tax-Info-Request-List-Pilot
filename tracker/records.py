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
import re
from dataclasses import asdict, dataclass, field, fields
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
    return IndexEntry(**{key: value for key, value in row.items() if key in known})


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

    ``label`` is the request's own label - the words the client already
    reads under *WHAT WE STILL NEED* - and never the client's file name nor
    the firm's working name. ``day`` is the date part of the row's received
    stamp, or ``None`` where the stamp does not read as a date.
    """

    return_path: Path
    label: str
    day: dt.date | None


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
#: as a new one does.
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
RULE_FLAG_FIELDS: frozenset[str] = frozenset({"date_pattern_derived", "named"})
#: What a yes/no rule field means when the line that wrote the row never
#: said - a journal from before the field existed, and so a column holding
#: null. The record owns the answer, because it is the record's default:
#: ``named`` is **true**, so a row written before decision 128 is strict.
RULE_FLAG_DEFAULTS: dict[str, bool] = {"date_pattern_derived": False, "named": True}
assert set(RULE_FLAG_DEFAULTS) == set(RULE_FLAG_FIELDS)


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
