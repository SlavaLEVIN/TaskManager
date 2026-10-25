from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "scripts/setup_database.py")],
    pathex=[str(root / "src"), str(root / "scripts")],
    binaries=[],
    datas=[(str(root / "database/create_schema.sql"), "database"),
           (str(root / "database/seed_categories.sql"), "database")],
    hiddenimports=["psycopg2._psycopg", "bcrypt._bcrypt"],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=["PySide6"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="TaskManager-Setup",
          icon=str(root / "src/task_manager/resources/app.ico"), console=True,
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False)
