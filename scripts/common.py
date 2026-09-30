import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from task_manager.config import DatabaseConfig
from task_manager.database import Database


def parser(description):
    result = argparse.ArgumentParser(description=description)
    result.add_argument("--config", type=Path, help="INI с подключением к целевой БД")
    return result


def database(args):
    return Database(DatabaseConfig.load(args.config))
