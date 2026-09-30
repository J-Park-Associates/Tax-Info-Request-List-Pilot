# Shell S2 review 4 (opus, high effort)

Branch `claude/shell-s2-menus`, reviewed at `690905f` (rebuild 3). The change
is `git diff 4a92488...HEAD`. The reviewer did not build S2 or any rebuild.
This review adds this file and runs `python tools/repo_map.py update`. It
changes no code.

## Verdict

Two findings, both small. Neither is a behaviour bug:

- Finding 1: one refusal has no test. The fallback log is never written
  through a symbolic link, and nothing tests that.
- Finding 2: one return value is now dead, and one harness comment is stale.

Jason's ruling is carried out correctly in `app/main.js` and `tracker/api.py`:

- With no log named, a failure is saved to the fallback log.
- The screen's added line is exactly `Tracker failed`.
- No stderr ever reaches a reply.
- Open error log falls back safely.

## What was checked, and holds

1. **The word.** `api.SHELL_NO_LOG == "Tracker failed"`, which is the same
   as `main.js`'s default `noLog` (`app/main.js:97`). Two tests pin this:
   `test_the_shells_default_words_are_the_apis_word_for_word` and the
   fallback test's own assert. `learn()` replaces `noLog` from
   `vocab.shell.no_log`, and that is `SHELL_NO_LOG` (`api.py:1629`).

   **No stderr reaches the reply.** The reply is built from stdout's last
   JSON line, from `killedReply` or from `shellFailure(noReply)`.
   `withNoLog` adds only `noLog`. stderr goes only to `keepInLog`
   (`:366`). The pass path (`onEnded`) sends the same `ending`.

2. **The fallback path** is `path.join(app.getPath("userData"), "error.log")`
   (`:128`). If `getPath` throws, the path is `null` and nothing is written.

   - **A named log:** `keepInLog` appends there with `capped=false`. The
     fallback is not touched, and no userData folder is created. The test
     asserts that `userdata` does not exist.
   - **Rotation:** when the file is over 256 KB before an append, it is
     renamed to `error.log.1`, after the older `.1` is removed.
   - **Every write is caught.** `appendToLog` wraps lstat, mkdir, rm,
     rename and append in one `try`. A link or a non-file at the path
     returns before any write. A userData path blocked by a file makes
     `mkdirSync` throw, and the throw is caught. The reply is unchanged.
   - **The writes are now synchronous** (`appendFileSync`). The failure reply
     is settled after the write. A write that fails cannot block the reply,
     because it throws at once and the throw is caught.

3. **Help > Open error log** (`openErrorLog`, `:523`) opens the named log
   when there is one. Otherwise it opens the fallback. Both go through
   `openChecked` (lstat, no link, a regular file). A missing file or a
   refused one sends `{id:'error_log', missing:true}`.

   `openPath` still refuses a path that is not in `openable` before it calls
   `openChecked`. The fallback is never added to `openable`.

   **Attempted break (probe on the real `main.js`, scratch harness).** The
   probe added an `open-path` handler to the `test_shell` harness. On the
   `open-path` channel the page sent:

   - the fallback's real path, before and after `list`
   - an unrelated real file
   - an object
   - `"__proto__"`
   - `"constructor"`

   Every call answered "That path is not one the tracker reported; nothing
   was opened", and `shell.openPath` was never called. The page cannot open
   the fallback or any path of its own choosing.

4. **Privacy and the standing rules.**
   - stderr goes only into a local file. Nothing in the change opens a
     socket or reads a client document, and no reply carries stderr.
   - **The fallback folder does not collide with the data home.** On
     Windows the fallback is `%APPDATA%\Tax Document Tracker Pilot` (from
     `productName`). The data home is `%LOCALAPPDATA%\tax-document-tracker-pilot`
     (`DATA_HOME_NAME`).
   - **The fallback is not the settings folder.** That folder is beside the
     program or the checkout (`settings_dir()`).
   - **The package check still holds.** `test_build`'s
     "package holds no store…" name set is unchanged, and the package ships
     no `error.log`.
   - **The deny list and the gitignore are unchanged.** `test_single_source`'s
     deny-list and gitignore tests pass.
   - **`main.js` still never spells `ERROR_LOG_FILENAME`.**

5. **Mutation check.** Each mutation was made on a scratch copy of the
   worktree, and `test_shell` and `test_single_source` were run in full.
   Seven `test_single_source` tests fail in any copy with no `.git`, and
   they are left out below.

   | Mutation | Caught by |
   |---|---|
   | Stop the fallback write (`file = named ? errorLog : null`) | `test_with_no_error_log_named_…_two_words`, `test_the_fallback_log_is_capped_…` |
   | Fallback append made a no-op | same two |
   | Open error log skips the fallback | `test_open_error_log_falls_back_…` |
   | stderr added to the reply (no log named) | `test_with_no_error_log_named_…_two_words` |
   | stderr added to the reply (log named) | `test_the_shell_never_puts_stderr_on_screen_…`, `test_with_an_error_log_named_…` |
   | Fallback also written when a log is named | `test_with_an_error_log_named_…` |
   | `try` removed around the write | `test_the_fallback_log_is_capped_and_a_write_that_fails_never_throws` |
   | Rotation removed | same |
   | Fallback opened without the lstat check | both new `test_shell` tests and the lstat pin |
   | `openable.has` guard removed from `openPath` | `test_the_shell_runs_only_commands_the_api_has` (a text check only) |
   | Word changed back to "Tracker failed; no error log" | three tests |
   | **The fallback write follows a symbolic link** | **nothing: finding 1** |

6. **The docs match the code.** These all describe the same file, cap,
   precedence and wording as the code:
   - SPEC-shell 5.5 (the fallback, and the menu bar hidden until Alt)
   - SPEC-shell 11.2
   - the `shell.no_log` row of `wording-shell.tsv`
   - the runbook entry at line 569
   - the curated notes for `app/main.js`, `app/preload.js` and
     `artifact:tracker-errors.log`

   `autoHideMenuBar: true` (`:644`) is already in place, so the menu bar
   needed no code change. See the note below on "just".

7. **The deny list.** See the Notes for Jason. `.claude/settings.json` was
   not edited.

8. **Scope.** The diff touches these files, and nothing else:
   - `app/main.js`
   - `tracker/api.py` (the constant and one docstring)
   - `tests/test_shell.py`
   - `tests/test_single_source.py`
   - `pilot/SPEC-shell.md`
   - `pilot/wording-shell.tsv`
   - `docs/runbook.md`
   - `docs/repo-map.curated.json`, and the generated `docs/repo-map.json` and
     `docs/repo-map.md`
   - `pilot/handoffs/shell-S2-rebuild-3.md`

   No renderer file changed, and nothing else changed.

## Findings

**1. No test covers the rule that the fallback log is never written through
a link, and the test named for links tests only a folder.**

- **The code.** `appendToLog` returns early when the path is a symbolic
  link (`app/main.js:146`, `info.isSymbolicLink() ||`).
- **The mutation that survives.** Changing that line to
  `if (info && !info.isSymbolicLink() && !info.isFile()) return;` makes the
  fallback write follow a link. It fails no test in `test_shell` or
  `test_single_source`.
- **The misnamed test.**
  `tests/test_shell.py::test_open_error_log_refuses_a_fallback_that_is_a_link_or_a_folder`
  makes only a folder. It also covers opening, not writing.
- **Why it matters.** A link planted at `userData\error.log` could redirect
  a client-naming stderr into another file. The code prevents this today,
  but nothing keeps it that way.
- **Fix.**
  - Add a link case, skipped where links cannot be made, to that
    `test_shell` test.
  - Add a link case to
    `test_the_fallback_log_is_capped_and_a_write_that_fails_never_throws`.
    It should assert that the link's target is unchanged and that the reply
    still ends with `SHELL_NO_LOG`.

**2. Dead return value and a stale comment (the dead-code gate).**

- **The dead return value.** `keepInLog` still returns a boolean, and its
  comment says "Whether there is a log to keep it in" (`app/main.js:161-171`).
  None of its three callers reads it: `:261`, `:366` and `:413`. The last
  one was the `:116` ternary, which this change replaced.
- **The stale comment.** The comment in the `test_single_source` shell
  harness (`tests/test_single_source.py:2510`) still says "The shell appends a failed child's stderr without
  waiting on it". The append is now synchronous.
- **Fix.** Drop the return value and its sentence, and reword the harness
  comment.

## Notes for Jason

1. **The agent deny list does not cover the fallback log.** This is the
   builder's note, and this review confirms it.
   - **The gap.** `.claude/settings.json` denies Claude's own file tools the
     data home and every client-naming file by name. `error.log` in
     `%APPDATA%\Tax Document Tracker Pilot\` is on neither list, and its
     stderr can name a client. An agent's Read tool could open it.
   - **Why the builder did not add it.** The list is pinned rule for rule by
     `test_the_agent_deny_list_names_the_data_home_and_every_file_that_names_a_client`.
     Adding it means a change to the settings and to the test together,
     which is yours to approve.
   - This review did not edit any settings or config file.
2. **"Just" means the added line, not the whole notice.** The notice reads:

   ```
   No reply from the tracker

   Tracker failed
   ```

   The failure's own sentence comes first, then a blank line, then the two
   words. SPEC 11.2 says the notice "says just 'Tracker failed'". The
   handoff describes it correctly.
   - **An empty stderr adds nothing.** A failure that wrote nothing to
     stderr has nothing to save, so it gets no added line, as before.
   - **If you meant only the two words on screen,** the reply should replace
     the sentence rather than append to it. That would be a one-line change
     in `withNoLog` and in the pinned test.
3. **Roaming profiles.** On a roaming domain profile `%APPDATA%` roams, and
   the fallback log would travel with it. The builder names this too. It is
   local on the office's setup today.
4. **Wrong model in the trailer, again.** The rebuild commit's trailer reads
   `Claude Sonnet 5.5`, as rebuild 2's did. `CLAUDE.md` says Opus 5.5
   builds. The shared history is left as it is.
5. **A rare case where the log stops.** If a folder named `error.log.1`
   ever exists in userData, rotation cannot remove it, and every later
   fallback write is dropped quietly. It is caught, so nothing breaks. It
   is not worth code today.

## Gate run by the review

Each file ran as its own process, under Python 3.11 (`/tmp/v`) and 3.13
(`/tmp/v313`). The results were the same under both.

| Test file | Result |
|---|---|
| `test_shell` | 22 passed |
| `test_single_source` | 170 passed |
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
- `python tools/repo_map.py check` reported the map current at `690905f`.
- After this file was added, `update`, then `check`, then `test_repo_map`
  were run again. The commit's message records the result.
