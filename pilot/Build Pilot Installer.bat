@echo off
rem ── Build the Tax Document Tracker Pilot installer ─────────────────────
rem Output: build-portable\installer\Tax-Document-Tracker-Pilot-Setup-<version>.exe
rem
rem The installer is exactly what is committed: this refuses a tree with any
rem uncommitted change (pilot decision P13). The version comes from
rem app\renderer\pilot-content.js, its one home; the commit is recorded by
rem Build App.bat in BUILD-INFO.txt. Nothing is stamped into any file.
rem
rem Needs what Build App.bat needs (Python, Node, git) plus Inno Setup 6.3 or later.
rem A person double-clicks this, so it waits for a key before every exit.
rem TRACKER_BUILD_NONINTERACTIVE (set by any caller) makes the wait return at
rem once; that name is read in exactly one place, the ":wait" label below.

rem Before any other command: cmd would otherwise look for git, node and the
rem tools in this folder before the search path (E-10).
set "NoDefaultCurrentDirectoryInExePath=1"

set "CALLER_NONINTERACTIVE=%TRACKER_BUILD_NONINTERACTIVE%"
cd /d "%~dp0.."
if errorlevel 1 (echo Could not open the repository folder & call :wait & exit /b 1)

echo [1/5] Checking that everything is committed...
git rev-parse --verify HEAD >nul 2>&1
if errorlevel 1 (
  echo This folder is not a git checkout, or git is not installed: the installer must be built from a commit.
  call :wait
  exit /b 1
)
set "DIRTY="
for /f "delims=" %%i in ('git status --porcelain') do set DIRTY=1
if defined DIRTY (
  echo Commit or discard your changes first: the installer must be built from exactly what is committed.
  call :wait
  exit /b 1
)

echo [2/5] Reading the version from pilot-content.js...
set "VER="
for /f "usebackq delims=" %%i in (`node -p "require('./app/renderer/pilot-content.js').edition.version"`) do set VER=%%i
if not defined VER (echo Could not read the version from app\renderer\pilot-content.js & call :wait & exit /b 1)

echo [3/5] Building the app package (Build App.bat)...
set TRACKER_BUILD_NONINTERACTIVE=1
call "Build App.bat"
set BUILD_RESULT=%errorlevel%
set "TRACKER_BUILD_NONINTERACTIVE=%CALLER_NONINTERACTIVE%"
if not "%BUILD_RESULT%"=="0" (echo Build App.bat failed & call :wait & exit /b 1)
for /f "usebackq delims=" %%i in (`node -p "require('./app/package.json').productName"`) do set NAME=%%i
set "PACKAGED=%CD%\build-portable\dist\%NAME%-win32-x64"
if not exist "%PACKAGED%\%NAME%.exe" (echo The packaged program is missing: %PACKAGED%\%NAME%.exe & call :wait & exit /b 1)

echo [4/5] Finding Inno Setup 6...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
  echo Inno Setup 6.3 or later is not installed. Install it from jrsoftware.org ^(free^), then run this again.
  call :wait
  exit /b 1
)

echo [5/5] Compiling the installer...
"%ISCC%" /DAppVersion=%VER% /DSourceDir="%PACKAGED%" pilot\installer\setup.iss
if errorlevel 1 (echo Inno Setup failed & call :wait & exit /b 1)

set "INSTALLER=%CD%\build-portable\installer\Tax-Document-Tracker-Pilot-Setup-%VER%.exe"
if not exist "%INSTALLER%" (echo The installer was not produced: %INSTALLER% & call :wait & exit /b 1)
echo.
echo Installer: %INSTALLER%
%SystemRoot%\System32\certutil.exe -hashfile "%INSTALLER%" SHA256
echo.
echo Tag this commit pilot-%VER% (never v...)
call :wait
exit /b 0

rem The one reader of the switch this file's header names. Every exit above
rem goes through here.
:wait
if not defined CALLER_NONINTERACTIVE pause
exit /b 0
