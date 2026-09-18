@echo off
rem ── Run the desktop app from source ────────────────────────────────
rem Double-click to start. First run installs Electron (needs internet
rem once), the exact version app\package-lock.json pins; every run after
rem that is instant and fully offline.

cd /d "%~dp0"

rem Not "where python": on a fresh Windows that finds the Store's
rem installer stub, which is not Python. Ask the interpreter itself.
python -c "import sys" >nul 2>nul || (
  echo Python was not found. Install Python 3.11+ and re-run.
  pause & exit /b 1
)
where npm >nul 2>nul || (
  echo Node.js was not found. Install Node.js LTS and re-run.
  pause & exit /b 1
)

rem The Python packages requirements.txt pins, installed when they are not
rem (a satisfied requirement costs a second and needs no network).
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (echo. & echo pip install failed - check your internet connection. & pause & exit /b 1)

if not exist "app\node_modules\electron" (
  echo First-time setup: installing Electron ^(a few minutes^)...
  pushd app
  call npm ci --no-audit --no-fund
  if errorlevel 1 (echo. & echo npm ci failed - check your internet connection. & pause & exit /b 1)
  popd
)

rem Electron is started through its own entry script, not the npx shim:
rem the shim breaks when the folder's path contains an ampersand (as a
rem firm's name often does). The script downloads the binary on first run.
pushd app
node node_modules\electron\cli.js .
popd
