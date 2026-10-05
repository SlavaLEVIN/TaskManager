@echo off
setlocal
cd /d "%~dp0"
if exist "TaskManager.exe" (
  start "" "TaskManager.exe"
  exit /b 0
)
if exist "runtime\pythonw.exe" (
  start "" "runtime\pythonw.exe" "run.py"
  exit /b 0
)
if exist "dist\TaskManager.exe" (
  start "" "dist\TaskManager.exe"
  exit /b 0
)
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "run.py"
  exit /b 0
)
echo Use the Windows portable package or run BUILD_WINDOWS.cmd first.
pause
exit /b 1
