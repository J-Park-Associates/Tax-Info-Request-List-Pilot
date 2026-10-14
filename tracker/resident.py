"""The app's engine: one process for the session that answers every click
(pilot P276, ``pilot/SPEC-ui-menu-speed.md`` section 3).

Starting Python and loading the program is most of what a small command
costs (``import tracker.api`` is 0.21 s on the Mac, about 0.85 s on the
office PC). P220's waiting spare hid that for one click at a time; the
engine pays it once, when the app opens, and then waits. ``main.js`` starts
``python -m tracker.resident --resident`` (the packaged build:
``tracker-api --resident``, dispatched by ``api_entry.py``) and hands it a
command whenever it is free; the command's reply is **byte for byte what a
process of its own would print** - this module only frames the commands in
and ends each reply with a line of its own.

**The framing** is the spare's, with the payload's length where the spare
had the end of input (an engine cannot use the end of input between
commands). A request is one UTF-8 JSON line ``{"id": n, "argv": [...],
"bytes": k}`` - at most :data:`LINE_MAX` bytes, ``n`` a positive integer,
``argv`` at least one string, ``0 <= k <= PAYLOAD_MAX`` - then exactly ``k``
bytes: the payload as ``main.js`` writes it (``JSON.stringify``, UTF-8, read
by ``api._read_spec`` as bytes, decision 176, never re-encoded inside the
line). A reply is whatever ``api.main`` prints - the firm's count lines
(P222) and the reply line - then a newline and one line
``{"engine_end": n, "code": <exit code>, "retiring": <bool>}``. The newline
leads so that output a command left without one can never hide the end line;
the shell reads the blank line as nothing.

**What never runs here.** A pass (``run-now``, decision 203) and the
after-install step (``api.OWN_PROCESS_COMMANDS``) can take minutes, hold
household locks for up to two hours and are stopped or killed on their own
terms - a Sort's Stop, its stated time limit, the shell destroying its
stdout at quit. None of that can be done to one command inside a process
that answers every click, and one process runs one command at a time, so a
pass would hold every click behind it. The shell gives them processes of
their own; the engine refuses them (:data:`OWN_PROCESS_ONLY`) and retires,
so a shell mistake is loud and never a pass run here.

**Still one command at a time, and the answers of the SPEC's section 3.1.**
Decision 171's lock rule: every lock is taken and let go inside one command,
as now. The one way a lock outlives its command - a release that could
neither delete nor mark the file - leaves a file naming this process, which
is alive, so every other process would read it as held for 2 h 05 min; so
the engine **retires after any command that left a lock held or unreleased**
(``locking.held_now``, ``locking.left_unreleased``), and the dead-owner rule
clears the file at the next take exactly as a one-command process's leftover
is cleared today. One store per command: ``api.main``'s ``finally`` closes it
after every command. P118's holds: ``api.main`` enters and leaves
``hold.one_reading()`` per command, so nothing is held between two. The
kill per command: ``main.js`` kills the engine at the same time limit and
starts a new one. Crash isolation: a command that crashes the engine is
answered by the shell (a read asked once more in a process of its own, a
write never run twice).

**Retiring.** After each command the engine compares how the process stands
with how it stood before: a lock still held or one it could not let go, a
changed environment, temp folder or working folder, a thread still running,
an error that escaped ``api.main`` (said as the failure envelope), a refused
own-process command - and after :data:`COMMANDS_MAX` commands, for the memory
a long session's large replies leave behind. It says the reason on the error
log as one line at WARNING, **by its code alone** (``"engine retired:
lock-held"``): never a value, a path or a name. The end line then says
``retiring: true`` and the engine returns; the shell starts a new one at
once, at no cost against its restart budget.

**The state between commands** (SPEC-architecture R5.1). A process of its
own began every command with each module as it was imported; the engine
keeps its modules, so what one command leaves in them must not reach the
next. The state register names every module-level name in ``tracker/`` that
a function rebinds with ``global`` (or through ``globals()``), or that is a
list, dict or set some function changes in place, in one of two tables.
:data:`PER_COMMAND` holds each such name with its fresh value, and the
engine restores every one after every command and before a refusal
(:func:`_restore_per_command`): a container is emptied in place and filled
with its fresh value, so whatever holds it still holds the same object, and
anything else is bound to its fresh value again. :data:`PER_PROCESS` holds
the rest, each with the reason or decision that keeps it for the engine's
life. ``tests/test_resident.py`` derives the names by reading the package
and fails on a name in neither table, in both, or in one no longer derived,
so a new module-level state is placed the day it is written. ``functools``
caches on pure functions are outside the register.

**The real input is the engine's alone.** It duplicates file descriptor 0
for itself and points 0 at the null device, so nothing a command starts - a
scheduler tool, a reading child - can read a frame (the duplicate is not
inherited). The temp folder is asked once at the start, so that the first
command's own first ask of it is not mistaken for a change.

**Documents.** The engine reads documents only in a reading child, as every
app command does (``content_check.READ_IN_A_CHILD``, decision 169): the
reader's process-wide switches change only in that child and end with it.
It makes no network call and imports none (``tests/test_layers.py``); it
imports ``api`` (which owns the commands), ``errlog`` (the error log every
command's lines go to), ``locking``, ``ocr`` (to forget the reader's
warnings between commands) and the standard library, and nothing imports it
but ``api_entry.py``, at call time. The register's other modules are restored
through ``sys.modules`` without importing them: a module not yet imported holds
its fresh values.
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import tempfile
import threading
from typing import BinaryIO

from tracker import api, errlog, locking, ocr

#: How the app starts the engine: this flag, alone. ``main.js`` names the
#: same word (``tests/test_single_source.py`` pins it).
RESIDENT_FLAG = "--resident"
#: The longest request line the engine reads, in bytes, newline included
#: (the spare's limit). ``main.js`` names the same number.
LINE_MAX = 64 * 1024
#: The most bytes of payload a request may name. ``main.js`` names it too.
PAYLOAD_MAX = 32 * 1024 * 1024
#: The key an end line leads with; ``main.js`` finds the line by it.
END_KEY = "engine_end"
#: How many commands one engine answers before it retires.
COMMANDS_MAX = 500
#: What a refused own-process command says (the failure envelope, ``refused``).
OWN_PROCESS_ONLY = "This runs in a process of its own; nothing was started."

#: Why an engine retired, each a code and nothing else: this is all the
#: error log says about it (no value, no path).
RETIRED_REFUSED = "own-process-command"
RETIRED_ESCAPED = "escaped-error"
RETIRED_LOCK_HELD = "lock-held"
RETIRED_LOCK_LEFT = "lock-left"
RETIRED_ENVIRONMENT = "environment-changed"
RETIRED_TEMP_FOLDER = "temp-folder-changed"
RETIRED_WORKING_FOLDER = "working-folder-changed"
RETIRED_THREAD = "thread-left-running"
RETIRED_BUDGET = "command-budget"

log = logging.getLogger("tracker.resident")

#: The state register's names restored after every command: ``(module,
#: name)`` -> the value the module binds it to when imported.
PER_COMMAND: dict[tuple[str, str], object] = {
    # What the last command left for its envelope: its warnings, the row it
    # was asked about, and its own name (api.main sets all three per command).
    ("api", "_ASKED"): {},
    ("api", "_RUNNING"): {"command": ""},
    ("api", "_WARNINGS"): [],
    # The files whose reader could not start, which only a pass says and
    # empties: no pass runs here, so they piled up until the engine retired
    # (finding A-7).
    ("content_check", "_COULD_NOT_START"): [],
    # The last line a reading looked at, one document's.
    ("content_check", "_last_line"): None,
    # The full-sync warning is said once per command, as before P276 (C-3).
    ("fsio", "_full_sync_said"): False,
    ("locking", "_full_sync_said"): False,
    # The reader's memory-limit warnings, said once per command (P276);
    # ocr.forget_said empties it before each command too.
    ("ocr", "_SAID"): set(),
}

#: The state register's names kept for the engine's life: ``(module, name)``
#: -> the reason or decision that keeps it.
PER_PROCESS: dict[tuple[str, str], str] = {
    ("content_check", "_STOP"): "one document's safety stop, set and cleared around it by "
                                "extract_by_ocr (decision 137)",
    ("errors", "_dropped"): "a reading child's count, started by keep_for_the_parent and cleared by "
                            "take_kept (decision 190)",
    ("errors", "_for_the_parent"): "a reading child's keeps, started by keep_for_the_parent and emptied "
                                   "by take_kept (decision 190)",
    ("hold", "_HELD"): "reset by `hold.one_reading`",
    ("hold", "_HOLDING"): "reset by `hold.one_reading`",
    ("locking", "_held"): "every lock is taken and let go inside one command, and the engine retires "
                          "after one that left a lock held (decision 171, locking.held_now)",
    ("locking", "_mac_host"): "a fact about the machine: its local host name (SPEC-mac R21)",
    ("locking", "_unreleased"): "the engine retires after a command that could not let a lock go "
                                "(decision 171, locking.left_unreleased)",
    ("ocr", "SETTINGS"): "the reader's settings, changed by use_settings for the reader bench and the "
                         "suite only",
    ("ocr", "_DEVICE"): "the reader's device, settled once a process (decision 169)",
    ("ocr", "_ENGINE"): "the reader's engine, built once a process (decision 169)",
    ("ocr", "_NOTES"): "a pass's notes, taken by take_notes and cleared by reset; no pass runs in the "
                       "engine (decision 169)",
    ("ocr", "_PROCESSOR_ONLY"): "set after a fault on the card, for the rest of the process "
                                "(decision 169)",
    ("ocr", "_SESSION"): "the reading session, for the life of reading_session's with block "
                         "(decision 169)",
    ("settings", "_redirect_answer"): "a fact about the machine, asked once",
    ("store", "_CHECKPOINT"): "the store's connection, closed by store.close in api.main's finally "
                              "after every command (decision 101, P214)",
    ("store", "_CHECKPOINT_FILE"): "the store's connection, closed by store.close in api.main's "
                                   "finally after every command (decision 101, P214)",
    ("store", "_CHECKPOINT_PATH"): "the store's connection, closed by store.close in api.main's "
                                   "finally after every command (decision 101, P214)",
    ("store", "_CONNECTION"): "the store's connection, closed by store.close in api.main's finally "
                              "after every command (decision 101, P214)",
    ("store", "_CONNECTION_PATH"): "the store's connection, closed by store.close in api.main's "
                                   "finally after every command (decision 101, P214)",
    ("store", "_REPLACED"): "part of every held read's token for the process's life, so a row built "
                            "again is never answered from a read of the one it replaced (P215)",
    ("validators", "PdfReader"): "pypdf's reader, imported once, at the first PDF (P219)",
}


def _request_of(line: bytes) -> dict | None:
    """The request ``line`` says, or ``None`` when it is not of the agreed
    shape: one JSON object with exactly ``id``, ``argv`` and ``bytes``, each
    as the module's docstring has them."""
    try:
        asked = json.loads(line.decode("utf-8"))
    except ValueError:
        return None
    if not isinstance(asked, dict) or set(asked) != {"id", "argv", "bytes"}:
        return None
    number, argv, size = asked["id"], asked["argv"], asked["bytes"]
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        return None
    if not (isinstance(argv, list) and argv and all(isinstance(one, str) for one in argv)):
        return None
    if isinstance(size, bool) or not isinstance(size, int) or not 0 <= size <= PAYLOAD_MAX:
        return None
    return asked


def _own_the_input() -> BinaryIO:
    """The real standard input, for the engine alone: descriptor 0 is
    duplicated (the copy is not inherited by anything a command starts) and
    then pointed at the null device, so a child that reads its input meets
    the end of it at once and can never take a frame."""
    mine = os.dup(0)
    null = os.open(os.devnull, os.O_RDONLY)
    try:
        os.dup2(null, 0)
    finally:
        os.close(null)
    return open(mine, "rb")


def _stand() -> dict:
    """How the process stands, for comparing after a command with before."""
    return {"held": locking.held_now(), "environ": dict(os.environ),
            "tempdir": tempfile.tempdir, "cwd": os.getcwd(),
            "threads": threading.active_count()}


def _left_unlike(before: dict) -> str | None:
    """The code of the first way the process stands unlike ``before``, or
    ``None`` when it is as it was found."""
    if locking.left_unreleased():
        return RETIRED_LOCK_LEFT
    if locking.held_now() > before["held"]:
        return RETIRED_LOCK_HELD
    if dict(os.environ) != before["environ"]:
        return RETIRED_ENVIRONMENT
    if tempfile.tempdir != before["tempdir"]:
        return RETIRED_TEMP_FOLDER
    if os.getcwd() != before["cwd"]:
        return RETIRED_WORKING_FOLDER
    if threading.active_count() > before["threads"]:
        return RETIRED_THREAD
    return None


def _say_retired(reason: str) -> None:
    """One line on the error log, inside ``errlog.error_log()`` as every
    command's lines are: the reason's code alone."""
    with errlog.error_log("tracker"):
        log.warning("engine retired: %s", reason)


# The helpers below are named apart from any other module's (not ``_run`` or
# ``_end``): ``tests/test_api.py`` derives the writing commands from the
# package's calls by name, so a shared name would join them to a writer.
def _write_end_line(number: int, code: int, retiring: bool) -> None:
    """The end line, on a line of its own after the reply."""
    sys.stdout.write("\n" + json.dumps({END_KEY: number, "code": code, "retiring": retiring}) + "\n")
    sys.stdout.flush()


def _restore_per_command() -> None:
    """Every :data:`PER_COMMAND` name as its module was imported: a
    container emptied in place and filled from its fresh value (whatever
    holds it still holds the same object), anything else bound again. A
    fresh value holds no container of its own (``tests/test_resident.py``),
    so filling from it shares nothing a command could change. A module not
    yet imported is passed over: it holds its fresh values already."""
    for (name_of_module, name), fresh in PER_COMMAND.items():
        module = sys.modules.get(f"tracker.{name_of_module}")
        if module is None:
            continue
        held = getattr(module, name)
        if isinstance(held, (list, dict, set)):
            held.clear()
            if isinstance(held, list):
                held.extend(fresh)
            else:
                held.update(fresh)
        else:
            setattr(module, name, fresh)


def _run_one_command(argv: list[str], payload: bytes) -> tuple[int, bool]:
    """One command through ``api.main`` with ``payload`` as its standard
    input: its exit code, and whether an error escaped it (said then as the
    failure envelope, exit code 1).

    The reader's memory-limit warnings are said "once by this process"
    (``ocr.forget_said``); a process of its own said them once per command, so the
    engine forgets them before each command and its error log reads the same.
    After the command, its reply said, every :data:`PER_COMMAND` name is
    restored (:func:`_restore_per_command`), so the next command finds the
    modules as a process of its own would."""
    ocr.forget_said()
    stdin = sys.stdin
    sys.stdin = io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8")
    try:
        return api.main(argv), False
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # SystemExit, or an error outside main's own try
        # Inside the error log, as main's own are: its `with` has already
        # closed, and said outside it the trace the reply promises is dropped.
        with errlog.error_log("tracker"):
            return api.say_failure(argv[0], exc), True
    finally:
        sys.stdin = stdin
        _restore_per_command()


def serve(stream: BinaryIO | None = None) -> int:
    """Serve commands until the app closes or the engine retires.

    ``stream`` is the binary input to read frames from; ``None`` is the
    process's real standard input, taken for the engine alone
    (:func:`_own_the_input`). Returns 0 at the end of input, or when it
    retires; 2 after a request line that is not of the agreed shape, since
    the stream can no longer be trusted (the usage envelope and an end line
    with ``id`` 0 and ``retiring: true`` are printed first).

    The steps are the SPEC's 3.3 in order: read a line (the end of input
    before its newline returns 0 and prints nothing), read exactly the bytes
    it names (the end of input first returns 0), refuse an own-process
    command, note how the process stands, run the command with the payload
    as its input, flush, decide whether to retire, write the end line.
    """
    tempfile.gettempdir()        # asked once, so a first ask is not a change
    stream = stream if stream is not None else _own_the_input()
    answered = 0
    while True:
        line = stream.readline(LINE_MAX + 1)
        if not line or (not line.endswith(b"\n") and len(line) <= LINE_MAX):
            return 0
        asked = _request_of(line) if len(line) <= LINE_MAX else None
        if asked is None:
            try:
                _write_end_line(0, api.main([]), True)
            except OSError:
                return 0
            return 2
        payload = stream.read(asked["bytes"]) if asked["bytes"] else b""
        if len(payload) < asked["bytes"]:
            return 0
        argv = asked["argv"]
        if argv[0] in api.OWN_PROCESS_COMMANDS:
            _restore_per_command()   # a refusal carries nothing the last command left
            code = api.say_failure(argv[0], api.ManifestError(OWN_PROCESS_ONLY))
            retire = RETIRED_REFUSED
        else:
            before = _stand()
            try:
                code, escaped = _run_one_command(argv, payload)
            except KeyboardInterrupt:
                return 130
            except OSError:
                return 0     # the app is gone while a failure was being said
            answered += 1
            retire = RETIRED_ESCAPED if escaped else _left_unlike(before)
            if retire is None and answered >= COMMANDS_MAX:
                retire = RETIRED_BUDGET
        try:
            sys.stdout.flush()
            sys.stderr.flush()
            if retire is not None:
                _say_retired(retire)
            _write_end_line(asked["id"], code, retire is not None)
        except OSError:
            return 0         # the app is gone and nobody is left to answer
        if retire is not None:
            return 0


if __name__ == "__main__":
    if sys.argv[1:] != [RESIDENT_FLAG]:
        sys.stderr.write(f"usage: python -m tracker.resident {RESIDENT_FLAG}\n")
        raise SystemExit(2)
    raise SystemExit(serve())
