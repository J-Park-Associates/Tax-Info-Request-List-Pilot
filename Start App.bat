@echo off
rem ── Run the desktop app from source ────────────────────────────────
rem Double-click to start. First run installs Electron (needs internet
rem once), the exact version app\package-lock.json pins; every run after
rem that is instant and fully offline.

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
  call npm ci --no-audit --no-fund
  if errorlevel 1 (echo. & echo npm ci failed - check your internet connection. & pause & exit /b 1)
  popd
)

pushd app
call npx electron .
popd
