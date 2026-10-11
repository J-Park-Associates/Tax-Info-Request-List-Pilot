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

from tests.samples import DEMO_ITEMS, SCRATCH_HOUSEHOLD, SCRATCH_RETURN, SCRATCH_SCAN, build_scratch_root
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
    assert "tags:" in triggers
    assert "branches:" not in triggers and "pull_request:" not in triggers


def test_a_package_is_built_only_from_a_version_tag():
    """Decision 191: `v*` tags are protected, so a package built from one
    is the build of reviewed code. No manual trigger (a run started by hand
    from any branch), and the job's own guard refuses any other ref."""
    triggers = "\n".join(line for line in workflow().split("\non:", 1)[1].split("\nconcurrency:", 1)[0]
                         .splitlines() if not line.lstrip().startswith("#"))
    assert "workflow_dispatch" not in commands()
    assert re.fullmatch(r'\s*push:\s*tags: \["v\*"\]\s*', triggers), triggers
    job = workflow().split("\njobs:", 1)[1]
    assert re.search(r"^    if: startsWith\(github\.ref, 'refs/tags/v'\)$", job, re.M)


def test_the_package_is_published_with_its_sha256_after_the_smoke_checks():
    """Decision 191: the zip is hashed after it has answered both smoke
    checks, the hash is written beside it and on the run's summary page (the
    copy the runbook compares), and the upload carries the zip and the hash."""
    run = commands()
    step = run.index("- name: Zip the package and publish its SHA-256")
    assert run.index("- name: The frozen executable makes one dry pass") < step < run.index(
        "- name: Upload the package")
    checksum = run[step:run.index("- name: Upload the package")]
    assert "Get-FileHash" in checksum and "-Algorithm SHA256" in checksum
    assert "GITHUB_STEP_SUMMARY" in checksum
    assert '"$hash  $zipName"' in checksum                     # the `sha256sum` / certutil-comparable form
    upload = run[run.index("- name: Upload the package"):]
    assert "${{ env.PACKAGE_ZIP }}" in upload and "${{ env.PACKAGE_SHA256 }}" in upload
    assert "${{ env.PACKAGE_DIR }}" not in upload
    # Review M-1: the upload is wrapped in the artifact's own zip, so the
    # runbook names the inner zip - by the name this step gives it - and
    # compares with the summary page, never only with the file beside it.
    runbook = read("docs/runbook.md")
    prefix = re.search(r'\$zipName = "([\w.-]+)\$env:GITHUB_REF_NAME\.zip"', checksum).group(1)
    artifact = re.search(r"^\s*name: (\S+)$", upload, re.M).group(1)
    assert f"certutil -hashfile {prefix}<tag>.zip SHA256" in runbook
    assert f"`{artifact}.zip`" in runbook
    step = runbook[runbook.index(f"`{artifact}.zip`"):]
    assert step.index(f"Unzip `{artifact}.zip`") < step.index("certutil -hashfile") < step.index("summary page")


def test_every_run_of_the_tracker_in_the_build_has_a_data_home_of_its_own():
    """Decision 186: the job sets the tracker's data folder under the
    runner's temp before any step runs the tracker, so no store, log or
    scratch of a smoke check lands in the runner account's own folder."""
    from tracker.settings import ENV_DATA_HOME

    run = commands()
    lines = run.splitlines()
    [home] = [n for n, line in enumerate(lines)
              if f"{ENV_DATA_HOME}=" in line and "RUNNER_TEMP" in line and "GITHUB_ENV" in line]
    tracker_runs = [n for n, line in enumerate(lines)
                    if "API_EXE" in line and "&" in line or "python -m tracker" in line
                    or "Build App.bat" in line]
    assert tracker_runs and home < min(tracker_runs)


def data_home_names() -> tuple[set[str], set[str]]:
    """Every name the data home or the settings folder holds, and the
    patterns of 159's set-asides, each spelled by the constant that owns it:
    what no package may carry (decision 186), on Windows and on a Mac alike."""
    from tracker.checkpoint import (
        CHECKPOINT_DAMAGED_FILENAME,
        CHECKPOINT_FILENAME,
        CHECKPOINT_JOURNAL_FILENAME,
        CHECKPOINT_SHM_FILENAME,
        CHECKPOINT_WAL_FILENAME,
        SET_ASIDE_SUFFIX,
    )
    from tracker.progress import PASSES_DIRNAME
    from tracker.runner import LAST_PASS_FILENAME, LOG_FILENAME, PASS_ORDER_FILENAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    from tracker.settings import (
        DATA_HOME_NAME,
        ERROR_LOG_BACKUPS,
        ERROR_LOG_FILENAME,
        OCR_SCRATCH_DIRNAME,
        SETTINGS_FILENAME,
    )
    from tracker.store import RECOVERED_DIR, STORE_FILENAME, STORE_SHM_FILENAME, STORE_WAL_FILENAME

    names = {
        STORE_FILENAME, STORE_WAL_FILENAME, STORE_SHM_FILENAME, LOG_FILENAME, PASS_ORDER_FILENAME,
        CHECKPOINT_FILENAME, CHECKPOINT_JOURNAL_FILENAME, CHECKPOINT_WAL_FILENAME,
        CHECKPOINT_SHM_FILENAME, CHECKPOINT_DAMAGED_FILENAME,
        RECOVERED_DIR, LAST_PASS_FILENAME,
        ERROR_LOG_FILENAME, *(f"{ERROR_LOG_FILENAME}.{n}" for n in range(1, ERROR_LOG_BACKUPS + 1)),
        PASSES_DIRNAME,
        SCHEDULE_XML_FILENAME, OCR_SCRATCH_DIRNAME, DATA_HOME_NAME, SETTINGS_FILENAME}
    # 159's set-asides by the pattern set_aside() gives them (186's rebase review, SF3).
    patterns = {name + SET_ASIDE_SUFFIX.format(version="*") + "*" for name in (STORE_FILENAME, CHECKPOINT_FILENAME)}
    return names, patterns


def test_the_package_is_proved_to_hold_no_store_log_task_file_or_settings():
    """The proof (decision 186): a step before the package is zipped and
    uploaded fails the build when anything in it bears a name the data
    home or the settings folder holds - each spelled by its constant,
    decision 159's files (the checkpoint's write-ahead log and shared memory
    among them, P214) and decision 193's error log, its rotated
    copies and its ``passes`` folder beside the store among them."""
    run = commands()
    step = run.index("- name: The package holds no store, run log, task file or settings")
    assert step < run.index("- name: Zip the package and publish its SHA-256") < run.index(
        "- name: Upload the package")
    body = run[step:run.index("- name: Zip the package and publish its SHA-256")]
    names, patterns = data_home_names()
    listed = re.search(r"\$names = @\(([^)]*)\)", body).group(1)
    assert set(re.findall(r"'([^']+)'", listed)) == names
    listed_patterns = re.search(r"\$patterns = @\(([^)]*)\)", body).group(1)
    assert set(re.findall(r"'([^']+)'", listed_patterns)) == patterns
    assert "$names -contains $name" in body and "$name -like $_" in body
    assert "$env:PACKAGE_DIR -Recurse -Force" in body and "throw" in body


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


def test_a_smoke_pass_that_logs_takes_its_root_from_a_settings_folder():
    """A root on the command line together with ``--log`` is the shape of
    the job installed before decision 131, and the runner refuses it
    unless the settings file names that root. So a smoke pass that logs
    names a settings folder, never a root."""
    from tracker.runner import LOG_FLAG, SETTINGS_FLAG

    for line in fired_at_the_frozen_executable().splitlines():
        if LOG_FLAG in line.split():
            assert SETTINGS_FLAG in line.split(), line
            assert "SCRATCH_ROOT" not in line, line


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


def test_ci_never_fires_per_commit():
    """Decision 211 (revising 207 and 122): CI runs only where a person asks.

    Every session runs the whole local gate before it pushes, so GitHub's paid
    minutes go only on a push to main (Linux, the net under what merged) and
    on a pull request marked ready (the one run main's branch protection needs
    before a merge). A push to a pull request runs nothing: there is no
    `synchronize` and no `opened`. Windows runs only when a ready pull request
    carries the `windows` label - marked ready with it, or given it - and
    never on main, because the office PC, which is Windows, ran the gate
    before the push. A draft runs nothing. Windows is its own job, because a
    job's own `if:` is evaluated before a matrix is expanded and cannot see it
    - so the steps live once, in gate.yml, which both jobs call.
    """
    ci = read(".github/workflows/ci.yml")
    gate = read(f".github/workflows/{GATE_WORKFLOW}")
    triggers = ci.split("\non:", 1)[1].split("\nconcurrency:", 1)[0]
    push = triggers.split("pull_request:", 1)[0]
    assert re.search(r"^\s*push:\s*$", push, re.M)                   # a push to main runs
    assert re.search(r"^\s*branches: \[main\]$", push, re.M)
    pull = triggers.split("pull_request:", 1)[1]
    assert re.search(r"^\s*branches: \[main\]$", pull, re.M)       # only pull requests into main
    types = {t.strip() for t in re.search(r"^\s*types: \[([^\]]+)\]$", pull, re.M).group(1).split(",")}
    assert types == {"ready_for_review", "labeled"}                  # never per commit
    assert "cancel-in-progress: true" in ci
    linux = re.search(r"^\s*if: (.+)$", ci.split("\n  linux:\n", 1)[1].split("\n  windows:\n", 1)[0], re.M).group(1)
    windows = re.search(r"^\s*if: (.+)$", ci.split("\n  windows:\n", 1)[1].split("\n  macos:\n", 1)[0],
                        re.M).group(1)
    macos = re.search(r"^\s*if: (.+)$", ci.split("\n  macos:\n", 1)[1], re.M).group(1)
    # The conditions are pinned whole, not by fragments: the same pieces in
    # another order (`A || B && C`) would say something else.
    assert linux == (                                                 # main, or a ready non-draft PR; never a label
        "github.event_name == 'push' || "
        "(github.event.action == 'ready_for_review' && github.event.pull_request.draft == false)")
    assert windows == (                                               # a ready PR that asked; never main
        "github.event_name == 'pull_request' && github.event.pull_request.draft == false"
        " && contains(github.event.pull_request.labels.*.name, 'windows')"
        " && (github.event.action == 'ready_for_review' || github.event.label.name == 'windows')")
    # macOS is the Windows job with `macos` in its condition (SPEC-mac R18): a
    # run on a Mac bills at ten times a Linux one, so it is the explicit ask
    # and nothing else - never a push to main, a draft or another branch.
    assert macos == windows.replace("'windows'", "'macos'")
    assert "'macos'" in macos and "windows" not in macos and "push" not in macos
    macos_job = ci.split("\n  macos:\n", 1)[1]
    assert re.search(r"^\s+os: macos-latest$", macos_job, re.M)
    assert re.search(r'^\s+python-version: "3\.14"$', macos_job, re.M)
    assert "uses: ./.github/workflows/gate.yml" in macos_job
    assert not re.search(r"^\s*(strategy|matrix):", macos_job, re.M)
    assert ci.count("macos-latest") == 1 and ci.count("windows-latest") == 1
    # A label run is its own concurrency group: adding any label must never
    # cancel the required Linux checks already running on the pull request.
    group = re.search(r"^\s*group: (.+)$", ci.split("\nconcurrency:", 1)[1], re.M).group(1)
    assert group == ("ci-${{ github.ref }}-${{ github.event.action == 'labeled'"
                     " && format('label-{0}', github.event.label.name) || 'gate' }}")
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


def test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else(tmp_path):
    """Decision 169: the frozen smoke check proves the package reads, so
    the pile holds a scan whose only words are the reader's - no text
    layer, a name that says nothing - and the reader files it. A package
    that could not read would park it, and its line would differ from the
    source's by one "review"."""
    from tracker.content_check import extract
    from tracker.router import route_file

    root = build_scratch_root(tmp_path / "clients")
    [scan] = root.rglob(SCRATCH_SCAN)

    assert extract(scan, ocr=False).needs_ocr                  # no words without the reader
    routed = route_file(scan, list(DEMO_ITEMS))
    assert routed.identifier == "A01", routed.reason           # the W-2 row, on its required words


# ------------------------------------------ decision 137: the whole tree pinned ----

#: The locks a build installs (decision 191): its freeze is their union.
BUILD_LOCKS = ("requirements.lock", "requirements-build.lock", "requirements-nodeps.lock")
RUNTIME_LOCK = "requirements.lock"
#: The line of BUILD-INFO.txt after which the build lists what it froze
#: (written by "Build App.bat" from ``pip freeze``).
FROZEN_HEADING = "Python packages frozen"


def _name(package: str) -> str:
    """A distribution's name as pip compares them (PEP 503)."""
    return re.sub(r"[-_.]+", "-", package).lower()


#: The two places the tree is installed that differ (decision 169, R-11a
#: and R-11b): the build and the office, Windows on the office's Python, and
#: CI's floor row, Linux on Python 3.11. A pin's marker is read for each.
BUILD_ENVIRONMENT = {"sys_platform": "win32", "python_version": "3.14"}
FLOOR_ENVIRONMENT = {"sys_platform": "linux", "python_version": "3.11"}
#: The Mac (SPEC-mac R12): Apple silicon on the office's interpreter.
MAC_ENVIRONMENT = {"sys_platform": "darwin", "python_version": "3.14"}


def _pin_lines(lines) -> list[tuple[str, str, str]]:
    """Every ``name==version`` line as (name, version, marker or ""); a lock's
    trailing continuation backslash is not part of the marker."""
    found = []
    for line in lines:
        line = line.split("#", 1)[0].strip().rstrip("\\").strip()
        if "==" in line and not line.startswith("-"):
            requirement, _, marker = line.partition(";")
            package, version = requirement.split("==", 1)
            found.append((_name(package), version.strip(), marker.strip()))
    return found


def _pins(lines, environment: dict[str, str] | None = None) -> dict[str, str]:
    """The pins that hold in ``environment`` (by default this interpreter's):
    a line whose marker does not hold there is not pip's there either."""
    from packaging.markers import Marker, default_environment

    where = {**default_environment(), **(environment or {})}
    return {name: version for name, version, marker in _pin_lines(lines)
            if not marker or Marker(marker).evaluate(where)}


def frozen_in(build_info: str) -> dict[str, str]:
    """What one BUILD-INFO.txt says the package froze, name -> version."""
    after = build_info.split(FROZEN_HEADING, 1)
    return _pins(after[1].splitlines()[1:]) if len(after) == 2 else {}


def locked(environment: dict[str, str] | None = None, locks: tuple[str, ...] = BUILD_LOCKS) -> dict[str, str]:
    """What the build's locks pin in ``environment``, name -> version."""
    pins: dict[str, str] = {}
    for lock in locks:
        pins.update(_pins(read(lock).splitlines(), environment))
    return pins


def drift(frozen: dict[str, str], pinned: dict[str, str]) -> list[str]:
    """Every package a build froze at a version the locks do not say,
    or froze with no lock line at all: the build is not the commit's."""
    return sorted(f"{name}: froze {version}, the locks say {pinned.get(name, 'nothing')}"
                  for name, version in frozen.items() if pinned.get(name) != version)


def test_the_build_fails_when_a_frozen_version_differs_from_the_locks():
    """Decision 137 (M5), on the locks of decision 191: requirements*.txt
    pin what the tracker imports by name; the locks pin the whole tree
    under them, by hash, "Build App.bat" installs exactly them, and a
    package whose BUILD-INFO.txt froze anything else is not the build of
    its commit (the build of 09/17 froze pypdfium2 5.13.0 against a pinned
    5.11.0). Every package BUILD-INFO.txt lists in this checkout's build
    folder is held to it; with no build here, the rule is held on the
    freeze that exposed it."""
    pinned = locked()
    # The tree the ruling names, and every direct pin agreeing with it.
    for package in ("pdfminer.six", "pypdfium2", "cryptography", "charset-normalizer",
                    "pillow-heif", "pyinstaller"):
        assert _name(package) in pinned, package
    for environment in (None, BUILD_ENVIRONMENT, FLOOR_ENVIRONMENT):
        where = locked(environment)
        for requirements in ("requirements.txt", "requirements-build.txt", NODEPS):
            for name, version in _pins(read(requirements).splitlines(), environment).items():
                assert where.get(name) == version, (environment, requirements, name, version,
                                                    where.get(name))
    script = read(BUILD_SCRIPT)
    assert re.search(r"pip install --require-hashes -r requirements\.lock -r requirements-build\.lock", script)

    # The rule, on the freeze of 09/17. That build froze 5.13.0 against a
    # pinned 5.11.0; since the pin itself moved to 5.13.0 (2026-10-01) the
    # replay freezes whichever of the two the locks do not hold.
    locked_pdfium = pinned["pypdfium2"]
    stray = "5.13.0" if locked_pdfium != "5.13.0" else "5.11.0"
    old = ("Commit:   a1d261b\n\nPython packages frozen (pip freeze):\n"
           + "\n".join(f"{name}=={version}" for name, version in pinned.items()
                       if name != "pypdfium2") + f"\npypdfium2=={stray}\n")
    assert drift(frozen_in(old), pinned) == [
        f"pypdfium2: froze {stray}, the locks say {locked_pdfium}"]
    assert drift({**pinned, "pandas": "3.0"}, pinned) == ["pandas: froze 3.0, the locks say nothing"]
    assert drift(dict(pinned), pinned) == []

    # And on whatever this checkout last built: the build's own markers.
    built = locked(BUILD_ENVIRONMENT)
    for info in (REPO / "build-portable" / "dist").glob("*/BUILD-INFO.txt"):
        frozen = frozen_in(info.read_text(encoding="utf-8", errors="replace"))
        assert frozen, info
        assert drift(frozen, built) == [], info


#: What PyInstaller 6.22.3 asks for on a Mac, from its published metadata
#: (``Requires-Dist``): macholib only there, as pefile and pywin32-ctypes are
#: only Windows'. The lock must name each by hash, or --require-hashes
#: refuses the whole install (decision 191).
PYINSTALLER_ON_A_MAC = ("altgraph", "macholib", "packaging", "pyinstaller-hooks-contrib", "setuptools")
#: The wheel each binary package installs from on an Apple silicon Mac on
#: Python 3.14, read off PyPI: name -> (version, file, SHA-256). A pin that
#: moves fails here until its row is read off PyPI again, so a release that
#: dropped its Apple silicon wheel is found on Linux, not on a Mac. ONNX
#: Runtime ships arm64 wheels only (macosx_14_0). pyclipper and PyInstaller
#: ship no arm64-only wheel: their universal2 wheel holds an arm64 slice and
#: is the one pip takes on an Apple silicon Mac.
MAC_WHEELS = {
    "onnxruntime": ("1.30.0", "onnxruntime-1.30.0-cp314-cp314-macosx_14_0_arm64.whl",
                    "8b6169c16a48429890d2f4a0c774ebf54dfe9066a998514aad0518a16d398547"),
    "opencv-python-headless": ("5.0.0.93", "opencv_python_headless-5.0.0.93-cp37-abi3-macosx_13_0_arm64.whl",
                               "030ca5e0837a2963ab36ef896baa9767eb8d2b83353fb28af5a521e40dd8756f"),
    "numpy": ("2.5.3", "numpy-2.5.3-cp314-cp314-macosx_14_0_arm64.whl",
              "adc1ada2662f8a5f960b8a10d9986897e7499ef07e06d4cfe7197f8cce923c07"),
    "shapely": ("2.1.2", "shapely-2.1.2-cp314-cp314-macosx_11_0_arm64.whl",
                "1ff629e00818033b8d71139565527ced7d776c269a49bd78c9df84e8f852190c"),
    "pyclipper": ("1.4.0", "pyclipper-1.4.0-cp314-cp314-macosx_10_15_universal2.whl",
                  "7c87480fc91a5af4c1ba310bdb7de2f089a3eeef5fe351a3cedc37da1fcced1c"),
    "pillow": ("12.3.0", "pillow-12.3.0-cp314-cp314-macosx_11_0_arm64.whl",
               "e158cb00350dc278f3b91551101aa7d12415a66ebf2c91d8d5ac14e56ddd3ad0"),
    "pillow-heif": ("1.8.0", "pillow_heif-1.8.0-cp314-cp314-macosx_11_0_arm64.whl",
                    "d953c39095d98584b7c60696b4bf25be561ef43a9441c44349e322b8f8a3233e"),
    "pypdfium2": ("5.13.0", "pypdfium2-5.13.0-py3-none-macosx_13_0_arm64.whl",
                  "da5c7b74eebf40b5c1fbe1de01aa1edc8827a79fb1efd999616bc20dcaf77ba4"),
    "pyinstaller": ("6.22.3", "pyinstaller-6.22.3-py3-none-macosx_10_13_universal2.whl",
                    "052f4a1cd4f81092ccb7a18fe8ebc9ecf832a5917317e39fb3775af4e959b253"),
    "cffi": ("2.1.1", "cffi-2.1.1-cp314-cp314-macosx_11_0_arm64.whl",
             "661c298b4821edebead0c91edd2b00374d67ad7c5a1f7a91d4442633b79d6a72"),
    "cryptography": ("50.0.1", "cryptography-50.0.1-cp311-abi3-macosx_11_0_arm64.whl",
                     "b8f852c65863251b9e3a1b8c150ce21e59b522dbb6a7d4bc80e680d38388e986"),
    "pyyaml": ("6.0.3", "pyyaml-6.0.3-cp314-cp314-macosx_11_0_arm64.whl",
               "34d5fcd24b8445fadc33f9cf348c1047101756fd760b4dacb5c3e99755703310"),
    "ruff": ("0.16.9", "ruff-0.16.9-py3-none-macosx_11_0_arm64.whl",
             "1632eb1d6197f33bd00b1acbc5b71009e89a8895c158e2d2b03a834fac964ab6"),
}


def _mac_hashes(environment: dict[str, str]) -> dict[str, set[str]]:
    """Every hash the build's locks name for each package that holds in ``environment``."""
    from packaging.markers import Marker, default_environment

    from tools.lockfiles import read_lock

    where = {**default_environment(), **environment}
    found: dict[str, set[str]] = {}
    for lock in BUILD_LOCKS:
        for name, _version, marker, hashes in read_lock(REPO / lock):
            if not marker or Marker(marker).evaluate(where):
                found.setdefault(_name(name), set()).update(hashes)
    return found


def test_every_lock_resolves_for_an_apple_silicon_mac():
    """SPEC-mac R12. A Mac installs the locks in hash mode like every other
    machine, and --require-hashes refuses a package no lock names. So in a
    Mac's environment every direct pin of every requirements file the build
    reads is in a lock, PyInstaller's own Mac requirement (macholib, as
    Windows has pefile) is locked by hash with the rest of its list, nothing
    Windows-only or graphics-card is asked for, and each binary package has
    the wheel an Apple silicon Mac installs among its hashes."""
    hashes = _mac_hashes(MAC_ENVIRONMENT)
    mac = locked(MAC_ENVIRONMENT)
    for rel in ("requirements.txt", NODEPS, "requirements-build.txt"):
        for name in _pins(read(rel).splitlines(), MAC_ENVIRONMENT):
            assert name in mac, (rel, name)
    assert _name("macholib") in _pins(read("requirements-build.txt").splitlines(), MAC_ENVIRONMENT)
    assert _name("macholib") not in locked(BUILD_ENVIRONMENT) and _name("macholib") not in locked(FLOOR_ENVIRONMENT)
    for name in PYINSTALLER_ON_A_MAC:
        assert hashes.get(name), name
    assert all(hashes[name] for name in mac), [name for name in mac if not hashes[name]]
    for name in ("pefile", "pywin32-ctypes", "onnxruntime-gpu", "colorama"):
        assert name not in mac, name
    assert mac["onnxruntime"] == "1.30.0" and mac["numpy"] == "2.5.3"
    for name, (version, wheel, digest) in MAC_WHEELS.items():
        assert mac[name] == version, (name, "read its Apple silicon wheel off PyPI again", mac[name])
        assert re.search(r"-macosx_\d+_\d+_(arm64|universal2)\.whl$", wheel), wheel
        assert digest in hashes[name], (name, wheel)


def test_the_frozen_api_is_built_for_apple_silicon_only_and_unsigned_but_ad_hoc():
    """SPEC-mac R13: on darwin the spec freezes arm64 alone (ONNX Runtime has
    no x86_64 Mac wheel, so universal2 is impossible), gives the console
    binary no icon (it sits inside the bundle), has PyInstaller sign it ad hoc
    and names no entitlements until signing lands (P239); every other
    platform keeps the .ico and none of these."""
    spec = read("api_entry.spec")
    mac, other = re.search(
        r'(?ms)^if sys\.platform == "darwin":\n(.*?)^else:\n(.*?)^$', spec).groups()
    assert re.search(r'PLATFORM_OPTIONS = \{"target_arch": "arm64", "codesign_identity": None, '
                     r'"entitlements_file": None\}', mac)
    assert "icon" not in mac and "universal2" not in mac
    assert 'PLATFORM_OPTIONS = {"icon": "app/assets/icon.ico"}' in other
    assert not re.search(r"target_arch|codesign|entitlements", other)
    assert re.search(r"^    \*\*PLATFORM_OPTIONS,$", spec, re.M)
    assert not re.search(r"^\s+(icon|target_arch|codesign_identity|entitlements_file)=", spec, re.M)
    assert "freeze_support()" in read("api_entry.py")


# ---------------------------------- decision 169: the reader, installed in two steps ----

#: The file holding rapidocr alone, installed with --no-deps (R-11).
NODEPS = "requirements-nodeps.txt"
#: The step every install of the tree makes after requirements.txt.
NODEPS_STEP = re.compile(r"pip install --require-hashes --no-deps -r requirements-nodeps\.lock")
#: The first step: the whole tree, from its lock, in hash mode.
TREE_STEP = re.compile(r"pip install --require-hashes -r requirements\.lock")
SETUP_SCRIPT = "Setup.bat"
LAUNCHER = "Start App.bat"
#: The Mac's three scripts for the batch files (SPEC-mac R16): setup, the
#: launcher, and the build, which is Build App.bat and the pilot installer's
#: build in one.
MAC_SETUP = "setup.command"
MAC_LAUNCHER = "start.command"
MAC_BUILD = "build-mac.sh"
MAC_SCRIPTS = (MAC_SETUP, MAC_LAUNCHER, MAC_BUILD)


def batch_files() -> list[str]:
    return sorted(path.name for path in REPO.glob("*.bat"))


def installing_places() -> dict[str, str]:
    """Every file that installs the tree, by name: the batch files and each
    workflow that runs ``pip install``."""
    places = {name: read(name) for name in (BUILD_SCRIPT, SETUP_SCRIPT, MAC_SETUP, MAC_BUILD)}
    for path in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"pip install", text):
            places[path.name] = text
    return places


def test_the_reader_is_installed_in_two_steps_everywhere_the_tree_is_installed():
    """R-11: rapidocr's metadata asks for the GUI build of OpenCV, so it is
    installed with --no-deps after requirements.lock, which holds what it
    really needs. Both steps, in that order, hash-checked, in the batch
    files and in every workflow that installs - and in the README's
    developer setup, which is how a person installs it by hand."""
    places = installing_places()
    assert {BUILD_SCRIPT, SETUP_SCRIPT, MAC_SETUP, MAC_BUILD, GATE_WORKFLOW, BUILD_WORKFLOW} <= set(places)
    for name, text in {**places, "README.md": read("README.md"), "CLAUDE.md": read("CLAUDE.md")}.items():
        first, second = TREE_STEP.search(text), NODEPS_STEP.search(text)
        assert first and second and first.start() < second.start(), name
    assert [name for name, _version, _marker in _pin_lines(read(NODEPS).splitlines())] == ["rapidocr"]


#: A pip install however it is spelled (review S-2): ``pip``, ``pip3``,
#: ``pip3.14``, ``pip.exe``, and ``python -m pip``, ``py -m pip`` or
#: ``%PY% -m pip`` (each ends in ``pip``), any case, any spacing.
PIP_INSTALL = re.compile(r"(?i)\bpip(?:\d+(?:\.\d+)?)?(?:\.exe)?\s+install\b")
#: An npm install however it is spelled: ``npm`` or ``npm.cmd``, running
#: ``ci``, ``install`` or its short form ``i``.
NPM_INSTALL = re.compile(r"(?i)\bnpm(?:\.cmd)?\s+(?:ci|install|i)\b")
#: A line that IS an npm install (not an echo of its name in an error line).
NPM_COMMAND = re.compile(r"(?i)(?:call\s+)?npm(?:\.cmd)?\s+(?:ci|install|i)\b")
#: The spellings the two patterns must catch, each a line a person might add.
PIP_SPELLINGS = ("pip install -r requirements.txt", "pip3 install pyinstaller", "pip3.14 install x",
                 "PIP.EXE Install x", "python -m pip  install -r requirements.txt",
                 "py -m pip install x", "%PY% -m pip install x", "python3 -m   pip\tinstall x")
NPM_SPELLINGS = ("npm ci", "call npm.cmd ci", "npm install", "npm i electron", "NPM   Install",
                 "call npm.CMD i")


def _commands(text: str) -> list[str]:
    """A batch file's or workflow's lines that run something: comments and echoes aside."""
    return [line.strip() for line in text.splitlines()
            if line.strip() and not re.match(r"\s*(#|rem\b|echo\b|::)", line, re.I)]


def _install_lines(text: str) -> list[str]:
    """Every command line that runs a pip install, however it is spelled."""
    return [line for line in _commands(text) if PIP_INSTALL.search(line)]


def test_every_spelling_of_an_install_is_recognised():
    """Review S-2: the proofs below are only as good as the pattern that
    finds an install - a ``pip3`` or a doubled space must not slip past."""
    for spelling in PIP_SPELLINGS:
        assert _install_lines(spelling) == [spelling.strip()], spelling
    for spelling in NPM_SPELLINGS:
        assert NPM_INSTALL.search(spelling), spelling
    for harmless in ("pipeline install", "rem pip install x", "echo pip install failed", "pip freeze"):
        assert not _install_lines(harmless), harmless
    for harmless in ("npm run build", "npm --version", "npm cache verify"):
        assert not NPM_INSTALL.search(harmless), harmless


def test_every_install_is_hash_checked_from_a_lock():
    """Decision 191: every pip install in every batch file and workflow
    reads a lock and checks every file's hash; none reads a requirements
    file or a constraint, and none upgrades pip (an unpinned, unhashed
    install)."""
    sources = {name: read(name) for name in (*batch_files(), *MAC_SCRIPTS)}
    sources.update({path.name: path.read_text(encoding="utf-8")
                    for path in sorted((REPO / ".github" / "workflows").glob("*.yml"))})
    seen = 0
    for name, text in sources.items():
        for line in _install_lines(text):
            seen += 1
            assert "--require-hashes" in line, (name, line)
            files = re.findall(r"-r\s+(\S+)", line)
            assert files and all(file.endswith(".lock") for file in files), (name, line)
            assert not re.search(r"\s-c\s", line) and "--upgrade" not in line and not re.search(r"\s-U\b", line), (
                name, line)
    assert seen >= 12                      # Setup, the build, the pack, their Mac scripts, gate and build workflows


def test_the_launcher_never_installs_and_says_when_setup_must_run():
    """Decision 191: a launch that installed would run a package's install
    code and reach the network every time the app opens. The launcher runs
    the private Python Setup.bat made, verifies its stamp, and refuses in
    the one sentence the lock tool owns."""
    from tools.lockfiles import NOT_SET_UP, STAMP_NAME

    launcher = read(LAUNCHER)
    assert "pip" not in launcher.lower()                    # not even in a comment
    for line in _commands(launcher):
        assert not PIP_INSTALL.search(line) and not NPM_INSTALL.search(line), line
    assert r"tools\lockfiles.py verify .venv" in launcher
    assert f"echo {NOT_SET_UP}" in launcher
    assert r'if not exist ".venv\Scripts\python.exe" goto :not_set_up' in launcher
    # Setup's stamp is its last command after the installs, found by the
    # commands themselves, never by a comment that names them (review S-3).
    setup = _commands(read(SETUP_SCRIPT))
    # The line that runs npm, not the error line after it that echoes its name.
    [npm] = [i for i, line in enumerate(setup) if NPM_COMMAND.match(line)]
    assert re.fullmatch(r"call npm ci\b.*", setup[npm]), setup[npm]
    [stamp] = [i for i, line in enumerate(setup) if re.search(r"tools\\lockfiles\.py stamp \.venv", line)]
    installs = [i for i, line in enumerate(setup) if PIP_INSTALL.search(line)]
    assert installs and stamp > max(installs) and stamp > npm, (stamp, installs, npm)
    assert STAMP_NAME.endswith(".json")


def test_every_batch_file_ignores_its_own_folder_when_it_finds_a_command():
    """E-10: before its first command, every batch file tells cmd not to
    look in the current folder for python, npm, node or git, so a file
    dropped beside it cannot run in their place; Windows' own tools are
    called by their full path."""
    assert {SETUP_SCRIPT, LAUNCHER, BUILD_SCRIPT, "Build GPU Pack.bat"} <= set(batch_files())
    for name in batch_files():
        statements = [line.strip() for line in read(name).splitlines()
                      if line.strip() and not re.match(r"\s*rem\b", line, re.I)]
        assert statements[:2] == ["@echo off", 'set "NoDefaultCurrentDirectoryInExePath=1"'], name
        for tool in ("where", "robocopy", "certutil"):
            for found in re.finditer(rf"(\S*)\b{tool}(\.exe)?\s", read(name)):
                line = read(name)[:found.start()].rsplit("\n", 1)[-1]
                if re.match(r"\s*rem\b", line, re.I):
                    continue
                assert found.group(1).endswith("%SystemRoot%\\System32\\") and found.group(2), (name, tool)


def test_every_checkout_leaves_no_credentials_behind():
    """F-12: no workflow pushes, so no checkout leaves the token in .git/config."""
    checkouts = 0
    for path in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for found in re.finditer(r"uses: actions/checkout@", text):
            checkouts += 1
            step = text[found.start():].split("\n      - ", 1)[0]
            assert "persist-credentials: false" in step, path.name
    assert checkouts >= 3


def test_the_audit_runs_weekly_on_linux_and_never_on_a_push():
    """Decision 191: the audit is detection, scheduled and by hand, on the
    cheaper runner, installing nothing - it adds no CI to any change."""
    audit = read(".github/workflows/audit.yml")
    triggers = audit.split("\non:", 1)[1].split("\npermissions:", 1)[0]
    assert "schedule:" in triggers and "workflow_dispatch:" in triggers
    assert "push:" not in triggers and "pull_request" not in triggers
    assert re.findall(r"runs-on: (\S+)", audit) == ["ubuntu-latest"]
    assert "python tools/lockfiles.py audit" in audit and "pip install" not in audit
    assert "contents: read" in audit


def test_the_gui_opencv_is_never_pinned_and_the_locks_cover_every_reader_pin():
    """R-11: the headless OpenCV only - the GUI build is in no requirements
    file and no lock - and requirements.lock covers every package in both
    install files, on the build and on CI's floor row."""
    gui = _name("opencv-python")
    for rel in ("requirements.txt", NODEPS, "requirements-build.txt", *BUILD_LOCKS, "requirements-gpu.lock"):
        assert gui not in {name for name, _version, _marker in _pin_lines(read(rel).splitlines())}, rel
    for environment in (BUILD_ENVIRONMENT, FLOOR_ENVIRONMENT):
        pinned = locked(environment)
        for rel in ("requirements.txt", NODEPS):
            for name in _pins(read(rel).splitlines(), environment):
                assert name in pinned, (environment, rel, name)
    assert _name("opencv-python-headless") in locked(BUILD_ENVIRONMENT, (RUNTIME_LOCK,))


def test_the_onnx_runtime_and_numpy_are_pinned_by_platform_and_interpreter():
    """R-11a and R-11b, as written in both files: the graphics card build
    of ONNX Runtime on Windows and the plain one elsewhere (the same
    module; CI has no card), and numpy 2.5.3 where Python is 3.12 or later
    with 2.4.6 for the floor's 3.11 row."""
    wanted = {
        ("onnxruntime-gpu", "1.30.0", 'sys_platform == "win32"'),
        ("onnxruntime", "1.30.0", 'sys_platform != "win32"'),
        ("numpy", "2.5.3", 'python_version >= "3.12"'),
        ("numpy", "2.4.6", 'python_version < "3.12"'),
    }
    for rel in ("requirements.txt", RUNTIME_LOCK):
        lines = set(_pin_lines(read(rel).splitlines()))
        assert wanted <= lines, (rel, wanted - lines)
    build, floor = locked(BUILD_ENVIRONMENT), locked(FLOOR_ENVIRONMENT)
    assert build["onnxruntime-gpu"] == "1.30.0" and "onnxruntime" not in build
    assert floor["onnxruntime"] == "1.30.0" and "onnxruntime-gpu" not in floor
    assert (build["numpy"], floor["numpy"]) == ("2.5.3", "2.4.6")


def test_the_graphics_card_pack_is_pinned_apart_and_read_by_its_own_build_step():
    """Ruling 2 and R-11: the NVIDIA wheels are pinned in
    requirements-gpu.txt and locked in requirements-gpu.lock, installed only
    by the pack's own build step, and in no file the app or CI installs."""
    pack = {name for name, _version, _marker in _pin_lines(read("requirements-gpu.txt").splitlines())}
    assert pack and all(name.startswith("nvidia-") for name in pack)
    assert pack == {name for name, _v, _m in _pin_lines(read("requirements-gpu.lock").splitlines())}
    for rel in ("requirements.txt", NODEPS, "requirements-build.txt", *BUILD_LOCKS):
        assert not pack & {name for name, _v, _m in _pin_lines(read(rel).splitlines())}, rel
    installers = {name: read(name) for name in batch_files()}
    installers.update({path.name: path.read_text(encoding="utf-8")
                       for path in (REPO / ".github" / "workflows").glob("*.yml")})
    readers = sorted(name for name, text in installers.items() if "requirements-gpu" in text)
    assert readers == ["Build GPU Pack.bat"], readers


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
            for rel in ("requirements.txt", "requirements-build.txt", RUNTIME_LOCK)}
    assert len(set(pins.values())) == 1, pins
    version = pins[RUNTIME_LOCK]
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


def test_the_smoke_check_fails_when_the_package_printed_nothing_to_compare():
    """REVIEW-169 N-2: a dry pass that prints no OK, ERROR or SKIP line
    would compare two empty strings and pass. The step throws first."""
    run = commands()
    guard = run.index("if (-not (& $lines $frozen)) { throw")
    assert guard < run.index("if ((& $lines $frozen) -ne (& $lines $source))")


def test_setup_runs_the_after_install_step_last_after_the_stamp():
    """Decision 209: every one-time step after installing is Setup's own last
    step - after the stamp, which records what was installed whatever the
    step then finds - and its failure is said in the module's own words."""
    from tracker.after_install import SETUP_RETRY

    setup = _commands(read(SETUP_SCRIPT))
    runs = [line for line in setup if not line.startswith((":", "if ", "pause", "exit", "goto"))]
    assert runs[-1] == "%PY% -m tracker.after_install --reason setup", runs[-1]
    [stamp] = [i for i, line in enumerate(setup) if re.search(r"tools\\lockfiles\.py stamp \.venv", line)]
    [step] = [i for i, line in enumerate(setup) if "-m tracker.after_install --reason setup" in line]
    assert step > stamp
    assert f"echo {SETUP_RETRY}" in read(SETUP_SCRIPT)


def test_batch_files_check_out_with_crlf():
    """cmd reads a batch file by byte offset, and loses its place in an LF
    file (Setup printed a stray "'mputer' is not recognized" after a pause
    on the office computer): every .bat checks out CRLF, while the
    repository still holds LF, which is what the map hashes."""
    import shutil
    import subprocess

    import pytest

    if shutil.which("git") is None:
        pytest.skip("git is not on PATH; the attribute cannot be asked")
    names = ["Setup.bat", "Start App.bat", "Build App.bat", "Build GPU Pack.bat"]
    assert set(names) <= set(batch_files())
    said = subprocess.run(["git", "check-attr", "eol", "--", *names], cwd=REPO,
                          capture_output=True, text=True, check=True).stdout.splitlines()
    assert said == [f"{name}: eol: crlf" for name in names], said


ICON_SOURCE = "pilot/brand/tax-document-console/app/icon.ico"
ICON_COPY = "app/assets/icon.ico"


def test_the_packaged_exe_carries_the_console_icon():
    """The packager writes the icon into the shell's .exe (run from app/, so the
    path is app-relative) and the freeze gives the engine's .exe the same file."""
    packager = next(line for line in read(BUILD_SCRIPT).splitlines() if "electron-packager.mjs" in line)
    assert "--icon=assets\\icon.ico" in packager
    spec = read("api_entry.spec")
    assert f'PLATFORM_OPTIONS = {{"icon": "{ICON_COPY}"}}' in spec
    assert (REPO / ICON_COPY).is_file()


def test_the_dev_launch_icon_is_a_byte_identical_copy_of_the_artworks():
    """app/assets/icon.ico is committed because the unpackaged launch needs it;
    the artwork's generator owns the original, so the copy cannot drift."""
    assert (REPO / ICON_COPY).read_bytes() == (REPO / ICON_SOURCE).read_bytes()


#: The oldest macOS the pinned Electron (44) runs on; R6's bundle minimum.
ELECTRON_MACOS_FLOOR = "13.0"
MAC_ICON_SOURCE = "pilot/brand/tax-document-console/app/icon.icns"
MAC_ICON_COPY = "app/assets/icon.icns"
ARTWORK_APP = "pilot/brand/tax-document-console/app"


def _icns_module():
    """The artwork generator's packer, loaded by path: it lives in a design tool's
    folder that is not a package, beside the .ico packer it is written like."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "brand_icns", REPO / "pilot/brand/tax-document-console/source/icns.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _icns_elements(data: bytes) -> list[tuple[str, bytes]]:
    """(type, payload) of each element of an .icns, after checking its two lengths."""
    import struct

    assert data[:4] == b"icns" and struct.unpack(">I", data[4:8])[0] == len(data)
    found, at = [], 8
    while at < len(data):
        kind, length = data[at:at + 4].decode("ascii"), struct.unpack(">I", data[at + 4:at + 8])[0]
        found.append((kind, data[at + 8:at + length]))
        at += length
    assert at == len(data)
    return found


def _png(size: int) -> bytes:
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGBA", (size, size), (0, 0, 0, 255)).save(out, "PNG")
    return out.getvalue()


def test_the_mac_icon_is_a_byte_identical_copy_of_the_artworks():
    """SPEC-mac R15: app/assets/icon.icns is what electron-packager puts in the
    bundle and what the unpackaged launch needs; the artwork's generator owns
    the original, so the copy cannot drift - the same rule as the .ico's."""
    assert (REPO / MAC_ICON_COPY).read_bytes() == (REPO / MAC_ICON_SOURCE).read_bytes()


def test_the_mac_icon_is_made_from_the_same_renders_as_the_windows_one():
    """P232 (one export, both icons): the five sizes the .ico also holds and
    the artwork's own single PNGs are the very bytes inside the .icns, and the
    two sizes only a Mac wants (512 and 1024) are drawn at their own size."""
    packer = _icns_module()
    elements = dict(_icns_elements((REPO / MAC_ICON_SOURCE).read_bytes()))
    assert [kind for kind, _png_bytes in _icns_elements((REPO / MAC_ICON_SOURCE).read_bytes())] == [
        kind for kind, _pixels in packer.ELEMENTS]
    for kind, pixels in packer.ELEMENTS:
        assert packer._png_size(elements[kind]) == (pixels, pixels), kind
        single = REPO / ARTWORK_APP / f"icon-{pixels}.png"
        if single.is_file():
            assert elements[kind] == single.read_bytes(), kind


def test_the_icns_packer_writes_apples_ten_elements_with_their_own_lengths():
    packer = _icns_module()
    renders = {size: _png(size) for size in packer.SIZES}
    elements = _icns_elements(packer.pack(renders))
    assert [kind for kind, _body in elements] == [
        "icp4", "icp5", "ic11", "ic12", "ic07", "ic13", "ic08", "ic14", "ic09", "ic10"]
    assert dict(packer.ELEMENTS) == {
        "icp4": 16, "icp5": 32, "ic07": 128, "ic08": 256, "ic09": 512, "ic10": 1024,
        "ic11": 32, "ic12": 64, "ic13": 256, "ic14": 512}
    assert [body for _kind, body in elements] == [renders[pixels] for _kind, pixels in packer.ELEMENTS]


def test_the_icns_packer_refuses_a_missing_wrong_sized_or_non_png_render():
    import pytest

    packer = _icns_module()
    renders = {size: _png(size) for size in packer.SIZES}
    with pytest.raises(ValueError, match="1024"):
        packer.pack({size: png for size, png in renders.items() if size != 1024})
    with pytest.raises(ValueError, match="came back"):
        packer.pack({**renders, 512: _png(256)})
    with pytest.raises(ValueError, match="PNG"):
        packer.pack({**renders, 64: b"BM" + bytes(64)})


# ------------------------------------- SPEC-mac R16, R17: the Mac's scripts and bundle ----


def _bash() -> str:
    import shutil

    import pytest

    found = shutil.which("bash")
    if found is None:
        pytest.skip("bash is not on PATH")
    return found


def _sh(rel: str) -> list[str]:
    """A shell script's lines that run something: comments and echoes dropped."""
    return [line for line in _commands(read(rel)) if not line.startswith("#!")]


def _between(text: str, first: str, last: str) -> str:
    return text[text.index(first):text.index(last)]


#: The block every Mac script opens with, after its cd: PATH reduced to its
#: absolute folders, from the line that starts it to the line that ends it.
PATH_BLOCK = ('clean_path=""', "PATH=$clean_path")


def _path_block(rel: str) -> str:
    text = read(rel)
    return text[text.index(PATH_BLOCK[0]):text.index(PATH_BLOCK[1]) + len(PATH_BLOCK[1])]


def test_every_mac_script_runs_under_the_bash_macos_ships_and_parses():
    """SPEC-mac R16: /bin/bash is 3.2 on every Mac, whatever else is
    installed, so no script uses what 3.2 lacks - mapfile and readarray,
    ${x,,} and ${x^^}, associative arrays, namerefs, |&, &>> and coproc -
    and each starts with the interpreter it means and ``bash -n`` parses it."""
    import subprocess

    bash = _bash()
    for name in MAC_SCRIPTS:
        text = read(name)
        assert text.startswith("#!/bin/bash\n"), name
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        for lacking in (r"\bmapfile\b", r"\breadarray\b", r"\$\{[^}]*(,,|\^\^)", r"\bdeclare\s+-A\b",
                        r"\blocal\s+-n\b", r"\|&", r"&>>", r"\bcoproc\b", r"\bdeclare\s+-n\b"):
            assert not re.search(lacking, code), (name, lacking)
        checked = subprocess.run([bash, "-n", str(REPO / name)], capture_output=True, text=True, check=False)
        assert checked.returncode == 0, (name, checked.stderr)


def test_every_mac_script_opens_in_its_own_folder_and_finds_tools_by_command_v():
    """SPEC-mac R16 (E-10 for bash): the first command is ``cd`` to the script's
    own folder, tools are found with ``command -v``, and before any is run PATH
    is cut to its absolute folders - bash looks in the current folder only for
    an empty or relative PATH entry, and this takes those out - so a file
    dropped beside the script named like python3, node, npm or git cannot run
    in its place. The block is one text in all three, so it is fixed in one."""
    tools = re.compile(r"\b(python3|node|npm|git|codesign|ditto|hdiutil|shasum|find|file)\b")
    blocks = set()
    for name in MAC_SCRIPTS:
        commands_ = _sh(name)
        assert commands_[0] == 'cd "$(dirname "$0")" || exit 1', name
        path_done = commands_.index("PATH=$clean_path")
        for line in commands_[1:path_done]:
            assert not tools.search(line), (name, line)
        assert any("command -v" in line for line in commands_[path_done:]), name
        blocks.add(_path_block(name))
    assert len(blocks) == 1


def test_the_path_block_drops_an_empty_or_relative_folder_and_keeps_the_rest():
    import subprocess

    from tests.conftest import child_env

    bash = _bash()
    block = _path_block(MAC_SETUP)
    # The suite's one way to build a child's environment (decision 185), though
    # this child is bash: the guard allows no other shape.
    run = subprocess.run([bash, "-c", block + '\nprintf %s "$PATH"'], capture_output=True, text=True, check=True,
                         env=child_env(PATH=":.:rel/bin:/usr/bin:/bin:"))
    assert run.stdout == "/usr/bin:/bin"


def test_the_mac_launcher_never_installs_and_says_when_setup_must_run():
    """Decision 191 for start.command: not even the word pip, no install of
    either kind, the lock tool's stamp checked first, and the one sentence
    the lock tool owns (its Mac form) when there is no private Python."""
    from tools.lockfiles import NOT_SET_UP_MAC

    launcher = read(MAC_LAUNCHER)
    assert "pip" not in launcher.lower()
    for line in _sh(MAC_LAUNCHER):
        assert not PIP_INSTALL.search(line) and not NPM_INSTALL.search(line), line
    assert ".venv/bin/python tools/lockfiles.py verify .venv" in launcher
    assert f'echo "{NOT_SET_UP_MAC}"' in launcher
    assert '[ -x ".venv/bin/python" ] || not_set_up' in launcher
    assert '[ -d "app/node_modules/electron" ] || not_set_up' in launcher
    # Started through Electron's own entry script, as the Windows launcher does.
    assert "node node_modules/electron/cli.js ." in launcher
    assert "npx" not in "\n".join(_sh(MAC_LAUNCHER))


def test_mac_setup_installs_by_hash_then_stamps_and_runs_the_after_install_step_last():
    """Decisions 169, 191 and 209 for setup.command: the venv is made fresh,
    both hash-checked installs are the reader's two steps in order, npm ci
    follows, the stamp comes after every install, and the after-install step
    is the last command - its failure said in the module's own words."""
    from tracker.after_install import SETUP_RETRY

    commands_ = _sh(MAC_SETUP)
    assert any(line.startswith("python3 -m venv --clear .venv") for line in commands_)
    installs = [i for i, line in enumerate(commands_) if PIP_INSTALL.search(line)]
    assert len(installs) == 2
    assert commands_[installs[0]].startswith('"$PY" -m pip install --require-hashes -r requirements.lock')
    assert commands_[installs[1]].startswith('"$PY" -m pip install --require-hashes --no-deps -r requirements-nodeps.lock')
    [npm] = [i for i, line in enumerate(commands_) if NPM_INSTALL.search(line)]
    assert "npm ci --no-audit --no-fund" in commands_[npm] and npm > installs[1]
    [stamp_at] = [i for i, line in enumerate(commands_) if '"$PY" tools/lockfiles.py stamp .venv' in line]
    [step] = [i for i, line in enumerate(commands_) if '-m tracker.after_install --reason setup' in line]
    assert stamp_at > max(installs) and stamp_at > npm and step > stamp_at
    assert not any(PIP_INSTALL.search(line) or NPM_INSTALL.search(line) for line in commands_[step:])
    assert f'echo "{SETUP_RETRY}"' in read(MAC_SETUP)


def test_mac_setup_and_build_ask_for_the_python_floor_pyproject_declares():
    """The floor is typed in the scripts as the interpreter's own test and as
    a sentence; pyproject.toml's ``requires-python`` is the one source."""
    floor = re.search(r'requires-python\s*=\s*">=([\d.]+)"', read("pyproject.toml")).group(1)
    for name in (MAC_SETUP, MAC_BUILD):
        text = read(name)
        assert f"Install Python {floor}+" in text, name
        assert f"sys.version_info < ({floor.replace('.', ', ')})" in text, name


def test_scripts_check_out_with_lf_and_execute():
    """SPEC-mac R16: bash reads a carriage return as part of the interpreter's
    name ("bad interpreter"), and Finder will not run a file that is not
    executable, so each script checks out LF (.gitattributes) with mode
    100755 (the index), and holds no carriage return at all."""
    import shutil
    import subprocess

    import pytest

    for name in MAC_SCRIPTS:
        assert b"\r" not in (REPO / name).read_bytes(), name
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH; the attribute and the mode cannot be asked")
    said = subprocess.run(["git", "check-attr", "eol", "--", *MAC_SCRIPTS], cwd=REPO,
                          capture_output=True, text=True, check=True).stdout.splitlines()
    assert said == [f"{name}: eol: lf" for name in MAC_SCRIPTS], said
    listed = subprocess.run(["git", "ls-files", "--stage", "--", *MAC_SCRIPTS], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout.splitlines()
    assert [(line.split()[0], line.split("\t")[1]) for line in listed] == [("100755", name) for name in sorted(MAC_SCRIPTS)]


def test_the_mac_build_runs_its_seven_steps_in_the_order_that_keeps_the_seal():
    """SPEC-mac R17: freeze, package, copy, BUILD-INFO, sign, check, image. The
    order is the claim: BUILD-INFO before signing (a file written after breaks
    the seal), signing before the image (an image of a broken seal is the app
    Apple silicon calls damaged), the seal verified before it, each inner
    Mach-O signed before the app that holds them, and the proof that no data
    folder's file is in the bundle before anything is imaged."""
    text = read(MAC_BUILD)
    marks = [text.index(f'echo "[{n}/7]') for n in range(1, 8)]
    assert marks == sorted(marks)
    freeze, package, copy_, info, sign, proof, image = (
        text[a:b] for a, b in zip(marks, [*marks[1:], len(text)], strict=True))
    assert "-m PyInstaller --noconfirm --clean" in freeze and "api_entry.spec" in freeze
    assert "electron-packager.mjs" in package and "--platform=\"$PLATFORM\" --arch=\"$ARCH\"" in package
    assert re.search(r'^PLATFORM=darwin$', text, re.M) and re.search(r'^ARCH=arm64$', text, re.M)
    assert 'ditto "$OUT/py/$API" "$APP/Contents/Resources/$API"' in copy_
    assert '> "$APP/Contents/Resources/BUILD-INFO.txt"' in info
    inner = sign.index('codesign --force --sign - "$file"')
    outer = sign.index('codesign --force --deep --sign - "$APP"')
    verify = sign.index('codesign --verify --deep --strict "$APP"')
    assert inner < outer < verify
    assert 'file -b "$file" | grep -q "Mach-O"' in sign
    assert 'hdiutil create -volname "$NAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG"' in image
    assert 'ln -s /Applications "$STAGE/Applications"' in image
    assert 'shasum -a 256 "$DMG_NAME" > "$DMG_NAME.sha256"' in image
    # Nothing after the signing alters the bundle: the proof only reads it and
    # the image only copies it.
    assert "codesign" not in image and "codesign" not in proof
    assert not re.search(r">\s*\"\$APP|\brm\b[^\n]*\$APP|\bditto\b[^\n]*\"\$APP/Contents", proof + image)


def test_the_mac_build_names_everything_from_package_json_and_the_pilots_version():
    """The product's and the API's names are package.json's, the version is
    pilot-content.js's (P13), the image is named as the installer is, and the
    app's identifier is the one the shell gives Windows (never typed twice)."""
    text = read(MAC_BUILD)
    package = json.loads(read("app/package.json"))
    assert "node -p \"require('./app/package.json').productName\"" in text
    assert "node -p \"require('./app/package.json').config.apiName\"" in text
    assert "node -p \"require('./app/renderer/pilot-content.js').edition.version\"" in text
    assert package["productName"] not in text and package["config"]["apiName"] not in text
    assert 'DMG_NAME="$(echo "$NAME" | tr \' \' \'-\')-$VER-mac-$ARCH.dmg"' in text
    setup_iss = read("pilot/installer/setup.iss")
    assert re.search(r"^OutputBaseFilename=" + re.escape(package["productName"].replace(" ", "-"))
                     + r"-Setup-\{#AppVersion\}$", setup_iss, re.M)
    identifier = re.search(r'^APP_ID="([^"]+)"$', text, re.M).group(1)
    assert f'setAppUserModelId("{identifier}")' in read("app/main.js")
    assert '--app-bundle-id="$APP_ID"' in text
    # The disk image is of a commit, refused otherwise, as the pilot installer is (P13).
    assert text.index("git rev-parse --verify HEAD") < text.index("git status --porcelain") < text.index(
        '"[1/7]')
    assert "Commit or discard your changes first" in text


def test_the_mac_build_reads_the_version_the_badge_shows():
    """The build's own node expression, run against the real pilot-content.js."""
    import shutil
    import subprocess

    import pytest

    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    expr = re.search(r"node -p \"(require\('\./app/renderer/pilot-content\.js'\)[^\"]*)\"", read(MAC_BUILD)).group(1)
    out = subprocess.run(["node", "-p", expr], cwd=REPO, capture_output=True, text=True, check=True)
    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", out.stdout.strip())


def test_the_mac_bundle_is_given_its_icon_floor_and_folder_strings():
    """The packager is given the .icns, the identifier and the plist; the
    plist holds Electron's own floor, below the app's (R6), and the three folder
    strings macOS shows when the clients folder sits in Desktop, Documents or
    Downloads."""
    import plistlib

    text = read(MAC_BUILD)
    assert "--icon=assets/icon.icns" in text and "--extend-info=assets/Info-mac.plist" in text
    assert (REPO / "app/assets/icon.icns").is_file() and (REPO / "app/assets/Info-mac.plist").is_file()
    info = plistlib.loads((REPO / "app/assets/Info-mac.plist").read_bytes())
    # Electron's own floor, not the app's: the bundle must let a Mac below the
    # app's floor (macOS 14) start, so the app can say its own sentence (R6);
    # only a Mac Electron cannot run on (macOS 12, dropped in Electron 44) is
    # refused by macOS itself.
    assert info["LSMinimumSystemVersion"] == ELECTRON_MACOS_FLOOR
    for folder in ("Desktop", "Documents", "Downloads"):
        sentence = info[f"NS{folder}FolderUsageDescription"]
        assert sentence.endswith(f"in your {folder} folder.") or sentence.endswith(f"on your {folder}.")
    assert set(info) == {"LSMinimumSystemVersion", "NSDesktopFolderUsageDescription",
                         "NSDocumentsFolderUsageDescription", "NSDownloadsFolderUsageDescription"}


def test_the_mac_build_info_sits_where_the_after_install_step_looks_in_a_bundle(tmp_path):
    """BUILD-INFO.txt is written to Contents/Resources, which is two folders
    above the frozen executable at Contents/Resources/<api>/<api>: exactly
    where ``after_install.build_info`` looks."""
    from tracker.after_install import BUILD_INFO_FILENAME, build_info

    text = read(MAC_BUILD)
    assert f'"$APP/Contents/Resources/{BUILD_INFO_FILENAME}"' in text
    assert 'ditto "$OUT/py/$API" "$APP/Contents/Resources/$API"' in text
    resources = tmp_path / "Console.app" / "Contents" / "Resources"
    executable = resources / "tracker-api" / "tracker-api"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    assert build_info(executable) is None
    (resources / BUILD_INFO_FILENAME).write_text("built", encoding="utf-8")
    assert build_info(executable) == resources / BUILD_INFO_FILENAME


def test_the_mac_build_proves_the_bundle_holds_no_store_log_task_file_or_settings(tmp_path):
    """SPEC-mac R17 step 6: the same names and patterns the Windows workflow
    checks (each spelled by the constant that owns it), and the check itself
    is run: a clean bundle passes and one holding any named file or a
    set-aside fails with the file's path."""
    import subprocess

    bash = _bash()
    text = read(MAC_BUILD)
    step = _between(text, 'echo "[6/7]', 'echo "[7/7]')
    names, patterns = data_home_names()
    listed = re.search(r"^names=\(([^)]*)\)$", step, re.M).group(1).split()
    listed_patterns = re.findall(r"'([^']+)'", re.search(r"^patterns=\(([^)]*)\)$", step, re.M).group(1))
    assert set(listed) == names and len(listed) == len(names)
    assert set(listed_patterns) == patterns

    def run(app) -> subprocess.CompletedProcess:
        script = 'fail() { echo "$1"; exit 1; }\nAPP="$1"\n' + step
        return subprocess.run([bash, "-c", script, "probe", str(app)], capture_output=True, text=True, check=False)

    clean = tmp_path / "Clean.app"
    (clean / "Contents" / "Resources" / "tracker-api").mkdir(parents=True)
    (clean / "Contents" / "Resources" / "BUILD-INFO.txt").write_text("x", encoding="utf-8")
    assert run(clean).returncode == 0
    for leaked in sorted(names | {"tracker.db.v3.old1", "record-heads.db.v7.old2"}):
        app = tmp_path / f"{leaked}.app"
        (app / "Contents" / "Resources").mkdir(parents=True)
        (app / "Contents" / "Resources" / leaked).write_text("x", encoding="utf-8")
        ran = run(app)
        assert ran.returncode == 1 and leaked in ran.stdout, (leaked, ran.stdout)


def test_the_mac_launcher_and_setup_sentences_are_the_ones_their_owners_say():
    """The sentences the scripts print are the modules' own, word for word
    (the Windows files are held the same way): the launcher's refusal is the
    lock tool's, setup's failure is the after-install module's."""
    from tools.lockfiles import NOT_SET_UP, NOT_SET_UP_MAC

    assert NOT_SET_UP_MAC == NOT_SET_UP.replace("Setup.bat", "setup.command")
    assert NOT_SET_UP_MAC in read(MAC_LAUNCHER)
