"""The request-list editor's save rules, and the details and people a
spec sends, as the dialog and the editor send them.

What a save from the editor writes is settled here, before
``manifest.save_rules`` records it, in parts that each uphold the decision
rows they name:

- **The details** (decisions 117 and 187). :func:`_info_from_spec` reads
  what the dialog or the editor sent over what is carried - last year's
  details on a rollover, the details as recorded on an edit - over the firm
  default; the editor's blank clears a value and the dialog's keeps it, the
  dates are the record's ``DATE_FIELDS``, read by the record's own date
  rule.
- **The people** (decision 128). :func:`_people_from_spec` parses the people
  block's shape and asks the record's typed people rule
  (``records.typed_person_problem``, SPEC-architecture-p2 P2.5) for every
  refusal, in order.
- **A row as the editor gets it, and as it is saved** (decisions 145 and
  160). :func:`_rule_for_the_editor` hands a stored rule out with "any" file
  type said as the star, and :func:`_as_recorded` fills a column a sent row
  leaves out from the record's row of that identifier: absent means
  unchanged.
- **The refusals**, each before anything is recorded:
  :func:`_refuse_a_list_nobody_is_asked_for`, creation's and the editor's
  one refusal (decision 142's review R6); :func:`_refuse_a_changed_row_past_the_limit`,
  creation's room standard for the rows a save changes (decision 131, P305,
  P307); and :func:`_refuse_taking_away_documents`, a request holding filed
  documents taken off the list (decision 160, the audit's D-7), which
  ``manifest.save_rules`` asks under the engagement lock.

**Why it is its own module** (SPEC-architecture-p5 P5.4, P341; the
architecture audit's C-1 item 2 and B-3). These rules sat in ``tracker.api``
at layer 5, where only the app's commands could reach them - the bug class
decision 123 found, when a rollover run on the command line missed a rule
the API alone applied. Here, a command line could reach them. The handler,
``tracker.api._cmd_edit``, keeps its body and calls these by import: the
body writes the command's warnings into the reply's envelope, which is the
API's per-command state (the audit's C-3). Creation and the rollover
command call :func:`_info_from_spec` and
:func:`_refuse_a_list_nobody_is_asked_for` the same way, and
``tracker.api.state`` hands each rule out through
:func:`_rule_for_the_editor`.

**Q-F, measured** (SPEC-architecture-p5 section 7). Through the one room
function as it stood, the editor's save would also have measured the
return's review folder where long paths are off, and refused every save of
a return whose folder has grown since creation, even one that changes no
row's path. Jason chose (C): the editor calls
:func:`tracker.copies.refuse_a_path_past_the_limit` with
``review_folder=False``, so there is one room function, its review-folder
term is creation's and the rollover's, and every save comes out as before -
the same comparison and the same sentence.

**Why it sits at layer 3.** It reads :func:`tracker.actions.documents_by_request`
in its own layer (the documents a request holds), :mod:`tracker.copies`
(layer 2, the room), the request list, the record types and
:mod:`tracker.screen_words` (layer 1; the two refusals it says,
``HOLDS_DOCUMENTS`` and ``NOTHING_ASKED``), and the bounds and the settings
(layer 0). It imports nothing above layer 3, and never the API, which
imports from here by name what its handlers call. A stand-in follows the
name's readers (the audit's A-4): ``dt`` and ``load_manifest`` are read
here as well as in the API, so a stand-in for either is set on both. It
does not log.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from pathlib import Path
from typing import cast

from tracker import bounds, records
from tracker.actions import documents_by_request
from tracker.copies import refuse_a_path_past_the_limit
from tracker.manifest import (
    ANY_EXTENSION,
    ISO_DATE_HINT,
    ManifestError,
    Override,
    item_from_record,
    load_manifest,
    rule_as_read,
)
from tracker.records import (
    DATE_FIELDS,
    ENGAGEMENT_LABELS,
    PEOPLE_LABEL,
    EngagementInfo,
    Person,
    identifier_key,
)
from tracker.screen_words import HOLDS_DOCUMENTS, NOTHING_ASKED
from tracker.settings import firm


def _info_from_spec(spec: dict, *, carry: EngagementInfo | None = None,
                    blank_clears: bool = False) -> EngagementInfo:
    """The engagement's details: what the dialog or the editor sent, over
    what is carried (last year's details on a rollover, the details as
    recorded on an edit), over the firm default.

    ``blank_clears`` is the editor's rule: a key present with a blank
    value clears the recorded value, and a key absent keeps it - a person
    who empties the Link box means the link to go. The dialog and the
    rollover keep their fallback: a blank there is nothing typed, and the
    carried or default value stands.

    The engagement's name is not written: the folder is the name, and a
    copy in the record would drift the first time the folder was renamed.
    """
    base = carry or EngagementInfo()

    def text(key: str, fallback: str) -> str:
        # One line, whatever was pasted: a detail with a line break inside
        # it would carry that break into the reminder draft's headers.
        def clean(value: object) -> str:
            return " ".join(str(value).split())

        if blank_clears and key in spec:
            return clean(spec[key] or "")
        value = spec.get(key)
        return clean(value) if value not in (None, "") else fallback

    def date(key: str) -> dt.date | None:
        # Which details are dates is the record's answer, so the two are
        # read by one rule and a third would be read by it too.
        typed = str(spec.get(key, "") or "").strip()
        if typed:
            # The record's own date rule (decision 187): a real calendar date
            # in the years the store's gate admits, never one it refuses.
            if bounds.date_problem(typed):
                raise ManifestError(
                    f"{ENGAGEMENT_LABELS[key]} must be {ISO_DATE_HINT}, got {typed!r}"
                )
            return dt.date.fromisoformat(typed)
        if blank_clears and key in spec:
            return None
        return getattr(base, key)

    return replace(
        base,
        client=text("client", base.client),
        link=text("link", base.link),
        sender=text("sender", base.sender),
        firm=text("firm", base.firm or firm()),
        reminders=bool(spec.get("reminders", base.reminders)),
        active=bool(spec.get("active", base.active)),
        people=_people_from_spec(spec["people"]) if "people" in spec else base.people,
        # DATE_FIELDS names the record's date fields only, each a date or None.
        **cast(dict, {key: date(key) for key in DATE_FIELDS}),
    )


def _people_from_spec(sent: object) -> tuple[Person, ...]:
    """The return's people as the dialog and the editor's block send them:
    a list of ``{kind, name, spellings}`` (decision 128).

    Every refusal is by name and in the words their one owner gives them:
    a kind nothing knows, a name nobody typed, a spelling of one word
    (:data:`tracker.records.ONE_WORD_SPELLING`). Nothing is inferred here -
    the app *proposes* spellings through ``propose-spellings`` and a person
    ticks them, and what arrives is what they ticked.
    """
    if not isinstance(sent, list):
        raise ManifestError(f"{PEOPLE_LABEL} must be a list of people")
    people: list[Person] = []
    for one in sent:
        if not isinstance(one, dict):
            raise ManifestError(f"{PEOPLE_LABEL} must be a list of people")
        kind = str(one.get("kind", "") or "").strip()
        name = " ".join(str(one.get("name", "") or "").split())
        if problem := records.typed_person_problem(kind, name):
            raise ManifestError(problem)
        spellings: list[str] = []
        for spelling in one.get("spellings") or []:
            spelling = " ".join(str(spelling).split())
            if not spelling:
                continue
            if problem := records.typed_spelling_problem(name, spelling):
                raise ManifestError(problem)
            if spelling not in spellings:
                spellings.append(spelling)
        people.append(Person(kind=kind, name=name, spellings=tuple(spellings)))
    return tuple(people)


def _rule_for_the_editor(row) -> dict:
    """One stored rule as ``state`` hands it out: read as every reader reads
    it (``rule_as_read``), with a row that accepts any file type saying so
    with the star, ``["*"]``.

    The record holds "any" as an empty list, but a person's blank means the
    default types (``parse_extensions``), and ``edit`` reads what it is sent
    as a person's row. So ``[]`` sent back unchanged became pdf, xlsx, csv
    and the save recorded a change nobody made (decision 145). The star is
    what the editor already sends for such a row, and it is how "any" has
    always had to be said; a blank typed in the editor still means the
    default types.
    """
    rule = rule_as_read(row)
    if not rule["allowed_extensions"]:
        rule["allowed_extensions"] = [ANY_EXTENSION]
    return rule


def _as_recorded(row: dict, recorded: dict | None) -> dict:
    """``row`` with every column it leaves out taken from ``recorded``, the
    record's row of the same identifier (decision 160): absent means
    unchanged, as it does for the details. A row the record does not hold
    is a new request and takes the defaults, as before.

    ``recorded`` is in the form ``state`` hands a rule out
    (:func:`_rule_for_the_editor`), which :func:`tracker.manifest.item_from_fields` reads
    back as the same rule. Three keys are not columns a person keeps on
    their own: ``row`` is the position, which the save numbers from the
    list's order; the file types sent as ``extensions`` are the file types;
    and ``date_pattern_derived`` is what the save decided of the date
    pattern, so it is kept only with the pattern it describes - when the
    row leaves the pattern out too, or sends back exactly the pattern the
    record holds. A pattern the person typed is theirs, derived or not.
    """
    if recorded is None:
        return row
    filled = dict(row)
    for key, value in _rule_for_the_editor(recorded).items():
        if key in row or key == "row":
            continue
        if key == "allowed_extensions" and "extensions" in row:
            continue
        if key == "date_pattern_derived" and "date_pattern" in row and \
                str(row["date_pattern"] or "").strip() != str(recorded.get("date_pattern") or "").strip():
            continue
        filled[key] = value
    return filled


def _refuse_taking_away_documents(engagement: Path, recorded: list[dict], items: list) -> None:
    """Refuse a save that would take a request holding filed documents off
    the list (decision 160, the audit's D-7): the first such request, by
    name and count (:data:`HOLDS_DOCUMENTS`). Compared without case, so a
    respelling by case alone keeps the request and is saved. Called by
    ``manifest.save_rules`` under the engagement lock, after the list's
    version is checked - so ``recorded`` is the list as it still stands."""
    kept = {identifier_key(item.identifier) for item in items}
    held = documents_by_request(engagement, [item_from_record(rule) for rule in recorded])
    for rule in recorded:
        key = identifier_key(str(rule["identifier"]))
        if key not in kept and held.get(key):
            raise ManifestError(HOLDS_DOCUMENTS.format(identifier=rule["identifier"], n=held[key]))


#: What a matched row is compared on to say the editor changed it (decision
#: 131): the things a working copy's path is made of, bar the identifier,
#: which rows are matched by (its key) and whose case is not a change (P305;
#: its length is compared separately). The short name a copy is named by
#: (decision 144) is the short title or the Document's derivation, so both
#: are compared (P307).
_PATH_FIELDS = ("document", "short_title", "period", "allowed_extensions")


def _refuse_a_changed_row_past_the_limit(engagement: Path, items: list) -> None:
    """The editor's save keeps creation's standard for the rows it changes
    (decision 131).

    A row is matched to the stored one by the identifier's key, so a change
    of case alone is the same row (decision 160, P305): a case change cannot
    alter a path's length, and a held row already past the limit is never
    refused one. The one exception is a respelling that keeps the key and
    changes the length: ``"İ".lower()`` is two code points, so ``İ01`` and
    ``i̇01`` are one key and two lengths, and that row counts as changed.
    A row whose document, short title, period or file types differ from the
    stored list, and every new row, is measured as creation measures a
    list (``copies.room_for``); one whose canonical working copy would pass
    what Windows opens refuses the save with creation's own sentence, and
    nothing is recorded - the person shortens the label and saves again.
    A row the person did not touch is never refused: it is already in the
    room the page and the banner report, so shortening one label is never
    trapped by another. A row set Not Applicable is not measured, as
    creation does not measure it, and neither is a row nobody asked for
    (decision 142); a row a person has just set Asked, or taken off Not
    Applicable, is measured, because it is now a request creation would
    have measured (P307).
    """
    stored = {identifier_key(item.identifier): item for item in load_manifest(engagement)}
    changed = []
    for item in items:
        held = stored.get(identifier_key(item.identifier))
        # The identifier's length is compared beside the fields: ``.lower()``
        # lengthens the one letter "İ", so a respelling that keeps the key
        # can still grow the path (SPEC-form-inputs section 22).
        if (held is None
                or len(item.identifier) != len(held.identifier)
                or any(getattr(item, name) != getattr(held, name) for name in _PATH_FIELDS)
                or (item.asked and not held.asked)
                or (held.manual_override == Override.NOT_APPLICABLE
                    and item.manual_override != Override.NOT_APPLICABLE)):
            changed.append(item)
    refuse_a_path_past_the_limit(engagement, changed, review_folder=False)


def _refuse_a_list_nobody_is_asked_for(items: list) -> None:
    """A return always asks for at least one thing: every catalog row is on
    it, but a list with no asked row would chase nothing and list nothing
    as needed. Refused at creation and at every editor save, in the same
    words, before anything is recorded."""
    if not any(item.asked for item in items):
        raise ManifestError(NOTHING_ASKED)
