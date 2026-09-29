# Shell S2 rebuild 4

Branch `claude/shell-s2-menus` (local branch `rebuild-s2-4`), built on rebuild 3
(`690905f`) plus review 4. The code commit is `5a681b4`; the commit that adds
this file and the refreshed map is the branch tip (`git log -1`).

## Review 4 findings, each fixed

**F1: the link refusal had no test.** `appendToLog` already returns early when
the saved-log path is a symbolic link (`app/main.js`, the `isSymbolicLink()`
test). Now tested:

- `test_the_fallback_log_is_capped_and_a_write_that_fails_never_throws` gains a
  link case: `error.log` is a link to a file; after a failure the target is
  unchanged and the reply still ends with `Tracker failed`.
- `test_open_error_log_refuses_a_fallback_that_is_a_link_or_a_folder` gains a
  link case (Open error log does not open a linked fallback).
- Both cases skip themselves where the OS forbids a symlink; they run in the
  cloud (Linux) and did run under 3.11 and 3.13.
- **Proof.** On a scratch copy, the refusal at `appendToLog` was changed to
  follow links (`!info.isFile() && !info.isSymbolicLink()`). The capped test
  failed (the link's target gained the stderr text). Restored; not in the repo.

**F2: dead value and stale comment.** `keepInLog` now returns nothing (its
"whether there is a log" sentence is gone). The harness comment in
`tests/test_single_source.py` no longer says the write is not waited on.

**Edge note: a folder named `error.log.1`.** Rotation used to throw at the
folder and drop every later write. Now, if the rotation cannot be done
(remove `.1`, rename), the old log is removed instead and the append goes on,
so the cap still holds and later writes still land. The folder is left alone.
Tested in the capped test (two failures in a row after the folder is there).

## Jason's rulings

1. **Fallback log is local and non-roaming.** On Windows:
   `%LOCALAPPDATA%\Tax Document Tracker Pilot\error.log` (`process.env.LOCALAPPDATA`,
   else `os.homedir()\AppData\Local`; folder name is `productName`). Off Windows
   (tests, dev runs): `app.getPath('userData')`. Same behaviour otherwise:
   256 KB rotates to `error.log.1`, every write caught, links and folders
   refused, Open error log opens the named log else the fallback.
   Not `tax-document-tracker-pilot` (data home, hyphens) and not
   `tax-document-tracker` (upstream): `test_on_windows_the_fallback_log_is_local_and_never_the_roaming_or_data_folder`
   asserts the names differ and neither folder is created. `test_build` and
   `test_single_source` package checks pass (only the known OCR scratch-roots
   failure, which fails on the base too). Text changed: `app/main.js`,
   SPEC-shell 5.5 and 11.2, runbook (error-log entry), curated map notes
   (three places), this file, and the tests (both shell harnesses force
   `process.platform`, `linux` by default, so tests do not depend on the host).
2. **Deny list.** Added to `.claude/settings.json` after the existing rules,
   Read and Edit forms only (the file has no Grep/Glob/Bash forms), in the two
   styles the data-home rules use (Windows `//c/Users/*/...` and a `~/` path,
   which for Electron's userData off Windows is `~/.config/...`), the same
   file plus `.*` pattern as `tracker-errors.log`:

```
Read(//c/Users/*/AppData/Local/Tax Document Tracker Pilot/error.log)
Edit(//c/Users/*/AppData/Local/Tax Document Tracker Pilot/error.log)
Read(//c/Users/*/AppData/Local/Tax Document Tracker Pilot/error.log.*)
Edit(//c/Users/*/AppData/Local/Tax Document Tracker Pilot/error.log.*)
Read(~/.config/Tax Document Tracker Pilot/error.log)
Edit(~/.config/Tax Document Tracker Pilot/error.log)
Read(~/.config/Tax Document Tracker Pilot/error.log.*)
Edit(~/.config/Tax Document Tracker Pilot/error.log.*)
```

   The pin `test_the_agent_deny_list_names_the_data_home_and_every_file_that_names_a_client`
   now expects them (`_fallback_log_rules()`, spelled from `package.json`'s
   `productName`). A bare `//**/error.log` was not used: it would refuse any
   person's unrelated `error.log`. Nothing else in `.claude/` changed.

## Left as it was (for Jason to confirm)

The reply text is unchanged: the failure's own sentence, a blank line, then
`Tracker failed`. Review 4's note stands: if Jason wants only the two words on
screen, that is a one-line change in `withNoLog` and its pinned tests.

No renderer file changed. No network call; nothing reads a client document;
nothing is sent.

## Tests run (each file its own process, in parallel, Python 3.11 and 3.13)

test_shell 23, test_single_source 171, test_api 380, test_layers 29,
test_errors 83, test_tripwire 19: all passed under both. test_build 30 passed,
1 failed (the OCR scratch-roots test, failing on the base). `ruff check .`
passed. `repo_map.py update`, `check` and `test_repo_map` run last (results in
the tip commit message).

## Proposed decision rows for S6

- **Fallback log is local, non-roaming, and denied to the agent.** With no data
  folder the shell saves the failure to `%LOCALAPPDATA%\Tax Document Tracker Pilot\error.log`
  (256 KB cap, one `.1` copy; `userData` off Windows), never the roaming
  `%APPDATA%`, the data home or the upstream folder; its path is in the agent
  deny list, pinned by test. Supersedes rebuild 3's `userData` location.
- **The fallback log is never written through a link, and a stuck `.1` never
  stops it.** A link or folder at `error.log` is left alone; if `error.log.1`
  cannot be replaced, the old log is dropped and writing continues.
