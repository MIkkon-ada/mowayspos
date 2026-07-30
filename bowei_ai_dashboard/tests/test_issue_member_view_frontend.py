from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "IssuesPage.tsx").read_text(encoding="utf-8")
DETAIL = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "IssueDetailPage.tsx").read_text(encoding="utf-8")


def test_member_and_management_visibility_scopes_are_explicit():
    assert "hasAnyManagementRole" in SOURCE
    assert "canViewAllProjectIssues" in SOURCE
    assert "isMemberIssueView" in SOURCE
    assert "memberFilteredIssues" in SOURCE


def test_issue_actions_are_owned_by_the_detail_view():
    assert "canManageIssues" in DETAIL
    for action in ["doAssignHelper", "doRequestCeo", "doResolve", "doClose"]:
        assert action in DETAIL


def test_issue_list_navigates_to_detail_instead_of_embedding_write_actions():
    assert "navigate(`/work/issues/${item.id}?projectId=${projectId}`)" in SOURCE
