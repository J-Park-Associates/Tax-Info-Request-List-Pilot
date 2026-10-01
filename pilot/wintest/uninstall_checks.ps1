# Pilot Windows check - uninstall and what it must leave behind (P12, P28, P29, P155).
# Run after the hands-on part:  powershell -ExecutionPolicy Bypass -File pilot\wintest\uninstall_checks.ps1
# Works in Windows PowerShell 5.1: tools are judged by exit codes, never by
# what they print to their error output.

$ErrorActionPreference = "Continue"
$Test     = Join-Path $env:USERPROFILE "PilotTest"
$Results  = Join-Path $Test "results"
$Json     = Join-Path $Results "uninstall.json"
$ProductName = "Tax Document Console"
# The pilot's earlier name, tracker.settings.EARLIER_PRODUCT_NAME (a test holds
# this copy equal to it): its task must be gone too, and a PC upgraded from it
# keeps that program's own folder (P155, SPEC-rename R2).
$EarlierName = "Tax Document Tracker Pilot"
$TaskNames = @($ProductName, $EarlierName)
$AppDir   = Join-Path $env:LOCALAPPDATA "Programs\$ProductName"
foreach ($name in $TaskNames) {
    $dir = Join-Path $env:LOCALAPPDATA "Programs\$name"
    if (Test-Path (Join-Path $dir "$ProductName.exe")) { $AppDir = $dir; break }
}
$DataDir  = Join-Path $env:LOCALAPPDATA "tax-document-tracker-pilot"
New-Item -ItemType Directory -Force -Path $Results | Out-Null
$checks = [ordered]@{}
function Record($name, $ok, $evidence) {
    # $ok is $true (PASS), $false (FAIL), or a verdict string such as "NOT VERIFIED".
    $verdict = if ($ok -is [string]) { $ok } elseif ($ok) { "PASS" } else { "FAIL" }
    $checks[$name] = [ordered]@{ result = $verdict; evidence = "$evidence" }
    $checks | ConvertTo-Json -Depth 4 | Set-Content -Path $Json -Encoding UTF8
    Write-Host ("{0}: {1} - {2}" -f $name, $checks[$name].result, $evidence)
}
function Task-Exists($taskName) {
    & schtasks.exe /Query /TN $taskName 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}
function Tasks-Present {
    return @($TaskNames | Where-Object { Task-Exists $_ })
}

Get-Process -Name $ProductName -ErrorAction SilentlyContinue | Stop-Process -Force
$tasksBefore = Tasks-Present
$settingsBefore = Test-Path (Join-Path $AppDir "settings.json")
$unins = Get-ChildItem $AppDir -Filter "unins*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $unins) { Record "uninstaller_found" $false "no unins*.exe in $AppDir"; exit 1 }
$p = Start-Process -FilePath $unins.FullName -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
Start-Sleep -Seconds 5
Record "uninstall_ran" ($p.ExitCode -eq 0) "exit $($p.ExitCode)"
Record "program_removed" (-not (Test-Path (Join-Path $AppDir "$ProductName.exe"))) $AppDir
# Both names must be gone after the uninstall. With no task before it, its
# removal was never exercised: that is not a PASS (the pilot 0.1 Windows check
# reported one it had not tested).
$tasksAfter = Tasks-Present
if ($tasksBefore.Count -gt 0) {
    Record "scheduled_task_removed" ($tasksAfter.Count -eq 0) "tasks before uninstall: $($tasksBefore -join ', '); still there after: $($tasksAfter -join ', ')"
} else {
    Record "scheduled_task_removed" "NOT VERIFIED" "no task under either name existed before the uninstall, so its removal was not exercised; still none after: $($tasksAfter.Count -eq 0)"
}
Record "data_folder_kept" (Test-Path $DataDir) $DataDir
Record "clients_folder_kept" (Test-Path (Join-Path $Test "Clients")) (Join-Path $Test "Clients")
Record "settings_kept" ((Test-Path (Join-Path $AppDir "settings.json")) -or -not $settingsBefore) "settings.json existed before uninstall: $settingsBefore; still there: $(Test-Path (Join-Path $AppDir 'settings.json'))"
