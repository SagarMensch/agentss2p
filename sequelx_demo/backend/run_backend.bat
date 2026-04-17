@echo off
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo Missing virtual environment at venv\Scripts\python.exe
  pause
  exit /b 1
)

echo Restarting SequelX backend on http://127.0.0.1:8000
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart_backend.ps1"

if errorlevel 1 (
  echo.
  echo Backend exited with an error.
  pause
)
