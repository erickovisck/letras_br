@echo off
title Tradutor YouTube Music - LetrasBR
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================================
echo   LetrasBR - Servidor API
echo ========================================================
echo.

:: 1. Busca por python ou python3 com versao >= 3.10
set "PYTHON_CMD="

:: Testa python
python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :python_ok
)

:: Testa python3
python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python3"
    goto :python_ok
)

:: Testa py -3
py -3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    goto :python_ok
)

:: Testa py
py -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    goto :python_ok
)

:: Se o .venv ja existir e for compativel, podemos prosseguir direto para a execucao
if not exist ".venv\Scripts\python.exe" goto :nenhum_python
.venv\Scripts\python.exe -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 goto :iniciar_app

:nenhum_python
echo [ERRO] Nao foi encontrada nenhuma instalacao compativel do Python (3.10 ou superior)!
echo.
where python >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2^>nul') do echo Foi detectado 'python' versao %%v - incompativel.
)
where python3 >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%v in ('python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2^>nul') do echo Foi detectado 'python3' versao %%v.
)
echo.
echo Requisito: Python 3.10 ou superior no PATH.
echo Download: https://www.python.org/downloads/
echo.
pause
exit /b 1

:python_ok
:: 2. Verifica se o ambiente virtual .venv existe e e compativel; se nao, cria
if not exist ".venv\Scripts\python.exe" goto :criar_venv

.venv\Scripts\python.exe -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 goto :iniciar_app

echo [AVISO] O ambiente virtual (.venv) atual foi criado com versao inferior a 3.10.
echo Recriando .venv com %PYTHON_CMD%...
rmdir /s /q .venv

:criar_venv
echo [INFO] Ambiente virtual (.venv) nao detectado ou desatualizado.
echo [INFO] Criando ambiente virtual com %PYTHON_CMD%...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 (
    echo [ERRO] Nao foi possivel criar o ambiente virtual .venv.
    pause
    exit /b 1
)
    echo [SUCESSO] Ambiente virtual criado!
    echo.
)

:iniciar_app

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
