@echo off
title Krpito MTF
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_local_stack.ps1"
if errorlevel 1 (
    echo.
    echo Baslatma hatasi. Yukaridaki mesaji okuyun.
    pause
)
