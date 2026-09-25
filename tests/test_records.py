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

from tests.test_layers import import_edges
from tracker import content_check, filer, manifest, records, router
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
    prepared_location="Prepared/A01 - W-2 Wage Statements/A01 - W-2 Wage Statements - TY2025.pdf",
    pbc_location="../../../../Clients/Smith Family/2025/scan0031.pdf",
    decision="Filed",
    reason="names several forms",
    candidates=CANDIDATE_SEP.join(("A01", "A02")),
    evidence=format_evidence({
        "A01": (Evidence(RULE_REQUIRED, "W-2", WHERE_TITLE, 1),),
        "A02": (Evidence(RULE_ANY, "interest", WHERE_DEEP, 4),),
    }),
    also_filed="Prepared/A02 - 1099-INT Interest Income/A02 - 1099-INT Interest Income - TY2025.pdf",
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


def test_the_records_import_nothing_of_the_package():
    """The whole point of the module: a layer above may name a record
    without loading the machinery that writes it. `tests/test_layers.py`
    pins the direction of every edge; this names this one."""
    load, call = import_edges()

    assert load["records"] == set(), load["records"]
    assert call["records"] == set(), call["records"]
    assert "records" in load["manifest"], "the manifest names the shapes it loads"


def test_nothing_here_reaches_a_file_or_a_workbook():
    """A record knows nothing about where it is stored. The imports say so:
    no openpyxl, no os, `pathlib` only because a Routing names a path,
    `re` only because as_pattern() turns a sentence's template into the
    pattern that reads it back (decision 109), and `json` only because the
    return's people come back as JSON text from the one column that holds
    them (decision 128) - reading a value is not knowing where it lives."""
    source = (Path(records.__file__)).read_text(encoding="utf-8")
    imported = {line.split()[1] for line in source.splitlines()
                if line.startswith("import ") or line.startswith("from ")}

    assert imported == {"__future__", "datetime", "dataclasses", "json", "pathlib", "re"}, imported
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
    now = "Prepared/C01 - Mortgage Interest Statement/w2 (2).pdf"
    said = template.format(home="Prepared/A01 - W-2/A01 - W-2 - TY2025.pdf", now=now,
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
