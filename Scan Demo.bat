@echo off
rem Double-click to scan the demo engagement and update demo\_manifest.xlsx
cd /d "%~dp0"
python -m tracker.scanner demo
echo.
pause
