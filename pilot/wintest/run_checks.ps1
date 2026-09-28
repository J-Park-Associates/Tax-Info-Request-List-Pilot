# Pilot 0.1 Windows check - the automated part (pilot decision P28).
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File pilot\wintest\run_checks.ps1
# Every step writes PASS or FAIL with its evidence to
# %USERPROFILE%\PilotTest\results\checks.json and a full log beside it.
# It installs nothing on its own: a missing tool is reported with the exact
# winget command, and the script stops.

$ErrorActionPreference = "Stop"
$Repo     = (Resolve-Path "$PSScriptRoot\..\..").Path
$Test     = Join-Path $env:USERPROFILE "PilotTest"
$Results  = Join-Path $Test "results"
$Log      = Join-Path $Results "run_checks.log"
$Json     = Join-Path $Results "checks.json"
$TaskName = "Tax Document Tracker Pilot"
$AppDir   = Join-Path $env:LOCALAPPDATA "Programs\Tax Document Tracker Pilot"
New-Item -ItemType Directory -Force -Path $Results | Out-Null
$checks = [ordered]@{}

function Say($text) { $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $text; Write-Host $line; Add-Content -Path $Log -Value $line }
function Record($name, $ok, $evidence) {
    $checks[$name] = [ordered]@{ result = $(if ($ok) { "PASS" } else { "FAIL" }); evidence = "$evidence" }
    $checks | ConvertTo-Json -Depth 4 | Set-Content -Path $Json -Encoding UTF8
    Say ("{0}: {1} - {2}" -f $name, $checks[$name].result, $evidence)
}
function Stop-Here($why) { Say "STOPPED: $why"; exit 1 }
function Run($exe, [string[]]$argv) {
    & $exe @argv *>> $Log
    return $LASTEXITCODE
}

Set-Location $Repo
Say "Repository: $Repo"

# 1. Tools
$missing = @()
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) { $pv = (& python -c "import sys;print('%d.%d'%sys.version_info[:2])") } else { $pv = "" }
if (-not $py -or [version]$pv -lt [version]"3.11") { $missing += "Python 3.11+ :  winget install -e --id Python.Python.3.13" }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { $missing += "Node.js :  winget install -e --id OpenJS.NodeJS.LTS" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { $missing += "git :  winget install -e --id Git.Git" }
$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$innoOk = $false
if ($iscc) { $iv = (Get-Item $iscc).VersionInfo.ProductVersion; $innoOk = ([version]($iv -replace '[^\d\.].*$','')) -ge [version]"6.3" }
if (-not $innoOk) { $missing += "Inno Setup 6.3 or later :  winget install -e --id JRSoftware.InnoSetup" }
Record "tools" ($missing.Count -eq 0) $(if ($missing.Count) { "missing: " + ($missing -join " | ") } else { "Python $pv, Node, git, Inno Setup $iv" })
if ($missing.Count) { Stop-Here "install the missing tools (commands above), open a new terminal, run again" }

# 2. Tree state
Run git @("fetch", "origin", "main") | Out-Null
$branch = (& git rev-parse --abbrev-ref HEAD).Trim()
$dirty  = (& git status --porcelain)
$behind = (& git rev-list --count "HEAD..origin/main").Trim()
$head   = (& git rev-parse --short HEAD).Trim()
Record "tree" (($branch -eq "main") -and -not $dirty -and ($behind -eq "0")) "branch $branch at $head, behind origin/main by $behind, uncommitted: $([bool]$dirty)"
if ($branch -ne "main" -or $dirty -or $behind -ne "0") { Stop-Here "check out a clean, up-to-date main (git checkout main; git pull)" }

# 3. Environment (hash-checked, as Setup.bat does)
if (-not (Test-Path ".venv")) { Run python @("-m", "venv", ".venv") | Out-Null }
$vpy = Join-Path $Repo ".venv\Scripts\python.exe"
$e1 = Run $vpy @("-m", "pip", "install", "--require-hashes", "-r", "requirements.lock")
$e2 = Run $vpy @("-m", "pip", "install", "--require-hashes", "--no-deps", "-r", "requirements-nodeps.lock")
Push-Location app; $e3 = Run npm @("ci"); Pop-Location
Record "environment" (($e1 -eq 0) -and ($e2 -eq 0) -and ($e3 -eq 0)) "pip=$e1 pip-nodeps=$e2 npm-ci=$e3"
if ($e1 -or $e2 -or $e3) { Stop-Here "the environment did not install; see $Log" }

# 4. Checks: the whole suite, ruff, the map
$suite = Join-Path $Results "pytest.txt"
& $vpy -m pytest -q -p no:cacheprovider *> $suite
$suiteExit = $LASTEXITCODE
$summary = (Get-Content $suite | Select-String -Pattern "passed|failed" | Select-Object -Last 1).Line
Record "test_suite" ($suiteExit -eq 0) "$summary (full output: $suite)"
$ruff = Run $vpy @("-m", "ruff", "check", ".")
$map  = Run $vpy @("tools\repo_map.py", "check")
Record "ruff_and_map" (($ruff -eq 0) -and ($map -eq 0)) "ruff=$ruff map=$map"

# 5. Build the installer
$env:TRACKER_BUILD_NONINTERACTIVE = "1"
& cmd.exe /c "pilot\Build Pilot Installer.bat" *>> $Log
$build = $LASTEXITCODE
Remove-Item Env:TRACKER_BUILD_NONINTERACTIVE
$setup = Get-ChildItem "build-portable\installer\Tax-Document-Tracker-Pilot-Setup-*.exe" -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($build -ne 0 -or -not $setup) { Record "build" $false "Build Pilot Installer.bat exit $build; installer found: $([bool]$setup)"; Stop-Here "the installer did not build; see $Log" }
$sha = (Get-FileHash -Algorithm SHA256 $setup.FullName).Hash
Record "build" $true "$($setup.FullName) SHA-256 $sha"

# 6. Silent per-user install
$instLog = Join-Path $Results "install.log"
$p = Start-Process -FilePath $setup.FullName -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=`"$instLog`"" -Wait -PassThru
$exe = Join-Path $AppDir "Tax Document Tracker Pilot.exe"
$shortcut = Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs" -Recurse -Filter "Tax Document Tracker Pilot*.lnk" -ErrorAction SilentlyContinue | Select-Object -First 1
$uninst = Get-ChildItem "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall" -ErrorAction SilentlyContinue |
          Where-Object { (Get-ItemProperty $_.PSPath).DisplayName -like "Tax Document Tracker Pilot*" } | Select-Object -First 1
Record "install" (($p.ExitCode -eq 0) -and (Test-Path $exe) -and $shortcut -and $uninst) "exit $($p.ExitCode); program $(Test-Path $exe); Start-menu shortcut $([bool]$shortcut); uninstall entry $([bool]$uninst); no admin prompt (per-user)"

# 7. Sample clients folder (fake documents only)
$sampleExit = Run $vpy @("pilot\wintest\make_samples.py")
Record "sample_folder" ($sampleExit -eq 0) "$(Join-Path $Test 'Clients') (made-up documents from tests/samples.py)"

Say "Automated part done. Results: $Json"
