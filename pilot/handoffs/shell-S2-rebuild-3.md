# Shell S2 rebuild 3

Branch `claude/shell-s2-menus` (local branch `rebuild-s2-3`), built on the S2 rebuild 2 head.
Last commit: see `git log -1` on the branch (the commit that adds this file).

## Jason's ruling (2026-09-29)

When a tracker command fails and the API has named no error log (no data folder
yet): (a) the failure is still SAVED to a log, and (b) the screen says just
"Tracker failed". The menu bar stays hidden until Alt (no change, recorded here).

## What changed

- **The word.** `api.SHELL_NO_LOG` and `app/main.js`'s default `noLog` are exactly
  `Tracker failed` (was `Tracker failed; no error log`). The reply keeps its shape:
  the failure sentence, a blank line, then the two words. Only a failure that wrote
  something to stderr gets the line, as before.
- **The fallback log.** `keepInLog()` appends a failed command's details (heading with
  the time, then stderr, capped at 64 KB per entry as before) to the API-named log when
  there is one, otherwise to `error.log` in `app.getPath('userData')`. Never on screen.
  A renderer error (`log-error`) and a shell serialisation error go the same way.
  Writes are fail-safe (`appendToLog`): any error is dropped, nothing throws. A path
  that is a link or not a plain file is left alone. The fallback is capped: past
  256 KB it becomes `error.log.1` (one copy, replacing an older one), so it never holds
  more than about 512 KB. The API's own log is not capped by the shell (Python rotates it).
- **Help > Open error log** opens the API-named log when named; otherwise the fallback if
  it exists; both through the same lstat check (`openChecked`, split out of `openPath`;
  `openPath` still refuses any path the API did not report first). If neither exists the
  page gets `{id: "error_log", missing: true}`.
- Docs: SPEC-shell 5.5 (fallback, menu bar hidden until Alt) and 11.2, `pilot/wording-shell.tsv`
  row `shell.no_log`, runbook (the sentence at the error-log entry), curated map notes for
  `app/main.js`, `app/preload.js` and the error-log artifact.

## Where the fallback lives, and why

`userData` is `%APPDATA%\Tax Document Tracker Pilot\error.log` on Windows (Electron names
it from `productName`). Checked against the P19 rules: the deny list and the package check
name `DATA_HOME_NAME` (`tax-document-tracker-pilot`, under `%LOCALAPPDATA%` /
`~/.local/state`), `UPSTREAM_DATA_HOME_NAME` (`tax-document-tracker`), and the file names
`tracker-errors.log` (+ `.1`-`.3`) etc. `userData` is a different folder with a different
name, and the shell does not create the data home, so it does not collide, and the package
holds no `error.log` (the log is written at run time, not shipped). It is not the data
home because "no data folder yet" is exactly the case, and creating that folder from the
shell would pre-empt the API's own rules for it. `test_single_source` still forbids the
API's log file name inside `main.js`, so the fallback is deliberately named `error.log`.

Two things to know, for Jason:
1. The agent deny list (`.claude/settings.json`) does not cover `userData\error.log`
   (it is pinned rule for rule to the constants, and the tests pin it). An agent could
   read it. If wanted, add a rule for it in a separate change with the test.
2. On a domain PC with a roaming profile `%APPDATA%` can roam. On the office's setup this is
   local; if that ever changes, the alternative is `app.getPath('sessionData')`/`temp`
   or a `LOCALAPPDATA` folder that is not the data home.

## Privacy

The raw stderr can contain client names. It stays on this PC in that log only: never on
screen, never in the reply, never sent (no network call, nothing read from a client
document).

## Tests

- `tests/test_single_source.py`: the harness stub gains `app.getPath` (env `FAKE_USERDATA`).
  New or changed: no named log -> failure saved in the fallback and the reply ends with
  exactly `Tracker failed`, nothing of stderr in it; named log -> goes there, no fallback
  created, no suffix; the cap (400 KB file rotates to `.1`); a log path that is a folder and a
  per-user folder that cannot be made -> the reply is unchanged, nothing throws; the
  `noLog` default equals the API's; the lstat pin now reads `openChecked`.
- `tests/test_shell.py`: Open error log falls back (missing -> page told; saved -> opens;
  named wins; a folder in the fallback's place is refused).
- Mutations, each caught: making `keepInLog` ignore the fallback (2 tests fail); making Open
  error log ignore the fallback (1 test fails). Restored after.

## Proposed decision rows for S6 (both Jason's rulings, 2026-09-29)

- **No error log => fallback log, message "Tracker failed".** With no data folder the API
  names no error log; the shell saves the failure to `error.log` in Electron's `userData`
  folder (256 KB cap, one copy) and the screen says just "Tracker failed". Supersedes the
  MF2 wording "no error log / details dropped". Nothing is shown or sent.
- **Menu bar hidden until Alt.** The window keeps `autoHideMenuBar`; no change.
