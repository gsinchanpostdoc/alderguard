@echo off
REM setup_and_run.bat — One-command setup for alder-ipm-sim-py on Windows
REM Usage:  setup_and_run.bat

setlocal

set VENV_DIR=.venv

echo === AlderIPM-Sim Python — Setup ^& Run ===
echo.

REM 1. Create virtual environment
if exist "%VENV_DIR%\" (
    echo [skip] Virtual environment already exists at %VENV_DIR%
) else (
    echo [1/4] Creating virtual environment...
    py -m venv %VENV_DIR%
    if errorlevel 1 (
        echo ERROR: Failed to create venv. Make sure Python is installed and 'py' is on PATH.
        exit /b 1
    )
)

REM 2. Activate
echo [2/4] Activating virtual environment...
call %VENV_DIR%\Scripts\activate.bat

REM 3. Install package with dev dependencies
echo [3/4] Installing alder-ipm-sim with dev dependencies...
pip install --upgrade pip -q
pip install -e ".[app,dev]" -q
if errorlevel 1 (
    echo ERROR: pip install failed.
    exit /b 1
)

REM 4. Run tests
echo [4/4] Running test suite...
echo.
pytest tests/ -v
echo.

echo ============================================
echo   Setup complete — all tests passed!
echo ============================================
echo.
echo Next steps:
echo   %VENV_DIR%\Scripts\activate.bat
echo   alder-ipm-sim --help              # CLI overview
echo   alder-ipm-sim simulate --years 50 # run a simulation
echo   alder-ipm-sim dashboard           # launch Streamlit app
echo   pytest tests/ -v               # re-run tests
echo.
