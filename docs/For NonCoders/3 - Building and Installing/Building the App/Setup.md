# Setup: preparing a computer to run the app from source

**Original file:** `Setup.bat`  
**Kind of file:** Windows batch script (a list of commands a person double-clicks)  
**Tags:** Kind: Program file · Topic: Building, Supply-chain safety  

## In one sentence
This script prepares a computer to run the app directly from the code folder: it builds the app's own private Python, installs the exact checked parts, and registers the daily schedule.

## What it is
A batch script a person double-clicks, with the internet on. It is for running the app from the code folder, not from the packed program. The computer's own Python is used only to make the private one, and is never installed into. So no other program can break the app, and the app cannot break them. The script pauses at the end so the window can be read.

## What it does, step by step
0. **Checks the basics.** It asks the Python on the computer for its own version, and needs 3.11 or newer. (It does not just look for "python", because a fresh Windows has a Store stub that is not Python.) It also looks for Node.js. If either is missing it says what to install and stops. Like the other scripts, it tells Windows not to run programs from this folder by name (E-10).
1. **Makes the private Python** in a folder named `.venv`. It clears any old one, so a part an older lock file named cannot linger.
2. **Installs the locked parts,** each checked against its SHA-256 fingerprint (decision 191). A file swapped on the package site is refused. The reader's own package goes in separately, without its dependencies (decision 169).
3. **Installs Electron** (the app window) exactly as `app\package-lock.json` says.
4. **Records a stamp** of what was installed: the fingerprint of each lock file and of `package-lock.json`. `Start App.bat` compares it at every launch. It is written after the installs, so a Setup that stopped half way leaves no stamp.
5. **Runs the after-install step** (decision 209). It registers the daily schedule, only on the computer that is meant to run it. It checks every record against today's rules. It removes an old test cache folder left by earlier versions. If a record has a problem, Setup still finishes and the household waits in the app. If a step could not run at all, Setup says so and the app tries again when it starts.

## Why it matters to the firm
It is the way a source checkout becomes a working, safe install. Nothing a person has to remember is left over: the schedule and record checks run as part of Setup itself (decision 209).

## What must never be changed without a programmer
- **The hash-checked installs and the stamp.** They are what keep altered parts out.
- **The order:** stamp after installs, after-install step last.
- **The sentence shown when the after-install step fails.** A test holds it word for word to the same sentence in the program.
- **The `.venv` clearing.**

## Words to know
- **Private Python (.venv, virtual environment):** a separate copy of Python used only by this app.
- **Lock file:** a list of every outside part, with a fingerprint for each.
- **SHA-256:** the fingerprint type used.
- **Electron:** the tool that makes the app window.
- **Node.js:** the tool Electron runs on.
- **Schedule:** the daily job that sorts documents.
