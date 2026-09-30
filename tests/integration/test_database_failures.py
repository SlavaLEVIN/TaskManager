import time
from dataclasses import replace

import pytest
from PySide6.QtWidgets import QMessageBox

from task_manager.database import Database
from task_manager.domain import DatabaseError
from task_manager.ui.presenter import Presenter
from task_manager.ui.views import MainWindow

pytestmark = pytest.mark.integration


def test_unavailable_server_and_reconnect(env):
    missing = Database(replace(env.db.config, port=1, connect_timeout=2))
    started = time.monotonic()
    with pytest.raises(DatabaseError, match="Повторить подключение"):
        missing.ping()
    assert time.monotonic() - started < 10
    env.db.ping()


def test_connection_cut_during_transaction_rolls_back(env):
    with pytest.raises(DatabaseError):
        with env.db.transaction() as cursor:
            cursor.execute("UPDATE users SET login='must_rollback_cut' WHERE id=2")
            cursor.execute("SELECT pg_backend_pid() AS pid")
            pid = cursor.fetchone()["pid"]
            with env.db.transaction() as killer:
                killer.execute("SELECT pg_terminate_backend(%s)", (pid,))
            cursor.execute("SELECT 1")
    assert env.users.get_current(env.ivan).login == "ivan"


def test_gui_connection_error_can_recover(qtbot, env, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: messages.append(text))
    window = MainWindow()
    qtbot.addWidget(window)
    presenter = Presenter(window, Database(replace(env.db.config, port=1, connect_timeout=2)))
    window.show()
    window.login.retry.click()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert window.connection.property("state") == "error"
    assert messages and window.isVisible() and window.login.enter.isEnabled()
    presenter._services(env.db)
    window.login.retry.click()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert window.connection.property("state") == "ok"
    assert "Соединение исправно" in window.connection.text()
    assert "Проверка завершена" in window.activity.text()
    assert window.stack.currentWidget() is window.login
    window.close_pending = True
    window.close()
