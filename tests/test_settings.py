"""Tests for tracker/settings.py — the clients root, written once, read by all.

The claim: there is exactly one place the app and the scheduled job learn
where the clients live, it is set once, and a typo cannot quietly create an
empty folder for the run to walk for ever.
"""

import json

import pytest

from tracker.settings import (
    ENV_REAL_CORPUS,
    ENV_SETTINGS_DIR,
    KEY_CLIENTS_ROOT,
    SETTINGS_FILENAME,
    SettingsError,
    clients_root,
    real_corpus_dir,
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


def test_a_cleared_folder_box_is_refused_not_recorded_as_the_working_folder(beside_the_app):
    # The eleventh reading: Path("") is the working folder, which is a
    # folder, so a cleared box recorded the app's own folder as the clients
    # root and the real one was gone from the settings.
    for typed in ("", "   "):
        with pytest.raises(SettingsError, match="no folder given"):
            set_clients_root(typed)
    for typed in (".", " . ", "./", "tests/.."):        # the twelfth reading: the working folder by another name
        with pytest.raises(SettingsError, match="working folder itself"):
            set_clients_root(typed)
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


def test_the_real_corpus_is_a_folder_outside_the_repo_or_it_is_nothing(tmp_path, monkeypatch):
    # The firm's redacted documents are never in the tree, so every machine
    # without them - CI included - must get None rather than an error.
    monkeypatch.delenv(ENV_REAL_CORPUS, raising=False)
    assert real_corpus_dir() is None
    monkeypatch.setenv(ENV_REAL_CORPUS, "   ")
    assert real_corpus_dir() is None
    monkeypatch.setenv(ENV_REAL_CORPUS, str(tmp_path / "gone"))
    assert real_corpus_dir() is None
    (tmp_path / "corpus").mkdir()
    monkeypatch.setenv(ENV_REAL_CORPUS, str(tmp_path / "corpus"))
    assert real_corpus_dir() == tmp_path / "corpus"
    (tmp_path / "corpus" / "a document.pdf").write_bytes(b"%PDF-1.4\n")
    monkeypatch.setenv(ENV_REAL_CORPUS, str(tmp_path / "corpus" / "a document.pdf"))
    assert real_corpus_dir() is None                  # a file is not a corpus


def test_the_root_is_stored_absolute_and_a_bare_drive_is_its_root(beside_the_app, monkeypatch):
    import os
    from pathlib import Path

    clients = beside_the_app / "Clients"
    clients.mkdir()
    monkeypatch.chdir(beside_the_app)
    assert set_clients_root("Clients") == clients.resolve()
    if os.name == "nt":
        drive = Path.cwd().drive
        assert set_clients_root(drive) == Path(drive + os.sep)


def test_the_firm_phone_is_written_beside_the_firm_name_and_blank_when_unset(beside_the_app):
    """Decision 117: the firm's telephone number belongs to the firm, not
    to an engagement, so it is kept where the firm's name is - and taken
    as typed, because a firm writes its number its own way."""
    from tracker.settings import KEY_FIRM, KEY_FIRM_PHONE, firm_phone, set_firm, set_firm_phone

    assert firm_phone() == ""
    clients = beside_the_app / "Clients"
    clients.mkdir()
    set_clients_root(clients)
    set_firm("J Park & Associates, CPA")
    assert set_firm_phone("  (555) 010-2020 ext. 4  ") == "(555) 010-2020 ext. 4"
    assert firm_phone() == "(555) 010-2020 ext. 4"

    written = json.loads(settings_path().read_text(encoding="utf-8"))
    assert written[KEY_FIRM_PHONE] == "(555) 010-2020 ext. 4"
    assert written[KEY_FIRM] == "J Park & Associates, CPA"
    assert written[KEY_CLIENTS_ROOT] == str(clients)

    assert set_firm_phone("") == "" and firm_phone() == ""
    assert clients_root() == clients, "clearing the number touches nothing else"
