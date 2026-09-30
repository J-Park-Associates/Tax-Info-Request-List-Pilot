# Shell final check 2: fix pass 2

Checker: an independent Opus session. I built none of the shell and none of
either fix pass. Branch `claude/shell-join` at `ed0ef69`. Diff checked:
`d555b2a..ed0ef69`, against NEW 1-5 of `shell-final-rereview.md`, the "Fix
pass 2" section of `shell-fixpass.md` and rulings 24-30. No code was changed.

**Verdict: no finding blocks the merge.** N1-N5 are fixed in the code and were
confirmed by running it. What is left is two one-line document fixes and three
words for Jason.

## How it was checked

- **N1 and N2 with the real engine.** A probe on a scratch tree built with
  `tests.samples` and `tests.test_runner.build_engagement`. It had one
  household with two returns and one household never sorted. The runs from
  the real final line were fed through the page's own `scanFailed` and
  `scanSummary`, lifted out of `app.js` and run under node. The scheduled pass
  ran as a real `python -m tracker.runner --settings <dir> --log` subprocess,
  and `last_pass` was read back through a real `python -m tracker.api list`.
- **Regression.**
  - Setup: fresh venvs built from `requirements.lock` and
    `requirements-nodeps.lock`, so the reader is installed.
  - Run: every test file in its own process, four at a time.
  - Python 3.11.15: all 55 files exit 0. **4002 passed, 21 skipped, 0
    failed.**
  - Python 3.13.12: all 55 files exit 0. **4002 passed, 21 skipped, 0
    failed.**
  - There is no failure, so there is nothing to compare with `main`. The
    re-review's `main` run had no failures either.
- **Guards.**
  - `ruff check .` is clean.
  - `repo_map.py check` reports the map current (341 nodes) before this file
    was added.
  - `vocab_report.py check` reports the report current.
  - `docs/backtest-baseline.json` is unchanged against `main`.
- **Engine.**
  - `git diff d555b2a..HEAD -- tracker/` touches only `tracker/api.py`:
    - The three kill phrases gain a full stop.
    - There is a new `SCAN_NOTHING_DONE_BARE = "Nothing Done"`.
    - `vocab.scan` gains `nothing_done_bare`.
  - Across the whole branch against `main`, `runner.py` changes only three
    words and the `code` field of the final line.
  - Nothing changes sorting, filing, routing, locking, what is written to
    client folders or what is written to the record. **Confirmed.**

## Per-item verdicts

| Item | Verdict | Evidence (run) |
|---|---|---|
| N1 banner sentences | **Fixed** | See the table below. No drawn line holds a path, a backtick, "Clients", "missing", "lock" or an engine sentence, for the asked return or for the other return |
| N2 PROMPT steps 11-13 | **Fixed**, with one wording nit (NEW 1) | See the step 12 and step 13 notes below. Step 11 is unchanged and fine |
| N3 TSV rows | **Fixed** | See the TSV note below |
| N4 kill texts | **Fixed** | See the kill-text note below |
| N5 README and runbook | **Fixed in the runbook, not fully in the README** (NEW 2) | See the README and runbook notes below |

### N1: what the banner drew

Each row is one real run, drawn by the page's own code. A bullet means the
line for the household's other return.

| Case | Banner lines drawn |
|---|---|
| Client folder renamed, both returns fail with `client-folder-missing` | `Sort Failed: Folder Not Found`<br>`• Test Household 2025 Smith TY2025: Sort Failed: Folder Not Found` |
| Lock held (real `lock-held` on both returns; the engine holds the whole household back) | `Nothing Done: Another PC Sorting.`<br>`• …: Another PC Sorting` |
| Two returns broken different ways: asked return `crashed:PermissionError`, other return `lock-held` | `Sort Failed: Unexpected Error`<br>`• …: Another PC Sorting` |
| The same two, the other way round | `Nothing Done: Another PC Sorting.`<br>`• …: Sort Failed: Unexpected Error` |
| Unknown code `weird-new-code`, and `crashed:*` | `Sort Failed: Unexpected Error` |
| `household-paused` | `Sort Failed: Two Years Open` |
| Asked return skipped as `inactive` or `no-room` | `Nothing Done` |
| Other return skipped as `inactive` or `no-room` | No line |

In all of these the engine's long sentences were given deliberately, holding
`C:\Users\...\Clients\...`. None of them reached a drawn line.

- **A timed-out run.** It gives no runs. `passEnded` shows only the shell's
  kill line (see N4).
- **A failed run has no warnings.** The pre-check returns before
  `check_rules`, so the raw `other.warnings` loop that was left in place draws
  nothing for a failed or held-back return.
- **The new word "Nothing Done".** It is two words, in Title Case. It is
  flagged for Jason in `shell-fixpass.md` and in the TSV, but not in
  `HANDOFF.md`'s "Open for Jason" list (NEW 3).

### N2: step 12 run for real

1. The baseline scheduled pass exits 0, and `last_pass.ok` is true.
2. The folder chosen in step 2 was renamed to `Clients-away`. The scheduled
   pass then exits 1.
3. After renaming it back, `list` gives `last_pass.ok: false` and `level:
   err`. That is exactly the condition for `syncSortNotice` and for the side
   panel's "Sort Failed" line.
4. A further scheduled pass exits 0 and `ok` is true again, so the notice
   clears as the step says.

"Repair Schedule" is the Tools menu's real label (`main.js:498`).

### N2: step 13 run for real

- By step 13, the step 12 clearing run has sorted every household, so every
  household has a client folder. Even the one that was never sorted had one
  afterwards, so the "sorted once" condition always holds by then.
- Renaming the inner `Clients\Test Household` and then running `run-now`
  exits 3 with `client-folder-missing` on both returns.
- The first banner line is exactly "Sort Failed: Folder Not Found".
- A CPA can follow both steps.

### N3: the TSV

- Nine rows say "Approved by Jason, ruling 30".
- "Bad Year" says "Working word (ruling 18a), Jason may change".
- `name_requests` and `pick_request` still cite rulings 18/18a/23. That is
  correct, because ruling 23 is theirs.
- The word counts match.

### N4: the kill texts

- Every phrase ends in a full stop, and each is five words or fewer:
  - "Sort Stopped: Ran Too Long." (5)
  - "Change Stopped: Ran Too Long." (5)
  - "It May Be Partly Done." (5)
  - "Stopped: Ran Too Long." (4)
  - "It Was on {household}: {name}." (5 with the fills)
- All are in Title Case.
- `main.js` defaults match `api.py` word for word.
- `test_single_source` pins the joined lines, and it passes on both
  interpreters.

### N5: the README and the runbook

- **The README sentence** now reads correctly: "A household's name is unique
  across both trees…". "The app is…" follows as its own sentence.
- **The doubled "a"** in the runbook is gone.
- **"Advanced" switch:** it replaces "Routing rules fold", and it is the real
  control (`app.js:2949`).
- **The runbook's "card":**
  - Every remaining use is the graphics card, the pinned `reminder.py` quote
    ("open it from its card", line 1854), or the one line that explains it
    (line 1168).
  - `--discard` also matches a search for "card"; it is not the word.
- **No `test_single_source` violation.** It is green.

## NEW findings

1. **PROMPT step 13 names the other return's line in a shape the screen does
   not use.** Should fix (one line).
   - The step says each other return gets "{Return}: Sort Failed: Folder Not
     Found".
   - The page draws `• {household} {year} {return}: Sort Failed: Folder Not
     Found`, with a bullet, the household and the year before the return
     name. It uses the engine label (`layout.label_for`), for example
     `• Test Household 2025 Smith TY2025: …`.
   - A careful CPA could mark that as a FAIL. Either change the step's words,
     or (JASON) draw the other return as "{Return} ({Year})", as the
     re-review suggested. The fix pass kept the engine label.

2. **The README still uses "card" for the old cards in two places.** Should
   fix (two words).
   - `README.md:363`: "The app's **Reminder** card is where that draft is
     read". The runbook now says "side sheet".
   - `README.md:486`: "from the parked K-1's card in one step". The runbook
     now says "row".
   - The fix pass also lists `test_single_source` as the pin for N5, but no
     test pins the absence of "card". That is a documentation claim only.

3. **"Nothing Done" is not on HANDOFF's "Open for Jason" list.** Should fix.
   **JASON.**
   - It is a new, unapproved word: two words, Title Case, from
     `scan.nothing_done_bare`.
   - It is flagged only in `shell-fixpass.md` and the TSV. Add it to
     `pilot/HANDOFF.md`'s open list so Jason sees it before the pilot.

4. **"Another PC Sorting" is drawn when the lock holder is this PC.** Note.
   **JASON.**
   - In the new test and in my probe, the lock is held by the same machine's
     own process. That is the usual case: this PC's scheduled pass holds the
     household while a person presses Sort. Both still say "Another PC
     Sorting".
   - Ruling 29 approved the word for "lock held elsewhere", so the build
     follows the ruling. Jason may want a word that is true for both, for
     example "Another Sort Running".

5. **Small punctuation differences inside the banner.** Note.
   - The asked return's lock line ends in a full stop: "Nothing Done: Another
     PC Sorting.", from the older `Nothing Done: {why}.` pattern.
   - The bare "Nothing Done" has no full stop, and neither do "Sort Failed:
     …" or the other return's "…: Another PC Sorting".
   - This is harmless, but it is inconsistent.

6. **"Repair the Schedule" in engine sentences against the menu's "Repair
   Schedule".** Note. This predates fix pass 2.
   - `runner.OLD_JOB_ROOT` and three `after_install.py` sentences tell a
     person to "press Repair the Schedule".
   - The Tools menu item reads "Repair Schedule". The schedule dialog's own
     label (`api.SCHEDULE_REPAIR_LABEL`) is "Repair the Schedule", so the
     sentence can be found, but the words differ from the menu.

Hygiene: no history was rewritten, and nothing was force-pushed. This file is
the only change in this commit, so it alone will make `repo_map.py check`
stale. `update` was not run, as instructed.
