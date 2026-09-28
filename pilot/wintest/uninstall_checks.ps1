# Pilot 0.1 Windows check - uninstall and what it must leave behind (P12, P28).
# Run after the hands-on part:  powershell -ExecutionPolicy Bypass -File pilot\wintest\uninstall_checks.ps1

$ErrorActionPreference = "Stop"
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

Get-Process -Name "Tax Document Tracker Pilot" -ErrorAction SilentlyContinue | Stop-Process -Force
$taskBefore = [bool](& schtasks.exe /Query /TN $TaskName 2>$null)
$unins = Get-ChildItem $AppDir -Filter "unins*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $unins) { Record "uninstaller_found" $false "no unins*.exe in $AppDir"; exit 1 }
$p = Start-Process -FilePath $unins.FullName -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
Start-Sleep -Seconds 3
& schtasks.exe /Query /TN $TaskName *> $null
$taskGone = ($LASTEXITCODE -ne 0)
Record "uninstall_ran" ($p.ExitCode -eq 0) "exit $($p.ExitCode)"
Record "program_removed" (-not (Test-Path (Join-Path $AppDir "Tax Document Tracker Pilot.exe"))) $AppDir
Record "scheduled_task_removed" $taskGone "task existed before uninstall: $taskBefore"
Record "data_folder_kept" (Test-Path $DataDir) $DataDir
Record "clients_folder_kept" (Test-Path (Join-Path $Test "Clients")) (Join-Path $Test "Clients")
Record "settings_kept" (Test-Path (Join-Path $AppDir "settings.json")) (Join-Path $AppDir "settings.json")
