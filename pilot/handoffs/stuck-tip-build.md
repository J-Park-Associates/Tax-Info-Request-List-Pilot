# P202 build hand-back - a tooltip outlives its element

Builder, 2026-10-01. Branch `claude/stuck-tip-build` from `3cf38f3`, one commit. Not pushed.

## The cause: confirmed

As the SPEC says. `tooltip.js` hid a tip only on `mouseout` from its element; an element the page removes while it is hovered never sends `mouseout`, and `mouseover` on an element without a tip returned at once - so nothing noticed the tip's element was gone. The pending-delay case (R3) was a real second path: the old `showTip` would show a tip for a removed element when its 300 ms delay ended.

## Rulings, where they are built

- **R1** - `app/renderer/tooltip.js:138-146`, the `mouseover` listener: before anything else, a tip showing (`tipFor`) or waiting on its delay (`tipWaitFor`) for an element that is not `isConnected` is hidden. `tipWaitFor` (`tooltip.js:22`) is new: the element a pending timer is for. It is set when the delay starts (144) and cleared by `hideTip` (114) and when the tip shows (94).
- **R2** - `app/renderer/shell.js:259`, in `shellGo` (`shell.js:254`): `hideTip()` beside `closeSheet()` and `hideFound()`, before the page is drawn. `shellGo` is the one function every page change goes through: the menu's Ctrl+1-4 (`shell.js:939-942`; keys bound at `main.js:547-548`), the side panel's links (1057), the path row (513), the search box (686) and pages.js's links. `shellDraw`/`drawPage` were not chosen: they also redraw the same page when its state arrives, which must not hide a tip. The SPEC's Files line now names it.
- **R3** - `app/renderer/tooltip.js:85-88`, `showTip`: an element that is not `isConnected` gets no words, so the existing "no words" branch hides and shows nothing.
- Nothing else changed: timing (300 ms, `TIP_DELAY_MS` still appears exactly twice), focus tips, Escape, the search box rule, Floating UI placement.

## Tests

New, in `tests/test_shell.py` after the Escape tests, under a shared fake page (`TIP_PAGE`) that runs the whole real `tooltip.js` through the existing `run_shell` Node harness, with a hand-fired timer:

- `test_a_tip_whose_element_leaves_the_page_is_hidden_at_the_next_mouse_move`
- `test_a_page_change_hides_a_showing_tip` (lifts the real `shellGo`; checks the tip is already hidden when `shellDraw` runs)
- `test_a_tip_waiting_on_its_delay_is_never_shown_for_an_element_that_left`

All three were run against the code at `3cf38f3` (files swapped in temporarily, then restored) and all three failed there.

Pass lines, each file its own process:

| | Python 3.11 (`pl\v311`) | Python 3.14 (`pl\v314`) |
|---|---|---|
| `tests/test_shell.py` | 173 passed | 173 passed |
| `tests/test_single_source.py` | 179 passed | 179 passed |
| `tests/test_repo_map.py` | 80 passed | 80 passed |

## Quick checks

- Dead code: none added; `tipWaitFor` is read at 139 and written at 94, 114, 144.
- `python -m ruff check .`: All checks passed.
- `python tools/repo_map.py update` then `check`: Map is current (426 nodes, this file included). `test_repo_map.py` and `test_single_source.py` were rerun on both interpreters after this file was added: 80 and 179 passed on each.

## Map

`docs/repo-map.curated.json`, `app/renderer/tooltip.js`: the notes gain one P202 sentence on when a tip goes with its page. The role also said "after 500 ms of hover"; the code has been 300 ms since Jason's ruling 7 (2026-09-29), so it now says 300 ms. That is a correction to the map only; the reviewer may rule on it.

## For the reviewer

Diff: `git diff 3cf38f3 claude/stuck-tip-build`. Files: `app/renderer/tooltip.js`, `app/renderer/shell.js`, `tests/test_shell.py`, `pilot/SPEC-stuck-tip.md`, `docs/repo-map.curated.json`, `docs/repo-map.json`, `docs/repo-map.md`, this file. The hands-on check (hover a Taxpayer link on Overview, press Ctrl+4) is for the Windows check; this build did not start the app.
