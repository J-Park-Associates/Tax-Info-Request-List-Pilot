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
rem The freeze runs in its own virtual environment holding exactly
rem requirements-build.txt. PyInstaller follows every import it can find,
rem including a library's optional ones, so freezing from the machine's
rem Python ships whatever else happens to be installed there (a first run
rem from the firm's machine bundled pandas, numpy and two database drivers).
set VENV=%OUT%\venv
rem Made fresh every build: a package once installed into a reused venv
rem would be frozen into every later package.
python -m venv --clear "%VENV%"
if errorlevel 1 (echo Could not create the build environment & pause & exit /b 1)
set PY="%VENV%\Scripts\python.exe"
%PY% -m pip install -r requirements-build.txt --quiet
if errorlevel 1 (echo Installing requirements-build.txt failed & pause & exit /b 1)
%PY% -m PyInstaller --noconfirm --clean --distpath %OUT%\py --workpath %OUT%\pyi-work api_entry.spec
if errorlevel 1 (echo PyInstaller failed & pause & exit /b 1)

echo [2/4] Packaging Electron app (npm ci from package-lock.json)...
pushd app
call npm ci --no-audit --no-fund
if errorlevel 1 (popd & echo npm ci failed - check your internet connection. & pause & exit /b 1)
rem The packager is run through its entry script, not the npx shim: the
rem shim breaks when the folder's path contains an ampersand.
node node_modules\@electron\packager\bin\electron-packager.mjs . "%NAME%" --platform=%PLATFORM% --arch=%ARCH% --out="..\%OUT%\dist" --overwrite
if errorlevel 1 (popd & echo electron-packager failed & pause & exit /b 1)
popd

echo [3/4] Assembling portable folder...
set PKG=%OUT%\dist\%NAME%-%PLATFORM%-%ARCH%
if exist "%PKG%\resources\%API%" rmdir /s /q "%PKG%\resources\%API%"
rem robocopy, not xcopy: xcopy gives up on long paths (a deep checkout plus
rem the package's own depth is enough) and the copy would be silently
rem incomplete. robocopy's exit codes below 8 all mean "copied".
robocopy "%OUT%\py\%API%" "%PKG%\resources\%API%" /e /nfl /ndl /njh /njs /np >nul
if errorlevel 8 (echo Copying the frozen API into the package failed & pause & exit /b 1)
if not exist "%PKG%\resources\%API%\%API%.exe" (echo The package has no %API%.exe & pause & exit /b 1)

rem No parentheses in this value: it is expanded inside the parenthesised
rem block below, where a ")" would end the block early.
set COMMIT=not a git checkout
for /f "usebackq delims=" %%i in (`git rev-parse HEAD 2^>nul`) do set COMMIT=%%i
rem A package made from a tree with uncommitted changes is not the commit
rem it names; BUILD-INFO.txt says so rather than claim otherwise.
for /f "usebackq delims=" %%i in (`git status --porcelain 2^>nul`) do set COMMIT=%COMMIT% plus uncommitted changes
for /f "usebackq delims=" %%i in (`%PY% --version`) do set PYVER=%%i
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
  %PY% -m pip freeze
)

echo [4/4] Done.
echo.
echo Portable app: "%CD%\%PKG%"
echo Copy that entire folder to a USB drive or laptop and double-click
echo "%NAME%.exe".
pause
