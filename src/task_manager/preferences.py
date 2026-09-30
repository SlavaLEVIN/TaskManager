"""Настройки интерфейса текущего Windows-пользователя."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import data_directory
from .domain import AppError


@dataclass(frozen=True)
class Preferences:
    theme: str = "light"
    font_size: int = 13
    start_page: str = "tasks"
    confirm_exit: bool = True

    def validate(self):
        if self.theme not in {"light", "dark"} or self.start_page not in {"home", "tasks"}:
            raise AppError("Недопустимые настройки интерфейса.")
        if type(self.font_size) is not int or not 12 <= self.font_size <= 16:
            raise AppError("Размер текста должен быть от 12 до 16.")
        if type(self.confirm_exit) is not bool:
            raise AppError("Неверная настройка подтверждения выхода.")

    @classmethod
    def load(cls, path: Path | None = None):
        try:
            result = cls(**json.loads((path or data_directory() / "preferences.json").read_text(encoding="utf-8")))
            result.validate()
            return result
        except (OSError, ValueError, TypeError, AppError):
            return cls()

    def save(self, path: Path | None = None):
        self.validate()
        path = path or data_directory() / "preferences.json"
        temporary = path.with_suffix(".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, path)
        except OSError as exc:
            raise AppError("Не удалось сохранить настройки программы.") from exc
