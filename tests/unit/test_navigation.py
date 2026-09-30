from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from task_manager.ui.views import MainWindow, UserDialog


def click_box_button(text):
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QMessageBox):
            for button in widget.buttons():
                if button.text() == text:
                    button.click()
                    return
    QTimer.singleShot(20, lambda: click_box_button(text))


def test_close_confirmation_cancel_preserves_screen(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    for page in (window.login, window.shell):
        window.stack.setCurrentWidget(page)
        QTimer.singleShot(10, lambda: click_box_button("Отмена"))
        assert not window.close()
        assert window.stack.currentWidget() is page and window.isVisible()
    QTimer.singleShot(10, lambda: click_box_button("Выйти"))
    assert window.close()
    window.close_pending = True


def test_help_returns_and_form_cancel_does_not_save(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.pages.setCurrentWidget(window.tasks)
    window.show_help()
    window.help_back.click()
    assert window.pages.currentWidget() is window.tasks
    dialog = UserDialog(window)
    qtbot.addWidget(dialog)
    saved = []
    dialog.submitted.connect(lambda: saved.append(True))
    dialog.login.setText("unsaved")
    dialog.reject()
    assert not saved
    window.close_pending = True


def test_exit_cancel_preserves_unsaved_form(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    dialog = UserDialog(window)
    qtbot.addWidget(dialog)
    dialog.login.setText("Введённый логин")
    dialog.open()
    QTimer.singleShot(10, lambda: click_box_button("Отмена"))
    assert not window.close()
    assert dialog.isVisible() and dialog.login.text() == "Введённый логин"
    dialog.reject()
    window.close_pending = True


def test_large_report_selection_does_not_expand_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.stack.setCurrentWidget(window.shell)
    window.pages.setCurrentWidget(window.reports)
    text = "\n".join(f"№{i} <b>Задача {i}</b>" for i in range(1000))
    window.reports.selection.setPlainText(text)
    window.show()
    qtbot.wait(20)
    assert window.height() == 800
    assert window.reports.selection.verticalScrollBar().maximum() > 0
    assert "<b>" in window.reports.selection.toPlainText()
    window.close_pending = True
