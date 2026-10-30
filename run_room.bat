@echo off
title BOT Room 3D Server
cd /d "%~dp0"
echo ===================================================
echo   BOT Room 3D - Sujiraporn Cafe' Web Server
echo ===================================================
echo.
echo Starting web server on http://localhost:8099 ...

if exist "C:\Users\sager\.platformio\penv\Scripts\python.exe" (
    set "PYTHON_EXE=C:\Users\sager\.platformio\penv\Scripts\python.exe"
) else if exist "C:\Users\PONG\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" (
    set "PYTHON_EXE=C:\Users\PONG\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

start "" http://localhost:8099/
"%PYTHON_EXE%" server.py
pause
