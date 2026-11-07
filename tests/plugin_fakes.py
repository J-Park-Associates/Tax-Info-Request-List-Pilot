"""The stand-ins every test gets, each a ``MonkeyPatch`` of its own on one module seam: the firm-cache fill, the
after-install step's test-cache job, the scheduler and the floor's computer, the reading child and the room measure.
Also what a test turns them off with (``on_a_mac``, ``a_mac``, ``path_setting``) and the fakes it uses then (``FakeLaunchd``,
``FakeTmutil``). Decisions 150, 209 and P29 stand behind them, and the pins of SPEC-mac.

The second plugin in ``tests/conftest.py``'s ``pytest_plugins``: pytest sets a plugin's autouse fixtures up in the list's
order and, inside one plugin, by name, so its five autouse fixtures run after the app folder's and before the
agreement fixtures, as ``tests/test_suite_shape.py``'s ``AUTOUSE_ORDER`` pins. It imports nothing from another plugin,
and ``plugin_session`` reads ``REAL_HOST_SYSTEM`` and ``stand_on_the_floor`` from it (a plugin may import from one
listed before it, never from one listed after; a plugin never imports a fixture function by name, because pytest
would register it a second time under the importing plugin). Every ``REAL_*`` capture is taken at import, before any
test runs.

**Reading in the test's own process** (``reading_in_this_process``,
decision 150). The pass reads each document in a child process it can
stop, and the suite's stand-in readers - a fake OCR, a slow reader, a
reader that must never be called - are patched into the test's process,
which a child started fresh never sees. So every test reads in its own
process, and the tests about the child (``tests/test_content_check.py``,
the decision-150 section) turn the child back on.
"""
from __future__ import annotations

import functools
import io
import os
import platform

import pytest

from tracker import after_install, content_check, fsio, layout, locking, runner, scheduling, settings


@pytest.fixture(autouse=True)
def reading_in_this_process():
    """Every test reads a document in its own process (decision 150).

    ``content_check.judge_bounded()`` reads in a child process in the
    tracker, and a child imports the reader afresh: the patches the suite
    makes to it would not be there. A ``MonkeyPatch`` of its own, like the
    store's, so a test calling ``monkeypatch.undo()`` does not turn the
    child on by accident; a test about the child turns it on with its own.
    """
    patch = pytest.MonkeyPatch()
    patch.setattr(content_check, "READ_IN_A_CHILD", False)
    try:
        yield
    finally:
        patch.undo()

@pytest.fixture(autouse=True)
def room_is_the_absolute_length():
    """Room is measured as the absolute length of a path, on every machine
    (SPEC-mac R9).

    On a Mac the tracker measures room as if the clients folder sat under a
    Windows root (``layout.measured_length``). The suite's root-length tests
    are written against absolute lengths, so they mean the same on a Mac as
    on Linux and Windows: this pins ``layout.on_a_mac`` off for every test.
    A test that is about a Mac says so with the :func:`on_a_mac` fixture. A
    ``MonkeyPatch`` of its own, like the store's, so ``monkeypatch.undo()``
    in a test cannot lift it."""
    patch = pytest.MonkeyPatch()
    patch.setattr(layout, "on_a_mac", lambda: False)
    try:
        yield
    finally:
        patch.undo()

@pytest.fixture
def on_a_mac(monkeypatch):
    """This test is on a Mac as far as room is measured: lifts
    :func:`room_is_the_absolute_length` for it (``layout.on_a_mac``)."""
    monkeypatch.setattr(layout, "on_a_mac", lambda: True)

#: The real answer to "is there a scheduler here", for the one test that
#: asks it of the machine (decision 209; SPEC-mac R24 renamed it).
REAL_SCHEDULER_HERE = scheduling.scheduler_here
#: The real ``schtasks`` runner, for the one test of its time limit, which
#: stands in for ``subprocess.run`` so no real Task Scheduler is reached.
REAL_SCHTASKS = scheduling._schtasks
#: The same for ``launchctl`` and ``tmutil`` (SPEC-mac R7, R24).
REAL_LAUNCHCTL = scheduling._launchctl
REAL_TMUTIL = after_install._tmutil

def _schtasks_unfaked(command):
    raise AssertionError(f"a test reached schtasks without faking it: {command}")

def _launchctl_unfaked(command):
    raise AssertionError(f"a test reached launchctl without faking it: {command}")

def _tmutil_unfaked(command):
    raise AssertionError(f"a test reached tmutil without faking it: {command}")

#: The computer's own answer to ``settings.host_system``, kept before the
#: autouse guard below pins it to the floor's on a Mac: for what guards the
#: *real* computer (the tripwire's data home) and must be asked as it is.
REAL_HOST_SYSTEM = settings.host_system

#: ``platform.node`` as the platform itself has it, kept before any test can
#: replace it: a test that has not is on the machine it really runs on.
REAL_NODE = platform.node

class _TheFloorsPlatform:
    """``platform`` as the lock layer sees it on a Mac under the suite's
    pin. ``this_host()`` there answers ``platform.node()`` (the floor's way)
    and not the Mac's ``LocalHostName``, so a test that fakes the computer's
    name through ``platform.node`` gets its fake back. A test that does not
    fake it gets the Mac's real ``LocalHostName``, the name a child process
    running ``this_host()`` answers, so a lock a real child holds is still
    this machine's. Everything else is ``platform``'s own."""

    _real_name: str | None = None

    def __getattr__(self, name):
        return getattr(platform, name)

    @classmethod
    def node(cls) -> str:
        if platform.node is not REAL_NODE:
            return platform.node()
        if cls._real_name is None:
            cls._real_name = locking._local_host_name() or REAL_NODE()
        return cls._real_name

def _not_a_mac(original):
    """The lock layer's and the flush's ``_on_a_mac`` as ``False``, still
    *reading* as the original (``functools.wraps``), because
    ``tests/test_fsio.py`` holds the two copies identical by their source."""
    @functools.wraps(original)
    def not_a_mac() -> bool:
        return False

    return not_a_mac

def _the_floors_answer(original):
    """``settings.host_system`` answering ``"posix"``, still *reading* as the
    original (``functools.wraps``), because ``tests/test_admission.py`` digests
    ``inspect.getsource(settings.host_system)`` into the store's admission
    version and the pin must not change it."""
    @functools.wraps(original)
    def posix() -> str:
        return "posix"

    return posix

def stand_on_the_floor(patch: pytest.MonkeyPatch) -> None:
    """On a Mac, make the seams that name the computer answer the Linux
    floor's through ``patch``; on any other computer, do nothing. Its own
    function so the suite-shape test can run it against a faked Mac."""
    if settings.host_system() == "darwin":
        patch.setattr(settings, "host_system", _the_floors_answer(settings.host_system))
        for module in (locking, fsio):
            patch.setattr(module, "_on_a_mac", _not_a_mac(module._on_a_mac))
        patch.setattr(locking, "platform", _TheFloorsPlatform())
        # Asked once now, before any test body can fake ``subprocess.run`` or
        # the name, so the cached answer is the Mac's real one.
        _TheFloorsPlatform.node()

@pytest.fixture(autouse=True)
def no_task_scheduler_unless_faked():
    """No test registers or deletes a real scheduled task (decision 209).

    Saving a clients root, the app's launch and Setup all run the
    after-install step, which registers the daily job on a Windows machine
    that has Task Scheduler - the Windows CI runner included - and on a Mac
    as a launchd agent that excludes the data home from Time Machine
    (SPEC-mac R7, R24). Every test starts on a computer with none; a test
    about registering says it is on Windows (and fakes ``schtasks`` itself)
    or on a Mac (:func:`a_mac`, which fakes ``launchctl`` and ``tmutil``),
    and one that forgets fails here rather than reaching the real one. A
    ``MonkeyPatch`` of its own, like the store's, so ``monkeypatch.undo()``
    in a test cannot lift it.

    The suite's default computer is the Linux floor's: on a Mac,
    ``settings.host_system`` is pinned to ``"posix"`` here, so a test that
    never said which computer it is on does not take the Mac branches (the
    real ``tmutil``, the Mac's own name, the Mac's vocabulary). A test about
    a Mac says :func:`a_mac` or ``mac``, which pin ``"darwin"`` on top.

    The lock layer and the flush have a seam of their own: ``_on_a_mac`` in
    ``locking`` and in ``fsio`` reads ``sys.platform`` (neither may import
    ``settings``). On a Mac it would make ``this_host()`` answer the Mac's
    ``LocalHostName`` instead of the faked ``platform.node()`` every test
    sets, the flush ask for ``F_FULLFSYNC`` instead of the ``os.fsync`` the
    tests watch, and ``boot_time()`` read the Mac's ``sysctl`` instead of
    answering None (no boot rule) as it does where ``/proc/uptime`` is
    missing. So :func:`stand_on_the_floor` pins both ``False`` too -
    :func:`a_mac` leaves them so: the tests about a Mac's schedule fake the
    computer's name through ``platform.node()`` (the ``mac`` fixture) and
    expect it back - and shows the lock layer ``platform.node()`` (see
    :class:`_TheFloorsPlatform`). ``tests/test_locking.py`` and
    ``tests/test_fsio.py`` set ``_on_a_mac`` to ``True`` where they test the
    Mac's lock name and full flush.
    """
    patch = pytest.MonkeyPatch()
    stand_on_the_floor(patch)
    patch.setattr(scheduling, "scheduler_here", lambda: False)
    patch.setattr(scheduling, "_schtasks", _schtasks_unfaked)
    patch.setattr(scheduling, "_launchctl", _launchctl_unfaked)
    patch.setattr(after_install, "_tmutil", _tmutil_unfaked)
    try:
        yield
    finally:
        patch.undo()

class Said:
    """What a faked ``launchctl`` or ``tmutil`` answers: an exit code and
    what it printed."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr

class FakeLaunchd:
    """A launchd that keeps every ``launchctl`` command it is given, in order,
    and answers as the real one does for the verbs the schedule uses: an
    agent is loaded after ``bootstrap`` and not after ``bootout``; ``print``,
    ``kickstart`` and ``bootout`` of one that is not loaded say so (exit 113
    and 3); ``print-disabled`` lists the label when ``switched_off`` is set.
    ``refuse`` maps a verb to the exit code and words it answers with
    instead."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self.loaded = False
        self.switched_off = False
        self.refuse: dict[str, tuple[int, str]] = {}

    def verbs(self) -> list[str]:
        return [command[1] for command in self.calls]

    def __call__(self, command):
        self.calls.append(list(command))
        verb = command[1]
        if verb in self.refuse:
            code, words = self.refuse[verb]
            return Said(code, stderr=words)
        if verb == "bootstrap":
            self.loaded = True
        elif verb == "bootout":
            was, self.loaded = self.loaded, False
            return Said(0 if was else 3, stderr="" if was else "Boot-out failed: 3: No such process")
        elif verb in ("print", "kickstart"):
            return Said(0 if self.loaded else 113, stderr="" if self.loaded else "Could not find service")
        elif verb == "print-disabled":
            state = "disabled" if self.switched_off else "enabled"
            return Said(0, stdout=f'disabled services = {{\n\t"{scheduling.LAUNCH_AGENT_LABEL}" => {state}\n}}\n')
        return Said()

class FakeTmutil:
    """A ``tmutil`` that keeps every command and holds a set of excluded
    folders: ``addexclusion`` adds one, ``isexcluded`` answers the way
    ``tmutil`` does (``[Excluded]`` or ``[Included]``, exit 0 either way).
    ``refuse`` maps a verb to the exit code and words it answers with."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self.excluded: set[str] = set()
        self.refuse: dict[str, tuple[int, str]] = {}

    def __call__(self, command):
        self.calls.append(list(command))
        verb, folder = command[1], command[-1]
        if verb in self.refuse:
            code, words = self.refuse[verb]
            return Said(code, stderr=words)
        if verb == "addexclusion":
            self.excluded.add(folder)
        elif verb == "isexcluded":
            return Said(0, stdout=f"[{'Excluded' if folder in self.excluded else 'Included'}]    {folder}\n")
        return Said()

class AMac:
    """What :func:`a_mac` hands a test: the fake launchd and the fake tmutil."""

    def __init__(self, launchd, tmutil):
        self.launchd, self.tmutil = launchd, tmutil

@pytest.fixture
def a_mac(monkeypatch, tmp_path):
    """This test runs on a Mac, as far as the schedule goes (SPEC-mac R7, R24):
    ``settings.host_system`` answers ``"darwin"`` (the seam, never the
    platform), the scheduler is there, the account's home is a folder of the
    test's own - the agent's file lands in its ``Library/LaunchAgents`` - every
    disk is a fixed one (the disk rule is job 1's), and ``launchctl`` and
    ``tmutil`` are the fakes above. The user id is 501, a Mac's first account."""
    home = tmp_path / "home"
    home.mkdir()
    # ``Path.home()`` reads HOME on a Mac and Linux and USERPROFILE on Windows;
    # both are the test's own, and the user id is a seam (Windows has no getuid).
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(scheduling, "_uid", lambda: 501)
    monkeypatch.setattr(settings, "host_system", lambda: "darwin")
    monkeypatch.setattr(settings, "drive_type", lambda path: settings.DRIVE_FIXED)
    monkeypatch.setattr(scheduling, "scheduler_here", lambda: True)
    mac = AMac(FakeLaunchd(), FakeTmutil())
    monkeypatch.setattr(scheduling, "_launchctl", mac.launchd)
    monkeypatch.setattr(after_install, "_tmutil", mac.tmutil)
    return mac

#: The pass's real fill of the firm view's cache (P201), kept before any
#: test can stand in for it, for the tests that ask for the real one.
REAL_FILL = runner.fill_firm_cache

@pytest.fixture(autouse=True)
def fills_asked():
    """No pass starts a real firm summary unless its test asks (P201,
    ``pilot/SPEC-firm-cache-fill.md`` R8). Every real pass over the saved
    root asks one at its end, in a child Python that writes
    ``firm-view.json``; across the suite that is a second interpreter per
    pass and a file in every data folder. Here the fill answers "filled"
    and records the root and product it was asked for; a test of the fill
    puts :data:`REAL_FILL` back with its own ``monkeypatch``.
    """
    asked: list[tuple[str, str]] = []

    def recorded(root, *, product=""):
        asked.append((str(root), product))
        return ""

    patch = pytest.MonkeyPatch()
    patch.setattr(runner, "fill_firm_cache", recorded)
    try:
        yield asked
    finally:
        patch.undo()

@pytest.fixture(autouse=True)
def no_real_test_cache_is_cleared(tmp_path_factory):
    """No test clears this checkout's own ``.pytest_cache`` (SPEC-209 R8).

    Every door of the after-install step runs its test-cache job, and the
    suite is running from that very checkout: left alone, the first test
    to save a root would remove the cache pytest is writing. The job is
    pointed at a folder that is never made; a test about the job names its
    own fabricated checkout. Its own ``MonkeyPatch``, as above."""
    patch = pytest.MonkeyPatch()
    patch.setattr(after_install, "CHECKOUT", tmp_path_factory.getbasetemp() / "no-checkout-here")
    try:
        yield
    finally:
        patch.undo()

#: The two settings a claim about room is made under (pilot decision P29):
#: whatever this machine allows, and a Windows with long paths off.
PATH_SETTINGS = ("as this machine allows", "long paths off")
#: What Windows with long paths off refuses: a file path of MAX_PATH (260)
#: characters or more - the null that ends it is counted - and a folder of
#: MAX_PATH less 12 (248) or more, to leave an 8.3 name room inside it.
_SHORT_FILE, _SHORT_FOLDER = 260, 248

def refuse_what_windows_refuses(monkeypatch) -> None:
    """Make this machine refuse, as a Windows with long paths off does, a
    folder of 248 characters or more and a file path of 260 or more - with
    the ``FileNotFoundError`` Windows raises for either (``WinError 206``).

    So "long paths off" is a claim on Linux too, not only on the office's
    Windows: a room rule that lets a path through that Windows would refuse
    fails here the way it failed there, and so does a test that builds a
    folder deeper than Windows would make it. Only ``os.mkdir``, ``open``
    (builtins and ``io``, which ``Path.open`` and ``shutil`` use),
    ``os.open``, ``os.replace`` and ``os.rename`` are held to it: every
    folder and file the tracker makes passes through one of them.
    """
    import builtins
    import errno

    def too_long(path, limit: int) -> bool:
        if isinstance(path, int):
            return False
        return len(os.path.abspath(os.fsdecode(os.fspath(path)))) >= limit

    def refused(path):
        return FileNotFoundError(errno.ENOENT, "The filename or extension is too long", os.fspath(path))

    real_mkdir, real_open, real_os_open = os.mkdir, builtins.open, os.open
    real_replace, real_rename = os.replace, os.rename

    def mkdir(path, *args, **kwargs):
        if too_long(path, _SHORT_FOLDER):
            raise refused(path)
        return real_mkdir(path, *args, **kwargs)

    def guarded_open(file, *args, **kwargs):
        if too_long(file, _SHORT_FILE):
            raise refused(file)
        return real_open(file, *args, **kwargs)

    def os_open(path, *args, **kwargs):
        if too_long(path, _SHORT_FILE):
            raise refused(path)
        return real_os_open(path, *args, **kwargs)

    def moved(real):
        def move(src, dst, *args, **kwargs):
            for path in (src, dst):
                if too_long(path, _SHORT_FILE):
                    raise refused(path)
            return real(src, dst, *args, **kwargs)
        return move

    monkeypatch.setattr(os, "mkdir", mkdir)
    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)
    monkeypatch.setattr(os, "open", os_open)
    monkeypatch.setattr(os, "replace", moved(real_replace))
    monkeypatch.setattr(os, "rename", moved(real_rename))

@pytest.fixture(params=PATH_SETTINGS)
def path_setting(request, monkeypatch) -> str:
    """Run a claim about room under both settings (pilot decision P29).

    *As this machine allows* changes nothing: Linux, macOS and a long-path
    Windows measure against 260, a Windows with long paths off against 259
    and its folders. *Long paths off* makes ``layout.short_paths`` say so
    and holds this machine to what that Windows refuses
    (:func:`refuse_what_windows_refuses`). Neither is ever skipped: a
    machine with long paths off runs the stricter claim twice, because a
    fixture cannot build there what only long paths allow. A claim reads
    its numbers from ``layout.path_limit`` and :func:`floor_return`.
    """
    from tracker import layout

    if request.param == "long paths off":
        monkeypatch.setattr(layout, "short_paths", lambda: True)
        refuse_what_windows_refuses(monkeypatch)
    return request.param
