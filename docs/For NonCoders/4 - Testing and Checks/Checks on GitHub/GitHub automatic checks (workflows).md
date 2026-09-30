# GitHub's automatic checks, and the rule that keeps them cheap

**Original file:** `.github/workflows/ci.yml`, `.github/workflows/gate.yml`, `.github/workflows/build.yml`, `.github/workflows/audit.yml`, `.github/dependabot.yml`  

**Kind of file:** GitHub automation settings (instructions GitHub runs on its own computers)  
**Tags:** Kind: Program file · Topic: Testing, GitHub costs  

## In one sentence
These files tell GitHub when to test the code, build the program, check for known security flaws and suggest updates, and they are written to spend as little paid time as possible.

## What it is
GitHub can run jobs on rented computers ("runners") when something happens in the repository. Each job uses paid minutes. Windows runners cost twice as much as Linux ones. Pinned actions (the ready-made steps a job uses) are tied to an exact commit so they cannot be swapped.

## What it does, step by step
1. **ci.yml, the traffic controller.** It runs on a push to `main` (Linux) and once when a person marks a pull request "ready for review". It never runs when a commit is pushed to a pull request, and a draft runs nothing. Windows runs only on a ready pull request with the `windows` label. Linux runs two Python versions: the floor (3.11, the oldest version the code must work on) and the office's (3.14). A pull request based on another branch runs nothing.
2. **gate.yml, the checks themselves,** written once and called by ci.yml. It installs the locked parts, runs the tests, the code cleanliness check (ruff), the repository-map check, the vocabulary report check, and confirms the Electron files parse. It stops after 60 minutes.
3. **build.yml, the package build.** It runs only when a tag starting with `v` is pushed. It runs `Build App.bat` on Windows, starts the frozen program to prove it answers, does a small practice pass on a made-up clients folder, checks the package holds no data, and uploads a zip with its SHA-256 fingerprint. There is no manual start.
4. **audit.yml, the weekly security check.** It runs Mondays and by hand, on Linux, only. It runs `tools/lockfiles.py audit` (see the lock files page).
5. **dependabot.yml, update suggestions.** One grouped pull request per kind: Python weekly, the Electron shell monthly, and the Actions pins monthly. A Python pin change makes the lock check fail on purpose, so a person must move the lock and run the hash tool.

## The cost rule (from CLAUDE.md)
An audit on 2026-09-22 found 30 runs in 34.5 hours costing about 890 billed minutes, enough to use a month's quota in about 3 days. Windows was over 65% of it. Jason's rule (decision 207, 2026-09-26): checks are not run on the GitHub budget. Test locally, and merge in bulk. Decision 211 then made CI never fire per commit.
- Before pushing, every session runs the local gate: dead-code cleanup first, then only the tests the change affects (Jason, 2026-09-29), then ruff and both `check`s.
- Do not push or merge on every commit. Batch the work.
- Every landing is a merge commit. Never a rebase merge, a squash or a force-push to `main`.
- Lanes (separate streams of work) land one at a time, in a queue, when the orchestrator (the session that coordinates them) says "YOUR TURN".
- The `windows` label is the explicit ask for Windows, for work on locking, the atomic replace (saving a file so it is never left half-written), path handling, or Windows-only tests.
- Never trigger `@claude` inside a GitHub issue or pull request. That runs on GitHub. Start work from claude.ai/code.

## Why it matters to the firm
These checks are the safety net under the code. The cost rule keeps the safety net affordable, so it is never switched off.

## What must never be changed without a programmer
- **The triggers.** Adding "on every push" undoes the cost rule.
- **The `v*` tag rule** for builds and the tag protection behind it.
- **The required check names,** which the merge protection depends on.
- **The commit-pinned action versions.**

## Words to know
- **Workflow:** one automation file for GitHub.
- **Runner:** the rented computer that runs a job.
- **CI (continuous integration):** automatic testing of code changes.
- **Pull request:** a proposed change waiting to be merged. A *draft* is one not yet ready.
- **Tag:** a name pinned to one commit.
- **Dependabot:** GitHub's helper that suggests part updates.
- **Merge commit:** a landing recorded as its own step.
