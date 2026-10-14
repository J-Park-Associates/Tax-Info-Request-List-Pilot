"""Tests for tools/typecheck.py - no file may gain a type error the baseline does not hold.

Decision P310 (SPEC-architecture J6, R6.3). The suite never runs mypy: every
command here is handed a made-up reading in place of the real checker, the
way ``test_lockfiles`` hands its network commands made-up answers, so the
claims hold on a machine with no type checker installed. The gate runs the
real one (``python tools/typecheck.py check``). The last claims hold the
committed baseline and ``[tool.mypy]`` to what the tool and the SPEC say.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import tokenize
import tomllib
from pathlib import Path

import pytest

from tools import lockfiles, typecheck
from tools.typecheck import BASELINE, INSTALL, NOT_INSTALLED, TypeCheckError, check, read_output, update

REPO = Path(__file__).resolve().parent.parent
VERSION = "9.9.9"


def output(*errors: str, files: int | None = None, checked: int = 40) -> str:
    """What mypy prints with the tool's flags: one line per error, notes
    between them, and the summary last."""
    if not errors:
        return f"Success: no issues found in {checked} source files\n"
    named = files if files is not None else len({line.split(":", 1)[0] for line in errors})
    lines = [*errors, "tracker/a.py:3: note: See the documentation for more"]
    plural = "s" if len(errors) != 1 else ""
    lines.append(f"Found {len(errors)} error{plural} in {named} file{'s' if named != 1 else ''} "
                 f"(checked {checked} source files)")
    return "\n".join(lines) + "\n"


def mypy_saying(*errors: str, version: str = VERSION):
    """A stand-in for the checker that prints ``errors``, as ``check`` and ``update`` take it."""
    def run(root: Path) -> tuple[str, int, str]:
        return version, 1 if errors else 0, output(*errors)
    return run


def repository(root: Path, baseline: dict[str, list[str]] | None = None, version: str = VERSION) -> Path:
    """A made-up repository: a ``docs`` folder, and the baseline when one is given."""
    (root / "docs").mkdir(parents=True, exist_ok=True)
    if baseline is not None:
        data = {"note": typecheck.BASELINE_NOTE, "mypy": version,
                "total": sum(len(found) for found in baseline.values()), "files": baseline}
        (root / BASELINE).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return root


A_NONE = 'tracker/a.py:10: error: Item "None" of "str | None" has no attribute "strip"  [union-attr]'
A_RETURN = 'tracker/a.py:20: error: Incompatible return value type (got "str", expected "int")  [return-value]'
B_ARG = 'tools/b.py:5: error: Argument 1 to "f" has incompatible type "int"; expected "str"  [arg-type]'


def message(line: str) -> str:
    return line.split(": error: ", 1)[1]


# ----------------------------------------------------------- reading mypy ----


def test_each_error_is_counted_under_its_file_and_a_note_is_not_an_error():
    reading = read_output(VERSION, 1, output(A_RETURN, B_ARG, A_NONE))
    assert reading.version == VERSION
    assert reading.total == 3
    assert reading.errors == {
        "tracker/a.py": [(10, message(A_NONE)), (20, message(A_RETURN))],
        "tools/b.py": [(5, message(B_ARG))],
    }


def test_a_windows_run_names_each_file_as_a_linux_run_does():
    """The baseline is one file for every machine, so a backslash path is the
    same file as the forward-slash one."""
    reading = read_output(VERSION, 1, output(A_NONE.replace("tracker/a.py", "tracker\\a.py")))
    assert list(reading.errors) == ["tracker/a.py"]


def test_a_clean_run_reads_as_no_errors():
    reading = read_output(VERSION, 0, output())
    assert reading.errors == {} and reading.total == 0


def test_mypy_stopping_before_it_counts_fails_loudly_with_what_it_said():
    """Exit code 2 is a bad setting, a file mypy cannot parse or a blocking
    error: never read as a run with no errors."""
    said = "pyproject.toml: [mypy]: Unrecognized option: frobnicate = True\n"
    with pytest.raises(TypeCheckError, match="exit code 2") as raised:
        read_output(VERSION, 2, said)
    assert "Unrecognized option" in str(raised.value)


def test_a_summary_that_disagrees_with_the_lines_read_fails():
    """A change in mypy's output the tool cannot read must not read as fewer errors."""
    unreadable = output(A_NONE, B_ARG).replace(A_NONE, "tracker/a.py: line 10 is wrong somehow")
    with pytest.raises(TypeCheckError, match="mypy said 2 errors .* and 1 could be read"):
        read_output(VERSION, 1, unreadable)


def test_output_with_no_summary_line_fails():
    with pytest.raises(TypeCheckError, match="no summary line"):
        read_output(VERSION, 1, A_NONE + "\n")


def test_an_exit_code_that_disagrees_with_the_count_fails():
    with pytest.raises(TypeCheckError, match="exit code 0"):
        read_output(VERSION, 0, output(A_NONE))
    with pytest.raises(TypeCheckError, match="exit code 1"):
        read_output(VERSION, 1, output())


def test_no_checker_installed_is_one_sentence_naming_the_install(monkeypatch):
    monkeypatch.setattr(typecheck, "CHECKER", "no-such-distribution-made-up-for-this-test")
    with pytest.raises(TypeCheckError) as raised:
        typecheck.run_mypy(REPO)
    assert str(raised.value) == NOT_INSTALLED
    assert INSTALL in NOT_INSTALLED


# ------------------------------------------------------------------ check ----


def test_check_passes_at_the_baseline(tmp_path):
    repo = repository(tmp_path, {"tracker/a.py": [message(A_NONE), message(A_RETURN)],
                                 "tools/b.py": [message(B_ARG)]})
    assert check(repo, mypy_saying(A_NONE, A_RETURN, B_ARG)) == (
        [], "3 type errors in 2 files, none above the baseline")


def test_check_passes_below_the_baseline_and_says_update_lowers_it(tmp_path):
    repo = repository(tmp_path, {"tracker/a.py": [message(A_NONE), message(A_RETURN)],
                                 "tools/b.py": [message(B_ARG)]})
    problems, summary = check(repo, mypy_saying(A_RETURN))
    assert problems == []
    assert summary == ("1 type error in 1 files, none above the baseline; "
                       "2 fewer than it records, so python tools/typecheck.py update lowers it")


def test_a_file_the_baseline_holds_none_for_fails_on_its_first_error_and_names_it(tmp_path):
    repo = repository(tmp_path, {"tracker/a.py": [message(A_NONE), message(A_RETURN)]})
    problems, _summary = check(repo, mypy_saying(A_NONE, A_RETURN, B_ARG))
    assert problems == [f"tools/b.py: 1 type error, and the baseline records none\n  {B_ARG.split(': error: ')[0]}: "
                        f"{message(B_ARG)}"]


def test_a_file_above_its_count_names_only_the_errors_the_baseline_does_not_hold(tmp_path):
    """An error the baseline holds is not named; one whose message it holds
    fewer times is named on every line it is on, since either may be the new
    one, with how many the baseline holds."""
    repo = repository(tmp_path, {"tracker/a.py": [message(A_NONE), message(A_RETURN)]})
    again = A_NONE.replace(":10:", ":30:")
    problems, _summary = check(repo, mypy_saying(A_NONE, A_RETURN, again))
    assert problems == ["tracker/a.py: 3 type errors, and the baseline records 2\n"
                        f"  tracker/a.py:10, 30: {message(A_NONE)}  (the baseline holds 1 of these)"]


def test_a_reworded_error_at_the_same_count_is_no_failure(tmp_path):
    """The pass or fail is by count: a newer wording of an error mypy already
    counted lets in nothing."""
    repo = repository(tmp_path, {"tracker/a.py": [message(A_NONE)]})
    reworded = A_NONE.replace("has no attribute", "does not have the attribute")
    assert check(repo, mypy_saying(reworded))[0] == []


def test_check_without_a_baseline_says_update_records_the_first(tmp_path):
    with pytest.raises(TypeCheckError, match="python tools/typecheck.py update records the first one"):
        check(repository(tmp_path), mypy_saying(A_NONE))


def test_a_baseline_another_mypy_counted_fails_naming_the_install(tmp_path):
    repo = repository(tmp_path, {"tracker/a.py": [message(A_NONE)]}, version="1.0.0")
    with pytest.raises(TypeCheckError) as raised:
        check(repo, mypy_saying(A_NONE))
    assert "counted by mypy 1.0.0" in str(raised.value) and f"runs mypy {VERSION}" in str(raised.value)
    assert str(raised.value).endswith(INSTALL)


def test_a_baseline_whose_total_was_edited_by_hand_is_refused(tmp_path):
    repo = repository(tmp_path, {"tracker/a.py": [message(A_NONE)]})
    data = json.loads((repo / BASELINE).read_text(encoding="utf-8"))
    data["total"] = 5
    (repo / BASELINE).write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(TypeCheckError, match="edited by hand"):
        check(repo, mypy_saying(A_NONE))


@pytest.mark.parametrize("text", ["not json", "[]", '{"mypy": "9.9.9", "total": 0}',
                                  '{"mypy": "9.9.9", "total": 0, "files": {"tracker/a.py": []}}',
                                  '{"total": 1, "files": {"tracker/a.py": ["x"]}}'])
def test_a_baseline_this_tool_did_not_write_is_refused(tmp_path, text):
    repo = repository(tmp_path)
    (repo / BASELINE).write_text(text, encoding="utf-8")
    with pytest.raises(TypeCheckError, match=re.escape(BASELINE)):
        check(repo, mypy_saying(A_NONE))


# ----------------------------------------------------------------- update ----


def test_update_records_the_first_baseline(tmp_path):
    repo = repository(tmp_path)
    assert update(repo, mypy_saying(A_RETURN, B_ARG, A_NONE)) == (
        [], "3 type errors in 2 files recorded (no baseline)")
    data = json.loads((repo / BASELINE).read_text(encoding="utf-8"))
    assert data == {"note": typecheck.BASELINE_NOTE, "mypy": VERSION, "total": 3,
                    "files": {"tools/b.py": [message(B_ARG)],
                              "tracker/a.py": sorted([message(A_NONE), message(A_RETURN)])}}
    assert check(repo, mypy_saying(A_RETURN, B_ARG, A_NONE))[0] == []


def test_update_lowers_the_counts_after_a_fix(tmp_path):
    repo = repository(tmp_path, {"tracker/a.py": [message(A_NONE), message(A_RETURN)],
                                 "tools/b.py": [message(B_ARG)]})
    assert update(repo, mypy_saying(A_NONE)) == ([], "1 type error in 1 files recorded (3 before)")
    assert json.loads((repo / BASELINE).read_text(encoding="utf-8"))["files"] == {"tracker/a.py": [message(A_NONE)]}


def test_update_refuses_to_raise_a_count_and_leaves_the_baseline_as_it_was(tmp_path):
    repo = repository(tmp_path, {"tracker/a.py": [message(A_NONE)]})
    before = (repo / BASELINE).read_bytes()
    problems, summary = update(repo, mypy_saying(A_NONE, A_RETURN))
    assert problems == [f"tracker/a.py: 2 type errors, and the baseline records 1\n  tracker/a.py:20: {message(A_RETURN)}"]
    assert summary == ""
    assert (repo / BASELINE).read_bytes() == before


# -------------------------------------------------------------------- CLI ----


def test_the_check_command_prints_its_summary_and_exits_zero(tmp_path, monkeypatch, capsys):
    repo = repository(tmp_path, {"tracker/a.py": [message(A_NONE)]})
    monkeypatch.setattr(typecheck, "ROOT", repo)
    monkeypatch.setattr(typecheck, "run_mypy", mypy_saying(A_NONE))
    assert typecheck.main(["check"]) == 0
    assert capsys.readouterr().out == "check: 1 type error in 1 files, none above the baseline\n"


def test_the_check_command_names_each_file_above_the_baseline_and_exits_one(tmp_path, monkeypatch, capsys):
    repo = repository(tmp_path, {"tracker/a.py": [message(A_NONE)]})
    monkeypatch.setattr(typecheck, "ROOT", repo)
    monkeypatch.setattr(typecheck, "run_mypy", mypy_saying(A_NONE, A_RETURN, B_ARG))
    assert typecheck.main(["check"]) == 1
    err = capsys.readouterr().err
    assert "tracker/a.py: 2 type errors, and the baseline records 1" in err
    assert "tools/b.py: 1 type error, and the baseline records none" in err
    assert err.endswith("check: 2 files have more type errors than the baseline records\n")


def test_the_update_command_that_would_raise_a_count_exits_one_and_says_so(tmp_path, monkeypatch, capsys):
    repo = repository(tmp_path, {"tracker/a.py": [message(A_NONE)]})
    monkeypatch.setattr(typecheck, "ROOT", repo)
    monkeypatch.setattr(typecheck, "run_mypy", mypy_saying(A_NONE, A_RETURN))
    assert typecheck.main(["update"]) == 1
    assert capsys.readouterr().err.endswith(
        "update: the baseline is left as it was: 1 file has more type errors than the baseline records, "
        "and update never raises a count\n")


def test_a_command_that_cannot_count_exits_one_with_its_sentence(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(typecheck, "ROOT", repository(tmp_path))
    monkeypatch.setattr(typecheck, "run_mypy", mypy_saying(A_NONE))
    assert typecheck.main(["check"]) == 1
    assert capsys.readouterr().err.startswith("check: there is no docs/typecheck-baseline.json")


# ------------------------------------------- the committed baseline and settings ----


def test_the_committed_baseline_is_one_this_tool_wrote_by_the_pinned_checker():
    """A newer mypy may count differently, so the baseline names the version
    it was counted by, and that is the one requirements-dev.txt pins: bumping
    the pin means recounting."""
    baseline = typecheck.load_baseline(REPO)
    assert baseline is not None
    [(name, version, _marker)] = lockfiles.direct_pins(REPO / "requirements-dev.txt")
    assert (name, version) == ("mypy", baseline.version)
    for path in baseline.errors:
        assert path.startswith(("tracker/", "tools/")) and (REPO / path).is_file(), path


def test_the_checker_reads_what_the_spec_names():
    """R6.2, and the settings that make the count the same on every machine
    the gate runs on."""
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    settings = pyproject["tool"]["mypy"]
    floor = pyproject["project"]["requires-python"].removeprefix(">=")
    assert settings["files"] == ["tracker", "tools"]
    assert settings["python_version"] == floor
    assert settings["explicit_package_bases"] is True
    assert settings["platform"] == "linux"
    assert settings["no_site_packages"] is True


def test_every_third_party_package_the_checked_code_imports_is_read_as_untyped():
    """With no installed package's types read, a package mypy is not told to
    read as untyped is an error in every file importing it; and a name left
    on the list after its import has gone is a stale setting."""
    overrides = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["mypy"]["overrides"]
    untyped = {module.removesuffix(".*") for override in overrides if override.get("ignore_missing_imports")
               for module in override["module"]}
    tools = {path.stem for path in (REPO / "tools").glob("*.py")}
    imported = set()
    for path in [*(REPO / "tracker").rglob("*.py"), *(REPO / "tools").glob("*.py")]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else []
            imported |= {name.split(".")[0] for name in names}
    first_party = {"tracker", "tools", "tests", "__future__", *tools}
    assert {name for name in imported if name not in sys.stdlib_module_names and name not in first_party} == untyped


# The one excuse that is not a platform line (P2.1): the standard library's
# private regular-expression parser, which the value rule reads (decision
# 187) and typeshed does not stub. It is named by file and wording, so a
# second such line fails here rather than passing as this one.
UNSTUBBED = (("bounds.py", "# type: ignore[import-not-found]  # typeshed does not stub the private parser"),)


def test_every_ignore_in_the_checked_code_is_narrow():
    """R6.2: a platform line the checker cannot read on Linux is excused by
    its own error code, never by a whole file; the one other line is excused
    by name (UNSTUBBED)."""
    narrow = re.compile(r"# type: ignore\[[a-z-]+(, [a-z-]+)*\]  # (Windows|Mac) only \(mypy checks as Linux\)$")
    excused = 0
    unstubbed = []
    for path in [*(REPO / "tracker").rglob("*.py"), *(REPO / "tools").glob("*.py")]:
        with path.open("rb") as source:
            comments = [(token.start[0], token.string) for token in tokenize.tokenize(source.readline)
                        if token.type == tokenize.COMMENT]
        for number, comment in comments:
            assert not comment.lstrip("# ").startswith("mypy:"), f"{path.name}:{number}"
            if "type: ignore" in comment:
                if (path.name, comment) in UNSTUBBED:
                    unstubbed.append((path.name, comment))
                    continue
                assert narrow.match(comment), f"{path.name}:{number}"
                excused += 1
    assert excused == 9
    assert sorted(unstubbed) == sorted(UNSTUBBED)


def test_the_install_sentence_names_the_dev_lock_by_hash():
    assert INSTALL == f"pip install --require-hashes -r {lockfiles.DEV_LOCK}"


def test_the_tool_imports_the_standard_library_alone():
    tree = ast.parse((REPO / "tools" / "typecheck.py").read_text(encoding="utf-8"))
    names = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
             for alias in node.names}
    names |= {node.module.split(".")[0] for node in ast.walk(tree)
              if isinstance(node, ast.ImportFrom) and node.module}
    assert names - {"__future__"} <= sys.stdlib_module_names


def test_nothing_in_the_tracker_imports_the_checker():
    """mypy is never frozen into a package: nothing the app runs reads it."""
    for path in (REPO / "tracker").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] != "mypy" for alias in node.names), path.name
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] != "mypy", path.name
