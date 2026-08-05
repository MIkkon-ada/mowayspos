from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "IssuesPage.tsx").read_text(encoding="utf-8")
DETAIL = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "IssueDetailPage.tsx").read_text(encoding="utf-8")


def test_member_and_management_visibility_scopes_are_explicit():
    assert "hasAnyManagementRole" in SOURCE
    assert "canViewAllProjectIssues" in SOURCE
    assert "isMemberIssueView" in SOURCE
    assert "memberFilteredIssues" in SOURCE


def test_management_and_member_scope_use_distinct_role_decisions():
    management_block = SOURCE[SOURCE.index("const hasAnyManagementRole"):SOURCE.index("const isMemberIssueView")]
    assert "currentUser?.is_tech_admin || currentUser?.is_ceo" in management_block
    assert "['owner', 'coordinator', 'project_ceo']" in management_block
    assert "Boolean(currentProject) && !canViewAllProjectIssues" in SOURCE


def test_member_filter_does_not_expose_management_owner_or_helper_filters():
    filter_block = SOURCE[SOURCE.index("const memberFilteredIssues"):SOURCE.index("function getMyRelationship")]
    assert "memberStatusFilter" in filter_block
    assert "keyword.trim().toLowerCase()" in filter_block
    assert "filterOwner" not in filter_block
    assert "filterHelper" not in filter_block


def test_issue_actions_are_owned_by_the_detail_view():
    assert "canManageIssues" in DETAIL
    for action in ["doAssignHelper", "doRequestCeo", "doResolve", "doClose"]:
        assert action in DETAIL


def test_issue_list_navigates_to_detail_instead_of_embedding_write_actions():
    assert "navigate(`/work/issues/${item.id}?projectId=${projectId}`)" in SOURCE


def test_issue_detail_write_actions_are_guarded_by_manage_permission():
    action_block = DETAIL[DETAIL.index("const canManageIssues"):DETAIL.index("const doClose")]
    assert "currentUser?.is_tech_admin" in action_block
    assert "roles.includes('owner')" in action_block
