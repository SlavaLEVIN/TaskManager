from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "scripts/update_database.py")],
    pathex=[str(root / "src"), str(root / "scripts")],
    binaries=[], datas=[], hiddenimports=["psycopg2._psycopg"],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=["PySide6"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="Обновить базу",
          icon=str(root / "src/task_manager/resources/app.ico"), console=True,
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False)
