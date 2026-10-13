# Architecture audit, 2026-10-13: the evidence

Run at Jason's request ("a comprehensive, phased refactor to bring this
codebase up to production-grade standards"), read only, against `main` at
`2741665` (pull request #55). Five reviewers on Opus at high effort, one per
slice, each in its own context and none of them editing anything: A the
sorting engine, B the record and the store, C the door, the pass and the
schedule, D the Electron shell, E the guards, tests, tools and build. Each
checked `docs/ROADMAP.md` and `pilot/DECISIONS.md` before calling anything an
anti-pattern, and marks every finding **accidental**, **deliberate** or
**outgrown**. Measurements came from throwaway AST and parser scripts outside
the repository; the type-checker count came from the `mypy` binary already on
the machine, with nothing installed.

The orchestrating session re-checked the claims the plan rests on before
writing it: four guards read `tracker/*.py` without descending into
folders (test_layers.py:294, 338, 488, 750; 488 is the no-network test), while
the import allowlist test (`_tracker_trees`, 499) does descend;
`content_check._COULD_NOT_START`
is filled in the app's engine and drained only by a pass (A-7); the
admission's parameter `kind` shadows `store.kind` (B-2); the across-household
park on the re-send road passes `candidates=""` (A-3); and the page's
command-allowlist test reads `app.js` alone (D-5).

This file is the evidence. **The plan is [`SPEC-architecture.md`](SPEC-architecture.md)**,
which cites these findings by letter and number (A-1, B-2, ...). Line numbers
are as of `2741665` and drift as soon as anything lands; the names they point
at do not.


---

## Slice A: the sorting engine

*Questions put to this slice: (Q1) what distinct jobs live in filer.py and what split keeps the layer rule and the filer-scanner cycle; (Q2) is routing logic duplicated across router, filer, scanner and content_check; (Q3) what module-level caches or state exist and who owns their lifetime; (Q4) how far test_filer and test_router reach private names.*

Measured on the tree as checked out on 2026-10-13 (`python tools/repo_map.py check`: current, 302 nodes).
Fan-in and fan-out count `tracker/` modules only, load-time and call-time imports together. Type-hint share
means functions (nested ones included) whose parameters and return are all annotated. "Private reach" is how
much the module's own test file uses `_names` (imported, read as attributes, or monkeypatched).

### Module table
| Module | Lines | Top-level defs | Longest function (lines) | Fan-in | Fan-out | Own test file (lines) | Type-hint share |
|---|---|---|---|---|---|---|---|
| tracker/filer.py (L3) | 7,878 | 180 (159 fn, 120 of them private; 21 classes) | `assign_review_file` 321; `hand_over` 227; `_decide_across` 221; `_sort_all` 218; `rename_request` 209. 13 functions are over 100 lines, 29 over 50 | 8 (api, reminder, review, rollover, runner, scanner, store, view) | 21 | tests/test_filer.py (10,227; 339 tests) | 95% |
| tracker/scanner.py (L3) | 967 | 21 | `_scan_item` 215; `scan_engagement` 133; `_received_date` 37; `_answered` 30; `_host_not_counted` 28 | 3 (api, filer, runner) | 15 | tests/test_scanner.py (972) | 92% |
| tracker/router.py (L2) | 1,227 | 19 | `_decide` 398; `_multi_form` 90; `route_file` 71; `_near_miss` 45; `_names_only_its_own` 38 | 1 (filer) | 7 | tests/test_router.py (1,498; 78 tests) | 90% |
| tracker/review.py (L3) | 537 | 16 | `shortlist_for` 44; `triage` 27; `_name_said` 25; `_label_of` 23; `_reason_for` 22 | 3 (api, reminder, view) | 7 | tests/test_review.py (557) | 100% |
| tracker/content_check.py (L2) | 2,505 | 87 (74 fn, 13 classes) | `evaluate_rules` 66; `judgment_of` 53; `extract_by_ocr` 50; `self_named_forms` 46; `_extract_xlsx` 44 | 8 (after_install, api, containers, filer, names, router, runner, scanner) | 11 | tests/test_content_check.py (2,931) | 90% |
| tracker/ocr.py (L2) | 1,898 | 64 (59 fn, 5 classes) | `ReadingChild.run` 61; `_build_engine` 60; `_the_child` 56; `_kill_on_close_job` 52; `_upright_lines` 48 (classes `ReadingChild` 154, `Session` 149) | 5 (api, content_check, filer, resident, runner) | 4 | tests/test_ocr.py (1,729) | 50% |
| tracker/containers.py (L2) | 685 | 13 | `_eml_part` 44; `_msg_attachment` 39; `Opened.add` 38; `safe_name` 37; `open_bounded` 29 | 2 (api, filer) | 5 | tests/test_containers.py (1,064) | 76% |
| tracker/names.py (L2) | 296 | 10 | `propose_spellings` 36; `check_name` 36; `_said_at` 29; `_distinct` 14; `_without_a_suffix` 11 | 4 (api, content_check, filer, review) | 2 | tests/test_names.py (144) | 100% |
| tracker/validators.py (L1) | 689 | 25 | `check_file` 70; `bears_macros` 28; `_image_error` 28; `is_program` 20; `is_cloud_placeholder` 20 | 8 (api, content_check, filer, reminder, router, scaffold, scanner, store) | 8 | tests/test_validators.py (509) | 88% |

Private reach by the own test file: test_filer 24 private names / 75 references / 37 of 339 tests; test_router
1 (`_shows_its_form_number`); test_scanner 0; test_content_check 14 / 56 / 34 of 96 tests; test_ocr 20 / 69 /
35 of 71 tests; test_containers 1 (`_CHILD_OPENER`); test_validators 2; test_names 1; test_review 1.

### Findings

#### A-1. filer.py is a god module of eleven jobs (answers Q1)
- Kind: god-module
- Severity: high
- Evidence: 7,878 lines, 180 top-level definitions, 103 module-level sentence constants spread from line 350 to
  line 7576, 21 imported tracker modules. What it does, by its own section headers (lengths in lines):

  | Lines | Size | Responsibility | Public names other modules use |
  |---|---|---|---|
  | 1-554 | 554 | docstring, imports, decision words (`FILED` ... `OPENED`), sentences, `FileReport`, errors | `NEEDS_REVIEW` (6 modules), `FILED`, `FILE_MOVED`, `NOT_REQUESTED`, `DUPLICATE`, `FilingError` |
  | 555-1283 | 729 | naming, path room, byte-proved copy (`_copy_whole` 951), rename-only move (`_move_whole` 1098), Protected-View mark, `_unique_path` | `prepared_name_for`, `room_for`, `refuse_a_path_past_the_limit`, `copies_of`, `_may_carry_code` (api) |
  | 1284-1320, 1734-1871 | 175 | the index: `read_index`, `ensure`, `_record` (the one write), `_rows_changed` | `read_index` (9 modules), `ensure` (5) |
  | 1321-1556 | 236 | client README acknowledgement and its lock | `received_for`, `refresh_household_readme` |
  | 1557-1733 | 177 | stranded-temp sweep | `sweep_stranded_temps` |
  | 1872-2211 | 340 | write-ahead intents (`_op`, `_intend`, `_prove`, `_do_op`) | none (tests reach `_do_op`, `_intend`) |
  | 2212-2638 | 427 | walking the inbox, drops that cannot be read or listed | `iter_drops`, `unreachable_drops`, `unlistable_folders`, `unfinished_drops` (reminder) |
  | 2639-3244 | 606 | working-copy sweep, re-making gone copies, readers of the firm's sentence tails | `moved_to`, `both_gone`, `marked_missing` |
  | 3245-3608 | 364 | finishing an interrupted move (decision 119) | `interrupted` |
  | 3609-4840 | 1,232 | the household pass (`file_household_drops`, `_prepare_return`, `_sort_all`), then opening emails and zips | `file_household_drops` |
  | 4841-5805 | 965 | deciding a drop: name tier, across returns, file or park, `_sort_one`. **No section header**: it sits under "an email or a zip" | none |
  | 5806-7817 | 2,012 | a person's actions: assign, hand over, dismiss, unfile, mark missing, restore, rename | 15 names, all used only by `api.py` (plus `assign_review_file` by tools/learned_keywords.py) |
  | 7818-7878 | 61 | CLI | |

  Half the file (5806-7817, plus the README, sweep and index pieces) is not the sort at all; component 7's own
  row (docs/ROADMAP.md line 409) describes the file as "sort the drop folder".
- Decision rows checked: 51 (seams where the code already turned; `_SortContext`; "route_file() left long on purpose"):
  covers `_sort_one`'s arguments, not module size. 99 and 95 (layer test; filer <-> scanner cycle is deliberate):
  limit any move, do not explain the size. 100 (records moved out of the modules that write them): the precedent
  for this split. 132 (`_file_into` is the one road for the pass and the hand-over). 119 (intents are shared by
  the pass and a person's actions). 209 / P233 (CLI only where something runs it). No row decides that the
  person's actions, the README or the sweep belong in filer. Verdict: **outgrown** (component 7 grew; no decision
  holds it in one file).
- Proposed seam (in this order; each step its own decision row; filer keeps re-exporting what it gives away,
  so every `from tracker.filer import X` still works, pinned the way `tests/test_records.py::RE_EXPORTED` already
  pins decision 100's shim):
  1. `tracker/index.py`, **L1** (imports `store`, `ledger`, `records`, `reasons`, `layout` only): decision words,
     `read_index`, `ensure`, `_record` / `_rows_changed` / `_ledger_event`, the moved / both-gone / marked /
     interrupted sentence templates and their readers (`moved_to`, `both_gone`, `marked_missing`, `interrupted`,
     `_moved_part`), `holds_the_row`. About 450 lines. See A-2 for why this goes first.
  2. `tracker/copies.py`, **L2** (imports `fsio`, `layout`, `door`, `validators`, `scaffold`, `index`, `errors`,
     `reasons`, and `content_check` for the `ContentCache` type): 555-1283 plus the stranded-temp sweep 1557-1733.
     This is where "originals are never altered" is carried out: `_move_whole` is a rename and nothing else,
     `_copy_whole` proves the bytes. About 900 lines.
  3. `tracker/intents.py`, **L3**: 1872-2211 and 3245-3608 (the plan, carrying it out, and finishing it after a
     kill). About 700 lines. The pass and the person's actions both import it.
  4. `tracker/inbox.py`, **L3** (L2 is possible): 2212-2638. `tracker/readme_ack.py`, **L3**: 1321-1556.
  5. `tracker/actions.py`, **L3**: assign, dismiss, unfile, mark missing, restore, rename, the `find_*` helpers
     (5806-6263, 6689-7817). It imports `filer` at load time for `_rescan` (in-layer, allowed). `filer` must
     **not** re-export from it (that would be a load-time cycle), so `api.py` changes its imports (slice owner:
     whoever has api). `hand_over` and `hand_over_copies` stay in filer with `_file_into` and `_file_it`.

  What stays in filer.py: the household pass, opening containers, the decision (name tier, across returns,
  `_sort_one`, file or park), `hand_over`, `_rescan`, the CLI. About 3,600 lines, one job, and it remains the
  enforcer of "nothing is guessed".
  **Keeping the deliberate cycle.** `tests/test_layers.py:464-467` asserts `"scanner" in call["filer"]` and
  `"filer" in call["scanner"]`. `_rescan` stays in filer, so the first half holds. For the second half, the
  scanner keeps its seven call-time `from tracker.filer import ...` sites (scanner.py:201, 223, 266, 285, 323,
  358, 479, 811), which work because filer re-exports the index names. That keeps the pin unchanged. A2 gives the
  better option, which moves the pin.
- Behaviour risk: the four standing rules do not change, because no rule moves. The copy and the move move
  whole, and the decision code does not move at all. Pins that move: `test_repo_map.py:845` ENFORCERS
  (`rule:originals-are-never-altered` must add `tracker/copies.py`); `test_reasons.py:159-160` TAIL_READERS
  (`("filer", "moved_to")` and `("filer", "interrupted")` become `index`); `test_single_source.py:2265`
  (`_file_into` must be defined once in filer.py, with callers `_file_it` and `hand_over`, so those three stay
  together); `test_layers.py` LAYERS (add the new modules). The hidden risk is monkeypatching (A-4).
- Cost: L (five steps; step 1 is M by itself).

#### A-2. The index's vocabulary and readers sit two layers too high, so everything that reads a row imports the sorter
- Kind: tight-coupling
- Severity: high
- Evidence: `read_index` (filer.py:1287) and `ensure` (1737) use only `store`, `ledger` and `records`, which are
  all L1. `FILED`, `NEEDS_REVIEW` and the other decision words (363-384) are plain strings. Yet: review.py:82
  imports filer at load time only for `NEEDS_REVIEW`. reminder, view and rollover import filer for
  `NEEDS_REVIEW`, `read_index`, `iter_drops` and `both_gone`. store.py:3833, an L1 module, reaches up to filer
  (L3) at call time for `FILE_MOVED` and `holds_the_row`. The scanner's half of the "deliberate cycle" is not
  `_rescan`: it is eight call-time imports of `read_index`, `ensure`, `FILED`, `FILE_MOVED`, `moved_to`,
  `both_gone`, `interrupted` and `prepared_location`, all of them index reading and none of them sorting.
  router.py:1220 writes `"Needs Review"` as a literal because an L2 module cannot import the L3 constant.
- Decision rows checked: 95 and 99 (the cycle is curated as deliberate, closing at call time inside `_rescan()`).
  The reason they give (the scan reads the index this module writes, and this module asks for the scan) holds
  for filer -> scanner. It does not hold for scanner -> filer, which only reads. 100 (records apart from the
  behaviour that writes them) left the decision words behind in filer. 101 (store narrow on purpose). Verdict:
  **outgrown**.
- Proposed seam: `tracker/index.py` at L1 as in A-1 step 1. Then, as a separate decision, scanner, review,
  reminder, view, rollover and store import `index` directly. Filer's fan-in drops from 8 to 3 (api, runner,
  and actions once A-1 step 5 lands). store's call-time edge goes to an L1 module. The scanner -> filer edge
  disappears, and the cycle becomes one-way (filer -> scanner at call time). That needs
  `test_the_filer_and_scanner_cycle_closes_only_at_call_time` rewritten to "the scanner never imports the filer;
  the filer reaches the scanner only at call time". It also needs the curated `deliberate_cycle` edge,
  `test_repo_map.py:878-884` and the CLAUDE.md sentence changed, with a decision row. If the cycle must stay as
  pinned, stop after the re-export (A-1 keeps it).
- Behaviour risk: none in behaviour. The `index` names are the same objects, re-exported. Pins:
  `test_layers.py:464-467`, `test_repo_map.py:876-886`, `test_reasons.py:159-160`, and
  `test_records.py::RE_EXPORTED` (extend it to filer's re-exports of index).
- Cost: M

#### A-3. The step after routing is written twice in filer, and the two copies already differ (answers Q2)
- Kind: duplication
- Severity: medium (the code is the "nothing is guessed" rule across returns. Today's differences may be
  intended, but nothing pins that the two stay in step.)
- Evidence: `_decide_across` (filer.py:4980-5200) and `_sort_one` (5635-5803) each run the same sequence:
  `before_a_judgment`, then `read_once(questions_for(...))`, then `_not_read`, then `report.timed`, then
  `route_file(judgment=...)`, then `_by_the_name`, then the across-household park (named or unnamed, with
  `_waits_for`), then `_file_it`, with `NoRoom` caught into a park. They already differ: `_sort_one` parks the
  across-household case with `candidates=""` (5780) where `_decide_across` passes `home_routing.candidates`
  (5159, 5168). `_sort_one` has no `opened_across` check and relies on `_may_hold` upstream (docstring at
  5655-5660). The `NoRoom` sentence differs (`PATH_NO_ROOM_IN` against `str(exc)`).
  On routing across modules (Q2): **rule evaluation is not duplicated.** `content_check.evaluate_rules`
  (1300) is the one place, reached by the router through `Judgment` (`judgment_of`, 1526) and by the scanner
  through `check_content` (2213). Tier 1 is `validators.check_file`, called by both router (`_decide` loop,
  router.py:887) and scanner. The verdicts are shared through `ContentCache` keyed by
  `rules_fingerprint` (decision 107). What is repeated is the **exactly-one rule at two scopes**: the router
  applies it across one list's rows (`_decide`, router.py:792-1190), and filer applies it across the household's
  returns plus the name tier (`_decide_across`, `_by_the_name` 4922). That split is deliberate (decision 128:
  "the router knows no person"). The scanner and review decide nothing about routing: review only ranks the
  evidence that was kept (`RULE_STRENGTH`, review.py:119).
- Decision rows checked: 111 (a re-send is judged by the earlier row's decision, which is why `_sort_one` exists),
  128 (name tier), 132 / 204 (across households waits for a person), 143 (an attachment never goes across). None
  says the after-routing step should exist twice. Verdict: **accidental**.
- Proposed seam: one function in filer, `_settle(drop, original, digest, size_kb, stamp, runs, home, judgment,
  routed, *, refiled="", resent="")`, that takes the routings and returns `(run, IndexEntry)`. Both callers build
  `routed`, the re-send road with a single return, and pass it in. Give `candidates` one type, `tuple[str, ...]`
  (see A-8). Add one table-driven test that pushes the same drop through both roads and asserts the same row,
  except for the `refiled`/`resent` sentence.
- Behaviour risk: a re-sent or re-filed document across households could pick up candidates it does not carry
  today (5780). Decide that first, and say which answer was chosen in the row. The tests covering this are
  test_filer's household and re-send tests, and test_runner, which patches `filer._decide_across`
  (tests/test_runner.py).
- Cost: M

#### A-4. Splitting is expensive because of where the tests patch, more than which private names they import (answers Q4)
- Kind: tight-coupling
- Severity: medium
- Evidence: **test_router barely reaches inside** (1 private name, `_shows_its_form_number`; 0 monkeypatches of
  the router module). **test_filer does**: it imports 93 public and 24 private names. There are 75 references to
  the private ones, in 37 of its 339 tests (`_do_op` 11, `_unique_path` 9, `_request_of_copy` 8,
  `_without_moved_sentence` 5, `_review_copy_path` 4, `_a_copy_to_act_on` 4, `_intend` 4, ...). Other test files
  reach filer privates too: test_api (`_record`, `_do_op`, `_extensions_of`), test_runner (`_move_whole`,
  `_decide_across`), test_containers (`_prepare_return`, `_decide_attachment`, `_unaccounted_in_opened`),
  test_errors (`_a_copy_to_act_on`), test_records and test_review (`_CANDIDATE_SEP`). 22 test and tool files
  import `tracker.filer`. The bigger cost: **73 `monkeypatch.setattr(filer|filer_module, "...")` sites in 9 test
  files** (test_filer 46, test_api 9, test_errors 5, test_scaffold 4, test_containers 3, test_rollover 3,
  test_runner 2, test_reminder 1, test_content_check 1). About 45 of them patch a name filer **imported** from
  somewhere else: `is_cloud_placeholder` 11, `sha256_of` 8, `read_index` 5, `mark_from_internet` 5,
  `read_once` 2, `received_for` 2, `write_readme` 2, `place_problem` 2, `pid_alive` 2, `load_manifest`,
  `locate`, `acquire_lock`, `path_limit`, `limit_for`, ... A patch like that works only while the caller
  looks the name up in filer's namespace. Move `_copy_whole` to `copies.py` and `monkeypatch.setattr(filer,
  "sha256_of", ...)` stops reaching it. The test then passes or fails for the wrong reason, with no error.
  test_content_check (14 private names, 29 patch lines) and test_ocr (20 private names, 25 patch lines,
  including `_ENGINE` and `_DEVICE` set directly) carry the same cost for A-5 and A-6.
- Decision rows checked: 100 (re-exports kept so `from tracker.filer import IndexEntry` resolves; pinned by
  test_records.py:185-200). No row covers where to patch. Verdict: **accidental**.
- Proposed seam: before any move, a mechanical commit that moves each patch to the module that defines the
  function under test, and adds one guard test. The guard walks test files with `ast` and fails when a
  `monkeypatch.setattr(<module>, "<name>")` names a `<name>` that is not *defined* in `<module>` (an imported
  name). This is standard library only. It makes A-1's moves safe and also catches the problem today.
- Behaviour risk: none to the product. It costs test churn of about 73 sites. The guard would itself need a
  `test_tripwire`/`test_single_source`-style home.
- Cost: M

#### A-5. content_check is seven jobs in one L2 module
- Kind: mixed-concerns
- Severity: medium
- Evidence: 2,505 lines and fan-in 8, by its section headers: evidence decoding 241-326; keyword and form-number
  vocabulary and the rules 326-1368 (`keyword_pattern`, `form_key`, `self_named_forms`, `dominant_forms`,
  `evaluate_rules`, about 1,040 lines of pure text logic); judgment and questions 1368-1581; extraction per
  format (pdfplumber, openpyxl, text) 1581-1925; OCR call and safety stop 1709-1989; the reading child's
  parent side (`in_a_child`, `could_not_start`, `_CHILD_READER`) 1989-2210; checking 2210-2278; the
  store-backed verdict cache `ContentCache` 2278-2471 (it calls `store.connect()` and `store.cached_verdicts`);
  CLI. `names` imports it only for `PAGE_BREAK` (A-9).
- Decision rows checked: component row 4 (ROADMAP line 406: "extraction ... + rules + verdict cache", the
  original scope). 107 (`own_forms()` is "content_check's one reading"; the cache moved to the store). 150 and
  189 (the reading and the judgment run in the child; no text crosses back). Verdict: **outgrown**. The
  one-reading rule needs one *function*, not one file.
- Proposed seam: `tracker/keywords.py` (L2; imports `records`, `manifest`, `reasons`): 326-1368 plus evidence
  decoding. It is pure functions of text, testable without a file. `tracker/verdicts.py` (L2; imports `store`,
  `settings`, `records`): `ContentCache`, `CACHE_VERSION`, `RETIRED_CACHE_FILENAME`. `content_check` keeps
  extraction, judgment and checking, and re-exports the names its 8 importers use.
- Behaviour risk: "No generative AI reads a client document" is unchanged, but the ENFORCERS pin
  (`test_repo_map.py:844`: content_check and validators) must add whichever module holds extraction. Pins:
  `test_single_source.py:915-937` (openpyxl imported once, in `content_check._extract_xlsx`, so extraction
  should stay in content_check); `test_single_source.py:18, 671` (`RETIRED_CACHE_FILENAME` from content_check);
  `READER_MODULES` in test_layers; `monkeypatch.setattr("tracker.content_check._ocr_image"/"_ocr_pdf")`; and the
  cache version bump rules (decision 107).
- Cost: M

#### A-6. ocr.py holds both the OCR engine and a general process supervisor
- Kind: mixed-concerns
- Severity: medium
- Evidence: 175-1007 is the engine and page preparation (devices, `_build_engine`, deline, deskew, Sauvola, Otsu,
  `read_page`). 1008-1663 is the child process: `ReadingChild`, `_the_child`, Windows job objects through
  `ctypes`/`kernel32` (`_kill_on_close_job` 1462, `_extended_limits`, `_close_job`), per-OS memory footprint
  (`_darwin_footprint`, `_linux_footprint`, `_libproc`), `awake_clock`. 1664-1898 is `Session`,
  `reading_session` and `run_in_child`. The child runs jobs that are not OCR: the text-layer reading, the open
  test, and opening emails and zips (decision 154, `containers.open_bounded` -> `content_check.in_a_child` ->
  `ocr.run_in_child`). So "the one mechanism" is split across ocr.py (child, session) and content_check
  (`in_a_child`, outcome-to-Extraction). It has the lowest type-hint share in the slice (50%: 51 unannotated
  parameters or returns, mostly numpy/PIL images and the engine).
- Decision rows checked: 169 (the child moved to tracker/ocr.py with the job object and lifeline, one child per
  pass that keeps the engine warm). 150 and 154 (one mechanism for every parse). Verdict: **outgrown**. Keeping
  the engine warm requires that the child *imports* ocr. It does not require the supervisor to live in ocr.
- Proposed seam: `tracker/reader_child.py` (L2; imports `errors`, `locking`, `settings`, `page`, and the standard
  library): `Outcome`, `ReadingChild`, `Session`, `reading_session`, `run_in_child`, the job-object and footprint
  code, `awake_clock`, the scratch sweep, and `content_check.in_a_child` with its outcome mapping. `ocr` keeps
  the engine and image preparation. For the image types, use `TYPE_CHECKING` imports so no heavy import is added
  at load time.
- Behaviour risk: `test_layers.py:743` (the child talks over a named pipe, never a socket) and the
  `multiprocessing` allowance move with it; `tests/test_ocr.py` reaches 20 privates
  (`_ENGINE`/`_DEVICE`/`_PROCESSOR_ONLY` set directly, `_kill_on_close_job`, `_footprint`). Call sites to
  update: runner.py:2031, api.py:6795, tools/reader_bench.py. The `windows` label applies (job objects).
- Cost: M

#### A-7. Module-level state, and who owns its lifetime (answers Q3)
- Kind: global-state
- Severity: medium (one item is a real leak in the P276 resident engine; the rest is deliberate)
- Evidence, by owner:

  | State | Where | Lifetime owner |
  |---|---|---|
  | `ContentCache` (verdict cache: digest memos, verdicts, up to 8 held judgments) | instances: filer.py:3989 (one per return per pass, in `_prepare_return`), scanner.py:824 (one per scan) | caller. Saved by filer.py:3857, 4193 and scanner.py:882, 903 under the engagement lock. Store-backed (decision 107) |
  | `PdfVerdictCache` (validators.py:384, LRU 512) | filer `_SortContext` (one per return run), scanner.py:825, router.py:743 (a fresh one when the caller passes none) | caller, one run, by design (its docstring) |
  | `ocr._ENGINE`, `_DEVICE`, `_PROCESSOR_ONLY`, `_NOTES` (476-483) | `global` in 6 functions (`_engine`, `use_settings`, `processor_only`, `reset`, `read_page`) | the process, in practice the reading child. `Session.close` calls `reset()` only when `in_a_child` is false |
  | `ocr.SETTINGS` | reassigned by `use_settings` (521) | bench and suite only (docstring) |
  | `ocr._SESSION` (1835) | `reading_session()` | the outermost `with`: runner.py:2031 per pass, api.py:6795 per app command |
  | `ocr._SAID` (1557) | `_say_once` | cleared per command by resident.py:213 (`forget_said`, P276) |
  | `content_check._STOP` (1746) | set and cleared per document in `extract_by_ocr` (1928-1959) | one document, in the child |
  | `content_check._last_line` (693) | memo of the last line found, holding the whole lower-cased text | the process. In production the judging runs in the child (`READ_IN_A_CHILD`), so the text dies with the child |
  | `content_check._COULD_NOT_START` (2027) | appended in the **parent** by `could_not_start` (2100); drained only by `runner.reader_start_warning` (runner.py:928) | nobody, outside a pass |
  | `content_check._CHILD_READER`, `containers._CHILD_OPENER` | test seams handed to the child by reference | module, deliberate (150, 154) |

  The leak: in the resident app engine (P276, up to `COMMANDS_MAX = 500` commands per process), an app command
  whose reader child could not start appends the client's **file name** to `_COULD_NOT_START`. Nothing in that
  process ever drains it, because run-now runs in a process of its own, so the names pile up unsaid until the
  engine retires. resident.py clears `api._WARNINGS`, `api._ASKED` and `ocr._SAID` per command, but not this list.
- Decision rows checked: 150 (the pass says the could-not-start list once). P276 (one long-lived engine; it
  added `forget_said` for exactly this kind of state). 137/150 (`_STOP` per document). 178 (`_line_of`'s look-back
  memo). 169 (engine state per process). Verdict: `_COULD_NOT_START` is **outgrown** (it was written when every
  app command was its own process). The rest is **deliberate**.
- Proposed seam: make the could-not-start list an attribute of `ocr.Session` (the object that already owns a
  pass's or a command's reading), and have `runner.reader_start_warning` read it from the session it opened.
  The minimal alternative is to clear it in `resident._run_one_command` beside `forget_said`.
- Behaviour risk: runner's warning wording and count (test_runner) and resident tests. No standing rule is
  touched. Nothing is sent, and nothing is persisted either way.
- Cost: S

#### A-8. The decision path is the least typed part of filer
- Kind: weak-typing
- Severity: medium-low
- Evidence: filer shows 95% hinted, but every gap is in the code that decides. The `routing` parameter is
  unannotated in `_with_the_name` (4862), `_with_the_wanting_return` (5231), `_waits_for` (5254), `_the_home`
  (5269) and `_file_it` (5464). `_NameStage.kept` is `list[tuple[_ReturnRun, object]]` (4895). filer never
  imports `records.Routing`, although it handles nothing else. `_park_it(candidates)` (5573) is untyped and gets
  both a tuple (`home_routing.candidates`) and a string (`""`, 5780, 6196, 6461). It then
  `CANDIDATE_SEP.join(candidates)`, which on a non-empty string would join its characters. Write-ahead ops are
  bare `dict` (`_do_op(op: dict)` 1979, `_the_trouble`, `_refuse_a_step_*`). `rename_request(head: object)`
  (7607).
- Decision rows checked: 51 (`_SortContext` because "an argument-order slip could stay silent", the same
  motive). 119 (the op is the journal's on-disk shape). Verdict: **accidental**.
- Proposed seam: annotate with `records.Routing` and make `candidates: tuple[str, ...]`. Add a
  `typing.TypedDict` `Op` beside the `ledger.OP_KEY`/`FROM_KEY`/`TO_KEY`/`DIGEST_KEY` constants, so the shape the
  journal stores stays a plain dict. No new tool is needed. A type checker (mypy) as a dev-only gate would catch
  the tuple/str `candidates` mix, which the standard library cannot check. That is a separate item.
- Behaviour risk: none at run time.
- Cost: S

#### A-9. Three call-time cycles the docs do not declare
- Kind: tight-coupling
- Severity: low
- Evidence: CLAUDE.md and the curated map name "the one deliberate cycle, filer <-> scanner". An AST walk finds
  more two-module cycles that close at call time. In this slice: `content_check -call-> names -load->
  content_check`. names.py:57 imports content_check for `PAGE_BREAK = "\f"` (content_check.py:168) and nothing
  else, while content_check.py:1564 imports `check_name`, `read_names` at call time (the comment at 1562 admits
  the cycle). Also `filer -load-> store -call-> filer` (store.py:3833) and `scaffold -load-> validators -call->
  scaffold` (validators' CLI block, 631). Outside the slice: `registry <-> store`, `settings <-> store`.
- Decision rows checked: 128 (names imports `records` and `content_check` "for the one page-break character").
  95 (only filer <-> scanner is curated `deliberate_cycle`). Verdict: names <-> content_check **accidental**
  (for one constant). store -> filer is fixed by A-2. validators -> scaffold is a CLI-only edge and harmless.
- Proposed seam: move `PAGE_BREAK` to `records` (L1, which names already imports) or `page` (L0), and leave
  content_check re-exporting it.
- Behaviour risk: none. test_layers stays green. The curated map may want a sentence on the remaining call-time
  cycles.
- Cost: S

#### A-10. A person's refusals are typed inline, the same sentence several times
- Kind: duplication
- Severity: low
- Evidence: "is still syncing; try again when it is here" is written inline 5 times (filer.py:6063, 6390, 6926,
  7385, 7404) and also exists as `RENAME_COPY_SYNCING` (7570). "the original {..} is no longer there" is
  written at 6060 and 6387. 28 `raise FilingError(f"...")` sentences are inline, against 103 named sentence
  constants elsewhere in the file. The "here and hydrated" test `path.is_file() and not is_cloud_placeholder(path)`
  is respelled about 20 times (911, 2426, 2621-2623, 3119, 3325, 6062, 6082, 6388, 6430, 6902, 6925, 7277, 7384),
  although `_waiting_on_sync` (3316) and `holds_the_row` (7266) exist.
- Decision rows checked: 190 (codes are columns, sentences are the firm's own) and 193 (the app types no
  sentence of its own). Neither asks for inline duplicates. Verdict: **accidental**.
- Proposed seam: name the refusals (`ORIGINAL_GONE`, `ORIGINAL_SYNCING`) beside the existing ones. Add one
  `_here(path) -> bool` helper in the copies module (A-1 step 2).
- Behaviour risk: wording pins in test_filer and test_api that assert these strings. The sentences do not change.
- Cost: S

#### A-11. Two run-state objects, one mutated in place around each attachment
- Kind: global-state
- Severity: low
- Evidence: `_ReturnRun` (3626) and `_SortContext` (5284) both carry `engagement_dir`, `report` and `cache`.
  `run.cache` and `run.context.cache` are the same object, as are the two reports, and `items`/`known` are
  forwarded by properties. `_decide_attachment` (4752-4790) overwrites `run.context.container` and
  `run.context.subfolder` on **every** run of the household, then restores them in a `finally`. `_sort_all` does
  the same for `subfolder` around each drop. That is per-drop state threaded through shared mutable objects.
- Decision rows checked: 51 (`_SortContext` replaced sixteen positional arguments). 143 and 147 (container and
  subfolder must reach every row the decision writes, the intent included). Verdict: **deliberate** for the
  context, **accidental** for the duplicate fields.
- Proposed seam: a small frozen `_Arrival(container, subfolder)` passed down `_decide_across` -> `_sort_one` ->
  `_file_it`/`_park_it` instead of mutating the context. Drop the duplicated `cache`/`report` fields from
  `_ReturnRun` and keep them on the context.
- Behaviour risk: every row writer reads `context.container`/`subfolder`. The intent-recovery tests check that a
  recovered row has the same container. test_containers patches `filer._decide_attachment`.
- Cost: S-M

#### A-12. A "for one release" compatibility shim that never left
- Kind: dead-code
- Severity: low
- Evidence: filer.py:280-312 re-exports the `records` names "kept for one release" (decision 100,
  2026-09-18), including `parse_evidence  # noqa: F401` and the alias `_CANDIDATE_SEP = CANDIDATE_SEP` (456).
  Tests still import `IndexEntry` through filer (test_reminder.py:292 and 2152-2251, test_api.py:3692, 8724,
  8795). test_records.py:185-200 pins the shim, and test_review.py:35 imports the private alias.
- Decision rows checked: 100. Verdict: **outgrown** (the release has passed). It is also useful precedent for
  A-1's re-exports.
- Proposed seam: point the tests at `tracker.records`, then delete the unused re-exports and the `_CANDIDATE_SEP`
  alias. Keep the identity-pin pattern for A-1's new re-exports.
- Behaviour risk: test-only.
- Cost: S

### Looks wrong, is deliberate (leave alone)
- `router._decide` is 398 lines: "load_manifest() and route_file() are left long on purpose: each is one rule
  after another, in the order the rules apply" (decision 51; that body is now `_decide`).
- The exactly-one rule is applied twice, per list in the router and across returns plus the name in filer.
  Decision 128 says the router knows no person, and whose a document is gets asked a layer up.
- filer -> scanner at call time inside `_rescan()` is the deliberate cycle (decisions 95 and 99;
  test_layers.py:464).
- Moved / both-gone / marked / interrupted state is read back off the Reason by regexes built from the templates
  (`_moved_tail`, `as_pattern`). Decision 190 kept "the regular expressions that read the firm's own tails"
  unchanged on purpose, decision 108 set the derive-the-reader-from-the-template precedent, and
  test_reasons.py:158 TAIL_READERS lists each reader.
- `content_check._CHILD_READER` and `containers._CHILD_OPENER` are module names set after their definition. A
  patch in the parent never reaches a child that imports the module afresh (decisions 150 and 154).
- `ocr.use_settings` reassigns a global `SETTINGS`. It is for the reader bench and the suite only, and a child
  always imports `SHIPPED` (its docstring, decision 169).
- `content_check._STOP` is a per-document global, set and cleared around one OCR reading in the child
  (decisions 137 B1.2 and 150).
- `PdfVerdictCache` belongs to a run, never to the process ("nothing is shared between runs that might one day
  be concurrent", validators.py:384).
- validators sits at L1 because scaffold reads one helper from it (test_layers.py docstring).
- `_sort_one` takes a `_SortContext` and not arguments (decision 51).

### Cross-slice notes
- api.py is the only caller of the 15 person-action functions (assign, hand over, dismiss, unfile, restore,
  rename, mark missing). A-1 step 5 changes its imports, and api also imports filer's private `_may_carry_code`
  (api.py:131).
- runner.py:928 is the only reader of `content_check.readers_that_could_not_start()`. resident.py:195-213 clears
  some per-command state but not that list (A-7).
- store.py:3833 imports `filer.FILE_MOVED` and `filer.holds_the_row` at call time (L1 reaching L3). The store's
  owner should take A-2's `index` module.
- Two further call-time cycles outside this slice: `registry <-> store`, `settings <-> store`. CLAUDE.md's "the
  one deliberate cycle" sentence is stale for the package as a whole.
- Decision words are duplicated as UI labels: api.py:791, 1314, 1344, 1371 and app/main.js:960, 983 spell
  "Needs Review" and "Not Requested" separately from filer.py:364, 374 (an api/app slice question: is a label a
  second copy of the decision?).
- `NAME_CONFIRMED_NOTE` is two different sentences under one name, in filer.py:4852 and review.py:154.
- The 73 monkeypatch sites against filer's namespace (A-4) fall mostly in test_api, test_errors, test_scaffold,
  test_rollover and test_runner, which other slices own.

---

## Slice B: the record, the store and the layout

*Questions put to this slice: (Q1) what jobs live in store.py and what split is safe; (Q2) where each field rule (names, identifiers, short titles, spoofing characters, path room) is implemented; (Q3) who writes the record and the store, by one path or several; (Q4) whether settings.py mixes concerns; (Q5) whether the record types are typed dataclasses or dicts.*

Read only. Measured with throwaway AST scripts in the scratchpad (`bwork/`).
"Fan-in" = tracker modules that import it (load or call time); "fan-out" =
tracker modules it imports, written `load + call`. Type-hint share = functions
(nested included) with every parameter and the return annotated.

### Module table
| Module | Lines | Top-level defs | Longest function (lines) | Fan-in | Fan-out | Own test file (lines) | Type-hint share |
|---|---|---|---|---|---|---|---|
| store | 4,143 | 120 (111 fn, 9 cls) | `_refuse_a_malformed_line` (332) | 12 | 4 + 10 = 14 | test_store (5,692) | 98% |
| records | 2,172 | 79 (66, 13) | `date_pattern_problem` (68) | 16 | 1 + 0 | test_records (699) | 96% |
| manifest | 2,026 | 61 (53, 8) | `save_rules` (107) | 15 | 1 + 3 | test_manifest (1,564) | 92% |
| settings | 1,588 | 69 (64, 5) | `resolve_data_home` (57) | 14 | 2 + 2 | test_settings (1,352) | 92% |
| locking | 1,512 | 48 (45, 3) | `race` (81) | 15 | 0 + 2 | test_locking (1,402) | 97% |
| ledger | 1,330 | 35 (32, 3) | `apply` (62) | 12 | 1 + 3 | test_ledger (1,020) | 100% |
| layout | 1,270 | 62 (60, 2) | `place_problem` (67) | 18 | 0 | test_layout (856) | 100% |
| rollover | 1,267 | 22 (16, 6) | `roll_household` (215, ~80 of it docstring) | 1 | 7 + 8 | test_rollover (2,035) | 88% |
| registry | 1,046 | 36 (28, 8) | `households_named` (52) | 5 | 7 + 3 | test_registry (1,278) | 97% |
| templates | 835 | 14 | `issuer_row` (55) | 2 | 1 + 0 | test_templates (480) | 100% |
| scaffold | 802 | 20 (16, 4) | `write_readme` (90) | 7 | 8 + 2 | test_scaffold (1,178) | 95% |
| checkpoint | 760 | 35 (27, 8) | `connected` (28) | 3 | 0 + 2 | test_checkpoint (319) | 71% |
| fsio | 587 | 20 | `append_rotating` (48) | 15 | 0 | test_fsio (432) | 100% |
| households | 543 | 17 (15, 2) | `client_side_expected` (72) | 6 | 2 + 6 | test_households (538) | 100% |
| door | 258 | 11 (10, 1) | `through_a_link` (24) | 18 | 3 + 1 | test_door (176) | 100% |

Five longest in store: `_refuse_a_malformed_line` 332, `record` 106, `_apply` 92, `recover` 91,
`rebuild_engagement` 90. In settings: `resolve_data_home` 57, `program_drive_refusal` 44,
`root_refusal` 41, `redirect_probe` 41, `mac_floor_refusal` 37.

Module-level mutable state in the slice: store `_CONNECTION`, `_CONNECTION_PATH`, `_CHECKPOINT`,
`_CHECKPOINT_PATH`, `_CHECKPOINT_FILE`, `_REPLACED` (store.py:746-776, `global` at 761, 817, 837,
2586, 2641, 2665); settings `_HELD`, `_HOLDING` (1104-1112, `global` 1173), `_redirect_answer`
(993, `global` 999); fsio and locking `_full_sync_said` (fsio:157, locking:310); locking `_held`
dict and `_unreleased` list (273-278, mutated in `acquire_lock`, `release_lock`, `_delete_own`).
`lru_cache` in layout on `is_invisible`, `segment_problem`, `name_key`, `_parts_below_of`: all
pure string functions (P219), none reads the disk.

Tests reaching privates (a split's cost): 19 distinct `store._x` names from the suite (31 uses of
`store._engagement_row`, 21 of `store._refuse_a_malformed_line`, `_CONNECTION` from test_resident
and test_after_install, `_Cursor` from test_runner); `store.record` monkeypatched 13 times,
`store._refuse_a_malformed_line` 5; `settings.host_system` monkeypatched 25 times. The
`ADMISSION_PIN` table in tests/test_store.py:2814-3870 holds 271 entries for version 5 keyed by
qualified name (`tracker.records._width`, `tracker.layout._SPOOFING_CODES`, ...), so any move of a
function the admission reaches renames pin keys.

### Findings

#### B-1. store.py is eighteen responsibilities in one file (answers Q1)
- Kind: god-module
- Severity: high
- Evidence: tracker/store.py by line range:
  1-348 docstring (255 lines), placement constants, `SCHEMA_VERSION`/`_IN_PLACE` migrations, `ADMISSION_VERSION`;
  349-441 errors and the `_Connection`/`_Cursor` wrappers (decision 189);
  442-636 column/DDL derivation (`_AFFINITY`, `_column_types`);
  637-1106 open, set-aside/upgrade (`open` 640-705), `connect`/`close`, `store_path`, root keys
  (`key_root`, `_positional_root`, `_engagement_key`), read tokens, `held_read`;
  1107-1231 SQL<->record values; 1232-1533 queries (`documents`, `rules`, `statuses`, `households`, `last_event`...);
  1534-1685 table writers; **1686-2077 the admission (the gate that validates lines)**;
  2078-2195 `_apply` fold; 2196-2554 the write (`record`, `catch_up`, `follow_the_journal`, rewrite refusal);
  2555-2929 checkpoint proof and foreign lines; 2930-3040 verdict cache;
  **3041-3214 rebuild from the record**; 3215-3538 `check`; 3539-3609 `export`; 3610-3798 `recover`;
  3799-3902 `verify`; 3903-4143 CLI. Public surface used by other modules: 37 names
  (`connect` 37 uses, `record` 33, `store_path` 12, `rules` 9, `follow_the_journal` 9 ...).
  `verify` imports `filer`, `validators`, `registry` (all L3) at call time (3832-3835); the CLI
  imports `registry`, `page`, `door`.
- Decision rows checked: 101 (the store is one SQLite file and `tracker/store.py`: describes the
  database, not one module for every use of it); 159 (checkpoint, verify, recover added here);
  187 (admission "is the one admission" - one rule, not one file); 209 R3b (re-judging applied
  lines). No row decides that check/export/recover/verify/admission must share the file. Verdict:
  **outgrown** - the "store imports only records, ledger, locking, checkpoint" contract (test_layers:388-394)
  was written when the file was the database; it now also holds the firm-wide audit and the gate.
- Proposed seam (in this order, each its own commit, each keeping `store` as the facade that
  re-exports the moved public names the way records re-exports `IndexEntry`):
  1. `tracker/admission.py` (L1; load-time imports `ledger`, `records`, `layout`, `reasons`, all
     at or below L1): 1686-2077 plus `ADMISSION_VERSION`, `KIND_RETURN/HOUSEHOLD`, `MALFORMED_LINE`,
     `REFUSED_CHANGE`, `UNKNOWN_EVENT`, `ALSO_IN`, `StoreError` (defined there, re-exported by
     store so `except store.StoreError` is the same class). Pure function of an event dict, no DB.
  2. `tracker/store_check.py` (L1; imports `store`, `ledger`, `records`): `check`, `_check_*`,
     `_recorded_statuses`, `_recorded_learned`, `state`, `export` (3215-3609). Read-only.
  3. `tracker/verify.py` (L3; imports `store`, `filer`, `validators`, `registry` at load time):
     `verify` and the `V_*` sentences (3799-3902). Removes store's upward call-time edge to L3.
  4. Leave in store: connection/schema/migration, queries, table writers, `_apply`, `record`,
     `catch_up`, rebuild, checkpoint proof, verdict cache, recover (they share the six process
     globals and the transaction; splitting them would split the integrity proof). The CLI stays
     under `if __name__ == "__main__":` in store (the runbook runs `python -m tracker.store`) and
     calls the moved functions. Store drops to about 3,000 lines.
  Standing rules: nothing moves behaviour; the admission is what keeps "nothing is guessed" and
  "originals are never altered" true for a forged line (`layout.place_problem` confines every step).
  Moved byte for byte, those rules hold exactly as before; `record` still calls the admission
  before `ledger.append`.
- Behaviour risk: pins that move - test_layers `LAYERS` (new modules) and
  `test_the_store_imports_only_...` (exact set `{checkpoint, ledger, locking, records}` gains
  `admission`), plus the matching sentence in CLAUDE.md ("`store` imports `ledger`, `locking`,
  `records` and `checkpoint` and nothing else") - a decision row; `ADMISSION_PIN` keys renamed
  `tracker.store.* -> tracker.admission.*` and re-pinned **under version 5** (the test's own message
  allows that for a move that refuses nothing new); test_errors:411 key `("store.py",
  "_refuse_a_malformed_line")`; test_single_source:2280 `'ALSO_IN = "also_in"' in tracker["store.py"]`;
  5 `monkeypatch.setattr(store, "_refuse_a_malformed_line", ...)` only take effect if store calls the
  admission through its own module global (keep `from tracker.admission import refuse as
  _refuse_a_malformed_line` and call that name); repo map curated nodes; docs/storage.md names.
- Cost: M (steps 1-3), L if the core is ever split further.

#### B-2. The admission pin hashes code the admission never runs (name shadowing)
- Kind: tight-coupling
- Severity: high
- Evidence: tests/test_store.py:3882-3943 `admission_closure()` treats every `ast.Name` load whose
  id is in the function's globals as a callee. In `_refuse_a_malformed_line` the parameter `kind`
  and the local `statuses` shadow the module functions `store.kind` and `store.statuses`, so the
  walker follows them into `_engagement_row`, `key_root`, `engagement_path`, `_positional_root`,
  `_recorded_root_over`, `STATUS_COLUMNS` and from there into settings. The version-5 pin
  (test_store.py:3607-3870) holds 19 `tracker.settings.*` entries (`host_system`, `product_name`,
  `mac_settings_dir`, `held`, `_HOLDING`, `_read`, `clients_root` ...) and 9 store entries that
  no admission line calls (grep of store.py:1730-2061 for `kind(`, `statuses(`, `_engagement_row`,
  `key_root`: no hits).
- Decision rows checked: 209 R3b (pin the admission's closure "and every constant they read");
  the re-review's SF1 (reach into records/layout). Neither intends settings. Verdict: **accidental**.
- Proposed seam: in the walker, collect the function's own argument names and every name bound in
  its body (Store ctx, nested defs) and skip those before matching globals; or rename the
  parameter to `record_kind`. Then re-pin under version 5.
- Behaviour risk: none to the product. Today any edit to settings' Mac seam, the hold, or store's
  root keying fails `test_admission_version_changes_with_the_admission`, which trains people to
  re-pin reflexively - the opposite of what the gate is for - and makes B-1 and B-5 needlessly
  noisy.
- Cost: S

#### B-3. The same field rule is invoked at four layers, and the typed-input rules have three homes (answers Q2)
- Kind: duplication
- Severity: medium
- Evidence (each rule, every place it is implemented or invoked):
  - **Identifier**: rule `records.identifier_problem` (records:1462-1486); typed rule
    `records.typed_identifier_problem` (1516-1537); invoked in `manifest.item_from_fields`
    (manifest:1140-1144), again in `manifest.validated` (1229-1231), again inside
    `records.rule_row_fault` (2008-2011, which `validated` calls at 1276), again in the store's
    admission via `rule_row_problem` (store:1828), plus filer (rename) and templates. One editor
    save runs `identifier_problem` four times, with two different sentences.
  - **Windows file-name part** (illegal chars, spoofing, trailing dot/space, device name):
    the same four-check body is written three times - `records.identifier_problem` (1476-1486),
    `records.short_title_problem` (1554-1564, differing only in "it begins" / "it is part of"),
    and inside `layout.segment_problem` (layout:471-482, wider, its own phrases).
  - **Sanitisers of the same character set** (`layout.WINDOWS_ILLEGAL_CHARS`): `scaffold.sanitize_component`
    replaces with `-` (scaffold:199-213), `manifest.issuer_short_title` with `-` (manifest:618),
    `containers.safe_name` with `_` (containers:246), `layout.recorded_subfolder_part` with `_`
    (layout:260-283).
  - **Spoofing / invisible characters**: one implementation each (`layout.spoofing_problem`
    389-403, `layout.invisible_problem` 361-374), invoked from records (identifier, short title,
    document), manifest (`_short_title` 1069) and `segment_problem`. Not duplicated in JavaScript
    (app/renderer has no such check; the one `maxlength` is the terms sign-off, pilot.js:183).
  - **Name length**: `records.IDENTIFIER_MAX_CHARS = 80` (records:1513) is typed again rather than
    `= layout.NAME_MAX_CHARS` (layout:244), "for the same reason".
  - **Person name / spelling**: `records.person_from_json` holds the name to `text_problem`
    (records:819-823); `api._people_from_spec` holds the name again and adds the spelling rule
    (api.py:2309-2324). The typed spelling rule lives in api; the typed identifier and short-title
    rules live in records.
  - **Path room**: measurement in layout (`deepest_path_length`, `folder_need`, `path_limit`,
    layout:1129-1218); `filer.room_for` and `filer.refuse_a_path_past_the_limit` (filer:780-866,
    docstring: "Creation, the household rollover and the editor's save all refuse through this
    one"); but `api._refuse_a_changed_row_past_the_limit` (api.py:3671-3714) calls `room_for`
    directly, compares `room.need > room.limit` and omits `folder_need`, so the docstring's claim
    is false; `filer` rename has a third check (`RENAME_PATH_TOO_LONG`, filer:7759-7762).
- Decision rows checked: 187 (one value rule, the editor holds a person to the gate's bounds);
  188 (one name rule in layout); P290/P291/P301/P304 (typed vs stored is deliberate: the gate is
  narrower so an older paste does not stop a household); P305/P307 (editor room check by key).
  Verdict: the two-tier rule is **deliberate**; the four invocations per save, the three copies
  of the file-name-part body and the typed rules' three homes are **outgrown** (they grew one
  review finding at a time).
- Proposed seam: (a) one helper `layout.file_name_part_problem(text, *, begins: bool)` that
  `identifier_problem` and `short_title_problem` call (layout L0, imports nothing - fine);
  (b) move the typed people rule into records as `typed_person_problem(kind, name, spellings)` next
  to `typed_identifier_problem`, api calls it - all typed rules in one module; (c) let
  `manifest.validated` rely on `rule_row_fault` for the identifier instead of its own call at
  1229 (keep the blank and duplicate checks); (d) move the editor's room check into filer as
  `refuse_changed_rows_past_the_limit` so filer's claim is true; (e) `IDENTIFIER_MAX_CHARS =
  NAME_MAX_CHARS`.
- Behaviour risk: wording is pinned (test_records, test_manifest, test_api refusals, test_errors);
  (a) changes code in the admission closure, so re-pin `ADMISSION_PIN` under version 5 and keep
  every phrase byte-identical; (c) changes which sentence a blank-vs-bad identifier gets - keep
  the `where` prefix. Standing rule 3 (nothing is guessed) is unaffected: every refusal stays a
  refusal.
- Cost: M

#### B-4. One door into the record, but events are composed in six modules and the API writes around the domain writers (answers Q3)
- Kind: leaky-abstraction
- Severity: medium
- Evidence: **the record has one physical write path**: `ledger.append` has exactly one caller,
  `store.record` (store.py:2313), which admits every event first (2290-2296) and then applies it in
  one transaction. The store's other writes are derivations or bookkeeping: `catch_up` /
  `_catching_up` (replay), `rebuild_engagement`, `recover` (typed confirmation), `forget` (row
  delete: api:4336, households:106, manifest:1492, rollover:1039), `remember_verdicts` (cache,
  content_check:2458 only, never journalled), `acknowledge_foreign` (checkpoint, api:5918). But
  **events are built in six modules** - `ledger.new` call sites: filer 15, manifest 6, api 3,
  reminder 3, households 2, scanner 1; `store.record` call sites: filer 11, api 4, manifest 3,
  households 2, reminder 1, scanner 1. The API builds `HOUSEHOLD_CHANGED` and `RULES_CHANGED`
  itself in `_cmd_accept_folder_name` (api.py:4839-4851), bypassing `households.save_household`'s
  diff and link rule (households:150-172) and `manifest.save_rules`' `validated()`; it writes
  `SHARING_CONFIRMED` (api.py:4780) although households owns that event's meaning
  (`shared_on`, households:175-200). records.py's docstring (25-28) still says "the journal is
  written by filer, the scanner and manifest".
- Decision rows checked: 102 ("every writer calls `record` - one call per decision"); 126 (mark
  as shared); 187 (one door in: the admission); 188 R6 (accept a folder's name). None says the
  API composes events. Verdict: **accidental** (the door is deliberate and sound; the composers
  spread).
- Proposed seam: `households.mark_shared(household_dir)` and `households.accept_name(...)` /
  `manifest.accept_return_name(...)` (L1, call-time `store`), so api.py contains no `ledger.new`;
  then a guard test beside test_layers: `ledger.new(` appears only in L1-L3 domain modules.
- Behaviour risk: low; the admission still judges every line. test_api's accept-name and
  mark-shared tests pin the replies, not the call site.
- Cost: S

#### B-5. settings.py mixes seven concerns, including a process-wide memo the store depends on (answers Q4)
- Kind: mixed-concerns
- Severity: medium
- Evidence: tracker/settings.py - 1-284 docstring and ~60 wording/key constants; 285-344 errors,
  `host_system`, settings folder; **345-456 a rotating error-log `logging.Handler`**; 459-656 the
  settings file's read/write, firm name/phone, product name, schedule preference (the file I/O the
  module docstring calls "deliberately tiny"); 659-824 where the program is, drive type,
  `statfs`; 827-1096 sync-service detection, data-home resolution, the `%LOCALAPPDATA%` redirect
  probe (`_redirect_answer` global); **1099-1254 `one_reading` / `one_household` / `held` /
  `resolved` / `refuse_a_write_while_reading`, the package's per-reply memo with `_HELD` and
  `_HOLDING` globals**, used by store (`held_read`, `record`), api, registry, runner, resident,
  content_check; 1257-1279 scratch/log folders; 1282-1570 platform floors and refusals
  (`program_drive_refusal`, `root_refusal`, `mac_floor_refusal`, `set_clients_root`); 1573-1588 CLI.
- Decision rows checked: 131 (one home for the root), 186 (data home), P118 (one reading),
  P207 (one household), P215 (`held` is "the one memo whose life is a hold"), P249 (Mac seam is
  `settings.host_system`), 193's review S2 (own rotation so no `socket` import). Each concern is
  justified; none says they must share a module. Verdict: **outgrown**.
- Proposed seam: `tracker/hold.py` (L0, stdlib only): 1099-1254 moved whole, re-exported by
  settings; `tracker/errlog.py` (L0, imports `errors` at call time): 345-456. Keep `host_system`,
  `drive_type` and the refusals in settings (25 + 5 monkeypatches target `settings.host_system` /
  `settings.drive_type`, and P249 names that seam), and keep the file I/O there.
- Behaviour risk: tests patch `tracker.settings._read`, `_SETTINGS_HELD`, `_HOLDING`, `resolved`
  as strings; a moved hold must still route `_read` through the same memo key. Patches of
  `settings.held` would no longer reach callers that import from `hold` - keep callers going
  through `settings.held` for one release, or update the patches in the same commit. Also the
  ADMISSION_PIN currently lists these names (B-2): fix B-2 first.
- Cost: M

#### B-6. settings and store each ask the other where the data lives
- Kind: tight-coupling
- Severity: low
- Evidence: `settings.error_log_path` imports store at call time to read `store.store_path()`
  (settings:363-370); `store.store_path` reads `settings.data_home`, `program_folders`,
  `drive_type`, `DRIVE_FIXED` and the private `settings._inside` (store:778-806); `store_named`
  uses `settings._inside` twice more (3942). So settings (L0) depends on store (L1) to know its
  own data home, and store re-implements the data home's two checks for `ENV_STORE`.
- Decision rows checked: 186 (three homes; `store_path` "is the whole of that rule"; N4 held
  `ENV_STORE` to the data home's checks). Verdict: **accidental** placement - the rule is right,
  its home is the wrong side.
- Proposed seam: `settings.store_file()` holding `ENV_STORE` and its checks (settings already owns
  every other home); `store.store_path = settings.store_file` kept as the public name; rename
  `_inside` to public `inside`. The call-time cycle disappears.
- Behaviour risk: test_settings and test_store patch `ENV_STORE` via the environment, not names;
  low.
- Cost: S

#### B-7. The admission is one 332-line function with five closures and an event `elif` ladder
- Kind: god-module (function level)
- Severity: medium
- Evidence: store.py:1730-2061; closures `refuse`, `a_place`, `a_segment`, `a_code`, `a_row`; one
  branch per event family (rules 1847-1890, rows 1891-1906, scanned 1907-1920, moving 1921-1983 -
  recursive for `also`, release, keywords, drafts, household 2019-2054, sharing 2055-2061).
  21 direct test calls of `store._refuse_a_malformed_line`.
- Decision rows checked: 137 L4, 187, 190, 209 R3b, P170, P288-P301 (each added a branch).
  Verdict: **outgrown**.
- Proposed seam (inside `admission.py` from B-1): one function per family
  (`_admit_rules`, `_admit_row`, `_admit_scan`, `_admit_intent`, `_admit_household`, ...) selected
  by an explicit `if/elif` on the event name in the entry function - **not** a dict of functions,
  because `admission_closure()` follows names, and a dispatch table's members would escape the
  pin, letting a branch tighten without `ADMISSION_VERSION` rising.
- Behaviour risk: the version pin (B-2) re-pinned under 5; error wording byte-identical
  (test_store, test_errors). Standing rules unchanged.
- Cost: S-M

#### B-8. The journal's events and rule rows are untyped dicts (answers Q5)
- Kind: weak-typing
- Severity: medium
- Evidence: **records are plain frozen, slotted dataclasses with full hints** - all 12 in
  records.py (`IndexEntry` 17 fields, `EngagementInfo` 15, `HouseholdInfo`, `StatusUpdate`,
  `Person`, `Feed`, `Routing`, `Evidence`, ...), `RequestItem` (21 fields) in manifest, and the
  registry/rollover reports. What travels between them is `dict`: every journal event
  (`ledger.new` returns `dict`, ~100 string key constants in ledger), rule rows
  (`rule_to_json`/`rule_from_json`, `Folded.rules: dict[str, dict]`), the info/household partials,
  status payloads. Signatures with bare `dict`/`list[dict]`: store 29 of 122 functions, ledger 14
  of 34, records 17 of 80 (records also takes `object` in 26 - deliberate, those are validators of
  untrusted input). checkpoint is the lowest-hinted module (71%).
- Decision rows checked: 103/104 (rows travel as the event carries them; records'
  docstring: "deliberately duck-typed on the field names rather than on the class"); 187 (the
  record is untrusted input, so readers must accept any shape and the admission refuses).
  Verdict: dicts at the boundary **deliberate**; dicts past the admission **accidental**.
- Proposed seam: `typing.TypedDict` per event family in ledger (`RowEvent`, `ScannedEvent`,
  `RulesChangedEvent`, `MovingEvent`, ... ; stdlib, no runtime cost, ledger still imports nothing),
  used in signatures after the admission (`_apply`, `_write_*`, ledger fold helpers). Separate
  item: a dev-only type checker (mypy or pyright, not shipped, not in the lock files the app
  installs) - the standard library cannot check a TypedDict, so without one the annotations are
  documentation only.
- Behaviour risk: none at run time.
- Cost: M (L with the checker)

#### B-9. Three folds of the same keyword and status events
- Kind: duplication
- Severity: low
- Evidence: learned keywords are folded by `ledger._apply_keyword_event` (ledger:1232-1267),
  again by SQL insert/delete in `store._apply` (store:2148-2161), and a third time by
  `store._recorded_learned` (3401-3424), whose docstring says it is "`ledger._apply_keyword_event`'s
  rule applied per `identifier_key`". Statuses likewise: `ledger.apply` (by exact spelling) vs
  `store._recorded_statuses` (3382-3398, used by both `_apply` and `check`).
- Decision rows checked: 136 (the check keys a request as the store does), 138 (writer and
  check share `_recorded_statuses`); docs/storage.md "The check is the gate". The reason - ledger
  sits below records and may not import `identifier_key` - still holds. Verdict: **deliberate**,
  with a cheaper remedy available.
- Proposed seam: `ledger.replay(events, key=lambda s: s)` / `apply(state, event, key=...)`; store
  passes `records.identifier_key`; delete `_recorded_learned`, make `_recorded_statuses` a view of
  the keyed fold. Ledger still imports nothing (test_layers:372-375). The check still compares an
  independent fold with the SQL tables, so the gate keeps its meaning.
- Behaviour risk: the conftest agreement fixture (rebuild + check after every test) exercises it;
  docs/storage.md paragraphs name `_recorded_statuses` / `_recorded_learned` and must change.
- Cost: S

#### B-10. Four "is this a Mac" probes behind one claimed seam
- Kind: duplication
- Severity: low
- Evidence: `settings.host_system` (settings:295-304), `layout.on_a_mac` (layout:1082-1086),
  `fsio._on_a_mac` (148-152), `locking._on_a_mac` (301-305); likewise `full_sync` twice (fsio:160,
  locking:313). Tests patch each one separately (conftest pins `layout.on_a_mac`; 25 setattrs of
  `settings.host_system`).
- Decision rows checked: P249 ("built behind one seam, `settings.host_system()`"), P261, SPEC-mac
  R22 (the two `full_sync` copies are the layering's price; test_fsio:349 holds them identical).
  Verdict: fsio/locking copies **deliberate**; `layout.on_a_mac` beside `settings.host_system`
  **outgrown** against P249 (settings already imports layout, so `host_system` can be built on
  `layout.on_a_mac` or the reverse).
- Proposed seam: `settings.host_system` returns `"darwin"` from `layout.on_a_mac()`; one patch
  point for the two L0 seams. Leave the fsio/locking pair.
- Behaviour risk: tests that pin one and not the other would start to agree; check test_settings
  and the `a_mac` fixture.
- Cost: S

#### B-11. records.py holds shapes, value bounds, editor wording and a regex cost analyser
- Kind: mixed-concerns
- Severity: low
- Evidence: shapes and serialisation 98-1440; editor labels/help text 930-1013
  (`ENGAGEMENT_LABELS`, `ENGAGEMENT_HELP`, `RETURN_NAME_HELP`, `PEOPLE_HELP`); the value rules and
  their phrases 1444-2172 (~730 lines: bounds, `*_problem`, `rule_row_fault`, `entry_problem`);
  the Date Pattern cost analyser on the private `re._parser` (74, 1829-1977). The module
  docstring still describes "the record half"; the rules are the gate's.
- Decision rows checked: 137 L4, 187 (the value rule lives with the record so the editor and the
  gate share it), 188 (name rule moved down to layout). Verdict: **outgrown**.
- Proposed seam: `tracker/bounds.py` (L0; imports `layout` only) for 1444-2172, re-exported by
  records so every `records.text_problem` caller is unchanged.
- Behaviour risk: 113 `tracker.records.*` keys in `ADMISSION_PIN` v5 rename (re-pin under 5 after
  B-2); test_store reaches 18 records privates by qualified name in that table.
- Cost: M

#### B-12. Process-wide globals in store are six loose names
- Kind: global-state
- Severity: low
- Evidence: store.py:746-776 - `_CONNECTION`, `_CONNECTION_PATH`, `_CHECKPOINT`, `_CHECKPOINT_PATH`,
  `_CHECKPOINT_FILE`, `_REPLACED`, reassigned by `global` in six functions; `close()` must reset
  them in the right order (P214). Tests read `store._CONNECTION` (test_resident, test_after_install)
  and `store._CHECKPOINT` (test_store, test_after_install).
- Decision rows checked: store docstring "One store per process" (decision 101), P214, P215.
  Verdict: **deliberate** - one connection per process is the design.
- Proposed seam: one `_Process` dataclass instance (connection, path, checkpoint, checkpoint path,
  checkpoint file, replaced count) with a `reset()` that `close()` calls; keep `_CONNECTION` as a
  property-like accessor only if tests need it, or update the four tests.
- Behaviour risk: the close order in P214; tests that reach the names.
- Cost: S

### Looks wrong, is deliberate (leave alone)
- `ledger` and `locking` import nothing but each other; two identical `full_sync` copies - SPEC-mac R22, test_fsio:349.
- `store.record` re-reads the journal inside its transaction and applies from the stored seq, not the handed events - decision 135.
- Every `sqlite3.Error` wrapped at the connection (`_Connection`) rather than per call - decision 189.
- The store is set aside and rebuilt on an old schema; only additive NULL columns upgrade in place, listed by hand in `_IN_PLACE` - decisions 159, 190, 204, 209, P170.
- The gate (`spoofing_problem`) is narrower than the typed rule (`invisible_problem`) - P290, P291, P301.
- A stored person's spellings are not re-judged by the gate, only where typed - P304.
- `RequestItem` lives in manifest, not records - records.py docstring, decision 103/104.
- Rule rows and events travel as dicts duck-typed on field names - decisions 103, 187 (see B-8 for the part past the gate).
- `re._parser` used for the Date Pattern cost bound (no second regex engine) - decision 187; keep it under both pinned interpreters.
- `lru_cache` on `segment_problem`, `name_key`, `is_invisible`, `_parts_below_of` - pure string functions, P219.
- `settings.held` as the one memo whose life is a hold, and refusing writes inside a reading - P118, P207, P215.
- locking's `_held` / `_unreleased` process registries - decisions 159, 171.
- `door.py` at L0 importing layout, fsio and settings - decision 188 (test_layers comment).
- scaffold composes the client README and makes folders in one module - decision 130 (one composer).
- `rollover.roll_household` plans everything, takes every lock, then writes - decision 159 (all or nothing); its length is mostly the docstring.
- The verdict cache is in the store but not in the record, written outside `record` - decision 107.

### Cross-slice notes
- api.py builds and records `HOUSEHOLD_CHANGED` / `RULES_CHANGED` / `SHARING_CONFIRMED` itself (api:4780, 4839-4851) - slice owning api (see B-4).
- `api._refuse_a_changed_row_past_the_limit` (api:3671-3714) omits `layout.folder_need`, unlike `filer.refuse_a_path_past_the_limit` (filer:831-866), whose docstring says the editor's save refuses through it - filer/api slice.
- `filer` rename has its own path-length check and sentence (`RENAME_PATH_TOO_LONG`, filer:7571, 7759-7762) - filer slice.
- The people form parser and its typed rules live in api (`_people_from_spec`, api:2295-2328) - api slice (B-3 b).
- `store.verify` reaches up into `filer.holds_the_row`, `validators.is_cloud_placeholder`, `registry` at call time - moving it to L3 touches the filer slice's public surface.
- tests/test_store.py `admission_closure()` (3882-3943) is test infrastructure every slice that edits records/layout/ledger/settings will trip on (B-2).
- records.py docstring (25-28) says the journal is written by filer, scanner and manifest; it is written only through `store.record` - docs/knowledge-map owner.

---

## Slice C: the door, the pass and the schedule

*Questions put to this slice: (Q1) what jobs live in api.py and what split keeps `COMMANDS` and the layer rule; (Q2) the same for runner.py; (Q3) what state survives between commands in the long-lived engine; (Q4) whether each sentence has one home; (Q5) whether the JSON contract with the shell is written down.*

Read only. Map checked current (`python tools/repo_map.py check`: 302 nodes, exit 0). Measurements came from AST scripts in the scratchpad (`scratchpad/auditC/`). Fan-in counts the importers under `tracker/`, `tools/` and `api_entry.py`; fan-out counts the distinct `tracker.*` modules imported, at load time or call time. "Type-hint share" counts functions whose every parameter and whose return are annotated.

### Module table
| Module | Lines | Top-level defs | Longest function (lines) | Fan-in | Fan-out | Own test file (lines) | Type-hint share |
|---|---|---|---|---|---|---|---|
| tracker/api.py | 6,810 | 172 fn, 3 cls, 297 module assigns (256 str consts) | `_vocab` 459; `_state` 200; `_cmd_create` 141; `_household_payload` 108; `_firm_from_cache` 101 | 2 (api_entry, resident) | 36 | tests/test_api.py (11,751) | 91% (163/178); 76 fns return bare `dict` |
| tracker/runner.py | 3,652 | 81 fn, 5 cls, 165 assigns (137 str) | `_pass` 288; `run_household` 243; `run_registry` 128; `write_status_page` 93; `run_engagement` 92 | 5 (api, after_install, scheduling, api_entry, tools/reader_bench) | 24 | tests/test_runner.py (5,909) | 91% (87/95) |
| tracker/reminder.py | 2,260 | 55 fn, 12 cls | `draft_reminder` 130; `write_draft` 86; `_parked_holds` 86; `_compose_letter` 82; `triage` 72 | 2 (api, runner) | 16 | tests/test_reminder.py (2,468) | 96% |
| tracker/after_install.py | 1,358 | 42 fn, 3 cls | `_run` 88; `_schedule` 54; `main` 48; `_task_missing` 48; `_time_machine` 37 | 2 (api, api_entry) | 12 | tests/test_after_install.py (1,831) | 100% |
| tracker/scheduling.py | 1,045 | 44 fn, 3 cls | `task_scheduler_xml` 78; `register_here` 32; `launch_agent_plist` 29; `schedule_decision` 28; `claim` 27 | 2 (api, after_install) | 5 | tests/test_scheduling.py (906) | 100% |
| tracker/view.py | 917 | 25 fn, 2 cls | `write_view` 59; `request_row` 42; `_readers` 40; `_set_aside_block` 32; `_body` 32 | 2 (api, runner) | 10 | tests/test_view.py (993) | 96% |
| tracker/reasons.py | 895 | 2 fn, 2 cls, 87 assigns (~50 `Reason`s) | `code_of` 7 | 12 | 0 | tests/test_reasons.py (239) | 71% (5/7) |
| tracker/firm_pages.py | 712 | 27 fn, 5 cls | `name_order` 70; `_needs_review` 51; `_clients` 37; `_overview` 36; `load_view` 29 | 1 (api) | 5 | tests/test_firm_pages.py (454) | 94% |
| tracker/firm_cache.py | 425 | 17 fn, 1 cls | `_listed` 33; `fingerprints` 25; `load` 23 | 4 | 3 | tests/test_firm_cache.py (388) | 94% |
| tracker/progress.py | 371 | 12 fn, 1 cls | `_keep` 33; `say` 31; `__init__` 21 | 5 | 2 | tests/test_progress.py (236) | 100% |
| tracker/resident.py | 295 | 9 fn | `serve` 60; `_run_one_command` 22; `_request_of` 18 | 1 (api_entry, at call time) | 4 | tests/test_resident.py (506) | 100% |
| tracker/page_rows.py | 258 | 7 fn, 1 cls | `load` 36; `_entry_is_whole` 22 | 1 (runner) | 3 | tests/test_page_rows.py (362) | 100% |
| tracker/errors.py | 253 | 9 fn, 1 cls | `keep` 24; `error_class` 16; `_main` 16 | 25 | 0 | tests/test_errors.py (1,046) | 100% |
| tracker/page.py | 236 | 11 fn, 2 cls | `table` 18; `tolerant_console` 17 | 21 | 0 | tests/test_page.py (68) | 100% |
| api_entry.py | 99 | 2 fn | `run_setup_step` 18 | 0 (entry point) | 5 | tests/test_api_entry.py (240) | 100% |

How much the tests reach into private names (the cost of a split): **api**: 38 distinct `api._x` names, 176 uses in 11 files (`api._vocab` ×71, `api._state` ×31). The tests also call `monkeypatch.setattr(api, "<imported name>")` 39 times on 27 distinct names (`load_manifest`, `discover_engagements`, `scaffold_engagement`, `created_on`, `data_home`, ...). **runner**: 2 private names; 19 `setattr(runner, ...)` in test_runner. **scheduling**: 6 private names, 14 uses. Every other module in the slice: 3 or fewer.

### Findings

#### C-1. api.py is eight modules in one file, and its own docstring is no longer true
- Kind: god-module
- Severity: high
- Evidence: The docstring (api.py:4-5) says "All real logic lives in the tracker package; this module only serializes it." By line range, the file is:
  - 1-80: docstring, pinned to `COMMANDS`.
  - 82-374: 35 import statements, about 290 lines, from 36 package modules, including the private `filer._may_carry_code` (131).
  - 376-650: the envelope's words, the mutable per-command state, `_failure_of`/`say_failure`/`_root`.
  - 656-1091: 162 screen-word constants.
  - 1094-1256: request parsing (`_folder_name`, `_new_return_dir`, `_engagement_dir`, `_read_spec`).
  - 1261-1691: more words and tables (`PATH_KINDS`, `MENU`, `SCREEN`, ...).
  - 1694-2152: `_vocab()`, 459 lines with about 361 literal keys.
  - 2155-3061: spec parsing and reply shaping (`_info_from_spec`, `_people_from_spec`, `_triage_payload`, `_household_payload`, ...).
  - 3062-3101: a domain rule (`item_group`/`file_group`, see C-2).
  - 3104-3404: `_state` and its helpers.
  - 3407-5919: 38 `_cmd_*` handlers, about 2,500 lines, many holding business operations: the editor save's merge and refusals (`_cmd_edit` 3525-3609 with `_as_recorded` 3619, `_refuse_taking_away_documents` 3650 and `_refuse_a_changed_row_past_the_limit` 3674, decisions 160/131/P305/P307); the create transaction with rollback and `shutil.rmtree` (`_cmd_create` 4140-4280, `_undo_made` 4283, `_undo_create` 4317, decision 137); the cross-household record reconciliation taken under each household's lock (`_mirror_related` 4409-4454, P170, called from `_cmd_edit_household` 4457).
  - 5922-6650: the whole firm view (fresh walk, cache, paging, firm-last), about 730 lines.
  - 6653-6768: the dispatch sets and `COMMANDS`.
  - 6771-6806: `main`.

  Words and `_vocab` together are about 1,200 lines (18%).
- Decision rows checked:
  - 42: one home per fact; the vocabulary comes from the API. That is still right for *who sends* the words, not for where they live.
  - 51: seams "where the code already turned"; it keeps only `load_manifest`/`route_file` long on purpose, not api.
  - 123: `with_default_dates` was moved *out of the API into rollover* because the command line missed a rule that lived only in api. This is a precedent for this finding.
  - 104: `manifest.save_rules` got the request list's writes.
  - P66: wording-only edits to `_vocab`.

  Verdict: **outgrown**. Decision 123 shows the bug class (a rule in L5 that the CLI and the pass cannot reach) has already happened once.
- Proposed seam: use **flat sibling modules, not a `tracker/api/` package.** The guard tests read `tracker/*.py` non-recursively:
  - test_layers.py:294, 338, 488 (the "nothing is ever sent" forbidden-imports check) and 750;
  - test_single_source.py:1503, 1522, 1585, 2132 and others;
  - test_api.py:7197 (`_writers_in_the_package`, which derives `WRITING_COMMANDS`).

  A subpackage would silently escape the standing-rule check. In order of payoff:
  1. `tracker/screen_words.py`: every constant from 376-525 (not the three mutable ones), 656-1091 and 1261-1691, plus the stray ones (4305, 5317, 5654-5684, 5824-5831, 5942, 6123). Its layer is set by what it imports (`records.NO`, `settings.ERROR_LOG_FILENAME`, `manifest` labels): L1. api does `from tracker.screen_words import *`-style explicit imports, so `api.FOO_LABEL` keeps working (845 test references, 188 distinct names).
  2. `tracker/request_edit.py` (L3: imports manifest, filer, layout): `_ROW_KEYS`, `_as_recorded`, `_refuse_taking_away_documents`, `_PATH_FIELDS`, `_refuse_a_changed_row_past_the_limit`, `_refuse_a_list_nobody_is_asked_for`, `_info_from_spec`/`_people_from_spec`/`_members_from_spec`. It exposes one `save_from_editor(engagement, spec) -> SavedRules`.
  3. `tracker/household_edit.py` (L3: imports registry, households, locking, layout): `_feeds_from_spec`, `_related_from_spec`, `_mirror_related`.
  4. `tracker/creation.py` (L3/L4): the create transaction (`_new_return_dir`, `_refuse_a_taken_household_name`, `_undo_made`, `_undo_create`). It keeps decision 137's "remove only what this call made" in one place, callable from a CLI.
  5. `tracker/firm_view.py`: see C-2.

  `api.py` keeps the docstring, `COMMANDS`, `HELD_READING_COMMANDS`/`WRITING_COMMANDS`/`OWN_PROCESS_COMMANDS`, the envelope, `_vocab()`, `main` and thin `_cmd_*` handlers (parse the argv and spec, call the domain function, shape the reply). Standing rules: nothing moved touches reading, sending or the inbox originals. `_undo_create` removes only folders this call made under the private tree, and it moves with its guard (`owned`) unchanged.
- Behaviour risk:
  - The 39 `monkeypatch.setattr(api, "<name>")` calls stop intercepting once the caller moves. This fails silently, so each must be re-pointed at the new module.
  - test_api.py:10367 (`_commands_that_reach`) parses only `tracker/api.py`. It still works only while the `runner.main`/`after_install.run` calls stay in api's own handlers (they do in this plan).
  - Source-text pins that move with `_vocab`: test_single_source.py:546-547 (`'"product": product_name(),' in read("tracker/api.py")`) and test_shell.py:3815 (`'"client_type_forms": CLIENT_TYPE_FORMS,'` in api.py).
  - test_api.py:10534 pins `("api.py", "SCREEN")` as the only import-time fixed value, so it moves if `SCREEN` moves.
  - test_errors.py:399 names `("api.py", "_failure_of")`, which stays.
  - The `LAYERS` table and `tracker/__init__.py`'s module list (test_single_source.py:1581) gain each new module, each with a decision row.
  - repo-map curated nodes and the runbook mention api by name.
- Cost: L

#### C-2. The firm view's row builder and the four-group rule sit at layer 5, so the pass runs its own API as a child process
- Kind: tight-coupling
- Severity: high
- Evidence:
  - `item_group`/`file_group`/`GROUPS` (api.py:3062-3101) are pure rules over records ("one grouping rule, in Python").
  - `_firm_row` (5945-6023), `_firm_draft`, `_firm_from_cache` (6312-6412) and `_firm_fresh` (6214) decide each return's counts and draft state.
  - `runner.fill_firm_cache` (runner.py:642-692) says outright: "The rows the cache keeps are built by the API (`api._firm_from_cache`), and this module may not import it ... so the pass runs exactly what Overview runs, as its own process: `python -m tracker.api firm`". That means a 300 s subprocess, a `--product` flag threaded through the packaged task (runner.py:630-639; scheduling.py:198), and return codes turned into sentences.
  - test_runner.py:4478 pins that `follow=False` appears only in `api.py` and `runner.py`, so the practice's two read-only pages live in the top two layers.
- Decision rows checked:
  - P201: fill at the pass's end, in a child, "the runner never imports api". The only reason given is the layer rule.
  - P120: a cache never makes a status wrong, and there is no second builder. Both still hold if the builder moves down rather than being copied.
  - 99 (layers as a test).

  Verdict: **outgrown**. The child exists only because the builder sits above the runner.
- Proposed seam: `tracker/firm_view.py` at L4, beside runner. It imports reminder, review, manifest, filer and firm_cache, all L3 or lower. It takes the group rule, `_firm_row`, `_firm_draft`, `_firm_key`, `_firm_marks`, `_firm_read_households`, `_firm_fresh`, `_firm_from_cache`, `_firm_cached` and `FIRM_JUDGED`. api's `_cmd_firm`/`_cmd_firm_last` keep the paging (`firm_pages`) and the words (`_firm_words`).
  - The runner can then fill the cache in-process. Alternatively it keeps the child for isolation (closed stdio, own time limit), but by calling `tracker.firm_view` rather than the API. Either way there is one builder.
  - `item_group`/`file_group` could go lower still (L3, next to `reminder.sides`, which they already read), so `view.py` and the status page can share the grouping if they ever show it.
  - The standing rules are unchanged: the builder reads with `follow=False`, takes no lock and reads no document, and moving it changes none of that.
- Behaviour risk: P201's byte-identical replies (test_api's firm tests compare fresh and cached replies). test_runner.py:4478's file list moves to `["firm_view.py", "runner.py"]`. `api._firm_cached` is monkeypatched twice and `FIRM_READ_BATCH` twice; `api._firm_key` (5 uses) and `api._firm_words` (4) are reached by tests. The `_fixed_at_import` set is untouched.
- Cost: M

#### C-3. Per-command state is module globals, reset in two places, and the engine reaches api's private names to do it
- Kind: global-state
- Severity: medium
- Evidence:
  - `_WARNINGS: list`, `_ASKED: dict` and `_RUNNING: dict` (api.py:388-394) are the command's context. They are written from deep inside: `_warn` (534) from 9 sites, `_read_spec` does `_ASKED.update(spec)` (1216), `_failure_of` reads `_ASKED` (572-574), and `_with_list` reads `_RUNNING` (4084). The global list is also handed into another module: `refresh_household_readme(household_dir, said=_WARNINGS)` (3359).
  - They are cleared by `api.main` (6775-6777) *and* by `resident._clear_the_last_command` (resident.py:196-203: `api._WARNINGS.clear(); api._ASKED.clear()`). The resident does not reset `_RUNNING`.
  - The engine lives up to `COMMANDS_MAX = 500` commands (resident.py:101). Its retire check `_left_unlike` (155-174) compares locks, environment, temp folder, working folder and thread count, and no module state.
  - Process-wide latches that therefore last a whole engine session instead of one command:
    - `fsio._full_sync_said` (fsio.py:157) and `locking._full_sync_said` (locking.py:310): the Mac "volume refuses a full flush" warning is said once per session, not once per command.
    - `settings._redirect_answer` (settings.py:993).
    - `content_check._last_line` (693).
    - `store._REPLACED` (757), a counter, which is harmless.
    - The `layout` `lru_cache`s (321, 445, 547, 866; pure) and `_long_paths_on` (1143; Windows reads it once per process anyway).

    Only the reader's warnings are reset explicitly (`ocr.forget_said`, resident.py:205-215). The resident docstring promises "its error log reads the same", and that holds for the reader only.
  - What *is* pinned: values fixed at import (test_api.py:10534 `_fixed_at_import`: `TASK_NAME`, `SCREEN`, `PACKAGE_JSON`, `CHECKOUT`), one store and one reading hold per command (test_resident.py:380), and "a refusal carries nothing the last command left" (test_resident.py:343).
- Decision rows checked:
  - 193: the envelope and `_failure_of`.
  - P276: one engine per session; retire on a lock left behind.
  - P118: `one_reading` per command.
  - P220: the import-time names pinned.
  - No row covers the full-sync latch or the redirect answer under the engine, and SPEC-ui-menu-speed does not mention them.

  Verdict: the three api globals are **outgrown** (they were fine when every command was its own process, decision 193 predates P276). The latches under the engine are **accidental**.
- Proposed seam:
  - A small `_Command` dataclass (`warnings: list[str]`, `asked: dict`, `name: str`) held in a `contextvars.ContextVar` (standard library) that `api.main` sets and resets with a token in its `finally`.
  - `_warn`/`_failure_of`/`_with_list` read the var. The resident calls a public `api.begin_command()` (or nothing, if `main` owns it all) instead of clearing private lists.
  - Add a test like `_fixed_at_import` that lists every module-level name assigned under `global` in `tracker/` and requires each to be on one of two lists: "per process, deliberately" or "reset per command, by <function>". The resident then resets the second list, and a new latch cannot slip in unreviewed.
  - Standing rules: unaffected. No document, send path or original is involved.
- Behaviour risk: test_resident.py:343 and test_api.py's two `api._ASKED`/`api._RUNNING` uses (and 2 `api._warn`) reach these names. The byte-for-byte engine tests (test_resident.py:82, 100, 482) must stay green.
- Cost: S

#### C-4. The JSON contract between Python and the shell is written down nowhere as a schema, and the envelope is built in three places
- Kind: weak-typing
- Severity: medium
- Evidence:
  - The contract is implied by api.py's dict literals and the JS readers. 76 api functions return bare `dict` or `list`. There is one `@dataclass`/TypedDict-like type in api and no TypedDict.
  - It is enforced key by key in test_api.py (for example 2925-2990, which asserts `vocab["review_labels"]` key by key), by `pilot/harness/app-stub.js` ("the contract, written as code") and by test_shell's `test_the_harness_stub_replies_have_the_shape_of_the_engines`. The api docstring (1-60) lists commands, not shapes.
  - The error envelope is built by `progress.failure_reply` (progress.py:95-110), by `api.say_failure` (api.py:615-629, which re-assembles `{"error","failure","warnings"}` itself from `failure_reply(...)["failure"]`) and by `main.js shellFailure` (app/main.js:227-229).
  - `progress.FAILURE_KINDS` (92) is not sent in the vocabulary. The renderer compares the literals `"stale"`, `"failed"`, `"locked"` and `"refused"` (app.js:248-249, 320, 1805, 3422; shell.js:562). Only one of those (`err.failure.kind === "refused"`, test_single_source.py:1320) is pinned.
  - The engine's framing constants are typed twice, `resident.LINE_MAX`/`PAYLOAD_MAX`/`END_KEY` and main.js:678-683, but those are pinned.
- Decision rows checked:
  - 52: the shell runs only commands the vocabulary lists.
  - 193: the envelope.
  - P69: menu words duplicated as main.js defaults, pinned.
  - P300: vocabulary keys are dropped only with evidence. This shows the cost of having no schema: "nineteen keys were believed unread; some were."

  Verdict: **accidental**. No row chose "no schema".
- Proposed seam: `tracker/replies.py` (L0, standard library `typing.TypedDict` only):
  - `Failure`, `Envelope` and the top-level shapes of `list`, `state`, `firm`, `firm-last`, `reminder` and the write replies.
  - Annotate the `_cmd_*` returns with them. Have `_failure_of`/`say_failure` return and print exactly `progress.failure_reply(...)`, one builder.
  - A test that runs each command on the demo root and compares the reply's keys with the TypedDict's `__required_keys__`/`__optional_keys__` (runtime introspection, standard library).
  - Add `failure_kinds` to `_vocab()` and have app.js/shell.js compare against `vocab.failure_kinds.*`, or pin each literal in test_single_source.

  This gives one written contract that the stub, the tests and the JS can each be held to. Standing rules: not affected.
- Behaviour risk: none at run time (annotations only). It touches the 11,751-line test_api only by adding a test.
- Cost: M

#### C-5. runner.py holds the pass, the run log, the status page, the order hint and the CLI
- Kind: god-module
- Severity: medium
- Evidence:
  - 1-283: a 156-line docstring and imports from 24 modules.
  - 329-432: the left-behind checkpoint files (decision 186).
  - 437-625 and 719-922: CLI flags and 115 words.
  - 626-717: the firm-cache child (C-2).
  - 935-1114: the `EngagementRun`/`RunReport` records.
  - 1128-1222: draft-day rules.
  - 1253-1929: the household pass (`run_household` 243 lines, `run_engagement` 92, the sort, view and draft steps).
  - 1932-2257: the registry run and the household order hint file (`_read_order_hint`, `_write_order_hint`, `_keep_the_order`).
  - 2297-2546: the run log, the last-pass file and `last_pass_line`.
  - 2554-2989: the practice status page as HTML (about 435 lines, 23 words, `_STATUS_STYLE`).
  - 2994-3133: the argument parser and the self-limited watch (SPEC-mac R26).
  - 3136-3646: `main`, the progress lines and `_pass` (288 lines).

  api imports 10 runner names (api.py:310-321), mostly the run log's and the draft day's, not the pass's.
- Decision rows checked:
  - 51: the runner's pre-checks and draft step were named functions, and "seams where the code turned".
  - 91: the status report is a page.
  - 203: Sort & Scan is the runner.
  - 99: the runner never imports scheduling or api.

  Verdict: **outgrown**. Nothing argues for one file; decision 51 itself split by paragraph.
- Proposed seam, all flat and runner-imported:
  - `tracker/status_page.py` (L3; it needs registry, page, page_rows and manifest): `write_status_page`, `status_report`, `_engagement_status`, `_parked_files`, `_page_token`, the `STATUS_*` words.
  - `tracker/run_log.py` (L3/L4): `format_report`, `log_counts`, `append_log`, `write_last_pass`, `last_pass_line`, `amber_hours`, `PassFailed`. api then imports run-log facts without importing the pass.
  - `tracker/pass_order.py` (L4): the order hint, 2062-2257.

  `runner.py` keeps `main`/`_pass`/`run_registry`/`run_household`/`run_engagement` and the CLI. Standing rules: the draft step and "nothing is ever sent" stay in runner/reminder, unchanged.
- Behaviour risk:
  - The 19 `setattr(runner, ...)` calls in test_runner (`write_status_page`, `append_log`, `fill_firm_cache`, `load_manifest`, `_emit_line`, ...) must re-point.
  - test_runner.py:4478's `follow=False` file list moves.
  - test_layers.py:461 (`runner` never imports scheduling/api) still holds.
  - Only 2 private runner names are reached by tests, so this is the cheapest god-module to split.
- Cost: M

#### C-6. Wording: one home per sentence mostly holds, but the homes are many and api's are mixed into its code
- Kind: mixed-concerns
- Severity: medium
- Evidence:
  - Module-level string constants: api 256 (in 23 separate runs through the file, for example `NOTHING_ASKED` 4305, `DRAFT_MOVED` 5317, the schedule's words 5654-5684, `PILOT_RECORD_*` 5824-5831, `FIRM_UNREADABLE` 5942, `FIRM_PAGE_REFUSED` 6123), runner 137, reminder 79, after_install 60, scheduling 39, reasons 35 plus about 50 `Reason`s, view 24.
  - Also: `records`/`manifest` field labels and help; main.js defaults for the shell and menu words (pinned, P69); and `pilot/wording-shell.tsv` (338 rows), a third copy of on-screen words held to `_vocab` by test_api.py:2214, 2226, 10622, 10880 and 11009.
  - A literal-duplicate scan across tracker/ found only:
    - `api.MISFITS_HEADING` (760) == `runner.STATUS_MISFITS_HEADING` (2563). api already imports runner. Accidental.
    - `api.REMINDER_UNREADABLE` == `REMINDER_LINE_UNREADABLE` (423/425).
    - `ROOM_HEADING` (1261) == `ROOM_SHORT_WORDS` (1673).
    - `AFTER_INSTALL_WAIT` (1664) == `AFTER_INSTALL_HEADING` (5684).
    - `DISMISS_NOTE_HINT` == `UNFILE_NOTE_HINT` (799/804).
    - `api.DISMISS_LABEL` == `filer.NOT_REQUESTED` (791 / filer 374), a button word and a record value.

    The pairs inside api are two keys that happen to share words, which is acceptable. The api/runner pair is a true second typing.
  - `reasons.py` is a clean home: each `Reason` carries its code, sentence and client ask, and `SHORT_REASONS`/`REASON_TIPS` are keyed by code. `errors.py` holds almost no wording: it names errors by class.
  - The reminder letter's words are in reminder.py, beside `Reason.client_ask`.
- Decision rows checked:
  - 42: every fact, one home; reasons.py is every refusal.
  - P66: screen wording changes go through `_vocab` and its constants.
  - P84/P69: the shell's defaults are mirrored and pinned.

  Verdict: the one-home rule is **deliberate** and holds. That api's home is spread through a 6,800-line logic file is **outgrown**.
- Proposed seam: `tracker/screen_words.py` (C-1 item 1) becomes the single screen-word home, in the order `_vocab` sends them. Have api import `MISFITS_HEADING` from where the status page's word lives (runner, or `status_page.py` after C-5). Leave reasons.py, reminder.py's letter and the TSV alone.
- Behaviour risk: test_api's `api.<WORD>` references keep working through api's imports. The TSV tests read `_vocab()` output, not file positions.
- Cost: S (after C-1 starts), M alone

#### C-7. The "Open" allow-list of reason codes lives in the API rather than beside the codes
- Kind: leaky-abstraction
- Severity: low
- Evidence: `READ_AND_PARKED_CODES`/`NO_OPEN_CODES` (api.py:860-922) list about 50 `reasons.*` codes by hand. The test that every code is in exactly one set is at test_api.py:1085, and test_single_source.py:2757-2764. Meanwhile `Reason` already carries its other per-code policy as its own fields (`holds`, `firm_side`, reasons.py:1-60, decision 140).
- Decision rows checked: 190 ("codes are columns"; Open is an allow-list that fails closed), 184. The "listed, not derived" rule is deliberate. Placing the list in L5 is **outgrown**: a pass or a page that wants to say "openable" has to reach api.
- Proposed seam: move both frozensets into reasons.py (L0) as `OPENS_CODES`/`NO_OPEN_CODES`, still listed by hand, and keep the exactly-one-set test there. api imports them. This is safety-relevant: the allow-list must stay closed by default, and moving it changes no member.
- Behaviour risk: 7 test references to `api.READ_AND_PARKED_CODES`/`NO_OPEN_CODES`, which keep working through the import.
- Cost: S

#### C-8. reminder.py mixes triage, letter composition, HTML styling, approvals and file writing
- Kind: mixed-concerns
- Severity: low
- Evidence:
  - triage, sides and holds: 938-1159.
  - letter composition and runs: 1174-1347.
  - drafting: 1426-1555.
  - HTML and text rendering with inline colours: `Emphasis`/`STAGE_COLOURS` 543-591, `render_html` 1610-1677, `render_text_html` 1712.
  - fingerprints and approval ledger events: 1739-1881.
  - draft file IO: `write_draft` 1999-2084.
  - drafted events: 2090-2149.

  12 classes. Only 1 private name is reached by tests.
- Decision rows checked: 115 (an ambiguous row holds the draft), 117 (stages), 133 (wait for the sort). Verdict: **accidental**, but low harm today.
- Proposed seam: `tracker/letter_render.py` (L0/L1, pure: `stage_emphasis`, `run_emphasis`, `render_html`, `pasted_text`, `split_pasted`, `render_text_html`, the colours). reminder.py keeps the decisions and the record. Standing rule "nothing is ever sent": rendering stays text-only, and the module imports no network module (test_layers.py:488 covers it if it is flat).
- Behaviour risk: test_reminder's rendering tests import from reminder, so re-export or re-point them.
- Cost: S

#### C-9. The HTML page skeleton is typed twice
- Kind: duplication
- Severity: low
- Evidence: runner.py:2809-2820 and view.py:696-712 build the same doctype/head/charset/CSP-policy/title/style/body lines by hand. `page.py` already owns `policy`, `table` and `page_text` (page.py:198-217).
- Decision rows checked: 91 (pages, not workbooks); no row on the skeleton. Verdict: **accidental**.
- Proposed seam: add `page.document(title, style, policy, body, *, meta=(), script=None) -> list[str]` in page.py (L0). This keeps "nothing fetched" (the CSP) in one place, which serves the no-network rule.
- Behaviour risk: the pages' exact bytes are compared by the view and status-page tests. Keep the line order.
- Cost: S

#### C-10. after_install's `run()` hard-wires its jobs, so adding the "further job" CLAUDE.md asks for touches five places
- Kind: other
- Severity: low
- Evidence: `_run` (after_install.py:893-981) calls `_schedule`, `_time_machine`, `_check`, `_clear_test_cache`, `_remove_the_retired_caches` and `_ready_the_overview` one after another. It then builds `failed` from a hand-picked tuple (`(schedule, excluded, check, cache)` at 929; `retired` and `overview` are left out on purpose), assembles `lines` with per-job conditions (956-970), and fills `AfterInstall` field by field. CLAUDE.md and decision 209 name this as the one place a one-time step is added.
- Decision rows checked: 209 (one-time steps run themselves), P234 (the retired-cache job moved here). Verdict: **accidental**.
- Proposed seam: a tuple of `(key, job, counts_as_failure)` entries returning `_Step | None`, folded by one loop into `failed` and `lines`. `AfterInstall` keeps its fields for the record's shape.
- Behaviour risk: test_after_install (1,831 lines) pins line order and record keys. Keep the order.
- Cost: S

### Looks wrong, is deliberate (leave alone)
- `resident.py` duplicating stdin and refusing own-process commands, then retiring, rather than running everything: P276 and SPEC-ui-menu-speed 3.1 (locks, kill per command).
- The engine framing constants and the shell/menu words typed again in main.js: P69 and P84. A notice must work before any vocabulary arrives (api.py:403-405 `NOTICE_LABELS`), and the copies are pinned by test.
- `scheduling.TASK_NAME` and `api.SCREEN` read the product name at import: P220. They are pinned as the only import-time values (test_api.py:10534), and api_entry.py orders imports for it.
- Two caches for the practice, `firm-view.json` (firm_cache) and `page-rows.json` (page_rows), keyed differently: P120 and P227. page_rows.py:34-40 records why the firm view's rows were rejected ("a second place a status is decided").
- `runner.py` never importing api or scheduling: decision 99 and test_layers.py:461. Fix the coupling by moving the builder down (C-2), not by relaxing this rule.
- `fsio.full_sync` and `locking.full_sync`, two identical copies: SPEC-mac R22 (fsio.py:171-178). It is the price of the layer rule, and a test holds them equal.
- `api.main` handing `run-now` straight to `runner.main` before its envelope and reading session: decision 203.
- `HELD_READING_COMMANDS`/`WRITING_COMMANDS`/`OWN_PROCESS_COMMANDS` as hand lists checked by AST derivations: decision 159 (E5) and P276. The derivations are the guard.
- `reasons.Said`, a `str` subclass carrying its code: decision 190 (reasons.py:80-92).
- `_undo_create` using `shutil.rmtree`: decision 137. It is reached only through `_undo_made` on folders this call made. Move it with that guard (C-1), never without it.

### Cross-slice notes
- `store._CHECKPOINT`/`_CONNECTION`, `settings._HELD`/`_redirect_answer`, `ocr._ENGINE`/`_SESSION`/`_SAID` and `content_check._STOP`/`_last_line` are process globals that the engine relies on being reset per command (C-3). This belongs to the slice owning store, settings, ocr and content_check.
- `layout` has four `lru_cache(maxsize=8192)`s and one `functools.cache` (`_long_paths_on`, which asks Windows). They are pure or once per process, but the engine keeps them for a session: the layout and fsio slice.
- The guard tests (test_layers.py:294, 338, 488, 750; test_single_source.py:1503, 1522, 1585, 2132, ...; test_api.py:7197) glob `tracker/*.py` non-recursively. Any slice proposing a subpackage must widen them to `rglob` first, or the forbidden-network-import check stops seeing the new files. This matters to every slice.
- `app/renderer/app.js` compares failure kinds by literal (248-249, 320, 1805, 3422) with no vocabulary key and only one pin: the JS slice (see C-4).
- `pilot/harness/app-stub.js` calls itself "the contract, written as code" for app.js's surface, a second implied contract on the JS side: the JS slice.
- `filer._may_carry_code` is imported by api (api.py:131), a private name across modules: the filer slice could make it public (`may_carry_code`).

---

## Slice D: the Electron shell

*Questions put to this slice: (Q1) how the renderer scripts share state; (Q2) what jobs live in app.js; (Q3) which rules JavaScript re-implements; (Q4) how main.js talks to the engine; (Q5) the Electron security posture; (Q6) how the renderer is tested and how brittle that is to moving code.*

Read only. Measurements come from an acorn parse of each file (`/opt/node-tools/node_modules/acorn`, from a scratchpad script). "Top-level defs" counts top-level function declarations and arrow-function consts; `let` means module-level `let` bindings. Fan-in and fan-out count the other renderer files that use, or are used through, the shared global lexical scope (classic scripts; see D-2). There are no `import` statements anywhere. For the JS files, "Type-hint share" is the share of functions with JSDoc `@param`/`@returns`. It is 0 everywhere: there is not one JSDoc tag in the shell.

### Module table
| Module | Lines | Top-level defs | Longest function (lines) | Fan-in | Fan-out | Own test file (lines) | Type-hint share |
|---|---|---|---|---|---|---|---|
| app/main.js | 1,325 | 39 fn; 18 `let`, 53 `const` (Maps/Sets `passes`, `openable`, `carriesCode`; `shellSays` mutated) | spawnTracker 161 (its Promise executor alone 145), createWindow 52, startEngine 45, learn 40, engineLine 31 | 0 (Electron entry; `Start App.bat`) | preload.js (by path), the engine processes `tracker.api` / `tracker.resident` | none by name. test_shell_menu.py (952) runs it under a fake Electron. The engine tests are in test_single_source.py 4956-5150 | 0% |
| app/preload.js | 27 | 1 bridge object, 9 members | 1-line closures | main.js | electron | none. Read as text by test_shell_menu.py | 0% |
| app/renderer/app.js | 4,283 | 229 fn + 1 class; 41 `let`, 15 `const` | editorWindow 143, drawReminder 80, requestRows 79, createEngagement 63, cellInput 62 | 5 (pages, sheet, shell, pilot, tour) | 5 (shell, pages, sheet, tooltip, pilot-content) | none. Pinned by test_shell.py (8,823), test_single_source.py (5,348), test_api.py, test_row_columns.py (769). 79 of its functions are lifted by name | 0% |
| app/renderer/shell.js | 1,819 | 111 fn; 33 `let`, 12 `const` | setupPage 49, drawLastSort 42, shellAskLastPass 41, shellTurnFirm 41, shellLoadFirm 40 | 3 (app, pages, sheet) | 6 (app, pages, sheet, tooltip, pilot, tour) | test_shell.py (shared). 81 of 111 functions lifted by name | 0% |
| app/renderer/pages.js | 2,255 | 145 fn; 17 `let`, 17 `const` | pagesReturnGroups 120, pagesDraw 57, pagesGroup 49, pagesRowNode 43, pagesList 39 | 3 (app, sheet, shell) | 4 (app, sheet, shell, tooltip) | test_shell.py (shared). 57 lifted | 0% |
| app/renderer/sheet.js | 355 | 20 fn; 2 `let` | sheetDrawCheck 33, openReminder 31, openCheck 24 | 3 | 4 | test_shell.py (shared). 16 of 20 lifted | 0% |
| app/renderer/tooltip.js | 174 | 11 fn; 3 `let`, 3 `const` | placeTip 22 | 6 (every other file) | 0 (vendor floating-ui) | test_shell.py | 0% |
| app/renderer/tour.js | 208 | 1 IIFE namespace `PilotTour` | the IIFE 190; place 35 | 2 (pilot, shell) | 4 | test_tour.py (114) + test_pilot.py | 0% |
| app/renderer/pilot.js | 341 | 3 IIFE namespaces (`PilotRecord`, `PilotDom`, `PilotTerms`) | PilotTerms 194; build 69; gate 57 | 2 (shell, tour) | 4 (app `vocab`, pilot-content, tooltip, tour) | test_pilot.py (986) | 0% |
| app/renderer/pilot-content.js | 168 | 1 data const `PILOT` | - | 3 | 0 | test_pilot.py | 0% |
| app/renderer/index.html | 573 | 202 ids. Script order: floating-ui x2, app, tooltip, pages, sheet, shell, pilot-content, pilot, tour | - | - | - | test_shell.py / test_pilot.py / test_single_source.py (text) | - |
| CSS: style.css 457, pilot-ui.css 622, shell.css 1,407, pilot-style.css 208 | 2,694 | 625 selectors; 65 defined in more than one file (54 in both style.css and pilot-ui.css) | - | - | - | test_pilot_ui.py (311); test_shell.py reads shell.css 44 times | - |
| pilot/harness/stub.js | 665 | 1 IIFE | IIFE 651; stateOf 101; pageOf 85 | harness only | - | held to the API by test_shell.py `_stub_replies` | 0% |
| pilot/harness/app-stub.js | 292 | 37 fn; 11 `let` | showReturn 22 | harness only | - | none | 0% |

### Findings

#### D-1. app.js is a 4,283-line god module holding at least 17 responsibilities (answers Q2)
- Kind: god-module
- Severity: high
- Evidence: 229 functions, 41 module `let`s and 53 top-level wiring statements. The responsibilities by line range, from its own section heads:
  - 1-60: the shared state (`paths`, `engagements`, `households`, `active`, `forms`, `editorRows`, `lastState`, `vocab` and others), `$`, platform detection, and the `el` attribute allowlist.
  - 61-189: the `el` builder, `fill`, the set-aside grouping and `toast`.
  - 190-231: **IPC client**: `TrackerError`, `call()`, `takeReply()`. `call()` also tells the shell that a write landed (`shellWriteLanded`, 215), so the transport calls into the UI.
  - 232-450: notices.
  - 451-509: view generation, `withEng` and `renderFor`.
  - 510-831: the weekly reminder letter (drawn here, framed by sheet.js).
  - 832-1234: the review sheet's rows and answers: a wandered copy, Needs review, an unnamed issuer, hand-over.
  - 1235-1388: the write helpers `writeRow`, `writesInFlight`, unfile and mark missing.
  - 1389-1762: the roll dialog.
  - 1763-1923: the engagement lock watch.
  - 1924-2195: data flows: `applyVocabulary`, `loadEngagements`, `bootstrap`, `saveRoot` and the schedule repair.
  - 2196-2316: the Schedule dialog.
  - 2318-2616: the pass and Sort's answers.
  - 2617-2910: Add a return / New household, the household step and People.
  - 2911-3333: the shared row component and the editor's own virtualizer.
  - 3334-3432: custom requests and `createEngagement`.
  - 3433-3894: **the request-list editor**, including the CSV and TSV paste parser.
  - 3895-4105: the dialog registry (`DIALOGS`, `openDialog`, `requestClose`, `trapTab`).
  - 4106-4283: wiring: about 60 listeners, the one keydown listener, and `startWhenLoaded(bootstrap)`.
  - Its curated repo-map note (`docs/repo-map.curated.json`, node `app/renderer/app.js`) runs to roughly 8,000 words.
- Decision rows checked:
  - P7 and P10: pilot code is additive, with no edit to existing JS. Both have been relaxed again and again: P21 (app.js for the schedule), P40, P58 (main.js and preload), P67 (app.js and index.html "edited where the SPEC names them"), P253 (an app.js handler).
  - P160 makes the Console the one product, so the original is to be folded in and retired. P7's reason ("keeps merges from main conflict-free") therefore no longer fits.
  - P76 keeps the one keydown listener in app.js, and decision 201 keeps one dialog registry. Both still hold inside any split.
  - Verdict: **outgrown**. The file boundaries follow the build history (the base app, then S3 shell, S5 sheet), not responsibility.
- Proposed seam: keep classic scripts in the same index.html order, and split app.js by line range into new files loaded just after the floating-ui vendor scripts:
  - `api-client.js`: `TrackerError`, `call`, `takeReply`, `withEng`, `viewGeneration`, `writeRow`, `writesInFlight`, `sayNotes`.
  - `notices.js`: 232-450.
  - `dialogs.js`: 3895-4105.
  - `reminder.js`: 510-831.
  - `review.js`: 832-1388.
  - `household.js`: 1389-1762, 2617-2910, 3334-3432.
  - `editor.js`: 2911-3333 and 3433-3894.
  - `schedule.js`: 2196-2316.
  - `pass.js`: 2318-2616.
  - app.js keeps the state, `applyVocabulary`, `bootstrap` and the wiring. The global names stay identical, so shell, pages and sheet do not change. All of these files sit in the `desktop-app` layer.
  - The standing rules are untouched: no file gains a network call or a write path. Every write still goes through `call()` to the engine.
- Behaviour risk:
  - test_single_source.py reads `app/renderer/app.js` 61 times, test_shell.py 103 times and test_api.py 24 times.
  - Count pins that assume one file: `js.count('withEng("assign")') == 2` and `fileRow` x2 (test_single_source.py 136-141); `document.addEventListener("keydown"` == 1 (test_shell.py 676-680; test_single_source.py 4242).
  - Negative guards that read only app.js would silently stop covering the moved code (see D-5).
  - 79 app.js functions are lifted by name with an explicit `"app.js"` source (for example `js_function("storeRead", "app.js")`).
  - Do D-5 first.
- Cost: L

#### D-2. Renderer state is shared through one implicit global scope, with bidirectional coupling and no enforced seam (answers Q1)
- Kind: global-state / tight-coupling
- Severity: high
- Evidence:
  - **How state is shared.** No `window.*` property is hung anywhere. The only `window.` names used are `window.tracker` (the bridge), `localStorage` and timers. All sharing is through the classic-script global lexical scope: top-level `let`/`const`/`function`, ordered by index.html lines 443-452.
  - **Cross-file references, counted by name from an acorn walk:**
    - shell.js uses 45 names declared in app.js, 12 of them data: `vocab`, `scanning`, `setupDraft`, `lastState`, `paths`, `engagements`, `households`, `forms`, `locked`, `lockStale`, `active`, `dialogStack`.
    - app.js uses 27 shell.js names, among them `shellRoute`, `shellReturnStale`, `shellBack`, `shellRootSet` and `shellWriteLanded`.
    - pages.js uses 23 app.js names. sheet.js uses 22, including `reminderCard`, `reminderCardFor`, `dialogOpener` and `dialogStack`.
  - **Writers and readers.** Every app.js `let` is written only inside app.js; `reminderCard` has the most writers (5 functions). `lastState` is written by `renderFor` alone and read 13 times in pages.js, 11 in sheet.js and 9 in shell.js. The writes across files are:
    - app.js:2050 sets shell.js `shellReturnStale`; app.js:2096 sets `shellBack`.
    - shell.js:1780 and 1787 set pages.js `pagesClientType`. shell.js:559 and 1788 mutate or delete keys of `pagesPageAt`.
    - shell.js:1467-1526 writes fields of app.js `setupDraft`.
  - **The documented seam understates the real one.** shell.js's header (lines 15-37) names about 8 app.js entry points; the real use is 45.
  - **Load order has already broken once.** The app.js:4274-4283 comment records "final review B, finding 1": the first `list` could answer before shell.js and pages.js had loaded.
  - **Nothing indexes it.** The repo map draws no edges between renderer files (the `show app/renderer/shell.js` "out:" list is empty), and test_layers.py has no JS layer table.
- Decision rows checked:
  - P67 (new files share app.js globals).
  - P10 (no edit to existing JS, so the new files had to read app.js's globals rather than change it).
  - No row chooses globals as an architecture, and P10 is relaxed.
  - Verdict: **accidental**, an artifact of P10 that P10's relaxation leaves without a reason.
- Proposed seam, staying with plain classic scripts: each file keeps its mutable state in one owner object (`const appData = {paths, engagements, ...}`, `const shellNav = {route, back, returnStale, ...}`, `const pagesView = {clientType, pageAt, ...}`). Writes across files become owner functions: `shellForgetBack()`, `shellMarkReturnStale()`, `pagesSetClientType()`, `setupDraftSet()`. A new `tests/test_renderer_seams.py`, the JS analogue of test_layers:
  - reads the script order from index.html;
  - collects each file's top-level declarations by regex (`^(async )?function (\w+)\(`, `^(let|const) (\w+)`);
  - pins the allowed cross-file names per ordered pair.
  - Add the same edges to the curated repo map.
  - ES modules are not proposed: the tests lift top-level functions as text, and an IIFE or namespace refactor would break every lift (see D-5).
- Behaviour risk: renaming the shared `let`s breaks the test fakes that redeclare them (test_shell.py builds `let lastState`, `let vocab` and others in its setup strings). The app-stub double (D-9) must change with them.
- Cost: M

#### D-3. Rules re-implemented in JavaScript that the engine also implements (answers Q3)
- Kind: duplication
- Severity: medium
- Evidence:
  - **(a) Who a document may be handed to.** app.js:1047-1057 `fedReturns` (an active return, in an open year, not this one, plus feeds that have a path) duplicates api.py:4953-4975 `_fed_returns`. `_state` already builds it (`fed_once`, api.py:3148) but never sends the list. pages.js:2167 also uses `fedReturns` to decide whether to offer the menu item. A drift means a choice is offered and then refused (`NOT_FED`, api.py:4991), never a misfile.
  - **(b) A return's group counts.** pages.js:1595-1608 `pagesTally` (items by group; files only in needs_you or set_aside) duplicates the firm row's counts in api.py:5985-5994 together with `file_group` (api.py:3092-3101). shell.js:879-885 `shellCountsDiffer` compares the two to decide whether to ask again for the firm's counts. The Python comment says "the two cannot disagree", but nothing shares the code.
  - **(c) The taxpayer cut.** pages.js:221-232 `pagesTaxpayer` duplicates firm_pages.py:292 `_taxpayer`, whose docstring names the JS twin. Each has its own test cases (test_shell.py:1988; test_firm_pages.py:283). No shared table.
  - **(d) The group keys.** pages.js:57 `PAGES_GROUPS` duplicates api.py:3067-3071 `GROUPS`. No test pins them equal. The literal is copied a third and fourth time into the test fakes (test_shell.py:1018; test_single_source.py:4147, 4172).
  - **(e) The list cells.** pages.js:77-82 `PAGES_COLUMNS` duplicates firm_pages.py:85-92 `CELLS`.
  - **(f) The nothing-asked rule.** app.js:3375-3384 (custom rows must be named; at least one request asked) also lives at api.py:4305-4314 (`NOTHING_ASKED`). The words come from the vocabulary; the rule is a pre-check, and the API refuses too.
  - No limit or max length is duplicated except pilot.js:183 `maxlength=200`, which is pinned to `SIGNED_BY_LONGEST` (test_single_source.py:5347).
- Decision rows checked:
  - P278: the engine pages the firm lists, and pages.js still draws the household and return pages, which is why (c) and (e) exist.
  - Decision 129 (feed list), SPEC-shell 9.1 (groups), decision 142 (nothing asked).
  - Verdict: **(a), (b), (d) accidental; (c), (e) outgrown** (P278 moved half the drawing to the engine); **(f) deliberate** (an instant answer in the dialog).
- Proposed seam: the engine sends results and the page only draws them.
  - Add `state.hand_over_targets: [{path, label}]` from `fed_once`, and drop `fedReturns`.
  - Add `state.tally` (the same per-return counts the firm row computes, built by one shared helper in api.py), and drop `pagesTally`.
  - Add `vocab.groups = GROUPS`, so `PAGES_GROUPS` is read rather than typed.
  - Add a `taxpayer` key on each `household.returns[]` row, so pages.js stops cutting names.
  - All layers are unchanged. The standing rules hold: the engine stays the single decider ("nothing is guessed"), and the page only shows.
- Behaviour risk: test_shell.py probes lift `pagesTally`, `pagesTaxpayer` and `fedReturns` fakes (2116, 2162). test_api.py shape tests for `state` would gain keys. The harness `stub.js` `stateOf` must send the new keys (test_shell.py `_stub_replies` checks the shape).
- Cost: M

#### D-4. main.js mixes 13 concerns, and one 161-line function carries the whole engine-call path (answers Q4)
- Kind: mixed-concerns
- Severity: medium
- Evidence:
  - **The concerns by line range:**
    - 1-94: packaging paths and the Mac floor.
    - 95-218: the command allowlist state, timeouts, channels and the shell's own sentences.
    - 218-300: error logs and rotation.
    - 300-370: menu words and the last-pass file watch.
    - 380-421: `learn()`, which mutates 10 module globals from **every** reply: `allowedCommands`, `ownProcessCommands`, `engagementFlag`, `passCommand`, `pathKinds`, `shellSays`, `writingCommands`, `errorLog`, `openable`, `carriesCode`, plus the menu and the watch.
    - 423-640: validation, then `spawnTracker`.
    - 642-674: `lineReader` and `startTracker`.
    - 676-900: the resident engine's lifecycle, the restart budget and the program stamp.
    - 900-960: `openPath` and `openChecked`.
    - 960-990: the IPC handlers.
    - 990-1160: the menu bar and popups.
    - 1164-1240: theme and window.
    - 1240-1325: app lifecycle.
    - There are 18 module `let`s.
  - **Q4: one client wrapper, not many call sites.** Every renderer command enters through `ipcMain.handle("tracker-cmd")` (960). The path then runs:
    - `runTracker` (439), which checks `commandProblem`: an allowlisted command alone, or followed by `vocab.engagement_flag` and one folder.
    - `spawnTracker` (454). It serialises the payload once, then hands the command either to the free engine through `takeEngine` (884) or to a process of its own through `startTracker`.
    - The resident framing to the engine is one line `{id, argv, bytes}`, then the payload bytes, with stdin kept open.
    - The engine replies with stdout lines. A line keyed `progress` is a progress line, and the last other line is the reply. The command ends at `{"engine_end": id, code, retiring}` (`engineLine` 773).
    - Passes, `own_process_commands`, the launch door and retries always get a process of their own. A read the engine lost is retried once; a write never is.
  - On the renderer side there is one wrapper, app.js:212 `call()`, plus `writeRow` (10 sites) and `withEng` (16 commands). Three call sites bypass `call()` and go straight to `window.tracker.call`: shell.js:349 and 391 (early `firm` and `firm-last`, which still pass through `takeReply`, by P221/P229), and pilot.js:78 (see D-6).
  - Argument lists are hand-built at about 40 sites: 17 `call([...])` in app.js, 7 in shell.js, and the `withEng` uses.
- Decision rows checked:
  - P58 relaxed P10 for main.js (the menu). P276 put the engine into main.js. Decisions 176, 188 and 193 explain the checks.
  - Verdict: **outgrown**. The checks are deliberate; their being in one file is not.
- Proposed seam: CommonJS files the main process `require`s by plain string (allowed by test_layers' tripwire, test_layers.py:270-275 and 631-650):
  - `app/engine.js`: `commandProblem`, `runTracker`, `spawnTracker` split into `framePayload`, `routeCommand`, `watchReply`; `lineReader`, `startTracker`, the engine lifecycle.
  - `app/open-path.js`: `openable`, `carriesCode`, `openPath`, `openChecked`, `pathKinds`.
  - `app/menu.js`: 941-1160.
  - `app/logs.js`: 205-300.
  - `app/last-pass-watch.js`.
  - main.js keeps the window, the IPC registration and the lifecycle, and calls a `learn()` that hands each module its slice of the vocabulary.
  - All main-process files sit in the `desktop-app` layer. The standing rules hold: no new channel, no network module, and `openable` stays the only door for opening.
- Behaviour risk: tests slice main.js text by function boundaries:
  - test_single_source.py:3549-3552, 4983 (`main_js.index("function spawnTracker"):main_js.index("function lineReader")`), 5218-5223, 2498-2505 (`openChecked`).
  - test_shell_menu.py splits on `const BAR = [`, `const POPUPS = new Map([` and `const DEFAULT_MENU_WORDS = {`, and runs `app/main.js` by path under the fake Electron (test_shell_menu.py:340).
  - test_layers.py:960-968 scans only `app/main.js` and `app/renderer/app.js` for `startsWith(`.
  - test_single_source.py's engine tests (4956-5150) drive main.js as one file.
- Cost: M

#### D-5. Text-pinning tests are tied to file names and formatting, so moving code is expensive and can silently drop guards (answers Q6)
- Kind: tight-coupling (test to source layout)
- Severity: medium-high (it is the gate on D-1, D-2, D-4 and D-7)
- Evidence:
  - **How the renderer is tested.** Mostly not in a browser. Python tests do two things:
    - They read JS and CSS as text and assert substrings or regexes.
    - They **lift functions by name**: `js_function(name, source="shell.js")` (test_shell.py:726-731) cuts from `function name(` to the first `"\n}\n"`. `run_shell` (734-753) writes the lifted text plus hand-written fakes for the DOM and app.js globals to a temporary probe.js, and runs it under `node`.
  - **How much is lifted.** 235 distinct renderer functions are lifted by name: 81 from shell.js, 79 from app.js, 57 from pages.js, 16 from sheet.js and 2 from tooltip.js. The calls are 72 `js_function` calls in test_shell.py (55 name a file explicitly: 19 app.js, 19 pages.js, 11 shell.js, 3 sheet.js, 3 tooltip.js) and 35 in test_single_source.py.
  - **Only one lifter survives a move.** `lift()` (4474-4482) searches `SPEED_SOURCES` (4 files). It is the only lifter that survives a move.
  - **Guards that read one file.** These check app.js only, so code moved out escapes them silently:
    - test_single_source.py:566-575 (`innerHTML`, `eval(` and the other sinks).
    - test_single_source.py:105-115 (commands called must be in `api.COMMANDS`). shell.js's `firm`, `firm-last`, `last-pass` and `list` calls are not checked by any test against `api.COMMANDS`.
    - test_api.py:1266-1329 (no vocabulary word typed in the renderer).
    - test_layers.py:960-968 (`startsWith(`).
  - **Four hand-kept lists of renderer files:** `SHELL_FILES` (test_shell.py:49), `TITLE_FREE` (51), `SPEED_SOURCES` (4471) and `PILOT_JS` (test_pilot.py:23). A new file is covered only if someone adds it.
  - **The formatting is load-bearing.** A function indented inside an IIFE, or closing at anything but column 0, cannot be lifted.
  - **The in-browser harness** (pilot/harness `shoot.mjs`, `interact.mjs` with Playwright) is not run by pytest (README line 6).
- Decision rows checked:
  - P10's reason ("many tests pin the existing files' exact text").
  - test_row_columns.py:33-39 ("the app has no test harness of its own").
  - Verdict: **accidental**. The pins are deliberate; their being scoped to file names is not.
- Proposed seam: one test helper, `tests/renderer_source.py`:
  - `RENDERER_SCRIPTS` is parsed from index.html's `<script src>` list, excluding `vendor/`.
  - `renderer_text()` joins all of them.
  - `js_function(name)` searches every script and asserts exactly one definition.
  - `lift_line` follows the same rule.
  - Turn the four negative guards into loops over `RENDERER_SCRIPTS`, and replace the four hand lists with it or with named subsets of it.
  - This is test-only, with no product change. Do it before any split.
- Behaviour risk: none expected from widening the command guard: shell.js's `last-pass`, `firm`, `firm-last`, `list` and pilot.js's `pilot-record` are all in `api.COMMANDS` (checked). The count pins (`withEng("assign")` == 2) should count across all scripts.
- Cost: S

#### D-6. pilot.js polls the `vocab` global and bypasses `call()`, a P10 workaround that P10's relaxation leaves unneeded
- Kind: tight-coupling
- Severity: medium
- Evidence:
  - pilot.js:49-62 `ready()` polls `typeof vocab === "object"` every 200 ms for up to 120 s (`READY_WAIT_MS`).
  - pilot.js:78 calls `window.tracker.call(["pilot-record"], payload)` directly. Reply warnings are dropped, and an error goes only to `logError` (80). Nothing is shown.
  - The badge and the Tour button are built at run time, not in index.html (P10).
  - tour.js and pilot.js use IIFE namespaces (`PilotRecord`, `PilotDom`, `PilotTerms`, `PilotTour`), a different module style from the rest. Both styles are fine; they are not consistent.
- Decision rows checked:
  - P10 (no edit to existing JS, the badge created at run time); P7.
  - Both relaxed in practice by P21, P40, P58, P67 and P253. P160 (one product).
  - Verdict: **outgrown**.
- Proposed seam: app.js (or `api-client.js` from D-1) exposes `const appReady = new Promise(...)`, resolved in `applyVocabulary` next to the existing `shellVocabulary()` seam. pilot.js awaits it and calls through `call()`, so failures become notices like every other command's (decision 193).
- Behaviour risk: test_pilot.py pins pilot.js text, including `const COMMAND = "pilot-record";` (140) and its banned-sink list (97). test_tour.py and test_pilot.py check the badge is built at run time.
- Cost: S

#### D-7. shell.js carries a 30-flag firm-count loading state machine mixed with routing and drawing
- Kind: global-state / mixed-concerns
- Severity: medium
- Evidence:
  - shell.js:54-88 declares 30 module `let`s. `shellFirmNow` is written in 5 functions and `shellFirmLast` in 4. `shellFirmEarly`, `shellFirmCount`, `shellFirmSlow`, `shellFirmTimer`, `shellFirmAsOf`, `shellLastPassOwed`, `shellLastPassAgain` and `shellTurnGen` are each written in 3.
  - The loading protocol (scheduled-pass watch 215-367, last counts 368-456, the firm lists a page at a time 457-735) is about 520 lines.
  - The same file also holds the route (43-125, 767-894), the side panel, View toggles, last sort, the path row, the Sort Now button, search (1227-1354), the setup page (1450-1529), the page's side of the menu channel (1530-1687) and the keyboard (1688-1776).
- Decision rows checked: P218, P221, P222, P228, P229, P262, P277 and P278. Each added a flag or a timer to the same scattered state. Verdict: **outgrown**.
- Proposed seam: a new classic script, `firm-loader.js`, loaded before shell.js:
  - One `const firmLoad = {now, asked, early, earlyLanded, last, asOf, sentAt, wroteAt, held, count, slow, timer, turns, turnGen, turnThen}` and one `const lastPass = {...}`.
  - It takes `shellAskFirmNow`, `shellAskFirmLast`, `shellLoadFirm`, `shellFirmMerge`, `shellFirmShaped`, `shellFirmAsk`, `shellTurnFirm`, `shellAskLastPass`, `shellWriteLanded` and `shellCountsDiffer`, keeping their names.
  - shell.js keeps the route and the drawing. Layer: `desktop-app`.
- Behaviour risk: `js_function`'s default source is `"shell.js"` (test_shell.py:726), and `ENGINE_FUNCTIONS` (708) lifts `shellFirmAsk`, `shellFirmMerge` and `shellFirmShaped` from it. A move breaks those lifts unless D-5 lands first.
- Cost: M

#### D-8. The harness's app.js double, "the contract written as code", has drifted, and nothing holds it
- Kind: other (test infrastructure)
- Severity: medium
- Evidence:
  - pilot/harness/app-stub.js:33-40 `EL_ATTRIBUTES` lacks `"open"`, which app.js:50-58 has.
  - Eight app.js names that shell.js and pages.js call are not defined in the double: `editorDensityChanged` (shell.js:1000), `removeScheduleHere` (1661), `toastWord` (1798), `notADocument`, `fedReturns`, `writeBusy`, `openUnfile` and `withdrawAnswer` (pages.js:2167-2234). The double throws a ReferenceError on those paths.
  - pilot/harness/README.md calls the double "the contract, written as code". stub.js is held to the API by test_shell.py:2573+ (`_stub_replies`), but no test reads app-stub.js.
- Decision rows checked: SPEC-shell 14.4 (the harness). No row exempts the double from checking. Verdict: **accidental**.
- Proposed seam: a test that collects the app.js names shell.js, pages.js and tooltip.js use (the D-2 regex table) and asserts that app-stub.js defines each of them, with an equal `EL_ATTRIBUTES` literal. Alternatively, have serve.mjs lift `el` and `EL_ATTRIBUTES` from app.js instead of copying them.
- Behaviour risk: none to the product.
- Cost: S

#### D-9. Sentences typed in app.js, outside the API's vocabulary
- Kind: duplication (wording)
- Severity: low
- Evidence: app.js:1073-1077 in `fileRow`'s `sayNotes`: `` `${a.original_name} filed as ${a.filed_as}` ``, `` `"${a.keyword}" added to ${a.identifier} so the next one files itself` `` and `` `"${a.spelling}" added so the next page that prints it confirms itself` ``. These are the only multi-word English literals in the renderer outside CSS selectors and error text (acorn scan over all 6 renderer scripts). They break app.js's own claim (lines 33-35, "every word ... comes from the API's vocabulary") and P63's five-word limit. The guard against typed words (test_shell.py:640-655) covers `SHELL_FILES` only, and app.js is not in it.
- Decision rows checked: P63 (every word is the API's; at most five words); decision 112 (sayNotes). Verdict: **accidental**.
- Proposed seam: the engine returns `assigned.said` (its own sentences, as `marked_missing.reason` and `dismissed.decision` already are), or `vocab.review_labels.filed_as` and `keyword_added` patterns. Extend the literal-words test to app.js.
- Behaviour risk: test_api.py's assign reply shape tests. The wording table in the decision log.
- Cost: S

#### D-10. Electron security posture is sound; the IPC handlers other than `menu` do not check the sender (answers Q5)
- Kind: other (security)
- Severity: low
- Evidence:
  - **Window settings.** `webPreferences` (main.js:1212-1222) sets `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`, `webSecurity: true`, and `devTools: !app.isPackaged`.
  - **Containment.** `setWindowOpenHandler` denies (1228), `will-navigate` is prevented (1229), and there is a single-instance lock (1251). The CSP is `default-src 'none'; script-src 'self'`, with no inline script or handler (index.html:8; pinned by test_single_source.py:566-575).
  - **The preload's surface** (preload.js:3-27):
    - `call(args, payload)`, which reaches any allowlisted command with any JSON payload;
    - `open(p, how)`, `pickFolder(title)`, `logError(text)`;
    - `onProgress`, `onAfterInstallDone`, `onLastPassChanged`, `menu.onCommand`, `menu.send`. The `on*` listeners cannot be removed.
  - **What each channel checks:**
    - `tracker-cmd`: the command against the learned allowlist (or `EARLY_COMMANDS` before it is learned) and the argument shape (`commandProblem`, 423-436). The `--engagement` folder string and the payload are not inspected in main.js; the engine's door does that (decisions 176, 188).
    - `open-path`: the path must equal a reported one (`openable`), and an `lstat` must find the same kind and no symbolic link (900-958).
    - `pick-folder`: only a title string goes in.
    - `log-error`: capped at 64 KB per entry (`STDERR_CAP`), with no rate limit. It appends to the API's log without rotating it (rotation happens on Python's own writes; main.js:247-249).
    - `menu`: checks the sender (`event.sender !== mainWindow.webContents`, 1140), and the ids and tokens.
    - `tracker-cmd`, `open-path`, `pick-folder` and `log-error` do **not** check the sender. Low risk while there is one window and navigation is denied.
  - **No channel takes a command or path unchecked** in a way that bypasses the engine. `spawn` takes an argv array and no shell.
- Decision rows checked: 176 (parse, never trust; devtools), 188 (one path authority), 190 (no network), 193 (envelope; stderr only to the log). The prior audit pilot/AUDIT-2026-10-11.md S3 covers `log-error`. Verdict: **deliberate**, apart from the sender checks, which are accidental.
- Proposed seam: one `fromMainWindow(event)` guard applied in every `ipcMain.handle`, as `onMenuMessage` already does. Optionally, a per-minute cap on `log-error`.
- Behaviour risk: the fake Electron in test_shell_menu.py must pass a sender whose `webContents` matches.
- Cost: S

#### D-11. Four stylesheets layered by override; style.css frozen and restyled by pilot-ui.css
- Kind: duplication (CSS)
- Severity: low
- Evidence: 625 selectors across 4 files. 65 are defined in more than one file: 54 in both style.css and pilot-ui.css (for example `.btn`, `.editor-table td`, `#notices`) and 9 in both pilot-ui.css and shell.css. 4 `!important` in all. The link order is load-bearing and pinned (test_pilot.py:90-94; test_pilot_ui.py:137).
- Decision rows checked:
  - P51 (style.css unedited; pilot-ui.css overrides it) and P67 (style.css stays unedited).
  - P160 (fold the original; still Open).
  - Verdict: **deliberate today, outgrown once P160's fold lands**. The reason is merges from the original, which the fold ends.
- Proposed seam: after the fold, merge each of the 54 overridden rules into one home (pilot-ui.css), delete them from style.css, and keep one `:root` token block.
- Behaviour risk: test_pilot_ui.py's 13 tests read pilot-ui.css. test_shell.py reads shell.css 44 times and style.css 5. main.js:1170-1185 reads `--window-light` and `--window-dark` from pilot-ui.css.
- Cost: M

#### D-12. Smaller items: the untested paste parser, and two virtualizers
- Kind: other / duplication
- Severity: low
- Evidence:
  - **The paste parser.** app.js:3808-3851 `csvFields` and `pasteRows` (an RFC 4180-style reader, tab detection, heading-line skip) appear in no test by name. The engine's `edit` re-validates every field, so no rule is bypassed.
  - **Two row virtualizers** (P279): app.js:3111-3333 (`editorWindow`, 143 lines, variable heights, spacer rows) and pages.js:1815-2075 (fixed-height absolute rows). Both carry their own window arithmetic: `editorSpan` and `editorPins` against `pagesWindow` and `pagesOver`.
- Decision rows checked: P279, and decision 176's row on the editor's paste behaviour. Verdict: the parser is **accidental** (untested); the two virtualizers are **deliberate** (the editor's rows vary in height and hold inputs, per app.js:3112-3121).
- Proposed seam: a node probe test for `pasteRows` (tab, CSV with quotes, the heading-line skip, short rows) using `run_shell`. Optionally, share the pure span arithmetic as one `virtualSpan()` in pages.js.
- Behaviour risk: none.
- Cost: S

### Looks wrong, is deliberate (leave alone)
- main.js types defaults for wording and protocol constants the engine owns: `shellSays`, `DEFAULT_MENU_WORDS`, `PROGRESS_KEY`, `HELD_READING_COMMANDS`, `ENGINE_LINE_MAX`, `ENGINE_PAYLOAD_MAX`, `RESIDENT_FLAG`, `ENGINE_END_KEY`, `TRACKER_TIMEOUT_MS`. Each is pinned to Python by test_single_source.py or test_shell_menu.py (decisions 193 and 176; P276).
- `NOT_SET_UP`, `NOT_SET_UP_MAC` and `MAC_FLOOR` are sentences typed in main.js because they are said before any Python can run (SPEC-mac R6).
- `el()` with an attribute allowlist and no `innerHTML` anywhere (decision 137; guards at test_shell.py:631 and test_single_source.py:566).
- The one `keydown` listener in app.js hands keys to `shellKey` and `pagesKey` (P76).
- `openable` only grows during a session (decision 188). The comment at main.js:166-178 explains that saying a path once too often is safe.
- shell.js's early `firm` and `firm-last` go through `window.tracker.call` plus `takeReply` rather than `call()`, because `call()` needs the vocabulary that the list brings (P221, P228, P229; shell.js:336-343).
- A read the engine lost is retried once and a write never is (P220, P276; main.js:577-591).
- pilot.js `maxlength="200"` equals `SIGNED_BY_LONGEST`, pinned (test_single_source.py:5347; prior audit V9).
- Name ordering is approximated in Python against `Intl.Collator` (firm_pages.py:39-48, P278, Jason's question E), with a shared sample in tests/samples.py.
- devtools only in an unpackaged run (decision 176).
- The two virtual-list implementations (P279; D-12).
- style.css is unedited and overridden, until P160's fold (P51, P67; D-11).

### Cross-slice notes
- tracker/api.py: `_state` builds `fed_once` (3148) but does not send it, and the renderer re-derives it (D-3a). The firm row counting (5985-5994) and `file_group` (3092) are twinned by `pagesTally` (D-3b).
- tracker/firm_pages.py: `_taxpayer` (292) and `CELLS` (85-92) are twins of pages.js code, tested separately with different cases (D-3c, D-3e).
- tests/test_single_source.py (5,348 lines) mixes single-source text pins with behavioural tests of main.js's engine (4956-5150). main.js has no test file that owns it by name.
- tools/repo_map.py and docs/repo-map.curated.json draw no edges between renderer files, so the global coupling in D-2 is invisible to the map. test_layers.py has no JS layer table.
- tracker/resident.py's framing constants are mirrored in main.js (pinned). Any change to the resident protocol must touch main.js:678-691.
- pilot/DECISIONS.md: P7 and P10 are still worded as standing rules, but P21, P40, P58, P67 and P253 relax them and P160 removes their reason. A row retiring or rewording them would stop the next agent from treating them as binding.

---

## Slice E: the cross-cutting guards, tests, tools and build

*Questions put to this slice: (Q1) which tests pin exact source text; (Q2) how much the suite tests through private names; (Q3) duplicated fixtures; (Q4) whether anything measures size, complexity or types, and what a type checker would find; (Q5) what a refactor needs from the suite to be safe; (Q6) duplication between the Windows and Mac kits and build scripts.*

Scope measured: `tests/` (65 files, 94,985 lines, 3,626 `test_` functions before parametrisation), `tools/` (7 files, 4,317 lines), the root build and setup scripts, `pilot/wintest`, `pilot/mactest` and `.github/workflows`. Measurements came from throwaway AST and regex scripts in the scratchpad (`audit/e/*.py`). The type-checker numbers come from the `mypy` 2.3.1 binary that was already on this machine (`/root/.local/bin/mypy`). Nothing was installed. Its cache went to the scratchpad, and `git status` was clean before and after the run. The suite (95k lines) is 1.56x the size of `tracker/` (60.7k lines).

### Module table

In this table "Own test file" means, for a test file, **the module it owns and that module's line count**. For a tool it means the tool's own test file. Fan-in counts the test and tool files that import the file. Fan-out counts the `tracker`, `tests` and `tools` modules it imports. Type-hint share is the share of functions with at least one annotation.

| Module | Lines | Top-level defs | Longest function (lines) | Fan-in | Fan-out | Own test file (lines) | Type-hint share |
|---|---|---|---|---|---|---|---|
| tests/test_api.py | 11,751 | 513 (437 tests) | test_the_renderer_gets_its_vocabulary_from_the_api (102) | 3 | 42 | tracker/api.py (6,810), ratio 1.73 | 33/589 |
| tests/test_filer.py | 10,227 | 409 (339) | test_a_hand_over_killed_at_every_point_... (78) | 5 | 35 | tracker/filer.py (7,878), 1.30 | 18/469 |
| tests/test_shell.py | 8,823 | 358 (326) | test_the_harness_stub_replies_have_the_shape_of_the_engines (83) | 1 | 10 | app/renderer JS (10 files, 10,955 total) | 34/363 |
| tests/test_runner.py | 5,909 | 264 (215) | test_no_byte_of_a_damaged_document_reaches_... (86) | 2 | 33 | tracker/runner.py (3,652), 1.62 | 26/347 |
| tests/test_store.py | 5,692 | 231 (174) | admission_closure (60) | 0 | 17 | tracker/store.py (4,143), 1.37 | 25/259 |
| tests/test_single_source.py | 5,348 | 233 (196) | test_the_renderer_types_no_vocabulary_of_its_own (83) | 1 | 36 | (cross-language guard) | 40/243 |
| tests/test_content_check.py | 2,931 | 121 (96) | test_no_page_starts_past_the_safety_stop_... (96) | 6 | 22 | tracker/content_check.py (2,505), 1.17 | 12/144 |
| tests/conftest.py | 1,370 | 56 (8 autouse fixtures) | real_places (71); office_shaped_copy (64); refuse_what_windows_refuses (56); an_app_folder_of_its_own (48); make_engagement (46) | 34 | 21 | (shared) | 30/70 |
| tests/samples.py | 566 | 19 | cfb_bytes (86); build_samples (65); build_scratch_root (39) | 19 (+ pilot/wintest/make_samples.py) | 7 | (shared) | 22/22 |
| tests/test_layers.py | 1,021 | 50 (31) | spellings (57); visit (44) | 2 | 1 | (guard) | 22/53 |
| tests/test_repo_map.py | 884 | 77 (68) | repo (41) | 0 | 0 | tools/repo_map.py (1,234), 0.72 | 3/77 |
| tests/test_tripwire.py | 669 | 27 (23) | test_a_python_child_is_judged_by_... (38) | 0 | 11 | tests/tripwire/sitecustomize.py | 4/27 |
| tests/test_errors.py | 1,046 | 62 (39) | test_a_caught_errors_words_reach_no_console_during_a_pass (35) | 0 | 19 | tracker/errors.py (253), ratio 4.13 | 21/68 |
| tests/test_build.py | 1,309 | 78 (53) | test_ci_never_fires_per_commit (61) | 0 | 13 | build scripts and workflows | 25/79 |
| tests/test_pilot.py | 986 | 63 (50) | test_the_sample_pile_holds_a_macro_workbook_... (40) | 1 | 6 | pilot kits and renderer | 16/66 |
| tests/child_readers.py | 259 | 21 | a_photo_open_that_never_finishes (17) | 4 | 5 | (shared) | 21/24 |
| tools/repo_map.py | 1,234 | 46 | render_markdown (123); build (102); derive_node (68); validate_curated (53); parse_python_full (44) | 3 | 0 | test_repo_map.py (884) | 47/47 |
| tools/backtest.py | 704 | 31 | score (78); route_corpus (44); main (28) | 5 | 8 (+ tests.test_real_corpus at call time) | test_backtest.py (446) | 28/29 |
| tools/reader_bench.py | 710 | 33 | run_bench (50); measure (34); main (28) | 3 | 9 (7 private names of backtest) | test_reader_bench.py (764) | 30/32 |
| tools/vocab_report.py | 620 | 25 | render_markdown (77); report (63); real_documents (45) | 5 | 9 (+ 3 test modules at call time) | test_vocab_report.py (411) | 23/23 |
| tools/learned_keywords.py | 501 | 18 | render (61); main (42); collect (41) | 2 | 5 | test_learned_keywords.py (383) | 19/19 |
| tools/lockfiles.py | 443 | 19 | audit (49); check (42); main (37) | 4 | 0 | test_lockfiles.py (375) | 18/18 |
| tools/gpu_pack.py | 105 | 4 | main (17) | 1 | 0 | test_gpu_pack.py (74) | 3/3 |

Annotation coverage, with every parameter and the return annotated: `tracker/` 1,574 of 1,706 functions (92%), `tools/` 159 of 171 (92%), `tests/` 343 of 5,037 (6%). The tools hold no module-level mutable state: no `global`, no cache, and only two constant tables. The only `global` in the suite is `tests/child_readers.py:190 _SERVED`.

### Findings

#### E-1. A large share of the suite pins exact source text and breaks when code moves
- Kind: other (tests coupled to how the source is spelled)
- Severity: high
- Evidence (question 1):
  - **288 tests (7.9% of 3,626)** read a code file by path and assert on its text. Another 51 do the same with a document.
  - The worst offenders:

    | Test file | Tests that pin code text | Tests in file |
    |---|---|---|
    | test_single_source.py | 100 | 196 |
    | test_shell.py | 83 | 326 |
    | test_api.py | 25 | 437 |
    | test_pilot.py | 23 | 50 |
    | test_build.py | 13 | 53 |
    | test_pilot_ui.py | 6 | 13 |
    | test_shell_menu.py | 6 | 48 |

  - The most-pinned files: `app/renderer/app.js` (121 references), `app/main.js` (52), `shell.css` (47), `index.html` (63), `pages.js` (26) and `shell.js` (32).
  - JavaScript functions are lifted out of the source by their exact header: **176 calls in test_shell.py** (`run_shell`, `run_pages`, `js_function` and `lift`, :726-760, :4474) and **52 in test_single_source.py**. There are **7 separate brace-matching lifters**: test_api.py:5797 and :6161, test_pilot_ui.py:102, test_row_columns.py:394 and :761, test_shell.py:726, and test_single_source.py:1086 and :3562. Two of them are byte-identical: `test_row_columns._function_source` and `test_single_source._js_function`.
  - **26 tests read Python `tracker/` source.** 10 of them are in test_single_source.py. 18 scan the whole package, which is robust. The fragile ones slice a body out by signature or count call sites:
    - test_single_source.py:2265-2270 requires exactly three `_file_into(` call sites and slices `^def _file_it` by regex.
    - :3015-3017 slices from `"def _pass(ns, parser, reached: dict)"`, an exact signature.
    - :2618-2620 slices `def this_host` out of `locking.py`.
    - :934-936 requires that `def _extract_xlsx(` precede the one openpyxl import.
    - test_api.py:8039 requires that `inspect.getsource(api).count('["list"] =') == 1`.
    - test_shell.py:3815 requires the literal `'"client_type_forms": CLIENT_TYPE_FORMS,'` in api.py.
    - test_runner.py:5065 locates `_warn` by name.
    - test_fsio.py:358-359 compares the `getsource` of two functions.
- Decision rows checked:
  - 42 ("Every fact, one home": the cross-language literal pins). Deliberate.
  - 132 (`_file_into` is the one filing). The rule is deliberate, but pinning it with a call-site count is outgrown.
  - R22 / P250 (two copies of `full_sync`). Deliberate.
  - Verdict: the cross-language literal pins are **deliberate**. Pinning Python signatures, call-site counts and regex-sliced bodies is **outgrown**: the 1,000-line modules those tests were written against are now 4,000-8,000 lines and about to be split.
- Proposed seam:
  - A test-only `tests/source_pins.py` holding three things:
    - `py_function(module, name)`, which finds a function through `ast` by name in any `tracker/` module, so a moved function is still found.
    - `calls_of(name)`, which collects every call site across the package.
    - One `js_function(file, name)` that replaces the 7 lifters.
  - Rewrite the signature and offset pins above to name-based AST queries.
  - The JS node harness (`run_shell`, `run_pages_dom`, the 13 `run_*` helpers in test_shell.py) moves to `tests/node_harness.py`.
- Behaviour risk: none in the product, only in the tests. The pins that move are the ones listed above, the `SHELL_FILES` and `TITLE_FREE` lists in test_shell.py, and `ONE_TIME_STEP_DOCUMENTS` in test_single_source.py.
- Cost: M

#### E-2. Tests reach 232 private names, and the most-used ones are the real public surface
- Kind: leaky-abstraction
- Severity: high
- Evidence (question 2): across the suite there are **885 references to 232 distinct `_private` names in `tracker`/`tools`**, against about 11,266 public references (7.3%). That counts attribute access, `from x import _y` and `monkeypatch.setattr(x, "_y")`.
  - The five biggest test files:

    | Test file | Private refs | Distinct private names | Public refs | Private share |
    |---|---|---|---|---|
    | test_api.py | 155 | 47 | 1,833 | 7.8% |
    | test_filer.py | 69 | 32 | 1,255 | 5.2% |
    | test_shell.py | 21 | 5 | 42 | n/a: it tests JS, mostly through E-1's lifts |
    | test_runner.py | 50 | 24 | 815 | 5.8% |
    | test_store.py | 155 | 40 | 1,412 | 9.9% |

  - Private reach by module: api 193, store 112, content_check 87, filer 84, ocr 79, locking 66, settings 62.
  - The names reached most often:
    - `api._vocab` 75 times, from test_api, test_shell and test_single_source.
    - `api._state` 35.
    - `store._engagement_row` 35.
    - `store._refuse_a_malformed_line` 25.
    - `content_check._ocr_pdf` 21 and `_ocr_image` 20.
    - `settings._HELD` 20, a module global that tests set directly.
    - `filer._do_op` 16.
    - `scheduling._schtasks` 14, captured at load time in conftest.py:273.
    - `content_check._CHILD_READER` 14.
  - test_api.py:8043 writes `api._RUNNING["command"]`, a module-level dict at api.py:394.
- Decision rows checked: I grepped ROADMAP and DECISIONS for "private", "underscore" and "test file" and found no row on test access to private names. Decision 42 calls `_vocab()` the renderer's vocabulary, which makes it a published contract with a private name. Verdict: **accidental**.
- Proposed seam:
  - Before any module split, promote the de facto public names: `api.vocab()`, `api.state()`, `store.engagement_row()`, `store.refuse_malformed_line()`, `filer.do_op()`. Keep the old `_` alias for one session.
  - For a split module, keep the old module as a facade that re-exports what moved, so the 885 references keep resolving while the tests are retargeted file by file.
  - Replace monkeypatching of `settings._HELD` and `_HOLDING` with a context manager the module exports.
- Behaviour risk: tests that monkeypatch a private name on the old module stop intercepting once the call site moves, and they pass silently because the patch lands on an unused name. That affects `scheduling._schtasks`, `_launchctl`, `after_install._tmutil` (conftest.py:270-290), `content_check._ocr_*` and `_CHILD_READER`. The facade must forward a patch, or those tests must patch the new home.
- Cost: M

#### E-3. The test files mirror the god modules and defeat the "affected tests only" gate
- Kind: god-module
- Severity: high
- Evidence: six test files exceed 5,000 lines (test_api 11,751; test_filer 10,227; test_shell 8,823; test_runner 5,909; test_store 5,692; test_single_source 5,348), together 47.7k lines, half the suite. Decision 207 runs each changed module's own test file plus the own test file of every module that imports it. Any edit to `api.py` therefore reruns 11.7k lines, and any edit to a module imported by api (most of them) does too. Test-to-module size ratios: api 1.73, resident 1.72, runner 1.62, rollover 1.61, store 1.37, filer 1.30. errors.py is 4.13, from AST guards over the whole package.
- Decision rows checked:
  - P122 deferred splitting test_api.py "because every lane edits that file". Its measured 339 s for test_runner still holds.
  - 207/211 set the affected-tests gate.
  - Verdict: **outgrown**. One builder now does the work (CLAUDE.md, 2026-09-25), and the deferral's reason was lane contention, not design.
- Proposed seam: split each big test file along the module split it shadows, in the same commit, so `test_<module>.py` keeps meaning ownership for `tools/repo_map.py`'s owner edges. Examples: `test_api_commands_*.py` by command family, and `test_filer_handover.py`, `test_filer_room.py` and `test_filer_crash.py` from the existing section banners. Shared helpers go to E-4's modules first.
- Behaviour risk: `repo_map` derives "tested by" from file names, so `docs/repo-map.curated.json` and the map must be updated. `test_single_source` imports `run_pages` from test_shell, and test_shell imports `run`, `sample_engagement` and `scan` from test_api, so those must move before the split.
- Cost: M per big file

#### E-4. Shared test helpers live in test modules: 24 files import from 14 other test files
- Kind: duplication
- Severity: medium
- Evidence (question 3):
  - **Cross test-module imports**, not counting conftest, samples and child_readers:
    - `test_scanner.text_pdf` is imported by **15** files.
    - test_page_rows takes 7 helpers from test_runner (`_run_now`, `_three_households`, `build_engagement`, ...).
    - test_containers and test_ocr take fixtures from test_content_check (`no_child_left`, `eventually`, `STOP_IN_TESTS`, ...).
    - test_runner, test_api and test_containers take helpers from test_filer.
    - test_shell takes helpers from test_api and test_pilot_ui. test_tour takes them from test_api and test_pilot. test_records takes `import_edges` from test_layers.
  - **Three different hand-built text-PDF writers**: samples.py:81 (lines), test_content_check.py:25 (one string), test_scanner.py:56 (pages and escaping). There is also `test_validators.write_pdf`, and `test_containers.pdf` at :95.
  - **Byte-identical helper bodies**: `_link_to` (test_door, test_filer), `cache_rows` (test_filer, test_store), `drop` (test_ledger, test_store, test_view).
  - **Near-identical fixtures**: `engagement` is defined in 11 files, eight of them a one-line `make_engagement(tmp_path, ITEMS[, household=...])`. `read(rel)` is defined in 5 files. `root` in 4, `a_pass` in 4, `cli` in 3.
  - **Effect on the gate**: decision 207's affected-tests rule never sees these edges. Changing `test_scanner.text_pdf` changes 15 files' fixtures, and only `test_scanner.py` reruns.
- Decision rows checked: none found. The samples.py docstring ("one pile, not two that can drift") is the stated intent and is not applied to the PDF writers. Verdict: **accidental**.
- Proposed seam:
  - `tests/samples.py` takes the one `text_pdf(path, text_or_lines, pages=1)` and `write_pdf`.
  - `tests/builders.py` takes `drop`, `cache_rows`, `_link_to` and `original_at`, plus a parametrised `engagement` fixture factory.
  - `tests/children.py` takes `no_child_left`, `eventually` and `running`.
  - `tests/node_harness.py` takes the JS runners.
  - Test files then import only from non-test modules, which `repo_map` already labels "exercised by".
- Behaviour risk: the three PDF writers emit different bytes, and tests pin counts and sizes against them. The samples.py writer pads 8 KB "realistic file size". Keep each variant as an option rather than unifying the bytes.
- Cost: S-M

#### E-5. A dev-only type checker would find about 200 real errors on its first run
- Kind: weak-typing
- Severity: medium
- Evidence (question 4):
  - **Nothing measures function size, complexity or type coverage today.** Ruff selects `E, F, B, UP, I` only (pyproject.toml); there is no C90 or PLR09 rule and no mypy, pyright or coverage tool. The gate (gate.yml) runs pytest, ruff, the map check, the vocab check and `node --check` on 3 files.
  - Dead code at the module level is clean: a scan of `tracker/` found 0 top-level definitions referenced nowhere or only by tests.
  - I measured with the mypy already on the machine rather than estimating:
    - Default mode, `--python-version 3.11`, stops at 16 import errors because the readers have no stubs here (`pdfplumber`, `pypdfium2`, `rapidocr`, `cv2`, `numpy`, `PIL`, `pypdf`, `olefile`, `openpyxl`). It also stops on a blocking path error ("tools/backtest.py found twice").
    - With `--explicit-package-bases --ignore-missing-imports`: **209 errors in 31 files**. By category: attr-defined 67, arg-type 61, union-attr 18, assignment 18, return-value 9, operator 9, index 9.
    - About 9 are platform false positives (`ctypes.WinDLL`, `fcntl.F_FULLFSYNC`).
    - Most of the rest are Optional values used without narrowing (filer.py:634, :1209-1220 and :3531-3578; locking.py:1388-1409; progress.py:248) and parameters typed `object` then read as records. There are 26 `: object` annotations in records.py, and the message `"object" has no attribute "path"` appears 12 times.
    - By file: filer 51, api 24, store 16, scaffold 13, ocr 10, rollover 9, content_check 9.
  - Annotation coverage is already 92%, so the checker has real annotations to check.
- Decision rows checked: no row on type checking (grepped mypy, pyright, typing, annotation). Verdict: **accidental**.
- Proposed seam:
  - Add mypy as a dev-only, hash-locked requirement (`requirements-dev.lock`) and leave it out of the frozen build.
  - Configure it in `[tool.mypy]`: `files = tracker, tools`, `explicit_package_bases`, `ignore_missing_imports` for the eleven reader packages, and `platform` overrides for the ctypes and fcntl blocks.
  - Gate on "no new errors" against a committed baseline count, then burn the baseline down module by module, starting with filer, api and store before they are split.
  - Why the standard library cannot do this: Python has no static checker. `typing` only declares; nothing verifies it.
- Behaviour risk: none at run time. `test_layers.ALLOWED_THIRD_PARTY` and `test_build`'s lock tests must learn that a dev lock exists and is never installed into a build.
- Cost: S to add with a baseline, M to burn down

#### E-6. conftest.py is 1,370 lines of nine unrelated concerns with 8 autouse fixtures
- Kind: mixed-concerns
- Severity: medium
- Evidence: conftest.py holds these concerns:
  - Isolation and data home (152-260).
  - Platform fakes: the floor's `platform`, `on_a_mac`, `AMac`, `FakeLaunchd` and `FakeTmutil` (261-360, 410-510).
  - Scheduler fakes (362-409).
  - The firm-cache fill recorder (512-540).
  - Test-cache guard (539-570).
  - Builders: `make_engagement`, `sort`, `sort_all`, `refuse_what_windows_refuses`, `path_setting` (598-845).
  - The two agreement oracles (844-917).
  - Seeding helpers (918-975).
  - The tripwire and xdist session hooks (976-1290).
  - The office-shaped copy (1292-1370).

  34 test files import it by name, besides pytest's implicit load. It captures private module functions at load time (`REAL_SCHTASKS = scheduling._schtasks` and the three like it).
- Decision rows checked: 185 (the suite never sees a real root; the tripwire), 89 and 91 (the view agreement), 101/102 (the store agreement). The guards themselves are **deliberate**. Keeping them all in one file is **accidental**.
- Proposed seam: `tests/conftest.py` keeps only `pytest_plugins = ["tests.plugins.isolation", "tests.plugins.tripwire_session", "tests.plugins.agreement", "tests.plugins.fakes"]` and re-exports the builders. `tests/builders.py` holds `make_engagement`, `sort`, `seed_*` and `named_page`, shared with E-4.
- Behaviour risk: test_tripwire.py:362 special-cases `path.name == "conftest.py"`, so it must accept the plugins folder. The tripwire must still arm in `pytest_configure` before collection, and plugins listed in `pytest_plugins` do load before collection. The 34 `from tests.conftest import ...` lines keep working through re-exports.
- Cost: S

#### E-7. Refactor-safety nets: what exists, and the three seams that lack a recorded characterisation
- Kind: other
- Severity: medium
- Evidence (question 5). These already serve as characterisation tests:
  1. conftest's autouse `the_view_agrees_with_the_readers` (871) and `the_store_agrees_with_the_record` (900). After every test they re-render the view and compare bytes, and rebuild the store from the record and compare it. This is the strongest net for splitting view, store, ledger and records.
  2. test_catalog.py's 343 typed `CASES`/`XLSX_CASES` rows, each with its decision (decision 70), plus test_irs_forms' corpus walk. These cover splitting router, content_check, templates and manifest.
  3. test_api's `run(capsys, *argv)` (:111) drives `api.main` argv-to-JSON exactly as main.js does, in 437 tests. test_shell's `test_the_harness_stub_replies_have_the_shape_of_the_engines` holds the JS-side stub to the engine's reply shape. These cover splitting api.
  4. test_runner's whole passes over `samples.build_samples` and test_filer's kill-at-every-point tests (e.g. `test_a_hand_over_killed_at_every_point_...`). These cover runner and filer crash-consistency.
  5. test_layers' import-direction table, for any module move.

  The gaps:
  - **(a)** No recorded snapshot of the reply schema. Tests poke inside `_vocab()` 75 times instead of comparing it to a recorded key tree.
  - **(b)** No golden output of one full pass over the fabricated sample pile (index rows' decision, reason code and relative destination; record event kinds in order; the status page without its clock).
  - **(c)** `docs/backtest-baseline.json` records `agreement: null, documents: 0`, so CLAUDE.md's rule "no routing change may lower the baseline" has nothing to compare against.
- Decision rows checked: 70 and 71 (cases and the real-document harness; the baseline waits for the office run). 89/91 and 101 (the agreement oracles). Verdict: the nets are **deliberate**. Gaps (a) and (b) are **accidental**. Gap (c) is deliberate until the office runs it.
- Proposed seam: `tests/golden/` holding `vocab.keys.json`, `replies.<command>.keys.json` and `pass.samples.json`, all built from `tests/samples.py`'s fabricated pile only. Add one test, `test_a_pass_over_the_sample_pile_matches_its_recording`, with a `--record` switch that rewrites the files. This keeps every standing rule: no client data and no generative reading, because it uses the same fabricated pile the suite already uses.
- Behaviour risk: a golden file pins wording, so it must store reason codes and keys and leave out sentences, or it becomes another E-1.
- Cost: M

#### E-8. The location-keyed guards a module split must edit in the same commit
- Kind: tight-coupling
- Severity: medium
- Evidence: these pins name a file or a function, not a behaviour:
  - test_layers.py has **18 exact import-set asserts** (e.g. :394 `load["store"] == {"checkpoint", "ledger", "locking", "records"}`, :1012 `load["resident"] == {...}`, :1019 `importers of firm_pages == ["api"]`) and the `LAYERS` table (:124-160).
  - `ALLOWED_SPELLINGS` (:766) has 8 entries keyed by (file, function).
  - `SPELLING_OWNERS = ("tracker/layout.py", "tracker/door.py")` (:781).
  - test_fsio.py:346 requires callers to equal `[("fsio.py","full_sync"),("locking.py","full_sync")]`.
  - test_runner.py:4478 requires `passing == ["api.py","runner.py"]` (the files that say `follow=False`).
  - test_single_source.py:933 (`openpyxl` only in `tracker/content_check.py`) and :2617 (`platform.node` only in `tracker/locking.py`).
  - test_vocab_report.py:241 names `tracker/templates.py`.
  - test_errors' "no module but settings attaches a log file" (:321).
  - `docs/repo-map.curated.json` (529 KB, 144 nodes, 138 edges) keys curated nodes by path.
- Decision rows checked: 101, 103, 104, 120, 159, 188, P276, P278 (each pins one import set); R22 (full_sync); 186 (`follow=False`). Verdict: **deliberate**, and the reasons still hold. This is listed because it is the price of every proposal in slices A to D.
- Proposed seam: no change to the rule. Let a pin name a module family where the decision allows it, e.g. `store` plus `store_*` for the store's import set, so that splitting `store` into `store` and `store_admission` keeps decision 101 without rewriting the assert. Each split proposal should carry a pin-move checklist naming the lines above.
- Behaviour risk: loosening a set to a family could admit a new upward edge, but `test_no_load_time_import_points_to_a_higher_layer` still catches that.
- Cost: S

#### E-9. The tools reach each other's private names and import test modules for their data
- Kind: tight-coupling
- Severity: low
- Evidence:
  - tools/reader_bench.py:133-146 imports **7 private names from tools/backtest.py**: `_corpus`, `_document_path`, `_harness`, `_linked_under_a_neutral_name`, `_outside_the_repository`, `_temp_pointed_at`, `_unknown_catalog`.
  - At call time, tools import test modules:
    - backtest.py:210 imports `tests.test_real_corpus`.
    - vocab_report.py:221 imports `tests.test_irs_forms.EXPECT`, :247 `tests.test_real_corpus`, and :309 `tests.test_catalog.CASES, XLSX_CASES`.
  - Tests import tools in turn: test_layers, test_catalog, test_single_source and test_api.
  - `tracker/ocr.py` names reader_bench in a docstring only.
- Decision rows checked: 70 (the cases carry their decision and the coverage report reads them) and 71 (the harness). Reading the case tables is **deliberate**. Reaching private names across tools is **accidental**.
- Proposed seam: `tools/corpus.py` takes backtest's corpus-and-harness half as public names, imported by backtest and reader_bench. `tests/cases.py`, a data module with no tests, takes `CASES`, `XLSX_CASES` and `EXPECT`, so that the tools and test_catalog/test_irs_forms all read data rather than a pytest module.
- Behaviour risk: test_catalog uses `-k d67`-style ids built from `CASES` (decision 70), and those ids must stay identical. `docs/vocab-coverage.*` must be rebuilt (test_vocab_report fails on a stale report).
- Cost: S

#### E-10. Windows and Mac scripts duplicate their steps by design; one unpinned copy and one gap in the Windows build
- Kind: duplication
- Severity: low
- Evidence (question 6):
  - **The pairs**: Setup.bat (89) with setup.command (124), Start App.bat (48) with start.command (68), Build App.bat (118) with build-mac.sh (200), and run_checks.ps1 (348) with run_checks.sh (488). Each pair carries the same steps in the same order: venv `--clear`, the two hash-checked installs (169), `npm ci`, `lockfiles.py stamp`, `after_install --reason setup` last. They also print the same sentences.
  - **What test_build.py pins about the pairs**: the sentences equal their Python owners (:1302), the steps run in this order (:858 and :1107), the Python floor equals pyproject.toml's (:1129), and every install is hash-checked (:660).
  - **Duplicates within one language**:
    - The PATH-cleaning block is copied into all 4 bash scripts and pinned by `test_the_path_block_...` (:1074).
    - `NoDefaultCurrentDirectoryInExePath` appears in 5 .bat files and is pinned by :706.
    - The data-home name list is in `.github/workflows/build.yml:206` and `build-mac.sh` step 6. Both are pinned to the Python constants through `test_build.data_home_names()` (:134-169, :171 and :1270).
  - **Divergence**: `Build App.bat` builds the Windows package the office carries on a USB stick, and it does not check that the package holds no store, log or settings. Only the CI `build.yml` does. `build-mac.sh` checks locally, and also refuses an uncommitted tree; the Windows script records "plus uncommitted changes" and continues.
  - **Unpinned copy**: `$ProductName = "Tax Document Console"` is typed in `pilot/wintest/run_checks.ps1:29` and `uninstall_checks.ps1:10`. The product-name single-source test (test_single_source.py:39-50) does not list `pilot/wintest/*.ps1` (only `$EarlierName` is pinned, in test_pilot_installer.py:162).
  - The test-file resolver (P200 N8) is implemented once in PowerShell and once in bash, and each is tested separately in test_pilot.py.
- Decision rows checked:
  - SPEC-mac R16 ("Three scripts for the batch files"), P254 (mactest mirrors wintest), P28 (the wintest kit) and P200 (the resolver). The pairs are **deliberate**.
  - 186 and SPEC-mac R17 step 6 (no data home in a package). The missing local Windows check is **accidental**.
  - Decision 42 (one home for the product name). The unpinned PowerShell copy is **accidental**.
- Proposed seam:
  - Leave the pairs alone. A sourced `lib.sh` would cost the scripts their standalone double-click behaviour, for about 10 lines each.
  - Add the data-home step to `Build App.bat`, or have it call the same PowerShell block build.yml runs, so the list stays in one place on Windows.
  - Have run_checks.ps1 and uninstall_checks.ps1 read the product name from `app\package.json` as `Build App.bat` does, or add both to the list in `test_the_product_name_has_one_home`.
- Behaviour risk: test_build pins the step numbering `[1/4]` to `[4/4]`, and a new Windows step renumbers it.
- Cost: S

#### E-11. The gate syntax-checks 3 of the 10 Electron JS files
- Kind: other
- Severity: low
- Evidence: gate.yml's last step runs `node --check` on `app/main.js`, `app/preload.js` and `app/renderer/app.js` only. It skips `pages.js`, `shell.js`, `sheet.js`, `tour.js`, `tooltip.js`, `pilot.js` and `pilot-content.js`. Those files are exercised only through E-1's function lifts, which run single functions, not the whole file. A syntax error outside a lifted function in `shell.js` would pass the gate.
- Decision rows checked: 207/211 (the gate's contents). No row names the three. Verdict: **accidental**.
- Proposed seam: `for f in app/*.js app/renderer/*.js; do node --check "$f"; done` in gate.yml, plus the same loop as one test in test_build.py, so the local gate covers it too.
- Behaviour risk: none.
- Cost: S

### Looks wrong, is deliberate (leave alone)
- `fsio.full_sync` and `locking.full_sync` are two identical copies, pinned by `inspect.getsource` equality (test_fsio.py:349-359). This is the price of the layering: SPEC-mac R22 and P250.
- test_single_source reads JS, .bat, .yml and .css text to pin the literals that cross the language line (decision 42).
- The tools import `tests.test_catalog`, `tests.test_irs_forms` and `tests.test_real_corpus` for the case tables (decisions 70, 71).
- The Windows and Mac script pairs repeat each other line for line (SPEC-mac R16, P254, P28).
- The data-home name list is spelled in build.yml and build-mac.sh and tied to the Python constants by a test (decision 186, R17).
- test_layers holds an exact import set per low module (decisions 101, 103, 104, 120, 159, 188, P276, P278).
- 8 autouse fixtures in conftest re-render every view and rebuild every store after every test (decisions 89, 91, 101, 185).
- The tripwire in `tests/tripwire/sitecustomize.py` and the conftest session hooks fail the whole session on any reach for a real place (decision 185).
- `docs/backtest-baseline.json` records no agreement until the office run (decision 71).
- test_api.py has not been split yet (P122 deferred it; finding E-3 argues this is now outgrown).
- Modules keep a `__main__` CLI only when something runs it (P233). Every tool has one, and each is run by a test or the runbook.

### Cross-slice notes
- api slice: `api._vocab`, `_state`, `_with_list` and the `_RUNNING` dict (api.py:394) are what tests and the renderer contract use. Rename them to public names before splitting api.py (E-2). mypy finds 24 errors in api.py.
- store slice: `store._engagement_row` (35 test references) and `_refuse_a_malformed_line` (25) are de facto public. mypy finds 16 errors in store.py, including `_Connection | None` returned as `_Connection` (store.py:2673) and `GuardedConnection` returned as `_Connection` (checkpoint.py:379).
- filer slice: mypy finds 51 errors in filer.py, almost all unnarrowed Optionals (filer.py:634, 1209-1220, 2423, 2540, 2995, 3531-3578). A split of filer moves `_do_op`, `_move_whole`, `_record`, `_review_copy_path` and 28 more private names that test_filer reaches.
- records slice: 26 parameters annotated `: object` in records.py. mypy reports `math.isfinite(object)` at records.py:1698 and :1706. Most of the 67 attr-defined errors package-wide are `object`-typed record parameters.
- settings slice: `_HELD` and `_HOLDING` are module globals that 20 and 9 test references set directly (test_runner, test_settings). This is global state with a test-only write path.
- content_check/ocr slice: tests monkeypatch `_ocr_pdf`, `_ocr_image`, `_CHILD_READER` and `_read_in_a_child` (65 references). Moving them silently disarms those patches (E-2's risk).
- app slice: 7 brace-matching JS function lifters in the tests depend on exact function headers in `app.js`, `shell.js` and `pages.js`. Renaming or reshaping a JS function breaks about 228 test call sites for non-behavioural reasons (E-1).
