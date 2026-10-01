# Pilot 0.3 - the lists: column headers, ordering, widths and group hierarchy - SPEC

Lane 4 of the Pilot 0.3 build (Jason, P140: all four lanes ship as Pilot 0.3;
this lane changes no version number). Decisions P135-P139 (`pilot/DECISIONS.md`).
It adds to `pilot/SPEC-shell.md` (sections 3.6, 3.9, 6.1-6.4, 5.1, 8.5, 10, 11)
and changes nothing that SPEC settled except where a section below says so.

## 0. What changes, in plain English

Jason, 2026-09-29, looking at Overview with 27 returns:

> "im not seeing a way to sort either. i should be able to sort by each column."

> "Household and file needs to be distinguished by color or size or font or all three."

> "columns should also be expandable and shrinkable."

After this change:

- The four firm lists (Overview's Work Waiting, Needs Review, Reminders and
  Clients, both of its tabs) have a row of **column headers** above their rows,
  in the rows' own columns (for example Return, Client, Status, Date).
- **Clicking a header orders the list by that column.** Clicking it again
  reverses the order; a third click puts the list back in its usual order. A
  small arrow beside the header's word shows which column orders the list and
  which way. The header's tooltip reads **"Sort by {Column}"** (Jason, Q1,
  P180); its "by {Column}" keeps it apart from the filing pass (the Sort
  icon, "Sort Failed", "Sorted 11:14 PM").
- **Each header can be made wider or narrower** by dragging its right edge, as
  in File Explorer; double-clicking the edge fits the column to its widest
  entry. From the keyboard, with a header focused, **Ctrl+Shift+Right** widens
  and **Ctrl+Shift+Left** narrows it. Widths are remembered on this PC; **View ›
  Reset Column Widths** puts them back.
- On **Needs Review**, a return's heading, its household beside it and its
  files now look different from one another: the return is the large bold
  link, the household is a small grey link, and each file name is a link in
  ordinary (not bold) type. File names are ordinary weight wherever they
  appear as rows, the return page included.

Staff notice: headers above the four lists; the lists can be reordered and
their columns resized; the Needs Review groups read as heading, household,
files. Nothing a client sees changes. No engine behaviour changes.

## 1. Which lists get headers (P135)

Since P194/P195, Overview's and Reminders' columns are Tax Year, Taxpayer,
Form Type, then Status/Stage and Date/Drafted, and the household has no
column: `pilot/SPEC-firm-columns.md`. The rows below for those two lists, and
section 2's `columns.return` and `columns.client`, are history.

| List | Page | Headers (name, detail, status, end) | Orderable |
|---|---|---|---|
| `overview` | Overview's Work Waiting | Return, Client, Status, Date | all four |
| `needs_review` | Needs Review (one header row for the page, above the first group) | File, Suggestion, Reason, Received | all four |
| `reminders` | Reminders | Return, Client, Stage, Drafted | all four |
| `clients` | Clients, Work Waiting and All tabs (one order for both) | Client, Returns, Status, (none) | the three with a word |

The Clients list's end column is always empty (SPEC-shell 6.4), so its header
cell is empty and cannot order anything; its width still follows the others.

**Not in this change (owner question Q2, recommendation A):** the household
page, the year page and the return page. A household holds a handful of
returns under year headings; a return's sections are in the order the work
takes (Needs You, Waiting on Client, Received, Set Aside) and, inside a
section, in the request list's own order, which the preparer set in the
request list editor. Reordering them would undo an order someone chose.

## 2. The words (P138; owner question Q1)

`vocab.screen.columns` in `tracker/api.py` (`SCREEN`), Title Case, at most five
words (ruling 10, P63):

| Key | Words | Where |
|---|---|---|
| `columns.return` | Return | Overview, Reminders |
| `columns.client` | Client | Overview, Reminders, Clients |
| `columns.status` | Status | Overview, Clients |
| `columns.date` | Date | Overview (the oldest waiting file's date, or the due date) |
| `columns.file` | File | Needs Review |
| `columns.suggestion` | Suggestion | Needs Review (the request it most likely is) |
| `columns.reason` | Reason | Needs Review |
| `columns.received` | Received | Needs Review |
| `columns.stage` | Stage | Reminders |
| `columns.drafted` | Drafted | Reminders |
| `columns.returns` | Returns | Clients |
| `columns.sort_by` | Sort by {column} | each header's tooltip, e.g. "Sort by Status" (Jason, Q1, P180) |
| `columns.width` | {column} Width {n} | said to a screen reader after a keyboard resize, e.g. "Status Width 176" |
| `vocab.menu.reset_columns` (`MENU`) | Reset Column Widths | View menu |

"Client" is the household's word on screen already ("Navigate to Client"). The
header is a button whose name is its word; the tooltip adds "Sort by".

**Owner question Q1** (decided C by Jason, 2026-09-30, P180; built in lane 4b): the header tooltip says
**A) "Order by Status"** (recommended: plain, and cannot be confused with
filing); B) "Arrange by Status" (File Explorer's word for grouping, a different
thing there); C) "Sort by Status" (the most familiar, but "Sort" is the filing
action here).

## 3. How ordering works (P135)

- **A header is a real button** (`button.col-head`) inside a
  `role="columnheader"` cell of a one-row `role="table"` named by the section
  (`vocab.screen.sections`). It is a Tab stop; Enter and Space press it (the
  browser's own button keys). Tab order: the headers left to right, then the
  list.
- **Click cycle:** first click orders by the column in its natural direction;
  the second reverses it; the third puts the list back in its usual order.
  `aria-sort` on the column header is `ascending` for the natural direction,
  `descending` for the reverse, `none` otherwise. The arrow is the drawn
  chevron (SPEC-shell 3.8), turned up for ascending and down for descending,
  shown only on the ordering column; no typed glyph.
- **Natural order of each column:**
  - **Names** (return, client, file, suggestion): alphabetical, numbers in
    numeric order (`localeCompare` with `numeric`), by the text as shown. A
    return is ordered by its whole shown name, form first ("1040 - …",
    "1120-S - …"), then its year: the header orders by what the column reads,
    as File Explorer does, so the order is predictable at a glance; the
    **Client** column is the way to order by the people's names. (Owner
    question Q7, recommendation A.)
  - **Status and Stage: by urgency, most urgent first** - the order the app
    already uses, never alphabetical. Rank: a return whose record cannot be
    read, or a household paused for two open years (0); anything that needs a
    person, "Held" (1); waiting on the client (2); complete (3); blank (4).
    Inside a rank: the larger count first ("12 Need You" before "3 Need You");
    on Reminders the later stage first (a later reminder is more overdue);
    then the words alphabetically (Needs Review's reasons all rank 1, so they
    are grouped by reason).
  - **Dates** (Date, Received, Drafted): by the date itself (the ISO date the
    API sent, never the drawn "Mar 3"), oldest first. On Overview a
    need-you return's date is its oldest waiting file and a waiting return's
    is its due date, as drawn.
  - **Counts** (Clients' Returns): by the number, fewest first.
  - **Blank cells always go last**, in both directions; ties keep the list's
    usual order.
- **Needs Review:** files are ordered inside each return's group, and the
  groups follow their first file (so ordering by Received newest first puts
  the return with the newest file on top). One header row serves every group.
- **The usual order** (no header chosen) is today's order, unchanged
  (SPEC-shell 6.1-6.4).
- **Memory (P139; owner question Q3, recommendation A):** each list keeps its
  chosen order while the app is open - leaving Overview and coming back, or a
  refresh after a sort, keeps it - and every list starts in its usual order
  when the app starts. Clients' two tabs share one order.
- **After a click** the list is drawn again (`pagesDraw`) and focus returns to
  the same header, so a keyboard user can press it again.
- **Where it happens:** in the renderer only (`pages.js`), on the rows the
  engine already sends in the `firm` reply. No engine change: every value a
  column orders by (names, counts, ISO dates, stage numbers) is in that reply
  already, and ordering is a view of it, not a fact about a return.

## 4. Column widths (P137; owner question Q4)

- **Drag:** each header cell carries a grip on its right edge
  (`span.col-grip`, 8px wide, centred in the 16px column gap, `cursor:
  col-resize`). Dragging it sets that column's width live. The grip shows a
  1px line in `--border-input` while the header row is hovered, and in
  `--focus` (2px) while its header has keyboard focus or it is being dragged.
- **Double-click the grip:** fits the column to its widest entry on the page
  (every cell of that column and the header's own word), within the limits.
- **Keyboard (Fluent: full keyboard use):** with a header focused,
  **Ctrl+Shift+Right** widens and **Ctrl+Shift+Left** narrows its column by
  16px (four grid steps). Chosen over Alt+Left/Right because Alt+Left is
  "Back" in File Explorer and Windows, and Alt is also the key that shows this
  app's hidden menu bar (ruling 3); Ctrl+Shift+Arrow extends a text selection
  in a box, and a header is a button, so it means nothing else here. The new
  width is said to a screen reader through a polite live region
  (`#page-say`): "{column} Width {n}".
- **Limits:**

  | Column | Least | Most | Usual |
  |---|---|---|---|
  | name (Return, File, Client) | 160 | 640 | 224 (its least; it takes the space the others leave; 240 until P179) |
  | detail | 80 | 400 | 200 |
  | status | 96 | 320 | 160 |
  | end (date and step) | 112 | 240 | 144 |

- **Needs Review's own usual widths:** Suggestion 160 and Reason 200 (the
  others 200 and 160). Lane 2 measured "Looks Like Wrong Document", "Names
  Another Household" and "Claimed by Two Requests" cut at 160px on Windows;
  the suggestions are short request names. The sum is unchanged, so the
  1100px window still fits. Whether 200px shows every reason whole in the
  app's font on Windows is **not measured here** (no Windows font in this
  build's tests): the Windows check measures it, and owner question Q9
  covers the case where it does not.
- **The name column absorbs the remaining space** (`minmax(name, 1fr)`, as
  today): its width is its least width, so narrowing it undoes a widening and
  never leaves a gap; widening any other column takes the space from it.
- **The 1100px window:** the usual widths add to 840 of the 860px main (P179: 843px beside Windows' scrollbar)
  area (SPEC-shell 3.6), so there is no sideways scroll. Headers are short
  words on one line and cut with "…" before they push anything. A return link
  still wraps (ruling 27: the year is never cut), and a status word keeps its
  "…" and tooltip. When a person widens columns past the window, the page
  area (`#page`) scrolls sideways - the header row and the rows together, as
  one - and the side panel and path row stay put. No whole-window scroll.
- **This answers cut status words** such as "Came in Email or Zip" (the
  status column can be widened or fitted). Lane 2 is shortening those words;
  this lane does not change them.
- **Memory (P139; owner question Q4, recommendation A):** widths are
  remembered per list on this PC across restarts, in the renderer's
  `localStorage` under `tracker.columns` (the app's own storage, never the
  record or the data folder: a width is a comfort of this screen, not a fact
  about a return). **View › Reset Column Widths** (`reset_columns`, enabled
  whenever a clients folder is set) forgets them all and redraws the page.
  Storage that cannot be read or written (a locked profile) leaves the usual
  widths and says nothing: the page still works, and the width holds while
  the app is open.
- **Order and width are remembered differently on purpose:** a width suits a
  screen and a person's eyes, so it should survive a restart; an order answers
  the question of the moment, and the usual order is the one the firm agreed
  (oldest waiting first), so each day starts there. Reset Column Widths does
  not touch the order.

## 5. The group hierarchy on Needs Review (P136; owner questions Q5 and Q6)

Before (today): the return heading ("1040 - Chidi & Ada Okafor (2025)", 16px,
weight 600, link blue, underlined), the household beside it ("Okafor Family",
12px, link blue, underlined) and the file rows ("Chidi Expenses 2025.gsheet",
14px, weight 600, link blue, underlined) are all bold-ish blue underlined
links, so groups and rows blur.

After (three levels; links stay links - underlined, SPEC-shell 3.9):

| Level | Size / line | Weight | Colour | Other |
|---|---|---|---|---|
| Return heading (H2 link) | 16 / 24 | 600 | `--link` | unchanged; 32px above each group (24px the first) |
| Household beside it | 12 / 16 | 400 | `--text-secondary`, underlined; `--link` on hover | then " · {count}" in `--text-caption` |
| File row name | 14 / 20 | **400** | `--link`, underlined | ordinary weight: a file is an item, not a heading |

- The same file-row weight applies wherever a file's own name is a row's name
  (Needs Review, and the return page's parked, moved, set-aside and extra
  received-file rows, `fileKind` or a file link). Request rows, return rows and
  household rows keep weight 600. The household page and year page have no
  household-beside-heading pattern, so nothing else changes there.
- **Contrast (WCAG AA, computed from the tokens of SPEC-shell 10.1):**

  | Pair | Light | Dark |
  |---|---|---|
  | `--text-secondary` on `--bg-page` (household, header words) | 8.28 | 9.36 |
  | `--text-secondary` on `--bg-hover` (header hovered) | 7.56 | 8.08 |
  | `--text-secondary` on `--bg-pressed` (header pressed) | 6.71 | 7.13 |
  | `--link` on `--bg-page` (heading, file names) | 12.67 | 9.38 |
  | `--border-input` on `--bg-page` (grip line, non-text, 3:1 needed) | 3.34 | 4.52 |
  | `--border-input` on `--bg-hover` | 3.05 | 3.90 |
  | `--focus` on `--bg-page` (grip while focused or dragged) | 5.17 | 7.60 |
  | `--text-caption` on `--bg-page` (the count) | 5.94 | 6.75 |

  The household's grey and the link blue are 1.53 (light) and 1.00 (dark)
  apart: colour is not the only cue; size (12 vs 16) and weight (400 vs 600)
  are, and the underline says "link" (WCAG 1.4.1).
- **Windows High Contrast (forced colours):** colours become the system's
  (`LinkText` for all three links); the levels still differ by size and
  weight (16/600, 12/400, 14/400). Header words are `CanvasText`, the grip
  line is `CanvasText` and always shown, the focus ring stays.
- **Owner question Q5** (built: A): the household beside a return heading is
  **A) grey, underlined, small** (recommended: a secondary link, clearly
  under the heading); B) link blue, underlined, small (as today, size alone).
- **Owner question Q6** (built: A): **A) no band** - space, size, weight and
  colour divide the groups, as SPEC-shell 3.6 and P71 set ("no box, no fill");
  B) a light band (`--bg-nav`) behind each return heading, a stronger cue at
  the cost of reversing P71.

## 6. The three sections of a return's page (P136, P176; Q8 built)

Request relayed by the orchestrator, 2026-09-29, looking at a return's page
(990 - Sunrise Community Arts Center): "please also distinguish between need
you, waiting on client, and received." Today the three headings and their
rows look the same; only the words differ.

Each of the three sections carries **its status colour**, the one its rows'
status words already use, so the heading and the statuses agree:

| Section | Colour (token) | Icon (drawn, 16px, `currentColor`) |
|---|---|---|
| Needs You | `--st-attention` (amber-brown) | `i-alert`: a circle with an exclamation stroke |
| Waiting on Client | `--st-waiting` (blue) | `i-clock`: a clock face |
| Received | `--st-done` (green) | `i-done`: the existing tick |

- **Heading:** a 3px bar (`--size-pill`) in the section's colour at the
  page's left edge beside the heading, and the section's icon in its colour
  before the words. The heading words keep `--text` (readability; the colour
  is on the bar and the icon, not on the words).
- **Rows:** a 2px edge (two `--size-hair`) in the same colour at the left of
  each of the section's rows, so the section reads as one block down the
  page. Drawn as an inset shadow, so no row moves by a pixel.
- **Set Aside** keeps its plain fold (it is not a status the client or a
  person is waiting on).
- **Not colour alone:** the heading words and the icon's shape carry the
  section. In Windows High Contrast the browser removes shadows, so the bar
  and edge go; the icon (`CanvasText`) and the words stay, which is the
  difference that must survive.
- **Where:** the return page only. Needs Review's groups are returns, not
  sections (their rows' status words are already amber), and the household
  page's groups are years; neither shares this look.
- **Contrast (non-text, 3:1 needed; the icons and the bar):**

  | Pair | Light | Dark |
  |---|---|---|
  | `--st-attention` on `--bg-page` / `--bg-hover` / `--bg-selected` | 7.80 / 7.12 / 6.44 | 9.44 / 8.16 / 7.53 |
  | `--st-waiting` on `--bg-page` / `--bg-hover` / `--bg-selected` | 10.36 / 9.45 / 8.55 | 8.96 / 7.74 / 7.15 |
  | `--st-done` on `--bg-page` / `--bg-hover` / `--bg-selected` | 7.63 / 6.97 / 6.30 | 9.80 / 8.46 / 7.81 |

  Every pair also clears 4.5:1, the text figure, though no text takes these
  colours here beyond the status words that already did.
- **Owner question Q8** (built: A): **A) a coloured left bar and icon on the
  heading, a matching edge down the rows** (recommended: strongest cue that
  keeps the page quiet); B) a lightly tinted band behind each heading; C) the
  icon alone.

## 7. Files, functions and lines

| File | What |
|---|---|
| `app/renderer/pages.js` | New: `PAGES_COLUMNS`, `PAGES_CELLS`, `PAGES_WIDTHS`, `PAGES_URGENCY`, `PAGES_USUAL`, `PAGES_WIDTH_STEP`, `PAGES_WIDTHS_KEY`, `pagesOrder`, `pagesWidths`; `pagesColumnHeads`, `pagesGrip`, `pagesOrderBy`, `pagesOrdered`, `pagesCompare`, `pagesCompareKeys`, `pagesIsBlank`, `pagesUrgent`, `pagesColumnKey`, `pagesGripStart`, `pagesFit`, `pagesSetWidth`, `pagesWidthOf`, `pagesStoredWidths`, `pagesSaveWidths`, `pagesApplyWidths`, `pagesResetWidths`, `pagesListOf`, `pagesReviewSpec`, `pagesOrderedGroups`. Changed: `pagesRow` (the `row-file` class), `pagesGroup` (`spec.heads` between heading and rows), `pagesWorkRows`, `pagesPausedRows`, `pagesOverview`, `pagesNeedsReview`, `pagesReminderSpecs`, `pagesReminders`, `pagesClientSpecs`, `pagesClients` (sort keys, the ordered specs and the header row), `pagesDraw` (apply the list's widths). |
| `app/renderer/shell.js` | `H_ATTRIBUTES` gains `aria-sort`; `shellEnabled` enables `reset_columns` with a clients folder; `MENU_ANSWERS.reset_columns`; `shellKey` hands a key on a column header to `pagesColumnKey`. |
| `app/renderer/shell.css` | The header row (`.col-table`, `.col-heads`, `.col-cell`, `.col-head`, `.col-arrow`, `.col-grip`), the lists' least width, the measuring state, `.row-file`, the household beside a heading; the forced-colours block. |
| `app/renderer/index.html` | One polite live region, `#page-say`. |
| `app/main.js` | `DEFAULT_MENU_WORDS.reset_columns`, the View menu's item. |
| `tracker/api.py` | `SCREEN["columns"]`, `MENU["reset_columns"]` (words only). |
| `pilot/wording-shell.tsv` | The new words' rows. |
| `docs/repo-map.curated.json` | `pages.js`'s note (headers, ordering, widths). |

**Lane 4b (sections 9-17):**

| File | What |
|---|---|
| `tracker/records.py` | `HouseholdInfo.related`, `HOUSEHOLD_FIELDS`, `HOUSEHOLD_EDITABLE`, `household_to_json`, `household_from_json`, new `related_from_json`, `household_problem`. |
| `tracker/store.py` | `SCHEMA_VERSION` 20 and its history note, `_IN_PLACE[19]`, `ADMISSION_VERSION` 3, `_LIST_COLUMNS`, `_household_cell`'s note, `_refuse_a_malformed_line` (the related list). |
| `tracker/api.py` | `RELATED_LABEL`, `ADD_RELATED_LABEL`, `RELATED_REFUSED`, `RELATED_UNKNOWN`; `_related_from_spec`, `_mirror_related`, `_cmd_edit_household`; `_household_payload` (`related`); `LINK_FEEDS`, `LINK_FED_BY`, `LINK_RELATED`, `_household_links`; `_list_payload` (`links`, `form`); `_firm_row` (`form`, files' `suggestion_short`); `_cmd_firm` (`links`); `SCREEN` (`find_placeholder`, `find_placeholder_files`, `linked`, `tabs`, `documents`, `paging`, `side`, `client_types` (words; the forms are `CLIENT_TYPE_FORMS`, `vocab.client_type_forms`), `columns.client_name`, `columns.sort_by`, `counts.one_file`, `icons.more_actions`, `icons.remove_filter`, `notices.under_construction`); the household words (`related_label`, `add_related`). |
| `app/renderer/pages.js` | New: `PAGES_PER_PAGE`, `PAGES_REASON_ICONS`, `PAGES_SECTIONS`, `pagesPageAt`, `pagesTab`, `pagesReasonPick`, `pagesClientType`, `pagesPanel`; `pagesLinkMark`, `pagesLinkMarkIn`, `pagesShowPanel`, `pagesPanelOpen`, `pagesClosePanel`, `pagesOpenRowLinks`, `pagesDetailCell`, `pagesStatusCell`, `pagesPaged`, `pagesFoot`, `pagesTurn`, `pagesPick`, `pagesTabs`, `pagesFileCount`, `pagesReasonCards`, `pagesReviewGroup`, `pagesTypeFilter`. Changed: `pagesNameCell`, `pagesRow`, `pagesActivate`, `pagesList`, `pagesGroup`, `pagesOrderBy`, `pagesWorkRows`, `pagesPausedRows`, `pagesOverview`, `pagesReviewSpec`, `pagesNeedsReview`, `pagesReminderSpecs`, `pagesReminders`, `pagesClientSpecs`, `pagesSwitch`, `pagesClients`, `pagesReturn`, `pagesDraw`, `pagesKey`, `PAGES_COLUMNS.clients`. |
| `app/renderer/shell.js` | New `shellSideWords`, `drawFindWords`; changed `shellVocabulary`, `drawSide`, `drawCounts`, `shellDraw`, `findOptions`, `drawFound`, `openFound`, `shellKey` (Escape closes the panel), the wiring (Client Types, Under Construction, Settings, a click outside the panel). |
| `app/renderer/tooltip.js` | New `showTipNow`. |
| `app/renderer/app.js` | Edit Household's related list: `editorRelated`, `renderEditorRelated`, `addEditorRelated`, `openHouseholdEditor`, `saveHousehold`, the dialog's model, the wiring. |
| `app/renderer/index.html` | The side panel (brand words, icons, the unbuilt items, Client Types, Workspace, Settings), the new icon symbols, Edit Household's related field. |
| `app/renderer/shell.css`, `pilot-ui.css` | The raised lists' rules and their forced-colours lines; `--st-linked`, `--bg-band`; `--size-col-name` 224px (P179). |
| `app/main.js` | No change: Settings answers through the existing `change_root`. |

**Owner tests (lane 4b):** `tests/test_records.py`, `tests/test_store.py`,
`tests/test_api.py`, `tests/test_shell.py`, `tests/test_shell_menu.py`; the
guards as above plus `tests/test_tripwire.py` and `tests/test_errors.py`.

**Owner tests:** `tests/test_shell.py` (the renderer's owner: the pages'
node probes and the stylesheet), `tests/test_shell_menu.py` (the template),
`tests/test_api.py` only if a vocabulary pin names every key. Guards:
`tests/test_layers.py`, `tests/test_single_source.py`,
`tests/test_repo_map.py`, `tests/test_vocab_report.py`.

New tests in `tests/test_shell.py`, named as their claims:
`test_the_four_firm_lists_draw_a_header_row_of_buttons_in_the_rows_columns`,
`test_a_header_orders_its_list_then_reverses_then_returns_to_the_usual_order`,
`test_status_orders_by_urgency_not_alphabetically`,
`test_dates_order_by_the_iso_date_and_blanks_go_last_both_ways`,
`test_needs_review_orders_files_in_each_group_and_groups_follow_their_first_file`,
`test_no_header_word_or_tooltip_says_sort`,
`test_a_column_width_is_clamped_saved_and_reset`,
`test_needs_review_moves_width_from_suggestion_to_reason_and_still_fits_1100px`,
`test_the_keyboard_resizes_a_focused_header_with_ctrl_shift_arrows_only`,
`test_the_header_row_and_grips_keep_the_rules_of_the_stylesheet`,
`test_file_rows_are_ordinary_weight_and_the_household_beside_a_heading_is_secondary`.

## 8. Docs made true in the same commit

- `pilot/SPEC-shell.md` 3.6 gains a pointer: "Column headers, ordering and
  widths: `pilot/SPEC-lists.md`." (a one-line note; nothing re-opened).
- `pilot/wording-shell.tsv`: the rows of section 2.
- `docs/repo-map.curated.json`: `pages.js`'s note; `repo-map.json/.md`
  regenerated.
- The runbook and README describe no screen layout at this level; the
  tester guide is emailed and versioned at the landing (P140). No line of
  either becomes untrue.

## 9. Linked households: the record (P141, P170, P172)

Jason, 2026-09-29: "both, lets go with 1 (make the icon a medium standout
color) have the linked to information appear when you click the tooltip."
"Linked" means both kinds (P141):

- **(a) Also Feeds** - a household whose `Drop files here` also feeds a
  return line in another household (`HouseholdInfo.feeds`, decision 132).
  It is shown on **both ends**: the feeding household says **Also Feeds**
  the other; the fed household says **Fed By** the feeder. Nothing new is
  stored for it; it is read from the feed list the record already holds.
- **(b) Related** - households a person marks as related in Edit
  Household. New.

### 9.1 The field (P170)

- `tracker/records.py`: `HouseholdInfo.related: tuple[str, ...] = ()` -
  household **folder names**, last field, default empty. `HOUSEHOLD_FIELDS`
  gains `("Related Households", "related")` and `HOUSEHOLD_EDITABLE` gains
  `"related"`. `household_to_json` writes it as a JSON list;
  `household_from_json` reads a list of names (a record written before
  this field reads as none: **backward compatible**).
- **Never inferred.** Only a person's save in Edit Household writes it;
  nothing compares two households and suggests one.
- **Symmetric.** Saving household A with B added writes B into A's record
  and A into B's, each under its own household lock, **one after the
  other, never two locks at once** (so no lock order is needed). Removing
  it from either side removes it from both. The screen reads **either**
  record (9.4), so a save that stopped between the two writes still shows
  the link on both ends, and saving either household again completes it.
  **How a half-finished save is repaired** (review M1): a save does not
  diff the household's old list against its new one; it rebuilds the link
  on both sides from what the person saved - every household the saved
  list names is made to name this one, and every household whose record
  names this one but is no longer in the list stops naming it. So re-saving
  the side that has the link writes it into the other, and removing it on
  the side that lacked it (the editor shows it there, from the other
  record) clears it from the side that had it. Each other household is
  read and written **inside its own lock** (review S1), so a change another
  writer makes there cannot be reverted. A household whose record already
  agrees is left alone - no lock, no write - so a save that changes only
  the contact never reaches a linked household. When another household's
  lock is held (its sort is running), the household edited is still saved
  and the reply exits 0 with the notice **"Link Pending: {household} Is
  Busy"** (Jason, P183: the lock may be something other than a sort) (`vocab.screen.notices.related_pending`); saving again after
  that sort writes the other side (re-check MUST-R1).
- **Only households that exist.** Edit Household offers the other
  households of the `list` reply; the command refuses a name that is not a
  household under the clients root (`RELATED_UNKNOWN`), the household
  itself, a blank, or a name twice (`RELATED_REFUSED`), each by name.
- **A note, not a route.** Nothing files, feeds, shares or hands over
  through a related link; decision 132's rule - only the drop point
  crosses households - is unchanged. The standing rules hold: no document
  is read, nothing is guessed, nothing is sent.

### 9.2 The store (schema 20, admission 3)

- `SCHEMA_VERSION` 19 -> 20: the household columns are the record's fields
  (`_column_types(HouseholdInfo)`), so `related` is the new column
  `engagements.household_related` (TEXT, a JSON list, in `_LIST_COLUMNS`).
- **In place** (`_IN_PLACE[19]`): `ALTER TABLE engagements ADD COLUMN
  "household_related" TEXT DEFAULT '[]'`. The default is what a rebuild
  writes for a row whose lines never name the field (the record's own
  default, `_new_engagement_defaults`), so `store check` finds nothing on
  an upgraded file, and the verdict cache is kept.
- **Admission 3** (`ADMISSION_VERSION`): `_refuse_a_malformed_line`
  refuses a `household_changed` line whose `related` is not a list of
  text, or names something that is not one folder name (`a_segment`), and
  `records.household_problem` holds each name to the text rule. It refuses
  something it used to admit, so every row judged by admission 2 is judged
  again at its next sync (decision 209); `tests/test_store.py`'s pin moves
  to 3.

### 9.3 The command (`edit-household`)

`tracker/api.py` `_cmd_edit_household`: JSON `related` is a list of
household names; `_related_from_spec` refuses what 9.1 refuses, then the
household is saved, then `_mirror_related` makes every other household's
record agree with the saved list (candidates from one listing of the
private tree with `registry.households_named`; each re-read and written
under its own `engagement_lock`); a list that is not a list of names is
refused with `RELATED_NOT_A_LIST`. The state's household
gains `related` (its own record's list). Edit Household (`app.js`,
`index.html`) gains a "Related Households" list with a picker of the other
households and an "Add Related Household" button, shaped like Also Feeds.

### 9.4 The reply fields (P172; additive, for lane 1's cache)

| Reply | Field | Shape |
|---|---|---|
| `firm` `returns[]` | `links` | `[{"name", "path", "kind"}]` - the linked households of the return's household |
| `firm` `returns[]` | `form` | the return's catalog id (`"1040"`, `"1120S"`, `"990"`, ...), `""` when not recorded |
| `list` `households[]` | `links` | as above |
| `list` `households[].returns[]` and `engagements[]` | `form` | as above |

`kind` is `feeds` (this household's drop folder also feeds that one),
`fed_by` (that household's drop folder feeds this one) or `related`
(either record names the other). A pair linked two ways has an entry per
kind. Worked out once per walk from the registry the command already
holds (`_household_links`), no extra disk read; `path` is `""` for a name
no household folder answers (a retired link), which the panel shows as
text, not a link. `form` is the record's own (`EngagementInfo.form`),
**never read from a folder name**; a blank form has no chip and belongs
to no Client Type (15.3).

**Owner test files:** `tests/test_records.py`, `tests/test_store.py`,
`tests/test_households.py`, `tests/test_api.py`.

## 10. Linked households: the mark and the panel (P141, P171)

- **Where:** beside the household name in each of the four firm lists -
  Overview's Client column, Needs Review's household under each return,
  Reminders' Client column and Clients' Client Name column. Not on the
  household, year or return pages (their own header already names the
  household, and Edit Household lists the links).
- **The icon:** `i-link` (two linked rings, drawn like the others, 16px,
  1.5px stroke, `currentColor`) in **`--st-linked`**, a violet from the
  firm's palette: not link blue, not one of the status colours (amber,
  blue, green, red), 5.56:1 or more on every surface it sits on, light
  and dark (16). In Windows High Contrast it is `ButtonText` on a button
  with a `CanvasText` edge: the shape carries it, never colour alone.
- **Words:** tooltip and accessible name "Linked Households"
  (`vocab.screen.linked.tip`). Kinds: "Also Feeds", "Fed By", "Related"
  (`vocab.screen.linked.feeds|fed_by|related`; owner question Q10).
- **Opening:** a click, or Enter/Space when the icon has focus, opens a
  small panel (`#link-panel`, `role="dialog"`, named "Linked Households")
  under the icon: one line per link, the household's name as an
  underlined link (`navigate_client`'s tooltip) and its kind in caption
  grey. Choosing a name goes to that client's page. **Escape** or a
  click outside closes it and returns focus to where it was opened from.
  A redraw of the page while it is open (a firm reply after a sort or a
  refresh) opens it again on the same household's mark; when that mark is
  gone, focus goes to the page's list, never lost (review S2). Every
  control in it shows the focus ring, the panel itself too when every name
  in it is retired (S3). The icon says `aria-haspopup="dialog"`, More
  Actions `aria-haspopup="menu"` (N4).
  Motion: a 150ms fade (`--dur`); none under reduced motion.
- **Inside a row list** (Overview, Reminders, Clients): a listbox is one
  Tab stop that moves by `aria-activedescendant` (SPEC-shell 3.6), so the
  icon there is a button with `tabindex="-1"` for the pointer; the row's
  `aria-description` gains "Linked Households", and **Space** on the
  active row opens its panel (Enter still runs the row's step). On
  **Needs Review** the icon sits in a group heading, outside any list,
  and is a normal Tab stop.

## 11. Overview raised (P145)

- **Summary cards:** the three counts ("Need a Person", "Waiting on
  Clients", "Complete", unchanged words and meanings) each in a raised
  card (`--bg-raised`, 1px `--border`, `--radius`), the number in the
  figure type, the label in caption, and a small icon in the card's
  status colour (`i-alert` amber, `i-clock` blue, `i-done` green).
- **Title row:** "Work Waiting" (H2) with its count as secondary caption
  text, and at its right three **filter tabs** - "All", "Need You ({n})",
  "Waiting ({n})" - buttons with `aria-pressed`, in the switch's look. A
  tab narrows the whole list, then the chosen order and the pages apply.
  The tab is forgotten when Overview is left.
- **The list:** muted Title Case column headers (lane 4's), row dividers,
  subtle alternating shading (`--bg-band` on every second row), a form
  chip ("1040", "1120S", "990", "1041", "1065", "1120") before each
  return's name (caption, `--bg-hover` chip, `--text-secondary`), the
  status as a **pill with a dot** that keeps the count ("2 Need You") in
  the app's colours on the notice tints (`--warn-bg` / `--info-bg` /
  `--ok-bg`).
- **Not built:** monospace anywhere (digits use `tabular-nums`),
  checkboxes, "Open" as a status, a version badge in the title, a
  subtitle, "Complete Today", "active cases".

## 12. Needs Review raised (P149)

- **Title row:** "Needs Review" (H2) with the page's count as secondary
  text ("13 Files", "1 File"), no alarm badge, no subtitle.
- **Reason cards:** one raised card per reason present, its short reason
  word, its icon and its count, each a **filter** (`aria-pressed`); an
  "All" card clears. Choosing one narrows the whole list, then order and
  pages apply; forgotten when the page is left.
- **Each return is a card group** (`--bg-raised`, 1px `--border`,
  `--radius`, 16px apart): a folder icon; the return's name (the H2 link,
  unchanged); the household as the small grey secondary link with the
  P141 icon when linked; the count "1 Document" / "{n} Documents"; and a
  visible **More Actions** icon button (`i-more`, tooltip "More Actions")
  that opens **the same native right-click menu** as the heading (the
  `return` template, acting on that return; no new action). The heading
  is right-clickable too.
- **File rows** under the heading: a file icon, the file link (regular
  weight), the request it most likely is as a **muted chip** (its short
  title, the full title as its tooltip), the **reason as a pill**, and
  the date.
- **Reason pills are all the Need You amber**, told apart by a small icon
  per reason family and by their words: can't tell (`i-question`), names
  (`i-person`), the file itself (`i-file`), emails and zips (`i-box`),
  moved or touched by a person (`i-hand`), anything else (`i-alert`).
  Colour keeps one meaning across the app.
- **Not built:** a brand change, extra pages, "Re-run Checks" (ruling 28,
  P113), "Critical Only", a subtitle.

## 13. Search (P173)

The bar's one search box stays (SPEC-shell 8.2) and always searches the
whole practice, never only the page shown. Its placeholder is **"Search
Clients and Returns"** (`vocab.screen.find_placeholder`); on Needs Review
it is **"Search Files, Clients and Returns"**
(`find_placeholder_files`, owner question Q12) and the box also finds the
waiting files by name - files first there, each noted with its return and
year; choosing one opens Check on it. Up to eight options, as before.

## 14. Page buttons (P152, P174)

- Overview, Needs Review, Reminders and Clients show a footer,
  **"Showing {from}-{to} of {total} {noun}"** (nouns Returns, Files,
  Drafts, Clients), with **Previous** and **Next** buttons (disabled at
  the ends). Digits are `tabular-nums`.
- **50 rows per page** (`PAGES_PER_PAGE`; owner question Q11).
- **Order, tabs, reason cards and the Clients type filter act on the
  whole list first**; pages only divide the result. Any change of them
  returns to page 1.
- **Needs Review pages by whole return groups**: a page takes groups
  while their files stay within 50 (a group larger than 50 is a page of
  its own); the footer counts files.
- The **column header row sticks** to the top of the page area while it
  scrolls.
- The page number is **not remembered**: leaving the page and coming
  back starts at page 1.
- Previous/Next keep keyboard focus on the button pressed (or the other
  one when it becomes disabled) and scroll the page to its top.

## 15. The side panel and Clients (P153, P154)

Since P196 the screen calls Clients **Households**, its name column
**Household Name** and the Client Types **Taxpayer Types**; the keys and
code names below are unchanged. See `SPEC-taxpayer-words.md`.

### 15.1 The panel

- **Brand band** (`--brand`, both themes; P179): the JP logo, whose
  wordmark already reads "J Park & Associates", and under it **"Tax
  Document Console"** (caption, 600) in `--window-light`; the words **"J
  Park & Associates"** are in the band for a screen reader
  (`visually-hidden`), because beside the 133px-wide wordmark they were cut
  to "J Park &..." (owner question Q14). The band grows to its content
  (about 64px, SPEC-shell 3.3 said 48px). New words name the app "Tax
  Document Console" (P155); nothing existing is renamed and no version
  number changes (P140).
- **Pages:** Overview, Needs Review, Reminders, Clients, each with an
  icon, its count badge (Needs Review files waiting, **amber**:
  `--st-attention` on `--warn-bg`; Reminders drafts ready, neutral:
  `--text-secondary` on `--bg-pressed`), the current page highlighted as
  today (`aria-current="page"`, the pill), Ctrl+1..4 kept.
- **Under Construction** (P154): "Ready to Sign (Under Construction)" and
  "Family Entities (Under Construction)" among the pages; section
  **"Workspace"**: "Personal Trusts (Under Construction)", "Corporate
  Entities (Under Construction)", "Portal Settings (Under Construction)".
  Each muted but readable (`--text-secondary`, 7.58:1 on `--bg-nav`),
  keyboard-reachable, `aria-disabled="true"`, tooltip "Under
  Construction". Choosing one shows a short **"Under Construction"**
  toast and opens nothing, calls no engine command.
- **Client Types** (section heading): Individuals (1040), Businesses
  (1120, 1120S, 1065), Trusts & Estates (1041), Nonprofits (990); the
  forms are each item's tooltip. Each opens Clients filtered to the
  households with a return of that form group (15.3).
- **Settings** at the bottom opens the settings the app already has - the
  settings page of File › Change Clients Folder (the folder, the firm's
  name and phone) - through the same menu answer (`change_root`). No
  user profile: the last-sort line and the version badge keep the corner.
- **Height:** the item list scrolls (`overflow-y: auto`); at a 700px
  window nothing is cut.

### 15.2 Clients

Headers **Client Name / Returns / Status** (Title Case; ordering and
resizing as lane 4 built), row dividers and banding, the Work Waiting tab
with its count beside "All", status pills in Overview's style, the page
footer (14), the P141 icon beside a linked name, and the search
placeholder of 13. Names stay underlined links. The name column's header
word is "Client Name" on Clients only (`columns.client_name`).

### 15.3 Client Types filter

A type is shown on Clients as a **removable chip** (the type's word and a
dismiss icon, tooltip "Remove Filter"); both tabs are narrowed by it. A
household belongs to a type when one of its returns' recorded `form` is
in the type's forms; a return with no recorded form belongs to none (the
tracker never reads a form out of a folder name). The type is the
renderer's filter only: nothing is written and no command is called. It
is forgotten when Clients is left for another firm page.

## 16. Tokens and contrast (P177)

New tokens (in `pilot-ui.css`'s two `:root` blocks):

| Token | Light | Dark | Use |
|---|---|---|---|
| `--st-linked` | `#7c3aad` | `#c4a0f0` | the link icon |
| `--bg-band` | `#f8fafc` | `#1f232a` | every second row of a firm list |

Every new pair, computed from the tokens (WCAG 2.2; text 4.5:1, non-text
3:1):

| Pair | Needs | Light | Dark |
|---|---|---|---|
| `--st-linked` on `--bg-page` (icon) | 3 | 6.85 | 7.66 |
| `--st-linked` on `--bg-hover` | 3 | 6.25 | 6.62 |
| `--st-linked` on `--bg-selected` | 3 | 5.66 | 6.11 |
| `--st-linked` on `--bg-band` | 3 | 6.55 | 7.23 |
| `--st-linked` on `--bg-raised` (Needs Review card) | 3 | 6.85 | 6.87 |
| `--st-linked` on `--bg-pressed` (the icon's own hover) | 3 | 5.56 | 5.84 |
| `--st-attention` on `--warn-bg` (Need You pill, reason pill, amber badge) | 4.5 | 7.52 | 8.05 |
| `--st-waiting` on `--info-bg` (Waiting pill) | 4.5 | 9.52 | 7.85 |
| `--st-done` on `--ok-bg` (Complete pill) | 4.5 | 7.25 | 9.07 |
| `--st-attention` on `--bg-raised` (card icon) | 3 | 7.80 | 8.47 |
| `--st-waiting` on `--bg-raised` (card icon) | 3 | 10.36 | 8.03 |
| `--st-done` on `--bg-raised` (card icon) | 3 | 7.63 | 8.78 |
| `--text` on `--bg-band` | 4.5 | 17.06 | 13.30 |
| `--text-secondary` on `--bg-band` (detail, chips) | 4.5 | 7.91 | 8.84 |
| `--text-caption` on `--bg-band` (date) | 4.5 | 5.68 | 6.37 |
| `--link` on `--bg-band` | 4.5 | 12.11 | 8.85 |
| `--link` on `--bg-raised` (Needs Review card links) | 4.5 | 12.67 | 8.41 |
| `--focus` on `--bg-band` (focus ring) | 3 | 4.94 | 7.17 |
| `--text-secondary` on `--bg-nav` (Under Construction, section words) | 4.5 | 7.58 | 10.05 |
| `--text-secondary` on `--bg-nav-hover` | 4.5 | 6.97 | 8.84 |
| `--text-secondary` on `--bg-pressed` (neutral badge, chips) | 4.5 | 6.71 | 7.13 |
| `--window-light` on `--brand` (brand words) | 4.5 | 12.67 | 12.67 |

The row band against the page is decoration, not a cue: the row dividers
and the words carry the rows. **Windows High Contrast:** pills, chips,
cards and badges take a `CanvasText` edge on `Canvas`; shadings go; the
link icon is `ButtonText` on a `CanvasText`-edged button; section icons
and words carry the sections; focus stays `CanvasText`.

**1100px (ruling 27):** measured on this PC in Segoe UI Variable (the
app's face) with `PIL.ImageFont` from `C:\Windows\Fonts\SegUIVar.ttf`:
at the pills' 12px weight 600, "Looks Like Wrong Document" is 158px,
"Names Another Household" 149px, "Claimed by Two Requests" 140px, "Came
in Email or Zip" 113px; with the pill's 32px of padding, dot or icon and
gap, the longest is 191px, inside Needs Review's 200px Reason column, so
every reason shows whole at 1100px and Q9 no longer arises. **P179:** the
name column's usual least width is 224px (was 240px): Windows' classic
scrollbar takes 17px of the 860px main area, and at 240px the lists
(856px) scrolled sideways; at 224px the header row needs 840px and a
Needs Review card 842px, inside 843px. Checked in the harness at 1100 x
700, light and dark: no sideways scroll. "Two Years
Open; Sorting Paused" (176px at 12px) wraps in its row, as ruling 21
already allows. The rendered
look is the Windows check's to confirm.

## 17. The keyboard's status tooltip (P178)

Rows move by `aria-activedescendant`, so a row made active by the
keyboard (Up/Down, Home/End, PageUp/PageDown, or focus arriving on the
list) shows its status cell's tooltip at once - the full words, for
example "Came in Email or Zip" - through `tooltip.js`'s `showTipNow`,
placed below the status cell; moving on, a click or leaving the list
hides it. A pointer still shows it after 300ms, and only when the words
are cut.

## 18. Open for Jason

Each is answerable by a letter; the recommendation is built meanwhile.

| # | Question | Recommendation |
|---|---|---|
| Q1 | Header tooltip word: A) "Order by Status"; B) "Arrange by Status"; C) "Sort by Status". | **Decided C** (Jason, 2026-09-30, P180: "1. sort by"); built in lane 4b |
| Q2 | Headers on which lists: A) the four firm lists only; B) also the household and year pages; C) also the return page's sections. | **Decided A** (Jason, 2026-09-30, P180: "a for the rest") |
| Q3 | A chosen order is kept: A) while the app is open; B) across restarts; C) only until you leave the page. | **Decided A** (Jason, 2026-09-30, P180: "a for the rest") |
| Q4 | Column widths are kept: A) on this PC across restarts, with View › Reset Column Widths; B) only while the app is open. | **Decided A** (Jason, 2026-09-30, P180: "a for the rest") |
| Q5 | The household beside a Needs Review heading: A) small grey underlined link; B) small blue underlined link. | **Decided A** (Jason, 2026-09-30, P180: "a for the rest") |
| Q6 | A band behind each Needs Review heading: A) no band; B) a light band. | **Decided A** (Jason, 2026-09-30, P180: "a for the rest") |
| Q7 | The Return column orders by: A) the whole name as shown, form first; B) the name without its form ("John & Jane Smith"). | **Decided A** (Jason, 2026-09-30, P180: "a for the rest") |
| Q9 | If a Needs Review reason is still cut at 200px on Windows: A) shorter reason words (lane 2's job); B) a wider Reason column, taken from the Return column (File names then cut sooner). | **Decided A** (Jason, 2026-09-30, P180: "a for the rest") |
| Q8 | The return page's three sections: A) a coloured bar and icon on the heading, a tinted count badge and a matching edge down the rows; B) a tinted band behind each heading; C) the icon alone. | **A** (built in lane 4b, P176) |
| Q10 | The kinds in the Linked Households panel: A) "Also Feeds" / "Fed By" / "Related"; B) "Feeds" / "Fed From" / "Related"; C) one word for all, "Linked". | **Decided A** (Jason, 2026-09-30, P182) |
| Q11 | Rows per page on the four firm lists: A) 50; B) 100; C) 25. | **Decided A** (Jason, 2026-09-30, P182) |
| Q12 | The search box's words on Needs Review: A) "Search Files, Clients and Returns"; B) "Search Files and Clients"; C) the same "Search Clients and Returns" as every page. | **Decided A** (Jason, 2026-09-30, P182) |
| Q13 | If a reason word is still cut at 1100px in the Windows check (16 measured none cut): A) shorter words (lane 2's job); B) a wider default Reason column. | **Decided A** (Jason, 2026-09-30, P182) |
| Q14 | The side panel's brand band: A) the logo (its wordmark is the firm's name) with "Tax Document Console" under it, the firm's name as words for a screen reader; B) a smaller logo with "J Park & Associates" and "Tax Document Console" written beside it (the wordmark would need a JP-only mark, which the firm does not have as a file yet). | **Decided A** (Jason, 2026-09-30, P182) |
