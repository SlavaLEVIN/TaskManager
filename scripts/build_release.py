"""Собирает пользовательский архив из готовых Windows EXE."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "TaskManager.exe",
    "TaskManager-Setup.exe",
    "TaskManager-Update.exe",
    "START_HERE_WINDOWS.md",
    "THIRD_PARTY_NOTICES.md",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--output", type=Path, default=ROOT / "release")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    archive_path = args.output / "TaskManager-Windows-Portable.zip"
    with ZipFile(archive_path, "w", ZIP_DEFLATED, compresslevel=6) as archive:
        for name in FILES:
            source = (args.dist if name.endswith(".exe") else ROOT) / name
            if not source.is_file():
                parser.error(f"Не найден файл: {source}")
            if name.endswith(".exe") and source.read_bytes()[:2] != b"MZ":
                parser.error(f"Файл не является Windows EXE: {source}")
            archive.write(source, f"TaskManager/{name}")
    with ZipFile(archive_path) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(FILES):
            raise SystemExit("Проверка архива не пройдена.")
    print(f"Готово: {archive_path} ({archive_path.stat().st_size} байт, {len(FILES)} файлов)")


if __name__ == "__main__":
    main()
