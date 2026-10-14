# The proof that a Windows package carries nothing a pass derives from clients
# and no settings (decision 186; SPEC-architecture R6.5, audit E-10).
#
# Build App.bat runs it on the package it has just assembled, before it says
# the build is done, and .github/workflows/build.yml runs it before the package
# is zipped. One script, so the names below have one home on Windows: the
# office's build and CI's build cannot check two different lists. (The Mac's
# build-mac.sh checks the same names in bash; tests/test_build.py holds both
# lists to the constants that own them.)
#
#   powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File tools\check_package.ps1 -Package <folder>
#
# Exit 0 when the package holds none of them. Exit 1, with one sentence, when
# it holds one (each found file named), when a file in it could not be read
# (a check that skipped a folder would prove nothing), or when the folder is
# not there. Windows PowerShell 5.1 (the office) and PowerShell 7 (CI) alike.

param([string]$Package = "")

# Every name the data home or the settings folder holds, each spelled by the
# constant that owns it under tracker/ (tests/test_build.py holds this list
# equal to them): the store and its write-ahead files, the run log, the pass
# order, decision 159's checkpoint with its journal, write-ahead files,
# damaged copy, recovered folder and last-pass file, decision 193's error log
# with its rotated copies and its passes folder, the schedule's task file, the
# reader's scratch folder, the data folder's own name and the settings file.
$names = @('tracker.db', 'tracker.db-wal', 'tracker.db-shm', 'runs.log', 'pass-order.json', 'record-heads.db', 'record-heads.db-journal', 'record-heads.db-wal', 'record-heads.db-shm', 'record-heads.db.damaged', 'recovered', 'last-pass.json', 'tracker-errors.log', 'tracker-errors.log.1', 'tracker-errors.log.2', 'tracker-errors.log.3', 'passes', 'tax-tracker.xml', 'ocr-scratch', 'tax-document-tracker-pilot', 'settings.json')
# Decision 159's set-asides, by the pattern set_aside() gives them.
$patterns = @('tracker.db.v*.old*', 'record-heads.db.v*.old*')

function Stop-Check($sentence) {
    [Console]::Error.WriteLine($sentence)
    exit 1
}

if (-not $Package -or -not (Test-Path -LiteralPath $Package -PathType Container)) {
    Stop-Check "There is no package folder at '$Package' to check."
}
$unread = @()
$found = @(Get-ChildItem -LiteralPath $Package -Recurse -Force -ErrorAction SilentlyContinue -ErrorVariable unread |
    Where-Object { $name = $_.Name; ($names -contains $name) -or ($patterns | Where-Object { $name -like $_ }) })
if ($unread.Count -gt 0) {
    Stop-Check ("Not every file in the package could be read, so it is not proved to hold no data: " +
        (($unread | ForEach-Object { "$($_.TargetObject)" }) -join ', '))
}
if ($found.Count -gt 0) {
    Stop-Check ("The package holds what belongs in a data folder or a settings folder: " + ($found.FullName -join ', '))
}
Write-Host "The package holds no store, run log, task file or settings."
exit 0
