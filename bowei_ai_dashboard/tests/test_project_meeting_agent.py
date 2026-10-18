from __future__ import annotations

import json

import pytest

from app.services.project_meeting_agent import (
    AgentModelResponse,
    MeetingAgentError,
    _base_prompt,
    _parse_envelope,
    run_project_meeting_agent,
)
from app.services.project_meeting_agent_tools import ProjectMeetingAgentTools


def response(payload: dict, call_id: int) -> AgentModelResponse:
    return AgentModelResponse(text=json.dumps(payload), model_code="fake-chat", invocation_log_id=call_id)


@pytest.fixture()
def snapshot() -> dict:
    return {
        "project_id": 1,
        "project": {"id": 1, "name": "AI Upgrade"},
        "members": [],
        "history": {"is_first_meeting": True, "previous_meeting_ids": []},
        "recent_progress": [],
        "previous_meetings": [],
        "workstreams": [
            {
                "id": 10,
                "key_task": "Delivery",
                "status": "in_progress",
                "key_tasks": [
                    {
                        "id": 20,
                        "title": "Meeting minutes workflow",
                        "status": "in_progress",
                        "execution_schedules": [{"id": 30, "title": "Draft agent", "status": "pending"}],
                    }
                ],
            }
        ],
    }


@pytest.fixture()
def document_text() -> str:
    return "Meeting date: 2026-07-27\nImprove meeting minutes workflow"


@pytest.fixture()
def valid_final(document_text: str) -> dict:
    quote = "2026-07-27"
    start = document_text.index(quote)
    return {
        "meeting_info": {
            "title": "",
            "meeting_date": quote,
            "meeting_type": "",
            "location": "",
            "host": "",
            "participants": [],
            "organizer": "",
            "copied_to": [],
        },
        "meeting_info_evidence": {"meeting_date": [{"quote": quote, "char_start": start, "char_end": start + len(quote)}]},
        "summary": "",
        "summary_evidence": [],
        "agenda_items": [],
        "decisions": [],
        "completed_items": [],
        "next_steps": [],
        "risks": [],
        "open_questions": [],
        "task_updates": [],
    }


def test_agent_executes_tool_then_returns_final(snapshot: dict, document_text: str, valid_final: dict):
    events = []
    replies = iter([
        response({"type": "tool_call", "tool": "search_plan_nodes", "arguments": {"project_id": 1, "queries": [{"fact_id": "F001", "query": "minutes"}]}}, 11),
        response({"type": "final", "result": valid_final}, 12),
    ])

    result = run_project_meeting_agent(
        project_id=1,
        document_text=document_text,
        snapshot=snapshot,
        tools=ProjectMeetingAgentTools(snapshot),
        provider=lambda prompt: next(replies),
        on_event=events.append,
    )

    assert result.final.meeting_info.meeting_date == "2026-07-27"
    assert result.invocation_log_ids == [11, 12]
    assert result.trace[0]["tool"] == "search_plan_nodes"
    assert result.trace[0]["model_code"] == "fake-chat"
    assert result.trace[0]["invocation_log_id"] == 11
    assert [event["kind"] for event in events] == ["model_response", "tool_result", "model_response", "final"]
    assert result.events == events


def test_agent_prompt_includes_the_exact_tool_and_final_envelope_shapes(document_text: str):
    prompt = _base_prompt(1, document_text)

    assert '{"type":"tool_call","tool":"get_project_profile","arguments":{"project_id":1}}' in prompt
    assert '{"type":"final","result":{' in prompt
    assert 'Do not use tool_call/tool_name/parameters/final wrapper keys.' in prompt
    assert '"meeting_date":[{"quote":"2026-07-27","char_start":0,"char_end":10}]' in prompt
    assert '"content":"Action description","topic":"","owner":"","tracker":"","due_date":"","source_note":""' in prompt
    assert '"prior_action_tracking":[]' in prompt
    assert 'Action-only facts may include owner, tracker, and due_date only when each value is explicitly stated in Word evidence.' in prompt
    assert '"action":"update_execution_schedule","target":{"project_id":1,"workstream_id":10,"key_task_id":20,"execution_schedule_id":30}' in prompt
    assert 'Do not put a fact-shaped action item in task_updates.' in prompt
    assert 'Write a non-empty summary when the Word has any agenda, decision, completion, risk, or action.' in prompt
    assert 'The Word label 整理人 maps only to meeting_info.organizer.' in prompt
    assert '"summary":"Brief factual summary grounded in Word","summary_evidence":[{"quote":"exact Word quote","char_start":0,"char_end":16}]' in prompt
    assert '"meeting_facts"' in prompt
    assert '"project_matches"' in prompt
    assert '"project_deltas"' in prompt
    assert '"proposed_changes"' in prompt
    assert '"fact_id":"F001","fact_type":"action_item"' in prompt
    assert '"raw_text":"正在推进"' in prompt
    assert '"source_type":"meeting_fact","source_fact_id":"F001","usage":"new"' in prompt
    assert '"match_id":"M001","fact_id":"F001"' in prompt
    assert '"delta_id":"D001","source_fact_id":"F001","source_match_id":"M001"' in prompt
    assert '"change_id":"C001","source_fact_id":"F001","source_match_id":"M001","source_delta_id":"D001"' in prompt
    assert 'Never put an ID string such as "F001" in unmatched_items or needs_confirmation.' in prompt
    assert 'Move the complete fact object out of meeting_facts before placing it in unmatched_items or needs_confirmation.' in prompt
    assert "Word-only Meeting Fact -> Project Match -> inference-only Delta -> confirmation-required Proposed Change" in prompt
    assert "Project baseline is not current meeting evidence" in prompt
    assert "Inference cannot create writable new values" in prompt
    assert "explicit field_sources" in prompt
    assert "confirmed_report" in prompt
    assert "confirmed_event" in prompt
    assert "project_baseline" in prompt
    assert "does not replace Word evidence" in prompt
    assert '"queries":[{"fact_id":"F001","query":"focused task title"}]' in prompt
    assert "用户选择的会议类型" not in prompt


def test_standard_minutes_prompt_asks_model_to_return_only_project_analysis(document_text: str):
    prompt = _base_prompt(
        1,
        document_text,
        standard_minutes=True,
        standard_fact_inventory=[
            {"fact_id": "F001", "fact_type": "discussion", "content": "Keep the workflow", "evidence": {"char_start": 0, "char_end": 17}},
            {"fact_id": "F002", "fact_type": "action_item", "content": "Publish the report", "evidence": {"char_start": 20, "char_end": 39}},
        ],
    )

    assert "标准 Word 已由服务端完整解析" in prompt
    assert "agenda_items、decisions、completed_items、next_steps、prior_action_tracking 留空" in prompt
    assert "每一条决议、上期进展和本周行动事实都提供一个 F 编号" in prompt
    assert 'F001 [discussion] span=0:17 Keep the workflow' in prompt
    assert 'F002 [action_item] span=20:39 Publish the report' in prompt


def test_standard_minutes_retries_until_every_source_fact_has_one_analysis_disposition():
    document = (
        "Meeting date: 2026-07-27\n"
        "Decision: Keep the workflow\n"
        "Action: Publish the weekly report\n"
        "Prior: Review the open item"
    )
    snapshot = {
        "project_id": 1,
        "standard_minutes": {
            "is_standard_minutes": True,
            "discussion_sections": [{"title": "Workflow", "points": ["Decision: Keep the workflow"]}],
            "current_action_items": [{"会议安排事项": "Action: Publish the weekly report"}],
            "prior_action_items": [{"上周事项": "Prior: Review the open item"}],
        },
    }
    quoted = [
        "Decision: Keep the workflow",
        "Action: Publish the weekly report",
        "Prior: Review the open item",
    ]
    fact_types = ["decision", "action_item", "progress"]
    complete_facts = [
        {"fact_id": f"F{index:03}", "fact_type": fact_type, "disposition": "needs_confirmation",
         "confidence": 0.9, "reason": "需确认项目关联"}
        for index, fact_type in enumerate(fact_types, 1)
    ]
    prompts: list[str] = []
    replies = iter([
        response({"facts": complete_facts[:-1]}, 301),
        response({"facts": complete_facts}, 302),
    ])

    result = run_project_meeting_agent(
        1,
        document,
        snapshot,
        ProjectMeetingAgentTools(snapshot),
        lambda prompt: (prompts.append(prompt), next(replies))[1],
    )

    assert result.invocation_log_ids == [301, 302]
    assert [fact.fact_id for fact in result.final.needs_confirmation] == ["F001", "F002", "F003"]
    assert "缺少事实编号" in prompts[1]


def test_standard_minutes_large_inventory_is_analyzed_in_bounded_batches():
    document = "\n".join(f"Discussion point {index}" for index in range(1, 10))
    snapshot = {
        "project_id": 1,
        "standard_minutes": {
            "is_standard_minutes": True,
            "discussion_sections": [{"title": "Discussion", "points": [f"Discussion point {i}" for i in range(1, 10)]}],
            "current_action_items": [],
            "prior_action_items": [],
        },
    }
    inventory_ids = [f"F{i:03}" for i in range(1, 10)]
    provider_calls = []
    call_id = 400
    provider_call_count = 0

    def provider(prompt: str) -> AgentModelResponse:
        nonlocal call_id, provider_call_count
        provider_calls.append(prompt)
        call_id += 1
        provider_call_count += 1
        batch_ids = inventory_ids[:8] if provider_call_count == 1 else inventory_ids[8:]
        return response({"facts": [
            {"fact_id": fact_id, "fact_type": "decision", "disposition": "needs_confirmation",
             "confidence": 0.8, "reason": "需确认项目关联"}
            for fact_id in batch_ids
        ]}, call_id)

    result = run_project_meeting_agent(
        1, document, snapshot, ProjectMeetingAgentTools(snapshot), provider, require_plan_lookup=True,
    )

    assert [fact.fact_id for fact in result.final.needs_confirmation] == inventory_ids
    assert len(result.trace) == 2
    assert [item["batch"] for item in result.trace] == [1, 2]
    assert result.step_count == 4
    assert [event["batch"] for event in result.events if event["kind"] == "model_response"] == [1, 2]
    assert '"F009"' not in provider_calls[0]
    assert '"F009"' in provider_calls[1]


def test_agent_retains_events_without_event_callback(snapshot: dict, document_text: str, valid_final: dict):
    result = run_project_meeting_agent(
        project_id=1,
        document_text=document_text,
        snapshot=snapshot,
        tools=ProjectMeetingAgentTools(snapshot),
        provider=lambda prompt: response({"type": "final", "result": valid_final}, 13),
    )

    assert [event["kind"] for event in result.events] == ["model_response", "final"]
    assert result.events[0]["invocation_log_id"] == 13


def test_agent_isolates_internal_events_from_callback_mutation(snapshot: dict, document_text: str, valid_final: dict):
    received_events = []

    def mutate_callback(event: dict) -> None:
        received_events.append(event)
        event["kind"] = "tampered"
        event["extra"] = "callback-only"

    result = run_project_meeting_agent(
        project_id=1,
        document_text=document_text,
        snapshot=snapshot,
        tools=ProjectMeetingAgentTools(snapshot),
        provider=lambda prompt: response({"type": "final", "result": valid_final}, 14),
        on_event=mutate_callback,
    )

    assert received_events[0]["kind"] == "tampered"
    assert result.events[0] == {
        "kind": "model_response",
        "step": 1,
        "model_code": "fake-chat",
        "invocation_log_id": 14,
        "finish_reason": None,
        "prompt_tokens": None,
        "completion_tokens": None,
    }


def test_agent_strictly_rejects_non_standard_json_constants(snapshot: dict):
    for constant in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(ValueError, match=f"non-standard JSON constant: {constant}"):
            _parse_envelope(f'{{"type": {constant}}}')

    replies = iter([
        AgentModelResponse('{"type": NaN}', "fake-chat", 15),
        AgentModelResponse('{"type": -Infinity}', "fake-chat", 16),
        AgentModelResponse('{"type": Infinity}', "fake-chat", 17),
        AgentModelResponse('{"type": NaN}', "fake-chat", 18),
        AgentModelResponse('{"type": -Infinity}', "fake-chat", 19),
    ])

    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(1, "document", snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))

    assert exc.value.code == "invalid_model_output"


def test_agent_repairs_one_invalid_json_response(snapshot: dict, document_text: str, valid_final: dict):
    replies = iter([AgentModelResponse("not-json", "fake-chat", 21), response({"type": "final", "result": valid_final}, 22)])

    result = run_project_meeting_agent(1, document_text, snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))

    assert result.invocation_log_ids == [21, 22]


def test_agent_repairs_a_second_invalid_response_within_a_bounded_budget(
    snapshot: dict, document_text: str, valid_final: dict,
):
    prompts: list[str] = []
    replies = iter([
        AgentModelResponse('{"type":"final","result":', "fake-chat", 201),
        AgentModelResponse('{"type":"final","result":', "fake-chat", 202),
        response({"type": "final", "result": valid_final}, 203),
    ])

    result = run_project_meeting_agent(
        1,
        document_text,
        snapshot,
        ProjectMeetingAgentTools(snapshot),
        lambda prompt: (prompts.append(prompt), next(replies))[1],
    )

    assert result.invocation_log_ids == [201, 202, 203]
    assert len(prompts) == 3
    assert "不要输出未闭合的 JSON" in prompts[2]


def test_agent_repair_after_plan_lookup_requires_final_without_another_tool_call(
    snapshot: dict,
    document_text: str,
    valid_final: dict,
):
    prompts: list[str] = []
    replies = iter([
        response(
            {
                "type": "tool_call",
                "tool": "search_plan_nodes",
                "arguments": {"project_id": 1, "queries": [{"fact_id": "F001", "query": "minutes"}]},
            },
            26,
        ),
        AgentModelResponse(
            json.dumps({"type": "final", "result": valid_final}) + " trailing text",
            "fake-chat",
            27,
        ),
        response({"type": "final", "result": valid_final}, 28),
    ])

    result = run_project_meeting_agent(
        1,
        document_text,
        snapshot,
        ProjectMeetingAgentTools(snapshot),
        lambda prompt: (prompts.append(prompt), next(replies))[1],
        require_plan_lookup=True,
    )

    assert result.invocation_log_ids == [26, 27, 28]
    assert len(result.trace) == 1
    assert "Return a final envelope only; do not call any tool." in prompts[2]
    assert '"tool": "search_plan_nodes"' in prompts[2]


def test_project_meeting_agent_requires_a_plan_search_before_final(snapshot: dict, document_text: str, valid_final: dict):
    prompts: list[str] = []
    replies = iter([
        response({"type": "final", "result": valid_final}, 23),
        response({"type": "tool_call", "tool": "search_plan_nodes", "arguments": {"project_id": 1, "queries": [{"fact_id": "F001", "query": "minutes"}]}}, 24),
        response({"type": "final", "result": valid_final}, 25),
    ])

    result = run_project_meeting_agent(
        1,
        document_text,
        snapshot,
        ProjectMeetingAgentTools(snapshot),
        lambda prompt: (prompts.append(prompt), next(replies))[1],
        require_plan_lookup=True,
    )

    assert result.invocation_log_ids == [23, 24, 25]
    assert result.trace[0]["tool"] == "search_plan_nodes"
    assert "must call search_plan_nodes before a final response" in prompts[1]
    assert "Plan lookup requirement is fulfilled" in prompts[2]


def test_agent_blocks_repeated_identical_tool_call(snapshot: dict):
    duplicate = {"type": "tool_call", "tool": "get_project_profile", "arguments": {"project_id": 1}}
    replies = iter([response(duplicate, 31), response(duplicate, 32)])

    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(1, "document", snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))

    assert exc.value.code == "repeated_tool_call"


def test_agent_stops_at_six_steps(snapshot: dict):
    replies = iter([
        response({"type": "tool_call", "tool": "search_plan_nodes", "arguments": {"project_id": 1, "queries": [{"fact_id": "F001", "query": str(index)}]}}, index)
        for index in range(1, 7)
    ])

    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(1, "document", snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))

    assert exc.value.code == "step_limit_exceeded"


def test_agent_reserves_the_last_step_for_a_final_after_five_tool_queries(snapshot: dict, document_text: str, valid_final: dict):
    prompts: list[str] = []
    replies = iter([
        response({"type": "tool_call", "tool": "search_plan_nodes", "arguments": {"project_id": 1, "queries": [{"fact_id": "F001", "query": str(index)}]}}, index)
        for index in range(1, 6)
    ] + [response({"type": "final", "result": valid_final}, 6)])

    result = run_project_meeting_agent(
        1,
        document_text,
        snapshot,
        ProjectMeetingAgentTools(snapshot),
        lambda prompt: (prompts.append(prompt), next(replies))[1],
    )

    assert result.step_count == 6
    assert "must return final" in prompts[-1]


def test_agent_rejects_responses_after_the_bounded_repair_budget(snapshot: dict):
    replies = iter([
        AgentModelResponse("bad", "fake-chat", 41),
        AgentModelResponse("still-bad", "fake-chat", 42),
        AgentModelResponse("bad-again", "fake-chat", 43),
        AgentModelResponse("last-bad", "fake-chat", 44),
        AgentModelResponse("final-bad", "fake-chat", 45),
    ])

    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(1, "document", snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))

    assert exc.value.code == "invalid_model_output"


def test_agent_reports_output_limit_when_the_final_retry_was_truncated(snapshot: dict):
    replies = iter([
        AgentModelResponse("bad", "fake-chat", 51),
        AgentModelResponse("still-bad", "fake-chat", 52),
        AgentModelResponse('{"type":"final","result":', "fake-chat", 53, finish_reason="length"),
        AgentModelResponse("still-truncated", "fake-chat", 54),
        AgentModelResponse("last-truncated", "fake-chat", 55),
    ])

    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(
            1, "document", snapshot, ProjectMeetingAgentTools(snapshot), lambda _prompt: next(replies),
        )

    assert exc.value.code == "truncated_model_output"


def test_agent_wraps_provider_exception_and_retains_events(snapshot: dict):
    replies = iter([
        response({"type": "tool_call", "tool": "get_project_profile", "arguments": {"project_id": 1}}, 51),
    ])

    def provider(prompt: str) -> AgentModelResponse:
        first = next(replies, None)
        if first is not None:
            return first
        raise RuntimeError("model service unavailable")

    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(1, "document", snapshot, ProjectMeetingAgentTools(snapshot), provider)

    assert exc.value.code == "provider_error"
    assert exc.value.invocation_log_ids == [51]
    assert exc.value.raw_responses == [json.dumps({"type": "tool_call", "tool": "get_project_profile", "arguments": {"project_id": 1}})]
    assert exc.value.trace[0]["tool"] == "get_project_profile"
    assert [event["kind"] for event in exc.value.events] == ["model_response", "tool_result"]


def test_agent_processes_seven_fact_queries_in_one_plan_lookup(snapshot: dict, document_text: str, valid_final: dict):
    queries = [{"fact_id": f"F00{index}", "query": "minutes"} for index in range(1, 8)]
    replies = iter([
        response(
            {
                "type": "tool_call",
                "tool": "search_plan_nodes",
                "arguments": {"project_id": 1, "queries": queries},
            },
            61,
        ),
        response({"type": "final", "result": valid_final}, 62),
    ])

    result = run_project_meeting_agent(
        1,
        document_text,
        snapshot,
        ProjectMeetingAgentTools(snapshot),
        lambda prompt: next(replies),
        require_plan_lookup=True,
    )

    assert result.step_count == 2
    assert len(result.trace) == 1
    assert result.trace[0]["arguments"]["queries"] == queries
    assert [item["fact_id"] for item in result.trace[0]["observation"]["results"]] == [
        query["fact_id"] for query in queries
    ]
