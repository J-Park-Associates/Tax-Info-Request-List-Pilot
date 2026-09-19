"""The page a person opens: derived from the record, holding no facts of its own.

Stage A step 3 of the record/view separation (decision 89), as the owner
settled it in decision 91: **every file staff open only to read is a web
page; the one file they edit stays a workbook.** The record
(:mod:`tracker.ledger`) is what the machine decided, the two workbooks beside
it are written exactly as before, and this is the third thing - **one file a
person opens that nobody has to be careful with.**

``VIEW_FILENAME`` is that file, and it carries no leading underscore on
purpose: the machine-owned files keep theirs, and this is the one a person
is meant to open. :func:`write_view` regenerates it at the end of every real
pass from the readers - :func:`tracker.manifest.load_manifest` for the
request rows as the readers now answer them, :func:`tracker.filer.read_index`
for the index, and :func:`tracker.review.triage` for what each parked file
might be. Four sections, in the order a person reads them:

- **Summary** - the rules workbook's digest, the record's head, when it was
  drawn, the counts, and the sentence that says it is regenerated every
  pass and holds nothing of its own.
- **Requests** - the person's rules, the keywords a filing taught, and each
  row's status as a badge.
- **Index** - every original, in the index's own column order.
- **Needs Review** - the rows parked for a person, and under each the
  shortlist the app's review card shows, in the words
  :mod:`tracker.review` gives them.

**Why a page and not a workbook.** A workbook is a thing a person types
into, and this is a thing nobody may type into: the read-only attribute,
the sentence on the Summary and the six decisions spent on Excel's locking
were all defences of that one point. A browser holds no write lock, opens
from a double click on any machine in the firm, prints, and cannot be
edited into a second version of the truth. So there is no attribute to set
and none to clear before the next replace.

**It holds no facts, and that is the whole point.** Nothing reads this file
back: not the pass, not the app, not the drafts. So the one failure mode
every other file has - somebody has it open when the pass wants to write it
- costs nothing here. The replace fails, the run carries ``view_stale`` and
**succeeds**, and the page on disk stays one pass behind until the next one
lands. No sidecar, no retry, no deferred rows: there is nothing in it that
is not somewhere else.

**Current, behind, or unknown.** Because the view is a mirrored derivation,
a person has to be able to tell whether the thing in front of them is still
true. :func:`view_state` answers by comparing the stamp the page carries in
its ``<head>`` - the rules workbook's SHA-256 and the record's head as they
were when the page was drawn - with those same two things now: ``CURRENT``
when both match, ``BEHIND`` when the page is there and either has moved on,
``UNKNOWN`` when there is no page or its stamp cannot be read. The stamp is
in meta tags rather than in the visible text, so reading it is a short
regular expression over the head of the file and never a parser; the same
values are shown in the Summary for a person.

**Every value is escaped, and nothing is fetched.** One escaper
(:func:`tracker.page.esc`), shared with the practice-wide page, so a client
file called like a tag is shown as its name; no script but the few lines
that sort a table, no style sheet, no font and no image, because a page
naming the firm's clients must not reach the network to render. It carries
only what the index and the request list already carry - catalog terms,
file names, statuses, reasons - and not one word of a client's document.

**Imports downwards only.** This module reads the record, the manifest, the
index, the triage and the engagement's file names, and nothing in the
package imports it but :mod:`tracker.runner` and :mod:`tracker.api`, which
sit above all of them. Writing the view is the last thing a pass does.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from tracker import ledger, review
from tracker.filer import (
    INDEX_SHEET,
    NEEDS_REVIEW,
    FilingError,
    read_index,
    rules_digest,
)
from tracker.manifest import (
    ANY_EXTENSION,
    COL_ALLOWED_EXTENSIONS,
    COL_ANY_KEYWORDS,
    COL_DATE_PATTERN,
    COL_DOCUMENT,
    COL_EXPECTED_COUNT,
    COL_FILE_COUNT,
    COL_IDENTIFIER,
    COL_MANUAL_OVERRIDE,
    COL_MIN_SIZE_KB,
    COL_PERIOD,
    COL_RECEIVED_DATE,
    COL_REQUIRED_KEYWORDS,
    COL_STATUS,
    COL_VALIDATION_NOTES,
    HEADERS,
    SHEET_NAME,
    ManifestError,
    Override,
    RequestItem,
    Status,
    load_manifest,
    write_text_atomically,
)
from tracker.page import Cell, Row, esc, page_text, slug, table, unesc
from tracker.records import (
    BEHIND,
    CURRENT,
    INDEX_COLUMNS,
    INDEX_LAYOUT,
    STATES,
    UNKNOWN,
    IndexEntry,
)
from tracker.scaffold import MANIFEST_FILENAME

log = logging.getLogger("tracker.view")

#: The file a person opens. Regenerated every pass; it holds no facts.
VIEW_FILENAME = "Status Report.html"

#: The section carrying the stamp. The other three are named by the modules
#: that own what they show, so the page invents no heading of its own.
SUMMARY_SECTION = "Summary"
#: The sections, in the order they are drawn and the navigation lists them.
SECTIONS = (SUMMARY_SECTION, SHEET_NAME, INDEX_SHEET, NEEDS_REVIEW)

#: What the Summary says about itself, in the first line a person reads.
VIEW_NOTE = ("This page is regenerated every pass and holds no facts of its own: "
             "every value on it comes from the record, the request list and the index.")

#: The Summary's labels. ``view_state`` reads two of them back, so they are
#: the stamp's field names and are worded once.
LABEL_ENGAGEMENT = "Engagement folder"
LABEL_GENERATED = "Generated (UTC)"
LABEL_GENERATED_LOCAL = "Generated (this machine)"
LABEL_RULES_DIGEST = "Rules workbook SHA-256"
LABEL_RECORD_DIGEST = "Record SHA-256"
LABEL_REQUEST_ROWS = "Request rows"
LABEL_INDEX_ROWS = "Index rows"
LABEL_PARKED_ROWS = "Parked for a person"

#: The same values, machine-readable, as the meta tags the head carries.
#: ``read_stamp`` reads these rather than the visible text: a label is
#: written for a person and may be reworded, and a meta name is a field
#: name that must not move under a reader.
META_NAMES: dict[str, str] = {
    LABEL_ENGAGEMENT: "tracker-engagement",
    LABEL_GENERATED: "tracker-generated",
    LABEL_GENERATED_LOCAL: "tracker-generated-local",
    LABEL_RULES_DIGEST: "tracker-rules-sha256",
    LABEL_RECORD_DIGEST: "tracker-record-sha256",
    LABEL_REQUEST_ROWS: "tracker-request-rows",
    LABEL_INDEX_ROWS: "tracker-index-rows",
    LABEL_PARKED_ROWS: "tracker-parked-rows",
}
_LABEL_BY_META = {name: label for label, name in META_NAMES.items()}
_META_PATTERN = re.compile(r'<meta name="([^"]+)" content="([^"]*)">')

#: What the app says about a view, and the three words it may say. The view
#: is a derivation of two things that both move, so "there is one" is not an
#: answer: a person has to know whether it still describes what is there.
#: The words themselves are :mod:`tracker.records`' since decision 101,
#: because the store answers about an engagement's rows in the same three;
#: they are re-exported here so every caller that had them from this module
#: still gets the same objects.
VIEW_STATES = STATES
#: What the chip beside the engagement calls it, and what the button that
#: opens it says. Both are the API's vocabulary; the app types neither.
VIEW_LABEL = "Status report"
VIEW_OPEN_LABEL = "Open Status Report"

#: The index columns the review section repeats. The headers still come
#: from the index's own table, so there is one owner for them.
NEEDS_REVIEW_FIELDS = ("received", "original_name", "pbc_location", "reason",
                       "candidates", "evidence")

#: What a coloured status word is classed as, and what a row nobody wants
#: any more is classed as. The colours are matched to each value below.
BADGE_CLASS = "badge"
WAIVED_CLASS = "waived"
_BADGE_COLOURS: dict[str, str] = {
    Status.RECEIVED: "background: #ecfdf5; border-color: #a7f3d0; color: #047857;",
    Status.PARTIAL: "background: #fffbeb; border-color: #fde68a; color: #b45309;",
    Status.FAILED: "background: #fef2f2; border-color: #fecaca; color: #b91c1c;",
    Status.MISSING: "background: #f1f5f9; border-color: #d8e0ea; color: #475569;",
    Status.PENDING_SYNC: "background: #eff6ff; border-color: #bfdbfe; color: #1d4ed8;",
    Override.ACCEPTED: "background: #ecfdf5; border-color: #a7f3d0; color: #047857;",
    Override.WAIVED: "background: #f8fafc; border-color: #e2e8f0; color: #64748b;",
}

#: Inline, because the page is one file that must render from a share, a
#: memory stick or an email attachment with nothing fetched, and printable,
#: because the firm prints one for a file when a client asks what is
#: outstanding. Kept in step with the practice-wide page's own style. The
#: badge rules are written from the values themselves, so a class name can
#: never drift from the word it colours.
_BASE_STYLE = """
body { font-family: "Segoe UI", system-ui, sans-serif; margin: 2rem 2.5rem; color: #1c1c1c;
       background: #fbfbfa; line-height: 1.45; }
h1 { font-size: 1.35rem; margin: 0 0 0.2rem; }
h2 { font-size: 1.05rem; margin: 0 0 0.6rem; border-bottom: 1px solid #d8d6d1; padding-bottom: 0.3rem; }
h3 { font-size: 0.92rem; margin: 0.9rem 0 0.2rem; }
p.stamp { margin: 0 0 0.6rem; color: #6b6862; font-size: 0.85rem; max-width: 60rem; }
section { margin: 2rem 0 0; overflow-x: auto; }
nav { position: sticky; top: 0; background: #fbfbfa; border-bottom: 1px solid #d8d6d1;
      padding: 0.5rem 0; margin: 0 0 0.5rem; font-size: 0.87rem; }
nav a { color: #1d4ed8; text-decoration: none; margin-right: 1.2rem; }
nav a:hover { text-decoration: underline; }
dl { display: grid; grid-template-columns: max-content 1fr; gap: 0.25rem 1.2rem;
     font-size: 0.87rem; margin: 0; }
dt { color: #6b6862; }
dd { margin: 0; font-family: "Cascadia Mono", Consolas, monospace; word-break: break-all; }
table { border-collapse: collapse; width: 100%; font-size: 0.87rem; }
th, td { text-align: left; padding: 0.35rem 0.6rem; border-bottom: 1px solid #e6e4df; vertical-align: top; }
th { background: #f0eeea; font-weight: 600; white-space: nowrap; cursor: pointer; }
th::after { content: ""; color: #9b978f; }
th[data-sort="up"]::after { content: " \\2191"; }
th[data-sort="down"]::after { content: " \\2193"; }
tr:hover td { background: #f6f5f2; }
tr.waived td { color: #9b978f; }
ul { margin: 0.2rem 0 0; padding-left: 1.2rem; font-size: 0.87rem; }
li { margin-bottom: 0.2rem; }
p.nothing { margin: 0.2rem 0 0; color: #6b6862; font-size: 0.87rem; }
.badge { display: inline-block; padding: 0.05rem 0.45rem; border-radius: 999px;
         border: 1px solid; font-size: 0.8rem; white-space: nowrap; }
@media print { nav { display: none; } body { margin: 0; background: #fff; } }
"""
_STYLE = _BASE_STYLE + "".join(
    f".{BADGE_CLASS}-{slug(word)} {{ {colours} }}\n" for word, colours in _BADGE_COLOURS.items()
)

#: Sorting, in the few lines it takes. No library, nothing fetched, and
#: nothing the page needs to be read: with scripts off every table is the
#: plain table it was drawn as, in the order the readers gave it.
_SORT_SCRIPT = """
for (const th of document.querySelectorAll("th[data-sort]")) {
  th.addEventListener("click", () => {
    const head = th.parentNode;
    const body = th.closest("table").tBodies[0];
    const column = [...head.children].indexOf(th);
    const up = th.getAttribute("data-sort") !== "up";
    for (const other of head.children) other.setAttribute("data-sort", "");
    th.setAttribute("data-sort", up ? "up" : "down");
    const rows = [...body.rows];
    rows.sort((a, b) => (up ? 1 : -1) *
      a.cells[column].textContent.localeCompare(b.cells[column].textContent,
                                                undefined, {numeric: true}));
    body.append(...rows);
  });
}
"""


class ViewError(RuntimeError):
    """The view could not be built from what the readers say."""


@dataclass(slots=True)
class ViewResult:
    """What one regeneration did. ``stale`` is the only interesting failure."""

    path: Path
    stale: bool = False              # the replace did not land; the old one stands
    requests: int = 0
    rows: int = 0
    parked: int = 0
    stamp: dict[str, str] = field(default_factory=dict)


# ------------------------------------------------------------------ cells ----


def _text(value: object) -> str:
    """One value as a cell of the page: a string, always.

    A date is written the way the manifest's own date hint spells one, and a
    blank is a blank rather than the word for nothing. Everything else is
    ``str()``.
    """
    if value is None:
        return ""
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


def request_row(item: RequestItem) -> dict[str, str]:
    """One Requests row, column header to cell text.

    The one definition of what the view says about a request, so the suite's
    agreement fixture compares the page with the reader through the same
    function rather than a second copy of these rules.
    """
    return {
        COL_IDENTIFIER: _text(item.identifier),
        COL_DOCUMENT: _text(item.document),
        COL_PERIOD: _text(item.period),
        COL_EXPECTED_COUNT: _text(item.expected_count),
        # An item with no extensions accepts anything; the manifest says so
        # out loud rather than leaving a blank, and so does the view.
        COL_ALLOWED_EXTENSIONS: ", ".join(item.allowed_extensions) or ANY_EXTENSION,
        COL_MIN_SIZE_KB: _text(item.min_size_kb),
        COL_REQUIRED_KEYWORDS: ", ".join(item.required_keywords),
        COL_ANY_KEYWORDS: ", ".join(item.any_keywords),
        COL_DATE_PATTERN: _text(item.date_pattern),
        COL_MANUAL_OVERRIDE: _text(item.manual_override),
        COL_STATUS: _text(item.status),
        COL_RECEIVED_DATE: _text(item.received_date),
        COL_FILE_COUNT: _text(item.file_count),
        COL_VALIDATION_NOTES: _text(item.validation_notes),
    }


def index_row(entry: IndexEntry) -> list[str]:
    """One Index row as the view writes it: the reader's own row, as text."""
    return [_text(value) for value in entry.as_row()]


def _needs_review_row(entry: IndexEntry) -> list[str]:
    return [_text(getattr(entry, name)) for name in NEEDS_REVIEW_FIELDS]


def _badge(word: str) -> Cell:
    """One status or override as a coloured word, classed by the value."""
    return Cell(word, class_name=f"{BADGE_CLASS} {BADGE_CLASS}-{slug(word)}", badge=True)


def _request_cells(item: RequestItem) -> Row:
    """One Requests row as it is drawn: the statuses as badges, a row the
    firm no longer wants dimmed rather than dropped - it was asked for once
    and the page is the record of what was asked."""
    row = request_row(item)
    values: list[object] = []
    for header in HEADERS:
        word = row[header]
        badged = header in (COL_STATUS, COL_MANUAL_OVERRIDE) and word
        values.append(_badge(word) if badged else word)
    dimmed = row[COL_MANUAL_OVERRIDE] == Override.WAIVED
    return Row(tuple(values), class_name=WAIVED_CLASS if dimmed else "")


# ------------------------------------------------------------------ write ----


def _readers(
    engagement_dir: Path,
    items: list[RequestItem] | None,
    entries: list[IndexEntry] | None,
) -> tuple[list[RequestItem], list[IndexEntry]]:
    """What the readers say, read here if the caller has not read it already."""
    try:
        if items is None:
            items = load_manifest(engagement_dir / MANIFEST_FILENAME)
        if entries is None:
            entries = read_index(engagement_dir)
    except (ManifestError, FilingError, OSError) as exc:
        # A manifest the loader refuses or an index the tracker will not
        # touch: there is nothing to draw, and the caller decides what that
        # means. A pass says it in a log line and stands.
        raise ViewError(f"{engagement_dir.name}: the view could not be built ({exc})") from exc
    return items, entries


def _stamp(
    engagement_dir: Path,
    items: list[RequestItem],
    entries: list[IndexEntry],
    parked: list[IndexEntry],
    now: dt.datetime | None,
) -> dict[str, str]:
    """The stamp the head carries and the Summary shows, label to value.

    Both times come from one moment: the UTC one is what a reader compares
    and what travels between machines, the local one is the only one a
    person in the office reads without arithmetic.
    """
    generated = now or dt.datetime.now(dt.UTC)
    return {
        LABEL_ENGAGEMENT: engagement_dir.name,
        LABEL_GENERATED: generated.isoformat(timespec="seconds"),
        LABEL_GENERATED_LOCAL: generated.astimezone().isoformat(sep=" ", timespec="seconds"),
        LABEL_RULES_DIGEST: rules_digest(engagement_dir),
        LABEL_RECORD_DIGEST: ledger.head(engagement_dir),
        LABEL_REQUEST_ROWS: str(len(items)),
        LABEL_INDEX_ROWS: str(len(entries)),
        LABEL_PARKED_ROWS: str(len(parked)),
    }


def _anchor(section: str) -> str:
    """Where the navigation's link for one section points."""
    return slug(section)


def _heading(section: str, count: int | None = None) -> list[str]:
    counted = esc(section) if count is None else f"{esc(section)} ({count})"
    return [f'<section id="{esc(_anchor(section))}">', f"<h2>{counted}</h2>"]


def _summary(stamp: dict[str, str]) -> list[str]:
    return [
        *_heading(SUMMARY_SECTION),
        "<dl>",
        *(line for label, value in stamp.items()
          for line in (f"<dt>{esc(label)}</dt>", f"<dd>{esc(value)}</dd>")),
        "</dl>",
        "</section>",
    ]


def _triage_block(triaged: review.Triage) -> list[str]:
    """One parked file's shortlist, in the words :mod:`tracker.review` gives
    it - the same sentences the app's review card shows, so a person reading
    the page sees what the app would suggest."""
    if not triaged.shortlist:
        return [f"<h3>{esc(triaged.entry.original_name)}</h3>",
                f'<p class="nothing">{esc(review.NOTHING_SUGGESTED)}</p>']
    return [
        f"<h3>{esc(triaged.entry.original_name)}</h3>",
        "<ul>",
        *(f"<li>{esc(suggestion.reason)}</li>" for suggestion in triaged.shortlist),
        "</ul>",
    ]


def _body(
    engagement_dir: Path,
    items: list[RequestItem],
    entries: list[IndexEntry],
    triaged: list[review.Triage],
    stamp: dict[str, str],
) -> list[str]:
    return [
        f"<h1>{esc(engagement_dir.name)} — {esc(VIEW_LABEL)}</h1>",
        f'<p class="stamp">{esc(VIEW_NOTE)}</p>',
        "<nav>",
        *(f'<a href="#{esc(_anchor(section))}">{esc(section)}</a>' for section in SECTIONS),
        "</nav>",
        *_summary(stamp),
        *_heading(SHEET_NAME, len(items)),
        *table(HEADERS, (_request_cells(item) for item in items), sortable=True),
        "</section>",
        *_heading(INDEX_SHEET, len(entries)),
        *table(INDEX_COLUMNS, (index_row(entry) for entry in entries), sortable=True),
        "</section>",
        *_heading(NEEDS_REVIEW, len(triaged)),
        *table([INDEX_LAYOUT[name][0] for name in NEEDS_REVIEW_FIELDS],
               (_needs_review_row(one.entry) for one in triaged), sortable=True),
        *(line for one in triaged for line in _triage_block(one)),
        "</section>",
    ]


def _page(
    engagement_dir: Path,
    items: list[RequestItem],
    entries: list[IndexEntry],
    triaged: list[review.Triage],
    stamp: dict[str, str],
) -> str:
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{esc(engagement_dir.name)} — {esc(VIEW_LABEL)}</title>",
        *(f'<meta name="{esc(META_NAMES[label])}" content="{esc(value)}">'
          for label, value in stamp.items() if label in META_NAMES),
        f"<style>{_STYLE}</style>",
        "</head>",
        "<body>",
        *_body(engagement_dir, items, entries, triaged, stamp),
        f"<script>{_SORT_SCRIPT}</script>",
        "</body>",
        "</html>",
    ]
    return page_text(lines)


def render_page(
    engagement_dir: Path | str,
    *,
    items: list[RequestItem] | None = None,
    entries: list[IndexEntry] | None = None,
    now: dt.datetime | None = None,
) -> str:
    """The page for one engagement as text, writing nothing.

    The whole rendering, in one call that touches no file but the ones the
    readers open, so the suite's agreement fixture can draw the page again
    from the readers and compare it with what is on disk. A page showing a
    row the readers do not have would differ in that comparison, which is
    the only claim the fixture makes.
    """
    engagement_dir = Path(engagement_dir)
    items, entries = _readers(engagement_dir, items, entries)
    triaged = review.triage(engagement_dir, entries, items=items)
    parked = [one.entry for one in triaged]
    stamp = _stamp(engagement_dir, items, entries, parked, now)
    return _page(engagement_dir, items, entries, triaged, stamp)


def write_view(
    engagement_dir: Path | str,
    *,
    items: list[RequestItem] | None = None,
    entries: list[IndexEntry] | None = None,
    now: dt.datetime | None = None,
) -> ViewResult:
    """Regenerate the view for one engagement. Returns what it did.

    ``items`` and ``entries`` are the readers' answers, so a caller that has
    already read them (a pass has) does not pay for a second reading. Left
    out, they are read here exactly as the app reads them: nothing is moved,
    not even a sidecar that cannot be parsed - drawing the view changes
    nothing about what it describes.

    **Never raises because somebody had it open.** The replace goes through
    the same atomic swap the index uses, and a file another process holds
    raises from it; that is reported as ``stale`` and the caller carries on.
    The view holds no fact that is not in the record and the workbooks, so a
    stale one costs a person one pass of freshness and nothing else.
    """
    engagement_dir = Path(engagement_dir)
    path = engagement_dir / VIEW_FILENAME
    items, entries = _readers(engagement_dir, items, entries)
    triaged = review.triage(engagement_dir, entries, items=items)
    parked = [one.entry for one in triaged]
    stamp = _stamp(engagement_dir, items, entries, parked, now)
    result = ViewResult(path=path, requests=len(items), rows=len(entries),
                        parked=len(parked), stamp=stamp)
    try:
        write_text_atomically(path, _page(engagement_dir, items, entries, triaged, stamp))
    except OSError as exc:
        # Somebody has it open, and on Windows an open read handle is
        # enough to refuse the swap. Nothing here is a fact, so this is the
        # one write in the system that may simply not happen.
        log.warning(
            "%s: %s was not regenerated (%s); it stays one pass behind and the run stands",
            engagement_dir.name, VIEW_FILENAME, exc,
        )
        result.stale = True
    return result


# ------------------------------------------------------------------- read ----


def path_for(engagement_dir: Path | str) -> Path:
    """Where one engagement's view lives."""
    return Path(engagement_dir) / VIEW_FILENAME


def read_stamp(engagement_dir: Path | str) -> dict[str, str] | None:
    """The stamp the page's head carries, or None if there is no readable one.

    The meta tags this module wrote, read back by name with one regular
    expression over the head of the file: the values are the page's own,
    written in one place and never nested, so a parser would buy nothing
    and would have to be defended against a page somebody saved from a
    browser. Read from the file's bytes and takes no lock - looking at a
    derivation cannot change anything - and a file that is not this page
    simply carries none of these names, which is "unknown".
    """
    path = path_for(engagement_dir)
    try:
        data = path.read_bytes()
    except OSError:
        return None
    head = data.decode("utf-8", "replace").split("</head>", 1)[0]
    stamp = {}
    for name, value in _META_PATTERN.findall(head):
        label = _LABEL_BY_META.get(name)
        # A blank value is a value: an engagement with no record yet was
        # stamped with an empty head, and reading that as "no stamp" would
        # leave a fresh view permanently unknown.
        if label is not None:
            stamp[label] = unesc(value)
    return stamp or None


def view_state(engagement_dir: Path | str) -> str:
    """Whether the view still describes the engagement: one of ``VIEW_STATES``.

    ``CURRENT`` when the stamp's two digests are the rules workbook's and
    the record's head *now*; ``BEHIND`` when there is a view and either has
    moved on since it was drawn; ``UNKNOWN`` when there is none, or its
    stamp cannot be read. The firm's rule for a mirrored derivation is that
    it says how old it is rather than looking authoritative, and these are
    the three honest answers.
    """
    engagement_dir = Path(engagement_dir)
    stamp = read_stamp(engagement_dir)
    if not stamp:
        return UNKNOWN
    if LABEL_RULES_DIGEST not in stamp or LABEL_RECORD_DIGEST not in stamp:
        return UNKNOWN
    matches = (
        stamp[LABEL_RULES_DIGEST] == rules_digest(engagement_dir)
        and stamp[LABEL_RECORD_DIGEST] == ledger.head(engagement_dir)
    )
    return CURRENT if matches else BEHIND


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m tracker.view",
        description="Regenerate the engagement's status report page and say whether "
                    "it is current. Writes nothing else and takes no lock.",
    )
    parser.add_argument("engagement_dir", help="the engagement folder")
    ns = parser.parse_args()

    folder = Path(ns.engagement_dir)
    written = write_view(folder)
    print(f"\n{written.path}")
    if written.stale:
        print("  not regenerated: it is open somewhere; the one on disk stands")
    print(f"  requests: {written.requests}")
    print(f"  rows:     {written.rows}")
    print(f"  parked:   {written.parked}")
    for label, value in written.stamp.items():
        print(f"  {label + ':':<26}{value}")
    print(f"  state:    {view_state(folder)}\n")
