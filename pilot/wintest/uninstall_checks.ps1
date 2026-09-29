# Pilot 0.1 Windows check - uninstall and what it must leave behind (P12, P28, P29).
# Run after the hands-on part:  powershell -ExecutionPolicy Bypass -File pilot\wintest\uninstall_checks.ps1
# Works in Windows PowerShell 5.1: tools are judged by exit codes, never by
# what they print to their error output.

$ErrorActionPreference = "Continue"
$Test     = Join-Path $env:USERPROFILE "PilotTest"
$Results  = Join-Path $Test "results"
$Json     = Join-Path $Results "uninstall.json"
$TaskName = "Tax Document Tracker Pilot"
$AppDir   = Join-Path $env:LOCALAPPDATA "Programs\Tax Document Tracker Pilot"
$DataDir  = Join-Path $env:LOCALAPPDATA "tax-document-tracker-pilot"
New-Item -ItemType Directory -Force -Path $Results | Out-Null
$checks = [ordered]@{}
function Record($name, $ok, $evidence) {
    $checks[$name] = [ordered]@{ result = $(if ($ok) { "PASS" } else { "FAIL" }); evidence = "$evidence" }
    $checks | ConvertTo-Json -Depth 4 | Set-Content -Path $Json -Encoding UTF8
    Write-Host ("{0}: {1} - {2}" -f $name, $checks[$name].result, $evidence)
}
function Task-Exists {
    & schtasks.exe /Query /TN $TaskName 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

Get-Process -Name "Tax Document Tracker Pilot" -ErrorAction SilentlyContinue | Stop-Process -Force
$taskBefore = Task-Exists
$settingsBefore = Test-Path (Join-Path $AppDir "settings.json")
$unins = Get-ChildItem $AppDir -Filter "unins*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $unins) { Record "uninstaller_found" $false "no unins*.exe in $AppDir"; exit 1 }
$p = Start-Process -FilePath $unins.FullName -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
Start-Sleep -Seconds 5
Record "uninstall_ran" ($p.ExitCode -eq 0) "exit $($p.ExitCode)"
Record "program_removed" (-not (Test-Path (Join-Path $AppDir "Tax Document Tracker Pilot.exe"))) $AppDir
Record "scheduled_task_removed" (-not (Task-Exists)) "task existed before uninstall: $taskBefore"
Record "data_folder_kept" (Test-Path $DataDir) $DataDir
Record "clients_folder_kept" (Test-Path (Join-Path $Test "Clients")) (Join-Path $Test "Clients")
Record "settings_kept" ((Test-Path (Join-Path $AppDir "settings.json")) -or -not $settingsBefore) "settings.json existed before uninstall: $settingsBefore; still there: $(Test-Path (Join-Path $AppDir 'settings.json'))"
