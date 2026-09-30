@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
"runtime\python.exe" -X utf8 "scripts\check_installation.py"
pause
