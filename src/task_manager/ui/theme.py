"""Одна палитра для окон, диалогов, календарей и всплывающих списков."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QTextCharFormat
from PySide6.QtWidgets import QApplication, QCalendarWidget


COLORS = {
    "light": dict(bg="#f3f5fa", surface="#ffffff", text="#18283e", muted="#52647b",
                  border="#c5cfdd", hover="#e7eef9", accent="#2459bd", selected="#d9e8ff",
                  selected_text="#122c51", disabled="#6a7789", alternate="#f5f8fc",
                  danger="#b42318", success="#087443"),
    "dark": dict(bg="#141c29", surface="#202c3d", text="#edf3fb", muted="#b3c1d4",
                 border="#53647c", hover="#30435e", accent="#376ccb", selected="#324f79",
                 selected_text="#ffffff", disabled="#a0aec1", alternate="#253347",
                 danger="#ffaaa3", success="#86e5b2"),
}


def apply_theme(preferences):
    app = QApplication.instance()
    app.setStyle("Fusion")
    app.setProperty("taskManagerTheme", preferences.theme)
    c = COLORS[preferences.theme]
    resources = Path(__file__).resolve().parents[1] / "resources"
    check = (resources / "check.svg").as_posix()
    arrow = (resources / f"arrow-{preferences.theme}.svg").as_posix()
    up = (resources / f"up-{preferences.theme}.svg").as_posix()
    palette = QPalette()
    roles = {"Window": "bg", "WindowText": "text", "Base": "surface", "AlternateBase": "alternate",
             "Text": "text", "Button": "surface", "ButtonText": "text", "ToolTipBase": "surface",
             "ToolTipText": "text", "Highlight": "selected", "HighlightedText": "selected_text",
             "PlaceholderText": "muted", "Link": "text", "LinkVisited": "muted",
             "Light": "surface", "Midlight": "hover", "Mid": "border", "Dark": "border", "Shadow": "bg"}
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled):
        for role, color in roles.items():
            palette.setColor(group, getattr(QPalette.ColorRole, role), QColor(c[color]))
        if group == QPalette.ColorGroup.Disabled:
            for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
                palette.setColor(group, role, QColor(c["disabled"]))
    app.setPalette(palette)
    app.setStyleSheet(f"""
        QWidget {{ font-family: 'Segoe UI', sans-serif; font-size: {preferences.font_size}px; color: {c['text']}; }}
        QMainWindow, QDialog, QMessageBox {{ background: {c['bg']}; }}
        QLabel {{ background: transparent; }}
        QLabel#headline {{ font-size: 25px; font-weight: 600; margin: 6px 0; }}
        QLabel#muted {{ color: {c['muted']}; }}
        QLabel#identity {{ font-size: 15px; font-weight: 600; padding: 8px; }}
        QFrame#card {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; }}
        QLabel#connection {{ padding: 7px 10px; border-radius: 6px; background: {c['hover']}; }}
        QLabel#connection[state='ok'] {{ color: {c['success']}; }}
        QLabel#connection[state='error'] {{ color: {c['danger']}; }}
        QPushButton, QToolButton {{ padding: 7px 12px; border: 1px solid {c['border']}; border-radius: 6px;
                                 background: {c['surface']}; color: {c['text']}; }}
        QPushButton:hover, QToolButton:hover {{ background: {c['hover']}; }}
        QPushButton:pressed, QToolButton:pressed {{ background: {c['selected']}; }}
        QPushButton:focus, QToolButton:focus {{ border-color: {c['accent']}; }}
        QPushButton:disabled, QToolButton:disabled {{ color: {c['disabled']}; background: {c['bg']}; }}
        QPushButton#primary:enabled {{ background: {c['accent']}; color: #ffffff; border-color: {c['accent']}; }}
        QPushButton#primary:hover:enabled {{ background: #316ccc; }}
        QLineEdit, QComboBox, QDateEdit, QSpinBox {{ padding: 6px; min-height: 20px;
            border: 1px solid {c['border']}; border-radius: 5px; background: {c['surface']}; color: {c['text']}; }}
        QSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; width: 20px; border: none; }}
        QSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; width: 20px; border: none; }}
        QSpinBox::up-arrow {{ image: url("{up}"); width: 12px; height: 12px; }}
        QSpinBox::down-arrow {{ image: url("{arrow}"); width: 12px; height: 12px; }}
        QComboBox {{ padding-right: 24px; }}
        QComboBox::drop-down, QDateEdit::drop-down {{ width: 22px; border: none; }}
        QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url("{arrow}"); width: 12px; height: 12px; }}
        QComboBox:disabled, QDateEdit:disabled, QSpinBox:disabled {{ color: {c['disabled']}; background: {c['bg']}; }}
        QComboBox QAbstractItemView {{ background: {c['surface']}; color: {c['text']};
            selection-background-color: {c['selected']}; selection-color: {c['selected_text']};
            border: 1px solid {c['border']}; outline: 0; padding: 3px; }}
        QComboBox QAbstractItemView::item {{ min-height: 28px; }}
        QTextEdit, QTextBrowser, QTableView {{ background: {c['surface']}; alternate-background-color: {c['alternate']};
            color: {c['text']}; border: 1px solid {c['border']}; border-radius: 5px;
            selection-background-color: {c['selected']}; selection-color: {c['selected_text']}; }}
        QTableView {{ gridline-color: {c['border']}; }}
        QHeaderView::section {{ background: {c['hover']}; color: {c['text']}; padding: 8px;
            border: none; border-bottom: 1px solid {c['border']}; }}
        QCheckBox {{ spacing: 7px; background: transparent; }}
        QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {c['border']}; border-radius: 3px; background: {c['surface']}; }}
        QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; image: url("{check}"); }}
        QMenu {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 5px; }}
        QMenu::item {{ padding: 9px 24px; border-radius: 4px; }}
        QMenu::item:selected {{ background: {c['selected']}; color: {c['selected_text']}; }}
        QMenu::separator {{ height: 1px; background: {c['border']}; margin: 5px; }}
        QToolTip {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 5px; }}
        QCalendarWidget QWidget {{ background: {c['surface']}; color: {c['text']}; }}
        QCalendarWidget QToolButton {{ padding: 3px 5px; border: none; border-radius: 0; }}
        QCalendarWidget QSpinBox {{ padding: 0; min-height: 0; }}
        QCalendarWidget QAbstractItemView {{ background: {c['surface']}; color: {c['text']};
            selection-background-color: {c['selected']}; selection-color: {c['selected_text']}; }}
        QSplitter::handle {{ background: {c['border']}; height: 3px; }}
        QTabWidget::pane {{ border: 1px solid {c['border']}; }}
        QTabBar::tab {{ background: {c['surface']}; padding: 9px 18px; border: 1px solid {c['border']}; }}
        QTabBar::tab:selected {{ background: {c['selected']}; }}
    """)
    for widget in app.allWidgets():
        if isinstance(widget, QCalendarWidget):
            weekend = QTextCharFormat()
            weekend.setForeground(QColor(c["text"]))
            widget.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, weekend)
            widget.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, weekend)
