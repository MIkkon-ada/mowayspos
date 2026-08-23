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
    assert '"content":"Action description","owner":"","tracker":"","due_date":""' in prompt
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
    }


def test_agent_strictly_rejects_non_standard_json_constants(snapshot: dict):
    for constant in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(ValueError, match=f"non-standard JSON constant: {constant}"):
            _parse_envelope(f'{{"type": {constant}}}')

    replies = iter([
        AgentModelResponse('{"type": NaN}', "fake-chat", 15),
        AgentModelResponse('{"type": -Infinity}', "fake-chat", 16),
    ])

    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(1, "document", snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))

    assert exc.value.code == "invalid_model_output"


def test_agent_repairs_one_invalid_json_response(snapshot: dict, document_text: str, valid_final: dict):
    replies = iter([AgentModelResponse("not-json", "fake-chat", 21), response({"type": "final", "result": valid_final}, 22)])

    result = run_project_meeting_agent(1, document_text, snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))

    assert result.invocation_log_ids == [21, 22]


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


def test_agent_rejects_a_second_invalid_response(snapshot: dict):
    replies = iter([AgentModelResponse("bad", "fake-chat", 41), AgentModelResponse("still-bad", "fake-chat", 42)])

    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(1, "document", snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))

    assert exc.value.code == "invalid_model_output"


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
