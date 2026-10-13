# Prompts — the build loop for SPEC-architecture

These are the standing instructions for every subagent that builds the
refactor in [`SPEC-architecture.md`](SPEC-architecture.md) (P312). The
orchestrating session starts each subagent with a short prompt that names its
role, its job and the paths below; the subagent then reads **section 2 of
this file and its own role's section**, and nothing of any earlier session's
transcript. Every role is a fresh agent: it knows only what the files say.

The orchestrator gives every subagent these values:

| Name | What it is |
|---|---|
| `REPO` | the checkout, `/home/user/Tax-Info-Request-List-Pilot` in the cloud session |
| `BRANCH` | the one branch every job's commits go on |
| `ORCH` | the loop's working folder outside the repository: `jobs/<job>/handoff.md`, `review-<n>.md`, `baseline/`. Never committed. |
| `PY311`, `PY314` | the two test environments (the floor interpreter and the office's), installed from `requirements.lock` and `requirements-nodeps.lock` with `--require-hashes` |
| `JOB`, `SPEC`, `SECTION` | the job's id, the SPEC file that holds it, and its section |
| `BASE` | the commit the job started from |
| `TIER` | `sonnet` or `opus`, the builder tier section 1.3 chose |

## 1. The loop (the orchestrator's part)

### 1.1 Per phase

1. **Tranche 1** (phases 0 and 1, jobs J1 to J6) is already specified in
   SPEC-architecture section 8. Every later phase first gets its own SPEC,
   `pilot/SPEC-architecture-p<N>.md`, written from the code as it is at that
   moment, because line numbers drift as jobs land.
2. **Write:** a SPEC writer (Opus, high effort, section 3) writes the phase
   SPEC.
3. **Review:** a SPEC reviewer (Opus, high effort, section 4) checks it
   against the code. The writer revises against the numbered findings; at most
   two rounds, then the orchestrator settles what is left or stops and asks
   Jason.
4. The orchestrator reads the phase SPEC, commits it with the map updated,
   and runs its jobs in order.

### 1.2 Per job

1. **Build:** the builder at `TIER` (section 5).
2. **Review:** Opus at high effort, never the agent that built (section 6).
   If there are no findings, the job is done.
3. **Rebuild:** the builder's tier fixes the findings and nothing more
   (section 7), then the job goes back to step 2.
4. **Escalate:** a finding that survives one rebuild is fixed by an Opus fixer
   (section 8). If that fix also fails review, **stop the loop and tell
   Jason**, with the finding, the two attempts and the reviewer's evidence.
5. **Land:** when a review has no findings, the orchestrator pushes `BRANCH`.
   It adds the job's row to SPEC-architecture section 13 (who built, rounds,
   commits, anything owed to the office PC), and updates the map in that
   commit.

At most six review rounds per job; a seventh means the job is stuck, and the
loop stops and tells Jason.

### 1.3 Which tier builds

**Opus** builds a job when any of these holds; **Sonnet** builds the rest
(Jason, 2026-10-13: "Have difficult builds be done by opus"):

- (a) it moves code out of `filer.py`, `store.py`, `api.py`, `runner.py`,
  `content_check.py`, `ocr.py`, `app/main.js` or `app/renderer/app.js`;
- (b) it touches the admission, `store.record` or the ledger's write path,
  the engagement lock, the atomic replace, or the reading child;
- (c) it builds a guard or a tool that derives facts by parsing source (an
  AST walk, a parse of JavaScript);
- (d) it changes a Windows-only script that cannot be run in the cloud;
- (e) its SPEC section says Opus.

A rebuild runs on the builder's tier. Reviews, SPEC writing and SPEC review
are always Opus at high effort; builds and rebuilds run at the default
effort.

### 1.4 Parallel or in order

Jobs run one at a time on `BRANCH`, in their SPEC's order. Almost every job
edits the same guard files (`test_single_source.py`, `test_shell.py`,
`test_api.py`, `test_layers.py`, the map), so parallel builds would mostly
buy merge conflicts, and a review must see one job's diff alone.

### 1.5 Resuming

If the orchestrating session ends, a new one resumes from the files alone:
SPEC-architecture section 13 (the ledger), `git log BASE..` on `BRANCH`, and
this file. A job with commits but no ledger row is reviewed again from round
1.

### 1.6 The coordination board

The orchestrator and the subagents talk through one board, `ORCH/board/`
(Jason, 2026-10-13: "establish a coordination board for you to orchestrate
and communicate with subagents"). It lives beside the loop's working files,
not in the repository: it changes several times per job, and the lasting
record is the ledger (SPEC-architecture section 13) and the commits.

| File | Who writes it | What it holds |
|---|---|---|
| `STATUS.md` | the orchestrator only | the phase, every job with its state (`queued`, `building`, `reviewing`, `rebuilding`, `fixing`, `passed`, `landed`, `blocked`, `question`), its tier, its base commit and its round |
| `NOTICES.md` | the orchestrator only | what every agent must know now: an environment fact, a baseline quirk, a decision taken since the SPEC was written. Newest first, dated. |
| `threads/<JOB>/` | each agent adds files; nobody edits another's | one numbered file per message: `<NNN>-<role>-<kind>.md`, where kind is `brief` (orchestrator to agent), `report` (agent's summary at the end), `question` (an agent needs a decision), `answer` (the orchestrator's reply), `next` (something a later job must know) |

**The protocol.**

1. At the start, every agent reads `NOTICES.md`, `STATUS.md` and its job's
   whole thread, then this file's section 2 and its role's section.
2. An agent never edits `STATUS.md`, `NOTICES.md` or another agent's message.
   It adds its own message with the next free number.
3. **A question stops the agent.** Where the SPEC does not settle something
   and guessing would risk behaviour or a standing rule, the agent writes a
   `question` message (what is undecided, the options, what it recommends,
   what it has already done, and the state of the working tree), commits
   nothing half-done, and returns `question`. The orchestrator writes the
   `answer` (or asks Jason first, when the decision is his), and a fresh agent
   of the same role continues from the thread and the working tree.
4. At the end, every agent writes a `report`: its outcome in five lines or
   fewer, and the path of its full file (handoff or review).
5. Anything a later job must know (a pin that moved, a name that is now
   public, a trap) is a `next` message. The orchestrator copies what matters
   into `NOTICES.md` and into the next phase's SPEC.

## 2. Common to every role

**The board first.** Read `ORCH/board/NOTICES.md`, `ORCH/board/STATUS.md` and
your job's thread `ORCH/board/threads/<JOB>/` before anything else, and end
with a `report` message there (section 1.6).

**The hard rules.**

- No generative AI reads a client document. You work on code and made-up
  test data only (`tests/samples.py`, `tests/irs/` blank forms). Never point
  anything at a real clients root; the tripwire (decision 185) fails a run
  that does.
- The four standing rules (`tracker/__init__.py`, `STANDING_RULES`), the
  layer table in `tests/test_layers.py` and the single-source tests hold
  after every commit.
- Behaviour does not change unless your job names the change. A move moves
  code byte for byte, with its words.

**Git.**

- Work in `REPO` on `BRANCH`. Commit locally; **never push** (the
  orchestrator pushes). Never rebase, amend, squash or force; never touch
  another branch; never commit files outside your job's scope.
- Commit subject: `SPEC-architecture <JOB>: <what the commit does>`.
  The body says what changed and why, which requirements it meets (R-numbers)
  and the gate commands run with their last line. It ends with the
  attribution lines your own session's instructions give, so the
  Co-Authored-By line names the model that wrote the commit. With none given,
  it ends with these two lines:

  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01182LCMMNQ3Vg2tyyuf89VK
  ```
- Never write a model identifier (a `claude-...` name) into anything
  committed.

**The environment.**

- Run Python through `PY311/bin/python` and `PY314/bin/python`: tests as
  `<py> -m pytest -q -p no:cacheprovider <files>`, one process per test file
  and both interpreters (start them side by side). `node` is on the path.
  Do not install anything into the two environments except where your job
  adds a lock file, and then only that lock, with `--require-hashes`.
- Windows-only steps (PowerShell, `.bat` files, job objects, Task
  Scheduler) cannot run here. Build them carefully, test what a test can
  reach, and list every hands-on step as **owed to the office PC** in your
  handoff, with the exact command.
- **The baseline:** `ORCH/baseline/` records the tests that fail or skip on
  the untouched tree in this environment. A test in that list passes your
  gate if it fails the same way as before. Any other failure is your job's.
- Run the whole suite only when your job says so.

**The gate, before every commit that ends a piece of work.**

1. Delete dead code in the files you changed: unused imports and locals,
   commented-out code, names nothing uses, and debug prints.
2. The job's named test files, under both interpreters.
3. `PY314/bin/python -m ruff check .`
4. `PY314/bin/python tools/repo_map.py update`, then `... check` (after
   `git add`-ing any new file, and after editing `docs/repo-map.curated.json`
   for any changed purpose, enforcer or curated edge).
5. `PY314/bin/python tools/vocab_report.py check` when a catalog, the
   matcher or a typed case changed.
6. After J4: `PY314/bin/python tools/patch_sites.py check`. After J6:
   `PY314/bin/python tools/typecheck.py check`.

**Reading.** Use `python tools/repo_map.py show <file>` for one module's node,
and read code by line range or by searching. Do not read
`docs/repo-map.md`, `docs/ROADMAP.md` or `pilot/DECISIONS.md` whole; search
them for the decision or topic.

**Decision rows.** A job that needs a decision row takes the next free
number in `pilot/DECISIONS.md` (`| P<n> | <date> | <decision> | <why> |`),
cites the SPEC section, and adds it in the same commit as the change it
records. Never renumber or remove a row.

**Words.** Plain sentences in the repository's own style. Module docstrings
carry the reasoning: the trade-off, the rejected alternative, the rule
upheld. Tests are named as the claim they make.

## 3. SPEC writer (Opus, high effort)

You write `pilot/SPEC-architecture-p<N>.md`, the buildable SPEC for phase N.

Read: SPEC-architecture sections 4, 5, 6 and phase N's paragraph in section 9;
the appendix findings that paragraph cites
(`pilot/AUDIT-2026-10-13-architecture.md`); section 11's question for the
phase and P313's answer to it; SPEC-architecture section 13 (what has
landed); then the code at `HEAD` for every finding. Re-measure at `HEAD`:
the appendix's line numbers are from `2741665`.

Write, in this order:

1. **The answer:** what the phase does, in plain English, in under fifteen
   lines.
2. **What it relies on:** the decision rows and landed jobs.
3. **The jobs**, each sized to one build session, in landing order, ids
   `P<N>.<k>`. Each has:
   - title, cost (S/M), **builder tier** with the reason (section 1.3), the
     findings, what it depends on;
   - numbered requirements `R<N>.<k>.<m>`, each one checkable. Name the
     functions and constants by name, give line ranges at `HEAD`, and say
     what stays the public surface and what the facade re-exports;
   - the **pin-move list**: every test line that names a file, function or
     import set the job moves (grep for them at `HEAD`, including
     test_layers' import sets and allow-lists, test_single_source's file
     reads, test_repo_map's enforcers, and test_reasons' tail readers);
   - the **patch-site list**: `tools/patch_sites.py report <module>` for every
     module code leaves (once J4 has landed);
   - **tests to run**: each changed module's own test file, the own test file
     of every module that imports a changed one, the guard files
     (`test_layers`, `test_single_source`, `test_repo_map`, plus
     `test_tripwire` and `test_errors` when tests or error wording change).
     Name the whole suite only when the job reaches the sorting engine;
   - **accept when**, including "every recording in `tests/golden/` is
     unchanged" for a move.
4. **The facade-removal job last:** points the remaining importers and
   patches at the new homes and deletes the re-exports the phase added.
5. **Risks**, and anything the phase cannot do here (office PC steps).

Rules: no job changes behaviour unless the main SPEC or P313 names the change;
no job changes `SCHEMA_VERSION` or `ADMISSION_VERSION` (if one would have to,
say so and stop); keep each job's test list as short as Jason's rule allows
(CLAUDE.md, "Test minimally"); flat modules in `tracker/`, never a
subpackage (main SPEC 5.1).

Return the list of jobs: id, title, tier, depends on.

## 4. SPEC reviewer (Opus, high effort)

You check a phase SPEC before anything is built from it. Read the phase SPEC,
the main SPEC's sections 5, 6 and the phase's paragraph in section 9, then
verify against the code at `HEAD`:

- every function, constant, file and line range the SPEC names exists where
  it says;
- every requirement is checkable, and the jobs together carry out everything
  the phase paragraph and its findings ask for (say what is missing);
- no job changes behaviour unless it names the change and the main SPEC or
  P313 allows it;
- each pin-move list is complete (grep for the file and function names
  yourself); each tests-to-run list includes every importer's own test file;
- each tier follows section 1.3, and no job is bigger than one session;
- the order respects the dependencies.

Write numbered findings `S<n>` to `ORCH/spec-p<N>/review-<r>.md`, each with
the SPEC line it concerns, what is wrong, the evidence, and the fix. A
style preference is a note, not a finding.

## 5. Builder (`TIER`)

1. Read section 2, your job's section in `SPEC`, the main SPEC's section 6,
   and the appendix findings your job cites. Run
   `python tools/repo_map.py show` for each file you will touch.
2. **Before any edit**, run your job's named tests on both interpreters and
   write the counts (passed, failed, skipped, per file) to
   `ORCH/jobs/<JOB>/before.txt`.
3. Build exactly the requirements. Where the SPEC is wrong about the code
   (a name moved, a line range is off), follow the SPEC's intent and record
   the difference in your handoff. Where carrying out a requirement would
   change behaviour the SPEC did not name, or break a standing rule, **stop
   and ask** on the board (section 1.6, step 3) and return `question`; do not
   improvise policy. Return `blocked` only when the job cannot be done here
   at all (a tool missing, the SPEC impossible), with the reason.
4. For a move: retarget the patches first (its own commit), then the move with
   the facade and its identity test, then the importers and pins. Each is a
   commit of its own.
5. Run the gate (section 2). Commit.
6. Write `ORCH/jobs/<JOB>/handoff.md`:
   - **Commits:** each hash and subject.
   - **Requirements:** each R-number, done or not, with where.
   - **Tests:** before and after counts, per file and interpreter, and the
     last line of each gate command.
   - **Differences from the SPEC**, and why.
   - **Owed to the office PC:** the exact steps, or "none".
   - **Read first:** what the reviewer should look at first.
7. Return the structured result the orchestrator asks for.

## 6. Reviewer (Opus, high effort)

You did not build this job. Your job is to find what is wrong with it, with
evidence, before it lands.

1. Read section 2, the job's section in `SPEC`, the main SPEC's section 6,
   the builder's `ORCH/jobs/<JOB>/handoff.md` and every earlier
   `review-<n>.md` for this job.
2. Read the change itself: `git log BASE..HEAD` and `git diff BASE..HEAD`.
   Do not trust the handoff's claims; check them.
3. Check each requirement and each acceptance line against the diff.
4. Run, yourself, the job's named tests on both interpreters and every gate
   step, and compare with `ORCH/baseline/` and the builder's `before.txt`.
5. Look for: a behaviour change the job did not name; a moved name whose
   patches or text pins were not moved with it; a guard or pin made weaker
   (fewer files read, a looser assert, a test deleted); a layer, decision row
   or map entry missing; a file changed outside the job's scope; dead code or
   debug output left in; a standing rule put at risk; a commit that mixes a
   move with a change.
6. For each earlier finding still listed as open, say whether it is resolved,
   with the evidence.

**A finding** is a defect against the SPEC, section 2's rules, or the
standing rules: an unmet requirement or acceptance line, a behaviour change
not named, a test or gate failure not in the baseline, a weakened guard, a
standing-rule risk, leftover dead code, an unretargeted patch, a missing
layer row, decision row or map entry, or an out-of-scope change. Give each a
new id `F<round>.<n>`, a severity (`blocking` or `minor`; both must be fixed),
the requirement or rule it breaks, the file and line, the evidence (a command
and its output, or the lines), and the fix. **A note** is anything else (a
better design, a style preference, an improvement for a later phase). Notes
never block and never start a rebuild.

Write `ORCH/jobs/<JOB>/review-<round>.md` with the findings, then the notes,
then the commands you ran with their last line. Return the structured
result.

## 7. Rebuilder (the builder's tier)

Fix exactly the findings you are given, and nothing more. Read section 2,
the findings in `ORCH/jobs/<JOB>/review-<round>.md`, and the job's section in
`SPEC`. For each finding: fix it, or, if the reviewer is wrong, say why with
evidence (the next reviewer judges). Rerun only the tests the fixes touch,
on both interpreters, and the gate steps 3 to 6. Commit as
`SPEC-architecture <JOB>: review <round> fixes (<finding ids>)`. Append a
"Round <round> fixes" part to the handoff: each finding, what was done, the
commit, the tests run. Return the structured result.

## 8. Fixer (Opus)

A finding has survived one rebuild. Read section 2, the job's section, every
review file and the handoff's fix parts for this job. First write, in the
handoff, why the earlier fix did not hold. Then fix it at its root and work as
a rebuilder (section 7) for the findings you are given, committing as
`SPEC-architecture <JOB>: Opus fix (<finding ids>)`.
