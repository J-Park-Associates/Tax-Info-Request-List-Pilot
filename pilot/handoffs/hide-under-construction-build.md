# Build handoff: hide the Under Construction sections (P197)

Branch `claude/hide-under-construction`, stacked on `a4a8e07` (tip of
`claude/zen-easley-93548b`). Not pushed, no pull request. Built 2026-10-01.
SPEC: `pilot/SPEC-hide-under-construction.md`. Awaiting the separate review.

## Rulings built (SPEC section 2)

| Ruling | Where |
|---|---|
| 1. One setting hides all five items and the Workspace heading and list (a heading whose every item is Under Construction) | `app/renderer/shell.js:387` `drawSoon` |
| 2. Hidden = the `.hidden` class (display: none: out of the Tab order and the accessibility tree); the `hidden` attribute would lose to `#side-sections li:not(.hidden)` | `shell.js:387-399` |
| 3. Focus on a hidden item moves to the side panel's current page (`focusRegion("side")`, F6's place); a showing tip is hidden. No page changes: these items open none | `shell.js:402-419` `shellToggleSoon` |
| 4. View menu check item, last in View, enabled from the first frame (ALWAYS) | `app/main.js:548`, `:565`; page's list `shell.js:840`; answer `shell.js:945` |
| 5. Kept on this PC: `localStorage` `tracker.underConstruction` = `hidden`; unreadable storage shows them; a refused write holds while open | `shell.js:49`, `:62`, `:367` `shellReadSoon` |
| 6. The tick follows the page: `{enable, checked}`; main keeps only `CHECKABLE` ids, ignores a missing `checked`, rebuilds only on a change; ticked until the page speaks | `shell.js:379` `shellChecked`, `shellEnable`; `main.js:569-573`, `:616`, `:666`; `app/preload.js:19` comment |
| 7. Native Windows check item (tick, focus, High Contrast are Windows'); Alt, V, U; no Ctrl shortcut; no motion | `main.js:616` |
| 8. Words: `api.MENU["show_under_construction"] = "Show &Under Construction"`, mirrored in main.js | `tracker/api.py:1258`, `main.js:505` |

Docs in the same change: `pilot/wording-shell.tsv` (one `api.MENU` row),
`pilot/SPEC-shell.md` 11.3 table, `pilot/SPEC-lists.md` 15.1 (one line),
`app/renderer/index.html` comment, `docs/repo-map.curated.json` (main.js and
shell.js notes) + `update`; `pilot/DECISIONS.md` P197 status. README and
`docs/runbook.md` mention neither the items nor the View menu's items: no line
changes. `pilot/HANDOFF.md` is left for the orchestrator at landing. No new
decision row (P198-P199 not taken). No engine module, no `settings.json`.

## Owner questions (built as recommended meanwhile)

- Q1 where it lives: (a) built - View menu check item, kept on this PC; (b) a line in the settings dialog / `settings.json`.
- Q2 a new install: (a) built - shown; (b) hidden.
- Q3 the words: (a) built - "Show Under Construction"; (b) "Show Unfinished Pages".

## Dead code

New names all used (`SOON_KEY`, `shellSoonHidden`, `shellReadSoon`,
`shellChecked`, `drawSoon`, `shellToggleSoon`, `CHECKABLE`, `menuChecked`);
no commented-out code, no unused imports. `node --check` on main.js,
shell.js, preload.js: ok.

## Tests (each file its own process, in parallel)

| File | Python 3.11.15 (scratchpad venv) | Python 3.14.3 (`C:\Python314`) |
|---|---|---|
| tests/test_shell.py | 162 passed | 162 passed |
| tests/test_shell_menu.py | 33 passed, 3 skipped | 33 passed, 3 skipped |
| tests/test_api.py::test_every_short_word_the_engine_adds_is_five_words_or_fewer | 1 passed | 1 passed |
| tests/test_layers.py | 29 passed | 29 passed |
| tests/test_single_source.py | 179 passed | 179 passed |
| tests/test_repo_map.py | 80 passed | 80 passed |

The first test_shell run failed one existing test on both interpreters
(`test_a_menu_channel_that_throws_is_a_notice_and_never_stops_a_route_change`):
its fixture stubs what `shellEnable` calls and lacked the new `shellChecked`;
the stub was added and test_shell alone rerun (the pass lines above). The 3
skips are the pre-existing "cannot make a symbolic link" ones. The 3.11
test_shell_menu timing flake did not show. New tests: test_shell.py 3973,
3989, 4012, 4026; test_shell_menu.py 423, 439, 456 (and the harness now
records `checked`; the ALWAYS set gains the id).

`python -m ruff check .`: All checks passed. `python tools/repo_map.py
check`: Map is current (411 nodes, after this handoff was added).

## Not done

Not run in the real app on Windows (a hands-on check: View > Show Under
Construction off and on, Alt+V+U, focus on a Tab-focused item, High Contrast,
a restart keeps it). No push, no pull request.

## Review fold (2026-10-01)

Review: `pilot/reviews/hide-under-construction-review.md` (no MUST); rulings
word for word: `pilot/reviews/hide-under-construction-rulings.md`.

- **S1** (flash at start): `drawSoon();` once at load in shell.js's wiring
  section, before the Under Construction click wiring; pinned in
  `test_the_setting_is_this_pcs_and_the_side_panel_draws_it_on_every_draw`
  (a top-level `drawSoon();` line). The menu tick at start is left as it was
  (the menu bar is hidden until Alt; NIT 1's rebuild covers a click).
- **S2**: SPEC-shell 5.3 now says `{enable: [ids], checked: [ids]}` and how
  main.js treats `checked`; 5.4's preload copy matches preload.js word for
  word; the curated `app/preload.js` role says `{enable, checked}`; map updated.
- **NIT 1**: main.js's item click rebuilds the menu after sending when the id
  is checkable, so the tick returns to what the page last said and only the
  page's reply moves it. Test
  `test_a_chosen_check_item_keeps_the_pages_tick_until_the_page_answers`
  (an ordinary item still rebuilds nothing).
- **NIT 2**: `test_a_damaged_stored_value_shows_them` ("HIDDEN", "1", "true",
  "") and `test_hiding_while_focus_is_elsewhere_leaves_focus_where_it_is`.
- **NIT 3**: `hiddenNow()` labels a list `list:<aria-labelledby>`, so the
  heading and its list read as two different things.
- **NIT 4**: SPEC-shell 5.1's View rows gain Show Under Construction (always,
  P197).

Dead code: none added; `node --check` main.js and shell.js ok. Tests, each its
own process, in parallel:

| File | 3.11.15 | 3.14.3 |
|---|---|---|
| tests/test_shell.py | 164 passed | 164 passed |
| tests/test_shell_menu.py | 34 passed, 3 skipped | 34 passed, 3 skipped |
| tests/test_single_source.py | 179 passed | 179 passed |
| tests/test_repo_map.py | 80 passed | 80 passed |

ruff: All checks passed. Map check: current (after this note, `update` run).
