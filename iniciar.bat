@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Asistente Financiero
cd /d "%~dp0"
if errorlevel 1 exit /b 1

if /I "%~1"=="--diagnose" goto :launch_options
echo ===================================================
echo   ASISTENTE FINANCIERO
echo ===================================================

:launch_options
set "APP_PYTHON=%~dp0.venv\Scripts\python.exe"
set "APP_CHECK_ONLY=0"
if /I "%~1"=="--check" set "APP_CHECK_ONLY=1"
if /I "%~1"=="--update" call :update_source

if exist "%APP_PYTHON%" goto :check_dependencies
if "%APP_CHECK_ONLY%"=="1" goto :missing_python
echo [*] Creando entorno virtual...
py -3 -m venv "%~dp0.venv" 2>nul
if exist "%APP_PYTHON%" goto :check_dependencies
python -m venv "%~dp0.venv"
if not exist "%APP_PYTHON%" goto :missing_python

:check_dependencies
if /I "%~1"=="--setup" goto :install_dependencies
"%APP_PYTHON%" -c "import importlib.util; names=['customtkinter','dotenv','flask','flask_cors','apscheduler','msal','httpx','socksio','telegram','pandas','sklearn','joblib','openpyxl','bs4','google.genai']; raise SystemExit(0 if all(importlib.util.find_spec(n) for n in names) else 1)" >nul 2>&1
if not errorlevel 1 goto :ready
if "%APP_CHECK_ONLY%"=="1" goto :missing_dependencies

:install_dependencies
echo [*] Instalando dependencias necesarias...
"%APP_PYTHON%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto :missing_dependencies
goto :ready

:ready
if /I "%~1"=="--diagnose" (
    "%APP_PYTHON%" "%~dp0diagnostico.py" todo --json
    exit /b
)
if "%APP_CHECK_ONLY%"=="1" (
    echo [OK] Python y dependencias disponibles. Arranque local listo.
    exit /b 0
)
if not exist ".env" echo [AVISO] Falta .env. Copia la configuracion de tu instalacion anterior para conectar tus servicios.
echo [*] Abriendo el programa local...
echo [*] Para actualizar GitHub usa: iniciar.bat --update
"%APP_PYTHON%" -u "%~dp0src\app.py"
set "APP_EXIT_CODE=%ERRORLEVEL%"
if "%APP_EXIT_CODE%"=="0" exit /b 0
echo.
echo [ERROR] El programa termino con codigo %APP_EXIT_CODE%.
echo Copia las ultimas lineas del error para identificar el problema.
pause
exit /b %APP_EXIT_CODE%

:missing_python
echo [ERROR] No se pudo encontrar o crear Python en .venv.
echo Instala Python y vuelve a abrir iniciar.bat.
if "%APP_CHECK_ONLY%"=="0" pause
exit /b 1

:missing_dependencies
echo [ERROR] Faltan dependencias o fallo su instalacion.
echo Ejecuta iniciar.bat --setup con conexion a Internet.
if "%APP_CHECK_ONLY%"=="0" pause
exit /b 1

:update_source
if not exist ".git" (
    echo [AVISO] Copia descargada sin Git. Se abrira la version local.
    exit /b 0
)
where git >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Git no esta instalado. Se abrira la version local.
    exit /b 0
)
if exist ".env" (
    if not exist "backups" mkdir "backups"
    copy /y ".env" "backups\.env.before-update" >nul
    if errorlevel 1 (
        echo [AVISO] No se pudo respaldar .env. No se actualizara el codigo.
        exit /b 0
    )
)
set "GIT_TERMINAL_PROMPT=0"
git pull --ff-only origin main
if errorlevel 1 echo [AVISO] No se pudo actualizar. Se abrira la version local.
if not exist ".env" if exist "backups\.env.before-update" copy /y "backups\.env.before-update" ".env" >nul
exit /b 0
