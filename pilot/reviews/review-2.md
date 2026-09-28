# Review 2 - Build C (#7, schedule setting)

Independent reviewer (Opus, built nothing), 2026-09-28. Verdict: no
blocking findings; approve after the should-fix items. C's five HANDOFF
deviations are all acceptable (choice types live in `settings.py` and are
re-exported by `scheduling` because `runner` may not import `scheduling`;
reworded last-pass sentences; `schedule_problem`; `vocab.schedule.loading`;
the runbook move step).

1. **should-fix** `tracker/scheduling.py:766,814` - the command line never
   calls `check_every`; `--every 45` writes `PT45M`. Fix:
   `repeat_minutes=check_every(ns.every)`, drop `type=int`; add a test beside
   `test_the_command_line_uses_the_one_start_time_check`.
2. **should-fix** `app/renderer/app.js:2456` - Off saved but the task delete
   failed shows the failure sentence in the ok colour. Fix:
   `result.after_install.exit === 0 && (result.installed || !result.enabled) ? "ok" : "warn"`.
3. **should-fix** `tracker/api.py:4799` - `next_run` promises a run on a
   computer that registered nothing. Fix: `next_run(chosen) if done.installed else ""`.
4. **should-fix** `tracker/after_install.py:1005` - moving the schedule to a
   computer whose setting is Off leaves no computer running it. Fix: refuse
   the move with "The schedule is off on this computer; turn it on with the
   Schedule button before moving it here."; add a test.
5. **nit** `tracker/after_install.py:375-386` - an `OSError` writing the
   choice escapes `run()` unrecorded. Fix: catch it and record a sentence that
   the settings file could not be written.
6. **nit** `tracker/runner.py:2218` - a refused saved choice is reported as
   the last-pass file being unreadable. Fix: show the refusal's own sentence.
7. **nit** `app.js` `openSchedule` - "Next run" goes stale while editing and
   the reply's `next_run` is not shown after Save. Fix: hide `#sc-next` on
   change; append `result.next_run` to the banner.
8. **nit** `app.js` `saveSchedule` - refresh `state` after a successful save
   so the last-pass line follows the new choice.

Merged tree (C onto main with A and B): only the generated map conflicted;
`index.html` keeps both sides. Python 3.11: 1577 passed, 8 skipped; the
failures are the OCR / Tesseract set that fails the same on `main` (P25).
Python 3.13 in the cloud lacks `pdfplumber`; the second interpreter is
re-run on the office PC.
