@echo off
rem ── Build the portable app package ─────────────────────────────────────
rem Output: <OUT>\dist\<productName>-<PLATFORM>-<ARCH>\ (the variables below)
rem Copy that whole folder to a USB stick or any Windows laptop.
rem
rem Reproducible: the Python packages (requirements-build.txt), the Electron
rem packages (app\package-lock.json, installed with npm ci) and the freeze
rem itself (api_entry.spec) are all pinned in the commit being built, and
rem BUILD-INFO.txt records which commit and which tools made the package.

cd /d "%~dp0"
set OUT=build-portable
set PLATFORM=win32
set ARCH=x64

rem The product's name and the API executable's name live in app\package.json;
rem the Electron shell reads the same file, so nothing is typed twice.
for /f "usebackq delims=" %%i in (`node -p "require('./app/package.json').productName"`) do set NAME=%%i
for /f "usebackq delims=" %%i in (`node -p "require('./app/package.json').config.apiName"`) do set API=%%i

echo [1/4] Freezing Python tracker API (PyInstaller, api_entry.spec)...
python -m pip install -r requirements-build.txt --quiet
python -m PyInstaller --noconfirm --clean --distpath %OUT%\py --workpath %OUT%\pyi-work api_entry.spec
if errorlevel 1 (echo PyInstaller failed & pause & exit /b 1)

echo [2/4] Packaging Electron app (npm ci from package-lock.json)...
pushd app
call npm ci --no-audit --no-fund
if errorlevel 1 (popd & echo npm ci failed - check your internet connection. & pause & exit /b 1)
call npx electron-packager . "%NAME%" --platform=%PLATFORM% --arch=%ARCH% --out="..\%OUT%\dist" --overwrite
if errorlevel 1 (popd & echo electron-packager failed & pause & exit /b 1)
popd

echo [3/4] Assembling portable folder...
set PKG=%OUT%\dist\%NAME%-%PLATFORM%-%ARCH%
if exist "%PKG%\resources\%API%" rmdir /s /q "%PKG%\resources\%API%"
xcopy /e /i /q %OUT%\py\%API% "%PKG%\resources\%API%" >nul

set COMMIT=(not a git checkout)
for /f "usebackq delims=" %%i in (`git rev-parse HEAD 2^>nul`) do set COMMIT=%%i
for /f "usebackq delims=" %%i in (`python --version`) do set PYVER=%%i
for /f "usebackq delims=" %%i in (`node --version`) do set NODEVER=%%i
for /f "usebackq delims=" %%i in (`npm --version`) do set NPMVER=%%i
> "%PKG%\BUILD-INFO.txt" (
  echo %NAME%
  echo Built:    %DATE% %TIME%
  echo Built on: %COMPUTERNAME%
  echo Commit:   %COMMIT%
  echo Python:   %PYVER%
  echo Node:     %NODEVER%
  echo npm:      %NPMVER%
  echo.
  echo Python packages frozen ^(pip freeze^):
  python -m pip freeze
)

echo [4/4] Done.
echo.
echo Portable app: %CD%\%PKG%
echo Copy that entire folder to a USB drive or laptop and double-click
echo "%NAME%.exe".
pause
