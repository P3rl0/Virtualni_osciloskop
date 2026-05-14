@echo off
REM Virtual Oscilloscope - one-click launcher.
REM First run: creates venv and installs pip dependencies.
REM Later runs: just launches main.py.
REM
REM NOTE: This does NOT install NI-DAQmx or NI-VISA drivers.
REM Those are separate downloads from ni.com and are required
REM for the DAQ card and signal generator to communicate.

setlocal EnableExtensions
cd /d "%~dp0"

echo Virtual Oscilloscope launcher
echo Working directory: %CD%
echo.

REM ----- pick a Python interpreter -----
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
    where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
    echo [ERROR] Python is not installed or not on PATH.
    echo Install Python 3.11+ from https://www.python.org/downloads/
    echo During install, tick "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

echo Using Python interpreter: %PY%

REM ----- first-time setup -----
if not exist "venv\Scripts\python.exe" (
    echo.
    echo First run detected. Creating virtual environment...
    %PY% -m venv venv
    if errorlevel 1 (
        echo [ERROR] venv creation failed.
        pause
        exit /b 1
    )

    echo Upgrading pip...
    "venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 (
        echo [ERROR] pip upgrade failed.
        pause
        exit /b 1
    )

    echo Installing dependencies. This may take several minutes...
    "venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency install failed. See output above.
        pause
        exit /b 1
    )

    echo.
    echo Setup complete. Launching the app...
    echo To refresh dependencies in the future, delete the "venv" folder and run this again.
    echo.
)

REM ----- run -----
echo Launching main.py
"venv\Scripts\python.exe" main.py
set "RC=%errorlevel%"

if not "%RC%"=="0" (
    echo.
    echo main.py exited with code %RC%
    pause
)

exit /b %RC%