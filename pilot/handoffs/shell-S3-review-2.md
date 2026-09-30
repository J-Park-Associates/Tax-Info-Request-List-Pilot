# Shell S3 - review 2

Reviewer: a separate Opus 5.5 session at high effort. It built neither S3 nor its rebuild.
Date: 2026-09-29. Branch `claude/friendly-archimedes-33y9uk` at `e973147`. I diffed it
against `0776ea6` for the whole session and against `7e199c2` for rebuild 1. I checked it
against SPEC-shell 10, 3-5, 6 (no H1 on firm pages), 6.8, 8.1-8.3, 10.4, 11.1, 12 and 14.

**7 findings.** Finding 1 is review 1's F3, which survived the rebuild. I fixed it in this
review. Findings 2 and 3 are regressions caused by the rebuild's own fixes (F4 and F2).
Findings 4-7 are smaller.

## What was run

- Python 3.11 (`/tmp/v`) and 3.13 (a venv with the pinned packages). Each file ran in its
  own process, in parallel: `test_shell` (32), `test_pilot_ui` (11), `test_tour` (8),
  `test_pilot` (18), `test_single_source` (167), `test_layers` (29), `test_repo_map` (80),
  `test_api` (368), `test_pilot_installer` (12). All pass under both interpreters.
  After my fix, I ran `test_shell`, `test_pilot_ui`, `test_single_source`, `test_layers` and
  `test_repo_map` again under both.
- `ruff check .` is clean, and `tools/repo_map.py check` says the map is current.
- `shoot.mjs` took 81 shots. `interact.mjs` **fails**: see finding 2. I then changed its
  one wait in a throwaway copy, and every other interaction passed.
- I looked at these shots in light and dark, at 1100x700 and 1400x900: Overview, loading,
  counts failed, sort running, the setup page, a tooltip shown by keyboard, the real-app
  smoke shot and the contrast theme.
- I wrote my own Playwright probes (throwaway, not committed):
  - File > Change clients folder on the **real** `app.js`, both themes, both sizes.
  - Light and dark contrast themes on Needs review and on the open search list.
  - The focus ring's computed colour on every control the shell draws, in both contrast
    themes.
  - The loading page (is there an H1, where the section names start).

## Review 1's findings, checked in code and in the browser

- **F1: fixed.** `shellChangeRoot()` fills `#firm-input` and `#phone-input` from
  `vocab.firm` and `vocab.settings.phone`. The API sends `settings.phone` (`api.py`
  `firm_phone()`). On the real `app.js`, both themes and both sizes, the setup page
  opened from File > Change clients folder shows the firm's name and phone that were
  saved. It has Cancel, the side panel stays enabled and the path is empty.
- **F2: fixed for the section's name**, which is now readable in both contrast themes.
  The fix caused finding 3.
- **F3: survived.** See finding 1. I fixed it.
- **F4: fixed in `shell.js`.** The loading state (`aria-busy`, "Loading", no H1), counts
  failed and the fallback draw no H1 on firm pages. The fix broke `interact.mjs` (finding
  2). The harness's stand-in pages still draw one (finding 4).
- **F5: fixed.** No path shows as a segment name, and the new test pins this. The empty
  name it leaves behind is finding 7.
- **F6: fixed in code.** Before the first numbered progress line arrives, the foot shows
  the bar alone. The handoff still describes the old behaviour (finding 5).
- **F7: fixed.** The tour titles are "Sort" and "Needs review", and proposed decision 5 is
  reworded.
- **F8: fixed.** Section names start at x=16 (measured).
- **F9: fixed.** The four missing banners are listed in the handoff. The "locked"
  scenario no longer fakes a notice.
- **F10: fixed.** The underline offset is `var(--sp-1)`, and `--size-menu-row` is gone.

## The rebuild's scope

Rebuild 1 touched only what the findings named: `pilot-content.js` (F7), `pilot-ui.css`
(F10), `shell.css` (F2, F3, F8, F10), `shell.js` (F1, F4, F5, F6; `drawTitleOnly()` is F4's
helper), `shoot.mjs` (F9), three tests in `test_shell.py`, the two handoff files and the
map. **No edits beyond the findings.**

## These still hold

- The standing rules hold. There is no network call, nothing reads a document and
  nothing is sent.
- The CSP is unchanged. There is no inline script or style and no `innerHTML`
  (checked by grep over `shell.js`, `tooltip.js`, `index.html` and the harness).
- The rebuild adds only `var(--sp-1)` and `var(--sp-2)`, so spacing stays on the
  4/8/16/24/32/48 grid. No new words were added.
- The sort icon keeps its name and a five-word tooltip in every state ("Sort now"
  was shown by keyboard).
- Reduced motion is untouched.
- **For Jason** (rebuild file, items 1-2): the rebuild names both departures from the
  SPEC openly and leaves them undecided:
  - keydown listeners stay in `tour.js` and `pilot.js`, against SPEC 14.1's "one
    listener";
  - a focused text box shows no tooltip, against SPEC 8.5.

  Both still appear as *proposed* decisions 2 and 3 in `shell-S3.md`. Neither is settled
  quietly.

## Findings

### 1 - Review 1's F3 survived: in a contrast theme, the ring on the search box, the notices and the setup page is still `Highlight` (fixed here)

- **Where:** `app/renderer/shell.css`, the forced-colours block.
- **SPEC:** 10.4 says the focus ring uses `CanvasText`.
- **Code:** The rebuild changed `:focus-visible` to `CanvasText`. More specific rules in
  the older stylesheets outrank it:
  - `style.css` sets `input:focus-visible { outline: 2px solid Highlight }`.
  - `pilot-ui.css` sets `.btn:focus-visible` to `Highlight`.
  - `pilot-ui.css:548` sets `:is(#page, …) :is(input…):focus-visible` to `var(--focus)`,
    and Chromium forces that colour to `Highlight`.

  I measured the computed ring in both contrast themes. It was `Highlight` on `#find`, on
  the notice's Retry and Dismiss, and on every control of the setup page (Choose folder,
  Firm name, Firm phone, Start, Cancel). Only the side sections drew `CanvasText`.
- **Fixed in this review:** one rule at the end of that block:
  `#bar #find:focus-visible, #main #notices :focus-visible, #main #page .setup :focus-visible { outline: 2px solid CanvasText; }`.
  Its selectors outrank the older rules by id. They leave `#page:focus` and
  `.rows:focus` (which draw no ring) alone.
  - Measured after the fix: every one of those controls rings in `CanvasText`, black in the
    light contrast theme and white in the dark one.
  - `test_the_contrast_theme_fills_and_rings_follow_spec_10_4` now also pins this rule.
  - `test_shell`, `test_pilot_ui`, `test_single_source`, `test_layers` and `test_repo_map`
    pass under 3.11 and 3.13, and `interact.mjs` (with finding 2's wait changed) passes.

### 2 - The F4 fix broke `interact.mjs`

- **Where:** `pilot/harness/interact.mjs:32`.
- **Code:** `open()` waits for `#page h1` before each block. After F4, a firm page with no
  data draws no H1. The "counts failure is one notice" block (`?scenario=firm-fails`)
  therefore times out after 8s, and the script dies with a `TimeoutError` before it reports
  anything. The rebuild file says only "Harness re-shot", so `interact.mjs` was not run.
  The earlier blocks pass only because the stand-in pages draw an H1 on firm pages
  (finding 4).
- **Smallest fix:** Wait for the page to be drawn rather than for an H1, for example
  `document.querySelector("#page > *, #notices > *")`. With that one change, every
  interaction passes.

### 3 - The F2 fix left the selected section's count and the selected search option's caption grey on `Highlight` in a contrast theme

- **Where:** `app/renderer/shell.css:574` and `:579` (`forced-color-adjust: none`).
- **SPEC:** 10.4 says the selected section and the focused row use `Highlight` /
  `HighlightText`, and must be readable.
- **Code:** `forced-color-adjust` is inherited, so the children of those rows now keep
  their own token colours. `.side-count` and `.find-note` set `color: var(--text-caption)`.
  - The shell gives the rows' own columns `color: inherit`; nothing does that for these two.
  - Measured on Needs review (count "25"): light contrast draws `rgb(86,101,121)` on
    navy `Highlight`, about 2:1. Dark contrast draws `rgb(154,166,180)` on cyan
    `Highlight`, about 1.1:1.
  - The search list's selected caption ("2 returns", "Smith Family 2025") is the same.
    Both are unreadable in the shots.
- **Smallest fix:** In the same block:
  `.side-section[aria-current="page"] .side-count, .find-option[aria-selected="true"] .find-note { color: HighlightText; }`.

### 4 - The harness's stand-in pages draw an H1 on the four firm pages

- **Where:** `pilot/harness/pages-stub.js:53`, `:59`, `:65`, `:69`.
- **SPEC:** 6 says firm pages have no H1 (P75).
- **Code:** The Overview, Needs review, Reminders and Clients shots still name the page
  three times: in the path, in the side panel and in an H1. The handoff tells S4 that
  `pages-stub.js` "shows all of them in use", so it teaches S4 the layout P75 removes.
  `interact.mjs` also depends on it (finding 2).
- **Smallest fix:** Drop those four `h1` pushes.

### 5 - The handoff still says the last-sort line shows `scan.scanning`

- **Where:** `pilot/handoffs/shell-S3.md:74`.
- **Code:** The S6 paragraph still reads "shows the API's `scan.scanning` word when they
  are missing". Since F6, the code draws the bar alone, and S6 must not supply that word.
- **Smallest fix:** Change the paragraph to say that without `n`/`of` only the bar shows.

### 6 - The real-app smoke says "0 page errors" while the page shows an error notice

- **Where:** `pilot/harness/shoot.mjs:103-117`, `pilot/harness/stub.js` (the `state`
  reply).
- **Code:** The stub's `state` reply has no `items`, so `app.js`'s `render()` throws at
  `app.js:350` (`state.items.filter`).
  - `app.js` catches the error, logs it and draws "The app met an error of its own
    (TypeError)…", which is visible in `real-app-1100x700.png`.
  - The smoke counts only uncaught `pageerror`s, so it prints "0 page errors". The build
    handoff reported that line as a clean run.
  - The fault has been there since the build; review 1 missed it too.
- **Smallest fix:**
  - Have the stub's `state` reply carry `items: []`.
  - Have the smoke also fail on anything in `HARNESS.logged`.

### 7 - The F5 fallback leaves a crumb button with no name

- **Where:** `app/renderer/shell.js:323`.
- **Code:** On a year or return page whose household is not in the latest `list`, the
  household segment is still a `button` (it has a `go` route), but now its text is `""`.
  That is a focusable control with no accessible name. The path no longer shows a path,
  which is right; only the empty button is new.
- **Smallest fix:** Leave out a segment whose name is empty (or draw it as a plain
  `span`), so the path shows Clients › year.
