import json

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.domain import submission_status as SS
from app.routers import confirmations
from tests.test_confirmation_card_coordinator_flow import _make_card_submission
from tests.test_confirmation_card_coach_flow import _seed_card_coach_team
from tests.test_submission_submitter_identity_flow import _make_session, _seed_team, _submission


def test_router_reexports_confirmation_review_helpers():
    from app.services import confirmation_review_workflow as workflow

    assert confirmations._load_submission is workflow.load_submission
    assert confirmations._is_submission_submitter is workflow.is_submission_submitter
    assert confirmations._submission_project_id is workflow.submission_project_id


def test_submission_review_commands_own_state_transitions_and_submitter_identity():
    from app.services import confirmation_review_workflow as workflow

    db = _make_session()
    team = _seed_team(db)

    saved = _submission(
        db,
        submitter=team["submitter"].name,
        submitter_id=team["submitter"].id,
        status=SS.S_PENDING_OWNER,
    )
    saved_result = workflow.save_submission_review(
        submission_id=saved.id,
        payload=schemas.ConfirmationSaveRequest(human_result={"task_reports": []}),
        current_user="owner",
        db=db,
    )
    assert saved_result["submission"]["confirm_status"] == SS.S_NEEDS_REVISION

    returned = _submission(
        db,
        submitter=team["submitter"].name,
        submitter_id=team["submitter"].id,
        status=SS.S_PENDING_OWNER,
    )
    returned_result = workflow.return_submission_to_submitter(
        submission_id=returned.id,
        payload=schemas.RejectRequest(reason="请补充", operator="owner"),
        current_user="owner",
        db=db,
    )
    assert returned_result["submission"]["confirm_status"] == SS.S_RETURNED

    resubmitted = workflow.resubmit_submission(
        submission_id=returned.id,
        payload=schemas.ResubmitRequest(supplement_note="已补充"),
        current_user="submitter_account",
        db=db,
    )
    assert resubmitted["submission"]["confirm_status"] == SS.S_PENDING_OWNER

    withdrawn = _submission(
        db,
        submitter=team["submitter"].name,
        submitter_id=team["submitter"].id,
        status=SS.S_PENDING_OWNER,
    )
    assert workflow.withdraw_submission(
        submission_id=withdrawn.id,
        current_user="submitter_account",
        db=db,
    )["submission"]["confirm_status"] == SS.S_WITHDRAWN

    final_rejected = _submission(
        db,
        submitter=team["submitter"].name,
        submitter_id=team["submitter"].id,
        status=SS.S_PENDING_OWNER,
    )
    assert workflow.reject_submission_finally(
        submission_id=final_rejected.id,
        payload=schemas.RejectRequest(reason="无效", operator="owner"),
        current_user="owner",
        db=db,
    )["submission"]["confirm_status"] == SS.S_PERMANENTLY_REJECTED

    marked = _submission(
        db,
        submitter=team["submitter"].name,
        submitter_id=team["submitter"].id,
        status=SS.S_PENDING_OWNER,
    )
    assert workflow.mark_submission_unrecognized(
        submission_id=marked.id,
        payload=schemas.RejectRequest(reason="需人工处理", operator="owner"),
        current_user="owner",
        db=db,
    )["submission"]["confirm_status"] == SS.S_NEEDS_REVISION

    assigned = _submission(
        db,
        submitter=team["submitter"].name,
        submitter_id=team["submitter"].id,
        status=SS.S_NEEDS_REVISION,
    )
    assigned_result = workflow.assign_submission_owner(
        submission_id=assigned.id,
        payload=schemas.AssignRequest(assignee="项目负责人", operator="owner"),
        current_user="owner",
        db=db,
    )
    assert assigned_result["submission"]["confirm_status"] == SS.S_PENDING_OWNER
    assert json.loads(assigned_result["submission"]["human_result_json"])["assigned_to"] == "项目负责人"

    identity_row = _submission(
        db,
        submitter=team["submitter"].name,
        submitter_id=team["submitter"].id,
        status=SS.S_RETURNED,
    )
    with pytest.raises(HTTPException) as exc_info:
        workflow.resubmit_submission(
            submission_id=identity_row.id,
            payload=schemas.ResubmitRequest(),
            current_user="other_account",
            db=db,
        )
    assert exc_info.value.status_code == 403


def test_submission_escalation_commands_keep_project_scoped_review_flow():
    from app.services import confirmation_review_workflow as workflow

    db = _make_session()
    team = _seed_team(db)
    row = _submission(
        db,
        submitter=team["submitter"].name,
        submitter_id=team["submitter"].id,
        status=SS.S_PENDING_OWNER,
    )

    transferred = workflow.transfer_submission_to_coordinator(
        submission_id=row.id,
        payload=schemas.WorkflowNoteRequest(note="请反馈", operator="owner"),
        current_user="owner",
        db=db,
    )
    assert transferred["submission"]["confirm_status"] == SS.S_WAITING_COORDINATOR

    feedback = workflow.coordinator_feedback(
        submission_id=row.id,
        payload=schemas.WorkflowNoteRequest(note="统筹意见", operator="coordinator"),
        current_user="coordinator",
        db=db,
    )
    assert feedback["submission"]["confirm_status"] == SS.S_COORDINATOR_GIVEN

    escalated = workflow.escalate_submission_to_coach(
        submission_id=row.id,
        payload=schemas.WorkflowNoteRequest(note="请批示", operator="owner"),
        current_user="owner",
        db=db,
    )
    assert escalated["submission"]["confirm_status"] == SS.S_WAITING_CEO

    decided = workflow.coach_decide_submission(
        submission_id=row.id,
        payload=schemas.WorkflowNoteRequest(note="同意", operator="coach"),
        current_user="coach",
        db=db,
    )
    assert decided["submission"]["confirm_status"] == SS.S_CEO_DECIDED

    denied = _submission(
        db,
        submitter=team["submitter"].name,
        submitter_id=team["submitter"].id,
        status=SS.S_WAITING_COORDINATOR,
    )
    with pytest.raises(HTTPException) as exc_info:
        workflow.coordinator_feedback(
            submission_id=denied.id,
            payload=schemas.WorkflowNoteRequest(note="越权", operator="coach"),
            current_user="coach",
            db=db,
        )
    assert exc_info.value.status_code == 403
    assert db.get(models.UpdateSubmission, denied.id).confirm_status == SS.S_WAITING_COORDINATOR


def test_card_review_commands_change_only_the_target_card():
    from app.services import confirmation_review_workflow as workflow

    db = _make_session()
    _seed_card_coach_team(db)
    row = _make_card_submission(db, statuses=("", ""))
    db.commit()

    transferred = workflow.transfer_task_card_to_coordinator(
        submission_id=row.id,
        card_index=0,
        payload=schemas.WorkflowNoteRequest(note="请统筹", operator="owner"),
        current_user="owner",
        db=db,
    )
    assert json.loads(transferred["submission"]["human_result_json"])["task_reports"][0]["confirmation_status"] == "transferred_to_coordinator"

    feedback = workflow.coordinator_feedback_task_card(
        submission_id=row.id,
        card_index=0,
        payload=schemas.WorkflowNoteRequest(note="可执行", operator="coordinator"),
        current_user="coordinator",
        db=db,
    )
    assert json.loads(feedback["submission"]["human_result_json"])["task_reports"][0]["confirmation_status"] == "coordinator_given"

    escalated = workflow.escalate_task_card_to_coach(
        submission_id=row.id,
        card_index=0,
        payload=schemas.WorkflowNoteRequest(note="请批示", operator="owner"),
        current_user="owner",
        db=db,
    )
    assert json.loads(escalated["submission"]["human_result_json"])["task_reports"][0]["confirmation_status"] == "pending_ceo_decision"

    decided = workflow.coach_decide_task_card(
        submission_id=row.id,
        card_index=0,
        payload=schemas.WorkflowNoteRequest(note="同意", operator="coach"),
        current_user="coach",
        db=db,
    )
    reports = json.loads(decided["submission"]["human_result_json"])["task_reports"]
    assert reports[0]["confirmation_status"] == "ceo_decided"
    assert not reports[1].get("confirmation_status")

    returned = workflow.reject_task_card_review(
        submission_id=row.id,
        card_index=0,
        payload=schemas.RejectRequest(reason="请补充依据", operator="owner"),
        current_user="owner",
        db=db,
    )
    assert json.loads(returned["submission"]["human_result_json"])["task_reports"][0]["confirmation_status"] == "returned"

    escalated_issue = workflow.escalate_task_card_to_issue(
        submission_id=row.id,
        card_index=1,
        target="coordinator",
        note="请统筹协调",
        operator="owner",
        current_user="owner",
        db=db,
    )
    issue = db.get(models.Issue, escalated_issue["issue_id"])
    assert issue is not None
    assert issue.source_submission_id == row.id
    assert issue.source_card_index == 1
    assert json.loads(escalated_issue["submission"]["human_result_json"])["task_reports"][1]["confirmation_status"] == "transferred_to_coordinator"

    with pytest.raises(HTTPException) as exc_info:
        workflow.escalate_task_card_to_coach(
            submission_id=row.id,
            card_index=0,
            payload=schemas.WorkflowNoteRequest(note="重复", operator="owner"),
            current_user="owner",
            db=db,
        )
    assert exc_info.value.status_code == 409
