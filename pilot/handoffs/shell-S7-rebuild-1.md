# Shell S7 - rebuild 1 (after review 1)

Branch `claude/shell-s7-tooltips` (built locally as `rebuild-s7`, pushed with
`git push origin HEAD:claude/shell-s7-tooltips`). Started from `430aa27`.
Last commit: the tip of the branch (its sha is in the final report; a file
cannot name the commit that contains it). Only F1 to F4 and ruling 7 changed.

## Each finding, and how it was fixed

**F1 - real app.js did not start.** The two vendor `<script>` tags now sit
directly above `<script src="app.js">` in `app/renderer/index.html`, so
nothing parser-blocking is left between `app.js` and `shell.js`. They depend
on nothing and still load before `tooltip.js`. The order pinned in
`tests/test_shell.py` is now `(*FLOATING_UI_SCRIPTS, "app.js", "tooltip.js",
"shell.js", ...)`; it was the only place the order was pinned. The S7
handoff's S6 merge note is corrected. Proof: `shoot.mjs` (all scenarios,
81 shots, and `real-app` alone) reports "side panel Overview|Needs
review|Reminders|Clients, 0 page errors, 0 logged, no visible error", and
`interact.mjs` says "all interactions pass".

**F2 - a tip outlived a scrolled-away element.** (Jason's choice, the
orchestrator's decision for the pilot, reversible.) `tooltip.js` adds Floating
UI's own `FloatingUIDOM.hide()` to the middleware, and its `.then` calls
`hideTip()` when `middlewareData.hide.referenceHidden` is set. The vendored
dom build exports `hide`; no vendored file was touched (the SHA-256 test
passes unchanged). The tip still follows its element while it is visible.
Tests: `test_a_tip_goes_when_its_element_is_scrolled_out_of_view` in
`tests/test_shell.py`, and three checks in `pilot/harness/interact.mjs` (a
focused button inside a scrolling box: tip shows; still shows after a small
scroll; hidden once scrolled out of view). Mutation, on a scratch copy under
the scratchpad: deleting the `hide()` line made the harness check "the tip is
hidden once its element is scrolled out of view" fail and the new test fail.

**F3 - the CDN check missed single quotes.** The regex in the loading-order
test now reads a `src` that is double-quoted, single-quoted or unquoted:
`<script[^>]*\bsrc=["']?([^"'\s>]+)`. Mutation on a scratch copy: adding
`<script src='https://cdn.jsdelivr.net/x.js'>` now fails
`test_the_loading_order_is_the_specs_and_the_csp_is_unchanged`.

**F4 - wrong decision number.** "P86" is gone from the test comments and
docstring; they cite "Jason's ruling 5 (2026-09-29)". S6 puts in the number it
logs.

**Ruling 7 (Jason, 2026-09-29) - hover delay 300 ms.** `TIP_DELAY_MS` (already
a named constant) is 300 in `app/renderer/tooltip.js`, and the file's header
comment says 300. Keyboard focus still shows the tip at once.
`test_the_hover_delay_is_300_ms_and_keyboard_focus_waits_for_nothing` pins the
constant, its single use in the hover timer, and that the focus path does not
use it. The harness checks that a hover shows no tip at 200 ms and shows it by
450 ms. Mutation: setting the constant back to 500 failed both the harness
check and the new test.

## Proposed SPEC-shell.md 8.5 edit (SPEC branch not touched here)

- Hover delay: "500 ms" becomes "300 ms". Keyboard focus shows the tip at once
  on every control except the search box.
- Add: "The tip is placed by Floating UI (below, 4 px off, flipped and shifted
  8 px inside the window). It follows its element when the page scrolls and is
  hidden when the element is scrolled out of view."

This supersedes the S7 handoff's "hover delay stays 500 ms" and "clipped by the
window, not hidden" lines.

## Tests run

Each file in its own process, in parallel, on Python 3.11 and 3.13:
`test_shell`, `test_pilot_ui`, `test_tour`, `test_pilot`, `test_single_source`,
`test_layers`, `test_api`, `test_pilot_installer`, `test_row_columns`,
`test_build` (the known OCR scratch-roots failure ignored), `test_repo_map`.
Also `python -m ruff check .`, `shoot.mjs` (all scenarios, including
`real-app`), `interact.mjs`, and `repo_map.py update` then `check`. Results
are in the final report.

## Proposed decision rows

1. **Tooltip scripts load before app.js.** The Floating UI files (`core` then
   `dom`) sit above `app.js` so `app.js`'s start-up, which calls
   `shellVocabulary()` from `shell.js` after its first reply, is not delayed by
   parser-blocking scripts between the two. Pinned by the loading-order test.
2. **A tip hides when its element is scrolled out of view.** Floating UI's
   `hide()` (`referenceHidden`); the tip follows the element while visible.
   Pilot decision, reversible (option b was S3's "any scroll hides it").
3. **Tooltip hover delay is 300 ms**, focus is immediate. Jason, ruling 7,
   2026-09-29. Replaces the 500 ms of SPEC 8.5.
