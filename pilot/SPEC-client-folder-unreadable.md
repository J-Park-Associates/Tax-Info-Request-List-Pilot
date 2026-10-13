# A household whose record cannot be read is never laid out again - SPEC

Status: written 2026-10-13 for a separate builder and a separate reviewer.
Decision **P296** (`pilot/DECISIONS.md`; the row is added by the session that
lands this, not by the builder - another build edits that file at the same
time). Source: `pilot/AUDIT-2026-10-13-error-handling.md`, finding E1,
reproduced there against commit `e8661e9`. No version number changes.

**Not in this SPEC:** E2 to E7 of the same audit.

**Hard rules kept.** Nothing new is written into the tree a client is shared
with on a read failure. No generative AI reads a client document. No layer
moves: `households` keeps its imports; `runner`, `scaffold` and `registry`
import `households` already.

## What staff will notice (plain English)

A household the firm marked shared, whose `Clients\<name>` folder has gone
and whose record the app cannot read, is held back by the pass with one
sentence that says both things - the folder is missing and the record could
not be read, with the record's own reason - instead of getting a new, empty,
unshared `Clients\<name>` made under the old name. New return and Roll
forward refuse with the same sentence. Once the record reads again (runbook
section 6), the usual "Was the household renamed or moved?" verdict applies.

---

## 1. The finding

`tracker/households.py` `client_side_expected(household_dir, returns)`
answers whether the household *had* a client folder: the record says it was
shared (`shared_on`), or a recorded original of one of its returns rests
under `Clients\<name>`. Both reads are wrapped in `except Exception`
(`pass`, then `continue`), so a record the ledger refuses - an unlinked line,
a malformed line, a sync conflict - falls through to `False`: "never had
one". `client_folder_missing` then answers `""`, and the pass
(`tracker/runner.py`, the held-back block before `_worth_a_pass`) goes on to
`tracker/scaffold.py`, which makes `Clients\<name>` again
(`may_make_household`), while the same pass warns that the household's
record could not be read (`FEEDS_UNREAD`). `create` in the same state refuses
on the record, so the pass and the dialog disagree. Decision 188 and
SPEC-162 ruling 2: nothing is made again under the old name when the
household had one.

## 2. R1 - "cannot tell" is an answer of its own

In `tracker/households.py`:

- `class ClientSideUnknown(RuntimeError)`: raised when the household's
  client-side history cannot be read. Its message is the sentence below.
- `CLIENT_SIDE_UNKNOWN = ("`Clients\\{name}` is missing and the household's record could not be read ({problem}), "
  "so the app cannot tell whether the household was renamed or moved. Nothing is made under the old name "
  "until the record reads again (runbook section 6).")`
- `client_side_expected` keeps its signature and its `True`/`False` answers
  for a record that reads. A read failure in either half (`shared_on`, or
  `store.documents` of any return) is kept on the error log
  (`errors.keep("households: the client-side history", exc, name=folder.name)`)
  and raises `ClientSideUnknown(CLIENT_SIDE_UNKNOWN.format(name=folder.name,
  problem=errors.said(exc, (ManifestError, LedgerError, StoreError))))` -
  the same sanitiser the runner uses for `FEEDS_UNREAD`, so a sentence the
  firm wrote is quoted and anything else is named by class. No `except` in
  the function swallows anything any more.
- `client_folder_missing(household_dir, returns=None)` **looks at the disk
  first**: when `layout.client_household_dir(root, name).is_dir()` it returns
  `""` without reading the record (nothing is to be decided, and the pass
  asks this of every household). Only when the folder is gone does it ask
  `client_side_expected`; `ClientSideUnknown` passes through to the caller.
  `door.client_folder_missing` is unchanged.

## 3. R2 - the three callers each say what they do with it

- `tracker/runner.py`, the held-back block: wrap the
  `client_folder_missing(...)` call; on `ClientSideUnknown`,
  `held_back = str(exc)` and `held_code = CODE_RECORD_UNREADABLE` (the code
  the pass already uses for a record it cannot read; the remedy is the same).
  Every run of the household carries it, as the folder-missing case does.
- `tracker/scaffold.py`, the `may_make_household is None` branch: on
  `ClientSideUnknown`, `raise ClientFolderMissing(str(exc)) from None`, so
  `create` and every Roll forward refuse with the sentence and make nothing.
- `tracker/registry.py`, the household's pause sentence
  (`household_pause(folder) or client_folder_missing(folder)`): on
  `ClientSideUnknown` return `str(exc)`, so the list and the household's card
  show it where they show the folder-missing sentence today.

## 4. R3 - the runbook

`docs/runbook.md` has an entry for the "`Clients\<name>` is missing. Was the
household renamed or moved?" hold-back (find it by that phrase). Add one
paragraph after it: the variant sentence above, that it means the record is
the first thing to repair (section 6), and that no folder is made meanwhile.
`tests/test_single_source.py` may quote the layout's sentence; keep whatever
it pins passing.

## 5. Tests

- `tests/test_households.py`
  - `test_a_household_whose_record_cannot_be_read_is_not_said_to_have_had_no_client_folder`:
    a household record with one line appended that breaks the ledger's link,
    its client folder removed → `client_folder_missing` raises
    `ClientSideUnknown` whose message is `CLIENT_SIDE_UNKNOWN` filled with
    the household's name and the ledger's own sentence; the error log holds
    the exception.
  - `test_a_client_folder_that_is_there_is_never_a_reason_to_read_the_record`:
    with the folder present and `shared_on` monkeypatched to raise,
    `client_folder_missing` returns `""`.
- `tests/test_runner.py`
  `test_a_shared_household_whose_record_cannot_be_read_is_held_back_and_its_client_folder_is_not_remade`:
  the audit's reproduction - a household marked shared, its client folder
  removed, one unlinked line in its record, a pass → every run of the
  household has `error == CLIENT_SIDE_UNKNOWN.format(...)` and
  `code == CODE_RECORD_UNREADABLE`, nothing is filed, and
  `Clients\<name>` does not exist after the pass. The existing
  `test_a_household_renamed_in_the_firm_tree_pauses_and_makes_no_client_folder`
  and `test_a_new_return_or_a_roll_forward_never_makes_a_gone_client_folder_again`
  keep passing unchanged.
- `tests/test_scaffold.py`
  `test_the_scaffold_refuses_to_lay_out_a_household_whose_record_cannot_be_read`:
  `ClientFolderMissing` with the sentence; no folder made.
- `tests/test_registry.py` (if the household pause sentence is tested there;
  else `tests/test_households.py`)
  `test_a_household_whose_record_cannot_be_read_says_so_where_its_pause_is_said`.

## 6. Files

Code: `tracker/households.py`, `tracker/runner.py`, `tracker/scaffold.py`,
`tracker/registry.py`. Docs: `docs/runbook.md`. Tests: `tests/test_households.py`,
`tests/test_runner.py`, `tests/test_scaffold.py`, `tests/test_registry.py`.
Then `python tools/repo_map.py update`. **Not** `pilot/DECISIONS.md` (the
landing session adds P296) and not any file the form-inputs build owns
(`tracker/{api,records,layout,door,manifest,templates,store,settings,filer}.py`
and their tests).

## 7. The gate

Dead code first. Then one process per file, in parallel: `test_households`,
`test_runner`, `test_scaffold`, `test_registry`, `test_door`, `test_layers`,
`test_single_source`, `test_repo_map`. Then `python -m ruff check .` and
`python tools/repo_map.py check`. Another build runs in the same checkout;
if the map check or `test_repo_map` fails only on its half-edited files, run
`update` again and retry once, and say so in the handoff. Never the whole
suite; the router and the readers are untouched.

## 8. Handoff

`pilot/HANDOFF-client-folder.md`: what was built against R1-R3, the gate's
counts file by file, anything done differently and why, the files the
reviewer needs. The reviewer reads this SPEC, the diff and that handoff, and
writes numbered findings under "## Review".

## 9. Decision row (added by the landing session)

| P296 | 2026-10-13 | A household whose client folder is gone and whose record cannot be read is held back with one sentence saying both (`households.ClientSideUnknown`), never laid out again under the old name; the pass, New return, Roll forward and the household's card all say it, and a client folder that is there is never a reason to read the record (SPEC-client-folder-unreadable). | The error-handling audit of 2026-10-13 (E1): a swallowed read failure answered "never had one" and the pass remade `Clients\<name>` while warning the record could not be read. |
