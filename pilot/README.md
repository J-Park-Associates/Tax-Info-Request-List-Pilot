# Pilot edition (first edition)

This branch, `pilot/first-edition`, holds a working-but-in-progress copy of the
Tax Document Tracker for a first batch of test firms. Testers install it on a
Windows PC and run it on their own clients' files: the client's drop folder,
the sorting engine, the organized working copies in `Prepared/`, the Needs
Review queue, the status page and the drafted (never sent) reminder emails. A
guided tour inside the app walks through each step and states plainly what
the system does well and where it is still limited.

It is a separate line of work. It never blocks, changes or lands on `main`
unless Jason decides it should.

## Rules for this branch

1. **Additive only.** Pilot code lives in this `pilot/` folder and in new
   renderer files (`app/renderer/tour.js`, `tour.css`, `pilot-terms.js`).
   Existing files get only small hook lines (`index.html`, `app.js`,
   `main.js`). Nothing under `tracker/` changes here: an engine fix the pilot
   needs lands on `main` through the normal lane and reaches the pilot at the
   next merge.
2. **Pilot decisions are logged in [`DECISIONS.md`](DECISIONS.md)** as P1, P2,
   and so on - never in `docs/ROADMAP.md`, so the two logs never compete for
   decision numbers.
3. **`main` flows in, never out.** Before each pilot build, merge `main` into
   this branch with a merge commit (never a rebase), then regenerate the map
   with `python tools/repo_map.py update`. The generated map files are never
   hand-resolved.
4. **No GitHub Actions minutes.** A push to this branch runs nothing on CI.
   The gate runs locally, as `CLAUDE.md` sets out. Pilot releases are tagged
   `pilot-<version>` and never `v*`, which would start the Windows build on
   Actions.
5. **The standing rules hold unchanged.** No generative AI reads a client
   document, originals are never altered, nothing is guessed, nothing is ever
   sent.

## Working folder

Pilot work happens in its own worktree - a second working folder of the same
repository with this branch checked out - next to the main checkout, so pilot
work and main work never share a folder:

```
git fetch origin
git worktree add ../Tax-Tracker-Pilot pilot/first-edition
```

## Where things are

- [`HANDOFF.md`](HANDOFF.md) - what is done, what is next, what to read.
- [`DECISIONS.md`](DECISIONS.md) - the pilot's decision log.
- `SPEC.md` - the pilot SPEC (written by the next job).
