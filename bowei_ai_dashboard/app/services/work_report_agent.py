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
    completed_markers = ("完成", "上线", "交付", "发布", "落地", "解决", "整理")
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


def merge_task_cards(cards: list[dict]) -> list[dict]:
    """Merge only cards already matched to the same real key task."""
    merged: list[dict] = []
    positions: dict[int, int] = {}
    for card in cards:
        subtask_id = card.get("matched_subtask_id") if card.get("match_status") == MATCHED else None
        if not subtask_id or subtask_id not in positions:
            if subtask_id:
                positions[subtask_id] = len(merged)
            merged.append(card)
            continue
        target = merged[positions[subtask_id]]
        target["evidence"] = _dedupe(target["evidence"] + card["evidence"])
        target["completed"] = "\n".join(_dedupe([value for value in [target["completed"], card["completed"]] if value]))
        for field in ("achievements", "subtask_issues", "next_steps"):
            target[field] = _dedupe(target[field] + card[field])
        if card.get("status_update"):
            target["status_update"] = card["status_update"]
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


def _agent_prompt(text: str, candidates: list[dict]) -> str:
    context = json.dumps([_public_candidate(item) for item in candidates], ensure_ascii=False)
    return f"""你是跨项目工作汇报 Agent。只拆分用户实际提到的工作，不得为未提及任务生成卡片，不得因未提及推断无进展或延期。
候选任务仅用于理解语义，不要输出或选择任务 ID；归属由后续安全匹配器处理。
请将原文拆成语义片段，每个片段必须给出原文逐字证据 evidence，并仅提取明确提到的 completed、achievements、subtask_issues、next_steps、status_update。
候选上下文：{context}
原文：{text}
只输出 JSON：{{"fragments":[{{"evidence":"原文逐字片段","completed":"","achievements":[],"subtask_issues":[],"next_steps":[],"status_update":""}}]}}"""


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


def extract_work_report_agent(transcript_text: str, candidates: list[dict], provider: str,
                              llm_call: Callable[[str, str], dict] = _call_agent_llm) -> dict:
    """Run the full Agent pipeline with one LLM call and deterministic matching."""
    if not transcript_text.strip():
        return build_work_report_draft(transcript_text, candidates, [])
    parsed = llm_call(_agent_prompt(transcript_text, candidates), provider)
    fragments = parsed.get("fragments") or []
    if not isinstance(fragments, list):
        raise RuntimeError("AI Agent 返回的 fragments 格式无效")
    return build_work_report_draft(transcript_text, candidates, fragments)
