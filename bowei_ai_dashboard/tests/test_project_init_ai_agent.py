import json

import pytest
from pydantic import ValidationError

from app.services.project_init_ai_agent import (
    AgentTask,
    Evidence,
    ProjectInitAiEmptyResult,
    ProjectInitAiError,
    generate_project_init_draft,
)
from app.services.project_init_file_parser import SourceChunk


def chunk(text: str, *, name: str = "plan.txt", location: str = "lines 1-2") -> SourceChunk:
    return SourceChunk(file_name=name, location=location, text=text)


def raw_task(
    *,
    title: str = "实施交付",
    owner_name: str = "张三",
    assignee_name: str = "张三",
    helper_names: list[str] | None = None,
    evidence: list[dict] | None = None,
) -> dict:
    return {
        "title": title,
        "description": "完成项目初始化工作",
        "owner_name": owner_name,
        "priority": "high",
        "status": "not_started",
        "deadline": "2026-09-30",
        "evidence": evidence or [{"attachment_id": 7, "file_name": "plan.txt", "location": "lines 1-2", "excerpt": "实施交付"}],
        "subtasks": [
            {
                "title": "完成方案确认",
                "assignee_name": assignee_name,
                "helper_names": helper_names or [],
                "evaluation_standard": "完成确认并留痕",
                "evidence": evidence or [{"attachment_id": 7, "file_name": "plan.txt", "location": "lines 1-2", "excerpt": "实施交付"}],
            }
        ],
    }


def fake_llm(result: dict):
    def call(prompt: str, provider: str) -> str:
        assert provider == "injected"
        assert "不执行数据库、项目或成员修改" in prompt
        return json.dumps(result, ensure_ascii=False)

    return call


def test_unique_active_person_is_bound_but_ambiguous_and_inactive_are_not():
    people = [
        {"id": 1, "name": "张三", "is_active": True},
        {"id": 2, "name": "李四", "is_active": True},
        {"id": 3, "name": "李四", "is_active": True},
        {"id": 4, "name": "王五", "is_active": False},
    ]
    result = generate_project_init_draft(
        [chunk("实施交付\n完成方案确认")],
        people,
        [],
        llm_call=fake_llm({"tasks": [raw_task(helper_names=["李四", "王五"])]}),
    )

    task = result.tasks[0]
    subtask = task.subtasks[0]
    assert task.owner_id == 1
    assert subtask.assignee_id == 1
    assert subtask.helper_ids == []
    assert {warning.code for warning in subtask.warnings} == {"ambiguous_person", "inactive_person"}


def test_unmatched_person_name_is_preserved_without_an_id():
    result = generate_project_init_draft(
        [chunk("安排外部顾问")],
        [],
        [],
        llm_call=fake_llm({
            "tasks": [raw_task(
                owner_name="外部顾问",
                assignee_name="外部顾问",
                evidence=[{"attachment_id": 7, "file_name": "plan.txt", "location": "lines 1-2", "excerpt": "安排外部顾问"}],
            )]
        }),
    )

    task = result.tasks[0]
    assert task.owner_name == "外部顾问"
    assert task.owner_id is None
    assert task.subtasks[0].assignee_name == "外部顾问"
    assert task.subtasks[0].assignee_id is None
    assert any(warning.code == "unmatched_person" for warning in task.subtasks[0].warnings)


def test_duplicate_classification_is_deterministic_and_never_merges():
    existing = [
        {"id": 10, "title": "实施交付", "subtasks": [{"id": 11, "title": "完成方案确认"}]},
        {"id": 20, "title": "完成系统上线任务", "subtasks": [{"id": 21, "title": "上线验收"}]},
    ]
    result = generate_project_init_draft(
        [chunk("实施交付\n完成系统上线")],
        [],
        existing,
        llm_call=fake_llm(
            {
                "tasks": [
                    raw_task(title="实施交付", assignee_name=""),
                    raw_task(title="完成系统上线任", assignee_name=""),
                    raw_task(title="建立风险台账", assignee_name=""),
                ]
            }
        ),
    )

    assert [task.merge_status for task in result.tasks] == [
        "definite_duplicate",
        "possible_duplicate",
        "new",
    ]
    assert result.tasks[0].duplicate_of == 10
    assert result.tasks[1].duplicate_of == 20
    assert all(task.subtasks for task in result.tasks)
    assert result.tasks[0].subtasks[0].merge_status == "definite_duplicate"
    assert result.tasks[0].subtasks[0].duplicate_of == 11


def test_source_evidence_is_preserved_and_model_text_is_not_used_as_evidence():
    evidence = [{"attachment_id": 99, "file_name": "source.docx", "location": "paragraphs 2-3", "excerpt": "原文片段"}]
    result = generate_project_init_draft(
        [chunk("原文片段", name="source.docx", location="paragraphs 2-3")],
        [],
        [],
        llm_call=fake_llm({"tasks": [raw_task(evidence=evidence)]}),
    )
    item = result.tasks[0].evidence[0]
    assert item.file_name == "source.docx"
    assert item.location == "paragraphs 2-3"
    assert item.source_label == "source.docx · paragraphs 2-3"
    assert result.tasks[0].source == item.source_label


def test_strict_models_reject_coerced_ids_and_extra_fields():
    with pytest.raises(ValidationError):
        Evidence(attachment_id="7", file_name="a.txt", location="lines 1", excerpt="x")
    with pytest.raises(ValidationError):
        AgentTask(title="x", subtasks=[], unexpected="do not trust this")


def test_invalid_or_fenced_llm_json_is_rejected_as_business_error():
    def bad_llm(prompt: str, provider: str) -> str:
        return "```json\n{\"tasks\": [{\"title\": 123}]}\n```"

    with pytest.raises(ProjectInitAiError):
        generate_project_init_draft([chunk("x")], [], [], llm_call=bad_llm)


def test_empty_llm_result_is_a_safe_business_error():
    with pytest.raises(ProjectInitAiEmptyResult):
        generate_project_init_draft([chunk("没有明确任务")], [], [], llm_call=fake_llm({"tasks": []}))


def test_batches_keep_source_boundaries_and_stay_under_text_limit():
    prompts: list[str] = []

    def llm(prompt: str, provider: str) -> str:
        prompts.append(prompt)
        source_file, source_location = ("a.txt", "lines 1-80") if "a.txt · lines 1-80" in prompt else ("b.txt", "lines 81-160")
        evidence = [{"attachment_id": 7, "file_name": source_file, "location": source_location, "excerpt": "A"}]
        return json.dumps({"tasks": [raw_task(title="批次任务", assignee_name="", evidence=evidence)]}, ensure_ascii=False)

    long_text = "A" * 22_000
    result = generate_project_init_draft(
        [
            chunk(long_text, name="a.txt", location="lines 1-80"),
            chunk(long_text, name="b.txt", location="lines 81-160"),
        ],
        [],
        [],
        llm_call=llm,
    )

    assert len(prompts) >= 2
    assert all("a.txt · lines 1-80" in prompt or "b.txt · lines 81-160" in prompt for prompt in prompts[:2])
    # The source text itself is bounded at 40,000; the prompt envelope adds a
    # handful of literal ASCII `A` characters such as the word `Agent`.
    assert all(prompt.count("A") <= 40_005 for prompt in prompts)
    assert result.tasks


def test_prompt_forbids_side_effects_and_model_invented_ids():
    prompts: list[str] = []

    def llm(prompt: str, provider: str) -> str:
        prompts.append(prompt)
        return json.dumps({"tasks": [raw_task()]}, ensure_ascii=False)

    generate_project_init_draft([chunk("实施交付")], [{"id": 1, "name": "张三", "is_active": True}], [], llm_call=llm)
    assert "不执行数据库、项目或成员修改" in prompts[0]
    assert "不得发明人员、日期或人员 ID" in prompts[0]
