# Second independent check of stage S1 (the shell's engine side), after the first fix round

**Original file:** `pilot/handoffs/shell-S1-review-2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen, Engine, Wording · Stage: S1  
**Date:** not stated  

## In one sentence

A second reviewer, who had built none of it, confirmed that all nine problems from the first check were fixed, and found one leftover: an older note still describes a rule the code no longer follows.

## What this session was asked to do

Stage S1 is the first build stage of the app's new screen ("the shell"). It changes the part of the program that answers the screen's questions (the "engine side").

A first reviewer had listed nine problems, called F1 to F9. A builder fixed them in a fix round called "rebuild 1". This session checked two things:

- Were F1 to F9 really fixed, in the code itself and not just in the builder's own note?
- Did the fix round change anything else it should not have?

## What it did

- **Checked each of the nine fixes in the code.** All nine hold. Some examples:
  - The table of screen words was compared key by key with the plan. All 78 keys and words match. The 79th row lives where the plan says it should.
  - Files that a person moved by hand are now counted and listed on the firm-wide view.
  - A return that cannot be read now says "Could not be read" and counts as needing a person.
  - A draft counts as "ready" if it was written this week and is not yet approved. A hold on the return no longer stops it being "ready".
  - A test now proves the firm view changes nothing on disk.
- **Checked that the fix round changed nothing else.** It touched only the engine file, its tests, one row of a test-notes file, its own handoff note and the regenerated repository map.
- **Checked the standing rules.** The firm view takes no lock and makes no network call. Nothing is sent. It reads only the firm's own data, never a client document. It writes nothing. No folder path is shown on screen.
- **Ran the tests.** Each test file ran on its own, on Python 3.11 and on Python 3.13, with the same results. Most files passed in full. One file, `test_single_source`, had 6 failures. They are exactly the tests about the app's window code, which wait for stage S2. The code-tidiness check and the repository-map check were both clean.

## What it found wrong, or what was left to do

**One finding (F1).** The first stage's own handoff note, `pilot/handoffs/shell-S1.md`, still says a draft is "ready" only when nothing holds it. It also lists that as a decision for stage S6 to write into the decision log. The code and the plan now say the opposite. So stage S6 could log a decision that is wrong.

The fix is to edit that note only (no code, no tests):

- Correct the "ready" line. Ready means: drafted this week and not yet approved. A draft edited after approval does not count as approved. "Held" means the holding rows plus the unsorted files in the inbox. A hold does not undo "ready".
- Add a proposed decision: a return the firm view cannot read says "Could not be read", the detail goes to the error log, and it counts as needing a person. The new words "Could not be read" are not yet in the approved word list.

**A note, not a finding.** The firm view now reads more for every return, even when nothing was drafted. A household with several returns has its inbox listed once per return. The speed goal is 750 returns in 3 seconds. That is measured later, on the Windows check. If it fails, look here first.

## Decisions (made by Jason, or waiting for Jason)

- Waiting for Jason: approve the new words "Could not be read" (it follows the already-approved "Reminder could not be read").
- The meaning of "ready" and "held" needs no new approval. It matches section 6.3 of the plan.

## Words to know

- **Shell:** the app's new screen.
- **Stage S1:** the first build stage. It builds the engine side that answers the screen's questions.
- **Review / rebuild:** a review is one independent check. A rebuild is one round of fixes after a check.
- **Firm view:** the screen that shows every return the firm has, with counts of what needs a person.
- **Draft:** a chase email the program writes for a person to send. The program never sends it.
- **Held:** stopped by a rule. Unsorted files in the inbox hold the whole draft.
- **Repository map:** a generated guide to every file in the program. It must be refreshed when code changes.
- **Mutation check:** breaking the code on purpose to prove a test notices.
