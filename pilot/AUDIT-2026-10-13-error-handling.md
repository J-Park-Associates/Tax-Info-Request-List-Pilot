# Error handling, edge cases and the page/API contract audit, 2026-10-13

Run by Jason's instruction on `claude/admiring-goodall-vhomni`, read against
commit `e8661e9` (a snapshot of that commit under the scratchpad, so the
form-inputs build going on in the same checkout could not skew a result).
Three questions: does any `try/except` swallow an error a person should
hear about; does an edge case outside what a SPEC named fall to a generic
fallback; and has the page's contract with the API drifted. Then the three
scenarios asked for, run live against the real API with a scratch clients
root: the API failing outright, the database locked or broken, and a missing
environment variable. This note changes no code.

## 1. The answer

**The contract has not drifted, and it cannot drift quietly.**
`tests/test_single_source.py` pins that the page calls only commands the API
has (`test_the_renderer_calls_only_commands_the_api_has_and_types_no_flag`),
every vocabulary key the page or the shell reads (`vocab.*`, 45 keys) is one
`api._vocab()` sends, every failure-envelope key the page reads (`sentence`,
`kind`, `identifier`, `lock`, `key`, `detail`) is one `api._failure_of`
writes, and the shell's own sentences are held word for word to the API's
`SHELL_*` constants. The page learns its command list, its path kinds and
its words from the API at start, so an older page and a newer API disagree
on nothing but what the API refuses by name ("not a column this version
knows; close the app and open it again").

**Errors reach a person.** Every renderer `catch` but three routes to
`failed(err)`, which draws the failure envelope as a notice; the three are
deliberate fail-safes (a locked `localStorage` reads as nothing held, a row
whose label cannot be built is drawn unnamed, a row that cannot be built at
all is collected in `pagesBroken` and listed). The shell's bare `catch`
blocks guard the fallback error log, file watchers and JSON parsing, and a
reply that is not JSON becomes the "No Reply From the App" failure with the
exit code. In the Python, 73 of the handlers log through `errors.keep` or
`log.warning` and re-say the failure in a run note or the envelope; the
handful that return a default silently are listed in section 2.

**The three scenarios:**

| Scenario | What happened | Verdict |
|---|---|---|
| The API fails outright (its "500") | A Python exception the API did not classify becomes `{"error", "failure": {"kind": "failed"}}`, exit 1, with the trace in `tracker-errors.log` and the sentence "The app hit an error it did not expect (Class). ... the details are in tracker-errors.log". A process that prints no JSON, or is killed at the time limit, is said by the shell as "No Reply From the App" / "Stopped: Ran Too Long" with the exit code, and the stderr goes to the error log. Both paths are tested (`test_single_source.py`: the killed-at-limit and no-reply tests; `test_shell.py`). | Held. |
| The database times out or is broken | A store locked exclusively by another process: reads of the record still answer (they read the journal), a write waits `store.BUSY_TIMEOUT_MS` (5 s) and then fails with the envelope above naming `SQLITE_BUSY`; nothing is written. A store file that is not a database: `SQLITE_NOTADB` the same way, and the pass marks every return "the record could not be read: the database could not be used (SQLITE_NOTADB)", code `record-unreadable`. A held engagement lock: the pass refuses with "another pass holds this return's lock (taken 2 s ago); nothing was changed". | Held, with one wording point (E5). |
| A required environment variable is missing | On Linux and the Mac the data home falls back to the account's home folder (`XDG_STATE_HOME`, then `~/.local/state`; `~/Library/Application Support`); with no home at all it refuses (`NO_HOME`). On Windows a missing or non-folder `LOCALAPPDATA` refuses (`NO_LOCAL_APPDATA`, `LOCAL_APPDATA_NOT_A_FOLDER`). A relative `TRACKER_DATA_HOME` is refused by name the first time the data home is needed. The settings folder has no such check and needs none (it is the program's own folder). | Held, with one gap (E6). |

## 2. Findings

Severity is for the firm's single-user desktop app and its scheduled pass.

| # | Where | Finding | Severity | Suggested fix |
|---|---|---|---|---|
| E1 | `tracker/households.py` `client_side_expected`; its callers `client_folder_missing`, `tracker/runner.py` (the held-back check), `tracker/scaffold.py` (`may_make_household is None`) | **Reproduced.** The function answers "had a client folder" from the household's record (`shared_on`) and its returns' originals; a record it cannot read is swallowed (`except Exception: pass` / `continue`) and the answer falls through to `False`, which means "never had one". So a household the firm marked shared, whose client folder is gone and whose record holds one line the ledger refuses (a hand edit, an older version, a sync conflict), gets a **new empty `Clients\Smith` made under the old name** by the next scheduled pass, while the same pass warns that the record could not be read. SPEC-162 ruling 2 and decision 188 say nothing is made again under the old name when the household had one. `create` in the same state refuses correctly, so the pass and the dialog disagree. A locked store does not trigger it (the check reads the journal). | **Should fix - medium.** A read failure becomes a write into the tree a client is shared. | `client_side_expected` must not answer when it cannot read: let the exception out (or return `None` for "cannot tell") and have `client_folder_missing` turn that into a hold-back sentence naming the unreadable record, so the runner holds the household (code `record-unreadable`) and the scaffold raises `ClientFolderMissing`. Test: a shared household, folder gone, one unlinked line → nothing made, the run says why. |
| E2 | `tracker/rollover.py` `_unfiled_last_year` | An unreadable prior-year index returns `[]` ("must never block a rollover"), so the rolled return's report lists no unfiled documents and says nothing about not having looked. | Low | Keep the rollover going, but carry one note in `report` ("last year's unfiled documents could not be listed: ...") the dialog shows, and `errors.keep` the exception. |
| E3 | `tracker/api.py` the cleanup after a failed `create` (`store.forget` in `except Exception: pass`); `tracker/rollover.py` the same pattern after a failed rollover | A ghost store row left by a failed cleanup is forgotten on the next attempt, as the comment says, but the failure itself is not logged. | Low | `errors.keep("api: forgetting a failed return", exc)` in both places. Nothing else changes. |
| E4 | `tracker/filer.py` `_details_of` → `people=()` | A return whose details cannot be loaded at that moment is sorted with no people, so every named request parks for review. Conservative (nothing is guessed), but silent at that spot; it relies on the runner having already reported the record unreadable, which holds today because both read the same record in one pass. | Low | `errors.keep` the exception where it is swallowed, so a race shows in the log. |
| E5 | `tracker/api.py` `_failure_of` for `store.StoreUnavailable` / `ledger.RecordNotWritten` | **Reproduced.** A busy or broken database is said as "The app hit an error it did not expect (StoreUnavailable (SQLITE_BUSY))". Decision 189 made it an expected class with its own name, and the pass already words it well ("the record could not be read: the database could not be used (SQLITE_NOTADB)"). | Low (message) | A sentence of its own: "The app's database could not be used just now (SQLITE_BUSY); nothing was changed. Try again in a moment; if it keeps happening, the details are in tracker-errors.log." |
| E6 | `tracker/settings.py` `resolve_data_home` | **Reproduced.** The Windows branch checks `LOCALAPPDATA` is a folder; the override and the Linux/Mac branches do not. `TRACKER_DATA_HOME` pointing at a file, or under a path that cannot be made (`/proc/version/x`), passes `set-root` and `list`, and the first write fails with "The app hit an error it did not expect (FileExistsError (EEXIST))" and no error log (the log lives in the data home). | Low | After `answer` is chosen: if it exists and is not a folder, or its nearest existing parent is not a folder, refuse with a `DATA_HOME_NOT_A_FOLDER` sentence, at `set-root` as well as at the first write. |
| E7 | `tracker/api.py` `_vocab` | Nineteen vocabulary keys are sent that neither the page nor the shell reads (`statuses`, `view`, `progress`, `evidence`, `period_pattern`, `example_root`, `default_extensions`, `expected_pattern`, `year_note`, `keyword_default_note`, `extension_default_note`, `candidate_separator`, `unknown_year_label`, `origin_prior`, `override_labels`, `not_asked_key`, `unscanned_key`, `unscanned_label`, `ask_the_client_note`). Some are read by tests or the status page; the rest are drift in the other direction - words the API keeps for a page that no longer asks. | Nit | Check each against `tests/` and `tracker/view.py`; drop what nothing reads, so the single-source tests guard a smaller surface. |

Also seen and correct: `list` answers while the store is locked or broken
(it reads the journals, and the pass says the store is unusable); a deleted
return folder leaves the household listed as a misfit and `state` on it says
"the journal holds fewer lines than the store has applied ... restore the
journal from Drive's trash or version history"; an unlinked line in a return's
record is refused on read with "line N was written without the record's link
... Run recover (runbook §6)"; the error log and the run log rotate through
the hand-rolled rotation in `tracker/fsio.py` (decision 186), so neither grows
without bound; the engine's progress hints (`tracker/progress.py`) are
documented never to raise and return `None`, which is right for a hint.

## 3. What is left

E1 is the one item worth a SPEC on its own, with the reproduction above as
its test. E2 to E6 are small and can ride one build. E7 is a cleanup.
Nothing here was changed; the form-inputs build in progress on this branch is
separate.
