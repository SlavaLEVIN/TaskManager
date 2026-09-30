from dataclasses import replace

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QCalendarWidget, QDialogButtonBox

from task_manager.domain import Role, User
from task_manager.preferences import Preferences
from task_manager.ui.presenter import Presenter
from task_manager.ui.theme import apply_theme
from task_manager.ui.views import MainWindow, PreferencesDialog, UserDialog


def contrast(first, second):
    def luminance(color):
        values = [color.redF(), color.greenF(), color.blueF()]
        values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(v * weight for v, weight in zip(values, (.2126, .7152, .0722)))
    a, b = sorted((luminance(first), luminance(second)))
    return (b + .05) / (a + .05)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_theme_applies_to_dialogs_popups_and_identity(qtbot, theme):
    window = MainWindow()
    window.close_pending = True
    qtbot.addWidget(window)
    apply_theme(Preferences(theme=theme))
    window.set_role(User(1, "Слава", Role.ADMIN))
    window.show()
    window.stack.setCurrentWidget(window.shell)
    dialog = UserDialog(window)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.role.showPopup()
    qtbot.wait(20)
    for widget, foreground, background in (
        (window.identity, QPalette.ColorRole.WindowText, QPalette.ColorRole.Window),
        (dialog.role.view(), QPalette.ColorRole.Text, QPalette.ColorRole.Base),
        (window.tasks.date_from.calendarWidget(), QPalette.ColorRole.WindowText, QPalette.ColorRole.Window),
    ):
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            backdrop = widget.palette().color(group, background)
            if backdrop.alpha() == 0:
                backdrop = window.palette().color(group, QPalette.ColorRole.Window)
            assert contrast(widget.palette().color(group, foreground), backdrop) >= 4.5
    assert "Слава" in window.identity.text() and "Администратор" in window.identity.text()
    assert len(window.menu_button.menu().actions()) == 6
    dialog.role.hidePopup()
    dialog.reject()
    window.close_pending = True


def test_preferences_persist_and_cancel_does_not_change(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    preferences = Preferences(theme="dark", font_size=15, start_page="home", confirm_exit=False)
    preferences.save()
    assert Preferences.load() == preferences
    window = MainWindow()
    window.close_pending = True
    qtbot.addWidget(window)
    assert window.preferences == preferences
    dialog = PreferencesDialog(preferences, window)
    qtbot.addWidget(dialog)
    dialog.theme.setCurrentIndex(dialog.theme.findData("light"))
    dialog.reject()
    assert Preferences.load() == preferences
    window.close_pending = True


def test_invalid_preferences_recover_to_default(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text('{"theme":"unknown"}')
    assert Preferences.load(path) == Preferences()
