import argparse
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def pause_if_frozen():
    if getattr(sys, "frozen", False):
        try:
            input("Нажмите Enter, чтобы закрыть окно...")
        except (EOFError, KeyboardInterrupt):
            pass


if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(ROOT / "src"))

from task_manager.config import DatabaseConfig
from task_manager.database import Database


def ask(label, default):
    return input(f"{label} [{default}]: ").strip() or default


def parser(description):
    result = argparse.ArgumentParser(description=description)
    result.add_argument("--config", type=Path, help="INI с подключением к целевой БД")
    return result


def database(args):
    return Database(DatabaseConfig.load(args.config))
