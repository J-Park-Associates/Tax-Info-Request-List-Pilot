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
3. **Filename** — a request's keyword appears in the file's name. Used only
   when the file has no readable text, which rescues the common case of a
   scanned PDF with no text layer.

A scan with no text layer and a name that says nothing is read by OCR, if
OCR is installed - the same reading the scanner would make of it later
(:func:`tracker.content_check.extract`), so the two never disagree about
what the file says. But OCR text is read *more strictly* than a text layer:
it routes a file only on a request's **required** keywords. OCR misreads
words, and the looser any-keyword tier is exactly where a misread "1099"
would file a document under the wrong request; those matches go to a
person instead (``OCR_ONLY``).

Two things deliberately do *not* route a file:

- **A matching extension.** A row that accepts ``pdf`` would otherwise
  swallow every PDF in the drop. A request with no keyword rules never
  auto-routes; its files go to review with a note naming the row a keyword
  would fix.
- **A contested document.** If a file satisfies one row's required keywords
  but fails that row's other rules — last year's W-2, say — it is not filed
  anywhere, even if some other row would accept it. It looks like a W-2, so
  it must not be filed as a prior-year return; a person gets it, with the
  failed rule quoted.

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

A decision also keeps *why* it was reached. ``Routing.evidence`` names the
tier the decision rested on; ``Routing.evidence_record`` carries, per
candidate, the keywords that matched and where in the document they were
said (:class:`tracker.content_check.Evidence`), a by-name hit as the file's
own title, and a tier-2 refusal as that Reason's code. A *blocked* file -
one whose content fits a request and whose file the same request's tier-2
rules then refused - keeps both, because the refusal alone says which rule
said no and never which request the document looked like, and that is the
half a person needs. It decides nothing - every verdict above is reached
exactly as it was before there was a record - and it is what the index's
Evidence column, and the person working the review queue, then read.

Routing is read-only. Moving, renaming and indexing happen in
:mod:`tracker.filer`, which uses the decisions made here. The verdicts the
router reaches on the way are left in the engagement's content cache,
keyed by the file's content, so the scan that follows finds them under the
working copy's new name instead of reading the document a second time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from tracker import reasons
from tracker.content_check import (
    RULE_FILENAME,
    RULE_REFUSED,
    WHERE_TITLE,
    ContentCache,
    Evidence,
    Extraction,
    any_keyword_matched,
    contains_keyword,
    evaluate_rules,
    extract,
    extract_by_ocr,
    format_evidence,
    rules_fingerprint,
    says,
)
from tracker.manifest import Override, RequestItem, has_routing_rules
from tracker.validators import (
    PdfVerdictCache,
    check_file,
    extension_of,
    google_stub_reason,
    is_cloud_placeholder,
    is_ignored,
)

#: Why a file was not routed. Stored verbatim in the index's Reason column.
UNMATCHED = "matched no request"
AMBIGUOUS = "matched more than one request"
#: OCR text matched a request's looser keywords only; not enough to file on.
OCR_ONLY = "matched only by OCR text"
#: What a routing decision rested on.
EVIDENCE_CONTENT = "content"
EVIDENCE_FILENAME = "filename"
PENDING = reasons.PENDING_SYNC.format()
#: Every request refused the file type: said once, checked by tests by name.
NO_REQUEST_ACCEPTS = "no request accepts .{extension} files"

_WORD_SPLIT = re.compile(r"[^a-z0-9]+")
#: What a file name uses between words, read as spaces; a hyphen stays,
#: because "1098-T.pdf" names the form it names.
_SEPARATORS = re.compile(r"[^a-z0-9-]+")


@dataclass(frozen=True, slots=True)
class Routing:
    """Where one dropped file belongs, and why."""

    path: Path
    identifier: str | None          # None → needs human review
    reason: str                     # plain English, safe to show a client
    candidates: tuple[str, ...] = ()  # identifiers that accepted the file
    evidence: str = ""              # EVIDENCE_CONTENT | EVIDENCE_FILENAME | ""
    #: What each candidate's evidence actually was, by identifier: the
    #: keywords that matched, where they were said, the tier-2 reason that
    #: refused the file. ``evidence`` above says which *tier* the decision
    #: rested on and nothing more; this says why, and only for the
    #: identifiers the decision names, so the index's cell stays readable.
    evidence_record: dict[str, tuple[Evidence, ...]] = field(default_factory=dict)
    pending: bool = False           # still syncing; leave it where it is

    @property
    def routed(self) -> bool:
        return self.identifier is not None


def _filename_evidence(path: Path, item: RequestItem) -> tuple[Evidence, ...]:
    """Every keyword from ``item`` that appears in ``path``'s own name.

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


def _filename_hit(path: Path, item: RequestItem) -> bool:
    """True if a keyword from ``item`` appears in ``path``'s own name."""
    return bool(_filename_evidence(path, item))


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

    Waived rows want nothing, and a row with no content rule has no way to
    recognise a document — it never auto-routes, by design.
    """
    return item.manual_override != Override.WAIVED and has_routing_rules(item)


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


def _read(path: Path, items: list[RequestItem], text: str | None) -> Extraction:
    """The document's words, the way the scanner will read them.

    The text layer first. A scan whose name already says which request it
    is (``_filename_hit``) is not OCR'd - the name routes it, cheaply and
    exactly as before OCR was part of routing; one whose name says nothing
    is OCR'd, because that is the only evidence left.
    """
    if text is not None:
        return Extraction(text)
    reading = extract(path, ocr=False)
    if reading.needs_ocr and not any(_filename_hit(path, i) for i in items if _considers(i)):
        return extract_by_ocr(path)
    return reading


def route_file(
    path: Path,
    items: list[RequestItem],
    *,
    text: str | None = None,
    digest: str | None = None,
    cache: ContentCache | None = None,
    pdf_cache: PdfVerdictCache | None = None,
) -> Routing:
    """Decide which request ``path`` belongs to.

    ``text`` may be supplied by a caller that has already extracted it;
    otherwise it is read here (once, and reused across every request).
    With a ``cache`` (and the file's ``digest``, if the caller has it), the
    per-request verdicts are kept for the scan that follows. ``pdf_cache``
    spares parsing the same PDF once per manifest row.
    """
    if is_cloud_placeholder(path):
        return Routing(path=path, identifier=None, reason=PENDING, pending=True)

    # A Google-native stub can never be filed, and the client can fix it —
    # say so instead of the generic UNMATCHED.
    if stub := google_stub_reason(path):
        return Routing(path=path, identifier=None, reason=stub)

    pdf_cache = pdf_cache or PdfVerdictCache()
    reading = _read(path, items, text)
    # A text layer below _MIN_TEXT_CHARS (a scanned form's page breaks, a
    # "Page 1 of 2" stamp) is no reading: the name, or OCR, is the evidence.
    words = "" if reading.needs_ocr else (reading.text or "")
    # The scanner's verdict is the verdict on the *whole* reading; a scan
    # rescued by its name was never fully read, so nothing is remembered.
    remember = cache is not None and reading.text is not None and not reading.needs_ocr
    if remember and digest is None:
        digest = cache.digest_of(path)

    def verdict_for(item: RequestItem):
        verdict = evaluate_rules(words, item)
        if remember and digest:
            cache.put_by_digest(digest, rules_fingerprint(item), verdict)
        return verdict

    strong: list[str] = []      # required keywords matched and every rule passed
    medium: list[str] = []      # passed on any_keywords / date alone
    ocr_only: list[str] = []    # passed on any_keywords, but the text is OCR's word for it
    near: list[tuple[str, str]] = []   # looks like this request but fails a rule
    leads: list[tuple[str, str]] = []  # its keywords matched and only the year did not
    by_name: list[str] = []     # no readable text; the filename is all we have
    blocked: list[tuple[str, str]] = []  # content fits, but tier 2 refused the file
    refusals: list[str] = []    # every tier-2 reason, for an honest "why not"
    #: Why, per row: the keywords that matched and where, or the refusal.
    #: Kept for every row considered and cut down at the end to the rows
    #: the decision names (``_recorded_for``).
    record: dict[str, tuple[Evidence, ...]] = {}

    for item in items:
        if not _considers(item):
            continue
        tier2 = check_file(path, item, pdf_cache=pdf_cache)
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
            continue
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
            elif reasons.WRONG_PERIOD.matches(verdict.reason) and any_keyword_matched(words, item):
                # Every keyword this row asks for matched and only its year
                # did not. That is no filing decision - the year is a check,
                # never evidence (decision 40) - but it is the lead a person
                # needs, and it is all this file is going to give them.
                leads.append((item.identifier, verdict.reason))
        elif named := _filename_evidence(path, item):
            record[item.identifier] = named
            by_name.append(item.identifier)

    # A document that announces itself as one request's paperwork but fails
    # that request's other rules is contested — never file it somewhere else.
    if near and not strong:
        return _contested(path, near, record)

    for hits, strength, how in (
        (strong, EVIDENCE_CONTENT, "content matched this request's required keywords"),
        (medium, EVIDENCE_CONTENT, "content matched this request's keywords"),
        (by_name, EVIDENCE_FILENAME, "file name matched this request's keywords"),
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
            return Routing(path=path, identifier=None, reason=f"{UNMATCHED}; {refusals[0]}")
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

    # Nothing accepted the file, and a row's keywords all matched but its
    # year: say so with the row named, the way a contested file is said.
    # Unlike a required-keyword match, a lead never pre-empts a filing - it
    # is read only when the file was going to be parked with no candidate
    # at all, so the decision is exactly as it was and only the reason and
    # the candidates improve (the thirteenth reading).
    if leads:
        return _contested(path, leads, record)

    rule_less = [i.identifier for i in items if not _considers(i)
                 and i.manual_override != Override.WAIVED]
    hint = ""
    if rule_less:
        hint = (
            f"; add a keyword to {', '.join(rule_less[:3])} in the manifest "
            "to route files like this automatically"
        )
    return Routing(path=path, identifier=None, reason=f"{UNMATCHED}{hint}")


def route_files(paths: list[Path], items: list[RequestItem]) -> list[Routing]:
    """Route many files, skipping OS/sync junk entirely."""
    return [route_file(p, items) for p in paths if not is_ignored(p)]


# ------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.manifest import load_manifest
    from tracker.scaffold import MANIFEST_FILENAME

    parser = argparse.ArgumentParser(
        description="Where would these files go, and why? Read-only: routes, moves nothing."
    )
    parser.add_argument("engagement_dir", help=f"folder containing {MANIFEST_FILENAME}")
    parser.add_argument("files", nargs="+", help="the dropped file(s) to route")
    ns = parser.parse_args()

    manifest_items = load_manifest(Path(ns.engagement_dir) / MANIFEST_FILENAME)
    for decision in route_files([Path(f) for f in ns.files], manifest_items):
        where = decision.identifier or "Needs Review"
        print(f"{decision.path.name}\n    -> {where}: {decision.reason}")
        if decision.evidence:
            print(f"       evidence: {decision.evidence}")
        if decision.candidates:
            print(f"       candidates: {', '.join(decision.candidates)}")
        if decision.evidence_record:
            print(f"       why: {format_evidence(decision.evidence_record)}")
