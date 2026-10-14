# SPEC-architecture phase 3: the record

Written by the SPEC writer and measured at `144c5d2` (the phase's base, P2.14 landed). Every line number below is at
that commit unless a job says it is measured after an earlier job. Round 2: revised against review 1
(`ORCH/spec-p3/review-1.md`, S1-S11 and N1-N3) and the orchestrator's answer to it (`threads/P3/003`). Round 3:
revised against review 2 (`ORCH/spec-p3/review-2.md`, S12-S21 and N4-N6) and the orchestrator's settlement of it
(`threads/P3/006`). A check of round 3's fixes followed (`threads/P3/009`): no blocking finding, and the orchestrator
settled its three minor ones on 2026-10-14 (S22, a `was` too large for the database, is a row of P3.8's table; S23
corrects R3.8.5's citation and puts its held-row run in test_store; S24 is moot under option (A)). Jason answered Q1
on 2026-10-14: "a - the full rule" (`threads/P3/008`), so P3.8 builds option (A). The SPEC reviewer's findings are in
`ORCH/spec-p3/review-<r>.md`.

## 1. The answer

Phase 3 takes the record's four jobs out of the 4,149-line store and gives each one home, without changing what any of
them does - except for one named defect, fixed in its own job, as Jason chose (Q1).

- `admission.py` (L1): the one rule every line of a record meets, its version and its sentences (B-1).
- The admission becomes one function per event family behind an explicit `if/elif` (B-7), and the pin learns to see a
  class's members.
- `store_check.py` (L1): the gate (`check`) and the export.
- `verify.py` (L3): the read-only firm-wide proof, which reads the registry and the index and so belongs above them.
- One keyed fold in the ledger (B-9): `_recorded_learned` goes, `_recorded_statuses` becomes a view of it.
- The API's three hand-built record events move to the household and request-list writers, and a guard keeps
  `ledger.new(` out of the door (B-4).
- The `released` defect: a `released` line's `was`, and the retired hand-over's, are held to the rule, and a hand-over
  must carry a key. This alone raises `ADMISSION_VERSION` to 6 (P3.8; Jason chose the full rule, Q1).

`SCHEMA_VERSION` (20), every golden recording, the catalog, the matcher, the router, the vocabulary report's counts and
the backtest baseline do not change.

## 2. What it relies on

**Decision rows:**
- 101 and P321: the store is narrow, and its load set is an exact pin.
- 104: the request list's writes live in the manifest.
- 113 and 136: the taught words, and one request whatever its case.
- 129 and 132: the hand-over's retirement, and `released`.
- 137, 187 and P292: one admission, one malformed-line sentence, a typed change refused as a change.
- 159: the checkpoint, `verify`.
- 188: accepting a folder's name (`ACCEPTED_KEY`).
- 209 R3b: the admission version; a raised version re-judges applied lines once.
- P310: mypy, dev-only. P312 and P313: the loop, and behaviour does not change.

**Landed jobs:**
- J1: `ADMISSION_PIN` follows the closure; `names_bound_in` (B-2).
- J4: `tools/patch_sites.py` and `tests/golden/`.
- J5: the state register (`tracker/resident.py`).
- J6: `tools/typecheck.py` and the baseline (215 errors in 25 files at `144c5d2`).
- P2.11: the event `TypedDict`s (ledger 568-683). P2.13 and P2.14: no facade is left.

**SPEC-architecture:** section 5.1 (flat modules, a move is a move), 5.2 and 5.3 (`admission.py` L1, `store_check.py`
L1, `verify.py` L3, one door into the record), section 6 (behaviour does not change), section 9 (phase 3's paragraph);
the audit's B-1 (482), B-4 (615), B-7 (689) and B-9 (732).

### 2.1 Where this SPEC departs from section 9's paragraph, and why

| Item | What section 9 or the audit asks | What this SPEC does | Why |
|---|---|---|---|
| **No re-export facade** | Section 5.1: the old module re-exports what moved until a last job removes it | Store imports back, by name, only what store itself uses (`StoreError`, `KIND_*`, `ADMISSION_VERSION`, `MALFORMED_LINE`, `UNKNOWN_EVENT`, the two admission functions; `check`/`export`/`verify` only inside its `__main__`). No `# noqa: F401` line is written. Every reader of a name store does not use is retargeted in the job that moves it. P3.9 retargets the tests' reads of the admission's own names. | A from-import store uses is not a facade and needs no removal. Readers of `REFUSED_CHANGE` and `ALSO_IN` (one test file, one pin, one comment) are few enough to retarget at once. The stand-ins on `store._refuse_a_malformed_line` (five) must keep reaching `store.record`, which a bare-name call through store's own import does. |
| **`manifest.accept_folder_name`** | The audit names `manifest.accept_return_name(...)` | `manifest.accept_folder_name(conn, return_dir, household, *, return_name=None)` | The line it writes names the household for a household-scope accept and both names for a return-scope one. "Return name" would misname the first. It matches the command it serves (`accept-folder-name`). |
| **The six unused event types** | Carry-forward: give each a signature or say why not | They stay descriptions (R3.3.6) | The admission reads untrusted lines (a signature would claim a shape the gate has not proved yet), and `ledger.new` returns `dict` by design. |
| **`test_store.py` split** | `test_admission.py`, `test_store_check.py`, `test_verify.py` | Those three, plus `tests/store_helpers.py` for the fixtures and helpers they share with test_store | test_suite_shape forbids a test file importing another. `tests/passes.py` is the precedent for a shared fixture module. |

### 2.2 Carried-forward items (`ORCH/carry-forward.md`)

- **The pin does not see a class's members** (`Override.ALL`, `Override.RETIRED`, read by `records.rule_row_fault`).
  Taken in P3.3 R3.3.1. The walker widens and re-pins under 5. Measured: exactly two keys join
  (`tracker.bounds.Override.ALL`, a tuple; `tracker.bounds.Override.RETIRED`, a dict), and no digest changes.
- **Six event types nothing takes** (`RowEvent`, `ScannedEvent`, `ReleaseEvent`, `KeywordEvent`, `HouseholdEvent`,
  `DraftEvent`). Taken in P3.3 R3.3.6: each stays a description, for the reason in 2.1, and ledger's docstring says so.
- **`Final` key constants.** Not reached: phase 3 types no more of the apply path than P3.6's `key` parameter, which
  reads no key constant.
- **The `released` defect.** Taken as P3.8.
- **Pin each event type's keys to the `*_KEY` constants.** Taken in P3.6 R3.6.6, read with
  `typing.get_type_hints(T, include_extras=True)` and `get_origin(hint) is NotRequired`, never `__required_keys__`.
- **`monkeypatch.setitem` outside patch_sites.** Taken: at `144c5d2` the only `setitem` targets are `sys.modules`,
  `api.COMMANDS` and `reasons.SHORT_REASONS`. Phase 3 moves none of them; each move job greps `setitem(` for what it
  moves.
- **Review 6's four patch_sites limits (F6.1-F6.4).** Taken as a hand check in every move job: the tool's report plus a
  grep of `tests/` for each moved name (string-form `setattr("tracker.x.y", ...)`, a store through a parameter, an
  `import` helper). At `144c5d2` the string-form grep finds none for any name this phase moves.
- **The register derivation's blind spots.** Not reached: no job adds or moves module state. `V_BY_KIND` moves (P3.5)
  but is a dict nothing mutates; the store's connection globals are phase 7's (B-12) and stay. P3.2, P3.4 and P3.5 run
  `test_resident` anyway.
- **The mypy upgrade rule.** Not reached: phase 3 upgrades no tool.
- **`repo_map.py` reading `ast.AnnAssign`.** Not needed this phase: no annotated module-level constant moves (every
  constant that moves is a plain `ast.Assign`), and the one new alias, `Refuse` (P3.3), is written as a plain
  assignment. The tools job stays carried.

## 3. Rules every job follows

**The gate.** Each job runs it before its report, under PY311 (the floor) and PY314 (the office's):
1. dead code deleted in the changed files first: unused imports and locals, commented-out code, a module-level name
   nothing uses;
2. the job's named tests, each file as its own process;
3. `python -m ruff check .`;
4. `python tools/repo_map.py check`;
5. `python tools/typecheck.py check`;
6. `python tools/patch_sites.py check`;
7. `python tools/vocab_report.py check`, in the job that touches manifest (P3.7).

**The map, the docs and the decision rows:**
- `python tools/repo_map.py update` in the same commit as the code, after any edit to `docs/repo-map.curated.json`.
- A new module gets, in the commit that creates it:
  - a curated node (role, and notes carrying the reasoning, as its neighbours' do);
  - a row in `tests/test_layers.py`'s `LAYERS` (with the comment above the layer's set, in its neighbours' form) and
    `DOMAINS`;
  - a line under its layer in `docs/architecture.md`, whose count "forty-three" (line 29) goes up by one per new module
    (forty-four at P3.2, forty-five at P3.4, forty-six at P3.5);
  - a line in `tracker/__init__.py`'s module list (store's line is 32), in the format `- name          : description`;
  - its own `tests/test_<module>.py`;
  - a decision row in `pilot/DECISIONS.md`, in P322's form.
- A new test file or test helper module (`tests/test_admission.py` in P3.2, `tests/test_store_check.py` and
  `tests/store_helpers.py` in P3.4, `tests/test_verify.py` in P3.5) gets a curated node in the commit that creates it:
  a role saying what it holds and notes saying where it came from and why, in the form of `tests/builders.py`,
  `tests/passes.py` and `tests/test_index.py` (the review's N4). `repo_map.py check` passes without one; the node is
  what tells the next reader why the file exists.
- Decision rows, in landing order: **P323** (P3.2), **P324** (P3.4), **P325** (P3.5), **P326** (P3.6), **P327** (P3.7),
  **P328** (P3.8). A job that lands out of order takes the next free number and says so.

**A move is a move:**
- Code moves byte for byte, with its comments and words. The exceptions are the edits a requirement names.
- The new module imports what its moved code reads, by name, so bodies stay byte for byte.
- The old module imports back by name only what it still uses itself. Nothing is re-exported for a reader.
- Every reader in `tracker/`, `tests/`, `tools/` and `docs/` of a name its old module no longer holds is retargeted in
  the same commit.
- A stand-in is read with the job's patch-site list: if a stand-in replaces a name on the old module and the code it
  must reach has moved, stop and ask.

**The admission:**
- The closure is everything `admission_closure()` reaches from `_refuse_a_malformed_line` and `_line_keys_problem`.
  Its keys are `f"{function.__module__}.{qualname}"` for a function, and `f"{reading function's module}.{name}"` for a
  constant read by bare name.
- A job that moves or edits a closure part re-pins it: paste `admission_digests()` under `ADMISSION_PIN[5]`
  (test_store 2807-3842 at the base), and add a comment line above `ADMISSION_PIN` saying what moved and that no rule
  changed.
- If any part's source changes beyond what the job names, stop and ask.
- `ADMISSION_VERSION` stays 5 in every job but P3.8.

**What "Test minimally" means here** (CLAUDE.md):
- A job runs each changed module's own test file, each changed test file, and the own test file of each module that
  imports a changed module where the move reaches it (named per job).
- The guards are always run: `test_layers`, `test_single_source`, `test_repo_map`. `test_tripwire` and `test_errors`
  run where a job changes tests or error wording, which is every job here.
- `test_golden` runs for every job. `test_typecheck` runs where the baseline changes. `test_suite_shape` runs where a
  test file or helper module is added. `test_patch_sites` never runs: the tool does not change.
- Only P3.6 reaches far enough to run the whole suite (its section says why).

**No routing change.** No job edits the router, the catalog or the matcher. P3.7 adds a function to `manifest.py`, an
`INPUT_PATHS` file of `tools/vocab_report.py`. So it runs `python tools/vocab_report.py build` in the same commit, and
the report's counts and hits must come out unchanged. The backtest baseline is not touched.

**Golden.** `tests/golden/` is never re-recorded. Each job's accept-when includes: "`pytest tests/test_golden.py`
passes and every recording in `tests/golden/` is unchanged". Measured at `144c5d2`: no recording holds an admission
sentence or a `released` line's `was`. The one admission-adjacent hit, `handed_over`, is a reply key.

**Windows.** Only the held engagement lock, the atomic replace or path handling earns the `windows` label. Each job says
whether it touches them; none does in a way that changes it (section 6).

**Safety.** Tests use made-up data only, and nothing points at a real clients root (decision 185). Commit signing stays
on. No model identifier is written into anything committed. The standing rules' wording is not touched.

## 4. The jobs, in landing order

| Job | Title | Cost | Tier | Depends on |
|---|---|---|---|---|
| P3.1 | Type burn-down in the store | S | Opus (b) | — |
| P3.2 | `admission.py`: the admission out of the store | M | Opus (a, b) | P3.1 |
| P3.3 | One function per family, by explicit `if/elif`; the pin sees class members | M | Opus (b) | P3.2 |
| P3.4 | `store_check.py`: the check and the export | M | Opus (a) | P3.3 |
| P3.5 | `verify.py` at L3 | S | Opus (a) | P3.4 |
| P3.6 | One keyed fold (B-9) | M | Opus (b) | P3.5 |
| P3.7 | The API's record events to the domain writers; the `ledger.new(` guard (B-4) | M | Opus (a, c) | P3.6 |
| P3.8 | The `released` defect; `ADMISSION_VERSION` 6 | S | Opus (b) | P3.7 (Q1 answered: option (A)) |
| P3.9 | The admission's names read from their home | S | Sonnet | P3.8 |

Every job edits `tests/test_store.py`, `tests/test_layers.py` or the map, so they are built in order. Jason answered Q1
on 2026-10-14 (section 7), so P3.8 lands before P3.9.

---

### P3.1 Type burn-down in the store

- **Cost:** S.
- **Tier:** Opus, by rule (b): R3.1.1 edits `_refuse_a_malformed_line`, and R3.1.3 edits `_apply`, the store's write
  path.
- **Findings:** section 9 ("every phase starts by burning down the type errors in the modules it will move").
- **Depends on:** nothing.

The modules phase 3 moves code out of or into, and their errors in `docs/typecheck-baseline.json` (mypy 2.3.1):

| Module | Errors | In code this phase moves or edits |
|---|---|---|
| store | 16 | 1929, 2131, 3876, 4086 (1), 4087 (5): nine, burnt down here (and 1910, which R3.1.1 would add, is never let in: R3.1.1a) |
| api | 24 | none in `_cmd_mark_shared` / `_cmd_accept_folder_name` (4707-4806) |
| households | 7 | none: 276-290 and 345 are not in the functions P3.7 adds beside them |
| manifest | 6 | none: 1380 is not near P3.7's addition |
| after_install | 4 | none at 159 or in `_check` (667-700) |
| checkpoint | 2 | none: checkpoint is not edited |
| ledger, records, index | 0 | — |

Store's other seven stay, because no job touches them. They are 1105 (`held_read`), 1179 (`_apply`'s caller,
`cursor.lastrowid`), 2673, 2677 and 2679 (`_held_checkpoint`, phase 7's connection globals), and 3705 and 3708
(`_described`, in recover). Each is in a function this phase does not edit.

**Requirements:**

- **R3.1.1** — store.py:1785, `def refuse(problem: str) -> None:` (the nested function in `_refuse_a_malformed_line`)
  becomes `def refuse(problem: str) -> NoReturn:`. store.py:204's `from typing import TypeVar, cast` becomes
  `from typing import NoReturn, TypeVar, cast`. This clears 1929 (`for op in ops`): mypy then knows the
  `refuse(...)` at 1928 does not return.
- **R3.1.1a** — `NoReturn` also lets mypy narrow `stored` to `dict` after the `refuse(...)` at 1907. The call at
  store.py:1910, `records.split_codes(stored.get("note_codes"))`, then becomes a new error (`Argument 1 to
  "split_codes" has incompatible type "Any | None"; expected "str"`), which mypy did not report while it read the code
  after `refuse(...)` as reached with `stored` untyped. The remedy: records.py:324,
  `def split_codes(joined: str) -> list[str]:` becomes `def split_codes(joined: str | None) -> list[str]:`. Its body
  already reads `(joined or "")`, so the annotation now says what the function takes. Its two other callers
  (records 1491, manifest 483) pass a `str` and are unaffected.
  - The rejected alternative is `cast(str, stored.get("note_codes"))` at the call. It would move one digest fewer, but
    it states a type the value does not have (a status may carry no `note_codes`), in the one function whose job is to
    distrust its input. `or ""` at the call was not taken either: `split_codes` already does it, so the call would
    say it twice.
  - Measured on a scratch copy at `144c5d2` with R3.1.1-R3.1.4 and this edit: `typecheck.py check` reads 206 errors in
    25 files (store 7, records 0), and the pin differs from 5 in exactly the two digests R3.1.6 names.
- **R3.1.2** — store.py:3876, in `verify`: `checkpoint.intent(held, key)` becomes
  `checkpoint.intent(cast(sqlite3.Connection, held), key)`, with the comment `# held is not None: vouched came from
  it` at the end of line 3876's statement, or on its own line above it. `verify` is not in the closure. (The same call
  at 2797, in `_prove_against_checkpoint`, where `held` is already narrowed, raises no error and is not edited.)
- **R3.1.3** — store.py:2131, in `_apply`: `seqs[event.get(ledger.KEY_KEY)] = seq` becomes
  `seqs[cast(str, event.get(ledger.KEY_KEY))] = seq`. The admission at 2119 has refused a row event with no str key.
  `_apply` is not in the closure.
- **R3.1.4** — store.py:4086-4087, in the CLI's recover branch: the loop variable `one` (which shadows the Path `one`
  of the CLI's own folder loop) becomes `difference`, in the `for` and in the f-string's five reads. This clears 4086
  (1) and 4087 (5).
- **R3.1.5** — `python tools/typecheck.py update` lowers the baseline by exactly 9 (store 16 to 7; records stays 0).
  It then reads 206 errors in 25 files, and `check` passes.
- **R3.1.6** — Re-pin `ADMISSION_PIN[5]` (paste `admission_digests()`). Two digests change and nothing else:
  `tracker.store._refuse_a_malformed_line` (R3.1.1's annotation) and `tracker.records.split_codes` (R3.1.1a's). The part
  count stays 241. Comment line above `ADMISSION_PIN`: "Pinned again under 5 when P3.1 typed the admission's refusal
  NoReturn and split_codes' parameter str | None: two annotations, no rule changed."

**Pin-move list:**
- `ADMISSION_PIN[5]` in tests/test_store.py (3600-3842): the digests of `tracker.store._refuse_a_malformed_line` and
  `tracker.records.split_codes`, and no other key;
- `docs/typecheck-baseline.json`: store's entry.

**Patch sites:** `report tracker.store` (49 stand-ins in 11 files). None replaces `verify`, `_apply`'s `seqs`, or the
CLI. The five stand-ins on `_refuse_a_malformed_line` replace the whole function, so its annotation does not matter to
them.

**Tests:** `test_store`, `test_records` (R3.1.1a's annotation), `test_typecheck`, `test_golden`; guards `test_layers`,
`test_single_source`, `test_repo_map`.

**Stop and ask:** if mypy reports a new error anywhere other than 1910 (for example, unreachable code after a
`refuse(...)` call), if 1910 is still reported after R3.1.1a, or if the re-pin changes any digest other than R3.1.6's two.

**Accept when:**
- the gate passes;
- the baseline is lower by 9 (206 in 25 files, store 7) and `check` passes;
- `mypy` reports nothing at store.py:1910;
- `ADMISSION_PIN[5]` differs from `144c5d2` in R3.1.6's two digests;
- `tests/golden/` is unchanged;
- nothing else changes.
- **Windows:** no label. Nothing touches the lock, the atomic replace or a path.

---

### P3.2 `admission.py`: the admission out of the store

- **Cost:** M.
- **Tier:** Opus, by rules (a) (code out of `store.py`) and (b) (the admission).
- **Findings:** B-1 (482). SPEC-architecture 5.3: `admission.py` at L1.
- **Depends on:** P3.1.

**What moves.** Into a new `tracker/admission.py`, byte for byte, with their comments (store line numbers at
`144c5d2`; P3.1 adds no lines above them):

| Store lines | Names |
|---|---|
| 305-333 | the `#:` comment and `ADMISSION_VERSION = 5` |
| 357-363 | the KIND comment, `KIND_RETURN`, `KIND_HOUSEHOLD` |
| 377-378 | `class StoreError(RuntimeError)` and its docstring |
| 1688-1705 | `MALFORMED_LINE`, `REFUSED_CHANGE`, `UNKNOWN_EVENT`, `ALSO_IN`, with their comments |
| 1708-1729 | `_line_keys_problem` |
| 1731-2062 | `_refuse_a_malformed_line` (its call-time `from tracker import layout, reasons` at 1777 stays inside it) |

`StoreError`'s three subclasses (`CheckpointNotMade` 381, `StoreUnavailable` 401, `WouldDiscard` 3072) stay in store and
subclass the imported class.

**Requirements:**

- **R3.2.1** — `tracker/admission.py`.
  - Its module docstring says, in its neighbours' form:
    - what it holds: the one rule every line of a record meets before the store applies it or the check, the
      checkpoint's judgment or `verify` trusts it (decision 187), its version (decision 209 R3b), and the two sentences
      a refused line or change is told in (decision 137, P292);
    - why it is its own module: the store is the database, and the admission is a rule about a line. The rule has its
      own version and its own pin, so a module whose whole content is the rule makes "what the admission is" a file,
      and the pin's roots name it;
    - why it sits at L1: it reads the journal's words (`ledger`) and the record's shapes (`records`), which are L1, and
      the bounds (L0); it reads the layout and the reasons at call time, as it did in the store;
    - who asks it: the store (`record`, `_apply`, `_judge`, the check through it), and nothing else at load time.
  - Its imports, and only these:
    - `from __future__ import annotations`, `import json`, `from typing import NoReturn`;
    - `from tracker import bounds, ledger, records`;
    - `from tracker.records import RULE_LIST_FIELDS`, the one name the admission reads through store's from-import
      (it is keyed `tracker.store.RULE_LIST_FIELDS` in the pin at the base).
  - The builder confirms by AST that the moved code reads no other store global. A read of any store name other than
    the moved ones is a stop-and-ask.
- **R3.2.2** — store imports back exactly what it uses. A new line with the package imports at store.py:206-208
  (ruff's isort places it among them; store.py:208 opens the `from tracker.records import (...)` parenthesis, so
  "after 208" would fall inside it - the review's N5):
  `from tracker.admission import (ADMISSION_VERSION, KIND_HOUSEHOLD, KIND_RETURN, MALFORMED_LINE, StoreError,
  UNKNOWN_EVENT, _line_keys_problem, _refuse_a_malformed_line)`, wrapped as ruff's isort settles it.
  - Store keeps importing `RULE_LIST_FIELDS` from records only if it still reads it after the move; otherwise that name
    leaves store's records import.
  - Store does not import `REFUSED_CHANGE` or `ALSO_IN`: nothing in store reads them outside the moved code.
  - Every call stays a bare-name call, so `monkeypatch.setattr(store, "_refuse_a_malformed_line", ...)` still replaces
    what `store.record` calls (the five stand-ins below).
- **R3.2.3** — Readers of the two names store no longer holds are retargeted:
  - tests/test_store.py 1877 and 1880: `store.ALSO_IN` becomes `admission.ALSO_IN`, with
    `from tracker import admission` added to test_store's imports;
  - tests/test_single_source.py 2348: `assert 'ALSO_IN = "also_in"' in tracker["store.py"]` reads `tracker["admission.py"]`.
    Its docstring's "the store's refusal of it" (2333-2334) becomes "the admission's refusal of it". The count at 2347
    (`"also_in"` once across tracker) is unchanged;
  - tracker/ledger.py:233's comment: ``(``tracker.store.ALSO_IN``)`` becomes ``(``tracker.admission.ALSO_IN``)``. It is a
    module-level comment, not part of any closure function.
  - tests/test_errors.py:411's key `("store.py", "_refuse_a_malformed_line")` becomes
    `("admission.py", "_refuse_a_malformed_line")`, its reason unchanged. At the base this entry exempts nothing (the
    review's N3: deleting it raises no finding). It is retargeted, not deleted: its reason records SPEC-190 R2's grant
    ("R2: stays"), and taking a granted exemption away is a decision of its own, not part of a move. The report says
    whether it is live after the move.
- **R3.2.3a** — The two sentences that say where the pin lives follow it to `tests/test_admission.py`:
  - store.py:94, in the module docstring's decision 209 paragraph: "``tests/test_store.py`` pins the source of every
    function the admission reaches" becomes "``tests/test_admission.py`` pins the source of every function the
    admission reaches". The paragraph stays in store: ``admitted_by`` and the re-judging are the store's;
  - store.py:316, inside the `#:` comment that moves with `ADMISSION_VERSION`: "``tests/test_store.py``
    (``test_admission_version_changes_with_the_admission``)" becomes "``tests/test_admission.py``
    (``test_admission_version_changes_with_the_admission``)".
  - Neither is in a closure part (a module docstring, and a comment on a constant the closure does not read), so no
    digest moves.
- **R3.2.3b** — The store's own account of its imports names the admission (the review's S14). store.py:166-168, in
  the module docstring's "What it imports, and why so little" paragraph. Old:

  ```
  **What it imports, and why so little.** ``bounds``, ``records``,
  ``ledger``, ``locking``, ``checkpoint`` and the standard library - nothing
  else of the package, at load time. Everything it holds comes out of the
  ```

  New:

  ```
  **What it imports, and why so little.** ``admission``, ``bounds``,
  ``records``, ``ledger``, ``locking``, ``checkpoint`` and the standard
  library - nothing else of the package, at load time. The admission is the
  one rule every line meets before the store writes or applies it (P323),
  so the store asks it at every write and every read. Everything it holds comes out of the
  ```

  The rest of the paragraph is unchanged, rewrapped as its neighbours are. The module docstring is not a closure part,
  so no digest moves. The same claim's other copies are test_layers' docstring (R3.2.6) and CLAUDE.md (R3.2.7).
- **R3.2.4** — The admission tests move to a new `tests/test_admission.py`, by cut and paste, names kept:
  - the pin and its machinery, test_store 2790-4106: the `#:` comment block from 2790, `ADMISSION_PIN`,
    `names_bound_in`, `admission_closure`, `admission_digests`, `test_admission_version_changes_with_the_admission`,
    `test_the_admission_pin_reaches_the_rules_it_calls`, `SHADOWING_MODULE`, the `shadowing` fixture and the three
    shadowing tests through `test_a_name_declared_global_is_still_the_modules`;
  - the three tests that call the admission directly, take no fixture and read no test_store helper:
    `test_a_moving_line_in_a_households_record_is_refused` (2598),
    `test_the_store_admits_the_accepted_key_with_one_value` (4136) and
    `test_a_related_list_that_is_not_folder_names_is_refused_at_admission` (5372).
  - A fourth fixture-less one,
    `test_an_event_carried_in_also_is_refused_in_the_wording_of_the_line_that_carries_it` (5725), stays in test_store
    in this job: it builds its event with `_a_rule` (test_store 2500), a plain helper test_admission cannot import from
    a test file (test_suite_shape). It moves to test_admission in P3.4, which moves `_a_rule` to `tests/store_helpers.py`
    (R3.4.6). An AST listing of test_store's direct callers at the base finds no fifth.
  - Every other test stays in test_store: it drives the admission through the store's door (`record`, `catch_up`,
    `check`) or takes the store's fixtures. That is a test of the door's wiring as much as of the rule.
  - The moved tests' bodies are unchanged: they read `store._refuse_a_malformed_line`, `store.KIND_HOUSEHOLD` and
    `store.ADMISSION_VERSION`, which store holds by import. P3.9 retargets the admission's own names.
  - `admission_closure()`'s default roots stay `[store._refuse_a_malformed_line, store._line_keys_problem]` (the same
    objects) until P3.9.
  - The new file's docstring says what it pins and why the pin is here: the admission's own file holds the rule, and
    its test file holds the pin.
  - The collected ids change only by file. The builder diffs `pytest --collect-only -q` before and after.
  - test_store's module-level `import ast` (16) is deleted. Outside the moved block its only reader is
    `test_the_store_names_no_reader_at_load_time`, which imports `ast` itself (1107). Measured on a scratch copy with
    this requirement's moves cut (2790-4106, 2598-2607, 4136-4160, 5372-5388): ruff reports F401 at 16 and F811 at 1107, and nothing else. P3.5 then deletes the local import with
    the lines that read it (R3.5.3). test_admission imports `ast` at module level for the moved walker.
- **R3.2.5** — Re-pin `ADMISSION_PIN[5]`. The nine keys `tracker.store.{ALSO_IN, KIND_HOUSEHOLD, KIND_RETURN,
  MALFORMED_LINE, REFUSED_CHANGE, RULE_LIST_FIELDS, UNKNOWN_EVENT, _line_keys_problem, _refuse_a_malformed_line}`
  become `tracker.admission.<same>`, each with the same digest. The part count stays 241. Versions 2, 3 and 4 are
  history and are not edited. Add the comment line: "Pinned again under 5 when P3.2 moved the admission to
  tracker.admission: nine keys follow the module, no digest changed."
- **R3.2.6** — The layer table and the import pins, in tests/test_layers.py:
  - `LAYERS[1]` gains `"admission"`, with a comment above the set: "``admission`` joins L1 with P323
    (SPEC-architecture-p3 P3.2): the one rule a line of the record meets, out of ``store``, which imports it back -
    ``bounds`` (L0), ``ledger`` and ``records`` (L1); ``layout`` and ``reasons`` at call time.";
  - `DOMAINS["record"]` gains `"admission"`;
  - `test_the_store_imports_only_the_bounds_the_record_the_journal_the_lock_and_the_checkpoint` (416) is renamed
    `test_the_store_imports_only_the_admission_the_bounds_the_record_the_journal_the_lock_and_the_checkpoint`. Its
    assert becomes `{"admission", "bounds", "checkpoint", "ledger", "locking", "records"}`, and its docstring gains
    "P323 adds the admission, which is L1 and imports only the bounds, the journal and the record." This rename is a
    claim that changed, so its id changes by name. It is the one exception to "ids change only by file";
  - a new test beside it, `test_the_admission_imports_the_bounds_the_journal_and_the_record`:
    `load["admission"] == {"bounds", "ledger", "records"}` and `call["admission"] == {"layout", "reasons"}`;
  - the module docstring's store paragraph (90-97): "it imports ``bounds`` (P321), ``records``, ``ledger``,
    ``locking`` and (since decision 159) ``checkpoint``" becomes "it imports ``admission`` (P323), ``bounds``
    (P321), ``records``, ``ledger``, ``locking`` and (since decision 159) ``checkpoint``".
  - `CALL_TIME_CYCLES` is unchanged: the admission imports nothing that imports it.
- **R3.2.7** — CLAUDE.md, lines 214-215. Old:

  ```
    (its `__main__` alone reaches `page`); `store` imports `bounds`, `ledger`,
    `locking`, `records` and `checkpoint` and nothing else; `manifest` imports
  ```

  New:

  ```
    (its `__main__` alone reaches `page`); `store` imports `admission`, `bounds`,
    `ledger`, `locking`, `records` and `checkpoint` and nothing else; `manifest` imports
  ```

- **R3.2.8** — Docs and map:
  - `docs/architecture.md`: "forty-three" becomes "forty-four" (29), and an `admission.py` line goes before the store's
    line (84);
  - `tracker/__init__.py`: an `admission` line before `store` (32);
  - a curated node for `tracker/admission.py`, and store's node notes say the admission moved and why;
  - a curated node for `tests/test_admission.py` (section 3): its role, that it holds the admission's pin, its closure
    walker and the tests that call the admission directly; its notes, that they came from test_store with P323 because
    the admission's file holds the rule and its test file holds the pin, and that the tests driving the admission
    through the store's door stay in test_store;
  - decision row **P323**;
  - `repo_map.py update`.

**Pin-move list:**
- tests/test_store.py 1877, 1880 (`ALSO_IN`), and the moved block (R3.2.4);
- tracker/store.py 94 and the moved comment's 316 (R3.2.3a), and 166-168 (R3.2.3b);
- tests/test_store.py 16 (`import ast`, R3.2.4);
- tests/test_single_source.py 2333-2334 and 2348;
- tests/test_errors.py 411;
- tests/test_layers.py 90-97, `LAYERS[1]`, `DOMAINS["record"]` and 416-422.
- The builder greps `tests/` for `"store.py"` and `tracker["store.py"]` reads of any moved text. At the base, 2348 is
  the only file-read pin on a moved line.

**Patch sites** (`report tracker.store`):
- The five stand-ins on `_refuse_a_malformed_line` are test_store 2676, 2694 and 5797, test_after_install 291 and
  test_api 11531. Each replaces store's attribute so that `store.record` writes a line the gate would refuse, then
  undoes the replacement before reading. They keep working because `record` and `_apply` call the name bare through
  store's globals. None moves.
- No other stand-in names a moved name.
- `setitem(`: none on a moved name.

**Register:** no module state moves. `test_resident` runs.

**Tests:** `test_admission` (new), `test_store`, `test_ledger` (the comment), `test_after_install` and `test_api`
(their stand-ins: the two named tests only, `-k` on the test containing test_after_install 291 and the one containing
test_api 11531), `test_resident`, `test_golden`, `test_suite_shape`; guards `test_layers`, `test_single_source`,
`test_repo_map`, `test_tripwire`, `test_errors`.

**Stop and ask:**
- a digest changes;
- the part count is not 241;
- the moved code reads a store name beyond R3.2.1's imports;
- a stand-in on a moved name exists that the report did not list.

**Accept when:**
- the gate passes;
- `ADMISSION_PIN[5]` differs from P3.1's only by the nine renamed keys;
- `store.StoreError is admission.StoreError`, and `issubclass(store.WouldDiscard, admission.StoreError)`;
- `grep -n "noqa: F401" tracker/store.py` finds nothing new;
- the collected ids differ from P3.1's only by file, and by R3.2.6's one renamed test;
- `tests/golden/` is unchanged.
- **Windows:** no label. The admission reads `layout.place_problem` (a path rule) unchanged, moved byte for byte.

---

### P3.3 One function per family, by explicit `if/elif`; the pin sees class members

- **Cost:** M.
- **Tier:** Opus, by rule (b): it restructures the admission.
- **Findings:** B-7 (689); carry-forward (the pin's class members; the six event types).
- **Depends on:** P3.2. Line numbers are in `tracker/admission.py` as P3.2 leaves it. They are given by name.

Two commits: the walker first, so the second commit's re-pin is read against a pin that already sees everything.

**Requirements:**

- **R3.3.1** (commit 1) — `admission_closure()` (tests/test_admission.py, from test_store 3884) also records a class
  member.
  - Where an `ast.Attribute` node's value is an `ast.Name` that resolves, in `names`, to a class whose `__module__`
    starts with `tracker`, the member `inspect.getattr_static(cls, node.attr)` is handled as a module attribute is:
    - a function (unwrapped from `staticmethod`/`classmethod`) whose module starts with `tracker` is followed;
    - a set or frozenset, or a constant of the listed types, is recorded under
      `f"{cls.__module__}.{cls.__qualname__}.{node.attr}"`.
  - The docstring gains one sentence: a member read off a class (decision 187's `Override.ALL`) is part of the rule as
    a module's constant is.
  - A new test on a made-up module (in the form of `SHADOWING_MODULE`, written to `tmp_path_factory`) proves that
    `Box.LIMIT` and `Box.check` are reached from a function reading `Box.LIMIT` and calling `Box.check`:
    `test_a_member_read_off_a_class_is_part_of_the_closure`.
  - Re-pin under 5. Measured: exactly `tracker.bounds.Override.ALL` and `tracker.bounds.Override.RETIRED` join (from
    `records.rule_row_fault`, records 1574), and no digest changes. Comment line: "Pinned again under 5 when P3.3 taught
    the walker a class's members: Override.ALL and Override.RETIRED joined, no digest changed."
- **R3.3.2** (commit 2) — `_refuse_a_malformed_line` keeps its signature, its docstring, its nested `refuse` (with
  P3.1's `-> NoReturn`) and `known`. After `refuse`, the body is:
  1. `_admit_line(event, name, refuse)`: the AT_KEY, ACCEPTED_KEY and line-keys checks that today precede the family
     branches, in their order;
  2. one explicit `if/elif` chain on `name`, in today's order. Each branch is one call:

     | Branch (today's test, unchanged) | Call |
     |---|---|
     | rules (`RULES_CHANGED`, `RULES_IMPORTED`) | `_admit_rules(event, refuse)` |
     | `name in ledger.ROW_EVENTS` | `_admit_row(event, where, refuse)` |
     | `SCANNED` | `_admit_scan(event, refuse)` |
     | `MOVING` | `_admit_intent(event, seq, where, kind, written, refuse)` (holds the `also` recursion into `_refuse_a_malformed_line` and the `ALSO_IN` refusal) |
     | `MOVE_ABANDONED` | `_admit_abandoned(event, refuse)` |
     | `RELEASED` | `_admit_release(event, refuse)` |
     | keywords | `_admit_keyword(event, refuse)` |
     | drafts | `_admit_draft(event, refuse)` |
     | `HOUSEHOLD_CHANGED` | `_admit_household(event, refuse)` |
     | `SHARING_CONFIRMED` | `_admit_sharing(event, refuse)` |

  - A family function takes the arguments its branch reads today, and no others. If a branch reads a name not listed
    here, it takes that name too and the report says so.
  - **Never a dict of functions:** `admission_closure()` follows names, and a table's values would escape the pin.
- **R3.3.3** — Today's closures `a_place`, `a_segment`, `a_code` and `a_row` become module functions taking `refuse`
  first:
  - `_a_place(refuse, where, field, location, *, writes, what="a step", removes=False)`;
  - `_a_segment(refuse, field, label)`;
  - `_a_code(refuse, field, code, what)`;
  - `_a_row(refuse, where, row)`.

  Each makes its own call-time `from tracker import layout` or `reasons` import, as its body needs. Their bodies are
  today's, with the closed-over names now parameters.
- **R3.3.4** — `Refuse = Callable[[str], NoReturn]`, a plain assignment (not an annotated one, so `repo_map.py` reads it),
  with `from collections.abc import Callable`. Every family function and helper annotates `refuse: Refuse`. No new mypy
  error. `typecheck.py check` passes with the baseline unchanged.
- **R3.3.5** — Equivalence, not committed. `ORCH/jobs/P3/admission-equivalence.py` loads P3.2's
  `tracker/admission.py` (from `git show <P3.2's commit>:tracker/admission.py`, into a scratch module) and the new one.
  It runs both over a generated corpus:
  - every family's valid line (from `ledger.new` with the fixtures' shapes);
  - each key of that family, set to each of: absent, `None`, `""`, `0`, `5`, `True`, `[]`, `["x"]`, `{}`, a 2,001-character
    text, a text with a NUL, `"../x"`;
  - `written` True and False, and `kind` return and household;
  - an `also` holding each mutated line.

  For each line it asserts that both admit it, or both raise with the same sentence, each raising its own module's
  `StoreError`: the old copy, loaded as a scratch module, defines a `StoreError` class of its own, so the harness
  compares `isinstance(exc, old_module.StoreError)` for the old side and `isinstance(exc, admission.StoreError)` for the
  new, never one class against both (the review's N1). Any other exception on either side is a difference. The report
  gives the corpus size and zero differences. It also runs the moved and the remaining admission tests in test_store and
  test_admission.
- **R3.3.6** — The six unused event `TypedDict`s stay descriptions. ledger.py's docstring sentence "The others describe
  their families' shapes; nothing takes them by type yet" (about 143-160) becomes: "The others describe their families'
  shapes and stay descriptions: the admission reads a line before anything has proved its shape, so its family
  functions take ``dict`` (P3.3), and :func:`new` returns a plain ``dict`` by design." The ledger is not in the closure.
- **R3.3.7** — The two records docstrings that name the old home are retargeted in this commit:
  `records.person_from_json` (851) and `records.feed_from_json` (1210) read `tracker.admission._refuse_a_malformed_line`
  in place of `tracker.store._refuse_a_malformed_line`. Both are in the closure, so their digests change for those
  words only.
- **R3.3.8** — Re-pin under 5. What changes, and nothing else:
  - the digest of `tracker.admission._refuse_a_malformed_line`;
  - fifteen keys added (the ten `_admit_*` family functions, `_admit_line` and the four helpers), with no constant key
    removed or added;
  - the digests of `tracker.records.person_from_json` and `tracker.records.feed_from_json` (R3.3.7).

  Comment line: "Pinned again under 5 when P3.3 split the admission into one function per family (B-7): the entry
  function, fifteen new parts and two docstrings moved, and the equivalence run found no line judged differently. No
  rule changed."

**Pin-move list:** `ADMISSION_PIN[5]` (both commits); tests/test_admission.py's `admission_closure` and its new test;
ledger's docstring (not a pin; test_ledger has no read of it at the base).

**Patch sites:** none on `tracker.admission` (`report tracker.admission` lists 0 after P3.2). The five stand-ins
replace the entry function whole and are unaffected.

**Tests:** `test_admission`, `test_store`, `test_records` (the docstrings), `test_ledger`, `test_golden`; guards
`test_layers`, `test_single_source`, `test_repo_map`, `test_tripwire`, `test_errors`.

**Stop and ask:**
- the equivalence run finds a difference;
- R3.3.1 joins any key other than the two;
- the re-pin changes a digest R3.3.8 does not name;
- a branch reads state that cannot be passed as an argument.

**Accept when:**
- the gate passes;
- the equivalence report shows zero differences;
- `grep -nE "^\s+(if|elif) name" tracker/admission.py` shows the chain, and `grep -n "{.*_admit_" tracker/admission.py`
  finds no table;
- the pin moved only as R3.3.1 and R3.3.8 say;
- `tests/golden/` is unchanged.
- **Windows:** no label. `_a_place` calls `layout.place_problem` unchanged.

---

### P3.4 `store_check.py`: the check and the export

- **Cost:** M.
- **Tier:** Opus, by rule (a).
- **Findings:** SPEC-architecture 5.3 (`store_check.py` L1).
- **Depends on:** P3.3.

**What moves** (store lines at `144c5d2`; P3.1-P3.3 change no line count in this region except the moved admission
above, so the builder anchors on names):

| Store lines | Names |
|---|---|
| 3221-3288 | the check's section comment, `check` |
| 3300-3386 | `_check_household`, `_check_documents`, `_check_intents` |
| 3407-3430 | `_recorded_learned` (until P3.6 deletes it) |
| 3433-3518 | `_check_statuses`, `_check_rules`, `_check_learned` |
| 1215-1230 | the `#:` comment, `FORMULA_LEADS` and `_as_text` (the export's spreadsheet-cell rule; the review's S16) |
| 3545-3614 | the export's section comment, `DOCUMENTS_CSV`, `REQUESTS_CSV`, `ENGAGEMENTS_CSV`, `export`, `_write_csv` |

`FORMULA_LEADS` and `_as_text` move because `_write_csv` (3611) is their only reader in the tree: grepped across
tracker/, tests/, tools/, the docs and the curated map at `144c5d2`, nothing else names either. In store_check they sit
above `export`, in their order. The one test of them,
`test_the_export_writes_every_cell_as_text_and_a_formula_shaped_name_stays_a_name` (test_store 573), is in R3.4.6's
move list and reads neither by name. With `_write_csv` gone, store's `import csv` (193) has no reader and is deleted.

**What stays in store:** `holds` (3291; after-install asks it before the check), `_recorded_statuses` (3388; `_apply`
writes through it), `state` (3521; `index.py:186` reads it), `recover` (it does not call export), and the CLI.

**Requirements:**

- **R3.4.1** — `tracker/store_check.py`.
  - Its module docstring says:
    - what it holds: the gate (decision 101, "the check is the gate", docs/storage.md 502) and the export;
    - why it is apart from the store: the store answers questions and applies lines; the check asks what else holds the
      same facts and compares. A module that reads the store and the journal side by side, and writes neither, keeps
      the gate from being edited as part of the writer it checks. The export sits with it because it is the other
      read-only whole-store walk, the one a person keeps;
    - why L1: it reads the store, the admission, the journal and the record (L1) and the lock (L0, `full_sync`, which
      `_write_csv` calls), and nothing above them; it writes the export through `fsio` at call time.
  - Its imports are what the moved code reads, by name: `import csv`; `from tracker import ledger, store` (and
    `records` if read); `from tracker.locking import full_sync`; `from tracker.admission import KIND_HOUSEHOLD,
    StoreError, _refuse_a_malformed_line` (as read); and
    `from tracker.store import ...` for each store name the moved bodies call bare (`_engagement_row`,
    `engagement_path`, `key_root`, `_rewritten_from`, `REWRITTEN`, `JOURNAL_GONE`, `_recorded_statuses`,
    `_stored_learned`, and whichever others the AST lists).
  - The builder lists every one, and `ruff` holds the list exact.
- **R3.4.2** — `_write_csv`'s docstring. Its sentence "Reached at call time - the store imports the bounds, the record,
  the journal, the lock and the checkpoint and nothing else at load time (decision 101, P321), and this is the one file
  it writes that is not the database." becomes "Reached at call time - the check imports the store, the admission, the
  journal, the record and the lock and nothing else at load time (P324), and this is the one file it writes that is not
  the database." (The review's S15: `full_sync` is the lock module's, so the sentence names the lock.) Its body, the
  call-time `from tracker.fsio import atomic_replacement` and `full_sync`, is unchanged. `full_sync` is imported from
  `tracker.locking`, as in store. If the AST shows the moved code reads nothing of `records`, the sentence drops "the
  record" and R3.4.5's expected load set drops `records`, both in the same commit.
- **R3.4.3** — The store's CLI (its `__main__` block) gains `from tracker.store_check import check, export` beside its
  registry import, with the comment's sentence extended: "and the check and the export, which read the store from one
  module up the file list (P324)." Its bare `check(...)` and `export(...)` calls are unchanged.
- **R3.4.4** — The callers are retargeted:
  - `tracker/after_install.py`:
    - 159 gains `store_check` (`from tracker import door, errors, fsio, ledger, registry, runner, scheduling, settings,
      store, store_check`);
    - 684 `store.check(` becomes `store_check.check(`;
    - the docstring at 48-49 "decision 187's ``store.check``" becomes "decision 187's ``store_check.check``".
  - `tests/conftest.py:898` becomes `store_check.check`, with the import added.
  - In the tests, every `store.check(` becomes `store_check.check(`:
    - test_filer 3942, 7627, 7635, 7700, 7849, 8282, 8549, 8694, 8702, 9019;
    - test_ledger 375, 421, 673, 681, 713, 719, 729;
    - test_households 55, 91, 107, 217, 251;
    - test_manifest 351, 504, 520;
    - test_containers 721;
    - every one in test_store (30 at the base, `grep -c "store\.check(" tests/test_store.py`), in the tests that stay
      and in the ones R3.4.6 moves.

    Each file gains `from tracker import store_check`.
  - `store.export(` and `store.{DOCUMENTS,REQUESTS,ENGAGEMENTS}_CSV` (test_store 579, 582, 588, 601, 602, 613, 721-723)
    become `store_check.export(` and `store_check.<NAME>_CSV`. They are all in the export tests R3.4.6 moves, and are
    retargeted as they move.
  - The prose that names the check or the export through the store, each by name (all outside every closure part):
    - tracker/ledger.py:148, ``store.check`` folds the journal becomes ``store_check.check`` folds the journal;
    - tracker/ledger.py:1258, ``tracker.store._recorded_learned`` becomes ``tracker.store_check._recorded_learned``
      (P3.6 rewrites the sentence; this keeps it true until then);
    - tracker/ledger.py:1411, ``tracker.store.check()`` becomes ``tracker.store_check.check()`` (P3.6 rewrites this
      sentence too, from the text this job leaves);
    - docs/storage.md:504 and docs/tools.md:62, `store.check()` becomes `store_check.check()`;
    - docs/repo-map.curated.json, three mentions: the ledger node's notes "store.check folds the journal before it
      judges a line" and "store._check_learned(), folds both sides itself. So the learned table is inside
      store.check() at last" become "store_check.check folds ...", "store_check._check_learned(), folds ..." and
      "inside store_check.check() at last"; the after_install node's role "(store.check per record folder,
      store.gone_journals)" becomes "(store_check.check per record folder, store.gone_journals)";
    - in tracker/store.py's own text that stays (module docstring and function docstrings and comments outside the
      closure): every `:func:`check`` and `:func:`export`` becomes `:func:`tracker.store_check.check`` and
      `:func:`tracker.store_check.export``, and the comment's ``check()`` at 1129 becomes ``store_check.check()``. At the
      base these are 68, 71, 99, 113, 130, 144, 351, 1129, 1596, 1680, 2094 and 2102. 1757 and 1767 are in the
      admission's docstring, a closure part moved by P3.2, and are left as they are here (P3.8's R3.8.3a retargets
      them, since it moves that digest anyway).
  - Not retargeted here: `tracker/manifest.py:1778`'s ``store.check()``. Manifest is an `INPUT_PATHS` file of
    `tools/vocab_report.py`, so any edit to it rebuilds the vocabulary report; P3.7 edits manifest anyway and
    retargets it there (R3.7.6). docs/runbook.md names the check only as the command `python -m tracker.store ...
    check`, which is unchanged.
  - The builder then runs `grep -rn "store\.check(\|store\.export(\|store\.check\b" tracker tests tools docs/storage.md
    docs/tools.md docs/repo-map.curated.json` and finds only tracker/manifest.py:1778.
- **R3.4.5** — test_layers:
  - `LAYERS[1]` gains `"store_check"` with its comment ("``store_check`` joins L1 with P324 ...: the gate and the export
    out of ``store`` - ``admission``, ``ledger``, ``records`` and ``store`` (L1), ``locking`` (L0); ``fsio`` at call
    time; the store's command line asks it at call time");
  - `DOMAINS["record"]` gains it;
  - a new pin `test_the_check_imports_the_store_and_the_record_and_writes_through_fsio_alone`, asserting the measured
    load set (expected `{"admission", "ledger", "locking", "records", "store"}`) and `call == {"fsio"}`;
  - `CALL_TIME_CYCLES` gains `frozenset({"store", "store_check"}),  # the store's ``__main__`` asks the check`;
  - the docstring's line 15 "Three two-module cycles remain" becomes "Four two-module cycles remain".
  - The store pin is unchanged: store does not import store_check at load time.
- **R3.4.6** — The tests move to a new `tests/test_store_check.py`, by cut and paste, names kept:
  - the export tests 573, 595, 607 and 700;
  - the check tests 1126, 1137, 1170, 1235-1315 (the scanned and decision-136 respelling tests), 1818, 2670 and 4178;
  - the builder confirms each by reading it: its subject is `check`'s verdict or the export's files.
  - 1355-1402 (`_recorded_statuses` and its writer) stay: their subject is the store's write.
  - The fixtures and helpers both files need (`root`, `conn`, `by_hand`, `engagement`, `build`, `key_of`, `scanned`,
    `_a_rule`, `cli` and any other the moved tests read) move to a new **`tests/store_helpers.py`**, a non-test module.
    - Fixtures follow `tests/passes.py`'s precedent in the form its curated note recommends: a test file names each
      fixture it uses once, by assignment (`conn = store_helpers.conn`, as test_runner 112 and test_golden 73 name
      `samples = passes.samples`), because an imported fixture that a test takes as a parameter trips ruff's F811 at
      every such test (test_page_rows 328 carries `# noqa: F811` for it, and `conn`, `root` and `by_hand` are taken by
      dozens). Plain helpers (`build`, `key_of`, `_a_rule`, ...) are imported by name.
    - `engagement` stays a factory call, `engagement_fixture(ITEMS, household="Smith Family", root="root")`, in
      store_helpers with `ITEMS`.
    - test_suite_shape must pass: no test file imports another.
  - With `_a_rule` in store_helpers, `test_an_event_carried_in_also_is_refused_in_the_wording_of_the_line_that_carries_it`
    (test_store 5725 at the base), which P3.2 left in test_store for that reason (R3.2.4), moves to
    `tests/test_admission.py`, which imports `_a_rule` from store_helpers. Its body is unchanged.
  - The collected ids change only by file.
- **R3.4.7** — CLAUDE.md, lines 64-67. Old:

  ```
  curated `calls` edge, stated on both nodes (P313's Q-A). Three two-module
  cycles remain, each closing at call time, and `tests/test_layers.py` names
  them in `CALL_TIME_CYCLES`: store ↔ index (`store.verify`), registry ↔ store,
  and scaffold ↔ validators (validators' `__main__` block). There is no load-time
  ```

  New:

  ```
  curated `calls` edge, stated on both nodes (P313's Q-A). Four two-module
  cycles remain, each closing at call time, and `tests/test_layers.py` names
  them in `CALL_TIME_CYCLES`: store ↔ index (`store.verify`), registry ↔ store,
  store ↔ store_check (the store's `__main__` block), and scaffold ↔ validators
  (validators' `__main__` block). There is no load-time
  ```

  docs/architecture.md:33's "The three call-time cycles that remain" becomes "The four call-time cycles that remain".
- **R3.4.8** — Docs and map:
  - docs/architecture.md "forty-five" and a `store_check.py` line after the store's;
  - `tracker/__init__.py` a `store_check` line after `store`;
  - curated nodes for `tests/test_store_check.py` (the gate's and the export's tests, from test_store with P324) and
    `tests/store_helpers.py` (the store's fixtures and helpers that test_store, test_store_check, test_admission and,
    from P3.5, test_verify share; a module that is not a test file because test_suite_shape forbids a test file
    importing another, in `tests/builders.py`'s form), per section 3;
  - a curated node for `tracker/store_check.py`. Store's node: its role's list drops "check() (every disagreement with
    the journal, as sentences)" and "export() (three CSVs on demand, ...)" and says, in their place, that the check
    and the export are `tracker/store_check.py`'s (P324); its notes gain one sentence saying why they moved (R3.4.1's
    reason). The decision sentences already in its notes (decisions 113, 136, 138 and the gate paragraph) stay where
    they are, as the store's history; P3.6 rewrites the two that name the old folds (R3.6.8);
  - decision row **P324**: the move, L1 and domain record, why, and the {store, store_check} call-time cycle and where it
    closes;
  - `repo_map.py update`.
- **R3.4.9** — Re-pin: the closure is unchanged (check calls the admission; it is not in it). The builder runs
  `test_admission` and confirms that `ADMISSION_PIN[5]` is byte-identical.

**Pin-move list:** test_layers (R3.4.5); tracker/store.py 193 (`import csv`, deleted) and 1215-1230 (moved); test_store's no-reader test 1097-1120 is unchanged (check was never exempt;
the CLI's assert `"from tracker import registry" in command_line` still holds); the moved tests; every retargeted call
(R3.4.4).

**Patch sites:** `report tracker.store` has no stand-in on `check`, `export`, `_write_csv`, `FORMULA_LEADS`,
`_as_text`, `_recorded_learned` or a `_check_*`. Stand-ins on names check calls (`engagement_path` at test_store 5536,
inside `_counting_keys`) count calls made in store's `_engagement_row` and are not active while a check runs, so
store_check's from-imports leave them unaffected. `setitem(`: none. Hand grep: none.
Of the stand-ins on `store._refuse_a_malformed_line` in test_store (the review's S17):
- 2676 is inside `test_the_store_check_names_a_line_the_gate_now_refuses` (2670), which moves to test_store_check. It
  moves with it unchanged: it still replaces store's attribute, so `store.record` still writes the forged line, and it
  is undone before the check runs.
- 2694 is inside the helper `_applied_before_the_rule` (2687), whose one caller is
  `test_an_applied_line_the_rule_now_refuses_stops_its_household` (2706, call at 2713), a test of the store's own
  re-judging. The helper and its test stay in test_store, and so does 2694. The helper does not move to store_helpers:
  nothing that moves reads it.
- 5797 stays in test_store (P3.2).

**Register:** none moves. `test_resident` runs.

**Tests:**
- `test_store_check` (new), `test_store`, `test_admission` (the test it gains);
- `test_after_install`, `test_filer`, `test_ledger`, `test_households`, `test_manifest` and `test_containers` (their
  retargeted calls; `test_filer` as a changed test file, not a reach into the engine);
- `test_resident`, `test_golden`, `test_suite_shape`;
- guards `test_layers`, `test_single_source`, `test_repo_map`, `test_tripwire`, `test_errors`.

Conftest's change means every test now runs the moved `check`. The named list covers the files whose calls changed.
P3.6 runs the whole suite.

**Stop and ask:**
- a stand-in must reach the moved check through store;
- store_check's load set differs from the expected one by more than `records` (R3.4.2);
- any test fails only after the move.

**Accept when:**
- the gate passes;
- R3.4.4's last grep finds only `tracker/manifest.py:1778` (left for P3.7), and nothing else;
- `ADMISSION_PIN[5]` is unchanged;
- the collected ids differ only by file;
- `tests/golden/` is unchanged.
- **Windows:** no label. `_write_csv` calls the atomic replace, moved byte for byte. The office's Windows check names
  `test_store_check` (section 6).

---

### P3.5 `verify.py` at L3

- **Cost:** S.
- **Tier:** Opus, by rule (a).
- **Findings:** SPEC-architecture 5.3 (`verify.py` L3).
- **Depends on:** P3.4.

**What moves:** store 3805-3907 (`#: verify` section comment, `V_RECORD` ... `V_CHANGED`, `V_BY_KIND`, `verify`) to a
new `tracker/verify.py`, byte for byte. Its call-time imports (3838-3841: `layout`, `registry`, `index`'s `FILE_MOVED`
and `holds_the_row`, `layout.locate`, `validators.is_cloud_placeholder`) stay call-time. Verify is read-only and runs
only when a person runs it, so loading it pulls in nothing.

**Requirements:**

- **R3.5.1** — `tracker/verify.py`.
  - Its module docstring says:
    - what it holds: decision 159's read-only firm-wide proof;
    - why it is apart: it walks every record under a root (the registry) and proves files' bytes (the index), which
      the store must never import;
    - why L3: it reads the registry, which is L3. Its load-time imports are L1 and below, but its place is set by what
      it asks;
    - that the store's command line asks it at call time.
  - Its load imports: `from tracker import checkpoint, ledger, records`;
    `from tracker.admission import KIND_RETURN, StoreError, _refuse_a_malformed_line`; `from tracker.store import
    _CLAIMS, _FOREIGN, _MALFORMED, _NO_WRITER, _REWRITTEN, _SHORTER, _engagement_row, _judge, engagement_path, key_root`;
    and `sqlite3` and `cast` for P3.1's R3.1.2. The exact list is as the AST and ruff settle it.
- **R3.5.2** — The store's CLI gains `from tracker.verify import verify` at call time, beside R3.4.3's import. Its
  bare `verify(...)` call is unchanged.
- **R3.5.3** — `tests/test_store.py::test_the_store_names_no_reader_at_load_time` (1097-1120) drops the exemption:
  - the five lines that find and cut `verify` (1111-1115: `tree = ast.parse(top)`, the two lines of
    `verify = next(...)`, `lines = top.splitlines()` and `top = "\n".join(...)`) go, and the function's own
    `import ast` (1107) goes with them, since nothing in it reads `ast` after the cut (ruff F401 otherwise; the review's
    S18). test_store's module-level `import ast` went in P3.2 (R3.2.4), so test_store imports no `ast` after this job;
  - its docstring's second paragraph becomes "Read from the text: nothing above the command line names a reader since
    P325 moved ``verify``, the read-only firm-wide proof that reaches the registry and the index, to
    ``tracker.verify``.";
  - the two asserts on `command_line` stay.
- **R3.5.4** — The verify tests move to a new `tests/test_verify.py`, names kept:
  - `_tree` (4691), `test_verify_changes_nothing_and_names_every_mismatch` (4698), `locate_original` (4739, if only
    the moved tests read it; otherwise to store_helpers) and `test_verify_names_a_line_with_no_writer_as_the_pass_refuses_it`
    (4905);
  - their `store.V_*` reads (4732, 4922) become `verify.V_*`. They drive the store's CLI (`cli(..., "verify", root)`),
    whose command is unchanged;
  - the fixtures come from store_helpers.
- **R3.5.5** — test_layers:
  - `LAYERS[3]` gains `"verify"` with its comment;
  - `DOMAINS["record"]` gains it;
  - `CALL_TIME_CYCLES` loses `frozenset({"index", "store"})`, since store no longer reaches index, and gains
    `frozenset({"store", "verify"}),  # the store's ``__main__`` asks verify`. The registry entry's comment becomes
    "the store's ``__main__`` asks the registry";
  - a pin `test_verify_reads_the_walk_and_the_proof_at_call_time` asserting the measured load set (expected
    `{"admission", "checkpoint", "ledger", "records", "store"}`) and the call set `{"index", "layout", "registry",
    "validators"}`.
- **R3.5.6** — CLAUDE.md, lines 64-68 as R3.4.7 left them. Old:

  ```
  curated `calls` edge, stated on both nodes (P313's Q-A). Four two-module
  cycles remain, each closing at call time, and `tests/test_layers.py` names
  them in `CALL_TIME_CYCLES`: store ↔ index (`store.verify`), registry ↔ store,
  store ↔ store_check (the store's `__main__` block), and scaffold ↔ validators
  (validators' `__main__` block). There is no load-time
  ```

  New:

  ```
  curated `calls` edge, stated on both nodes (P313's Q-A). Four two-module
  cycles remain, each closing at call time, and `tests/test_layers.py` names
  them in `CALL_TIME_CYCLES`: registry ↔ store, store ↔ store_check and
  store ↔ verify (each through the store's `__main__` block), and scaffold ↔
  validators (validators' `__main__` block). There is no load-time
  ```

- **R3.5.7** — Prose:
  - `tracker/index.py:405`, ``tracker.store.verify`` becomes ``tracker.verify.verify``;
  - every other `store.verify` in tracker/, docs/ and the curated map the grep finds (at the base: the filer's and the
    index's curated notes). The runbook's `python -m tracker.store ... verify` lines are unchanged;
  - in tracker/store.py's own text, `:func:`verify`` (56, in the module docstring, and 2738, in `_judge`'s docstring,
    outside the closure) becomes `:func:`tracker.verify.verify``, as R3.4.4 did for the check;
  - docs/architecture.md "forty-six" and a `verify.py` line under L3;
  - `tracker/__init__.py`'s list;
  - curated node, store's and index's notes (the index node's curated edge to verify);
  - a curated node for `tests/test_verify.py` (section 3): verify's tests, from test_store with P325, driving the
    store's command line as a person runs it;
  - decision row **P325**: the move, L3 and domain record, the {index, store} cycle gone and {store, verify} come;
  - `repo_map.py update`.

**Pin-move list:** test_store 1097-1120; test_layers (R3.5.5); test_store 4732 and 4922 (moved).

**Patch sites:** none on verify or `V_*`, measured. The verify tests reach it only through a subprocess, so no stand-in
crosses it. `setitem(`: none.

**Register:** `V_BY_KIND` moves. It is a dict that nothing mutates, and the register derivation lists only mutated
containers and rebound names. The builder runs `test_resident` and confirms that the register gains no key.

**Tests:** `test_verify` (new), `test_store`, `test_index` (its docstring), `test_resident`, `test_golden`,
`test_suite_shape`; guards `test_layers`, `test_single_source`, `test_repo_map`, `test_tripwire`, `test_errors`.

**Stop and ask:**
- the register gains a key;
- verify's load set reaches L2 or L3 at load time;
- a stand-in reaches verify through store.

**Accept when:**
- the gate passes;
- `CALL_TIME_CYCLES` reads registry↔store, store↔store_check, store↔verify and scaffold↔validators;
- store's text above `__main__` names no reader;
- `tests/golden/` is unchanged.
- **Windows:** no label. Verify reads paths (`layout.locate`, `parts_below`) unchanged, moved byte for byte.

---

### P3.6 One keyed fold (B-9)

- **Cost:** M.
- **Tier:** Opus, by rule (b): `ledger.apply` is the ledger's fold, and `_apply` is the store's write path.
- **Findings:** B-9 (732).
- **Depends on:** P3.5.

Today the journal's fold (`ledger.apply`) keys a status and a taught word by the line's own spelling, because ledger
cannot import `records.identifier_key`. So the store folds the same lines twice more, keyed without case:
`_recorded_statuses(events)` for the writer and the check, and `_recorded_learned(events)` for the check. Three
copies of two rules. This job makes the one fold take the key rule as a parameter. Ledger still imports nothing of the
package.

**Requirements:**

- **R3.6.1** — ledger.
  - `apply(state, event, *, key=None)` (1262) and `replay(events, *, key=None)` (1433), with
    `key: Callable[[str], str] | None`. ledger gains `from collections.abc import Callable` (stdlib only).
  - **Unkeyed** (`key is None`), every branch is exactly today's: the scanned branch's
    `state.statuses.update(event.get(STATUSES_KEY) or {})` and `_apply_keyword_event`'s exact-spelling fold. So
    `python -m tracker.ledger` and every caller that passes no key fold as now.
  - **Keyed**:
    - the scanned branch does `for identifier, status in (event.get(STATUSES_KEY) or {}).items():
      k = key(identifier); state.statuses[k] = status; state.spellings[k] = identifier`;
    - `_apply_keyword_event(state, event, key)` computes `identifier = key(str(event.get(IDENTIFIER_KEY, "")))`, and
      everything else is unchanged.
  - `replay` passes `key` to each `apply`.
  - `Folded` gains a last field, `spellings: dict[str, str] = field(default_factory=dict)`, with a `#:` comment: "key ->
    the spelling the last scan of that key carried; filled only by a keyed fold (P326)".
- **R3.6.2** — The comments that name the store's second fold are rewritten:
  - ledger 1250-1259 (`learned`): "...Keyed by the identifier exactly as the event spells it, unless the caller hands
    :func:`replay` a ``key`` - this module sits below :mod:`tracker.records` and may not borrow its case-folding, so the
    store passes ``records.identifier_key`` and gets the same fold keyed as it keys its tables (decision 136, P326).
    Unkeyed, it is what ``python -m tracker.ledger`` prints.";
  - `_apply_keyword_event`'s docstring (1404-1414). The text P3.4 left, "``tracker.store_check.check()`` applies this
    same rule per ``records.identifier_key`` instead (``_recorded_learned``, decision 136)", becomes
    "``tracker.store_check.check()`` runs this same function with ``key=records.identifier_key`` (decision 136, P326)",
    and its earlier "across spellings the store's check folds by ``records.identifier_key``" becomes "across spellings
    a keyed fold folds by the key it is handed".
  - ledger 1250-1259 holds the ``tracker.store_check._recorded_learned`` P3.4 wrote; the new text above replaces the
    whole sentence, so no name of the deleted function is left in ledger.
- **R3.6.3** — store's `_apply`:
  - the line `ledger.apply(state, event)` becomes `ledger.apply(state, event, key=identifier_key)`. `state` starts
    with empty statuses and spellings, as now, so it holds what these events changed;
  - the last loop becomes `for k, (identifier, stored) in _recorded_statuses(state).items():
    _write_status(conn, engagement_id, identifier, stored, status_seqs[k])`;
  - `_apply`'s docstring, the statuses passage of its first paragraph (store 2087-2095 at the base; the review's S19
    and the rest of S10). Old, as P3.4 left it (P3.4 retargeted its `:func:`check``):

    ```
    from the first line by a reader cannot come out different. The statuses
    are the exception (decision 138): ``ledger.Folded.statuses`` is keyed by
    the exact spelling, because the ledger imports nothing that could fold
    case, so a batch scanning ``A01``, ``a01`` and ``A01`` again would hold
    two entries and write the second scan's status last. What these events
    changed is taken instead from :func:`_recorded_statuses` - the rule
    :func:`tracker.store_check.check` holds the table to, one entry per ``identifier_key`` with
    the last scan's spelling and status - and upserted onto what the table
    already said, so the writer and the check cannot disagree.
    ```

    New:

    ```
    from the first line by a reader cannot come out different. The statuses
    are folded by ``identifier_key`` (decision 138): the ledger imports
    nothing that could fold case, so the store hands it the key
    (``ledger.apply(..., key=identifier_key)``, P326), and a batch scanning
    ``A01``, ``a01`` and ``A01`` again is one entry, with the last scan's
    spelling and status. What these events changed is read out of that fold
    through :func:`_recorded_statuses` - the rule
    :func:`tracker.store_check.check` holds the table to - and upserted onto
    what the table already said, so the writer and the check cannot
    disagree.
    ```

    The first line is context and is unchanged. `_apply` is not a closure part, so no digest moves.
  - `_apply`'s keyword paragraph's last sentence, as P3.4 left it, ":func:`tracker.store_check.check` holds the two to its
    own fold of the same lines, keyed by ``records.identifier_key`` as this table is (decision 136)." becomes
    ":func:`tracker.store_check.check` holds the two to the journal's own fold of the same lines, handed
    ``records.identifier_key`` so that it is keyed as this table is (decision 136, P326)." (the review's S10).
  - Nothing else in `_apply` reads `state.statuses` or `state.learned` (measured).
- **R3.6.4** — `_recorded_statuses(folded: ledger.Folded) -> dict[str, tuple[str, dict]]` becomes the view
  `{k: (folded.spellings[k], status) for k, status in folded.statuses.items()}`. Its docstring says it is a view of a
  keyed fold, not a fold.
- **R3.6.5** — store_check's `check`:
  - `_recorded_learned` is deleted;
  - where `check` today calls `_recorded_statuses(events)`, it binds `keyed = ledger.replay(events, key=identifier_key)`
    once, at that point (after `_check_documents`, before `_check_statuses`), so the order of what is checked is
    unchanged;
  - it calls `_check_statuses(..., _recorded_statuses(keyed))` and `_check_learned(..., keyed.learned)`;
  - the unkeyed `folded = ledger.replay(events)` stays for the rows, the rules, the intents and the household.
  - `check`'s docstring (the review's S10), its paragraph "**A request is one request whatever its case**": the
    sentences "So those two are folded again here, from the same lines, by the store's rule
    (:func:`_recorded_statuses`, :func:`_recorded_learned`) - otherwise ..." and "... the same list is handed to the
    replay and to both folds, so no two of them can be looking at two different moments of the journal." become "So for
    those two the journal's own fold is run again over the same lines, handed the store's rule
    (``ledger.replay(events, key=identifier_key)``, P326), and :func:`tracker.store._recorded_statuses` reads the
    statuses out of it - otherwise ..." and "... the same list is handed to both replays, so neither can be looking at a
    different moment of the journal from the other." The rest of the paragraph is unchanged.
  - `_check_learned`'s docstring (store 3505-3510 at the base): "so the record's side is folded from the lines by the
    table's own rule (:func:`_recorded_learned`, decision 136)" becomes "so the record's side is the journal's fold
    handed the table's own rule (``ledger.replay(events, key=identifier_key)``, decision 136, P326)". The rest is
    unchanged.
  - **Why the gate keeps its meaning.** The SQL statuses are upserted by `_apply`'s per-batch keyed fold onto what the
    table held. The check folds the whole journal again, so a writer that lost or reordered a batch still disagrees
    with it. The SQL learned table is written by `INSERT OR REPLACE` and `DELETE`, never by the fold, so the keyed fold
    is an independent account of it, as `_recorded_learned` was.
- **R3.6.6** — tests/test_ledger.py:
  - `test_a_keyed_fold_is_the_two_store_folds_it_replaced`. It pastes the two old functions (store 3388-3430 at the
    base) into the test's body, nested, as `_old_recorded_statuses` and `_old_recorded_learned` (so neither is a
    module-level name the map lists), and asserts equality with the keyed fold. The cases: made-up journals with `A01`/`a01`/`A01 ` spellings, teach-unlearn-teach, an unlearn under the other
    spelling, an unlearn of a word never taught, and an empty `statuses`;
  - `test_an_unkeyed_fold_is_the_journals_own`: a journal with two spellings folds to two entries unkeyed and one keyed;
  - the carry-forward's key pin, `test_every_event_type_names_its_keys_by_the_key_constants`. For each `TypedDict` in
    ledger 568-683 (the nine event types and `IntentOp`), every key of `typing.get_type_hints(T, include_extras=True)`
    equals the value of one module-level str constant in ledger whose name ends in `_KEY`, or of
    `EVENT_KEY_AFTER`, the one constant named outside that rule (the review's S12).
    - `EVENT_KEY_AFTER = "then"` (ledger 239) is the key of `IntentEvent.then`, the event an intent will write. The
      test names it in a one-entry tuple, with a comment: it is named for what the key holds (the event after the
      move), not for being a key, and renaming it would be an unnamed change to ledger's exports, with the filer's
      five reads (1998, 3249, 3269, 3276, 7487), ledger's own docs (224, 481, 638) and the curated
      ledger node's mention moving with it, for no gain. (It is not an admission pin key: the pin at `144c5d2` keys no
      `tracker.ledger.EVENT_KEY_AFTER`, since the admission does not read it.)
    - Measured at `144c5d2` by that rule: every key of every type matches, and `IntentEvent.then` is the only key
      matched through the exception.
    - `get_origin(hint) is NotRequired` says which keys may be absent, and that set is asserted per type as written
      today. `__required_keys__` is never read.
- **R3.6.7** — docs/storage.md 531-540. Old: "So for those two the check does not use the journal's fold: it folds the
  same lines again, keyed without case and in journal order (`_recorded_statuses`, `_recorded_learned`) — the last scan
  of a request wins, a word taught again moves last, a word taken back under either spelling is gone." New: "So for
  those two the check hands the journal's own fold the store's key: `ledger.replay(events, key=identifier_key)` folds
  the same lines keyed without case and in journal order (P326) — the last scan of a request wins, a word taught again
  moves last, a word taken back under either spelling is gone — and `_recorded_statuses` reads the statuses out of it
  with the spelling each last scan carried." The rest of the paragraph is unchanged.
- **R3.6.8** — Map, curated notes and decision row **P326** (one keyed fold; ledger still imports nothing of the
  package; the gate's independence argument in one sentence). The curated edits, each in docs/repo-map.curated.json
  (the review's S3):
  - store's notes, decision 136's sentence. Old: "Decision 136: check() folds the record's statuses and learned
    keywords from the journal's lines itself, keyed by identifier_key in journal order (_recorded_statuses,
    _recorded_learned), rather than taking ledger.replay()'s, which keys them by each line's spelling - so a request
    respelled by case is one request to the gate, as it is to the store." New: "Decision 136: the check folds the
    record's statuses and learned keywords keyed by identifier_key in journal order - since P326 by handing
    ledger.replay() the key (key=identifier_key), where it once folded the lines itself - rather than taking the
    unkeyed fold, which keys them by each line's spelling - so a request respelled by case is one request to the gate,
    as it is to the store.";
  - store's notes, decision 138's sentence. Old: "Decision 138: _apply() writes a batch's statuses from
    _recorded_statuses(events) - one row per identifier_key," New: "Decision 138: _apply() writes a batch's statuses
    from _recorded_statuses(folded), a view of the keyed fold since P326 - one row per identifier_key,", the rest of
    the sentence unchanged; and its next sentence's "Folded.statuses is unchanged (ledger cannot fold case) and nothing
    written or shown reads it" becomes "an unkeyed fold's Folded.statuses is unchanged (ledger cannot fold case on its
    own) and nothing written or shown reads it";
  - ledger's notes, the sentence P3.4 left: "the one reader that has to join two spellings of a request,
    store_check._check_learned(), folds both sides itself." becomes "the readers that have to join two spellings of a
    request hand replay() and apply() a key instead (key=records.identifier_key, P326): the store's writer, and
    store_check.check(), whose _check_learned() compares the table with that keyed fold.";
  - store_check's node notes gain the gate's independence argument (R3.6.5's "Why the gate keeps its meaning") in one
    sentence.
  - docs/ROADMAP.md 209 and 216 (decisions 136 and 138) are history and are not edited.

**Why the whole suite.** Conftest's agreement fixture (898) runs rebuild and `check` after every test, so every test in
the suite exercises both new folds: the writer's through `_apply` and the gate's through `check`. A named list would
leave most of that coverage unrun for exactly the change it exists to catch. So this job's gate runs
`python -m pytest -q -n auto` once on PY311 and once on PY314, corpus walks included. Review-fix reruns use the named
files (`test_ledger`, `test_store`, `test_store_check`, and the files a fix touches).

**Pin-move list:** test_layers' ledger pin (ledger imports nothing of the package) is unchanged and must pass; the
docstrings above. The closure: `ledger.apply` is not in it (measured: no `tracker.ledger.apply` key), so
`ADMISSION_PIN[5]` is unchanged.

**Patch sites:** `report tracker.ledger` (10 stand-ins), none on `apply`, `replay` or `_apply_keyword_event`; `report
tracker.store`, none on `_recorded_statuses`. `test_api.py:8893` and `test_store.py:389` stand in on `store._apply`
whole, which is unaffected. `setitem(`: none.

**Tests:** the whole suite, both interpreters (above); `test_golden` is in it.

**Stop and ask:**
- the equivalence test fails on any case;
- any test anywhere in the suite fails only after the change;
- `ledger` would need any package import;
- a status's written spelling differs from today's on any test.

**Accept when:**
- the whole suite passes on both interpreters;
- after `repo_map.py update`, `grep -rn "_recorded_learned" tracker tests tools docs/storage.md docs/tools.md
  docs/architecture.md docs/repo-map.curated.json docs/repo-map.md docs/repo-map.json` finds only the pasted old
  function in test_ledger (`docs/ROADMAP.md` is history and is left out of the grep on purpose; the generated map
  carries the name only if the curated text does);
- `grep -rn "_recorded_statuses(events)" tracker docs/repo-map.curated.json docs/storage.md` finds nothing;
- `ADMISSION_PIN[5]` is unchanged;
- `tests/golden/` is unchanged.
- **Windows:** no label. No lock, no replace, no path.

---

### P3.7 The API's record events to the domain writers; the `ledger.new(` guard (B-4)

- **Cost:** M.
- **Tier:** Opus, by rules (a) (code out of `api.py`) and (c) (a guard that parses source).
- **Findings:** B-4 (615): "one door into the record".
- **Depends on:** P3.6.

**What the API composes today** (the three `ledger.new(` calls in api):
- `_cmd_mark_shared` (4707-4734): `store.record(store.connect(), household_dir, ledger.new(ledger.SHARING_CONFIRMED))`
  under the household lock, after refusing a household with no link (`SHARE_LINK_FIRST`).
- `_cmd_accept_folder_name` (4737-4806), under every lock, after its stale, pause, year and originals checks:
  - one `HOUSEHOLD_CHANGED` carrying `{HOUSEHOLD_KEY: {"name": folder_name}}` and `accepted` (4789-4790);
  - per judged return, one `RULES_CHANGED` carrying `{INFO_KEY: named}` and `accepted` (4799-4800).

**Checked against the existing saves, as the brief asks.** `save_household` (households 131) and `save_rules`
(manifest 1508) cannot be used, and the new writers do not go through them:
- `save_household` diffs the whole household against the store, and refuses a changed link. It has no way to carry
  `ACCEPTED_KEY`, and the name is never a field it moves (its docstring: "The one writer of it after creation is the
  app's *Accept the folder's name*").
- `save_rules` runs `validated()` over the whole list, which rewrites rows and would write a `rules` key the accept
  line has never carried.

Routing the API's events through either would change what is written, a behaviour change. So the new writers write
exactly today's lines, and each decision the API makes today stays in the API. What moves is the composing of the
event, nothing else.

**Requirements:**

- **R3.7.1** — `tracker/households.py` gains, after `save_household`:
  - `def mark_shared(household_dir: Path | str) -> None:` with a docstring:
    - it records the person's word that the household is shared, one `sharing_confirmed` line carrying nothing but
      the day (decision 126);
    - the caller holds the household's lock and has already refused a household with no link (the API's
      `SHARE_LINK_FIRST`), because what to refuse is the door's decision and what to write is this module's.

    Body: `from tracker import ledger, store` at call time; `store.record(store.connect(), Path(household_dir),
    ledger.new(ledger.SHARING_CONFIRMED))`.
  - `def accept_name(conn: sqlite3.Connection, household_dir: Path | str, folder_name: str) -> None:` with a docstring
    citing decision 188: the household's folder name recorded as its name, with the person's word (`ACCEPTED_KEY`),
    the one writer of a household's name after creation. The caller holds the locks and has made every check.

    Body: call-time imports; `store.record(conn, Path(household_dir), ledger.new(ledger.HOUSEHOLD_CHANGED,
    **{ledger.HOUSEHOLD_KEY: {"name": folder_name}}, **{ledger.ACCEPTED_KEY: ledger.FOLDER_NAME_ACCEPTED}))`, keeping
    today's keyword order.
  - The `conn` annotation is a string under `from __future__ import annotations` (households 58), with
    `if TYPE_CHECKING: import sqlite3`, as `tracker/containers.py` does. Neither households nor manifest imports
    `sqlite3` at base, and a type-only import keeps their load sets as they are. The same applies to R3.7.2. The
    builder checks that test_layers' households and manifest pins are unchanged.
- **R3.7.2** — `tracker/manifest.py` gains, beside `save_rules`, `def accept_folder_name(conn: sqlite3.Connection,
  return_dir: Path | str, household: str, *, return_name: str | None = None) -> None:`.
  - Its docstring cites decision 188: one `rules_changed` line naming the folder's names as the return's details, with
    the person's word; never through `save_rules`, whose `validated()` would rewrite the list.
  - Body: `named = {"household": household}`, plus `named["return_name"] = return_name` when given (so the dict's key
    order is today's), then `store.record(conn, Path(return_dir), ledger.new(ledger.RULES_CHANGED,
    **{ledger.INFO_KEY: named}, **{ledger.ACCEPTED_KEY: ledger.FOLDER_NAME_ACCEPTED}))`, with call-time imports as
    `save_rules` makes them.
- **R3.7.3** — `tracker/api.py`:
  - `_cmd_mark_shared` calls `mark_shared(household_dir)` inside its `with engagement_lock(household_dir):` (keeping
    the comment);
  - `_cmd_accept_folder_name` calls `accept_name(conn, household_dir, folder_name)` and
    `accept_folder_name(conn, one, folder_name)` (household scope) or `accept_folder_name(conn, one, folder_name,
    return_name=one.name)` (return scope), in today's order, with today's `written.append`s;
  - `accepted` and `named` go, as nothing else reads them;
  - api's existing imports of households (148) and manifest (204) gain the three names;
  - every check, lock and refusal in both handlers stays as it is;
  - `api.py` then has no `ledger.new(` (5517 records `reminder.approved_event(...)`, built by the reminder).
- **R3.7.4** — The bytes are the same. A new test in test_api, `test_the_accept_and_the_share_write_the_lines_they_wrote_before`:
  - drive `mark-shared`, `accept-folder-name` household scope and return scope on made-up households (the existing
    accept tests' fixtures);
  - assert each new journal line, minus `ledger.AT_KEY` and every key in `ledger.LINE_KEYS` (`LINK_KEY` "prev",
    `HOST_KEY` "host", `FORMAT_KEY` "fmt", which `ledger.append` adds to every line), equals the dict the old
    composition built (pasted into the test as literals). The keys dropped are named by constant, never by spelling
    (the review's S20). The comparison is dict equality: the journal writes a line with sorted keys (`ledger.line_of`,
    866), so key order is not on disk to compare.
- **R3.7.5** — The guard, in tests/test_layers.py: `test_only_the_domain_writers_compose_a_record_event`.
  - An AST walk over `tracker/*.py` collects every module with a call to `ledger.new` (an `ast.Attribute` `new` on
    the `Name` `ledger`), or to a bare `new` from-imported from `tracker.ledger`.
  - It asserts:
    - that set equals `COMPOSERS = frozenset({"filer", "households", "manifest", "reminder", "scanner"})`;
    - no member is in `DOMAINS["door"]` (`errors`, `errlog`, `api`, `resident`, `replies`);
    - a must-find: `filer` is in the walked set, so a walker that finds nothing fails.
  - `COMPOSERS` gets a `#:` comment: the modules whose decisions the record holds, each writing its own family; the
    door asks them and never composes an event itself (B-4, P327); a new composer is a decision.
  - The guard parses source, which is why this job is Opus (c).
- **R3.7.6** — Prose:
  - `tracker/records.py` 25-28: "the journal is written by :mod:`tracker.filer`, the scanner and
    :mod:`tracker.manifest`" becomes "the journal is written by :mod:`tracker.filer`, the scanner,
    :mod:`tracker.manifest`, :mod:`tracker.households` and the reminder". It is the module docstring, not in the
    closure;
  - `tracker/manifest.py:1778`: ``store.check()`` becomes ``store_check.check()``. P3.4 left it for this job;
  - api's two handlers' docstrings are unchanged in substance. Each names its writer in one clause ("written by
    :func:`tracker.households.mark_shared`");
  - curated notes for households, manifest and api;
  - decision row **P327**;
  - `repo_map.py update`;
  - `python tools/vocab_report.py build` (manifest is an `INPUT_PATHS` file): the report's counts and hits are
    unchanged, and only its input hash moves, if it records one.
- **R3.7.7** — `tests/test_api.py::test_every_command_that_writes_holds_the_root_to_the_checkpoint_first` (7076) still
  derives `accept-folder-name` and `mark-shared`. `_writers_in_the_package` follows names across the package, so
  `accept_name`, `accept_folder_name` and `mark_shared`, which call `store.record`, are writers, and so are their
  callers. Nothing in `NOT_A_RECORD_WRITE` names them. Measured: no other function in tracker/ has these three names.

**Pin-move list:** test_api 7076-7086 (the derivation, unchanged and passing); test_layers (the new guard); records'
docstring (test_records has no read of it).

**Patch sites:**
- `report tracker.api` (62 stand-ins): none on `_cmd_mark_shared`, `_cmd_accept_folder_name` or their locals.
- test_api 7921 and 8262 stand in on `store.record` for the list and the issuer tests, unrelated to these commands.
- `report tracker.households` (1: `shared_on` at test_households 536, read after the write, unaffected).
- `report tracker.manifest` (4, none on `save_rules` or the new function).
- builders 191's `store.record` stand-in replaces the module attribute, which the new writers call through the module,
  so it reaches them as it reached the API.
- `setitem(`: none.

**Tests:** `test_households`, `test_manifest`, `test_api` (the accept, share and writers tests by `-k`: `accept`,
`mark_shared`, `share`, `writes_holds_the_root`), `test_vocab_report`, `test_golden`; guards `test_layers`,
`test_single_source`, `test_repo_map`, `test_tripwire`, `test_errors`.

**Stop and ask:**
- a line's bytes differ (R3.7.4);
- the derivation stops seeing a command;
- the guard finds a composer outside `COMPOSERS`;
- the vocabulary report's counts move.

**Accept when:**
- the gate passes;
- `grep -n "ledger\.new(" tracker/api.py` finds nothing;
- R3.7.4 passes;
- `tests/golden/` is unchanged (no recording is of accept or share, but `replies.state.keys.json` holds the state reply
  both commands return, and it must not move).
- **Windows:** no label. The lock stays where it is, taken by the API exactly as now.

---

### P3.8 The `released` defect; `ADMISSION_VERSION` 6

- **Cost:** S.
- **Tier:** Opus, by rule (b).
- **Findings:** the carry-forward from P2.11's builder.
- **Depends on:** P3.7. **Jason answered Q1 on 2026-10-14: "a - the full rule"** (section 7). This job builds option
  (A).

**The defect.** The admission holds a `released` line's key, row and reason, but not its `was`. The retired
`handed_over_by_person` (decision 129, read once and folded as a release, decision 132) has no branch at all. The brief's
line `{"event": "released", "key": "x.pdf", "was": ["not", "a", "place"]}` passes the gate. Then `_apply`'s release
branch hands the list to `_close_intent`'s SQL, and `catch_up` fails with `StoreUnavailable` (SQLITE_ERROR) instead of
decision 187's "line N of the record is malformed" (the review confirmed it by probe: a `ProgrammingError` binding a
parameter, raised through checkpoint.py:252). That is on a return that holds no row. **On a return that holds one**
(any return the office has worked), the same line fails earlier, with a bare `TypeError` ("cannot use 'list' as a dict
key"): `_apply`'s release branch pops the list from a dictionary of keys (`seqs.pop`) before `_close_intent`'s SQL binds it, and an empty
dictionary is the only one whose `pop` does not hash its argument. The runner then records the return as stopped
early by an unexpected error (`CODE_CRASHED`, through its `except Exception` at runner 1446 or 1688), by class and never by message. A `was` of `5` passes and is
applied: `_close_intent` binds it, and the fold pops a key that is no location.

**What each kind of `was` does today, and after the fix** (measured by probe at `144c5d2`: a `released` line and a
`handed_over_by_person` line, each written into a made-up return's journal by `written_elsewhere`, on a return with
no row and on one holding a filed row, and read back through `catch_up`; the review's S13):

| The line's `was` | Today | After the fix (option (A)) |
|---|---|---|
| a list or a mapping with something in it | the return stops with an unexpected error: a `TypeError` if it holds a row, "the database could not be used (SQLITE_ERROR)" if it holds none | stops with "line N of the record is malformed" |
| an integer too large for the database (`10**20`) | the return stops with an unexpected error (`OverflowError`, `CODE_CRASHED`), on any return | stops with "line N of the record is malformed" |
| any other number (`5`, `0`), true or false | admitted and applied silently | **newly stops** with "line N of the record is malformed" |
| an empty list or an empty mapping | admitted and applied silently (it is falsy, so nothing is popped) | **newly stops** |
| text over 1,000 characters, or text with a NUL | admitted and applied silently | **newly stops** |
| absent, `null`, or any other text (`"../x"` included) | admitted | admitted |

- The rule (A) adds is `bounds.name_problem`: text, at most 1,000 characters (`bounds.TEXT_MAX`), with no NUL. It does
  not check that the text names a place that exists, or a place inside the folder: `"../x"` is admitted.
- So a household whose record holds a `was` of the third, fourth or fifth row **sorts today and would stop at every
  sort after the upgrade** until a person repairs the line. For the first two rows only the sentence changes: the
  household already stops today.
- A hand-over with no key (absent or `null`) fails today with the fold's "carries no 'key'" (`LedgerError`) and, under
  after the fix, with the malformed-line sentence. A key of `""` or `5` is admitted today and after.

**What raising the version does to a store that exists today** (read from the code):
- **Nothing runs at open.** The schema is unchanged (20). No rebuild runs, and no table changes.
- **At each return's next sync.** `_admitted(row)` (store 2065) is false, because `admitted_by` is 5 < 6. Two doors
  then judge that return's applied lines again with the new admission (`_judge_the_applied_lines`, 2071), both as they
  did when versions 2 to 5 rose (decision 209 R3b):
  - `_catching_up` (2463-2470), the door every reading takes (`catch_up`, `follow_the_journal`): it judges them, then
    sets `admitted_by = 6` in the same transaction. `follow_the_journal`'s fast path is skipped that once;
  - `record()` (2276-2282), before it appends: it judges them too, and a refusal is the change's "...; nothing was
    written". It does not record the version, so the sync that follows still judges once and records it.
- **The after-install step.** The upgrade changes the program, so after_install's `_check` (667-700) runs
  `store.holds`, the record check and `gone_journals` for every folder. That happens on every program change already,
  and the check re-admits every line on every run, whatever the version.
- **How long, and when.** The re-judging is **one wait**: the first listing of the clients folder in the app, or the
  first scheduled pass after the upgrade, whichever comes first, reads every return, so every return is judged again
  in that one walk. It is not spread over each return's first page. In the runbook's own words for the same mechanism
  at decision 209 (docs/runbook.md 738-750): "the first time each return's record is read after it - by the scheduled
  pass, or by the app when it first lists the clients folder - every line the record already holds is judged by
  today's rule, once per return", and "the first screen after this upgrade can take a few seconds to list the clients,
  once". The runbook's figures, measured on returns of two hundred lines: about 3 s per hundred returns when one line
  in ten is a request-list edit, and about 12 s per hundred when every line is one; processor time, not reading from
  Drive. At 750 returns (the firm view's scale, P115) that is about 22 s, and about 90 s if every line were heavy.
  After that walk no later pass or screen judges anything again for this version.
- **If a real record already holds a line the new rule refuses.** That household stops, with decision 187's sentence
  ("line N of the record is malformed (released carries 'was' that is not a location)", or the hand-over's), at the
  pass, in the app's walk and on the return's page, and is judged again at every pass until a person repairs the line.
  The first screen's notice names it, and after-install's findings name it. A person repairs it as the runbook's
  malformed-line section (2752-2775) says. This can be a household that sorts today (a number, true or false, an
  empty list or mapping, or an over-long or NUL text, per the table above).
- **Can one exist?** The tracker's two `released` writers (filer 3255 and 6215) write `key` and `reason`, never `was`.
  Decision 129's hand-over writer is gone from the tree, so what an office record's old hand-over lines carry cannot be
  read from here. The read-only `verify` run on the office PC answers that before landing (section 6).
- **A hand-over with no key** (absent, or `None`) changes from a `LedgerError` raised inside the fold to the
  malformed-line sentence. It stops today and stops after, so only its sentence changes. A hand-over whose key is any
  other value (`""`, a number) is admitted, as the fold reads it today (the orchestrator's answer to review 1's S6,
  `threads/P3/003` section 1).

**Requirements:**

- **R3.8.1** — `_admit_release(event, refuse)` (P3.3) gains, after its reason check:

  ```python
  leaving = event.get(ledger.WAS_KEY)
  if leaving is not None and bounds.name_problem(leaving):
      refuse(f"carries {ledger.WAS_KEY!r} that is not a location")
  ```

  These are the row family's words and rule (admission's row branch), so one sentence names one problem.

  Jason chose (A) (section 7, 2026-10-14). (A-narrow), which would have refused only a non-empty list or mapping, is
  not built.
- **R3.8.2** — The chain gains `elif name == ledger.HANDED_OVER_BY_PERSON_EVENT: _admit_hand_over(event, refuse)`, after
  the `RELEASED` branch. `_admit_hand_over`:
  - refuses a hand-over whose key is absent or `None`, in the release's words (`carries no 'key'`), and holds the key to
    nothing more. That is exactly what `ledger._apply_release` (1336-1338) refuses today with a `LedgerError`, so the
    only hand-over the key rule newly stops is one that already stops;
  - holds `was` to R3.8.1's rule, the same as a release's. That is the defect itself: a `was` that reaches the store's
    SQL as whatever it was;
  - checks no row and no reason: decision 129's line carried its own shape, and holding it to more than the fold reads
    would refuse lines the fold reads safely.
- **R3.8.3** — `ADMISSION_VERSION = 6`, and its comment gains: "6 adds P328's: a release's (and the retired hand-over's)
  ``was`` held to the name rule (``bounds.name_problem``: text, at most 1,000 characters, no NUL), which reached the
  store's SQL and its fold as whatever it was, and a hand-over with no key, which the fold refused in its own words.
  Checked against the office's real records by the read-only ``verify`` before landing."
- **R3.8.3a** — In `_refuse_a_malformed_line`'s docstring, the two `:func:`check`` (store 1757 and 1767 at the base,
  moved by P3.2) become `:func:`tracker.store_check.check``. The function's digest moves in this job anyway (R3.8.4),
  so the words follow the check's move at no further cost to the pin.
- **R3.8.4** — `ADMISSION_PIN[6]` is pasted from `admission_digests()`. Versions 2 to 5 are unchanged.
  `test_admission_version_changes_with_the_admission` then passes on 6. Pin 6 differs from 5 by exactly four parts
  (the review's S4):
  - two moved digests: `tracker.admission._admit_release` (R3.8.1) and `tracker.admission._refuse_a_malformed_line`
    (the new branch, and R3.8.3a's two words);
  - two added keys: the new function `tracker.admission._admit_hand_over`, and the constant
    `tracker.ledger.HANDED_OVER_BY_PERSON_EVENT`, which the new branch reads off `ledger` and the walker keys as pin 5
    keys `tracker.ledger.RELEASED`;
  - no other part. `tracker.ledger.WAS_KEY` and `tracker.bounds.name_problem` are already keyed (the row branch reads
    them), and their digests do not move.
- **R3.8.5** — Tests, in test_admission unless named otherwise:
  - `test_a_released_line_whose_was_is_not_a_location_is_malformed`. The brief's line, put into a made-up return's
    journal with `written_elsewhere` (tests/conftest.py 942, the way another machine writes a linked line, so the store
    never applied it) and read back through `catch_up`, raises `StoreError` matching "line N of the record is
    malformed" (N the line's number) and "'was' that is not a location", on a return that holds no row (today it fails
    in the SQL). The same event through `store.record` raises "This change carries 'was' that is not a location;
    nothing was written". (This test takes the store's fixtures, from store_helpers.)
  - in test_store, beside the version-five test below (because `a_row` and `A_ROW_ORIGINAL` stay in test_store after
    P3.4), `test_a_released_line_whose_was_is_not_a_location_is_malformed_on_a_return_that_holds_a_row`: the same line
    and the same sentence on a return holding a filed row (today it fails with a `TypeError` before the SQL). The row is
    written as test_store 1857-1858 writes one: `with engagement_lock(by_hand):` then
    `store.record(conn, by_hand, ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row()))`. Not test_store 4806:
    that line is written under another host name and is refused with "says it was written on this machine". Not a bare `ledger.append`: measured at `144c5d2`, a line appended under this machine's own
    name that the store did not write is refused first as "says it was written on this machine, and this machine did
    not write it", before its values are read.
  - on a release and on a hand-over: `was: 5`, `was: True`, `was: 10**20`, `was: []`, `was: {"a": 1}`, a
    1,001-character text and a text with a NUL are refused; `was: "Prepared/x.pdf"`, `was: "../x"`, `was: None` and an absent `was` are admitted.
    These pin each row of the defect paragraph's table for (A), and `"../x"` pins that the rule is a name rule, not a
    place rule;
  - `test_a_hand_over_with_no_key_is_malformed`: no key, and a key of `None`, are refused with "carries no 'key'";
  - `test_a_hand_over_whose_key_is_blank_is_still_admitted`: a hand-over with key `""` and a location `was` is
    admitted, which pins the narrow key rule (R3.8.2);
  - `test_a_decision_129_hand_over_is_still_read`: a hand-over with a str key and a str `was` is admitted and folds as a
    release;
  - in test_store, `test_a_record_admitted_under_version_five_is_judged_again_for_its_release`, after
    `test_a_record_admitted_under_version_four_is_judged_again_for_its_document` (5789) and in its form:
    - the forged line is a release with `was: 5`, written through `store.record` under a stand-in on
      `store._refuse_a_malformed_line` and undone. Not the brief's list `was`: that line cannot be applied under any
      version (it is the defect), so it could not stand as a line a version-5 store applied. `was: 5` applies cleanly
      under 5 and is refused under 6;
    - with `admitted_by = 5`, both readings (`catch_up`, `follow_the_journal`) stop with the new sentence, and
      `admitted_by` stays 5;
    - the second door (the review's N2): `store.record(conn, by_hand)` under the lock, with no events, raises the same
      sentence ending "; nothing was written", and `admitted_by` still stays 5.
- **R3.8.6** — docs/runbook.md:
  - after the decision 209 upgrade paragraph (738-750), a paragraph in its form, in these words or as close as the
    paragraph's form allows: "**P328** (admission version 6) needs nothing either: the first time each return's record
    is read after it - by the scheduled pass, or by the app when it first lists the clients folder - every line the
    record already holds is judged again by today's rule, once per return, as for decision 209 above, and with the same
    cost: the first screen after this upgrade can take a few seconds to list the clients (about 22 seconds across 750
    returns when one line in ten is a request-list edit, up to about 90 if every line were one), once. A return whose
    record holds a release, or an old hand-over, whose 'was' is not a location, or a hand-over with no key, stops with
    the malformed-line sentence below until it is repaired.";
  - in the malformed-line section (2752-2775), the list of problems a line can carry gains "a release or an old
    hand-over whose 'was' is not a location, or a hand-over with no 'key'".
  - This is a runbook line for a person-visible refusal that is not one-time (any later hand-edited line meets it too).
    The once-only re-judging is already built into the program (decision 209). No step is added for a person to
    remember.
- **R3.8.7** — Decision row **P328**, quoting Jason's answer: "a - the full rule" (2026-10-14).

**Golden:** no recording changes. No recorded scenario writes a `released` line with `was`, or a hand-over (measured at
`144c5d2`).

**Patch sites:** none on the admission. The five stand-ins are unaffected.

**Tests:** `test_admission`, `test_store`, `test_golden`; guards `test_layers`, `test_single_source` (the runbook),
`test_repo_map`, `test_tripwire`, `test_errors`.

**Stop and ask:** if any existing test fails (a fixture writing `was` on a release), or if pin 6 differs from 5 by any
part beyond R3.8.4's four (two moved digests and two added keys).

**Accept when:**
- the gate passes;
- the brief's line is refused by the malformed-line sentence;
- `ADMISSION_PIN[6]` differs from 5 by exactly R3.8.4's four parts: two moved digests, and two added keys (one function,
  one constant);
- `tests/golden/` is unchanged;
- the office's read-only `verify` has been run with this build (section 6) and its result is in the report.
- **Windows:** no label.

---

### P3.9 The admission's names read from their home

- **Cost:** S.
- **Tier:** Sonnet. Test reads and prose. No closure part changes.
- **Findings:** section 5.1 (a move ends with every reader at the new home).
- **Depends on:** P3.8.

**Requirements:**

- **R3.9.1** — In `tests/test_admission.py`, `tests/test_store.py` and `tests/test_store_check.py`, every read of an admission-owned name through
  store (`store._refuse_a_malformed_line` called directly, `store._line_keys_problem`, `store.MALFORMED_LINE`,
  `store.UNKNOWN_EVENT`, `store.REFUSED_CHANGE`, `store.ADMISSION_VERSION`) reads `admission.<name>`.
  - `admission_closure()`'s default roots become `[admission._refuse_a_malformed_line, admission._line_keys_problem]`.
    They are the same objects, so no key or digest changes.
  - **Not retargeted:**
    - the five `monkeypatch.setattr(store, "_refuse_a_malformed_line", ...)` stand-ins: test_store_check's one (2676 at
      the base, moved by P3.4 inside `test_the_store_check_names_a_line_the_gate_now_refuses`), test_store 2694 (in the
      helper `_applied_before_the_rule`, which stays) and 5797 (and P3.8's new version-five test), test_after_install 291 and test_api 11531 (the review's S17). They must replace what `store.record`
      calls;
    - `store.KIND_RETURN`, `store.KIND_HOUSEHOLD` and `store.StoreError` anywhere. They are the store's vocabulary
      (registry 562 and rollover 1103-1107 read `store.KIND_HOUSEHOLD`; every caller catches `store.StoreError`) and
      stay read through store.
- **R3.9.2** — Prose, module-level only (none is in the closure):
  - bounds.py 10 and 62: ``tracker.store._refuse_a_malformed_line`` becomes ``tracker.admission._refuse_a_malformed_line``;
  - ledger.py 111: ``store._refuse_a_malformed_line`` becomes ``admission._refuse_a_malformed_line``;
  - ledger.py 153: the bare ``_refuse_a_malformed_line`` (it has no `store.` prefix; the review's N6), in "``store._apply``
    casts to one only once ``_refuse_a_malformed_line`` has returned", becomes ``admission._refuse_a_malformed_line``,
    so the sentence names the module the function lives in now that it is not `_apply`'s own;
  - after_install.py 86: ``store.ADMISSION_VERSION`` becomes ``admission.ADMISSION_VERSION``;
  - docs/runbook.md 2753: `tracker.store.MALFORMED_LINE` becomes `tracker.admission.MALFORMED_LINE`;
  - store.py's module docstring (79-93), where it names the admission's functions, gains the module
    (`:func:`tracker.admission._refuse_a_malformed_line``).
  - The builder greps tracker/, docs/ and the curated map for `store\.(_refuse_a_malformed_line|_line_keys_problem|
    MALFORMED_LINE|UNKNOWN_EVENT|ADMISSION_VERSION|REFUSED_CHANGE|ALSO_IN)`, and every remaining hit is one of
    R3.9.1's kept stand-ins or a function docstring inside the closure. The report lists the latter and leaves them.
  - The admission's own docstring's two `:func:`check`` (store 1757 and 1767 at the base) are closure text. P3.8
    retargets them (R3.8.3a), because it moves that digest anyway; this job does not, whichever lands first.
- **R3.9.3** — `repo_map.py update`. No decision row: no module, layer or rule changes.

**Patch sites:** unchanged; `patch_sites.py check` passes.

**Tests:** `test_admission`, `test_store`, `test_store_check`, `test_bounds`, `test_ledger`, `test_after_install` (docstring only; run
whole, it is short enough), `test_golden`; guards `test_layers`, `test_single_source`, `test_repo_map`,
`test_tripwire`, `test_errors`.

**Stop and ask:** if any retarget changes an `ADMISSION_PIN` digest or key.

**Accept when:**
- the gate passes;
- `ADMISSION_PIN` is byte-identical to the job before;
- R3.9.2's grep holds;
- `tests/golden/` is unchanged.
- **Windows:** no label.

## 5. Risks

- **The admission pin is re-pinned five times under 5** (P3.1, P3.2, P3.3 twice, and P3.9's roots), then raised once to
  6 (P3.8). Version 5's meaning holds only if each re-pin is exactly what the job names:
  - P3.1: two annotations (`NoReturn`, and `split_codes`' `str | None`);
  - P3.2: nine keys renamed;
  - P3.3: two class-member keys joined, then the split (one digest, fifteen parts, two docstrings);
  - P3.9: no change.

  A reviewer diffs the pin and the closure's sources, not the count.
- **The split could judge a line differently** (P3.3). The equivalence harness is the proof that it does not, and its
  corpus is generated, not chosen. A difference it cannot reach (a shape no mutation produces) would pass unseen.
  Today's admission tests, which all run unchanged, are the second net.
- **A stand-in that silently stops reaching its target.** The five admission stand-ins depend on store calling the
  function through its own globals (R3.2.2). If a later job makes store call `admission._refuse_a_malformed_line`
  through the module, they would stop forging lines, and the tests that rely on a forged line would fail. That would
  be loud, not silent. The patch-site lists name every other site.
- **The keyed fold touches the writer and the gate at once** (P3.6). Both use the one function, so a bug in it could
  agree with itself. The equivalence test against the pasted old functions, and the SQL learned table's independence,
  are what keep the gate meaningful. The whole suite runs for that reason.
- **Found, not built: the check replays before it admits.** `check` calls `ledger.replay(events)` before its admission
  loop. A forged line with an unhashable `was` raises `TypeError` inside the fold, not `StoreError`, and
  after_install's `_check` catches `StoreError`, `LedgerError` and `OSError`, not `TypeError`. P3.8 makes such a line
  refused at `catch_up`, so the pass stops at it with the right sentence, but `check` would still raise first. Reordering
  `check` (admission first) changes when the gate's other comparisons run, which is a behaviour change. It goes to the
  carry list for phase 4's check, not here.
- **Left as it is: a hand-over whose key is a list or a mapping.** R3.8.2 holds a hand-over's key only to "present"
  (the orchestrator's answer to S6). A key that is present but unhashable still fails inside the fold or the SQL as it
  does today, not with the malformed-line sentence. No writer ever wrote one, it stops its household today and after,
  and holding the key to more would also refuse the `""` and numeric keys the fold reads safely. It goes to the carry
  list with the check-ordering item above.
- **A new cycle** ({store, store_check}, then {store, verify}) is a decision, written in P324 and P325. Both close in
  the store's `__main__`, which nothing imports.
- **The API's writes move under the API's locks** (P3.7). The lock is still taken by the API, so a writer called
  without it would write unlocked. Each writer's docstring says the caller holds the lock. `store.record` itself
  refuses outside the engagement lock (its docstring, store 2237), so a caller that forgets fails loudly.

## 6. Owed to the office PC

- **P3.8: the read-only `verify` against the office's real records, before P3.8 merges.** Run
  `python -m tracker.store "<the app folder>" verify "<clients root>"` with the P3.8 build on the office PC. It opens
  the store and checkpoint read-only, takes no lock and writes nothing. The cloud never sees the firm's records. No
  generative AI reads a client document: `verify` is deterministic, and its output names paths and line numbers only.
  - **What it can report.** `verify` stops reading a folder at its first refused line (the `break` in its per-folder
    loop, store 3869) and lists one finding per household. So the report gives **households, counted by the reason of
    their first refused line** (the review's S21): those refused for a `was` ("'was' that is not a location", on a
    release or a hand-over), those refused for a hand-over with no key ("carries no 'key'"), and those refused for any
    other reason. It cannot count lines, and a folder whose first refusal is something else hides any later `was`
    problem. `verify` is not changed for this.
  - **What a hit means** (the same account as Q1). A household listed for a `was` or a key is one that may sort today
    and would stop after the upgrade: its `was` may be a number, true or false, an empty list or an over-long text,
    which today's store applies without complaint. One whose `was` is a list or mapping with something in it, or an
    integer too large for the database, already stops today with an unexpected error. The report names every listed household to Jason
    before merging.
  - **A household listed for another reason** already stops today under version 5's rule. It is repaired first, as the
    runbook's malformed-line section says, and `verify` is run again to see whether a `was` or key problem lies behind
    it.
  - **Run it with the P3.8 build, not today's.** Today's admits a list or mapping `was`, and `verify` then folds the
    journal (`ledger.replay`, store 3886), whose release branch fails on it with a Python `TypeError` on any return
    that holds a row (measured), so the whole run would stop with a traceback instead of a list. With the P3.8 build the line is refused at the admission
    and the folder is skipped before the fold. A hand-over whose key is a list or a mapping (section 5, left as it is)
    still reaches the fold under P3.8; if the run stops with a `TypeError`, that is its cause, and the report says so.
- **Windows.** No job touches the engagement lock's behaviour, the atomic replace or path handling. No job asks for the
  `windows` label.
  - P3.4 moves `_write_csv`, which calls the atomic replace and `full_sync`, byte for byte.
  - P3.5 moves verify's path reads byte for byte.
  - P3.7 leaves every lock where it is.

  Per "Test minimally", the Windows check prompt for the landing names `test_store_check` (the export's replace),
  `test_verify` (paths under a root), `test_admission` (`layout.place_problem`, the path rule), `test_store` and
  `test_api -k "accept or mark_shared"` (the locks around the moved writes), because they hold file-replace, path and
  lock behaviour. It repeats no hands-on step: no screen or installer behaviour changes. P3.8's refusal is
  person-visible only on a record that holds a refused line.
- **Mac.** Nothing in phase 3 changes a Mac path.

## 7. Questions for Jason

**Q1 (answered: option (A). Jason, 2026-10-14: "a - the full rule").** Every return and household keeps a record: one line per thing that happened to its
files. Before the tracker trusts a line, it checks that the line is well formed. When a document leaves a return's
record, its line can also say where the file used to be, and that "where it used to be" is the one part of the line
the check skips. It also skips the same part of an older kind of line, written by an earlier version of the tracker when
a person handed a document over by hand.

- **What happens today**, by what that part holds (it would have to be written by hand, or by something other than
  the tracker):
  - **A list of things** (or a set of labelled values, or a whole number too large for the database to hold). The return stops with an unexpected program error, not with
    the tracker's own message for a damaged line ("line N of the record is malformed").
  - **A number, or a yes/no, or an empty list.** It is accepted today, and the return sorts without complaint: the
    record quietly forgets a file that was never there. The same goes for a piece of text over 1,000 characters long,
    or one holding a hidden "null" character.
- **What the fix checks.** That "where it used to be" is a piece of text of reasonable length (at most 1,000
  characters, with no hidden "null" character), the rule the same part of a filing's or a move's line already meets.
  It does not check that the place exists.
- **The one wait.** Because the check then refuses something it used to let through, every line already in every
  record is checked once more after the upgrade, which is how the tracker has handled every tightening of this check
  since decision 209. That happens at the first listing of the clients in the app or the first scheduled sort after
  the upgrade, whichever comes first, in one go. The runbook's measurements put it at about 22 seconds across 750
  returns in an ordinary record, and up to about 90 seconds in the worst case (every line a request-list edit). It is
  the computer's work, not Drive's, and it happens once.
- **After the upgrade, under the full fix (A), the one chosen.** A household whose record holds either kind of line above stops with
  "line N of the record is malformed" at every sort until someone repairs that line, as the runbook's section on that
  message says. For the first kind that only changes the message: the household already stops today. **For the second
  kind it is new: a household that sorts today would stop.** Nothing is moved or changed for that household meanwhile,
  and every other household is sorted as usual.
- **The older hand-over line** is also held to name the document it is about. One that names none already stops today,
  and would stop with the tracker's own message instead.
- **Can that happen in the office?** The tracker itself has never written either kind. The older hand-over lines were
  written by a version that is no longer in the program, so what they hold cannot be checked from here. A read-only
  check of every record on the office PC, which changes nothing, lists every household that would stop, before
  anything is merged; its list comes back to you first. It reports each household once, by the first problem in its
  record, so a household listed for some other problem is repaired and checked again.
- The runbook gains one paragraph about this upgrade and one phrase in its list of what a damaged line can say.

Options:
- **(A) The full fix** (recommended; **chosen** by Jason on 2026-10-14). Run the read-only check on the office PC first. If it lists no household,
  nothing a person sees changes except the one wait. If it lists one, you see the list before anything merges, and
  decide then.
- Not chosen: **(A-narrow)**, refuse only what fails today (the list of things), leaving a number, a yes/no, an
  empty list or an over-long text accepted.
- Not chosen: **(C)**, not this phase.

A fix for new lines only, with no re-check of the lines already in a record, is not offered: decision 209 rules out a
check that tightens without looking again at what it already let through.
