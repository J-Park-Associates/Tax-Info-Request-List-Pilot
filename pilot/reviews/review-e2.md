# Review E2 - Rebuild E1 (commit `0862c8c`)

Reviewer: the same session that wrote [`review-e1.md`](review-e1.md). It built
nothing in Build E or in Rebuild E1. Date 2026-09-29.

**Verdict: all six E1 findings are fixed. The fix commit adds three new nits and
nothing blocking or should-fix.** The nits are:

- a mirror image of E1's finding 5 on the toolbar's first row;
- one stale screenshot;
- one wrong number in a CSS comment.

## The six E1 findings

### 1. Blocking, a hidden link showed again - **fixed**

- **The flow.** I re-ran `scratchpad/e1/addret.mjs` on the rebuilt page:
  Add a return, then Form 1040. `#wi-household` has class `wiz-back hidden`,
  computed `display: none` and is not visible. Before this fix it was
  `display: flex` and visible.
- **The `.hidden` scan.** `scratchpad/e1/hiddenscan.mjs` finds no element
  shown despite `.hidden` in main, in Add a return, or in the editor. I also
  added `.hidden` to every element in turn. The set of elements that `.hidden`
  cannot hide is now exactly the pre-build set: 33 lines, the same list as
  `b8ad769`. The four elements the build had added to it
  (`#btn-open-draft`, `#wi-back`, `#chosen-form`, `.household-return`) are
  gone from it.
- **Visible layout is unchanged.**
  - `.household-return`, `#chosen-form`, `#wi-back` and `#btn-open-draft` still
    compute `flex` / `inline-flex` when shown, at 24px tall.
  - The sweep reports 0 findings in 11 scenarios.
  - `after-wizard-requests.png` re-renders pixel-identical, and it holds the
    chosen-form row.
- **The new test.** `test_the_structure_pass_never_unhides_a_hidden_element`
  fails when I restore `.rem-quiet, .wiz-back { display: ... }` or add a bare
  `display: flex` in a scratch copy. It also fails on a non-`.pilot-`
  `display` rule appended to `pilot-style.css`.

### 2. Should-fix, Open the draft file looked enabled - **fixed**

I measured with reduced motion, so the readings are not mid-transition.

- **Normal mode:**
  - `#btn-open-draft` (disabled, no draft) is `#94a3b8` on transparent, with
    the default cursor. Hover and press leave it unchanged.
  - Enabled, it is navy with the pointer cursor, and hover gives
    `--surface-hover`.
  - `#wi-back` set disabled is `#94a3b8` with the default cursor, and hover
    leaves it unchanged.
- **Forced-colors:** disabled text and border are GrayText (`rgb(96,0,0)` in
  Chromium's emulated palette) at rest, on hover and on press. Enabled, the
  border is ButtonText, and on hover it stays visible.

### 3. Should-fix, "contrast themes last" did not check last - **fixed**

I ran each mutation against the new test in a scratch copy
(`scratchpad/e1/mut2`). The new test fails on every one:

- a multi-line rule appended after the block;
- a single-line rule appended after the block;
- a second forced-colors block at the end;
- GrayText present only in a comment;
- a hex inside the block.

The current file passes.

### 4. Nit, three tests narrower than their names - **fixed**

Each of these now fails the right test:

- **Colour:** `color: red`, `border: 1px solid white`, `background: navy`,
  `box-shadow: 0 0 0 2px black`, `outline: 2px solid blue` and `hsl(...)`.
- **Type ramp:** `font: 700 15px/1.5 sans-serif`.
- **Spacing grid:** `padding-inline-start: 18px`, `inset: 3px` and
  `inset-block-start: 3px`.
- **`!important`:** `!important` inside `:root`.

Two things still pass, and neither is a regression or in the SPEC's scope:

- `scrollbar-color: red white`. It is not in `COLOUR_PROPS`, and the file
  does not use it.
- `top: 3px`. It is not a spacing property in SPEC 3.

The tightened tests accept everything in the current files, under both
Pythons.

### 5. Nit, a wrapped toolbar row started 12px in - **fixed**

- **Left edges.** `scratchpad/e1/rows.mjs` checks every width from 1100 to
  1920 in 4px steps. No row starts anywhere but flush left. This matches
  `b8ad769`.
- **Group spacing.** Status to Sort & Scan is 16px (4 gap + 12 margin), the
  same as SPEC 6.2. Sort & Scan to Stop is still 4px. Stop's spacing has not
  changed.
- **Screenshots** at 1100, 1366, 1440, 1536 and 1920: `shots/tb2-after2-*.png`.
- The move to `margin-right` has a side effect on the first row's right edge.
  That is new finding 1.

### 6. Nit, docs - **fixed**

- README rule 1 now names `pilot-ui.css` and counts five `index.html` lines,
  saying which SPEC names each.
- `SPEC.md:966` notes the fifth line and `SPEC-ui.md`.
- The HANDOFF deviations record the terms card's body-size `h3`.
- The "Rebuild E1" paragraph describes the six fixes accurately, with one
  exception about the screenshots. That is new finding 2.

## New findings

### 1. NIT - the toolbar's first row now ends 12px short of the right edge

- **SPEC:** 6.2 and 12.3.
- **Where:** `app/renderer/pilot-ui.css:358`
  (`#btn-repair-schedule, #btn-schedule, #btn-status { margin-right: var(--sp-3) }`).
- **What is wrong:**
  - The first row holds the `.toolbar-spacer`, which pushes that row's buttons
    to the right edge. So when the last button on that row is one that
    carries the new right margin, the margin shows as a 12px inset.
  - With the fallback font, that happens at 1396-1592px (1440 and 1536
    included), where Repair the schedule ends the row, and at 1724-1920px
    (1920 included), where Schedule ends it.
  - Before the fix, that row ended flush with the toolbar's rule. The rows
    below are left-aligned, so their trailing margin is invisible, as
    intended.
  - This is E1's finding 5 moved from the left edge of row 2 to the right edge
    of row 1. It is smaller, because nothing in that row lines up with the
    bar's right end except the rule and the notices below it.
- **Failure scenario:** On a 1920x1080 or 1536x864 screen, the top-right
  command ("Schedule" or "Repair the schedule") stops 12px short of where the
  cards and notices below it end (`shots/tb2-after2-1920.png`,
  `tb2-after2-1536.png`).
- **Fix:** CSS alone cannot tell which button ends a wrapped line, so neither
  a left margin nor a right margin is flush at both ends. A flush result needs
  a divider element between runs, which is markup and so a SPEC line.
  I recommend accepting the 12px inset: the label already sits 12px inside
  its own transparent box, and a right-edge inset is less visible than the
  left-edge indent it replaced. Note it in the HANDOFF next to finding 5 so
  the next reviewer does not report it again. Jason's look at Segoe UI
  Variable widths decides whether it ever shows.

### 2. NIT - `after-review-cards.png` still shows the enabled-looking draft link

- **SPEC:** 12.1 (after screenshots of every scenario).
- **Where:** `pilot/reviews/ui-screens/after-review-cards.png`, and the
  HANDOFF "Rebuild E1" closing paragraph ("only `after-main-1366x860.png` and
  `after-main-1100x760.png` changed").
- **What is wrong:**
  - The review-cards scenario is full height and includes the Reminder card.
  - Re-rendered from `0862c8c`, it differs from the committed file only in
    the box (1190,2430)-(1316,2443): the "Open the draft file" label.
  - The committed image shows the old navy look. The fresh render shows the
    fixed disabled grey (`scratchpad/e1/rc-draft.png`).
- **Failure scenario:** Jason, or the next reviewer, compares the before and
  after sets and sees a disabled control drawn as enabled in the after set,
  which the code no longer does.
- **Fix:** Regenerate `after-review-cards.png`
  (`node <scratchpad>/harness/shoot.mjs <out> --only review-cards`) and
  commit it, then correct the HANDOFF sentence to name three changed
  screenshots.

### 3. NIT - the run-gap comment says 12px; the gap is 16px

- **SPEC:** 6.2 ("4px inside a run, 16px between runs").
- **Where:** `app/renderer/pilot-ui.css:354-357`.
- **What is wrong:** The rewritten comment says "4px inside a run, 12px
  between runs". The 12px margin adds to the toolbar's 4px gap, so the
  distance between runs is 16px, as the SPEC asks and as measured (Status to
  Sort & Scan: 16px). The old comment said 16px.
- **Failure scenario:** A later edit trusts the comment and bumps the margin
  to `--sp-4` to reach a "missing" 16px, which makes the runs 20px apart.
- **Fix:** Say "16px between runs (the bar's 4px gap plus a 12px right margin
  on the last button of the run before)".

Nothing else is new. I also checked the following, and each is sound:

- Guarding `display` under `:not(.hidden)` drops no layout the elements need:
  alignment, gap and padding stay on the plain selectors.
- Specificity changes nothing: `.household-return:not(.hidden)` and
  `.chosen-badge:not(.hidden)` are (0,2,0), and nothing in `style.css`
  competes with them.
- The forced-colors additions are system colours only.
- The `pilot.js` / `tour.js` / `pilot-content.js` guard in the new test
  (`\.hidden\b` or a quoted `hidden`) holds today. It also covers the `hidden`
  attribute route, which author `display` rules would override just the same.

## Gate

- `ruff check .`: clean.
- `repo_map.py check` before my commit: current, 198 nodes.
- Test results, under 3.11.15 and then 3.13.12:

  | Test file | Tests | Result |
  |---|---|---|
  | `test_pilot_ui` | 10 | pass |
  | `test_pilot` | 15 | pass |
  | `test_layers` | 29 | pass |
  | `test_repo_map` | 80 | pass |
  | `test_single_source` | 167 | all pass, exit 1 |

- `test_single_source`'s exit 1 is only the decision-185 tripwire in
  `test_the_app_opens_one_window`. I showed in E1 that it happens on the
  pre-build tree with a `.venv` beside it, so it does not come from this work.
- The re-rendered screenshots and the sweep show no console error and 0
  findings.
