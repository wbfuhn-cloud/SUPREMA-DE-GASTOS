@echo off
title Lanzador Gastos Raccoon
cd /d "%~dp0"

echo ===================================================
echo   INICIANDO ASISTENTE FINANCIERO - GASTOS RACCOON
echo ===================================================
echo.

:: 1. Liberar puertos y cerrar ventanas previas
echo [*] Cerrando ventanas previas y liberando puertos 5050 y 5000...
taskkill /F /FI "WINDOWTITLE eq Asistente Financiero" /IM cmd.exe >nul 2>&1

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5050"') do (
    if not "%%a"=="0" (
        echo [!] Cerrando proceso en puerto 5050 ^(PID: %%a^)...
        taskkill /f /pid %%a >nul 2>&1
    )
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000"') do (
    if not "%%a"=="0" (
        echo [!] Cerrando proceso en puerto 5000 ^(PID: %%a^)...
        taskkill /f /pid %%a >nul 2>&1
    )
)

echo [OK] Puertos liberados correctamente.
echo.

:: 2. Auto-actualizador desde GitHub (v3.3.0)
echo [*] Buscando y aplicando actualizaciones desde GitHub (origin/main)...
if exist ".git" (
    git fetch origin main >nul 2>&1
    git reset --hard origin/main >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [OK] Sistema actualizado y parcheado correctamente desde GitHub.
    ) else (
        git pull origin main
        if %ERRORLEVEL% NEQ 0 (
            echo [!] Advertencia: No se pudo conectar a GitHub. Continuando en modo local...
        ) else (
            echo [OK] Sistema actualizado correctamente.
        )
    )
) else (
    echo [!] No es un repositorio de Git. Saltando actualizacion.
)
echo.

:: 3. Python del entorno virtual
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [!] No se encontro el entorno virtual .venv. Creando uno nuevo...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Fallo la creacion del entorno virtual. Verifica que python este instalado.
        pause
        exit /b 1
    )
    echo [*] Instalando dependencias desde requirements.txt...
    "%~dp0.venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Fallo la instalacion de dependencias.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado exitosamente.
)

echo [OK] Python encontrado: %PYTHON%
echo.

:: 4. Verificar dependencias
echo [0/1] Verificando dependencias...
"%PYTHON%" -c "import flask, bs4, httpx, pandas, msal, sklearn" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] Instalando dependencias faltantes...
    "%PYTHON%" -m pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Fallo la instalacion de dependencias.
        pause
        exit /b 1
    )
)
echo [OK] Dependencias listas.
echo.

:: 5. Lanzar la app principal
echo [1/1] Lanzando ASISTENTE FINANCIERO (Todo en uno)...
echo.
echo   NOTA: Se abrira una ventana del navegador con el dashboard.
echo.
title Asistente Financiero
"%PYTHON%" "%~dp0src\app.py"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] La aplicacion termino con codigo: %ERRORLEVEL%
    echo.
    echo Posibles causas:
    echo   - El entorno virtual (.venv) fue copiado de otra PC y esta roto. (Borralo y re-crealo)
    echo   - Error en src/app.py
    echo.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo El programa finalizo.
pause
