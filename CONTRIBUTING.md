# Contributing

This repository is the public pilot edition of a tax-document tracking app
for CPA firms, built and owned by J Park & Associates. It is public so that
the firms testing it can read what it does to their clients' files. Changes
are welcome under the rules below; the owner decides what lands. The
[README](README.md) says what the app is, [docs/architecture.md](docs/architecture.md)
how its pieces fit, and [LICENSE](LICENSE) what the code is under.

## Before anything else: the rules that make the app trustworthy

The four standing rules in the README (worded once in `tracker/__init__.py`,
and the suite holds every copy to that wording) are not style. Every change
is judged against them:

- No generative AI ever reads a client financial document; routing and
  status decisions are deterministic rules.
- Originals are never altered.
- Nothing is guessed; the unclear goes to a person.
- Nothing is ever sent; the app drafts and stops.

Two consequences for anyone working here:

- **Client data never enters the repository**, in any form: no client name,
  no share link, no folder path under a clients root, no document, no
  screenshot of one - not in code, a test, a commit message, an issue, a
  pull request or a decision row. Tests, probes and prompts use documents
  drawn by the suite itself (`tests/samples.py`, `pilot/wintest/make_samples.py`).
  `.gitignore` keeps every runtime file the app writes out of a checkout,
  and `.claude/settings.json` carries a deny list that keeps an agent's file
  tools away from the data folder, the clients root and every record file.
  Do not loosen either.
- **Never trigger `@claude` inside a GitHub issue or pull request.** That
  spends the GitHub Actions budget; start the work from a local session.

## Local development setup

You need Git, Python at the floor `requires-python` in `pyproject.toml`
declares, and Node.js LTS. The internet is needed for the install and for
nothing else; the app starts offline.

The two batch files on Windows, and the two `.command` files on a Mac, do
all of this for a person who double-clicks them (`Setup.bat` / `setup.command`,
then `Start App.bat` / `start.command`). By hand, in a clone:

```bash
python -m venv --clear .venv
```

Then, with that environment's Python, the two hash-checked installs, in this
order (decision 169: the reader's own package is installed without its
dependencies, because its metadata asks for the desktop build of OpenCV and
the app uses the headless one):

```bash
.venv/bin/python -m pip install --require-hashes -r requirements.lock
```

```bash
.venv/bin/python -m pip install --require-hashes --no-deps -r requirements-nodeps.lock
```

On Windows the interpreter is `.venv\Scripts\python.exe`. Then the Electron
shell, from its lock:

```bash
cd app && npm ci --no-audit --no-fund
```

Every install reads a lock file and checks every package's SHA-256
(decision 191). To move a pin, change it in the `requirements*.txt` file and
in its `.lock`, run `python tools/lockfiles.py hash` (it needs the internet)
to fill the hashes, and run the suite; `python tools/lockfiles.py check`
proves the locks agree with the pins, and the suite runs it.

For the gate (below) keep a second environment on the floor interpreter
beside the office's. The convention on the firm's Macs is `.venv` on the
interpreter `[tool.office]` in `pyproject.toml` names and `.venv311` on the
floor; both are gitignored.

## How a change is made

- **Nothing is built without a written SPEC.** A change starts as a
  `pilot/SPEC-<topic>.md` that says what changes, what does not, and how
  it is proved. The review is done by someone, or some session, that did not
  build the change, against the SPEC, as numbered findings.
- **Decisions are logged.** The pilot's own decisions are rows P1, P2, ...
  in `pilot/DECISIONS.md`, with the owner's words. `docs/ROADMAP.md` is the
  original product's log, merged in; before changing behaviour that looks
  odd, search both for the topic, because the odd choice is usually
  load-bearing.
- **The map travels with the code.** `docs/repo-map.md` is the repository
  knowledge graph. Behaviour changed: edit `docs/repo-map.curated.json`,
  then run `python tools/repo_map.py update` in the same commit. Never edit
  `docs/repo-map.json` or `docs/repo-map.md` by hand; both are generated.
  New tracked files are nodes, so `git add` them before `update`.
- **The documents are part of the change.** The README, `docs/runbook.md`
  (the operator's page), `docs/workflow.md` and `docs/storage.md` describe
  behaviour the suite pins against the code; change the behaviour and the
  document changes in the same commit.
- **Routing changes are measured.** Before touching a catalog keyword, a
  typed case or the matcher, read `docs/tools.md`; rebuild the vocabulary
  report in the same commit (`python tools/vocab_report.py build`), and
  never lower the recorded backtest baseline.

Conventions worth matching:

- Python at the floor, `pathlib.Path` throughout, the standard library
  preferred over a dependency.
- One component per module, with its own `tests/test_<module>.py`. A module
  keeps a command line under `if __name__ == "__main__":` only when a
  script, a document or a test runs it.
- Module docstrings carry the reasoning: the trade-off, the rejected
  alternative, the rule being upheld.
- Fail loudly with context. A silent skip in a scheduled job surfaces at a
  filing deadline.
- Tests are named as the claim they make, `test_overrides_are_never_asked_for`,
  never `test_case_3`.
- Import directions hold. `tests/test_layers.py` pins every module's layer
  and that no load-time import points to a higher one; a module that moves
  layers moves in that table, in the same commit.
- Any one-time step that must run after installing or upgrading is built
  into installation (`tracker/after_install.py`), never into a line a person
  has to remember.

## Running the tests

The whole suite, in parallel across your cores (pytest-xdist is in the lock):

```bash
python -m pytest -q -n auto
```

A quick local run may add `-m "not corpus"` to skip the walk over the
blank-IRS corpus; a gate never adds it. The suite never reads the checkout's
settings file, store or scratch folder: every test gets its own, and a
tripwire fails the whole run if any test, or any process a test starts,
reaches a real one (decision 185). Do not point a test at a real folder.

**The gate every change runs before it is pushed**, on this machine, never
on GitHub Actions (the CI budget rule below):

1. Delete dead code in the changed files first: unused imports and locals,
   commented-out code, a module-level name nothing uses.
2. Run the affected tests only, each test file as its own process, under
   both interpreters (the floor and the office's): the changed test files,
   each changed module's own test file, the own test file of every module
   that imports a changed one, and always `test_layers`, `test_single_source`
   and `test_repo_map` (plus `test_tripwire` and `test_errors` when tests or
   error wording change). The whole suite runs only when a change reaches
   the sorting engine, or when the owner asks.
3. Lint, and the two freshness checks:

```bash
python -m ruff check .
```

```bash
python tools/repo_map.py check
```

```bash
python tools/vocab_report.py check
```

After review fixes, only the tests the fix touched run again.

Ruff is configured in `pyproject.toml`: pyflakes for dead code, the
pycodestyle errors, bugbear, pyupgrade at the floor and import order
(first-party packages are `tracker`, `tests` and `tools`); line length is a
courtesy, not a rule, because a wrapped sentence in a docstring reads worse
than a long one. `docs/` and the build output are excluded.

On the office's Windows machine `pilot\wintest\run_checks.ps1 -Tests <file>,<file>`
runs the named test files in parallel beside the installer build, and
`pilot/mactest/run_checks.sh` is the Mac's check; both are the hands-on checks
a machine passes before it is trusted with a season.

## Branches

- `main` is the only long-lived branch, and every commit on it is a landing.
  Never force-push it, never rebase or squash onto it.
- Work happens on a short branch named for the work. The convention here is
  `claude/<topic>` for a lane of work (`claude/ocr-prepare`,
  `claude/security-review-fixes`); a stacked lane builds on its own stack.
  `orchestrator/board` is a coordination branch that is never merged.
- Lanes land one at a time, in a queue. A lane does not rebase onto `main`
  early; at its turn GitHub does the rebase (the pull request's
  *Update branch*, rebase option), and a lane rebases locally only when
  GitHub reports a conflict it cannot apply.
- Dependabot's branches are pull requests like any other: the reviewer sets
  one to draft and marks it ready so the required run happens.

## Commits

- The subject is one sentence in the software's own words - the household,
  the inbox, the return, the request list, the record, Needs Review, the
  pass - saying what changed for a person, with the decision in parentheses:
  `Pilot: a scan or photo is prepared before the reader reads it (P285)`.
  Pilot-edition work is prefixed `Pilot:`; a pilot decision's own build may
  be prefixed with its number, `P286: ...`.
- The body says why, names the SPEC section or the review finding it
  answers, and never a client, a link or a document's contents.
- Batch commits before pushing. A push is not a save.
- Every landing on `main` is a merge commit: it records the landing as its
  own step, and the decision-history job reads the pull request number from
  it.

## Pull requests

GitHub Actions minutes are a budget, and Windows runners bill at twice
Linux (decisions 207 and 211). So:

1. Open every pull request **as a draft**. A draft runs nothing.
2. Run the gate above locally. Push the batch.
3. When the stack is final, **mark it ready once**. That one event runs
   `ci.yml` (the Linux gate: tests, ruff, the map and the vocabulary
   checks, and that the Electron shell parses). A push to a ready pull
   request runs nothing and cannot merge until the pull request is set back
   to draft and marked ready again.
4. Add the `windows` label only for work touching the held engagement lock,
   the atomic replace, path handling or a Windows-only test; it runs the
   Windows matrix once.
5. Land with a merge commit, never a squash or a rebase merge, and delete
   the branch:

```bash
gh pr merge <number> --merge --delete-branch
```

The pull request's description says what changed, in the software's words,
and what was run. A stacked pull request stays a draft until it is
retargeted onto `main`. CI on a push to `main` is the net under what merged,
not the test runner.

Releases follow `pilot/RELEASE.md`: `Build App.bat` and `pilot/Build Pilot Installer.bat`
make the Windows installer from a clean commit, `build-mac.sh` the Mac disk
image, each refusing a tree with uncommitted changes, and `build.yml` builds
and smoke-checks the Windows package from a protected tag.

## Reporting a problem

Open an issue that describes what the app did and what you expected, with
the reason code or the sentence the app showed, in the software's words.
Never attach a client's document or name one. If a problem could expose a
client's files, do not file it publicly: report it privately to the
maintainers through the J-Park-Associates organisation on GitHub.
