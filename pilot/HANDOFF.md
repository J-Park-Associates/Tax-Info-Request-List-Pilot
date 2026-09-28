# Pilot handoff

## Done

- **Job 0 (2026-09-28):** pilot started from the original's `main` at `a2d6af4`
  (PR #139, decision 209); `README.md`, `DECISIONS.md`.
- **Job 1 (2026-09-28):** [`SPEC.md`](SPEC.md) written; decisions P8-P16 added.
- **Move (2026-09-28, P17-P19):** the pilot now lives in its own repository,
  `J-Park-Associates/Tax-Info-Request-List-Pilot`, whose `main` is the pilot.
  SPEC gained section 3a (the pilot's own names on the PC and the two-folder
  deny list). The renames are **not made yet**: Build A makes them first.

## Waiting on Jason before any build starts

1. **Approve or mark up the tour wording** in `SPEC.md` section 8. (Section 7,
   the terms, was approved on 2026-09-28 - P20.) Builders copy both exactly.
2. **Turn off GitHub Actions for this repository** (Settings -> Actions ->
   General -> Disable actions). The workflow files came with the copy, and the
   weekly audit would otherwise run here.
3. **Start the job in the original repository for the schedule setting - on/off and run time** (P14, P16,
   `SPEC.md` section 12 has the brief). It runs in its own session in
   `Tax-Info-Request-List` under the normal lane (SPEC, build, review, decision number). Pilot 0.1 is
   not released until the pilot has merged it.

## Next: Jobs 2A and 2B in parallel (sonnet), after approval

Both read only `pilot/README.md`, `pilot/DECISIONS.md` and `pilot/SPEC.md`
(no transcript, no whole `docs/repo-map.md`; use
`python tools/repo_map.py show <file>`).

- **2A - names and installer:** `SPEC.md` section 3a first (its own commit,
  with the name-sensitive tests), then sections 10, 13, 11 (installer tests)
  and 14. Branch `build-a` from `main`.
- **2B - app:** `SPEC.md` sections 2-9, 11 (pilot and tour tests).
  Branch `build-b` from `main`.
- Each: run the gate (section 15), merge back into `main` with a merge commit,
  run `python tools/repo_map.py update`, and update this file.
- Why parallel: the two touch disjoint files and share only the
  `pilot-content.js` shape the SPEC fixes (section 4).

## Then

- **Job 3:** opus review, high effort, in a session that built nothing:
  numbered findings against `SPEC.md`; rebuild/review loop.
- **Job 4 (Jason, office PC, on a copy of client folders - P15, P18):** run
  `pilot\Build Pilot Installer.bat`, install, accept terms, run the tour on a
  copy of client folders, uninstall, confirm the clients folder, data folder
  and `settings.json` remain and the scheduled task is gone.
- **Job 5:** after the original's schedule setting is merged in from `upstream` and the wrap-up
  sentence swapped (SPEC section 8), tag `pilot-0.1` (never `v*`) and send the
  installer and `Tester Guide.md`.

## Environment notes for cloud sessions

`pip install -r requirements.lock` fails in the cloud container (a wheel will
not build) and the system `cryptography` breaks `pypdf`. Use a fresh virtual
environment and install only what the affected tests need:
`pytest==9.1.1 ruff==0.14.3 pypdf==6.19.0 openpyxl==3.1.5`.
