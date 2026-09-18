@echo off

title Krpito Live Monitor

cd /d "%~dp0"

set KRPITO_REMOTE_ONLY=1

py -3 live_monitor.py 2>nul || python live_monitor.py

if errorlevel 1 (
    echo.
    echo Monitor baslatilamadi. Python ve bagimliliklari kontrol edin.
    pause
)
