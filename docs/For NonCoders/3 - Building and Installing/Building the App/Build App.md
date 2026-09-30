# Build App: making the portable program folder

**Original file:** `Build App.bat`  
**Kind of file:** Windows batch script (a list of commands a person double-clicks)  
**Tags:** Kind: Program file · Topic: Building  

## In one sentence
This script builds the complete program folder, ready to put on the office computer, from exactly the version of the code that is checked out.

## What it is
A batch script is a text file of Windows commands. Double-clicking it runs them in order. This one is written for a person, so it waits for a key press before it closes and the window stays readable. The automatic build on GitHub has nobody to press a key. Setting `TRACKER_BUILD_NONINTERACTIVE` makes every wait return at once.

The result lands in `build-portable\dist\<product name>-win32-x64`. Everything the build uses is pinned in the version being built: the Python parts (lock files), the Electron parts (`app\package-lock.json`) and the freezing recipe (`api_entry.spec`).

## What it does, step by step
0. **Safety first.** It tells Windows not to run programs from this folder by name, so a stray file called `python` or `git` cannot run in their place (E-10). It reads the product name and engine name from `app\package.json`.
1. **Freezing the engine.** It makes a fresh private Python environment, and installs into it only what the lock files name, each file checked against its fingerprint. A fresh one every time means nothing left over is frozen in. It installs the reader's own package separately, without its dependencies (decision 169). Then it runs PyInstaller with `api_entry.spec`.
2. **Packaging the shell** (the app window around the engine). It installs the Electron parts exactly as `package-lock.json` says, then packages the app window. It calls the packager's entry script directly because the shortcut breaks when a folder name has an ampersand.
3. **Assembling the folder.** It copies the frozen engine into the package. It uses `robocopy`, not `xcopy`, because `xcopy` gives up on long paths without saying so. It checks that the engine `.exe` is really there.
4. **Recording what was built.** It writes `BUILD-INFO.txt`: the date, the computer, the commit (and a note if there were uncommitted changes), and the Python, Node and npm versions, plus the list of frozen Python packages.
5. **Done.** It prints where the folder is and says to put the whole folder on the designated machine (the runbook, section 1, says which).

If any step fails, it says so in words and stops.

## Why it matters to the firm
This is the one way the office program is made. Because it pins everything and records the commit, two builds of the same version are the same program, and a person can tell later exactly what a package holds.

## What must never be changed without a programmer
- **The fresh environment and hash-checked installs.** They keep unknown or altered parts out of the package.
- **The "not a git checkout / plus uncommitted changes" note.** It keeps BUILD-INFO honest.
- **The one place the wait switch is read** (the `:wait` label at the end).
- **The installs' order and flags.**

## Words to know
- **Batch script (.bat):** a Windows file of commands.
- **Lock file:** a list of every outside part the program uses, with a fingerprint (SHA-256) for each.
- **Virtual environment:** a private copy of Python for one job.
- **Freeze:** pack the Python engine and everything it needs into one Windows program (`.exe`) that runs without Python installed.
- **PyInstaller:** the tool that freezes the engine.
- **Electron:** the tool that makes the app window.
- **Commit:** one saved version of the code.
- **robocopy:** a Windows tool that copies folders reliably.
