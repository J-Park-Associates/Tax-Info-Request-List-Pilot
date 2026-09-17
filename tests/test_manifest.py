"""Tests for tracker/manifest.py — the manifest layer, no OneDrive needed."""

import datetime as dt
import json
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.workbook.workbook import Workbook as WorkbookClass

from tracker.manifest import (
    HEADERS,
    SHEET_NAME,
    ManifestError,
    Override,
    RequestItem,
    Status,
    StatusUpdate,
    create_template,
    load_manifest,
    pending_path,
    write_statuses,
)

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
        allowed_extensions=("pdf", ".CSV"),  # dot + case normalize on load
        min_size_kb=10,
        any_keywords=("statement", "account summary"),
    ),
    RequestItem(
        identifier="B01",
        document="Payroll Register Q4",
        period="Q4 2025",
        allowed_extensions=("xlsx", "csv"),
        manual_override=Override.WAIVED,
    ),
]


@pytest.fixture
def manifest(tmp_path):
    return create_template(tmp_path / "_manifest.xlsx", SAMPLE_ITEMS)


# ---------------------------------------------------------------- loading ----


def test_template_load_roundtrip(manifest):
    items = load_manifest(manifest)
    assert [i.identifier for i in items] == ["A01", "A02", "B01"]

    a01 = items[0]
    assert a01.document == "Dec 2025 Bank Statement"
    assert a01.period == "Dec 2025"
    assert a01.expected_count == 1          # default
    assert a01.min_size_kb == 5             # default
    assert a01.allowed_extensions == ("pdf",)
    assert a01.required_keywords == ("Chase",)
    assert a01.any_keywords == ()
    assert a01.date_pattern.startswith("(?i)december")
    assert a01.manual_override == ""
    assert a01.status == ""
    assert a01.received_date is None
    assert a01.row == 2

    a02 = items[1]
    assert a02.expected_count == 12
    assert a02.min_size_kb == 10
    assert a02.allowed_extensions == ("pdf", "csv")  # normalized
    assert a02.any_keywords == ("statement", "account summary")

    assert items[2].manual_override == Override.WAIVED


def test_template_refuses_overwrite(manifest):
    with pytest.raises(ManifestError, match="Refusing to overwrite"):
        create_template(manifest)


def test_missing_manifest(tmp_path):
    with pytest.raises(ManifestError, match="not found"):
        load_manifest(tmp_path / "nope.xlsx")


def test_missing_column_rejected(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME
    for idx, header in enumerate(h for h in HEADERS if h != "Status"):
        ws.cell(row=1, column=idx + 1, value=header)
    path = tmp_path / "bad.xlsx"
    wb.save(path)
    with pytest.raises(ManifestError, match="missing column.*Status"):
        load_manifest(path)


def _write_cell(path, row, header, value):
    wb = load_workbook(path)
    ws = wb[SHEET_NAME]
    col = HEADERS.index(header) + 1
    ws.cell(row=row, column=col, value=value)
    wb.save(path)


def test_duplicate_identifier_rejected(manifest):
    _write_cell(manifest, 3, "Identifier", "A01")
    with pytest.raises(ManifestError, match="Duplicate identifier 'A01'.*rows 2 and 3"):
        load_manifest(manifest)


def test_bad_regex_rejected(manifest):
    _write_cell(manifest, 2, "Date Pattern", "([unclosed")
    with pytest.raises(ManifestError, match="Row 2.*not a valid regex"):
        load_manifest(manifest)


def test_bad_expected_count_rejected(manifest):
    _write_cell(manifest, 2, "Expected Count", "twelve")
    with pytest.raises(ManifestError, match="Row 2.*whole number"):
        load_manifest(manifest)


def test_unknown_status_rejected(manifest):
    _write_cell(manifest, 2, "Status", "Done-ish")
    with pytest.raises(ManifestError, match="Row 2.*Status must be one of"):
        load_manifest(manifest)


def test_unknown_override_rejected(manifest):
    _write_cell(manifest, 2, "Manual Override", "Maybe")
    with pytest.raises(ManifestError, match="Row 2.*Manual Override"):
        load_manifest(manifest)


def test_blank_rows_skipped(manifest):
    _write_cell(manifest, 6, "Identifier", "C01")  # row 5 left entirely blank
    _write_cell(manifest, 6, "Document", "Trial Balance")
    items = load_manifest(manifest)
    assert [i.identifier for i in items] == ["A01", "A02", "B01", "C01"]
    assert items[-1].row == 6


# ------------------------------------------------------------- write-back ----


def test_write_statuses_roundtrip(manifest):
    updates = {
        "A01": StatusUpdate(
            status=Status.RECEIVED,
            file_count=1,
            received_date=dt.date(2026, 7, 8),
        ),
        "A02": StatusUpdate(
            status=Status.PARTIAL,
            file_count=7,
            validation_notes="7 of 12 monthly statements received",
        ),
    }
    assert write_statuses(manifest, updates) is True

    items = {i.identifier: i for i in load_manifest(manifest)}
    assert items["A01"].status == Status.RECEIVED
    assert items["A01"].received_date == dt.date(2026, 7, 8)
    assert items["A01"].file_count == 1
    assert items["A02"].status == Status.PARTIAL
    assert items["A02"].file_count == 7
    assert "7 of 12" in items["A02"].validation_notes
    # untouched rows and accountant columns intact
    assert items["B01"].status == ""
    assert items["A01"].required_keywords == ("Chase",)


def test_write_unknown_identifier_dropped(manifest, caplog):
    assert write_statuses(manifest, {"Z99": StatusUpdate(status=Status.MISSING)}) is True
    assert "Z99" in caplog.text
    assert not pending_path(manifest).exists()


def test_locked_write_defers_to_sidecar(manifest, monkeypatch):
    def locked_save(self, filename):
        raise PermissionError(f"[Errno 13] locked: {filename}")

    monkeypatch.setattr(WorkbookClass, "save", locked_save)
    updates = {"A01": StatusUpdate(status=Status.MISSING, validation_notes="no files")}
    assert write_statuses(manifest, updates, retries=2, retry_delay=0.01) is False

    sidecar = pending_path(manifest)
    assert sidecar.exists()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["A01"]["status"] == Status.MISSING


def test_pending_sidecar_merged_and_cleared(manifest):
    pending_path(manifest).write_text(
        json.dumps(
            {
                "A01": {  # stale: superseded by the new update below
                    "status": Status.MISSING,
                    "file_count": 0,
                    "received_date": None,
                    "validation_notes": "",
                },
                "B01": {  # only in sidecar: must still be applied
                    "status": Status.PENDING_SYNC,
                    "file_count": 1,
                    "received_date": None,
                    "validation_notes": "cloud-only placeholder",
                },
            }
        ),
        encoding="utf-8",
    )
    new = {
        "A01": StatusUpdate(
            status=Status.RECEIVED, file_count=1, received_date=dt.date(2026, 7, 8)
        )
    }
    assert write_statuses(manifest, new) is True
    assert not pending_path(manifest).exists()

    items = {i.identifier: i for i in load_manifest(manifest)}
    assert items["A01"].status == Status.RECEIVED  # new beat stale sidecar
    assert items["B01"].status == Status.PENDING_SYNC
    assert "placeholder" in items["B01"].validation_notes


def test_corrupt_sidecar_quarantined(manifest, caplog):
    pending_path(manifest).write_text("{not json", encoding="utf-8")
    assert write_statuses(manifest, {"A01": StatusUpdate(status=Status.MISSING)}) is True
    assert not pending_path(manifest).exists()
    assert pending_path(manifest).with_suffix(".corrupt.json").exists()
    assert "Unreadable pending sidecar" in caplog.text


# -------------------------------------------------------- identifier safety ----


def _manifest_with_identifiers(tmp_path, *identifiers):
    items = [
        RequestItem(identifier=ident, document=f"Doc {n}")
        for n, ident in enumerate(identifiers, start=1)
    ]
    return create_template(tmp_path / "_manifest.xlsx", items)


@pytest.mark.parametrize("identifier", ["A:01", "A/01", "A?1", 'B"1', "A01.", "A<1>"])
def test_identifier_that_cannot_name_a_folder_is_rejected(tmp_path, identifier):
    # The identifier is the folder-name prefix the scanner matches back on.
    # One the filesystem would alter is a permanent "folder not found".
    path = _manifest_with_identifiers(tmp_path, identifier)
    with pytest.raises(ManifestError, match="Identifier"):
        load_manifest(path)


def test_identifiers_differing_only_by_case_are_duplicates(tmp_path):
    # Windows folder names are case-insensitive: "A01" and "a01" would fight
    # over one folder, so they are the same identifier.
    path = _manifest_with_identifiers(tmp_path, "A01", "a01")
    with pytest.raises(ManifestError, match="Duplicate identifier"):
        load_manifest(path)


# ------------------------------------------------------------ atomic saves ----


def test_a_crash_mid_save_leaves_the_previous_manifest_intact(manifest, monkeypatch):
    # openpyxl streams straight into the target; a killed task mid-write
    # used to leave a manifest Excel could not open. The save now lands
    # beside the file and is swapped in whole, or not at all.
    def crash(self, filename):
        Path(str(filename)).write_bytes(b"PK\x03\x04 half a zip")
        raise KeyboardInterrupt

    monkeypatch.setattr(WorkbookClass, "save", crash)
    with pytest.raises(KeyboardInterrupt):
        write_statuses(manifest, {"A01": StatusUpdate(status=Status.MISSING)}, retries=1)

    assert not manifest.with_name(manifest.name + ".tmp").exists()
    assert [i.identifier for i in load_manifest(manifest)] == ["A01", "A02", "B01"]


# --------------------------------------------------------- engagement sheet ----


def test_the_engagement_sheet_round_trips(tmp_path):
    from tracker.manifest import EngagementInfo, load_engagement_info, write_engagement_info

    info = EngagementInfo(client="John Smith", name="Smiths 2025", link="https://drive.example/abc",
                          due=dt.date(2026, 4, 15), sender="Jason Park", firm="J Park",
                          reminders=False, active=True)
    path = create_template(tmp_path / "_manifest.xlsx", SAMPLE_ITEMS, info)
    assert load_engagement_info(path) == info
    assert [i.identifier for i in load_manifest(path)] == ["A01", "A02", "B01"]  # Requests untouched

    write_engagement_info(path, EngagementInfo(client="Jane", active=False))
    loaded = load_engagement_info(path)
    assert loaded.client == "Jane" and loaded.active is False and loaded.reminders is True


def test_a_manifest_without_the_sheet_loads_as_defaults(manifest):
    from openpyxl import load_workbook as lw
    from tracker.manifest import EngagementInfo, load_engagement_info

    wb = lw(manifest)
    del wb["Engagement"]
    wb.save(manifest)
    assert load_engagement_info(manifest) == EngagementInfo()


def test_yes_no_cells_are_forgiving_but_not_guessing(manifest):
    from openpyxl import load_workbook as lw
    from tracker.manifest import load_engagement_info

    def set_cell(label, value):
        wb = lw(manifest)
        for row in wb["Engagement"].iter_rows(min_row=1, max_col=2):
            if row[0].value == label:
                row[1].value = value
        wb.save(manifest)

    set_cell("Reminders", "No ")
    assert load_engagement_info(manifest).reminders is False
    set_cell("Active", "TRUE")
    assert load_engagement_info(manifest).active is True
    set_cell("Active", "later")
    with pytest.raises(ManifestError, match="Active must be yes or no"):
        load_engagement_info(manifest)


def test_add_any_keyword_appends_once_and_names_a_missing_row(manifest):
    from tracker.manifest import add_any_keyword

    assert add_any_keyword(manifest, "A01", "Schedule E") is True
    assert add_any_keyword(manifest, "A01", "schedule e") is False     # case-insensitive
    assert load_manifest(manifest)[0].any_keywords == ("Schedule E",)
    assert add_any_keyword(manifest, "A01", "   ") is False
    with pytest.raises(ManifestError, match="No request 'Z99'"):
        add_any_keyword(manifest, "Z99", "x")


# ------------------------------------------------------ allowed extensions ----


def test_a_blank_allowed_extensions_means_the_safe_default_not_anything(tmp_path):
    from openpyxl import load_workbook as lw
    from tracker.manifest import DEFAULT_EXTENSIONS

    path = create_template(tmp_path / "_manifest.xlsx", [RequestItem(identifier="A01", document="W-2")])
    wb = lw(path)
    wb["Requests"].cell(row=2, column=5).value = None   # the accountant cleared the cell
    wb.save(path)
    assert load_manifest(path)[0].allowed_extensions == DEFAULT_EXTENSIONS


def test_accepting_any_file_type_has_to_be_said_with_a_star(tmp_path):
    from openpyxl import load_workbook as lw

    path = create_template(tmp_path / "_manifest.xlsx", [RequestItem(identifier="A01", document="W-2")])
    # An item built with no extensions means anything; the template writes "*"
    # so the workbook says so and the loader reads it back the same way.
    wb = lw(path)
    assert wb["Requests"].cell(row=2, column=5).value == "*"
    wb.close()
    assert load_manifest(path)[0].allowed_extensions == ()


# ------------------------------------------------------------------ check ----


def test_check_manifest_reports_problems_with_their_row(manifest):
    from openpyxl import load_workbook as lw
    from tracker.manifest import check_manifest

    assert check_manifest(manifest).ok
    wb = lw(manifest)
    wb["Requests"].cell(row=3, column=9, value="(unclosed")   # A02 Date Pattern
    wb.save(manifest)
    result = check_manifest(manifest)
    assert not result.ok
    assert result.problems[0].startswith("Row 3: Date Pattern is not a valid regex")


def test_check_manifest_warns_about_rows_the_rules_cannot_act_on(tmp_path):
    from tracker.manifest import _save_pending, check_manifest

    path = create_template(tmp_path / "_manifest.xlsx", [
        RequestItem(identifier="A01", document="Anything goes"),              # no rule, "*"
        RequestItem(identifier="A02", document="W-2", required_keywords=("W-2",),
                    allowed_extensions=("pdf",)),
        RequestItem(identifier="A03", document="Waived", manual_override=Override.WAIVED),
    ])
    _save_pending(path, {"A02": StatusUpdate(status=Status.RECEIVED)})
    result = check_manifest(path)
    assert result.ok
    assert [w[:14] for w in result.warnings] == ["Row 2 (A01): n", "Row 2 (A01): A", "_manifest.pend"]
    assert "never be filed automatically" in result.warnings[0]
    assert "any file type counts" in result.warnings[1]
    assert "close Excel and re-scan" in result.warnings[2]


# --------------------------------------------------------------- summary ----


def test_summarize_is_the_one_count():
    from tracker.manifest import summarize

    items = [
        RequestItem(identifier="A01", document="a", status=Status.RECEIVED),
        RequestItem(identifier="A02", document="b", status=Status.MISSING),
        RequestItem(identifier="A03", document="c", status=Status.PARTIAL),
        RequestItem(identifier="A04", document="d", status=Status.FAILED,
                    manual_override=Override.ACCEPTED),          # signed off: counts as in
        RequestItem(identifier="A05", document="e", status=Status.MISSING,
                    manual_override=Override.WAIVED),            # nobody is waiting
        RequestItem(identifier="A06", document="f"),             # never scanned
        RequestItem(identifier="A07", document="g", status=Status.PENDING_SYNC),
    ]
    summary = summarize(items)
    assert summary.total == 6 and summary.waived == 1
    assert summary.received == 2
    assert summary.outstanding == 2
    assert summary.unscanned == 1
    assert summary.counts == {"Received": 2, "Missing": 1, "Partial": 1, "Pending Sync": 1}
    assert summary.line == "Missing: 1 · Partial: 1 · Pending Sync: 1 · Received: 2 · Requested: 1 · Waived: 1"
    assert summarize([]).line == "no requests"


# ------------------------------------------------------- the derived year ----


def test_a_period_with_a_year_implies_the_year_check(tmp_path):
    from tracker.manifest import derived_date_pattern

    assert derived_date_pattern("TY2025") == r"(?i)\b2025\b"
    assert derived_date_pattern("Dec 2025") == r"(?i)\b2025\b"
    assert derived_date_pattern("As of 12/31/2025") == r"(?i)\b2025\b"
    assert derived_date_pattern("Current") == ""
    assert derived_date_pattern("Acct 120250") == ""      # not a year

    path = create_template(tmp_path / "_manifest.xlsx", [
        RequestItem(identifier="A01", document="W-2", period="TY2025", required_keywords=("W-2",)),
        RequestItem(identifier="A02", document="Trust deed", period="Current", required_keywords=("trust",)),
        RequestItem(identifier="A03", document="Typed", period="TY2025", required_keywords=("x",),
                    date_pattern=r"2025|2026"),
    ])
    rows = {i.identifier: i for i in load_manifest(path)}
    assert rows["A01"].date_pattern == r"(?i)\b2025\b" and rows["A01"].date_pattern_derived
    assert rows["A02"].date_pattern == "" and not rows["A02"].date_pattern_derived
    assert rows["A03"].date_pattern == r"2025|2026" and not rows["A03"].date_pattern_derived


def test_a_star_in_date_pattern_means_no_year_check(tmp_path):
    from openpyxl import load_workbook as lw

    path = create_template(tmp_path / "_manifest.xlsx", [
        RequestItem(identifier="A01", document="W-2", period="TY2025", required_keywords=("W-2",)),
    ])
    wb = lw(path)
    wb["Requests"].cell(row=2, column=9, value="*")
    wb.save(path)
    [row] = load_manifest(path)
    assert row.date_pattern == "" and not row.date_pattern_derived


def test_a_derived_year_is_a_check_not_a_reason_to_route():
    from tracker.manifest import has_routing_rules

    typed = RequestItem(identifier="A01", document="x", date_pattern=r"\b2025\b")
    derived = RequestItem(identifier="A02", document="x", date_pattern=r"\b2025\b",
                          date_pattern_derived=True)
    keyed = RequestItem(identifier="A03", document="x", any_keywords=("w-2",))
    assert has_routing_rules(typed) and has_routing_rules(keyed)
    assert not has_routing_rules(derived)
