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

rem Stamp the build so anyone holding the folder can tell what is inside it.
> "%PKG%\BUILD-INFO.txt" (
  echo Tax Document Tracker - portable marketing demo
  echo Version:       1.1.0
  echo Built:         %DATE% %TIME%
  echo Built on:      %COMPUTERNAME%
  echo Cloud support: OneDrive AND Google Drive
  echo.
  echo v1.1.0 adds Google Drive support. Online-only placeholder files are
  echo detected on both services and never force-downloaded, Google Drive
  echo .tmp.drive* transfer temps are ignored, and Google-native files
  echo ^(.gdoc / .gsheet^) are rejected with instructions telling the client
  echo to upload an exported PDF or Excel copy instead.
)

echo [4/4] Done.
echo.
echo Portable demo: %CD%\%PKG%
echo Build stamp:   BUILD-INFO.txt  (v1.1.0 - OneDrive + Google Drive)
echo Copy that entire folder to a USB drive or laptop and double-click
echo "Tax Document Tracker.exe".
pause
