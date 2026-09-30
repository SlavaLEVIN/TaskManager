"""Внешняя конфигурация подключения; секреты не попадают в журнал."""

import configparser
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .domain import AppError


def data_directory() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share")))
    return root / "TaskManager"


def config_path() -> Path:
    if os.environ.get("TASK_MANAGER_CONFIG"):
        return Path(os.environ["TASK_MANAGER_CONFIG"])
    if getattr(sys, "frozen", False):
        adjacent = Path(sys.executable).parent / "database.ini"
        if adjacent.is_file():
            return adjacent
    return data_directory() / "database.ini"


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = "127.0.0.1"
    port: int = 5432
    dbname: str = "task_manager"
    user: str = "task_client"
    password: str = field(default="", repr=False)
    connect_timeout: int = 5
    statement_timeout: int = 10000
    sslmode: str = "prefer"

    def validate(self) -> None:
        if not all((self.host.strip(), self.dbname.strip(), self.user.strip())):
            raise AppError("Заполните адрес сервера, имя БД и технического пользователя.")
        if not 1 <= self.port <= 65535 or not 2 <= self.connect_timeout <= 15:
            raise AppError("Порт: 1–65535; тайм-аут подключения: 2–15 секунд.")
        if not 1000 <= self.statement_timeout <= 30000:
            raise AppError("Тайм-аут запроса: 1000–30000 миллисекунд.")
        if self.sslmode not in {"disable", "prefer", "require", "verify-ca", "verify-full"}:
            raise AppError("Неверный режим SSL.")

    @classmethod
    def load(cls, path: Path | None = None) -> "DatabaseConfig":
        path = path or config_path()
        parser = configparser.ConfigParser(interpolation=None)
        try:
            with path.open(encoding="utf-8-sig") as stream:
                parser.read_file(stream)
            values = dict(parser["postgresql"])
            for key in ("port", "connect_timeout", "statement_timeout"):
                if key in values:
                    values[key] = int(values[key])
            result = cls(**values)
            result.validate()
            return result
        except (OSError, ValueError, TypeError, KeyError, configparser.Error) as exc:
            raise AppError("Не удалось прочитать настройки БД. Откройте «Настройки подключения».") from exc

    def save(self, path: Path | None = None) -> None:
        self.validate()
        path = path or config_path()
        parser = configparser.ConfigParser(interpolation=None)
        parser["postgresql"] = {key: str(value) for key, value in vars(self).items()}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as stream:
                parser.write(stream)
            if os.name != "nt":
                path.chmod(0o600)
        except OSError as exc:
            raise AppError("Не удалось сохранить настройки подключения в выбранную папку.") from exc
