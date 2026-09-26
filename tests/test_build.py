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


def test_the_package_is_proved_to_hold_no_store_log_task_file_or_settings():
    """The proof (decision 186): a step before the package is zipped and
    uploaded fails the build when anything in it bears a name the data
    home or the settings folder holds - each spelled by its constant."""
    from tracker.runner import LOG_FILENAME, PASS_ORDER_FILENAME
    from tracker.scheduling import SCHEDULE_XML_FILENAME
    from tracker.settings import DATA_HOME_NAME, OCR_SCRATCH_DIRNAME, SETTINGS_FILENAME
    from tracker.store import STORE_FILENAME, STORE_SHM_FILENAME, STORE_WAL_FILENAME

    run = commands()
    step = run.index("- name: The package holds no store, run log, task file or settings")
    assert step < run.index("- name: Zip the package and publish its SHA-256") < run.index(
        "- name: Upload the package")
    body = run[step:run.index("- name: Zip the package and publish its SHA-256")]
    listed = re.search(r"\$names = @\(([^)]*)\)", body).group(1)
    assert set(re.findall(r"'([^']+)'", listed)) == {
        STORE_FILENAME, STORE_WAL_FILENAME, STORE_SHM_FILENAME, LOG_FILENAME, PASS_ORDER_FILENAME,
        SCHEDULE_XML_FILENAME, OCR_SCRATCH_DIRNAME, DATA_HOME_NAME, SETTINGS_FILENAME}
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
    windows = re.search(r"^\s*if: (.+)$", ci.split("\n  windows:\n", 1)[1], re.M).group(1)
    # The conditions are pinned whole, not by fragments: the same pieces in
    # another order (`A || B && C`) would say something else.
    assert linux == (                                                 # main, or a ready non-draft PR; never a label
        "github.event_name == 'push' || "
        "(github.event.action == 'ready_for_review' && github.event.pull_request.draft == false)")
    assert windows == (                                               # a ready PR that asked; never main
        "github.event_name == 'pull_request' && github.event.pull_request.draft == false"
        " && contains(github.event.pull_request.labels.*.name, 'windows')"
        " && (github.event.action == 'ready_for_review' || github.event.label.name == 'windows')")
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

    # The rule, on the freeze of 09/17.
    old = ("Commit:   a1d261b\n\nPython packages frozen (pip freeze):\n"
           + "\n".join(f"{name}=={version}" for name, version in pinned.items()
                       if name != "pypdfium2") + "\npypdfium2==5.13.0\n")
    assert drift(frozen_in(old), pinned) == ["pypdfium2: froze 5.13.0, the locks say 5.11.0"]
    assert drift({**pinned, "pandas": "3.0"}, pinned) == ["pandas: froze 3.0, the locks say nothing"]
    assert drift(dict(pinned), pinned) == []

    # And on whatever this checkout last built: the build's own markers.
    built = locked(BUILD_ENVIRONMENT)
    for info in (REPO / "build-portable" / "dist").glob("*/BUILD-INFO.txt"):
        frozen = frozen_in(info.read_text(encoding="utf-8", errors="replace"))
        assert frozen, info
        assert drift(frozen, built) == [], info


# ---------------------------------- decision 169: the reader, installed in two steps ----

#: The file holding rapidocr alone, installed with --no-deps (R-11).
NODEPS = "requirements-nodeps.txt"
#: The step every install of the tree makes after requirements.txt.
NODEPS_STEP = re.compile(r"pip install --require-hashes --no-deps -r requirements-nodeps\.lock")
#: The first step: the whole tree, from its lock, in hash mode.
TREE_STEP = re.compile(r"pip install --require-hashes -r requirements\.lock")
SETUP_SCRIPT = "Setup.bat"
LAUNCHER = "Start App.bat"


def batch_files() -> list[str]:
    return sorted(path.name for path in REPO.glob("*.bat"))


def installing_places() -> dict[str, str]:
    """Every file that installs the tree, by name: the batch files and each
    workflow that runs ``pip install``."""
    places = {name: read(name) for name in (BUILD_SCRIPT, SETUP_SCRIPT)}
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
    assert {BUILD_SCRIPT, SETUP_SCRIPT, GATE_WORKFLOW, BUILD_WORKFLOW} <= set(places)
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
    sources = {name: read(name) for name in batch_files()}
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
    assert seen >= 8                                   # Setup, the build, the pack, gate and build workflows


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
