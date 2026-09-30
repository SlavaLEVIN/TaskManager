import pytest
from PySide6.QtWidgets import QMessageBox

from task_manager.domain import Priority, Role, TaskInput
from task_manager.ui.presenter import Presenter
from task_manager.ui.views import MainWindow

pytestmark = [pytest.mark.integration, pytest.mark.ui]


def test_ui_to_database_and_role_change(qtbot, env, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: messages.append(text))
    window = MainWindow()
    presenter = Presenter(window, env.db)
    qtbot.addWidget(window)
    window.show()

    def wait():
        qtbot.waitUntil(lambda: not window.busy, timeout=15000)

    window.login.login.setText("admin")
    window.login.password.setText("Test-Password!")
    window.login.enter.click()
    wait()
    assert window.stack.currentWidget() is window.shell
    window.tasks_button.click()
    wait()
    window.tasks.create.click()
    wait()
    dialog = presenter.dialog
    assert dialog is not None
    dialog.title.setText('Задача из формы; "Кириллица"')
    dialog.description.setPlainText("Описание\nиз интерфейса")
    dialog.assignee.setCurrentIndex(dialog.assignee.findData(2))
    dialog.submitted.emit()
    qtbot.waitUntil(lambda: not window.busy and presenter.dialog is None and window.tasks.model.rowCount() == 1, timeout=15000)
    task = env.tasks.get_tasks(env.ivan).tasks[0]
    assert task.title == 'Задача из формы; "Кириллица"' and task.description == "Описание\nиз интерфейса"
    window.tasks.table.selectRow(0)
    assert not window.tasks.complete.isEnabled()
    window.tasks.change.click()
    wait()
    assert window.tasks.complete.isEnabled()
    window.tasks.complete.click()
    wait()
    assert "Выполнена" in window.tasks.model.rows[0]
    window.tasks.report.click()
    wait()
    assert "Кириллица" in window.reports.text.toPlainText()
    assert "Выполнена: 1" in window.reports.text.toPlainText()
    env.tasks.create_task(env.admin, TaskInput("Новая задача", "", 2, 1, env.today, Priority.LOW))
    window.reports_button.click()
    wait()
    assert window.reports.model.rowCount() == 2
    window.reports.select_all.click()
    window.reports.generate.click()
    wait()
    assert "Новая: 1" in window.reports.text.toPlainText()
    assert "Выполнена: 1" in window.reports.text.toPlainText()
    current_page = window.pages.currentWidget()
    window.retry.click()
    wait()
    assert window.pages.currentWidget() is current_page
    assert window.connection.property("state") == "ok"
    assert "Проверка завершена" in window.activity.text()
    window.logout.trigger()
    assert window.tasks.model.rowCount() == 0 and not window.reports.text.toPlainText()
    window.login.login.setText("ivan")
    window.login.password.setText("Test-Password!")
    window.login.enter.click()
    wait()
    window.tasks_button.click()
    wait()
    assert window.tasks.model.rowCount() == 2 and window.tasks.create.isHidden()
    env.users.update_user(env.admin, 2, "ivan", Role.ADMIN)
    window.tasks.refresh.click()
    wait()
    assert window.tasks.model.rowCount() == 0 and not window.tasks.create.isHidden()
    env.users.update_user(env.admin, 2, "ivan", Role.USER)
    window.users_button.click()
    wait()
    assert window.users.model.rowCount() == 0 and window.users_button.isHidden()
    assert messages and "администратору" in messages[-1]
    window.close_pending = True
    window.close()
