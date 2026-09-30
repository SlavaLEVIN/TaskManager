from datetime import date, timedelta

import pytest

from task_manager.domain import AppError, Priority, Task, TaskInput, TaskQuery, TaskStatus, password_bytes


@pytest.mark.parametrize("old,new,allowed", [
    ("NEW", "NEW", True), ("NEW", "IN_PROGRESS", True), ("NEW", "COMPLETED", False),
    ("IN_PROGRESS", "NEW", True), ("IN_PROGRESS", "IN_PROGRESS", True), ("IN_PROGRESS", "COMPLETED", True),
    ("COMPLETED", "NEW", False), ("COMPLETED", "IN_PROGRESS", True), ("COMPLETED", "COMPLETED", True),
])
def test_transitions(old, new, allowed):
    task = Task(1, "Задача", "", 1, 1, date(2026, 9, 30), Priority.LOW, TaskStatus(old))
    if allowed:
        task.change_status(TaskStatus(new))
        assert task.status == new
    else:
        with pytest.raises(AppError):
            task.change_status(TaskStatus(new))
        assert task.status == old


@pytest.mark.parametrize("offset,status,late", [(-1, "NEW", True), (0, "NEW", False), (1, "NEW", False), (-1, "COMPLETED", False)])
def test_overdue(offset, status, late):
    today = date(2026, 9, 30)
    task = Task(1, "a", "", 1, 1, today + timedelta(days=offset), Priority.LOW, TaskStatus(status))
    assert task.is_overdue(today) is late


def test_password_is_not_trimmed_and_has_explicit_byte_limit():
    assert password_bytes("  пароль  ") == "  пароль  ".encode()
    assert len(password_bytes("я" * 36)) == 72
    with pytest.raises(AppError, match="72"):
        password_bytes("я" * 37)
    with pytest.raises(AppError):
        password_bytes("")


def test_invalid_dates_and_range():
    with pytest.raises(AppError):
        TaskInput("t", "", 1, 1, "2026-02-30", Priority.LOW).validate()
    with pytest.raises(AppError):
        TaskQuery(date_from=date(2026, 10, 2), date_to=date(2026, 10, 1)).validate()
    TaskInput("t", "", 1, 1, date(2000, 1, 1), Priority.LOW).validate()
