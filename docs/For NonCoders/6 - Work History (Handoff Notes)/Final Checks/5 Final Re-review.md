# Final re-check of the whole shell after the fix pass

**Original file:** `pilot/handoffs/shell-final-rereview.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Final check · Topic: Screen  
**Date:** not stated  

## In one sentence
An independent reviewer ran the whole test suite and the real code, found that every blocking finding was fixed, and listed a few smaller items, two of them for Jason.

## What this session was asked to do
Re-check the "fix pass" made after three final reviews (A, B and C) of the new screen. The reviewer built none of the shell or the fix pass. It looked at branch `claude/shell-join` at `2933a67` (changes from `0b278d9`), against the findings, the fix pass's claims and rulings 1 to 29. It changed no code.

## What it did
- **Verdict: no finding blocks the merge.**
- Ran the whole suite on Python 3.11 and 3.13 in fresh installs: 55 files, 4001 passed, 21 skipped, 0 failed on each. The code checker was clean, the repository map current (340 entries), and the vocabulary report current. The routing backtest baseline is not lowered.
- **The engine's only change** is a `code` field on each run in the final line. Sorting, filing, routing, locking and client folders are unchanged. Emails and zips get no link key anywhere; this is confirmed safe.
- Ran the harness: all interactions pass, and 181 screenshots with 0 page errors.
- Reproduced the start-up race (B1) before the fix, and confirmed it gone after.
- Broke the code on purpose twice; the tests caught both.
- Each finding is judged fixed (A1 to A7, B1 to B7, C1 to C10). Some are "partly fixed": C5 (open words for Jason) and C8 (runbook and README). Rulings 24, 27 and 28 are met, and 29 is met as written.

## What it found wrong, or what was left to do
1. **The failed-sort banner still shows long engine sentences** for the other returns in a household and for a lock-held run. That breaks ruling 25 and can show a folder path. The Windows check's step 13 holds only for a household with one active return. Suggested: say each as "{Return} ({Year}): {short reason}".
2. **Windows prompt step 12** does not say which folder to rename, so it could record a false FAIL. It also calls the menu item "Repair the Schedule" when the menu says "Repair Schedule".
3. **Nine misfit words** are marked approved by rulings that do not approve them (Unknown Folder, Old Layout, No Household, Unowned Folder, Name Refused, No Return, Cannot List, Look-Alike Folder, Old Workbook).
4. **A missing full stop** in the stopped-command line ("...Ran Too Long It May Be Partly Done.").
5. **Runbook and README:** a broken sentence in the README, a doubled "a" in the runbook, and many old words such as "card" and "Routing rules".
6. Note: the Windows prompt is followable by a CPA.
7. Note: known fixable conditions, such as two folders claiming one household, show as "Unexpected Error" (as ruling 29 says).
8. Note: the Sort Failed notice can be dismissed; ruling 28 says "no button".
9. Note: "Came in Email or ..." is cut off in the status column at 1100px.

## Decisions (made by Jason, or waiting for Jason)
Waiting for Jason: item 1 (the short word for a skipped run), item 3 (approve the nine misfit words or mark them proposed), and optionally items 7 and 8 (confirm he is content that the notice can be dismissed). Already on his open list: the word "Could Not Be Read" (open item O1) and the cut-off "Came in Email or ..." (open item 5).

## Words to know
- **The shell:** the app's new screen and window.
- **Fix pass:** the round of fixes after the final reviews.
- **Independent reviewer:** someone who did not build the work.
- **Backtest baseline:** the recorded routing score that no change may lower.
- **Race (start-up race):** a bug that depends on which of two things finishes first.
- **Mutation:** deliberately breaking code to prove a test would notice.
- **Harness:** a test setup that runs the screen with pretend data.
- **Ruling:** one of Jason's numbered decisions.
- **Misfit:** a folder that does not fit the expected layout.
- **Commit:** one saved step in the program's history.
