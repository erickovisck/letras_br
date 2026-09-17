@echo off
title Tradutor YouTube Music - LetrasBR
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================================
echo   LetrasBR - Servidor API
echo ========================================================
echo.

:: Se o .venv ja existir e for compativel, podemos prosseguir direto para a execucao
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 goto :iniciar_app
)

set "INSTALL_ATTEMPTED=0"

:buscar_python
set "PYTHON_CMD="

:: 1. Busca por python, python3, python3.10 e variacoes com versao >= 3.10
call :test_python "python"
if defined PYTHON_CMD goto :python_ok

call :test_python "python3"
if defined PYTHON_CMD goto :python_ok

call :test_python "python3.10"
if defined PYTHON_CMD goto :python_ok

call :test_python "python3.11"
if defined PYTHON_CMD goto :python_ok

call :test_python "python3.12"
if defined PYTHON_CMD goto :python_ok

call :test_python "python3.13"
if defined PYTHON_CMD goto :python_ok

call :test_python "py -3.10"
if defined PYTHON_CMD goto :python_ok

call :test_python "py -3.11"
if defined PYTHON_CMD goto :python_ok

call :test_python "py -3.12"
if defined PYTHON_CMD goto :python_ok

call :test_python "py -3.13"
if defined PYTHON_CMD goto :python_ok

call :test_python "py -3"
if defined PYTHON_CMD goto :python_ok

call :test_python "py"
if defined PYTHON_CMD goto :python_ok

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    call :test_python "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    if defined PYTHON_CMD goto :python_ok
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    call :test_python "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    if defined PYTHON_CMD goto :python_ok
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    call :test_python "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    if defined PYTHON_CMD goto :python_ok
)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    call :test_python "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    if defined PYTHON_CMD goto :python_ok
)
if exist "%ProgramFiles%\Python310\python.exe" (
    call :test_python "%ProgramFiles%\Python310\python.exe"
    if defined PYTHON_CMD goto :python_ok
)
if exist "%ProgramFiles%\Python311\python.exe" (
    call :test_python "%ProgramFiles%\Python311\python.exe"
    if defined PYTHON_CMD goto :python_ok
)
if exist "%ProgramFiles%\Python312\python.exe" (
    call :test_python "%ProgramFiles%\Python312\python.exe"
    if defined PYTHON_CMD goto :python_ok
)
if exist "%ProgramFiles%\Python313\python.exe" (
    call :test_python "%ProgramFiles%\Python313\python.exe"
    if defined PYTHON_CMD goto :python_ok
)

:: Se ja tentou instalar e ainda nao encontrou, encerra com erro
if "%INSTALL_ATTEMPTED%"=="1" (
    echo [ERRO] Nao foi possivel detectar o Python (3.10 ou superior) mesmo apos a instalacao automatica.
    echo Por favor, reinicie o terminal ou instale manualmente via https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Nao encontrou: executa a instalacao via terminal
echo [AVISO] Nenhuma instalacao compativel do Python (3.10 ou superior) foi encontrada.
echo [INFO] Iniciando instalacao automatica do Python 3.10 pelo terminal...
echo.

set "INSTALL_ATTEMPTED=1"

where winget >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Tentando instalar Python 3.10 via winget...
    winget install --id Python.Python.3.10 --silent --accept-source-agreements --accept-package-agreements
    if not errorlevel 1 (
        echo [INFO] Instalacao via winget concluida.
        goto :pos_instalacao
    )
    echo [AVISO] Instalacao via winget nao completada com sucesso. Tentando download direto...
)

set "PY_INSTALLER=%TEMP%\python-3.10.11-amd64.exe"
echo [INFO] Baixando instalador oficial do Python 3.10.11...
where curl >nul 2>&1
if not errorlevel 1 (
    curl.exe -L -o "%PY_INSTALLER%" "https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe', '%PY_INSTALLER%')"
)

if exist "%PY_INSTALLER%" (
    echo [INFO] Executando instalador silencioso do Python 3.10...
    start /wait "" "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1
    del "%PY_INSTALLER%" 2>nul
) else (
    echo [ERRO] Nao foi possivel baixar o instalador oficial do Python.
    echo Verifique sua conexao com a internet.
    pause
    exit /b 1
)

:pos_instalacao
:: Atualiza o PATH da sessao atual
if exist "%LOCALAPPDATA%\Programs\Python\Python310" (
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python310;%LOCALAPPDATA%\Programs\Python\Python310\Scripts;%PATH%"
)
if exist "%ProgramFiles%\Python310" (
    set "PATH=%ProgramFiles%\Python310;%ProgramFiles%\Python310\Scripts;%PATH%"
)

echo [INFO] Verificando instalacao...
goto :buscar_python

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
exit /b 0

:test_python
set "_cand=%~1"
if not defined _cand exit /b 0
if exist "%_cand%" (
    "%_cand%" -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD="%_cand%""
        exit /b 0
    )
)
%_cand% -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=%_cand%"
    exit /b 0
)
exit /b 0
