# Shell S6b - the second half of the join

Session: S6b joiner (sonnet), 2026-09-30. **Branch: `claude/shell-join`** (S6a tip `2bc948f`).
Merge commit for `claude/shell-s5-sheet` (tip `30ba8cf`); nothing rebased, nothing force-pushed.
After this the branch holds every shell job (S1-S5, S7, S8a, S8b, spec-sync).

## The merge and how each conflict was resolved

| File | Resolution |
|---|---|
| `docs/repo-map.json`, `docs/repo-map.md` | took this side, regenerated with `tools/repo_map.py update` at the end |
| `pilot/SPEC-shell.md` (7 hunks) | took the join's text in all seven: the join's is a superset (Show in File Explorer in the 5.2 and 11.3 tables, 5.7's reveal-only kinds and final key names, 9.2's `paused`, `open_key`, `paths`, 9.3, 11.4 rows for `close`, the two proposed notices, `editor.advanced`). S5's side of each hunk was the older wording of the same lines |
| `pilot/wording-shell.tsv` (2 hunks) | kept the join's file (it carries the two spec-sync columns). S5's side of both hunks was empty: the file S5 branched from had none of the rows the join added, so nothing of S5's was lost (checked: apart from `shell.no_log` the rows of S5's file and the merge base agree, and the join has the reworded `no_log`) |
| `pilot/harness/interact.mjs` | S5's `open()` (the `?mode=double` default and the `?mode=real` opt-in) with the join's `forcedColors` option |
| `tests/test_shell.py` (3 hunks) | the renderer half stays at `tests/test_shell.py` (S2's menu half is `tests/test_shell_menu.py`). Constants: the join's Floating UI table plus S5's `SHELL_FILES` and `TITLE_FREE` (with `pages.js`, `sheet.js`, `app.js`, `index.html`); the script order test has the two Floating UI scripts, then `app.js`, `tooltip.js`, `pages.js`, `sheet.js`, `shell.js`; the join's four Floating UI / tooltip tests kept; the skeleton test is S5's (the legacy box holds only the three inputs `saveRoot` reads) |
| `tests/test_single_source.py` (1 hunk) | S5's: the notice template's Retry is text and Dismiss is the icon with `screen.icons.dismiss`; the join's older "casefold" comparison is gone |

Merge checks after the commit: `test_shell` and `test_shell_menu` passed before any step below.

## Step 1: the renderer runs on the real API

- `pilot/harness/vocab-mirror.json` is deleted; `make_vocab.py` dumps `tracker.api._vocab()` every run
  and `HARNESS_LIVE_VOCAB` is gone. The live vocabulary differed from the snapshot only in
  `menu.show_in_explorer`, `screen.close` and `screen.misfits.reasons.not_a_year`.
- Two tests that read the mirror now read `api._vocab()`.
- `test_the_harness_stub_speaks_the_apis_vocabulary`: no mirror file, `make_vocab.py` output equals
  `_vocab()`, every `vocab.a.b` the stub's code reads is a key the API has, and the stub's `list` hands
  the vocabulary on unchanged. It found a real drift at once: the stub read `vocab.decisions.unfiled`,
  which the API has never had (an unfile leaves the row at `Needs Review`).
- `test_the_harness_stub_replies_have_the_shape_of_the_engines`: the real `list`, `firm` and `state` of a
  scratch tree (the sample return after a pass, plus a stray folder for a misfit) against the stub's.
  It found: `paused` was absent from the stub's `firm.returns[]` unless paused (the engine sends a
  boolean on every entry), an authoring field `rollYear` leaked into `list.households[]`, the moved row
  lacked `pbc_location` and `group`, the unfile reply lacked `reason`, `prepared_location`,
  `moved_working_copy`. All fixed in `stub.js`.
- The SPEC 14.1 vocabulary tests exist as the API-side tests (`test_every_drawn_word_the_vocabulary_carries_is_in_title_case`,
  `test_the_notices_carry_a_short_word_for_every_kind_the_pages_show`, `test_every_short_word_the_engine_adds_is_five_words_or_fewer`,
  `test_every_code_has_one_short_label_of_five_words_or_fewer`, `test_every_icon_has_a_name_and_a_tooltip`); all pass.
- `interact.mjs` on the live words: the tour's first line, the search icon's tip and the skipped-folders
  reasons are Title Case / current (Misc now has a real reason, `Bad Year` had no word in the snapshot).
  The stub's made-up misfits are now `bad_name` for Misc and one deliberately unwritten code
  (`Clients/Loose`, `unwritten_code`) so the page's draw-the-name-alone path stays covered; the shape
  test names that one code as the only allowed difference.

## Step 2: S5's words are in the API

- `editor.routing` and `editor.routing_all` (and their constants) are dropped: nothing reads them since
  S5's one Advanced switch (`test_shell` already pinned that `app.js` does not). `editor.routing_help`
  stays: the SPEC lists it as cut from the screen but `test_api` and the wording table pin it; drop with a
  ruling if wanted.
- The three info dialogs (Safeguards, About, Folders Skipped) close with `screen.close` ("Close"), not the
  dismiss icon's word (S5 review F9); `test_the_three_info_dialogs_close_with_the_apis_close_word`.
  `icons.dismiss` stays on the notice icon and the side sheet's close.
- `pick_request` / `name_requests` were already read through the API (`toastWord`); still PROPOSED for Jason.

## Step 3: Title Case

`index.html` was already cased by S5 (no `Needs review` heading is left). New
`test_every_word_index_html_types_is_in_title_case` holds its text, `aria-label`s and placeholders to the rule
(mutation: `Add a custom request` fails it). One harness comment was re-cased (the two section comments in `app.js` and `pages.js` stay
lower-case: `test_the_renderer_types_no_vocabulary_of_its_own` forbids the Title Case word even in a comment). The stub's remaining lower-case strings are made-up data (request names, the letter's own text,
the engine's long sentences kept as sent), not vocabulary.

## Step 4: the wire

Verified with the real `python -m tracker.api create | list | firm | state --engagement <path>` on a scratch
tree (settings in `TRACKER_SETTINGS_DIR`, clients root set with `set_clients_root`), and pinned by
`test_the_harness_stub_replies_have_the_shape_of_the_engines` and
`test_every_link_key_the_engine_sends_names_a_real_file_main_js_would_reveal`.

| Field | Engine (`tracker/api.py`) | `main.js` / `preload.js` | Renderer |
|---|---|---|---|
| `firm.returns[].paused` | boolean on every return (ruling 21) | - | `pages.js` `pagesPausedRows`: `one.paused === true` |
| `firm.files[].open_key` and `firm.paths` | key `shown_copy <handle>` or `review_copy <handle>` (or `""`), path in `paths` | `main.js` learns `result.paths` into `openable` with `path_kinds[word]` | `pages.js` `pagesFileLink(firm.paths, open_key)` |
| `state.index[].shown_key` / `open_keys[0]`, `moved[].open_key`, `state.paths` | parked `shown_key`, filed `open_keys`, moved `open_key`; every path a real file | same learn, from `result.state.paths` or `result.paths` | `pages.js` `linkOf(...)` per row |
| `list.vocab.path_kinds` | `PATH_KINDS`: `review_copy` = file; `filed_copy`, `moved_copy`, `shown_copy` = reveal | `main.js` `pathKinds`, checked against the same map | - |
| `list.misfits[].code` | one of the `screen.misfits.reasons` codes (registry test) | - | `app.js` `reasons[one.code]` beside the name; a code with no word draws the name alone |
| `open(path, "reveal")` | - | `preload.js` `open: (p, how) => invoke("open-path", p, how)`; `main.js` `openPath` then `openChecked`: same allow-list and `lstat`, a reveal-only kind refuses a plain open | `pages.js` `pagesRunLink` calls `openPath(path, "reveal")` (`shell.js`) |
| menu id `show_in_explorer` | `api.MENU`, `DEFAULT_MENU_WORDS` (equal, pinned) | popups `file`, `moved`, `received` (the four templates equal S5's `JOIN_POPUPS`) | `pages.js` answers it (`pagesRunLink`), offered when a row has a link |

Not done: the real CLI replies were not fed through the browser renderer (the pages need the whole
Electron `main.js`); the shape test compares keys level by level instead, and `interact.mjs` / `shoot.mjs`
run the real renderer on the stub whose shapes that test holds.

## Gate

Each test file its own process, Python 3.11 then 3.13 (`/tmp/v11`, `/tmp/v13`), all pass: `test_shell`,
`test_shell_menu`, `test_pilot_ui`, `test_tour`, `test_pilot`, `test_api`, `test_api_entry`, `test_registry`,
`test_row_columns`, `test_single_source`, `test_layers`, `test_repo_map`, `test_tripwire`, `test_errors`.
`python -m ruff check .` clean (the new tests do not import a fixture: `scratch_root` is spelled in
`test_shell.py`); `tools/repo_map.py update` then `check` current (last step). `interact.mjs`: "all
interactions pass". `shoot.mjs` ran all scenarios (exit 0); Needs Review and Folders Skipped (the Close
button, four folders, the last drawn by name alone) looked at, light and dark. Mutation checks: `paused`
removed from the stub fails the shape test; the stub reading `vocab.decisions.unfiled` fails the vocabulary
test; `Add a custom request` in `index.html` fails the Title Case test.

## Left

The comprehensive review, the merge to `main`, the Windows check (`wintest/PROMPT-shell.md`; the firm
summary speed is the number to watch), and Jason's ruling on the two proposed notice words.
