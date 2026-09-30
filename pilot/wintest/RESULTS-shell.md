# Pilot 0.2 - Windows check result (app shell)

- **Date:** 2026-09-29, 10:10 PM to 10:57 PM Pacific
- **Machine:** Windows 11 Pro 10.0.26200 (office PC JPPC), 100% display scaling; Python 3.14.3, Node 24.14.0, Inno Setup 6.7.3
- **Commit tested:** local snapshot `dbbcf9d` of the downloaded ZIP (made by `run_checks.ps1`; cannot be compared with GitHub)
- **Summary:** FAIL. The shell works on Windows, but the firm summary takes 53.8 seconds for 750 returns against a 3-second budget, Escape does not close a tooltip, and a return's "Sort Failed" banner neither clears after a good sort nor stays off the firm pages.

## Automated part (run_checks.ps1)

Run with the prompt's `-Tests` list. The prompt's one-line command (`powershell -File ... -Tests a,b,c`) stopped at once: see A1.
The run that counted used `powershell -ExecutionPolicy Bypass -Command "& '.\pilot\wintest\run_checks.ps1' -Tests <the same 14 files>"`.

| Check | Result | Evidence |
|---|---|---|
| tools | PASS | Python 3.14, Node, git, Inno Setup 6.7.3; long paths enabled |
| tree | NOT VERIFIED | ZIP download committed as local snapshot `dbbcf9d` |
| environment | PASS | pip=0 pip-nodeps=0 npm-ci=0 |
| ruff_and_map | PASS | ruff=0 map=0 |
| test_shell.py | **FAIL** | 2 failed, 110 passed (see A3) |
| test_shell_menu.py | **FAIL** | 1 failed, 30 passed, 2 skipped (see A4) |
| test_api.py | PASS | 407 passed (script printed FAIL: see A2) |
| test_registry.py | PASS | 32 passed, 1 warning (script printed FAIL) |
| test_runner.py | PASS | 194 passed, 1 warning (script printed FAIL) |
| test_pilot_ui.py | PASS | 11 passed (script printed FAIL) |
| test_tour.py | PASS | 9 passed (script printed FAIL) |
| test_pilot.py | PASS | 18 passed (script printed FAIL) |
| test_single_source.py | PASS | 172 passed (script printed FAIL) |
| test_layers.py | PASS | 29 passed (script printed FAIL) |
| test_vocab_report.py | PASS | 28 passed (script printed FAIL) |
| test_repo_map.py | PASS | 80 passed (script printed FAIL) |
| test_tripwire.py | PASS | 19 passed (script printed FAIL) |
| test_errors.py | PASS | 83 passed (script printed FAIL) |
| build | PASS | `build-portable\installer\Tax-Document-Tracker-Pilot-Setup-0.2.exe` |
| install | PASS | exit 0; program, Start-menu shortcut and uninstall entry present; per-user, no admin prompt |
| sample_folder | PASS | `%USERPROFILE%\PilotTest\Clients` kept from the 2026-09-28 run (already sorted once) |
| uninstall rows | NOT RUN | `uninstall_checks.ps1` is not part of the shell check; the app stays installed |

Test output: `%USERPROFILE%\PilotTest\results\pytest-<file>.txt`; run log `run_checks.log`; `checks.json`.

**Installer SHA-256:** `A4209EFA429AAD61187B68D9C51D359FAA8B394D3C43FB7FBDAF2464536FB82A`

## Hands-on part (installed app, sample documents only)

| # | Step | Result | What was seen |
|---|---|---|---|
| 1 | Build and install; terms and tour on a fresh install | SKIPPED | Installed silently; the app remembered the 2026-09-28 install, so no terms or tour appeared (not a fresh install). |
| 2 | Four pages from the side panel and Ctrl+1 to Ctrl+4 | PASS | Each key and each side-panel entry opens its page. |
| 3 | Contrast themes (Aquatic, Night sky) | PASS | Checked by Jason. |
| 4 | Dark and Light mode, no white flash | PASS | Checked by Jason. |
| 5 | "Came in Email or Zip" status | SKIPPED | No sample file came in an email or zip; Jason chose to skip making one. |
| 6 | Firm summary speed | **FAIL** | 53.8 s for 750 returns (warm, two runs); 131 s cold; budget 3 s. See F1. |
| 7 | Links and their tooltips | PASS | File name opens Explorer with the working copy selected; return and household names navigate; tips read "Show in File Explorer", "Navigate to Return", "Navigate to Client". |
| 8 | Return years at 1100 px | PASS | Window floor is 1100 x 700. Overview and the household page show "1040 - John A. Smith (2025)" in full; tip "Navigate to Return". Reminders had no drafts and Clients (All) lists households, so no return names there; no sample name is long enough to wrap. |
| 9 | Tooltips | **FAIL** | Hover tip waits briefly; Tab shows it at once; no tip on the search box. Escape does not close a tip. See F2. |
| 10 | Right-click menus end with "Show in File Explorer" | PASS | Parked file, moved file and Received row: each ends with it and each opens Explorer on the right file. |
| 11 | Unfile box | PASS | "Reason (Optional)" with Unfile; the reason reached the return's `_ledger.jsonl` ("unfiled by a person on 2026-09-29 (Windows check test unfile)"). |
| 12 | A failed scheduled sort | PASS | Task run with the Clients folder renamed: Last Result 1. On all four pages "Sort Failed" with only the dismiss cross; side panel "Sort Failed". The household's own Sort ran ("Nothing Done") and the notice stayed. Task run again (Last Result 0), F5: notice gone, side panel "Sorted 10:55 PM". |
| 13 | A return's failed-sort banner | PASS | "Sort Failed: Folder Not Found" (four words, no path). Smith Family has one return, so no bullet lines could show. See F3 for what happened after. |
| 14 | Paused marker | PASS | "Two Years Open; Sorting Paused" in full, wrapped, on Clients and Overview; gone after Active was switched off and F5. See F4 and N2. |
| 15 | Skipped folders | PASS | "1 Folders Skipped"; Show lists "Archive 2024" with "Bad Year". Test folder deleted. |
| 16 | Fallback error log | PARTIAL | Help > Open Error Log opened `tracker-errors.log` in Notepad. "No Error Log Yet" needs a fresh Windows user and was not tried; no fallback `error.log` exists; uninstall not run. |
| 17 | Remote Desktop at 1100 x 700 | SKIPPED | No Remote Desktop session was available. The local window at 1100 x 700 cut nothing off and had no sideways scroll. |

## Failures and notes

### Automated

**A1. The prompt's test command stops before any test runs.** `powershell -File` hands the comma list to the script as one long file name, so the script says "no such test file" and stops. Reproduce: run the command in `PROMPT-shell.md` ('The tests') as written. Fix: give the `-Command "& '.\pilot\wintest\run_checks.ps1' -Tests ..."` form in `PROMPT-shell.md`, or have the script split a single comma-joined value.

**A2. `run_checks.ps1` marks every test file FAIL, even when all its tests pass.** Twelve files report "N passed" with an empty error file and still read FAIL. Likely cause: in Windows PowerShell 5.1 a process started with `Start-Process -PassThru` reports no exit code unless its handle was read before it ended (`run_checks.ps1` lines 145-157), so `Verdict ($r.Proc.ExitCode -eq 0)` is false. Fix: read `$r.Proc.Handle` right after starting each process, or judge by the pytest summary line.

**A3. `tests/test_shell.py`: 2 tests fail on Windows only.** `test_the_harness_stub_speaks_the_apis_vocabulary` and `test_the_harness_stub_replies_have_the_shape_of_the_engines`. Root cause: `_stub_replies` runs the whole stub as `node -e <script>` (`tests/test_shell.py:2334`), which is longer than Windows' 32,767-character command-line limit ("[WinError 206] The filename or extension is too long"). Fix: write the script to a temporary file and run `node <file>`. Until then the stub's vocabulary check is unproven on Windows.

**A4. `tests/test_shell_menu.py`: 1 test fails on a PC that cannot make symbolic links.** `test_reveal_is_refused_when_the_file_is_no_longer_a_file_or_is_a_link`. Root cause: it makes a symbolic link (`tests/test_shell_menu.py:649`) without the "this machine cannot make a symbolic link" skip that the file's two other link tests use (around lines 496-509), and this PC cannot make one without Developer Mode or admin ("[WinError 1314] A required privilege is not held by the client"). Fix: wrap that `symlink_to` in the same try/skip.

### Hands-on

**F1. Firm summary: 53.8 seconds for 750 returns (budget 3 s; sandbox 6.7 s).** How it was measured: the sorted Smith Family household (both trees) was copied byte for byte to 750 households in `%USERPROFILE%\PilotTest\Clients-750`, and `python -m tracker.api firm` (the command behind Overview's counts, from the source the installer was built from) was timed with `TRACKER_SETTINGS_DIR` pointing at a copy of the settings naming that folder. Results: 2-return sample 0.98 s; 750 returns 131.2 s (first run), 53.8 s and 53.8 s (warm); reply 2.34 MB, 750 returns listed. The installed `tracker-api.exe` could not be timed alone (it expects details the shell passes at launch). Overview cannot show its counts before this command finishes, so the on-screen wait is at least this long. This is item 4 in `pilot/HANDOFF.md` ('Open for Jason'): the Windows number says the firm view needs a cache or a leaner `firm`.

**F2. Escape does not close a tooltip.** Reproduce: open a return, click the search box, press Tab (the Sort icon shows "Sort Now"), press Escape: the tip stays. Root cause: `app/renderer/tooltip.js` hides a tip on focus-out, pointer-down, window blur and scroll, but has no Escape key handler. Screenshot: none.

**F3. A return's "Sort Failed" banner outlives a good sort and shows on the firm pages.** Reproduce: rename `Clients\Smith Family`, press Sort on its return ("Sort Failed: Folder Not Found"), rename it back, press Sort again (the return's `Status Report.html` was rewritten at 10:39:08, so the sort succeeded), press F5. Expected (rulings 20 and 28, SPEC-shell 3.5 and 8.4): the notice clears with the record. Seen: it stays on the return, and it also appears on Overview and Clients (`14-overview-paused-marker-and-leaked-banner.jpg`), where step 12 says a failed-sort notice comes only from the scheduled sort. It went away only when the app was restarted, so it looks held in the app's memory rather than read from the record.

**F4. After Add a Return, the page goes blank until F5.** Reproduce: on a return's page choose Client > Add a Return..., Form 1040, Create Return. The two notices show but the page body stays empty (8 seconds and more) until F5 (`14-return-page-after-refresh.jpg` is after F5).

**F5. The schedule-off message uses old words.** After switching the schedule off: "The schedule is off on this computer. Scan still works. Turn it on with the Schedule button." The shell's word is Sort, and Schedule is a Tools menu item, not a button.

**N1. Maximized, the Sort icon shows a Windows "Close" tip.** With the window maximized, hovering the Sort icon shows a plain Windows tooltip "Close" instead of the app's tip; clicking does not close the app. Restored, the app's own tip shows ("Open a Client to Sort" on firm pages). May come from Windhawk, which is installed on this PC; worth a look on another PC. Screenshot: `09-sort-icon-maximized.jpg`.

**N2. Step 14's wording.** Edit Request List shows Active as a tick box labelled "Active — No: Sorting Skips This Return", not a choice to set to "No: Sorting Skips This Return" as `PROMPT-shell.md` says.

**N3. PC restart during the session.** Windows was shut down normally at 10:45:30 PM (Start-menu shutdown, reason "Other (Unplanned)"); the event log shows no crash, no hang and no error in the minutes before. Nothing from this check was running then.

### Sample data changed by this check

- Smith Family: the prior-year return was unfiled (step 11); a 2024 Form 1040 return was added and set inactive (step 14).
- `%USERPROFILE%\PilotTest\Clients-750` (750 copied households) and `%USERPROFILE%\PilotTest\settings-750` remain for a re-measure; delete them when done.
- The schedule was switched on for step 12 and switched off again; the Windows task is gone.

## Screenshots

In `%USERPROFILE%\PilotTest\results\screens` (sample data only; not committed): `01-app-opens.jpg`, `02-ctrl1-overview.jpg`, `02-ctrl2-needs-review.jpg`, `02-ctrl3-reminders.jpg`, `02-ctrl4-clients.jpg`, `07-file-link-explorer.jpg`, `08-overview-1100px.jpg`, `09-sort-icon-maximized.jpg`, `11-unfile-box.jpg`, `12-scheduled-sort-failed-overview.jpg`, `12-cleared-after-good-run.jpg`, `13-return-sort-failed-banner.jpg`, `14-clients-paused-marker.jpg`, `14-overview-paused-marker-and-leaked-banner.jpg`, `14-return-page-after-refresh.jpg`, `15-folders-skipped-bad-year.jpg`.
