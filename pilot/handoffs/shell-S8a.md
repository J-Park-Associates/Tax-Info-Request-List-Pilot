# Shell S8a handoff: file names are live links (engine and window side), Title Case words (sonnet)

Branch `claude/shell-s8a-links`, from S2's clean tip `ae30aae`. The first
session's WIP (`dc57766`, `1e34e78`) was audited, not trusted; this session
finished, gated and fixed it. Last commit: the one that adds this file (its
sha is in the final message). No renderer file was touched.

## What changed, in plain English

1. **Only a file name opens File Explorer.** The engine gives every filed
   document's working copy, and every moved-by-hand copy, a key on its row and
   the path only in the openable map (`paths`). Read-only: the keys come from
   the record's own locations; no lock, no write, no document read.
   Households and returns carry **no** open key (rulings 11, 12).
2. **The window's `open-path` takes an optional second argument**, `"reveal"`,
   on the same channel (no new channel). After the same allow-list and the same
   `lstat` (a link, or a path that is not the reported kind, is refused with
   the same sentence), a reported **file** is shown with
   `shell.showItemInFolder`; a **folder** still goes to `shell.openPath`; any
   other second argument opens the default way. A page-supplied path that the
   API did not report is refused with reveal exactly as without it.
3. **Return links can be read as "{Return Name} ({Year})":** every row that
   names a return carries `year` beside its label (see keys).
4. **Words in Title Case** for every drawn engine phrase of five words or fewer
   (menu defaults in `main.js` stay word for word `api.MENU`), including
   "Needs Review" and "Could Not Sort", and the three new words.

## Exact keys the renderer uses

State (`state` reply):

- `state.index[i].open_keys`: list of strings, one per working copy of a
  **filed** row, in the order of `filed_names` (decision 94: one page filed
  under several requests). `[]` for every row that is not filed. Key text:
  `filed_copy <ledger key> <n>` (n = 0, 1, ...).
- `state.moved[i].open_key`: `moved_copy <ledger key>` for a moved-by-hand
  copy whose bytes are found; `""` when they are nowhere. (The moved row's
  index entry carries `open_keys: []`, so a file is never linked twice.)
- `state.index[i].open_key` (existing, parked rows): `review_copy <ledger key>`.
- `state.paths[key]` is the absolute path for each of those keys. The page
  passes the **path it looked up**, never draws it. Kinds: `vocab.path_kinds`
  has `review_copy` = `"file"` and `filed_copy`, `moved_copy`, `shown_copy` =
  `"reveal"` (the shell reads the word before the first space). Superseded
  by review 1's rebuild: see `shell-S8a-rebuild-1.md`.

Years and labels for return links:

- `state.household.returns[i]`: `label`, `year` (existing, confirmed).
- `list.households[h].returns[i]`: `label`, `year` (existing, confirmed).
- `list.engagements[i]`: `name` (label), `year`, `return_name` (existing).
- `firm.returns[i]`: **new** `label` and `year` (beside `path`, `household`).
- `firm.files[i]`: **new** `year`, beside `return`, for the Needs Review group
  headings. (Superseded by the merge below: `return` is the return's path.)
- No household or return row has an `open_key`; there is none to add.

Words (`vocab.screen`): `show_in_explorer` = "Show in File Explorer"
(file-name tooltip and right-click item), `navigate_client` = "Navigate to
Client", `navigate_return` = "Navigate to Return". Section names:
`vocab.screen.sections.needs_review` = "Needs Review"; `SHORT_REASONS
["unmatched"]` = "Could Not Sort". "Open Client Folder" is not renamed.

## The exact open call

```js
// preload.js (window.tracker.open); the same channel "open-path"
window.tracker.open(path)            // default program (unchanged)
window.tracker.open(path, "reveal")  // file: shown selected in File Explorer
// resolves "" on success, or one sentence (vocab.shell.not_opened etc.)
```

`path` must be a string the API reported in `paths`. A file name link calls
`open(state.paths[key], "reveal")`.

## The words and the Title Case rule

The rule is one small pure stdlib function, `title_case`, in
`tests/test_api.py`: capitalise every word except a, an, the, and, but, or,
nor, for, of, on, in, to, by, at, as, up, vs when not first or last; each part
of a hyphenated word; the word after a colon or semicolon; placeholders
(`{n}`), numbers, ALL-CAPS tokens left alone. `test_every_drawn_word_the_
vocabulary_carries_is_in_title_case` walks `api._vocab()` and every drawn
phrase of five words or fewer must pass; the branches it skips (machine
values, the standing rules' quoted headlines, sentences over five words,
fragments a sentence splices in) are listed with reasons in
`_TITLE_EXEMPT_BRANCHES`. Rule consequence to know: "with", "from", "than" are
not on Jason's small-word list, so they are capitalised ("Read From Scan
Only", "Move Schedule Here From {host}?").

- **Flag for Jason:** "Could not tell" became **"Could Not Sort"**, not his
  earlier "Could not Sort": the Title Case ruling (10) wins.
- Unchanged by ruling: the pilot terms, the client reminder letter and its
  subject, the error log, prose in docs. Docs that quote a changed button
  label were changed with it (ROADMAP, runbook, workflow, README, CLAUDE.md;
  `test_single_source` fixed to the new labels), and `pilot/wording-shell.tsv`
  "proposed" column was re-cased (rows whose verdict is error-log are
  untouched, being exempt).
- `pilot` sentence wording in status-page records (`Not Asked`, `Partly In`,
  `Could Not Use`, `Not Yet Checked`) are the preparer's labels
  (`STATUS_LABELS[...].label`); the record's own status words (`Not asked`,
  `Missing`, ...) are unchanged.

## Audit of the WIP: what was fixed here

- `test_single_source::test_documents_name_buttons_by_their_labels` and the
  runbook schedule test failed on the old-cased button names in docs and a pin;
  docs and the pin now use the Title Case labels.
- `test_view::test_not_asked_rows_fold_away...` compared the status column to
  the record word; it now compares to the label.
- Firm rows lacked `label`/`year`: added, with
  `test_every_return_row_the_pages_link_carries_its_year_beside_its_label`.
- Stale api comment that said return names open Explorer: corrected.

## Proposed SPEC edits (S6)

- 5.2/11: the right-click item "Show in File Explorer" acts on file rows only
  (`file`, `moved` popups); the folder items (Open Client Folder, Open Inbox,
  Open Working Folder) keep their names.
- 5.4/9: name the `open(path, "reveal")` option; state the shell reveals only
  reported files, opens reported folders, refuses everything else.
- 11: file link tooltip "Show in File Explorer"; return "Navigate to Return";
  household "Navigate to Client"; return links read "{Return Name} ({Year})"
  from `year` on the row; sections "Needs Review"; short reason "Could Not Sort".
- 9.2: `firm.returns[i]` gains `label`, `year`; `firm.files[i]` gains `year`.
- Add the Title Case rule to the wording rules with its exceptions.
- Decision rows: file-name-only Explorer link; reveal as an argument, not a
  channel; the "Could Not Sort" spelling.

## Renderer and pilot literals left for S5 and S6 (I could not change them)

- `app/renderer/index.html`: "Look again" (notice button, line ~121; the API's
  `NOTICE_LABELS` says "Look Again"), `<h3>Needs review</h3>` (~320), "Add a
  return", "New household".
- `app/renderer/app.js`: "Add a return", "Clients folder", "File it", "File
  under another return", "Look again", "Mark missing", "Needs review", "New
  household" (comments and drawn strings alike; the ones drawn should come
  from the vocabulary).
- `app/renderer/style.css`: comments only ("Needs review", "Moved by hand",
  "Set aside", "Discard my changes", "Keep editing").
- `app/renderer/pilot-content.js`: "Clients folder", "New household", the tour
  step title for Needs review, and the safeguards: "No AI reads documents",
  "Nothing is guessed", "Nothing is ever sent" (the API's `SAFEGUARDS` are now
  "No AI Reads Documents", "Originals Never Changed", "Nothing Is Guessed",
  "Nothing Is Ever Sent"; pilot terms stay as they are by ruling).
- Added after review 1 (F10), all drawn and not listed above:
  `app/renderer/app.js:316` "No content rules", `:934` "Belongs to…";
  `app/renderer/index.html:177` "Use this folder", `:190` "Clear lock", `:560`
  "Tax year", `:587` "Add a custom request", read-out names `:29-30` "Active
  engagement", `:250` "Document requests", `:645` "Rows to paste";
  `app/renderer/tour.js:101-104` callout titles "What it does", "Why it's
  safe", "Current limit" (the tour is S6's). "Add a return", "New household",
  "File it", "Mark missing" and "File under another return" are, in `app.js`,
  only in comments. Also `main.js`: "Malformed command." and "Malformed command
  arguments." (refusals to a malformed call, not drawn in normal use).
- `pages.js` does not exist on this branch (S5's): file links, the two
  navigating link kinds and "{Return Name} ({Year})" are S5's to draw.

## Tests

Each test file in its own process, Python 3.11 then 3.13 (one after the
other): test_shell, test_single_source, test_api, test_names, test_reminder,
test_reasons, test_review, test_runner, test_view, test_manifest, test_layers,
test_errors, test_tripwire, test_repo_map (last, after `update`); ruff clean.
`test_build` not run (its OCR scratch-roots test fails on the base).

Mutation checks on a scratch copy (not in the repo):
1. `SHORT_REASONS["unmatched"]` back to "Could not Sort": the Title Case and
   short-reason tests fail.
2. `open-path` with the reported-path allow-list removed and the kind
   defaulted to file: `test_reveal_of_a_path_the_api_did_not_report_is_refused`
   fails. (Removing the allow-list alone did not fail: the kind check still
   refuses an unreported path, two locks on one door.)
3. `_moved_copy_key` returning `""`: `test_a_moved_by_hand_copy_has_a_key...`
   fails.

## Merge with S1 rebuild 3

Merged origin/claude/sharp-goldberg-jmfynk (S1 rebuild 3) into this branch with
a merge commit. Conflicts and how each was resolved:

1. `tracker/api.py` `AFTER_INSTALL_HEADING`: S2's old words vs S1's "Setup
   needs attention". Title Case rules (Jason's ruling 10): it is now
   **"Setup Needs Attention"**. S1's wording test, `pilot/wording-shell.tsv`
   and `docs/runbook.md` were changed to match; SPEC-shell.md and AUDIT-shell.md
   still quote S1's lower-case spelling as history and were left alone.
2. `tracker/api.py` `_firm_row` row: kept S8a's `label`, and S1's `year`
   computed inline (same value).
3. `tracker/api.py` `firm.files[]`: S1's shape wins. `return` is the return's
   **path** (same string as `returns[].path`), plus `year`, `handle`, `name`,
   `code`, `received`, `suggestion`. S8a's `files[].return` (label) and
   `files[].path` are gone. files[] carries no label: pages join to
   `returns[]` by path to draw "{Return Name} ({Year})". The renderer
   (`app/renderer/app.js`) does not read the firm reply yet, so nothing there
   changed.
4. `tests/test_api.py`: kept both sides' tests. S8a's year/label test now
   checks that each file's `return` is one of the firm's return paths; S1's
   exact-keys test now expects `label` in the returns rows; the heading test
   expects "Setup Needs Attention".
5. `docs/repo-map.json` / `.md`: regenerated with `repo_map.py update`.

Final field names the renderer/pages use:

- `firm.returns[i]`: `path`, `household`, `label`, `year`, `counts`
  (`needs_you`, `waiting`, `received`, `set_aside`; parked, moved-by-hand and
  set-aside files counted), `files`, `oldest`, `due`, `draft`, `problem`.
- `firm.files[i]`: `return` (path), `year`, `name`, `handle`, `code`,
  `received`, `suggestion`.
- `firm.totals`: `need`, `waiting`, `complete`, `files`, `drafts`.
- `state.index[i]`: `handle`, `group`, `open_keys` (unchanged);
  `state.moved[i].open_key`; `state.paths`; `state.household.returns[i]`:
  `label`, `year`; `state.engagement.tax_year`.

Real check (scratch root, made-up names "Test Household 2025 Mixed"): the firm
row counts `{needs_you 1, waiting 1, received 1, set_aside 0}` equal the same
return's state tally; `year` 2025 in firm row, firm file and
`state.engagement.tax_year`; the parked file's `handle` `pbc/setup.exe` is the
same in `firm.files[0]` and `state.index[0]`; `open_keys` is `[]` for that
file because it has no copy on disk in the seed (the open-key tests cover the
present case); `state.paths` carries its keys.
