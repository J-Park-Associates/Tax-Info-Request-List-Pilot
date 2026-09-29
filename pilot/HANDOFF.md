# Pilot handoff

## Build E, the structure pass (2026-09-29, built, reviewed E1-E3 with no findings left; pull request #13, branch `claude/keen-keller-vx7xxj`)

Built exactly [`SPEC-ui.md`](SPEC-ui.md) (P51-P55): one new file,
`app/renderer/pilot-ui.css` (tokens, type ramp, one button shape in four
importances and two sizes, command bar, surfaces, inputs, dialogs, a
`forced-colors` block last), loaded between `style.css` and `pilot-style.css`.
`style.css`, `app.js`, `main.js`, `preload.js` and `tracker/` are untouched.
Other edits: one link line in `index.html`, `next.classList.add("btn-primary")`
in `tour.js`, `pilot-style.css` now written in the tokens (no literal colour,
size or step left), a `pilot-ui.css` node and `loads` edge in the curated map,
`tests/test_pilot_ui.py` (9 tests at build, 10 after Rebuild E1). The SPEC author added P55 mid-build
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
- `.pilot-terms-section h3` (the terms card's six section headings) is body
  size, 14/20 at 600, not the dialog title size SPEC 4 gives the terms card's
  `h2`/`h3`: six 20px headings in one card would be loud. The card's own title
  (`h2`) is title size.
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

**Rebuild E1** (fixes to [`reviews/review-e1.md`](reviews/review-e1.md), six
findings, nothing else; `style.css`, `app.js`, `main.js`, `preload.js` and
`tracker/` still untouched).

1. *Blocking, a hidden link showed again.* `.wiz-back` set `display` in
   `pilot-ui.css`, which loads after `style.css` and so out-ranked `.hidden`;
   `#wi-household` ("Change household details") showed in Add a return.
   `display` now sits only under `:not(.hidden)` for `.rem-quiet`, `.wiz-back`,
   `.household-return` and `.chosen-badge` (the alignment and gap stay on the
   plain selector). A sweep of both stylesheets found no other `display` on an
   element the page can hide; `pilot-style.css`'s are the pilot's own overlays
   and chips, built and removed by `pilot.js`/`tour.js`, which never toggle
   `.hidden`. New test `test_the_structure_pass_never_unhides_a_hidden_element`
   (fails on the old file; `.mode-toggle` is the one named exemption). Reproduced
   and cleared with the reviewer's Add a return script: `display=flex` before,
   `display=none` after.
2. *Should-fix, Open the draft file looked enabled.* `.rem-quiet` and
   `.wiz-back` now have the drawn disabled look of SPEC 5.2, subtle variant:
   transparent fill, `--text-disabled` text, default cursor, and `:hover` and
   `:active` change nothing; the forced-colors block gives them `GrayText`.
3. *Should-fix, "contrast themes last" did not check last.* The test now parses
   the comment-stripped file by balanced braces and asserts the last top-level
   rule is the one forced-colors block, nothing follows it, and its colours
   are system colours (checked on stripped text). A rule appended after the
   block fails it (mutation-checked in a scratch copy).
4. *Nit, three tests narrower than their names.* The colour test rejects any
   colour that is not a `var()`, `transparent`, `currentColor`, `inherit` or a
   system colour (named colours, `hsl()`, `hwb()`, `lab()`, ...); the type-ramp
   test rejects the `font:` shorthand; the grid test covers the logical
   `padding`/`margin`/`inset` properties; `!important` is checked in `:root`
   too. Each was proved by a mutation in a scratch copy.
5. *Nit, a wrapped toolbar row started 12px in.* The run gap is now a
   `margin-right` on the last button of the run before (`#btn-repair-schedule`,
   `#btn-schedule`, `#btn-status`); every row starts flush at 1100, 1366, 1440,
   1536 and 1920, and Stop still sits 4px after Sort & Scan.
6. *Nit, docs.* README rule 1 and `SPEC.md` (Build B's list) now count the
   fifth `index.html` line and name `pilot-ui.css`; the terms card's
   body-size headings are in the deviations above.

Re-run after the fixes: the sweep is 0 findings in 11 scenarios; only
`after-main-1366x860.png` and `after-main-1100x760.png` changed (the disabled
Open the draft file). `test_pilot_ui` is now 10 tests. The Add a return flow
is not in the harness's shoot scenarios; it was run by the reviewer's script.

**Review E2** ([`reviews/review-e2.md`](reviews/review-e2.md)): all six E1
findings fixed; three new nits, fixed by the SPEC author (Opus): the stale
`after-review-cards.png` is re-rendered (Open the draft file drawn disabled);
the run-gap comment in `pilot-ui.css` now says 16px and names the one accepted
limit - a first toolbar row that ends on Repair the schedule or Schedule stops
12px short of the right edge (at 1440, 1536 and 1920 in the fallback font),
because CSS cannot make both edges of a wrapping row flush.

**Review E3** ([`reviews/review-e3.md`](reviews/review-e3.md)): the three E2 nits
fixed; no new findings. The build/review loop is closed.

**Open for Jason.** SPEC 5.7 (which of two primaries leads a review row); the
setup screen's empty picker is a 260px empty box; the tour's primary (Next)
sits between Back and Close. **Left.** Jason's look
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

## Status (2026-09-29): what `main` is

`main` (merge `a0c256d`, pull request #11) is the pilot as it will ship, version
**0.2** (the badge and the installer name both read `pilot-content.js`).

- **Built and reviewed:** Builds A, B and C (renames and installer, badge, terms
  and tour, schedule setting), with `pilot/reviews/review-1.md` and `review-2.md`;
  then the restart and one-after-install-run fixes (P46, P47).
- **Tried and removed:** the glass theme, its refraction level and Mica (P30-P45
  built, then P48-P50 withdrawn). `pilot/SPEC-glass.md` is kept, marked
  withdrawn, as the record. The look is the original navy design in `style.css`.
- **Added on top (P50):** Windows contrast-theme support, a `forced-colors`
  block at the end of `style.css` and `pilot-style.css`, one test in
  `tests/test_pilot.py`. Basis: Microsoft Learn, "Contrast themes - Windows apps".
- **Build E (P51-P55, pull request #13):** the structure pass - one button
  shape, four importances, the command bar, the type ramp and the spacing grid,
  in `app/renderer/pilot-ui.css` layered over `style.css`; plus the fix for
  cards collapsing when notices fill the window (P55). See the Build E section
  above.
- **Old pull requests:** #9 (Mica) and #10 (glass) are superseded and can be
  closed; #5 is the coordination board and is never merged.
- **Local gate at the merge:** ruff, `repo_map.py check`, `test_pilot`, `test_tour`,
  `test_pilot_installer`, `test_layout`, `test_layers`, `test_single_source`,
  `test_repo_map` pass under Python 3.11. Not run: Python 3.13, and CI (GitHub
  started none for the pull request). `test_build` has one failure that needs the
  OCR reader, which the cloud cannot install; it fails the same on the original.

## Waiting on Jason

The Windows check of 0.2, then tag and send. Build E adds to it: look at the
new look on a Windows 11 PC (Segoe UI Variable's real widths - the wizard's
Change-form row, the tour's stage chips, the reminder stage labels) and
answer SPEC-ui 5.7. Easiest: the test kit in
`pilot/wintest/` - paste `pilot/wintest/PROMPT.md` into Claude Code on a Windows
test PC (P28). By hand: [`RELEASE.md`](RELEASE.md), which now includes the
contrast-theme check (Settings, Accessibility, Contrast themes, then open the
app). The tag is `pilot-0.2`; the tag and sending stay Jason's.

## Next

Nothing is built without a SPEC. The next job is a SPEC session (opus, high
effort) for the tester feedback below. Two things a SPEC must respect:
`app.js`, `preload.js` and `tracker/` change only where the SPEC names the lines,
and every new control takes its words from the API's vocabulary.

## Tester feedback for 0.2 (Jason, Windows re-run, 2026-09-29)

Raised while clicking through 0.1. Each needs a SPEC before any build; 2 and 3
belong together (fewer buttons, and a tooltip on each that stays).

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
