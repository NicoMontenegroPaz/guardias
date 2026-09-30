# Script portable: usa la ruta del directorio donde se encuentra este archivo
$BaseDir = $PSScriptRoot
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\Sistema de Guardias.lnk")
$Shortcut.TargetPath = "$BaseDir\dist\Guardias\Guardias.exe"
$Shortcut.WorkingDirectory = "$BaseDir\dist\Guardias"
$Shortcut.IconLocation = "$BaseDir\app_icon.ico"
$Shortcut.Description = "Sistema de Gestion y Generacion Equitativa de Guardias"
$Shortcut.Save()
Write-Host "[+] Acceso directo creado en tu Escritorio." -ForegroundColor Green
