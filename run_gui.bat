@echo off
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app.py"
) else if exist "C:\Program Files\Python312\pythonw.exe" (
    start "" "C:\Program Files\Python312\pythonw.exe" "%~dp0app.py"
) else (
    start "" pythonw.exe "%~dp0app.py"
)
