from __future__ import annotations

import asyncio

from app import models, schemas
from app.domain import submission_status as SS
from app.routers.confirmations import confirm
from app.routers.updates import create_update

from tests.test_execution_submission_to_work_progress_flow import (
    _make_session,
    _seed_execution_team,
)


def _submit_with_human_result(db, team, human_result: dict) -> int:
    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="manual",
        title="工作汇报",
        transcript_text="完成资料整理，形成资料清单初稿。",
        submitter=team["member"].name,
        human_result=human_result,
    )
    result = asyncio.run(create_update(payload, current_user="member", db=db))
    return result["submission"]["id"]


def test_confirm_suggest_new_subtask_writes_report_achievements():
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "suggest_new_subtask",
                "type": "suggest_new_subtask",
                "title": "资料整理与初步验证",
                "assignee": team["member"].name,
                "parent_task_id": team["task"].id,
                "parent_key_task": team["task"].key_task,
                "completed": "完成第一版资料清单整理",
                "achievements": [
                    {"name": "资料清单初稿", "achievement_type": "表格"},
                ],
                "subtask_issues": [],
                "next_steps": ["继续补充缺失资料"],
            }
        ],
        "achievements": [
            {"name": "资料清单初稿", "achievement_type": "表格"},
        ],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    result = confirm(
        submission_id,
        schemas.ConfirmRequest(operator="owner"),
        current_user="owner",
        db=db,
    )

    assert result["ok"] is True
    row = db.get(models.UpdateSubmission, submission_id)
    assert row.confirm_status == SS.S_CONFIRMED
    assert row.related_task_id == team["task"].id

    created_subtask = (
        db.query(models.SubTask)
        .filter_by(source_submission_id=submission_id)
        .one()
    )
    assert created_subtask.task_id == team["task"].id
    assert created_subtask.title == "资料整理与初步验证"

    achievements = (
        db.query(models.Achievement)
        .filter_by(source_submission_id=submission_id)
        .all()
    )
    assert len(achievements) == 1
    achievement = achievements[0]
    assert achievement.name == "资料清单初稿"
    assert achievement.project_id == team["project"].id
    assert achievement.related_task_id == team["task"].id
    assert achievement.source_submission_id == submission_id
    assert achievement.confirmed_by == "owner"
    assert achievement.confirmed_at is not None


def test_confirm_existing_subtask_report_achievement_still_writes_once():
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "完成现有关键任务进展",
                "achievements": [
                    {"name": "现有关键任务成果", "achievement_type": "文档"},
                ],
                "subtask_issues": [],
            }
        ],
        "achievements": [
            {"name": "现有关键任务成果", "achievement_type": "文档"},
        ],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    confirm(
        submission_id,
        schemas.ConfirmRequest(operator="owner"),
        current_user="owner",
        db=db,
    )

    achievements = (
        db.query(models.Achievement)
        .filter_by(source_submission_id=submission_id)
        .all()
    )
    assert len(achievements) == 1
    assert achievements[0].name == "现有关键任务成果"
