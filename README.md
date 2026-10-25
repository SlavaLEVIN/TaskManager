# TaskManager

Настольный менеджер задач для Windows 10/11 x64 с двумя ролями и базой PostgreSQL.

**Если нужна готовая программа, откройте [Releases](https://github.com/SlavaLEVIN/TaskManager/releases) и скачайте `TaskManager-Windows-Portable.zip`.** Кнопка GitHub «Code → Download ZIP» скачивает исходный код, а не готовую программу.

В пользовательском архиве находятся `TaskManager.exe`, мастера `TaskManager-Setup.exe` и `TaskManager-Update.exe`, команды для их запуска и короткая инструкция. Python на рабочем компьютере не требуется. Для уже настроенной базы достаточно запустить новый `TaskManager.exe`; мастер создания базы повторно запускать нельзя.

В репозитории оставлены исходники приложения, скрипты создания и обновления базы, SQL-схема, сборка и документация для курсовой:

| Путь | Назначение |
|---|---|
| `src/task_manager/` | код приложения и ресурсы интерфейса |
| `scripts/setup_database.py`, `scripts/update_database.py` | создание и обновление базы |
| `database/` | SQL-схема и начальные категории |
| `packaging/`, `scripts/build_windows.ps1` | сборка трёх EXE |
| `docs/` | руководства и схемы |

Рабочие пароли не включены в исходники. Настройки клиента хранятся в `%LOCALAPPDATA%\TaskManager\database.ini` либо в `database.ini` рядом с EXE, если файл был размещён там вручную. Задачи и пользователи хранятся в PostgreSQL, поэтому обновление клиентских файлов их не удаляет.

Для сборки из исходников на Windows установите Python 3.13 x64 и запустите `BUILD_WINDOWS.cmd`. Скрипт соберёт три EXE в папку `dist`. Приёмку проводите по ТЗ.

Руководства: [пользователю](docs/user_manual.md), [системному программисту](docs/system_programmer_manual.md), [обновление](docs/UPDATE.md).
