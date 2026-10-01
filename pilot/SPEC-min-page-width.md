# Pilot 0.3 - the minimum window's page is narrower than 1100 - SPEC (P203)

Status: written 2026-10-01, 4:10 AM Pacific, by the orchestrator, for a separate builder and reviewer. Decision **P203**.

## The fault and its cause

**Seen** on the installed build of `main` at `4b55bc4` (hands-on check, 4:04 AM): with the window at its minimum width, Overview's Work Waiting list shows a sideways scrollbar whose handle is nearly the full width - the list is a few pixels too wide.

**Measured:** at the minimum, `GetWindowRect` gives the window 1100 wide and `GetClientRect` gives the page 1084 wide (Windows 11, the office PC).

**Cause, in one sentence:** `app/main.js:710-713` gives `BrowserWindow` `minWidth: 1100` without `useContentSize`, so 1100 counts the window's frame, while every 1100 px budget in the SPECs (SPEC-firm-columns item 14: 832 of 843 px; SPEC-shell's 1100 px minimum window) assumes the page itself is 1100 wide.

## Rulings

- **R1. The window's sizes are its page's sizes.** `useContentSize: true` in the `BrowserWindow` options at `app/main.js:709-713`, so `width`, `height`, `minWidth` and `minHeight` (1400, 900, 1100, 700) are the page's. Reason: one line makes every page's 1100 px budget true at once; shrinking a column instead would fix one list and leave the assumption wrong everywhere. The window becomes larger than the page by its frame (about 16 px wider and 39 px taller on the office PC), as Windows draws it.
- **R2. A test pins it.** A test in the file that already reads `main.js`'s window options (the builder finds it; expect `tests/test_shell_menu.py` or `tests/test_shell.py`) asserts `useContentSize: true` beside `minWidth: 1100`, named as its claim.
- **R3. The words follow.** Where a SPEC or the runbook says "1100 px minimum window", nothing changes: it now means what it says. The P179 note in SPEC-firm-columns item 14 gains one sentence: the budget is the page's, and P203 makes the minimum window's page 1100.

## What staff will notice

At the smallest window, no sideways scrollbar under the lists; the window itself is about 16 px wider and 39 px taller than before, at its smallest and by default.

## Files and owning tests

- `app/main.js` 709-713; the test file R2 names; `pilot/SPEC-firm-columns.md` item 14.
- Tests this SPEC runs: the R2 test file, `tests/test_single_source.py`, `tests/test_repo_map.py`, on Python 3.11 and 3.14.
- Proof on Windows after install: `GetClientRect` at the minimum gives 1100, and the Overview list shows no sideways scrollbar.
