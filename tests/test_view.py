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

from tests.conftest import make_engagement
from tests.test_scanner import text_pdf
from tracker import ledger, review, view
from tracker.filer import NEEDS_REVIEW, file_drops, read_index
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
from tracker.runner import run_engagement
from tracker.scaffold import SHARED_DIR_NAME
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
    return make_engagement(tmp_path / "Smith Family 2025", ITEMS)


def drop(engagement, name, text):
    return text_pdf(engagement / SHARED_DIR_NAME / name, text)


def a_pass(engagement, today=DAY1):
    """What a pass does to the folder, without a registry: sort, then scan."""
    file_drops(engagement, today=today)
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
    heading = view.NOT_APPLICABLE_SECTION.format(label="Not Applicable in TY2025", n=1)
    assert f"<details><summary>{html.escape(heading)}</summary>" in page
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
    assert blocks == [
        view.NOT_APPLICABLE_SECTION.format(label="Not Applicable in TY2024", n=1),
        view.NOT_APPLICABLE_SECTION.format(label="Not Applicable in TY2025", n=1),
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
    assert "http" not in page
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
    run = run_engagement(engagement_from(engagement), today=DAY1)

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
    run_engagement(engagement_from(engagement), today=DAY1, dry_run=True)
    assert not view.path_for(engagement).exists()

    run = run_engagement(engagement_from(engagement), today=DAY1)
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
    run_engagement(engagement_from(engagement), today=DAY1)

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

    alone = tmp_path / "alone"
    (alone / "Client 2025").mkdir(parents=True)
    (alone / "Client 2025" / view.VIEW_FILENAME).write_bytes(b"not a manifest")
    with pytest.raises(RegistryError):
        discover_engagements(alone)


# -------------------------------------------------------------------- CLI ----


def test_the_cli_writes_the_view_and_prints_its_state_and_path(engagement):
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
