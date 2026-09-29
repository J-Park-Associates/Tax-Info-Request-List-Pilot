# Pilot 0.2 Windows check, run 3: narrow (P46, P47)

Only what the restart and scheduled-task fix touched (Jason's test-minimally
preference, CLAUDE.md). Code at commit 95edfe8 or later on `main`.

```
You are running a NARROW Windows check (run 3) for Tax Document Tracker Pilot 0.2 on this computer, for
Jason Park (a CPA, not a programmer - report in plain English). Run 2 passed everything except two bugs,
now fixed on main: (1) after a restart the terms and tour came back; (2) the pilot's scheduled task
vanished before the uninstall. Test ONLY what that fix touched. Do not rerun the whole test suite, the
scan, the tour's content or the badge - they passed in run 2.

SAFETY (unchanged): only the made-up documents under %USERPROFILE%\PilotTest\Clients; never open, list
or read any other folder or document; nothing is sent; do not change code, tag or release; stop and ask
Jason if anything needs administrator rights or would touch a folder outside %USERPROFILE%\PilotTest and
the pilot checkout.

1. CODE. In the pilot checkout used for run 2 (C:\Users\User\Downloads\New folder\pilot-checkout, or C:\pt):
   git checkout main; git pull. Confirm HEAD is 95edfe8 or later and `git status` is clean. Move the old
   %USERPROFILE%\PilotTest\results to results-run2.

2. AUTOMATED (tests in parallel with the build). Run:
     powershell -ExecutionPolicy Bypass -File pilot\wintest\run_checks.ps1 -Tests tests\test_pilot.py,tests\test_tour.py,tests\test_after_install.py,tests\test_api.py,tests\test_single_source.py,tests\test_errors.py,tests\test_layers.py,tests\test_repo_map.py
   Why these: test_pilot and test_tour cover the terms and tour pages; test_after_install covers the new
   one-run-at-a-time lock and the scheduled-task paths; test_api covers the new pilot-record command and
   the schedule commands; test_single_source, test_errors, test_layers and test_repo_map are the guard
   tests the change touched. It builds and silently installs the new installer and keeps the sample
   folder. Record the installer's SHA-256.

3. HANDS-ON (Jason clicks, you record; use computer use only if it is available and Jason agrees):
   a. Open the app. The terms show (a fresh install keeps the old acceptance only if the data folder
      still has it - either is fine; note which). If shown: tick, "I agree. Continue.", then Finish the tour.
   b. Check %LOCALAPPDATA%\tax-document-tracker-pilot\pilot-record.json holds "terms": "1" and
      "tour_seen": true.
   c. Close the app and reopen it normally: no terms, no tour.
   d. Close it and reopen it within about 2 seconds: no terms and no tour. If the terms flash and vanish,
      record it (the durable record working) - that is a pass.
   e. Schedule button: Off, Save; `schtasks /Query /TN "Tax Document Tracker Pilot"` finds no task. Then
      On, first run 06:30, every 4 hours, Save; `schtasks /Query /TN "Tax Document Tracker Pilot" /XML`
      shows 06:30 and PT4H (or PT240M).
   f. Close the app, reopen normally, close, reopen within 2 seconds, close. Run the /Query again: the
      task MUST still be there.
   g. With the app closed, confirm %LOCALAPPDATA%\tax-document-tracker-pilot\after-install.lock does not
      exist.
   If the task is missing at f, copy the lines containing "removed this computer's scheduled task" from
   %LOCALAPPDATA%\tax-document-tracker-pilot\logs\tracker-errors.log (or the debug log beside it) into the
   report.

4. UNINSTALL: powershell -ExecutionPolicy Bypass -File pilot\wintest\uninstall_checks.ps1
   scheduled_task_removed must be PASS with "task existed before uninstall: True".

5. REPORT: write %USERPROFILE%\PilotTest\results\RESULT.md (template: pilot\wintest\RESULTS-TEMPLATE.md;
   mark the rows not rerun as "not rerun - passed in run 2"), then post it on the board:
     gh pr comment 5 --repo J-Park-Associates/Tax-Info-Request-List-Pilot --body-file "%USERPROFILE%\PilotTest\results\RESULT.md"
   with the first line "[WINTEST] PASS" or "[WINTEST] FAIL" and a one-line summary. Then stop.
```
