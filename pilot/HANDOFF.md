# Pilot handoff

The pilot is Tax Document Console for a first batch of test firms: the
tracker, the Electron app that fronts it, and the Windows installer and check
kit in this folder. [`README.md`](README.md) says what it is and the rules for
this repository; [`SPEC.md`](SPEC.md) says what it builds.

## Where the record is

- **`main` is `213d876`** (pull request #32, the Sort & Scan speed round,
  P216-P230); this branch is cut from it.

- **Decisions live in [`DECISIONS.md`](DECISIONS.md), rows P1 to P237.** Code
  and tests cite those numbers, so a row is never renumbered or removed. Why
  a thing is the way it is: search the row, do not guess.
- **Pilot decisions never go in `docs/ROADMAP.md`**, which stays the
  original's log.
- **A SPEC is built from, not read for history.** The SPECs beside this file
  are cited by section from the code; each names the P-rows that built it.

## Current work

[`SPEC-cleanup.md`](SPEC-cleanup.md): dead code, folds, bloat and repository
residue, in seven jobs.

1. Delete the repository residue (the old handoff, rewritten as this note,
   the old `handoffs/`, `reviews/` and `review/` folders, the design skill packs, the unused brand
   exports; P231, P232).
2. The Electron side: folds, dead and overridden CSS, unreachable guards.
3. Storage: the SQLite-helper fold, dead names, the schema changelog.
4. The app face: the row-action handlers, the `api.py` refrains, the three
   upgrade carry-overs retired (P235), the after-install job (P234).
5. The sorting engine: the `find_*` fold, the OCR exception tail, the
   decision-107 tidy-up leaving the pass (P234).
6. The runner and the rest: three unused command lines dropped (P233), two
   unreachable `client_ask` branches deleted (P236).
7. Test runtime: `pytest-xdist` in the lockfile and a `corpus` marker (P237).

Behaviour does not change in any job. Each is built on Sonnet and reviewed on
Opus in a session that did not build it, and all of them land in one draft
pull request in that order (decision 211).

## How a session hands over

**In the pull request description**, not in a file. The folder
`pilot/handoffs/` is gone: what a session decided is a P-row, what it built
is its commits, and what is left is the pull request's checklist. A job's
description says its branch, its commits, what it did and skipped, the
commands it ran with their last line, and what the reviewer should look at
first.

## Open for Jason

- Whether to turn GitHub Actions back on for this repository (it is off; the
  gate runs locally, `pilot/README.md` rule 4).
- The schedule stays off at Jason's word.
- Questions built as recommended meanwhile: P196 Q1-Q5
  (`SPEC-taxpayer-words.md`), P197 Q1-Q3 (`SPEC-hide-under-construction.md`),
  P199 Q1 (`SPEC-check-notes-0.3.md`).
- Check once by hand that a tooltip does not outlive its page (hover a name,
  press Ctrl+4; P202), and that a laptop at 125-150 % display scaling opens
  within its screen (older than P203).

## Left

- F6 by hand needs the schedule on.
- `run_checks.ps1` runs whole at the next Windows check.
- The production tracker's own private copy under the Claude package, and its
  `checkpoint-left-behind` pass, belong to its own repository.

## Environment notes for cloud sessions

`pip install -r requirements.lock` fails in the cloud container (a wheel will
not build) and the system `cryptography` breaks `pypdf`. Use a fresh virtual
environment and install only what the affected tests need:
`pytest==9.1.1 ruff==0.16.9 pypdf==6.19.0 openpyxl==3.1.5`, plus
`pdfplumber==0.11.10 pdfminer.six==20260107 pillow==12.3.0 pypdfium2==5.13.0
charset-normalizer==3.5.1 cryptography==50.0.1 cffi==2.1.1 pycparser==3.0`
(`test_api` and `test_build` fail without them).
