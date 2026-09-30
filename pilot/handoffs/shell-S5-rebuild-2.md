# Shell S5 - rebuild 2 (Jason's rulings 16-21)

Session: S5 rebuild-2 builder (sonnet), 2026-09-30. Branch `claude/shell-s5-sheet` (local `rebuild-s5-2`),
from `b495fe6`. Made-up names only; nothing here reads a client document. No generative AI, no path
drawn, the renderer types no sentence, five words Title Case, 4/8 px grid: all held. Nothing but the six
rulings was built.

## What was built, per ruling

| Ruling | Built | Where |
|---|---|---|
| **16** Unfile reason | A right-click Unfile no longer writes: it opens `#unfile-modal` (in the one dialog registry, focus on the reason field, Esc / Cancel close it without a write). Words all from the vocabulary: title and confirm `review_labels.unfile` ("Unfile"), field `review_labels.unfile_note` ("Reason (Optional)"), Cancel `editor.cancel`. The file's name is shown under the title. Confirm sends the trimmed reason as the write's `note` (empty stays empty, as before); the button is greyed while the write is in flight and `writeStart` still stops a second identical write. Mark Missing: the wording table has **no** note for it (only `dismiss_note` for Not Requested and `unfile_note`), so it is unchanged. | `app.js` (`openUnfile`, `confirmUnfile`, `DIALOGS`), `index.html`, `pages.js` |
| **17** several files | A request answered by more than one filed file keeps its "{n} Files" row and gets one child row per file (class `row-child`, set in 16 px). A file filed under this request links `open_keys[0]` through `state.paths` (reveal, tooltip "Show in File Explorer") and its right-click is Show in File Explorer + Unfile (own `seq`, own dialog). A file that only *answers* the request (decision 146, no copy here) is a row with no link and no Unfile. The request row keeps Mark Missing if a statement answers it; it no longer offers Unfile when several files are filed. Single-file rows are unchanged. The Received count counts requests, not file rows. | `pages.js`, `shell.css` |
| **18** Folders Skipped | Each name gets `vocab.screen.misfits.reasons[misfit.code]` beside it; a code with no word (`not_a_year`) draws the name alone and logs nothing; the long sentence still goes to the error log; no path. Harness stub sends `code`; `vocab-mirror.json` carries S8b's nine words exactly. | `app.js`, `stub.js`, `vocab-mirror.json` |
| **19** | No change (the sheet moves on after a right-click write). | - |
| **20** sort failure | `syncSortNotice()` (called from `shellChanged`): when the list's `last_pass` is `ok === false`, one keyed notice "Sort Failed" (`screen.last_sort.failed`) with Retry (`runScan`) shows in the notices area at the top of the main area, on every page. Left as it is while a sort runs; cleared when `last_pass` says a sort worked (or none). The side-panel line stays. The failure is already in the list reply (`last_pass.ok`), so no engine change. If a sort fails in this session, the pass's own failure notice (existing) shows too; the two are different lines (the record's word and the event). | `shell.js` |
| **21** paused household | `pagesPaused(firm)` reads `paused === true` on `firm.returns[]`. Clients: the household's row shows the vocabulary's `screen.notices.paused` ("Two Years Open; Sorting Paused") beside the name (`row-mark`), and the household counts as Work Waiting. Overview: one row per paused household leads Work Waiting, that word as its status, opening the household. When the field is absent nothing is drawn. | `pages.js`, `shell.css`, `stub.js` (scenario `paused`) |

## The shape S6 must send (ruling 21)

`tracker/api.py` `firm`: each entry of `returns[]` of a household paused for two open years carries
`paused: true`. The field is **absent** (not `false`) otherwise; the renderer treats only `=== true` as
paused, and reads the household from any entry's `household` name. Nothing else changes in `firm`.
The stub documents this in `firm()` and pauses "Okafor Family" under `?scenario=paused`.

## For S6

- Ruling 18: `not_a_year` has no word until Jason gives one ("Bad Year" is the working word, ruling 18a);
  when S6 adds it to `_vocab()` the renderer draws it with no change.
- Ruling 16/17: the two `unfile` calls still send `note` and `seq`; nothing new on the API.
- The mirror gains `screen.misfits.reasons` only; delete the mirror with the rest at the join
  (`HARNESS_LIVE_VOCAB=1`).
- The join checklist of rebuild 1 still stands (its item 2: `received` now also offers Show in File Explorer
  on a file row; the same `JOIN_POPUPS` ids, no new one).

## Tests

- `test_shell`: the four dialogs (reason and no-error for a missing word), the link test (child rows),
  `test_unfile_from_the_menu_asks_first...`, `test_a_request_answered_by_several_files...`,
  `test_a_failed_last_sort_is_a_keyed_notice...`, `test_a_household_paused_for_two_open_years...`.
- `test_single_source`: the dialog registry (11 openers, `unfile-modal`), the unfile spec shape.
- `pilot/harness/interact.mjs`: a check for each ruling (18: reason beside each name, two `.misfit-why`; 16: box
  words, focus, Cancel writes nothing, confirm sends the note, empty note; 17: three child rows, links reveal
  their own copy, count is requests, child right-click ids; 20: on Overview, three other pages, both modes,
  side line stays, clears; 21: Overview row first, Clients marker, none when absent).
- Mutation checks (in place, restored): 15 mutations against `test_shell` + `test_single_source`; 13 killed
  at once; the two that survived (reason span drawn empty; paused rows dropped from Overview) got a
  stronger assertion (the harness counts `.misfit-why`; a source pin on `pagesOverview`) and are killed now.

Gate: see the last line of the report (3.11 then 3.13, ruff, interact, repo map).
