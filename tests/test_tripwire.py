"""Tests for the suite's tripwire and its own folders (decision 185).

The claim: every test, and the collection before any test, runs against a
settings folder and a store of its own; a tripwire armed in the pytest
process and in every Python child the suite starts stops and records any
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

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.conftest import (
    ENV_OFFICE_SHAPED_FULL,
    REPO,
    TRIPWIRE_HEADING,
    checkout_folders,
    child_env,
    real_places,
    run_in_copy,
)
from tests.tripwire import sitecustomize as tripwire
from tracker import settings, store
from tracker.layout import CLIENTS_TREE, PRIVATE_TREE
from tracker.scheduling import SCHEDULE_XML_FILENAME

#: The guarded places that are folders, by their label; the rest are files.
FOLDER_LABELS = {"OCR scratch folder", "client tree", "private tree"}


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
    for place in (beside, store.path_for(beside), beside.with_name(store.STORE_WAL_FILENAME),
                  beside.with_name(store.STORE_SHM_FILENAME), beside.with_name(SCHEDULE_XML_FILENAME),
                  settings.app_dir() / settings.OCR_SCRATCH_DIRNAME,
                  REPO / CLIENTS_TREE, REPO / PRIVATE_TREE):
        assert place in guarded, place

    named = tmp_path / "named"
    monkeypatch.setenv(settings.ENV_SETTINGS_DIR, str(named))
    guarded = {path for _label, path in real_places(REPO)}
    assert named / settings.SETTINGS_FILENAME in guarded
    assert store.path_for(named / settings.SETTINGS_FILENAME) in guarded
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
''')
CANARIES = {"test_a_settings": "settings file", "test_b_store": "store",
            "test_c_scratch": "OCR scratch folder", "test_d_client_tree": "client tree",
            "test_e_child": "settings file", "test_f_reading_child": "settings file",
            "test_g_swallowed": "settings file"}


def _unchanged(copy: Path, fabricated: dict) -> None:
    for rel, content in fabricated.items():
        assert (copy / rel).read_bytes() == content, rel


def _section(output: str) -> list[str]:
    """The lines the session printed under the tripwire's heading."""
    lines = output.splitlines()
    start = next(i for i, line in enumerate(lines) if TRIPWIRE_HEADING in line)
    said = []
    for line in lines[start + 1:]:
        if line.startswith("=="):
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
    assert len(said) == len(CANARIES), said
    for test, label in CANARIES.items():
        assert any(f"test_canary_185.py::{test} " in line and f"the checkout's {label}" in line
                   for line in said), (test, said)
    # (e), (f) and (g) pass on their own - the child's exit is tolerated, the
    # error swallowed - and the session fails for them all the same.
    assert "4 failed, 3 passed" in output, output[-2000:]
    _unchanged(copy, fabricated)
    assert checkout_folders(copy, ()) == folders


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
