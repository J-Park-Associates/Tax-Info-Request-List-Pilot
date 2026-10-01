# Combined review: P193 (F7), P194/P195 (firm columns), P196 (Taxpayer words)

Reviewer: a separate agent that built none of this and wrote no SPEC. Reviewed
2026-09-30: `git diff 392ec27..896d1d7` on `claude/zen-easley-93548b`, against
SPEC-F7-redirected-data-folder, SPEC-firm-columns, SPEC-taxpayer-words, the
three hand-backs, `pilot/reviews/combined-rulings.md` and Jason's rulings in
`pilot/DECISIONS.md` P193-P196. Nothing edited, committed or pushed.

**Verdict: 1 MUST, 5 SHOULD, 5 NIT.** The three builds merged without loss, and
F7 and the firm columns hold to their rulings. The MUST is one sentence still
on screen that says "client" (P196).

## The seams (check 1): nothing lost

- I merged the two branch tips again in a scratch tree
  (`git merge-tree --write-tree ae5219f 9e20f2c`). The result is the same as
  the committed merge `2ee1dce` in every file except `docs/repo-map.json` and
  `docs/repo-map.md`. Those are generated and were rebuilt, and
  `repo_map.py check` passes (see the results at the end).
  - `tracker/api.py`, `docs/runbook.md`, `tests/test_api.py`,
    `tests/test_single_source.py`, `pilot/DECISIONS.md` and `pilot/HANDOFF.md`
    each keep both sides by content. Examples: F7's `REDIRECTED_COPY` line in
    `_machine_warnings` (api.py:3579) sits beside P196's vocabulary changes;
    the runbook has F7's sentence (line 49) and P196's "Household menu" and
    "Households" lines.
- The fold `2ee1dce..896d1d7` touches only `run_checks.ps1` step 8,
  `PROMPT-0.3.md`'s note, the rulings file and the map, as ruling 3 says.
  - Step 8 now starts nothing. It records `launch` INFO with the
    `explorer.exe` command, or NOT VERIFIED.
  - Its only `Start-Process` calls are the pre-existing pytest runner (line 85)
    and the installer (line 206). See S3.
- F7's words do not say "client". The P196 rename touched none of F7's
  sentences, and F7's sentences say nothing P196 rules on.

## Findings

### MUST

**M1 - P196: the request-list editor still shows "this client" on screen.**
- Where:
  - The words are in `tracker/records.py:958`
    (`ENGAGEMENT_NOTES["reminders"] = "{NO} = this client is not chased by email"`).
  - `tracker/api.py:2002-2003` sends them as `editor.engagement_fields[].help`.
  - `app/renderer/app.js:3165-3171` draws the help of every editable yes/no
    field (Reminders as well as Active), as "Reminders — No = this client is
    not chased by email".
- Jason's ruling is "change client to Taxpayer across the entire app". This
  word is neither changed nor listed in SPEC-taxpayer-words section 3 with a
  reason.
- It was missed because `tests/test_api.py::test_no_word_the_window_draws_says_client_but_a_folders_own_name`
  (around test_api.py:9294) checks the editor's labels but not its help lines.
- Fix:
  1. In `tracker/api.py`, add `EDITOR_HELP: dict[str, str] = {"reminders": f"{NO} = this taxpayer is not chased by email"}`
     beside `EDITOR_LABELS` (api.py:1218). Use the same `NO` the record
     uses.
  2. Use it at api.py:2003:
     `"help": ACTIVE_HELP if f == "active" else EDITOR_HELP.get(f, ENGAGEMENT_HELP.get(f, ""))`.
     The record and `records.py` keep their words, as R7 and R9 require.
  3. Add `[f["help"] for f in vocab["editor"]["engagement_fields"] if f["editable"]]`
     to that test's `drawn` list.
  4. Add a row to `pilot/wording-shell.tsv`.
  5. Rerun `tests/test_api.py` only.

### SHOULD

**S1 - P196: other sentences that reach the screen still say "client", and the SPEC does not list them.**
- SPEC-taxpayer-words section 3 says only the error-log and command-line
  sentences keep "client". These ones reach the screen:
  - `tracker/settings.py:145` and `:147`: "client data never sits beside the
    program / on a removable or network drive". These are first-screen
    `machine_warnings`.
  - `tracker/runner.py:288` (`LEFT_BEHIND`): "They hold client ...", also on
    the first screen.
  - `tracker/settings.py:973-984`: the clients-root refusals, "choose the
    folder the firm keeps its clients in", shown in the setup and settings
    screens.
  - `tracker/api.py:3852` (`CLIENT_FOLDER_TAKEN`): "the clients' tree", a
    refusal shown in a dialog.
  - `tracker/api.py:648` (`RETURN_CREATED_LINE`): "client README generated".
    It is shown as a notice when a link was dropped (app.js:2937-2938).
- Most of these speak of the firm's clients and their data, which is R4's
  reason, or of a folder, which is R3's.
- Fix: list each in SPEC-taxpayer-words section 3 with its rule (R3 or R4).
  Then either ask Jason as Q6 (recommend keeping them) or reword them. No
  code change is needed if they are kept.

**S2 - F7: a folder the app cannot list raises the wrong kind of error.**
- `tracker/settings.py` `_package_names` (around line 797) catches only
  `FileNotFoundError` and `NotADirectoryError`.
- My probe (`scratchpad/probe_perm.py`) replaced `os.scandir` with one that
  raises `PermissionError`:
  - `redirected_copies()` and `redirect_probe()` both raise a raw
    `PermissionError`, not a `SettingsError`. The probe file is still
    removed.
  - So `data_home()` raises it, and `_machine_warnings`
    (api.py:3579, outside its `try`) fails the whole `list` reply. The person
    gets a failure instead of a first-screen sentence.
- Fix: in `_package_names`, catch `OSError as exc` and raise
  `SettingsError(PACKAGES_UNREADABLE.format(folder=packages, error=exc))`.
  That is a new sentence with no client name, and it fails loudly the way
  the first screen and the pass already report a data home they cannot use.
  Add a test in `tests/test_settings.py` with `os.scandir` patched.

**S3 - F7: the check script still starts the installer from the agent's shell.**
- `pilot/wintest/run_checks.ps1:206` runs `Start-Process` on the installer
  from the agent's shell.
- The installer is per-user and writes a new folder,
  `{localappdata}\Programs\Tax Document Console` (`pilot/installer/setup.iss:24,30`).
  SPEC-F7 evidence 2 says a new folder written under `%LOCALAPPDATA%` from
  that shell landed only in the Claude package's copy.
- SPEC R4 weighed only the app's start. On a fresh install, the program
  itself may land in the private copy. The Start-menu shortcut and the
  scheduled task, which run outside Claude, would then not find it.
- Fix:
  1. On the next Windows check, prove where the program landed. Have Jason
     list the program folder from File Explorer outside Claude, or check the
     shortcut's target from a normal window.
  2. If it landed in the private copy, make the install a hands-on step too
     (`explorer.exe` on the setup file, or a person's double-click). Record
     that in `PROMPT-0.3.md`'s F7 note and in `run_checks.ps1` step 7.

**S4 - `pilot/HANDOFF.md` does not record F7, and its P194-P196 lead is out of date.**
- Lines 3-9 still say the two branches are separate and "awaiting review".
  F7 (P193) appears nowhere in it.
- Fix: replace that paragraph with one line covering all three:
  - all three are combined on `claude/zen-easley-93548b` at `896d1d7`;
  - the combined review is `pilot/reviews/combined-review.md`;
  - P196's Q1-Q5 are open and built as recommended;
  - F7's R6 (the office PC) and Q1 (a) (Jason removes the private copy)
    are his.

**S5 - The 1100 px "proof" holds for the column layout but not for the text widths.**
- The column layout is sound by adding up the width settings:
  - The new minimum-width rule (shell.css:542-545) adds up the same settings
    the column layout uses (shell.css:538-541).
  - The year and form columns cut long text with "…" instead of growing.
  - The status and date columns keep their old widths.
  - So 80 + 224 + 96 + 160 + 144 + 4×16 + 2×32 = 832 px ≤ 843 px holds
    whatever the content.
- Text widths are not proven:
  - These were measured with GDI+, an older Windows text-drawing system,
    not in the app's Chromium window:
    - the header "Form Type" with its arrow (about 88 of 96 px);
    - "Tax Year" (about 76 of 80 px);
    - the search placeholder "Files, Households and Returns" (192 of 198 px).
  - Chromium's widths can differ by a few pixels, and the margins are 4-8 px.
- Fix: add one hands-on look at 1100 px to the next Windows check: Overview,
  Reminders, and the Needs Review search box. Or run
  `pilot/harness/shoot.mjs` where Playwright is present. Record the
  result in the hand-back.

### NIT

- **N1** - Comments that still say the old words. Fix the comments only:
  - `app/renderer/index.html:24-25` ("the Client Types / that open Clients
    filtered") and `:508` ("(Client menu)");
  - `app/renderer/pages.js:93` ("waits on the client"), `:117`
    ("Clients' Client Type"), and the Reminders comment "a later reminder is
    the more overdue client" in `pagesReminderSpecs`.
- **N2** - `pilot/wording-shell.tsv`: the rows `paging.nouns.clients` and
  `columns.client_name` still give the place as "... Clients". It should be
  "Households".
- **N3** - When this process is itself redirected, the first screen shows
  both `DATA_HOME_REDIRECTED` and a `REDIRECTED_COPY` line for the same
  folder. The second line says "The app never uses it" (as the F7 hand-back's
  live proof shows).
  - Fix: in `_machine_warnings` (api.py:3579), leave out the `REDIRECTED_COPY`
    lines when a `DATA_HOME_REDIRECTED` refusal is already in the list.
  - Or keep it, and say why in the SPEC.
- **N4** - The loading placeholder rows (`.row-skeleton`, shell.css:611-613)
  still have four columns. On Overview and Reminders, which now have five,
  they do not line up with the headers.
  - Fix: add `#page[data-list="overview"] .row-skeleton,
    #page[data-list="reminders"] .row-skeleton` to the five-column rule at
    shell.css:537.
- **N5** - One `test_shell_menu` test failed once, and the cause was timing,
  not this change:
  - `test_open_error_log_opens_the_named_file_and_says_so_when_there_is_none`
    failed once under 3.11 while 12 test files ran in parallel.
  - Alone it passes, both on this branch (twice) and on base `392ec27`.
  - Cause: its harness waits a fixed `await wait(100)`
    (tests/test_shell_menu.py:245) for `main.js` to be ready. The menu
    words were the only change to `main.js`.
  - Fix, separately: wait for `whenReady` instead of a fixed 100 ms.

## Checked and sound (no finding)

- **F7 R1 (the refusal):**
  - The probe runs only on Windows, only with `TRACKER_DATA_HOME` unset or
    blank, and once per process (`_redirect_answer`).
  - The probe file is removed in a `finally`, and my probe confirmed it is
    removed even when listing the folder fails.
  - A failed write answers None.
  - The refusal is a `SettingsError`, so the first screen
    (`_machine_warnings`'s `try`) and the pass (`runner.py`) say it with no
    new code.
  - The product name comes from `product_name()`. Ruling 1 accepted that.
  - Package names and paths only: no client name.
  - The live Windows proof is in the F7 hand-back.
- **F7 R2 and R3:**
  - `redirected_copies()` only reads, with `isdir`. It answers nothing under
    `TRACKER_DATA_HOME`, as ruling 2 says.
  - The tripwire's `real_places` is untouched (`tests/conftest.py` is not in
    the diff).
  - `make_samples.py` builds under a throwaway `TRACKER_DATA_HOME`. It drops
    `TRACKER_STORE` and closes the store and the log before the folder is
    removed.
- **P194/P195 on Overview and Reminders:**
  - The columns are Tax Year, Taxpayer, Form Type, Status (Stage), Date
    (Drafted) (pages.js:72-76).
  - The form is cut from the taxpayer's name only when the record's form
    leads the name. It is never a guess.
  - The household appears in the tooltip "Navigate to Return ({household})"
    and in the row's screen-reader description.
  - The Linked Households mark moves to the name cell, still owned by the
    household.
  - The paused household's row keeps its place.
  - Each column has its own sort key, with blanks last both ways.
  - `aria-sort`, the header buttons and the keyboard (Ctrl+Shift+Arrow) work
    unchanged.
  - The year and the heading year use `tabular-nums` (shell.css:21).
  - High Contrast is unchanged: no new colours.
  - Saved widths: one kept for a column a list no longer has is ignored
    (`pagesWidthOf`), and the next save drops it (`pagesSetWidth`). Sort
    orders are kept only in memory, so no old saved order exists.
- **"Apply to all windows" (P195), each window SPEC-firm-columns section 2
  left unchanged:**
  - The Needs Review headings and the household and year pages now say each
    field once.
  - Return page title and path row (`pages.js:696`, `shell.js:438,644`): the
    title is "1040 - Name" with no form chip and no year beside it, and the
    year is its own step in the path. The form and the year each appear once
    there.
  - Search (`shell.js:552-566`): "1040 - Name", noted "{household} {year}".
    Each field appears once.
  - The roll-forward dialog (`app.js:1294-1303`): a label plus a form picker.
    The picker is a choice for next year, not a repeat.
  - Households: no return names.
  - Nothing else in the renderer prints "({year})" after a name, and
    `pagesReturnText` is gone.
- **P196:**
  - The menu (H&ousehold, Alt+O, no clash), the page "Households", the
    Taxpayer and Household split, and Title Case all match SPEC-taxpayer-words.
  - The folder buttons keep "Clients", as ruled (R3).
  - The standing rules, the pilot terms and the reminder drafts keep their
    words.
  - No code name changed.
  - `main.js`'s menu defaults equal `api.MENU`.
  - The wording table matches the screen, apart from N2.
- No monospace font in any renderer CSS, HTML or JS.
- No dead code found:
  - `pagesReturnText`, `headingLink` and `linksIn: "detail"` are all gone.
  - Every new helper has a caller.
  - `ruff` is clean.
- The new tests are named as the claims they make.

## Test results (each file its own process, in parallel)

Interpreters: Python 3.11.15, a private virtual environment in the
reviewer's scratchpad, installed from `requirements.lock` and
`requirements-nodeps.lock` with their hashes checked; and the office's
`C:\Python314\python.exe` (3.14.4). Each round started all 12 files at once.

| File | 3.11.15 | 3.14.4 |
|---|---|---|
| tests/test_settings.py | 65 passed | 65 passed |
| tests/test_api.py | 441 passed | 441 passed |
| tests/test_shell.py | 158 passed | 158 passed |
| tests/test_shell_menu.py | 1 failed, 29 passed, 3 skipped; the failed test passed when rerun alone (twice), and passes on base 392ec27 (N5) | 30 passed, 3 skipped |
| tests/test_reasons.py | 58 passed | 58 passed |
| tests/test_tour.py | 9 passed | 9 passed |
| tests/test_pilot.py | 24 passed | 24 passed |
| tests/test_layers.py | 29 passed | 29 passed |
| tests/test_single_source.py | 179 passed | 179 passed |
| tests/test_repo_map.py | 80 passed | 80 passed |
| tests/test_errors.py | 83 passed | 83 passed |
| tests/test_tripwire.py | 19 passed | 19 passed |

- `python -m ruff check .`: All checks passed!
- `python tools/repo_map.py check`:
  - With this review file present, it reports the map stale. The only reason
    it names is this file, which is not tracked by git.
  - With this file set aside, it reports "Map is current (407 nodes,
    generated 2026-09-30)", exit 0. The file was put back afterwards.
  - The only warning is a CRLF line-ending note on
    `pilot/SPEC-F7-redirected-data-folder.md`.
- My own checks are in the reviewer's scratchpad:
  - `probe_vocab.py` lists every word in the app's vocabulary that says
    "client". That is how M1 and S1 were found.
  - `probe_perm.py` makes listing the Packages folder fail with
    `PermissionError`. That is S2.
