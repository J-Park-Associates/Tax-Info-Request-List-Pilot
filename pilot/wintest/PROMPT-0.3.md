# Prompt: the Windows check of Pilot 0.3 (Tax Document Console)

Open a fresh Claude Code session in `C:\Users\User\Desktop\Tax-Document-Console-0.3`
(GitHub `main` at `e234c54`, extracted 2026-09-30) and paste everything below the
line. Opus 5.5, default effort.

---

You are running the Windows check of Pilot 0.3, now named **Tax Document
Console**, on this Windows office PC. I am Jason, a CPA, not a programmer:
explain in plain English, lead with the answer, and state the root cause in one
sentence when something breaks.

**Hard rules.**
- Made-up documents only (`%USERPROFILE%\PilotTest`); never touch a real client folder.
- No generative AI reads any document. You run the app on the made-up samples; you never open or read their contents.
- Nothing is sent anywhere.
- Do not edit any file under `tracker/`, `app/`, `tests/`, `tools/` or `docs/`, or `pilot/DECISIONS.md`. The orchestrator session owns the code.
- You may write only `pilot/wintest/RESULTS-0.3.md` and screenshots under `%USERPROFILE%\PilotTest\results-0.3\screens`.
- Do not commit or push.
- Test only what changed (the repo `CLAUDE.md`, "Test minimally"); never run the whole suite.

**Read first (targeted, never whole files):**
- `CLAUDE.md`
- `pilot/SPEC-rename.md` sections 1, 9 and 12.3
- `pilot/handoffs/landing-0.3.md`
- `pilot/wintest/RESULTS-shell.md` (what 0.2 failed and how it was reproduced)
- `pilot/wintest/PROMPT-shell.md` steps 5, 6, 9, 12-14 and 18-22
- `pilot/wintest/RESULTS-TEMPLATE.md`

**Already done by the previous session (do not repeat):**
- The test run and the build. `run_checks.ps1` ran these 18 files in parallel:
  - the 14 shell files of the 0.2 check: `test_shell`, `test_shell_menu`, `test_api`, `test_registry`, `test_runner`, `test_pilot_ui`, `test_tour`, `test_pilot`, `test_single_source`, `test_layers`, `test_vocab_report`, `test_repo_map`, `test_tripwire`, `test_errors`;
  - plus the four the rename changed whose behaviour depends on Windows: `test_after_install`, `test_settings`, `test_scheduling`, `test_pilot_installer`.

  It built `Tax-Document-Console-Setup-0.3.exe` and installed it silently over 0.2. Results: `%USERPROFILE%\PilotTest\results\checks.json`, `run_checks.log` and `pytest-<file>.txt`. Report each file's PASS/FAIL from the pytest summary line, not the script's verdict alone, and quote the installer SHA-256 from `checks.json`.
- Step 18, upgrade over the earlier name. Before the install, 0.2 had the schedule on (06:30, every 240 minutes), the task "Tax Document Tracker Pilot" present, one Start menu entry and one Settings > Apps entry ("Tax Document Tracker Pilot 0.2"). The state before and after the install is in `%USERPROFILE%\PilotTest\results-0.3\before-upgrade.txt` and `after-upgrade.txt`. Judge step 18 from those two files.
- Known from the run (record it; do not rerun):
  - all 18 files passed every test, but `test_api` (438 passed) and `test_runner` (194 passed) read FAIL;
  - the cause: the installer build ran alongside them and wrote `build-portable\pyi-work` into the checkout, and the suite's end-of-run guard ("the session left a new folder in the checkout") failed the two files still running;
  - that is a clash inside `run_checks.ps1`, not the app;
  - the installer SHA-256 is `C02D215A6693F9FF249D4026B4A648BC692D463DC0B533A1AEF8FB16201B7838`.
- After the install, the old task "Tax Document Tracker Pilot" was still present, as expected before the first start. It runs the 0.3 engine inside the kept folder `%LOCALAPPDATA%\Programs\Tax Document Tracker Pilot`. If its 6:30 PM run (or a later one) happened before you start, that is a normal sort of the sample, not a fault.
- **The app has not been started since the install.** Step 19 is its first start; do not open it before you are ready to record step 19.

**The sample data (keep it; say before you change anything):**
- `%USERPROFILE%\PilotTest\Clients`: 22 made-up households (Smith Family, Test Household and 20 more across 1040, 1120, 1120-S, 1065, 1041 and 990), sorted once.
  - Smith Family also has an inactive 2024 return (added in the 0.2 check's step 14).
- `%USERPROFILE%\PilotTest\Clients-750` with `settings-750\settings.json`: 750 copies of one sorted household, for timing.
- `%USERPROFILE%\PilotTest\results-0.2`: the 0.2 check's output; leave it.
- The schedule is **on** (from before the upgrade); its next runs sort the sample on their own.

**Do this, one step at a time, telling me before anything that needs my hands:**

1. Report the automated part: PASS/FAIL per test file, the installer SHA-256, and step 18 (PASS or FAIL from the two state files).
2. **Step 19, first start, and the sign-off (SPEC-rename 12.3).**
   - Start Tax Document Console from the Start menu. If the terms card shows, check four things:
     - "Sign and Accept" stays greyed with the name box empty;
     - it stays greyed with only spaces typed;
     - it turns on once the made-up name "Jane Tester" is typed;
     - after accepting, Help > Terms shows "Signed by Jane Tester on {date}".

     If the terms do not show (an earlier acceptance carries over, ruling P188 Q2), record that and check that Help > Terms shows no signature line.
   - Then check the tasks. `schtasks /Query /TN "Tax Document Console"` should find the task, and `schtasks /Query /TN "Tax Document Tracker Pilot"` none.
   - Then check that the Clients folder, the schedule choice and the column widths are as before.
3. **Step 22, on screen.** The window title, side panel, Help > About and the badge read Tax Document Console / Pilot 0.3, and failure words say "App", not "Tracker". Force a failure only the way `PROMPT-shell.md` step 12 does: rename `%USERPROFILE%\PilotTest\Clients` away, run the scheduled task, then rename it back. You may skip that if step 6 below covers it.
4. **What 0.2 failed, rechecked** (each was fixed in PR #19):
   - **F1, firm speed (step 6).** Time `firm` on `Clients-750` the way `RESULTS-shell.md` F1 says, with the installed 0.3 data. Run it three times: cold, then warm twice. Then time Overview's counts appearing in the app on the 22-household sample. Budget: 3 s for 750 returns (0.2 took 53.8 s warm).
   - **P116, "Email or Zip" (step 5).** It was never seen in 0.2. If no sample file came in an email or zip, ask me before making one. At 1100 px the status must show whole, and the tooltip reads "Came in Email or Zip".
   - **F2, Escape closes a tooltip (step 9):** Tab to the Sort icon, then press Escape.
   - **F3, a return's banner (step 13).** After the folder is renamed back, a good Sort and F5 clear "Sort Failed: Folder Not Found". It never shows on Overview, Needs Review, Reminders or Clients. Then do step 12, the overnight banner, once.
   - **F4, Add a Return (step 14):** the page is not blank afterwards.
   - **F5, schedule-off message:** it says "Sort" and points at the Tools menu.
   - **N1:** with the window maximized, the Sort icon's tip is the app's, not a Windows "Close".
   - **"Nothing Done" and "Held: 1 Files Not Sorted"** on Smith Family 2025: say what the screen now says and why.
5. **Lane 4, new in 0.3:** column headers you can order by, resizable columns, and the visual difference between the return heading, household and file rows. Look at each on Overview, Needs Review and a return page; I judge the look, so show me and ask.
6. **Steps 20 and 21, last, because they uninstall.**
   - Step 20: uninstall 0.3, then install 0.3 again. It goes to `%LOCALAPPDATA%\Programs\Tax Document Console`, and the after-install line says the settings left by the earlier name were copied.
   - Step 21: run `pilot\wintest\uninstall_checks.ps1`; both task names are gone, and the data folder and `settings.json` are left.
   - Then install 0.3 once more so the PC ends with it installed, and ask me whether the schedule should stay on.
7. **Write `pilot/wintest/RESULTS-0.3.md`** from `RESULTS-TEMPLATE.md`. It holds:
   - the commit (`e234c54`) and the installer SHA-256;
   - each check with PASS, FAIL or SKIPPED and one sentence;
   - each failure with the exact steps to reproduce;
   - the screenshot file names;
   - the timings.

   Do not fix any failure. Tell me the file's path and stop.

If a step fails, state the root cause in one sentence, note it, and go on unless it blocks. End with a short list: what to fix, what needs my decision, and whether the build is ready to tag `pilot-0.3` (P140).
