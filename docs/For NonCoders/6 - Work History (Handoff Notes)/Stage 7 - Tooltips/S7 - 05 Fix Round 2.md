# Small document fix for the tooltips stage (S7, second fix round)

**Original file:** `pilot/handoffs/shell-S7-rebuild-2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen · Stage: S7  
**Date:** not stated  

## In one sentence

This session corrected the S7 handoff's wording about the tooltip hover delay and about tips that scroll out of view, and made one test stricter.

## What this session was asked to do

Fix finding F1 of "review 2" of stage S7 (tooltips), plus one test change from that review's notes. No other code changed.

## What it did

In the S7 handoff file `pilot/handoffs/shell-S7.md`:

- In "Left for S6", the hover delay is now stated as 300 ms (Jason's ruling 7), replacing the plan's 500. The proposed plan edit also says that a tip hidden because its control scrolled out of view does not come back when the control scrolls back. It returns only on the next hover or focus.
- In "For Jason", the scrolled-away tip is now described as hidden (by Floating UI's own hide feature), not clipped.
- The proposed decision row now mentions that hide feature.

The test change: a pattern in a test of the page's loading order is now case-insensitive. Proof: on a scratch copy outside the repository, adding an outside script tag in capital letters to the page made that test fail.

Checks: 37 tests in the shell test file passed on Python 3.11 and 3.13. The code-cleanliness check was clean. Then the map was updated and its check and test run.

## What it found wrong, or what was left to do

Nothing is stated in the note.

## Decisions (made by Jason, or waiting for Jason)

Nothing new is stated. The note relies on Jason's ruling 7 (300 ms).

## Words to know

- **Tooltip:** the small label that appears when you hover over or focus on a control.
- **Floating UI:** a small outside code library that decides where a tooltip is placed.
- **Hover delay:** how long the pointer waits before the tooltip shows.
- **Ruling:** a decision Jason made and wrote down.
- **Scratch copy:** a throwaway copy of the code used for experiments, never saved to the repository.
