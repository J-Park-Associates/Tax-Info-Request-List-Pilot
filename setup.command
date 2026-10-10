#!/bin/bash
# ── Set this Mac up to run the app from source ─────────────────────────
# Double-click it, with the internet on. It makes the app's own private
# Python in .venv beside this file and installs into it exactly the packages
# the lock files name, each checked against its SHA-256 (decision 191): a
# file replaced on PyPI at a pinned version is refused. The Mac's own Python
# is used only to make that environment and is never installed into, so no
# other program on this computer can break the app, or be broken by it. Then
# it installs Electron from app/package-lock.json (npm ci checks every
# package's integrity hash).
# Last, it runs the after-install step (decision 209): it registers the
# daily schedule, on the computer that runs it, and checks every record
# against today's rules - so no one-time step waits for a person to remember
# it.
#
# start.command never installs anything: it starts offline, and says in one
# sentence when this file must run again (the lock files changed).
#
# This is Setup.bat for a Mac (SPEC-mac R16). It runs under the /bin/bash 3.2
# macOS ships, so it uses no mapfile, no ${x,,} and no associative array.

cd "$(dirname "$0")" || exit 1

# Before any other command: bash would otherwise look for python3, npm and
# node in this folder, or in whatever relative folder PATH names, before the
# folders that hold the real ones, so a file dropped here named like one of
# them would run instead (E-10). Only absolute folders are kept.
clean_path=""
old_ifs=$IFS
IFS=:
for dir in $PATH; do
  case "$dir" in
    /*) clean_path="${clean_path:+$clean_path:}$dir" ;;
  esac
done
IFS=$old_ifs
PATH=$clean_path

# A person double-clicks this, and Terminal may close the window the moment
# the script ends; wait for Return, but only when someone is there to press it.
wait_for_return() {
  if [ -t 0 ]; then
    read -r -p "Press Return to close this window. " _
  fi
}

# The floor is pyproject.toml's requires-python (tests/test_build.py holds the
# two together). python3 is asked, not guessed: the python3 a bare Mac has is
# a stub that offers to install the developer tools, and is older than this.
command -v python3 >/dev/null 2>&1 && python3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >/dev/null 2>&1 || {
  echo "Python was not found, or is older than the app needs. Install Python 3.11+ and run setup.command again."
  wait_for_return
  exit 1
}
command -v npm >/dev/null 2>&1 || {
  echo "Node.js was not found. Install Node.js LTS and run setup.command again."
  wait_for_return
  exit 1
}

echo "[1/4] Making the app's private Python in .venv..."
# --clear: a package an older lock named and this one does not must not
# survive in the environment.
python3 -m venv --clear .venv || {
  echo "Could not make .venv - is the app still running? Close it and run setup.command again."
  wait_for_return
  exit 1
}
PY=".venv/bin/python"

echo "[2/4] Installing the locked packages (hash-checked)..."
# Two steps (decision 169, R-11): the reader's own package goes in without its
# dependencies, because its metadata asks for the GUI build of OpenCV;
# requirements.lock holds what it really needs.
"$PY" -m pip install --require-hashes -r requirements.lock --quiet || {
  echo
  echo "Installing requirements.lock failed - check your internet connection."
  wait_for_return
  exit 1
}
"$PY" -m pip install --require-hashes --no-deps -r requirements-nodeps.lock --quiet || {
  echo
  echo "Installing requirements-nodeps.lock failed - check your internet connection."
  wait_for_return
  exit 1
}

echo "[3/4] Installing Electron (npm ci from app/package-lock.json)..."
(cd app && npm ci --no-audit --no-fund) || {
  echo
  echo "npm ci failed - check your internet connection."
  wait_for_return
  exit 1
}

# After every install, so a setup that stopped part-way leaves no stamp and the
# app says to run it again. The stamp records the hash of each lock file and of
# app/package-lock.json; start.command compares them every launch.
"$PY" tools/lockfiles.py stamp .venv || {
  echo "Could not record what was installed"
  wait_for_return
  exit 1
}

echo "[4/4] Registering the schedule and checking the records..."
# The after-install step, last: it needs the packages just installed, and the
# stamp stays whatever it says - the packages are installed. It registers the
# schedule only on the computer that runs it, and says why not on any other. A
# record it names is a finding, not a failure: setup finishes, and the household
# waits in the app. It exits non-zero only when a step could not run at all; the
# app tries it again at launch.
if ! "$PY" -m tracker.after_install --reason setup; then
  # The sentence is tracker.after_install's SETUP_RETRY, word for word
  # (tests/test_build.py holds the two together).
  echo
  echo "The after-install step could not finish (above). Start the app: it tries again at launch."
  wait_for_return
  exit 1
fi

echo
echo "Set up. From now on, double-click start.command - it needs no internet."
wait_for_return
exit 0
