"""Воспроизводимые снимки интерфейса с демонстрационными данными, без обращения к БД."""
import argparse
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QPoint, QLocale
from PySide6.QtWidgets import QApplication

from common import ROOT
from task_manager.domain import Category, Priority, Role, Task, TaskList, TaskStatus, User
from task_manager.preferences import Preferences
from task_manager.ui.theme import apply_theme
from task_manager.ui.views import MainWindow, PreferencesDialog, TaskDialog, UserDialog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/screenshots/v1.1")
    args = parser.parse_args()
    destination = Path(args.output)
    destination.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    QLocale.setDefault(QLocale(QLocale.Language.Russian, QLocale.Country.Russia))
    today = date(2026, 9, 30)
    users = [User(1, "admin", Role.ADMIN), User(2, "slava", Role.USER)]
    categories = [Category(1, "Документация"), Category(2, "Организационные")]
    tasks = [Task(1, "Подготовить пояснительную записку", "Проверить структуру, оформить рисунки и список источников.", 2, 1, today + timedelta(days=2), Priority.HIGH, TaskStatus.NEW, "slava", "Документация"),
             Task(2, "Проверить совместную работу в сети", "Проверка на двух компьютерах Windows.", 2, 2, today, Priority.MEDIUM, TaskStatus.IN_PROGRESS, "slava", "Организационные"),
             Task(3, "Согласовать план проекта", "План согласован с руководителем.", 1, 2, today - timedelta(days=2), Priority.LOW, TaskStatus.COMPLETED, "admin", "Организационные"),
             Task(4, "Оформить техническое задание", "Уточнить требования и критерии приёмки.", 2, 1, today - timedelta(days=1), Priority.HIGH, TaskStatus.NEW, "slava", "Документация")]
    result = TaskList(tasks, today, users[0])
    window = MainWindow()
    window.show()
    assert window.fontMetrics().inFontUcs4(ord("М")), "Russian font glyphs are unavailable in the rendering environment"

    def capture(widget, name):
        app.processEvents()
        assert widget.grab().save(str(destination / f"{theme}-{name}.png"))

    for theme in ("light", "dark"):
        preferences = Preferences(theme=theme)
        window.preferences = preferences
        apply_theme(preferences)
        window.stack.setCurrentWidget(window.login)
        window.set_activity("")
        capture(window, "login")
        window.stack.setCurrentWidget(window.shell)
        window.set_role(users[0])
        window.set_connection("ok", "Соединение исправно · 14:30")
        window.tasks.model.set_tasks(result)
        window.tasks.count.setText("Найдено задач: 4 · Дата сервера: 30.09.2026")
        window.tasks.table.selectRow(1)
        window.pages.setCurrentWidget(window.tasks)
        capture(window, "tasks")
        window.tasks.status.showPopup()
        capture(window.tasks.status.view().window(), "status-popup")
        window.tasks.status.hidePopup()
        dialog = TaskDialog(users, categories, today, window)
        dialog.show()
        capture(dialog, "task-dialog")
        dialog.category.showPopup()
        capture(dialog.category.view().window(), "category-popup")
        dialog.category.hidePopup()
        # Собственный календарь имеет стабильную геометрию при разных системных темах.
        calendar = dialog.due_date.calendarWidget()
        calendar.show()
        capture(calendar, "calendar")
        calendar.hide()
        dialog.close()
        user_dialog = UserDialog(window)
        user_dialog.show()
        user_dialog.role.showPopup()
        capture(user_dialog.role.view().window(), "role-popup")
        user_dialog.role.hidePopup()
        user_dialog.close()
        preferences_dialog = PreferencesDialog(preferences, window)
        preferences_dialog.show()
        capture(preferences_dialog, "settings")
        preferences_dialog.close()
        window.reports.model.set_tasks(result)
        window.reports.table.selectAll()
        window.pages.setCurrentWidget(window.reports)
        capture(window, "reports")
        window.menu_button.menu().popup(window.menu_button.mapToGlobal(QPoint(0, window.menu_button.height())))
        capture(window.menu_button.menu(), "menu")
        window.menu_button.menu().hide()
        window.preferences = Preferences(theme=theme, font_size=16)
        apply_theme(window.preferences)
        window.resize(1050, 720)
        window.pages.setCurrentWidget(window.tasks)
        capture(window, "tasks-large-text")
        window.resize(1200, 800)
    window.close_pending = True
    window.close()
    print(f"Screenshots saved to {destination}")


if __name__ == "__main__":
    main()
