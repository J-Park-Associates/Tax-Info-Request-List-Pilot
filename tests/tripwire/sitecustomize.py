"""The suite's tripwire (decision 185): no test, and no Python child a test
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
copy and SQLite connection that Python code makes to a guarded place. That holds
in the pytest process and in every Python child that inherits the suite's
environment: `subprocess` children and the reading child. It then fails the
session. It **does not see**:
- children that are not Python (`node`, `git`, `cmd`, `icacls` in
  `tests/test_single_source.py`, `tests/test_api.py:4232`, `tests/samples.py`,
  `tests/test_ocr.py`), which are never pointed at a guarded place today;
- a Python child started with `-I`, `-E` or `-S`, or with an environment that
  drops `PYTHONPATH`/`TRACKER_TEST_TRIPWIRE`. Proof test 10 fails the suite on
  the second shape in `tests/`; the first appears nowhere in `tests/` today;
- a native library that opens a file itself (pdfium, ONNX Runtime), unless
  Python opened it first. Such a library is only handed a path a test chose;
- `os.stat`/`exists` (no audit event): existence is learned, never content. §3.2
  moves the one existence check that mattered to an open;
- an alias that does not contain the place's name (a Windows 8.3 short name
  such as `SETTIN~1.JSO`);
- code that deliberately goes around it (`ctypes`). It is a guard rail in the
  suite, not a wall. The wall is 186's placement plus the account boundary
  (Jason's decision (a)).
In a child it shadows another `sitecustomize` on the path while the suite runs.
CI's `setup-python` installs none.

One more it cannot place: a relative name opened against a directory
descriptor (``os.open(name, dir_fd=...)``, how ``shutil.rmtree`` walks a tree),
because ``os.open``'s audit event does not carry the descriptor. Such a name is
not judged; the walk's own top folder, named in full, is.
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
    "sqlite3.connect": (0,),
}
#: Where an event carries the directory descriptor a relative path is
#: resolved against. A relative path with one is not the working folder's.
DIR_FDS = {"os.mkdir": (2,), "os.rmdir": (1,), "os.remove": (1,), "os.rename": (2, 3)}
SEEN: list[tuple[str, str, str]] = []      # (test, event, label), this process

_IN_HOOK = [False]                         # the re-entry guard for the log


class TripwireError(RuntimeError):
    """Not an OSError on purpose: most code that expects a missing file catches
    OSError, and this must not read as one."""


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def prepare(places) -> tuple:
    """``[(label, path)]`` -> ``((label, spelled, real, name), ...)``: each
    place as it is spelled, as the filesystem resolves it, and by its name."""
    out = []
    for label, path in places:
        path = os.fspath(path)
        out.append((label, _norm(path),
                    os.path.normcase(os.path.realpath(path)),
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
        spelled = _norm(text)
        for label, place, _real, name in prepared:
            if _hits(spelled, place, name):
                return label
        if any(name and name in spelled for _l, _p, _r, name in prepared):
            real = os.path.normcase(os.path.realpath(text))
            for label, _place, place_real, name in prepared:
                if _hits(real, place_real, name):
                    return label
    return None


def install(prepared: tuple, log: str | None) -> None:
    """Add the hook: on a hit, record it in :data:`SEEN` (and ``log``) and
    raise :class:`TripwireError`, which stops the operation."""

    def hook(event, args):
        if event not in WATCHED:
            return
        label = judge(event, args, prepared)
        if label is None:
            return
        test = os.environ.get("PYTEST_CURRENT_TEST", "outside any test")
        SEEN.append((test, event, label))
        if log and not _IN_HOOK[0]:
            _IN_HOOK[0] = True
            try:
                with open(log, "a", encoding="utf-8") as out:
                    out.write(json.dumps({"test": test, "event": event,
                                          "label": label, "pid": os.getpid()}) + "\n")
            except OSError:
                pass            # the raise below still fails the test
            finally:
                _IN_HOOK[0] = False
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
