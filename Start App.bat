@echo off
rem ── Run the desktop app from source ────────────────────────────────
rem Double-click to start. Run Setup.bat once first (it needs the internet);
rem every start after that is offline.
rem
rem This file never installs anything (decision 191). A launch that
rem installed would run a package's install code, and reach the network,
rem every time the app opens. It runs the app's private Python (.venv, made
rem by Setup.bat) and refuses, in one sentence, when that is missing or when
rem the lock files have changed since Setup ran.
rem
rem The app itself runs the after-install step at launch when the program
rem changed since that step last ran (decision 209): an update pulled from
rem the repository that left the lock files alone still registers the
rem schedule and checks the records, with nothing to remember.

rem Before any other command: cmd would otherwise look for node in this
rem folder before the search path, so a file dropped here named like it
rem would run instead (E-10).
set "NoDefaultCurrentDirectoryInExePath=1"

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto :not_set_up
rem verify prints its own sentence (tools\lockfiles.py) when the locks moved.
".venv\Scripts\python.exe" tools\lockfiles.py verify .venv
if errorlevel 1 goto :stop
if not exist "app\node_modules\electron" goto :not_set_up
%SystemRoot%\System32\where.exe node >nul 2>nul || (
  echo Node.js was not found. Install Node.js LTS and start the app again.
  goto :stop
)

rem Electron is started through its own entry script, not the npx shim:
rem the shim breaks when the folder's path contains an ampersand (as a
rem firm's name often does). The shell runs .venv's Python by its full path.
pushd app
node node_modules\electron\cli.js .
popd
exit /b 0

rem The sentence is tools\lockfiles.py's NOT_SET_UP, word for word
rem (tests/test_build.py holds the two together).
:not_set_up
echo The app's private Python is not set up on this computer. Run Setup.bat once (it needs the internet), then start the app again.
:stop
pause
exit /b 1
