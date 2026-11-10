@echo off
title Smart Restaurant - Frontend Portal
cd /d "%~dp0frontend"
echo ============================================================
echo Starting Smart Restaurant Management Platform - Frontend
echo URL: http://localhost:5173
echo ============================================================
call npm.cmd run dev
pause

