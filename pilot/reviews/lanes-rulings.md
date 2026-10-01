# Orchestrator's rulings on the complete review of the four lanes (2026-10-01)

The four lanes (P198 F6, P199 check notes, P200 check scripts, P201 cache fill) were combined on `claude/zen-easley-93548b` (`c7eed52`) before review, at Jason's word ("you must consolidate all of the work before reviewing. After reviewing, merge"). Two reviewers covered the combined branch side by side: the screen and scripts (`lanes-screen-review.md`) and the engine (`lanes-engine-review.md`).

## Screen and scripts

- **M1 ("Nothing to Sort" after a household Sort that filed into another return):** accepted. The notice is said only when no return in the pass filed, moved or parked anything; the fix and the test case are as the review gives them.
- **S1 (the close step looks only in the real Programs folder):** accepted. The close step identifies the app by its program file name wherever it is installed, including a `Packages\*\LocalCache\Local\Programs` copy, still never forcing and never touching another program.
- **N1-N4:** all accepted: no ".py.py" in the message; a name given twice runs once; `-Tests` takes `.py` files only; the schedule dialog's next-run time gets `tabular-nums`.

## Engine (no MUST)

- **SHOULD-1 (a pass a person stopped still runs the fill):** accepted, ruled here because Jason asked not to be asked tonight ("Dont ask im going to bed"): **Stop means stop.** A stopped pass skips the fill; the next Overview fills the cache as it did before P201. The SPEC's line saying otherwise is changed to say this, with the reason.
- **SHOULD-2 (schtasks has no time limit and runs at every start, inside the step's lock):** accepted. A 60-second limit; a query that times out is "cannot reach Task Scheduler" (`SCHEDULE_UNREACHABLE`), said and logged, never "the task exists".
- **SHOULD-3 (a one-household Sort pays the whole firm's cold fill):** accepted. A person's Sort fills only the households its pass touched; the scheduled pass fills the whole firm. The cache's own staleness rules cover the rest.
- **NIT-1 (the cache file is rewritten on every reply while nothing is kept):** accepted; write only when the head changes.
- **NIT-2 (an "access denied" query re-registers at every start with nothing logged):** accepted; the query's refusal (its exit code) goes to the error log once per start.
- **NIT-3 (a test named "...and says so" does not check the log):** accepted; it asserts the log entry.
- **NIT-4 (the fill can push a long pass past the task's limit before the log and page are written):** accepted; the fill runs after the pass's log line and page are written, so the record is never lost to the fill.

## On the folds (`a6c0d85`, `9c7d9a4`)

- M1 re-checked by the orchestrator: `app/renderer/app.js` 2177-2178 tests every return of the pass, and `test_shell.py -k nothing_to_sort` passes (2 tests).
- SHOULD-3 was built differently from the ruling, and the difference is accepted: the household a Sort just wrote is always too recent (under 5 s) for the cache to keep, so a person's Sort refreshes only changed households and only when today's cache is already current; otherwise the next Overview fills it. The scheduled pass fills the whole firm, as ruled.
