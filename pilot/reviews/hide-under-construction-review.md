# Review: hide the Under Construction sections (P197)

Meant for `pilot/reviews/hide-under-construction-review.md` in worktree
`agent-a48ab460885e4d3d6`. This session's hook refused writes into another
worktree, so the file is here; copy it across.

Reviewer: a separate agent (did not write the SPEC or build). 2026-10-01.
Diff reviewed: `git diff a4a8e07..73160a1` on `claude/hide-under-construction`.
Standard: P197 (Jason: "Add a setting to hide "Under Construction" sections
from sidebar"), `pilot/SPEC-hide-under-construction.md` (Q1-Q3 built as
recommended), the build hand-back, the repo CLAUDE.md, Jason's global design
preferences (Fluent 2 behaviour, firm look, no monospace).

**Verdict: no MUST. Two SHOULDs, four NITs.** The setting does what Jason
asked; the remaining items are a start-up flicker and two stale doc lines.

## The orchestrator's question 1: is the menu word missing from main.js?

**No - the premise does not hold.** `app/main.js` *is* in the diff
(`git diff --stat a4a8e07..73160a1` lists it: 19 lines). The word is in
`DEFAULT_MENU_WORDS` at `app/main.js:505` (`show_under_construction: "Show
&Under Construction"`), the View menu's `BAR` row at `app/main.js:548`, the
`ALWAYS` set at `app/main.js:565`, and `CHECKABLE` / `menuChecked` at
`app/main.js:569`, `:573`. The equality guard
`tests/test_shell_menu.py::test_the_menus_default_words_are_the_apis_word_for_word`
reads `DEFAULT_MENU_WORDS` by regex and compares it to `api.MENU`. It passes
on both interpreters, so it covers the new word. The item is in the menu from
the first frame, enabled and ticked.

## Findings

### SHOULD

**S1. With "hidden" stored, the five items flicker on at start-up and then
vanish.** `app/renderer/shell.js:360` - `drawSoon()` runs only from `drawSide()`,
and the first `drawSide()` comes from `shellVocabulary()`. That runs only after
the page has asked the engine and the engine has answered
(`app/renderer/app.js:1822`, reached from `bootstrap`'s awaited
`loadEngagements`, `app.js:1906-1909`). Until then `#shell` is visible, and so
are the five Under Construction icons (no words yet). When the words arrive,
the icons disappear and the panel below them moves up. That is the
"flash of the items on start" the brief asked about. Separately,
`main.js:573` shows the menu ticked until the page first speaks, so Alt
pressed in that first second shows the wrong tick for a moment.
*Fix:* `drawSoon` needs only the page and this PC's storage, not the words.
Call it once at load, in shell.js's wiring section, beside the `data-soon`
click wiring (`app/renderer/shell.js:1068`):
`drawSoon();   // a stored "hidden" applies before the first paint (P197)`.
Add one line to `test_the_setting_is_this_pcs_and_the_side_panel_draws_it_on_every_draw`
(`tests/test_shell.py:4026`) asserting that call is at the top level of
`stripped_js("shell.js")`. The tick can stay as it is (the menu bar is hidden
until Alt), or `shellEnable()` can be sent at load too if
`shellEnabled()` is safe before the vocabulary arrives - builder's choice.

**S2. Two docs still describe the menu message as `{enable}` alone.**
`pilot/SPEC-shell.md:641-643` (5.3: "sends `{enable: [ids]}` ... It never adds,
removes or renames an item for the page") and `pilot/SPEC-shell.md:654` (5.4's
copy of preload's comment, which `app/preload.js` itself now words as
`{enable: [ids], checked: [ids ticked]}`). Also `docs/repo-map.curated.json:193`,
the `app/preload.js` role ("send posts the page's {enable} or {popup, ...}").
SPEC section 6 says the change makes the SPEC-shell lines true in the same
commit; these were missed.
*Fix:* in 5.3, "sends `{enable: [ids], checked: [ids]}`: the ids whose rule
in 5.1 holds now, and the checkable ids that are on (P197; `main.js` keeps only
`CHECKABLE` ids, and a message without `checked` leaves the tick)". In 5.4,
copy preload's new comment line word for word. In the curated preload role,
"{enable, checked}". Then run `python tools/repo_map.py update`.

### NIT

**N1. The native tick can briefly disagree with the page if the page's
answer fails.** `app/main.js:616`. Electron flips a checkbox item's own
`checked` when it is clicked. If `shellToggleSoon` throws before `shellEnable`
(`shell.js:402-417`), the menu shows the flipped tick until the next rebuild.
`menuChecked` is unchanged, so the next page message that differs puts it
right. *Fix (optional):* in the item's click handler, rebuild the menu after
sending when `CHECKABLE.has(id)`, so the tick always comes back from
`menuChecked` until the page confirms it. Or leave it and record the edge in
the SPEC's ruling 6.

**N2. Two test gaps.**
(a) A damaged stored value (for example `"HIDDEN"` or `"1"`) reads as shown.
The code is right (`shell.js:371`, `=== "hidden"`), but no test says so.
(b) Hiding while focus is *elsewhere* leaves focus alone. Untested: the one
"focus left alone" step in `tests/test_shell.py:3989` is a *show*, where
`lost` is always false.
*Fix:* in `test_storage_that_cannot_be_read_...` or a new
`test_a_damaged_stored_value_shows_them`, set `store.data[SOON_KEY] = "1"` and
assert `hiddenNow() == []`. In the 3989 test, add a hide step with
`document.activeElement` set to a page item, and assert that `said.focus`
does not grow.

**N3. `tests/test_shell.py:3984-3986` asserts `"side-workspace-heading"`
twice in the hidden list.** One is the `<h2>`'s id and one is the `<ul>`'s
`aria-labelledby`, but read cold it looks like a typo. *Fix:* have `hiddenNow()`
label a list as `list:<aria-labelledby>`, or add a one-line comment saying the
heading and its list are both hidden.

**N4. SPEC-shell 5.1's View rows (`pilot/SPEC-shell.md:~580-587`) do not list
the new item** (nor Reset Column Widths, an earlier omission). *Fix:* add
`| | Show Under Construction (show_under_construction), a checked item | - | always (P197) |`
after Refresh. Optional.

## Checked and found sound

- **Hiding removes the items, not just fades them (question 2).**
  `.hidden` is `display: none` (`app/renderer/style.css:509`). Every display
  rule on the side panel's items is written under `:not(.hidden)`
  (`shell.css:73`, `:86`, `:88`). `.side-heading` and `.side-list` set no
  display, so the class wins on the `<h2>` and `<ul>` too. A display:none
  item leaves the Tab order and the accessibility tree. The order comes back
  as it was, because no node is moved. `#side-sections`, which also holds the
  built pages, loses only its two `<li>`. `drawSoon` copes with a panel that
  has no such list: the loops simply find nothing, and a missing heading is
  guarded (`if (heading)`). Focus on a hidden item goes to `focusRegion("side")`
  (`shell.js:986-990`), whose first choice is never an Under Construction
  item. On the first-run page those items are disabled, so they cannot hold
  focus there. `hideTip()` hides a tip that was showing.
- **The remembered choice (question 3).** It is kept in `localStorage`
  (`tracker.underConstruction`, value `hidden`), the column widths' mechanism
  (`pages.js:869`, `:902`, `:922`). It is never stored in `settings.json`, and
  a test checks that. Unreadable storage shows the items. A missing or
  damaged value shows them too, because only `"hidden"` hides. A refused write
  still holds the choice while the app is open. The tick follows the stored
  state from the page's first message onward (S1 covers the first second).
- **Alt, V, U (question 4).** No other View item has `&U` or starts with U;
  a menu test pins that. The item has no shortcut key. The words are Title
  Case and three words long. The `wording-shell.tsv` row, SPEC-shell 11.3 and
  SPEC-lists 15.1 all match `api.MENU` and the screen. It is a native Windows
  check item, so Windows draws the tick, the focus and the High Contrast
  colours. Nothing animates. No font is touched.
- **preload.js (question 5).** The change is a comment only. Nothing new is
  exposed to the page, and `contextIsolation`, `send` and the channel are
  unchanged. `main.js` treats `checked` as untrusted: it keeps only ids it
  knows, keeps a list it can read, and keeps only `CHECKABLE` ids
  (`main.js:666`).
- **Dead code, tests, stand-in, map (question 6).** Every new name is used,
  and there is no commented-out code. The test names state claims. The
  `const shellChecked = () => [];` added to
  `test_a_menu_channel_that_throws_is_a_notice_and_never_stops_a_route_change`
  (`tests/test_shell.py:2274`) hides no defect: that fixture stands in for
  everything `shellEnable` calls, and in the real code `shellChecked()` runs
  inside `shellEnable`'s own `try` (`shell.js:862-866`), so a failure there
  would still be a notice. The map is current.

## Runs (each file its own process, in parallel)

| File | Python 3.11.15 (scratchpad venv311) | Python 3.14 (`C:\Python314`) |
|---|---|---|
| tests/test_shell.py | 162 passed | 162 passed |
| tests/test_shell_menu.py | 33 passed, 3 skipped | 33 passed, 3 skipped |
| tests/test_api.py -k "menu or short_word" | 4 passed, 439 deselected | 4 passed, 439 deselected |
| tests/test_layers.py | 29 passed | 29 passed |
| tests/test_single_source.py | 179 passed | 179 passed |
| tests/test_repo_map.py | 80 passed | 80 passed |

The 3.11 `test_shell_menu` timing flake did not show; no rerun was needed.
`python -m ruff check .`: All checks passed. `python tools/repo_map.py check`:
"Map is current (411 nodes, generated 2026-10-01)". It ran with no review
file in the worktree, so nothing needed setting aside.

Not done (needs a person on Windows): View > Show Under Construction off and
on in the real app, Alt+V+U, Tab focus on an item when hiding it, High
Contrast, and a restart with "hidden" stored (S1's flicker is visible there).
