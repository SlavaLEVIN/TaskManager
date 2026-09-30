$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($env:OS -ne 'Windows_NT') { throw 'Run this script on Windows 10/11 x64.' }
& py -3.13 -c "import struct; assert struct.calcsize('P') == 8, '64-bit Python required'"
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.13 x64 from python.org, including the py launcher.' }
& py -3.13 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Failed to create the build environment.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
$env:QT_QPA_PLATFORM = 'offscreen'
& .\.venv\Scripts\python.exe -m pytest tests/unit -q
if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed.' }
Remove-Item Env:QT_QPA_PLATFORM
& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging/task_manager.spec
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
Copy-Item config\database.example.ini dist\database.example.ini -Force
Copy-Item START_HERE_WINDOWS.md dist\START_HERE_WINDOWS.md -Force
Write-Host 'Built: dist\TaskManager.exe. Test it on a Windows PC without Python.'
