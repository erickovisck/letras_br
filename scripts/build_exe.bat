@echo off
title Compilar LetrasBR.exe
chcp 65001 > nul
cd /d "%~dp0\.."

echo ========================================================
echo   Compilando LetrasBR.exe (Nativo Win32 GUI)
echo ========================================================
echo.

set "CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" (
    echo [ERRO] Compilador C# [csc.exe] nao encontrado no Windows.
    pause
    exit /b 1
)

echo Compilando scripts\Launcher.cs com icone assets\app_icon.ico...
"%CSC%" /nologo /target:winexe /win32icon:assets\app_icon.ico /out:LetrasBR.exe scripts\Launcher.cs

if %errorlevel% equ 0 (
    echo.
    echo [SUCESSO] LetrasBR.exe compilado com exito na raiz do projeto!
) else (
    echo.
    echo [ERRO] Falha ao compilar LetrasBR.exe.
)
echo.
pause
