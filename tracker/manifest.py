"""The request list: its schema, its validation, and its reading from and
writing to the record (component 1, docs/ROADMAP.md).

**The manifest is the record's request list** (decision 104). It is the
eleven columns an accountant edits (:data:`COLUMNS`, whose headers are
:data:`HEADERS`) and the engagement's own details
(:class:`tracker.records.EngagementInfo`), and it lives in exactly one
place: the engagement's record - the journal beside the client's files
(:mod:`tracker.ledger`) folded into the store on the machine
(:mod:`tracker.store`, ``docs/storage.md``). There is no workbook. Until
this decision the list was a workbook (the file
``registry.LEGACY_MANIFEST_FILENAME`` names), read once a pass and
journalled as it changed; the owner retired it on 2026-09-19 - "I don't
want anything to do with the Excel manifest anymore. I just want it all on
the database." - and the workbook half of this module is set aside,
outside the tree, in ``Retired - Excel manifest``.

So this module does four things with that list:

- **it says what a row is.** :class:`RequestItem`, the column constants,
  :data:`COLUMN_HELP` (the sentence the app's editor shows under each
  heading) and the defaults - the one schema the store's ``requests``
  table, the API's ``edit`` command and the catalog in
  :mod:`tracker.templates` all write against;
- **it validates it, as a function on records.** The checks the sheet's
  loader used to make cell by cell are :func:`item_from_fields` (one row
  from plain values - the editor's JSON, a catalog spec) and
  :func:`validated` (the list: identifiers, duplicates without case, the
  counts, the date pattern compiled or derived from the Period, the
  narrowing names), each refusal naming the row and the column in one
  sentence. Every path that stores rules or routes against a catalog goes
  through them, so the derived year check the harnesses used to get from a
  workbook round trip is the same check, made once, here;
- **it reads it** (:func:`load_manifest`, :func:`load_engagement_info`):
  from the record - the rules as the last edit left them, each row's
  status, and the keywords a filing taught - after
  :func:`tracker.store.follow_the_journal` has brought the store up to
  the journal. A folder with no journal is nobody's engagement and is
  refused by sentence (:data:`NOT_AN_ENGAGEMENT`);
- **it writes it, at three moments and no others**: :func:`create_engagement`
  writes an engagement's first list and details as one ``rules_changed``
  event, :func:`save_rules` writes a person's edit as one - exactly
  the rows that changed, the identifiers removed, the details that moved,
  and nothing at all when nothing did - and :func:`unlearn_keyword` takes
  back a keyword a filing taught the row, as one ``keyword_unlearned``
  (decision 113), which is the only one of the three that does not touch
  the rules the person typed. All three go through
  :func:`tracker.store.record` under the engagement lock, so the journal
  is written first and the fold is one transaction. The app's editor is
  the only way a rule is entered; there is no import and no export.

Why the writes came back to this module, having left it in decision 103:
they left because a workbook was the person's file and the machine only
read it. The person's file is the record now, and the module that owns
the schema and the validation is the one that must own the two writes,
or the rows in the journal would be shaped by somebody else. It reaches
``store``, ``ledger`` and ``locking`` at call time - an in-layer edge,
closed where an edge is allowed to close (``tests/test_layers.py``) - and
imports :mod:`tracker.records` and nothing else of the package at load
time.

``row`` is the request's 1-based position in the list. It is part of the
rule: a row inserted in the middle moves every row below it, and those
rows are recorded as changed, because a person reordered them and the
record says so.

It used to own *how* the machine's own small files are written, because
the manifest was once the workbook they were written for. The temp suffix,
the temp path, the replacement context and the two writers over it are
:mod:`tracker.fsio` since decision 120, and this module neither holds nor
re-exports them.

The *records* this module reads and writes - :class:`EngagementInfo`,
:class:`StatusUpdate`, the details' field table, the serialisation of a
rule row - live in :mod:`tracker.records` since decision 100.
:class:`RequestItem` stays here: it is the schema of the list a person
edits, not a record of what the machine decided.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

# The records this module reads and writes live in tracker/records.py
# (decision 100): they are the shapes, this is the list. An in-layer
# import, and the only one that way round - nothing in records imports
# the manifest.
from tracker.records import (
    COL_IDENTIFIER,
    NO,
    RULE_FIELDS,
    YES,
    EngagementInfo,
    StatusUpdate,
    identifier_key,
    info_to_json,
    link_problem,
    rule_from_json,
    rule_to_json,
)

# ---------------------------------------------------------------- schema ----

COL_DOCUMENT = "Document"
COL_PERIOD = "Period"
COL_EXPECTED_COUNT = "Expected Count"
COL_ALLOWED_EXTENSIONS = "Allowed Extensions"
COL_MIN_SIZE_KB = "Min Size KB"
COL_REQUIRED_KEYWORDS = "Required Keywords"
COL_ANY_KEYWORDS = "Any Keywords"
COL_DATE_PATTERN = "Date Pattern"
COL_MANUAL_OVERRIDE = "Manual Override"
COL_OVERRIDE_REASON = "Override Reason"
#: Whether this request's document carries a name (decision 128). Last, as
#: it was added last, and yes by default everywhere: strict is the rule the
#: owner asked for.
COL_NAMED = "Named"
COL_STATUS = "Status"
COL_RECEIVED_DATE = "Received Date"
COL_FILE_COUNT = "File Count"
COL_VALIDATION_NOTES = "Validation Notes"

#: Each column's key in the record and the API, beside its header: the
#: twelve columns a person edits, in the order the editor shows them. The
#: keys are ``records.RULE_FIELDS`` less the two the person never types
#: (``row`` is the position, ``date_pattern_derived`` is what
#: ``validated()`` decided), and the assertion below holds the two lists
#: together.
COLUMNS: tuple[tuple[str, str], ...] = (
    (COL_IDENTIFIER, "identifier"),
    (COL_DOCUMENT, "document"),
    (COL_PERIOD, "period"),
    (COL_EXPECTED_COUNT, "expected_count"),
    (COL_ALLOWED_EXTENSIONS, "allowed_extensions"),
    (COL_MIN_SIZE_KB, "min_size_kb"),
    (COL_REQUIRED_KEYWORDS, "required_keywords"),
    (COL_ANY_KEYWORDS, "any_keywords"),
    (COL_DATE_PATTERN, "date_pattern"),
    (COL_MANUAL_OVERRIDE, "manual_override"),
    (COL_OVERRIDE_REASON, "override_reason"),
    (COL_NAMED, "named"),
)
#: The headers, in order. The roadmap's schema table lists exactly
#: these (``tests/test_single_source.py`` holds it to that), the Status
#: Report draws them, and every message that names a column uses one.
HEADERS = tuple(header for header, _ in COLUMNS)
assert tuple(field for _, field in COLUMNS) == tuple(
    f for f in RULE_FIELDS if f not in ("row", "date_pattern_derived")
)

DEFAULT_EXPECTED_COUNT = 1
DEFAULT_MIN_SIZE_KB = 5
#: The bounds ``validated()`` and ``item_from_fields()`` enforce on the
#: two numbers, and where the editor's number inputs take their minimum
#: from - through the API's vocabulary, never typed in the page.
MIN_EXPECTED_COUNT = 1
MIN_SIZE_KB_FLOOR = 0

#: The one sentence the editor shows under each heading, by field. The
#: roadmap's schema table carries the same sentences in its Purpose column
#: on purpose: one text, two places a person reads it.
COLUMN_HELP: dict[str, str] = {
    "identifier": "Names the request and its folder; matched by prefix, so A100 and BS01 both work",
    "document": "What the request is called to people",
    "period": "The period asked for, e.g. TY2025 or Dec 2025; a year in it is the year check",
    "expected_count": "How many files are due; counted over distinct valid files",
    "allowed_extensions": "File types accepted, comma-separated; blank means the safe default, * means any type",
    "min_size_kb": "Files smaller than this are rejected as placeholders",
    "required_keywords": (
        "Every one of these must appear in the document (a keyword may hold alternatives with | "
        "and phrases wanted together with +)"
    ),
    "any_keywords": "At least one of these must appear; a keyword reads the same way",
    "date_pattern": (
        "Blank with a year in Period checks for that year; * turns the year check off; "
        "a typed regex wins"
    ),
    "manual_override": (
        "Accepted counts as Received; Not Applicable takes the request out of every count "
        "for the year"
    ),
    "override_reason": "Why the rules were overridden; required when Manual Override is Accepted",
    "named": (
        "yes: the document carries the taxpayer's or the entity's name and files only where "
        "that name is on the page; no: a receipt, a log or a headerless export, filed by its "
        "keywords alone when the name is absent"
    ),
}
assert set(COLUMN_HELP) == {field for _, field in COLUMNS}

#: What a blank Allowed Extensions means. A blank used to mean "accept
#: anything", which is easy to leave by accident and lets an .exe count as a
#: document; accepting anything now has to be said out loud with "*".
DEFAULT_EXTENSIONS = ("pdf", "xlsx", "csv")
ANY_EXTENSION = "*"
#: A blank Date Pattern on a row whose Period names a year checks for that
#: year; "*" says "no year check" out loud. The year was already typed once,
#: in Period - typing it again as a regex was the redundancy, and not typing
#: it was a 2024 form satisfying a TY2025 request.
NO_DATE_CHECK = "*"
#: The years a tax year can be. The pattern below is built from them, the
#: app's year inputs are bounded by them, and every path that takes a year
#: from a person checks it against them through :func:`check_tax_year`.
YEAR_MIN = 1900
YEAR_MAX = 2099
#: What a year outside those bounds is told, wherever it was typed.
YEAR_OUT_OF_RANGE = "Tax year must be between {minimum} and {maximum}, got {year}"
#: A four-digit year standing on its own. The digit guards keep an account
#: number like 120250 from being read as "2025". Used wherever a year is
#: found or shifted: the derived year check, rollover, the catalog.
YEAR_PATTERN = re.compile(
    r"(?<!\d)(?:" + "|".join(str(c) for c in range(YEAR_MIN // 100, YEAR_MAX // 100 + 1))
    + r")\d{2}(?!\d)"
)
_PERIOD_YEAR = YEAR_PATTERN

#: Characters Windows forbids in file and folder names, plus control
#: characters - the one list, for identifiers and for sanitising names.
_ILLEGAL_PUNCTUATION = '\\/:*?"<>|'
WINDOWS_ILLEGAL_CHARS = re.compile("[" + re.escape(_ILLEGAL_PUNCTUATION) + r"\x00-\x1f]")
WINDOWS_ILLEGAL_CHARS_TEXT = " ".join(_ILLEGAL_PUNCTUATION)
#: The names Windows keeps for devices (decision 137, L6). A folder or a
#: file named one of them - with or without an extension, in any case - is
#: not a folder at all: ``NUL`` is the null device, ``COM1`` a serial port,
#: and a request folder, a household or a return named one could never
#: hold a document.
WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{n}" for n in range(1, 10)}
    | {f"LPT{n}" for n in range(1, 10)}
    # The superscript digits Windows reserves too (the review's F6).
    | {f"{port}{digit}" for port in ("COM", "LPT") for digit in "\u00b9\u00b2\u00b3"}
)
WINDOWS_RESERVED_NAMES_TEXT = ("CON, PRN, AUX, NUL, CONIN$, CONOUT$, COM1-COM9, LPT1-LPT9 "
                               "and their superscript-1, 2 and 3 forms")


def is_reserved_name(name: str) -> bool:
    """Whether Windows reads ``name`` as a device rather than a file or a
    folder: a reserved name, alone or before an extension (``nul.txt``),
    whatever its case and any spaces before the dot."""
    stem = str(name).split(".", 1)[0].rstrip(" ")
    return stem.upper() in WINDOWS_RESERVED_NAMES
#: How a date is asked for on a command line or in the wizard.
ISO_DATE_HINT = "YYYY-MM-DD"

#: Characters an identifier may not contain. The identifier becomes the
#: prefix of a Windows folder name and is matched back by that prefix, so
#: anything the filesystem would alter (``WINDOWS_ILLEGAL_CHARS``) or strip
#: (a trailing dot) would leave the scanner unable to
#: find the folder scaffold just made — a permanent "folder not found".
_ILLEGAL_IDENTIFIER_CHARS = WINDOWS_ILLEGAL_CHARS



class Status:
    """Scanner-resolved status values (plain constants, stored as strings)."""

    MISSING = "Missing"
    PARTIAL = "Partial"
    FAILED = "Failed Validation"
    RECEIVED = "Received"
    PENDING_SYNC = "Pending Sync"

    ALL = (MISSING, PARTIAL, FAILED, RECEIVED, PENDING_SYNC)
    #: The client still owes us something: what the reminder asks for and
    #: what ``summarize`` counts as outstanding, decided once.
    OUTSTANDING = (MISSING, PARTIAL, FAILED)


#: What a row with no status yet is called wherever a count is shown: it
#: has been requested and nothing has been looked at. Not a Status, because
#: the scanner never writes it.
UNSCANNED_LABEL = "Requested"
#: How ``Summary.line`` joins its counts, and what it says with no rows.
SUMMARY_SEPARATOR = " · "
SUMMARY_EMPTY = "no requests"


class Override:
    """Accountant judgment values that beat the automated rules.

    ``ACCEPTED`` treats the row as Received despite the checks, and carries
    a reason (:data:`OVERRIDE_REASONS`, decision 116). ``NOT_APPLICABLE``
    says the request does not apply this year - shown to people with the
    row's own year (:func:`override_label`) - and takes the row out of
    every count, every reminder and the active table.

    ``RETIRED`` is the retired-value rule of decision 104 applied to a
    value: the spelling journals written before decision 116 hold for the
    second value, folded to its successor on every read by
    :func:`_override` and never written again.
    """

    ACCEPTED = "Accepted"
    NOT_APPLICABLE = "Not Applicable"

    ALL = (ACCEPTED, NOT_APPLICABLE)
    RETIRED: dict[str, str] = {"Waived": NOT_APPLICABLE}


#: The reasons a person may give for an ``Override.ACCEPTED`` override, offered as a
#: list so a reason is usually one click. The stored value is the reason's
#: text: one of these, or the person's own words when they chose
#: :data:`OVERRIDE_REASON_OTHER` - the word "Other" itself is never stored,
#: because a reason that says "other" records nothing.
OVERRIDE_REASONS: tuple[str, ...] = (
    "Client confirmed this is the final version",
    "Correct document, validation flagged formatting only",
    "Received outside the system (in person, fax, confirmed in a meeting)",
    "Prior-year or substitute document accepted",
)
OVERRIDE_REASON_OTHER = "Other"

#: How a Not Applicable row is named to people: with the year its Period
#: gives, so "does not apply" is always "does not apply *this year*". The
#: value stored is ``Override.NOT_APPLICABLE``; the year is derived from
#: the row's Period, which is the year's one home, and is never stored.
NOT_APPLICABLE_LABEL = "Not Applicable in TY{year}"



class ManifestError(Exception):
    """A request list could not be read, parsed, or validated."""


#: What a reader says of a folder that holds no journal: it is not an
#: engagement, whatever else is in it. The journal's file name is filled in
#: at call time by the reader, because this module does not import the
#: ledger at load time.
NOT_AN_ENGAGEMENT = "{name}: no record here ({ledger}); it is not an engagement"

#: What :func:`unlearn_keyword` says of a pair the record never carried.
#: A person may take back a keyword a filing taught; they may not take
#: back a word the row types itself (that is an edit of the rule) and they
#: may not take back a word nobody taught - both are the same refusal,
#: because the record is what says a word was learned (decision 113).
UNLEARN_REFUSED = "{identifier} was never taught {keyword!r}; nothing to unlearn"


@dataclass(frozen=True, slots=True)
class RequestItem:
    """One request: the person's rule, and what the record says about it.

    ``records.RULE_FIELDS`` names the person's half - the twelve columns
    (:data:`COLUMNS`) plus ``row``, the request's 1-based position in the
    list - and that half is what a ``rules_changed`` event and the
    store's ``requests`` table carry. The four status fields are the
    record's: ``validated()`` leaves them at their defaults and
    :func:`load_manifest` fills them from the store's ``statuses``.
    """

    identifier: str
    document: str
    period: str = ""
    expected_count: int = DEFAULT_EXPECTED_COUNT
    allowed_extensions: tuple[str, ...] = ()   # lowercase, no leading dot
    min_size_kb: int = DEFAULT_MIN_SIZE_KB
    required_keywords: tuple[str, ...] = ()
    any_keywords: tuple[str, ...] = ()
    date_pattern: str = ""                     # validated to compile on load
    date_pattern_derived: bool = False         # True: made from Period's year, not typed
    manual_override: str = ""                  # "", Override.ACCEPTED, Override.NOT_APPLICABLE
    status: str = ""                           # the record's, never typed
    received_date: dt.date | None = None
    file_count: int | None = None
    validation_notes: str = ""
    row: int = 0                               # 1-based position in the list
    override_reason: str = ""                  # why; required with Override.ACCEPTED
    #: Whether this request's document carries a name (decision 128).
    #: True by default and everywhere a row is read without one: strict is
    #: the rule, so a row nobody has marked is a row that needs the name on
    #: the page. False is a receipt, a log or a headerless export - filed
    #: on its keywords alone when no name is there to find.
    named: bool = True

    @property
    def label(self) -> str:
        """``A01 - W-2 Wage Statements (TY2025)`` - how a request is named to people."""
        text = label_for(self.identifier, self.document)
        return f"{text} ({self.period})" if self.period else text

    @property
    def year(self) -> int | None:
        """The tax year this one row is about, from its own Period and typed
        date rule (:func:`detect_year` over the row alone), or None."""
        return detect_year([self])

    @property
    def expected_text(self) -> str:
        """``2 files expected`` when more than one file is due, else ``""``."""
        return EXPECTED_PATTERN.format(n=self.expected_count) if self.expected_count > 1 else ""


def shift_years(text: str, delta: int) -> str:
    """Move every four-digit year in ``text`` by ``delta``.

    Shifting rather than substituting one fixed year keeps *relative* periods
    correct: on a 2025 -> 2026 roll, a row asking for the TY2024 prior-year
    return correctly comes to ask for TY2025.
    """
    if not text or not delta:
        return text
    return YEAR_PATTERN.sub(lambda m: str(int(m.group(0)) + delta), text)


def shift_item(item: RequestItem, delta: int) -> RequestItem:
    """``item`` with every year in its document, period and typed date pattern moved.

    A derived year check is left alone: the shifted Period derives it again.
    """
    if not delta:
        return item
    return replace(
        item,
        document=shift_years(item.document, delta),
        period=shift_years(item.period, delta),
        date_pattern="" if item.date_pattern_derived else shift_years(item.date_pattern, delta),
    )


def detect_year(items: Iterable[RequestItem]) -> int | None:
    """The tax year a list of rows is about, inferred from its own rows.

    The most common year across periods and typed date rules wins; ties go
    to the later year. None when nothing carries a year at all.
    """
    from collections import Counter

    years: Counter[int] = Counter()
    for item in items:
        for text in (item.period, "" if item.date_pattern_derived else item.date_pattern):
            for match in YEAR_PATTERN.findall(text or ""):
                years[int(match)] += 1
    if not years:
        return None
    best = max(years.values())
    return max(year for year, count in years.items() if count == best)


def override_label(item: RequestItem) -> str:
    """The word a person sees for the row's override.

    ``Override.ACCEPTED`` is its own word. ``Override.NOT_APPLICABLE`` is
    said with the year the row's Period gives
    (:data:`NOT_APPLICABLE_LABEL`), because a
    request that does not apply does not apply *this year*; a row whose
    Period names no year is said with the bare value. A blank override is
    a blank. The value stored is never the label: the year is derived
    every time from the Period, which is the one place it is kept.
    """
    if item.manual_override != Override.NOT_APPLICABLE:
        return item.manual_override
    year = detect_year([item])
    return NOT_APPLICABLE_LABEL.format(year=year) if year else Override.NOT_APPLICABLE


#: How a request's parts are joined into one name: the README line, the
#: request folder and the working copy all use it.
LABEL_SEPARATOR = " - "


def label_for(*parts: str) -> str:
    """``A01 - W-2 Wage Statements`` from its parts, blanks dropped."""
    return LABEL_SEPARATOR.join(part for part in parts if part)


#: How a multi-file request says so, everywhere (the README, the reminder,
#: the app's wizard preview).
EXPECTED_PATTERN = "{n} files expected"



# --------------------------------------------------------------- parsing ----


def csv_tuple(value: object) -> tuple[str, ...]:
    """A comma-separated list as typed, or a list the caller already has.

    A typed cell holds one string; a spec typed as JSON holds ``["pdf"]``, and
    stringifying that gave the single extension ``['pdf']``, which no
    document has and every document therefore parked against for ever.
    """
    if isinstance(value, (list, tuple)):
        return tuple(str(v).strip() for v in value if str(v).strip())
    text = "" if value is None else str(value).strip()
    return tuple(p.strip() for p in text.split(",") if p.strip())


#: What one keyword may hold beside its words. A keyword cell's commas are
#: the column's own word - every one of them in Required Keywords, any one
#: of them in Any Keywords - and neither column can say "these three
#: words, or this one". A prior-year return row has to: the federal return
#: is known by three lines only it prints, and a standalone state return
#: by its own printed title, which shares none of them (decision 90). So a
#: keyword may name alternatives with ``|``, and join with ``+`` the
#: phrases one alternative wants together:
#:
#:     individual income tax return + filing status + under penalties of
#:     perjury | resident income tax return
#:
#: reads "all of these, or that one", and another state's return is one
#: more ``|``. A keyword holding neither character is one phrase, exactly
#: as every keyword was before, and no shipped keyword held either.
KEYWORD_ANY_OF = "|"
KEYWORD_ALL_OF = "+"


def keyword_alternatives(keyword: str) -> tuple[tuple[str, ...], ...]:
    """One keyword as the alternatives it accepts, each a tuple of phrases
    the document must say together.

    ``"trial balance"`` is ``(("trial balance",),)``; the grammar costs a
    plain keyword nothing. Read here rather than in the matcher because
    this module owns how a keyword cell is read (``csv_tuple``), and the
    catalog writes cells the matcher then reads - one owner for the shape
    of a keyword, whether it was typed into the editor or written in
    :mod:`tracker.templates`.
    """
    alternatives = []
    for alternative in keyword.split(KEYWORD_ANY_OF):
        parts = tuple(p.strip() for p in alternative.split(KEYWORD_ALL_OF) if p.strip())
        if parts:
            alternatives.append(parts)
    return tuple(alternatives)



# ------------------------------------------------- a row per issuer (d93) ----

#: What a keyword cell cannot hold, replaced by the space between words:
#: the comma the cell is split on (:func:`csv_tuple`) and the two
#: characters the keyword grammar reserves (:func:`keyword_alternatives`).
_RESERVED_IN_A_NAME = ",|+"
#: Dropped outright rather than spaced, so "L.P." is one word and not two.
_DROPPED_FROM_A_NAME = "."
_RUN_OF_SPACES = re.compile(r"\s+")


def entity_keyword(name: str) -> str:
    """An entity's name as a keyword cell can hold it.

    An *issuer row* (decision 93, the owner's) is an ordinary request row
    whose Required Keywords cell holds the name of the entity that issued
    the document, so that a person holding several Schedule K-1s gets one
    row per issuing entity instead of one folder with everything in it.
    The name is somebody's typing, and typing carries punctuation a
    keyword cell cannot:

    - **A comma cannot survive.** The cell is comma-separated
      (:func:`csv_tuple`), so "Ashford Holdings, L.P." is not one keyword
      but two - ``Ashford Holdings`` and ``L.P.`` - and Required Keywords
      is an AND over its cells, so the row would quietly start demanding
      both. Nothing warns; the row simply stops being the row that was
      meant.
    - **``|`` and ``+`` are the grammar's** (:data:`KEYWORD_ANY_OF`,
      :data:`KEYWORD_ALL_OF`): a name holding either would be read as
      alternatives rather than as a name.
    - **A period is dropped**, so that the two ways one person writes an
      entity agree with each other: "Ashford Holdings, L.P." and "Ashford
      Holdings LP" are the same row, whichever was typed.

    The consequence is worth saying out loud, because it is what the
    runbook tells a person: the name is then matched against the document
    the way every keyword is - whole tokens, case-insensitive, an
    apostrophe or a dash forgiven (:func:`tracker.content_check.says`) -
    and a legal suffix the K-1 prints as "L.P." is no longer in the
    keyword to be found. So the name to type is the distinctive part
    ("Ashford Holdings"), not the suffix.
    """
    spaced = "".join(
        "" if ch in _DROPPED_FROM_A_NAME else " " if ch in _RESERVED_IN_A_NAME else ch
        for ch in str(name)
    )
    return _RUN_OF_SPACES.sub(" ", spaced).strip()


def _folded(keywords: Iterable[str]) -> set[str]:
    return {k.strip().lower() for k in keywords if k.strip()}


def narrowing_rows(items: Iterable[RequestItem]) -> dict[str, tuple[str, ...]]:
    """Which rows narrow which: the broad row's identifier → the rows that narrow it.

    A row **narrows** another when it asks for the same document and
    something more about it. That is exactly the shape a person makes an
    issuer row in: copy the K-1 row, name it for the entity, and put the
    entity's name in Required Keywords. So:

    - the **broad** row recognises its document on looser words alone -
      Any Keywords, and no Required Keywords, so it can never be the
      strongest evidence for anything (:func:`tracker.router._required_matched`);
    - the **narrowing** row shares at least one of those looser words, so
      it is asking about the same document, and requires something on top.

    One shared word, rather than every one of them, because a keyword a
    person teaches one of the two rows (``add_any_keyword``) must not
    silently unpair them and start filing unnamed K-1s on the broad row
    again. Nothing in any shipped catalog narrows anything - no catalog
    row has Required Keywords where another has none and a looser word in
    common - so this relation is empty until a person adds an issuer row,
    and ``tests/test_catalog.py`` says so by name.
    """
    items = list(items)
    narrowed: dict[str, list[str]] = {}
    for broad in items:
        if broad.required_keywords or not broad.any_keywords:
            continue
        broad_words = _folded(broad.any_keywords)
        for narrow in items:
            if narrow.identifier == broad.identifier or not narrow.required_keywords:
                continue
            if broad_words & _folded(narrow.any_keywords):
                narrowed.setdefault(broad.identifier, []).append(narrow.identifier)
    return {broad: tuple(rows) for broad, rows in narrowed.items()}


def _name_tokens(item: RequestItem) -> frozenset[str]:
    """A narrowing row's required words as whole tokens, normalised."""
    joined = entity_keyword(" ".join(item.required_keywords)).lower()
    return frozenset(t for t in re.split(r"[^a-z0-9]+", joined) if t)


def check_narrowing_names(items: Iterable[RequestItem]) -> None:
    """Refuse a list where one issuer row's name is inside another's.

    "Ashford" and "Ashford Holdings" both accept the Ashford Holdings
    K-1, so every one of them would be contested and park - one row
    quietly making the other useless, with nothing said. The fix is a
    person renaming a row, and the only moment they can be told is when
    the list is validated. Names are compared as whole tokens, normalised
    (:func:`entity_keyword`), and only between rows narrowing the *same*
    broad row: two unrelated requests are allowed to share a word.
    """
    by_identifier = {i.identifier: i for i in items}
    for broad, narrow_identifiers in narrowing_rows(by_identifier.values()).items():
        named = [(i, _name_tokens(by_identifier[i])) for i in narrow_identifiers]
        for inner, inner_words in named:
            for outer, outer_words in named:
                if inner != outer and inner_words and inner_words < outer_words:
                    raise ManifestError(
                        f"Rows {inner} and {outer} both narrow {broad}, and {inner}'s "
                        f"name is inside {outer}'s: a document naming "
                        f"{', '.join(by_identifier[outer].required_keywords)} matches "
                        "both rows, so every one of them would park. Rename one so "
                        "that neither name is part of the other."
                    )



_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_MONTH_NAMES = ("january", "february", "march", "april", "may", "june", "july", "august",
                "september", "october", "november", "december")


def derived_date_pattern(period: str) -> str:
    """The date check a Period like ``TY2025`` or ``Dec 2025`` implies, or "".

    Case-insensitive, whole-token: ``\b2025\b`` matches "Tax Year 2025"
    and "12/31/2025" but not an account number that happens to contain it.
    A Period that names a month asks for that month too - "December 2025",
    "Dec 2025" or a "12/dd/2025" date - so a November statement is not the
    December one a row asks for.
    """
    match = _PERIOD_YEAR.search(period or "")
    if not match:
        return ""
    year = match.group(0)
    month = next((m for m in _MONTHS if (period or "").lower().lstrip().startswith(m)), None)
    if month is None:
        return rf"(?i)\b{year}\b"
    number = _MONTHS.index(month) + 1
    name = rf"(?:{month}|{_MONTH_NAMES[number - 1]})\.?"          # Dec, Dec., December
    return (
        rf"(?i)(?:\b{name}\s[^\n]{{0,20}}\b{year}\b|"
        rf"\b{year}\b[^\n]{{0,20}}\b{name}\b|\b0?{number}/[0-3]?[0-9]/(?:{year}|{year[2:]})\b)"
    )


def check_tax_year(year: int) -> int:
    """``year`` back, or ``ManifestError`` if it is not a year a tax return
    is for. One check, because a year that reaches a list unbounded
    shifts every Period by a few thousand years and the document names
    with them; the wizard's box and the rollover's flag are two doors into
    the same room.
    """
    if not YEAR_MIN <= year <= YEAR_MAX:
        raise ManifestError(YEAR_OUT_OF_RANGE.format(minimum=YEAR_MIN, maximum=YEAR_MAX, year=year))
    return year


def parse_extensions(value: object) -> tuple[str, ...]:
    """Blank → the safe default; ``*`` → anything (empty tuple); else the list."""
    parts = csv_tuple(value)
    if not parts:
        return DEFAULT_EXTENSIONS
    if any(p == ANY_EXTENSION for p in parts):
        return ()
    return tuple(e.lower().lstrip(".") for e in parts)


def identifier_problem(identifier: str) -> str:
    """Why ``identifier`` cannot name a request folder, or "" if it can.

    Shared by :func:`validated` and the desktop app's create path so a
    bad identifier is refused with the same sentence wherever it is typed.
    """
    if _ILLEGAL_IDENTIFIER_CHARS.search(identifier):
        return f"may not contain any of {WINDOWS_ILLEGAL_CHARS_TEXT} (it becomes a folder name)"
    if identifier != identifier.rstrip(". "):
        return "may not end with a dot or a space (Windows drops them from folder names)"
    if is_reserved_name(identifier):
        return (f"may not be a name Windows keeps for a device ({WINDOWS_RESERVED_NAMES_TEXT}); "
                f"it becomes a folder name")
    return ""



# ------------------------------------------------ a row from plain values ----


def _whole_number(value: object, default: int, minimum: int, column: str, where: str) -> int:
    """A count or a size from a typed value: blank is the default, anything
    else a whole number no smaller than ``minimum``, refused with the row
    and the column named."""
    text = "" if value is None else str(value).strip()
    if not text:
        return default
    try:
        number = float(text)
        if number != int(number):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise ManifestError(f"{where}: {column} must be a whole number, got {value!r}") from None
    if int(number) < minimum:
        raise ManifestError(f"{where}: {column} must be at least {minimum}")
    return int(number)


def _override(value: object, where: str) -> str:
    """A Manual Override as typed or as stored, folded to the one spelling,
    or blank.

    A retired spelling (``Override.RETIRED``) folds to its successor before
    the match, so every read of a rule row - the store's rows becoming
    ``RequestItem``s, the editor's round trip, a value typed by hand - sees
    the current value, and the retired one is never written again.
    """
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    for retired, successor in Override.RETIRED.items():
        if text.lower() == retired.lower():
            text = successor
    for candidate in Override.ALL:
        if text.lower() == candidate.lower():
            return candidate
    raise ManifestError(
        f"{where}: {COL_MANUAL_OVERRIDE} must be one of {', '.join(Override.ALL)} (or blank), "
        f"got {value!r}"
    )


def _override_reason(value: object, override: str, where: str) -> str:
    """An Override Reason as typed: required with ``Override.ACCEPTED``,
    never the word :data:`OVERRIDE_REASON_OTHER` itself, and nothing on a
    row with no override - a reason for a decision nobody made."""
    text = "" if value is None else str(value).strip()
    if override == Override.ACCEPTED and not text:
        raise ManifestError(
            f"{where}: {COL_OVERRIDE_REASON} is required when {COL_MANUAL_OVERRIDE} is "
            f"{Override.ACCEPTED}"
        )
    if text.lower() == OVERRIDE_REASON_OTHER.lower():
        raise ManifestError(
            f"{where}: {COL_OVERRIDE_REASON} {OVERRIDE_REASON_OTHER} needs the reason typed"
        )
    if text and not override:
        raise ManifestError(f"{where}: {COL_OVERRIDE_REASON} needs a {COL_MANUAL_OVERRIDE}")
    return text


def _named(value: object, where: str) -> bool:
    """A Named mark as the editor sends it, as the catalog writes it, or as
    the store hands it back: the two yes/no words, a boolean, or blank.

    **Blank is yes.** A row nobody has marked is strict (decision 128): a
    list pasted from a spreadsheet without the column, a row typed in the
    wizard, and a rule stored before the mark existed all need the name on
    the page. Anything else is refused with the column named, exactly as a
    Manual Override nobody recognises is.
    """
    if value is None or value == "":
        return True
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == YES:
        return True
    if text == NO:
        return False
    raise ManifestError(f"{where}: {COL_NAMED} must be {YES} or {NO} (or blank), got {value!r}")


def item_from_fields(fields: Mapping[str, object], *, where: str) -> RequestItem:
    """One request row from plain values: the editor's JSON, a catalog spec,
    a test's dict.

    **The one parser of a row.** The sheet used to be parsed cell by cell;
    the same defaults and the same refusals are made here from a mapping
    keyed by :data:`COLUMNS`' field names, and ``where`` is what every
    refusal begins with (``"Row 3"`` from the API, the identifier from the
    catalog). Strings are stripped; the two numbers take their defaults
    when blank and must be whole and no smaller than the floor; the file
    types go through :func:`parse_extensions` (``"extensions"`` is accepted
    as the key too, as the wizard has always sent it); the keywords through
    :func:`csv_tuple`, a string or a list; the override is folded to its
    one spelling; the date pattern is kept as typed - whether it compiles,
    and what a blank one derives from the Period, is :func:`validated`'s
    to say, because that is a fact about the list and not the row. A row
    that says its pattern was derived (``date_pattern_derived``, as the
    store hands rows back) is read as having none typed, so a list read
    out of the record and sent back in is the same list.

    It defaults **no keyword**: a row with no rule is legal and is warned
    about (:func:`check_rules`), as the sheet allowed. The catalog's
    ``item_from_spec`` adds its own rule on top.
    """
    def text(key: str) -> str:
        value = fields.get(key)
        return "" if value is None else str(value).strip()

    extensions = fields.get("allowed_extensions")
    if extensions in (None, ""):
        extensions = fields.get("extensions")
    return RequestItem(
        identifier=text("identifier"),
        document=text("document"),
        period=text("period"),
        expected_count=_whole_number(fields.get("expected_count"), DEFAULT_EXPECTED_COUNT,
                                     MIN_EXPECTED_COUNT, COL_EXPECTED_COUNT, where),
        allowed_extensions=parse_extensions(extensions),
        min_size_kb=_whole_number(fields.get("min_size_kb"), DEFAULT_MIN_SIZE_KB,
                                  MIN_SIZE_KB_FLOOR, COL_MIN_SIZE_KB, where),
        required_keywords=csv_tuple(fields.get("required_keywords")),
        any_keywords=csv_tuple(fields.get("any_keywords")),
        date_pattern="" if fields.get("date_pattern_derived") else text("date_pattern"),
        manual_override=_override(fields.get("manual_override"), where),
        override_reason=text("override_reason"),
        named=_named(fields.get("named"), where),
    )


def item_from_record(row: Mapping[str, object]) -> RequestItem:
    """One request row as the record holds it, read as this version reads it.

    The one reader of a stored rule row - :func:`load_manifest`, the diff
    in :func:`save_rules` and the rows the API hands the editor all come
    through here - so a retired override spelling folds to its successor
    (:func:`_override`) on every read, and a field the row was written
    without (a reason, on a row stored before decision 116) is its default
    rather than the column's null. The store and the journal keep the bytes
    they hold; what changes is only what is read out of them.
    """
    values = rule_from_json(dict(row))
    identifier = str(values.get("identifier", ""))
    values["manual_override"] = _override(values.get("manual_override"), identifier)
    if values.get("override_reason") is None:
        values["override_reason"] = ""
    return RequestItem(**values)


def rule_as_read(row: Mapping[str, object]) -> dict:
    """A stored rule row in the shape a ``rules_changed`` event carries it,
    as this version reads it (:func:`item_from_record`)."""
    return rule_to_json(item_from_record(row))


def validated(items: Iterable[RequestItem]) -> list[RequestItem]:
    """The list-level checks the sheet's loader made, on records.

    Every path that stores rules or routes against a catalog goes through
    this - ``create_engagement``, ``save_rules``, the IRS-form and catalog
    harnesses, the vocabulary report - so one list is validated one way:
    an identifier on every row, none the file system would alter
    (:func:`identifier_problem`), no two the same without case (a Windows
    folder name is not case-sensitive); a document on every row; the two
    numbers within their floors; ``NO_DATE_CHECK`` made blank, a typed
    pattern made to compile, and a blank one derived from the Period with
    ``date_pattern_derived`` set; the override folded to its one spelling
    and its reason read against it (:func:`_override_reason`: required
    with ``Override.ACCEPTED``, never the word :data:`OVERRIDE_REASON_OTHER`,
    none without an override); and last, no two issuer rows whose names
    nest (:func:`check_narrowing_names`). Returns new items with ``row``
    set to 1..n - the position is part of the rule (decision 104).

    A row that comes in with a derived pattern already set (one a reader
    gave back) is treated as blank and derived again: a derived check was
    never typed, and re-reading it as typed would turn it into a rule the
    person did not make.
    """
    out: list[RequestItem] = []
    seen: dict[str, int] = {}
    for n, item in enumerate(items, start=1):
        where = f"Row {n}"
        identifier = item.identifier.strip()
        if not identifier:
            raise ManifestError(f"{where}: {COL_IDENTIFIER} is required")
        problem = identifier_problem(identifier)
        if problem:
            raise ManifestError(f"{where}: {COL_IDENTIFIER} {identifier!r} {problem}")
        key = identifier_key(identifier)
        if key in seen:
            raise ManifestError(f"Duplicate identifier {identifier!r} (rows {seen[key]} and {n})")
        seen[key] = n
        document = item.document.strip()
        if not document:
            raise ManifestError(f"{where}: {COL_DOCUMENT} is required")
        if item.expected_count < MIN_EXPECTED_COUNT:
            raise ManifestError(f"{where}: {COL_EXPECTED_COUNT} must be at least {MIN_EXPECTED_COUNT}")
        if item.min_size_kb < MIN_SIZE_KB_FLOOR:
            raise ManifestError(f"{where}: {COL_MIN_SIZE_KB} must be at least {MIN_SIZE_KB_FLOOR}")
        period = item.period.strip()
        date_pattern = "" if item.date_pattern_derived else item.date_pattern.strip()
        derived = False
        if date_pattern == NO_DATE_CHECK:
            date_pattern = ""
        elif date_pattern:
            try:
                re.compile(date_pattern)
            except re.error as exc:
                raise ManifestError(f"{where}: {COL_DATE_PATTERN} is not a valid regex: {exc}") from None
        else:
            date_pattern = derived_date_pattern(period)
            derived = bool(date_pattern)
        override = _override(item.manual_override, where)
        out.append(replace(
            item,
            identifier=identifier,
            document=document,
            period=period,
            date_pattern=date_pattern,
            date_pattern_derived=derived,
            manual_override=override,
            override_reason=_override_reason(item.override_reason, override, where),
            row=n,
        ))
    # Two issuer rows whose names nest make each other useless and say
    # nothing about it; the one moment a person can be told is now.
    check_narrowing_names(out)
    return out


# --------------------------------------------------------------- reading ----


def _the_record(engagement_dir: Path | str):
    """The store's connection, brought up to this engagement's journal.

    Imported here, not at the top: this module owns the list, the store
    owns the tables, and the two sit in the same layer with no load-time
    edge between them (``tests/test_layers.py``). A folder with no journal
    is refused: it has nothing to fold and is nobody's engagement - a
    folder somebody made a moment ago, or one that holds only a workbook
    the tracker no longer reads.
    """
    from tracker import ledger, store

    folder = Path(engagement_dir)
    if not ledger.path_for(folder).exists():
        raise ManifestError(NOT_AN_ENGAGEMENT.format(name=folder.name, ledger=ledger.LEDGER_FILENAME))
    conn = store.connect()
    store.follow_the_journal(conn, store.root_for(folder), folder)
    return conn


def load_manifest(engagement_dir: Path | str) -> list[RequestItem]:
    """Every request, as the record answers it now, in the list's order.

    The rules are the ones the last edit left in the store's ``requests``
    table, each row's Status, Received Date, File Count and Validation
    Notes come from ``statuses``, and a keyword a person's filing taught
    the row is added to its Any Keywords from ``learned_keywords``. The
    store is a derivation of the journal and
    :func:`tracker.store.follow_the_journal` makes it one again first, so
    no reader has to know whether a pass prepared this engagement -
    exactly as ``tracker.filer.read_index`` does for the index.

    Raises :class:`ManifestError` for a folder that holds no record.
    """
    from tracker import store

    folder = Path(engagement_dir)
    conn = _the_record(folder)
    items = [item_from_record(row) for row in store.rules(conn, folder) or []]
    return _with_the_record(
        items, store.statuses(conn, folder), store.learned_keywords(conn, folder)
    )


def _with_the_record(
    items: Iterable[RequestItem],
    statuses: Mapping[str, StatusUpdate],
    learned: Mapping[str, tuple[str, ...]],
) -> list[RequestItem]:
    """The person's rules with what the record holds about each laid on top.

    One place where "what a request is now" is assembled: the status the
    last scan recorded, and the keywords a person's filings taught the row
    added to the ones they typed. Identifiers are matched without case,
    because a folder name on Windows is (``records.identifier_key``).
    """
    out = []
    for item in items:
        key = identifier_key(item.identifier)
        update = statuses.get(key)
        taught = tuple(
            word for word in learned.get(key, ())
            if word.lower() not in {k.lower() for k in item.any_keywords}
        )
        if update is None and not taught:
            out.append(item)
            continue
        out.append(replace(
            item,
            any_keywords=item.any_keywords + taught,
            **({} if update is None else {
                "status": update.status,
                "file_count": update.file_count,
                "received_date": update.received_date,
                "validation_notes": update.validation_notes,
            }),
        ))
    return out


def with_statuses(
    items: Iterable[RequestItem], updates: Mapping[str, StatusUpdate]
) -> list[RequestItem]:
    """``items`` with each row's status replaced by ``updates``, where it has one.

    What a scan shows of itself before the record has been read again: the
    scanner resolves a status per row and counts the rows as it is about to
    leave them (``ScanReport.summary``). Identifiers match without case,
    the way every reading that joins a status to a request does.
    """
    by_identifier = {identifier_key(identifier): update for identifier, update in updates.items()}
    return _with_the_record(items, by_identifier, {})



def load_engagement_info(engagement_dir: Path | str) -> EngagementInfo:
    """The engagement's own details, as the record holds them.

    The one reader that wants this half alone and not the rules: the
    registry, which asks every folder under the clients root who it is
    for; the reminder, for its greeting and sign-off; the scaffold, for
    the README's contact line. Every field is at its default on an
    engagement nothing has recorded details for. Raises
    :class:`ManifestError` for a folder that holds no record.
    """
    from tracker import store

    folder = Path(engagement_dir)
    conn = _the_record(folder)
    return store.engagement_info(conn, folder) or EngagementInfo()


# --------------------------------------------------------------- writing ----


@dataclass(frozen=True, slots=True)
class RulesSaved:
    """What one save of the list recorded: the identifiers of the rows that
    changed or were added, the identifiers removed, the engagement fields
    that moved, and whether anything was written at all."""

    changed: tuple[str, ...]
    removed: tuple[str, ...]
    info_fields: tuple[str, ...]
    recorded: bool


def create_engagement(
    engagement_dir: Path | str,
    items: Iterable[RequestItem],
    info: EngagementInfo | None = None,
    *,
    form: str = "",
) -> None:
    """Write an engagement's first request list and details into its record.

    The folder must exist and hold no journal: a live engagement carries a
    season of somebody's rules and must never be written over by a re-run.
    ``items`` are validated whole before anything is written, so a refusal
    leaves no folder content and no store row; then, under the engagement
    lock, the store is brought up to the (empty) journal and **one**
    ``rules_changed`` event carries the whole list and the whole of
    ``info``. That first event is what every later edit is a difference
    from, and what makes the fold of every event the list.

    ``form`` is the catalog the rows were cut from, recorded in the
    details. A keyword rather than a field of the rows because it is one
    fact about the engagement, not a property of any request. Optional,
    and a blank never clears a form ``info`` already carries.
    """
    from tracker import ledger, store
    from tracker.locking import engagement_lock

    folder = Path(engagement_dir)
    if not folder.is_dir():
        raise ManifestError(f"{folder} is not a folder; make it before creating the engagement")
    if ledger.path_for(folder).exists():
        raise ManifestError(f"Refusing to overwrite an engagement that already has a record: {folder}")
    rows = [rule_to_json(item) for item in validated(items)]
    info = info or EngagementInfo()
    # A reminder's link is a web address or nothing (decision 137, L5).
    if problem := link_problem(info.link):
        raise ManifestError(problem)
    if form:
        info = replace(info, form=form)
    conn = store.connect()
    with engagement_lock(folder):
        # A row the store may still hold for this folder - a name whose
        # folder was deleted by hand and is being set up again - would
        # read the new, shorter journal as truncated; forget it first.
        store.forget(conn, folder)
        store.follow_the_journal(conn, store.root_for(folder), folder)
        store.record(conn, folder, ledger.new(ledger.RULES_CHANGED, **{
            ledger.RULES_KEY: rows,
            ledger.REMOVED_KEY: [],
            ledger.INFO_KEY: info_to_json(info),
        }))


def save_rules(
    engagement_dir: Path | str,
    items: Iterable[RequestItem],
    info: EngagementInfo,
    *,
    lock_held: bool = False,
) -> RulesSaved:
    """Record a person's edit of the list and the details as one event.

    Validated whole first (:func:`validated`), so a refusal records
    nothing. Then, under the engagement lock (taken here unless the caller
    already holds it), the list is diffed against what the store holds:
    ``changed`` is every row whose stored form differs from the held row
    of the same identifier, spelled exactly - whole rows, ``row`` included,
    so a row moved is a row changed - ``removed`` is every held identifier
    no longer present in that exact spelling, and the details are the
    fields that differ from the ones recorded, or all of them when no
    rules event has ever been written. Nothing changed, nothing written:
    a save of the same list is not an event. Otherwise one
    ``rules_changed`` event carries exactly the difference, through
    :func:`tracker.store.record`, journal first.

    **Journalled, not simply written.** The record cannot stop a person
    mistyping a keyword, but it can say when it changed and to what, which
    is the difference between a rule that went wrong and a rule nobody can
    account for - and it is what lets the store be rebuilt from the
    journals alone.
    """
    from contextlib import nullcontext

    from tracker import ledger, store
    from tracker.locking import engagement_lock

    folder = Path(engagement_dir)
    rows = [rule_to_json(item) for item in validated(items)]
    now = info_to_json(info)
    with nullcontext() if lock_held else engagement_lock(folder):
        conn = _the_record(folder)
        held = store.rules(conn, folder) or []
        first = not store.has_rules_event(conn, folder)
        # Diffed by the identifier's exact spelling, because that is how
        # the fold and the store key a rule. A respelling by case is a
        # removal of the old spelling and an addition of the new, in one
        # event; diffing by the folded key here would carry the new
        # spelling and never name the old one, and the record would hold
        # both for good. The stored side is read the way every reader
        # reads it (rule_as_read: a retired override spelling folded, a
        # field the row never had at its default), so a list read out of
        # the record and saved back unchanged is not an event, and a
        # retired value is rewritten only when the row itself changes.
        was = {str(row["identifier"]): rule_as_read(row) for row in held}
        changed = [row for row in rows if was.get(str(row["identifier"])) != row]
        still_there = {str(row["identifier"]) for row in rows}
        removed = [str(row["identifier"]) for row in held if str(row["identifier"]) not in still_there]
        if first:
            moved = dict(now)
        else:
            before = info_to_json(store.engagement_info(conn, folder) or EngagementInfo())
            moved = {name: value for name, value in now.items() if before.get(name) != value}
        if not (changed or removed or moved):
            return RulesSaved(changed=(), removed=(), info_fields=(), recorded=False)
        # A reminder's link is a web address or nothing (decision 137, L5),
        # refused when a save changes it. A link recorded before this
        # decision does not block every later save of the list - the letter
        # drops it and says so - only a save that sets it.
        changing_link = moved.get("link")
        if changing_link is not None and (problem := link_problem(str(changing_link))):
            raise ManifestError(problem)
        store.record(conn, folder, ledger.new(ledger.RULES_CHANGED, **{
            ledger.RULES_KEY: changed,
            ledger.REMOVED_KEY: removed,
            ledger.INFO_KEY: moved,
        }))
    return RulesSaved(
        changed=tuple(str(row["identifier"]) for row in changed),
        removed=tuple(removed),
        info_fields=tuple(moved),
        recorded=True,
    )


@dataclass(frozen=True, slots=True)
class KeywordUnlearned:
    """What one unlearn took back: the request, and the word."""

    identifier: str
    keyword: str


def unlearn_keyword(
    engagement_dir: Path | str,
    identifier: str,
    keyword: str,
    *,
    lock_held: bool = False,
) -> KeywordUnlearned:
    """Take back a keyword a person's filing taught one request (decision 113).

    A word that seemed distinctive and was not - a common word that turns
    out to be on many unrelated documents - was permanent: the filing
    recorded it, every reader laid it over the row's own Any Keywords, and
    nothing took it back. This is the way back, per engagement. The
    firm-wide vocabulary is :mod:`tracker.templates` and still changes
    only by a commit, which is the graduation gate and always was.

    **Journalled, not simply deleted.** Deleting the store's row would
    take the word out of every reader's answer until the next rebuild put
    it back, because the journal is the record and the store is its
    derivation. So a word taught by an event is taken back by an event:
    one ``keyword_unlearned``, under the engagement lock (taken here
    unless the caller already holds it), through
    :func:`tracker.store.record` - journal first - and the history says
    who took it back and when.

    The request is matched without case, as every reading that joins a
    row to the record is (``records.identifier_key``), and the keyword
    exactly as the record holds it: the caller sends back the word it was
    shown. A pair the record never carried is refused by name
    (:data:`UNLEARN_REFUSED`) rather than passing quietly - a person
    cannot unlearn what nobody taught, and a word the row types itself is
    an edit of the rule, made in the editor like any other.

    **The line spells the request the way the list does.** The journal's
    own fold keys a taught word by the spelling its line carries - it sits
    below ``records`` and has no case rule of its own
    (:class:`tracker.ledger.Folded`) - and the filing that taught the word
    spelt the request as the list spells it. So the identifier recorded
    here is the one the rules hold, whatever case the caller used, or the
    caller's where no rule holds that request any more, and the journal
    read on its own (``python -m tracker.ledger``) shows the word gone -
    wherever the list still spells the request as the teaching line did.
    After a respelling by case it does not: the journal's fold keeps the
    word under the old spelling.
    The gate does not depend on it: ``store.check()`` folds the words by
    the store's case rule (decision 136), so a line spelt either way is
    the same request to it.

    Unfiling still unlearns nothing (decision 77): the request wanted the
    word when the document was filed and wants it still, and guessing
    which word to take back would be guessing.
    """
    from contextlib import nullcontext

    from tracker import ledger, store
    from tracker.locking import engagement_lock

    folder = Path(engagement_dir)
    with nullcontext() if lock_held else engagement_lock(folder):
        conn = _the_record(folder)
        taught = store.learned_keywords(conn, folder)
        if keyword not in taught.get(identifier_key(identifier), ()):
            raise ManifestError(UNLEARN_REFUSED.format(identifier=identifier, keyword=keyword))
        identifier = _as_the_list_spells_it(store.rules(conn, folder), identifier)
        store.record(conn, folder, ledger.new(ledger.KEYWORD_UNLEARNED, **{
            ledger.IDENTIFIER_KEY: identifier,
            ledger.KEYWORD_KEY: keyword,
        }))
    return KeywordUnlearned(identifier=identifier, keyword=keyword)


def _as_the_list_spells_it(stored: list[dict] | None, identifier: str) -> str:
    """``identifier`` in the spelling the request list holds, or as given
    where the list holds no such request."""
    key = identifier_key(identifier)
    for row in stored or []:
        held = str(row.get("identifier", ""))
        if identifier_key(held) == key:
            return held
    return identifier


def has_routing_rules(item: RequestItem) -> bool:
    """Can this row recognise a document - by a keyword, or a year check a
    person typed? A year derived from Period is a *check* on a document
    already matched by a keyword, never evidence on its own: "it says 2025"
    describes half of what a client sends."""
    return bool(
        item.required_keywords
        or item.any_keywords
        or (item.date_pattern and not item.date_pattern_derived)
    )


# --------------------------------------------------------------- summary ----


@dataclass(frozen=True, slots=True)
class Summary:
    """Where an engagement stands, counted one way for everyone.

    The runner's log line, the reminder's "N of M are in", the scanner CLI
    and the desktop summary all used to count for themselves, each with a
    slightly different idea of what an override meant. This is the count.
    Not Applicable rows are nobody's to wait on and are outside every figure
    except ``not_applicable``; an Accepted row is Received whatever its
    status cell says, so a signed-off row counts as in even before the next
    scan writes it.
    """

    counts: dict[str, int]   # status -> rows with it (Not Applicable rows excluded)
    total: int               # rows anybody is waiting on (Not Applicable excluded)
    received: int
    outstanding: int         # Missing + Partial + Failed Validation
    not_applicable: int
    unscanned: int           # rows with no status yet

    @property
    def line(self) -> str:
        """``Received: 3 · Missing: 2 · Not Applicable: 1`` - the same
        everywhere. The count is said with the bare value, not the year's
        label: a list may hold rows of more than one year."""
        parts = [f"{status}: {n}" for status, n in sorted(self.counts.items())]
        if self.unscanned:
            parts.append(f"{UNSCANNED_LABEL}: {self.unscanned}")
        if self.not_applicable:
            parts.append(f"{Override.NOT_APPLICABLE}: {self.not_applicable}")
        return SUMMARY_SEPARATOR.join(parts) or SUMMARY_EMPTY


def summarize(items: Iterable[RequestItem]) -> Summary:
    """Count ``items`` the one agreed way (see :class:`Summary`)."""
    counts: dict[str, int] = {}
    total = received = outstanding = not_applicable = unscanned = 0
    for item in items:
        if item.manual_override == Override.NOT_APPLICABLE:
            not_applicable += 1
            continue
        total += 1
        status = item.status
        if item.manual_override == Override.ACCEPTED:
            status = Status.RECEIVED
        if not status:
            unscanned += 1
            continue
        counts[status] = counts.get(status, 0) + 1
        if status == Status.RECEIVED:
            received += 1
        elif status in Status.OUTSTANDING:
            outstanding += 1
    return Summary(counts=counts, total=total, received=received,
                   outstanding=outstanding, not_applicable=not_applicable, unscanned=unscanned)



# ----------------------------------------------------------------- check ----

#: Form numbers that name a family, not a form: a keyword of just the number
#: matches none of the family's members (``1099`` does not match ``1099-INT``;
#: see ``tracker.content_check.contains_keyword``), so the check says so.
FORM_FAMILIES = {"1099": "1099-INT", "1095": "1095-A"}
EMPTY_KEYWORD_WARNING = (
    "Row {row} ({identifier}): the keyword '{keyword}' has no letters or digits and "
    "matches nothing; leave the cell blank instead"
)
BARE_FORM_NUMBER_WARNING = (
    "Row {row} ({identifier}): the keyword '{keyword}' matches only that form, not its "
    "variants such as {example}; list the forms this request means"
)


def check_rules(items: Iterable[RequestItem]) -> list[str]:
    """What a person should know about a list the rules will act on: legal,
    but probably not what was meant.

    The warnings half of what the old manifest check said; there is no
    problems half, because a list the record holds has been validated on
    the way in. Rides every ``state`` the app reads and every pass's
    report, so a request that can never auto-file is seen now rather than
    at a deadline: a row with no keyword and no typed date rule, a row
    accepting any file type (an .exe would count), a keyword with no
    letter or digit in it, and a bare family number that matches none of
    the family's forms. A Not Applicable row is nobody's to act on and is
    skipped.
    """
    warnings: list[str] = []
    for item in items:
        if item.manual_override == Override.NOT_APPLICABLE:
            continue
        if not has_routing_rules(item):
            warnings.append(
                f"Row {item.row} ({item.identifier}): no {COL_REQUIRED_KEYWORDS}, {COL_ANY_KEYWORDS} "
                f"or {COL_DATE_PATTERN}, so its documents can never be filed automatically"
            )
        if not item.allowed_extensions:
            warnings.append(
                f"Row {item.row} ({item.identifier}): {COL_ALLOWED_EXTENSIONS} is '{ANY_EXTENSION}', so any "
                "file type counts as this document"
            )
        for keyword in (*item.required_keywords, *item.any_keywords):
            if not any(ch.isalnum() for ch in keyword):
                warnings.append(EMPTY_KEYWORD_WARNING.format(
                    row=item.row, identifier=item.identifier, keyword=keyword.strip()))
            if keyword.strip() in FORM_FAMILIES:
                warnings.append(BARE_FORM_NUMBER_WARNING.format(
                    row=item.row, identifier=item.identifier, keyword=keyword.strip(),
                    example=FORM_FAMILIES[keyword.strip()],
                ))
    return warnings
