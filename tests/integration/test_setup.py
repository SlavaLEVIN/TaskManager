import builtins
import uuid
from pathlib import Path
from datetime import date, timedelta

import psycopg2
import pytest
from psycopg2 import sql

from task_manager.config import DatabaseConfig
from task_manager.database import Database
from task_manager.domain import AppError, Priority, TaskInput, TaskStatus
from task_manager.services import AuthService, TaskService, UserService

pytestmark = pytest.mark.integration


def test_setup_and_non_superuser_client(postgres, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "scripts"))
    import setup_database
    config_path = tmp_path / "client.ini"
    monkeypatch.setenv("TASK_MANAGER_CONFIG", str(config_path))
    suffix = uuid.uuid4().hex[:8]
    dbname, role = f"task_setup_{suffix}_test", f"task_client_{suffix}"
    cfg = postgres.config
    answers = iter([cfg.host, str(cfg.port), cfg.user, dbname, role, "firstadmin", "CREATE"])
    passwords = iter([cfg.password, "Client-Test!", "Client-Test!", "Admin-Test!", "Admin-Test!"])
    monkeypatch.setattr(builtins, "input", lambda _: next(answers))
    monkeypatch.setattr(setup_database, "getpass", lambda _: next(passwords))
    try:
        setup_database.main()
        client = Database(DatabaseConfig.load(config_path))
        client.ping()
        session, user = AuthService(UserService(client)).authenticate("firstadmin", "Admin-Test!")
        assert user.is_admin()
        with client.transaction() as cursor:
            cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")
            assert not cursor.fetchone()["rolsuper"]
        with pytest.raises(AppError, match="не хватает прав"):
            with client.transaction() as cursor:
                cursor.execute("CREATE TABLE forbidden(id integer)")
        assert len(UserService(client).get_users(session)) == 1
        with client.transaction() as cursor:
            cursor.execute("SELECT id FROM categories WHERE name='Разработка'")
            category_id = cursor.fetchone()["id"]
        tasks = TaskService(client)
        task_id = tasks.create_task(
            session,
            TaskInput("Проверка установки", "", user.id, category_id,
                      date.today() + timedelta(days=1), Priority.MEDIUM),
        )
        tasks.update_task(session, task_id, TaskInput("Изменена", "", user.id, category_id, date.today(), Priority.HIGH))
        tasks.change_status(session, task_id, TaskStatus.IN_PROGRESS)
        tasks.change_status(session, task_id, TaskStatus.COMPLETED)
        assert tasks.get_selected(session, [task_id]).tasks[0].status == TaskStatus.COMPLETED
        # Simulate a 1.1 database and upgrade it twice without losing records.
        import update_database
        owner = psycopg2.connect(host=cfg.host, port=cfg.port, user=cfg.user, password=cfg.password, dbname=dbname)
        try:
            with owner:
                with owner.cursor() as cursor:
                    cursor.execute(sql.SQL("REVOKE INSERT,UPDATE ON categories FROM {}").format(sql.Identifier(role)))
                    cursor.execute("UPDATE categories SET name='Обслуживание' WHERE id=%s", (category_id,))
            with pytest.raises(AppError, match="UPDATE_DATABASE"):
                tasks.save_category(session, "Новая категория")
            update_database.upgrade(owner, role)
            update_database.upgrade(owner, role)
        finally:
            owner.close()
        assert tasks.get_selected(session, [task_id]).tasks[0].category == "Разработка"
        new_category = tasks.save_category(session, "Проверка категорий")
        tasks.save_category(session, "Проверка переименования", new_category)
        assert AuthService(UserService(client)).authenticate("firstadmin", "Admin-Test!")[0] == session

        with client.transaction() as cursor:
            cursor.execute("SELECT has_table_privilege(current_user, 'categories', 'UPDATE') AS allowed")
            assert cursor.fetchone()["allowed"]
    finally:
        connection = psycopg2.connect(host=cfg.host, port=cfg.port, user=cfg.user, password=cfg.password, dbname="postgres")
        try:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname)))
                cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        finally:
            connection.close()
