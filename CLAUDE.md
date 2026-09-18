# Tax Document Tracker — working notes for agents

Deterministic tax-document request tracking for J Park & Associates, CPA. The
client gets one folder to drop everything into; scheduled jobs sort, rename,
index and validate what arrives, and draft the chase emails a person sends.

## Start here, do not re-scan the repo

**Read [`docs/repo-map.md`](docs/repo-map.md) first.** It is the repository
knowledge graph: every module, what it is for, what it imports, what tests
cover it, which runtime artifacts it reads and writes, and the rules that cut
across the code. Reading it costs one file instead of fifty, and it carries
judgment that grepping cannot recover — why the router refuses to guess, why
`create_template()` does not write scanner columns, which import cycle is
deliberate.

Confirm it is current before trusting it:

```
python tools/repo_map.py check      # exit 0 = current, 1 = stale (names the files)
```

If `check` says stale, refresh it rather than working from a map you know is
wrong. Only re-scan the repository directly for something the map does not
cover — then consider whether that gap belongs in the curated layer.

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

An "exercised by" edge is never evidence a module is tested.

## Keeping the map current

**Refresh the map in the same commit as any change to the code.** A stale map
is worse than no map, because the next agent will believe it.

```
python tools/repo_map.py update     # incremental — re-parses only what changed
```

It is genuinely incremental: every node carries a SHA-256 of its file, so
unchanged files are copied forward untouched. A one-file change costs one
parse, not a full rebuild. `build` exists for a from-scratch rebuild but is
rarely the right command.

The map has two layers, and the distinction matters:

| | |
|---|---|
| **Derived** — imports, exports, CLIs, test coverage, hashes | Parsed from source by `tools/repo_map.py`. Never hand-edit; the next `update` overwrites it. |
| **Curated** — what a module is *for*, runtime artifacts, cross-language hops, the standing rules | Hand-written in `docs/repo-map.curated.json`. Survives every regeneration. |

So: **changed behaviour → edit `docs/repo-map.curated.json`, then run `update`.**
Never edit `docs/repo-map.json` or `docs/repo-map.md` — both are generated, and
both say so at the top. `tests/test_repo_map.py::test_the_committed_map_is_current`
fails if the committed map has drifted, so the suite catches a forgotten update.

## The vocabulary coverage report

[`docs/vocab-coverage.md`](docs/vocab-coverage.md) is the map's counterpart
for the routing rules: which keyword in each catalog is reached by which IRS
form in `tests/irs/` or reconstructed case in `tests/test_catalog.py`, and
which keywords nothing in the suite defends. `tools/vocab_report.py`
generates it from the catalog, the matcher and the suite; it is committed
and checked by hash, like the map:

```
python tools/vocab_report.py check      # exit 0 = current, 1 = an input changed (names it)
python tools/vocab_report.py build      # rebuild after changing a keyword, a case or the matcher
python tools/vocab_report.py show 1040  # one catalog, row by row
```

Read its headline lists before changing a keyword: an unreached keyword has
no test to say when it starts misfiling. Rebuild it in the same commit as a
catalog, matcher or case change; `tests/test_vocab_report.py` fails on a
stale one. Every case in `tests/test_catalog.py` carries the decision that
introduced it, so `python -m pytest -k d67` runs decision 67's whole history
before a rule it touched is trusted.

The firm's own redacted documents are the third corpus, and they live
outside the repository: the environment variable TRACKER_REAL_CORPUS names
the folder holding them, with an expectations.csv beside them saying, per
document, which catalog and engagement year it is routed against and the
identifier it must file under — blank where it must park in
`00 - Needs Review`. `tests/test_real_corpus.py` routes every row of that
file the way the IRS forms are routed, and the coverage report reads the
same documents, when the variable is set; both skip when it is not, so a
machine without a corpus (CI, a fresh clone) is green. They are never
committed, redacted or not: client documents do not enter the repo, and a
report built with them names files the firm's clients can be read out of,
so `check` refuses one.

The catalog is not the only vocabulary in the field. When a person files a
parked document they may type a keyword, and it is written into that one
engagement's `Any Keywords` — invisible to every other engagement and to the
catalog the suite tests. `tools/learned_keywords.py` is the season's list of
them: it walks every engagement under the clients root, compares each request
row's keywords against the catalog rows carrying the same identifier and
document, and groups what is left by row with the number of engagements that
typed it. It only reads — no lock, no write-back — and it prints no client
folder name unless it is asked for one, so a keyword several engagements had
to be taught separately can be promoted into `tracker/templates.py`, where
the suite defends it. It can run each candidate over the IRS forms in
`tests/irs/` first, and marks the ones that would misfile a form the suite
already places.

## The backtest: the firm's own documents score the router

[`docs/backtest-baseline.json`](docs/backtest-baseline.json) holds one
number — how often the router files the firm's own already-sorted
documents where a person filed them — and `tools/backtest.py` measures it.
The fifty IRS forms and the typed cases are blank paperwork nobody sent;
the documents a client actually sent sit on the office file server, sorted
by hand over years, and they are the only corpus that can say whether the
routing rules work on real mail. The tool routes them against the shipped
catalogs and reports the agreement, the confusions (expected this row,
filed that one), the per-row table, the parked and no-text shares, and the
time each document took. Each document is routed through a hard link under
one neutral name (`NEUTRAL_STEM`), so the router's by-name fallback can
never read the client's name off the file: what is scored is the rules,
not the firm's file naming.

```
python tools/backtest.py collect <folder>    # a skeleton expectations file for a person to fill in
python tools/backtest.py run <folder>        # route the corpus, score it, time it
python tools/backtest.py record              # make that report's agreement the baseline
python tools/backtest.py check               # exit 1 when a report is below the baseline
```

The corpus, its expectations.csv and the report are the firm's: they never
enter the repository, and the tool refuses to write either file into the
tree. Nothing identifying comes back either — the report and the console
carry counts, catalog identifiers and a document's row number in the
expectations file, never a file name, never a folder name below the corpus
root, never a word of a document. The baseline ships unrecorded and `check`
says so plainly rather than passing quietly: an unknown baseline is not a
met one. Once the owner has run the backtest at the office and recorded it,
no routing change may lower that number.

## The standing rules

These are not style preferences. They are why the system is trusted with
client tax documents, and they hold across every module. They are worded
once, in `STANDING_RULES` in `tracker/__init__.py`; the app shows them and
`tests/test_single_source.py` keeps this copy, the README, the roadmap and
the knowledge map quoting them exactly:

- **No generative AI ever reads a client financial document.** Every routing
  and status decision comes from deterministic rules in the manifest.
- **Originals are never altered.** Files are moved byte for byte under their
  own names into `Shared/PBC/`; all work happens on copies, and every move is
  recorded in `_index.xlsx`.
- **Nothing is guessed.** A document is filed only when exactly one request
  accepts it. Ambiguous, contested and unrecognized files go to
  `00 - Needs Review` for a person — misfiling a tax document is worse than
  not filing it.
- **Nothing is ever sent.** The system drafts client emails and stops. There
  is no SMTP, no mail client and no network call in the reminder or scheduling
  path.

`docs/ROADMAP.md` holds the decision log — the record of *why* things that
look arbitrary are the way they are. Read it before changing behaviour that
seems odd; the odd choice is usually load-bearing.

[`docs/runbook.md`](docs/runbook.md) is the same system from the operator's
side, written for a person rather than an agent: which machine runs the
schedule and why only one may, what someone does each morning and on the
draft day, what every index reason and validation note means, and how the
firm moves to another machine. Change how any of that behaves and the
runbook is part of the change.

## Working on this repo

```
pip install -r requirements.txt
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

Client data never enters the repo: `runs.log` and the
drafts are gitignored because they carry real client names and share links.
