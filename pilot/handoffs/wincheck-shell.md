# Handoff: Windows check of the app shell (2026-09-29)

## Done

- The Windows check of the shell ran on the office PC (JPPC), 2026-09-29, 10:10-10:57 PM Pacific. Results, reproduction steps and screenshot names: [`../wintest/RESULTS-shell.md`](../wintest/RESULTS-shell.md). Verdict: FAIL; not ready to tag pilot-0.2.
- Installer SHA-256 `A4209EFA429AAD61187B68D9C51D359FAA8B394D3C43FB7FBDAF2464536FB82A` (local snapshot `dbbcf9d` of a ZIP download).
- Jason's two rulings after the check, logged in [`../DECISIONS.md`](../DECISIONS.md):
  - **P115** - build a cache for the firm view, and make the repository faster.
  - **P116** - "Came in Email or Zip" becomes short tag words that fit the 160px status column (working words "Email or Zip"); the full sentence stays in the hover tip.
- Nothing was fixed. These files, and decisions P115-P117, are on branch `claude/wincheck-shell-results` (from `main` at `877c7a2`, which holds the same code the check tested). P117 accepts the shell's open defaults and keeps O4.

## Left (three jobs; each gets its own SPEC and session)

1. **SPEC-firm-speed (P115).** The firm view's `firm` command (`tracker/api.py`, `_firm_draft` near line 5312 per `shell-final-review-A.md`) takes 53.8 s warm and 131 s cold for 750 returns on Windows (budget 3 s, SPEC-shell 9.2). Profile first; do not guess where the time goes. Then specify the cache: what it keys on, how it knows a return changed (the record, the inbox, the working folder), where it lives (the tracker's data folder, never a client tree, decision 186), and what the screen shows while it fills. "The repository faster" is in the same SPEC: `test_api.py` took 598 s and `test_runner.py` 268 s on this PC; measure before changing either. No routing change, and the backtest baseline may not drop.
   - Re-measure the way the check did: copy one sorted sample household (both trees) to 750 households under `%USERPROFILE%\PilotTest\Clients-750`, point `TRACKER_SETTINGS_DIR` at a folder holding a copy of `settings.json` whose `clients_root` names that folder, and time `python -m tracker.api firm` three times. The copy is still on the office PC.
2. **SPEC-email-zip-tag (P116).** Shorten the status words in the vocabulary (`tracker/api.py` holds the screen words) and whatever renders them (`app/renderer/`); keep the full sentence as the tooltip; update `wording-shell.tsv`, the vocabulary report and the tests that pin the words. Owner question, if any: the exact two or three words (working words "Email or Zip").
3. **SPEC-wincheck-fixes.** From `RESULTS-shell.md`:
   - A1: the command in `wintest/PROMPT-shell.md` uses `-File`;
   - A2: `run_checks.ps1` reads no exit code from `Start-Process -PassThru`;
   - A3: `tests/test_shell.py:2334` passes the stub through `node -e`, too long for Windows;
   - A4: `tests/test_shell_menu.py:649` makes a symbolic link with no skip;
   - F2: Escape does not close a tooltip (`app/renderer/tooltip.js`);
   - F3: a return's "Sort Failed" banner outlives a good sort and shows on firm pages;
   - F4: the page is blank after Add a Return until F5;
   - F5: the schedule-off message says "Scan" and "Schedule button";
   - N2: step 14's wording in `PROMPT-shell.md`.
   - **Added after the check (Jason, 2026-09-29, 11 PM):** on the Smith 2025 return a household Sort showed a bare "Nothing Done" (`SCAN_NOTHING_DONE_BARE`, `tracker/api.py:460`: a skip whose kind has no approved word), and the reminder sheet reads "Held: 1 Files Not Sorted" with all four stages greyed (`INBOX_HELD_SUMMARY`, `tracker/reminder.py:335-345`: a file still in Drop files here holds every draft). Neither says why, and the app's own Sort writes nothing to `runs.log` or `tracker-errors.log` that would. Find the skip's kind (candidates: the 2024 return added in step 14, set inactive; the scheduled pass that failed at 10:53; the lock), decide whether it needs a word, and say on the reminder sheet which file holds the draft. A "Nothing Done" may also be the stale in-memory notice of F3.

**Parallel or in order:** 1 and 3 can run side by side (different files, except that both may touch `tracker/api.py`: flag the overlap on the board). 2 and 3 both touch the screen words in `tracker/api.py`, so 2 lands before 3 edits those words. After all three land, rerun the Windows check steps 5, 6, 9, 12 and 13 only, with the test files each SPEC names.

## Files the next session needs

- `pilot/wintest/RESULTS-shell.md` (the findings and how to reproduce them)
- `pilot/DECISIONS.md` rows P115 and P116
- `pilot/SPEC-shell.md` sections 3.5, 8.4, 9.2 and 16
- `pilot/handoffs/shell-S8a-review-3.md` ('Size and cost', the sandbox measurement)
- `pilot/HANDOFF.md` 'Open for Jason' items 3a, 4 and 5 (4 and 5 now answered by P115 and P116)
- Node for each touched module: `python tools/repo_map.py show tracker/api.py`, and the same for `tracker/reminder.py`, `app/renderer/tooltip.js` and `app/renderer/shell.js`

## On the office PC after this check

- `%USERPROFILE%\PilotTest\Clients` (Smith Family: prior-year return unfiled then refiled by Jason, an inactive 2024 return, one file waiting in its inbox), `Clients-750`, `settings-750`, `results\screens`.
- The pilot app is installed; its schedule is off and the scheduled task is removed.
- A read-only `state` probe from the source copy was refused ("this machine did not write it"; nothing applied): the source checkout and the installed app keep different machine records, so probe the sample with the installed app, not the checkout.
