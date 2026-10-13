"""Tests for tracker/resident.py - the app's engine (pilot P276,
pilot/SPEC-ui-menu-speed.md section 3).

The contract under test: the engine answers each command handed to it exactly
as a process of its own would, frames its reply with an end line, never runs a
pass or the after-install step, and ends itself after any command that left the
process unlike it found it. The engine is driven in this process through
``serve`` and a byte stream, as ``tests/test_api.py`` drives ``api.main``; the
two claims about real descriptors (the input only the engine can read, the
process end to end) start a real process.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import threading

import pytest

import tracker.api as api
from tests.conftest import REPO, child_env, make_engagement
from tracker import locking, resident, settings, store
from tracker.manifest import RequestItem

#: The line an end line starts with: ``main.js`` finds it by this prefix.
END_PREFIX = '{"' + resident.END_KEY + '"'


@pytest.fixture
def engine_root(short_root, tmp_path, monkeypatch):
    """A clients root recorded the way the app records it, with one return."""
    monkeypatch.setenv(settings.ENV_SETTINGS_DIR, str(tmp_path / "app"))
    settings.set_clients_root(short_root)
    settings.set_firm("J Park & Associates, CPA")
    return make_engagement(short_root, [RequestItem(identifier="A01", document="W-2")],
                           household="Smith Family")


def frame(number: int, argv: list[str], payload: bytes = b"") -> bytes:
    """One request as ``main.js`` writes it: the line, then the payload's bytes."""
    head = json.dumps({"id": number, "argv": argv, "bytes": len(payload)})
    return head.encode("utf-8") + b"\n" + payload


def serve(capsys, *frames: bytes) -> tuple[int, str]:
    """``serve`` over these frames: its return value and everything it printed."""
    code = resident.serve(io.BytesIO(b"".join(frames)))
    return code, capsys.readouterr().out


def replies(out: str) -> list[tuple[str, dict]]:
    """``out`` as (what the command printed, its end line) pairs: the end line is
    a line of its own, after the newline the engine leads it with."""
    pairs, buffer = [], []
    for line in out.split("\n")[:-1]:
        if line.startswith(END_PREFIX):
            pairs.append(("\n".join(buffer[:-1]) + ("\n" if len(buffer) > 1 else ""), json.loads(line)))
            buffer = []
        else:
            buffer.append(line)
    assert buffer == [], buffer
    return pairs


def fresh(capsys, argv: list[str]) -> tuple[int, str]:
    """The same command as a process of its own prints it."""
    code = api.main(argv)
    return code, capsys.readouterr().out


def error_log_text() -> str:
    path = settings.error_log_path()
    return path.read_text(encoding="utf-8") if path.is_file() else ""


# ----------------------------------------------------- P276 (SPEC-ui-menu-speed §3) ----


def test_the_engine_answers_each_command_as_a_fresh_process_would_byte_for_byte(capsys, engine_root):
    """The engine only frames: for the commands the window asks most, what it
    printed before the end line is what ``api.main`` prints, and the end line
    carries the same exit code."""
    asked = [["templates"], ["list"], ["firm"], ["last-pass"],
             ["state", api.ENGAGEMENT_FLAG, str(engine_root)],
             ["watch", api.ENGAGEMENT_FLAG, str(engine_root)]]
    for number, argv in enumerate(asked, start=1):
        code, wanted = fresh(capsys, argv)
        assert code == 0, (argv, wanted)
        engine_code, out = serve(capsys, frame(number, argv))
        assert engine_code == 0
        [(printed, end)] = replies(out)
        assert printed == wanted, argv
        assert end == {resident.END_KEY: number, "code": 0, "retiring": False}, argv
        assert out == wanted + "\n" + json.dumps(end) + "\n", argv


def test_a_write_with_a_payload_is_answered_as_a_fresh_process_would_byte_for_byte(capsys, engine_root, monkeypatch):
    """The claim P220's spare test made, kept for the engine: an ``edit`` that
    carries a payload, through ``serve``, prints what ``api.main`` prints for
    the same bytes on its standard input, and leaves the engine serving."""
    from tests.conftest import app_stdin

    rules = json.loads(fresh(capsys, ["state", api.ENGAGEMENT_FLAG, str(engine_root)])[1])["rules"]
    store.close()
    edit = ["edit", api.ENGAGEMENT_FLAG, str(engine_root)]
    from tracker.manifest import list_head

    def body_now() -> bytes:
        return json.dumps({"items": rules, "engagement": {}, "head": list_head(engine_root)}).encode("utf-8")

    with monkeypatch.context() as patch:
        # The first edit records the firm on the return; the ones after change nothing.
        patch.setattr("sys.stdin", app_stdin(json.loads(body_now())))
        assert fresh(capsys, edit)[0] == 0
    store.close()
    body = body_now()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdin", app_stdin(json.loads(body)))
        wanted_code, wanted = fresh(capsys, edit)
    assert wanted_code == 0, wanted
    store.close()
    code, out = serve(capsys, frame(1, edit, body), frame(2, ["templates"]))
    [(printed, first), (_listed, second)] = replies(out)
    assert code == 0 and printed == wanted and first == {resident.END_KEY: 1, "code": 0, "retiring": False}
    assert json.loads(printed)["saved"]["recorded"] is False and second[resident.END_KEY] == 2


def test_one_command_that_fails_is_answered_and_the_next_is_served(capsys, engine_root):
    """A refusal is an answer, not an end: the engine says it, keeps its place
    and serves the next frame."""
    code, out = serve(capsys, frame(1, ["state"]), frame(2, ["templates"]))
    assert code == 0
    [(refused, first), (listed, second)] = replies(out)
    assert json.loads(refused)["failure"]["kind"] == "refused"
    assert first == {resident.END_KEY: 1, "code": 1, "retiring": False}
    assert "forms" in json.loads(listed) and second == {resident.END_KEY: 2, "code": 0, "retiring": False}


MARKER = "a made-up marker 7f3a"


@pytest.mark.parametrize("escape", [SystemExit(MARKER), MemoryError(MARKER)])
def test_an_error_that_escapes_main_is_said_as_the_envelope_and_the_engine_retires(capsys, monkeypatch, escape):
    """``SystemExit`` and a ``MemoryError`` that got past ``api.main`` are said
    through ``api.say_failure`` (exit code 1) and the engine retires; the frame
    after it is left unread."""
    def main(argv):
        raise escape

    monkeypatch.setattr(api, "main", main)
    code, out = serve(capsys, frame(7, ["templates"]), frame(8, ["templates"]))
    assert code == 0
    [(printed, end)] = replies(out)
    said = json.loads(printed)
    assert said["failure"]["kind"] == "failed"
    assert said["error"] == api.FAILED.format(kind=type(escape).__name__, log=api.ERROR_LOG_FILENAME)
    assert MARKER not in printed, "the reply says the class, never the words"
    assert MARKER in error_log_text() and type(escape).__name__ in error_log_text(), \
        "the words and the trace the reply promises are in the error log, not on stderr alone"
    assert "Traceback" in error_log_text()
    assert end == {resident.END_KEY: 7, "code": 1, "retiring": True}


def test_the_payload_is_read_as_utf8_bytes_of_the_length_its_line_names(capsys, monkeypatch):
    """Decision 176 through the engine: ``Muñoz`` is three more bytes than
    characters in a longer payload, and the next frame still starts where the
    last one's bytes end. ``sys.stdin`` is the command's for its run only."""
    seen = []

    def echo(argv):
        spec = api._read_spec()
        seen.append(spec)
        return {"name": spec["name"]}

    monkeypatch.setitem(api.COMMANDS, "templates", echo)
    before = sys.stdin
    payload = json.dumps({"name": "Muñoz Núñez"}, ensure_ascii=False).encode("utf-8")
    assert len(payload) > len(payload.decode("utf-8"))
    code, out = serve(capsys, frame(1, ["templates"], payload), frame(2, ["templates"]), frame(3, ["templates"], payload))
    assert code == 0 and sys.stdin is before
    [(first, _), (second, _), (third, _)] = replies(out)
    assert json.loads(first)["name"] == "Muñoz Núñez" == json.loads(third)["name"]
    assert "error" in json.loads(second)        # no payload: the spec is {}, which has no name
    assert seen[0] == seen[2] == {"name": "Muñoz Núñez"}


def _usage(capsys) -> str:
    return fresh(capsys, [])[1]


@pytest.mark.parametrize("line", [
    b"not json\n", b'["templates"]\n', b'{"id": 1, "argv": ["templates"]}\n',
    b'{"id": 1, "argv": ["templates"], "bytes": 0, "extra": 1}\n',
    b'{"id": 0, "argv": ["templates"], "bytes": 0}\n', b'{"id": true, "argv": ["templates"], "bytes": 0}\n',
    b'{"id": 1, "argv": [], "bytes": 0}\n', b'{"id": 1, "argv": ["templates", 3], "bytes": 0}\n',
    b'{"id": 1, "argv": ["templates"], "bytes": -1}\n',
    b'{"id": 1, "argv": ["templates"], "bytes": ' + str(resident.PAYLOAD_MAX + 1).encode() + b'}\n',
    b"\xff\xfe\n",
    json.dumps({"id": 1, "argv": ["templates", "x" * (resident.LINE_MAX + 10)], "bytes": 0}).encode() + b"\n",
    b"x" * (resident.LINE_MAX + 1),
])
def test_a_malformed_or_oversized_line_says_the_usage_and_retires(capsys, line):
    """A line not of the agreed shape - or too long, or naming too many bytes -
    is answered as every unknown command is (``main([])``, no words of its own)
    with an end line of ``id`` 0, and the engine returns 2: the stream can no
    longer be trusted."""
    wanted = _usage(capsys)
    code, out = serve(capsys, line, frame(2, ["templates"]))
    assert code == 2
    [(printed, end)] = replies(out)
    assert printed == wanted and json.loads(wanted)["error"].startswith("usage")
    assert end == {resident.END_KEY: 0, "code": 1, "retiring": True}


@pytest.mark.parametrize("stream", [b"", b'{"id": 1, "argv": ["temp', frame(1, ["templates"], b"{}")[:-1]])
def test_the_end_of_input_ends_the_engine_quietly(capsys, stream, monkeypatch):
    """The app closed: before a line, inside one, or inside a payload, the
    engine runs nothing, prints nothing and returns 0."""
    monkeypatch.setattr(api, "main", lambda argv: pytest.fail("a command was run"))
    code, out = serve(capsys, stream)
    assert (code, out) == (0, "")


def test_a_command_that_leaves_a_lock_held_or_unreleased_retires_the_engine(capsys, monkeypatch, tmp_path):
    """Decision 171: a lock that outlives its command names this live process, so
    every other process would read it as held. Held after the command, or one a
    release could neither delete nor mark: the engine retires."""
    held = []

    def take(argv):
        held.append(locking.acquire_lock(tmp_path))
        return {}

    monkeypatch.setitem(api.COMMANDS, "templates", take)
    try:
        code, out = serve(capsys, frame(1, ["templates"]), frame(2, ["templates"]))
        [(_, end)] = replies(out)
        assert code == 0 and end["retiring"] is True and end[resident.END_KEY] == 1
        assert "engine retired: lock-held" in error_log_text()
    finally:
        for lock in held:
            locking.release_lock(lock)

    monkeypatch.setattr(locking, "_unreleased", [])
    monkeypatch.setitem(api.COMMANDS, "templates", lambda argv: locking._unreleased.append(tmp_path / "x") or {})
    code, out = serve(capsys, frame(1, ["templates"]), frame(2, ["templates"]))
    [(_, end)] = replies(out)
    assert end["retiring"] is True and "engine retired: lock-left" in error_log_text()


@pytest.mark.parametrize("change, reason", [
    ("environment", resident.RETIRED_ENVIRONMENT),
    ("temp", resident.RETIRED_TEMP_FOLDER),
    ("cwd", resident.RETIRED_WORKING_FOLDER),
])
def test_a_command_that_changes_the_environment_the_temp_folder_or_the_working_folder_retires_the_engine(
        capsys, monkeypatch, tmp_path, change, reason):
    monkeypatch.setenv("P276_PROBE", "before")
    monkeypatch.setattr(tempfile, "tempdir", tempfile.gettempdir())
    monkeypatch.chdir(tmp_path)
    (tmp_path / "elsewhere").mkdir()

    def change_it(argv):
        if change == "environment":
            os.environ["P276_PROBE"] = "after"
        elif change == "temp":
            tempfile.tempdir = str(tmp_path / "elsewhere")
        else:
            os.chdir(tmp_path / "elsewhere")
        return {}

    monkeypatch.setitem(api.COMMANDS, "templates", change_it)
    code, out = serve(capsys, frame(1, ["templates"]), frame(2, ["templates"]))
    [(_, end)] = replies(out)
    assert code == 0 and end == {resident.END_KEY: 1, "code": 0, "retiring": True}
    assert f"engine retired: {reason}" in error_log_text()


def test_the_first_ask_of_the_temp_folder_is_not_a_change(capsys, monkeypatch):
    """``tempfile.tempdir`` is empty until something asks for it; the engine asks
    once at its start, so the first command that does is not a reason to retire."""
    monkeypatch.setattr(tempfile, "tempdir", None)
    monkeypatch.setitem(api.COMMANDS, "templates", lambda argv: {"dir": tempfile.mkdtemp() and "ok"})
    _code, out = serve(capsys, frame(1, ["templates"]), frame(2, ["templates"]))
    assert [end["retiring"] for _printed, end in replies(out)] == [False, False]


def test_a_thread_left_running_retires_the_engine(capsys, monkeypatch):
    stop = threading.Event()
    threads = []

    def start(argv):
        threads.append(threading.Thread(target=stop.wait, daemon=True))
        threads[-1].start()
        return {}

    monkeypatch.setitem(api.COMMANDS, "templates", start)
    try:
        _code, out = serve(capsys, frame(1, ["templates"]), frame(2, ["templates"]))
        [(_, end)] = replies(out)
        assert end["retiring"] is True and "engine retired: thread-left-running" in error_log_text()
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=10)


def test_the_engine_retires_after_its_command_budget(capsys, monkeypatch):
    assert resident.COMMANDS_MAX == 500
    monkeypatch.setattr(resident, "COMMANDS_MAX", 3)
    code, out = serve(capsys, *(frame(n, ["templates"]) for n in range(1, 6)))
    assert code == 0
    ends = [end for _printed, end in replies(out)]
    assert [end["retiring"] for end in ends] == [False, False, True]
    assert "engine retired: command-budget" in error_log_text()


def test_a_pass_or_the_after_install_step_is_refused_and_never_started_here(capsys, monkeypatch):
    """The pass and the after-install step have processes of their own; a shell
    mistake is a refusal in the failure envelope and the engine retires - and
    nothing they would run is called."""
    from tracker import after_install, runner

    def never(*args, **kwargs):
        raise AssertionError("started in the engine")

    monkeypatch.setattr(runner, "main", never)
    monkeypatch.setattr(after_install, "run", never)
    monkeypatch.setattr(after_install, "launch", never)
    for command in sorted(api.OWN_PROCESS_COMMANDS):
        code, out = serve(capsys, frame(4, [command, "--engagement", "/x"]), frame(5, ["templates"]))
        assert code == 0, command
        [(printed, end)] = replies(out)
        said = json.loads(printed)
        assert said["error"] == resident.OWN_PROCESS_ONLY and said["failure"]["kind"] == "refused", command
        assert end == {resident.END_KEY: 4, "code": 1, "retiring": True}, command
        assert said["warnings"] == [], command


def test_a_refusal_carries_nothing_the_last_command_left(capsys, monkeypatch):
    """A refusal made before any command runs must not carry the last command's
    warnings or the row it was asked about."""
    def warns(argv):
        api._warn("a sentence of the last command")
        api._ASKED.update({"identifier": "A01"})
        return {}

    monkeypatch.setitem(api.COMMANDS, "templates", warns)
    _code, out = serve(capsys, frame(1, ["templates"]))
    assert json.loads(replies(out)[0][0])["warnings"] == ["a sentence of the last command"]
    api._warn("left behind")
    api._ASKED.update({"identifier": "A02"})
    _code, out = serve(capsys, frame(1, [api.PASS_COMMAND]))
    said = json.loads(replies(out)[0][0])
    assert said["warnings"] == [] and said["failure"]["identifier"] is None


def test_nothing_a_command_starts_can_read_the_engines_frames():
    """The engine takes its input for itself: descriptor 0 is duplicated and then
    pointed at the null device, so a child that reads its input gets the end of
    it at once, while the engine still reads its frame."""
    script = (
        "import subprocess, sys\n"
        "from tracker import resident\n"
        "stream = resident._own_the_input()\n"
        "child = subprocess.run([sys.executable, '-c', 'import sys; print(repr(sys.stdin.read()))'],\n"
        "                       capture_output=True, text=True, timeout=60)\n"
        "print(child.stdout.strip())\n"
        "print(stream.readline())\n"
    )
    done = subprocess.run([sys.executable, "-c", script], cwd=REPO, env=child_env(),
                          input=b"a frame the child must not take\n", capture_output=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert done.stdout.decode().splitlines() == ["''", "b'a frame the child must not take\\n'"]


def test_every_command_has_its_own_reading_hold_and_store(capsys, engine_root, monkeypatch):
    """Decision 171, P118: ``api.main`` enters a reading hold and closes the store
    per command; between two commands the engine holds neither."""
    held_during = []
    real_templates = api.COMMANDS["templates"]

    def probe(argv):
        held_during.append((settings._HELD, store._CONNECTION))
        return real_templates(argv)

    _code, out = serve(capsys, frame(1, ["state", api.ENGAGEMENT_FLAG, str(engine_root)]))
    assert replies(out)[0][1]["code"] == 0
    assert settings._HELD is None and store._CONNECTION is None
    monkeypatch.setitem(api.COMMANDS, "templates", probe)
    serve(capsys, frame(2, ["templates"]))
    assert held_during == [(None, None)]


def test_the_end_line_follows_the_reply_on_a_line_of_its_own_even_after_unended_output(capsys, monkeypatch):
    def main(argv):
        sys.stdout.write("partial output with no newline")
        return 0

    monkeypatch.setattr(api, "main", main)
    _code, out = serve(capsys, frame(9, ["templates"]))
    assert out == ("partial output with no newline\n"
                   + json.dumps({resident.END_KEY: 9, "code": 0, "retiring": False}) + "\n")
    assert out.splitlines()[-1].startswith(END_PREFIX) and list(json.loads(out.splitlines()[-1]))[0] == resident.END_KEY


def test_the_engine_reads_documents_only_in_a_child(tmp_path):
    """Decision 169: the reading is in a child by default (the suite turns it off
    for itself). A command that really reads a document - a text PDF through
    ``content_check.judge_bounded``, the one door every reading of a pass or a
    command goes through, which reads in this process when the switch is off -
    is read by exactly one reading child, which answers it; the engine's own
    ``ocr`` is left with no reader of its own and no session open, and a real
    reading child does not retire the engine."""
    script = (
        "import io, json, sys\n"
        "from pathlib import Path\n"
        "from tests.samples import text_pdf\n"
        "from tracker import api, content_check, ocr, resident\n"
        "assert content_check.READ_IN_A_CHILD is True\n"
        "pdf = text_pdf(Path(sys.argv[1]) / 'doc.pdf', ['Form W-2 Wage and Tax Statement 2025'], style='padded')\n"
        "made, kinds = [], []\n"
        "making = ocr.ReadingChild.__init__\n"
        "def counted(self, *args, **kwargs):\n"
        "    made.append(1)\n"
        "    making(self, *args, **kwargs)\n"
        "ocr.ReadingChild.__init__ = counted\n"
        "running = ocr.run_in_child\n"
        "def heard(*args, **kwargs):\n"
        "    outcome = running(*args, **kwargs)\n"
        "    kinds.append(outcome.kind)\n"
        "    return outcome\n"
        "ocr.run_in_child = heard\n"
        "def reading(argv):\n"
        "    judgment = content_check.judge_bounded(pdf, content_check.Questions())\n"
        "    return {'kinds': kinds, 'has_words': judgment.has_words}\n"
        "api.COMMANDS['templates'] = reading\n"
        "frame = json.dumps({'id': 1, 'argv': ['templates'], 'bytes': 0}).encode() + b'\\n'\n"
        "resident.serve(io.BytesIO(frame))\n"
        "print(ocr._ENGINE is None, ocr._PROCESSOR_ONLY, ocr._SESSION is None, len(made))\n"
    )
    done = subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=REPO, env=child_env(),
                          capture_output=True, text=True, timeout=180)
    assert done.returncode == 0, done.stderr
    lines = done.stdout.strip().splitlines()
    reply = json.loads(lines[0])
    assert reply["kinds"] == ["read"] and reply["has_words"] is True, "one child read the document: " + lines[0]
    assert lines[-1] == "True False True 1", "exactly one reading child, and nothing of the reader left here"
    [end] = [json.loads(line) for line in lines if line.startswith(END_PREFIX)]
    assert end == {resident.END_KEY: 1, "code": 0, "retiring": False}, "a real reading child must not retire the engine"


def test_the_retirement_is_said_in_the_error_log_by_its_code_alone(capsys, monkeypatch):
    """One line at WARNING, the code and nothing else: no value of the changed
    environment, no path."""
    monkeypatch.setenv("P276_PROBE", "before")

    def change(argv):
        os.environ["P276_PROBE"] = "a-value-that-must-not-be-logged"
        return {}

    monkeypatch.setitem(api.COMMANDS, "templates", change)
    serve(capsys, frame(1, ["templates"]))
    text = error_log_text()
    lines = [line for line in text.splitlines() if "engine retired" in line]
    assert len(lines) == 1 and lines[0].endswith("tracker.resident WARNING engine retired: environment-changed")
    assert "a-value-that-must-not-be-logged" not in text


def test_the_end_line_leads_with_its_key_and_the_module_names_its_flag():
    """``main.js`` finds the end line by its first key and starts the engine by
    the flag; ``tests/test_single_source.py`` pins the shell's copy of both."""
    assert resident.RESIDENT_FLAG == "--resident" and resident.END_KEY == "engine_end"
    done = subprocess.run([sys.executable, "-m", "tracker.resident", "--other"], cwd=REPO, env=child_env(),
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 2 and "--resident" in done.stderr and done.stdout == ""


def test_a_real_engine_process_answers_as_a_process_of_its_own_does():
    """End to end through real descriptors: the engine started as the shell
    starts it, two frames in, closed - the replies are a fresh process's, and
    the end of input ends it with exit code 0."""
    fresh_run = subprocess.run([sys.executable, "-m", "tracker.api", "templates"], cwd=REPO, env=child_env(),
                               capture_output=True, timeout=180)
    engine = subprocess.run([sys.executable, "-m", "tracker.resident", resident.RESIDENT_FLAG], cwd=REPO,
                            env=child_env(), input=frame(1, ["templates"]) + frame(2, ["templates"]),
                            capture_output=True, timeout=180)
    assert fresh_run.returncode == engine.returncode == 0, engine.stderr
    def end(n):
        return ("\n" + json.dumps({resident.END_KEY: n, "code": 0, "retiring": False}) + "\n").encode()

    assert engine.stdout == fresh_run.stdout + end(1) + fresh_run.stdout + end(2)


def test_the_readers_once_per_process_warnings_are_said_once_per_command_as_a_process_of_its_own_would(capsys, monkeypatch):
    """``ocr._say_once`` keeps what this process has said; a process per command
    said each warning once per command, so the engine forgets it between two."""
    from tracker import ocr

    monkeypatch.setattr(ocr, "_SAID", set())
    monkeypatch.setitem(api.COMMANDS, "templates", lambda argv: ocr._say_once("a memory-limit sentence") or {})
    serve(capsys, frame(1, ["templates"]), frame(2, ["templates"]))
    assert error_log_text().count("a memory-limit sentence") == 2
