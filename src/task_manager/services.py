"""Прикладные сценарии. Каждый публичный метод заново проверяет полномочия."""

import csv
import os
import tempfile
from pathlib import Path

import bcrypt

from .database import Database
from .domain import (
    AccessError, AppError, Category, LABELS, Priority, Role, Session, SessionExpired,
    Task, TaskInput, TaskList, TaskQuery, TaskStatus, User, enum_value, password_bytes,
    required_text,
)

# Один порядок блокировок для операций с пользователями исключает взаимную блокировку
# при конкурентном понижении двух администраторов. Ключ относится только к этой БД.
USER_LOCK = 74192136


def safe_user(row) -> User:
    return User(row["id"], row["login"], Role(row["role"]))


def current_user(cursor, session: Session, admin: bool = False) -> User:
    if not isinstance(session, Session):
        raise SessionExpired("Войдите в учётную запись.")
    cursor.execute("SELECT id,login,role FROM users WHERE id=%s", (session.user_id,))
    row = cursor.fetchone()
    if row is None:
        raise SessionExpired("Учётная запись удалена. Выполните вход заново.")
    user = safe_user(row)
    if admin and not user.is_admin():
        raise AccessError("Действие доступно только администратору. Права могли измениться.")
    return user


class UserService:
    """Управление учётными записями и получение безопасных данных о сессии."""

    def __init__(self, database: Database):
        self.database = database

    def get_current(self, session: Session) -> User:
        with self.database.transaction() as cursor:
            return current_user(cursor, session)

    def get_users(self, session: Session) -> list[User]:
        with self.database.transaction() as cursor:
            current_user(cursor, session, admin=True)
            cursor.execute("SELECT id,login,role FROM users ORDER BY lower(login),id")
            return [safe_user(row) for row in cursor.fetchall()]

    def _credentials(self, login: str) -> User | None:
        with self.database.transaction() as cursor:
            cursor.execute("SELECT id,login,role,password_hash FROM users WHERE lower(login)=lower(%s)", (login,))
            row = cursor.fetchone()
            return User(row["id"], row["login"], Role(row["role"]), row["password_hash"]) if row else None

    def create_user(self, session: Session, login: str, password: str, role: Role) -> int:
        login = required_text(login, "Логин")
        role = enum_value(Role, role)
        hashed = bcrypt.hashpw(password_bytes(password), bcrypt.gensalt()).decode("ascii")
        with self.database.transaction() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (USER_LOCK,))
            current_user(cursor, session, admin=True)
            cursor.execute("INSERT INTO users(login,password_hash,role) VALUES(%s,%s,%s) RETURNING id", (login, hashed, role))
            return cursor.fetchone()["id"]

    @staticmethod
    def _target(cursor, user_id: int):
        cursor.execute("SELECT id,role FROM users WHERE id=%s FOR UPDATE", (user_id,))
        row = cursor.fetchone()
        if row is None:
            raise AppError("Пользователь уже удалён. Обновите список.")
        return row

    @staticmethod
    def _protect_last(cursor, target, next_role=None):
        if target["role"] == Role.ADMIN and next_role != Role.ADMIN:
            cursor.execute("SELECT count(*) AS n FROM users WHERE role='ADMIN'")
            if cursor.fetchone()["n"] <= 1:
                raise AppError("Нельзя удалить или понизить последнего администратора.")

    def update_user(self, session: Session, user_id: int, login: str, role: Role) -> None:
        login = required_text(login, "Логин")
        role = enum_value(Role, role)
        with self.database.transaction() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (USER_LOCK,))
            current_user(cursor, session, admin=True)
            target = self._target(cursor, user_id)
            self._protect_last(cursor, target, role)
            cursor.execute("UPDATE users SET login=%s,role=%s WHERE id=%s", (login, role, user_id))

    def delete_user(self, session: Session, user_id: int) -> None:
        with self.database.transaction() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (USER_LOCK,))
            current_user(cursor, session, admin=True)
            target = self._target(cursor, user_id)
            cursor.execute("SELECT 1 FROM tasks WHERE assignee_id=%s LIMIT 1", (user_id,))
            if cursor.fetchone():
                raise AppError("У пользователя есть задачи. Сначала переназначьте все его задачи другому исполнителю.")
            self._protect_last(cursor, target)
            cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))

    def reset_password(self, session: Session, user_id: int, password: str) -> None:
        hashed = bcrypt.hashpw(password_bytes(password), bcrypt.gensalt()).decode("ascii")
        with self.database.transaction() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (USER_LOCK,))
            current_user(cursor, session, admin=True)
            self._target(cursor, user_id)
            cursor.execute("UPDATE users SET password_hash=%s WHERE id=%s", (hashed, user_id))


class AuthService:
    def __init__(self, user_service: UserService):
        self.user_service = user_service

    def authenticate(self, login: str, password: str) -> tuple[Session, User]:
        login = required_text(login, "Логин")
        encoded = password_bytes(password)
        user = self.user_service._credentials(login)
        if user is None or not bcrypt.checkpw(encoded, user.password_hash.encode("ascii")):
            raise AppError("Неверный логин или пароль.")
        session = Session(user.id)
        return session, self.user_service.get_current(session)


TASK_SELECT = """
SELECT t.id,t.title,t.description,t.assignee_id,t.category_id,t.due_date,
       t.priority,t.status,u.login AS assignee,c.name AS category
FROM tasks t JOIN users u ON u.id=t.assignee_id
JOIN categories c ON c.id=t.category_id
"""
SORT_FIELDS = {
    "title": "lower(t.title)", "due_date": "t.due_date", "category": "lower(c.name)",
    "priority": "CASE t.priority WHEN 'LOW' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END",
    "status": "CASE t.status WHEN 'NEW' THEN 1 WHEN 'IN_PROGRESS' THEN 2 ELSE 3 END",
}


def make_task(row) -> Task:
    values = dict(row)
    values["priority"] = Priority(values["priority"])
    values["status"] = TaskStatus(values["status"])
    return Task(**values)


class TaskService:
    """Отбор задач, управление назначением и допустимыми переходами статуса."""

    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _read(cursor, user: User, query: TaskQuery, ids: list[int] | None = None) -> list[Task]:
        query.validate()
        if query.sort not in SORT_FIELDS:
            raise AppError("Недопустимое поле сортировки.")
        conditions, params = [], []
        if not user.is_admin():
            conditions.append("t.assignee_id=%s")
            params.append(user.id)
        for field, value in (("status", query.status), ("priority", query.priority),
                             ("category_id", query.category_id), ("assignee_id", query.assignee_id)):
            if value is not None:
                conditions.append(f"t.{field}=%s")
                params.append(value)
        if query.text:
            # strpos не интерпретирует %, _ и кавычки как шаблон поиска.
            conditions.append("(strpos(lower(t.title),lower(%s))>0 OR strpos(lower(t.description),lower(%s))>0)")
            params.extend((query.text, query.text))
        for operator, value in ((">=", query.date_from), ("<=", query.date_to)):
            if value is not None:
                conditions.append(f"t.due_date {operator} %s")
                params.append(value)
        if ids is not None:
            conditions.append("t.id=ANY(%s)")
            params.append(ids)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        direction = "DESC" if query.descending else "ASC"
        cursor.execute(TASK_SELECT + where + f" ORDER BY {SORT_FIELDS[query.sort]} {direction},t.id {direction}", params)
        return [make_task(row) for row in cursor.fetchall()]

    def get_tasks(self, session: Session, query: TaskQuery = TaskQuery(), *, require_admin=False) -> TaskList:
        with self.database.transaction() as cursor:
            user = current_user(cursor, session, admin=require_admin)
            cursor.execute("SELECT CURRENT_DATE AS today")
            today = cursor.fetchone()["today"]
            return TaskList(self._read(cursor, user, query), today, user)

    def get_selected(self, session: Session, task_ids: list[int]) -> TaskList:
        if not task_ids:
            raise AppError("Выберите хотя бы одну задачу.")
        ids = list(dict.fromkeys(task_ids))
        if any(type(value) is not int for value in ids):
            raise AppError("Неверный выбор задач.")
        with self.database.transaction() as cursor:
            user = current_user(cursor, session)
            cursor.execute("SELECT CURRENT_DATE AS today")
            today = cursor.fetchone()["today"]
            tasks = self._read(cursor, user, TaskQuery(), ids)
            if len(tasks) != len(ids):
                raise AccessError("Одна из выбранных задач удалена или больше недоступна. Обновите список и выбор.")
            return TaskList(tasks, today, user)

    def get_categories(self, session: Session) -> list[Category]:
        with self.database.transaction() as cursor:
            current_user(cursor, session)
            cursor.execute("SELECT id,name FROM categories ORDER BY name,id")
            return [Category(**row) for row in cursor.fetchall()]

    @staticmethod
    def _references(cursor, data: TaskInput):
        cursor.execute("SELECT id FROM users WHERE id=%s FOR KEY SHARE", (data.assignee_id,))
        if cursor.fetchone() is None:
            raise AppError("Ответственный не существует. Обновите список пользователей.")
        cursor.execute("SELECT id FROM categories WHERE id=%s FOR KEY SHARE", (data.category_id,))
        if cursor.fetchone() is None:
            raise AppError("Категория не существует. Обновите справочник.")

    @staticmethod
    def _locked_task(cursor, user: User, task_id: int) -> Task:
        cursor.execute(TASK_SELECT + " WHERE t.id=%s FOR UPDATE OF t", (task_id,))
        row = cursor.fetchone()
        if row is None or (not user.is_admin() and row["assignee_id"] != user.id):
            raise AccessError("Задача удалена или недоступна. Обновите список.")
        return make_task(row)

    def create_task(self, session: Session, data: TaskInput) -> int:
        data.validate()
        with self.database.transaction() as cursor:
            current_user(cursor, session, admin=True)
            self._references(cursor, data)
            cursor.execute("""INSERT INTO tasks(title,description,assignee_id,category_id,due_date,priority)
                           VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",
                           (data.title, data.description, data.assignee_id, data.category_id, data.due_date, data.priority))
            return cursor.fetchone()["id"]

    def update_task(self, session: Session, task_id: int, data: TaskInput, status: TaskStatus | None = None) -> None:
        data.validate()
        with self.database.transaction() as cursor:
            user = current_user(cursor, session, admin=True)
            task = self._locked_task(cursor, user, task_id)
            self._references(cursor, data)
            if status is not None:
                task.change_status(status)
            cursor.execute("""UPDATE tasks SET title=%s,description=%s,assignee_id=%s,category_id=%s,
                           due_date=%s,priority=%s,status=%s WHERE id=%s""",
                           (data.title, data.description, data.assignee_id, data.category_id,
                            data.due_date, data.priority, task.status, task_id))

    def delete_task(self, session: Session, task_id: int) -> None:
        with self.database.transaction() as cursor:
            user = current_user(cursor, session, admin=True)
            self._locked_task(cursor, user, task_id)
            cursor.execute("DELETE FROM tasks WHERE id=%s", (task_id,))

    def change_status(self, session: Session, task_id: int, status: TaskStatus) -> None:
        with self.database.transaction() as cursor:
            user = current_user(cursor, session)
            task = self._locked_task(cursor, user, task_id)
            task.change_status(status)
            cursor.execute("UPDATE tasks SET status=%s WHERE id=%s", (task.status, task_id))


def write_csv(path: str | Path, headers: list[str], rows: list[list]) -> None:
    """Запись через временный файл в той же папке не оставляет частичный CSV."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", dir=path.parent,
                                         prefix=".taskmanager-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
            writer.writerow(headers)
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise AppError("Не удалось записать CSV. Проверьте папку, свободное место и не открыт ли файл в Excel.") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class ReportService:
    def __init__(self, task_service: TaskService, user_service: UserService):
        self.task_service = task_service
        self.user_service = user_service

    def create_task_report(self, session: Session, task_id: int) -> str:
        return self.create_summary(session, [task_id])

    def create_summary(self, session: Session, task_ids: list[int]) -> str:
        result = self.task_service.get_selected(session, task_ids)
        lines = ["ОТЧЁТ ПО ЗАДАЧАМ", f"Дата сервера: {result.today:%d.%m.%Y}", f"Количество задач: {len(result.tasks)}", ""]
        for task in result.tasks:
            lines.extend((f"Задача №{task.id}: {task.title}", f"Ответственный: {task.assignee}",
                          f"Категория: {task.category}", f"Приоритет: {LABELS[task.priority]}",
                          f"Срок: {task.due_date:%d.%m.%Y}", f"Статус: {LABELS[task.status]}",
                          f"Просрочена: {'Да' if task.is_overdue(result.today) else 'Нет'}",
                          f"Описание: {task.description}", "", "─" * 48, ""))
        return "\n".join(lines)

    def export_tasks(self, session: Session, query: TaskQuery, path: str | Path) -> None:
        result = self.task_service.get_tasks(session, query, require_admin=True)
        write_csv(path, ["ID", "Название", "Описание", "Ответственный", "Категория", "Приоритет", "Срок", "Статус", "Просрочена"],
                  [[t.id, t.title, t.description, t.assignee, t.category, LABELS[t.priority], t.due_date.isoformat(),
                    LABELS[t.status], "Да" if t.is_overdue(result.today) else "Нет"] for t in result.tasks])

    def export_users(self, session: Session, path: str | Path) -> None:
        users = self.user_service.get_users(session)
        write_csv(path, ["ID", "Логин", "Роль"], [[u.id, u.login, LABELS[u.role]] for u in users])
