"""Current issue-flow contract: coordination and owner confirmation stay explicit."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _issues_source() -> str:
    return (ROOT.parent / "frontend" / "src" / "pages" / "IssuesPage.tsx").read_text(encoding="utf-8")


def test_issue_flow_has_the_six_supported_statuses():
    from app.domain import issue_flow as flow

    assert set(flow.ALL_STATUSES) == {
        "待处理", "待协调", "待决策", "待负责人确认", "已解决", "已关闭",
    }
    assert flow.normalize_status("协调") == flow.STATUS_COORDINATING
    assert flow.normalize_status("待协调") == flow.STATUS_COORDINATING


def test_issue_type_compatibility_is_preserved():
    from app.domain import issue_flow as flow
    from app.domain import issue_type

    assert flow.TYPE_COORDINATE == "待协调"
    assert issue_type.TYPE_COORDINATION == "coordination"


def test_issue_list_exposes_current_active_flow_stages():
    source = _issues_source()
    for status in ["待处理", "待协调", "待决策", "待负责人确认", "已解决"]:
        assert status in source
    assert "ISSUE_FLOW" in source


def test_issue_actions_keep_backend_transitions_authoritative():
    import inspect
    from app.routers import issues

    assert "STATUS_PENDING_DECISION" in inspect.getsource(issues.request_ceo)
    assert "STATUS_RESOLVED" in inspect.getsource(issues.resolve_issue)
    assert "STATUS_CLOSED" in inspect.getsource(issues.close_issue)


def test_issue_model_does_not_require_a_coordinating_column():
    from app.models import Issue

    assert "coordinating_status" not in {column.name for column in Issue.__table__.columns}
