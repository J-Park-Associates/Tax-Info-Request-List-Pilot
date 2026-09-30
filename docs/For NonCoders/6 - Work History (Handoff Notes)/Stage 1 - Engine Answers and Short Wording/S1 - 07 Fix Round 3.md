# Shell engine, fix round 3: the `firm` answer now matches the plan

**Original file:** `pilot/handoffs/shell-S1-rebuild-3.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen, Engine, Wording · Stage: S1  
**Date:** not stated in the note (a ruling of Jason's from 2026-09-29 is mentioned)  

## In one sentence

The engine's "firm" answer (one summary of every return in the firm) had five
small mistakes or gaps, and this round checked each one, confirmed them, and fixed them.

## What this session was asked to do

Check five claims raised by the review of the pages job (S4) and by Jason's ruling
of 2026-09-29 that a return's link reads "{Return Name} ({Year})". For each claim:
reproduce it first, then fix it. The checks used a made-up test setup: a return with two
requests received, one parked `setup.exe`, one moved `w2.pdf` and one set-aside `junk.pdf`.

## What it did

All five claims were true and were fixed:
1. **Field named `return`.** The plan says `return` is the return's path. The engine
   was sending a display label there. It now sends the path, and the extra fields are gone.
2. **Missing `handle`.** Each file in the answer now carries its `handle` (a short
   name that identifies one file), the same one used elsewhere in the state answer.
3. **Counts only counted requests.** The scratch return showed no files needing a person
   even though two did and one was set aside. Now every file that is not "received" is
   counted in its group. The result is needs you 2, waiting 0, received 2, set aside 1,
   the same as the page's own tally. Files already filed are not counted twice.
4. **Setup heading.** It said "After installing: needs a person". The approved wording
   is "Setup needs attention". The runbook line that used the old words was changed too.
5. **Year.** Returns and files in the `firm` answer now carry the year, read the same
   way as the other answers read it.

The answer stays read-only: no lock, no writing, no reading of any document, no network.
Four new tests were added and two changed. Each fix was tried in reverse to prove the
tests notice (counting no files, and putting the label back in `return`).

## What it found wrong, or what was left to do

One difference is left for the pages job (S4): a moved file that a person marked
missing counts as "set aside" in the engine, but the page only counts files it sees as
dismissed. This rare case still differs. The pages should count from the index rows' group.
Title Case for the new heading is left to job S8a.

## Decisions (made by Jason, or waiting for Jason)

Made: Jason's ruling of 2026-09-29 that return links show the year. Nothing is waiting.

## Words to know

- **Firm answer (`firm`):** the engine's read-only summary of all returns.
- **Handle:** a short name that identifies one file in the record.
- **Parked file:** a file the system did not file and set aside for a person.
- **Set aside:** a file or request a person decided not to file or asked for.
- **Scratch root:** a made-up test folder that holds no real client data.
- **Mutation check:** breaking the code on purpose to see that a test fails.
- **Rebuild:** a round of fixes after a review.
