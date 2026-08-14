from __future__ import annotations

import json

import pytest

from app.services.project_meeting_agent import (
    AgentModelResponse,
    MeetingAgentError,
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
        response({"type": "tool_call", "tool": "search_plan_nodes", "arguments": {"project_id": 1, "query": "minutes"}}, 11),
        response({"type": "final", "result": valid_final}, 12),
    ])

    result = run_project_meeting_agent(
        project_id=1,
        document_text=document_text,
        requested_meeting_type="project weekly meeting",
        snapshot=snapshot,
        tools=ProjectMeetingAgentTools(snapshot),
        provider=lambda prompt: next(replies),
        on_event=events.append,
    )

    assert result.final.meeting_info.meeting_date == "2026-07-27"
    assert result.invocation_log_ids == [11, 12]
    assert result.trace[0]["tool"] == "search_plan_nodes"
    assert [event["kind"] for event in events] == ["model_response", "tool_result", "model_response", "final"]


def test_agent_repairs_one_invalid_json_response(snapshot: dict, document_text: str, valid_final: dict):
    replies = iter([AgentModelResponse("not-json", "fake-chat", 21), response({"type": "final", "result": valid_final}, 22)])

    result = run_project_meeting_agent(1, document_text, snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))

    assert result.invocation_log_ids == [21, 22]


def test_agent_blocks_repeated_identical_tool_call(snapshot: dict):
    duplicate = {"type": "tool_call", "tool": "get_project_profile", "arguments": {"project_id": 1}}
    replies = iter([response(duplicate, 31), response(duplicate, 32)])

    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(1, "document", snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))

    assert exc.value.code == "repeated_tool_call"


def test_agent_stops_at_six_steps(snapshot: dict):
    replies = iter([
        response({"type": "tool_call", "tool": "search_plan_nodes", "arguments": {"project_id": 1, "query": str(index)}}, index)
        for index in range(1, 7)
    ])

    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(1, "document", snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))

    assert exc.value.code == "step_limit_exceeded"


def test_agent_rejects_a_second_invalid_response(snapshot: dict):
    replies = iter([AgentModelResponse("bad", "fake-chat", 41), AgentModelResponse("still-bad", "fake-chat", 42)])

    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(1, "document", snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))

    assert exc.value.code == "invalid_model_output"
