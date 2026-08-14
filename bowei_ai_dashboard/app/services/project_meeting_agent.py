"""Bounded, tool-using Agent for project meeting Word documents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import ValidationError

from .project_meeting_agent_contracts import FinalEnvelope, MeetingAgentFinal, ToolCallEnvelope
from .project_meeting_agent_tools import AgentToolError, ProjectMeetingAgentTools


PROMPT_VERSION = "project-meeting-agent-v1"
MAX_AGENT_STEPS = 6


@dataclass(frozen=True)
class AgentModelResponse:
    text: str
    model_code: str
    invocation_log_id: int


@dataclass(frozen=True)
class MeetingAgentRunResult:
    final: MeetingAgentFinal
    trace: list[dict[str, Any]]
    raw_responses: list[str]
    invocation_log_ids: list[int]
    events: list[dict[str, Any]]
    model_code: str
    step_count: int


class MeetingAgentError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        trace: list[dict[str, Any]] | None = None,
        raw_responses: list[str] | None = None,
        invocation_log_ids: list[int] | None = None,
        events: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.trace = list(trace or [])
        self.raw_responses = list(raw_responses or [])
        self.invocation_log_ids = list(invocation_log_ids or [])
        self.events = list(events or [])


def _base_prompt(
    project_id: int,
    document_text: str,
    requested_meeting_type: str,
) -> str:
    tool_names = ", ".join(ProjectMeetingAgentTools.TOOL_NAMES)
    return f"""你是项目会议纪要分析 Agent，提示词版本：{PROMPT_VERSION}。

规则：
1. Word 正文是唯一的会议事实来源。用户选择的会议类型只是上下文，不能覆盖与 Word 正文矛盾的事实。
2. 项目工具返回的项目人员、计划、进展和历史会议仅用于上下文、检索和目标匹配，不能作为会议事实证据。
3. 每个非空的会议基本信息字段、每条事实和每个执行排期更新，都必须提供 Word 正文中的精确 evidence span（quote、char_start、char_end）。
4. 缺失信息保持空值，或写入 open_questions；不要猜测、补全或从项目上下文推断会议事实。
5. 只能建议 update_execution_schedule 或 create_execution_schedule；不能直接写入项目计划。
6. 每次回复必须是且只能是一个 JSON 对象：tool_call 或 final 信封。不要输出 Markdown、解释或 JSON 外文本。
7. 可用只读工具：{tool_names}。每个工具参数都必须含 project_id={project_id}。

项目 ID：{project_id}
用户选择的会议类型：{requested_meeting_type or "（未选择）"}
Word 正文（证据偏移以此文本为准）：
{document_text}
"""


def _parse_envelope(text: str) -> ToolCallEnvelope | FinalEnvelope:
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"response is not valid JSON: {exc.msg if isinstance(exc, json.JSONDecodeError) else exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("response JSON must be an object")
    response_type = payload.get("type")
    try:
        if response_type == "tool_call":
            return ToolCallEnvelope.model_validate(payload)
        if response_type == "final":
            return FinalEnvelope.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"response does not match {response_type} envelope: {exc}") from exc
    raise ValueError("response type must be tool_call or final")


def _emit(
    events: list[dict[str, Any]],
    on_event: Callable[[dict[str, Any]], None] | None,
    event: dict[str, Any],
) -> None:
    events.append(event)
    if on_event is not None:
        on_event(event)


def run_project_meeting_agent(
    project_id: int,
    document_text: str,
    snapshot: dict[str, Any],
    tools: ProjectMeetingAgentTools,
    provider: Callable[[str], AgentModelResponse],
    requested_meeting_type: str = "",
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> MeetingAgentRunResult:
    """Run at most six model steps against the immutable project snapshot."""
    events: list[dict[str, Any]] = []
    if project_id != snapshot.get("project_id"):
        raise MeetingAgentError(
            "project_boundary",
            "project_id does not match frozen snapshot",
            events=events,
        )

    trace: list[dict[str, Any]] = []
    raw_responses: list[str] = []
    invocation_log_ids: list[int] = []
    seen_tool_calls: set[tuple[str, str]] = set()
    repair_used = False
    base_prompt = _base_prompt(project_id, document_text, requested_meeting_type)
    prompt = base_prompt

    for step in range(1, MAX_AGENT_STEPS + 1):
        try:
            response = provider(prompt)
        except Exception as exc:
            raise MeetingAgentError(
                "provider_error",
                f"provider invocation failed: {exc}",
                trace=trace,
                raw_responses=raw_responses,
                invocation_log_ids=invocation_log_ids,
                events=events,
            ) from exc
        if not isinstance(response, AgentModelResponse):
            raise MeetingAgentError(
                "provider_error",
                "provider must return AgentModelResponse",
                trace=trace,
                raw_responses=raw_responses,
                invocation_log_ids=invocation_log_ids,
                events=events,
            )
        raw_responses.append(response.text)
        invocation_log_ids.append(response.invocation_log_id)
        _emit(events, on_event, {
            "kind": "model_response",
            "step": step,
            "model_code": response.model_code,
            "invocation_log_id": response.invocation_log_id,
        })
        try:
            envelope = _parse_envelope(response.text)
        except ValueError as exc:
            if repair_used:
                raise MeetingAgentError(
                    "invalid_model_output",
                    "model response remained invalid after one repair request",
                    trace=trace,
                    raw_responses=raw_responses,
                    invocation_log_ids=invocation_log_ids,
                    events=events,
                ) from exc
            repair_used = True
            prompt = (
                f"{base_prompt}\n上一条模型回复不符合严格 JSON 信封，原因：{exc}。\n"
                f"无效回复：{response.text}\n请仅返回一个合法 tool_call 或 final JSON 对象。"
            )
            continue

        if isinstance(envelope, FinalEnvelope):
            _emit(events, on_event, {
                "kind": "final",
                "step": step,
                "model_code": response.model_code,
                "invocation_log_id": response.invocation_log_id,
            })
            return MeetingAgentRunResult(
                final=envelope.result,
                trace=trace,
                raw_responses=raw_responses,
                invocation_log_ids=invocation_log_ids,
                events=events,
                model_code=response.model_code,
                step_count=step,
            )

        signature = (envelope.tool, json.dumps(envelope.arguments, ensure_ascii=False, sort_keys=True))
        if signature in seen_tool_calls:
            raise MeetingAgentError(
                "repeated_tool_call",
                "model repeated an identical tool call",
                trace=trace,
                raw_responses=raw_responses,
                invocation_log_ids=invocation_log_ids,
                events=events,
            )
        seen_tool_calls.add(signature)
        try:
            observation = tools.execute(envelope.tool, envelope.arguments)
        except AgentToolError as exc:
            raise MeetingAgentError(
                "tool_error",
                str(exc),
                trace=trace,
                raw_responses=raw_responses,
                invocation_log_ids=invocation_log_ids,
                events=events,
            ) from exc
        trace.append({
            "step": step,
            "tool": envelope.tool,
            "arguments": envelope.arguments,
            "observation": observation,
            "model_code": response.model_code,
            "invocation_log_id": response.invocation_log_id,
        })
        _emit(events, on_event, {
            "kind": "tool_result",
            "step": step,
            "tool": envelope.tool,
            "arguments": envelope.arguments,
            "model_code": response.model_code,
            "invocation_log_id": response.invocation_log_id,
        })
        prompt = (
            f"{base_prompt}\n工具调用轨迹（仅项目上下文，不是会议事实证据）：\n"
            f"{json.dumps(trace, ensure_ascii=False)}\n请继续，仅返回一个合法 JSON 信封。"
        )

    raise MeetingAgentError(
        "step_limit_exceeded",
        f"agent exceeded {MAX_AGENT_STEPS} steps without a final envelope",
        trace=trace,
        raw_responses=raw_responses,
        invocation_log_ids=invocation_log_ids,
        events=events,
    )
