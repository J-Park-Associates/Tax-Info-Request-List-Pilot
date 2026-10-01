# P202 review - a tooltip outlives its element

Reviewer, 2026-10-01. Branch `claude/stuck-tip`, diff `adb2b41..HEAD` (3cf38f3 SPEC, e20a87d build, 4604a19 results sheet, 255e6de merge). I did not write the SPEC or build it. Nothing edited, committed or pushed.

**Verdict: ready to land. 0 MUST, 1 SHOULD, 4 NIT.**

## The rulings, checked against the SPEC

- **R1** `app/renderer/tooltip.js:138-146`: the first two lines of the `mouseover` listener hide a tip that is showing (`tipFor`) or waiting (`tipWaitFor`) for an element that is no longer `isConnected`. This happens before the early return, so moving the mouse over plain page now clears the tip. `tipWaitFor` (`:22`) is set when the delay starts (`:144`) and cleared in `hideTip` (`:114`) and `showTip` (`:94`). Both can never be set at once: every path that sets one first clears the other. As ruled.
- **R2** `app/renderer/shell.js:259`: `hideTip()` in `shellGo`, after `hideFound()` and before `shellDraw()`. As ruled.
- **R3** `app/renderer/tooltip.js:85-89`: `showTip` gets no words for a disconnected element, so the existing "no words" branch hides and shows nothing. As ruled.
- **Keyboard focus tips are not hidden wrongly by R1.** R1 hides only an element that is gone. A focus tip on an element still on the page passes untouched. A focus tip whose element was removed is now hidden, which is correct. R2 hides a focus tip on a page change, and `shellGo` then moves focus to `#page` (`shell.js:273`), which has no tip. That is the SPEC's ruling, not a regression.
- **Nothing else changed.** `TIP_DELAY_MS` is still 300 (`tooltip.js:16`) with no new timing. The `focusin`, `focusout`, `pointerdown`, Escape (`tipKey`), search-box (`#find`) and Floating UI code is unchanged in the diff. `pages.js:543` already calls `hideTip()` before `showTipNow`, so the new `tipWaitFor` bookkeeping holds there too.
- **Curated note, 500 ms -> 300 ms:** correct. The constant is `TIP_DELAY_MS = 300` (`tooltip.js:16`), and the file's own header says 300 ms (`:3`). The new P202 sentence describes the code accurately.

## Does every page change go through shellGo?

Mostly. These routes call `shellGo` directly:
- the menu's Ctrl+1-4;
- the side panel;
- the path row;
- the search box;
- the links in `pages.js` (`:225-226`), including the linked households panel (`:390`), a next-step "open" (`:561`) and a row menu (`:1924`);
- Create Return (`app.js:2966`);
- setup's Cancel, which is the only "back" (`shell.js:792`).

There is no browser-history back or forward (`popstate`, `history.*`) anywhere in the renderer. `tour.js` never changes the page. Dialogs and the side sheet draw over the page rather than changing it.

**One exception, the SHOULD below:** `shellNeedsRoot(true, ...)` (`shell.js:806-813`) switches the page to setup by itself. It sets `shellRoute = { level: "setup" }` and calls `shellDraw()` without going through `shellGo`. `app.js:1840` calls it from a list reply when the clients folder is missing, which can happen during a refresh. Every other `shellDraw()` call (`shell.js:161, 228, 302, 316, 922`) redraws the same page.

## The tests

The three new tests in `tests/test_shell.py` (`TIP_PAGE` at about `:437`, tests at about `:463-510`) run the real code:
- the whole of `tooltip.js`, with its own listeners;
- the real `shellGo`, taken out of `shell.js` by the existing `run_shell` helper.

The fakes are limited to the page, the timer and Floating UI.

**Mutation check (my own, in a scratch copy of HEAD, with `tooltip.js` and `shell.js` set back to `adb2b41`):** all 3 fail. The output was `3 failed, 170 deselected`. With the fix, all 3 pass. Only `tests/test_shell.py` takes `shellGo` out of `shell.js`, so the call to `hideTip()` without a guard breaks no other test.

## Findings

**SHOULD**

1. `app/renderer/shell.js:810-812` (`shellNeedsRoot`): a page change to setup that does not go through `shellGo`, so R2 misses it. A tip showing when the folder goes missing stays until the mouse moves. R1 then clears it, so the cause is only half-fixed for this path.
   - **Fix:** add `hideTip();` on the line before `shellRoute = { level: "setup" };`.
   - The test is the R2 test's pattern, with `shellNeedsRoot` taken out of `shell.js`.
   - Correct the hand-back's claim that `shellGo` is "the one function every page change goes through" (`pilot/handoffs/stuck-tip-build.md`, R2 bullet) and the SPEC's Files line (`pilot/SPEC-stuck-tip.md`, "the one every page change goes through").
   - If the orchestrator rules it out of scope, record that in the SPEC instead.

**NIT**

2. `pilot/DECISIONS.md:197` (P202): the status still says "SPEC written; building". **Fix:** "built (`e20a87d`) and merged into `claude/stuck-tip` (`255e6de`); reviewed 2026-10-01; hands-on Ctrl+4 check still to run on Windows".
3. `pilot/SPEC-stuck-tip.md` R3 reason: it says "400 ms later", but the delay is 300 ms (`TIP_DELAY_MS`, `tooltip.js:16`). **Fix:** "300 ms later".
4. `pilot/wintest/RESULTS-0.3-followup.md`, "Install over the open app" row: the title says the install ran over the open app, but the evidence says the app was closed through its Close button first. **Fix:** retitle it "Install after closing the app (N7)".
5. `pilot/wintest/RESULTS-0.3-followup.md`, "The real store is whole" row: "real store" sits next to "made-up sample data only" in the header, and a reader could take it to mean client data. **Fix:** "The store in the installed app's data folder is whole".

Apart from items 4 and 5, the results sheet states only what it shows. The FAIL row points to the SPEC, and the "Not checked by hand tonight" list is honest about what was left out. The hands-on Ctrl+4 recheck of the fix has not been run yet, and the hand-back says so.

## Dead code

None. `tipWaitFor` is read at `tooltip.js:139` and written at `:94`, `:114` and `:144`. Nothing is commented out, and no import or name went unused.

## Results (run by me, each file in its own process, this worktree at HEAD `255e6de`)

| | Python 3.11 (`pl\v311`) | Python 3.14 (`pl\v314`) |
|---|---|---|
| `tests/test_shell.py` | 173 passed in 39.21s | 173 passed in 36.57s |
| `tests/test_single_source.py` | 179 passed in 40.64s | 179 passed in 41.44s |
| `tests/test_repo_map.py` | 80 passed in 27.65s | 80 passed in 29.00s |

- `python -m ruff check .`: All checks passed!
- `python tools/repo_map.py check`: Map is current (426 nodes, generated 2026-10-01). The map gains three document nodes: the SPEC, the hand-back and the results sheet. The header count went from 424 to 426. `check` exited 0.
- Working tree clean after the review.
