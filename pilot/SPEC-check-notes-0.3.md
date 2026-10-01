# Pilot 0.3 - the list and dialog notes from the Windows check - SPEC

Decision P199 (`pilot/DECISIONS.md`). Sources: `pilot/wintest/RESULTS-0.3.md`
(L4, N2, N3, N5, the "Nothing Done" row) and `pilot/handoffs/wincheck-0.3.md`,
Left items 3 and 5. Written 2026-10-01 by the P199 builder (Opus 5.5), branch
`claude/check-notes` from `4534b30`. The columns are Tax Year, Taxpayer, Form
Type, Status, Date (`pilot/SPEC-firm-columns.md`, P194-P196). No engine
change, no version number.

## What staff will notice (plain English)

- On Overview, Needs Review, Reminders and Households, the **Date** sits right
  after the Status, under its header's word, at any window size. The space
  left over on a wide window is blank at the right, as in File Explorer.
- **Widening a column** by dragging its header's right edge to the right
  makes that column wider and moves the columns after it to the right. It no
  longer takes the room from the column on its left.
- The **order chosen by clicking a header** is still there after the app is
  restarted, as column widths already are (on this PC, list by list).
- When a Sort cannot reach the household's folder, the household's **other
  returns** each get a line that **begins with a bullet** and names the
  return the way the lists do: "• 2024 John A. Smith 1040: Sort Failed:
  Folder Not Found".
- The schedule dialog shows **one clock style**: "Next run: today at 10:30
  PM" beside "First Run At 6:30 AM", not "22:30".
- A Sort that finds **nothing to do** now says "Nothing to Sort" (Q1 below;
  built as recommended). If a file is still arriving in Drop files here it
  says "Nothing Done: 1 Still Syncing." A Sort that filed into **another**
  return of the household did something and never says it (the screen
  review's M1).

## 1. L4: the Date column sits too far to the right

**Cause.** The Taxpayer column (and the name column on Needs Review and
Households) was `minmax(224px, 1fr)`: it took every pixel of the window's
slack, so the Date was pushed to the window's right edge, and the date was
right-aligned in its 144px cell on top of that (measured: at 1100px the date
text began 141px after the Status's right edge; at 1920px, 1617px into the
list).

**Ruling (the rule).** Every column of a firm list is exactly its usual or
chosen width, side by side from the list's 32px padding; no column takes the
slack, and what is left is blank after the last column (File Explorer's
Details view). The date and the Date header's word start at their column's
left edge. So the Date always starts 16px (one column gap) after the
Status's right edge: at the usual widths 32 + 80 + 224 + 96 + 160 + 4 x 16 =
**656px** into the list, at 1100px and at every width above it. A return's
own page (household, year and return pages, no headers) is unchanged: its
name column still fills and its date stays at the end.

Reason: a reader looks for a row's date beside its status; the old layout
put it a window's width away on a maximised window. File Explorer is the
convention staff already know (Fluent 2: Windows behaviour). Trade-off: on a
wide window long taxpayer or file names keep their usual 224px (names wrap,
file names keep "..." and their tooltip); widen the column once and the
width is kept.

**Files.** `app/renderer/shell.css` 535-565: the five-column rule's taxpayer
track becomes `var(--size-col-taxpayer)`; a new rule gives Needs Review's and
Households' rows, header row and loading rows fixed tracks; a new rule
starts `.row-end` at the column's left on the four lists; the
`.col-cell[data-cell="end"] { text-align: right; }` rule is removed (the
header word starts left). `app/renderer/pages.js` 81-84: the comment on
`PAGES_WIDTHS` says the new rule.

**Owning tests.** `tests/test_shell.py`:
`test_a_firm_lists_columns_are_their_own_widths_so_the_date_sits_after_the_status`
(new), `test_overview_and_reminders_say_tax_year_taxpayer_and_form_type_once_each_in_their_own_columns`
(its grid line), `test_the_four_lists_and_a_needs_review_card_fit_1100px_beside_a_windows_scrollbar`,
`test_the_header_row_and_grips_keep_the_rules_of_the_stylesheet` (unchanged, still pass).

**1100px.** The five usual widths, four gaps and the padding are still 832px
of the 843px beside Windows' scrollbar (P179): no sideways scroll.

## 2. N2a: widening a column grew it to the left

**Cause.** The same flexible column: widening Form Type (or, before P194,
Client) took its pixels from the flexible column on its left, so the
widened column's left edge moved left and its right edge stayed put.

**Ruling.** Fixed by section 1's rule, with no script change: the grip's
drag (`pagesGripStart`) already sets the column's own width from where the
drag began, so with fixed tracks the dragged edge follows the pointer and
every column after it moves right; past the window the page area scrolls
sideways, header and rows together (SPEC-lists 4, unchanged). The keyboard
(Ctrl+Shift+Right and Left on a focused header, 16px a step, said to a
screen reader), double-click to fit, the visible focus ring, the High
Contrast rules and the motion (`--dur`, 150-250ms) are unchanged.

Measured in Chromium with the real stylesheets (section 8): widening Form
Type by 64px moved Status and Date 64px right; before, they did not move.

## 3. N2b: the chosen order reset on restart

**Cause.** By design: P139 kept an order only while the app was open
(`const pagesOrder = {}` in memory), widths in `localStorage`.

**Ruling (Jason, 2026-10-01, P199; replaces P139's order half).** The order
each list was left in is kept on this PC per list, the way widths are: in
the renderer's `localStorage` under `tracker.order` (never the record or the
data folder). It is read once (`pagesStoredOrder`) and written on each
header press (`pagesSaveOrder`); the third press, back to the usual order,
forgets that list's entry. Only an order a header can give is read back - a
list the app draws, one of its columns that has a word, a direction of 1 or
-1; anything else (not JSON, a column the list no longer has such as the
old Return, Households' wordless end column, any other direction) leaves
that list in its usual order and says nothing. Storage that refuses the
write keeps the order while the app is open. View > Reset Column Widths
still does not touch the order (its name says widths); a third press of the
header is the way back.

**Files.** `app/renderer/pages.js`: 92 (`PAGES_ORDER_KEY`), 97
(`let pagesOrder = null`), `pagesOrdered` 760, `pagesOrderBy` 769-774,
`pagesColumnHeads` 789, new `pagesStoredOrder` / `pagesSaveOrder` 866-898,
`pagesOrderedGroups` 1163.

**Owning tests.** `tests/test_shell.py`:
`test_the_order_chosen_by_a_header_is_kept_on_this_pc_across_a_restart`
(new), `test_a_header_orders_its_list_then_reverses_then_returns_to_the_usual_order`
and the other ordering tests (unchanged); `PAGES_CONSTS` and
`COLUMN_FUNCTIONS` name the new constant and functions.

## 4. N3: step 13's extra lines had no bullet

**Cause.** `scanSummary` writes each other return's line as "• {label}:
...", but `passEnded` stripped the bullet when it split the answer into one
notice per line (`line.replace(/^•\s*/, "")`).

**Ruling.** `passEnded` keeps a line's bullet (`app/renderer/app.js`
2314-2320). The return is said by its fields, as the lists say it since
P194-P196 - the year, the taxpayer and the form, each once, in a Needs
Review heading's order - by a new `sortReturnSaid` (2127-2137): "• 2024 John
A. Smith 1040: Sort Failed: Folder Not Found". The household is not said:
a Sort's answer shows only on that household's own pages (P131). The same
words lead the asked return's first line when another return is shown
("2025 John A. Smith 1040: Sort Failed: ..."). A return the list does not
hold is said by its label, never guessed; a return whose name does not
begin with its form keeps its whole name (`pagesTaxpayer`, P172).
`pilot/wintest/PROMPT-shell.md` step 13 is reworded to say so.

**Owning tests.** `tests/test_shell.py`:
`test_another_returns_line_keeps_its_bullet_and_says_the_return_by_its_fields`
(new), `test_the_sorts_answer_is_built_line_by_line_from_the_pass` (its
second line now carries the bullet),
`test_a_failed_or_locked_household_sort_draws_no_engine_sentence_and_no_path`
(lifts the helper).

## 5. N5: two clock styles in the schedule dialog

**Cause.** "First Run At" is an `<input type="time">`, which Windows draws
in this PC's style ("6:30 AM"); "Next run: today at 22:30" is the engine's
sentence (`tracker/scheduling.py` `next_run`, `%H:%M`), shown as it came.

**Ruling.** The app's style is this PC's own time style through
`toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })` - the side
panel's "Next Sort" (`pages.js` `pagesTime`) and the last-sort line
(`shell.js`) already use it, "10:30 PM" on the office's US-English Windows.
A new `scheduleClock` (`app/renderer/app.js` 2022-2029) rewrites the HH:MM
that ends the engine's sentence through `pagesTime`; the dialog (2063) and
the toast after Save (2091) use it. The engine's sentence is unchanged
(`_next_sort` in `tracker/api.py` reads its last five characters, and
`tests/test_scheduling.py` pins it). A sentence that does not end in a time
is left whole. The time in the sentence is drawn with
`font-variant-numeric: tabular-nums`, as every date and time is: `#sc-next`
joins the tabular list in `app/renderer/shell.css` line 21 (the screen
review's N4).

**Owning test.** `tests/test_shell.py`
`test_the_schedule_dialog_says_its_next_run_in_the_apps_clock_style` (new;
it also holds `#sc-next` in the tabular list).

## 6. A household Sort that does nothing (owner question Q1)

**Cause.** P131: a good Sort says nothing (its rows show it). A Sort that
filed nothing, sent nothing to review and met no problem is "good", so it
said nothing at all, and a person could not tell it ran.

**Q1 (for Jason; answer by letter).** What should a Sort that finds nothing
to do say?

- **A (recommended, built):** a short notice, **"Nothing to Sort"**, as a
  skipped return's Sort says "Nothing Done" (P134, P169). It is that Sort's
  answer (P131): shown on the household's pages, replaced by its next Sort,
  gone on F5 or when dismissed.
- B: a toast that goes by itself.
- C: nothing, as now.

Built as A, for every Sort of the household (the household, year or return
page: each Sort is the household's pass). When a file is still arriving in
Drop files here (the pass counted it as syncing), nothing was sorted but
something waits, so it says **"Nothing Done: 1 Still Syncing."** - the
approved "Nothing Done: {why}." with the pass line's own "{n} Still
Syncing" (no new pattern; five words). A Sort that filed, sent to review,
could not sort a file, warned, was stopped, or has a line about another
return is unchanged.

**Every return of the pass decides, not the asked one alone** (the screen
review's M1, accepted in `pilot/reviews/lanes-rulings.md`). The pass sorts
the household's one inbox across every open return and counts per return,
so a Sort pressed while the 1065 is shown can file five documents into the
1040. The notice is said only when no return in the pass filed, sent to
review, met a file it could not sort or was stopped; the syncing count is
the pass's, summed over its returns.

**Files.** `tracker/api.py` 494-501 (`SCAN_NOTHING_TO_SORT`, its comment) and
1892-1893 (`vocab.scan.nothing_to_sort`); `app/renderer/app.js` 2168-2182
(`scanSummary`).

**Owning tests.** `tests/test_shell.py`
`test_a_sort_that_finds_nothing_to_do_says_nothing_to_sort` (new; Title Case
and five words) and
`test_nothing_to_sort_is_said_only_when_no_return_of_the_household_received_anything`
(M1: another return filing, parking, failing a file or stopping keeps it
silent); `tests/test_single_source.py`
`test_every_word_a_scan_reply_is_said_in_is_the_apis` (the new key is used
as `words.nothing_to_sort`); `tests/test_api.py`
`test_every_drawn_word_the_vocabulary_carries_is_in_title_case`.

## 7. Words, docs and map

| Key | Words | Where |
|---|---|---|
| `scan.nothing_to_sort` (new) | Nothing to Sort | A Sort's answer, on the household's pages (Q1 A) |
| `scan.nothing_done` with `scan.syncing` (existing) | Nothing Done: {n} Still Syncing. | The same, when a file is still arriving |

Rows added to `pilot/wording-shell.tsv`. Also made true in this commit:
`pilot/SPEC-lists.md` section 4 (the fill rule and the order's memory point
here), `pilot/SPEC-firm-columns.md` item 13 (the taxpayer no longer takes
what the others leave), `docs/runbook.md` (the column order is kept beside
the widths), `pilot/wintest/PROMPT-shell.md` step 13, `pilot/DECISIONS.md`
P199 (and P139 marked as revised for the order), the curated map notes for
`app/renderer/pages.js` and `app/renderer/app.js`, and the map.

## 8. The 1100px proof

The real `style.css`, `pilot-ui.css`, `shell.css` and `pilot-style.css`,
before (HEAD `4534b30`) and after, on a static Overview of two rows in
Chromium (the session's browser pane; a 240px side panel; no scrollbar):

| Window | Status (px into the list) | Date text, before | Date text, after |
|---|---|---|---|
| 1100 | 480-640 (before 508-668) | 797 | **656** |
| 1920 | 480-640 (before 1328-1488) | 1617 | **656** |
| 1920, Form Type widened 96 -> 160 | after: 544-704 | before: did not move | **720** |
| 1100, Taxpayer widened 224 -> 320 | after: 576-736 | - | **752** (page scrolls sideways) |

Not measured on Windows itself (Segoe UI, the classic scrollbar): the
arithmetic is the stylesheet's, and the next Windows check looks at it.

## Tests this SPEC runs

Each its own process, under Python 3.11 (floor) and `C:\Python314`:
`tests/test_shell.py`, `tests/test_single_source.py`, `tests/test_layers.py`,
`tests/test_repo_map.py`, and in `tests/test_api.py` only
`test_every_drawn_word_the_vocabulary_carries_is_in_title_case` (one new
word). No error wording changes, so `test_errors.py` does not run. Then
`python -m ruff check .` and `python tools/repo_map.py check`.
