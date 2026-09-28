# Pilot handoff

## Done

- **Job 0 (2026-09-28):** branch `pilot/first-edition` cut from `main` at
  `a2d6af4`, in worktree `../Tax-Tracker-Pilot`; `README.md`, `DECISIONS.md`.
- **Job 1 (2026-09-28):** [`SPEC.md`](SPEC.md) written; decisions P8-P15 added.

## Waiting on Jason before any build starts

1. **Approve or mark up the wording** in `SPEC.md` section 7 (terms) and
   section 8 (tour). Builders copy it exactly as approved.
2. **Start the `main`-lane job for the schedule on/off setting** (P14,
   `SPEC.md` section 12 has the brief). It runs in its own session on `main`
   under the normal lane (SPEC, build, review, decision number). Pilot 0.1 is
   not released until the pilot has merged it.

## Next: Jobs 2A and 2B in parallel (sonnet), after approval

Both read only `pilot/README.md`, `pilot/DECISIONS.md` and `pilot/SPEC.md`
(no transcript, no whole `docs/repo-map.md`; use
`python tools/repo_map.py show <file>`).

- **2A - installer:** `SPEC.md` sections 10, 13, 11 (installer tests), 14.
  Worktree branch `pilot/build-a` from `pilot/first-edition`.
- **2B - app:** `SPEC.md` sections 2-9, 11 (pilot and tour tests).
  Worktree branch `pilot/build-b` from `pilot/first-edition`.
- Each: run the gate (section 15), merge back into `pilot/first-edition` with a
  merge commit, run `python tools/repo_map.py update`, update this file.
- Why parallel: the two touch disjoint files and share only the
  `pilot-content.js` shape the SPEC fixes (section 4).

## Then

- **Job 3:** opus review, high effort, in a session that built nothing:
  numbered findings against `SPEC.md`; rebuild/review loop.
- **Job 4 (Jason, office PC, separate Windows account - P15):** run
  `pilot\Build Pilot Installer.bat`, install, accept terms, run the tour on a
  copy of client folders, uninstall, confirm the clients folder, data folder
  and `settings.json` remain and the scheduled task is gone.
- **Job 5:** after the `main` schedule switch is merged in and the wrap-up
  sentence swapped (SPEC section 8), tag `pilot-0.1` (never `v*`) and send the
  installer and `Tester Guide.md`.

## Environment notes for cloud sessions

`pip install -r requirements.lock` fails in the cloud container (a wheel will
not build) and the system `cryptography` breaks `pypdf`. Use a fresh virtual
environment and install only what the affected tests need:
`pytest==9.1.1 ruff==0.14.3 pypdf==6.19.0 openpyxl==3.1.5`.
