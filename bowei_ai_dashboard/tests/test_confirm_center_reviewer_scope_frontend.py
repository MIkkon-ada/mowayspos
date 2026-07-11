from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIRM_PAGE = REPO_ROOT / "frontend" / "src" / "pages" / "ConfirmPage.tsx"


def _confirm_page_source() -> str:
    return CONFIRM_PAGE.read_text(encoding="utf-8")


def test_confirm_page_reviewer_scope_not_only_current_project_capabilities():
    source = _confirm_page_source()

    assert "globalUserRoles" in source
    assert "REVIEWER_PROJECT_ROLES" in source
    for role in ("owner", "coordinator", "project_ceo"):
        assert role in source

    assert "currentCapabilities?.canConfirm" in source
    assert "currentCapabilities?.canCoordinate" in source
    assert "currentCapabilities?.canCeoDecide" in source
    assert "hasReviewerRoleInAnyProject" in source


def test_confirm_page_defaults_reviewers_to_pending_without_current_project():
    source = _confirm_page_source()

    assert "setViewMode((prev)" in source
    assert "isReviewer && prev === 'mine'" in source
    assert "return 'all'" in source
    assert "!isReviewer && prev === 'all'" in source
    assert "return 'mine'" in source


def test_confirm_page_supports_project_id_query_for_pending_scope():
    source = _confirm_page_source()

    assert "useSearchParams" in source
    assert "searchParams.get('projectId')" in source
    assert "urlProjectId" in source
    assert "pendingProjectId" in source
    assert "getPending(pendingProjectId, 'all')" in source


def test_confirm_page_keeps_mine_and_pending_data_sources_separate():
    source = _confirm_page_source()

    assert "viewMode === 'mine'" in source
    assert "fetchMyUpdates()" in source
    assert "getPending(pendingProjectId, 'all')" in source
    assert "itemProjectId" in source
    assert "fetchSubtasksByAssignee(submitter, itemProjectId)" in source


def test_confirm_page_does_not_add_backend_contract_or_route_concepts():
    source = _confirm_page_source()

    forbidden_terms = [
        "newConfirmationsRoute",
        "createReviewerScope",
        "confirm_center_scope",
        "reviewer_scope_id",
    ]
    for term in forbidden_terms:
        assert term not in source
