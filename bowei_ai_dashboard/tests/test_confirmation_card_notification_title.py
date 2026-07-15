"""FIX-2D: readable task-card notification titles and unchanged routing metadata."""
from __future__ import annotations

import json

import pytest

from app import models, schemas
from app.domain import submission_status as SS
from app.routers.confirmations import (
    _get_card_title,
    ceo_decide_task_card,
    coordinator_feedback_task_card,
    escalate_task_card_to_ceo,
    transfer_task_card_to_coordinator,
)
from tests.test_confirmation_card_coach_flow import _seed_card_coach_team
from tests.test_execution_submission_to_work_progress_flow import _make_session


MATCHED_TITLE = "资料核验"


def _report(**overrides) -> dict:
    report = {
        "result_type": "subtask_progress",
        "type": "progress",
        "matched_subtask_id": 1,
        "matched_subtask_title": MATCHED_TITLE,
        "title": "",
        "key_task": "",
        "content": "",
        "completed": "完成资料核验",
        "achievements": [],
        "subtask_issues": [],
    }
    report.update(overrides)
    return report


def _submission(db, team) -> models.UpdateSubmission:
    data = {
        "special_project": team["project"].name,
        "task_reports": [_report()],
        "achievements": [],
        "issues": [],
    }
    row = models.UpdateSubmission(
        project_id=team["project"].id,
        source_type="任务进展",
        submitter=team["member"].name,
        submitter_id=team["member"].id,
        title="提交标题",
        transcript_text="完成资料核验",
        ai_result_json=json.dumps(data, ensure_ascii=False),
        human_result_json=json.dumps(data, ensure_ascii=False),
        confirm_status=SS.S_PENDING_OWNER,
    )
    db.add(row)
    db.flush()
    return row


def _notification(db, ntype: str, recipient_id: int) -> models.Notification:
    return (
        db.query(models.Notification)
        .filter(models.Notification.type == ntype, models.Notification.recipient_id == recipient_id)
        .one()
    )


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        ({"matched_subtask_title": "资料核验", "title": "", "key_task": "", "content": ""}, "资料核验"),
        ({"matched_subtask_title": "", "subtask_title": "历史关键任务"}, "历史关键任务"),
        ({"matched_subtask_title": "", "subtask_title": "", "title": "新增关键任务"}, "新增关键任务"),
        ({"matched_subtask_title": "", "subtask_title": "", "title": "", "parent_key_task": "数据质量验证"}, "数据质量验证"),
        ({"key_task": "历史重点工作"}, "历史重点工作"),
        ({"content": "历史任务内容"}, "历史任务内容"),
        ({}, "（无标题）"),
        ({"matched_subtask_title": "   ", "title": "有效标题"}, "有效标题"),
        ({"matched_subtask_title": "资料核验", "parent_key_task": "不能覆盖"}, "资料核验"),
    ],
)
def test_get_card_title_priority_and_backward_compatibility(report, expected):
    assert _get_card_title(report) == expected


def test_get_card_title_truncates_to_100_characters():
    result = _get_card_title({"matched_subtask_title": "标" * 120})
    assert result == "标" * 100
    assert len(result) == 100


def test_transfer_to_coordinator_notification_uses_matched_subtask_title():
    db = _make_session()
    team = _seed_card_coach_team(db)
    row = _submission(db, team)

    transfer_task_card_to_coordinator(
        row.id,
        0,
        schemas.WorkflowNoteRequest(note="请统筹评估", operator="owner"),
        current_user="owner",
        db=db,
    )

    notification = _notification(db, "confirmation_card_transferred_to_coordinator", team["coordinator"].id)
    assert notification.title == f"有任务卡需要你提供统筹意见：{MATCHED_TITLE}"
    assert "（无标题）" not in notification.title
    assert notification.project_id == team["project"].id
    assert notification.link == f"/work/confirmations?view=coordinator&projectId=1&submissionId={row.id}&cardIndex=0"


def test_coordinator_feedback_notification_uses_matched_subtask_title():
    db = _make_session()
    team = _seed_card_coach_team(db)
    row = _submission(db, team)
    transfer_task_card_to_coordinator(
        row.id, 0, schemas.WorkflowNoteRequest(note="请统筹评估", operator="owner"), current_user="owner", db=db,
    )

    coordinator_feedback_task_card(
        row.id,
        0,
        schemas.WorkflowNoteRequest(note="建议继续推进", operator="coordinator"),
        current_user="coordinator",
        db=db,
    )

    notification = _notification(db, "confirmation_card_coordinator_feedback", team["owner"].id)
    assert notification.title == f"统筹人已反馈任务卡：{MATCHED_TITLE}"
    assert "（无标题）" not in notification.title
    assert notification.project_id == team["project"].id
    assert notification.link == f"/work/confirmations?view=all&projectId=1&submissionId={row.id}&cardIndex=0"

def test_escalate_to_coach_notification_uses_matched_subtask_title():
    db = _make_session()
    team = _seed_card_coach_team(db)
    row = _submission(db, team)

    escalate_task_card_to_ceo(
        row.id,
        0,
        schemas.WorkflowNoteRequest(note="请教练决策", operator="owner"),
        current_user="owner",
        db=db,
    )

    notification = _notification(db, "confirmation_card_escalate_ceo", team["coach"].id)
    assert notification.title == f"有任务卡需要您决策：{MATCHED_TITLE}"
    assert "（无标题）" not in notification.title
    assert notification.project_id == team["project"].id
    assert notification.link == f"/work/confirmations?view=ceo&projectId=1&submissionId={row.id}&cardIndex=0"


def test_coach_decision_notification_uses_matched_subtask_title():
    db = _make_session()
    team = _seed_card_coach_team(db)
    row = _submission(db, team)
    escalate_task_card_to_ceo(
        row.id, 0, schemas.WorkflowNoteRequest(note="请教练决策", operator="owner"), current_user="owner", db=db,
    )

    ceo_decide_task_card(
        row.id,
        0,
        schemas.WorkflowNoteRequest(note="同意继续", operator="coach"),
        current_user="coach",
        db=db,
    )

    notification = _notification(db, "confirmation_card_ceo_decided", team["owner"].id)
    assert notification.title == f"企业教练已批示任务卡：{MATCHED_TITLE}"
    assert "（无标题）" not in notification.title
    assert notification.project_id == team["project"].id
    assert notification.link == f"/work/confirmations?view=all&projectId=1&submissionId={row.id}&cardIndex=0"
