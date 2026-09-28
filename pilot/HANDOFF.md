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

## Waiting on Jason

Nothing. Terms (P20) and tour (P22) wording approved; Actions are off in this
repository; the old `pilot/first-edition` branch is deleted from the original.

## Next: run the sessions in [`PROMPTS.md`](PROMPTS.md) (P23)

1. **Prompts 1, 2, 3 in parallel** (Sonnet): Build A (names and installer),
   Build B (badge, terms, tour), Build C (schedule setting). Each pushes its
   session branch and opens a draft pull request to `main`.
2. **Prompt 4** (Opus, high effort): one review of all three pull requests,
   findings in `pilot/reviews/review-1.md`.
3. **Prompt 5** in each build session that has findings.
4. **Prompt 6** (Opus): confirm fixes, merge B -> A -> C, gate, write
   `pilot/RELEASE.md`.

## Then

- **Job 3:** opus review, high effort, in a session that built nothing:
  numbered findings against `SPEC.md`; rebuild/review loop.
- **Job 4 (Jason, office PC, on a copy of client folders - P15, P18):** run
  `pilot\Build Pilot Installer.bat`, install, accept terms, run the tour on a
  copy of client folders, uninstall, confirm the clients folder, data folder
  and `settings.json` remain and the scheduled task is gone.
- **Job 5:** once Builds A, B and C are merged, reviewed and checked on Windows, tag `pilot-0.1` (never `v*`) and send the
  installer and `Tester Guide.md`.

## Environment notes for cloud sessions

`pip install -r requirements.lock` fails in the cloud container (a wheel will
not build) and the system `cryptography` breaks `pypdf`. Use a fresh virtual
environment and install only what the affected tests need:
`pytest==9.1.1 ruff==0.14.3 pypdf==6.19.0 openpyxl==3.1.5`.
