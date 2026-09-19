"""Triage of the review queue: a ranked shortlist, and never a filing.

The filer parks what the router would not guess at, and the index says why
in one sentence. For a person working that queue in March, "matched no
request" is where the work starts, not where it ends: they open the
document, read the request list, and decide. This module does the
reading-back part. It turns the evidence a verdict kept
(:class:`tracker.content_check.Evidence`, written into the index's Evidence
column) into a short ranked list of the requests a parked document most
plausibly belongs to, each with the sentence that says why it is on the
list.

**It triages and it never files.** Nothing here moves a file, writes a
status, takes the engagement lock, opens a client document or persists
anything. :func:`triage` reads the manifest and the index and computes; the
answer lives as long as the caller holds it and no longer. The index's
Evidence column is already the store, and a second one - a sidecar of
suggestions - could disagree with it the moment somebody filed a row by
hand, which is the kind of disagreement nobody notices until the wrong
document is under the right name.

**Evidence only; what the request list still wants is not a prior.** A row
the scanner calls outstanding is not thereby a better guess than one whose
document already arrived (owner, 2026-09-18). A nudge with no evidence
behind it is how a tired reviewer files the wrong document into the last
open row, and once it is filed the index says a person decided it. So a
parked row with nothing behind it - one that matched no request, a scan
whose name says nothing either, a record carrying only a refusal - gets an
**empty** shortlist and keeps the router's own reason, and the person reads
the document. No suggestion is better than an invented one.

**A file name is a suggestion and never a filing** (owner, 2026-09-18).
Since decision 92 the router files nothing on a name; what the name of an
unreadable scan says is kept on the parked row as ``RULE_FILENAME``
evidence, so it arrives here and becomes "A01 - the file name says W-2" at
the bottom of the ranking. That is the right place for it: it is the one
piece of evidence the *client* wrote rather than the form, so it starts a
person reading and cannot outrank a word the document itself said.

**A row that wants nothing is never suggested.** ``Override.WAIVED`` says
the firm no longer needs that document; offering it is offering a known
wrong answer. Rows a person marked ``NOT_REQUESTED`` (decision 76) are not
``NEEDS_REVIEW``, so they are never triaged at all, and a row sent back by
``UNFILED_BY_PERSON`` (decision 77) is parked and is.

**Three at most.** A shortlist is something a person reads at a glance and
acts on. Every row that ever said "1099", ranked, is the request list
again - which they already have, on the screen, beside this.

The words in a reason are the firm's own: the keyword off the manifest row,
the period it asked for, the file's own name, and the refusal's plain name
out of :mod:`tracker.reasons`. Not one word of a client's document is read
here or written anywhere, which is the line the content cache and the index
already draw.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tracker import reasons
from tracker.content_check import (
    RULE_ANY,
    RULE_DATE,
    RULE_FILENAME,
    RULE_REFUSED,
    RULE_REQUIRED,
    WHERE_DEEP,
    WHERE_FIRST_PAGE,
    WHERE_FOOTER,
    WHERE_TITLE,
    Evidence,
)
from tracker.filer import INDEX_FILENAME, NEEDS_REVIEW, IndexEntry, read_index
from tracker.manifest import Override, RequestItem, load_manifest
from tracker.scaffold import MANIFEST_FILENAME

#: How many requests one parked file is offered. Past three a shortlist
#: stops being read and starts being scrolled, and the fourth-best guess
#: has never been the one a person wanted.
MAX_SUGGESTIONS = 3

#: How strongly each rule speaks to what a document *is*, strongest first.
#: Required keywords are the accountant's assertion that a document says
#: its own name, which is why the router lets them outrank any-keywords
#: when it chooses between requests; the same order decides here. The
#: period is a *check* on a document, never evidence of which one it is
#: (decision 40), so it ranks below both. A keyword in the file's own name
#: is the weakest of all: the client chose that name, not the form.
#: ``RULE_REFUSED`` is deliberately absent - a refusal is never evidence
#: *for* a request, only a caveat on one (see :func:`_refusals_for`).
RULE_STRENGTH: dict[str, int] = {
    RULE_REQUIRED: 0,
    RULE_ANY: 1,
    RULE_DATE: 2,
    RULE_FILENAME: 3,
}

#: Where the term was said, strongest first. A form printing its own name
#: at the top is the strongest thing a document can say about itself; a
#: page footer is next, because a form repeats its number on every copy
#: there and a stray sentence does not; then the rest of the first page;
#: then deep inside, which is the weakest place a keyword can be said and
#: the one a person most wants named.
PLACE_STRENGTH: dict[str, int] = {
    WHERE_TITLE: 0,
    WHERE_FOOTER: 1,
    WHERE_FIRST_PAGE: 2,
    WHERE_DEEP: 3,
}

#: The rank's first slot, reserved for identity: a name or a number on the
#: document agreeing with the engagement's own, the year right before the
#: year wrong. Nothing reads identity yet (it arrives with C5), so every
#: suggestion carries ``IDENTITY_UNKNOWN`` today and the order below it is
#: the whole order. The slot is here so that when identity does arrive it
#: sorts *above* every content tier without renumbering anything.
IDENTITY_AGREES = 0
IDENTITY_AGREES_WRONG_YEAR = 1
IDENTITY_UNKNOWN = 2

#: How each place is said in a reason sentence - the one mapping, so the
#: app can label a place without typing a word of its own (the vocabulary
#: imports this; it does not restate it). ``{page}`` is filled from the
#: evidence, and dropped when the evidence has no page to give.
PLACE_WORDS: dict[str, str] = {
    WHERE_TITLE: "in the title",
    WHERE_FOOTER: "in the footer of page {page}",
    WHERE_FIRST_PAGE: "on page {page}",
    WHERE_DEEP: "on page {page}",
}
#: Said of a term whose place the evidence does not name.
NOWHERE_WORDS = "somewhere in the document"
#: Said of a keyword found in the file's own name rather than in it.
FILENAME_WORDS = "the file name says {term}"
#: How one of the row's own words is quoted back.
TERM_WORDS = "'{term}'"
#: Said of a parked file the evidence says nothing about.
NOTHING_SUGGESTED = "nothing to suggest - the evidence says nothing about which request this is"

#: How a reason sentence is put together: the request, then what was found,
#: then the rule that refused it.
IDENTIFIER_SEPARATOR = " — "
FOUND_SEPARATOR = ", "
REFUSAL_SEPARATOR = "; "

#: Every refusal by its code, so a ``RULE_REFUSED`` term (which travels as
#: the code, never the sentence) can be said in the words its one owner
#: gives it.
_REASON_BY_CODE: dict[str, reasons.Reason] = {reason.code: reason for reason in reasons.ALL}


@dataclass(frozen=True, slots=True)
class Suggestion:
    """One request a parked file might belong to, and why it is offered.

    ``rank`` sorts ascending, lowest first: ``(identity, strength,
    catalog)``. ``identity`` is the reserved slot above; ``strength`` is
    the best thing the evidence said about this request (:func:`_strength`);
    ``catalog`` is the row's position in the manifest, which breaks a tie
    the only way that is not a guess. Two requests with equal evidence
    therefore agree on the first two slots and differ only in the third.
    """

    identifier: str
    reason: str
    rank: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Triage:
    """One parked index row and the shortlist computed for it.

    ``genre`` and ``group`` are reserved: what kind of document this looks
    like, and which other parked files belong with it. Both arrive later
    (C5 and D5) and are empty until then, so a caller can render the whole
    shape now and gain them without a change.
    """

    entry: IndexEntry
    shortlist: tuple[Suggestion, ...] = ()
    genre: str = ""
    group: str = ""


def _strength(evidence: Evidence) -> int:
    """How strongly one piece of evidence points at a request; lower is stronger.

    Rule-major, place-minor: a required keyword said deep in a document
    still outranks an any-keyword in a title, because the two rules are
    different claims about what the document *is* and the place only says
    how loudly it was claimed. A rule or a place nothing recognises (a cell
    a person typed into) ranks last rather than raising - the index is an
    audit trail, and half a record read is better than a queue that will
    not load.
    """
    rule = RULE_STRENGTH.get(evidence.rule, len(RULE_STRENGTH))
    place = PLACE_STRENGTH.get(evidence.where, len(PLACE_STRENGTH))
    return rule * (len(PLACE_STRENGTH) + 1) + place


def _where_said(evidence: Evidence) -> str:
    """Where the term was said, in words."""
    words = PLACE_WORDS.get(evidence.where, NOWHERE_WORDS)
    if "{page}" not in words:
        return words
    return words.format(page=evidence.page) if evidence.page else NOWHERE_WORDS


def _said(evidence: Evidence) -> str:
    """One piece of evidence as a clause of the reason sentence."""
    if evidence.rule == RULE_FILENAME:
        return FILENAME_WORDS.format(term=evidence.term)
    return f"{TERM_WORDS.format(term=evidence.term)} {_where_said(evidence)}"


def _refusals_for(entry: IndexEntry, identifier: str, found: tuple[Evidence, ...]) -> list[str]:
    """The rules that refused this request, said in the words reasons.py gives them.

    Two places carry one: a ``RULE_REFUSED`` entry in the request's own
    evidence, and - for a request the row's Candidates cell names - the
    row's own reason, which is where a failed period check ends up when the
    document announced itself as that request's paperwork and then failed
    it. Deduplicated, because they are frequently the same refusal said
    twice.
    """
    codes = [e.term for e in found if e.rule == RULE_REFUSED]
    refused = [_REASON_BY_CODE[code] for code in codes if code in _REASON_BY_CODE]
    if identifier in entry.candidate_list:
        named = reasons.find(entry.reason)
        if named is not None:
            refused.append(named)
    said: list[str] = []
    for reason in refused:
        if reason.marker not in said:
            said.append(reason.marker)
    return said


def _reason_for(entry: IndexEntry, identifier: str, found: tuple[Evidence, ...]) -> str:
    """The one-line sentence behind a suggestion, strongest clause first."""
    content = sorted((e for e in found if e.rule != RULE_REFUSED), key=_strength)
    said = FOUND_SEPARATOR.join(_said(e) for e in content)
    refusals = _refusals_for(entry, identifier, found)
    if refusals:
        said = REFUSAL_SEPARATOR.join([said, *refusals])
    return f"{identifier}{IDENTIFIER_SEPARATOR}{said}"


def shortlist_for(entry: IndexEntry, items: list[RequestItem]) -> tuple[Suggestion, ...]:
    """The requests one parked row's evidence points at, best first.

    A request is offered only when the row's evidence said something *for*
    it. A candidate carrying nothing but a refusal is not a suggestion - it
    is the router saying the file could not be this request - and a
    candidate no longer on the manifest is not offered either, since there
    is no row left to file it into.
    """
    catalog = {item.identifier: (position, item) for position, item in enumerate(items)}
    suggestions: list[Suggestion] = []
    for identifier, found in entry.evidence_record.items():
        known = catalog.get(identifier)
        if known is None:
            continue
        position, item = known
        if item.manual_override == Override.WAIVED:
            continue
        content = tuple(e for e in found if e.rule != RULE_REFUSED)
        if not content:
            continue
        rank = (IDENTITY_UNKNOWN, min(_strength(e) for e in content), position)
        suggestions.append(Suggestion(identifier, _reason_for(entry, identifier, found), rank))
    suggestions.sort(key=lambda suggestion: suggestion.rank)
    return tuple(suggestions[:MAX_SUGGESTIONS])


def triage(
    engagement_dir: Path | str,
    *,
    items: list[RequestItem] | None = None,
    entries: list[IndexEntry] | None = None,
) -> list[Triage]:
    """Every parked file in one engagement, with its shortlist, oldest first.

    ``items`` and ``entries`` are for a caller that has already loaded the
    manifest and the index (the desktop app loads both to draw one screen);
    left out, they are read here. Either way this is a read: the index is
    read without moving a sidecar aside, no lock is taken, and nothing is
    written. Only rows the filer parked as ``NEEDS_REVIEW`` are triaged.
    """
    engagement_dir = Path(engagement_dir)
    if items is None:
        items = load_manifest(engagement_dir / MANIFEST_FILENAME)
    if entries is None:
        entries = read_index(engagement_dir / INDEX_FILENAME, quarantine=False)
    return [
        Triage(entry, shortlist_for(entry, items))
        for entry in entries
        if entry.decision == NEEDS_REVIEW
    ]


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Which request might each parked file belong to, and why? "
                    "Read-only: it suggests, and files nothing."
    )
    parser.add_argument("engagement_dir", help=f"folder containing {MANIFEST_FILENAME}")
    ns = parser.parse_args()

    parked = triage(ns.engagement_dir)
    print(f"{len(parked)} file(s) parked for a person in {Path(ns.engagement_dir)}\n")
    for triaged in parked:
        print(f"  {triaged.entry.original_name}  ({triaged.entry.reason})")
        for suggestion in triaged.shortlist:
            print(f"      {suggestion.reason}")
        if not triaged.shortlist:
            print(f"      {NOTHING_SUGGESTED}")
