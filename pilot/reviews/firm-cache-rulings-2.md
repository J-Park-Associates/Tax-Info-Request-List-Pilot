# Orchestrator rulings on the lane 1 re-check (after 92729ef)

Re-check: `pilot/reviews/firm-cache-recheck.md` - (1) PASS, (2) FAIL with MUST-R1, (3) PASS, NIT-R1. Ruled 2026-09-30.

| Finding | Ruling |
|---|---|
| MUST-R1 - the status-page exclusion (`tracker/firm_cache.py:237`) applies in the client tree, at any depth and to folders, so a client drop named "Status Report.html", or a folder of that name holding a W-2, is invisible to the cache (whole walk held=1, cache held=0) | **Fold.** Exclude only the file the tracker itself writes: a regular file named exactly as the tracker names it, directly inside a return folder of the private (`J Park & Associates`) tree. Never in the client tree, never a folder, never at another depth. Add both cases (a file and a folder of that name in Drop files here) as tests that fail on 92729ef. |
| NIT-R1 - `_README.txt` and reminder drafts are hashed by name at any depth, so a client's own file of that name is hashed too | **Fold.** Match the tracker's own files only where the tracker writes them (the inbox's `_README.txt` directly in Drop files here; drafts where the reminder module writes them). A client file of the same name elsewhere is judged like any other file. Test it. |

One fold commit, with the re-check and this rulings file. Rerun tests/test_firm_cache.py on both interpreters, and tests/test_api.py on one (it passed on both at 92729ef and the fold touches only the cache module - state that). Report pass lines and exit codes. The reviewer then re-checks MUST-R1.
