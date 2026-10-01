# F7 build (SPEC-F7, decision P193) - builder's hand-back

Built 2026-09-30 by the builder agent from `pilot/SPEC-F7-redirected-data-folder.md`
(at 392ec27; Jason's answers Q1 (a), Q2 (a) not reopened). For a separate reviewer.

## What was built, per ruling

**R1 - the engine refuses a data folder Windows is redirecting** (`tracker/settings.py`)
- Constants beside the data-home sentences: `REDIRECT_PROBE_PREFIX` (155),
  `PACKAGES_DIR_NAME`, `REDIRECTED_LOCAL`, `DATA_HOME_REDIRECTED` (164),
  `REDIRECTED_COPY` (169), with the reasoning in their comments.
- `data_home()` (691) now calls `_the_data_home()` (717): `resolve_data_home()`
  unchanged, then - on Windows, only with `ENV_DATA_HOME` unset or blank - the
  once-a-process answer `_redirected_package()` (747, held in `_redirect_answer`,
  744). A hit raises `SettingsError(DATA_HOME_REDIRECTED)`. `resolve_data_home()`
  and `default_data_home()` are untouched, so the tripwire still learns the real place.
- `redirect_probe(local, *, make=...)` (760): writes
  `.tracker-redirect-probe-<pid>-<16 hex>` in `%LOCALAPPDATA%`, looks for it in
  every `Packages\*\LocalCache\Local\`, removes it from wherever it landed in a
  `finally`. `make` is injected (as `drive_type` is). A write that fails answers
  None (nothing new raised). `_package_names()` (797) lists package folders.
- **Builder's choice the SPEC did not spell out:** the sentence says
  `{product}` and is formatted with `product_name()`, not the literal
  "Tax Document Console" - `test_single_source::test_the_product_name_has_one_home`
  forbids typing the product name in `tracker/`. The words shown are the SPEC's.
- `REDIRECT_PROBE_PREFIX` contains "tracker"; it is a file name, not a sentence,
  so it is added to `_NAMES_NOT_SENTENCES` in `tests/test_single_source.py`.

**R2 - a stale copy is named, never removed**
- `settings.redirected_copies(environ=None, *, windows=None)` (805): every existing
  `%LOCALAPPDATA%\Packages\*\LocalCache\Local\tax-document-tracker-pilot`; Windows
  only, read-only, nothing with no Packages folder.
- **Builder's choice for the reviewer to rule on:** it also answers nothing when
  `ENV_DATA_HOME` names the data home. Reason: the app then never uses
  `%LOCALAPPDATA%`, so that copy is no copy of its data folder; and without it
  every first-screen test on this PC read the real machine and found the real
  Claude copy (the suite always sets `ENV_DATA_HOME`).
- `tracker/api.py` `_machine_warnings` (3566): one `REDIRECTED_COPY` sentence per
  copy, last; docstring says why. Not added to `runner.left_behind()`.

**R3 - the sample script never writes the real data folder**
(`pilot/wintest/make_samples.py`, docstring 11, build 54): builds under a
`tempfile.TemporaryDirectory` set as `TRACKER_DATA_HOME` (and drops
`TRACKER_STORE`), closes the store and the logging handlers so Windows can
remove the folder, then removes it.

**R4 - the Windows check starts the app outside Claude**
- `pilot/wintest/run_checks.ps1` new step 8 (230): `& explorer.exe "<shortcut>"`,
  recorded as `launch` INFO (or NOT VERIFIED with no shortcut), with the why in a
  comment; never `Start-Process`. The script did not start the app before; it now
  does at its end - the reviewer should weigh that against PROMPT-0.3's "step 19
  is its first start" for the next check.
- `pilot/wintest/PROMPT-0.3.md` (92): the SPEC's prompt line, as a note for the next check.

**R5 - docs:** `docs/runbook.md` (49), the SPEC's sentence in the data-folder
paragraph. README: its data-folder line (84) does not name where the folder is,
so no change. `docs/repo-map.curated.json` settings node says R1 and R2;
`repo_map.py update` run.

**R6** is Jason's; no code.

## Tests added (named as their claims)
`tests/test_settings.py` 519-618: `test_a_redirected_data_folder_is_refused_by_name`,
`test_an_unredirected_data_folder_is_answered_as_before`,
`test_a_named_data_folder_is_never_probed`, `test_the_probe_runs_once_a_process`,
`test_the_redirect_probe_leaves_nothing_behind`,
`test_a_stale_redirected_copy_is_found_and_never_touched`,
`test_no_packages_folder_names_no_copy`. `tests/test_api.py` 7658:
`test_a_stale_redirected_copy_is_named_on_the_first_screen`.

## Dead code
Checked the changed files first: no unused imports, locals, commented-out code or
unused module-level names (`ruff check .`: All checks passed!). One leftover
comprehension in a test helper was simplified.

## Gate
The SPEC's seven files, each its own process, all at once, on Windows, under
Python 3.14.3 (`.venv`, the office's) and 3.11.15 (`.venv311`, the floor), exit 0 every one:

| File | 3.14.3 | 3.11.15 |
|---|---|---|
| tests/test_settings.py | 65 passed in 11.00s | 65 passed in 10.25s |
| tests/test_api.py | 439 passed in 708.68s | 439 passed in 971.48s |
| tests/test_layers.py | 29 passed in 37.13s | 29 passed in 30.65s |
| tests/test_single_source.py | 179 passed in 64.07s | 179 passed in 62.13s |
| tests/test_repo_map.py | 80 passed in 65.45s | 80 passed in 62.94s |
| tests/test_errors.py | 83 passed in 24.39s | 83 passed in 22.88s |
| tests/test_tripwire.py | 19 passed in 46.31s | 19 passed in 57.72s |

`python -m ruff check .`: All checks passed! `python tools/repo_map.py check`: "Map is current (402 nodes, generated 2026-09-30)", exit 0.
`test_errors` needed no new rows (both sentences are `SettingsError`s the
existing paths already say).

## Windows proof (this PC, from the agent's shell inside the Claude desktop app)
`TRACKER_DATA_HOME` and `TRACKER_STORE` unset, `.venv\Scripts\python.exe -m tracker.api list`:
- exit 0; `needs_root` true; `machine_warnings`:
  1. "Windows is giving this copy of the app a private data folder of its own, because it was started from inside another program (Claude_pzs8sxrjxfjjc). Close it and start Tax Document Console from the Start menu."
  2. "Windows kept a private copy of the app's data folder at C:\Users\User\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\tax-document-tracker-pilot, from a time the app was started inside another program. The app never uses it and it is out of date; move that folder to the Recycle Bin."
- `.tracker-redirect-probe-*` files before / after: `%LOCALAPPDATA%` 0 / 0;
  `Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local` 0 / 0 (names only listed;
  nothing inside the private copy was opened, moved or deleted).

**R3 proof:** `make_samples.py` refuses any target outside `%USERPROFILE%\PilotTest`,
so it was not run as shipped. Instead a scratch driver loaded it, moved its
`SANDBOX_PARENT` into a temporary folder, set a guard `TRACKER_DATA_HOME`, and ran
`main()`: exit 0, 14 fake documents; the data home during the build was a
`pilot-samples-*` throwaway holding `tracker.db`, `record-heads.db` and the WAL
files; the throwaway was gone afterwards; the guard data home was never made.
PilotTest was not touched.

## Not done / notes
- Nothing pushed; no pull request.
- `.venv` (3.14.3) and `.venv311` (3.11.15) were made in this worktree for the gate (both ignored by git).
- The machine-wide slot was taken as `%TEMP%\tracker-test-slot-<n>` (no slot convention existed on this PC) and released.
