# Review: claude/wincheck-fixes (SPEC-wincheck-fixes, P128-P134)

- **Reviewer:** Lane 3 reviewer (did not build this change or write its SPEC).
- **Branch reviewed:** `claude/wincheck-fixes` at c712034, 7 commits on main 877c7a2, 25 files.
- **Against:** `pilot/SPEC-wincheck-fixes.md`, `pilot/handoffs/wincheck-fixes-build.md`, RESULTS-shell (A1-A4, F2-F5, N1, N2) and wincheck-shell job 3 "Added after the check" (read in the results clone, read only).
- **Counts:** 2 MUST, 5 SHOULD, 4 NIT.

## MUST

### M1. A retried (or dismissed) Sort that fails the same way again shows nothing at all
`app/renderer/app.js:2305-2312` (`forgetSortLine`) with `app/renderer/app.js:2272-2277` (`keepSortAnswer`) and the keyed-notice rule at `app/renderer/app.js:253-261` (`keyedNotice`).

- **What happens:** the Sort answer is shown through `syncNotices("sort", ...)`, which uses keyed notices. A keyed notice deliberately stays silent when its key already holds the same sentence ("dismissed, it does not come back on the next draw").
- **The problem:** dismissing the notice, or pressing its Retry, calls `dismissNotice` and `forgetSortLine`. Neither one removes the key from `keyedNotices`.
- **The result:** the retried Sort fails with the same sentence, and `keyedNotice` returns without drawing it. The person pressed Retry, the Sort failed again, and the screen says nothing.
- **Proved** with a node probe on the branch's real functions (temp folder):
  - after the first failure, one notice: "Sort Failed: Folder Not Found";
  - after Retry fails the same way, no notice.
- **Before the fix:** `notice()` was used, so the failure showed again. This is a regression, and it breaks "fail loudly".
- **Why the tests miss it:** the owning tests (`test_a_sorts_answer_shows_only_on_its_own_clients_pages`, `test_a_later_sort_or_f5_takes_a_sorts_answer_away`) fake `syncNotices`, so the keyed-notice rule is never run.

**Fix:**
1. In `keepSortAnswer`, clear the keys of every path in `ran` and of `asked` before calling `showSortAnswers()`. For example, `for (const key of [...keyedNotices.keys()]) if (key.indexOf("sort:") === 0 && pathsOf(key) matches) keyedNotices.delete(key);`. At minimum, `forgetSortLine` must `keyedNotices.delete(key)` for the dismissed key.
2. Add a node test that lifts `notice`, `keyedNotice`, `clearNotice`, `syncNotices`, `dismissNotice` and the four sort-answer functions. It should run fail, dismiss (and Retry), then the same failure again, and assert that the notice is back.

### M2. The household-page Sort still picks the inactive return, and the SPEC's reason for leaving it is false
- **SPEC:** `pilot/SPEC-wincheck-fixes.md:236-238` ("The list carries no active flag").
- **The claim is untrue.** List entries carry `active` and `superseded_by`: `app/renderer/pages.js:622` already reads `one.active === false` and `one.superseded_by` to draw "Inactive" and "Rolled Forward".
- **Where the choice is made:** a household or year page picks its return at `app/renderer/shell.js:257` (`own.find(active) || own[0]`), and `runScan` asks for that return.
- **What staff still see:** exactly the reported case. Sort on the Smith household page reports on the inactive 2024 return, now as "Nothing Done: Inactive." That reads as if the Sort did nothing, but the same pass sorted the active 2025 return.
- **The ruling rests on a false fact,** so the root cause of the "Added after the check" item is left in place.

**Fix (build detail, not an owner question):**
- `shell.js:257`: `path = (own.find((one) => one.path === active) || own.find((one) => one.active !== false && !one.superseded_by) || own[0]).path;`
- A test in `tests/test_shell.py`: lift `shellOpenState` with a household of an inactive 2024 and an active 2025 return. The 2025 return is chosen.
- Correct SPEC section 7's "Considered and left" paragraph and the P134 row.
- Keep `SCAN_SKIPPED`: it is still right when the return itself is asked for.

## SHOULD

### S1. The whole failure is no longer passed on
- **Where:** `app/renderer/app.js:2217-2218` and `2295-2296`.
- **What changed:** the Sort's pass-level failure is reduced to `{sentence, kind}`.
  - Before, `notice(ended.failure, ...)` kept `identifier`, which outlines the refused row.
  - It also kept `lock`: a `kind: "locked"` failure from `api._failure_of` carries `lock`, and `notice()` calls `showLock(failure.lock)`.
  - A locked pass therefore no longer opens the lock notice and its watch.
- **Fix:** keep the failure whole, `answer.push({ ...failure, kind: failure.kind || "failed", retry: runScan })`. In `showSortAnswers`, pass `failure: { ...line }` without `retry` and `gone`, so `identifier` and `lock` reach `notice()`.

### S2. A good Sort of a return that is no longer on screen now says nothing
- **Where:** `app/renderer/app.js:2244-2256`.
- **Before:** when `!shown` (the person moved to another return while the pass ran), even an "ok" summary was a notice, `"{label}: Pass complete - Filed 3. ..."` (decision 193 §8: "so nothing vanishes").
- **Now:** `said.cls === "ok"` drops it.
- **The SPEC doesn't cover this:** it says "What was a toast-free 'ok' says nothing, as today", which is only true for the shown return.
- **Fix, either:**
  - keep the `!shown` ok line as a `warning`-kind answer line, as before but scoped to its household; or
  - record the change as a ruling in SPEC section 4 and the P131 row.

### S3. F4 has only a static test, and a behaviour test is possible
- **Where:** `tests/test_shell.py:2693-2702` (`test_create_return_goes_to_the_new_returns_page`).
- **Why it's possible:** `run_shell` already lifts app.js functions with fakes.
- **Fix:** lift `createEngagement` plus `pagesRoute` (pages.js), with fakes for `call` (it returns `{state:{paths:{engagement:"new"}}, list, created}`), `adoptList`, `renderFor`, `select`, `closeDialog` and a recording `shellGo`. Start on another household's return route, and assert `shellGo` got `{level:"return", ret:"new", household:<new's>}`, with the "return created" notice said after it. The harness stub's missing create is not needed for this.

### S4. The `passEnded` line-building has only a string-match test
- **Where:** `tests/test_shell.py:2680-2691`.
- **What's untested:** the label prefix on the first line, the splitting of multi-line summaries, and `retry` only on a pass-level failure. They are checked by string presence only.
- **Fix:** add a node test that lifts `passEnded` with fakes (`scanDone`, `call`, `adoptList`, `showReturn`, `keepSortAnswer` as a recorder) for:
  - an error ending, which gives one failed line with `retry`;
  - a not-shown warn summary, which gives a `"{label}: "` prefix on its first line only;
  - an ok summary, which gives no lines.

### S5. Out of this lane, but the daily run will hit it: the decision-185 tripwire in `test_single_source`
- **Builder's claim verified.** Both interpreters give "172 passed" with exit 1. The trip is `test_the_app_opens_one_window (call): open of the checkout's settings file`.
  - `app/main.js` is unchanged by this branch.
  - At launch it spawns `SOURCE_PYTHON` (`app/main.js:34-36`, the checkout's `.venv`) whenever that file exists (`app/main.js:290`), with `TRACKER_SETTINGS_DIR: SETTINGS_DIR` (`app/main.js:292`), which is the repo root from source (`app/main.js:41`).
- **The builder's suggested fix will not work.** A test cannot redirect it with `TRACKER_SETTINGS_DIR`, because main.js overwrites that variable.
- **Proper fix:** at `tests/test_single_source.py:221-223` (the `_ELECTRON_STUB`'s `Module._load` hook), also answer `request === "child_process"` with a stub whose `spawn` records the call and returns an inert EventEmitter child (`stdout`/`stderr` emitters, `kill(){}`). The one-window test then never starts the real tracker.
- **Scope:** give it its own small SPEC or lane item. It is not this branch's change.

## NIT

- **N-a. The count and the names come from two walks.** `tracker/api.py:4917-4919`: the card's `unsorted` comes from the draft's walk and `unsorted_files` from a second walk, so the card can disagree if a file lands in between, despite the docstring's "can never disagree" (`tracker/reminder.py:1418-1420`). Fix: send `"unsorted": len(files)` when `files` is taken, or word the docstring as the module's claim only.
- **N-b. Two words are restated, not referenced.** `tracker/api.py:482-486`: `SCAN_SKIPPED` restates "Inactive" and "Rolled Forward" rather than referencing `SCREEN["inactive"]` and `SCREEN["rolled"]` (`tracker/api.py:1331-1332`). The test pins their equality, but a single source is better. Fix: build `"skipped"` in `_vocab()` as `{"inactive": SCREEN["inactive"], "rolled-forward": SCREEN["rolled"], "no-room": SCAN_NO_ROOM}`.
- **N-c. Escape doesn't reach `tipKey` while the tour or the terms card is open.** `app/renderer/tour.js:154-157` and `app/renderer/pilot.js:181-185` capture Escape and stop it, so it never reaches `shellKey`/`tipKey`, and a tip over those cards survives Escape. Fix: call `tipKey(e)` first in both handlers (or `hideTip()` on their Escape).
- **N-d. The map was not refreshed in the same commit.** Commits 825ab98, 996896a and 2053c7c changed code without refreshing the map (the handoff says so). History can't be fixed without a rewrite, which is forbidden. Note it for the landing; the head is current.

## Verified as claimed

- **A1 is real and fixed.** Isolated on this PC (PowerShell 5.1.26100.9444), `-File x.ps1 -Tests a,b` gives count 1 (`a,b`), and `-Command "& ..."` gives count 2. The branch's `Split-TestList`, lifted and run under `-File`, gives count 2, trims the items, and gives count 0 for no list.
- **A2 is real and fixed.** Without a `Handle` read, `ExitCode` comes back empty; with it, the real code. The owning test's driver, run with the branch's helpers, prints `2|pass.txt;fail.txt|0;3`. With the `$null = $proc.Handle` line removed it prints `...|;`, so the test fails if the fix is reverted.
- **A3** (the stub runs from a file) and **A4** (the folder half is checked first, the link half skips) are correct. Both tests run on this PC.
- **F2:** `tipKey` is called first in `shellKey`, never consumes the key, and `tipShowing` is gone with no caller left. Both tests fail without the fix. (N-c above is the only gap.)
- **F3:** the scoping is correct for route changes, firm pages, F5, a later good Sort and dismiss, apart from M1, S1 and S2. The scheduled sort's `last-sort` notice is untouched.
- **F5:** `SCHEDULE_OFF`, `SCHEDULE_OFF_HERE` and `PREFERENCE_UNUSABLE` say Sort and Tools > Schedule, with no "Scan" and no "button". The runbook line is changed.
- **N2:** step 14 is reworded as the SPEC says.
- **P134 words:** `SCAN_SKIPPED` is sent as `vocab.scan.skipped`, and `SCAN_REASONS` is unchanged. Q1 is recorded with a recommendation. The three `wording-shell.tsv` rows are added. The held reminder lists file names only.
- **Standing rules hold:** there is no document read, file move or send, and nothing is guessed. Layers are unchanged (`test_layers` passes).
- **Boundaries held:**
  - no Email or Zip word was touched;
  - no version number was changed (P140);
  - no new text names the app (P155);
  - no dead code (ruff clean, `tipShowing` removed, `tempfile` used).

## Tests run (each file its own process, in parallel, in the worktree)

| Test file | .venv (Python 3.14.3) | Exit | .venv311 (Python 3.11.15) | Exit |
|---|---|---|---|---|
| test_shell | 119 passed | 0 | 119 passed | 0 |
| test_shell_menu | 30 passed, 3 skipped | 0 | 30 passed, 3 skipped | 0 |
| test_pilot | 19 passed | 0 | 19 passed | 0 |
| test_after_install | 73 passed, 3 skipped | 0 | 73 passed, 3 skipped | 0 |
| test_reminder | 205 passed, 1 skipped | 0 | 205 passed, 1 skipped | 0 |
| test_api | 407 passed (26 min) | 0 | 407 passed (32 min) | 0 |
| test_layers | 29 passed | 0 | 29 passed | 0 |
| test_single_source | 172 passed | 1 (decision-185 tripwire, S5) | 172 passed | 1 (same) |
| test_repo_map | 80 passed | 0 | 80 passed | 0 |
| test_tripwire | 19 passed | 0 | 19 passed | 0 |
| test_errors | 83 passed | 0 | 83 passed | 0 |
| test_vocab_report | 28 passed | 0 | 28 passed | 0 |

## Checks

- `python -m ruff check .`: All checks passed! (exit 0)
- `python tools/repo_map.py check`: Map is current (346 nodes). (exit 0)
- `python tools/vocab_report.py check`: Report is current (371 keywords, 66 unreached). (exit 0)

Probes lived only in `%TEMP%\claude\rv3` and used no client data. Nothing under `%USERPROFILE%\PilotTest` was opened. No tracked file was edited, and nothing was committed or pushed.
