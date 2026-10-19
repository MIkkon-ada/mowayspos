from __future__ import annotations

import json

from app import models, schemas
from app.domain import submission_status as SS
from app.routers.confirmations import confirm_task_card
from app.routers.issues import (
    OwnerConfirmOpinionRequest,
    SubmitOpinionRequest,
    owner_confirm_opinion,
    submit_opinion,
)
from app.services.escalation import escalate_card_to_issue
from tests.test_confirmation_card_coach_flow import _seed_card_coach_team, _submit
from tests.test_execution_submission_to_work_progress_flow import _make_session


def _card(db, submission_id: int) -> dict:
    submission = db.get(models.UpdateSubmission, submission_id)
    return json.loads(submission.human_result_json)["task_reports"][0]


def test_coach_decision_returns_to_pm_for_separate_final_confirmation():
    db = _make_session()
    team = _seed_card_coach_team(db)
    submission_id = _submit(db, team)
    submission = db.get(models.UpdateSubmission, submission_id)
    issue = escalate_card_to_issue(
        db=db,
        submission=submission,
        card_index=0,
        target="ceo",
        note="请教练决策",
        caller_username="owner",
        caller_name="项目负责人",
        project_id=team["project"].id,
        decision_by_username="企业教练",
    )
    db.commit()

    submit_opinion(
        issue.id,
        SubmitOpinionRequest(opinion="按计划继续推进"),
        current_user="coach",
        db=db,
    )
    assert db.get(models.Issue, issue.id).status == "待负责人确认"

    owner_confirm_opinion(
        issue.id,
        OwnerConfirmOpinionRequest(accepted=True, note="PM 已核对"),
        current_user="owner",
        db=db,
    )

    report = _card(db, submission_id)
    assert report["confirmation_status"] == "ceo_decided"
    assert report["ceo_operator"] == "coach"
    assert db.get(models.UpdateSubmission, submission_id).confirm_status != SS.S_CONFIRMED

    confirm_task_card(
        submission_id,
        0,
        schemas.ConfirmRequest(operator="owner"),
        current_user="owner",
        db=db,
    )
    assert _card(db, submission_id)["confirmation_status"] == "confirmed"
    assert db.get(models.UpdateSubmission, submission_id).confirm_status == SS.S_CONFIRMED
