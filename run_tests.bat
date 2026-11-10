@echo off
title Smart Restaurant - Test Suite
cd /d "%~dp0backend"
echo ============================================================
echo Running Automated Pytest Suite
echo ============================================================
.\venv\Scripts\python.exe -m pytest -v
pause

