@echo off
title DareFX Auto-Trading Bot
cd /d C:\DareFX
set PATH=C:\Program Files\Python312;C:\Program Files\Python312\Scripts;%PATH%

:loop
echo [DareFX] Starting DareFX Bot...
python bot.py
echo [DareFX] Process stopped. Restarting in 10 seconds...
timeout /t 10
goto loop
