#!/bin/bash
# ── Run the desktop app from source ────────────────────────────────────
# Double-click to start. setup.command has to have run on this Mac before
# (it needs the internet); every start after that is offline.
#
# This file never installs anything (decision 191). A launch that installed
# would run a package's install code, and reach the network, every time the app
# opens. It runs the app's private Python (.venv, made by setup.command) and
# refuses, in one sentence, when that is missing or when the lock files have
# changed since setup ran.
#
# The app itself runs the after-install step at launch when the program changed
# since that step last ran (decision 209): an update pulled from the repository
# that left the lock files alone still registers the schedule and checks the
# records, with nothing to remember.
#
# This is "Start App.bat" for a Mac (SPEC-mac R16), for the /bin/bash 3.2
# macOS ships.

cd "$(dirname "$0")" || exit 1

# Before any other command: bash would otherwise look for node in this folder,
# or in a relative folder PATH names, before the folders that hold the real
# one, so a file dropped here named like it would run instead (E-10). Only
# absolute folders are kept.
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

wait_for_return() {
  if [ -t 0 ]; then
    read -r -p "Press Return to close this window. " _
  fi
}

# The sentence is tools/lockfiles.py's NOT_SET_UP_MAC, word for word
# (tests/test_build.py holds the two together).
not_set_up() {
  echo "The app's private Python is not set up on this computer. Run setup.command once (it needs the internet), then start the app again."
  wait_for_return
  exit 1
}

[ -x ".venv/bin/python" ] || not_set_up
# verify prints its own sentence (tools/lockfiles.py) when the locks moved.
.venv/bin/python tools/lockfiles.py verify .venv || {
  wait_for_return
  exit 1
}
[ -d "app/node_modules/electron" ] || not_set_up
command -v node >/dev/null 2>&1 || {
  echo "Node.js was not found. Install Node.js LTS and start the app again."
  wait_for_return
  exit 1
}

# Electron is started through its own entry script, not the npx shim: the shim
# breaks when the folder's path contains an ampersand (as a firm's name often
# does). The shell runs .venv's Python by its full path.
cd app || exit 1
exec node node_modules/electron/cli.js .
