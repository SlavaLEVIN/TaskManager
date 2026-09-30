@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist "runtime\python.exe" (
  "runtime\python.exe" -X utf8 "scripts\update_database.py"
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -X utf8 "scripts\update_database.py"
) else (
  py -3.13 -X utf8 "scripts\update_database.py"
)
pause
