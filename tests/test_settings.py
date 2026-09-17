"""Tests for tracker/settings.py — the clients root, written once, read by all.

The claim: there is exactly one place the app and the scheduled job learn
where the clients live, it is set once, and a typo cannot quietly create an
empty folder for the run to walk for ever.
"""

import json

import pytest

from tracker.settings import (
    KEY_CLIENTS_ROOT,
    ENV_SETTINGS_DIR,
    SETTINGS_FILENAME,
    SettingsError,
    clients_root,
    set_clients_root,
    settings_dir,
    settings_path,
)


@pytest.fixture
def beside_the_app(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    return tmp_path


def test_nothing_set_means_none_not_a_guess(beside_the_app):
    assert clients_root() is None
    assert settings_dir() == beside_the_app / "app"
    assert settings_path().name == SETTINGS_FILENAME


def test_the_root_is_written_once_and_read_back(beside_the_app):
    clients = beside_the_app / "Clients"
    clients.mkdir()
    assert set_clients_root(clients) == clients
    assert clients_root() == clients
    assert json.loads(settings_path().read_text(encoding="utf-8")) == {KEY_CLIENTS_ROOT: str(clients)}


def test_a_folder_that_does_not_exist_is_refused(beside_the_app):
    with pytest.raises(SettingsError, match="not a folder"):
        set_clients_root(beside_the_app / "Clientz")
    assert clients_root() is None


def test_the_settings_file_is_swapped_in_whole(beside_the_app):
    from tracker.manifest import TEMP_SUFFIX

    clients = beside_the_app / "Clients"
    clients.mkdir()
    set_clients_root(clients)
    assert list(settings_path().parent.glob(f"*{TEMP_SUFFIX}")) == []
    assert clients_root() == clients


def test_an_unreadable_settings_file_is_an_error_not_a_default(beside_the_app):
    settings_path().parent.mkdir(parents=True)
    settings_path().write_text("{not json", encoding="utf-8")
    with pytest.raises(SettingsError, match="could not be read"):
        clients_root()
