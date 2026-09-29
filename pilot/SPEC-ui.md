# Pilot 0.2 - Build E: the structure pass (buttons, type, spacing) - SPEC

Status: **written 2026-09-29 for Jason's review.** Decisions P51-P54
(`DECISIONS.md`). Jason asked for the UI to look **minimal and sleek**, with
**structure first: button layout, importance, shape, sizing, font.** Colour
identity stays as P50 left it (the navy design of `style.css`); this pass
changes structure, not the palette.

Read first: [`README.md`](README.md) (rule 1), [`DECISIONS.md`](DECISIONS.md)
(P50-P54), this file. Builders look up renderer files with
`python tools/repo_map.py show <file>` and read only the line ranges named
here; never read `docs/repo-map.md` whole.

## 1. Where the research came from

Forum threads and round-ups scraped on 2026-09-29 (Hacker News on Pico CSS
and classless frameworks; r/webdev, r/ClaudeCode, r/UXDesign on design skills;
the Snyk and Firecrawl 2026 skill round-ups) agree on two things this SPEC
uses:

- **Anthropic's `frontend-design` skill** and **Impeccable**
  (`pbakaus/impeccable`, Apache 2.0) are the design skills people credit most.
  For an app screen (Impeccable's "Operate" mode) they say the same things:
  one well-tuned sans family, a tight fixed type scale (steps of 1.125-1.2),
  a 4px spacing grid, one accent used only for the primary action and the
  current selection, every control with hover, focus, active and disabled
  states, the same button shape everywhere, 150-250ms transitions, no
  decoration that does not carry state.
- **Pico CSS** is the most-praised drop-in library, but the same thread
  criticises its buttons and inputs as too large for data-dense screens, and
  every drop-in library restyles bare elements, which would fight
  `style.css`. So no library is added. The token values below are Microsoft's
  **Fluent 2** sizes (control heights 24/32px, 4px control corners, 8px
  surface corners, the Windows type ramp), written as this app's own CSS
  custom properties: it is a Windows app, and P50 already aligned it with
  Microsoft's guidance.

No third-party file enters the product. (The skills themselves are not
installed in the repository; see P54.)

## 2. The shape of the change (P51, P52)

**One new file, `app/renderer/pilot-ui.css`**, loaded after `style.css` and
before `pilot-style.css`. It redefines the look by overriding `style.css`
selectors. `style.css`, `app.js`, `main.js` and `preload.js` are **not
edited** (README rule 1: the original's files change only where a SPEC names
the lines, so merges from the original stay clean).

Files that change:

| File | Change |
|---|---|
| `app/renderer/pilot-ui.css` | new: sections 3-9 |
| `app/renderer/index.html` | one added line: `<link rel="stylesheet" href="pilot-ui.css" />` between the `style.css` and `pilot-style.css` links |
| `app/renderer/tour.js` | the Next/Finish button gets `btn-primary` (section 5.6) |
| `app/renderer/pilot-style.css` | its literal colours become the tokens of section 3 (section 8) |
| `tests/test_pilot_ui.py` | new: section 10 |
| `tests/test_pilot.py` | only if a test pins the exact stylesheet list: add `pilot-ui.css` to it |
| `docs/repo-map.curated.json` | a node for `pilot-ui.css` (role, layer as for `pilot-style.css`), then `repo_map.py update` |
| `pilot/HANDOFF.md` | the Build E entry |

`pilot-ui.css` must end with its own `@media (forced-colors: active)` block
(section 9), carry no `!important` except inside a `prefers-reduced-motion`
block, no `url(`, no `@import`, no `@font-face`, no "glass" and no
`backdrop-filter`.

## 3. Tokens (`:root` in `pilot-ui.css`)

Existing `style.css` token names are redefined where the value changes, so
every `var(--x)` already in `style.css` picks the new value up. `--bg` keeps
`#f5f7fa` (main.js reads the window colour from `style.css` by regex; the two
must agree).

```
/* type */
--font-ui: "Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
--font-display: "Segoe UI Variable Display", "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
--fs-caption: 12px;  --lh-caption: 16px;
--fs-body: 14px;     --lh-body: 20px;
--fs-subtitle: 16px; --lh-subtitle: 22px;
--fs-title: 20px;    --lh-title: 28px;
--fw-regular: 400;   --fw-strong: 600;

/* space: a 4px grid */
--sp-half: 2px; --sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px;
--sp-5: 20px;  --sp-6: 24px; --sp-8: 32px;

/* shape */
--radius-control: 4px;   /* buttons, inputs, selects, small pills that are not status chips */
--radius: 8px;           /* surfaces: cards, banners, notices, dialogs, toast, tour and terms cards */
--radius-pill: 999px;    /* status chips only */
--ctl-h: 32px; --ctl-h-sm: 24px;

/* colour: the P50 palette, named once */
--navy: #14335c; --navy-deep: #0e2544;
--blue: #2563eb; --blue-dark: #1d4ed8;            /* focus ring and links only */
--text: #0f172a; --muted: #475569;
--subtle: #5a6a80;                                /* was #64748b: 4.43:1 on --bg, now 5.14:1 */
--border: #e2e8f0; --border-strong: #cbd5e1;
--border-input: #7d8ea5;                          /* input bottom edge: 3.34:1 on white (WCAG 1.4.11) */
--surface-hover: #f1f5f9; --surface-pressed: #e2e8f0;
--surface-selected: #e8eef7; --surface-sunken: #f8fafc;
--text-disabled: #94a3b8; --surface-disabled: #f1f5f9;
--danger: #b42318; --danger-hover-bg: #fef3f2; --danger-border: #fda29b;
--ok-bg: #ecfdf5;   --ok-border: #a7f3d0;   --ok-fg: #065f46;
--warn-bg: #fffbeb; --warn-border: #fde68a; --warn-fg: #92400e;
--err-bg: #fef2f2;  --err-border: #fecaca;  --err-fg: #991b1b;
--info-bg: #eff6ff; --info-border: #bfdbfe; --info-fg: #1e3a8a;
--amber: #f59e0b; --amber-deep: #d97706; --amber-soft: #fcd34d;   /* the pilot badge and tour spot */
--shadow: none;                                   /* flat controls and cards */
--shadow-overlay: 0 8px 32px rgba(15, 23, 42, 0.24), 0 2px 8px rgba(15, 23, 42, 0.12);
--ease: cubic-bezier(0.2, 0, 0, 1); --dur: 150ms;
```

Contrast, computed before writing (WCAG ratio): white on navy 12.67; navy on
white 12.67, on hover 11.56, on pressed 10.28, on selected 10.86; danger on
white 6.57, on its hover 6.05; subtle on white 5.51, on bg 5.14; banners 6.84
to 9.52. Disabled text is exempt (WCAG 1.4.3) and is paired with a cursor
change and the `disabled` attribute.

**Rule:** outside `:root`, `pilot-ui.css` writes no hex or `rgb(` colour, no
literal font size, weight or line height, and no padding, margin or gap other
than `0`, a `var(--sp-*)`, or `calc()` of them. The one exception is the
reminder letter (section 7.4).

## 4. Type (P53)

- `body`: `font-family: var(--font-ui)`, `font-size: var(--fs-body)`,
  `line-height: var(--lh-body)` (was 15px / 1.55).
- Headings that name a card or a dialog use `--font-display`:
  `.card-head h3` subtitle (16/22, 600, navy); `.modal h3` title (20/28, 600,
  `--text`); `.pilot-terms-card h2`/`h3` and `.pilot-tour-card h3` the same
  as a dialog title (these live in `pilot-style.css`, section 8).
- **Two weights only:** 400 and 600. Every 700 and `bold` in `style.css`
  and `pilot-style.css` (inventory: 16 + 4) is overridden to 600, and the
  user-agent bold of `th`, `legend`, `strong` in `.assure` and `.modal h3`
  too.
- **Four sizes only:** every size in `style.css` maps to the ramp:
  11 / 11.5 / 12 / 12.5 -> caption 12/16; 13 / 13.5 / 14 / 15 -> body 14/20;
  17 / 18 -> subtitle 16/22 (`.form-num` included); modal and dialog titles
  -> title 20/28.
- Uppercase and letter-spacing go: `.requests th`, `.tmpl-head`,
  `.ed-engagement legend`, `.editor-table th`, `.pilot-badge`,
  `.pilot-tour-card h3` become sentence case, caption size, 600, `--subtle`
  (the badge keeps its own colours, section 8). The words do not change.
- `font-variant-numeric: tabular-nums` on `table.requests`, `.editor-table`,
  `.summary`, `.chip` and any count, so figures line up.
- Letters in the reminder preview keep their own fonts (section 7.4).

## 5. Buttons (P52): one shape, four importances, two sizes

### 5.1 The shape

| | height | padding | text | corner |
|---|---|---|---|---|
| default `.btn` | `min-height: var(--ctl-h)` (32px) | `0 var(--sp-3)` | body 14/20, 600 | `--radius-control` |
| `.btn-small` | `min-height: var(--ctl-h-sm)` (24px) | `0 var(--sp-2)` | caption 12/16, 600 | `--radius-control` |

Both: `display: inline-flex; align-items: center; justify-content: center;
gap: var(--sp-2)` (small: `--sp-1`), `white-space: nowrap`, 1px border,
`box-shadow: none`, `transition: background-color, border-color, color
var(--dur) var(--ease)`. Icons inside are 16px (small: 12px),
`flex-shrink: 0`, stroke `currentColor`. The `.ed-unlearn` override in
`style.css` (2px 6px, 11px) is overridden back to `.btn-small`.

### 5.2 The four importances

| Importance | Who | Rest | Hover | Pressed (`:active`) |
|---|---|---|---|---|
| **Primary** `.btn-primary` | the one main action of a region | navy fill, white text, navy border | `--navy-deep` fill and border | `--navy-deep`, no other change |
| **Secondary** `.btn` | ordinary actions | white fill, `--navy` text, `--border-strong` border | `--surface-hover` fill | `--surface-pressed` fill |
| **Subtle** `.btn-subtle` and the contexts in 5.4 | commands in a bar, Cancel-like exits, links to other places | transparent fill and border, `--navy` text | `--surface-hover` fill | `--surface-pressed` fill |
| **Danger** `.btn-danger` and the hooks in 5.5 | removes, undoes or discards something | white fill, `--danger` text, `--border-strong` border | `--danger-hover-bg` fill, `--danger-border` border | same as hover |

All four: `:focus-visible` is `outline: 2px solid var(--blue); outline-offset:
2px`. **Disabled** is drawn, not faded: `opacity: 1`, `--surface-disabled`
fill, `--text-disabled` text, `--border` border (subtle: transparent fill and
border), `cursor: default`, and hover and active change nothing
(`:disabled:hover` rules repeat the disabled look). This replaces
`opacity: 0.55`.

`.btn-ghost` in `style.css` is dead (used nowhere); leave it (style.css is not
edited) but nothing new uses it.

### 5.3 Selected is not primary

The accent means "the main action". A control that is *selected* gets the
selected look instead: `--surface-selected` fill, `--navy` text, a
`--navy` 1px border, weight 600.

- `.mode-toggle` (review Cards/List) becomes a segmented control: the
  container gets a 1px `--border-strong` border, `--radius-control`,
  `padding: var(--sp-half)`, `gap: var(--sp-half)`; its buttons lose their
  border (transparent) and fill; `.mode-toggle .btn.on` gets the selected
  look (overriding `style.css`'s blue fill).
- The active return in `#household-returns` is marked by `app.js` with
  `btn-primary` (not edited, rule 1). `.household-return .btn.btn-primary`
  gets the selected look.

### 5.4 Where the subtle look comes from, without editing markup

`index.html` and `app.js` are not edited, so the importance comes from
context selectors in `pilot-ui.css`:

- `.toolbar > .btn:not(.btn-primary)` - the whole command bar (section 6),
  except `#btn-stop-pass` (danger).
- `.rem-quiet` (Open the draft file) and `.wiz-back` (the wizard's back
  links): the subtle look at `.btn-small` metrics (they are not `.btn`, so
  every property is set on them).
- `.notice-act[data-act="dismiss"]`: subtle; Retry and Look again stay
  secondary.
- `.pilot-tour-actions` Back and Close: subtle, set in `pilot-style.css`
  under the `.pilot-` prefix (section 8).
- `#pilot-terms-quit` stays secondary (leaving the terms is not destructive).

### 5.5 Danger, without editing markup

These already carry a hook class or id; `pilot-ui.css` gives them the danger
look: `.dlg-discard` (Discard my changes), `.r-unfile` (Unfile),
`.r-withdraw` (Mark missing, both sizes), `.hh-feed-remove`, `.ed-unlearn`,
`.ed-remove .btn` (the editor's per-row Remove), `#btn-unlock` (Clear lock),
`#btn-stop-pass` (Stop). The wizard's per-person Remove (`app.js` ~2946) has
no hook: the builder finds a selector that matches it and nothing else inside
the wizard; if none exists without editing `app.js`, it stays secondary and
the handoff says so.

`.r-dismiss` (Not requested) stays secondary: it sets a file aside and can be
reopened.

### 5.6 The pilot's own buttons

`tour.js` builds Back, Next/Finish and Close as plain `.btn`: Next/Finish
gets `btn-primary` (one-word change in `tour.js`); Back and Close are subtle
(5.4). The terms' Accept is already primary.

### 5.7 Two primaries in one review row

A Needs review row can show both **File it** (`.r-file`) and, in its own
"where it waits" block, **File it under {label}** (`.r-where-it-waits`); a deck
card likewise `.c-accept` and `.c-where-it-waits`. They are two different
answers in two visual blocks, and choosing which one leads is a product
decision, so **both stay primary** in this build; the `.where-it-waits` block
is set apart (section 7.2) so each primary leads its own block. Flagged to
Jason (HANDOFF).

## 6. The command bar and the top bar

### 6.1 Top bar

`.topbar`: `min-height: 48px`, `padding: 0 var(--sp-6)`, solid
`--navy-deep` fill (no gradient). `.brand-logo` height 28px. `.brand-divider`
height 20px. `.brand-product` body 14/20, 400. The pilot badge keeps its
place (section 8).

### 6.2 The toolbar becomes a command bar

DOM order is fixed by tests and is not changed: picker, form pill, view pill,
New household, spacer, Tour, Open Inbox, Open Client Folder, Repair the
schedule, Edit Request List, Schedule, Open Status Report, Open Status,
Sort & Scan, Stop.

- `.toolbar`: `gap: var(--sp-1)`, `min-height: 40px`,
  `padding-bottom: var(--sp-3)`, `border-bottom: 1px solid var(--border)`.
  `flex-wrap: wrap` stays (at the 1100px minimum window width the bar must
  wrap rather than overflow; check it in section 11).
- Every toolbar button except Sort & Scan is **subtle** (5.4) with its 16px
  icon: nine boxed buttons become one quiet row. Sort & Scan is the only
  filled button on the screen's chrome. Stop is **danger** (outlined).
- **Groups by space, not boxes.** The buttons fall in four runs of DOM order:
  *places and upkeep* (Tour, Open Inbox, Open Client Folder, Repair the
  schedule), *the list* (Edit Request List, Schedule), *pages* (Open Status
  Report, Open Status), *the run* (Sort & Scan, Stop). `#btn-edit`,
  `#btn-view` and `#btn-scan` get `margin-left: var(--sp-3)` so each run
  reads as a group (4px inside a run, 16px between runs).
- `#eng-select`: `min-height: var(--ctl-h)`, `min-width: 260px`, body 14/20
  600, `--radius-control`, the input border of section 7.3.
- `#eng-form` and `#view-state` pills: `min-height: var(--ctl-h-sm)`,
  caption 12/16, `padding: 0 var(--sp-2)`, `--radius-control`; their
  `view-*` colours are untouched.

## 7. Surfaces, inputs and rows

### 7.1 Page and cards

- `.main`: `padding: var(--sp-4) var(--sp-6)`, `gap: var(--sp-4)`.
- `.card`: 1px `--border`, `--radius`, no shadow.
- `.card-head`: `padding: var(--sp-3) var(--sp-4)`, `align-items: center`.
  `.summary` caption, `--subtle`.
- `.main > * { flex-shrink: 0 }`: a card never shrinks inside the scrolling
  column. Without it, `.card { overflow: hidden }` lets every card collapse to
  a sliver when notices fill the window (found by the harness, present before
  this build; P55).
- Card bodies whose `style.css` inset is 18px (`0 18px 14px` and the like)
  move to `--sp-4` (16px) on both sides and `--sp-4` at the bottom.

### 7.2 Rows, lists, tables

- `table.requests`: `th` caption 600 `--subtle`, sentence case,
  `padding: var(--sp-2) var(--sp-3)`, 1px `--border` bottom; `td`
  `padding: var(--sp-2) var(--sp-3)`, 1px `--border` bottom; row hover
  `--surface-sunken`. Status chips: `min-height: 20px`,
  `padding: 0 var(--sp-2)`, caption 12/16 600, `--radius-pill`; their colours
  are untouched.
- `ul.review > li` and `.deck-card`: `padding: var(--sp-3) var(--sp-4)`;
  their action buttons sit in a row with `gap: var(--sp-2)`, primary first
  (DOM order already puts it first where it exists).
- `.where-it-waits`: `margin-top: var(--sp-3)`,
  `padding: var(--sp-3)`, `--surface-sunken` fill, 1px `--border`,
  `--radius`, so its primary leads its own block (5.7).
- `.editor-table`: `th` as `.requests th`; cells
  `padding: var(--sp-1) var(--sp-2)`.

### 7.3 Inputs, selects, textareas

`input` (text-like), `select`, `textarea` inside the page: `min-height:
var(--ctl-h)` (not textarea), `padding: 0 var(--sp-3)` (textarea:
`var(--sp-2) var(--sp-3)`), body 14/20, 1px `--border-strong` border with a
`--border-input` bottom edge, `--radius-control`, white fill. Focus:
`outline: 2px solid var(--blue); outline-offset: 0`. Inputs inside
`.editor-table` and `.review` rows: `min-height: 28px`, `padding: 0
var(--sp-2)`. Checkboxes and radios: `accent-color: var(--navy)`,
16px square.

### 7.4 The reminder letter is not restyled

`.rem-preview` and everything inside it mirror the emailed letter
(`tracker.page` fonts, `--rem-*` inks set by `app.js`). `pilot-ui.css` does
not touch their font family, size, weight, line height or colours. The
reminder card's chrome around it (stages, hint, actions) follows this SPEC.
`.rem-stage` buttons keep their `--stage-ink` colouring and get
`min-height: var(--ctl-h)`, `padding: 0 var(--sp-3)`, `--radius-control`,
caption 12/16 600; pressed keeps its inset ring.

### 7.5 Banners, notices, toast

`.banner`, `.notice`: `padding: var(--sp-2) var(--sp-3)`, `--radius`, body
14/20, **400** (was 600; a whole sentence in bold is loud), their `ok` /
`warn` / `err` / `notice-*` colours through the section 3 tokens (same
values). Buttons inside sit at `.btn-small`. `.toast`: `--radius`,
`padding: var(--sp-3) var(--sp-4)`, `--shadow-overlay`, body 14/20.

### 7.6 Dialogs

- `.modal`: `padding: var(--sp-6)`, `--radius`, `--shadow-overlay`, 1px
  `--border`. `.modal h3`: title 20/28 600, `margin-bottom: var(--sp-4)`.
- `.modal-actions`: `justify-content: flex-end; gap: var(--sp-2);
  margin-top: var(--sp-6)`. **`.modal-actions > .toolbar-spacer { display:
  none }`**, so every dialog ends the same way: Cancel, then the primary, at
  the right (today four dialogs push Cancel to the far left and two keep it
  beside Save). Cancel stays secondary.
- `.dlg-unsaved`: Keep editing secondary, Discard my changes danger (5.5).
- `.form-card` tiles (wizard form step): `padding: var(--sp-3) var(--sp-4)`,
  `--radius`, 1px `--border`; hover `--surface-hover` fill and
  `--border-strong` border (no blue); focus ring as buttons. `.form-num`
  subtitle 16/22 600.

### 7.7 Assurances footer

`.assure`: caption 12/16 for the text, 600 for the `strong`,
`gap: var(--sp-4)`.

## 8. `pilot-style.css`

Every literal colour becomes a section 3 token (`#1f2937` -> `--text`,
`#6b7280` and `#4b5563` -> `--subtle`/`--muted`, `#d1d5db` -> `--border-strong`,
`#ffffff` -> `--card`, `#16a34a` -> `--ok-fg`, the
ambers -> `--amber*`). Sizes and spacing follow sections 4 and 5; radii
10px -> `--radius`, 8px -> `--radius`. Tour card and terms card:
`--shadow-overlay`, `padding: var(--sp-6)`. Tour Back and Close are subtle
(`.pilot-tour-actions .btn:not(.btn-primary)`). Selectors keep the
`.pilot-` / `#pilot-` / `#btn-tour` / `.brand` prefix (test-pinned); the
`forced-colors` block stays last. The rgba dims of the overlays may stay as
literals (they are not text colours).

## 9. States, motion, contrast themes

- `@media (prefers-reduced-motion: reduce)`: `style.css` already turns every
  transition off; `pilot-ui.css` adds no animation.
- Hover never moves or resizes anything; only fills, borders and text colour
  change.
- `pilot-ui.css` ends with `@media (forced-colors: active)`: every `.btn`
  variant, `.btn-subtle` context included, gets `border: 1px solid
  ButtonText`; selected controls (`.mode-toggle .btn.on`,
  `.household-return .btn.btn-primary`) get `border: 2px solid Highlight`;
  disabled gets `color: GrayText; border-color: GrayText`; focus
  `outline: 2px solid Highlight`. System colours only, no hex.

## 10. Tests (`tests/test_pilot_ui.py`)

Named as claims, reading the files as text like `test_pilot.py` does:

- `test_the_structure_pass_loads_between_the_app_and_the_pilot`: in
  `index.html`, `href="style.css"` < `href="pilot-ui.css"` <
  `href="pilot-style.css"`.
- `test_the_structure_pass_writes_no_literal_colour_outside_its_tokens`: with
  comments stripped, no `#hex` or `rgb(`/`rgba(` in `pilot-ui.css` outside the
  `:root` block, except `rgba(` inside `--shadow-overlay`.
- `test_the_structure_pass_uses_only_the_type_ramp`: every `font-size`,
  `line-height` and `font-weight` declaration outside `:root` is a
  `var(--fs-*)` / `var(--lh-*)` / `var(--fw-*)`.
- `test_the_structure_pass_uses_only_the_spacing_grid`: every `padding`,
  `margin`, `gap`, `row-gap`, `column-gap` value is made of `0`, `auto`,
  `var(--sp-*)` or `calc()` of them.
- `test_the_structure_pass_leaves_the_letter_alone`: no selector in
  `pilot-ui.css` contains `.rem-preview`.
- `test_the_structure_pass_honours_contrast_themes_last`: the file ends with
  a `forced-colors` block holding system colours only.
- `test_the_structure_pass_adds_no_remote_or_forbidden_thing`: no `url(`,
  `@import`, `@font-face`, `glass`, `backdrop-filter`, and `!important` only
  inside a `prefers-reduced-motion` block.
- `test_the_tour_leads_with_next`: `tour.js` builds Next/Finish with
  `btn-primary`.

## 11. Build order (one commit each, message ends with `[skip ci]`)

1. `pilot-ui.css` with sections 3 and 4, the `index.html` link, the repo-map
   node; `tests/test_pilot_ui.py`.
2. Section 5 (buttons) and `tour.js`.
3. Section 6 (top bar, command bar).
4. Section 7 (surfaces, inputs, rows, dialogs).
5. Section 8 (`pilot-style.css`) and section 9.
6. Rendered checks (section 12), screenshots, gate, `HANDOFF.md`.

## 12. Checks the build must pass

**Rendered, in the cloud's Chromium with the stubbed page** (the harness in
the session scratchpad: `node <scratchpad>/harness/shoot.mjs <outdir>`; made-up
names only, never a client file):

1. Screenshots of every harness scenario before and after, both at
   1366x860 and the main screen at 1100x760, saved as
   `pilot/reviews/ui-screens/before-<scenario>.png` and
   `after-<scenario>.png`.
2. A computed-style sweep over every visible element outside `.rem-preview`:
   every `.btn` is 32px tall and every `.btn-small` 24px (a label that wraps
   is a finding); every font size is 12, 14, 16 or 20px; every weight 400 or
   600; every text colour against its effective background is 4.5:1 or
   better (disabled controls excepted). The sweep script stays in the
   scratchpad; its output goes in the handoff.
3. The toolbar at 1100px wide wraps cleanly (no clipped or overlapping
   buttons), and Sort & Scan is the only filled button in it.
4. `forced-colors: active` and `prefers-reduced-motion: reduce` emulated:
   buttons keep visible borders, focus is visible, nothing animates.
5. No console error on any scenario.

**The gate** (CLAUDE.md): dead code first, `python -m ruff check .`,
`python tools/repo_map.py update` then `check`, and the affected tests under
Python 3.11 and 3.13: `tests/test_pilot_ui.py`, `tests/test_pilot.py`,
`tests/test_tour.py`, `tests/test_single_source.py`, `tests/test_layers.py`,
`tests/test_repo_map.py`, `tests/test_api.py` (it pins toolbar markup).

## 13. Out of scope

Colour palette changes beyond the named tokens; any change to `style.css`,
`app.js`, `main.js`, `preload.js` or the engine; new layout regions, a
sidebar, dark mode, bundled fonts, icons; any wording. Each is a later SPEC
if Jason wants it.
