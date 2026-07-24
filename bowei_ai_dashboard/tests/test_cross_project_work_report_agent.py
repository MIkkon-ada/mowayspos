from pathlib import Path

import pytest

from app.services.work_report_agent import _agent_prompt, build_work_report_draft, extract_work_report_agent


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


def test_agent_can_assign_generic_bugfix_to_candidate_task():
    candidates = [candidate(81, "AI升级计划", "开发并应用项目运营系统", "完成系统模块梳理与迭代")]

    def fake_llm(prompt: str, provider: str) -> dict:
        return {
            "task_reports": [
                {
                    "evidence": "这次修复了一个BUG",
                    "match_status": "matched",
                    "matched_subtask_id": 81,
                    "match_reason": "当前候选任务与系统迭代开发直接相关，BUG 修复属于该任务推进内容。",
                    "completed": "这次修复了一个BUG",
                    "achievements": [],
                    "subtask_issues": [],
                    "next_steps": [],
                    "status_update": "",
                }
            ]
        }

    card = extract_work_report_agent("这次修复了一个BUG", candidates, "deepseek", llm_call=fake_llm)["task_reports"][0]
    assert card["match_status"] == "matched"
    assert card["matched_subtask_id"] == 81
    assert card["matched_subtask_title"] == "完成系统模块梳理与迭代"
    assert card["completed"] == "这次修复了一个BUG"


def test_agent_returned_subtask_id_must_be_in_candidate_pool():
    candidates = [candidate(81, "AI升级计划", "开发并应用项目运营系统", "完成系统模块梳理与迭代")]

    def fake_llm(prompt: str, provider: str) -> dict:
        return {
            "task_reports": [
                {
                    "evidence": "这次修复了一个BUG",
                    "match_status": "matched",
                    "matched_subtask_id": 999,
                    "match_reason": "模型误选了候选池外的任务。",
                    "completed": "这次修复了一个BUG",
                    "achievements": [],
                    "subtask_issues": [],
                    "next_steps": [],
                    "status_update": "",
                }
            ]
        }

    card = extract_work_report_agent("这次修复了一个BUG", candidates, "deepseek", llm_call=fake_llm)["task_reports"][0]
    assert card["match_status"] == "unmatched"
    assert card["matched_subtask_id"] is None
    assert card["match_candidates"] == []


def test_single_candidate_is_matched_even_when_agent_is_overcautious():
    candidates = [candidate(81, "AI升级计划", "开发并应用项目运营系统", "完成系统模块梳理与迭代")]

    def fake_llm(prompt: str, provider: str) -> dict:
        return {
            "task_reports": [
                {
                    "evidence": "本周提交了一个BUG",
                    "match_status": "unmatched",
                    "matched_subtask_id": None,
                    "match_reason": "模型过度谨慎，没有选择唯一候选任务。",
                    "completed": "本周提交了一个BUG",
                    "achievements": [],
                    "subtask_issues": [],
                    "next_steps": [],
                    "status_update": "",
                }
            ]
        }

    card = extract_work_report_agent("本周提交了一个BUG", candidates, "deepseek", llm_call=fake_llm)["task_reports"][0]
    assert card["match_status"] == "matched"
    assert card["matched_subtask_id"] == 81
    assert card["matched_subtask_title"] == "完成系统模块梳理与迭代"


def test_followup_plan_fragment_stays_with_previous_matched_task():
    candidates = [
        candidate(81, "AI升级计划", "开发并应用项目运营系统", "完成系统模块梳理与迭代"),
        candidate(91, "AI升级计划", "开发并应用项目运营系统", "导入系统运行"),
        candidate(101, "AI升级计划", "开发并应用项目运营系统", "梳理流程"),
    ]

    def fake_llm(prompt: str, provider: str) -> dict:
        assert "先按真实任务聚合" in prompt
        return {
            "task_reports": [
                {
                    "evidence": "本周完成了系统模块梳理",
                    "match_status": "matched",
                    "matched_subtask_id": 81,
                    "match_reason": "明确命中系统模块梳理任务。",
                    "completed": "本周完成了系统模块梳理",
                    "achievements": [],
                    "subtask_issues": [],
                    "next_steps": [],
                    "status_update": "",
                },
                {
                    "evidence": "下一周计划继续做最小POS",
                    "match_status": "needs_confirmation",
                    "matched_subtask_id": None,
                    "match_candidate_ids": [91, 101],
                    "match_reason": "最小POS可能关联多个候选。",
                    "completed": "",
                    "achievements": [],
                    "subtask_issues": [],
                    "next_steps": ["继续做最小POS"],
                    "status_update": "",
                },
            ]
        }

    result = extract_work_report_agent(
        "本周完成了系统模块梳理，下一周计划继续做最小POS",
        candidates,
        "deepseek",
        llm_call=fake_llm,
    )

    assert len(result["task_reports"]) == 1
    card = result["task_reports"][0]
    assert card["match_status"] == "matched"
    assert card["matched_subtask_id"] == 81
    assert card["completed"] == "本周完成了系统模块梳理"
    assert card["next_steps"] == ["继续做最小POS"]
    assert card["evidence"] == ["本周完成了系统模块梳理", "下一周计划继续做最小POS"]


def test_agent_groups_a_submission_and_rewrites_business_progress_fields():
    candidates = [candidate(81, "AI升级计划", "开发并应用项目运营系统", "完成系统模块梳理与迭代")]
    text = "本周完成了系统模块梳理，下一周计划继续做最小POS"

    def fake_llm(prompt: str, provider: str) -> dict:
        return {
            "task_reports": [
                {
                    "evidence": ["本周完成了系统模块梳理", "下一周计划继续做最小POS"],
                    "match_status": "matched",
                    "matched_subtask_id": 81,
                    "match_reason": "两段内容都在同一项系统迭代任务的连续进展中。",
                    "completed": "完成系统模块梳理，明确后续迭代范围。",
                    "achievements": [],
                    "subtask_issues": [],
                    "next_steps": ["推进最小POS方案开发与验证。"],
                    "status_update": "任务持续推进中。",
                }
            ]
        }

    result = extract_work_report_agent(text, candidates, "deepseek", llm_call=fake_llm)

    assert len(result["task_reports"]) == 1
    card = result["task_reports"][0]
    assert card["matched_subtask_id"] == 81
    assert card["evidence"] == ["本周完成了系统模块梳理", "下一周计划继续做最小POS"]
    assert card["completed"] == "完成系统模块梳理，明确后续迭代范围。"
    assert card["next_steps"] == ["推进最小POS方案开发与验证。"]
    assert card["status_update"] == "任务持续推进中。"


def test_agent_prompt_requires_whole_submission_grouping_and_business_summaries():
    prompt = _agent_prompt("完成系统梳理，继续做最小POS", [candidate(81, "AI升级计划", "系统建设", "系统模块梳理")])

    assert "完整理解这一次提交" in prompt
    assert "按真实任务聚合" in prompt
    assert "业务化归纳" in prompt
    assert '"evidence":["原文逐字片段"]' in prompt


def test_legacy_fragments_response_no_longer_uses_fixed_title_matching():
    candidates = [candidate(81, "AI升级计划", "开发并应用项目运营系统", "完成系统模块梳理与迭代")]

    def fake_llm(prompt: str, provider: str) -> dict:
        return {
            "fragments": [
                {
                    "evidence": "这次修复了一个BUG",
                    "completed": "这次修复了一个BUG",
                    "achievements": [],
                    "subtask_issues": [],
                    "next_steps": [],
                    "status_update": "",
                }
            ]
        }

    card = extract_work_report_agent("这次修复了一个BUG", candidates, "deepseek", llm_call=fake_llm)["task_reports"][0]
    assert card["match_status"] == "matched"
    assert card["matched_subtask_id"] == 81
    assert card["matched_subtask_title"] == "完成系统模块梳理与迭代"


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
