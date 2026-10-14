"""Tests for tracker/page.py — the markup both pages share, and the console.

The module has values in and markup out, and it is exercised end to end
through the two pages that draw with it (tests/test_view.py,
tests/test_runner.py). What is pinned here is the one thing it does that is
not markup: the console made to take what it cannot encode (decision 108);
the policy each page carries (decision 190); and, since SPEC-architecture
P2.8, the skeleton both pages are written in, line for line.
"""

import io
import sys

from tracker.page import document, esc, policy, tolerant_console

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


def test_a_policy_names_a_script_only_when_the_page_has_one():
    """A page with no script gets no script source at all, so an inserted
    script is refused by ``default-src 'none'``; a hash for a script is given
    only to the page that runs one, and the known digest of the empty text
    shows the hash is SHA-256 in base64 (decision 190)."""
    empty = "'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='"
    assert policy(style="") == (
        f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src {empty}">'
    )
    assert f"script-src {empty}" in policy(style="p {}", script="")
    assert "script-src" not in policy(style="p {}")


#: What a page with a style and a script is held to, written out: the hash of
#: each block is the SHA-256 of exactly the text the page writes for it.
_STYLE = "p { color: #1B2A4A; }"
_SCRIPT = 'document.body.dataset.sorted = "";'
_STYLE_ONLY = ("<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; "
               "style-src 'sha256-BwlYNMTLIJ2JS6CdompTZc4t1yr5810MLBgjW6jHVY4='\">")
_STYLE_AND_SCRIPT = ("<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; "
                     "style-src 'sha256-BwlYNMTLIJ2JS6CdompTZc4t1yr5810MLBgjW6jHVY4='; "
                     "script-src 'sha256-B7XSx4fV+XokioHFZHEPVrVt2tMGCopu+N1WVcgEegA='\">")


def test_a_document_is_the_two_pages_skeleton():
    """C-9: both pages are written through ``document()``, so its lines are
    the skeleton each page had typed for itself - the policy before the
    title and the blocks it names, the title and every meta name and value
    escaped, the style and the body the page's own markup. ``script`` only
    feeds the policy: no line ``document()`` writes is a script tag, whatever
    ``script=`` is, so a page with a script writes its own tag, last in its
    body, as the view does."""
    body = ["<h1>Made Up &amp; Co</h1>", "<p>made up</p>"]
    with_meta_and_script = document(
        'Made Up & "Co" <2025> — Status Report', _STYLE, [*body, f"<script>{_SCRIPT}</script>"],
        meta=(("tracker-one", "1 < 2"), ("tracker-two", 'a "quoted" & value')), script=_SCRIPT)
    assert with_meta_and_script == [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        _STYLE_AND_SCRIPT,
        "<title>Made Up &amp; &quot;Co&quot; &lt;2025&gt; — Status Report</title>",
        '<meta name="tracker-one" content="1 &lt; 2">',
        '<meta name="tracker-two" content="a &quot;quoted&quot; &amp; value">',
        "<style>p { color: #1B2A4A; }</style>",
        "</head>",
        "<body>",
        "<h1>Made Up &amp; Co</h1>",
        "<p>made up</p>",
        '<script>document.body.dataset.sorted = "";</script>',
        "</body>",
        "</html>",
    ]
    assert document("Made Up Clients", _STYLE, body) == [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        _STYLE_ONLY,
        "<title>Made Up Clients</title>",
        "<style>p { color: #1B2A4A; }</style>",
        "</head>",
        "<body>",
        "<h1>Made Up &amp; Co</h1>",
        "<p>made up</p>",
        "</body>",
        "</html>",
    ]
    assert _STYLE_AND_SCRIPT == policy(style=_STYLE, script=_SCRIPT)
    assert _STYLE_ONLY == policy(style=_STYLE)

    # The tag in the first page was the body's; document() writes none.
    for script in (None, "", _SCRIPT, "</script><script>alert(1)"):
        assert not [line for line in document("t", _STYLE, [], script=script) if "<script" in line], script

    # The view's title is joined before it is escaped: the separator holds no
    # character esc() changes, so that is the title it always wrote.
    label = 'Made Up & "Co" <2025>'
    assert esc(" — ") == " — "
    assert esc(f"{label} — Status Report") == f"{esc(label)} — {esc('Status Report')}"
