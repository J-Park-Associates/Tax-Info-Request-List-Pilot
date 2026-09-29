# Shell S2 rebuild 1

Branch `claude/shell-s2-menus` (local `rebuild-s2`), rebuilt from review 1 at
`adf4902`+review. The last commit is the one that adds this file; its sha is
in the final report. Only F1-F3 were touched. No finding was wrong.

## F1 - the unknown-id test did not pin the drop: fixed

`tests/test_shell.py::test_the_menu_channel_drops_what_it_does_not_know` now
sends a second `{enable: ["overview"]}` right after the first message (which
holds `"overview"`, `"check"`, `"constructor"` and other strays) and still
asserts `len(menus) == 2`: dropped ids leave the same list, so no rebuild.
Proof: in a scratch edit `main.js` `known()` was changed to keep every string
id (`typeof id === "string"` only). The test then FAILED (assert at line 333,
1 failed, 19 passed). `main.js` was restored byte for byte (`git status`
showed only the test file changed). The test passes with the real code.

## F2 - stale map notes: fixed

`docs/repo-map.curated.json`: the `app/main.js` notes now say a failed
command's reply adds `vocab.shell.no_log` and its stderr is neither kept nor
shown (SPEC-shell 11.2), with no `STDERR_ON_SCREEN_CAP`; `after-install-done`
is "one of two main-to-renderer channels, with MENU_CHANNEL"; open-path also
opens the error log `vocab.shell.error_log` names, as a file. The
`artifact:tracker-errors.log` role now says the reply says there is no error
log and stderr is dropped, and that Help > Open error log opens it. I also
added "when there is a log" to its "stderr the shell appends" clause, which
was otherwise still true only in that case. `repo_map.py update` was run.

## F3 - runbook: fixed

`docs/runbook.md` (~569-571) now reads "with no data folder, a failed
command's message says there is no error log, and its details are not kept
or shown."

## Tests run (each file its own process, in parallel)

| File | Python 3.11 | Python 3.13 |
|---|---|---|
| test_shell | 20 passed | 20 passed |
| test_single_source | 168 passed | 168 passed |
| test_repo_map | 80 passed | 80 passed |
| test_layers | 29 passed | 29 passed |

`python -m ruff check .` passed; `repo_map.py update` then `check` current.
