# Review: lane 4 / 4b, the lists (branch `claude/column-order`)

Reviewer: separate agent (built none of it, wrote none of the SPEC). Date: 2026-09-30.
Scope: `git diff 877c7a2..0d941d5` (24 files; lane 4 bf2d9ed, 11e2695; lane 4b fefb93d..0d941d5).
Read: SPEC-lists 1-18 (targeted), both handoffs, Jason's P140/P141/P145/P149/P152-P155/P180
(`claude/wincheck-shell-results`, read only), branch rows P135-P139 and P170-P179, map nodes of
the changed modules. Nothing committed, pushed or edited in the tree except this file.

Counts: **1 MUST, 5 SHOULD, 5 NIT.**

## MUST

**M1. A one-sided related link cannot be removed from the side that lacks it, and re-saving the
side that holds it does not complete it** - `tracker/api.py:4109-4129` (`_mirror_related`),
called at `tracker/api.py:4176` with `held.related` as "before".
The SPEC (`pilot/SPEC-lists.md:392-396`) and P170 promise: "removing it from either side removes
it from both" and "a save that stopped half way still shows the link and saving again completes
it". The mirror only acts on names that differ between this record's own `before` and `after`,
but the screen (`_household_links`, `api.py` ~3670) and the editor (`app.js:1519-1521`, which
merges the list's inbound links into `editorRelated`) both treat an inbound-only link as present.
Probe (scratchpad `probe/test_probe_related.py`, `tests/test_api.py` fixtures, made-up names):
Park's record names Lee, Lee's does not (the crash case).
- `list`: Lee shows `Related: Park Family`, Park shows `Related: Lee Family` (two-sided on screen).
- `state` of Lee: `household.related == []`.
- Re-save Park with `["Lee Family"]`: exit 0, **Lee's record still `()`** (not completed).
- Save Lee with `[]` (what the editor sends after the person removes Park): exit 0, **Park's
  record still `('Lee Family',)`**, and `list` still shows Lee linked to Park. The person's
  removal is silently undone - a write that reports success and changes nothing.
Fix: make the mirror reconcile, not diff. In `_cmd_edit_household`, compute `before` as this
record's list **plus every household whose record names this one** (walk the siblings once:
`households_named(household_dir.parent, <all names under the root>)` or the registry the `list`
command builds), and in `_mirror_related` visit every name in `before | after` (not only the
changed ones), writing each other record so it names this household iff this household's new
list names it. Add a test in `tests/test_api.py` for exactly the probe above (one-sided link:
removing from the missing side clears both; re-saving the holding side completes the other).

## SHOULD

**S1. Mirror reads the other household outside its lock** - `tracker/api.py:4124` loads, `:4129`
saves. `save_household` diffs the stale `info` against the store under the lock, so a change to
the other household's members/contact/link/feeds made between the two lines is reverted by this
save. Low risk on one PC, but it is a lost update. Fix: take `engagement_lock(other.path)`, read
`load_household_info` inside it, and call `save_household(..., lock_held=True)` - still one lock
at a time, so the no-deadlock argument holds.

**S2. The link panel is dropped, with focus, by any redraw** - `app/renderer/pages.js:1598`
(`pagesDraw` calls `pagesClosePanel(false)` on every draw). A firm reply that arrives while the
panel is open (after a sort, a refresh) removes the focused panel and leaves focus on `<body>`
(Fluent 2: focus must not be lost). Fix: in `pagesDraw`, if a panel was open, close it with
`back = true` (or re-open it on the redrawn mark when the route is unchanged).

**S3. Focus can be invisible in the link panel** - `app/renderer/shell.css:892`
(`#link-panel:focus { outline: none; }`) with `pages.js` `(first || node).focus()`: when every
linked name is a retired one (`path ""`, no `.link-to` button), focus lands on the panel itself
with no ring. Fix: `#link-panel:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }`
(forced colours already give `:focus-visible` `CanvasText`), or drop the `outline: none`.

**S4. The Related Households picker has no accessible name** - `app/renderer/index.html:222`
(`<select id="hh-edit-related-pick">`), label is a bare `<span id="hh-edit-related-label">`.
Same pattern as the older feeds picker (`index.html:211`), copied. Fix:
`aria-labelledby="hh-edit-related-label"` on the select and on `#hh-edit-related` (and the same
on the feeds pair).

**S5. Escape closing the panel is not pinned by a test** - `app/renderer/shell.js:940-945`. The
panel test (`tests/test_shell.py` ~3049) calls `pagesClosePanel(true)` directly; reverting the
Escape branch in `shellKey` fails nothing. Fix: drive `shellKey({key: "Escape", ...})` with a
panel open and assert it closes and focus returns to the mark/list.

## NIT

- **N1** `tracker/api.py:681-690`: `CLIENT_TYPE_FORMS` sits between `RELATED_LABEL` and
  `ADD_RELATED_LABEL`, splitting the comment that describes the RELATED_* words. Move it below
  `RELATED_UNKNOWN`.
- **N2** `tracker/api.py:4088`: a `related` that is not a list is refused as "(blank) is not a
  household this one can be related to" - misleading for a string. Use a message that says the
  list is not a list of names (the admission's wording).
- **N3** `pilot/SPEC-lists.md:466` claims `--st-linked` is "5.66:1 or more on every surface it
  sits on"; on its own hover (`.link-mark:hover`, `--bg-pressed`) it is 5.56:1 light, 5.84:1
  dark. Still well over 3:1; correct the SPEC line and add the pair to section 16's table.
- **N4** `app/renderer/pages.js:1086`: the "More Actions" button opens a menu but has no
  `aria-haspopup="menu"`. Add it.
- **N5** 1100px margin is 3px (lists need 840px, cards 842px, of 843px beside a classic 17px
  scrollbar, P179). Correct today; any added padding will scroll sideways again. Consider a test
  that sums the grid tokens against 843.

## Rulings checked (built as written unless noted)

- P180 "Sort by {Column}": `columns.sort_by`, header tooltip seen in the harness ("Sort by Client");
  no "Order by" left in code (history rows only).
- P140: version badge, installer name, RELEASE.md untouched (`pilot-content.js` not in the diff).
- P141/P171: violet `i-link` mark, click opens panel naming each household and kind, names are
  links; Escape returns focus (`pagesClosePanel(true)`); click outside closes (focus goes where
  clicked). Kinds "Also Feeds / Fed By / Related".
- P145/P149: cards, tabs All / Need You (n) / Waiting (n) with `aria-pressed`, pills with dot,
  form chip, reason cards as filters, reason pills one amber family (`--warn-bg` +
  `--st-attention`) with an icon per reason; request chip short title with full title tooltip.
- P152/P174: 50 per page after order/tabs/cards/type filter; any change resets to page 1
  (`pagesOrderBy`, `pagesPick`, type click); Needs Review pages by whole groups
  (`pagesPaged` with `sizeOf`); sticky header row.
- P153/P154/P175: JP logo band, no profile, last-sort line kept in `#side-foot`; Needs Review
  badge amber (`shell.css:142`); five "(Under Construction)" items `aria-disabled`, focusable,
  tooltip "Under Construction", click = `toastWord` only, no `call(`/`shellGo` (pinned by test).
  Settings opens `change_root`. Client Types match the recorded `form` only.
- P155: new words say "Tax Document Console"; no existing name renamed (window title still
  "Tax Document Tracker Pilot", correctly left for the rename pass).
- P176: return-page section bar, icon, badge, edge. Names stay underlined links.
- No monospace anywhere in `app/renderer` (grep: monospace/Consolas/Courier - none).
- Reply fields are additive only (no removed or renamed key in the api diff).
- Standing rules: nothing sent, nothing inferred (related comes only from a person's save),
  no document read. `test_layers` passes. Decision 186: new files carry made-up names only.

## Engine probes

- **Deadlock:** `_cmd_edit_household` holds no lock across the mirror (not in any `with
  engagement_lock`); `save_household` takes and releases each household's lock in turn. No two
  locks held at once, so no lock-order deadlock. Confirmed by reading `api.py:4132-4180`,
  `households.py:151-190`.
- **Crash between the two writes:** yes, it leaves a one-sided record that the screen shows as
  two-sided (deliberate, SPEC 9.1) - but see M1: neither side can then repair or remove it
  except by saving the missing side's editor (which silently re-adds it).
- **Upgrade from main (real main code, not a dropped column):** `git archive 877c7a2` in the
  scratchpad; main wrote a schema-19 store from `tests/conftest.make_engagement` data; the branch
  opened it: `user_version 20`, nothing set aside, `store.check == []` before and after sync,
  `admitted_by 3` after sync (re-judged under admission 3, admitted), requests rows identical.
- **Older code on a schema-20 store:** main's `store.open` refuses it by name
  ("... was written by a newer version of the tracker (version 20 ...)") for both the store and
  the household data store. A journal line carrying `related` read by main is ignored
  (`household_from_json` drops unknown keys - the existing, deliberate forward-compat rule), and
  main never writes `related`, so it cannot erase one.
- **Validation:** `_related_from_spec` refuses self, blank, repeat, non-existent (tested);
  admission refuses non-list / non-text / non-folder-name (`test_store`).
- **Measured 1100 x 700** (harness `pilot/harness/serve.mjs` in the Browser pane, stub data):
  Overview/Needs Review/Reminders/Clients - no document sideways scroll, no cut `.pill-word`,
  `.row-status`, `.row-name`, `.col-word`, footer or tab. Every reason word forced into a Needs
  Review pill: longest "Looks Like Wrong Document" **189px in the 200px Reason column**, none cut
  (builder said 191px; PIL with a 16px icon gives 194px - the icon is 12px on screen). Ctrl+Shift+Right
  on a focused header: 200 -> 216px, focus kept, live region "Client Width 216". (Harness
  Chromium uses overlay scrollbars, so the 17px classic-scrollbar case is by arithmetic only.)
- **Contrast recomputed from the CSS hex values (WCAG):** `--st-linked` on page/hover/band/raised
  6.85/6.25/6.55/6.85 light, 7.66/6.62/7.23/6.87 dark; on `--bg-pressed` 5.56/5.84 (N3);
  `--st-attention`/`--warn-bg` 7.52/8.05; `--st-waiting`/`--info-bg` 9.52/7.85;
  `--st-done`/`--ok-bg` 7.25/9.07; `--text-secondary`/`--bg-band` 7.91/8.84;
  `--text-secondary`/`--bg-pressed` 6.71/7.13; `--link`/`--bg-band` 12.11/8.85. All match the
  SPEC table; all pass.
- Motion: `--dur` 150ms, reduced-motion block zeroes transitions and the panel's fade.
- Forced colours: pills/chips/cards/badges edged, link mark `ButtonText` with `CanvasText` edge,
  pressed tab/card `Highlight`, section icons carry the sections. Not checked on screen.

## Tests (each file its own process, four at a time)

`.venv` = Python 3.14.3, `.venv311` = Python 3.11.15.

| File | 3.14 pass line / exit | 3.11 pass line / exit |
|---|---|---|
| test_shell.py | 2 failed, 134 passed / 1 | 2 failed, 134 passed / 1 |
| test_shell_menu.py | 1 failed, 30 passed, 2 skipped / 1 | same / 1 |
| test_api.py | 410 passed / 0 | 410 passed / 0 |
| test_store.py | 178 passed / 0 | 178 passed / 0 |
| test_records.py | 49 passed / 0 | 49 passed / 0 |
| test_households.py | 16 passed / 0 | 16 passed / 0 |
| test_layers.py | 29 passed / 0 | 29 passed / 0 |
| test_single_source.py | 172 passed / 1 | 172 passed / 1 |
| test_repo_map.py | 80 passed / 0 | 80 passed / 0 |
| test_vocab_report.py | 28 passed / 0 | 28 passed / 0 |
| test_tripwire.py | 19 passed / 0 | 19 passed / 0 |
| test_errors.py | 83 passed / 0 | 83 passed / 0 |

Failures are only the known pre-existing ones: `test_the_harness_stub_speaks_the_apis_vocabulary`
and `test_the_harness_stub_replies_have_the_shape_of_the_engines` (WinError 206),
`test_reveal_is_refused_when_the_file_is_no_longer_a_file_or_is_a_link` (WinError 1314),
and `test_single_source` exit 1 from the decision-185 tripwire with every test passing
("open of the checkout's settings file" in `test_the_app_opens_one_window`).

## Checks

- `python -m ruff check .` - All checks passed (exit 0).
- `python tools/repo_map.py check` - Map is current (347 nodes) (exit 0).
- `python tools/vocab_report.py check` - Report is current (exit 0).
- Dead code: every new JS function/const and Python name is used; no commented-out code found.
