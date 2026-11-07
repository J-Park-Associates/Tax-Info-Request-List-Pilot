# Refactor handoff: phase 3 complete (P3.1-P3.9), the phase 4 SPEC committed, its builds waiting on Jason

**Paused 2026-10-14 at Jason's word** ("pause at a good spot and leave notes so you can pick it up next week"); the
loop resumed on 2026-11-07 and phase 3 is now complete: P3.1-P3.9 have landed on the branch, head `68b9212`, and the
phase 4 SPEC ([`SPEC-architecture-p4.md`](SPEC-architecture-p4.md), 13 jobs) passed review and is committed at
`f674d93`. Its builds wait on Jason's two questions (section "Open for Jason"). This file was brought up to date at that
point and is the whole
hand-over. A new session reads it, `CLAUDE.md`, [`PROMPT-refactor.md`](PROMPT-refactor.md)
(sections 1 and 2) and the ledger ([`SPEC-architecture.md`](SPEC-architecture.md) section 13), and nothing of an
earlier session's transcript.

## Where it stopped

- **Branch** `claude/quirky-johnson-22edtv`, head after `f674d93` ("SPEC-architecture phase 4: the sorting engine, 13
  jobs"), pushed. No build job is in flight. The phase 4 SPEC was reviewed in three rounds (4, 4 and 0 blocking
  findings) and a check of round 3's two minor fixes, all measured at `68b9212`; the board thread `P4` holds the
  record. Phase 4's code base is still `68b9212` (the SPEC and this file change no code).
- **Landed on the branch:** tranche 1 (J1-J6), phase 2 (P2.1-P2.14, no facade left), the phase 3 SPEC
  ([`SPEC-architecture-p3.md`](SPEC-architecture-p3.md), `6cfb1c9`), and all of phase 3, each with its row in the
  ledger (build commits, then the landing commit):
  - **P3.1** `de3da78`, landed `21322e3`;
  - **P3.2** `82960bd`, `c450650`, landed `969bfd6`;
  - **P3.3** `81a5f26`, `37203de`, landed `1298c23`;
  - **P3.4** `a4c5135`, landed `a49b4d6`;
  - **P3.5** `41afd0c`, landed `69cc9a2`;
  - **P3.6** `cc02198`, landed `9d94c6e`;
  - **P3.7** `18d548b`, landed `ef68704`;
  - **P3.8** `c58bccf`, landed `326beeb`;
  - **P3.9** `95aa0df`, `b7f4b1e`, landed `68b9212`.
- **Nothing is on `main`.** Landing on `main` is a person's step, and no pull request is open: Jason has not asked
  for one. When he does, CLAUDE.md's cost rules apply (open it as a draft, mark it ready once), and **P3.8's office
  `verify` must be recorded first** (section "Owed to the office PC").
- **Next: phase 4's builds**, P4.1 first, in the SPEC's order (section 4's table: tier, dependency, whether it moves
  routing code, whether it carries the `windows` label). They **wait on Jason's answers** to the SPEC's section 7 Q1
  (build now, with the office backtest before and after phase 4, or wait for the office baseline) and Q2 (which
  modules the map lists as upholding "Originals are never altered"; the SPEC's default is (A)). Then phases 5 to 7,
  each with its own SPEC written when the phase before has landed.

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
| The phase 4 SPEC brief (what the phase-SPEC loop was given) | section "For phase 4: the SPEC brief", below |

**The board page** is https://claude.ai/artifact/PGTu5QL1KKSzZ2DMW125oS (Jason's monitor). It is a claude.ai artifact,
so it outlives the container. Its store holds collection `board` (documents `status` and `notices`) and collection
`threads` (one document per job, with every message and working file the sync sent). Read it with the `ArtifactData`
tool (`list` on `board` and on `threads`). Versions the sync last recorded (`pushed.json`): `board/status` 69,
`board/notices` 40; threads J1 5, J2 12, J3 12, J4 23, J5 8, J6 8, P2 15, P2.1 4, P2.2 4, P2.3 4, P2.4 3, P2.5 3, P2.6
4, P2.7 3, P2.8 4, P2.9 3, P2.10 3, P2.11 2, P2.12 4, P2.13 5, P2.14 5, P3 7, P3.1 2, P3.2 2, P3.3 2, P3.4 2, P3.5 3,
P3.6 2, P3.7 3, P3.8 3, P3.9 3. Still waiting to be sent when this was written (`pending.json`): the status document's
newest text (phase 4 "SPEC being written") and the new thread `P4` (the brief); the first `batch` after a rebuild sends
them.

## Resuming, step by step

1. **Confirm the branch.** `git fetch origin claude/quirky-johnson-22edtv`, check out that branch, and confirm
   `git log -1` is `68b9212` or a later commit a person added. If the branch's pull request has been merged since,
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
7. **(Done: the phase 4 SPEC is committed; skip to step 9.)** Write the phase 4 brief at `ORCH/board/threads/P4/000-orchestrator-brief.md`: the text is in section "For phase 4:
   the SPEC brief", below. Re-measure its anchors if the branch has moved past `68b9212`.
8. **Run the phase-SPEC loop** with appendix C: `phase` "4", `repo` the checkout, `branch`
   "claude/quirky-johnson-22edtv", `orch`, `py311`, `py314` (absolute paths), `base` "68b9212", `thread` "P4", `draft`
   `ORCH/jobs/P4/SPEC-architecture-p4.md`, `reviews` `ORCH/spec-p4` (a link to `ORCH/jobs/P4`). Run a Monitor on
   `ORCH/board/threads` for new `*report*.md` and `*question*.md` files (30 minutes, re-armed on expiry). When the
   SPEC passes review, commit it as `pilot/SPEC-architecture-p4.md` and ask Jason the phase 4 build-gate question
   (section "Open for Jason") if he has not answered it.
9. **Build phase 4's jobs** with appendix B, in the SPEC's order, once Jason has answered the build-gate question,
   and **land each job** when a review is clean, by the checklist below.

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
- **Known failure under 3.14:** test_api's `test_importing_the_api_opens_no_file_but_the_programs_own`. It fails at
  the base too; it is not a job's.
- **Baselines at `68b9212`:** `typecheck.py check` 206 errors in 25 files; `patch_sites.py check` 761 stand-ins on 45
  modules; the map 359 nodes, 1642 edges; `ADMISSION_VERSION` 6 and `ADMISSION_PIN[6]` 260 parts; test_layers 38,
  test_single_source 219 and test_repo_map 82 tests; the one known PY314 failure in test_api
  (`test_importing_the_api_opens_no_file_but_the_programs_own`, /dev/urandom); and the pre-existing order-dependent lock
  leak between test_locking and test_resident (carry-forward).
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
  jobs). Whether builds may start before the office records its baseline is Jason's Q1.

## Open for Jason

- **P313's Q-B** (whether the re-send road's across-household park carries a shortlist) and **Q-F** (if unifying the
  room check would change a save's outcome): kept as today until his word. Q-B touches phase 4, Q-F phase 5.
- **P3.8's office `verify`** (above): its list, if any, is his before P3.8 merges.
- **Phase 4's Q1, the build gate** (SPEC-architecture-p4 section 7). The plan holds phase 4's builds until the office
  has recorded its backtest baseline (`docs/backtest-baseline.json` records no agreement yet). Asked on 2026-11-07:
  may phase 4 instead build on the branch now, with the backtest run at the office on the build before phase 4 and on
  the build after (agreement must not move), before phase 4 merges to `main`? Recommended: build now. Until he
  answers, builds wait.
- **Phase 4's Q2** (section 7): which modules the map lists as upholding "Originals are never altered" once the copy
  and the intents leave the filer: (A) the modules that do the work join (`copies`, `intents`; the SPEC's default),
  (B) only the filer, (C) as (A), and `keywords` also joins the no-AI rule. Map labels only; no behaviour changes.
- Q1 of phase 3 is answered ("a - the full rule", 2026-10-14) and written into the SPEC.

## For phase 4: the SPEC brief

The brief below was given to the phase-SPEC loop on 2026-11-07 (base `68b9212`; draft to
`ORCH/jobs/P4/SPEC-architecture-p4.md`, reviews to `ORCH/spec-p4`, which links to `ORCH/jobs/P4`); if the draft is
lost, a new session reruns that loop with it.

~~~~markdown
# Phase 4 brief (orchestrator): the SPEC for "The sorting engine"

Phase 3 has landed: nine jobs, the last landing at `68b9212`, which is this phase's base. No facade is left. Ledger:
SPEC-architecture section 13. P3.8's office `verify` is still owed before the branch reaches `main`; it does not touch
this phase.

**Your job (SPEC writer, PROMPT-refactor section 3).** Write the buildable SPEC for phase 4 from the code at
`68b9212`. Its scope is SPEC-architecture section 9's "Phase 4" paragraph (819-827), the section 5 rows it relies on
(the filer row at 166, the ocr row at 172, the layer picture at 338-346 and the new-module table at 385-392:
`copies.py` L2, `keywords.py` L2, `verdicts.py` L2, `reader_child.py` L2, `intents.py` L3, `inbox.py` L3,
`readme_ack.py` L3, `actions.py` L3), and the audit findings it cites in `pilot/AUDIT-2026-10-13-architecture.md`:
**A-1** (61), **A-3** (156), **A-4** (190), **A-5** (220), **A-6** (246), **A-8** (305), **A-10** (343) and **E-6**
(1623). A-7 and A-11 are phase 7's: leave them, and say so where a move touches the state they name.

- **Where to write it.** Write the draft to `ORCH/jobs/P4/SPEC-architecture-p4.md`, not into the repository. The
  orchestrator copies it to `pilot/SPEC-architecture-p4.md` and commits it with the map once the review settles.
- **The SPEC reviewer** writes its findings to `ORCH/spec-p4/review-<r>.md`. Revise against them; there are at most
  two rounds.
- `pilot/SPEC-architecture-p3.md` is the model for form: section 3's rules every job follows, then one section per
  job with numbered requirements (R4.k.n), measured anchors, the tests, "stop and ask" and "accept when", then risks,
  what is owed to the office PC, and questions for Jason.

**Measured at `68b9212`** (re-measure anything you rely on; these are where to start):
- `tracker/filer.py` 7,576 lines; `tracker/content_check.py` 2,496; `tracker/router.py` 1,227; `tracker/scanner.py`
  967; `tracker/ocr.py` (measure it). `tests/test_filer.py` 9,964 lines; `tests/test_content_check.py` 2,748;
  `tests/conftest.py` 1,383 with 8 autouse fixtures.
- `patch_sites.py report`: **tracker.filer 77 stand-ins in 9 files** (29 defined, 48 imported); **tracker.content_check
  102 in 13**; **tracker.ocr 63 in 7**. `patch_sites.py check`: 761 on 45. Give each moving job its exact list (A-4:
  splitting is expensive because of where the tests stand in, so every stand-in follows the name it replaces, in the
  same commit, and the job says which `setattr` targets change module).
- Type-check baseline (`docs/typecheck-baseline.json`): **filer 52**, content_check 9, ocr 8, router 2; the whole is
  206 errors in 25 files.
- `tools/vocab_report.py` `INPUT_PATHS` (107-114): `tracker/templates.py`, `tracker/content_check.py`,
  `tracker/manifest.py`, `tests/routing_cases.py`, `tools/corpus.py`, `tools/vocab_report.py`. A job that moves the
  matcher out of content_check (keywords.py) must add the new home to `INPUT_PATHS` in the same commit and rebuild the
  report, with counts and hits unchanged. The carry-forward also asks for `tests/samples.py` (below).

**What is settled:**
- **Behaviour does not change** (SPEC-architecture section 6; P313). No routing change, no change to what a person
  sees, no change to which file goes where. `tests/golden/` is unchanged by every job, and each job's "accept when"
  says so. The vocabulary report's counts and hits are unchanged.
- **Q-B is built as P313 says:** today's behaviour is kept. The re-send road still parks an across-household document
  without a shortlist (`candidates=""`); the one folded road (`_settle`, A-3) carries that difference as a named
  parameter, and the question stays Jason's. A-3's table-driven test pushes the same drop through both roads and
  asserts today's rows, the difference included, so a later answer to Q-B is one visible edit.
- **The office backtest.** `docs/backtest-baseline.json` records no agreement yet (SPEC-architecture section 4.1,
  item 11), and the plan says phase 4 needs the office baseline first because it moves routing code. Jason has been
  asked whether phase 4 may build on the branch now, with the office backtest run before phase 4 merges to `main` (on
  the build before phase 4 and on the build after; agreement must not move), or must wait for the baseline. **Write
  the SPEC either way.** For each job, say plainly whether it moves routing code (the matcher, the keyword fold, the
  router, the catalog, the reading) or not, and put the office backtest in the "owed to the office PC" section with
  the exact commands (`tools/backtest.py run` and `check`, and `tests/test_real_corpus.py` with `TRACKER_REAL_CORPUS`
  set) and when each runs.
- **The whole suite runs once per job** (section 9: this phase reaches the engine), on both interpreters, with
  `-n auto`. **Before that, the pre-existing lock leak must go**: `tests/test_locking.py::test_two_takes_in_one_clock_tick_write_two_tokens`
  leaves `locking._unreleased` holding a path, and a `tests/test_resident.py` engine test in the same xdist worker
  retires with `engine retired: lock-left` (carry-forward; `ORCH/jobs/P3.6/probe/`). The fix is test-only: a stand-in
  on `locking._unreleased` in that test, as test_locking 1385/1402 and test_resident 251 do. Make it the first
  requirement of the first job, with its own test that fails before (run the two files in one process, in that
  order) and passes after.
- **A-1's order** is the plan's: `copies.py`, `intents.py`, `inbox.py`, `readme_ack.py`, `actions.py`. The filer keeps
  the household pass and the decision (about 3,600 lines). Each new module gets its row in `tests/test_layers.py`'s
  table (layer and domain) and its node in the curated map; each module that moves layers moves in that table with a
  decision row. Decision rows start at **P329**, in `pilot/DECISIONS.md` after P328.
- **A-5:** `keywords.py` (content_check 326-1368 per the plan; re-measure) and `verdicts.py` (`ContentCache`) at L2.
  content_check keeps the one reading. Say what each move does to the vocabulary report and to `INPUT_PATHS`.
- **A-6:** `reader_child.py` at L2 (ocr 1008-1898 and `content_check.in_a_child` per the plan; re-measure). It is the
  one job here that certainly carries the **`windows` label**: the child process and its supervisor are
  Windows-sensitive (the kill-on-close job object). Say what the office's Windows check runs for it.
- **A-8:** `candidates` as `tuple[str, ...]` and an `Op` `TypedDict`. Most of filer's 52 baseline errors are on this
  path (`"object" has no attribute "candidates"`, `Path | None` arguments). Say which job lowers which entries, with
  `typecheck.py update` in the same commit; a job that moves code carries its baseline entries with it, and no file
  may gain an error.
- **A-10:** a person's refusals typed inline, the same sentence several times: name each once (the plan's `_here`
  helper in copies, A-1 step 2). The words do not change; `test_single_source`, `test_errors` and the said-sentence
  guards (J5) hold every copy.
- **E-6:** `conftest.py` into plugins, one per concern, registered in `conftest.py`'s `pytest_plugins` or by the same
  mechanism. The autouse fixtures keep their scope and order; the collected ids do not change; the agreement fixture
  (rebuild and check after every test) keeps running everywhere it runs today. Say how the job proves that.
- **The test splits follow the modules** (E-3): `test_filer.py` and `test_content_check.py` split with the moves
  (`test_copies.py`, `test_intents.py`, ... or names you justify). A test moves by cut and paste, keeping its name;
  the collected ids change only by file. Shared fixtures go to a helper module named once by assignment, as P3.4 did
  with `tests/store_helpers.py`.
- **The facade-removal job is last.** If filer, content_check or ocr re-export moved names for a while, the last job
  removes them and points every reader at the new home (P2.13 and P2.14 are the model).

**What earlier phases give this phase:**
- **Start with the type burn-down** in the modules this phase moves: filer first (52), then content_check (9), ocr
  (8). The first job lowers the baseline for exactly those, or say why a later job does it with the move.
- **The patch-site lists** (above) and `patch_sites.py check` in every gate. The tool's written limits are in its
  docstring; a from-import copy is read by hand.
- **The golden recordings** (`tests/golden/`) are unchanged by every job.
- **The state register** (`tracker/resident.py`): a module-level name a job moves keeps its `(module, name)` key in
  step, in the same commit. filer's per-drop state and ocr's could-not-start list are phase 7's (A-11, A-7): move the
  code that reads them, not the state's ownership, and say where each ends up.
- **The layer table and `CALL_TIME_CYCLES`** (`tests/test_layers.py`). Say what each move does to the cycles
  (filer ↔ scanner closes through `_rescan()` at call time, P313's Q-A) and give each CLAUDE.md change as a
  requirement with its exact old and new text. CLAUDE.md's import-direction bullet names the filer.
- **The `COMPOSERS` set** (P3.7, `tests/test_layers.py` 480): `{filer, households, manifest, reminder, scanner}`. The
  filer composes 11 events today; a job that moves a composing write into `intents.py` or `actions.py` moves the name
  in `COMPOSERS` in the same commit with a decision row, and no door module may join it.
- **The admission pin** (`tests/test_admission.py`, `ADMISSION_PIN[6]`, 260 parts): the closure reaches `layout`,
  `bounds`, `ledger`, `records`, `reasons`. A phase 4 move that touches any of those changes a digest; say so, and
  re-pin under 6 only for a part that moves without a rule changing (a raised version is never this phase's).

**Carried forward** (`ORCH/carry-forward.md`; take each into the SPEC, or say in one line why not):
- *Phase 4 items* (its section "Phase 4 (the sorting engine)", 148 onward): `tests/samples.py` into `INPUT_PATHS`;
  the router's "for one release" wording (router 154-156, 191-195, curated 41) and router 121's
  `tracker.content_check.Evidence`; `OTHER_DOCUMENT` and `PREPARED_DIR_NAME` still reached through the filer in four
  test lines; the filer's curated note's older wording about `holds_the_row` (P3.5); the lock leak (above).
- *Any-phase items* this phase reaches: the sections "Any phase that moves a module" (26, 33), "Any phase that adds or
  moves module state" (61), "Any phase" (71), "A tools job (any phase)" (140), and the phase-3 notes at the end of
  the file that name a phase-4 file. Read them and decide.

**Rules to keep:**
- Builder tier by PROMPT-refactor section 1.3: the filer moves, `_settle` (A-3) and `reader_child` (A-6) are Opus;
  well-specified moves with exact lists may be Sonnet. Each job is one session, the jobs are in landing order.
- Flat modules in `tracker/`, never a subpackage (section 5.1).
- The `windows` label only for a job that touches the held engagement lock, the atomic replace or path handling, or
  a Windows-only test. `copies.py` (naming, room, copy and move) and `intents.py` (write-ahead intents) very likely
  do: say for each job whether it does, and what the office's `run_checks.ps1 -Tests ...` list is.
- Test lists: each job's gate is the whole suite (above), plus ruff, `repo_map.py check`, `vocab_report.py check`,
  `typecheck.py check` and `patch_sites.py check`.
- Never change the standing rules' wording (`STANDING_RULES` in `tracker/__init__.py`; `test_single_source` holds
  every copy). CLAUDE.md edits this SPEC names are authorized, each with exact old and new text.
- The hard rule holds everywhere: no generative AI reads a client document or moves a client file; every routing
  decision stays deterministic.

Return the job list (id, title, tier, depends on), and end with a report message on this board.
~~~~

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
| J4 | Stand-ins that cannot silently miss; recordings | opus | landed as it is (Jason, 2026-10-14) | 4bb2b8f | 6 |
| J5 | Engine state between commands; sender check; typed sentences | opus | landed (review 1 clean) | f1a6b4c | 1 |
| J6 | The type checker; the Windows build's missing check | opus | landed (review 1 clean) | 286b535 | 1 |

## Phases 2-7

Each phase's SPEC (pilot/SPEC-architecture-p<N>.md) is written when the phase before has landed.

| Phase | State |
|---|---|
| 2 Types and shared low layers | landed (14 jobs; last landing 144c5d2; no facade left) |
| 3 The record | landed: P3.1-P3.9, last 68b9212 (P3.8's office verify owed before main) |
| 4 The sorting engine | SPEC being written (base 68b9212); builds wait on Jason's backtest answer |
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
| P3.8 | The `released` defect; `ADMISSION_VERSION` 6 (office `verify` before merge) | opus | landed (review 1 clean); office verify owed | 326beeb | 1 |
| P3.9 | The admission's names read from their home | sonnet | landed (review 2 clean) | 68b9212 | 2 |

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
