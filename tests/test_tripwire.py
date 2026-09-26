"""Tests for the suite's tripwire and its own folders (decision 185).

The claim: every test, and the collection before any test, runs against a
settings folder and a store of its own; a tripwire armed in the pytest
process and in every Python child that inherits the suite's environment
stops and records any
reach for a place where a real settings file, store, scratch folder or
client tree resolves on this machine, and such a reach - or a folder the
session leaves in the checkout - fails the whole session, even when the test
swallowed the error.

The last two tests prove it the way the office would meet it: the checkout
copied, with fabricated files shaped like an office's beside it, and the
suite run there in a process of its own. With ``TRACKER_OFFICE_SHAPED_FULL=1``
the second runs the whole suite there; CI runs the bounded set only, under
the standing cost rule.
"""

import json
import ntpath
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.conftest import (
    ENV_OFFICE_SHAPED_FULL,
    REPO,
    TRIPWIRE_DIR,
    TRIPWIRE_HEADING,
    UNREADABLE_LOG,
    UNREADABLE_LOG_LINE,
    checkout_folders,
    child_env,
    read_tripwire_log,
    real_places,
    run_in_copy,
    tripwire_log_said,
)
from tests.tripwire import sitecustomize as tripwire
from tracker import settings, store
from tracker.checkpoint import CHECKPOINT_FILENAME
from tracker.layout import CLIENTS_TREE, PRIVATE_TREE
from tracker.progress import PASSES_DIRNAME
from tracker.runner import LAST_PASS_FILENAME
from tracker.scheduling import SCHEDULE_XML_FILENAME

#: The guarded places that are folders, by their label; the rest are files.
FOLDER_LABELS = {"OCR scratch folder", "client tree", "private tree", "recovered record copies", "passes folder"}


# ----------------------------------------------------- a folder of its own ----


def test_every_test_has_a_settings_folder_and_a_store_of_its_own(tmp_path):
    assert settings.settings_dir().is_relative_to(tmp_path)
    assert store.store_path().is_relative_to(tmp_path)


def test_no_test_sees_the_real_corpus_unless_it_names_one():
    assert settings.real_corpus_dir() is None
    assert settings.ENV_REAL_CORPUS not in os.environ


def test_a_test_that_undoes_its_monkeypatch_keeps_its_own_folders(tmp_path, monkeypatch):
    monkeypatch.setenv(settings.ENV_SETTINGS_DIR, str(tmp_path / "elsewhere"))
    monkeypatch.undo()
    assert settings.settings_dir().is_relative_to(tmp_path)
    assert store.store_path().is_relative_to(tmp_path)


# ------------------------------------------------------ the places guarded ----


def test_the_tripwire_guards_every_place_a_real_settings_file_store_or_scratch_resolves_to(tmp_path, monkeypatch):
    monkeypatch.delenv(settings.ENV_SETTINGS_DIR)
    beside = settings.settings_path()
    guarded = {path for _label, path in real_places(REPO)}
    for place in (beside, beside.with_name(store.STORE_FILENAME), beside.with_name(store.STORE_WAL_FILENAME),
                  beside.with_name(store.STORE_SHM_FILENAME), beside.with_name(SCHEDULE_XML_FILENAME),
                  settings.app_dir() / settings.OCR_SCRATCH_DIRNAME,
                  REPO / CLIENTS_TREE, REPO / PRIVATE_TREE,
                  # decision 159's files beside the store
                  beside.with_name(CHECKPOINT_FILENAME), beside.with_name(LAST_PASS_FILENAME),
                  beside.with_name(store.RECOVERED_DIR),
                  # decision 193's, beside the store
                  beside.with_name(settings.ERROR_LOG_FILENAME), beside.with_name(PASSES_DIRNAME)):
        assert place in guarded, place

    named = tmp_path / "named"
    monkeypatch.setenv(settings.ENV_SETTINGS_DIR, str(named))
    guarded = {path for _label, path in real_places(REPO)}
    assert named / settings.SETTINGS_FILENAME in guarded
    assert named / store.STORE_FILENAME in guarded
    assert beside in guarded                      # the checkout's own stays guarded


def test_the_ignore_file_knows_every_place_the_tripwire_guards(monkeypatch):
    """A place the wire guards is a place a real file lands in a checkout;
    the ignore file must keep each out of a commit, by the same name."""
    monkeypatch.delenv(settings.ENV_SETTINGS_DIR)
    ignored = [line.strip() for line in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.startswith("#")]
    under = [(label, path) for label, path in real_places(REPO) if path.parent == REPO]
    assert under
    for label, path in under:
        name = f"{path.name}/" if label in FOLDER_LABELS else path.name
        assert ignored.count(name) == 1, name


# --------------------------------------------------------------- judgement ----


def fabricated_places(tmp_path: Path) -> tuple:
    app = tmp_path / "place"
    (app / "Clients").mkdir(parents=True)
    (app / settings.SETTINGS_FILENAME).write_text("{}", encoding="utf-8")
    return tripwire.prepare([("settings file", app / settings.SETTINGS_FILENAME),
                             ("client tree", app / "Clients")])


def test_a_place_is_judged_by_the_folder_itself_not_its_spelling(tmp_path, monkeypatch):
    prepared = fabricated_places(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert tripwire.judge("open", ("place/settings.json", "r", 0), prepared) == "settings file"
    assert tripwire.judge("open", (str(tmp_path / "place" / "x" / ".." / "settings.json"), "r", 0),
                          prepared) == "settings file"
    assert tripwire.judge("os.listdir", (str(tmp_path / "place" / "Clients" / "Smith"),),
                          prepared) == "client tree"
    assert tripwire.judge("sqlite3.connect", (f"file:{tmp_path / 'place' / 'settings.json'}?mode=ro",),
                          prepared) == "settings file"
    assert tripwire.judge("sqlite3.connect", (":memory:",), prepared) is None
    if os.name == "nt":
        assert tripwire.judge("open", (str(tmp_path / "PLACE" / "SETTINGS.JSON"), "r", 0),
                              prepared) == "settings file"
    else:
        alias = tmp_path / "alias"
        try:
            alias.symlink_to(tmp_path / "place", target_is_directory=True)
        except OSError:
            pytest.skip("this machine refuses symlinks")
        assert tripwire.judge("open", (str(alias / "settings.json"), "r", 0), prepared) == "settings file"


def test_the_atomic_writes_temporary_beside_a_guarded_file_is_guarded_too(tmp_path):
    prepared = fabricated_places(tmp_path)
    temporary = tmp_path / "place" / f"{settings.SETTINGS_FILENAME}.4242.9f3a.tmp"
    assert tripwire.judge("open", (str(temporary), "w", 0), prepared) == "settings file"
    assert tripwire.judge("os.rename", (str(temporary), str(tmp_path / "place" / "settings.json"), None, None),
                          prepared) == "settings file"


def test_a_link_to_or_from_a_guarded_place_is_judged(tmp_path, monkeypatch):
    """A hard link or a symbolic link names the place it reaches; either end
    guarded is a reach for it. A symbolic link's relative target is read from
    the link's own folder."""
    prepared = fabricated_places(tmp_path)
    settings_file = str(tmp_path / "place" / settings.SETTINGS_FILENAME)
    elsewhere = str(tmp_path / "elsewhere" / "copy.json")
    assert tripwire.judge("os.link", (settings_file, elsewhere, None, None), prepared) == "settings file"
    assert tripwire.judge("os.link", (elsewhere, settings_file, None, None), prepared) == "settings file"
    assert tripwire.judge("os.symlink", (settings_file, elsewhere, None), prepared) == "settings file"
    monkeypatch.chdir(tmp_path)
    beside = str(tmp_path / "place" / "link.json")
    assert tripwire.judge("os.symlink", ("settings.json", beside, None), prepared) == "settings file"
    assert tripwire.judge("os.link", (elsewhere, str(tmp_path / "other.json"), None, None), prepared) is None


def test_a_verbatim_windows_spelling_is_the_same_place():
    """``\\\\?\\C:\\...`` and ``\\\\?\\UNC\\server\\share\\...`` are the long spellings of
    ``C:\\...`` and ``\\\\server\\share\\...``; the comparison strips the prefix.
    Fed as Windows spellings through ``ntpath``, so it runs on every platform."""
    norm = tripwire._norm
    assert norm("\\\\?\\C:\\Firm\\settings.json", ntpath) == norm("C:\\Firm\\settings.json", ntpath)
    assert norm("\\\\?\\c:\\FIRM\\Settings.JSON", ntpath) == norm("C:\\Firm\\settings.json", ntpath)
    assert (norm("\\\\?\\UNC\\office\\share\\Clients", ntpath)
            == norm("\\\\office\\share\\Clients", ntpath))
    assert (norm("\\\\?\\unc\\office\\share\\Clients", ntpath)
            == norm("\\\\office\\share\\Clients", ntpath))
    assert norm("C:\\Firm\\settings.json", ntpath) != norm("C:\\Other\\settings.json", ntpath)


def test_the_rest_of_the_checkout_is_not_guarded(tmp_path, monkeypatch):
    monkeypatch.delenv(settings.ENV_SETTINGS_DIR)
    prepared = tripwire.prepare(real_places(REPO))
    for path in (REPO / "pyproject.toml", REPO / "tests", tmp_path / settings.SETTINGS_FILENAME):
        assert tripwire.judge("open", (str(path), "r", 0), prepared) is None, path
        assert tripwire.judge("os.listdir", (str(path),), prepared) is None, path


# ------------------------------------------------------------------ children ----


def test_every_python_child_starts_with_the_tripwire_armed():
    probe = 'import sys; print("sitecustomize" in sys.modules and bool(sys.modules["sitecustomize"].WATCHED))'
    done = subprocess.run([sys.executable, "-c", probe], env=child_env(), cwd=REPO,
                          capture_output=True, text=True, timeout=120)
    assert done.stdout.strip() == "True", done.stderr


def _armed_env(session: str) -> dict:
    return {**dict(os.environ), tripwire.ENV_TRIPWIRE: session,
            "PYTHONPATH": os.pathsep.join([str(TRIPWIRE_DIR), str(REPO)])}


def test_a_python_child_is_judged_by_its_environment_its_path_and_its_flags():
    """Decision 185, the review's M2: a Python child the pytest process
    starts without the session's variable, without the tripwire folder
    first on its path, or with a flag that drops either is recorded."""
    session = '{"places": [], "log": "x"}'
    armed = _armed_env(session)
    popen = "subprocess.Popen"
    judge = tripwire.judge_child
    assert judge(popen, (sys.executable, [sys.executable, "-c", "print(1)"], None, armed), session) is None
    assert judge(popen, (None, ["python3", "-m", "tracker.ledger"], None, armed), session) is None

    lacking = {k: v for k, v in armed.items() if k != tripwire.ENV_TRIPWIRE}
    assert judge(popen, (sys.executable, [sys.executable, "-c", "1"], None, lacking), session)
    other = {**armed, tripwire.ENV_TRIPWIRE: '{"places": []}'}
    assert judge(popen, (sys.executable, [sys.executable, "-c", "1"], None, other), session)
    bare = {"PATH": os.environ.get("PATH", "")}
    assert judge(popen, (sys.executable, [sys.executable, "-c", "1"], None, bare), session)
    moved = {**armed, "PYTHONPATH": os.pathsep.join([str(REPO), str(TRIPWIRE_DIR)])}
    assert judge(popen, (sys.executable, [sys.executable, "-c", "1"], None, moved), session)
    for flags in (["-I"], ["-E"], ["-S"], ["-IS"], ["-u", "-E"], ["-Wignore", "-bS"], ["-X", "utf8", "-I"]):
        assert judge(popen, (sys.executable, [sys.executable, *flags, "-c", "1"], None, armed), session), flags
    # A flag after the script or the command is the script's, not the interpreter's.
    assert judge(popen, (sys.executable, [sys.executable, "-c", "1", "-I"], None, armed), session) is None
    assert judge(popen, (sys.executable, [sys.executable, "-m", "pytest", "-S"], None, armed), session) is None
    assert judge(popen, (sys.executable, [sys.executable, "script.py", "-E"], None, armed), session) is None
    # Not Python: not judged.
    assert judge(popen, ("/usr/bin/git", ["git", "status"], None, bare), session) is None
    # The other ways a program starts.
    assert judge("os.posix_spawn", (sys.executable, [sys.executable, "-c", "1"], bare), session)
    assert judge("os.spawn", (0, sys.executable, [sys.executable, "-I", "-c", "1"], armed), session)
    assert judge("os.exec", (sys.executable, [sys.executable, "-c", "1"], bare), session)
    assert judge("os.exec", (sys.executable, [sys.executable, "-c", "1"], armed), session) is None
    # multiprocessing's two: no environment in the event, so this process's is the child's.
    command_line = f'"{sys.executable}" -I -c "from multiprocessing.spawn import spawn_main"'
    assert judge("_winapi.CreateProcess", (None, command_line, None), session)
    assert judge(tripwire.SPAWNV_PASSFDS, (sys.executable, [sys.executable, "-c", "1"]),
                 os.environ[tripwire.ENV_TRIPWIRE]) is None       # this session's own environment
    assert judge(tripwire.SPAWNV_PASSFDS, (sys.executable, [sys.executable, "-c", "1"]), session)


def test_a_line_of_the_tripwires_log_it_cannot_read_is_said_as_a_violation():
    """The review's N7: a torn or stray line fails the session plainly, never
    as an internal error - an unread line might have been a hit."""
    good = json.dumps({"test": "t::a", "event": "open", "label": "store", "pid": 7})
    unarmed = json.dumps({"test": "t::b", "event": "subprocess.Popen",
                          "label": f"{tripwire.UNARMED}: started with -I", "pid": 8})
    said = tripwire_log_said([good, '{"test": "t::c", "ev', "[1, 2]", unarmed])
    assert said[0] == "t::a: open of the checkout's store (pid 7)"
    assert said[1] == f"{UNREADABLE_LOG_LINE} (line 2)"
    assert said[2] == f"{UNREADABLE_LOG_LINE} (line 3)"
    assert said[3] == f"t::b: subprocess.Popen started an {tripwire.UNARMED}: started with -I (pid 8)"


def test_a_tripwire_log_that_cannot_be_read_is_said_as_a_violation(tmp_path):
    """The re-check's note: any OSError reading the log - here a folder where
    the file should be - is a named violation; no file at all is no hit."""
    assert read_tripwire_log(tmp_path / "never written.log") == []
    unreadable = tmp_path / "tripwire.log"
    unreadable.mkdir()
    (said,) = read_tripwire_log(unreadable)
    assert said.startswith(UNREADABLE_LOG)


def test_no_test_starts_a_python_child_around_the_tripwire():
    """One rule for a child's environment: ``child_env()``. A test that built
    its own could drop the path the tripwire is found on."""
    shapes = ("PYTHON" + "PATH", "os.environ" + ".items()", "env={**" + "os.environ")
    here = Path(__file__).resolve()
    for path in sorted((REPO / "tests").rglob("*.py")):
        if path.name == "conftest.py" or path.parent.name == "tripwire" or path.resolve() == here:
            continue
        text = path.read_text(encoding="utf-8")
        for shape in shapes:
            assert shape not in text, f"{path.relative_to(REPO)} holds {shape}"


# ------------------------------------------------ the office-shaped copy ----

#: One attempt per test at a place the office's checkout has for real.
CANARY = textwrap.dedent('''
    import multiprocessing
    import os
    import subprocess
    import sys

    import pytest

    from tests.conftest import REPO, child_env
    from tracker import settings, store
    from tracker.layout import CLIENTS_TREE


    def test_a_settings(monkeypatch):
        monkeypatch.delenv(settings.ENV_SETTINGS_DIR)
        settings.clients_root()


    def test_b_store(monkeypatch):
        monkeypatch.delenv(settings.ENV_SETTINGS_DIR)
        monkeypatch.delenv(store.ENV_STORE)
        store.close()
        store.connect()


    def test_c_scratch():
        os.listdir(REPO / settings.OCR_SCRATCH_DIRNAME)


    def test_d_client_tree():
        list((REPO / CLIENTS_TREE).iterdir())


    def test_e_child():
        subprocess.run([sys.executable, "-c", "from tracker import settings; settings.clients_root()"],
                       cwd=REPO, env=child_env(drop=(settings.ENV_SETTINGS_DIR,)),
                       capture_output=True, timeout=120)


    def test_f_reading_child(monkeypatch):
        monkeypatch.delenv(settings.ENV_SETTINGS_DIR)
        child = multiprocessing.get_context("spawn").Process(target=settings.clients_root)
        child.start()
        child.join(120)


    def test_g_swallowed(monkeypatch):
        monkeypatch.delenv(settings.ENV_SETTINGS_DIR)
        try:
            settings.clients_root()
        except Exception:
            pass


    def test_h_child_without_the_variable(monkeypatch):
        monkeypatch.delenv("TRACKER_TEST_TRIPWIRE")
        done = subprocess.run([sys.executable, "-c", "print(1)"], env=child_env(),
                              capture_output=True, text=True, timeout=120)
        assert done.stdout.strip() == "1"


    def test_i_child_with_a_bare_environment():
        done = subprocess.run([sys.executable, "-c", "print(1)"], env={"PATH": os.environ["PATH"]},
                              capture_output=True, text=True, timeout=120)
        assert done.stdout.strip() == "1"


    def test_j_link(tmp_path):
        os.link(REPO / settings.SETTINGS_FILENAME, tmp_path / "linked.json")


    def test_k_unarmed_reading_child(monkeypatch):
        monkeypatch.delenv("TRACKER_TEST_TRIPWIRE")
        child = multiprocessing.get_context("spawn").Process(target=os.getpid)
        child.start()
        child.join(120)
        assert child.exitcode == 0


    def test_l_fork_then_exec_isolated():
        if not hasattr(os, "fork"):
            pytest.skip("no fork on this platform")
        pid = os.fork()
        if pid == 0:
            os.execve(sys.executable, [sys.executable, "-I", "-c", "pass"], child_env())
        _, status = os.waitpid(pid, 0)
        assert status == 0
''')
#: Each canary, and what its line under the tripwire's heading says.
CANARIES = {"test_a_settings": "the checkout's settings file", "test_b_store": "the checkout's store",
            "test_c_scratch": "the checkout's OCR scratch folder",
            "test_d_client_tree": "the checkout's client tree",
            "test_e_child": "the checkout's settings file", "test_f_reading_child": "the checkout's settings file",
            "test_g_swallowed": "the checkout's settings file",
            "test_h_child_without_the_variable": tripwire.UNARMED,
            "test_i_child_with_a_bare_environment": tripwire.UNARMED,
            "test_j_link": "the checkout's settings file",
            "test_k_unarmed_reading_child": tripwire.UNARMED,
            "test_l_fork_then_exec_isolated": tripwire.UNARMED}
if not hasattr(os, "fork"):
    del CANARIES["test_l_fork_then_exec_isolated"]      # skipped there: Windows has no fork


def _unchanged(copy: Path, fabricated: dict) -> None:
    for rel, content in fabricated.items():
        assert (copy / rel).read_bytes() == content, rel


def _section(output: str) -> list[str]:
    """The lines the session printed under the tripwire's heading, up to the
    next heading or the quiet run's closing count (``2 passed in 0.07s``)."""
    lines = output.splitlines()
    start = next(i for i, line in enumerate(lines) if TRIPWIRE_HEADING in line)
    said = []
    for line in lines[start + 1:]:
        if line.startswith("==") or re.match(r"\d+ \w+(, \d+ \w+)* in [\d.]+s", line):
            break
        said.append(line)
    return said


def test_the_suite_in_an_office_shaped_copy_stops_every_way_to_a_real_place(office_shaped_copy):
    copy, fabricated = office_shaped_copy
    folders = checkout_folders(copy, ())
    canary = copy / "tests" / "test_canary_185.py"
    canary.write_text(CANARY, encoding="utf-8")
    try:
        done = run_in_copy(copy, "-p", "no:cacheprovider", "tests/test_canary_185.py")
    finally:
        canary.unlink()
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    said = _section(output)
    # Every line is a canary's, and every canary has one; a start may be
    # heard twice (``subprocess.Popen`` and then ``os.posix_spawn``).
    named = {test for test in CANARIES for line in said if f"test_canary_185.py::{test} " in line}
    assert named == set(CANARIES) and all("test_canary_185.py::" in line for line in said), said
    for test, label in CANARIES.items():
        assert any(f"test_canary_185.py::{test} " in line and label in line
                   for line in said), (test, said)
    # (e), (f), (g), (h), (i), (k) and (l) pass on their own - the child's
    # exit is tolerated, the error swallowed, the unarmed child's answer
    # right - and the session fails for them all the same.
    counts = "5 failed, 7 passed" if hasattr(os, "fork") else "5 failed, 6 passed, 1 skipped"
    assert counts in output, output[-2000:]
    _unchanged(copy, fabricated)
    assert checkout_folders(copy, ()) == folders


#: Two tests that both pass, each having reached a real place (the review's S3).
ALL_PASS = textwrap.dedent('''
    import subprocess
    import sys

    from tests.conftest import REPO, child_env
    from tests.tripwire.sitecustomize import TripwireError
    from tracker import settings


    def test_a_swallowed_open():
        try:
            open(REPO / settings.SETTINGS_FILENAME, encoding="utf-8").close()
        except TripwireError:
            pass


    def test_b_child_whose_failure_is_ignored():
        subprocess.run([sys.executable, "-c", "open(sys.argv[1]).close()".replace("sys.argv[1]", repr(
            str(REPO / settings.SETTINGS_FILENAME)))], env=child_env(), capture_output=True, timeout=120)
''')


def test_a_session_where_every_test_passes_still_fails_for_a_reach(office_shaped_copy):
    """Every test green, the session red: the verdict comes from the wire's
    record, not from any test's outcome, and it names each reach once."""
    copy, fabricated = office_shaped_copy
    canary = copy / "tests" / "test_all_pass_185.py"
    canary.write_text(ALL_PASS, encoding="utf-8")
    try:
        done = run_in_copy(copy, "-p", "no:cacheprovider", "tests/test_all_pass_185.py")
    finally:
        canary.unlink()
    output = done.stdout + done.stderr
    assert done.returncode == 1, output[-4000:]
    assert re.search(r"^2 passed in ", output, re.M), output[-2000:]       # and nothing failed
    said = _section(output)
    assert len(said) == 2, said
    assert any("test_a_swallowed_open" in line for line in said), said
    assert any("test_b_child_whose_failure_is_ignored" in line and "(pid " in line for line in said), said
    _unchanged(copy, fabricated)


def test_the_suite_in_an_office_shaped_copy_creates_no_folder_in_the_checkout(office_shaped_copy):
    copy, fabricated = office_shaped_copy
    folders = checkout_folders(copy, ())
    timeout = 600
    if os.environ.get(ENV_OFFICE_SHAPED_FULL) == "1":
        args = ("--ignore=tests/test_tripwire.py",)
        timeout = 3600                 # the whole suite takes longer than the bounded set's 600 s
    else:
        args = ("tests/test_api_entry.py", "tests/test_settings.py",
                "tests/test_build.py::test_the_graphics_card_pack_is_pinned_apart_and_read_by_its_own_build_step",
                "tests/test_learned_keywords.py::"
                "test_the_report_writes_nothing_under_the_repository_and_refuses_an_out_path_inside_it",
                "tests/test_backtest.py::test_the_tool_writes_nothing_under_the_repository_root")
    done = run_in_copy(copy, *args, timeout=timeout)
    output = done.stdout + done.stderr
    print(output[-1500:])              # the tail the builder and the reviewer quote (-s shows it)
    assert done.returncode == 0, output[-4000:]
    assert TRIPWIRE_HEADING not in output
    _unchanged(copy, fabricated)
    assert checkout_folders(copy, ()) == folders
