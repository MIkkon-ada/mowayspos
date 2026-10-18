"""Bounded, tool-using Agent for project meeting Word documents."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import ValidationError

from .project_meeting_agent_contracts import (
    FinalEnvelope,
    MeetingAgentFinal,
    ProjectDelta,
    ProjectEvidence,
    ProjectMatch,
    StandardFactBatchResult,
    ToolCallEnvelope,
)
from .project_meeting_agent_tools import AgentToolError, ProjectMeetingAgentTools


PROMPT_VERSION = "project-meeting-agent-v4-batched-complete-analysis"
MAX_AGENT_STEPS = 6
MAX_INVALID_OUTPUT_REPAIRS = 4
MAX_STANDARD_FACTS_PER_BATCH = 8


@dataclass(frozen=True)
class AgentModelResponse:
    text: str
    model_code: str
    invocation_log_id: int
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


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
    *,
    standard_minutes: bool = False,
    standard_fact_inventory: list[dict[str, Any]] | None = None,
) -> str:
    tool_names = ", ".join(ProjectMeetingAgentTools.TOOL_NAMES)
    standard_fact_list = "\n".join(
        f"- {item['fact_id']} [{item['fact_type']}] span={item['evidence']['char_start']}:{item['evidence']['char_end']} {item['content']}"
        for item in (standard_fact_inventory or [])
    )
    standard_fact_contract = (
        "\n服务端解析得到的标准纪要事实编号及精确原文跨度（必须使用这些 ID 和跨度，每项恰好分类一次；不得新造或遗漏）：\n"
        f"{standard_fact_list}\n"
        if standard_minutes and standard_fact_list else ""
    )
    protocol_examples = """
STRICT RESPONSE PROTOCOL (this overrides any older meeting-minutes JSON format):
- Return exactly one JSON object, with no Markdown fences and no explanatory text.
- A tool request must be exactly this shape:
  {"type":"tool_call","tool":"get_project_profile","arguments":{"project_id":1}}
- A completed analysis must be exactly this shape (include every listed result field):
  {"type":"final","result":{"meeting_info":{"title":"","meeting_date":"","meeting_type":"","location":"","host":"","participants":[],"organizer":"","copied_to":[]},"meeting_info_evidence":{},"summary":"","summary_evidence":[],"agenda_items":[],"decisions":[],"completed_items":[],"next_steps":[],"risks":[],"open_questions":[],"prior_action_tracking":[],"task_updates":[],"meeting_facts":[],"project_matches":[],"project_deltas":[],"proposed_changes":[],"unmatched_items":[],"needs_confirmation":[]}}
- meeting_info_evidence is a mapping from field name to an ARRAY of spans, never one span object:
  {"meeting_date":[{"quote":"2026-07-27","char_start":0,"char_end":10}]}
- Every item in agenda_items, decisions, completed_items, next_steps, risks, and open_questions has exactly this shape:
  {"content":"Action description","topic":"","owner":"","tracker":"","due_date":"","source_note":"","evidence":[{"quote":"exact Word quote","char_start":0,"char_end":16}],"confidence":0.9,"needs_confirmation":false}
- In decisions, topic is a short meaningful heading shared by related discussion points. Preserve the substantive meeting discussion and conclusion, grouping points under their topic in source order; do not output generic headings such as 会议事项1. For other fact arrays, topic is empty.
- For next_steps, source_note summarizes an explicitly supported source or condition, never a fabricated assignment. Leave owner/tracker/due_date empty when the Word does not state them.
- prior_action_tracking contains only follow-up items with a status or progress explicitly stated in THIS Word document, not items copied from previous meeting context. Shape: {"content":"Previous action","owner":"","status":"in progress","progress_note":"current document update","evidence":[{"quote":"exact Word quote","char_start":0,"char_end":16}],"confidence":0.9,"needs_confirmation":false}. For a first meeting, return [].
- Action-only facts may include owner, tracker, and due_date only when each value is explicitly stated in Word evidence. Keep an unavailable field as an empty string; never infer it from the project plan. For agenda, decision, completion, risk, and open-question facts, leave all three fields empty.
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
- Standard-minute discussion facts use inventory label [discussion]; classify each into its actual supported fact_type (action_item, decision, completion, progress, risk, output, or scope) based on the Word wording. Current action and prior-action inventory types are fixed as action_item and progress.
- Never put an ID string such as "F001" in unmatched_items or needs_confirmation. Move the complete fact object out of meeting_facts before placing it in unmatched_items or needs_confirmation.
- Use these exact analysis object shapes (replace example values with evidence-grounded values; never omit required keys):
  meeting_facts item: {"fact_id":"F001","fact_type":"action_item","content":"Prepare customer shortlist","fields":{"status":{"value":"in_progress","raw_text":"正在推进","evidence":[{"quote":"正在推进","char_start":0,"char_end":4}],"provenance":{"source_type":"meeting_fact","source_fact_id":"F001","usage":"new"}}},"meeting_evidence":[{"quote":"正在推进","char_start":0,"char_end":4}],"confidence":0.9,"needs_confirmation":false}
  project_matches item: {"match_id":"M001","fact_id":"F001","target_type":"key_task","target_id":20,"workstream_id":10,"key_task_id":20,"confidence":0.9,"reasons":["title and intent match"],"project_evidence":[{"source_object":"key_task","field":"title","value":"Customer shortlist"}]}
  project_deltas item: {"delta_id":"D001","source_fact_id":"F001","source_match_id":"M001","delta_type":"PROGRESS_UPDATE","reasoning":"Word states current progress"}
  proposed_changes item: {"change_id":"C001","source_fact_id":"F001","source_match_id":"M001","source_delta_id":"D001","action":"update_execution_schedule","target":{"project_id":1,"workstream_id":10,"key_task_id":20,"execution_schedule_id":30},"before":{"status":"pending"},"proposed":{"status":"in_progress"},"field_sources":{"status":{"source_type":"meeting_fact","source_fact_id":"F001","usage":"new"}},"requires_confirmation":true}
- If a fact has no structured business field, emit fields as {} and do not create a Proposed Change. A Proposed Change is allowed only when every proposed field has field_sources and each meeting_fact field source names the same F-series fact containing that field-level Word evidence.
- In a fact's fields object, omit every field that is not explicitly stated in the Word. Never output an empty SourcedValue or a value without non-empty raw_text and evidence.
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
8. 会议纪要成稿使用：标题与会议信息；一、会议议题；二、按议题分组的会议讨论与结论；三、本周行动项（事项、负责人、追踪人、完成时限、来源/备注）；若本次文档明确记载上期事项进展，再附上期待办追踪。整理人和抄送放页尾。事实必须来自本次文档，缺失字段保持空值。

{("标准 Word 已由服务端完整解析；为了避免重复输出原文，请在 final 中将 meeting_info 的文本字段留空、participants/copied_to 留空数组、meeting_info_evidence 留空对象、summary 留空、summary_evidence 留空数组，并将 agenda_items、decisions、completed_items、next_steps、prior_action_tracking 留空数组。服务端会合并完整原文结构。你仍必须完成项目分析：对每一条决议、上期进展和本周行动事实都提供一个 F 编号，并且在 meeting_facts、unmatched_items、needs_confirmation 中恰好出现一次；不要漏项。只为确实需要用户确认的项目匹配或计划变更填写 open_questions、needs_confirmation。" if standard_minutes else "")}
{standard_fact_contract}

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
    _standard_fact_inventory_override: list[dict[str, Any]] | None = None,
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
    repair_requests = 0
    saw_output_truncation = False
    is_standard_minutes = bool(
        isinstance(snapshot.get("standard_minutes"), dict)
        and snapshot["standard_minutes"].get("is_standard_minutes")
    )
    try:
        full_standard_fact_inventory = _standard_fact_inventory(snapshot.get("standard_minutes"), document_text) if is_standard_minutes else []
    except ValueError as exc:
        raise MeetingAgentError("source_evidence_missing", str(exc), events=events) from exc
    if _standard_fact_inventory_override is None and is_standard_minutes:
        return _run_standard_fact_batches(
            project_id=project_id,
            document_text=document_text,
            snapshot=snapshot,
            tools=tools,
            provider=provider,
            on_event=on_event,
            require_plan_lookup=require_plan_lookup,
            inventory=full_standard_fact_inventory,
        )
    standard_fact_inventory = (
        _standard_fact_inventory_override
        if _standard_fact_inventory_override is not None
        else full_standard_fact_inventory
    )
    base_prompt = _base_prompt(
        project_id,
        document_text,
        standard_minutes=is_standard_minutes,
        standard_fact_inventory=standard_fact_inventory,
    )
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
            "finish_reason": response.finish_reason,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
        })
        saw_output_truncation = saw_output_truncation or response.finish_reason in {"length", "max_tokens"}
        try:
            response_text = (
                _normalize_standard_fact_evidence(response.text, standard_fact_inventory, document_text)
                if standard_fact_inventory else response.text
            )
            envelope = _parse_envelope(response_text)
            if isinstance(envelope, FinalEnvelope) and standard_fact_inventory:
                _validate_standard_fact_coverage(envelope.result, standard_fact_inventory)
        except ValueError as exc:
            if repair_requests >= MAX_INVALID_OUTPUT_REPAIRS:
                raise MeetingAgentError(
                    "truncated_model_output"
                    if saw_output_truncation
                    else "invalid_model_output",
                    (
                        f"model output reached its token limit after {repair_requests} repair requests"
                        if saw_output_truncation
                        else f"model response remained invalid after {repair_requests} repair requests"
                    ),
                    trace=trace,
                    raw_responses=raw_responses,
                    invocation_log_ids=invocation_log_ids,
                    events=events,
                ) from exc
            repair_requests += 1
            repair_instruction = (
                "A project plan lookup has already completed. "
                "Return a final envelope only; do not call any tool."
                if require_plan_lookup and any(item.get("tool") == "search_plan_nodes" for item in trace)
                else "Return only one valid tool_call or final JSON object."
            )
            truncation_note = (
                "上一条响应因达到模型输出上限而停止，请优先压缩分析说明，保留全部事实编号和每条对应的归类。"
                if response.finish_reason in {"length", "max_tokens"} else ""
            )
            tool_context = (
                "\n已经完成的项目检索结果（继续使用这些结果，不要重复调用工具）：\n"
                f"{json.dumps(trace, ensure_ascii=False)}\n"
                if trace else ""
            )
            prompt = (
                f"{base_prompt}\n上一条模型回复未通过 JSON/结构校验，原因：{exc}。\n"
                "请从头重新生成完整结果，不要复述上一条回复，也不要输出未闭合的 JSON；"
                "保持内容精炼但覆盖全部事实，每一条事实只保留一个分析条目。"
                "对于标准 Word，请使用服务端可识别的事实列表，不重复输出完整纪要字段。"
                "未能安全匹配的事实必须归到 unmatched_items 或 needs_confirmation，不得放入 meeting_facts 后省略项目匹配。"
                + truncation_note
                + tool_context
                + f"\n{repair_instruction}"
            )
            _emit(events, on_event, {
                "kind": "model_output_repair",
                "step": step,
                "repair_number": repair_requests,
            })
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


def _run_standard_fact_batches(
    *,
    project_id: int,
    document_text: str,
    snapshot: dict[str, Any],
    tools: ProjectMeetingAgentTools,
    provider: Callable[[str], AgentModelResponse],
    on_event: Callable[[dict[str, Any]], None] | None,
    require_plan_lookup: bool,
    inventory: list[dict[str, Any]],
) -> MeetingAgentRunResult:
    batches = [
        inventory[index:index + MAX_STANDARD_FACTS_PER_BATCH]
        for index in range(0, len(inventory), MAX_STANDARD_FACTS_PER_BATCH)
    ]
    traces: list[dict[str, Any]] = []
    raw_responses: list[str] = []
    invocation_log_ids: list[int] = []
    events: list[dict[str, Any]] = []
    total_steps = 0
    final_payload: dict[str, Any] = {
        "meeting_info": {"title": "", "meeting_date": "", "meeting_type": "", "location": "", "host": "", "participants": [], "organizer": "", "copied_to": []},
        "meeting_info_evidence": {}, "summary": "", "summary_evidence": [],
        "agenda_items": [], "decisions": [], "completed_items": [], "next_steps": [], "risks": [],
        "open_questions": [], "prior_action_tracking": [], "task_updates": [],
        "meeting_facts": [], "project_matches": [], "project_deltas": [], "proposed_changes": [],
        "unmatched_items": [], "needs_confirmation": [],
    }
    last_model_code = ""

    for batch_number, batch in enumerate(batches, start=1):
        try:
            query_observation = tools.execute("search_plan_nodes", {
                "project_id": project_id,
                "queries": [{"fact_id": item["fact_id"], "query": item["content"]} for item in batch],
            })
        except AgentToolError as exc:
            raise MeetingAgentError("tool_error", str(exc), trace=traces, raw_responses=raw_responses,
                                    invocation_log_ids=invocation_log_ids, events=events) from exc
        batch_trace = {"step": 1, "tool": "search_plan_nodes", "arguments": {
            "project_id": project_id,
            "queries": [{"fact_id": item["fact_id"], "query": item["content"]} for item in batch],
        }, "result": query_observation, "batch": batch_number}
        traces.append(batch_trace)
        total_steps += 1
        lookup_event = {"kind": "tool_result", "step": total_steps, "tool": "search_plan_nodes",
                        "batch": batch_number, "batch_count": len(batches)}
        events.append(lookup_event)
        if on_event is not None:
            on_event(deepcopy(lookup_event))
        candidates_by_fact = {
            item["fact_id"]: item.get("candidates", [])
            for item in query_observation.get("results", [])
        }
        base_prompt = _standard_batch_prompt(project_id, batch, candidates_by_fact)
        prompt = base_prompt
        classifications = None
        saw_output_truncation = False
        batch_repair_count = 0
        batch_error = ""

        for attempt in range(MAX_INVALID_OUTPUT_REPAIRS + 1):
            try:
                response = provider(prompt)
            except Exception as exc:
                raise MeetingAgentError(
                    "provider_error", f"标准纪要事实批次 {batch_number}/{len(batches)} 调用模型失败：{exc}",
                    trace=traces, raw_responses=raw_responses,
                    invocation_log_ids=invocation_log_ids, events=events,
                ) from exc
            if not isinstance(response, AgentModelResponse):
                raise MeetingAgentError("provider_error", "provider must return AgentModelResponse",
                                        trace=traces, raw_responses=raw_responses,
                                        invocation_log_ids=invocation_log_ids, events=events)
            raw_responses.append(response.text)
            invocation_log_ids.append(response.invocation_log_id)
            last_model_code = response.model_code
            total_steps += 1
            saw_output_truncation = saw_output_truncation or response.finish_reason in {"length", "max_tokens"}
            event = {
                "kind": "model_response", "step": total_steps, "model_code": response.model_code,
                "invocation_log_id": response.invocation_log_id, "finish_reason": response.finish_reason,
                "prompt_tokens": response.prompt_tokens, "completion_tokens": response.completion_tokens,
                "batch": batch_number, "batch_count": len(batches),
            }
            events.append(event)
            if on_event is not None:
                on_event(deepcopy(event))
            try:
                decoded = json.loads(response.text)
                batch_result = StandardFactBatchResult.model_validate(decoded)
                _validate_standard_batch_result(batch_result, batch, candidates_by_fact)
                classifications = batch_result.facts
                break
            except (TypeError, ValueError, ValidationError) as exc:
                batch_error = str(exc)
                if batch_repair_count >= MAX_INVALID_OUTPUT_REPAIRS:
                    raise MeetingAgentError(
                        "truncated_model_output" if saw_output_truncation else "invalid_model_output",
                        f"标准纪要事实批次 {batch_number}/{len(batches)} 分析失败："
                        + ("模型输出达到上限，有限重试后仍未完成" if saw_output_truncation else "模型结果未通过事实覆盖或匹配校验"),
                        trace=traces, raw_responses=raw_responses,
                        invocation_log_ids=invocation_log_ids, events=events,
                    ) from exc
                batch_repair_count += 1
                repair_event = {"kind": "model_output_repair", "step": total_steps,
                                "repair_number": batch_repair_count, "batch": batch_number,
                                "batch_count": len(batches)}
                events.append(repair_event)
                if on_event is not None:
                    on_event(deepcopy(repair_event))
                prompt = (
                    f"{base_prompt}\n上一条输出未通过校验，原因：{batch_error}。"
                    "请只返回符合给定结构的 JSON；每个事实编号只能出现一次。"
                    "匹配项的 target_id 必须来自对应事实的候选列表；无安全匹配时标记 unmatched 或 needs_confirmation。"
                    "不要输出原文证据、字段值、项目写回或完整会议纪要。"
                )

        if classifications is None:
            raise MeetingAgentError("invalid_model_output", f"标准纪要事实批次 {batch_number} 无有效结果",
                                    trace=traces, raw_responses=raw_responses,
                                    invocation_log_ids=invocation_log_ids, events=events)
        for classification in classifications:
            source = next(item for item in batch if item["fact_id"] == classification.fact_id)
            if source["fact_type"] != "discussion" and classification.fact_type != source["fact_type"]:
                raise MeetingAgentError("invalid_model_output", f"事实类型与来源不符：{classification.fact_id}",
                                        trace=traces, raw_responses=raw_responses,
                                        invocation_log_ids=invocation_log_ids, events=events)
            fact_data = {
                "fact_id": source["fact_id"],
                "fact_type": classification.fact_type,
                "content": source["content"],
                "reason": classification.reason,
                "fields": {},
                "meeting_evidence": [source["evidence"]],
                "confidence": classification.confidence,
                "needs_confirmation": classification.disposition == "needs_confirmation",
            }
            if classification.disposition == "unmatched":
                final_payload["unmatched_items"].append(fact_data)
            elif classification.disposition == "needs_confirmation":
                final_payload["needs_confirmation"].append(fact_data)
                final_payload["open_questions"].append({
                    "content": source["content"], "topic": "", "owner": "", "tracker": "",
                    "due_date": "", "source_note": classification.reason,
                    "evidence": [source["evidence"]], "confidence": classification.confidence,
                    "needs_confirmation": True,
                })
            else:
                candidate = next((item for item in candidates_by_fact.get(classification.fact_id, [])
                                  if item.get("target_id") == classification.target_id), None)
                if candidate is None:
                    raise MeetingAgentError("invalid_model_output", f"匹配目标不属于事实候选项：{classification.fact_id}",
                                            trace=traces, raw_responses=raw_responses,
                                            invocation_log_ids=invocation_log_ids, events=events)
                final_payload["meeting_facts"].append(fact_data)
                number = int(source["fact_id"][1:])
                match_id = f"M{number:03d}"
                delta_id = f"D{number:03d}"
                final_payload["project_matches"].append({
                    "match_id": match_id, "fact_id": source["fact_id"],
                    "target_type": candidate["target_type"], "target_id": candidate["target_id"],
                    "workstream_id": candidate.get("workstream_id"),
                    "key_task_id": candidate["target_id"], "confidence": classification.confidence,
                    "reasons": [classification.reason],
                    "project_evidence": [{"source_object": f"{candidate['target_type']}:{candidate['target_id']}", "field": "key_task" if candidate["target_type"] == "workstream" else "title", "value": candidate.get("title", "")}],
                })
                final_payload["project_deltas"].append({
                    "delta_id": delta_id, "source_fact_id": source["fact_id"],
                    "source_match_id": match_id, "delta_type": classification.delta_type,
                    "reasoning": classification.delta_reason,
                })

    final = MeetingAgentFinal.model_validate(final_payload)
    _validate_standard_fact_coverage(final, inventory)
    return MeetingAgentRunResult(
        final=final,
        trace=traces,
        raw_responses=raw_responses,
        invocation_log_ids=invocation_log_ids,
        events=events,
        model_code=last_model_code,
        step_count=total_steps,
    )


def _standard_batch_prompt(
    project_id: int,
    batch: list[dict[str, Any]],
    candidates_by_fact: dict[str, list[dict[str, Any]]],
) -> str:
    facts = [{"fact_id": item["fact_id"], "expected_type": item["fact_type"], "content": item["content"]} for item in batch]
    return f"""你负责分析标准 Word 会议纪要的一小批事实。只根据输入的事实与项目候选项作判断，不输出会议纪要正文。

项目 ID：{project_id}
事实及该项目的检索候选项：
{json.dumps({"facts": facts, "project_candidates": candidates_by_fact}, ensure_ascii=False, separators=(",", ":"))}

请只返回如下 JSON 对象，不要 Markdown 或其他文字：
{{"facts":[{{"fact_id":"F001","fact_type":"decision","disposition":"matched","target_id":12,"confidence":0.85,"reason":"事实与候选任务目标一致","delta_type":"PROGRESS_UPDATE","delta_reason":"会议记录表明该任务有新的推进"}}]}}

规则：
1. 输出 facts 必须对输入每个 fact_id 恰好一条，不能遗漏、重复或新造编号；content 不要输出，服务端会原样保留 Word 内容。
2. 讨论事实 expected_type=discussion 时，按原文准确分类为 action_item、decision、completion、progress、risk、output、scope；确实无法判定时可用 discussion。固定类型 action_item/progress 必须原样保留。
3. disposition 只能是 matched、unmatched、needs_confirmation。matched 必须选择同一 fact_id 候选列表中的 target_id；没有安全匹配时用 unmatched；多个候选无法判定时用 needs_confirmation。
4. matched 必须给出 delta_type 和 delta_reason。delta_type 只能是 NO_CHANGE、PROGRESS_UPDATE、STATUS_CHANGE、NEW_EXECUTION_SCHEDULE、SCHEDULE_CHANGE、ASSIGNEE_CHANGE、NEW_RISK、RISK_UPDATE、NEW_OUTPUT、COMPLETION、SCOPE_CHANGE。只对实际与项目基线相关的差异分类；无变化用 NO_CHANGE。
5. unmatched 和 needs_confirmation 不得输出 target_id、delta_type、delta_reason。reason 简明说明归类或匹配依据。
6. 不生成负责人、日期等字段值，不生成证据跨度，不提出项目写回，不要把未匹配事实伪装为 matched。
7. confidence 为 0 到 1 的数字。
"""


def _validate_standard_batch_result(
    result: StandardFactBatchResult,
    batch: list[dict[str, Any]],
    candidates_by_fact: dict[str, list[dict[str, Any]]],
) -> None:
    expected = {item["fact_id"]: item for item in batch}
    counts: dict[str, int] = {}
    for classification in result.facts:
        counts[classification.fact_id] = counts.get(classification.fact_id, 0) + 1
    missing = sorted(set(expected) - set(counts))
    unknown = sorted(set(counts) - set(expected))
    duplicated = sorted(fact_id for fact_id, count in counts.items() if count != 1)
    wrong_type = sorted(
        item.fact_id for item in result.facts
        if item.fact_id in expected
        and expected[item.fact_id]["fact_type"] != "discussion"
        and item.fact_type != expected[item.fact_id]["fact_type"]
    )
    invalid_match = sorted(
        item.fact_id for item in result.facts
        if item.disposition == "matched"
        and not any(candidate.get("target_id") == item.target_id for candidate in candidates_by_fact.get(item.fact_id, []))
    )
    if missing or unknown or duplicated or wrong_type or invalid_match:
        problems = []
        if missing:
            problems.append(f"缺少事实编号 {', '.join(missing)}")
        if unknown:
            problems.append(f"存在未来源事实编号 {', '.join(unknown)}")
        if duplicated:
            problems.append(f"事实编号重复 {', '.join(duplicated)}")
        if wrong_type:
            problems.append(f"固定事实类型错误 {', '.join(wrong_type)}")
        if invalid_match:
            problems.append(f"项目匹配目标不在候选列表 {', '.join(invalid_match)}")
        raise ValueError("批次覆盖校验失败：" + "；".join(problems))


def _standard_fact_inventory(standard: Any, document_text: str) -> list[dict[str, Any]]:
    if not isinstance(standard, dict) or not standard.get("is_standard_minutes"):
        return []
    facts: list[dict[str, Any]] = []
    cursor = 0

    def add(fact_type: str, content: Any) -> None:
        nonlocal cursor
        value = str(content or "").strip()
        if value:
            start = document_text.find(value, cursor)
            if start < 0:
                start = document_text.find(value)
            evidence = (
                {"quote": value, "char_start": start, "char_end": start + len(value)}
                if start >= 0 else None
            )
            if evidence is None:
                raise ValueError(f"standard meeting fact F{len(facts) + 1:03} cannot be located in extracted source text")
            cursor = start + len(value)
            facts.append({
                "fact_id": f"F{len(facts) + 1:03}",
                "fact_type": fact_type,
                "content": value,
                "evidence": evidence,
            })

    for section in standard.get("discussion_sections", []):
        if not isinstance(section, dict):
            continue
        for point in section.get("points", []):
            # Discussion content can describe a decision, risk, progress, output,
            # completion, scope change, or an action. Let the model classify it.
            add("discussion", point)
    for row in standard.get("current_action_items", []):
        if isinstance(row, dict):
            add("action_item", row.get("会议安排事项"))
    for row in standard.get("prior_action_items", []):
        if isinstance(row, dict):
            add("progress", row.get("上周事项"))
    return facts


def _normalize_standard_fact_evidence(
    response_text: str,
    inventory: list[dict[str, Any]],
    document_text: str,
) -> str:
    """Replace model-invented offsets with deterministic spans from source text."""
    try:
        payload = json.loads(response_text)
    except (TypeError, ValueError):
        return response_text
    if not isinstance(payload, dict) or payload.get("type") != "final":
        return response_text
    result = payload.get("result")
    if not isinstance(result, dict):
        return response_text
    source_by_id = {item["fact_id"]: item for item in inventory}
    for field in ("meeting_facts", "unmatched_items", "needs_confirmation"):
        facts = result.get(field)
        if not isinstance(facts, list):
            continue
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            source = source_by_id.get(fact.get("fact_id"))
            if source is None:
                continue
            fact["meeting_evidence"] = [source["evidence"]]
            sourced_fields = fact.get("fields")
            if not isinstance(sourced_fields, dict):
                continue
            for field_name, sourced_value in list(sourced_fields.items()):
                if not isinstance(sourced_value, dict):
                    continue
                raw_text = str(sourced_value.get("raw_text") or "").strip()
                if not raw_text:
                    sourced_fields.pop(field_name, None)
                    continue
                start = document_text.find(raw_text)
                if start >= 0:
                    sourced_value["evidence"] = [{
                        "quote": raw_text,
                        "char_start": start,
                        "char_end": start + len(raw_text),
                    }]
    return json.dumps(payload, ensure_ascii=False)


def _validate_standard_fact_coverage(result: MeetingAgentFinal, inventory: list[dict[str, Any]]) -> None:
    expected = {item["fact_id"]: item for item in inventory}
    classified = (*result.meeting_facts, *result.unmatched_items, *result.needs_confirmation)
    counts: dict[str, int] = {}
    for fact in classified:
        counts[fact.fact_id] = counts.get(fact.fact_id, 0) + 1
    actual = set(counts)
    missing = sorted(set(expected) - actual)
    unknown = sorted(actual - set(expected))
    duplicated = sorted(fact_id for fact_id, count in counts.items() if count != 1)
    wrong_type = sorted(
        fact.fact_id for fact in classified
        if fact.fact_id in expected and not (
            expected[fact.fact_id]["fact_type"] == "discussion"
            and fact.fact_type in {"action_item", "decision", "completion", "progress", "risk", "output", "scope", "discussion"}
        ) and fact.fact_type != expected[fact.fact_id]["fact_type"]
    )
    changed_content = sorted(
        fact.fact_id for fact in classified
        if fact.fact_id in expected and fact.content.strip() != expected[fact.fact_id]["content"]
    )
    unmatched_project_matches = sorted(
        fact.fact_id for fact in result.meeting_facts
        if fact.fact_id not in {match.fact_id for match in result.project_matches}
    )
    if missing or unknown or duplicated or wrong_type or changed_content or unmatched_project_matches:
        details = []
        if missing:
            details.append(f"缺少事实编号 {', '.join(missing)}")
        if unknown:
            details.append(f"存在未来源事实编号 {', '.join(unknown)}")
        if duplicated:
            details.append(f"事实被重复分类 {', '.join(duplicated)}")
        if wrong_type:
            details.append(f"事实类型与原文不符 {', '.join(wrong_type)}")
        if changed_content:
            details.append(f"事实内容与解析原文不符 {', '.join(changed_content)}")
        if unmatched_project_matches:
            details.append(f"缺少项目匹配结果 {', '.join(unmatched_project_matches)}")
        raise ValueError("标准纪要事实覆盖不完整：" + "；".join(details))
