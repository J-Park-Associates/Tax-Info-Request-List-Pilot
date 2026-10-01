# Pilot 0.1 Windows check - the automated part (pilot decisions P28, P29).
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File pilot\wintest\run_checks.ps1
# Works in Windows PowerShell 5.1 and PowerShell 7, from a git clone or from
# GitHub's "Download ZIP". Every step writes PASS / FAIL / NOT VERIFIED / INFO with
# its evidence to %USERPROFILE%\PilotTest\results\checks.json, and a full log
# beside it. It installs no tool on its own: a missing one is reported with
# the exact winget command, and the script stops.

#
# -Tests runs only the named test files (the components a change touched),
# each in its own process, at the same time as the installer build - the
# sorting engine's own tests are not rerun (Jason, 2026-09-29). Without
# -Tests the whole suite runs, as before.
#   powershell -ExecutionPolicy Bypass -File pilot\wintest\run_checks.ps1 -Tests tests\test_pilot.py,tests\test_after_install.py

param([string[]]$Tests = @())

# PowerShell 5.1 turns any line a tool writes to its error output into a
# fatal error under "Stop" (the first Windows check died on pip's routine
# notice). Tools are judged by their exit codes instead.
$ErrorActionPreference = "Continue"
$Repo     = (Resolve-Path "$PSScriptRoot\..\..").Path
$Test     = Join-Path $env:USERPROFILE "PilotTest"
$Results  = Join-Path $Test "results"
$Log      = Join-Path $Results "run_checks.log"
$Json     = Join-Path $Results "checks.json"
$ProductName = "Tax Document Console"
# The pilot's earlier name, tracker.settings.EARLIER_PRODUCT_NAME (a test holds
# this copy equal to it). A new install goes to Programs\<new name>; a PC
# upgraded from the earlier name keeps that program's own folder (P155,
# SPEC-rename R2), so the new folder is looked for first, then the earlier one.
$EarlierName = "Tax Document Tracker Pilot"
$AppDir   = Join-Path $env:LOCALAPPDATA "Programs\$ProductName"
if (-not (Test-Path $AppDir)) {
    $earlierDir = Join-Path $env:LOCALAPPDATA "Programs\$EarlierName"
    if (Test-Path $earlierDir) { $AppDir = $earlierDir }
}
New-Item -ItemType Directory -Force -Path $Results | Out-Null
$checks = [ordered]@{}

function Say($text) {
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $text
    Write-Host $line
    Add-Content -Path $Log -Value $line
}
function Record($name, $result, $evidence) {
    $checks[$name] = [ordered]@{ result = $result; evidence = "$evidence" }
    $checks | ConvertTo-Json -Depth 4 | Set-Content -Path $Json -Encoding UTF8
    Say ("{0}: {1} - {2}" -f $name, $result, $evidence)
}
function Verdict($ok) { if ($ok) { "PASS" } else { "FAIL" } }
function Stop-Here($why) { Say "STOPPED: $why"; exit 1 }
# Runs a tool, copies everything it prints into the log, returns its exit code.
function Run($exe, [string[]]$argv) {
    $out = & $exe @argv 2>&1 | Out-String
    $code = $LASTEXITCODE
    Add-Content -Path $Log -Value $out
    return $code
}
# Inno Setup 6.7 ships ISCC.exe without a version number, so the version is
# read from its uninstall entry, then from its uninstaller.
function Inno-Version($iscc) {
    $keys = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
            "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
            "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"
    foreach ($k in $keys) {
        $v = (Get-ItemProperty -Path $k -ErrorAction SilentlyContinue).DisplayVersion
        if ($v) { return $v }
    }
    $unins = Join-Path (Split-Path $iscc) "unins000.exe"
    if (Test-Path $unins) { return (Get-Item $unins).VersionInfo.ProductVersion }
    return ""
}
# BEGIN test-file helpers
# `powershell -File run_checks.ps1 -Tests a,b` hands the script "a,b" as one
# value (only -Command splits it), so every value is split on commas here and
# the command works however it is typed (P128).
function Split-TestList([string[]]$list) {
    return @($list | ForEach-Object { "$_" -split "," } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}
# One test file in its own process. Windows PowerShell 5.1 reports no exit code
# for a Start-Process -PassThru process whose handle was never read while it
# ran, so the handle is read at once (P128); otherwise every file read FAIL.
function Start-TestFile($python, $file, $out) {
    $proc = Start-Process -FilePath $python -ArgumentList "-m", "pytest", "-q", "-p", "no:cacheprovider", "`"$file`"" `
            -RedirectStandardOutput $out -RedirectStandardError "$out.err" -NoNewWindow -PassThru
    $null = $proc.Handle
    return $proc
}
# END test-file helpers
function As-Version($text) {
    $m = [regex]::Match("$text", '\d+(\.\d+){1,3}')
    if ($m.Success) { return [version]$m.Value } else { return [version]"0.0" }
}

Set-Location $Repo
Say "Repository: $Repo"

# 1. Tools
$missing = @()
$pv = ""
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pv = (& python -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null | Out-String).Trim()
}
if ((As-Version $pv) -lt [version]"3.11") { $missing += "Python 3.11+ :  winget install -e --id Python.Python.3.13" }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { $missing += "Node.js :  winget install -e --id OpenJS.NodeJS.LTS" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { $missing += "git :  winget install -e --id Git.Git" }
$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$iv = ""
if ($iscc) { $iv = Inno-Version $iscc }
if (-not $iscc -or ($iv -and (As-Version $iv) -lt [version]"6.3")) { $missing += "Inno Setup 6.3 or later :  winget install -e --id JRSoftware.InnoSetup" }
if ($iscc -and -not $iv) { $iv = "(version unreadable; the build will show whether it works)" }
$longPaths = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -ErrorAction SilentlyContinue).LongPathsEnabled
$toolsText = if ($missing.Count) { "missing: " + ($missing -join " | ") } else { "Python $pv, Node, git, Inno Setup $iv; Windows long paths enabled: $([bool]$longPaths)" }
$toolsResult = if ($missing.Count) { "FAIL" } elseif ($iv -like "(version unreadable*") { "NOT VERIFIED" } else { "PASS" }
Record "tools" $toolsResult $toolsText
if ($missing.Count) { Stop-Here "install the missing tools (commands above), open a new terminal, run again" }

# 2. Where the code came from: a clone, or GitHub's "Download ZIP"
if (-not (Test-Path (Join-Path $Repo ".git"))) {
    # A ZIP has no history. The installer build insists on a committed tree
    # (P13), so the test makes one local snapshot commit and says so.
    Run git @("init", "-q") | Out-Null
    Run git @("add", "-A") | Out-Null
    $code = Run git @("-c", "user.name=Pilot Windows check", "-c", "user.email=pilot-check@localhost",
                      "commit", "-q", "-m", "Snapshot of the downloaded ZIP for the pilot Windows check")
    if ($code -ne 0) { Record "tree" "FAIL" "could not make the local snapshot commit"; Stop-Here "see $Log" }
    $head = (& git rev-parse --short HEAD 2>$null | Out-String).Trim()
    Record "tree" "NOT VERIFIED" "ZIP download committed as local snapshot $head; cannot be compared with GitHub"
} else {
    $branch = (& git rev-parse --abbrev-ref HEAD 2>$null | Out-String).Trim()
    $dirty  = (& git status --porcelain 2>$null | Out-String).Trim()
    $head   = (& git rev-parse --short HEAD 2>$null | Out-String).Trim()
    $fetch  = Run git @("fetch", "origin", "main")
    if ($dirty) { Record "tree" "FAIL" "uncommitted changes in the checkout"; Stop-Here "commit or discard them first" }
    if ($fetch -ne 0) {
        Record "tree" "NOT VERIFIED" "branch $branch at $head, clean; GitHub could not be reached to compare"
    } else {
        $behind = (& git rev-list --count "HEAD..origin/main" 2>$null | Out-String).Trim()
        Record "tree" (Verdict (($branch -eq "main") -and ($behind -eq "0"))) "branch $branch at $head, behind origin/main by $behind"
        if ($branch -ne "main" -or $behind -ne "0") { Stop-Here "check out an up-to-date main (git checkout main; git pull)" }
    }
}

# 3. Environment (hash-checked, as Setup.bat does)
if (-not (Test-Path ".venv")) { Run python @("-m", "venv", ".venv") | Out-Null }
$vpy = Join-Path $Repo ".venv\Scripts\python.exe"
$e1 = Run $vpy @("-m", "pip", "install", "--disable-pip-version-check", "--require-hashes", "-r", "requirements.lock")
$e2 = Run $vpy @("-m", "pip", "install", "--disable-pip-version-check", "--require-hashes", "--no-deps", "-r", "requirements-nodeps.lock")
Push-Location app; $e3 = Run npm.cmd @("ci"); Pop-Location
Record "environment" (Verdict (($e1 -eq 0) -and ($e2 -eq 0) -and ($e3 -eq 0))) "pip=$e1 pip-nodeps=$e2 npm-ci=$e3"
if ($e1 -or $e2 -or $e3) { Stop-Here "the environment did not install; see $Log" }

# The limit the app will hold file paths to on this PC (P29): 259 with
# Windows long paths off, 260 with them on.
$limits = (& $vpy -c "from tracker import layout; print('source install - long paths off:', layout.short_paths(), '- path limit:', layout.path_limit())" 2>&1 | Out-String).Trim()
Record "path_limit" "INFO" $limits

# 4. Checks: ruff, the map, and the tests - either the named files (started
# now, in parallel, and collected after the build) or the whole suite.
$ruff = Run $vpy @("-m", "ruff", "check", ".")
$map  = Run $vpy @("tools\repo_map.py", "check")
Record "ruff_and_map" (Verdict (($ruff -eq 0) -and ($map -eq 0))) "ruff=$ruff map=$map"
$env:PYTHONIOENCODING = "utf-8"
$running = @()
$Tests = Split-TestList $Tests
if ($Tests.Count) {
    foreach ($t in $Tests) {
        if (-not (Test-Path $t)) { Record "tests" "FAIL" "no such test file: $t"; Stop-Here "check the -Tests list" }
        $out = Join-Path $Results ("pytest-" + [IO.Path]::GetFileNameWithoutExtension($t) + ".txt")
        $running += [pscustomobject]@{ File = $t; Out = $out; Proc = Start-TestFile $vpy $t $out }
    }
    Say "Started $($Tests.Count) test file(s) in parallel; building meanwhile"
} else {
    $suite = Join-Path $Results "pytest.txt"
    & $vpy -m pytest -q -p no:cacheprovider 2>&1 | Out-File -FilePath $suite -Encoding UTF8
    $suiteExit = $LASTEXITCODE
    $summary = (Get-Content $suite | Select-String -Pattern "passed|failed" | Select-Object -Last 1).Line
    Record "test_suite" (Verdict ($suiteExit -eq 0)) "$summary (full output: $suite)"
}
Remove-Item Env:PYTHONIOENCODING

# 5. Build the installer
$env:TRACKER_BUILD_NONINTERACTIVE = "1"
$build = Run "cmd.exe" @("/c", "pilot\Build Pilot Installer.bat")
Remove-Item Env:TRACKER_BUILD_NONINTERACTIVE
$setup = Get-ChildItem "build-portable\installer\Tax-Document-Console-Setup-*.exe" -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
# The named test files, collected now that the build is done
foreach ($r in $running) {
    $r.Proc.WaitForExit()
    $summary = (Get-Content $r.Out -ErrorAction SilentlyContinue | Select-String -Pattern "passed|failed|error" | Select-Object -Last 1).Line
    Record ("tests " + $r.File) (Verdict ($r.Proc.ExitCode -eq 0)) "$summary (output: $($r.Out))"
}

if ($build -ne 0 -or -not $setup) {
    Record "build" "FAIL" "Build Pilot Installer.bat exit $build; installer found: $([bool]$setup) (log: $Log)"
    Stop-Here "the installer did not build"
}
$sha = (Get-FileHash -Algorithm SHA256 $setup.FullName).Hash
Record "build" "PASS" "$($setup.FullName) SHA-256 $sha"

# 6. Silent per-user install
$instLog = Join-Path $Results "install.log"
$p = Start-Process -FilePath $setup.FullName -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=`"$instLog`"" -Wait -PassThru
# The folder is found again after the install, as the one that now holds the
# program: on a first install neither existed when the script started, and an
# earlier folder may hold only the settings an uninstall left.
foreach ($name in @($ProductName, $EarlierName)) {
    $dir = Join-Path $env:LOCALAPPDATA "Programs\$name"
    if (Test-Path (Join-Path $dir "$ProductName.exe")) { $AppDir = $dir; break }
}
$exe = Join-Path $AppDir "$ProductName.exe"
$shortcut = Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs" -Recurse -Filter "$ProductName*.lnk" -ErrorAction SilentlyContinue | Select-Object -First 1
$uninst = Get-ChildItem "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall" -ErrorAction SilentlyContinue |
          Where-Object { (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DisplayName -like "$ProductName*" } | Select-Object -First 1
$installed = ($p.ExitCode -eq 0) -and (Test-Path $exe) -and [bool]$shortcut -and [bool]$uninst
Record "install" (Verdict $installed) "exit $($p.ExitCode); program $(Test-Path $exe); Start-menu shortcut $([bool]$shortcut); uninstall entry $([bool]$uninst); per-user, no admin prompt"

# 7. Sample clients folder (made-up documents only)
$sample = Join-Path $Test "Clients"
if (Test-Path $sample) {
    Record "sample_folder" "PASS" "$sample already exists (kept from an earlier run)"
} else {
    $sampleExit = Run $vpy @("pilot\wintest\make_samples.py")
    Record "sample_folder" (Verdict ($sampleExit -eq 0)) "$sample (made-up documents from tests/samples.py)"
}

# 8. How to start the app (F7, P193, R4). This script never starts it: the
# first start is the hands-on part's step, watched as it runs its one-time
# setup. Windows redirects what a program started from inside a packaged app
# (an AI assistant's window among them) writes under %LOCALAPPDATA% into that
# package's private copy, so an app started with Start-Process from such a
# shell reads and writes a second data folder the schedule never sees. The
# Start menu, or the shortcut handed to explorer.exe, starts it as the desktop
# does.
if ($shortcut) {
    Record "launch" "INFO" "not started here; start it from the Start menu or with: explorer.exe `"$($shortcut.FullName)`" - never Start-Process"
} else {
    Record "launch" "NOT VERIFIED" "no Start-menu shortcut found; start the app from the Start menu by hand"
}

Say "Automated part done. Results: $Json"
