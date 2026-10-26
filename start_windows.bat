@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please follow docs/windows-setup.md first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\start_server.py
pause
