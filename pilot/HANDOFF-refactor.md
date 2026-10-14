# Refactor handoff: paused after P3.2

**Paused 2026-10-14 at Jason's word** ("pause at a good spot and leave notes so you can pick it up next week").
This file is the whole hand-over. A new session reads it, `CLAUDE.md`, [`PROMPT-refactor.md`](PROMPT-refactor.md)
(sections 1 and 2) and the ledger ([`SPEC-architecture.md`](SPEC-architecture.md) section 13), and nothing of an
earlier session's transcript.

## Where it stopped

- **Branch** `claude/quirky-johnson-22edtv`, head `969bfd6` ("SPEC-architecture P3.2: landed"), pushed. The tree is
  clean and no job is in flight: nothing was half built when the loop paused.
- **Landed on the branch:** tranche 1 (J1-J6), phase 2 (P2.1-P2.14, no facade left), the phase 3 SPEC
  ([`SPEC-architecture-p3.md`](SPEC-architecture-p3.md), `6cfb1c9`), **P3.1** (`de3da78`, landed `21322e3`) and
  **P3.2** (`82960bd`, `c450650`, landed `969bfd6`). Each has its row in the ledger.
- **Nothing is on `main`.** Landing on `main` is a person's step, and no pull request is open: Jason has not asked
  for one. When he does, CLAUDE.md's cost rules apply (open it as a draft, mark it ready once).
- **Next: P3.3**, base `969bfd6`: one function per event family by explicit `if/elif`, and the admission pin sees a
  class's members (SPEC-architecture-p3 section 4, P3.3). Then P3.4 to P3.9 in order, then phases 4 to 7, each with
  its own SPEC written when the phase before has landed.

## What did not survive the session, and where it is now

The cloud container is reclaimed when a session ends. The loop's working folder (`ORCH`: the board, every job's
`before.txt`, handoff and review files) lived in the session's scratch folder, outside the repository, as
PROMPT-refactor 1.6 says it should. It is gone. What it held that matters is here:

| What | Where it is now |
|---|---|
| What each job did, its rounds, commits and what it owes | the ledger, SPEC-architecture section 13, and the commits |
| The board (status, notices, every job's messages) | the board page, below; and its status table, appendix A |
| The carry-forward list (open items found outside a job's scope) | section "Carry-forward", below |
| The two loop scripts (one job; one phase SPEC) | appendices B and C |
| The board page's sync script | appendix D |
| What P3.2's builder measured for P3.3 onward | section "For P3.3", below |

**The board page** is https://claude.ai/artifact/PGTu5QL1KKSzZ2DMW125oS (Jason's monitor). It is a claude.ai artifact,
so it outlives the container. Its store holds collection `board` (documents `status` and `notices`) and collection
`threads` (one document per job, with every message and working file the sync sent). Read it with the `ArtifactData`
tool (`list` on `board` and on `threads`). Versions at the pause: `board/status` 55, `board/notices` 31; threads J1 5,
J2 12, J3 12, J4 23, J5 8, J6 8, P2 15, P2.1 4, P2.2 4, P2.3 4, P2.4 3, P2.5 3, P2.6 4, P2.7 3, P2.8 4, P2.9 3,
P2.10 3, P2.11 2, P2.12 4, P2.13 5, P2.14 5, P3 6, P3.1 2, P3.2 2.

## Resuming, step by step

1. **Confirm the branch.** `git fetch origin claude/quirky-johnson-22edtv`, check out that branch, and confirm
   `git log -1` is `969bfd6` or a later commit a person added. If the branch's pull request has been merged since,
   follow the session's rule for a merged branch (restart it from `main`, keep the same name) before any new work.
2. **Build the two test interpreters** (the floor, 3.11, and the office's, 3.14) with `uv`, in the new session's
   scratch folder (`E` below). `--require-hashes` works with `uv pip`:

   ```
   uv python install 3.14
   for v in 3.11 3.14; do uv venv -q -p $v $E/py${v/./}; done
   for p in $E/py311/bin/python $E/py314/bin/python; do
     uv pip install -p $p --require-hashes -r requirements.lock
     uv pip install -p $p --require-hashes --no-deps -r requirements-nodeps.lock
     uv pip install -p $p --require-hashes -r requirements-dev.lock
   done
   ```

   The system Python has neither ruff nor mypy; always use these two. If a lock fails, HANDOFF.md's "Environment
   notes for cloud sessions" lists the fallback packages.
3. **Check the map:** `$E/py311/bin/python tools/repo_map.py check` must say current.
4. **Rebuild `ORCH`** in the new scratch folder: `ORCH/board/STATUS.md` from appendix A; `ORCH/board/NOTICES.md` from
   the page's `board/notices` document (its text), so the page's history is not overwritten; `ORCH/carry-forward.md`
   from the section below; empty `ORCH/board/threads/` and `ORCH/jobs/`.
5. **Rebuild the board sync** (only if the page is to stay live): appendix D as `<scratch>/board-sync/sync.py`, with
   `ORCH` at `<scratch>/orchestration` (the script reads `HERE.parent / "orchestration"`). Its `pushed.json` is gone:
   write one, `{"board/status": {"hash": "", "version": <the page's version>}, "board/notices": {...}}`, from the
   versions an `ArtifactData list` returns. The first `batch` then re-sends both with the right `if_version`. Old
   jobs' threads are not in the new `ORCH`, so the sync never touches them. Then `batch`, an `ArtifactData batch`
   with exactly the writes it prints, and `mark` with the versions returned.
6. **Save the loop scripts:** appendix B is the one-job loop, appendix C the phase-SPEC loop. Run them with the
   `Workflow` tool (`scriptPath`), with the arguments below. Each prompts its agents to read PROMPT-refactor, the
   board and the brief, so the brief does the steering.
7. **Write P3.3's brief** at `ORCH/board/threads/P3.3/000-orchestrator-brief.md`, in the form of the earlier ones
   (the page's `threads/P3.2` document holds P3.2's brief as an example). Re-measure every anchor P3.3 names at
   `969bfd6`: the admission now lives in `tracker/admission.py`, and the shifts are in "For P3.3" below.
8. **Launch P3.3** with appendix B: `job` "P3.3", `title` (the SPEC's), `spec` "pilot/SPEC-architecture-p3.md",
   `section` "P3.3", `tier` "opus", `base` "969bfd6", `repo` the checkout, `branch` "claude/quirky-johnson-22edtv",
   `orch`, `py311`, `py314` (absolute paths), and `extra` naming the brief and the SPEC lines to read. Run a Monitor on
   `ORCH/board/threads` for new `*report*.md` and `*question*.md` files (30 minutes, re-armed on expiry).
9. **Land each job** when a review is clean, by the checklist below. Then the next job, in the SPEC's order.

## The orchestrator's habits, learned the hard way

- **Landing checklist.** (1) every commit since the last landing is signed (`git cat-file -p <c> | grep -c 'BEGIN
  SSH SIGNATURE'` is 1) and touches nothing under `.github/`; push. (2) Add the job's row to SPEC-architecture section
  13 after the last row, six cells: Job, Tier, Rounds, Commits, Outcome, Owed to the office PC (P2.13's and P2.14's
  rows lacked the sixth until this hand-over). (3) `repo_map.py update` then `check`, ruff, and `test_layers`,
  `test_single_source` and `test_repo_map` under both interpreters. (4) A signed commit "SPEC-architecture <JOB>:
  landed", pushed. (5) Board status and notices, then the sync.
- **Commits are signed.** Never pass `--no-gpg-sign` or `commit.gpgsign=false`. Never force-push. A builder's commit
  can be pushed before its review: fixes go on top as new commits, and pushing this branch runs no CI.
- **The vocabulary trap.** An edit to any of `tools/vocab_report.py`'s `INPUT_PATHS` (templates, content_check,
  manifest, `tests/routing_cases.py`, `tools/corpus.py`, vocab_report itself) needs `vocab_report.py build`, then
  `repo_map.py update`, in the same commit. P3.7 edits manifest.
- **Known failure under 3.14:** test_api's `test_importing_the_api_opens_no_file_but_the_programs_own`. It fails at
  the base too; it is not a job's.
- **Baselines at `969bfd6`:** `typecheck.py check` 206 errors in 25 files (store 7); `patch_sites.py check` 760
  stand-ins on 45 modules; the map 353 nodes; `ADMISSION_PIN[5]` 241 parts, `ADMISSION_VERSION` 5, `SCHEMA_VERSION` 20.
- **Pytest:** one process per test file, in parallel, with `-p no:cacheprovider`; never the whole suite for a job
  that does not reach the engine (CLAUDE.md, "Test minimally").
- **A SPEC edit by script** must end with the file's write; one did not, and an hour went to edits that never saved.
  Confirm with `cmp` against a copy.
- **Questions.** An agent that stops with a `question` gets an `answer` file on its thread from the orchestrator, or
  Jason's word first when the decision is his. A question at the build is answered by running appendix B again (a
  fresh builder continues from the thread and the working tree); one at a review or a fix by running it with
  `resume` (`{round, open: [{f, tries}]}`), which skips the build and starts at that round's fixes. The phase-SPEC
  loop takes `start` and `answer` the same way.

## Owed to the office PC

None of this can run in the cloud. The ledger's last column is the record; gathered here:

- **J2 (optional):** `test_door`, `test_filer`, `test_containers`, `test_ocr` and `test_content_check` once on Windows,
  one process each.
- **J3, J4, J5, J6:** each row names its `pilot\wintest\run_checks.ps1 -Tests ...` list and hands-on steps (J5's built
  app on a made-up clients root; J6's installer build and the planted `app\settings.json`).
- **P2.12:** `tools/backtest.py run` and `check` against `docs/backtest-baseline.json`, and `tests/test_real_corpus.py`
  with `TRACKER_REAL_CORPUS` set.
- **P3.8, before it merges:** `python -m tracker.store "<the app folder>" verify "<clients root>"` with the P3.8
  build. It is read-only. If it names any household, the list goes to Jason before P3.8 merges
  (SPEC-architecture-p3 section 6).
- **Phase 4 needs the office backtest baseline first** (it owns the matcher).

## Open for Jason

- **P313's Q-B** (whether the re-send road's across-household park carries a shortlist) and **Q-F** (if unifying the
  room check would change a save's outcome): kept as today until his word. Q-B touches phase 4, Q-F phase 5.
- **P3.8's office `verify`** (above): its list, if any, is his before P3.8 merges.
- Q1 of phase 3 is answered ("a - the full rule", 2026-10-14) and written into the SPEC.

## For P3.3

From P3.2's builder (`threads/P3.2/002-builder-next.md` on the page), measured at `82960bd`. `c450650` then added one
line to store.py from 910 and two from 3200, and nothing to admission.py or the tests.

**tracker/admission.py** (new, 481 lines): docstring 1-54; imports 56-62; the `ADMISSION_VERSION` comment and constant
64-92; the KIND names 94-100; `StoreError` 103-104; the words 107-124; `_line_keys_problem` 127-148;
`_refuse_a_malformed_line` from 150.

**tracker/store.py**, against `21322e3`: unchanged to 203; +3 from 204; +13 from 208; -17 from 305; -25 from 357; -29
from 377; -406 from 1688 (then +1 from 910 and +2 from 3200 at `c450650`). Landmarks at `82960bd`: `CheckpointNotMade`
352, `StoreUnavailable` 372, `RULE_LIST_FIELDS` reads 1169 and 1548, `_admitted` 1659, `_apply` 1675, `record` 1821,
`_judge` 2329, `WouldDiscard` 2666, `check` 2818, `verify` 3418.

**tests/test_store.py** (4442 lines), against `21322e3`: -1 from 17; -13 from 2610; -1334 from 4111; -1361 from 4165;
-1380 from 5393. The local `import ast` is at 1106; `admission.ALSO_IN` at 1876 and 1879;
`test_an_event_carried_in_also_is_refused_in_the_wording_of_the_line_that_carries_it` (P3.4 moves it) at 4347. The
stand-ins on `store._refuse_a_malformed_line` are test_store 2663, 2681 and 4419, test_after_install 291 and test_api
11531; `patch_sites report` calls them "imported".

**tests/test_admission.py** (new, 1412 lines): the P3.2 re-pin comment 65-66; `ADMISSION_PIN` 67; version 5's dict from
860; `admission_closure` 1144; `admission_digests` 1209; the pin test 1216. The moved bodies still read `store.*`, and
the closure's default roots are still the store's names, until P3.9.

**Prose left for P3.8 and P3.9** (it names a moved name through the store, and is still true while store holds it by
import): records.py 851 and 1210 (`tracker.store._refuse_a_malformed_line`, in closure docstrings, so editing them
moves digests); bounds 10 and 62 and ledger 111 (the same name); after_install 86 (`store.ADMISSION_VERSION`);
docs/runbook.md 2753 (`tracker.store.MALFORMED_LINE`).

## Carry-forward

Open items a job found outside its own scope. Each phase's SPEC writer takes the items for its phase into its SPEC,
or says why not. The `ORCH/...` paths below named working files that no longer exist; each item is written to stand
alone. Phase 3's SPEC (section 2.2) has already taken the phase 3 items.

### Phase 6 (the shell)

From J3 (reviews 1 and 2, `ORCH/jobs/J3/review-1.md`, `review-2.md`):
- tour.js types `` `Step ${index + 1} of ${all.length}` `` on screen, and no typed-words guard reads the pilot's
  scripts (tour.js, pilot.js, pilot-content.js; test_pilot holds pilot-content.js's wording).
- Guards that still read app.js alone or a typed list of files, to be widened by claim:
  - test_single_source `no_status_chip` (`("app.js", "pages.js", "shell.js", "index.html")`);
  - test_single_source `types_no_colour` (app.js);
  - test_single_source `scan_buttons_label` (typed list);
  - test_single_source's `engagements_page` words (app.js);
  - test_single_source's `"Escape"` count (app.js);
  - several test_api pins that read app.js (around 2929, 2956, 3026, 3598 at 3bc63f8).
- `roll-household` is the one command the renderer sends that the commands guard never reads (app.js `call(...built)`
  in `rollHouseholdCall`). A guard could read the first literal of every array whose second element is
  `vocab.engagement_flag`.
- The error-text pass is structural: a future `toast(new Error("...").message)` would pass the typed-words guard.
- `stripped_js` assumes no string holds `//`; test_renderer_seams' `js_code` is a tokenizer-grade alternative.
- The no-typed-vocabulary guard matches whole words outside app.js and substrings in app.js; one rule for every
  script is a choice for phase 6.

### Any phase that moves a module (from J4's review 2, N4)

- `tools/patch_sites.py` reads only `monkeypatch.setattr`. `monkeypatch.setitem` is outside it: for example,
  `setitem(api.COMMANDS, ...)` in test_api and test_errors, and `setitem(sys.modules, ...)` in `tests/children.py`.
  A `setitem` on a dict is read where the dict is, so a move carries it with the dict. A later phase may want the
  tool to list them.

### Any phase that moves a module (from J4's review 6; Jason, 2026-10-14: land as it is)

`tools/patch_sites.py` names these four in its list of what it does not read. None occurs in the suite at
`4bb2b8f`; each was shown with a made-up case (`ORCH/jobs/J4/review-6.md`, F6.1-F6.4):
- bindings its test side does not model: a comprehension or class body as a scope, a walrus in a comprehension,
  except-as, a match capture, a star import (F6.1);
- a `tests/` helper imported by its bare name (`import children`), a second copy the tool takes for an outside
  library, so a stand-in on it passes unlisted (F6.2);
- a store through a value it does not follow (a parameter, `self`, a call's result), not seen as rebinding (F6.3);
- a store into `sys.modules`, while reads back through `sys.modules`, `import_module` and `importorskip` are
  followed (F6.4).

If a later phase tightens the tool, the measured options are in `ORCH/jobs/J4/round6-measure/` (board 019):
- the strict plain forms of ruling 018 rewrite 490 lines;
- with an import inside the test function counted as plain, 83;
- with F6.3 on the boundary list as well, 23 (66 once loops are written one line each).
Two points from that work hold whichever is chosen:
- the string form must check from its first part, as pytest reads each later part as an attribute;
- `type(folder)` in test_content_check cannot be named plainly without changing what it patches.

### Phase 6 (the shell), from J5's review 1 (`ORCH/jobs/J5/review-1.md`, notes)

- `fromMainWindow`'s comment in app/main.js says it refuses "another frame, a page the window was led to".
  `event.sender` is the same WebContents for every frame and across a navigation, so it cannot tell those apart.
  Nothing is exposed today: navigation is denied, and the preload runs only in the main frame. Reword it, or check
  `event.senderFrame`.
- `NOT_FROM_THE_WINDOW` is a sentence typed in main.js, not an API word.

### Any phase that adds or moves module state, from J5's review 1

- The register's derivation (tests/test_resident.py) does not see:
  - an alias of a module-level container;
  - a mutating method outside the SPEC's list;
  - a nested function's shadowing.

  Nothing is missed at `f1a6b4c`.
- `_restore_per_command` could bind the table's own fresh object in one rare case. No command does it today.

### Any phase, from J6's review 1 (`ORCH/jobs/J6/review-1.md`, notes)

- A mypy upgrade that counts more errors can only be taken by recording a fresh baseline. That is a deliberate
  raise, and `update` refuses it. It needs a rule (a decision row) before the first upgrade.
- `platform = "linux"` leaves the `sys.platform`-guarded Windows branches unchecked.
- gate.yml's pip cache key does not include `requirements-dev.lock`.
- `typecheck.py` prints "1 files" when one file has errors.
- Windows PowerShell 5.1 may report long paths as unreadable in `tools/check_package.ps1`. The owed office build run
  shows whether it does.

### The first phase that owes a Mac check, from the phase 2 SPEC (review 1; `board/threads/P2/003`)

- **B-10, one Mac probe.** Four "is this a Mac" probes stay: `settings.host_system`, `layout.on_a_mac`,
  `fsio._on_a_mac` and `locking._on_a_mac`. The fsio and locking copies are deliberate (SPEC-mac R22).
- **Joining `settings.host_system` to `layout.on_a_mac` needs a ruling on which seam a Mac-room test means.**
  - conftest's autouse `room_is_the_absolute_length` pins `layout.on_a_mac` off.
  - `stand_on_the_floor` and `a_mac` drive `settings.host_system`.
  - Joining them changes what `stand_on_the_floor` pins on a real Mac, and makes `test_tripwire.py:122`'s Mac
    branch dead.
  - It also changes the five `on_a_mac` tests: test_filer 6841 and 6891, test_layout 743 and 788, test_validators 100.
  - Build it only with a `pilot/mactest` run owed in the same phase. Audit severity: low.

### Phase 3 (the record), from the phase 2 SPEC writer (round 2, W5; `board/threads/P2/004`)

- **The admission pin does not see a class's members.** `admission_closure()` (test_store 3876 at `286b535`) records
  functions and constants of simple types.
  - `records.rule_row_fault` reads `Override.ALL` and `Override.RETIRED`. A change to `Override`'s members changes
    what the admission admits, but leaves `ADMISSION_PIN` as it is.
  - J1's guard (B-2) means to close exactly that kind of gap.
  - Widening the closure to class attributes read by the closure's functions is a test change, re-pinned under v5.
    Take it in phase 3's SPEC, which owns the store and the admission.

### Phase 6 (the shell), from P2.3's review 1 (`ORCH/jobs/P2.3/review-1.md`, notes N2 and N3)

- **Nothing holds the harness's stub to `tracker/replies.py` yet.** replies.py's docstring says "the harness's stub,
  the recorded replies (``tests/golden/``) and the JavaScript are held to it" (the SPEC's own words, 5.1 (6)), but at
  `378d8c9` only the recordings, the envelope, `shellFailure` and the failure kinds are checked. Phase 6 adds the check
  that holds `pilot/harness/app-stub.js`'s replies to the same types, which makes the sentence true; until then it is
  a claim about the target.
- **`shellFailure`'s `...extra` spread puts `progress` (and `killed`) at the top level of the main process's
  envelope**, and `Envelope` names neither. The engine's own envelope never carries them. Phase 6 either names them in
  a main-process type or says in replies.py why they are left out.

### Phase 3 (the record), from the orchestrator at P2.11's launch (`board/threads/P2.11/000`)

- **Six event types will be in ledger.py with nothing taking them:** `RowEvent`, `ScannedEvent`, `ReleaseEvent`,
  `KeywordEvent`, `HouseholdEvent` and `DraftEvent`. R2.11.1 requires them, but R2.11.2 types only the intent and
  rules writers. Phase 3's writers (B-4, `ledger.new(` out of the door) are where they get used, so phase 3's SPEC
  either gives each one a signature or says why it stays only a description. P2.11's handoff lists which of the six
  are still unused.
- **Some key constants may be `Final` after P2.11** (the brief allows it only for constants a typed function reads
  through). If phase 3 types more of the apply path, the same rule extends to it.

### Phase 3 (the record), from P2.11's builder (`board/threads/P2.11/001-builder-next.md`)

- **A defect: the admission does not hold a `released` line's `was` to any rule** (and the retired
  `handed_over_by_person` gets no branch). In a scratch copy, `{"event": "released", "key": "x.pdf", "was": ["not",
  "a", "place"]}` passes the gate, then `catch_up` fails with `StoreUnavailable: the database could not be used
  (SQLITE_ERROR)` instead of decision 187's "line N of the record is malformed". It fails loudly, but with the wrong
  sentence and the wrong recovery pointer.
  - The fix refuses what the gate admits today, so it raises `ADMISSION_VERSION` and re-pins (decision 209).
  - Phase 3's SPEC owns the store and the admission, so it takes this as a requirement, with a test that writes that
    line and expects the malformed-line refusal. Tell Jason in the phase 3 summary.
- **The event types' keys are held to nothing.** A phase 3 test can pin each `ledger` event type's keys to the
  `*_KEY` constants' values.
  - Read them with `typing.get_type_hints(T, include_extras=True)` and `get_origin(hint) is NotRequired`, never
    `__required_keys__`. Under `from __future__ import annotations`, a class-form `TypedDict` reports every key as
    required at run time.

### A tools job (any phase), from P2.11's builder

- **`tools/repo_map.py` reads exports and constants from `ast.Assign` only**, so an annotated module constant
  (`X: Final = ...`, `STANDING_RULES: tuple[...] = ...`) is missing from its node's derived `exports`/`constants`.
  - About 60 are missing today, five of them ledger's `Final` keys from P2.11.
  - Reading `ast.AnnAssign` with a value changes many nodes' derived facts at once, so it is a job of its own, with
    `test_repo_map` cases.

### Phase 4 (the sorting engine), from P2.12's review 1 (`ORCH/jobs/P2.12/review-1.md`, notes)

- **`tests/samples.py` is not in `tools/vocab_report.py`'s `INPUT_PATHS`,** though the typed cases in
  `tests/routing_cases.py` are built from its line makers. A change to a line maker can change what the report
  counts without making it stale, so `test_vocab_report` would not notice. The gap is older than P2.12, which only
  moved the cases. Phase 4 owns the matcher and the cases: add `tests/samples.py` to `INPUT_PATHS` with a comment,
  rebuild the report, and check that its counts are unchanged.
- **`tracker/hold.py` 42-44's wording** (P2.13 review 1, N3, cosmetic): "Before P2.13 pointed their readers here, it
  re-exported the public names" reads as history but sits in a paragraph about what the module does now. Reword it
  when a later job next touches hold.py. Do not open a job for it.
- **The router's "for one release" wording** (P2.14 builder, `threads/P2.14/002-builder-next.md`): router.py 154-156
  (docstring), 191-195 (the comment over the records import) and the router's curated note
  (`docs/repo-map.curated.json` 41) still say `Routing` and `EVIDENCE_CONTENT` are re-exported "for one release".
  The router reads both itself, so the row in test_records' `RE_EXPORTED` is not a shim. The first job that edits
  router.py (phase 4 owns the matcher) rewords all three to say so, and router.py 121's
  `tracker.content_check.Evidence` (P2.14 review 1, N1), which should name `tracker.records.Evidence`.
- **Two names still reached through the filer in tests** (P2.14 review 1, N2): `OTHER_DOCUMENT` and
  `PREPARED_DIR_NAME`, in four test lines (`ORCH/jobs/P2.14/review-1.md` names them). Neither is an index or record
  name, so P2.14 left them. Point them at their defining module when a later job next touches those test files.

### Phase 4 (the check), from the phase 3 SPEC (section 5)

- **The check replays before it admits.** `check` calls `ledger.replay(events)` before its admission loop. A forged
  line with an unhashable `was` raises a Python `TypeError` inside the fold, not `StoreError`, and after_install's
  `_check` catches `StoreError`, `LedgerError` and `OSError`, not `TypeError`. After P3.8 such a line is refused at
  `catch_up` with the right sentence, but `check` still raises first. Reordering `check` (admission first) changes
  when the gate's other comparisons run, which is a behaviour change: phase 4's check takes it or says why not.
- **A hand-over whose key is a list or a mapping** still fails inside the fold or the SQL as it does today. P3.8 holds
  a hand-over's key only to being present, because holding it to more would also refuse the `""` and numeric keys the
  fold reads safely. No writer ever wrote one, and it stops its household today and after.

### Any phase that touches the Mac kit, from P3.2's review 1 (N1)

- `tests/test_pilot.py` 476-483 (`KIT_TESTS`) and `pilot/mactest/run_checks.sh` run `test_store`, which used to
  hold the admission pin, and not `test_admission`, which holds it now. P2.9's `test_index` and P2.4's
  `test_bounds` were never added either. The kit is SPEC-mac's record, so adding a file to it is a change of its own:
  take it in the first phase that owes a Mac check.

## Appendix A: the board's status table at the pause (`ORCH/board/STATUS.md`)

~~~~markdown
# Board: status (orchestrator only)

Branch: claude/quirky-johnson-22edtv
Plan: pilot/SPEC-architecture.md · Prompts: pilot/PROMPT-refactor.md

## Phase 0-1 (tranche 1), SPEC-architecture section 8

| Job | Title | Tier | State | Base | Round |
|---|---|---|---|---|---|
| J1 | Admission fingerprint follows only what the gate runs; README says P309 | sonnet | landed | c4feb8f | 2 |
| J2 | Test helpers live in helper modules | sonnet | landed | 2d4394f | 2 |
| J3 | The guards find code wherever it sits | opus | landed | 7a8ea57 | 2 |
| J4 | Stand-ins that cannot silently miss; recordings | opus | landed as it is (Jason, 2026-10-14) | 4bb2b8f | 6 |
| J5 | Engine state between commands; sender check; typed sentences | opus | landed (review 1 clean) | f1a6b4c | 1 |
| J6 | The type checker; the Windows build's missing check | opus | landed (review 1 clean) | 286b535 | 1 |

## Phases 2-7

Each phase's SPEC (pilot/SPEC-architecture-p<N>.md) is written when the phase before has landed.

| Phase | State |
|---|---|
| 2 Types and shared low layers | landed (14 jobs; last landing 144c5d2; no facade left) |
| 3 The record | paused after P3.2 (Jason, 2026-10-14); next P3.3, base 969bfd6; notes `pilot/HANDOFF-refactor.md` |
| 4 The sorting engine | queued |
| 5 The door and the pass | queued |
| 6 The shell | queued |
| 7 State | queued |

## Phase 2, `pilot/SPEC-architecture-p2.md`

| Job | Title | Tier | State | Base | Round |
|---|---|---|---|---|---|
| P2.1 | Type burn-down in the code that moves | opus | landed (review 1 clean) | e71f2d8 | 1 |
| P2.2 | A domain column in the layer table | sonnet | landed (review 1 clean) | ccc9890 | 1 |
| P2.3 | `replies.py`, one envelope builder, the failure kinds pinned | opus | landed (review 1 clean) | 15a0f72 | 1 |
| P2.4 | `bounds.py`: the value bounds out of records | opus | landed (review 1 clean) | d1addd7 | 1 |
| P2.5 | One file-name-part rule, the typed people rule in records | opus | landed (review 1 clean) | ddfef10 | 1 |
| P2.6 | `hold.py`: the per-reply memo out of settings | opus | landed (review 1 clean; question 001 answered) | c51a1ba | 1 |
| P2.7 | `errlog.py`, and `settings.inside` | sonnet | landed (review 1 clean) | 6029c9d | 1 |
| P2.8 | `PAGE_BREAK` into records, the Open lists into reasons, `page.document` | opus | landed (review 2 clean; F1.1 fixed) | fb43861 | 2 |
| P2.9 | `index.py` out of filer, re-exported | opus | landed (review 1 clean) | c515b2e | 1 |
| P2.10 | The index's readers import it; the scanner never imports filer | sonnet | landed (review 1 clean) | ea04b99 | 1 |
| P2.11 | Event `TypedDict`s past the admission | opus | landed (review 1 clean) | ffa3406 | 1 |
| P2.12 | `tools/corpus.py`, the case tables into `tests/routing_cases.py` | sonnet | landed (review 2 clean; F1.1 fixed) | f8d89a6 | 2 |
| P2.13 | Facades removed: bounds, hold, the spelling sentence | opus | landed (review 2 clean; F1.1 fixed) | 9377690 | 2 |
| P2.14 | Facades removed: the index, and decision 100's shim (A-12) | opus | landed (review 2 clean; F1.1 fixed) | 144c5d2 | 2 |

## Phase 3, `pilot/SPEC-architecture-p3.md`

| Job | Title | Tier | State | Base | Round |
|---|---|---|---|---|---|
| P3.1 | Type burn-down in the store | opus | landed (review 1 clean) | 21322e3 | 1 |
| P3.2 | `admission.py`: the admission out of the store | opus | landed (review 2 clean; F1.1, F1.2 fixed) | 969bfd6 | 2 |
| P3.3 | One function per family, by explicit `if/elif`; the pin sees class members | opus | queued | | |
| P3.4 | `store_check.py`: the check and the export | opus | queued | | |
| P3.5 | `verify.py` at L3 | opus | queued | | |
| P3.6 | One keyed fold (B-9) | opus | queued | | |
| P3.7 | The API's record events to the domain writers; the `ledger.new(` guard (B-4) | opus | queued | | |
| P3.8 | The `released` defect; `ADMISSION_VERSION` 6 (office `verify` before merge) | opus | queued | | |
| P3.9 | The admission's names read from their home | sonnet | queued | | |

Carried to later phases: `carry-forward.md` (open items a job found outside its own scope).
~~~~

## Appendix B: the one-job loop (`Workflow` script)

Build at the job's tier, an Opus review at high effort by an agent that did not build, a rebuild at the builder's
tier, an Opus fix for a finding that survives one rebuild, at most six rounds (PROMPT-refactor 1.2). Arguments: `job`,
`title`, `spec`, `section`, `tier`, `base`, `repo`, `branch`, `orch`, `py311`, `py314`, `extra`; optional
`max_rounds` and `resume`. It returns `passed`, `question`, `blocked`, `stuck` (six rounds spent), `escalate` (an
Opus fix failed review: stop and tell Jason, PROMPT-refactor 1.2 step 4) or `error` (an agent died).

~~~~javascript
export const meta = {
  name: 'refactor-job',
  description: 'One SPEC-architecture job through build, Opus review, rebuild and Opus fix until a review is clean',
  phases: [
    { title: 'Build' },
    { title: 'Review', model: 'opus' },
    { title: 'Rebuild' },
    { title: 'Opus fix', model: 'opus' },
  ],
}

const A = args
const MAX_ROUNDS = A.max_rounds || 6

const BUILD = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['built', 'question', 'blocked'] },
    commits: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    handoff: { type: 'string' },
    question: { type: 'string' },
    owed: { type: 'array', items: { type: 'string' } },
  },
  required: ['status', 'commits', 'summary'],
}
const REVIEW = {
  type: 'object',
  properties: {
    prior: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, resolved: { type: 'boolean' }, evidence: { type: 'string' } },
      required: ['id', 'resolved', 'evidence'] } },
    findings: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, severity: { type: 'string', enum: ['blocking', 'minor'] },
      rule: { type: 'string' }, where: { type: 'string' }, summary: { type: 'string' }, fix: { type: 'string' } },
      required: ['id', 'severity', 'rule', 'where', 'summary', 'fix'] } },
    jason_question: { type: 'string' },
    review_file: { type: 'string' },
    summary: { type: 'string' },
  },
  required: ['prior', 'findings', 'review_file', 'summary'],
}
const FIX = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['fixed', 'question', 'blocked'] },
    fixed: { type: 'array', items: { type: 'string' } },
    disputed: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, why: { type: 'string' } }, required: ['id', 'why'] } },
    commits: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    question: { type: 'string' },
  },
  required: ['status', 'fixed', 'commits', 'summary'],
}

function header(role, section) {
  return [
    `You are the ${role} for job ${A.job} of the architecture refactor (P312).`,
    ``,
    `Values: REPO=${A.repo}  BRANCH=${A.branch}  ORCH=${A.orch}  PY311=${A.py311}  PY314=${A.py314}`,
    `JOB=${A.job}  SPEC=${A.spec}  SECTION=${A.section} ("${A.title}")  BASE=${A.base}  TIER=${A.tier}`,
    ``,
    `Begin with the board: read ORCH/board/NOTICES.md, ORCH/board/STATUS.md and every file in ORCH/board/threads/${A.job}/.`,
    `Then read ${A.repo}/pilot/PROMPT-refactor.md section 2 (common rules) and section ${section} (your role), and follow them exactly.`,
    `ORCH/baseline/SUMMARY.md lists what fails on the untouched tree here (one 3.14-only failure in test_api); that is not your job's.`,
    `Work only in REPO on BRANCH. Never push, rebase, amend or force. End with a report message in ORCH/board/threads/${A.job}/ (next free number).`,
    A.extra ? `\nOrchestrator notes for this job: ${A.extra}` : ``,
  ].join('\n')
}

async function run(prompt, opts, tries) {
  for (let i = 0; i < (tries || 2); i++) {
    const r = await agent(prompt, opts)
    if (r) return r
    log(`${opts.label}: agent returned nothing, retrying`)
  }
  return null
}

const R = A.resume || null   // {round, open: [{f, tries}]}: start at that round's fixes, skipping the build
let build = R ? { status: 'built', commits: [], summary: 'resumed at round ' + R.round } : null
if (!R) {
phase('Build')
build = await run(header(`builder (tier ${A.tier})`, 5) + `

Build the job. Before any edit write ORCH/jobs/${A.job}/before.txt; at the end write ORCH/jobs/${A.job}/handoff.md as section 5 says.
Leave the working tree clean: everything for the job committed on BRANCH, nothing else changed.
Return status 'built' with every commit (hash and subject), a short summary, the handoff path and the office-PC steps owed;
or 'question' (the question you wrote on the board) or 'blocked' (why).`,
  { label: `build ${A.job}`, phase: 'Build', model: A.tier, agentType: 'general-purpose', schema: BUILD })

}
if (!build) return { outcome: 'error', stage: 'build' }
if (build.status !== 'built') return { outcome: build.status, stage: 'build', build }

const open = new Map()   // id -> {finding, tries}
if (R) for (const o of R.open) open.set(o.f.id, { f: o.f, tries: o.tries || 0 })
const history = []
const fixes = []
let jason = null

for (let round = R ? R.round : 1; round <= MAX_ROUNDS; round++) {
  if (!(R && round === R.round)) {
  phase('Review')
  const openList = [...open.values()].map(o => `- ${o.f.id} (${o.f.severity}, tries ${o.tries}): ${o.f.summary}`).join('\n')
  const review = await run(header('reviewer (Opus, high effort; you did not build this job)', 6) + `

This is review round ${round}. Write ORCH/jobs/${A.job}/review-${round}.md. New finding ids are F${round}.<n>.
You change nothing in REPO: no edit, no commit, no repo_map update (run 'check' only). If a test leaves files behind, remove them.
${openList ? `Findings still open from earlier rounds; for each, say in 'prior' whether it is resolved now, with evidence:\n${openList}` : 'There are no earlier findings.'}
Only defects are findings (section 6); notes go in the file and never in 'findings'.
Put a decision that only Jason can make in 'jason_question'; leave it empty otherwise.`,
    { label: `review ${A.job} r${round}`, phase: 'Review', model: 'opus', effort: 'high', agentType: 'general-purpose', schema: REVIEW })
  if (!review) return { outcome: 'error', stage: `review ${round}`, build, history, fixes }
  history.push({ round, summary: review.summary, file: review.review_file,
    new: review.findings.map(f => `${f.id} ${f.severity}: ${f.summary}`),
    prior: review.prior.map(p => `${p.id} ${p.resolved ? 'resolved' : 'OPEN'}`) })

  for (const p of review.prior) {
    if (p.resolved) open.delete(p.id)
    else if (open.has(p.id)) open.get(p.id).evidence = p.evidence
  }
  for (const f of review.findings) open.set(f.id, { f, tries: 0 })

  if (review.jason_question) { jason = review.jason_question }
  if (jason) return { outcome: 'question', stage: `review ${round}`, question: jason, build, history, fixes, open: [...open.keys()] }
  if (open.size === 0) return { outcome: 'passed', rounds: round, build, history, fixes }
  if (round === MAX_ROUNDS) return { outcome: 'stuck', rounds: round, build, history, fixes, open: [...open.values()].map(o => o.f) }
  }

  const failedOpus = [...open.values()].filter(o => o.tries >= 2)
  if (failedOpus.length) return { outcome: 'escalate', stage: `review ${round}`, build, history, fixes,
    findings: failedOpus.map(o => ({ ...o.f, evidence: o.evidence })) }

  const toOpus = [...open.values()].filter(o => o.tries === 1)
  const toTier = [...open.values()].filter(o => o.tries === 0)
  const describe = list => list.map(o => `- ${o.f.id} [${o.f.severity}] ${o.f.where}: ${o.f.summary}\n  fix: ${o.f.fix}${o.evidence ? `\n  still open because: ${o.evidence}` : ''}`).join('\n')

  if (toOpus.length) {
    phase('Opus fix')
    const r = await run(header('fixer (Opus)', 8) + `

These findings survived one rebuild. Fix each at its root (the review files are ORCH/jobs/${A.job}/review-*.md):
${describe(toOpus)}
Commit as section 8 says. Return the ids you fixed, any you dispute with the evidence, and your commits.`,
      { label: `opus fix ${A.job} r${round}`, phase: 'Opus fix', model: 'opus', agentType: 'general-purpose', schema: FIX })
    if (!r) return { outcome: 'error', stage: `opus fix ${round}`, build, history, fixes }
    fixes.push({ round, by: 'opus', ...r })
    if (r.status !== 'fixed') return { outcome: r.status, stage: `opus fix ${round}`, question: r.question, build, history, fixes }
    toOpus.forEach(o => { o.tries = 2 })
  }
  if (toTier.length) {
    phase('Rebuild')
    const r = await run(header(`rebuilder (tier ${A.tier})`, 7) + `

Fix exactly these findings from ORCH/jobs/${A.job}/review-${round}.md, and nothing more:
${describe(toTier)}
Commit as section 7 says. Return the ids you fixed, any you dispute with the evidence, and your commits.`,
      { label: `rebuild ${A.job} r${round}`, phase: 'Rebuild', model: A.tier, agentType: 'general-purpose', schema: FIX })
    if (!r) return { outcome: 'error', stage: `rebuild ${round}`, build, history, fixes }
    fixes.push({ round, by: A.tier, ...r })
    if (r.status !== 'fixed') return { outcome: r.status, stage: `rebuild ${round}`, question: r.question, build, history, fixes }
    toTier.forEach(o => { o.tries = 1 })
  }
}
return { outcome: 'stuck', build, history, fixes }
~~~~

## Appendix C: the phase-SPEC loop (`Workflow` script)

An Opus writer and an Opus reviewer, both at high effort, round by round (PROMPT-refactor 1.1). Arguments: `phase`,
`repo`, `branch`, `orch`, `py311`, `py314`, `base`, `thread`, `draft`, `reviews`; optional `start`, `rounds`,
`answer` and `scope` (a fixes-only check). It returns `question` when the reviewer names a decision for Jason, and
`unsettled` after its last round with findings; the orchestrator then settles them or asks Jason.

~~~~javascript
export const meta = {
  name: 'phase-spec',
  description: 'Write a phase SPEC for the architecture refactor (Opus writer), then an Opus review, at most two rounds',
  phases: [
    { title: 'Write', model: 'opus' },
    { title: 'Review', model: 'opus' },
  ],
}

const A = args
const ROUNDS = A.rounds || 2

const WRITE = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['written', 'question', 'blocked'] },
    spec_file: { type: 'string' },
    jobs: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, title: { type: 'string' }, tier: { type: 'string' }, depends_on: { type: 'string' } },
      required: ['id', 'title', 'tier', 'depends_on'] } },
    answered: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, done: { type: 'boolean' }, how: { type: 'string' } }, required: ['id', 'done', 'how'] } },
    summary: { type: 'string' },
    question: { type: 'string' },
  },
  required: ['status', 'spec_file', 'jobs', 'summary'],
}
const REVIEW = {
  type: 'object',
  properties: {
    prior: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, resolved: { type: 'boolean' }, evidence: { type: 'string' } },
      required: ['id', 'resolved', 'evidence'] } },
    findings: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, severity: { type: 'string', enum: ['blocking', 'minor'] },
      where: { type: 'string' }, summary: { type: 'string' }, fix: { type: 'string' } },
      required: ['id', 'severity', 'where', 'summary', 'fix'] } },
    jason_question: { type: 'string' },
    review_file: { type: 'string' },
    summary: { type: 'string' },
  },
  required: ['prior', 'findings', 'review_file', 'summary'],
}

function header(role, section) {
  return [
    `You are the ${role} for phase ${A.phase} of the architecture refactor (P312).`,
    ``,
    `Values: REPO=${A.repo}  BRANCH=${A.branch}  ORCH=${A.orch}  PY311=${A.py311}  PY314=${A.py314}  BASE=${A.base}`,
    `THREAD=ORCH/board/threads/${A.thread}  DRAFT=${A.draft}  REVIEWS=${A.reviews}`,
    ``,
    `Begin with the board: read ORCH/board/NOTICES.md, ORCH/board/STATUS.md and every file in THREAD (the brief is 000).`,
    `Then read ${A.repo}/pilot/PROMPT-refactor.md section 2 (common rules) and section ${section} (your role), and follow them, with the brief's paths in place of the ones section ${section} names.`,
    `Read only; you change nothing in REPO, commit nothing and push nothing. Python environments with the dev tools: PY311, PY314 (use them to run tools/patch_sites.py report, tools/typecheck.py check and the like).`,
    `End with a message in THREAD (next free number): a report, or a question if you stop on one.`,
  ].join('\n')
}

async function run(prompt, opts) {
  for (let i = 0; i < 2; i++) {
    const r = await agent(prompt, opts)
    if (r) return r
    log(`${opts.label}: agent returned nothing, retrying`)
  }
  return null
}

let last = null
let review = null
for (let r = A.start || 1; r <= ROUNDS; r++) {
  phase('Write')
  const wp = r === 1
    ? header('SPEC writer', 3) + `\n\nWrite the phase SPEC to DRAFT, as the brief says.`
    : header('SPEC writer', 3) + `\n\nRound ${r}: revise DRAFT against every finding in ${A.reviews}/review-${r - 1}.md. For each finding, return it in "answered" with done=true and how, or done=false with the evidence it is wrong. Keep what the review did not touch.` + (A.answer ? ` The orchestrator's answer to review ${r - 1}'s question is ${A.answer}; follow it.` : ``)
  const w = await run(wp, { label: `write:${r}`, phase: 'Write', model: 'opus', effort: 'high', agentType: 'general-purpose', schema: WRITE })
  if (!w) return { outcome: 'error', round: r, where: 'write' }
  last = w
  if (w.status !== 'written') return { outcome: 'question', round: r, write: w }

  phase('Review')
  const rp = header('SPEC reviewer', 4) + `\n\nRound ${r}: review DRAFT against the code at HEAD (which is BASE). Write ${A.reviews}/review-${r}.md.` +
    (r > 1 ? ` First judge each finding of review-${r - 1}.md as resolved or not in "prior", with evidence.` : ``) +
    (A.scope ? ` ${A.scope}` : ``) + ` Mark a finding blocking when a builder following the SPEC would build the wrong thing, miss a pin, change behaviour, or be unable to check acceptance; otherwise minor. A style preference is a note, not a finding. Put anything only Jason can decide in jason_question.` + (A.answer ? ` The orchestrator answered review ${r - 1}'s question in ${A.answer}: judge against it, and put in jason_question only what it does not settle and what turns on what a person sees or on how client files are handled.` : ``)
  review = await run(rp, { label: `review:${r}`, phase: 'Review', model: 'opus', effort: 'high', agentType: 'general-purpose', schema: REVIEW })
  if (!review) return { outcome: 'error', round: r, where: 'review', write: w }
  const blocking = review.findings.filter(f => f.severity === 'blocking')
  log(`round ${r}: ${review.findings.length} findings, ${blocking.length} blocking`)
  if (review.jason_question) return { outcome: 'question', round: r, write: w, review }
  if (review.findings.length === 0) return { outcome: 'passed', round: r, write: w, review }
}
return { outcome: 'unsettled', round: ROUNDS, write: last, review }
~~~~

## Appendix D: the board page's sync (`<scratch>/board-sync/sync.py`)

~~~~python
"""Copy the coordination board into documents for the board page.

The board is files in ORCH (board/STATUS.md, board/NOTICES.md,
board/threads/<JOB>/*.md, jobs/<JOB>/*). The page reads documents from its
own store, so this script turns the files into one JSON document each:

    board/status     the job tables and phase table from STATUS.md
    board/notices    NOTICES.md as text
    threads/<JOB>    the job's messages and its working files

Commands:
    diff             print the keys of documents that changed since the last push
    batch            write the changed documents to out/ and print the batch writes
    mark K=V ...     record that document K, as the last batch wrote it, now has version V
"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
ORCH = HERE.parent / "orchestration"
REPO = pathlib.Path("/home/user/Tax-Info-Request-List-Pilot")
OUT = HERE / "out"
STATE = HERE / "pushed.json"
PENDING = HERE / "pending.json"
FILE_CAP = 40_000
MESSAGE_CAP = 20_000
DOC_CAP = 230_000


def stamp(path):
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")


def cut(text, cap):
    if len(text) <= cap:
        return text
    return text[:cap] + f"\n\n[cut here: {len(text) - cap} more characters are in the file on the board]"


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


#: The words the page colours by. A STATUS.md cell may carry a note after its
#: word ("landed (review 1 clean)"); the page needs the word alone.
STATES = {"queued", "building", "reviewing", "rebuilding", "fixing", "passed", "landed", "question",
          "blocked", "stuck", "escalated"}


def split_state(text):
    """(state word, note) from a status cell, or (the cell, "") when it does
    not begin with one of the page's state words."""
    m = re.match(r"\s*([A-Za-z]+)\b\s*(.*)$", text)
    if not m or m.group(1).lower() not in STATES:
        return text, ""
    note = m.group(2).strip()
    if note.startswith("(") and note.endswith(")"):
        note = note[1:-1].strip()
    return m.group(1).lower(), note


def commit_log():
    """(commit time, subject) for every commit on the branch, newest first."""
    out = subprocess.run(["git", "-C", str(REPO), "log", "--format=%cI%x09%s"],
                         capture_output=True, text=True, check=True).stdout
    return [line.split("\t", 1) for line in out.splitlines() if "\t" in line]


def landed_at(job, log):
    """When ``job``'s landing commit was made ("SPEC-architecture P2.11: landed",
    "SPEC-architecture ledger: J2 landed", "SPEC-architecture J4: land as it is"),
    or "" when the branch has none. P2.1 never matches P2.10."""
    pattern = re.compile(rf"^SPEC-architecture\b.*(?<![\w.]){re.escape(job)}(?![\w.]):?\s+"
                         r"land(?:ed\b|\s+as\s+it\s+is\b)")
    for when, subject in log:
        if pattern.search(subject):
            return when
    return ""


def status_doc():
    path = ORCH / "board" / "STATUS.md"
    lines = path.read_text().splitlines()
    groups, phases, meta, heading = [], [], [], ""
    log = commit_log()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            heading = line[3:].strip()
        elif line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-|]+\|$", lines[i + 1].strip()):
            headers = [h.lower() for h in cells(line)]
            rows = []
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(dict(zip(headers, cells(lines[i]))))
                i += 1
            if "job" in headers:
                groups.append({"heading": heading, "jobs": [
                    {"id": r.get("job", ""), "title": r.get("title", ""), "tier": r.get("tier", ""),
                     "state": split_state(r.get("state", ""))[0], "note": split_state(r.get("state", ""))[1],
                     "landedAt": (landed_at(r.get("job", ""), log)
                                  if split_state(r.get("state", ""))[0] == "landed" else ""),
                     "base": r.get("base", ""), "round": r.get("round", "")}
                    for r in rows]})
            elif "phase" in headers:
                phases = [{"name": r.get("phase", ""), "state": split_state(r.get("state", ""))[0],
                           "note": split_state(r.get("state", ""))[1]} for r in rows]
            continue
        elif line.strip() and not line.startswith("#") and not heading:
            meta.append(line.strip())
        i += 1
    return {"asOf": stamp(path), "meta": meta, "groups": groups, "phases": phases}


def notices_doc():
    path = ORCH / "board" / "NOTICES.md"
    return {"asOf": stamp(path), "text": cut(path.read_text(), DOC_CAP)}


def message(path):
    parts = path.stem.split("-")
    number = parts[0] if parts and parts[0].isdigit() else ""
    kind = parts[-1] if len(parts) > 1 else ""
    role = "-".join(parts[1:-1]) if len(parts) > 2 else ""
    return {"n": number, "role": role, "kind": kind, "file": path.name, "at": stamp(path),
            "text": cut(path.read_text(errors="replace"), MESSAGE_CAP)}


def file_kind(name):
    if name.startswith("review-"):
        return "review"
    if name.startswith("handoff"):
        return "handoff"
    if name.startswith("before"):
        return "before"
    return "file"


def thread_doc(job):
    thread = ORCH / "board" / "threads" / job
    work = ORCH / "jobs" / job
    messages = [message(p) for p in sorted(thread.glob("*.md"))] if thread.is_dir() else []
    files = []
    if work.is_dir():
        for p in sorted(work.iterdir()):
            if p.is_file():
                files.append({"name": p.name, "kind": file_kind(p.name), "at": stamp(p),
                              "text": cut(p.read_text(errors="replace"), FILE_CAP)})
    doc = {"job": job, "messages": messages, "files": files}
    while len(json.dumps(doc)) > DOC_CAP and any(len(f["text"]) > 2000 for f in files):
        biggest = max(files, key=lambda f: len(f["text"]))
        biggest["text"] = cut(biggest["text"], len(biggest["text"]) // 2)
    stamps = [m["at"] for m in messages] + [f["at"] for f in files]
    doc["asOf"] = max(stamps) if stamps else ""
    return doc


def build():
    docs = {"board/status": status_doc(), "board/notices": notices_doc()}
    jobs = set()
    for root in (ORCH / "board" / "threads", ORCH / "jobs"):
        if root.is_dir():
            jobs.update(p.name for p in root.iterdir() if p.is_dir())
    order = {g["id"]: n for n, g in enumerate(j for grp in docs["board/status"]["groups"] for j in grp["jobs"])}
    for job in sorted(jobs, key=lambda j: (order.get(j, 999), j)):
        docs[f"threads/{job}"] = thread_doc(job)
    return docs


def digest(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def changed(docs, state):
    return [k for k, d in docs.items() if state.get(k, {}).get("hash") != digest(d)]


def main(argv):
    command = argv[1] if len(argv) > 1 else "diff"
    docs, state = build(), load_state()
    if command == "diff":
        print(" ".join(changed(docs, state)))
    elif command == "batch":
        OUT.mkdir(exist_ok=True)
        writes, pending = [], {}
        for key in changed(docs, state):
            pending[key] = digest(docs[key])
            collection, doc_id = key.split("/")
            target = OUT / f"{collection}__{doc_id}.json"
            target.write_text(json.dumps(docs[key]))
            entry = {"op": "set", "collection": collection, "doc_id": doc_id, "file_path": str(target)}
            if state.get(key, {}).get("version"):
                entry["if_version"] = state[key]["version"]
            writes.append(entry)
        PENDING.write_text(json.dumps(pending))
        print(json.dumps(writes))
    elif command == "mark":
        pending = json.loads(PENDING.read_text())
        for pair in argv[2:]:
            key, version = pair.split("=")
            state[key] = {"hash": pending[key], "version": int(version)}
        STATE.write_text(json.dumps(state, indent=1))
        print("marked", len(argv) - 2)
    else:
        raise SystemExit(f"unknown command {command!r}: use diff, batch or mark")


if __name__ == "__main__":
    main(sys.argv)
~~~~
