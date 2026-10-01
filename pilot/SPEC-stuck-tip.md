# Pilot 0.3 - a tooltip outlives its element - SPEC (P202)

Status: written 2026-10-01, 3:45 AM Pacific, by the orchestrator, for a separate builder and reviewer. Decision **P202**.

## The fault and its cause

**Seen** on the installed build of `main` at `adb2b41` (hands-on check, 3:38 AM): hover a Taxpayer link on Overview until its tip shows ("Navigate to Return (Okafor Family)"), then press Ctrl+4, Ctrl+2 or Ctrl+3 without moving the mouse. The tip stays on the new page, over rows it does not belong to; moving the mouse over plain parts of the page does not clear it. It clears only on a click, Escape, a scroll or hovering another element that has a tip.

**Cause, in one sentence:** `app/renderer/tooltip.js` closes a tip only on `mouseout` from its element (129-139), and an element the page removes while it is hovered never sends `mouseout`, while `mouseover` on an element without a tip returns early (131) - so nothing ever notices the tip's element is gone.

The code dates from SPEC-shell and lane 4b (`d2c3768`, `5c290a0`); nothing in P193-P201 caused it.

## Rulings

- **R1. A tip whose element is no longer on the page is hidden at the next pointer move.** In the `mouseover` handler (`tooltip.js:129-134`), before anything else: when a tip is showing or waiting (`tipFor`, or a pending `tipTimer` for a node) and that node is not `isConnected`, `hideTip()`. Reason: the cheapest event that always follows a page change under a resting or moving mouse; no observer of the whole document.
- **R2. A page change hides the tip at once.** Wherever the shell draws a new page (the one place every page change goes through - the builder names it with file:line), call `hideTip()` before drawing. Reason: Ctrl+1-4 with the mouse resting still must not leave a tip for a frame; R1 alone waits for the mouse.
- **R3. A pending tip whose element left before its delay ended is never shown.** `showTip` (`tooltip.js:81`) does nothing for a node that is not `isConnected`. Reason: a hover just before a keyboard page change would otherwise show a tip for a removed element 300 ms later (`TIP_DELAY_MS`, `tooltip.js:16`).
- Nothing else changes: timing, focus tips, Escape, the search box rule, Floating UI placement.

## What staff will notice

A tip never stays behind after the page changes; it goes with its page.

## Files and owning tests

- `app/renderer/tooltip.js` 81-99 (`showTip`), 129-134 (`mouseover`); the page-drawing function the builder names: `shellGo` in `app/renderer/shell.js:254`, and `shellNeedsRoot` (`shell.js:806`), which sends a missing clients folder to the setup page without it (the P202 review's SHOULD) (`shellGo` is the one every other page change goes through - the menu's Ctrl+1-4 at `shell.js:939-942` (main.js:547-548 binds the keys), the side panel's links at `shell.js:1057`, the path row at 513, the search box at 686, and pages.js's links; `shellDraw`/`drawPage` also redraw the same page when its state arrives, so they are not where a page change is).
- `tests/test_shell.py`, beside the tooltip tests at 368-434, using their Node harness. New tests, named as claims:
  `test_a_tip_whose_element_leaves_the_page_is_hidden_at_the_next_mouse_move`,
  `test_a_page_change_hides_a_showing_tip`,
  `test_a_tip_waiting_on_its_delay_is_never_shown_for_an_element_that_left`.
- Tests this SPEC runs: `tests/test_shell.py`, `tests/test_single_source.py`, `tests/test_repo_map.py`, on Python 3.11 and 3.14. No wording changes, no docs beyond this SPEC and the curated map note for `tooltip.js` if it describes when a tip hides.
