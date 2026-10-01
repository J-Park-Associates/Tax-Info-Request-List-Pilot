# P203 review - the minimum size is the page's (SPEC-min-page-width)

Reviewer: separate agent (did not write the SPEC or build). Reviewed 2026-10-01 04:10 PDT.
Diff: `git diff 4b55bc4..HEAD` on `claude/min-width` (HEAD df0e610; build 6bbda44).

**Verdict: no MUST. Ready to fold the SHOULD and NITs.**

## R1-R3 against the SPEC

- **R1 - met.** `app/main.js:715` `useContentSize: true` is in the one `BrowserWindow` (the only one in app/), beside width 1400, height 900, minWidth 1100, minHeight 700 (716-719). Comment 710-714 gives the reason.
- **R2 - met.** `tests/test_shell_menu.py:618-626` runs the real `app/main.js` under node through `_run` (harness line 301 passes `REPO/app/main.js`; the Electron stand-in records the constructor's options at line 187). It asserts `useContentSize is True`, so it fails without the line. It ran (not one of the 3 skips, which are the file's symbolic-link tests).
- **R3 - met.** `pilot/SPEC-firm-columns.md:102-103` adds exactly the ruled sentence. No other SPEC or runbook wording changed, as ruled.

## Side effects of useContentSize (Electron on Windows)

- Nothing else reads or sets the window's size: grep of app/ for getSize, getBounds, setSize, setBounds, getContentSize, setContentSize, setMinimumSize, getNormalBounds, workArea, zoom finds only `main.js:718-719` (minWidth/minHeight). No saved or restored window size or position exists.
- The tour (`app/renderer/tour.js:95-96`) sizes against `window.innerWidth/innerHeight`, which is the page; it now gets the intended 1100 at the minimum. Dialogs are Electron's native message boxes, not sized against the window.
- No SPEC or test asserts the old outer sizes. SPEC-shell's 1100 x 700 and 1400 x 900 (lines 315, 403, 1851, 1933) are page budgets and now hold as written.
- On-screen: at 100% the window grows by its frame, about 16 px wide and about 39 px tall (title bar plus bottom border), so the default is about 1416 x 939. A 1920 x 1080 display at 100% has a work area of about 1920 x 1032: fits. This PC: 2560 x 1440, work area 2560 x 1392, 96 DPI (100%): fits.

## Findings

- **SHOULD** `pilot/DECISIONS.md:198` - P203's Status still reads "SPEC written; building." The build (6bbda44) is merged on the branch. Fix: change to "Status: built (`6bbda44`), reviewed (no MUST), its findings folded; lands with the hands-on result." (the P202 row's wording), once the fold is in.
- **NIT** `app/main.js:714` and `pilot/SPEC-min-page-width.md:15` and `:21` - "16 px wider" names only the width; Windows also adds the title bar and bottom border, so the window is about 39 px taller too. Fix: main.js 714 "The window is drawn larger than the page by its frame (about 16 px wide, 39 px tall at 100%)."; SPEC 21 "...the window itself is a little larger than before (its frame: about 16 px wider and 39 px taller) at its smallest and by default."
- **NIT (pre-existing, not this SPEC)** - on a 1920 x 1080 laptop at 125% scaling (work area about 1536 x 824 in page units) the default 900-tall page already did not fit before P203; it now overhangs by about 39 px more. At 150% the 700-tall minimum (now about 739 tall outside) exceeds the about 688 work area. The office PC is unaffected. Fix: none in P203; if Jason wants it, a later SPEC clamps the first-open size to the screen's work area (`screen.getPrimaryDisplay().workAreaSize`).
- Results sheet (`pilot/wintest/RESULTS-0.3-followup.md:29-37`): states only what was shown (window 1100, page 1084, scrollbar); P202 marked NOT VERIFIED with the reason; removing the "1100 px not checked" line is correct because it was checked (and failed). No finding.

## Dead code

None in the changed lines (one option, one comment, one test; no new names).

## Runs (each file its own process)

| File | Python 3.11 (`pl\v311`) | Python 3.14 (`pl\v314`) |
|---|---|---|
| tests/test_shell_menu.py | 35 passed, 3 skipped | 35 passed, 3 skipped |
| tests/test_shell.py | 173 passed | 173 passed |
| tests/test_single_source.py | 179 passed | 179 passed |
| tests/test_repo_map.py | 80 passed | 80 passed |

- `python -m ruff check .`: All checks passed!
- `python tools/repo_map.py check`: Map is current (430 nodes, generated 2026-10-01). Exit 0.
- Working tree clean; nothing edited, committed or pushed.
