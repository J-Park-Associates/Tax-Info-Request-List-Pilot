# Shell final review C - completeness and consistency of the whole

Reviewer: independent Opus session (built none of the shell), 2026-09-30.
Branch reviewed: `claude/shell-join` at `0b278d9` against `origin/main` (`e22b539`).
Area C: every ruling implemented or logged; the decision log and the documents agree
with the code and each other; the Windows check and handoff for Jason; the build
config; the whole suite; git hygiene. No code was changed.

## Verdict

Two findings **block the merge** (C1: a guard test fails on the branch and not on
`main`; C2: ruling 20's Retry cannot clear the notice it sits on, and on a firm page
it draws a command-line sentence). The rest are should-fix or notes, mostly
bookkeeping that would mislead Jason or the next session.

## Findings

**C1 - BLOCKS merge. The vocabulary coverage report is stale; `test_vocab_report` fails on the branch, passes on `main`.**
`docs/vocab-coverage.json:9410-9411` hashes `tracker/manifest.py` and
`tracker/templates.py`, which the join changed (Title Case words only: `Partly In`,
`Not Asked`, `Repair the Schedule`, ...). `python tools/vocab_report.py check` exits 1
("2 input(s) changed"); `tests/test_vocab_report.py::test_the_committed_report_is_current`
fails under 3.11 and 3.13. CLAUDE.md: rebuild it in the same commit. I rebuilt it in a
scratch copy: the only difference is those two hashes, so **no routing change** - it is
bookkeeping, but the suite is red until `python tools/vocab_report.py build` is committed.

**C2 - BLOCKS merge (JASON for the wording of the fix). Ruling 20's "Sort Failed" notice: Retry does not clear it, and on a firm page Retry fails with a command-line sentence.**
`app/renderer/shell.js:473-481` shows the notice while `list.last_pass.ok === false` and
gives it `retry: runScan`. But `last-pass.json` is written **only** by the scheduled
job's shape (`tracker/runner.py:2697`: `ns.settings and not ns.root and ns.household is None`;
decision 159, "a pass run by hand must not make a stopped schedule look alive"), and the
app's Sort (`app.js:2152` -> `api.py:3025` `run-now`) always names a household.
Scenarios: (a) the overnight pass fails; the preparer opens a client, presses Retry; the
household sorts fine; the notice comes straight back on the next redraw and stays until
the next scheduled pass - ruling 20 says "it clears when a sort works". (b) The same
notice on Overview right after launch (`active` is null, `app.js:9`): Retry sends
`run-now` with no `--engagement`, and `api.py:1042` answers
"Pick an engagement first (--engagement <folder>)" - a flag on screen, over five words,
and P80 greys Sort on firm pages for exactly this reason. The unit test
(`tests/test_shell.py:2250`) mocks `shellLastPass`, so it cannot see either. Fix options
for Jason: Retry on this notice runs nothing on firm pages (or is not offered), and the
notice's words say it is the overnight sort; or the app's own successful sort clears the
notice for the session. Also PROMPT-shell step 11 (C7) cannot produce this notice.

**C3 - should fix. `pilot/handoffs/shell-rulings.md` on the branch stops at ruling 14.**
Rulings 15-22 and 18a exist only on `origin/claude/amazing-maxwell-b4hdzo`; the branch's
copy (22 lines) lacks them, yet `DECISIONS.md` P99-P107 each cite
"`pilot/handoffs/shell-rulings.md`" as their source. Bring the full file onto the branch.

**C4 - should fix. Decision rows and the ledger are frozen before S5 rebuild 2 was joined.**
`pilot/DECISIONS.md:106,107,111` (P100, P101, P105) say "Status: S5 rebuild 2"; P92, P94-P97,
P99, P102, P106 say "pages S5" / "S5 draws it". All of that is now on the branch (S6b
merged `claude/shell-s5-sheet`; verified below). `pilot/handoffs/shell-ledger.md` is "as of
2026-09-29 (evening)": rows 8-13 "In progress", no rows for 14-22, and its "Work that
predates the rulings" table lists fixes that are done. HANDOFF.md:6 calls it "the live
ledger". Update the statuses, or mark the ledger closed and point at DECISIONS.

**C5 - should fix (JASON). "Waiting on Jason" is incomplete in `pilot/HANDOFF.md:24-30`.**
It names only `pick_request` and `name_requests`. Also open, with defaults taken:
SPEC section 19 O1-O6 (`pilot/SPEC-shell.md:1893-1908`; the ledger's six defaults, e.g.
"Tracker Failed" vs ruling 6's "Tracker failed", the cut-name-vs-link tooltip, the
keyboard path to a name link, and O4 - "Show in File Explorer" added to right-click menus,
built without a ruling); ruling 18 says the eight two-word misfit reasons are for Jason to
approve "before the pilot", and 18a calls "Bad Year" a working word "Jason may change",
yet `pilot/wording-shell.tsv:139-147` marks all nine "Approved by Jason". Either get the
approvals or say "proposed" in the TSV and list them in HANDOFF.

**C6 - should fix. The SPEC does not carry rulings 16, 17 and 20.**
"Nothing is built without a written SPEC." `pilot/SPEC-shell.md` has no "Reason (Optional)"
confirm box for Unfile (ruling 16), no one-row-per-file rule (17) and no failed-sort
notice with Retry (20); its preamble (lines 20-45) lists rulings through 14. 18 and 21
are there (lines 1106, 1135, 1506). It still says "Mark missing" (239, 884) and "Needs
review" as the section's name (160, 322, 487, 720, 776, 1783) - ruling 10 wants "Mark
Missing" / "Needs Review".

**C7 - should fix. `pilot/wintest/PROMPT-shell.md` has steps Jason cannot complete as written.**
- Step 11 (line 63): renaming the Clients folder and pressing Sort runs `run-now`, which
  never writes `last-pass.json` (C2), so no "Sort Failed" line or notice appears; Jason
  would record a false FAIL. The notice needs a failed **scheduled** pass (for example:
  rename the Clients folder, then Task Scheduler, Run on the tracker's task; rename back).
- Step 12 "Switch the older return off": say where, with the menu's own words.
- Step 13 (line 70): "where a year folder would sit" - say
  `J Park & Associates\<household>\Archive 2024` (the private tree; `registry.py:480`).
- Step 14 (line 72): "make a command fail" gives no way to do it on a fresh user.
- Code first: `git fetch` / check out a branch is a programmer's step; after the merge it
  should read "the installer from the release" or give the exact commands.

**C8 - should fix. The runbook and README still describe the pre-shell app.**
CLAUDE.md: "Change how any of that behaves and the runbook is part of the change."
`docs/runbook.md` names **Sort & Scan** (250, 253, 594, 692, 895, 2055, 2210), "the
engagement picker" (247), "**Folders the tracker leaves alone**" in the app (248; the app
now has the Folders Skipped dialog, and the status-page heading is now "Folders the
Tracker Leaves Alone", `runner.py:2270`), the household's "card" and "**New household** on the
toolbar" (396; now File, New Household...), "**Add a return**" / "**Roll forward**" (285,
396; now "Add a Return...", "Roll Forward..."), the "Routing rules" fold (331; S5 made it
one Advanced switch), "**Not asked**" (434), "Help, Open error log" (574; menu is "Open
Error Log"). `README.md:115-120` has the same card/toolbar text. It never mentions the side
panel, the pages, the right-click menus, Show in File Explorer or Folders Skipped.

**C9 - note. Leftovers of removed things.**
No glass, Mica, refraction, `backdrop-filter`, old tabs or sidebar, "Feed Return Not Found"
or "Not A Year" in any code path (only decision-log history, the SPEC-ui/test pins that
forbid them, and one comment at `tracker/api.py:1356`). But `pilot/mockup-shell.html:369,399`
still reads "Could not tell" and lower-case reasons; HANDOFF.md says the published mock-up
is current - the in-repo source is not. `pilot/README.md:56` still indexes `SPEC-glass.md`
(marked withdrawn; fine as history).

**C10 - note. Tests that do not pin what the rows say they pin (mutation survivors).**
`SAFEGUARDS` words: changing "Nothing Is Guessed" to "Nothing Guessed" passes every test
(`test_single_source.py:3999` checks count and order only). The ruling 22 runbook note can
be deleted with no test failing. Neither is harmful today; both are approved words/notes
that nothing holds.

## (1) Rulings 1-22 and 18a

| Ruling | Where | Verified how |
|---|---|---|
| 1 keydown exception | logged P85; SPEC 14.1 | read |
| 2 focus tip except search | `tooltip.js:124-134` (`!node.matches("#find")`) | mutation killed by `test_shell` |
| 3 menu hidden until Alt | `main.js:675` `autoHideMenuBar` | read |
| 4 fallback log, local folder, deny list | `main.js:133-142`; `.claude/settings.json` last 8 rules | mutations: roaming path killed (`test_shell_menu`), deny rule removed killed (`test_single_source`) |
| 5 Floating UI 1.8.0 vendored | `app/renderer/vendor/floating-ui/` (2 files + 3 licences), `index.html:504-505` | SHA-256 recomputed = `test_shell.py:58-59` |
| 6 failure text as built | `api.SHELL_NO_LOG` "Tracker Failed" (ruling 10 default, C5) | read |
| 7 300 ms | `tooltip.js:16`; SPEC 8.5 line 1018 | mutation 500 killed |
| 8-12 links | `api.py:1213-1234` words; `pages.js` link kinds | `test_api` kills "Navigate To Client" |
| 10 Title Case | engine words, `index.html`, tour | "Could not Sort" killed by `test_api`; tour "Needs review" killed by `test_tour` |
| 13 "{Return} ({Year})" | `pages.js:122` `pagesReturnText` | read |
| 14 notice words | `api.py:1333-1336` | "Feed Return Not Found" killed by `test_api` |
| 15 firm file links | `firm.files[].open_key`, `firm.paths` (`api.py:5455-5459`) | read |
| 16 Unfile reason box | `app.js:1192-1201`, `UNFILE_NOTE_HINT` | test at `test_shell.py:2219`; SPEC missing (C6) |
| 17 a row per file | `pages.js:360,752` | read; SPEC missing (C6) |
| 18 / 18a reasons, Bad Year | `api.py:1357`, `registry.py:481` | "Not A Year" killed by `test_registry` and `test_api`; approval status (C5) |
| 19 sheet moves on | no change | logged P104 |
| 20 failed-sort notice | `shell.js:473-481` | clear mutation killed; behaviour wrong (C2) |
| 21 paused marker | `api.py:5446-5455`, `pages.js:247-251,463-467,561-564` | `paused=False` killed by `test_api` |
| 22 runbook note | `docs/runbook.md:575-581` | present; unpinned (C10) |

## (2) Decision log and documents

P85-P107 quote rulings 1-22 and 18a verbatim and in order; content agrees with the code
except the stale statuses (C4) and the missing source file (C3). `tests/test_single_source`
standing-rule wording: `tracker/__init__.py` `STANDING_RULES` is unchanged by the join
(only `SAFEGUARDS` added) and the test passes. `python tools/repo_map.py check`: current
(336 nodes) at `0b278d9`; this review file alone makes it stale (it maps
`pilot/handoffs`), per the instructions no update was run. `ruff check .`: clean.

## (3) Build config

`app/package.json` uses `@electron/packager` over the whole `app/` folder
(`Build App.bat:66`) and `pilot/installer/setup.iss:39` takes the packaged folder
recursively, so `sheet.js`, `tooltip.js`, `shell.js`, `pages.js`, both Floating UI files
and the three licences ship with no list to update. The harness lives in
`pilot/harness/`, outside `app/`, so it and the tests never ship; the harness writes its
screenshots and vocabulary dump to the OS temp folder. Nothing to fix.

## (4) The whole suite

All 55 test files, each its own process (four at a time), Python 3.11.15 and 3.13.12:
**3982 passed** in each, the same **7 failures** in each:

| Failure | New vs `main`? | Cause |
|---|---|---|
| `test_vocab_report::test_the_committed_report_is_current` | **new** (passes on `main`'s tree) | C1 |
| `test_build::test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else` | pre-existing (fails on `main` too) | the known OCR scratch-roots failure: `rapidocr` is not installed in this sandbox |
| `test_ocr` (4 tests) | pre-existing (fail on `main` too) | `rapidocr` not installed |
| `test_real_corpus::test_corpus_rows_are_named_by_number_in_ids_messages_and_the_cache` | could not compare (on `main`'s exported tree it errors at setup: no `.git`) | its inner run skips `row-2`; the join touches no router, reader or corpus file, so almost certainly the missing reader - confirm on the office PC |

`main` was run from a `git archive` export, so its extra failures (`test_repo_map`,
`test_single_source`, `test_tripwire`, `test_build` CRLF) are the missing `.git`, not
`main`. No catalog, matcher, router or typed-case file changed; `docs/backtest-baseline.json`
is unchanged (still no recorded run); the rebuilt vocabulary report differs only in the two
input hashes (C1). `ruff check .` clean; `repo_map.py check` current.

Mutation checks (scratch copy, 13): killed - "Bad Year" -> "Not A Year" (`test_registry`,
`test_api`); feed word (`test_api`); 500 ms (`test_shell`); search box focus tip
(`test_shell`); "Navigate To Client" (`test_api`); `paused=False` (`test_api`); the sort
notice never cleared (`test_shell`); deny rule removed (`test_single_source`); fallback
log to roaming AppData (`test_shell_menu`); "Could not Sort" (`test_api`); tour "Needs
review" (`test_tour`). Survived - the SAFEGUARDS words and the ruling 22 runbook note (C10).

## (5) Git hygiene

`origin/main` and every shell branch (S2, S4, S5, S7, S8a, S8b, spec-sync) are fully
contained in the join; the six merges on it are true merge commits (two parents); no
branch was rebased or force-pushed as far as the graph shows. The diff adds no binary
but three licence texts; grep of the added lines for keys, tokens, passwords, SSNs, e-mail
addresses and `C:\Users\<name>` paths found none (only the firm's admin address in a test
pin, already on `main`, and `/secret/...` fake paths in a test). `.gitignore` unchanged and
sufficient. Made-up names only.
