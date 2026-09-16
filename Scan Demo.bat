@echo off
rem Double-click to scan the demo engagement and update demo\_manifest.xlsx
cd /d "%~dp0"
if not exist "demo\_manifest.xlsx" (
  echo There is no demo manifest yet. Build one first with:
  echo.
  echo     python demo\demo_manifest.py
  echo.
  echo then run this again.
  pause
  exit /b 1
)
python -m tracker.scanner demo
echo.
pause
