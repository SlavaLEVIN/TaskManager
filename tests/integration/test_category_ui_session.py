from dataclasses import replace

import pytest
from PySide6.QtWidgets import QMessageBox

from task_manager.ui.presenter import Presenter
from task_manager.ui.views import MainWindow


pytestmark = [pytest.mark.integration, pytest.mark.ui]


def sign_in(window, qtbot, login):
    window.login.login.setText(login)
    window.login.password.setText("Test-Password!")
    window.login.enter.click()
    qtbot.waitUntil(lambda: not window.busy and window.stack.currentWidget() is window.shell, timeout=15000)


def test_admin_can_create_and_rename_category_from_visible_controls(qtbot, env):
    window = MainWindow()
    window.preferences = replace(window.preferences, confirm_exit=False)
    presenter = Presenter(window, env.db)
    qtbot.addWidget(window)
    window.show()
    sign_in(window, qtbot, "admin")
    window.categories_action.trigger()
    qtbot.waitUntil(lambda: not window.busy and window.pages.currentWidget() is window.categories, timeout=15000)
    assert window.categories.create.isVisible()
    window.categories.create.click()
    dialog = presenter.dialog
    assert dialog is not None
    dialog.name.setText("Разработка ПО")
    dialog.submitted.emit()
    qtbot.waitUntil(lambda: not window.busy and presenter.dialog is None and window.categories.model.rowCount() == 3, timeout=15000)
    row = next(i for i, category in enumerate(window.categories.model.objects) if category.name == "Разработка ПО")
    window.categories.table.selectRow(row)
    assert window.categories.rename.isEnabled()
    window.categories.rename.click()
    dialog = presenter.dialog
    dialog.name.setText("Программирование")
    dialog.submitted.emit()
    qtbot.waitUntil(lambda: not window.busy and presenter.dialog is None and
                    any(category.name == "Программирование" for category in window.categories.model.objects), timeout=15000)
    assert "Программирование" in [category.name for category in env.tasks.get_categories(env.admin)]
    window.close()


def test_password_reset_logs_out_idle_user(qtbot, env, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, message: messages.append(message))
    window = MainWindow()
    window.preferences = replace(window.preferences, confirm_exit=False)
    presenter = Presenter(window, env.db)
    qtbot.addWidget(window)
    window.show()
    sign_in(window, qtbot, "ivan")
    assert presenter.session_timer.isActive()
    env.users.reset_password(env.admin, 2, "New-Password!")
    presenter.check_session()
    qtbot.waitUntil(lambda: not window.busy and window.stack.currentWidget() is window.login, timeout=15000)
    assert not presenter.session_timer.isActive()
    assert not window.tasks.model.rowCount()
    assert messages and "Пароль изменён" in messages[-1]
    window.close()
