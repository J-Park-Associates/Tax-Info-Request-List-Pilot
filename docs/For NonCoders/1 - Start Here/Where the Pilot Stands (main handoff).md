# The pilot's main hand-off page: where the new app screen stands

**Original file:** `pilot/HANDOFF.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Overview · Topic: Screen, Rules and decisions  
**Date:** the top section is dated 2026-09-30; older sections go back to 2026-09-28  

## In one sentence

This is the pilot's running "where things stand" page: it says the new app
screen (called "the shell") is built and joined, lists what is still left
(a check of the fix round, the merge to `main`, and the Windows check), and keeps
the history of earlier builds.

## What this session was asked to do

Nothing is stated in the note as one single request. The page is kept up to
date by many sessions. Its top section (2026-09-30, branch `claude/shell-join`,
job S6b) is the index of the shell build. The shell is the app's new main
screen, described in `pilot/SPEC-shell.md`. The build is split into jobs S1 to
S8b (decision P78). Each job has its own note in the `handoffs` folder.

## What it did

The page has these parts, newest first.

**1. Where the shell build stands (2026-09-30).** A table lists each job and its state:
- S1 (engine and wording), S2 (window and menus), S3 (page foundation), S7 (hover tips),
  S8a (link keys), S8b (a code for each skipped folder), the SPEC sync and S4/S5 (the
  pages, the side sheet, dialogs) are all "joined".
- S6a and S6b are the two halves of the join. S6b merged S5, made the test screen run
  on the real engine instead of a saved copy of its words, and wrote down how each
  piece of data crosses between the engine and the screen.
- The fix pass answered the final reviews A, B and C (Jason's rulings 23 to 29). It is
  done and waiting for its own review.

**2. The SPEC and mock-up (2026-09-29).** The written plan for the shell,
a list of 212 sentences over five words, a survey of the tests, and a clickable
mock-up with made-up names. Jason answered six questions: the read-only `firm`
command is approved (P79), the sort icon greys out on firm pages (P80), no
Tester Guide in Help (P81), the wording is approved (P84), and others.
The page also repeats the rules every shell session follows: builds are done by
Sonnet, reviews by Opus at high effort, a reviewer never reviews its own build,
and each session ends with the tests for what it changed.

**3. Older sections.** The design brief (P58 to P62), the "Pilot 0.2" merge (the
version is 0.2 everywhere; two older pull requests were closed), Build E (the tidy-up of
how the screen looks, with its reviews E1 to E3, which ended with no findings),
Builds A, B and C, what `main` is today, Jason's tester feedback, and notes for
cloud sessions.

## What it found wrong, or what was left to do

Left to do:
1. A session that did not build the fix pass reviews it.
2. The merge to `main`, as a merge commit, in the queue.
3. The Windows check on the office PC, using `pilot/wintest/PROMPT-shell.md`.

Known trouble spots:
- Speed: the firm view took 6.7 seconds for 750 returns in the cloud test machine.
  The goal is under 3 seconds. The real Windows number decides whether it needs a cache
  (a saved copy of recent answers so it does not have to redo the work).
- The status word "Came in Email or Zip" is cut off in its 160px column.

## Decisions (made by Jason, or waiting for Jason)

Made: rulings 1 to 29 (rows P85 to P114 in `pilot/DECISIONS.md`); the six answers above.

Waiting, with a default taken so nothing is blocked (SPEC section 19, O1 to O6):
- O1: "Could Not Be Read" as the word for an unreadable return.
- O2: which tooltip wins on a cut link name (the link's is taken).
- O3: how a keyboard user acts on a name link.
- O4: "Show in File Explorer" on file rows' right-click menus (built without a ruling).
- O5: whether `triage.places.footer` stays lower case (it does, as a fragment).
- O6: "Tracker Failed" in Title Case against ruling 6's "Tracker failed".
- "Bad Year" (ruling 18a) is a working word; "Nothing Done" is a working word.
  "Another PC Sorting" also shows when the lock holder is this same PC's own
  scheduled sort (ruling 29 as written).
- Ruling 25's reason words are approved (ruling 29). Two are not mapped, because the
  engine does not tell them apart: "Drive Not Signed In" and "Ran Too Long".
- Firm speed on Windows: the Windows number decides whether the firm view needs a cache.
- "Came in Email or Zip": Jason may say whether the column should be wider or the
  words shorter.
- Build E's open questions: SPEC-ui 5.7 (which of two main buttons leads a review
  row); the setup screen's empty picker is a 260px empty box; the tour's main
  button (Next) sits between Back and Close. Jason's own look on Windows 11 is left.
- The design skills pull request (#14, a draft) merges when Jason says so.
- After the Windows check: the tag (`pilot-0.2`) and sending of version 0.2 stay Jason's.

## Words to know

- **The shell:** the app's new main screen, with a side panel, pages and menus.
- **S1 to S8b:** the named build jobs of the shell.
- **Review / rebuild:** an independent check of a job, and the round of fixes after it.
- **Join:** merging separate jobs' work into one branch.
- **Branch:** a separate line of work in the code history.
- **Merge commit:** a record that joins one line of work into another.
- **Fix pass:** one round that fixes what the final reviews found.
- **`firm` command:** a read-only question the engine answers about every return in the firm.
- **Cache:** a saved copy of an answer, kept so the work is not redone.
- **Mock-up:** a picture-like model of the screen that is not the real app.
- **Ruling (P-number):** a decision of Jason, recorded as a row in `pilot/DECISIONS.md`.
