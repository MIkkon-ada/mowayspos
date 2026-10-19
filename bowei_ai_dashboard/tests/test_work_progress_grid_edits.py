from datetime import timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import models, schemas
from app.routers import subtasks
from tests.test_key_task_execution_workspace import _db, _seed_workspace


def _setup():
    db = _db()
    project, task, row = _seed_workspace(db)
    db.add(models.SubTask(id=21, task_id=task.id, title="另一项工作", assignee="负责人", assignee_id=1, status="进行中"))
    db.add(models.Account(username="member", password_hash="x", person_id=2, status="active"))
    db.commit()
    return db, project, row


def _edit(row, **changes):
    return {"id": row.id, "expected_updated_at": row.updated_at.isoformat(), "changes": changes}


def test_grid_updates_explicit_fields_dates_and_audit_without_erasing_other_data():
    db, _, row = _setup()
    row.notes = "保留原始备注"
    db.commit()
    result = subtasks.update_work_progress_cells(1, schemas.WorkProgressEditsPayload(edits=[_edit(row, title="核对交付", due_date="2026-10-30")]), current_user="owner", db=db)
    db.refresh(row)
    assert row.title == "核对交付"
    assert str(row.due_date) == "2026-10-30" and row.due_kind == "exact"
    assert row.notes == "保留原始备注" and row.collaborator_ids == [2]
    assert result["updated_ids"] == [20]
    assert db.query(models.OperationLog).filter_by(action="work_progress_grid_edit").count() == 1


def test_grid_conflict_rolls_back_entire_batch():
    db, _, row = _setup()
    other = db.get(models.SubTask, 21)
    edits = [_edit(row, title="不应保存"), _edit(other, title="版本冲突")]
    edits[1]["expected_updated_at"] = (other.updated_at - timedelta(seconds=1)).isoformat()
    with pytest.raises(HTTPException) as error:
        subtasks.update_work_progress_cells(1, schemas.WorkProgressEditsPayload(edits=edits), current_user="owner", db=db)
    assert error.value.status_code == 409
    db.refresh(row)
    assert row.title == "完成系统模块梳理与迭代"
    assert db.query(models.OperationLog).filter_by(action="work_progress_grid_edit").count() == 0


def test_grid_uses_precise_version_returned_by_list_endpoint():
    db, _, row = _setup()
    wire = subtasks.list_subtasks(row.task_id, current_user="owner", db=db)[0]
    assert wire["edit_version"] != wire["updated_at"]
    result = subtasks.update_work_progress_cells(1, schemas.WorkProgressEditsPayload(edits=[{"id": row.id, "expected_updated_at": wire["edit_version"], "changes": {"notes": "界面返回的版本可直接保存"}}]), current_user="owner", db=db)
    assert result["updated_ids"] == [row.id]


@pytest.mark.parametrize("case", ["member", "archived", "cross_project", "completed"])
def test_grid_enforces_scope_and_business_write_rules(case):
    db, project, row = _setup()
    if case == "archived":
        project.status = "archived"
    if case == "cross_project":
        db.get(models.Task, row.task_id).project_id = 2
    if case == "completed":
        row.status = "已完成"
    db.commit()
    with pytest.raises(HTTPException) as error:
        subtasks.update_work_progress_cells(1, schemas.WorkProgressEditsPayload(edits=[_edit(row, title="拒绝修改")]), current_user="member" if case == "member" else "owner", db=db)
    assert error.value.status_code in (403, 409)
    db.refresh(row)
    assert row.title == "完成系统模块梳理与迭代"


@pytest.mark.parametrize("changes", [{"status": "已完成"}, {"latest_confirmed_progress": "伪造进展"}, {"title": ""}, {"due_date": "2026-02-30"}])
def test_grid_rejects_readonly_or_invalid_fields(changes):
    with pytest.raises(ValidationError):
        schemas.WorkProgressEditsPayload(edits=[{"id": 1, "expected_updated_at": "2026-10-19T09:00:00", "changes": changes}])
