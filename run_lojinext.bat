@echo off
TITLE LojiNext Unified Runner
COLOR 0D
echo ======================================================
echo 🚀 LOJINEXT - Elite Logistics Intelligence Startup
echo ======================================================
echo.

:: Get the directory of the script
set BASE_DIR=%~dp0

echo [~] Cleaning up stale processes (Ports 8080 and 3000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8080 ^| findstr LISTENING') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do taskkill /F /PID %%a 2>nul
echo [*] Cleanup complete.
echo.

:: 1. Start Backend in a new window
echo [~] Starting Backend Engine...
start "LOJINEXT BACKEND" cmd /k "cd /d %BASE_DIR% && echo [*] Launching FastAPI with Uvicorn... && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8080"

:: 2. Start Frontend in a new window
echo [~] Starting Frontend Engine...
start "LOJINEXT FRONTEND" cmd /k "cd /d %BASE_DIR%frontend && echo [*] Launching Vite Dev Server... && npm run dev"

echo.
echo ======================================================
echo ✨ Both engines are launching in separate windows.
echo ✨ Backend: http://localhost:8080
echo ✨ Frontend: http://localhost:3000 (Check Vite output)
echo ======================================================
echo.
pause
