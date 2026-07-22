from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.services.cross_project_submission import create_submission_batch


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(db):
    admin = models.Person(id=1, name="管理员", system_role="super_admin", is_admin=True, is_active=True)
    owner_a = models.Person(id=2, name="负责人A", system_role="normal_member", is_active=True)
    owner_b = models.Person(id=3, name="负责人B", system_role="normal_member", is_active=True)
    member = models.Person(id=4, name="成员", system_role="normal_member", is_active=True)
    db.add_all([admin, owner_a, owner_b, member])
    db.flush()
    db.add_all([
        models.Account(username="admin", password_hash="x", person_id=1, status="active", is_tech_admin=True),
        models.Account(username="member", password_hash="x", person_id=4, status="active"),
    ])
    projects = [
        models.Project(id=1, name="项目A", status="active", is_active=True),
        models.Project(id=2, name="项目B", status="active", is_active=True),
    ]
    db.add_all(projects)
    db.flush()
    db.add_all([
        models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="负责人A", role="owner"),
        models.ProjectMember(project_id=2, person_id=3, person_name_snapshot="负责人B", role="owner"),
        models.ProjectMember(project_id=1, person_id=4, person_name_snapshot="成员", role="member"),
    ])
    tasks = [
        models.Task(id=11, project_id=1, special_project="项目A", key_task="重点工作A", status="进行中"),
        models.Task(id=22, project_id=2, special_project="项目B", key_task="重点工作B", status="进行中"),
    ]
    db.add_all(tasks)
    db.flush()
    db.add_all([
        models.SubTask(id=111, task_id=11, title="任务A1", assignee="成员", status="进行中"),
        models.SubTask(id=112, task_id=11, title="任务A2", assignee="成员", status="进行中"),
        models.SubTask(id=221, task_id=22, title="任务B1", assignee="成员", status="进行中"),
    ])
    db.commit()


def _card(parent: int, subtask: int, title: str) -> dict:
    return {
        "type": "progress", "match_status": "matched", "parent_task_id": parent,
        "matched_subtask_id": subtask, "matched_subtask_title": title,
        "completed": f"完成{title}", "achievements": [], "subtask_issues": [], "next_steps": [],
    }


def _payload(request_id="request-1", cards=None):
    return schemas.BatchUpdateRequest(
        client_request_id=request_id,
        source_type="文字更新",
        title="跨项目工作汇报",
        transcript_text="完成任务A和任务B",
        human_result={"task_reports": cards or [_card(11, 111, "任务A1"), _card(22, 221, "任务B1")]},
    )


def test_two_projects_create_two_children_and_same_project_cards_group():
    db = _session(); _seed(db)
    payload = _payload(cards=[_card(11, 111, "任务A1"), _card(11, 112, "任务A2"), _card(22, 221, "任务B1")])
    result = create_submission_batch(payload, current_user="admin", db=db)
    db.commit()

    assert result["batch"].submission_count == 2
    children = db.query(models.UpdateSubmission).order_by(models.UpdateSubmission.batch_order).all()
    assert [row.project_id for row in children] == [1, 2]
    assert len(json.loads(children[0].human_result_json)["task_reports"]) == 2
    assert len(json.loads(children[1].human_result_json)["task_reports"]) == 1
    assert {r["matched_subtask_id"] for r in json.loads(children[0].human_result_json)["task_reports"]} == {111, 112}


def test_invalid_card_rolls_back_without_batch_or_child():
    db = _session(); _seed(db)
    payload = _payload(cards=[_card(11, 111, "任务A1"), _card(11, 221, "错误跨项目关系")])
    with pytest.raises(HTTPException) as exc:
        create_submission_batch(payload, current_user="admin", db=db)
    db.rollback()
    assert exc.value.status_code == 422
    assert "任务卡 2" in str(exc.value.detail)
    assert db.query(models.UpdateSubmissionBatch).count() == 0
    assert db.query(models.UpdateSubmission).count() == 0


def test_member_without_access_to_every_project_gets_zero_writes():
    db = _session(); _seed(db)
    with pytest.raises(HTTPException) as exc:
        create_submission_batch(_payload(), current_user="member", db=db)
    db.rollback()
    assert exc.value.status_code == 403
    assert db.query(models.UpdateSubmissionBatch).count() == 0
    assert db.query(models.UpdateSubmission).count() == 0


def test_idempotent_request_returns_existing_batch_without_duplicate_rows_or_notifications():
    db = _session(); _seed(db)
    first = create_submission_batch(_payload(), current_user="admin", db=db)
    db.commit()
    notification_count = db.query(models.Notification).count()
    second = create_submission_batch(_payload(), current_user="admin", db=db)
    db.commit()

    assert second["batch"].id == first["batch"].id
    assert db.query(models.UpdateSubmissionBatch).count() == 1
    assert db.query(models.UpdateSubmission).count() == 2
    assert db.query(models.Notification).count() == notification_count == 2


def test_idempotency_key_cannot_replay_another_submitters_batch():
    db = _session(); _seed(db)
    create_submission_batch(_payload("shared-request-id"), current_user="admin", db=db)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        create_submission_batch(_payload("shared-request-id"), current_user="member", db=db)

    assert exc.value.status_code == 409
    assert db.query(models.UpdateSubmissionBatch).count() == 1
    assert db.query(models.UpdateSubmission).count() == 2


def test_batch_endpoint_commits_and_returns_serialized_children():
    import asyncio
    from app.routers.updates import create_update_batch

    db = _session(); _seed(db)
    result = asyncio.run(create_update_batch(_payload("request-endpoint"), current_user="admin", db=db))
    assert result["batch"]["submission_count"] == 2
    assert [item["project_id"] for item in result["submissions"]] == [1, 2]
    assert db.query(models.UpdateSubmissionBatch).count() == 1


def test_personal_history_contains_batch_metadata_and_legacy_rows_stay_unbatched():
    from app.routers.updates import list_updates

    db = _session(); _seed(db)
    create_submission_batch(_payload("request-history"), current_user="admin", db=db)
    db.add(models.UpdateSubmission(
        project_id=1, source_type="manual", submitter="管理员", submitter_id=1,
        title="旧提交", transcript_text="旧记录", confirm_status="待确认",
    ))
    db.commit()
    rows = list_updates(mine=True, current_user="admin", db=db)
    batch_rows = [item for item in rows if item.get("batch_id")]
    legacy = next(item for item in rows if item["title"] == "旧提交")
    assert len(batch_rows) == 2
    assert {item["batch_submission_count"] for item in batch_rows} == {2}
    assert {item["project_name"] for item in batch_rows} == {"项目A", "项目B"}
    assert legacy.get("batch_id") is None
