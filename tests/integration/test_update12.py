from dataclasses import replace
from datetime import date, timedelta

import pytest
from task_manager.domain import AccessError, AppError, Priority, TaskInput, TaskQuery

pytestmark = pytest.mark.integration


def test_admin_categories_preserve_task_references(env):
    category_id = env.tasks.save_category(env.admin, 'Разработка')
    task_id = env.tasks.create_task(env.admin, TaskInput('Модуль', '', 2, category_id, env.today, Priority.HIGH))
    env.tasks.save_category(env.admin, 'Программирование', category_id)
    task = env.tasks.get_selected(env.ivan, [task_id]).tasks[0]
    assert task.category == 'Программирование' and task.category_id == category_id
    with pytest.raises(AppError, match='уже существует'):
        env.tasks.save_category(env.admin, 'программирование')
    for name, id_ in (('Новая', None), ('Изменена', category_id)):
        with pytest.raises(AccessError):
            env.tasks.save_category(env.ivan, name, id_)
    with pytest.raises(AppError):
        env.tasks.save_category(env.admin, '  ')


def test_date_filter_boundaries_year_and_optional_overdue_line(env):
    template = TaskInput('Срок', '', 2, 1, date(2026, 9, 29), Priority.MEDIUM)
    ids = [env.tasks.create_task(env.admin, replace(template, due_date=value)) for value in
           (date(2026, 9, 29), date(2026, 10, 4), date(2027, 10, 3))]
    query = TaskQuery(date_from=date(2026, 9, 29), date_to=date(2026, 10, 4))
    assert [t.id for t in env.tasks.get_tasks(env.admin, query).tasks] == ids[:2]
    assert len(env.tasks.get_tasks(env.admin).tasks) == 3
    today = env.tasks.create_task(env.admin, replace(template, due_date=env.today))
    late = env.tasks.create_task(env.admin, replace(template, due_date=env.today-timedelta(days=1)))
    report = env.reports.create_summary(env.admin, [today])
    assert 'Просрочена' not in report and 'Дата создания отчёта:' in report
    assert 'Просрочена' in env.reports.create_summary(env.admin, [late])
