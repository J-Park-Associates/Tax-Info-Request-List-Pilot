# Lane 2 build hand-back: SPEC-email-zip-tag (P116, built as P125)

Written 2026-09-29 23:59 PDT. Branch `claude/email-zip-tag` in `C:\Users\User\pl\tag`,
from `main` at 877c7a2. Pilot 0.3 (P140). No version number was touched.
Not pushed, no pull request, no rebase.

## Built

- The status for code `opened-not-across` now reads **"Email or Zip"**. Its
  tooltip always says **"Came in Email or Zip"**, whether the tag is cut or not.
  Every other status is unchanged: it shows its own words as a tooltip only when cut.
- The tip words are a new table, `tracker/reasons.py` `REASON_TIPS`, which the
  app receives as `vocab.reason_tips`. `SHORT_REASONS` stays plain strings.
- In `app/renderer/pages.js`, `pagesRow` looks the tip up by the row's reason
  code (`spec.reason`, set by `pagesNeedsReview` and `pagesReturnGroups`). If
  the table is missing, the row fails loudly with `Error("reason_tips")`.
- The file name stays plain text (ruling 24). The side sheet keeps the tag.

## Words, decisions, owner questions

- Words: Jason's working words, "Email or Zip". No owner question: they fit
  with 84px to spare.
- Decision taken: **P125** (written in `pilot/DECISIONS.md`). P126 and P127
  were not used.
- How the fit was proven: measured in Chromium 152 on this PC, in
  "Segoe UI Variable Text" 600 14px, in a 160px `nowrap` box. The tag is
  75.8px and not cut. Details are in SPEC section 4.
- **Finding (no change made):** on Windows the old words "Came in Email or Zip"
  measure 131.2px and also fit. The "cut" was only ever seen in the cloud's
  DejaVu font, and the Windows check skipped step 5. Three other labels *are*
  cut on Windows (each already has its full words as a tooltip):
  - "Looks Like Wrong Document": 183.7px
  - "Names Another Household": 172.3px
  - "Claimed by Two Requests": 161.7px

  Worth telling Jason. Nothing here depends on it.

## Exact lines changed in tracker/api.py (for the landing's combine with lane 3)

Only two lines were added, after line 1693 (`"reasons": dict(reasons.SHORT_REASONS),`) in `_vocab()`:

```
        # The words a shortened label stands for, its tooltip every time (P116).
        "reason_tips": dict(reasons.REASON_TIPS),
```

No existing api.py line changed. The words themselves live in `tracker/reasons.py`
(`SHORT_REASONS` line 845, and `REASON_TIPS` after the dict).

## Files changed

- Code: `tracker/reasons.py`, `tracker/api.py`, `app/renderer/pages.js`.
- Tests: `tests/test_reasons.py`, `tests/test_api.py`, `tests/test_shell.py`
  (the stub gains `reason_tips` and a `cutTips` recorder; one new test; one expected tag).
- Docs:
  - `pilot/SPEC-email-zip-tag.md` (new);
  - `pilot/DECISIONS.md` (P125);
  - `pilot/HANDOFF.md` item 5 (answered);
  - `pilot/SPEC-shell.md` (11.5 row and the "Also open" paragraph);
  - `pilot/wording-shell.tsv` (two rows);
  - `pilot/wintest/PROMPT-shell.md` step 5 and `PROMPT-shell-local.md` item 4;
  - `docs/repo-map.curated.json` (the pages.js note), plus the regenerated map.
- Overlap note: lane 3 may also edit `PROMPT-shell.md` (A1, N2). Mine is step 5 only.

## Checks (both interpreters: .venv = Python 3.14, .venv311 = Python 3.11.15)

- Dead code: none in the changed files. `python -m ruff check .`: All checks passed!
- The SPEC's tests, run as separate processes:

  | Test files | 3.14 | 3.11 |
  |---|---|---|
  | `test_api.py` | 407 passed in 715 s | 407 passed in 1074 s |
  | `test_reasons.py`, `test_shell.py`, `test_layers.py`, `test_single_source.py`, `test_repo_map.py`, `test_vocab_report.py` | 2 failed, 478 passed | 2 failed, 478 passed |
  | `test_tripwire.py`, `test_errors.py` | 102 passed | 102 passed |

- The 2 failures on each interpreter are the known pre-existing
  WinError 206 harness-stub tests, which belong to lane 3:
  - `test_shell.py::test_the_harness_stub_speaks_the_apis_vocabulary`
  - `test_shell.py::test_the_harness_stub_replies_have_the_shape_of_the_engines`

  The stub passes `api._vocab()` on unchanged, so `reason_tips` needs no stub edit.
- `python tools/repo_map.py check`: Map is current (345 nodes).
- `python tools/vocab_report.py build` then `check`: Report is current (371
  keywords, 66 unreached). No change: that report covers routing keywords, not screen words.

## Commits

- `f16aacb`: P116/P125: the status "Email or Zip" is a tag, with "Came in Email or Zip" as its tooltip every time.
- The commit that adds this hand-back file.

## Housekeeping for the orchestrator

- **Stray folder:** a mistaken first command created an empty
  `C:\Users\User\Desktop\Tax-Info-Request-List-Pilot-main\.venv311` (Python
  3.11, no packages) at 23:26. The hook blocked me from deleting it; it is safe
  to remove.
- `.venv311` in this worktree is not in `.gitignore`. It was not committed.
