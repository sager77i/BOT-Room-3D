@echo off
title BOT Room 3D Relay AI Engine
cd /d "%~dp0"
echo ===================================================
echo   BOT Room 3D - Multi-Agent Relay Engine
echo ===================================================
echo.
echo Starting dialogue relay with Hermes OpenRouter...

if exist "C:\Users\PONG\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" (
    set "PYTHON_EXE=C:\Users\PONG\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" relay.py
pause
