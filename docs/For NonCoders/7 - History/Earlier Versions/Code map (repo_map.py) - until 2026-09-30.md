# Code map

**Original file:** `tools/repo_map.py`, with `docs/repo-map.md`, `docs/repo-map.json` and `docs/repo-map.curated.json`  
**Kind of file:** helper tool (Python) and the map files it builds  
**Tags:** Kind: Program file · Topic: Code map  

## In one sentence
The code map is a single guide to the whole program - what every file is for, what it depends on, and which tests cover it - and `repo_map.py` builds it and checks that it is still true.

## What it is
A program made of hundreds of files is hard to learn by reading. The map lets a new worker (usually an AI helper) look up one file instead of re-reading everything. There are four pieces:
- **`tools/repo_map.py`** - the tool that builds, updates, checks and looks up the map. It uses only Python's standard parts, so it runs anywhere the project does.
- **`docs/repo-map.json`** - the full map in a machine-readable form (348 nodes and 1162 links when last built). Generated. Do not edit by hand.
- **`docs/repo-map.md`** - the same map as a readable page. Generated. It says at the top that it must not be edited.
- **`docs/repo-map.curated.json`** - the hand-written part: what each file is *for*, the files it creates while working, and the standing rules. It survives every rebuild.

The map has two layers on purpose. The *derived* layer is read straight from the code by the tool (what each file imports, what it offers, which tests belong to it, a fingerprint of the file). The *curated* layer holds judgment no program can work out.

## What it does, step by step
The tool has four commands:
1. **update** - the normal refresh. Each file's fingerprint (a SHA-256 code) is compared with the one stored, and only changed or new files are read again. It refuses to run in the middle of an unfinished merge.
2. **build** - rebuilds everything from nothing. Rarely needed.
3. **check** - proves the map is current and true. It compares fingerprints, rebuilds the derived layer and compares it fact by fact, then re-creates the readable page and compares that. A hand-edited fact, a forged link or a forgotten refresh all fail it. It exits with an error if anything is stale.
4. **show** - prints one file's entry, with its links, tests and artifacts (the files it reads and writes while running).

Two kinds of test link are kept apart on purpose. "Tested by" means the test file that owns the module by name. "Exercised by" means some other test only borrows it, which is not coverage. Likewise "imports" means loaded at start, while "imports at call time" means loaded only when a function runs.

## Why it matters to the firm
The map saves time and prevents mistakes: a helper reads the one entry it needs instead of guessing. It also records why odd design choices exist. A repository test (`test_the_committed_map_is_current`) fails if the map drifts, so nobody works from a wrong map.

## What must never be changed without a programmer
- Never edit `repo-map.json` or `repo-map.md` by hand. The next update overwrites them.
- To change a description, edit `repo-map.curated.json` and then run update.
- Refresh the map in the same commit as any code change.
- Do not loosen `check`. Its strictness is the point.

## Words to know
- **Map / knowledge graph:** a guide of files (nodes) and how they connect (links).
- **Derived:** worked out by the tool from the code.
- **Curated:** written by a person; kept across rebuilds.
- **Fingerprint (SHA-256 hash):** a code that changes if a file changes at all.
- **Import:** one file using another.
- **Incremental:** redoing only what changed.
- **Commit:** a saved step in the project's history.
