import logging
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from .config import DatabaseConfig, data_directory
from .database import Database
from .domain import AppError
from .ui.presenter import Presenter
from .ui.views import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Менеджер задач")
    app.setOrganizationName("TaskManager")
    app.setStyle("Fusion")
    QLocale.setDefault(QLocale(QLocale.Language.Russian, QLocale.Country.Russia))
    try:
        log_directory = data_directory() / "logs"
        log_directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_directory / "application.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
    except OSError:
        logging.getLogger().addHandler(logging.NullHandler())
    configuration_notice = None
    try:
        config = DatabaseConfig.load()
    except AppError as error:
        config = DatabaseConfig()
        configuration_notice = str(error)
    window = MainWindow()
    presenter = Presenter(window, Database(config))
    if configuration_notice:
        window.set_activity(configuration_notice)
    window.show()
    result = app.exec()
    presenter.pool.waitForDone()
    return result
