"""Tests for tracker/fsio.py — the one way a file is replaced whole or not
at all: the temp name beside the target, and the swap over it."""

import ast
from pathlib import Path

import pytest

from tracker.fsio import TEMP_SUFFIX, temp_path_for

REPO = Path(__file__).resolve().parents[1]


def test_two_writers_never_share_a_temp_name_and_the_walk_ignores_it(tmp_path):
    from tracker.validators import is_ignored

    target = tmp_path / "settings.json"
    first, second = temp_path_for(target), temp_path_for(target)
    assert first != second
    assert first.parent == target.parent
    for temp in (first, second):
        assert temp.name.endswith(TEMP_SUFFIX)
        assert is_ignored(temp)                   # a stranded temp is never a document


def test_a_failed_save_reports_its_own_error_not_a_locked_temp_file(tmp_path, monkeypatch):
    # A writer may leave the half-written file open when it raises; on
    # Windows the temp then cannot be deleted. That must not turn a full
    # disk into "held by another program".
    import tracker.fsio as fsio_module
    from tracker.fsio import atomic_replacement

    target = tmp_path / "x.json"
    target.write_bytes(b"before")
    real_unlink = fsio_module.Path.unlink

    def held(self, *args, **kwargs):
        if self.name.endswith(fsio_module.TEMP_SUFFIX):
            raise PermissionError("[WinError 32] still open")
        return real_unlink(self, *args, **kwargs)
    monkeypatch.setattr(fsio_module.Path, "unlink", held)
    with pytest.raises(OSError, match="No space left"):
        with atomic_replacement(target) as temp:
            temp.write_bytes(b"half")
            raise OSError(28, "No space left on device")
    assert target.read_bytes() == b"before"


def test_fsio_imports_nothing_of_the_package():
    """Decision 120 put it at the bottom layer, and the point of the bottom
    layer is that everything may reach it. An import of the package here -
    at load time or inside a function - would make some module unable to
    use the one atomic write, which is how there came to be only one.

    ``tests/test_layers.py`` says the same thing from the table's side;
    this says it about the file, so a reader of this module's own tests is
    told the rule that shapes it.
    """
    tree = ast.parse((REPO / "tracker" / "fsio.py").read_text(encoding="utf-8"))
    reached = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "tracker":
            reached.append(node.module)
        elif isinstance(node, ast.ImportFrom) and node.level:
            reached.append("." * node.level + (node.module or ""))
        elif isinstance(node, ast.Import):
            reached += [a.name for a in node.names if a.name.split(".")[0] == "tracker"]
    assert reached == [], reached


@pytest.mark.parametrize("writer", ["text", "bytes", "copy"])
def test_every_writer_flushes_its_bytes_to_the_disk_before_the_swap(tmp_path, monkeypatch, writer):
    """Decision 155, A-F7. NTFS journals the rename and not the data, so a
    swap made before the bytes were down could leave ``settings.json`` or a
    README empty after a power cut. The text writer swapped unflushed until
    155; every writer flushes the temp first now."""
    import os

    import tracker.fsio as fsio_module

    said: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace

    def fsync(handle):
        said.append("fsync")
        return real_fsync(handle)

    def replace(source, target):
        said.append("replace")
        return real_replace(source, target)

    monkeypatch.setattr(fsio_module.os, "fsync", fsync)
    monkeypatch.setattr(fsio_module.os, "replace", replace)
    target = tmp_path / "settings.json"
    if writer == "text":
        fsio_module.write_text_atomically(target, "{}")
    elif writer == "bytes":
        fsio_module.write_bytes_atomically(target, b"{}")
    else:
        source = tmp_path / "source.json"
        source.write_bytes(b"{}")
        fsio_module.copy_atomically(source, target)
    monkeypatch.undo()
    # The temp is flushed immediately before the swap. On POSIX the folder
    # is flushed after it too (``_fsync_folder``), so the swap need not be
    # the last call - only the flush before it is the claim.
    swap = max(i for i, call in enumerate(said) if call == "replace")
    assert swap > 0 and said[swap - 1] == "fsync" and target.read_bytes() == b"{}"


def test_a_copy_that_does_not_prove_never_takes_the_name(tmp_path):
    """``copy_atomically``'s ``prove`` runs on the temp, before the swap: a
    copy that came out as something else leaves the target as it was."""
    from tracker.fsio import copy_atomically

    source, target = tmp_path / "a.pdf", tmp_path / "b.pdf"
    source.write_bytes(b"%PDF-1.4 whole")

    def refuse(temp):
        assert temp.read_bytes() == b"%PDF-1.4 whole" and not target.exists()
        raise ValueError("not the document")

    with pytest.raises(ValueError):
        copy_atomically(source, target, prove=refuse)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.pdf"]


def test_a_temp_beside_a_target_near_the_limit_fits_under_it_and_keeps_its_shape(tmp_path):
    """A working copy is named to fit Windows's limit (decision 131), and its
    temp is up to 24 characters longer: given the limit, the target's name
    inside the temp is cut so the temp fits too, and it is still a temp of
    the one shape the sweep recognises (decision 155)."""
    from tracker.fsio import TEMP_NAME, temp_owner

    limit = len(str(tmp_path)) + 60
    target = tmp_path / ("A01 - W-2 - TY2025" + "x" * (limit - len(str(tmp_path)) - 1 - 22) + ".pdf")
    assert len(str(target)) == limit
    temp = temp_path_for(target, limit=limit)
    assert len(str(temp)) <= limit and temp.parent == target.parent
    assert TEMP_NAME.fullmatch(temp.name) and temp_owner(temp.name) is not None
    short = tmp_path / "settings.json"
    assert temp_path_for(short, limit=limit).name.startswith("settings.json.")   # not cut: it fits


# ------------------------------------ decision 190: the mark of the internet ----


class _Stream:
    """What an injected opener hands back: a stream that remembers."""

    def __init__(self, written: dict, name: str):
        self.written, self.name = written, name

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def write(self, text: str) -> None:
        self.written[self.name] = text


def test_a_copy_is_marked_from_the_internet_on_windows(tmp_path, monkeypatch):
    import tracker.fsio as fsio_module

    written: dict = {}
    monkeypatch.setattr(fsio_module.os, "name", "nt")
    target = tmp_path / "budget.xlsm"
    assert fsio_module.mark_from_internet(
        target, _opener=lambda name, *a, **k: _Stream(written, name)) is True
    assert written == {str(target) + fsio_module.ZONE_STREAM: "[ZoneTransfer]\r\nZoneId=3\r\n"}


def test_marking_is_a_no_op_that_says_so_anywhere_but_windows(tmp_path, monkeypatch):
    import tracker.fsio as fsio_module

    monkeypatch.setattr(fsio_module.os, "name", "posix")

    def never(*_args, **_kwargs):
        raise AssertionError("nothing is opened where there is no mark to write")

    assert fsio_module.mark_from_internet(tmp_path / "budget.xlsm", _opener=never) is False


def test_a_mark_that_cannot_be_written_on_windows_is_raised_never_swallowed(tmp_path, monkeypatch):
    import tracker.fsio as fsio_module

    monkeypatch.setattr(fsio_module.os, "name", "nt")

    def refused(*_args, **_kwargs):
        raise OSError(95, "Operation not supported")

    with pytest.raises(OSError):
        fsio_module.mark_from_internet(tmp_path / "budget.xlsm", _opener=refused)
