# One field per column on the firm's lists - SPEC (P194, P195)

Decisions: **P194** (Jason, 2026-09-30), **P195** (his answers to this SPEC's
two owner questions, and the column's word "Taxpayer"). P196 (Client becomes
Taxpayer everywhere else) is a separate SPEC stacked on this branch and is not
built here. Builder: one agent, this worktree. A separate reviewer reviews the
diff against this SPEC.

## 0. What changes, in plain English

Today a return in Overview's Work Waiting reads, left to right:
`[1040] 1040 - Chidi & Ada Okafor (2025)` | `Okafor Family` | `2 Need You` |
`Mar 3`. The form is said twice (the chip and the start of the name) and the
year is folded into the name. After this change it reads:

| Tax Year | Taxpayer | Form Type | Status | Date |
|---|---|---|---|---|
| 2025 | Chidi & Ada Okafor | [1040] | 2 Need You | Mar 3 |

Each field is said once, in its own column, in the order Jason gave. Reminders
gets the same five columns (its Status is "Stage", its Date is "Drafted").
Where a window is not a table (a Needs Review return heading, the household
and year pages), it says the year, the taxpayer and the form once each.

## 1. Rulings and their reasons

1. **Overview's Work Waiting columns are Tax Year, Taxpayer, Form Type, Status,
   Date, left to right** (P194, Jason's order; P195 the word "Taxpayer").
   Reason: one field per column, nothing said twice.
2. **Tax Year** is the return's tax year from the row the engine already
   sends (`firm.returns[].year`, the record's year). Blank when the engine
   sends none; never typed or guessed by the renderer.
3. **Taxpayer** is the return's name without the form it begins with: the
   return's name (`return_name`) less the leading `"{form} - "` that the
   naming pattern (`vocab.layout.return_name_pattern`, `"{form} - {client}"`)
   puts there, **only when the return's recorded form is what the name begins
   with** (letter case and a hyphen inside the form number aside: the
   catalog itself writes 1120S as "1120-S"). A return with no recorded form, or a name
   someone typed another way, is shown whole - never cut by a guess (the
   standing rule "nothing is guessed"; P172: the form is read from the record,
   never from a folder name). It is still the link that opens the return, and
   it may wrap to two lines rather than be cut (ruling 27).
4. **Form Type** is the form chip (P145), from the record's form, now in its
   own column. Blank when the record has none. Because the name no longer
   repeats it, the chip is no longer hidden from a screen reader.
5. **Status and Date** are unchanged (SPEC-lists 3, 11).
6. **The household** (the old Client column) is no longer a column (P195 Q1,
   "Take your recommendation"): its name is in the Taxpayer link's tooltip -
   "Navigate to Return ({household})" - and in the row's screen-reader
   description, and the return page names it in its path row (unchanged).
   Reaching the household page: the path row on the return page, or the row's
   right-click menu (unchanged). The **Linked Households mark** (P171) moves
   with it: it sits after the taxpayer's name, still not a Tab stop in a list,
   still opened by Space on the active row, still owned by the household
   (`dataset.owner` is the household name, so a redraw re-finds it).
7. **A household paused for two open years** (ruling 21) is still Overview's
   first row: its Tax Year and Form Type are blank, its Taxpayer cell is the
   household's name (the link to the household), and its Status is the
   paused words, as today.
8. **Reminders** takes the same five columns (P195 Q2, "yes, apply to all
   windows"): Tax Year, Taxpayer, Form Type, then its own Stage and Drafted.
   The household goes to the tooltip and description as on Overview.
9. **Needs Review is a table of files, not of returns.** Its columns stay
   File, Suggestion, Reason, Received: adding Tax Year, Taxpayer and Form Type
   to each file would repeat one return's fields on every file under it. Its
   **return heading** says each field once instead: the year, the taxpayer
   (the link to the return, tooltip "Navigate to Return") and the form chip,
   in the columns' order. The household beside the heading stays the small
   grey link P180 settled.
10. **Household and year pages** (no headers, SPEC-lists Q2): a return's row
    is the form chip then the taxpayer (the link), with no year - the year is
    the heading above the rows (household page) or the page's title (year
    page). Their usual order is unchanged (by the return's name).
11. **Clients** lists households, not returns, and shows no return name:
    unchanged. Its "Client Name" header is P196's business.
12. **Ordering** (SPEC-lists 3's cycle: natural, reverse, usual):
    - Tax Year: by the number, oldest first.
    - Taxpayer: by the name as shown, numbers in numeric order.
    - Form Type: in the order the app already lists forms - the side panel's
      Client Types (`vocab.client_type_forms`: 1040; 1120, 1120S, 1065; 1041;
      990) - then any other form by its name; a blank form last both ways.
    - Status, Date: unchanged.
    P180's "the Return column orders by the whole name as shown, form first"
    has no column left to apply to on these two lists; the three columns now
    order separately.
13. **Widths** (SPEC-lists 4): new columns with their limits and usual widths:

    | Column | Least | Most | Usual |
    |---|---|---|---|
    | Tax Year (`year`) | 64 | 160 | 80 |
    | Taxpayer (`taxpayer`) | 160 | 640 | 224 (its least; it takes what the others leave) |
    | Form Type (`form`) | 64 | 160 | 96 |

    Status and Date keep theirs. **Stored widths:** a list's saved widths are
    read only for that list's own columns, so a saved width of the old Return
    (`name`) or Client (`detail`) column on Overview or Reminders is ignored,
    and the next save drops it (it never widens the Taxpayer column). Status
    and Date keep a saved width, since they mean the same. View > Reset Column
    Widths still forgets them all.
14. **1100px:** the five usual widths, four 16px gaps and the 32px padding
    each side are 80 + 224 + 96 + 160 + 144 + 64 + 64 = 832px, inside the
    843px beside Windows' scrollbar (P179). No sideways scroll.
15. **Keyboard, focus, High Contrast:** the new headers are the same
    `button.col-head` in a `role="columnheader"` cell (Tab stop, Enter/Space,
    Ctrl+Shift+Arrow resizes, visible focus ring, `aria-sort`), and the
    forced-colours rules already cover the header, grips and chip. Motion is
    the existing `--dur` (150-250ms). No new key.
16. **Type:** no monospace anywhere; the year (`.row-year`, `.head-year`) and
    the date use `font-variant-numeric: tabular-nums`.

## 2. Every window that shows a return's long name (P195 Q2)

| Window | Where | Today | After |
|---|---|---|---|
| Overview, Work Waiting | `pages.js` `pagesWorkRows` (962-986), `pagesPausedRows` (991-1000), `PAGES_COLUMNS.overview` (69) | chip + "1040 - Name (2025)", household column | Tax Year, Taxpayer, Form Type, Status, Date (rulings 1-7) |
| Reminders | `pagesReminderSpecs` (1149-1168), `PAGES_COLUMNS.reminders` (71) | chip + "1040 - Name (2025)", household column | Tax Year, Taxpayer, Form Type, Stage, Drafted (ruling 8) |
| Needs Review, return heading | `pagesReviewGroup` (1094-1121) | "1040 - Name (2025)" | year, taxpayer link, form chip (ruling 9) |
| Household page | `pagesReturnSpecs` (1269-1279), `pagesHousehold` (1282-1295) | "1040 - Name (2025)" under a "2025" heading | chip + taxpayer (ruling 10) |
| Year page | `pagesYear` (1297-1303) | "1040 - Name (2025)" under the H1 "2025" | chip + taxpayer (ruling 10) |
| Clients | `pagesClientSpecs` (1180-1209) | households only | unchanged (ruling 11) |
| Return page H1 and path row | `pagesTitleFor` (649-655), `shell.js` `crumbList` (438), `shell.js` 644 | "1040 - Name", after the year in the path | unchanged: the return's own name, which is also its folder's name; the year is its own segment of the path, so nothing is said twice |
| Search results | `shell.js` `findOptions` (548-570) | a return as its name, noted "{household} {year}"; a file noted "{return name} {year}" | unchanged: one name and its note, each field once; the name is what a person types to find it |
| Dialogs and notices naming a return by its label ("{household} {year} {return name}", `layout.ENGAGEMENT_LABEL_PATTERN`) | `app.js` 1017, 1303, 1418, 1560, 1572, 1663, 2134, 2288 | one label in a picker, list or sentence | unchanged: each field once, and not a list of rows |

`pagesReturnText` (`pages.js` 172-177, "{Return Name} ({Year})", ruling 13)
has no caller left and is deleted. Ruling 13's purpose - telling two years of
one return apart - is now the Tax Year column, the year heading or the year
page's title.

## 3. Files, functions and lines

| File | What |
|---|---|
| `app/renderer/pages.js` | `PAGES_COLUMNS` (overview and reminders: `year`, `taxpayer`, `form`, `status`, `end`), `PAGES_CELLS` (every cell any list has), `PAGES_WIDTHS` (`year`, `taxpayer`, `form`); new `pagesTaxpayer`, `pagesFormKey`, `pagesFormCell`, `pagesReturnHeading`, `pagesReturnCells`, `pagesReturnKeys`; changed `pagesLinkNode` (a link may carry its own tooltip), `pagesNameCell` (no chip in a return row; chip no longer `aria-hidden`; the link mark's owner), `pagesDetailCell` (its link-mark branch, which no list uses any more, removed), `pagesRow` (the return row's five cells, `row-return`, the household in the description), `pagesGroup` (a heading may be nodes; `headingLink` gone), `pagesColumnHeads` (a list's own cells), `pagesFit` (the new cells), `pagesWidthOf` / `pagesSetWidth` (a list's own cells only), `pagesWorkRows`, `pagesPausedRows`, `pagesReviewGroup`, `pagesReminderSpecs`, `pagesReturnSpecs`; deleted `pagesReturnText`. |
| `pilot/harness/shoot.mjs` | The household-tooltip shot becomes the taxpayer-tooltip shot. |
| `app/renderer/shell.css` | The five-column grid for `#page[data-list="overview"]` and `[data-list="reminders"]` rows, header row and least width; `.row-year`, `.row-form`, `.head-year`; tabular digits for the year. |
| `app/renderer/pilot-ui.css` | `--size-col-year: 80px`, `--size-col-taxpayer: 224px`, `--size-col-form: 96px`. |
| `tracker/api.py` | `SCREEN["columns"]` (lines 1379-1395 only): add `tax_year` "Tax Year", `taxpayer` "Taxpayer", `form_type` "Form Type", `taxpayer_tip` "{action} ({household})"; remove `return` and `client`, which nothing draws any more. Words only; no reply field changes. |
| `pilot/wording-shell.tsv` | The four new rows; the two removed words marked removed. |
| `pilot/harness/interact.mjs` | The ruling-27 check at 1100px: a return row's year is its own cell, never cut. |
| `docs/repo-map.curated.json` | `pages.js`'s note. Then `python tools/repo_map.py update`. |
| `pilot/SPEC-lists.md` | One pointer line in sections 1 and 2 to this SPEC (nothing re-opened). |
| `pilot/HANDOFF.md` | One status line. |

Not touched: `tracker/settings.py`, `tracker/api.py` 3543-3561,
`make_samples.py`, `run_checks.ps1`, the runbook's data-folder paragraph (the
parallel builder's), and no reply field of the API.

## 4. Owning tests

- `tests/test_shell.py` - the renderer's owner. Changed expectations where a
  test read "1040 - Alpha (2025)" or four headers; new tests named as claims:
  `test_overview_and_reminders_say_tax_year_taxpayer_and_form_type_once_each_in_their_own_columns`,
  `test_the_taxpayer_is_the_name_without_its_recorded_form_and_never_a_guess`,
  `test_the_household_is_in_the_taxpayer_tooltip_and_the_rows_description`,
  `test_tax_year_orders_by_number_and_form_type_by_the_apps_form_order`,
  `test_a_saved_width_of_the_old_return_column_never_reaches_the_new_layout`,
  `test_needs_review_household_and_year_pages_say_each_field_once`,
  and the 1100px sum test extended to the five columns.
- `tests/test_api.py::test_every_drawn_word_the_vocabulary_carries_is_in_title_case`
  (the new words).
- Guards: `tests/test_layers.py`, `tests/test_single_source.py`,
  `tests/test_repo_map.py`.
- Not run: `tests/test_shell_menu.py` (no menu changes), `tests/test_tripwire.py`
  and `tests/test_errors.py` (no error wording).

## 5. What staff will notice

- Overview and Reminders: five columns, Tax Year first; the taxpayer's names
  without "1040 - " or "(2025)"; the form chip in its own column; no
  household column. Hovering a taxpayer shows "Navigate to Return (Okafor
  Family)". The violet linked-households icon is beside the taxpayer.
- A column width someone dragged on the old Return or Client column is gone
  on those two lists; Status and Date keep theirs.
- Needs Review: each return heading reads "2025  Chidi & Ada Okafor  [1040]"
  with the household beside it as before.
- Household and year pages: "[1040] Chidi & Ada Okafor" under the year.

## 6. Words (the wording table)

| Key | Words | Where |
|---|---|---|
| `columns.tax_year` | Tax Year | Header, Overview and Reminders |
| `columns.taxpayer` | Taxpayer | Header, Overview and Reminders (P195) |
| `columns.form_type` | Form Type | Header, Overview and Reminders |
| `columns.taxpayer_tip` | {action} ({household}) | The Taxpayer link's tooltip, e.g. "Navigate to Return (Okafor Family)" |
| `columns.return`, `columns.client` | removed | No list draws them |

Header tooltips follow P180: "Sort by Tax Year", "Sort by Taxpayer", "Sort by
Form Type".

## 7. Docs made true in the same commit

README and runbook describe no list columns (checked: neither names Work
Waiting's columns), so no line of either becomes untrue. `pilot/SPEC-lists.md`
sections 1-2 gain a pointer to this SPEC; `pilot/HANDOFF.md` a status line;
the repo map's `pages.js` note; the wording table.

## 8. Open for Jason

Both answered (2026-09-30), recorded in P195:

- **Q1. Where does the household name go, now that the old Client column is
  gone?** A) into the Taxpayer cell's tooltip and the return page
  (recommended; Jason listed five columns); B) a sixth Household column;
  C) a small grey line under the taxpayer. **Answered A**: "Take your
  recommendation." Built.
- **Q2. Does one field per column apply to the other windows that show a
  return's long name?** A) Overview only; B) every window (recommended only
  narrowly). **Answered B**: "yes, apply to all windows." Built as section 2.

No question is open.
