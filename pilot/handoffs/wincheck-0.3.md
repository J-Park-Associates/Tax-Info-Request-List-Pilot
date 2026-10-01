# Handoff: Windows check of Pilot 0.3, Tax Document Console (2026-09-30)

## Done

- The Windows check of 0.3 ran on the office PC, 2026-09-30, 5:54 PM to 9:00 PM Pacific. Results, reproduction steps, timings and screenshot names: [`../wintest/RESULTS-0.3.md`](../wintest/RESULTS-0.3.md); the prompt it followed: [`../wintest/PROMPT-0.3.md`](../wintest/PROMPT-0.3.md). Both are new and **uncommitted** in this clone (branch `claude/after-0.3`). Verdict: **FAIL; not ready to tag `pilot-0.3` (P140).**
- Two builds were checked:
  - **Before the logo:** ZIP snapshot `c87926f`; the prompt names `e234c54`, which could not be verified. Installer SHA-256 `C02D215A6693F9FF249D4026B4A648BC692D463DC0B533A1AEF8FB16201B7838`. The full hands-on check ran on this build.
  - **The logo build:** `main` at `fe6fedf` (PR #22), local snapshot `8605d3b`. Installer SHA-256 `9F14923AEC1AE4FBE0E7A64FDB1D4739F0C499505E3800794B5DDCDE668FE0EA`. Only the logo's own tests (all passed), the install and the icon were checked; the icon matches `pilot/brand/tax-document-console/app/icon-32.png`.
- **What passed:**
  - **The rename:** the upgrade over the earlier name, the first start (one task under the new name, settings carried over), the uninstall checks, and every name on screen (Tax Document Console / Pilot 0.3).
  - **The 0.2 fixes:** F1 firm speed (1.6 s warm for 750 returns against a 3 s budget; 0.2 took 53.8 s), F3 (a return's banner), F4 (Add a Return), F5 (the schedule-off wording) and N1 (the tip when maximized: it was the Claude window, not the app).
  - **Step 12:** the overnight banner.
- **Not proven:**
  - **F2 (Escape):** skipped at Jason's word; the simulated Escape did not reach the app.
  - **P116 "Email or Zip":** only shows when a document inside a zip belongs to *another* household (decision 143); setting that up was refused by the session's safety check.
  - **"App Failed":** cannot be made by hand on an installed app; covered by tests.
- Nothing was fixed, committed or pushed.

## Left, in order

1. **F7, first: after a fresh install into `Programs\Tax Document Console`, no return can be read.**
   - **What shows:** "Setup Needs Attention" and "Could Not Be Read" on all 27 sample returns. The after-install record holds 1,700 findings, all "the store holds 0 index row(s), the record carries 1" or "…has a status in the record and none in the store".
   - **What the code search found:** the store file is the same one, and its engagement rows exist, but the documents and statuses rows under them are absent. Nothing in the store is keyed to the program folder, so the root cause is not found.
   - **First, the deciding read-only check:** `PRAGMA user_version` and the row counts of `documents`, `engagements` and `admitted_by` in `%LOCALAPPDATA%\tax-document-tracker-pilot\tracker.db` on the office PC (sample data only).
   - **The unproven lead:** the build change makes every row be judged again on its next read (`tracker/store.py:397-418`, 2121). Details and file:line citations are in RESULTS-0.3, F7.
   - **Recovery:** `rebuild_engagement` (`store.py:3146-3245`) should recover each return; export or recover first.
   - Needs a SPEC: this touches the store, the engine layer.
2. **F6: reinstalling the same build after an uninstall leaves the schedule off.** `after_install.launch()` (`tracker/after_install.py:1196-1209`) skips when the program matches the last clean run. The uninstaller removes the task but keeps `after-install.json`, so the task never returns, and the schedule dialog still says "On, next run 22:30". Decision 209 applies (nothing may depend on a person remembering a step).
3. **Lane 4's look (Jason): the Date column sits too far to the right.** With it, from N2:
   - widening a column grows it to the left;
   - the chosen order resets on restart.
4. **The check scripts** (`pilot/wintest/run_checks.ps1`):
   - **A1:** it builds while tests run, so the decision-185 guard fails the files still running;
   - **N7:** it installs while the app may be open, and the silent install aborts with exit 5 (close the app first, or use `CloseApplications`);
   - **N8:** `-Tests` needs `tests\<file>.py` paths, not bare names; the prompt should say so.
5. **Smaller notes** in RESULTS-0.3:
   - N3: step 13's extra line has no bullet;
   - N4: the cold firm summary is 65 s for 750 returns; this is the handoff's "fill the cache at a pass's end";
   - N5: "6:30 AM" sits beside "22:30" in the schedule dialog;
   - a household Sort that does nothing now shows no notice at all; decide whether that is right.
6. **Commit** `pilot/wintest/RESULTS-0.3.md`, `PROMPT-0.3.md` and this file with the next landing.

**Parallel or in order:**
- 1 and 2 both touch the after-install and install path, so 2 waits for 1's SPEC to say whether they share a cause.
- 3 (the renderer) and 4 (the scripts) are independent of both and of each other, so they can run side by side.
- After 1 and 2 land, rerun only steps 19-21 of the check (upgrade, fresh install, uninstall, then reinstall), plus the test files each SPEC names. After 3, Jason looks at lane 4 again.

## State of the office PC

- **Installed:** the logo build (`9F14…0EA`) in `%LOCALAPPDATA%\Programs\Tax Document Console`. It shows F7 on screen.
- **The schedule is off** at Jason's word (`settings.json` `"schedule_enabled": false`; no task under either name).
- **The earlier program folder** `Programs\Tax Document Tracker Pilot` still holds only `settings.json`, by design.
- **Sample data changed by the check:**
  - Test Household gained a 2024 return (inactive) and `W-2 Test 2025.pdf` in Needs You (from a test zip).
  - Smith Family was sorted by hand.
  - Details: RESULTS-0.3, "Sample data changed".
- **Kept for a re-measure:** `%USERPROFILE%\PilotTest\Clients-750` and `settings-750`. The timing leftovers are in the Recycle Bin.
- **Screenshots:** `%USERPROFILE%\PilotTest\results-0.3\screens` (not committed).
- **Desktop:**
  - Kept: this clone and `Tax-Document-Console-0.3-icon` (the logo build and its installer).
  - In the Recycle Bin: the 0.2 snapshot `Tax-Info-Request-List-Pilot-main`.
  - Left for Jason to delete after the check session closes: `Tax-Document-Console-0.3`, which was that session's working folder.

## Files the next session needs

- `pilot/wintest/RESULTS-0.3.md`: F7, F6, L4, A1, N2-N8.
- `tracker/store.py` (lines cited in F7) and `tracker/after_install.py:1196-1209`.
- `pilot/wintest/run_checks.ps1` and `pilot/wintest/PROMPT-0.3.md`.
- `pilot/DECISIONS.md` (P140, P155, P185-P192) and this file.
