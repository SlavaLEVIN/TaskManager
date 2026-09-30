"""Последовательные фоновые операции; сигналы возвращаются в GUI-поток."""

import logging
import traceback

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ..domain import AppError


class WorkerSignals(QObject):
    done = Signal(object, object)


class Worker(QRunnable):
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.operation()
        except AppError as error:
            self.signals.done.emit(None, error)
        except Exception as error:
            frames = [(frame.name, frame.lineno) for frame in traceback.extract_tb(error.__traceback__)]
            logging.getLogger(__name__).error("Unexpected error type=%s frames=%s", type(error).__name__, frames)
            self.signals.done.emit(None, AppError("Не удалось выполнить операцию. Технические сведения записаны в журнал."))
        else:
            self.signals.done.emit(result, None)
