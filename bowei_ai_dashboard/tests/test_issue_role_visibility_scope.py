from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "IssuesPage.tsx").read_text(encoding="utf-8")


def test_issue_visibility_uses_project_roles_and_current_flow():
    assert "['owner', 'coordinator', 'project_ceo']" in SOURCE
    assert "canViewAllProjectIssues" in SOURCE
    for status in ["待处理", "待协调", "待决策", "待负责人确认", "已解决", "已关闭"]:
        assert status in SOURCE
