# Masaustune Krpito MTF kisayolu olusturur
# Usage: .\scripts\create_desktop_shortcut.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$launcher = Join-Path $root "launch_krpito.bat"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Krpito MTF.lnk"

if (-not (Test-Path $launcher)) {
    Write-Host "HATA: launch_krpito.bat bulunamadi: $launcher" -ForegroundColor Red
    exit 1
}

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $launcher
$Shortcut.WorkingDirectory = $root
$Shortcut.WindowStyle = 1
$Shortcut.Description = "Krpito MTF - Local motor + Ollama + Flet"
$Shortcut.Save()

Write-Host "Kisayol guncellendi: $shortcutPath" -ForegroundColor Green
Write-Host "Hedef: $launcher" -ForegroundColor Cyan
