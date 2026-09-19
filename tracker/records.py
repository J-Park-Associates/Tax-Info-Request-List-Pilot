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
facts about the record and not about the file it lands in. The writers
stay where they are: the workbook, the sidecar and the ledger are written
by :mod:`tracker.filer` and :mod:`tracker.manifest`, which is where the
lock, the retry and the atomic replace belong.

It sits at layer 1 and imports nothing of the package (``tests/test_layers.py``
pins that), so every layer above may name a record without reaching for the
module that produces it. :mod:`tracker.manifest` imports it, which is an
in-layer edge and allowed; nothing here imports the manifest, so the edge
cannot become a cycle.

**``RequestItem`` stays in the manifest.** It is not a record of what the
machine decided - it is the *schema* of the workbook a person edits, read
cell by cell with the manifest's own defaults, validation and column
names, and it means nothing away from the sheet it is parsed from. The
same goes for ``FileError``, ``FileReport`` and ``ContentResult``: they are
one run's report of what it did, produced and consumed inside the module
that did it, and never stored.

**The old names still work, for one release.** Each module a record left
keeps a re-export of it - ``from tracker.filer import IndexEntry`` resolves
to exactly this class, the same object, not a copy - so no caller had to
change in the commit that moved them. They are marked in each module, and
the release that follows removes them.

**What this is for.** The store of decision 101 reads and writes these
records; it will import them from here and never from
:mod:`tracker.filer`, because a store that had to import the filer to name
a row would import the workbook writer it is meant to replace.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, fields
from pathlib import Path

# ---------------------------------------------------------------- evidence ----

#: Which of the manifest row's rules found the term. ``required`` and ``any``
#: are the row's keyword lists, ``date`` its Period check, ``filename`` the
#: router's by-name fallback and ``refused`` a tier-2 refusal travelling as
#: evidence (the Reason's code). One list, named once, so the router, the
#: index and the app's vocabulary all say the same words.
RULE_REQUIRED = "required"
RULE_ANY = "any"
RULE_DATE = "date"
RULE_FILENAME = "filename"
RULE_REFUSED = "refused"
EVIDENCE_RULES: tuple[str, ...] = (
    RULE_REQUIRED, RULE_ANY, RULE_DATE, RULE_FILENAME, RULE_REFUSED,
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
#: date; L01: 1098-t@title filename``. Compact because it shares one Excel
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
#: second copy of the word would let one sheet drift from the other;
#: :mod:`tracker.manifest` imports it and lists it first in ``HEADERS``.
COL_IDENTIFIER = "Identifier"

#: How candidate identifiers are joined in the Candidates cell, and the
#: other working copies in Also Filed.
CANDIDATE_SEP = ", "


@dataclass(frozen=True, slots=True)
class IndexEntry:
    """One row of the index — the audit trail for one original file.

    The fields ARE the columns: their order is the column order, the
    ``INDEX_LAYOUT`` table below gives each its header and width, and the
    workbook is read back by header name, so a column added here is one
    edit and an older index (with columns since dropped) still reads.
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


#: field name -> (column header, Excel width). One table, in field order.
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

    The one shape for it. The snapshot sidecar writes it, the engagement's
    record writes it, and :func:`entry_from_json` reads it back, so a field
    added to the row above is carried by all three without another edit.
    A plain dict of the fields rather than ``dataclasses.asdict`` spelled
    out at each call site, because two call sites are two owners.
    """
    return {f.name: getattr(entry, f.name) for f in fields(IndexEntry)}


def entry_from_json(row: object) -> IndexEntry:
    """An IndexEntry from a stored row, ignoring keys a later version may add:
    a row for an original already moved must never be thrown away over a
    field this version does not know."""
    if not isinstance(row, dict):
        raise TypeError(f"index sidecar row is {type(row).__name__}, not an object")
    known = {f.name for f in fields(IndexEntry)}
    return IndexEntry(**{key: value for key, value in row.items() if key in known})


def ledger_key(entry: IndexEntry) -> str:
    """The identity the engagement's record keeps this row under.

    The index's own: where the client's preserved original is, which is what
    the snapshot merge keys on and what the app joins a review card back by.
    A row that names no original (only a workbook somebody built by hand has
    one) falls back to what else the row says about the document, so two such
    rows are not folded into one.

    It is still one location per row after decision 94, and that is why the
    index keeps one row for a page filed under several requests rather than
    one row per copy: two rows naming one preserved original would collide
    here, and the collision would be silent - the record would fold them
    into one and the workbook would go on holding two. The copies are a
    column of that row (``IndexEntry.also_filed``), not rows of their own.
    """
    return entry.pbc_location or f"{entry.received}|{entry.original_name}|{entry.digest}"


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

    @property
    def routed(self) -> bool:
        return self.identifier is not None

    @property
    def filed_to(self) -> tuple[str, ...]:
        """Every request this document is filed under, in the order the
        page names their forms; empty when it is not filed at all."""
        return () if self.identifier is None else (self.identifier, *self.also)


# ------------------------------------------------------------ engagement ----

#: The Engagement sheet's yes/no cells, as written; the manifest's
#: ``_parse_yes_no`` also reads the usual spellings a person types. Here
#: rather than beside that parser because the notes below are written from
#: them and a record's own words are the record's.
YES = "yes"
NO = "no"


@dataclass(frozen=True, slots=True)
class EngagementInfo:
    """The Engagement sheet: who this is for and how the run should treat it.

    Every field is optional. A manifest without the sheet (one made before
    it existed) loads as all defaults and is still processed.
    """

    # What each field is for is said once, in ENGAGEMENT_HELP below.
    client: str = ""
    name: str = ""
    link: str = ""
    due: dt.date | None = None
    sender: str = ""
    firm: str = ""
    reminders: bool = True
    active: bool = True
    rolled_from: str = ""
    #: Which catalog the request list was cut from, as the catalog keys it.
    #: Blank on an engagement made before it was recorded, and blank is
    #: unknown to every reader - nothing refuses a manifest for it.
    form: str = ""


#: Row labels on the Engagement sheet, in the order they are written.
ENGAGEMENT_FIELDS = (
    ("Client", "client"),
    ("Engagement Name", "name"),
    ("Share Link", "link"),
    ("Due Date", "due"),
    ("Sender", "sender"),
    ("Firm", "firm"),
    ("Reminders", "reminders"),
    ("Active", "active"),
    ("Rolled From", "rolled_from"),
    # Added last so an engagement made before it existed keeps every cell
    # where its reader and its owner left them; the sheet is read by label
    # (manifest._engagement_from_sheet), so a missing row is simply a blank value.
    ("Form", "form"),
)
#: field name -> the sheet's label, for messages that name a cell.
ENGAGEMENT_LABELS = {field_name: label for label, field_name in ENGAGEMENT_FIELDS}
#: What the yes/no and Rolled From cells mean, said on the sheet and in the README.
ENGAGEMENT_NOTES = {
    "reminders": f"{NO} = this client is not chased by email",
    "active": f"{NO} = the scheduled run skips this folder",
    "rolled_from": "written by the rollover; the engagement it names is no longer chased",
}
#: What each cell is for, as the README tells it.
ENGAGEMENT_HELP = {
    "client": "greeting name in the reminder",
    "name": "label; the folder name if blank",
    "link": "pasted into the reminder",
    "due": "the date the reminder asks the client to send things by",
    "sender": "who the reminder is from",
    "firm": "the sign-off line and the client README's contact (typed once at setup)",
    "form": "which catalog the request list was cut from; blank if it was never recorded",
    **ENGAGEMENT_NOTES,
}


@dataclass(frozen=True, slots=True)
class StatusUpdate:
    """Scanner output for one identifier, destined for the scanner columns."""

    status: str
    file_count: int = 0
    received_date: dt.date | None = None
    validation_notes: str = ""
