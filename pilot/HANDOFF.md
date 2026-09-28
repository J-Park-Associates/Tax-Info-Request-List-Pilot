# Pilot handoff

## Done

- **Job 0 (2026-09-28):** pilot started from the original's `main` at `a2d6af4`
  (PR #139, decision 209); `README.md`, `DECISIONS.md`.
- **Job 1 (2026-09-28):** [`SPEC.md`](SPEC.md) written; decisions P8-P16 added.
- **Move (2026-09-28, P17-P19):** the pilot now lives in its own repository,
  `J-Park-Associates/Tax-Info-Request-List-Pilot`, whose `main` is the pilot.
  SPEC gained section 3a (the pilot's own names on the PC and the two-folder
  deny list). The renames are **not made yet**: Build A makes them first.
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
  - Not caused by Build A, failing in the cloud only: three `test_build.py` /
    `test_api.py` tests that need Tesseract (the scanned-text reader) are not
    installable here; `test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else`
    fails identically on the untouched code.

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
`pytest==9.1.1 ruff==0.14.3 pypdf==6.19.0 openpyxl==3.1.5`, plus
`pdfplumber==0.11.10 pdfminer.six==20260107 pillow==12.3.0 pypdfium2==5.11.0
charset-normalizer==3.5.1 cryptography==50.0.1 cffi==2.1.1 pycparser==3.0`
(`test_api` and `test_build` fail without them).
