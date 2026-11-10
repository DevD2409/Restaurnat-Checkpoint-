@echo off
title Smart Restaurant - Backend API
cd /d "%~dp0backend"
echo ============================================================
echo Starting Smart Restaurant Management Platform - Backend API
echo Host: http://localhost:8000
echo Docs: http://localhost:8000/docs
echo ============================================================
.\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
pause

