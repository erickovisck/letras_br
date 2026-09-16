@echo off
title LetrasBR - Registrar no Menu Iniciar
chcp 65001 > nul
cd /d "%~dp0\.."

echo Registrando LetrasBR.exe no Menu Iniciar do Windows...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$wshell = New-Object -ComObject WScript.Shell; $programs = [Environment]::GetFolderPath('Programs'); $shortcut = $wshell.CreateShortcut((Join-Path $programs 'LetrasBR.lnk')); $shortcut.TargetPath = (Resolve-Path '.\LetrasBR.exe').Path; $shortcut.WorkingDirectory = (Resolve-Path '.').Path; $shortcut.IconLocation = (Resolve-Path '.\assets\app_icon.ico').Path + ',0'; $shortcut.Description = 'LetrasBR - Tradutor e Overlay de Letras'; $shortcut.Save();"

if %errorlevel% equ 0 (
    echo [SUCESSO] LetrasBR registrado no Menu Iniciar!
    echo Agora voce pode pesquisar por 'LetrasBR' no Windows.
) else (
    echo [ERRO] Falha ao registrar atalho no Menu Iniciar.
)
echo.
pause
