@echo off
title Sistema de Gestion de Guardias
chcp 65001 > nul
cls

if exist "%~dp0dist\Guardias\Guardias.exe" (
    start "" "%~dp0dist\Guardias\Guardias.exe"
    exit /b
)

echo Iniciando aplicacion de escritorio...
python "%~dp0app.py"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Ocurrio un problema al iniciar la aplicacion.
    pause
)
