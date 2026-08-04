from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src"
LIST = (ROOT / "pages" / "IssuesPage.tsx").read_text(encoding="utf-8")
DETAIL = (ROOT / "pages" / "IssueDetailPage.tsx").read_text(encoding="utf-8")


def test_project_issue_list_has_current_flow_and_project_selection():
    assert "parseProjectId" in LIST
    assert "ISSUE_FLOW" in LIST
    assert "navigate(`/work/issues/${item.id}?projectId=${projectId}`)" in LIST
    for status in ["待处理", "待协调", "待决策", "待负责人确认", "已解决", "已关闭"]:
        assert status in LIST


def test_issue_detail_owns_authorized_transitions():
    for api_call in ["assignIssueHelper", "requestIssueCeo", "resolveIssue", "closeIssue"]:
        assert api_call in DETAIL
    for handler in ["doAssignHelper", "doRequestCeo", "doResolve", "doClose"]:
        assert handler in DETAIL
