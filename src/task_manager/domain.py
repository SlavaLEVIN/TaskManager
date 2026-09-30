"""Предметная модель, не зависящая от Qt и PostgreSQL."""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class AppError(Exception):
    """Ожидаемая ошибка, текст которой безопасно показать пользователю."""


class AccessError(AppError):
    pass


class SessionExpired(AccessError):
    pass


class DatabaseError(AppError):
    pass


class Role(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class Priority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TaskStatus(StrEnum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


LABELS = {
    Role.USER: "Пользователь", Role.ADMIN: "Администратор",
    Priority.LOW: "Низкий", Priority.MEDIUM: "Средний", Priority.HIGH: "Высокий",
    TaskStatus.NEW: "Новая", TaskStatus.IN_PROGRESS: "В работе",
    TaskStatus.COMPLETED: "Выполнена",
}
TRANSITIONS = {
    TaskStatus.NEW: (TaskStatus.IN_PROGRESS,),
    TaskStatus.IN_PROGRESS: (TaskStatus.NEW, TaskStatus.COMPLETED),
    TaskStatus.COMPLETED: (TaskStatus.IN_PROGRESS,),
}


def enum_value(enum_type, value):
    try:
        return enum_type(value)
    except (ValueError, TypeError) as exc:
        raise AppError("Выбрано недопустимое значение.") from exc


def required_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError(f"Заполните поле «{label}».")
    if "\x00" in value:
        raise AppError(f"Поле «{label}» содержит недопустимый нулевой символ.")
    return value.strip()


def password_bytes(password: str) -> bytes:
    if not isinstance(password, str) or not password:
        raise AppError("Пароль не должен быть пустым.")
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        raise AppError("bcrypt допускает не более 72 байт UTF-8 в пароле. Кириллица занимает несколько байт на символ.")
    return encoded


@dataclass(frozen=True)
class User:
    id: int
    login: str
    role: Role
    password_hash: str = field(default="", repr=False, compare=False)

    def is_admin(self) -> bool:
        return self.role == Role.ADMIN


@dataclass(frozen=True)
class Session:
    """В памяти хранится только ID, права каждый раз читаются из БД."""
    user_id: int


@dataclass(frozen=True)
class Category:
    id: int
    name: str


@dataclass
class Task:
    id: int
    title: str
    description: str
    assignee_id: int
    category_id: int
    due_date: date
    priority: Priority
    status: TaskStatus
    assignee: str = ""
    category: str = ""

    def change_status(self, new_status: TaskStatus) -> None:
        new_status = enum_value(TaskStatus, new_status)
        if new_status != self.status and new_status not in TRANSITIONS[self.status]:
            raise AppError(f"Переход «{LABELS[self.status]} → {LABELS[new_status]}» запрещён. Обновите список.")
        self.status = new_status

    def is_overdue(self, current_date: date) -> bool:
        return self.due_date < current_date and self.status != TaskStatus.COMPLETED


@dataclass(frozen=True)
class TaskInput:
    title: str
    description: str
    assignee_id: int
    category_id: int
    due_date: date
    priority: Priority

    def validate(self) -> None:
        required_text(self.title, "Название")
        if not isinstance(self.description, str) or "\x00" in self.description:
            raise AppError("Описание содержит недопустимые данные.")
        if type(self.due_date) is not date:
            raise AppError("Укажите существующую дату выполнения.")
        if type(self.assignee_id) is not int or self.assignee_id <= 0:
            raise AppError("Выберите ответственного.")
        if type(self.category_id) is not int or self.category_id <= 0:
            raise AppError("Выберите категорию.")
        enum_value(Priority, self.priority)


@dataclass(frozen=True)
class TaskQuery:
    text: str = ""
    status: TaskStatus | None = None
    priority: Priority | None = None
    category_id: int | None = None
    assignee_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    sort: str = "due_date"
    descending: bool = False

    def validate(self) -> None:
        for value in (self.date_from, self.date_to):
            if value is not None and type(value) is not date:
                raise AppError("Неверная дата фильтра.")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise AppError("Начало диапазона не может быть позже конца.")
        if self.status is not None:
            enum_value(TaskStatus, self.status)
        if self.priority is not None:
            enum_value(Priority, self.priority)
        if not isinstance(self.text, str) or "\x00" in self.text:
            raise AppError("Недопустимый поисковый запрос.")


@dataclass(frozen=True)
class TaskList:
    tasks: list[Task]
    today: date
    user: User
