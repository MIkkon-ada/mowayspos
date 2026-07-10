from __future__ import annotations

from types import SimpleNamespace

from app.schemas import IssuePayload


def _issue_type_module():
    try:
        from app.domain import issue_type as IT
    except Exception as exc:  # pragma: no cover - intentional RED state for TDD
        raise AssertionError(f"issue_type helper missing or unusable: {exc}") from exc
    return IT


def test_issue_type_normalize_and_labels():
    IT = _issue_type_module()

    assert IT.normalize("问题") == "issue"
    assert IT.normalize("普通问题") == "issue"
    assert IT.normalize("issue") == "issue"
    assert IT.normalize("problem") == "issue"
    assert IT.normalize("风险") == "risk"
    assert IT.normalize("risk") == "risk"
    assert IT.normalize("协调") == "coordination"
    assert IT.normalize("协调事项") == "coordination"
    assert IT.normalize("coordination") == "coordination"
    assert IT.normalize("决策") == "decision"
    assert IT.normalize("决策事项") == "decision"
    assert IT.normalize("需决策") == "decision"
    assert IT.normalize("needs_decision") == "decision"
    assert IT.normalize("decision") == "decision"
    assert IT.normalize(None) == "unknown"
    assert IT.normalize("") == "unknown"
    assert IT.label("decision") == "决策事项"
    assert IT.label("决策") == "决策事项"
    assert "决策" in IT.aliases_for("decision")
    assert "needs_decision" in IT.aliases_for("decision")


def test_issue_payload_issue_type_can_be_normalized_to_standard_key():
    IT = _issue_type_module()

    payload = IssuePayload(project_id=1, description="示例问题", issue_type="决策")
    assert IT.normalize(payload.issue_type) == "decision"
    payload2 = IssuePayload(project_id=1, description="示例问题", issue_type="问题")
    assert IT.normalize(payload2.issue_type) == "issue"


def test_issue_type_filter_matches_decision_aliases_without_database():
    from app.routers.issues import _issue_type_matches_filter

    decision_row = SimpleNamespace(issue_type="需决策", need_decision_by="")
    english_row = SimpleNamespace(issue_type="decision", need_decision_by="")
    issue_row = SimpleNamespace(issue_type="问题", need_decision_by="")

    assert _issue_type_matches_filter(decision_row, "决策")
    assert _issue_type_matches_filter(english_row, "decision")
    assert not _issue_type_matches_filter(issue_row, "决策")
