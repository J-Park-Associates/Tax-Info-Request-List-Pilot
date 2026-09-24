"""Tests for tracker/manifest.py — the request list: its schema, its validation,
and its reading from and writing to the record. No workbook anywhere."""

import datetime as dt
import re
from dataclasses import replace

import pytest

from tests.conftest import (
    TEST_HOUSEHOLD,
    TEST_PEOPLE,
    TEST_RETURN,
    TEST_YEAR,
    make_engagement,
)
from tracker import ledger, store
from tracker.manifest import (
    COL_DATE_PATTERN,
    COL_DOCUMENT,
    COL_EXPECTED_COUNT,
    COL_IDENTIFIER,
    COL_MANUAL_OVERRIDE,
    COL_MIN_SIZE_KB,
    COL_NAMED,
    COL_OVERRIDE_REASON,
    COLUMN_HELP,
    COLUMNS,
    DEFAULT_MIN_SIZE_KB,
    HEADERS,
    MIN_EXPECTED_COUNT,
    MIN_SIZE_KB_FLOOR,
    NOT_AN_ENGAGEMENT,
    NOT_APPLICABLE_LABEL,
    OVERRIDE_REASON_OTHER,
    OVERRIDE_REASONS,
    SUMMARY_EMPTY,
    SUMMARY_SEPARATOR,
    UNLEARN_REFUSED,
    UNSCANNED_LABEL,
    EngagementInfo,
    ManifestError,
    Override,
    RequestItem,
    Status,
    check_narrowing_names,
    check_rules,
    create_engagement,
    entity_keyword,
    item_from_fields,
    load_engagement_info,
    load_manifest,
    narrowing_rows,
    override_label,
    save_rules,
    unlearn_keyword,
    validated,
)
from tracker.records import RULE_FIELDS, info_to_json, rule_to_json

SAMPLE_ITEMS = [
    RequestItem(
        identifier="A01",
        document="Dec 2025 Bank Statement",
        period="Dec 2025",
        allowed_extensions=("pdf",),
        required_keywords=("Chase",),
        date_pattern=r"(?i)december\s+2025|12/\d{1,2}/2025",
    ),
    RequestItem(
        identifier="A02",
        document="Monthly Bank Statements FY2025",
        period="FY2025",
        expected_count=12,
        allowed_extensions=("pdf", "csv"),
        min_size_kb=10,
        any_keywords=("statement", "account summary"),
    ),
    RequestItem(
        identifier="B01",
        document="Payroll Register Q4",
        period="Q4 2025",
        allowed_extensions=("xlsx", "csv"),
        manual_override=Override.NOT_APPLICABLE,
    ),
]


def placed(info: EngagementInfo) -> EngagementInfo:
    """The details as the record holds them once the return exists.

    Creation writes where the return is into its own details - the
    household, the tax year and the return name (decision 125) - so a
    record read back carries three fields nobody typed. They are not
    editable, and ``tests/test_api.py`` is where that is claimed; here they
    are simply what a round trip has to allow for. The people the return is
    for (decision 128) are the fourth: the suite's helper gives every
    return the one test person, as the wizard makes a person give it one.
    """
    return replace(info, household=TEST_HOUSEHOLD, tax_year=TEST_YEAR,
                   return_name=TEST_RETURN, people=TEST_PEOPLE)


@pytest.fixture
def engagement(tmp_path):
    return make_engagement(tmp_path / "Smith 2025", SAMPLE_ITEMS, scaffold=False)


def rules_events(folder) -> list[dict]:
    return [e for e in ledger.read_events(folder) if e[ledger.EVENT_KEY] == ledger.RULES_CHANGED]


# ---------------------------------------------------------------- loading ----


def test_create_then_load_round_trips_through_the_record(engagement):
    items = load_manifest(engagement)
    assert [i.identifier for i in items] == ["A01", "A02", "B01"]

    a01 = items[0]
    assert a01.document == "Dec 2025 Bank Statement"
    assert a01.period == "Dec 2025"
    assert a01.expected_count == 1          # default
    assert a01.min_size_kb == DEFAULT_MIN_SIZE_KB
    assert a01.allowed_extensions == ("pdf",)
    assert a01.required_keywords == ("Chase",)
    assert a01.any_keywords == ()
    assert a01.date_pattern.startswith("(?i)december")
    assert a01.manual_override == ""
    assert a01.status == ""
    assert a01.received_date is None
    assert a01.row == 1                     # the position in the list, 1-based

    a02 = items[1]
    assert a02.expected_count == 12
    assert a02.min_size_kb == 10
    assert a02.allowed_extensions == ("pdf", "csv")
    assert a02.any_keywords == ("statement", "account summary")
    assert a02.row == 2

    assert items[2].manual_override == Override.NOT_APPLICABLE


def test_an_engagement_is_created_from_a_template_and_read_back_from_the_record_with_no_workbook_anywhere(tmp_path):
    """Decision 104's first claim: one event carries the whole list and the
    whole of the details, the derived year check is live on the way back,
    and there is no spreadsheet under the folder."""
    from tracker.templates import template_items

    folder = make_engagement(tmp_path / "Smith 2025", template_items("1040", year=2025),
                             EngagementInfo(client="John"), form="1040")
    items = load_manifest(folder)
    assert [i.identifier for i in items] == [i.identifier for i in template_items("1040", year=2025)]
    assert all(i.date_pattern_derived for i in items if re.search(r"\d{4}", i.period))
    assert list(folder.rglob("*.xlsx")) == []

    [event] = rules_events(folder)
    assert [row["identifier"] for row in event[ledger.RULES_KEY]] == [i.identifier for i in items]
    assert event[ledger.REMOVED_KEY] == []
    assert event[ledger.INFO_KEY] == info_to_json(placed(EngagementInfo(client="John", form="1040")))
    assert load_engagement_info(folder) == placed(EngagementInfo(client="John", form="1040"))


def test_a_folder_with_no_record_is_not_an_engagement(tmp_path):
    folder = tmp_path / "nope"
    folder.mkdir()
    with pytest.raises(ManifestError, match=re.escape(
            NOT_AN_ENGAGEMENT.format(name="nope", ledger=ledger.LEDGER_FILENAME))):
        load_manifest(folder)
    with pytest.raises(ManifestError, match="not an engagement"):
        load_engagement_info(folder)


def test_create_refuses_a_folder_that_already_has_a_record(engagement):
    before = ledger.path_for(engagement).read_bytes()
    with pytest.raises(ManifestError, match="Refusing to overwrite an engagement that already has a record"):
        create_engagement(engagement, SAMPLE_ITEMS)
    assert ledger.path_for(engagement).read_bytes() == before


def test_create_refuses_a_bad_list_before_a_line_is_written(tmp_path):
    folder = tmp_path / "Smith 2025"
    folder.mkdir()
    with pytest.raises(ManifestError, match="Duplicate identifier"):
        create_engagement(folder, [RequestItem(identifier="A01", document="a"),
                                   RequestItem(identifier="a01", document="b")])
    assert not ledger.path_for(folder).exists()
    assert store.rules(store.connect(), folder) is None      # nothing in the store either


def test_the_list_is_the_fourteen_columns_a_person_edits():
    """Decision 103 took the four scanner columns out of the schema; 104
    keeps the ten, keyed by the record's own field names, each with the
    sentence the editor shows under its heading; 116 adds the eleventh,
    the reason an override was made; 128 the twelfth, whether the document
    this request asks for carries a name; 142 the thirteenth, whether the
    client is asked for it; 144 the fourteenth, the short name the firm's
    working folder and copies go by."""
    from tracker.manifest import COL_ASKED, COL_SHORT_TITLE

    assert HEADERS == tuple(header for header, _ in COLUMNS)
    assert len(HEADERS) == 14
    assert HEADERS[-4:] == (COL_OVERRIDE_REASON, COL_NAMED, COL_ASKED, COL_SHORT_TITLE)
    assert tuple(field for _, field in COLUMNS) == tuple(
        f for f in RULE_FIELDS if f not in ("row", "date_pattern_derived"))
    assert set(COLUMN_HELP) == {field for _, field in COLUMNS}
    assert all(sentence and not sentence.endswith(".") for sentence in COLUMN_HELP.values())


# ------------------------------------------------------------ validation ----


def test_duplicate_identifier_rejected():
    rows = [*SAMPLE_ITEMS, RequestItem(identifier="A01", document="again")]
    with pytest.raises(ManifestError, match="Duplicate identifier 'A01'.*rows 1 and 4"):
        validated(rows)


def test_bad_regex_rejected():
    rows = [RequestItem(identifier="A01", document="x", date_pattern="([unclosed")]
    with pytest.raises(ManifestError, match=f"Row 1: {COL_DATE_PATTERN} is not a valid regex"):
        validated(rows)


def test_bad_expected_count_rejected():
    with pytest.raises(ManifestError, match=f"Row 2: {COL_EXPECTED_COUNT} must be a whole number, got 'twelve'"):
        item_from_fields({"identifier": "A01", "document": "x", "expected_count": "twelve"}, where="Row 2")
    with pytest.raises(ManifestError, match=f"Row 3: {COL_EXPECTED_COUNT} must be at least {MIN_EXPECTED_COUNT}"):
        item_from_fields({"identifier": "A01", "document": "x", "expected_count": 0}, where="Row 3")
    with pytest.raises(ManifestError, match=f"Row 1: {COL_MIN_SIZE_KB} must be at least {MIN_SIZE_KB_FLOOR}"):
        validated([RequestItem(identifier="A01", document="x", min_size_kb=-1)])


def test_unknown_override_rejected():
    with pytest.raises(ManifestError, match=f"Row 2: {COL_MANUAL_OVERRIDE} must be one of"):
        item_from_fields({"identifier": "A01", "document": "x", "manual_override": "Maybe"}, where="Row 2")
    with pytest.raises(ManifestError, match=f"Row 1: {COL_MANUAL_OVERRIDE}"):
        validated([RequestItem(identifier="A01", document="x", manual_override="Maybe")])


# ------------------------------------------------- the override's reason (116) ----


def test_an_accepted_override_with_no_reason_is_refused_naming_the_row_and_the_column():
    rows = [SAMPLE_ITEMS[0], RequestItem(identifier="A02", document="x", manual_override=Override.ACCEPTED)]
    with pytest.raises(ManifestError, match=(
            f"Row 2: {COL_OVERRIDE_REASON} is required when {COL_MANUAL_OVERRIDE} is {Override.ACCEPTED}")):
        validated(rows)
    # And one of the offered reasons, or a person's own words, is enough.
    for reason in (*OVERRIDE_REASONS, "the client walked it in on Tuesday"):
        [row] = validated([RequestItem(identifier="A02", document="x", manual_override=Override.ACCEPTED,
                                       override_reason=reason)])
        assert row.override_reason == reason


def test_other_with_nothing_typed_is_refused_and_typed_words_are_the_reason():
    """The editor's last entry opens a box; what is saved is what was typed,
    never the word that opened it."""
    with pytest.raises(ManifestError, match=f"Row 1: {COL_OVERRIDE_REASON} {OVERRIDE_REASON_OTHER} needs the reason typed"):
        validated([RequestItem(identifier="A01", document="x", manual_override=Override.ACCEPTED,
                               override_reason=OVERRIDE_REASON_OTHER)])
    with pytest.raises(ManifestError, match="needs the reason typed"):
        validated([RequestItem(identifier="A01", document="x", manual_override=Override.ACCEPTED,
                               override_reason=OVERRIDE_REASON_OTHER.lower())])
    [row] = validated([item_from_fields(
        {"identifier": "A01", "document": "x", "manual_override": Override.ACCEPTED,
         "override_reason": "  confirmed by phone with the client  "}, where="Row 1")])
    assert row.override_reason == "confirmed by phone with the client"
    assert OVERRIDE_REASON_OTHER not in OVERRIDE_REASONS


def test_a_reason_without_an_override_is_refused():
    with pytest.raises(ManifestError, match=f"Row 1: {COL_OVERRIDE_REASON} needs a {COL_MANUAL_OVERRIDE}"):
        validated([RequestItem(identifier="A01", document="x", override_reason="because")])
    # A set-aside row may carry one or not.
    for reason in ("", "no foreign accounts this year"):
        [row] = validated([RequestItem(identifier="A01", document="x", period="TY2025",
                                       manual_override=Override.NOT_APPLICABLE, override_reason=reason)])
        assert row.override_reason == reason


def test_a_waived_row_in_an_old_journal_reads_as_not_applicable_and_saving_the_list_back_records_nothing(tmp_path):
    """The retired-value rule of decision 104, applied to a value: the
    journal keeps the spelling it holds, every reader sees the successor,
    and an untouched list is not an event."""
    from tests.conftest import ensure
    from tracker.locking import engagement_lock

    folder = make_engagement(tmp_path / "Old 2025", SAMPLE_ITEMS[:2], scaffold=False)
    retired = rule_to_json(validated(SAMPLE_ITEMS)[2])       # as an older version stored it
    retired["manual_override"] = "Waived"
    del retired["override_reason"]                      # written by a version that had no such field
    with engagement_lock(folder):
        ensure(folder)
        store.record(store.connect(), folder, ledger.new(ledger.RULES_CHANGED, **{
            ledger.RULES_KEY: [retired], ledger.REMOVED_KEY: [], ledger.INFO_KEY: {},
        }))
    before = ledger.path_for(folder).read_bytes()
    assert b'"Waived"' in before

    items = load_manifest(folder)
    assert items[2].manual_override == Override.NOT_APPLICABLE
    assert items[2].override_reason == ""
    assert override_label(items[2]) == NOT_APPLICABLE_LABEL.format(year=2025)

    assert save_rules(folder, items, load_engagement_info(folder)).recorded is False
    assert ledger.path_for(folder).read_bytes() == before        # the bytes are the bytes
    conn = store.connect()
    assert store.check(conn, store.root_for(folder), folder) == []
    assert store.rules(conn, folder)[2]["manual_override"] == "Waived"   # the store keeps them too


def test_the_label_carries_the_rows_period_year_or_the_bare_value():
    set_aside = RequestItem(identifier="A01", document="x", period="TY2025",
                            manual_override=Override.NOT_APPLICABLE)
    assert override_label(set_aside) == "Not Applicable in TY2025" == NOT_APPLICABLE_LABEL.format(year=2025)
    assert set_aside.year == 2025
    no_year = replace(set_aside, period="quarterly")
    assert override_label(no_year) == Override.NOT_APPLICABLE and no_year.year is None
    assert override_label(replace(set_aside, manual_override=Override.ACCEPTED)) == Override.ACCEPTED
    assert override_label(replace(set_aside, manual_override="")) == ""


def test_summarize_counts_not_applicable_apart_and_check_rules_skips_it():
    from tracker.manifest import summarize

    rows = validated([
        RequestItem(identifier="A01", document="W-2", required_keywords=("W-2",), allowed_extensions=("pdf",)),
        RequestItem(identifier="A02", document="Nothing to go on", period="TY2025",
                    manual_override=Override.NOT_APPLICABLE),        # no rule, "*": nobody's to warn about
    ])
    summary = summarize(rows)
    assert summary.total == 1 and summary.not_applicable == 1 and summary.unscanned == 1
    assert summary.line.endswith(f"{Override.NOT_APPLICABLE}: 1")
    assert NOT_APPLICABLE_LABEL.format(year=2025) not in summary.line       # the count says the value
    assert check_rules(rows) == []


def test_the_retired_spelling_is_folded_on_every_read_and_never_written(engagement):
    """A value typed by hand in the retired spelling is stored as the
    successor: nothing this version writes carries the old word."""
    typed = item_from_fields({"identifier": "C01", "document": "Old habit", "manual_override": "waived"},
                             where="Row 4")
    assert typed.manual_override == Override.NOT_APPLICABLE
    rows = [*load_manifest(engagement), typed]
    saved = save_rules(engagement, rows, load_engagement_info(engagement))
    assert saved.recorded and saved.changed == ("C01",)
    last = rules_events(engagement)[-1]
    assert last[ledger.RULES_KEY][0]["manual_override"] == Override.NOT_APPLICABLE
    assert b"Waived" not in ledger.path_for(engagement).read_bytes()
    assert Override.RETIRED == {"Waived": Override.NOT_APPLICABLE}
    assert not hasattr(Override, "WAIVED")


def test_a_row_needs_an_identifier_and_a_document():
    with pytest.raises(ManifestError, match=f"Row 1: {COL_IDENTIFIER} is required"):
        validated([RequestItem(identifier=" ", document="x")])
    with pytest.raises(ManifestError, match=f"Row 2: {COL_DOCUMENT} is required"):
        validated([RequestItem(identifier="A01", document="x"), RequestItem(identifier="A02", document="")])


@pytest.mark.parametrize("identifier", ["A:01", "A/01", "A?1", 'B"1', "A01.", "A<1>"])
def test_identifier_that_cannot_name_a_folder_is_rejected(identifier):
    # The identifier is the folder-name prefix the scanner matches back on.
    # One the filesystem would alter is a permanent "folder not found".
    with pytest.raises(ManifestError, match=f"Row 1: {COL_IDENTIFIER}"):
        validated([RequestItem(identifier=identifier, document="Doc")])


def test_identifiers_differing_only_by_case_are_duplicates():
    # Windows folder names are case-insensitive: "A01" and "a01" would fight
    # over one folder, so they are the same identifier.
    with pytest.raises(ManifestError, match="Duplicate identifier"):
        validated([RequestItem(identifier="A01", document="a"), RequestItem(identifier="a01", document="b")])


def test_validated_numbers_the_rows_by_their_position_and_strips_what_was_typed():
    rows = validated([RequestItem(identifier=" A01 ", document=" W-2 ", period=" TY2025 "),
                      RequestItem(identifier="A02", document="x")])
    assert [(i.identifier, i.document, i.period, i.row) for i in rows] == [
        ("A01", "W-2", "TY2025", 1), ("A02", "x", "", 2)]


def test_a_row_the_readers_gave_back_validates_to_itself(engagement):
    """A derived year check is not typed: fed back in, it is derived again
    rather than read as a regex somebody wrote, so a loaded list validates
    to the same rules and a save of it records nothing."""
    loaded = load_manifest(engagement)
    again = validated(loaded)
    assert [rule_to_json(i) for i in again] == [rule_to_json(i) for i in loaded]
    assert save_rules(engagement, loaded, load_engagement_info(engagement)).recorded is False


# ---------------------------------------------------------------- writes ----


def test_a_persons_edit_is_one_rules_changed_event_of_exactly_the_changed_rows(engagement):
    """Change one row's Any Keywords and remove another: the last event
    carries that one row whole and the removed identifier; the store is the
    fold of the journal; saving the same list again records nothing."""
    info = load_engagement_info(engagement)
    rows = load_manifest(engagement)
    edited = [rows[0], replace(rows[1], any_keywords=("statement", "ledger"))]

    saved = save_rules(engagement, edited, info)
    assert saved.recorded and saved.changed == ("A02",) and saved.removed == ("B01",)
    assert saved.info_fields == ()

    last = rules_events(engagement)[-1]
    assert [row["identifier"] for row in last[ledger.RULES_KEY]] == ["A02"]
    assert last[ledger.RULES_KEY][0]["any_keywords"] == ["statement", "ledger"]
    assert last[ledger.RULES_KEY][0]["row"] == 2
    assert last[ledger.REMOVED_KEY] == ["B01"]
    assert last[ledger.INFO_KEY] == {}

    stored = store.rules(store.connect(), engagement)
    folded = ledger.replay(ledger.read_events(engagement)).rules
    assert {row["identifier"]: row for row in stored} == {
        identifier: {name: (row[name] if name != "date_pattern_derived" else bool(row[name]))
                     for name in RULE_FIELDS}
        for identifier, row in folded.items()}
    assert [i.identifier for i in load_manifest(engagement)] == ["A01", "A02"]

    before = ledger.path_for(engagement).read_bytes()
    assert save_rules(engagement, edited, info).recorded is False
    assert ledger.path_for(engagement).read_bytes() == before


def test_a_row_moved_in_the_list_is_a_row_changed(engagement):
    """``row`` is part of the rule: the position a person gave a request
    is recorded, so reordering the list is an edit the record says."""
    info = load_engagement_info(engagement)
    rows = load_manifest(engagement)
    saved = save_rules(engagement, [rows[1], rows[0], rows[2]], info)
    assert saved.changed == ("A02", "A01") and saved.removed == ()
    assert [i.identifier for i in load_manifest(engagement)] == ["A02", "A01", "B01"]
    assert [i.row for i in load_manifest(engagement)] == [1, 2, 3]


def test_an_identifier_respelled_by_case_or_removed_leaves_the_record_holding_only_what_the_list_says(tmp_path):
    """Retype ``A01`` as ``a01``: one event that names ``A01`` removed and
    carries ``a01``; the store as the pass left it and the journal folded
    both hold exactly the new spelling, ``check`` agrees, and the same
    list again records nothing. The diff is by the exact spelling and the
    folds apply removals first; diffed by the folded key, the record held
    both spellings for good and no save from the app could repair it. Then
    a non-ASCII identifier is added and removed."""
    engagement = make_engagement(tmp_path / "Smith 2025", SAMPLE_ITEMS, scaffold=False)
    info = load_engagement_info(engagement)
    rows = load_manifest(engagement)
    respelled = [replace(rows[0], identifier="a01"), *rows[1:]]

    saved = save_rules(engagement, respelled, info)
    assert saved.recorded and saved.changed == ("a01",) and saved.removed == ("A01",)
    last = rules_events(engagement)[-1]
    assert [row["identifier"] for row in last[ledger.RULES_KEY]] == ["a01"]
    assert last[ledger.REMOVED_KEY] == ["A01"]

    conn = store.connect()          # the live store, as the save left it - not a rebuild
    assert [row["identifier"] for row in store.rules(conn, engagement)] == ["a01", "A02", "B01"]
    assert list(ledger.replay(ledger.read_events(engagement)).rules) == ["A02", "B01", "a01"]
    assert store.check(conn, tmp_path, engagement) == []
    assert [i.identifier for i in load_manifest(engagement)] == ["a01", "A02", "B01"]

    before = ledger.path_for(engagement).read_bytes()
    assert save_rules(engagement, respelled, info).recorded is False
    assert ledger.path_for(engagement).read_bytes() == before

    # A non-ASCII identifier removed leaves the store the way it leaves the
    # journal: the delete is by the exact spelling, not SQLite's ASCII-only
    # lower(), which would have kept an orphan the fold had dropped.
    added = save_rules(engagement, [*respelled, RequestItem(identifier="É01", document="Foreign statement")], info)
    assert added.changed == ("É01",)
    gone = save_rules(engagement, respelled, info)
    assert gone.removed == ("É01",)
    assert [row["identifier"] for row in store.rules(conn, engagement)] == ["a01", "A02", "B01"]
    assert list(ledger.replay(ledger.read_events(engagement)).rules) == ["A02", "B01", "a01"]
    assert store.check(conn, tmp_path, engagement) == []


def test_the_engagement_details_round_trip_through_the_record(tmp_path):
    info = EngagementInfo(client="John Smith", name="Smiths 2025", link="https://drive.example/abc",
                          due=dt.date(2026, 4, 15), sender="Jason Park", firm="J Park",
                          reminders=False, active=True)
    folder = make_engagement(tmp_path / "Smith 2025", SAMPLE_ITEMS, info, scaffold=False)
    assert load_engagement_info(folder) == placed(info)
    assert [i.identifier for i in load_manifest(folder)] == ["A01", "A02", "B01"]  # the list untouched

    saved = save_rules(folder, load_manifest(folder),
                       replace(placed(info), due=None, client="Jane", active=False))
    assert saved.recorded and saved.changed == () and set(saved.info_fields) == {"client", "active", "due"}
    loaded = load_engagement_info(folder)
    assert loaded.client == "Jane" and loaded.active is False and loaded.reminders is False
    assert loaded.due is None and loaded.link == info.link


def test_a_details_only_edit_is_recorded_as_one(engagement):
    # The details the editor sends are the recorded ones with the one box a
    # person changed: where the return is (decision 125) is not editable, so
    # it travels back untouched and is not part of what moved.
    edited = replace(load_engagement_info(engagement), client="Jane")
    saved = save_rules(engagement, load_manifest(engagement), edited)
    assert saved.recorded and saved.changed == () and saved.removed == ()
    assert saved.info_fields == ("client",)
    assert rules_events(engagement)[-1][ledger.INFO_KEY] == {"client": "Jane"}


def test_a_refused_save_records_nothing(engagement):
    before = ledger.path_for(engagement).read_bytes()
    rows = load_manifest(engagement)
    with pytest.raises(ManifestError, match="Row 2"):
        save_rules(engagement, [rows[0], RequestItem(identifier="A02", document="x", date_pattern="(")],
                   load_engagement_info(engagement))
    assert ledger.path_for(engagement).read_bytes() == before
    assert [i.identifier for i in load_manifest(engagement)] == ["A01", "A02", "B01"]


def test_a_save_of_a_folder_with_no_record_is_refused(tmp_path):
    folder = tmp_path / "nope"
    folder.mkdir()
    with pytest.raises(ManifestError, match="not an engagement"):
        save_rules(folder, SAMPLE_ITEMS, EngagementInfo())
    assert not ledger.path_for(folder).exists()


def test_create_records_the_catalog_the_request_list_was_cut_from(tmp_path):
    """Decision 86: the wizard's choice is written into the details, so an
    engagement can say which checklist it came from without the folder name."""
    from tracker.templates import template_items

    folder = make_engagement(tmp_path / "S", template_items("1120S", year=2025), form="1120S", scaffold=False)
    assert load_engagement_info(folder).form == "1120S"


def test_the_form_a_caller_gives_never_clears_the_one_the_details_carry(tmp_path):
    info = EngagementInfo(client="John Smith", form="1065")
    folder = make_engagement(tmp_path / "S", SAMPLE_ITEMS, info, scaffold=False)
    assert load_engagement_info(folder) == placed(info)  # no form= given; the info's stands


def test_an_engagement_that_never_recorded_a_form_reads_as_unknown(tmp_path):
    """Blank is unknown to every reader, never a refusal."""
    folder = make_engagement(tmp_path / "S", SAMPLE_ITEMS, scaffold=False)
    assert load_engagement_info(folder).form == ""
    assert check_rules(load_manifest(folder)) == []


# -------------------------------------------------- the unlearn (decision 113) ----


def taught(folder, identifier: str, keyword: str) -> None:
    """A person's filing teaching one request one word, which is the only
    way one is learned (decision 103)."""
    from tracker.filer import ensure
    from tracker.locking import engagement_lock

    with engagement_lock(folder):
        ensure(folder)
        store.record(store.connect(), folder, ledger.new(ledger.KEYWORD_LEARNED, **{
            ledger.IDENTIFIER_KEY: identifier, ledger.KEYWORD_KEY: keyword,
        }))


def any_keywords(folder) -> dict[str, tuple[str, ...]]:
    return {i.identifier: i.any_keywords for i in load_manifest(folder)}


def test_unlearning_a_keyword_takes_it_out_of_the_overlay_and_refuses_a_pair_nobody_taught(
        engagement):
    """Decision 113: a word a filing taught may be taken back, by a person.

    One event, so the store's row goes and a rebuild agrees; the rules the
    person typed are not touched, because a taught word was never one of
    them; and a pair the record never carried is refused by name rather
    than passing quietly.
    """
    taught(engagement, "A01", "lender")
    assert any_keywords(engagement)["A01"] == ("lender",)
    before = store.rules(store.connect(), engagement)     # the rules the person typed

    taken = unlearn_keyword(engagement, "A01", "lender")

    assert (taken.identifier, taken.keyword) == ("A01", "lender")
    assert any_keywords(engagement)["A01"] == ()
    assert store.learned_keywords(store.connect(), engagement) == {}
    assert store.rules(store.connect(), engagement) == before
    names = [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)]
    assert names.count(ledger.KEYWORD_UNLEARNED) == 1 and ledger.RULES_CHANGED in names

    head = ledger.head(engagement)
    with pytest.raises(ManifestError) as refused:
        unlearn_keyword(engagement, "A01", "lender")
    assert str(refused.value) == UNLEARN_REFUSED.format(identifier="A01", keyword="lender")
    assert ledger.head(engagement) == head              # a refusal records nothing


def test_a_keyword_the_row_types_itself_is_not_unlearnable_because_it_was_never_taught(
        engagement):
    """The editor is where a rule is changed (decision 104). A word in the
    row's own Any Keywords is a rule, not a thing a filing taught, so it is
    not in the learned table and there is nothing here to take back."""
    assert "statement" in any_keywords(engagement)["A02"]

    with pytest.raises(ManifestError, match="never taught"):
        unlearn_keyword(engagement, "A02", "statement")

    assert "statement" in any_keywords(engagement)["A02"]


def test_an_unlearn_matches_the_request_without_case_and_records_the_lists_spelling(engagement):
    """The identifier folds the way every reading that joins a row to the
    record folds it, and the word is matched as the record holds it,
    because the editor sends back what it showed.

    The line itself spells the request the way the list does, whatever
    case the caller typed: the journal's fold has no case rule, so a line
    saying ``a01`` would leave that fold holding a word the store had
    deleted - which the suite's own store check would report after every
    test from here on.
    """
    taught(engagement, "A01", "Lender")

    with pytest.raises(ManifestError, match="never taught"):
        unlearn_keyword(engagement, "A01", "lender")

    taken = unlearn_keyword(engagement, "a01", "Lender")

    assert taken.identifier == "A01"
    assert ledger.read_events(engagement)[-1][ledger.IDENTIFIER_KEY] == "A01"
    assert ledger.replay(ledger.read_events(engagement)).learned == {}
    assert any_keywords(engagement)["A01"] == ()


# ------------------------------------------------------ allowed extensions ----


def test_a_blank_allowed_extensions_means_the_safe_default_not_anything():
    from tracker.manifest import DEFAULT_EXTENSIONS

    item = item_from_fields({"identifier": "A01", "document": "W-2", "allowed_extensions": ""}, where="Row 1")
    assert item.allowed_extensions == DEFAULT_EXTENSIONS


def test_accepting_any_file_type_has_to_be_said_with_a_star():
    from tracker.manifest import ANY_EXTENSION

    item = item_from_fields({"identifier": "A01", "document": "W-2", "allowed_extensions": ANY_EXTENSION},
                            where="Row 1")
    assert item.allowed_extensions == ()
    # And it comes back the same way through the record.
    assert validated([item])[0].allowed_extensions == ()


def test_a_spec_that_gives_its_extensions_as_a_list_gets_those_extensions():
    # The thirteenth reading: a spec typed as JSON holds ["pdf"], and
    # stringifying it made one extension called "['pdf']" - which no
    # document has, so every document parked against that row for ever.
    from tracker.manifest import DEFAULT_EXTENSIONS, parse_extensions
    from tracker.templates import item_from_spec

    assert parse_extensions(["pdf"]) == ("pdf",)
    assert parse_extensions(("PDF", ".Xlsx")) == ("pdf", "xlsx")
    assert parse_extensions(["*"]) == ()
    assert parse_extensions([]) == DEFAULT_EXTENSIONS
    item = item_from_spec({"identifier": "A01", "document": "W-2", "extensions": ["pdf", "xlsx"],
                           "required_keywords": ["W-2", "wage"]})
    assert item.allowed_extensions == ("pdf", "xlsx")
    assert item.required_keywords == ("W-2", "wage")
    # The editor's key works too, and the file types are normalised.
    item = item_from_fields({"identifier": "A01", "document": "W-2", "allowed_extensions": "PDF, .CSV"},
                            where="Row 1")
    assert item.allowed_extensions == ("pdf", "csv")


def test_item_from_fields_defaults_no_keyword_and_folds_the_override():
    item = item_from_fields({"identifier": "A01", "document": "Anything", "manual_override": "not applicable",
                             "expected_count": "2", "min_size_kb": ""}, where="Row 1")
    assert item.required_keywords == () and item.any_keywords == ()
    assert item.manual_override == Override.NOT_APPLICABLE
    assert item.expected_count == 2 and item.min_size_kb == DEFAULT_MIN_SIZE_KB
    assert item.row == 0                       # the position is validated()'s to give


# ------------------------------------------------------------------ check ----


def test_check_rules_warns_about_rows_the_rules_cannot_act_on():
    rows = validated([
        RequestItem(identifier="A01", document="Anything goes"),              # no rule, "*"
        RequestItem(identifier="A02", document="W-2", required_keywords=("W-2",),
                    allowed_extensions=("pdf",)),
        RequestItem(identifier="A03", document="Set aside", manual_override=Override.NOT_APPLICABLE),
    ])
    warnings = check_rules(rows)
    assert [w[:14] for w in warnings] == ["Row 1 (A01): n", "Row 1 (A01): A"]
    assert "never be filed automatically" in warnings[0]
    assert "any file type counts" in warnings[1]


def test_check_rules_names_the_rows_position_in_the_list(engagement):
    """The row a warning names is the one the editor shows, not a cell."""
    rows = load_manifest(engagement)
    rows.append(RequestItem(identifier="C01", document="Nothing to go on", allowed_extensions=("pdf",)))
    save_rules(engagement, rows, load_engagement_info(engagement))
    [warning] = check_rules(load_manifest(engagement))
    assert warning.startswith("Row 4 (C01):")


def test_check_rules_warns_when_a_keyword_names_a_family_of_forms():
    from tracker.manifest import BARE_FORM_NUMBER_WARNING, FORM_FAMILIES

    rows = validated([
        RequestItem(identifier="B01", document="1099s", allowed_extensions=("pdf",), any_keywords=("1099",)),
        RequestItem(identifier="C01", document="Mortgage", allowed_extensions=("pdf",), required_keywords=("1098",)),
    ])
    assert check_rules(rows) == [BARE_FORM_NUMBER_WARNING.format(
        row=1, identifier="B01", keyword="1099", example=FORM_FAMILIES["1099"])]


def test_check_rules_warns_about_a_keyword_with_nothing_in_it():
    from tracker.manifest import EMPTY_KEYWORD_WARNING

    rows = validated([RequestItem(identifier="A01", document="x", allowed_extensions=("pdf",),
                                  any_keywords=("w-2", "--"))])
    assert check_rules(rows) == [EMPTY_KEYWORD_WARNING.format(row=1, identifier="A01", keyword="--")]


# ---------------------------------------------------------- atomic writes ----


@pytest.mark.parametrize("name", ["TEMP_SUFFIX", "temp_path_for", "atomic_replacement",
                                  "write_text_atomically", "write_json_atomically"])
def test_the_manifest_does_not_re_export_the_atomic_write(name):
    """Decision 120 moved the five names to tracker/fsio.py. They are not
    left here as aliases: a name that resolves in two modules is a name
    that drifts, and a caller that still asks the manifest for the write
    should be told at the import rather than kept working until somebody
    reads the layer table and wonders."""
    import tracker.manifest as manifest_module

    with pytest.raises(ImportError):
        exec(f"from tracker.manifest import {name}")
    assert not hasattr(manifest_module, name)


# --------------------------------------------------------------- summary ----


def test_summarize_is_the_one_count():
    from tracker.manifest import summarize

    items = [
        RequestItem(identifier="A01", document="a", status=Status.RECEIVED),
        RequestItem(identifier="A02", document="b", status=Status.MISSING),
        RequestItem(identifier="A03", document="c", status=Status.PARTIAL),
        RequestItem(identifier="A04", document="d", status=Status.FAILED,
                    manual_override=Override.ACCEPTED,
                    override_reason=OVERRIDE_REASONS[0]),        # signed off: counts as in
        RequestItem(identifier="A05", document="e", status=Status.MISSING,
                    manual_override=Override.NOT_APPLICABLE),    # nobody is waiting
        RequestItem(identifier="A06", document="f"),             # never scanned
        RequestItem(identifier="A07", document="g", status=Status.PENDING_SYNC),
    ]
    summary = summarize(items)
    assert summary.total == 6 and summary.not_applicable == 1
    assert summary.received == 2
    assert summary.outstanding == 2
    assert summary.unscanned == 1
    assert summary.counts == {Status.RECEIVED: 2, Status.MISSING: 1, Status.PARTIAL: 1, Status.PENDING_SYNC: 1}
    assert summary.line == SUMMARY_SEPARATOR.join([
        f"{Status.MISSING}: 1", f"{Status.PARTIAL}: 1", f"{Status.PENDING_SYNC}: 1",
        f"{Status.RECEIVED}: 2", f"{UNSCANNED_LABEL}: 1", f"{Override.NOT_APPLICABLE}: 1",
    ])
    assert summarize([]).line == SUMMARY_EMPTY


# ------------------------------------------------------- the derived year ----


def test_a_period_with_a_year_implies_the_year_check(tmp_path):
    from tracker.manifest import derived_date_pattern

    assert derived_date_pattern("TY2025") == r"(?i)\b2025\b"
    assert derived_date_pattern("As of 12/31/2025") == r"(?i)\b2025\b"
    # A Period that names a month asks for that month: a November statement
    # is not the December one, and "12/31/2025" or "December 2025" both are.
    december = derived_date_pattern("Dec 2025")
    for text in ("Statement period 12/01/2025 - 12/31/2025", "December 2025 statement", "as of 12/31/2025"):
        assert re.search(december, text), text
    for text in ("Statement period 11/01/2025 - 11/30/2025", "Nov 2025", "Tax Year 2025"):
        assert not re.search(december, text), text
    assert derived_date_pattern("Current") == ""
    assert derived_date_pattern("Acct 120250") == ""      # not a year

    folder = make_engagement(tmp_path / "S", [
        RequestItem(identifier="A01", document="W-2", period="TY2025", required_keywords=("W-2",)),
        RequestItem(identifier="A02", document="Trust deed", period="Current", required_keywords=("trust",)),
        RequestItem(identifier="A03", document="Typed", period="TY2025", required_keywords=("x",),
                    date_pattern=r"2025|2026"),
    ], scaffold=False)
    rows = {i.identifier: i for i in load_manifest(folder)}
    assert rows["A01"].date_pattern == r"(?i)\b2025\b" and rows["A01"].date_pattern_derived
    assert rows["A02"].date_pattern == "" and not rows["A02"].date_pattern_derived
    assert rows["A03"].date_pattern == r"2025|2026" and not rows["A03"].date_pattern_derived


def test_a_star_in_date_pattern_means_no_year_check():
    from tracker.manifest import NO_DATE_CHECK

    [row] = validated([RequestItem(identifier="A01", document="W-2", period="TY2025",
                                   required_keywords=("W-2",), date_pattern=NO_DATE_CHECK)])
    assert row.date_pattern == "" and not row.date_pattern_derived


def test_a_derived_year_is_a_check_not_a_reason_to_route():
    from tracker.manifest import has_routing_rules

    typed = RequestItem(identifier="A01", document="x", date_pattern=r"\b2025\b")
    derived = RequestItem(identifier="A02", document="x", date_pattern=r"\b2025\b",
                          date_pattern_derived=True)
    keyed = RequestItem(identifier="A03", document="x", any_keywords=("w-2",))
    assert has_routing_rules(typed) and has_routing_rules(keyed)
    assert not has_routing_rules(derived)


# ------------------------------------------- a row per issuer (decision 93) ----

K1_WORDS = ("partner's share of income", "member's share of income")


def k1_rows(*issuers):
    """The generic K-1 row and one row per (identifier, entity) after it."""
    rows = [RequestItem(identifier="F01", document="Schedule K-1s Received",
                        allowed_extensions=("pdf",), any_keywords=K1_WORDS)]
    rows += [RequestItem(identifier=identifier, document=f"Schedule K-1 - {entity}",
                         allowed_extensions=("pdf",), required_keywords=(entity,),
                         any_keywords=K1_WORDS)
             for identifier, entity in issuers]
    return rows


@pytest.mark.parametrize("typed, expected", [
    ("Ashford Holdings, L.P.", "Ashford Holdings LP"),
    ("Ashford Holdings LP", "Ashford Holdings LP"),
    ("  Ashford   Holdings  ", "Ashford Holdings"),
    ("Ashford Holdings | Birch Lane", "Ashford Holdings Birch Lane"),
    ("Ashford + Birch", "Ashford Birch"),
    ("O'Hara & Sons, Inc.", "O'Hara & Sons Inc"),
])
def test_an_entity_name_becomes_one_keyword_a_cell_can_hold(typed, expected):
    """A comma would split the cell into two required keywords; the grammar's
    own two characters would turn a name into alternatives."""
    assert entity_keyword(typed) == expected


def test_two_typings_of_one_entity_make_one_row():
    assert entity_keyword("Ashford Holdings, L.P.") == entity_keyword("Ashford Holdings LP")


def test_an_issuer_name_typed_with_commas_loads_as_one_keyword(tmp_path):
    """The point of normalising before the row is made: read back, the
    row asks for one name and not for two."""
    from tracker.templates import issuer_row, item_from_spec

    folder = make_engagement(tmp_path / "S",
                             [*k1_rows(), item_from_spec(issuer_row("F02", "Ashford Holdings, L.P."))],
                             scaffold=False)
    loaded = {i.identifier: i for i in load_manifest(folder)}

    assert loaded["F02"].required_keywords == ("Ashford Holdings LP",)
    assert loaded["F02"].document == "Schedule K-1 - Ashford Holdings LP"


def test_an_issuer_row_narrows_the_generic_row():
    assert narrowing_rows(k1_rows(("F02", "Ashford Holdings"), ("F03", "Birch Lane"))) == {
        "F01": ("F02", "F03"),
    }


def test_a_row_sharing_no_word_with_the_generic_row_narrows_nothing():
    rows = [*k1_rows(), RequestItem(identifier="C01", document="Mortgage Interest",
                                    required_keywords=("1098",), any_keywords=("1098",))]
    assert narrowing_rows(rows) == {}


def test_two_issuer_rows_whose_names_nest_are_refused_when_the_list_is_validated(tmp_path):
    """Both accept the same K-1, so every one of them would park with
    nothing said about why. The person renames one - and nothing is
    recorded until they do."""
    folder = tmp_path / "S"
    folder.mkdir()
    with pytest.raises(ManifestError) as caught:
        create_engagement(folder, k1_rows(("F02", "Ashford"), ("F03", "Ashford Holdings")))

    assert "F02" in str(caught.value) and "F03" in str(caught.value)
    assert "F01" in str(caught.value), "the row they both narrow is named too"
    assert not ledger.path_for(folder).exists()


def test_two_issuer_names_that_merely_share_a_word_are_allowed():
    check_narrowing_names(k1_rows(("F02", "Ashford Holdings"), ("F03", "Birch Holdings")))


def test_two_unrelated_rows_may_share_a_name(tmp_path):
    """Only rows narrowing the *same* row are compared: an ordinary request
    whose keywords sit inside another's is nobody's issuer."""
    rows = [
        RequestItem(identifier="A01", document="W-2", required_keywords=("Ashford",)),
        RequestItem(identifier="A02", document="1099", required_keywords=("Ashford Holdings",)),
    ]
    folder = make_engagement(tmp_path / "S", rows, scaffold=False)
    assert len(load_manifest(folder)) == 2


def test_a_stored_row_without_the_named_column_reads_as_named():
    """Decision 128, strict by default. A rules event written before the
    mark existed carries no ``named``, and a store column filled from one
    holds null; both read as **named**, so a W-2 in an engagement made last
    season needs the name on the page exactly as a new one does. The record
    owns that default (``RULE_FLAG_DEFAULTS``), not the store."""
    from tracker.manifest import item_from_record
    from tracker.records import RULE_FLAG_DEFAULTS, rule_from_json, rule_to_json

    old = {"identifier": "A01", "document": "W-2", "required_keywords": ["w-2"]}
    assert "named" not in rule_from_json(old)
    assert item_from_record(old).named is True
    assert RULE_FLAG_DEFAULTS["named"] is True

    # And the mark travels whole once it is there, either way round.
    assert rule_to_json(RequestItem(identifier="D01", document="Receipts", named=False))["named"] \
        is False
    assert item_from_record(rule_to_json(
        RequestItem(identifier="D01", document="Receipts", named=False))).named is False


def test_the_named_mark_is_read_as_the_editors_two_words_and_anything_else_is_refused():
    """The editor sends the record's own yes/no words, the catalog sends a
    boolean and a pasted row sends nothing at all; blank is yes, because a
    row nobody marked is a row that needs the name."""
    from tracker.manifest import item_from_fields
    from tracker.records import NO, YES

    base = {"identifier": "A01", "document": "W-2"}
    assert item_from_fields(base, where="Row 1").named is True
    assert item_from_fields({**base, "named": ""}, where="Row 1").named is True
    assert item_from_fields({**base, "named": YES}, where="Row 1").named is True
    assert item_from_fields({**base, "named": NO.upper()}, where="Row 1").named is False
    assert item_from_fields({**base, "named": False}, where="Row 1").named is False
    with pytest.raises(ManifestError, match=f"Row 1: {COL_NAMED} must be"):
        item_from_fields({**base, "named": "maybe"}, where="Row 1")


# --------------------------------------------- decision 142: accepted, not asked ----


def test_summarize_counts_asked_rows_and_also_received_counts_the_rest():
    """``total``, ``outstanding``, ``received`` and ``unscanned`` are about
    asked rows; a not-asked row that received a document is
    ``also_received``, so "N of M are in" never reads 7 of 5; and the word
    for a request nobody has scanned is never said of a row nobody asked
    for."""
    from tracker.manifest import ALSO_RECEIVED_LABEL, NOT_ASKED_LABEL, status_label, summarize

    rows = [
        RequestItem(identifier="A01", document="W-2", status=Status.RECEIVED),
        RequestItem(identifier="A02", document="1099", status=Status.MISSING),
        RequestItem(identifier="A03", document="1098"),                          # asked, unscanned
        RequestItem(identifier="B01", document="SSA-1099", asked=False, status=Status.RECEIVED),
        RequestItem(identifier="B02", document="1099-K", asked=False, status=Status.PARTIAL),
        RequestItem(identifier="B03", document="W-2G", asked=False, status=Status.MISSING),
        RequestItem(identifier="B04", document="1099-C", asked=False),
        RequestItem(identifier="C01", document="1095-A", asked=False,
                    manual_override=Override.NOT_APPLICABLE),
    ]
    summary = summarize(rows)

    assert (summary.total, summary.received, summary.outstanding, summary.unscanned) == (3, 1, 1, 1)
    assert summary.also_received == 2 and summary.not_asked == 2 and summary.not_applicable == 1
    assert summary.counts == {Status.RECEIVED: 1, Status.MISSING: 1}
    assert f"{ALSO_RECEIVED_LABEL}: 2" in summary.line and f"{NOT_ASKED_LABEL}: 2" in summary.line
    assert f"{UNSCANNED_LABEL}: 1" in summary.line

    labels = {row.identifier: status_label(row) for row in rows}
    assert labels["A03"] == UNSCANNED_LABEL
    assert labels["B03"] == labels["B04"] == NOT_ASKED_LABEL
    assert labels["B01"] == Status.RECEIVED and labels["B02"] == Status.PARTIAL
    assert UNSCANNED_LABEL not in {labels[i] for i in ("B01", "B02", "B03", "B04")}


def test_warnings_skip_not_asked_rows():
    """The preparer did not choose a row nobody asked for, so the rules
    warnings say nothing about it; the same row asked is warned about."""
    from tracker.manifest import check_rules

    bare = RequestItem(identifier="A01", document="Anything", row=1)
    assert check_rules([bare])
    assert check_rules([replace(bare, asked=False)]) == []


def test_the_asked_mark_is_read_as_the_named_mark_is():
    """Blank is yes; the two words and a boolean are read; anything else is
    refused with the column named."""
    from tracker.manifest import COL_ASKED, item_from_fields

    assert item_from_fields({"identifier": "A01", "document": "W-2"}, where="Row 1").asked is True
    assert item_from_fields({"identifier": "A01", "document": "W-2", "asked": "no"}, where="Row 1").asked is False
    assert item_from_fields({"identifier": "A01", "document": "W-2", "asked": False}, where="Row 1").asked is False
    with pytest.raises(ManifestError, match=f"Row 1: {COL_ASKED} must be"):
        item_from_fields({"identifier": "A01", "document": "W-2", "asked": "maybe"}, where="Row 1")


def test_a_row_with_no_short_title_derives_one_at_a_whole_word():
    """Decision 144, claim 3. A row with no short title of its own - a
    preparer's own row, a row stored before the field existed - takes the
    first twenty characters of its document title, cut back to the last
    whole word, with the separator it was left hanging on dropped. A title
    that fits is itself; a single word longer than the limit is cut at it.
    A typed one is refused past the limit or where a folder could not have
    it, with the column named."""
    from tracker.manifest import COL_SHORT_TITLE, SHORT_TITLE_MAX, derived_short_title, item_from_record

    assert SHORT_TITLE_MAX == 20
    assert derived_short_title("Schedule K-1 - ABC Partners LLC") == "Schedule K-1 - ABC"
    assert derived_short_title("W-2 Wage Statements - All Employers") == "W-2 Wage Statements"
    assert derived_short_title("1099-INT / 1099-DIV - Interest") == "1099-INT / 1099-DIV"
    assert derived_short_title("Fiduciary, Attorney & Accounting Fees") == "Fiduciary, Attorney"
    assert derived_short_title("Rental Records") == "Rental Records"
    # The twentieth character ends a word when a dot follows it, not a letter.
    assert derived_short_title("Fixed Asset Register.") == "Fixed Asset Register"
    assert derived_short_title("x" * 30) == "x" * 20
    # Exactly twenty, ending at a word: kept whole.
    assert derived_short_title("Brokerage Statements and more") == "Brokerage Statements"

    row = item_from_fields({"identifier": "X01", "document": "Schedule K-1 - ABC Partners LLC"},
                           where="Row 1")
    assert row.short_title == "" and row.short_name == "Schedule K-1 - ABC"
    typed = item_from_fields({"identifier": "X01", "document": "Anything at all",
                              "short_title": "  K-1 ABC  "}, where="Row 1")
    assert typed.short_title == "K-1 ABC" and typed.short_name == "K-1 ABC"
    # A row read out of the record from before the field: blank, derived.
    old = rule_to_json(row)
    del old["short_title"]
    assert item_from_record(old).short_title == ""
    for bad in ("x" * 21, "W-2 / 1099", "Receipts.", "NUL"):
        with pytest.raises(ManifestError, match=f"Row 1: {COL_SHORT_TITLE} "):
            item_from_fields({"identifier": "X01", "document": "Doc", "short_title": bad}, where="Row 1")
