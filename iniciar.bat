@echo off
title Asistente Financiero
cd /d "%~dp0"

:: Auto-actualizador desde GitHub
echo [*] Buscando actualizaciones en GitHub...
if exist ".git" (
    git pull origin main
    if %ERRORLEVEL% NEQ 0 (
        echo [!] Advertencia: No se pudo actualizar desde GitHub. Continuando con la version local...
    ) else (
        echo [OK] Sistema actualizado.
    )
) else (
    echo [!] No es un repositorio de Git. Saltando actualizacion.
)
echo.

:: Python del entorno virtual
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [ERROR] No se encontro el entorno virtual .venv
    echo.
    echo Solucion: Ejecuta este comando en la terminal:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado: %PYTHON%
echo.

:: Verificar dependencias
echo [0/1] Verificando dependencias...
if not exist ".deps_ok" (
    "%PYTHON%" -c "import flask, bs4, httpx" 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [!] Instalando dependencias faltantes...
        "%PYTHON%" -m pip install -r requirements.txt
        if %ERRORLEVEL% NEQ 0 (
            echo [ERROR] Fallo la instalacion de dependencias.
            pause
            exit /b 1
        )
    )
    echo OK > .deps_ok
)
echo [OK] Dependencias listas.
echo.

:: Lanzar la app principal
echo [1/1] Lanzando ASISTENTE FINANCIERO (Todo en uno)...
echo.
echo   NOTA: Se abrira una ventana del navegador con el dashboard.
echo   El puerto se asignara automaticamente para evitar conflictos.
echo.
"%PYTHON%" "%~dp0src\app.py"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] La aplicacion termino con codigo: %ERRORLEVEL%
    echo.
    echo Posibles causas:
    echo   - El entorno virtual (.venv) fue copiado de otra PC y esta roto. (Bórralo y re-créalo)
    echo   - Error en src/app.py
    echo.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo El programa finalizo.
pause
