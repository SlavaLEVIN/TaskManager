"""Представления собирают ввод и отображают данные, не обращаясь к БД."""

from pathlib import Path

from PySide6.QtCore import QDate, QEvent, Qt, Signal
from PySide6.QtGui import QIcon, QTextCharFormat
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCalendarWidget, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListView, QMenu,
    QMainWindow, QMessageBox, QPushButton, QSpinBox, QSplitter, QStackedWidget,
    QSizePolicy, QTableView, QTextBrowser, QTextEdit, QToolButton, QTabWidget, QVBoxLayout, QWidget,
)

from ..config import DatabaseConfig
from ..preferences import Preferences
from .theme import apply_theme
from ..domain import LABELS, TRANSITIONS, Priority, Role, TaskInput, TaskQuery, TaskStatus
from .table_models import TableModel, TaskTableModel


def button(label, layout, callback=None):
    widget = QPushButton(label)
    widget.setMinimumHeight(34)
    layout.addWidget(widget)
    if callback:
        widget.clicked.connect(callback)
    return widget


class ComboBox(QComboBox):
    def __init__(self):
        super().__init__()
        self.setView(QListView())
        self.setMaxVisibleItems(10)
        self.setMinimumContentsLength(12)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)


def combo(values, all_label=None):
    widget = ComboBox()
    if all_label:
        widget.addItem(all_label, None)
    for value in values:
        widget.addItem(LABELS[value], value)
    return widget


def calendar():
    widget = QDateEdit(QDate.currentDate())
    widget.setCalendarPopup(True)
    popup = QCalendarWidget()
    popup.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
    popup.setMinimumSize(330, 275)
    weekend = QTextCharFormat()
    weekend.setForeground(QApplication.palette().text())
    popup.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, weekend)
    popup.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, weekend)
    widget.setCalendarWidget(popup)
    widget.setDisplayFormat("dd.MM.yyyy")
    widget.setDateRange(QDate(1, 1, 1), QDate(9999, 12, 31))
    return widget


class DataTable(QTableView):
    def fit_headers(self):
        if self.model() is not None:
            for column in range(self.model().columnCount()):
                text = self.model().headerData(column, Qt.Orientation.Horizontal)
                minimum = self.fontMetrics().horizontalAdvance(str(text)) + 32
                if self.columnWidth(column) < minimum:
                    self.setColumnWidth(column, minimum)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self.fit_headers()


def table(model):
    widget = DataTable()
    widget.setModel(model)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setAlternatingRowColors(True)
    widget.verticalHeader().setVisible(False)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    widget.horizontalHeader().setStretchLastSection(True)
    widget.setWordWrap(False)
    widget.verticalHeader().setDefaultSectionSize(34)
    widget.fit_headers()
    return widget


class LoginView(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.addStretch()
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(440)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)
        title = QLabel("Менеджер задач")
        title.setObjectName("headline")
        layout.addWidget(title)
        subtitle = QLabel("Задачи команды в одном месте")
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)
        form = QFormLayout()
        self.login = QLineEdit()
        self.password = QLineEdit()
        self.login.setMaxLength(2147483647)
        self.password.setMaxLength(2147483647)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login.setPlaceholderText("Ваш логин")
        self.password.setPlaceholderText("Ваш пароль")
        form.addRow("Логин", self.login)
        form.addRow("Пароль", self.password)
        layout.addLayout(form)
        self.enter = button("Войти", layout)
        self.enter.setObjectName("primary")
        self.settings = button("Настройки подключения", layout)
        self.preferences = button("Настройки программы", layout)
        self.retry = button("Повторить подключение", layout)
        self.exit = button("Завершить работу", layout)
        note = QLabel("Доступные действия определяются ролью учётной записи.")
        note.setWordWrap(True)
        note.setObjectName("muted")
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
        self.status.addItem("Просрочена", "OVERDUE")
        self.priority = combo(Priority, "Все приоритеты")
        self.category = ComboBox()
        self.category.addItem("Все категории", None)
        self.assignee = ComboBox()
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
        self.sort = ComboBox()
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
        self.new_status = ComboBox()
        self.new_status.setVisible(False)
        self.change = button("Взять в работу", actions)
        self.change.setObjectName("primary")
        self.complete = button("Завершить задачу", actions)
        self.report = button("В отчёт", actions)
        layout.addLayout(actions)
        self.status_hint = QLabel("Выберите одну задачу, чтобы изменить её статус.")
        self.status_hint.setObjectName("muted")
        self.status_hint.setWordWrap(True)
        layout.addWidget(self.status_hint)
        self.admin_widgets = [self.create, self.edit, self.delete, self.assignee]
        self.table.selectionModel().selectionChanged.connect(self.update_details)

    def query(self):
        return TaskQuery(self.search.text(), None if self.status.currentData() == "OVERDUE" else self.status.currentData(), self.priority.currentData(),
                         self.category.currentData(), self.assignee.currentData(),
                         self.date_from.date().toPython() if self.date_enabled.isChecked() else None,
                         self.date_to.date().toPython() if self.date_enabled.isChecked() else None,
                         self.sort.currentData(), self.descending.isChecked(),
                         overdue=self.status.currentData() == "OVERDUE")

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
        self.complete.setEnabled(len(tasks) == 1 and tasks[0].status == TaskStatus.IN_PROGRESS)
        self.edit.setEnabled(len(tasks) == 1)
        self.delete.setEnabled(len(tasks) == 1)
        if len(tasks) == 1:
            task = tasks[0]
            self.details.setPlainText(f"№{task.id} · {task.title}\nОтветственный: {task.assignee} · {task.category}\n\n{task.description or 'Описание не задано.'}")
            for status in TRANSITIONS[task.status]:
                self.new_status.addItem(LABELS[status], status)
            target = TaskStatus.NEW if task.status == TaskStatus.IN_PROGRESS else TaskStatus.IN_PROGRESS
            self.new_status.setCurrentIndex(self.new_status.findData(target))
            self.change.setText("Вернуть в новые" if task.status == TaskStatus.IN_PROGRESS else
                                "Вернуть в работу" if task.status == TaskStatus.COMPLETED else "Взять в работу")
            self.status_hint.setText("Сначала нажмите «Взять в работу», затем «Завершить задачу»." if task.status == TaskStatus.NEW else
                                     "Работа закончена? Нажмите «Завершить задачу»." if task.status == TaskStatus.IN_PROGRESS else
                                     "Задача выполнена. При необходимости её можно вернуть в работу.")
            self.complete.setToolTip("Сначала переведите задачу в работу." if task.status == TaskStatus.NEW else "Отметить задачу выполненной")
        else:
            self.details.clear()
            self.status_hint.setText("Выберите одну задачу, чтобы изменить её статус.")


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
        self.tabs = QTabWidget()
        picker = QWidget()
        pick_layout = QVBoxLayout(picker)
        filters = QHBoxLayout()
        self.status = combo(TaskStatus, "Все статусы")
        self.status.addItem("Просрочена", "OVERDUE")
        filters.addWidget(self.status)
        self.refresh = button("Показать задачи", filters)
        self.select_all = button("Выбрать все", filters)
        self.clear_selection = button("Снять выбор", filters)
        pick_layout.addLayout(filters)
        dates = QHBoxLayout()
        self.date_enabled = QCheckBox("Срок задачи с")
        self.date_from, self.date_to = calendar(), calendar()
        dates.addWidget(self.date_enabled)
        dates.addWidget(self.date_from)
        dates.addWidget(QLabel("по"))
        dates.addWidget(self.date_to)
        self.week = button("Текущая неделя", dates)
        pick_layout.addLayout(dates)
        note = QLabel("В отчёт можно включать новые, выполняемые и выполненные задачи. Период отбирает по сроку задачи, а не по дате завершения.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        pick_layout.addWidget(note)
        self.model = TaskTableModel(self)
        self.table = table(self.model)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 145)
        self.table.setColumnWidth(2, 155)
        pick_layout.addWidget(self.table, 1)
        self.selection = QTextEdit()
        self.selection.setReadOnly(True)
        self.selection.setMaximumHeight(80)
        self.selection.setPlainText("Выберите задачи в таблице: Ctrl — несколько строк, Shift — диапазон.")
        pick_layout.addWidget(self.selection)
        self.generate = button("Сформировать отчёт по выбранным задачам", pick_layout)
        self.generate.setObjectName("primary")
        output = QWidget()
        output_layout = QVBoxLayout(output)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlaceholderText("Выберите задачи на соседней вкладке и сформируйте отчёт.")
        output_layout.addWidget(self.text, 1)
        report_actions = QHBoxLayout()
        self.copy = button("Скопировать отчёт", report_actions)
        self.save = button("Сохранить отчёт в TXT", report_actions)
        output_layout.addLayout(report_actions)
        self.tabs.addTab(picker, "1. Выбор задач")
        self.tabs.addTab(output, "2. Готовый отчёт")
        layout.addWidget(self.tabs, 1)
        actions = QHBoxLayout()
        self.tasks_csv = button("Экспорт списка задач в CSV", actions)
        self.users_csv = button("Экспорт пользователей в CSV", actions)
        layout.addLayout(actions)
        self.note = QLabel("CSV задач использует фильтры раздела «Работа с задачами». Текстовый отчёт — выбранные здесь задачи.")
        self.note.setWordWrap(True)
        self.note.setObjectName("muted")
        layout.addWidget(self.note)
        self.select_all.clicked.connect(self.table.selectAll)
        self.clear_selection.clicked.connect(self.table.clearSelection)
        self.table.selectionModel().selectionChanged.connect(self.update_selection)
        self.update_selection()

    def query(self):
        selected = self.status.currentData()
        return TaskQuery(status=None if selected == "OVERDUE" else selected,
                         overdue=selected == "OVERDUE",
                         date_from=self.date_from.date().toPython() if self.date_enabled.isChecked() else None,
                         date_to=self.date_to.date().toPython() if self.date_enabled.isChecked() else None)

    def selected_ids(self):
        return [self.model.objects[i.row()].id for i in sorted(self.table.selectionModel().selectedRows(), key=lambda i: i.row())]

    def update_selection(self):
        ids = self.selected_ids()
        self.selection.setPlainText(f"Выбрано задач: {len(ids)} из {self.model.rowCount()}. Можно объединить задачи с разными статусами.")
        self.generate.setEnabled(bool(ids))


class EditDialog(QDialog):
    submitted = Signal()

    def __init__(self, title, parent):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(540)
        self.setSizeGripEnabled(True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(16)
        self.form = QFormLayout()
        self.form.setSpacing(12)
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
        self.description.setMinimumHeight(110)
        self.description.setMaximumHeight(180)
        self.assignee, self.category = ComboBox(), ComboBox()
        for user in users:
            self.assignee.addItem(user.login, user.id)
        for category in categories:
            self.category.addItem(category.name, category.id)
        self.category_hint = QLabel()
        self.category_hint.setObjectName("muted")
        self.category_hint.setWordWrap(True)
        descriptions = {"Документация": "Подготовка текстов, инструкций и отчётных документов.",
                        "Обслуживание": "Настройка, проверка и исправление оборудования или программ.",
                        "Организационные": "Встречи, согласования и планирование работы команды.",
                        "Прочее": "Задачи, которые не подходят под остальные категории."}
        self.category.currentTextChanged.connect(lambda name: self.category_hint.setText(descriptions.get(name, "Категория для группировки задач.")))
        self.category_hint.setText(descriptions.get(self.category.currentText(), "Категория для группировки задач."))
        self.priority = combo(Priority)
        self.priority.setCurrentIndex(1)
        self.due_date = calendar()
        chosen_date = task.due_date if task else today
        self.due_date.setDate(QDate(chosen_date.year, chosen_date.month, chosen_date.day))
        self.status = ComboBox()
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
            if widget is self.category:
                self.form.addRow("", self.category_hint)

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
                field = ComboBox()
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


class PreferencesDialog(EditDialog):
    def __init__(self, preferences, parent):
        super().__init__("Настройки программы", parent)
        self.theme = ComboBox()
        self.theme.addItem("Светлая", "light")
        self.theme.addItem("Тёмная", "dark")
        self.theme.setCurrentIndex(self.theme.findData(preferences.theme))
        self.font_size = QSpinBox()
        self.font_size.setRange(12, 16)
        self.font_size.setValue(preferences.font_size)
        self.start_page = ComboBox()
        self.start_page.addItem("Работа с задачами", "tasks")
        self.start_page.addItem("Главное меню", "home")
        self.start_page.setCurrentIndex(self.start_page.findData(preferences.start_page))
        self.confirm_exit = QCheckBox("Спрашивать перед закрытием программы")
        self.confirm_exit.setChecked(preferences.confirm_exit)
        self.form.addRow("Тема", self.theme)
        self.form.addRow("Размер текста", self.font_size)
        self.form.addRow("После входа открывать", self.start_page)
        self.form.addRow(self.confirm_exit)
        note = QLabel("Настройки сохраняются на этом компьютере для текущего пользователя Windows. Тема применяется также к спискам, календарю и диалогам.")
        note.setWordWrap(True)
        self.form.addRow(note)

    def values(self):
        return Preferences(self.theme.currentData(), self.font_size.value(), self.start_page.currentData(), self.confirm_exit.isChecked())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.preferences = Preferences.load()
        apply_theme(self.preferences)
        self.setWindowTitle("Менеджер задач")
        self.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[1] / "resources/app.svg")))
        self.resize(1200, 800)
        self.setMinimumSize(1050, 720)
        self.busy = False
        self.close_pending = False
        self.stack = QStackedWidget()
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(16, 12, 16, 12)
        connection_row = QHBoxLayout()
        self.connection = QLabel("Подключение ещё не проверено")
        self.connection.setObjectName("connection")
        connection_row.addWidget(self.connection)
        self.activity = QLabel()
        self.activity.setObjectName("muted")
        self.activity.setWordWrap(True)
        connection_row.addWidget(self.activity, 1)
        self.retry = QPushButton("Проверить подключение")
        connection_row.addWidget(self.retry)
        central_layout.addLayout(connection_row)
        central_layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.login = LoginView()
        self.stack.addWidget(self.login)
        self.shell = QWidget()
        self.stack.addWidget(self.shell)
        shell_layout = QVBoxLayout(self.shell)
        top = QHBoxLayout()
        self.identity = QLabel()
        self.identity.setObjectName("identity")
        self.identity.setTextFormat(Qt.TextFormat.PlainText)
        self.identity.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        top.addWidget(self.identity, 1)
        self.menu_button = QToolButton()
        self.menu_button.setText("☰  Меню")
        self.menu_button.setAccessibleName("Открыть меню программы")
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        navigation = QMenu(self.menu_button)
        self.home = navigation.addAction("Главное меню")
        self.preferences_action = navigation.addAction("Настройки программы")
        self.help_button = navigation.addAction("Справка")
        navigation.addSeparator()
        self.logout = navigation.addAction("Выйти из учётной записи")
        self.exit = navigation.addAction("Завершить работу")
        self.exit.triggered.connect(self.close)
        self.menu_button.setMenu(navigation)
        top.addWidget(self.menu_button)
        shell_layout.addLayout(top)
        self.pages = QStackedWidget()
        shell_layout.addWidget(self.pages, 1)
        self.menu = QWidget()
        menu_layout = QVBoxLayout(self.menu)
        title = QLabel("Рабочее пространство")
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
        self.retry.hide()
        self.stack.currentChanged.connect(lambda _: self.retry.setVisible(self.stack.currentWidget() is self.shell))
        self.login.exit.clicked.connect(self.close)
        self.home.triggered.connect(lambda: self.pages.setCurrentWidget(self.menu))
        self.previous_page = self.menu
        self.help_button.triggered.connect(self.show_help)
        self.help_back.clicked.connect(lambda: self.pages.setCurrentWidget(self.previous_page))
        help_path = Path(__file__).resolve().parents[1] / "resources/help.html"
        self.help_text.setHtml(help_path.read_text(encoding="utf-8"))


    def set_activity(self, text):
        self.activity.setText(text)

    def set_connection(self, state, message):
        self.connection.setText(message)
        self.connection.setProperty("state", state)
        self.connection.style().unpolish(self.connection)
        self.connection.style().polish(self.connection)

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
        self.reports.model.clear()
        self.reports.status.setCurrentIndex(0)
        self.reports.date_enabled.setChecked(False)
        self.reports.tabs.setCurrentIndex(0)
        self.reports.selection.setPlainText("Выберите задачи в разделе «Работа с задачами» и нажмите «В отчёт».")
        self.tasks.assignee.clear()
        self.tasks.assignee.addItem("Все исполнители", None)
        self.tasks.reset_filters()

    def closeEvent(self, event):
        if self.close_pending and not self.busy:
            event.accept()
            return
        if not self.preferences.confirm_exit and not self.busy:
            event.accept()
            return
        prompt = QMessageBox(self)
        prompt.setWindowTitle("Завершение работы")
        prompt.setIcon(QMessageBox.Icon.Question)
        prompt.setText("Завершить работу приложения?")
        leave = prompt.addButton("Выйти", QMessageBox.ButtonRole.AcceptRole)
        cancel = prompt.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        prompt.setDefaultButton(cancel)
        prompt.exec()
        if prompt.clickedButton() != leave:
            event.ignore()
        elif self.busy:
            self.close_pending = True
            self.set_activity("Завершение текущей операции перед выходом…")
            event.ignore()
        else:
            event.accept()
