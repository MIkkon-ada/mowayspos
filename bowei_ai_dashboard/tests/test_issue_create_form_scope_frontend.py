from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _source(path: str) -> str:
    return (ROOT / "frontend" / "src" / path).read_text(encoding="utf-8")


def test_issue_create_form_keeps_only_reporter_inputs_and_safe_defaults():
    source = _source("pages/IssuesPage.tsx")
    modal = source[source.index("function AddIssueModal"):]
    assert "description" in modal
    assert "related_task_id" in modal and "related_subtask_id" in modal
    assert "expected_resolve_time" in modal
    assert "issue_type: '问题'" in modal
    assert "priority: '中'" in modal
    assert "status: '待处理'" in modal


def test_issue_list_uses_current_flow_without_manual_status_control():
    source = _source("pages/IssuesPage.tsx")
    assert "ISSUE_FLOW" in source
    for status in ["待处理", "待协调", "待决策", "待负责人确认", "已解决", "已关闭"]:
        assert status in source
    assert "status_select" not in source.lower()


def test_issue_api_exposes_supported_create_fields_and_actions():
    source = _source("api/issues.ts")
    for field in ["status?: string", "source_type?: string", "assignIssueHelper", "requestIssueCeo"]:
        assert field in source
