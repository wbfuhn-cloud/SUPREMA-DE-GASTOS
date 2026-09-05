@echo off
title Bot de Notificaciones Financieras
echo ========================================
echo   BOT NOTIFICADOR DE INVERSIONES
echo ========================================
echo.
echo Comandos disponibles:
echo 1. Ver resumen del Portafolio (--portfolio)
echo 2. Escanear tickers especificos (ej: TSLA,AAPL)
echo 3. Agregar ticker al portafolio
echo.

set /p choice=Selecciona una opcion (1-3): 

if "%choice%"=="1" (
    python notificador_cli.py --portfolio
)
if "%choice%"=="2" (
    set /p tickers=Ingresa los tickers separados por coma: 
    python notificador_cli.py --scan %tickers%
)
if "%choice%"=="3" (
    set /p ticker=Ingresa el ticker a agregar: 
    python notificador_cli.py --add %ticker%
)

echo.
pause
