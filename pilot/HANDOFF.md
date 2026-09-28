# Pilot handoff

## Done

- **Job 0 (2026-09-28):** pilot started from the original's `main` at `a2d6af4`
  (PR #139, decision 209); `README.md`, `DECISIONS.md`.
- **Job 1 (2026-09-28):** [`SPEC.md`](SPEC.md) written; decisions P8-P16 added.
- **Move (2026-09-28, P17-P19):** the pilot now lives in its own repository,
  `J-Park-Associates/Tax-Info-Request-List-Pilot`, whose `main` is the pilot.
  SPEC gained section 3a (the pilot's own names on the PC and the two-folder
  deny list). The renames are **not made yet**: Build A makes them first.

## Waiting on Jason

Nothing. Terms (P20) and tour (P22) wording approved; Actions are off in this
repository; the old `pilot/first-edition` branch is deleted from the original.

## Next: builds (sonnet), each its own fresh session

Every build reads only `pilot/README.md`, `pilot/DECISIONS.md` and
`pilot/SPEC.md` (no transcript, no whole `docs/repo-map.md`; use
`python tools/repo_map.py show <file>`), runs the gate (SPEC section 15),
merges back into `main` with a merge commit, runs
`python tools/repo_map.py update`, and updates this file.

- **2A - names and installer** (parallel with 2B): SPEC section 3a first (its
  own commit, with the name-sensitive tests), then sections 10, 13, 11
  (installer tests) and 14. Branch `build-a`.
- **2B - badge, terms, tour** (parallel with 2A): SPEC sections 2-9 and 11
  (pilot and tour tests). Branch `build-b`.
- **2C - schedule setting** (after 2B has merged; both edit `index.html`):
  SPEC section 12. Branch `build-c`.
- Why this order: A and B touch disjoint files and share only the
  `pilot-content.js` shape; C changes the engine and the same page file as B.

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
