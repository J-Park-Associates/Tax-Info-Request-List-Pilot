# Shell S5 - rebuild 1 (fixes for review 1)

Session: S5 rebuild-1 builder (sonnet), 2026-09-30. Branch `claude/shell-s5-sheet` (local `rebuild-s5-1`),
from review 1's tip `85069f2`. Made-up names only; nothing here reads a client document. No generative
AI, no path drawn, the renderer types no sentence, five words Title Case, 4/8 px grid: all held.

## What was fixed, per finding

| Finding | Fix | Where |
|---|---|---|
| **F1** sheet stuck after Not Requested / a Put Back that parks | The sheet remembers what it was drawn from (`sheetSeen`: the kind the file is in and its `seq`). A state that shows the same handle in another kind or at another `seq` counts as answered: the sheet moves on. The stub now keeps the handle (as the engine does) and moves `seq`, so the harness no longer hides it. | `sheet.js`, `stub.js`, `test_the_sheet_moves_on_only_when_the_file_it_shows_has_been_answered` |
| **F2** held reminder drew codes and the 25-word hold sentence | A held row draws its document alone; the two dead CSS rules went. The stub's `reason` is now the engine's long sentence, so a regression shows. | `app.js`, `style.css`, `pilot-ui.css`, `stub.js`, `interact.mjs`, `test_a_held_reminder_row_draws_its_document_alone...` |
| **F3(a)** double Unfile / Mark Missing from the menu | `writeKey`/`writeStart`/`writeDone`: a second identical write while one is in flight is not sent, and `pagesEnableFor` greys the item (`writeBusy`) meanwhile; freed on reply or refusal. | `app.js`, `pages.js`, `test_a_second_unfile_or_mark_missing...` |
| **F4 (fixable half)** decision-94 copy link | The Received row of a request links `open_keys[0]` when its one filed file is filed **under that request** (`single.identifier === item.identifier`) and has one or more copies. Confirmed: `filer._file_copies` builds `locations` with the row's own request first, `prepared_location = locations[0]`, `also_filed = locations[1:]` (`tracker/filer.py` ~5595-5619); `records.IndexEntry.filed_locations` is `[prepared_location] + also_filed`; S8a's `api._filed_copy_keys` (`tracker/api.py` 2070-2081 at 62b76fa) numbers them in that order, so `open_keys[0]` is the copy under `entry.identifier`. A file that only **answers** the request (decision 146, no copy of its own there) now shows text, not the other request's copy (the old rule linked it when it had one key). | `pages.js`, `test_the_link_kinds_are_built_from_the_apis_keys...` |
| **F5** items that cannot act | `another_return` only where the sheet has the button: a parked **document** (`!notADocument`) of the return whose state is on screen, with `fedReturns().length` (`pagesCanHandOver`). `put_back` not for a moved copy whose original is gone (`gone` on the spec). A file of a return that is not on screen stays grey for Another Return (its rule cannot be known without reading it; Check and Not Requested still work). | `pages.js`, `test_a_row_menu_offers_only_what_applies...` |
| **F6** typed toasts | Two toasts now come from the vocabulary: `toastWord(key)` reads `vocab.screen.notices[key]` and, if it is missing, says so as a failure (never a blank or a typed sentence). New words (see "Words for Jason / S1" below). A test forbids a string literal in any `toast(` call and checks the words are at most five and Title Case. | `app.js`, `vocab-mirror.json`, `test_no_toast_types_a_sentence...` |
| **F7** E91 one Advanced switch | Per-row `ed-fold` toggles, the `ed-fold-cell` column and `ed-fold-all` are gone. One button (`ed-advanced`, `aria-pressed`, word `editor.advanced`) turns every row's routing rules + taught keywords **and** the paste and rename blocks (now inside `#ed-advanced-body`) on and off. A row typed/pasted since opening stays open; a refused save turns the switch on (`showEveryFold` -> `setAdvanced(true)`); opening the editor resets it. | `app.js`, `index.html`, `vocab-mirror.json`, `test_the_editor_has_one_advanced_switch...`, `test_single_source` (editor fold tests) |
| **F8** wizard Cancels | `wf-cancel` (form step, its whole action row) and `ne-cancel` cut, with their listeners; step 1's Cancel stays, step 3's Back stays; Esc and the scrim still close `#modal`. | `index.html`, `app.js`, `test_the_wizard_keeps_the_first_steps_cancel_only...`, `test_single_source` |
| **F11** keyboard route to links | `show_in_explorer` on the `received` template when the row has a filed-copy link (`detailLink`). The Needs Review group heading's return link, its household caption link, and the household link in Overview / Reminders detail are **not** made focusable: their keyboard route is the path row (the crumbs are focusable buttons) and Enter on the row (opens the return). Say so in the S6 test notes if Jason wants them focusable. | `pages.js`, tests above |
| **F12** client-row item after navigation | After `shellGo`, `pagesClientMenu` answers only if `shellEnabled()` for the new route still includes the id (lock and rules read on arrival); else the page stays where it went. | `pages.js`, `test_a_client_rows_item_is_answered_only_if_its_rule_holds...` |
| **F13** the S8a join | See the S6 checklist below. Renderer side pinned: `JOIN_POPUPS` in `tests/test_shell.py` is the exact set of ids each template can offer (`file`, `moved`, `request`, `received`); the page answers exactly their union. The SPEC does not say a join test may be skipped or xfailed, so no failing-until-joined test was added on this branch; the join lines are the checklist. | `test_shell.py` |
| **F14(a)** received date on a moved copy | `sheetStatus(found, state)` reads the date from the index row with the moved copy's handle. | `sheet.js`, `test_the_status_line_of_every_kind_of_file...` |
| **F14(b)** request codes | Picker options read the document (value stays the identifier); "Mark {…} Missing" is filled with the request's name (`pagesItemName`) - a request it cannot name is a loud failure, never the code; the Where-It-Waits list also draws the document alone (same rule, third place). | `app.js`, `sheet.js`, `test_no_request_code_is_drawn...` |
| **F14(c)** test gaps | Unfile and Mark Missing under a live lock on `received`; client-row menus never carry `show_in_explorer`; the sheet advancing when a file is set aside. | `test_shell.py` |

## Left untouched (Jason is deciding; current behaviour stays)

- **F3(b)** the Unfile / Mark Missing reason box (a right-click Unfile still sends `note: ""`).
- **F4 several files per request** (no Unfile / no link on a "{n} Files" Received row).
- **F10** Folders Skipped two-word reasons (name only, sentence to the error log).
- **F15** the right-click write items moving the sheet on after the write, and the reminder sheet's title.
- **F9** the info dialogs' Dismiss vs Close word: S6's.

## Words for Jason / S1 (new vocabulary; P66)

Added to the harness mirror `pilot/harness/vocab-mirror.json` only (this branch's `tracker/api.py` has no `screen` block; S1 owns it):

| Key | Word | Why |
|---|---|---|
| `screen.notices.pick_request` | Pick a Request First | SPEC E33's example, Title Case; replaces the 8-word sentence toast (3 places) |
| `screen.notices.name_requests` | Name Each Custom Request | replaces "Give each custom request a document name first."; needs Jason's approval |
| `editor.advanced` | Advanced | E91's switch |

`editor.routing` and `editor.routing_all` are no longer read by the renderer: S1 can drop them.

## S6 checklist (the join)

1. `api.MENU["show_in_explorer"]` = "Show in File Explorer" **and** the same line in `main.js`'s `DEFAULT_MENU_WORDS` (`test_the_menus_default_words_are_the_apis_word_for_word`). `screen.show_in_explorer` alone is not enough: `main.js` never reads `screen`.
2. `main.js` `POPUPS` (S2's branch, `app/main.js` ~513-521) must become exactly (after the renderer's `JOIN_POPUPS`):
   `file: check, not_requested, another_return, show_in_explorer`;
   `moved: check, put_back, keep_here, show_in_explorer`;
   `request: edit_request`;
   `received: unfile, mark_missing, show_in_explorer`.
   `main.js` drops an id its template lacks, so a join that forgets one fails silently. Add the test on `main.js` there (read POPUPS, compare to `JOIN_POPUPS`).
3. Amend SPEC 5.2's table and 11.3's menu table (ledger O4: `show_in_explorer` on file and moved rows; now also received).
4. `preload.js` / `main.js` `open(p, how)` -> `openPath(p, reveal)` from S8a.
5. Add `screen.notices.pick_request`, `screen.notices.name_requests` and `editor.advanced` to the API (see above), then delete the mirror as before (`HARNESS_LIVE_VOCAB=1`).
6. Re-run the new `pagesEnableFor` behaviour against the live shape of `state.index[]` / `household.feeds` (Another Return uses `fedReturns()`).

## Tests run

Each file its own process, Python 3.11 (`/tmp/v`) then 3.13 (`/tmp/v313`), one after the other:
`test_shell`, `test_pilot_ui`, `test_single_source`, `test_layers`, `test_repo_map`, `test_api` (touched: it reads `app.js` for the moved card). See the last line for the results.
`python -m ruff check .` clean. `node pilot/harness/interact.mjs`: "all interactions pass" (two checks changed on purpose: the held row, and the parked file's menu without Another Return where the household feeds nothing).

**Mutation checks** (in place, one at a time, restored after; against `test_shell` + `test_single_source`): all caught -
F1 the comparison back to "handle only" (moves-on test); F2 identifier added to the held row; F3a `writeStart` result ignored;
F4 `>= 1` back to `=== 1`, and the `identifier` guard removed; F5 `!spec.gone`, `fedReturns`, `notADocument`, other-return guard each removed;
F11 the `detailLink` item removed; F12 the re-check removed; F14c `show_in_explorer` offered for client rows; F6 a typed toast and an over-long word;
F7 `editorAdvanced ||` dropped, `showEveryFold` not turning the switch on, the hidden body un-hidden; F8 a Cancel put back;
F14a date lookup removed; F14b code back in the option, in Mark Missing, and the loud failure removed; F13 `show_in_explorer` handler removed, the `received` item removed.

Repository map: `python tools/repo_map.py update` and `check` were run last.
