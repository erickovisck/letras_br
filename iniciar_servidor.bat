@echo off
title Tradutor YouTube Music - LetrasBR API
chcp 65001 > nul
cd /d "%~dp0"
echo ========================================================
echo   Iniciando API Tradutor YouTube Music (LetrasBR)
echo ========================================================
echo.
.venv\Scripts\python.exe run_api.py
pause
