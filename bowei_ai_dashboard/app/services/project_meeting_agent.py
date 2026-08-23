"""Bounded, tool-using Agent for project meeting Word documents."""

from __future__ import annotations

import json
from copy import deepcopy
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
) -> str:
    tool_names = ", ".join(ProjectMeetingAgentTools.TOOL_NAMES)
    protocol_examples = """
STRICT RESPONSE PROTOCOL (this overrides any older meeting-minutes JSON format):
- Return exactly one JSON object, with no Markdown fences and no explanatory text.
- A tool request must be exactly this shape:
  {"type":"tool_call","tool":"get_project_profile","arguments":{"project_id":1}}
- A completed analysis must be exactly this shape (include every listed result field):
  {"type":"final","result":{"meeting_info":{"title":"","meeting_date":"","meeting_type":"","location":"","host":"","participants":[],"organizer":"","copied_to":[]},"meeting_info_evidence":{},"summary":"","summary_evidence":[],"agenda_items":[],"decisions":[],"completed_items":[],"next_steps":[],"risks":[],"open_questions":[],"task_updates":[],"meeting_facts":[],"project_matches":[],"project_deltas":[],"proposed_changes":[],"unmatched_items":[],"needs_confirmation":[]}}
- meeting_info_evidence is a mapping from field name to an ARRAY of spans, never one span object:
  {"meeting_date":[{"quote":"2026-07-27","char_start":0,"char_end":10}]}
- Every item in agenda_items, decisions, completed_items, next_steps, risks, and open_questions has exactly this shape:
  {"content":"Owner and due date may be included in this sentence.","evidence":[{"quote":"exact Word quote","char_start":0,"char_end":16}],"confidence":0.9,"needs_confirmation":false}
- Do not add owner, due_date, assignee, deadline, or any other fields to a fact item.
- task_updates is only for a safely matched execution schedule and has exactly this shape:
  {"action":"update_execution_schedule","target":{"project_id":1,"workstream_id":10,"key_task_id":20,"execution_schedule_id":30},"before":{},"proposed":{},"evidence":[{"quote":"exact Word quote","char_start":0,"char_end":16}],"reason":"why the matching schedule changes","confidence":0.9,"needs_confirmation":false}
- Do not put a fact-shaped action item in task_updates. If a plan node or schedule is not safely matched, put that action in open_questions with needs_confirmation true.
- Write a non-empty summary when the Word has any agenda, decision, completion, risk, or action. Give summary_evidence as an array of exact Word spans.
- Summary example: {"summary":"Brief factual summary grounded in Word","summary_evidence":[{"quote":"exact Word quote","char_start":0,"char_end":16}]}
- The Word label 整理人 maps only to meeting_info.organizer. Do not substitute the host for organizer.
- Do not use tool_call/tool_name/parameters/final wrapper keys. Do not use any field names other than the two envelope shapes above.
- For every non-empty meeting field, fact, summary, or task update, include exact Word evidence with quote, char_start, and char_end.
- ANALYSIS LAYERS: Word-only Meeting Fact -> Project Match -> inference-only Delta -> confirmation-required Proposed Change.
- The four analysis arrays are mandatory analysis-layer data, not optional legacy fields. For every Word action, progress, completion, risk, output, scope item, or decision considered for project linkage, emit one F-series fact in exactly ONE of meeting_facts, unmatched_items, or needs_confirmation. Do not put a plain legacy MeetingFact object in those arrays.
- A fact with no safe project match goes to unmatched_items; an ambiguous match goes to needs_confirmation. Only a fact in meeting_facts may be referenced by a Project Match. An F ID must appear in only one of those three arrays.
- Never put an ID string such as "F001" in unmatched_items or needs_confirmation. Move the complete fact object out of meeting_facts before placing it in unmatched_items or needs_confirmation.
- Use these exact analysis object shapes (replace example values with evidence-grounded values; never omit required keys):
  meeting_facts item: {"fact_id":"F001","fact_type":"action_item","content":"Prepare customer shortlist","fields":{"status":{"value":"in_progress","raw_text":"正在推进","evidence":[{"quote":"正在推进","char_start":0,"char_end":4}],"provenance":{"source_type":"meeting_fact","source_fact_id":"F001","usage":"new"}}},"meeting_evidence":[{"quote":"正在推进","char_start":0,"char_end":4}],"confidence":0.9,"needs_confirmation":false}
  project_matches item: {"match_id":"M001","fact_id":"F001","target_type":"key_task","target_id":20,"workstream_id":10,"key_task_id":20,"confidence":0.9,"reasons":["title and intent match"],"project_evidence":[{"source_object":"key_task","field":"title","value":"Customer shortlist"}]}
  project_deltas item: {"delta_id":"D001","source_fact_id":"F001","source_match_id":"M001","delta_type":"PROGRESS_UPDATE","reasoning":"Word states current progress"}
  proposed_changes item: {"change_id":"C001","source_fact_id":"F001","source_match_id":"M001","source_delta_id":"D001","action":"update_execution_schedule","target":{"project_id":1,"workstream_id":10,"key_task_id":20,"execution_schedule_id":30},"before":{"status":"pending"},"proposed":{"status":"in_progress"},"field_sources":{"status":{"source_type":"meeting_fact","source_fact_id":"F001","usage":"new"}},"requires_confirmation":true}
- If a fact has no structured business field, emit fields as {} and do not create a Proposed Change. A Proposed Change is allowed only when every proposed field has field_sources and each meeting_fact field source names the same F-series fact containing that field-level Word evidence.
- Project baseline is not current meeting evidence. It may only support a project match or baseline comparison.
- Execution context returned by tools is frozen project_baseline. Treat confirmed_report and confirmed_event as context for matching, consistency checks, risk flags, and questions for the owner. This project_baseline does not replace Word evidence: it never replaces field-level Word evidence and must never be the sole source of a proposed writeback value.
- Inference cannot create writable new values. A Proposed Change must use explicit field_sources for every proposed field and requires_confirmation=true.
- Extract every Word-only Meeting Fact before matching. Then call search_plan_nodes once with one batch covering all facts:
  {"type":"tool_call","tool":"search_plan_nodes","arguments":{"project_id":1,"queries":[{"fact_id":"F001","query":"focused task title"}]}}
- Batch all fact queries in that single search call. Never omit a fact merely because the meeting has more than six facts; the six-step limit is a model-step limit, not a fact limit.
- Before final, call search_plan_nodes for the project using the batch protocol. Use its returned IDs for any task update; if no plan node matches an action, put that action in open_questions instead.

"""
    return f"""{protocol_examples}你是项目会议纪要分析 Agent，提示词版本：{PROMPT_VERSION}。

规则：
1. Word 正文是唯一的会议事实来源。
2. 项目工具返回的项目人员、计划、进展和历史会议仅用于上下文、检索和目标匹配，不能作为会议事实证据。
3. 每个非空的会议基本信息字段、每条事实和每个执行排期更新，都必须提供 Word 正文中的精确 evidence span（quote、char_start、char_end）。
4. 缺失信息保持空值，或写入 open_questions；不要猜测、补全或从项目上下文推断会议事实。
5. 只能建议 update_execution_schedule 或 create_execution_schedule；不能直接写入项目计划。
6. 每次回复必须是且只能是一个 JSON 对象：tool_call 或 final 信封。不要输出 Markdown、解释或 JSON 外文本。
7. 可用只读工具：{tool_names}。每个工具参数都必须含 project_id={project_id}。

项目 ID：{project_id}
Word 正文（证据偏移以此文本为准）：
{document_text}
"""


def _parse_envelope(text: str) -> ToolCallEnvelope | FinalEnvelope:
    def reject_non_standard_constant(constant: str) -> None:
        raise ValueError(f"non-standard JSON constant: {constant}")

    try:
        payload = json.loads(text, parse_constant=reject_non_standard_constant)
    except (TypeError, ValueError) as exc:
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
    stored_event = deepcopy(event)
    events.append(stored_event)
    if on_event is not None:
        on_event(deepcopy(stored_event))


def run_project_meeting_agent(
    project_id: int,
    document_text: str,
    snapshot: dict[str, Any],
    tools: ProjectMeetingAgentTools,
    provider: Callable[[str], AgentModelResponse],
    on_event: Callable[[dict[str, Any]], None] | None = None,
    require_plan_lookup: bool = False,
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
    base_prompt = _base_prompt(project_id, document_text)
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
            repair_instruction = (
                "A project plan lookup has already completed. "
                "Return a final envelope only; do not call any tool."
                if require_plan_lookup and any(item.get("tool") == "search_plan_nodes" for item in trace)
                else "Return only one valid tool_call or final JSON object."
            )
            prompt = (
                f"{base_prompt}\n上一条模型回复不符合严格 JSON 信封，原因：{exc}。\n"
                f"无效回复：{response.text}\n请仅返回一个合法 tool_call 或 final JSON 对象。"
                f"\n{repair_instruction}"
            )
            continue

        if isinstance(envelope, FinalEnvelope):
            if require_plan_lookup and not any(item.get("tool") == "search_plan_nodes" for item in trace):
                _emit(events, on_event, {
                    "kind": "final_deferred",
                    "step": step,
                    "reason": "missing_plan_lookup",
                    "model_code": response.model_code,
                    "invocation_log_id": response.invocation_log_id,
                })
                prompt = (
                    f"{base_prompt}\nYou must call search_plan_nodes before a final response. "
                    "Return one valid tool_call envelope now; do not return final yet."
                )
                continue
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
        if step == MAX_AGENT_STEPS - 1:
            prompt = (
                f"{base_prompt}\n工具调用轨迹（仅项目上下文，不是会议事实证据）：\n"
                f"{json.dumps(trace, ensure_ascii=False)}\n"
                "This was the last allowed tool query. You must return final now; "
                "do not call another tool. Put any unmatched action in open_questions."
            )
        elif require_plan_lookup and envelope.tool == "search_plan_nodes":
            prompt = (
                f"{base_prompt}\n工具调用轨迹（仅项目上下文，不是会议事实证据）：\n"
                f"{json.dumps(trace, ensure_ascii=False)}\n"
                "Plan lookup requirement is fulfilled. Do not call search_plan_nodes again. "
                "Return final now, unless one get_plan_node_detail call is essential to make a safe task update; "
                "put every unmatched action in open_questions."
            )
        else:
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
