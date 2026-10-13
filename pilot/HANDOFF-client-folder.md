# Handoff - a household whose record cannot be read is never laid out again (P296)

Builder's handoff for `pilot/SPEC-client-folder-unreadable.md`. The reviewer reads
the SPEC, the diff and this, and writes numbered findings under "## Review".
`pilot/DECISIONS.md` is untouched: the landing session adds P296.

## Built, against R1-R3

- **R1** (`tracker/households.py`): `ClientSideUnknown(RuntimeError)` and
  `CLIENT_SIDE_UNKNOWN`, worded as the SPEC has them. `client_side_expected`
  keeps its signature; a failure in either half (`shared_on`, or `store.documents`
  of any return) is kept (`errors.keep("households: the client-side history", exc,
  name=folder.name)`) and raised as `ClientSideUnknown`, the problem named by
  `errors.said(exc, (ManifestError, LedgerError, StoreError))`. No `except` in the
  function swallows anything any more. `client_folder_missing` looks at the disk
  first (`layout.client_household_dir(...).is_dir()` -> `""`, record unread) and
  lets `ClientSideUnknown` pass through. `door.client_folder_missing` unchanged.
  The new imports are call-time (`errors`, `ledger`, `LedgerError`, `StoreError`);
  no load-time import was added and no layer moved.
- **R2**: `runner.py` held-back block sets `held_back = str(exc)` and
  `held_code = CODE_RECORD_UNREADABLE` on `ClientSideUnknown` (every run of the
  household carries it); `scaffold.py` raises `ClientFolderMissing(str(exc)) from
  None`; `registry.held_back` returns `str(exc)`.
- **R3**: `docs/runbook.md`, one paragraph (a new bullet) right after the
  "`Clients\<name>` is missing. Was the household renamed or moved?" entry.
  `test_single_source` still passes.

## Done differently, and why

One deviation from the SPEC's letter. Three existing runner tests
(`test_a_missing_folder_is_recorded_not_raised`,
`test_a_missing_folder_is_said_without_its_path`,
`test_every_failure_and_skip_is_logged_as_a_code`) pass a pass an engagement whose
folder does not exist at all, so there is no `_ledger.jsonl` anywhere. Under the
SPEC's wording ("a read failure in either half") "no record here" counted as a
failure and they got the new sentence instead of `FOLDER_NOT_FOUND`. A journal
that is absent has said nothing - there is nothing to refuse - and a household
whose record is gone while its returns hold theirs is already *stopped* by the
registry with its own sentence before anything asks this. So `client_side_expected`
skips a household or a return whose `ledger.path_for(...)` is not a file; only a
journal that is there and will not read is "cannot tell". The docstring says so.
The audit's reproduction (an unlinked line) is still caught. The reviewer should
confirm this reading.

## Tests added (each fails without its fix; checked by reverting the fix)

- `tests/test_households.py`: `test_a_household_whose_record_cannot_be_read_is_not_said_to_have_had_no_client_folder`,
  `test_a_client_folder_that_is_there_is_never_a_reason_to_read_the_record`
- `tests/test_runner.py`: `test_a_shared_household_whose_record_cannot_be_read_is_held_back_and_its_client_folder_is_not_remade`
- `tests/test_scaffold.py`: `test_the_scaffold_refuses_to_lay_out_a_household_whose_record_cannot_be_read`
- `tests/test_registry.py`: `test_a_household_whose_record_cannot_be_read_says_so_where_its_pause_is_said` (tests `registry.held_back`)

## The gate (venv python, `-p no:cacheprovider`, one process per file, parallel)

| file | result |
|---|---|
| test_households | 18 passed |
| test_runner | 230 passed |
| test_scaffold | 55 passed |
| test_registry | 42 passed, 2 skipped (as before) |
| test_door | 7 passed |
| test_layers | 31 passed |
| test_single_source | 218 passed |
| test_repo_map | 82 passed |

`python -m ruff check .`: all checks passed. `python tools/repo_map.py check`: map is current (after the final `update`).
The first run of `test_single_source` and `test_repo_map`
failed only on the other build's half-edited files (`COL_ISSUER`, `tracker/api.py`);
they passed on the re-run after `update`, as the SPEC allows. The router and the
readers were not run.

## For the reviewer

`tracker/households.py` (`ClientSideUnknown`, `CLIENT_SIDE_UNKNOWN`,
`client_side_expected`, `client_folder_missing`), `tracker/runner.py` (held-back
block, ~line 1358), `tracker/scaffold.py` (`scaffold_household`),
`tracker/registry.py` (`held_back`), `docs/runbook.md` (the bullet after the
"Was the household renamed or moved?" entry), the five tests above.

Not done: `docs/repo-map.curated.json` was not edited (outside SPEC section 6);
the households node's `notes` could name P296 when the landing session adds the row.

## Review (Opus, 2026-10-13)

Reviewer: a separate agent that did not build this. Read against the SPEC, this
handoff, audit E1 and the build as committed in `bfe9fea` (the nine files only;
the other build's files ignored). No code or test was edited.

### Findings

**F1 - R1/R3, `tracker/households.py` `client_side_expected`, `docs/runbook.md`.
A return's journal that will not read is reported as the household's, with no
folder named.** When the household's record reads and holds no share, the
returns are read; if one of *their* journals refuses, the sentence says "the
household's record could not be read (`_ledger.jsonl line 2 was written without
the record's link ... Run recover (runbook §6).`)". Reproduced in a scratch test:
the household's own record reads clean, and nothing in the sentence, the
`errors.keep` entry (`name=folder.name`, the household) or the runs (every run
carries the same sentence, and the pass returns before the broken return's own
`RECORD_UNREADABLE` is ever said) names the return whose journal needs recover.
The runbook paragraph repeats it ("the household's own record will not read"),
so a person repairs the one record that is fine. The build follows the SPEC's
sentence to the letter; the gap is the SPEC's. Fix: name the folder whose
journal refused - e.g. fill `{problem}` with ``f"`{one.name}`: {said}"`` for a
return's failure and keep it on the log under that folder's name - or reword the
sentence to "a record of the household (`<folder>`) could not be read"; that
needs the SPEC owner's ruling because the sentence is pinned word for word. In
any case the runbook line should say "the household's record, or one of its
returns'". Severity: **should fix** (SPEC amendment).

**F2 - R1, `tracker/households.py` `client_side_expected`. A definite "yes" is
overridden by an unreadable half.** A household whose own record will not read
but one of whose returns has an original resting under `Clients\<name>`, or a
household whose first return will not read while a later return's original rests
there, now says "cannot tell whether the household was renamed or moved" - where
it used to (and could still) say the definite `CLIENT_FOLDER_MISSING` ("Give its
client folder back the name"). Safe either way - both hold the household back
and make nothing - only the less exact sentence. Fix: remember the first
failure, keep looking for a `True`, and raise `ClientSideUnknown` only when none
is found. The SPEC says "a read failure in either half ... raises", so this is
the SPEC owner's call. Severity: **nit**.

**F3 - the deviation, `tests/test_households.py`. "A record that is not there is
not a record that cannot be read" has no test named as that claim.** It is
pinned only by three runner tests whose names are about a missing return folder
(confirmed: removing the two `is_file()` guards fails exactly those three).
Fix: add e.g.
`test_a_record_that_is_not_there_is_not_a_record_that_cannot_be_read` - a
household whose `_ledger.jsonl` is absent and a return whose journal is absent,
client folder gone, `client_folder_missing` answers `""` and raises nothing.
Severity: **nit**.

**F4 - R2, `tests/test_registry.py`
`test_a_household_whose_record_cannot_be_read_says_so_where_its_pause_is_said`
(docstring), `tracker/registry.py` `held_back` (docstring), and the build's
commit message.** The test's docstring says `held_back` "is the sentence the
list, the household's card, a new return and Roll Forward read"; in the tree it
is read only by `api.create` (New return), the api's Roll forward and
`rollover.roll_household`. The list and the card show the sentence through the
pass's run error, not through `held_back` (the card's pause is `api._pause_payload`
-> `pause_of`). The commit message's "the household's card says it" has the same
slip. `held_back`'s own docstring lists its answers and does not yet name the
"cannot tell" one. Fix: reword the test docstring to New return and Roll
forward, and add "or its record cannot say whether it had one" to `held_back`'s
docstring. Severity: **nit**.

### The deviation - verdict

**Sound; keep it.** A missing journal was already "skip" before this build (the
old `except Exception` swallowed `the_record`'s `NOT_AN_ENGAGEMENT`), so the
deviation only declines to *widen* the change to files that are absent; it
preserves the audit's fix for every journal that exists and refuses. Traced:

- *Shared household, client folder gone, household record missing, returns'
  records present:* stopped before this is asked on every path - the pass by
  `registry.stopped` (`HOUSEHOLD_RECORD_MISSING`, `_stopped_of`), New return by
  `api.create`'s "No household record found" (given household) or
  `HOUSEHOLD_NOT_OURS` (typed name over an existing folder), Roll forward by
  `registry.held_back`'s first branch. If a return holds an original under
  `Clients\<name>`, `client_side_expected` still answers `True` anyway. No path
  makes `Clients\<name>` again.
- *A return whose record is missing:* not a return - `household_returns` already
  filters on `ledger.path_for(child).is_file()`, the registry lists it as a
  misfit, and the `is_file()` test matches both exactly (a `_ledger.jsonl` that
  is a directory is skipped here and is "record missing" there - consistent).
- *A brand-new household:* `api.create` writes the household's record and the
  return's before `scaffold_engagement` -> `scaffold_household(None)`; both
  journals exist and read, `shared_on` is `None`, the new return has no rows ->
  `False` -> the folder is made. The deviation is not even reached.
- *The three runner tests:* reverting the guards (SPEC letter) turns their
  `FOLDER_NOT_FOUND` into `CLIENT_SIDE_UNKNOWN`/`record-unreadable` for an
  engagement that does not exist - wrong, and the deviation fixes it.
- Can it stop a household that should run? Only a journal that exists and
  refuses (or an `is_file()` that raises, e.g. EACCES, or a row whose
  `pbc_location` will not locate - both inside the `try`) - all "cannot tell",
  and only when the client folder is already gone. A household whose folder is
  in place is never stopped by this (disk first).

### Verified

- R1: `ClientSideUnknown(RuntimeError)`; `CLIENT_SIDE_UNKNOWN` matches the SPEC
  word for word; `errors.keep("households: the client-side history", exc,
  name=folder.name)` then `raise ... from exc` with
  `errors.said(exc, (ManifestError, LedgerError, StoreError))` - the same call as
  `FEEDS_UNREAD`'s (`runner._feeds_of`); no `except` swallows anything.
- Disk first: `client_folder_missing` returns `""` on
  `layout.client_household_dir(...).is_dir()` before any read. Same `is_dir()`
  test as `door.client_folder_missing`, the runner's `client_side_there` and
  `scaffold_household`'s `client_dir.is_dir()`, so a symlinked folder (followed,
  "there") or a file in its place ("not there") answers as before; the only
  change is that the record is not read. `door.client_folder_missing` unchanged.
- Callers: `client_folder_missing`/`client_side_expected` are called only from
  `runner.run_household`, `scaffold.scaffold_household` and `registry.held_back`
  (grep of tracker/ and tools/); each catches `ClientSideUnknown` as R2 names
  (runner: `str(exc)`/`CODE_RECORD_UNREADABLE` on every run, returns before the
  scaffold; scaffold: `ClientFolderMissing(str(exc)) from None`; registry:
  `str(exc)`). `household_pause` swallows an unreadable record, so `held_back`
  does reach the new branch. `rollover.roll_household` and the api's create and
  Roll forward ask `held_back` first and raise `ManifestError(said)`; the
  scaffold refusal is the backstop. The pass's own `scaffold_household` call
  passes `may_make_household=not client_side_there`, so it never re-asks.
- Observation, no change asked: the embedded ledger sentence carries
  `ledger.RUN_RECOVER`, so every run of the held household is counted in
  `RunReport.refused` and listed in the practice page's "records needing a
  person", one row per return. Reasonable (it is a record to repair), and part of
  why F1 matters.
- Tests: each new test fails without its fix (scratch copy of `bfe9fea`):
  swallowing again fails the households, registry, scaffold and runner tests;
  dropping the disk-first check fails only the folder-is-there test. Named as
  claims; the runner test asserts sentence, code, nothing filed and no
  `Clients\<name>`.
- Gate re-run here, one file at a time: test_households 18 passed, test_runner
  230 passed, test_scaffold 55 passed, test_registry 42 passed 2 skipped,
  test_door 7 passed, test_layers 31 passed, test_single_source 218 passed,
  test_repo_map 82 passed; `ruff check` on the eight changed files clean;
  `repo_map.py check` current.
- Layers: no load-time import added (`errors`, `ledger`, `LedgerError`,
  `StoreError`, `layout` are call-time); no dead code; docstrings carry the
  reasoning in the repo's voice.
- Runbook paragraph sits after the "Was the household renamed or moved?" entry,
  quotes the sentence, points at section 6 *When a record needs recovering*, and
  says nothing is made by the pass, a new return or Roll forward meanwhile -
  accurate except "the household's own record" (F1).

Findings: 0 must fix, 1 should fix, 3 nits.

## Rebuild 1 (Sonnet, 2026-10-13)

- **F1** built: `CLIENT_SIDE_UNKNOWN` now reads "the record of {whose} could not be read ... until that record reads again"; `client_side_expected` fills `whose` with `the household` or ``its return `<folder name>` `` and keeps the error-log entry under the failed folder's name; runbook paragraph says "the household's record, or one of its returns'" and that the sentence names which; households test checks both spellings (`test_a_household_whose_record_cannot_be_read_...` the household, `test_the_sentence_names_the_return_whose_record_cannot_be_read` the return); the runner, scaffold and registry tests assert the sentence with `whose="the household"`.
- **F2** kept as built; `client_side_expected`'s docstring now says one unreadable part makes the answer "cannot tell" even when another return would have proved the folder existed, and why.
- **F3** added `test_a_journal_that_does_not_exist_is_skipped_and_only_one_that_will_not_read_is_cannot_tell` (fails with the two `is_file()` guards removed).
- **F4** `registry.held_back`'s docstring names the "cannot tell" answer; the registry test's docstring says New return and Roll forward read `held_back` (the list and card show it through the pass's run error).
- Gate (one process per file, parallel): test_households 20 passed, test_runner 230 passed, test_scaffold 55 passed, test_registry 42 passed 2 skipped, test_single_source 218 passed, test_repo_map 82 passed; ruff clean; repo map check current.

## Review 2 (Opus, 2026-10-13)

Second reviewer: a separate agent that built neither the build nor the
rebuild. Read against the SPEC (section 10 over section 2), the first review
and Rebuild 1; the rebuild is `git diff 2680406 98cfd87`, the whole change
`git diff 6f6410b 98cfd87` on the nine files. Every other file ignored. No
code or test edited; mutations were run on a `git archive` copy in the
scratchpad, never in the checkout.

### Resolved

- **F1 - resolved.** `CLIENT_SIDE_UNKNOWN` is section 10's sentence word for
  word. `client_side_expected` starts with `whose = "the household"`,
  `failed = folder`, and each pass of the returns loop sets
  ``whose, failed = f"its return `{one.name}`", one`` before anything of that
  return is read, so the name always belongs to the part being read when it
  fails. Traced in a scratch test (two returns, `1040 - A` 2024 and
  `1040 - B` 2025, by `household_returns` order): an unlinked line in the
  *second* return's journal gives "the record of its return `1040 - B`" and
  the log entry `households: the client-side history (1040 - B)` - the
  failing return, not the first; an unlinked line in the household's journal
  (shared) gives "the record of the household" and
  `households: the client-side history (Smith Family)`. The error-log name is
  `failed.name`, the folder whose journal refused, as section 10 asks. Runbook
  says "the household's record, or one of its returns'" and that the sentence
  names which. Both spellings tested. But see G1 (the return's name alone is
  not unique) and G2 (the log-name assertion is vacuous).
- **F2 - resolved as ruled** (kept as built; docstring paragraph added). The
  paragraph overstates slightly - see G3.
- **F3 - resolved.** The test exists and fails with the two `is_file()`
  guards removed (mutation run). Its name claims a second half it does not
  assert - see G4.
- **F4 - resolved.** `registry.held_back`'s docstring names the "cannot
  tell" answer; the registry test's docstring says New return and Roll
  Forward read `held_back`, and the list and the card show it through the
  pass's run error.

### Findings

**G1 - `tracker/households.py` `client_side_expected` (and SPEC section 10).
The return is named by its folder name alone, which is not unique within a
household.** Roll Forward keeps a return's name by default
(`rollover._plan_one`: `return_name = plan.return_name or prior.name`), so a
household of two seasons holds `2024\1040 - John & Maria Park` and
`2025\1040 - John & Maria Park`. "the record of its return `1040 - John &
Maria Park`" names both; the problem text (`_ledger.jsonl line 2 ...`)
carries no path, the log entry carries the same bare name, and every run of
the household carries the same sentence, so neither the run rows nor the
practice page's "records needing a person" tell the two apart. F1's point -
a person repairs the right record - is half met: right return, possibly
wrong year. `layout.label_for`'s own docstring is the rule this misses
("so nobody reads ... two identical return names"). The build follows
section 10's spelling exactly; the gap is the amendment's. Fix: name the
return with its year, e.g. ``f"its return `{one.parent.name}\\{one.name}`"``
(the `Clients\\{name}` backslash convention), log under the same, and say
``its return `<year>\<folder name>` `` in the runbook and the test - a
SPEC-owner ruling, since the spelling is pinned. Severity: **should fix**
(SPEC amendment).

**G2 - `tests/test_households.py`
`test_the_sentence_names_the_return_whose_record_cannot_be_read`. "the error
log carries that folder's name" is asserted by a check that cannot fail.**
`"1040 - John" in caplog.text` is satisfied by the store's own WARNING
`checkpoint seeded for J Park & Associates/Smith Family/2025/1040 - John at
0 line(s)`, which caplog captures in the same test. Mutation: putting
`name=folder.name` back in `errors.keep` (the household's name, the pre-F1
behaviour) - the test still passes. Fix: assert the entry exactly as
`errors.keep` writes it, `"households: the client-side history (1040 - John)"
in caplog.text` (and, for symmetry, `"... (Smith Family)"` in the
household-half test). Severity: **should fix** (a test claim that does not
fail without its fix).

**G3 - `tracker/households.py` `client_side_expected` docstring (F2's
paragraph) and `docs/runbook.md` (the "same hold-back, when a record cannot
be read" bullet).** The docstring says one unreadable part makes the answer
"cannot tell" "even when another return would have proved the folder
existed"; the code is order-dependent - a proof found *before* the failing
part wins: a household whose own record reads and shows it shared answers
`True` without reading any return, and an earlier return whose original
rests under `Clients\<name>` answers `True` before a later broken return is
reached. Both then get the definite `CLIENT_FOLDER_MISSING`. The runbook's
"If the client folder is gone and the household's record, or one of its
returns', will not read ... every run of the household says instead" has
the same overstatement. Safe either way (both hold back, nothing is made).
Also in the runbook bullet, `<whose>` is set in backticks, while the
sentence prints "the record of the household" bare (only the return's name
is backticked). Fix: docstring "a part that will not read before anything
has proved the folder existed makes the answer 'cannot tell', even when a
later return would have proved it"; runbook "... will not read before the
record has shown it was shared ..." (or "may say instead"); write
`the record of <whose>` without backticks. Severity: **nit**.

**G4 - `tests/test_households.py`
`test_a_journal_that_does_not_exist_is_skipped_and_only_one_that_will_not_read_is_cannot_tell`.
The name's second claim is not asserted.** The test checks only that absent
journals answer `""`; "only one that will not read is cannot tell" is left
to other tests. Fix: in the same test, write one line the ledger refuses
into a journal that is there (e.g. a second return's, as the F1 test does)
and assert `ClientSideUnknown` - the contrast the name states. Severity:
**nit**.

### Verified

- Sentence: `CLIENT_SIDE_UNKNOWN` matches section 10 character for
  character; `whose` is `the household` for the `shared_on` half and
  ``its return `<folder name>` `` for a return's `store.documents` half
  (traced above, including the second of two returns). No stale copy of the
  old wording anywhere outside `pilot/` (grep); the map's constants carry
  the new one.
- Callers unchanged by the rebuild and still right: runner holds every run
  with `str(exc)` / `CODE_RECORD_UNREADABLE` and returns before
  `_worth_a_pass`; scaffold raises `ClientFolderMissing(str(exc)) from None`;
  registry returns `str(exc)` after the stop and pause checks.
  `client_folder_missing` is disk first and passes a list, so `whose` cannot
  be mis-set by a lazy iterable raising between returns.
- Runbook paragraph against the code: the quoted sentence, "the household,
  or its return `<folder name>`", "every run of the household", nothing made
  by the pass, a new return or Roll Forward, section 6 *When a record needs
  recovering* (exists, line 2378) - accurate apart from G3.
- Tests as claims: mutations on a scratch copy - dropping `whose` for the
  return fails the F1 return test; removing the `is_file()` guards fails the
  F3 test; reverting the log name passes (G2). The household-half tests
  compare against the constant itself, so the wording is pinned by the
  return test's substring and by the constant.
- Gate re-run here, one process per file in parallel: test_households 20
  passed, test_runner 230 passed, test_scaffold 55 passed, test_registry 42
  passed 2 skipped, test_layers 31 passed, test_single_source 218 passed,
  test_repo_map 82 passed, test_door 7 passed; `ruff check` on the eight
  changed code and test files clean; `repo_map.py check` current (298
  nodes). Worktree clean before this section was appended.
- Layers and dead code: no load-time import added by the rebuild (the
  households imports stay call-time); no unused name, local or import; the
  two new locals (`whose`, `failed`) are both read.

Findings: 0 must fix, 2 should fix, 2 nits.

## Rebuild 2 (Sonnet, 2026-10-13)

Built SPEC section 11, nothing more. No commit made; the other lane's files
(`tracker/{manifest,filer,api}.py`, their tests, `pilot/DECISIONS.md`) were
not touched.

- **G1.** `tracker/households.py` `client_side_expected`: `whose` for a return
  is now ``its return `<year>\<folder name>` `` (`one.parent.name` and
  `one.name`, backslash-joined); the `errors.keep` `name=` carries the same for
  a return (`failed.name` for the household, tested by `failed is folder`).
  Docstring updated. `docs/runbook.md` ("The same hold-back, when a record
  cannot be read") says ``its return `<year>\<folder name>` ``.
- **G2.** `test_the_sentence_names_the_return_whose_record_cannot_be_read`
  checks the year in the sentence (`whose="its return `2025\\1040 - John`"`)
  and the exact entry `households: the client-side history (2025\\1040 - John)`
  in `caplog.text`. The household-half test also asserts
  `households: the client-side history (Smith Family)`.
- **G3.** Docstring paragraph replaced by "the halves are read in order, the
  first definite answer wins, 'cannot tell' only when a read fails before any
  half has answered". Runbook bullet says the same in its opening clause
  ("before the record has shown the household was shared (or an earlier return
  has shown the folder existed)") and prints <whose> without backticks; only
  the return's name is in backticks.
- **G4.** `test_a_journal_that_does_not_exist_is_skipped_and_only_one_that_will_not_read_is_cannot_tell`
  now also writes an unlinked line into a second return's journal
  (`1040 - Maria`) and asserts `ClientSideUnknown` naming
  ``its return `2025\1040 - Maria` ``, after the missing-journal half.
- **test_errors.** Reproduced first: `test_the_error_class_list_is_spelled_once`
  failed on `registry.py:941`, `runner.py:1368`, `scaffold.py:384`. Each
  `str(exc)` is now `errors.said(exc, (ClientSideUnknown,))`. `errors` was
  already imported in all three modules (registry and scaffold at load time,
  runner in its package import), so no import was added and `test_layers`
  is unaffected. Test passes after: 83 passed.

**Gate** (one process per file, in parallel): test_households 20 passed;
test_runner 230 passed, 1 warning; test_scaffold 55 passed; test_registry 42
passed, 2 skipped; test_errors 83 passed; test_single_source 218 passed;
test_layers 31 passed; test_repo_map 82 passed. `ruff check .` clean;
`repo_map.py update` run, `check` current (298 nodes). No retry needed for the
other lane's files. `docs/repo-map.curated.json` needed no edit.

**Done differently:** nothing from the SPEC. The gate was run once over the
final text. The runbook line was rewrapped by hand after the edit.

**For the reviewer:** `tracker/households.py`, `tracker/registry.py`,
`tracker/runner.py`, `tracker/scaffold.py`, `docs/runbook.md`,
`tests/test_households.py`, `docs/repo-map.json` (regenerated).
Note `tests/test_runner.py`, `tests/test_scaffold.py` and
`tests/test_registry.py` needed no change.

## Review 3 (Opus, 2026-10-13)

Third reviewer: a separate agent that built neither the build nor either
rebuild. Read against SPEC section 11 (and sections 2-5 and 10 for what it
amends), Review 2 and Rebuild 2; the rebuild is `git diff 07e0fda 7df8b93`.
No repo code or test edited; every mutation and throwaway test ran on a
`git archive` copy of each commit in the scratchpad, never in the checkout.

### Resolved

- **G1 - resolved in effect.** `whose` for a return is
  ``f"its return `{one.parent.name}\\{one.name}`"``, set before anything of
  that return is read; the `errors.keep` name is
  `failed.name if failed is folder else f"{failed.parent.name}\\{failed.name}"`
  - the household's bare folder name for the household half, `<year>\<folder>`
  for a return. Scratch test of Review 2's case (two seasons of one name,
  `2024\1040 - John` reading clean and `2025\1040 - John` holding an unlinked
  line): the sentence says "the record of its return `2025\1040 - John`" with
  no `2024` in it, and the one log entry is
  `households: the client-side history (2025\1040 - John)`. Household half:
  "the record of the household" and `... (Smith Family)`. End to end through
  the pass (scratch, `test_runner`'s `build_engagement` with the return's
  journal broken and `Clients\Test Household` removed): every run carries
  `record-unreadable` and "the record of its return `2025\Smith TY2025`", and
  no client folder is made. Runbook says *its return `<year>\<folder name>`*.
- **G2 - resolved.** The test asserts the exact entry
  `households: the client-side history (2025\\1040 - John)`. Mutation M1
  (log name put back to `failed.name` alone): exactly that test fails - the
  store's checkpoint warning no longer satisfies it. Mutation M3 (the
  household half logged as `<parent>\<folder>` too): the household-half test
  fails, so the bare household name is pinned, not merely allowed. Mutation
  M2 (`whose` back to the folder name alone): the G2 test and the G4 test fail.
- **G3 - resolved.** The docstring says what the code does: `shared_on` is
  read and answers `True` before the returns loop; an earlier return's proof
  returns before a later return is read; "cannot tell" only when a read
  fails before any half answered. The runbook bullet opens with the same
  limit ("before the record has shown the household was shared (or an
  earlier return has shown the folder existed)") and prints `<whose>` bare,
  only the return's name in backticks, as the sentence prints it.
- **G4 - resolved.** The test now writes an unlinked line into a second
  return's journal (`2025\1040 - Maria`) and asserts `ClientSideUnknown`
  naming it, after the absent-journal half answers `""`. Mutation M4 (a
  return journal that will not read is swallowed and skipped): this test and
  the G2 test fail.
- **`test_errors::test_the_error_class_list_is_spelled_once` - resolved.**
  On a copy of `07e0fda` it fails at exactly `registry.py:941`,
  `runner.py:1368`, `scaffold.py:384`, as the handoff says; at `7df8b93` it
  passes (83 passed). `errors.said(exc, (ClientSideUnknown,))` is the right
  form: `said` returns `str(exc)` for an instance of a listed class, and the
  handler only catches `ClientSideUnknown`, so the sentence is returned whole
  and no wording changed. The form is load-bearing, not cosmetic: mutating
  each of the three to `errors.said(exc, ())` (class name instead of the
  sentence) fails the runner, scaffold and registry P296 tests. `errors` was
  already a load-time import in all three (`registry.py:70`,
  `scaffold.py:76`, runner's `from tracker import (... errors ...)`), so no
  import was added; `test_layers` 31 passed.
- **Runbook quote.** Word for word against `CLIENT_SIDE_UNKNOWN`, placeholders
  aside (`<name>`, `<whose>`, `<the record's own reason>` for `{name}`,
  `{whose}`, `{problem}`); "runbook section 6" and section 6 *When a record
  needs recovering* both present. `tests/test_single_source.py` pins nothing
  about this paragraph or the sentence (no reference to `CLIENT_SIDE_UNKNOWN`
  or any phrase of it); the SPEC (section 4) asked only that what it pins
  keep passing, which it does. The constant is pinned by the households,
  runner, scaffold and registry tests instead.
- **Dead code, layers, weakened tests.** No unused name, local or import in
  the changed lines (ruff clean; `whose`, `failed` both read). No layer
  change. No assertion removed or loosened: the household-half test's
  `"households: the client-side history" in caplog.text` became the stricter
  `"... (Smith Family)"`, and the return test's vacuous `"1040 - John" in
  caplog.text` became the exact entry.

### Findings

**H1 - `tracker/households.py` `household_pause` (reached through
`tracker/registry.py` `held_back`), against SPEC "What staff will notice",
section 3's registry bullet and section 10's F1. New return and Roll Forward
never say the return-half sentence: they refuse with the ledger's own words,
which name no record.** `held_back` asks `household_pause(folder)` before
`client_folder_missing(folder)`. `household_pause`'s return loop catches only
`(ManifestError, ValueError, OSError)` around `load_engagement_info(one)`;
a return journal the ledger refuses raises `LedgerError` (a `RuntimeError`,
not a `ManifestError`) out of `the_record` -> `store.follow_the_journal` ->
`ledger._parse_lines`, so `held_back` raises before the client-side check is
reached. Scratch test (`test_registry`'s `root`, `make_engagement`, one line
appended to the return's journal, `Clients\Test Household` removed, not
shared): `held_back(household)` raises `LedgerError: _ledger.jsonl line 2 does
not follow the line before it ... Run recover (runbook §6).` instead of
returning "the record of its return `2025\Smith TY2025` could not be read
...". `api._cmd_create` (line 4176, and 4572) and `rollover` (lines 678, 995)
call `held_back`, and `api._failure_of` says a `LedgerError` as a refusal,
whole - so a person sees a sentence, not a traceback, and nothing is made
(the client folder was still absent after the call), but the sentence names
neither the household, the return nor the year: exactly what F1 and G1 were
built to give. The pass and the scaffold are right (they call
`client_folder_missing` directly; the pass end to end is traced above), and
the household half through `held_back` is right (the registry test). The same
`LedgerError` escapes `held_back` when the client folder is *there*, so a
household with any return whose record will not read takes no new return
with a nameless sentence. Pre-existing: `household_pause` is unchanged since
before `bfe9fea`, so this is no regression of either rebuild; but the SPEC
made the promise for this path, and no test exercises the return half
through `held_back`, which is why three reviews passed it. Fix (a SPEC-owner
ruling): either widen `household_pause`'s return-loop catch to the record's
own errors (`LedgerError`, `StoreError`), as its docstring already says ("A
record that cannot be read claims nothing here; the pass says its own
problem"), so `held_back` reaches `client_folder_missing` and returns the
sentence - with a ruling on what `held_back` should then say when the client
folder is there and a return will not read - or amend section 3 to state the
limit. Either way, a registry test for the return half through `held_back`.
Severity: **should fix** (SPEC-owner ruling).

**H2 - `docs/runbook.md`, the "same hold-back, when a record cannot be read"
bullet.** The handoff says the paragraph was rewrapped by hand, but the line
"repair (section 6, *When a record needs recovering*); until it reads, no
`Clients\<name>` is made - not by the" runs about 110 columns against the
bullet's ~76. The file has no enforced width. Severity: **nit**.

### Verified, and how

- Interpreter: the gate ran on the scratchpad venv's Python 3.13.16 only.
  `pyproject.toml`'s floor is 3.11; `/usr/bin/python3.11` exists here but
  has no pytest, and nothing was installed, so the floor itself was not
  exercised in this review.
- Worktree: only the form-inputs lane's files were modified
  (`tracker/{manifest,filer}.py`, `tests/test_{api,manifest,filer}.py`,
  `pilot/DECISIONS.md`, `pilot/HANDOFF-form-inputs.md`, `docs/repo-map.json`);
  the map check was current, so no stale-on-their-files caveat applied.
  That lane has since committed them (`8da6fe9`); this review is of `7df8b93`.
- Gate, one process per file in parallel, `-p no:cacheprovider`, in the
  checkout: test_households 20 passed; test_runner 230 passed, 1 warning
  (runpy's `tracker.rollover` RuntimeWarning, pre-existing); test_scaffold 55
  passed; test_registry 42 passed, 2 skipped; test_errors 83 passed;
  test_single_source 218 passed; test_layers 31 passed; test_repo_map 82
  passed. `python -m ruff check .` all checks passed;
  `python tools/repo_map.py check` current (298 nodes).

Findings: 0 must fix, 1 should fix, 1 nit.

## Rebuild 3 (Sonnet, 2026-10-13)

Built SPEC section 12 against `b558c94`; nothing committed, per the brief.
Files changed: `tracker/households.py`, `tests/test_registry.py`,
`docs/runbook.md`, this handoff, and the generated `docs/repo-map.json` (the
curated map's text stays true: it never listed which errors the pause skips).

### H1 - `household_pause` lets the "cannot tell" check run

- `tracker/households.py` `household_pause`: the return loop's `except` is now
  `(ManifestError, LedgerError, StoreError, ValueError, OSError)`, with
  `from tracker.ledger import LedgerError` and `from tracker.store import
  StoreError` inside the function beside the existing call-time import (no
  load-time edge, so `test_layers` is untouched). No sentence changed.
- New test, `tests/test_registry.py`
  `test_a_return_whose_record_will_not_read_is_said_as_cannot_tell_where_a_new_return_asks`:
  one unlinked line in the return's record, the household's own record
  reading clean, its client folder removed -> `held_back` returns
  `CLIENT_SIDE_UNKNOWN` filled with the household's name, ``its return
  `2025\1040 - Test Client` `` and the ledger's own reason; then the folder is
  put back -> `held_back` returns `""`.
- **Before the code change** the test failed with the ledger's error escaping:
  `tracker.ledger.LedgerError: _ledger.jsonl line 2 was written without the
  record's link ... Run recover (runbook §6).`, raised at `registry.py:936
  held_back` -> `households.py:430 household_pause` -> `manifest.load_engagement_info`
  -> `ledger._in_its_place`, at the test's first assertion. **After:** 1 passed.
  (To show the "before" a second time after the final test text, the change was
  reverted with `git apply -R` of its own diff and re-applied; no stash.)

### Done differently, and why

- **The test does not mark the household shared**, although SPEC section 12
  says "a household marked shared". I built it that way first and it failed
  after the fix too: `held_back` returned the plain folder-missing sentence
  ("`Clients\Test Household` is missing. Was the household renamed or moved?
  ..."). `client_side_expected` reads the household's own record first and,
  when it says shared, answers `True` before any return is read - its
  docstring (G3) says exactly this ("A household whose own record says it was
  shared ... gets the folder-missing sentence even if a later return would
  not read"). So "cannot tell" for a return needs a household not yet shown
  shared, which is also how Review 3 reproduced H1 ("not shared"). The code is
  right and the SPEC's wording was loose; the test's docstring says so in one
  parenthesis. SPEC section 12 itself was not edited by this rebuild (the brief
  limits the files); the landing session then edited it in `ed109f1`, after
  this handoff named the slip.
- The test seeds with `make_engagement(..., scaffold=False)`, so it creates
  the client folder itself for the "present" half rather than relying on the
  scaffold having made one.

### H2 - runbook wrap

`docs/runbook.md`, "The same hold-back, when a record cannot be read": the one
~110-column line is rewrapped at about 80 columns like its neighbours; the
words are identical (checked on the diff: three lines became three lines).

### Gate

One process per file, `-p no:cacheprovider`, Python 3.13 (the scratchpad
venv; the 3.11 floor was not exercised here, as in Review 3):
test_registry 43 passed, 2 skipped; test_households 20 passed;
test_runner 230 passed; test_scaffold 55 passed; test_errors 83 passed;
test_single_source 218 passed; test_layers 31 passed; test_repo_map 82 passed;
`python -m ruff check .` all checks passed; `python tools/repo_map.py update`
then `check` (see the gate result below). Dead code in the changed lines: none
(ruff clean, no unused locals or imports; one unused `store`/`engagement_lock`
import I first put in the new test was removed along with the sharing step).

Gate result: `repo_map.py check` -> "Map is current (298 nodes)", and
test_repo_map 82 passed on the re-run after the final `update`. The second
`update` also re-hashed `pilot/HANDOFF-form-inputs.md` (the form-inputs
review's file, which changed while this rebuild ran); if that lane writes
again before the commit, `update` needs one more run.

## Review 4 (Opus, 2026-10-13)

Fourth reviewer: a separate agent that built neither the build nor any
rebuild. Read against SPEC section 12 (as corrected in `ed109f1`) and
sections 2-3, 10 and 11 for what it amends, Review 3 and Rebuild 3; the
rebuild is `git diff b558c94 ed109f1 -- tracker/ tests/ docs/runbook.md`.
No repo code or test edited; every throwaway test and mutation ran on
`git archive` copies of `ed109f1` and `b558c94` in the scratchpad.

### Resolved

- **H1 - resolved in effect.** `household_pause`'s return loop catches
  `(ManifestError, LedgerError, StoreError, ValueError, OSError)`, the two
  new classes imported inside the function beside `manifest`'s (no
  load-time edge; `test_layers` 31 passed, untouched). Scratch checks on
  `ed109f1`, `test_registry`'s `root` fixture, household not shared, one
  return made with `scaffold=False`:
  - *Ledger refusal* (one unlinked line in the return's journal, client
    folder gone): `held_back` returns exactly `CLIENT_SIDE_UNKNOWN` with
    "the record of its return `2025\1040 - Test Client`" and the ledger's
    own reason; the log carries `households: the client-side history
    (2025\1040 - Test Client)`; nothing escapes. Folder put back: `""`.
  - *The store's own refusal* (`manifest.the_record` patched to raise
    `StoreError` for that return only): the same sentence with the store's
    words as the reason; folder present: `""`.
  - *A store file that is not a database* (the data home's store replaced
    with junk bytes): `held_back` returns the sentence naming *the
    household* with "the database could not be used (SQLITE_NOTADB)" - the
    household half reads first and the store is one file - rather than
    escaping; folder present: `""`.
  - On `b558c94` all three escape (`LedgerError`, `StoreError`,
    `StoreUnavailable` from `sqlite3.DatabaseError`), which is H1.
- **The new test is load-bearing for the ledger half.** Mutation M1 (catch
  back to `(ManifestError, ValueError, OSError)`): exactly
  `test_a_return_whose_record_will_not_read_is_said_as_cannot_tell_where_a_new_return_asks`
  fails across test_registry, test_households, test_scaffold and
  test_runner (1 failed, 347 passed). Mutation M3 (`LedgerError` dropped,
  `StoreError` kept): the same one test fails. Mutation M2 (`StoreError`
  dropped, `LedgerError` kept): the suite passes - see I1.
- **End to end, the create path.** `api create` with `household_path` into a
  household whose return `2025\1040 - John Park` has an unlinked line and
  whose `Clients\Park Family` is gone: exit 1, `failure.kind` `refused`,
  the sentence naming that return year first; no client folder made, and
  the tree under the root is byte-for-byte the same listing as before the
  call. On `b558c94` the same call refused with the ledger's bare words,
  naming no record. `scaffold.scaffold_household(household)` (so
  `may_make_household is None`) raises `ClientFolderMissing` with the same
  sentence and makes no folder (true on both commits; the scaffold always
  called `client_folder_missing` directly).
- **Nothing swallowed that the pass needed.** `household_pause` has one
  caller, `registry.held_back` (the pass reads `registry.stopped`/`paused`
  and calls `client_folder_missing` itself, not `household_pause`). Scratch
  pass (`test_runner`'s `build_engagement`, client folder present, the
  return's journal broken): the run carries "the record could not be read:
  _ledger.jsonl line 2 ..." under `record-unreadable`, filed 0 - identical
  on `b558c94` and `ed109f1`. The one behaviour that moves is the SPEC's
  ruled half: with the client folder present, `api create` into a household
  one of whose returns will not read now succeeds (exit 0) where it used to
  refuse with the ledger's words; section 12 rules `held_back` returns `""`
  there, and the pass keeps saying that return's own problem every run.
- **H2 - resolved.** `git diff --word-diff b558c94 ed109f1 -- docs/runbook.md`
  shows no word added or removed; three lines became three lines, none past
  ~76 columns.
- **Dead code, weakened tests.** ruff clean; the two new imports are both
  read by the `except`; every name in the new test is used. The diff only
  adds to `tests/`; no assertion removed or loosened.
- **Section 12 built as written,** with the one deviation the handoff
  states (household *not* marked shared), which `ed109f1` also wrote into
  section 12's test paragraph. Sections 1-11: the gate below covers every
  test file they touched, and the household half through `held_back`, the
  return half through the pass and the scaffold all still hold.

### Findings

**I1 - `tests/test_registry.py` (H1's test), against SPEC section 12's
`except` tuple. The `StoreError` half of the widened catch has no test.**
Mutation M2 (drop `StoreError`, keep `LedgerError`) passes test_registry,
test_households, test_scaffold and test_runner, yet on that mutant a store
file that is not a database makes `held_back` raise `StoreUnavailable` out
of `household_pause`'s return loop again (scratch test above), so New
return and Roll forward lose the sentence in that case and nothing would
notice. Section 12 asked only for the ledger test, so this is beyond what
was ordered. A second case in the same test - the return's
`manifest.the_record` raising `StoreError`, or the store file replaced -
would pin it. Severity: **nit** (SPEC owner's call).

**I2 - `pilot/HANDOFF-client-folder.md` "Rebuild 3 / Done differently" and
`pilot/SPEC-client-folder-unreadable.md` line 280.** The handoff says
"SPEC section 12 itself was not edited", but `ed109f1` does edit it (the
commit message says so: the correction was folded in at commit). And the
corrected paragraph's line "removed, one unlinked line in one return's
record → `held_back` returns `CLIENT_SIDE_UNKNOWN` filled with" runs 107
columns against its neighbours' ~78. The SPEC has other lines past 100
(107, 152, 167, 168) and no wrap convention; named only because it is the
one line this commit lengthened. Severity: **nit**.

### Verified, and how

- Interpreter: the scratchpad venv's Python 3.13.16 only. The floor is 3.11
  (`pyproject.toml`); `/usr/bin/python3.11` has no pytest and nothing was
  installed, so the floor was not exercised, as in Reviews 2 and 3.
- Worktree: the form-inputs lane has uncommitted edits to
  `pilot/DECISIONS.md`, `pilot/HANDOFF-form-inputs.md`, `tests/test_api.py`
  and `docs/repo-map.json`; the map check was nonetheless current, so no
  stale-on-their-files caveat applied; that lane has since committed them
  (`5aead97`). The scratch `api create` runs used `tests/test_api.py` from
  the `ed109f1` archive, not the half-edited copy. After this review was
  appended, `repo_map.py check` is stale on this handoff alone; the commit
  of this review runs `update`.
- Gate, in the checkout, one process per file in parallel,
  `-p no:cacheprovider`: test_registry 43 passed, 2 skipped, 1 warning
  (runpy's `tracker.registry` RuntimeWarning, pre-existing - 42 passed, 2
  skipped, 1 warning on `b558c94`); test_households 20 passed; test_runner
  230 passed, 1 warning (runpy, pre-existing); test_scaffold 55 passed;
  test_errors 83 passed; test_tripwire 23 passed; test_single_source 218
  passed; test_layers 31 passed; test_repo_map 82 passed.
  `python -m ruff check .` all checks passed; `python tools/repo_map.py
  check` "Map is current (298 nodes)".

Findings: 0 must fix, 0 should fix, 2 nits.

## Rebuild 4 (Sonnet, 2026-10-13)

Built SPEC section 13 against `6a4ac16`; nothing committed, per the brief.
Files changed: `tests/test_registry.py`, this handoff, and the generated
`docs/repo-map.json` / `docs/repo-map.md`. No `tracker/` code changed: the test
pins what Rebuild 3 already put there.

### I1 - the `StoreError` half of the widened catch is pinned

- New test, `tests/test_registry.py`
  `test_a_return_whose_store_refuses_it_is_said_as_cannot_tell_where_a_new_return_asks`:
  the ledger test's household (not marked shared, client folder removed, the
  return made with `scaffold=False`, the household's own record reading
  clean), but the return's record fails through the store. It monkeypatches
  `tracker.manifest.load_engagement_info` (what `household_pause` imports at
  call time) and `tracker.manifest.the_record` (what `client_side_expected`
  feeds `store.documents`) to raise
  `StoreError("the database could not be used (SQLITE_NOTADB)")` when called
  for that return's folder and to read through for any other. `held_back` is
  asserted equal to `CLIENT_SIDE_UNKNOWN` filled with the household's name,
  ``its return `2025\1040 - Test Client` `` and the StoreError's sentence.
- **After (the code as it is):** the test passes (test_registry 44 passed, 2
  skipped).
- **Before (mutation, once):** in `tracker/households.py` `household_pause`,
  `StoreError` alone removed from the `except` tuple (`(ManifestError,
  LedgerError, ValueError, OSError)`), test_registry and test_households run
  together: **1 failed, 63 passed, 2 skipped** - exactly this test, with the
  `StoreError` escaping `household_pause` at the `load_engagement_info` call.
  The file was then restored from a byte copy (`cmp` identical; `git diff --
  tracker/` empty); no stash.

### I2 - the record corrected

Rebuild 3's "Done differently" note said SPEC section 12 was not edited; it now
says it was not edited by that rebuild, and that the landing session edited it
in `ed109f1` after this handoff named the slip. One sentence; nothing else in
that section changed.

### Gate

One process per file, `-p no:cacheprovider`, Python 3.13 (the scratchpad venv;
the 3.11 floor was not exercised, as in the earlier reviews): test_registry 44
passed, 2 skipped; test_households 20 passed; test_layers 31 passed;
test_single_source 218 passed; test_repo_map 82 passed (it failed 1 of 82
before `update`, on the stale test file's hash, as expected).
`python -m ruff check .` all checks passed; `python tools/repo_map.py update`
then `check`: "Map is current (298 nodes)". The map check never failed on
`pilot/HANDOFF-form-inputs.md`, so no second `update` for that lane was needed.
Dead code in the changed lines: none (every name in the new test is used).

## Review 5 (Opus, 2026-10-13)

Fifth reviewer: a separate agent that built neither the build nor any
rebuild. Read against SPEC section 13 only, with Review 4 (I1, I2), Rebuild
4 and the corrected Rebuild 3 sentence; the rebuild is `git diff 6a4ac16
2530021 -- tests/test_registry.py pilot/HANDOFF-client-folder.md`. No repo
code or test edited; every mutation ran on `git archive 2530021` copies in
the scratchpad.

### Resolved

- **I1 - resolved.** `test_a_return_whose_store_refuses_it_is_said_as_cannot_tell_where_a_new_return_asks`
  is the household section 13 names (not shared, client folder gone, return
  made with `scaffold=False`, the household's own record read clean first)
  with that one return's record refused through the store.
  - *As committed:* 1 passed.
  - *Mutation M2* (`StoreError` alone dropped from `household_pause`'s
    `except`, `LedgerError` kept): the test fails with
    `tracker.store.StoreError: the database could not be used
    (SQLITE_NOTADB)` raised at `registry.py:936 held_back` ->
    `households.py:432 household_pause`. Across test_registry and
    test_households on the mutant: 1 failed, 63 passed, 2 skipped - this
    test only, matching Rebuild 4's count.
  - *It patches what the code reads.* Both reads are call-time
    `from tracker.manifest import ...` inside the functions, so
    `monkeypatch.setattr(manifest, ...)` is what they see. The registry's
    own load-time `load_engagement_info` binding is untouched, but it calls
    `manifest.the_record` by module global, so `stopped_households` meets
    the same refusal and reads that return as a problem engagement
    (`registry.py` ~584), as a real store refusal would; nothing is
    stopped, so the path to the sentence is the real one.
  - *It cannot pass for a wrong reason.* With the `the_record` patch
    removed, the test fails (`held_back` returns `""`: the return's rows
    read and prove nothing), so the client-side history must hit the
    refusal for the sentence to appear. If the path comparison never
    matched, both patches would read through and the test would fail the
    same way. With the `load_engagement_info` patch removed the test still
    passes as committed and still fails under M2 (at `manifest.py:1391`,
    `load_engagement_info` -> `the_record`): the second patch is redundant
    belt and braces, not a gap - section 13 offers either. The assertion is
    whole-string equality; `problem` is `str(refusal)`, so it also pins that
    `errors.said` quotes a `StoreError` whole rather than by class.
  - *The sentence is exact.* A literal copy of the expected text ("`Clients\Test
    Household` is missing and the record of its return `2025\1040 - Test
    Client` could not be read (the database could not be used
    (SQLITE_NOTADB)), so the app cannot tell ... (runbook section 6).")
    asserted beside the test's own passes, so the test's formula and the
    literal agree.
- **I2 - resolved.** The Rebuild 3 note is one sentence: "SPEC section 12
  itself was not edited by this rebuild (the brief limits the files); the
  landing session then edited it in `ed109f1`, after this handoff named the
  slip." That is what section 13 says; `git show --stat ed109f1` confirms
  it touches `pilot/SPEC-client-folder-unreadable.md`. The long SPEC line
  stays, as section 13 rules.
- **Nothing weakened, nothing else changed.** `git diff --stat 6a4ac16
  2530021`: `tests/test_registry.py` (+39, nothing removed), this handoff
  (the one Rebuild 3 sentence replaced, the rest appended), and the
  generated `docs/repo-map.json`. No `tracker/` file changed. Every name in
  the new test is used; ruff clean.

### Findings

None. (Observations only, not asked for by section 13: the store test has
no folder-present half like the ledger test beside it, which already pins
that a present folder reads nothing; and the `load_engagement_info` patch
is redundant as said above.)

### Verified, and how

- Interpreter: the scratchpad venv's Python 3.13 only; the 3.11 floor was
  not exercised, as in Reviews 2-4.
- Gate, in the checkout at `2530021` (clean tree before this review), one
  process per file in parallel, `-p no:cacheprovider`: test_registry 44
  passed, 2 skipped, 1 warning (the pre-existing runpy warning);
  test_households 20 passed; test_layers 31 passed; test_single_source 218
  passed; test_repo_map 82 passed. `python -m ruff check .` all checks
  passed; `python tools/repo_map.py check` "Map is current (298 nodes)"
  before this review was appended. After it, `check` is stale on this
  handoff alone; the commit of this review runs `update`.
- No staleness from `pilot/HANDOFF-form-inputs.md` was seen.

No findings.

## Closed (2026-10-13)

The loop closed at commit `0002172` (Review 5: no findings). Code for
SPEC-client-folder-unreadable sections 1-13 is on
`claude/admiring-goodall-vhomni`; decision row P296 is in `pilot/DECISIONS.md`
(commit `5aead97`). The converged gate ran on `5aead97` (the last code change of
either lane): nineteen test files one process each, ruff, the map, all clean -
on the Python 3.13 venv only; the 3.11 floor was not run in this container (no
pytest for it), so the office gate before the merge covers it.

**Jason's open calls:**
- Section 13: with the client folder present, New return into a household one
  of whose returns has a record that will not read now proceeds (the pause
  claims nothing; the pass still reports that return as `record-unreadable`
  every run). Before, it refused by accident of an escaping ledger error.
  Confirm or reverse.
- E2 to E7 of `pilot/AUDIT-2026-10-13-error-handling.md` are not built: the
  rollover's silent empty unfiled list (E2), the unlogged `store.forget`
  failures (E3), the filer's silent `people=()` (E4), the StoreUnavailable
  wording (E5), the data-home override not checked as a folder (E6), the
  nineteen unread vocabulary keys (E7).

**Landing:** with the form-inputs change, per CLAUDE.md's bulk-landing rule.

**Decided by Jason, 2026-10-13:** confirmed - New return proceeds into a
household whose other return's record will not read while the client folder
is there; the pass keeps reporting that return. P296 stands as written.

## Rebuild 5 (Sonnet, 2026-10-13)

Built SPEC-client-folder-unreadable section 14, nothing more.

**Built.** `tracker/rollover.py`: `ROLLOVER_RECORD_UNREADABLE` (the SPEC's
sentence, exact) and a private helper `_unreadable_return_said`. When a
planned prior is not among the open returns, `roll_household` first asks the
helper: it walks `households.household_returns` (discovery's positional list,
the one the open returns come from), finds the folder (resolved-path
comparison), asks `registry.engagement_from(folder).problem` and, if set,
returns the new sentence; `ManifestError` carries it. Only when that is empty
does `ROLLOVER_NOT_THIS_HOUSEHOLD` stand. The CLI's `--only` lookup in `main`
uses the same helper (comparing by the layout's `name_key`) and says the same
sentence through `parser.error`. `roll_household`'s docstring names the second
refusal. The helper reads the `Engagement.problem` field; no `str(exc)` in a
handler.

**Tests.** `test_the_client_tree_is_byte_identical_after_a_roll_forward_whose_record_names_a_path`:
before, failed with `'not one folder name' in '1040 - John Park is not an
open-year return of Park Family'` (plus a teardown error from the forged
journal it left); after, passes unchanged. New
`test_rolling_a_return_whose_record_cannot_be_read_says_so_rather_than_not_this_household`:
before the wiring (constant defined, helper absent) it failed with the "is not
an open-year return of Park Family" sentence; after, passes. It asserts the
whole sentence from the function and from the command line (`--only`, exit 2),
that the old sentence is absent, and that the client tree, the private tree
listing and the record bytes are unchanged; it restores the journal at the end
because the suite's teardown walks every journal with the store's reader.

**Gate** (one process per file): test_rollover 65 passed, test_registry 44
passed 2 skipped, test_households 20, test_api 522, test_errors 85,
test_layers 31, test_single_source 218, test_repo_map 82; ruff clean; repo-map
`update` then `check` current (302 nodes). No retry was needed. The map update
was swept into `6d67fc1` by the other lane's commit, so the working tree shows
only `tracker/rollover.py` and `tests/test_rollover.py` as modified.

**Not done / noted.** The CLI is covered by the one new test (it has no
separate test for the `--only` path of a readable-but-not-open return, which
still says the old sentence). A retired return, a legacy-folder return (its
`problem` is set) and a return not in discovery's list are the cases the
helper distinguishes: legacy is said as "record could not be read (...)" per
the SPEC's "if its problem is set".

## Review 6 (Opus, 2026-10-13)

Independent review of Rebuild 5, commit `2599175`
(`git diff 6d67fc1 2599175 -- tracker/rollover.py tests/test_rollover.py`),
against SPEC section 14. Everything ran on a `git archive 2599175` copy in the
scratchpad (git-initialised, one commit); the checkout was not touched except
for this section. The probe file `tests/test_probe_r6.py` and the mutations
lived in that copy only.

**Resolved.**
- `test_the_client_tree_is_byte_identical_after_a_roll_forward_whose_record_names_a_path`
  is unchanged by the diff (the diff only adds code) and passes.
- The new test asserts the whole sentence from `roll_household` and from the
  command line (`--only`, exit 2), that the old sentence is absent, and that
  nothing is written: client-tree hashes, the private-tree listing, the record's
  bytes. **It catches the helper being bypassed** (mutations on the copy):
  M1, `_unreadable_return_said` always returns `""`: the new test and the
  forged-line test both fail (`'not one folder name' in '1040 - John Park is
  not an open-year return of Park Family'`). M2, only `roll_household`'s call
  bypassed: the new test fails. M3, only `main`'s `--only` call bypassed: the
  new test fails. So both call sites are pinned.
- The helper matches by discovery's positional list (`household_returns`) and
  by `_same_folder` (function) or `name_key` (command line). The case it must
  leave alone still gets `ROLLOVER_NOT_THIS_HOUSEHOLD`, run once each in the probe file:
  another household's folder (`Smith Family/2026/1040 - John Park`, same
  return name) → "`1040 - John Park` is not an open-year return of Park Family";
  a name that exists nowhere (`1040 - Nobody`), from the function and from
  `--only` (exit 2) → the old sentence; a readable return of another year that
  is not open (`2025/1040 - Old Park`, `active: no`), from the function and
  from `--only "1040 - old park"` (exit 2, case folded) → the old sentence. That
  last one is the `--only` readable-but-not-open path the handoff says has no
  test (K5).
- No `str(exc)` in a handler (the helper reads `Engagement.problem`, which the
  registry already sanitised); `test_errors` passes. No layer change: the
  helper imports `registry` at call time, as `open_year_returns` already does;
  `test_layers` passes. No dead code; ruff clean.
- "runbook section 6" is the right section and matches what is already there.
  Section 6 holds *When a record needs recovering*, and the hold-back sentence
  already in the runbook (section 1, *The same hold-back, when a record cannot be
  read*, P296's `CLIENT_SIDE_UNKNOWN`) points to "(runbook section 6)" for the
  same kind of record. Context for Jason, not a finding: what a malformed line
  *means* is explained in section 9 (the "line N of the record is malformed"
  bullet), and the advice there is "do not edit the record by hand; run the
  store check", which section 6 covers as well.

**Findings.**

**K1 - should fix, needs a SPEC line.** `tracker/rollover.py`
`_unreadable_return_said`: a legacy-folder return is described as a record
that "could not be read". When a record reads, holds no rules and has
`_manifest.xlsx` beside it, `registry.engagement_from` gives an Engagement *with
its `info` read* and `problem = LEGACY_FOLDER`. The helper wraps that
sentence as it is. Probe (`2025/1040 - Old Park`, `active: no`, record with an
empty list, `_manifest.xlsx` beside it), from the function and from `--only` alike:

> 1040 - Old Park's record could not be read (holds a request list in a
> workbook the app no longer reads (_manifest.xlsx) and no record; set the
> engagement up again in the app); repair it first (runbook section 6), then
> roll it forward

It is misleading in three ways:
(a) the record was read (`load_engagement_info` returned it);
(b) section 6's recover procedure has nothing to repair; the runbook's own
instruction for this folder is section 1, *A folder from before September
2026*: set it up again in the app;
(c) "then roll it forward" is the wrong next step.
Worse, **the helper only ever reaches a legacy return that is not open**
(retired, superseded, or another year). One in the open year is `active` and
is planned (see observation 1). For those returns the old sentence ("is not
an open-year return of Park Family") was true, so the new rule replaces a true
sentence with a false one. The builder followed section 14's "if its `problem`
is set" literally, so the SPEC needs the line. Proposed rule: say
`ROLLOVER_RECORD_UNREADABLE` only when `problem` is set **and is not**
`registry.LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME)`. The legacy folder
gets either `ROLLOVER_NOT_THIS_HOUSEHOLD` (true there) or its own words, with
no "could not be read" and no section-6 pointer, for instance
"`<prior>` <the LEGACY_FOLDER sentence>". Comparing the sentence is the only
hook today; a flag on `Engagement` would be cleaner, and the SPEC author picks.
Add one test: a not-open legacy return of the household gets the chosen
sentence and not "could not be read". Should fix rather than must: the Roll
Forward dialog offers open returns only, so a person most likely meets this through a
name typed on the command line or a plan passed to the function.

**K2 - nit.** `tests/test_rollover.py`, the new test: the journal is restored
on the last line, not in a `try/finally` or a finalizer. When any assert
fails, the forged line stays and the suite's journal-walking teardown adds an
ERROR on top of the real failure (seen under M1: "2 failed, 2 errors").
Use `request.addfinalizer(lambda: journal.write_bytes(original))` or
`try/finally`. The restore itself is sound: the forged line was refused at the
store's gate and never applied, so putting the original bytes back leaves the
journal and the store agreeing, which is why the passing run tears down
clean.

**K3 - nit.** `tracker/rollover.py` `main`, the `--only` loop:
`name_key(normalised_name(name))` is computed once for `by_name.get` and again as
`wanted`. Compute `wanted` once, before the lookup.

**K4 - nit, needs a SPEC line.** `docs/runbook.md` section 1, *Rolling a
household into the next year*, lists what Roll Forward refuses before writing
(paused, stopped, client folder gone), and the new refusal is not there, even
though its sentence sends the reader to the runbook. CLAUDE.md makes the
runbook part of any change to behaviour. Section 14 asked for no runbook edit,
so this needs one sentence in the SPEC and then in the runbook.

**K5 - nit.** No test for the `--only` path of a readable return of this
household that is not open (the handoff says so). The probe shows it still
gives the old sentence correctly (above). A small test would pin the
`or ROLLOVER_NOT_THIS_HOUSEHOLD...` branch of `main`.

**Observations, not counted (outside section 14).**
1. A legacy-folder return in the **open** year is in `open_year_returns`
   and rolls forward with zero rows, and nothing is said. Probe: `2026/1040 - Leg Park`, a record
   with an empty list and `_manifest.xlsx` beside it, rolled with the other three:
   rolled rows `[1, 0, 1, 1]`. Why: `Engagement.active` is
   `info.active and not superseded_by` and ignores `problem`. An unreadable
   return drops out of the open set only because its default
   `EngagementInfo()` has `tax_year = None`, not because it is inactive, so
   section 14's "its `Engagement` carries `problem`, so it is not active" is
   imprecise. This is the same kind of silence as audit E2 (the silent empty list). It was there before this change.
2. `LEGACY_FOLDER` says "... and no record", but `engagement_from` gives it
   when the journal exists and merely holds no rules. The wording was there before.
3. `test_registry`'s one RuntimeWarning (runpy in
   `test_the_registry_command_line_prints_households_returns_and_misfits`) was
   there before this diff.

**Gate** (archive copy, venv Python 3.13, `-p no:cacheprovider`, one process
per file, in parallel): test_rollover 65 passed; test_registry 44 passed,
2 skipped (1 warning, observation 3); test_households 20 passed; test_api 522
passed; test_errors 85 passed; test_layers 31 passed; test_single_source 218
passed; test_repo_map 82 passed. `python -m ruff check .`: all checks passed.
`python tools/repo_map.py check`: current (302 nodes). The 3.11 floor was not run (no pytest
for it in this container).

Findings: 0 must fix, 1 should fix, 4 nits.

## Rebuild 6 (Sonnet, 2026-10-13)

Built SPEC-client-folder-unreadable section 15 (K1-K5), nothing more.

**K1.** `tracker/rollover.py` `_unreadable_return_said` imports `LEGACY_FOLDER`
and `LEGACY_MANIFEST_FILENAME` from `tracker.registry` at call time and says
`ROLLOVER_RECORD_UNREADABLE` only when `problem` is set and `problem !=
LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME)` (compared to the one
constant, no substring); a legacy folder falls through to
`ROLLOVER_NOT_THIS_HOUSEHOLD`. The docstring says why. New test
`test_a_legacy_folder_that_is_not_open_is_not_this_household_not_a_record_that_cannot_be_read`:
a 2025 return of the Park household (inactive, `make_engagement(root, [], ...)`
so the record reads and holds no rules, `_manifest.xlsx` beside it), rolled by
plan and by `--only` (exit 2). It first asserts the registry gives it the
legacy `problem` and a read `tax_year` of 2025. Before the change it failed on
the function call with "1040 - Old Park's record could not be read (holds a
request list in a workbook the app no longer reads ...); repair it first
(runbook section 6), then roll it forward"; after, it passes.

**K2.** The rebuild-5 test now restores the journal bytes in a `try/finally`.

**K3.** `main`'s `--only` loop computes `wanted = name_key(normalised_name(name))`
once, before the lookup, and uses it for `by_name.get` and the helper.

**K4.** `docs/runbook.md`, "Rolling a household into the next year", after the
paused/stopped/client-folder-gone refusals, one insertion: "A return whose
record cannot be read is refused too, with the record's own problem, and sent
to section 6."

**K5.** New test `test_only_naming_a_readable_return_of_a_closed_year_is_not_this_household`:
`--only "1040 - old park"` for an inactive, readable 2025 return gets
`ROLLOVER_NOT_THIS_HOUSEHOLD` (name as typed) through `parser.error`, exit 2,
no "could not be read", nothing written. It passed before the K1 change too:
it pins the existing `or ROLLOVER_NOT_THIS_HOUSEHOLD` branch, not new behaviour.

**Gate** (one process per file): test_rollover 67 passed, test_registry 44
passed 2 skipped, test_api 522, test_errors 85, test_single_source 218,
test_layers 31, test_repo_map 82; ruff clean; repo-map `update` then `check`
current (302 nodes). No retry was needed. test_single_source stays green with
the runbook insertion. Not run: Python 3.11 floor (not installed here).
Observations 1-2 of Review 6 are recorded for Jason, not built.

## Review 7 (Opus, 2026-10-13)

Independent review of Rebuild 6, commit `57c3f83`
(`git diff 57adab1 57c3f83 -- tracker/ tests/ docs/runbook.md`), against SPEC
section 15. Everything ran on a `git archive 57c3f83` copy in the scratchpad
(git-initialised, one commit); the mutations lived in that copy only and were
reverted there. The checkout was not touched except for this section.

**Resolved.**
- **K1.** `_unreadable_return_said` compares `problem` for inequality with
  `LEGACY_FOLDER.format(name=LEGACY_MANIFEST_FILENAME)`, computed once from the
  registry's constants (imported at call time). That is the same expression
  `registry.engagement_from` uses to set the legacy `problem` (registry.py
  line 595), so the comparison is exact and uses no substring. The new test
  builds a 2025 return of the Park household (inactive, a record that reads
  with no rules, `_manifest.xlsx` beside it). It first asserts that the
  registry gives the legacy `problem` and a read `tax_year` of 2025. It then
  gets `ROLLOVER_NOT_THIS_HOUSEHOLD` from `roll_household` (the whole sentence)
  and from `--only` (exit 2), with no "could not be read" and no "repair it
  first". The rebuild-5 unreadable-record test still asserts the new sentence
  whole, from both paths, and passes.
- **K2.** The rebuild-5 test's body runs inside `try:`, and
  `finally: journal.write_bytes(original)` puts the journal back. Its asserts
  are unchanged (whole sentence, prefix and suffix, old sentence absent, the
  `--only` exit 2 and console, both trees and the record bytes unchanged).
  Under mutation M2 below, that test fails without a teardown error. The one
  teardown ERROR left belongs to the older forged-line test (observation 1).
- **K3.** `main`'s `--only` loop computes
  `wanted = name_key(normalised_name(name))` once (line 1090) and uses it for
  `by_name.get` and for the helper. It is the only occurrence in the file.
  Behaviour is unchanged: it is the same expression, only lifted out.
- **K4.** `docs/runbook.md` section 1, *Rolling a household into the next
  year* (heading line 1328). The sentence is lines 1381-1382, appended to the
  paragraph that lists the stopped and client-folder-gone refusals ("Roll
  Forward also refuses, before anything is written ..."). It is true against
  the code: `roll_household` raises `ROLLOVER_RECORD_UNREADABLE` before
  anything is written, the sentence carries the Engagement's `problem`, and it
  points to "runbook section 6". `test_single_source` passes.
- **K5.** The new test types `--only "1040 - old park"` for an inactive,
  readable 2025 return. It asserts the exit 2, then
  `ROLLOVER_NOT_THIS_HOUSEHOLD.format(prior="1040 - old park", ...)` (the name
  as typed, not the folder's case), that "could not be read" is absent, and
  that nothing is written. Mutations M4 and M5 show that it pins that branch.

**Mutations (archive copy, each reverted).** Targeted run: the K1, K5 and
rebuild-5 tests, plus the older forged-line test.
- M1: the legacy exclusion dropped (`if problem:`). The new K1 test fails
  with exactly the false sentence ("1040 - Old Park's record could not be read
  (holds a request list ...); repair it first (runbook section 6), then roll
  it forward"). The other three tests pass.
- M2: the helper always returns `""`. The rebuild-5 test and the older
  forged-line test fail. There is one teardown ERROR, on the older test only.
- M3: only `main`'s `--only` call loses the legacy exclusion (an inline copy
  of the helper without it). The K1 test fails on its `--only` assert, so
  both paths are pinned for the legacy case.
- M4: the `--only` refusal formats `prior=name.upper()`. The K1 and K5 tests
  fail.
- M5: the `or ROLLOVER_NOT_THIS_HOUSEHOLD...` branch is replaced. The K1 and
  K5 tests fail.

**Also checked.** The diff adds no `str(exc)` to a handler. There is no layer
change: the helper's registry import was already call-time, and
`test_layers` passes. There is no dead code: the new imports are all used,
and ruff is clean. The diff holds nothing beyond section 15: the five files
are `tracker/rollover.py`, `tests/test_rollover.py`, `docs/runbook.md`,
`docs/repo-map.json` (line counts, hashes and the reuse count only) and this
handoff.

**Findings.**

**L1 - nit.** `tracker/rollover.py` `_unreadable_return_said`, docstring,
first paragraph. It still says a return whose record cannot be read "is
listed by the registry with its `problem` and is not active, so it is
missing from the open-year returns for that reason". Section 15 corrected
that reading: `Engagement.active` is `info.active and not superseded_by`, and
an unreadable return's default `EngagementInfo()` has `active = True`
(records.py line 904). So it *is* active, and it drops out because its
`tax_year` is `None`. The second paragraph, added by this rebuild, gets it
right ("it is not in the open year"), so the docstring now contradicts
itself. Fix: "is listed by the registry with its `problem` and no `tax_year`,
so it is missing from the open-year returns for that reason". This changes
wording only, not behaviour.

**Observations, not counted (outside section 15).**
1. `test_the_client_tree_is_byte_identical_after_a_roll_forward_whose_record_names_a_path`
   has the K2 shape. It restores the journal at the top of each loop pass and
   at the end, with no `finally`, so when one of its asserts fails the forged
   line stays. The journal-walking teardown then adds an ERROR (seen under
   M2). This was there before this change.
2. `test_registry`'s one RuntimeWarning (runpy) was there before, as Review 6
   noted.

**Gate** (archive copy, venv Python 3.13.16, `-p no:cacheprovider`, one
process per file, in parallel): test_rollover 67 passed; test_registry 44
passed, 2 skipped (1 warning, observation 2); test_api 522 passed;
test_errors 85 passed; test_single_source 218 passed; test_layers 31 passed;
test_repo_map 82 passed. `python -m ruff check .`: all checks passed.
`python tools/repo_map.py check`: current (302 nodes). Not run: the 3.11
floor (no interpreter for it in this container).

Findings: 0 must fix, 0 should fix, 1 nit.

**L1 (Review 7's nit), fixed by the landing session:** the helper's first
paragraph now says "with its ``problem`` and no ``tax_year``" instead of
"and is not active". Wording only; no test or behaviour changes. Lane closed
at this commit.
