# Shell S8a review 1: file-name links (engine and window), Title Case words

Reviewer: a separate agent that did not build S8a (Opus 5.5, high effort).
Reviewed: `claude/shell-s8a-links` at `9279a41` - the S8a commits `dc57766`,
`1e34e78`, `f577c48`, `e2de133`, `96e04e4`, `207d831` and the merge `9279a41`
with its conflict resolutions (S1 rebuild 3's own commits were reviewed
clean elsewhere and were read only where the merge touched them). Brief:
rulings 8-13 (12 over 11 over 9 over 8; 10 over any spelling),
`shell-ledger.md`, `shell-S8a.md`, SPEC sync 3.9, 5.2, 5.4, 5.7, 9, 11.1-11.6.
No code was changed by this review.

## Gate as run

- Each test file in its own process, Python 3.11 then 3.13 (one after the
  other): test_api 393, test_names 6, test_reminder 204 (1 skipped),
  test_reasons 57, test_review 67, test_runner 193, test_view 34,
  test_manifest 102, test_layers 29, test_errors 83, test_tripwire 19,
  test_shell 29, test_single_source 171, test_repo_map 80, test_pilot_ui 10:
  all pass on both. test_build: 30 pass, 1 fails on both
  (`test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else`,
  the OCR scratch-roots test that fails on the base; ignored as briefed).
- `ruff check .` clean; `repo_map.py check` current (284 nodes).

## What was checked and holds

1. **Engine keys.** `state.index[i].open_keys` is `filed_copy <ledger key> <n>`
   per working copy, in `filed_locations` (so `filed_names`) order, `[]` for
   every row that is not `Filed` (`tracker/api.py:2056-2066`, `2815`);
   `state.moved[i].open_key` is `moved_copy <ledger key>` or `""` when the bytes
   are nowhere (`api.py:2069-2072`; confirmed with a real "nowhere" row, see
   F3); `state.paths[key]` is the absolute path (`locate`, `api.py:2877-2884`);
   `PATH_KINDS` has the three words as `"file"` (`api.py:1145`). Keys decode
   uniquely (the copy number is always the last token). Household and return
   rows carry no `open_key` in `list`, `state` or `firm`; `list.paths` carries
   only `clients_root` and `status`.
2. **Read-only, by a wrapped run.** A scratch test (copied into `tests/` only
   while it ran, then removed) made a return with a filed-then-moved copy, a
   parked zip, a parked `setup.exe` and a set-aside `.docx`, then ran `state`,
   `list` and `firm` with `builtins.open`, `io.open`, `os.open` recorded,
   `socket.socket` / `create_connection` raising, and `acquire_lock` /
   `engagement_lock` raising. Result: 0 sockets, 0 locks, 0 opens for writing;
   the only non-record file read is the tracker's own `_README.txt` in the
   inbox (by `state` and `firm`, as before S8a); no client document was
   opened. `_filed_copy_keys`, `_moved_copy_key` and `moved_to` are pure (they
   read the row, never the disk).
3. **Paths on drawn fields.** Every string of the three replies was scanned
   for a leading `/`, a drive letter, a backslash or the root, outside
   `paths`. S8a added none. What the scan finds is S1's or older and listed in
   the notes below (identity fields, and two drawn checklist sentences).
4. **Reveal in `main.js`.** Same channel, same allow-list, same `lstat`; a
   file of kind `file` goes to `showItemInFolder`, a folder to `openPath`, a
   link or a changed kind is refused with `notOpened`. `preload.js` exposes
   only the optional argument; one `ipcMain.handle("open-path"`, no new
   channel. The real `main.js` under node, with page-supplied paths
   (a scratch test on the existing harness): relative, `..`, trailing slash,
   upper-cased, `\\server\share\…`, `//server/share/…`, `__proto__`,
   `constructor`, `toString` - all refused with the not-reported sentence;
   the fallback log and a file beside it (reported under keys `__proto__ x`
   and `constructor y`) - refused (`pathKinds` resolves an object/function,
   not `"file"`, so the kind check fails closed); a symlink - refused; a
   reported folder with `"reveal"` - opened, not revealed; `["reveal"]` and
   `"REVEAL"` - the default open. Only the API's error log and the reported
   copy were revealed. See F1 for what the default open now also reaches.
5. **Words.** `title_case` implements ruling 10 as written for what it
   capitalises (small-word list, first/last, hyphen parts, after `:`/`;`,
   placeholders, numbers, ALL-CAPS). "with", "from", "than", "per" are not on
   Jason's list, so "Read From Scan Only", "Move Schedule Here From {host}?",
   "One Per Line" are right under the rule as written: agreed. "Needs Review",
   "Could Not Sort" (flagged to Jason), "Setup Needs Attention", "Show in File
   Explorer", "Navigate to Client", "Navigate to Return" present; "Open Client
   Folder" not renamed. `main.js`'s 44 `DEFAULT_MENU_WORDS` equal `api.MENU`
   key for key, and its seven shell sentences equal `SHELL_*` (by script). The
   docs (README, runbook, ROADMAP, CLAUDE.md, workflow) change only the casing
   of quoted labels (word diff); `wording-shell.tsv` changes only the
   `proposed` column (68 rows).
6. **Merge.** `firm.files[i]` = `return` (the return's path, one of
   `returns[].path`), `year`, `name`, `handle`, `code`, `received`,
   `suggestion`; `firm.returns[i]` has `label` and `year` beside S1's fields;
   the counts are S1 rebuild 3's. Test functions compared by script across
   the merge base, both parents and the merge: none lost in any test file;
   the two `test_single_source` tests absent are the ones S2 removed.

## Findings

**F1. Filed and moved-by-hand working copies can now be opened in their
default program, not only shown in File Explorer.**
`tracker/api.py:1145` (`"filed_copy": "file", "moved_copy": "file"`) with
`app/main.js:417-423`. Ruling 12: the file name "shows that exact working copy
in File Explorer (item selected)"; SPEC 5.7: reveal "applies to a file only".
Decision 190 (`api.py:754-812`): Open is an allow-list - "only a row carrying
one of these [codes] opens its marked copy on this machine"; `MATCHED_CODE`,
`FILED_WHOLE_CODE`, `FILE_MOVED` are on `NO_OPEN_CODES`, and only review
copies are marked for Protected View (`filer._mark_for_review`). The shell's
`openable` map is the guard against a page that asks for more than it should
("The renderer never names a path of its own, so anything else is refused").
What the code does: every filed and moved copy is registered with kind
`"file"`, so `window.tracker.open(path)` without `"reveal"` goes to
`shell.openPath`. Shown in node: a reported `moved_copy` `.xlsm` and a
reported `filed_copy` `.pdf` were both opened by `openPath` (answer `""`),
with no Protected View mark. Before S8a the shell opened no working copy at
all (`review_copy` had no kind in `PATH_KINDS`, so even the card's Open was
refused; S8a's first-word lookup rightly fixes that for review copies).
**Smallest fix:** a reveal-only kind -
`PATH_KINDS["filed_copy"] = PATH_KINDS["moved_copy"] = "reveal"` (any word
not `"file"`), and in `openChecked` treat it as a file for the `lstat` test and
refuse it (`notOpened`) unless `reveal`; plus a `test_shell` case that
`open(filed copy)` without reveal opens nothing. The review copy keeps
`"file"` (its Open is decision 190's). If the orchestrator prefers to keep
`"file"` as briefed, this needs Jason's yes, since it widens 190's Open.

**F2. Set-aside file names, and parked files that are not openable, have no
key, so they cannot be links.** `tracker/api.py:2036-2053` and `2075-2083`.
SPEC 3.9: "A **file name** (a parked, moved-by-hand, set-aside or filed file's
own name ...) shows that exact working copy in File Explorer"; ruling 8(a):
"every file name is a live link". What the code does: a `Not Requested` row
(its copy still in the review folder, `filer.py:369`) gets `open_key: ""`
and `open_keys: []`; a parked email or zip, or a parked row whose code is not
on `READ_AND_PARKED_CODES`, gets `open_key: ""` although it has a working
copy. Probe: `Mortgage Notes.docx` set aside and `letters.zip` parked both
carry no key. (A parked program has no working copy - `filed_names: []` - so
nothing to show; that is right.) The review copy key cannot simply be widened,
because it is also the Open key (decision 190). **Smallest fix,** with F1's
reveal-only kind: a `shown_copy <ledger key>` key (kind `"reveal"`) on every
`Needs Review` / `Not Requested` row with a `prepared_location`, beside the
unchanged `open_key`; a test for a set-aside and a zip row. If the scope is
meant to be "filed and moved only" (ruling 12's "What S6 does" column), SPEC
3.9 must drop "set-aside" and say which parked names are plain text.

**F3. `test_a_moved_copy_whose_bytes_are_nowhere_has_no_key` is vacuous.**
`tests/test_api.py:8487-8495`. It deletes a filed copy and scans; that makes
no moved row, so `state["moved"]` is `[]` and the loop asserts nothing
(adding `assert payload["state"]["moved"]` fails it). The `""` branch of
`_moved_copy_key` is therefore untested. **Fix:** build the row with
`a_moved_row(...)`, then `target.unlink()` and scan again: that gives a moved
row with `now: None` (checked), and assert `[moved] = state["moved"]`,
`moved["open_key"] == ""` and no `moved_copy` key in `state["paths"]`.

**F4. The allow-list lock of `open-path` is not pinned by any behaviour
test.** `tests/test_shell.py:564-575`. Mutation: `openable.has(p)` ->
`(openable.has(p) || true)` in `app/main.js:402` - every `test_shell` test
passes, and the `"openable.has("` text pin in `test_single_source` passes too.
The reveal test asserts only that each answer is truthy, and the kind check
refuses the same paths with a different sentence (the builder's "two locks"
note). The kind lock is pinned (`test_reveal_is_refused_when_the_file_is_no_
longer_a_file_or_is_a_link`); the allow-list is not. **Fix:** assert the exact
sentence - `ran["answers"] == ["That path is not one the tracker reported;
nothing was opened."] * 5` - which fails with the allow-list gone; and one
case for a reported key whose word has no kind (refused, opens nothing), to
pin the kind check's fail-closed default on its own.

**F5. `title_case` never lower-cases, so a capitalised small word passes.**
`tests/test_api.py:8545-8546` (a small word not first/last is appended as it
is). Ruling 10: a, an, the, ... "when not first or last" are not capitalised.
Mutation: `"Waiting on Clients"` -> `"Waiting On Clients"` - the walk passes.
No such word is in the vocabulary today (checked by script), so this is the
test's strength, not a wrong word. **Fix:** `out.append(word[:1].lower() +
word[1:])` for a non-forced small word (the ALL-CAPS and placeholder branch
still runs first), and a line in `test_the_title_case_rule_does_what_jason_
wrote`: `title_case("Waiting On Clients") == "Waiting on Clients"`.

**F6. The `filed_names` order of `open_keys` (decision 94) is not tested.**
`tests/test_api.py:8449-8470` checks one copy only. Mutation: number the keys
in reverse in `_filed_copy_keys` - the test passes. **Fix:** one case with a
page filed under two requests (an existing decision-94 fixture) asserting
`Path(state["paths"][k]).name for k in open_keys == filed_names`.

**F7. `triage.places.footer` was Title-Cased against the orchestrator's
default 5.** `tracker/api.py:1346`, `pilot/wording-shell.tsv:147`. Ledger,
"Defaults taken ... pending Jason", row 5: "`triage.places.footer` ... Stays
lower case as a fragment; listed as a Title Case exception". The code says
`"In the Page {page} Footer"`, while its siblings in the same map stay
`"in the title"`, `"on page {page}"` (the branch is exempt), so one reason
line would read "... in the title" and another "... In the Page 2 Footer".
**Fix:** `FOOTER_PLACE_WORDS = "in the page {page} footer"` and the TSV's
proposed cell to match. The same question (O5) covers `SCAN_FILED`,
`SCAN_REVIEW`, `SCAN_SYNCING`, `SCAN_NOT_SORTED` (`api.py:453-456`), which
are spliced into `SCAN_COMPLETE` ("Pass complete — Filed 3, 2 to Review."),
exempt, lower case: name them in the handoff's flags for Jason rather than
change them here.

**F8. Two drawn short phrases are exempted by whole-branch skips, unnamed.**
`tests/test_api.py:8573-8575`. The `columns` and `editor.engagement_fields`
branches are skipped whole, which hides `columns[13].label` = "Short name"
(`manifest.COL_SHORT_TITLE`, drawn as an editor column heading beside "Expected
Count") and `editor.engagement_fields[8].help` = `ACTIVE_HELP` "No: sorting
skips this return" (`api.py:1353`), the Active warning SPEC 11.2 keeps on
screen (P77); `SCHEDULE_MOVE_WARNING`, from the same 11.2 sentence, was
Title-Cased. "Short name" is the record's column name (record data, rightly
untouched, but the reason should be written); the Active warning is a drawn
phrase of five words. **Fix:** narrow the two skips to what is not drawn (`.key`, and the
`.help` lines SPEC 7 cuts from the screen), name `columns[13].label` as an
exemption with its reason, and either Title Case `ACTIVE_HELP`
("No: Sorting Skips This Return", with S1's pin at `test_api.py:8416`) or add
it to the flags for Jason.

**F9. The preload comment says reveal opens a return's folder.**
`app/preload.js:5-7`: "or opens a return's folder". Ruling 12: return names
navigate in the app; no return row carries an open key. **Fix:** "or, for a
reported folder, opens it".

**F10. The handoff's list of renderer literals left for S5/S6 is not
complete.** `pilot/handoffs/shell-S8a.md`, "Renderer and pilot literals".
Drawn and not listed: `app/renderer/app.js:316` "No content rules",
`app.js:934` "Belongs to…"; `app/renderer/index.html:177` "Use this folder",
`:190` "Clear lock", `:560` "Tax year", `:587` "Add a custom request", and the
read-out names `:29-30` "Active engagement", `:250` "Document requests", `:645`
"Rows to paste"; `app/renderer/tour.js:101-104` callout titles "What it does",
"Why it's safe", "Current limit" (tour, S6). Several items the list does name
("Add a return", "New household", "File it", "Mark missing", "File under
another return") are only in comments in `app.js`. **Fix:** add these to the
handoff list (below, so S5/S6 have it now).

## Notes for S5/S6

- **Keys are tokens, not text.** `open_keys[n]`, `moved[i].open_key` and
  `open_key` embed the row's ledger key, which is a relative location
  (`moved_copy ../../../../Clients/...`). Look them up in `state.paths` and
  never draw them, put them in a tooltip or a read-out name.
- **Which rows have a link today:** a filed row, one link per entry of
  `filed_names`, key `open_keys[n]`; a moved row, by `moved[i].open_key`
  (draw the basename of `now`, never `now` itself - it is a relative path);
  a parked row with a non-empty `open_key`. Set-aside rows, parked emails and
  zips, duplicates and opened containers have no key (F2): draw them as
  plain text until F2 is settled. An empty key means no link.
- **Call:** `window.tracker.open(state.paths[key], "reveal")`; answer `""` is
  success, anything else is one sentence for a notice (SPEC 3.9).
- **Return links:** "{Return Name} ({Year})" from `label` and `year` on
  `state.household.returns[i]`, `list.households[h].returns[i]`,
  `list.engagements[i]` (`name`, `year`) and `firm.returns[i]`; a
  `firm.files[i]` joins its heading through `return` == `firm.returns[].path`.
- **Paths that are on reply fields today (not S8a's, not to be drawn):**
  `state.view.path`, `state.reminder_card.reminder.file.path`,
  `state.household.path`, `state.household.returns[].path`,
  `list.engagements[].path` / `.household`, `list.households[].path` /
  `.client_folder` / `.inbox`, `list.root`, `vocab.shell.error_log`,
  `firm.returns[].path`, `firm.files[].return`. Two are drawn sentences:
  `state.household.checklist.lines[0-1]` ("Share the household folder,
  <absolute path>, with the client as Viewer.") - P63 says no path on screen;
  if the new household page keeps the checklist it needs the folder's name,
  not its path (an engine change for S6 to raise).
- **Renderer literals still in old casing** (F10 plus the handoff's list):
  `index.html` "Look again", `<h3>Needs review</h3>`, "Use this folder",
  "Clear lock", "Tax year", "Add a custom request", read-out names "Active
  engagement", "Document requests", "Rows to paste"; `app.js` "No content
  rules", "Belongs to…"; `tour.js` "What it does", "Why it's safe", "Current
  limit"; `pilot-content.js` tour step titles and "Clients folder", "New
  household", and the safeguard lines (the API's `SAFEGUARDS` are Title Case;
  the pilot terms themselves stay as written).
- `main.js` still says "Malformed command." and "Malformed command
  arguments." (refusals to a malformed call, not drawn in normal use); S6 may
  Title-Case them or name them as machine errors.
- `NOTHING_OUTSTANDING` (`runner.py:573`) is now "Nothing Outstanding; No
  Reminder Needed" beside the lower-case `draft_note` sentences of the run
  log ("would draft {n} item(s)"); fine on the Reminders page, mixed in the
  log. For Jason with F7's fragments question.
- The SPEC sync (11.1) names a `title_case` column of `wording-shell.tsv`;
  this branch re-cased the `proposed` column. S6 reconciles the two.
- SPEC 5.7's "in progress at this sync" paragraph can say the key names are
  final once F1-F3 are settled; add the reveal-only kind to 5.7 and 9.3 if F1
  is taken.

## Mutation checks (scratch copy, not the repo; bytecode off)

| Mutation | Test | Result |
|---|---|---|
| `if (reveal && kind === "file")` -> `if (reveal)` | `test_a_word_that_is_not_reveal_...folder_is_never_revealed` | fails (caught) |
| kind from the key's first word removed | `test_reveal_shows_a_reported_file_...` | fails (caught) |
| `SCREEN.sections.needs_review` -> "Needs review" | `test_every_drawn_word_..._title_case` | fails (caught) |
| allow-list neutered (`|| true`) | all of `test_shell` | passes (F4) |
| `open_keys` numbered in reverse | `test_a_filed_documents_working_copy_...` | passes (F6) |
| moved row always keyed | `test_a_moved_copy_whose_bytes_are_nowhere_has_no_key` | passes; the test is vacuous (F3) |
| "Waiting on Clients" -> "Waiting On Clients" | `test_every_drawn_word_..._title_case` | passes (F5) |

Ten findings: F1 and F2 change what the engine reports and the shell allows;
F3-F6 are test gaps; F7-F8 are wording; F9-F10 are a comment and the handoff.
