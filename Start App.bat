@echo off
rem ── Tax Document Tracker: run the app from source ─────────────────
rem Double-click to start. First run installs Electron (needs internet
rem once); every run after that is instant and fully offline.

cd /d "%~dp0"

where python >nul 2>nul || (
  echo Python was not found. Install Python 3.11+ and re-run.
  pause & exit /b 1
)
where npm >nul 2>nul || (
  echo Node.js was not found. Install Node.js LTS and re-run.
  pause & exit /b 1
)

if not exist "app\node_modules\electron" (
  echo First-time setup: installing Electron ^(a few minutes^)...
  pushd app
  call npm install --save-dev electron
  if errorlevel 1 (echo. & echo npm install failed - check your internet connection. & pause & exit /b 1)
  popd
)

pushd app
call npx electron .
popd
