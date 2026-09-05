@echo off
title Autorizar Lector de Correo (BAZ Digital)
cd /d "%~dp0"

echo =======================================================
echo   CONFIGURACION DE ACCESO A CORREO PARA EL ASISTENTE
echo =======================================================
echo.
echo Se requiere iniciar sesion en la cuenta de Microsoft
echo para que el sistema pueda leer automaticamente los 
echo gastos desde los correos de notificacion.
echo.

set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] No se encontro el entorno virtual.
    echo Por favor, ejecuta 'iniciar.bat' al menos una vez antes.
    echo.
    pause
    exit /b 1
)

"%PYTHON%" src\email_reader.py --authorize

echo.
pause
