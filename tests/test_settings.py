"""Tests for tracker/settings.py — the clients root, written once, read by all.

The claim: there is exactly one place the app and the scheduled job learn
where the clients live, it is set once, and a typo cannot quietly create an
empty folder for the run to walk for ever.
"""

import errno
import json
from pathlib import Path

import pytest

from tracker import settings as data_rules
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
        # A second local drive only: a letter mapped to a share (the firm's
        # S:) resolves to its \\server\share path, which is the network
        # rule's case, not this one (the pilot's Windows check, P29).
        from tracker.settings import DRIVE_FIXED, drive_type
        others = [f"{letter}:" for letter in string.ascii_uppercase
                  if f"{letter}:" != system.drive and Path(f"{letter}:\\").is_dir()
                  and drive_type(Path(f"{letter}:\\")) == DRIVE_FIXED]
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


def test_the_error_log_lives_beside_the_tracker_database(beside_the_app, monkeypatch):
    # Decision 193, the lane's ruling: beside the store, the folder 189's
    # pass-order.json uses, so it moves wherever the store moves - and
    # never in either client tree.
    import logging

    from tracker import store
    from tracker.settings import ERROR_LOG_FILENAME, error_log, error_log_path

    elsewhere = beside_the_app / "data" / store.STORE_FILENAME
    monkeypatch.setenv(store.ENV_STORE, str(elsewhere))
    assert error_log_path() == elsewhere.parent / ERROR_LOG_FILENAME
    with error_log() as path:
        logging.getLogger("tracker.test").warning("a fabricated warning")
    assert path == elsewhere.parent / ERROR_LOG_FILENAME
    assert "a fabricated warning" in path.read_text(encoding="utf-8")
    assert not (settings_dir() / ERROR_LOG_FILENAME).exists()


def test_an_error_log_that_cannot_be_written_never_spills_kept_words_to_stderr(
        beside_the_app, monkeypatch, capfd):
    """Decision 190's landing review, SF1: with the log unwritable, logging's
    own handleError would print the record's arguments - the kept error's
    whole words - to stderr. The handler says one fixed line instead."""
    import logging

    from tracker import errors, store
    from tracker.layout import CLIENTS_TREE
    from tracker.settings import ERROR_LOG_FILENAME, ERROR_LOG_NOT_WRITTEN, error_log

    quoted = f"/{CLIENTS_TREE}/Sample Household/Drop files here/W2.pdf"
    elsewhere = beside_the_app / "data" / store.STORE_FILENAME
    monkeypatch.setenv(store.ENV_STORE, str(elsewhere))
    (elsewhere.parent / ERROR_LOG_FILENAME).mkdir(parents=True)     # a folder: never writable as a file
    monkeypatch.setattr(logging, "raiseExceptions", True)
    capfd.readouterr()
    with error_log("tracker") as path:
        errors.keep("probe", ValueError(quoted), name="W2.pdf")
    err = capfd.readouterr().err
    assert quoted not in err and "W2.pdf" not in err, err
    said = err.strip().splitlines()
    head, tail = ERROR_LOG_NOT_WRITTEN.format(name=path.name, kind="\0").split("\0")
    assert len(said) == 1 and said[0].startswith(head) and said[0].endswith(tail), err


def test_the_error_log_is_none_when_the_data_home_cannot_be_had(monkeypatch):
    """Decision 186 on 193: the error log sits beside the store, in the
    data home; with no data home there is no log, and the block still runs
    rather than raising before the command can say why."""
    import logging

    from tracker import store
    from tracker.settings import ENV_DATA_HOME, error_log

    monkeypatch.delenv(store.ENV_STORE, raising=False)
    monkeypatch.setenv(ENV_DATA_HOME, "relative-data")
    with error_log() as path:
        logging.getLogger("tracker.test").warning("a fabricated warning")
    assert path is None


# ------------------------------------------ decision 185: the suite's own folder ----


def test_one_rule_says_what_lies_inside_the_app_folder(tmp_path, monkeypatch):
    """The report tools ask this before writing: a file in the checkout is one
    `git add -A` from every clone."""
    from tracker.settings import app_dir, inside_the_app

    app = app_dir()
    assert inside_the_app(app)
    assert inside_the_app(app / "docs" / "learned.md")
    monkeypatch.chdir(app / "docs")
    assert inside_the_app("learned.md") and inside_the_app("../x")
    assert not inside_the_app(tmp_path)


def test_an_absent_settings_file_is_found_absent_by_opening_it(beside_the_app, monkeypatch):
    """``exists()`` raises no audit event, so the suite's tripwire would not
    see a test reach the checkout's settings on a machine without one."""
    from pathlib import Path

    def never(self, *args, **kwargs):
        raise AssertionError(f"exists() asked of {self}")

    monkeypatch.setattr(Path, "exists", never)
    assert clients_root() is None
# ------------------------------------------------ the data home (decision 186) ----


def _fixed(_path):
    return data_rules.DRIVE_FIXED


def _resolve(environ, *, windows=False, home=None, program=(), drive_type=_fixed):
    return data_rules.resolve_data_home(environ, windows=windows, home=home, program=program,
                                        drive_type=drive_type)


def _refused(sentence, **kwargs):
    with pytest.raises(SettingsError) as caught:
        _resolve(**kwargs)
    assert str(caught.value) == sentence
    return caught.value


def test_the_data_home_is_the_accounts_own_local_application_data_folder(tmp_path):
    local = tmp_path / "Local"
    local.mkdir()
    assert _resolve({"LOCALAPPDATA": str(local)}, windows=True) == local / data_rules.DATA_HOME_NAME


def test_a_missing_local_application_data_is_refused_and_nothing_falls_back_to_the_program_or_temp(
        tmp_path):
    a_file = tmp_path / "not-a-folder"
    a_file.write_text("", encoding="utf-8")
    _refused(data_rules.NO_LOCAL_APPDATA, environ={}, windows=True)
    _refused(data_rules.NO_LOCAL_APPDATA, environ={"LOCALAPPDATA": "  "}, windows=True)
    for named in ("AppData/Local", str(a_file), str(tmp_path / "gone")):
        _refused(data_rules.LOCAL_APPDATA_NOT_A_FOLDER.format(folder=named),
                 environ={"LOCALAPPDATA": named}, windows=True)
    # Even with a home folder and a state folder to hand, Windows never
    # borrows them: the answer is LOCALAPPDATA's or nothing.
    _refused(data_rules.NO_LOCAL_APPDATA, environ={"XDG_STATE_HOME": str(tmp_path)}, windows=True,
             home=tmp_path)


def test_a_data_home_override_must_be_a_whole_path(tmp_path):
    _refused(data_rules.DATA_HOME_NOT_ABSOLUTE.format(value="data"),
             environ={data_rules.ENV_DATA_HOME: "data"})
    mine = tmp_path / "somewhere" / "of-its-own"
    assert _resolve({data_rules.ENV_DATA_HOME: str(mine)}) == mine
    assert _resolve({data_rules.ENV_DATA_HOME: str(mine), "LOCALAPPDATA": str(tmp_path)},
                    windows=True) == mine                      # the override wins on Windows too
    assert _resolve({data_rules.ENV_DATA_HOME: "  "}, home=tmp_path) == (
        tmp_path / ".local" / "state" / data_rules.DATA_HOME_NAME)   # blank is unset


def test_beside_the_program_is_the_settings_folder_and_a_frozen_executables_own(tmp_path, monkeypatch):
    """The one answer to "beside the program" (the rebase review of 186,
    MF1): where what an earlier version left is looked for, and a fresh
    checkpoint refused - the settings folder, and, frozen, the executable's
    folder when it is another one."""
    import sys

    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    assert data_rules.beside_the_program() == [settings.resolve()]
    executable = tmp_path / "package" / "tracker-api.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    assert data_rules.beside_the_program() == [settings.resolve(), executable.parent.resolve()]
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(executable.parent))
    assert data_rules.beside_the_program() == [executable.parent.resolve()]


def test_the_data_home_is_never_inside_the_program_nor_holds_it(tmp_path, monkeypatch):
    app = data_rules.app_dir()                                 # the checkout, from source
    for inside_or_around in (app / "data", app, app.parent):
        _refused(data_rules.DATA_HOME_BESIDE_PROGRAM.format(home=inside_or_around, program=app),
                 environ={data_rules.ENV_DATA_HOME: str(inside_or_around)}, program=[app])

    # The unzipped package: the settings folder holds the executable's folder,
    # so it is the program too, and the data home may not sit in it.
    package = tmp_path / "package"
    executable = package / "resources" / "api"
    executable.mkdir(parents=True)
    _refused(data_rules.DATA_HOME_BESIDE_PROGRAM.format(home=package / "data", program=package),
             environ={data_rules.ENV_DATA_HOME: str(package / "data")}, program=[executable, package])

    # Asked of this process: a settings folder holding the checkout is the
    # program; the suite's own settings folder, which does not, is not.
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(app.parent))
    assert data_rules.program_folders() == [app, app.parent.resolve()]
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    assert data_rules.program_folders() == [app]
    monkeypatch.setenv(data_rules.ENV_DATA_HOME, str(tmp_path / "app" / "data"))
    assert data_rules.data_home() == tmp_path / "app" / "data"


def test_the_data_home_off_windows_is_the_users_own_state_folder(tmp_path):
    state = tmp_path / "state"
    assert _resolve({"XDG_STATE_HOME": str(state)}, home=tmp_path / "home") == (
        state / data_rules.DATA_HOME_NAME)
    for ignored in ({"XDG_STATE_HOME": "relative/state"}, {"XDG_STATE_HOME": ""}, {}):
        assert _resolve(ignored, home=tmp_path / "home") == (
            tmp_path / "home" / ".local" / "state" / data_rules.DATA_HOME_NAME)
    _refused(data_rules.NO_HOME, environ={}, home=None)


def test_the_data_home_must_be_on_this_computers_own_disk(tmp_path):
    mine = tmp_path / "data"
    for kind in range(7):
        environ = {data_rules.ENV_DATA_HOME: str(mine)}
        if kind == data_rules.DRIVE_FIXED:
            assert _resolve(environ, drive_type=lambda _path, kind=kind: kind) == mine
        else:
            _refused(data_rules.DATA_HOME_NOT_LOCAL.format(home=mine), environ=environ,
                     drive_type=lambda _path, kind=kind: kind)


def test_asking_where_the_data_home_is_creates_nothing(tmp_path, monkeypatch):
    from tracker import scheduling, store

    mine = tmp_path / "data-home"
    monkeypatch.setenv(data_rules.ENV_DATA_HOME, str(mine))
    monkeypatch.delenv(store.ENV_STORE, raising=False)
    assert data_rules.data_home() == mine
    assert data_rules.default_data_home() != mine               # the real place, the override set aside
    assert data_rules.scratch_root() == mine / data_rules.SCRATCH_DIR_NAME
    assert data_rules.process_scratch().parent == mine / data_rules.SCRATCH_DIR_NAME
    assert data_rules.logs_dir() == mine / data_rules.LOGS_DIR_NAME
    assert store.store_path() == mine / store.STORE_FILENAME
    assert scheduling.schedule_xml_path() == mine / scheduling.SCHEDULE_XML_FILENAME
    assert not mine.exists()


# ------------------------------- the data folder Windows redirects (F7, P193) ----

#: The package the F7 session found redirecting this PC's %LOCALAPPDATA%.
PACKAGE = "Claude_pzs8sxrjxfjjc"


@pytest.fixture
def unasked(monkeypatch):
    """A process that has not yet asked whether it is redirected."""
    monkeypatch.setattr(data_rules, "_redirect_answer", data_rules._UNASKED)


def _local(tmp_path):
    local = tmp_path / "Local"
    local.mkdir(parents=True)
    return local


def test_a_redirected_data_folder_is_refused_by_name(tmp_path, monkeypatch, unasked):
    local = _local(tmp_path)
    monkeypatch.setattr(data_rules, "redirect_probe", lambda _local: PACKAGE)
    with pytest.raises(SettingsError) as caught:
        data_rules._the_data_home({"LOCALAPPDATA": str(local)}, windows=True)
    assert str(caught.value) == data_rules.DATA_HOME_REDIRECTED.format(package=PACKAGE,
                                                                        product=data_rules.product_name())
    assert PACKAGE in str(caught.value) and "Start menu" in str(caught.value)


def test_an_unredirected_data_folder_is_answered_as_before(tmp_path, monkeypatch, unasked):
    local = _local(tmp_path)
    monkeypatch.setattr(data_rules, "redirect_probe", lambda _local: None)
    assert data_rules._the_data_home({"LOCALAPPDATA": str(local)}, windows=True) == (
        local / data_rules.DATA_HOME_NAME)


def test_a_named_data_folder_is_never_probed(tmp_path, monkeypatch, unasked):
    """A person who names a folder means it; and off Windows there is no
    %LOCALAPPDATA% for Windows to redirect."""
    def never(_local):
        raise AssertionError("probed a data home a person named")

    monkeypatch.setattr(data_rules, "redirect_probe", never)
    mine = tmp_path / "of-its-own"
    assert data_rules._the_data_home({data_rules.ENV_DATA_HOME: str(mine),
                                      "LOCALAPPDATA": str(_local(tmp_path))}, windows=True) == mine
    assert data_rules._the_data_home({"XDG_STATE_HOME": str(tmp_path / "state")}, windows=False) == (
        tmp_path / "state" / data_rules.DATA_HOME_NAME)
    assert data_rules._redirect_answer is data_rules._UNASKED


def test_the_probe_runs_once_a_process(tmp_path, monkeypatch, unasked):
    asked = []

    def probe(local):
        asked.append(local)
        return PACKAGE

    monkeypatch.setattr(data_rules, "redirect_probe", probe)
    environ = {"LOCALAPPDATA": str(_local(tmp_path))}
    for _ in range(3):
        with pytest.raises(SettingsError):
            data_rules._the_data_home(environ, windows=True)
    assert len(asked) == 1


def _redirecting(local, package):
    """A stand-in for Windows' redirect: the probe file is visible at the
    normal path and also lands in the package's own copy."""
    copy = local / data_rules.PACKAGES_DIR_NAME / package / "LocalCache" / "Local"
    copy.mkdir(parents=True)

    def make(probe):
        probe.write_bytes(b"")
        (copy / probe.name).write_bytes(b"")
    return make


def _probe_files(folder):
    return list(folder.rglob(data_rules.REDIRECT_PROBE_PREFIX + "*"))


def test_the_redirect_probe_leaves_nothing_behind(tmp_path):
    local = _local(tmp_path)
    (local / data_rules.PACKAGES_DIR_NAME / "Another_abc" / "LocalCache" / "Local").mkdir(parents=True)
    assert data_rules.redirect_probe(local, make=_redirecting(local, PACKAGE)) == PACKAGE
    assert _probe_files(local) == []

    elsewhere = _local(tmp_path / "unredirected")
    assert data_rules.redirect_probe(elsewhere) is None          # the real writer, no Packages folder
    (elsewhere / data_rules.PACKAGES_DIR_NAME / "Another_abc").mkdir(parents=True)
    assert data_rules.redirect_probe(elsewhere) is None          # a Packages folder, no copy
    assert _probe_files(elsewhere) == []

    def cannot(_probe):
        raise PermissionError("denied")
    assert data_rules.redirect_probe(local, make=cannot) is None  # nothing new is raised
    assert _probe_files(local) == []


def test_a_stale_redirected_copy_is_found_and_never_touched(tmp_path):
    local = _local(tmp_path)
    copy = (local / data_rules.PACKAGES_DIR_NAME / PACKAGE / "LocalCache" / "Local"
            / data_rules.DATA_HOME_NAME)
    copy.mkdir(parents=True)
    (copy / "tracker.db").write_bytes(b"made-up")
    (local / data_rules.PACKAGES_DIR_NAME / "Another_abc" / "LocalCache" / "Local").mkdir(parents=True)
    environ = {"LOCALAPPDATA": str(local)}
    assert data_rules.redirected_copies(environ, windows=True) == [copy]
    assert (copy / "tracker.db").read_bytes() == b"made-up"
    assert data_rules.redirected_copies(environ, windows=False) == []
    assert data_rules.redirected_copies({**environ, data_rules.ENV_DATA_HOME: str(tmp_path / "mine")},
                                        windows=True) == []


def _packages_denied(monkeypatch):
    """Windows refusing to list a Packages folder, as the review's probe did
    (combined review S2); every other folder lists as it does."""
    real = data_rules.os.scandir

    def scandir(path):
        if Path(path).name == data_rules.PACKAGES_DIR_NAME:
            raise PermissionError(errno.EACCES, "Access is denied", str(path))
        return real(path)
    monkeypatch.setattr(data_rules.os, "scandir", scandir)


def test_a_packages_folder_windows_will_not_list_is_one_sentence_not_a_raw_error(tmp_path, monkeypatch):
    """Combined review S2: the copy search and the probe say the folder and
    the error's class in the firm's sentence, never a raw PermissionError;
    the probe still removes its file."""
    local = _local(tmp_path)
    (local / data_rules.PACKAGES_DIR_NAME / PACKAGE).mkdir(parents=True)
    _packages_denied(monkeypatch)
    said = data_rules.PACKAGES_UNREADABLE.format(folder=local / data_rules.PACKAGES_DIR_NAME,
                                                 error="PermissionError (EACCES)")
    with pytest.raises(SettingsError) as caught:
        data_rules.redirected_copies({"LOCALAPPDATA": str(local)}, windows=True)
    assert str(caught.value) == said
    with pytest.raises(SettingsError) as caught:
        data_rules.redirect_probe(local)
    assert str(caught.value) == said
    assert "Access is denied" not in said
    assert _probe_files(local) == []


def test_a_redirected_data_folder_is_refused_by_its_own_kind_of_settings_error(tmp_path, monkeypatch, unasked):
    """Combined review N3: the first screen tells R1's refusal from any
    other data-home refusal by its class, not by its words."""
    monkeypatch.setattr(data_rules, "redirect_probe", lambda _local: PACKAGE)
    with pytest.raises(data_rules.DataHomeRedirected):
        data_rules._the_data_home({"LOCALAPPDATA": str(_local(tmp_path))}, windows=True)


def test_no_packages_folder_names_no_copy(tmp_path):
    local = _local(tmp_path)
    assert data_rules.redirected_copies({"LOCALAPPDATA": str(local)}, windows=True) == []
    assert data_rules.redirected_copies({}, windows=True) == []


def test_the_data_home_is_named_by_the_apps_package_name():
    from tracker.settings import PACKAGE_JSON

    assert data_rules.DATA_HOME_NAME == json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["name"]


# ---------------------------------------------- the rename (P155, SPEC-rename)


def test_the_earlier_product_name_is_the_pilots_old_name_not_the_current_or_production_one():
    """R1 and R8: the one home of the earlier name, which is neither the
    product's name now nor the firm's production product's."""
    assert data_rules.EARLIER_PRODUCT_NAME == "Tax Document Tracker Pilot"
    assert data_rules.EARLIER_PRODUCT_NAME != data_rules.product_name()
    assert data_rules.EARLIER_PRODUCT_NAME != "Tax Document Tracker"


def test_the_earlier_settings_path_is_under_local_app_data_programs(tmp_path, monkeypatch):
    """Where the earlier installer put the program, and settings.json beside
    it; None where there is no LOCALAPPDATA to look in."""
    from pathlib import Path

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert data_rules.earlier_settings_path() == (
        Path(tmp_path) / "Programs" / data_rules.EARLIER_PRODUCT_NAME / SETTINGS_FILENAME)
    monkeypatch.setenv("LOCALAPPDATA", "")
    assert data_rules.earlier_settings_path() is None
    monkeypatch.delenv("LOCALAPPDATA")
    assert data_rules.earlier_settings_path() is None


def test_the_data_folder_keeps_its_name_through_the_rename():
    """R3: the data folder holds the store, the checkpoint and the run log,
    and a scheduled pass can start between the upgrade and the app's first
    launch, so it is never renamed or moved: it keeps the pilot's internal
    name, which is not the product's name now."""
    assert data_rules.DATA_HOME_NAME == "tax-document-tracker-pilot"
    assert data_rules.DATA_HOME_NAME != data_rules.product_name()


def test_a_clients_root_that_holds_or_sits_inside_the_data_home_is_refused(beside_the_app, monkeypatch):
    from pathlib import Path

    rules = dict(settings=beside_the_app / "app", app=beside_the_app / "program",
                 system=Path(beside_the_app.anchor))
    data = beside_the_app / "shared" / "data"
    around, inside = beside_the_app / "shared", data / "logs"
    assert data_rules.root_refusal(around, data=data, **rules) == data_rules.ROOT_HOLDS_DATA.format(
        root=around, data=data)
    assert data_rules.root_refusal(inside, data=data, **rules) == data_rules.ROOT_INSIDE_DATA.format(
        root=inside, data=data)
    assert data_rules.root_refusal(beside_the_app / "clients", data=data, **rules) == ""

    # And on this machine: the rule set_clients_root asks.
    data.mkdir(parents=True)
    monkeypatch.setenv(data_rules.ENV_DATA_HOME, str(data))
    with pytest.raises(SettingsError) as caught:
        set_clients_root(around)
    assert str(caught.value) == data_rules.ROOT_HOLDS_DATA.format(root=around.resolve(), data=data)
    assert clients_root() is None                               # nothing recorded


def test_the_store_the_scratch_and_the_task_file_never_resolve_under_the_program_the_checkout_or_the_clients_root(
        tmp_path, monkeypatch):
    """The proof (decision 186): with every override gone, what the tracker
    derives from clients resolves into this account's own folder, and never
    under the program, the repository or the clients root."""
    import os
    from pathlib import Path

    from tracker import runner, scheduling, store

    repository = Path(__file__).resolve().parent.parent
    account = tmp_path / "account"
    account.mkdir()
    clients = tmp_path / "clients"
    clients.mkdir()
    monkeypatch.delenv(data_rules.ENV_DATA_HOME, raising=False)
    monkeypatch.delenv(store.ENV_STORE, raising=False)
    monkeypatch.setenv("LOCALAPPDATA" if os.name == "nt" else "XDG_STATE_HOME", str(account))
    places = [store.store_path(), data_rules.scratch_root(), data_rules.process_scratch(),
              scheduling.schedule_xml_path(), data_rules.logs_dir(), runner.log_path()]
    for place in places:
        assert data_rules._inside(place, account / data_rules.DATA_HOME_NAME), place
        for never in (data_rules.app_dir(), repository, clients):
            assert not data_rules._inside(place, never), (place, never)
    assert not (account / data_rules.DATA_HOME_NAME).exists()


def test_a_corpus_inside_the_app_is_refused_by_name(tmp_path, monkeypatch):
    """Decision 186: no corpus is nothing to route (None); a corpus inside
    the checkout is a mistake, said by name."""
    inside = data_rules.app_dir() / "tests"                     # a folder the checkout already has
    monkeypatch.setenv(ENV_REAL_CORPUS, str(inside))
    with pytest.raises(SettingsError) as caught:
        real_corpus_dir()
    assert str(caught.value) == data_rules.CORPUS_INSIDE_APP.format(folder=inside)
    outside = tmp_path / "corpus"
    outside.mkdir()
    monkeypatch.setenv(ENV_REAL_CORPUS, str(outside))
    assert real_corpus_dir() == outside


def test_only_a_fixed_disk_may_hold_the_program_the_schedule_runs(tmp_path):
    """Decision 186: Install Schedule asks where the program and its settings
    folder are; every answer Windows can give but a fixed disk is refused by
    its own sentence, and nothing is guessed."""
    app, settings = tmp_path / "app", tmp_path / "settings"
    sentence = {
        data_rules.DRIVE_UNKNOWN: data_rules.PROGRAM_DRIVE_UNKNOWN,
        data_rules.DRIVE_NO_ROOT_DIR: data_rules.PROGRAM_DRIVE_UNKNOWN,
        data_rules.DRIVE_REMOVABLE: data_rules.PROGRAM_ON_REMOVABLE,
        data_rules.DRIVE_FIXED: "",
        data_rules.DRIVE_REMOTE: data_rules.PROGRAM_ON_NETWORK,
        data_rules.DRIVE_CDROM: data_rules.PROGRAM_ON_REMOVABLE,
        data_rules.DRIVE_RAMDISK: data_rules.PROGRAM_DRIVE_UNKNOWN,
    }
    assert sorted(sentence) == list(range(7))
    for kind, said in sentence.items():
        for odd in (app, settings):
            def answer(path, kind=kind, odd=odd):
                return kind if path == odd else data_rules.DRIVE_FIXED
            refusal = data_rules.program_drive_refusal(app=app, settings=settings, drive_type=answer)
            assert refusal == (said.format(folder=odd) if said else "")


# --------------------------------------- the schedule setting (pilot P21) ----


def test_nothing_saved_means_the_schedule_defaults(beside_the_app):
    chosen = data_rules.schedule_preference()
    assert (chosen.enabled, chosen.start, chosen.every) == (True, "07:00", 120)


def test_the_schedule_choice_round_trips_and_sits_beside_the_root(beside_the_app):
    clients = beside_the_app / "Clients"
    clients.mkdir()
    set_clients_root(clients)

    saved = data_rules.set_schedule(False, "06:30", 0)

    assert saved == data_rules.SchedulePreference(False, "06:30", 0)
    assert data_rules.schedule_preference() == saved
    on_file = json.loads(settings_path().read_text(encoding="utf-8"))
    assert on_file == {"clients_root": str(clients.resolve()), "schedule_enabled": False,
                       "schedule_start": "06:30", "schedule_every": 0}
    data_rules.set_schedule(True, "13:00", 480)
    assert clients_root() == clients.resolve()          # the root is not disturbed


def test_saving_the_root_alone_writes_only_the_root(beside_the_app):
    clients = beside_the_app / "Clients"
    clients.mkdir()
    set_clients_root(clients)
    assert json.loads(settings_path().read_text(encoding="utf-8")) == {"clients_root": str(clients.resolve())}
    assert data_rules.schedule_preference() == data_rules.SchedulePreference()


def test_a_missing_key_takes_its_default_and_the_others_are_kept(beside_the_app):
    settings_path().parent.mkdir(parents=True)
    settings_path().write_text(json.dumps({"schedule_start": "09:15"}), encoding="utf-8")
    assert data_rules.schedule_preference() == data_rules.SchedulePreference(True, "09:15", 120)


@pytest.mark.parametrize(("key", "value"), [
    ("schedule_enabled", "yes"), ("schedule_enabled", 1), ("schedule_enabled", None),
    ("schedule_start", "9am"), ("schedule_start", 900), ("schedule_start", "25:00"),
    ("schedule_every", 45), ("schedule_every", "2 hours"), ("schedule_every", True), ("schedule_every", None),
])
def test_a_bad_saved_value_is_refused_naming_the_file_and_the_key(beside_the_app, key, value):
    settings_path().parent.mkdir(parents=True)
    settings_path().write_text(json.dumps({key: value}), encoding="utf-8")
    with pytest.raises(data_rules.ScheduleChoiceError) as refused:
        data_rules.schedule_preference()
    assert str(settings_path()) in str(refused.value) and key in str(refused.value)


@pytest.mark.parametrize("choice", [
    ("yes", "07:00", 120), (True, "7:00", 120), (True, "07:00", 90), (True, "07:00", None),
])
def test_a_bad_choice_is_refused_and_nothing_is_written(beside_the_app, choice):
    with pytest.raises(data_rules.ScheduleChoiceError):
        data_rules.set_schedule(*choice)
    assert not settings_path().exists()


def test_a_settings_file_that_will_not_read_is_not_overwritten_by_a_save(beside_the_app):
    settings_path().parent.mkdir(parents=True)
    settings_path().write_text("{not json", encoding="utf-8")
    with pytest.raises(SettingsError):
        data_rules.set_schedule(True, "07:00", 120)
    assert settings_path().read_text(encoding="utf-8") == "{not json"


# ------------------------------------------------ one reading (P118) ----

def test_one_reading_asks_the_data_folder_once_and_outside_it_every_time(monkeypatch, tmp_path):
    """A read-only reply asks where the data folder is thousands of times;
    inside ``one_reading`` the first answer stands, and outside it an
    override takes effect at once, as ``data_home`` has always promised."""
    asked = []
    real = data_rules.resolve_data_home

    def counted(*args, **kwargs):
        asked.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(data_rules, "resolve_data_home", counted)
    first = data_rules.data_home()
    with data_rules.one_reading():
        assert data_rules.data_home() == data_rules.data_home() == first
        monkeypatch.setenv(data_rules.ENV_DATA_HOME, str(tmp_path / "elsewhere"))
        assert data_rules.data_home() == first, "one reply sees one data folder"
    assert len(asked) == 2
    assert data_rules.data_home() == tmp_path / "elsewhere", "outside a reading, an override is at once"


def test_one_reading_reads_the_settings_once_and_hands_each_caller_its_own_copy():
    data_rules.set_firm("J Park & Associates, CPA")
    with data_rules.one_reading():
        mine = data_rules._read()
        mine["firm"] = "changed by one caller"
        settings_path().write_text(json.dumps({"firm": "written meanwhile"}), encoding="utf-8")
        assert data_rules._read()["firm"] == "J Park & Associates, CPA"
    assert data_rules._read()["firm"] == "written meanwhile"


def test_one_reading_holds_what_a_path_resolves_to_but_never_an_error(monkeypatch, tmp_path):
    from pathlib import Path

    calls, real = [], Path.resolve

    def counted(self, strict=False):
        calls.append(str(self))
        if self.name == "refuses":
            raise OSError("cannot be resolved")
        return real(self, strict)

    monkeypatch.setattr(Path, "resolve", counted)
    with data_rules.one_reading():
        for _ in range(3):
            assert data_rules.resolved(tmp_path / "a") == real(tmp_path / "a")
            with pytest.raises(OSError):
                data_rules.resolved(tmp_path / "refuses")
    assert calls.count(str(tmp_path / "a")) == 1
    assert calls.count(str(tmp_path / "refuses")) == 3
    data_rules.resolved(tmp_path / "a")
    assert calls.count(str(tmp_path / "a")) == 2, "outside a reading nothing is held"


def test_a_nested_reading_is_the_same_reading_and_ends_with_the_outer_one():
    with data_rules.one_reading():
        first = data_rules.app_dir()
        with data_rules.one_reading():
            assert data_rules._HELD is not None and data_rules.app_dir() == first
        assert data_rules._HELD is not None
    assert data_rules._HELD is None


def test_a_settings_write_inside_a_reading_is_refused_outright():
    """The review's SHOULD-3: a read-only reply writes nothing, and a write
    under held answers would leave the rest of the reply stale."""
    with data_rules.one_reading():
        with pytest.raises(RuntimeError, match="read-only reply"):
            data_rules.set_firm("Written inside a reading")
    data_rules.set_firm("Written after it")
    assert data_rules.firm() == "Written after it"


# --------------------------------------------- one household (P207) ----

def test_one_household_asks_the_data_folder_once_and_drops_it_after(monkeypatch, tmp_path):
    """A pass asked where the data folder is tens of thousands of times at
    1,000 households; inside one household's hold the first answer stands,
    and the next household asks again."""
    asked = []
    real = data_rules.resolve_data_home

    def counted(*args, **kwargs):
        asked.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(data_rules, "resolve_data_home", counted)
    with data_rules.one_household():
        first = data_rules.data_home()
        assert data_rules.data_home() == data_rules.data_home() == first
        monkeypatch.setenv(data_rules.ENV_DATA_HOME, str(tmp_path / "elsewhere"))
        assert data_rules.data_home() == first, "one household sees one data folder"
    assert len(asked) == 1
    assert data_rules._HELD is None
    with data_rules.one_household():
        assert data_rules.data_home() == tmp_path / "elsewhere", "the next household asks again"


def test_one_household_lets_the_pass_write_its_records_and_the_store():
    """The pass writes the store and the records while it holds; the store
    asks ``refuse_a_write_while_reading``, and only a read-only reply
    refuses (P118's SHOULD-3 is the reading's)."""
    with data_rules.one_household():
        data_rules.refuse_a_write_while_reading("the store")


def test_a_settings_write_inside_a_household_is_refused_and_never_undoes_a_save():
    """The review's SHOULD-3: every setter writes back what it read, which
    inside a household is the copy held since the household began, so a
    save the app made meanwhile would be undone in silence. The pass never
    writes the file; one that tried is refused, and the save stands."""
    data_rules.set_firm("Before")
    with data_rules.one_household():
        assert data_rules.firm() == "Before"
        settings_path().write_text(json.dumps({"firm": "Saved by the app meanwhile"}), encoding="utf-8")
        with pytest.raises(RuntimeError, match="holds a household's answers"):
            data_rules.set_firm_phone("555-0100")
    assert json.loads(settings_path().read_text(encoding="utf-8")) == {"firm": "Saved by the app meanwhile"}


def test_one_household_holds_a_path_only_once_it_is_there(monkeypatch, tmp_path):
    """A folder the pass makes later is resolved again: a path resolves
    differently once it exists (Windows gives the folder's own case, a link
    is followed), and a store key from before it existed would be another
    return's key."""
    from pathlib import Path

    calls, real = [], Path.resolve

    def counted(self, strict=False):
        calls.append(str(self))
        return real(self, strict)

    monkeypatch.setattr(Path, "resolve", counted)
    later = tmp_path / "made later"
    with data_rules.one_household():
        for _ in range(3):
            assert data_rules.resolved(tmp_path) == real(tmp_path)
            assert data_rules.resolved(later) == real(later)
        assert calls.count(str(tmp_path)) == 1, "a folder that is there is resolved once"
        assert calls.count(str(later)) == 3, "a folder that is not there yet is never held"
        later.mkdir()
        data_rules.resolved(later)
        data_rules.resolved(later)
        assert calls.count(str(later)) == 4, "once it is there, it is held"


def test_one_household_never_holds_an_error(monkeypatch, tmp_path):
    from pathlib import Path

    calls, real = [], Path.resolve

    def refusing(self, strict=False):
        calls.append(str(self))
        if self.name == "refuses":
            raise OSError("cannot be resolved")
        return real(self, strict)

    monkeypatch.setattr(Path, "resolve", refusing)
    with data_rules.one_household():
        for _ in range(3):
            with pytest.raises(OSError):
                data_rules.resolved(tmp_path / "refuses")
    assert calls.count(str(tmp_path / "refuses")) == 3


def test_a_household_inside_a_reading_is_the_reading_and_still_refuses_a_write():
    """Nested, a hold is part of the one outside it: a household's hold
    never lifts a reading's refusal, and a reading inside a household is
    the household's."""
    with data_rules.one_reading():
        with data_rules.one_household():
            assert data_rules._HOLDING == data_rules.HOLD_READING
            with pytest.raises(RuntimeError, match="read-only reply"):
                data_rules.set_firm("Written inside a reading")
    with data_rules.one_household():
        with data_rules.one_reading():
            assert data_rules._HOLDING == data_rules.HOLD_HOUSEHOLD
        assert data_rules._HELD is not None
    assert data_rules._HELD is None and data_rules._HOLDING == ""


# ----------------------------------------------- the one hold memo (P215) ----


def test_held_keeps_an_answer_for_the_hold_and_only_once_its_path_is_there(tmp_path):
    """P215: outside a hold every ask is answered afresh; inside a reading
    the first answer stands; inside a household's hold an answer about a
    folder is kept only once the folder is there, so a folder the pass makes
    later is never answered from before it existed."""
    asked = []

    def answer():
        asked.append(1)
        return len(asked)

    assert data_rules.held(("a question",), answer) == 1
    assert data_rules.held(("a question",), answer) == 2            # nothing kept outside a hold
    with data_rules.one_reading():
        assert data_rules.held(("a question",), answer) == 3
        assert data_rules.held(("a question",), answer) == 3
    assert data_rules.held(("a question",), answer) == 4            # dropped with the hold

    later = tmp_path / "made later"
    asked.clear()
    with data_rules.one_household():
        assert data_rules.held(("about", str(later)), answer, there=later) == 1
        assert data_rules.held(("about", str(later)), answer, there=later) == 2   # not there: asked again
        later.mkdir()
        assert data_rules.held(("about", str(later)), answer, there=later) == 3
        assert data_rules.held(("about", str(later)), answer, there=later) == 3   # there: kept
        assert data_rules.held(("no folder",), answer) == 4
        assert data_rules.held(("no folder",), answer) == 4
    with data_rules.one_reading():
        gone = tmp_path / "never made"
        assert data_rules.held(("about", str(gone)), answer, there=gone) == 5
        assert data_rules.held(("about", str(gone)), answer, there=gone) == 5     # a reading keeps it


def test_held_never_keeps_an_error():
    calls = []

    def failing():
        calls.append(1)
        if len(calls) == 1:
            raise OSError("fabricated")
        return "answered"

    with data_rules.one_reading():
        with pytest.raises(OSError):
            data_rules.held(("flaky",), failing)
        assert data_rules.held(("flaky",), failing) == "answered"
        assert data_rules.held(("flaky",), failing) == "answered"
    assert len(calls) == 2
