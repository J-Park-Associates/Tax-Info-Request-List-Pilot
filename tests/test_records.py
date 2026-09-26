"""Tests for tracker/records.py - the records, apart from what writes them.

The claims here are the whole of what this module owes anyone. The
index's columns are its record's fields, in order. A row survives being
written down and read back, field for field. The Evidence cell survives the
same trip with several candidates and several places in it. And the move
itself cost nobody anything: every name a module used to own resolves, from
that module, to the very object this one defines - the same object, not a
copy - and this module reaches for nothing in the package to do any of it.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import fields
from pathlib import Path

import pytest

from tests.test_layers import import_edges
from tracker import content_check, filer, ledger, manifest, records, router
from tracker.records import (
    CANDIDATE_SEP,
    ENGAGEMENT_FIELDS,
    ENGAGEMENT_HELP,
    ENGAGEMENT_LABELS,
    EVIDENCE_PLACES,
    EVIDENCE_RULES,
    INDEX_COLUMNS,
    INDEX_LAYOUT,
    RULE_ANY,
    RULE_REQUIRED,
    WHERE_DEEP,
    WHERE_TITLE,
    EngagementInfo,
    Evidence,
    IndexEntry,
    entry_from_json,
    entry_to_json,
    format_evidence,
    ledger_key,
    parse_evidence,
)

#: One row with every field filled and nothing defaulted, including the two
#: cells decision 94 added, so a round trip that drops one is seen.
A_ROW = IndexEntry(
    received="2026-01-14",
    original_name="scan0031.pdf",
    size_kb=9.4,
    digest="dd7d" * 16,
    identifier="A01",
    prepared_location="Prepared/A01 - W-2 Wage Statements - TY2025.pdf",
    pbc_location="../../../../Clients/Smith Family/2025/scan0031.pdf",
    decision="Filed",
    reason="names several forms",
    candidates=CANDIDATE_SEP.join(("A01", "A02")),
    evidence=format_evidence({
        "A01": (Evidence(RULE_REQUIRED, "W-2", WHERE_TITLE, 1),),
        "A02": (Evidence(RULE_ANY, "interest", WHERE_DEEP, 4),),
    }),
    also_filed="Prepared/A02 - 1099-INT Interest Income - TY2025.pdf",
)


# -------------------------------------------------------------- the layout ----


def test_the_index_layout_names_exactly_the_rows_fields_in_order():
    """The fields ARE the columns: a field added without a header would be
    written into no column at all, and a header with no field would move
    every value to its right one cell over."""
    assert tuple(INDEX_LAYOUT) == tuple(f.name for f in fields(IndexEntry))
    assert INDEX_COLUMNS == tuple(header for header, _ in INDEX_LAYOUT.values())
    assert len(set(INDEX_COLUMNS)) == len(INDEX_COLUMNS), "two columns share a header"


def test_the_identifier_column_is_the_one_the_manifest_asks_for():
    """The index is joined back to the request list by that header, so the
    two tables spell it once between them."""
    assert INDEX_LAYOUT["identifier"][0] is manifest.COL_IDENTIFIER
    assert manifest.HEADERS[0] is records.COL_IDENTIFIER


# --------------------------------------------------------- the round trips ----


def test_a_row_round_trips_through_the_json_helpers_field_for_field():
    """What the sidecar and the record store is what comes back: the row a
    client's original is recorded under must survive being written down."""
    again = entry_from_json(entry_to_json(A_ROW))

    assert again == A_ROW
    assert again.as_row() == A_ROW.as_row()
    assert entry_to_json(A_ROW) == {f.name: getattr(A_ROW, f.name) for f in fields(IndexEntry)}
    assert ledger_key(again) == ledger_key(A_ROW) == A_ROW.pbc_location


def test_a_stored_row_from_a_later_version_is_read_and_not_thrown_away():
    """A key this version does not know costs the row nothing: a row for an
    original already moved is never dropped over a column added later."""
    stored = entry_to_json(A_ROW) | {"something_later": "kept by a newer version"}

    assert entry_from_json(stored) == A_ROW


def test_the_evidence_cell_round_trips_two_candidates_and_two_places():
    """One Excel cell carries every candidate's evidence, and the reader is
    the writer's own: a person filing a parked row reads it back exactly."""
    record = {
        "A01": (Evidence(RULE_REQUIRED, "W-2", WHERE_TITLE, 1),
                Evidence(RULE_ANY, "wage", WHERE_DEEP, 3)),
        "C01": (Evidence(RULE_REQUIRED, "1098", WHERE_TITLE, 1),
                Evidence(RULE_ANY, "mortgage interest", WHERE_DEEP, 2)),
    }

    assert parse_evidence(format_evidence(record)) == record
    assert A_ROW.evidence_record == parse_evidence(A_ROW.evidence)
    assert set(A_ROW.evidence_record) == set(A_ROW.candidate_list)


def test_every_rule_and_place_is_in_the_list_that_names_them():
    """The two lists are the app's vocabulary; a value named nowhere would
    reach a screen with no word for it."""
    assert set(EVIDENCE_RULES) == {RULE_REQUIRED, RULE_ANY, records.RULE_DATE,
                                   records.RULE_FILENAME, records.RULE_REFUSED,
                                   records.RULE_NAME}
    assert set(EVIDENCE_PLACES) == {WHERE_TITLE, records.WHERE_FIRST_PAGE,
                                    records.WHERE_FOOTER, WHERE_DEEP}


# ------------------------------------------------------------ the engagement ----


def test_the_date_fields_are_the_two_dates_and_both_round_trip_through_json():
    """Decision 117: which details are dates is said once here, and the
    record's own serialisers read that list rather than naming a field -
    so a date added to the details is stored and read back without a
    second edit, and one nobody set comes back as nothing."""
    import datetime as dt

    from tracker.records import DATE_FIELDS, EngagementInfo, info_from_json, info_to_json

    typed = {f.name for f in fields(EngagementInfo) if f.type == "dt.date | None"}
    assert set(DATE_FIELDS) == typed == {"due", "filing_deadline"}

    info = EngagementInfo(client="Dana", due=dt.date(2026, 4, 10),
                          filing_deadline=dt.date(2026, 4, 15))
    stored = info_to_json(info)
    assert stored["due"] == "2026-04-10" and stored["filing_deadline"] == "2026-04-15"
    assert info_from_json(stored) == info
    assert info_from_json({"client": "Dana"}) == EngagementInfo(client="Dana")


def test_the_engagement_labels_name_exactly_the_engagement_records_fields():
    """The details are shown and edited by label, so a field with no label
    is a value nobody sees and a label with no field is a box nobody reads."""
    names = tuple(f.name for f in fields(EngagementInfo))

    assert tuple(field for _, field in ENGAGEMENT_FIELDS) == names
    assert set(ENGAGEMENT_LABELS) == set(names)
    assert set(ENGAGEMENT_HELP) == set(names), "every cell says what it is for"
    assert len(set(ENGAGEMENT_LABELS.values())) == len(names), "two fields share a label"


# ------------------------------------------------------------- the move itself ----

#: module -> the names it used to own, each of which must still resolve to
#: this module's object. Written out rather than derived: the point of the
#: re-exports is that these exact names go on working, and a list computed
#: from the modules would pass whatever they happen to say today.
RE_EXPORTED = {
    filer: ("IndexEntry", "ledger_key",
            "Evidence", "format_evidence", "parse_evidence"),
    content_check: ("Evidence", "EVIDENCE_RULES", "EVIDENCE_PLACES",
                    "RULE_REQUIRED", "RULE_ANY", "RULE_DATE", "RULE_FILENAME", "RULE_REFUSED",
                    "WHERE_TITLE", "WHERE_FIRST_PAGE", "WHERE_FOOTER", "WHERE_DEEP",
                    "format_evidence", "parse_evidence"),
    router: ("Routing", "EVIDENCE_CONTENT"),
    # The manifest's copies of the details' field table and the yes/no
    # words went with decision 104: nothing read them from there.
    manifest: ("StatusUpdate", "EngagementInfo", "COL_IDENTIFIER"),
}


def test_every_name_a_module_re_exports_is_this_modules_own_object():
    """`from tracker.filer import IndexEntry` still gives the class this
    module defines - the same object, so an isinstance check, a pickle and
    a dataclass comparison cannot tell the two import paths apart."""
    for module, names in RE_EXPORTED.items():
        for name in names:
            assert hasattr(module, name), f"{module.__name__} no longer offers {name}"
            assert getattr(module, name) is getattr(records, name), f"{module.__name__}.{name}"


def test_the_filers_old_private_separator_is_the_records_own():
    """The one moved name that kept its underscore, because the app and the
    tests still ask the filer for it."""
    assert filer._CANDIDATE_SEP is CANDIDATE_SEP


def test_the_records_import_nothing_of_the_package_but_the_layouts_name_rule():
    """The whole point of the module: a layer above may name a record
    without loading the machinery that writes it. `tests/test_layers.py`
    pins the direction of every edge; this names this one. Since decision
    188 the Windows character and device rule is the layout's, which reads
    no file, and the record imports it from there."""
    load, call = import_edges()

    assert load["records"] == {"layout"}, load["records"]
    assert call["records"] == set(), call["records"]
    assert "records" in load["manifest"], "the manifest names the shapes it loads"


def test_nothing_here_reaches_a_file_or_a_workbook():
    """A record knows nothing about where it is stored. The imports say so:
    no openpyxl, no os, `pathlib` only because a Routing names a path,
    `re` only because as_pattern() turns a sentence's template into the
    pattern that reads it back (decision 109), and `json` only because the
    return's people come back as JSON text from the one column that holds
    them (decision 128) - reading a value is not knowing where it lives.
    `math` and `re._parser` are the value rule's (decision 187): a count is
    finite, and a Date Pattern's shape is read off the standard library's
    own parser rather than a second engine. `tracker.layout` is the Windows
    name rule's (decision 188), and it reads no file either."""
    source = (Path(records.__file__)).read_text(encoding="utf-8")
    imported = {line.split()[1] for line in source.splitlines()
                if line.startswith("import ") or line.startswith("from ")}

    assert imported == {"__future__", "datetime", "dataclasses", "json", "math", "pathlib", "re",
                        "re._parser", "tracker.layout"}, imported
    assert isinstance(records.EngagementInfo().due, type(None))
    assert EngagementInfo(due=dt.date(2026, 4, 15)).due.year == 2026


def test_as_pattern_reads_a_templates_own_sentence_back():
    """Decision 109 moved this down here from the scanner, where it had read
    the regression sentence back since 108. The claim is the one both
    readers rest on: a pattern built from a template matches exactly what
    that template writes, whatever the detail is - a path with brackets, a
    date, a count - and the words are never retyped on either side."""
    from tracker.records import as_pattern

    template = "{home} no longer holds this row's bytes; they are at {now} (found {date})"
    pattern = re.compile(as_pattern(
        template, home=r".+?", now="(?P<now>.+?)", date=r"\d{4}-\d{2}-\d{2}") + "$")
    now = "Prepared/C01 - w2 (2).pdf"
    said = template.format(home="Prepared/A01 - W-2 - TY2025.pdf", now=now,
                           date="2026-07-09")

    assert pattern.search(said).group("now") == now
    assert pattern.search(said.replace("(found", "(seen")) is None   # not this template
    # Every word between the placeholders is escaped, so a template that
    # holds a regular expression's own characters is still itself.
    assert re.fullmatch(as_pattern("a (b) c {n}", n=r"\d+"), "a (b) c 12")


def test_the_also_answers_cell_reads_back_as_it_was_written():
    """d146. The requests a consolidated statement answers, and the sections
    that answered each, survive the cell: one per section, one where a
    phrase answered, and an empty cell answers nothing."""
    from tracker.records import answer_count, format_answers, parse_answers

    answers = (("A02", ("1099-int", "1099-div")), ("B02", ()))
    cell = format_answers(answers)
    assert cell == "A02 (1099-int, 1099-div); B02"
    assert parse_answers(cell) == answers
    assert [answer_count(one) for one in answers] == [2, 1]
    assert parse_answers("") == () and format_answers(()) == ""
    assert IndexEntry(received="", original_name="x.pdf", size_kb=1, digest="", identifier="E01",
                      prepared_location="", pbc_location="", decision="Filed", reason="",
                      answers=cell).answered == answers


# Decision 187: the value rule, worded once here, for the editor and the gate.


def test_a_nested_or_alternating_repetition_is_not_a_date_pattern():
    """The shape rule is read off the standard library's own parser: a
    repetition that can repeat more than once may hold no other such
    repetition, no alternation and no back-reference, at any depth; at most
    three of them, one open-ended, the rest at most twenty."""
    refused = {
        r"(\d+)+x": records.DATE_PATTERN_NESTED,
        r"(?:(?:\d{1,4}\s)*)x": records.DATE_PATTERN_NESTED,
        r"(?:Dec|12)+": records.DATE_PATTERN_ALTERNATES,
        r"(\d)(?:\1x)+": records.DATE_PATTERN_REFERS_BACK,
        r"\d{1,2}\d{1,2}\d{1,2}\d{1,2}": records.DATE_PATTERN_TOO_MANY,
        r"\d*-\d*": records.DATE_PATTERN_TOO_OPEN,
        r"\d{0,21}": records.DATE_PATTERN_TOO_WIDE,
        "x" * (records.DATE_PATTERN_MAX + 1): records.DATE_PATTERN_TOO_LONG,
        "([unclosed": records.DATE_PATTERN_NOT_A_REGEX,
        5: records.TEXT_BOUNDS,
    }
    for pattern, phrase in refused.items():
        assert records.date_pattern_problem(pattern) == phrase, pattern
    for fine in [r"(?i)\b2025\b", r"\d+/\d{1,2}/2025", r"(?:Dec|12)\s?2025", r"0?1/[0-3]?[0-9]/2025",
                 r"(?:Dec|12)?\s?2025", r"\d{0,20}x\d{0,20}y"]:
        assert records.date_pattern_problem(fine) == "", fine


def test_every_derived_date_pattern_passes_the_shape_rule():
    """The flag that marks a pattern derived is the record's claim, so a
    derived pattern is held to the same rule - and every one the Period
    derives passes it."""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    periods = [f"{month} {year}" for month in months for year in (2025, 2099)] + ["TY2025", "TY1900"]
    for period in periods:
        pattern = manifest.derived_date_pattern(period)
        assert pattern, period
        assert records.date_pattern_problem(pattern) == "", period


def test_a_flag_is_true_false_zero_or_one_and_nothing_else():
    for fine in (True, False, 0, 1):
        assert records.flag_problem(fine) == ""
    for refused in ("no", "yes", "false", 2, 1.0, None, [], ""):
        assert records.flag_problem(refused) == records.FLAG_BOUNDS, refused


def test_a_count_past_its_bound_is_refused_by_one_phrase():
    phrase = records.COUNT_BOUNDS.format(minimum=records.MIN_EXPECTED_COUNT,
                                         maximum=records.MAX_EXPECTED_COUNT)
    for refused in (10**20, "3", 0, records.MAX_EXPECTED_COUNT + 1, 2.5, True, float("inf"),
                    float("nan"), None):
        assert records.count_problem(refused, records.MIN_EXPECTED_COUNT,
                                     records.MAX_EXPECTED_COUNT) == phrase, refused
    assert records.count_problem(3, records.MIN_EXPECTED_COUNT, records.MAX_EXPECTED_COUNT) == ""
    assert records.count_problem(3.0, records.MIN_EXPECTED_COUNT, records.MAX_EXPECTED_COUNT) == ""
    assert records.rule_row_problem({"expected_count": 10**20}) == f"'expected_count' {phrase}"
    assert records.date_problem("2025-02-30") == records.DATE_BOUNDS
    assert records.date_problem("13/45/2025") == records.DATE_BOUNDS
    assert records.date_problem("2025-02-28") == ""
    assert records.stamp_problem(12345) == records.STAMP_BOUNDS
    assert records.stamp_problem("2025-02-28T10:00:00Z") == ""
    assert records.digest_problem(5) == records.DIGEST_BOUNDS
    assert records.digest_problem("a" * 64) == records.digest_problem("") == ""
    assert records.text_problem("two\nlines") == records.TEXT_BOUNDS
    assert records.text_problem("two\nlines", long=True) == ""
    assert records.text_problem("nul\x00", long=True) == records.LONG_TEXT_BOUNDS


def test_the_editors_checks_are_the_records_own_objects():
    """The editor re-exports each check it used to define: the same object,
    not a copy, so the editor and the gate can never hold two rules."""
    for name in ("YEAR_MIN", "YEAR_MAX", "YEAR_OUT_OF_RANGE", "WINDOWS_ILLEGAL_CHARS",
                 "WINDOWS_ILLEGAL_CHARS_TEXT", "WINDOWS_RESERVED_NAMES", "WINDOWS_RESERVED_NAMES_TEXT",
                 "is_reserved_name", "identifier_problem", "SHORT_TITLE_MAX", "short_title_problem",
                 "Override", "MIN_EXPECTED_COUNT", "MIN_SIZE_KB_FLOOR"):
        assert getattr(manifest, name) is getattr(records, name), name


def test_an_optional_chain_is_not_a_date_pattern():
    """The review's M1: an optional is a choice point too. ``\\d?`` twenty
    times over a line of digits backtracks without end though no single
    part repeats more than once, so every variable repetition counts -
    ``?`` included - for nesting and for the budget, and the ways one line
    may be tried are held to the measured 0.22 s case."""
    assert records.date_pattern_problem(r"\d?" * 20 + "x") == records.DATE_PATTERN_TOO_MANY_OPTIONAL
    assert records.date_pattern_problem(r"\d?" * 60 + "x") == records.DATE_PATTERN_TOO_MANY_OPTIONAL
    assert records.date_pattern_problem(r"(?:\d?){20}x") == records.DATE_PATTERN_NESTED
    assert records.date_pattern_problem(r"\d*\d{0,20}\d{0,20}\d?x") == records.DATE_PATTERN_TOO_MANY_WAYS
    assert records.date_pattern_problem(r"\d?" * 8 + "x") == ""
    assert records.date_pattern_problem(r"\d*\d{0,20}\d{0,20}x") == records.DATE_PATTERN_TOO_MANY_WAYS
    assert records.DATE_PATTERN_VARIABLE_MAX == 8 and records.DATE_PATTERN_OPEN_MAX == 1


def test_a_stamp_is_the_one_form_the_ledger_writes_from_the_epoch():
    """The review's S1: ``ledger.stamp`` has only ever written one form, and
    Windows cannot give a time before 1970 its local day."""
    assert records.stamp_problem(ledger.stamp()) == ""
    for refused in ("1900-01-01T00:00:00Z", "2025-W01-1", "20250101T000000", "2025-01-01T00:00:00",
                    "2025-01-01T00:00:00+00:00", 12345):
        assert records.stamp_problem(refused) == records.STAMP_BOUNDS, refused


def test_a_files_own_name_is_refused_only_for_a_nul_or_its_length():
    """The review's M5: decision 104 files a POSIX name holding a control
    character, so a name, a key or a location a real file gave is held only
    to what no path can hold; a label a person types keeps the one-line rule."""
    assert records.name_problem("w2\x01.pdf") == ""
    assert records.name_problem("w2\x00.pdf") == records.NAME_BOUNDS
    assert records.name_problem("x" * (records.TEXT_MAX + 1)) == records.NAME_BOUNDS
    assert records.entry_problem({"original_name": "w2\x01.pdf",
                                  "pbc_location": "../../../../Clients/H/2025/w2\x01.pdf"}) == ""
    assert records.text_problem("w2\x01") == records.TEXT_BOUNDS


#: The re-check's timing corpus (decision 187's review, M1a and M1b): each
#: took from 0.7 s to a minute on one 500-character line under the rule it
#: broke, and each is refused now.
RUNAWAYS = [
    "(?:" + "(?:1|11)" * 23 + "){1}x",                  # a {1} wrapper hid the chain: 60 s at k=22
    "(?:1|11)" * 17 + "x",                              # an alternation chain: 1.6 s
    "(?:1|11|111)" * 11 + "x",
    r"\d+\d{0,20}\d{0,20}\D",                           # no literal ending to short-cut: 0.85 s
    r"\d+\d{0,20}\d{0,20}\s",
    r"\d{0,20}" * 3 + r"\d?" * 4 + "x",
    r"\d{0,20}" * 3 + "(?:1|11)" * 4 + "x",
]


@pytest.mark.parametrize("pattern", RUNAWAYS)
def test_a_once_wrapped_alternation_is_counted(pattern):
    """Ways are counted through every repetition - a fixed ``{1}`` too - and
    an alternation's branches add, so no wrapping hides a chain, and the
    limit is the one measured on lines with no literal ending."""
    assert records.date_pattern_problem(pattern) == records.DATE_PATTERN_TOO_MANY_WAYS
    assert records.DATE_PATTERN_WAYS_MAX == 16_384


def test_an_optional_alternation_is_a_date_pattern():
    """A plain optional may hold an alternation (the re-check's ruling): its
    ways are counted like any other, and ``(?:Dec|12)?`` tries three. Only a
    repetition that can repeat more than once may not hold one. The common
    patterns a person types all pass."""
    for common in [r"(?:Dec|12)?", r"12/31/20\d\d", r"20(24|25)", r"Q[1-4]",
                   r"(0[1-9]|1[0-2])/\d{2}/\d{4}", r"Dec(ember)?\s+31", r"(?:Dec|12)?/31/2025",
                   r"(?:Q4|4th Quarter)?\s*2025", r"\d{1,2}/\d{1,2}/\d{2,4}"]:
        assert records.date_pattern_problem(common) == "", common
    assert records.date_pattern_problem(r"(?:Dec|12){0,2}") == records.DATE_PATTERN_ALTERNATES


def test_every_period_form_derives_a_pattern_the_rule_admits():
    """As the re-check generated them: every year 1900-2100 with TY, FY, a
    bare year and every month's abbreviation and full name, in four
    spellings. None is refused, and none is tried more than 176 ways."""
    forms = [*manifest._MONTHS, *manifest._MONTH_NAMES, "TY", "FY", ""]
    most = 0
    for year in range(1900, 2101):
        for head in forms:
            for period in (f"{head} {year}", f"{head}{year}", f"{head.upper()} {year}", f"{head}  {year}"):
                pattern = manifest.derived_date_pattern(period)
                if pattern:
                    assert records.date_pattern_problem(pattern) == "", period
                    most = max(most, records._ways(records._re_parser.parse(pattern)))
    assert most <= 176


#: The second re-check's table (decision 187's review, M1c): a fixed-count
#: repetition adds no way and hundreds of characters of matching to each -
#: from 0.72 s to 15 s on one 500-character line under the ways rule alone.
COSTLY = [
    "(?:1|11)" * 14 + r"(?:\d\d){200}\D",
    "(?:1|11)" * 13 + r"(?:\d\d){200}\D",
    r"\d{0,20}" * 3 + r"(?:\d\d){200}\D",
    r"\d+\d{0,20}(?:\d\d){150}\D",
    "(?:1|11)?" * 8 + r"(?:\d\d){200}\D",
    "(?:1|11)" * 13 + r"\w{400}\D",
    "(?:1|11)" * 13 + r"\d{300}\D",
    "(?:1|11)?" * 8 + r"\d{300}\D",
    "(?:1|11)" * 13 + r"(?=\d{400})\D",
    r"\d{0,20}" * 3 + r"\d{400}\D",
]


@pytest.mark.parametrize("pattern", COSTLY)
def test_a_fixed_count_of_matching_is_counted_in_the_cost(pattern):
    """A pattern's cost is its ways times the widest match of its bounded
    parts - a fixed ``{n}`` and a lookaround included - and one over
    200,000 is refused."""
    assert records.date_pattern_problem(pattern) == records.DATE_PATTERN_TOO_COSTLY
    assert records.DATE_PATTERN_COST_MAX == 200_000


def test_every_derived_and_common_pattern_is_within_the_cost():
    """Every pattern the Period derives costs at most 6,688, and the ten
    common hand-typed patterns pass the cost rule too."""
    most = 0
    for year in range(1900, 2101):
        for head in [*manifest._MONTHS, *manifest._MONTH_NAMES, "TY", "FY"]:
            pattern = manifest.derived_date_pattern(f"{head} {year}")
            if pattern:
                parsed = records._re_parser.parse(pattern)
                most = max(most, records._ways(parsed) * records._width(parsed))
                assert records.date_pattern_problem(pattern) == "", pattern
    assert most <= 6_688
    for common in [r"(?:Dec|12)?", r"12/31/20\d\d", r"20(24|25)", r"Q[1-4]",
                   r"(0[1-9]|1[0-2])/\d{2}/\d{4}", r"Dec(ember)?\s+31", r"(?:Dec|12)?/31/2025",
                   r"(?:Q4|4th Quarter)?\s*2025", r"\d{1,2}/\d{1,2}/\d{2,4}", r"(?:12/31|Dec(?:ember)?\s+31)"]:
        assert records.date_pattern_problem(common) == "", common


def test_a_zero_width_assertion_counts_toward_the_width():
    """The third re-check: ``\\B`` matches nothing yet is a test at every
    step, so a fixed group padded with thirty of them did unbounded work per
    counted character - 14.4 s on one 500-digit line. Every zero-width
    assertion counts one toward the width."""
    padded = "(?:1|11)?" * 7 + "(?:" + r"\B" * 30 + r"\d){35}\D"
    assert records.date_pattern_problem(padded) == records.DATE_PATTERN_TOO_COSTLY
    for assertion in (r"\b", r"\B", "^", "$", r"\A", r"\Z"):
        assert records._width(records._re_parser.parse(assertion)) == 1, assertion
