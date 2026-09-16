@echo off
title Tradutor YouTube Music - LetrasBR
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================================
echo   LetrasBR - Servidor API & Overlay Flutuante
echo ========================================================
echo.

:: 1. Verifica se o Python esta instalado
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERRO] Python nao foi encontrado no sistema!
        echo Por favor, instale o Python 3.10 ou superior marcando 'Add Python to PATH'.
        echo Download: https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=py -3"
) else (
    set "PYTHON_CMD=python"
)

:: 2. Verifica se o ambiente virtual .venv existe; se nao, cria
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Ambiente virtual (.venv) nao detectado.
    echo [INFO] Criando ambiente virtual automaticamente...
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERRO] Nao foi possivel criar o ambiente virtual .venv.
        pause
        exit /b 1
    )
    echo [SUCESSO] Ambiente virtual criado!
    echo.
)

:: 3. Verifica se as dependencias estao instaladas; se nao, instala
.venv\Scripts\python.exe -c "import fastapi, uvicorn, requests, bs4, ytmusicapi" >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Dependencias ausentes ou desatualizadas.
    echo [INFO] Instalando pacotes necessarios de letrasbr_api\requirements.txt...
    echo [INFO] Aguarde um momento...
    .venv\Scripts\pip.exe install -r letrasbr_api\requirements.txt
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao instalar dependencias.
        pause
        exit /b 1
    )
    echo [SUCESSO] Dependencias instaladas com sucesso!
    echo.
    :: Registra protocolo caso seja a primeira instalacao
    .venv\Scripts\python.exe letrasbr_api\protocol.py >nul 2>nul
)

:: 4. Inicia o servidor e o overlay flutuante
echo ========================================================
echo   Iniciando API e Overlay Flutuante...
echo ========================================================
echo.
.venv\Scripts\python.exe run_api.py
if %errorlevel% neq 0 (
    echo.
    echo [INFO] Processo finalizado com codigo %errorlevel%.
    pause
)
