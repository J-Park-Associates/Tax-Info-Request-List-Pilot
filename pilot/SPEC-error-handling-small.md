# The error-handling audit's small findings, E2 to E7 - SPEC

Status: written 2026-10-13 for a separate builder and a separate reviewer.
Decisions **P297-P300** (`pilot/DECISIONS.md`; the rows are added by the
session that lands this, not by the builder - the other lane's rows go in
beside them). Source: `pilot/AUDIT-2026-10-13-error-handling.md`, findings
E2 to E7, read against commit `e8661e9`; E1 is built
(SPEC-client-folder-unreadable). No version number changes.

**Not in this SPEC:** E8, the store's gate reading the Document
(`pilot/SPEC-document-gate.md`), built in parallel by another builder in the
same checkout. This build touches none of its files.

**Hard rules kept.** No generative AI reads a client document. Nothing is
sent. Nothing new is written into a tree a client is shared. No layer moves.
Every caught exception is said through `tracker.errors` (`errors.keep`,
`errors.said`, `errors.error_class`, or the new `errors.error_code`), never
`str(exc)`, an f-string or `.args`: `tests/test_errors.py` scans every
`except` handler under `tracker/` for exactly that.

## What staff will notice (plain English)

A Roll forward that could not read last year's index says so in the dialog
instead of silently listing no unfiled documents. A busy or broken database
is said in plain words with its code, and Retry stays. A data folder
override that points at a file is refused by name at Settings and at the
first command, not with "an error it did not expect" and no log. Nothing
else changes on screen; the rest is the error log carrying what it should.

---

## 1. R1 - E2: a rollover says when it could not look (`tracker/rollover.py`)

`_unfiled_last_year(prior_dir)` returns `[]` on any failure to read the prior
year's index ("must never block a rollover"). Keep the rollover going, but
say so:

- `_unfiled_last_year` returns `tuple[list[str], str]`: the lines, and `""`
  or `UNFILED_LAST_YEAR_UNREAD.format(problem=errors.said(exc,
  (FilingError, ManifestError, LedgerError, StoreError)))` when the read
  failed. The exception is kept first:
  `errors.keep("rollover: last year's unfiled documents", exc, name=prior_dir.name)`.
- `UNFILED_LAST_YEAR_UNREAD = ("Last year's unfiled documents could not be listed ({problem}), "
  "so the new list carries none of them; check last year's `00 - Needs Review` by hand")`.
- The note reaches the dialog. **Trap:** `report.warnings` is *assigned*
  later in the same rollover (`roll.report.warnings = list(create_engagement(...))`
  near line 905, and `result.warnings = list(create_engagement(...))` near
  line 1107), so a note appended at line 512 is overwritten. Keep the note on
  the report (`RolloverReport.unfiled_last_year_unread: str = ""`) and append
  it to `warnings` **after** each of those assignments, so it is in
  `report.warnings` when the rollover returns. The API's reply already sends
  `warnings`; the page already draws them (`app/renderer/app.js`, the
  `one.warnings` loop). No page change.
- Tests (`tests/test_rollover.py`): a prior year whose index cannot be read
  (monkeypatch `filer.read_index` to raise `FilingError("the index is torn")`)
  → the rollover completes, `report.unfiled_last_year == []`, the sentence
  with the index's own words is the last line of `report.warnings`, and the
  error log holds the exception. A prior year that reads → no note, as today.
  `tests/test_api.py`: the `roll` reply's `warnings` carry the sentence.

## 2. R2 - E3 and E4: nothing is swallowed without a log line

- `tracker/api.py`, the cleanup after a failed `create`
  (`store.forget(store.connect(), engagement)` inside `except Exception: pass`):
  `except Exception as exc: errors.keep("api: forgetting a failed return", exc, name=engagement.name)`.
  Nothing else changes: the ghost row is still forgotten on the next attempt,
  as the docstring says.
- `tracker/rollover.py`, the same pattern after a failed rollover
  (`store.forget(store.connect(), target)`):
  `errors.keep("rollover: forgetting a failed return", exc, name=target.name)`.
- `tracker/filer.py` `_details_of`: `except Exception as exc:
  errors.keep("filer: the return's details", exc, name=engagement_dir.name);
  return None`. The sort still runs with `people=()` (nothing is guessed), but
  a race between the runner's read and this one now shows in the log.
- Tests: one each, monkeypatching the call to raise, asserting the behaviour
  is unchanged (the cleanup finishes; `_details_of` returns `None`) and the
  log entry is exact (`"api: forgetting a failed return (<folder>)"` and so
  on, in `caplog.text` at WARNING on `errors.DEBUG_LOGGER`).

## 3. R3 - E5: a database that cannot be used is said as itself (`tracker/api.py`, `tracker/errors.py`)

`_failure_of` says `store.StoreUnavailable` and `ledger.RecordNotWritten` with
`FAILED` ("The app hit an error it did not expect (StoreUnavailable
(SQLITE_BUSY))"). Decision 189 made both expected classes with a code.

- `tracker/errors.py`: `error_code(exc) -> str`: the code alone -
  `exc.code` for a class marked `SAYS_ITS_CODE`, the errno's name for an
  `OSError` that has one, else the class name. Spelled beside
  `error_class`, which keeps its own form; `errors.py` is the one module the
  one-definition test does not scan, so this is where a code is read.
- `tracker/api.py`, two sentences:
  `STORE_UNAVAILABLE = ("The app's database could not be used just now ({code}); nothing was changed. "
  "Try again in a moment; if it keeps happening, the details are in {log}")` and
  `RECORD_NOT_WRITTEN = ("The record could not be written ({code}); nothing was changed. "
  "Free the disk or close whatever holds the record open, then try again; the details are in {log}")`,
  with `code=errors.error_code(exc)` and `log=ERROR_LOG_FILENAME`. The
  branch keeps `kind = "failed"`, so the window keeps Retry (P278's comment
  on the branch below it explains what the kind controls).
- `docs/runbook.md`, the paragraph in section 6 that says the dialog names
  the fault "by its kind and code alone - *StoreUnavailable (SQLITE_BUSY)*,
  *RecordNotWritten (ENOSPC)*": the dialog now says *the app's database
  could not be used just now (SQLITE_BUSY)* and *the record could not be
  written (ENOSPC)*; the run log and the pass keep the class-and-code form.
  Exact find-and-replace of that clause; nothing else in the paragraph.
- Tests: `tests/test_api.py` pins the old wording at the parametrised
  `error_class` test near line 7267 - keep that test (it is about
  `error_class`) and add one that `_failure_of(store.StoreUnavailable("SQLITE_BUSY"))`
  is `kind == "failed"` with the new sentence, and the same for
  `ledger.RecordNotWritten("ENOSPC")`; `tests/test_errors.py` pins
  `error_code` for the three cases. `test_tripwire` and `test_single_source`
  run (wording changed).

## 4. R4 - E6: the data home must be a folder or makeable (`tracker/settings.py`)

In `resolve_data_home`, after `answer` is chosen and before the
program/synced/drive checks: if `answer` exists and is not a folder, or the
nearest existing ancestor of `answer` is not a folder, raise
`SettingsError(DATA_HOME_NOT_A_FOLDER.format(home=answer, blocker=<that path>))`,
`DATA_HOME_NOT_A_FOLDER = "the app's data folder {home} cannot be used: {blocker} is a file, not a folder"`.
The function already reads the disk (`LOCALAPPDATA.is_dir()`), so the pure
core stays testable with `tmp_path`. This refuses at `set-root`, at `list`
and at the first write alike - every command resolves the data home before
it reads the store - and that is intended: the error log lives there, so a
command that cannot have it must say so rather than fail later with no log.
Tests (`tests/test_settings.py`, the `resolve_data_home` helper near line
379): the override naming a file; the override under a file (`<file>/x`); a
makeable path under an existing folder still answers.

## 5. R5 - E7: the vocabulary sends only what something reads (`tracker/api.py` `_vocab`)

The audit lists nineteen keys it believes nothing reads: `statuses`, `view`,
`progress`, `evidence`, `period_pattern`, `example_root`,
`default_extensions`, `expected_pattern`, `year_note`,
`keyword_default_note`, `extension_default_note`, `candidate_separator`,
`unknown_year_label`, `origin_prior`, `override_labels`, `not_asked_key`,
`unscanned_key`, `unscanned_label`, `ask_the_client_note`. **Some are
read:** `tests/test_shell.py` near line 1892 lists `year_note` and
`ask_the_client_note` among keys the page draws, and
`tests/test_single_source.py` near line 1015 excludes
`chip-${vocab.unscanned_key}` as a renderer literal. The page reads the
vocabulary through `vocab.<key>`, `words.<key>`, bracket access and loops.

**The rule:** a key is dropped only when its bare name has **no hit of any
kind** under `app/` (every `.js` and `.html`, grepped for the bare name) and
in no `tracker/` module but `api.py`, and no doubt remains. Any doubt keeps
it; a dropped key the page reads draws `undefined` with no error, the
opposite of fail-loudly. For each of the nineteen the builder records in the
handoff a one-line evidence row: the grep forms tried and the hit count under
`app/`, `tracker/` (minus api) and `tests/`. For each dropped key: remove
the `_vocab` entry, its entry in `tests/test_api.py` `_TITLE_EXEMPT_BRANCHES`
if any, and the test lines that only pin that key's value (a test that pins
other things keeps its other assertions). `test_single_source`'s "the
renderer types no vocabulary of its own" and "every key the page reads is
sent" keep passing. The reviewer re-greps the page for every dropped key.

## 6. Files

Code: `tracker/rollover.py`, `tracker/api.py`, `tracker/filer.py`,
`tracker/settings.py`, `tracker/errors.py`. Docs: `docs/runbook.md` (R3
only). Tests: `tests/test_rollover.py`, `tests/test_api.py`,
`tests/test_filer.py`, `tests/test_settings.py`, `tests/test_errors.py`.
Then `python tools/repo_map.py update`. **Not** `pilot/DECISIONS.md`, and
not any file the document-gate build owns (`tracker/{records,store,manifest,templates}.py`
and `tests/test_{records,store,manifest,templates,row_columns}.py`). Both
lanes edit `tests/test_api.py`: this lane adds tests near the ones it
changes and never rewrites the file whole; the other lane's additions sit in
other places. `docs/repo-map.curated.json` only if a node's text for these
modules becomes wrong.

## 7. The gate

Dead code first. Then one process per file, in parallel: `test_rollover`,
`test_api`, `test_filer`, `test_settings`, `test_shell`, `test_errors`,
`test_tripwire`, `test_layers`, `test_single_source`, `test_repo_map`. Then
`python -m ruff check .` and `python tools/repo_map.py check`. Another build
runs in the same checkout; if the map check or `test_repo_map` fails only on
its half-edited files, run `update` again and retry once, and say so. Never
the whole suite.

## 8. Handoff

`pilot/HANDOFF-error-handling-small.md`: what was built against R1-R5, the
E7 evidence table, the gate's counts file by file, anything done
differently and why. The reviewer reads this SPEC, the diff and the handoff,
and writes numbered findings under "## Review".

## 9. Decision rows (added by the landing session)

| P297 | 2026-10-13 | A rollover that cannot read last year's index still rolls, and says so in the dialog's warnings (`rollover.UNFILED_LAST_YEAR_UNREAD`); the failed `store.forget` after a failed create or rollover and the filer's unreadable return details are kept on the error log where they were swallowed (SPEC-error-handling-small R1, R2). | The error-handling audit of 2026-10-13 (E2-E4): three silent fallbacks. |
| P298 | 2026-10-13 | A database the engine refuses and a record the disk refuses are said in the dialog as themselves with their code (`api.STORE_UNAVAILABLE`, `api.RECORD_NOT_WRITTEN`; `errors.error_code`), saying that what finished is on the record, with Retry; the pass and the run log keep the class-and-code form (R3). | E5: decision 189's expected classes were worded as "an error it did not expect". |
| P299 | 2026-10-13 | The data home must be a folder or makeable under one; `TRACKER_DATA_HOME` naming a file, or a path under one, is refused by name wherever the data home is resolved - `set-root` refuses outright, `list` answers an empty list with the sentence in its warnings, as for any settings error (`settings.DATA_HOME_NOT_A_FOLDER`) (R4, as the first review read it). | E6: the first write failed with no error log, because the log lives in the data home. |
| P300 | 2026-10-13 | The API's vocabulary sends only keys something reads; a key is dropped only when its bare name has no hit under `app/` or in any tracker module but `api`, with the evidence recorded in the build's handoff (R5). | E7: nineteen keys were believed unread; some were. |

---

## 10. Amendments after the first review (Opus, 2026-10-13)

Findings F1-F5 are in `pilot/HANDOFF-error-handling-small.md` under
"Review". None survived a rebuild, so the rebuild is Sonnet's. All five are
built; F1 and F4 were this SPEC's wording.

**R3, amended (F1).** "nothing was changed" is false in the common busy case:
`store.record` writes the journal line first and applies it to the database
after, so a busy database fails with the line already on the record (the
database replays the journal on the next read). Both sentences drop that
clause for the old one, which is true:
`STORE_UNAVAILABLE = ("The app's database could not be used just now ({code}). What it finished is on the record; "
"try again in a moment, and if it keeps happening the details are in {log}")` and
`RECORD_NOT_WRITTEN = ("The record could not be written ({code}). What it finished is on the record; "
"free the disk or close whatever holds the record open, then try again - the details are in {log}")`.
The P298 row in section 9 is reworded to match. The runbook sentence does
not quote the clause; check it still reads true.

**Dead code (F2).** `tracker/templates.py`: `YEAR_NOTE`, `EXTENSION_DEFAULT_NOTE`
and `KEYWORD_DEFAULT_NOTE` are dead since R5 dropped their keys; remove them
and the `DEFAULT_EXTENSIONS` import that then has no user (ruff names it
once the constants go). `templates.py` was the other lane's during the
build and is free now.

**The one-definition table (F3).** `tests/test_errors.py`: `_code_of` is a
second place an errno's name is read in order to say an error, so it belongs
with `THE_ONE_DEFINITION` (made a set of the two `errors.py` functions), not
in `ERRNO_NAMED_ON_PURPOSE`, whose docstring says "for something other than
saying an error". Move it; the test's docstring says why both are there.

**R4, reworded (F4).** `list` does not refuse: it answers an empty list with
the sentence among its warnings, as it does for any settings error, and
`set-root` refuses with exit 1. Section 4's "refuses at `set-root`, at `list`
and at the first write alike" reads from here as "is said at `set-root`
(refused), at `list` (an empty list with the sentence in its warnings) and
at the first write". P299 in section 9 is reworded to match. No code change.

**Stale lines (F5).** `tests/test_single_source.py`: the no-op
`unscanned_key` replace near line 1015 and the `ask_the_client_note` stub
near line 3966 are removed; both referred to dropped keys.

Gate after the rebuild, one process per file: `test_api`, `test_templates`,
`test_errors`, `test_single_source`, `test_tripwire`, `test_layers`,
`test_repo_map`, ruff, the map check. The builder appends
`## Rebuild 1 (Sonnet, 2026-10-13)` to the handoff.

---

## 11. After the second review (Opus, 2026-10-13)

Review 2 found nothing against the code. G1 (should fix) was the map
committed in `48a1f8b` while the rollover rebuild was mid-edit in the same
checkout; `57c3f83` made it current again and it lands in the same pull
request, so nothing is left to do. G2: the Rebuild 1 handoff note that P298
still needed rewording was wrong - `bf22b65` had reworded it. G3 (optional
tightening of `test_errors`' scan of `errors.py`'s own functions) is not
taken: the one-definition rule guards every other module, and `errors.py` is
the definition. G4 (commit trailers) is the session's attribution line, not a
record of which model built what; the handoffs are. The lane is closed at
`48a1f8b`.
