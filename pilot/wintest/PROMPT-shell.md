# Windows check for the app shell (Jason, office PC)

Run this once the shell branch is joined (`claude/shell-join`, then S5 merged
by S6b) and its last review says "No findings". It is the check the sandbox
cannot make: a real Windows, a real installer, real themes. Plain English; tick
each step and write down what you saw. Made-up documents only
(`%USERPROFILE%\PilotTest\Clients`); nothing is sent anywhere.

Code first: in the pilot checkout, `git fetch`, check out the branch named in
`pilot/handoffs/shell-S6b.md` (until it exists: `claude/shell-join`), and
`git status` should be clean.

## The tests (each file in its own window, in parallel)

```
powershell -ExecutionPolicy Bypass -File pilot\wintest\run_checks.ps1 -Tests tests\test_shell.py,tests\test_shell_menu.py,tests\test_api.py,tests\test_registry.py,tests\test_pilot_ui.py,tests\test_tour.py,tests\test_pilot.py,tests\test_single_source.py,tests\test_layers.py,tests\test_repo_map.py,tests\test_tripwire.py,tests\test_errors.py
```

Why these: `test_shell` and `test_shell_menu` are the renderer and the window
and menus; `test_api` and `test_registry` are the engine words, the firm view
and the skipped-folder reasons; `test_pilot_ui`, `test_tour` and `test_pilot`
read the pilot's own files; the rest are the guards. Not the whole suite: the
sorting engine was not touched. It also builds the installer; note its
SHA-256.

## By hand

1. **Build and install.** The run above builds the installer. Install it
   (silent is fine). The app opens; the terms and the tour come first on a
   fresh install: accept, finish the tour. Every tour step title should read
   in Title Case ("Needs Review", not "Needs review").
2. **Run it on the sample folder.** Point it at the made-up Clients folder.
   Check the four pages (Overview, Needs Review, Reminders, Clients) open from
   the side panel and the keys Ctrl+1 to Ctrl+4.
3. **Contrast theme.** Windows Settings, Accessibility, Contrast themes: turn
   one on (Aquatic, then Night sky) with the app open. Text stays readable,
   focus outlines show, nothing vanishes. Turn it off.
4. **Dark mode.** Settings, Personalisation, Colours: choose Dark, then Light,
   with the app open (it follows at once). Close and reopen while Dark: the
   window must not flash white first.
5. **The "Came in email or zip" column.** Open a return that has a file that
   came in an email or a zip. The words in that column must be cut with an
   ellipsis at the column's edge, not spill into the next column; hovering
   shows the full words.
6. **Firm summary speed.** Clients folder with many returns (the 750-return
   copy if you have it, else note the count): open Overview and time how long
   the counts take to appear. The budget is 3 seconds for 750 returns. The
   sandbox measured 6.7 seconds, so this is the real answer; write the number
   down.
7. **Links.** In Needs Review, click a file name: File Explorer opens with that
   working copy selected. Click a return name: the app goes to that return's
   page. Click a household name: the app goes to that client's page (nothing
   opens in Explorer). Hover each: the tooltips read "Show in File Explorer",
   "Navigate to Return", "Navigate to Client".
8. **Tooltips.** Hover an icon: the tip appears after a short wait (300 ms).
   Tab to an icon: it appears at once. Click into the search box: no tip.
   Escape closes a tip.
9. **Right-click menus.** Right-click a parked file, a moved file and a
   Received row: each menu ends with "Show in File Explorer" and it works.
10. **Unfile box.** Right-click a Received row, Unfile: a small box asks
    "Reason (Optional)" with a confirm button. Confirm with a reason, then
    check the reason shows in the record.
11. **Sort-failure notice.** Make a sort fail (rename the Clients folder while
    the app is open, then Sort). A notice with Retry shows at the top of every
    page and clears when a sort works. The side panel keeps "Sort Failed".
12. **Paused marker.** In a household, make two years open (add a return for
    the year before). Clients shows a marker beside the household reading
    "Two Years Open; Sorting Paused", and Overview lists it. Nothing is hidden
    on the household's own pages. Switch the older return off: the marker goes.
13. **Skipped folders.** Put a folder named `Archive 2024` where a year folder
    would sit. "Folders Skipped" shows it with the reason "Bad Year".
14. **Fallback error log.** With no data folder yet (fresh user), make a
    command fail. The screen says the failure's sentence and "Tracker Failed"
    only. Look in `%LOCALAPPDATA%\Tax Document Tracker Pilot\error.log`
    (normally `C:\Users\<you>\AppData\Local\Tax Document Tracker Pilot\`): the
    details are there. Help, Open Error Log opens it. Uninstall the app: the
    folder is still there (delete it by hand).
15. **Remote Desktop** at 1100 x 700: nothing cut off, no horizontal scroll.

Record results in `pilot/wintest/` as `RESULTS-TEMPLATE.md` asks and tell Jason
what passed, what failed and why.
