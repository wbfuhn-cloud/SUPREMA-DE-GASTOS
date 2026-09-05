@echo off
title Asistente Financiero
cd /d "%~dp0"

:: Python del entorno virtual
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [ERROR] No se encontro el entorno virtual .venv
    echo.
    echo Solucion: Ejecuta este comando en la terminal:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    echo.
    echo O arrastra la carpeta a: https://ajolonauta.xyz/bat-fixer
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
            echo Ejecuta manualmente: .venv\Scripts\pip install -r requirements.txt
            pause
            exit /b 1
        )
    )
    echo OK > .deps_ok
)
echo [OK] Dependencias listas.
echo.

:: Buscar un puerto libre entre 5050 y 5060
echo [*] Buscando un puerto libre para la aplicacion...
set "APP_PORT=5050"
for /L %%p in (5050,1,5060) do (
    netstat -ano ^| find "LISTENING" ^| find ":%%p" >nul || (
        set "APP_PORT=%%p"
        goto :PortFound
    )
)
echo [!] Advertencia: No se encontraron puertos libres entre 5050 y 5060.
echo [!] Usando el puerto por defecto 5050, podria haber errores.
:PortFound
echo [OK] Usando el puerto: %APP_PORT%
echo.

:: Lanzar la app principal
echo [1/1] Lanzando ASISTENTE FINANCIERO (Todo en uno)...
echo.
echo   NOTA: Se abrira una ventana del navegador con el dashboard.
echo   Si no se abre, visita: http://localhost:%APP_PORT%/dashboard
echo.
"%PYTHON%" "%~dp0src\app.py"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] La aplicacion termino con codigo: %ERRORLEVEL%
    echo.
    echo Posibles causas:
    echo   - Ya hay una instancia ejecutandose (revisa el Administrador de Tareas)
    echo   - Puerto %APP_PORT% ocupado por otro programa
    echo   - Error en src/app.py
    echo.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo El programa finalizo.
pause
