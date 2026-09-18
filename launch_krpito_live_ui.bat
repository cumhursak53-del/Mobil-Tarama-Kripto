@echo off

title Krpito Live - PC Arayuzu

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_live_ui.ps1"

if errorlevel 1 (
    echo.
    echo Baslatma hatasi.
    pause
)
