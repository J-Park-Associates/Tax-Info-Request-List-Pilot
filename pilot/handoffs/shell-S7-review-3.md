# Shell S7 - review 3 (after rebuild 2)

Reviewer: a separate agent that built neither S7 nor its rebuilds. Branch
`claude/shell-s7-tooltips` at `b56de1d`, diff `7ff3394...HEAD`. No code was
changed; the only changes are this file and the refreshed repository map.

## Verdict

No findings. Review 2's F1 is fixed, and its "upper-case script tag" note is
closed by the `re.I` flag. The rebuild stayed in scope.

## What was checked

**History.** `git log --oneline 7ff3394..HEAD` is one commit, `b56de1d`.
Review 2's commits `c98c5e0` and `7ff3394` are ancestors of HEAD, and the
earlier history (`99defa4`, `99aba3e`, `cc7b66e`, `02cc36a`, `430aa27`,
`976778f`, then S3's `afd566d` and below) is unchanged. The replaced commit
`3ce4561` had parent `7ff3394`, and it differs from `b56de1d` only in
`docs/repo-map.json` and `docs/repo-map.md`. So the force-push rewrote the
builder's own commit and nothing else.

**Scope.** `git diff 7ff3394...HEAD --stat` touches only these files:
- `pilot/handoffs/shell-S7.md`
- `pilot/handoffs/shell-S7-rebuild-2.md` (new)
- `tests/test_shell.py` (one line: `re.I` added to the script-source
  `re.findall`)
- `docs/repo-map.json` and `docs/repo-map.md` (regenerated: the new node,
  and new hashes for the two changed files)

**Handoff against the code.**
- In `tooltip.js`, `TIP_DELAY_MS = 300`. The middleware includes
  `FloatingUIDOM.hide()`, and `hideTip()` runs on `referenceHidden`.
- `shell-S7.md` now says the following, and each point matches the code:
  - "Left for S6" says 300 ms (ruling 7, replacing SPEC 8.5's 500).
  - It says a tip hidden by scrolling returns only on the next hover or
    focus.
  - The decision row names `hide()`.
  - "For Jason" says the tip is HIDDEN, not clipped, and stays hidden until
    it is shown again.
- I searched every `pilot/handoffs/shell-S7*.md` file for 500, clip, hide
  and scroll. No statement contradicts the code.
- Two passages are history rather than contradictions:
  - Rebuild 1's line "This supersedes the S7 handoff's 'hover delay stays
    500 ms' ..." quotes lines that are now gone.
  - Point 1 of "What was done" in `shell-S7.md` lists `offset`, `flip` and
    `shift` but not `hide`. It describes the first build, and the decision
    row and "For Jason" cover `hide`.

**The case-insensitive check.** I made a scratch copy of HEAD outside the
repository and added `<SCRIPT SRC="https://cdn.example.com/x.js"></SCRIPT>`
to `index.html`. With `re.I`,
`test_the_loading_order_is_the_specs_and_the_csp_is_unchanged` fails at the
count assertion. With `re.I` removed on the same copy, it passes. So the flag
is what catches the tag.

**Vendored files and app code are untouched.**
- `git diff 99aba3e HEAD -- app/` is empty.
- `git diff cc7b66e...HEAD -- app/renderer/vendor app/renderer/tooltip.js`
  shows only rebuild 1's `tooltip.js` change (10+/4-). It shows nothing under
  `vendor/`.
- The SHA-256 of both UMD builds and of the three licence files matches the
  vendor README (`65940d86...`, `61a46f94...`, `0e4c9a9b...`).

**Gate.** Each file ran in its own process:

| Python | `test_shell` | `test_repo_map` |
|---|---|---|
| 3.11.15 | 37 passed | 80 passed |
| 3.13.12 | 37 passed | 80 passed |

`ruff check .` passes. `repo_map.py check` says the map is current (290
nodes).

## Findings

No findings.
