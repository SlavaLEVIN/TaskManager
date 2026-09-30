import csv
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier

import pytest

from task_manager.domain import AccessError, AppError, Priority, Role, Session, SessionExpired, TaskInput, TaskQuery, TaskStatus

pytestmark = pytest.mark.integration


def data(env, **kwargs):
    return replace(TaskInput("Проверить документ", "Описание", 2, 1, env.today, Priority.MEDIUM), **kwargs)


def test_authentication_and_safe_user(env):
    session, user = env.auth.authenticate(" ADMIN ", "Test-Password!")
    assert session == env.admin and user.is_admin() and user.password_hash == ""
    assert env.auth.authenticate("ivan", "Test-Password!")[1].role == Role.USER
    for login, password in (("admin", "wrong"), ("missing", "x"), ("", "x"), ("admin", "")):
        with pytest.raises(AppError):
            env.auth.authenticate(login, password)


def test_access_and_scope_survive_query_reset(env, tmp_path):
    own = env.tasks.create_task(env.admin, data(env))
    other = env.tasks.create_task(env.admin, data(env, assignee_id=3))
    assert [t.id for t in env.tasks.get_tasks(env.ivan).tasks] == [own]
    assert not env.tasks.get_tasks(env.empty).tasks
    for operation in (
        lambda: env.tasks.get_selected(env.ivan, [other]),
        lambda: env.tasks.change_status(env.ivan, other, TaskStatus.IN_PROGRESS),
        lambda: env.tasks.update_task(env.ivan, own, data(env)),
        lambda: env.tasks.create_task(env.ivan, data(env)),
        lambda: env.tasks.delete_task(env.ivan, own),
        lambda: env.users.get_users(env.ivan),
        lambda: env.users.update_user(env.ivan, 3, "changed", Role.ADMIN),
        lambda: env.users.delete_user(env.ivan, 4),
        lambda: env.users.reset_password(env.ivan, 3, "x"),
        lambda: env.users.create_user(env.ivan, "new", "pw", Role.ADMIN),
        lambda: env.reports.create_summary(env.ivan, [own, other]),
        lambda: env.reports.export_tasks(env.ivan, TaskQuery(), tmp_path / "tasks.csv"),
        lambda: env.reports.export_users(env.ivan, tmp_path / "users.csv"),
    ):
        with pytest.raises(AccessError):
            operation()
    assert len(env.tasks.get_tasks(env.ivan, TaskQuery()).tasks) == 1
    assert not list(tmp_path.iterdir())


def test_search_cyrillic_and_literal_special_characters(env):
    one = env.tasks.create_task(env.admin, data(env, title='Отчёт 100%_готов; "А"', description="Совещание"))
    env.tasks.create_task(env.admin, data(env, title="Другой отчёт", description="Пусто"))
    for query in ("ОТЧЁТ 100", "%_", '"А"', "СОВЕЩАНИЕ"):
        assert [t.id for t in env.tasks.get_tasks(env.ivan, TaskQuery(text=query)).tasks] == [one]
    assert not env.tasks.get_tasks(env.ivan, TaskQuery(text="' OR 1=1 --")).tasks
    assert len(env.tasks.get_tasks(env.ivan).tasks) == 2


def test_filters_are_combined_and_inclusive(env):
    first = env.tasks.create_task(env.admin, data(env, priority=Priority.HIGH))
    env.tasks.create_task(env.admin, data(env, priority=Priority.LOW, category_id=2))
    env.tasks.create_task(env.admin, data(env, priority=Priority.HIGH, assignee_id=3))
    query = TaskQuery(text="документ", status=TaskStatus.NEW, priority=Priority.HIGH, category_id=1,
                      assignee_id=2, date_from=env.today, date_to=env.today)
    assert [t.id for t in env.tasks.get_tasks(env.admin, query).tasks] == [first]
    with pytest.raises(AppError):
        env.tasks.get_tasks(env.admin, replace(query, date_to=env.today - timedelta(days=1)))


@pytest.mark.parametrize("sort", ["title", "due_date", "priority", "status", "category"])
def test_sort_both_directions_and_ties(env, sort):
    for index, priority in enumerate((Priority.HIGH, Priority.LOW, Priority.MEDIUM, Priority.MEDIUM)):
        task_id = env.tasks.create_task(env.admin, data(env, title=f"Имя {3-index}", priority=priority, category_id=index % 2 + 1,
                                                       due_date=env.today + timedelta(days=index % 2)))
        if index in (1, 2):
            env.tasks.change_status(env.admin, task_id, TaskStatus.IN_PROGRESS)
        if index == 2:
            env.tasks.change_status(env.admin, task_id, TaskStatus.COMPLETED)
    asc = env.tasks.get_tasks(env.admin, TaskQuery(sort=sort)).tasks
    desc = env.tasks.get_tasks(env.admin, TaskQuery(sort=sort, descending=True)).tasks
    assert [t.id for t in asc] == list(reversed([t.id for t in desc]))
    if sort == "priority":
        assert [t.priority for t in asc] == [Priority.LOW, Priority.MEDIUM, Priority.MEDIUM, Priority.HIGH]
    if sort == "status":
        assert [t.status for t in asc] == [TaskStatus.NEW, TaskStatus.NEW, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED]
    with pytest.raises(AppError):
        env.tasks.get_tasks(env.admin, TaskQuery(sort="title; DROP TABLE users"))


def test_create_update_assign_and_current_status(env):
    task_id = env.tasks.create_task(env.admin, data(env, due_date=env.today - timedelta(days=2), description=""))
    assert env.tasks.get_selected(env.ivan, [task_id]).tasks[0].status == TaskStatus.NEW
    with pytest.raises(AppError):
        env.tasks.update_task(env.admin, task_id, data(env), TaskStatus.COMPLETED)
    assert env.tasks.get_selected(env.ivan, [task_id]).tasks[0].due_date < env.today
    env.tasks.change_status(env.ivan, task_id, TaskStatus.IN_PROGRESS)
    env.tasks.update_task(env.admin, task_id, data(env, assignee_id=3), TaskStatus.COMPLETED)
    assert not env.tasks.get_tasks(env.ivan).tasks
    task = env.tasks.get_selected(env.anna, [task_id]).tasks[0]
    assert not task.is_overdue(env.today)
    for invalid in (data(env, title=" "), data(env, assignee_id=99999), data(env, category_id=99999), data(env, priority="urgent")):
        with pytest.raises(AppError):
            env.tasks.create_task(env.admin, invalid)
    assert len(env.tasks.get_tasks(env.admin).tasks) == 1


def test_rename_role_active_session_password_and_assignments(env):
    task_id = env.tasks.create_task(env.admin, data(env))
    env.users.update_user(env.admin, 2, "  ИВАН  ", Role.ADMIN)
    assert env.users.get_current(env.ivan).is_admin()
    assert len(env.users.get_users(env.ivan)) == 4
    assert env.auth.authenticate("иван", "Test-Password!")[0] == env.ivan
    with pytest.raises(AppError):
        env.auth.authenticate("ivan", "Test-Password!")
    assert env.tasks.get_selected(env.ivan, [task_id]).tasks[0].assignee == "ИВАН"
    env.users.update_user(env.admin, 2, "ИВАН", Role.USER)
    with pytest.raises(AccessError):
        env.users.get_users(env.ivan)
    with pytest.raises(AppError):
        env.users.create_user(env.admin, "иван", "secret", Role.USER)
    env.users.reset_password(env.admin, 2, " New-password! ")
    with pytest.raises(AppError):
        env.auth.authenticate("иван", "Test-Password!")
    assert env.auth.authenticate("ИВАН", " New-password! ")[0] == env.ivan
    with env.db.transaction() as cursor:
        cursor.execute("SELECT password_hash FROM users WHERE id=2")
        assert cursor.fetchone()["password_hash"].startswith("$2b$")


def test_user_delete_requires_reassignment_and_revokes_session(env):
    task_id = env.tasks.create_task(env.admin, data(env))
    with pytest.raises(AppError, match="переназначьте"):
        env.users.delete_user(env.admin, 2)
    env.tasks.update_task(env.admin, task_id, data(env, assignee_id=3))
    env.users.delete_user(env.admin, 2)
    with pytest.raises(SessionExpired):
        env.tasks.get_tasks(env.ivan)
    assert env.tasks.get_selected(env.anna, [task_id]).tasks


def test_reports_requery_no_table_and_filtered_csv(env, tmp_path):
    title, description = 'Сводка; "Отдел"', 'Строка 1\nСтрока; "2"'
    one = env.tasks.create_task(env.admin, data(env, title=title, description=description))
    env.tasks.create_task(env.admin, data(env, title="Не включать"))
    with pytest.raises(AppError, match="Выберите"):
        env.reports.create_summary(env.ivan, [])
    env.tasks.change_status(env.ivan, one, TaskStatus.IN_PROGRESS)
    report = env.reports.create_task_report(env.ivan, one)
    assert "В работе" in report and "Просрочена: Нет" in report and title in report
    tasks_path, users_path = tmp_path / "tasks.csv", tmp_path / "users.csv"
    env.reports.export_tasks(env.admin, TaskQuery(text="Сводка"), tasks_path)
    env.reports.export_users(env.admin, users_path)
    with tasks_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter=";"))
    assert len(rows) == 1 and rows[0]["Название"] == title and rows[0]["Описание"] == description
    assert "password" not in users_path.read_text(encoding="utf-8-sig") and "$2b$" not in users_path.read_text(encoding="utf-8-sig")
    env.tasks.delete_task(env.admin, one)
    for operation in (lambda: env.reports.create_summary(env.ivan, [one]), lambda: env.tasks.change_status(env.ivan, one, TaskStatus.IN_PROGRESS)):
        with pytest.raises(AccessError):
            operation()
    with env.db.transaction() as cursor:
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        assert {row["table_name"] for row in cursor.fetchall()} == {"users", "categories", "tasks"}


def test_rollback_composite_operation(env):
    with pytest.raises(RuntimeError):
        with env.db.transaction() as cursor:
            cursor.execute("UPDATE users SET login='must_rollback' WHERE id=2")
            cursor.execute("INSERT INTO categories(name) VALUES ('must_rollback')")
            raise RuntimeError("controlled failure")
    assert env.users.get_current(env.ivan).login == "ivan"
    assert "must_rollback" not in [c.name for c in env.tasks.get_categories(env.ivan)]


def concurrent(*operations):
    barrier = Barrier(len(operations))

    def call(operation):
        barrier.wait(timeout=10)
        try:
            operation()
            return "ok"
        except AppError:
            return "blocked"

    with ThreadPoolExecutor(max_workers=len(operations)) as executor:
        return list(executor.map(call, operations))


def test_two_clients_status_uses_locked_current_state(env):
    task_id = env.tasks.create_task(env.admin, data(env))
    env.tasks.change_status(env.ivan, task_id, TaskStatus.IN_PROGRESS)
    outcomes = concurrent(lambda: env.tasks.change_status(env.ivan, task_id, TaskStatus.NEW),
                          lambda: env.tasks.change_status(env.admin, task_id, TaskStatus.COMPLETED))
    assert sorted(outcomes) == ["blocked", "ok"]


@pytest.mark.parametrize("delete", [False, True])
def test_concurrent_last_admin_protection(env, delete):
    with pytest.raises(AppError, match="последнего"):
        env.users.update_user(env.admin, 1, "admin", Role.USER)
    with pytest.raises(AppError, match="последнего"):
        env.users.delete_user(env.admin, 1)
    env.users.update_user(env.admin, 2, "ivan", Role.ADMIN)
    if delete:
        operations = (lambda: env.users.delete_user(env.admin, 1), lambda: env.users.delete_user(env.ivan, 2))
    else:
        operations = (lambda: env.users.update_user(env.admin, 1, "admin", Role.USER),
                      lambda: env.users.update_user(env.ivan, 2, "ivan", Role.USER))
    assert sorted(concurrent(*operations)) == ["blocked", "ok"]
    with env.db.transaction() as cursor:
        cursor.execute("SELECT count(*) AS n FROM users WHERE role='ADMIN'")
        assert cursor.fetchone()["n"] == 1


def test_overdue_excludes_completed_today_future_and_other_users(env):
    late = env.tasks.create_task(env.admin, data(env, due_date=env.today - timedelta(days=1)))
    done = env.tasks.create_task(env.admin, data(env, due_date=env.today - timedelta(days=2)))
    env.tasks.change_status(env.admin, done, TaskStatus.IN_PROGRESS)
    env.tasks.change_status(env.admin, done, TaskStatus.COMPLETED)
    env.tasks.create_task(env.admin, data(env, due_date=env.today))
    env.tasks.create_task(env.admin, data(env, due_date=env.today + timedelta(days=1)))
    other = env.tasks.create_task(env.admin, data(env, assignee_id=3, due_date=env.today - timedelta(days=3)))
    assert [t.id for t in env.tasks.get_tasks(env.ivan, TaskQuery(overdue=True)).tasks] == [late]
    assert {t.id for t in env.tasks.get_tasks(env.admin, TaskQuery(overdue=True)).tasks} == {late, other}
