# Third independent check of stage S7 (tooltips): no findings

**Original file:** `pilot/handoffs/shell-S7-review-3.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S7  
**Date:** not stated  

## In one sentence

A reviewer checked the second fix round of stage S7, the tooltips, and found nothing wrong.

## What this session was asked to do

Check "rebuild 2" of stage S7 on its branch. S7 is the stage that adds better placement to the app's tooltips, using the Floating UI library. The reviewer built neither S7 nor its fix rounds. It changed no code. It added only its own note and the refreshed repository map.

## What it did

- **History:** confirmed the rebuild is one commit on top of review 2's commits. A force-push rewrote only the builder's own commit and nothing else.
- **Scope:** the rebuild changed only the S7 notes, one line in `tests/test_shell.py` (a flag that ignores upper or lower case), and the generated map files.
- **The notes match the code.** The hover delay is 300 ms (ruling 7, replacing the spec's 500). A tooltip hidden by scrolling comes back only on the next hover or focus. The reviewer searched every S7 note for old figures and found no contradiction. Two passages are history, not errors.
- **The case check works.** The reviewer added an upper-case script tag from an outside site on a scratch copy. With the flag, the test fails as it should. Without it, the test passes. So the flag is what catches it.
- **Vendored files untouched.** The app code did not change. The two Floating UI files and three licence files match the fingerprints in the vendor notes.
- **Gate:** `test_shell` 37 passed and `test_repo_map` 80 passed, under Python 3.11 and 3.13. Ruff passed and the map was current (290 nodes).

## What it found wrong, or what was left to do

No findings. Review 2's finding 1 is fixed, and its note about an upper-case script tag is closed.

## Decisions (made by Jason, or waiting for Jason)

Nothing new is stated in the note. It relies on Jason's ruling 7 (a 300 ms hover delay).

## Words to know

- **Tooltip:** a small label that appears when you point at an icon.
- **Floating UI:** a small outside library that places tooltips so they stay inside the window.
- **Vendored:** an outside file copied into the project on purpose, with its fingerprint checked.
- **Force-push:** replacing a branch's history on the server.
- **Rebuild-2 / review-3:** the second fix round, and the third independent check.
- **Repository map:** the generated guide to what every file is for.
