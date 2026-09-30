# The fix round after the final reviews A, B and C

**Original file:** `pilot/handoffs/shell-fixpass.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen  
**Date:** not stated in the note (it sits on `claude/shell-join`, which is dated 2026-09-30 elsewhere)  

## In one sentence

The final reviews A, B and C of the whole shell found a list of problems, and this note says
which were fixed, how each fix is proven, and which words Jason may still want to change.

## What this session was asked to do

A Sonnet 5.5 builder worked on branch `claude/shell-join` and applied Jason's rulings 23 to 29.
It was to fix exactly the findings named, and nothing else. A second round ("fix pass 2")
then fixed five newer findings (N1 to N5) from a re-review.

## What it did

Fix pass 1, a few of the fixes:
- The warning about moving a schedule now appears under its question (A1).
- Emails and zip files now show as plain text, not as links (A2, ruling 24).
- "Could Not Be Read" became the word for an unreadable return (A3).
- "PROPOSED" marks were removed where Jason had approved words (A4).
- A sort or change that ran past the 30-minute limit now says so and whether it may be partly
  done (A5).
- A failed sort shows a short approved reason and never a path (A6, rulings 25 and 29).
- The firm view is proven read-only with a test (A7).
- The start-up race is fixed: the page starts only after every script loads (B1).
- The "Sort Failed" notice has no retry button and clears when a sort works (B2, ruling 28).
- Rows wrap their text, sit on the 4px grid and always underline links (B3 to B6).
- Vocabulary report hashes, the plan, the Windows check prompt, the runbook and README,
  the mock-up and the ledger were brought up to date (C1 to C10).

Fix pass 2:
- N1: other returns' raw engine sentences are no longer shown; only short approved words.
- N2: the Windows check step 12 now says which folder to rename; it was checked on a scratch tree.
- N3 to N5: approval marks, full stops on the 30-minute messages, and README and runbook wording.

Each fix has a named test, and each was checked by removing the fix to see the test fail.
Tests ran in Python 3.11 and 3.13, with style checks, the map check and the interaction script.

## What it found wrong, or what was left to do

- Two failure reasons cannot be told apart by the engine in a return's pass: "Drive Not Signed
  In" and "Ran Too Long". They are in the vocabulary but not mapped.
- "Another PC Sorting" is a skip, drawn as "Nothing Done", not "Sort Failed", so it is not
  yet seen on a return's banner.
- While fixing A7 the builder found that the firm view can update the store (the app's saved
  database) when it lags behind its journal, though it never touches a document. Not changed.
- The reminder's own refusal in `tracker/reminder.py` still says "card"; left alone.

## Decisions (made by Jason, or waiting for Jason)

Made: rulings 23 to 29 (reason words approved by ruling 29) and ruling 30 (nine misfit rows).
Waiting for Jason: the builder's own words, which Jason may change: "Change Stopped: Ran Too
Long", "It May Be Partly Done.", "Stopped: Ran Too Long", "Nothing Done", and "Bad Year"
(ruling 18a working word).

## Words to know

- **Fix pass:** one round of fixes that answers reviews.
- **Rulings:** Jason's numbered decisions.
- **Store / journal:** the app's saved database and the list of changes kept for it.
- **Firm view:** the summary of all returns.
- **Banner:** a notice at the top of a page.
- **Title Case / 4px grid:** capital letters on main words, and spacing in steps of four pixels.
- **Mutation check:** breaking code on purpose to see a test fail.
