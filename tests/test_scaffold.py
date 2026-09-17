"""Tests for tracker/scaffold.py — folder scaffolding, no OneDrive needed."""

import pytest

from tracker.manifest import ManifestError, Override, RequestItem, create_template
from tracker.scaffold import (
    MANIFEST_FILENAME,
    README_NAME,
    PBC_DIR_NAME,
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
    SHARED_DIR_NAME,
    assign_folders,
    folder_name_for,
    matches_identifier,
    sanitize_component,
    scaffold_engagement,
)

ITEMS = [
    RequestItem(identifier="A01", document="Dec 2025 Bank Statement", period="Dec 2025"),
    RequestItem(
        identifier="A02",
        document="Monthly Bank Statements FY2025",
        period="FY2025",
        expected_count=12,
    ),
    RequestItem(
        identifier="B01",
        document='Q4: A/R "Aging" <Final>?',  # illegal chars everywhere
    ),
    RequestItem(
        identifier="C01",
        document="Fixed Asset Register.",  # trailing dot is illegal on Windows
        manual_override=Override.WAIVED,
    ),
]


@pytest.fixture
def engagement(tmp_path):
    eng = tmp_path / "TY2025 1040"
    eng.mkdir()
    create_template(eng / MANIFEST_FILENAME, ITEMS)
    return eng


# ------------------------------------------------------------ name rules ----


def test_sanitize_component():
    assert sanitize_component('Q4: A/R "Aging" <Final>?') == 'Q4- A-R -Aging- -Final--'
    assert sanitize_component("Fixed Asset Register.") == "Fixed Asset Register"
    assert sanitize_component("  spaced   out  ") == "spaced out"
    assert sanitize_component("12/31/2025") == "12-31-2025"


def test_folder_names_are_windows_safe():
    for item in ITEMS:
        name = folder_name_for(item)
        assert not set('\\/:*?"<>|') & set(name)
        assert not name.endswith((".", " "))
        assert name.startswith(f"{item.identifier} - ")


def test_matches_identifier_boundaries():
    assert matches_identifier("A01 - Dec 2025 Bank Statement", "A01")
    assert matches_identifier("a01 - renamed by client", "A01")  # case-insensitive
    assert matches_identifier("A01-whatever", "A01")
    assert matches_identifier("A01", "A01")
    assert not matches_identifier("A10 - Something", "A1")   # boundary: '0' is alnum
    assert not matches_identifier("A012", "A01")
    assert not matches_identifier("XA01 - Nope", "A01")
    assert not matches_identifier("A01x", "A01")


def test_assign_folders_longest_identifier_wins(tmp_path):
    (tmp_path / "A01 - Bank").mkdir()
    (tmp_path / "A01-B - Loan Docs").mkdir()
    assigned = assign_folders(tmp_path, ["A01", "A01-B"])
    assert [p.name for p in assigned["A01"]] == ["A01 - Bank"]
    assert [p.name for p in assigned["A01-B"]] == ["A01-B - Loan Docs"]


# -------------------------------------------------------------- scaffold ----


def test_creates_folders_and_readme(engagement):
    result = scaffold_engagement(engagement, contact="J Park & Associates")
    shared = engagement / SHARED_DIR_NAME
    prepared = engagement / PREPARED_DIR_NAME

    # Client side: one drop folder plus the place their originals are kept.
    assert shared.is_dir()
    assert (shared / PBC_DIR_NAME).is_dir()
    assert not any(p.is_dir() and p.name.startswith("A01") for p in shared.iterdir())
    # Firm side: one folder per request, plus somewhere for the unclear.
    assert (prepared / REVIEW_DIR_NAME).is_dir()
    assert [p.name for p in result.created] == [
        "A01 - Dec 2025 Bank Statement",
        "A02 - Monthly Bank Statements FY2025",
        "B01 - Q4- A-R -Aging- -Final--",
    ]
    assert result.waived == ["C01"]
    assert not (prepared / "C01 - Fixed Asset Register").exists()

    readme = (shared / README_NAME).read_text(encoding="utf-8")
    assert "A01 - Dec 2025 Bank Statement" in readme
    assert "[12 files expected]" in readme
    assert "C01" not in readme                    # waived items dropped
    assert "J Park & Associates" in readme
    assert "Google Docs" in readme                # export-first guidance


def test_idempotent_rerun_creates_nothing(engagement):
    scaffold_engagement(engagement)
    result = scaffold_engagement(engagement)
    assert result.created == []
    assert sorted(result.existing) == ["A01", "A02", "B01"]


def test_recreates_deleted_folder(engagement):
    scaffold_engagement(engagement)
    (engagement / PREPARED_DIR_NAME / "A01 - Dec 2025 Bank Statement").rmdir()
    result = scaffold_engagement(engagement)
    assert [p.name for p in result.created] == ["A01 - Dec 2025 Bank Statement"]


def test_client_rename_with_prefix_not_duplicated(engagement):
    scaffold_engagement(engagement)
    prepared = engagement / PREPARED_DIR_NAME
    (prepared / "A01 - Dec 2025 Bank Statement").rename(prepared / "A01 - bank stuff")

    result = scaffold_engagement(engagement)
    assert result.created == []
    assert "A01" in result.existing
    assert sum(1 for p in prepared.iterdir() if p.name.startswith("A01")) == 1


def test_existing_client_files_never_touched(engagement):
    scaffold_engagement(engagement)
    folder = engagement / PREPARED_DIR_NAME / "A01 - Dec 2025 Bank Statement"
    client_file = folder / "chase_dec_2025.pdf"
    client_file.write_bytes(b"%PDF-1.7 fake")

    scaffold_engagement(engagement)
    assert client_file.read_bytes() == b"%PDF-1.7 fake"


def test_waived_folder_left_alone_if_it_exists(engagement):
    # Client already uploaded to C01 before the item was waived.
    prepared = engagement / PREPARED_DIR_NAME
    prepared.mkdir()
    stale = prepared / "C01 - Fixed Asset Register"
    stale.mkdir()
    (stale / "far.xlsx").write_bytes(b"data")

    result = scaffold_engagement(engagement)
    assert result.waived == ["C01"]
    assert (stale / "far.xlsx").exists()          # never deleted


def test_readme_refreshed_on_rerun(engagement):
    scaffold_engagement(engagement)
    readme = engagement / SHARED_DIR_NAME / README_NAME
    readme.write_text("client scribbled over this", encoding="utf-8")

    scaffold_engagement(engagement)
    assert "WHAT WE STILL NEED" in readme.read_text(encoding="utf-8")


def test_missing_manifest_raises(tmp_path):
    with pytest.raises(ManifestError, match="not found"):
        scaffold_engagement(tmp_path)


def test_the_review_folder_is_never_assigned_to_an_identifier(tmp_path):
    # "00 - Needs Review" starts with "00"; an identifier "00" must not
    # claim it and count every parked file as its own.
    (tmp_path / REVIEW_DIR_NAME).mkdir()
    (tmp_path / "00 - Opening Balances").mkdir()
    assigned = assign_folders(tmp_path, ["00"])
    assert [p.name for p in assigned["00"]] == ["00 - Opening Balances"]


def test_the_readme_contact_comes_from_the_engagement_sheet(tmp_path):
    from tracker.manifest import EngagementInfo, RequestItem, create_template

    folder = tmp_path / "Smith 2025"
    folder.mkdir()
    create_template(folder / MANIFEST_FILENAME, [RequestItem(identifier="A01", document="W-2")],
                    EngagementInfo(firm="J Park & Associates, CPA"))
    result = scaffold_engagement(folder)
    assert "Questions? Contact J Park & Associates, CPA." in result.readme.read_text(encoding="utf-8")
    result = scaffold_engagement(folder, contact="Someone Else")
    assert "Contact Someone Else." in result.readme.read_text(encoding="utf-8")
