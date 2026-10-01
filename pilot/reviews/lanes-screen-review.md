# Screen and check-scripts review - P199, P200 and their seams

Branch `claude/zen-easley-93548b` at c7eed52; diff `4534b30..c7eed52`. Reviewer did not build or specify this work. Nothing edited, committed or pushed.

## Verdict

One MUST: a household Sort that filed documents into a **different** return of the household now says "Nothing to Sort". Everything else matches the SPECs. The other findings are one SHOULD and NITs.

## MUST

**M1 - "Nothing to Sort" is shown even when the Sort filed files into another return of the household.**
`app/renderer/app.js:2173` checks only the asked return's own counts (`run.filed`, `run.review`, `run.waiting`, `run.file_errors`).
- The engine sorts the household's one inbox across every open return and counts per return. See `tracker/runner.py:1462-1468`, where `run.filed`, `run.review` and `run.waiting` are each that return's own, and `:2135`/`:2138`, which sum them across runs.
- `asked` is whichever return is active (`app.js:2252`). The other returns' successes are never added to `also` (`app.js:2151-2158`), because only failures, locks and warnings are.
- The result: on a household with a 1040 and a 1065, a Sort pressed while the 1065 is active can file 5 documents into the 1040 and still say "Nothing to Sort". Before P199 it said nothing (cls "ok"). The new words are therefore false in a common case. Jason chose answer A because a person "could not tell a Sort that ran", and this now tells them the wrong thing.

Fix, in `scanSummary`:
```js
const all = [run, ...others];
const quiet = all.every((o) => !o.filed && !o.review && !o.file_errors.length && !o.warnings.length && !o.cancelled);
const waiting = all.reduce((n, o) => n + (o.waiting || 0), 0);
if (quiet && !also.length) {
  return { text: waiting ? fill(words.nothing_done, { why: fill(words.syncing, { n: waiting }) }) : words.nothing_to_sort, cls: "warn" };
}
```
Add a case to `tests/test_shell.py::test_a_sort_that_finds_nothing_to_do_says_nothing_to_sort`: `scanSummary(run({}), [run({ filed: 3 })], "")` must not say "Nothing to Sort" and keeps cls "ok". Name it as the claim, for example `..._only_when_no_return_of_the_household_received_anything`. Also fix the wording row's "Where" note in `pilot/wording-shell.tsv:324`, which currently reads as if the asked return alone decides.

## SHOULD

**S1 - The app-close step cannot see an app running from the Claude package's private copy.**
`pilot/wintest/run_checks.ps1:260` builds `$appExes` only from the real `%LOCALAPPDATA%\Programs\...` folder.
- S3 (end of PROMPT-0.3.md) is still unconfirmed. If the program ever lands in the redirected copy (`%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\Programs\...`, P193), `Find-AppProcess` matches nothing. The script then records "the app was not open", and the silent install aborts with exit 5 as in N7, behind a misleading INFO line.
- Fix (still only the installed exe, still never forced): also add that redirected path for both product names to `$appExes`. Alternatively, when the install exits 5, have the Record line say "the app may still be open from another folder; close it (File > Exit) and run again".
- Add one line to the P200 note in `pilot/wintest/PROMPT-0.3.md:98-102`.

## NIT

- **N1** `run_checks.ps1:216`: the stop message prints `$t.py` even when `$t` already ends in `.py` ("test_x.py.py"). Fix: build the message from the same `$tried` list `Resolve-TestFile` uses. Either return it alongside, or say "looked for it as typed, with .py, and under tests\".
- **N2** `run_checks.ps1:212-219`: the same file named twice (`-Tests test_api,tests\test_api.py`) starts two processes writing one `pytest-test_api.txt`. Fix: skip a name already listed, with `if ($files -notcontains $file) { $files += $file }`. Compare the resolved full path (`(Resolve-Path $file).Path`).
- **N3** `run_checks.ps1:83-95`: `Resolve-TestFile` accepts any existing file, so `-Tests README.md` runs pytest on it. Fix: require the found name to end in `.py`, or the run stops with the same sentence.
- **N4** `app/renderer/index.html:307` `#sc-next`: the time in the next-run sentence is not `tabular-nums` (the standard: dates and times). Fix: add `#sc-next` to the tabular list at `app/renderer/shell.css:21`.

## Checked and found right

- **Columns.**
  - Every firm list uses fixed tracks (`shell.css:547`, `:556`), and the date starts at its column's left edge (`:561-564`). The return pages are untouched (`pagesListOf` gives "" for them).
  - The drag sets the column's own width from where it began (`pages.js:816-833`), so the dragged edge follows the pointer and only later columns move.
  - Ctrl+Shift+Arrow, double-click to fit, focus ring, High Contrast and motion are unchanged.
  - 1100px: Overview and Reminders are 832px, Needs Review is 840px (842px with a card's margins), all at most 843px (the test holds).
  - Card rows line up with the header row (24 + 1 + 8 px inset, against 32px, unchanged from before).
- **Order kept across a restart.**
  - `pagesStoredOrder` accepts only a list the app draws, a column of it that has a word, and a direction of 1 or -1. Junk, the old `name`, Households' wordless `end`, direction 2 and an array all fall back to the usual order (the test covers each).
  - No other code still treats `pagesOrder` as the old in-memory object.
  - The window's close handler flushes storage (`main.js:739`), so the order is written before the app exits.
- **Bullets.** `passEnded` keeps the bullet (`app.js:2318`). `sortReturnSaid` says year, taxpayer and form, and falls back to the label for a return the list does not hold. PROMPT-shell step 13 agrees.
- **Clock style.**
  - `scheduleClock` rewrites only a trailing HH:MM through `pagesTime`.
  - `tracker/scheduling.py` and the task XML are not in the diff, and `_next_sort` still reads the engine's untouched sentence.
- **Words.** "Nothing to Sort" is Title Case, 3 words, and has its own `pilot/wording-shell.tsv` row. "Nothing Done: 1 Still Syncing." reuses approved keys (5 words). This is consistent with P134 and P169's "Nothing Done".
- **The check script.**
  - It never forces: there is no Stop-Process, .Kill, taskkill or /FORCECLOSEAPPLICATIONS, and the test pins this.
  - It closes only processes whose Path is exactly the installed exe, and stops with one sentence.
  - Every test process is waited for and recorded before the build.
  - It accepts bare names, `.py` names and `tests\` or `tests/` paths.
  - It is PowerShell 5.1-safe: no `&&`, `??` or ternary; the `if`-expression assignment is valid in 5.1; `.Count` on a `$null` return is 0.
  - It never starts the app; step 8 only says how (P193 ruling 3).
- **The flake fix.** The fixed 100ms and 60ms waits are replaced by a pending counter over `whenReady`, the fake child and `fs.promises`, drained by `setImmediate` turns. No longer sleep was added.
- **Tests.** The tests are named as claims, and no dead code was found.
- **Docs.** SPEC-lists, SPEC-firm-columns, the runbook, DECISIONS P139/P199 and the curated map are all updated.

## Runs (each file its own process, at most two at a time per interpreter)

| File | Python 3.11.15 (scratchpad venv, hash-checked locks) | C:\Python314 |
|---|---|---|
| tests/test_shell.py | 169 passed in 37.24s | 169 passed in 32.09s |
| tests/test_shell_menu.py | run 1: 34 passed, 3 skipped in 6.47s; run 2: 34 passed, 3 skipped in 3.70s; run 3: 34 passed, 3 skipped in 3.82s | 34 passed, 3 skipped in 8.04s |
| tests/test_pilot.py | 28 passed in 5.88s | 28 passed in 6.97s |
| tests/test_pilot_installer.py | 20 passed in 0.38s | 20 passed in 0.29s |
| tests/test_single_source.py | 179 passed in 39.58s | 179 passed in 47.63s |
| tests/test_repo_map.py | 80 passed in 22.99s | 80 passed in 24.49s |
| tests/test_api.py -k "title_case or vocab or menu or scan" | 28 passed, 416 deselected in 54.18s | 28 passed, 416 deselected in 36.65s |

- `python -m ruff check .`: All checks passed!
- `python tools/repo_map.py check`: Map is current (421 nodes, generated 2026-10-01). It also warned that the working copy of `docs/repo-map.curated.json` has CRLF line endings; that is a warning only, since the map hashes what Git commits (LF).
- `run_checks.ps1` was not run, as instructed.
