# Tax Document Tracker — working notes for agents

Deterministic tax-document request tracking for J Park & Associates, CPA. The
client gets one folder to drop everything into; scheduled jobs sort, rename,
index and validate what arrives, and draft the chase emails a person sends.

## Start here, do not re-scan the repo

**Use the repository map, one node at a time.** [`docs/repo-map.md`](docs/repo-map.md)
is the repository knowledge graph: every module, what it is for, what it
imports, what tests cover it, which runtime artifacts it reads and writes, and
the rules that cut across the code. It carries judgment that grepping cannot
recover — why the router refuses to guess, why the request list lives in the
record and is edited only in the app, which import cycle is deliberate.

It is also very large, so do not read it whole by default. Look up the nodes
for the files the task touches with `show` (below); read the whole page only
for work that cuts across the system, such as a layer move or a
repository-wide review.

Confirm it is current before trusting it:

```
python tools/repo_map.py check      # exit 0 = current, 1 = stale (names the files or the facts)
```

`check` compares hashes, then rebuilds the derived layer and compares it fact
for fact with the committed map, then renders the page and compares that: a
hand-edited derived field, a forged edge, a stale `repo-map.md` or a new source
file you have not `git add`-ed all fail it. If `check` says stale, refresh it
rather than working from a map you know is wrong. Only re-scan the repository
directly for something the map does not cover — then consider whether that
gap belongs in the curated layer.

Useful lookups:

```
python tools/repo_map.py show tracker/runner.py    # one node, its imports, tests, artifacts
```

**Read the test edges precisely.** They make two different claims, and the
difference is the point:

- **tested by** — the test file that owns the module by name
  (`tests/test_filer.py` → `tracker/filer.py`). This is coverage.
- **exercised by** — some other test imports it, usually to borrow a fixture.
  Real and worth knowing (many test files import `manifest.py`, so its schema
  is load-bearing across the suite) but it is *not* coverage of that module.
- **no dedicated test file** — said plainly where it is true; the map names
  each one.

An "exercised by" edge is never evidence a module is tested. The owner edge is
drawn from the file names, so a test that drives its module through `runpy`
or a subprocess still counts as its coverage.

**Read the import edges precisely too.** `imports` is a load-time dependency.
**imports at call time** is an import inside a function or a `__main__` block:
it runs when called, not when the module loads, so a cycle that closes through
one is a cycle only at call time. `from tracker import ledger` draws both the
module (`tracker/ledger.py`) and the package it executes (`tracker/__init__.py`).
The one deliberate cycle, filer ↔ scanner inside `_rescan()`, is a curated
`deliberate_cycle` edge and is stated on both nodes. There is no load-time
cycle: `tracker/__init__.py` imports nothing (decision 99), and
`tests/test_layers.py` pins the layer of every module and that no load-time
import points to a higher layer - a module that moves layers moves in that
table, in the same commit, with a decision row.

## Keeping the map current

**Refresh the map in the same commit as any change to the code.** A stale map
is worse than no map, because the next agent will believe it.

```
python tools/repo_map.py update     # incremental — re-parses only what changed
```

It is genuinely incremental: every node carries a SHA-256 of its file, so
unchanged files are copied forward untouched. A one-file change costs one
parse, not a full rebuild. `build` exists for a from-scratch rebuild but is
rarely the right command. The map hashes what Git commits (LF, per
.gitattributes), so a CRLF working copy is only a warning from `check`, and
`update` refuses a half-resolved merge until the resolved files are `git add`-ed
(decision 151).

The map has two layers, and the distinction matters:

| | |
|---|---|
| **Derived** — imports, exports, CLIs, test coverage, hashes | Parsed from source by `tools/repo_map.py`. Never hand-edit; the next `update` overwrites it. |
| **Curated** — what a module is *for*, runtime artifacts, cross-language hops, the standing rules | Hand-written in `docs/repo-map.curated.json`. Survives every regeneration. |

So: **changed behaviour → edit `docs/repo-map.curated.json`, then run `update`.**
Never edit `docs/repo-map.json` or `docs/repo-map.md` — both are generated, and
both say so at the top. `tests/test_repo_map.py::test_the_committed_map_is_current`
fails if the committed map has drifted, so the suite catches a forgotten update.

## The routing tools

The vocabulary coverage report (`docs/vocab-coverage.md`, `tools/vocab_report.py`),
the season's learned keywords (`tools/learned_keywords.py`) and the backtest
against the firm's own documents (`tools/backtest.py`,
`docs/backtest-baseline.json`) are described in [`docs/tools.md`](docs/tools.md).
Read it before changing a catalog keyword, a typed case or the matcher, and
rebuild the vocabulary report in the same commit as any of those
(`python tools/vocab_report.py build`; `tests/test_vocab_report.py` fails on a
stale one). No routing change may lower the recorded backtest baseline.

## The standing rules

These are not style preferences. They are why the system is trusted with
client tax documents, and they hold across every module. They are worded
once, in `STANDING_RULES` in `tracker/__init__.py`; the app shows them and
`tests/test_single_source.py` keeps this copy, the README, the roadmap and
the knowledge map quoting them exactly:

- **No generative AI ever reads a client financial document.** Every routing
  and status decision comes from deterministic rules in the manifest.
- **Originals are never altered.** Files are moved byte for byte under their own names out of `Drop files here` into the client's folder for the year; all work happens on copies, and every move is
  recorded in the record.
- **Nothing is guessed.** A document is filed only when exactly one request
  accepts it — or, when one document names several forms as itself, when each
  of those forms is accepted by exactly one request, or, when a broker's
  consolidated statement is accepted by several requests, when exactly one of
  them accepts it for its 1099-B, which then holds the whole statement.
  Ambiguous, contested and unrecognized files go to `00 - Needs Review` for a
  person — misfiling a tax document is worse than not filing it.
- **Nothing is ever sent.** The system drafts client emails and stops. There
  is no SMTP, no mail client and no network call in the reminder or scheduling
  path.

**The layout.** A client folder is a household, with one folder per tax
year inside it and one folder per return inside that (decision 125). Two
trees sit under the clients root: `Clients`, the only one a client is ever
shared - the household's folder, its one permanent inbox `Drop files here`,
and one folder per year holding the originals a pass moved out of that
inbox - and `J Park & Associates`, which never is: the household's own
record, and under each year one folder per return, named form first
(`1040 - John & Maria Park`). Discovery is positional, reads that layout
and no other, and lists every folder that does not fit with one sentence,
left alone. There is no migration and no importer.

`docs/ROADMAP.md` holds the decision log — the record of *why* things that
look arbitrary are the way they are. Before changing behaviour that seems
odd, search it for the decision number or the topic and read those rows;
the odd choice is usually load-bearing. It is too large to read whole.

[`docs/runbook.md`](docs/runbook.md) is the same system from the operator's
side, written for a person rather than an agent: which machine runs the
schedule and why only one may, what someone does each morning and on the
draft day, what every index reason and validation note means, and how the
firm moves to another machine. Change how any of that behaves and the
runbook is part of the change.

## How work flows here

Nothing is built without a written SPEC. **Claude Opus 5.5 designs, writes the
SPEC, builds, and reviews** (set by Jason on 2026-09-25, replacing the earlier
Fable-designs / Opus-builds / Fable-reviews split; decision-log rows that
name Fable are history and stay as written). Work at the default (medium)
effort, which on Opus 5.5 matches Opus 5 at high; raise it to high for design,
SPEC writing and review, and use xhigh or max only where it has been shown to
help. The review is a separate session or agent that did not build the
change, so the work is not grading itself. Jason owns every decision; the
claude.ai Project records his decisions in the Drive thread (folder
Handoffs), and each work session ends with a CODE UPDATE there.

## Working on this repo

```
pip install --require-hashes -r requirements.lock                     # hash-checked (decision 191)
pip install --require-hashes --no-deps -r requirements-nodeps.lock    # the reader (decision 169)
python -m pytest -q                 # the whole suite, all green
python tools/repo_map.py check      # map matches the tree
python -m ruff check .              # no dead code, no unused imports (CI runs this too)
```

Conventions worth matching:

- Python at the floor `pyproject.toml` declares, `pathlib.Path` throughout, standard library preferred.
- One component per module, each with its own CLI under
  `if __name__ == "__main__":` and its own `tests/test_<module>.py`.
- Module docstrings carry the *reasoning*, not just the description — the
  trade-off, the rejected alternative, the rule being upheld. Match that.
- Fail loudly with context. A silent skip in a scheduled job surfaces at a
  filing deadline.
- Tests are named as the claim they make
  (`test_overrides_are_never_asked_for`), not `test_case_3`.
- Import directions hold, and `tests/test_layers.py` says which: no load-time
  import points to a higher layer; `ledger` and `locking` import nothing of
  the package but each other, and `checkpoint` imports nothing of it at all
  (its `__main__` alone reaches `page`); `store` imports `ledger`, `locking`,
  `records` and `checkpoint` and nothing else; `manifest` imports `records` and nothing else
  at load time, and reaches `store`, `ledger` and `locking` at call time
  (decision 104 gave it the request list's writes); `runner` never imports
  `scheduling` or `api`;
  the package's `__init__` imports nothing. An import inside a function or a `__main__`
  block is a call-time import and may point anywhere.

Client data never enters the repo: `runs.log` and the
drafts are gitignored because they carry real client names and share links.

## Standing rule: GitHub Actions cost discipline

Windows CI runners bill at 2x Linux, and a burst of pushes/PRs re-runs the full
`gate.yml` matrix each time. An audit on 2026-09-22 found 30 CI runs in 34.5
hours (2026-09-21) costing ~890 GitHub-billed minute-equivalents — enough to
blow through a typical monthly Actions quota in about 3 days — with Windows
jobs alone accounting for more than 65% of that despite already being gated.

**Standing rule since 2026-09-26 (decision 207, Jason: "CI checks should not
be done on the github budget. test here and merge in bulk. make this the
standing rule"):**

- **Every session runs the whole suite before it pushes** (a tracker-lane
  restack runs the narrower set below). Run
  `python -m pytest -q`, `python -m ruff check .`, and both `check`s. A
  cloud session runs them on its own machine, which costs no GitHub minutes.
  The tracker lane runs them on the office PC: the owning tests of every
  file a restack touched, plus ruff and both checks.
- **CI never fires per commit** (decision 211, revising 207). It runs on a
  push to `main` (Linux, the net under what merged) and once when a person
  marks a pull request ready (the run main's protection needs before a
  merge). A push to a ready pull request runs nothing; to check it again,
  set it back to draft and mark it ready. A **draft** pull request runs
  nothing, and no other branch ever runs. The tracker lane opens every pull
  request as a draft and marks it ready once, when the stack is final.
- **Land in bulk.** One pull request may carry several reviewed decisions in
  landing order, each still its own commits. A stacked pull request stays a
  draft until it is retargeted onto `main`, then is marked ready: a pull
  request based on another branch runs nothing, and retargeting starts no
  run.
- **Rebase merging is the default when several agents work on the same
  head** (Jason, 2026-09-26): parallel lanes branched from one `main` tip land
  by GitHub's rebase merge, so history stays one line and the next lane
  rebases onto a straight tip. A single chain from one agent may still merge
  with a merge commit. Never squash, and never force-push `main`.
- **Lanes land one at a time, in a queue: the default workflow** (Jason,
  2026-09-26). Only the lane whose turn it is lands, on the orchestrator's
  "YOUR TURN" message; until then a lane builds only on its own stack or
  waits, and never rebases onto `main` early. **GitHub does the rebase:** at
  a lane's turn the orchestrator rebases its pull request onto `main` on
  GitHub, then lands it by rebase merge. A lane rebases locally only when
  GitHub reports a conflict it cannot apply.
- **The `windows` label is the explicit ask for Windows,** and only for
  work touching the held engagement lock, the atomic replace, path handling,
  or a Windows-only test. Put on a draft, it rides the one run when the pull
  request is marked ready; added to a ready pull request, it runs Windows
  once. Windows never runs on a push to `main`.
- **Never trigger `@claude` inside a GitHub issue or pull request.** That
  runs on GitHub Actions; start the work from claude.ai/code instead.
- **Batch commits before pushing** rather than pushing after every small
  fixup. `concurrency: cancel-in-progress` only saves runs *superseded*
  before they finish; a run that completes is billed regardless.

### Tests run locally, not on CI (Jason, 2026-09-26)

The cost discipline above is now firm policy, and it is global — set in the
global `~/.claude/CLAUDE.md`, in the project-folder `CLAUDE.md`, and here — so
it binds every session and every agent, not only work in this repo.

- **Subagents and builder agents run the suite on this machine, never on
  GitHub Actions.** The local gate — `python -m pytest -q`,
  `python tools/repo_map.py check`, `python -m ruff check .` and the
  vocab/backtest checks — is run in the worktree before any push. CI is a rare
  safety net, not the test runner; an agent never pushes a branch to "let CI
  test it."
- **Do not push or merge on every commit.** Batch the work and land to `main`
  occasionally, in larger, less frequent merges. Every push to `main` and every
  run on a pull request spends Actions minutes, and the quota is being hit.
- **CI must not fire per commit.** `ci.yml` triggers only where a person
  explicitly needs the safety net — a push to `main`, a pull request marked
  ready, and the `windows` label — and never on `pull_request: synchronize`,
  so pushing to a pull request branch does not re-run the suite (decision
  211). Release tags are built and smoke-checked by `build.yml`.

Set by Jason on 2026-09-22; revised to decision 207, then 211, on 2026-09-26.
