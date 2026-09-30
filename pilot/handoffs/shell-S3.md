# Shell S3 - renderer foundation (built)

Session: S3 builder (sonnet), 2026-09-29. **Branch: `claude/friendly-archimedes-33y9uk`**
(built on `claude/admiring-lamport-bp1sse`, the SPEC branch S1 and S3 both start
from). S4 starts from this branch, after S3's latest review says "No findings".
Last code commit: see the last line of this file. Nothing here is reviewed yet.

**A slip to undo:** this session's two commits were also pushed to
`claude/admiring-lamport-bp1sse` by mistake (that branch should stay at the
SPEC's last commit, `0776ea6`, for S1 to start from). They are identical to
the ones on the S3 branch; Jason decides whether to reset that branch to `0776ea6`.

## Done, in plain English

The new screen's frame is built and drawn. The side panel (four sections, the
counts, the last-sort line, the Pilot badge), the path across the top, the
search box, the one sort icon, the notice area and the page area all exist,
in light and dark, and the first-run setup page works from a made-up
folder to the Overview. Every colour is now a named light-and-dark pair; the
tour is one short line per step; Help can start the tour and show the terms
again. The rows and groups every page will use are in the stylesheet already.
The old screen is still in the page, hidden, so `app.js` keeps working until
the pages take over.

| SPEC section 16, S3's row | Where |
|---|---|
| tokens, light and dark (10) | `app/renderer/pilot-ui.css` (two `:root` blocks; grid steps 4/8/16/24/32/48; type roles; literal colours of `style.css` restated) |
| `shell.css` | `app/renderer/shell.css` |
| `tooltip.js` | `app/renderer/tooltip.js` (`setTip`, `setTipIfCut`, `hideTip`, `tipShowing`) |
| `index.html` skeleton (3.1) | `app/renderer/index.html` (old screen kept in `#legacy`, hidden) |
| `shell.js`: routing, side panel, path, search, sort icon, last-sort, keyboard via `shellKey`, the page side of the menu channel, the setup page | `app/renderer/shell.js` |
| pilot layer (12) | `pilot.js` (badge in `#side-foot`, no Tour button, `PilotTerms.show()` read-only with one Close), `tour.js` (title + one line), `pilot-content.js` (one line per step, new anchors, `terms.close`, label "Pilot"), `pilot-style.css` |
| harness (14.4) | `pilot/harness/` (see its README) |
| tests | `tests/test_shell.py` (29, new), and `test_pilot_ui`, `test_tour`, `test_pilot`, `test_single_source` (two probes) changed as 14.2 says |

`app.js` gained six one-line seams and nothing else (`shellVocabulary`,
`shellAdopt`, `shellNeedsRoot`, `shellChanged` in `setLocked`/`runScan`/
`stopPass`/`scanDone`, `shellProgress`, and `shellKey` first in the document's
one keydown listener). No card code was touched.

## What the next sessions need to know

**S4 (pages).** `shell.js` calls `pagesDraw(route, page)` (draw into `#page`),
`pagesKey(e)` (a key on a `role=listbox`; returns true if handled) and
`pagesMenu(id, token)` (a right-click item on a row; `false` = not mine) if
they exist. It gives S4: `shellGo(route)`, `shellRoute`, `shellFirm()`
(`{status, data}`; status idle/loading/ok/failed; `data` is the `firm` reply),
`shellLoadFirm()`, `shellLoading(title)` (title + outline rows), `shellPopup(name,
token, x, y)` (the six native menus), `setTip`/`setTipIfCut`, and the CSS the
rows use: `.rows` (the listbox), `.row` with `.row-name/.row-detail/.row-status/
.row-end > .row-date + .row-step`, `.has-step`, `.is-active`, `.is-attention/
.is-waiting/.is-done/.is-plain`, `.group-head` (+ `.is-first`), `.group-title`,
`.group-count`, `.group-sub`, `.group-none`, `.page-title`, `.page-caption`,
`.page-empty`, `.figures/.figure-number/.figure-label`, `.row-skeleton`.
`pilot/harness/pages-stub.js` shows all of them in use. S4 must:
add `pages.js` to `index.html` between `tooltip.js` and `shell.js`;
delete each card's markup from `#legacy` and its rules as it takes it over;
turn the hidden banners into notices (see "Loud failures" below); shorten
`RETIRED` in `test_shell.py`; add `app.js` and `index.html` to `TITLE_FREE`
and `pages.js` to `SHELL_FILES`; replace the notice template's Look again /
Dismiss with Retry and the close icon; and remove `--radius-pill` with the chips.

**S5 (sheet and dialogs).** `#sheet`, `#sheet-scrim`, `#sheet-title`, `#sheet-body`,
`#sheet-foot`, `#sheet-close` exist (hidden; `shell.css` frames them). `shell.js`
calls `closeSheet()`, `openRoll()`, `openReminder()`, `openSafeguards()`,
`openAbout()` if they exist and says a notice + error-log line if not.
Esc closes the sheet before the search list and the tooltip.

**S6 (join).** What the real API must supply, by key: `vocab.screen` (SPEC 11.4,
every key the harness's `stub.js` lists), `vocab.menu`, the `firm` command in
`vocab.commands`, `list.paths.clients_root` and `.status`, `list.last_pass.ok`
and `.when`, and `n`/`of` on the progress line (it already carries them:
`progress.household` is `{household} ({n} of {of})`; the last-sort line uses
those two numbers, and shows the bar alone when they are missing, so
S6 supplies no word for that case). `harness/app-stub.js` is the list of what `shell.js` needs of
`app.js` - if S4 renames one, the double changes with it.

**Proposed decision rows (S6 logs them from P85):**
1. The old screen stays in `#legacy` (hidden) between S3 and S4/S5 so `app.js` keeps finding its elements; each later build deletes what it takes over.
2. "One keydown listener" is held as: `app.js` owns the document's one listener and hands keys to `shellKey(e)`; the new files add none (row-list keys and the search box's keys reach `pagesKey`/`findKey` through it). The existing listeners in `tour.js`, `pilot.js` and the editor's table are untouched.
3. (Changed by S7, Jason's ruling 2.) Keyboard focus shows the tooltip on every control except the search box; hover shows it everywhere. S3 had left out every text box; S7 narrowed that to the search box alone, because only its tip would cover the list its typing opens.
4. Test scoping: `test_the_renderer_has_no_title_attribute` covers the new and pilot files now (`TITLE_FREE`); `app.js` and `index.html` still hold `title` attributes until S4/S5 delete them.
5. Tour step titles: rebuild 1 set the two that broke SPEC 11.1 to SPEC 12's words ("Sort", "Needs review"); the rest were left as they are.

## Loud failures - read this

Until S4 turns them into notices, the old banners live in `#legacy` and **are not
drawn**: the reader warning, the machine warnings, the last-pass line, the
after-install banner, the lock notice, the result banner, the "clients folder
set" line, and four more: `#misfits-card` ("{n} folders skipped", with Show),
`#room-card` ("Names shortened to fit"), `#household-two-years` ("Two years
open") and `#household-paused` with `#btn-accept-folder-name` ("Folder renamed",
with Accept - the household's sorting stays paused until someone accepts, so
this one is a real silent failure). The harness's "locked" shot shows only what
the real app draws (the sort icon and menus go grey); the real `#lock-notice`
is hidden until S4 moves `showLock` to a notice. Notices from `notice()`/`failed()` (in `#notices`), toasts, the counts
failure and menu-id failures all show. This branch must not ship on its own;
S4 has to move those banners before the stack lands.

## Tests run (affected only, both interpreters)

Python 3.11 and 3.13, each file its own process: `test_shell` (29), `test_pilot_ui`
(11), `test_tour` (8), `test_pilot` (18), `test_single_source` (167),
`test_layers` (29), `test_repo_map`, `test_api` (368), `test_pilot_installer` (12) - all
pass (results line under "Gate" below). `ruff check .` clean;
`repo_map.py update` and `check` current. `test_build.py::test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else`
fails on this branch **and on the branch it started from** (checked with the
changes stashed): the cloud machine, not this work.

The harness: `HARNESS_PYTHON=<venv python> node pilot/harness/shoot.mjs <dir>` shot 81
images (19 scenarios x light/dark x 1100x700/1400x900, a contrast-theme shot,
and a smoke run of the **real** `app.js` on the stub tracker: side panel filled,
Overview drawn, 0 page errors). `node pilot/harness/interact.mjs` drives 30
checks by keyboard and mouse (routes, counts, Ctrl+1..4, Ctrl+F, search, F9 sort
and Stop, F6, Esc, the setup flow, Help > Terms, Help > Take the tour, tooltip
by hover, the counts-failure notice) - all pass; it found one real bug
(`aria-disabled` missing from `h()`'s list on the "No match" option), now fixed
and pinned by `test_every_attribute_the_shell_builds_a_node_with_is_on_its_list`.

Looked at (light and dark, both sizes where they differ): Overview, empty
Overview, Needs review, Reminders, Clients, household, household with no returns,
year, return (four groups), return with nothing received, setup, loading, sort
running, sort failed, locked (no notice: the real one is hidden until S4), counts failed, search open,
tooltip by mouse and by keyboard, the sheet's empty frame, a contrast theme.
Rows fit at 1100 (name cut with "…", date and step sharing one end column).
Nothing scrolls sideways. Screenshots are not committed (regenerate with the
command above).

## Things a reviewer should know

- **Contrast-theme emulation.** In Chromium's emulated `forced-colors`, the selected
  section ("Clients") draws white text on a white plate over its Highlight fill:
  the emulator's Highlight has partial opacity and Chromium adds a backplate. The
  computed style is right (`HighlightText` on `Highlight`); a real Windows
  contrast theme has opaque colours. Check it on the office PC (Windows check).
- The logo (an `img`) is pale on the contrast theme's white `Canvas` band, as SPEC
  10.4 specifies; it is exempt as a logotype.
- `impeccable detect` over the changed UI files: two kinds of finding left, both
  answered by the SPEC: hairline + wide shadow on the sheet, tooltip and dialogs
  (Windows 11's flyout recipe, kept), and a 3px left border on the terms card in
  `pilot-style.css` (unchanged from Build E). The one real finding (a width
  transition on the progress bar) was fixed.
- `--radius-pill`, `.chip` rules, the deck, the request table and other rules for
  cards S4 removes are still in `pilot-ui.css`; they match nothing drawn.
- The row's next-step text is `aria-hidden` in the SPEC; the harness stand-in does
  not model the listbox roles fully (S4's `pages.js` owns them).
- The sheet scrim covers the whole window, top included: the menu bar is native,
  so nothing of the page's sits above it.
- The Electron window itself was not run (no `main.js` change here). First paint
  in dark (`--window-dark`) is S2's, from `pilot-ui.css` by name; the names exist.

## Files the next session needs

`pilot/SPEC-shell.md` (3, 6, 7, 13), this file, `app/renderer/shell.js` (its head
comment lists the seams), `shell.css`, `pilot/harness/` (README, `pages-stub.js`,
`app-stub.js`), `tests/test_shell.py`.

Last code commit: `f8065ce` on `claude/friendly-archimedes-33y9uk` (the handoff-only commit after it adds this line).
