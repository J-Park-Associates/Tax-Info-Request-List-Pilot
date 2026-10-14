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

from tests.import_graph import import_edges
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


def test_the_records_import_nothing_of_the_package_but_the_layouts_name_rule_and_the_bounds():
    """The whole point of the module: a layer above may name a record
    without loading the machinery that writes it. `tests/test_layers.py`
    pins the direction of every edge; this names this one. Since decision
    188 the Windows character and device rule is the layout's, which reads
    no file, and the record imports it from there; since P2.4 the value
    rule's bounds are `tracker.bounds`', which reads none either, and the
    record imports them from there."""
    load, call = import_edges()

    assert load["records"] == {"bounds", "layout"}, load["records"]
    assert call["records"] == set(), call["records"]
    assert "records" in load["manifest"], "the manifest names the shapes it loads"


def test_nothing_here_reaches_a_file_or_a_workbook():
    """A record knows nothing about where it is stored. The imports say so:
    no openpyxl, no os, `pathlib` only because a Routing names a path,
    `re` only because as_pattern() turns a sentence's template into the
    pattern that reads it back (decision 109), and `json` only because the
    return's people come back as JSON text from the one column that holds
    them (decision 128) - reading a value is not knowing where it lives.
    The value rule's bounds, with `math` and the standard library's own
    parser, are `tracker.bounds`' since P2.4. `tracker.layout` is the
    Windows name rule's (decision 188), and it reads no file either."""
    source = (Path(records.__file__)).read_text(encoding="utf-8")
    imported = {line.split()[1] for line in source.splitlines()
                if line.startswith("import ") or line.startswith("from ")}

    assert imported == {"__future__", "datetime", "dataclasses", "json", "pathlib", "re",
                        "tracker.bounds", "tracker.layout"}, imported
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


# Decision 187: the value rule, worded once, for the editor and the gate. Its own
# tests are tests/test_bounds.py's since P2.4; these read a row check or the
# editor's re-export as well.


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


def test_waits_for_round_trips_and_is_empty_on_every_other_row():
    """Decision 204: the Waits For cell reads back exactly as it was written
    - the return line, the requests in order, the Also Answers cell - and
    its grammar is unambiguous because the layout's one name rule refuses
    the separator in a household or return name. An empty or unreadable
    cell is no claim at all, which offers no click rather than a guessed
    one, and a row that says nothing of it waits for nothing."""
    from tracker import layout
    from tracker.records import (
        WAITS_FOR_SEP,
        IndexEntry,
        WaitsFor,
        entry_from_json,
        format_answers,
        format_waits_for,
        parse_waits_for,
    )

    answers = format_answers([("A02", ("1099-int", "1099-div")), ("A04", ("1099-misc",))])
    for claim in (WaitsFor("Park & Lee LLC", "1120S - Park & Lee LLC", ("B01",)),
                  WaitsFor("Dana Reyes", "1040 - Dana Reyes", ("A01", "C01")),
                  WaitsFor("Dana Reyes", "1040 - Dana Reyes", ("E01",), answers)):
        assert parse_waits_for(format_waits_for(claim)) == claim
    assert format_waits_for(WaitsFor("H", "R", ("E01",), answers)) == f"H / R / E01; also answers {answers}"
    for unreadable in ("", "Park Family", "Park Family / 1040 - John Park", " /  / A01"):
        assert parse_waits_for(unreadable) is None
    # The separator's one character is refused in either name, by the rule
    # every household and return is typed through.
    assert layout.segment_problem(f"Park{WAITS_FOR_SEP.strip()}Lee") is not None
    row = {"received": "2026-07-01", "original_name": "w2.pdf", "size_kb": 1.0, "digest": "ab" * 32,
           "identifier": "", "prepared_location": "", "pbc_location": "x.pdf",
           "decision": "Needs Review", "reason": ""}
    entry = entry_from_json(row)
    assert entry.waits_for == "" and entry.waiting_for is None
    assert IndexEntry(**row).waits_for == ""


def test_a_stored_waits_for_cell_is_refused_unless_it_reads_back_whole():
    """Decision 204's review, S-3 (security principle 1): the claim is held
    to its structure when a record line is read in, not only when the click
    carries it out. Empty is no claim; a cell that does not read back as
    written, or whose parts are not one-line text, is refused by name."""
    from tracker.records import WAITS_FOR_BOUNDS, entry_problem, waits_for_problem

    assert waits_for_problem("") == ""
    assert waits_for_problem("Park & Lee LLC / 1120S - Park & Lee LLC / B01, B02") == ""
    assert waits_for_problem("H / R / E01; also answers A02 (1099-int, 1099-div)") == ""
    for forged in ("B01", "a / b", "a / b / c / d", "a /  / B01", " a / b / B01", 7):
        assert waits_for_problem(forged) == WAITS_FOR_BOUNDS, forged
    assert waits_for_problem("a\tb / R / B01") != ""
    row = {"received": "2026-07-01", "original_name": "w2.pdf", "size_kb": 1.0, "digest": "ab" * 32,
           "decision": "Needs Review", "reason": "", "waits_for": "a / b"}
    assert entry_problem(row) == f"'waits_for' {WAITS_FOR_BOUNDS}"


def test_rows_written_before_190_read_as_cause_not_recorded():
    """Decision 190. A row stored before the Code and Client's Subfolder
    columns, and a status stored before its notes had codes, read back with
    ``""`` in each: the cause was not recorded, and nothing here reads one
    out of the sentence - even one that is a reason's own words, from a
    subfolder named like another reason."""
    from tracker import reasons
    from tracker.records import StatusUpdate, status_from_json, status_to_json

    old = {
        "received": "2026-01-01", "original_name": "w2.pdf", "size_kb": 9.4, "digest": "d",
        "identifier": "", "prepared_location": "", "pbc_location": "../w2.pdf",
        "decision": "Needs Review",
        "reason": f"{reasons.PASSWORD_PROTECTED.template}; "
                  "came from the client's subfolder 'not allowed'",
    }
    entry = entry_from_json(old)
    assert entry.code == "" and entry.subfolder == ""
    assert entry_from_json({**old, "code": None, "subfolder": None}).code == ""
    now = entry_from_json({**old, "code": reasons.PASSWORD_PROTECTED.code, "subfolder": "Scans"})
    assert entry_from_json(entry_to_json(now)) == now

    status = status_from_json({"status": "Failed Validation",
                               "validation_notes": "x.pdf: " + reasons.NO_TEXT_LAYER.template})
    assert status.note_codes == "" and status.note_code_list == []
    coded = StatusUpdate(status="Failed Validation", note_codes=", ".join(
        [reasons.NO_TEXT_LAYER.code, reasons.PASSWORD_PROTECTED.code]))
    assert status_from_json(status_to_json(coded)) == coded
    assert coded.note_code_list == [reasons.NO_TEXT_LAYER.code, reasons.PASSWORD_PROTECTED.code]


def test_the_code_and_the_subfolder_are_columns_of_the_index():
    """Decision 190: a row's cause and the client's subfolder each have a
    column of their own - a header in the one layout table, so the Status
    Report shows them - and the Reason carries neither."""
    assert INDEX_LAYOUT["code"][0] == "Code"
    assert INDEX_LAYOUT["subfolder"][0] == "Client's Subfolder"
    assert {"Code", "Client's Subfolder"} <= set(INDEX_COLUMNS)


# ----------------------------------------------- pilot P170: related households ----


def test_a_households_related_list_round_trips_and_an_old_record_reads_as_none():
    """Pilot P170: the related households are the record's last field, a
    list of names written as a JSON list and read back as they were; a
    household record from before the field names none (backward
    compatible), and a shape that is not a list of names raises rather
    than being half-read."""
    info = records.HouseholdInfo(name="Park Family", related=("Lee Family", "Park & Lee LLC"))
    stored = records.household_to_json(info)
    assert stored["related"] == ["Lee Family", "Park & Lee LLC"]
    assert records.household_from_json(stored) == info
    assert records.household_from_json({"name": "Park Family"}).related == ()
    assert records.household_from_json({"name": "Park Family", "related": '["Lee Family"]'}).related == ("Lee Family",)
    assert "related" in records.HOUSEHOLD_EDITABLE
    assert ("Related Households", "related") in records.HOUSEHOLD_FIELDS
    assert [one.name for one in fields(records.HouseholdInfo)][-1] == "related"
    for bad in ([1], {"name": "Lee"}, "Lee Family"):
        with pytest.raises((ValueError, TypeError)):
            records.household_from_json({"name": "Park Family", "related": bad})


def test_a_households_related_list_is_held_to_the_text_rule():
    """Pilot P170: each related name is one line of text, as a member is."""
    assert records.household_problem({"related": ["Lee Family"]}) == ""
    assert records.household_problem({"related": "Lee Family"}).startswith("'related' ")
    assert records.household_problem({"related": ["Lee\nFamily"]}).startswith("'related' ")


def test_a_persons_name_is_held_to_the_one_line_text_rule():
    """P288: the one name with no bound is bound like every other. A name
    over 1,000 characters, one with a line break and one that is not text
    are each refused by name; 1,000 characters pass."""
    for bad in ("J" * 1001, "John\nPark", "John\x00Park", 7, None):
        with pytest.raises(ValueError, match="a person's name"):
            records.person_from_json({"kind": "taxpayer", "name": bad, "spellings": []})
    assert records.person_from_json(
        {"kind": "taxpayer", "name": "J" * 1000, "spellings": []}).name == "J" * 1000
    assert records.person_from_json({"kind": "taxpayer", "name": "John Park"}).name == "John Park"


def test_a_stored_row_whose_document_hides_a_spoofing_character_is_a_fault_naming_the_document():
    """P301: ``rule_row_fault`` is the store's gate and the editor's, so a
    refused line is named by its field, as an identifier or a short name is;
    a Document that is not text is still the text rule's, never a crash."""
    spoof = "W-2\u202efdp.exe"
    problem = records.document_problem(spoof)
    assert records.rule_row_fault({"identifier": "A01", "document": spoof}) == ("document", problem)
    assert records.rule_row_problem({"document": spoof}) == f"'document' {problem}"
    assert records.rule_row_fault({"identifier": "A01", "document": "W-2\u00a0Wages"}) == ("", "")
    assert records.rule_row_fault({"identifier": "A01"}) == ("", "")
    assert records.rule_row_fault({"document": 7}) == ("document", records.LONG_TEXT_BOUNDS)
