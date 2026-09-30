# Lane 3 build hand-back: SPEC-wincheck-fixes (P128-P134)

- **Written:** 2026-09-30, 12:56 AM Pacific, by the Lane 3 builder.
- **Branch:** `claude/wincheck-fixes` in `C:\Users\User\pl\fixes`, from `main` at 877c7a2.
- **SPEC:** `pilot/SPEC-wincheck-fixes.md`. **Decisions:** P128-P134 in `pilot/DECISIONS.md`.
- **Not pushed. No pull request, no rebase, main not merged in.** This build has had no review yet; a separate reviewer does that.
- **P140 and P155 respected:** no version number changed. None of the new user-visible text names the app, so the new name "Tax Document Console" has no place to appear.

## Items

| Item | State | Root cause (one sentence) | Decision |
|---|---|---|---|
| A1 | Done | `powershell -File ... -Tests a,b` hands the script `a,b` as one value (proved here: count 1 with -File, 2 with -Command). | P128 |
| A2 | Done | Windows PowerShell 5.1 gives a `Start-Process -PassThru` process an empty `ExitCode` unless its `Handle` was read while it ran (proved here on 5.1.26100). | P128 |
| A3 | Done | `_stub_replies` ran the stub as `node -e`, which is over Windows' 32,767-character command line. | P129 |
| A4 | Done | The reveal test made a symbolic link with no skip, and this PC cannot make one. | P129 |
| F2 | Done | Only the last branch of `shellKey` hid a tip, so an Escape taken earlier (the search box with focus, reproduced in the harness) left it showing. | P130 |
| F3 | Done | `passEnded` said a Sort's answer through `outcome()`, which makes window-wide notices that only the dismiss icon removes. | P131 |
| F4 | Done | `createEngagement` drew the new return's state but left the route on the old return, so the return page drew nothing. | P132 |
| F5 | Done | The sentences were written before Scan became Sort and Schedule moved into the Tools menu. | P133 |
| N1 | Investigated; not the app's doing | The window has the standard frame, and the renderer sets no `title`. The "Close" tip is Windows' own caption tip (Windhawk is on that PC). | P133 |
| N2 | Done | The prompt described the Active tick box as a choice. | P133 |
| Nothing Done / Held | Done; owner question Q1 open | A household page sorts through its first return, which on that PC is the inactive 2024 one, and a skip of kind `inactive` had no word. The one waiting file was the sample pile's half-uploaded `W-2 Jane Smith 2025.pdf.tmp.driveupload`. | P134 |

**Open for Jason (SPEC, "Open for Jason"):** Q1, the word for a `no-room` skip. (a) "Nothing Done: Names Too Long." is recommended and built; (b) "No Room for Name" (six words); (c) the bare "Nothing Done".

**Left and flagged (not this SPEC):**
- The runbook's many "Schedule button" lines, which `test_single_source` pins.
- `runner.LAST_PASS_OFF` and `api.SCHEDULE_NOTE`, which are not drawn by the shell.
- Choosing a household page's default return by year or by whether it is active.

## Exact lines changed, for combining lanes (against 877c7a2)

**tracker/api.py**
- After line 475 (end of `SCAN_REASONS`): new lines 476-486, a comment and `SCAN_SKIPPED = {"inactive": "Inactive", "rolled-forward": "Rolled Forward", "no-room": "Names Too Long"}`.
- Old line 1721 (in `_vocab`, `"scan"`): becomes new lines 1732-1733, `"reasons": dict(SCAN_REASONS), "skipped": dict(SCAN_SKIPPED),` then `"complete": SCAN_COMPLETE, "filed": SCAN_FILED,`.
- After old line 4905 (in `_reminder_now`, after `"unsorted": draft.unsorted,`): new lines 4918-4919, a comment and `"unsorted_files": reminder.unsorted_files_in_inbox(engagement) if draft.unsorted else [],`.
- No Email or Zip word was touched.

**app/renderer/shell.js**
- After old line 795 (`async function shellRefresh() {`): new line 796, `forgetSortAnswers();` with its comment.
- After old line 878 (`function shellKey(e) {`): new line 880, `tipKey(e);` with its comment.
- Old lines 898-901 (`if (tipShowing()) { hideTip(); return true; }`) are removed.

**Other files touched:**
- Code and harness: `app/renderer/app.js`, `app/renderer/tooltip.js`, `pilot/harness/app-stub.js`, `pilot/harness/stub.js`.
- Engine words: `tracker/reminder.py`, `tracker/scheduling.py`, `tracker/after_install.py`.
- Check script and prompt: `pilot/wintest/run_checks.ps1`, `pilot/wintest/PROMPT-shell.md`.
- Docs and words: `docs/runbook.md` (line 639), `pilot/wording-shell.tsv` (three rows added at the end), `docs/repo-map.*`.
- Tests: `tests/test_shell.py`, `test_shell_menu.py`, `test_pilot.py`, `test_reminder.py`, `test_api.py`, `test_after_install.py`.

## Gate on this PC (Windows 11, branch head a59ae29)

**Dead code:** `tipShowing()` was removed (no caller left). `ruff`: "All checks passed!". The temporary probe test was deleted before commit.

**Owning tests:** every new test failed before its fix and passes after. The A2 test also fails with the handle read removed; that run printed `2|pass.txt;fail.txt|;`, meaning both exit codes came back empty.

Each file ran in its own process, in parallel. "Exit" is pytest's exit code.

| Test file | Python 3.14.3 (.venv) | Exit | Python 3.11.15 (.venv311) | Exit |
|---|---|---|---|---|
| test_shell | 119 passed | 0 | 119 passed | 0 |
| test_shell_menu | 30 passed, 3 skipped | 0 | 30 passed, 3 skipped | 0 |
| test_pilot | 19 passed | 0 | 19 passed | 0 |
| test_after_install | 73 passed, 3 skipped | 0 | 73 passed, 3 skipped | 0 |
| test_reminder | 205 passed, 1 skipped | 0 | 205 passed, 1 skipped | 0 |
| test_api | 407 passed (17 min 21 s) | 0 | 407 passed (33 min 15 s) | 0 |
| test_layers | 29 passed | 0 | 29 passed | 0 |
| test_single_source | 172 passed | **1** (see below) | 172 passed | **1** (see below) |
| test_repo_map | 80 passed | 0 | 80 passed | 0 |
| test_tripwire | 19 passed | 0 | 19 passed | 0 |
| test_errors | 83 passed | 0 | 83 passed | 0 |
| test_vocab_report | 28 passed | 0 | 28 passed | 0 |

**test_single_source on Python 3.14.** The first 3.14 run of test_single_source had 1 failure. My new app.js comment quoted two vocabulary words, which the file forbids. Commit a59ae29 fixed the comment, and both reruns then gave 172 passed.

**test_single_source exits 1 with every test passing.** The suite's tripwire (decision 185) records "`test_the_app_opens_one_window`: open of the checkout's settings file".
- That test runs the real `app/main.js` under node. In a checkout that has a `.venv`, main.js starts `.venv\Scripts\python.exe -m tracker.api`, which reads the checkout's settings file.
- Proof that it depends on the environment and not on this branch:
  - With `.venv` renamed away, the same test on this branch exits 0.
  - On a clean 877c7a2 checkout with no `.venv`, it also exits 0.
  - This lane did not change `main.js`.
- The daily run on this PC will meet the same tripwire. It needs its own small fix: the test should point `TRACKER_SETTINGS_DIR` at a temporary folder, or run main.js with no `.venv` beside it.

**Quick checks:** `python tools/repo_map.py check` gave "Map is current (345 nodes)". `python tools/vocab_report.py check` gave "Report is current (371 keywords, 66 unreached)". The map was refreshed with `update` and the curated notes were edited for app.js, tooltip.js and reminder.py.

**Checked by hand in the renderer harness (made-up names, real app.js):**
- F2: with the focus in the search box and a hover tip on Sort, Escape hid the tip and cleared the box.
- F3: "Sort Failed: Folder Not Found" showed on the return and household pages, not on Overview or Clients. It went after a good Sort and after F5.
- P134: an inactive skip showed "Nothing Done: Inactive."
- F4 has a static test only, because the harness stub cannot create a return. It needs a hands-on look at the next Windows check.

## Commits (oldest first)

1. 5c6c7ea SPEC and decisions
2. 825ab98 A1, A2, N2
3. 996896a A3, A4
4. 2053c7c F2, first form: a capture-phase listener, dropped in commit 5 to keep SPEC-shell 4.3's single keydown listener
5. d2c3768 F3, F4, F5, P134, F2 final form, map
6. a59ae29 renderer comment fix, map

`git log 877c7a2..HEAD` shows exactly these six. The orchestrator said a second copy of this builder had worked in the same folder; nothing of it is on the branch.

**Map-refresh rule:** commits 1-4 did not refresh the map in the same commit, as the rule asks. Commit 5 refreshed it. I did not rewrite history to fix this.

## Housekeeping to know about

At the start, a background command of mine ran outside this worktree, in `C:\Users\User\Desktop\Tax-Info-Request-List-Pilot-main`:
- It ran `npm ci` in `app\`, which rebuilt `node_modules` from that checkout's own lockfile.
- It left a partial, untracked `.venv311` folder there. The permission check refused my attempt to delete it, so it is still there for Jason to delete.
- That checkout's `pilot/mockup-shell.html` shows as modified at 11:27 PM. My commands did not change that file, so another session did.

## Files the next session needs

- `pilot/SPEC-wincheck-fixes.md` and this file.
- `pilot/DECISIONS.md` rows P128-P134.
- For the next Windows check: steps 9, 12, 13 and 14, plus Create Return (F4), and the reminder sheet's file names on a held return. Test files: the twelve above, through `run_checks.ps1 -Tests` (which also re-proves A1 and A2).
