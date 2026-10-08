"""The one progress-line format and the cancel marker (decision 193)."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

from tracker import progress
from tracker.progress import (
    CANCEL_SUFFIX,
    PASSES_DIRNAME,
    PROGRESS_KEY,
    PROGRESS_MAX_BYTES,
    PROGRESS_SUFFIX,
    Watch,
    ask_to_stop,
    line,
    read_latest,
)


def _dead_pid() -> int:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


def test_a_progress_line_is_one_ascii_json_object_on_one_line_under_one_key():
    text = line(41, "file", step="sort", name="W-2 été\nsecond line.pdf",
                household="Sample Household", n=1, of=2)
    assert text.endswith("\n") and text.count("\n") == 1
    assert text.isascii()
    payload = json.loads(text)
    assert list(payload) == [PROGRESS_KEY]
    said = payload[PROGRESS_KEY]
    assert said["v"] == progress.FORMAT_VERSION and said["pass"] == 41
    assert said["event"] == "file" and said["name"].startswith("W-2 été")
    assert "at" in said
    long = json.loads(line(41, "file", name="x" * 5000))[PROGRESS_KEY]["name"]
    assert len(long) == progress.NAME_MAX_CHARS


def test_the_progress_file_holds_the_latest_line_and_is_gone_when_the_pass_ends(tmp_path):
    printed: list[str] = []
    watch = Watch(tmp_path, emit=printed.append, limit_seconds=7200)
    watch.say("started", started="2026-01-02T03:04:05", households=1)
    watch.say("household", household="Sample Household", n=1, of=1)
    watch.say("file", step="sort", name="1099-INT.pdf")
    latest = read_latest(tmp_path, watch.pass_id)
    assert latest["event"] == "file" and latest["name"] == "1099-INT.pdf"
    assert latest["household"] == "Sample Household" and latest["of"] == 1
    assert json.loads(printed[0])[PROGRESS_KEY]["limit_seconds"] == 7200
    assert [json.loads(one)[PROGRESS_KEY]["event"] for one in printed] == [
        "started", "household", "file"]
    watch.close("finished")
    assert json.loads(printed[-1])[PROGRESS_KEY]["outcome"] == "finished"
    assert read_latest(tmp_path, watch.pass_id) is None
    assert list((tmp_path / PASSES_DIRNAME).iterdir()) == []


def test_a_leftover_of_a_dead_pass_is_removed_and_a_live_ones_kept(tmp_path):
    passes = tmp_path / PASSES_DIRNAME
    passes.mkdir()
    dead = _dead_pid()
    for name in (f"{dead}{PROGRESS_SUFFIX}", f"{dead}{CANCEL_SUFFIX}",
                 f"{dead}{PROGRESS_SUFFIX}.tmp"):
        (passes / name).write_text("{}", encoding="utf-8")
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        live = passes / f"{other.pid}{PROGRESS_SUFFIX}"
        live.write_text("{}", encoding="utf-8")
        Watch(tmp_path, limit_seconds=60)
        assert live.exists()
        assert not any(path.name.startswith(f"{dead}.") for path in passes.iterdir())
    finally:
        other.kill()
        other.wait()


def test_a_stop_is_seen_at_the_next_check_and_stays_seen(tmp_path):
    printed: list[str] = []
    watch = Watch(tmp_path, emit=printed.append, limit_seconds=60)
    watch.say("started")
    assert not watch.stop_asked()
    assert ask_to_stop(tmp_path, watch.pass_id)
    assert watch.stop_asked()
    (tmp_path / PASSES_DIRNAME / f"{watch.pass_id}{CANCEL_SUFFIX}").unlink()
    assert watch.stop_asked(), "once seen, a stop stays seen"
    assert json.loads(printed[-1])[PROGRESS_KEY]["event"] == "stopping"
    watch.close("stopped")


def test_a_broken_emit_is_a_stop_that_sticks(tmp_path):
    """Decision 203, R6: the app that started a pass closed, and its pipe
    broke. The pass stops at its next check, as if a person had asked, and
    says why; nothing more is printed, the progress file is still kept."""
    printed: list[str] = []

    def emit(text: str) -> None:
        if len(printed) >= 2:
            raise BrokenPipeError(32, "Broken pipe")
        printed.append(text)

    watch = Watch(tmp_path, emit=emit, limit_seconds=60)
    watch.say("started")
    watch.say("household", household="Sample Household", n=1, of=1)
    assert not watch.stop_asked() and watch.why_stopped == ""
    watch.say("file", step="sort", name="W-2.pdf")          # the pipe breaks here
    assert watch.stop_asked() and watch.why_stopped == progress.APP_CLOSED
    assert watch.stop_asked(), "a reader gone does not come back"
    watch.say("file", step="sort", name="1099.pdf")
    assert len(printed) == 2, "nothing is printed to a pipe that broke"
    assert read_latest(tmp_path, watch.pass_id)["name"] == "1099.pdf"
    watch.close("stopped")

    asked = Watch(tmp_path / "again", emit=[].append, limit_seconds=60)
    asked.say("started")
    assert ask_to_stop(tmp_path / "again", asked.pass_id) and asked.stop_asked()
    assert asked.why_stopped == progress.ASKED
    asked.close("stopped")


def test_only_a_pass_the_app_started_can_be_asked_to_stop(tmp_path):
    scheduled = Watch(tmp_path, limit_seconds=60, pass_id=os.getpid())
    scheduled.say("started")
    assert not ask_to_stop(tmp_path, scheduled.pass_id)
    (tmp_path / PASSES_DIRNAME / f"{scheduled.pass_id}{CANCEL_SUFFIX}").write_bytes(b"")
    assert not scheduled.stop_asked(), "the scheduled pass never reads a marker as its own"
    assert not ask_to_stop(tmp_path, _dead_pid()), "no progress file, nothing to stop"
    scheduled.close("finished")


def test_reading_a_progress_file_is_bounded_and_never_raises(tmp_path):
    passes = tmp_path / PASSES_DIRNAME
    passes.mkdir()
    (passes / f"7{PROGRESS_SUFFIX}").write_bytes(b"{" + b" " * PROGRESS_MAX_BYTES + b"}")
    (passes / f"8{PROGRESS_SUFFIX}").write_bytes(b"\xff\xfe not json")
    (passes / f"9{PROGRESS_SUFFIX}").write_text("[1, 2]", encoding="utf-8")
    (passes / f"10{PROGRESS_SUFFIX}").mkdir()
    for pass_id in (7, 8, 9, 10, 11):
        assert read_latest(tmp_path, pass_id) is None
    assert read_latest(tmp_path / "not-there", 1) is None


def test_progress_imports_nothing_of_the_package_at_load_time():
    tree = ast.parse(Path(progress.__file__).read_text(encoding="utf-8"))
    load_time = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    names = [alias.name for node in load_time if isinstance(node, ast.Import) for alias in node.names]
    names += [node.module or "" for node in load_time if isinstance(node, ast.ImportFrom)]
    assert names and not any(name == "tracker" or name.startswith("tracker.") for name in names)


def test_a_failure_reply_says_its_sentence_once_as_the_error_and_in_the_failure():
    from tracker.progress import FAILURE_KINDS, failure_reply

    reply = failure_reply("the row moved; look again", "stale", seq=12, identifier="W-2.pdf",
                          warnings=["a warning"])
    assert reply["error"] == reply["failure"]["sentence"] == "the row moved; look again"
    assert reply["failure"] == {"sentence": "the row moved; look again", "kind": "stale",
                                "seq": 12, "identifier": "W-2.pdf"}
    assert reply["warnings"] == ["a warning"]
    odd = failure_reply("no", "refused", seq="12", identifier=["x"])
    assert odd["failure"]["seq"] is None and odd["failure"]["identifier"] is None
    assert set(FAILURE_KINDS) == {"stale", "locked", "refused", "failed"}


# --------------------------------------- the progress file's scan lines (P219) ----


class _Clock:
    """A monotonic clock a test moves by hand."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_a_scan_line_is_kept_at_most_once_a_second_and_every_other_line_at_once(tmp_path):
    clock = _Clock()
    watch = Watch(tmp_path, emit=[].append, limit_seconds=60, clock=clock)
    watch.say("household", household="Sample Household", n=1, of=1)
    watch.say("file", step=progress.SCAN_STEP, name="A01")
    assert read_latest(tmp_path, watch.pass_id)["event"] == "household"       # under a second: held
    clock.now += progress.SCAN_KEPT_EVERY_SECONDS
    watch.say("file", step=progress.SCAN_STEP, name="A02")
    assert read_latest(tmp_path, watch.pass_id)["name"] == "A02"
    clock.now += 0.2
    watch.say("file", step=progress.SCAN_STEP, name="A03")
    assert read_latest(tmp_path, watch.pass_id)["name"] == "A02"
    watch.say("stopping")                                                     # not a scan line: at once
    assert read_latest(tmp_path, watch.pass_id)["event"] == "stopping"


def test_a_sort_line_is_always_kept(tmp_path):
    """A sort line comes before a document's reading - the slow step the
    lock notice names - so it is never held, however close behind another."""
    clock = _Clock()
    watch = Watch(tmp_path, emit=[].append, limit_seconds=60, clock=clock)
    for name in ("one.pdf", "two.pdf", "three.pdf"):
        watch.say("file", step="sort", name=name)
        assert read_latest(tmp_path, watch.pass_id)["name"] == name


def test_every_line_is_still_printed(tmp_path):
    """Run now's reader is unchanged: every line reaches stdout."""
    printed: list[str] = []
    clock = _Clock()
    watch = Watch(tmp_path, emit=printed.append, limit_seconds=60, clock=clock)
    for n in range(5):
        watch.say("file", step=progress.SCAN_STEP, name=f"A0{n}")
    assert [json.loads(one)[PROGRESS_KEY]["name"] for one in printed] == [f"A0{n}" for n in range(5)]
