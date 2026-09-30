# Windows check for the app shell (Jason, office PC)

Run this once the shell is joined and its last review says "No findings". It is
the check the sandbox cannot make: a real Windows, a real installer, real
themes. Plain English throughout: tick each step and write down what you saw.
Made-up documents only (`%USERPROFILE%\PilotTest\Clients`); nothing is sent
anywhere. Nothing here needs Git or a programmer's tool.

## Get the code (no Git)

Use whichever is true today:

- **The shell is merged to `main`:** open
  <https://github.com/J-Park-Associates/Tax-Info-Request-List-Pilot>, press the
  green **Code** button, **Download ZIP**.
- **It is not merged yet:** on the same page open the branch list (the button
  that says `main`), choose `claude/shell-join` (or the branch named in
  `pilot/handoffs/shell-S6b.md`), then **Code**, **Download ZIP**.

Right-click the ZIP in Downloads, **Extract All**, and open the extracted
folder in File Explorer. That folder is "the pilot folder" below.

## The tests (each file in its own window, in parallel)

In the pilot folder, click the address bar, type `powershell` and press Enter.
Paste this one line and press Enter:

```
powershell -ExecutionPolicy Bypass -File pilot\wintest\run_checks.ps1 -Tests tests\test_shell.py,tests\test_shell_menu.py,tests\test_api.py,tests\test_registry.py,tests\test_runner.py,tests\test_pilot_ui.py,tests\test_tour.py,tests\test_pilot.py,tests\test_single_source.py,tests\test_layers.py,tests\test_vocab_report.py,tests\test_repo_map.py,tests\test_tripwire.py,tests\test_errors.py
```

Why these: `test_shell` and `test_shell_menu` are the renderer and the window
and menus; `test_api`, `test_registry` and `test_runner` are the engine words,
the firm view, the failure reasons and the skipped-folder reasons;
`test_pilot_ui`, `test_tour` and `test_pilot` read the pilot's own files; the
rest are the guards. Not the whole suite: the sorting engine's own tests are
not rerun. The run also builds the installer; note its SHA-256.

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
   focus outlines show, nothing vanishes, and the links are still underlined
   in the theme's link colour. Turn it off.
4. **Dark mode.** Settings, Personalisation, Colours: choose Dark, then Light,
   with the app open (it follows at once). Close and reopen while Dark: the
   window must not flash white first. In both, a return or file name that is a
   link is underlined, and a status such as "3 Waiting" is not.
5. **The "Came in Email or Zip" status.** Open a return that has a file that
   came in an email or a zip. That file's name is plain text, not a link (an
   email or a zip is never opened from here), and its status words end with an
   ellipsis at the column's edge without spilling into the next column;
   hovering shows the full words.
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
8. **Return years show.** Shrink the window to its smallest width (1100 pixels
   wide). On Overview, Reminders, the household page and Clients (All), every
   return name reads "1040 - Name (2025)" with its year, on two lines when the
   name is long, and no row cuts the year off. Hover a return name: the tip
   still reads "Navigate to Return".
9. **Tooltips.** Hover an icon: the tip appears after a short wait (300 ms).
   Tab to an icon: it appears at once. Click into the search box: no tip.
   Escape closes a tip.
10. **Right-click menus.** Right-click a parked file, a moved file and a
    Received row: each menu ends with "Show in File Explorer" and it works.
11. **Unfile box.** Right-click a Received row, Unfile: a small box asks
    "Reason (Optional)" with a confirm button. Confirm with a reason, then
    check the reason shows in the record.
12. **A failed scheduled sort.** The banner comes only from the overnight
    (scheduled) sort, never from the app's own Sort, so make the scheduled
    sort fail once, on purpose:
    1. Close the app. In File Explorer rename **the folder you chose as the
       Clients folder in step 2** (`%USERPROFILE%\PilotTest\Clients`, the
       one that holds the two folders `Clients` and `J Park & Associates`) to
       `Clients-away`. Rename that one and not the `Clients` folder inside it:
       the scheduled sort is refused for certain when the chosen folder is
       gone, but a household that was never sorted just gets its inside
       folder made again and the sort succeeds, which would show no banner.
    2. Open the Start menu, type **Task Scheduler**, open it, click **Task
       Scheduler Library**, right-click the task named **Tax Document Tracker
       Pilot** and choose **Run**. Wait half a minute and press F5: **Last
       Run Result** is not `0x0`. (If there is no such task, open the app once
       and choose **Repair Schedule** in the Tools menu, then come back.)
    3. Rename `Clients-away` back to `Clients`, then open the app.
    What you must see, on every page (Overview, Needs Review, Reminders,
    Clients): a notice that says "Sort Failed" with **no Retry button and no
    other button** (only the small dismiss cross), and the side panel's
    last-sort line says "Sort Failed" too. Now open a client and press the
    Sort icon: the sort runs, but the notice **stays** (correct: the app's own
    Sort names one household and cannot clear it). There is no Retry to grey
    out and nothing on a firm page can start a sort. To clear it: in Task
    Scheduler run the task again (the folder is back), wait half a minute,
    press F5 in the app: the notice and the side panel's failed line are gone.
13. **A return's failed-sort banner.** Use a household the app or the
    overnight sort has already sorted once (its client folder then exists;
    a household never sorted just gets it made again). In the `Clients`
    folder that sits inside the folder from step 2, rename that household's
    folder (keep the name in your notes), open one of its returns and press
    Sort. The banner's first line reads "Sort Failed: Folder Not Found"
    (five words at most, no folder path). If the household has other returns,
    each gets one more line beginning with a bullet and its household, year
    and return name, then "Sort Failed: Folder Not Found", and never a
    folder path or a long sentence. Rename the folder back.
14. **Paused marker.** In a household make two years open: Add a Return for
    the year before. Clients shows a marker beside the household reading
    "Two Years Open; Sorting Paused" **in full, on wrapped lines if needed,
    never cut**, and Overview lists it the same way. Nothing is hidden on the
    household's own pages. To switch the older return off: open that older
    return's page, right-click its name and choose **Edit Request List…**, set
    **Active** to *No: Sorting Skips This Return*, and save. Press F5: the
    marker goes.
15. **Skipped folders.** In File Explorer, inside the practice folder
    `J Park & Associates\<household>\` (the household's own folder, for
    example `J Park & Associates\Smith Family\`), create a folder named
    `Archive 2024` next to the year folders. Press F5 in the app. The notice
    "1 Folders Skipped" appears; **Show** opens Folders Skipped with the
    folder and the reason "Bad Year". Delete the test folder afterwards.
16. **Fallback error log.** A failing command cannot be made by hand on an
    installed app (the tracker has to crash before it names its data folder),
    so the tests make that failure (`test_shell_menu.py`,
    `test_single_source.py`). By hand check what a person can: on a fresh
    Windows user, before choosing a Clients folder, choose **Help**, **Open
    Error Log**: the notice says "No Error Log Yet". If a fallback log exists
    (`%LOCALAPPDATA%\Tax Document Tracker Pilot\error.log`, normally
    `C:\Users\<you>\AppData\Local\Tax Document Tracker Pilot\`), Open Error
    Log opens it. Uninstall the app: that folder is still there (delete it by
    hand; it can hold client names).
17. **Remote Desktop** at 1100 x 700: nothing cut off, no horizontal scroll.

Record results in `pilot/wintest/` as `RESULTS-TEMPLATE.md` asks and tell Jason
what passed, what failed and why.
