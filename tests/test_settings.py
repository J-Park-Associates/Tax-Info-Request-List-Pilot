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
    # The twelfth reading: the working folder by another name. The suite
    # runs from the repository, which is the app's own folder from source,
    # and that is refused by name since decision 137 - the check against
    # the working folder it replaced meant nothing in the packaged build.
    for typed in (".", " . ", "./", "tests/.."):
        with pytest.raises(SettingsError, match="holds the app itself"):
            set_clients_root(typed)
    assert clients_root() is None


def test_the_settings_file_is_swapped_in_whole(beside_the_app):
    from tracker.fsio import TEMP_SUFFIX

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
    clients = beside_the_app / "Clients"
    clients.mkdir()
    monkeypatch.chdir(beside_the_app)
    assert set_clients_root("Clients") == clients.resolve()
    # A bare drive letter is that drive's root ("D:" is the drive's current
    # folder to Windows); the system drive's is refused since decision 137,
    # and another drive's is kept - see the tests below.


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


# ------------------------------------------ decision 137: the root cannot swallow the app ----


def test_the_clients_root_cannot_be_the_settings_folder_the_app_folder_or_their_ancestors(
        beside_the_app):
    """Decision 137 (M3): a root that holds the settings file and the store,
    or the app itself, would be walked every two hours, have runs.log and
    status.html written into it, and widen "under the clients root" to the
    app's own files. Refused by name: the settings folder, any folder that
    holds it and any folder inside it, and the app's folder and any folder
    that holds it. A folder beside them is a clients root like any other."""
    from tracker.settings import ROOT_HOLDS_APP, ROOT_HOLDS_SETTINGS, ROOT_INSIDE_SETTINGS, app_dir

    settings = settings_dir()
    (settings / "inside").mkdir(parents=True)
    refused = {
        settings: ROOT_HOLDS_SETTINGS,
        beside_the_app: ROOT_HOLDS_SETTINGS,             # the folder that holds it
        settings / "inside": ROOT_INSIDE_SETTINGS,
        app_dir(): ROOT_HOLDS_APP,
        app_dir().parent: ROOT_HOLDS_APP,
    }
    for folder, sentence in refused.items():
        marker = sentence.split("{root}", 1)[1].split("(", 1)[0].strip()
        with pytest.raises(SettingsError, match=marker):
            set_clients_root(folder)
    assert clients_root() is None
    beside = beside_the_app / "Clients"
    beside.mkdir()
    assert set_clients_root(beside) == beside.resolve()


def test_the_system_drive_root_is_refused_and_another_drive_root_is_kept(beside_the_app):
    """Decision 137 (M3): the system drive's root is the whole machine and
    is refused; another drive's root is a real clients root (the firm's
    ``S:`` convention, a Shared Drive letter) and is kept, with the old
    ``"D:"`` -> ``"D:\\"`` normalisation. Run on Windows, the rule meets the
    machine's real drives; the pure rule is held on every OS."""
    import os
    import string
    from pathlib import Path

    from tracker.settings import ROOT_IS_SYSTEM_DRIVE, app_dir, root_refusal, system_drive_root

    system = system_drive_root()
    marker = ROOT_IS_SYSTEM_DRIVE.split("{root}", 1)[1].split(";", 1)[0].strip()
    with pytest.raises(SettingsError, match=marker):
        set_clients_root(system)
    if os.name == "nt":
        with pytest.raises(SettingsError, match=marker):
            set_clients_root(system.drive)                   # "C:" is the same root
        others = [f"{letter}:" for letter in string.ascii_uppercase
                  if f"{letter}:" != system.drive and Path(f"{letter}:\\").is_dir()]
        for drive in others:                                  # a machine with a second drive
            root = Path(drive + os.sep)
            if root_refusal(root, settings=settings_dir().resolve(), app=app_dir(),
                            system=system) == "":
                assert set_clients_root(drive) == root        # "D:" recorded as "D:\"
    else:
        assert clients_root() is None

    # The rule itself, on any machine: another drive's root is allowed,
    # the system drive's is not, whatever holds the settings and the app.
    if os.name == "nt":
        app = settings = Path(r"C:\Program Files\Tracker")
        system_root, other = Path("C:\\"), Path("S:\\")
    else:
        app = settings = Path("/opt/tracker")
        system_root, other = Path("/"), Path("/mnt/clients")
    assert (root_refusal(system_root, settings=settings, app=app, system=system_root)
            == ROOT_IS_SYSTEM_DRIVE.format(root=system_root))
    assert root_refusal(other, settings=settings, app=app, system=system_root) == ""


def test_the_clients_root_is_judged_by_the_folder_itself_not_its_spelling(beside_the_app):
    """Decision 137's review (F1): the refusals compare the folders
    themselves, so the long-path and administrative-share spellings of the
    system drive, the app's folder and the settings folder are refused like
    their plain names. The admin-share spellings are asked only where this
    machine answers them."""
    import os
    from pathlib import Path

    from tracker.settings import app_dir, system_drive_root

    if os.name != "nt":
        pytest.skip("the \\\\?\\ and C$ spellings are Windows'")
    settings = settings_dir()
    settings.mkdir(parents=True, exist_ok=True)
    drive = system_drive_root().drive                          # "C:"
    letter = drive.rstrip(":")
    spellings = [
        "\\\\?\\" + drive + "\\",
        "\\\\?\\" + str(app_dir()),
        "\\\\?\\" + str(settings.resolve()),
    ]
    for host in ("localhost", "127.0.0.1"):
        share = f"\\\\{host}\\{letter}$\\"
        if Path(share).is_dir():
            spellings += [share, share + str(app_dir())[3:]]
    for typed in spellings:
        with pytest.raises(SettingsError):
            set_clients_root(typed)
    assert clients_root() is None
    clients = beside_the_app / "Clients"
    clients.mkdir()
    assert set_clients_root("\\\\?\\" + str(clients)) is not None   # a real clients folder still is one


def test_a_root_one_level_too_deep_is_refused_and_the_example_root_is_not(beside_the_app):
    """Decision 188 (D-3): a folder inside either tree of a real clients
    root - one holding both trees - is refused, naming the root to choose
    instead. A folder named like a tree is not refused for its name: the
    runbook's own example root is a folder called ``Clients``, and it is a
    root like any other."""
    from tracker.layout import CLIENTS_TREE, PRIVATE_TREE
    from tracker.settings import ROOT_INSIDE_A_TREE

    real = beside_the_app / "Clients"
    (real / CLIENTS_TREE / "Park Family").mkdir(parents=True)
    (real / PRIVATE_TREE / "Park Family").mkdir(parents=True)
    assert set_clients_root(real) == real.resolve()
    for too_deep, tree in [(real / CLIENTS_TREE, CLIENTS_TREE),
                           (real / CLIENTS_TREE / "Park Family", CLIENTS_TREE),
                           (real / PRIVATE_TREE, PRIVATE_TREE),
                           (real / PRIVATE_TREE / "Park Family", PRIVATE_TREE)]:
        with pytest.raises(SettingsError) as refused:
            set_clients_root(too_deep)
        assert str(refused.value).endswith(ROOT_INSIDE_A_TREE.format(
            root=too_deep.resolve(), tree=tree, real=real.resolve())), refused.value
    # A folder beside the trees is not inside one, and a lone tree's name
    # above no pair of trees is a folder like any other.
    (real / "Archive").mkdir()
    assert set_clients_root(real / "Archive") == (real / "Archive").resolve()
    lone = beside_the_app / "Elsewhere" / CLIENTS_TREE
    lone.mkdir(parents=True)
    assert set_clients_root(lone) == lone.resolve()
