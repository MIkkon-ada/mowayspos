from pathlib import Path

import pytest

from app.services.work_report_agent import build_work_report_draft


def candidate(subtask_id: int, project: str, key_task: str, title: str) -> dict:
    return {"project_id": subtask_id // 10, "project_name": project, "parent_task_id": subtask_id * 10,
            "parent_key_task": key_task, "subtask_id": subtask_id, "subtask_title": title,
            "status": "进行中", "assignee": "张三", "user_relation": "subtask_assignee",
            "completion_criteria": "完成验收", "plan_time": "2026-07"}


CANDIDATES = [candidate(11, "A项目", "增长交付", "A方案验收"),
              candidate(21, "B项目", "数据治理", "B数据清洗"),
              candidate(31, "C项目", "渠道建设", "C渠道复盘")]


def fragment(evidence: str, **values) -> dict:
    return {"evidence": evidence, "completed": values.get("completed", evidence),
            "achievements": values.get("achievements", []), "subtask_issues": values.get("subtask_issues", []),
            "next_steps": values.get("next_steps", []), "status_update": values.get("status_update", "")}


def test_candidate_pool_abc_only_outputs_mentioned_a_and_b():
    text = "A方案验收已完成初审。B数据清洗完成第一批。"
    result = build_work_report_draft(text, CANDIDATES, [fragment("A方案验收已完成初审"), fragment("B数据清洗完成第一批")])
    assert [card["matched_subtask_id"] for card in result["task_reports"]] == [11, 21]
    assert all(card["project_name"] != "C项目" for card in result["task_reports"])


def test_same_task_fragments_merge_into_one_card():
    text = "A方案验收已完成初审。A方案验收下一步安排终审。"
    result = build_work_report_draft(text, CANDIDATES, [fragment("A方案验收已完成初审", completed="完成初审"), fragment("A方案验收下一步安排终审", completed="", next_steps=["安排终审"])])
    assert len(result["task_reports"]) == 1
    assert result["task_reports"][0]["completed"] == "A方案验收已完成初审"
    assert result["task_reports"][0]["next_steps"] == ["安排终审"]
    assert result["task_reports"][0]["evidence"] == ["A方案验收已完成初审", "A方案验收下一步安排终审"]


def test_similar_candidates_require_confirmation_without_first_choice():
    candidates = [candidate(41, "客户项目", "方案交付", "客户方案A"), candidate(42, "客户项目", "方案交付", "客户方案B")]
    card = build_work_report_draft("客户方案完成了初稿。", candidates, [fragment("客户方案完成了初稿")])["task_reports"][0]
    assert card["match_status"] == "needs_confirmation"
    assert card["matched_subtask_id"] is None
    assert {item["subtask_id"] for item in card["match_candidates"]} == {41, 42}


def test_no_reliable_candidate_is_unmatched():
    card = build_work_report_draft("完成了临时培训材料整理。", CANDIDATES, [fragment("完成了临时培训材料整理")])["task_reports"][0]
    assert card["match_status"] == "unmatched"
    assert card["matched_subtask_id"] is None
    assert card["match_candidates"] == []


def test_evidence_must_be_verbatim_from_transcript():
    with pytest.raises(ValueError, match="evidence"):
        build_work_report_draft("A方案验收已完成初审。", CANDIDATES, [fragment("用户没有说过的句子")])


def test_unmentioned_tasks_do_not_create_no_progress_or_delay_cards():
    cards = build_work_report_draft("A方案验收已完成初审。", CANDIDATES, [fragment("A方案验收已完成初审")])["task_reports"]
    assert len(cards) == 1
    assert "C渠道复盘" not in str(cards)
    assert "无进展" not in str(cards)
    assert "延期" not in str(cards)


def test_post_validation_removes_fields_without_explicit_evidence():
    evidence = "A项目投放复盘已完成"
    card = build_work_report_draft(evidence, [candidate(11, "A项目", "投放工作", "投放复盘")], [
        fragment(
            evidence,
            completed="完成A项目投放复盘",
            achievements=["形成复盘方法论"],
            subtask_issues=["待跟进风险"],
            next_steps=["继续推进并复盘"],
            status_update="进行中",
        )
    ])["task_reports"][0]
    assert card["completed"] == evidence
    assert card["achievements"] == []
    assert card["subtask_issues"] == []
    assert card["next_steps"] == []
    assert card["status_update"] == ""


def test_explicit_fields_remain_traceable_to_verbatim_evidence():
    evidence = "已完成方案初稿；成果是方案V1；问题是接口超时；下一步计划联调；任务状态调整为已完成"
    card = build_work_report_draft(evidence, [candidate(11, "A项目", "方案交付", "方案初稿")], [
        fragment(
            evidence,
            completed="已完成方案初稿",
            achievements=["方案V1"],
            subtask_issues=["接口超时"],
            next_steps=["联调"],
            status_update="已完成",
        )
    ])["task_reports"][0]
    assert card["completed"] in card["evidence"]
    for field in ("achievements", "subtask_issues", "next_steps"):
        assert all(value in evidence for value in card[field])
    assert card["status_update"] == "已完成"


def test_voice_context_route_keeps_member_scope_and_supports_no_project_id():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app" / "routers" / "updates.py").read_text(encoding="utf-8")
    assert "project_id: int | None = None" in source
    assert "models.SubTask.assignee == display_name" in source
    assert "models.Task.owner == display_name" in source
    assert 'd["project_name"]' in source
    assert 'd["subtask_id"]' in source
    assert "Never trust a client-supplied cross-project candidate pool" in source
    assert "get_voice_context(project_id=payload.project_id" in source


def test_project_scope_uses_agent_even_when_only_one_candidate_exists():
    root = Path(__file__).resolve().parents[1]
    router = (root / "app" / "routers" / "updates.py").read_text(encoding="utf-8")
    schemas = (root / "app" / "schemas.py").read_text(encoding="utf-8")
    assert "report_scope" in schemas
    assert "payload.report_scope in" in router
    assert '"all", "project"' in router
