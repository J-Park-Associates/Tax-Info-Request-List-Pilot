"""Tests for tracker/fsio.py — the one way a file is replaced whole or not
at all: the temp name beside the target, and the swap over it."""

import ast
import os
import time
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


def test_a_rotating_append_keeps_the_newest_entries_in_at_most_keep_and_one_files(tmp_path):
    """Decision 186: the run log never grows for ever. An append that would
    take it past the size turns it over first - the file to ``.1``, ``.1``
    to ``.2``, the oldest dropped - and every entry lands whole."""
    from tracker.fsio import append_rotating

    log = tmp_path / "runs.log"
    entries = [f"entry {n:02d}\n" for n in range(20)]              # 9 bytes each
    for entry in entries:
        assert append_rotating(log, entry, max_bytes=30, keep=2) == log
    files = sorted(tmp_path.iterdir())
    assert [one.name for one in files] == ["runs.log", "runs.log.1", "runs.log.2"]
    assert all(one.stat().st_size <= 30 for one in files)
    kept = "".join((tmp_path / name).read_text(encoding="utf-8")
                   for name in ("runs.log.2", "runs.log.1", "runs.log"))
    assert kept == "".join(entries[-len(kept) // 9:])                # the newest, in order
    assert kept.endswith(entries[-1]) and len(kept) // 9 > 2 * 3     # the older files are full


def test_a_rotation_another_process_blocks_still_appends_the_entry(tmp_path, monkeypatch, caplog):
    """A rename the other writer blocks (Windows: the file is open) is
    skipped with a warning and tried again next time; the entry is never
    lost."""
    import tracker.fsio as fsio_module

    log = tmp_path / "runs.log"
    log.write_text("x" * 40, encoding="utf-8")

    def blocked(source, target):
        raise PermissionError(13, "The process cannot access the file")

    monkeypatch.setattr(fsio_module.os, "replace", blocked)
    with caplog.at_level("WARNING", logger="tracker.fsio"):
        fsio_module.append_rotating(log, "the entry\n", max_bytes=30, keep=3)
    assert log.read_text(encoding="utf-8") == "x" * 40 + "the entry\n"
    assert [one.name for one in tmp_path.iterdir()] == ["runs.log"]
    assert "Could not rotate" in caplog.text

    monkeypatch.undo()
    fsio_module.append_rotating(log, "the next\n", max_bytes=30, keep=3)
    assert log.read_text(encoding="utf-8") == "the next\n"
    assert (tmp_path / "runs.log.1").read_text(encoding="utf-8") == "x" * 40 + "the entry\n"


def test_two_writers_rotating_at_once_lose_neither_an_entry_nor_the_older_entries(tmp_path, monkeypatch):
    """Decision 186's review, S3: the scheduled pass and the app's pass both
    cross the size at once. The second finds the first's rotation lock held,
    appends and leaves the turning-over to it; nothing is renamed from a
    stale view, so the older file is shifted once, never overwritten."""
    import tracker.fsio as fsio_module

    log = tmp_path / "runs.log"
    log.write_text("x" * 100, encoding="utf-8")
    (tmp_path / "runs.log.1").write_text("older\n", encoding="utf-8")
    real_replace = os.replace
    the_other_writer = []

    def meanwhile(source, target):
        if not the_other_writer:        # the other writer, while this one is rotating
            the_other_writer.append(True)
            fsio_module.append_rotating(log, "A-entry\n", max_bytes=50, keep=3)
        return real_replace(source, target)

    monkeypatch.setattr(fsio_module.os, "replace", meanwhile)
    fsio_module.append_rotating(log, "B-entry\n", max_bytes=50, keep=3)
    monkeypatch.undo()

    everything = "".join((tmp_path / name).read_text(encoding="utf-8")
                         for name in ("runs.log.2", "runs.log.1", "runs.log"))
    assert everything == "older\n" + "x" * 100 + "A-entry\n" + "B-entry\n"
    assert (tmp_path / "runs.log.2").read_text(encoding="utf-8") == "older\n"
    assert not (tmp_path / ("runs.log" + fsio_module.ROTATION_LOCK_SUFFIX)).exists()


def test_a_rotation_whose_file_another_writer_already_moved_still_appends_the_entry(tmp_path, monkeypatch,
                                                                                    caplog):
    """A rotation that fails at any step - here the log was moved away
    under it (FileNotFoundError) - is abandoned and the entry still lands."""
    import tracker.fsio as fsio_module

    log = tmp_path / "runs.log"
    log.write_text("x" * 100, encoding="utf-8")
    real_replace = os.replace

    def moved_first(source, target):
        if Path(source) == log and log.exists():
            real_replace(log, tmp_path / "moved.log")
        return real_replace(source, target)

    monkeypatch.setattr(fsio_module.os, "replace", moved_first)
    with caplog.at_level("WARNING", logger="tracker.fsio"):
        fsio_module.append_rotating(log, "the entry\n", max_bytes=50, keep=3)
    assert log.read_text(encoding="utf-8") == "the entry\n"
    assert (tmp_path / "moved.log").read_text(encoding="utf-8") == "x" * 100
    assert "Could not rotate" in caplog.text
    assert not (tmp_path / ("runs.log" + fsio_module.ROTATION_LOCK_SUFFIX)).exists()


def test_a_rotation_lock_a_killed_writer_left_is_removed_and_the_next_append_rotates(tmp_path):
    """A lock nobody holds any more must not stop the log turning over for
    ever: a fresh one is left alone (its holder is rotating), a stale one is
    removed, and every entry is appended either way."""
    import tracker.fsio as fsio_module

    log = tmp_path / "runs.log"
    log.write_text("x" * 100, encoding="utf-8")
    lock = tmp_path / ("runs.log" + fsio_module.ROTATION_LOCK_SUFFIX)
    lock.write_bytes(b"")

    fsio_module.append_rotating(log, "one\n", max_bytes=50, keep=3)
    assert lock.exists() and not (tmp_path / "runs.log.1").exists()

    old = time.time() - fsio_module.ROTATION_LOCK_STALE_SECONDS - 5
    os.utime(lock, (old, old))
    fsio_module.append_rotating(log, "two\n", max_bytes=50, keep=3)
    assert not lock.exists()
    fsio_module.append_rotating(log, "three\n", max_bytes=50, keep=3)
    assert (tmp_path / "runs.log.1").read_text(encoding="utf-8") == "x" * 100 + "one\ntwo\n"
    assert log.read_text(encoding="utf-8") == "three\n"
