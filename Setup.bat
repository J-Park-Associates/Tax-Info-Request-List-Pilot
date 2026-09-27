@echo off
rem ── Set this computer up to run the app from source (once) ─────────
rem Double-click once, with the internet on. It makes the app's own private
rem Python in .venv beside this file and installs into it exactly the
rem packages the lock files name, each checked against its SHA-256
rem (decision 191): a file replaced on PyPI at a pinned version is refused.
rem The machine's own Python is used only to make that environment and is
rem never installed into, so no other program on this computer can break
rem the app, or be broken by it. Then it installs Electron from
rem app\package-lock.json (npm ci checks every package's integrity hash).
rem Last, it runs the after-install step (decision 209): it registers the
rem daily schedule, on the computer that runs it, and checks every record
rem against today's rules - so no one-time step waits for a person to
rem remember it.
rem
rem "Start App.bat" never installs anything: it starts offline, and says in
rem one sentence when this file must run again (the lock files changed).

rem Before any other command: cmd would otherwise look for python, npm and
rem node in this folder before the search path, so a file dropped here
rem named like one of them would run instead (E-10).
set "NoDefaultCurrentDirectoryInExePath=1"

cd /d "%~dp0"

rem Not "where python": on a fresh Windows that finds the Store's
rem installer stub, which is not Python. Ask the interpreter itself.
python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul || (
  echo Python was not found, or is older than the app needs. Install Python 3.11+ and run Setup.bat again.
  pause & exit /b 1
)
%SystemRoot%\System32\where.exe npm >nul 2>nul || (
  echo Node.js was not found. Install Node.js LTS and run Setup.bat again.
  pause & exit /b 1
)

echo [1/4] Making the app's private Python in .venv...
rem --clear: a package an older lock named and this one does not must not
rem survive in the environment.
python -m venv --clear .venv
if errorlevel 1 (echo Could not make .venv - is the app still running? Close it and run Setup.bat again. & pause & exit /b 1)
set PY=".venv\Scripts\python.exe"

echo [2/4] Installing the locked packages (hash-checked)...
rem Two steps (decision 169, R-11): the reader's own package goes in
rem without its dependencies, because its metadata asks for the GUI build
rem of OpenCV; requirements.lock holds what it really needs.
%PY% -m pip install --require-hashes -r requirements.lock --quiet
if errorlevel 1 (echo. & echo Installing requirements.lock failed - check your internet connection. & pause & exit /b 1)
%PY% -m pip install --require-hashes --no-deps -r requirements-nodeps.lock --quiet
if errorlevel 1 (echo. & echo Installing requirements-nodeps.lock failed - check your internet connection. & pause & exit /b 1)

echo [3/4] Installing Electron (npm ci from app\package-lock.json)...
pushd app
call npm ci --no-audit --no-fund
if errorlevel 1 (popd & echo. & echo npm ci failed - check your internet connection. & pause & exit /b 1)
popd

rem After every install, so a Setup that stopped part-way leaves no stamp
rem and the app says to run it again. The stamp records the hash of each
rem lock file and of app\package-lock.json; "Start App.bat" compares them
rem every launch.
%PY% tools\lockfiles.py stamp .venv
if errorlevel 1 (echo Could not record what was installed & pause & exit /b 1)

echo [4/4] Registering the schedule and checking the records...
rem The after-install step, last: it needs the packages just installed,
rem and the stamp stays whatever it says - the packages are installed. It
rem registers the schedule only on the computer that runs it, and says why
rem not on any other. A record it names is a finding, not a failure: Setup
rem finishes, and the household waits in the app. Last, it removes the
rem test cache (.pytest_cache) earlier versions left in this folder, never
rem following a link out of it. It exits non-zero only when a step could
rem not run at all; the app tries it again at launch.
%PY% -m tracker.after_install --reason setup
if errorlevel 1 goto :after_install_failed

echo.
echo Set up. From now on, double-click "Start App.bat" - it needs no internet.
pause
exit /b 0

rem The sentence is tracker.after_install's SETUP_RETRY, word for word
rem (tests/test_build.py holds the two together).
:after_install_failed
echo.
echo The after-install step could not finish (above). Start the app: it tries again at launch.
pause
exit /b 1
