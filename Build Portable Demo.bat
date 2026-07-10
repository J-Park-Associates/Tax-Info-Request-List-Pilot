@echo off
rem ── Rebuild the portable marketing demo package ───────────────────────
rem Output: build-portable\dist\Tax Document Tracker-win32-x64\
rem Copy that whole folder to a USB stick or any Windows laptop.

cd /d "%~dp0"

echo [1/4] Freezing Python tracker API (PyInstaller)...
python -m pip install pyinstaller --quiet
python -m PyInstaller --noconfirm --clean --onedir --console --name tracker-api --distpath build-portable\py api_entry.py
if errorlevel 1 (echo PyInstaller failed & pause & exit /b 1)

echo [2/4] Packaging Electron app...
pushd app
call npm install --save-dev @electron/packager electron
call npx electron-packager . "Tax Document Tracker" --platform=win32 --arch=x64 --out="..\build-portable\dist" --overwrite
if errorlevel 1 (popd & echo electron-packager failed & pause & exit /b 1)
popd

echo [3/4] Assembling portable folder...
set PKG=build-portable\dist\Tax Document Tracker-win32-x64
if exist "%PKG%\resources\tracker-api" rmdir /s /q "%PKG%\resources\tracker-api"
xcopy /e /i /q build-portable\py\tracker-api "%PKG%\resources\tracker-api" >nul
copy /y DEMO-SCRIPT.md "%PKG%\" >nul
copy /y portable-readme.txt "%PKG%\READ ME FIRST.txt" >nul

echo [4/4] Done.
echo.
echo Portable demo: %CD%\%PKG%
echo Copy that entire folder to a USB drive or laptop and double-click
echo "Tax Document Tracker.exe".
pause
