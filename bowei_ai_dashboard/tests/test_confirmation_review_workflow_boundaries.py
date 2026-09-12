import json

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.domain import submission_status as SS
from app.routers import confirmations
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
