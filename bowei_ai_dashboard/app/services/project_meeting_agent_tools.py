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
        if set(arguments) != {"project_id", "queries"}:
            raise AgentToolError("search_plan_nodes requires exactly project_id and queries")
        queries = arguments.get("queries")
        if not isinstance(queries, list) or not queries:
            raise AgentToolError("search_plan_nodes queries must be a non-empty list")

        results: list[dict[str, Any]] = []
        seen_fact_ids: set[str] = set()
        for item in queries:
            if not isinstance(item, dict) or set(item) != {"fact_id", "query"}:
                raise AgentToolError("search_plan_nodes queries require exactly fact_id and query")
            fact_id = item.get("fact_id")
            query = item.get("query")
            if not self._is_fact_id(fact_id):
                raise AgentToolError("search_plan_nodes fact_id must use a nonzero F001-compatible form")
            if fact_id in seen_fact_ids:
                raise AgentToolError("search_plan_nodes queries must not contain duplicate fact_id values")
            if not isinstance(query, str) or not query.strip():
                raise AgentToolError("search_plan_nodes query must be a non-empty string")
            seen_fact_ids.add(fact_id)
            results.append({"fact_id": fact_id, "candidates": self._plan_candidates(query)})
        return {"results": results}

    @staticmethod
    def _is_fact_id(value: Any) -> bool:
        if not isinstance(value, str) or not value.startswith("F"):
            return False
        suffix = value[1:]
        return len(suffix) >= 3 and suffix.isdigit() and suffix.strip("0") != ""

    def _plan_candidates(self, query: str) -> list[dict[str, Any]]:
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
                        "target_type": "key_task",
                        "target_id": key_task.get("id"),
                        "title": key_task.get("title", ""),
                        "workstream_id": workstream.get("id"),
                        "workstream_name": workstream.get("key_task", ""),
                        "assignee": key_task.get("assignee", ""),
                        "status": key_task.get("status", ""),
                        "execution_schedules": [
                            {
                                "id": schedule.get("id"),
                                "title": schedule.get("title", ""),
                                "status": schedule.get("status", ""),
                            }
                            for schedule in schedules
                        ],
                    }
                )
                if len(candidates) == 10:
                    return candidates
        return candidates

    @staticmethod
    def _node_summary(node: dict[str, Any], *, title_field: str, assignee_field: str = "assignee") -> dict[str, Any]:
        """Return the small, stable subset needed for matching and baseline review."""
        return {
            "id": node.get("id"),
            "title": node.get(title_field, ""),
            "assignee": node.get(assignee_field, ""),
            "status": node.get("status", ""),
            "plan_time": node.get("plan_time") or node.get("due_date") or node.get("plan_month") or "",
            "completion_criteria": node.get("completion_criteria") or node.get("completion_standard") or "",
            "current_progress": node.get("progress_note", ""),
        }

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
                    "workstream": self._node_summary(
                        workstream,
                        title_field="key_task",
                        assignee_field="owner",
                    ),
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
                    "workstream": self._node_summary(
                        workstream,
                        title_field="key_task",
                        assignee_field="owner",
                    ),
                    "key_task_id": key_task.get("id"),
                    "key_task": self._node_summary(key_task, title_field="title"),
                    "execution_schedules": [
                        self._node_summary(schedule, title_field="title")
                        for schedule in matching_schedules
                    ],
                    "execution_context": deepcopy(key_task.get("execution_context", {})),
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
        key_tasks = [
            key_task
            for workstream in self._snapshot.get("workstreams", [])
            if isinstance(workstream, dict)
            for key_task in workstream.get("key_tasks", [])
            if isinstance(key_task, dict)
        ]
        if schedule_id is not None:
            owner = next(
                (
                    key_task
                    for key_task in key_tasks
                    if any(
                        isinstance(schedule, dict) and schedule.get("id") == schedule_id
                        for schedule in key_task.get("execution_schedules", [])
                    )
                ),
                None,
            )
            contexts = (
                [owner.get("execution_context", {})]
                if owner is not None and (key_task_id is None or owner.get("id") == key_task_id)
                else []
            )
        else:
            contexts = [
                key_task.get("execution_context", {})
                for key_task in key_tasks
                if key_task_id is None or key_task.get("id") == key_task_id
            ]
        return {
            "window": self._snapshot.get("execution_window"),
            "items": items,
            "confirmed_reports": [
                item
                for context in contexts
                if isinstance(context, dict)
                for item in context.get("confirmed_reports", [])
            ],
            "confirmed_events": [
                item
                for context in contexts
                if isinstance(context, dict)
                for item in context.get("confirmed_events", [])
            ],
        }

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
