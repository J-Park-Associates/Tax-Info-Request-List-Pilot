# Start App: opening the app from source

**Original file:** `Start App.bat`  
**Kind of file:** Windows batch script (a list of commands a person double-clicks)  
**Tags:** Kind: Program file · Topic: Building, App window  

## In one sentence
Double-click this to open the app; it works offline, installs nothing, and stops with one clear sentence if the computer needs `Setup.bat` first.

## What it is
A batch script for running the app from the code folder. It never installs anything (decision 191). A launch that installed things would run outside code, and reach the network, every time the app opened. So the internet is not needed. Like the other scripts, it tells Windows not to run programs from this folder by name (E-10).

## What it does, step by step
1. **Looks for the private Python** (`.venv`) made by `Setup.bat`. If it is missing, it says: the app's private Python is not set up on this computer, run `Setup.bat` (it needs the internet), then start the app again.
2. **Checks that the lock files have not changed** since Setup ran, using `tools\lockfiles.py verify`. That command prints its own sentence if they moved.
3. **Checks that Electron is installed** and that Node.js is found. If Electron is missing, it shows the same "not set up" sentence as step 1. If Node.js is missing, it says to install Node.js.
4. **Starts the app** by running Electron's own entry script. The shortcut is not used, because it breaks when a folder name has an ampersand (a firm name often does). The app runs the private Python by its full path.
5. **On any refusal,** it shows the sentence, waits for a key, and closes with a failure code.

At launch, the app itself runs the after-install step if the program changed since it last ran (decision 209). An update that changed no lock files still gets its schedule and record checks with nothing for a person to remember.

## Why it matters to the firm
It is the everyday front door. Because it cannot install or download, opening the app is fast, safe and predictable. The sentence it shows when the app is not ready is the same as in `tools\lockfiles.py`, and a test keeps them equal.

## What must never be changed without a programmer
- **Never add an install step.** That is the rule this file exists to keep.
- **The "not set up" sentence.** It must stay word for word equal to the one in `tools\lockfiles.py`.
- **The way Electron is started.**

## Words to know
- **Private Python (.venv):** the app's own copy of Python, made by Setup.
- **Lock file:** a list of every outside part, with a fingerprint for each.
- **Electron:** the tool that makes the app window.
- **Node.js:** what Electron runs on.
- **Offline:** working with no internet.
