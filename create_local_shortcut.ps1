$WshShell = New-Object -ComObject WScript.Shell
$TargetPath = (Resolve-Path "dist\Guardias\Guardias.exe").Path
$WorkDir = (Resolve-Path "dist\Guardias").Path
$IconPath = (Resolve-Path "app_icon.ico").Path

$Shortcut = $WshShell.CreateShortcut("Sistema de Guardias.lnk")
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = $WorkDir
$Shortcut.IconLocation = $IconPath
$Shortcut.Description = "Sistema de Gestión de Guardias"
$Shortcut.Save()
Write-Host "[+] Acceso directo local creado con éxito." -ForegroundColor Green
