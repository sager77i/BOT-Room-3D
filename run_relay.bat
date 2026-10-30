@echo off
title BOT Room 3D Relay AI Engine
cd /d "%~dp0"
echo ===================================================
echo   BOT Room 3D - Multi-Agent Relay Engine
echo ===================================================
echo.
echo Starting dialogue relay with OpenRouter AI...

if exist "C:\Users\sager\.platformio\penv\Scripts\python.exe" (
    set "PYTHON_EXE=C:\Users\sager\.platformio\penv\Scripts\python.exe"
) else if exist "C:\Users\PONG\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" (
    set "PYTHON_EXE=C:\Users\PONG\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" relay.py
pause
