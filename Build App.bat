@echo off
rem ── Build the portable app package ─────────────────────────────────────
rem Output: <OUT>\dist\<productName>-<PLATFORM>-<ARCH>\ (the variables below)
rem Put that whole folder on the designated machine: today one machine runs a
rem clients root, and docs\runbook.md section 1 says which and why.
rem
rem Reproducible: the Python packages (requirements.lock and
rem requirements-build.lock, the whole tree by version and by hash), the
rem Electron packages (app\package-lock.json, installed with npm ci) and the
rem freeze itself (api_entry.spec) are all pinned in the commit being built,
rem and BUILD-INFO.txt records which commit and which tools made the package.
rem
rem A person double-clicks this, so it waits for a key before every exit and
rem the window stays up long enough to read. CI has nobody to press one:
rem setting TRACKER_BUILD_NONINTERACTIVE (to anything) makes every wait return
rem at once and changes nothing else. That name is read in exactly one place,
rem the ":wait" label at the end of this file.

rem Before any other command: cmd would otherwise look for python, node, npm
rem and git in this folder before the search path, so a file dropped here
rem named like one of them would run instead (E-10).
set "NoDefaultCurrentDirectoryInExePath=1"

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
rem the two locks. PyInstaller follows every import it can find,
rem including a library's optional ones, so freezing from the machine's
rem Python ships whatever else happens to be installed there (a first run
rem from the firm's machine bundled pandas, numpy and two database drivers).
set VENV=%OUT%\venv
rem Made fresh every build: a package once installed into a reused venv
rem would be frozen into every later package.
python -m venv --clear "%VENV%"
if errorlevel 1 (echo Could not create the build environment & call :wait & exit /b 1)
set PY="%VENV%\Scripts\python.exe"
rem The locks pin the whole tree (decision 137), so two builds of one
rem commit freeze the same code, and name the SHA-256 of every file
rem (decision 191), so a file replaced at a pinned version is refused.
rem --require-hashes also refuses any package the locks do not name.
%PY% -m pip install --require-hashes -r requirements.lock -r requirements-build.lock --quiet
if errorlevel 1 (echo Installing requirements.lock and requirements-build.lock failed & call :wait & exit /b 1)
rem The reader's own package, without its dependencies (decision 169,
rem R-11): its metadata asks for the GUI build of OpenCV, which the app
rem does not ship; requirements.lock holds what it really needs.
%PY% -m pip install --require-hashes --no-deps -r requirements-nodeps.lock --quiet
if errorlevel 1 (echo Installing requirements-nodeps.lock failed & call :wait & exit /b 1)
%PY% -m PyInstaller --noconfirm --clean --distpath %OUT%\py --workpath %OUT%\pyi-work api_entry.spec
if errorlevel 1 (echo PyInstaller failed & call :wait & exit /b 1)

echo [2/4] Packaging Electron app (npm ci from package-lock.json)...
pushd app
call npm ci --no-audit --no-fund
if errorlevel 1 (popd & echo npm ci failed - check your internet connection. & call :wait & exit /b 1)
rem The packager is run through its entry script, not the npx shim: the
rem shim breaks when the folder's path contains an ampersand. --icon is
rem relative to app\ (pushd above) and writes the console icon into the .exe.
node node_modules\@electron\packager\bin\electron-packager.mjs . "%NAME%" --platform=%PLATFORM% --arch=%ARCH% --out="..\%OUT%\dist" --icon=assets\icon.ico --overwrite
if errorlevel 1 (popd & echo electron-packager failed & call :wait & exit /b 1)
popd

echo [3/4] Assembling portable folder...
set PKG=%OUT%\dist\%NAME%-%PLATFORM%-%ARCH%
if exist "%PKG%\resources\%API%" rmdir /s /q "%PKG%\resources\%API%"
rem robocopy, not xcopy: xcopy gives up on long paths (a deep checkout plus
rem the package's own depth is enough) and the copy would be silently
rem incomplete. robocopy's exit codes below 8 all mean "copied".
%SystemRoot%\System32\robocopy.exe "%OUT%\py\%API%" "%PKG%\resources\%API%" /e /nfl /ndl /njh /njs /np >nul
if errorlevel 8 (echo Copying the frozen API into the package failed & call :wait & exit /b 1)
if not exist "%PKG%\resources\%API%\%API%.exe" (echo The package has no %API%.exe & call :wait & exit /b 1)

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
echo Put that entire folder on the designated machine - today one machine
echo runs a clients root, docs\runbook.md section 1 - and double-click
echo "%NAME%.exe" there.
call :wait
exit /b 0

rem The one reader of the switch this file's header names. Every exit above
rem goes through here, so a person still gets the window they can read and a
rem build with nobody watching still ends.
:wait
if not defined TRACKER_BUILD_NONINTERACTIVE pause
exit /b 0
