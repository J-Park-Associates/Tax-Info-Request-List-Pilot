# Prompt for a local Claude Code session on the Windows office PC

Paste everything below the line into a fresh Claude Code session opened in the
extracted pilot folder (the ZIP of `main`, or a `git clone` of it). Use Sonnet
at the default effort.

---

You are running the Windows check of the Tax Document Tracker Pilot 0.2 app
shell on this Windows PC. I am a CPA, not a programmer: explain in plain
English, lead with the answer, and state the root cause in one sentence when
something breaks. Made-up documents only; never touch real client folders.

Hard rules: no generative AI reads any client document (the sample files are
made-up and you only run the app on them; you do not read their contents);
nothing is sent anywhere; do not edit any file under `tracker/`, `app/` or
`tests/`. You may write only the results file named below.

Read first (targeted, do not read whole files): `CLAUDE.md`, `pilot/HANDOFF.md`
('Open for Jason'), and `pilot/wintest/PROMPT-shell.md` (the numbered checks).
Use `python tools/repo_map.py show <file>` if you need a module's node.

Do this, one step at a time, telling me before anything that needs my hands:

1. Run the tests in parallel, each file in its own process, exactly as
   `pilot/wintest/PROMPT-shell.md` ('The tests') says, using
   `pilot\wintest\run_checks.ps1`. Report PASS/FAIL per file and the installer's
   SHA-256. If a tool is missing, print the one command that installs it and
   stop for me.
2. Make the sample data with `pilot/wintest/make_samples.py`
   (`%USERPROFILE%\PilotTest\Clients`), install the built installer, and launch
   the app. Use a screenshot for each check you can do yourself.
3. Work through the 'By hand' list in `PROMPT-shell.md`, in order. For each
   number: do it yourself where you can (launch, click, screenshot, time the
   Overview counts, rename a folder, run the scheduled pass); where it needs
   me (turning on a Windows contrast theme, dark mode in Settings, looking at
   how it renders), tell me exactly what to click, wait, then ask what I saw.
   Record PASS, FAIL or SKIPPED with one sentence each.
4. Report the numbers I care about: how long Overview took for the largest
   Clients folder tried (budget 3 s for 750 returns; the cloud measured 6.7 s),
   and whether the status 'Email or Zip' shows whole (no ellipsis) at 1100 px.
5. Write `pilot/wintest/RESULTS-shell.md` from `pilot/wintest/RESULTS-TEMPLATE.md`:
   what passed, what failed with the exact steps to reproduce, screenshots'
   file names, and the installer SHA-256. Do not fix any failure. Do not commit
   or push. Tell me the file's path and stop.

If a step fails, state the root cause in one sentence, note it, and continue
with the next step unless it blocks. At the end give me a short list: what to
fix, what needs my decision, and whether the build is ready to tag `pilot-0.2`.
