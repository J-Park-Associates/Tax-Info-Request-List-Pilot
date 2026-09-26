r"""The suite's tripwire (decision 185): no test, and no Python child a test
starts, may open, list, make, move, remove or connect to a place where a real
settings file, store, scratch folder or client tree resolves on this machine.

**Why an audit hook.** ``sys.addaudithook`` is called for every open, listing,
folder creation, rename, removal, copy and SQLite connection the interpreter
makes, whichever module asked for it, before the operation happens. A hook
cannot be removed once added, and raising from it stops the operation: the
file is not read, the database is not opened, the folder is not made. A
patched ``open`` or a fixture that checks paths sees only what goes through
it; the interpreter's own hook sees everything Python does.

**Why also a file log.** A child's violation raises in the child, where the
test may tolerate a non-zero exit or never read its output. So a child armed
from the environment also appends each hit, as one JSON line with its process
id, to the session's log, and the pytest process fails the session on any
line there as it does on any hit of its own (:data:`SEEN`) - even when the
test swallowed the error.

**One module for both.** The pytest process imports it as
``tests.tripwire.sitecustomize`` and installs it itself; every Python child
finds it as ``sitecustomize`` on ``PYTHONPATH`` and arms itself from
:data:`ENV_TRIPWIRE` at start-up, before its first import. So it is standard
library only and imports nothing of the package or the tests: a child may
start anywhere.

**What the tripwire buys, and what it does not** (security 8).
It **detects and stops** every open, listing, folder creation, rename, removal,
copy, link and SQLite connection that Python code makes to a guarded place.
That holds in the pytest process and in every Python child that inherits the
suite's environment: `subprocess` children and the reading child. It then
fails the session.

It also **watches every Python child the pytest process starts**
(``subprocess.Popen``, ``os.posix_spawn``, ``os.spawn``, ``os.exec``). A child
is a Python interpreter when its program is this interpreter (after
``realpath`` and ``normcase``) or its name starts with ``python``. Such a child
is recorded - not stopped, so a test that wanted the child's result gets the
session's plain verdict rather than a confusing error - when its environment
(``env``, or this process's when none is given) lacks
:data:`ENV_TRIPWIRE` or carries a value other than the session's, when its
``PYTHONPATH`` does not begin with the tripwire folder of the process's own
session (the folder this module lives in), or when its flags carry ``-I``,
``-E`` or ``-S``, alone or combined. Only the pytest process enforces this; a
child need not. A nested session in the office-shaped copy is its own
session: its pytest process imports the copy's module, so its children must
begin with the copy's tripwire folder, which is what its ``pytest_configure``
gives them; the outer session sees the nested run started with its own.

It **does not see**:
- children that are not Python (`node`, `git`, `cmd`, `icacls` in
  `tests/test_single_source.py`, `tests/test_api.py:4232`, `tests/samples.py`,
  `tests/test_ocr.py`), which are never pointed at a guarded place today;
- a Python child started by a Python child, unarmed: only the pytest process
  judges how a child starts;
- a native library that opens a file itself (pdfium, ONNX Runtime), unless
  Python opened it first. Such a library is only handed a path a test chose;
- `os.stat`/`exists` (no audit event): existence is learned, never content. §3.2
  moves the one existence check that mattered to an open;
- a relative name given to os.open (how shutil.rmtree walks with dir_fd) is not
  judged, since the event does not carry the descriptor: every ``open`` event
  with no mode and a path that is not absolute is passed over. The walk's own
  top folder, named in full, is judged;
- an alias that does not contain the place's name (a Windows 8.3 short name
  such as `SETTIN~1.JSO`), or an administrative share naming a local disk
  (``\\localhost\C$\...``). A verbatim prefix (``\\?\``, ``\\?\UNC\``) is
  stripped before comparing, so that spelling is seen;
- code that deliberately goes around it (`ctypes`). It is a guard rail in the
  suite, not a wall. The wall is 186's placement plus the account boundary
  (Jason's decision (a)).
In a child it shadows another `sitecustomize` on the path while the suite runs.
CI's `setup-python` installs none.
"""
import json
import os
import sys

ENV_TRIPWIRE = "TRACKER_TEST_TRIPWIRE"
#: The audit events that reach a place, and which arguments are paths.
WATCHED = {
    "open": (0,), "os.listdir": (0,), "os.scandir": (0,), "os.mkdir": (0,),
    "os.rename": (0, 1), "os.remove": (0,), "os.rmdir": (0,),
    "shutil.copyfile": (0, 1), "shutil.copytree": (0, 1), "shutil.rmtree": (0,),
    "sqlite3.connect": (0,), "os.link": (0, 1), "os.symlink": (0, 1),
}
#: Where an event carries the directory descriptor a relative path is
#: resolved against. A relative path with one is not the working folder's.
DIR_FDS = {"os.mkdir": (2,), "os.rmdir": (1,), "os.remove": (1,), "os.rename": (2, 3),
           "os.link": (2, 3), "os.symlink": (2,)}
#: The audit events that start a program: where its path, its arguments and
#: its environment sit in the event's arguments.
STARTS = {"subprocess.Popen": (0, 1, 3), "os.posix_spawn": (0, 1, 2),
          "os.spawn": (1, 2, 3), "os.exec": (0, 1, 2)}
#: The label a Python child started around the tripwire is recorded under.
UNARMED = "unarmed Python child"
#: The interpreter flags that start a child without its sitecustomize or its
#: environment: isolated, no ``PYTHON*`` variables, no ``site``.
UNARMING_FLAGS = frozenset("IES")
#: The folder this module lives in: the tripwire folder of this session.
HERE = os.path.dirname(os.path.abspath(__file__))
SEEN: list[tuple[str, str, str]] = []      # (test, event, label), this process

_IN_HOOK = [False]                         # the re-entry guard for the log


class TripwireError(RuntimeError):
    """Not an OSError on purpose: most code that expects a missing file catches
    OSError, and this must not read as one."""


def _unverbatim(path: str) -> str:
    """``path`` without a Windows verbatim prefix: ``\\\\?\\UNC\\server\\share``
    is ``\\\\server\\share`` and ``\\\\?\\C:\\x`` is ``C:\\x``, so a place is
    not missed for being spelled the long way."""
    if path[:8].upper() == "\\\\?\\UNC\\":
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def _norm(path: str, pathmod=os.path) -> str:
    """``path`` absolute, case-folded where the filesystem folds case, and
    without a verbatim prefix. ``pathmod`` is for a test that feeds another
    platform's spelling (``ntpath`` on Linux)."""
    return pathmod.normcase(pathmod.abspath(_unverbatim(path)))


def _resolved(path: str, pathmod=os.path) -> str:
    """``path`` as the filesystem resolves it, compared the way :func:`_norm` compares."""
    return pathmod.normcase(_unverbatim(pathmod.realpath(path)))


def prepare(places) -> tuple:
    """``[(label, path)]`` -> ``((label, spelled, real, name), ...)``: each
    place as it is spelled, as the filesystem resolves it, and by its name."""
    out = []
    for label, path in places:
        path = os.fspath(path)
        out.append((label, _norm(path), _resolved(path),
                    os.path.normcase(os.path.basename(os.path.abspath(path)))))
    return tuple(out)


def _hits(path: str, place: str, name: str) -> bool:
    """``path`` is the place, lies under it, or is a sibling named after it
    (``settings.json.<pid>.<hex>.tmp``, the atomic write's temporary)."""
    if path == place or path.startswith(place.rstrip(os.sep) + os.sep):
        return True
    folder, base = os.path.split(path)
    return folder == os.path.dirname(place) and base.startswith(name + ".")


def _as_path(event: str, arg) -> str | None:
    if arg is None or isinstance(arg, int):
        return None
    try:
        text = os.fsdecode(os.fspath(arg))
    except TypeError:
        return None
    if event == "sqlite3.connect":
        if text == ":memory:" or text == "":
            return None
        if text.startswith("file:"):
            text = text[len("file:"):].split("?", 1)[0]
            if not text or text == ":memory:":
                return None
    return text


def _against_a_descriptor(event: str, args: tuple) -> bool:
    """Whether a relative path in ``args`` is resolved against a directory
    descriptor, not the working folder. ``os.open`` audits as ``open`` with
    no mode and without its ``dir_fd``, which is how ``shutil.rmtree`` walks
    a tree: such a relative name cannot be placed, so it is not judged."""
    if event == "open":
        return len(args) > 1 and args[1] is None
    return any(i < len(args) and args[i] is not None for i in DIR_FDS.get(event, ()))


def judge(event: str, args: tuple, prepared: tuple) -> str | None:
    """The label of the guarded place ``event`` with ``args`` reaches, or None."""
    positions = WATCHED.get(event)
    if positions is None:
        return None
    for index in positions:
        if index >= len(args):
            continue
        text = _as_path(event, args[index])
        if text is None:
            continue
        if not os.path.isabs(text) and _against_a_descriptor(event, args):
            continue
        if event == "os.symlink" and index == 0 and not os.path.isabs(text):
            # A link's relative target is read from the link's own folder.
            destination = _as_path(event, args[1]) if len(args) > 1 else None
            if destination is None:
                continue
            text = os.path.join(os.path.dirname(os.path.abspath(destination)), text)
        spelled = _norm(text)
        for label, place, _real, name in prepared:
            if _hits(spelled, place, name):
                return label
        if any(name and name in spelled for _l, _p, _r, name in prepared):
            real = _resolved(text)
            for label, _place, place_real, name in prepared:
                if _hits(real, place_real, name):
                    return label
    return None


def _is_python(program) -> bool:
    """Whether ``program`` is a Python interpreter: this one, or one named so."""
    try:
        text = os.fsdecode(os.fspath(program))
    except TypeError:
        return False
    if os.path.basename(text).lower().startswith("python"):
        return True
    try:
        return _resolved(text) == _resolved(sys.executable)
    except (OSError, ValueError):
        return False


def _split(args) -> list[str]:
    """A command line as its words: a list as given, a string (Windows) split
    on spaces outside double quotes."""
    if isinstance(args, (str, bytes)):
        text = os.fsdecode(args)
        words, word, quoted = [], "", False
        for char in text:
            if char == '"':
                quoted = not quoted
            elif char.isspace() and not quoted:
                if word:
                    words.append(word)
                word = ""
            else:
                word += char
        return words + ([word] if word else [])
    try:
        return [os.fsdecode(os.fspath(a)) if not isinstance(a, str) else a for a in args]
    except TypeError:
        return []


def _unarming_flags(words: list[str]) -> list[str]:
    """The flags among an interpreter's arguments that start it unarmed, read
    up to the script, ``-m``, ``-c`` or ``-`` the way the interpreter reads them."""
    found = []
    rest = iter(words)
    for word in rest:
        if word == "--" or not word.startswith("-") or word == "-":
            break
        if word.startswith("--"):
            if word == "--check-hash-based-pycs":
                next(rest, None)
            continue
        for at, letter in enumerate(word[1:], start=1):
            if letter in UNARMING_FLAGS:
                found.append(f"-{letter}")
            elif letter in "cm":
                return found
            elif letter in "WX":
                if at == len(word) - 1:
                    next(rest, None)
                break
    return found


def judge_child(event: str, args: tuple, session: str, folder: str = HERE) -> str | None:
    """Why the program ``event`` starts is a Python child around the
    tripwire, or None: its environment lacks the session's value or its
    path the tripwire ``folder`` first, or its flags drop either."""
    where = STARTS.get(event)
    if where is None:
        return None
    program_at, argv_at, env_at = where
    program = args[program_at] if program_at < len(args) else None
    argv = _split(args[argv_at]) if argv_at < len(args) and args[argv_at] is not None else []
    if program is None:
        if not argv:
            return None
        program = argv[0]
    if not _is_python(program):
        return None
    env = args[env_at] if env_at < len(args) else None
    if env is None:
        env = os.environ
    env = {os.fsdecode(k): os.fsdecode(v) for k, v in dict(env).items()}
    if os.name == "nt":
        env = {k.upper(): v for k, v in env.items()}
    if env.get(ENV_TRIPWIRE) != session:
        return f"{UNARMED}: its environment lacks the session's {ENV_TRIPWIRE}"
    first = (env.get("PYTHONPATH") or "").split(os.pathsep)[0]
    if not first or _resolved(first) != _resolved(folder):
        return f"{UNARMED}: its PYTHONPATH does not begin with the tripwire folder"
    flags = _unarming_flags(argv[1:])
    if flags:
        return f"{UNARMED}: started with {' '.join(flags)}"
    return None


def _record(test: str, event: str, label: str, log: str | None) -> None:
    SEEN.append((test, event, label))
    if log and not _IN_HOOK[0]:
        _IN_HOOK[0] = True
        try:
            with open(log, "a", encoding="utf-8") as out:
                out.write(json.dumps({"test": test, "event": event,
                                      "label": label, "pid": os.getpid()}) + "\n")
        except OSError:
            pass            # the raise that follows still fails the test
        finally:
            _IN_HOOK[0] = False


def install(prepared: tuple, log: str | None, *, children: str | None = None) -> None:
    """Add the hook: on a hit, record it in :data:`SEEN` (and ``log``) and
    raise :class:`TripwireError`, which stops the operation.

    ``children`` is the session's :data:`ENV_TRIPWIRE` value, given only by
    the pytest process: every Python child started without it, or without
    this folder first on its path, is recorded (never raised on)."""

    def hook(event, args):
        if children is not None and event in STARTS:
            reason = judge_child(event, args, children)
            if reason is not None:
                _record(os.environ.get("PYTEST_CURRENT_TEST", "outside any test"), event, reason, log)
            return
        if event not in WATCHED:
            return
        label = judge(event, args, prepared)
        if label is None:
            return
        test = os.environ.get("PYTEST_CURRENT_TEST", "outside any test")
        _record(test, event, label, log)
        raise TripwireError(f"decision 185: the suite may not {event} the checkout's {label} ({test})")

    sys.addaudithook(hook)


def _from_environment() -> None:
    raw = os.environ.get(ENV_TRIPWIRE)
    if not raw:
        return
    spec = json.loads(raw)
    install(prepare([(label, path) for label, path in spec["places"]]), spec.get("log"))


if __name__ == "sitecustomize":          # a child: arm from the environment
    _from_environment()
