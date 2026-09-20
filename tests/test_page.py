"""Tests for tracker/page.py — the markup both pages share, and the console.

The module has values in and markup out, and it is exercised end to end
through the two pages that draw with it (tests/test_view.py,
tests/test_runner.py). What is pinned here is the one thing it does that is
not markup: the console made to take what it cannot encode (decision 108).
"""

import io
import sys

from tracker.page import tolerant_console

ARROW = "\u2192"


def _console(encoding: str) -> io.TextIOWrapper:
    # newline pinned, so the claim is about the encoding and not the platform
    return io.TextIOWrapper(io.BytesIO(), encoding=encoding, newline="\n")


def _shown(console: io.TextIOWrapper) -> bytes:
    console.flush()
    return console.buffer.getvalue()


def test_the_tolerant_console_replaces_what_the_console_cannot_encode_and_leaves_a_utf8_console_alone(
    monkeypatch,
):
    narrow = _console("cp1252")
    monkeypatch.setattr(sys, "stdout", narrow)
    monkeypatch.setattr(sys, "stderr", _console("cp1252"))
    tolerant_console()
    print(f"2025 {ARROW} 2026")
    assert _shown(narrow) == b"2025 \\u2192 2026\n"
    assert narrow.encoding == "cp1252" and narrow.errors == "backslashreplace"
    assert sys.stderr.errors == "backslashreplace"

    wide = _console("utf-8")
    monkeypatch.setattr(sys, "stdout", wide)
    tolerant_console()
    print(f"2025 {ARROW} 2026")
    assert _shown(wide) == f"2025 {ARROW} 2026\n".encode()   # the same text as ever
    assert wide.encoding == "utf-8"


def test_a_stream_with_no_reconfigure_is_left_as_it_is(monkeypatch):
    plain = io.StringIO()
    assert not hasattr(plain, "reconfigure")
    monkeypatch.setattr(sys, "stdout", plain)
    monkeypatch.setattr(sys, "stderr", plain)
    tolerant_console()
    print(f"2025 {ARROW} 2026")
    assert sys.stdout is plain
    assert plain.getvalue() == f"2025 {ARROW} 2026\n"
