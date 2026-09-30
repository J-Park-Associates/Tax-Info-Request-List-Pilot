# Final check of the screen's display code against the plan and Jason's rulings

**Original file:** `pilot/handoffs/shell-final-review-B.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Final check · Topic: Screen  
**Date:** not stated  

## In one sentence

The final reviewer of the display code found six problems that should be fixed, two of them needing Jason's call, and noted three smaller things.

## What this session was asked to do

Check "Area B" of the joined branch `claude/shell-join`: the screen's display code (the files under `app/renderer`) and the test setup (`pilot/harness`). It compared them with the plan and Jason's rulings, and with `origin/main`. The reviewer was independent and built none of it.

## What it did

- **Ran the tests.** Nine test files, each on its own, on Python 3.11 and then 3.13. All passed: `test_shell` 104, `test_shell_menu` 33, `test_pilot` 18, `test_pilot_ui` 11, `test_row_columns` 26, `test_tour` 9, `test_layers` 29, `test_single_source` 169 and `test_repo_map` 80.
- **Broke the code on purpose 13 times.** All 13 were caught.
- **Ran the test setup and a probe of its own.** It used 750 households and very long names. It checked every drawn page for a folder path and found none. There was no sideways scroll. The Clients list drew 758 rows in about 80 ms. Tab stays inside the sheet, and Esc closes it. It looked at screenshots in light and dark. Both scripts fail intermittently because of finding 1.
- **Checked with no problem:** the three link kinds and tooltips, Unfile with its reason, several files under a request, Folders Skipped, tooltips at 300 ms, the sheet's behaviour, and the empty and loading screens.

## What it found wrong, or what was left to do

1. **Startup race, should fix.** The app can start before the script that supplies its word list has loaded. Then it shows only "The App Hit an Error" with Retry, and the log reads a "not defined" error. It happened in one screenshot and makes the test scripts time out at different steps. On the real machine it should be rare, but a busy PC or antivirus scanning could trigger it. Retry recovers. Fix: start the app after the last script has loaded.
2. **The "Sort Failed" Retry does not retry the failed sort (Jason's call).** On a firm page, Retry sorts the last-loaded household, which nobody chose, while Sort is greyed. Even if it works, the notice never clears, because a one-household run does not write the last-pass file. Jason must decide: offer a firm-wide run, drop Retry on firm pages, or open the schedule.
3. **The year of a return link gets cut off (ruling 13, Jason's call).** At the smallest window width, "1040 - John & Jane Smith (20…" loses its year, and hovering does not help. Two years of one return then look the same. Fix: cut the name before the year and keep the year in its own piece that does not shrink.
4. **The paused-household words are cut away (ruling 21).** On Clients, "Two Years Open; Sorting Paused" runs past the name cell and is hidden. With a 60-character name it cannot be seen at all. On Overview it reads "Two Years Open; S…".
5. **A Needs Review group that cannot be built names itself by its full folder path.** That breaks the no-path rule (P63). Fix: name it by the return's name, and add the notices area to the test's scan.
6. **Links differ from plain names by colour alone, at about 1.4 to 1.** The accessibility standard (WCAG 1.4.1) wants 3 to 1 plus a cue that is not colour. Forced-colours mode is fine.
7. **Note:** keyboard users cannot reach a link's tooltip or a cut name. The screen-reader name is complete.
8. **Note:** the rulings file and the ledger on this branch are out of date. Rulings 15 to 22 and 18a exist only on another branch. The code does apply them.
9. **Note:** one style slip, two statements on one line at `pages.js` line 482.

The shot script had not finished the sheet, dialog, contrast and tooltip shots, so they were not viewed. This note is the only change in its commit, and it makes the repository map stale. The reviewer did not refresh the map, as instructed.

## Decisions (made by Jason, or waiting for Jason)

- Waiting for Jason: finding 2 (what Retry should do) and finding 3 (how to keep a return link's year visible).
- Jason's rulings (for example 7, 13 and 20 to 21) were the standard the code was checked against.

## Words to know

- **Area B:** the display code and its test setup.
- **Renderer:** the code that draws the screen.
- **Harness:** the test setup that runs the screen with made-up data.
- **Race:** two things that must happen in order, sometimes happening in the wrong order.
- **Tooltip:** a small text that appears when you hover or focus.
- **Forced-colours mode:** a high-contrast display mode.
- **WCAG:** a widely used accessibility standard.
- **Mutation check:** breaking the code on purpose to prove a test notices.
