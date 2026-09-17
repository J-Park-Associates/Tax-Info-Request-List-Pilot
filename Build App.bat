@echo off
rem ── Build the portable app package ─────────────────────────────────────
rem Output: <OUT>\dist\<productName>-<PLATFORM>-<ARCH>\ (the variables below)
rem Copy that whole folder to a USB stick or any Windows laptop.

cd /d "%~dp0"
set OUT=build-portable
set PLATFORM=win32
set ARCH=x64

rem The product's name and the API executable's name live in app\package.json;
rem the Electron shell reads the same file, so nothing is typed twice.
for /f "usebackq delims=" %%i in (`node -p "require('./app/package.json').productName"`) do set NAME=%%i
for /f "usebackq delims=" %%i in (`node -p "require('./app/package.json').config.apiName"`) do set API=%%i

echo [1/4] Freezing Python tracker API (PyInstaller)...
python -m pip install pyinstaller --quiet
python -m PyInstaller --noconfirm --clean --onedir --console --name %API% --distpath %OUT%\py api_entry.py
if errorlevel 1 (echo PyInstaller failed & pause & exit /b 1)

echo [2/4] Packaging Electron app...
pushd app
call npm install --save-dev @electron/packager electron
call npx electron-packager . "%NAME%" --platform=%PLATFORM% --arch=%ARCH% --out="..\%OUT%\dist" --overwrite
if errorlevel 1 (popd & echo electron-packager failed & pause & exit /b 1)
popd

echo [3/4] Assembling portable folder...
set PKG=%OUT%\dist\%NAME%-%PLATFORM%-%ARCH%
if exist "%PKG%\resources\%API%" rmdir /s /q "%PKG%\resources\%API%"
xcopy /e /i /q %OUT%\py\%API% "%PKG%\resources\%API%" >nul

> "%PKG%\BUILD-INFO.txt" (
  echo %NAME%
  echo Built:    %DATE% %TIME%
  echo Built on: %COMPUTERNAME%
)

echo [4/4] Done.
echo.
echo Portable app: %CD%\%PKG%
echo Copy that entire folder to a USB drive or laptop and double-click
echo "%NAME%.exe".
pause
