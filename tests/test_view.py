"""Tests for tracker/view.py - the page a pass regenerates for one engagement.

The view's standing claim is not made here: it is the autouse fixture in
tests/conftest.py, which draws every view the suite leaves behind again from
the readers and compares it with what is on disk, byte for byte. What is
made here is the view's own behaviour - the four sections and the navigation,
the stamp in the head, the escaping, the shortlist under each parked file,
the three words it answers "is this still true?" with, and the one failure
it is allowed to have: somebody had it open when the pass tried to replace
it.

Tables are read back with ``html.parser`` **here and nowhere in the
package**: a test may parse what production only ever writes, and reading
the cells back is how the claim "this row is on the page" is made without
matching markup by eye.
"""

from __future__ import annotations

import datetime as dt
import html
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tests.conftest import make_engagement, named_page, sort
from tests.test_scanner import text_pdf
from tracker import ledger, review, view
from tracker.filer import NEEDS_REVIEW, read_index
from tracker.layout import household_of, inbox_of, root_of
from tracker.manifest import (
    COL_ANY_KEYWORDS,
    COL_STATUS,
    Override,
    RequestItem,
    Status,
    load_engagement_info,
    load_manifest,
    save_rules,
)
from tracker.page import slug
from tracker.records import rule_from_json
from tracker.registry import RegistryError, discover_engagements, engagement_dirs
from tracker.runner import run_household
from tracker.scanner import scan_engagement

REPO = Path(__file__).resolve().parents[1]
DAY1 = dt.date(2026, 7, 1)

ITEMS = [
    RequestItem(
        identifier="A01", document="W-2 Wage Statements", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("W-2",),
        date_pattern=r"(?i)\b2025\b",
    ),
    RequestItem(
        identifier="C01", document="Mortgage Interest Statement", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("1098",),
    ),
    RequestItem(
        identifier="E01", document="Prior Year Return", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("1040",),
        manual_override=Override.NOT_APPLICABLE,
    ),
]


@pytest.fixture
def engagement(tmp_path):
    return make_engagement(tmp_path, ITEMS, household="Smith Family")


def drop(engagement, name, text):
    """One document into the household's inbox, with the return's person on
    the page - a named request files only where a name confirms (128)."""
    return text_pdf(inbox_of(engagement) / name, named_page(text))


def a_pass(engagement, today=DAY1):
    """What a pass does to the folder, without a registry: sort, then scan."""
    sort(engagement, today=today)
    scan_engagement(engagement, today=today)


def type_a_keyword(engagement, identifier, keyword):
    """A person typing a keyword into the request list, in the app: one
    saved edit, from the rows as the store holds them."""
    from dataclasses import replace

    from tracker import store

    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement)]
    edited = [replace(row, any_keywords=(keyword,)) if row.identifier == identifier else row
              for row in rows]
    save_rules(engagement, edited, load_engagement_info(engagement))


def teach_a_keyword(engagement, identifier, keyword):
    """A person's filing teaching a request a keyword: recorded, not typed."""
    from tests.conftest import ensure
    from tracker import store
    from tracker.locking import engagement_lock

    with engagement_lock(engagement):
        ensure(engagement)
        store.record(store.connect(), engagement, ledger.new(ledger.KEYWORD_LEARNED, **{
            ledger.IDENTIFIER_KEY: identifier, ledger.KEYWORD_KEY: keyword,
        }))


def page_of(engagement) -> str:
    return view.path_for(engagement).read_text(encoding="utf-8")


class _Tables(HTMLParser):
    """Every table on the page as lists of cell text, header row first."""

    def __init__(self):
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.tables[-1].append(self._row)
            self._row = None


def tables(text: str) -> list[list[list[str]]]:
    parser = _Tables()
    parser.feed(text)
    return parser.tables


def table_headed(engagement, columns):
    """The one table on the page whose header row is ``columns`` - found by
    its heading, because the Requests section may fold a second table of
    the same columns below the first (the set-aside rows)."""
    return next(t for t in tables(page_of(engagement)) if t[0] == list(columns))


def requests_table(engagement):
    return table_headed(engagement, view.REQUEST_COLUMNS)


def not_applicable_tables(engagement):
    """The folded tables of set-aside rows, after the active Requests table."""
    found = [t for t in tables(page_of(engagement)) if t[0] == list(view.REQUEST_COLUMNS)]
    return found[1:]


def index_table(engagement):
    return table_headed(engagement, view.INDEX_COLUMNS)


def review_table(engagement):
    return table_headed(engagement, [view.INDEX_LAYOUT[name][0] for name in view.NEEDS_REVIEW_FIELDS])


# ------------------------------------------------------ the four sections ----


def test_the_page_has_the_four_sections_and_a_navigation_to_each(engagement):
    view.write_view(engagement)
    page = page_of(engagement)

    assert view.SECTIONS == (view.SUMMARY_SECTION, "Requests", "Index", NEEDS_REVIEW)
    for section in view.SECTIONS:
        assert f'<section id="{slug(section)}">' in page, section
        assert f'<a href="#{slug(section)}">{section}</a>' in page, section
        assert f">{html.escape(section)}" in page, section
    # And the tables are the ones the sections own, headed by the columns
    # their own modules name: the Requests table, the folded table of the
    # one set-aside row under it, the Index and Needs Review.
    assert [table[0] for table in tables(page)] == [
        list(view.REQUEST_COLUMNS),
        list(view.REQUEST_COLUMNS),
        list(view.INDEX_COLUMNS),
        [view.INDEX_LAYOUT[name][0] for name in view.NEEDS_REVIEW_FIELDS],
    ]
    assert view.VIEW_NOTE in page


def test_the_page_carries_a_policy_allowing_only_its_own_style_and_script(engagement):
    """The page sits in the office's folder, where anyone could edit it. Its
    policy (decision 190) lets a browser run the style and the sort script
    the page was written with, each by the SHA-256 of its text as it stands
    on the page, and fetch nothing."""
    import base64
    import hashlib

    view.write_view(engagement)
    page = page_of(engagement)

    def allowed(block: str) -> str:
        digest = hashlib.sha256(block.encode("utf-8")).digest()
        return f"'sha256-{base64.b64encode(digest).decode('ascii')}'"

    (style,) = re.findall(r"<style>(.*?)</style>", page, re.S)
    (script,) = re.findall(r"<script>(.*?)</script>", page, re.S)
    (policy,) = re.findall(r'<meta http-equiv="Content-Security-Policy" content="([^"]*)">', page)
    assert policy == f"default-src 'none'; style-src {allowed(style)}; script-src {allowed(script)}"
    assert page.index("Content-Security-Policy") < page.index("<style>")


def test_every_index_row_is_on_the_page_as_the_reader_gives_it(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "puzzle.pdf", "a page about nothing anybody asked for")
    a_pass(engagement)
    view.write_view(engagement)

    entries = read_index(engagement)
    assert len(entries) == 2
    assert index_table(engagement)[1:] == [view.index_row(entry) for entry in entries]


def test_every_request_row_is_on_the_page_with_the_status_the_record_holds(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    type_a_keyword(engagement, "C01", "lender")     # a person edits the list
    a_pass(engagement)                              # and the pass works from it
    view.write_view(engagement)

    items = load_manifest(engagement)
    rows = requests_table(engagement)
    assert rows[1:] == [[view.request_row(item)[header] for header in view.REQUEST_COLUMNS]
                        for item in items if item.manual_override != Override.NOT_APPLICABLE]

    by_identifier = {row[0]: dict(zip(view.REQUEST_COLUMNS, row, strict=True)) for row in rows[1:]}
    assert by_identifier["A01"][COL_STATUS] == Status.RECEIVED
    assert "lender" in by_identifier["C01"][COL_ANY_KEYWORDS]
    # And that status is the one the record holds, not a second reading.
    assert by_identifier["A01"][COL_STATUS] == next(
        i.status for i in items if i.identifier == "A01"
    )
    # A status is a coloured word, classed by the value it says.
    assert f'<span class="{view.BADGE_CLASS} {view.BADGE_CLASS}-{slug(Status.RECEIVED)}">' in page_of(engagement)


def test_a_keyword_a_filing_taught_is_on_the_page_beside_the_typed_ones(engagement):
    """Decision 103: the word is in the record, not in a cell, and the page
    is where a person sees what their filing taught the request."""
    type_a_keyword(engagement, "C01", "mortgage")
    teach_a_keyword(engagement, "C01", "lender")
    view.write_view(engagement)

    row = {r[0]: dict(zip(view.REQUEST_COLUMNS, r, strict=True))
           for r in requests_table(engagement)[1:]}["C01"]
    assert row[COL_ANY_KEYWORDS] == "mortgage, lender"


def test_not_applicable_rows_sit_in_a_collapsed_section_per_year_and_the_active_table_holds_the_rest(
    engagement,
):
    """Decision 91 kept a set-aside row on the page, dimmed; 116 folds it
    away as well: out of the active table, under a details block headed
    by its year's label and count, in the same columns, still dimmed.
    With none, nothing is drawn."""
    from tracker.manifest import load_engagement_info, save_rules

    view.write_view(engagement)
    page = page_of(engagement)

    assert [row[0] for row in requests_table(engagement)[1:]] == ["A01", "C01"]
    [folded] = not_applicable_tables(engagement)
    assert [row[0] for row in folded[1:]] == ["E01"]
    assert "Not Applicable in TY2025" in folded[1]
    heading = view.SET_ASIDE_SECTION.format(n=1)
    assert f"<details><summary>{html.escape(heading)}</summary>" in page
    group = view.SET_ASIDE_GROUP.format(label="Not Applicable in TY2025", n=1)
    assert f"<h3>{html.escape(group)}</h3>" in page
    assert page.count(f'<tr class="{view.NOT_APPLICABLE_CLASS}">') == 1
    assert f"{view.BADGE_CLASS}-{slug(Override.NOT_APPLICABLE)}" in page
    assert "<h2>Requests (2)</h2>" in page

    # A second year is its own block, in year order.
    rows = load_manifest(engagement)
    rows.append(RequestItem(identifier="F01", document="Older thing", period="TY2024",
                            manual_override=Override.NOT_APPLICABLE))
    save_rules(engagement, rows, load_engagement_info(engagement))
    view.write_view(engagement)
    page = page_of(engagement)
    blocks = re.findall(r"<details><summary>(.*?)</summary>", page)
    assert blocks == [view.SET_ASIDE_SECTION.format(n=2)]
    assert re.findall(r"<h3>(.*?)</h3>", page) == [
        view.SET_ASIDE_GROUP.format(label="Not Applicable in TY2024", n=1),
        view.SET_ASIDE_GROUP.format(label="Not Applicable in TY2025", n=1),
    ]

    # With none set aside, no block at all.
    rows = [r for r in load_manifest(engagement) if r.manual_override != Override.NOT_APPLICABLE]
    save_rules(engagement, rows, load_engagement_info(engagement))
    view.write_view(engagement)
    assert "<details>" not in page_of(engagement)
    assert not_applicable_tables(engagement) == []


def test_the_override_reason_is_a_column_of_the_requests_table(engagement):
    from dataclasses import replace

    from tracker.manifest import (
        COL_MANUAL_OVERRIDE,
        COL_OVERRIDE_REASON,
        OVERRIDE_REASONS,
        load_engagement_info,
        save_rules,
    )

    rows = [replace(r, manual_override=Override.ACCEPTED, override_reason=OVERRIDE_REASONS[1])
            if r.identifier == "C01" else r for r in load_manifest(engagement)]
    save_rules(engagement, rows, load_engagement_info(engagement))
    view.write_view(engagement)

    table = requests_table(engagement)
    assert COL_OVERRIDE_REASON in table[0]
    by_identifier = {row[0]: dict(zip(view.REQUEST_COLUMNS, row, strict=True)) for row in table[1:]}
    assert by_identifier["C01"][COL_OVERRIDE_REASON] == OVERRIDE_REASONS[1]
    assert by_identifier["C01"][COL_MANUAL_OVERRIDE] == Override.ACCEPTED
    assert by_identifier["A01"][COL_OVERRIDE_REASON] == ""


def test_a_value_shaped_like_markup_is_shown_as_its_own_text(engagement):
    """A keyword somebody typed, and a client's file name, are names -
    whatever characters they carry. (The keyword carries the tag: Windows
    refuses a file name holding one, so the file carries an ampersand.)"""
    type_a_keyword(engagement, "C01", "<b>lender</b>")
    drop(engagement, "Smith & Co 1098.pdf", "Form 1098 Mortgage Interest Statement")
    a_pass(engagement)
    view.write_view(engagement)
    page = page_of(engagement)

    assert "<b>lender</b>" not in page
    assert "&lt;b&gt;lender&lt;/b&gt;" in page
    assert "&amp;" in page
    cells = [cell for table in tables(page) for row in table for cell in row]
    assert any("<b>lender</b>" in cell for cell in cells)
    assert any("Smith & Co 1098.pdf" in cell for cell in cells)


# ------------------------------------------------------------ needs review ----


def test_a_parked_file_carries_the_shortlist_the_app_would_show(engagement):
    """The same sentences, from the same function: one owner for the words."""
    drop(engagement, "both.pdf",
         "Form W-2 Wage and Tax Statement 2025 Form 1098 Mortgage Interest Statement")
    a_pass(engagement)
    view.write_view(engagement)
    page = page_of(engagement)

    triaged = review.triage(engagement, read_index(engagement))
    assert len(triaged) == 1 and triaged[0].shortlist
    assert review_table(engagement)[1:] == [
        [str(getattr(one.entry, name)) for name in view.NEEDS_REVIEW_FIELDS]
        for one in triaged
    ]
    said = [html.unescape(line) for line in re.findall(r"<li>(.*?)</li>", page)]
    assert said == [suggestion.reason for one in triaged for suggestion in one.shortlist]
    assert f"<h3>{html.escape(triaged[0].entry.original_name)}</h3>" in page


def test_a_parked_file_the_evidence_says_nothing_about_says_so(engagement):
    drop(engagement, "puzzle.pdf", "a page about nothing anybody asked for")
    a_pass(engagement)
    view.write_view(engagement)

    parked = [e for e in read_index(engagement) if e.decision == NEEDS_REVIEW]
    assert [e.original_name for e in parked] == ["puzzle.pdf"]
    assert f'<p class="nothing">{html.escape(review.NOTHING_SUGGESTED)}</p>' in page_of(engagement)


# --------------------------------------------------- one file, no fetching ----


def test_the_page_fetches_nothing_when_it_is_opened(engagement):
    """A page naming the firm's clients must not reach the network to
    render: no image, no style sheet, no font, and every link a place on
    the page itself."""
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    a_pass(engagement)
    view.write_view(engagement)
    page = page_of(engagement)

    assert "src=" not in page
    assert "://" not in page, "no address to fetch from"
    assert all(link.startswith("#") for link in re.findall(r'href="([^"]*)"', page))


def test_the_page_sorts_with_a_script_and_is_a_plain_table_without_one(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    a_pass(engagement)
    view.write_view(engagement)
    page = page_of(engagement)

    assert page.count("<script>") == 1
    assert 'data-sort=""' in page
    # The rows are in the markup, not built by the script: a parser that
    # runs nothing still reads every one of them.
    entries = read_index(engagement)
    without_script = page.split("<script>")[0]
    assert index_table(engagement)[1:] == [view.index_row(entry) for entry in entries]
    assert "</tbody>" in without_script and "<thead>" in without_script


# ---------------------------------------------------------------- the stamp ----


def test_the_head_carries_the_stamp_and_read_stamp_reads_it_back(engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    a_pass(engagement)
    view.write_view(engagement)
    page = page_of(engagement)

    stamp = view.read_stamp(engagement)
    assert set(stamp) == set(view.META_NAMES)
    for label, name in view.META_NAMES.items():
        assert f'<meta name="{name}" content="{html.escape(stamp[label])}">' in page
    assert stamp[view.LABEL_RECORD_DIGEST] == ledger.head(engagement)
    assert stamp[view.LABEL_ENGAGEMENT] == engagement.name
    assert stamp[view.LABEL_INDEX_ROWS] == "1"
    # The two times are one moment said twice, and the machine-readable one
    # is the UTC one.
    assert dt.datetime.fromisoformat(stamp[view.LABEL_GENERATED]).utcoffset() == dt.timedelta(0)
    # And a person reads the same values in the Summary.
    for label, value in stamp.items():
        assert f"<dt>{html.escape(label)}</dt>" in page
        assert f"<dd>{html.escape(value)}</dd>" in page


def test_the_stamp_changes_when_the_rules_change_and_when_the_record_grows(engagement):
    view.write_view(engagement)
    first = view.read_stamp(engagement)

    type_a_keyword(engagement, "C01", "lender")
    view.write_view(engagement)
    second = view.read_stamp(engagement)
    # A rules edit is an event (decision 104): the one stamp moves with it.
    assert second[view.LABEL_RECORD_DIGEST] != first[view.LABEL_RECORD_DIGEST]

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    a_pass(engagement)
    view.write_view(engagement)
    third = view.read_stamp(engagement)
    assert third[view.LABEL_RECORD_DIGEST] != second[view.LABEL_RECORD_DIGEST]


# ---------------------------------------------------------------- the state ----


def test_there_is_no_view_until_one_is_written(engagement):
    assert view.view_state(engagement) == view.UNKNOWN
    view.write_view(engagement)
    assert view.view_state(engagement) == view.CURRENT


def test_a_stamp_that_cannot_be_read_is_unknown_rather_than_believed(engagement):
    view.write_view(engagement)
    view.path_for(engagement).write_bytes(b"<html><head></head><body>hello</body></html>")
    assert view.view_state(engagement) == view.UNKNOWN


def test_the_view_is_behind_after_a_person_edits_the_rules_and_after_a_new_event(engagement):
    view.write_view(engagement)
    type_a_keyword(engagement, "C01", "lender")
    assert view.view_state(engagement) == view.BEHIND

    view.write_view(engagement)
    assert view.view_state(engagement) == view.CURRENT

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    a_pass(engagement)
    assert view.view_state(engagement) == view.BEHIND

    view.write_view(engagement)
    assert view.view_state(engagement) == view.CURRENT


# ------------------------------------------- a page that says the same (P210) ----


def _written(engagement, monkeypatch) -> list[Path]:
    """Every page write_view hands to the atomic writer from now on."""
    calls: list[Path] = []
    real = view.write_text_atomically

    def counted(path, text, **kwargs):
        calls.append(Path(path))
        return real(path, text, **kwargs)

    monkeypatch.setattr(view, "write_text_atomically", counted)
    return calls


def test_a_page_that_would_say_the_same_is_not_written_again(engagement, monkeypatch):
    """Every pass drew every return's page again only for its time, and
    Drive uploaded each one: a thousand uploads a pass at 1,000 returns."""
    first = view.write_view(engagement)
    before = view.path_for(engagement).read_bytes()
    calls = _written(engagement, monkeypatch)

    again = view.write_view(engagement)
    assert calls == [] and again.unchanged and not again.stale
    assert view.path_for(engagement).read_bytes() == before
    assert again.stamp == first.stamp, "the stamp is the page's own, generated time and all"
    assert view.view_state(engagement) == view.CURRENT


def test_a_page_with_anything_new_is_written(engagement, monkeypatch):
    view.write_view(engagement)
    calls = _written(engagement, monkeypatch)

    type_a_keyword(engagement, "C01", "lender")
    result = view.write_view(engagement)
    assert calls == [view.path_for(engagement)] and not result.unchanged
    assert view.view_state(engagement) == view.CURRENT

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    a_pass(engagement)
    assert not view.write_view(engagement).unchanged
    assert len(calls) == 2


def test_a_page_changed_by_hand_is_drawn_again(engagement, monkeypatch):
    """Only the page word for word is left: one edited, cut short or saved
    from a browser is drawn again."""
    view.write_view(engagement)
    path = view.path_for(engagement)
    path.write_text(path.read_text(encoding="utf-8") + "<!-- edited -->", encoding="utf-8")
    calls = _written(engagement, monkeypatch)

    assert not view.write_view(engagement).unchanged
    assert calls == [path] and "edited" not in path.read_text(encoding="utf-8")


def test_a_page_whose_time_cannot_be_read_is_drawn_again(engagement, monkeypatch):
    view.write_view(engagement)
    path = view.path_for(engagement)
    stamp = view.read_stamp(engagement)
    path.write_text(path.read_text(encoding="utf-8").replace(stamp[view.LABEL_GENERATED], "not a time"),
                    encoding="utf-8")
    calls = _written(engagement, monkeypatch)

    assert not view.write_view(engagement).unchanged
    assert calls == [path] and view.view_state(engagement) == view.CURRENT


def test_a_page_written_on_windows_compares_by_what_it_says(engagement, monkeypatch):
    """The atomic writer turns each line end into the system's, so a page
    written on Windows ends its lines in CRLF; it says the same."""
    view.write_view(engagement)
    path = view.path_for(engagement)
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    calls = _written(engagement, monkeypatch)

    assert view.write_view(engagement).unchanged and calls == []


def test_a_caller_that_names_the_time_gets_a_page_drawn_at_it(engagement, monkeypatch):
    view.write_view(engagement)
    calls = _written(engagement, monkeypatch)
    then = dt.datetime(2026, 7, 2, 12, 0, tzinfo=dt.UTC)

    result = view.write_view(engagement, now=then)
    assert calls == [view.path_for(engagement)] and not result.unchanged
    assert view.read_stamp(engagement)[view.LABEL_GENERATED] == then.isoformat(timespec="seconds")


def test_a_line_appended_while_the_page_is_drawn_leaves_it_stale_not_current(
    engagement, monkeypatch
):
    """Decision 152: the page's digest is the head read *before* its rows.

    A line the record gains after the readers have read - a pass recording
    while ``python -m tracker.view``, which takes no lock, draws - is not on
    the page, so the page must not name it: its digest is the head from
    before the line and ``view_state()`` calls it behind, never current.
    Both ways the page is drawn, the one written and the one rendered.
    """
    view.write_view(engagement)
    read_index = view.read_index

    def rows_then_a_line(engagement_dir):
        entries = read_index(engagement_dir)
        teach_a_keyword(engagement, "C01", "lender")     # the record moves on
        return entries

    monkeypatch.setattr(view, "read_index", rows_then_a_line)

    before = ledger.head(engagement)
    written = view.write_view(engagement)
    assert ledger.head(engagement) != before                 # the line did land
    assert written.stamp[view.LABEL_RECORD_DIGEST] == before
    assert view.read_stamp(engagement)[view.LABEL_RECORD_DIGEST] == before
    assert view.view_state(engagement) == view.BEHIND

    before = ledger.head(engagement)
    drawn = view.render_page(engagement)
    assert ledger.head(engagement) != before
    digest = f'<meta name="{view.META_NAMES[view.LABEL_RECORD_DIGEST]}" content="{before}">'
    assert digest in drawn


def test_a_page_drawn_on_a_quiet_record_is_current(engagement):
    """Decision 152: nothing appended while the page is drawn, and the head
    read first is the head now - the page is current, as it always was."""
    teach_a_keyword(engagement, "C01", "lender")
    written = view.write_view(engagement)
    assert written.stamp[view.LABEL_RECORD_DIGEST] == ledger.head(engagement)
    assert view.view_state(engagement) == view.CURRENT


# ------------------------------------------------------------ held open ----


def test_a_view_whose_replace_fails_is_reported_stale_and_the_pass_succeeds(
    engagement, monkeypatch, caplog
):
    """Everywhere: the replace fails, the old page stands, the run is fine."""
    view.write_view(engagement)
    before = view.path_for(engagement).read_bytes()

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    a_pass(engagement)

    def held(path, text, **kwargs):
        raise PermissionError(13, "The process cannot access the file")

    monkeypatch.setattr(view, "write_text_atomically", held)
    with caplog.at_level("WARNING"):
        result = view.write_view(engagement)

    assert result.stale
    assert view.path_for(engagement).read_bytes() == before
    assert engagement.name in caplog.text
    # And the reader can still say, truthfully, that it is out of date.
    assert view.view_state(engagement) == view.BEHIND


def test_a_pass_whose_view_cannot_be_replaced_reports_it_and_still_succeeds(
    tmp_path, engagement, monkeypatch
):
    from tracker import runner
    from tracker.registry import engagement_from

    view.write_view(engagement)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    def held(path, text, **kwargs):
        raise PermissionError(13, "The process cannot access the file")

    monkeypatch.setattr(view, "write_text_atomically", held)
    # The pass is the household's since decision 125 - one inbox feeds
    # every return of it - and this return's run is what it answers with.
    [run] = run_household(household_of(engagement), [engagement_from(engagement)], today=DAY1,
                          registry=discover_engagements(root_of(engagement)))

    assert run.ok and not run.error
    assert run.view_stale
    assert run.filed == 1
    assert runner.VIEW_NOT_REGENERATED in run.summary()


def test_a_page_somebody_is_reading_is_still_read_and_says_what_each_system_does(engagement):
    """The honest equivalent of the old Excel share-mode test.

    Nothing in the suite had ever shown what a held-open file really does
    to the replace; the workbook test held one the way Excel does. A
    browser is not Excel: it reads the page and lets go, so the file is
    normally free by the time the next pass comes. What is proved here is
    the case where it is not - an ordinary read handle, open - and the two
    file systems differ, so the test says which does what rather than
    skipping one.

    **Windows** refuses the replace while a plain ``open()`` handle is held
    (Python's ``open`` shares reading and writing, never deleting), so
    ``view_stale`` still has a real trigger there and the older page
    stands. **POSIX** replaces the name under the reader, which keeps its
    own open file. Either way ``view_state()`` answers while the handle is
    held, and the next pass with nothing holding it lands.
    """
    view.write_view(engagement)
    path = view.path_for(engagement)
    before = path.read_bytes()

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    a_pass(engagement)

    with path.open(encoding="utf-8") as reading:
        assert "<!doctype html>" in reading.read()      # somebody has it open
        assert view.view_state(engagement) == view.BEHIND   # a read, and it answers
        held = view.write_view(engagement)
        if sys.platform == "win32":
            assert held.stale
            assert path.read_bytes() == before          # not a byte of it moved
        else:
            assert not held.stale
            assert path.read_bytes() != before

    landed = view.write_view(engagement)
    assert not landed.stale
    assert path.read_bytes() != before
    assert view.view_state(engagement) == view.CURRENT


# ------------------------------------------------------ the pass and the app ----


def test_a_pass_regenerates_the_view_and_a_dry_run_writes_none(tmp_path, engagement):
    from tracker.registry import engagement_from

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    run_household(household_of(engagement), [engagement_from(engagement)],
                  today=DAY1, dry_run=True, registry=discover_engagements(root_of(engagement)))
    assert not view.path_for(engagement).exists()

    [run] = run_household(household_of(engagement), [engagement_from(engagement)], today=DAY1,
                          registry=discover_engagements(root_of(engagement)))
    assert not run.view_stale
    assert view.view_state(engagement) == view.CURRENT
    assert index_table(engagement)[1:] == [
        view.index_row(e) for e in read_index(engagement)
    ]


def test_a_pass_writes_no_workbook_for_a_person_to_open(engagement):
    """Decision 91: the file staff open is the page; since decision 104
    there is no workbook in the folder at all, the accountant's included."""
    from tracker.registry import engagement_from

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    run_household(household_of(engagement), [engagement_from(engagement)], today=DAY1,
                          registry=discover_engagements(root_of(engagement)))

    assert view.path_for(engagement).suffix == ".html"
    assert sorted(p.name for p in engagement.rglob("*.xlsx")) == []


def test_the_state_the_app_reads_carries_the_view_and_its_path(engagement):
    from tracker.api import _state, _vocab

    state = _state(engagement)
    assert state["view"] == {"state": view.UNKNOWN, "path": str(view.path_for(engagement))}
    assert state["paths"]["view"] == str(engagement / view.VIEW_FILENAME)

    view.write_view(engagement)
    assert _state(engagement)["view"]["state"] == view.CURRENT
    assert _vocab()["view"] == {"label": view.VIEW_LABEL, "open": view.VIEW_OPEN_LABEL,
                                "states": list(view.VIEW_STATES)}


# ------------------------------------------------------------- not a manifest ----


def test_the_registry_never_mistakes_the_view_for_an_engagement(tmp_path, engagement):
    """A folder holding only a view is not an engagement, and the rollover's
    prior-year discovery - the same walk - never offers one."""
    view.write_view(engagement)
    lonely = tmp_path / "Not An Engagement"
    lonely.mkdir()
    (lonely / view.VIEW_FILENAME).write_bytes(view.path_for(engagement).read_bytes())

    assert engagement_dirs(tmp_path) == [engagement]
    assert [e.path for e in discover_engagements(tmp_path).engagements] == [engagement]

    # And a root with nothing under it at all is a typo in the scheduled
    # task, not an empty practice.
    alone = tmp_path / "alone"
    alone.mkdir()
    with pytest.raises(RegistryError):
        discover_engagements(alone)


# -------------------------------------------------------------------- CLI ----


def test_the_cli_writes_the_view_and_prints_its_state_and_path(tmp_path):
    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    engagement = make_engagement(tmp_path / "root", ITEMS, household="Smith Family")
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    a_pass(engagement)

    out = subprocess.run(
        [sys.executable, "-m", "tracker.view", str(engagement)],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout

    assert view.path_for(engagement).is_file()
    assert str(view.path_for(engagement)) in out
    assert f"state:    {view.CURRENT}" in out
    assert view.LABEL_RECORD_DIGEST in out
    assert "rows:     1" in out


# --------------------------------------------- decision 142: accepted, not asked ----


def test_not_asked_rows_fold_away_until_a_document_arrives_and_then_sit_in_the_table_marked(tmp_path):
    """A row nobody asked for with nothing received folds into one block,
    "Not asked (N)", after the active table and before the set-aside ones,
    its status said as not asked rather than Missing. Once a document has
    arrived for it, it is real work: in the active table, classed not
    asked, showing its real status."""
    from dataclasses import replace

    from tracker.manifest import COL_ASKED, NOT_ASKED_LABEL, STATUS_LABELS

    rows = [ITEMS[0], replace(ITEMS[1], asked=False), ITEMS[2],
            RequestItem(identifier="G01", document="Property Tax", period="TY2025",
                        allowed_extensions=("pdf",), min_size_kb=0,
                        required_keywords=("property tax statement",), asked=False)]
    engagement = make_engagement(tmp_path, rows, household="Smith Family")
    a_pass(engagement)
    view.write_view(engagement)
    page = page_of(engagement)

    assert [row[0] for row in requests_table(engagement)[1:]] == ["A01"]
    blocks = re.findall(r"<details><summary>(.*?)</summary>", page)
    # One fold: the two rows nobody asked for, then ITEMS' set-aside row.
    assert blocks == [view.SET_ASIDE_SECTION.format(n=3)]
    assert re.findall(r"<h3>(.*?)</h3>", page)[0] == view.SET_ASIDE_GROUP.format(
        label=STATUS_LABELS[NOT_ASKED_LABEL].label, n=2)
    folded = not_applicable_tables(engagement)[0]
    by_id = {row[0]: dict(zip(view.REQUEST_COLUMNS, row, strict=True)) for row in folded[1:]}
    assert set(by_id) == {"C01", "G01"}
    assert {one[COL_STATUS] for one in by_id.values()} == {STATUS_LABELS[NOT_ASKED_LABEL].label}
    assert {one[COL_ASKED] for one in by_id.values()} == {"no"}

    drop(engagement, "1098.pdf", "Form 1098 Mortgage Interest Statement 2025")
    a_pass(engagement)
    view.write_view(engagement)
    page = page_of(engagement)
    active = {row[0]: dict(zip(view.REQUEST_COLUMNS, row, strict=True))
              for row in requests_table(engagement)[1:]}
    assert set(active) == {"A01", "C01"}
    assert active["C01"][COL_STATUS] == Status.RECEIVED and active["C01"][COL_ASKED] == "no"
    assert page.count(f'<tr class="{view.NOT_ASKED_CLASS}">') == 2        # C01 in the table, G01 folded
    assert re.findall(r"<details><summary>(.*?)</summary>", page) == [view.SET_ASIDE_SECTION.format(n=2)]
    assert "<h2>Requests (2)</h2>" in page


def test_a_not_asked_row_with_any_document_sits_in_the_active_table_and_only_one_with_none_folds(tmp_path):
    """The designer's ruling on the 142 build: a document of any status in a
    row nobody asked for - Received, Partial, Failed Validation or still
    syncing - is work for the preparer, so the row sits in the active table
    with its real status; only a row with no document at all folds, and
    only those are counted in the fold's N and ``Summary.not_asked``."""
    from tests.conftest import seed_statuses
    from tracker.manifest import STATUS_LABELS, StatusUpdate, is_idle_unasked, summarize

    def unasked(identifier):
        return RequestItem(identifier=identifier, document=f"Document {identifier}", period="TY2025",
                           allowed_extensions=("pdf",), min_size_kb=0,
                           required_keywords=(f"keyword {identifier.lower()}",), asked=False)

    rows = [ITEMS[0], unasked("B01"), unasked("B02"), unasked("B03"), unasked("B04"),
            unasked("B05"), unasked("B06")]
    engagement = make_engagement(tmp_path, rows, household="Smith Family", scaffold=False)
    seed_statuses(engagement, {
        "B01": StatusUpdate(status=Status.RECEIVED, file_count=1, received_date=DAY1),
        "B02": StatusUpdate(status=Status.PARTIAL, file_count=1),
        "B03": StatusUpdate(status=Status.FAILED, file_count=0, validation_notes="b03.pdf: refused"),
        "B04": StatusUpdate(status=Status.PENDING_SYNC, file_count=0),
        "B05": StatusUpdate(status=Status.MISSING, file_count=0),
    })
    view.write_view(engagement)
    page = page_of(engagement)

    active = {row[0]: dict(zip(view.REQUEST_COLUMNS, row, strict=True))
              for row in requests_table(engagement)[1:]}
    assert list(active) == ["A01", "B01", "B02", "B03", "B04"]
    assert [active[i][COL_STATUS] for i in ("B01", "B02", "B03", "B04")] == [
        STATUS_LABELS[word].label
        for word in (Status.RECEIVED, Status.PARTIAL, Status.FAILED, Status.PENDING_SYNC)]
    [folded] = not_applicable_tables(engagement)
    assert [row[0] for row in folded[1:]] == ["B05", "B06"]
    assert re.findall(r"<details><summary>(.*?)</summary>", page) == [view.SET_ASIDE_SECTION.format(n=2)]

    items = load_manifest(engagement)
    assert [i.identifier for i in items if is_idle_unasked(i)] == ["B05", "B06"]
    summary = summarize(items)
    assert summary.not_asked == 2 and summary.also_received == 2


# ------------------------------------------ decision 159: who wrote the last line ----


def test_current_names_the_host_that_wrote_the_last_line(engagement):
    """D-7: "current" says the page is fresh; the Summary now says whose
    line it is fresh to - the host and the time the record's last line
    carries, and whether the pass or a person decided it. A last line from
    before 159 says it recorded no writer."""
    from tests.conftest import written_elsewhere
    from tracker.locking import this_host

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=dt.date(2026, 7, 1))
    written = view.write_view(engagement)
    last = ledger.read_events(engagement)[-1]
    said = written.stamp[view.LABEL_LAST_WRITTEN]
    assert said.startswith(f"on {this_host()} {last[ledger.AT_KEY]} by ")
    assert view.view_state(engagement) == view.CURRENT
    assert html.escape(said) in view.path_for(engagement).read_text(encoding="utf-8")

    written_elsewhere(engagement, ledger.new(ledger.RELEASED, **{
        ledger.KEY_KEY: "nothing", ledger.REASON_KEY: "x", ledger.DECIDED_BY_KEY: ledger.BY_PERSON}),
        host="laptop-2")
    assert view.last_written(ledger.read_events(engagement)[-1]).startswith("on laptop-2 ")
    assert view.last_written(ledger.read_events(engagement)[-1]).endswith(" by a person")
    assert view.last_written({ledger.EVENT_KEY: ledger.SCANNED, ledger.AT_KEY: "2026-01-01"}) \
        == view.LAST_WRITTEN_UNKNOWN
    assert view.last_written(None) == view.LAST_WRITTEN_NOTHING
    assert view.META_NAMES[view.LABEL_LAST_WRITTEN] == "tracker-last-written"


@pytest.mark.parametrize("host, at", [
    ("PLANTED/Fabricated-Name.pdf", "2026-03-02T11:00:00Z"),
    ("office-pc", "Fabricated Client, SSN 000-00-0000"),
], ids=["a-writer-that-is-not-a-name", "a-time-that-is-not-one"])
def test_the_summary_names_a_writer_only_inside_the_gates_rule(host, at):
    """The view reads the record's last line itself, not through the
    store's admission (decision 187), so it asks the admission's two rules
    before it shows a writer or a time: nothing a line carries is echoed."""
    from tracker import ledger
    from tracker.view import LAST_WRITTEN_UNKNOWN, last_written

    said = last_written({ledger.EVENT_KEY: ledger.FILED, ledger.HOST_KEY: host, ledger.AT_KEY: at})
    assert said == LAST_WRITTEN_UNKNOWN and "Fabricated" not in said


# ------------------------------- statuses in a preparer's words (d200) ----


def test_a_badge_shows_the_label_and_is_classed_by_the_record_word():
    """The page says a preparer's word; its colour stays keyed by the
    record's word, so no colour moves with a label."""
    from tracker.manifest import STATUS_LABELS

    row = view._request_cells(RequestItem(identifier="A01", document="W-2", period="TY2025",
                                          status=Status.MISSING))
    [cell] = [value for header, value in zip(view.REQUEST_COLUMNS, row.values, strict=True)
              if header == COL_STATUS]
    assert cell.value == STATUS_LABELS[Status.MISSING].label == "Outstanding"
    assert cell.class_name == "badge badge-missing"


def test_the_status_report_has_one_set_aside_fold_with_a_group_per_sub_label():
    """Decision 200: every row nobody waits on is under one Set aside fold,
    one group per label - Not asked first, then each year oldest first -
    each group followed by its label's sentence."""
    from tracker.manifest import NOT_ASKED_LABEL, STATUS_LABELS

    rows = [
        RequestItem(identifier="A01", document="W-2", period="TY2025"),
        RequestItem(identifier="B01", document="1099-C", period="TY2025", asked=False),
        RequestItem(identifier="C01", document="1095-A", period="TY2025",
                    manual_override=Override.NOT_APPLICABLE),
        RequestItem(identifier="C02", document="1098-T", period="TY2024",
                    manual_override=Override.NOT_APPLICABLE),
    ]
    drawn = "\n".join(view._set_aside_block(rows))
    assert re.findall(r"<details><summary>(.*?)</summary>", drawn) == [view.SET_ASIDE_SECTION.format(n=3)]
    groups = [
        (view.SET_ASIDE_GROUP.format(label=STATUS_LABELS[NOT_ASKED_LABEL].label, n=1), STATUS_LABELS[NOT_ASKED_LABEL].sentence),
        (view.SET_ASIDE_GROUP.format(label="Not Applicable in TY2024", n=1),
         STATUS_LABELS[Override.NOT_APPLICABLE].sentence),
        (view.SET_ASIDE_GROUP.format(label="Not Applicable in TY2025", n=1),
         STATUS_LABELS[Override.NOT_APPLICABLE].sentence),
    ]
    assert re.findall(r'<h3>(.*?)</h3>\n<p class="stamp">(.*?)</p>', drawn) == [
        (html.escape(heading), html.escape(sentence)) for heading, sentence in groups]
    assert "A01" not in drawn
    assert view._set_aside_block(rows[:1]) == []
