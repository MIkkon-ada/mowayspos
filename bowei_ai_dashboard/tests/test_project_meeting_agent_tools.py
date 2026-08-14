from __future__ import annotations

import pytest

from app.services.project_meeting_agent_tools import AgentToolError, ProjectMeetingAgentTools


@pytest.fixture()
def snapshot() -> dict:
    return {
        "project_id": 7,
        "project": {"id": 7, "name": "AI Upgrade", "status": "active"},
        "members": [{"person_id": 1, "name": "Owner", "role": "owner"}],
        "history": {"is_first_meeting": True, "previous_meeting_ids": []},
        "recent_progress": [
            {
                "key_task_id": 20,
                "execution_schedule_id": 30,
                "content": "Half done",
                "actual_output": "",
                "status": "in_progress",
                "updated_at": "2026-08-14T10:00:00",
            }
        ],
        "previous_meetings": [],
        "workstreams": [
            {
                "id": 10,
                "key_task": "Delivery stream",
                "status": "in_progress",
                "key_tasks": [
                    {
                        "id": 20,
                        "title": "Weekly delivery",
                        "status": "in_progress",
                        "execution_schedules": [
                            {"id": 30, "title": "Finish acceptance checklist", "status": "in_progress"}
                        ],
                    }
                ],
            }
        ],
    }


def test_search_plan_nodes_returns_key_task_and_execution_schedule_ids(snapshot: dict):
    result = ProjectMeetingAgentTools(snapshot).execute(
        "search_plan_nodes", {"project_id": 7, "query": "acceptance checklist"}
    )

    assert result["candidates"] == [
        {
            "workstream_id": 10,
            "workstream_name": "Delivery stream",
            "workstream_status": "in_progress",
            "key_task_id": 20,
            "key_task_name": "Weekly delivery",
            "key_task_status": "in_progress",
            "execution_schedule_ids": [30],
            "execution_schedules": [
                {"id": 30, "title": "Finish acceptance checklist", "status": "in_progress"}
            ],
        }
    ]


def test_first_meeting_has_no_previous_meetings(snapshot: dict):
    result = ProjectMeetingAgentTools(snapshot).execute("get_previous_meetings", {"project_id": 7})

    assert result == {"is_first_meeting": True, "meetings": []}


def test_previous_meeting_limit_is_capped_at_five(snapshot: dict):
    snapshot["history"] = {"is_first_meeting": False, "previous_meeting_ids": [1, 2, 3, 4, 5, 6]}
    snapshot["previous_meetings"] = [{"meeting_id": index} for index in range(1, 7)]

    result = ProjectMeetingAgentTools(snapshot).execute("get_previous_meetings", {"project_id": 7, "limit": 99})

    assert result["is_first_meeting"] is False
    assert [item["meeting_id"] for item in result["meetings"]] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("name, arguments, message", [
    ("get_project_profile", {"project_id": 8}, "project boundary"),
    ("not_a_tool", {"project_id": 7}, "unknown tool"),
])
def test_execute_rejects_cross_project_and_unknown_tools(snapshot: dict, name: str, arguments: dict, message: str):
    with pytest.raises(AgentToolError, match=message):
        ProjectMeetingAgentTools(snapshot).execute(name, arguments)


def test_node_and_progress_filters_stay_inside_frozen_project_boundary(snapshot: dict):
    tools = ProjectMeetingAgentTools(snapshot)

    node = tools.execute("get_plan_node_detail", {"project_id": 7, "execution_schedule_id": 30})
    progress = tools.execute("get_recent_progress", {"project_id": 7, "execution_schedule_id": 30})

    assert node["workstream_id"] == 10
    assert node["key_task_id"] == 20
    assert progress["items"] == [snapshot["recent_progress"][0]]
    with pytest.raises(AgentToolError, match="not found"):
        tools.execute("get_plan_node_detail", {"project_id": 7, "execution_schedule_id": 31})
    assert tools.execute("get_recent_progress", {"project_id": 7, "execution_schedule_id": 31}) == {"items": []}


def test_plan_node_detail_preserves_parent_relationship_for_each_node_kind(snapshot: dict):
    tools = ProjectMeetingAgentTools(snapshot)

    workstream = tools.execute("get_plan_node_detail", {"project_id": 7, "workstream_id": 10})
    key_task = tools.execute("get_plan_node_detail", {"project_id": 7, "key_task_id": 20})

    assert workstream["node_type"] == "workstream"
    assert workstream["key_task"] is None
    assert key_task["node_type"] == "key_task"
    assert key_task["workstream_id"] == 10
    assert key_task["key_task_id"] == 20
