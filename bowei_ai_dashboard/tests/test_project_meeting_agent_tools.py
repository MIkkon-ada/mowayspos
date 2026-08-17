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
                        "assignee": "Owner",
                        "status": "in_progress",
                        "notes": "must not leak",
                        "execution_schedules": [
                            {
                                "id": 30,
                                "title": "Finish acceptance checklist",
                                "status": "in_progress",
                                "risk": "must not leak",
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_search_plan_nodes_returns_batch_candidates_in_fact_id_input_order(snapshot: dict):
    result = ProjectMeetingAgentTools(snapshot).execute(
        "search_plan_nodes",
        {
            "project_id": 7,
            "queries": [
                {"fact_id": "F002", "query": "not found"},
                {"fact_id": "F001", "query": "acceptance checklist"},
            ],
        },
    )

    assert result == {
        "results": [
            {"fact_id": "F002", "candidates": []},
            {
                "fact_id": "F001",
                "candidates": [
                    {
                        "target_type": "key_task",
                        "target_id": 20,
                        "title": "Weekly delivery",
                        "workstream_id": 10,
                        "workstream_name": "Delivery stream",
                        "assignee": "Owner",
                        "status": "in_progress",
                        "execution_schedules": [
                            {
                                "id": 30,
                                "title": "Finish acceptance checklist",
                                "status": "in_progress",
                            }
                        ],
                    }
                ],
            },
        ]
    }


@pytest.mark.parametrize("fact_id", ["F000", "F00", "FABC", "F001x"])
def test_search_plan_nodes_rejects_invalid_fact_id(snapshot: dict, fact_id: str):
    with pytest.raises(AgentToolError, match="fact_id"):
        ProjectMeetingAgentTools(snapshot).execute(
            "search_plan_nodes",
            {"project_id": 7, "queries": [{"fact_id": fact_id, "query": "acceptance"}]},
        )


def test_search_plan_nodes_requires_exact_batch_arguments(snapshot: dict):
    tools = ProjectMeetingAgentTools(snapshot)

    for arguments in (
        {"project_id": 7, "query": "acceptance"},
        {"project_id": 7, "queries": [], "extra": True},
        {"project_id": 7, "queries": [{"fact_id": "F001"}]},
    ):
        with pytest.raises(AgentToolError, match="search_plan_nodes"):
            tools.execute("search_plan_nodes", arguments)


def test_search_plan_nodes_rejects_empty_query_and_duplicate_fact_id(snapshot: dict):
    tools = ProjectMeetingAgentTools(snapshot)

    with pytest.raises(AgentToolError, match="query"):
        tools.execute(
            "search_plan_nodes",
            {"project_id": 7, "queries": [{"fact_id": "F001", "query": "   "}]},
        )

    with pytest.raises(AgentToolError, match="duplicate fact_id"):
        tools.execute(
            "search_plan_nodes",
            {
                "project_id": 7,
                "queries": [
                    {"fact_id": "F001", "query": "acceptance"},
                    {"fact_id": "F001", "query": "delivery"},
                ],
            },
        )


def test_search_plan_nodes_caps_each_fact_candidate_set_at_ten(snapshot: dict):
    for index in range(11, 22):
        snapshot["workstreams"].append(
            {
                "id": index,
                "key_task": f"Delivery stream {index}",
                "key_tasks": [
                    {
                        "id": index * 10,
                        "title": f"Acceptance item {index}",
                        "assignee": "Owner",
                        "status": "pending",
                        "execution_schedules": [],
                    }
                ],
            }
        )

    result = ProjectMeetingAgentTools(snapshot).execute(
        "search_plan_nodes",
        {"project_id": 7, "queries": [{"fact_id": "F001", "query": "acceptance"}]},
    )

    assert len(result["results"][0]["candidates"]) == 10


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
    ("list_project_members", {}, "project boundary"),
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


def test_plan_node_detail_returns_only_sanitized_matching_and_baseline_fields(snapshot: dict):
    workstream = snapshot["workstreams"][0]
    workstream.update(
        {
            "owner": "Program owner",
            "plan_time": "2026-Q3",
            "completion_standard": "Delivery accepted",
            "secret": "must not leak",
        }
    )
    key_task = workstream["key_tasks"][0]
    key_task.update(
        {
            "plan_time": "2026-08-20",
            "completion_criteria": "Checklist approved",
            "progress_note": "Half done",
            "secret": "must not leak",
        }
    )
    schedule = key_task["execution_schedules"][0]
    schedule.update(
        {
            "due_date": "2026-08-20",
            "assignee": "Owner",
            "completion_criteria": "Checklist approved",
            "progress_note": "Half done",
            "secret": "must not leak",
        }
    )

    detail = ProjectMeetingAgentTools(snapshot).execute(
        "get_plan_node_detail",
        {"project_id": 7, "execution_schedule_id": 30},
    )

    assert set(detail) == {
        "node_type",
        "workstream_id",
        "workstream",
        "key_task_id",
        "key_task",
        "execution_schedules",
    }
    assert set(detail["workstream"]) == {
        "id",
        "title",
        "assignee",
        "status",
        "plan_time",
        "completion_criteria",
        "current_progress",
    }
    assert set(detail["key_task"]) == set(detail["workstream"])
    assert set(detail["execution_schedules"][0]) == set(detail["workstream"])
    assert detail["execution_schedules"] == [
        {
            "id": 30,
            "title": "Finish acceptance checklist",
            "assignee": "Owner",
            "status": "in_progress",
            "plan_time": "2026-08-20",
            "completion_criteria": "Checklist approved",
            "current_progress": "Half done",
        }
    ]
    assert "secret" not in repr(detail)
    assert "notes" not in repr(detail)
    assert "risk" not in repr(detail)


def test_tools_freeze_input_snapshot_and_isolate_return_values(snapshot: dict):
    tools = ProjectMeetingAgentTools(snapshot)
    snapshot["project"]["name"] = "Mutated source"
    snapshot["members"][0]["name"] = "Mutated member"
    snapshot["workstreams"][0]["key_tasks"][0]["execution_schedules"][0]["title"] = "Mutated schedule"

    profile = tools.execute("get_project_profile", {"project_id": 7})
    members = tools.execute("list_project_members", {"project_id": 7})
    matches = tools.execute(
        "search_plan_nodes",
        {"project_id": 7, "queries": [{"fact_id": "F001", "query": "acceptance"}]},
    )
    profile["project"]["name"] = "Mutated return"
    members["members"][0]["name"] = "Mutated return"
    candidate = matches["results"][0]["candidates"][0]
    candidate["execution_schedules"][0]["title"] = "Mutated return"
    assert set(candidate) == {
        "target_type",
        "target_id",
        "title",
        "workstream_id",
        "workstream_name",
        "assignee",
        "status",
        "execution_schedules",
    }
    assert set(candidate["execution_schedules"][0]) == {"id", "title", "status"}

    assert tools.execute("get_project_profile", {"project_id": 7})["project"]["name"] == "AI Upgrade"
    assert tools.execute("list_project_members", {"project_id": 7})["members"][0]["name"] == "Owner"
    assert tools.execute(
        "search_plan_nodes",
        {"project_id": 7, "queries": [{"fact_id": "F001", "query": "acceptance"}]},
    )["results"][0]["candidates"][0]["execution_schedules"][0]["title"] == "Finish acceptance checklist"
