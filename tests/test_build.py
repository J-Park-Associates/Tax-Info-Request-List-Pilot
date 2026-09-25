"""Tests for .github/workflows/build.yml — what CI builds is what ships.

Nothing here can prove the package runs; only the workflow itself can, on a
Windows runner, with a freeze and an Electron download. What can be proved is that the
workflow is pointed at the right things: that it runs the batch file this
repository owns rather than a second copy of the build, that the switch it
sets is the one that batch file reads, that the commands it fires at the
frozen executable use flags the Python owns, and that the interpreter it
names is the one interpreter written down. A workflow wrong about any of
those fails ten minutes into a run nobody triggers until release day.

The fixture it runs the package over is asserted here too, because a smoke
check over a folder with nothing in it proves only that discovery does not
crash.
"""

import json
import re
from pathlib import Path

from tests.samples import SCRATCH_HOUSEHOLD, SCRATCH_RETURN, build_scratch_root
from tracker.registry import discover_engagements
from tracker.runner import REMINDER_MODES, RUNNER_MODE_FLAG, main
from tracker.settings import ENV_PRODUCT_NAME, ENV_SETTINGS_DIR

REPO = Path(__file__).resolve().parent.parent
BUILD_WORKFLOW = "build.yml"
GATE_WORKFLOW = "gate.yml"
BUILD_SCRIPT = "Build App.bat"


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def workflow() -> str:
    return read(f".github/workflows/{BUILD_WORKFLOW}")


def commands() -> str:
    """The workflow with its comments dropped: what it runs, not what it explains.

    The prose is allowed to name PyInstaller and the build-info file, because
    saying what the batch file does is the point of it. Running them is what
    would make this a second copy of the build.
    """
    return "\n".join(line for line in workflow().splitlines()
                     if not line.lstrip().startswith("#"))


def fired_at_the_frozen_executable() -> str:
    """Only the lines that run the package, so pip's own flags are not read as the runner's."""
    return "\n".join(line for line in commands().splitlines() if "API_EXE" in line)


def office_python() -> str:
    """The interpreter the firm runs, from the one place it is written."""
    return re.search(r'(?ms)^\[tool\.office\].*?^python-version\s*=\s*"([^"]+)"',
                     read("pyproject.toml")).group(1)


def test_the_build_workflow_runs_the_repositorys_own_build_script():
    """Not a re-implementation of it: a second build is the one that drifts."""
    text = commands()
    assert f'"{BUILD_SCRIPT}"' in text
    # The steps that make the package are the batch file's, not this file's.
    for reimplemented in ("PyInstaller", "electron-packager", "robocopy", "npm ci",
                          "requirements-build.txt", "api_entry.spec"):
        assert reimplemented not in text, reimplemented


def test_the_build_workflow_is_never_run_per_commit():
    """Ten minutes a commit is what makes a build job get turned off."""
    triggers = workflow().split("\non:", 1)[1].split("\nconcurrency:", 1)[0]
    assert "workflow_dispatch:" in triggers
    assert "tags:" in triggers
    assert "branches:" not in triggers and "pull_request:" not in triggers


def test_the_workflow_skips_the_prompts_through_the_switch_the_script_reads():
    """One switch, read in one place, and every wait behind it."""
    script = read(BUILD_SCRIPT)
    switch = re.search(r"^if not defined (\w+) pause$", script, re.M).group(1)
    assert f"{switch}:" in workflow()
    # `pause` survives for a person, and only where that switch has cleared it.
    assert script.count("pause") == 1
    assert script.count(switch) == 2            # the header's explanation, and the reader


def test_the_workflow_types_no_path_the_build_script_or_the_shell_owns():
    """Where the package lands is the batch file's fact; the names are package.json's."""
    text = commands()
    package = json.loads(read("app/package.json"))
    script = read(BUILD_SCRIPT)
    for setting in ("OUT", "PLATFORM", "ARCH"):
        value = re.search(rf"^set {setting}=(\S+)$", script, re.M).group(1)
        assert f"set {setting}=" in text, setting     # read back out of the script
        assert value not in text, (setting, value)    # never retyped
    assert package["productName"] not in text
    assert package["config"]["apiName"] not in text
    assert "productName" in text and "config.apiName" in text
    # BUILD-INFO.txt is named by the line that writes it, not by this workflow.
    info = re.search(r'^>\s*"%PKG%\\([^"]+)"', script, re.M).group(1)
    assert info not in text


def test_the_smoke_checks_drive_the_frozen_entry_by_the_flags_the_code_owns():
    """`--run` and the dry-run flag are the runner's; a typo would only show in CI."""
    fired = fired_at_the_frozen_executable()
    declared = set(re.findall(r'"(--[a-z][a-z-]*)"', read("tracker/runner.py")))
    assert RUNNER_MODE_FLAG in declared                  # the constant is one of them
    used = set(re.findall(r"(--[a-z][a-z-]*)", fired))
    assert used <= declared, used - declared
    assert RUNNER_MODE_FLAG in used
    for mode in re.findall(r"--reminders (\w+)", fired):
        assert mode in REMINDER_MODES, mode


def test_the_smoke_checks_pass_the_environment_the_electron_shell_passes():
    """A frozen build has no package.json; the shell's two variables are how it is told."""
    text = workflow()
    assert f"{ENV_SETTINGS_DIR}:" in text
    assert f"{ENV_PRODUCT_NAME}=" in text


def test_both_workflows_name_the_one_interpreter_the_office_runs():
    """The version is written down once; a matrix row and a build step quote it."""
    office = office_python()
    floor = re.search(r'requires-python\s*=\s*">=([\d.]+)"', read("pyproject.toml")).group(1)
    assert office != floor                                   # otherwise there is nothing to add
    assert f'python-version: "{office}"' in workflow()
    ci = read(".github/workflows/ci.yml")
    assert f'python-version: "{office}"' in ci
    assert f'python-version: "{floor}"' in ci                 # and the floor is still run


def test_windows_runs_on_main_and_by_label_and_every_job_has_a_timeout():
    """Decision 122: a pull request pays for Linux; Windows is main's, or the label's.

    The Windows pair was four fifths of a run's price and repeated a gate that
    had just run on Windows locally. Windows is its own job now, because a
    job's own `if:` is evaluated before a matrix is expanded and cannot see
    it — so the steps live once, in gate.yml, which both jobs call. main must
    keep the Windows check, and the label must be able to ask for it on a pull
    request, which it can only do if labelling one starts a run.
    """
    ci = read(".github/workflows/ci.yml")
    gate = read(f".github/workflows/{GATE_WORKFLOW}")
    condition = re.search(r"^\s*if: (.+)$", ci.split("\n  windows:\n", 1)[1], re.M).group(1)
    assert "github.event_name == 'push'" in condition               # main keeps the Windows check
    assert "labels.*.name, 'windows'" in condition                  # and a pull request may ask
    types = re.search(r"^\s*types: \[([^\]]+)\]$", ci, re.M).group(1)
    assert "labeled" in types                                       # the label starts its own run
    # The gate is written once and called twice: a job's own `if:` cannot see
    # the matrix, so Linux and Windows are two jobs, not two rows of one.
    assert not re.search(r"^\s*steps:", ci, re.M)
    assert "workflow_call:" in gate
    # Without one, a hung job costs until GitHub's six-hour ceiling.
    assert "timeout-minutes:" in gate
    assert "timeout-minutes:" in workflow()


def test_a_scratch_root_is_one_engagement_a_whole_dry_pass_can_walk(tmp_path, capsys):
    """The smoke check's fixture: real folders, real documents, nothing written."""
    root = build_scratch_root(tmp_path / "clients")

    found = discover_engagements(root)

    assert [engagement.path.name for engagement in found.engagements] == [SCRATCH_RETURN]
    assert [household.name for household in found.households] == [SCRATCH_HOUSEHOLD]
    assert main([str(root), "--dry-run", "--reminders", REMINDER_MODES[1]]) == 0
    printed = capsys.readouterr().out
    assert SCRATCH_RETURN in printed and SCRATCH_HOUSEHOLD in printed
    assert "0 draft(s) written" in printed                    # dry: decided, not written


# ------------------------------------------ decision 137: the whole tree pinned ----

CONSTRAINTS = "constraints.txt"
#: The line of BUILD-INFO.txt after which the build lists what it froze
#: (written by "Build App.bat" from ``pip freeze``).
FROZEN_HEADING = "Python packages frozen"


def _name(package: str) -> str:
    """A distribution's name as pip compares them (PEP 503)."""
    return re.sub(r"[-_.]+", "-", package).lower()


def _pins(lines) -> dict[str, str]:
    pins = {}
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if "==" in line and not line.startswith("-"):
            package, version = line.split("==", 1)
            pins[_name(package)] = version.strip()
    return pins


def frozen_in(build_info: str) -> dict[str, str]:
    """What one BUILD-INFO.txt says the package froze, name -> version."""
    after = build_info.split(FROZEN_HEADING, 1)
    return _pins(after[1].splitlines()[1:]) if len(after) == 2 else {}


def constraints() -> dict[str, str]:
    return _pins(read(CONSTRAINTS).splitlines())


def drift(frozen: dict[str, str], pinned: dict[str, str]) -> list[str]:
    """Every package a build froze at a version the constraints do not say,
    or froze with no constraint at all: the build is not the commit's."""
    return sorted(f"{name}: froze {version}, constraints say {pinned.get(name, 'nothing')}"
                  for name, version in frozen.items() if pinned.get(name) != version)


def test_the_build_fails_when_a_frozen_version_differs_from_the_constraints():
    """Decision 137 (M5): requirements*.txt pin what the tracker imports by
    name; constraints.txt pins the whole tree under them, "Build App.bat"
    installs with it, and a package whose BUILD-INFO.txt froze anything
    else is not the build of its commit (the build of 09/17 froze pypdfium2
    5.13.0 against a pinned 5.11.0). Every package BUILD-INFO.txt lists in
    this checkout's build folder is held to it; with no build here, the rule
    is held on the freeze that exposed it."""
    pinned = constraints()
    # The tree the ruling names, and every direct pin agreeing with it.
    for package in ("pdfminer.six", "pypdfium2", "cryptography", "charset-normalizer",
                    "pillow-heif", "pyinstaller"):
        assert _name(package) in pinned, package
    for requirements in ("requirements.txt", "requirements-build.txt"):
        for name, version in _pins(read(requirements).splitlines()).items():
            assert pinned.get(name) == version, (requirements, name, version, pinned.get(name))
    script = read(BUILD_SCRIPT)
    assert re.search(r"pip install -r requirements-build\.txt -c constraints\.txt", script)

    # The rule, on the freeze of 09/17.
    old = ("Commit:   a1d261b\n\nPython packages frozen (pip freeze):\n"
           + "\n".join(f"{name}=={version}" for name, version in pinned.items()
                       if name != "pypdfium2") + "\npypdfium2==5.13.0\n")
    assert drift(frozen_in(old), pinned) == ["pypdfium2: froze 5.13.0, constraints say 5.11.0"]
    assert drift({**pinned, "numpy": "2.0"}, pinned) == ["numpy: froze 2.0, constraints say nothing"]
    assert drift(dict(pinned), pinned) == []

    # And on whatever this checkout last built.
    for info in (REPO / "build-portable" / "dist").glob("*/BUILD-INFO.txt"):
        frozen = frozen_in(info.read_text(encoding="utf-8", errors="replace"))
        assert frozen, info
        assert drift(frozen, pinned) == [], info


# ------------------------------------- decision 153: pypdf past its advisories ----

#: The highest first-patched version among the pypdf advisories Dependabot
#: raised on 6.7.4 (every one a denial of service on a hostile PDF).
PYPDF_ADVISORIES_FIXED_IN = (6, 16, 1)


def _resolved_pins(rel: str) -> dict[str, str]:
    """A requirements file's pins with its ``-r`` includes followed, as pip reads it."""
    pins: dict[str, str] = {}
    for line in read(rel).splitlines():
        included = re.match(r"\s*-r\s+(\S+)", line)
        if included:
            pins.update(_resolved_pins(included.group(1)))
    pins.update(_pins(read(rel).splitlines()))
    return pins


def test_the_pinned_pypdf_is_at_least_the_advisories_fix():
    """Decision 153: the tier-2 open test parses a client's PDF with pypdf,
    and 6.7.4 had 56 open advisories - infinite loops and runaway memory on
    a hostile file. The source and the frozen build must agree on one pypdf
    (decision 137), and that pypdf must be at or past the release that
    closes them all, so a later downgrade fails here."""
    pins = {rel: _resolved_pins(rel).get("pypdf")
            for rel in ("requirements.txt", "requirements-build.txt", CONSTRAINTS)}
    assert len(set(pins.values())) == 1, pins
    version = pins[CONSTRAINTS]
    assert version, pins
    assert tuple(int(part) for part in version.split(".")[:3]) >= PYPDF_ADVISORIES_FIXED_IN, version


def test_every_action_the_workflows_run_is_pinned_by_commit():
    """Decision 137 (B3): an action named by tag runs whatever code the tag
    names on the day - a tag can be moved. Every action a workflow takes
    from another repository is pinned by a full commit SHA, with the tag it
    stood for beside it; the repository's own reusable workflow is not
    somebody else's code and is named by path."""
    used = []
    for path in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            found = re.search(r"^\s*-?\s*uses:\s*(\S+)(.*)$", line)
            if found:
                used.append((path.name, found.group(1), found.group(2)))
    remote = [(name, ref, rest) for name, ref, rest in used if not ref.startswith("./")]
    assert remote
    for name, ref, rest in remote:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", ref), (name, ref)
        assert re.search(r"#\s*v\d+", rest), (name, ref, "the tag it stood for")
