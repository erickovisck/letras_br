@echo off
title LetrasBR - Configuracao do Ambiente
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================================
echo   LetrasBR - Instalador e Configurador de Ambiente
echo ========================================================
echo.

:: 1. Verifica se o Python esta instalado
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERRO] Python nao foi encontrado no sistema!
        echo Por favor, instale o Python 3.10 ou superior com a opcao 'Add Python to PATH' marcada.
        echo Download: https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=py -3"
) else (
    set "PYTHON_CMD=python"
)

echo [1/3] Python detectado:
%PYTHON_CMD% --version
echo.

:: 2. Cria ou valida ambiente virtual
echo [2/3] Configurando ambiente virtual (.venv)...
if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual em .venv...
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao criar o ambiente virtual .venv.
        pause
        exit /b 1
    )
    echo Ambiente virtual criado com sucesso!
) else (
    echo Ambiente virtual .venv existente detectado.
)
echo.

:: 3. Instala dependencias
echo [3/3] Instalando/atualizando dependencias (FastAPI, Uvicorn, ytmusicapi, etc.)...
.venv\Scripts\pip.exe install -r letrasbr_api\requirements.txt
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao instalar dependencias do requirements.txt.
    pause
    exit /b 1
)
echo.

:: 4. Registra protocolo personalizado no Windows
echo [4/4] Registrando protocolo letrasbr:// no Windows...
.venv\Scripts\python.exe letrasbr_api\protocol.py
echo.

echo ========================================================
echo   [SUCESSO] Configuracao concluida com exito!
echo   Voce ja pode iniciar dando dois cliques em 'iniciar_servidor.bat'.
echo ========================================================
echo.
pause
