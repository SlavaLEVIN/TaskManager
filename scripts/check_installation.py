"""Локальная проверка Python, DLL Qt, драйвера и ресурсов без подключения к БД."""
import importlib.metadata
import platform
import struct
from pathlib import Path

from common import ROOT

import bcrypt
import psycopg2
from PySide6.QtCore import qVersion
from PySide6.QtWidgets import QApplication, QLabel


def main():
    print("OS:", platform.platform())
    print("Python:", platform.python_version(), "; bits:", struct.calcsize("P") * 8)
    for package in ("PySide6-Essentials", "shiboken6", "psycopg2-binary", "bcrypt"):
        print(package, importlib.metadata.version(package))
    print("Qt:", qVersion())
    app = QApplication([])
    label = QLabel("Менеджер задач — проверка Qt")
    label.resize(350, 60)
    label.show()
    app.processEvents()
    assert not label.grab().isNull()
    assert (ROOT / "src/task_manager/resources/help.html").is_file()
    assert (ROOT / "src/task_manager/resources/app.svg").is_file()
    assert bcrypt.checkpw(b"local-test", bcrypt.hashpw(b"local-test", bcrypt.gensalt(rounds=4)))
    label.close()
    print("Local dependency check: OK. Database access was not tested.")


if __name__ == "__main__":
    main()
