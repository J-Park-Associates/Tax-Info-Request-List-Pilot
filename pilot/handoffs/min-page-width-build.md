# P203 build - the minimum size is the page's (SPEC-min-page-width)

Built 2026-10-01 on branch `claude/min-width-build`, from `claude/min-width` at `617a5ed`. One commit; not pushed.

## What changed

- **R1** `app/main.js:710-715`: `useContentSize: true` added as the first `BrowserWindow` option, with a comment giving the reason (P203): the 1400 x 900 default and the 1100 x 700 minimum are now the page's, so the page at the smallest window is 1100 wide, not 1084; the window is drawn 16 px wider than the page.
- **R2** `tests/test_shell_menu.py:618-626`: `test_the_windows_minimum_and_default_sizes_are_its_pages` runs the real `main.js` under the file's Electron stand-in and asserts the recorded window options carry `useContentSize: True`, `width`/`height` 1400/900 and `minWidth`/`minHeight` 1100/700. (This file already records `windowOptions`; no test read `minWidth` before.)
- **R3** `pilot/SPEC-firm-columns.md:102-103`: item 14 gains one sentence - the budget is the page's, and P203 makes the minimum window's page 1100 wide. No other SPEC or runbook wording changed.
- Map: `python tools/repo_map.py update` (hashes for the changed files). No curated note needed editing: `app/main.js`'s note does not mention the window's size, and the notes that say "1100px window" now mean what they say (R3).
- Dead code: none added or found in the changed lines.

## Tests (each file its own process)

| File | Python 3.11 (`pl\v311`) | Python 3.14 (`pl\v314`) |
|---|---|---|
| tests/test_shell_menu.py | 35 passed, 3 skipped | 35 passed, 3 skipped |
| tests/test_single_source.py | 179 passed | 179 passed |
| tests/test_repo_map.py | 80 passed | 80 passed |

The 3 skips are the file's existing symbolic-link tests ("this machine cannot make a symbolic link"); the new test ran and passed on both interpreters.

`python -m ruff check .`: All checks passed. `python tools/repo_map.py check`: Map is current (430 nodes) - run after this file was added and `update` re-run, and `tests/test_repo_map.py` re-run on both interpreters on that final map.

## Left for others

- Reviewer: check R1-R3 against the SPEC.
- Proof on Windows after install (SPEC): `GetClientRect` at the minimum gives 1100, and Overview's list shows no sideways scrollbar.
