# Pilot 0.3 - UI menu, the small items - SPEC

Status: written 2026-10-11 on `claude/ui-polish` at `16931e2` (P264 built in
`c718e37`, Jason's menu answers recorded as P265-P280). This SPEC builds eight
of those answers: **P265, P266, P267, P268, P269, P270, P274, P280**
(`pilot/DECISIONS.md`). The menu they answer is `SPEC-ui-polish.md` section 2
(Q1-Q6, Q10, Q16). The larger answers (P271-P273, P275) and the speed answers
(P276-P279) have SPECs of their own, built after this one.

Read first: this file, then `SPEC-ui-polish.md` section 1 (the format this
file follows), then the nodes of the files below with
`build-portable/venv/bin/python tools/repo_map.py show <file>`. Do not re-scan
the repository.

**Hard rules kept.** No generative AI reads a client document. No test reads a
real folder. The screenshot harness's names are made up. Nothing in this job
sends anything, calls the network or adds a command: every change is how the
app draws what it already has, plus words in the vocabulary.

---

## 0. What changes, in plain English

- **The side panel's five Under Construction pages** each take one line: a
  short name ("Ready to Sign") and a small grey "Soon" tag at the right. The
  tooltip still says "Under Construction", and View › Show Under Construction
  still hides them.
- **The brand band** at the top of the side panel shows the JP mark alone,
  32px, with "Tax Document Console" beside it. The firm's name is the
  window's title and nowhere else in the panel.
- **Names in the lists** (a taxpayer, a household, a file) are no longer
  underlined at rest. They keep their link colour, and the underline comes
  back when the pointer is over the name or the keyboard is on its row.
- **The Tax Year column** of the Overview and Reminders shows only when the
  list holds more than one year. In a season where every row is 2025, the
  column is not drawn.
- **The "Date" header** is held: the column does not show the last activity
  (section 0.1, question A). Nothing about it changes in this job.
- **Every row with a next step** shows a small grey chevron at its end at
  rest, so a person can see the row does something. The step's words
  ("Open", "Check") appear beside it on hover or when the keyboard is on
  the row.
- **Sort Now** is a labelled button, at the right end of the path row, on a
  household's, a year's and a return's page. The firm pages (Overview,
  Needs Review, Reminders, Households) have no sort control. While a sort
  the app started is running, the button reads "Stop Sorting" on every page,
  so a running sort can always be stopped.
- **The type** is the Mac's own system face on a Mac, and Segoe UI on Windows,
  chosen in one place.

### 0.1 Questions only Jason can answer (the build does not wait: each has a default)

**A. P269, the "Date" header: the column is not the last activity.** The
menu said "the value is the last activity". It is not: on the Overview,
a return that needs a person shows the day its **oldest waiting file**
arrived ("Mar 3"), and a return waiting on the taxpayer shows its **due date**
("Due Apr 15"); `tracker/api.py` `_firm_row` sends only `oldest` and `due`,
and SPEC-shell 6.1 says the same. A header reading "Last Activity" would
misstate both kinds of row.
**Answered 2026-10-11: (c), built in this job** (the default before the answer was nothing).
The options (M5 says what each costs):
(a) keep "Date";
(b) make the column truly the last activity - a new field in the engine's
`firm` reply (the newest day anything happened on the return) and the firm
cache that keeps it, its own SPEC, effort M;
(c) keep the values and let each cell say what it is: "Since Mar 3" on a
return that needs a person, "Due Apr 15" as today, header "Date" (one new
word, effort S). Recommend **(c)**.

**B. P266, which mark.** "The mark alone" is read as **the JP mark of the
firm's logo** (the circle and monogram, without the words), because it was
drawn for the navy band, and because Jason kept the firm's logo over the
product's folder mark in P192 (SPEC-icon question 2). The other reading is
the Tax Document Console folder mark of P191; on the navy band its navy body
and rim are about 1.9:1 against the band, so only its gold tab and cream sheet
would show. **Default built: the JP mark.**

**C. P274, the year page and a running sort.** Jason named the household and
return pages. **Default built:** Sort Now shows on the **year page too** (it
sits between them, sorts the same household, and F9 works there today), and
while a sort the app started is running, **Stop Sorting shows on every page**,
firm pages included (today's rule that a running sort can always be stopped;
the firm pages still never offer Sort Now).

**D. New and changed words** (`tracker/api.py` `SCREEN`, all five words or
fewer, Title Case). **Default built as listed:**

| Key | Today | After |
|---|---|---|
| `side.soon.ready_to_sign` | Ready to Sign (Under Construction) | Ready to Sign |
| `side.soon.family_entities` | Family Entities (Under Construction) | Family Entities |
| `side.soon.personal_trusts` | Personal Trusts (Under Construction) | Personal Trusts |
| `side.soon.corporate_entities` | Corporate Entities (Under Construction) | Corporate Entities |
| `side.soon.portal_settings` | Portal Settings (Under Construction) | Portal Settings |
| `side.soon_tag` | (new) | Soon |
| `side.brand` | J Park & Associates | (removed: nothing draws it) |
| `sort.tip` | (new) | Sort This Household's Inbox |
| `sort.firm` | Open a Household to Sort | (removed: firm pages have no button) |

`sort.tip` is the Sort Now button's tooltip; Jason may prefer other words or
no tooltip.

**E. P267 and the colour-only cue.** The link colour is 1.4:1 against the
text (final review B, finding 6), so at rest a name in a list is told apart
from plain text by its column, its weight and (for a file) its icon, not by
an underline (WCAG 1.4.1 asks for a non-colour cue). Jason chose this; it is
built as decided. **Default built:** a Windows contrast theme keeps the
underline at rest, where the system's colours decide.

**F. P280, "one token".** Read as "the face is chosen once, in the token
block, by one platform switch". The text and display role names stay, because
Windows has two cuts of Segoe UI Variable; on a Mac both are the one system
stack. Worth knowing: on a Mac without Segoe UI installed (nearly every Mac)
the app already falls through to the system face today, so on most Macs this
item changes nothing visible; it makes the choice deliberate rather than a
fallback.

---

## 1. The items

Each item gives: why (for a person), the behaviour, the code (file and
function), keyboard and focus, both themes, the SPEC sentences that change,
the words, the tests to add (named as claims) and the existing tests whose
pins change. Line numbers are at `16931e2`; the builder finds each by its
function name.

### M1. The side panel's Under Construction items are one line (P265)

**Why.** The five pages not built yet took two lines each and a third of the
panel. One line each, with "Soon", says the same in a third of the room.

**Behaviour.** Each of the five items is one 40px row: its icon, its short
name, and at the row's right a small "Soon" tag. The row stays muted
(`--text-secondary`), stays an `aria-disabled` button, keeps the tooltip
"Under Construction", and choosing it still shows the "Under Construction"
toast and opens nothing (P154). View › Show Under Construction is unchanged
(P197: hides the five and the Workspace heading, kept on this PC).

**Code.**
- `app/renderer/index.html`, the five `.side-section.is-soon` buttons: add
  after each `span.side-name` a `<span class="side-soon" aria-hidden="true"></span>`.
  The file types no word.
- `app/renderer/shell.js` `shellSideWords`: for each `[data-soon]` item, the
  name from `side.soon[key]` (as today), the tag's text from `side.soon_tag`
  (a missing word throws, as every word there does), `setTip(node,
  side.under_construction)` (as today), and
  `node.setAttribute("aria-description", side.under_construction)`. The tag
  is `aria-hidden`, so a screen reader hears "Ready to Sign, unavailable,
  Under Construction", never "Ready to Sign Soon". (While the tooltip shows,
  tooltip.js's `aria-describedby` wins over `aria-description`, so the words
  are never read twice.)
- `app/renderer/shell.css`: `.side-section.is-soon:not(.hidden)` keeps only
  `color: var(--text-secondary)` (its `height: auto`, `min-height` and
  `padding-block` go); the rule `.side-section.is-soon .side-name { white-space:
  normal; overflow: visible; }` goes, so the name cuts with "…" like every
  other item. New `.side-soon`: `flex: none; padding: 0 var(--sp-2);
  border-radius: var(--radius); background: var(--bg-pressed); color:
  var(--text-secondary); font-size: var(--fs-caption); line-height:
  var(--lh-caption); font-weight: var(--fw-strong);` (the neutral count
  badge's look) and `.side-soon:empty { display: none; }` (no empty pill at
  the first paint, before the words). In the forced-colors block, `.side-soon`
  joins the list that gets `border: 1px solid CanvasText; background: Canvas;
  color: CanvasText`.
- `tracker/api.py` `SCREEN["side"]`: the five short names and `soon_tag`
  (0.1 D). `pilot/wording-shell.tsv`: the five `side.soon.*` rows' `proposed`
  column to the short names (note "P265"), and a new row
  `api.SCREEN	side.soon_tag		new	Soon	1	Side panel, tag on an unbuilt page	Pilot 0.3, SPEC-ui-menu-small M1 (P265)	Soon	new`.

**Keyboard and focus.** Unchanged: each item is a Tab stop in the panel,
Enter or Space shows the toast, F6 reaches the panel at its current page,
and an item hidden by the View menu hands focus to the current page (P197).

**Themes.** The tag is `--text-secondary` on `--bg-pressed`: 4.5:1 or more in
both themes (the pair is in `test_the_new_tokens_and_every_new_pair_meet_their_contrast_in_both_themes`).
The row on `--bg-nav` and `--bg-nav-hover` as today.

**Fit.** The name has about 132px beside the icon and the tag; "Corporate
Entities", the longest, is about 120px in Segoe UI and a little more in the
Mac's face. If the harness shows any name cut at 1400 × 900, the builder
reports it (a finding for the review), and does not shrink the type.

**SPEC sentences that change.** SPEC-lists 15.1, the **Under Construction**
bullet: "\"Ready to Sign (Under Construction)\" and \"Family Entities (Under
Construction)\" among the pages; section **\"Workspace\"**: \"Personal Trusts
(Under Construction)\", \"Corporate Entities (Under Construction)\", \"Portal
Settings (Under Construction)\". Each muted but readable" becomes: "**Ready to
Sign** and **Family Entities** among the pages; section **Workspace**:
**Personal Trusts**, **Corporate Entities**, **Portal Settings** - each one
line, its short name and a small **Soon** tag at the right (P265; the tag is
`aria-hidden`, the button's `aria-description` is \"Under Construction\").
Each muted but readable". SPEC-shell 3.3's last bullet adds P265 and P266 to
its list of decisions. `SPEC-hide-under-construction.md` is history and is
not edited.

**Tests to add.**
- `tests/test_shell.py`
  `test_an_unbuilt_item_is_one_line_its_short_name_and_a_soon_tag_a_screen_reader_does_not_read`:
  index.html's five `is-soon` buttons each hold one `side-soon` span with
  `aria-hidden="true"` and no text; `shellSideWords`, lifted with a fake
  DOM, fills the five names and tags from the vocabulary, sets each item's
  tooltip and `aria-description` to "Under Construction", and throws for a
  missing `soon_tag`; shell.css has no `height: auto` or `white-space: normal`
  under `.is-soon`, and `.side-soon` uses only tokens.
- `tests/test_api.py`
  `test_the_side_panels_unbuilt_items_have_short_names_and_one_soon_word`:
  `SCREEN["side"]["soon"]` is the five short names, none says "Under
  Construction", `soon_tag` is "Soon", `under_construction` is unchanged, and
  each word's row in `wording-shell.tsv` proposes it.

**Pins that change.** `test_the_side_panel_is_the_mocks_with_the_firms_brand_and_nothing_behind_the_unbuilt_items`
asserts every `soon` word ends in "(Under Construction)": it now asserts the
short names (and M2 changes its brand lines; rename it
`test_the_side_panel_is_the_mocks_with_the_products_brand_and_nothing_behind_the_unbuilt_items`).

### M2. The brand band is the mark and the product's name (P266)

**Why.** The logo's firm line was 133px wide and could not be read at normal
size. The mark alone is legible, the product's name sits beside it, and the
firm's own name is where Windows and macOS already show it: the window's
title.

**Behaviour.** The band is 48px tall (SPEC-shell 3.3's height, back from
P179's 64px), navy (`--brand`) in both themes. In it: the JP mark (the circle
and monogram of the firm's logo, no words), 32 × 32, then 8px, then "Tax
Document Console" in body type, weight 600, `--window-light`, on one line,
cut with "…" if it ever does not fit. The firm's name is not in the band,
not even for a screen reader (the `visually-hidden` copy goes). The window's
title is unchanged: `applyVocabulary` already sets it to "Tax Document
Console — {firm}" when the setup page has the firm's name, and to the
product's name alone when it does not.

**Code.**
- New `app/renderer/mark.svg`: the `<circle>` and the monogram `<path>` of
  `app/renderer/logo.svg`, copied unchanged, in an `<svg
  xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 480">` (the mark sits
  inside x 0-480 of the logo's 2000 × 480 drawing). No `<text>`, no script,
  no style element. `app/renderer/logo.svg` is deleted: nothing loads it after
  this change (the lockup stays in Git's history).
- `app/renderer/index.html` `#side-brand`:
  `<div id="side-brand"><img src="mark.svg" alt="" /><span id="side-brand-product"></span></div>`
  (the `side-brand-words` wrapper and the `side-brand-name` span go). The
  comment above the side panel says the band is the mark and the product's
  name (P266).
- `app/renderer/shell.js` `shellSideWords`: the `side-brand-name` line goes;
  `side-brand-product` is filled from `side.product` as today.
- `app/renderer/shell.css`: the two `#side-brand:not(.hidden)` blocks become
  one - `display: flex; align-items: center; gap: var(--sp-2); height:
  var(--size-bar); padding-inline: var(--sp-4); background: var(--brand);` -
  with `#side-brand img { width: var(--size-control); height:
  var(--size-control); flex: none; }` and `#side-brand-product { min-width: 0;
  color: var(--window-light); font-size: var(--fs-body); line-height:
  var(--lh-body); font-weight: var(--fw-strong); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }`. The `#side-brand-words`
  rules go; in the forced-colors block `#side-brand-words { color: CanvasText; }`
  becomes `#side-brand-product { color: CanvasText; }`.
- `tracker/api.py` `SCREEN["side"]`: `brand` is removed. `wording-shell.tsv`:
  the `side.brand` row's verdict becomes `cut`, proposed empty, words 0,
  where "Nowhere; was the side panel's brand band", note "P266".

**Keyboard and focus.** None: the band is not a control, and the image is
decorative (`alt=""`); the product's name is read as text.

**Themes.** Navy in both themes, as today; `--window-light` on `--brand`
passes 4.5:1 (an existing pair). In a contrast theme the band takes `Canvas`
as today, and the mark (an image, drawn cream and gold) keeps its own colours,
as the logo did; the product's name carries the band there.

**SPEC sentences that change.**
- SPEC-shell 3.1 skeleton: "div#side-brand              navy band, 48px, logo 32px tall"
  becomes "div#side-brand              navy band, 48px: the mark 32px and the product's name (P266)".
- SPEC-shell 3.3: "`#side-brand`: 48px tall, `--brand` (navy in both themes),
  the logo 32px tall, `padding-inline: var(--sp-4)`." becomes "`#side-brand`:
  48px tall, `--brand` (navy in both themes), the JP mark 32px and beside it
  \"Tax Document Console\" (body, 600, `--window-light`), `padding-inline:
  var(--sp-4)`; the firm's name is the window's title (P266)."
- SPEC-lists 15.1, the **Brand band** bullet, whole, becomes: "**Brand band**
  (`--brand`, both themes; P266, superseding P179): the JP mark alone, 32px,
  and beside it **\"Tax Document Console\"** (body, 600) in `--window-light`;
  48px tall. The firm's name is the window's title (\"Tax Document Console —
  {firm}\" once the setup page has it) and is not in the band. New words name
  the app \"Tax Document Console\" (P155); nothing existing is renamed and no
  version number changes (P140)."

**Tests to add.**
- `tests/test_shell.py`
  `test_the_brand_band_is_the_mark_and_the_products_name_and_never_the_firms_name`:
  `#side-brand` holds `<img src="mark.svg" alt="" />` and
  `id="side-brand-product"`, and no `side-brand-name`; `mark.svg` exists, its
  viewBox is `0 0 480 480`, it has no `<text>`, `<script>` or `<style>`, and
  no renderer file names `logo.svg`; `SCREEN["side"]` has no `brand`;
  `shellSideWords` reads no `side.brand`; the band's rule is 48px
  (`var(--size-bar)`) and the mark `var(--size-control)`.
- `tests/test_shell.py` `test_the_firms_name_is_the_window_titles_alone`:
  `applyVocabulary`'s title line is unchanged (`vocab.firm ? \`${vocab.product}
  — ${vocab.firm}\` : vocab.product`), and "J Park" appears in no file of
  `app/renderer` but `pilot-content.js` (the pilot's terms, P63's exception)
  and in no word of `SCREEN`.

**Pins that change.** The side panel test above (`words["brand"]`, the
`side-brand-name` id). `test_the_side_panel_names_the_product_from_its_one_home`
(`test_single_source.py`) is unchanged and must still pass.

### M3. Names in lists are underlined on hover and focus only (P267)

**Why.** Fifty underlined names on a page read as noise. The names keep their
link colour, and the underline comes back exactly when a person is about to
act on one.

**Behaviour.** Every `.row-link` (a taxpayer's or household's name in a row,
a file's name, a return's name in a Needs Review heading, the household
beside it) is drawn in its colour with no underline at rest. It is
underlined (1px, offset 4px, as today's rest) while the pointer is over it,
and while its row is the keyboard's active row in a focused list. In a
Windows contrast theme it is always underlined. Nothing else changes: the
link colours, the pointer cursor, the tooltips, what a click does. The
Linked Households panel's names (`.link-to`) and the path row's buttons are
not lists and keep their own rules.

**Code.** `app/renderer/shell.css`:
- `.row-link`: `text-decoration: none` (was `underline`); keeps `color`,
  `cursor`, `text-decoration-thickness: 1px`, `text-underline-offset`.
- `.row-link:hover { text-decoration-thickness: 2px; }` becomes
  `.row-link:hover, .rows:focus-visible .row.is-active .row-link { text-decoration: underline; }`.
- The comment above `.row-link` says P267 and the cue that remains at rest
  (the column, the weight, a file's icon), replacing "a link is always
  underlined".
- The forced-colors block: `.row-link { color: LinkText; }` becomes
  `.row-link { color: LinkText; text-decoration: underline; }`.

A heading's link (`pagesHeadLink`) and the household beside it are not Tab
stops today and stay so: the keyboard reaches what they open through the
rows and the row's menu, so for them "focus" is the row's.

**Themes.** No colour changes. The underline is `currentColor`, so it is
`--link` (or `--text-secondary` for the household beside a heading) in both
themes.

**SPEC sentences that change.**
- SPEC-lists 15.2: "Names stay underlined links." becomes "Names are links in
  their colour, underlined on hover and on the keyboard's active row, and
  always in a contrast theme (P267)."
- SPEC-lists 5: "After (three levels; links stay links - underlined,
  SPEC-shell 3.9):" becomes "After (three levels; links stay links -
  underlined on hover, P267, SPEC-shell 3.9):"; in its table, "underlined;
  `--link` on hover" becomes "`--link` and underlined on hover", and
  "`--link`, underlined" becomes "`--link`"; and the sentence ending "and the
  underline says \"link\" (WCAG 1.4.1)." ends instead "and, on hover, the
  underline (P267: at rest a name is told from text by its place, size and
  weight; a contrast theme keeps the underline)."
- SPEC-shell 3.9: add after the table's first sentence: "A name link is
  underlined on hover and on the keyboard's active row, and always in a
  contrast theme (P267)."

**Tests to add.** `tests/test_shell.py`
`test_a_name_link_is_underlined_on_hover_on_the_keyboards_active_row_and_always_in_a_contrast_theme`,
replacing `test_a_link_differs_from_plain_text_by_more_than_its_colour`:
`.row-link` has `text-decoration: none` and `cursor: pointer`; one rule
whose selectors are `.row-link:hover` and `.rows:focus-visible .row.is-active
.row-link` sets `text-decoration: underline`; the forced-colors block has
`.row-link { color: LinkText; text-decoration: underline; }`; the status
rules (`.is-waiting`, `.is-attention`, `.is-done`, `.is-plain`,
`.row-status`) still set no `text-decoration` and no `cursor` (they never
look pressable).

**Pins that change.** The test it replaces. The `.group-count .row-link`
colour pins (`test_shell.py` about line 3474) are unchanged.

### M4. The Tax Year column only when the list holds more than one year (P268)

**Why.** In a season every row said the same year, so the column took 80px to
say nothing. When two years are listed (a late return from last season),
the column comes back and tells them apart.

**Behaviour.** The Overview's Work Waiting and Reminders draw their Tax Year
column (the header and each row's year cell) only when the list's rows hold
**more than one year**. The count is over the **whole list before its tab
and its pages** (the Overview: the paused households and every return of
both buckets; Reminders: every ready draft), so switching the Overview's
tab or turning a page never makes the column come or go. A blank year (a
paused household's row, a return whose record has no year) is not a year.
With the column left out:
- the other four columns keep their order and widths and move left by the
  year's width (every column is exactly its width, P199);
- the year is still said to a screen reader: each return row's
  `aria-description` ends with its year;
- an order by Tax Year kept on this PC is not applied (the list is in its
  usual order, so a paused household still leads) and is kept, so it applies
  again when the column comes back; no header shows an arrow for it;
- a kept width for the column stays kept.
Needs Review is unchanged: it has no Tax Year column, and each return's
heading says its year. The household, year and return pages have no year
column.

**Code.** `app/renderer/pages.js`:
- New `pagesYearsDiffer(specs)`: true when the specs' non-blank `year`
  values (as strings) number more than one.
- New module state `let pagesYearless = false;` - the list being drawn
  leaves out its Tax Year column (P268). `pagesDraw` sets it to `false`
  before `pagesBuild`, and after drawing toggles the class `is-yearless` on
  the page (`page.classList.toggle("is-yearless", pagesYearless)`) beside
  where it sets `data-list`.
- `pagesOverview`: `pagesYearless = !pagesYearsDiffer(all)` before
  `pagesOrdered`. `pagesReminders`: the same over every spec of
  `pagesReminderSpecs`, before its order.
- `pagesOrdered(list, specs)`: an order whose cell is `year` is not applied
  while `pagesYearless`.
- `pagesColumnHeads(list)`: leaves out the `year` cell while `pagesYearless`.
- `pagesRow(spec)`: a `returnRow` leads with the year cell only when not
  `pagesYearless`; when yearless and the spec has a year, `String(spec.year)`
  joins the end of `described`.

`app/renderer/shell.css`, after the five-column rules:
```css
/* P268: a list of returns whose rows are all one year leaves out its Tax Year column. */
#page.is-yearless .row-return:not(.hidden),
#page.is-yearless .col-table[data-list="overview"] .col-heads:not(.hidden),
#page.is-yearless .col-table[data-list="reminders"] .col-heads:not(.hidden) {
  grid-template-columns: var(--size-col-taxpayer) var(--size-col-form) var(--size-col-status) var(--size-col-end);
}
#page.is-yearless .col-table[data-list="overview"], #page.is-yearless .col-table[data-list="reminders"],
#page.is-yearless[data-list="overview"] .rows, #page.is-yearless[data-list="reminders"] .rows {
  min-width: calc(var(--size-col-taxpayer) + var(--size-col-form) + var(--size-col-status) + var(--size-col-end) + 3 * var(--sp-4) + 2 * var(--sp-8));
}
```
The loading outline keeps the five-column shape (the years are not known
until the counts arrive).

**Keyboard and focus.** The header row has one button fewer, so Tab skips
nothing that is not there; Ctrl+Shift+Arrow and the grips work on the four
that are. Focus kept across a redraw (`pagesRemember` / `pagesRestore`) is
by row and header key, so it is unaffected.

**Themes.** No colour.

**SPEC sentences that change.**
- SPEC-lists section 1, first paragraph, add: "Since P268 the Tax Year
  column of both lists is drawn only when the list, before its tab and its
  pages, holds more than one year (`SPEC-ui-menu-small.md` M4)."
- SPEC-firm-columns ruling 2: after "never typed or guessed by the
  renderer." add "**Drawn only when the list holds more than one year**
  (P268): with one year the header and the year cells are left out, the year
  is in the row's screen-reader description, and a kept order by Tax Year
  waits until the column is back." Ruling 8 (Reminders) inherits it; say so
  in one clause.

**Tests to add** (`tests/test_shell.py`, on `run_lists`):
- `test_the_tax_year_column_shows_only_when_its_list_holds_more_than_one_year`:
  with every return 2025, the Overview's and Reminders' header words are
  Taxpayer, Form Type, Status/Stage, Date/Drafted, no row has a `row-year`
  cell, and the page has `is-yearless`; with one return set to 2024, both
  lists have the five headers and every row its year cell, and the page has
  no `is-yearless`; a paused household's blank year counts as no year.
- `test_a_tab_or_a_page_turn_never_shows_or_hides_the_tax_year_column`: with
  the 2024 return waiting and every need-you return 2025, the Need You tab
  still draws the column.
- `test_an_order_by_tax_year_waits_while_the_column_is_hidden_and_is_kept`:
  a stored `{overview: {cell: "year", dir: -1}}` with one year draws the
  usual order (the paused household first) and leaves the stored value as it
  was; with two years the same stored order applies.
- `test_a_hidden_tax_year_is_still_said_to_a_screen_reader`: yearless, each
  return row's `aria-description` ends with "2025"; with the column shown it
  does not repeat the year.
- `test_a_list_without_its_tax_year_draws_four_columns_in_its_rows_and_its_heads`:
  the CSS rules above, read with `blocks`, give the rows and both header rows
  the same four-column grid and the matching least width.

**Pins that change.** `FIRM_LISTS` is all 2025, so with this change its lists
are yearless. Set **one** fixture return to 2024 (Charlie, in the `line(...)`
call) so the existing five-column tests keep their meaning, and adjust the
assertions that every row says 2025:
`test_the_four_firm_lists_draw_a_header_row_of_buttons_in_the_rows_columns`
and `test_overview_and_reminders_say_tax_year_taxpayer_and_form_type_once_each_in_their_own_columns`
(the latter's `year == "2025"` becomes the row's own year). The builder runs
`grep -n 'row-year\|"Tax Year"' tests/test_shell.py` and checks every hit.

### M5. The "Date" header (P269) - option (c) is built

**Jason answered on 2026-10-11, before the build started:** "Say what each
cell is instead of just saying date." Option (c) below is built as part of
this job; P269 records it. The paragraphs that follow are kept as written.

**Why held.** See 0.1 A: the column holds the oldest waiting file's day or the
due date, never the last activity, so "Last Activity" would say something
untrue on every row. The builder changes no word for this item.

**If Jason answers before the build starts** (otherwise it is a later round):
- (a) "Date": nothing to build; Jason amends P269.
- (b) the engine's last activity: not this job; a SPEC of its own (a
  `firm` row field, the firm cache's shape, the column's order key).
- (c) "Since {date}": a new word `SCREEN["since"] = "Since {date}"` beside
  `due` (and its `wording-shell.tsv` row); `pages.js` `pagesWorkRows` draws a
  need-you row's date as `fill(screenWords().since, { date: pagesDay(one.oldest) })`
  (the order key stays the ISO day); SPEC-shell 6.1's "Date: the oldest file
  waiting (\"Mar 3\")" becomes "(\"Since Mar 3\")" and SPEC-lists 2's
  `columns.date` row says so; test `test_an_overview_date_says_whether_it_is_since_or_due`.

### M6. A quiet chevron at rest on every row with a next step (P270)

**Why.** The step ("Open ›", "Check ›") showed only under the pointer, so a
new user could not tell a row does anything. A small grey chevron at rest
says "this row goes somewhere"; the words still wait for the pointer or the
keyboard, so a page of fifty rows stays calm.

**Behaviour.** A row with a next step shows, at rest, a chevron at the right
edge of its end column, in `--text-caption`, beside its date. On hover, or
when it is the keyboard's active row in a focused list, the step's words
appear just before that chevron and both turn `--link`, in the place of the
date (the date hides, as today). A row with no step (and an Edit step a live
lock takes away) has no chevron. Clicking the chevron runs the step, as
clicking the step does today. The group heading's own step (`pagesGroupStep`)
is unchanged. The end column's width and the row's height do not change.

**Code.**
- `app/renderer/pages.js` `pagesRow`: the step becomes
  `h("span", { className: "row-step", "aria-hidden": "true" }, h("span", { className: "row-step-words" }, words), icon("chev", true))`
  (the words in their own span; the rest as today: `aria-hidden`, the words
  in the row's `aria-description`).
- `app/renderer/shell.css`:
  - `.row-step:not(.hidden)`: drop `visibility: hidden`; add `justify-self:
    end; color: var(--text-caption); cursor: pointer;` (keeps its padding,
    radius, weight and no-wrap).
  - `.row:hover .row-step, .rows:focus-visible .row.is-active .row-step
    { visibility: visible; }` becomes `{ color: var(--link); }`.
  - New `.row-step-words { display: none; }` and
    `.row:hover .row-step-words:not(.hidden), .rows:focus-visible .row.is-active .row-step-words:not(.hidden) { display: inline; }`.
  - New `.row.has-step .row-date { margin-inline-end: var(--sp-6); }` (the
    chevron's 12px, its 4px padding each side and a 4px gap), so a date drawn
    at the column's end (household, year and return pages) never meets the
    chevron; on the firm lists the date still starts at the column's left
    edge under its header (P199).
  - The rule `.row.has-step:hover .row-date, .rows:focus-visible
    .row.has-step.is-active .row-date { visibility: hidden; }` stays.
  - The comment over the firm lists' end column ("a row's step shows in the
    same place on hover") says instead that the chevron rests at the
    column's right edge and the words come before it.
  - Forced colors: unchanged (`.row-step` is `color: inherit`, and the
    focused row's step is `HighlightText`).

**Keyboard and focus.** Unchanged: the list is one Tab stop; Up/Down move the
active row; Enter runs its step; the step's words are announced from
`aria-description`, never read twice.

**Themes.** The chevron is non-text and needs 3:1: `--text-caption` is 4.9:1
or more on `--bg-page`, `--bg-band`, `--bg-hover` and `--bg-selected` in both
themes (all existing pairs).

**SPEC sentences that change.** SPEC-shell 3.6, the table's **end** row,
"at rest the date (\"Mar 3\", \"Due Apr 15\"); on hover or focus the row's
next step and a chevron in the same place" becomes "at rest the date and,
when the row has a step, a quiet chevron (`--text-caption`) at the column's
right edge; on hover or focus the step's words appear before the chevron, in
`--link`, in place of the date (P270)"; and "A row with no step keeps its
date on hover." becomes "A row with no step has no chevron and keeps its
date on hover." In the Keyboard paragraph, "clicking its step runs the step"
becomes "clicking its step - the chevron at rest - runs the step".

**Tests to add.** `tests/test_shell.py`
`test_a_row_with_a_step_shows_a_quiet_chevron_at_rest_and_its_words_on_hover_or_the_keyboards_active_row`:
`pagesRow` with a Check step gives `row-end` the children `row-date`,
`row-step`; `row-step` is `aria-hidden` and holds a `row-step-words` span
saying "Check" and the chevron; the CSS: `.row-step:not(.hidden)` has no
`visibility` and is `--text-caption` and `justify-self: end`;
`.row-step-words` is `display: none` and shown only by the hover and the
active-row rules; `.row.has-step .row-date` has `margin-inline-end:
var(--sp-6)`.

**Pins that change.** `test_a_row_carries_one_step_and_its_status_word_and_no_sentence`
keeps its claims (the end column's children, the lock taking Edit away, no
step no chevron); if it reads the step's text it reads `row-step-words`. The
forced-colors pin on `.rows:focus-visible .row.is-active .row-step` (about
line 919) is unchanged.

### M7. A labelled Sort Now button on a household's pages (P274)

**Why.** The circular-arrows icon read as "refresh". A button that says Sort
Now cannot be misread, and showing it only where a sort can run (a
household's pages) removes a grey control from the four firm pages, where it
could never be pressed.

**Where it sits, and why there.** In the path row (`#bar`, the header strip
above the page), at its right end, 8px after the search box and 32px from
the window's edge - the place the icon had. Not beside the page's H1: the
page is redrawn several times a visit (a state arriving, the counts landing,
a sort ending), and a button inside it would be rebuilt each time, losing
focus mid-press and flickering between Sort Now and Stop Sorting. The path
row outlives every page draw, and P275's household header card (next SPEC)
then has nothing to make room for.

**States** (`shell.js` `sortState`, drawn by `drawSort`):

| State | When | Shown | Words | Tooltip | Does |
|---|---|---|---|---|---|
| now | a household's, year's or return's page; no sort of the app's running; the return not locked | yes, enabled, `aria-keyshortcuts="F9"` | Sort Now (`sort.now`) | Sort This Household's Inbox (`sort.tip`) | `runScan()` for the open household, as today |
| locked | the same pages, the shown return locked elsewhere | yes, disabled | Sort Now | In Use Elsewhere (`sort.locked`) | nothing |
| stop | a sort the app started is running, **on any page** | yes, enabled, danger colours | Stop Sorting (`sort.stop`) | none | `stopPass()` |
| stopping | after Stop, until the pass ends, on any page | yes, disabled | Stopping (`sort.stopping`) | none | nothing |
| none | a firm page (Overview, Needs Review, Reminders, Households), or the setup page | **no** (the `hidden` class) | - | - | nothing |

- **No clients folder set:** the app is on the setup page (`shellNeedsRoot`),
  so the button is not shown, and F9 does nothing (the menu's `sort_now` is
  enabled only on a household's pages, `shellEnabled`, unchanged). The same on
  File › Change Clients Folder.
- **A scheduled pass running** (P256, the side panel says "Sorting"): as
  today, the button is not changed by it; Sort Now stays offered, and a click
  that meets the scheduled pass's hold on the household says so in the
  engine's words (the lock notice), exactly as the icon's click does today.
- The menu bar's Tools › Sort Now (F9) and Stop Sorting are unchanged.

**Code.**
- `app/renderer/index.html`: `<button id="sort" class="icon-button" type="button" data-tip-key="screen.sort.now">…</button>`
  becomes `<button id="sort" class="btn hidden" type="button"></button>` (no
  `data-tip-key`: it is not an icon-only button; hidden until the shell
  decides). The sprite's `i-sort` and `i-stop` symbols go: nothing draws them
  after this change. The comment over the skeleton says the button (P274).
- `app/renderer/shell.js`:
  - `sortState()` returns `{ key, words, tip, off, hidden, stop }` per the
    table: `key` one of `now`, `locked`, `stop`, `stopping`, `none`; `none`
    is `{ hidden: true, off: true }`. The `firm` state and `icon` go.
  - `drawSort()`: the first time it runs with the words, the button gets
    three spans, `h("span", { className: "sort-word", dataset: { word } }, said)`
    for `now`, `stop` and `stopping` from `screenWords().sort`; on every call
    it sets `aria-hidden="true"` on the spans that are not the state's
    (`locked` shows `now`), toggles `hidden` and `is-stop`, sets `disabled`,
    `data-sort-state`, `setTip(button, state.tip)` (empty clears it) and
    `aria-keyshortcuts` as today. No `aria-label`: the visible word is the
    name. If the button is about to be hidden while it has focus, focus moves
    to `#find` when it is enabled, else to the page (`focusRegion("page")`),
    and a tip it showed is hidden (`hideTip()`), so focus is never lost to
    the window.
  - `sortClicked()`: unchanged (`off` covers the hidden state).
  - The header comment and the section comment say "the Sort Now button
    (P274)" instead of "the sort icon (SPEC 8.1)".
- `app/renderer/shell.css`:
  - `#sort:not(.hidden) { display: inline-grid; }` and
    `#sort > .sort-word { grid-area: 1 / 1; }` and
    `#sort > .sort-word[aria-hidden="true"] { visibility: hidden; }`: the
    three words share one cell, so the button is as wide as its longest word
    in every state and the search box never moves.
  - `#sort.is-stop { --b-fg: var(--danger); --b-hover: var(--err-bg);
    --b-hover-bd: var(--err-border); --b-active: var(--err-bg); }` (the
    danger look the dialogs' discard buttons use), replacing the icon's two
    `#sort.is-stop` rules. `.btn:disabled` draws Stopping and the locked Sort
    Now.
  - The comment over `.icon-button` no longer names the sort icon.
- `tracker/api.py` `SCREEN["sort"]`: add `tip`, remove `firm` (0.1 D).
  `wording-shell.tsv`: a new `sort.tip` row, and the `sort.firm` row's verdict
  `cut` (where "Nowhere; firm pages have no sort control", note "P274").
- `pilot/harness/interact.mjs`: "grey on a firm page" becomes "absent on a
  firm page" (`#sort` has the `hidden` class on the Overview); the checks
  that hover or focus `#sort` go to the Smith household first (the one after
  the tour, and the contrast-theme tooltip); "and it gives the icon back"
  says "the button"; a new check: start a sort on the household (F9), press
  Ctrl+1, and `#sort` shows Stop Sorting on the Overview, and a click turns it
  to Stopping.
- `docs/runbook.md` and `README.md` (the runbook is part of a change to what
  the operator sees): every "**Sort** icon" becomes "**Sort Now** button" -
  runbook lines about 451, 908, 1377, 2338 and 2494, README about 126. The
  sentence at about 1377, "The one **Sort** icon beside the search box sorts
  the open return's household (grey on the four pages: open a household
  first)", becomes "The **Sort Now** button beside the search box sorts the
  open household (it is on a household's, year's or return's page; the four
  firm pages have none)". At about 912, "The button becomes **Stop**" becomes
  "The button becomes **Stop Sorting**", and the "**Stop** ends it" after it
  "**Stop Sorting** ends it".

**Keyboard and focus.** The button is in the path row's Tab order after the
search box (as the icon was); F6 to the path row lands on its first button as
today. Enter or Space presses it. F9 is the menu's, unchanged. Hidden, it is
out of the Tab order and the accessibility tree (`display: none`).

**Themes.** `.btn`'s tokens: `--link` words on `--bg-raised` with
`--border-strong` (both themes); Stop Sorting is `--danger` on `--bg-raised`
(6.57 light, 6.89 dark); disabled is `--text-disabled` on `--bg-nav`, as every
disabled button. Contrast theme: `.btn`'s own forced-colors rules.

**SPEC sentences that change.**
- SPEC-shell 3.1 skeleton: "button#sort              icon only; aria-label + data-tip from the API"
  becomes "button#sort              Sort Now, labelled; a household's pages, and any page while a sort runs (P274)",
  and the sprite line loses "sort, stop".
- SPEC-shell 3.4: "`#sort`: a 32 × 32 subtle icon button, 8px after `#find`,
  32px from the window's right edge (the keyline mirrored). Section 8.1."
  becomes "`#sort`: the Sort Now button, 32px tall, secondary, 8px after
  `#find`, 32px from the window's right edge; not drawn on the firm pages or
  the setup page (P274). Section 8.1."
- SPEC-shell 3.8: the list "**search, sort, stop, dismiss, open (chevron),
  next, done, more**" loses sort and stop.
- SPEC-shell 8.1: retitled "The Sort Now button (`#sort`, P274; the icon of
  P60 and P70 is gone)", its table replaced by the table above, and its last
  paragraph becomes "`aria-keyshortcuts=\"F9\"` while it says Sort Now. The
  one Stop is this button, on whatever page is shown while a sort the app
  started runs; the side panel's foot shows progress only (P70's half that
  stands)."
- SPEC-shell 3.5's "nothing on a firm page may send a sort with no return
  chosen" stands as written (a firm page now has no control to send one).

**Tests to add.** `tests/test_shell.py`:
- `test_sort_now_is_a_labelled_button_on_a_households_pages_and_absent_from_the_firm_pages`
  (replaces `test_the_sort_icon_is_stop_while_a_sort_runs_and_grey_on_a_firm_page`):
  `sortState` on household, year and return is `now`, shown, enabled, words
  Sort Now, tip the `sort.tip` words; on the four firm pages and setup it is
  `none`, hidden; locked is shown, disabled, words Sort Now, tip In Use
  Elsewhere.
- `test_stop_sorting_shows_on_every_page_while_this_apps_sort_runs`: with
  `scanning` set, every level (firm pages included) is `stop`, shown,
  enabled; with `stopping`, `stopping`, disabled; a scheduled pass running
  (`shellLastPass.running`) alone changes nothing.
- `test_the_sort_button_keeps_one_width_whatever_it_says`: `drawSort`, lifted
  with a fake DOM, gives the button three `sort-word` spans (Sort Now, Stop
  Sorting, Stopping) once, and in each state exactly one is not
  `aria-hidden`; the CSS stacks them in one grid cell and hides the others
  with `visibility`.
- `test_a_focused_sort_button_that_goes_away_hands_focus_to_the_search_box`:
  the button focused, the route moved to a firm page, `drawSort` moves focus
  to `#find` (to the page when `#find` is disabled).
- `tests/test_api.py`
  `test_the_sort_buttons_words_are_the_apis_and_its_tooltip_says_what_it_sorts`:
  `SCREEN["sort"]` is exactly `now`, `stop`, `locked`, `stopping`, `tip`;
  `tip` is "Sort This Household's Inbox"; each has its `wording-shell.tsv`
  row.

**Pins that change.**
- `test_shell.py` `test_the_skeleton_is_the_specs_and_no_hidden_box_is_used_as_a_variable`:
  its symbol list loses `sort` and `stop`.
- `test_shell.py` `test_every_icon_has_a_name_and_a_tooltip`: the icon-only
  buttons are `{"sheet-close"}`.
- `test_api.py` `test_the_vocabulary_carries_the_menu_the_screen_and_the_short_words`:
  the `sort` key set.
- `test_single_source.py` `test_the_runbooks_189_sentence_is_rewritten`: its
  last line counts the new runbook sentence ("The app's **Sort Now** button
  (Run now) is" and the line after it, as the builder wraps it).
- The `PEOPLE` fixture's `sort` words in `test_shell.py` lose `firm` and gain
  `tip` where a test reads them.

### M8. The type is chosen once, by platform (P280)

**Why.** The type started with Windows' Segoe UI everywhere and reached the
Mac's own face only as a fallback. Choosing it by platform, in one place,
makes a Mac look like a Mac app on purpose and leaves Windows exactly as it
is.

**Behaviour.** On a Mac, every text and heading is set in the system face
(`-apple-system`, which is San Francisco; it picks its own text and display
cuts by size). On Windows and anywhere else, nothing changes: Segoe UI
Variable Text for text, Segoe UI Variable Display for headings, Segoe UI
before them on older Windows.

**How the page knows it is on a Mac.** The app does not pass the platform to
the page today (`preload.js` exposes no platform, and `main.js` keeps
`process.platform` to itself), and the vocabulary arrives too late for the
first paint. The browser's own `navigator` already says it, with no new
channel and no change to `main.js` or `preload.js`:
- `app/renderer/app.js`, right after `const $ = …` (the top, before anything
  draws): a function `appOnMac(nav)` - true when
  `nav.userAgentData && nav.userAgentData.platform` (else `nav.platform`, else
  "") begins with "mac", any case ("macOS" and "MacIntel" both) - and one
  statement, `document.documentElement.classList.toggle("on-mac", appOnMac(navigator));`.
  A comment says P280 and why the class is on `<html>` (the token block reads
  it before the first paint).
- `app/renderer/pilot-ui.css`: the light `:root` keeps `--font-ui` and
  `--font-display` exactly as they are. After the dark block, a new block:
  ```css
  /* P280: a Mac's own face. The one platform switch: app.js puts on-mac on <html>. */
  :root.on-mac {
    --font-ui: -apple-system, system-ui, sans-serif;
    --font-display: var(--font-ui);
  }
  ```
  It sits before the forced-colors block (which stays the file's last rule).
  The type comment at about line 186 and the file's header ("the face is the
  one Windows already has") say P280.
- No other rule names a face: every `font-family` in `pilot-ui.css`,
  `shell.css` and `pilot-style.css` is `var(--font-ui)`, `var(--font-display)`
  or `inherit` (the reminder letter's faces in `style.css` mirror the email
  and are not touched).

**Keyboard and focus.** None.

**Themes.** None (no colour). The harness on this Mac draws the Mac's face
before and after (Segoe UI is not installed here), so the Windows face is
checked in the next Windows check, not in these shots.

**SPEC sentences that change.** SPEC-shell 3.7, after the table: "The face is
one choice per platform (P280): Segoe UI Variable (its Text and Display cuts)
on Windows, the system face on a Mac (`-apple-system`), set only in
`pilot-ui.css`'s token block by the `on-mac` class `app.js` puts on `<html>`
from the browser's own platform." P53's Mac half is superseded; its Windows
half stands.

**Tests to add.**
- `tests/test_shell.py`
  `test_a_mac_is_known_from_the_browsers_own_platform_and_every_other_system_keeps_segoe`:
  `appOnMac` lifted from `app.js` is true for `{platform: "MacIntel"}` and
  `{userAgentData: {platform: "macOS"}}`, false for `{platform: "Win32"}`,
  `{userAgentData: {platform: "Windows"}, platform: "Win32"}`,
  `{platform: "Linux x86_64"}` and `{}`; the `classList.toggle("on-mac", …)`
  statement is top-level in `app.js` and comes before `function applyVocabulary`.
- `tests/test_pilot_ui.py`
  `test_the_face_is_chosen_once_per_platform_in_the_token_block_and_no_rule_names_a_face`:
  the light `:root`'s `--font-ui` begins with "Segoe UI Variable Text"; one
  `:root.on-mac` block, outside every `@media`, sets `--font-ui` beginning
  with `-apple-system` and `--font-display: var(--font-ui)`; it comes before
  the forced-colors block; every other `font-family` in `pilot-ui.css`,
  `shell.css` and `pilot-style.css` is one of the two tokens or `inherit`.

**Pins that change.** None expected: the token tests read `:root` blocks by
the exact selector `:root`, which `:root.on-mac` is not.

---

## 2. Screenshots and measurement (in the handoff, not a test)

The harness (`pilot/harness`, made-up names only; `stub.js`'s Smith Family,
Rivera Design, Ana Lopez and 500 generated households) at **1400 × 900, light
and dark**, before and after:
`HARNESS_PYTHON=build-portable/venv/bin/python PLAYWRIGHT_MODULE=<this Mac's playwright> node pilot/harness/shoot.mjs <out> <scenario ...>`
(it also shoots 1100 × 700; attach the 1400 × 900 ones). **The "before" set is
shot first, from the untouched tree, before any edit.**

Scenarios, and what each shows:

| Scenario | Shows |
|---|---|
| `overview` | the brand band (M2), the Soon tags (M1), one year so no Tax Year column (M4), chevrons at rest (M6), names without underline (M3), no sort button (M7) |
| `overview-two-years` (new) | the Tax Year column back (M4) |
| `reminders`, `needs-review`, `clients` | M3, M4 (Reminders), M6 on each list |
| `household`, `year`, `return` | Sort Now in the path row (M7), chevrons on end-aligned dates (M6) |
| `return-active-row` | the keyboard's active row: step words and the name underlined (M3, M6) |
| `row-hover` (new) | the pointer on the Overview's second row's name: its underline and its step's words |
| `sort-running` | Stop Sorting on a household (M7) |
| `sort-running-firm` (new) | Stop Sorting on the Overview while the app's sort runs (M7) |
| `return-locked` | Sort Now disabled (M7) |
| `tooltip-mouse`, `tooltip-keyboard` | the Sort Now tooltip (M7) |
| `setup` | no sort button; the brand band (M2, M7) |
| `forced-colors` | underlines kept, chevrons and the Soon tags in system colours |

New scenarios: `overview-two-years` is `?scenario=two-years`, a `stub.js`
scenario whose `firm` reply also lists the 2024 returns of the households
that have them (so both the Overview and Reminders hold 2025 and 2024 rows);
`row-hover` hovers `#page .rows .row:nth-child(2) .row-link`;
`sort-running-firm` runs the `sort-running` script and then
`shellGo({ level: "overview" })`.

Also recorded in the handoff: on this Mac, in the harness,
`document.documentElement.classList.contains("on-mac")` is true and
`getComputedStyle(document.body).fontFamily` begins with `-apple-system`;
with an init script that makes `navigator.platform` "Win32" (and
`userAgentData` absent) the class is absent and the family begins with
"Segoe UI Variable Text". `pilot/harness/interact.mjs` runs whole and passes
(M7's new and changed checks). If Playwright is not on this Mac, the handoff
says so plainly and the orchestrator shoots.

**For the next Windows check** (named here so its prompt can list them): the
brand band and the Soon tags at 1100 × 700 in Segoe UI (nothing cut); the
Overview with one year and with two; a row's chevron and its words on hover;
Sort Now, Stop Sorting and its absence on a firm page; the face is Segoe UI
Variable. Test files: `tests/test_shell.py`, `tests/test_pilot_ui.py`.

---

## 3. Scope: one job

**Builder: one sonnet session** builds M1-M8 (M5 as option (c), Jason's
answer of 2026-10-11 to question A; only the (c) lines in M5). It may touch
only:

- `app/renderer/index.html`, `app/renderer/shell.js`, `app/renderer/pages.js`,
  `app/renderer/app.js` (M8's function and statement only),
  `app/renderer/shell.css`, `app/renderer/pilot-ui.css`
- `app/renderer/mark.svg` (new), `app/renderer/logo.svg` (deleted)
- `tracker/api.py` (`SCREEN["side"]` and `SCREEN["sort"]` words only; no
  reply field, no command)
- `pilot/wording-shell.tsv` (the rows named above)
- `tests/test_shell.py`, `tests/test_pilot_ui.py`, `tests/test_api.py` (the
  new tests and the changed pins above), `tests/test_single_source.py` (the
  runbook pin only)
- `docs/runbook.md`, `README.md` (M7's sentences only)
- `pilot/SPEC-shell.md`, `pilot/SPEC-lists.md`, `pilot/SPEC-firm-columns.md`
  (the sentences each item names)
- `pilot/harness/stub.js` (the `two-years` scenario), `pilot/harness/shoot.mjs`
  (the three new scenarios), `pilot/harness/interact.mjs` (M7's checks)

Not touched: `app/main.js`, `app/preload.js`, `app/renderer/sheet.js`,
`app/renderer/tooltip.js`, `app/renderer/tour.js`,
`app/renderer/pilot-content.js` (the tour's Sort step anchors `#sort`; on a
firm page the button is hidden and the tour already centres a step whose
anchor is not drawn), anything else under `tracker/`, `pilot/DECISIONS.md`,
`pilot/HANDOFF.md`, `docs/repo-map.*`.

**The gate it runs** (dead code in the changed files first: unused locals,
the removed `firm` state's leftovers, the `#side-brand-words` and icon-sort
rules; then each test file **as its own process**, under the floor interpreter
and the office's, and the handoff names the two it used or says plainly which
was missing):
`tests/test_shell.py`, `tests/test_pilot_ui.py`, `tests/test_api.py` (the
changed `api.py`'s own), `tests/test_api_entry.py` (`api_entry.py` imports
`api` at call time), `tests/test_shell_menu.py` (the menu's `sort_now` and
the preload stay as they are), `tests/test_pilot.py` (the tour and
`index.html`), `tests/test_single_source.py`, `tests/test_tripwire.py`
(tests changed), `tests/test_layers.py`. Not the engine's tests: no sorting
code changes. After a review's fixes, only the files those fixes touch run
again.

**No commit and no map update by the builder.** It ends with its handoff:
what it built per item, any finding (a cut name, a test it could not make
pass), the before and after shot folders, the font check of section 2, and
the test runs with their counts.

**Review: Opus, high effort, in a session that did not build**, numbered
findings against this SPEC. A finding that survives one rebuild is fixed by
the reviewer's tier. Then the orchestrator: the curated map notes for
`app/renderer/shell.js` (they describe "the sort icon", P60 and P70),
`pages.js`, `app.js` and `index.html`; `python tools/repo_map.py update`;
`python -m ruff check .`; `python tools/repo_map.py check`;
`tests/test_repo_map.py`; one commit citing P265-P268, P270, P274, P280 (and
P269 only if built).
