"""Связь представлений, сессии и сервисов; все запросы выполняются вне GUI-потока."""

from PySide6.QtCore import QObject, QThreadPool, Qt, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ..config import DatabaseConfig
from ..database import Database
from ..domain import AccessError, AppError, SessionExpired, TaskQuery
from ..services import AuthService, ReportService, TaskService, UserService
from .views import SettingsDialog, TaskDialog, UserDialog
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
        w.login.retry.clicked.connect(self.reconnect)
        w.retry.clicked.connect(self.reconnect)
        w.logout.clicked.connect(self.logout)
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
        w.tasks.report.clicked.connect(self.select_report)
        w.users.create.clicked.connect(lambda: self.edit_user("create"))
        w.users.edit.clicked.connect(lambda: self.edit_user("edit"))
        w.users.password.clicked.connect(lambda: self.edit_user("password"))
        w.users.delete.clicked.connect(self.delete_user)
        w.users.tasks.clicked.connect(self.user_tasks)
        w.users.refresh.clicked.connect(self.load_users)
        w.reports.generate.clicked.connect(self.generate_report)
        w.reports.tasks_csv.clicked.connect(lambda: self.export_csv("tasks"))
        w.reports.users_csv.clicked.connect(lambda: self.export_csv("users"))

    def error(self, error):
        QMessageBox.warning(self.dialog if self.dialog and self.dialog.isVisible() else self.window, "Менеджер задач", str(error))

    def run(self, operation, callback, *, protected=True):
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
        self.window.centralWidget().setEnabled(False)
        self.window.retry.setEnabled(False)
        if self.dialog:
            self.dialog.set_busy(True)
        self.window.statusBar().showMessage("Выполняется операция…")
        self.callback = callback
        self.worker = Worker(wrapped)
        self.worker.signals.done.connect(self.finished)
        self.pool.start(self.worker)

    @Slot(object, object)
    def finished(self, payload, failure):
        self.window.busy = False
        self.window.centralWidget().setEnabled(True)
        self.window.retry.setEnabled(True)
        if self.dialog:
            self.dialog.set_busy(False)
        self.window.statusBar().showMessage("Готово")
        callback, self.callback = self.callback, None
        self.worker = None
        if self.window.close_pending:
            self.window.close()
            return
        if failure is not None:
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
            self.window.statusBar().showMessage("Права изменены. Данные очищены; откройте нужный раздел заново.")
            if error:
                self.error(error)
            return
        if error:
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
        self.window.statusBar().showMessage("Вход выполнен")

    def logout(self):
        if self.window.busy:
            return
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
        self.window.statusBar().showMessage("Войдите в учётную запись")

    def settings(self):
        dialog = SettingsDialog(self.database.config, self.window)

        def save():
            try:
                config = dialog.values()
                config.save()
                self._services(Database(config))
                dialog.accept()
                self.window.statusBar().showMessage("Настройки сохранены. Нажмите «Повторить подключение».")
            except AppError as error:
                self.error(error)

        self.show_dialog(dialog, save)

    def reconnect(self):
        def success(_):
            self.window.statusBar().showMessage("Подключение восстановлено")
            if self.session:
                self.load_tasks()
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
            self.fill_options(self.window.tasks.category, categories, "Все категории", "name")
            self.fill_options(self.window.tasks.assignee, users, "Все исполнители", "login")
            conditions = []
            if query.text:
                conditions.append(f"поиск: {query.text}")
            for widget in (self.window.tasks.status, self.window.tasks.priority, self.window.tasks.category, self.window.tasks.assignee):
                if widget.currentData() is not None:
                    conditions.append(widget.currentText())
            if query.date_from:
                conditions.append(f"срок: {query.date_from:%d.%m.%Y} — {query.date_to:%d.%m.%Y}")
            self.window.tasks.active_filters.setText("Условия: " + ("; ".join(conditions) if conditions else "все доступные задачи"))
            self.window.tasks.count.setText(f"Найдено задач: {len(result.tasks)} · Дата сервера: {result.today:%d.%m.%Y}" if result.tasks else "По заданным условиям доступных задач нет.")
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

    def change_status(self):
        task = self.one_task()
        status, session = self.window.tasks.new_status.currentData(), self.session
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

    def open_reports(self):
        session = self.session
        self.run(lambda: self.users.get_current(session), lambda _: self.window.pages.setCurrentWidget(self.window.reports))

    def select_report(self):
        tasks = self.window.tasks.selected()
        if not tasks:
            self.error(AppError("Выберите хотя бы одну задачу."))
            return
        self.report_ids = [task.id for task in tasks]
        self.window.reports.selection.setPlainText(f"Выбрано задач: {len(tasks)}\n" + "\n".join(f"№{t.id} {t.title}" for t in tasks))
        self.window.reports.text.clear()
        self.generate_report()

    def generate_report(self):
        session, ids = self.session, list(self.report_ids)
        self.window.reports.text.clear()

        def success(report):
            self.window.reports.text.setPlainText(report)
            self.window.pages.setCurrentWidget(self.window.reports)

        self.run(lambda: self.reports.create_summary(session, ids), success)

    def export_csv(self, kind):
        path, _ = QFileDialog.getSaveFileName(self.window, "Сохранить CSV", "tasks.csv" if kind == "tasks" else "users.csv", "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        session, query = self.session, self.last_query
        operation = (lambda: self.reports.export_tasks(session, query, path)) if kind == "tasks" else (lambda: self.reports.export_users(session, path))
        self.run(operation, lambda _: self.window.statusBar().showMessage(f"CSV сохранён: {path}"))
