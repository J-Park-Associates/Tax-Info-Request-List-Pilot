"""The pilot's installer script and its build script (pilot SPEC section 10).

Both are text, so these tests read them as text: Inno Setup and Windows are
not needed to check the claims that keep a tester's data safe - installs for
one user, uninstall removes the schedule it registered and never touches
client or tracker data, the build refuses uncommitted work. No module owns
this file; the pilot's decisions are in ``pilot/DECISIONS.md`` (P4, P12, P13).
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SETUP = REPO / "pilot" / "installer" / "setup.iss"
BUILD = REPO / "pilot" / "Build Pilot Installer.bat"
UPSTREAM_DATA_HOME_NAME = "tax-document-tracker"
#: The firm's production product (R8 of pilot/SPEC-rename.md): never named by
#: the installer or the check scripts, which name only the pilot's earlier name.
UPSTREAM_PRODUCT_NAME = "Tax Document Tracker"
#: How an upgrade finds the copy it replaces: never changes (P155, R2).
APP_ID = "AppId={{27812DF2-05B3-4844-81BA-E58F49D2BD7D}"
WINTEST = REPO / "pilot" / "wintest"


def _setup() -> str:
    return SETUP.read_text(encoding="utf-8")


def _build() -> str:
    return BUILD.read_text(encoding="utf-8")


def _sections(text: str) -> dict[str, str]:
    """The script's ``[Section]`` bodies by name, comments left out."""
    found: dict[str, list[str]] = {}
    current = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(";"):
            continue
        match = re.fullmatch(r"\[(\w+)\]", line)
        if match:
            current = match.group(1)
            found[current] = []
        elif current and line:
            found[current].append(line)
    return {name: "\n".join(lines) for name, lines in found.items()}


def _product_name() -> str:
    return json.loads((REPO / "app" / "package.json").read_text(encoding="utf-8"))["productName"]


def test_the_installer_installs_for_one_user_without_admin():
    assert re.search(r"^PrivilegesRequired=lowest$", _sections(_setup())["Setup"], re.MULTILINE)


def test_uninstalling_removes_the_schedule_it_ran():
    from tracker import scheduling

    task = scheduling.TASK_NAME
    assert task == _product_name()
    run = _sections(_setup())["UninstallRun"]
    assert "schtasks.exe" in run
    assert f'/Delete /TN ""{task}"" /F' in run
    assert "RunOnceId" in run


def test_uninstalling_removes_the_task_under_either_name():
    """An upgrade's first start removes the earlier name's task (P155), but a
    PC uninstalled before the app ever started again still has it: the
    uninstaller removes the task under both names, each once."""
    from tracker import scheduling, settings

    run = _sections(_setup())["UninstallRun"].splitlines()
    for name, once in ((scheduling.TASK_NAME, "RemoveSchedule"),
                       (settings.EARLIER_PRODUCT_NAME, "RemoveEarlierSchedule")):
        [line] = [line for line in run if f'/Delete /TN ""{name}"" /F' in line]
        assert f'RunOnceId: "{once}"' in line
    assert len(run) == 2


def test_uninstalling_never_deletes_client_or_tracker_data():
    text = _setup()
    sections = _sections(text)
    assert "UninstallDelete" not in sections
    # The comments may say what uninstall leaves alone; the script itself never
    # names it. [InstallDelete] names only the earlier name's own files (its
    # own test, below).
    code = "\n".join(body for name, body in sections.items() if name != "InstallDelete")
    for name in ("tax-document-tracker-pilot", UPSTREAM_DATA_HOME_NAME, "settings.json"):
        assert name not in code, name
    assert not re.search(r"\bdel(ete)?\b", code.replace("/Delete /TN", ""), re.IGNORECASE)


def test_the_installer_needs_a_version_to_compile():
    text = _setup()
    assert re.search(r"^#ifndef AppVersion\s*\n\s*#error", text, re.MULTILINE)
    assert re.search(r"^#ifndef SourceDir\s*\n\s*#error", text, re.MULTILINE)


def test_the_installer_is_named_and_placed_as_the_spec_says():
    setup = _sections(_setup())["Setup"]
    name = _product_name()
    assert f"AppName={name}" in setup
    assert f"DefaultDirName={{localappdata}}\\Programs\\{name}" in setup
    assert "OutputBaseFilename=" + name.replace(" ", "-") + "-Setup-{#AppVersion}" in setup
    assert "UninstallDisplayName=" + name + " {#AppVersion}" in setup
    assert re.search(r"^AppId=\{\{[0-9A-F-]{36}\}$", setup, re.MULTILINE)
    files = _sections(_setup())["Files"]
    assert 'Source: "{#SourceDir}\\*"; DestDir: "{app}"' in files
    assert f'{{app}}\\{name}.exe' in _sections(_setup())["Icons"]


def test_an_upgrade_installs_over_the_earlier_copy_in_its_own_folder():
    """R2: the AppId never changes and UsePreviousAppDir stays at Inno Setup's
    default (yes), so a PC that has the earlier name is upgraded in place,
    where its settings.json already is; only a new install uses the new
    folder."""
    setup = _sections(_setup())["Setup"]
    assert APP_ID in setup.splitlines()
    assert "UsePreviousAppDir" not in setup


def test_the_start_menu_takes_the_new_name_on_an_upgrade():
    """R7: an upgrade would otherwise keep the earlier Start menu folder."""
    assert "UsePreviousGroup=no" in _sections(_setup())["Setup"].splitlines()


def test_an_upgrade_removes_exactly_the_earlier_shortcuts_and_program_file():
    """R7: the earlier Start menu shortcut, its folder when empty, the earlier
    desktop icon and the earlier program file - by exact path, never a
    wildcard, so nothing else in the Start menu or on the desktop can match."""
    from tracker.settings import EARLIER_PRODUCT_NAME as old

    lines = _sections(_setup())["InstallDelete"].splitlines()
    assert lines == [
        f'Type: files; Name: "{{app}}\\{old}.exe"',
        f'Type: files; Name: "{{userprograms}}\\{old}\\{old}.lnk"',
        f'Type: dirifempty; Name: "{{userprograms}}\\{old}"',
        f'Type: files; Name: "{{userdesktop}}\\{old}.lnk"',
    ]
    assert not any(wild in line for line in lines for wild in "*?")


def test_every_copy_of_the_earlier_name_matches_the_one_in_settings():
    """R1: the earlier name has one home, settings.EARLIER_PRODUCT_NAME; the
    places that cannot import Python type it, and each copy is that one. R8:
    none of them ever names the firm's production product, whose name is
    the earlier one without "Pilot"."""
    from tracker.settings import EARLIER_PRODUCT_NAME as old

    config = json.loads((REPO / "app" / "package.json").read_text(encoding="utf-8"))["config"]
    assert config["userDataName"] == old
    for script in ("run_checks.ps1", "uninstall_checks.ps1"):
        text = (WINTEST / script).read_text(encoding="utf-8")
        assert re.findall(r'^\$EarlierName = "([^"]*)"$', text, re.MULTILINE) == [old], script
    for path in (SETUP, WINTEST / "run_checks.ps1", WINTEST / "uninstall_checks.ps1"):
        text = path.read_text(encoding="utf-8")
        named = re.findall(re.escape(UPSTREAM_PRODUCT_NAME) + r"(?: Pilot)?", text)
        assert named and set(named) == {old}, path.name


def test_the_pilot_build_names_the_installer_as_setup_iss_does():
    base = re.search(r"^OutputBaseFilename=(.+)-\{#AppVersion\}$", _sections(_setup())["Setup"],
                     re.MULTILINE).group(1)
    named = re.findall(r"installer\\([^\\\s\"]+)-%VER%\.exe", _build())
    assert named == [base]


def test_the_desktop_icon_is_offered_but_not_ticked():
    tasks = _sections(_setup())["Tasks"]
    assert "desktopicon" in tasks and "Flags: unchecked" in tasks


def test_the_pilot_build_refuses_what_is_not_committed():
    text = _build()
    check = text.index("git status --porcelain")
    refusal = text.index("Commit or discard your changes first", check)
    assert "exit /b 1" in text[refusal:refusal + 200]
    assert text.index("Build App.bat\"", check) > refusal      # refused before anything is built


def test_the_pilot_build_checks_it_is_a_git_checkout_before_the_dirty_check():
    text = _build()
    verify = text.index("git rev-parse --verify HEAD")
    assert verify < text.index("git status --porcelain")
    assert "not a git checkout, or git is not installed" in text[verify:text.index("git status --porcelain")]


def test_the_pilot_build_follows_the_root_scripts_rules():
    text = _build()
    commands = [line for line in text.splitlines() if line.strip() and not line.lower().startswith("rem")]
    assert commands[0] == "@echo off"
    assert commands[1] == 'set "NoDefaultCurrentDirectoryInExePath=1"'
    assert 'call ".\\Build App.bat"' in text
    assert "require('./app/renderer/pilot-content.js').edition.version" in text
    assert "%SystemRoot%\\System32\\certutil.exe" in text
    mentions = re.findall(r"[^\n]*\bv\d[^\n]*|[^\n]*never v[^\n]*", text)
    assert mentions == ["echo Tag this commit pilot-%VER% (never v...)"]


def test_the_tester_guide_names_the_pilot_folders_it_leaves_alone():
    guide = (REPO / "pilot" / "Tester Guide.md").read_text(encoding="utf-8")
    assert "admin@jparkassociates.com" in guide
    assert "%LOCALAPPDATA%\\tax-document-tracker-pilot" in guide
    assert "More info" in guide and "Run anyway" in guide
    assert f"Apps -> {_product_name()}" not in guide            # said in words, not arrows
    assert _product_name() in guide


def test_the_version_the_build_reads_is_the_one_the_badge_shows():
    """The .bat's own node expression, run against the real pilot-content.js,
    gives a plain version number (review 1, finding 4)."""
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    expr = re.search(r"node -p \"(require\('\./app/renderer/pilot-content\.js'\)[^\"]*)\"", _build()).group(1)
    out = subprocess.run(["node", "-p", expr], cwd=REPO, capture_output=True, text=True, check=True)
    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", out.stdout.strip())


def test_every_batch_file_the_pilot_build_calls_is_named_by_its_path():
    """With NoDefaultCurrentDirectoryInExePath set, cmd will not find a batch
    file named bare, even in its own folder: the pilot's Windows check found
    ``call "Build App.bat"`` failing on every PC (P29). Every call of a
    batch file names its folder."""
    calls = re.findall(r'^\s*call\s+"([^"]+\.bat)"', _build(), re.M | re.I)
    assert calls, "the build calls Build App.bat"
    assert all(c.startswith((".\\", "%~dp0")) for c in calls), calls


def test_the_installer_shows_the_console_icon():
    """SetupIconFile, both wizard images (seven scalings each, smallest first)
    and the uninstall entry's icon: every file named exists."""
    setup = dict(line.split("=", 1) for line in _sections(_setup())["Setup"].splitlines() if "=" in line)
    folder = SETUP.parent

    def on_disk(name: str) -> Path:
        return folder / name.replace("\\", "/")      # the script's paths are Windows'

    assert on_disk(setup["SetupIconFile"]).is_file()
    for key, stem in (("WizardImageFile", "wizard-large"), ("WizardSmallImageFile", "wizard-small")):
        named = setup[key].split(",")
        assert [n.rsplit("\\", 1)[-1] for n in named] == [f"{stem}-{i}.bmp" for i in range(1, 8)], key
        for name in named:
            assert on_disk(name).is_file(), name
    assert setup["UninstallDisplayIcon"] == f"{{app}}\\{_product_name()}.exe"


def test_the_shortcuts_and_the_window_share_one_app_id():
    """Windows groups taskbar buttons by app id: a shortcut and the running
    process that name different ids show as two buttons, so every [Icons] line
    carries the id app/main.js gives the process."""
    main = (REPO / "app" / "main.js").read_text(encoding="utf-8")
    found = re.search(r'setAppUserModelId\("([^"]+)"\)', main)
    assert found, "app/main.js no longer sets an app user model id"
    icons = [line for line in _sections(_setup())["Icons"].splitlines() if line.strip()]
    assert icons
    for line in icons:
        assert f'AppUserModelID: "{found.group(1)}"' in line, line


def test_the_pilot_installer_makes_the_overview_ready_before_it_launches_the_app():
    """Q1 of the speed round (Jason, 2026-10-08: "Yes, add to pilot"): the
    pilot's installer runs the after-install step through its setup door,
    so a tester's first Overview is warm. The packaged API is started in
    its setup mode with the settings folder (the installed folder, where
    the shell keeps settings.json) and the product's name, hidden and waited
    for, before the launch entry - and not as a postinstall entry, so a
    silent install runs it too."""
    from tracker.runner import PRODUCT_FLAG, SETTINGS_FLAG, SETUP_MODE_FLAG

    package = json.loads((REPO / "app" / "package.json").read_text(encoding="utf-8"))
    api = package["config"]["apiName"]
    entries = _sections(_setup())["Run"].splitlines()
    step, launch = entries
    assert step.startswith(f'Filename: "{{app}}\\resources\\{api}\\{api}.exe";')
    parameters = re.search(r'Parameters: "((?:[^"]|"")*)"', step).group(1).replace('""', '"')
    assert parameters == f'{SETUP_MODE_FLAG} {SETTINGS_FLAG} "{{app}}" {PRODUCT_FLAG} "{_product_name()}"'
    flags = set(re.search(r"Flags: ([\w ]+)$", step).group(1).split())
    assert flags == {"runhidden", "waituntilterminated"}
    assert "postinstall" in launch and "Tax Document Console.exe" in launch


def test_the_packaged_setup_mode_is_the_entrys_own_door():
    """The flag the installer passes is the one ``api_entry.py`` reads,
    before the API - and with it the task name - is imported."""
    from tracker.runner import SETUP_MODE_FLAG

    entry = (REPO / "api_entry.py").read_text(encoding="utf-8")
    assert "if argv[:1] == [SETUP_MODE_FLAG]:" in entry
    assert entry.index("[SETUP_MODE_FLAG]:") < entry.index("from tracker.api import main")
    assert SETUP_MODE_FLAG in _setup()
