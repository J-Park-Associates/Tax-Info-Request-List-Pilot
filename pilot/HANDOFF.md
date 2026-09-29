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
- **Old pull requests:** #9 (Mica) and #10 (glass) are superseded and can be
  closed; #5 is the coordination board and is never merged.
- **Local gate at the merge:** ruff, `repo_map.py check`, `test_pilot`, `test_tour`,
  `test_pilot_installer`, `test_layout`, `test_layers`, `test_single_source`,
  `test_repo_map` pass under Python 3.11. Not run: Python 3.13, and CI (GitHub
  started none for the pull request). `test_build` has one failure that needs the
  OCR reader, which the cloud cannot install; it fails the same on the original.

## Waiting on Jason

The Windows check of 0.2, then tag and send. Easiest: the test kit in
`pilot/wintest/` - paste `pilot/wintest/PROMPT.md` into Claude Code on a Windows
test PC (P28). By hand: [`RELEASE.md`](RELEASE.md), which now includes the
contrast-theme check (Settings, Accessibility, Contrast themes, then open the
app). The tag is `pilot-0.2`; the tag and sending stay Jason's.

## Next

Nothing is built without a SPEC. The next job is a SPEC session (opus, high
effort) for the tester feedback below. Two things a SPEC must respect:
`app.js`, `preload.js` and `tracker/` change only where the SPEC names the lines,
and every new control takes its words from the API's vocabulary.

**Planned (2026-09-29, branch `claude/stoic-curie-1azsk7`):** Jason approved
[`PLAN-ui.md`](PLAN-ui.md), a simpler screen that answers feedback 1-5 below:
a sidebar tree of clients, tabs for one return, three top-bar buttons and a
More menu, a custom tooltip, a start-up safety badge, and every sentence in
plain English. His answers are in its Context table. The SPEC session reads
that file and this one; it writes `pilot/SPEC-ui.md`, decision P51 (build in
the pilot now, port to the main tracker later; supersedes P10 for this work)
and the other P-rows the plan names, then shows Jason a mock-up with made-up
names and the wording table before any build.

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
