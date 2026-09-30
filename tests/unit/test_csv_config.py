import csv

import pytest

from task_manager.config import DatabaseConfig
from task_manager.domain import AppError
from task_manager.services import write_csv


def test_csv_round_trip_and_no_partial_replacement(tmp_path):
    path = tmp_path / "tasks.csv"
    value = 'Кириллица; "кавычки"\nНовая строка'
    write_csv(path, ["Текст", "Пустое"], [[value, ""], ["=SUM(1;2)", "1"]])
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream, delimiter=";"))
    assert rows == [["Текст", "Пустое"], [value, ""], ["=SUM(1;2)", "1"]]
    with pytest.raises(AppError):
        write_csv(tmp_path / "missing" / "out.csv", ["a"], [["b"]])
    assert not list(tmp_path.glob(".taskmanager-*"))


def test_config_round_trip_with_percent_in_password(tmp_path):
    config = DatabaseConfig(password="a%_x#пароль")
    path = tmp_path / "database.ini"
    config.save(path)
    assert DatabaseConfig.load(path) == config
    assert config.password not in repr(config)
    with pytest.raises(AppError):
        DatabaseConfig(connect_timeout=61).validate()
