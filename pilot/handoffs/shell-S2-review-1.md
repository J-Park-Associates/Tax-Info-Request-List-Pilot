# Shell S2 review 1 (opus, high effort)

Branch `claude/shell-s2-menus`, reviewed at `adf4902` against S1's clean tip
`ff0fef0` (`git diff ff0fef0...HEAD`). The reviewer did not build S2. This
file is the review's only change, plus the map refresh it needs.

## Verdict

Three findings. None is in the menu's behaviour or its security: the code
meets S2's row of SPEC-shell 16. The findings are one test that does not pin
its claim and two documents that still describe the no-error-log behaviour
S2 removed.

## What was checked, and holds

- **Words.** A script compared `DEFAULT_MENU_WORDS` in `app/main.js` with
  `tracker.api.MENU`: all 44 keys are equal, in the same order, and both equal
  the table of SPEC 11.3. The shell words `killed`, `killedAt`, `noReply`,
  `couldNotStart`, `couldNotSend`, `noLog` and `notOpened` are
  `api.SHELL_*` word for word. The six `test_single_source` tests S1 left
  failing now pass.
- **Template (5.1).** File, Edit (`editMenu` role), Client, View, Tools and Help
  are in the table's order, with its separators. The accelerators are Ctrl+N,
  Ctrl+E, Ctrl+1 to 4, Ctrl+F, F5 and F9 and nothing else. Exit is the `quit`
  role with no accelerator of its own. There is no Reload, Force reload, Zoom,
  full screen or Developer tools item or role. `devTools: !app.isPackaged` is
  unchanged, and both builds set the menu before the window is made. Items with
  an "always" rule are enabled from the first frame. The page's `{enable}`
  enables the rest and never adds, removes or renames an item.
- **Right-click menus (5.2).** The six popups hold exactly the items and
  separators of the table. Each item is enabled only when that popup's own
  list names it.
- **Channel (5.4).** `preload.js` adds only `menu.onCommand` and `menu.send`,
  and does not pass the IPC event across. `main.js` adds one `ipcMain.on("menu")`
  and no other IPC. It drops messages from other senders, messages that are
  not plain objects, and ids that are unknown or not strings. It ignores any
  popup that is not one of the six. `x` and `y` are used only when both are
  inside the content bounds. A click sends `{id, token}` to the one window.
  Exit and `error_log` are not sent.
- **Token.** On a non-string or over-64-character token, the builder drops
  the whole popup. This is a sound reading of the SPEC. 5.4 says the token
  "must be" such a string and gives no fallback. 14.1 lists "a long token"
  among the things `test_the_menu_channel_drops_what_it_does_not_know` drops.
  Opening the popup with no token would leave the page unable to tell which
  row was meant. An absent token is taken as `""`, which does no harm.
- **Open error log and Exit (5.5).** Open error log goes through the existing
  `openPath` and its `lstat` check. A missing file, a folder or a symbolic link
  sends `{id: "error_log", missing: true}`. To make this work, the API-named
  log is put in `openable` as a `file`, so the page could also open that one
  file through `tracker.open`. The page already knows the path from
  `vocab.shell.error_log`, and a person opening their own log is what Help
  does anyway. This is not an arbitrary path, so it is not a finding.
- **First paint (5.6).** `--window-light` and `--window-dark` are read by name
  from `pilot-ui.css`. Under a contrast theme the colour is `undefined`.
  `nativeTheme.on("updated")` sets the colour again, and `themeSource` is
  `"system"`. The read is defensive: if the file or its names are missing, it
  falls back to `style.css`'s `--bg`, then to nothing. The handoff sends that
  fallback to S6 to remove once S3's tokens are joined.
- **Stderr with no error log.** Dropping it entirely matches SPEC 11.2 ("there
  is nowhere to keep its details, and they are no longer printed on screen; the
  notice says 'Tracker failed; no error log'"). It also matches `api.py`'s own
  comments at `SHELL_NO_LOG` and `_error_log_said`.
- **Security and standing rules.** `contextIsolation`, `sandbox`,
  `nodeIntegration: false`, `webSecurity`, the window-open and navigation
  guards, and the CSP are all untouched. S2 changed no renderer file
  (`git diff --stat ff0fef0...HEAD` names only `app/main.js`, `app/preload.js`,
  the map, the handoff and two test files). The menu adds no network call,
  reads no client document and sends nothing. No command reaches the tracker
  through `menu`.
- **Tests.** The 14.1 and 14.2 tests are present and named as claims. The
  behavioural ones run the real `main.js` under node against a recording
  Electron stand-in. Two names differ from 14.1: the menu half of
  `test_every_menu_id_is_answered_by_the_page_and_every_answer_is_in_the_menu`
  is here as `test_every_menu_id_is_in_the_apis_words_and_every_word_is_placed`,
  and `test_the_window_colours_main_reads_are_the_pages` checks the CSS only
  when the tokens exist. Both are handed to S6 in the handoff, which is
  acceptable for a branch without `shell.js` or S3's `pilot-ui.css`.
- **Mutation checks** (scratch edits to `app/main.js`, restored afterwards,
  running `test_shell` and the shell tests of `test_single_source`):
  - These eight mutants were each caught by a failing test:
    - no sender check
    - a 1000-character token accepted
    - `x` and `y` outside the window used
    - the dark colour always
    - `error_log` sent to the page instead of opened
    - the `lstat` link check removed
    - stderr appended to the reply
    - the menu rebuilt on every `list`
  - One mutant survived: accepting unknown ids in `enable` (F1).

## Findings

**F1 - the test of "ids not in the template are dropped" passes without the
drop.** `app/main.js:537-538`; test in `tests/test_shell.py:316-334`.

- **What the SPEC says.** 5.4: "`enable` must be an array of strings; ids not
  in the template are dropped". 14.1:
  `test_the_menu_channel_drops_what_it_does_not_know` covers unknown ids.
- **What the code does.** The code is right: `known()` filters by
  `allowed.has(id)`.
- **What the test misses.** Change the filter to
  `typeof id === "string"`, so every string id is kept, and every test still
  passes. An unknown id kept in `menuEnabled` changes no item. The only
  visible effect is on the "same list, no rebuild" comparison, and the test
  never reaches it: its only later bar message is not an array.
- **Smallest fix.** In that test, or in
  `test_the_page_enables_the_items_whose_rule_holds_and_the_menu_follows`,
  send `{"enable": ["overview", "no_such_id", "check"]}` and then
  `{"enable": ["overview"]}`, and assert that the second does not rebuild the
  menu: `len(ran["menus"]) == 2`. This mutant then fails.

**F2 - the map still describes the removed no-log behaviour and the old
channel count.** `docs/repo-map.curated.json:191` (`app/main.js` notes) and
`:423` (`artifact:tracker-errors.log` role).

- **What the rule says.** CLAUDE.md: "changed behaviour → edit
  `docs/repo-map.curated.json`"; "a stale map is worse than no map". The
  handoff says these notes were rewritten.
- **What the map says.**
  - The `main.js` notes still say "with none, a failed command's stderr (its
    last STDERR_ON_SCREEN_CAP) is said in its reply after vocab.shell.no_log".
    That constant is deleted and the behaviour is reversed.
  - They call `LAUNCH_DONE_CHANNEL` "the one main-to-renderer channel", but
    `menu` is now a second.
  - They say open-path opens "only a path the API reported in state.paths",
    but the API-named error log is now openable too.
  - The error-log artifact's role ends "a failed command's stderr is said in
    its reply instead".
- **Smallest fix.**
  - Replace the MF2 clause with: "with none, a failed command's reply adds
    vocab.shell.no_log (api.SHELL_NO_LOG) and its stderr is neither kept nor
    shown (SPEC-shell 11.2)".
  - Say "one of two main-to-renderer channels, with MENU_CHANNEL".
  - Add "and the error log vocab.shell.error_log names, as a file" to the
    open-path sentence.
  - In the artifact role, replace the last clause with "a failed command's
    reply says there is no error log and its stderr is dropped
    (api.SHELL_NO_LOG; SPEC-shell 11.2)", and add that Help › Open error log
    opens it.
  - Then run `python tools/repo_map.py update`.

**F3 - the runbook still tells the operator the details are shown on
screen.** `docs/runbook.md:569-571`.

- **What the rule says.** CLAUDE.md: "Change how any of that behaves and the
  runbook is part of the change."
- **What the runbook says.** "The app never writes an error log beside
  itself: with no data folder, what a failed command said is shown in its
  message instead." S2 made that false. The message now says only "Tracker
  failed; no error log", and the details are dropped.
- **Smallest fix.** Replace the sentence after the colon with: "with no data
  folder, a failed command's message says there is no error log, and its
  details are not kept or shown."

## Notes, not findings

- `autoHideMenuBar: true` is kept, so the bar shows on Alt. The SPEC does not
  say whether the bar must always show. The builder has put the choice to
  Jason, and it is his.
- `pilot/shell-test-pins.md` still names the old test names. It is a survey,
  and the handoff leaves it to S6.

## Gate run by the review

Each file ran as its own process, in parallel, under Python 3.11 (`/tmp/v`)
and 3.13 (a fresh venv). Results were the same under both:

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

`python -m ruff check .` passed. `python tools/repo_map.py check` was current
before this file was added. `update` and `check` were run after adding it.
