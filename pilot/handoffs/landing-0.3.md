# Handoff: the Pilot 0.3 landing (2026-09-30)

## Done
- Pull request #19 (`landing/pilot-0.3`, head `a023b7b`) merged into `main` with a
  merge commit, `76f6e30`. The merge's content is identical to the tested head
  (`git diff a023b7b 76f6e30` is empty).
- It carries five branches, merged in this order: `claude/wincheck-shell-results`,
  `claude/email-zip-tag`, `claude/wincheck-fixes`, `claude/firm-cache` and
  `claude/column-order`, plus the landing's own fixes `9b4b5ee` (the review's four
  MUSTs) and `a023b7b` (the schema pin in `tests/test_filer.py`).
- Whole suite once on the office PC (Windows 11), under Python 3.14 and 3.11:
  4119 passed, and 1 failed on each. The failure was the schema pin, fixed in
  `a023b7b`; `tests/test_filer.py` then passed on both (402 passed).
  ruff, the repo map check and the vocabulary check are all clean.
- GitHub Actions is disabled for the repository, so no CI ran. Jason chose to land
  on the office PC's pass (P184).

## Left, in order
1. **Done 2026-09-30 (P205, pull request #20, e234c54).** The rename and version lane: P155 ("Tax Document Console" everywhere a
   person reads the name; the badge reads "Pilot 0.3"; "Tracker" on screen becomes
   "App"; internal names stay) and P140 (version 0.3). It includes the job in
   `tracker/after_install.py` that carries settings, data and the schedule over.
   Write the SPEC first, then a builder and a separate reviewer. Branch
   `claude/rename-0.3` (which already holds P184).
2. Then the Windows check of 0.3, in the "Pilot 0.3 Windows check (artifact)"
   session.
3. Later: the firm-cache follow-ups (fill the cache at a pass's end; split
   test_api), the P160 fold of the original tracker SPEC, the P165 draft of the
   licence terms, the P166 SPEC for the weekly key, lane 4's NITs (`_One` as a
   NamedTuple, one sort order in `_links_from`), and the NIT for `suggestion_short`
   in the stub.
4. Cleanup (Jason's say): the `.venv311` folders in the ZIP copy, and
   `%USERPROFILE%\PilotTest\Clients-750` and `settings-750`.

## Files the next session needs
`pilot/DECISIONS.md` (P140, P155, P181-P184), `pilot/wintest/RESULTS-shell.md`
and this file.
