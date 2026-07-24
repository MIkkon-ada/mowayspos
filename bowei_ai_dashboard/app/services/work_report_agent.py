"""Cross-project work-report extraction agent.

The agent separates extraction from ownership matching: the LLM identifies only
content explicitly present in the report, while deterministic matching keeps
ambiguous and unmatched ownership visible for human confirmation.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from .extractor import _extract_json_blob, _get_cfg

MATCHED = "matched"
NEEDS_CONFIRMATION = "needs_confirmation"
UNMATCHED = "unmatched"

_CARD_FIELDS = (
    "project_id", "project_name", "parent_task_id", "parent_key_task",
    "subtask_id", "subtask_title", "status", "assignee", "user_relation",
    "completion_criteria", "plan_time",
)


def split_semantic_fragments(text: str) -> list[str]:
    """Split a report into non-empty semantic clauses without creating work."""
    return [part.strip(" ，,。；;\n") for part in re.split(r"[。！？；;\n]+", text or "") if part.strip(" ，,。；;\n")]


def _compact(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", (value or "").lower())


def _longest_common_substring(left: str, right: str) -> int:
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    best = 0
    for char in left:
        current = [0]
        for index, other in enumerate(right, 1):
            size = previous[index - 1] + 1 if char == other else 0
            current.append(size)
            best = max(best, size)
        previous = current
    return best


def _candidate_score(evidence: str, candidate: dict) -> float:
    text = _compact(evidence)
    title = _compact(str(candidate.get("subtask_title") or candidate.get("title") or ""))
    project = _compact(str(candidate.get("project_name") or ""))
    parent = _compact(str(candidate.get("parent_key_task") or ""))
    if not text or not title:
        return 0.0
    if title in text:
        score = 1.0
    else:
        common = _longest_common_substring(text, title)
        score = common / max(len(title), 1) if common >= 2 else 0.0
    if project and project in text:
        score += 0.2
    if parent and parent in text:
        score += 0.15
    return min(score, 1.0)


def _public_candidate(candidate: dict) -> dict:
    return {field: candidate.get(field) for field in _CARD_FIELDS}


def match_fragment(evidence: str, candidates: list[dict]) -> dict:
    """Return a safe three-state ownership match; never pick a close tie."""
    ranked = sorted(((_candidate_score(evidence, item), item) for item in candidates), key=lambda row: row[0], reverse=True)
    if not ranked or ranked[0][0] < 0.45:
        return {"match_status": UNMATCHED, "match_confidence": ranked[0][0] if ranked else 0.0,
                "match_reason": "未找到足够可靠的任务归属", "matched": None, "match_candidates": []}
    best_score = ranked[0][0]
    plausible = [item for score, item in ranked if score >= 0.45 and best_score - score <= 0.08]
    if len(plausible) > 1:
        return {"match_status": NEEDS_CONFIRMATION, "match_confidence": best_score,
                "match_reason": "存在多个相近候选，需要人工确认", "matched": None,
                "match_candidates": [_public_candidate(item) for item in plausible]}
    return {"match_status": MATCHED, "match_confidence": best_score,
            "match_reason": "原文与任务名称或所属工作存在明确对应", "matched": ranked[0][1],
            "match_candidates": [_public_candidate(ranked[0][1])]}


def _dedupe(values: list) -> list:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _supported_values(values: list, evidence: str, markers: tuple[str, ...]) -> list[str]:
    """Keep only values explicitly present in evidence under the right semantic cue."""
    if not _has_any(evidence, markers):
        return []
    return _dedupe([
        str(value).strip()
        for value in values
        if str(value).strip() and str(value).strip() in evidence
    ])


def _sanitize_fragment(fragment: dict, evidence: str) -> dict:
    """Fail closed when the LLM adds content not supported by this report fragment."""
    completed = str(fragment.get("completed") or "").strip()
    completed_markers = ("完成", "上线", "交付", "发布", "落地", "解决", "整理", "修复")
    status_update = str(fragment.get("status_update") or "").strip()
    return {
        "evidence": evidence,
        # Preserve the user's wording instead of accepting an LLM paraphrase.
        "completed": evidence if completed and _has_any(evidence, completed_markers) else "",
        "achievements": _supported_values(
            list(fragment.get("achievements") or []), evidence,
            ("成果", "形成", "产出", "获得", "取得"),
        ),
        "subtask_issues": _supported_values(
            list(fragment.get("subtask_issues") or []), evidence,
            ("问题", "风险", "阻塞", "困难", "卡点", "异常"),
        ),
        "next_steps": _supported_values(
            list(fragment.get("next_steps") or []), evidence,
            ("下一步", "计划", "后续", "准备", "预计", "将要"),
        ),
        "status_update": status_update
        if "状态" in evidence and status_update and status_update in evidence
        else "",
    }


def _make_card(fragment: dict, match: dict) -> dict:
    matched = match["matched"] or {}
    return {
        "type": "progress",
        "project_id": matched.get("project_id"),
        "project_name": matched.get("project_name", ""),
        "parent_task_id": matched.get("parent_task_id"),
        "parent_key_task": matched.get("parent_key_task", ""),
        "matched_subtask_id": matched.get("subtask_id"),
        "matched_subtask_title": matched.get("subtask_title", ""),
        "match_status": match["match_status"],
        "match_confidence": round(float(match["match_confidence"]), 3),
        "match_reason": match["match_reason"],
        "match_candidates": match["match_candidates"],
        "evidence": [fragment["evidence"]],
        "completed": str(fragment.get("completed") or "").strip(),
        "achievements": list(fragment.get("achievements") or []),
        "subtask_issues": list(fragment.get("subtask_issues") or []),
        "next_steps": list(fragment.get("next_steps") or []),
        "status_update": str(fragment.get("status_update") or "").strip(),
    }


def _candidate_by_subtask_id(candidates: list[dict]) -> dict[int, dict]:
    result = {}
    for item in candidates:
        subtask_id = item.get("subtask_id") or item.get("id")
        if subtask_id is not None:
            result[int(subtask_id)] = item
    return result


def _normalize_agent_status(value: str) -> str:
    return value if value in {MATCHED, NEEDS_CONFIRMATION, UNMATCHED} else UNMATCHED


def _owner_priority(candidate: dict, submitter: str | None = None) -> int:
    submitter_name = str(submitter or "").strip()
    assignee = str(candidate.get("assignee") or "").strip()
    relation = str(candidate.get("user_relation") or "").strip()
    if submitter_name and assignee == submitter_name:
        return 0
    if relation == "subtask_assignee":
        return 0
    if relation == "task_owner":
        return 1
    return 2


def _unique_owner_preferred_candidate(candidates: list[dict], submitter: str | None = None) -> dict | None:
    if not candidates:
        return None
    ranked = sorted(candidates, key=lambda item: _owner_priority(item, submitter))
    best_priority = _owner_priority(ranked[0], submitter)
    best = [item for item in ranked if _owner_priority(item, submitter) == best_priority]
    return best[0] if len(best) == 1 else None


def _agent_evidence_fragments(report: dict, transcript_text: str) -> list[str]:
    """Return verbatim evidence clauses emitted for one task-level report."""
    raw_evidence = report.get("evidence")
    values = raw_evidence if isinstance(raw_evidence, list) else [raw_evidence]
    evidence = _dedupe([str(value).strip() for value in values if str(value or "").strip()])
    if not evidence or any(value not in transcript_text for value in evidence):
        raise ValueError("evidence must be verbatim substrings of transcript_text")
    return evidence


def _agent_business_fields(report: dict) -> dict:
    """Keep agent summaries separate from verbatim evidence validation."""
    def values(field: str) -> list[str]:
        raw = report.get(field) or []
        if not isinstance(raw, list):
            raw = [raw]
        return _dedupe([str(value).strip() for value in raw if str(value or "").strip()])

    return {
        "completed": str(report.get("completed") or "").strip(),
        "achievements": values("achievements"),
        "subtask_issues": values("subtask_issues"),
        "next_steps": values("next_steps"),
        "status_update": str(report.get("status_update") or "").strip(),
    }


def _make_ai_card(report: dict, candidates: list[dict], transcript_text: str, submitter: str | None = None) -> dict:
    evidence = _agent_evidence_fragments(report, transcript_text)

    candidate_map = _candidate_by_subtask_id(candidates)
    requested_id = report.get("matched_subtask_id")
    matched = candidate_map.get(int(requested_id)) if requested_id is not None else None
    status = _normalize_agent_status(str(report.get("match_status") or ""))
    invalid_explicit_id = requested_id is not None and matched is None
    if matched is None and not invalid_explicit_id and len(candidates) == 1:
        matched = candidates[0]
        status = MATCHED
    if status == MATCHED and matched is None:
        status = UNMATCHED

    candidate_ids = report.get("match_candidate_ids") or []
    actual_candidates = [
        candidate_map[int(item_id)]
        for item_id in candidate_ids
        if item_id is not None and int(item_id) in candidate_map
    ]
    public_candidates = [_public_candidate(candidate) for candidate in actual_candidates]
    if status == NEEDS_CONFIRMATION and matched is None:
        preferred = _unique_owner_preferred_candidate(actual_candidates or candidates, submitter)
        if preferred is not None:
            matched = preferred
            status = MATCHED
            public_candidates = [_public_candidate(matched)]
    if status == MATCHED and matched is not None and not public_candidates:
        public_candidates = [_public_candidate(matched)]

    fields = _agent_business_fields(report)
    return {
        "type": "progress",
        "project_id": matched.get("project_id") if matched else None,
        "project_name": matched.get("project_name", "") if matched else "",
        "parent_task_id": matched.get("parent_task_id") if matched else None,
        "parent_key_task": matched.get("parent_key_task", "") if matched else "",
        "matched_subtask_id": matched.get("subtask_id") if matched else None,
        "matched_subtask_title": matched.get("subtask_title", "") if matched else "",
        "match_status": status,
        "match_confidence": round(float(report.get("match_confidence") or (0.9 if matched else 0.0)), 3),
        "match_reason": "当前候选池只有一个可汇报任务，已自动归属到该任务。" if len(candidates) == 1 else str(report.get("match_reason") or "").strip(),
        "match_candidates": public_candidates if status != UNMATCHED else [],
        "evidence": evidence,
        "completed": fields["completed"],
        "achievements": fields["achievements"],
        "subtask_issues": fields["subtask_issues"],
        "next_steps": fields["next_steps"],
        "status_update": fields["status_update"],
    }


def build_ai_work_report_draft(transcript_text: str, candidates: list[dict], agent_reports: list[dict], submitter: str | None = None) -> dict:
    cards = [_make_ai_card(report, candidates, transcript_text, submitter) for report in agent_reports]
    task_reports = merge_task_cards(cards)
    return {"summary": f"AI 已识别 {len(task_reports)} 项工作", "task_reports": task_reports,
            "agent_steps": ["context", "agent_match", "evidence", "sanitize", "merge", "draft"]}


def _merge_card_content(target: dict, card: dict) -> None:
    target["evidence"] = _dedupe(target["evidence"] + card["evidence"])
    target["completed"] = "\n".join(_dedupe([value for value in [target["completed"], card["completed"]] if value]))
    for field in ("achievements", "subtask_issues", "next_steps"):
        target[field] = _dedupe(target[field] + card[field])
    if card.get("status_update"):
        target["status_update"] = card["status_update"]


def _is_followup_plan_only(card: dict) -> bool:
    return (
        card.get("match_status") != MATCHED
        and bool(card.get("next_steps"))
        and not card.get("completed")
        and not card.get("achievements")
        and not card.get("subtask_issues")
        and not card.get("status_update")
    )


def merge_task_cards(cards: list[dict]) -> list[dict]:
    """Merge cards that belong to the same real work item."""
    merged: list[dict] = []
    positions: dict[int, int] = {}
    for card in cards:
        subtask_id = card.get("matched_subtask_id") if card.get("match_status") == MATCHED else None
        if _is_followup_plan_only(card) and merged and merged[-1].get("match_status") == MATCHED:
            _merge_card_content(merged[-1], card)
            continue
        if not subtask_id or subtask_id not in positions:
            if subtask_id:
                positions[subtask_id] = len(merged)
            merged.append(card)
            continue
        target = merged[positions[subtask_id]]
        _merge_card_content(target, card)
    return merged


def build_work_report_draft(transcript_text: str, candidates: list[dict], extracted_fragments: list[dict]) -> dict:
    """Validate evidence, match fragments, merge same-task work, and return drafts."""
    cards = []
    for fragment in extracted_fragments:
        evidence = str(fragment.get("evidence") or "").strip()
        if not evidence or evidence not in transcript_text:
            raise ValueError("evidence must be a verbatim substring of transcript_text")
        cards.append(_make_card(_sanitize_fragment(fragment, evidence), match_fragment(evidence, candidates)))
    task_reports = merge_task_cards(cards)
    return {"summary": f"AI 已识别 {len(task_reports)} 项工作", "task_reports": task_reports,
            "agent_steps": ["split", "match", "evidence", "extract", "merge", "mark_uncertain", "draft"]}


def build_legacy_fragment_draft(transcript_text: str, candidates: list[dict], fragments: list[dict]) -> dict:
    """Handle old LLM fragment-only responses without falling back to title scoring."""
    cards = []
    candidate_ids = [item.get("subtask_id") or item.get("id") for item in candidates]
    for fragment in fragments:
        evidence = str(fragment.get("evidence") or "").strip()
        if not evidence or evidence not in transcript_text:
            raise ValueError("evidence must be a verbatim substring of transcript_text")
        report = {
            **fragment,
            "match_status": NEEDS_CONFIRMATION if candidates else UNMATCHED,
            "matched_subtask_id": None,
            "match_candidate_ids": candidate_ids,
            "match_confidence": 0.0,
            "match_reason": "AI returned content without an explicit task decision; candidates are shown for confirmation.",
        }
        cards.append(_make_ai_card(report, candidates, transcript_text))
    task_reports = merge_task_cards(cards)
    return {"summary": f"AI 已识别 {len(task_reports)} 项工作", "task_reports": task_reports,
            "agent_steps": ["context", "legacy_fragment", "evidence", "candidate_confirmation", "draft"]}


def _agent_prompt(text: str, candidates: list[dict]) -> str:
    context = json.dumps([_public_candidate(item) for item in candidates], ensure_ascii=False)
    return f"""你是工作汇报提交理解 Agent。候选上下文已经按当前登录用户的权限、项目成员关系和任务责任范围筛选；只能在这些候选任务中判断归属。

先完整理解这一次提交，先按真实任务聚合，再决定它实际涉及几项真实任务。不要按句号、逗号或单个动作机械拆卡：同一任务的完成、计划、风险和成果必须归入同一张 task_report。只有工作对象、交付物或候选任务语义明显变化时，才输出多张卡。

对每个真实任务输出一张 task_report：
- evidence 是原文逐字片段数组，每一项都必须能在原文中找到；它用于审核追溯。
- completed、achievements、subtask_issues、next_steps、status_update 是业务化归纳，可以把口语原文改写成清晰完整的工作表达，但不得添加原文不支持的事实、成果、风险或承诺。
- matched：结合候选任务的标题、所属重点工作、责任关系、完成标准和本次原文，能合理归属到某任务；matched_subtask_id 必须填写候选中的 ID。
- needs_confirmation：存在多个同等合理的候选；matched_subtask_id 为 null，match_candidate_ids 填候选 ID。
- unmatched：确实与任何候选任务都无法建立合理关联；matched_subtask_id 为 null。
- 若候选池只有一项，且原文描述的是该用户的正常工作进展，应优先归属到该任务，不要因为原文未复述任务标题而要求确认。

只报告用户实际提到的工作，不得为未提及任务生成“无进展”或“延期”等卡片。不得编造候选池外的 subtask_id。

候选任务上下文：{context}
本次提交原文：{text}

只输出 JSON：{{"task_reports":[{{"evidence":["原文逐字片段"],"match_status":"matched","matched_subtask_id":123,"match_candidate_ids":[],"match_confidence":0.9,"match_reason":"简要说明归属判断理由","completed":"清晰的完成内容归纳","achievements":["业务化成果归纳"],"subtask_issues":["业务化风险或问题归纳"],"next_steps":["清晰的下一步计划归纳"],"status_update":"业务化进度说明"}}]}}"""


def _call_agent_llm(prompt: str, provider: str) -> dict:
    cfg = _get_cfg(provider)
    if not cfg.get("api_key"):
        raise RuntimeError(f"AI引擎（{provider}）未配置 API Key")
    if provider == "anthropic":
        import anthropic
        response = anthropic.Anthropic(api_key=cfg["api_key"]).messages.create(
            model=cfg["model"], max_tokens=4000, messages=[{"role": "user", "content": prompt}])
        raw = response.content[0].text
    else:
        from openai import OpenAI
        response = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"]).chat.completions.create(
            model=cfg["model"], messages=[{"role": "user", "content": prompt}], max_tokens=4000)
        raw = response.choices[0].message.content or ""
    return _extract_json_blob(raw)


def extract_work_report_agent(transcript_text: str, candidates: list[dict], provider: str, submitter: str | None = None,
                              llm_call: Callable[[str, str], dict] = _call_agent_llm) -> dict:
    """Run the full Agent pipeline with one LLM call and server-side ID validation."""
    if not transcript_text.strip():
        return build_ai_work_report_draft(transcript_text, candidates, [], submitter)
    parsed = llm_call(_agent_prompt(transcript_text, candidates), provider)
    if isinstance(parsed.get("task_reports"), list):
        return build_ai_work_report_draft(transcript_text, candidates, parsed["task_reports"], submitter)
    fragments = parsed.get("fragments") or []
    if not isinstance(fragments, list):
        raise RuntimeError("AI Agent 返回的 fragments 格式无效")
    return build_legacy_fragment_draft(transcript_text, candidates, fragments)
