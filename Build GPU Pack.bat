@echo off
rem -- Build the graphics card pack (decision 169) ----------------------------
rem Output: <OUT>\gpu-runtime\ - one folder of NVIDIA libraries (about 1.6 GB).
rem Copy it beside tracker-api.exe, in the app's resources\tracker-api\
rem folder, on a machine with a supported NVIDIA card. Nowhere else: without
rem it the reader reads on the processor, which every machine can.
rem
rem It downloads the NVIDIA wheels pinned in requirements-gpu.txt, and only
rem those (--no-deps), into an environment of its own; tools\gpu_pack.py
rem then copies their libraries out. "Build App.bat" never runs this: the
rem app is one build, and the pack is an optional folder.

cd /d "%~dp0"
set OUT=build-portable
set VENV=%OUT%\gpu-venv

python -m venv --clear "%VENV%"
if errorlevel 1 (echo Could not create the pack's environment & call :wait & exit /b 1)
set PY="%VENV%\Scripts\python.exe"
%PY% -m pip install --no-deps -r requirements-gpu.txt --quiet
if errorlevel 1 (echo Installing requirements-gpu.txt failed & call :wait & exit /b 1)
for /f "usebackq delims=" %%i in (`%PY% -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"`) do set SITE=%%i
%PY% tools\gpu_pack.py "%SITE%" "%OUT%\gpu-runtime"
if errorlevel 1 (echo The pack could not be made & call :wait & exit /b 1)
echo.
echo Graphics card pack: "%CD%\%OUT%\gpu-runtime"
echo Copy that folder beside tracker-api.exe on the machine with the NVIDIA card.
call :wait
exit /b 0

rem Every exit goes through here, so a person gets a window they can read.
:wait
if not defined TRACKER_BUILD_NONINTERACTIVE pause
exit /b 0
