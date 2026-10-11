"""The pilot edition's badge, terms screen and wording (pilot SPEC sections 4, 5, 7, 9).

The wording lives in ``app/renderer/pilot-content.js`` between two marker
lines as plain JSON, so these tests read it with ``json.loads`` exactly as
the installer build reads it with node. The renderer files are read as text:
they run in a sandboxed window, so what can be pinned is what they may and
may not contain.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RENDERER = REPO / "app" / "renderer"
PILOT_JS = ("pilot-content.js", "pilot.js", "tour.js")


def read(name: str) -> str:
    return (RENDERER / name).read_text(encoding="utf-8")


def content() -> dict:
    text = read("pilot-content.js")
    begin, end = "// PILOT-CONTENT-BEGIN\n", "// PILOT-CONTENT-END"
    assert text.count(begin) == 1 and text.count(end) == 1
    return json.loads(text.split(begin)[1].split(end)[0])


def tour_lines(content_: dict):
    """One line per step (SPEC-shell 12): the strength, limit and fallback
    lines and the stage chips are gone."""
    for step in content_["tour"]["steps"]:
        assert set(step) == {"id", "anchors", "title", "does"}, step["id"]
        assert isinstance(step["does"], str), step["id"]
        yield step["does"]


def test_the_pilot_content_is_json_between_its_markers():
    data = content()
    assert set(data) == {"edition", "contact", "terms", "tour"}
    assert set(data["tour"]) == {"steps"}


def test_the_edition_version_is_a_plain_version_number():
    version = content()["edition"]["version"]
    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", version), version
    assert content()["edition"]["label"]


def test_the_terms_have_every_field_and_a_positive_version():
    terms = content()["terms"]
    assert isinstance(terms["version"], int) and terms["version"] >= 1
    for key in ("title", "checkbox", "sign", "accept", "signed", "quit", "close"):
        assert isinstance(terms[key], str) and terms[key].strip(), key
    assert terms["sections"]


def test_every_terms_section_has_a_heading_and_bullets():
    for section in content()["terms"]["sections"]:
        assert section["heading"].strip()
        assert section["bullets"] and all(b.strip() for b in section["bullets"])


def test_the_contact_is_the_firms_admin_address():
    assert content()["contact"]["email"] == "admin@jparkassociates.com"


def test_every_line_of_copy_is_short():
    data = content()
    lines = [b for s in data["terms"]["sections"] for b in s["bullets"]]
    long = [line for line in lines if len(line.split()) > 30]
    assert not long, long


def test_every_tour_line_is_five_words_or_fewer():
    """P63: five words. The terms are the one exception, shown whole (P20)."""
    long = [line for line in tour_lines(content()) if len(line.split()) > 5]
    assert not long, long


def test_the_page_loads_the_pilot_after_the_app():
    html = read("index.html")
    assert html.index("pilot-style.css") > html.index('href="style.css"')
    order = [html.index(f'src="{name}"') for name in ("app.js", *PILOT_JS)]
    assert order == sorted(order)


def test_the_pilot_files_build_the_page_only_with_text():
    banned = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write",
              "eval(", "new Function", "startsWith(")
    for name in PILOT_JS:
        text = read(name)
        assert not [b for b in banned if b in text], name


def test_the_pilot_never_types_the_product_name():
    product = json.loads((REPO / "app" / "package.json").read_text(encoding="utf-8"))["productName"]
    # The approved terms' first bullet names the product (P155, Q1 of
    # SPEC-rename: "A test edition of Tax Document Console, built by ..."):
    # the terms a tester accepts are firm wording, kept word for word, so
    # that is the one place the pilot says the name, exactly once.
    approved = f"A test edition of {product}, built by J Park & Associates."
    content = read("pilot-content.js")
    assert content.count(product) == 1 and approved in content
    for name in (*PILOT_JS, "pilot-style.css"):
        assert product not in read(name).replace(approved, ""), name


def test_the_terms_cannot_be_escaped():
    js = read("pilot.js")
    assert re.search(r'addEventListener\("keydown",\s*\w+,\s*true\)', js)
    assert '"Escape"' in js
    assert "DIALOGS" not in js.replace("app.js's DIALOGS", "")


def test_the_pilot_style_targets_only_its_own_names():
    css = re.sub(r"/\*.*?\*/", "", read("pilot-style.css"), flags=re.S)
    css = re.sub(r"@media[^{]*\{", "", css)
    selectors = [s.strip() for block in re.findall(r"([^{}]+)\{", css) for s in block.split(",")]
    allowed = (".pilot-", "#pilot-")
    assert selectors and all(s.startswith(allowed) for s in selectors), selectors


def test_acceptance_is_asked_of_the_durable_record_before_the_terms_stay():
    """P46: the window's storage is only a cache. A launch whose cache says
    nothing - storage that could not be opened reads as nothing - asks the
    tracker's own record, through the one channel the page has, and the
    terms go when it holds this version's acceptance."""
    import tracker.api as api

    js = read("pilot.js")
    assert 'const COMMAND = "pilot-record";' in js and "pilot-record" in api.COMMANDS
    assert "window.tracker.call([COMMAND], payload)" in js
    # The shell allows it only once the page's first call named the commands.
    assert "vocab.commands.indexOf(COMMAND)" in js
    shown = js.index("document.body.appendChild(overlay);")
    asked = js.index("PilotRecord.read().then((record) => {", shown)
    assert "record.terms !== version" in js[asked:] and "close();" in js[asked:]
    # Accepting records it durably, not only in the cache.
    accepted = js[js.index('accept.addEventListener("click"'):]
    assert "PilotRecord.acceptTerms(version, signedBy());" in accepted.split("});")[0]
    # Storage is touched in one place only.
    assert js.count("window.localStorage.") == 2


def test_the_tour_is_remembered_through_the_pilot_record():
    tour = read("tour.js")
    assert "PilotRecord.tourSeen();" in tour and "localStorage" not in tour
    assert "tourSeen: () => {" in read("pilot.js")


def test_the_shell_writes_the_pages_storage_as_the_window_closes():
    """P46: flushed at close, not left to the end of a shutdown a quick
    restart can overtake."""
    main = (REPO / "app" / "main.js").read_text(encoding="utf-8")
    assert 'win.on("close", () => win.webContents.session.flushStorageData());' in main
    assert "app.requestSingleInstanceLock()" in main


def test_windows_contrast_themes_are_honoured_without_touching_the_normal_look():
    """Microsoft's contrast-theme guidance: a forced-colors block keeps edges and focus."""
    for name in ("style.css", "pilot-style.css"):
        css = read(name)
        block = re.search(r"@media \(forced-colors: active\) \{(.*)\n\}\n?$", css, flags=re.S)
        assert block, f"the forced-colors block must be the last rule of {name}"
        inner = block.group(1)
        assert "CanvasText" in inner or "Highlight" in inner
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", inner), "system colours only"
        assert "glass" not in css and "backdrop-filter" not in css


def test_the_badge_sits_in_the_side_panels_foot_and_there_is_no_tour_button():
    """SPEC-shell 12: the badge moves to #side-foot; Help > Take the tour
    starts the tour (the menu id `tour`), so the page has no Tour button."""
    js = read("pilot.js")
    assert 'document.getElementById("side-foot")' in js
    assert "btn-tour" not in js and "btn-tour" not in read("index.html")
    assert "PilotTour.start()" in read("shell.js") and "PilotTerms.show()" in read("shell.js")
    assert 'id="side-foot"' in read("index.html")


def test_help_terms_shows_the_same_card_read_only_with_one_close():
    js = read("pilot.js")
    shown = js[js.index("function show() {"):js.index("function gate() {")]
    code = re.sub(r"//[^\n]*", "", shown)
    assert "build(true)" in code and "close" in code
    assert not re.search(r"\b(?:agree|accept|quit)\b", code) and "window.close" not in code
    assert '"close": "Close"' in read("pilot-content.js")


def _gate() -> str:
    js = read("pilot.js")
    return re.sub(r"//[^\n]*", "", js[js.index("function gate() {"):js.index("return { show, gate };")])


def test_the_accept_button_waits_for_a_typed_name():
    """P188: the terms card gains one box, "Type Your Full Name to Sign",
    and "Sign and Accept" stays disabled until the box holds a name - the
    sign-off is part of accepting, not an extra."""
    terms = content()["terms"]
    assert terms["sign"] == "Type Your Full Name to Sign" and terms["accept"] == "Sign and Accept"
    js = read("pilot.js")
    built = js[js.index("function build(readOnly) {"):js.index("function holdKeys(")]
    assert 'make("span", "", terms.sign)' in built
    assert 'name.id = "pilot-terms-name";' in built and 'name.setAttribute("type", "text");' in built
    assert built.index("card.appendChild(field);") < built.index("card.appendChild(actions);")
    assert 'accept.setAttribute("disabled", "");' in built
    gate = _gate()
    assert "const ready = () => agree.checked && signedBy() !== \"\";" in gate
    assert gate.count("accept.disabled = !ready();") == 2        # the box and the name each re-ask
    assert 'name.addEventListener("input"' in gate
    assert "[agree, name, quit, accept]" in gate                  # Tab reaches the name box


def test_a_blank_or_spaces_only_name_does_not_enable_accept():
    """A name is what is left once the spaces are trimmed; spaces alone are
    no name, and a click that somehow arrives without one does nothing."""
    gate = _gate()
    assert "const signedBy = () => name.value.trim();" in gate
    clicked = gate[gate.index('accept.addEventListener("click"'):]
    assert clicked.split("\n")[1].strip() == "if (!ready()) return;"


def test_the_signed_name_is_sent_with_the_acceptance():
    """The trimmed name travels with the acceptance to the durable record,
    as ``signed_by`` beside ``terms`` - the one shape the api takes."""
    js = read("pilot.js")
    clicked = _gate()[_gate().index('accept.addEventListener("click"'):]
    assert "PilotRecord.acceptTerms(version, signedBy());" in clicked.split("});")[0]
    record = js[js.index("acceptTerms: (version, signedBy) => {"):js.index("cacheTerms:")]
    assert "{ terms: version, signed_by: signedBy }" in record


def test_help_terms_shows_who_signed_and_when():
    """Help, Terms shows "Signed by {name} on {date}" when the record holds a
    name, the date in full with its year (``signedDay``: a sign-off carries a
    full date, and the app's short ``pagesDay`` drops the year), and the name
    set as text, never HTML; the line is attached only once there is a name,
    never hidden and shown; the read-only card has no name box and no sign
    button."""
    assert content()["terms"]["signed"] == "Signed by {name} on {date}"
    js = read("pilot.js")
    shown = re.sub(r"//[^\n]*", "", js[js.index("function show() {"):js.index("function gate() {")])
    assert "PilotRecord.read().then((record) => {" in shown
    assert "record.terms_signed_by" in shown and "signedDay(record.terms_accepted_at)" in shown
    assert "pagesDay" not in shown
    assert "if (!name || !day || !overlay.isConnected) return;" in shown
    assert 'signed.textContent = PILOT.terms.signed.split("{date}").join(day).split("{name}").join(name);' in shown
    assert "actions.before(signed);" in shown
    assert "pilot-terms-name" not in shown and "terms.sign" not in shown.replace("terms.signed", "")
    day = js[js.index("function signedDay(iso) {"):js.index("function show() {")]
    assert 'year: "numeric", month: "long", day: "numeric"' in day


def test_an_earlier_acceptance_without_a_name_is_not_asked_again():
    """P188 Q2 (a): a tester who accepted version 1 before the sign-off is
    not asked again. The terms version stays 1 (P187), the gate asks the
    record only for the version, and the cache's level-up sends no name, so
    none is ever recorded that was not typed."""
    assert content()["terms"]["version"] == 1
    gate = _gate()
    assert "terms_signed_by" not in gate and "signed_by" not in gate
    cached = gate[gate.index("if (PilotRecord.termsCached(version)) {"):gate.index("const { overlay")]
    assert "if (record && record.terms !== version) PilotRecord.acceptTerms(version);" in cached
    asked = gate[gate.index("PilotRecord.read().then((record) => {", gate.index("document.body.appendChild")):]
    assert "if (!record || record.terms !== version || !overlay.isConnected) return;" in asked


POWERSHELL = shutil.which("powershell.exe") if sys.platform == "win32" else None


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell 5.1 is the Windows check's shell")
def test_the_check_script_splits_a_comma_joined_test_list_and_reads_each_exit_code(tmp_path):
    """P128 (Windows check A1, A2): ``powershell -File`` hands ``-Tests a,b``
    over as one value, and Windows PowerShell 5.1 gives a ``Start-Process
    -PassThru`` process no exit code unless its handle was read while it ran.
    The script's own helpers, lifted as they are and run in 5.1, split the
    list and read back 0 for a passing file and 3 for another."""
    script = (REPO / "pilot" / "wintest" / "run_checks.ps1").read_text(encoding="utf-8")
    begin, end = "# BEGIN test-file helpers\n", "# END test-file helpers"
    assert script.count(begin) == 1 and script.count(end) == 1
    helpers = script.split(begin)[1].split(end)[0]
    assert "$Tests = Split-TestList $Tests" in script and "Start-TestFile $vpy $file $out" in script
    # A fake "pytest": a module the helper's `-m pytest` finds first, exiting
    # with the number the file names.
    (tmp_path / "pytest.py").write_text(
        "import sys\nraise SystemExit(int(open(sys.argv[-1]).read()))\n", encoding="utf-8")
    (tmp_path / "pass.txt").write_text("0", encoding="utf-8")
    (tmp_path / "fail.txt").write_text("3", encoding="utf-8")
    driver = tmp_path / "drive.ps1"
    driver.write_text(helpers + """
$here, $python = $args[0], $args[1]
Set-Location $here
[string[]]$files = Split-TestList @("pass.txt, fail.txt")
$procs = @($files | ForEach-Object { Start-TestFile $python $_ (Join-Path $here ("out-" + $_)) })
Start-Sleep -Milliseconds 500
$codes = @($procs | ForEach-Object { $_.WaitForExit(); "$($_.ExitCode)" })
"$($files.Count)|$($files -join ';')|$($codes -join ';')"
""", encoding="utf-8")
    done = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(driver),
                           str(tmp_path), sys.executable],
                          capture_output=True, text=True, timeout=120, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().splitlines()[-1] == "2|pass.txt;fail.txt|0;3", done.stdout + done.stderr


def _helpers(name: str) -> str:
    """One BEGIN/END block of run_checks.ps1, lifted as it is."""
    script = (REPO / "pilot" / "wintest" / "run_checks.ps1").read_text(encoding="utf-8")
    begin, end = f"# BEGIN {name} helpers\n", f"# END {name} helpers"
    assert script.count(begin) == 1 and script.count(end) == 1
    return script.split(begin)[1].split(end)[0]


def _run_ps(driver: Path, *args: str) -> str:
    done = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(driver), *args],
                          capture_output=True, text=True, timeout=120, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout.strip().splitlines()[-1]


def test_the_check_script_builds_only_after_every_named_test_file_has_ended():
    """P200, A1: the build writes build-portable into the checkout, and the
    suite's end-of-run guard (decision 185) fails any file still running when
    a new folder appears there. So every test process is waited for, and its
    verdict recorded, before the build starts."""
    script = (REPO / "pilot" / "wintest" / "run_checks.ps1").read_text(encoding="utf-8")
    waited = script.index("$r.Proc.WaitForExit()")
    recorded = script.index('Record ("tests " + $r.File)')
    build = script.index(r'Run "cmd.exe" @("/c", "pilot\Build Pilot Installer.bat")')
    assert script.count("$r.Proc.WaitForExit()") == 1 and script.count("Build Pilot Installer.bat\")") == 1
    assert waited < recorded < build


def test_the_check_script_closes_only_the_app_and_never_forces_it_before_installing():
    """P200, N7: an open app makes the silent install abort and roll back, so
    the app is asked to close first, and the script stops if it does not.
    Nothing in the script kills a process."""
    script = (REPO / "pilot" / "wintest" / "run_checks.ps1").read_text(encoding="utf-8")
    assert "Stop-Process" not in script and ".Kill(" not in script and "taskkill" not in script.lower()
    assert "/FORCECLOSEAPPLICATIONS" not in script
    close = script.index("$stillOpen = Close-App $appExes 30")
    install = script.index('Start-Process -FilePath $setup.FullName')
    assert close < install
    assert script.index('Stop-Here "close $ProductName', close) < install


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell 5.1 is the Windows check's shell")
def test_the_check_script_takes_a_test_file_by_bare_name_by_file_name_or_by_path(tmp_path):
    """P200, N8: ``-Tests test_build`` once stopped with "no such test file".
    The script's resolver, lifted as it is and run in 5.1, finds the same
    file from each way of naming it, and nothing for a name that is not one."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_build.py").write_text("", encoding="utf-8")
    driver = tmp_path / "drive.ps1"
    driver.write_text(_helpers("test-file") + r"""
Set-Location $args[0]
$found = @("test_build", "test_build.py", "tests\test_build.py", "tests/test_build", "test_none") |
         ForEach-Object { $f = Resolve-TestFile $_; if ($f) { (Resolve-Path $f).Path } else { "none" } }
$found -join "|"
""", encoding="utf-8")
    want = str(tmp_path / "tests" / "test_build.py")
    assert _run_ps(driver, str(tmp_path)).split("|") == [want] * 4 + ["none"]


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell 5.1 is the Windows check's shell")
def test_the_check_script_takes_only_py_files_says_where_it_looked_and_runs_a_file_named_twice_once(tmp_path):
    """The screen review's N1-N3, the script's helpers lifted as they are and
    run in 5.1: "-Tests README.md" finds no test file although README.md
    exists (only .py files are test files); the stop message names the places
    looked, never "test_x.py.py"; and a file named twice in two ways is run
    once, under its first naming."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_build.py").write_text("", encoding="utf-8")
    (tmp_path / "README.md").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "README.md").write_text("", encoding="utf-8")
    driver = tmp_path / "drive.ps1"
    driver.write_text(_helpers("test-file") + r"""
Set-Location $args[0]
$readme = if (Resolve-TestFile "README.md") { "found" } else { "none" }
$looked = (Get-TestFileCandidates "test_x.py") -join " and "
$bare = (Get-TestFileCandidates "test_x") -join " and "
$files = @(Get-UniqueTestFiles @("tests\test_build.py", "tests/test_build.py", (Resolve-TestFile "test_build")))
"$readme|$looked|$bare|$($files.Count)|$($files[0])"
""", encoding="utf-8")
    said = _run_ps(driver, str(tmp_path)).split("|")
    assert said == ["none", r"test_x.py and tests\test_x.py", r"test_x.py and tests\test_x.py", "1", r"tests\test_build.py"]
    script = (REPO / "pilot" / "wintest" / "run_checks.ps1").read_text(encoding="utf-8")
    assert "$looked = (Get-TestFileCandidates $t) -join" in script and "$t.py and tests" not in script
    assert script.index("$files = @(Get-UniqueTestFiles $files)") < script.index("Start-TestFile $vpy $file $out")


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell 5.1 is the Windows check's shell")
def test_the_check_script_finds_the_app_wherever_it_was_installed_and_nothing_else(tmp_path):
    """The screen review's S1: an install run from inside a packaged app lands
    in that package's private copy of Programs (P193), where the close step
    once never looked. The helpers, lifted as they are and run in 5.1 against
    a stand-in %LOCALAPPDATA%, find the program in the real Programs folder
    and in a Packages\\<package>\\LocalCache\\Local\\Programs copy, and never
    a program of another name or in another folder."""
    local = tmp_path / "Local [x]"
    real = local / "Programs" / "Tax Document Console" / "app.exe"
    copy = local / "Packages" / "Claude_abc" / "LocalCache" / "Local" / "Programs" / "Tax Document Console" / "app.exe"
    others = [local / "Programs" / "Other" / "app.exe", local / "Programs" / "Tax Document Console" / "other.exe"]
    for exe in (real, copy, *others):
        exe.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(POWERSHELL, exe)
    procs = [subprocess.Popen([str(exe), "-NoProfile", "-Command", "Start-Sleep -Seconds 120"],
                              creationflags=subprocess.CREATE_NO_WINDOW) for exe in (real, copy, *others)]
    driver = tmp_path / "drive.ps1"
    driver.write_text(_helpers("app-close") + """
$patterns = Get-AppExePatterns $args[0] @("Tax Document Console") "app.exe"
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline -and @(Find-AppProcess $patterns).Count -lt 2) { Start-Sleep -Milliseconds 200 }
$found = @(Find-AppProcess $patterns | ForEach-Object { $_.Path } | Sort-Object -Unique)
"$($patterns.Count)|$($found -join ';')"
""", encoding="utf-8")
    try:
        said = _run_ps(driver, str(local)).split("|")
        assert said[0] == "2"
        assert sorted(said[1].split(";")) == sorted([str(real), str(copy)])
        assert all(proc.poll() is None for proc in procs), "finding the app never closes anything"
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait(10)
    script = (REPO / "pilot" / "wintest" / "run_checks.ps1").read_text(encoding="utf-8")
    assert '$appExes = Get-AppExePatterns $env:LOCALAPPDATA @($ProductName, $EarlierName) "$ProductName.exe"' in script


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell 5.1 is the Windows check's shell")
def test_the_check_script_asks_the_app_to_close_and_leaves_alone_what_will_not(tmp_path):
    """P200, N7: the script's close helpers, lifted as they are and run in 5.1.
    A stand-in app with a window (a copy of PowerShell holding an invisible
    form) closes when asked; a stand-in without one is still running when the
    helper gives up, and is returned rather than killed; a process whose
    program is not named is never touched."""
    shown, windowless = tmp_path / "shown" / "app.exe", tmp_path / "windowless" / "app.exe"
    for exe in (shown, windowless):
        exe.parent.mkdir()
        shutil.copy(POWERSHELL, exe)
    form = ("Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.Form; "
            "$f.Opacity = 0; [System.Windows.Forms.Application]::Run($f)")
    procs = [subprocess.Popen([str(shown), "-NoProfile", "-Command", form]),
             subprocess.Popen([str(windowless), "-NoProfile", "-Command", "Start-Sleep -Seconds 120"],
                              creationflags=subprocess.CREATE_NO_WINDOW)]
    driver = tmp_path / "drive.ps1"
    driver.write_text(_helpers("app-close") + """
$shown, $windowless = $args[0], $args[1]
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline -and -not (@(Find-AppProcess @($shown) | Where-Object { $_.MainWindowHandle -ne 0 }).Count)) {
    Start-Sleep -Milliseconds 200
}
$before = @(Find-AppProcess @($shown, $windowless)).Count
$left = @(Close-App @($shown) 20).Count
$stubborn = @(Close-App @($windowless) 2).Count
"$before|$left|$stubborn|$(@(Find-AppProcess @($windowless)).Count)"
""", encoding="utf-8")
    try:
        assert _run_ps(driver, str(shown), str(windowless)) == "2|0|1|1"
        assert procs[0].wait(10) == 0
        assert procs[1].poll() is None, "the window-less stand-in was not the helper's to end"
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait(10)


# ------------------------------------------ the Mac check kit (SPEC-mac R33, P254) ----

MACTEST = REPO / "pilot" / "mactest"
KIT_SCRIPT = MACTEST / "run_checks.sh"
KIT_PROMPT = MACTEST / "PROMPT.md"
KIT_RESULTS = MACTEST / "RESULTS-TEMPLATE.md"
#: The test files SPEC-mac R33 names: the ones the port changes, run on the
#: system they change for.
KIT_TESTS = (
    "test_settings", "test_after_install", "test_scheduling", "test_runner", "test_locking", "test_fsio",
    "test_checkpoint", "test_store", "test_ledger", "test_layout", "test_filer", "test_validators", "test_ocr",
    "test_api", "test_api_entry", "test_build", "test_shell", "test_shell_menu", "test_single_source",
    "test_layers", "test_repo_map", "test_tripwire")
#: Added by the last job: the files R36 changes, and the two the earlier jobs'
#: sections of SPEC-mac section 7 name that R33's list leaves out.
KIT_TESTS_ADDED = ("test_content_check", "test_pilot", "test_errors", "test_lockfiles")


def _bash() -> str:
    found = shutil.which("bash")
    if found is None:
        pytest.skip("bash is not on PATH")
    return found


def _kit_text(path: Path = KIT_SCRIPT) -> str:
    return path.read_text(encoding="utf-8")


def _kit_block(name: str) -> str:
    """One BEGIN/END block of run_checks.sh, lifted as it is."""
    script = _kit_text()
    begin, end = f"# ── BEGIN {name} ──\n", f"# ── END {name} ──"
    assert script.count(begin) == 1 and script.count(end) == 1, name
    return script.split(begin)[1].split(end)[0]


def _in_bash(code: str, cwd: Path, **env: str) -> subprocess.CompletedProcess:
    """``code`` run by bash, with the suite's one way to build a child's
    environment (decision 185), though this child is bash."""
    from tests.conftest import child_env

    return subprocess.run([_bash(), "-c", code], capture_output=True, text=True, cwd=cwd, check=False,
                          env=child_env(**env))


def test_the_mac_kit_has_its_three_files_and_takes_the_samples_from_the_windows_kit_by_path():
    """R33: ``run_checks.sh``, ``PROMPT.md`` and ``RESULTS-TEMPLATE.md``; the
    made-up documents come from ``pilot/wintest/make_samples.py`` by its path,
    never copied, so there is one builder of them."""
    for path in (KIT_SCRIPT, KIT_PROMPT, KIT_RESULTS):
        assert path.is_file(), path
    assert "pilot/wintest/make_samples.py" in _kit_text()
    assert not (MACTEST / "make_samples.py").exists()


def test_the_mac_kit_script_runs_under_the_bash_macos_ships_and_parses():
    """R16, R33: /bin/bash is 3.2 on every Mac, so the kit uses nothing 3.2
    lacks (the list ``test_build`` holds the other scripts to), starts with the
    interpreter it means, is checked out with LF and the execute bit, and
    ``bash -n`` parses it."""
    text = _kit_text()
    assert text.startswith("#!/bin/bash\n") and "\r" not in text
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    for lacking in (r"\bmapfile\b", r"\breadarray\b", r"\$\{[^}]*(,,|\^\^)", r"\bdeclare\s+-A\b", r"\blocal\s+-n\b",
                    r"\|&", r"&>>", r"\bcoproc\b", r"\bdeclare\s+-n\b", r"\bprintf\s+-v\b"):
        assert not re.search(lacking, code), lacking
    checked = subprocess.run([_bash(), "-n", str(KIT_SCRIPT)], capture_output=True, text=True, check=False)
    assert checked.returncode == 0, checked.stderr
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not on PATH; the mode cannot be asked")
    staged = subprocess.run([git, "ls-files", "-s", "--", "pilot/mactest/run_checks.sh"], cwd=REPO,
                            capture_output=True, text=True, check=False).stdout.split()
    assert staged and staged[0] == "100755", staged


def test_the_mac_kit_opens_in_the_checkout_and_cuts_path_with_the_block_the_mac_scripts_share():
    """R16 (E-10) for the kit: the first command is ``cd`` to the checkout (two
    folders above the kit), and before any tool is run PATH is cut to its
    absolute folders by the very text ``build-mac.sh`` opens with, so a file
    dropped in the checkout named like python3, node or git cannot run in
    its place."""
    def block(text: str) -> str:
        return text[text.index('clean_path=""'):text.index("PATH=$clean_path") + len("PATH=$clean_path")]

    script = _kit_text()
    assert block(script) == block((REPO / "build-mac.sh").read_text(encoding="utf-8"))
    runs = [line for line in script.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert runs[0] == 'cd "$(dirname "$0")/../.." || exit 1'
    before = "\n".join(script[:script.index("PATH=$clean_path")].splitlines())
    tools = re.compile(r"\b(python3|node|npm|git|codesign|ditto|hdiutil|shasum|find|file|lipo|sed|grep)\b")
    assert not [line for line in before.splitlines() if not line.lstrip().startswith("#") and tools.search(line)]


def test_the_mac_kit_names_the_same_safety_rules_as_the_windows_kit():
    """R33: the prompt carries wintest's safety block. Each rule of the Windows
    prompt's is found, by its own opening words, in the Mac prompt's - so a rule
    reworded for Windows fails here until the Mac's follows - and the Mac adds
    the ones only a Mac has: nobody types its password but Jason, Gatekeeper
    is never switched off, nothing is forced."""
    def safety(path: Path) -> str:
        text = " ".join(path.read_text(encoding="utf-8").split())
        return text.split("SAFETY - never break these:")[1].split(" 1. GET THE CODE")[0]

    windows = safety(REPO / "pilot" / "wintest" / "PROMPT.md").replace("the installer", "the disk image")
    mac = safety(KIT_PROMPT)
    leads = [re.split(r"[:.]", bullet.strip())[0].strip() for bullet in windows.split(" - ") if bullet.strip()]
    assert len(leads) >= 4, leads
    for lead in leads:
        assert lead in mac, lead
    # The four standing rules, as they bind this kit.
    assert "Generative AI never reads client financial documents" in mac
    assert "Nothing is ever sent" in mac
    for mac_only in ("Never type, read, store or ask for the Mac's password", "Never use sudo",
                     "never turn off Gatekeeper", "never remove the quarantine mark",
                     "Never toggle iCloud's", "Quit it with Command-Q, never force it",
                     "~/PilotTest"):
        assert mac_only.lower() in mac.lower(), mac_only


def test_the_mac_kit_installs_no_tool_sends_nothing_forces_nothing_and_tags_nothing():
    """The kit installs nothing of its own (it reports where to get a tool and
    stops), sends nothing, ends no process it did not start, and never turns
    off the Mac's guards. The only installs are the locks' hash-checked ones."""
    code = "\n".join(line for line in _kit_text().splitlines() if not line.lstrip().startswith("#"))
    for forbidden in (r"\bsudo\b", r"\bbrew\b", r"\bcurl\b", r"\bwget\b", r"\bnpm\s+(install|i)\b", r"\bkill\b",
                      r"\bpkill\b", r"\bkillall\b", r"\bspctl\b", r"\bxattr\b", r"\bgit\s+(tag|push)\b",
                      r"\bgh\b", r"\bsendmail\b", r"\bmail\b", r"\bosascript\b", r"\bsoftwareupdate\b"):
        assert not re.search(forbidden, code), forbidden
    for line in code.splitlines():
        if re.search(r"\bpip\s+install\b|\bpip install\b|-m pip install", line):
            assert "--require-hashes" in line, line
        if "xcode-select" in line:
            assert "--install" not in line.replace('xcode-select --install"', ""), line
    for line in code.splitlines():
        if "rm -rf" in line:
            assert "${SMOKE:?}" in line, line


def test_the_mac_kit_reads_no_folder_but_the_checkout_and_pilottest():
    """The kit never prints or stores a client's name because it never reads
    one: its only paths are the checkout and ``~/PilotTest`` (the made-up
    samples, the smoke's scratch root and the results)."""
    code = "\n".join(line for line in _kit_text().splitlines() if not line.lstrip().startswith("#"))
    assert not re.search(r"CloudStorage|Mobile Documents|\bDocuments\b|\bDesktop\b|\bDownloads\b|GoogleDrive", code)
    for home in re.findall(r"(?:\$HOME|~)/[A-Za-z]\w*", code):
        assert home.endswith("/PilotTest"), home
    assert 'TEST="$HOME/PilotTest"' in code


def test_the_mac_kit_builds_only_after_every_named_test_file_has_ended():
    """P200, A1 on a Mac: the build writes ``build-portable`` into the
    checkout, and the suite's end-of-run guard (decision 185) fails any file
    still running when a new folder appears there. So every test process is
    waited for, and its verdict recorded, before the build starts."""
    script = _kit_text()
    waited = script.index('wait "${PIDS[$i]}"')
    recorded = script.index('record "tests $file"')
    build = script.index('run /bin/bash "$REPO/build-mac.sh"')
    assert script.count('wait "${PIDS[$i]}"') == 1 and script.count("build-mac.sh") == 2
    assert waited < recorded < build
    assert '"$VPY" -m pytest -q -p no:cacheprovider "$file" > "$out" 2>&1 &' in script


def test_the_mac_kit_takes_a_test_file_by_bare_name_by_file_name_or_by_path(tmp_path):
    """P200, N8 for the kit: ``--tests test_build`` once stopped with "no such
    test file". The script's resolver, lifted as it is and run in bash, finds
    the same file from each way of naming it, and nothing for a name that is
    not a test file."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_build.py").write_text("", encoding="utf-8")
    (tmp_path / "README.md").write_text("", encoding="utf-8")
    done = _in_bash(_kit_block("test-file helpers") + """
for name in test_build test_build.py tests/test_build.py README.md nope; do
  printf '%s=%s\\n' "$name" "$(resolve_test_file "$name")"
done
split_test_list " a , b,,c.py ," | tr '\\n' '|'
""", tmp_path)
    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    assert lines[:5] == ["test_build=tests/test_build.py", "test_build.py=tests/test_build.py",
                         "tests/test_build.py=tests/test_build.py", "README.md=", "nope="]
    assert lines[5] == "a|b|c.py|"


def _run_kit(tmp_path: Path, *args: str, path: str | None = None) -> tuple[subprocess.CompletedProcess, dict]:
    """The real script, run by bash with a home of its own, and what it wrote
    to checks.json (``{}`` when it wrote none)."""
    from tests.conftest import child_env

    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = child_env(HOME=str(home), USERPROFILE=str(home))
    if path is not None:
        env["PATH"] = path
    done = subprocess.run([_bash(), str(KIT_SCRIPT), *args], capture_output=True, text=True, cwd=tmp_path,
                          check=False, env=env, timeout=120)
    checks = home / "PilotTest" / "results" / "checks.json"
    return done, json.loads(checks.read_text(encoding="utf-8")) if checks.is_file() else {}


def test_a_typo_in_the_test_list_stops_the_kit_at_once_naming_where_it_looked(tmp_path):
    """Every named file is found before the environment is installed or any
    tool asked for, so a typo costs nothing: the run stops, says where it
    looked, and only a ``.py`` file counts."""
    done, checks = _run_kit(tmp_path, "--tests", "test_pilot,test_nosuch")
    assert done.returncode == 1, done.stdout + done.stderr
    assert checks["tests"]["result"] == "FAIL"
    assert checks["tests"]["evidence"].startswith(
        "no such test file: test_nosuch (looked for test_nosuch.py and tests/test_nosuch.py;")
    _, checks = _run_kit(tmp_path, "--tests", "README.md")
    assert "README.md.py and tests/README.md.py" in checks["tests"]["evidence"]
    assert ".py.py" not in checks["tests"]["evidence"]
    _, checks = _run_kit(tmp_path, "--tests", "../outside")
    assert checks["tests"]["evidence"].startswith("no such test file: ../outside")
    done, _ = _run_kit(tmp_path, "--tests")
    assert done.returncode == 2 and "--tests needs a list" in done.stdout
    done, _ = _run_kit(tmp_path, "--bogus")
    assert done.returncode == 2 and "Usage" in done.stdout


def test_a_file_named_two_ways_is_one_test_run_and_the_kit_then_asks_for_a_mac(tmp_path):
    """``test_pilot``, ``test_pilot.py`` and ``tests/test_pilot.py`` are one
    file, and two runs would write one output file. The machine is stood in for
    as a Linux one (on a real Mac the kit would go on and build), so the kit
    then stops where it should, having written nothing but its own results
    under the home it was given."""
    done, checks = _run_kit(tmp_path, "--tests", "test_pilot, test_pilot.py,tests/test_pilot.py",
                            path=_stub_bin(tmp_path, system="Linux"))
    assert done.returncode == 1
    assert "Test files to run: tests/test_pilot.py\n" in done.stdout
    assert checks["tools"]["result"] == "FAIL" and "not a Mac" in checks["tools"]["evidence"]
    assert sorted(path.name for path in (tmp_path / "home").iterdir()) == ["PilotTest"]


def _stub_bin(tmp_path: Path, *, system: str = "Darwin", machine: str = "arm64", macos: str = "15.1", translated: str = "0",
              clt: bool = True, python: str | None = None, node: str | None = None) -> str:
    """A PATH of one folder: the system tools the kit's first steps use,
    linked, and stand-ins for the Mac's ``uname``, ``sw_vers``, ``sysctl`` and
    ``xcode-select`` (and a Python or Node when given)."""
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    for tool in ("sed", "tr", "grep", "date", "mkdir", "dirname", "basename", "mv", "rm", "head", "tail", "cut",
                 "env", "cat", "ls"):
        found = shutil.which(tool)
        assert found, tool
        (bin_ / tool).unlink(missing_ok=True)
        (bin_ / tool).symlink_to(found)

    def stub(name: str, body: str) -> None:
        path = bin_ / name
        path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        path.chmod(0o755)

    stub("uname", f'case "$1" in -s) echo {system};; -m) echo {machine};; *) echo {system};; esac')
    stub("sw_vers", f"echo {macos}")
    stub("sysctl", f"echo {translated}")
    stub("xcode-select", "exit 0" if clt else "exit 2")
    if python is not None:
        stub("python3", python)
    if node is not None:
        stub("node", node)
        stub("npm", "echo 10.0.0")
    return str(bin_)


@pytest.mark.parametrize(("stubs", "said"), [
    ({"machine": "x86_64"}, "this Terminal reports x86_64"),
    ({"translated": "1"}, "running under Rosetta"),
    ({"macos": "13.6.1"}, "macOS 13.6.1; the app needs macOS 14 or later"),
])
def test_the_kit_stops_on_a_mac_the_app_would_refuse_and_says_why(tmp_path, stubs, said):
    """The app needs Apple silicon, macOS 14 or later and a Terminal that is
    not under Rosetta (P243); the kit builds on exactly that, so on any other
    it records why and stops before it installs or builds anything."""
    done, checks = _run_kit(tmp_path, path=_stub_bin(tmp_path, **stubs))
    assert done.returncode == 1, done.stdout + done.stderr
    assert checks["tools"]["result"] == "FAIL" and said in checks["tools"]["evidence"], checks
    assert list(checks) == ["tools"]
    assert "STOPPED" in done.stdout


def test_a_missing_tool_is_reported_with_where_to_get_it_and_the_kit_installs_nothing(tmp_path):
    """R33: python.org's installer for the office's Python (read from
    ``pyproject.toml``), nodejs.org's LTS and the Command Line Tools; the
    script stops and installs none of them. A Python below the floor is as
    missing as none."""
    office = re.search(r'\[tool\.office\]\s*python-version = "([^"]+)"',
                       (REPO / "pyproject.toml").read_text(encoding="utf-8")).group(1)
    for python in (None, "exit 1"):
        done, checks = _run_kit(tmp_path, path=_stub_bin(tmp_path, clt=False, python=python))
        assert done.returncode == 1, done.stdout + done.stderr
        evidence = checks["tools"]["evidence"]
        assert checks["tools"]["result"] == "FAIL" and list(checks) == ["tools"]
        assert f"Python {office} :  the macOS installer from https://www.python.org/downloads/macos/" in evidence
        assert "Node.js (with npm) :  the LTS installer from https://nodejs.org/" in evidence
        assert "Command Line Tools (git, codesign) :  xcode-select --install" in evidence
    assert not (tmp_path / "home" / "PilotTest" / "smoke").exists()


def test_the_kit_writes_every_result_as_json_in_the_order_it_ran(tmp_path):
    """The recording helpers, lifted as they are: each result is PASS, FAIL,
    NOT VERIFIED or INFO with its evidence, the file is whole JSON after every
    record, and quotes, backslashes, tabs, newlines and non-ASCII text in an
    evidence line cannot break it."""
    results = tmp_path / "results"
    results.mkdir()
    done = _in_bash(_kit_block("recording helpers") + """
record "tools" PASS 'Python 3.14.0, Node v22, "git"'
record "tree" "NOT VERIFIED" $'branch x\\twith a tab\\nand a line, a \\\\ backslash, a Zoë'
record "tests tests/test_pilot.py" FAIL "1 failed, 3 passed (output: /x/y)"
record "install_by_hand" INFO "not installed here"
""", tmp_path, JSON=str(results / "checks.json"), LOG=str(results / "run.log"))
    assert done.returncode == 0, done.stderr
    data = json.loads((results / "checks.json").read_text(encoding="utf-8"))
    assert list(data) == ["tools", "tree", "tests tests/test_pilot.py", "install_by_hand"]
    assert {entry["result"] for entry in data.values()} == {"PASS", "NOT VERIFIED", "FAIL", "INFO"}
    assert data["tools"]["evidence"] == 'Python 3.14.0, Node v22, "git"'
    assert data["tree"]["evidence"].startswith("branch x with a tab and a line") and "Zoë" in data["tree"]["evidence"]
    assert "tools: PASS - " in (results / "run.log").read_text(encoding="utf-8")


def _prompt() -> str:
    return KIT_PROMPT.read_text(encoding="utf-8")


def test_the_mac_prompt_lists_the_ports_test_files_and_every_one_exists():
    """R33: the exact test files, named in the prompt's run line - the twenty-two
    the SPEC lists, then the four the last job adds with its reason - and each is
    a file under ``tests/``. The whole suite runs only if Jason asks."""
    line = re.search(r"bash pilot/mactest/run_checks\.sh --tests (\S+)", _prompt())
    assert line, "the prompt names no --tests line"
    named = line.group(1).split(",")
    assert tuple(named) == KIT_TESTS + KIT_TESTS_ADDED
    for name in named:
        assert (REPO / "tests" / f"{name}.py").is_file(), name
    assert "only if Jason asks" in _prompt()


def test_the_mac_prompt_walks_every_step_of_the_buyers_walk_and_every_hands_on_step():
    """R33: section 3's fourteen steps are the prompt's H2, and H1 to H14 are
    each a step of their own with the reason it was chosen. The SPEC's walk
    and the prompt's cannot drift apart: every walk step's number is there."""
    prompt = _prompt()
    walk = prompt.split("H2. THE BUYER'S WALK")[1].split("   H3.")[0]
    assert re.findall(r"^ {5}(\d+)\. ", walk, re.MULTILINE) == [str(n) for n in range(1, 15)]
    for number in range(1, 15):
        assert re.search(rf"^ {{3}}H{number}\. ", prompt, re.MULTILINE), number
    assert re.search(r"^ {3}H1b\. ", prompt, re.MULTILINE)
    assert prompt.count("Chosen because") >= 13
    spec = (REPO / "pilot" / "SPEC-mac.md").read_text(encoding="utf-8")
    for sentence in ("Within a minute the schedule's first pass runs", "Leave the Mac on and signed in overnight",
                     "Switched off by hand", "Removal"):
        assert sentence in spec and sentence.split(".")[0] in " ".join(prompt.split())


def test_the_mac_results_template_has_a_row_for_every_check_and_every_step():
    """The template and the script cannot disagree: each check the script
    records by a fixed name, each test file the prompt names, each walk step
    and each H step has its row, so a result nobody filled in is visible."""
    template = KIT_RESULTS.read_text(encoding="utf-8")
    rows = {line.split("|")[1].strip() for line in template.splitlines() if line.startswith("|")}
    fixed = set(re.findall(r'record "([a-z_]+)"', _kit_text())) - {"tests", "test_suite", "install_by_hand"}
    assert fixed >= {"tools", "tree", "environment", "room_as_windows", "ruff_and_map", "build", "bundle",
                     "frozen_smoke", "sample_folder"}
    for name in fixed:
        assert name in rows, name
    for name in KIT_TESTS + KIT_TESTS_ADDED:
        assert f"tests {name}.py" in rows, name
    for number in range(1, 15):
        assert any(row == str(number) or re.fullmatch(rf"{number}[a-c]", row) for row in rows), number
        assert f"H{number}" in rows or number == 2 and "H2" in template, number
    assert {"H1b", "H4b"} <= rows


def test_the_season_builder_in_the_prompt_makes_scans_no_two_of_which_share_their_bytes(tmp_path):
    """H10 times a first pass over a season of scans. The reader keeps a
    verdict by content, so scans alike would be read once and the timing would
    mean nothing; the builder's program, lifted from the prompt and run, makes
    each household's own, and writes only under the folder it is given."""
    import hashlib

    from tests.conftest import child_env

    program = _prompt().split("THE SEASON BUILDER (")[1].split("\n\n", 1)[1].rstrip("`\n ")
    root = tmp_path / "season"
    done = subprocess.run([sys.executable, "-", str(root), "2", "2"], input=program, capture_output=True, text=True,
                          cwd=REPO, check=False, env=child_env(TRACKER_DATA_HOME=str(tmp_path / "data")))
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().endswith(f"2 made-up households, 2 scan(s) each, under {root}")
    scans = sorted(root.rglob("scan 000*.pdf"))
    assert len(scans) == 4
    assert len({hashlib.sha256(scan.read_bytes()).hexdigest() for scan in scans}) == 4
    assert {path.name for path in tmp_path.iterdir()} <= {"app", "data", "season"}   # "app" is every test's own
