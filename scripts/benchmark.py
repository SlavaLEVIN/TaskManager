"""Замеры через Presenter до обновления Qt-виджетов на отдельной нагрузочной БД."""
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from common import database, parser

import psutil
from PySide6.QtWidgets import QApplication

from task_manager.domain import Priority, TaskQuery
from task_manager.ui.presenter import Presenter
from task_manager.ui.views import MainWindow


def main():
    arguments = parser(__doc__)
    arguments.add_argument("--output", type=Path, required=True)
    arguments.add_argument("--password", default=None, help="Только демонстрационный пароль; рабочие пароли не передавать в командной строке")
    args = arguments.parse_args()
    db = database(args)
    if not db.config.dbname.endswith("_test"):
        raise SystemExit("Используйте отдельную нагрузочную БД *_test.")
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    window = MainWindow()
    presenter = Presenter(window, db)
    window.show()
    durations = {}

    def wait():
        deadline = time.monotonic() + 60
        while window.busy:
            app.processEvents()
            if time.monotonic() > deadline:
                raise TimeoutError("Операция не завершилась за 60 секунд")
            time.sleep(0.001)
        app.processEvents()

    def measure(name, action):
        values = []
        for _ in range(5):
            started = time.perf_counter()
            action()
            wait()
            values.append(round(time.perf_counter() - started, 4))
        durations[name] = {"median_seconds": statistics.median(values), "max_seconds": max(values), "samples": values}

    window.login.login.setText("admin")
    window.login.password.setText(args.password or "Demo-2026!")
    presenter.login()
    wait()
    if presenter.session is None:
        raise RuntimeError("Не выполнен вход в нагрузочную БД")
    measure("list_ui", presenter.load_tasks)
    row_count = window.tasks.model.rowCount()
    window.tasks.search.setText("документов")
    measure("search_ui", presenter.load_tasks)
    window.tasks.search.clear()
    window.tasks.priority.setCurrentIndex(window.tasks.priority.findData(Priority.HIGH))
    measure("filter_ui", presenter.load_tasks)
    window.tasks.priority.setCurrentIndex(0)
    window.tasks.sort.setCurrentIndex(window.tasks.sort.findData("priority"))
    measure("sort_ui", presenter.load_tasks)
    presenter.report_ids = [t.id for t in window.tasks.model.objects]
    measure("report_1000_ui", presenter.generate_report)
    with tempfile.TemporaryDirectory() as directory:
        measure("csv_1000_ui", lambda: presenter.run(
            lambda: presenter.reports.export_tasks(presenter.session, TaskQuery(), Path(directory) / "tasks.csv"),
            lambda _: window.statusBar().showMessage("CSV записан")))
    with db.transaction() as cursor:
        cursor.execute("SELECT pg_database_size(current_database()) AS bytes,version() AS version")
        size = dict(cursor.fetchone())
        cursor.execute("SELECT count(*) AS n FROM users")
        users = cursor.fetchone()["n"]
    output = {
        "platform": platform.platform(), "processor": platform.processor(), "python": platform.python_version(),
        "physical_memory_bytes": psutil.virtual_memory().total, "logical_cpus": psutil.cpu_count(),
        "network": f"{db.config.host}:{db.config.port}", "mode": os.environ.get("QT_QPA_PLATFORM", "native Qt"),
        "users": users, "tasks": row_count, "database": size,
        "client_rss_bytes": psutil.Process().memory_info().rss, "timings": durations,
        "limits": "Source client, not a Windows executable; UI event processing included, actual monitor presentation not measured.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    window.close_pending = True
    window.close()
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
