# Review: SPEC-email-zip-tag (P116, built as P125), lane 2

Reviewer: a separate agent (did not build it or write its SPEC). Written 2026-09-30 00:12 PDT.
Reviewed: `claude/email-zip-tag` in `C:\Users\User\pl\tag`, commits f16aacb and a2eb656 on main 877c7a2
(`git diff 877c7a2..HEAD`). Not committed; nothing in the worktree's tracked files was edited.

Verdict: **no MUST.** The change does what P116 and the SPEC say and nothing more. Two SHOULDs, four NITs.

## Findings

### SHOULD-1: a keyboard user never sees the tag's words
- `app/renderer/pages.js:287` puts the tip on the `.row-status` span. Rows are `role="option"` and the
  keyboard moves through them with `aria-activedescendant` on the list (`pages.js:297-305`), so focus never
  lands on that span. `tooltip.js:127-133` shows a tip only on `focusin` of the element that has it, so the
  tooltip never shows from the keyboard. The row's `aria-description` (`pages.js:274`) carries only the
  step words, so a screen reader never hears "Came in Email or Zip" either.
- This gap was already there for every cut status. P116 makes it matter more: SPEC ruling 3 says the tag
  alone "could be misread", and the global Fluent 2 rule asks for full keyboard use.
- The SPEC says "one hover away" and does not claim keyboard, so this is not a SPEC breach.
- Fix (smallest): in `pagesRow`, when `tip` is set, add it to the row's description:
  `"aria-description": [words, tip].filter(Boolean).join(", ") || undefined` (compute `tip` before `h("div", ...)`).
  Assert it in the new `test_shell.py` test (`node.getAttribute("aria-description")` contains the tip).
  A visible tip on keyboard moves (`showTip` on the active row's `.row-status[data-tip]` in `pagesActivate`
  while the list is `:focus-visible`) is the fuller fix and could be its own SPEC. The orchestrator rules.

### SHOULD-2: no test proves the real pages pass the reason code
- The new test `tests/test_shell.py:999-1017` calls `pagesRow` directly with `reason` set.
- No test checks that `pagesNeedsReview` (`pages.js:524`, `reason: file.code`) or `pagesReturnGroups`
  (`pages.js:720`, `reason: entry.code`) set it.
  - Delete either `reason:` and every test stays green.
  - The tooltip then goes silently (the row falls back to `setTipIfCut`), and so does the loud
    `reason_tips` failure. This is the silent skip the project's rules forbid.
- Fix: in `test_a_returns_needs_you_group_holds_parked_files_then_moved_then_requests_then_the_buckets`
  (`test_shell.py:996`), return `one.reason || ""` too and expect `"opened-not-across"` on `zip.pdf`.
  In a `pagesNeedsReview` test (e.g. the one at `test_shell.py:1817`), assert that the `tips` recorder
  holds `["row-status ...", "Came in email or zip"]` for a parked `opened-not-across` file.

### NIT-1: two docs still call the old words cut
- `pilot/HANDOFF.md:52` and `pilot/SPEC-shell.md:1964` still say "Came in Email or Zip" "is cut in the
  160px status column". So does the note at `pilot/wording-shell.tsv:245` ("cut in the 160px column").
- On Windows they measure 131.2px and fit (reproduced below). They were cut only in the cloud's DejaVu Sans.
- Fix: word each as "cut in the cloud's font (fits on Windows, 131px)", or add "(in the cloud)".

### NIT-2: SPEC-shell 11.5 does not mention the new tip table
- `pilot/SPEC-shell.md:1575-1578` (the 11.5 intro) still describes one table: a short label beside each
  code's sentence. Only the table row (1591) names the tooltip.
- Fix: add one sentence: "A label shortened into a tag has its longer words in `reasons.REASON_TIPS`
  (`vocab.reason_tips`), shown as its tooltip every time (P116)."

### NIT-3: the builder's hand-back misstates two check results
- `pilot/handoffs/email-zip-tag-build.md:84` says "Map is current (345 nodes)". At HEAD it is 346 nodes,
  and `check` exits 0.
- It also reports `test_single_source.py` as passed. In this worktree that file exits **1** on both
  interpreters: 172 pass, then the decision-185 tripwire fires ("the suite reached a real place",
  `test_the_app_opens_one_window`, "open of the checkout's settings file").
  - The cause is not this change. The diff does not touch `app/main.js`, that test or the tripwire.
  - The same test exits 0 in a clean export of 877c7a2 that has no `.venv`. The worktree's own `.venv`
    probably lets `main.js` (its `SOURCE_PYTHON`, lines 34-36) start the real API against the
    checkout's settings path.
- Fix: none in this branch. The hand-back should report exit codes, not only pass counts. Worth a
  look before the daily whole-suite run, which runs from a checkout that has a `.venv`.

### NIT-4: the P125 row is out of order in the decision log
- `pilot/DECISIONS.md:121`: on this branch P125 (dated 2026-09-29) follows P114 (2026-09-30).
- Main's working copy and `claude/wincheck-shell-results` already hold P115-P117 and P140 at those
  lines, so the landing's combine will conflict here.
- Fix: none now. At the landing, keep both sides and put P125 after P116.

## What was verified (not taken on trust)

- **Scope.** The diff touches exactly the files the SPEC names (section 2), plus the docs of section 5
  and the regenerated map. `api.py` gains only the two lines at 1694-1695. `SHORT_REASONS` stays plain strings.
- **Every place the words live.** I searched the whole repo (`git grep -i`) for "Came in Email or Zip"
  and `opened-not-across`:
  - Code and tests: `reasons.py` 845 and 898, `test_reasons.py`, the `test_shell.py` stub.
  - Docs updated: HANDOFF, SPEC-shell 1591 and 1964, both PROMPT files, the wording TSV.
  - Left alone: history files (`shell-S4*.md`, `shell-ledger.md`). They record the past and stay.
  - `pilot/harness/stub.js:63` takes its words from `_vocab()`, so it needs no change.
- **The tooltip every time.**
  - `pages.js:284-288`: a code in `reason_tips` gets `setTip`, which clears `tipCut`, so the tip shows
    whether or not the tag is cut.
  - A code not in the table falls back to `setTipIfCut`.
  - A missing table throws `Error("reason_tips")` only for rows that carry a reason.
  - Keyboard: see SHOULD-1.
- **The file name stays plain text.** `nameLink` is unchanged. An email or zip has no `open_key` or
  `shown_key`, so `pagesFileLink` returns null (`pages.js:142-144`). Ruling 24 holds.
- **The fit, reproduced.**
  - Method: Playwright's Chromium headless shell 1223 on this PC. A 160px `display:block` span with
    `font-family: "Segoe UI Variable Text", ...`, 14px, weight 600, `nowrap` + ellipsis, as the app's
    `--font-ui`, `--fs-body`, `--fw-strong` and `.row-status` set them. Width is the text range's
    `getBoundingClientRect().width`; "cut" is `scrollWidth > clientWidth`.
  - Results, identical to the SPEC's figures:
    - "Email or Zip": 75.8px, not cut.
    - "Came in Email or Zip": 131.2px, not cut.
    - Cut: "Looks Like Wrong Document" 183.7px, "Names Another Household" 172.3px, "Claimed by Two Requests" 161.7px.
    - Every other `SHORT_REASONS` label fits. The next longest is "Expected Words Missing" at 155.3px.
  - The column is a fixed 160px track (`pilot-ui.css:26/45`, `shell.css:376`), with no padding on `.row-status`.
  - `RESULTS-shell.md:50` confirms that the Windows check skipped step 5, and `shell-S4-review-1.md:248`
    shows the "cut" came from DejaVu Sans.
- **The `reason_tips` key is built and used like the others.** It is `dict(reasons.REASON_TIPS)`, beside
  `"reasons": dict(reasons.SHORT_REASONS)`. It is read only by `pages.js`.
  - The Title Case test walks every drawn vocab word, so it covers the tip, and it passes.
  - The five-word test now walks `REASON_TIPS` (`test_api.py:8617`).
- **Standing rules and layers.**
  - No filing, moving, reading or sending path is touched.
  - `reasons.py` gains no import, and `api.py` already imported `reasons`.
  - `test_layers` passes.
- **Would the tests catch a revert?**
  - Reverting the words fails `test_reasons.py:235` and `test_api.py:8594`.
  - Reverting `pagesRow` to `setTipIfCut` only fails the new shell test: the tip is cut-only and there
    is no loud error.
  - Removing the `reason:` lines is not caught (SHOULD-2).
- **Dead code.** None: `cutTips` is used, and `tip` and `tips` are both read. ruff is clean.

## Tests and checks run by the reviewer

Each file ran as its own process, all in parallel. `.venv` is Python 3.14 and `.venv311` is Python 3.11.

| File | 3.14 (`.venv`) | 3.11 (`.venv311`) |
|---|---|---|
| tests/test_reasons.py | 58 passed, exit 0 | 58 passed, exit 0 |
| tests/test_api.py | 407 passed in 1003 s, exit 0 | 407 passed in 1408 s, exit 0 |
| tests/test_shell.py | 2 failed, 111 passed, exit 1 | 2 failed, 111 passed, exit 1 |
| tests/test_layers.py | 29 passed, exit 0 | 29 passed, exit 0 |
| tests/test_single_source.py | 172 passed, exit 1 (tripwire, NIT-3) | 172 passed, exit 1 (tripwire, NIT-3) |
| tests/test_repo_map.py | 80 passed, exit 0 | 80 passed, exit 0 |
| tests/test_vocab_report.py | 28 passed, exit 0 | 28 passed, exit 0 |
| tests/test_tripwire.py | 19 passed, exit 0 | 19 passed, exit 0 |
| tests/test_errors.py | 83 passed, exit 0 | 83 passed, exit 0 |

The two `test_shell.py` failures are the only failures, the same two on both interpreters:
`test_the_harness_stub_speaks_the_apis_vocabulary` and
`test_the_harness_stub_replies_have_the_shape_of_the_engines`.
- Here each fails with WinError 206.
- Both also fail on a clean export of main 877c7a2 (there with `BadZipFile`, since that export is not a
  git checkout), so they predate this change. The new code is not in their path.

Quick checks, on the branch:
- `python -m ruff check .`: All checks passed!
- `python tools/repo_map.py check`: Map is current (346 nodes).
- `python tools/vocab_report.py check`: Report is current (371 keywords, 66 unreached).

No MUST findings.
