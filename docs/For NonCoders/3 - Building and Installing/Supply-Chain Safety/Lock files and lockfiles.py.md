# Lock files: the list of every outside part, with fingerprints

**Original file:** `tools/lockfiles.py`, `requirements.txt`, `requirements.lock`, `requirements-build.txt`, `requirements-build.lock`, `requirements-nodeps.txt`, `requirements-nodeps.lock`, `requirements-gpu.txt`, `requirements-gpu.lock`  

**Kind of file:** dependency lists (the `.txt` files), lock files (the `.lock` files) and the tool that manages them (`lockfiles.py`)  
**Tags:** Kind: Program file · Topic: Supply-chain safety  

## In one sentence
These files name every outside part the program uses by exact version and by a fingerprint, so a part swapped by an attacker is refused, and `lockfiles.py` keeps them honest.

## What it is
A program is built from many outside parts (libraries). A *pin* names an exact version. A version name alone does not stop a file being replaced on the download site (PyPI). So decision 191 added *lock files*. Each lists every part and the SHA-256 fingerprint of every file published for it. The installer command `pip install --require-hashes` refuses a file whose fingerprint is not listed, and any part the lock does not name. That also proves the lock holds the whole tree.

The four pairs:
- `requirements.txt` / `requirements.lock`: what the program uses, plus the test tools. Setup, the build and CI install it.
- `requirements-build.txt` / `requirements-build.lock`: PyInstaller (the freezing tool). `Build App.bat` installs it with the main lock.
- `requirements-nodeps.txt` / `requirements-nodeps.lock`: the reader's package (`rapidocr`) alone, installed without its own dependency list (decision 169, R-11), because that list asks for a display build of OpenCV the app does not ship.
- `requirements-gpu.txt` / `requirements-gpu.lock`: the optional NVIDIA graphics card pack. Only `Build GPU Pack.bat` reads it.

The `.txt` files are edited by a person. The `.lock` files carry the whole tree and the fingerprints.

## What it does, step by step
The tool `tools/lockfiles.py` uses only the standard library. Its commands:
1. **hash:** fills in each lock's fingerprints from PyPI. Needs the internet. A maintainer runs it after a pin moves.
2. **check:** proves the locks agree with the `.txt` pins and every line has a fingerprint. No network. The test suite runs it.
3. **stamp:** at the end of Setup, records the fingerprint of each lock and of `app/package-lock.json` inside the private Python folder.
4. **verify:** at every start, `Start App.bat` compares the stamp to the files now. If they differ, it says so in one sentence and the app does not start.
5. **audit:** asks OSV (an open vulnerability database) about every locked package. It also holds the two file-parsing engines, pillow and pypdfium2, to a cadence: once the first release newer than the pinned one is more than 90 days old, the run fails until the pin moves. The weekly audit workflow runs it.

The program itself never imports this tool, because its rules keep the network out.

## Why it matters to the firm
The program handles client tax documents. This is the defense against a tampered outside part. A pin moved by the update helper (Dependabot) makes the lock check fail on purpose, so a person must run the hash tool before a new fingerprint enters.

## What must never be changed without a programmer
- **Never hand-edit a fingerprint.** Change the pin in both files and run `hash`.
- **Never install these files without the hash-checking option.**
- **The "not set up" sentence** is held equal to the one in `Start App.bat`.
- **Keep pillow and pypdfium2 current.**

## Words to know
- **Dependency / outside part:** code written by others that the program uses.
- **Pin:** an exact version.
- **Lock file:** a list of every part with a fingerprint.
- **SHA-256 hash:** a fingerprint that changes if a file changes.
- **PyPI:** the public site Python parts are downloaded from.
- **OSV:** an open database of known security flaws.
- **Stamp:** the record of which lock files were installed.
