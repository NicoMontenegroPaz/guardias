"""
Script de compilacion y empaquetado para generar el ejecutable nativo de Windows (Guardias.exe).
NOTA: Este script no genera rutas hardcodeadas. Todos los scripts de instalacion
son portables y funcionan en cualquier PC independientemente de donde este instalado el proyecto.
"""

import os
import sys
import subprocess

def build():
    print("=========================================================")
    print("   COMPILANDO APLICACION NATIVA DE WINDOWS (GUARDIAS.EXE)")
    print("=========================================================")

    # Asegurar que el icono exista
    if not os.path.exists("app_icon.ico"):
        import create_icon
        create_icon.create_shield_icon()

    # Comando de PyInstaller con todas las dependencias y datos estaticos
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconsole",
        "--name=Guardias",
        "--icon=app_icon.ico",
        "--add-data=ui;ui",
        "--collect-all=holidays",
        "--collect-all=webview",
        "--onedir",
        "--noconfirm",
        "--clean",
        "app.py"
    ]

    print(f"[*] Ejecutando PyInstaller...")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n[+] Compilacion completada con exito.")
        dist_exe = os.path.join("dist", "Guardias", "Guardias.exe")
        print(f"[+] Ejecutable generado en: {os.path.abspath(dist_exe)}")

        # Crear scripts portables de acceso directo
        create_installer_shortcut()
    else:
        print(f"\n[!] Error en la compilacion. Codigo de retorno: {result.returncode}")

def create_installer_shortcut():
    """Crea scripts portables para crear el acceso directo en el Escritorio.
    Todos los scripts usan rutas relativas a su propia ubicacion (sin rutas
    hardcodeadas del sistema del desarrollador). Funcionan en cualquier PC.
    """
    # PowerShell portable: usa $PSScriptRoot (la carpeta donde esta el .ps1)
    ps_content = (
        "# Script portable: usa la ruta del directorio donde se encuentra este archivo\n"
        "$BaseDir = $PSScriptRoot\n"
        "$WshShell = New-Object -ComObject WScript.Shell\n"
        "$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)\n"
        "$Shortcut = $WshShell.CreateShortcut(\"$DesktopPath\\Sistema de Guardias.lnk\")\n"
        "$Shortcut.TargetPath = \"$BaseDir\\dist\\Guardias\\Guardias.exe\"\n"
        "$Shortcut.WorkingDirectory = \"$BaseDir\\dist\\Guardias\"\n"
        "$Shortcut.IconLocation = \"$BaseDir\\app_icon.ico\"\n"
        "$Shortcut.Description = \"Sistema de Gestion y Generacion Equitativa de Guardias\"\n"
        "$Shortcut.Save()\n"
        "Write-Host \"[+] Acceso directo creado en tu Escritorio.\" -ForegroundColor Green\n"
    )
    with open("Crear_Acceso_Directo_Escritorio.ps1", "w", encoding="utf-8") as f:
        f.write(ps_content)
    print("[+] Script Crear_Acceso_Directo_Escritorio.ps1 generado (portable).")

    # BAT portable: usa %~dp0 (ruta del .bat en ejecucion)
    bat_content = (
        "@echo off\n"
        "chcp 65001 > nul\n"
        "powershell -ExecutionPolicy Bypass -File \"%~dp0Crear_Acceso_Directo_Escritorio.ps1\"\n"
        "pause\n"
    )
    with open("Instalar_Acceso_Directo_Escritorio.bat", "w", encoding="utf-8") as f:
        f.write(bat_content)

    # VBS portable: calcula su propia ubicacion en tiempo de ejecucion
    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        'Dim ScriptDir\n'
        'ScriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\\"))\n'
        'WshShell.Run """" & ScriptDir & "dist\\Guardias\\Guardias.exe""", 0, False\n'
    )
    with open("Iniciar_Guardias.vbs", "w", encoding="utf-8") as f:
        f.write(vbs_content)

    print("[+] Scripts de instalacion creados (portables, sin rutas hardcodeadas).")

if __name__ == "__main__":
    build()
