# Shell S3 - review 3

Reviewer: a separate Opus 5.5 session at high effort. It did not build S3 or either rebuild.
Date: 2026-09-29. Branch `claude/friendly-archimedes-33y9uk` at `a3ffb5c`. I diffed it
against `3af373c` for rebuild 2 and against `0776ea6` for the whole session. I checked it
against SPEC-shell 6, 10.2-10.4, 11.1, 12 and 14.4.

**No findings.** All seven of review 2's findings are fixed. I checked each one in the code
and in the browser, not from the rebuild file. I changed no code.

## What was run

- **Python tests.** I ran them under Python 3.11 (`/tmp/v`) and 3.13 (`/tmp/v13`). Each
  file ran in its own pytest process, in parallel. Every file passes under both:
  - `test_shell` (32)
  - `test_pilot_ui` (11)
  - `test_tour` (8)
  - `test_pilot` (18)
  - `test_single_source` (167)
  - `test_layers` (29)
  - `test_repo_map` (80)
  - `test_api` (368)
  - `test_pilot_installer` (12)
- **Checks.** `ruff check .` is clean. `tools/repo_map.py check` says the map is current.
- **Harness.**
  - `interact.mjs` prints "all interactions pass".
  - `shoot.mjs` took 81 shots and exits 0. Its real-app line reads "0 page errors,
    0 logged, no visible error".
- **Shots I looked at.**
  - Contrast theme.
  - Needs review, Overview loading and counts failed, in light and dark.
  - The setup page, in dark.
  - The real-app smoke.
- **My own Playwright probes.** These were throwaway files and are deleted. They covered
  the light and dark contrast themes, the normal themes, and the path.

## Review 2's findings, checked

1. **The ring is `CanvasText` everywhere: fixed.** I tabbed through Needs review, a return
   page, the counts-failed page and the setup page in both contrast themes.
   - Every control drew a solid 2px ring in `CanvasText`: black in light, white in dark.
     That covers the side sections, the last-sort line, `#find`, the path's buttons, the
     notice's Retry and Dismiss, Choose folder, Firm name and Firm phone.
   - While the search list is open, `#find`'s ring is `CanvasText` too.
   - The row list draws no ring of its own, by design. Its active row carries the
     `CanvasText` outline instead.
2. **`interact.mjs`: fixed.** It passes fully.
3. **The selected count and the selected caption are readable: fixed.** I measured WCAG
   contrast against the `Highlight` fill:

   | What | Light contrast theme | Dark contrast theme |
   |---|---|---|
   | Needs review's count "25" | white on navy, 19.0:1 | black on cyan, 13.8:1 |
   | Selected search option's caption "Smith Family 2025" | 19.0:1 | 13.8:1 |

   Every child of the selected option is `HighlightText`. Both read clearly in the shots.
4. **`pages-stub.js` draws no H1 on firm pages: fixed.** Overview, Needs review, Reminders
   and Clients each have 0 H1s in both themes. The loading page (`aria-busy`) and the
   counts-failed page have none either.
5. **`shell-S3.md` matches the code: fixed.** `drawLastSort()` draws the bar alone, with no
   text and no `aria-valuenow`, when `n`/`of` are missing. The handoff says the same.
6. **The real-app smoke now fails on logged errors and on a visible error notice: fixed.**
   - I took `items: []` back out of the stub's `state` reply for a moment. The smoke then
     exited 1, naming the logged TypeError and "The app met an error of its own
     (TypeError)…".
   - With the stub put back, it is clean.
   - The same smoke shot shows no notice.
7. **A household or return not in the list is left out of the path: fixed.** I tried
   these routes:

   | Route | Path shown |
   |---|---|
   | Year of an unlisted household | Clients › 2025 |
   | Return of an unlisted household | Clients › 2025 |
   | Unlisted return of a listed household | Clients › Smith Family › 2025 |
   | Unlisted household | Clients |

   None of them has an unnamed button, and no path appears in the bar.

   The harness's stand-in page throws on those made-up routes, because `pages-stub.js`
   expects a listed return. It is harness-only and is replaced by the real pages. The
   shell draws the path before the page, so the path is unaffected.

## Scope of rebuild 2

It touched only what the findings named:

- `shell.css`: one forced-colours rule (finding 3).
- `shell.js`: `crumbList()` (finding 7).
- `interact.mjs`: the wait (finding 2).
- `pages-stub.js`: four `h1` pushes removed (finding 4).
- `shoot.mjs` and `stub.js`: the smoke check, `items: []` and a whole `household` block
  (finding 6). `app.js`'s `renderHousehold` needs the block.
- `shell-S3.md`: the last-sort paragraph (finding 5).
- Two assertions in `test_shell.py`.
- The rebuild file and the map.

**No extras.**

## These still hold

- **Standing rules.** There is no network call. Nothing reads or sends a document.
- **CSP.** `index.html` is untouched. There is still no `innerHTML` and no inline style
  attribute in `shell.js`, `tooltip.js` or the harness.
- **Grid.** Rebuild 2 adds no size or spacing value.
- **No new words.** The fallback path uses no new words and shows no path.
- **The sort icon.**
  - It keeps its name and tooltip ("Open a client to sort" on a firm page).
  - When disabled it draws `GrayText`, which is Chromium's emulated maroon/green, as
    SPEC 10.4 says.
- **Reduced motion.** It is untouched, and the shots were taken with it on.
- **For Jason: both departures are still flagged and undecided.** Proposed decisions 2
  and 3 in `shell-S3.md` still name them:
  - `tour.js` and `pilot.js` still add their own keydown listeners, against SPEC 14.1.
  - A text box being typed into shows no tooltip on focus, against SPEC 8.5.
