$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($env:OS -ne 'Windows_NT') { throw 'Run this script on Windows 10/11 x64.' }
& py -3.13 -c "import struct; assert struct.calcsize('P') == 8, '64-bit Python required'"
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.13 x64 from python.org, including the py launcher.' }
& py -3.13 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Failed to create the build environment.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
foreach ($spec in @('task_manager', 'setup_database', 'update_database')) {
    & .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm "packaging\$spec.spec"
    if ($LASTEXITCODE -ne 0) { throw "EXE build failed: $spec" }
}
Write-Host 'Built: dist\TaskManager.exe, TaskManager-Setup.exe, TaskManager-Update.exe.'
