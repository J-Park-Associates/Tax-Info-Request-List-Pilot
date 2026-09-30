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
  which way. The word is **"Order"**, never "Sort": in this app "Sort" already
  means filing documents (the Sort icon, "Sort Failed", "Sorted 11:14 PM").
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
| `columns.order_by` | Order by {column} | each header's tooltip, e.g. "Order by Status" |
| `columns.width` | {column} Width {n} | said to a screen reader after a keyboard resize, e.g. "Status Width 176" |
| `vocab.menu.reset_columns` (`MENU`) | Reset Column Widths | View menu |

"Client" is the household's word on screen already ("Navigate to Client"). The
header is a button whose name is its word; the tooltip adds "Order by".

**Owner question Q1** (built: A): the header tooltip says
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
  | name (Return, File, Client) | 160 | 640 | 240 (its least; it takes the space the others leave) |
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
- **The 1100px window:** the usual widths still add to 856 of the 860px main
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

## 6. The three sections of a return's page (P136; owner question Q8)

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

## 7. Docs made true in the same commit

- `pilot/SPEC-shell.md` 3.6 gains a pointer: "Column headers, ordering and
  widths: `pilot/SPEC-lists.md`." (a one-line note; nothing re-opened).
- `pilot/wording-shell.tsv`: the rows of section 2.
- `docs/repo-map.curated.json`: `pages.js`'s note; `repo-map.json/.md`
  regenerated.
- The runbook and README describe no screen layout at this level; the
  tester guide is emailed and versioned at the landing (P140). No line of
  either becomes untrue.

## 8. Open for Jason

Each is answerable by a letter; the recommendation is built meanwhile.

| # | Question | Recommendation |
|---|---|---|
| Q1 | Header tooltip word: A) "Order by Status"; B) "Arrange by Status"; C) "Sort by Status". | **A** |
| Q2 | Headers on which lists: A) the four firm lists only; B) also the household and year pages; C) also the return page's sections. | **A** |
| Q3 | A chosen order is kept: A) while the app is open; B) across restarts; C) only until you leave the page. | **A** |
| Q4 | Column widths are kept: A) on this PC across restarts, with View › Reset Column Widths; B) only while the app is open. | **A** |
| Q5 | The household beside a Needs Review heading: A) small grey underlined link; B) small blue underlined link. | **A** |
| Q6 | A band behind each Needs Review heading: A) no band; B) a light band. | **A** |
| Q7 | The Return column orders by: A) the whole name as shown, form first; B) the name without its form ("John & Jane Smith"). | **A** |
| Q9 | If a Needs Review reason is still cut at 200px on Windows: A) shorter reason words (lane 2's job); B) a wider Reason column, taken from the Return column (File names then cut sooner). | **A** (words that fit keep every column readable at 1100px) |
