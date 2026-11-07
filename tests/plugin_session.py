"""The session's own guards: the tripwire that stops and records any reach for a real place (decision 185), the
xdist hooks that bring a worker's verdict to the controller, the ``--record-golden`` option, the Mac's short temporary
root, and the office-shaped copy a nested run is made in.

The last plugin in ``tests/conftest.py``'s ``pytest_plugins``, with no autouse fixture. It imports from the two plugins
listed before it, and nothing from the two that follow: ``APP_FOLDER``, ``own_folders`` and ``data_home_for`` from
``plugin_isolation``, and ``REAL_HOST_SYSTEM`` and ``stand_on_the_floor`` from ``plugin_fakes``. ``tests/builders.py``
is an ordinary helper module (``TEST_HOUSEHOLD``, ``make_engagement``); no builder reads a plugin's name.

**And the suite can never see a real root** (decision 185). The session
points itself at a folder of its own before collection, and a tripwire
(``tests/tripwire/sitecustomize.py``), armed here and in every Python child
that inherits the suite's environment (the tripwire's docstring lists what
escapes), stops and records any reach for a place
:func:`real_places` names; any record, or any folder the session leaves in
the checkout, fails the whole session.

**A short temporary root on a Mac.** pytest's default on this Mac puts a
test's ``tmp_path`` about 145 characters deep, the floor's about 40, and the
room a return's path has is the absolute length (``layout.on_a_mac`` is
pinned off), so on a Mac the controller points ``basetemp`` at a folder of
its own under ``/private/tmp`` (``_short_temp_root``) unless one was given.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tests.builders import TEST_HOUSEHOLD, make_engagement
from tests.plugin_fakes import REAL_HOST_SYSTEM, stand_on_the_floor
from tests.plugin_isolation import APP_FOLDER, data_home_for, own_folders
from tests.tripwire import sitecustomize as tripwire
from tracker import errlog, layout, scheduling, settings, store
from tracker.layout import CLIENTS_TREE, PRIVATE_TREE

REPO = Path(__file__).resolve().parent.parent

TRIPWIRE_DIR = Path(__file__).resolve().parent / "tripwire"

# ------------------------------------------- the suite can never see a real root ----


def floors_data_home() -> Path:
    """The data home the Linux floor's rules give this account: what a bare
    test resolves on a Mac under the suite's pin (``stand_on_the_floor``)."""
    environ = {key: value for key, value in os.environ.items() if key != settings.ENV_DATA_HOME}
    return settings.resolve_data_home(environ, system="posix", home=Path.home(),
                                      program=settings.program_folders(), drive_type=settings.drive_type)

def real_places(repo: Path) -> tuple[tuple[str, Path], ...]:
    """Every place a real settings file, store, scratch folder or client tree
    resolves to on this machine when nothing of the suite's overrides it:
    beside the app as the checkout resolves it, and wherever the shell running
    the suite names instead. The tripwire guards each; decision 186 adds the
    data home - the account's real one, worked out with ``ENV_DATA_HOME``
    set aside (none, if this machine has none), and one the shell names."""
    from tracker.checkpoint import CHECKPOINT_FILENAME, CHECKPOINT_SHM_FILENAME, CHECKPOINT_WAL_FILENAME
    from tracker.progress import PASSES_DIRNAME
    from tracker.reminder import DRAFT_FILENAME, NEW_DRAFT_FILENAME
    from tracker.runner import AFTER_INSTALL_FILENAME, LAST_PASS_FILENAME, LOG_FILENAME, STATUS_PAGE_FILENAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME

    named = settings.settings_path()                     # the shell's, if it sets one
    with pytest.MonkeyPatch.context() as bare:
        bare.delenv(settings.ENV_SETTINGS_DIR, raising=False)
        beside = settings.settings_path()                 # the checkout's own
    places = []
    for where in dict.fromkeys((beside, named)):          # one entry when they agree
        places += [("settings file", where),
                   ("store", where.with_name(store.STORE_FILENAME)),
                   ("store's write-ahead log", where.with_name(store.STORE_WAL_FILENAME)),
                   ("store's shared memory", where.with_name(store.STORE_SHM_FILENAME)),
                   ("scheduled task file", where.with_name(SCHEDULE_XML_FILENAME)),
                   # Decision 159 writes these beside the store: the record
                   # checkpoint, the last pass's outcome, and the recovered
                   # copies of a return's lines (record-derived, like the store).
                   ("record checkpoint", where.with_name(CHECKPOINT_FILENAME)),
                   # Its write-ahead log and shared memory (P214), as the store's.
                   ("record checkpoint's write-ahead log", where.with_name(CHECKPOINT_WAL_FILENAME)),
                   ("record checkpoint's shared memory", where.with_name(CHECKPOINT_SHM_FILENAME)),
                   ("last-pass file", where.with_name(LAST_PASS_FILENAME)),
                   # Decision 209's note of the last after-install run, beside the store too.
                   ("after-install note", where.with_name(AFTER_INSTALL_FILENAME)),
                   ("recovered record copies", where.with_name(store.RECOVERED_DIR)),
                   # Decision 193 writes these beside the store too: the error
                   # log (its rotated copies share its name) and the passes' progress.
                   ("error log", where.with_name(errlog.ERROR_LOG_FILENAME)),
                   ("passes folder", where.with_name(PASSES_DIRNAME))]
    if os.environ.get(store.ENV_STORE):
        places.append(("store", Path(os.environ[store.ENV_STORE])))
    # The data home (decision 186, SPEC-186 section 9): the real one, which
    # default_data_home() works out without ENV_DATA_HOME; a machine that has
    # none (a SettingsError) adds nothing. Then whatever the shell names.
    try:
        places.append(("data home", settings.default_data_home()))
    except settings.SettingsError:
        pass
    # On a Mac the suite is pinned to the floor's answer (stand_on_the_floor),
    # so a bare test resolves the floor's data home for this account too: armed
    # as well, or a reach there would go unseen.
    if REAL_HOST_SYSTEM() == "darwin":
        try:
            places.append(("data home", floors_data_home()))
        except settings.SettingsError:
            pass
    if os.environ.get(settings.ENV_DATA_HOME, "").strip():
        places.append(("data home", Path(os.environ[settings.ENV_DATA_HOME])))
    try:
        places.append(("launch agent file", scheduling.launch_agent_path()))
    except RuntimeError:     # no home folder for this account: no agent to guard
        pass
    app = settings.app_dir()
    places += [("OCR scratch folder", app / settings.OCR_SCRATCH_DIRNAME),
               ("client tree", repo / CLIENTS_TREE),
               ("private tree", repo / PRIVATE_TREE),
               ("run log", repo / LOG_FILENAME),
               ("status page", repo / STATUS_PAGE_FILENAME),
               ("reminder draft", repo / DRAFT_FILENAME),
               ("reminder draft", repo / NEW_DRAFT_FILENAME)]
    return tuple(places)

#: Folders the walk of the checkout never enters: another tool's, and big.
_NEVER_ENTERED = {".git", "node_modules", ".venv", "venv"}
#: Folders the interpreter and pytest make of their own accord, not a test's doing.
_CACHES = {"__pycache__", ".pytest_cache", ".ruff_cache"}
#: Folders whose files change for reasons that are nobody's doing.
_UNWATCHED = {".claude", "build-portable", "dist", "build"}

def _walk_checkout(repo: Path, places):
    """Yield ``(relative path, DirEntry)`` for everything in the checkout, never
    entering ``.git``, the environments or a guarded place: listing a client
    tree or the scratch folder would trip the wire itself."""
    guarded = {os.path.normcase(os.path.abspath(path)) for _label, path in places}
    pending = [Path(repo)]
    while pending:
        folder = pending.pop()
        with os.scandir(folder) as entries:
            for entry in entries:
                if os.path.normcase(os.path.abspath(entry.path)) in guarded:
                    continue
                rel = os.path.relpath(entry.path, repo)
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in _NEVER_ENTERED:
                        continue
                    yield rel, entry
                    pending.append(Path(entry.path))
                else:
                    yield rel, entry

def checkout_folders(repo: Path, places) -> frozenset[str]:
    """Every folder in the checkout by relative path, the caches left out."""
    return frozenset(rel for rel, entry in _walk_checkout(repo, places)
                     if entry.is_dir(follow_symlinks=False)
                     and not _CACHES.intersection(Path(rel).parts))

def checkout_snapshot(repo: Path, places) -> dict[str, tuple[int, int]]:
    """Every file in the checkout by relative path, as ``(size, mtime_ns)``,
    the caches and the unwatched folders left out."""
    skip = _CACHES | _UNWATCHED
    found = {}
    for rel, entry in _walk_checkout(repo, places):
        if entry.is_dir(follow_symlinks=False) or skip.intersection(Path(rel).parts):
            continue
        stat = entry.stat(follow_symlinks=False)
        found[rel] = (stat.st_size, stat.st_mtime_ns)
    return found

def child_env(*, drop: tuple[str, ...] = (), **extra: str) -> dict[str, str]:
    """The environment every Python child the suite starts gets (decision 185):
    this process's, less ``drop``, with the tripwire first on the path and the
    repository after it, plus ``extra``."""
    env = {name: value for name, value in os.environ.items() if name not in drop}
    env["PYTHONPATH"] = os.pathsep.join([str(TRIPWIRE_DIR), str(REPO)])
    env.update(extra)
    return env

_STATE = pytest.StashKey[dict]()
#: The heading the session's verdict is printed under.
TRIPWIRE_HEADING = "decision 185: the suite reached a real place"

#: Where a Mac's suite keeps its temporary folders. ``/tmp`` is a link to
#: ``/private/tmp`` there; the real path is used, so ``resolve()`` changes nothing.
SHORT_TEMP_PARENT = Path("/private/tmp")

def _short_temp_root(config) -> Path | None:
    """On a Mac, a temporary root of the suite's own under ``/private/tmp``,
    unless ``--basetemp`` was given; ``None`` otherwise (and always off a Mac).

    pytest's default root on this Mac is the account's per-user cache folder,
    ``/private/var/folders/xx/<long>/T/pytest-of-<user>/pytest-N``: a test's
    ``tmp_path`` is about 145 characters long, where the floor's
    ``/tmp/pytest-of-<user>/pytest-N`` is about 40. ``layout.on_a_mac`` is
    pinned off for every test, so the room a return's path has is the absolute
    length, and the longer root fails tests (filer, content check, runner,
    shell) that fit with room to spare on the floor. A root of its own, one
    per session so a second run beside it never clears it, makes the length
    the floor's. A pytest-xdist worker is given ``<this root>/popen-gwN`` by
    its controller (``xdist.workermanage``), so the workers do not collide."""
    if sys.platform != "darwin" or config.option.basetemp is not None:
        return None
    return Path(tempfile.mkdtemp(prefix="ts-", dir=SHORT_TEMP_PARENT)).resolve()

#: The option that makes ``tests/test_golden.py`` write its recordings
#: rather than compare against them (SPEC-architecture J4, R4.3).
RECORD_GOLDEN = "--record-golden"

def pytest_addoption(parser):
    parser.addoption(RECORD_GOLDEN, action="store_true", default=False,
                     help="rewrite tests/golden/ from this run instead of comparing against it")

@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    worker = getattr(config, "workerinput", None)
    if worker is not None:
        _configure_worker(config)
        return
    short = _short_temp_root(config)
    if short is not None:
        config.option.basetemp = str(short)         # before pytest's own tmpdir plugin reads it
    places = real_places(REPO)                     # before own_folders(): the shell's own values count
    session = Path(tempfile.mkdtemp(prefix="tracker-suite-"))
    log = session / "tripwire.log"
    patch = pytest.MonkeyPatch()
    own_folders(patch, session / APP_FOLDER)
    patch.setenv(tripwire.ENV_TRIPWIRE, json.dumps(
        {"places": [[label, str(path)] for label, path in places], "log": str(log)}))
    patch.setenv("PYTHONPATH", os.pathsep.join(
        [str(TRIPWIRE_DIR), *filter(None, [os.environ.get("PYTHONPATH")])]))
    before = checkout_folders(REPO, places)
    # In-process: SEEN, and a Python child this process starts through a
    # watched route is judged (the tripwire's docstring lists the routes).
    # The log is written only from a process this one forks (a fork that execs).
    tripwire.install(tripwire.prepare(places), log=str(log), children=os.environ[tripwire.ENV_TRIPWIRE])
    config.stash[_STATE] = {"patch": patch, "session": session, "log": log, "short": short,
                            "places": places, "before": before, "said": [], "workers": []}

def _configure_worker(config):
    """A pytest-xdist worker joins the controller's session and arms no new one.

    The controller armed the tripwire once, before it started the worker, and
    the worker inherited that environment: its folders are the session's, and
    its places are the controller's. A worker that armed its own would keep
    a verdict of its own that xdist never reads back - xdist ignores a
    worker's exit status. So the worker reads the places and the log from the
    inherited :data:`ENV_TRIPWIRE`, watches its own process and the Python
    children it starts, and hands the hits it saw to the controller in
    ``workeroutput`` (:func:`pytest_sessionfinish`)."""
    armed = os.environ[tripwire.ENV_TRIPWIRE]
    spec = json.loads(armed)
    places = tuple((label, Path(path)) for label, path in spec["places"])
    tripwire.install(tripwire.prepare(places), log=spec["log"], children=armed)
    config.stash[_STATE] = {"worker": True, "said": []}

#: What the session says of a line in the tripwire's log it cannot read.
UNREADABLE_LOG_LINE = "the tripwire's log has a line it cannot read"
#: What the session says when the tripwire's log cannot be read at all.
UNREADABLE_LOG = "the tripwire's log could not be read"

def _hit_said(test: str, event: str, label: str) -> str:
    """One hit as the session says it: a reach for a place, or a child
    started around the wire."""
    if label.startswith(tripwire.UNARMED):
        return f"{test}: {event} started an {label}"
    return f"{test}: {event} of the checkout's {label}"

def tripwire_log_said(lines) -> list[str]:
    """Each line of the session's tripwire log as the session says it. A line
    that is not a hit the wire wrote - a torn write, a stray byte - is said
    plainly as a violation, never an internal error: an unread line might
    have been a hit."""
    said = []
    for number, line in enumerate(lines, start=1):
        try:
            hit = json.loads(line)
            said.append(f"{_hit_said(hit['test'], hit['event'], hit['label'])} (pid {hit['pid']})")
        except (ValueError, TypeError, KeyError, AttributeError):
            said.append(f"{UNREADABLE_LOG_LINE} (line {number})")
    return said

def read_tripwire_log(log: Path) -> list[str]:
    """The session's tripwire log as the session says it. No file is no hit;
    a log that exists and cannot be read might hold one, so it is said as a
    violation, never skipped and never an internal error."""
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return []                      # nothing was ever written: no child hit anything
    except OSError as exc:
        return [f"{UNREADABLE_LOG} ({type(exc).__name__})"]
    return tripwire_log_said(lines)

@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session):
    state = session.config.stash[_STATE]
    said = [_hit_said(test, event, label) for test, event, label in tripwire.SEEN]
    if state.get("worker"):
        session.config.workeroutput[WORKER_SAID_KEY] = said     # the controller gives the verdict
        return
    said += state["workers"]
    said += read_tripwire_log(state["log"])
    said += [f"the session left a new folder in the checkout: {rel}"
             for rel in sorted(checkout_folders(REPO, state["places"]) - state["before"])]
    if said:
        state["said"] = said
        session.exitstatus = pytest.ExitCode.TESTS_FAILED

#: Where a pytest-xdist worker puts the hits it saw, for the controller to collect.
WORKER_SAID_KEY = "tripwire_said"
#: What the session says of a worker that ended without handing over its hits.
LOST_WORKER = "a pytest-xdist worker ended without giving the tripwire's verdict"

@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    """The controller collects what each pytest-xdist worker saw. A worker
    that ended without saying is itself said: its hits might be lost."""
    workers = node.config.stash[_STATE]["workers"]
    output = getattr(node, "workeroutput", None) or {}
    if WORKER_SAID_KEY in output:
        workers += output[WORKER_SAID_KEY]
    else:
        workers.append(f"{LOST_WORKER} ({node.gateway.id})")

def pytest_terminal_summary(terminalreporter, config):
    said = config.stash[_STATE]["said"]
    if said:
        terminalreporter.write_sep("=", TRIPWIRE_HEADING, red=True)
        for line in said:
            terminalreporter.write_line(line)

def pytest_unconfigure(config):
    state = config.stash.get(_STATE, None)
    if state is None:
        return
    store.close()
    if state.get("worker"):
        return                         # the controller made the session's folders and removes them
    state["patch"].undo()
    shutil.rmtree(state["session"], ignore_errors=True)
    shutil.rmtree(data_home_for(state["session"] / APP_FOLDER), ignore_errors=True)
    if state["short"] is not None:
        shutil.rmtree(state["short"], ignore_errors=True)

# ---------------------------------------------------- the office-shaped copy ----

#: Set to run the whole suite, not the bounded set, in the office-shaped copy.
ENV_OFFICE_SHAPED_FULL = "TRACKER_OFFICE_SHAPED_FULL"

@pytest.fixture(scope="session")
def office_shaped_copy(tmp_path_factory):
    """The checkout copied with fabricated, real-looking files beside the app
    (decision 185): a settings file naming a clients root with one
    engagement, a store, the retired scratch folder with a page in it, the
    scheduled task's file, a client tree and a run log - everything the
    tripwire guards, in the shape an office checkout has it. Returns the copy
    and a ``{relative path: bytes}`` record of the fabricated files, so a
    nested run can be shown to have changed none of them.

    The copy is a Git repository of its own (``git init``, ``git add -A``) so
    a test that asks ``git ls-files`` gets the copy's answer."""
    from tracker.manifest import RequestItem

    base = tmp_path_factory.mktemp("office")
    copy = base / "checkout"
    listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                            cwd=REPO, capture_output=True, text=True, check=True).stdout
    for rel in filter(None, listed.split("\0")):
        source = REPO / rel
        if not source.is_file():
            continue                       # deleted in the working tree, not yet staged
        target = copy / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    office_root = base / "office-root"
    # A session fixture is set up before the function-scoped autouse fixtures
    # that give a test its own store and its pins, so here it has only the
    # session's: under pytest-xdist every worker's session fixture and the
    # tests it ran shared the one store file of the controller's app folder,
    # and a second "Test Household / 2025 / 1040 - Test Client" met the first
    # one's applied line with a journal of its own that had none (the store
    # refused it: the journal 0, the store 1). So the engagement is made in a
    # store of this fixture's own, under the suite's default computer, and the
    # connection is let go before the patch is.
    with pytest.MonkeyPatch.context() as patch:
        own_folders(patch, base / APP_FOLDER)
        stand_on_the_floor(patch)
        patch.setattr(layout, "on_a_mac", lambda: False)
        store.close()
        try:
            make_engagement(office_root, [RequestItem(identifier="A01", document="W-2")])
        finally:
            store.close()
    (copy / settings.SETTINGS_FILENAME).write_text(json.dumps(
        {settings.KEY_CLIENTS_ROOT: str(office_root), settings.KEY_FIRM: PRIVATE_TREE}), encoding="utf-8")
    store.open(copy / store.STORE_FILENAME).close()
    (copy / settings.OCR_SCRATCH_DIRNAME).mkdir()
    (copy / settings.OCR_SCRATCH_DIRNAME / "page-1.png").write_bytes(b"fabricated")
    from tracker.runner import LOG_FILENAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    (copy / SCHEDULE_XML_FILENAME).write_text("<Task/>", encoding="utf-8")
    (copy / CLIENTS_TREE / TEST_HOUSEHOLD).mkdir(parents=True)
    (copy / CLIENTS_TREE / TEST_HOUSEHOLD / "note.txt").write_text("fabricated", encoding="utf-8")
    (copy / LOG_FILENAME).write_text("fabricated\n", encoding="utf-8")
    fabricated = {}
    for path in (copy / settings.SETTINGS_FILENAME, copy / store.STORE_FILENAME,
                 copy / settings.OCR_SCRATCH_DIRNAME / "page-1.png", copy / SCHEDULE_XML_FILENAME,
                 copy / CLIENTS_TREE / TEST_HOUSEHOLD / "note.txt", copy / LOG_FILENAME):
        fabricated[path.relative_to(copy).as_posix()] = path.read_bytes()

    for command in (["git", "init", "-q"], ["git", "add", "-A"]):
        subprocess.run(command, cwd=copy, capture_output=True, check=True)
    return copy, fabricated

def run_in_copy(copy: Path, *args: str, timeout: int = 600, **extra: str) -> subprocess.CompletedProcess:
    """``python -m pytest -q <args>`` in the copy, started as a fresh shell
    would start it: no settings folder, store or data home of the suite's.
    The outer tripwire's variable is kept, so this session watches the
    nested one."""
    env = child_env(drop=(settings.ENV_SETTINGS_DIR, store.ENV_STORE, settings.ENV_DATA_HOME,
                          "PYTEST_CURRENT_TEST"), **extra)
    return subprocess.run([sys.executable, "-m", "pytest", "-q", *args], cwd=copy, env=env,
                          capture_output=True, text=True, timeout=timeout)
