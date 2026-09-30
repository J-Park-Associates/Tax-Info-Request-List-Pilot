# Shell S7 - review 2 (after rebuild 1)

Reviewer: a separate agent that built neither S7 nor its rebuild. Branch
`claude/shell-s7-tooltips` at `99defa4` (code commit `99aba3e`), diff
`cc7b66e...HEAD`. No code was changed. The only changes are this file and
the refreshed repository map.

## Verdict

All four review-1 findings are fixed, and ruling 7 is built as Jason asked.
I checked this in the code and in the browser. There is **one finding**, F1:
the S7 handoff still tells S6 that the hover delay "stays 500 ms". No review-1
finding survived, so I fixed nothing.

## What was checked, and how

**Review-1 F1: script order.** In `index.html`, the core and dom vendor tags
now sit directly above `app.js`. Nothing is left between `app.js` and
`shell.js` except `tooltip.js`, as on the base. `test_the_loading_order_...`
pins `(*FLOATING_UI_SCRIPTS, "app.js", "tooltip.js", ...)`. I ran
`shoot.mjs` for every scenario: 81 shots and no problems. `real-app` passed
three runs of three ("side panel Overview|Needs review|Reminders|Clients,
0 page errors, 0 logged, no visible error"). `interact.mjs` reports "all
interactions pass".

**Review-1 F2: `hide()`.**
- The middleware is `FloatingUIDOM.hide()`. The `.then` calls `hideTip()` when
  `middlewareData.hide.referenceHidden` is set. The existing `tipFor !== node`
  guard still runs first.
- I read the vendored dom build myself: `Q=e.hide` (where `e` is
  `FloatingUICore`) and `t.hide=Q`, so it really exports core's `hide`. The
  core build implements the `referenceHidden` strategy.
- The vendored files are untouched:
  - `git diff cc7b66e HEAD` touches nothing under `app/renderer/vendor/`.
  - The SHA-256 of every file matches the vendor README and
    `FLOATING_UI_SHA256`.
  - I ran a fresh `npm pack @floating-ui/dom@1.8.0 @floating-ui/core@1.8.0`
    in the scratchpad, outside the repository. It gives the same hashes for
    both UMD builds (`61a46f94...`, `65940d86...`) and for `LICENSE`
    (`0e4c9a9b...`).
- **Browser check.** I used the review-1 reproduction: a button with a tip at
  the top of `#page` on the Clients page, given keyboard focus.
  - At scroll 0 the button top is 48 and the tip top is 76.
  - At scroll 10 the button top is 38 and the tip top is 66, so the tip
    follows the button.
  - At scroll 25 the button's bottom (47) is above `#page`'s top (48), so the
    button is fully clipped, and the tip is hidden. It stays hidden at scroll
    60, 120 and 300.
- Mutation on a scratch copy: removing the `hide()` line fails
  `test_a_tip_goes_when_its_element_is_scrolled_out_of_view`. It also fails
  the `interact.mjs` check "the tip is hidden once its element is scrolled out
  of view".

**Review-1 F3: the CDN check.** Each mutation below was an added tag, made
on a scratch copy of the repository:

| Mutation | Result |
|---|---|
| `src="https://cdn..."` (double-quoted) | the loading-order test fails |
| `src='https://cdn...'` (single-quoted) | the loading-order test fails; it passed before the fix |
| `src=https://cdn...` (unquoted) | the loading-order test fails |
| `defer src=//cdn...` (unquoted, no scheme) | the loading-order test fails |
| `src = "https://cdn..."` (spaces around `=`) | the loading-order test fails, on a later assertion |
| `<SCRIPT SRC="https://cdn...">` (upper case) | **passes**; see the notes |

The quoted and unquoted forms now fail through the count check: the regex
captures the tag, so `len(sources)` no longer equals `len(scripts)`.

**Review-1 F4: decision numbers.** "P86" is gone. The rebuild's comments cite
"Jason's ruling 5" and "ruling 7" only. `tooltip.js` still cites P63 and P65,
unchanged from S3's base (`afd566d`). No new decision number appears anywhere
in the diff.

**Ruling 7: the hover delay.**
- `TIP_DELAY_MS = 300`.
  `test_the_hover_delay_is_300_ms_and_keyboard_focus_waits_for_nothing` pins
  three things: the value, its single use in the hover timer, and that the
  `focusin` path does not use it.
- **Browser check, light and dark:**
  - Hover on `#sort`: no tip at 101, 200 or 260 ms. The tip shows at 320 ms
    and is still shown at 450 ms.
  - The same delay measured inside the page: 305 ms.
  - Tab onto `#sort` shows "Sort now" at once, with no wait.
  - `#find` shows no tip in each of these cases: on Tab, 400 ms after Tab, on
    Ctrl+F and on a click.
  - Hover on `#find` shows "Find a client". So does hover on the search icon.
- Mutation on a scratch copy: setting the delay to 150 fails the new test and
  the harness check "hover shows no tip at 200 ms".

**No regression.**
- **Edges.** I placed a control at all eight edges and corners of the window,
  with a tip wider than the control ("Needs review from the client"). I
  checked this at 1100x700 and at 1400x900, with forced colors off and on.
  The tip stayed at least 8 px inside the window every time. In forced
  colors it has a solid black (CanvasText) border on white (Canvas).
- **Words.** The tip texts on Overview, Needs review, Reminders, Clients and a
  household are the vocabulary's short phrases ("Sort now", "Find a client",
  "Open a client to sort", "Dismiss") or names. Only names run past five
  words.
- **`tooltip.js`.** It sets the tip's position only with `style.setProperty`,
  has no `innerHTML`, and has no network call.
- **CSP and scripts.** The CSP is unchanged from the base. The only script
  change from the base is the two vendor tags.
- **Network.** No page in the probes made a request that left the local
  harness server.
- **Standing rules.** Nothing reads a client document or sends anything.

**Scope.** The rebuild touched:
- `index.html`, `tooltip.js`, `interact.mjs` and `tests/test_shell.py`;
- `shell-S7.md` (its S6 merge note) and the new `shell-S7-rebuild-1.md`;
- the regenerated `docs/repo-map.*`.

There are no extras beyond F1 to F4 and ruling 7.

**Dead-code sweep of the changed files.**
- `tooltip.js`: every function and constant is used (`tipShowing` by
  `shell.js`, `setTipIfCut` by `shell.js` and `pages-stub.js`). No comment
  describes removed behaviour: the header says 300 ms, and the placement
  comment names `hide`.
- `interact.mjs`: every added variable and element is used.
- `tests/test_shell.py`: nothing left over. No "500" and no "P86" remain in
  any of these files.
- `ruff check .` is clean.

**Gate.** Each test file ran in its own process, on Python 3.11.15 and then
on 3.13.12, with the same results on both:

| Test file | Passed |
|---|---|
| `test_shell` | 37 |
| `test_pilot_ui` | 11 |
| `test_tour` | 8 |
| `test_pilot` | 18 |
| `test_single_source` | 167 |
| `test_layers` | 29 |
| `test_api` | 368 |
| `test_pilot_installer` | 12 |
| `test_row_columns` | 26 |
| `test_repo_map` | 80 |
| `test_build` | 30, and 1 failure |

The `test_build` failure is
`test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else`, the
known OCR failure on the base, which I ignored. `ruff check .` passes, and
`repo_map.py check` says current.

## Findings

**F1 - The S7 handoff still tells S6 the hover delay "stays 500 ms", and that
a scrolled-away tip is "clipped, not hidden".**
- *Where:* `pilot/handoffs/shell-S7.md`, in "Left for S6" (the "Update SPEC
  8.5" bullet: "the hover delay stays 500 ms") and in "For Jason" (the last
  two bullets).
- *Why it matters:* S6 edits SPEC 8.5 from the "Left for S6" list. The
  rebuild edited that same list for the script order, but left the 500 ms
  line in it. The rebuild-1 handoff does say it "supersedes" those lines, but
  S6 would have to know to read it. As written, the SPEC could be set back to
  500 ms against ruling 7. The proposed decision row in `shell-S7.md` also
  leaves out `hide`, which rebuild 1's proposed row 2 covers.
- *Smallest fix:* in that bullet, change "stays 500 ms" to "is 300 ms (ruling
  7)" and add "hidden when its element is scrolled out of view". Mark the two
  "For Jason" bullets as settled by rebuild 1. Documentation only; no code or
  test changes.

## Notes for Jason

- **Upper-case script tags.** The "no CDN" check reads lower-case `<script
  src=` only, so an upper-case `<SCRIPT SRC="https://...">` would pass it.
  The CSP (`script-src 'self'`) would still block that script when the app
  runs, so the app is safe. Adding `re.I` to the regex would close the gap
  in the test. It is outside F3's scope, which was about quotes.
- **After `hide`, the tip does not come back by itself.** Once a focused
  control is scrolled out of view, its tip is gone. Scrolling it back does
  not bring the tip back until the next hover or keyboard focus. That is the
  usual behaviour and I think it is right. It is worth one line in SPEC 8.5
  when S6 edits it.
- **The harness covers only three edges.** `interact.mjs` checks the right,
  bottom and bottom-right edges. I checked all eight by hand, in forced
  colors too, and all passed. The scroll check tests that the tip shows and
  hides, but not that it moves; I confirmed by hand that it moves with its
  element.
- **"page title undefined".** `shoot.mjs real-app` prints this line because
  the Overview page has no `h1`. It is not new and not a failure.
