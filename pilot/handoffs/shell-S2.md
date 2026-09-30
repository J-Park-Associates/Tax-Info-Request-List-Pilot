# Shell S2 handoff: the window and its menus (sonnet)

Branch `claude/shell-s2-menus`, started from `claude/sharp-goldberg-jmfynk`
(S1, whose latest review says "No findings"). Last commit: the one that adds
this file; its sha is in the final message of the session. Built exactly S2's
row of SPEC-shell 16. No renderer file was touched.

## Done, in plain English

- **The menu bar** (`app/main.js`): `buildMenu()` builds File, Edit, Client,
  View, Tools and Help from the table of 5.1, with the accelerators of 5.1
  (Ctrl+N, Ctrl+E, Ctrl+1 to 4, Ctrl+F, F5, F9) and no others. Edit is the
  `editMenu` role, Exit is the `quit` role. There is no Reload, Zoom, Toggle
  full screen or Developer tools item or accelerator, in either build; the
  old "no menu when packaged" line is gone and both builds set the same menu
  before the window is made. `devTools: !app.isPackaged` stays.
- **The words**: `DEFAULT_MENU_WORDS` is word for word `api.MENU` (44 keys); a
  `list` reply's `vocab.menu` replaces a word only for a key the menu has, and
  the menu is rebuilt only when a word differs.
- **Enable rules**: the page sends `{enable: [ids]}`; the bar enables those
  ids. Eight items need nothing of the page and are enabled from the first
  frame (`ALWAYS`: change clients folder, refresh, tour, safeguards, terms,
  open error log, about, and exit which Electron enables itself). The menu is
  rebuilt only when the list changes. Nothing the page says adds, removes or
  renames an item.
- **Right-click menus** (5.2): the six native popups (`household`, `return`,
  `file`, `moved`, `request`, `received`) from `POPUPS`; each item is enabled
  only if the popup's own `enable` list names it.
- **The `menu` channel** (5.4): `preload.js` exposes `menu.onCommand` and
  `menu.send` (nothing else new). `main.js` listens with `ipcMain.on`, ignores
  a message that is not from its own window or not a plain object, drops
  unknown ids (and non-strings) from `enable`, ignores a popup that is not one
  of the six, ignores a popup whose token is not a string of at most 64
  characters (an absent token is `""`), and uses `x`/`y` only when both are
  numbers inside the window (else the pointer). A click sends `{id, token}`
  on `menu` to the window (`token` is `""` for the bar).
- **Open error log** (5.5): opened through the existing `openPath` (so its
  `lstat` test and the single `shell.openPath(` call stay); the API-named log
  is added to `openable` as a file when learned. No log named, missing, a
  folder or a link: the page is sent `{id: "error_log", missing: true}`.
- **First paint** (5.6): `pageBackground()` reads `--window-light` /
  `--window-dark` from `pilot-ui.css` for `nativeTheme.shouldUseDarkColors`,
  `undefined` under a contrast theme; `nativeTheme.on("updated")` sets the
  window colour again; `themeSource` is `"system"`. Read defensively: a
  missing file or missing names fall back to `style.css`'s `--bg` (today's
  value, so the existing pin holds until S6), then to nothing; never a thrown
  error.
- **Shell words** set to the API's (`killed`, `noReply`, `couldNotStart`,
  `couldNotSend`, `noLog`, `notOpened`). `noLog` has no `{stderr}` any more,
  so with no error log the reply says "Tracker failed; no error log" and the
  stderr is neither kept nor shown (`withStderr` became `withNoLog`;
  `STDERR_ON_SCREEN_CAP` deleted). The stale "stderr is said in the reply"
  comments in `main.js` and the docstring/name of the `test_single_source`
  test are fixed; that test is now
  `test_with_no_error_log_the_shell_says_so_and_shows_no_stderr_and_writes_no_file`.
  The six tests S1 named pass unchanged in their claims.

## Tests

`tests/test_single_source.py` changed (14.2): the two IPC-channel tests now
include `menu` both ways (`MENU_CHANNEL` in main, `ipcMain.on`, and
`ipcRenderer.on` / `.send` in the preload); the "no menu" test became "the
app's menu is the template in both builds" (private-python half unchanged);
`_ELECTRON_STUB` and `_SHELL_HARNESS` gained `Menu.buildFromTemplate`,
`setApplicationMenu`, `nativeTheme`, `ipcMain.on`.

`tests/test_shell.py` is new (20 tests, the menu part of 14.1): defaults equal
`api.MENU`; no Reload/Zoom/DevTools; every accelerator named once; every menu
id is a `MENU` key and every key is placed; one preload channel; the window
colour names; and, run in node against the real `main.js`: the template in
both builds, accelerators, enabled rules, `test_the_menu_channel_drops_what_it_does_not_know`,
the popups' items and token echo, the six popup contents, bar clicks, Open
error log (opens / none / missing / folder / symbolic link), the API's words
replacing defaults only when they differ, first paint (fixture stylesheet,
dark, contrast, missing file) and the repaint on a theme switch.

Gate: `test_shell`, `test_single_source`, `test_layers`, `test_repo_map`,
`test_api` (380), `test_errors`, `test_tripwire`, `test_pilot` each in its own
process, in parallel, under Python 3.11 and 3.13: all pass. `python -m ruff
check .` clean; `tools/repo_map.py update` then `check` current. (`test_build`
not run: it fails on the base, as told.) Curated notes for `app/main.js` and
`app/preload.js` rewritten.

## Left for others

- **Two things S3/S6 must join.** (1) `tests/test_shell.py` exists on S3's
  branch too (renderer part): S6 merges the two files by keeping both sets of
  tests and the one module docstring. (2) `pilot-ui.css` gets
  `--window-light` and `--window-dark` on S3's branch; the static colour test
  here checks them and `--bg-page` only if they are present, so S6 should make
  that check unconditional and may then drop the `style.css` `--bg` fallback
  in `pageBackground()` (and `test_the_window_colour_is_read_from_the_stylesheet`
  with it, replaced by 14.1's `test_the_window_colours_main_reads_are_the_pages`).
- **The page's half** of `test_every_menu_id_is_answered_by_the_page_and_every_answer_is_in_the_menu`
  is not written (there is no `shell.js` here); S6 adds it. This branch's test
  covers the menu's half.
- `shell.js` (S3) sends `{enable}` and popups and answers `{id, token}` and
  `{id: "error_log", missing: true}`; the toast "No error log yet" is the page's.
- The menu accelerators and the page's single keydown listener (4.3) overlap
  for Ctrl+1 to 4, Ctrl+F, Ctrl+N, Ctrl+E, F5, F9: Electron delivers the key
  to the menu first, and it then reaches the page as `{id}`; the page must not
  also act on the raw key or it will act twice. S6 to check on Windows.
- `autoHideMenuBar: true` is kept (Alt shows the bar, as the keyboard map of
  4.3 says); if Jason wants the bar always visible, it is one line.
- `pilot/shell-test-pins.md` rows that name the renamed tests were not edited
  (the file is the survey; S6 may refresh it).

## Files the next session needs

`app/main.js` (`DEFAULT_MENU_WORDS`, `BAR`, `POPUPS`, `onMenuMessage`,
`openErrorLog`, `pageBackground`), `app/preload.js`, `tests/test_shell.py`
(`_HARNESS` is reusable for any test that needs the menu or the window
recorded), this file.

## Proposed decision rows for S6

- The menu is the app's own in both builds; no Reload, Zoom, Toggle full
  screen or Developer tools, no accelerator for them (P58); F5 is Refresh.
- The menu channel is one-way each way, untrusted on arrival: unknown ids,
  popups and tokens over 64 characters are dropped, never an error; the
  token is the page's row key and is echoed, never used by the shell.
- Open error log is the shell's alone, through `openPath`'s `lstat` test; a
  missing log is told to the page, which says "No error log yet".
- With no error log, a failed command's reply says "Tracker failed; no error
  log" and its stderr is dropped rather than shown (supersedes decision 186's
  MF2 "said in the reply", as SPEC 11.2 requires).
- `pageBackground()` reads `pilot-ui.css` for the system theme's window colour
  and leaves a contrast theme to paint its own (P59, P73).

## Needing Jason

Nothing blocking. Two small calls he may want: whether the menu bar stays
hidden until Alt (as now) or is always shown, and confirming that dropping the
stderr entirely when there is no error log (rather than showing it) is the
intent of the new `noLog` word.
