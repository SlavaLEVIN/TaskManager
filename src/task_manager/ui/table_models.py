from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from ..domain import LABELS, TaskList, TaskStatus


class TableModel(QAbstractTableModel):
    """Только отображение; сортировка выполняется сервисом и PostgreSQL."""

    def __init__(self, headers, parent=None):
        super().__init__(parent)
        self.headers = headers
        self.rows = []
        self.objects = []
        self.colors = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return str(self.rows[index.row()][index.column()])
        if role == Qt.ItemDataRole.ForegroundRole and self.colors:
            return QColor(self.colors[index.row()])
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def replace(self, rows, objects, colors=None):
        self.beginResetModel()
        self.rows, self.objects, self.colors = rows, objects, colors or []
        self.endResetModel()

    def clear(self):
        self.replace([], [])


class TaskTableModel(TableModel):
    def __init__(self, parent=None):
        super().__init__(["Название", "Ответственный", "Категория", "Приоритет", "Срок", "Статус", "Просрочена"], parent)

    def set_tasks(self, result: TaskList):
        rows, colors = [], []
        for task in result.tasks:
            late = task.is_overdue(result.today)
            rows.append([task.title, task.assignee, task.category, LABELS[task.priority],
                         task.due_date.strftime("%d.%m.%Y"), LABELS[task.status], "Да" if late else "Нет"])
            colors.append("#b42318" if late else "#087443" if task.status == TaskStatus.COMPLETED else "#213247")
        self.replace(rows, result.tasks, colors)
