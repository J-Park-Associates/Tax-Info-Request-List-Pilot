# P199 hand-back: the list and dialog notes from the 0.3 Windows check

Written 2026-10-01 (PDT) by the P199 builder, branch `claude/check-notes` from
`4534b30`. Not pushed, no pull request, no rebase. Not self-reviewed: a
separate reviewer is next. SPEC: `pilot/SPEC-check-notes-0.3.md`.

## Items (file:line on the branch)

1. **L4, Date too far right.** Cause: the Taxpayer / name column was
   `minmax(224px, 1fr)` and took all the window's slack; the date was also
   right-aligned. Rule: every firm-list column is exactly its width, slack
   blank after the last column, date and its header start at the column's
   left: Date starts 656px into the list at every width from 1100px up.
   `app/renderer/shell.css` 535-565 (five-column track, new four-column rule
   for Needs Review and Households, `.row-end` start on the four lists; the
   end header's right-align rule removed); `pages.js` 81-84 (comment).
2. **N2a, widening grew left.** Same cause; fixed by item 1 with no script
   change. Drag, double-click fit, Ctrl+Shift+Arrow, focus ring, High
   Contrast and motion unchanged.
3. **N2b, order reset on restart.** Kept per PC per list in `localStorage`
   `tracker.order`, as widths are; damaged values fall back to the usual
   order. `pages.js` 92, 97, 760, 769-774, 789, 866-898 (new
   `pagesStoredOrder`, `pagesSaveOrder`), 1163. Replaces P139's order half
   (P139 row marked).
4. **N3, bullet.** `passEnded` no longer strips it (`app.js` 2314-2320); the
   return is said by its fields, "• 2024 John A. Smith 1040: Sort Failed:
   Folder Not Found" (new `sortReturnSaid`, `app.js` 2127-2137; label
   fallback). `pilot/wintest/PROMPT-shell.md` step 13 reworded.
5. **N5, clock style.** The app's style is `toLocaleTimeString([], {hour:
   "numeric", minute: "2-digit"})` (`pagesTime`, the last-sort line): "10:30
   PM". New `scheduleClock` (`app.js` 2022-2029) used in the dialog (2063)
   and the Save toast (2091). Engine sentence unchanged.
6. **Household Sort that does nothing. Owner question Q1** (SPEC 6): A
   "Nothing to Sort" notice (recommended, BUILT); B a toast; C nothing. A
   file still arriving says "Nothing Done: 1 Still Syncing." (approved
   pattern; a 6-word "Nothing to Sort: 1 Still Syncing" broke the five-word
   rule). `app.js` 2168-2176; `tracker/api.py` below.

## Every line changed in tracker/api.py

- 494-501: new comment (7 lines) and `SCAN_NOTHING_TO_SORT = "Nothing to Sort"`.
- 1892-1893: `"but": SCAN_BUT, "not_in_pass": SCAN_NOT_IN_PASS,` now ends
  with a comma, and the new line `"nothing_to_sort": SCAN_NOTHING_TO_SORT},`.

## Lane overlap

- `pilot/wintest/PROMPT-shell.md` (lane C's folder): step 13 only, lines
  116-121. `tests/test_shell_menu.py` not touched.

## Dead code

None found in the changed files; removed the end header's right-align rule
(`.col-cell[data-cell="end"]`) and the bullet-stripping in `passEnded`.
Ruff: "All checks passed!".

## Tests (each file its own process, in parallel)

| File | Python 3.11.15 (scratchpad venv) | C:\Python314 |
|---|---|---|
| `tests/test_shell.py` | 169 passed | 169 passed |
| `tests/test_single_source.py` | 179 passed | 179 passed |
| `tests/test_layers.py` | 29 passed | 29 passed |
| `tests/test_repo_map.py` | 80 passed | 80 passed |
| `tests/test_api.py::test_every_drawn_word_the_vocabulary_carries_is_in_title_case` | 1 passed | 1 passed |

The first single_source run failed 2 guards (comments in `app.js` quoting
"Needs Review" and "Nothing Done:"); comments reworded, touched files rerun.
New tests in `test_shell.py`: five (SPEC 1, 3, 4, 5, 6). `test_errors.py`
not run (no error wording changed). Map: `python tools/repo_map.py check` ->
"Map is current (415 nodes, with this hand-back)".

## 1100px proof

Real stylesheets, before (HEAD) and after, in Chromium (browser pane, static
Overview, 240px side): Date text at 1100px 797 -> 656px; at 1920px 1617 ->
656px; widening Form Type 96 -> 160 at 1920px moved Status and Date 64px
right (before: did not move). Not measured on Windows itself (Segoe UI,
classic scrollbar); the token sum is still 832 <= 843px.

## Not done

- Not measured on Windows; the next Windows check should look at L4/N2/N5.
- Q1 waits for Jason's letter (record in SPEC 6 and DECISIONS P199).
