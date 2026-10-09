"""Triage of the review queue: a ranked shortlist, and never a filing.

The filer parks what the router would not guess at, and the index says why
in one sentence. For a person working that queue in March, "matched no
request" is where the work starts, not where it ends: they open the
document, read the request list, and decide. This module does the
reading-back part. It turns the evidence a verdict kept
(:class:`tracker.records.Evidence`, written into the index's Evidence
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

**A row that wants nothing is never suggested - but it is named.**
``Override.NOT_APPLICABLE`` says the request does not apply this year;
offering it as a filing target is offering a known wrong answer. When the
evidence points at such a row anyway, the shortlist says so in one
sentence (:data:`SET_ASIDE_NOTE`, carried as ``Triage.set_aside``) - the
row's identifier and its year's label, and that clearing the override in
the editor is how to file there - so the person who set it aside decides,
and the machine never files under a row somebody said does not apply
(decision 116, amending 83). Rows a person marked ``NOT_REQUESTED``
(decision 76) are not ``NEEDS_REVIEW``, so they are never triaged at all,
and a row sent back by ``UNFILED_BY_PERSON`` (decision 77) is parked and
is.

**A name outranks every keyword** (decision 128). The household pass checks
the name on a page against the return's own people list, and what it found
rides the same evidence record as the keywords
(:data:`tracker.records.RULE_NAME`). A confirmed name takes the rank's
first slot - the one reserved for identity since C5 - so a suggestion on a
page that says whose it is is offered before one that only says what it is;
and the card says which of the three it was in one sentence, because a
person working the queue in March wants "the page names Maria Park" before
they want "'W-2' in the title". The spelling quoted is the firm's own, as
every other word here is.

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

import re
from dataclasses import dataclass
from pathlib import Path

from tracker import reasons
from tracker.filer import NEEDS_REVIEW
from tracker.manifest import Override, RequestItem, load_manifest, override_label
from tracker.names import NAME_ABSENT, NAME_CONFIRMED, NAME_VETOED
from tracker.records import (
    RULE_ANY,
    RULE_DATE,
    RULE_FILENAME,
    RULE_NAME,
    RULE_REFUSED,
    RULE_REQUIRED,
    WHERE_DEEP,
    WHERE_FIRST_PAGE,
    WHERE_FOOTER,
    WHERE_TITLE,
    Evidence,
    IndexEntry,
    as_pattern,
)

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
#: ``RULE_NAME`` sits **above** required keywords (decision 128), which is
#: what the negative number says: a keyword says what a document is and a
#: name says whose it is, and in a household where two returns ask for the
#: same row, whose it is is the harder half.
RULE_STRENGTH: dict[str, int] = {
    RULE_NAME: -1,
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

#: The rank's first slot: whether the document's own identity agrees with
#: the return's. Reserved since C5 and filled by decision 128 - a
#: suggestion whose row carries a **confirmed name**
#: (:data:`tracker.records.RULE_NAME`) ranks ``IDENTITY_AGREES`` and sorts
#: above every content tier; everything else is ``IDENTITY_UNKNOWN``.
#: The year never ranks: it is a *check* on a document and never evidence
#: of which one it is (decision 40).
IDENTITY_AGREES = 0
IDENTITY_UNKNOWN = 2

#: What the card says the page said about whose it is (decision 128). One
#: of the three, after the keyword sentence; the app types none of them.
#: ``{spelling}`` is always the firm's own spelling and ``{label}`` the
#: other return's own label - never a word of the document.
NAME_CONFIRMED_NOTE = "the page names {spelling}"
NAME_OTHER_NOTE = "the page names {spelling}, who is on {label}"
NAME_ABSENT_NOTE = "the page names none of this return's people"

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
#: Said of a set-aside row the evidence points at: named, with its year's
#: label, and never offered as a filing target. ``{identifier}`` and
#: ``{label}`` are filled from the row; the app fills the same pattern from
#: the vocabulary.
SET_ASIDE_NOTE = "{identifier} is {label} - clear it in the editor to file here"

#: How a reason sentence is put together: the request, then what was found,
#: then the rule that refused it.
IDENTIFIER_SEPARATOR = " — "
FOUND_SEPARATOR = ", "
REFUSAL_SEPARATOR = "; "

#: Every refusal by its code, so a ``RULE_REFUSED`` term (which travels as
#: the code, never the sentence) can be said in the words its one owner
#: gives it. The one table, :data:`tracker.reasons.BY_CODE`.
_REASON_BY_CODE: dict[str, reasons.Reason] = reasons.BY_CODE


@dataclass(frozen=True, slots=True)
class NameSaid:
    """What the page said about whose document this is (decision 128).

    ``outcome`` is one of :mod:`tracker.names`' three; ``spelling`` is the
    firm's own spelling that decided it, and ``label`` the other return's
    own label where the name belonged to somebody else. Both are blank
    where the page named nobody, which is the whole of an absent verdict.
    """

    outcome: str
    spelling: str = ""
    label: str = ""


@dataclass(frozen=True, slots=True)
class Suggestion:
    """One request a parked file might belong to, and why it is offered.

    ``rank`` sorts ascending, lowest first: ``(identity, strength,
    catalog)``. ``identity`` is the slot above - a confirmed name ranks
    first; ``strength`` is the best thing the evidence said about this
    request (:func:`_strength`); ``catalog`` is the row's position in the
    manifest, which breaks a tie the only way that is not a guess. Two
    requests with equal evidence therefore agree on the first two slots
    and differ only in the third.

    ``name`` is what the page said about whose it is, where it said
    anything: the same answer for every suggestion on one row, because it
    is the row's return that was judged and not the row's request.
    """

    identifier: str
    reason: str
    rank: tuple[int, ...]
    name: NameSaid | None = None


@dataclass(frozen=True, slots=True)
class SetAside:
    """One request the evidence points at that a person set aside as not
    applicable: its identifier, and the label its year gives it. Named to
    the person, never suggested (decision 116)."""

    identifier: str
    label: str


def set_aside_note(one: SetAside) -> str:
    """The one sentence a set-aside row is named with (:data:`SET_ASIDE_NOTE`)."""
    return SET_ASIDE_NOTE.format(identifier=one.identifier, label=one.label)


@dataclass(frozen=True, slots=True)
class Triage:
    """One parked index row and the shortlist computed for it.

    ``set_aside`` names the rows the evidence pointed at that the shortlist
    may not offer - rows set aside as not applicable - so the person sees
    why a document that plainly says "1040" has no suggestion, and what to
    do about it.

    ``genre`` and ``group`` are reserved: what kind of document this looks
    like, and which other parked files belong with it. Both arrive later
    (C5 and D5) and are empty until then, so a caller can render the whole
    shape now and gain them without a change.
    """

    entry: IndexEntry
    shortlist: tuple[Suggestion, ...] = ()
    set_aside: tuple[SetAside, ...] = ()
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


def _label_of(reason: str, spelling: str) -> str:
    """The other return's label, read back off the sentence the filer wrote.

    The pattern is built from the very sentences the filer wrote - the
    Reason's own template and the one way a spelling and a return are said
    together - so rewording either moves this reader with it, exactly as
    ``filer.moved_to`` reads a path back off a Reason (decisions 108 and
    109). The row is the only place the other return's label is kept, and
    it is kept there because the name's *evidence* is the spelling and a
    label is not evidence of anything.

    The spelling is known before the search - it is the row's own
    ``RULE_NAME`` evidence - so it goes into the pattern escaped, and the
    label group is greedy: a return name may itself hold a parenthesis
    (``1120S - Park (USA) Inc``), and what closes the label is the
    sentence's fixed tail rather than the first ``)``.
    """
    found = re.search(as_pattern(
        reasons.NAMES_ANOTHER_RETURN.template,
        listed=as_pattern(reasons.NAME_AND_RETURN,
                          spelling=re.escape(spelling), label=r"(?P<label>.+)"),
    ), reason)
    return found.group("label") if found is not None else ""


def _name_said(entry: IndexEntry, found: tuple[Evidence, ...]) -> NameSaid | None:
    """What the page said about whose document this is, from the row alone.

    The row's Reason says which of the three it was - the filer wrote one
    of :mod:`tracker.reasons`' three name sentences when the name is what
    parked it - and the :data:`tracker.records.RULE_NAME` evidence carries
    the spelling. A row the name tier said nothing about (an ordinary
    unmatched file, a duplicate) gets ``None`` and the card says nothing,
    which is right: no suggestion is better than an invented one.

    A veto is told from a confirmation by the row's code (decision 190),
    never by its sentence - which carries the client's file name and the
    subfolder it came from - and never by whether a regular expression
    over the prose happened to match: on a vetoed row the ``RULE_NAME``
    evidence carries the *other* return's spelling, and a failed match
    would read it as this return's and say the page names a person it
    does not. The other return's label is read back off the sentence the
    filer wrote once the code has said it is that sentence.
    """
    spelling = next((e.term for e in found if e.rule == RULE_NAME), "")
    if entry.code == reasons.NAMES_ANOTHER_RETURN.code:
        return NameSaid(NAME_VETOED, spelling, _label_of(entry.reason, spelling))
    if entry.code in (reasons.NAME_NOT_ON_PAGE.code, reasons.NO_PEOPLE_ON_FILE.code):
        return NameSaid(NAME_ABSENT)
    return NameSaid(NAME_CONFIRMED, spelling) if spelling else None


def _name_note(said: NameSaid | None) -> str:
    """One of the three sentences, filled, or "" where the page said
    nothing about whose it is."""
    if said is None:
        return ""
    if said.outcome == NAME_CONFIRMED:
        return NAME_CONFIRMED_NOTE.format(spelling=said.spelling)
    if said.outcome == NAME_VETOED:
        return NAME_OTHER_NOTE.format(spelling=said.spelling, label=said.label)
    return NAME_ABSENT_NOTE


def _refusals_for(entry: IndexEntry, identifier: str, found: tuple[Evidence, ...]) -> list[str]:
    """The rules that refused this request, said in the words reasons.py gives them.

    Two places carry one: a ``RULE_REFUSED`` entry in the request's own
    evidence, and - for a request the row's Candidates cell names - the
    row's own code (decision 190), which is where a failed period check
    ends up when the document announced itself as that request's paperwork
    and then failed it. Deduplicated, because they are frequently the same
    refusal said twice.
    """
    codes = [e.term for e in found if e.rule == RULE_REFUSED]
    refused = [_REASON_BY_CODE[code] for code in codes if code in _REASON_BY_CODE]
    if identifier in entry.candidate_list:
        named = _REASON_BY_CODE.get(entry.code)
        if named is not None:
            refused.append(named)
    said: list[str] = []
    for reason in refused:
        if reason.marker not in said:
            said.append(reason.marker)
    return said


def _reason_for(
    entry: IndexEntry, identifier: str, found: tuple[Evidence, ...],
    said_of_the_name: str = "",
) -> str:
    """The one-line sentence behind a suggestion, strongest clause first.

    The keyword clauses, then what the page said about whose it is
    (decision 128), then the rules that refused it - the order a person
    reads them in: what it looks like, whose it looks like, why it was not
    filed. The name's own evidence is not quoted twice: it is the sentence
    rather than a ``'term' on page 1`` clause, because a name is not one of
    the row's keywords.
    """
    content = sorted((e for e in found if e.rule not in (RULE_REFUSED, RULE_NAME)), key=_strength)
    clauses = [_said(e) for e in content]
    said = FOUND_SEPARATOR.join(clauses)
    if said_of_the_name:
        said = FOUND_SEPARATOR.join([said, said_of_the_name]) if said else said_of_the_name
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

    A row whose name the page confirmed ranks first, whatever its keywords
    said (decision 128): the return was judged, not the request, so every
    suggestion on that row takes the same first slot - and the name is then
    left out of the strength that sorts them within it, so the keywords
    keep their own order underneath.
    """
    catalog = {item.identifier: (position, item) for position, item in enumerate(items)}
    suggestions: list[Suggestion] = []
    for identifier, found in entry.evidence_record.items():
        known = catalog.get(identifier)
        if known is None:
            continue
        position, item = known
        if item.manual_override == Override.NOT_APPLICABLE:
            continue
        content = tuple(e for e in found if e.rule != RULE_REFUSED)
        if not content:
            continue
        said = _name_said(entry, found)
        identity = (IDENTITY_AGREES if said is not None and said.outcome == NAME_CONFIRMED
                    else IDENTITY_UNKNOWN)
        # The name has taken the identity slot already, so it is left out
        # of the strength slot: it is on every candidate of the row and at
        # the strongest tier there is, so counting it again would give
        # every candidate the same minimum and leave the keyword tiers
        # ordering nothing - an any-keyword row would sort above a
        # required-keyword one on catalog position alone. A candidate whose
        # only evidence *is* the name has no keyword tier to fall back on
        # and keeps the rank it had.
        keywords = [e for e in content if e.rule != RULE_NAME]
        rank = (identity, min(_strength(e) for e in (keywords or content)), position)
        suggestions.append(Suggestion(
            identifier, _reason_for(entry, identifier, found, _name_note(said)), rank, said))
    suggestions.sort(key=lambda suggestion: suggestion.rank)
    return tuple(suggestions[:MAX_SUGGESTIONS])


def set_aside_for(entry: IndexEntry, items: list[RequestItem]) -> tuple[SetAside, ...]:
    """The set-aside rows one parked file points at, in the list's order.

    A row is named when it is among the file's candidates or its record
    carries evidence for it, and a person set it aside as not applicable.
    It is a name and a sentence, never a :class:`Suggestion`: the person
    who set the row aside decides whether this document changes that, by
    clearing the override in the editor - the machine does not file under
    a row somebody said does not apply (decision 116).
    """
    pointed_at = set(entry.candidate_list) | set(entry.evidence_record)
    return tuple(
        SetAside(item.identifier, override_label(item))
        for item in items
        if item.manual_override == Override.NOT_APPLICABLE and item.identifier in pointed_at
    )


def triage(
    engagement_dir: Path | str,
    entries: list[IndexEntry],
    *,
    items: list[RequestItem] | None = None,
) -> list[Triage]:
    """Every parked file in one engagement, with its shortlist, oldest first.

    ``entries`` is the index as the caller has already read it, and it is
    **required**: this module suggests and never reads, and an argument a
    caller may leave out is an argument that quietly opens the engagement's
    index behind them. Every caller has read it already to draw the screen
    it is drawing. ``items`` may still be left out and is then read here,
    once, from the manifest.

    Either way this is a read: no lock is taken, no sidecar is moved aside
    and nothing is written. Only rows the filer parked as ``NEEDS_REVIEW``
    are triaged.
    """
    engagement_dir = Path(engagement_dir)
    if items is None:
        items = load_manifest(engagement_dir)
    return [
        Triage(entry, shortlist_for(entry, items), set_aside_for(entry, items))
        for entry in entries
        if entry.decision == NEEDS_REVIEW
    ]


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description="Which request might each parked file belong to, and why? "
                    "Read-only: it suggests, and files nothing."
    )
    parser.add_argument("engagement_dir", help="the engagement folder")
    ns = parser.parse_args()
    # A typed folder is parsed, never trusted: it must be a return's
    # place under the checked clients root (decision 188).
    from tracker import door
    from tracker.layout import LayoutError

    try:
        ns.engagement_dir = door.return_dir(Path(ns.engagement_dir).absolute())
    except (door.DoorError, LayoutError) as exc:     # the door's own sentences
        parser.error(str(exc))

    from tracker.filer import ensure, read_index

    engagement = Path(ns.engagement_dir)
    ensure(engagement)
    parked = triage(engagement, read_index(engagement))
    print(f"{len(parked)} file(s) parked for a person in {engagement}\n")
    for triaged in parked:
        print(f"  {triaged.entry.original_name}  ({triaged.entry.reason})")
        for suggestion in triaged.shortlist:
            print(f"      {suggestion.reason}")
        if not triaged.shortlist:
            print(f"      {NOTHING_SUGGESTED}")
        for one in triaged.set_aside:
            print(f"      {set_aside_note(one)}")
