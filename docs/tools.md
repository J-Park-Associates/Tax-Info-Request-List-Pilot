# The routing tools: vocabulary report, learned keywords, backtest

Moved here from `CLAUDE.md` on 2026-09-25 so that every agent session does
not load it; `CLAUDE.md` points here. Read this before changing a catalog
keyword, a typed case or the matcher, or before running the backtest.

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
file the way the IRS forms are routed, and names each by its row in that
file, never by its name, so no client's file name reaches a test id, the
console or pytest's cache; it skips when the variable is not set, so a
machine without a corpus (CI, a fresh clone) is green. The documents are
never committed, redacted or not. The coverage report's `build` refuses to
write the committed report while the variable names a corpus;
`python tools/vocab_report.py build --out <folder>` writes that reading
outside the repository, each real document named by its row, and `check`
refuses a committed report built with them (decision 185). The report reads each document the router's way (decision 208), so a
damaged one in that folder stops `build` with one sentence naming every
damaged document by its expectations entry (its place among the rows that
name a file) and its error class — never a file name, the folder or the
parser's message. Fix or remove those files, then build again.

The catalog is not the only vocabulary in the field. When a person files a
parked document they may type a keyword, and it is recorded against that one
engagement's request — invisible to every other engagement and to the
catalog the suite tests, and laid over the row's own `Any Keywords` by every
reader. A word that turns out not to be distinctive is taken back in the
app's editor, per engagement, as one `keyword_unlearned` event that both
folds know and `store.check()` compares (decision 113); the firm-wide
vocabulary is still `tracker/templates.py` and still changes only by a
commit. `tools/learned_keywords.py` is the season's list of
them: it walks every engagement under the clients root, compares each request
row's keywords against the catalog rows carrying the same identifier and
document, and groups what is left by row with the number of engagements that
typed it. It only reads — no lock, no write-back — and by default it prints
no client's name, no folder and no problem's text - `--engagements` names the
engagements and why any could not be read, so a keyword several engagements had
to be taught separately can be promoted into `tracker/templates.py`, where
the suite defends it. It can run each candidate over the IRS forms in
`tests/irs/` first, and marks the ones that would misfile a form the suite
already places.

## The backtest: the firm's own documents score the router

[`docs/backtest-baseline.json`](docs/backtest-baseline.json) holds one
number — how often the router files the firm's own already-sorted
documents where a person filed them — and `tools/backtest.py` measures it.
The blank IRS and state forms in `tests/irs/` and the typed cases are paperwork nobody sent;
the documents a client actually sent sit on the office file server, sorted
by hand over years, and they are the only corpus that can say whether the
routing rules work on real mail. The tool routes them against the shipped
catalogs and reports the agreement, the confusions (expected this row,
filed that one), the per-row table, the parked and no-text shares, and the
time each document took. Each document is routed through a hard link under
one neutral name (`NEUTRAL_STEM`), so the client's own file naming never
reaches the router with the document: nothing is filed on a name (decision
92), but a name still leaves evidence for the person reviewing, and what
is scored — and written down — should be the rules, not the firm's naming.

```
python tools/backtest.py collect <folder> --catalog 1040 --year 2025 --out <file>   # a skeleton expectations file for a person to fill in
python tools/backtest.py run <folder> --out <report>    # route the corpus, score it, time it
python tools/backtest.py record --report <report>       # make that report's agreement the baseline
python tools/backtest.py check --report <report>        # exit 1 when the report is below the baseline
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

