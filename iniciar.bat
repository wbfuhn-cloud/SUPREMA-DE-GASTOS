@echo off
setlocal EnableExtensions
title Asistente Financiero
cd /d "%~dp0"

echo ===================================================
echo   ASISTENTE FINANCIERO - INICIO RAPIDO
echo ===================================================

set "PYTHON=%~dp0.venv\Scripts\python.exe"
set "FORCE_SETUP=0"
set "DO_UPDATE=0"
if /I "%~1"=="--setup" set "FORCE_SETUP=1"
if /I "%~1"=="--update" set "DO_UPDATE=1"

if "%DO_UPDATE%"=="1" (
    if exist ".git" (
        echo [*] Actualizando desde origin/main...
        git pull --ff-only origin main
        if errorlevel 1 echo [!] No se pudo actualizar. Se usara la copia local.
    ) else (
        echo [!] Esta carpeta no contiene un repositorio Git.
    )
)

echo [*] El actualizador de GitHub comprobara nuevas versiones al abrir la aplicacion.

if not exist "%PYTHON%" (
    echo [*] Creando el entorno virtual...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 goto :venv_error
    set "FORCE_SETUP=1"
)

if "%FORCE_SETUP%"=="1" (
    echo [*] Instalando dependencias. Esto solo se hace en la configuracion...
    "%PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 goto :deps_error
    "%PYTHON%" -c "from pathlib import Path; Path('.deps_ok').touch()"
) else if not exist ".deps_ok" (
    echo [*] Primera configuracion de dependencias...
    "%PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 goto :deps_error
    "%PYTHON%" -c "from pathlib import Path; Path('.deps_ok').touch()"
)

echo [OK] Iniciando aplicacion...
"%PYTHON%" "%~dp0src\app.py"
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" (
    echo.
    echo [ERROR] La aplicacion termino con codigo %APP_EXIT%.
    echo Ejecuta iniciar.bat --setup si cambiaste requirements.txt.
    pause
)
exit /b %APP_EXIT%

:venv_error
echo [ERROR] No se pudo crear .venv. Verifica la instalacion de Python.
pause
exit /b 1

:deps_error
echo [ERROR] No se pudieron instalar las dependencias.
pause
exit /b 1
