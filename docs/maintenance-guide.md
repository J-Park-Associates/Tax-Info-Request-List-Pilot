# Taking care of the Tax Document Tracker

This page is for the person who looks after the program after the people
who built it are gone. **You do not need to know how to code to read it.**
Every hard word is explained the first time it shows up.

If a step here says "ask a programmer," that is not a failure. It means the
step can break something that protects client files, and a second pair of
eyes is the safe choice.

---

## The one-minute picture

Think of the program as a small office with three workers.

1. **The window** (the part you click on). Its builders call it *Electron*,
   which is a kit for making desktop programs out of web pages. It shows
   you lists and buttons. **It is not trusted to touch files by itself.**
2. **The engine** (the part that does the real work). It is written in
   *Python*, a programming language. It sorts, renames and records every
   client document. It is the only worker allowed to decide anything.
3. **The alarm clock** (Windows *Task Scheduler*, a part of Windows that
   starts programs at set times). It wakes the engine up during the day so
   documents get sorted even when nobody has the window open.

Client files live in a **Google Drive** folder that Google's own program
copies onto the office computer. The tracker reads and writes that copy;
Google Drive moves the changes to the cloud by itself.

There are four promises the program always keeps. They are written word
for word in `tracker/__init__.py`, and the app shows them in short under
**Help > Safeguards**:

- No AI ever reads a client's financial document.
- Original files are never changed.
- Nothing is guessed. If the program is not sure, a person decides.
- Nothing is ever sent. The program writes draft emails; a person sends them.

**If any change would break one of these promises, do not make it.**

---

## Part 1. The safety walls (please do not weaken these)

The window is treated like a stranger. Even if someone tricked it, it
still could not open or change files on its own. Five walls make that true.

### Wall 1: The window is in a sandbox

A *sandbox* is a locked playpen: what is inside cannot reach out. The
settings that build it are in `app/main.js`, near the bottom, where the
window is made:

```
contextIsolation: true
nodeIntegration: false
sandbox: true
webSecurity: true
```

The next two lines stop the window from opening new windows or going to
any web page.

**Rule: never change `true` to `false` or `false` to `true` in those
lines.** The automatic tests check them.

### Wall 2: The window may only use a short list of buttons

The window cannot run any command it wants. When the program starts, the
engine hands the window a list of the commands that exist (the builders
call it the *allowlist*: a list of what is allowed, where everything else
is refused). `app/main.js` refuses any command that is not on that list.

`app/preload.js` is the tiny doorway between the window and the rest of
the program. It has only a few doors: run a command, open a file, pick a
folder, write to the error log, hear how a sorting pass is going, and use
the menu. **Never add a door there** without a programmer and a written
plan.

### Wall 3: The window may only open files the engine named

This is the "allowed-file list." Here is how it works, step by step:

1. Every time the engine answers, it lists the files and folders it is
   talking about, and says for each one whether it is a **file** or a
   **folder**.
2. `app/main.js` writes each one down in a list called `openable`.
3. When you click to open something, `app/main.js` checks the list. **If
   the path is not on the list, it is refused** with the sentence "That
   path is not one the tracker reported; nothing was opened."
4. Even if it is on the list, it looks one more time, right before
   opening: is it still a real file (or a real folder), and not a
   *shortcut in disguise* (a *symbolic link*, which points somewhere else)?
   If anything changed, it is refused.

**Rule: never make the window able to open a path it typed itself.**

### Wall 4: The page may only load its own files

The page itself carries a rule called the *Content Security Policy* (CSP),
which is a list the browser part obeys about what the page may load. It is
in `app/renderer/index.html`, near the top:

```
default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'
```

In plain words:

| Part | What it means |
|---|---|
| `default-src 'none'` | Load nothing, unless a line below allows it. |
| `script-src 'self'` | Programs only from the app's own folder. No programs from the internet, and none typed into the page. |
| `style-src 'self'` | Colors and layout only from the app's own files. |
| `img-src 'self' data:` | Pictures only from the app's own files, or drawn inside the page. |
| `font-src 'self'` | Lettering only from the app's own files. |

It stops a bad file name or a bad web page from sneaking a program into
the window.

**Rule: never add a web address, `'unsafe-inline'` or `'unsafe-eval'` to
that line.** Those words would open the wall. If a new feature "needs"
them, the feature is built the wrong way.

### Wall 5: The engine checks everything again

The engine (`tracker/api.py`) checks every request the window sends, even
though the window already checked. Two walls are better than one.

---

## Part 2. How it connects to Windows and Google Drive

### The alarm clock (Windows Task Scheduler)

- **Its name** in Task Scheduler is the program's name:
  `Tax Document Tracker Pilot`.
- **When it runs:** unless someone changed it, starting at 7:00 in the
  morning, then every 2 hours. It can be changed, or turned off, in the app
  under **Tools > Schedule…**. On Saturdays it also writes the reminder
  emails (as drafts only).
- **What it runs** (in the installed program):

  ```
  <program folder>\resources\tracker-api\tracker-api.exe --run --settings "<program folder>" --log
  ```

  `--run` means "do a sorting pass." `--settings` names the folder that
  holds `settings.json`, the small file that says where the clients folder
  is. `--log` means "write what happened in the run log."
- **Where it starts** (its *working directory*, the folder it stands in):
  the engine's folder, `<program folder>\resources\tracker-api`.
- **How long it may run:** up to 2 hours. After that Windows stops it.
  Stopping it half way is safe: the next pass cleans up and carries on.

**You never set this up by hand.** Installing the program, the first start
after an update, and saving the clients folder all set it up. If it ever
looks wrong, open the app and use **Tools > Repair Schedule**.

Only **one** computer may run the alarm clock for a clients folder. That
computer's name is written in a file called `_Scheduling computer.txt` in
the firm's private folder. Moving it to a new computer is in
[runbook.md](runbook.md), section 6.

### What happens when something goes wrong at night

It is **not** silent. That is on purpose: a quiet failure would show up at
a filing deadline.

- One client's problem never stops the other clients. It is written down
  and the pass moves on.
- If anything failed, the pass ends with an error number. **Task
  Scheduler then shows the run as failed** ("Last Run Result" is not
  `0x0`).
- The app shows a red **Sort Failed** notice with a short reason, until the
  next good pass.
- The details go in the run log (`logs\runs.log`) and the error log
  (`tracker-errors.log`), both in the tracker's data folder under
  `%LOCALAPPDATA%` on that computer. Client paths are never shown on screen.

What each note means is in [runbook.md](runbook.md), sections 4 and 5.

### Google Drive

- **Where the files are:** a folder on the firm's Shared Drive, which
  Google Drive for desktop shows on the computer, for example
  `G:\Shared drives\JPA Clients`. That is the *clients root* (the top
  folder that holds every client).
- **Inside it, two trees:**
  - `Clients` - the only part a client ever sees. Each household has one
    `Drop files here` folder and one folder per year.
  - `J Park & Associates` - the firm's private side. Never shared.
- **A file that is still downloading** (Google shows it but has not copied
  it down yet) is left alone. The next pass picks it up.
- **A file being changed during a pass** is safe: the engine writes every
  file to a temporary copy first and swaps it in whole, so nobody ever
  sees half a file.
- **Two copies of the record** (a name like `_ledger (1).jsonl`) mean two
  computers wrote at once. **Never delete these.** The runbook, section 2,
  says what to do.
- The program's own database lives on the computer, **not** in Google
  Drive, because a database that syncs gets corrupted.

The full details are in [runbook.md](runbook.md), sections 1, 2 and 6.

---

## Part 3. Building a new installer

You need a Windows computer with **Python**, **Node** (a tool that runs
the window's code), **Git** (the tool that keeps the history of every
change) and **Inno Setup 6.3 or later** (a free tool that makes Windows
installers).

### The easy way: one double-click

Double-click `pilot\Build Pilot Installer.bat`. It does every step below,
in order, and stops with a clear message if any step fails:

1. Checks that every change is saved in Git. **It refuses to build from
   unsaved changes**, so the installer is exactly what is in the history.
2. Reads the version number from `app\renderer\pilot-content.js`.
3. Runs `Build App.bat` (next section).
4. Finds Inno Setup.
5. Makes the installer and prints its fingerprint (its *SHA-256*, a long
   code that changes if even one letter of the file changes).

The installer lands in `build-portable\installer\`.

### What `Build App.bat` does

1. **Freezes the engine.** *Freezing* turns the Python engine into one
   program, `tracker-api.exe`, so the office computer does not need
   Python. The tool is called *PyInstaller*, and its recipe is the file
   `api_entry.spec`. The step it runs is:

   ```
   python -m PyInstaller --noconfirm --clean --distpath build-portable\py --workpath build-portable\pyi-work api_entry.spec
   ```

   It runs inside a brand-new, empty Python every time, so nothing extra
   from the build computer sneaks in.
2. **Packs the window** with the exact versions saved in
   `app\package-lock.json`.
3. **Puts the engine inside the window's folder** at
   `resources\tracker-api\`.
4. **Writes `BUILD-INFO.txt`**, which records the exact version (Git
   *commit*, a saved snapshot of the code) and tools used.

### What the installer does

The recipe is `pilot\installer\setup.iss`.

- Installs for one person only. It does **not** need an administrator.
- Installs to `%LOCALAPPDATA%\Programs\Tax Document Tracker Pilot`.
- **On an upgrade:** close the app first. If the app or a sorting pass is
  still running, the installer asks to close it. **Say yes.** It then
  removes only the old program code (two folders:
  `resources\app` and `resources\tracker-api\_internal`) and copies in the
  new code, so no leftover old files stay behind. It never touches client
  files, the data folder, `settings.json`, or the optional graphics card
  pack (`gpu-runtime`).
- **If an upgrade stops half way** (for example, you said no to closing
  the app, then pressed Abort), the program may not start. Close the app,
  then run the same installer again; it finishes the job.
- **On uninstall:** removes the program and the alarm clock. It never
  removes client files, the data folder or `settings.json`.
- **Never change the `AppId` line.** It is how an upgrade finds the old
  copy. A new `AppId` makes Windows think it is a different program.

The release checklist is [pilot/RELEASE.md](../pilot/RELEASE.md).

### Locked ingredient lists (supply-chain safety)

The engine is built from outside parts called *packages*. A **lock file**
lists every package, its exact version, and its fingerprint. If a package
on the internet were ever swapped for a bad one, its fingerprint would not
match and **the install stops**.

| File | What it locks |
|---|---|
| `requirements.lock` | Everything the engine and its tests need. |
| `requirements-build.lock` | The freezing tool (PyInstaller). |
| `requirements-nodeps.lock` | The document reader, installed by itself. |
| `requirements-gpu.lock` | The optional graphics card pack. |

Every install uses `--require-hashes`, which means "check every
fingerprint, and refuse anything not on the list." `Setup.bat`,
`Build App.bat` and the automatic checks all do this.

Commands (a programmer runs these):

```
python tools/lockfiles.py check     # do the lock files match the wish lists?
python tools/lockfiles.py hash      # fill in fingerprints after a version change (uses the internet)
python tools/lockfiles.py verify .venv   # does this computer still match the locks?
python tools/lockfiles.py audit     # any known security problems? (uses the internet)
```

Once a week, GitHub runs the `audit` by itself (`.github/workflows/audit.yml`).
Dependabot (a GitHub helper) suggests updates; a person approves each one.

---

## Part 4. Testing, and the GitHub bill

### Test on your own computer, not on GitHub

GitHub charges for each automatic test run, and Windows runs cost double.
The rules are in [CLAUDE.md](../CLAUDE.md), in the section **"Standing rule:
GitHub Actions cost discipline."** The short version:

- **Test here first, every time.** Never push a change "to let GitHub
  test it."
- Test only what the change touched (the list of which files is in
  CLAUDE.md).
- Save up changes and send them to GitHub in bigger, less frequent batches.
- GitHub runs its tests only when:
  1. a change lands on `main` (the main copy of the code), or
  2. a person marks a pull request (a proposed change) **ready**, or
  3. a person adds the `windows` label, and only for work that touches
     Windows-only things.
- Never type `@claude` in a GitHub issue or pull request. That runs on the
  paid GitHub computers.

### The test commands

A programmer runs these from the project's top folder, after `Setup.bat`
has set up the private Python:

```
python -m pytest -q                          # every automatic test (slow; only when the engine changed)
python -m pytest -q tests/test_pilot_installer.py   # just one file's tests
python -m ruff check .                       # finds unused or dead code
python tools/repo_map.py check               # is the repository map up to date?
python tools/vocab_report.py check           # is the word-matching report up to date?
```

The tests run on two Python versions: the oldest one allowed (3.11) and
the one the office uses (3.14).

**On the Windows office computer**, one script runs chosen test files side
by side and builds the installer at the same time:

```
pilot\wintest\run_checks.ps1 -Tests tests\test_pilot_installer.py,tests\test_shell.py
```

**The screen pictures and click tests** use a hidden copy of the Chromium
web browser and made-up client names only (never real clients). How to run
them is in [pilot/harness/README.md](../pilot/harness/README.md):

```
HARNESS_PYTHON=<the private Python> node pilot/harness/shoot.mjs <output folder>   # pictures of every screen
HARNESS_PYTHON=<the private Python> node pilot/harness/interact.mjs                # clicks through and checks
```

`HARNESS_PYTHON` names the Python that `Setup.bat` made (for example
`.venv\Scripts\python.exe`).

---

## Part 5. The map of the code

`docs/repo-map.md` is a big map of every file and what it is for. It is
made by a program, so **never edit it by hand**. To change what the map
says about a file, edit `docs/repo-map.curated.json` and run:

```
python tools/repo_map.py update
```

The places where the separate parts meet are the places most likely to
break. The map marks them. They are:

| Where two parts meet | File |
|---|---|
| The window starts the engine | `app/main.js` (look for `spawn`) |
| The one door between window and program | `app/preload.js` |
| The engine starts, either for the window or for the alarm clock | `api_entry.py` |
| The alarm clock's command is read and a sorting pass runs | `tracker/runner.py` |
| The alarm clock is written into Windows | `tracker/scheduling.py` |
| The freezing recipe | `api_entry.spec` (top folder) |
| The installer recipe | `pilot/installer/setup.iss` |
| The build buttons | `Build App.bat`, `pilot/Build Pilot Installer.bat` |

The plain-English library in `docs/For NonCoders/` keeps itself honest. A
small program, `tools/noncoder_pages.py`, remembers a fingerprint of every
file a page explains. A new handoff note or a changed file cannot be
finished without its page: an automatic check fails, and an AI helper is
told which page to write, until it is done. The same program files the
pages into the right folders, renumbers them, and keeps a history of pages
that were rewritten or whose file was removed.

---

## Where to look next

| If you want to... | Read |
|---|---|
| Know what to do each morning, or fix a daily problem | [runbook.md](runbook.md) |
| Know who does what at the firm | [workflow.md](workflow.md) |
| Know **why** something odd was built that way | [ROADMAP.md](ROADMAP.md) (search for the decision number) and [pilot/DECISIONS.md](../pilot/DECISIONS.md) |
| Know how the program stores its records | [storage.md](storage.md) |
| Hand work to an AI helper | [CLAUDE.md](../CLAUDE.md) |
| Read any program file or past handoff note in plain words | [For NonCoders](<For NonCoders/README.md>) |

## Words used on this page

| Word | Meaning |
|---|---|
| Allowlist | A list of what is allowed. Anything not on it is refused. |
| Clients root | The top folder that holds every client's folder. |
| Commit | A saved snapshot of the code in Git's history. |
| CSP | Content Security Policy: a rule telling the window what it may load. |
| Electron | The kit the window is built with. |
| Freeze | Turn Python code into a program that runs without Python. |
| Git | The tool that keeps every past version of the code. |
| Hash / fingerprint / SHA-256 | A long code made from a file. If the file changes, the code changes. |
| Inno Setup | The free tool that makes the Windows installer. |
| Lock file | A list of every outside package, its version and its fingerprint. |
| Pull request | A proposed change, waiting to be checked and joined to `main`. |
| PyInstaller | The tool that freezes the engine. |
| Python | The language the engine is written in. |
| Sandbox | A locked area. What is inside cannot reach out. |
| Symbolic link | A shortcut that points to another place. |
| Task Scheduler | The part of Windows that starts programs at set times. |
