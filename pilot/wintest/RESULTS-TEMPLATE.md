# Pilot 0.2 - Windows check result

- **Date:**
- **Machine:** Windows version, test machine
- **Commit tested:** (git rev-parse --short HEAD)
- **Summary:** PASS / FAIL, and one plain-English sentence.

## Automated part (run_checks.ps1, uninstall_checks.ps1)

| Check | Result | Evidence |
|---|---|---|
| tools | | |
| tree | | |
| environment | | |
| test_suite | | passed / failed counts; each failing test named |
| ruff_and_map | | |
| build | | installer path |
| install | | |
| sample_folder | | |
| uninstall_ran | | |
| program_removed | | |
| scheduled_task_removed | | |
| data_folder_kept | | |
| clients_folder_kept | | |
| settings_kept | | |

**Installer SHA-256:**

## Hands-on part (in the installed app, sample documents only)

| # | Step | Result | What was seen |
|---|---|---|---|
| 1 | Header badge reads "Pilot edition 0.2" | | |
| 2 | Terms: Escape does nothing | | |
| 3 | Terms: "I agree. Continue." disabled until the box is ticked | | |
| 4 | Accepting starts the tour | | |
| 5 | Tour: all 11 steps highlight or show their fallback; stage strip fits; wrap-up shows two columns | | |
| 6 | Tour button replays the tour | | |
| 7 | Clients folder set to %USERPROFILE%\PilotTest\Clients | | |
| 8 | New household with a 1040 request list created | | |
| 9 | Scan on "Smith Family": originals moved to the year folder | | |
| 10 | Named working copies in Prepared (e.g. "A01 - W-2 - TY2025.pdf") | | |
| 11 | Files the rules cannot place are in Needs Review | | |
| 12 | Status opens | | |
| 13 | Schedule Off: `schtasks /Query /TN "Tax Document Tracker Pilot"` finds no task | | |
| 14 | Schedule On at 06:30, every 4 hours: task XML shows 06:30 and PT240M or PT4H | | |
| 15 | After restart the Schedule dialog keeps the choice | | |
| 16 | After restart the terms and tour do not reappear | | |

## Failures and notes

(One entry per FAIL: what was expected, what happened, screenshot name.)

## Screenshots

Kept on the test PC in %USERPROFILE%\PilotTest\results\screens (sample data
only; not committed).
