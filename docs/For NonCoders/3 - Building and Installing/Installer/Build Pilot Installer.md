# Build Pilot Installer: making the Setup file

**Original file:** `pilot/Build Pilot Installer.bat`  
**Kind of file:** Windows batch script (a list of commands a person double-clicks)  
**Tags:** Kind: Program file · Topic: Installer, Building  

## In one sentence
This script builds the program folder and then wraps it into one Setup file, `Tax-Document-Tracker-Pilot-Setup-<version>.exe`, and refuses to do so unless everything is saved in a commit.

## What it is
A batch script that a person double-clicks. It needs what `Build App.bat` needs (Python, Node, git) plus Inno Setup 6.3 or later. It waits for a key before every exit unless a caller sets `TRACKER_BUILD_NONINTERACTIVE`. Like the other scripts, it first tells Windows not to run programs from this folder by name (E-10).

## What it does, step by step
1. **Checks that everything is committed.** It stops if this is not a git checkout, or if any change is uncommitted. The installer must be exactly what is committed (pilot decision P13).
2. **Reads the version** from `app\renderer\pilot-content.js`, the one place it lives.
3. **Builds the app package** by running `Build App.bat` in quiet mode. If that fails, it stops. It also checks that the packaged program exists.
4. **Finds Inno Setup 6.** It looks in the usual Program Files folders and the person's own Programs folder. If it is not found, it says to install it (free, from jrsoftware.org).
5. **Compiles the installer** with Inno Setup, using `pilot\installer\setup.iss` (see that page), passing the version and the package folder.
6. **Reports the result.** It prints the path of the Setup file and its SHA-256 fingerprint. It then reminds the person to tag the commit `pilot-<version>` (never `v...`).

## Why it matters to the firm
Anyone who installs the Pilot gets a file that matches one exact commit. The fingerprint lets a person confirm the copy they received is the copy that was built. Nothing is stamped into any file, so the code stays exactly as reviewed.

## What must never be changed without a programmer
- **The "must be committed" check.** Without it, a Setup file could contain code nobody saved.
- **The tag name rule.** Tags starting with `v` start the separate automatic build of the main package (see the workflows page). Pilot tags must be `pilot-...`.
- **The wait switch handling.** It is read in one place only (the `:wait` label).

## Words to know
- **Installer:** a program that installs another.
- **Inno Setup:** the free tool that builds it.
- **Commit:** one saved version of the code.
- **Tag:** a name pinned to one commit, such as a version label.
- **SHA-256 fingerprint:** a long code that changes if even one byte of a file changes.
- **Batch script (.bat):** a Windows file of commands.
