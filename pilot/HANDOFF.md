# Pilot handoff

## Build E, the structure pass (2026-09-29, built; branch `claude/keen-keller-vx7xxj`, not pushed)

Built exactly [`SPEC-ui.md`](SPEC-ui.md) (P51-P55): one new file,
`app/renderer/pilot-ui.css` (tokens, type ramp, one button shape in four
importances and two sizes, command bar, surfaces, inputs, dialogs, a
`forced-colors` block last), loaded between `style.css` and `pilot-style.css`.
`style.css`, `app.js`, `main.js`, `preload.js` and `tracker/` are untouched.
Other edits: one link line in `index.html`, `next.classList.add("btn-primary")`
in `tour.js`, `pilot-style.css` now written in the tokens (no literal colour,
size or step left), a `pilot-ui.css` node and `loads` edge in the curated map,
`tests/test_pilot_ui.py` (9 tests). The SPEC author added P55 mid-build
(`.main > * { flex-shrink: 0 }`, a bug of 0.1 that let every card collapse to a
sliver when notices filled the window); it is in SPEC 7.1, `DECISIONS.md` and a
test.

Commits (each `[skip ci]`, map refreshed in each): step 1 tokens and type,
step 2 buttons and the tour's Next, step 3 top bar and command bar, step 4
surfaces/inputs/rows/dialogs, step 5 `pilot-style.css`, step 6 rendered-check
fixes, P55, screenshots and this entry.

**Open question for Jason (SPEC 5.7).** A Needs review row can show two
primaries, **File it** and, in its own block, **File it under {label}** (a deck
card likewise). Both stay primary; the second block is set apart with a tinted
box so each primary leads its own block. Which answer should lead is a product
decision.

**Deviations from the SPEC, and why.**

- `ul.review > li` is `padding: var(--sp-3) 0`, not `sp-3 sp-4`: the list is
  already inset 16px by the card body, so 16px more would push rows in from the
  card head.
- `.pilot-tour-card h3` (the What it does / Why it's safe labels) is a sentence-
  case caption in `--subtle` (SPEC 4's caption rule), not a dialog-sized title
  as SPEC 4's last line reads for it; the tour's step title (`h2`) got the title
  size. The stage chips in the tour card pad `0 var(--sp-1)` so five fit the
  400px card.
- Rules the SPEC does not name, added because the rendered check showed a fault
  (all on the grid and in tokens): `.rem-stage .rem-stage-n { opacity: 1 }` (the
  75% fade put the count at 3.5:1); `.editor-actions .btn { align-self: center }`
  (a stretched flex row made two 24px buttons 28 and 32px tall);
  `.editor-actions { gap }` and `.household-return { display: flex; gap }` (small
  buttons and the "not drafted yet" note touched); `.form-chosen` wraps and
  `.wiz-back`/`.chosen-badge` never wrap (labels broke onto two lines);
  `.deck-card .c-open-copy { justify-self: start }` (Open stretched across the
  card, as it did in 0.1); `.editor-table` first column has no left padding (it
  lines up with the text above); `.where-it-waits { grid-column: 1 / -1 }`.
- The wizard's per-person Remove has no hook class; `.person .editor-actions
  .btn` matches it and nothing else, so it is danger (SPEC 5.5 satisfied).
- Not changed, SPEC silent: `.rem-stage:disabled` still fades (`opacity: 0.55`
  in `style.css`); a stage label in the Reminder card ("Response Requested;
  Deadline Approaching") still wraps to two lines at 1366px, as in 0.1 (it is a
  `.rem-stage`, not a `.btn`).
- `tests/test_pilot.py` needed no change (no test pins the stylesheet list).

**Rendered checks** (Chromium 1194, the harness page and stub, made-up names
only; scripts in the session scratchpad, not the repo:
`scratchpad/sweep/sweep.mjs`). Segoe UI is not on this machine, so text fell
back to a wider sans: wrap findings are the pessimistic case.

- 12.1 screenshots: 13 before (made from the pre-build commit `b8ad769`) and 13
  after, in `pilot/reviews/ui-screens/before-<scenario>.png` and
  `after-<scenario>.png`: main at 1366x860 and 1100x760 (full and `-viewport`),
  review-cards, setup, editor, wizard, wizard-form, wizard-requests, schedule,
  terms, tour. All 26 were looked at. After the P55 fix the `-viewport` shots
  show whole cards with the page scrolling.
- 12.2 sweep, 11 scenarios (dialogs and the tour swept inside their own
  surface): 1,927 visible elements, 1,121 with text, 100 `.btn` and 71
  `.btn-small`. **After the fixes above: 0 findings**: every `.btn` 32px and
  every `.btn-small` 24px tall, every text size 12/14/16/20px, every weight
  400/600, every text colour 4.5:1 or better against its effective background
  (disabled excepted). The first run found 4 (two `.rem-stage-n` at 3.5:1;
  `.ed-fold-all` 28px and `#ed-rename-btn` 32px), all fixed.
- 12.3 toolbar at 1100px: 14 children on 3 visual rows, none clipped, none
  overlapping, no horizontal scroll; `#btn-scan` is the only filled button.
- 12.4 `forced-colors: active` and `prefers-reduced-motion: reduce`: 33 buttons,
  0 without a border, selected control 2px `Highlight`, focus ring solid 2px
  (`Highlight`), 0 running animations, every button's transition `0s`. In the
  normal theme the first Tab lands on the engagement picker with a 2px blue
  ring. A disabled button was set by hand and checked: `#94a3b8` on
  `#f1f5f9`, opacity 1, the subtle one transparent.
- 12.5: no console or page error in any scenario.

**Gate.** `ruff` clean; `repo_map.py update` then `check` current (197 nodes);
`test_pilot_ui`, `test_pilot`, `test_tour`, `test_single_source`,
`test_layers`, `test_repo_map`, `test_api` pass under Python 3.11.15 and 3.13.12
(9, 15, 8, 167, 29, 80 and 368 tests). Two things about the run, not the code:
`test_single_source.py` exits 1 with all 167 passed, on this machine only,
because the decision 185 tripwire sees `main.js` (run by the one-window test)
start the checkout's real `tracker.api` when a `.venv` sits in the checkout;
the pre-build commit does the same with a `.venv` beside it, so it is not from
this build. `test_api.py` under both Pythons at once collides on
`/tmp/Real root`; run the two interpreters one after the other.

**Left.** Review by a separate Opus session that did not build it. Jason's look
on Windows 11 at Segoe UI Variable's real rendering (widths differ from the
fallback used here, so re-check the wizard's Change-form row, the tour's stage
chips and the reminder stage labels), and the hands-on contrast-theme check
from the section below.

## Done

- **Job 0 (2026-09-28):** pilot started from the original's `main` at `a2d6af4`
  (PR #139, decision 209); `README.md`, `DECISIONS.md`.
- **Job 1 (2026-09-28):** [`SPEC.md`](SPEC.md) written; decisions P8-P16 added.
- **Move (2026-09-28, P17-P19):** the pilot now lives in its own repository,
  `J-Park-Associates/Tax-Info-Request-List-Pilot`, whose `main` is the pilot.
  SPEC gained section 3a (the pilot's own names on the PC and the two-folder
  deny list). The renames are **not made yet**: Build A makes them first.
- **Build B (2026-09-28, branch `claude/practical-feynman-ua2clc`, draft PR to `main`):**
  `app/renderer/pilot-content.js` (terms and tour JSON copied from SPEC sections 7 and 8
  by script, so the wording is exact), `pilot.js`, `tour.js`, `pilot-style.css`, the four
  `index.html` lines, `tests/test_pilot.py`, `tests/test_tour.py`. Checked in real Chromium
  with a stubbed tracker (Electron is not installed in the cloud): badge shows, terms show
  once and Escape/Tab cannot leave them, the tour starts after accepting, all 11 steps
  highlight their element or show their fallback, and terms and tour do not reappear after
  a reload. Not checked in the packaged Electron window. Gate run under Python 3.11 only.
  P24's four fallbacks are in; the test requires a non-empty fallback whenever anchors are non-empty.
- **Build A (2026-09-28, branch `claude/kind-fermi-cjkoxl`, draft PR to `main`):**
  - Commit 1: the section 3a renames (`app/package.json`, `pyproject.toml`,
    `tracker/settings.py`, README and ROADMAP first lines) and the P19 deny
    list (both data folders) with its test change
    (`UPSTREAM_DATA_HOME_NAME` in `tests/test_single_source.py`). One more
    line the SPEC did not list: `.github/workflows/build.yml` names the data
    folder in its "package holds no data" check, and `test_build.py` requires
    it to equal `DATA_HOME_NAME`, so it now says `tax-document-tracker-pilot`.
  - Commit 2: `pilot/installer/setup.iss`, `pilot/Build Pilot Installer.bat`,
    `pilot/Tester Guide.md`, `tests/test_pilot_installer.py`.
  - Left for others: the `.bat` and `setup.iss` were never run (no Windows or
    Inno Setup here); the `.bat` needs `pilot-content.js` from Build B; the
    Tester Guide's Schedule section describes Build C's button.
  - Not caused by Build A, failing in the cloud only: one test fails (needs Tesseract, fails the same on main) and three are skipped:
    `test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else`
    needs the scanned-text reader, which is not installable here.

- **Build C (2026-09-28, P21, branch `claude/festive-mayer-wpxbo2`, draft PR to
  `main`):** SPEC section 12 built - the saved schedule choice, every
  registration path using it, the "off" outcome, the launch comparison, the
  `set-schedule` command and `vocab.schedule`, the Schedule button and dialog,
  the once-a-day wording, the interval-aware last-pass rule, the runbook
  passages and the 12.8 tests. Gate run: ruff, repo-map `update` and `check`,
  the affected tests under Python 3.11 and 3.13 (all pass except four
  `test_ocr.py` tests and four setup errors that need `onnxruntime`/`rapidocr`,
  which the cloud venv lacks; Build C touches no OCR code).
  - **Deviations from SPEC 12 for the next reader:**
    1. The choice, its checks (`check_start`, `check_every`, `EVERY_CHOICES`,
       `ScheduleChoiceError`, `SchedulePreference`) and the two defaults live in
       `tracker/settings.py`, not `scheduling.py`. The runner must read the
       saved interval for the last-pass line and may not import `scheduling`
       (`tests/test_layers.py`), and `settings` may not import upward.
       `scheduling` re-exports the names, so `scheduling.check_start` etc.
       work as the SPEC says. `scheduling.DEFAULT_START` /
       `DEFAULT_REPEAT_MINUTES` are now aliases of the settings defaults.
    2. `runner.LAST_PASS_NEVER` no longer says "within two hours" (untrue for a
       longer interval); `LAST_PASS_OLD` is now a template taking `{hours}`.
       New: `LAST_PASS_OFF`, `LAST_PASS_AMBER_HOURS_DAILY`, `amber_hours()`.
    3. `settings` also returns `schedule_problem` (a sentence) and
       `schedule: null` when a hand-edited value is refused; the dialog shows
       the sentence and starts from the defaults.
    4. Extra: `vocab.schedule.loading` (the dialog's loading line), and a few
       CSS lines for the dialog in `style.css`.
    5. The runbook's move step says a move keeps the saved time and interval.
  - **Merge notes:** B and C both edit `index.html` (different spots). Both
    edit `docs/repo-map.*`: merge, then `python tools/repo_map.py update`,
    never hand-resolve.
  - **Decision text to log** (the integrate session numbers it): none new;
    P21 covers this build.

## Status (2026-09-28, orchestrator)

Builds A, B and C are reviewed, fixed and merged into `main` (7a8432e,
cca50a7, 96853df). Reviews: `pilot/reviews/review-1.md`, `review-2.md`.

## Waiting on Jason

The Windows check. Easiest: the test kit in `pilot/wintest/` - paste
`pilot/wintest/PROMPT.md` into Claude Code on any Windows test PC (P28); the
result arrives on branch `wintest-results` and as a `[WINTEST]` comment on
board #5. By hand: `RELEASE.md`.

The Windows steps in [`RELEASE.md`](RELEASE.md): run the gate under the
office's Python, build the installer, install and try it, uninstall, then tag
`pilot-0.1` and send it.

## Next after 0.1: Build D, the glass theme (pilot 0.2, P30)

It does not block 0.1.

- **SPEC (2026-09-29, branch `build-d-spec`, draft PR to `main`):**
  [`SPEC-glass.md`](SPEC-glass.md) written; decisions P31-P44. Jason chose a
  soft navy gradient backdrop and light mode only for 0.2 (P31). Verified:
  Electron 43 = Chromium 150, which has `backdrop-filter` with `url(#svg)`,
  `corner-shape: superellipse()` (139+) and `prefers-reduced-transparency`
  (118+); the cloud's Playwright Chromium is 141, enough for every check.
  One correction to the starting analysis (P32): the theme must not override
  `--card`/`--shadow`/`--radius` globally - they paint solid lists and inputs
  too, and most radii are literals - so it uses its own tokens by selector.
  The token values in SPEC section 4 were checked with the section 10.2
  contrast model before writing: every pair is 4.5:1 or better.
- **Revised (2026-09-29, same branch):** a preview mock-up (scratch only,
  made-up names) showed a sticky-toolbar gap and squashed cards (fixed in SPEC
  6.2, P37). Jason then asked for thinner glass, a 3D effect and movement; the
  SPEC now carries them (P41-P44): 55-65% glass, a lit rim and depth shadows,
  a pointer light, button spring, arrival motion, a scrolled toolbar and a
  Full-level backdrop drift, with a per-surface contrast proof (P42) whose
  figures were computed before writing.
- **Speed pass (2026-09-29, P45):** every click and movement measured on
  the mock-up in software rendering (the Remote Desktop case). The pointer
  light moved to the Full level, all timings cut to 200ms or less, the drift
  moved to its own layer and pauses in the background. Glass went from 28 to
  45 frames a second with the pointer moving, 38 to 42 while scrolling, and a
  dialog from ~200ms to ~120ms to readable. SPEC 7.3 carries the numbers and
  the budget Build D must meet.
- **Waiting on Jason:** approve `SPEC-glass.md` (the picker wording in 7.2 is
  proposed copy), then merge the SPEC PR.
- **Build D is done** (see its entry below); next **Review 3** (opus, high
  effort, a session that did not build), then rebuild/review until no findings. The two prompts
  are below; paste each into a fresh claude.ai/code session on this
  repository.

### Build D prompt (sonnet, default effort)

```
You are the Build D builder for the Tax Document Tracker Pilot: the glass
theme, pilot 0.2. Build exactly pilot/SPEC-glass.md and nothing more.
Read first, and nothing else to start: pilot/README.md, pilot/DECISIONS.md
(P30-P45), pilot/SPEC.md section 2 (the page rules you still obey),
pilot/SPEC-glass.md (all of it), pilot/HANDOFF.md. Use
`python tools/repo_map.py show <file>` for the renderer files and read only
the line ranges the SPEC names; never read docs/repo-map.md whole.
Follow SPEC-glass section 11 in order, one commit per step, every commit
message with "[skip ci]". Never edit app.js, main.js, preload.js, style.css
or anything under tracker/. No Apple name or "Liquid Glass" in any product
file. Use only made-up names in the stubbed page; never open a client file.
The rendered checks use the cloud's Playwright Chromium
(executablePath /opt/pw-browsers/chromium-1194/chrome-linux/chrome); their
scripts stay in your scratchpad, their results go in the handoff.
Run the gate from CLAUDE.md (dead code, ruff, repo_map update + check, the
affected tests under Python 3.11 and 3.13; the cloud venv notes are in
HANDOFF.md). Push your session branch, open a draft pull request to main
titled "Build D: glass theme", and add a Build D entry to pilot/HANDOFF.md:
what was done, any deviation from the SPEC and why, the sweep results, what
is left. Report in plain English.
```

### Review 3 prompt (opus, high effort)

```
You are Review 3 for the Tax Document Tracker Pilot: an independent review of
Build D, the glass theme, in a session that built nothing. Read first:
pilot/DECISIONS.md (P30-P45), pilot/SPEC-glass.md, pilot/HANDOFF.md (the
Build D entry), then the Build D pull request's diff. Use
`python tools/repo_map.py show <file>`; never read docs/repo-map.md whole.
Check the build against SPEC-glass section 13, item by item. Re-run the
rendered contrast sweep and the four reduced-preference emulations yourself
in the cloud's Playwright Chromium with a stubbed page and made-up names
only, and look at every screenshot in pilot/reviews/glass-screens/. Run the
gate's affected tests under 3.11 and 3.13, ruff, and repo_map check.
Write numbered findings, each against a SPEC section, with the file and line
and the fix, in pilot/reviews/review-3.md; say plainly if there are none.
Commit with "[skip ci]", push to your session branch, and report in plain
English. Do not fix anything yourself.
```

## Glass removed entirely (2026-09-29, P49, P50; branch `claude/amazing-maxwell-b4hdzo`)

Jason: "remove Mica and refraction completely", then "remove glass entirely,
align with MSFT docs but keep our design theme". Mica was already out (P48; PR
#9 is abandoned). Now gone too: `glass.css`, `glass.js`, the Screen effects
picker and its `glass` block in `pilot-content.js`, `test_glass.py`, the
screenshots and clips, and Tester Guide section 8 (later sections renumbered).
`SPEC-glass.md` stays, marked withdrawn. The look is `style.css` as it was.
Added: a `forced-colors` block at the end of `pilot-style.css` (Windows contrast
themes) and one test for it in `test_pilot.py`. PR #10 is superseded by this
branch; nothing from it that is not in this branch should be merged.
Left: Jason's hands-on check of the contrast-theme block on Windows (Settings,
Accessibility, Contrast themes); the version label still reads 0.2.

## Build D (2026-09-29, done; branch `claude/build-d-pilot-handoff-w5w7mx`, draft PR #10 to `main`)

Status: **all nine steps of SPEC-glass section 11 are done and the gate
passes.** Steps 1-5 were built on `build-d` by the first session; a second
session carried that branch forward (fast-forward, same commits) and did
steps 6-9. Next: **Review 3** (prompt above), in a session that built nothing.

**Steps 1-5 (first session)**
- Step 1: `pilot/make_glass_lens.py` and `app/renderer/glass-lens.png`.
- Step 2: the three `index.html` additions. **Deviation:** the lens image does
  not load from a file inside a backdrop filter in the cloud Chromium (rim
  identical with and without the filter). The same bytes inlined as a
  `data:image/png;base64,` `href` do (rim differs in 1200 of 2500 pixels, centre
  in 0). SPEC section 3 allows this fallback; the test accepts either form and
  checks the inline bytes equal the file.
- Step 3: `glass.css`. **Deviations from SPEC 7.2:** (a) dialogs' and terms'
  dim fades in through `background-color` on the overlay, not `opacity`,
  because an overlay with opacity below 1 becomes a backdrop root and the
  glass card would draw with no blur until the fade ended; (b) `display` is
  not in any `transition`, because with `allow-discrete` it would delay
  closing a dialog by the transition time, and the SPEC says closing is
  instant. Entry motion works from `@starting-style` alone. **Known
  limits:** `.modal` scrolls (`overflow-y: auto`), so its lit rim scrolls with
  the content on a tall dialog (the editor); `.rem-stages` gets the inner
  radius but nothing visible (it is a bare grid).
- Step 4: `glass.js`, the `glass` block and version 0.2 in `pilot-content.js`,
  `tour.js` and `pilot-style.css` (spot radius).
- Step 5: `tests/test_glass.py` (24 tests) plus the `test_pilot.py` and
  `test_tour.py` changes.

**Step 6: rendered sweep, reduced preferences, speed (second session)**
- *Contrast sweep:* every visible text inside a glass surface, its computed
  colour against that surface's 10.2 worst case, with any translucent layer
  between them composited on top, an opaque layer taken as the background,
  and a gradient background sampled at the text's own height. 18 states (main
  screen, New household, Edit household, Schedule, the request-list editor,
  the handover dialog shown by class, the terms, all 11 tour steps) at Glass,
  Glass with refraction and Solid: **2,247 pairs, none under 4.5:1.** Lowest:
  header 4.87, card 5.02, toolbar 5.48, dialog 5.80 (Solid: 5.02-6.83). Three
  failures were found and fixed on the way, all token or selector changes in
  `glass.css`, which the reviewer checks against SPEC 13.2:
  1. **Header picker** white text on its fill: 4.48:1. `--glass-picker-fill`
     `rgba(255, 255, 255, 0.10)` -> `0.06` (SPEC 7.4 said 0.10): 4.87:1.
  2. **Held-reminder line** (`.rem-hold`, coloured by the reminder stage's
     `--stage-ink`) on the glass reminder card: 2.35:1. New rule
     `#reminder-card .rem-hold { color: var(--glass-warn); }`: 5.95:1. The
     selector is inside `GLASS_TARGETS` (`#reminder-card`), and `--stage-ink`
     itself is untouched (the test still passes); the stage pills keep their
     colours. The line reads dark brown instead of the stage's amber.
  3. **Solid made Sort & Scan invisible** (found in the screenshots, which is
     why the sweep now reads gradients): SPEC 4.2's Solid
     `--glass-control-gloss` is `linear-gradient(#ffffff, #ffffff)`, an opaque
     white layer over `.btn-primary`'s dark fill, so its white label was 1:1.
     Now `linear-gradient(rgba(255, 255, 255, 0), rgba(255, 255, 255, 0))` at
     Solid and in both fallback blocks (they must match): 14.69:1, and the
     other toolbar controls stay white from `--glass-control`. **The SPEC's
     table should be corrected** to the new value.
- *Reduced preferences* (each emulated through the DevTools protocol at the
  Full level, plus the Solid level alone, a dialog open): no element has a
  computed `backdrop-filter`; header, toolbar, cards and dialog are opaque;
  the picker is disabled with its note under each of the four (not at Solid,
  as the SPEC says); **no running animation under reduced motion**. Under the
  other three the dialog's arrival fade runs, which SPEC 8.2 allows.
- *Speed probe* (SPEC 7.3 method, the real page with the stub, the cloud's
  software rendering, two runs each; the dialog is timed from the moment it is
  un-hidden, which is what "within 150ms of being shown" says - the app itself
  takes about 10ms from click to showing it):

  | | Pointer sweep | Scroll 600px | Dialog readable | Press |
  |---|---|---|---|---|
  | Glass (budget 40 fps, 150 ms) | 56.9 / 56.9 | 55.9 / 53.7 | 134 / 133 ms | first frame |
  | Solid (budget 55 fps, 150 ms) | 60 / 60 | 60 / 60 | 102 / 107 ms | first frame |
  | Glass with refraction (150 ms) | 19.5-20.7 | 21.5-25 | **116-219 ms (7 runs, median ~160)** | first frame |

  "Press: first frame" means the button's scale transition has started on
  the first animation frame after the pointer goes down, at every level.
  **One budget miss, for the reviewer:** at Glass with refraction a dialog
  is readable in more than 150ms in most runs. Pausing the drift (the theme's
  own `glass-paused` switch) lifts the frame rate to about 50 but leaves the
  dialog at 107-216ms, so the cost is the refraction filter drawn on the
  dialog in software, not the drift. That level is the one the SPEC and the
  Tester Guide reserve for a PC with a graphics card; no change was made.

**Step 7:** Tester Guide section 8 "Screen effects" (later sections renumbered
9-11; the one cross-reference, "section 8 says plainly what it will not do
yet", now says section 9). Curated map roles for `glass.css`, `glass.js`,
`make_glass_lens.py` and `test_glass.py`. **Deviation:** `glass-lens.png` has
no role of its own, because the map indexes text files only (a curated node
for an untracked type fails `check`); it is described in the roles of the
script that draws it and the sheet that uses it.

**Step 8:** `pilot/reviews/glass-screens/`: `1-main-scrolled-*`,
`2-dialog-*`, `3-terms-*`, `4-tour-*` each as `-glass`, `-solid` and
`-transparency-off` (emulated), `5-dialog-refraction.png`, and
`6-motion-glass.webm` (17.9 s: cards arriving at load, pointer across the
toolbar and the reminder card, a scroll, a held press released off the
button, the New household dialog arriving). Extra, for Jason's "video of the
theme in action": `6-motion-refraction.webm` (19.5 s, the same script at
Glass with refraction, showing the pointer light and the drift). The tour
shot is step 2, the first step whose spot sits on a toolbar control.
**How they were drawn, and one finding for the Windows check:** Chromium's
pure software drawing mode (the cloud default) does not blur the sticky
toolbar's *buttons* behind a dialog or the tour card: they show through
sharp and faded, while everything else behind is blurred. It is not the
CSS: every property of the buttons was switched off in turn with no change,
and with Chromium's GPU path emulated (SwiftShader,
`--use-angle=swiftshader --enable-unsafe-swiftshader --enable-gpu`) the same
page blurs them correctly. The screenshots and clips therefore use the GPU
path, as a PC with a graphics card draws. Two consequences: over Remote
Desktop, where Chromium can fall back to software, the sharp ghost may show
(the guide already says to pick Solid there); and **at Glass with refraction
the ghost shows even on the GPU path** (`5-dialog-refraction.png`), so the
SVG filter probably forces that surface back to software drawing. Jason
should look at a dialog at Glass with refraction on his own PC.

**Step 9, the gate:** dead-code scan of the changed files (nothing unused or
commented out in the JS or CSS); `ruff check .` found three lint issues in
`tests/test_glass.py` (two `zip()` without `strict=`, one unused loop name),
fixed. `repo_map.py check` then failed
`test_a_module_is_tested_by_its_own_test_file_if_and_only_if_that_file_exists`:
the generator gives a `tests/test_<stem>.py` its owner edge only when one file
has that stem, and `glass.js` shares "glass" with `glass.css`. **Change
outside the SPEC:** `tools/repo_map.py` now counts only the node types a test
can own (`OWNED_TYPES`: module, tool, workflow, script, the same four the test
checks), so a stylesheet no longer hides a script's owner. Before/after
comparison: exactly one owner edge added (`tests/test_glass.py` ->
`app/renderer/glass.js`), none removed. Map updated and `check` current.
Tests, each file its own process, under Python 3.11 and 3.13: `test_glass`
24, `test_pilot` 11, `test_tour` 8, `test_layers` 29, `test_single_source`
167, `test_repo_map` 80, and `test_vocab_report` 28 (it imports the map
tool): all pass. `git diff main` on `app.js`, `main.js`, `preload.js`,
`style.css` and `tracker/` is empty.

**Left**
- Review 3 (opus, high effort, separate session; prompt above), then
  rebuild/review until no findings.
- Jason: the section 12 checklist on the screenshots and clips, then on
  Windows with the installed 0.2 - including a dialog at Glass with
  refraction (the ghost above) and one over Remote Desktop at Glass.
- SPEC-glass 4.2 and 7.4 to be brought in line with the two token changes
  (gloss at Solid, picker fill), once the review accepts them.
- `.claude/skills/fluent-2-design/SKILL.md`, which the update below says was
  added, is **not in the repository** (only `.mcp.json` is). Whoever takes
  up Fluent 2 should add it or correct that line.

**Scratch tooling (in the session's scratchpad, not committed; rebuild if the
session is gone):** a Playwright harness (Node, the global `playwright`
package, `NODE_PATH=$(npm root -g)`) that opens the real
`app/renderer/index.html` over `file://` and replaces Electron's preload with
a bridge (`page.exposeFunction`) to the real `python -m tracker.api`, with
`TRACKER_SETTINGS_DIR` and `TRACKER_DATA_HOME` pointed at the scratchpad and a
made-up root built by `tests.samples.build_scratch_root` (Smith Family),
`set-root`, and one `run-now --engagement <its return>` pass, so the review
card has five items and the reminder card shows. Terms and tour are skipped
or shown by setting `pilot.terms.accepted` and `pilot.tour.seen` in local
storage; the level by `pilot.glass.level`. Reduced preferences are emulated
with CDP `Emulation.setEmulatedMedia` (Playwright has no
`prefers-reduced-transparency`). The page's CSP refuses injected styles, so
experiments use `element.style` or the theme's own classes. No client file
was opened.

**Requests received mid-build and NOT done (need Jason's decision)**
1. *Fluent 2 as the default UI language.* Not set up. The safety check blocked
   registering the third-party `mcp-fluent-ui` server (`.mcp.json`; npm
   package version 1.0.2, individual maintainer, last updated Sept 2025) and
   blocked writing a `fluent-2-design` skill and a CLAUDE.md default. Nothing
   about it is in the repo. Also open: Fluent UI v9 is React and the app is
   plain JavaScript (Jason's no-new-framework rule), and Fluent's 4/8/12px
   corners differ from SPEC-glass's 20-28px concentric ones.
2. *Native window materials (`pykeio/vibe`, `GregVido/mica-electron`).* Not
   added and not verified: neither repository has been read. They would (a)
   need `app/main.js` changes (a transparent frameless window and a native
   call), which SPEC-glass section 1 and P32 forbid for Build D; (b) add
   native Windows binaries that cannot be built or run in the cloud, so the
   Windows check kit would have to prove them; (c) require the page to have no
   solid background, which contradicts `glass.css`'s backdrop gradient (the
   theme's whole look is painted in the page). This is a design change, not an
   add-on. It needs its own SPEC and a decision on which of the two, if either,
   and whether it replaces Build D's in-page glass or sits beside it.
   **Update (Jason, later 2026-09-29):** Fluent 2 is *opt-in, not the default*
   and the `fluent-ui` server is approved: `.mcp.json` (pinned 1.0.2) and
   `.claude/skills/fluent-2-design/SKILL.md` are added; CLAUDE.md is unchanged.
   Native materials: Electron itself has `BrowserWindow.backgroundMaterial`
   (`mica`, `acrylic`, `tabbed`; Windows 11 22H2+, since Electron 26), so no
   third-party module is needed; it still needs a `main.js` edit and a
   transparent page, so it needs its own SPEC.
3. Neither third-party integration should be added by a builder without
   Jason's explicit approval of the exact package and version.

## Mica: dropped (Jason, 2026-09-29, P48)

Jason first asked to try Mica, then to ship it in 0.2, then, after seeing what
it needs (a `main.js` change, a transparent page, a new contrast proof over the
user's wallpaper colour, a Windows-only check): "lets just forget mica". There
is no Mica job. Do not write `SPEC-mica.md` or change `createWindow()` for a
window material; the glass theme stays painted in the page (Build D).

## Tester feedback for 0.2 (Jason, Windows re-run, 2026-09-29)

Raised while clicking through 0.1. Each needs a SPEC before any build; the
glass theme (Build D, P30) is the natural place to fold in 2 and 3.

1. **Firm-wide client list.** There is no single screen listing every
   household across the firm, only one clients folder at a time. The API's
   `list` command already returns every household under the root; no screen
   shows it.
2. **Too many buttons.** The main screen feels crowded. Which buttons go (or
   move into a menu) is Jason's call - ask him in the SPEC session.
3. **No tooltips.** Hovering a button or icon shows no description. Every
   control should say what it does, with the words coming from the API's
   vocabulary like the rest of the page.
4. **Status inside the app, as the landing page.** The Status page opens
   outside the app (a file in the browser). Jason wants it shown inside the
   app, and as the page the app opens on.
5. **Terms wording.** The terms screen does not clearly say that it is an
   agreement. Wording is Jason's to approve (P20 was his text).

## Environment notes for cloud sessions

`pip install -r requirements.lock` fails in the cloud container (a wheel will
not build) and the system `cryptography` breaks `pypdf`. Use a fresh virtual
environment and install only what the affected tests need:
`pytest==9.1.1 ruff==0.14.3 pypdf==6.19.0 openpyxl==3.1.5`, plus
`pdfplumber==0.11.10 pdfminer.six==20260107 pillow==12.3.0 pypdfium2==5.11.0
charset-normalizer==3.5.1 cryptography==50.0.1 cffi==2.1.1 pycparser==3.0`
(`test_api` and `test_build` fail without them).
