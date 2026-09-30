# Window control center

**Original file:** `app/main.js`  
**Kind of file:** program code (JavaScript) for the app's outer shell  
**Tags:** Kind: Program file · Topic: Safety, App window  

## In one sentence
This file opens the app's window and passes messages between that window and the tracker program, and it refuses anything the tracker has not said is allowed.

## What it is
The app has two halves. The *window* shows the screens you click on. The *tracker* is the Python program that does all the real work: sorting, filing and checking documents. This file is the go-between. It is written for *Electron*, a kit that turns a web page into a Windows desktop program. In Electron terms this is the "main process" - the one part that is allowed to open windows and start other programs.

The file says of itself that it does no tracking logic. It only carries messages (in a text format called *JSON*) and opens files and folders in Explorer or Excel.

## What it does, step by step
1. **Finds the tracker.** In the installed app it starts the packaged tracker program. When run from source, it starts the app's private copy of Python that Setup.bat made in a folder called `.venv`. If that copy is missing, it shows a plain message saying the private Python is not set up. It never uses whatever Python happens to be on the computer (decision 191).
2. **Allows only one window.** If someone double-clicks the app a second time, the running window is brought forward instead of opening a second one (decision 160). Two windows could each save over the other's changes to the request list.
3. **Builds the window.** It sets the size (1400 by 900, at least 1100 by 700), the menu, and the safety settings. The window may not open other pages or pop-ups, and the page cannot leave the app.
4. **Runs commands for the window.** The window asks for a command by name. This file first checks that the command is in the list the tracker itself published. The very first command allowed is `list`, which asks the tracker for that list. Anything else is refused as "Unknown command" or "Malformed command."
5. **Stops runaways.** A command that takes longer than 30 minutes is stopped and reported, so a button does not stay greyed out forever. Sort & Scan is the exception: it follows the run limit the tracker states (decision 193, decision 203).
6. **Opens files only when allowed.** The window may only open a path the tracker has reported. Just before opening, the file checks that the item is still what the tracker said it was (a folder is a folder, a file is a file, and no shortcut link has been swapped in) (decision 188). Some working copies can only be shown in Explorer, never opened (decision 190).
7. **Keeps errors private.** When something fails, details go into an error log on this computer, never on screen. If the tracker has not named a log, a backup log is kept at `%LOCALAPPDATA%\Tax Document Tracker Pilot\error.log`, capped at about 256 KB with one older copy. It may contain a client's name, so it stays on the PC and is never sent.
8. **Starts the after-install step in the background** at every launch (decision 209). The screen appears at once; if that step did real work, the window is told so it can show a notice.
9. **Quits cleanly.** When the app closes while a Sort & Scan is running, the sort stops after the file it is on. What it did is recorded and its locks are let go (decision 203).

## Why it matters to the firm
Client tax documents pass through this program. The window is treated as *untrusted*, meaning the file assumes the page could be tricked or buggy. So this file is the "second wall": the tracker still checks everything itself (the first wall), but this file also refuses bad commands and bad paths. It also turns off the developer console in the installed app, because a console would let someone at the computer send the tracker any command they typed (decision 176).

## What must never be changed without a programmer
- The list of allowed commands and the check on paths the window may open.
- The window safety settings (page isolation, no developer tools, no navigation, no pop-ups).
- The 30-minute limit and the way a sort is stopped.
- The one-window rule and the way errors are logged.
- Several sentences here are copied word for word from the tracker, and tests check that the two match. Changing wording on one side breaks those tests.

## Words to know
- **Electron:** a kit for making desktop programs out of web pages.
- **Main process:** the one part of an Electron app that may open windows and start other programs. This file is it.
- **Renderer (the window page):** the screens you see. It is not trusted.
- **IPC (inter-process communication):** the message channel between the window and this file.
- **JSON:** a plain-text way of writing structured information so two programs can read it.
- **Allowlist:** a list of the only things permitted. Anything not on it is refused.
- **Lock:** a marker that says a job is running so another cannot start at the same time.
- **Decision number:** a numbered ruling in the project's decision log (see the pilot decision log page).
