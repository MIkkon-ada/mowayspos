from app.routers import projects


def test_projects_router_reexports_close_workflow_helpers():
    from app.services import project_close_workflow as workflow

    assert projects._lock_project_for_close is workflow.lock_project_for_close
    assert projects._lock_close_request is workflow.lock_close_request
    assert projects._close_request_response is workflow.close_request_response
