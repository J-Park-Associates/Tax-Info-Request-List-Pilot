# Combined review fold (P193-P196), 2026-10-01

Builder's hand-back for folding `reviews/combined-review.md` into
`claude/zen-easley-93548b` (base `686d84b`), as `reviews/combined-rulings.md`
("Rulings on the combined review") rules. One commit; nothing pushed. The
review and rulings files are unchanged.

## Each finding

- **M1 (editor's "this client is not chased by email") - fixed.**
  `tracker/api.py:1220-1224` adds `EDITOR_HELP = {"reminders": f"{NO} = this taxpayer is not chased by email"}`
  beside `EDITOR_LABELS`; `tracker/api.py:2009` uses it ahead of
  `ENGAGEMENT_HELP`. `records.py` and the README it writes keep their words
  (R7, R9). `tests/test_api.py:9339-9341` adds the help lines to
  `test_no_word_the_window_draws_says_client_but_a_folders_own_name`, limited
  to the yes/no fields (Reminders, Active): the editor draws a help line only
  beside a yes/no box (`app.js` `renderEngagementFields`), and the review's
  "every editable field" would have caught the Due and Firm help lines, which
  are never drawn. New row at the end of `pilot/wording-shell.tsv`; new row in
  `SPEC-taxpayer-words.md` section 2.1.
- **S1 (other "client" sentences) - all kept, each listed with its reason** in
  `SPEC-taxpayer-words.md` section 3 (f), by the ruling's rule: `settings.py:144-147`
  and `runner.py:288` (the firm's clients' data in general, R4);
  `settings.py:972-985` (the clients root, a folder on disk, R3);
  `api.py:3857` `CLIENT_FOLDER_TAKEN` (the `Clients` tree, R3); `api.py:648`
  `RETURN_CREATED_LINE` (the README in the household's folder under
  `Clients`, and the Open Client Folder button, R3). None means the person on
  a return or a listed household, so no code changed.
- **S2 (unlistable Packages folder) - fixed.** `tracker/settings.py:172-179` new
  `PACKAGES_UNREADABLE` (folder + error class, no message, no client name);
  `settings.py:817-833` `_package_names` turns any other `OSError` into
  `SettingsError` with `errors.error_class` (imported at call time, so
  settings' load-time imports stay `layout`, `fsio`). The probe lets it
  through (refusing the data home: it cannot rule a redirect out) and still
  removes its file in its `finally`. `tracker/api.py:3577-3596`
  `_machine_warnings` catches it from `redirected_copies()` and says it once.
  Tests: `tests/test_settings.py:617-645` (os.scandir patched to
  `PermissionError(EACCES)`; both raise the sentence; no probe file left) and
  `tests/test_api.py:7677-7696` (list replies, one sentence, rest of the
  reply present, said once when the probe said it too). Docs: SPEC-F7 R1/R2
  notes, `docs/runbook.md:52-55`.
- **S3, S5 - check items, not code.** Added to `pilot/wintest/PROMPT-0.3.md`
  ("Two more checks for the next Windows check"): where the program landed
  (Jason lists the folder or the shortcut's target outside Claude) and one
  look at 1100 px (Overview, Reminders, the Needs Review search box).
- **S4 (HANDOFF stale) - fixed.** `pilot/HANDOFF.md:3-20` names F7, the
  combined branch, the review, rulings and this fold, what is open, and the
  `test_shell_menu` flake.
- **N1 comments - fixed.** `app/renderer/index.html:24-25` (Taxpayer Types,
  Households), `:508` (Household menu); `app/renderer/pages.js:93` (taxpayer),
  `:117` (Households' Taxpayer Type), `:1230` (more overdue taxpayer).
- **N2 - fixed.** `pilot/wording-shell.tsv`: `paging.nouns.clients` and
  `columns.client_name` now say "... Households".
- **N3 (contradictory copy line) - fixed** as ruled (R1's sentence alone):
  `settings.py:219-222` new `DataHomeRedirected(SettingsError)`, raised at
  `:751`; `api.py:3588-3591` leaves out the `REDIRECTED_COPY` lines when it is
  the refusal. Tests: `tests/test_settings.py:648-654`,
  `tests/test_api.py:7699-7713`.
- **N4 (four-column loading rows) - fixed.** `app/renderer/shell.css:533-544`
  adds Overview's and Reminders' `.row-skeleton` to the five-column rule;
  `:631-633` puts their second bar in column 4 (status), as column 3 is on the
  four-column lists.
- **N5 (`test_shell_menu` timing flake) - not fixed**, as ruled; recorded in
  `pilot/HANDOFF.md`.

Map: curated `tracker/settings.py` and `tracker/api.py` notes updated;
`python tools/repo_map.py update` run.

## Dead code

None found in the changed files: `ruff check .` passes (unused imports and
names), no commented-out code was added, and every new name is used
(`EDITOR_HELP`, `PACKAGES_UNREADABLE`, `DataHomeRedirected`, the tests'
`_packages_denied`).

## Tests (each file its own process, in parallel)

| File | Python 3.11.15 (scratchpad venv, hash-checked locks) | Python 3.14 (`C:\Python314`) |
|---|---|---|
| tests/test_api.py | 443 passed | 443 passed |
| tests/test_settings.py | 67 passed | 67 passed |
| tests/test_shell.py | 158 passed | 158 passed |
| tests/test_single_source.py | 179 passed | 179 passed |
| tests/test_errors.py | 83 passed | 83 passed |
| tests/test_repo_map.py | 80 passed | 80 passed |
| tests/test_layers.py | 29 passed | 29 passed |
| tests/test_tripwire.py | 19 passed | 19 passed |

`test_layers` ran because `settings` gained a call-time import; `test_tripwire`
because tests were added.

`python -m ruff check .`: All checks passed. `python tools/repo_map.py check`:
"Map is current (409 nodes)".
