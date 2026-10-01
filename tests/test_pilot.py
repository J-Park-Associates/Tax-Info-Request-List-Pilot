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
