# Pilot 0.2 - Build D: the glass theme - SPEC

> **WITHDRAWN (P50, 2026-09-29). Nothing in this file is built.** Jason removed
> the glass theme entirely (refraction P49, then glass itself); the pilot keeps
> its original navy design. Kept only as the record of what was tried and why.


Status: **revised 2026-09-29 for Jason's approval.** Decisions P30-P45
(`DECISIONS.md`). Jason's answers: the backdrop is a **soft navy gradient**;
**light mode only** for 0.2, dark mode later (P31). After seeing the first
preview he asked for **more transparent glass, a 3D effect and movement
animations** (P41), then for every click and movement to be **optimised for
efficiency and speed** (P45); this revision builds both in.

Read first: [`README.md`](README.md), [`SPEC.md`](SPEC.md) sections 2, 3, 5, 6
and 9 (the page rules this build still obeys), and this file. Builders look up
`app/renderer/index.html`, `style.css`, `pilot-style.css` and `app.js` with
`python tools/repo_map.py show <file>` and read only the line ranges named
here.

**Naming rule.** The product calls this the **glass theme** and nothing else.
No Apple name, logo or the term "Liquid Glass" appears in any tracked file the
build adds or changes, the tester guide included. (This SPEC and the decision
log may say where the idea came from; the product may not.)

**Reference preview.** The look below was prototyped on 2026-09-29 as a
scratch mock-up (made-up names, the app's own `style.css` and
`pilot-style.css` plus a draft `glass.css` and `glass.js`) and screenshotted in
the cloud's Chromium. The values in this SPEC are the prototype's. The
prototype files are not committed; the builder rebuilds from this SPEC.

## 1. What this is

The app's screen gets translucent glass for the things that float - the
header bar, the toolbar, the dialogs, the pilot terms screen, the tour card and
the three action cards - over a soft navy backdrop. The glass is thin: the
backdrop and whatever scrolls behind it show through clearly, softened by
blur. It has **depth**: a lit rim bright at the top-left and dim at the
bottom-right, a light inner glow along the top edge, a faint inner shade along
the bottom, and a two-layer drop shadow. It **moves**, fast: buttons lift and
press with a small spring, cards and dialogs settle into place in a fifth of a
second, the toolbar deepens its shadow once the page scrolls, and at the top
quality level a soft light follows the pointer, the backdrop drifts slowly and
the glass bends it at the rim. Every movement was measured for speed before
this SPEC was merged (P45, section 7.3).

Corners are **concentric**: a shape nested inside another's corner has the
container's radius minus the gap between them, drawn as a continuous
(superellipse) curve. Lists and document tables stay solid white so rows,
chips and figures read exactly as they do today.

It is CSS, one small script, one image and a few lines of markup. It changes
no behaviour of the tracker and no word the tracker shows.

### Non-goals (do not build)

- Dark mode (P31: later, with its own token column).
- Any change to `app.js`, `main.js`, `preload.js`, `style.css`, anything under
  `tracker/`, or any IPC channel. The theme overrides from its own files (P32).
- 3D tilt or perspective rotation of any surface, parallax, or motion tied to
  scroll position beyond the toolbar's one shadow change (P43: a work screen
  must keep still under the reader's eye).
- Animating `backdrop-filter`, `width`, `height`, `top`, `left` or `padding`
  (each re-blurs or re-lays-out the page every frame).
- Glass on the toast, the banners, the notices, the household card, the filed
  card, the setup card, tables, lists, inputs or chips.
- Changing the window's own frame, or Electron's `transparent`/`vibrancy`
  window options (those need `main.js`, and Windows draws its own frame).
- A photo or image backdrop.

## 2. Verified platform facts

Checked 2026-09-29 against the code and the release notes:

| Fact | Where |
|---|---|
| The app runs Electron `43.7.1` | `app/package.json` |
| Electron 43 ships **Chromium 150** | electronjs.org/blog/electron-43-0 |
| `backdrop-filter` (blur, saturate, brightness) | Chromium 76+ |
| `backdrop-filter: url(#id)` running an SVG filter, `feDisplacementMap` included, on the backdrop | Chromium only; this app never runs elsewhere |
| `corner-shape` with `superellipse(K)` (`K = 1` round, `2` "squircle") | Chromium 139+ |
| `@starting-style` and `transition-behavior: allow-discrete` (entry transitions for an element leaving `display: none`) | Chromium 117+ |
| `mask-composite: exclude` (the lit rim) | Chromium 120+ |
| `@media (prefers-reduced-transparency: reduce)`, which Windows turns on when Settings > Personalization > Colors > **Transparency effects** is off | Chromium 118+ |
| `prefers-reduced-motion` (Windows Settings > Accessibility > Visual effects > **Animation effects** off), `prefers-contrast`, `forced-colors` | long supported |
| `style.css` already stops every animation and transition under `prefers-reduced-motion: reduce` (`* { animation: none !important; transition: none !important; }`) | `style.css` ~line 697 |
| The cloud's Playwright Chromium is 141 (>= 139), enough for every check here, and it records video | `/opt/pw-browsers` |
| CSP: `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'` | `index.html` line 9 |
| `main.js` reads `--bg` from `style.css` for the window's first-paint colour; untouched, so the window flashes `#f5f7fa` for one frame before the backdrop paints | `main.js` `pageBackground()` |

## 3. Files, load order and the exact `index.html` lines

New files (all pilot files, P7):

| File | What it is |
|---|---|
| `app/renderer/glass.css` | Every rule, token and animation of the theme. Loaded **last**, after `style.css` and `pilot-style.css`, so it wins on equal specificity. |
| `app/renderer/glass.js` | Sets the quality level on `<html>`, builds the "Screen effects" picker, moves the pointer light and marks the scrolled state (section 7.1). |
| `app/renderer/glass-lens.png` | The refraction's displacement map (section 6.3), made by `pilot/make_glass_lens.py`. |
| `pilot/make_glass_lens.py` | Writes `glass-lens.png` with the standard library only (`zlib`, `struct`). Own CLI; run once, output committed. |
| `tests/test_glass.py` | Section 10. |

Changed pilot files: `pilot-content.js` (the `glass` wording block and
`edition.version` `"0.2"`), `tour.js` (the spot follows its anchor's corner,
section 5.5), `pilot-style.css` (one declaration, section 5.5),
`tests/test_pilot.py` (the key set and `PILOT_JS`), `tests/test_tour.py`
(one test), `pilot/Tester Guide.md` (section 8.2),
`docs/repo-map.curated.json` (roles for the new files).

**`index.html` - add exactly these lines, move nothing (P40).** Line numbers are
today's (`sha256 af23b4a0...`):

1. After line 12 (`  <link rel="stylesheet" href="pilot-style.css" />`):
   ```
     <link rel="stylesheet" href="glass.css" />
   ```
2. After line 14 (`<body>`), the refraction filter, markup only:
   ```
     <svg class="glass-defs" width="0" height="0" aria-hidden="true" focusable="false">
       <filter id="glass-refract" x="0" y="0" width="1" height="1" color-interpolation-filters="sRGB">
         <feImage href="glass-lens.png" preserveAspectRatio="none" result="lens" />
         <feDisplacementMap in="SourceGraphic" in2="lens" scale="20" xChannelSelector="R" yChannelSelector="G" />
       </filter>
     </svg>
   ```
3. After `  <script src="tour.js"></script>` (today line 680):
   ```
     <script src="glass.js"></script>
   ```

Why inline markup (P35): an SVG `<filter>` is neither script nor style, so the
CSP allows it; `backdrop-filter: url(#glass-refract)` resolves a same-document
id reliably in Chromium, while a reference into an external `.svg` document
from `backdrop-filter` is not something the CSP or Chromium promise. The map
is a file under `img-src 'self'`. **Fallback, only if the builder's rendered
check (section 11, step 2) shows the `feImage` file does not load inside a
backdrop filter:** put the same PNG bytes in the `href` as
`data:image/png;base64,...`, which `img-src ... data:` also allows, and record
that in the handoff.

`.glass-defs` in `glass.css`: `position: absolute; width: 0; height: 0;
overflow: hidden;`.

## 4. Tokens (light mode only, P31)

All tokens sit in `glass.css` in `:root` (the Standard level), re-set by
`:root.glass-full`, `:root.glass-solid` and the fallback blocks (section 8.1).
**No colour literal appears anywhere else in `glass.css`** (P33; tested).
Values not listed in a level's column are the Standard value.

### 4.1 Backdrop (P31)

```
--glass-backdrop:
  radial-gradient(55% 45% at 12% 4%, rgba(127, 166, 217, 0.55), transparent 70%),
  radial-gradient(45% 40% at 90% 12%, rgba(255, 255, 255, 0.22), transparent 70%),
  radial-gradient(60% 50% at 70% 85%, rgba(127, 166, 217, 0.35), transparent 70%),
  linear-gradient(180deg, #14335c 0px, #2c4d78 160px, #b7c6d9 420px, #e6ecf3 640px, #f3f6fa 100%);
```

Applied as `body { background: var(--glass-backdrop) #f3f6fa; }`. The body does
not scroll (`.main` does), so the backdrop is fixed to the window: navy behind
the header and toolbar, fading to light slate behind the cards, with three soft
glows for the glass to catch. The backdrop stays at every level, Solid
included. At the Full level the glows move to their own layer and drift
(section 7.2): `:root.glass-full body` keeps only the linear gradient, and
`:root.glass-full body::before` (`position: fixed; inset: -8%; z-index: -1;
pointer-events: none; will-change: transform;`) carries the three radial
glows. Moving that layer by `transform` never repaints the page.

### 4.2 Glass surfaces (P41)

| Token | Standard / Full | Solid and fallback | Used for |
|---|---|---|---|
| `--glass-tint-bar` | `rgba(14, 37, 68, 0.50)` | `#14335c` | header bar |
| `--glass-tint` | `rgba(255, 255, 255, 0.55)` | `#ffffff` | action cards |
| `--glass-tint-toolbar` | `rgba(255, 255, 255, 0.60)` | `#ffffff` | toolbar (cards and lists scroll under it, so a little more body) |
| `--glass-tint-strong` | `rgba(255, 255, 255, 0.65)` | `#ffffff` | dialogs, terms card, tour card |
| `--glass-control` | `rgba(255, 255, 255, 0.45)` | `#ffffff` | toolbar controls (not `.btn-primary`) |
| `--glass-control-hover` | `rgba(255, 255, 255, 0.65)` | `#f1f5f9` | their hover |
| `--glass-control-gloss` | `linear-gradient(180deg, rgba(255, 255, 255, 0.35), rgba(255, 255, 255, 0))` | `linear-gradient(#ffffff, #ffffff)` | convex sheen on every toolbar control, `.btn-primary` included |
| `--glass-control-edge` | `rgba(255, 255, 255, 0.70)` | `#e2e8f0` | toolbar controls' border |
| `--glass-rim` | `linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.20) 35%, rgba(255, 255, 255, 0.05) 60%, rgba(255, 255, 255, 0.65))` | `linear-gradient(#e2e8f0, #e2e8f0)` | the lit rim (5.6) |
| `--glass-edge-bar` | `rgba(255, 255, 255, 0.18)` | `rgba(255, 255, 255, 0.18)` | the header's bottom border |
| `--glass-depth` | see below | `0 1px 3px rgba(15, 23, 42, 0.08)` | toolbar, cards |
| `--glass-depth-strong` | see below | `0 20px 50px rgba(15, 23, 42, 0.35)` | dialogs, terms, tour, the scrolled toolbar |
| `--glass-depth-bar` | `inset 0 -1px 0 rgba(255, 255, 255, 0.10), 0 6px 20px rgba(15, 23, 42, 0.18)` | `none` | header |
| `--glass-depth-inner` | `0 1px 0 rgba(255, 255, 255, 0.60), inset 0 1px 3px rgba(15, 23, 42, 0.08)` | `none` | the solid lists inside cards: set into the glass |
| `--glass-sheen` | `rgba(255, 255, 255, 0.45)` | `transparent` | the pointer light, drawn at the Full level only (7.2, P45) |
| `--glass-halo` | `0 0 10px rgba(255, 255, 255, 0.55)` | `none` | `text-shadow` on text sitting on light glass |

```
--glass-depth:
  inset 0 1px 0 rgba(255, 255, 255, 0.85),         top edge catch-light
  inset 0 -1px 0 rgba(255, 255, 255, 0.30),        bottom edge
  inset 0 12px 24px -16px rgba(255, 255, 255, 0.90), inner glow along the top
  inset 0 -14px 24px -18px rgba(15, 23, 42, 0.22),   inner shade along the bottom
  0 2px 6px rgba(15, 23, 42, 0.08),                near shadow
  0 18px 44px rgba(15, 23, 42, 0.22);              far shadow
--glass-depth-strong:
  inset 0 1px 0 rgba(255, 255, 255, 0.90),
  inset 0 -1px 0 rgba(255, 255, 255, 0.30),
  inset 0 16px 32px -20px rgba(255, 255, 255, 0.95),
  inset 0 -18px 30px -22px rgba(15, 23, 42, 0.25),
  0 4px 12px rgba(15, 23, 42, 0.12),
  0 32px 80px rgba(15, 23, 42, 0.40);
```

(The words after each line above are notes for the reader, not CSS.)

### 4.3 Text on glass (P42)

Thinner glass lets more navy through, so the app's mid-greys no longer pass on
it. Inside every glass surface the sheet re-points the app's own variables,
so `style.css`'s rules keep working and nothing there is edited:

| Token | Value | Replaces inside glass |
|---|---|---|
| `--glass-secondary` | `#1e293b` | **both** `--muted` (was `#475569`) and `--subtle` (was `#64748b`); secondary lines are told apart by size and weight, as they already are, not by a lighter grey |
| `--glass-accent` | `#172554` | `--blue` (text, outlines, `.btn-primary` fill) |
| `--glass-accent-dark` | `#0f1a3d` | `--blue-dark` |
| `--glass-ok` | `#052e16` | the tour's ✓ (`#16a34a` in `pilot-style.css`) |
| `--glass-warn` | `#451a03` | the tour's ! (`#d97706`) |
| `--glass-on-bar` | `#ffffff` | header text |
| `--glass-on-bar-soft` | `#f1f5f9` | the product name beside the logo (was `#cbd5e1`; `#e2e8f0` misses 4.5:1 by a hair on the thinner bar) |

`--text` (`#0f172a`) and `--navy` (`#14335c`) are unchanged. The literal greys
`pilot-style.css` types for the tour and terms (`#6b7280`, `#4b5563`,
`#1f2937`) are restyled in `glass.css` to `var(--glass-secondary)` or
`var(--text)` by the pilot selectors that set them (the rendered sweep,
section 11, finds any the list misses). Text sitting directly on light glass
gets `text-shadow: var(--glass-halo)`, a faint light halo that keeps letters
crisp over a busy backdrop; the halo is never counted in the contrast proof.
Solid lists, inputs, `.btn-primary` and chips get `text-shadow: none`.

Worst-case contrast with the section 10.2 model:

| Surface | text | navy | secondary | accent | ok | warn | on-bar | on-bar-soft |
|---|---|---|---|---|---|---|---|---|
| card (0.55) | 7.1 | 5.0 | 5.8 | 5.8 | 5.9 | 5.9 | - | - |
| toolbar (0.60) | 7.5 | 5.3 | 6.1 | 6.2 | 6.2 | 6.3 | - | - |
| strong (0.65, over the 0.60 dim) | 8.2 | 5.8 | 6.7 | 6.8 | 6.9 | 6.9 | - | - |
| control on toolbar | 11.5 | 8.1 | 9.4 | 9.4 | 9.6 | 9.6 | - | - |
| bar (0.50) | - | - | - | - | - | - | 5.5 | 5.1 |

Every pair clears WCAG AA's 4.5:1 for normal text. White on `--glass-accent`
(`.btn-primary`) is 14.7:1. These figures were computed with this exact
model (saturation 1.6 and brightness 1.04 included) before the SPEC was
written.

### 4.4 Blur, saturation and the filters

| Token | Standard | Full | Solid / fallback |
|---|---|---|---|
| `--glass-blur` | `14px` | `14px` | - |
| `--glass-blur-strong` | `22px` | `22px` | - |
| `--glass-saturate` | `1.6` | `1.6` | - |
| `--glass-brightness` | `1.04` | `1.04` | - |
| `--glass-filter` | `blur(var(--glass-blur)) saturate(var(--glass-saturate)) brightness(var(--glass-brightness))` | same | `none` |
| `--glass-filter-strong` | the same with `--glass-blur-strong` | same | `none` |
| `--glass-filter-refract` | `var(--glass-filter)` | `url(#glass-refract)` then the `--glass-filter` chain | `none` |
| `--glass-filter-refract-strong` | `var(--glass-filter-strong)` | `url(#glass-refract)` then the `--glass-filter-strong` chain | `none` |

Less blur than the first draft (14 / 22 instead of 16 / 28) keeps shapes behind
the glass recognisable, which is what makes thin glass read as glass. Every
glass rule writes `backdrop-filter: var(--glass-filter...)`; only the tokens
change between levels, so `url(#glass-refract)` is typed only inside
`:root.glass-full` (tested).

### 4.5 Radii, padding and the corner shape

| Token | Value | Note |
|---|---|---|
| `--glass-corner` | `superellipse(1.5)` | continuous corner; 1 is a circle arc, 2 a squircle. Jason may tune it within 1.2-2.0 at acceptance; the radii do not change |
| `--r-min` | `6px` | no nested corner is smaller |
| `--r-card` | `20px` | action cards and every other `.card` |
| `--pad-card` | `12px` | glass action cards only |
| `--r-card-inner` | `8px` | = max(6, 20 - 12) |
| `--r-toolbar` | `26px` | |
| `--pad-toolbar` | `6px` | |
| `--h-toolbar-control` | `40px` | toolbar buttons and the engagement select |
| `--r-toolbar-control` | `20px` | = max(6, 26 - 6) = 40 / 2, an exact capsule |
| `--r-dialog` | `28px` | `.modal`, terms card |
| `--pad-dialog` | `20px` | (was `22px 24px`) |
| `--r-dialog-inner` | `8px` | = max(6, 28 - 20) |
| `--r-tour` | `24px` | tour card |
| `--pad-tour` | `16px` | |
| `--r-tour-inner` | `8px` | = max(6, 24 - 16) |
| `--r-capsule` | `999px` | chips, tour stage pills, the pilot badge |

`corner-shape: var(--glass-corner)` is set on every element `glass.css` gives
a radius to, and on the rim ring, at every level (the Solid fallback keeps it,
P36).

### 4.6 Motion (P43)

| Token | Value | Used for |
|---|---|---|
| `--glass-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | button lift and release (a small overshoot) |
| `--glass-settle` | `cubic-bezier(0.2, 0.9, 0.3, 1.05)` | cards and dialogs arriving (barely overshoots, so it reads as done at once) |
| `--glass-t-press` | `50ms` | press down: the button answers within the frame the pointer goes down |
| `--glass-t-control` | `140ms` | hover lift, release; hover colour and shadow `120ms` (`--glass-t-hover`) |
| `--glass-t-fade` | `90ms` | a dialog's opacity in; the dim behind it `120ms` (`--glass-t-dim`) |
| `--glass-t-settle` | `200ms` | dialogs and terms settling; cards `180ms` (`--glass-t-card`) |
| `--glass-t-spot` | `160ms` | the tour spot gliding to its next anchor |
| `--glass-drift` | `40s` | one sweep of the backdrop drift (Full only) |

No duration except the drift exceeds 200ms (tested). The first draft's were up
to 460ms; the preview measured a dialog taking about 200-240ms to become
readable with them and about 100-130ms with these (7.3).

## 5. The concentric rule

**Rule.** A shape whose corner sits inside its container's corner - inset by
the container's padding on both sides - takes
`inner radius = max(--r-min, outer radius - gap)`. Where the two paddings
differ, the gap is the smaller one. All nested shapes share one
`--glass-corner`, so the curves stay parallel. A shape that does not sit in a
corner (a chip mid-row, a button mid-toolbar-row) is not bound by the rule and
takes its own shape: a capsule for chips, the toolbar control radius for
toolbar controls (which also happens to be concentric, 5.2).

`glass.css` writes the derived tokens as numbers, not `calc()`, so the test can
check the arithmetic (section 10, `test_nested_corners_are_concentric`).

### 5.1 The window

Windows 11 rounds the app window's corners at **8px** and draws them itself;
Windows 10 draws square corners. The header bar is flush with the window
(gap 0), so its top corners are `8 - 0 = 8` - exactly what Windows already
clips - and `glass.css` gives the header radius 0. Nothing else sits within
8px of a window corner (`.main` has 20-24px padding), so the rule gives
`max(6, 8 - 24) = 6`, i.e. no relation. Each floating surface starts its own
chain.

### 5.2 The toolbar and its buttons

Toolbar: radius 26, padding 6. A button whose corner sits in the toolbar's
corner: `max(6, 26 - 6) = 20`. Toolbar controls are 40px tall, so 20 is half
their height: a capsule concentric with the bar. When the toolbar wraps to two
rows it is a rounded rectangle of radius 26 and the corner controls still sit
6px in.

### 5.3 A card and what is inside it

Glass action card: radius 20, padding 12. The solid list inside it
(`#review-list`, `#moved-list`, `#review-deck`, `#dismissed-card`, the reminder
preview `.rem-preview`, the reminder stages `.rem-stages`): `max(6, 20 - 12) = 8`,
set into the glass with `--glass-depth-inner`. Rows inside the solid list run
edge to edge (square), as today. The card head sits in the padding on the
glass. Solid cards (household, filed, setup) keep no padding, as today, and
take radius 20.

### 5.4 A chip and a button in a dialog

Chip: 22px tall, capsule `999px`. It sits mid-row, never in a corner, so the
rule does not bind it. A capsule is its own shape and is kept even if a chip
ever lands in a corner - stated so no builder "fixes" it.

Dialog: radius 28, padding 20. Its action buttons sit in the bottom corners:
`max(6, 28 - 20) = 8`. Inputs, selects and the editor's tables inside a dialog:
8. The editor (`.modal-wide`) is the same. Terms card: 28 / 20 / 8. Tour card:
radius 24, padding 16, inner (its buttons, the compare columns) 8.

### 5.5 The tour spot (outward)

The spot is 6px larger than its anchor on every side, so it is the anchor's
container: `spot radius = anchor radius + 6`. A toolbar button (20) gets a 26px
spot; a card (20) gets 26; a dialog button (8) gets 14. `tour.js` reads
`getComputedStyle(anchor).borderTopLeftRadius` when it places the spot and sets
`spot.style.setProperty("--pilot-spot-radius", (r + 6) + "px")` (section 2 of
`SPEC.md` allows `style.setProperty` for the spotlight). `pilot-style.css`'s
`.pilot-tour-spot` changes `border-radius: 8px` to
`border-radius: var(--pilot-spot-radius, 8px)`. `glass.css` adds
`corner-shape: var(--glass-corner)` to the spot. The spot's existing
`transition: all .2s` makes it glide between anchors; `glass.css` narrows it to
`transition: top, left, width, height, border-radius` over
`var(--glass-t-spot)` with `var(--glass-settle)` (the spot is a
position-fixed box of its own, so moving it re-lays-out nothing else).

### 5.6 The lit rim (P41)

Every light glass surface draws a 1px ring with a `::before`:

```
position: absolute; inset: 0; padding: 1px;
border-radius: inherit; corner-shape: var(--glass-corner);
background: var(--glass-rim);
-webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
-webkit-mask-composite: xor; mask-composite: exclude;
pointer-events: none;
```

The surface itself gets `position: relative` (the toolbar is already sticky,
the tour card fixed) and `border: 0`, and the ring is its outermost pixel,
inside the padding box. It must not sit outside at `inset: -1px`: `.card` has
`overflow: hidden`, which clips at the padding box, so a ring outside it would
vanish on the three cards. Dropping the 1px border shrinks nothing visible,
since the ring takes its place. The gradient runs bright at the top-left, nearly clear
across the middle and half-bright at the bottom-right: light catching the
edge of a thick pane. **Before adding a `::before`, the builder checks the
target has none today** (`grep` the selector in `style.css` and
`pilot-style.css`); none of the section 6.1 surfaces does as of 2026-09-29. The
tour card, which is repositioned every step, gets no rim (its depth shadow
carries it).

## 6. What becomes glass, what stays solid

### 6.1 The table

| Element (selector) | Treatment | Tint | Filter token | Depth | Radius | Padding |
|---|---|---|---|---|---|---|
| Header `.topbar` | glass, dark | `--glass-tint-bar` | `--glass-filter` | `--glass-depth-bar` | 0 | as today |
| Toolbar `.toolbar` | glass, **sticky** at `top: -20px` (P37, 6.2), rim | `--glass-tint-toolbar` | `--glass-filter-refract` | `--glass-depth` (`-strong` once scrolled, 7.2) | `--r-toolbar` | `--pad-toolbar` |
| Toolbar controls `.toolbar .btn`, `.toolbar #eng-select` | convex glass control | `--glass-control-gloss` over `--glass-control` | none (sits on glass) | `inset 0 1px 0 rgba(255,255,255,.9), inset 0 -1px 2px rgba(15,23,42,.10), 0 1px 3px rgba(15,23,42,.12)` (a token, `--glass-depth-control`) | `--r-toolbar-control` | height `--h-toolbar-control` |
| `.toolbar .btn-primary` | convex, filled | `--glass-control-gloss` over `--glass-accent` | - | as controls | as controls | as controls |
| Action cards `#review-card`, `#reminder-card`, `#moved-card` | glass, rim | `--glass-tint` | `--glass-filter` | `--glass-depth` | `--r-card` | `--pad-card` |
| Their inner lists (5.3) | **solid** `--card`, set in | - | - | `--glass-depth-inner` | `--r-card-inner` | as today |
| Dialogs `.modal` (all five, editor included) | glass, strong, rim | `--glass-tint-strong` | `--glass-filter-refract-strong` | `--glass-depth-strong` | `--r-dialog` | `--pad-dialog` |
| Inputs, selects, textareas, buttons inside `.modal` | solid, as today | - | - | - | `--r-dialog-inner` | as today |
| Terms `.pilot-terms-card` | glass, strong, rim | `--glass-tint-strong` | `--glass-filter-refract-strong` | `--glass-depth-strong` | `--r-dialog` | `--pad-dialog` |
| Tour `.pilot-tour-card` | glass, strong, no rim | `--glass-tint-strong` | `--glass-filter-refract-strong` | `--glass-depth-strong` | `--r-tour` | `--pad-tour` |
| Every other `.card` (household, filed, setup) | **solid**, radius and entry motion only | - | - | - | `--r-card` | as today |
| Tables, lists, chips, banners, notices, toast, inputs outside dialogs | **unchanged** (buttons everywhere get the lift and press, 7.2) | - | - | - | - | - |
| Overlays `.modal-overlay`, `.pilot-terms-overlay`, the tour's dim | dim as today, fade in (7.2), no blur on the overlay itself | - | - | - | - | - |

Every light glass surface also gets `corner-shape: var(--glass-corner)`,
`text-shadow: var(--glass-halo)`, and the scoped re-pointing of 4.3. At the
Full level only, the pointer light (7.2) is added as a `background-image`
(`radial-gradient(260px circle at var(--glass-x, 25%) var(--glass-y, -40px), var(--glass-sheen), transparent 70%)`)
over the tint, from one rule:
`:root.glass-full :is(<the light glass surfaces>) { background-image: ...; }`.
The scoped re-pointing is:
`--muted: var(--glass-secondary); --subtle: var(--glass-secondary); --blue: var(--glass-accent); --blue-dark: var(--glass-accent-dark);`.
The header gets `color: var(--glass-on-bar)`, `position: relative;
z-index: 6` (so the toolbar's deeper shadow never paints over it), and
`.brand-product` `color: var(--glass-on-bar-soft)`.

### 6.2 The sticky toolbar and the scrolling page (P37)

`.toolbar { position: sticky; top: -20px; z-index: 5; }` inside `.main`, which
is the scroll container. The cards then scroll under the toolbar, which is
where glass reads as glass; over the static gradient alone a blur shows
nothing. `-20px` equals `.main`'s top padding: Chromium stops a sticky element
at the scroll container's padding edge, so `top: 0` leaves a 20px strip above
the bar where the cards show through untidily (seen in the preview). At
`-20px` the bar rests flush under the header.

`.main > * { flex-shrink: 0; }`: `.main` is a fixed-height flex column and a
`.card` has `overflow: hidden`, so when the content is taller than the window
the cards shrink and clip their own rows instead of the page scrolling (seen in
the preview's mock page). The builder confirms on the real page whether this
happens today; the rule is added either way, since the sticky toolbar needs the
page to scroll.

`z-index: 5` is below the tour (55), the modals (40) and the terms (60). The
toolbar keeps `flex-wrap: wrap`. The tour's spot finds the toolbar buttons in
the same place, so no tour anchor changes.

### 6.3 The lens map (refraction, P35)

`pilot/make_glass_lens.py` writes a 256 x 256 8-bit RGB PNG, no interlace,
filter byte 0 on every row, one IDAT, standard library only:

- band `b = 20` px (about 8% of each side);
- for each pixel, `t_x` = distance to the nearer left/right edge divided by
  `b`, clamped to 1; `d_x = (1 - t_x)^2`;
  `R = round(128 + 127 * d_x)` near the left edge,
  `round(128 - 127 * d_x)` near the right edge, `128` in the middle;
- `G` the same vertically (top positive, bottom negative); `B = 128`.

`feDisplacementMap` samples the backdrop at `x + scale * (R/255 - 0.5)`: near
the left edge it reads from further in, so the backdrop bends at the rim and is
untouched in the middle. `scale="20"` means at most 10px of bend (up from the
first draft's 6px, since the glass is now thin enough for the bend to show).
`preserveAspectRatio="none"` stretches the map over the element, so a wide
dialog's band is wider than a narrow card's - accepted. The script's CLI:
`python pilot/make_glass_lens.py [out-path]`, default
`app/renderer/glass-lens.png`.

## 7. Quality levels and motion (P34, P43)

| Level | Class on `<html>` | Glass | 3D | Motion | For |
|---|---|---|---|---|---|
| **Glass** (default) | none, or `glass-standard` | blur, saturation | rim, depth, halo | lift and press, arrivals, scrolled toolbar: nothing that runs every frame | most office PCs |
| **Glass with refraction** | `glass-full` | adds `url(#glass-refract)` on the toolbar, dialogs, terms and tour card (never the header or cards) | same | adds the pointer light and the backdrop drift | a PC with a real graphics card |
| **Solid** | `glass-solid` | every surface token its solid value (4.2), `--glass-filter*` `none` | none (flat shadows) | lift and press and arrivals only | remote desktop, slow PCs, or taste |

The pointer light sits at Full, not at the default, because it was the
single most expensive movement measured (P45, 7.3): it re-blurs the surface
under the pointer on every frame the pointer moves.

The default is what `glass.css` produces with no class, so the theme is correct
even if `glass.js` fails (it then has no pointer light and no scrolled state,
nothing else lost).

### 7.1 `glass.js`

Classic script, loaded last. Same rules as the other pilot JS (SPEC section 2:
no network, no HTML strings, no product name, DOM by `createElement`,
`textContent`, `classList`; `localStorage` in `try/catch`). One addition to
section 2's `style.setProperty` rule, for this file only (P44): it may set the
two custom properties `--glass-x` and `--glass-y`, and nothing else.

1. Read `PILOT.glass` (from `pilot-content.js`). If it is missing, do nothing
   further: the CSS default already applies.
2. Level = `localStorage["pilot.glass.level"]` if it is one of the `levels`
   keys, else `PILOT.glass.default`. A read that throws gives the default.
3. Apply: remove `glass-full`, `glass-standard`, `glass-solid` from
   `document.documentElement.classList`, add `glass-<level>`.
4. Build in the header (`.topbar`, whose right side is empty today):
   ```
   label.glass-level
     span.glass-level-label          PILOT.glass.label
     select#glass-level-select       one option per PILOT.glass.levels (value key, text name)
     span.glass-level-note.hidden    PILOT.glass.system_note
   ```
   If `.topbar` is missing, build nothing (the level still applies).
5. `change` -> apply and write `pilot.glass.level` (in `try/catch`; a failed
   write leaves the level applied for this session).
6. System preference: `const quiet = matchMedia("(prefers-reduced-transparency: reduce), (prefers-reduced-motion: reduce), (prefers-contrast: more), (forced-colors: active)")`.
   While `quiet.matches`, the select is `disabled` and the note shows; listen
   for `change` on `quiet` and update both live.
7. **Pointer light (Full level only).** A `pointerover` listener on
   `document`, `passive`, remembers the light glass surface under the pointer
   (`event.target.closest(GLASS_SURFACES)`, a constant string naming the
   surfaces of 6.1) and forgets its cached rectangle when that surface
   changes. A `pointermove` listener, `passive`, returns at once unless there
   is such a surface, the level is `full` and `quiet` does not match;
   otherwise it keeps the latest pointer position and, at most once per
   animation frame (`requestAnimationFrame`), sets `--glass-x` / `--glass-y`
   on that surface to the pointer's position inside it, in px. The surface's
   rectangle is read once and cached until the surface changes, `.main`
   scrolls or the window resizes, so no frame forces a layout. Leaving a
   surface leaves the light where it was (no snap back).
8. **Scrolled toolbar.** One `scroll` listener on `.main`, `passive`, computes
   `scrollTop > 4` and toggles `glass-scrolled` on `<html>` **only when that
   answer changes**, so scrolling costs no style work after the first 4px. It
   also drops the cached rectangle of step 7. If `.main` is missing, skip it.
9. **Pause the drift when the app is in the background.** `window` `blur`
   adds `glass-paused` to `<html>`, `focus` removes it;
   `:root.glass-paused body::before { animation-play-state: paused; }`.
   Chromium already stops it when the window is minimised; this also stops it
   while another program is in front.

No timers, no `setInterval`, no animation loop of its own: every animation is
CSS, and the script only moves two numbers when the pointer moves over glass
at the Full level.

### 7.2 The motion, element by element

All in `glass.css`, all with `transition`/`@keyframes` on `transform`,
`opacity`, `box-shadow`, `background-color` or (for `@starting-style` exits)
`display` with `allow-discrete` - nothing else (tested):

| What | How |
|---|---|
| **Buttons press** | `.btn:active { transform: scale(0.96); transition-duration: var(--glass-t-press); }`. `:active` applies on the frame the pointer goes down, so the press shows before the click has even finished; the app's own click handler runs at the same moment, untouched |
| **Buttons lift** | every `.btn`: `transition: transform var(--glass-t-control) var(--glass-spring), box-shadow var(--glass-t-hover) ease, background-color var(--glass-t-hover) ease`; `:hover` `translateY(-1px)`; on the toolbar `:hover` also `background-color: var(--glass-control-hover)` and a deeper shadow |
| **Cards arrive** | `.card { transition: opacity var(--glass-t-card) ease, transform var(--glass-t-card) var(--glass-settle), display var(--glass-t-card) allow-discrete; }` and `@starting-style { .card { opacity: 0; transform: translateY(6px); } }`: when the renderer removes `hidden`, the card rises 6px into place. `hidden` is `display: none` in `style.css`, so this needs no script |
| **Dialogs arrive** | `.modal-overlay` fades in over `--glass-t-dim` (`@starting-style { opacity: 0 }`); `.modal` and `.pilot-terms-card` fade in over `--glass-t-fade` and rise 6px from `scale(0.97)` over `--glass-t-settle` with `--glass-settle`. The dialog is readable after about 100ms and already takes typing: `app.js` focuses its first control at once, and nothing here delays that |
| **Toolbar deepens** | `:root.glass-scrolled .toolbar { box-shadow: var(--glass-depth-strong); }` with `transition: box-shadow var(--glass-t-hover) ease` |
| **Tour spot glides** | 5.5 |
| **Pointer light (Full only)** | the `background-image` of 6.1 follows `--glass-x/--glass-y`; no transition (it tracks the pointer frame by frame) |
| **Backdrop drifts (Full only)** | the glow layer of 4.1: `animation: glass-drift var(--glass-drift) ease-in-out infinite alternate;` with `@keyframes glass-drift { from { transform: translate(-3%, -2%); } to { transform: translate(3%, 3%); } }`, paused by `glass-paused` (7.1 step 9) |

Closing a dialog is not animated: `app.js` adds `hidden` and the element is
gone at once. That keeps Escape and Cancel instant, and animating an exit would
need `app.js`.

### 7.3 Speed: what was measured, and the budget (P45)

Measured on 2026-09-29 on the preview mock-up in the cloud's Chromium 141,
which has no graphics card and so draws in software, as Chromium does over
Remote Desktop: a worst case. A frame-time probe (`requestAnimationFrame`
timestamps) ran while the pointer swept the toolbar and a card, while the page
scrolled 600px, and while a dialog opened. Frames per second, two runs each:

| | First draft (all motion at Glass, long timings) | This SPEC |
|---|---|---|
| Glass: pointer moving | 27.5 / 27.5 | **46.0 / 45.2** |
| Glass: scrolling | 37.1 / 37.8 | **41.6 / 41.6** |
| Glass: dialog readable (opacity >= 0.9) | 201 / 242 ms | **119 / 132 ms** |
| Solid: pointer, scrolling | 60 / 57.5 | **60 / 59.1** |
| Solid: dialog readable | 184 ms | **103 / 95 ms** |
| Glass with refraction: pointer, scrolling | 27.8 / 39.1 | 24.3 / 33.6 (software; this level is for a PC with a graphics card) |

What made the difference, and what did not:

- **The pointer light cost about 40% of the frames** in software (43 frames
  per second without it, about 25 with it, however it was drawn: as a
  background layer or as a separate layer moved by `transform`). It moved to
  Full.
- **Shorter timings** halved the time to a readable dialog.
- **Less blur** (8/14px instead of 14/22) gained little and was not taken:
  the thinner, clearer glass needs the blur it has.
- **The drift** moves a separate layer by `transform`, not the page
  background, so it never repaints the page; it still re-blurs every glass
  surface each frame, which is why it stays at Full and pauses in the
  background.

Where the cost falls:

- Blur costs graphics-card time for every frame in which what is behind a
  glass surface changes: scrolling cards under the toolbar, a dialog opening,
  a hover on a glass button (brief), and at Full the pointer light and the
  drift.
- On the main screen at most five blurred surfaces show at once (header,
  toolbar, three action cards).
- Over Remote Desktop, Chromium often loses the graphics card and draws in
  software: the numbers above. The guide tells a tester on remote desktop to
  pick Solid.

**The budget the build must meet** (section 11, step 6), measured the same way
in the cloud Chromium on the real page with the stub: at Glass, at least **40**
frames per second while the pointer sweeps and while the page scrolls; at
Solid, at least **55**; at every level a dialog readable within **150ms** of
being shown; a pressed button scaled within **one frame** of the pointer going
down. A build that misses one says so in the handoff with its numbers, and the
reviewer treats it as a finding.

### 7.4 Wording in `pilot-content.js` (P8; proposed, Jason approves)

A fifth top-level key, `glass`:

```json
"glass": {
  "label": "Screen effects",
  "levels": [
    { "key": "standard", "name": "Glass" },
    { "key": "full", "name": "Glass with refraction" },
    { "key": "solid", "name": "Solid" }
  ],
  "default": "standard",
  "system_note": "Solid, because Windows is set to reduce transparency or motion."
}
```

and `"edition": { "label": "Pilot edition", "version": "0.2" }`.

The picker in the header: `.glass-level` is `display: flex; align-items:
center; gap: 8px; font-size: 12.5px; color: var(--glass-on-bar-soft)`; the
select has `background: rgba(255, 255, 255, 0.10)` (a token,
`--glass-picker-fill`), `color: var(--glass-on-bar)`, a
`1px solid rgba(255, 255, 255, 0.35)` border (`--glass-edge-on-bar`), radius 8,
and `option` elements get `color: var(--text); background: var(--card)` so the
drop-down list is legible.

## 8. Accessibility and fallback rules (P36, P43)

1. **Contrast.** Every text colour on a glass surface meets 4.5:1 against that
   surface's worst case (section 10.2). No exception for "large" text; the
   halo is not counted.
2. **System asks for less** - `prefers-reduced-transparency: reduce` (Windows
   Transparency effects off), `prefers-reduced-motion: reduce` (Windows
   Animation effects off), `prefers-contrast: more`, `forced-colors: active`:
   the screen is **Solid** whatever the picker says, with radii and
   `corner-shape` kept. Under reduced motion `style.css`'s own rule already
   stops every animation and transition, the drift and the arrivals included,
   and `glass.js` stops moving the pointer light (7.1 step 7).
3. **No `backdrop-filter` support** (`@supports not (backdrop-filter: blur(1px))`):
   Solid. Cannot happen on Chromium 150; it guards a future engine change.
4. **Forced colours**: `glass.css` sets nothing beyond the Solid tokens, and
   `text-shadow` is `none`, so Windows' own colours win.
5. **Focus** stays visible: the app's `outline: 2px solid var(--blue)` becomes
   `--glass-accent` on glass (above 3:1 on every surface). A pressed or lifted
   button's outline moves with it.
6. **Motion limits.** Nothing moves more than 6px (the tour spot, which travels
   to its next anchor, aside) or scales below 0.96; no
   transition lasts longer than 200ms except the Full-level drift, which is
   slow (40s a sweep) and large-area, never a flash. Nothing blinks. No
   animation delays input: arrivals are transitions on elements that already
   accept clicks, and `pointer-events` is never turned off on app elements.
7. **Nothing hides.** The theme changes no `display`, order or visibility of
   any app element; only the sticky toolbar's position and the cards'
   `flex-shrink` change layout.
8. **`glass.css` never uses `!important`** on `animation` or `transition`, so
   `style.css`'s reduced-motion rule always wins.

### 8.1 The fallback block

Last in `glass.css`:

```
@media (prefers-reduced-transparency: reduce), (prefers-reduced-motion: reduce),
       (prefers-contrast: more), (forced-colors: active) {
  :root, :root.glass-standard, :root.glass-full, :root.glass-solid { ...solid tokens... }
  :root.glass-full body::before { animation: none; }
}
@supports not (backdrop-filter: blur(1px)) {
  :root, :root.glass-standard, :root.glass-full, :root.glass-solid { ...solid tokens... }
}
```

The selector list repeats every level class so the block has the same
specificity as the level blocks and, coming last, wins. The Solid tokens are
written once, in `:root.glass-solid`, and the two fallback blocks repeat them
exactly (the test compares the three sets).

### 8.2 Tester Guide

`pilot/Tester Guide.md` gets a short **Screen effects** section: where the
picker is; Glass is the default and does nothing that runs continuously;
choose Solid on remote desktop or if scrolling stutters; Glass with refraction
(the pointer light and the drifting backdrop) only on a PC with a graphics
card; Windows' Transparency effects or Animation effects switch turns it
solid and still on its own. No Apple name.

## 9. What `glass.css` may target (P33)

`pilot-style.css`'s rule (`test_the_pilot_style_targets_only_its_own_names`)
stays exactly as it is. `glass.css` must restyle app classes, so it gets its
own, closed rule, held in `tests/test_glass.py`:

- Strip comments, `@media ... {`, `@supports ... {` and `@starting-style {`
  openers, `@keyframes glass-...` blocks (their `from`/`to` selectors), and a
  leading scope `:root.glass-standard `, `:root.glass-full `,
  `:root.glass-solid `, `:root.glass-scrolled ` or `:root.glass-paused ` from each
  selector.
- Every remaining selector starts with one of:
  - the theme's own names: `:root`, `body`, `.glass-`, `#glass-`;
  - the pilot's names: `.pilot-`, `#pilot-`;
  - `GLASS_TARGETS`, a tuple in the test:
    `.topbar`, `.brand-product`, `.main`, `.toolbar`, `#eng-select`, `.btn`,
    `#review-card`, `#reminder-card`, `#moved-card`, `#review-list`,
    `#moved-list`, `#review-deck`, `#dismissed-card`, `.rem-preview`,
    `.rem-stages`, `.card`, `.modal`, `.modal-overlay`, `.chip`.
- Each id or class in `GLASS_TARGETS` must exist in `index.html` (as `id="..."`
  or inside a `class="..."`) or, for a class the renderer makes, as a selector
  in `style.css`.
- `glass.css` declares no `.chip-<status>` rule and no `--stage-ink`,
  `--rem-ink` or `--rem-paper`.
- Colour literals (`#hex`, `rgb(`, `rgba(`) appear only in declarations of
  custom properties (`--...:`) inside the token blocks. Every other
  declaration uses `var(...)`.
- Keyframes are named `glass-...` only.

Adding a target later means adding it to `GLASS_TARGETS` in the same commit,
which a reviewer sees.

## 10. Tests

### 10.1 `tests/test_glass.py` (owns `app/renderer/glass.js`)

Named as the claims they make; reading files as text; standard library only.

- `test_the_page_loads_the_glass_last` - `glass.css` after `pilot-style.css`,
  `glass.js` after `tour.js`, each exactly once.
- `test_the_refraction_filter_is_markup_the_policy_allows` - the `<svg
  class="glass-defs"` block holds `<filter id="glass-refract"`, one `feImage`
  whose `href` is `glass-lens.png` (and that file exists) or a
  `data:image/png;base64,` URI, one `feDisplacementMap`; no `style=`, no
  `<script`, no ` on...=` in it; the CSP line is unchanged.
- `test_the_glass_style_targets_only_what_it_is_allowed` - section 9.
- `test_every_glass_target_is_on_the_page` - section 9, the existence check.
- `test_the_glass_style_types_colour_only_in_its_tokens` - section 9.
- `test_the_glass_leaves_the_status_chips_and_the_reminder_colours_alone`.
- `test_every_text_on_glass_meets_aa_contrast` - section 10.2.
- `test_refraction_is_used_only_at_the_full_level` - `url(#glass-refract)`
  occurs only in declarations inside a `:root.glass-full` block.
- `test_every_glass_rule_reads_its_filter_from_a_token` - every
  `backdrop-filter:` outside a token block is `var(--glass-filter...)`.
- `test_the_system_asking_for_less_makes_the_screen_solid_and_still` - the
  fallback `@media` names all four features and turns the drift off; the
  `@supports not` block exists; both come after every level block; both set
  exactly the same token values as `:root.glass-solid`; the Solid set gives
  every `--glass-filter*` `none`, every tint an opaque colour and
  `--glass-sheen` `transparent`.
- `test_motion_moves_only_what_the_compositor_can` - every property named in a
  `transition` or changed between `@keyframes` steps in `glass.css` is one of
  `transform`, `opacity`, `box-shadow`, `background-color`,
  `display` (with `allow-discrete`),
  or, for `.pilot-tour-spot` only, `top`, `left`, `width`, `height`,
  `border-radius`.
- `test_the_backdrop_drifts_only_at_the_full_level` - `animation:` appears
  only under `:root.glass-full`, on `body::before`, and a
  `:root.glass-paused` rule pauses it.
- `test_the_pointer_light_is_drawn_only_at_the_full_level` - `--glass-sheen`
  is read only in a rule scoped `:root.glass-full`, and `glass.js` checks
  for the `glass-full` class before moving it.
- `test_reduced_motion_still_stops_every_animation` - `style.css` still has
  its `prefers-reduced-motion` rule with `animation: none !important` and
  `transition: none !important`, and `glass.css` has no `!important`.
- `test_no_animation_runs_longer_than_its_limit` - every duration token and
  every literal duration in `glass.css` is at most `200ms`, except
  `--glass-drift`.
- `test_the_pointer_light_sets_only_its_two_numbers` - `glass.js` calls
  `style.setProperty` only with `"--glass-x"` or `"--glass-y"`, uses
  `requestAnimationFrame`, registers its `pointerover`, `pointermove`,
  `scroll` and `resize` listeners with `passive: true`, reads
  `getBoundingClientRect` only where the cached rectangle is empty, toggles
  `glass-scrolled` only on a change, and contains no `setInterval` or
  `setTimeout`.
- `test_nested_corners_are_concentric` - from the tokens:
  `r_card_inner == max(r_min, r_card - pad_card)`, the same for dialog, tour
  and toolbar; `r_toolbar_control * 2 == h_toolbar_control`.
- `test_every_rounded_glass_shape_has_continuous_corners` - every rule in
  `glass.css` that sets `border-radius` also sets `corner-shape:
  var(--glass-corner)` (or the selector is in the one shared rule that does).
- `test_the_lens_map_is_what_its_generator_draws` - decode `glass-lens.png`
  (zlib, filter byte 0) and compare every pixel with
  `make_glass_lens.pixel(x, y)`.
- `test_the_glass_wording_lives_in_the_pilot_content` - `PILOT.glass` has
  `label`, `levels` (keys exactly `standard`, `full`, `solid`), a `default`
  among them and a `system_note`; `glass.js` types none of those strings.
- `test_the_glass_level_is_kept_in_storage_safely` - every `localStorage` use
  in `glass.js` sits in a `try` block; the key is `pilot.glass.level`.
- `test_the_theme_touches_no_app_file` - the word `glass` does not occur in
  `app.js`, `main.js`, `preload.js` or `style.css`.
- `test_the_theme_never_names_its_inspiration` - none of `Apple`, `Liquid
  Glass`, `iOS`, `macOS`, `SwiftUI` (case-insensitive) in `glass.css`,
  `glass.js`, `pilot-content.js` or `pilot/Tester Guide.md`.

### 10.2 The contrast model (`test_every_text_on_glass_meets_aa_contrast`, P42)

The first draft asked every surface to pass over every colour the page ever
draws. That capped the glass at about 80% white. This model asks each surface
to pass over **what can actually be behind it**, and is still a worst case
over that set:

| Surface | What can be behind it | Candidate set |
|---|---|---|
| Header (`--glass-tint-bar`) | only the top of the fixed backdrop: nothing scrolls under the header, which sits outside `.main` | the backdrop's first two gradient stops (`#14335c`, `#2c4d78`), the first glow colour at full strength, and their midpoint |
| Action cards (`--glass-tint`) | only the fixed backdrop: cards never overlap each other or the header | every gradient stop and every glow colour at full strength |
| Toolbar (`--glass-tint-toolbar`) | the backdrop and anything that scrolls under it | the card set, plus `#ffffff` (a solid list) and `--navy-deep` (`#0e2544`) |
| Dialogs, terms, tour (`--glass-tint-strong`) | the dimmed page | the toolbar set, each also under the strongest overlay dim the page uses (0.60, `.pilot-terms-overlay`, read from `pilot-style.css`), plus the set undimmed |
| Toolbar controls (`--glass-control`) | the toolbar | the toolbar's results |

Then, per surface:

1. Apply the CSS `saturate(s)` matrix (Filter Effects spec) and the
   `brightness(b)` factor to each candidate, clamped to 0-255.
2. **Bounding box**: take the per-channel minimum and maximum over the
   candidates. Blur and refraction only average and move backdrop pixels, and
   the drift only moves the same colours, so anything behind the glass lies
   inside that box; luminance rises with each channel, so the two corners
   bound it.
3. **Composite** the surface's tint over both corners (sRGB alpha blend). The
   pointer light is **not** included: it only adds white, which raises the
   contrast of the dark text it sits under.
4. **Check** each pair in `GLASS_PAIRS` - bar: `--glass-on-bar`,
   `--glass-on-bar-soft`; card, toolbar, strong and control: `--text`,
   `--navy`, `--glass-secondary`, `--glass-accent`, `--glass-ok`,
   `--glass-warn` - at WCAG 2 relative luminance, minimum over both corners,
   `>= 4.5`. Also the Solid tokens with the same pairs.

The candidate sets are written in the test next to a one-line reason each, so
a later layout change (say, a card that floats over another) is visibly a
change to this table. The failure message names the pair, the surface and the
ratio.

### 10.3 Changes to existing tests

- `tests/test_pilot.py`: `PILOT_JS` gains `"glass.js"`; the content key set
  becomes `{"edition", "contact", "terms", "tour", "glass"}`.
- `tests/test_tour.py`: `test_the_spot_follows_its_anchors_corner` -
  `tour.js` reads `borderTopLeftRadius` and sets `--pilot-spot-radius`;
  `pilot-style.css` reads `var(--pilot-spot-radius`.
- Standing: `test_layers` (its network scan covers `glass.js`),
  `test_single_source`, `test_repo_map`.

## 11. Build D: one Sonnet builder

One builder, in order, one commit per step, gate before the push. It works on
the branch its prompt names, cut from `main` after this SPEC has merged, and
opens a draft pull request to `main`; every commit message carries `[skip ci]`.
No parallel split: every step after 1 reads the one before.

1. **Lens map.** `pilot/make_glass_lens.py` with `pixel(x, y)` and `main()`;
   run it; commit the PNG. Test `test_the_lens_map_is_what_its_generator_draws`.
2. **Markup and feasibility.** The three `index.html` additions (section 3).
   Then a **scratch** check (not committed) in the cloud's Playwright Chromium
   141: load `index.html` over `file://` with a stubbed `window.tracker`, put
   a patterned element behind a `.glass-full` test surface, screenshot with
   the refraction on and off, and confirm the rims differ and the centre does
   not. If the file `feImage` does not render, switch to the `data:` URI
   (section 3) and say so in the handoff.
3. **`glass.css`**: tokens (section 4), the rules of 5.5-5.6 and 6.1-6.2, the
   motion of 7.2, the levels, the fallback blocks (8.1), the header picker
   styles (7.4).
4. **`glass.js`** (7.1) and the `pilot-content.js` block and version;
   `tour.js` and `pilot-style.css` for the spot.
5. **Tests**: `tests/test_glass.py`, the 10.3 changes.
6. **Rendered sweep** (scratch, results in the handoff): in the same Chromium,
   with the stub and a sample state that shows the review, reminder and moved
   cards, a dialog, the terms and the tour, walk every element inside a glass
   surface that has text, read its computed `color`, and check it against that
   surface's worst case from 10.2. Any failure: restyle the selector in
   `glass.css` to a glass text token. Also emulate each of the four reduced
   preferences and confirm no element has a computed `backdrop-filter` other
   than `none` and, under reduced motion, no running animation
   (`document.getAnimations().length == 0` after a dialog opens).
   **Speed probe** (7.3): the same frame-time probe at Glass, Solid and Full;
   report the numbers in the handoff against the budget.
7. **Tester Guide** (8.2) and `docs/repo-map.curated.json` roles for
   `glass.css`, `glass.js`, `glass-lens.png`, `make_glass_lens.py`,
   `test_glass.py`.
8. **Screenshots and a motion clip** for Jason (section 12), from the stubbed
   page in the cloud Chromium, saved under `pilot/reviews/glass-screens/` and
   committed (they show only the stub's made-up names, never client data). The
   clip is a Playwright `recordVideo` `.webm`, under 20 seconds.
9. **Gate** (CLAUDE.md): dead code out; `ruff check .`; `repo_map.py update`
   then `check`; `test_glass`, `test_pilot`, `test_tour`, `test_layers`,
   `test_single_source`, `test_repo_map` under 3.11 and 3.13. Write the
   handoff in `pilot/HANDOFF.md`.

The stub state uses only made-up names (from `tests/samples.py` or typed in
the scratch script); no client file, real or copied, is ever opened.

### Done when

- the gate passes;
- `git diff main -- app/renderer/app.js app/main.js app/preload.js app/renderer/style.css tracker/`
  is empty, and `index.html`'s diff is exactly the section 3 lines;
- the rendered sweep reports no pair under 4.5:1, no `backdrop-filter` and no
  running animation under the reduced-preference emulations;
- the speed probe meets the 7.3 budget;
- the screenshots and the clip exist for every row of section 12;
- the Opus review has no open findings.

## 12. Visual acceptance checklist (Jason)

Screenshots, each at 1280 x 800, light mode:

| # | Screen | Glass (default) | Solid (picker) | Transparency effects off (emulated `prefers-reduced-transparency`) |
|---|---|---|---|---|
| 1 | Main screen, cards scrolled halfway under the toolbar, pointer over the toolbar | ☐ | ☐ | ☐ |
| 2 | A dialog open (New household) | ☐ | ☐ | ☐ |
| 3 | The terms screen | ☐ | ☐ | ☐ |
| 4 | The tour, a step pointing at a toolbar button | ☐ | ☐ | ☐ |
| 5 | Row 2 at Glass with refraction (rim bend visible) | ☐ | - | - |
| 6 | **Motion clip**: pointer across the toolbar and a card, a scroll, a button press, a card arriving, a dialog arriving | ☐ | - | - |

Jason checks, on the screenshots and clip, then on his own Windows PC with the
installed 0.2:

- ☐ The glass is clearly see-through, and text is still easy to read
  everywhere.
- ☐ Glass shows on the header, toolbar, action cards, dialogs, terms and tour
  card, and nowhere else; lists and tables are plain white.
- ☐ The surfaces look thick and lit: bright top-left rim, soft inner glow,
  lifted shadow.
- ☐ Every click answers at once: the button presses as the mouse goes down,
  and dialogs are readable before the eye has moved to them.
- ☐ The button spring and the arrivals feel quick and calm, not busy; at Glass
  with refraction, the pointer light and the drift feel smooth.
- ☐ Nested corners look parallel; corners look continuous, not circular (tune
  `--glass-corner` if not).
- ☐ Turning Windows Transparency effects or Animation effects off makes it
  solid and still, with the same corners, without restarting the app.
- ☐ Scrolling and moving the pointer are smooth at Glass on the office PC, and
  over Remote Desktop at Solid.
- ☐ The picker says why it is greyed when Windows asks for less.
- ☐ No Apple name anywhere; the header badge reads "Pilot edition 0.2".

## 13. Review criteria (Opus, a session that did not build)

Numbered findings against this SPEC, in `pilot/reviews/review-3.md`:

1. Every section 3 line is present and nothing else in `index.html` changed;
   `app.js`, `main.js`, `preload.js`, `style.css` and `tracker/` untouched.
2. Tokens match section 4 exactly, or a changed value is in the handoff with
   its contrast result.
3. The concentric numbers hold (5.1-5.5), every radius set has `corner-shape`,
   and the rim sits exactly on the border (5.6).
4. Glass is on exactly the surfaces of 6.1; lists and tables solid.
5. Refraction and the drift only at Full; refraction only on the toolbar,
   dialogs, terms and tour.
6. Motion: only the properties of 7.2, the limits of 8.6 and 4.6, no script
   timers, the pointer light only at Full, rAF-throttled, passive and with a
   cached rectangle; the speed probe meets the 7.3 budget; the reviewer
   watches the clip and re-runs the probe.
7. The fallback: with each of the four media features emulated and at Solid,
   no computed `backdrop-filter` other than `none`, every tint opaque, and
   under reduced motion no running animation.
8. The contrast test implements 10.2 (per-surface candidate sets with their
   reasons, saturation and brightness, bounding box), and the rendered sweep
   was run and reported.
9. `GLASS_TARGETS` is closed and every entry exists on the page.
10. `glass.js` obeys SPEC section 2 plus P44 (no network, no HTML strings, no
    product name, storage in `try/catch`, `setProperty` only for the two
    numbers) and types no wording.
11. No Apple name in the product.
12. The reviewer re-runs the rendered sweep, the reduced-preference checks and
    a motion recording itself in the cloud Chromium, and looks at every
    screenshot.
