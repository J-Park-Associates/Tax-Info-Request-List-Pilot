# Pilot handoff

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
- **Next: Build D** (sonnet), then **Review 3** (opus, high effort, a session
  that did not build), then rebuild/review until no findings. The two prompts
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

## Build D (2026-09-29, branch `build-d`, draft PR "Build D: glass theme" to `main`)

SPEC-glass section 11 steps 1-9 are built, one commit per step, every message
with `[skip ci]`. **Waiting on: Review 3 (opus, a session that did not build),
then Jason's section 12 checklist on his Windows PC.** The Windows check has not
been run; the cloud cannot draw the packaged window.

**Deviations from the SPEC, and why** (the reviewer should look at each)
1. Lens map is inlined in `index.html` as a `data:` URI (SPEC section 3's
   allowed fallback): a file `feImage` does not load inside a backdrop filter
   in Chromium 141 (rim identical on and off); the inline bytes do (rim differs
   in 1200 of 2500 pixels, centre in 0). `test_glass` checks the inline bytes
   equal `glass-lens.png`.
2. Dialog and terms dim fade through `background-color` on the overlay, not
   `opacity` (SPEC 7.2): an overlay with opacity below 1 becomes a backdrop
   root, so the glass card would draw with no blur until the fade ended.
3. `display` is in no `transition` (SPEC 7.2 / 4.6 listed it with
   `allow-discrete`): it would delay closing a dialog by the transition time;
   entry motion works from `@starting-style` alone, and closing stays instant.
4. **Found by the rendered sweep:** the reminder's hold line (`.rem-hold`) is
   drawn in an engine palette colour (`#8a5a10`) that fails 4.5:1 on thin glass
   over the navy end of the backdrop (2.35:1 worst case). P33 forbids this sheet
   restyling that colour, so it now sits on a solid `--card` pill (5.9:1), and
   `.rem-hold` was added to `GLASS_TARGETS` in `tests/test_glass.py`.
5. `tools/repo_map.py` (`_owner_edges`) now counts only code types when it
   decides which file a stem names: `glass.css` and `glass.js` share a stem, so
   the map refused to say `tests/test_glass.py` owns the script and
   `test_repo_map` failed. One edge was added to the map; nothing else changed.
6. `tests/test_glass.py` treats the mask's `#000` as not a colour (the rim's
   mask is read for alpha only).
7. Known limits: a tall dialog (the editor) scrolls its lit rim with the
   content (`.modal` is the scroll container); `.rem-stages` gets the inner
   radius but nothing visible (a bare grid). The tour card's pointer light
   keeps a cached rectangle until the pointer leaves it (the card moves without
   pointer events).

**Rendered sweep** (scratch Playwright in the cloud Chromium 141, the real
`index.html` with the real Python engine on a made-up household, Smith Family;
no client file opened). For main screen, New household dialog, tour and terms,
at Glass, Glass with refraction and Solid: every text colour directly on a glass
surface is one of the eight proven token colours (0 outside), and every text on
a solid backing has at least 4.5:1 against that backing (0 below), after fix 4.
Reduced preferences (`prefers-reduced-transparency`, `prefers-reduced-motion`,
`prefers-contrast: more`, `forced-colors: active`), each at Glass and at
refraction with a dialog open: no element has a computed `backdrop-filter` other
than `none`, the header/toolbar/card/dialog backgrounds are opaque,
`document.getAnimations().length` is 0, and the picker is disabled with its
note showing.

**Speed probe** (software rendering, no graphics card; SPEC 7.3 budget):

| | Glass | Solid | Refraction (no budget) |
|---|---|---|---|
| pointer sweeping, frames/s | 58.5 / 60 (need 40) | 60 / 58.5-60 (need 55) | 37.7 / 33.8 |
| scrolling, frames/s | 69 / 66 (need 40) | 106-119 | 44.5 / 39.4 |
| dialog readable, ms | 117 / 121 (need 150) | 90-109 in five runs (one warm-up run 171) | 144 / 149 |
| button pressed (scale 0.97), ms | 16.5 / 17.5 | 7.5-12.6 | 54 / 75 |

The budget is met at Glass and Solid. At Glass the press reaches its scale in
about one frame (16.7 ms). Refraction is slower in software, as SPEC 7.3 says.
The Solid scrolling figures above 60 are the headless clock, not a faster page.

**Gate:** dead code and `ruff check .` clean; `repo_map.py update` then `check`
current; `test_glass` (24), `test_pilot` (11), `test_tour` (8), `test_layers`
(29), `test_single_source` (167) and `test_repo_map` (80) pass, each as its own
process, under Python 3.11 and 3.13. Whole suite not run (CLAUDE.md).
`git diff main` is empty for `app.js`, `main.js`, `preload.js`, `style.css` and
`tracker/`, and `index.html`'s diff is exactly the three SPEC lines.

**Screenshots and clip:** `pilot/reviews/glass-screens/`: rows 1-4 at Glass
(`-glass`), Solid (`-solid`) and emulated Transparency effects off
(`-reduced-transparency`), `5-dialog-refraction.png`, and `6-motion.webm`
(15.7 s at the refraction level: pointer across the toolbar, a scroll, a button
press, the reminder card arriving, the New household dialog arriving). The card
arrival is staged by hiding and unhiding the reminder card, since the real app
shows it only after a pass. Made-up names only; the header says "Sample".

**Left**
- Review 3 (prompt above) and any rebuild.
- Jason's section 12 checklist, on the screenshots and clip, then on Windows
  with the installed 0.2. Tune `--glass-corner` (1.2-2.0) if corners look
  circular.
- The Mica job (below) and the tester-feedback SPEC.
- The Fluent 2 skill and `fluent-ui` server are in (`.mcp.json`,
  `.claude/skills/fluent-2-design`), opt-in only.

## Build D checkpoint, earlier today (kept for the open requests it records)

Status: **steps 1-5 of SPEC-glass section 11 are done and committed; steps 6-9
are not.** Gate not run. Not ready to merge.

**Done**
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
  `test_tour.py` changes. 43 tests pass under Python 3.11 in the cloud venv.
  Not run under 3.13. The contrast test passes on the tokens as the SPEC gives
  them.

**Left**
- Step 6: the rendered sweep (every text colour on a glass surface, the four
  reduced-preference emulations, no running animation under reduced motion),
  and the speed probe against SPEC 7.3 at Glass, Solid and Full.
- Step 7: Tester Guide "Screen effects" section (8.2); `docs/repo-map.curated.json`
  roles for `glass.css`, `glass.js`, `glass-lens.png`, `make_glass_lens.py`,
  `test_glass.py`.
- Step 8: screenshots for SPEC section 12 and the motion clip (Playwright
  `recordVideo`, under 20 s), into `pilot/reviews/glass-screens/`. Jason asked
  for a video of the theme in action: this is it.
- Step 9: dead-code check, `ruff check .`, `repo_map.py update` then `check`,
  the six named test files under 3.11 and 3.13, the draft PR titled
  "Build D: glass theme", then Review 3.

**Scratch tooling (in the session's scratchpad, not committed; rebuild if the
session is gone):** a Playwright harness that opens the real
`app/renderer/index.html` over `file://` and replaces Electron's preload with a
bridge to the real `python -m tracker.api`, using a made-up root built by
`tests.samples.build_scratch_root` (Smith Family) and one `run-now` pass, so
the review card has five items. No client file was opened. Terms and tour are
skipped by setting `pilot.terms.accepted` and `pilot.tour.seen` in local storage.

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

## Next job after Build D: try Mica (Jason: "Lets try mica", 2026-09-29)

A new job, not part of Build D (SPEC-glass forbids `main.js` edits, P32). It
needs its own SPEC (opus, high effort), then a sonnet build, then an opus
review, each in a fresh session, and a Windows check by Jason: the cloud cannot
draw Mica.

Facts for the SPEC session (checked, not yet tried):
- Electron 43 (`app/package.json`) has `BrowserWindow.backgroundMaterial`
  (`mica`, `acrylic`, `tabbed`, `auto`, `none`); Windows 11 22H2+ only, since
  Electron 26. No third-party module (`vibe`, `mica-electron`) is needed.
- `app/main.js` `createWindow()` (~line 367) builds the window with
  `backgroundColor: pageBackground()`, which reads `--bg` from `style.css`.
  Mica needs that colour transparent and the window's material set, so this is
  a `main.js` edit and must be tested by `tests/test_single_source.py` and the
  main.js tests, which pin its text.
- The page must not paint an opaque background over the material. Build D's
  `glass.css` paints the gradient on `body`; under Mica the header and toolbar
  glass would sit over the real desktop material instead. The SPEC must decide
  what the body paints on Windows 11 (transparent, with the in-page gradient
  as the fallback when the material is unavailable) and how the picker's
  levels map (Solid must still work).
- Windows 10 and remote desktop: the material is absent or slow; the fallback
  is Build D's page-painted look. `prefers-reduced-transparency` still forces
  Solid.
- Decide whether it ships in 0.2 or later, and log it as P46.

Prompt for the SPEC session (opus, high effort): read `pilot/DECISIONS.md`
(P30-P45), `pilot/SPEC-glass.md`, this section, `python tools/repo_map.py show
app/main.js` and the `createWindow` lines only; write `pilot/SPEC-mica.md` with
exact lines, tests, the Windows check steps and a rollback; do not build.

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
