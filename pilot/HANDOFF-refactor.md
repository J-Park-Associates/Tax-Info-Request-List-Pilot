# Refactor handoff: phase 4 building (P4.1-P4.9 landed), P4.10-P4.13 to go

Phase 3 is complete (P3.1-P3.9), and phase 4's SPEC ([`SPEC-architecture-p4.md`](SPEC-architecture-p4.md), 13 jobs,
`f674d93`) is building. Jason answered its two questions on 2026-11-07: build now, and workers join. P4.1 through P4.9
have landed on the branch, the last of them in the commit that carries this file.

This file was brought up to date at P4.9's landing and is the whole hand-over. A new session reads it, `CLAUDE.md`,
[`PROMPT-refactor.md`](PROMPT-refactor.md) (sections 1 and 2) and the ledger
([`SPEC-architecture.md`](SPEC-architecture.md) section 13), and nothing of an earlier session's transcript.

## Where it stopped

- **Branch** `claude/quirky-johnson-22edtv`, pushed, with P4.9's landing commit at its head (the commit that carries
  this file). No build job is in flight.
- **Landed on the branch:**
  - tranche 1 (J1-J6), phase 2 (P2.1-P2.14) and phase 3 (P3.1-P3.9);
  - phase 4's SPEC;
  - phase 4's P4.1-P4.9, each with its row in the ledger:
    - **P4.1** landed `939f241`;
    - **P4.2** landed `4c14445`;
    - **P4.3** landed `b59e4a2` (one after-routing road, `_settle`);
    - **P4.4** landed `f4a7e27` (`tracker/copies.py`);
    - **P4.5** landed `4a36449` (a person's refusals named once; `_here`);
    - **P4.6** landed `5fbb412` (`tracker/intents.py`);
    - **P4.7** landed `1a7a2c7` (`tracker/inbox.py`);
    - **P4.8** landed `79fd266` (`tracker/readme_ack.py`);
    - **P4.9** landed with this file (`tracker/actions.py`; the filer is about 3,700 lines, from 7,601 before P4.4).
- **Nothing is on `main`.** Landing on `main` is a person's step, and no pull request is open: Jason has not asked for
  one. When he does, CLAUDE.md's cost rules apply (open it as a draft, mark it ready once). These must be recorded
  first (section "Owed to the office PC"):
  - P3.8's office `verify`;
  - phase 4's two backtests.
- **Next: P4.10** (`keywords.py`, the matcher out of `content_check`), then P4.11, P4.12 and P4.13, in the SPEC's
  order. Each starts from a brief the orchestrator writes at `ORCH/board/threads/<JOB>/000-orchestrator-brief.md`.
  - The brief re-measures the SPEC's `68b9212` anchors by name at the new base.
  - It quotes section 4.0's stand-in rows verbatim. P4.8's review showed what a shortened rule costs.
  - P4.10-P4.12 move routing code. `vocab_report.py build` and the office backtest after P4.13 matter there.
- **After P4.13:**
  - phase 4 is complete;
  - the phase 5 SPEC ("The door and the pass") is written by the phase-SPEC loop (appendix C);
  - then phases 6 and 7, each with its own SPEC written when the phase before has landed.

## What did not survive the session, and where it is now

The loop's working folder (`ORCH`: the board, every job's `before.txt`, handoff and review files) lives in the
session's scratch folder, outside the repository, as PROMPT-refactor 1.6 says it should. It does not outlive the
container.

**Twice on 2026-11-07 the container restarted under a running builder.**
- The first restart kept the scratch folder.
- The second (about 16:40) wiped it: ORCH, both test environments, the sync tool's state and the loop scripts.

The rebuild took the steps below, from this file's appendices and the board page. Since then a background loop copies
ORCH, the sync tool and the scripts every five minutes to `/home/user/.orch-backup`, outside `/tmp`. That copy holds no
client data, only build notes, and it survives a restart but not the end of the session.

| What | Where it is now |
|---|---|
| What each job did, its rounds, commits and what it owes | the ledger, SPEC-architecture section 13, and the commits |
| The board (status, notices, every job's messages and working files) | the board page, below; and its status table, appendix A |
| The carry-forward list (open items found outside a job's scope) | section "Carry-forward", below |
| The two loop scripts (one job; one phase SPEC) | appendices B and C |
| The board page's sync script | appendix D |

**The board page** is https://claude.ai/artifact/PGTu5QL1KKSzZ2DMW125oS (Jason's monitor). It is a claude.ai artifact,
so it outlives the container.
- Its store holds collection `board` (documents `status` and `notices`) and collection `threads`. `threads` has one
  document per job, with every message and every working file the sync sent; files over 40,000 characters are cut.
- Read it with the `ArtifactData` tool: `list` on `board`, then on `threads`, paging with `query.cursor`, with
  `out_dir` set. The list result gives each document's version.

## Resuming, step by step

1. **Confirm the branch.** `git fetch origin claude/quirky-johnson-22edtv`, check out that branch, and confirm
   `git log -1` is P4.9's landing commit or a later one a person added. If the branch's pull request has been merged
   since, follow the session's rule for a merged branch (restart it from `main`, keep the same name) before any new
   work.
2. **If `/home/user/.orch-backup` exists** (the same session's container restarted), copy it back:
   - `orchestration`, `board-sync`, `workflows` and `land` go back into the scratch folder;
   - then rebuild the environments (step 3) and go to step 7.
3. **Build the two test interpreters** (the floor, 3.11, and the office's, 3.14) with `uv`, in the scratch folder
   (`E` below). `uv` downloads 3.14 itself. `--require-hashes` works with `uv pip`:

   ```
   for v in 3.11 3.14; do uv venv -q -p $v $E/py${v/./}; done
   for p in $E/py311 $E/py314; do
     VIRTUAL_ENV=$p uv pip install -q --require-hashes -r requirements.lock
     VIRTUAL_ENV=$p uv pip install -q --require-hashes --no-deps -r requirements-nodeps.lock
     VIRTUAL_ENV=$p uv pip install -q --require-hashes -r requirements-dev.lock
   done
   ```

   The system Python has neither ruff nor mypy; always use these two. If a lock fails, HANDOFF.md's "Environment
   notes for cloud sessions" lists the fallback packages.
4. **Check the map:** `$E/py311/bin/python tools/repo_map.py check` must say current.
5. **Save the tools:**
   - appendix D as `<scratch>/board-sync/sync.py`;
   - appendix B as `<scratch>/workflows/refactor-job.js`;
   - appendix C as `<scratch>/workflows/refactor-spec.js`.

   Cut each from between its `~~~~` fences with a short script, never by hand.
6. **Rebuild `ORCH`** at `<scratch>/orchestration` (the sync reads `HERE.parent / "orchestration"`) from the board page.
   - Read `board` and `threads` with `ArtifactData list` into a folder.
   - `board/STATUS.md`: render it from the `status` document. Its tables are appendix A's form, with a cell's note
     in brackets after its state word, or straight after it when the note starts with ":".
   - `board/NOTICES.md`: the `notices` document's text.
   - For the current phase's jobs: each message goes to `board/threads/<JOB>/<file>`, and each working file to
     `jobs/<JOB>/<name>`.
     - Set each file's modification time to its `at`. The sync stamps from it, so a regenerated document then equals
       the page's and is not re-sent.
     - Leave older phases' threads out. The sync never touches a job it has no folder for.
   - `carry-forward.md` from the section below.
   - `baseline/README.md` with the known failures (habits, below).
   - Then write `board-sync/pushed.json`: `{"<collection>/<doc>": {"hash": <sync.digest of the regenerated document,
     or "" where it differs from the page's>, "version": <the page's version>}}`.
   - `sync.py diff` should then print nothing.
7. **Arm the watch:** a Monitor on `ORCH/board/threads` for new `*report*.md`, `*review*.md` and `*question*.md` files
   (30 minutes, re-armed on expiry), and the five-minute copy to `/home/user/.orch-backup`.
8. **Build the next job** with appendix B (`scriptPath`), from the orchestrator's brief, and **land each job** when a
   review is clean, by the checklist below. Arguments: `job`, `title`, `spec`, `section` (`"4, P4.10"`), `tier`,
   `base`, `repo`, `branch`, `orch`, `py311`, `py314` (the environment folders), `extra` (the brief's path and the
   rules that bind this job).

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
  `repo_map.py update`, in the same commit. Phase 4 owns the matcher and the catalog, so most of its jobs meet it.
- **Known failures under 3.14:** test_api's `test_importing_the_api_opens_no_file_but_the_programs_own` (it
  opens /dev/urandom), and under `-n auto` a test_ocr `resident_pages` load flake that passes alone (rerun the file
  alone and cite both). Neither is a job's.
- **Baselines at P4.9's landing:** `typecheck.py check` 138 errors in 22 files (the filer family 0); `patch_sites.py check` 902 stand-ins on 50 modules; the map 375 nodes; collected ids 5,215; `ADMISSION_VERSION` 6; test_layers 38, test_single_source 219 and test_repo_map 82 tests; `FILER_FAMILY` is filer, copies, intents, inbox, readme_ack and actions; `COMPOSERS` is filer, households, intents, actions, manifest, reminder and scanner; architecture.md says "fifty-one" modules.
- **Pytest:** one process per test file, in parallel, with `-p no:cacheprovider`; never the whole suite for a job
  that does not reach the engine (CLAUDE.md, "Test minimally").
- **A SPEC edit by script** must end with the file's write; one did not, and an hour went to edits that never saved.
  Confirm with `cmp` against a copy.
- **A store constant read at module level must be a plain binding.** A module the store's `__main__` imports at call
  time (store_check, verify) that reads a store constant at module level must see it bound by a plain assignment,
  never by a tuple unpacking: mypy types a tuple unpacking only when it checks the store, so across the call-time
  cycle it reads as untyped (P3.5's question 001 and answer 002; the store now binds its five judgment kinds one per
  line).
- **An office-PC step a job cannot run in the cloud is owed, in words.** The brief gives the exact words; the job lists
  them in its handoff and its report as owed, and the reviewer judges the step satisfied when it is listed. The merge
  to `main` waits on the step, not the landing on the branch (P3.8's `verify`).
- **A builder's stop that leaves uncommitted work.** The stop hook's "uncommitted changes" is answered by explaining,
  not by committing the builder's files: the orchestrator does not commit a builder's work for it.
- **Questions.** An agent that stops with a `question` gets an `answer` file on its thread from the orchestrator, or
  Jason's word first when the decision is his. A question at the build is answered by running appendix B again (a
  fresh builder continues from the thread and the working tree); one at a review or a fix by running it with
  `resume` (`{round, open: [{f, tries}]}`), which skips the build and starts at that round's fixes. The phase-SPEC
  loop takes `start` and `answer` the same way.
- **A brief quotes the SPEC's rules, never paraphrases them.** P4.8's brief narrowed section 4.0's stand-in rule
  ("where the test drives the received list"); the builder followed it and review 1 found the gap. The rule the family
  follows: a stand-in goes on every module that reads the name as a global, whichever road the test takes.
- **A container restart under a builder.** Committed work and the repository's working tree survive; the scratch
  folder may not. Check `git status` (a partial in the tree is the builder's: save `git diff HEAD --binary` to the
  job folder, then relaunch the job with a note on its thread to continue it, treating the partial as unreviewed),
  then restore ORCH from `/home/user/.orch-backup` or the board page ("Resuming", steps 2 and 6).

## Owed to the office PC

None of this can run in the cloud. The ledger's last column is the record; gathered here:

- **J2 (optional):** `test_door`, `test_filer`, `test_containers`, `test_ocr` and `test_content_check` once on Windows,
  one process each.
- **J3, J4, J5, J6:** each row names its `pilot\wintest\run_checks.ps1 -Tests ...` list and hands-on steps (J5's built
  app on a made-up clients root; J6's installer build and the planted `app\settings.json`).
- **P2.12:** `tools/backtest.py run` and `check` against `docs/backtest-baseline.json`, and `tests/test_real_corpus.py`
  with `TRACKER_REAL_CORPUS` set.
- **P3.4:** the office Windows check names `test_store_check` (SPEC-architecture-p3 section 6): `_write_csv` calls the
  atomic replace, moved byte for byte.
- **P3.8, before it merges to `main`:** on the office PC, with the P3.8 build, run the read-only
  `python -m tracker.store "<the app folder>" verify "<clients root>"` and record whether any return's record holds a
  release or an old hand-over whose `was` is not a location, or a hand-over with no key (such a household stops after
  the upgrade until the line is repaired). If it names any household, the list goes to Jason before P3.8 merges
  (SPEC-architecture-p3 section 6).
- **Phase 4's backtest** (SPEC-architecture-p4 section 6, with the exact commands): `tools/backtest.py run` (plain
  and `--ocr`) and `check`, and `tests/test_real_corpus.py` with `TRACKER_REAL_CORPUS` set, once on the build at
  `68b9212` (before phase 4) and once after P4.13, both before phase 4 merges to `main`; the two reports must agree.
  Plus the whole-suite Windows check on the stack and the `-Tests` lists of P4.4, P4.6, P4.9 and P4.12 (the `windows`
  jobs). Jason's Q1 (2026-11-07): build now, both backtests before the merge.
- **P4.1:** `pilot\wintest\run_checks.ps1 -Tests test_locking,test_resident`.
- **P4.4:** `pilot\wintest\run_checks.ps1 -Tests test_copies,test_filer,test_scaffold,test_runner,test_api,test_rollover,test_errors`.
- **P4.6:** `pilot\wintest\run_checks.ps1 -Tests test_intents,test_filer,test_api,test_runner,test_errors,test_containers`.
- **P4.9:** `pilot\wintest\run_checks.ps1 -Tests test_actions,test_api,test_filer`.

## Open for Jason

- **P313's Q-B** (whether the re-send road's across-household park carries a shortlist) and **Q-F** (if unifying the
  room check would change a save's outcome): kept as today until his word. Q-B touches phase 4, Q-F phase 5.
- **P3.8's office `verify`** (above): its list, if any, is his before P3.8 merges.
- **Phase 4's Q1 and Q2 are answered** (Jason, 2026-11-07; SPEC-architecture-p4 section 7): Q1 (A) "Build now",
  with the office backtest on the build before phase 4 and the build after, both before phase 4 merges to `main`;
  Q2 (A) "Workers join" (`copies` and `intents` join the filer under "Originals are never altered").
- Q1 of phase 3 is answered ("a - the full rule", 2026-10-14) and written into the SPEC.

## The phase 4 SPEC brief

Phase 4's SPEC is committed; the brief the phase-SPEC loop was given is message 000 of the board page's
thread `P4`. Phase 5's brief is written the same way when P4.13 has landed.

## Carry-forward

Rebuilt on 2026-11-07 after a container restart wiped the scratch folder: the sections up to the P2.12 one are
HANDOFF-refactor.md's copy (as at `28b7628`); the phase 4 sections after it are the orchestrator's own entries.
Anything carried forward between `28b7628` and P4.1's entry, other than the tools job below, may be missing: the
P4.2 and P4.3 review notes are in their threads on the board page.

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
- **The pin's walker reads `Class.member` but not `module.Class.member`** (P3.3 review 1, note): a closure function
  that wrote `bounds.Override.ALL` would not have the member recorded. No closure function uses that form today. The
  first job that edits `admission_closure` again widens the Attribute branch to a two-level chain, with a made-up-module
  test, or the pin's docstring says the form is not followed.
- **`Refuse` and the `Final` keys are not in the map** (P3.3 builder and review): `tools/repo_map.py` records a
  module-level assignment only when its name is all upper case, so `admission.Refuse` (a type alias) and ledger's
  `Final` keys (P2.11) are invisible to it. A phase that touches repo_map's exports parser decides whether type aliases
  belong in the derived layer.
- **Two cosmetic leftovers in P3.3's code** (P3.3 review 1): a blank line after `_refuse_a_malformed_line`'s docstring
  where the removed import sat (tracker/admission.py about 200), and the walker's new docstring sentence in
  tests/test_admission.py not re-wrapped. The next job that edits either file tidies them; do not open a job for them.
- **`_agree` and `_ADDED_IN_PLACE` have the check as their one reader** (P3.4 review 1, note 2): after the move
  `store._agree` (store.py about 335) is read only by `tracker/store_check.py`, and store_check's docstring gives a
  slightly wrong reason for its staying in the store. The job that next edits store_check (P3.6's keyed fold) either
  moves both there with a sentence, or corrects the docstring's reason.
- **One bare ``check`` in store's prose** (P3.4 review 1, note 3): store.py about 3100, inside `gone_journals` ("as
  ``check`` holds it"), now means `store_check.check`. Retarget it when a later job next edits the store's prose.
- **after_install's curated notes list a stale import set** (P3.4 review 1, note 4; stale before P3.4): the after_install
  node's "Layer 4: imports scheduling, store, registry, ledger, door, ..." does not match its imports. Fix it when a
  job next edits after_install's curated node.
- **Cosmetic** (P3.4 review 1, note 1): three blank lines between definitions in `tests/store_helpers.py` and a
  trailing blank line at the end of tests/test_admission.py. P3.5 touches store_helpers' users; tidy then.
- **test_layers' store paragraph does not list verify** (P3.5 review 1, note): tests/test_layers.py about 90-98 lists
  the store's command-line call-time imports and does not yet name verify. Still true as written; add verify when a
  job next edits that paragraph.
- **A second loaded copy of the store under `python -m tracker.store`** (P3.5 review 1, note): run as `__main__`, the
  store's command line imports store_check and verify, which import `tracker.store` - a second module object beside
  `__main__`. No behaviour changes (both read constants and pure functions; store_check has done this since P3.4), but
  a later job that gives the store module-level state must not assume one copy. Phase 7's scheduling work is where it
  could matter.
- **The filer's curated note keeps older wording about `holds_the_row`** (P3.5 review 1, note). Reword it when a job
  next edits the filer's curated node (phase 4).
- **An order-dependent lock leak in the suite, older than P3.6 — fix before the next whole-suite gate** (P3.6 builder
  and review 1, N6): `tests/test_locking.py::test_two_takes_in_one_clock_tick_write_two_tokens` leaves
  `locking._unreleased` holding a path in its process, and any `tests/test_resident.py` engine test that later runs in
  the same xdist worker retires with `engine retired: lock-left`. Shown identical at `69cc9a2` (`ORCH/jobs/P3.6/probe/`).
  The fix is test-only: stand in on `locking._unreleased` in that test, as test_locking 1385/1402 and test_resident 251
  do. It can fail any whole-suite gate whenever xdist puts the two files on one worker, so the next job whose gate is
  the whole suite (phase 4's engine work at the latest) fixes it first, or a job before it carries it.
- **`ledger.apply`'s parameter `key` is rebound in the row branch** (P3.6 review 1, N1): `key = event.get(KEY_KEY)`
  reuses the name; the builder added a comment. A job that next edits `apply` renames the local (`row_key`).
- **`store._recorded_statuses` needs a keyed fold** (P3.6 review 1, N2): handed an unkeyed fold holding a status it
  raises `KeyError`. Both callers hand it a keyed one. A later edit of it adds a docstring sentence or an assert.
- **The store's curated decision-138 sentence reads oddly** (P3.6 review 1, N3): it keeps "not from
  ledger.Folded.statuses, which is keyed by the exact spelling" though `_apply`'s own fold is keyed now. Reword when the
  store's curated node is next edited.
- **`check`'s docstring names `ledger.read_with_head`; the code calls `read_with_chain`** (P3.6 review 1, N4;
  pre-existing). Fix at the next edit of store_check's `check` docstring.
- **The writers derivation test names `accept-folder-name` but not `mark-shared`** (P3.7 review 1, N1): `mark-shared`
  is covered only by `derived <= WRITING_COMMANDS`. A job that next edits `tests/test_api.py`'s derivation test adds
  the second name to its assert.
- **The `COMPOSERS` guard does not see `tracker.ledger.new(...)` through an unaliased `import tracker.ledger`** (P3.7
  review 1, N2). No such form exists in the package. Widen the walk if one ever appears.
- **The three new writers have no test in their own modules' files** (P3.7 review 1, N3): `households.mark_shared`,
  `households.accept_name` and `manifest.accept_folder_name` are covered through the API (R3.7.4 and the accept and
  share tests). A job that next edits test_households or test_manifest may add a direct test each.
- **The P3 SPEC's P3.8 "five stand-ins are unaffected" sentence** (P3.8 review 1, N1): R3.8.5 itself added a sixth
  stand-in on `store._refuse_a_malformed_line` (test_store 3935); patch_sites is 761 on 45 from `c58bccf`. History; a
  later SPEC counting stand-ins starts from 761.
- **One 97-character line in the runbook's malformed-line paragraph** (P3.8 review 1, N3). Reflow it when a job next
  edits that paragraph.
- **P3.8's office verify gates the merge to main**: the landing PR that carries P3.8 must not be marked ready until
  the office PC's read-only `verify` with that build is recorded (SPEC-architecture section 13, P3.8's row).
- **The admission's curated note says "five stand-ins"; there are six** (P3.9 builder and reviews): curated
  `docs/repo-map.curated.json` 53 keeps P3.2's count; P3.8's appended sentence gives the current six. Reword when the
  admission's curated node is next edited.

### A tools job (any phase), from the phase 4 SPEC writer (`board/threads/P4/003`, "Found, not built")

- **`tools/backtest.py` 231 says "with ``ocr=True`` there is no reading child".** At `68b9212`, `route_file` goes through
  `read_once`, `judge_bounded` and `run_in_child`, one session per document, so the `--ocr` run does reach the child
  (which is why SPEC-architecture-p4 section 6 uses it for P4.12). Prose in a tool; reword it when a job next edits
  `tools/backtest.py`.

### Any phase, from P4.1's review 1 (`ORCH/jobs/P4.1/review-1.md`, notes)

- **A test_ocr load flake under PY314 with `-n auto`**: the `resident_pages` test failed once in the whole-suite run
  at the base and at P4.1's head, and passes alone (3 of 3; the file 71 passed). Pre-existing. A job that next edits
  test_ocr or the reading child's tests (P4.12) looks for a timing assumption in it.
- **The ledger node's curated role repeats one sentence** (true at the base). Remove the repeat when the ledger node is
  next edited.

### Phase 4, from P4.4's review 1 (`ORCH/jobs/P4.4/review-1.md`, notes)

- **`pilot/wintest/make_samples.py` 28 names ``filer.bears_macros``**, which the filer no longer binds (it is
  `validators.bears_macros`, read by `copies`). It sits outside section 3's grep (`tracker`, `tools`, `tests`). P4.13,
  which points every reader at its home, retargets it, or a later wintest change does.
- **P4.4's "next" note** (`threads/P4.4/003-builder-next.md`): later filer jobs (P4.6-P4.9) add their shared helpers to
  `tests/filer_helpers.py` and their module to `FILER_FAMILY`; the filer imports back 29 names from `copies`, whose
  test reads through the filer are P4.13's; `_move_whole`, `_copy_whole`, `_existing_copy` and `_review_copy_path`
  keep the filer as stand-in target until their callers move.

### Phase 4, from P4.6's review 1 (`ORCH/jobs/P4.6/review-1.md`, notes)

- **`tracker/index.py` docstring 42-43** says a stand-in on `filer.read_index` "reaches the filer's own callers and
  nobody else's". Incomplete since P4.4 (copies) and more so with intents. A wording item for P4.13 or later.
- **The curated sentence on `RECORD_PRESERVE_INTENTS`** (now on the intents node) names a switch no code defines; it
  was already so at the base and moved verbatim. Whoever next edits the intents node's curated text fixes it.
- **P4.6's "next" note** (`threads/P4.6/002-builder-next.md`): `FILER_FAMILY` is filer, copies, intents; stand-ins
  on both filer and intents: `_move_whole`, `_copy_whole`, `_existing_copy`, `_review_copy_path`, `_do_op`; the filer
  imports back 14 names from intents; P4.13's import-back reads include test_intents 180 and 520.

### Phase 4, from P4.7's review 1 (`ORCH/jobs/P4.7/review-1.md`, notes)

- **`tracker/door.py` 166** says "the filer's walks and its step check ask it" (`through_a_link`). Since P4.6 the step
  check is `intents`', and since P4.7 most of the walks are `inbox`'s; the filer keeps `_prune_empty_dirs`. It names
  no moved name, so the grep-based retarget does not reach it: a word for P4.13's prose sweep.
- **P4.7's "next" note** (`threads/P4.7/002-builder-next.md`): `FILER_FAMILY` adds inbox; `two_returns` lives in
  `tests/filer_helpers.py`; the filer imports back 19 names from inbox, and P4.9's moved code reads
  `_copy_taken_by_a_later_row` and `_absent` from `tracker.inbox`; P4.13's import-back reads from P4.7 are listed
  there (test_filer, test_reminder 1640 and 1654, test_scaffold 380).

### Phase 4, from P4.8's reviews (`ORCH/jobs/P4.8/review-1.md`, `review-2.md`, notes)

- **`tracker/scaffold.py` 41-42** says "the filer at layer 3" for what is now `readme_ack`'s. A word for P4.13's prose
  sweep.
- **test_index's crossing tuple** leaves `readme_ack` out (it binds no index private), although the test's docstring
  says "the filer and the modules carved out of it". P4.13 decides whether the tuple names the whole family.
- **P334's "beside the filer, copies and intents"** is exact for `read_index` only; `load_manifest` sits beside the
  filer alone. Wording, for whoever next edits P334's neighbourhood.
- **P4.8's next note** (`threads/P4.8/004-rebuilder-next.md`) restates P4.4-P4.8's notes in full for P4.9 and P4.13.

### Phase 4, from P4.9's review 1 (`ORCH/jobs/P4.9/review-1.md`, notes)

- **The filer's docstring pointer paragraph has two sentences** (filer 165-169) where section 4.1 says one; the second
  restates R4.9.7. Trim it in any later touch.
- **P4.9's next note misplaces one test** (`threads/P4.9/002-builder-next.md`, the FILER_FAMILY bullet): the
  `_copy_whole` site at test_errors 990 is the refused-copy test (`intents._a_copy_to_act_on`); the power-loss test
  stays in `tests/test_filer.py` (about 2377, its loop at 2399). Both sit on `(intents, actions)` correctly. P4.13
  reads the note with this correction.
- **Re-wrapped prose past the paragraph's width** at intents 61 and readme_ack 43 and 53. Cosmetic.
- **Filer-node curated sentences mostly about moved code** stay under the P4.9 pointer ("restore_working_copy()
  dispatches", decision 76's `dismiss_review_file()`, the decision 112 block); each names a staying filer name. A map
  sweep could split them.
- **P4.13's import-back reads**: test_actions holds 17 reads through the filer of names the filer imports from
  elsewhere (`FilingError` x8, `MarkRefusedError`, `PATH_NO_ROOM_IN`, `UNTIED_IN_PBC`, the `sha256_of` x3 and
  `is_cloud_placeholder` x2 captures, `.Path`); test_filer 33 and filer_helpers 3 (`_move_whole` x2, `_do_op`) from
  P4.4-P4.8. The next note lists them.

## Appendix A: the board's status table now (`ORCH/board/STATUS.md`)

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
| J4 | Stand-ins that cannot silently miss; recordings | opus | landed (as it is (Jason, 2026-10-14)) | 4bb2b8f | 6 |
| J5 | Engine state between commands; sender check; typed sentences | opus | landed (review 1 clean) | f1a6b4c | 1 |
| J6 | The type checker; the Windows build's missing check | opus | landed (review 1 clean) | 286b535 | 1 |

## Phases 2-7

Each phase's SPEC (pilot/SPEC-architecture-p<N>.md) is written when the phase before has landed.

| Phase | State |
|---|---|
| 2 Types and shared low layers | landed (14 jobs; last landing 144c5d2; no facade left) |
| 3 The record | landed: P3.1-P3.9, last 68b9212 (P3.8's office verify owed before main) |
| 4 The sorting engine | building: SPEC f674d93; Jason answered Q1 (build now) and Q2 (workers join) |
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
| P3.3 | One function per family, by explicit `if/elif`; the pin sees class members | opus | landed (review 1 clean) | 1298c23 | 1 |
| P3.4 | `store_check.py`: the check and the export | opus | landed (review 1 clean) | a49b4d6 | 1 |
| P3.5 | `verify.py` at L3 | opus | landed (review 1 clean; one question, answered A) | 69cc9a2 | 1 |
| P3.6 | One keyed fold (B-9) | opus | landed (review 1 clean) | 9d94c6e | 1 |
| P3.7 | The API's record events to the domain writers; the `ledger.new(` guard (B-4) | opus | landed (review 1 clean) | ef68704 | 1 |
| P3.8 | The `released` defect; `ADMISSION_VERSION` 6 (office `verify` before merge) | opus | landed ((review 1 clean); office verify owed) | 326beeb | 1 |
| P3.9 | The admission's names read from their home | sonnet | landed (review 2 clean) | 68b9212 | 2 |

## Phase 4, `pilot/SPEC-architecture-p4.md`

| Job | Title | Tier | State | Base | Round |
|---|---|---|---|---|---|
| P4.1 | The lock leak; type burn-down; `candidates` and the ops typed (A-8) | opus | landed (review 1 clean) | 939f241 | 1 |
| P4.2 | `conftest.py` into plugins (E-6) | sonnet | landed (review 2 clean) | 4c14445 | 2 |
| P4.3 | One after-routing road, `_settle` (A-3) | opus | landed (review 1 clean) | 4c14445 | 1 |
| P4.4 | `copies.py`: names, room, copies and moves (A-1; windows) | opus | landed (review 1 clean) | b59e4a2 | 1 |
| P4.5 | A person's refusals named once; `_here` (A-10) | sonnet | landed (review 1 clean) | f4a7e27 | 1 |
| P4.6 | `intents.py`: the write-ahead intents (A-1; windows) | opus | landed (review 1 clean) | 4a36449 | 1 |
| P4.7 | `inbox.py`: walking the inbox (A-1) | opus | landed (review 1 clean) | 5fbb412 | 1 |
| P4.8 | `readme_ack.py`: the received list and the refresh (A-1) | opus | landed (review 2 clean; F1.1 fixed) | 1a7a2c7 | 2 |
| P4.9 | `actions.py`: a person's actions and the rescan (A-1; windows) | opus | landed (review 1 clean) | 79fd266 | 1 |
| P4.10 | `keywords.py`: the matcher out of content_check (A-5; routing) | opus | queued | - | - |
| P4.11 | `verdicts.py`: the judgment's shapes and the verdict cache (A-5; routing) | opus | queued | - | - |
| P4.12 | `reader_child.py`: the reading's child and its supervisor (A-6; routing; windows) | opus | queued | - | - |
| P4.13 | The moved names read from their home; a guard | sonnet | queued | - | - |

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
