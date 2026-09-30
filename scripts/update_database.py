"""Обновление существующей базы без пересоздания таблиц и учётных записей."""
from getpass import getpass

import psycopg2
from psycopg2 import sql

from common import ROOT
from task_manager.config import DatabaseConfig
from task_manager.domain import AppError
from setup_database import ask


def upgrade(connection, technical_user):
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (technical_user,))
            if cursor.fetchone() is None:
                raise AppError("Указанная техническая роль не существует.")
            cursor.execute("SELECT to_regclass('public.tasks'), to_regclass('public.users'), to_regclass('public.categories')")
            if any(value is None for value in cursor.fetchone()):
                raise AppError("В выбранной базе нет таблиц TaskManager. Проверьте имя базы.")
            cursor.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE ON public.categories TO {}").format(sql.Identifier(technical_user)))
            cursor.execute(sql.SQL("GRANT USAGE,SELECT ON SEQUENCE public.categories_id_seq TO {}").format(sql.Identifier(technical_user)))
            for old, new in (("Обслуживание", "Разработка"), ("Организационные", "Организация работы")):
                cursor.execute("UPDATE public.categories SET name=%s WHERE name=%s AND NOT EXISTS (SELECT 1 FROM public.categories WHERE lower(name)=lower(%s))", (new, old, new))


def main():
    config = DatabaseConfig.load()
    print("Обновление категорий TaskManager 1.2. Задачи, пользователи и пароли сохраняются.")
    host = ask("Сервер PostgreSQL", config.host)
    port = int(ask("Порт", str(config.port)))
    dbname = ask("Существующая база TaskManager", config.dbname)
    technical_user = ask("Существующая техническая роль клиента", config.user)
    owner = ask("Администратор PostgreSQL", "postgres")
    password = getpass("Пароль администратора PostgreSQL: ")
    print(f"База: {dbname}, сервер: {host}:{port}, клиентская роль: {technical_user}.")
    print("Будут добавлены права создания и переименования категорий. Стандартные названия обновятся.")
    if input("Для продолжения введите UPDATE: ") != "UPDATE":
        print("Обновление отменено.")
        return
    connection = psycopg2.connect(host=host, port=port, dbname=dbname, user=owner, password=password,
                                  connect_timeout=config.connect_timeout, sslmode=config.sslmode)
    try:
        upgrade(connection, technical_user)
    finally:
        connection.close()
    print("Обновление выполнено. Запустите новую версию TaskManager на рабочих компьютерах.")


if __name__ == "__main__":
    try:
        main()
    except (AppError, ValueError, OSError) as error:
        raise SystemExit(str(error))
    except psycopg2.Error as error:
        raise SystemExit(f"Обновление не выполнено ({error.pgcode or type(error).__name__}). Изменения отменены. Проверьте параметры и права администратора PostgreSQL.")
