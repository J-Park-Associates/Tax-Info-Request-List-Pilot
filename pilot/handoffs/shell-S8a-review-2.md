# Shell S8a review 2: rebuild 1 (reveal-only copies, shown keys, words)

Reviewer: a separate agent that built neither S8a nor its rebuild (Opus 5.5,
high effort). Reviewed: `claude/shell-s8a-links` at `67fd9df` (and `7771aba`, the
ruling 14 word change pushed while this review ran), the rebuild's
diff `a1c1ee9...67fd9df` (`aa98a57`, `91f8450`, `df88204`, `67fd9df`), against
review 1's F1-F10, `shell-S8a-rebuild-1.md`, `shell-rulings.md` and
`shell-ledger.md` (branch `claude/amazing-maxwell-b4hdzo`) and SPEC sync 3.9,
5.2, 5.4, 5.7, 9.3, 11.x (branch `claude/shell-spec-sync`). No code was
changed by this review: no review-1 finding survived. The two findings below
are new.

## Gate as run

- Each test file in its own process, Python 3.11 then 3.13 (one after the
  other): test_api 397, test_names 6, test_reminder 204 (1 skipped),
  test_reasons 57, test_review 67, test_runner 193, test_view 34,
  test_manifest 102, test_layers 29, test_errors 83, test_tripwire 19,
  test_shell 32, test_single_source 171, test_repo_map 80: all pass on both.
  test_build: 30 pass, 1 fails on both
  (`test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else`,
  the OCR test that fails on the base; ignored as briefed).
- `ruff check .` clean; `repo_map.py check` current (286 nodes).

## Review 1's findings, each checked in code and by running

- **F1 holds (safety).** `PATH_KINDS` has `filed_copy`, `moved_copy`,
  `shown_copy` = `"reveal"`, `review_copy` = `"file"`
  (`tracker/api.py:1150`); `openChecked` lstats a `"reveal"` path as a file
  and refuses it unless the call asked to reveal (`app/main.js:417-427`). A
  scratch test on the real `main.js` under node (the existing harness,
  `vocab.path_kinds` taken from `api._vocab()`): reported moved copies
  `.xlsm`, `.exe`, `.bat`, `.lnk`, `.html`, `.pdf`, a filed copy and a shown
  copy - every plain open refused ("Not Opened; It Has Changed"), and so are
  `["reveal"]`, `"REVEAL"`, `"reveal "`, `null`, `1` as the second
  argument; each shown with `"reveal"` (8 of 8 via `showItemInFolder`,
  `openPath` never called). Refused both ways: a reported symlink, a reported
  folder under `moved_copy`, keys whose word is `__proto__`, `constructor`,
  or an unknown word. Refused as not reported (16 of 16): an unreported file,
  `\\server\share\x.pdf`, `//server/share/x.pdf`, a `..` spelling of a
  reported path, the strings `__proto__` / `constructor`, an upper-cased and
  a trailing-slash spelling. The fallback log is untouched
  (`openErrorLog` -> `openChecked(target, "file")`, not reachable from the
  page). A marked review copy still opens - **but see finding 1**: on a real
  engine reply it no longer does.
- **F2 holds.** `shown_key` (`_shown_copy_key`, `api.py:2090`) on every
  Needs Review / Not Requested row with a `prepared_location`; real run: a
  set-aside `.bmp`, a parked zip, a parked `.eml` and a parked read PDF carry
  `shown_copy ...`; `setup.exe` (no copy) carries `""`; filed rows carry no
  `shown_key`. Read-only, by a wrapped run of `state`, `list`, `firm`
  (`builtins.open`, `io.open`, `os.open` recorded; `socket.socket`,
  `create_connection`, `locking.acquire_lock`, `api.engagement_lock`
  raising): 0 writes, 0 sockets, 0 locks; the only file under the inbox or
  Prepared read is the tracker's own `_README.txt`, as before. Every string
  of the three replies outside `paths` scanned for `/`, the root or `\`: no
  key and no field S8a or its rebuild added carries a path; what the scan
  finds is the pre-existing list in review 1's notes (identity paths, the
  two checklist sentences, `shell.error_log`, `example_root`).
- **F3 holds.** The test builds a real moved row, unlinks it, rescans and
  asserts `now is None`, `open_key == ""`, no `moved_copy` in `paths`
  (mutation "always keyed": caught).
- **F4 holds.** The exact not-reported sentence five times and once before
  any report; a separate test for a reported key with no kind. Each lock
  neutered on a scratch copy: allow-list `|| true` - caught; kind check
  fail-open (`: info.isFile()` for an unknown kind) - caught.
- **F5 holds.** The test's `title_case` lower-cases a non-first, non-last
  small word; `"Waiting On Clients"` -> `"Waiting on Clients"` asserted;
  mutation (no lower-casing) caught; a drawn word mutated to
  "Show In File Explorer" caught by the walk.
- **F6 holds.** Decision-94 fixture, two copies: keys end `0`, `1`, names
  equal `filed_names` (mutation "numbered in reverse": caught).
- **F7 holds.** `FOOTER_PLACE_WORDS = "in the page {page} footer"`, TSV
  matches; the four `triage.places` and the `scan.complete` / `filed` /
  `review` / `syncing` pieces are exact `(path, text)` exceptions, each with
  a reason (mutation: footer Title-Cased - caught, as not the exempt string).
- **F8 holds.** `columns`, `editor.engagement_fields`, `triage.places`,
  `scan.complete` are no longer branch skips; `ACTIVE_HELP` is
  "No: Sorting Skips This Return", not exempt, pinned (mutation back to lower
  case: caught). The branches still skipped whole were each checked for a
  2-5 word phrase that is not Title Case: only record values, folder names,
  the standing-rule headlines, stored override reasons and spliced fragments
  (`origin_*`, `expected_pattern`, `unknown_year_label`,
  `people.outcomes.other`, `not_asked_label` "Not asked", the record's
  status word) - none is a free-standing drawn phrase.
- **F9 holds.** `preload.js`: "or, for a reported folder, opens it".
- **F10 holds** for every item F10 named (`shell-S8a.md`, the "Added after
  review 1" paragraph). A script over `app/renderer/*.{html,js}` found no
  other old-cased drawn literal in `index.html`, `app.js` or `tour.js`. Not
  in the handoff by name: `pilot-content.js`'s tour step titles and stages
  beyond the Needs Review one (see Notes); they were in review 1's notes,
  not in F10.

**The extra item (notice words).** `SCREEN["notices"]` has `reader` "Install
Folder Name Too Long" (5), `machine` "Machine Needs Attention" (3),
`renamed` "Folder Renamed" (2), `paused` "Two Years Open; Sorting Paused"
(5), `feed` "Feed Return Not Found" (4; since `7771aba` "Prior Year Data Not
Found", 5) beside `drive`: Title Case, five words
or fewer, no path; `wording-shell.tsv` rows `screen.notices.*` with verdict
`reword`, word counts right, the three proposals marked PROPOSED in the note.
Consumers unaffected: `main.js` reads no `screen.notices`; the renderer reads
the separate `vocab.notices` (`app.js:187, 207`); `pages.js` is not on this
branch. **But see finding 2** (Jason ruled on two of them after the rebuild).

**The reused sentence.** A plain open of a reveal-only copy answers
"Not Opened; It Has Changed". On its own this is a note, not a finding: a
correct page never asks (it calls `open(path, "reveal")` for a file name), so
the sentence is reached only by a page bug. It does become misleading through
finding 1, where the card's Open of an unchanged review copy says it.

**Nothing else changed.** The rebuild touched only what its handoff names:
`PATH_KINDS`, the notices, `FOOTER_PLACE_WORDS`, `ACTIVE_HELP`,
`_shown_copy_key` / `_review_payload` / `_state` in `api.py`; `openChecked` in
`main.js`; the preload comment; tests; TSV; handoffs; the map. No extras. The
merge from S1 rebuild 3 still holds (real run): `firm.files[i]` has `return`
(a path equal to one of `firm.returns[].path`), `year`, `handle`, `code`,
`name`, `received`, `suggestion`; `firm.returns[i]` has `label` and `year`.

## Findings

**1. A parked read document's Open is now refused: its path is reported
twice, and the reveal-only kind overwrites the review copy's.**
`tracker/api.py:2900-2905` with `app/main.js:231-237`. `_state` names the
same copy under `review_copy <row>` (kind `file`) and, since F2, under
`shown_copy <row>` (kind `reveal`) - `_shown_copy_key` covers every Needs
Review row with a copy, including the ones `_review_copy_key` opens. The
shell's allow-list is a `Map` keyed by **path**, so the second
`openable.set(path, ...)` wins, and the dict puts the `shown_copy` entries
after the `review_copy` ones. Shown end to end: a real scan of an unmatched
text PDF gives a row with both keys pointing at one path; that reply's
`paths` (in its JSON order) fed to the real `main.js`: `open(path)` ->
"Not Opened; It Has Changed", `openPath` never called; `open(path,
"reveal")` -> shown. So the card's Open (decision 190) fails for every parked
document that has one, and tells the person the file changed when it did
not. It fails safe (nothing unmarked opens), but it is a regression against
the rebuild's own claim "a review copy still opens": its shell test uses a
review copy and a shown copy at two different files, and the F2 engine test
has no parked read document (its comment "a parked one keeps its open key
too" asserts nothing). **Smallest fix:** in `_shown_copy_key`, return the
review copy's own key where the row has one -
`return _review_copy_key(entry) or f"shown_copy {ledger_key(entry)}"` - so
a path is never named under two kinds (`review_copy` is `file`, and
`open(path, "reveal")` already shows a `file`). Tests: in the F2 engine test
add an unmatched text PDF and assert its `shown_key == open_key`; an
invariant test that no path in `state.paths` appears under two keys of
different kinds; and a `test_shell` case feeding a real `state.paths` with a
parked document through `main.js` (plain open opens it, reveal shows it).

**2. Ruling 14 is applied in the word but not in the record of it.**
Jason's ruling 14 (`shell-rulings.md`, commit `8643efe`, 23:51, five minutes
after the rebuild's last commit): "Two Years Open; Sorting Paused"
**approved**; the feed notice reads **"Prior Year Data Not Found"**. While
this review ran, `7771aba` (pushed to the branch by another session) changed
the word in `api.py:1330`, its test and the TSV's `proposed` cell - checked:
Title Case, five words, the notices and Title Case tests pass on 3.11 and
3.13. What it left: `pilot/wording-shell.tsv:218` still counts **4** words
(it is 5) and both the `feed` and `paused` rows' notes still say "PROPOSED
for Jason (SPEC names no words)"; the comment at `tracker/api.py:1324-1325`
still says `paused` and `feed` are PROPOSED; `shell-S8a-rebuild-1.md`'s table
still marks both **PROPOSED**. A reader of the TSV or the handoff would put
two settled words back in front of Jason. **Fix:** TSV `feed` words `5`, note
"Jason, ruling 14 (changed from the proposed Feed Return Not Found)";
`paused` note "Approved by Jason (ruling 14)"; the `api.py` comment names only
`machine` as proposed; the handoff table's status column to match. `machine`
stays PROPOSED (still awaiting his answer, as is "Could Not Be Read").

## Notes for S5/S6

- **Which key a file name uses** (after finding 1's fix): a filed row, one
  link per `filed_names[n]`, key `open_keys[n]`; a moved row, key
  `moved[i].open_key` (draw the basename of `now`, never `now`); a parked or
  set-aside row, key `shown_key`. An empty key means plain text (a parked
  program). Call `window.tracker.open(state.paths[key], "reveal")`; the
  card's Open button alone uses `open_key` with a plain `open`. Keys embed the
  ledger key (a relative location): never draw them or put them in a tooltip.
- **Firm-wide lists have no keys.** `firm.files[i]` carries `handle` and
  `return` but `firm` has no `paths`, so a file name on the firm-wide Needs
  Review page cannot be a File Explorer link from the `firm` reply alone
  (SPEC 3.9 says every file name is one). Either the page draws it as a link
  only once it holds that return's `state`, or the engine adds the keys and a
  `paths` map to `firm`: S5 raises it; it is not S8a's by SPEC 5.7, which
  puts the keys on `state`.
- `main.js`'s allow-list keeps the last kind reported for a path and never
  forgets a path. Today every other collision is safe (a moved copy dragged
  onto a review copy's name comes after it and is `reveal`); an engine change
  that reorders `state.paths` or reports one path under two kinds should
  keep finding 1's invariant test green.
- **Renderer and pilot literals still in old casing:** the handoff's list,
  plus `pilot-content.js` tour step titles and stages - "Set up", "Drop in",
  "One clients folder", "Household and request list", "Originals, untouched",
  "Organized working copies", "Status page", "Drafted reminder", "What to
  expect" - which are drawn on the tour card and are not in
  `wording-shell.tsv` at all (S6's; the pilot terms, lines 8-71, stay as
  written). The wrap-up strengths and limits are cut by the TSV.
- SPEC 5.7 (and 9.3) still says `PATH_KINDS` names each key's kind (`file`);
  S6 adds the `reveal` kind, `shown_copy` / `shown_key`, and the refusal of a
  plain open of a reveal-only path. The "in progress at this sync" paragraph
  can say the key names are final once finding 1 is fixed and reviewed.
- "Not Opened; It Has Changed" for a plain open of a reveal-only copy is a
  fair shell sentence while only a page bug reaches it; if S5 finds a real
  path to it, a sentence of its own ("Shown, Not Opened"-style) is cheap.

## Mutation checks (scratch copy of the tree, not the repo; bytecode off)

| Mutation | Test | Result |
|---|---|---|
| allow-list neutered (`openable.has(p) \|\| true`) | `test_reveal_of_a_path_the_api_did_not_report_is_refused` | caught |
| kind check fails open (unknown kind lstat'd as a file) | `test_a_reported_key_whose_word_has_no_kind_...` | caught |
| reveal-only refusal removed | `test_a_moved_workbook_...` and the whole `test_shell` | caught |
| `moved_copy` back to `"file"` | `test_a_moved_by_hand_copy_has_a_key_...` | caught |
| `filed_copy` back to `"file"` | `test_a_filed_documents_working_copy_...` | caught |
| `_shown_copy_key` always `""` | `test_a_set_aside_file_a_parked_zip_...` | caught |
| shown key without the copy check | same | caught |
| moved row always keyed | `test_a_moved_copy_whose_bytes_are_nowhere_has_no_key` | caught |
| `open_keys` numbered in reverse | `test_a_page_filed_under_two_requests_...` | caught |
| `title_case` not lower-casing | `test_the_title_case_rule_does_what_jason_wrote` | caught |
| "Show In File Explorer" | `test_every_drawn_word_..._title_case` | caught |
| `ACTIVE_HELP` lower-cased | same | caught |
| footer fragment Title-Cased | the title tests | caught |
| a notice lower-cased ("Folder renamed") | `test_the_notices_carry_a_short_word_...` | caught |
| (not a mutation) real `state.paths` of a parked PDF through `main.js` | - | Open refused: finding 1 |

Two findings: 1 is a regression of decision 190's Open introduced by the F2
fix (fails safe, misleading sentence); 2 is the bookkeeping ruling 14 still
needs (the word itself is in, `7771aba`).
