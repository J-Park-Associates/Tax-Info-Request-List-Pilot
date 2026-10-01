# Firm columns (P194, P195) - builder's hand-back

Branch `worktree-agent-afd00f65a766aa023` (fast-forwarded from `fe6fedf` to the
stated base `392ec27` first). SPEC: `pilot/SPEC-firm-columns.md`. Decision
rows written before use: P195 (`a19a647`), P196 verbatim from the coordinator
(`4099e3c`). Build commit `5a9b59b`; this hand-back is the commit after it.
Not pushed; no pull request.

## Rulings built (file:line, after the build)

| Ruling (SPEC 1) | Where |
|---|---|
| 1, 8: Overview and Reminders are Tax Year, Taxpayer, Form Type, Status/Stage, Date/Drafted | `app/renderer/pages.js:72` `PAGES_COLUMNS`; `:443` `pagesRow` (five cells, `row-return`); `:1016` `pagesReturnCells`, `:1027` `pagesReturnKeys`; `:1032` `pagesWorkRows`; `:1219` `pagesReminderSpecs`; `app/renderer/shell.css:537` the five-column grid and least width |
| 2-3: year from the row; Taxpayer = name less the recorded form, never a guess (case and a hyphen in the form number aside) | `pages.js:182` `pagesTaxpayer` |
| 4: Form Type is the form tag in its own cell, read by a screen reader | `pages.js:335` `pagesFormCell`; `:321` `pagesNameCell` (no `aria-hidden`; no tag inside a return row) |
| 6: household in the Taxpayer tooltip ("Navigate to Return (Okafor Family)") and the row description; link mark after the taxpayer, owned by the household | `pages.js:237` `pagesLinkNode` (`link.tip`), `:1016`, `:443`; `tracker/api.py:1380-1395` `columns.taxpayer_tip` |
| 7: a paused household is a row in the same five cells | `pages.js:1059` `pagesPausedRows` |
| 9: Needs Review heading = year, taxpayer link, form tag | `pages.js:341` `pagesReturnHeading`, `:1164` `pagesReviewGroup`, `:612` `pagesGroup` (`headingLink` gone) |
| 10: household and year pages = form tag + taxpayer under the year | `pages.js:1335` `pagesReturnSpecs` |
| 12: ordering - year by number, Form Type in the Client Types' form order, blanks last | `pages.js:197` `pagesFormKey`, `:1027` |
| 13: widths; an old Return/Client width never reaches the new layout and is dropped at the next save | `pages.js:83` `PAGES_WIDTHS`, `:79` `PAGES_CELLS`, `:881` `pagesWidthOf`, `:889` `pagesSetWidth`, `:834` `pagesFit`, `:782` `pagesColumnHeads`; `app/renderer/pilot-ui.css:46` tokens 80 / 224 / 96 |
| 16: tabular digits for the year | `shell.css:21` |

Words: `tracker/api.py` changed only at lines 1380-1395 (`SCREEN["columns"]`):
added `tax_year`, `taxpayer`, `form_type`, `taxpayer_tip`; removed `return`
and `client` (nothing draws them). No reply field changed; nothing in the
parallel builder's places touched. `pilot/wording-shell.tsv` rows updated.
`pagesReturnText` deleted (no caller). Harness: `pilot/harness/interact.mjs`
(1100px year check, heading check) and `shoot.mjs` (taxpayer tooltip shot).

## Owner questions

Both answered by Jason (2026-09-30), recorded in the SPEC's "Open for Jason"
and P195: Q1 A "Take your recommendation" (household in the tooltip and the
return page); Q2 B "yes, apply to all windows" (built as SPEC section 2). The
word "Taxpayer" is his (P195); the app-wide rename is P196's SPEC, not built.
Nothing is open.

## Dead code

Removed: `pagesReturnText`; `pagesDetailCell`'s link-mark branch and the
`headingLink` path in `pagesGroup` (no caller after the change); the
`columns.return` / `columns.client` words. Ruff: `All checks passed!`

## Tests (each file its own process, in parallel)

| File | Python 3.11.15 (floor) | Python 3.14 (office, `C:\Python314`) |
|---|---|---|
| `tests/test_shell.py` | 158 passed | 158 passed |
| `tests/test_api.py::test_every_drawn_word_the_vocabulary_carries_is_in_title_case` | 1 passed | 1 passed |
| `tests/test_layers.py` | 29 passed | 29 passed |
| `tests/test_single_source.py` | 179 passed | 179 passed |
| `tests/test_repo_map.py` | 80 passed | 80 passed |

The first run failed two `test_single_source` guards (the word "chip" and a
catalog id in pages.js comments); comments reworded, the touched files rerun.
New tests in `test_shell.py`: the five-column claim, the taxpayer rule, the
household tooltip/description, year and form ordering, the old saved width,
Needs Review / household / year pages. The 3.11 run used a private venv in the
session scratchpad (hash-checked locks), not another worktree's.
`python tools/repo_map.py check`: "Map is current (402 nodes)".

## The 1100px proof

- Token sum, now a test (`test_the_four_lists_and_a_needs_review_card_fit_1100px_beside_a_windows_scrollbar`):
  80 + 224 + 96 + 160 + 144 + 4 x 16 + 2 x 32 = 832px <= 843px (P179).
- Header words measured in the Windows font with GDI+ (Segoe UI Variable
  Text Semibold, 12px): "Tax Year" 46px, "Taxpayer" 49px, "Form Type" 58px.
  A header button is the word + 28px (padding, gap, arrow): 74px in the 80px
  Tax Year column, 86px in the 96px Form Type column. The form tag "1120S" is
  30px + 8px. Nothing cuts at the usual widths.
- Not done: the rendered check (`interact.mjs`, Playwright) - Playwright is not
  installed on this PC; the updated checks are syntax-checked only. The
  Windows check should run them, or look at Overview at 1100 x 700.

## Left / notes

- `pilot/HANDOFF.md` top line says this awaits review.
- An existence check of `%LOCALAPPDATA%\ms-playwright` was run while looking
  for Playwright (nothing inside it was opened or read).
