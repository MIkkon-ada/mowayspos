from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.routers.projects import batch_import_projects
from tests.test_project_permission_characterization import _seed


def test_complete_work_plan_import_creates_workstreams_and_key_tasks():
    db = _seed()
    rows = [
        schemas.BatchImportRow(
            project_name="模拟完整计划",
            project_objective="完成年度目标",
            workstream="重点工作A",
            key_task="关键任务A1",
            completion_standard="标准A",
            owner="Owner",
            plan_start="2026-09-15",
            plan_end="2026-09-20",
            collaborators="Member",
            status="未开始",
            notes="备注A",
            issue="需要协调资源",
        ),
        schemas.BatchImportRow(
            project_name="模拟完整计划",
            project_objective="完成年度目标",
            workstream="重点工作A",
            key_task="关键任务A2",
            owner="Owner",
            plan_start="2026-09-21",
            plan_end="2026-09-25",
            status="进行中",
        ),
        schemas.BatchImportRow(
            project_name="模拟完整计划",
            workstream="重点工作B",
            key_task="关键任务B1",
            owner="Member",
            plan_time="持续",
        ),
    ]

    result = batch_import_projects(
        schemas.ProjectBatchImportPayload(rows=rows), current_user="admin", db=db
    )

    project = db.query(models.Project).filter_by(name="模拟完整计划").one()
    tasks = db.query(models.Task).filter_by(project_id=project.id).order_by(models.Task.id).all()
    subtasks = (
        db.query(models.SubTask)
        .filter(models.SubTask.task_id.in_([task.id for task in tasks]))
        .order_by(models.SubTask.id)
        .all()
    )

    assert result["projects_created"] == 1
    assert result["tasks_created"] == 2
    assert result["subtasks_created"] == 3
    assert [task.key_task for task in tasks] == ["重点工作A", "重点工作B"]
    assert [subtask.title for subtask in subtasks] == ["关键任务A1", "关键任务A2", "关键任务B1"]
    assert subtasks[0].task_id == tasks[0].id
    assert subtasks[1].task_id == tasks[0].id
    assert subtasks[2].task_id == tasks[1].id
    assert subtasks[0].plan_time == "2026-09-15~2026-09-20"
    assert "协同人：Member" in subtasks[0].notes
    assert project.objectives == "完成年度目标"
    assert db.query(models.Issue).filter_by(project_id=project.id).count() == 1


def test_reimport_skips_existing_work_plan_rows_without_duplicates():
    db = _seed()
    rows = [
        schemas.BatchImportRow(
            project_name="重复计划",
            workstream="重点工作",
            key_task="关键任务",
            owner="Owner",
        )
    ]
    payload = schemas.ProjectBatchImportPayload(rows=rows)

    first = batch_import_projects(payload, current_user="admin", db=db)
    second = batch_import_projects(payload, current_user="admin", db=db)

    project = db.query(models.Project).filter_by(name="重复计划").one()
    task = db.query(models.Task).filter_by(project_id=project.id).one()

    assert first["subtasks_created"] == 1
    assert second["tasks_created"] == 0
    assert second["subtasks_created"] == 0
    assert second["duplicates_skipped"] == 1
    assert db.query(models.Task).filter_by(project_id=project.id).count() == 1
    assert db.query(models.SubTask).filter_by(task_id=task.id).count() == 1


def test_invalid_work_plan_row_is_atomic_and_does_not_create_partial_data():
    db = _seed()
    payload = schemas.ProjectBatchImportPayload(
        rows=[
            schemas.BatchImportRow(
                project_name="不会部分写入",
                workstream="重点工作",
                key_task="有效关键任务",
                owner="Owner",
            ),
            schemas.BatchImportRow(
                project_name="不会部分写入",
                workstream="重点工作",
                key_task="",
                owner="Owner",
            ),
        ]
    )

    with pytest.raises(HTTPException) as exc:
        batch_import_projects(payload, current_user="admin", db=db)

    assert exc.value.status_code == 422
    assert db.query(models.Project).filter_by(name="不会部分写入").count() == 0
    assert db.query(models.Task).count() == 0
    assert db.query(models.SubTask).count() == 0
