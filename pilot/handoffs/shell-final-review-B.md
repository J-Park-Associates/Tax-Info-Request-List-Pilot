# Shell final review B: the renderer against the SPEC and the rulings

Reviewer: Opus 5.5, independent (built none of this). Branch `claude/shell-join` at
0b278d9, compared with `origin/main`. Area B covers `app/renderer/*` (shell, pages, app,
sheet, tooltip, tour, pilot, css, index.html, vendored Floating UI) and `pilot/harness`.

## What was run

- **Tests.** Each file ran in its own process, first under Python 3.11 and then under 3.13:
  `test_shell` (104), `test_shell_menu` (33), `test_pilot` (18), `test_pilot_ui` (11),
  `test_row_columns` (26), `test_tour` (9), `test_layers` (29), `test_single_source` (169)
  and `test_repo_map` (80). **All passed on both versions.**
- **Mutations.** 13 mutations were made on a scratch copy of the tree and **all 13 were
  caught** by `test_shell.py`:
  - the 300 ms delay changed to 500;
  - the search box given a tip on focus;
  - the year dropped from return links;
  - a file link opened without reveal;
  - Unfile sent without its reason;
  - the ruling 17 child rows dropped;
  - the ruling 20 notice never shown;
  - the ruling 21 marker dropped;
  - the misfit reason dropped;
  - the misfit drawn as its full path;
  - Needs Review file names not drawn as links;
  - a household link opening File Explorer;
  - a Needs Review group failing to build.
- **Harness.** `interact.mjs` and `shoot.mjs` were run. Both fail intermittently because of
  finding 1. I also ran my own probe on a scratch copy of the stub. It used 750 households,
  household names of 60 characters and return names of 80, zero data, the notice, failed
  and paused scenarios, the sheet, and a DOM walk of every text node, attribute and input
  looking for a path. Results:
  - No path was drawn on any page, in the search, in the sheet, in Folders Skipped or in
    the notices.
  - No sideways scroll when the long names contain spaces.
  - Clients "All" drew 758 rows in about 80 ms.
  - An H1 of 80 characters wraps to 2 lines.
  - Tab stays inside the sheet (30 presses, 0 escapes). Esc closes the sheet and focus goes
    back to the row list.
  - Screenshots were checked in light and dark.

## Findings

1. **Startup race: "The App Hit an Error" instead of the app** - should fix.
   - **Where:** `app/renderer/app.js:3614` calls `bootstrap()` as soon as `app.js` runs.
     `loadEngagements` then calls `applyVocabulary()`, and that calls `shellVocabulary()`
     (`app.js:1784`), which is defined in `shell.js`. `shell.js` is loaded four scripts later
     (`index.html:506-510`).
   - **What happens:** if the `list` reply arrives before `pages.js`, `sheet.js` and
     `shell.js` have run, the app shows only "The App Hit an Error" with Retry. The error log
     reads `ReferenceError: shellVocabulary is not defined`.
   - **Seen here:** it happened in the dark Overview shot of `shoot.mjs`, and it is why
     `interact.mjs` and `shoot.mjs` time out at a different step on each run.
   - **Risk on the real machine:** in Electron the reply comes from Python and is usually
     slower than local scripts, so it will be rare. But a busy office PC, or antivirus
     scanning each `.js` file as it loads, makes it possible at every launch. Retry recovers.
   - **Fix:** start `bootstrap()` after the last script has run (for example on
     `DOMContentLoaded`, or from the end of `shell.js`).

2. **The ruling 20 "Sort Failed" Retry does not retry the failed sort** - should fix,
   **JASON**.
   - **Where:** `shell.js:476-477` passes `retry: runScan`. `runScan` (`app.js:2152`) runs
     `run-now` for the household of `active`.
   - **On a firm page:** `active` is still whatever return was loaded last. At startup it is
     the first return (the probe showed Smith Family). So Retry on Overview sorts one
     household nobody chose, while that same page shows Sort greyed as "Open a Client to
     Sort" (P80). With no return loaded yet, it is an engine refusal.
   - **Why the notice never clears:** `run-now` passes `--household`, and `runner.py:2697`
     writes the last-pass file only when no household is given. So a Retry that works never
     clears the notice, and the preparer sees Retry do nothing.
   - **Needs Jason's call:** whether Retry should offer a firm-wide run, be dropped on firm
     pages, or be replaced by an action that opens the schedule.

3. **The year of a return link is the part that gets cut** (ruling 13) - should fix,
   **JASON**.
   - **Where:** at the 1100 px minimum the name column is about 244 px (`pages.js:122-127`
     draws one string, and the CSS cuts it from the end).
   - **What the preparer sees:** on the household page both rows read "1040 - John & Jane
     Smith (20…" (see `household-dark-1100x700`). "1120-S - Rivera Design LLC (2025)" loses
     its year the same way on Overview and Reminders.
   - **Why hover does not help:** the tooltip is the link's "Navigate to Return", not the
     name (orchestrator default Q2). So two years of one return cannot be told apart, which
     is the whole point of ruling 13.
   - **Fix:** cut the name before the year, with the year in its own node that does not
     shrink.

4. **The ruling 21 paused words are cut away** - should fix.
   - **On Clients:** the marker "Two Years Open; Sorting Paused" sits inside the name cell,
     which has `overflow: hidden` (`pages.js:241-245`, `shell.css:398`). For "Okafor Family"
     the marker runs 97 px past the cell's edge. The cell has no tooltip, because the name is
     a link, so the link's tip is the only one. With a household name of 60 characters the
     marker cannot be seen at all.
   - **On Overview:** the status column reads "Two Years Open; S…" (this one has a
     cut-name tooltip on hover).
   - **Result:** the words that say sorting stopped are the words a preparer does not see.

5. **A Needs Review group that cannot be built names itself by its full folder path** -
   should fix.
   - **Where:** `pages.js:504` calls `pagesSafe(group.path, …)`. `pagesReportBroken` then
     draws "{label}: The App Hit an Error" with the label set to that path
     (`pages.js:928-938`).
   - **Example:** if the vocabulary lacks `screen.navigate_return` or
     `screen.navigate_client` (a version mismatch between app and engine), the notice reads
     "C:\Clients\J Park & Associates\Smith Family\2025\1040 - …: The App Hit an Error".
     This breaks P63. My mutation run showed the path in the `broken` list of
     `test_no_page_draws_a_path_as_text_or_as_a_tooltip`.
   - **Why the test misses it:** that test's path scan does not cover `#notices`, so its
     `hits` stayed empty.
   - **Fix:** name the group by `pagesReturnName(group.path)`, and add `#notices` to the
     test's scan.

6. **Links differ from plain names by colour alone, at 1.4:1** - should fix.
   - **The numbers:** `--link` `#14335c` against `--text` `#0f172a` is 1.41:1 in light.
     In dark it is `#a8c4ee` against `#e8ecf2`, 1.50:1. Both are bold, and the underline
     shows only on hover (`shell.css:397-402`).
   - **What the preparer sees:** on a return page the file-name links and a plain request
     name ("1098 - Harbor Bank") look the same. The "{n} Waiting" status (`--st-waiting`) is
     close to the link colour too.
   - **Standard:** WCAG 1.4.1 wants 3:1 between link and text plus a cue that is not colour.
     Forced-colors mode is fine, because `LinkText` is used there.

7. **Keyboard users cannot reach a link's tooltip or a cut name** - note.
   - Rows are `aria-activedescendant` options, so no link and no cut cell ever takes focus.
   - The screen-reader name is complete. A sighted keyboard user never sees a cut name or the
     cut paused words (orchestrator default Q3 covers only the link action).

8. **The rulings file and the ledger on this branch are out of date** - note.
   - `pilot/handoffs/shell-rulings.md` on `claude/shell-join` stops at row 14. Rows 15-22
     and 18a exist only on `claude/amazing-maxwell-b4hdzo`.
   - `shell-ledger.md` is "as of 2026-09-29" and still lists rulings 8-13 as in progress.
   - The code does apply rulings 15-22. It is the record that lags.

9. **Style** - note. `pages.js:482` has two statements on one line (`pagesRow);  if (...`).

## Checked with no finding

The following match the SPEC and the rulings:

- **Links and tooltips:** the three link kinds and their tooltips; firm Needs Review file
  links built from `firm.paths` (r15).
- **Unfile (r16):** the confirm box with "Reason (Optional)" sent as `note`, and one write
  per press.
- **Several files under a request (r17):** one child row per file, not counted; a link and
  Unfile only on its own copy.
- **Folders Skipped (r18):** each folder's own name and its two-word reason ("Bad Year"
  present). The long sentences go to the error log only.
- **Tooltips:** 300 ms on hover (r7); a tip on focus for every control but `#find` (r2);
  placement by Floating UI only.
- **Sheet:** open, More, Next, the order from firm and return pages, the move on after a
  write, closing and focus return, and the Tab trap.
- **Screens:** empty and zero-data states on every firm page; the loading frame; Title Case
  on every drawn word I saw.

`shoot.mjs` had not finished the sheet, dialog, forced-colors and tooltip shots when this
was written, because of finding 1. I did not view them.

This file is the only change in this commit. It alone makes the repository map stale:
`repo_map.py check` reports "added pilot/handoffs/shell-final-review-B.md" and nothing
else. As instructed, I did not run `update`.
