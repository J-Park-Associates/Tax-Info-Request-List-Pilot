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
  parenthesis. SPEC section 12 itself was not edited (the brief limits the
  files).
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
