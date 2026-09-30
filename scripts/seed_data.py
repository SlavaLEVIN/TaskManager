"""Явное демонстрационное / нагрузочное наполнение только пустой БД."""
from datetime import timedelta

import bcrypt

from common import ROOT, database, parser
from task_manager.domain import AppError
from task_manager.services import USER_LOCK

DEMO_PASSWORD = "Demo-2026!"


def seed(db, load=False):
    hashed = bcrypt.hashpw(DEMO_PASSWORD.encode("ascii"), bcrypt.gensalt()).decode("ascii")
    with db.transaction() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (USER_LOCK,))
        cursor.execute("SELECT (SELECT count(*) FROM users)+(SELECT count(*) FROM tasks) AS n")
        if cursor.fetchone()["n"]:
            raise AppError("Наполнение разрешено только в пустую тестовую БД. Рабочие записи не изменены.")
        cursor.execute((ROOT / "database/seed_categories.sql").read_text(encoding="utf-8"))
        cursor.execute("SELECT id FROM categories ORDER BY id")
        categories = [row["id"] for row in cursor.fetchall()]
        logins = ["admin", "ivan", "anna", "empty"] if not load else ["admin"] + [f"user{i:03d}" for i in range(1, 100)]
        users = []
        for index, login in enumerate(logins):
            cursor.execute("INSERT INTO users(login,password_hash,role) VALUES(%s,%s,%s) RETURNING id", (login, hashed, "ADMIN" if index == 0 else "USER"))
            users.append(cursor.fetchone()["id"])
        cursor.execute("SELECT CURRENT_DATE AS today")
        today = cursor.fetchone()["today"]
        for index in range(1000 if load else 12):
            cursor.execute("""INSERT INTO tasks(title,description,assignee_id,category_id,due_date,priority,status)
                              VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                           (f'Задача {index + 1:04d}: проверка "документов"; 100%_готовность',
                            "" if index % 4 == 0 else "Подготовить документацию; сверить данные.\nПроверить подпись «Отдел А».",
                            users[index % (len(users) - 1)], categories[index % len(categories)],
                            today + timedelta(days=(-5, 0, 7, -2)[index % 4]),
                            ("LOW", "MEDIUM", "HIGH")[index % 3],
                            ("NEW", "IN_PROGRESS", "COMPLETED")[(index // 3) % 3]))


def main():
    arguments = parser(__doc__)
    arguments.add_argument("--confirm-demo", action="store_true", required=True)
    arguments.add_argument("--load", action="store_true", help="100 пользователей и 1000 задач")
    args = arguments.parse_args()
    seed(database(args), args.load)
    print("Демонстрационные данные созданы. Логин admin, пароль Demo-2026! (только для тестовой БД).")


if __name__ == "__main__":
    try:
        main()
    except AppError as error:
        raise SystemExit(str(error))
