# Shell S7 - review 1 (tooltips on Floating UI)

Reviewer: a separate agent that did not build S7. Branch
`claude/shell-s7-tooltips` at `430aa27`, diff `afd566d...HEAD`. No code was
changed; this file and the refreshed repository map are the only changes.

## Verdict

The supply chain is clean and the two rulings are implemented as Jason asked.
There are **four findings**. F1 is a real regression: the harness's real-app
smoke test passes on the base and fails on this branch. F2 is a behaviour
change Jason should decide on. F3 and F4 are small.

## What was checked, and how

**1. Supply chain. I did this myself and did not rely on the builder's figures.**
- I ran `npm pack @floating-ui/dom@1.8.0 @floating-ui/core@1.8.0 @floating-ui/utils@0.2.12`
  in a scratch folder outside the repository. I computed each tarball's
  SHA-512 myself, in Python, and compared it with `npm view <pkg>@<ver> dist.integrity`.
  All three match, and they also match the integrity values in the vendor
  README and in the S7 handoff.
- I read the tarballs in Python and compared the vendored files byte for byte:
  `floating-ui.core.umd.min.js` is identical to `core@1.8.0/dist/floating-ui.core.umd.min.js`
  (12,552 bytes) and `floating-ui.dom.umd.min.js` is identical to
  `dom@1.8.0/dist/floating-ui.dom.umd.min.js` (10,042 bytes). The committed Git
  blobs match the working files (`git hash-object`), neither file contains a
  CR, and `.gitattributes` (`eol=lf`) keeps the bytes the same on Windows.
- SHA-256 of each vendored file (`65940d86...`, `61a46f94...`, and `0e4c9a9b...`
  for the licence files) agrees with the vendor README, with
  `FLOATING_UI_SHA256` in `tests/test_shell.py`, and with the handoff.
- Licences: `LICENSE-dom`, `LICENSE-core` and `LICENSE-utils` are byte-identical
  to each package's `LICENSE`: MIT, "Copyright (c) 2021-present Floating UI
  contributors". Each `package.json` says `"license": "MIT"`. The claim that
  `utils` is compiled into the core UMD holds: the core build is standalone
  and defines only `FloatingUICore`, and the dom build asks only for
  `FloatingUICore`.
- Code read: neither file contains `fetch`, `XMLHttpRequest`, `WebSocket`,
  `sendBeacon`, `eval`, `Function(`, `document.write`, `postMessage`, storage
  access (`localStorage`/`sessionStorage`/`indexedDB`/`cookie`), `import(`,
  `importScripts`, `createElement`, a `.src` assignment or a URL. The only
  `require`/`define` is the standard UMD header, which is inert in the renderer
  (`contextIsolation: true`, `nodeIntegration: false`, `sandbox: true` in
  `app/main.js:383-385`), so the dom build takes the `globalThis.FloatingUICore`
  branch. The dom build does contain `ResizeObserver`, `IntersectionObserver`,
  `requestAnimationFrame`, `addEventListener` and `setTimeout`, but only in
  `autoUpdate`, which `tooltip.js` never calls. The rest is DOM geometry
  (`getComputedStyle`, `visualViewport`, rects). **It is positioning maths and
  nothing else.**
- No `package.json` or lock change, no bundler, no `node_modules` (the diff
  does not touch `app/package.json`). Packaging: `Build App.bat` packs the whole
  `app/` folder with `electron-packager` and no ignore list, and
  `pilot/installer/setup.iss:39` copies the packaged folder with
  `recursesubdirs`. So the vendor folder ships (six files, including its
  README), and nothing else new ships. `pilot/harness/` is outside `app/`.

**2. Rulings 2 and 5.**
- Placement comes only from `FloatingUIDOM.computePosition`, using `offset(4)`,
  `flip({padding: 8})`, `shift({padding: 8})` and `strategy: "fixed"`, which
  matches `#tip`'s `position: fixed`. The 500 ms delay, `:focus-visible`, Esc,
  `pointerdown`, `blur`, `role="tooltip"` and `aria-describedby` are all kept.
- `#find` is the search box (SPEC 8.2 "Search (`#find`)", the combobox at
  `index.html:40`). I walked the controls with the keyboard in the harness.
  `#sort` and the done mark show their tips on Tab. `#find` shows none on Tab,
  Shift+Tab, Ctrl+F or a click. Hover on `#find` shows "Find a client", and so
  does hover on the search icon (checked in `interact.mjs`). The crumb shows no
  tip on focus, which is correct: it is a `setTipIfCut` name that is not cut.
  `#find` is the only `<input>` with a tip today.
- The words are unchanged: they still come from `setTip`, fed by the
  vocabulary and names. `tooltip.js` has no colour or size literal, and no
  `innerHTML`. Its position is set only through `style.setProperty`.
- The CSP is byte-for-byte unchanged (`script-src 'self'`), and there is no
  inline script.

**3. Behaviour (harness, Playwright Chromium from `/opt/pw-browsers`).**
- `interact.mjs` reports "all interactions pass". I ran `shoot.mjs` for
  `tooltip-mouse`, `tooltip-keyboard`, `forced-colors` and `real-app`, then
  looked at the tooltip shots in light and dark at 1100x700 and 1400x900.
  "Sort now" sits 4 px below the icon, shifted 8 px inside the right edge,
  with caption type on the raised background, its hairline and its shadow,
  and it reads correctly in both themes. My own forced-colors probe (hover on
  `#sort`) draws the tip with a CanvasText border on Canvas, inside the window.
  The edge checks in `interact.mjs` pass: the tip stays inside the window at
  the right, bottom and bottom-right.
- `real-app` **fails** on this branch and passes on the base. See F1.
- Scroll: see F2. **SPEC 8.5 does not say "hide on scroll".** It says "kept
  inside the window". Hiding on scroll was S3's choice, not the SPEC's.
- The hover delay is 500 ms, as SPEC 8.5 and the code say. The brief said
  about 300 ms. That is not a defect; it is flagged for Jason below.

**4. Tests and mutation checks.** Each mutation was run on a scratch copy
under `/tmp`, never in the repository:

| Mutation | Result |
|---|---|
| One bit flipped in `floating-ui.dom.umd.min.js` | `test_the_vendored_floating_ui_is_the_pinned_bytes_and_nothing_else` fails |
| Focus allowed on `#find` | `test_the_search_box_alone_shows_no_tooltip_on_keyboard_focus` fails; `interact.mjs` "the focused search box shows no tip" fails |
| `flip` and `shift` removed | `test_the_tooltip_reaches_floating_ui_only_through_its_one_global` fails; `interact.mjs` fails all three edge checks (tip at x 1100, and at y 704 in a 700 window) |
| `<script src="https://cdn...">` added | `test_the_loading_order_is_the_specs_and_the_csp_is_unchanged` fails |
| `<script src="//cdn...">` added | the same test fails |
| `<script src='https://cdn...'>` (single quotes) added | **no test fails**. See F3 |
| An extra file in the vendor folder | the pinned-bytes test fails |
| A README hash changed | the pinned-bytes test fails |

The test names state the claims they make.

**5. Gate.** Each test file ran in its own process on Python 3.11.15 and 3.13.12,
with the same results on both: `test_shell` 35, `test_pilot_ui` 11,
`test_tour` 8, `test_pilot` 18, `test_single_source` 167, `test_layers` 29,
`test_api` 368, `test_pilot_installer` 12, `test_row_columns` 26 and
`test_repo_map` 80 all pass. `test_build` has 30 passes and 1 failure,
`test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else`, the
known OCR failure on the base, which I ignored. `ruff check .` is clean, and
`repo_map.py check` says current.

**6. Scope and standing rules.** The harness uses only made-up names. Nothing
touches the network, reads a client document or sends anything. The changes
beyond the tooltip are all within the brief:
- `pilot/harness/serve.mjs` now serves subfolders. That was needed for
  `vendor/`, it still strips `..` and `.`, and it serves files only.
- `pilot/handoffs/shell-S3.md`: S3's proposed decision row 3 is reworded for
  ruling 2.
- `docs/repo-map.*` was regenerated.

Nothing else is touched.

## Findings

**F1 - The real `app.js` no longer starts in the harness: the new script tags
sit between `app.js` and `shell.js`.**
- *Where:* `app/renderer/index.html:754-755`, with the order pinned at
  `tests/test_shell.py:338`.
- *What the SPEC says:* SPEC 14.4 has the harness run a smoke test of the real
  `app.js` (`shoot.mjs real-app`), and the S3 reviews passed it. The base
  `afd566d` still passes it ("side panel Overview|Needs review|Reminders|Clients,
  0 logged").
- *What the code does:* `app.js` calls `bootstrap()` as it loads.
  `loadEngagements` awaits `call(["list"])` and then calls `shellVocabulary()`,
  which is defined in `shell.js`. Two more parser-blocking scripts now load
  between `app.js` and `shell.js`, so the stub's reply arrives before
  `shell.js` exists. On this branch, `shoot.mjs real-app` fails on every run
  (3 of 3): "ReferenceError: shellVocabulary is not defined", the side panel
  is empty, and the app shows its own-error notice. In the installed app the
  reply is an IPC round trip to Python, so the race is unlikely to show there.
  But this ordering makes the race wider, and the smoke test that guards
  start-up is now red. The builder ran only the tooltip scenarios, so this
  was missed.
- *Smallest fix:* load the two vendor scripts before `app.js`, directly above
  `<script src="app.js">`. They depend on nothing, and they still come before
  `tooltip.js`. Change the test's order list to
  `(*FLOATING_UI_SCRIPTS, "app.js", "tooltip.js", ...)`, and correct the
  handoff's S6 merge note. I tried this on a scratch copy: `real-app` passes
  and `interact.mjs` passes.

**F2 - A tip now outlives its element when the page scrolls, and floats over
the path bar pointing at nothing.**
- *Where:* `app/renderer/tooltip.js:130-136` (`replaceTip` on `scroll`) and
  `57-73` (no `hide` middleware).
- *What the SPEC says:* SPEC 8.5 says only "kept inside the window", not
  "hide on scroll". Ruling 5 asks for "keep inside the window".
- *What the code does:* I put a button with a tip inside `#page` on the
  Clients page, gave it keyboard focus, and scrolled `#page` by 120 px. The
  button scrolled under the top of `#page` (button top -16, `#page` top 48),
  so it is invisible. Its "Sort now" tip stayed shown at top 12, over the
  brand strip and the path bar (light and dark, at 1100 and 1400). `shift`
  moves only on the x axis by default, so an element that scrolls out of the
  window vertically takes its tip out with it. The handoff says this itself
  ("clipped by the window, not hidden"), which departs from "kept inside the
  window".
- *Smallest fix (Jason picks one):*
  - (a) Add `FloatingUIDOM.hide()` to the middleware, and in the `.then` call
    `hideTip()` when `middlewareData.hide.referenceHidden` is set. The tip then
    follows its element while the element is visible and goes away when the
    element is clipped.
  - (b) Go back to S3's `scroll -> hideTip` and keep `resize -> replaceTip`.
  - Either way, add an `interact.mjs` check that scrolls a focused tip's
    element out of `#page`.

**F3 - The "no CDN script" check misses a single-quoted `src`.**
- *Where:* `tests/test_shell.py:341`,
  `re.findall(r"<script[^>]*\bsrc=\"([^\"]+)\"", html)`.
- *What the test claims:* "Every script is a file of the app itself: no scheme,
  no host, no CDN."
- *What it does:* it matches only double-quoted `src`. In the mutation check,
  `<script src='https://cdn.jsdelivr.net/...'>` passed every test. The pinned
  CSP (`script-src 'self'`) would still block that script at run time, so this
  is a gap in the test, not in the app.
- *Smallest fix:* match either quote, or none: `r"<script[^>]*\bsrc=[\"']?([^\"'\s>]+)"`.
  Or assert that every `<script` tag's `src` was captured, by counting
  `<script` against `len(sources)`.

**F4 - The test cites a decision number that is not S7's.**
- *Where:* `tests/test_shell.py:48` and `:351` ("decision P86").
- *What the plan says:* S6 logs the rows from P85 onward. S3's five proposed
  rows come first (`shell-S3.md:78`, `pilot/HANDOFF.md:72`), then Jason's six
  rulings. P86 would be S3's row 2, "One keydown listener".
- *What the code does:* it names P86 for the Floating UI decision.
- *Smallest fix:* cite "Jason's ruling 5 (2026-09-29)" for now and let S6 put in
  the number it logs. Or S6 renumbers these two comments when it logs the row.

## Notes for Jason

- **Hover delay.** It is 500 ms, as SPEC 8.5 and S3's code have it. The brief
  said about 300 ms. It was left at 500. Say if you want 300; that is a
  one-constant change plus the SPEC line.
- **Scroll behaviour (F2).** Before S7, any scroll hid the tip. Now it
  follows its element, including out of sight. I recommend option (a): Floating
  UI's own `hide`, so the tip follows while its element is visible and goes
  when it is not.
- **Ruling 5 said "one file"; S7 ships two** (the unedited core and dom UMD
  builds, loaded in order). I agree with that choice. Joining them into one
  file would mean the bytes no longer match the published package, and that
  match is the point of pinning the hashes. It is worth a word in the decision
  row, which the handoff already gives.
- **Upgrades.** The vendor README says how to upgrade (npm pack outside the
  repository, compare integrity, copy the file, and change the README and the
  test together). The check is repeatable: every hash above I recomputed from
  the registry's tarballs myself.
- **Text boxes.** `#find` is the only text box with a tip today. A text box
  counts as `:focus-visible` even when it is clicked, so a tip added later to
  another input would show on a mouse click as well as on keyboard focus.
  That is within ruling 2 ("every control except the search box"), but it is
  worth knowing if tips are added to editor inputs.
