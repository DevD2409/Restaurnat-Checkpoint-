@echo off
title Launch Smart Restaurant Ecosystem
echo ============================================================
echo Launching Smart Restaurant Management Platform Ecosystem
echo ============================================================
start "SRMP Backend" cmd /k "cd /d %~dp0backend && .\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 /nobreak > nul
start "SRMP Frontend" cmd /k "cd /d %~dp0frontend && npm.cmd run dev"
echo Both servers launched in separate windows!
echo Backend:  http://localhost:8000/docs
echo Frontend: http://localhost:5173
echo ============================================================
pause

