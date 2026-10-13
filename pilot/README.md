# Pilot edition (first edition)

This repository, `J-Park-Associates/Tax-Info-Request-List-Pilot`, holds a
working-but-in-progress copy of Tax Document Console for a first batch of
test firms. Testers install it on a Windows PC and run it on their own
clients' files: the client's drop folder, the sorting engine, the organized
working copies in `Prepared/`, the Needs Review queue, the status page and the
drafted (never sent) reminder emails. A guided tour inside the app walks
through each step and states plainly what the system does well and where it
is still limited.

It is a separate repository (P17), copied with full history from
`J-Park-Associates/Tax-Info-Request-List`. Nothing here ever flows back to the
original. The original's improvements come in only when Jason asks for a merge.

## Rules for this repository

1. **This repository is the one codebase (P309).** Since 2026-10-13
   nothing is merged from the original
   `J-Park-Associates/Tax-Info-Request-List`. A fix the original gets is
   copied across by hand, as a change of this repository's own with its
   own decision row. Pilot code no longer has to be additive: P7 and P10,
   which kept the pilot's differences small so merges from the original
   stayed clean, are retired.
2. **Pilot decisions are logged in [`DECISIONS.md`](DECISIONS.md)** as P1, P2,
   and so on, never in `docs/ROADMAP.md` (which stays the original's log, as
   merged in).
3. **Nothing is taken from the original by merge** (P309, ending P17's
   hand merge). The `upstream` remote and `git merge upstream/main` are no
   longer part of the work.
4. **No GitHub Actions minutes.** The workflow files came along with the copy.
   Actions is to be turned off for this repository (Settings -> Actions ->
   General -> Disable actions), so nothing here runs on GitHub. The gate runs
   locally, as `CLAUDE.md` sets out. Pilot releases are tagged
   `pilot-<version>`.
5. **The standing rules hold unchanged.** No generative AI reads a client
   document, originals are never altered, nothing is guessed, nothing is ever
   sent.

## Where things are

- [`SPEC.md`](SPEC.md) - what the pilot builds.
- [`HANDOFF.md`](HANDOFF.md) - what is done, what is next, what to read.
- [`DECISIONS.md`](DECISIONS.md) - the pilot's decision log.
- [`RELEASE.md`](RELEASE.md) - the Windows steps to build, check, tag and send.
- [`Tester Guide.md`](<Tester Guide.md>) - what a tester is given.
- `wintest/` - the Windows test kit (P28).
- [SPEC-architecture.md](SPEC-architecture.md) - the current work: the architecture audit and the refactor in phases.
- [`SPEC-cleanup.md`](SPEC-cleanup.md) - dead code, folds and repository residue (landed, pull request #33).
