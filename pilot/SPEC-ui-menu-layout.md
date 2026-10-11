# Pilot 0.3 - four layout picks from the UI menu: Compact Rows, a flat Needs Review, the notices panel, the household card - SPEC

Status: written 2026-10-11 on top of `c718e37` (P264's no-brainers, N1-N12,
landed), from Jason's answers to `pilot/SPEC-ui-polish.md` section 2:
**P271** (Q7b), **P272** (Q8b), **P273** (Q9c) and **P275** (Q11b) in
`pilot/DECISIONS.md`. The other answers (P265-P270, P274, P276-P280) are
other jobs; section 7 says where they touch this one.

**What changes, in plain English.** Four things a person at the office PC
will see:

1. **View › Compact Rows.** A tick in the View menu makes every list's rows
   32px instead of 40px, so about a quarter more rows fit on the screen.
   It is remembered on that PC only; a new install starts Comfortable.
2. **Needs Review is one plain list.** The boxes around each return go, and
   so does the grey "2 Documents" pill. Each return is a heading (as on a
   return's own page) with its household and its count beside it, and its
   files under it. The "…" button stays, beside the count.
3. **Notices sit in a panel at the right.** In a window 1388px wide or
   wider (the app opens at 1400), the notices stack in a 288px panel to the
   right of the page instead of pushing the page down. The panel is there
   only while there is a notice. In a narrower window they go back above the
   page, as today.
4. **The household page has a card.** The household's contact, who it is
   shared with and whether its inbox link is saved sit in a card beside the
   list of returns, and each return's status sits right after its name
   instead of at the far right. The year headings stay.

Nothing here changes what the engine does, what a record holds, or a
standing rule. No generative AI reads a client document; nothing is sent;
no network call is added; no test reads a real folder; the harness's names
are made up, and no client name appears in this SPEC, a test or a
screenshot.

---

## 0. Order, and why this order

| # | Item | Decision | Builds on |
|---|---|---|---|
| L1 | Compact Rows | P271 | N1-N12 as landed |
| L2 | Needs Review, one flat list | P272 | L1: its rows are the one row, so they follow the density with no rule of their own |
| L3 | The notices panel | P273 | L2: the panel's width is chosen so every firm list, Needs Review's flat one included, keeps the 860px it is designed for |
| L4 | The household card | P275 | L3: the card sits beside the list only when the page (less the panel, when it shows) is wide enough, so the panel must exist first |

Each item below gives: what a person sees; the exact behaviour (markup,
CSS, JS) in the software's own words, with the file and function to
change; keyboard and focus; both themes; the sentences of `SPEC-shell.md`
and `SPEC-lists.md` it amends; the tests (new ones as named claims, and the
existing pins that change); and why.

Values are on the 4px grid (SPEC-shell 10.3). Every new size is a
`--size-*` token in the light `:root` block of `pilot-ui.css` (sizes are not
repeated in the dark block); every new rule is in `shell.css`, uses tokens
only, and declares any `display` under `:not(.hidden)`, `:not([hidden])` or
`:not(:empty)`, as `tests/test_shell.py` holds.

New tokens (all multiples of 4):

| Token | Value | For |
|---|---|---|
| `--size-row-compact` | 32px | a row under Compact Rows (L1) |
| `--size-notices` | 288px | the notices panel (L3) |
| `--size-card` | 288px | the household card beside the returns (L4) |

---

## 1. L1 - View › Compact Rows (P271)

### 1.1 What a person sees

The View menu gains **Compact Rows**, a check item, between **Reset Column
Widths** and **Show Under Construction**. Unticked (the default) the lists
are as today. Ticked, every row of every list page and of the request list
editor is 32px instead of 40px. Nothing else moves: the same columns, the
same widths, the same words.

### 1.2 Behaviour

**The setting is kept per PC exactly as P197's Show Under Construction is**
(`shell.js` `SOON_KEY`, `shellReadSoon`, `drawSoon`, `shellToggleSoon`;
`app.js` `storeRead` / `storeWrite`): the window's own storage, never
`settings.json`, never a record, never the engine.

- `shell.js`: a new constant `ROWS_KEY = "tracker.rows"` beside `SOON_KEY`;
  a module variable `shellCompact = null`.
- `shellReadCompact()`: as `shellReadSoon`, returns
  `storeRead(ROWS_KEY) === "compact"`, read once. Only the exact word
  `compact` is compact; any other stored value, and storage that cannot be
  read, is Comfortable (the new install's default).
- `drawCompact()`: `document.documentElement.classList.toggle("rows-compact",
  shellReadCompact())`. Called once at load as a top-level statement
  (`drawCompact();`, next to the existing top-level `drawSoon();`), so a
  stored choice applies before the first list is drawn and the outline rows
  of the first paint are already the chosen height.
- `shellToggleCompact()`: flips `shellCompact`, writes `"compact"` or forgets
  the key (`storeWrite(ROWS_KEY, on ? "compact" : null)`), calls
  `drawCompact()`, hides a showing tooltip (`hideTip()`: every row moved),
  scrolls the active row of the focused or last-used listbox into view
  (`row.scrollIntoView({ block: "nearest" })` on
  `document.querySelector(".rows .row.is-active")` when there is one), and
  calls `shellEnable()` so the menu's tick follows. A write the storage
  refuses holds the choice until the app closes.
- `shellChecked()` returns every ticked id: `show_under_construction` when
  the items show, then `compact_rows` when compact.
- `shellEnabled()`: `"compact_rows"` joins the first `ids` line (it needs
  nothing of the page, so it is enabled from the first frame, on every page,
  the setup page included).
- `MENU_ANSWERS.compact_rows: () => shellToggleCompact()`.
- `app/main.js`: `DEFAULT_MENU_WORDS.compact_rows = "&Compact Rows"`; `BAR`'s
  View menu becomes `... SEPARATOR, ["reset_columns"], ["compact_rows"],
  ["show_under_construction"]`; `ALWAYS` and `CHECKABLE` gain
  `compact_rows`; the tick before the page speaks is no longer every
  checkable id: a new `DEFAULT_TICKED = new Set(["show_under_construction"])`
  seeds `menuChecked`, so Compact Rows starts unticked and Show Under
  Construction ticked, as today. The Mac strips the `&` as for every item
  (P252). No accelerator: like P197, a once-in-a-while preference needs no
  key of its own; Alt, V, C reaches it (no other View item uses C).
- `tracker/api.py` `MENU`: `"compact_rows": "&Compact Rows"` after
  `reset_columns`. `pilot/wording-shell.tsv`: one `api.MENU` row, in the
  shape of the `show_under_construction` row.

**The CSS** (`shell.css`, one block headed "Compact Rows (P271)", before
the forced-colours block; `pilot-ui.css` gains the token):

| What | Comfortable (today) | Compact |
|---|---|---|
| A row's least height (`.row`, `.row-skeleton`) | `--size-row` 40px | `--size-row-compact` 32px |
| A row that wraps (rulings 21, 27: `.row-wrap`, 4px above and below) | 40 / 48 / 68px for 1 / 2 / 3 lines | 32 / 48 / 68px (the second and third lines are the same 20px lines) |
| The date (`.row-date`) | caption 12/16 | caption 12/16 (already caption, SPEC-shell 3.6: unchanged) |
| The Tax Year cell (`.row-year`, Overview and Reminders) | body 14/20 | caption 12/16, so the year reads with the dates |
| The editor's fields (`.editor-table` inputs and selects) | 28px, 4px above and below: a 36px line | `--size-control-sm` 24px, 4px above and below: a 32px line |
| Everything else in a row (name, detail, status pill, form chip, link mark, the step and its chevron) | as today | as today: each is 24px or less, so each fits a 32px row centred |

Selectors: `.rows-compact .row`, `.rows-compact .row-skeleton`,
`.rows-compact .row-year`, `.rows-compact .editor-table :is(input:not([type="checkbox"]):not([type="radio"]), select)`.
The block may set only `min-height`, `font-size` and `line-height`: no
width, no column and no padding changes, so a stored column width (P139,
P199) means the same thing in both densities and the 1100px arithmetic of
SPEC-shell 3.6 is untouched.

**Where it applies:** every list page - Overview, Needs Review, Reminders,
Households (both tabs), a household, a year, a return - and the request
list editor (and the custom-rows table of New Household and Add a Return,
which is the same component, `.editor-table`). **Not:** the side panel's
rows, the notices, the column headers (24px), the Overview's figures, the
side sheet, the search list, the other dialogs' lists. Those are not lists
of work.

### 1.3 Keyboard and focus

A native check item: Windows (and macOS) draw its tick, its focus and its
contrast colours. Choosing it moves no focus. A focused row stays focused
and stays in view. No motion: the rows change height at once (SPEC-shell 8.6,
no motion when the page changes).

### 1.4 Both themes

Heights only; no colour changes. Banding (`--bg-band`), hover, the active
row and the focus ring are the row's own in both themes and in forced
colours.

### 1.5 Files and functions

`app/renderer/shell.js` (`ROWS_KEY`, `shellCompact`, `shellReadCompact`,
`drawCompact`, `shellToggleCompact`, `shellChecked`, `shellEnabled`,
`MENU_ANSWERS`, the top-level `drawCompact();`), `app/renderer/shell.css`,
`app/renderer/pilot-ui.css` (the token), `app/main.js`
(`DEFAULT_MENU_WORDS`, `BAR`, `ALWAYS`, `CHECKABLE`, `DEFAULT_TICKED`,
`menuChecked`), `tracker/api.py` (`MENU`), `pilot/wording-shell.tsv`.

### 1.6 Sentences amended

- SPEC-shell 3.6, first sentence of the row: "A **row** is 40px tall
  (`min-height: 40px` ...)" gains: "; under View › Compact Rows it is 32px
  (`--size-row-compact`, P271), the Tax Year cell is caption, and nothing
  else changes."
- SPEC-shell 10.3, Sizes: "row 40" becomes "row 40 (32 compact, P271)".
- SPEC-shell 11.3: the table gains `compact_rows` | &Compact Rows (P271, a
  checked item).
- SPEC-lists 15.1 (where P197's setting is named): one line - "View ›
  Compact Rows (P271) is kept the same way, under `tracker.rows`."
- `pilot/SPEC-hide-under-construction.md` is history and is not edited.

### 1.7 Tests

New, `tests/test_shell.py` (a `COMPACT_FUNCTIONS` list and a fake document
root with a `classList`, beside `SOON_PANEL`):

- `test_compact_rows_are_off_until_chosen_and_the_menu_flips_keeps_and_says_the_tick`:
  with nothing stored, no `rows-compact` class and no `compact_rows` in
  `shellChecked()`; the menu's answer adds the class, stores `compact`
  under `tracker.rows` and sends the tick; again removes the class, forgets
  the key and sends no tick.
- `test_storage_that_cannot_be_read_keeps_comfortable_rows_and_a_choice_holds_while_the_app_is_open`.
- `test_a_damaged_stored_density_reads_as_comfortable` (`COMPACT`, `1`,
  `true`, empty).
- `test_a_stored_density_applies_at_load_before_the_words`: a top-level
  `drawCompact();` in `shell.js`, as P197's review S1 pinned for `drawSoon`.
- `test_a_compact_row_is_32px_on_every_list_page_and_in_the_editor`:
  `--size-row-compact` is 32px, `--size-row` still 40px, and the compact
  block's selectors cover `.row`, `.row-skeleton` and the editor's fields.
- `test_compact_rows_change_heights_and_the_years_size_never_a_column`: every
  rule whose selector names `.rows-compact` declares only `min-height`,
  `font-size` and `line-height`.
- `test_switching_density_keeps_the_active_row_in_view_and_hides_a_showing_tip`.

New, `tests/test_shell_menu.py`:

- `test_compact_rows_sits_between_reset_column_widths_and_show_under_construction_unticked_from_the_first_frame`.
- `test_choosing_compact_rows_is_sent_to_the_page`.

New, `tests/test_api.py`:

- `test_the_compact_rows_word_is_in_the_menu_and_the_wording_table`
  (`api.MENU["compact_rows"] == "&Compact Rows"`, and the tsv row's
  proposed word is the same).

Existing pins that change:

- `test_shell.py::test_every_menu_id_the_page_answers_is_in_the_template_and_the_rest_are_the_rows`
  (the id table gains `compact_rows`).
- `test_shell.py::test_the_setting_is_this_pcs_and_the_side_panel_draws_it_on_every_draw`
  (the first `ids` line now also holds `"compact_rows"`; the assertion on
  `show_under_construction` stands).
- The P197 tests that lift `shellChecked` (`SOON_FUNCTIONS`) now lift
  `shellReadCompact` too and give the fake its key; their expected values
  do not change, because a new install is Comfortable.
- `test_shell_menu.py::test_show_under_construction_is_the_view_menus_last_item_a_ticked_check_item_from_the_first_frame`
  (`view[-4:] == ["-", reset, compact, show]`; the "no other checkbox"
  assertion leaves out both check items),
  `::test_only_the_items_that_need_nothing_are_enabled_until_the_page_speaks`
  (gains `compact_rows`),
  `::test_the_tick_follows_the_page_and_a_stray_checked_id_is_dropped` and
  `::test_a_chosen_check_item_keeps_the_pages_tick_until_the_page_answers`
  (each run for both ids).

### 1.8 Why

Forty-pixel rows show about fifteen returns on the office screen. A
preparer working down a long list wants more at once; someone reading
across the room wants the roomier rows. The choice is a matter of taste on
one screen, so it is kept on that PC and never in the firm's settings.

---

## 2. L2 - Needs Review, one flat list (P272)

### 2.1 What a person sees

The title row ("Needs Review", "13 Files") and the reason cards (N11's even
grid) are unchanged, and so are the column headers. Under them, each return
with files waiting is an ordinary group, as on a return's own page:

```
 2025  Taxpayer  [1040]   Household Name · 2 Documents  […]
   file-one.pdf          [W-2 chip]      (!) Can't Tell     Mar 3
   file-two.pdf                          (!) Could Not Use  Mar 4

 2025  Other Taxpayer  [1065]   Other Household · 1 Document  […]
   ...
```

No box, no border, no raised fill, no folder icon, no "2 Documents" pill.
The count is in the heading's caption. The rows start at the page's keyline
like every other list, so they line up with the column headers (inside the
card they sat 1px and 8px off).

**The grouping stays one heading per return** (SPEC-lists 5, P136, P149),
with its household beside it. P272's words say "a heading per household";
see question J1 in section 9: the default built is per return, because the
answer Jason chose (Q8b) is about the card, not the grouping, and every
file's Check, the sheet's next arrow and the menu act on a return.

### 2.2 Behaviour

`pages.js` `pagesReviewGroup(group, specs)`:

- No `lead` (the folder icon goes).
- `caption`: the household as today's small grey link (`pagesHeadLink`,
  kind household) and its link mark (`pagesLinkMark`) when linked, then
  `" · "` and the count in the existing words (`words.documents.one` /
  `words.documents.many`, "1 Document" / "{n} Documents"). With no household
  known, the count alone. The separator is the one `pagesHouseholdCaption`
  types today; no new word.
- `tools: [more]`: the **More Actions** button (`i-more`,
  `aria-label` and tooltip `words.icons.more_actions`, `aria-haspopup="menu"`)
  stays and keeps its handler: it opens the return's native menu (the
  `return` template - Edit Request List…, Draft Reminder…, Open Working
  Folder, Open Client Folder, Open Inbox - with `pagesEnableFor` of the
  group's token) at the button's bottom-left. It now sits right after the
  count, 4px from it, not at the far right of a full-width card.
- A right-click anywhere on the heading line opens the same menu (kept).
- `first: true` for the first group drawn on the page, so it sits 24px under
  the column headers (`.group-head.is-first`); each next heading is 32px
  under the last row before it (the group's own margin).
- Returns the group's nodes; the `.return-card` wrapper goes.
- `group-docs` (the pill) and the folder icon are no longer drawn.

Unchanged: `pagesReviewGroups`, `pagesReviewSpec` (the file rows: icon,
link, request chip, reason pill, date, Check step, `file` menu),
`pagesOrderedGroups`, `pagesPaged` (by whole return groups),
`pagesReasonCards`, `pagesColumnHeads("needs_review")`, the sheet's next
arrow (group by group), the search's waiting files.

**Where the "…" actions go (the menu's actions survive):** they stay on the
heading - the More Actions button and the heading's right-click - because
every one of them acts on the return, not on a file. A row's hover step
stays **Check**, the file's own step; putting the return's menu on a file
row would make one file's row act for its neighbours.

`shell.css`:

- Delete `.return-card:not(.hidden)`, `.return-card .group-head:not(.hidden)`,
  `.return-card .row:not(.hidden)`, `.return-card .row-name`,
  `.return-card .rows` and `.group-docs`; take `.group-docs` out of the
  tabular-figures list (section "Browser surfaces") and `.return-card`,
  `.group-docs` out of the forced-colours list.
- `.group-head:has(.group-more):not(.hidden) { align-items: center; }`: a
  return heading holds a 16px chip and a 24px button, so it centres them; the
  page's title row keeps its baseline.
- `.group-more.icon-button:not(.hidden) { width: var(--size-control-sm);
  height: var(--size-control-sm); margin-left: var(--sp-1); color:
  var(--text-secondary); }`: a quiet 24px button, visible at rest so a person
  can find it (the reason Q6/P270 gives for steps).

### 2.3 Keyboard and focus

Tab order on the page: the reason cards, the column header buttons, then for
each return its heading's links (the taxpayer, the household, the link
mark), its More Actions button and its rows' listbox (one Tab stop, the
listbox keys of SPEC-shell 3.6). Enter or Space on More Actions opens the
native menu; Esc closes it and focus returns to the button (the system's
menu behaviour). Nothing new is a Tab stop; the card's border, which was
not, is gone.

### 2.4 Both themes

The heading is on `--bg-page` instead of `--bg-raised`: the taxpayer link
(`--link` on `--bg-page`, 12.67 / 9.38), the household and the count
(`--text-secondary` / `--text-caption` on `--bg-page`, 8.28 / 9.36 and
5.94 / 6.75) and the button (`--text-secondary`, hovered on `--bg-hover`,
7.56 / 8.08) are all pairs of SPEC-shell 10.2 already. Banding stays the
firm list's (`--bg-band`). Forced colours: the heading's links are
`LinkText`, the button `ButtonText` with its ring, as every icon button.

### 2.5 Sentences amended

- SPEC-lists 12, "Each return is a card group" paragraph, becomes: "**Each
  return is a group** (P272): the return's name (the H2 link), the
  household as the small grey secondary link with the P141 icon when
  linked, then ' · {n} Documents', and a visible **More Actions** icon
  button that opens the same native menu as a right-click on the heading.
  No card, no border, no pill, no folder icon; the rows sit at the page's
  keyline (SPEC-shell 3.2, 3.6)."
- SPEC-lists 5's table row "Household beside it" already says "then ' ·
  {count}' in `--text-caption`": unchanged, now true again.
- SPEC-shell 6.2, first bullet: "its caption the household (a link) and the
  count" stays; add "(P272: no card; the More Actions button after the
  count opens the return's menu)".

### 2.6 Tests

New, `tests/test_shell.py`:

- `test_needs_review_is_one_flat_list_with_no_card_pill_or_folder_icon`
  (lifted `pagesNeedsReview`: no node with class `return-card`,
  `group-docs` or `group-icon`; every group is a `.group-head` followed by
  its `.rows`).
- `test_a_needs_review_heading_says_the_return_then_the_household_and_its_count`
  (caption text "Household · 2 Documents" with the household a link; "1
  Document" for one; the count alone with no household).
- `test_more_actions_follows_the_count_and_opens_the_returns_own_menu`
  (a click calls `shellPopup("return", <the group's token>, x, y, enable)`;
  a right-click on the heading does the same).
- `test_the_first_needs_review_heading_is_the_pages_first_group`
  (`is-first` on the first heading drawn, page by page).
- `test_no_card_rule_remains_and_a_needs_review_row_starts_at_the_keyline`
  (no selector in `shell.css` names `.return-card` or `.group-docs`; no rule
  overrides `.row`'s padding for Needs Review).

Existing pins that change:

- `test_shell.py::test_the_firm_pages_rows_link_by_the_firms_keys_and_carry_the_year`:
  `ran["docs"] == ["2 Documents"]` goes; `captionText` becomes the
  fixture's made-up household name, then " · 2 Documents", and `caption`
  still links the household.
- `test_shell.py::test_needs_review_pages_by_whole_return_groups_and_counts_files`:
  counts `group-head` nodes that are not the page head, not `return-card`s.
- `test_shell.py::test_the_four_lists_and_a_needs_review_card_fit_1100px_beside_a_windows_scrollbar`
  becomes `test_the_four_lists_fit_1100px_beside_a_windows_scrollbar`: the
  card's assertion (`2 * sp[6] + 2 + 2 * sp[2]`) goes.

### 2.7 Why

The page mixed two ways of drawing a list: cards on Needs Review, plain
groups everywhere else. One way is easier to read and easier to keep: the
eye learns one shape, and the rows line up with their own column headers.
The menu that the "…" opened is kept, next to the count, because its
actions are the return's.

---

## 3. L3 - The notices panel (P273)

### 3.1 What a person sees

In a window **1388px wide or wider** (the app opens at 1400 × 900), the
notices sit in a panel at the right of the page, under the path row:
288px wide, the side panel's quiet fill, a hairline on its left edge. Each
notice keeps its sentence, its **Details** and its dismiss. The page is no
longer pushed down by them. When the last notice is dismissed or clears,
the panel goes and the page takes its width back. In a window narrower than
1388px the notices are exactly as today: one 40px line each above the page
(N12's form).

**The breakpoint is 1388px, not about 1100px.** The window's least width is
1100px (SPEC-shell 3.1), so "under 1100px" never happens. Every page is
designed to fit the 860px page area of a 1100px window (SPEC-shell 3.6, the
lists' fit test). The panel is drawn only where the page keeps those 860px
beside it: 240 (side panel) + 860 + 288 = **1388**. That is how "the page
keeps its whole width" is read here: never narrower than it was designed
for. At 1400 the firm lists' fixed columns (P199) end well before the
page's right edge, so the panel mostly takes space that was blank. See J2.

### 3.2 Behaviour

**Markup: none changes.** `#notices` stays where it is in `index.html`
(between `#bar` and `#page`, `role="alert"`, `aria-live="polite"`), and
`drawNotice` keeps its order: the sentence, the Details disclosure, the
action or Retry, the dismiss. Only the CSS places it, and two small JS
changes keep focus (3.3).

**CSS** (`shell.css`, one block `@media (min-width: 1388px)` headed "The
notices panel (P273)", after the notice rules and before the forced-colours
block; `pilot-ui.css` gains `--size-notices`):

- `#main:not(.hidden)`: `grid-template-columns: minmax(0, 1fr) auto;
  grid-template-rows: var(--size-bar) minmax(0, 1fr);`.
- `#bar:not(.hidden)`: `grid-column: 1 / -1` (the path row, search and sort
  stay full width; the sort control stays 32px from the window's edge).
- `#page`: `grid-column: 1; grid-row: 2`. `#notices`: `grid-column: 2;
  grid-row: 2`.
- `#notices:empty` stays `display: none` (style.css), so with no notice the
  `auto` column is 0 wide and the page has the whole width.
- `#notices:not(:empty)`: `display: grid; align-content: start; gap:
  var(--sp-2); width: var(--size-notices); min-height: 0; overflow-y: auto;
  padding: var(--sp-4); background: var(--bg-nav); border-left: 1px solid
  var(--border);`. Many notices scroll inside the panel; the page does not
  move.
- **A notice in the panel** (`#notices .notice:not(.hidden)`): `flex-wrap:
  wrap; align-items: center; column-gap: var(--sp-2); row-gap: var(--sp-1);
  min-height: 0; padding: var(--sp-2) var(--sp-2) var(--sp-2) var(--sp-4);`.
  - `.notice-text`: `flex: 0 0 100%` - the sentence has the notice's whole
    first line, and wraps to a second there only when the sentence is longer
    than the panel (each is five words or fewer, SPEC-shell 11.1; most fit
    one line). The words do not change.
  - The second line holds the controls, in the order they are in the
    markup: **Details** at the start (`.notice-detail { flex: 1 1 auto }`,
    which pushes the buttons to the end), then the action or Retry, then the
    dismiss. With no Details, the first button after the sentence takes
    `margin-inline-start: auto` so the buttons still sit at the end.
  - **Opened**, the Details disclosure takes the whole second line
    (`.notice-detail[open] { order: 0; flex: 0 0 100%; }`, overriding N12's
    `order: 1` for the panel only); its summary stays where it was, at the
    start of that line, so the same click closes it; the engine's sentence
    unfolds under the summary at the notice's width; the action and the
    dismiss move to the line after it, at the end
    (`.notice-detail[open] ~ .notice-act:first-of-type { margin-inline-start:
    auto }` or the equivalent).
  - Sizes: a notice in the panel is 72px closed (8 + 20 + 4 + 32 + 8), 92px
    when its sentence wraps once; every part stays on the 4px grid.
- **The toast** while the panel shows: `body:has(#notices:not(:empty))
  #toast { inset-inline-end: calc(var(--size-notices) + var(--sp-6)); }`, so a
  toast ("Copied", "Saved") sits at the bottom right of the page, 24px left
  of the panel, and never covers a notice. With no panel, and in the stacked
  form, the toast is where it is today (bottom right of the window).
- Under 1388px nothing in this block applies: the stacked form, N12's rules
  in `pilot-ui.css` and SPEC-shell 3.5, unchanged.

The panel never animates in or out (SPEC-shell 8.6: no motion when the page
changes); a notice's own 150ms fade is unchanged.

### 3.3 Keyboard and focus

- **F6** visits the notices: `shell.js` `F6_REGIONS = ["side", "bar",
  "notices", "page"]`; `regionOf` answers `"notices"` inside `#notices`;
  the cycle skips `"notices"` while `#notices` holds no notice;
  `focusRegion("notices")` focuses the first notice's first control (its
  Details summary, else its action, else its dismiss). The order is the
  markup's, in both forms, so Tab and F6 agree: path row, notices, page.
- **Dismissing keeps focus in place.** A new `app.js`
  `noticeFocusAfter(entry)`, called by `dismissNotice` before it removes the
  node, does nothing unless focus is inside the notice
  (`entry.node.contains(document.activeElement)`); then it moves focus to
  the next notice's dismiss, else the previous notice's dismiss, else
  `#page` (where F6 puts it) - so dismissing the last notice, which
  collapses the panel, never drops focus to the window. A notice cleared by
  the page (a keyed notice whose state ended) while it held focus is handled
  the same way. It reads only `document.activeElement` and the notice
  nodes, so the tests that lift `dismissNotice` give it a two-line fake.
- **Esc does not dismiss a notice.** Failures and warnings stay until a
  person dismisses them (decision 193); Esc keeps SPEC-shell 4.3's order
  (sheet, search list, tooltip).
- Screen readers: unchanged. `#notices` stays the live region; a new notice
  is announced as today, whichever form it is drawn in.

### 3.4 Both themes

The panel is `--bg-nav` with a `--border` hairline, the side panel's own
pair, in light and dark: the page sits between two quiet rails. Each notice
keeps its kind's fill, edge and ink (err, warn, info tokens; SPEC-shell
10.2's pairs, unchanged); nothing new is text on `--bg-nav`. Forced colours:
the shell's block gains `#notices:not(:empty) { border-left-color:
CanvasText; }` beside the existing `#notices .notice` rule; the background
is already `Canvas` through `#main`.

### 3.5 Sentences amended

- SPEC-shell 3.1, the tree's `div#main` line: "grid rows: [bar 48px][notices
  auto][page 1fr]" gains "; at 1388px and wider, columns [page 1fr][notices
  auto] under the bar (P273)".
- SPEC-shell 3.5, first sentence "Between the path row and the page, full
  width, ..." becomes: "**At 1388px and wider (P273)** the notice area is a
  288px panel at the right of the page, under the path row, `--bg-nav` with
  a hairline at its left, shown only while it holds a notice; each notice is
  its sentence on the first line and its controls (Details, the action, the
  dismiss) on the second, and opened Details takes the second line with the
  buttons under it. **Narrower**, between the path row and the page, full
  width, ..." (the rest of 3.5 as written). "Notices never push the path row
  away" stays; add "and in the panel they never push the page down".
- SPEC-shell 4.3, the F6 row: "side panel › path row › notices (while any
  shows) › page › side panel".
- SPEC-shell 8.4, first sentence "One line each, the kind by fill and ink":
  becomes "One line each in the stacked form, the sentence and then its
  controls in the panel (3.5, P273); the kind by fill and ink ...". The
  Details sentence "Closed, the disclosure sits at the right end of the
  notice's line, before the action and the dismiss (P264); opened, the
  sentence unfolds under the line at the notice's width" gains: "In the
  panel, closed, it is the first of the controls on the second line; opened,
  it takes that line and the action and dismiss move under it." The rest of
  8.4 (what each notice says, P259's open-on-setup rule, the dismiss icon
  ending each) is unchanged.
- SPEC-shell 8.6: add "The notices panel comes and goes without motion."
- SPEC-shell 2.2, E24's New home: "`#notices` at the top of the page area"
  becomes "`#notices`: the right-hand panel at 1388px and wider, the top of
  the page area below it".
- SPEC-shell 10.3, Sizes: add "notices panel 288".
- `docs/runbook.md`: the sentence "in a notice at the top of the app's first
  screen headed *Setup Needs Attention*" becomes "in a notice headed *Setup
  Needs Attention* - in the panel at the right of the app's first screen, or
  at its top in a window narrower than 1388px"; the window paragraph ("The
  app's window, in one paragraph") gains one sentence: "Notices (a failure,
  a warning) sit in a panel at the right of the page while there is one, or
  above the page in a narrow window; each stays until you dismiss it."

### 3.6 Tests

New, `tests/test_shell.py`:

- `test_the_notices_panel_is_a_column_beside_the_page_at_1388px_and_wider`
  (the media block places `#page` in column 1, `#notices` in column 2, the
  bar across both; the panel is `--size-notices` wide).
- `test_the_panel_leaves_every_page_the_860px_it_is_designed_for`
  (`1388 - --size-side - --size-notices == 860`, read from the tokens and
  the media query, in the style of the 1100px fit test).
- `test_a_notices_panel_with_no_notice_takes_no_width` (the column is
  `auto`; `#notices:empty` is `display: none`; no other rule in the block
  gives `#notices` a width while empty).
- `test_a_notice_in_the_panel_keeps_its_sentence_details_action_and_dismiss_in_markup_order`
  (lifted `drawNotice`: the children are the sentence, Details, the action,
  the dismiss, unchanged; the panel's rules give the sentence the first line
  and keep an opened summary at the start of the second).
- `test_below_1388px_the_notices_are_n12s_one_line` (the N12 rules are
  outside every `min-width` block).
- `test_dismissing_a_focused_notice_moves_focus_to_the_next_then_the_previous_then_the_page`
  (lifted `noticeFocusAfter` and `dismissNotice` with a fake document).
- `test_f6_visits_the_notices_between_the_path_row_and_the_page_only_while_one_shows`
  (lifted `regionOf`, `focusRegion` and the F6 branch of `shellKey`).
- `test_a_toast_sits_left_of_the_notices_panel_while_it_shows`.
- `test_escape_never_dismisses_a_notice` (the Escape branch of `shellKey`
  names no notice function).

Existing pins that change:

- The tests that lift `dismissNotice` (`SORT_NOTICE_FUNCTIONS`, and
  `test_the_notices_of_a_first_start_are_drawn_after_the_setup_page_takes_the_screen`
  and its neighbours that list it) add `noticeFocusAfter` to the lifted
  functions and a `document` fake with `activeElement: null`; their
  expected values do not change.
- Any pin on `F6_REGIONS` or SPEC-shell 4.3's F6 row (the builder searches
  `tests/test_shell.py` for `F6`).

### 3.7 Why

Four notices took a third of the page and pushed the work down. Notices
are for the few things that need a person; the work is the page. A panel at
the side keeps both in view: the list stays where the eye left it, and the
notices wait at the side until someone deals with them. The panel only
appears where there is room for it, so no list is ever squeezed; on a
small screen the notices go back to the top, as they are today.

---

## 4. L4 - The household page: a card beside the returns (P275)

### 4.1 What a person sees

```
 Household Name                                         (H1)

   2025                                    ┌───────────────────────┐ […]
   [1040] Taxpayer       3 Need You        │ Contact               │
   [1065] Other Name     Complete          │ A Person              │
                                           │ Shared With           │
   2024                                    │ A Person, Another     │
   [1040] Taxpayer       Complete   Rolled │ Shared                │
                                           │ Inbox Link            │
                                           │ Saved                 │
                                           └───────────────────────┘
```

The H1 stays. Under it, the returns list on the left, at the page's
keyline, with a year heading per year (newest first) and each return's
status right after its name; the card on the right, 288px, holding the
contact, who the household is shared with and whether it is shared, and
whether its inbox link is saved, with the More Actions button at its top
right. When the page is narrower than 1056px (a 1100px window; or a 1400px
window while the notices panel shows), the card sits above the list instead,
across the page, its three facts side by side.

### 4.2 What is on the card

From the `list` reply's household (`shellHousehold(route.household)`) and,
for the shared state, the household's state when it is the one on screen
(`lastState.household`, as `pagesHouseholdCaption` reads it today):

| Fact (`dt`, caption, `--text-caption`) | Value (`dd`, body, `--text`) | Drawn when |
|---|---|---|
| **Contact** | the contact's name | the household has a contact |
| **Shared With** | the members' names, joined ", "; under them, weight 600, **Shared** or **Not Shared** (the existing `screen.shared` / `screen.not_shared`) | it has members, or its state is on screen (the state line alone when there are no members) |
| **Inbox Link** | **Saved** when the record holds the inbox's link (`hh.link` not empty), else **Not Saved** | always |

- The link itself is **never drawn and never opened**: it is the client's
  share link, which the letter carries; an app that opened it would reach
  the network. "Saved" tells a person whether Mark as Shared will be
  accepted (the engine refuses it until the link is pasted). See J3.
- Opening the inbox folder stays a menu item (SPEC-shell 3.9, ruling 12:
  the only link that opens File Explorer is a file name): Household › Open
  Inbox, and the card's More Actions menu.
- A fact with nothing to say is left out, as the caption does today. The
  card always has at least the Inbox Link.
- New words, `vocab.screen.household_card` in `tracker/api.py` `SCREEN`
  (Title Case, five words or fewer, rows in `pilot/wording-shell.tsv`):
  `contact` "Contact", `shared_with` "Shared With", `inbox_link` "Inbox
  Link", `link_saved` "Saved", `no_link` "Not Saved". For Jason's approval
  (J4); built as written meanwhile. The page types none of them; a missing
  key is a loud failure, as every `screenWords()` read is.
- `screen.contact` ("Contact {name}") has no reader once the caption goes:
  the builder removes it with its tsv row if no test or file reads it, and
  otherwise leaves it and says so in the handoff.

### 4.3 Behaviour

`pages.js`:

- New `pagesHouseholdCard(route, hh)`: returns `div.household-card` holding
  a `dl.card-facts` (one `div.card-fact` per fact: `dt`, then one or two
  `dd`) and the **More Actions** button (`button.icon-button.card-more`,
  `i-more`, `aria-label` and tooltip `words.icons.more_actions`,
  `aria-haspopup="menu"`). The button opens the **household** native menu
  (Edit Household…, Add a Return…, Roll Forward…, Mark as Shared, Open
  Client Folder, Open Inbox) through `shellPopup("household",
  "crumb-household", box.left, box.bottom)` - the token the H1's own
  right-click uses (`pagesTitle`), so the menu acts on the page's household
  with the page's enable rules. A right-click anywhere on the card opens the
  same menu at the pointer.
- `pagesHousehold(route)` returns `[H1, div.household-body]`;
  `household-body` (the container, `container-type: inline-size`) holds
  `div.household-layout` holding the card (first, so it is read first) and
  `div.returns-list` with the year groups (`pagesGroup` per year, as today)
  or, with no returns, the empty line and **Add a Return…** button (as
  today). The card and each year are built inside `pagesSafe`, so one that
  cannot be built is named in a notice and the rest is drawn.
- `pagesHouseholdCaption` goes (its facts are the card's); `pagesCaption`
  stays for its other callers.
- `pagesReturnSpecs` sets `statusNext: true` on every spec; `pagesRow`, for a
  spec with `statusNext`, builds its cells as name, status, detail, end (the
  DOM order, so the accessible name reads in the order the eye does).
- `pagesYear(route)` wraps its list in `div.returns-list` too, so the year
  page's rows read the same way (SPEC-shell 6.6: "as on the household
  page"). It has no card.

`shell.css` (a block headed "The household page (P275)"; `pilot-ui.css`
gains `--size-card`):

- `.returns-list .row:not(.hidden)`: `grid-template-columns:
  var(--size-col-name) var(--size-col-status) minmax(var(--size-col-form),
  1fr) var(--size-col-end);` - name 224, status 160 right after it, then
  the detail (Inactive, Rolled Forward) and the end column. A long taxpayer
  name wraps (ruling 21), it is never cut.
- `.returns-list .rows`: `min-width: calc(var(--size-col-name) +
  var(--size-col-status) + var(--size-col-form) + var(--size-col-end) + 3 *
  var(--sp-4) + 2 * var(--sp-8));` (736px), replacing the general 840px
  least width for these lists.
- `.household-body { container-type: inline-size; }`.
- `.household-layout:not(.hidden) { display: grid; grid-template-columns:
  minmax(0, 1fr); }`; the card: `margin: var(--sp-6) var(--sp-8) 0;`, its
  facts `display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--sp-4);` (stacked: across the page, three facts side by side).
- `@container (min-width: 1056px)`: `.household-layout` gets
  `grid-template-columns: minmax(0, 1fr) var(--size-card); align-items:
  start;`, the list `grid-column: 1; grid-row: 1`, the card `grid-column: 2;
  grid-row: 1; margin: var(--sp-6) var(--sp-8) 0 0;` and its facts one
  column. 1056 is the list's least width (736: the keyline 32, name 224,
  16, status 160, 16, detail 96, 16, end 144, and 32 of the row's own right
  padding) plus the card (288) plus the card's right margin (32, the
  keyline mirrored). The rows' own right padding is the gap before the
  card.
- `.household-card:not(.hidden)`: `position: relative; padding:
  var(--sp-4); border: 1px solid var(--border); border-radius:
  var(--radius); background: var(--bg-raised);`. `dt`: caption, `--text-caption`;
  `dd`: body, `--text`, `margin: 0`, names wrap (`overflow-wrap: anywhere`);
  the shared state `dd`: weight 600. `.card-more`: 24px
  (`--size-control-sm`), `--text-secondary`, at the card's top right
  (`position: absolute; inset-block-start: var(--sp-2);
  inset-inline-end: var(--sp-2)`), the facts keeping clear of it
  (`padding-inline-end: var(--sp-6)` on the `dl`).
- The card's top lines up with the first year heading (both 24px under the
  H1).

### 4.4 Every action the household page has today, and where it goes

| Today | After |
|---|---|
| H1 right-click → the household menu (`pagesTitle`) | kept |
| The path's household segment right-click → the household menu (`shell.js` crumbs) | kept |
| Household menu bar: Edit Household…, Add a Return…, Roll Forward…, Mark as Shared, Open Client Folder, Open Inbox (and Edit Request List…, Draft Reminder…, Open Working Folder, grey off a return) | kept, same enable rules (`shellEnabled`) |
| *(none: the household menu had no keyboard path on the page)* | the card's **More Actions** button opens the household menu (new keyboard path; no new action) |
| A return's name link → its page | kept, in the returns list |
| A return row's **Open** step (hover, focus, Enter, double-click) | kept |
| A return row's right-click / Shift+F10 → the return menu (`pagesPopup`) | kept |
| The caption "Contact {name} · Shared / Not Shared" | the card's Contact and Shared With facts |
| A return's status, far right | right after the return's name |
| "Inactive" / "Rolled Forward" detail | the column after the status |
| Year groups (H2 per year, newest first) | kept, as headings in the returns list |
| No returns: "No returns yet" and **Add a Return…** | kept, in the returns list's place, the card beside or above it |
| Household notices: two years open, folder renamed with **Accept**, a year's pause, feeds (Details) | kept; drawn in the notices panel (L3) or above the page |
| Sort Now (F9, Tools › Sort Now, the sort control) for this household | kept where P274 puts it (section 7) |
| The roll dialog, the household editor, the mark-shared write | unchanged: reached from the menus above |

### 4.5 Keyboard and focus

Tab order: the path row, the notices (if any), then on the page the card's
More Actions button, then each year's listbox (one Tab stop each, the
listbox keys of SPEC-shell 3.6). The card is first because it is first in
the markup (the household's facts before its returns), in both forms. The
card itself is not a Tab stop; its facts are text. Enter or Space on More
Actions opens the native menu at the button; Esc closes it and focus
returns to the button. A focused return row stays focused across a redraw
(`pagesWhere` / `pagesRestore`, unchanged).

### 4.6 Both themes

The card is `--bg-raised` with a `--border` hairline in both themes (white
on white with an edge in light; a lighter raised grey on the dark page in
dark). Text on it is `--text` (17.85 / 12.63) and `--text-caption` (5.94 /
6.05); the button is `--text-secondary` (8.28 / 8.39), hovered on
`--bg-hover`; the focus ring `--focus` on `--bg-raised` (5.17 / 6.81). All
are SPEC-shell 10.2 pairs already: no contrast row is added. Forced colours:
the card joins the forced-colours list of raised things (`border: 1px solid
CanvasText; background: Canvas; color: CanvasText`); its button is an icon
button like every other.

### 4.7 Sentences amended

- SPEC-shell 6.5, "H1: the household's name. Under it one caption line of
  what applies, joined by ' · ': 'Contact {name}', 'Shared' or 'Not shared'."
  becomes: "H1: the household's name. Under it (P275) the returns list and,
  beside it at 1056px of page and wider, else above it, the household card:
  Contact, Shared With (the members and Shared or Not Shared), Inbox Link
  (Saved or Not Saved; the link is never drawn or opened), and More Actions,
  which opens the household menu."
- SPEC-shell 6.5, "Rows: one per return ... Detail ... Status: as on
  Clients" gains: "The status is the column right after the name; the
  detail follows it."
- SPEC-shell 6.6: "Rows: that year's returns, as on the household page"
  stays true (it now includes the status beside the name).
- SPEC-shell 2.4, E43 and E44's New home: "household page caption" becomes
  "the household card (P275)".
- SPEC-shell 10.3, Sizes: add "household card 288".

### 4.8 Tests

New, `tests/test_shell.py`:

- `test_the_household_page_is_its_h1_then_the_card_and_the_returns_list`
  (lifted `pagesHousehold`: `[h1, .household-body]`; the body holds the
  card first, then `.returns-list` with one group per year, newest first).
- `test_the_card_says_contact_shared_with_and_whether_the_inbox_link_is_saved`
  (a household with a contact, two members, a link and its state shared:
  the three facts and "Shared", "Saved"; with no contact and no state:
  Shared With without its state line, and Contact left out; with no link:
  "Not Saved").
- `test_the_card_never_draws_the_inbox_link_itself` (the fixture's link text
  appears nowhere in the card's text, attributes or tooltips).
- `test_more_actions_on_the_card_opens_the_household_menu_with_the_h1s_token`
  (a click and a right-click call `shellPopup("household",
  "crumb-household", ...)`).
- `test_a_household_and_a_year_row_put_the_status_right_after_the_name`
  (cell order name, status, detail, end; `statusNext` only from
  `pagesReturnSpecs`, so the firm lists' rows are unchanged).
- `test_the_card_sits_beside_the_returns_at_1056px_of_page_and_above_them_below`
  (the `@container (min-width: 1056px)` rule and the token arithmetic:
  `--sp-8 + col-name + col-status + col-form + col-end + 3 * --sp-4 + --sp-8
  + --size-card + --sp-8 == 1056`).
- `test_a_household_with_no_returns_keeps_add_a_return_beside_the_card`.
- `test_the_card_words_are_the_vocabularys` (every word the card shows is
  from `vocab.screen.household_card`, `screen.shared` / `not_shared` or
  `screen.icons.more_actions`; a missing key throws).

New, `tests/test_api.py`:

- `test_the_household_card_words_are_in_the_screen_vocabulary_and_the_wording_table`.

Existing pins that change:

- `test_shell.py::test_needs_review_household_and_year_pages_say_each_field_once`:
  the rows are found inside `.returns-list`; each row's name cell is still
  the form chip and the taxpayer.
- Any test that reads `pagesHouseholdCaption` or `screen.contact` (the
  builder searches `tests/`), and the run_pages_dom function lists that name
  `pagesHousehold` (they gain `pagesHouseholdCard`).
- `test_shell.py::test_only_the_household_year_and_return_pages_draw_an_h1`
  is unchanged and must still pass.

### 4.9 Why

The household page had three lines of content on a wide screen, and a
return's status sat at the far right, a long way from its name. Putting
the household's facts in one card answers "who do we talk to, have we
shared the folder, is the link in" at a glance, and putting the status next
to the name lets the eye read a return in one movement. Opening folders
stays in the menu, as it is everywhere else in the app, and the link that
would open a web page is described, never opened.

---

## 5. Screenshots (the harness)

`pilot/harness/shoot.mjs` gains these scenarios (made-up households of
`stub.js` only), and a per-scenario `sizes` option for the breakpoint
shots. `stub.js`: the first made-up household gets two members and a
made-up, non-URL link token (so its card says Saved); the household with no
returns keeps no link. No other stub change.

| Scenario | Shows | Item |
|---|---|---|
| `overview-compact`, `needs-review-compact`, `return-compact`, `household-compact` | each page after `shellToggleCompact()` | L1 |
| `editor`, `editor-compact` | the request list editor on the return (`openEditor()` after the return draws) | L1 |
| `needs-review` (existing), `needs-review-filtered` (a reason card pressed), `needs-review-empty` (existing), `sheet-check-from-firm` (existing) | the flat list | L2 |
| `notices` (existing, four notices), `notices-details-open` (the first Details opened), `setup` (existing, Details open), `sort-failed` (existing, one notice), `notices-toast` (a toast word the vocabulary has, while notices show) | the panel at 1400, the stacked form at 1100 | L3 |
| `notices-breakpoint` with `sizes: [[1387, 900], [1388, 900]]` | stacked at 1387, the panel at 1388 | L3 |
| `household` (existing), `household-notices` (existing: the panel shows, so the card stacks at 1400), `household-no-returns` (existing), `year` (existing) | the card beside and above | L4 |

Every scenario in both themes, at 1400 × 900 and 1100 × 700 (the harness's
`SIZES`), plus the breakpoint pair. The harness's forced-colours pass at
1100 covers `notices` and `household` too.

**Before and after** at 1400 × 900, light and dark, for `overview`,
`needs-review`, `return`, `household`, `household-notices`, `notices`,
`setup` and `editor`: "before" from a separate worktree of the base commit
(the builder never stashes or checks out in the working tree), "after"
from the build. The handoff names the folder and attaches the pairs to the
pull request. It also records one number: the rows of the Overview's Work
Waiting list visible at 1400 × 900, Comfortable and Compact.

---

## 6. New words (for Jason's approval; built as written meanwhile)

| Key | Words | Where |
|---|---|---|
| `api.MENU.compact_rows` | &Compact Rows | View menu, a check item (L1) |
| `screen.household_card.contact` | Contact | the household card (L4) |
| `screen.household_card.shared_with` | Shared With | the household card |
| `screen.household_card.inbox_link` | Inbox Link | the household card |
| `screen.household_card.link_saved` | Saved | the household card |
| `screen.household_card.no_link` | Not Saved | the household card |

L2 and L3 add no word. Every word is a `pilot/wording-shell.tsv` row and a
`tests/test_api.py` pin, in the shape of P256's and P257's.

---

## 7. Where the other answers touch this job

- **P267** (underline on hover), **P270** (a quiet chevron at rest), **P268**
  (the Tax Year column only when more than one year): row-level looks that
  L1's heights and L2/L4's lists inherit; none conflicts. P270's chevron is
  16px and fits a 32px row; L1's caption year applies whenever P268 shows
  the column.
- **P274** (a labelled Sort Now button on the household and return pages):
  its own job. Nothing here places it; L4 leaves the H1's line free for it
  and L3's bar spans both columns, so a button in the path row is
  unaffected.
- **P279** (virtualized household, year and return pages and editor): its
  SPEC is written after this job lands, and must take a row's height from
  the drawn rows (40 or 32, L1), never a constant, and keep L4's
  `.returns-list` structure.
- **P265, P266** (the side panel), **P269** (the "Last Activity" header),
  **P276-P278** (the engine process, the last-pass watch, paging the firm
  reply), **P280** (the type stack): no overlap with these four items
  beyond shared files.
- Because P265-P270 and P274 change the same files (`pages.js`,
  `shell.js`, `shell.css`, `tests/test_shell.py`), no two builders run in
  the same tree at once; this job takes its turn in the queue.

---

## 8. Scope: the job

**Recommendation: one sonnet builder for all four items, built in the
order L1, L2, L3, L4.** Reasons: the four share the same files
(`pages.js`, `shell.js`, `shell.css`, `pilot-ui.css`, `tests/test_shell.py`,
`SPEC-shell.md`), so separate builders would either wait for each other or
collide; L4's container width and L3's panel width are one calculation;
and one opus review of one coherent change, graded item by item against
L1-L4, costs less than four loops. The builder finishes and passes each
item's own tests before starting the next, and the handoff reports each
item separately (what was built, its tests, its screenshots). If the
builder runs long, it stops after L2 and hands off; the rest is a second
builder on the same branch, never in parallel.

**Branch:** a new branch from the commit that lands P264 (`c718e37` or its
merge), not `claude/ui-polish`'s working tree.

**Files the builder may touch:**

- `app/renderer/shell.js`, `app/renderer/pages.js`, `app/renderer/app.js`
  (`noticeFocusAfter`, `dismissNotice`), `app/renderer/shell.css`,
  `app/renderer/pilot-ui.css` (the three tokens), `app/main.js` (the menu)
- `tracker/api.py` (`MENU.compact_rows` and `SCREEN.household_card` only;
  words, no behaviour), `pilot/wording-shell.tsv`
- `tests/test_shell.py`, `tests/test_shell_menu.py`, `tests/test_api.py`
  (the two word pins), `tests/test_pilot_ui.py` (only if a token rule there
  needs the new tokens named)
- `pilot/harness/shoot.mjs`, `pilot/harness/stub.js` (section 5 only)
- `pilot/SPEC-shell.md`, `pilot/SPEC-lists.md` (the sentences of 1.6, 2.5,
  3.5 and 4.7, word for word as given there), `docs/runbook.md` (the two
  sentences of 3.5)
- Not: `index.html`, `style.css`, `sheet.js`, `tooltip.js`, any engine
  module's behaviour, `docs/repo-map.*`, `pilot/DECISIONS.md`,
  `pilot/HANDOFF.md` (the orchestrator's).

**Gate the builder runs (decisions 207, 211; Jason 2026-09-29):**

1. Dead code first, in the changed files: the `.return-card` and
   `.group-docs` rules, `pagesHouseholdCaption`, `screen.contact` if
   unread (4.2), any unused import, local or name.
2. The affected tests, **each file its own process, started side by side**,
   under the floor interpreter (3.11) and the office's (3.14; on this Mac
   `build-portable/venv/bin/python`); a machine without the floor
   interpreter says so in the handoff and the orchestrator's gate runs it:
   - `tests/test_shell.py` (owns `shell.js`, `pages.js`, `app.js`, the CSS)
   - `tests/test_shell_menu.py` (owns `main.js`'s menu)
   - `tests/test_pilot_ui.py` (the tokens' file)
   - `tests/test_api.py` (owns `tracker/api.py`)
   - `tests/test_api_entry.py` (`api_entry.py` imports `api` at call time)
   - `tests/test_single_source.py`, `tests/test_layers.py` (guards)
   - `tests/test_tripwire.py`, `tests/test_errors.py` (tests change)
   Never `-m "not corpus"`. The engine's tests (router, filer, scanner,
   manifest and the rest) do not run: nothing here reaches them.
3. `python -m ruff check .`.
4. The harness shots of section 5, attached.

After a review's findings, the rebuild reruns only the test files its
fixes touch.

**No commit and no map update by the builder.** The orchestrator, after
the review has no findings, updates `docs/repo-map.curated.json` (the
notes of `pages.js`, `shell.js`, `app.js`, `main.js`, `shell.css`) and runs
`python tools/repo_map.py update`, `python tools/repo_map.py check`,
`tests/test_repo_map.py`, ruff and the vocabulary report's check, writes
the P-rows' status lines, and commits.

**Review:** opus, high effort, in a session that did not build. Numbered
findings against L1-L4 and sections 5-6 of this SPEC, with the screenshots
in hand. A finding that survives one rebuild is fixed by opus itself; if
that fix still fails review, stop and tell Jason.

---

## 9. Questions only Jason can answer (each built as the default meanwhile)

- **J1 (P272). One heading per return, or per household?** Today each group
  is a return (year, taxpayer, form), with its household beside it
  (SPEC-lists 5, P136). P272's row says "a heading per household". (a)
  **Default, built:** one heading per return, its household beside it and
  its count - the card goes, the grouping stays, because Check, the sheet's
  next arrow and the "…" menu each act on one return. (b) One heading per
  household (its name and count), each of its returns a small sub-heading
  over its files: one more level, and the "…" menu moves to each
  sub-heading. P272's wording follows the answer.
- **J2 (P273). The panel's breakpoint.** (a) **Default, built:** the panel
  at 1388px and wider (it shows at the app's 1400 default), stacked above
  the page below that, so no page is ever narrower than the 860px it is
  designed for. (b) A panel that slides over the page's right edge at
  narrow windows: rejected as the default because it covers the Date and
  step columns.
- **J3 (P275). The inbox link on the card.** (a) **Default, built:**
  "Saved" or "Not Saved", the link itself never drawn or opened. (b) The
  link's text drawn (never opened), for a person to copy.
- **J4. The six new words of section 6.** Built as written.
- **J5 (P275). The card on the right (default, built: the returns keep the
  page's keyline, and the card is read first) or on the left.**
