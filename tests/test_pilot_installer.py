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


def test_uninstalling_never_deletes_client_or_tracker_data():
    text = _setup()
    sections = _sections(text)
    assert "UninstallDelete" not in sections
    assert "InstallDelete" not in sections
    # The comments may say what uninstall leaves alone; the script itself never names it.
    code = "\n".join(sections.values())
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
    assert "OutputBaseFilename=Tax-Document-Tracker-Pilot-Setup-{#AppVersion}" in setup
    assert "UninstallDisplayName=" + name + " {#AppVersion}" in setup
    assert re.search(r"^AppId=\{\{[0-9A-F-]{36}\}$", setup, re.MULTILINE)
    files = _sections(_setup())["Files"]
    assert 'Source: "{#SourceDir}\\*"; DestDir: "{app}"' in files
    assert f'{{app}}\\{name}.exe' in _sections(_setup())["Icons"]


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
