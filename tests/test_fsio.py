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
