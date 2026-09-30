# First independent check of the shell's engine job (S1): nine findings

**Original file:** `pilot/handoffs/shell-S1-review-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen, Engine, Wording · Stage: S1  
**Date:** not stated in the note  

## In one sentence

A reviewer who did not build job S1 (the engine and wording job) checked it against the
plan, found the wording and tests sound, and listed nine problems to fix.

## What this session was asked to do

Review job S1 against the plan (`pilot/SPEC-shell.md`, sections 9 and 11) and the approved
wording table. The reviewer was an Opus session at high effort and read only what changed on
the branch.

## What it did

- Compared the approved words one row at a time by script. 70 of 70 matched, except four
  that are meant to differ.
- Compared the menu (44 keys), the short reasons (60 codes), the stage words and the
  safeguards with the plan's tables. They were equal. One table (the screen words) had a problem.
- Searched the other documents for old sentences that the new words replace. Only
  intended leftovers remained.
- Checked the four standing rules. The `firm` command reads no document, files nothing,
  sends nothing, uses no network and takes no lock. A before-and-after snapshot of the
  data showed nothing changed.
- Ran the tests in Python 3.11 and 3.13 with identical results. Six tests failed in
  `test_single_source`; the earlier handoff already named them, and each runs the
  app's main program. Style checks and the repository map were current.

## What it found wrong, or what was left to do

Nine findings:
1. **F1.** Four sort words and one filter word were nested one level too deep in the screen
   words, so the names the plan gives did not exist. Fix: flatten them and add a test.
2. **F2.** `firm` counted files moved by hand but did not list them, and a return whose only
   work was a parked file could be treated as complete.
3. **F3.** Each file carried only a display label for its return, so it could not be tied to
   the return. Fix: carry the path.
4. **F4.** A return that cannot be read got a long engine sentence with a banned word, and
   was counted as Complete, which hides a failure. Fix: a short approved line, details
   to the error log, counted as needing attention.
5. **F5.** The draft "ready" flag ignored approval, counted only some holds, and could
   never show "Held".
6. **F6.** The page error text was still a 27-word sentence when there is no error log.
7. **F7.** The kind of error behind "Next sort rechecks it" was dropped instead of sent to the
   error log.
8. **F8.** The read-only test did not check the store (the app's saved database).
9. **F9.** Two code comments said the opposite of what the code now does.

Each finding names its lines and the smallest fix.

## Decisions (made by Jason, or waiting for Jason)

Nothing is stated in the note as a decision. F4 proposes the short line "Could not be read"
"for Jason's approval"; the later notes show this word was then raised as open item O1.

## Words to know

- **SPEC:** the written plan for the shell.
- **Store:** the app's saved database of records.
- **Error log:** a file that keeps error details out of sight of the screen.
- **`firm`:** the read-only summary of all returns.
- **Parked file:** a file set aside for a person to look at.
- **Read-only:** looks at data but never changes it.
- **Findings (F1...):** numbered problems a reviewer lists.
