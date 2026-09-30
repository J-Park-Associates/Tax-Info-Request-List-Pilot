"""tools/noncoder_pages.py: the plain-English library cannot go stale silently (P116).

The first test is the guard: it runs ``check`` on the real repository, so a
new handoff note without a page, or an original changed after its page, fails
every gate. The rest build a miniature library in ``tmp_path`` and prove each
finding, ``place`` for each naming family, the Stop hook's three outcomes and
the settings file that registers it.
"""

from __future__ import annotations

import datetime
import json
import subprocess
from pathlib import Path

import pytest

from tools import noncoder_pages as np

REPO = Path(__file__).resolve().parent.parent
LIB = np.LIBRARY


def _page(original: str, tags: str = "Kind: Build · Topic: Screen", headings=None, title="# A page") -> str:
    headings = headings or np.HANDOFF_HEADINGS
    head = [title, "", f"**Original file:** `{original}`  ", "**Kind of file:** handoff note  ", f"**Tags:** {tags}  ", ""]
    return "\n".join(head + [f"## {h}\n\ntext\n" for h in headings])


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A miniature repository: one note, its page in a stage folder, stamped."""
    (tmp_path / "pilot" / "handoffs").mkdir(parents=True)
    (tmp_path / "pilot" / "handoffs" / "shell-S1.md").write_text("Date 2026-09-01\nbody\n", encoding="utf-8")
    folder = tmp_path / LIB / np.WORK_HISTORY / "Stage 1 - First"
    folder.mkdir(parents=True)
    (folder / "S1 - 01 Build.md").write_text(_page("pilot/handoffs/shell-S1.md", "Kind: Build · Topic: Screen · Stage: S1"),
                                             encoding="utf-8")
    (tmp_path / LIB / np.WORK_HISTORY / "Final Checks").mkdir()
    np.stamp(tmp_path)
    return tmp_path


def _kinds(root: Path) -> list[str]:
    return [f.kind for f in np.findings(root)]


def test_the_committed_library_is_current():
    found = np.findings(REPO)
    assert not found, "run `python tools/noncoder_pages.py todo`:\n" + np.work_order(found)


def test_a_current_library_has_no_findings(root):
    assert np.findings(root) == []


def test_a_new_handoff_note_without_a_page_is_reported_with_its_place(root):
    (root / "pilot" / "handoffs" / "shell-S1-review-1.md").write_text("x\n", encoding="utf-8")
    [finding] = np.findings(root)
    assert finding.kind == "missing"
    assert f"{LIB}/{np.WORK_HISTORY}/Stage 1 - First/S1 - 02 Review 1.md" in finding.fix


def test_an_original_changed_after_stamp_is_stale_and_stamp_clears_it(root):
    note = root / "pilot" / "handoffs" / "shell-S1.md"
    note.write_text(note.read_text(encoding="utf-8") + "more\n", encoding="utf-8")
    assert _kinds(root) == ["stale"]
    assert np.stamp(root) == []
    assert np.findings(root) == []


def test_crlf_in_an_original_is_not_stale(root):
    note = root / "pilot" / "handoffs" / "shell-S1.md"
    note.write_bytes(note.read_bytes().replace(b"\n", b"\r\n"))
    assert np.findings(root) == []


def test_a_page_with_no_recorded_fingerprint_is_stale(root):
    (root / np.RECORD).write_bytes(np.render_record({}))
    assert _kinds(root) == ["stale"]


def test_an_orphan_record_is_reported(root):
    record = np.load_record(root)
    record["docs/For NonCoders/gone.md"] = {"page": "0" * 64, "originals": {"pilot/handoffs/shell-S1.md": "0" * 64}}
    (root / np.RECORD).write_bytes(np.render_record(record))
    assert _kinds(root) == ["orphan"]
    assert np.stamp(root) == []


def test_an_original_a_page_no_longer_names_is_an_orphan(root):
    page = next((root / LIB).rglob("S1 - 01 Build.md")).relative_to(root).as_posix()
    record = np.load_record(root)
    record[page]["originals"]["pilot/handoffs/old.md"] = "0" * 64
    (root / np.RECORD).write_bytes(np.render_record(record))
    assert _kinds(root) == ["orphan"]


def _break(root: Path, old: str, new: str) -> None:
    page = next((root / LIB).rglob("S1 - 01 Build.md"))
    page.write_text(page.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


@pytest.mark.parametrize("old, new, fragment", [
    ("# A page", "A page", "'# ' title"),
    ("**Original file:** `pilot/handoffs/shell-S1.md`", "**Original file:** none", "names no file"),
    ("**Original file:** `pilot/handoffs/shell-S1.md`", "**Original file:** `pilot/handoffs/shell-S1.md`, `nope.md`",
     "not a file in the repository"),
    ("**Tags:** Kind: Build", "**Tags:** Kind: Sketch", "unknown Kind"),
    ("Topic: Screen", "Topic: Screen, Weather", "unknown Topic"),
    ("Stage: S1", "Stage: 1", "Stage '1'"),
    ("## What it did", "## What it did not", "missing the section '## What it did'"),
    ("text\n", "text once after installing\n", "decision 209"),
])
def test_a_malformed_page_is_reported(root, old, new, fragment):
    _break(root, old, new)
    assert any(f.kind == "malformed" and fragment in f.problem for f in np.findings(root))


def test_a_page_without_a_tags_line_is_malformed(root):
    _break(root, "**Tags:** Kind: Build · Topic: Screen · Stage: S1", "")
    assert any("Tags" in f.problem for f in np.findings(root))


def test_a_page_over_the_line_limit_is_malformed(root):
    _break(root, "## Words to know", "\n" * 200 + "## Words to know")
    assert any("the limit is 200" in f.problem for f in np.findings(root))


def test_a_program_page_needs_the_program_layout(root):
    (root / "app.js").write_text("x", encoding="utf-8")
    page = root / LIB / np.WORKS / "App.md"
    page.parent.mkdir(parents=True)
    page.write_text(_page("app.js", "Kind: Program file · Topic: Safety"), encoding="utf-8")
    assert any("'## What it is'" in f.problem for f in np.findings(root))
    page.write_text(_page("app.js", "Kind: Program file · Topic: Safety", np.PROGRAM_HEADINGS), encoding="utf-8")
    np.stamp(root)
    assert np.findings(root) == []


def test_a_hand_edited_start_page_is_reported_and_stamp_regenerates_it(root):
    start = root / np.START_PAGE
    start.write_text(start.read_text(encoding="utf-8") + "\nsneaky\n", encoding="utf-8")
    assert _kinds(root) == ["start"]
    np.stamp(root)
    assert np.findings(root) == []


def test_the_start_page_lists_a_page_by_its_tags_and_carries_the_footer(root):
    text = (root / np.START_PAGE).read_text(encoding="utf-8")
    assert "- [A page](<6 - Work History (Handoff Notes)/Stage 1 - First/S1 - 01 Build.md>) - Build (S1)" in text
    assert text.rstrip().endswith("Generated by tools/noncoder_pages.py stamp; do not edit by hand.")


def test_stamp_of_one_page_leaves_the_others_as_they_were(root):
    other = root / "pilot" / "handoffs" / "shell-S1-review-1.md"
    other.write_text("x\n", encoding="utf-8")
    page = root / LIB / np.WORK_HISTORY / "Stage 1 - First" / "S1 - 02 Review 1.md"
    page.write_text(_page("pilot/handoffs/shell-S1-review-1.md", "Kind: Review · Topic: Screen · Stage: S1"),
                    encoding="utf-8")
    note = root / "pilot" / "handoffs" / "shell-S1.md"
    note.write_text("changed\n", encoding="utf-8")
    assert np.stamp(root, [page.relative_to(root / LIB).as_posix()]) != []   # shell-S1's page is still stale
    assert [f.kind for f in np.findings(root)] == ["stale"]


def test_stamp_refuses_a_name_that_is_not_a_page(root):
    with pytest.raises(np.LibraryError):
        np.stamp(root, ["nothing.md"])


def test_pages_json_round_trips_byte_for_byte_through_stamp(root):
    before = (root / np.RECORD).read_bytes()
    np.stamp(root)
    assert (root / np.RECORD).read_bytes() == before
    assert before.endswith(b"\n") and json.loads(before)["version"] == 2


def test_the_committed_pages_json_round_trips_through_its_own_renderer():
    raw = (REPO / np.RECORD).read_bytes()
    assert np.render_record(np.load_record(REPO)) == raw


def test_findings_are_sorted_and_do_not_depend_on_the_order_files_were_made(tmp_path):
    def build(where: Path, order: list[str]) -> list[np.Finding]:
        (where / "pilot" / "handoffs").mkdir(parents=True)
        for name in order:
            (where / "pilot" / "handoffs" / name).write_text("x\n", encoding="utf-8")
        (where / LIB).mkdir(parents=True)
        return np.findings(where)
    names = ["zeta.md", "aaa.md", "mid.md", "b-note.md"]
    first = build(tmp_path / "one", names)
    second = build(tmp_path / "two", names[::-1])
    plain = lambda found: [(f.kind, f.page, f.originals, f.problem, f.fix) for f in found]  # noqa: E731
    assert len(first) >= 4 and plain(first) == plain(second)
    assert first == sorted(first)


# ------------------------------------------------------------------- place ----


def test_place_numbers_a_stage_note_after_the_highest_in_its_folder(root):
    assert np.place(root, "pilot/handoffs/shell-S1-rebuild-1.md") == f"{LIB}/{np.WORK_HISTORY}/Stage 1 - First/S1 - 02 Fix Round 1.md"
    assert np.place(root, "shell-S1-review-2.md").endswith("S1 - 02 Review 2.md")


def test_place_starts_a_new_stage_letter_at_one(root):
    assert np.place(root, "shell-S1b.md").endswith("Stage 1 - First/S1b - 01 Build.md")


def test_place_reports_a_stage_with_no_folder(root):
    with pytest.raises(np.LibraryError, match="stage 9"):
        np.place(root, "shell-S9.md")


def test_a_new_stage_with_no_folder_is_a_finding_that_asks_for_the_folder(root):
    (root / "pilot" / "handoffs" / "shell-S9.md").write_text("x\n", encoding="utf-8")
    [finding] = np.findings(root)
    assert finding.kind == "missing" and finding.originals == ("pilot/handoffs/shell-S9.md",)
    assert "stage 9" in finding.problem and "creates or names the stage folder" in finding.fix
    assert "[missing]" in np.hook(root, "{}")[2]


def test_place_numbers_the_final_checks(root):
    folder = root / LIB / np.WORK_HISTORY / "Final Checks"
    (folder / "6 Something.md").write_text("x", encoding="utf-8")
    assert np.place(root, "shell-final-review-D.md") == f"{LIB}/{np.WORK_HISTORY}/Final Checks/7 Final Review D.md"
    assert np.place(root, "shell-fixpass2.md").endswith("Final Checks/7 Fixpass2.md")


def test_place_puts_rulings_in_their_folder_without_a_number(root):
    for name, title in (("shell-rulings2.md", "Rulings2"), ("shell-ledger.md", "Ledger"), ("shell-spec-sync-2.md", "Spec Sync 2")):
        assert np.place(root, name) == f"{LIB}/{np.WORK_HISTORY}/Jason's Rulings and Plan Updates/{title}.md"


def test_place_puts_other_notes_under_other_work_with_the_notes_own_date(root):
    (root / "pilot" / "handoffs" / "some-audit.md").write_text("# t\nDone on 2026-08-15.\n", encoding="utf-8")
    assert np.place(root, "pilot/handoffs/some-audit.md") == f"{LIB}/{np.WORK_HISTORY}/Other Work/2026-08-15 Some Audit.md"


def test_place_uses_today_when_the_note_has_no_date(root):
    got = np.place(root, "pilot/handoffs/undated.md", today=datetime.date(2026, 10, 1))
    assert got.endswith("Other Work/2026-10-01 Undated.md")


# -------------------------------------------------------------------- hook ----


def test_the_hook_is_silent_and_exits_0_when_current(root):
    assert np.hook(root, "{}") == (0, "", "")


def test_the_hook_exits_2_with_the_work_order_on_stderr_when_stale(root):
    (root / "pilot" / "handoffs" / "shell-S1.md").write_text("changed\n", encoding="utf-8")
    code, out, err = np.hook(root, "{}")
    assert (code, out) == (2, "")
    assert err.startswith("The plain-English library (docs/For NonCoders) is out of date:")
    assert "shell-S1.md" in err and np.STYLE_FILE in err


def test_the_hook_only_warns_when_the_session_already_tried_once(root):
    (root / "pilot" / "handoffs" / "shell-S1.md").write_text("changed\n", encoding="utf-8")
    code, out, err = np.hook(root, json.dumps({"stop_hook_active": True}))
    assert code == 0 and err == "" and "out of date" in out


@pytest.mark.parametrize("garbage", ["", "not json", "[1, 2]", "null"])
def test_the_hook_survives_garbage_on_stdin(root, garbage):
    (root / "pilot" / "handoffs" / "shell-S1.md").write_text("changed\n", encoding="utf-8")
    assert np.hook(root, garbage)[0] == 2


def test_the_hook_exits_0_on_an_internal_error(tmp_path):
    (tmp_path / np.LIBRARY).mkdir(parents=True)
    (tmp_path / np.RECORD).write_text("{broken", encoding="utf-8")
    code, out, err = np.hook(tmp_path, "{}")
    assert code == 0 and "skipped" in out and err == ""


def test_the_hook_lists_at_most_twenty_findings(root):
    for i in range(25):
        (root / "pilot" / "handoffs" / f"note-{i:02d}.md").write_text("x\n", encoding="utf-8")
    _, _, err = np.hook(root, "{}")
    assert "and 5 more" in err and err.count("[missing]") == 20


def test_the_settings_register_the_hook_and_keep_the_permissions():
    settings = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))
    [entry] = settings["hooks"]["Stop"]
    [command] = entry["hooks"]
    assert command["type"] == "command"
    assert command["command"] == 'f="$CLAUDE_PROJECT_DIR/tools/noncoder_pages.py"; [ -f "$f" ] || exit 0; for p in "$CLAUDE_PROJECT_DIR/.venv/Scripts/python.exe" "$CLAUDE_PROJECT_DIR/.venv/bin/python" python3 python; do command -v "$p" >/dev/null 2>&1 && exec "$p" "$f" hook; done; exit 0'
    assert settings["permissions"]["deny"]


# ---------------------------------------------------------------- organize ----


def _add_page(root: Path, folder: str, name: str, original: str, tags: str, headings=None) -> Path:
    page = root / LIB / folder / name
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_page(original, tags, headings), encoding="utf-8")
    return page


def _program(root: Path, folder: str, name: str, original: str = "tools/thing.py", topic: str = "Engine") -> Path:
    (root / original).parent.mkdir(parents=True, exist_ok=True)
    (root / original).write_text("x\n", encoding="utf-8")
    return _add_page(root, folder, name, original, f"Kind: Program file · Topic: {topic}", np.PROGRAM_HEADINGS)


TODAY = datetime.date(2026, 10, 1)


def test_a_page_whose_original_was_removed_is_retired_with_a_retired_line(root):
    page = _program(root, f"{np.WORKS}/Engine and Schedule", "The thing (thing.py).md")
    np.stamp(root)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "first")
    (root / "tools" / "thing.py").unlink()
    assert np.organize(root, dry_run=True) == ([], [])          # deleted but not committed: not retired yet
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "delete")
    moved, refused = np.organize(root, today=TODAY)
    target = root / LIB / np.ARCHIVE / np.RETIRED / np.WORKS / "Engine and Schedule" / "The thing (thing.py).md"
    assert target.is_file() and not page.exists() and refused == []
    assert moved == [f"moved: {page.relative_to(root).as_posix()} -> {target.relative_to(root).as_posix()}"]
    lines = target.read_text(encoding="utf-8").split("\n")
    tags = next(i for i, ln in enumerate(lines) if ln.startswith("**Tags:**"))
    assert lines[tags + 1].startswith("**Retired:** 2026-10-01 - the file it explained was removed.")
    assert not (root / LIB / np.WORKS / "Engine and Schedule").exists()      # the empty folders went
    assert np.findings(root) == []
    assert "The thing" not in (root / np.RECORD).read_text(encoding="utf-8")
    assert f"{np.ARCHIVE}/{np.RETIRED}/{np.WORKS}/Engine and Schedule/The thing (thing.py).md" in \
        (root / np.START_PAGE).read_text(encoding="utf-8")


def test_a_renamed_original_is_a_finding_not_a_retirement(root):
    page = _program(root, f"{np.WORKS}/Engine and Schedule", "The thing (thing.py).md")
    np.stamp(root)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "first")
    (root / "tools" / "thing.py").rename(root / "tools" / "other.py")
    assert np.organize(root) == ([], []) and page.exists()
    found = [f for f in np.findings(root) if "missing but not removed in Git" in f.problem]
    assert [f.originals for f in found] == [("tools/thing.py",)]
    assert "fix the page's Original file line" in found[0].problem and "commit the deletion" in found[0].problem


def test_without_git_nothing_is_retired(root):
    page = _program(root, f"{np.WORKS}/Engine and Schedule", "The thing (thing.py).md")
    np.stamp(root)
    (root / "tools" / "thing.py").unlink()
    assert np.organize(root) == ([], []) and page.exists()


def test_a_page_with_only_some_originals_gone_is_malformed_not_retired(root):
    page = _program(root, f"{np.WORKS}/Engine and Schedule", "The thing (thing.py).md")
    text = page.read_text(encoding="utf-8").replace("`tools/thing.py`", "`tools/thing.py`, `tools/gone.py`")
    page.write_text(text, encoding="utf-8")
    assert np.organize(root, dry_run=True) == ([], [])
    assert any(f.kind == "malformed" and "gone.py" in f.problem for f in np.findings(root))


def test_inserting_a_note_renumbers_and_renames_the_later_pages_of_the_stage(root):
    folder = root / LIB / np.WORK_HISTORY / "Stage 1 - First"
    for k in (1, 2):
        (root / "pilot" / "handoffs" / f"shell-S1-review-{k}.md").write_text("x\n", encoding="utf-8")
        _add_page(root, f"{np.WORK_HISTORY}/Stage 1 - First", f"S1 - {k + 1:02d} Review {k}.md",
                  f"pilot/handoffs/shell-S1-review-{k}.md", "Kind: Review · Topic: Screen · Stage: S1")
    np.stamp(root)
    (root / "pilot" / "handoffs" / "shell-S1-rebuild-1.md").write_text("x\n", encoding="utf-8")
    _add_page(root, f"{np.WORK_HISTORY}/Stage 1 - First", "S1 - 04 Fix Round 1.md",
              "pilot/handoffs/shell-S1-rebuild-1.md", "Kind: Fix round · Topic: Screen · Stage: S1")
    moved, refused = np.organize(root, today=TODAY)
    assert refused == []
    assert sorted(p.name for p in folder.glob("*.md")) == [
        "S1 - 01 Build.md", "S1 - 02 Review 1.md", "S1 - 03 Fix Round 1.md", "S1 - 04 Review 2.md"]
    assert len(moved) == 2
    np.stamp(root)
    assert np.findings(root) == []


def test_a_moved_page_keeps_its_record_so_it_is_no_staler_than_before(root):
    old = next((root / LIB).rglob("S1 - 01 Build.md"))
    (root / LIB / np.WORK_HISTORY / "Stage 1 - First" / "S1 - 01 Build.md").rename(old.with_name("S1 - 05 Build.md"))
    np.organize(root)
    assert np.findings(root) == []


def test_a_program_page_outside_its_section_moves_to_the_default_subfolder(root):
    page = _program(root, "Loose", "Thing (thing.py).md", topic="Installer")
    np.stamp(root)
    moved, _ = np.organize(root)
    assert (root / LIB / np.BUILD / "Installer" / "Thing (thing.py).md").is_file() and not page.exists()
    assert len(moved) == 1 and not (root / LIB / "Loose").exists()


def test_a_program_page_with_an_unrelated_name_is_renamed_with_its_original(root):
    _program(root, np.RULES, "Unrelated words.md", topic="Code map")
    np.stamp(root)
    np.organize(root)
    assert (root / LIB / np.RULES / "Unrelated words (thing.py).md").is_file()


def test_a_program_page_may_name_its_originals_folder(root):
    _program(root, np.RULES, "The tools.md", original="tools/thing.py", topic="Code map")
    assert np.organize(root, dry_run=True) == ([], [])


def test_a_program_page_inside_its_section_is_left_alone(root):
    _program(root, f"{np.BUILD}/A subfolder a person chose", "Thing (thing.py).md", topic="Installer")
    assert np.organize(root, dry_run=True) == ([], [])


def test_an_overview_page_goes_to_start_here(root):
    (root / "pilot" / "HANDOFF.md").write_text("x\n", encoding="utf-8")
    _add_page(root, np.RULES, "Where it stands.md", "pilot/HANDOFF.md", "Kind: Overview · Topic: Screen")
    np.stamp(root)
    np.organize(root)
    assert (root / LIB / np.START / "Where it stands.md").is_file()


def test_a_handoff_page_in_the_wrong_folder_moves_to_the_one_its_note_names(root):
    (root / "pilot" / "handoffs" / "shell-rulings.md").write_text("x\n", encoding="utf-8")
    _add_page(root, "Loose", "Rulings page.md", "pilot/handoffs/shell-rulings.md", "Kind: Rulings · Topic: Screen")
    np.stamp(root)
    np.organize(root)
    assert (root / LIB / np.WORK_HISTORY / "Jason's Rulings and Plan Updates" / "Rulings page.md").is_file()


def test_organize_refuses_to_overwrite_a_different_file(root):
    _program(root, "Loose", "Thing (thing.py).md", topic="Installer")
    clash = root / LIB / np.BUILD / "Installer" / "Thing (thing.py).md"
    clash.parent.mkdir(parents=True)
    clash.write_text("someone else's file\n", encoding="utf-8")
    moved, refused = np.organize(root)
    assert moved == [] and [f.kind for f in refused] == ["organize"]
    assert clash.read_text(encoding="utf-8") == "someone else's file\n"
    assert (root / LIB / "Loose" / "Thing (thing.py).md").is_file()


def test_organize_dry_run_changes_nothing(root):
    page = _program(root, "Loose", "Thing (thing.py).md", topic="Installer")
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    moved, _ = np.organize(root, dry_run=True)
    assert moved and moved[0].startswith("would move: ")
    assert page.exists() and before == sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_organize_on_the_committed_library_has_nothing_to_do():
    assert np.organize(REPO, dry_run=True) == ([], [])


def test_history_is_exempt_from_the_page_rules_but_needs_a_title(root):
    old = root / LIB / np.ARCHIVE / np.RETIRED / "Old.md"
    old.parent.mkdir(parents=True)
    old.write_text("# Old\n\nno tags, no headings\n", encoding="utf-8")
    np.stamp(root)
    assert np.findings(root) == []
    assert "[Old](<7 - History/Retired Pages/Old.md>)" in (root / np.START_PAGE).read_text(encoding="utf-8")
    assert "Old.md" not in (root / np.RECORD).read_text(encoding="utf-8")
    old.write_text("no title\n", encoding="utf-8")
    assert [f.kind for f in np.findings(root)] == ["malformed"]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args], cwd=root, check=True,
                   capture_output=True)


def test_stamp_keeps_the_version_a_rewritten_page_replaces(root):
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "first")
    page = next((root / LIB).rglob("S1 - 01 Build.md"))
    old = page.read_text(encoding="utf-8")
    page.write_text(old.replace("text", "better text", 1), encoding="utf-8")
    notes: list[str] = []
    np.stamp(root, notes=notes, today=TODAY)
    kept = root / LIB / np.ARCHIVE / np.EARLIER / "S1 - 01 Build - until 2026-10-01.md"
    assert kept.read_text(encoding="utf-8") == old and any("kept the earlier version" in n for n in notes)
    assert np.findings(root) == []
    np.stamp(root, notes=notes, today=TODAY)                         # unchanged page: nothing more kept
    assert len(list((root / LIB / np.ARCHIVE / np.EARLIER).glob("*.md"))) == 1
    page.write_text(page.read_text(encoding="utf-8").replace("better", "best", 1), encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "second")
    page.write_text(page.read_text(encoding="utf-8").replace("best", "the best", 1), encoding="utf-8")
    np.stamp(root, notes=notes, today=TODAY)
    assert notes[-1].startswith("no earlier version") and "never stamped" in notes[-1]


def test_a_second_earlier_version_on_the_same_day_is_numbered(root):
    _git(root, "init", "-q")
    for word in ("one", "two"):
        page = next((root / LIB).rglob("S1 - 01 Build.md"))
        page.write_text(page.read_text(encoding="utf-8").replace("text", word, 1), encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", word)
        np.stamp(root, today=TODAY)
        page.write_text(page.read_text(encoding="utf-8").replace(word, word + " again", 1), encoding="utf-8")
        np.stamp(root, today=TODAY)
    names = sorted(p.name for p in (root / LIB / np.ARCHIVE / np.EARLIER).glob("*.md"))
    assert names == ["S1 - 01 Build - until 2026-10-01 (2).md", "S1 - 01 Build - until 2026-10-01.md"]


def test_stamp_without_git_says_so_and_carries_on(root):
    page = next((root / LIB).rglob("S1 - 01 Build.md"))
    page.write_text(page.read_text(encoding="utf-8").replace("text", "new", 1), encoding="utf-8")
    notes: list[str] = []
    assert np.stamp(root, notes=notes) == []
    assert len(notes) == 1 and notes[0].startswith("no earlier version")


def test_the_hook_applies_organize_before_check(root):
    _program(root, "Loose", "Thing (thing.py).md", topic="Installer")
    np.stamp(root)
    code, out, err = np.hook(root, "{}")
    assert (code, out) == (2, "") and err.startswith("moved: ")
    assert 'stage these moves (git add -A "docs/For NonCoders") and run python tools/repo_map.py update' in err
    assert (root / LIB / np.BUILD / "Installer" / "Thing (thing.py).md").is_file()
    again = _program_hook_active(root)
    assert again[0] == 0 and again[2] == "" and "would move" in again[1]
    assert (root / LIB / "Loose" / "Other (other.py).md").is_file()     # a session that already tried: nothing moved


def _program_hook_active(root: Path):
    _program(root, "Loose", "Other (other.py).md", original="tools/other.py", topic="Installer")
    np.stamp(root)
    return np.hook(root, json.dumps({"stop_hook_active": True}))


def test_the_hook_reports_an_organize_refusal_in_the_work_order(root):
    _program(root, "Loose", "Thing (thing.py).md", topic="Installer")
    clash = root / LIB / np.BUILD / "Installer" / "Thing (thing.py).md"
    clash.parent.mkdir(parents=True)
    clash.write_text("x\n", encoding="utf-8")
    code, _, err = np.hook(root, "{}")
    assert code == 2 and "[organize]" in err and "taken by a different file" in err


def test_a_failed_second_rename_rolls_back_every_rename_and_leaves_no_temp_file(root, monkeypatch):
    first = _program(root, "Loose", "One (one.py).md", original="tools/one.py", topic="Installer")
    second = _program(root, "Loose", "Two (two.py).md", original="tools/two.py", topic="Installer")
    np.stamp(root)
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    real = Path.rename
    calls = {"n": 0}

    def flaky(self, target):
        if ".organize-" in self.name:
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("disk went away")
        return real(self, target)

    monkeypatch.setattr(Path, "rename", flaky)
    with pytest.raises(np.LibraryError, match="put back where it was"):
        np.organize(root)
    monkeypatch.undo()
    assert first.is_file() and second.is_file()
    assert before == sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    assert np.findings(root) == []


def test_rolling_back_two_pages_that_swapped_names_loses_neither(tmp_path):
    first, second = tmp_path / "S1 - 02 Review 1.md", tmp_path / "S1 - 03 Fix Round 1.md"
    first.write_text("was the fix round\n", encoding="utf-8")        # each now sits at the other's old name
    second.write_text("was the review\n", encoding="utf-8")
    assert np._roll_back([(first, second), (second, first)], {}) == []
    assert first.read_text(encoding="utf-8") == "was the review\n"
    assert second.read_text(encoding="utf-8") == "was the fix round\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == [first.name, second.name]


def test_a_rollback_that_cannot_put_a_page_back_names_where_it_is(tmp_path):
    moved, home = tmp_path / "new.md", tmp_path / "old.md"
    moved.write_text("the page\n", encoding="utf-8")
    home.write_text("someone else\n", encoding="utf-8")               # never overwritten
    stuck = np._roll_back([(moved, home)], {})
    assert len(stuck) == 1 and "old.md" in stuck[0]
    assert home.read_text(encoding="utf-8") == "someone else\n"
    assert [p.read_text(encoding="utf-8") for p in tmp_path.glob("new.md.organize-undo-*")] == ["the page\n"]


def test_a_note_renamed_before_its_first_commit_does_not_retire_its_page(root):
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "first")
    note = root / "pilot" / "handoffs" / "newthing.md"
    note.write_text("Date 2026-09-30\nbody\n", encoding="utf-8")
    page = _add_page(root, f"{np.WORK_HISTORY}/Other Work", "2026-09-30 Newthing.md", "pilot/handoffs/newthing.md",
                     "Kind: Build · Topic: Screen")
    np.stamp(root)
    note.rename(note.with_name("renamed.md"))
    assert np.organize(root, today=TODAY)[0] == [] and page.is_file()
    assert any(f.kind == "malformed" and "newthing.md" in f.problem for f in np.findings(root))


def test_a_leftover_organize_file_is_a_finding(root):
    stray = root / LIB / np.BUILD / "Thing.md.organize-0"
    stray.parent.mkdir(parents=True)
    stray.write_text("x", encoding="utf-8")
    [finding] = np.findings(root)
    assert finding.kind == "organize" and "Thing.md.organize-0" in finding.problem


# -------------------------------------------------------------------- main ----


def _run_main(monkeypatch, root: Path, capsys, *argv: str, stdin: str = ""):
    import io
    monkeypatch.setattr(np, "ROOT", root)
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = np.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_main_hook_reads_its_json_from_stdin(root, monkeypatch, capsys):
    (root / "pilot" / "handoffs" / "shell-S1.md").write_text("changed\n", encoding="utf-8")
    assert _run_main(monkeypatch, root, capsys, "hook", stdin="{}")[0] == 2
    code, out, err = _run_main(monkeypatch, root, capsys, "hook", stdin=json.dumps({"stop_hook_active": True}))
    assert code == 0 and "out of date" in out and err == ""


def test_main_check_exits_1_with_the_findings_and_0_when_current(root, monkeypatch, capsys):
    assert _run_main(monkeypatch, root, capsys, "check")[0] == 0
    (root / "pilot" / "handoffs" / "shell-S1.md").write_text("changed\n", encoding="utf-8")
    code, out, _ = _run_main(monkeypatch, root, capsys, "check")
    assert code == 1 and "[stale]" in out


def test_main_organize_dry_run_prints_the_moves_and_changes_nothing(root, monkeypatch, capsys):
    page = _program(root, "Loose", "Thing (thing.py).md", topic="Installer")
    code, out, _ = _run_main(monkeypatch, root, capsys, "organize", "--dry-run")
    assert code == 0 and "would move: " in out and page.exists()
