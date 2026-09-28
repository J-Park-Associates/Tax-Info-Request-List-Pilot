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

The Windows steps in [`RELEASE.md`](RELEASE.md): run the gate under the
office's Python, build the installer, install and try it, uninstall, then tag
`pilot-0.1` and send it.

## Environment notes for cloud sessions

`pip install -r requirements.lock` fails in the cloud container (a wheel will
not build) and the system `cryptography` breaks `pypdf`. Use a fresh virtual
environment and install only what the affected tests need:
`pytest==9.1.1 ruff==0.14.3 pypdf==6.19.0 openpyxl==3.1.5`, plus
`pdfplumber==0.11.10 pdfminer.six==20260107 pillow==12.3.0 pypdfium2==5.11.0
charset-normalizer==3.5.1 cryptography==50.0.1 cffi==2.1.1 pycparser==3.0`
(`test_api` and `test_build` fail without them).
