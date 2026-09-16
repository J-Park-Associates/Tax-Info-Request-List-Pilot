"""Tests for tracker/registry.py — a typo must never silently skip a client."""

import datetime as dt

import pytest

from tracker.registry import (
    Engagement,
    RegistryError,
    create_registry_template,
    load_registry,
)

GOOD = """
root: /clients
defaults:
  firm: J Park & Associates, CPA
  sender: Jason Park
  reminders: true
engagements:
  - path: Smith Family 2025
    client: John Smith
    link: https://drive.example/abc
    due: 2026-03-15
  - path: Acme Corp TY2025
    client: Dana Lee
    reminders: false
  - path: /elsewhere/Old Client 2024
    active: false
"""


def registry(tmp_path, text=GOOD, name="engagements.yaml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return load_registry(path)


def test_entries_inherit_defaults(tmp_path):
    smith = registry(tmp_path).engagements[0]
    assert smith.firm == "J Park & Associates, CPA"
    assert smith.sender == "Jason Park"
    assert smith.client == "John Smith"
    assert smith.due == dt.date(2026, 3, 15)


def test_an_entry_overrides_the_default(tmp_path):
    acme = registry(tmp_path).engagements[1]
    assert acme.reminders is False
    assert acme.firm == "J Park & Associates, CPA", "unset fields still inherit"


def test_relative_paths_hang_off_root_and_absolute_ones_do_not(tmp_path):
    loaded = registry(tmp_path)
    assert loaded.engagements[0].path.as_posix() == "/clients/Smith Family 2025"
    assert loaded.engagements[2].path.as_posix() == "/elsewhere/Old Client 2024"


def test_without_root_paths_are_taken_as_given(tmp_path):
    loaded = registry(tmp_path, "engagements:\n  - path: Smith 2025\n")
    assert loaded.engagements[0].path.as_posix() == "Smith 2025"


def test_inactive_engagements_are_kept_but_not_active(tmp_path):
    loaded = registry(tmp_path)
    assert len(loaded.engagements) == 3
    assert [e.label for e in loaded.active] == ["Smith Family 2025", "Acme Corp TY2025"]


def test_yaml_dates_are_accepted_as_well_as_strings(tmp_path):
    """PyYAML parses an unquoted 2026-03-15 into a date object already."""
    loaded = registry(tmp_path, "engagements:\n  - path: A\n    due: 2026-03-15\n")
    assert loaded.engagements[0].due == dt.date(2026, 3, 15)


def test_find_matches_label_or_path(tmp_path):
    loaded = registry(tmp_path)
    assert [e.label for e in loaded.find("smith")] == ["Smith Family 2025"]
    assert [e.label for e in loaded.find("/elsewhere")] == ["Old Client 2024"]
    assert loaded.find("nobody") == []


def test_label_falls_back_to_the_folder_name(tmp_path):
    loaded = registry(tmp_path, "engagements:\n  - path: /x/Smith 2025\n"
                                "    name: Smith Family Individual\n")
    assert loaded.engagements[0].label == "Smith Family Individual"
    assert Engagement(path=loaded.engagements[0].path).label == "Smith 2025"


# ------------------------------------------------------------ failing loud ----


def test_a_missing_registry_is_an_error(tmp_path):
    with pytest.raises(RegistryError, match="no registry at"):
        load_registry(tmp_path / "nope.yaml")


def test_an_empty_registry_is_an_error(tmp_path):
    with pytest.raises(RegistryError, match="empty"):
        registry(tmp_path, "\n")


def test_no_engagements_is_an_error(tmp_path):
    with pytest.raises(RegistryError, match="no engagements listed"):
        registry(tmp_path, "defaults:\n  firm: X\n")


def test_a_misspelled_key_is_rejected_not_ignored(tmp_path):
    """Silently ignoring 'reminder' would mean nobody ever gets chased."""
    with pytest.raises(RegistryError, match="reminder"):
        registry(tmp_path, "engagements:\n  - path: A\n    reminder: true\n")


def test_a_misspelled_top_level_key_is_rejected(tmp_path):
    with pytest.raises(RegistryError, match="engagments"):
        registry(tmp_path, "engagments:\n  - path: A\n")


def test_a_missing_path_is_an_error(tmp_path):
    with pytest.raises(RegistryError, match="path is required"):
        registry(tmp_path, "engagements:\n  - client: John\n")


def test_a_bad_date_names_the_engagement(tmp_path):
    with pytest.raises(RegistryError, match="Smith 2025.*YYYY-MM-DD"):
        registry(tmp_path, "engagements:\n  - path: Smith 2025\n    due: next friday\n")


def test_a_non_boolean_flag_is_an_error(tmp_path):
    with pytest.raises(RegistryError, match="must be true or false"):
        registry(tmp_path, "engagements:\n  - path: A\n    reminders: maybe\n")


def test_a_duplicated_path_is_an_error(tmp_path):
    """The same folder twice means filing and scanning it twice per run."""
    with pytest.raises(RegistryError, match="repeats the path"):
        registry(tmp_path, "engagements:\n  - path: A\n  - path: A\n")


def test_malformed_yaml_is_reported_as_such(tmp_path):
    with pytest.raises(RegistryError, match="not valid YAML"):
        registry(tmp_path, "engagements:\n  - path: [unclosed\n")


def test_missing_folders_are_not_rejected_at_load_time(tmp_path):
    """One mistyped path must not stop the other clients from being processed."""
    loaded = registry(tmp_path, "engagements:\n  - path: /no/such/folder\n")
    assert loaded.engagements[0].path.as_posix() == "/no/such/folder"


# ------------------------------------------------------------------ template ----


def test_the_starter_registry_is_valid_and_loads(tmp_path):
    path = create_registry_template(tmp_path / "engagements.yaml")
    loaded = load_registry(path)
    assert [e.label for e in loaded.engagements] == ["Smith Family 2025"]
    assert loaded.engagements[0].firm == "J Park & Associates, CPA"


def test_the_template_never_clobbers_a_live_registry(tmp_path):
    path = tmp_path / "engagements.yaml"
    path.write_text(GOOD, encoding="utf-8")
    with pytest.raises(RegistryError, match="Refusing to overwrite"):
        create_registry_template(path)
    assert path.read_text(encoding="utf-8") == GOOD
