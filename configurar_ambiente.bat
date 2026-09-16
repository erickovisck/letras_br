@echo off
title LetrasBR - Configuracao do Ambiente
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================================
echo   LetrasBR - Instalador e Configurador de Ambiente
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

:: Se nenhum Python >= 3.10 for encontrado, avisa e encerra sem criar venv
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
echo O ambiente virtual (.venv) NAO foi criado.
echo.
pause
exit /b 1

:python_ok
echo [1/3] Python compativel detectado:
for /f "delims=" %%v in ('%PYTHON_CMD% -c "import sys; print(f'{sys.version.split()[0]} ({sys.executable})')"') do echo Comando: %PYTHON_CMD% [Versao: %%v]
echo.

:: 2. Cria ou valida ambiente virtual
echo [2/3] Configurando ambiente virtual (.venv)...

if not exist ".venv\Scripts\python.exe" goto :criar_venv

:: Se ja existe, valida versao
.venv\Scripts\python.exe -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    echo Ambiente virtual .venv existente e compativel detectado.
    goto :instalar_deps
)

echo [AVISO] O ambiente virtual existente foi criado com Python inferior a 3.10.
echo Removendo ambiente antigo e recriando com %PYTHON_CMD%...
rmdir /s /q .venv

:criar_venv
echo Criando ambiente virtual em .venv com %PYTHON_CMD%...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 (
    echo [ERRO] Falha ao criar o ambiente virtual .venv.
    pause
    exit /b 1
)
echo Ambiente virtual criado com sucesso!

:instalar_deps
echo.

:: 3. Instala dependencias
echo [3/3] Instalando/atualizando dependencias (FastAPI, Uvicorn, ytmusicapi, etc.)...
.venv\Scripts\pip.exe install -r letrasbr_api\requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias do requirements.txt.
    pause
    exit /b 1
)
echo.

:: 4. Compila o LetrasBR.exe e registra no Menu Iniciar
echo [4/5] Compilando LetrasBR.exe e criando atalho no Menu Iniciar...
call scripts\build_exe.bat < nul > nul 2>&1
call scripts\registrar_menu_iniciar.bat < nul > nul 2>&1
echo.

:: 5. Registra protocolo personalizado no Windows
echo [5/5] Registrando protocolo letrasbr:// no Windows...
.venv\Scripts\python.exe letrasbr_api\protocol.py
echo.

echo ========================================================
echo   [SUCESSO] Configuracao concluida com exito!
echo   Voce pode iniciar pelo executavel 'LetrasBR.exe'
echo   ou pesquisando por 'LetrasBR' no Menu Iniciar!
echo ========================================================
echo.
pause
