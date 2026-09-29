# Pilot 0.2 - Build D: the glass theme - SPEC

Status: **written 2026-09-29, for Jason's approval.** Decisions P30-P40
(`DECISIONS.md`). Jason's answers: the backdrop is a **soft navy gradient**;
**light mode only** for 0.2, dark mode later (P31).

Read first: [`README.md`](README.md), [`SPEC.md`](SPEC.md) sections 2, 3, 5, 6
and 9 (the page rules this build still obeys), and this file. Builders look up
`app/renderer/index.html`, `style.css`, `pilot-style.css` and `app.js` with
`python tools/repo_map.py show <file>` and read only the line ranges named
here.

**Naming rule.** The product calls this the **glass theme** and nothing else.
No Apple name, logo or the term "Liquid Glass" appears in any tracked file the
build adds or changes, the tester guide included. (This SPEC and the decision
log may say where the idea came from; the product may not.)

## 1. What this is

The app's screen gets translucent, frosted "glass" surfaces for the things
that float - the header bar, the toolbar, the dialogs, the pilot terms screen,
the tour card and the three action cards - over a soft navy backdrop, and
**concentric corners**: a shape nested inside another's corner has the
container's radius minus the gap between them, drawn as a continuous
(superellipse) curve rather than a circular arc. Lists and document tables stay
solid white so rows, chips and figures read exactly as they do today.

It is CSS, one small script, one image and a few lines of markup. It changes
no behaviour of the tracker and no word the tracker shows.

### Non-goals (do not build)

- Dark mode (P31: later, with its own token column).
- Any change to `app.js`, `main.js`, `preload.js`, `style.css`, anything under
  `tracker/`, or any IPC channel. The theme overrides from its own files (P32).
- Animated glass: no moving highlights, no motion tied to scroll or the
  pointer, no transitions on `backdrop-filter`.
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
| `backdrop-filter` (blur, saturate) | Chromium 76+ |
| `backdrop-filter: url(#id)` running an SVG filter, `feDisplacementMap` included, on the backdrop | Chromium only; Safari and Firefox do not; this app never runs in them |
| `corner-shape` with `superellipse(K)` (`K = 1` round, `2` "squircle") | Chromium 139+ |
| `@media (prefers-reduced-transparency: reduce)`, which Windows turns on when Settings > Personalization > Colors > **Transparency effects** is off | Chromium 118+ |
| `prefers-reduced-motion`, `prefers-contrast`, `forced-colors` | long supported |
| The cloud's Playwright Chromium is 141 (>= 139), so a builder can check every feature above in the cloud | `/opt/pw-browsers` |
| CSP: `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'` | `index.html` line 9 |
| `main.js` reads `--bg` from `style.css` for the window's first-paint colour; untouched, so the window flashes `#f5f7fa` for one frame before the backdrop paints | `main.js` `pageBackground()` |

## 3. Files, load order and the exact `index.html` lines

New files (all pilot files, P7):

| File | What it is |
|---|---|
| `app/renderer/glass.css` | Every rule and token of the theme. Loaded **last**, after `style.css` and `pilot-style.css`, so it wins on equal specificity. |
| `app/renderer/glass.js` | Sets the quality level on `<html>` and builds the "Screen effects" picker in the header (section 7). |
| `app/renderer/glass-lens.png` | The refraction's displacement map (section 6.2), made by `pilot/make_glass_lens.py`. |
| `pilot/make_glass_lens.py` | Writes `glass-lens.png` with the standard library only (`zlib`, `struct`). Own CLI; run once, output committed. |
| `tests/test_glass.py` | Section 10. |

Changed pilot files: `pilot-content.js` (the `glass` wording block and
`edition.version` `"0.2"`), `tour.js` (the spot follows its anchor's corner,
section 5.5), `pilot-style.css` (one declaration, section 5.5),
`tests/test_pilot.py` (the key set and `PILOT_JS`), `pilot/Tester Guide.md`
(section 8), `docs/repo-map.curated.json` (roles for the new files).

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
         <feDisplacementMap in="SourceGraphic" in2="lens" scale="12" xChannelSelector="R" yChannelSelector="G" />
       </filter>
     </svg>
   ```
3. After `  <script src="tour.js"></script>` (today line 680):
   ```
     <script src="glass.js"></script>
   ```

Why inline markup (P35): an SVG `<filter>` is neither script nor style, so the
CSP allows it; `backdrop-filter: url(#glass-refract)` resolves a same-document
id reliably in Chromium, while a reference into an external `.svg` document from
`backdrop-filter` is not something the CSP or Chromium promise. The map is a
file under `img-src 'self'`. **Fallback, only if the builder's rendered check
(section 11, step 2) shows the `feImage` file does not load inside a backdrop
filter:** put the same PNG bytes in the `href` as `data:image/png;base64,...`,
which `img-src ... data:` also allows, and record that in the handoff.

`.glass-defs` in `glass.css`: `position: absolute; width: 0; height: 0;
overflow: hidden;` (the `width`/`height` attributes already keep it out of
layout; the class makes sure no flex gap is spent on it).

## 4. Tokens (light mode only, P31)

All tokens sit in `glass.css` in `:root` (the Standard level), re-set by
`:root.glass-full`, `:root.glass-solid` and the fallback block (section 9).
**No colour literal appears anywhere else in `glass.css`** (P33; tested).

### 4.1 Backdrop (P31)

```
--glass-backdrop:
  radial-gradient(60% 45% at 12% 0%, rgba(96, 140, 200, 0.35), transparent 70%),
  radial-gradient(50% 40% at 92% 8%, rgba(255, 255, 255, 0.12), transparent 70%),
  linear-gradient(180deg, #14335c 0px, #2c4d78 160px, #b7c6d9 420px, #e6ecf3 640px, #f3f6fa 100%);
```

Applied as `body { background: var(--glass-backdrop) #f3f6fa; }`. The body does
not scroll (`.main` does), so the backdrop is fixed to the window: navy behind
the header and toolbar, fading to light slate behind the cards. The two soft
glows give the glass something to catch at the top. The backdrop stays at every
level, Solid included - it is not transparency.

### 4.2 Glass colours

| Token | Standard / Full | Solid and fallback | Used for |
|---|---|---|---|
| `--glass-tint-bar` | `rgba(14, 37, 68, 0.80)` | `#14335c` | header bar |
| `--glass-tint` | `rgba(255, 255, 255, 0.80)` | `#ffffff` | toolbar, action cards |
| `--glass-tint-strong` | `rgba(255, 255, 255, 0.90)` | `#ffffff` | dialogs, terms card, tour card |
| `--glass-control` | `rgba(255, 255, 255, 0.60)` | `#ffffff` | `.btn` (not `.btn-primary`) and the engagement select on a glass surface |
| `--glass-control-hover` | `rgba(255, 255, 255, 0.85)` | `#f1f5f9` | their hover |
| `--glass-edge` | `rgba(255, 255, 255, 0.55)` | `#e2e8f0` | 1px border of every glass surface |
| `--glass-edge-bar` | `rgba(255, 255, 255, 0.14)` | `rgba(255, 255, 255, 0.14)` | the header's bottom border |
| `--glass-highlight` | `inset 0 1px 0 rgba(255, 255, 255, 0.65)` | `none` | top specular line |
| `--glass-shadow` | `0 8px 32px rgba(15, 23, 42, 0.18)` | `0 1px 3px rgba(15, 23, 42, 0.08)` | lift |
| `--glass-shadow-strong` | `0 24px 60px rgba(15, 23, 42, 0.35)` | `0 20px 50px rgba(15, 23, 42, 0.35)` | dialogs, terms, tour |

### 4.3 Text on glass

Inside every glass surface the sheet re-points the app's own variables, so
`style.css`'s rules keep working and nothing there is edited:

| Token | Value | Replaces inside glass |
|---|---|---|
| `--glass-muted` | `#334155` | `--muted` (was `#475569`) |
| `--glass-subtle` | `#475569` | `--subtle` (was `#64748b`, which fails AA on glass: 3.2:1 worst case) |
| `--glass-accent` | `#1e40af` | `--blue` (text and outline use); `--blue-dark` becomes `#1e3a8a` |
| `--glass-ok` | `#166534` | the tour's ✓ (`#16a34a` in `pilot-style.css`) |
| `--glass-warn` | `#92400e` | the tour's ! (`#d97706`) |
| `--glass-on-bar` | `#f8fafc` | header text |
| `--glass-on-bar-soft` | `#cbd5e1` | the product name beside the logo (as today) |

`--text` (`#0f172a`) and `--navy` (`#14335c`) are unchanged and pass on every
light surface. The literal greys `pilot-style.css` types for the tour and terms
(`#6b7280`, `#4b5563`) are restyled in `glass.css` to `var(--glass-subtle)` /
`var(--glass-muted)` by the pilot selectors that set them (see the rendered
sweep, section 11, which finds any the list misses). `.btn-primary` keeps white
on blue: it becomes white on `--glass-accent` inside glass (higher contrast
than today).

Worst-case contrast of these values, computed with the section 10.2 model
(minimum over every backdrop colour, the dims and saturation):

| Surface | text | navy | muted | subtle | accent | ok | warn | on-bar | on-bar-soft |
|---|---|---|---|---|---|---|---|---|---|
| glass | 11.9 | 8.5 | 6.9 | 5.1 | 5.8 | 4.8 | 4.7 | - | - |
| glass-strong (over the darkest dim) | 14.6 | 10.3 | 8.4 | 6.2 | 7.1 | 5.8 | 5.8 | - | - |
| control on glass | 15.3 | 10.9 | 8.9 | 6.5 | 7.5 | 6.1 | 6.1 | - | - |
| bar | - | - | - | - | - | - | - | 7.8 | 5.5 |

Every pair clears WCAG AA's 4.5:1 for normal text.

### 4.4 Blur and saturation

| Token | Standard | Full | Solid / fallback |
|---|---|---|---|
| `--glass-blur` | `16px` | `16px` | - |
| `--glass-blur-strong` | `28px` | `28px` | - |
| `--glass-saturate` | `1.4` | `1.4` | - |
| `--glass-filter` | `blur(var(--glass-blur)) saturate(var(--glass-saturate))` | same | `none` |
| `--glass-filter-strong` | `blur(var(--glass-blur-strong)) saturate(var(--glass-saturate))` | same | `none` |
| `--glass-filter-refract` | `var(--glass-filter)` | `url(#glass-refract) blur(var(--glass-blur)) saturate(var(--glass-saturate))` | `none` |
| `--glass-filter-refract-strong` | `var(--glass-filter-strong)` | `url(#glass-refract) blur(var(--glass-blur-strong)) saturate(var(--glass-saturate))` | `none` |

Every glass rule writes `backdrop-filter: var(--glass-filter...)`; only the
tokens change between levels. So `url(#glass-refract)` is typed only inside
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
a radius to, at every level (the Solid fallback keeps it, P36).

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
8px of a window corner (`.main` has 20-24px padding), so no other shape is
bound to the window: the gap is larger than the radius and the rule gives
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
preview `.rem-preview`, the reminder stages `.rem-stages`): `max(6, 20 - 12) = 8`.
Rows inside the solid list run edge to edge (square), as today. The card head
sits in the padding on the glass. Solid cards (household, filed, setup) keep no
padding, as today, and take radius 20; their rows are clipped by
`overflow: hidden` as today.

### 5.4 A chip and a button in a dialog

Chip: 22px tall (12px text, 3px padding, 1px border), capsule `999px`. It sits
mid-row, never in a corner, so the rule does not bind it. If a chip ever sits
in the corner of an 8px inner panel with a 4px gap, the rule would give
`max(6, 8 - 4) = 6`, and the capsule (11) is kept anyway because a capsule is
its own shape - stated so no builder "fixes" it.

Dialog: radius 28, padding 20. Its action buttons sit in the bottom corners:
`max(6, 28 - 20) = 8`, a rounded rectangle, the same 8px they have today.
Inputs, selects and the editor's tables inside a dialog: 8. The editor
(`.modal-wide`) is the same.

Terms card: 28 / 20 / 8, as a dialog. Tour card: radius 24, padding 16, inner
(the Back/Next/Close buttons, the compare columns) `max(6, 24 - 16) = 8`.

### 5.5 The tour spot (outward)

The spot is 6px larger than its anchor on every side, so it is the anchor's
container: `spot radius = anchor radius + 6`. A toolbar button (20) gets a 26px
spot; a card (20) gets 26; a dialog button (8) gets 14. `tour.js` reads
`getComputedStyle(anchor).borderTopLeftRadius` when it places the spot and sets
`spot.style.setProperty("--pilot-spot-radius", (r + 6) + "px")` (section 2 of
`SPEC.md` allows `style.setProperty` for the spotlight). `pilot-style.css`'s
`.pilot-tour-spot` changes `border-radius: 8px` to
`border-radius: var(--pilot-spot-radius, 8px)`. `glass.css` adds
`corner-shape: var(--glass-corner)` to the spot.

## 6. What becomes glass, what stays solid

### 6.1 The table

| Element (selector) | Treatment | Tint | Filter token | Radius | Padding |
|---|---|---|---|---|---|
| Header `.topbar` | glass, dark | `--glass-tint-bar` | `--glass-filter` | 0 | as today |
| Toolbar `.toolbar` | glass, **sticky** (P37) | `--glass-tint` | `--glass-filter-refract` | `--r-toolbar` | `--pad-toolbar` |
| Toolbar controls `.toolbar .btn`, `.toolbar #eng-select` | glass control | `--glass-control` | none (sits on glass) | `--r-toolbar-control` | height `--h-toolbar-control` |
| Action cards `#review-card`, `#reminder-card`, `#moved-card` | glass | `--glass-tint` | `--glass-filter` | `--r-card` | `--pad-card` |
| Their inner lists (5.3) | **solid** `--card` | - | - | `--r-card-inner` | as today |
| Dialogs `.modal` (all five, editor included) | glass, strong | `--glass-tint-strong` | `--glass-filter-refract-strong` | `--r-dialog` | `--pad-dialog` |
| Inputs, selects, textareas, buttons inside `.modal` | solid, as today | - | - | `--r-dialog-inner` | as today |
| Terms `.pilot-terms-card` | glass, strong | `--glass-tint-strong` | `--glass-filter-refract-strong` | `--r-dialog` | `--pad-dialog` |
| Tour `.pilot-tour-card` | glass, strong | `--glass-tint-strong` | `--glass-filter-refract-strong` | `--r-tour` | `--pad-tour` |
| Every other `.card` (household, filed, setup) | **solid**, radius only | - | - | `--r-card` | as today |
| Tables, lists, chips, banners, notices, toast, inputs outside dialogs | **unchanged** | - | - | - | - |
| Overlays `.modal-overlay`, `.pilot-terms-overlay`, the tour's dim | unchanged dim, no blur on the overlay itself | - | - | - | - |

Every glass surface also gets: `border: 1px solid var(--glass-edge)`
(`border-bottom: 1px solid var(--glass-edge-bar)` for the header),
`box-shadow: var(--glass-highlight), var(--glass-shadow)` (`-strong` for
dialogs, terms and tour), `corner-shape: var(--glass-corner)`, and the scoped
text re-pointing of 4.3:
`--muted: var(--glass-muted); --subtle: var(--glass-subtle); --blue: var(--glass-accent); --blue-dark: #1e3a8a;`
(the last value is a token too: `--glass-accent-dark`). The header gets
`color: var(--glass-on-bar)` and `.brand-product` `color: var(--glass-on-bar-soft)`.

### 6.2 The sticky toolbar (P37)

`.toolbar { position: sticky; top: 0; z-index: 5; }` inside `.main`, which is
the scroll container. The cards then scroll under the toolbar, which is where
glass reads as glass; over the static gradient alone a blur shows nothing.
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

`feDisplacementMap` samples the backdrop at
`x + scale * (R/255 - 0.5)`: near the left edge it reads from further in, so
the backdrop bends at the rim and is untouched in the middle. `scale="12"`
means at most 6px of bend. `preserveAspectRatio="none"` stretches the map over
the element, so a wide dialog's band is wider than a narrow card's - accepted;
the effect is at the rim either way. The script's CLI: `python
pilot/make_glass_lens.py [out-path]`, default `app/renderer/glass-lens.png`.

## 7. Quality levels (P34)

| Level | Class on `<html>` | What it does | For |
|---|---|---|---|
| **Glass** (default) | none, or `glass-standard` | blur + saturation, no refraction | most office PCs |
| **Glass with refraction** | `glass-full` | adds `url(#glass-refract)` on the toolbar, dialogs, terms and tour card only (never the header or cards: they are large and the header sits on a flat colour) | a PC with a real graphics card |
| **Solid** | `glass-solid` | every glass token becomes its solid value (4.2 column 3), `--glass-filter*` `none`; backdrop, radii and corner shape stay | remote desktop, slow PCs, or taste |

The default is the one `glass.css` produces with no class, so the theme is
correct even if `glass.js` fails.

**Cost, stated for the tester guide.** Blur costs graphics-card time for every
frame in which what is behind the glass changes: scrolling the cards under the
sticky toolbar, and opening a dialog. On the main screen at most five blurred
surfaces show at once (header, toolbar, three action cards). Refraction adds a
displacement pass on up to two surfaces at a time (toolbar plus one dialog,
terms or tour). Over Remote Desktop, Chromium often loses the graphics card and
draws in software, where blur is slow: the guide tells a tester on remote
desktop to pick Solid.

### 7.1 `glass.js`

Classic script, loaded last. Same rules as the other pilot JS (SPEC section 2:
no network, no HTML strings, no product name, DOM by `createElement`,
`textContent`, `classList`; `localStorage` in `try/catch`).

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
   While `quiet.matches`, the select is `disabled` and the note shows (remove
   `hidden`); listen for `change` on `quiet` and update both live. The CSS
   (section 9) is what makes the screen solid; the script only says why the
   picker is greyed.

### 7.2 Wording in `pilot-content.js` (P8; proposed, Jason approves)

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
select has a transparent background, `color: var(--glass-on-bar)`, a
`1px solid rgba(255, 255, 255, 0.35)` border (that colour becomes a token,
`--glass-edge-on-bar`), radius 8, and `option` elements get
`color: var(--text); background: var(--card)` so the drop-down list is legible.

## 8. Accessibility and fallback rules (P36)

1. **Contrast.** Every text colour on a glass surface meets 4.5:1 against that
   surface's worst case (section 10.2). No exception for "large" text.
2. **System asks for less** - `prefers-reduced-transparency: reduce` (Windows
   Transparency effects off), `prefers-reduced-motion: reduce` (Windows "Show
   animations" off; Jason's rule, though glass itself does not move),
   `prefers-contrast: more`, `forced-colors: active` (Windows contrast
   themes): the screen is **Solid** whatever the picker says. Radii and
   `corner-shape` stay.
3. **No `backdrop-filter` support** (`@supports not (backdrop-filter: blur(1px))`):
   Solid. Cannot happen on Chromium 150; it guards a future engine change.
4. **Forced colours** additionally: `glass.css` sets no colour on anything
   under `forced-colors: active` beyond the Solid tokens, so Windows' own
   colours win (`forced-color-adjust` is never set).
5. **Focus** stays visible: the app's `outline: 2px solid var(--blue)` becomes
   `--glass-accent` on glass, 5.8:1 worst case (above the 3:1 non-text need).
6. **No motion added.** The theme adds no animation or transition; the existing
   `prefers-reduced-motion` rule in `style.css` is untouched.
7. **Nothing hides.** The theme changes no `display`, order or visibility of
   any app element except the sticky toolbar's position.

### 8.1 The fallback block

Last in `glass.css`:

```
@media (prefers-reduced-transparency: reduce), (prefers-reduced-motion: reduce),
       (prefers-contrast: more), (forced-colors: active) {
  :root, :root.glass-standard, :root.glass-full, :root.glass-solid { ...solid tokens... }
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
picker is; Glass is the default; choose Solid on remote desktop or if
scrolling stutters; Glass with refraction only on a PC with a graphics card;
Windows' Transparency effects or animations switch turns it solid on its own.
No Apple name.

## 9. What `glass.css` may target (P33)

`pilot-style.css`'s rule (`test_the_pilot_style_targets_only_its_own_names`)
stays exactly as it is. `glass.css` must restyle app classes, so it gets its
own, closed rule, held in `tests/test_glass.py`:

- Strip comments, `@media ... {` and `@supports ... {` openers, and a leading
  scope `:root.glass-standard `, `:root.glass-full ` or `:root.glass-solid `
  from each selector.
- Every remaining selector starts with one of:
  - the theme's own names: `:root`, `body`, `.glass-`, `#glass-`;
  - the pilot's names: `.pilot-`, `#pilot-`;
  - `GLASS_TARGETS`, a tuple in the test:
    `.topbar`, `.brand-product`, `.toolbar`, `#eng-select`, `.btn`,
    `#review-card`, `#reminder-card`, `#moved-card`, `#review-list`,
    `#moved-list`, `#review-deck`, `#dismissed-card`, `.rem-preview`,
    `.rem-stages`, `.card`, `.modal`, `.chip`.
- Each id or class in `GLASS_TARGETS` must exist in `index.html` (as `id="..."`
  or inside a `class="..."`) or, for a class the renderer makes, as a selector
  in `style.css`; so the list cannot name something the page does not have.
- `glass.css` declares no `.chip-<status>` rule (status chips stay
  `style.css`'s, and `test_the_stylesheet_has_a_chip_for_every_status_and_nothing_else`
  still reads only `style.css`) and no `--stage-ink`, `--rem-ink` or
  `--rem-paper`.
- Colour literals (`#hex`, `rgb(`, `rgba(`) appear only in declarations of
  custom properties (`--...:`) inside the token blocks. Every other
  declaration uses `var(...)`.

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
- `test_the_system_asking_for_less_makes_the_screen_solid` - the fallback
  `@media` names all four features and the `@supports not` block exists; both
  come after every level block; both set exactly the same token values as
  `:root.glass-solid`; the Solid set gives every `--glass-filter*` `none` and
  every tint an opaque colour.
- `test_nested_corners_are_concentric` - from the tokens:
  `r_card_inner == max(r_min, r_card - pad_card)`, the same for dialog, tour
  and toolbar; `r_toolbar_control * 2 == h_toolbar_control`.
- `test_every_rounded_glass_shape_has_continuous_corners` - every rule in
  `glass.css` that sets `border-radius` also sets `corner-shape:
  var(--glass-corner)` (or the selector is in the one shared rule that does).
- `test_the_lens_map_is_what_its_generator_draws` - decode
  `glass-lens.png` (zlib, filter byte 0) and compare every pixel with
  `make_glass_lens.pixel(x, y)`; compares pixels, not bytes, so a different
  zlib cannot fail it.
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

### 10.2 The contrast model (`test_every_text_on_glass_meets_aa_contrast`)

The test reads the tokens from `glass.css` and `--text`/`--navy` from
`style.css`, then:

1. **Backdrop candidates** `B`: every colour in `--glass-backdrop` taken as
   opaque (an `rgba` glow counts at full strength, which only widens the
   range), plus `#ffffff` (a solid list scrolled under the toolbar) and
   `--navy-deep` (`#0e2544`, the darkest colour the page draws).
2. **Dimmed candidates** `D` (for dialogs, terms, tour): each of `B` under each
   overlay dim the page uses - `.modal-overlay` (`rgba(15, 23, 42, 0.45)`,
   from `style.css`), `.pilot-terms-overlay` (0.60) and the tour's (0.55),
   read from `pilot-style.css` - plus `B` itself.
3. **Saturation**: apply the CSS `saturate(s)` matrix (Filter Effects spec) to
   each candidate, clamped to 0-255.
4. **Bounding box**: take the per-channel minimum and maximum over the
   candidates. Blur and refraction only average and move backdrop pixels, so
   anything behind the glass lies inside that box, and luminance rises with
   each channel, so the two corners bound it. (Saturation is linear before
   clamping, so step 3 before step 4 keeps the bound.)
5. **Composite** each surface's tint over both corners (sRGB alpha blend);
   `--glass-control` is composited over the `--glass-tint` results.
6. **Check** each pair in `GLASS_PAIRS` - bar: `--glass-on-bar`,
   `--glass-on-bar-soft`; glass, strong and control: `--text`, `--navy`,
   `--glass-muted`, `--glass-subtle`, `--glass-accent`, `--glass-ok`,
   `--glass-warn` - at WCAG 2 relative luminance, minimum over both corners,
   `>= 4.5`. Also the Solid tokens with the same pairs.

The failure message names the pair, the surface and the ratio.

### 10.3 Changes to existing tests

- `tests/test_pilot.py`: `PILOT_JS` gains `"glass.js"` (so the network,
  text-only and product-name checks cover it, and the load-order check sees it
  after `tour.js`); the content key set becomes
  `{"edition", "contact", "terms", "tour", "glass"}`.
- `tests/test_tour.py`: `test_the_spot_follows_its_anchors_corner` -
  `tour.js` reads `borderTopLeftRadius` and sets `--pilot-spot-radius`;
  `pilot-style.css` reads `var(--pilot-spot-radius`.
- Standing: `test_layers` (its network scan covers `glass.js`),
  `test_single_source`, `test_repo_map`.

## 11. Build D: one Sonnet builder

One builder, in order, one commit per step, gate before the push. It works on
the branch its prompt names, cut from `main` after this SPEC has merged, and
opens a draft pull request to `main`; every commit message carries `[skip ci]`.
No parallel split: every step after 1 reads the one before (the tokens feed the
rules, the rules feed the tests and the sweep).

1. **Lens map.** `pilot/make_glass_lens.py` with `pixel(x, y)` and `main()`;
   run it; commit the PNG. Test `test_the_lens_map_is_what_its_generator_draws`.
2. **Markup and feasibility.** The three `index.html` additions (section 3).
   Then a **scratch** check (not committed) in the cloud's Playwright Chromium
   141: load `index.html` over `file://` with a stubbed `window.tracker` (as
   Build B did), put a patterned element behind a `.glass-full` test surface,
   screenshot with `backdrop-filter: url(#glass-refract) blur(0)` and with
   `none`, and confirm the rims differ and the centre does not. If the file
   `feImage` does not render, switch to the `data:` URI (section 3) and say so
   in the handoff.
3. **`glass.css`**: tokens (section 4), the rules of 6.1-6.2 and 5.5, the
   levels, the fallback blocks (8.1), the header picker styles (7.2).
4. **`glass.js`** and the `pilot-content.js` block and version; `tour.js` and
   `pilot-style.css` for the spot.
5. **Tests**: `tests/test_glass.py`, the 10.3 changes.
6. **Rendered sweep** (scratch, not committed, results in the handoff): in the
   same Chromium, with the stub and a sample state that shows the review,
   reminder and moved cards, a dialog, the terms and the tour, walk every
   element inside a glass surface that has text, read its computed `color`,
   and check it against that surface's worst case from 10.2. Any failure:
   restyle the selector in `glass.css` to a glass text token and add a
   `GLASS_TARGETS` entry only if it is a new app selector. Also emulate
   `prefers-reduced-transparency: reduce` and confirm no element has a
   computed `backdrop-filter` other than `none`.
7. **Tester Guide** (8.2) and `docs/repo-map.curated.json` roles for
   `glass.css`, `glass.js`, `glass-lens.png`, `make_glass_lens.py`,
   `test_glass.py`.
8. **Screenshots** for Jason (section 12), from the stubbed page in the cloud
   Chromium, saved under `pilot/reviews/glass-screens/` and committed (they
   show only the stub's made-up names, never client data).
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
- the rendered sweep reports no pair under 4.5:1 and no `backdrop-filter` in
  the reduced-transparency emulation;
- the screenshots exist for every row of section 12;
- the Opus review has no open findings.

## 12. Visual acceptance checklist (Jason)

Screenshots, each at the default window size (1280 x 800) and light mode:

| # | Screen | Glass (default) | Solid (picker) | Transparency effects off (emulated `prefers-reduced-transparency`) |
|---|---|---|---|---|
| 1 | Main screen, cards scrolled halfway under the toolbar | ☐ | ☐ | ☐ |
| 2 | A dialog open (New household) | ☐ | ☐ | ☐ |
| 3 | The terms screen | ☐ | ☐ | ☐ |
| 4 | The tour, a step pointing at a toolbar button | ☐ | ☐ | ☐ |
| 5 | Row 2 at Glass with refraction (rim bend visible) | ☐ | - | - |

Jason checks, on the screenshots and then on his own Windows PC with the
installed 0.2:

- ☐ Text is as easy to read as in 0.1 everywhere.
- ☐ Glass shows on the header, toolbar, action cards, dialogs, terms and tour
  card, and nowhere else; lists and tables are plain white.
- ☐ Nested corners look parallel (toolbar buttons in the bar, lists in the
  cards, buttons in a dialog's corner, the tour spot round a button).
- ☐ Corners look continuous, not circular (tune `--glass-corner` if not).
- ☐ Turning Windows Transparency effects off makes it solid with the same
  corners, without restarting the app.
- ☐ Scrolling the cards under the toolbar is smooth at Glass on the office PC,
  and over Remote Desktop at Solid.
- ☐ The picker says why it is greyed when Windows asks for less.
- ☐ No Apple name anywhere; the header badge reads "Pilot edition 0.2".

## 13. Review criteria (Opus, a session that did not build)

Numbered findings against this SPEC, in `pilot/reviews/review-3.md`:

1. Every section 3 line is present and nothing else in `index.html` changed;
   `app.js`, `main.js`, `preload.js`, `style.css` and `tracker/` untouched.
2. Tokens match section 4 exactly, or a changed value is in the handoff with
   its contrast result.
3. The concentric numbers hold (5.1-5.5) and every radius set has
   `corner-shape`.
4. Glass is on exactly the surfaces of 6.1; lists and tables solid.
5. Refraction only at Full, only on the toolbar, dialogs, terms and tour.
6. The fallback: with each of the four media features emulated and at Solid,
   no computed `backdrop-filter` other than `none`, every tint opaque.
7. The contrast test implements 10.2 (candidates, dims, saturation, bounding
   box), and the rendered sweep was run and reported.
8. `GLASS_TARGETS` is closed and every entry exists on the page.
9. `glass.js` obeys SPEC section 2 (no network, no HTML strings, no product
   name, storage in `try/catch`) and types no wording.
10. No Apple name in the product.
11. The reviewer re-runs the rendered sweep and the reduced-transparency check
    itself in the cloud Chromium, and looks at the screenshots.
