@echo off
setlocal
echo ===================================================
echo   RESPALDO DE SEGURIDAD - SUPREMA DE GASTOS
echo ===================================================

:: Definir variables
set "BACKUP_DIR=%~dp0backups"
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set "TIMESTAMP=%datetime:~0,4%%datetime:~4,2%%datetime:~6,2%_%datetime:~8,2%%datetime:~10,2%%datetime:~12,2%"
set "TARGET_DIR=%BACKUP_DIR%\backup_%TIMESTAMP%"

:: Crear directorio de respaldo
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
mkdir "%TARGET_DIR%"
mkdir "%TARGET_DIR%\database"

echo [*] Creando respaldo en: %TARGET_DIR%

:: Respaldar configuraciones
echo [*] Copiando archivos de configuracion...
if exist "%~dp0.env" copy /Y "%~dp0.env" "%TARGET_DIR%\" >nul
if exist "%~dp0visor_config.json" copy /Y "%~dp0visor_config.json" "%TARGET_DIR%\" >nul

:: Respaldar bases de datos
echo [*] Copiando bases de datos SQLite...
if exist "%~dp0database\expenses.db" copy /Y "%~dp0database\expenses.db" "%TARGET_DIR%\database\" >nul
if exist "%~dp0database\expenses.db-shm" copy /Y "%~dp0database\expenses.db-shm" "%TARGET_DIR%\database\" >nul
if exist "%~dp0database\expenses.db-wal" copy /Y "%~dp0database\expenses.db-wal" "%TARGET_DIR%\database\" >nul
if exist "%~dp0database\morosos.db" copy /Y "%~dp0database\morosos.db" "%TARGET_DIR%\database\" >nul

echo [OK] Respaldo completado con exito.
pause
