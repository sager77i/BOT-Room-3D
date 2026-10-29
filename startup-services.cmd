@echo off
rem Startup launcher for 9Router, Bot Room web server, Bot Room relay, and Bot Room proxy
timeout /t 5 /nobreak >nul

rem 1. Start 9Router
start "" "C:\Users\PONG\AppData\Local\hermes\node\9router.cmd" -t -n --skip-update

rem 2. Start Hermes Web Dashboard on Port 9119 (for Tailscale https://nuc.tail91953.ts.net/)
start "" /b "C:\Users\PONG\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe" dashboard --port 9119 --host 127.0.0.1 --no-open --skip-build

rem 3. Start Bot Room HTTP Server on Port 8099
start "" /b "C:\Users\PONG\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" "C:\Users\PONG\bot-room\server.py"

rem 4. Start Bot Room Relay AI Engine
timeout /t 5 /nobreak >nul
start "" /b "C:\Users\PONG\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" "C:\Users\PONG\bot-room\relay.py"

rem 5. Start Bot Room Proxy (port 80 -> Bot Room 8099 / Usage Monitor 3001)
start "proxy" /b "C:\Users\PONG\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" "C:\Users\PONG\bot-room\proxy.py"
tailscale serve --bg http://127.0.0.1:80

rem 6. Start Hermes Gateway (for Telegram, Discord, etc.)
start "" /b "C:\Users\PONG\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe" gateway

exit /b 0
