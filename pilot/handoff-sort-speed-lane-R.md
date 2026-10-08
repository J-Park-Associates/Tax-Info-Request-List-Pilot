# Handoff - Sort & Scan speed, Lane R (the app)

Builder: Lane R of [`SPEC-sort-speed.md`](SPEC-sort-speed.md) (section 5.2),
in its own worktree from `b894a32` (the SPEC with Jason's answers, 7.1).
Built against the SPEC's contract without the Python side, which Lane P
builds in another worktree at the same time. Made-up data only.

Jason's answers built here: **P228 yes** (ask all at once; the list after a
Sort is still asked, Q2(b) no), **P229 yes, built now**, with the words
"Updating, as of {time}".

## Commits

| Commit | Row |
|---|---|
| `f8458d2` P228, P229 (window): after a Sort ask all at once; last counts at launch | P228, P229 |
| `0f7bad3` Repo map: refresh for P228 and P229's window half | - |
| (this file, and the map's refresh for it) | - |

## P228 - after a Sort, the return, the Overview and the list are asked at once

- `app/renderer/app.js` `passEnded`: `shellWriteLanded()` as before, then
  `shellAskFirmNow()`; then it sends the shown return's `state` and the
  `list` at once (the state first) and awaits only the state. The state is
  drawn behind the view generation as before (`renderFor`), and the Sort's
  answer (`keepSortAnswer`) still waits for it. The list is adopted whenever
  it lands (`adoptList`) - still asked after every Sort (194's Q5, decision
  203, Q2(b)). A list that **fails** calls `shellLoadFirm()` (when a clients
  folder is set) so the Overview asked at the Sort's end is still adopted and
  no page is left saying Updating; the failure is said as before, only while
  the view is unchanged, with Retry reading the shown return.
- `app/renderer/shell.js`: `shellAskFirmEarly` renamed `shellAskFirmNow`
  (comment rewritten); P218's rule kept: a load already running sends
  nothing, and the list's adopt queues one more.
- No new `call(["list"])`: `test_single_source`'s count of three holds.
- Seen in headless Chromium (stub, list delayed 1.5 s, firm 0.8 s): `firm`,
  `state`, `list` sent at 0-9 ms; the state landed and the Sort's answer was
  kept at 29-36 ms; firm at 844 ms; list at 1,544 ms; one `firm` only.

## P229 - the window half: the last counts at launch, marked

- `app/main.js`: `firm-last` added to `EARLY_COMMANDS` (runs before the
  allowlist, beside `list` and `firm`) and to `HELD_READING_COMMANDS` (asked
  once more of a fresh process if its spare closed silently). Never a writing
  command.
- `app/renderer/app.js` `bootstrap`: `shellAskFirmNow(); shellAskFirmLast();`
  before it awaits the list.
- `app/renderer/shell.js`:
  - `shellAskFirmLast()` sends `window.tracker.call(["firm-last"])` once
    (not when counts are already drawn); a failed ask clears it, nothing shown.
  - `shellLastOf(reply)` takes the counts and their time, or null: `{last:
    null}`, an error reply, counts without `returns`, or no time shows nothing.
  - `shellShowLast()` draws them only when the reply, the words and a clients
    folder are all here **and** the fresh `firm` is still on its way with
    nothing drawn (`status === "loading"`, no data); each reply at most once.
    Called on landing and from `shellAdopt` (a reply that beat the list's
    words). A vocabulary without `screen.updating_as_of` logs the key to the
    error log and draws nothing (no word of the renderer's own).
  - Drawn as P222's held counts: `shellFirmNow = {status: "loading", data:
    last}`, so `aria-busy`, `is-updating` (figures, row statuses, pills
    muted; GrayText in a contrast theme - existing rules) and the side
    counts' `is-held` all come from the existing code. `shellFirmAsOf` holds
    the time; `shellMarkUpdating` fills `updating_as_of` with it in
    `#page-updating`, the path row's one status (set only when it changes).
  - `shellLoadFirm`: the fresh reply replaces the last counts in place; on a
    **failure** the last counts are taken down (`data: null`, the failed
    notice with Retry as today). Either outcome ends the last counts (a
    `firm-last` still on its way is dropped).
  - `shellDropEarlyFirm` (a list that asks for a folder) drops the last
    counts, asked or drawn.
  - Household and year pages (they follow the counts, P222) say the time too.
- `app/renderer/shell.css`: `.page-updating`'s fixed slot widened from `8ch`
  to `24ch` - "Updating, as of 12:59 PM" is 24 characters - kept the same
  width whether the word shows or not, so the path beside it never moves
  (Jason's rule of 2026-10-08). See departures.
- Actions while marked: unchanged code paths, which never read the counts
  (pinned): Open reads `state`; Check from a firm page always reads `state`
  and closes on a file no longer waiting; Copy/Approve act only on a card
  from the return's own read (P213); writes are judged in the engine.
- `pilot/harness/stub.js`: `firm-last` answers `{last: null}` (the API's
  refusal) in every scenario but `last-counts` (last counts at once, the
  fresh `firm` after 1.5 s) and `last-counts-fail` (the fresh `firm` fails
  after 1.5 s).
- Seen in headless Chromium (`?scenario=last-counts`, light, dark, forced
  colours, reduced motion; the word injected into the stub's vocabulary
  because Lane P's is not in this tree): at 0.5 s the Overview drawn from
  the last counts, `#page-updating` "Updating, as of 9:14 AM" (136 px in a
  182 px slot), page `aria-busy`, figures muted (GrayText under forced
  colours), side counts held; at 2.3 s the fresh counts, same 50 rows,
  marker gone. `last-counts-fail`: marked, then the page's frame alone and
  "Counts Not Available" with Retry. No page errors.

## New and changed tests

`tests/test_shell.py` (new):
- `test_after_a_sort_the_return_and_the_overview_are_asked_beside_the_list`
- `test_a_sorts_list_that_lands_last_changes_nothing_the_state_drew`
- `test_a_return_chosen_during_the_sort_is_the_one_drawn`
- `test_a_sorts_list_that_fails_still_lets_its_overview_land`
- `test_the_sorts_end_asks_the_overview_through_the_one_early_ask`
- `test_the_last_counts_are_drawn_marked_updating_as_of_their_time`
- `test_the_fresh_counts_replace_the_last_in_place`
- `test_last_counts_that_land_after_the_fresh_are_dropped`
- `test_a_failed_refresh_takes_the_last_counts_down`
- `test_a_refused_or_failed_last_count_ask_shows_nothing`
- `test_a_list_that_asks_for_a_folder_drops_the_last_counts`
- `test_the_last_counts_wait_for_their_own_words`
- `test_a_household_page_opened_on_the_last_counts_is_marked_with_their_time`
- `test_no_action_reads_the_counts_it_was_drawn_from`

`tests/test_shell.py` (changed): the `FIRM_LOAD` harness gains
`shellFirmLast`, `shellFirmAsOf`, the word and the three new functions;
`shellAskFirmEarly` → `shellAskFirmNow` throughout; two `passEnded` setups
gain a `shellAskFirmNow` fake; `test_after_a_sort_one_overview_is_asked_not_two`
kept unchanged (P218's); `test_the_path_beside_updating_keeps_its_width_when_the_word_comes`
now checks the slot against its longest words (and no more than 2 ch over).

`tests/test_single_source.py`: `LAST_COUNTS_COMMAND` and `_held_readings(api)`
(the API's held readings, plus `firm-last` only while the API lacks it);
the four early/held pins use it; `test_the_shell_allows_the_read_only_overview_before_the_first_reply`
expects `{"list", "firm", "firm-last"}`; `test_switching_returns_is_one_state_call`
now pins the state sent before the list and no `await` on the list; new
`test_the_last_counts_are_an_early_read_only_command_the_api_answers`
(skipped until the API has `firm-last`).

`tests/test_api.py`: the one renamed line -
`test_sort_and_scan_ends_with_one_list_then_one_state` →
`test_sort_and_scan_ends_with_one_list_and_one_state`, docstring updated
(body unchanged).

## Assumed contract (Lane P)

- Command: **`firm-last`**, no arguments, in `api.COMMANDS` and
  `api.HELD_READING_COMMANDS`, not in `WRITING_COMMANDS`.
- Reply: **`{"last": null}`** when refused; otherwise
  **`{"last": {<the firm reply: returns, totals, files, ...>, "as_of": "<time words>"}}`**.
  The renderer reads `reply.last` as the firm data and `last.as_of`, falling
  back to a top-level `reply.as_of`, so either placement of `as_of` works;
  the counts must be under `last`. `as_of` is inserted as given (the API's
  time words, e.g. "9:14 AM"). An `error` reply shows nothing.
- `last.paths` (if any) are **not** learned by `main.js` as openable (it
  learns a reply's top-level `paths` only): a file link on the marked page is
  refused until the fresh reply lands. Deliberate - see departures.
- Word: **`vocab.screen.updating_as_of`** = `api.SCREEN["updating_as_of"]`,
  "Updating, as of {time}", placeholder `{time}`.

## Tests meaningful only after the merge

- `test_single_source.py::test_the_last_counts_are_an_early_read_only_command_the_api_answers`
  - skipped in this tree; after the merge it runs and pins the API's lists
  and the word.
- `test_single_source.py`: the four early/held pins that use
  `_held_readings` pin `main.js` to the API's lists exactly once the API has
  `firm-last`. **At merge, delete `LAST_COUNTS_COMMAND`'s shim**
  (`_held_readings` → `set(api.HELD_READING_COMMANDS)`), so a drift fails.
- `test_shell.py::test_the_path_beside_updating_keeps_its_width_when_the_word_comes`
  reads `api.SCREEN["updating_as_of"]` once it exists (falls back to
  `APPROVED_UPDATING_AS_OF` until then; drop the fallback at merge).
- The `test_shell.py` P229 tests run the renderer against harness words and
  faked replies in Lane P's shape; they pass now and stay meaningful only
  while that shape is the API's (above).
- The real end to end - launch with a filled firm cache shows "Updating, as
  of {time}" - needs Lane P's `firm-last`; a Windows hands-on step, not run.

## Departures

1. **The Updating slot is 24 ch, always** (was 8 ch). The SPEC said reuse
   the slot; at 8 ch "Updating, as of 9:14 AM" would be cut to
   "Updating…" and the time never seen. Jason's 2026-10-08 rule (the slot
   never changes width) is kept by widening it once: the path loses about
   16 ch (about 110 px at 12 px) on every page, always. Measured in
   Chromium: the words take 136 px of the 182 px slot; 20 ch would fit the
   words but not the character-count rule the existing test uses. For
   review / Jason.
2. **List failure after a Sort**: the SPEC did not say; the early Overview
   would otherwise wait for ever, so a failed list starts the load that adopts
   it. The failure keeps today's notice and Retry.
3. **Last counts' file paths are not openable** until the fresh reply (main.js
   learns top-level `paths` only). Safer, consistent with "every action
   reads fresh"; a click on a file link in those seconds says Not Opened.
   If Lane P puts `paths` at the top level it would be learned instead.
4. `firm-last` is asked again on every `bootstrap` (start-up, its Retry,
   after set-root); after set-root the API refuses (another root's head), so
   nothing shows.

## Gate (SPEC 5.3, Lane R)

`python -m ruff check .` clean (no Python dead code; the JS changes leave no
unused function or variable). Each file its own process, two at a time:

| File | Python 3.11 (venv311) | Python 3.13 (python3) |
|---|---|---|
| `tests/test_shell.py` | 209 passed | 209 passed |
| `tests/test_api.py` | 458 passed | 458 passed |
| `tests/test_single_source.py` | 188 passed, 1 skipped | 188 passed, 1 skipped |
| `tests/test_shell_menu.py` | 38 passed | 38 passed |
| `tests/test_pilot_ui.py` | 11 passed | 11 passed |
| `tests/test_layers.py` | 29 passed | 29 passed |
| `tests/test_repo_map.py` | **1 failed**, 79 passed | **1 failed**, 79 passed |
| `tests/test_tripwire.py` | 19 passed | 19 passed |

The skip is `test_the_last_counts_are_an_early_read_only_command_the_api_answers`
(waits for Lane P). **The one failure is not Lane R's to fix:**
`test_repo_map.py`'s check that every `name()` the curated prose names still
exists finds `shellAskFirmEarly()` in the curated notes of `app/renderer/app.js`
and `app/renderer/shell.js` (`docs/repo-map.curated.json`, off limits to this
lane). The SPEC renames it to `shellAskFirmNow`; the merge must make that edit
in the curated file (below) and run `repo_map.py update` - then it passes.

`python tools/repo_map.py update` and `check` (exit 0) after each commit; `ruff check .` clean.

## Doc changes the merge needs (not Lane R's files)

- `docs/repo-map.curated.json`: app.js's note says "the page is redrawn with
  one `list`, then one `state`" and "bootstrap calls shellAskFirmEarly()";
  shell.js's note says "shellAskFirmEarly() sends firm beside list". Now:
  passEnded asks `state`, `list` and `firm` at once (P228), `shellAskFirmNow`,
  and P229's `shellAskFirmLast`/`shellShowLast`/`shellFirmAsOf`, main.js's
  `firm-last` in EARLY and HELD. Then `repo_map.py update`.
- `docs/runbook.md`: if it says the window asks the list "then" the return
  after a Sort, correct it (P228; no such sentence found by a grep here); and
  one line on the launch's "Updating, as of {time}" (P229) where the
  Updating marker is described.
- `pilot/wording-shell.tsv`: the `screen.updating_as_of` row (Lane P).
- `DECISIONS.md` P228, P229 rows; `pilot/SPEC-speed-round.md` and
  `pilot/handoff-speed-lane-R.md` mention `shellAskFirmEarly` - history,
  left as written.
