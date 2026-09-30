# SPEC: keeping the plain-English library current, automatically (P116)

Jason, 2026-09-30: "add the test that enforces it and i want it to be
completely automated efficiently so the handoff documentation can be well
kept." The library is `docs/For NonCoders/` (82 pages: 21 program-file
pages, 61 handoff-note pages; built and fact-checked in the session
recorded in `pilot/handoffs/maintainer-handoff-audit.md`).

## 1. The problem

A page is a translation of one or more originals. Three things make it
wrong silently: a new handoff note arrives with no page; an original
changes after its page was written; a page is moved or its tags edited and
the start page (`docs/For NonCoders/README.md`) no longer lists it right.
Nothing today notices any of them.

## 2. The design, in one paragraph

A standard-library tool, `tools/noncoder_pages.py`, owns the library's
bookkeeping the way `tools/vocab_report.py` owns its report: it
fingerprints every original (SHA-256, hashed as Git commits it, the
map's `git_text_auto_eol_lf` rule of decision 151) into a generated,
committed `docs/For NonCoders/pages.json`; generates the start page from
the pages' own Tags lines; and `check` fails, naming each page and what to
do, on any gap. Three triggers run `check`, from cheapest to last resort:
(1) a Claude Code **Stop hook** in `.claude/settings.json`, so an AI
session that leaves a page stale is told to fix it before it ends;
(2) `tests/test_noncoder_pages.py`, a guard every gate runs;
(3) CI, which runs the suite. Writing the page stays with the agent (an
AI may read handoff notes and program files - these are not client
documents); only the bookkeeping is automated, deterministically.

*Rejected:* hashes on each page (a page edit would churn its own hash);
generating pages without a model (a skeleton passes a structural check
and says nothing); a hook that edits pages itself (hooks must not write
prose; the agent does, and a person can read the diff).

## 3. `tools/noncoder_pages.py`

Standard library only; module docstring carries this reasoning. CLI:

| Command | Does |
|---|---|
| `check` | Exit 0 when current, 1 when not; prints one line per problem, each with the exact fix. |
| `todo` | Same findings as `check`, printed as a work order: for each, the page to write or update (repository-relative path), the original(s) to read, and the style rules file. Exit 0 always. |
| `stamp [PAGE ...]` | Record the current fingerprints of the given pages' originals (all pages when none given) and regenerate the start page. The one way `pages.json` changes. Run after a page is written or updated - or reviewed and found still accurate. |
| `place NOTE` | Print the folder and file name a new handoff note's page belongs at (section 5). |
| `hook` | For the Stop hook (section 6). |

### 3.1 What a page is

Every `*.md` under `docs/For NonCoders/` except `README.md`. It must have:
a first line `# ` title; a `**Original file:**` line naming one or more
originals in backticks, repository-relative, each an existing tracked
file; a `**Tags:**` line `Kind: <kind> · Topic: <t>[, <t>...][ · Stage: <s>]`
with the kind and every topic from the vocabularies in section 4; and the
six section headings of its layout (program layout for Kind
`Program file`, handoff layout otherwise - the headings exactly as in
`docs/noncoder-style.md`, section 7). At most 200 lines. No
sentence matching `once after (install|upgrad)` (decision 209's guard).

### 3.2 What `check` reports

1. **Missing page:** a file matching `pilot/handoffs/*.md` or
   `pilot/HANDOFF.md` that no page names as an original. Fix text names
   the path `place` gives.
2. **Stale page:** an original whose current fingerprint differs from the
   one in `pages.json` (or has none). Fix: "update the page (or confirm it
   is still accurate), then `python tools/noncoder_pages.py stamp '<page>'`".
3. **Orphan record:** a `pages.json` entry for a page that no longer
   exists, or an original the page no longer names.
4. **Malformed page:** any rule of 3.1 broken.
5. **Start page out of date:** `README.md` differs from what `stamp`
   would generate.

Findings are sorted and deterministic. `check` never writes.

### 3.3 `pages.json`

`{"version": 1, "pages": {"<page path>": {"<original path>": "<sha256>"}}}`,
keys sorted, 2-space indent, trailing newline. Generated; never
hand-edited (say so in the tool's docstring and in the start page's
footer).

## 4. Tag vocabularies (fixed in the tool, one place)

Kinds: `Overview`, `Program file`, `Build`, `Review`, `Fix round`,
`Final check`, `Rulings`. Topics: `Safety`, `App window`, `Engine`,
`Schedule`, `Installer`, `Building`, `Supply-chain safety`, `Testing`,
`GitHub costs`, `Rules and decisions`, `Code map`, `Screen`, `Wording`.
Stage: `S` + digits + optional lowercase letter. Each with the one-line
meaning the current start page gives; the start page's tag tables are
generated from these.

## 5. Where a new handoff note's page goes (`place`)

Deterministic, from the note's file name, reproducing the current layout:

- `shell-S<n><x>.md` / `-review-<k>.md` / `-rebuild-<k>.md` → the stage
  folder under `6 - Work History (Handoff Notes)` whose name starts
  `Stage <n> - ` (an existing folder; a stage with no folder is reported
  as needing one named by a person). File name `S<n><x> - NN <Label>.md`,
  NN the next number after the highest already in that folder for that
  stage prefix, Label `Build`, `Review k` or `Fix Round k`.
- `shell-final-*`, `shell-fixpass*` → `Final Checks`, next number.
- `shell-rulings*`, `shell-ledger*`, `shell-spec-sync*` → `Jason's Rulings
  and Plan Updates`.
- anything else → `Other Work/<YYYY-MM-DD> <Title Case of the stem>.md`,
  the date from the note's first line with a date, else today.

`place` only prints; the agent writes the page there.

## 6. The Stop hook

Add to `.claude/settings.json`, merged (the file has only `permissions`
today; keep every existing entry):

```json
"hooks": {"Stop": [{"hooks": [{"type": "command",
  "command": "f=\"$CLAUDE_PROJECT_DIR/tools/noncoder_pages.py\"; [ -f \"$f\" ] || exit 0; for p in \"$CLAUDE_PROJECT_DIR/.venv/Scripts/python.exe\" \"$CLAUDE_PROJECT_DIR/.venv/bin/python\" python3 python; do command -v \"$p\" >/dev/null 2>&1 && exec \"$p\" \"$f\" hook; done; exit 0",
  "timeout": 30}]}]}
```

`hook` reads the hook's JSON from stdin (tolerate empty or invalid
input). When `check` passes: exit 0, print nothing. When it fails and
`stop_hook_active` is not true: print to **stderr** a short work order
(the `todo` text, at most 20 findings then "and N more") headed
"The plain-English library (docs/For NonCoders) is out of date:" and exit
**2** - Claude Code then keeps the session going with that text as its
instruction. When `stop_hook_active` is true (the session already tried
once): exit 0 and print the same text to stdout as a warning, so a
session that cannot fix it is never trapped; the test and CI still hold
the line. Any exception inside `hook`: exit 0 with a one-line warning on
stdout - a broken hook must never block work. The command is a shell line that exits 0 when the script is missing and prefers the checkout's own `.venv` Python, so a missing script or interpreter can never trap a session. Runtime budget: under one
second on this repository (hash ~100 files; no subprocess except none).

## 7. Files

- `tools/noncoder_pages.py` (new).
- `tests/test_noncoder_pages.py` (new). Claims, each its own test, most
  on a temporary copy of a miniature library built in `tmp_path` (the
  tool takes the repository root as a parameter for this):
  - `test_the_committed_library_is_current` (runs `check` on the real
    repository: this is the guard);
  - a new handoff note without a page is reported with its `place` path;
  - an original changed after `stamp` is reported stale, and `stamp`
    clears it;
  - an orphan record, a malformed page (each rule of 3.1), and a
    hand-edited start page are each reported;
  - `place` for each naming family of section 5, including numbering;
  - the hook exits 2 with the work order on stderr when stale, 0 when
    current, 0 (warning on stdout) when `stop_hook_active` is true, and 0
    on garbage stdin or an internal error;
  - `.claude/settings.json` registers the hook command exactly and keeps
    its `permissions` block;
  - `pages.json` round-trips byte for byte through `stamp` on an
    unchanged tree.
- `docs/noncoder-style.md` (new): the style rules the pages follow -
  copy `/tmp/claude-0/-home-user-Tax-Info-Request-List-Pilot/7148f3af-4141-5d3a-99f1-c8a659198d13/scratchpad/STYLE.md`
  (the rules the pages were written to) into the repository, dropping its
  rule 7 (a one-off instruction to the writers), plus one section
  "Keeping the library current" (the three commands a session uses:
  `todo`, `place`, `stamp`). `todo` and the hook point to this file.
- `docs/For NonCoders/pages.json` (generated by `stamp`).
- `docs/For NonCoders/README.md` (now generated; its content otherwise
  as today, plus a footer line: "Generated by tools/noncoder_pages.py
  stamp; do not edit by hand.").
- `.claude/settings.json` (hook added).
- `CLAUDE.md`: in "Test minimally", add `test_noncoder_pages` to the
  guard files; add a short paragraph under "Keeping the map current":
  a new handoff note or a change to a translated original comes with its
  page, and the Stop hook and the test enforce it; the commands.
- `tests/test_layers.py`: `("tools/noncoder_pages.py", "*")` in
  `ALLOWED_SPELLINGS` if it uses a path relation, with the same reason
  as `repo_map`'s.
- `docs/repo-map.curated.json`: nodes for the tool (role and the
  reasoning) and `pages.json`; `python tools/repo_map.py update`.
- `pilot/DECISIONS.md`: row P116.
- `docs/maintenance-guide.md`: one sentence in "Where to look next"
  already links the library; add under Part 5 one plain paragraph: the
  library keeps itself honest - a new note or a changed file cannot be
  finished without its page.

## 8. Done when

`python tools/noncoder_pages.py check` exits 0 on the committed tree;
the new test file passes; the guard files pass; `ruff` is clean; the map
is current. The hook is pipe-tested:
`echo '{}' | python tools/noncoder_pages.py hook` exits 0 on the
committed tree and 2 after touching one original.

## 9. Amendment (Jason, same day): the tool also organizes the library

"have it also organize files as you just did, placing them in correct
folders, moving outdated files to history subfolders and renaming files
as well." Scope: the pages under `docs/For NonCoders/`. The originals
(`pilot/handoffs/`, the program files) are never moved or renamed - other
files and tests cite their paths.

### 9.1 `organize`

A new command, `organize [--dry-run]`, that moves and renames pages to
where the rules say, deterministically, and never edits a page's prose.
It prints one line per move ("moved: A -> B") and, with `--dry-run`,
changes nothing. After moving it regenerates the start page. Rules, in
order:

1. **Retire.** A page none of whose originals exists in the working tree *and* each of which Git shows was committed once and removed since (absent from `HEAD`, present in `git log`; no Git, never retire - review 2: a note renamed before its first commit is not a removal) is moved to
   `7 - History/Retired Pages/<its path relative to the library>`, and a
   line `**Retired:** <YYYY-MM-DD> - the file it explained was removed.`
   is inserted after its Tags line (the one text edit organize makes). A
   page with some originals gone and some present is not retired; `check`
   reports it as malformed (its Original line needs fixing by the agent). An original missing from the working tree but still in `HEAD` is a `check` finding (a rename or an uncommitted deletion), never a retirement.
2. **Handoff pages** go exactly where section 5 says, under the name
   section 5 gives. Numbering is recomputed for the whole stage folder
   from the originals (build, then review k and fix round k in turn, then
   anything else in name order), so a page inserted out of order moves
   the later ones up and they are renamed with it.
3. **Program pages** (Kind `Program file`) belong under the section folder
   of their first Topic:

   | First topic | Section folder | Default subfolder |
   |---|---|---|
   | Safety, App window | `2 - How the Program Works` | `Safety Walls` |
   | Engine, Schedule | `2 - How the Program Works` | `Engine and Schedule` |
   | Installer | `3 - Building and Installing` | `Installer` |
   | Building | `3 - Building and Installing` | `Building the App` |
   | Supply-chain safety | `3 - Building and Installing` | `Supply-Chain Safety` |
   | Testing, GitHub costs | `4 - Testing and Checks` | `Tests on This Computer` |
   | Rules and decisions, Code map, Wording, Screen | `5 - Rules, Plans and Decisions` | (none) |

   A page anywhere inside its section folder stays put (a person may
   choose the subfolder); one outside it moves to the default subfolder.
   Its file name must contain, case-insensitively, the file name, the
   stem, or the parent folder's name of one of its originals; otherwise it
   is renamed `<current stem> (<first original's file name>).md`.
4. **Overview** pages go to `1 - Start Here`.
5. A move onto an existing different file is refused with a message
   (never overwrite); empty folders left behind are removed. If a move
   fails part way, every page is put back in two phases, never over an
   existing file, and any page that cannot be put back is named with where
   it now is (review 2).

The current library already satisfies rules 2-4: `organize --dry-run` on
the committed tree prints nothing. A test pins that.

### 9.2 Earlier versions

`stamp` keeps the version a page replaces. `pages.json` records, per
page, the SHA-256 of the page itself as stamped (`"page": "<sha256>"`
beside the originals, schema version 2). When `stamp` finds a page whose
text differs from its recorded hash and the recorded version exists in
Git's `HEAD` (`git show HEAD:<path>`), it writes that earlier text to
`7 - History/Earlier Versions/<page stem> - until <YYYY-MM-DD>.md`
(numbered ` (2)`, ` (3)` on a clash) before recording the new hash. No
Git, or no earlier version in `HEAD`: say so in one line and continue.

### 9.3 History is exempt, and listed

Everything under `7 - History/` is outside the rules of 3.1 and 3.2 except
that it must start with a `# ` title; its pages are not in `pages.json`.
The start page lists them in a final section "History" (retired pages and
earlier versions, each linked), and the folder table gains
`7 - History` - "Pages whose file was removed, and earlier versions of
pages that were rewritten."

### 9.4 Automation

The Stop hook runs `organize` (applying, not dry-run) and then `check`:
the mechanical part fixes itself, and only the writing is handed back to
the agent. When the hook's `organize` moved anything the hook exits 2 (unless `stop_hook_active`) listing the moves and "stage these moves (git add -A) and run python tools/repo_map.py update". A partly failed `organize` rolls back every rename it made and raises; a leftover `*.organize-*` file is a `check` finding. A refusal
(rule 5) is a finding in the work order. `todo` lists what `organize
--dry-run` would do first.

### 9.5 Tests added

Retirement (with the Retired line), stage renumbering when a note is
inserted, a program page outside its section moved to the default
subfolder, a program page with an unrelated name renamed, a page inside
its section left alone, refusal to overwrite, empty folders removed,
`organize --dry-run` on the committed tree prints nothing, `stamp` keeps
an earlier version (a temporary Git repository in `tmp_path`), and the
hook applying organize before check.
