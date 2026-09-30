# Final check of the second fix pass on the joined screen

**Original file:** `pilot/handoffs/shell-final-check2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Final check · Topic: Screen  
**Date:** not stated  

## In one sentence

An independent checker confirmed that the second fix pass repaired five problems (N1 to N5), found that nothing blocks the merge, and left two small document fixes and some words for Jason.

## What this session was asked to do

Check "fix pass 2" of the joined screen (the branch `claude/shell-join` at `ed0ef69`) against the five open problems N1 to N5 from an earlier re-review and against Jason's rulings 24 to 30. The checker built none of the shell or either fix pass. It changed no code.

## What it did

- **N1 and N2, with the real engine.** It built a test tree with one household with two returns and one never sorted. It fed real sort results through the page's own code, and ran the scheduled pass as a real process.
- **Regression.** In fresh environments, all 55 test files ran in their own processes under Python 3.11 and 3.13. On each: 4002 passed, 21 skipped, 0 failed.
- **Guards.** The code-cleanliness check, the map check and the vocabulary report check were clean. The routing baseline file is unchanged.
- **Engine.** Only one engine file changed in this pass. Three "kill" sentences gained a full stop, and there is one new bare word, "Nothing Done". Nothing changes sorting, filing, routing, locking or what is written to client folders or the record.

**Verdicts.**
- **N1, banner sentences: fixed.** The banner drew short lines such as "Sort Failed: Folder Not Found" and "Nothing Done: Another PC Sorting." for many cases. No drawn line held a path, a backtick or an engine sentence.
- **N2, steps 11 to 13 of the test prompt: fixed,** with one wording nit. Steps 12 and 13 were run for real, and a CPA can follow them.
- **N3, the wording table: fixed.**
- **N4, the kill texts: fixed.** Each ends in a full stop, is five words or fewer, and is in Title Case. The app's defaults match the API word for word.
- **N5, README and runbook: fixed in the runbook, not fully in the README.**

## What it found wrong, or what was left to do

1. Step 13 of the test prompt names the other return's line in a shape the screen does not use (the screen adds a bullet, the household and the year). Fix the step's words, or change the screen.
2. The README still says "card" in two places (lines 363 and 486). The runbook says "side sheet" and "row". No test pins this.
3. "Nothing Done" is not on the handoff's "Open for Jason" list. It should be added.
4. "Another PC Sorting" also shows when the lock is held by the same PC. The build follows ruling 29. Jason may want a word true for both, such as "Another Sort Running".
5. Small punctuation differences inside the banner (some lines end with a full stop, some do not). Harmless.
6. Some engine sentences say "Repair the Schedule" while the menu item reads "Repair Schedule". This predates the pass.

Also: this file alone makes the map stale; `update` was not run, as instructed.

## Decisions (made by Jason, or waiting for Jason)

- **Waiting for Jason:** approve the new word "Nothing Done".
- **Waiting for Jason:** whether to change "Another PC Sorting", and how step 13's line should read.
- **Already made:** rulings 24 to 30. The build follows ruling 29.

## Words to know

- **Fix pass:** a round of repairs after a review.
- **Banner:** the message lines shown after a sort fails or is held back.
- **Engine:** the part of the program that sorts and files documents.
- **Regression run:** running all tests to see nothing broke.
- **Lock:** a marker that keeps only one PC working on a household at a time.
- **Scheduled pass:** the automatic overnight sort.
- **Kill text:** the message shown when a sort was stopped for running too long.
- **Repository map:** the generated guide to the program's files.
