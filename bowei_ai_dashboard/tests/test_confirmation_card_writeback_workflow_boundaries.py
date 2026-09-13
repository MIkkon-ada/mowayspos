from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from app import models, schemas
from tests.test_confirmation_card_coach_flow import _seed_card_coach_team
from tests.test_confirmation_card_coordinator_flow import _make_card_submission
from tests.test_execution_submission_to_work_progress_flow import _make_session


def test_confirm_task_card_service_writes_only_the_selected_card():
    from app.services import confirmation_card_writeback_workflow as workflow

    db = _make_session()
    team = _seed_card_coach_team(db)
    row = _make_card_submission(db, statuses=("", ""))
    data = json.loads(row.human_result_json)
    data["task_reports"][0].update(
        {
            "result_type": "subtask_progress",
            "type": "progress",
            "matched_subtask_id": team["subtask"].id,
            "completed": "写回服务测试进展",
            "achievements": [{"name": "写回服务成果"}],
            "subtask_issues": [{"description": "写回服务问题"}],
        }
    )
    row.human_result_json = json.dumps(data, ensure_ascii=False)
    db.commit()

    result = workflow.confirm_task_card(
        submission_id=row.id,
        card_index=0,
        payload=schemas.ConfirmRequest(operator="owner"),
        current_user="owner",
        db=db,
    )

    reports = json.loads(result["submission"]["human_result_json"])["task_reports"]
    assert reports[0]["confirmation_status"] == "confirmed"
    assert not reports[1].get("confirmation_status")
    achievement = db.query(models.Achievement).filter_by(source_submission_id=row.id).one()
    issue = db.query(models.Issue).filter_by(source_submission_id=row.id).one()
    assert achievement.related_subtask_id == team["subtask"].id
    assert issue.related_subtask_id == team["subtask"].id


def test_confirm_task_card_service_creates_suggested_subtask_with_lineage():
    from app.services import confirmation_card_writeback_workflow as workflow

    db = _make_session()
    team = _seed_card_coach_team(db)
    row = _make_card_submission(db, statuses=("",))
    data = json.loads(row.human_result_json)
    data["task_reports"][0].update(
        {
            "result_type": "suggest_new_subtask",
            "parent_task_id": team["task"].id,
            "title": "新增关键任务",
            "assignee": "member",
            "achievements": [{"name": "新增任务成果"}],
        }
    )
    row.human_result_json = json.dumps(data, ensure_ascii=False)
    db.commit()

    workflow.confirm_task_card(
        submission_id=row.id,
        card_index=0,
        payload=schemas.ConfirmRequest(operator="owner"),
        current_user="owner",
        db=db,
    )

    subtask = db.query(models.SubTask).filter_by(source_submission_id=row.id).one()
    achievement = db.query(models.Achievement).filter_by(source_submission_id=row.id).one()
    assert subtask.task_id == team["task"].id
    assert achievement.related_subtask_id == subtask.id
    assert db.get(models.UpdateSubmission, row.id).related_task_id == team["task"].id


def test_confirm_task_card_router_delegates_to_writeback_service():
    source = (
        Path(__file__).resolve().parents[1] / "app" / "routers" / "confirmations.py"
    ).read_text(encoding="utf-8")
    start = source.index("def confirm_task_card(")
    end = source.index("@router.post(\"/{submission_id}/cards/{card_index}/reject\")", start)
    body = source[start:end]
    assert "card_writeback_workflow.confirm_task_card(" in body


def test_confirm_task_card_service_parses_string_subtask_issues():
    from app.services import confirmation_card_writeback_workflow as workflow

    db = _make_session()
    team = _seed_card_coach_team(db)
    row = _make_card_submission(db, statuses=("",))
    data = json.loads(row.human_result_json)
    data["task_reports"][0].update(
        {
            "result_type": "subtask_progress",
            "matched_subtask_id": team["subtask"].id,
            "subtask_issues": ["需决策：请确认测试方案"],
        }
    )
    row.human_result_json = json.dumps(data, ensure_ascii=False)
    db.commit()

    workflow.confirm_task_card(
        submission_id=row.id,
        card_index=0,
        payload=schemas.ConfirmRequest(operator="owner"),
        current_user="owner",
        db=db,
    )

    issue = db.query(models.Issue).filter_by(source_submission_id=row.id).one()
    assert issue.description == "请确认测试方案"
    assert issue.status == "待决策"


def test_confirm_task_card_service_rejects_non_owner_and_frozen_project():
    from app.services import confirmation_card_writeback_workflow as workflow

    db = _make_session()
    team = _seed_card_coach_team(db)
    row = _make_card_submission(db, statuses=("",))
    db.commit()

    with pytest.raises(HTTPException) as denied:
        workflow.confirm_task_card(
            submission_id=row.id, card_index=0,
            payload=schemas.ConfirmRequest(operator="coach"),
            current_user="coach", db=db,
        )
    assert denied.value.status_code == 403

    team["project"].status = "pending_close"
    db.commit()
    with pytest.raises(HTTPException) as frozen:
        workflow.confirm_task_card(
            submission_id=row.id, card_index=0,
            payload=schemas.ConfirmRequest(operator="owner"),
            current_user="owner", db=db,
        )
    assert frozen.value.status_code == 409
    assert not json.loads(db.get(models.UpdateSubmission, row.id).human_result_json)["task_reports"][0].get("confirmation_status")
