"""Frozen, project-scoped read tools used by the project meeting Agent."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class AgentToolError(ValueError):
    """A tool request cannot be served from the frozen project snapshot."""


class ProjectMeetingAgentTools:
    """Read-only view over the context captured before an Agent run begins."""

    TOOL_NAMES = (
        "get_project_profile",
        "list_project_members",
        "search_plan_nodes",
        "get_plan_node_detail",
        "get_recent_progress",
        "get_previous_meetings",
    )

    def __init__(self, snapshot: dict[str, Any]):
        project_id = snapshot.get("project_id") if isinstance(snapshot, dict) else None
        if not isinstance(project_id, int) or isinstance(project_id, bool) or project_id <= 0:
            raise AgentToolError("snapshot project_id is required")
        self._snapshot = deepcopy(snapshot)
        self._project_id = project_id

    def execute(self, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        if name not in self.TOOL_NAMES:
            raise AgentToolError(f"unknown tool: {name}")
        args = arguments if isinstance(arguments, dict) else {}
        if args.get("project_id") != self._project_id:
            raise AgentToolError("project boundary violation")
        handler = getattr(self, f"_{name}")
        return deepcopy(handler(args))

    def _get_project_profile(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "project": self._snapshot.get("project", {}),
            "history": self._snapshot.get("history", {}),
        }

    def _list_project_members(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"members": self._snapshot.get("members", [])}

    @staticmethod
    def _matches(query: str, *values: str) -> bool:
        normalized = query.casefold().strip()
        text = " ".join(value for value in values if isinstance(value, str)).casefold()
        if not normalized:
            return True
        if normalized in text:
            return True
        tokens = {part for part in normalized.replace("_", " ").split() if part}
        value_tokens = {part for part in text.replace("_", " ").split() if part}
        return bool(tokens & value_tokens)

    def _search_plan_nodes(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query") or "")
        candidates: list[dict[str, Any]] = []
        for workstream in self._snapshot.get("workstreams", []):
            if not isinstance(workstream, dict):
                continue
            for key_task in workstream.get("key_tasks", []):
                if not isinstance(key_task, dict):
                    continue
                schedules = [item for item in key_task.get("execution_schedules", []) if isinstance(item, dict)]
                searchable = [
                    str(workstream.get("key_task") or ""),
                    str(key_task.get("title") or ""),
                    *(str(schedule.get("title") or "") for schedule in schedules),
                ]
                if not self._matches(query, *searchable):
                    continue
                candidates.append(
                    {
                        "workstream_id": workstream.get("id"),
                        "workstream_name": workstream.get("key_task", ""),
                        "workstream_status": workstream.get("status", ""),
                        "key_task_id": key_task.get("id"),
                        "key_task_name": key_task.get("title", ""),
                        "key_task_status": key_task.get("status", ""),
                        "execution_schedule_ids": [schedule.get("id") for schedule in schedules],
                        "execution_schedules": [
                            {"id": schedule.get("id"), "title": schedule.get("title", ""), "status": schedule.get("status", "")}
                            for schedule in schedules
                        ],
                    }
                )
                if len(candidates) == 10:
                    return {"candidates": candidates}
        return {"candidates": candidates}

    def _get_plan_node_detail(self, arguments: dict[str, Any]) -> dict[str, Any]:
        workstream_id = arguments.get("workstream_id")
        key_task_id = arguments.get("key_task_id")
        schedule_id = arguments.get("execution_schedule_id")
        if workstream_id is None and key_task_id is None and schedule_id is None:
            raise AgentToolError("plan node id is required")
        for workstream in self._snapshot.get("workstreams", []):
            if not isinstance(workstream, dict):
                continue
            if workstream_id is not None and workstream.get("id") != workstream_id:
                continue
            if key_task_id is None and schedule_id is None:
                return {
                    "node_type": "workstream",
                    "workstream_id": workstream.get("id"),
                    "workstream": workstream,
                    "key_task_id": None,
                    "key_task": None,
                    "execution_schedules": [],
                }
            for key_task in workstream.get("key_tasks", []):
                if not isinstance(key_task, dict):
                    continue
                if key_task_id is not None and key_task.get("id") != key_task_id:
                    continue
                schedules = [item for item in key_task.get("execution_schedules", []) if isinstance(item, dict)]
                matching_schedules = schedules
                if schedule_id is not None:
                    matching_schedules = [item for item in schedules if item.get("id") == schedule_id]
                    if not matching_schedules:
                        continue
                return {
                    "node_type": "execution_schedule" if schedule_id is not None else "key_task",
                    "workstream_id": workstream.get("id"),
                    "workstream": workstream,
                    "key_task_id": key_task.get("id"),
                    "key_task": key_task,
                    "execution_schedules": matching_schedules,
                }
        raise AgentToolError("plan node not found in project snapshot")

    def _get_recent_progress(self, arguments: dict[str, Any]) -> dict[str, Any]:
        key_task_id = arguments.get("key_task_id")
        schedule_id = arguments.get("execution_schedule_id")
        items = [
            item
            for item in self._snapshot.get("recent_progress", [])
            if isinstance(item, dict)
            and (key_task_id is None or item.get("key_task_id") == key_task_id)
            and (schedule_id is None or item.get("execution_schedule_id") == schedule_id)
        ]
        return {"items": items}

    def _get_previous_meetings(self, arguments: dict[str, Any]) -> dict[str, Any]:
        history = self._snapshot.get("history", {})
        if isinstance(history, dict) and history.get("is_first_meeting"):
            return {"is_first_meeting": True, "meetings": []}
        raw_limit = arguments.get("limit", 5)
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = 5
        limit = max(0, min(limit, 5))
        return {"is_first_meeting": False, "meetings": self._snapshot.get("previous_meetings", [])[:limit]}
