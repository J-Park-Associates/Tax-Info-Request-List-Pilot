# Pilot edition (first edition)

This repository, `J-Park-Associates/Tax-Info-Request-List-Pilot`, holds a
working-but-in-progress copy of the Tax Document Tracker for a first batch of
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

1. **Small, named differences from the original.** Pilot code lives in this
   `pilot/` folder and in new renderer files (`app/renderer/tour.js`,
   `pilot.js`, `pilot-content.js`, `pilot-style.css`, `pilot-ui.css`). Existing
   files change only where `SPEC.md` or `SPEC-ui.md` names the lines: the five
   added lines in `index.html` (four in `SPEC.md`, the `pilot-ui.css` link in
   `SPEC-ui.md`) and the pilot's own names on the PC (SPEC section 3a). Engine fixes are
   made in the original repository and merged in here. Keeping the differences
   small is what keeps each merge from the original clean.
2. **Pilot decisions are logged in [`DECISIONS.md`](DECISIONS.md)** as P1, P2,
   and so on, never in `docs/ROADMAP.md` (which stays the original's log, as
   merged in).
3. **Taking the original's changes, by hand, when Jason asks:**
   ```
   git remote add upstream https://github.com/J-Park-Associates/Tax-Info-Request-List.git   # once
   git fetch upstream main
   git merge upstream/main          # a merge commit, never a rebase
   python tools/repo_map.py update  # regenerate the map; never hand-resolve it
   ```
   Then run the gate (CLAUDE.md) and commit.
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
