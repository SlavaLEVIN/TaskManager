"""Отдельное соединение и транзакция на каждую операцию."""

import logging
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

from .config import DatabaseConfig
from .domain import AppError, DatabaseError

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, config: DatabaseConfig):
        config.validate()
        self.config = config

    @contextmanager
    def transaction(self):
        connection = None
        phase = "connect"
        try:
            values = vars(self.config).copy()
            timeout = values.pop("statement_timeout")
            connection = psycopg2.connect(
                **values, application_name="TaskManager",
                options=f"-c statement_timeout={timeout} -c lock_timeout=5000 -c idle_in_transaction_session_timeout=30000",
                keepalives=1, keepalives_idle=5, keepalives_interval=2, keepalives_count=3,
            )
            phase = "query"
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
            phase = "commit"
            connection.commit()
        except psycopg2.Error as exc:
            # Текст драйвера может содержать SQL и секреты, журналируем только код и этап.
            logger.error("Database failure phase=%s type=%s sqlstate=%s", phase, type(exc).__name__, exc.pgcode)
            if connection is not None:
                try:
                    connection.rollback()
                except psycopg2.Error:
                    pass
            if isinstance(exc, psycopg2.errors.UniqueViolation):
                raise AppError("Этот логин уже занят (регистр букв не учитывается).") from None
            if isinstance(exc, psycopg2.errors.ForeignKeyViolation):
                raise AppError("Запись связана с задачами или выбранный пользователь/категория уже удалены. Обновите список.") from None
            if isinstance(exc, (psycopg2.errors.CheckViolation, psycopg2.errors.NotNullViolation)):
                raise AppError("Данные не соответствуют обязательным ограничениям БД.") from None
            if phase == "commit":
                raise DatabaseError("Связь потеряна при подтверждении записи. Результат неизвестен. Восстановите подключение и обновите список перед повтором.") from None
            raise DatabaseError("База данных недоступна или операция прервана. Проверьте настройки и сервер, затем нажмите «Повторить подключение».") from None
        except Exception:
            if connection is not None:
                try:
                    connection.rollback()
                except psycopg2.Error:
                    pass
            raise
        finally:
            if connection is not None:
                connection.close()

    def ping(self) -> None:
        with self.transaction() as cursor:
            cursor.execute("SELECT id FROM users LIMIT 1")
            cursor.execute("SELECT id FROM categories LIMIT 1")
            cursor.execute("SELECT id FROM tasks LIMIT 1")
