"""Deterministic routing of dropped files to manifest rows (component 6).

The client drops everything into one folder. This module decides, for each
dropped file, which request it satisfies — using nothing but the manifest's
own rules. No AI reads the document, and nothing is ever guessed: a file is
routed only when exactly one request accepts it. Anything ambiguous or
unrecognized is parked for a human, because misfiling a tax document is
worse than not filing it.

Evidence, strongest first:

1. **Required keywords** — the document says what the request says it must
   say ("a W-2 says W-2") *and* every other rule on that row passes. The
   strongest claim a manifest row can make about a document's identity.
2. **Any keywords / period** — the row's looser rules pass. Enough on its
   own, but it loses to a required-keyword match, because tax forms are
   full of shared boilerplate: a real W-2 carries the line "To Be Filed
   With Employee's FEDERAL Tax Return", which a prior-year-returns row
   would otherwise happily claim.

There is no third tier. **A file name is not evidence** (owner,
2026-09-18): the client chose it, the form did not, and a document nobody
here can read is filed by nobody. A scan with no text layer that OCR
cannot rescue parks with ``reasons.NO_READABLE_TEXT``, and the keywords
its name does carry go with it as evidence for the person who will open
it (:func:`_filename_evidence`) - a shortlist to read the document
against, at the weakest tier :mod:`tracker.review` ranks, and never a
filing. The cost is known and was accepted: a scan the reader cannot
read parks.

A scan with no text layer is read by OCR (the reader ships inside the app
since decision 169, so it can run on every machine) - the same
reading the scanner would make of it later
(:func:`tracker.content_check.extract`), so the two never disagree about
what the file says. Its name no longer excuses that reading: OCR is now
the only thing that can still file a scan, and the scan whose name says
"W-2" is exactly the one whose content has to be read. But OCR text is
read *more strictly* than a text layer: it routes a file only on a
request's **required** keywords. OCR misreads words, and the looser
any-keyword tier is exactly where a misread "1099" would file a document
under the wrong request; those matches go to a person instead
(``OCR_ONLY``).

Two things deliberately do *not* route a file:

- **A matching extension.** A row that accepts ``pdf`` would otherwise
  swallow every PDF in the drop. A request with no keyword rules never
  auto-routes; its files go to review with a note naming the row a keyword
  would fix.
- **A contested document.** If a file satisfies one row's required keywords
  but fails that row's other rules — last year's W-2, say — it is not filed
  anywhere, even if some other row would accept it. It looks like a W-2, so
  it must not be filed as a prior-year return; a person gets it, with the
  failed rule quoted. A signed return of the wrong year is contested even
  when another row matched it strongly (decision 141): this year's 1065
  carries its K-1s, and it is never the K-1s.
- **A document whose issuer the list does not know.** A person holding
  several Schedule K-1s gets one row per issuing entity (decision 93, the
  owner's), each an ordinary row carrying the entity's name in Required
  Keywords. The two tiers above already settle which row wins — an issuer
  row that finds its name is required-keyword-strong and the generic K-1
  row, having no required keywords, never can be, so the issuer row takes
  it without a rule of its own. What needed a rule is the K-1 from an
  issuer nobody listed: the generic row accepts it, no issuer row does,
  and filing it there would put two entities' K-1s in one folder. It
  parks with ``reasons.ISSUER_NOT_NAMED``, the issuer rows named, for a
  person to file or to add the missing row.

**One document, several forms.** A page can be two documents: a client's
scanner takes a W-2 and a 1099-INT in one pass, and the sheet that comes
out prints both forms' own names. The owner's rule (2026-09-18) is that
such a page files a copy under each form it covers, and the exception is
deliberately narrow (:func:`_multi_form`): each form must name *itself*
the way decision 85 means it - its number heading a line, with or without
its printed title, and its year after
(:func:`tracker.content_check.self_named_forms`) - two families of them
must do it, the menu rules must not fire, and the forms must sort one to
a request and one request to a form. A cover letter or a checklist that
merely lists several forms is a menu and parks, exactly as it did before.
Where the bijection fails - a form no request asks for, two requests
wanting one form, a request accepted on a phrase that names no form - the
whole page parks for a person with the rows as its shortlist. This is the
one place a document is filed under more than one request, and standing
rule 3 says so in those words.

When a file is not routed, the reason says why in the most useful terms
available: a document whose content fits a request but which that request
refused (too small, wrong type, unreadable) is reported as ``CONTESTED_PREFIX``
plus the request and its refusal; a file whose keywords all matched one
request and whose *year* alone did not is reported the same way, with that
request named, because "matched no request" is a lie about last year's
childcare statement; and a file every request refused for the same reason
carries that reason — ``UNMATCHED`` alone is the last resort, not the
default. A lead of that kind never pre-empts a filing the way a
required-keyword match does: it is read only when the file would otherwise
be parked with no candidate at all.

**A near miss is a suggestion** (decision 140). A read document that
matched nothing, and whose page still shows a row's own form number - in
the title, or as the form dominating the first page beside another of
the row's own keywords - parks with
``reasons.SHOWS_ITS_FORM_NUMBER`` and that row's evidence, so the card
offers it and the reminder holds rather than asking the client for what
they sent. A real W-2 whose OCR reading lost one of the row's three
required phrases is the case. Where the page shows no row's form number,
the file's name is the last hint, as it is for a scan nothing could read,
said in a sentence of its own (``reasons.NAME_POINTS_AT``) that holds the
same way. The rows are never candidates: the required phrases were not loosened,
because every looser rule tried filed the W-3 family and the W-2c as
W-2s, and a suggestion is not evidence to file on.

A decision also keeps *why* it was reached. ``Routing.evidence`` names the
tier the decision rested on - ``EVIDENCE_CONTENT`` or nothing, since no
decision rests on a name any more; ``Routing.evidence_record`` carries, per
candidate, the keywords that matched and where in the document they were
said (:class:`tracker.content_check.Evidence`), a name's keywords as the
file's own title, and a tier-2 refusal as that Reason's code. A *blocked* file -
one whose content fits a request and whose file the same request's tier-2
rules then refused - keeps both, because the refusal alone says which rule
said no and never which request the document looked like, and that is the
half a person needs. It decides nothing - every verdict above is reached
exactly as it was before there was a record - and it is what the index's
Evidence column, and the person working the review queue, then read.

**The router knows no person** (decision 128). Whose document this is is a
different question from which request it answers, and it is asked
elsewhere: the household pass checks the name on the page against the
return's own people list after the request lists have accepted a document
and before the exactly-one rule (:mod:`tracker.names`,
:func:`tracker.filer.file_household_drops`). Nothing here reads a name, and
a request row's ``named`` mark is not consulted here either - it says what
the *pass* does with an absent name, not whether this row accepts the file.
What the router gained is the ``reading`` argument: the pass reads each
document once and routes it against every return the drop may feed, so a
two-return household costs one reading rather than two.

The decision itself - :class:`tracker.records.Routing` - lives in
:mod:`tracker.records` since decision 100: the decision is a record, and this
module is the deciding. It is re-exported here for one release.

Routing is read-only. Moving, renaming and indexing happen in
:mod:`tracker.filer`, which uses the decisions made here. The verdicts the
router reaches on the way are left in the engagement's verdict cache - in
the store since decision 107 - keyed by the file's content, so the scan
that follows finds them under the working copy's new name instead of
reading the document a second time.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from tracker import reasons

# MULTI_FORM_FAMILIES moved to tracker/content_check.py with decision 107
# (the scanner's miss path reads through the same rule); re-exported here
# for one release so `from tracker.router import MULTI_FORM_FAMILIES` still
# resolves to the same object.
from tracker.content_check import (
    BROKER_FORM,
    MULTI_FORM_FAMILIES,  # noqa: F401
    OPEN_TEST_FINGERPRINT,
    ContentCache,
    ContentResult,
    Extraction,
    any_keyword_matched,
    carries_a_1099b_section,
    contains_keyword,
    evaluate_rules,
    extract_bounded,
    form_key,
    own_forms,
    rules_fingerprint,
    says,
    self_named_forms,
)
from tracker.manifest import Override, RequestItem, asks_for_a_return, has_routing_rules, narrowing_rows

# The routing decision is a record and lives in tracker/records.py
# (decision 100); this module is the deciding. Routing and EVIDENCE_CONTENT
# are re-exported from here, so every `from tracker.router import Routing`
# still resolves to the same class; kept for one release; import from
# tracker.records.
from tracker.records import (
    EVIDENCE_CONTENT,
    RULE_ANY,
    RULE_FILENAME,
    RULE_REFUSED,
    RULE_REQUIRED,
    WHERE_FIRST_PAGE,
    WHERE_TITLE,
    Answer,
    Evidence,
    Routing,
    format_evidence,
)
from tracker.validators import (
    TEXT_READ_CAP_MB,
    PdfVerdictCache,
    check_file,
    extension_of,
    google_stub_reason,
    is_cloud_placeholder,
    is_ignored,
    too_large_reason,
)

#: Why a file was not routed. Stored verbatim in the index's Reason column.
UNMATCHED = "matched no request"
AMBIGUOUS = "matched more than one request"
#: OCR text matched a request's looser keywords only; not enough to file on.
OCR_ONLY = "matched only by OCR text"
PENDING = reasons.PENDING_SYNC.format()
#: No word of the document could be read, so nothing but its name is left
#: and a name files nothing. Worded once, in :mod:`tracker.reasons`.
UNREADABLE = reasons.NO_READABLE_TEXT.format()
#: Every request refused the file type: said once, checked by tests by name.
NO_REQUEST_ACCEPTS = "no request accepts .{extension} files"
#: The list asks for this document one row per issuer and the document
#: names none of them. Worded once, in :mod:`tracker.reasons`.
ISSUER_NOT_NAMED = reasons.ISSUER_NOT_NAMED
#: One page, several forms (decision 94): what the index says when it files
#: a copy under each, and what it says when the forms will not sort one to
#: a request. Both worded once, in :mod:`tracker.reasons`.
SEVERAL_FORMS = reasons.NAMES_SEVERAL_FORMS
SEVERAL_FORMS_UNSORTED = reasons.SEVERAL_FORMS_UNSORTED
#: A read document that matched no request but shows a row's own form
#: number (decision 140). Worded once, in :mod:`tracker.reasons`.
SHOWS_ITS_FORM_NUMBER = reasons.SHOWS_ITS_FORM_NUMBER
#: The same near miss where only the file's name points at a row.
NAME_POINTS_AT = reasons.NAME_POINTS_AT
#: A broker's consolidated 1099 filed whole (decision 146), and the other
#: asked requests it answers without a copy. Worded once, in
#: :mod:`tracker.reasons`.
FILED_WHOLE = reasons.FILED_WHOLE
ALSO_ANSWERS = reasons.ALSO_ANSWERS

_WORD_SPLIT = re.compile(r"[^a-z0-9]+")
#: What a file name uses between words, read as spaces; a hyphen stays,
#: because "1098-T.pdf" names the form it names.
_SEPARATORS = re.compile(r"[^a-z0-9-]+")


def _filename_evidence(path: Path, item: RequestItem) -> tuple[Evidence, ...]:
    """Every keyword from ``item`` that appears in ``path``'s own name.

    **Nothing is filed on this.** It is what a person is handed when the
    document itself could not be read: "A01 - the file name says W-2", at
    the weakest tier :mod:`tracker.review` ranks, beside a document they
    then open. The client chose that name and the form did not, so it can
    start a reader off and it can never end the matter.

    The same whole-token rule the content check uses (``contains_keyword``),
    over the name with its separators (``_``, ``.``) read as spaces: so
    ``1098`` matches ``Form 1098 Mortgage.pdf`` and ``smith_1098.pdf``, but
    neither ``ledger-10983.pdf`` nor ``1098-T.pdf`` - the tuition form is
    not the mortgage form, whichever side of the hyphen is read.

    A file name is all title (``content_check.TITLE_CHARS``), and it has no
    pages, so that is what the evidence says.
    """
    # Clients write "W2" for "W-2" and "1099INT" for "1099-INT": the keyword
    # pattern already reads a dash or a space as optional, and the same
    # rule keeps "Form1040-ES.pdf" from being last year's Form 1040.
    name = _SEPARATORS.sub(" ", path.stem.lower())
    return tuple(
        Evidence(RULE_FILENAME, keyword, WHERE_TITLE)
        for keyword in (*item.required_keywords, *item.any_keywords)
        if contains_keyword(name, keyword)
    )


def _refusal_evidence(reason: str) -> tuple[Evidence, ...]:
    """A tier-2 refusal as evidence: the Reason's code, not its sentence.

    The sentence is written for a person and may be reworded; the code is
    the cause's one name (:mod:`tracker.reasons`), which is what a later
    reader compares. A refusal nothing in ALL recognises leaves no
    evidence rather than a made-up code.
    """
    found = reasons.find(reason)
    return (Evidence(RULE_REFUSED, found.code),) if found is not None else ()


def _recorded_for(
    record: dict[str, tuple[Evidence, ...]], identifiers
) -> dict[str, tuple[Evidence, ...]]:
    """The evidence record cut down to the identifiers a decision names.

    Every row the router considered leaves something behind - a refusal, a
    keyword that matched, a keyword that did not - and writing all of it
    into one index cell would bury the two lines a person needs. What is
    kept is what the decision itself points at.
    """
    return {identifier: record[identifier] for identifier in identifiers if record.get(identifier)}


def _shows_its_form_number(evidence: tuple[Evidence, ...]) -> bool:
    """Whether a row's evidence says the page shows that row's own form number.

    Decision 140. A row's own form number is a keyword of the row that is a
    form's number (``content_check.form_key``, the one normalisation, which
    reads ``W-2``, ``1098`` and ``1099-INT`` as forms and a bare ``1099``
    only as its family). It is *shown* when the evidence says it was said
    in the title zone, or when it was said on the first page - where a form
    number counts only as the page's dominant form - **and** at least one
    more of the row's own keywords was found too (the designer's ruling on
    the review). Dominance alone is not enough: an OCR reading is one
    "page", and a K-1 whose partner line was misread still makes W-2 its
    dominant form on two "W-2 wages" lines, which would suggest A01 and
    hold the whole letter. This reads only what the verdict already
    recorded - nothing is read off the page again - and it decides nothing
    about filing: it is the question of whether a person should be handed
    this row to read the document against.
    """
    keywords = [found for found in evidence if found.rule in (RULE_REQUIRED, RULE_ANY)]
    for found in keywords:
        if form_key(found.term) is None:
            continue
        if found.where == WHERE_TITLE:
            return True
        if found.where == WHERE_FIRST_PAGE and any(other.term != found.term for other in keywords):
            return True
    return False


def _near_miss(
    path: Path, allowed: list[RequestItem], record: dict[str, tuple[Evidence, ...]], hint: str,
) -> Routing | None:
    """Decision 140: a read document that matched no request, and still
    points at one.

    The rows whose tier-2 rules let the file through and whose verdict
    recorded their own form number shown on the page (:func:`_shows_its_form_number`)
    - a real W-2 whose OCR reading cut "employee's social security number"
    at the box rule still shows "W-2" dominating its first page. Where the
    page shows no row's form number, the file's own name is the last hint
    (:func:`_filename_evidence`, the same evidence an unreadable scan
    keeps), added beside whatever the row's verdict did record.

    **Never a candidate, and never a filing.** A row here failed its own
    rules - that is how the file got this far - and a suggestion is not
    evidence to file on (decision 92). The rows travel as the evidence
    record, so the review card offers them and the reminder's hold reads
    them (``reasons.SHOWS_ITS_FORM_NUMBER`` holds, decision 117's hold);
    ``candidates`` stays empty. None when nothing points anywhere, and the
    file parks as plain "matched no request", as it always did.

    The two paths are said apart: ``reasons.SHOWS_ITS_FORM_NUMBER`` when
    the page showed the number, ``reasons.NAME_POINTS_AT`` when only the
    name did, because a reason must not claim the page said what only the
    client's name for the file said. Both hold the letter the same way.
    """
    because = SHOWS_ITS_FORM_NUMBER
    shown = [item.identifier for item in allowed
             if _shows_its_form_number(record.get(item.identifier, ()))]
    if not shown:
        because = NAME_POINTS_AT
        for item in allowed:
            if said_by_the_name := _filename_evidence(path, item):
                record[item.identifier] = record.get(item.identifier, ()) + said_by_the_name
                shown.append(item.identifier)
    if not shown:
        return None
    return Routing(
        path=path,
        identifier=None,
        reason=because.format(listed=", ".join(shown)) + hint,
        evidence_record=_recorded_for(record, shown),
    )


def _required_matched(text: str, item: RequestItem) -> bool:
    """True if every one of ``item``'s required keywords appears in ``text``.

    Required keywords are the accountant's strongest assertion about what a
    document *is* ("a W-2 says W-2"), which is why they both outrank
    ``any_keywords`` when choosing between requests and, when they match a
    request whose other rules then fail, stop the file being filed elsewhere.
    """
    if not item.required_keywords:
        return False
    return all(says(text, k) for k in item.required_keywords)


def _considers(item: RequestItem) -> bool:
    """Could this request accept any file at all?

    Not Applicable rows want nothing, and a row with no content rule has no
    way to recognise a document — it never auto-routes, by design.
    """
    return item.manual_override != Override.NOT_APPLICABLE and has_routing_rules(item)


#: How a contested file's reason starts. The candidates travel as data
#: (Routing.candidates, then the index's Candidates column); nothing parses
#: this sentence to get them back.
CONTESTED_PREFIX = "looks like"


def _contested(
    path: Path, near: list[tuple[str, str]],
    record: dict[str, tuple[Evidence, ...]] | None = None,
) -> Routing:
    listed = "; ".join(f"{ident} ({why})" for ident, why in near)
    candidates = tuple(ident for ident, _ in near)
    return Routing(
        path=path,
        identifier=None,
        reason=f"{CONTESTED_PREFIX} {listed} - a person should confirm",
        candidates=candidates,
        evidence=EVIDENCE_CONTENT,
        evidence_record=_recorded_for(record or {}, candidates),
    )


def _explained_by(evidence: tuple[Evidence, ...], named: set[str]) -> tuple[str, ...]:
    """Which of the page's self-named forms a row was accepted because of.

    A row is accepted *because of* a form when one of the keywords that
    matched it - a required keyword or an any-keyword, never the Period's
    year check, which is a check and not evidence (decision 40) - is that
    form's number (``content_check.form_key``, the one normalisation).
    A row whose whole case rests on a phrase ("statement period",
    "brokerage") names no form and comes back empty, which is what stops a
    page being split on a row that only happened to be nearby.
    """
    return tuple(dict.fromkeys(
        key for found in evidence
        if found.rule in (RULE_REQUIRED, RULE_ANY)
        and (key := form_key(found.term)) in named
    ))


def _sections(evidence: tuple[Evidence, ...]) -> tuple[str, ...]:
    """The form sections a row accepted a statement because of: each
    required or any-keyword that matched and is a form number, as the row
    spells it (``1099-int``), first match first. A row accepted on a phrase
    alone has none. The row's own words, never the document's."""
    return tuple(dict.fromkeys(
        found.term for found in evidence
        if found.rule in (RULE_REQUIRED, RULE_ANY) and form_key(found.term) is not None
    ))


def _filed_whole(
    path: Path, filed: str, accepted: list[str], items: list[RequestItem],
    record: dict[str, tuple[Evidence, ...]],
) -> Routing:
    """Decision 146: a broker's consolidated 1099 files whole under
    ``filed``, the one row among ``accepted`` that its 1099-B section was
    accepted by, and answers every other *asked* row that accepted it.

    The other rows ran their own rules over the same document and passed -
    the same acceptance a loose 1099-INT or 1099-MISC would have to meet -
    so each is answered by the section it was accepted because of
    (:func:`_sections`), with no copy made: one file, one folder. A row
    nobody asked for (decision 142) is not answered, because nobody is
    waiting on it; it still sees the statement as one of the candidates.
    The answers travel on the routing, and from there on the filed row's
    Also Answers cell, which the status, the letter and the client's
    received list all read.
    """
    asked = {item.identifier for item in items if item.asked}
    answers: tuple[Answer, ...] = tuple(
        (ident, _sections(record.get(ident, ())))
        for ident in accepted if ident != filed and ident in asked
    )
    reason = FILED_WHOLE.format(filed=filed)
    if answers:
        reason = f"{reason}; {ALSO_ANSWERS.format(listed=', '.join(i for i, _ in answers))}"
    candidates = (filed, *(ident for ident in accepted if ident != filed))
    return Routing(
        path=path,
        identifier=filed,
        reason=reason,
        candidates=candidates,
        evidence=EVIDENCE_CONTENT,
        evidence_record=_recorded_for(record, candidates),
        answers=answers,
    )


def _multi_form(
    path: Path, words: str, allowed: list[RequestItem], named: tuple[str, ...],
    keep: Callable[[RequestItem, ContentResult], None] | None = None,
) -> Routing | None:
    """Decision 94, the owner's: one page carrying several forms.

    ``named`` is every form the page prints its own name on
    (:func:`tracker.content_check.self_named_forms`), and this is called
    only when two or more *families* of them do. The page is read a second
    time with all of them counted as the document's own - the ordinary
    reading calls at most one form a page's own, so the second form's
    request would otherwise never accept the page at all - and each row
    that accepts is tied back to the form it was accepted because of
    (:func:`_explained_by`).

    ``keep`` is the caller's way of remembering a verdict for the scan
    that follows. It is called once per row a copy is filed under, with
    the second reading's verdict, *after* the ordinary reading has left
    its own: the ordinary reading called the page one form's and refused
    the other request, and a scan that found that refusal under the
    second copy would fail the copy and ask the client for a form they
    already sent. The verdict the router files on is the one the scan
    must find. Rows that park keep nothing new - the ordinary verdicts
    stand for a page that is going to a person anyway.

    A copy is filed under each request **only on a bijection**: every
    self-named form accepted by exactly one row, and every accepting row
    explained by exactly one self-named form. Anything short of it parks
    with the contested sentence and the rows as the shortlist - a form no
    request asks for parks the whole page, because filing the half we can
    place would put the other half somewhere nobody will look for it, and
    two rows wanting one of the forms is the ordinary contest a person
    settles. Returns None where no row accepted at all, so the ordinary
    reading keeps its own honest reason for parking.

    OCR text is read here like any other: this rests on a form printing
    its number at the head of a line with its year beside it, which a
    misread word does not manufacture, and on a bijection far stricter
    than the any-keyword tier ``OCR_ONLY`` exists to distrust.
    """
    named_set = set(named)
    record: dict[str, tuple[Evidence, ...]] = {}
    explained: dict[str, tuple[str, ...]] = {}
    verdicts: dict[str, tuple[RequestItem, ContentResult]] = {}
    for item in allowed:
        verdict = evaluate_rules(words, item, named_set)
        if not verdict.ok:
            continue
        record[item.identifier] = verdict.evidence
        explained[item.identifier] = _explained_by(verdict.evidence, named_set)
        verdicts[item.identifier] = (item, verdict)
    if not explained:
        return None
    rows_for: dict[str, list[str]] = {form: [] for form in named}
    for identifier, forms in explained.items():
        for form in forms:
            rows_for[form].append(identifier)

    shortlist = tuple(explained)
    if (all(len(rows) == 1 for rows in rows_for.values())
            and all(len(forms) == 1 for forms in explained.values())):
        filed = [rows_for[form][0] for form in named]
        if keep is not None:
            for identifier in filed:
                keep(*verdicts[identifier])
        return Routing(
            path=path,
            identifier=filed[0],
            also=tuple(filed[1:]),
            reason=SEVERAL_FORMS.format(n=len(named), listed=", ".join(filed)),
            candidates=tuple(filed),
            evidence=EVIDENCE_CONTENT,
            evidence_record=_recorded_for(record, filed),
        )
    return Routing(
        path=path,
        identifier=None,
        reason=(f"{CONTESTED_PREFIX} {', '.join(shortlist)} - "
                f"{SEVERAL_FORMS_UNSORTED.format(n=len(named))}; a person should confirm"),
        candidates=shortlist,
        evidence=EVIDENCE_CONTENT,
        evidence_record=_recorded_for(record, shortlist),
    )


def read_once(path: Path) -> Extraction:
    """The document's words, the way the scanner will read them.

    The text layer first; a scan with none is read by OCR, if OCR is
    installed. The file's own name used to excuse that reading - a scan
    whose name said which request it was routed on the name, cheaply -
    and since decision 92 it does not: nothing is filed on a name, so OCR
    is the only thing that can still file a scan, and the scan whose name
    says "W-2" is exactly the one whose content has to be read. It is the
    same reading the scanner makes of the same bytes later, so the two
    never disagree about what the file says.

    Public since decision 128: a household's pass reads each drop **once**
    and routes it against every return the drop may feed
    (:func:`tracker.filer.file_household_drops`), so a two-return household
    does not OCR every photo twice. The reading is handed back into
    :func:`route_file` as ``reading``.

    Read in a process the pass can stop (decision 150,
    :func:`tracker.content_check.extract_bounded`): the safety stop bounds
    the whole reading - text layer, render and OCR - and a reader that
    crashes parks this file rather than ending the pass.
    """
    return extract_bounded(path)


def route_file(
    path: Path,
    items: list[RequestItem],
    *,
    reading: Extraction | None = None,
    digest: str | None = None,
    cache: ContentCache | None = None,
    pdf_cache: PdfVerdictCache | None = None,
) -> Routing:
    """Decide which request ``path`` belongs to.

    ``reading`` may be supplied by a caller that has already read the
    document (:func:`read_once`); otherwise it is read here, once, and
    reused across every request. It is the whole :class:`Extraction` and
    not the text alone, because ``from_ocr`` is part of what the words are
    worth: decision 50 reads OCR's words more strictly than a text layer's,
    and a caller handing over a bare string would quietly promote an OCR
    reading to a text layer's standing. With a ``cache`` (and the file's
    ``digest``, if the caller has it), the per-request verdicts are kept
    for the scan that follows. ``pdf_cache`` spares parsing the same PDF
    once per manifest row.
    """
    if is_cloud_placeholder(path):
        return Routing(path=path, identifier=None, reason=PENDING, pending=True)

    # A Google-native stub can never be filed, and the client can fix it —
    # say so instead of the generic UNMATCHED.
    if stub := google_stub_reason(path):
        return Routing(path=path, identifier=None, reason=stub)

    # Past the size ceiling the file is never read (decision 137, M5): it
    # parks for a person with the one sentence that says why, and nothing
    # about its name or its type is weighed.
    if too_large := too_large_reason(path):
        return Routing(path=path, identifier=None, reason=too_large)

    reading = read_once(path) if reading is None else reading
    # A picture too large even for Pillow to decode, a reading the safety
    # stop abandoned (decision 137, B1), a reading whose process ended
    # without an answer and one whose reader could not start at all
    # (decision 150) park on their one sentence, as a file past the ceiling
    # does. The open test was made in the same child, so it stopped with it.
    # A pass never records the last of these: tracker.filer leaves a drop
    # whose reader could not start for the next pass (the re-review's ruling).
    if reading.text is None and (reasons.TOO_LARGE.matches(reading.reason)
                                 or reasons.READING_STOPPED.matches(reading.reason)
                                 or reasons.READING_CRASHED.matches(reading.reason)
                                 or reasons.READER_UNAVAILABLE.matches(reading.reason)):
        return Routing(path=path, identifier=None, reason=reading.reason, seconds=reading.seconds)
    # How long the reading took rides back with the decision (decision
    # 127), so the pass can name its slowest documents. It changes no
    # decision and cuts no reading short.
    routing = replace(
        _decide(path, items, reading, digest=digest, cache=cache,
                pdf_cache=pdf_cache or PdfVerdictCache()),
        seconds=reading.seconds,
    )
    if reading.cut and routing.identifier is None and routing.reason:
        # Parked on the first part of a long text file: the person opening
        # it is told the rest was never read (decision 137).
        routing = replace(routing, reason=f"{routing.reason}; "
                                          f"{reasons.TEXT_CUT.format(limit=TEXT_READ_CAP_MB)}")
    return routing


def _decide(
    path: Path,
    items: list[RequestItem],
    reading: Extraction,
    *,
    digest: str | None,
    cache: ContentCache | None,
    pdf_cache: PdfVerdictCache,
) -> Routing:
    """Which request a document belongs to, once it has been read.

    :func:`route_file`'s whole decision; split off it only so that every
    way out of the decision carries the reading's seconds without each
    ``return`` having to remember to.
    """
    # A text layer below _MIN_TEXT_CHARS (a scanned form's page breaks, a
    # "Page 1 of 2" stamp) is no reading at all, and neither is a scan OCR
    # could not rescue: with no words there is no candidate, and the file
    # parks for a person (UNREADABLE) rather than being filed on its name.
    words = "" if reading.needs_ocr else (reading.text or "")
    # The scanner's verdict is the verdict on the *whole* reading; a file
    # nothing could be read out of was never read, so nothing is remembered.
    remember = cache is not None and reading.text is not None and not reading.needs_ocr
    if remember and digest is None:
        digest = cache.digest_of(path)

    def keep(item: RequestItem, verdict: ContentResult) -> None:
        if remember and digest:
            cache.put_by_digest(digest, rules_fingerprint(item), verdict)

    # Tier 2's open test was made in the reading's child (decision 150):
    # its verdict is what every row's tier 2 is told, and it is kept by the
    # file's fingerprint so the scan of the working copy does not open the
    # file either. A reading handed in without one - a tool's - is opened
    # here, as before. The HEIC decoder's absence is the machine's, not kept.
    open_test = None
    if reading.opened is not None:
        opened = reading.opened
        open_test = lambda _path: opened  # noqa: E731
        if cache is not None and not reasons.HEIC_NOT_SUPPORTED.matches(opened):
            open_digest = digest or cache.digest_of(path)
            if open_digest:
                cache.put_by_digest(open_digest, OPEN_TEST_FINGERPRINT,
                                    ContentResult(ok=not opened, reason=opened))

    # Which forms the page counts as its own is content_check's one reading,
    # own_forms() (decision 107): the ordinary reading here, the split below
    # and the scanner's miss path all read through it, so a page that prints
    # two forms' own names is those two documents and never files on a third
    # form it merely mentions - decision 94's rule, by construction - and
    # every verdict kept here is one a rebuilt store reaches again.
    own = own_forms(words) if words else None

    def verdict_for(item: RequestItem):
        verdict = evaluate_rules(words, item, own)
        keep(item, verdict)
        return verdict

    strong: list[str] = []      # required keywords matched and every rule passed
    medium: list[str] = []      # passed on any_keywords / date alone
    ocr_only: list[str] = []    # passed on any_keywords, but the text is OCR's word for it
    near: list[tuple[str, str]] = []   # looks like this request but fails a rule
    #: A signed return of the wrong year: a return row's required keywords
    #: matched and only its period failed (decision 141). Parks even when
    #: another row matched strongly.
    signed: list[tuple[str, str]] = []
    leads: list[tuple[str, str]] = []  # its keywords matched and only the year did not
    #: Nothing could be read, and the file's *name* carries this row's
    #: keywords. Never filed on (decision 92) and never a candidate: it is
    #: the shortlist a person gets beside a document they must open - and,
    #: since decision 117, the shortlist that decides whether a parked file
    #: holds a request's reminder. A file the rules refused at tier 2 and
    #: could not read a word of (a locked PDF, an empty upload) is asked
    #: the same question as an unreadable scan, and lands here too.
    named: list[str] = []
    blocked: list[tuple[str, str]] = []  # content fits, but tier 2 refused the file
    refusals: list[str] = []    # every tier-2 reason, for an honest "why not"
    #: Why, per row: the keywords that matched and where, or the refusal.
    #: Kept for every row considered and cut down at the end to the rows
    #: the decision names (``_recorded_for``).
    record: dict[str, tuple[Evidence, ...]] = {}
    #: The rows this file got as far as tier 3 on: considered, and their
    #: own tier-2 rules did not refuse the file. The only rows a page that
    #: names several forms could be split across (decision 94).
    allowed: list[RequestItem] = []

    for item in items:
        if not _considers(item):
            continue
        tier2 = check_file(path, item, pdf_cache=pdf_cache, open_test=open_test)
        if not tier2.ok:
            refusals.append(tier2.reason)
            refused = _refusal_evidence(tier2.reason)
            record[item.identifier] = refused
            # The verdict was already read to know whether this is a
            # blocked file; keeping its evidence beside the refusal costs
            # nothing and is the only thing that says which request the
            # document looked like. Nothing is filed differently for it.
            if words and (verdict := verdict_for(item)).ok:
                blocked.append((item.identifier, tier2.reason))
                record[item.identifier] = verdict.evidence + refused
            elif not words and (said_by_the_name := _filename_evidence(path, item)):
                # Refused, and not a word of it could be read - a locked
                # PDF, an empty upload. The only thing left is the name
                # the client gave it, exactly as for a scan with no text
                # layer (decision 92): never a candidate and never a
                # filing, but the line that tells the person opening this
                # document which request it was probably meant for - and,
                # since decision 117, the thing that holds that request's
                # reminder instead of asking the client for a document
                # they know they sent.
                record[item.identifier] = refused + said_by_the_name
                named.append(item.identifier)
            continue
        allowed.append(item)
        if words:
            verdict = verdict_for(item)
            record[item.identifier] = verdict.evidence
            if verdict.ok:
                if _required_matched(words, item):
                    strong.append(item.identifier)
                elif reading.from_ocr:
                    ocr_only.append(item.identifier)
                else:
                    medium.append(item.identifier)
            elif _required_matched(words, item):
                near.append((item.identifier, verdict.reason))
                if asks_for_a_return(item) and reasons.WRONG_PERIOD.matches(verdict.reason):
                    signed.append((item.identifier, verdict.reason))
            elif reasons.WRONG_PERIOD.matches(verdict.reason) and any_keyword_matched(words, item):
                # Every keyword this row asks for matched and only its year
                # did not. That is no filing decision - the year is a check,
                # never evidence (decision 40) - but it is the lead a person
                # needs, and it is all this file is going to give them.
                leads.append((item.identifier, verdict.reason))
        elif said_by_the_name := _filename_evidence(path, item):
            record[item.identifier] = said_by_the_name
            named.append(item.identifier)

    # A signed return of another year (decision 141, the designer's ruling
    # on the review): it met a return row's required keywords - the form's
    # own title and the jurat - and failed only that row's period. This
    # year's 1065 carries its partners' K-1s and a 1040 may have a W-2G
    # stapled to it, so the K-1 row or the W-2G row can match it strongly,
    # and filing it there would put a signed return among the K-1s. It
    # parks, whatever else matched. Return rows only: they are the rows
    # whose document contains other forms.
    if signed:
        return _contested(path, signed, record)

    # A document that announces itself as one request's paperwork but fails
    # that request's other rules is contested — never file it somewhere else.
    if near and not strong:
        return _contested(path, near, record)

    # One page, two forms (decision 94, the owner's): a page on which two
    # or more form families each print their own name - the way a real
    # W-2 and a real 1099-INT each print their number and their year - is
    # two documents, and each request that asked for one of them gets a
    # copy. The menu rules come first and are untouched: a page that
    # *lists* forms names none of them (``self_named_forms``), so a
    # checklist and a cover letter park exactly as they did. This is read
    # after the contested check and before anything is filed, because a
    # page whose forms will not sort one to a request parks whether or not
    # one of them would have filed on its own - filing the half we can
    # place would put the other half where nobody will look for it.
    # The forms are taken in first-mention order (self_named_forms), because
    # which request the page files under first is part of the decision.
    if own is not None:
        # Its own name, not ``named``: that list is the rows a file's name
        # pointed at, and decision 140 reads it again at the last exit.
        self_named = self_named_forms(words)
        if split := _multi_form(path, words, allowed, self_named, keep):
            return split

    # The list asks for this document one row per issuer (decision 93): the
    # broad row accepted it on its looser words, every issuer row wanted a
    # name this document does not say, and nothing required-keyword-strong
    # claimed it. It parks. Filing it on the broad row would put two
    # entities' K-1s in one folder, which is what the issuer rows exist to
    # stop; taking whichever issuer row is left over would be guessing by
    # elimination, and a document is filed only when exactly one request
    # accepts it. The shortlist leads with the row that did accept it and
    # names the issuer rows after it, so a person sees both what the
    # document is and which issuers the list already knows.
    if medium and not strong:
        narrowed = narrowing_rows(i for i in items if _considers(i))
        issuer_rows = tuple(dict.fromkeys(
            row for ident in medium for row in narrowed.get(ident, ())
        ))
        if issuer_rows:
            shortlist = (*medium, *issuer_rows)
            return Routing(
                path=path,
                identifier=None,
                reason=ISSUER_NOT_NAMED.format(listed=", ".join(issuer_rows)),
                candidates=shortlist,
                evidence=EVIDENCE_CONTENT,
                evidence_record=_recorded_for(record, shortlist),
            )

    # A broker's consolidated 1099 (decision 146, the owner's go-live item
    # 13): it carries a 1099-B section beside its 1099-INT, 1099-DIV and
    # 1099-MISC ones, so the rows asking for each of them all accept it on
    # their looser words and it used to park as theirs to settle. It is the
    # brokerage year-end statement, and it files whole under the one row
    # that accepted it *because of* the 1099-B (``_explained_by``, keyed on
    # the evidence and never on an identifier, so it holds on every
    # catalog and on a preparer's own rows). Two such rows, or none, and it
    # parks exactly as before: nothing is guessed. Never on OCR's word
    # (``medium`` is text-layer only; decision 50), never over a row
    # matched on its required keywords, and after the issuer rule, so a
    # page that rule parks stays parked.
    if len(medium) > 1 and not strong and carries_a_1099b_section(words):
        broker = [ident for ident in medium
                  if _explained_by(record.get(ident, ()), {BROKER_FORM})]
        if len(broker) == 1:
            return _filed_whole(path, broker[0], medium, items, record)

    for hits, strength, how in (
        (strong, EVIDENCE_CONTENT, "content matched this request's required keywords"),
        (medium, EVIDENCE_CONTENT, "content matched this request's keywords"),
    ):
        if len(hits) == 1:
            return Routing(
                path=path,
                identifier=hits[0],
                reason=how,
                candidates=tuple(hits),
                evidence=strength,
                evidence_record=_recorded_for(record, hits),
            )
        if len(hits) > 1:
            return Routing(
                path=path,
                identifier=None,
                reason=f"{AMBIGUOUS} ({', '.join(hits)}); a person should choose",
                candidates=tuple(hits),
                evidence=strength,
                evidence_record=_recorded_for(record, hits),
            )

    # OCR's reading of the looser keywords is a lead for a person, not a
    # filing decision: a misread word is how a document lands under the
    # wrong request.
    if ocr_only:
        return Routing(
            path=path,
            identifier=None,
            reason=f"{OCR_ONLY} ({', '.join(ocr_only)}); a person should confirm",
            candidates=tuple(ocr_only),
            evidence=EVIDENCE_CONTENT,
            evidence_record=_recorded_for(record, ocr_only),
        )

    # The content says which request this is, but the file itself was
    # refused (too small, wrong type, unreadable PDF). Say that, so the
    # person reviewing it - and the client, via the reminder - hears the
    # real reason instead of UNMATCHED.
    if blocked:
        return _contested(path, blocked, record)

    # Nothing matched and every request refused the file for the same
    # reason: that reason is the story (a corrupt PDF, a locked PDF, a
    # file type nobody accepts), not the keyword rules.
    if refusals and len(refusals) == sum(1 for i in items if _considers(i)):
        if len(set(refusals)) == 1:
            # What its name said rides with it, for the person and for the
            # reminder's hold (decision 117). Still no candidate: nothing
            # is filed on a name, and the reason is the refusal's, not a
            # guess at which request this was.
            return Routing(path=path, identifier=None, reason=f"{UNMATCHED}; {refusals[0]}",
                           evidence_record=_recorded_for(record, named))
        if all(reasons.EXTENSION_NOT_ALLOWED.matches(r) for r in refusals):
            ext = extension_of(path) or "(none)"
            return Routing(
                path=path,
                identifier=None,
                reason=f"{UNMATCHED}; {NO_REQUEST_ACCEPTS.format(extension=ext)}",
            )

    if reading.error:
        return Routing(
            path=path,
            identifier=None,
            reason=f"{UNMATCHED}; could not read it ({reading.error})",
        )

    # No word of the document could be read - a scan with no text layer and
    # no OCR on this machine, an image-only PDF, a sheet with nothing in
    # it. The owner's rule (2026-09-18): a document nobody can read is
    # filed by nobody. So no row is a candidate, nothing is filed, and what
    # the file's *name* pointed at travels with the parked row as evidence
    # for the person who will open the document - a place to start reading,
    # never a decision. "Matched no request" would be a lie here: nothing
    # was matched against anything, and the fix is OCR or a person rather
    # than another keyword.
    if not words:
        return Routing(
            path=path,
            identifier=None,
            reason=UNREADABLE,
            evidence_record=_recorded_for(record, named),
        )

    # Nothing accepted the file, and a row's keywords all matched but its
    # year: say so with the row named, the way a contested file is said.
    # Unlike a required-keyword match, a lead never pre-empts a filing - it
    # is read only when the file was going to be parked with no candidate
    # at all, so the decision is exactly as it was and only the reason and
    # the candidates improve (the thirteenth reading).
    if leads:
        return _contested(path, leads, record)

    rule_less = [i.identifier for i in items if not _considers(i)
                 and i.manual_override != Override.NOT_APPLICABLE]
    hint = ""
    if rule_less:
        hint = (
            f"; add a keyword to {', '.join(rule_less[:3])} in the manifest "
            "to route files like this automatically"
        )
    # Read, matched nothing - and a row's own form number is on the page,
    # or the file's name says a row's word (decision 140). The rows go to
    # the person as a shortlist and hold the letter; nothing is filed.
    if near_miss := _near_miss(path, allowed, record, hint):
        return near_miss
    return Routing(path=path, identifier=None, reason=f"{UNMATCHED}{hint}")


def route_files(paths: list[Path], items: list[RequestItem]) -> list[Routing]:
    """Route many files, skipping OS/sync junk entirely."""
    return [route_file(p, items) for p in paths if not is_ignored(p)]


# ------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.manifest import load_manifest
    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description="Where would these files go, and why? Read-only: routes, moves nothing."
    )
    parser.add_argument("engagement_dir", help="the engagement folder")
    parser.add_argument("files", nargs="+", help="the dropped file(s) to route")
    ns = parser.parse_args()

    manifest_items = load_manifest(Path(ns.engagement_dir))
    for decision in route_files([Path(f) for f in ns.files], manifest_items):
        where = decision.identifier or "Needs Review"
        print(f"{decision.path.name}\n    -> {where}: {decision.reason}")
        if decision.evidence:
            print(f"       evidence: {decision.evidence}")
        if decision.candidates:
            print(f"       candidates: {', '.join(decision.candidates)}")
        if decision.evidence_record:
            print(f"       why: {format_evidence(decision.evidence_record)}")
