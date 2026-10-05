"""Связь представлений, сессии и сервисов; все запросы выполняются вне GUI-потока."""

from PySide6.QtCore import QDate, QObject, QThreadPool, QTimer, Qt, Slot
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from datetime import datetime

from ..config import DatabaseConfig
from ..database import Database
from ..domain import AccessError, AppError, DatabaseError, SessionExpired, TaskQuery, TaskStatus
from ..services import AuthService, ReportService, TaskService, UserService
from .views import CategoryDialog, PreferencesDialog, SettingsDialog, TaskDialog, UserDialog
from .theme import apply_theme
from .workers import Worker


class Presenter(QObject):
    def __init__(self, window, database: Database):
        super().__init__(window)
        self.window = window
        self.session = None
        self.user = None
        self.report_ids = []
        self.last_query = TaskQuery()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.worker = None
        self.dialog = None
        self.callback = None
        self.connection_check = False
        self.session_timer = QTimer(self)
        self.session_timer.setInterval(10000)
        self.session_timer.timeout.connect(self.check_session)
        self.quiet_run = False
        self._services(database)
        self._connect()

    def _services(self, database):
        self.database = database
        self.users = UserService(database)
        self.tasks = TaskService(database)
        self.auth = AuthService(self.users)
        self.reports = ReportService(self.tasks, self.users)

    def _connect(self):
        w = self.window
        w.login.enter.clicked.connect(self.login)
        w.login.password.returnPressed.connect(self.login)
        w.login.login.returnPressed.connect(self.login)
        w.login.settings.clicked.connect(self.settings)
        w.login.preferences.clicked.connect(self.preferences)
        w.preferences_action.triggered.connect(self.preferences)
        w.login.retry.clicked.connect(self.reconnect)
        w.retry.triggered.connect(self.reconnect)
        w.logout.triggered.connect(self.logout)
        w.tasks_button.clicked.connect(self.load_tasks)
        w.users_button.clicked.connect(self.load_users)
        w.reports_button.clicked.connect(self.open_reports)
        for btn in (w.tasks.apply, w.tasks.refresh):
            btn.clicked.connect(self.load_tasks)
        w.tasks.search.returnPressed.connect(self.load_tasks)
        w.tasks.reset.clicked.connect(self.reset_tasks)
        w.tasks.create.clicked.connect(lambda: self.edit_task(False))
        w.tasks.edit.clicked.connect(lambda: self.edit_task(True))
        w.tasks.delete.clicked.connect(self.delete_task)
        w.tasks.change.clicked.connect(self.change_status)
        w.tasks.complete.clicked.connect(lambda: self.change_status(target=TaskStatus.COMPLETED))
        w.tasks.report.clicked.connect(self.select_report)
        w.users.create.clicked.connect(lambda: self.edit_user("create"))
        w.users.edit.clicked.connect(lambda: self.edit_user("edit"))
        w.users.password.clicked.connect(lambda: self.edit_user("password"))
        w.users.delete.clicked.connect(self.delete_user)
        w.users.tasks.clicked.connect(self.user_tasks)
        w.users.refresh.clicked.connect(self.load_users)
        w.reports.generate.clicked.connect(self.generate_report)
        w.reports.refresh.clicked.connect(self.open_reports)
        w.reports.week.clicked.connect(self.report_week)
        w.reports.copy.clicked.connect(self.copy_report)
        w.categories_action.triggered.connect(self.load_categories)
        w.categories.refresh.clicked.connect(self.load_categories)
        w.categories.create.clicked.connect(lambda: self.edit_category(False))
        w.categories.rename.clicked.connect(lambda: self.edit_category(True))
        w.reports.tasks_csv.clicked.connect(lambda: self.export_csv("tasks"))
        w.reports.users_csv.clicked.connect(lambda: self.export_csv("users"))

    def error(self, error):
        if self.connection_check:
            self.connection_check = False
            self.window.set_connection("error", "Проверка подключения не пройдена")
        if isinstance(error, DatabaseError):
            self.window.set_connection("error", "Ошибка подключения")
        self.window.activity.setText(str(error))
        self.window.set_connection("error", str(error))
        QMessageBox.warning(self.dialog if self.dialog and self.dialog.isVisible() else self.window, "Менеджер задач", str(error))

    def run(self, operation, callback, *, protected=True, quiet=False):
        if self.window.busy:
            return
        session = self.session
        users = self.users

        def wrapped():
            before = users.get_current(session) if protected else None
            error, result = None, None
            try:
                result = operation()
            except AppError as exc:
                error = exc
            after = users.get_current(session) if protected else None
            return before, after, result, error

        self.window.busy = True
        self.quiet_run = quiet
        if not quiet:
            self.window.setCursor(Qt.CursorShape.WaitCursor)
            self.window.retry.setEnabled(False)
        if self.dialog:
            self.dialog.set_busy(True)
        if not quiet:
            self.window.set_activity("Выполняется операция…")
        self.callback = callback
        self.worker = Worker(wrapped)
        self.worker.signals.done.connect(self.finished)
        self.pool.start(self.worker)

    @Slot(object, object)
    def finished(self, payload, failure):
        self.window.busy = False
        was_quiet = self.quiet_run
        if not was_quiet:
            self.window.unsetCursor()
            self.window.retry.setEnabled(True)
        if self.dialog:
            self.dialog.set_busy(False)
        if not was_quiet:
            self.window.set_activity("Готово")
        self.quiet_run = False
        callback, self.callback = self.callback, None
        self.worker = None
        if self.window.close_pending:
            self.window.close()
            return
        if failure is not None:
            if was_quiet and isinstance(failure, DatabaseError):
                return
            if isinstance(failure, SessionExpired):
                if self.dialog:
                    self.dialog.reject()
                self.logout()
            self.error(failure)
            return
        before, after, result, error = payload
        changed = after is not None and (self.user is None or after.role != self.user.role)
        changed_during = before is not None and after.role != before.role
        if after:
            self.user = after
            self.window.set_role(after)
        if changed or changed_during:
            self.window.clear_private()
            self.report_ids.clear()
            self.last_query = TaskQuery()
            self.window.pages.setCurrentWidget(self.window.menu)
            if self.dialog:
                self.dialog.reject()
            self.window.set_activity("Права изменены. Данные очищены; откройте нужный раздел заново.")
            if error:
                self.error(error)
            return
        if error:
            if was_quiet and isinstance(error, DatabaseError):
                return
            if isinstance(error, SessionExpired):
                if self.dialog:
                    self.dialog.reject()
                self.logout()
                self.error(error)
                return
            if isinstance(error, AccessError):
                self.window.clear_private()
                self.report_ids.clear()
            self.error(error)
        else:
            callback(result)

    def login(self):
        login, password = self.window.login.login.text(), self.window.login.password.text()
        self.run(lambda: self.auth.authenticate(login, password), self.logged_in, protected=False)

    def logged_in(self, result):
        self.session, self.user = result
        self.window.login.password.clear()
        self.window.set_role(self.user)
        self.window.pages.setCurrentWidget(self.window.menu)
        self.window.stack.setCurrentWidget(self.window.shell)
        self.window.set_connection("ok", "Подключено к базе")
        self.session_timer.start()
        if self.window.preferences.start_page == "tasks":
            self.load_tasks()
        self.window.set_activity("Вход выполнен")

    def logout(self):
        if self.window.busy:
            return
        self.session_timer.stop()
        self.session, self.user = None, None
        self.report_ids.clear()
        self.last_query = TaskQuery()
        self.window.clear_private()
        self.window.identity.clear()
        self.window.identity.setToolTip("")
        self.window.login.password.clear()
        self.window.login.login.clear()
        self.window.stack.setCurrentWidget(self.window.login)
        self.window.login.login.setFocus()
        self.window.set_activity("Войдите в учётную запись")

    def check_session(self):
        if not self.session or self.window.busy:
            return
        session = self.session
        self.run(lambda: self.users.get_current(session), self.session_checked, protected=False, quiet=True)

    def session_checked(self, user):
        if self.user and user.role != self.user.role:
            self.window.clear_private()
            self.report_ids.clear()
            self.last_query = TaskQuery()
            self.window.pages.setCurrentWidget(self.window.menu)
            self.window.set_activity("Права изменены. Откройте нужный раздел заново.")
        self.user = user
        self.window.set_role(user)

    def preferences(self):
        if self.window.busy or self.dialog:
            return
        dialog = PreferencesDialog(self.window.preferences, self.window)

        def save():
            try:
                values = dialog.values()
                values.save()
                self.window.preferences = values
                apply_theme(values)
                self.window.refresh_menu_icon()
                self.window.tasks.table.viewport().update()
                self.window.reports.table.viewport().update()
                dialog.accept()
                self.window.set_activity("Настройки программы сохранены")
            except AppError as error:
                self.error(error)

        self.show_dialog(dialog, save)

    def settings(self):
        dialog = SettingsDialog(self.database.config, self.window)

        def save():
            try:
                config = dialog.values()
                config.save()
                self._services(Database(config))
                dialog.accept()
                self.window.set_activity("Настройки сохранены. Нажмите «Повторить подключение».")
            except AppError as error:
                self.error(error)

        self.show_dialog(dialog, save)

    def reconnect(self):
        if self.window.busy:
            return
        self.connection_check = True
        self.window.set_connection("checking", "Проверка подключения…")

        def success(_):
            self.connection_check = False
            self.window.set_connection("ok", f"Соединение исправно · {datetime.now():%H:%M}")
            self.window.activity.setText("Проверка завершена: сервер и таблицы доступны.")

        self.run(self.database.ping, success, protected=self.session is not None)

    @staticmethod
    def fill_options(widget, values, first_label, name):
        selected = widget.currentData()
        widget.clear()
        widget.addItem(first_label, None)
        for value in values:
            widget.addItem(getattr(value, name), value.id)
        index = widget.findData(selected)
        widget.setCurrentIndex(index if index >= 0 else 0)

    def load_tasks(self):
        selected_ids = {task.id for task in self.window.tasks.selected()}
        session, query = self.session, self.window.tasks.query()
        try:
            query.validate()
        except AppError as error:
            self.error(error)
            return

        def operation():
            result = self.tasks.get_tasks(session, query)
            categories = self.tasks.get_categories(session)
            users = self.users.get_users(session) if result.user.is_admin() else []
            return result, categories, users

        def success(data):
            result, categories, users = data
            self.last_query = query
            self.window.tasks.model.set_tasks(result)
            from PySide6.QtCore import QItemSelectionModel
            for row, task in enumerate(result.tasks):
                if task.id in selected_ids:
                    self.window.tasks.table.selectionModel().select(self.window.tasks.model.index(row, 0),
                        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
            self.fill_options(self.window.tasks.category, categories, "Все категории", "name")
            self.fill_options(self.window.tasks.assignee, users, "Все исполнители", "login")
            conditions = []
            if query.text:
                conditions.append(f"поиск: {query.text}")
            for widget in (self.window.tasks.status, self.window.tasks.priority, self.window.tasks.category, self.window.tasks.assignee):
                if widget.currentData() is not None:
                    conditions.append(widget.currentText())
            if query.date_from:
                conditions.append(f"дедлайн: {query.date_from:%d.%m.%Y} — {query.date_to:%d.%m.%Y}")
            self.window.tasks.active_filters.setText("Условия: " + ("; ".join(conditions) if conditions else "все доступные задачи"))
            self.window.tasks.count.setText(f"Найдено задач: {len(result.tasks)} · Сегодня: {result.today:%d.%m.%Y}" if result.tasks else "По заданным условиям доступных задач нет.")
            self.window.pages.setCurrentWidget(self.window.tasks)
            self.window.tasks.update_details()

        self.run(operation, success)

    def reset_tasks(self):
        self.window.tasks.reset_filters()
        self.load_tasks()

    def load_users(self):
        session = self.session

        def success(users):
            from ..domain import LABELS
            self.window.users.model.replace([[u.id, u.login, LABELS[u.role]] for u in users], users)
            self.window.pages.setCurrentWidget(self.window.users)

        self.run(lambda: self.users.get_users(session), success)

    def load_categories(self):
        session = self.session
        def ready(categories):
            self.window.categories.model.replace([[c.name] for c in categories], categories)
            self.window.pages.setCurrentWidget(self.window.categories)
        self.run(lambda: self.tasks.get_categories(session), ready)

    def edit_category(self, editing):
        category = self.window.categories.selected() if editing else None
        if editing and category is None:
            self.error(AppError("Выберите категорию для переименования."))
            return
        session = self.session
        dialog = CategoryDialog(self.window, category)
        def save():
            name = dialog.name.text()
            self.run(lambda: self.tasks.save_category(session, name, category.id if category else None),
                     lambda _: self.saved_dialog(dialog, self.load_categories))
        self.show_dialog(dialog, save)

    def one_task(self):
        tasks = self.window.tasks.selected()
        if len(tasks) != 1:
            self.error(AppError("Выберите ровно одну задачу."))
            return None
        return tasks[0]

    def one_user(self):
        user = self.window.users.selected()
        if user is None:
            self.error(AppError("Выберите пользователя."))
        return user

    def show_dialog(self, dialog, save):
        self.dialog = dialog
        dialog.submitted.connect(save)
        dialog.finished.connect(lambda _: self.dialog_closed(dialog))
        dialog.open()

    def dialog_closed(self, dialog):
        if self.dialog is dialog:
            self.dialog = None
        dialog.deleteLater()

    def edit_task(self, editing):
        selected = self.one_task() if editing else None
        if editing and selected is None:
            return
        session = self.session

        def operation():
            users = self.users.get_users(session)
            categories = self.tasks.get_categories(session)
            result = self.tasks.get_selected(session, [selected.id]) if selected else self.tasks.get_tasks(session)
            return users, categories, result

        def ready(data):
            users, categories, result = data
            task = result.tasks[0] if selected else None
            dialog = TaskDialog(users, categories, result.today, self.window, task)

            def save():
                values, status = dialog.values(), dialog.status.currentData()
                operation = (lambda: self.tasks.update_task(session, task.id, values, status)) if task else (lambda: self.tasks.create_task(session, values))
                self.run(operation, lambda _: self.saved_dialog(dialog, self.load_tasks))

            self.show_dialog(dialog, save)

        self.run(operation, ready)

    def saved_dialog(self, dialog, refresh):
        dialog.accept()
        refresh()

    def confirm(self, title, text):
        prompt = QMessageBox(self.window)
        prompt.setWindowTitle(title)
        prompt.setTextFormat(Qt.TextFormat.PlainText)
        prompt.setText(text)
        delete = prompt.addButton("Удалить", QMessageBox.ButtonRole.DestructiveRole)
        cancel = prompt.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        prompt.setDefaultButton(cancel)
        prompt.exec()
        return prompt.clickedButton() == delete

    def delete_task(self):
        task = self.one_task()
        if task and self.confirm("Удаление задачи", f"Удалить задачу №{task.id} «{task.title}»?"):
            session = self.session
            self.run(lambda: self.tasks.delete_task(session, task.id), lambda _: self.load_tasks())

    def change_status(self, checked=False, target=None):
        task = self.one_task()
        status, session = target or self.window.tasks.new_status.currentData(), self.session
        if task and status:
            self.run(lambda: self.tasks.change_status(session, task.id, status), lambda _: self.load_tasks())

    def edit_user(self, action):
        user = None if action == "create" else self.one_user()
        if action != "create" and user is None:
            return
        session = self.session
        dialog = UserDialog(self.window, user, action == "password")

        def save():
            login, role, password = dialog.login.text(), dialog.role.currentData(), dialog.password.text()
            if action == "create":
                operation = lambda: self.users.create_user(session, login, password, role)
            elif action == "password":
                operation = lambda: self.users.reset_password(session, user.id, password)
            else:
                operation = lambda: self.users.update_user(session, user.id, login, role)
            self.run(operation, lambda _: self.saved_dialog(dialog, self.load_users))

        self.show_dialog(dialog, save)

    def delete_user(self):
        user = self.one_user()
        if user and self.confirm("Удаление пользователя", f"Удалить учётную запись «{user.login}»?"):
            session = self.session
            self.run(lambda: self.users.delete_user(session, user.id), lambda _: self.load_users())

    def user_tasks(self):
        user = self.one_user()
        if user is None:
            return
        session = self.session

        def ready(users):
            self.window.tasks.reset_filters()
            self.fill_options(self.window.tasks.assignee, users, "Все исполнители", "login")
            self.window.tasks.assignee.setCurrentIndex(self.window.tasks.assignee.findData(user.id))
            self.load_tasks()

        self.run(lambda: self.users.get_users(session), ready)

    def open_reports(self, checked=False, selected_ids=None, generate=False):
        view = self.window.reports
        session = self.session
        ids = set(view.selected_ids() if selected_ids is None else selected_ids)
        query = view.query()
        try:
            query.validate()
        except AppError as error:
            self.error(error)
            return

        def ready(result):
            from PySide6.QtCore import QItemSelectionModel
            view.model.set_tasks(result)
            for row, task in enumerate(result.tasks):
                if task.id in ids:
                    view.table.selectionModel().select(view.model.index(row, 0),
                        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
            period = f"Дедлайн: {query.date_from:%d.%m.%Y} — {query.date_to:%d.%m.%Y}, обе даты включены" if query.date_from else "Период не ограничен"
            view.active_filters.setText(f"{period} · Найдено задач: {len(result.tasks)}")
            view.update_selection()
            view.tabs.setCurrentIndex(0)
            self.window.pages.setCurrentWidget(view)
            if generate:
                self.generate_report()

        self.run(lambda: self.tasks.get_tasks(session, query), ready)

    def report_week(self):
        # Период рассчитывается от даты сервера, а не часов рабочей станции.
        session = self.session
        def ready(result):
            today = QDate(result.today.year, result.today.month, result.today.day)
            monday = today.addDays(1 - today.dayOfWeek())
            self.window.reports.date_enabled.setChecked(True)
            self.window.reports.date_from.setDate(monday)
            self.window.reports.date_to.setDate(monday.addDays(6))
            self.open_reports()
        self.run(lambda: self.tasks.get_tasks(session), ready)

    def select_report(self):
        tasks = self.window.tasks.selected()
        if not tasks:
            self.error(AppError("Выберите хотя бы одну задачу."))
            return
        self.window.reports.status.setCurrentIndex(0)
        self.window.reports.date_enabled.setChecked(False)
        self.open_reports(selected_ids=[task.id for task in tasks], generate=True)

    def generate_report(self):
        session, ids = self.session, self.window.reports.selected_ids()
        self.window.reports.text.clear()
        if not ids:
            self.error(AppError("Выберите задачи на вкладке «Выбор задач»."))
            return

        def success(report):
            self.window.reports.text.setPlainText(report)
            self.window.reports.tabs.setCurrentIndex(1)
            self.window.pages.setCurrentWidget(self.window.reports)

        self.run(lambda: self.reports.create_summary(session, ids), success)

    def copy_report(self):
        report = self.window.reports.text.toPlainText()
        if not report:
            self.error(AppError("Сначала сформируйте отчёт."))
            return
        QApplication.clipboard().setText(report)
        self.window.set_activity("Отчёт скопирован в буфер обмена")

    def export_csv(self, kind):
        path, _ = QFileDialog.getSaveFileName(self.window, "Сохранить CSV", "tasks.csv" if kind == "tasks" else "users.csv", "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        session, query = self.session, self.last_query
        operation = (lambda: self.reports.export_tasks(session, query, path)) if kind == "tasks" else (lambda: self.reports.export_users(session, path))
        self.run(operation, lambda _: self.window.set_activity(f"CSV сохранён: {path}"))
