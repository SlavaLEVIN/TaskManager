import os
import hashlib
from pathlib import Path
from types import SimpleNamespace

import bcrypt
import pytest

from task_manager.config import DatabaseConfig
from task_manager.database import Database
from task_manager.domain import Session
from task_manager.services import AuthService, ReportService, TaskService, UserService


@pytest.fixture(scope="session")
def postgres():
    path = os.environ.get("TASK_MANAGER_TEST_CONFIG")
    if not path:
        pytest.skip("TASK_MANAGER_TEST_CONFIG не задан: требуется отдельная PostgreSQL БД с именем *_test")
    config = DatabaseConfig.load(Path(path))
    if not config.dbname.endswith("_test"):
        pytest.fail("Защита данных: имя интеграционной БД должно оканчиваться на _test")
    db = Database(config)
    with db.transaction() as cursor:
        cursor.execute("SELECT to_regclass('public.users') AS name")
        exists = cursor.fetchone()["name"] is not None
    if not exists:
        with db.transaction() as cursor:
            cursor.execute((Path(__file__).parents[1] / "database/create_schema.sql").read_text(encoding="utf-8"))
    return db


@pytest.fixture(scope="session")
def fixture_hash():
    # Быстрый хеш только для повторно создаваемых тестовых фикстур.
    return bcrypt.hashpw(b"Test-Password!", bcrypt.gensalt(rounds=4)).decode("ascii")


@pytest.fixture
def env(postgres, fixture_hash):
    with postgres.transaction() as cursor:
        cursor.execute("TRUNCATE tasks,users,categories RESTART IDENTITY CASCADE")
        for login, role in (("admin", "ADMIN"), ("ivan", "USER"), ("anna", "USER"), ("empty", "USER")):
            cursor.execute("INSERT INTO users(login,password_hash,role) VALUES(%s,%s,%s)", (login, fixture_hash, role))
        cursor.execute("INSERT INTO categories(name) VALUES ('Документы'),('Прочее')")
        cursor.execute("SELECT CURRENT_DATE AS today")
        today = cursor.fetchone()["today"]
    users = UserService(postgres)
    tasks = TaskService(postgres)
    return SimpleNamespace(db=postgres, users=users, tasks=tasks, auth=AuthService(users), reports=ReportService(tasks, users),
                           admin=Session(1, hashlib.sha256(fixture_hash.encode("ascii")).digest()),
                           ivan=Session(2, hashlib.sha256(fixture_hash.encode("ascii")).digest()),
                           anna=Session(3, hashlib.sha256(fixture_hash.encode("ascii")).digest()),
                           empty=Session(4, hashlib.sha256(fixture_hash.encode("ascii")).digest()), today=today)
