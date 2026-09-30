from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QAbstractSpinBox
from task_manager.config import DatabaseConfig
from task_manager.domain import Role, User
from task_manager.ui.views import MainWindow, SettingsDialog


def test_transient_connection_and_role_specific_help(qtbot):
    window = MainWindow()
    window.close_pending = True
    qtbot.addWidget(window)
    window.show()
    assert not window.connection.isVisible()
    window.set_connection('ok', 'Соединение исправно')
    assert window.connection.isVisible()
    qtbot.waitUntil(lambda: not window.connection.isVisible(), timeout=3500)
    window.set_connection('error', 'Нет связи')
    assert window.toast_timer.interval() == 9000
    window.set_role(User(1, 'admin', Role.ADMIN))
    assert 'Учётные записи' in window.help_text.toPlainText()
    window.set_role(User(2, 'user', Role.USER))
    assert 'Возможности пользователя' in window.help_text.toPlainText()
    assert 'Учётные записи' not in window.help_text.toPlainText()
    assert not window.categories_action.isVisible()
    cursor = window.help_text.document().find('Текущий логин')
    assert cursor.blockFormat().alignment() & Qt.AlignmentFlag.AlignJustify
    for view in (window.tasks, window.reports):
        assert not view.date_from.isEnabled()
        view.date_enabled.setChecked(True)
        view.date_from.setDate(QDate(2026, 9, 29))
        view.date_to.setDate(QDate(2026, 10, 4))
        assert view.date_from.isEnabled() and view.query().date_to.year == 2026
        view.date_enabled.setChecked(False)
        assert view.query().date_from is None
        assert view.table.columnWidth(6) < 200
    dialog = SettingsDialog(DatabaseConfig(), window)
    qtbot.addWidget(dialog)
    for field in ('port', 'connect_timeout', 'statement_timeout'):
        assert dialog.fields[field].buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
