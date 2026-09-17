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
refused (too small, wrong type, unreadable) is reported as *looks like A01
(file is 3.1 KB, below the 5 KB minimum)*, and a file every request refused
for the same reason carries that reason — "matched no request" alone is the
last resort, not the default.

Routing is read-only. Moving, renaming and indexing happen in
:mod:`tracker.filer`, which uses the decisions made here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from tracker import reasons
from tracker.content_check import contains_keyword, evaluate_rules, extract_text
from tracker.manifest import Override, RequestItem, has_routing_rules
from tracker.validators import (
    check_file,
    extension_of,
    google_stub_reason,
    is_cloud_placeholder,
    is_ignored,
)

#: Why a file was not routed. Stored verbatim in the index's Reason column.
UNMATCHED = "matched no request"
AMBIGUOUS = "matched more than one request"
PENDING = reasons.PENDING_SYNC.format()
#: Every request refused the file type: said once, checked by tests by name.
NO_REQUEST_ACCEPTS = "no request accepts .{extension} files"

_WORD_SPLIT = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class Routing:
    """Where one dropped file belongs, and why."""

    path: Path
    identifier: str | None          # None → needs human review
    reason: str                     # plain English, safe to show a client
    candidates: tuple[str, ...] = ()  # identifiers that accepted the file
    evidence: str = ""              # "content" | "filename" | ""
    pending: bool = False           # still syncing; leave it where it is

    @property
    def routed(self) -> bool:
        return self.identifier is not None


def _filename_hit(path: Path, item: RequestItem) -> bool:
    """True if a keyword from ``item`` appears in ``path``'s own name.

    Compared on word boundaries over a normalized name, so ``1098`` matches
    ``Form 1098 Mortgage.pdf`` but not ``ledger-10983.pdf``.
    """
    words = set(_WORD_SPLIT.split(path.stem.lower()))
    for keyword in (*item.required_keywords, *item.any_keywords):
        parts = [p for p in _WORD_SPLIT.split(keyword.lower()) if p]
        if not parts:
            continue
        if all(p in words for p in parts):
            return True
        # Clients write "W2" for "W-2" and "1099INT" for "1099-INT"; the
        # run-together spelling is the same whole token, not a substring.
        if len(parts) > 1 and "".join(parts) in words:
            return True
    return False


def _required_matched(text: str, item: RequestItem) -> bool:
    """True if every one of ``item``'s required keywords appears in ``text``.

    Required keywords are the accountant's strongest assertion about what a
    document *is* ("a W-2 says W-2"), which is why they both outrank
    ``any_keywords`` when choosing between requests and, when they match a
    request whose other rules then fail, stop the file being filed elsewhere.
    """
    if not item.required_keywords:
        return False
    return all(contains_keyword(text, k) for k in item.required_keywords)


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


def _contested(path: Path, near: list[tuple[str, str]]) -> Routing:
    listed = "; ".join(f"{ident} ({why})" for ident, why in near)
    return Routing(
        path=path,
        identifier=None,
        reason=f"{CONTESTED_PREFIX} {listed} - a person should confirm",
        candidates=tuple(ident for ident, _ in near),
        evidence="content",
    )


def route_file(
    path: Path, items: list[RequestItem], *, text: str | None = None
) -> Routing:
    """Decide which request ``path`` belongs to.

    ``text`` may be supplied by a caller that has already extracted it;
    otherwise it is extracted here (once, and reused across every request).
    """
    if is_cloud_placeholder(path):
        return Routing(path=path, identifier=None, reason=PENDING, pending=True)

    # A Google-native stub can never be filed, and the client can fix it —
    # say so instead of the generic "matched no request".
    if stub := google_stub_reason(path):
        return Routing(path=path, identifier=None, reason=stub)

    if text is None:
        try:
            text = extract_text(path)
        except Exception as exc:  # a corrupt file is a review reason, not a crash
            text = None
            extraction_error = f"{exc.__class__.__name__}: {exc}"
        else:
            extraction_error = ""
    else:
        extraction_error = ""

    strong: list[str] = []      # required keywords matched and every rule passed
    medium: list[str] = []      # passed on any_keywords / date alone
    near: list[tuple[str, str]] = []   # looks like this request but fails a rule
    by_name: list[str] = []     # no readable text; the filename is all we have
    blocked: list[tuple[str, str]] = []  # content fits, but tier 2 refused the file
    refusals: list[str] = []    # every tier-2 reason, for an honest "why not"

    for item in items:
        if not _considers(item):
            continue
        tier2 = check_file(path, item)
        if not tier2.ok:
            refusals.append(tier2.reason)
            if text and evaluate_rules(text, item).ok:
                blocked.append((item.identifier, tier2.reason))
            continue
        if text:
            verdict = evaluate_rules(text, item)
            if verdict.ok:
                (strong if _required_matched(text, item) else medium).append(
                    item.identifier
                )
            elif _required_matched(text, item):
                near.append((item.identifier, verdict.reason))
        elif _filename_hit(path, item):
            by_name.append(item.identifier)

    # A document that announces itself as one request's paperwork but fails
    # that request's other rules is contested — never file it somewhere else.
    if near and not strong:
        return _contested(path, near)

    for hits, strength, how in (
        (strong, "content", "content matched this request's required keywords"),
        (medium, "content", "content matched this request's keywords"),
        (by_name, "filename", "file name matched this request's keywords"),
    ):
        if len(hits) == 1:
            return Routing(
                path=path,
                identifier=hits[0],
                reason=how,
                candidates=tuple(hits),
                evidence=strength,
            )
        if len(hits) > 1:
            return Routing(
                path=path,
                identifier=None,
                reason=f"{AMBIGUOUS} ({', '.join(hits)}); a person should choose",
                candidates=tuple(hits),
                evidence=strength,
            )

    # The content says which request this is, but the file itself was
    # refused (too small, wrong type, unreadable PDF). Say that, so the
    # person reviewing it - and the client, via the reminder - hears the
    # real reason instead of "matched no request".
    if blocked:
        return _contested(path, blocked)

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

    if extraction_error:
        return Routing(
            path=path,
            identifier=None,
            reason=f"{UNMATCHED}; could not read it ({extraction_error})",
        )

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
