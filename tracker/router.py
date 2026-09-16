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

Routing is read-only. Moving, renaming and indexing happen in
:mod:`tracker.filer`, which uses the decisions made here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from tracker.content_check import (
    contains_keyword,
    evaluate_rules,
    extract_text,
    has_content_rules,
)
from tracker.manifest import Override, RequestItem
from tracker.validators import check_file, is_cloud_placeholder, is_ignored

#: Why a file was not routed. Stored verbatim in the index's Reason column.
UNMATCHED = "matched no request"
AMBIGUOUS = "matched more than one request"
PENDING = "cloud-only placeholder; waiting for OneDrive/Google Drive to sync"

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
        if parts and all(p in words for p in parts):
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


def _eligible(path: Path, item: RequestItem) -> bool:
    """Could this request accept this file at all (type, size, readability)?"""
    return (
        item.manual_override != Override.WAIVED
        and has_content_rules(item)
        and check_file(path, item).ok
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

    if text is None:
        text = extract_text(path)

    strong: list[str] = []      # required keywords matched and every rule passed
    medium: list[str] = []      # passed on any_keywords / date alone
    near: list[tuple[str, str]] = []   # looks like this request but fails a rule
    by_name: list[str] = []     # no readable text; the filename is all we have

    for item in items:
        if not _eligible(path, item):
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
        listed = "; ".join(f"{ident} ({why})" for ident, why in near)
        return Routing(
            path=path,
            identifier=None,
            reason=f"looks like {listed} — a person should confirm",
            candidates=tuple(ident for ident, _ in near),
            evidence="content",
        )

    for hits, strength, how in (
        (strong, "content", "content matched this request's keywords"),
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

    rule_less = [
        i.identifier
        for i in items
        if i.manual_override != Override.WAIVED and not has_content_rules(i)
    ]
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
