# Pilot 0.3 - Windows check result (Tax Document Console)

- **Date:** 2026-09-30, 6:30 PM to 7:50 PM Pacific (the automated part ran 5:54 PM to 6:06 PM in the previous session)
- **Machine:** Windows 11 Pro 10.0.26200 (office PC), Python 3.14, Node, Inno Setup 6.7.3
- **Commit tested:** local snapshot `c87926f` of the downloaded ZIP (made by `run_checks.ps1`). The prompt names `e234c54`; the snapshot cannot be compared with GitHub, so that is NOT VERIFIED.
- **Summary:** FAIL. The rename, the upgrade over the earlier name, the uninstall and the five 0.2 fixes that could be checked hold on Windows, and the firm summary now takes 1.6 seconds for 750 returns (53.8 s in 0.2). But after a fresh install into the new program folder the app cannot read any return (F7: "Could Not Be Read" on all 27, "Setup Needs Attention"), its cause not yet found. Also to fix: reinstalling the same build after an uninstall leaves the schedule off (F6), and the Date column sits too far right (lane 4, Jason). The logo build from `main` `fe6fedf` was then built and installed (section "Logo build"): its tests pass and it carries the approved icon, and F7 remains.

## Automated part (run_checks.ps1, uninstall_checks.ps1)

Run by the previous session with the 14 shell files of the 0.2 check plus the four the rename touched that depend on Windows, each in its own process, alongside the installer build. Each verdict below is read from the pytest summary line.

| Check | Result | Evidence |
|---|---|---|
| tools | PASS | Python 3.14, Node, git, Inno Setup 6.7.3; long paths enabled |
| tree | NOT VERIFIED | ZIP download committed as local snapshot `c87926f` |
| environment | PASS | pip=0 pip-nodeps=0 npm-ci=0 |
| ruff_and_map | PASS | ruff=0 map=0 |
| test_shell.py | PASS | 152 passed |
| test_shell_menu.py | PASS | 30 passed, 3 skipped |
| test_api.py | PASS (script printed FAIL: see A1) | 438 passed |
| test_registry.py | PASS | 35 passed, 1 warning |
| test_runner.py | PASS (script printed FAIL: see A1) | 194 passed, 1 warning |
| test_pilot_ui.py | PASS | 11 passed |
| test_tour.py | PASS | 9 passed |
| test_pilot.py | PASS | 24 passed |
| test_single_source.py | PASS | 179 passed |
| test_layers.py | PASS | 29 passed |
| test_vocab_report.py | PASS | 28 passed |
| test_repo_map.py | PASS | 80 passed |
| test_tripwire.py | PASS | 19 passed |
| test_errors.py | PASS | 83 passed |
| test_after_install.py | PASS | 91 passed, 3 skipped |
| test_settings.py | PASS | 58 passed |
| test_scheduling.py | PASS | 114 passed, 4 warnings |
| test_pilot_installer.py | PASS | 18 passed |
| build | PASS | `build-portable\installer\Tax-Document-Console-Setup-0.3.exe` |
| install | PASS | exit 0; program, Start-menu shortcut and uninstall entry present; per-user, no admin prompt |
| sample_folder | PASS | `%USERPROFILE%\PilotTest\Clients` kept from earlier runs |
| uninstall_ran | PASS | exit 0 (step 21) |
| program_removed | PASS | `%LOCALAPPDATA%\Programs\Tax Document Console` |
| scheduled_task_removed | PASS | before: "Tax Document Console"; after: none under either name |
| data_folder_kept | PASS | `%LOCALAPPDATA%\tax-document-tracker-pilot` |
| clients_folder_kept | PASS | `%USERPROFILE%\PilotTest\Clients` |
| settings_kept | PASS | `settings.json` there before and after |

Test output: `%USERPROFILE%\PilotTest\results\pytest-<file>.txt`, `run_checks.log`, `checks.json`, `uninstall.json`.

**Installer SHA-256:** `C02D215A6693F9FF249D4026B4A648BC692D463DC0B533A1AEF8FB16201B7838` (rechecked before the step 20 reinstall: same).

## Hands-on part (installed app, made-up sample documents only)

| # | Step | Result | What was seen |
|---|---|---|---|
| 18 | Upgrade over the earlier name | PASS | From `before-upgrade.txt` / `after-upgrade.txt`: one Start-menu entry, "Tax Document Console"; one Settings > Apps entry, "Tax Document Console 0.3"; no desktop icon before or after; program kept in `Programs\Tax Document Tracker Pilot` (ruling R3); settings unchanged; old task still present before the first start, as expected. The old task ran its 6:30 PM sort with the 0.3 engine before the first start (Last Result 0). |
| 19 | First start: terms and sign-off (SPEC-rename 12.3) | PASS | No terms card: the earlier acceptance carried over (P188 Q2). Help > Terms reads "A test edition of Tax Document Console…" and shows no "Signed by" line, no name box and no sign button. The blank, spaces-only and "Jane Tester" checks could not run because the card did not show; they are covered by `test_pilot.py` (24 passed). |
| 19 | First start: tasks | PASS | `schtasks /Query /TN "Tax Document Console"` finds the task (06:30, every 4 hours); `"Tax Document Tracker Pilot"` finds none. |
| 19 | First start: clients folder, schedule, column widths | PASS | Same Clients folder (the 22 households show); Tools > Schedule shows On, 6:30 AM, every 4 hours. 0.2 had no adjustable columns, so there were no earlier widths; a width changed in 0.3 survived a restart (lane 4). |
| 22 | On screen: the name | PASS | Window title "Tax Document Console — J Park & Associates"; side panel "Tax Document Console"; badge "Pilot 0.3"; Help > About "Tax Document Console / Pilot 0.3". No "Tracker" seen on any screen. |
| 22 | On screen: "App Failed" | SKIPPED | The renamed-folder failure correctly reads "Sort Failed". "App Failed" shows only when a command fails before the app has named its data folder, which cannot be made by hand on an installed app (the 0.2 check's step 16). `test_shell_menu.py` and `test_single_source.py` cover it, and both passed. |
| F1 | Firm summary speed (step 6) | PASS (warm) | `python -m tracker.api firm` on `Clients-750` from the checkout, with its own data folder (`settings-750\data-0.3`): 65.14 s cold (first run, builds the cache), then 1.67 s and 1.57 s warm; reply 2.44 MB each, exit 0. Budget 3 s; 0.2 took 53.8 s warm. On screen, Overview's counts appeared within 0.5 s on the 22-household sample. See N4 for the cold run. |
| P116 | "Email or Zip" status (step 5) | PARTIAL | With Jason's yes, a zip holding a copy of a made-up W-2 went into Test Household's inbox. The sort opened it and the W-2 came in under Needs You, "No Client Name Found". "Email or Zip" appears only when a document inside an email or zip would belong to another household (decision 143, `tracker/filer.py:5231`). A second zip set up for that case was refused by the session's safety check, so the tag, its 1100 px fit and its tooltip were not seen. |
| F2 | Escape closes a tooltip (step 9) | SKIPPED | Tab to the Sort icon shows "Sort Now" at once; the tip stayed after Escape, but a simulated Escape also did not clear the search box, so the key may not have reached the app. Jason chose to skip a hand check. The fix is in `app/renderer/tooltip.js:121` (`tipKey`). |
| F3 | A return's banner (step 13) | PASS | `Clients\Smith Family` renamed away, Sort on its 2025 return: "Sort Failed: Folder Not Found" and "Smith Family 2024 1040 - John A. Smith: Sort Failed: Folder Not Found"; no folder path. Not on Overview, Needs Review, Reminders or Clients (only "1 Folders Skipped" there). After renaming it back, Sort cleared both lines, and F5 kept them cleared. See N3. |
| 12 | The overnight banner | PASS | App closed, `PilotTest\Clients` renamed to `Clients-away`, task run: Last Result 1. Renamed back, app opened: "Sort Failed" with only the dismiss cross; side panel "Sort Failed". Task run again (Last Result 0), F5: notice gone, side panel "Sorted 7:38 PM". |
| F4 | Add a Return (step 14) | PASS | Test Household, Client > Add a Return…, Form 1040, Tax Year 2024, Create Return: the app went straight to the new 2024 return's page with its five requests and "Two Years Open; Sorting Paused". The page was not blank. Set inactive through Edit Request List (Ctrl+E), F5: the notice went. |
| F5 | Schedule-off message | PASS | "The schedule is off on this computer. Sort still works. Turn it on in Tools > Schedule." Switched back on afterwards. |
| N1 | Maximized Sort icon tip | PASS | With the app in front and maximized, the Sort icon shows the app's own "Sort Now". An earlier "Close" tip came from the Claude window behind the pointer, not the app (Jason). |
| — | "Nothing Done" and "Held: 1 Files Not Sorted", Smith Family 2025 | NOTED | The household's Sort ran (its Status Report was rewritten at 7:33 PM) and showed no notice at all. The reminder side sheet reads "Held: 1 Files Not Sorted" and names the one file holding it, `W-2 Jane Smith 2025.pdf.tmp.driveupload`: a half-uploaded file a sync tool left in the inbox, which the sort leaves alone. That matches P134: the held reminder names the files holding it. |
| L4 | Column headers, resizing, row levels (lane 4) | FAIL (Jason) | Ordering by a header works (Client, A to Z, arrow, tip "Sort by Client"). Resizing works and survives a restart. Return headings, households and file rows are visibly different on Needs Review and the return page. Jason judged the look: **the Date column is too far to the right.** See N2 for two smaller notes. |
| 20 | Fresh install | **FAIL** (F7) | The carry-over itself works, but afterwards no return can be read; see F7. Uninstalled (exit 0; only `settings.json` left in the old folder; both tasks and the Apps entry gone). Installed again: it went to `%LOCALAPPDATA%\Programs\Tax Document Console`. At first launch: "Copied the settings file left by the earlier name (…\Tax Document Tracker Pilot\settings.json) to …\Tax Document Console\settings.json, so the clients folder and the schedule choice carry over; the earlier file was left where it was." Task "Tax Document Console" present; the earlier name absent. |
| 21 | Uninstall checks | PASS | `uninstall_checks.ps1`: all six rows PASS (above). |
| — | Reinstall after step 21 | **FAIL** | Installed and started again: no task under either name, although `settings.json` says the schedule is on. See F6. |

## Failures and notes

### Automated

**A1. `run_checks.ps1` fails two files whose tests all passed.** Root cause: the installer build runs alongside the tests and writes `build-portable\pyi-work` (and `build-portable\dist`) into the checkout. The suite's end-of-run guard (decision 185, "the session left a new folder in the checkout") then fails whichever files are still running, here `test_api.py` (438 passed) and `test_runner.py` (194 passed). Reproduce: run `run_checks.ps1 -Tests test_api,test_runner`, which builds the installer while they run. This is a clash inside the script, not the app. Fix: build after the tests finish, or point the build's work folders outside the checkout.

### Hands-on

**F6. Reinstalling the same build after an uninstall leaves the schedule off.** Root cause: the first-launch step skips when this program is the one that last ran it cleanly (`tracker/after_install.py:1196-1209`, `launch()`). The uninstaller removes the task but keeps that note (`%LOCALAPPDATA%\tax-document-tracker-pilot\after-install.json`), so the identical build sees nothing changed and never registers the task again. Reproduce: with 0.3 installed and the schedule on, run `uninstall_checks.ps1` (or uninstall from Settings > Apps); install the same `Tax-Document-Console-Setup-0.3.exe`; start the app; `schtasks /Query /TN "Tax Document Console"` finds nothing, while `settings.json` still has `"schedule_enabled": true`. Nothing on screen says the schedule is not running. Tools > Repair Schedule is the manual way back. Decision 209 says a step needed after installing must never depend on a person remembering it.

**F7. After a fresh install into the new program folder, no return can be read.** Seen at 8:43 PM, on the copy installed after step 21 (first launched at step 20, 7:46 PM): Overview shows "Setup Needs Attention", and all 27 returns read "Could Not Be Read" (Need a Person 27, Waiting 0). At 7:38 PM, on the same data folder under the old program folder, every return read normally. The after-install record (`%LOCALAPPDATA%\tax-document-tracker-pilot\after-install.json`, run at 7:46:32 PM) holds 1,700 findings of one kind, for example "1040 - Tunde Adeyemi: the store holds 0 index row(s), the record carries 1" and "…request A01 has a status in the record and none in the store". The store (`tracker.db`, 40.7 MB) is the same file in the same data folder, last written at 7:46:32 PM. Installing the logo build (below) re-ran the after-install step at 8:52:57 PM with the same 1,700 findings, and the screen is unchanged. Root cause: not found. A read-only search of the code found nothing that keys the store to the program folder: the store's engagement rows exist (otherwise the check says "does not hold this engagement", `tracker/store.py:3292`), but the documents and statuses rows under them are absent (`store.py:3367`, `_check_documents`). Unproven lead: the build change makes every row be judged again on its next read (`store.py:397-418`, `_judge_the_applied_lines` 2121), and a refusal there would show "Could Not Be Read" (`api.py:5731-5734`). That would explain the screen but not the zero rows. The deciding check is a read-only count of the store's tables (`PRAGMA user_version`; `documents`, `engagements`, `admitted_by`), left to the code session because the store holds the sample's client records. `rebuild_engagement` (`store.py:3146-3245`) should recover each return. Reproduce: on a PC that had "Tax Document Tracker Pilot" installed and sorted, upgrade it to 0.3, uninstall 0.3, install 0.3 fresh (it goes to `Programs\Tax Document Console`), start it, open Overview. Screen: `F7-setup-needs-attention-could-not-be-read.jpg`.

**N2. Lane 4, smaller notes.** Widening the Client column grows it to the left (Return gets narrower; the Status edge stays put), not to the right as dragged. The order chosen by clicking a header resets on restart, while widths are kept. Screens: `L4-overview-client-column-resized.jpg`, `L4-width-kept-after-restart.jpg`.

**N3. Step 13's extra line has no bullet.** `PROMPT-shell.md` step 13 says each other return's line begins with a bullet; it reads "Smith Family 2024 1040 - John A. Smith: Sort Failed: Folder Not Found" with no bullet. Screen: `13-return-sort-failed-banner.jpg`.

**N4. The first firm summary after a change is still slow.** 65 s cold for 750 returns while it builds the cache; warm runs are 1.6 s. This is the handoff's open follow-up, "fill the cache at a pass's end" (`pilot/handoffs/landing-0.3.md`, Left item 3).

**N5. The schedule dialog mixes clock styles.** "First Run At" shows "6:30 AM", and the line under it says "Next run: today at 22:30". Screen: `19-schedule-carried-over.jpg`.

**N6. Two of this session's actions were refused by its safety check.** A read of the pilot record and the app's stored column widths (to compare before and after), and a second P116 zip that copied one household's file into another's inbox. Neither was retried.

### Sample data changed by this check

- Test Household: `Test W-2 2025.zip` went into `Drop files here` (a copy of a made-up Smith W-2, renamed); the sort opened it, and `W-2 Test 2025.pdf` now waits in Needs You. A 2024 Form 1040 return was added and set inactive.
- Smith Family: sorted by hand twice (Status Report rewritten); its client folder was renamed away and back (step 13).
- `PilotTest\Clients` was renamed away and back (step 12); the scheduled task ran three times this evening.
- The timing and zip leftovers (`results-0.3\f1`, `results-0.3\p116`, `settings-750\data-0.3`) were moved to the Recycle Bin at Jason's word. `Clients-750` and `settings-750` remain.
- The schedule is **off** at Jason's word (Tools > Schedule > Off; `settings.json` `"schedule_enabled": false`, no task under either name).
- The PC ends with the logo build installed in `%LOCALAPPDATA%\Programs\Tax Document Console`.

## Logo build (main `fe6fedf`, after PR #22)

Built in a separate folder, `Desktop\Tax-Document-Console-0.3-icon` (ZIP of `fe6fedf`, local snapshot `8605d3b`). Only the test files the logo change touched were run, as `pilot/SPEC-icon.md` names them, in parallel.

| Check | Result | Evidence |
|---|---|---|
| tools, environment, ruff_and_map | PASS | as above; ruff=0 map=0 |
| test_build.py | PASS | 33 passed |
| test_pilot_installer.py | PASS | 20 passed |
| test_shell.py | PASS | 153 passed |
| test_shell_menu.py | PASS | 30 passed, 3 skipped |
| test_single_source.py | PASS | 179 passed |
| test_layers.py | PASS | 29 passed |
| test_repo_map.py | PASS | 80 passed |
| build | PASS | `Tax-Document-Console-Setup-0.3.exe`, SHA-256 `9F14923AEC1AE4FBE0E7A64FDB1D4739F0C499505E3800794B5DDCDE668FE0EA` |
| install (by `run_checks.ps1`) | FAIL, not the build's fault | exit 5: the app was open from the previous step, so the silent installer found its files in use, chose Abort and rolled back (`install.log`: "RestartManager found an application using one of our files … Defaulting to Abort … Rolling back changes"). See N7. |
| install (app closed) | PASS | exit 0; the schedule stayed off and no task was made. |
| The icon | PASS | The installed program's icon is the approved blue folder with the gold check, the same as `pilot/brand/tax-document-console/app/icon-32.png` (`ICON-installed-exe.png`). The title bar shows it. The Start-menu shortcut and the Settings > Apps entry take their icon from the program. The taskbar icon was too small to judge on screen (`ICON-logo-build-window.jpg`). |
| F7 | Still FAIL | The after-install step ran again at the build change (8:52:57 PM) with the same 1,700 findings; Overview is unchanged. |

**N7. A silent install aborts while the app is open.** `run_checks.ps1` installs while the app may still be running, and with `/SUPPRESSMSGBOXES` the installer's "files in use" choice defaults to Abort. Fix: close the app before installing in `run_checks.ps1`, or let the installer close it (`CloseApplications`, or `/CLOSEAPPLICATIONS` on the command line).

**N8. `run_checks.ps1 -Tests` takes file paths, not names.** `-Tests test_build,…` stopped with "no such test file: test_build" before any test ran; `tests\test_build.py,…` worked.

## Screenshots

In `%USERPROFILE%\PilotTest\results-0.3\screens` (sample data only; not committed): `19-first-start-overview.jpg`, `19-help-terms-top.jpg`, `19-help-terms-no-signature.jpg`, `19-schedule-carried-over.jpg`, `22-help-about.jpg`, `09-tip-stays-after-escape.jpg`, `N1-sort-icon-maximized-app-tip.jpg`, `held-reminder-smith-2025.jpg`, `F5-schedule-off-message.jpg`, `13-return-sort-failed-banner.jpg`, `13-overview-no-banner.jpg`, `13-needs-review-no-banner.jpg`, `13-reminders-no-banner.jpg`, `13-clients-no-banner.jpg`, `13-cleared-after-sort-and-f5.jpg`, `12-scheduled-sort-failed-overview.jpg`, `12-cleared-after-good-run.jpg`, `L4-overview-ordered-by-client.jpg`, `L4-overview-client-column-resized.jpg`, `L4-needs-review.jpg`, `L4-return-page-smith-2025.jpg`, `L4-width-kept-after-restart.jpg`, `F4-add-return-page-not-blank.jpg`, `P116-zip-file-needs-you.jpg`, `F7-setup-needs-attention-could-not-be-read.jpg`, `ICON-installed-exe.png`, `ICON-logo-build-window.jpg`.

## Timings

| What | Time |
|---|---|
| `firm`, 750 returns, cold (builds the cache) | 65.14 s |
| `firm`, 750 returns, warm (twice) | 1.67 s, 1.57 s |
| Overview counts on screen, 22 households | under 0.5 s |
| 0.2, for comparison | 131.2 s cold, 53.8 s warm |
