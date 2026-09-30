# Сборка выполняется из корня проекта на Windows.
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / 'run.py')],
    pathex=[str(root / 'src')],
    binaries=[],
    datas=[(str(root / 'src/task_manager/resources'), 'task_manager/resources')],
    hiddenimports=['psycopg2._psycopg', 'bcrypt._bcrypt'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml', 'PySide6.QtQuick'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='TaskManager', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=False)
