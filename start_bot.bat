@echo off
title DareFX Auto-Trading Bot
cd /d C:\DareFX
set PATH=C:\Program Files\Python312;C:\Program Files\Python312\Scripts;%PATH%

:loop
tasklist /fi "imagename eq terminal64.exe" | findstr /i "terminal64.exe" >nul
if errorlevel 1 (
    echo [DareFX] Starting MetaTrader 5 with Valetax configuration...
    start "" "C:\Program Files\MetaTrader 5\terminal64.exe" /config:"C:\DareFX\mt5_config.ini"
    timeout /t 10 /nobreak >nul
)

echo [DareFX] Starting DareFX Bot...
python bot.py
echo [DareFX] Process stopped. Restarting in 10 seconds...
timeout /t 10
goto loop
