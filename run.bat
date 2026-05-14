@echo off
REM ============================================================
REM  Virtual Oscilloscope — one-click launcher
REM  First run: creates venv and installs pip dependencies.
REM  Later runs: just launches main.py.
REM
REM  NOTE: This does NOT install NI-DAQmx or NI-VISA drivers —
REM  those are separate downloads from ni.com and required for
REM  the DAQ card and signal generator. Pip packages alone
REM  cannot talk to the hardware without them.
REM ============================================================

setlocal
cd /d "%~dp0"

REM ----- pick a Python interpreter -----
set "PY="
where python >nul 2>nul
if not errorlevel 1 set "PY=python"
if "%PY%"=="" (
    where py >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)
if "%PY%"=="" (
    echo.
    echo [ERROR] Python is not installed or not on PATH.
    echo Install Python 3.11+ from https://www.python.org/downloads/
    echo During install, check "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

REM ----- create venv on first run -----
if not exist "venv\Scripts\python.exe" (
    echo.
    echo [setup] First-time setup — creating virtual environment...
    %PY% -m venv venv
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )

    echo [setup] Upgrading pip...
    "venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 (
        echo.
        echo [ERROR] pip upgrade failed.
        pause
        exit /b 1
    )

    echo [setup] Installing dependencies (PyQt5, pyqtgraph, nidaqmx, numpy, PyVISA, PyYAML, matplotlib)...
    "venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Dependency install failed. See output above.
        pause
        exit /b 1
    )

    echo.
    echo [setup] Done. Launching the oscilloscope...
    echo         To refresh dependencies in the future, delete the "venv" folder and run this again.
    echo.
)

REM ----- launch the app -----
"venv\Scripts\python.exe" main.py
set "RC=%errorlevel%"

if not "%RC%"=="0" (
    echo.
    echo [exit] main.py returned code %RC%
    pause
)

endlocal
exit /b %RC%
