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
