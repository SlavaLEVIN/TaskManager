"""Интерактивная первичная установка в НОВУЮ PostgreSQL БД."""
from getpass import getpass
from pathlib import Path

import bcrypt
import psycopg2
from psycopg2 import sql

from common import ROOT
from task_manager.config import DatabaseConfig, config_path
from task_manager.domain import AppError, password_bytes, required_text


def ask(label, default):
    return input(f"{label} [{default}]: ").strip() or default


def main():
    print("Создание новой БД. PostgreSQL должен быть установлен и запущен.")
    print("Существующие роли и базы этот мастер не изменяет.")
    host = ask("Сервер PostgreSQL", "127.0.0.1")
    port = int(ask("Порт", "5432"))
    owner = ask("Служебный администратор PostgreSQL", "postgres")
    owner_password = getpass("Пароль служебного администратора PostgreSQL: ")
    dbname = ask("Имя НОВОЙ базы", "task_manager")
    technical_user = ask("Имя НОВОЙ технической роли клиента", "task_client")
    technical_password = getpass("Задайте пароль технической роли: ")
    if not technical_password or technical_password != getpass("Повторите пароль технической роли: "):
        raise AppError("Пароли технической роли не совпадают или пусты.")
    login = required_text(ask("Логин администратора приложения", "admin"), "Логин")
    password = getpass("Задайте пароль администратора приложения: ")
    if password != getpass("Повторите пароль администратора приложения: "):
        raise AppError("Пароли администратора приложения не совпадают.")
    hashed = bcrypt.hashpw(password_bytes(password), bcrypt.gensalt()).decode("ascii")
    print(f"Будут созданы база {dbname!r} и техническая роль {technical_user!r} на сервере {host}:{port}.")
    if input("Для продолжения введите CREATE: ") != "CREATE":
        print("Установка отменена; изменений нет.")
        return
    connection = psycopg2.connect(host=host, port=port, dbname="postgres", user=owner, password=owner_password, connect_timeout=5)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (dbname,))
            if cursor.fetchone():
                raise AppError("База уже существует. Используйте её конфигурацию или другое имя новой БД.")
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (technical_user,))
            if cursor.fetchone():
                raise AppError("Техническая роль уже существует. Выберите новое имя либо настройте доступ вручную по руководству.")
            cursor.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE").format(sql.Identifier(technical_user)), (technical_password,))
            cursor.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0").format(sql.Identifier(dbname)))
            cursor.execute(sql.SQL("ALTER DATABASE {} SET timezone TO 'Europe/Moscow'").format(sql.Identifier(dbname)))
    finally:
        connection.close()
    connection = psycopg2.connect(host=host, port=port, dbname=dbname, user=owner, password=owner_password, connect_timeout=5)
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute((ROOT / "database/create_schema.sql").read_text(encoding="utf-8"))
                cursor.execute((ROOT / "database/seed_categories.sql").read_text(encoding="utf-8"))
                cursor.execute("INSERT INTO users(login,password_hash,role) VALUES(%s,%s,'ADMIN')", (login, hashed))
                cursor.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
                cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(technical_user)))
                cursor.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON users,tasks TO {}").format(sql.Identifier(technical_user)))
                cursor.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE ON categories TO {}").format(sql.Identifier(technical_user)))
                cursor.execute(sql.SQL("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(sql.Identifier(technical_user)))
                cursor.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(dbname)))
                cursor.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(dbname), sql.Identifier(technical_user)))
    finally:
        connection.close()
    DatabaseConfig(host=host, port=port, dbname=dbname, user=technical_user, password=technical_password).save()
    print(f"Готово. Настройки клиента сохранены: {config_path()}")
    print(f"Запустите START.cmd и войдите как {login!r} с заданным паролем приложения.")


if __name__ == "__main__":
    try:
        main()
    except (AppError, ValueError, OSError) as error:
        raise SystemExit(str(error))
    except psycopg2.Error as error:
        raise SystemExit(f"Ошибка PostgreSQL ({error.pgcode or type(error).__name__}). Проверьте сервер и права. Если создание уже началось, объекты могли сохраниться; автоматического удаления нет.")
