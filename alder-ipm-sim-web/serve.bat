@echo off
REM serve.bat — Start a local server for alder-ipm-sim-web (Windows)
REM Usage:  serve.bat [port]

cd /d "%~dp0"
set PORT=%1
if "%PORT%"=="" set PORT=8080
echo Starting alder-ipm-sim-web on http://localhost:%PORT%
py serve.py %PORT%
