# Shell S2 review 5 (opus, high effort)

Branch `claude/shell-s2-menus`, reviewed at `e50c531` (rebuild 4). The change
is `git diff dfa9e0c...HEAD`. The reviewer did not build S2 or any rebuild.
This review adds this file and runs `python tools/repo_map.py update`. It
changes no code and no settings.

## Verdict

No findings.

Review 4's two findings are fixed. Jason's rulings (a), (b) and (c) are
applied as ruled. Every behaviour below was checked against the code, and
the new tests were proved by mutation on scratch copies.

## What was checked, and holds

1. **Review 4, finding 1 (link refusal untested): fixed.**
   - The proof was reproduced on a scratch copy of the worktree (no `.git`).
     The refusal in `appendToLog` was changed to
     `if (info && !info.isSymbolicLink() && !info.isFile()) return;`, so the
     write follows a link.
     `test_the_fallback_log_is_capped_and_a_write_that_fails_never_throws`
     then fails: the link's target gains the stderr text.
   - `test_open_error_log_refuses_a_fallback_that_is_a_link_or_a_folder`
     now makes a link as well as a folder. Both link cases skip themselves
     only where the OS cannot make a link. They ran here, under Linux.

2. **Review 4, finding 2 (dead return, stale comment): fixed.**
   - `keepInLog` returns nothing (`if (!file || !text) return;`), and its
     "Whether there is a log" sentence is gone. None of its three callers
     read a value.
   - The `test_single_source` harness comment no longer says the append is
     not waited on.

3. **A folder named `error.log.1`: later writes still land and the cap holds.**
   - Rotation is now in its own `try`. If `.1` cannot be removed or the log
     cannot be renamed, the old log is removed instead, and the append goes
     on. The folder is left alone.
   - The capped test covers two failures in a row after the folder exists.
     After each, `error.log` holds only the new text, not the old 256 KB.
   - Two mutations fail that test:
     - Rethrowing from the inner `catch`, the old behaviour where writes
       stop.
     - Swallowing without removing the old log, where the cap breaks.
   - Removing the cap check altogether also fails it.

4. **The path (ruling a).** `fallbackLogPath()`:
   - On Windows it is `path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"), PRODUCT_NAME, "error.log")`.
   - Off Windows it is `app.getPath("userData")`.
   - A throw gives `null`, and then nothing is written.
   - `PRODUCT_NAME` is `package.json`'s `productName`,
     `Tax Document Tracker Pilot`.

   Three mutations each fail
   `test_on_windows_the_fallback_log_is_local_and_never_the_roaming_or_data_folder`,
   and the first two also fail
   `test_open_error_log_opens_the_local_non_roaming_fallback_on_windows`:
   - Windows given userData.
   - `LOCALAPPDATA` ignored.
   - The home-folder fallback replaced.

   The folder cannot collide with the others:
   - **Not the data home** `tax-document-tracker-pilot`: hyphens against
     spaces, so the names differ even on NTFS, which ignores case.
   - **Not the upstream** `tax-document-tracker`.
   - **Not the install folder**, which is
     `%LOCALAPPDATA%\Programs\Tax Document Tracker Pilot`. The uninstaller
     removes only that folder.
   - **Not the settings folder.**

   The test asserts that the names differ and that neither data folder is
   created. `test_build`'s "package holds no data" set is unchanged and
   passes.

   Nothing still gives userData or `%APPDATA%` as the Windows location:
   - `main.js`, SPEC-shell 5.5 and 11.2, the runbook entry, the three
     curated-map notes and the tests all say `%LOCALAPPDATA%`.
   - Where they mention userData, it is only for the off-Windows case, or to
     say "not the roaming `%APPDATA%`".
   - The only other mentions are in earlier handoff files, which are
     history.

5. **The deny list (ruling b).** `git diff dfa9e0c...HEAD -- .claude/` adds
   exactly the eight rules below. Its only `-` line is the old last rule
   again, with a trailing comma added so the list can go on. No rule was
   removed or loosened, no allow rule was added, and no other setting
   changed.

   ```
   Read/Edit(//c/Users/*/AppData/Local/Tax Document Tracker Pilot/error.log)
   Read/Edit(//c/Users/*/AppData/Local/Tax Document Tracker Pilot/error.log.*)
   Read/Edit(~/.config/Tax Document Tracker Pilot/error.log)
   Read/Edit(~/.config/Tax Document Tracker Pilot/error.log.*)
   ```

   **The coverage is right for this file's style:**
   - Every existing rule is a Read and Edit pair. There are no Grep, Glob or
     Bash forms.
   - Folder-scoped rules come in exactly these two spellings, as the data
     home's and the upstream folder's do: the Windows `//c/Users/*/AppData/Local/...`
     and a `~/` Linux path.
   - The `name` plus `name.*` pair matches `tracker-errors.log` and
     `runs.log`.
   - `~/.config/<productName>` is Electron's userData on Linux, which is
     where the fallback lands off Windows.
   - The rules name the folder rather than `//**/error.log`. That is the
     right call: `error.log` is a common name, and a bare rule would deny
     any unrelated one.

   **The pin was proved by mutation.** On a scratch copy,
   `test_the_agent_deny_list_names_the_data_home_and_every_file_that_names_a_client`
   passes unmutated. Removing any one of rules 0, 3, 4, 5 or 7 fails its
   equality assert. The eight rules are spelled from `package.json`'s
   `productName`, so renaming the product without the rules fails too.

6. **No regression (ruling c and the rest).**
   - **The words on screen are unchanged.** `withNoLog` still gives the
     failure's sentence, a blank line, then `Tracker failed`, as Jason ruled
     on 2026-09-29.
   - **No stderr reaches a reply.**
   - **The menu channel is untouched.**
   - **Open error log is safe.** It opens the named log if there is one,
     else the fallback, and always through `openChecked`'s lstat test. The
     fallback is never in `openable`.
   - **No renderer file changed.** Neither did `app/preload.js` nor
     anything under `tracker/`.
   - **The standing rules hold.** The only new require is Node's `os`, used
     for `homedir()`. No network call is added, nothing reads a client
     document, and nothing is sent.
   - **The test harnesses** force `process.platform` (to `linux` unless a
     test asks for `win32`), so the tests do not depend on the host.

7. **Scope.** Rebuild 4 touched only these files:
   - `.claude/settings.json`
   - `app/main.js`
   - `docs/runbook.md`
   - `pilot/SPEC-shell.md`
   - `docs/repo-map.curated.json`, and the generated `docs/repo-map.json`
     and `docs/repo-map.md`
   - `tests/test_shell.py`
   - `tests/test_single_source.py`
   - `pilot/handoffs/shell-S2-rebuild-4.md`

   There are no extras.

## Notes for Jason

1. **Limits the deny rules share with the existing ones.** These are not
   defects of this change:
   - The rules match only the default profile path on drive C. A redirected
     `LOCALAPPDATA` is not covered, and neither is the data home in that
     case.
   - As with every rule in the file, they bind Claude's file tools, not a
     shell command such as `type` or `cat`.
2. **A planted junction at the folder itself.** The lstat guard refuses a
   link at `error.log`. It does not refuse a junction at the
   `Tax Document Tracker Pilot` folder above it. Whoever can plant one can
   already write to the account's profile, and the same holds for the data
   home. Not worth code.
3. **Uninstalling leaves the fallback log behind,** as it leaves the data
   folder. It is at most about 512 KB (the log and one `.1` copy), and it
   can name a client. The runbook's move-to-another-machine steps could
   mention it if you want it cleared with the data.
4. **The trailers again read `Claude Sonnet 5.5`** on all three rebuild-4
   commits, as rebuilds 2 and 3 did. `CLAUDE.md` says Opus 5.5 builds. The
   shared history is left as it is.

## Gate run by the review

Each file ran as its own process, in parallel, under Python 3.11 (`/tmp/v`)
and 3.13 (`/tmp/v313`). The results were the same under both.

| Test file | Result |
|---|---|
| `test_shell` | 23 passed |
| `test_single_source` | 171 passed |
| `test_api` | 380 passed |
| `test_layers` | 29 passed |
| `test_repo_map` | 80 passed |
| `test_errors` | 83 passed |
| `test_tripwire` | 19 passed |
| `test_build` | 30 passed, 1 failed |

The one `test_build` failure is
`test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else`,
which also fails on the base.

- `python -m ruff check .` passed.
- `python tools/repo_map.py check` reported the map current at `e50c531`.
- In the mutation copies, seven `test_single_source` tests fail in any copy
  with no `.git`. They are left out of the mutation results above.
- After this file was added, `update`, then `check`, then `test_repo_map`
  were run again. The commit's message records the result.
