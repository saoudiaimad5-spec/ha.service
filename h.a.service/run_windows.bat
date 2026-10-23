@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 (
        echo Python 3 is required. Install Python for Windows first.
        pause
        exit /b 1
    )
    .venv\Scripts\python.exe -m pip install -r requirements-windows.txt
    if errorlevel 1 (
        echo Dependency installation failed.
        pause
        exit /b 1
    )
)
if not exist ".ha_secret" (
    powershell -NoProfile -Command "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')" > ".ha_secret"
)
set /p HA_SECRET_KEY=<.ha_secret
.venv\Scripts\python.exe app.py
pause
