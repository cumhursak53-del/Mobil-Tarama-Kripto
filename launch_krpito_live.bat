@echo off

title Krpito Live - Bybit Motor

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_live_stack.ps1"

if errorlevel 1 (

    echo.

    echo Baslatma hatasi. Yukaridaki mesaji okuyun.

    pause

)

