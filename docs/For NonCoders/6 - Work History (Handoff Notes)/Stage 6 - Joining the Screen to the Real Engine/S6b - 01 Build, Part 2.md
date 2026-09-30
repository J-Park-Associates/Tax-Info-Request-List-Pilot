# Second half of the join: the shell now runs on the real engine

**Original file:** `pilot/handoffs/shell-S6b.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Build · Topic: Screen, Engine · Stage: S6b  
**Date:** 2026-09-30  

## In one sentence

This session merged the sheet-and-dialogs job (S5) into the joined branch, made the test
screen use the real engine's words instead of a saved copy, and wrote down how each piece
of data travels.

## What this session was asked to do

Job S6b, by a Sonnet session on branch `claude/shell-join`: merge branch
`claude/shell-s5-sheet` (with a merge commit; nothing rebased, nothing force-pushed), then
four steps: run the screen on the real engine, put S5's words into the engine, check Title Case,
and verify the data "wire". After this the branch holds every shell job.

## What it did

- **The merge.** Conflicts were in the generated map, the plan, the wording table, the test
  harness, and two test files. In most, the join's text was kept because it was a superset;
  in others the two sides were combined. The map was regenerated, not hand-fixed.
- **Step 1, real engine.** The saved copy of the words (`vocab-mirror.json`) was deleted; the
  test screen now takes the words straight from the engine every run. New tests check that
  the test stand-in (the "stub") speaks the engine's words and gives replies of the same
  shape. They found real drift right away: the stub read a word the engine never had, a
  `paused` flag was missing, and some fields leaked or were absent. All were fixed in the stub.
- **Step 2, S5's words in the engine.** Two unused words were dropped. The three information
  dialogs now close with the word "Close". Two requests words remain proposed for Jason.
- **Step 3, Title Case.** A new test holds the page's own text to Title Case. Breaking it on
  purpose made the test fail, as it should.
- **Step 4, the wire.** A table shows, for each field (paused, file link keys, path kinds,
  misfit codes, "reveal" opening, the Show in File Explorer menu item), what the engine sends,
  what the app's main part does with it, and what the page draws. It was checked with the real
  commands on a scratch tree.
- **Gate.** All named test files passed in Python 3.11 and 3.13; style checks and the map
  check were clean; the interaction script said "all interactions pass"; screenshots of the
  Needs Review and Folders Skipped pages were looked at in light and dark.

## What it found wrong, or what was left to do

- Not done: the real replies were not fed through the browser page (the pages need the whole
  Electron main program); a level-by-level shape comparison is used instead.
- Left: the comprehensive review, the merge to `main`, the Windows check
  (`wintest/PROMPT-shell.md`; the firm summary's speed is the number to watch), and Jason's
  ruling on two proposed notice words.
- One word (`editor.routing_help`) is kept only because tests pin it; drop it with a ruling if wanted.

## Decisions (made by Jason, or waiting for Jason)

Waiting for Jason: the ruling on the two proposed notice words (`pick_request` and
`name_requests`), and optionally whether to drop `editor.routing_help`.

## Words to know

- **Join:** bringing separate jobs' work into one branch.
- **Merge commit:** a record that joins two lines of work.
- **Stub:** a stand-in that imitates the engine for testing the screen.
- **Vocabulary (vocab):** the list of every word the screen may show, kept in the engine.
- **Title Case:** Each Main Word Starts With A Capital.
- **Wire:** the way data crosses between engine, app main part and page.
- **Harness:** the test stand where the screen runs on its own.
- **Mutation check:** breaking code on purpose to see a test fail.
