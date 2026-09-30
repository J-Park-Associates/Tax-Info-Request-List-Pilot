# Stage S7 fixes: how the small hint boxes load and behave

**Original file:** `pilot/handoffs/shell-S7-rebuild-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen · Stage: S7  
**Date:** not stated (the ruling it applies is dated 2026-09-29)  

## In one sentence
This session fixed the four problems from the first check of stage S7 (the hover hints, called tooltips) and set the hover delay to 300 ms, as Jason ruled.

## What this session was asked to do
Answer review 1 of S7. It worked on branch `claude/shell-s7-tooltips`, starting from commit `430aa27`. Only F1 to F4 and Jason's ruling 7 changed.

## What it did
- **F1 (the real app did not start).** The two outside "Floating UI" script files now sit right above the app's own script, so nothing blocks between the two. The load order is pinned in a test. Proof: the screenshot script ran all 81 shots with "0 page errors", and the interaction script said "all interactions pass".
- **F2 (a hint outlived a scrolled-away control).** The hint now hides when its control is scrolled out of view, and follows the control while visible. This was Jason's choice, recorded as the orchestrator's decision for the pilot, and it can be reversed. The bundled outside files were not touched. A test and three harness checks pin it, and deleting the line made them fail.
- **F3 (the "no CDN" check missed single quotes).** The check now reads a script source in double quotes, single quotes or none. Adding a single-quoted web address now fails the test.
- **F4 (wrong decision number).** "P86" was removed; comments cite "Jason's ruling 5 (2026-09-29)". S6 will put in the number it logs.
- **Ruling 7.** The hover delay is 300 ms. Keyboard focus still shows the hint at once. A test pins it.
- Tests ran in parallel on Python 3.11 and 3.13, plus the code checker, the two harness scripts and the repository map. The known `test_build` failure was ignored.

## What it found wrong, or what was left to do
The plan (SPEC-shell 8.5) needs an edit, which this session proposed but did not make: the delay "500 ms" becomes "300 ms", and a line is added that the hint follows its control and is hidden when scrolled out of view. This replaces two lines in the S7 handoff.

## Decisions (made by Jason, or waiting for Jason)
Made by Jason: ruling 7 (300 ms delay, 2026-09-29), and ruling 5 as cited.
Proposed decision rows for S6:
1. The Floating UI scripts load before `app.js`.
2. A hint hides when its control is scrolled out of view (a reversible pilot decision).
3. The hover delay is 300 ms and focus is immediate (replaces the 500 ms).

## Words to know
- **Tooltip:** a small hint that appears when you hover on or tab to a control.
- **Floating UI:** an outside library that places such hints.
- **CDN:** a web server that hosts code; the app must not load code from one.
- **Harness:** a test setup that runs the screen with pretend data.
- **Mutation:** deliberately breaking code to prove a test would notice.
- **Ruling:** one of Jason's numbered decisions.
- **Orchestrator:** the session that directs the other work sessions.
