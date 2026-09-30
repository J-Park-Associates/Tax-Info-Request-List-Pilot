# Shell S2 review 2 (opus, high effort)

Branch `claude/shell-s2-menus`, reviewed at `7ffca7b`. The rebuild's diff is
`git diff 258d27a...HEAD`, and the whole session's is `git diff ff0fef0...HEAD`.
The reviewer did not build S2 or its rebuild. This review changes this file,
the one map note of F2 that survived (fixed here, see finding 1), and the map
refresh.

## Verdict

Two findings:

1. Part of review 1's F2 survived. The reviewer fixed it in this commit.
2. A new finding: the map's `app/preload.js` role lists fewer calls than the
   preload has. It is left to the builder.

F1 and F3 are fixed. The code is unchanged since review 1 and still meets
SPEC-shell 5.

## What was checked, and holds

- **F1 - the unknown-id test now pins the drop.** The reviewer made a scratch
  edit to `known()` in `app/main.js`, so that it keeps every string id:
  `list.filter((id) => typeof id === "string")`. With that edit,
  `test_the_menu_channel_drops_what_it_does_not_know` FAILED at
  `tests/test_shell.py:333` (`len(ran["menus"]) == 2`), with 1 failed and 19
  passed. `git checkout app/main.js` restored the file, and its sha256 was the
  same before and after (`bbc8ecb7...`). With the real code, all 20 tests pass.
  The strays in the first message include `"check"`, which is a popup id and
  not a bar id. So the test also catches a mutant that checks ids against
  every id the popups use instead of `BAR_IDS`.
- **F2 - the map against the code.**
  - `STDERR_ON_SCREEN_CAP` is gone from the code and from the notes.
  - A failed command's reply adds `noLog` (`withNoLog`, `app/main.js:132`). The
    stderr is neither kept nor shown, and the notes now say so.
  - The open-path sentence now names the error log. `learn()` puts it in
    `openable` as a `file` (`app/main.js:168`), and the `open-path` handler
    opens only what is in `openable` (`:336`).
  - The artifact role now says that Help > Open error log opens the log. That
    is `openErrorLog`, `:473`.
  - **The builder's added wording, "a failed child's stderr the shell appends
    when there is a log", is true.** `keepInLog` returns `false` when the API
    has named no log and appends nothing (`:120-121`). The same role already
    says there is no log at all without a data folder, so the words repeat
    that point. They are harmless.
  - One clause is still false: the channel count (finding 1).
- **F3 - the runbook.** `docs/runbook.md:569-571` now reads "with no data
  folder, a failed command's message says there is no error log, and its
  details are not kept or shown." This matches `withNoLog` and SPEC-shell
  11.2, and it is plain and clear. It is a runbook sentence for a person, so
  the five-word rule of 11.1 does not apply to it. One small point, not a
  finding: a failure that wrote nothing to stderr gets no "no error log" line
  (`:321-322`), because it had no details to lose.
- **Other statements that stderr is shown.** The reviewer searched
  `README.md`, `CLAUDE.md`, `docs/runbook.md`, `docs/ROADMAP.md`,
  `docs/tools.md`, `PRODUCT.md`, `pilot/Tester Guide.md`, `pilot/*.md` and
  the tests for a failed command's stderr or details shown on screen or in a
  reply. Three places still say it, and none is a finding:
  - **`docs/ROADMAP.md`, decision 186's row.** It says "a failed command's
    stderr is said in its reply (`api.SHELL_NO_LOG`)". The row is history.
    `pilot/handoffs/shell-S2.md` ("Proposed decision rows for S6") proposes
    the row that supersedes it, and S6 lands it.
  - **`pilot/shell-test-pins.md:165`.** It still names the old test,
    `test_with_no_error_log_the_shell_says_stderr_in_the_reply_and_writes_no_file`.
    This file is a survey, and review 1 already left it to S6.
  - **`tracker/api.py:1620-1623`.** It says the error log is where the shell
    appends a failed child's stderr. That is true.
  - Nothing else survives.
- **The rebuild changed nothing beyond the findings.** It changed
  `tests/test_shell.py` (F1: one step and one comment), `docs/runbook.md`
  (F3), `docs/repo-map.curated.json` (F2), the generated
  `docs/repo-map.json` and `docs/repo-map.md`, and its own handoff. The one
  extra is the "when there is a log" wording, which is judged above. It did
  not touch `app/`.
- **No regression.**
  - `git diff ff0fef0...HEAD` touches `app/main.js` and `app/preload.js` and
    no renderer file.
  - The menu bar is the table of 5.1. The accelerators are CmdOrCtrl+N
    (`new_household`), CmdOrCtrl+E (`edit_list`), CmdOrCtrl+1 to 4 (the four
    views), CmdOrCtrl+F (`find`), F5 (`refresh`) and F9 (`sort_now`). Exit is
    the `quit` role, Edit is the `editMenu` role, and there is no reload,
    zoom or developer-tools item.
  - The six popups match 5.2. `ALWAYS` is 5.1's "always" rows.
  - The channel rules of 5.4 hold: the sender check, a plain object, string
    ids filtered to the template, popups limited to the six, a token of at
    most 64 characters, and `x` and `y` used only inside the content bounds.
    `exit` and `error_log` are not sent to the page.
  - Preload adds only `menu.onCommand` and `menu.send`. The rebuild left the
    security settings, `devTools: !app.isPackaged`, the guards and the CSP
    unchanged.

## Findings

**1. F2 survived in one clause: the map counts two main-to-renderer
channels, and there are three. Fixed here.**
`docs/repo-map.curated.json`, `app/main.js` notes (Decision 209 sentence).

- **The rebuild's wording.** Review 1 suggested it, and the rebuild used it:
  `'after-install-done', one of two main-to-renderer channels, with
  MENU_CHANNEL`.
- **What the code does.** Main sends to the renderer on three channels:
  - `tracker-progress` (`app/main.js:356`, `event.sender.send`, decision 203)
  - `menu` (`:467`)
  - `after-install-done` (`:643`)

  The preload listens on all three (`onProgress`, `menu.onCommand`,
  `onAfterInstallDone`). The same notes already say that a pass streams on
  tracker-progress. The old wording, "the one main-to-renderer channel", was
  already false before S2 for the same reason.
- **Fix, made in this commit.** The clause now reads `'after-install-done',
  one of three main-to-renderer channels, with tracker-progress and
  MENU_CHANNEL`. Then `python tools/repo_map.py update` was run. The tests
  this fix touches, `test_repo_map` and `test_single_source`, were run again
  and pass.

**2. The map's `app/preload.js` role says "Nothing else crosses", but it
leaves out two calls the preload exposes.**
`docs/repo-map.curated.json`, `app/preload.js` role.

- **What the role says.** It lists `call`, `tracker.open`, `pickFolder`,
  `onAfterInstallDone` and, since S2, `tracker.menu`. Then it says "Nothing
  else crosses."
- **What the preload has.** `app/preload.js:7-8` also exposes
  `logError(text)` (`log-error`) and `onProgress(cb)` (`tracker-progress`).
- **Why it matters.** The gap is older than S2. But S2 rewrote this sentence
  to add `tracker.menu`, and it left the closing claim false. The rule is
  "a stale map is worse than no map", and a reader who trusts "nothing else
  crosses" would miss two IPC doors.
- **Smallest fix.** Add ", tracker.logError(text) on 'log-error' (kept only
  in the error log the API named) and tracker.onProgress(listener), which
  hears 'tracker-progress'" before "and tracker.menu". Then run
  `python tools/repo_map.py update`.
- **Why the reviewer did not fix it.** It is a new finding, not a review-1
  finding that survived.

## Gate run by the review

Each file ran as its own process, under Python 3.11 (`/tmp/v`) and 3.13
(`/tmp/v313`). Results were the same under both, after this review's edit and
map update:

| Test file | Passed |
|---|---|
| `test_shell` | 20 |
| `test_single_source` | 168 |
| `test_layers` | 29 |
| `test_repo_map` | 80 |
| `test_api` | 380 |
| `test_errors` | 83 |
| `test_tripwire` | 19 |
| `test_pilot` | 15 |

`python -m ruff check .` passed, and `python tools/repo_map.py check` reports
the map current.
