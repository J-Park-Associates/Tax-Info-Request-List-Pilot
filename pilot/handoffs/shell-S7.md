# Shell S7 - tooltips on Floating UI

Branch `claude/shell-s7-tooltips`, built from S3's clean tip (`afd566d`, branch
`claude/friendly-archimedes-33y9uk`). Last commit: see the bottom line.

## What was done, in plain English

1. **Placement is now Floating UI's.** `app/renderer/tooltip.js` still owns the
   timing (hover delay, keyboard focus, Esc, mouse-out), the one `#tip`
   element with `role="tooltip"` and `aria-describedby`, and the words (the
   API's vocabulary, five words or fewer). Only the hand-rolled placement is
   gone: the tip goes below its element, 4 px off it, flips above when there is
   no room and shifts to stay 8 px inside the window (`offset`, `flip`,
   `shift` from `FloatingUIDOM.computePosition`, strategy `fixed`). The result
   is set with `element.style.setProperty` as before: no `style` attribute, no
   `innerHTML`. It is placed when it shows and again when the window is
   resized or anything scrolls while it shows (before, a scroll hid it).
2. **Jason's ruling 2.** Keyboard focus shows the tip on every control except
   the search box (`#find`); hover shows it everywhere, the search icon
   included (the icon lets the pointer through to the box, so its tip is the
   box's "Find a client"). S3's rule "no tooltip on any focused input or
   textarea" is replaced. The S3 handoff's proposed decision 3 is reworded.
3. **Floating UI is vendored, unedited.** `app/renderer/vendor/floating-ui/`
   holds two script files, three licence files and a README with the versions,
   the tarball integrity and the SHA-256 of every file. `index.html` loads them
   with two plain `<script src>` tags, core then dom, before `tooltip.js`. The
   CSP is unchanged (`script-src 'self'`), there is no inline script, no CDN
   and no network call, and `app/package.json` is untouched.

## The exact package, and why two files

| Package | Version | Registry integrity (matches `npm view ... dist.integrity`) |
|---|---|---|
| `@floating-ui/dom` | 1.8.0 | `sha512-yXSrzeHZBTZadLOlfyhCkJHNeLJnHRnRInwdZ40L7ZiaAtrBwoYlsDrX3v5zB1Utk7CLfzcOVnVVWoXEky7Ceg==` |
| `@floating-ui/core` | 1.8.0 | `sha512-0CIZ5itps/8x7BG8dEIhs53BvCUH2PCoogtakwRTut+Arm58sJooJ0AuZhLw2HJYIR5cMLNPBSS728sPho2khQ==` |
| `@floating-ui/utils` | 0.2.12 | `sha512-HpCo8tmWzLVad5s2d19EhAz5zqrrQ6s69qd6moPMQvkOuSwDT1YgRfWSVuc4ennqrgv3OHppiOGMQ7oC13yIww==` |

Vendored files (SHA-256):

| File | SHA-256 |
|---|---|
| `floating-ui.core.umd.min.js` (from `core@1.8.0`, 12,552 bytes) | `65940d866a6b6d831394a4bbed99ed0a39330bac98b643386d9a2f87a1a1d5da` |
| `floating-ui.dom.umd.min.js` (from `dom@1.8.0`, 10,042 bytes) | `61a46f943c4e99379eaf073447811aec7e8b8f120d2f646316e01b7694bc90a3` |
| `LICENSE-dom`, `LICENSE-core`, `LICENSE-utils` (MIT, identical) | `0e4c9a9b6c71019cbbea3bdc20b01223110a9035700f9c960c8fcbf78c2325ce` |

The three tarballs came from `npm pack` in a scratch folder outside the repo,
and each tarball's integrity was compared with the registry's before any file
was copied. **Least-code option:** the `core` UMD build already has `utils`
compiled in, and the `dom` UMD build has its own DOM helpers compiled in and
asks only for the `FloatingUICore` global. So two unedited files, loaded in
order, give the one global `FloatingUIDOM`. No concatenation, no bundler, and
each byte is checkable against the published package. `utils` is therefore not
a file of its own; its licence is shipped because its code is inside `core`.
The browser-native `.mjs` builds were not used (they need `import`, and the
CSP and the classic-script order the app uses call for UMD).

## Tests

- `tests/test_shell.py` (new or changed claims):
  `test_the_vendored_floating_ui_is_the_pinned_bytes_and_nothing_else` (SHA-256
  of every vendored file, no extra file, the README names the versions and
  hashes); the loading-order test now also checks that every `<script src>` is a
  file of the app (no scheme, no `//`, no CDN, file exists) and that core loads
  before dom before `tooltip.js`; `test_the_tooltip_reaches_floating_ui_only_through_its_one_global`
  (only `FloatingUIDOM`, uses `computePosition`/`offset`/`flip`/`shift`, no
  import/require, none of the old edge arithmetic, no colour or size literal,
  placement only through `style.setProperty`);
  `test_the_search_box_alone_shows_no_tooltip_on_keyboard_focus`.
- `pilot/harness/interact.mjs` (Playwright Chromium from `/opt/pw-browsers`):
  a focused button shows its tip at once and is described by it; Esc hides it;
  the focused search box shows none; hover on the search icon shows "Find a
  client"; moving away hides it; the tip stays inside the window at the right,
  bottom and bottom-right edges; a forced-colors (contrast) theme still shows
  it, sized and inside the window. `pilot/harness/serve.mjs` now serves files in
  subfolders of `app/renderer` (it flattened every path to its last segment, so
  `vendor/...` was a 404); it still cannot leave the renderer folder.
- Mutation proof, on a scratch copy: see "Gate results" below.

## Gate results

Each file its own process, on Python 3.11 and 3.13, same result on both:
`test_shell` 35, `test_pilot_ui` 11, `test_tour` 8, `test_pilot` 18,
`test_single_source` 167, `test_layers` 29, `test_api` 368,
`test_pilot_installer` 12, `test_row_columns` 26 (it scans renderer files) all
pass; `test_build` 30 pass and 1 fails, `test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else`
(OCR, `onnxruntime` missing), the failure the brief said is on the base, so
ignored. `ruff check .` clean. `interact.mjs` passes (all interactions).
`shoot.mjs tooltip-mouse tooltip-keyboard` looked at in light and dark at
1100 x 700: the "Sort now" tip sits 4 px under the sort icon, shifted left to
stay 8 px inside the window edge, caption type on the raised background with
its hairline and shadow, contrast unchanged (no colour touched).

**Mutation proof** (a scratch copy under /tmp, never the repo): changing the
focus rule back to skip every input, deleting `flip` and `shift`, and adding a
byte to the vendored dom file made three `test_shell` tests fail
(`..._is_the_pinned_bytes_and_nothing_else`, `..._only_through_its_one_global`,
`..._search_box_alone_shows_no_tooltip_on_keyboard_focus`); the same copy with
`flip` and `shift` removed made the three edge checks in `interact.mjs` fail
(the tip ran to x 1100 against a limit of 1092 at the right edge, and sat at
top 704 in a 700-high window at the bottom). The repo copy was never mutated.

The repository map was refreshed last (`repo_map.py update`, then `check` and
`test_repo_map`).

## Left for S6

- S6 merges this branch. `app/renderer/index.html` will conflict with S4's
  edits at the script block at the bottom (this branch adds two `<script>`
  lines before `tooltip.js`); keep both sides' lines, with the two vendor lines
  before `app.js` (see rebuild 1, F1). `tests/test_shell.py` may conflict
  where S4 extends `SHELL_FILES` and the loading-order test (that test's script
  list now starts `*FLOATING_UI_SCRIPTS, app.js, tooltip.js`).
- Update SPEC 8.5 (on `claude/admiring-lamport-bp1sse`, not touched here): the
  hover delay stays 500 ms, focus shows the tip on every control except the
  search box, and placement is Floating UI's. SPEC 14's tooltip claims that
  named the old placement code are now the tests above.
- Log the decision row below and `pilot/DECISIONS.md`'s next number. Ruling 5's
  wording "vendored as one file" became two files, for the reason above.
- The installer needs no change: `setup.iss` copies the whole packaged folder
  (`recursesubdirs`), and `app/package.json` has no `files` list, so the
  `vendor` folder ships and nothing else new does.

## Proposed decision row

> **Tooltips: placement by Floating UI, focus on all but the search box.**
> `@floating-ui/dom` 1.8.0 with `@floating-ui/core` 1.8.0 (which holds
> `@floating-ui/utils` 0.2.12), MIT, vendored unedited as two UMD files in
> `app/renderer/vendor/floating-ui/`, SHA-256 pinned by `tests/test_shell.py`,
> loaded by plain script tags (CSP unchanged, no CDN, no runtime install).
> `tooltip.js` keeps its timing, focus, Esc and `role=tooltip` logic and uses
> the library only to place the tip (offset 4, flip, shift with 8 padding).
> Keyboard focus shows the tip on every control except the search box; hover
> shows it everywhere. Tippy.js rejected: built on Popper.js, about 2 MB, last
> released 2021. Jason, ruling 2 and 5, 2026-09-29.

## For Jason

- Hover delay: the brief said about 300 ms; SPEC 8.5 and the code say 500 ms,
  so it is unchanged at 500. Say so if you want 300.
- A scroll used to hide the tip; it now moves the tip with its element (the
  brief asked for placing on scroll). If the element scrolls out of view the
  tip follows it out and is clipped by the window, not hidden.
