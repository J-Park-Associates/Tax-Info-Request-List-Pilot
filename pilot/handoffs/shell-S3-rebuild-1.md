# Shell S3 - rebuild 1

Builder: Sonnet 5.5, default effort. Date: 2026-09-29. Answers `shell-S3-review-1.md`.
Branch `claude/friendly-archimedes-33y9uk` (local `rebuild-s3`), started from `7e199c2`.
The last commit is named at the foot of this file's commit message and in the reply that carried it.

## The findings

All ten findings were right. None is refused.

- **F1 fixed.** `shellChangeRoot()` (`shell.js`) now fills `#firm-input` and `#phone-input` from `vocab.firm` and `vocab.settings.phone` before opening the setup page, as `app.js` does at first run, so Start no longer sends empty strings. Test: `test_changing_the_clients_folder_keeps_the_firms_name_and_phone`.
- **F2 fixed.** `forced-color-adjust: none` on the three Highlight fills in `shell.css`'s forced-colours block (selected section, selected search option, focused row). Contrast shot looked at: "Clients" is light on the dark fill and readable. The handoff's older blame on the emulator was wrong; the backplate was the cause, as the review said.
- **F3 fixed.** The contrast-theme focus ring is `CanvasText`.
- **F4 fixed.** `routeTitle()` returns `""` for firm pages; a new `drawTitleOnly()` draws no H1 when the title is empty, in the failed and the fallback state; `shellLoading` leaves the title out (it must spread an empty list, not `null`, or `replaceChildren` prints the word "null"; caught in the first re-shoot and fixed). Loading and counts-failed shots looked at: no H1.
- **F5 fixed.** The household and return path segments fall back to `""`, like `routeTitle()`. Test: `test_a_household_or_return_not_in_the_list_never_shows_its_path_as_a_name`.
- **F6 fixed.** While `n` and `total` are unknown the side panel's foot draws only the bar, no text. Sort-running shot looked at ("Sorting 3 of 12" with its bar). I did not ask for a new word.
- **F7 fixed.** Tour titles are "Sort" and "Needs review". Proposed decision 5 in `shell-S3.md` is rewritten to say so.
- **F8 fixed.** Section rows use `padding-inline: var(--sp-2)`; names sit 16px from the panel edge (seen in the shots).
- **F9 fixed.** `shell-S3.md`'s "Loud failures" list now names `#misfits-card`, `#room-card`, `#household-two-years`, and `#household-paused` with `#btn-accept-folder-name` (marked as a real silent failure). The harness's "locked" scenario no longer calls `notice(...)`; the handoff says the real `#lock-notice` is hidden until S4 moves `showLock` to a notice.
- **F10 fixed.** The underline offset is `var(--sp-1)`; `--size-menu-row` is deleted.

One new test, `test_the_contrast_theme_fills_and_rings_follow_spec_10_4`, pins F2, F3 and F8 in `test_shell.py`.

## For Jason

Not mine to decide; the code is left as built.
1. **Keydown listeners.** `tour.js` and `pilot.js` keep their own capturing listeners, and the new files add none (proposed decision 2). This departs from SPEC 14.1's "one listener". Approve, or ask S6 to fold them in.
2. **No tooltip when a text box is focused** (proposed decision 3). Departs from SPEC 8.5 as written; hover still shows it.
3. S6 should make sure SPEC 14.1's vocabulary tests exist, since none of S1-S3 owns them (review's note).

## Tests run

Python 3.11 (`/tmp/v`) and 3.13 (fresh venv, pinned packages), the files grouped into a few processes per interpreter (the 3.11 and 3.13 runs in parallel):
`test_shell`, `test_pilot_ui`, `test_tour`, `test_pilot`, `test_layers`, `test_pilot_installer` (110 pass, both); `test_single_source` (167, both); `test_api` and `test_repo_map` (448, both). `python -m ruff check .` clean. `tools/repo_map.py update` then `check` current. `test_build`'s scratch-roots OCR test was not run (fails on the base too).
Harness re-shot: loading, sort-running, locked, counts-fail, household, forced-colors; looked at the contrast, side-panel, loading and failed shots.
