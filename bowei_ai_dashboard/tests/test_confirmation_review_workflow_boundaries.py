from app.routers import confirmations


def test_router_reexports_confirmation_review_helpers():
    from app.services import confirmation_review_workflow as workflow

    assert confirmations._load_submission is workflow.load_submission
    assert confirmations._is_submission_submitter is workflow.is_submission_submitter
    assert confirmations._submission_project_id is workflow.submission_project_id
