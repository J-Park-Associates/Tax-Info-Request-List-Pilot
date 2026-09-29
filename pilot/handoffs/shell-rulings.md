# Jason's rulings on the shell build (2026-09-29)

S6 (the join) applies these and logs each as a decision row (from P85).

| # | Question | Ruling | What S6 does |
|---|---|---|---|
| 1 | The tour and pilot scripts keep their own keydown listeners (a departure from SPEC 14.1's one-listener rule) | **Keep as built.** Accepted exception: the terms screen and the tour take over the keyboard on purpose; they act only while open. | Log the exception. No code change. |
| 2 | A text box being typed into shows no tooltip on focus (a departure from SPEC 8.5) | **Option b:** show the tooltip on keyboard focus for every control **except the search box**; hover still shows it everywhere. | Change `app/renderer/tooltip.js` (S3's file) so focus shows the tip for every control but the search box; update the SPEC 8.5 test in `tests/test_shell.py` to pin both halves; log the row. |
| 3 | Menu bar hidden until Alt | **Keep hidden.** | Log the row. No code change. |
| 4 | No error log named by the API | Save the failure to a fallback log; the screen says only "Tracker failed". Fallback log in a **local, non-roaming folder** (`%LOCALAPPDATA%\Tax Document Tracker Pilot\error.log`), and its path added to the agent deny list in `.claude/settings.json` (with the pinning test). | Built on S2's branch (rebuild 4); S6 logs the row. |
