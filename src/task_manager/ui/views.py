"""Представления собирают ввод и отображают данные, не обращаясь к БД."""

from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFormLayout, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QSpinBox, QSplitter, QStackedWidget,
    QSizePolicy, QTableView, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from ..config import DatabaseConfig
from ..domain import LABELS, TRANSITIONS, Priority, Role, TaskInput, TaskQuery, TaskStatus
from .table_models import TableModel, TaskTableModel


def button(label, layout, callback=None):
    widget = QPushButton(label)
    widget.setMinimumHeight(34)
    layout.addWidget(widget)
    if callback:
        widget.clicked.connect(callback)
    return widget


def combo(values, all_label=None):
    widget = QComboBox()
    if all_label:
        widget.addItem(all_label, None)
    for value in values:
        widget.addItem(LABELS[value], value)
    return widget


def calendar():
    widget = QDateEdit(QDate.currentDate())
    widget.setCalendarPopup(True)
    widget.setDisplayFormat("dd.MM.yyyy")
    widget.setDateRange(QDate(1, 1, 1), QDate(9999, 12, 31))
    return widget


def table(model):
    widget = QTableView()
    widget.setModel(model)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setAlternatingRowColors(True)
    widget.verticalHeader().setVisible(False)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    widget.horizontalHeader().setStretchLastSection(True)
    widget.setWordWrap(False)
    return widget


class LoginView(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.addStretch()
        card = QWidget()
        card.setMaximumWidth(460)
        layout = QVBoxLayout(card)
        title = QLabel("Менеджер задач")
        title.setObjectName("headline")
        layout.addWidget(title)
        subtitle = QLabel("Войдите в учётную запись организации")
        layout.addWidget(subtitle)
        form = QFormLayout()
        self.login = QLineEdit()
        self.password = QLineEdit()
        self.login.setMaxLength(2147483647)
        self.password.setMaxLength(2147483647)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Логин", self.login)
        form.addRow("Пароль", self.password)
        layout.addLayout(form)
        self.enter = button("Войти", layout)
        self.enter.setObjectName("primary")
        self.settings = button("Настройки подключения", layout)
        self.retry = button("Повторить подключение", layout)
        self.exit = button("Завершить работу", layout)
        note = QLabel("Доступные действия определяются ролью учётной записи.")
        note.setWordWrap(True)
        layout.addWidget(note)
        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch()


class TasksView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel("Работа с задачами")
        heading.setObjectName("headline")
        layout.addWidget(heading)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setMaxLength(2147483647)
        self.search.setPlaceholderText("Найти в названии или описании…")
        search_row.addWidget(self.search, 1)
        self.apply = button("Применить", search_row)
        self.reset = button("Сбросить", search_row)
        self.refresh = button("Обновить", search_row)
        layout.addLayout(search_row)
        filters = QGridLayout()
        self.status = combo(TaskStatus, "Все статусы")
        self.priority = combo(Priority, "Все приоритеты")
        self.category = QComboBox()
        self.category.addItem("Все категории", None)
        self.assignee = QComboBox()
        self.assignee.addItem("Все исполнители", None)
        for column, widget in enumerate((self.status, self.priority, self.category, self.assignee)):
            filters.addWidget(widget, 0, column)
        self.date_enabled = QCheckBox("Срок от / до")
        self.date_from, self.date_to = calendar(), calendar()
        dates = QHBoxLayout()
        dates.addWidget(self.date_enabled)
        dates.addWidget(self.date_from)
        dates.addWidget(QLabel("—"))
        dates.addWidget(self.date_to)
        filters.addLayout(dates, 1, 0, 1, 2)
        self.sort = QComboBox()
        for label, key in (("По сроку", "due_date"), ("По названию", "title"), ("По приоритету", "priority"),
                           ("По статусу", "status"), ("По категории", "category")):
            self.sort.addItem(label, key)
        self.descending = QCheckBox("По убыванию")
        filters.addWidget(self.sort, 1, 2)
        filters.addWidget(self.descending, 1, 3)
        layout.addLayout(filters)
        self.active_filters = QLabel("Условия: все доступные задачи")
        self.active_filters.setTextFormat(Qt.TextFormat.PlainText)
        self.active_filters.setWordWrap(True)
        layout.addWidget(self.active_filters)
        self.model = TaskTableModel(self)
        self.table = table(self.model)
        self.table.setColumnWidth(0, 300)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(2, 145)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Выберите задачу для просмотра описания. Для отчёта можно выбрать несколько строк (Ctrl / Shift).")
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.table)
        split.addWidget(self.details)
        split.setSizes([430, 130])
        layout.addWidget(split, 1)
        self.count = QLabel()
        layout.addWidget(self.count)
        actions = QHBoxLayout()
        self.create = button("Создать", actions)
        self.edit = button("Редактировать", actions)
        self.delete = button("Удалить", actions)
        actions.addStretch()
        self.new_status = QComboBox()
        actions.addWidget(self.new_status)
        self.change = button("Изменить статус", actions)
        self.report = button("В отчёт", actions)
        layout.addLayout(actions)
        self.admin_widgets = [self.create, self.edit, self.delete, self.assignee]
        self.table.selectionModel().selectionChanged.connect(self.update_details)

    def query(self):
        return TaskQuery(self.search.text(), self.status.currentData(), self.priority.currentData(),
                         self.category.currentData(), self.assignee.currentData(),
                         self.date_from.date().toPython() if self.date_enabled.isChecked() else None,
                         self.date_to.date().toPython() if self.date_enabled.isChecked() else None,
                         self.sort.currentData(), self.descending.isChecked())

    def reset_filters(self):
        self.search.clear()
        for widget in (self.status, self.priority, self.category, self.assignee, self.sort):
            widget.setCurrentIndex(0)
        self.date_enabled.setChecked(False)
        self.descending.setChecked(False)

    def selected(self):
        return [self.model.objects[index.row()] for index in sorted(self.table.selectionModel().selectedRows(), key=lambda i: i.row())]

    def update_details(self):
        tasks = self.selected()
        self.new_status.clear()
        self.change.setEnabled(len(tasks) == 1)
        self.edit.setEnabled(len(tasks) == 1)
        self.delete.setEnabled(len(tasks) == 1)
        if len(tasks) == 1:
            task = tasks[0]
            self.details.setPlainText(f"№{task.id} · {task.title}\nОтветственный: {task.assignee} · {task.category}\n\n{task.description or 'Описание не задано.'}")
            for status in TRANSITIONS[task.status]:
                self.new_status.addItem(LABELS[status], status)
        else:
            self.details.clear()


class UsersView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel("Управление пользователями")
        heading.setObjectName("headline")
        layout.addWidget(heading)
        self.model = TableModel(["ID", "Логин", "Роль"], self)
        self.table = table(self.model)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setColumnWidth(1, 350)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.create = button("Добавить", actions)
        self.edit = button("Редактировать", actions)
        self.delete = button("Удалить", actions)
        self.password = button("Сбросить пароль", actions)
        self.tasks = button("Задачи пользователя", actions)
        self.refresh = button("Обновить", actions)
        layout.addLayout(actions)

    def selected(self):
        rows = self.table.selectionModel().selectedRows()
        return self.model.objects[rows[0].row()] if rows else None


class ReportsView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Отчёты и экспорт")
        title.setObjectName("headline")
        layout.addWidget(title)
        self.selection = QTextEdit()
        self.selection.setReadOnly(True)
        self.selection.setMinimumHeight(70)
        self.selection.setMaximumHeight(100)
        self.selection.setPlainText("Выберите задачи в разделе «Работа с задачами» и нажмите «В отчёт».")
        layout.addWidget(self.selection)
        self.generate = button("Сформировать / обновить отчёт", layout)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text, 1)
        actions = QHBoxLayout()
        self.tasks_csv = button("Экспорт списка задач в CSV", actions)
        self.users_csv = button("Экспорт пользователей в CSV", actions)
        layout.addLayout(actions)
        self.note = QLabel("CSV задач учитывает условия последнего загруженного списка; CSV пользователей содержит все учётные записи.")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)


class EditDialog(QDialog):
    submitted = Signal()

    def __init__(self, title, parent):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        self.layout = QVBoxLayout(self)
        self.form = QFormLayout()
        self.layout.addLayout(self.form)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        self.buttons.accepted.connect(self.submitted)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
        self.busy = False

    def reject(self):
        if not self.busy:
            super().reject()

    def set_busy(self, busy):
        self.busy = busy
        self.buttons.setEnabled(not busy)
        for index in range(self.form.count()):
            widget = self.form.itemAt(index).widget()
            if widget:
                widget.setEnabled(not busy)


class TaskDialog(EditDialog):
    def __init__(self, users, categories, today, parent, task=None):
        super().__init__("Редактирование задачи" if task else "Новая задача", parent)
        self.title = QLineEdit(task.title if task else "")
        self.title.setMaxLength(2147483647)
        self.description = QTextEdit()
        self.description.setPlainText(task.description if task else "")
        self.description.setMinimumHeight(140)
        self.assignee, self.category = QComboBox(), QComboBox()
        for user in users:
            self.assignee.addItem(user.login, user.id)
        for category in categories:
            self.category.addItem(category.name, category.id)
        self.priority = combo(Priority)
        self.priority.setCurrentIndex(1)
        self.due_date = calendar()
        chosen_date = task.due_date if task else today
        self.due_date.setDate(QDate(chosen_date.year, chosen_date.month, chosen_date.day))
        self.status = QComboBox()
        statuses = (task.status, *TRANSITIONS[task.status]) if task else (TaskStatus.NEW,)
        for status in statuses:
            self.status.addItem(LABELS[status], status)
        self.status.setEnabled(task is not None)
        if task:
            self.assignee.setCurrentIndex(self.assignee.findData(task.assignee_id))
            self.category.setCurrentIndex(self.category.findData(task.category_id))
            self.priority.setCurrentIndex(self.priority.findData(task.priority))
        for label, widget in (("Название", self.title), ("Описание", self.description), ("Ответственный", self.assignee),
                              ("Категория", self.category), ("Приоритет", self.priority), ("Срок", self.due_date), ("Статус", self.status)):
            self.form.addRow(label, widget)

    def values(self):
        return TaskInput(self.title.text(), self.description.toPlainText(), self.assignee.currentData(),
                         self.category.currentData(), self.due_date.date().toPython(), self.priority.currentData())


class UserDialog(EditDialog):
    def __init__(self, parent, user=None, password_only=False):
        super().__init__("Сброс пароля" if password_only else "Редактирование пользователя" if user else "Новый пользователь", parent)
        self.login = QLineEdit(user.login if user else "")
        self.login.setMaxLength(2147483647)
        self.role = combo(Role)
        if user:
            self.role.setCurrentIndex(self.role.findData(user.role))
        self.password = QLineEdit()
        self.password.setMaxLength(2147483647)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        if not password_only:
            self.form.addRow("Логин", self.login)
            self.form.addRow("Роль", self.role)
        if user is None or password_only:
            self.form.addRow("Новый пароль", self.password)
        if password_only:
            self.form.insertRow(0, "Пользователь", QLabel(user.login))


class SettingsDialog(EditDialog):
    def __init__(self, config: DatabaseConfig, parent):
        super().__init__("Настройки подключения", parent)
        self.fields = {}
        labels = {"host": "Адрес сервера", "port": "Порт", "dbname": "Имя БД", "user": "Технический пользователь PostgreSQL",
                  "password": "Пароль PostgreSQL", "connect_timeout": "Тайм-аут подключения, с",
                  "statement_timeout": "Тайм-аут запроса, мс", "sslmode": "Режим SSL"}
        for key, value in vars(config).items():
            if key in {"port", "connect_timeout", "statement_timeout"}:
                field = QSpinBox()
                field.setRange(1, 65535)
                field.setValue(value)
            elif key == "sslmode":
                field = QComboBox()
                field.addItems(["disable", "prefer", "require", "verify-ca", "verify-full"])
                field.setCurrentText(value)
            else:
                field = QLineEdit(value)
                field.setMaxLength(2147483647)
                if key == "password":
                    field.setEchoMode(QLineEdit.EchoMode.Password)
            self.fields[key] = field
            self.form.addRow(labels[key], field)
        notice = QLabel("Эти данные настраивают доступ к серверу. Учётная запись приложения вводится в окне входа.")
        notice.setWordWrap(True)
        self.form.addRow(notice)

    def values(self):
        values = {}
        for key, widget in self.fields.items():
            values[key] = widget.value() if isinstance(widget, QSpinBox) else widget.currentText() if isinstance(widget, QComboBox) else widget.text()
        return DatabaseConfig(**values)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Менеджер задач")
        self.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[1] / "resources/app.svg")))
        self.resize(1200, 800)
        self.setMinimumSize(1000, 650)
        self.busy = False
        self.close_pending = False
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.login = LoginView()
        self.stack.addWidget(self.login)
        self.shell = QWidget()
        self.stack.addWidget(self.shell)
        shell_layout = QVBoxLayout(self.shell)
        top = QHBoxLayout()
        self.identity = QLabel()
        self.identity.setTextFormat(Qt.TextFormat.PlainText)
        self.identity.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        top.addWidget(self.identity, 1)
        self.home = button("Главное меню", top)
        self.help_button = button("Справка", top)
        self.logout = button("Выйти из учётной записи", top)
        self.exit = button("Завершить работу", top, self.close)
        shell_layout.addLayout(top)
        self.pages = QStackedWidget()
        shell_layout.addWidget(self.pages, 1)
        self.menu = QWidget()
        menu_layout = QVBoxLayout(self.menu)
        title = QLabel("Главное меню")
        title.setObjectName("headline")
        menu_layout.addWidget(title)
        self.tasks_button = button("Работа с задачами", menu_layout)
        self.users_button = button("Управление пользователями", menu_layout)
        self.reports_button = button("Отчёты и экспорт", menu_layout)
        menu_layout.addStretch()
        self.tasks, self.users, self.reports = TasksView(), UsersView(), ReportsView()
        self.help_page = QWidget()
        help_layout = QVBoxLayout(self.help_page)
        self.help_text = QTextBrowser()
        self.help_text.setOpenExternalLinks(False)
        help_layout.addWidget(self.help_text)
        self.help_back = button("Назад", help_layout)
        for page in (self.menu, self.tasks, self.users, self.reports, self.help_page):
            self.pages.addWidget(page)
        self.retry = QPushButton("Повторить подключение")
        self.statusBar().addPermanentWidget(self.retry)
        self.statusBar().showMessage("Войдите в учётную запись")
        self.login.exit.clicked.connect(self.close)
        self.home.clicked.connect(lambda: self.pages.setCurrentWidget(self.menu))
        self.previous_page = self.menu
        self.help_button.clicked.connect(self.show_help)
        self.help_back.clicked.connect(lambda: self.pages.setCurrentWidget(self.previous_page))
        help_path = Path(__file__).resolve().parents[1] / "resources/help.html"
        self.help_text.setHtml(help_path.read_text(encoding="utf-8"))
        self.setStyleSheet("""
            QMainWindow, QWidget { font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QMainWindow { background: #f5f7fb; }
            QLabel#headline { font-size: 25px; font-weight: 600; color: #183153; margin: 10px 0; }
            QPushButton { padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 5px; background: #ffffff; color: #183153; }
            QPushButton:hover { background: #e9eff9; }
            QPushButton:disabled { color: #8792a4; background: #eef1f5; }
            QPushButton#primary { background: #2459bd; color: white; border: none; }
            QLineEdit, QComboBox, QDateEdit, QSpinBox { padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; background: white; color: #213247; }
            QTextEdit, QTextBrowser, QTableView { background: white; alternate-background-color: #f2f5fa; color: #213247; border: 1px solid #d7deea; selection-background-color: #d6e6ff; selection-color: #142c50; }
            QHeaderView::section { background: #e9eef6; color: #334967; padding: 8px; border: none; border-bottom: 1px solid #cbd5e1; }
        """)

    def show_help(self):
        if self.pages.currentWidget() != self.help_page:
            self.previous_page = self.pages.currentWidget()
        self.pages.setCurrentWidget(self.help_page)

    def set_role(self, user):
        self.identity.setText(f"{user.login} · {LABELS[user.role]}")
        self.identity.setToolTip(f"{user.login} · {LABELS[user.role]}")
        for widget in (*self.tasks.admin_widgets, self.users_button, self.reports.tasks_csv, self.reports.users_csv, self.reports.note):
            widget.setVisible(user.is_admin())

    def clear_private(self):
        self.tasks.model.clear()
        self.tasks.details.clear()
        self.tasks.count.clear()
        self.users.model.clear()
        self.reports.text.clear()
        self.reports.selection.setPlainText("Выберите задачи в разделе «Работа с задачами» и нажмите «В отчёт».")
        self.tasks.assignee.clear()
        self.tasks.assignee.addItem("Все исполнители", None)
        self.tasks.reset_filters()

    def closeEvent(self, event):
        if self.close_pending and not self.busy:
            event.accept()
            return
        prompt = QMessageBox(self)
        prompt.setWindowTitle("Подтверждение выхода")
        prompt.setText("Завершить работу приложения?")
        leave = prompt.addButton("Выйти", QMessageBox.ButtonRole.AcceptRole)
        cancel = prompt.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        prompt.setDefaultButton(cancel)
        prompt.exec()
        if prompt.clickedButton() != leave:
            event.ignore()
        elif self.busy:
            self.close_pending = True
            self.statusBar().showMessage("Завершение текущей операции перед выходом…")
            event.ignore()
        else:
            event.accept()
