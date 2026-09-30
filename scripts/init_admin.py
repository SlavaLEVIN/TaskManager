"""Создание первого администратора без пароля в исходниках."""
from getpass import getpass

import bcrypt

from common import database, parser
from task_manager.domain import AppError, password_bytes, required_text
from task_manager.services import USER_LOCK


def main():
    args = parser(__doc__).parse_args()
    db = database(args)
    login = required_text(input("Логин первого администратора: "), "Логин")
    password = getpass("Пароль: ")
    if password != getpass("Повторите пароль: "):
        raise AppError("Пароли не совпадают.")
    hashed = bcrypt.hashpw(password_bytes(password), bcrypt.gensalt()).decode("ascii")
    with db.transaction() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (USER_LOCK,))
        cursor.execute("SELECT 1 FROM users WHERE role='ADMIN' LIMIT 1")
        if cursor.fetchone():
            raise AppError("Администратор уже существует. Добавляйте следующие записи через приложение.")
        cursor.execute("INSERT INTO users(login,password_hash,role) VALUES(%s,%s,'ADMIN')", (login, hashed))
    print("Первый администратор создан.")


if __name__ == "__main__":
    try:
        main()
    except AppError as error:
        raise SystemExit(str(error))
