@echo off
chcp 65001 > nul
powershell -ExecutionPolicy Bypass -File "%~dp0Crear_Acceso_Directo_Escritorio.ps1"
pause
