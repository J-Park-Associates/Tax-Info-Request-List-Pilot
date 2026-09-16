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
  Real and worth knowing (ten test files import `manifest.py`, so its schema
  is load-bearing across the suite) but it is *not* coverage of that module.
- **no dedicated test file** — said plainly where it is true. As of this
  writing that is `tracker/api.py`, the desktop app's whole command layer.

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

## The standing rules

These are not style preferences. They are why the system is trusted with
client tax documents, and they hold across every module:

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

## Working on this repo

```
pip install -r requirements.txt
python -m pytest -q                 # the whole suite, all green
python tools/repo_map.py check      # map matches the tree
```

Conventions worth matching:

- Python 3.11+, `pathlib.Path` throughout, standard library preferred.
- One component per module, each with its own CLI under
  `if __name__ == "__main__":` and its own `tests/test_<module>.py`.
- Module docstrings carry the *reasoning*, not just the description — the
  trade-off, the rejected alternative, the rule being upheld. Match that.
- Fail loudly with context. A silent skip in a scheduled job surfaces at a
  filing deadline.
- Tests are named as the claim they make
  (`test_overrides_are_never_asked_for`), not `test_case_3`.

Client data never enters the repo: `engagements.yaml`, `runs.log` and the
drafts are gitignored because they carry real client names and share links.
