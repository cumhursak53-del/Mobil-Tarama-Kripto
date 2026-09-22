# Masaustune Krpito Live kisayolu olusturur

# Usage: .\scripts\create_live_desktop_shortcut.ps1



$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

$launcher = Join-Path $root "launch_krpito_live.bat"

$desktop = [Environment]::GetFolderPath("Desktop")

$shortcutPath = Join-Path $desktop "Krpito Live.lnk"



if (-not (Test-Path $launcher)) {

    Write-Host "HATA: launch_krpito_live.bat bulunamadi: $launcher" -ForegroundColor Red

    exit 1

}



$WshShell = New-Object -ComObject WScript.Shell

$Shortcut = $WshShell.CreateShortcut($shortcutPath)

$Shortcut.TargetPath = $launcher

$Shortcut.WorkingDirectory = $root

$Shortcut.WindowStyle = 1

$Shortcut.Description = "Krpito Live - Bybit Hacim + PiyasaEvresi"

$Shortcut.Save()



Write-Host "Kisayol olusturuldu: $shortcutPath" -ForegroundColor Green

Write-Host "Hedef: $launcher" -ForegroundColor Cyan

