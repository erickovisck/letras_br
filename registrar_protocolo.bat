@echo off
title Registrar Protocolo LetrasBR
chcp 65001 > nul
cd /d "%~dp0"
echo ========================================================
echo   Registrando Protocolo letrasbr:// no Windows
echo ========================================================
echo.
.venv\Scripts\python.exe letrasbr_api\protocol.py
echo.
echo Concluido! Agora o botao "Iniciar API" na extensao podera
echo abrir o servidor e a janela flutuante automaticamente.
echo.
pause
